import argparse
import atexit
import pandas as pd

from utils.oci import *

logger = logging.getLogger("server")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def exit_handler(console_socket_proc, console_socket_file,
                 container_name):
    stop_container_and_console_socket(console_socket_proc, console_socket_file,
                                      container_name)


def stop_container_and_console_socket(console_socket_proc, console_socket_file,
                                      container_name):
    # Possibly stop the container and the console socket.
    cmd = "sudo runc kill {} KILL".format(container_name)
    logger.info("Running '{}'".format(cmd))
    os.system(cmd)

    cmd = "sudo runc delete " + container_name
    logger.info("Running '{}'".format(cmd))
    os.system(cmd)

    stop_console_socket(console_socket_proc, console_socket_file)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild_image",
                        dest="rebuild_image", action="store_true",
                        default=False)
    parser.add_argument("--repetitions", dest="repetitions", action="store",
                        required=True, type=int)
    return parser.parse_args()


def build_oci_bundle(container_name, runc_base, app_config_container_path):
    logger.info("Building OCI bundle '{}'".format(container_name))
    remove_oci_image_in_working_dir()
    remove_oci_bundle_in_runc_dir(runc_base, container_name)
    generate_oci_bundle(container_name)
    modify_oci_bundle_config(container_name, AppMode.SERVER,
                             app_config_container_path, vlog_level=3)
    move_oci_bundle_to_runc_dir(runc_base, container_name)


def set_configuration_file(runc_base, container_name,
                           app_config_container_path):
    config_path = "./base_configs/experiment3_server.json"
    with open(config_path, "r") as config_file:
        config = json.load(config_file)

    app_config_path = runc_base + container_name + "/rootfs" + \
                      app_config_container_path
    with open(app_config_path, "w") as app_config_file:
        json.dump(config, app_config_file, indent=4)


def wait_for_server_termination(container_name):
    logger.info("Waiting for server termination")
    cmd = "sudo runc list -f json"
    while True:
        cmd_output = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    shell=True).stdout.decode()
        if cmd_output == "null":
            logger.info("Server terminated")
            break

        container_list = json.loads(cmd_output)
        server = next((container for container in container_list if
                       container["id"] == container_name), None)

        if server is None or server["status"] == "stopped":
            logger.info("Server terminated")
            break

        time.sleep(1)


def parse_migration_notification_time_dump(runc_base, container_name,
                                           app_migration_notification_time_dump_container_path):
    app_dump_path = runc_base + container_name + "/rootfs" + \
                    app_migration_notification_time_dump_container_path
    try:
        with open(app_dump_path, "r") as app_migration_notification_time_file:
            return json.load(app_migration_notification_time_file)
    except:
        logger.error("Cannot parse the migration notification time output file")
        return None


def save_migration_notification_time(total_migration_notification_times,
                                     n_client, protocol, repetition,
                                     migration_notification_time):
    if migration_notification_time is None:
        return

    total_migration_notification_times["experiment"].append(3)
    total_migration_notification_times["numberOfClients"].append(n_client)
    total_migration_notification_times["protocol"].append(protocol)
    total_migration_notification_times["run"].append(repetition)
    total_migration_notification_times["migrationNotificationTime [us]"] \
        .append(migration_notification_time["migrationNotificationTime"])


def dump_migration_notification_times(total_migration_notification_times):
    file_name = "experiment3_migration_notification_times.csv"
    df = pd.DataFrame(total_migration_notification_times)
    df.to_csv(file_name, encoding="utf-8", index=False)


def main():
    container_name = "mhq-server"
    runc_base = "/runc/containers/"
    app_config_container_path = "/usr/src/app/proxygen/config.json"
    console_socket_file = runc_base + container_name + "/console.sock"
    app_migration_notification_time_dump_container_path = \
        "/usr/src/app/proxygen/migration_notification_time.json"

    args = parse_arguments()
    if args.rebuild_image or not os.path.isdir(runc_base + container_name):
        build_oci_bundle(container_name, runc_base, app_config_container_path)

    # Update the configuration file used by the application.
    set_configuration_file(runc_base, container_name, app_config_container_path)

    # NOTE: the seed is never changed across the different runs,
    # because its value is irrelevant for the measurements taken.
    n_clients = [1, 10, 20, 30, 50]
    protocols = ["reactiveExplicit", "symmetric"]
    n_repetitions = args.repetitions
    total_migration_notification_times = {"experiment": [], "run": [],
                                          "numberOfClients": [], "protocol": [],
                                          "migrationNotificationTime [us]": []}

    for protocol in protocols:
        for n_client in n_clients:
            for repetition in range(1, n_repetitions + 1):
                logger.info("New experiment run involving {} protocol and "
                            "{} clients. Repetition: {}"
                            .format(protocol, n_client, repetition))

                # Start the server container.
                console_socket_proc = start_console_socket(console_socket_file,
                                                           suppress_output=False)
                start_container(runc_base, container_name, container_name,
                                console_socket_file,
                                detached=True)

                # Handler used to stop the console socket and
                # the container if a failure occurs.
                atexit.unregister(exit_handler)
                atexit.register(exit_handler, console_socket_proc,
                                console_socket_file, container_name)

                # Wait until the end of the experiment,
                # namely until the server container stops.
                wait_for_server_termination(container_name)

                # Save migration notification time recorded by the server.
                migration_notification_time = \
                    parse_migration_notification_time_dump(runc_base,
                                                           container_name,
                                                           app_migration_notification_time_dump_container_path)
                save_migration_notification_time(
                    total_migration_notification_times,
                    n_client, protocol, repetition,
                    migration_notification_time)

                # Force console socket and container to stop
                # at the end of the run.
                logger.info("End of an experiment run: stopping console socket "
                            "and container, if still up")
                stop_container_and_console_socket(console_socket_proc,
                                                  console_socket_file,
                                                  container_name)

                # Sleep before starting a new run.
                logger.info("Sleeping for 5 seconds before the next run")
                time.sleep(5)

    logger.info("Ending the experiment")
    dump_migration_notification_times(total_migration_notification_times)


if __name__ == "__main__":
    main()

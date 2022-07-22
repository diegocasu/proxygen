import atexit
import argparse

from utils.oci import *

logger = logging.getLogger("client")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def exit_handler(container_names, console_socket_files,
                 console_socket_processes):
    stop_all_containers_and_console_sockets(container_names,
                                            console_socket_files,
                                            console_socket_processes)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild_image",
                        dest="rebuild_image", action="store_true",
                        default=False)
    parser.add_argument("--repetitions", dest="repetitions", action="store",
                        required=True, type=int)
    return parser.parse_args()


def build_oci_bundle(container_base_name, runc_base, app_config_container_path):
    logger.info("Building OCI bundle '{}'".format(container_base_name))
    remove_oci_image_in_working_dir()
    remove_oci_bundle_in_runc_dir(runc_base, container_base_name)
    generate_oci_bundle(container_base_name)
    modify_oci_bundle_config(container_base_name, AppMode.CLIENT,
                             app_config_container_path, vlog_level=3)
    move_oci_bundle_to_runc_dir(runc_base, container_base_name)


def update_configuration_file(runc_base, container_base_name,
                              app_config_container_path,
                              last_client=False,
                              protocol=None):
    config_path = "./base_configs/experiment3_client.json"
    with open(config_path, "r") as config_file:
        config = json.load(config_file)

        if last_client is True:
            config["experiment"]["serverMigrationProtocol"] = protocol

            # A value of "notifyImminentMigrationAfterRequest" different from 0
            # tells to the application that it must send a notification about
            # an imminent migration to the server.
            config["experiment"]["notifyImminentMigrationAfterRequest"] = 2

            # The last client is the one that stops first, and also the one
            # that sends the shutdown command to the server. The other clients
            # will be killed after the last client stops.
            config["experiment"]["shutdownAfterRequest"] = 3

            logger.info("Configuration file for the last client:\n{}"
                        .format(json.dumps(config, indent=4)))
        else:
            logger.info("Configuration file for the first clients:\n{}"
                        .format(json.dumps(config, indent=4)))

    app_config_path = runc_base + container_base_name + "/rootfs" + \
                      app_config_container_path
    with open(app_config_path, "w") as app_config_file:
        json.dump(config, app_config_file, indent=4)


def start_all_containers(runc_base, container_base_name,
                         app_config_container_path, container_names,
                         console_socket_files, protocol):
    console_socket_processes = []
    update_configuration_file(runc_base, container_base_name,
                              app_config_container_path,
                              last_client=False)
    for i in range(0, len(container_names)):
        if i == len(container_names) - 1:
            # Wait a bit so that the previous containers can load
            # the configuration before it is changed for the last client.
            time.sleep(3)
            update_configuration_file(runc_base, container_base_name,
                                      app_config_container_path,
                                      last_client=True, protocol=protocol)

        console_socket_processes.append(
            start_console_socket(console_socket_files[i],
                                 suppress_output=False))
        start_container(runc_base, container_base_name, container_names[i],
                        console_socket_files[i],
                        detached=True)

    return console_socket_processes


def stop_all_containers_and_console_sockets(container_names,
                                            console_socket_files,
                                            console_socket_processes):
    for i in range(0, len(container_names)):
        cmd = "sudo runc kill {} KILL".format(container_names[i])
        while True:
            # Repeatedly try to kill the container until the command succeeds.
            logger.info("Running '{}'".format(cmd))
            os.system(cmd)
            runc_list_cmd = "sudo runc list -f json"
            runc_list_cmd_output = subprocess.run(runc_list_cmd,
                                                  stdout=subprocess.PIPE,
                                                  shell=True).stdout.decode()
            if runc_list_cmd_output == "null":
                break
            container_list = json.loads(runc_list_cmd_output)
            client = next((container for container in container_list if
                           container["id"] == container_names[i]), None)
            if client is None or client["status"] == "stopped":
                break
            time.sleep(0.2)

        cmd = "sudo runc delete " + container_names[i]
        logger.info("Running '{}'".format(cmd))
        os.system(cmd)

        stop_console_socket(console_socket_processes[i],
                            console_socket_files[i])


def wait_for_last_client_termination(container_names):
    logger.info("Waiting for last client termination")
    cmd = "sudo runc list -f json"
    while True:
        cmd_output = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    shell=True).stdout.decode()
        if cmd_output == "null":
            logger.info("All the clients terminated")
            break

        container_list = json.loads(cmd_output)
        client = next((container for container in container_list if
                       container["id"] == container_names[-1]), None)

        if client is None or client["status"] == "stopped":
            logger.info("Last client terminated")
            break

        time.sleep(5)


def main():
    args = parse_arguments()
    container_base_name = "mhq-client"
    runc_base = "/runc/containers/"
    app_config_container_path = "/usr/src/app/proxygen/config.json"

    if args.rebuild_image or not os.path.isdir(runc_base + container_base_name):
        build_oci_bundle(container_base_name, runc_base,
                         app_config_container_path)

    # NOTE: the seed is never changed across the different runs,
    # because its value is irrelevant for the measurements taken.
    n_clients = [1, 10, 20, 30, 50]
    protocols = ["reactiveExplicit", "symmetric"]
    n_repetitions = args.repetitions

    for protocol in protocols:
        for n_client in n_clients:
            for repetition in range(1, n_repetitions + 1):
                logger.info("New experiment run involving {} protocol and"
                            " {} clients. Repetition: {}"
                            .format(protocol, n_client, repetition))

                container_names = [container_base_name + str(i) for i in
                                   range(1, n_client + 1)]
                console_socket_files = [runc_base + container_base_name +
                                        "/console{}.sock".format(i)
                                        for i in range(1, n_client + 1)]

                # Start all the client containers in detached mode.
                console_socket_processes = start_all_containers(runc_base,
                                                                container_base_name,
                                                                app_config_container_path,
                                                                container_names,
                                                                console_socket_files,
                                                                protocol)

                # Handler used to stop the console sockets and
                # the containers if a failure occurs.
                atexit.unregister(exit_handler)
                atexit.register(exit_handler, container_names,
                                console_socket_files,
                                console_socket_processes)

                # Wait until the end of the experiment, namely
                # until the last client container stops.
                wait_for_last_client_termination(container_names)

                # Force console sockets and containers
                # to stop at the end of the run.
                logger.info("End of an experiment run: stopping console "
                            "sockets and containers, if still up")
                stop_all_containers_and_console_sockets(container_names,
                                                        console_socket_files,
                                                        console_socket_processes)

                # Sleep before starting a new run.
                logger.info("Sleeping for 10 seconds before the next run")
                time.sleep(10)

    logger.info("Ending the experiment")


if __name__ == "__main__":
    main()

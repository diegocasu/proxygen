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
                 container_name, results):
    stop_container_and_console_socket(console_socket_proc, console_socket_file,
                                      container_name)
    dump_experiment_results_to_file(results, call_from_exit_handler=True)


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
    parser.add_argument("--rebuild_image", dest="rebuild_image",
                        action="store_true", default=False)
    parser.add_argument("--repetitions", dest="repetitions", action="store",
                        type=int, required=True)
    return parser.parse_args()


def build_oci_bundle(container_name, runc_base, app_config_container_path):
    logger.info("Building OCI bundle '{}'".format(container_name))
    remove_oci_image_in_working_dir()
    remove_oci_bundle_in_working_dir(container_name)
    remove_oci_bundle_in_runc_dir(runc_base, container_name)
    generate_oci_bundle(container_name)
    modify_oci_bundle_config(container_name, AppMode.SERVER,
                             app_config_container_path, vlog_level=3)


def load_base_configuration():
    with open("./baseconfigs/experiment6_server.json", "r") as config_file:
        return json.load(config_file)


def update_configuration_file(runc_base, container_name,
                              app_config_container_path, new_config):
    app_config_path = runc_base + container_name + "/rootfs" + \
                      app_config_container_path
    with open(app_config_path, "w") as app_config_file:
        json.dump(new_config, app_config_file, indent=4)


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


def save_results(results, run, repetition, seed):
    results["experiment"].append(6)
    results["run"].append(run)
    results["repetition"].append(repetition)
    results["seed"].append(seed)


def dump_experiment_results_to_file(results, call_from_exit_handler=False):
    df = pd.DataFrame(results)
    if call_from_exit_handler is True:
        results_file = "experiment6_server.bak.csv"
    else:
        results_file = "experiment6_server.csv"
    df.to_csv(results_file, encoding="utf-8", index=False)


def main():
    container_name = "mhq-server"
    runc_base = "/runc/containers/"
    app_config_container_path = "/usr/src/app/proxygen/config.json"
    console_socket_file = runc_base + container_name + "/console.sock"

    args = parse_arguments()
    if args.rebuild_image or not os.path.isdir(container_name):
        build_oci_bundle(container_name, runc_base, app_config_container_path)

    results = {"experiment": [], "run": [], "repetition": [], "seed": []}
    run = 0
    seed = 0
    migration_frequency_list = [10, 30]  # Minutes
    config = load_base_configuration()

    for migration_frequency in migration_frequency_list:
        run += 1

        for i in range(1, args.repetitions + 1):
            # Copy a fresh version of the OCI bundle to the runC base directory.
            remove_oci_bundle_in_runc_dir(runc_base, container_name)
            copy_oci_bundle_to_runc_dir(runc_base, container_name)

            seed += 1
            config["seed"] = seed

            if args.first_role == "source":
                logger.info("New experiment run with configuration\n{}"
                            .format(json.dumps(config, indent=4)))

            update_configuration_file(
                runc_base, container_name, app_config_container_path, config)

            # Start server container.
            console_socket_proc = start_console_socket(
                console_socket_file, suppress_output=False)
            start_container(runc_base, container_name, detached=True,
                            console_socket_file=console_socket_file)

            # Handler used to stop the console socket and
            # the container if a failure occurs.
            atexit.unregister(exit_handler)
            atexit.register(exit_handler, console_socket_proc,
                            console_socket_file, container_name, results)

            wait_for_server_termination(container_name)

            # Force console socket and container to stop at the end of the run.
            logger.info("End of an experiment run: stopping console socket "
                        "and container, if still up")
            stop_container_and_console_socket(
                console_socket_proc, console_socket_file, container_name)

            # Save results.
            save_results(results, run, i, config["seed"])

            # Sleep before starting a new run.
            logger.info("Sleeping for 5 seconds before the next run")
            time.sleep(5)

    logger.info("Ending the experiment")
    dump_experiment_results_to_file(results, args.first_role)


if __name__ == "__main__":
    main()

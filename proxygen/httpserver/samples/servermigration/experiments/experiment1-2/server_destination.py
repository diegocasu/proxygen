import argparse
import atexit
import socket
import pandas as pd

from utils.oci import *
from utils.migrate_server_destination import wait_for_server_migration
from utils.client_experiment import ClientExperimentManager

logger = logging.getLogger("server_destination")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def exit_handler(command_socket, console_socket_proc, console_socket_file,
                 container_name, total_restore_times, experiment):
    stop_container_and_console_socket(console_socket_proc, console_socket_file,
                                      container_name)
    command_socket.close()
    dump_restore_times(total_restore_times, experiment,
                       call_from_exit_handler=True)


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
    parser.add_argument("--management_ip", dest="management_ip",
                        action="store", type=str, required=True)
    parser.add_argument("--management_port", dest="management_port",
                        action="store", type=int, required=True)
    parser.add_argument("--experiment", dest="experiment", action="store",
                        required=True, type=int, choices=range(1, 3))
    parser.add_argument("--repetitions", dest="repetitions", action="store",
                        required=True, type=int)
    return parser.parse_args()


def build_oci_bundle(container_name, runc_base):
    logger.info("Building OCI bundle '{}'".format(container_name))
    remove_oci_image_in_working_dir()
    remove_oci_bundle_in_working_dir(container_name)
    remove_oci_bundle_in_runc_dir(runc_base, container_name)
    generate_oci_bundle(container_name)


def create_migration_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("", 18863))
        sock.listen()
        logger.info("Migration server listening on {}:{}"
                    .format(*sock.getsockname()))
        return sock
    except socket.error as msg:
        logger.error("Bind failed. Error: {}".format(msg))
        sock.close()
        sys.exit(1)


def create_command_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("", 19999))
        logger.info("Command server listening on {}:{}"
                    .format(*sock.getsockname()))
        return sock
    except socket.error as msg:
        logger.error("Bind failed. Error: {}".format(msg))
        sock.close()
        sys.exit(1)


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


def save_restore_times(total_restore_times, restore_times, experiment_manager):
    total_restore_times["experiment"].append(experiment_manager._id)
    total_restore_times["run"].append(experiment_manager._current_run)
    total_restore_times["repetition"].append(
        experiment_manager._current_repetition)
    total_restore_times["restoreTime [s]"] \
        .append(restore_times.get("restoreTime", None))
    total_restore_times["lazyPagesTxTime [s]"] \
        .append(restore_times.get("lazyPagesTxTime", None))
    total_restore_times["lazyPagesTxEndTime [s]"] \
        .append(restore_times.get("lazyPagesTxEndTime", None))
    total_restore_times["numberOfLazyPages"] \
        .append(restore_times.get("numberOfLazyPages", None))


def dump_restore_times(total_restore_times, experiment,
                       call_from_exit_handler=False):
    if call_from_exit_handler is True:
        file_name = "experiment{}_restore_times.bak.csv".format(experiment)
    else:
        file_name = "experiment{}_restore_times.csv".format(experiment)
    df = pd.DataFrame(total_restore_times)
    df.to_csv(file_name, encoding="utf-8", index=False)


def main():
    container_name = "mhq-server"
    runc_base = "/runc/containers/"
    console_socket_file = runc_base + container_name + "/console.sock"

    args = parse_arguments()
    if args.rebuild_image or not os.path.isdir(container_name):
        build_oci_bundle(container_name, runc_base)

    # Create socket used to receive notifications
    # about the end of an experiment.
    command_socket = create_command_socket()

    # Create socket used to perform the server migration.
    migration_socket = create_migration_socket()

    # Create dictionary storing the measurements.
    # Information regarding the protocol, migration technique, etc. will be
    # obtained merging the data with the results obtained on the other nodes.
    total_restore_times = {"experiment": [], "run": [], "repetition": [],
                           "restoreTime [s]": [], "numberOfLazyPages": [],
                           "lazyPagesTxTime [s]": [],
                           "lazyPagesTxEndTime [s]": []}

    # An experiment manager is not strictly needed here, since configuration
    # files are not needed when being the destination node of a migration.
    # However, using the client experiment manager allows to detect the end of
    # the experiment in isolation, which happens when no more configurations
    # can be crafted. Moreover, it is useful to record the run and repetition
    # numbers in the results file.
    experiment_manager = ClientExperimentManager(args.experiment,
                                                 args.repetitions)

    while True:
        # Copy a fresh version of the OCI bundle to the runC base directory.
        # Given that rsync transfers files in an incremental way, this is useful
        # to avoid that migration times are dependent on previous migrations.
        remove_oci_bundle_in_runc_dir(runc_base, container_name)
        copy_oci_bundle_to_runc_dir(runc_base, container_name)

        # Create a configuration like the client does, and check if
        # the experiment has ended. The configuration is never used.
        if experiment_manager.get_new_config() is None:
            logger.info("Ending the experiment")
            break
        logger.info("New experiment run")

        # Start the console socket.
        console_socket_proc = start_console_socket(console_socket_file,
                                                   suppress_output=False)

        # Handler used to stop the console socket and
        # the container if a failure occurs.
        atexit.unregister(exit_handler)
        atexit.register(exit_handler, command_socket, console_socket_proc,
                        console_socket_file, container_name,
                        total_restore_times, args.experiment)

        # Wait for a server migration and handle it. If the latter is replaced
        # by a shutdown command, skip the execution to the next cycle.
        restore_times = wait_for_server_migration(
            migration_socket, command_socket,
            args.management_ip, args.management_port)

        if not restore_times:
            # Save empty measurements and sleep before starting a new run.
            save_restore_times(total_restore_times, restore_times,
                               experiment_manager)
            stop_container_and_console_socket(console_socket_proc,
                                              console_socket_file,
                                              container_name)
            logger.info("Run interrupted due to an application error")
            logger.info("Sleeping for 5 seconds before the next run")
            time.sleep(5)
            continue

        # Save restore times.
        save_restore_times(total_restore_times, restore_times,
                           experiment_manager)

        # Wait until the end of the experiment,
        # namely until the server container stops.
        wait_for_server_termination(container_name)

        # Force console socket and container to stop at the end of the run.
        logger.info("End of an experiment run: stopping console socket "
                    "and container, if still up")
        stop_container_and_console_socket(console_socket_proc,
                                          console_socket_file,
                                          container_name)

        # Sleep before starting a new run.
        logger.info("Sleeping for 5 seconds before the next run")
        time.sleep(5)

    dump_restore_times(total_restore_times, args.experiment)


if __name__ == "__main__":
    main()

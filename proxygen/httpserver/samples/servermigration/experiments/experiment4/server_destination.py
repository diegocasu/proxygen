import argparse
import atexit
import socket
import pandas as pd

from utils.oci import *
from utils.migrate_server_destination import wait_for_server_migration
from utils.configuration import *

logger = logging.getLogger("server_destination")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def exit_handler(command_socket, console_socket_proc, console_socket_file,
                 container_name, total_restore_times):
    stop_container_and_console_socket(console_socket_proc, console_socket_file,
                                      container_name)
    command_socket.close()
    dump_restore_times(total_restore_times, call_from_exit_handler=True)


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


def save_restore_times(total_restore_times, restore_times, run, n_clients):
    for i in range(0, n_clients):
        total_restore_times["experiment"].append(4)
        total_restore_times["run"].append(run)
        total_restore_times["restoreTime [s]"] \
            .append(restore_times.get("restoreTime", None))
        total_restore_times["lazyPagesTxTime [s]"] \
            .append(restore_times.get("lazyPagesTxTime", None))
        total_restore_times["lazyPagesTxEndTime [s]"] \
            .append(restore_times.get("lazyPagesTxEndTime", None))
        total_restore_times["numberOfLazyPages"] \
            .append(restore_times.get("numberOfLazyPages", None))


def dump_restore_times(total_restore_times, call_from_exit_handler=False):
    if call_from_exit_handler is True:
        file_name = "experiment4_restore_times.bak.csv"
    else:
        file_name = "experiment4_restore_times.csv"
    df = pd.DataFrame(total_restore_times)
    df.to_csv(file_name, encoding="utf-8", index=False)


def main():
    container_name = "mhq-server"
    runc_base = "/runc/containers/"
    console_socket_file = runc_base + container_name + "/console.sock"

    args = parse_arguments()
    if args.rebuild_image or not os.path.isdir(container_name):
        build_oci_bundle(container_name, runc_base)

    # Create socket used to send onNetworkSwitch commands.
    command_socket = create_command_socket()

    # Create socket used to perform the server migration.
    migration_socket = create_migration_socket()

    total_restore_times = {"experiment": [], "run": [], "restoreTime [s]": [],
                           "numberOfLazyPages": [], "lazyPagesTxTime [s]": [],
                           "lazyPagesTxEndTime [s]": []}

    # Generate all the possible combinations used in the experiment
    # to synchronize this script with the others.
    combination_list = generate_experiment_combinations()
    run = 1
    n_clients = 30

    for _ in combination_list:
        # Copy a fresh version of the OCI bundle to the runC base directory.
        # Given that rsync transfers files in an incremental way, this is useful
        # to avoid that migration times are dependent on previous migrations.
        remove_oci_bundle_in_runc_dir(runc_base, container_name)
        copy_oci_bundle_to_runc_dir(runc_base, container_name)

        logger.info("New experiment run")

        # Start the console socket.
        console_socket_proc = start_console_socket(console_socket_file,
                                                   suppress_output=False)

        # Handler used to stop the console socket and
        # the container if a failure occurs.
        atexit.unregister(exit_handler)
        atexit.register(exit_handler, command_socket, console_socket_proc,
                        console_socket_file, container_name,
                        total_restore_times)

        # Wait for a server migration and handle it.
        restore_times = wait_for_server_migration(
            migration_socket, command_socket,
            args.management_ip, args.management_port)

        # Save restore times.
        save_restore_times(total_restore_times, restore_times, run, n_clients)

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
        run += 1

    dump_restore_times(total_restore_times)


if __name__ == "__main__":
    main()

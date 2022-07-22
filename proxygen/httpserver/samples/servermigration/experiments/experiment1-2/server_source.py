import argparse
import atexit
import socket

from utils.oci import *
from utils.server_experiment import ServerExperimentManager
from utils.migrate_server_source import start_migration

logger = logging.getLogger("server_source")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def exit_handler(command_socket, console_socket_proc, console_socket_file,
                 container_name, experiment_manager):
    stop_container_and_console_socket(console_socket_proc, console_socket_file,
                                      container_name)
    command_socket.close()
    experiment_manager \
        .dump_experiment_results_to_file(call_from_exit_handler=True)


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
    parser.add_argument("--experiment", dest="experiment", action="store",
                        required=True, type=int, choices=range(1, 3))
    parser.add_argument("--destination_ip", dest="destination_ip",
                        action="store", required=True, type=str)
    parser.add_argument("--repetitions", dest="repetitions", action="store",
                        required=True, type=int)

    compression_parser = parser.add_mutually_exclusive_group(required=True)
    compression_parser.add_argument("--enable_rsync_compression",
                                    dest="enable_compression",
                                    action="store_true")
    compression_parser.add_argument("--disable_rsync_compression",
                                    dest="enable_compression",
                                    action="store_false")
    return parser.parse_args()


def build_oci_bundle(container_name, runc_base, app_config_container_path):
    logger.info("Building OCI bundle '{}'".format(container_name))
    remove_oci_image_in_working_dir()
    remove_oci_bundle_in_working_dir(container_name)
    remove_oci_bundle_in_runc_dir(runc_base, container_name)
    generate_oci_bundle(container_name)
    modify_oci_bundle_config(container_name, AppMode.SERVER,
                             app_config_container_path, vlog_level=3)


def update_configuration_file(runc_base, container_name,
                              app_config_container_path, new_config):
    app_config_path = runc_base + container_name + "/rootfs" + \
                      app_config_container_path
    with open(app_config_path, "w") as app_config_file:
        json.dump(new_config, app_config_file, indent=4)


def create_command_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("", 19888))
        logger.info("Command server listening on {}:{}"
                    .format(*sock.getsockname()))
        return sock
    except socket.error as msg:
        logger.error("Bind failed. Error: {}".format(msg))
        sock.close()
        sys.exit(1)


def wait_for_migration_command(command_socket, destination_ip):
    logger.info("Waiting for the migration command")
    while True:
        message, address = command_socket.recvfrom(1024)
        message = message.decode()
        logger.info("Received message '{}' from {}:{}"
                    .format(message, *address))

        if message == "migrate":
            logger.info("Sending response: OK")
            response = "OK"
            command_socket.sendto(response.encode(), address)
            return True

        try:
            command = json.loads(message)
            if command["action"] == "shutdown":
                logger.info("Sending response: OK")
                response = "OK"
                command_socket.sendto(response.encode(), address)

                # Forward the shutdown command to the migration
                # server running on destination.
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((destination_ip, 18863))
                sock.send(message.encode())
                return False
        except:
            pass
        logger.info("Ignoring message")


def wait_for_end_command(command_socket):
    logger.info("Waiting for the end of the experiment")
    while True:
        message, address = command_socket.recvfrom(1024)
        message = message.decode()
        logger.info("Received message '{}' from {}:{}"
                    .format(message, *address))

        try:
            command = json.loads(message)
            if command["action"] == "shutdown":
                logger.info("Sending response: OK")
                response = "OK"
                command_socket.sendto(response.encode(), address)
                return
        except:
            pass
        logger.info("Ignoring message")


def main():
    container_name = "mhq-server"
    runc_base = "/runc/containers/"
    app_config_container_path = "/usr/src/app/proxygen/config.json"
    console_socket_file = runc_base + container_name + "/console.sock"

    args = parse_arguments()
    experiment_manager = ServerExperimentManager(args.experiment,
                                                 args.destination_ip,
                                                 args.repetitions)
    if args.rebuild_image or not os.path.isdir(container_name):
        build_oci_bundle(container_name, runc_base, app_config_container_path)

    # Create socket used to receive migration commands
    command_socket = create_command_socket()

    while True:
        # Copy a fresh version of the OCI bundle to the runC base directory.
        # Given that rsync transfers files in an incremental way, this is useful
        # to avoid that migration times are dependent on previous migrations.
        remove_oci_bundle_in_runc_dir(runc_base, container_name)
        copy_oci_bundle_to_runc_dir(runc_base, container_name)

        new_config, new_migration_technique = experiment_manager.get_new_config()
        if new_config is None or new_migration_technique is None:
            logger.info("Ending the experiment")
            break

        logger.info("New experiment run with migration technique {} "
                    "and configuration\n{}"
                    .format(str(new_migration_technique),
                            json.dumps(new_config, indent=4)))

        # Update the configuration file used by the application.
        update_configuration_file(runc_base, container_name,
                                  app_config_container_path, new_config)

        # Start the server container.
        console_socket_proc = start_console_socket(console_socket_file,
                                                   suppress_output=False)
        start_container(runc_base, container_name, console_socket_file,
                        detached=True)

        # Handler used to stop the console socket and
        # the container if a failure occurs.
        atexit.unregister(exit_handler)
        atexit.register(exit_handler, command_socket, console_socket_proc,
                        console_socket_file, container_name, experiment_manager)

        # Wait for migration command. If the latter is replaced by
        # a shutdown command, skip the execution to the next cycle.
        migrate = wait_for_migration_command(command_socket,
                                             args.destination_ip)
        if migrate is False:
            # Save empty measurements and sleep before starting a new run.
            experiment_manager \
                .save_migration_measurements({}, args.enable_compression)
            stop_container_and_console_socket(console_socket_proc,
                                              console_socket_file,
                                              container_name)
            logger.info("Run interrupted due to an application error")
            logger.info("Sleeping for 5 seconds before the next run")
            time.sleep(5)
            continue

        # Start migration.
        migration_measurements = start_migration(runc_base,
                                                 container_name,
                                                 args.destination_ip,
                                                 new_migration_technique.pre,
                                                 new_migration_technique.lazy,
                                                 args.enable_compression)
        experiment_manager.save_migration_measurements(migration_measurements,
                                                       args.enable_compression)

        # Wait for a message notifying the end of the experiment.
        wait_for_end_command(command_socket)

        # Force console socket and container to stop at the end of the run.
        # If a migration was successful, this step actually does nothing.
        logger.info("End of an experiment run: stopping console socket "
                    "and container, if still up")
        stop_container_and_console_socket(console_socket_proc,
                                          console_socket_file,
                                          container_name)

        # Sleep before starting a new run.
        logger.info("Sleeping for 5 seconds before the next run")
        time.sleep(5)

    experiment_manager.dump_experiment_results_to_file()


if __name__ == "__main__":
    main()

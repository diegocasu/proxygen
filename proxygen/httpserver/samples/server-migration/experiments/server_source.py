import argparse
import atexit
import socket

from utils.oci import *
from utils.server_experiment import ServerExperimentManager
from utils.migrate_server_source import start_migration


def exit_handler(command_socket, console_socket_proc, console_socket_file,
                 container_name):
    stop_container_and_console_socket(console_socket_proc, console_socket_file,
                                      container_name)
    command_socket.close()


def stop_container_and_console_socket(console_socket_proc, console_socket_file,
                                      container_name):
    # Possibly stop the container and the console socket.
    cmd = "sudo runc kill {} KILL".format(container_name)
    print("Running '{}'".format(cmd))
    os.system(cmd)

    cmd = "sudo runc delete " + container_name
    print("Running '{}'".format(cmd))
    os.system(cmd)

    stop_console_socket(console_socket_proc, console_socket_file)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild_image",
                        dest="rebuild_image", action="store_true",
                        default=False)
    parser.add_argument("--experiment", dest="experiment", action="store",
                        required=True, type=int, choices=range(1, 5))
    parser.add_argument("--destination_ip", dest="destination_ip",
                        action="store", required=True, type=str)
    return parser.parse_args()


def build_oci_bundle(container_name, runc_base, app_config_container_path):
    print("Building OCI bundle '{}'".format(container_name))
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
        print("Command server listening on {}:{}".format(*sock.getsockname()))
        return sock
    except socket.error as msg:
        print("Bind failed. Error:", msg)
        sock.close()
        sys.exit(1)


def wait_for_migration_command(command_socket):
    print("Waiting for the migration command")
    while True:
        message, address = command_socket.recvfrom(1024)
        message = message.decode()
        print("Received message '{}' from {}:{}".format(message, *address))

        if message == "migrate":
            print("Sending response: OK")
            response = "OK"
            command_socket.sendto(response.encode(), address)
            return

        print("Ignoring message")


def wait_for_end_command(command_socket):
    print("Waiting for the end of the experiment")
    while True:
        message, address = command_socket.recvfrom(1024)
        message = message.decode()
        print("Received message '{}' from {}:{}".format(message, *address))

        try:
            command = json.loads(message)
            if command["action"] == "shutdown":
                print("Sending response: OK")
                response = "OK"
                command_socket.sendto(response.encode(), address)
                return
        except:
            pass
        print("Ignoring message")


def main():
    container_name = "mhq-server"
    runc_base = "/runc/containers/"
    app_config_container_path = "/usr/src/app/proxygen/config.json"
    console_socket_file = runc_base + container_name + "/console.sock"

    args = parse_arguments()
    experiment_manager = ServerExperimentManager(args.experiment,
                                                 args.destination_ip)
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
            print("Ending the experiment")
            break

        print("New experiment run with migration technique",
              str(new_migration_technique), "and configuration")
        print(json.dumps(new_config, indent=4))

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
                        console_socket_file, container_name)

        # Wait for migration command.
        wait_for_migration_command(command_socket)

        # Start migration.
        migration_measurements = start_migration(runc_base,
                                                 container_name,
                                                 args.destination_ip,
                                                 new_migration_technique.pre,
                                                 new_migration_technique.lazy,
                                                 enable_compression=True)
        experiment_manager.save_migration_measurements(migration_measurements)

        # Wait for a message notifying the end of the experiment.
        wait_for_end_command(command_socket)

        # Force console socket and container to stop at the end of the run.
        # If a migration was successful, this step actually does nothing.
        print("End of an experiment run: stopping console socket "
              "and container, if still up")
        stop_container_and_console_socket(console_socket_proc,
                                          console_socket_file,
                                          container_name)

        # Sleep before starting a new run.
        print("Sleeping for 5 seconds before the next run")
        time.sleep(5)

    experiment_manager.dump_experiment_results_to_file()


if __name__ == "__main__":
    main()

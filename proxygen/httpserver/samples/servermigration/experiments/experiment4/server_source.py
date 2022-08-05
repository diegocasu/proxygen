import argparse
import atexit
import socket
import pandas as pd

from utils.oci import *
from utils.configuration import *
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
                 container_name, results):
    stop_container_and_console_socket(console_socket_proc, console_socket_file,
                                      container_name)
    command_socket.close()
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
    parser.add_argument("--rebuild_image",
                        dest="rebuild_image", action="store_true",
                        default=False)
    parser.add_argument("--destination_ip", dest="destination_ip",
                        action="store", required=True, type=str)
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


def generate_all_configs():
    combination_list = generate_experiment_combinations()
    config_path = "./baseconfigs/experiment4_server_source.json"
    config_list = []
    migration_technique_list = []
    seed = 0

    for combination in combination_list:
        seed += 1
        with open(config_path, "r") as config_file:
            config = json.load(config_file)
            config["seed"] = seed

            # Enable only the migration protocol required by the run.
            quic_protocol = combination[1]
            if "Explicit" in quic_protocol:
                quic_protocol = "explicit"

            migration_protocols = config["serverMigration"]
            for protocol in migration_protocols:
                if protocol == "enable" or protocol == "addressPool":
                    continue
                if protocol == quic_protocol:
                    migration_protocols[protocol] = True
                else:
                    migration_protocols[protocol] = False

            # Adjust memory inflation.
            inflation = combination[0]
            config["memoryFootprintInflation"]["additionalBytes"] = \
                inflation * 1024 * 1024

            config_list.append(config)
            migration_technique_list.append(combination[2])

    return config_list, migration_technique_list


def update_configuration_file(runc_base, container_name,
                              app_config_container_path, new_config):
    app_config_path = runc_base + container_name + "/rootfs" + \
                      app_config_container_path
    with open(app_config_path, "w") as app_config_file:
        json.dump(new_config, app_config_file, indent=4)


def wait_for_migration_command(command_socket):
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
            return

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


def save_migration_measurements(results, run, n_clients, config,
                                migration_technique, migration_times,
                                compression_enabled):
    seed = config["seed"]
    inflation = config["memoryFootprintInflation"]["additionalBytes"] / (
            1024 * 1024)

    for i in range(0, n_clients):
        results["experiment"].append(4)
        results["run"].append(run)
        results["seedServer"].append(seed)
        results["migrationTechnique"] \
            .append(migration_technique.to_camel_case_string())
        results["memoryFootprintInflation [MB]"].append(inflation)
        results["compressionEnabled"].append(compression_enabled)
        results["preDumpTime [s]"] \
            .append(migration_times.get("preDumpTime", None))
        results["preDumpTxTime [s]"] \
            .append(migration_times.get("preDumpTxTime", None))
        results["dumpTime [s]"] \
            .append(migration_times.get("dumpTime", None))
        results["dumpTxTime [s]"] \
            .append(migration_times.get("dumpTxTime", None))
        results["dumpSize"] \
            .append(migration_times.get("dumpSize", None))
        results["preDumpSize"] \
            .append(migration_times.get("preDumpSize", None))
        results["rsyncPreDumpTotalFileSize"] \
            .append(migration_times.get("rsyncPreDumpTotalFileSize", None))
        results["rsyncPreDumpTotalBytesSent"] \
            .append(migration_times.get("rsyncPreDumpTotalBytesSent", None))
        results["rsyncPreDumpTransferRate"] \
            .append(migration_times.get("rsyncPreDumpTransferRate", None))
        results["rsyncPreDumpCompressionSpeedup"] \
            .append(migration_times.get("rsyncPreDumpCompressionSpeedup", None))
        results["rsyncDumpTotalFileSize"] \
            .append(migration_times.get("rsyncDumpTotalFileSize", None))
        results["rsyncDumpTotalBytesSent"] \
            .append(migration_times.get("rsyncDumpTotalBytesSent", None))
        results["rsyncDumpTransferRate"] \
            .append(migration_times.get("rsyncDumpTransferRate", None))
        results["rsyncDumpCompressionSpeedup"] \
            .append(migration_times.get("rsyncDumpCompressionSpeedup", None))


def dump_experiment_results_to_file(results, call_from_exit_handler=False):
    df = pd.DataFrame(results)
    if call_from_exit_handler is True:
        results_file = "experiment4_migration_times.bak.csv"
    else:
        results_file = "experiment4_migration_times.csv"
    df.to_csv(results_file, encoding="utf-8", index=False)


def main():
    container_name = "mhq-server"
    runc_base = "/runc/containers/"
    app_config_container_path = "/usr/src/app/proxygen/config.json"
    console_socket_file = runc_base + container_name + "/console.sock"

    args = parse_arguments()
    if args.rebuild_image or not os.path.isdir(container_name):
        build_oci_bundle(container_name, runc_base, app_config_container_path)

    results = {"experiment": [], "run": [], "seedServer": [],
               "migrationTechnique": [], "memoryFootprintInflation [MB]": [],
               "compressionEnabled": [],
               "preDumpTime [s]": [], "preDumpTxTime [s]": [],
               "dumpTime [s]": [], "dumpTxTime [s]": [],
               "dumpSize": [], "preDumpSize": [],
               "rsyncPreDumpTotalFileSize": [],
               "rsyncPreDumpTotalBytesSent": [],
               "rsyncPreDumpTransferRate": [],
               "rsyncPreDumpCompressionSpeedup": [],
               "rsyncDumpTotalFileSize": [],
               "rsyncDumpTotalBytesSent": [],
               "rsyncDumpTransferRate": [],
               "rsyncDumpCompressionSpeedup": []}

    # Create socket used to receive migration commands
    command_socket = create_command_socket()

    run = 1
    n_clients = 30
    config_list, migration_technique_list = generate_all_configs()

    for config, technique in zip(config_list, migration_technique_list):
        # Copy a fresh version of the OCI bundle to the runC base directory.
        # Given that rsync transfers files in an incremental way, this is useful
        # to avoid that migration times are dependent on previous migrations.
        remove_oci_bundle_in_runc_dir(runc_base, container_name)
        copy_oci_bundle_to_runc_dir(runc_base, container_name)

        logger.info("New experiment run with migration technique {} "
                    "and configuration\n{}"
                    .format(str(technique), json.dumps(config, indent=4)))

        # Update the configuration file used by the application.
        update_configuration_file(runc_base, container_name,
                                  app_config_container_path, config)

        # Start the server container.
        console_socket_proc = start_console_socket(console_socket_file,
                                                   suppress_output=False)
        start_container(runc_base, container_name, container_name,
                        console_socket_file=console_socket_file,
                        detached=True)

        # Handler used to stop the console socket and
        # the container if a failure occurs.
        atexit.unregister(exit_handler)
        atexit.register(exit_handler, command_socket, console_socket_proc,
                        console_socket_file, container_name, results)

        # Wait for migration command.
        wait_for_migration_command(command_socket)

        # Start migration.
        migration_measurements = start_migration(runc_base,
                                                 container_name,
                                                 args.destination_ip,
                                                 technique.pre,
                                                 technique.lazy,
                                                 args.enable_compression)

        # Save results.
        save_migration_measurements(results, run, n_clients, config,
                                    technique, migration_measurements,
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
        run += 1

    logger.info("Ending the experiment")
    dump_experiment_results_to_file(results)


if __name__ == "__main__":
    main()

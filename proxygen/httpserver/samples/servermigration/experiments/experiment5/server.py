import argparse
import atexit
import pandas as pd

from utils.oci import *
from utils.configuration import *
from utils.migrate_server_source import *
from utils.migrate_server_destination import *

logger = logging.getLogger("server")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def exit_handler(command_socket, migration_socket, console_socket_proc,
                 console_socket_file, container_name, results, first_role):
    stop_container_and_console_socket(console_socket_proc, console_socket_file,
                                      container_name)
    command_socket.close()
    migration_socket.close()
    dump_experiment_results_to_file(
        results, first_role, call_from_exit_handler=True)


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
    parser.add_argument("--first_role", dest="first_role", action="store",
                        choices=["source", "destination"], type=str,
                        required=True)
    parser.add_argument("--management_port", dest="management_port",
                        action="store", type=int, required=True)
    parser.add_argument("--other_server_ip", dest="other_server_ip",
                        action="store", type=str, required=True)
    parser.add_argument("--repetitions", dest="repetitions", action="store",
                        type=int, required=True)

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


def generate_all_configs():
    combination_list = generate_experiment_combinations()
    config_path = "./baseconfigs/experiment5_server.json"
    config_and_frequency_list = []

    for combination in combination_list:
        with open(config_path, "r") as config_file:
            config = json.load(config_file)
            migration_frequency = combination[0]
            config_and_frequency_list.append((config, migration_frequency))

    return config_and_frequency_list


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
            return True

        try:
            command = json.loads(message)
            if command["action"] == "shutdown":
                logger.info("Sending response: OK")
                response = "OK"
                command_socket.sendto(response.encode(), address)
                return False
        except:
            pass
        logger.info("Ignoring message")


def migrate_to_destination(command_socket, runc_base, container_name,
                           destination_ip, technique, enable_compression,
                           total_migration_times):
    success = wait_for_migration_command(command_socket)
    if not success:
        return False

    migration_times = start_migration(
        runc_base, container_name, destination_ip,
        technique.pre, technique.lazy, enable_compression)

    if not total_migration_times:
        for key, value in migration_times.items():
            total_migration_times[key] = [value]
    else:
        for key, value in total_migration_times.items():
            value.append(migration_times[key])

    return True


def receive_migration_from_source(migration_socket, command_socket,
                                  management_ip, management_port,
                                  total_restore_times):
    restore_times = wait_for_server_migration(
        migration_socket, command_socket,
        management_ip, management_port)
    if not restore_times:
        return False

    if not total_restore_times:
        for key, value in restore_times.items():
            total_restore_times[key] = [value]
    else:
        for key, value in total_restore_times.items():
            value.append(restore_times[key])

    return True


def handle_periodic_migrations(first_role, n_migrations, command_socket,
                               migration_socket, runc_base, container_name,
                               console_socket_file, technique, this_server_ip,
                               other_server_ip, management_port,
                               enable_compression, results):
    # Start the console socket for the server application.
    console_socket_proc = start_console_socket(
        console_socket_file, suppress_output=False)

    if first_role == "source":
        # Start the server container.
        start_container(runc_base, container_name, detached=True,
                        console_socket_file=console_socket_file)

    total_migration_times = {}
    total_restore_times = {}
    wait_for_server_termination_at_the_end = False

    for i in range(0, n_migrations):
        # Handler used to stop the console socket and
        # the container if a failure occurs.
        atexit.unregister(exit_handler)
        atexit.register(exit_handler, command_socket, migration_socket,
                        console_socket_proc, console_socket_file,
                        container_name, results, first_role)

        even = (i % 2) == 0
        odd = not even

        if (first_role == "source" and even) \
                or (first_role == "destination" and odd):
            success = migrate_to_destination(
                command_socket, runc_base, container_name, other_server_ip,
                technique, enable_compression, total_migration_times)
            if not success:
                wait_for_server_termination_at_the_end = None
                break

            # Remove the console socket file.
            stop_console_socket(console_socket_proc, console_socket_file)

            # Start a new console socket for the server application,
            # if this server will act as destination in the next round.
            if i != n_migrations - 1:
                console_socket_proc = start_console_socket(
                    console_socket_file, suppress_output=False)

            wait_for_server_termination_at_the_end = False
        else:
            success = receive_migration_from_source(
                migration_socket, command_socket, this_server_ip,
                management_port, total_restore_times)
            if not success:
                wait_for_server_termination_at_the_end = None
                break

            wait_for_server_termination_at_the_end = True

    return wait_for_server_termination_at_the_end, total_migration_times, \
           total_restore_times, console_socket_proc


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


def save_migration_measurements(results, run, repetition, seed,
                                migration_technique, total_migration_times,
                                total_restore_times, compression_enabled):
    results["experiment"].append(5)
    results["run"].append(run)
    results["repetition"].append(repetition)
    results["seed"].append(seed)
    results["migrationTechnique"] \
        .append(migration_technique.to_camel_case_string())
    results["compressionEnabled"].append(compression_enabled)

    results["preDumpTimes [s]"] \
        .append(total_migration_times.get("preDumpTime", None))
    results["preDumpTxTimes [s]"] \
        .append(total_migration_times.get("preDumpTxTime", None))
    results["dumpTimes [s]"] \
        .append(total_migration_times.get("dumpTime", None))
    results["dumpTxTimes [s]"] \
        .append(total_migration_times.get("dumpTxTime", None))
    results["dumpSizes"] \
        .append(total_migration_times.get("dumpSize", None))
    results["preDumpSizes"] \
        .append(total_migration_times.get("preDumpSize", None))
    results["rsyncPreDumpTotalFileSizes"] \
        .append(total_migration_times.get("rsyncPreDumpTotalFileSize", None))
    results["rsyncPreDumpTotalBytesSent"] \
        .append(total_migration_times.get("rsyncPreDumpTotalBytesSent", None))
    results["rsyncPreDumpTransferRates"] \
        .append(total_migration_times.get("rsyncPreDumpTransferRate", None))
    results["rsyncPreDumpCompressionSpeedups"] \
        .append(total_migration_times.get("rsyncPreDumpCompressionSpeedup",
                                          None))
    results["rsyncDumpTotalFileSizes"] \
        .append(total_migration_times.get("rsyncDumpTotalFileSize", None))
    results["rsyncDumpTotalBytesSent"] \
        .append(total_migration_times.get("rsyncDumpTotalBytesSent", None))
    results["rsyncDumpTransferRates"] \
        .append(total_migration_times.get("rsyncDumpTransferRate", None))
    results["rsyncDumpCompressionSpeedups"] \
        .append(total_migration_times.get("rsyncDumpCompressionSpeedup", None))

    results["restoreTimes [s]"] \
        .append(total_restore_times.get("restoreTime", None))
    results["lazyPagesTxTimes [s]"] \
        .append(total_restore_times.get("lazyPagesTxTime", None))
    results["lazyPagesTxEndTimes [s]"] \
        .append(total_restore_times.get("lazyPagesTxEndTime", None))
    results["numberOfLazyPages"] \
        .append(total_restore_times.get("numberOfLazyPages", None))


def dump_experiment_results_to_file(results, first_role,
                                    call_from_exit_handler=False):
    df = pd.DataFrame(results)
    if first_role == "source":
        results_file = "experiment5_first_source"
    else:
        results_file = "experiment5_first_destination"
    if call_from_exit_handler is True:
        results_file += ".bak.csv"
    else:
        results_file += ".csv"
    df.to_csv(results_file, encoding="utf-8", index=False)


def main():
    container_name = "mhq-server"
    runc_base = "/runc/containers/"
    app_config_container_path = "/usr/src/app/proxygen/config.json"
    console_socket_file = runc_base + container_name + "/console.sock"

    args = parse_arguments()
    if args.rebuild_image or not os.path.isdir(container_name):
        build_oci_bundle(container_name, runc_base, app_config_container_path)

    results = {"experiment": [], "run": [], "repetition": [], "seed": [],
               "migrationTechnique": [], "compressionEnabled": [],
               "preDumpTimes [s]": [], "preDumpTxTimes [s]": [],
               "dumpTimes [s]": [], "dumpTxTimes [s]": [],
               "dumpSizes": [], "preDumpSizes": [],
               "rsyncPreDumpTotalFileSizes": [],
               "rsyncPreDumpTotalBytesSent": [],
               "rsyncPreDumpTransferRates": [],
               "rsyncPreDumpCompressionSpeedups": [],
               "rsyncDumpTotalFileSizes": [], "rsyncDumpTotalBytesSent": [],
               "rsyncDumpTransferRates": [], "rsyncDumpCompressionSpeedups": [],
               "restoreTimes [s]": [], "lazyPagesTxTimes [s]": [],
               "lazyPagesTxEndTimes [s]": [], "numberOfLazyPages": []}

    # Create socket used to receive migration commands
    # and send onNetworkSwitch commands.
    command_socket = create_command_socket()
    this_server_ip = command_socket.getsockname()[0]

    # Create socket used to receive incoming server migrations.
    migration_socket = create_migration_socket()

    run = 0
    seed = 0
    session_duration = 60  # 1 hour, expressed in minutes
    config_and_frequency_list = generate_all_configs()
    technique = MigrationTechnique.HYBRID

    for config, migration_frequency in config_and_frequency_list:
        run += 1
        n_migrations = int(session_duration / migration_frequency)
        for i in range(1, args.repetitions + 1):
            # Copy a fresh version of the OCI bundle to the runC base directory.
            remove_oci_bundle_in_runc_dir(runc_base, container_name)
            copy_oci_bundle_to_runc_dir(runc_base, container_name)

            seed += 1
            config["seed"] = seed

            if args.first_role == "source":
                logger.info("New experiment run with migration technique {} "
                            "and configuration\n{}".format(
                    str(technique), json.dumps(config, indent=4)))

            update_configuration_file(
                runc_base, container_name, app_config_container_path, config)

            wait_for_server_termination_at_the_end, total_migration_times, \
            total_restore_times, last_console_socket_proc = \
                handle_periodic_migrations(
                    args.first_role, n_migrations, command_socket,
                    migration_socket, runc_base, container_name,
                    console_socket_file, technique, this_server_ip,
                    args.other_server_ip, args.management_port,
                    args.enable_compression, results)

            # If wait_for_server_termination_at_the_end is None, i.e. if a
            # shutdown command interrupted the migration, both the following
            # branches are skipped.
            if wait_for_server_termination_at_the_end is True:
                wait_for_server_termination(container_name)
            elif wait_for_server_termination_at_the_end is False:
                wait_for_end_command(command_socket)

            # Force console socket and container to stop at the end of the run.
            logger.info("End of an experiment run: stopping console socket "
                        "and container, if still up")
            stop_container_and_console_socket(
                last_console_socket_proc, console_socket_file, container_name)

            # Save results.
            save_migration_measurements(results, run, i, config["seed"],
                                        technique, total_migration_times,
                                        total_restore_times,
                                        args.enable_compression)

            # Sleep before starting a new run.
            logger.info("Sleeping for 5 seconds before the next run")
            time.sleep(5)

    logger.info("Ending the experiment")
    dump_experiment_results_to_file(results, args.first_role)


if __name__ == "__main__":
    main()

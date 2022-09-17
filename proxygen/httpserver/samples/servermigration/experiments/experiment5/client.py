import atexit
import argparse
import socket
import pandas as pd
import json
import psutil
import select

from utils.configuration import *
from utils.handover import *

logger = logging.getLogger("client")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def exit_handler(client_process, results):
    stop_client_process(client_process)
    dump_experiment_results_to_file(results, call_from_exit_handler=True)


def stop_client_process(client_process):
    logger.info("Stopping client process")
    try:
        process = psutil.Process(client_process.pid)
        for child in process.children(recursive=True):
            child.kill()
        process.kill()
    except:
        pass


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial_access_point", dest="initial_access_point",
                        action="store", required=True, choices=["ap1", "ap2"])
    parser.add_argument("--server_app_port", dest="server_app_port",
                        action="store", type=int, required=True)
    parser.add_argument("--server_management_port",
                        dest="server_management_port", action="store",
                        type=int, required=True)
    parser.add_argument("--first_server_ip_eth", dest="first_server_ip_eth",
                        action="store", type=str, required=True)
    parser.add_argument("--second_server_ip_eth", dest="second_server_ip_eth",
                        action="store", type=str, required=True)
    parser.add_argument("--first_server_ip_wifi", dest="first_server_ip_wifi",
                        action="store", type=str, required=True)
    parser.add_argument("--second_server_ip_wifi", dest="second_server_ip_wifi",
                        action="store", type=str, required=True)
    parser.add_argument("--repetitions", dest="repetitions", action="store",
                        type=int, required=True)
    return parser.parse_args()


def generate_all_configs():
    combination_list = generate_experiment_combinations()
    config_path = "./baseconfigs/experiment5_client.json"
    config_and_frequency_list = []

    for combination in combination_list:
        with open(config_path, "r") as config_file:
            config = json.load(config_file)
            migration_frequency = combination[0]
            quic_protocol = combination[1]
            config["experiment"]["serverMigrationProtocol"] = quic_protocol
            config_and_frequency_list.append((config, migration_frequency))

    # Note: the seed is updated at each repetition, but outside this function.
    return config_and_frequency_list


def update_configuration_file(config_name, new_config):
    with open(config_name, "w") as config_file:
        json.dump(new_config, config_file, indent=4)


def start_client_process(client_exec_path, config_name, vlog_level):
    cmd = "sudo {} --mode=client --config={} --v={}" \
        .format(client_exec_path, config_name, vlog_level)
    logger.info("Starting client process")
    logger.info("Running '{}'".format(cmd))
    proc = subprocess.Popen(cmd, shell=True)
    return proc


def notify_imminent_server_migration(migration_notification_socket,
                                     server_management_ip, management_port,
                                     destination_address, quic_protocol,
                                     response_timeout):
    if "Explicit" in quic_protocol:
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Explicit",
                              "address": destination_address,
                              "notifyMigrationReady": True})
    elif quic_protocol == "poolOfAddresses":
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Pool of Addresses",
                              "notifyMigrationReady": True})
    elif quic_protocol == "symmetric":
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Symmetric",
                              "notifyMigrationReady": True})
    elif quic_protocol == "synchronizedSymmetric":
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Synchronized Symmetric",
                              "notifyMigrationReady": True})
    else:
        raise RuntimeError("Invalid QUIC migration protocol")

    logger.info("Notifying imminent server migration sending command '{}' "
                "to {}:{}".format(command, server_management_ip,
                                  management_port))
    migration_notification_socket.sendto(
        command.encode(), (server_management_ip, management_port))

    logger.info("Waiting for the response")
    while True:
        input_ready, _, _ = select.select(
            [migration_notification_socket], [], [], response_timeout)
        if not input_ready:
            return False

        message, address = migration_notification_socket.recvfrom(1024)
        message = message.decode()
        logger.info("Received message '{}' from {}:{}"
                    .format(message, *address))
        if message == "OK":
            return True


def wait_for_migration_ready_notification(migration_notification_socket,
                                          response_timeout):
    logger.info("Waiting for the server to be ready for migration")
    while True:
        input_ready, _, _ = select.select(
            [migration_notification_socket], [], [], response_timeout)
        if not input_ready:
            return False

        message, address = migration_notification_socket.recvfrom(1024)
        message = message.decode()
        logger.info("Received message '{}' from {}:{}"
                    .format(message, *address))
        if message == "migration ready":
            return True


def trigger_server_migration(container_migration_script_ip):
    command = "migrate"
    logger.info("Triggering server migration sending command '{}' to {}:{}"
                .format(command, container_migration_script_ip, 19888))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(command.encode(), (container_migration_script_ip, 19888))

    logger.info("Waiting for the response")
    while True:
        message, address = sock.recvfrom(1024)
        message = message.decode()
        logger.info("Received message '{}' from {}:{}"
                    .format(message, *address))
        if message == "OK":
            return


def send_shutdown(address, port, tcp_socket=False):
    command = json.dumps({"action": "shutdown"})
    logger.info("Sending shutdown command {} to {}:{}"
                .format(command, address, port))

    if not tcp_socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(command.encode(), (address, port))
        logger.info("Waiting for the response")
        while True:
            message, address = sock.recvfrom(1024)
            message = message.decode()
            logger.info("Received message '{}' from {}:{}"
                        .format(message, *address))
            if message == "OK":
                return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((address, port))
    sock.send(command.encode())


def send_handover_command(handover_command_socket, response_timeout,
                          tc_script_path):
    current_ap = get_current_access_point()
    if current_ap is None:
        return False

    next_ap = current_ap.choose_next_ap_for_handover()
    if next_ap is None:
        return False

    command = json.dumps({"action": "handover",
                          "address": "{}:0".format(next_ap.client_address),
                          "accessPoint": next_ap.ssid,
                          "accessPointGateway": next_ap.gateway,
                          "otherAccessPointSubnet": current_ap.subnet,
                          "tcScript": tc_script_path})

    logger.info("Sending handover command {} to {}:{}"
                .format(command, current_ap.client_address, 5555))
    handover_command_socket.sendto(command.encode(),
                                   (current_ap.client_address, 5555))
    logger.info("Waiting for the response")

    while True:
        input_ready, _, _ = select.select(
            [handover_command_socket], [], [], response_timeout)
        if not input_ready:
            return False

        message, address = handover_command_socket.recvfrom(1024)
        message = message.decode()
        logger.info("Received message '{}' from {}:{}"
                    .format(message, *address))
        if message == "OK":
            return True
        elif "error" in message.lower():
            return False
        logger.info("Ignoring message")


def migrate_periodically_and_shutdown(
        session_duration, migration_frequency, first_server_ip_eth,
        second_server_ip_eth, first_server_ip_wifi, second_server_ip_wifi,
        server_app_port, server_management_port, quic_protocol,
        client_process, tc_script_path):
    handover_timestamp_list = []
    migration_notification_timestamp_list = []
    migration_trigger_timestamp_list = []
    n_migrations = int(session_duration / migration_frequency)
    early_exit = False

    server_management_current_ip = first_server_ip_eth
    server_script_source_current_ip = first_server_ip_eth
    server_script_destination_current_ip = second_server_ip_eth

    server_app_source_current_ip = first_server_ip_wifi
    server_app_destination_current_ip = second_server_ip_wifi

    migration_notification_socket = \
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    handover_command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    handover_command_socket.bind(("127.0.0.1", 0))

    command_timeout = 180
    wait_time_before_ending_experiment = 300

    for i in range(0, n_migrations):
        time.sleep(migration_frequency * 60)  # Frequency in seconds.

        # Perform handover.
        handover_timestamp = time.time()
        success = send_handover_command(
            handover_command_socket, command_timeout, tc_script_path)
        handover_timestamp_list.append(handover_timestamp)
        if not success:
            logger.error("Stopping run after handover failure")
            stop_client_process(client_process)
            early_exit = True
            break

        # Notify imminent server migration.
        destination_address = "{}:{}".format(server_app_destination_current_ip,
                                             server_app_port)
        notification_timestamp = time.time()
        success = notify_imminent_server_migration(
            migration_notification_socket, server_management_current_ip,
            server_management_port, destination_address, quic_protocol,
            command_timeout)
        if not success:
            logger.error("Timeout while sending the imminent migration "
                         "notification. Stopping the run")
            early_exit = True
            break

        # Wait for the server to be ready and send the migration trigger.
        ready = wait_for_migration_ready_notification(
            migration_notification_socket, command_timeout)
        if not ready:
            logger.error("Timeout while waiting for the server to "
                         "prepare for migration. Stopping the run")
            early_exit = True
            break

        trigger_timestamp = time.time()
        trigger_server_migration(server_script_source_current_ip)

        # Update variables for next migrations.
        previous_script_source_ip = server_script_source_current_ip
        server_script_source_current_ip = server_script_destination_current_ip
        server_management_current_ip = server_script_destination_current_ip
        server_script_destination_current_ip = previous_script_source_ip

        previous_app_source_ip = server_app_source_current_ip
        server_app_source_current_ip = server_app_destination_current_ip
        server_app_destination_current_ip = previous_app_source_ip

        migration_notification_timestamp_list.append(notification_timestamp)
        migration_trigger_timestamp_list.append(trigger_timestamp)

    if not early_exit:
        # Wait for 5 minutes and end the experiment.
        time.sleep(wait_time_before_ending_experiment)
        send_shutdown(server_management_current_ip, server_management_port)
        send_shutdown(server_script_destination_current_ip, 19888)
    else:
        send_shutdown(server_management_current_ip, server_management_port)
        send_shutdown(server_script_source_current_ip, 19888)
        send_shutdown(server_script_destination_current_ip, 18863,
                      tcp_socket=True)

    return handover_timestamp_list, migration_notification_timestamp_list, \
           migration_trigger_timestamp_list


def parse_service_times_dump(service_times_file):
    try:
        with open(service_times_file, "r") as dump_file:
            service_times = json.load(dump_file)
        os.remove(service_times_file)
        return service_times
    except:
        logger.error("Cannot parse the service times dump file")
        return {}


def save_service_times(results, service_times, run, repetition, seed,
                       quic_protocol, migration_frequency,
                       handover_timestamps,
                       migration_notification_timestamps,
                       migration_trigger_timestamps):
    results["experiment"].append(5)
    results["run"].append(run)
    results["repetition"].append(repetition)
    results["seed"].append(seed)
    results["protocol"].append(quic_protocol)
    results["clientMigrationFrequency [min]"].append(migration_frequency)
    results["requestTimestamps [us]"] \
        .append(service_times.get("requestTimestamps", None))
    results["serviceTimes [us]"] \
        .append(service_times.get("serviceTimes", None))
    results["serverAddresses"] \
        .append(service_times.get("serverAddresses", None))
    results["handoverTimestamps [s]"].append(handover_timestamps)
    results["migrationNotificationTimestamps [s]"] \
        .append(migration_notification_timestamps)
    results["migrationTriggerTimestamps [s]"] \
        .append(migration_trigger_timestamps)


def dump_experiment_results_to_file(results, call_from_exit_handler=False):
    df = pd.DataFrame(results)
    if call_from_exit_handler is True:
        results_file = "experiment5_service_times.bak.csv"
    else:
        results_file = "experiment5_service_times.csv"
    df.to_csv(results_file, encoding="utf-8", index=False)


def main():
    args = parse_arguments()
    client_exec_path = "./proxygen/proxygen/_build/proxygen/httpserver/mhq"
    tc_script_path = os.path.abspath("../tc/tc_setup_experiment_5.sh")
    config_file = "config.json"
    service_times_file = "service_times.json"

    results = {"experiment": [], "run": [], "repetition": [], "seed": [],
               "protocol": [], "clientMigrationFrequency [min]": [],
               "requestTimestamps [us]": [], "serviceTimes [us]": [],
               "serverAddresses": [], "handoverTimestamps [s]": [],
               "migrationNotificationTimestamps [s]": [],
               "migrationTriggerTimestamps [s]": []}

    run = 0
    seed = 0
    session_duration = 60  # 1 hour, expressed in minutes
    client_process = None
    config_and_frequency_list = generate_all_configs()
    starting_ap = AccessPoint[args.initial_access_point.upper()]

    for config, migration_frequency in config_and_frequency_list:
        run += 1
        for i in range(1, args.repetitions + 1):
            seed += 1
            config["seed"] = seed
            logger.info("New experiment run with migration frequency of {} "
                        "minutes and configuration\n{}"
                        .format(migration_frequency,
                                json.dumps(config, indent=4)))

            # Always start connected to the access point passed as argument.
            success = perform_handover(starting_ap)
            if not success:
                logger.error("Impossible to start the run: "
                             "cannot connect to the access point")
                if client_process is not None:
                    stop_client_process(client_process)

                send_shutdown(args.first_server_ip_eth,
                              args.server_management_port)
                send_shutdown(args.first_server_ip_eth, 19888)
                send_shutdown(args.second_server_ip_eth, 18863, tcp_socket=True)
                logger.info("Sleeping for 10 seconds before the next run")
                time.sleep(10)
                continue

            # Start the client program.
            update_configuration_file(config_file, config)
            client_process = start_client_process(
                client_exec_path, config_file, vlog_level=3)

            # Handler used to stop the client if a failure occurs.
            atexit.unregister(exit_handler)
            atexit.register(exit_handler, client_process, results)

            # Start periodic handovers followed by server migrations.
            handover_timestamps, migration_notification_timestamps, \
            migration_trigger_timestamps = \
                migrate_periodically_and_shutdown(
                    session_duration, migration_frequency,
                    args.first_server_ip_eth, args.second_server_ip_eth,
                    args.first_server_ip_wifi, args.second_server_ip_wifi,
                    args.server_app_port, args.server_management_port,
                    config["experiment"]["serverMigrationProtocol"],
                    client_process, tc_script_path)

            time.sleep(200)
            stop_client_process(client_process)

            # Save the results.
            service_times = parse_service_times_dump(service_times_file)
            save_service_times(results, service_times, run, i, config["seed"],
                               config["experiment"]["serverMigrationProtocol"],
                               migration_frequency,
                               handover_timestamps,
                               migration_notification_timestamps,
                               migration_trigger_timestamps)

            # Sleep before starting a new run.
            logger.info("End of an experiment run. Sleeping for 10 seconds "
                        "before the next run")
            time.sleep(10)

    logger.info("Ending the experiment")
    dump_experiment_results_to_file(results)


if __name__ == "__main__":
    main()

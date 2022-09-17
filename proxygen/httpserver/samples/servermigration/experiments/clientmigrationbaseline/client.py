import atexit
import argparse
import socket
import pandas as pd
import json
import psutil
import select

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
    parser.add_argument("--repetitions", dest="repetitions", action="store",
                        type=int, required=True)
    parser.add_argument("--server_management_port",
                        dest="server_management_port", action="store",
                        type=int, required=True)
    parser.add_argument("--initial_access_point", dest="initial_access_point",
                        action="store", required=True, choices=["ap1", "ap2"])
    parser.add_argument("--server_ip_eth", dest="server_ip_eth",
                        action="store", type=str, required=True)
    return parser.parse_args()


def load_base_configuration():
    with open("./baseconfigs/experiment6_client.json", "r") as config_file:
        return json.load(config_file)


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


def send_shutdown(address, port):
    command = json.dumps({"action": "shutdown"})
    logger.info("Sending shutdown command {} to {}:{}"
                .format(command, address, port))

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


def migrate_periodically_and_shutdown(session_duration, migration_frequency,
                                      server_ip_eth, server_management_port,
                                      client_process, tc_script_path):
    handover_timestamp_list = []
    n_migrations = int(session_duration / migration_frequency)
    early_exit = False

    handover_command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    handover_command_socket.bind(("127.0.0.1", 0))

    wait_time_before_ending_experiment = 300
    command_timeout = 180

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

    if not early_exit:
        time.sleep(wait_time_before_ending_experiment)

    send_shutdown(server_ip_eth, server_management_port)
    return handover_timestamp_list


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
                       migration_frequency, handover_timestamps):
    results["experiment"].append(6)
    results["run"].append(run)
    results["repetition"].append(repetition)
    results["seed"].append(seed)
    results["clientMigrationFrequency [min]"].append(migration_frequency)
    results["requestTimestamps [us]"] \
        .append(service_times.get("requestTimestamps", None))
    results["serviceTimes [us]"] \
        .append(service_times.get("serviceTimes", None))
    results["serverAddresses"] \
        .append(service_times.get("serverAddresses", None))
    results["handoverTimestamps [s]"].append(handover_timestamps)


def dump_experiment_results_to_file(results, call_from_exit_handler=False):
    df = pd.DataFrame(results)
    if call_from_exit_handler is True:
        results_file = "experiment6_service_times.bak.csv"
    else:
        results_file = "experiment6_service_times.csv"
    df.to_csv(results_file, encoding="utf-8", index=False)


def main():
    args = parse_arguments()
    client_exec_path = "./proxygen/proxygen/_build/proxygen/httpserver/mhq"
    tc_script_path = os.path.abspath("../tc/tc_setup_experiment_6.sh")
    config_file = "config.json"
    service_times_file = "service_times.json"

    results = {"experiment": [], "run": [], "repetition": [], "seed": [],
               "clientMigrationFrequency [min]": [],
               "requestTimestamps [us]": [], "serviceTimes [us]": [],
               "serverAddresses": [], "handoverTimestamps [s]": []}

    run = 0
    seed = 0
    session_duration = 60  # 1 hour, expressed in minutes
    migration_frequency_list = [10]  # Minutes
    config = load_base_configuration()
    starting_ap = AccessPoint[args.initial_access_point.upper()]
    client_process = None

    for migration_frequency in migration_frequency_list:
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

                send_shutdown(args.server_ip_eth, args.server_management_port)
                logger.info("Sleeping for 10 seconds before the next run")
                time.sleep(10)
                continue

            # Start the client container.
            update_configuration_file(config_file, config)
            client_process = start_client_process(
                client_exec_path, config_file, vlog_level=3)

            # Handler used to stop the client if a failure occurs.
            atexit.unregister(exit_handler)
            atexit.register(exit_handler, client_process, results)

            # Start periodic handovers.
            handover_timestamps = migrate_periodically_and_shutdown(
                session_duration, migration_frequency, args.server_ip_eth,
                args.server_management_port, client_process, tc_script_path)

            time.sleep(200)
            stop_client_process(client_process)

            # Save the results.
            service_times = parse_service_times_dump(service_times_file)
            save_service_times(results, service_times, run, i, config["seed"],
                               migration_frequency, handover_timestamps)

            # Sleep before starting a new run.
            logger.info("Sleeping for 10 seconds before the next run")
            time.sleep(10)

    logger.info("Ending the experiment")
    dump_experiment_results_to_file(results)


if __name__ == "__main__":
    main()

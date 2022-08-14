import atexit
import argparse
import socket
import pandas as pd
import json

from utils.docker import *
from utils.handover import *

logger = logging.getLogger("client")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def exit_handler(container_name, logs_destination_path,
                 config_file, service_times_file, results):
    stop_container_and_clean_files(container_name, logs_destination_path,
                                   config_file, service_times_file)
    dump_experiment_results_to_file(results, call_from_exit_handler=True)


def stop_container_and_clean_files(container_name, logs_destination_path,
                                   config_file, service_times_file):
    kill_docker_container(container_name)
    append_docker_container_logs(container_name, logs_destination_path)
    remove_docker_container(container_name)
    try:
        os.remove(config_file)
    except:
        pass
    try:
        os.remove(service_times_file)
    except:
        pass


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild_image", dest="rebuild_image",
                        action="store_true", default=False)
    parser.add_argument("--repetitions", dest="repetitions", action="store",
                        type=int, required=True)
    parser.add_argument("--management_port", dest="management_port",
                        action="store", type=int, required=True)
    return parser.parse_args()


def load_base_configuration():
    with open("./baseconfigs/experiment6_client.json", "r") as config_file:
        return json.load(config_file)


def update_configuration_file(container_name, config_name,
                              app_config_container_path, new_config):
    with open(config_name, "w") as config_file:
        json.dump(new_config, config_file, indent=4)
    copy_to_docker_container(container_name, config_name,
                             app_config_container_path)


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


def migrate_periodically_and_shutdown(session_duration, migration_frequency,
                                      server_ip, server_management_port,
                                      container_name):
    handover_timestamp_list = []
    n_migrations = int(session_duration / migration_frequency)
    early_exit = False

    wait_time_after_each_migration = 180
    wait_time_before_ending_experiment = 300

    for i in range(0, n_migrations):
        time.sleep(migration_frequency * 60)  # Frequency in seconds.

        # Perform handover.
        handover_timestamp = time.time()
        success = perform_handover()
        handover_timestamp_list.append(handover_timestamp)
        if not success:
            logger.error("Stopping run after handover failure")
            kill_docker_container(container_name)
            early_exit = True
            break

        # Wait for some minutes and check if the client container is still up
        # and running. Due to packet loss, client migration could fail (loss of
        # path validation frames, which are not retransmitted in mvfst).
        time.sleep(wait_time_after_each_migration)
        state = get_docker_container_state(container_name)
        if state == DockerContainerState.EXITED \
                or state == DockerContainerState.PAUSED:
            logger.error("Client application timed out after client handover. "
                         "Stopping run")
            early_exit = True
            break

    if not early_exit:
        time.sleep(wait_time_before_ending_experiment)

    send_shutdown(server_ip, server_management_port)
    return handover_timestamp_list


def wait_for_client_termination(container_name):
    logger.info("Waiting for client termination")
    while True:
        state = get_docker_container_state(container_name)
        if state == DockerContainerState.EXITED \
                or state == DockerContainerState.PAUSED:
            logger.info("Client terminated")
            break
        time.sleep(5)


def parse_service_times_dump(container_name, service_times_file,
                             app_service_times_dump_container_path):
    copy_from_docker_container(container_name, service_times_file,
                               app_service_times_dump_container_path)
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
    container_name = "mhq-client"
    docker_network = "docker_handover"
    logs_destination_path = "exp6_client_docker.out"

    config_file = "config.json"
    app_config_container_path = "/usr/src/app/proxygen/"

    service_times_file = "service_times.json"
    app_service_times_dump_container_path = \
        "/usr/src/app/proxygen/" + service_times_file

    results = {"experiment": [], "run": [], "repetition": [], "seed": [],
               "clientMigrationFrequency [min]": [],
               "requestTimestamps [us]": [], "serviceTimes [us]": [],
               "serverAddresses": [], "handoverTimestamps [s]": []}

    if args.rebuild_image:
        pull_latest_docker_image()

    # Handler used to stop the container and
    # clean the local directory if a failure occurs.
    atexit.unregister(exit_handler)
    atexit.register(exit_handler, container_name, logs_destination_path,
                    config_file, service_times_file, results)

    run = 0
    seed = 0
    session_duration = 60  # 1 hour, expressed in minutes
    migration_frequency_list = [10, 30]  # Minutes
    config = load_base_configuration()
    server_ip = config["serverHost"]

    for migration_frequency in migration_frequency_list:
        run += 1
        for i in range(1, args.repetitions + 1):
            seed += 1
            config["seed"] = seed
            logger.info("New experiment run with migration frequency of {} "
                        "minutes and configuration\n{}"
                        .format(migration_frequency,
                                json.dumps(config, indent=4)))

            # Always start connected to AP1.
            success = perform_handover(selected_access_point=AccessPoint.AP1)
            if not success:
                logger.error("Impossible to start the run: "
                             "cannot connect to the access point")
                stop_container_and_clean_files(
                    container_name, logs_destination_path,
                    config_file, service_times_file)

                send_shutdown(server_ip, args.management_port)
                logger.info("Sleeping for 10 seconds before the next run")
                time.sleep(10)
                continue

            # Start the client container.
            create_docker_container(container_name, docker_network,
                                    AppMode.CLIENT, config_file, vlog_level=3)
            update_configuration_file(container_name, config_file,
                                      app_config_container_path, config)
            start_docker_container(container_name)

            # Start periodic handovers.
            handover_timestamps = migrate_periodically_and_shutdown(
                session_duration, migration_frequency, server_ip,
                args.management_port, container_name)

            wait_for_client_termination(container_name)

            # Save the results.
            service_times = parse_service_times_dump(
                container_name, service_times_file,
                app_service_times_dump_container_path)

            save_service_times(results, service_times, run, i, config["seed"],
                               migration_frequency, handover_timestamps)

            # Force container to stop at the end of the run.
            logger.info(
                "End of an experiment run: stopping container, if still up")
            stop_container_and_clean_files(
                container_name, logs_destination_path,
                config_file, service_times_file)

            # Sleep before starting a new run.
            logger.info("Sleeping for 10 seconds before the next run")
            time.sleep(10)

    logger.info("Ending the experiment")
    dump_experiment_results_to_file(results)


if __name__ == "__main__":
    main()

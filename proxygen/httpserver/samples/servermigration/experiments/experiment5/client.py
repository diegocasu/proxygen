import atexit
import argparse
import socket
import pandas as pd
import json

from utils.configuration import *
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
    parser.add_argument("--server_app_port", dest="server_app_port",
                        action="store", type=int, required=True)
    parser.add_argument("--management_port", dest="management_port",
                        action="store", type=int, required=True)
    parser.add_argument("--first_server_ip", dest="first_server_ip",
                        action="store", type=str, required=True)
    parser.add_argument("--second_server_ip", dest="second_server_ip",
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


def start_client_container(container_name, docker_network, config_file,
                           app_config_container_path, config,
                           logs_destination_path, service_times_file):
    # Attempt to start the container until the handshake succeeds.
    # The handshake could fail due to packet loss.
    while True:
        create_docker_container(container_name, docker_network,
                                AppMode.CLIENT, config_file, vlog_level=3)
        update_configuration_file(container_name, config_file,
                                  app_config_container_path, config)
        start_docker_container(container_name)

        # Wait for 30 seconds and check if client container is still up.
        # If it is not up, the handshake failed, so clean up and retry.
        time.sleep(30)
        state = get_docker_container_state(container_name)
        if state == DockerContainerState.EXITED \
                or state == DockerContainerState.PAUSED:
            logger.error("Restarting the client container: handshake with the "
                         "server failed")
            stop_container_and_clean_files(
                container_name, logs_destination_path,
                config_file, service_times_file)
            continue

        logger.info("Client application successfully completed the "
                    "handshake with the server")
        break


def update_configuration_file(container_name, config_name,
                              app_config_container_path, new_config):
    with open(config_name, "w") as config_file:
        json.dump(new_config, config_file, indent=4)
    copy_to_docker_container(container_name, config_name,
                             app_config_container_path)


def notify_imminent_server_migration(server_ip, destination_address,
                                     management_port, quic_protocol):
    if "Explicit" in quic_protocol:
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Explicit",
                              "address": destination_address})
    elif quic_protocol == "poolOfAddresses":
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Pool of Addresses"})
    elif quic_protocol == "symmetric":
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Symmetric"})
    elif quic_protocol == "synchronizedSymmetric":
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Synchronized Symmetric"})
    else:
        raise RuntimeError("Invalid QUIC migration protocol")

    logger.info("Notifying imminent server migration sending command {} "
                "to {}:{}".format(command, server_ip, management_port))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(command.encode(), (server_ip, management_port))

    logger.info("Waiting for the response")
    while True:
        message, address = sock.recvfrom(1024)
        message = message.decode()
        logger.info("Received message '{}' from {}:{}"
                    .format(message, *address))
        if message == "OK":
            return


def trigger_server_migration(container_migration_script_ip):
    command = "migrate"
    logger.info("Triggering server migration sending command {} to {}:{}"
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


def migrate_periodically_and_shutdown(session_duration, migration_frequency,
                                      first_server_ip, second_server_ip,
                                      server_app_port, server_management_port,
                                      quic_protocol, container_name):
    handover_timestamp_list = []
    migration_notification_timestamp_list = []
    migration_trigger_timestamp_list = []
    n_migrations = int(session_duration / migration_frequency)
    early_exit = False

    server_app_current_ip = first_server_ip
    server_source_current_ip = first_server_ip
    server_destination_current_ip = second_server_ip

    wait_time_after_each_migration = 180
    wait_time_after_migration_notification = 10
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

        # Wait for some minutes before triggering server migration and check if
        # the client container is still up and running. Due to packet loss,
        # client migration could fail (loss of path validation frames, which
        # are not retransmitted in mvfst).
        time.sleep(wait_time_after_each_migration)
        state = get_docker_container_state(container_name)
        if state == DockerContainerState.EXITED \
                or state == DockerContainerState.PAUSED:
            logger.error("Client application timed out after client handover. "
                         "Stopping run")
            early_exit = True
            break

        # Notify imminent server migration.
        destination_address = "{}:{}".format(server_destination_current_ip,
                                             server_app_port)
        notification_timestamp = time.time()
        notify_imminent_server_migration(server_app_current_ip,
                                         destination_address,
                                         server_management_port,
                                         quic_protocol)

        # Sleep for some seconds and send the migration trigger.
        time.sleep(wait_time_after_migration_notification)
        trigger_timestamp = time.time()
        trigger_server_migration(server_source_current_ip)

        # Update variables for next migrations.
        previous_source_ip = server_source_current_ip
        server_source_current_ip = server_destination_current_ip
        server_app_current_ip = server_destination_current_ip
        server_destination_current_ip = previous_source_ip

        migration_notification_timestamp_list.append(notification_timestamp)
        migration_trigger_timestamp_list.append(trigger_timestamp)

        # After a couple of minutes, and if this is not the last migration,
        # check if the server migration succeeded or not (again, due to packet
        # loss, the path validation could fail).
        if i != n_migrations - 1:
            time.sleep(wait_time_after_each_migration)
            state = get_docker_container_state(container_name)
            if state == DockerContainerState.EXITED \
                    or state == DockerContainerState.PAUSED:
                logger.error("Client application timed out after "
                             "server migration. Stopping run")
                early_exit = True
                break

    if not early_exit:
        # Wait for 5 minutes and end the experiment.
        time.sleep(wait_time_before_ending_experiment)
        send_shutdown(server_app_current_ip, server_management_port)
        send_shutdown(server_destination_current_ip, 19888)
    else:
        send_shutdown(server_app_current_ip, server_management_port)
        send_shutdown(server_source_current_ip, 19888)
        send_shutdown(server_destination_current_ip, 18863, tcp_socket=True)

    return handover_timestamp_list, migration_notification_timestamp_list, \
           migration_trigger_timestamp_list


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
    container_name = "mhq-client"
    docker_network = "docker_handover"
    logs_destination_path = "exp5_client_docker.out"

    config_file = "config.json"
    app_config_container_path = "/usr/src/app/proxygen/"

    service_times_file = "service_times.json"
    app_service_times_dump_container_path = \
        "/usr/src/app/proxygen/" + service_times_file

    results = {"experiment": [], "run": [], "repetition": [], "seed": [],
               "protocol": [], "clientMigrationFrequency [min]": [],
               "requestTimestamps [us]": [], "serviceTimes [us]": [],
               "serverAddresses": [], "handoverTimestamps [s]": [],
               "migrationNotificationTimestamps [s]": [],
               "migrationTriggerTimestamps [s]": []}

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
    config_and_frequency_list = generate_all_configs()

    for config, migration_frequency in config_and_frequency_list:
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

                send_shutdown(args.first_server_ip, args.management_port)
                send_shutdown(args.first_server_ip, 19888)
                send_shutdown(args.second_server_ip, 18863, tcp_socket=True)
                logger.info("Sleeping for 10 seconds before the next run")
                time.sleep(10)
                continue

            # Start the client container.
            start_client_container(container_name, docker_network, config_file,
                                   app_config_container_path, config,
                                   logs_destination_path, service_times_file)

            # Start periodic handovers followed by server migrations.
            handover_timestamps, migration_notification_timestamps, \
            migration_trigger_timestamps = \
                migrate_periodically_and_shutdown(
                    session_duration, migration_frequency,
                    args.first_server_ip, args.second_server_ip,
                    args.server_app_port, args.management_port,
                    config["experiment"]["serverMigrationProtocol"],
                    container_name)

            wait_for_client_termination(container_name)

            # Save the results.
            service_times = parse_service_times_dump(
                container_name, service_times_file,
                app_service_times_dump_container_path)

            save_service_times(results, service_times, run, i, config["seed"],
                               config["experiment"]["serverMigrationProtocol"],
                               migration_frequency,
                               handover_timestamps,
                               migration_notification_timestamps,
                               migration_trigger_timestamps)

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

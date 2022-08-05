import atexit
import argparse
import socket
import glob
import pandas as pd

from utils.oci import *
from utils.configuration import *

logger = logging.getLogger("client")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def exit_handler(container_names, console_socket_files,
                 console_socket_processes, results):
    stop_all_containers_and_console_sockets(container_names,
                                            console_socket_files,
                                            console_socket_processes)
    dump_experiment_results_to_file(results, call_from_exit_handler=True)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild_image", dest="rebuild_image",
                        action="store_true", default=False)
    parser.add_argument("--container_migration_script_ip", action="store",
                        type=str, dest="container_migration_script_ip",
                        required=True)
    parser.add_argument("--destination_address", action="store", type=str,
                        dest="destination_address", required=True)
    parser.add_argument("--server_ip", action="store", type=str,
                        dest="server_ip", required=True)
    parser.add_argument("--management_port", action="store", type=int,
                        dest="management_port", required=True)
    return parser.parse_args()


def build_oci_bundle(container_base_name, runc_base, app_config_container_path):
    logger.info("Building OCI bundle '{}'".format(container_base_name))
    remove_oci_image_in_working_dir()
    remove_oci_bundle_in_runc_dir(runc_base, container_base_name)
    generate_oci_bundle(container_base_name)
    modify_oci_bundle_config(container_base_name, AppMode.CLIENT,
                             app_config_container_path, vlog_level=3)
    move_oci_bundle_to_runc_dir(runc_base, container_base_name)


def generate_container_and_console_socket_names(runc_base, container_base_name,
                                                n_clients):
    container_names = [container_base_name + str(i)
                       for i in range(1, n_clients + 1)]
    console_socket_files = [runc_base + container_base_name +
                            "/console{}.sock".format(i)
                            for i in range(1, n_clients + 1)]
    return container_names, console_socket_files


def generate_all_configs(n_clients):
    combination_list = generate_experiment_combinations()
    config_path = "./baseconfigs/experiment4_client.json"
    config_list = []
    seed = 1

    for combination in combination_list:
        with open(config_path, "r") as config_file:
            config = json.load(config_file)
            config["seed"] = seed

            quic_protocol = combination[1]
            config["experiment"]["serverMigrationProtocol"] = quic_protocol

            request_interval = combination[3]
            if request_interval == 0:
                config["requestPattern"]["backToBack"] = True
            else:
                config["requestPattern"]["sporadic"] = True
                config["requestPattern"]["sporadicInterval"] = request_interval

            config_list.append(config)

        # Each client will have a different seed starting from the same base
        # configuration, so increment the seed by the number of clients for
        # each new base configuration.
        seed += n_clients

    return config_list


def update_configuration_file(runc_base, container_base_name,
                              app_config_container_path, config):
    app_config_path = runc_base + container_base_name + "/rootfs" + \
                      app_config_container_path
    with open(app_config_path, "w") as app_config_file:
        json.dump(config, app_config_file, indent=4)


def start_all_containers(runc_base, container_base_name, container_names,
                         console_socket_files, app_config_container_path,
                         config):
    console_socket_processes = []
    base_seed = config["seed"]

    for i, name in enumerate(container_names):
        config["seed"] = base_seed + i
        update_configuration_file(runc_base, container_base_name,
                                  app_config_container_path, config)

        console_socket_processes.append(
            start_console_socket(console_socket_files[i],
                                 suppress_output=False))
        start_container(runc_base, container_base_name, name,
                        console_socket_files[i], detached=True)

        # Wait a bit so that the container can be launched and
        # can parse the correct configuration.
        time.sleep(0.3)

    return console_socket_processes


def stop_all_containers_and_console_sockets(container_names,
                                            console_socket_files,
                                            console_socket_processes):
    for i in range(0, len(container_names)):
        cmd = "sudo runc kill {} KILL".format(container_names[i])
        while True:
            # Repeatedly try to kill the container until the command succeeds.
            logger.info("Running '{}'".format(cmd))
            os.system(cmd)
            runc_list_cmd = "sudo runc list -f json"
            runc_list_cmd_output = subprocess.run(runc_list_cmd,
                                                  stdout=subprocess.PIPE,
                                                  shell=True).stdout.decode()
            if runc_list_cmd_output == "null":
                break
            container_list = json.loads(runc_list_cmd_output)
            client = next((container for container in container_list if
                           container["id"] == container_names[i]), None)
            if client is None or client["status"] == "stopped":
                break
            time.sleep(0.2)

        cmd = "sudo runc delete " + container_names[i]
        logger.info("Running '{}'".format(cmd))
        os.system(cmd)

        stop_console_socket(console_socket_processes[i],
                            console_socket_files[i])


def notify_imminent_server_migration(server_ip, destination_address,
                                     management_port, protocol):
    if "Explicit" in protocol:
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Explicit",
                              "address": destination_address})
    elif protocol == "poolOfAddresses":
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Pool of Addresses"})
    elif protocol == "symmetric":
        command = json.dumps({"action": "onImminentServerMigration",
                              "protocol": "Symmetric"})
    elif protocol == "synchronizedSymmetric":
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


def wait_for_all_clients_termination(container_names):
    logger.info("Waiting for the termination of all the clients")
    cmd = "sudo runc list -f json"
    while True:
        cmd_output = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    shell=True).stdout.decode()

        if cmd_output == "null":
            logger.info("All the clients terminated")
            break

        container_list = json.loads(cmd_output)
        not_terminated = len(container_names)

        for name in container_names:
            client = next((container for container in container_list if
                           container["id"] == name), None)

            if client is None or client["status"] == "stopped":
                not_terminated -= 1

        if not_terminated == 0:
            logger.info("All the clients terminated")
            break

        time.sleep(2)


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


def parse_and_delete_service_times_dump(runc_base, container_name,
                                        app_service_times_dump_container_path):
    app_dump_path = runc_base + container_name + "/rootfs" + \
                    app_service_times_dump_container_path
    dump_files = glob.glob(app_dump_path)
    service_times_list = []

    for dump_file in dump_files:
        try:
            with open(dump_file, "r") as app_service_times_file:
                service_times_list.append(json.load(app_service_times_file))
            os.remove(dump_file)
        except:
            logger.error("Cannot parse the service times dump file")

    return service_times_list


def save_service_times(results, service_times_list, run, n_clients,
                       migration_notification_timestamp,
                       migration_trigger_timestamp, quic_protocol,
                       request_pattern):
    request_interval = 0 if request_pattern["backToBack"] \
        else request_pattern["sporadicInterval"]

    for service_times in service_times_list:
        results["experiment"].append(4)
        results["run"].append(run)
        results["seedClient"].append(service_times.get("seed", None))
        results["numberOfClients"].append(n_clients)
        results["protocol"].append(quic_protocol)
        results["intervalBetweenRequests"].append(request_interval)
        results["requestTimestamps [us]"] \
            .append(service_times.get("requestTimestamps", None))
        results["serviceTimes [us]"] \
            .append(service_times.get("serviceTimes", None))
        results["serverAddresses"] \
            .append(service_times.get("serverAddresses", None))
        results["connectionEndedDueToTimeout"] \
            .append(service_times.get("connectionEndedDueToTimeout", None))
        results["migrationNotificationTimestamp [ms]"] \
            .append(migration_notification_timestamp)
        results["migrationTriggerTimestamp [ms]"] \
            .append(migration_trigger_timestamp)


def dump_experiment_results_to_file(results, call_from_exit_handler=False):
    df = pd.DataFrame(results)
    if call_from_exit_handler is True:
        results_file = "experiment4_service_times.bak.csv"
    else:
        results_file = "experiment4_service_times.csv"
    df.to_csv(results_file, encoding="utf-8", index=False)


def main():
    args = parse_arguments()
    container_base_name = "mhq-client"
    runc_base = "/runc/containers/"
    app_config_container_path = "/usr/src/app/proxygen/config.json"
    app_service_times_dump_container_path = \
        "/usr/src/app/proxygen/service_times*.json"

    if args.rebuild_image or not os.path.isdir(runc_base + container_base_name):
        build_oci_bundle(container_base_name, runc_base,
                         app_config_container_path)

    results = {"experiment": [], "run": [], "seedClient": [],
               "numberOfClients": [], "protocol": [],
               "intervalBetweenRequests": [],
               "requestTimestamps [us]": [], "serviceTimes [us]": [],
               "serverAddresses": [], "connectionEndedDueToTimeout": [],
               "migrationNotificationTimestamp [ms]": [],
               "migrationTriggerTimestamp [ms]": []}

    # Times in seconds used to drive the experiment events.
    sleep_before_imminent_migration = 90
    sleep_before_migration_trigger = 10

    run = 1
    n_clients = 30
    config_list = generate_all_configs(n_clients)
    container_names, console_socket_files = \
        generate_container_and_console_socket_names(runc_base,
                                                    container_base_name,
                                                    n_clients)
    for config in config_list:
        logger.info("New experiment run with configuration\n{}"
                    .format(json.dumps(config, indent=4)))

        # Start all the client containers in detached mode.
        console_socket_processes = \
            start_all_containers(runc_base, container_base_name,
                                 container_names, console_socket_files,
                                 app_config_container_path, config)

        # Handler used to stop the console sockets and
        # the containers if a failure occurs.
        atexit.unregister(exit_handler)
        atexit.register(exit_handler, container_names,
                        console_socket_files, console_socket_processes, results)

        # Wait and notify the imminent migration.
        time.sleep(sleep_before_imminent_migration)
        migration_notification_timestamp = time.time()
        notify_imminent_server_migration(
            args.server_ip,
            args.destination_address,
            args.management_port,
            config["experiment"]["serverMigrationProtocol"])

        # Wait and trigger the migration.
        time.sleep(sleep_before_migration_trigger)
        migration_trigger_timestamp = time.time()
        trigger_server_migration(args.container_migration_script_ip)

        # Wait for all the clients to stop and end the experiment.
        wait_for_all_clients_termination(container_names)
        send_shutdown(args.destination_address.split(":")[0],
                      args.management_port)
        send_shutdown(args.container_migration_script_ip, 19888)

        # Save results.
        service_times_list = parse_and_delete_service_times_dump(
            runc_base, container_base_name,
            app_service_times_dump_container_path)

        if len(service_times_list) != n_clients:
            logger.error("Found {} service times files instead of {}"
                         .format(len(service_times_list), n_clients))

        save_service_times(results, service_times_list, run, n_clients,
                           migration_notification_timestamp,
                           migration_trigger_timestamp,
                           config["experiment"]["serverMigrationProtocol"],
                           config["requestPattern"])

        # Force console sockets and containers
        # to stop at the end of the run.
        logger.info("End of an experiment run: stopping console "
                    "sockets and containers, if still up")
        stop_all_containers_and_console_sockets(container_names,
                                                console_socket_files,
                                                console_socket_processes)

        # Sleep before starting a new run.
        logger.info("Sleeping for 10 seconds before the next run")
        time.sleep(10)
        run += 1

    logger.info("Ending the experiment")
    dump_experiment_results_to_file(results)


if __name__ == "__main__":
    main()

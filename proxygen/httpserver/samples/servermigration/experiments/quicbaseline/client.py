import atexit
import argparse
import pandas as pd

from utils.oci import *

logger = logging.getLogger("client")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def exit_handler(container_name, total_service_times):
    # Possibly stop the client container and free the occupied resources.
    cmd = "sudo runc kill {} KILL".format(container_name)
    logger.info("Running '{}'".format(cmd))
    os.system(cmd)

    cmd = "sudo runc delete " + container_name
    logger.info("Running '{}'".format(cmd))
    os.system(cmd)

    dump_experiment_results_to_file(total_service_times,
                                    call_from_exit_handler=True)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild_image",
                        dest="rebuild_image", action="store_true",
                        default=False)
    parser.add_argument("--repetitions", dest="repetitions", action="store",
                        required=True, type=int)
    return parser.parse_args()


def build_oci_bundle(container_name, runc_base, app_config_container_path):
    logger.info("Building OCI bundle '{}'".format(container_name))
    remove_oci_image_in_working_dir()
    remove_oci_bundle_in_runc_dir(runc_base, container_name)
    generate_oci_bundle(container_name)
    modify_oci_bundle_config(container_name, AppMode.CLIENT,
                             app_config_container_path, vlog_level=3)
    move_oci_bundle_to_runc_dir(runc_base, container_name)


def parse_base_config():
    config_path = "./base_configs/experiment0_client.json"
    with open(config_path, "r") as base_config_file:
        return json.load(base_config_file)


def update_configuration_file(runc_base, container_name,
                              app_config_container_path, new_config):
    app_config_path = runc_base + container_name + "/rootfs" + \
                      app_config_container_path
    with open(app_config_path, "w") as app_config_file:
        json.dump(new_config, app_config_file, indent=4)


def parse_and_delete_service_times_dump(runc_base, container_name,
                                        app_service_times_dump_container_path):
    app_dump_path = runc_base + container_name + "/rootfs" + \
                    app_service_times_dump_container_path
    try:
        with open(app_dump_path, "r") as app_service_times_file:
            service_times = json.load(app_service_times_file)
        os.remove(app_dump_path)
        return service_times
    except:
        logger.error("Cannot parse the service times dump file")
        return None


def save_service_times(total_service_times, service_times, repetition, seed):
    if service_times is None:
        return
    total_service_times["experiment"].append(0)
    total_service_times["repetition"].append(repetition)
    total_service_times["seed"].append(seed)
    total_service_times["serviceTimes [us]"] \
        .append(service_times["serviceTimes"])


def dump_experiment_results_to_file(total_service_times,
                                    call_from_exit_handler=False):
    if call_from_exit_handler is True:
        file_name = "experiment0_service_times.bak.csv"
    else:
        file_name = "experiment0_service_times.csv"
    df = pd.DataFrame(total_service_times)
    df.to_csv(file_name, encoding="utf-8", index=False)


def main():
    args = parse_arguments()
    container_name = "mhq-client"
    runc_base = "/runc/containers/"
    app_config_container_path = "/usr/src/app/proxygen/config.json"
    app_service_times_dump_container_path = \
        "/usr/src/app/proxygen/service_times.json"
    base_config = parse_base_config()
    total_service_times = {"experiment": [], "repetition": [], "seed": [],
                           "serviceTimes [us]": []}

    # Handler used to stop the client container if a failure occurs.
    atexit.register(exit_handler, container_name, total_service_times)

    if args.rebuild_image or not os.path.isdir(runc_base + container_name):
        build_oci_bundle(container_name, runc_base, app_config_container_path)

    seed = 0
    n_repetitions = args.repetitions

    for repetition in range(1, n_repetitions + 1):
        seed += 1
        base_config["seed"] = seed
        logger.info("New experiment run. Repetition: {}, configuration\n{}"
                    .format(repetition, json.dumps(base_config, indent=4)))

        # Update the configuration file used by the application.
        update_configuration_file(runc_base, container_name,
                                  app_config_container_path, base_config)

        # This method ends only when the client application
        # (and so the container) stops its execution.
        start_container(runc_base, container_name)

        # Parse the service times dumped by the proxygen client and
        # add them to the collection of service times.
        service_times = parse_and_delete_service_times_dump(runc_base,
                                                            container_name,
                                                            app_service_times_dump_container_path)
        save_service_times(total_service_times, service_times, repetition, seed)

        # Sleep before starting a new run. The time should be large enough
        # for the migration scripts to resume before this script.
        logger.info("Sleeping for 10 seconds before the next run")
        time.sleep(10)

    logger.info("Ending the experiment")
    dump_experiment_results_to_file(total_service_times)


if __name__ == "__main__":
    main()

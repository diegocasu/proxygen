import json
import sys
import logging
import pandas as pd

from utils.migrate_server_source import MigrationTechnique

logger = logging.getLogger("client_experiment")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class ClientExperimentManager:
    def __init__(self, experiment_id, n_repetitions):
        # The id identifies the experiment (first, second, third, fourth).
        # An experiment is composed by multiple runs, each one identified by a
        # particular combination of parameters (migration protocol, request
        # pattern, etc.), thus by a particular configuration file.
        # Each run is performed multiple times to gather significant
        # measurements.
        self._id = experiment_id
        self._current_run = 0
        self._current_repetition = 0
        self._current_seed = 0
        self._n_repetitions_per_run = n_repetitions

        if self._id == 1:
            self._initialize_first_experiment()
        elif self._id == 2:
            self._initialize_second_experiment()

        # Check that the given experiment ID and
        # the one of the configuration match.
        if self._current_config["experiment"]["id"] != self._id:
            logger.error("The given experiment ID and the configuration "
                         "experiment ID do not match. Exiting")
            sys.exit(1)

    def _parse_base_config(self, config_name):
        config_path = "./baseconfigs/" + config_name
        with open(config_path, "r") as base_config_file:
            self._current_config = json.load(base_config_file)

    def _initialize_first_experiment(self):
        self._parse_base_config("experiment1_client.json")
        self._migration_protocols_sequence = \
            ["proactiveExplicit",
             "reactiveExplicit",
             "poolOfAddresses",  # Pool size equal to 1
             "poolOfAddresses",  # Pool size equal to 2
             "poolOfAddresses",  # Pool size equal to 3
             "symmetric"]

        self._results = {"experiment": [], "run": [], "repetition": [],
                         "seed": [], "serviceTimes [us]": [],
                         "serverAddresses": [],
                         "firstRequestAfterMigrationTriggered": []}
        self._results_file = "experiment1_service_times.csv"

    def _initialize_second_experiment(self):
        self._parse_base_config("experiment2_client.json")
        self._migration_protocols_sequence = \
            ["proactiveExplicit",
             "reactiveExplicit",
             "poolOfAddresses",  # Pool size equal to 3
             "symmetric"]
        self._current_migration_protocols_sequence = None

        self._n_migration_techniques = len(MigrationTechnique)
        self._current_migration_technique = 0

        self._n_container_memory_inflations = len([0, 10, 50, 100])
        self._current_container_memory_inflation = 0

        self._results = {"experiment": [], "run": [], "repetition": [],
                         "seed": [], "serviceTimes [us]": [],
                         "serverAddresses": [],
                         "firstRequestAfterMigrationTriggered": []}
        self._results_file = "experiment2_service_times.csv"

    def _get_new_config_first_experiment(self):
        if self._current_repetition >= self._n_repetitions_per_run \
                or self._current_run == 0:
            if not self._migration_protocols_sequence:
                # All the configurations have been crafted,
                # so end the experiment.
                return None

            self._current_run += 1
            self._current_repetition = 1
            self._current_seed += 1

            self._current_config["experiment"]["serverMigrationProtocol"] = \
                self._migration_protocols_sequence.pop(0)
            self._current_config["seed"] = self._current_seed
            return self._current_config

        self._current_repetition += 1
        self._current_seed += 1
        self._current_config["seed"] = self._current_seed
        return self._current_config

    def _get_new_config_second_experiment(self):
        if self._current_repetition >= self._n_repetitions_per_run \
                or self._current_run == 0:
            if self._current_run == 0:
                self._current_container_memory_inflation += 1
                self._current_migration_protocols_sequence = \
                    self._migration_protocols_sequence.copy()
                self._current_config["experiment"]["serverMigrationProtocol"] = \
                    self._current_migration_protocols_sequence.pop(0)

            self._current_run += 1
            self._current_repetition = 1
            self._current_seed += 1
            self._current_migration_technique += 1

            if self._current_migration_technique > self._n_migration_techniques:
                if not self._current_migration_protocols_sequence:
                    self._current_container_memory_inflation += 1
                    if self._current_container_memory_inflation > \
                            self._n_container_memory_inflations:
                        # All the configurations have been crafted,
                        # so end the experiment.
                        return None
                    self._current_migration_protocols_sequence = \
                        self._migration_protocols_sequence.copy()

                self._current_migration_technique = 1
                self._current_config["experiment"]["serverMigrationProtocol"] = \
                    self._current_migration_protocols_sequence.pop(0)

            self._current_config["seed"] = self._current_seed
            return self._current_config

        self._current_repetition += 1
        self._current_seed += 1
        self._current_config["seed"] = self._current_seed
        return self._current_config

    def get_new_config(self):
        if self._id == 1:
            return self._get_new_config_first_experiment()
        elif self._id == 2:
            return self._get_new_config_second_experiment()

        return None

    def save_service_times(self, service_times):
        self._results["experiment"].append(self._id)
        self._results["run"].append(self._current_run)
        self._results["repetition"].append(self._current_repetition)
        self._results["seed"].append(self._current_seed)
        self._results["serviceTimes [us]"] \
            .append(service_times.get("serviceTimes", None))
        self._results["serverAddresses"] \
            .append(service_times.get("serverAddresses", None))
        self._results["firstRequestAfterMigrationTriggered"] \
            .append(service_times
                    .get("firstRequestAfterMigrationTriggered", None))

    def dump_experiment_results_to_file(self, call_from_exit_handler=False):
        df = pd.DataFrame(self._results)
        if call_from_exit_handler is True:
            results_file = self._results_file.rsplit(".")[0] + ".bak.csv"
            df.to_csv(results_file, encoding="utf-8", index=False)
        else:
            df.to_csv(self._results_file, encoding="utf-8", index=False)

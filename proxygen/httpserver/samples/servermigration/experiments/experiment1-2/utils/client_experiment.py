import json
import sys
import pandas as pd

from utils.migrate_server_source import MigrationTechnique


class ClientExperimentManager:
    def __init__(self, experiment_id):
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
        self._n_repetitions_per_run = 10

        if self._id == 1:
            self._initialize_first_experiment()
        elif self._id == 2:
            self._initialize_second_experiment()

        # Check that the given experiment ID and
        # the one of the configuration match.
        if self._current_config["experiment"]["id"] != self._id:
            print("The given experiment ID and the configuration "
                  "experiment ID do not match. Exiting")
            sys.exit(1)

    def _parse_base_config(self, config_name):
        config_path = "./base_configs/" + config_name
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
                         "serverAddresses": []}
        self._results_file = "experiment1_service_times.csv"

    def _initialize_second_experiment(self):
        self._parse_base_config("experiment2_client.json")
        self._migration_protocols_sequence = \
            ["proactiveExplicit",
             "reactiveExplicit",
             "poolOfAddresses",  # Pool size equal to 3
             "symmetric"]

        # Use the same protocol with all the migration techniques.
        self._n_migration_techniques = len(MigrationTechnique)
        self._current_migration_technique = 0

        self._results = {"experiment": [], "run": [], "repetition": [],
                         "seed": [], "serviceTimes [us]": [],
                         "serverAddresses": []}
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
                self._current_config["experiment"]["serverMigrationProtocol"] = \
                    self._migration_protocols_sequence.pop(0)

            self._current_run += 1
            self._current_repetition = 1
            self._current_seed += 1
            self._current_migration_technique += 1

            if self._current_migration_technique > self._n_migration_techniques:
                if not self._migration_protocols_sequence:
                    # All the configurations have been crafted,
                    # so end the experiment.
                    return None

                self._current_migration_technique = 1
                self._current_config["experiment"]["serverMigrationProtocol"] = \
                    self._migration_protocols_sequence.pop(0)

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

    def _save_service_times_first_experiment(self, service_times):
        self._results["experiment"].append(self._id)
        self._results["run"].append(self._current_run)
        self._results["repetition"].append(self._current_repetition)
        self._results["seed"].append(self._current_seed)
        self._results["serviceTimes [us]"].append(service_times["serviceTimes"])
        self._results["serverAddresses"] \
            .append(service_times["serverAddresses"])

    def _save_service_times_second_experiment(self, service_times):
        self._results["experiment"].append(self._id)
        self._results["run"].append(self._current_run)
        self._results["repetition"].append(self._current_repetition)
        self._results["seed"].append(self._current_seed)
        self._results["serviceTimes [us]"].append(service_times["serviceTimes"])
        self._results["serverAddresses"] \
            .append(service_times["serverAddresses"])

    def save_service_times(self, service_times):
        if self._id == 1:
            self._save_service_times_first_experiment(service_times)
        elif self._id == 2:
            self._save_service_times_second_experiment(service_times)

    def dump_experiment_results_to_file(self):
        df = pd.DataFrame(self._results)
        df.to_csv(self._results_file, encoding="utf-8", index=False)

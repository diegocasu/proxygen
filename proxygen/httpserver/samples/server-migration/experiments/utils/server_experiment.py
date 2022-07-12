import json
import sys
import pandas as pd

from utils.migrate_server_source import MigrationTechnique


class ServerExperimentManager:
    def __init__(self, experiment_id, destination_ip):
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
            self._initialize_first_experiment(destination_ip)

            # Consistency check.
            if len(self._base_address_pool) != 2 \
                    or self._destination_address is None:
                print("Wrong base configuration for address pool")
                sys.exit(1)

        elif self._id == 2:
            self._initialize_second_experiment()

            # Consistency check.
            if len(self._current_config["serverMigration"]["addressPool"]) != 3:
                print("Wrong base configuration for address pool. "
                      "It must be composed of 3 addresses")

    def _parse_base_config(self, config_name):
        config_path = "./base_configs/" + config_name
        with open(config_path, "r") as base_config_file:
            self._current_config = json.load(base_config_file)

    def _initialize_first_experiment(self, destination_ip):
        self._parse_base_config("experiment1_server_source.json")
        self._migration_protocols_sequence = \
            ["proactiveExplicit",
             "reactiveExplicit",
             "poolOfAddresses1",  # Pool size equal to 1
             "poolOfAddresses2",  # Pool size equal to 2
             "poolOfAddresses3",  # Pool size equal to 3
             "symmetric"]
        self._current_migration_protocol = None
        self._migration_technique = MigrationTechnique.COLD

        self._base_address_pool = []
        self._current_address_pool = []
        self._destination_address = None
        for address in self._current_config["serverMigration"]["addressPool"]:
            ip, port = address.split(":")
            if ip != destination_ip:
                self._base_address_pool.append(address)
            else:
                self._destination_address = address

        self._results = {"experiment": [], "run": [], "repetition": [],
                         "seed": [], "migrationTechnique": [], "protocol": [],
                         "preDumpTime [s]": [], "preDumpTxTime [s]": [],
                         "dumpTime [s]": [], "dumpTxTime [s]": [],
                         "dumpSize": [], "preDumpSize": []}
        self._results_file = "experiment1_migration_times.csv"

    def _initialize_second_experiment(self):
        self._parse_base_config("experiment2_server_source.json")
        self._migration_protocols_sequence = \
            ["proactiveExplicit",
             "reactiveExplicit",
             "poolOfAddresses3",  # Pool size equal to 3
             "symmetric"]
        self._current_migration_protocol = None

        self._migration_techniques = [e for e in MigrationTechnique]
        self._current_migration_technique = None

        self._results = {"experiment": [], "run": [], "repetition": [],
                         "seed": [], "migrationTechnique": [], "protocol": [],
                         "preDumpTime [s]": [], "preDumpTxTime [s]": [],
                         "dumpTime [s]": [], "dumpTxTime [s]": [],
                         "dumpSize": [], "preDumpSize": []}
        self._results_file = "experiment2_migration_times.csv"

    def _get_new_config_first_experiment(self):
        if self._current_repetition >= self._n_repetitions_per_run \
                or self._current_run == 0:
            if not self._migration_protocols_sequence:
                # All the configurations have been crafted,
                # so end the experiment.
                return None, None

            self._current_run += 1
            self._current_repetition = 1
            self._current_seed += 1

            self._current_config["seed"] = self._current_seed
            migration_protocols = self._current_config["serverMigration"]

            self._current_migration_protocol = \
                self._migration_protocols_sequence.pop(0)
            next_protocol = self._current_migration_protocol
            if "Explicit" in next_protocol:
                next_protocol = "explicit"
            elif "poolOfAddresses" in next_protocol:
                next_protocol = "poolOfAddresses"
                if not self._current_address_pool:  # Empty pool
                    self._current_address_pool.append(self._destination_address)
                else:
                    self._current_address_pool \
                        .append(self._base_address_pool.pop(0))
                migration_protocols["addressPool"] = self._current_address_pool

            # Enable only the migration protocol required by the run.
            for protocol in migration_protocols:
                if protocol == "enable" or protocol == "addressPool":
                    continue
                if protocol == next_protocol:
                    migration_protocols[protocol] = True
                else:
                    migration_protocols[protocol] = False

            return self._current_config, self._migration_technique

        self._current_repetition += 1
        self._current_seed += 1
        self._current_config["seed"] = self._current_seed
        return self._current_config, self._migration_technique

    def _get_new_config_second_experiment(self):
        if self._current_repetition >= self._n_repetitions_per_run \
                or self._current_run == 0:
            self._current_run += 1
            self._current_repetition = 1
            self._current_seed += 1

            self._current_config["seed"] = self._current_seed

            if not self._migration_techniques or self._current_run == 1:
                if not self._migration_protocols_sequence:
                    # All the configurations have been crafted,
                    # so end the experiment.
                    return None, None

                self._migration_techniques = [e for e in MigrationTechnique]
                self._current_migration_technique = \
                    self._migration_techniques.pop(0)

                migration_protocols = self._current_config["serverMigration"]
                self._current_migration_protocol = \
                    self._migration_protocols_sequence.pop(0)

                next_protocol = self._current_migration_protocol
                if "Explicit" in next_protocol:
                    next_protocol = "explicit"
                elif "poolOfAddresses" in next_protocol:
                    next_protocol = "poolOfAddresses"

                # Enable only the migration protocol required by the run.
                for protocol in migration_protocols:
                    if protocol == "enable" or protocol == "addressPool":
                        continue
                    if protocol == next_protocol:
                        migration_protocols[protocol] = True
                    else:
                        migration_protocols[protocol] = False
            else:
                self._current_migration_technique = \
                    self._migration_techniques.pop(0)

            return self._current_config, self._current_migration_technique

        self._current_repetition += 1
        self._current_seed += 1
        self._current_config["seed"] = self._current_seed
        return self._current_config, self._current_migration_technique

    def get_new_config(self):
        if self._id == 1:
            return self._get_new_config_first_experiment()
        elif self._id == 2:
            return self._get_new_config_second_experiment()

        return None, None

    def _save_migration_measurements_first_experiment(self, migration_times):
        self._results["experiment"].append(self._id)
        self._results["run"].append(self._current_run)
        self._results["repetition"].append(self._current_repetition)
        self._results["seed"].append(self._current_seed)
        self._results["migrationTechnique"] \
            .append(str(self._migration_technique.name).lower())
        self._results["protocol"].append(self._current_migration_protocol)
        self._results["preDumpTime [s]"].append(migration_times["preDumpTime"])
        self._results["preDumpTxTime [s]"] \
            .append(migration_times["preDumpTxTime"])
        self._results["dumpTime [s]"].append(migration_times["dumpTime"])
        self._results["dumpTxTime [s]"].append(migration_times["dumpTxTime"])
        self._results["dumpSize"].append(migration_times["dumpSize"])
        self._results["preDumpSize"].append(migration_times["preDumpSize"])

    def _save_migration_measurements_second_experiment(self, migration_times):
        self._results["experiment"].append(self._id)
        self._results["run"].append(self._current_run)
        self._results["repetition"].append(self._current_repetition)
        self._results["seed"].append(self._current_seed)
        self._results["migrationTechnique"] \
            .append(str(self._migration_technique.name).lower())
        self._results["protocol"].append(self._current_migration_protocol)
        self._results["preDumpTime [s]"].append(migration_times["preDumpTime"])
        self._results["preDumpTxTime [s]"] \
            .append(migration_times["preDumpTxTime"])
        self._results["dumpTime [s]"].append(migration_times["dumpTime"])
        self._results["dumpTxTime [s]"].append(migration_times["dumpTxTime"])
        self._results["dumpSize"].append(migration_times["dumpSize"])
        self._results["preDumpSize"].append(migration_times["preDumpSize"])

    def save_migration_measurements(self, migration_times):
        if self._id == 1:
            self._save_migration_measurements_first_experiment(migration_times)
        elif self._id == 2:
            self._save_migration_measurements_second_experiment(migration_times)

    def dump_experiment_results_to_file(self):
        df = pd.DataFrame(self._results)
        df.to_csv(self._results_file, encoding="utf-8", index=False)

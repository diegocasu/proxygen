import json
import sys
import logging
import pandas as pd

from utils.migrate_server_source import MigrationTechnique

logger = logging.getLogger("server_experiment")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class ServerExperimentManager:
    def __init__(self, experiment_id, destination_ip, n_repetitions):
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
            self._initialize_first_experiment(destination_ip)

            # Consistency check.
            if len(self._base_address_pool) != 2 \
                    or self._destination_address is None:
                logger.error("Wrong base configuration for address pool")
                sys.exit(1)

        elif self._id == 2:
            self._initialize_second_experiment()

            # Consistency check.
            if len(self._current_config["serverMigration"]["addressPool"]) != 3:
                logger.error("Wrong base configuration for address pool. "
                             "It must be composed of 3 addresses")

    def _parse_base_config(self, config_name):
        config_path = "./baseconfigs/" + config_name
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
        self._current_migration_technique = MigrationTechnique.COLD
        self._current_memory_inflation = 0

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
                         "memoryFootprintInflation [MB]": [],
                         "preDumpTime [s]": [], "preDumpTxTime [s]": [],
                         "dumpTime [s]": [], "dumpTxTime [s]": [],
                         "dumpSize": [], "preDumpSize": [],
                         "compressionEnabled": [],
                         "rsyncPreDumpTotalFileSize": [],
                         "rsyncPreDumpTotalBytesSent": [],
                         "rsyncPreDumpTransferRate": [],
                         "rsyncPreDumpCompressionSpeedup": [],
                         "rsyncDumpTotalFileSize": [],
                         "rsyncDumpTotalBytesSent": [],
                         "rsyncDumpTransferRate": [],
                         "rsyncDumpCompressionSpeedup": []}
        self._results_file = "experiment1_migration_times.csv"

    def _initialize_second_experiment(self):
        self._parse_base_config("experiment2_server_source.json")
        self._migration_protocols_sequence = \
            ["proactiveExplicit",
             "reactiveExplicit",
             "poolOfAddresses3",  # Pool size equal to 3
             "symmetric"]
        self._migration_protocols_sequence_in_this_run = None
        self._current_migration_protocol = None

        self._migration_techniques = [e for e in MigrationTechnique]
        self._migration_techniques_in_this_run = None
        self._current_migration_technique = None

        self._container_memory_inflations = [0, 10, 50, 100]  # Megabytes
        self._current_memory_inflation = None

        self._results = {"experiment": [], "run": [], "repetition": [],
                         "seed": [], "migrationTechnique": [], "protocol": [],
                         "memoryFootprintInflation [MB]": [],
                         "preDumpTime [s]": [], "preDumpTxTime [s]": [],
                         "dumpTime [s]": [], "dumpTxTime [s]": [],
                         "dumpSize": [], "preDumpSize": [],
                         "compressionEnabled": [],
                         "rsyncPreDumpTotalFileSize": [],
                         "rsyncPreDumpTotalBytesSent": [],
                         "rsyncPreDumpTransferRate": [],
                         "rsyncPreDumpCompressionSpeedup": [],
                         "rsyncDumpTotalFileSize": [],
                         "rsyncDumpTotalBytesSent": [],
                         "rsyncDumpTransferRate": [],
                         "rsyncDumpCompressionSpeedup": []}
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

            return self._current_config, self._current_migration_technique

        self._current_repetition += 1
        self._current_seed += 1
        self._current_config["seed"] = self._current_seed
        return self._current_config, self._current_migration_technique

    def _get_new_config_second_experiment(self):
        if self._current_repetition >= self._n_repetitions_per_run \
                or self._current_run == 0:
            self._current_run += 1
            self._current_repetition = 1
            self._current_seed += 1
            self._current_config["seed"] = self._current_seed

            if not self._migration_techniques_in_this_run:
                if not self._migration_protocols_sequence_in_this_run:
                    if not self._container_memory_inflations:
                        # All the configurations have been crafted,
                        # so end the experiment.
                        return None, None
                    self._migration_protocols_sequence_in_this_run = \
                        self._migration_protocols_sequence.copy()
                    self._current_memory_inflation = \
                        self._container_memory_inflations.pop(0)
                    self._current_config["memoryFootprintInflation"][
                        "additionalBytes"] = \
                        self._current_memory_inflation * 1024 * 1024

                self._migration_techniques_in_this_run = \
                    self._migration_techniques.copy()
                self._current_migration_technique = \
                    self._migration_techniques_in_this_run.pop(0)

                migration_protocols = self._current_config["serverMigration"]
                self._current_migration_protocol = \
                    self._migration_protocols_sequence_in_this_run.pop(0)

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
                    self._migration_techniques_in_this_run.pop(0)

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

    def save_migration_measurements(self, migration_times, compression_enabled):
        self._results["experiment"].append(self._id)
        self._results["run"].append(self._current_run)
        self._results["repetition"].append(self._current_repetition)
        self._results["seed"].append(self._current_seed)
        self._results["migrationTechnique"] \
            .append(self._current_migration_technique.to_camel_case_string())
        self._results["protocol"].append(self._current_migration_protocol)
        self._results["memoryFootprintInflation [MB]"] \
            .append(self._current_memory_inflation)
        self._results["preDumpTime [s]"] \
            .append(migration_times.get("preDumpTime", None))
        self._results["preDumpTxTime [s]"] \
            .append(migration_times.get("preDumpTxTime", None))
        self._results["dumpTime [s]"] \
            .append(migration_times.get("dumpTime", None))
        self._results["dumpTxTime [s]"] \
            .append(migration_times.get("dumpTxTime", None))
        self._results["dumpSize"] \
            .append(migration_times.get("dumpSize", None))
        self._results["preDumpSize"] \
            .append(migration_times.get("preDumpSize", None))
        self._results["compressionEnabled"].append(compression_enabled)
        self._results["rsyncPreDumpTotalFileSize"] \
            .append(migration_times.get("rsyncPreDumpTotalFileSize", None))
        self._results["rsyncPreDumpTotalBytesSent"] \
            .append(migration_times.get("rsyncPreDumpTotalBytesSent", None))
        self._results["rsyncPreDumpTransferRate"] \
            .append(migration_times.get("rsyncPreDumpTransferRate", None))
        self._results["rsyncPreDumpCompressionSpeedup"] \
            .append(migration_times.get("rsyncPreDumpCompressionSpeedup", None))
        self._results["rsyncDumpTotalFileSize"] \
            .append(migration_times.get("rsyncDumpTotalFileSize", None))
        self._results["rsyncDumpTotalBytesSent"] \
            .append(migration_times.get("rsyncDumpTotalBytesSent", None))
        self._results["rsyncDumpTransferRate"] \
            .append(migration_times.get("rsyncDumpTransferRate", None))
        self._results["rsyncDumpCompressionSpeedup"] \
            .append(migration_times.get("rsyncDumpCompressionSpeedup", None))

    def dump_experiment_results_to_file(self, call_from_exit_handler=False):
        df = pd.DataFrame(self._results)
        if call_from_exit_handler is True:
            results_file = self._results_file.rsplit(".")[0] + ".bak.csv"
            df.to_csv(results_file, encoding="utf-8", index=False)
        else:
            df.to_csv(self._results_file, encoding="utf-8", index=False)

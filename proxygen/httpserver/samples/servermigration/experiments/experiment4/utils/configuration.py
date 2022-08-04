import itertools

from utils.migrate_server_source import MigrationTechnique


def generate_experiment_combinations():
    container_dimensions = [0, 10, 50, 100]
    quic_protocols = ["reactiveExplicit", "poolOfAddresses", "symmetric"]
    migration_techniques = list(MigrationTechnique)

    # Throughputs in milliseconds. -1 means maximum possible (back to back).
    throughputs = [-1, 260, 1000]

    return list(itertools.product(container_dimensions, quic_protocols,
                                  migration_techniques, throughputs))

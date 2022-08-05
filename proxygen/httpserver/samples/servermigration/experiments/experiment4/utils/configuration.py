import itertools

from utils.migrate_server_source import MigrationTechnique


def generate_experiment_combinations():
    container_dimensions = [0, 10, 50, 100]
    quic_protocols = ["reactiveExplicit", "poolOfAddresses", "symmetric"]
    migration_techniques = list(MigrationTechnique)

    # Request intervals in milliseconds, where 0 means back-to-back requests.
    request_intervals = [0, 260, 1000]

    return list(itertools.product(container_dimensions, quic_protocols,
                                  migration_techniques, request_intervals))

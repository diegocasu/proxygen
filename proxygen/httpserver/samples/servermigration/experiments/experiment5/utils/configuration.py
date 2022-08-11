import itertools


def generate_experiment_combinations():
    migration_frequencies = [10, 30]  # Minutes
    quic_protocols = ["reactiveExplicit", "symmetric"]
    return list(itertools.product(migration_frequencies, quic_protocols))

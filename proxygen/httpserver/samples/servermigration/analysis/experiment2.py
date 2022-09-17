import os
import time
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


def parse_dataset(dataset_paths):
    def custom_eval(x):
        return np.NaN if x == "" else pd.eval(x)

    service_times = pd.read_csv(dataset_paths["serviceTimes"], converters={
        "serviceTimes [us]": lambda x: custom_eval(x),
        "serverAddresses": lambda x: custom_eval(x)})
    migration_times = pd.read_csv(dataset_paths["migrationTimes"])
    restore_times = pd.read_csv(dataset_paths["restoreTimes"], converters={
        "restoreTime [s]": lambda x: custom_eval(x)})

    dataset = pd.merge(service_times, migration_times, how="outer")
    dataset = pd.merge(dataset, restore_times, how="outer")
    return dataset


def get_migration_affected_service_time(row):
    server_destination = "192.168.1.105:6666"

    # 0-based index.
    first_request_after_migration_triggered = \
        int(row["firstRequestAfterMigrationTriggered"]) - 1

    addresses_after_migration_triggered = \
        row["serverAddresses"][first_request_after_migration_triggered:-1]
    service_times_after_migration_triggered = \
        row["serviceTimes [us]"][first_request_after_migration_triggered:-1]

    # Get the index of the first response from server destination.
    index = \
        next((i for i, v in enumerate(addresses_after_migration_triggered)
              if v == server_destination), None)

    if index is None:
        raise RuntimeError(
            "Pre-processing: wrong server destination address {}. "
            "Check the code".format(server_destination))

    return {"migrationAffectedServiceTime [us]":
                service_times_after_migration_triggered[index],
            "firstResponseFromNewAddress":
                row["firstRequestAfterMigrationTriggered"] + index}


def convert_to_megabytes(size):
    if pd.isnull(size):
        return size

    suffix = size[-1]
    prefix = float(size[:-1])
    if suffix == "K":
        return prefix / 1024
    elif suffix == "M":
        return prefix

    raise RuntimeError("Unkown suffix when converting transfer sizes. "
                       "String: '{}'".format(size))


def convert_protocol_name(name):
    if name == "proactiveExplicit":
        return "Proactive Explicit"
    elif name == "reactiveExplicit":
        return "Reactive Explicit"
    elif name == "poolOfAddresses3":
        return "Pool of Addresses (3)"
    elif name == "symmetric":
        return "Symmetric"


def convert_migration_technique_name(name):
    if name == "cold":
        return "Cold"
    elif name == "preCopy":
        return "Pre-copy"
    elif name == "postCopy":
        return "Post-copy"
    elif name == "hybrid":
        return "Hybrid"


def preprocess_dataset(dataset):
    preprocessed_dataset = dataset.copy(deep=True)

    # Check if there are entries with null service times, i.e. where the
    # service times could not be measured due to errors or connection timeouts.
    null_service_times = \
        preprocessed_dataset[preprocessed_dataset["serviceTimes [us]"].isna()]

    if null_service_times.empty:
        print("Pre-processing: there are no entries with null service times")
    else:
        stats = null_service_times.groupby(["protocol"]).size()
        print("Pre-processing: there are some entries with null service times "
              "that will be removed. They belong to the following protocols:")
        print(stats.to_string(header=False))

    preprocessed_dataset = \
        preprocessed_dataset[preprocessed_dataset["serviceTimes [us]"].notna()]

    # Parse the list of recorded service times and get the one affected both
    # by the container migration and the QUIC protocol migration. This service
    # time is related to the first request satisfied by the new server address,
    # whose number is saved as well in a separate column.
    new_columns = preprocessed_dataset.apply(
        lambda row: get_migration_affected_service_time(row),
        axis=1, result_type="expand")
    preprocessed_dataset = pd.concat(
        [preprocessed_dataset, new_columns], axis="columns")

    preprocessed_dataset["migrationAffectedServiceTime [ms]"] = \
        preprocessed_dataset["migrationAffectedServiceTime [us]"] / 1000
    preprocessed_dataset["migrationAffectedServiceTime [s]"] = \
        preprocessed_dataset["migrationAffectedServiceTime [ms]"] / 1000

    # The restore times are saved as a list in the format
    # [real X, user Y, sys Z]. Pick only the "real" time.
    preprocessed_dataset["restoreTime [s]"] = \
        preprocessed_dataset["restoreTime [s]"].map(
            lambda restore_times: float(restore_times[0].split(" ")[1]))

    # Convert some file sizes used in the plots to megabytes.
    # For lazy pages, each page is equal to 4KB.
    preprocessed_dataset["rsyncPreDumpTotalFileSize [MB]"] = \
        preprocessed_dataset["rsyncPreDumpTotalFileSize"].map(
            lambda size: convert_to_megabytes(size))

    preprocessed_dataset["rsyncDumpTotalFileSize [MB]"] = \
        preprocessed_dataset["rsyncDumpTotalFileSize"].map(
            lambda size: convert_to_megabytes(size))

    preprocessed_dataset["lazyPagesTotalSize [MB]"] = \
        preprocessed_dataset["numberOfLazyPages"].map(
            lambda n: (n * 4) / 1024 if not pd.isnull(n) else n)

    # Change the name of the protocols to be more clear in the plots.
    preprocessed_dataset["protocol"] = preprocessed_dataset["protocol"] \
        .map(lambda name: convert_protocol_name(name))

    # Change the name of the container migration
    # technique to be more clear in the plots.
    preprocessed_dataset["migrationTechnique"] = \
        preprocessed_dataset["migrationTechnique"] \
            .map(lambda name: convert_migration_technique_name(name))

    return preprocessed_dataset


def service_times_figure_save_path():
    return "plots/exp2_service_times_{}.pdf".format(str(time.time()))


def container_migration_time_figure_save_path(compression_enabled):
    if compression_enabled:
        return "plots/exp2_container_migration_time_with_compression_{}.pdf" \
            .format(str(time.time()))
    return "plots/exp2_container_migration_time_{}.pdf".format(str(time.time()))


def container_migration_overhead_figure_save_path(compression_enabled):
    if compression_enabled:
        return "plots/exp2_container_migration_overhead_with_compression_{}" \
               ".pdf".format(str(time.time()))
    return "plots/exp2_container_migration_overhead_{}.pdf" \
        .format(str(time.time()))


def plot_service_times_group_by_quic_protocol(dataset, title):
    inflations = [0, 10, 50, 100]
    sns.set_style("whitegrid")
    palette = sns.color_palette(
        ["cornflowerblue", "darkorange", "slategray", "gold"])

    for i, inflation in enumerate(inflations):
        df = dataset.loc[
            (dataset["memoryFootprintInflation [MB]"] == inflation)]
        plt.figure(figsize=(19.20, 10.80))
        ax = sns.barplot(x="protocol", y="migrationAffectedServiceTime [s]",
                         hue="migrationTechnique", data=df, ci=95,
                         estimator=np.mean, seed=1, n_boot=1000, capsize=0.05,
                         palette=palette, saturation=1)

        ax.set_xlabel("QUIC migration protocol", fontsize=15, labelpad=20)
        ax.set_ylabel("Service time [s]", fontsize=15, labelpad=20)
        ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=13)

        ax.set_title(title + " - memory inflation = {} MB".format(inflation),
                     fontsize=20)
        ax.legend(loc="upper right", fontsize=15)

        plt.yticks(np.arange(0, 42, 2))
        plt.savefig(service_times_figure_save_path(), format="pdf", dpi=300,
                    bbox_inches="tight")
        plt.show()


def plot_service_times_group_by_migration_technique(dataset, title):
    inflations = [0, 10, 50, 100]
    sns.set_style("whitegrid")
    palette = sns.color_palette(
        ["cornflowerblue", "darkorange", "slategray", "gold"])

    for i in range(0, len(inflations)):
        df = dataset.loc[
            (dataset["memoryFootprintInflation [MB]"] == inflations[i])]
        plt.figure(figsize=(19.20, 10.80))
        ax = sns.barplot(x="migrationTechnique",
                         y="migrationAffectedServiceTime [s]",
                         hue="protocol", data=df, ci=95,
                         estimator=np.mean, seed=1, n_boot=1000, capsize=0.05,
                         palette=palette, saturation=1)

        ax.set_xlabel("Container migration technique", fontsize=15, labelpad=20)
        ax.set_ylabel("Service time [s]", fontsize=15, labelpad=20)
        ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=13)

        ax.set_title(title + " - memory inflation = {} MB"
                     .format(inflations[i]), fontsize=20)
        ax.legend(loc="upper right", fontsize=15)

        plt.yticks(np.arange(0, 42, 2))
        plt.savefig(service_times_figure_save_path(), format="pdf", dpi=300,
                    bbox_inches="tight")
        plt.show()


def plot_service_times_scatterplot(dataset, title):
    sns.set_style("whitegrid")
    plt.figure(figsize=(19.20, 10.80))

    techniques = ["Cold", "Pre-copy", "Post-copy", "Hybrid", "empty_bar"]
    inflations = [0, 10, 50, 100]
    hue_order = []
    for i in inflations:
        for t in techniques:
            hue_order.append((i, t))

    palette = sns.color_palette("tab10", n_colors=6)
    palette.pop(3)

    ax = sns.stripplot(x="protocol", y="migrationAffectedServiceTime [s]",
                       hue=dataset[["memoryFootprintInflation [MB]",
                                    "migrationTechnique"]].apply(tuple, axis=1),
                       data=dataset, marker="o", dodge=True, size=10,
                       palette=palette, hue_order=hue_order)

    ax.set_xlabel("QUIC migration protocol", fontsize=15, labelpad=30)
    ax.set_ylabel("Service time [s]", fontsize=15, labelpad=20)
    ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=13)

    ax.tick_params(axis="x", which="major", labelsize=14, pad=25)
    ax.tick_params(axis="y", which="major", labelsize=14)
    ax.tick_params(axis="both", which="minor", labelsize=12,
                   reset=True, top=False)
    minor_ticks_positions = []
    for x in range(0, 4):
        minor_ticks_positions.append(x - 0.325)
        minor_ticks_positions.append(x - 0.11)
        minor_ticks_positions.append(x + 0.09)
        minor_ticks_positions.append(x + 0.29)
    ax.set_xticks(minor_ticks_positions,
                  ["{} MB".format(e) for e in inflations * 4],
                  minor=True, ha="center")

    legend_entries = [mpatches.Patch(color=palette[k], label=t)
                      for k, t in enumerate(techniques[:-1])]
    ax.legend(loc="upper left", fontsize=13, ncol=1, handles=legend_entries)

    ax.set_title(title, fontsize=20)
    ax.set_ymargin(0)
    plt.yticks(np.arange(0, 110, 10))
    plt.savefig(service_times_figure_save_path(), format="pdf", dpi=300,
                bbox_inches="tight")
    plt.show()


def plot_service_times_group_by_quic_protocol_all_together(dataset, title):
    sns.set_style("whitegrid")
    plt.figure(figsize=(19.20, 10.80))

    techniques = ["Cold", "Pre-copy", "Post-copy", "Hybrid", "empty_bar"]
    inflations = [0, 10, 50, 100]
    hue_order = []
    for i in inflations:
        for t in techniques:
            hue_order.append((i, t))

    palette = sns.color_palette("tab10", n_colors=6)
    palette.pop(3)

    ax = sns.barplot(x="protocol", y="migrationAffectedServiceTime [s]",
                     hue=dataset[["memoryFootprintInflation [MB]",
                                  "migrationTechnique"]].apply(tuple, axis=1),
                     data=dataset, hue_order=hue_order, ci=95,
                     estimator=np.mean, capsize=0.01, seed=1, n_boot=1000,
                     saturation=1, palette=palette)

    ax.set_xlabel("QUIC migration protocol", fontsize=15, labelpad=30)
    ax.set_ylabel("Service time [s]", fontsize=15, labelpad=20)
    ax.tick_params(axis="x", which="major", labelsize=14, pad=20)
    ax.tick_params(axis="y", which="major", labelsize=14)
    ax.tick_params(axis="both", which="minor", labelsize=10,
                   reset=True, top=False)

    sorted_bar_positions = sorted([bar.get_x() + bar.get_width()
                                   for bar in ax.patches])
    filtered_bar_positions = []
    for i, pos in enumerate(sorted_bar_positions):
        if i in np.arange(1, 80, 5):
            filtered_bar_positions.append(pos)

    ax.set_xticks(filtered_bar_positions,
                  ["{} MB".format(e) for e in inflations * 4],
                  minor=True, ha="center")
    ax.xaxis.remove_overlapping_locs = False

    legend_entries = [mpatches.Patch(color=palette[k], label=t)
                      for k, t in enumerate(techniques[:-1])]
    ax.legend(loc="upper center", fontsize=13, ncol=5, handles=legend_entries)

    ax.set_title(title, fontsize=20)
    ax.set_ymargin(0)

    plt.yticks(np.arange(0, 50, 5))
    plt.savefig(service_times_figure_save_path(), format="pdf", dpi=300,
                bbox_inches="tight")
    plt.show()


def compute_means_and_cis(dataset, inflation, techniques, metrics,
                          as_percentage, means, cis_upper, cis_lower,
                          means_labels, means_display_threshold,
                          means_percentage_display_threshold,
                          means_format_string, means_format_string_percentage):
    def compute_single_mean_and_ci(samples):
        if samples.isnull().values.any():
            return 0, 0, 0
        m = np.mean(samples)
        ci = sns.utils.ci(sns.algorithms.bootstrap(samples, func=np.mean,
                                                   n_boot=1000, units=None,
                                                   seed=1), which=95)
        return m, m - ci[0], ci[1] - m

    for technique in techniques:
        df = dataset.loc[
            (dataset["memoryFootprintInflation [MB]"] == inflation) & (
                    dataset["migrationTechnique"] == technique)]
        means_sum = 0

        for metric in metrics:
            mean, ci_lower, ci_upper = compute_single_mean_and_ci(df[metric])
            means[metric].append(mean)
            cis_lower[metric].append(ci_lower)
            cis_upper[metric].append(ci_upper)
            means_labels[metric].append(
                "" if mean == 0 or mean < means_display_threshold
                else means_format_string.format(mean))
            means_sum += mean

        if as_percentage is True:
            # Adjust the previously computed values to be a percentage.
            for metric in metrics:
                to_percentage = lambda x: (x * 100) / means_sum

                means[metric][-1] = to_percentage(means[metric][-1])
                cis_upper[metric][-1] = to_percentage(cis_upper[metric][-1])
                cis_lower[metric][-1] = to_percentage(cis_lower[metric][-1])

                last_mean = means[metric][-1]
                means_labels[metric][-1] = \
                    "" if last_mean == 0 \
                          or last_mean < means_percentage_display_threshold \
                        else means_format_string_percentage.format(last_mean)


def convert_container_migration_phase_to_label(name):
    if name == "preDumpTime [s]":
        return "Pre-dump time"
    elif name == "preDumpTxTime [s]":
        return "Pre-dump tx time"
    elif name == "dumpTime [s]":
        return "Dump time"
    elif name == "dumpTxTime [s]":
        return "Dump tx time"
    elif name == "restoreTime [s]":
        return "Restore time"
    elif name == "lazyPagesTxTime [s]":
        return "Faulted pages tx time"


def convert_container_migration_phase_size_to_label(name):
    if name == "rsyncPreDumpTotalFileSize [MB]":
        return "Pre-dump size"
    elif name == "rsyncDumpTotalFileSize [MB]":
        return "Dump size"
    elif name == "lazyPagesTotalSize [MB]":
        return "Faulted pages size"


def compute_next_bar_position(bar_centered_x, bar_number, bar_width):
    return bar_centered_x + (bar_width * (1 - len(bar_centered_x)) / 2) + \
           (bar_number * bar_width)


def plot_container_migration_time(dataset, as_percentage,
                                  compression_enabled,
                                  means_display_threshold=0.0,
                                  means_percentage_display_threshold=0.0):
    inflations = [0, 10, 50, 100]
    techniques = ["Cold", "Pre-copy", "Post-copy", "Hybrid"]
    metrics = ["preDumpTime [s]", "preDumpTxTime [s]", "dumpTime [s]",
               "dumpTxTime [s]", "restoreTime [s]", "lazyPagesTxTime [s]"]

    means = {k: [] for k in metrics}
    cis_upper = {k: [] for k in metrics}
    cis_lower = {k: [] for k in metrics}
    means_labels = {k: [] for k in metrics}

    sns.set_style("whitegrid")
    plt.figure(figsize=(19.80, 10.80))
    bar_centered_x = np.arange(len(techniques))
    bar_width = 0.2

    # Colors used for the bars, where each metric has a different color.
    colors = [sns.color_palette("Blues").as_hex()[3],
              sns.color_palette("light:salmon_r").as_hex()[2],
              sns.color_palette("YlOrBr").as_hex()[3],
              sns.color_palette("Purples").as_hex()[3],
              sns.light_palette("seagreen").as_hex()[3],
              sns.color_palette("ch:s=-.2,r=.6").as_hex()[3]]

    # List of dictionaries used to avoid printing confidence
    # intervals for the bars with a value of 0.
    error_kw = [{"errorevery": (1, 2)}, {"errorevery": (1, 2)},
                {}, {}, {}, {"errorevery": (2, 1)}]

    for i, inflation in enumerate(inflations):
        for k in metrics:
            means[k].clear()
            cis_upper[k].clear()
            cis_lower[k].clear()
            means_labels[k].clear()

        compute_means_and_cis(dataset, inflation, techniques, metrics,
                              as_percentage, means, cis_upper, cis_lower,
                              means_labels, means_display_threshold,
                              means_percentage_display_threshold,
                              "{:.2f}", "{:.2f}")

        # Array used to keep track of the starting vertical positions when
        # stacking bars in the plot. To initialize it, all the metrics are
        # equivalent, since they have the same length.
        bottom = np.zeros_like(means["preDumpTime [s]"])

        ax = plt.gca()
        next_bar_position = compute_next_bar_position(bar_centered_x, i,
                                                      bar_width)
        for k, metric in enumerate(metrics):
            g = ax.bar(next_bar_position, means[metric], bottom=bottom,
                       yerr=[cis_lower[metric], cis_upper[metric]],
                       error_kw=error_kw[k],
                       color=colors[k], width=bar_width, capsize=5)
            ax.bar_label(g, labels=means_labels[metric], label_type="center",
                         fontweight="bold", size=13)
            bottom += np.array(means[metric])

    ax = plt.gca()
    ax.set_xlabel("Container migration technique", fontsize=20, labelpad=30)
    ax.tick_params(axis="x", which="major", labelsize=14, pad=25)
    ax.tick_params(axis="y", which="major", labelsize=14)
    ax.tick_params(axis="both", which="minor", labelsize=12,
                   reset=True, top=False)
    ax.set_xticks(np.arange(len(techniques)), techniques)
    ax.set_xticks([bar.get_x() + bar.get_width() / 2. for bar in ax.patches],
                  ["{} MB".format(e) for e in
                   sorted(inflations * len(techniques) * 6)], minor=True)
    ax.xaxis.remove_overlapping_locs = False

    legend_entries = [mpatches.Patch(
        color=colors[k], label=convert_container_migration_phase_to_label(m))
        for k, m in enumerate(metrics)]

    if as_percentage is True:
        ax.legend(loc="upper center", fontsize=13,
                  ncol=6, handles=legend_entries)
        ax.set_ylabel("Container migration time (%)",
                      fontsize=20, labelpad=30)
        plt.yticks(np.arange(0, 130, 10))
    else:
        ax.legend(loc="upper left", fontsize=13, handles=legend_entries)
        ax.set_ylabel("Container migration time [s]",
                      fontsize=20, labelpad=30)
        plt.yticks(np.arange(0, 6.5, 0.5))

    plt.savefig(container_migration_time_figure_save_path(compression_enabled),
                format="pdf", dpi=300, bbox_inches="tight")
    plt.show()


def plot_container_migration_overhead(dataset, as_percentage,
                                      compression_enabled,
                                      means_display_threshold=0.0,
                                      means_percentage_display_threshold=0.0):
    inflations = [0, 10, 50, 100]
    techniques = ["Cold", "Pre-copy", "Post-copy", "Hybrid"]
    metrics = ["rsyncPreDumpTotalFileSize [MB]", "rsyncDumpTotalFileSize [MB]",
               "lazyPagesTotalSize [MB]"]

    means = {k: [] for k in metrics}
    cis_upper = {k: [] for k in metrics}
    cis_lower = {k: [] for k in metrics}
    means_labels = {k: [] for k in metrics}

    sns.set_style("whitegrid")
    plt.figure(figsize=(19.80, 10.80))
    bar_centered_x = np.arange(len(techniques))
    bar_width = 0.2

    # List of dictionaries used to avoid printing confidence
    # intervals for the bars with a value of 0.
    error_kw = [{"errorevery": (1, 2)}, {}, {"errorevery": (2, 1)}]

    # Colors used for the bars, where each metric has a different color.
    colors = [sns.color_palette("Blues").as_hex()[3],
              sns.color_palette("light:salmon_r").as_hex()[2],
              sns.light_palette("seagreen").as_hex()[3]]

    for i, inflation in enumerate(inflations):
        for k in metrics:
            means[k].clear()
            cis_upper[k].clear()
            cis_lower[k].clear()
            means_labels[k].clear()

        compute_means_and_cis(dataset, inflation, techniques, metrics,
                              as_percentage, means, cis_upper, cis_lower,
                              means_labels, means_display_threshold,
                              means_percentage_display_threshold,
                              "{:.2f}", "{:.2f}")

        # Array used to keep track of the starting vertical positions when
        # stacking bars in the plot. To initialize it, all the metrics are
        # equivalent, since they have the same length.
        bottom = np.zeros_like(means["lazyPagesTotalSize [MB]"])

        ax = plt.gca()
        next_bar_position = compute_next_bar_position(bar_centered_x, i,
                                                      bar_width)
        for k, metric in enumerate(metrics):
            g = ax.bar(next_bar_position, means[metric], bottom=bottom,
                       yerr=[cis_lower[metric], cis_upper[metric]],
                       error_kw=error_kw[k],
                       color=colors[k], width=bar_width, capsize=5)

            if inflation == 0 and as_percentage is False:
                ax.bar_label(g, labels=means_labels[metric], label_type="edge",
                             fontweight="bold", size=13, padding=5)
            else:
                ax.bar_label(g, labels=means_labels[metric],
                             label_type="center", fontweight="bold", size=13)
            bottom += np.array(means[metric])

    ax = plt.gca()
    ax.set_xlabel("Container migration technique", fontsize=20, labelpad=30)
    ax.tick_params(axis="x", which="major", labelsize=14, pad=25)
    ax.tick_params(axis="y", which="major", labelsize=14)
    ax.tick_params(axis="both", which="minor", labelsize=12,
                   reset=True, top=False)
    ax.set_xticks(np.arange(len(techniques)), techniques)
    ax.set_xticks([bar.get_x() + bar.get_width() / 2. for bar in ax.patches],
                  ["{} MB".format(e) for e in
                   sorted(inflations * len(techniques) * 3)], minor=True)
    ax.xaxis.remove_overlapping_locs = False

    legend_entries = [mpatches.Patch(
        color=colors[k],
        label=convert_container_migration_phase_size_to_label(m))
        for k, m in enumerate(metrics)]
    ax.legend(loc="upper center", fontsize=13, ncol=6, handles=legend_entries)

    if as_percentage is True:
        ax.set_ylabel("Container migration overhead [%]",
                      fontsize=20, labelpad=30)
        plt.yticks(np.arange(0, 140, 10))
    else:
        ax.set_ylabel("Container migration overhead [MB]",
                      fontsize=20, labelpad=30)
        plt.yticks(np.arange(0, 130, 10))

    plt.savefig(
        container_migration_overhead_figure_save_path(compression_enabled),
        format="pdf", dpi=300, bbox_inches="tight")
    plt.show()


def plot_service_times_over_time(dataset, with_loss):
    protocols = ["Proactive Explicit", "Reactive Explicit",
                 "Pool of Addresses (3)", "Symmetric"]
    techniques = ["Cold", "Pre-copy", "Post-copy", "Hybrid"]
    yticks = [(2, 0.5), (2, 0.5), (2, 0.5), (2, 0.5)]

    df = dataset.explode("serviceTimes [us]").reset_index()
    df["requestNumber"] = df.groupby(["run", "repetition"]).cumcount() + 1
    df["memoryFootprintInflation [MB]"] = df.apply(
        lambda row: "Memory inflation {} MB"
            .format(row["memoryFootprintInflation [MB]"]), axis=1)
    df["serviceTimes [s]"] = df["serviceTimes [us]"] / 1000000

    migration_trigger = df["firstRequestAfterMigrationTriggered"].iloc[0] - 1
    df = df[(df["requestNumber"] >= migration_trigger - 2) &
            (df["requestNumber"] <= 732)]

    for p, protocol in enumerate(protocols):
        sns.set_style("whitegrid")
        sns.set_palette("ch:s=-.2,r=.6")
        fig, axs = plt.subplots(ncols=2, nrows=2, figsize=(25.60, 10.80))

        for i, technique in enumerate(techniques):
            df_plot = df.loc[(df["protocol"] == protocol) & (
                    df["migrationTechnique"] == technique)]
            ax = axs[int(i / 2), i % 2]

            sns.lineplot(x="requestNumber", y="serviceTimes [s]",
                         hue="memoryFootprintInflation [MB]",
                         data=df_plot, ci=95, estimator=np.mean,
                         err_style="band", seed=1, n_boot=1000, ax=ax,
                         marker="o", markeredgewidth=0)

            # Plot line denoting the request
            # after which the migration is triggered.
            ax.axvline(migration_trigger, 0, 1, color="black", zorder=10,
                       linestyle="--", label="Migration trigger")

            # Plot markers to visually denote the
            # responses from the new server address.
            ax.scatter(df_plot["firstResponseFromNewAddress"],
                       np.zeros_like(df_plot["firstResponseFromNewAddress"]),
                       s=80, c="black", alpha=1, marker="x", zorder=10,
                       label="First response\nfrom new address")

            xmin, xmax = ax.get_xlim()
            if technique == "Cold" or technique == "Post-copy" \
                    or protocol == "Proactive Explicit":
                ax.set_xticks(np.arange(int(xmin) + 1, int(xmax) + 1, 1))
            else:
                ax.set_xticks(np.arange(int(xmin), int(xmax), 2))

            ax.set_xmargin(0)
            if protocol == "Proactive Explicit":
                if technique != "Post-copy":
                    ax.set_ymargin(0.01)
                elif technique == "Pre-copy" or technique == "Hybrid":
                    ax.set_ymargin(0.05)
            elif protocol == "Reactive Explicit":
                if technique == "Cold":
                    ax.set_ymargin(0.01)
                elif technique == "Post-copy":
                    ax.set_ymargin(0.025)
                elif with_loss is True:
                    ax.set_ymargin(0.04)
            elif protocol == "Pool of Addresses (3)":
                if technique == "Cold":
                    ax.set_ymargin(0.002)
                elif technique == "Post-copy":
                    ax.set_ymargin(0.004)
                elif with_loss:
                    ax.set_ymargin(0.01)
            elif protocol == "Symmetric":
                if technique == "Cold":
                    ax.set_ymargin(0.025)
                elif technique == "Post-copy":
                    ax.set_ymargin(0.03)

            ax.set_yticks(np.arange(0, yticks[p][0] + yticks[p][1],
                                    yticks[p][1]))
            ax.set_ylim(top=yticks[p][0])

            ax.tick_params(axis="both", which="major", labelsize=14)
            ax.tick_params(axis="both", which="minor", labelsize=14)
            ax.legend(loc="upper right", fontsize=13)
            ax.set_title("{} - {}".format(protocol, technique), fontsize=20)
            ax.set(xlabel=None, ylabel=None)

        axs[1, 0].set_xlabel("Request number", fontsize=20, labelpad=30)
        axs[1, 1].set_xlabel("Request number", fontsize=20, labelpad=30)
        axs[0, 0].set_ylabel("Service time [s]", fontsize=20, labelpad=30)
        axs[1, 0].set_ylabel("Service time [s]", fontsize=20, labelpad=30)
        plt.tight_layout(h_pad=5, w_pad=5)

        plt.savefig(service_times_figure_save_path(),
                    format="pdf", dpi=300, bbox_inches="tight")
        plt.show()


def main():
    base_path = "data/nopacketloss/exp2/"
    no_packet_loss_paths = {
        "serviceTimes": base_path + "experiment2_service_times.csv",
        "migrationTimes": base_path + "experiment2_migration_times.csv",
        "restoreTimes": base_path + "experiment2_restore_times.csv"
    }

    base_path = "data/packetloss/exp2/"
    packet_loss_paths = {
        "serviceTimes": base_path + "experiment2_service_times.csv",
        "migrationTimes": base_path + "experiment2_migration_times.csv",
        "restoreTimes": base_path + "experiment2_restore_times.csv"
    }

    base_path = "data/nopacketloss/exp2/compressionenabled/"
    no_packet_loss_and_compression_paths = {
        "serviceTimes": base_path + "experiment2_service_times.csv",
        "migrationTimes": base_path + "experiment2_migration_times.csv",
        "restoreTimes": base_path + "experiment2_restore_times.csv"
    }

    dataset_no_loss = parse_dataset(no_packet_loss_paths)
    dataset_loss = parse_dataset(packet_loss_paths)
    dataset_compression = parse_dataset(no_packet_loss_and_compression_paths)

    preprocessed_dataset_no_loss = preprocess_dataset(dataset_no_loss)
    preprocessed_dataset_loss = preprocess_dataset(dataset_loss)
    preprocessed_dataset_compression = preprocess_dataset(dataset_compression)

    os.makedirs("./plots", exist_ok=True)

    # plot_service_times_group_by_quic_protocol(
    #     preprocessed_dataset_no_loss, "No packet loss")
    # plot_service_times_group_by_migration_technique(
    #     preprocessed_dataset_no_loss, "No packet loss")
    plot_service_times_scatterplot(
        preprocessed_dataset_no_loss, "")
    plot_service_times_group_by_quic_protocol_all_together(
        preprocessed_dataset_no_loss, "")
    plot_service_times_over_time(preprocessed_dataset_no_loss, with_loss=False)

    # plot_service_times_group_by_quic_protocol(
    #     preprocessed_dataset_loss, "Packet loss 3 %")
    # plot_service_times_group_by_migration_technique(
    #     preprocessed_dataset_loss, "Packet loss 3 %")
    plot_service_times_scatterplot(
        preprocessed_dataset_loss, "Packet loss 3 %")
    plot_service_times_group_by_quic_protocol_all_together(
        preprocessed_dataset_loss, "Packet loss 3 %")
    plot_service_times_over_time(preprocessed_dataset_loss, with_loss=True)

    plot_container_migration_time(preprocessed_dataset_no_loss,
                                  as_percentage=False,
                                  compression_enabled=False,
                                  means_display_threshold=0.1)
    plot_container_migration_time(preprocessed_dataset_no_loss,
                                  as_percentage=True,
                                  compression_enabled=False,
                                  means_percentage_display_threshold=1.05)
    plot_container_migration_overhead(preprocessed_dataset_no_loss,
                                      as_percentage=False,
                                      compression_enabled=False,
                                      means_display_threshold=0.70)
    plot_container_migration_overhead(preprocessed_dataset_no_loss,
                                      as_percentage=True,
                                      compression_enabled=False,
                                      means_percentage_display_threshold=3)

    # Note: the packet loss was not set to affect the path between the
    # server machines, but only the ones between the client and the server
    # machines. This means that the packet loss does not affect the container
    # migration process and the following plots depict the same scenario of
    # the ones crafted above.
    plot_container_migration_time(preprocessed_dataset_loss,
                                  as_percentage=False,
                                  compression_enabled=False,
                                  means_display_threshold=0.1)
    plot_container_migration_time(preprocessed_dataset_loss,
                                  as_percentage=True,
                                  compression_enabled=False,
                                  means_percentage_display_threshold=1.05)
    plot_container_migration_overhead(preprocessed_dataset_loss,
                                      as_percentage=False,
                                      compression_enabled=False,
                                      means_display_threshold=0.79)
    plot_container_migration_overhead(preprocessed_dataset_loss,
                                      as_percentage=True,
                                      compression_enabled=False,
                                      means_percentage_display_threshold=3)

    plot_container_migration_time(preprocessed_dataset_compression,
                                  as_percentage=False,
                                  compression_enabled=True,
                                  means_display_threshold=0.1)
    plot_container_migration_overhead(preprocessed_dataset_compression,
                                      as_percentage=False,
                                      compression_enabled=True,
                                      means_display_threshold=0.75)


if __name__ == "__main__":
    main()

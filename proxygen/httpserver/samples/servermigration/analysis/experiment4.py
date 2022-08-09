import os
import time
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


def parse_dataset(dataset_paths):
    service_times = pd.read_csv(dataset_paths["serviceTimes"], converters={
        "requestTimestamps [us]": pd.eval,
        "serviceTimes [us]": pd.eval,
        "serverAddresses": pd.eval})
    migration_times = pd.read_csv(dataset_paths["migrationTimes"])
    restore_times = pd.read_csv(dataset_paths["restoreTimes"], converters={
        "restoreTime [s]": pd.eval})

    dataset = pd.merge(service_times, migration_times, left_index=True,
                       right_index=True)
    dataset = pd.merge(dataset, restore_times, left_index=True,
                       right_index=True)
    return dataset


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
    elif name == "poolOfAddresses":
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


def preprocess_dataset(dataset, n_clients):
    preprocessed_dataset = dataset.copy(deep=True)

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

    def first_session_timestamp(row):
        # Given the seed of the client represented by this row, compute the seed
        # of the first client that was launched in the same session. The first
        # client is the one holding the first request timestamp of the session.
        # To find the first client, we use the run number to compute the
        # corresponding seed. The number of clients is assumed to be the same
        # across all the runs.
        first_client_seed = (row["run"] - 1) * n_clients + 1
        df = preprocessed_dataset[
            preprocessed_dataset["seedClient"] == first_client_seed]
        return df["requestTimestamps [us]"].iloc[0][0] / 1000000

    # Save in a separate column the first request timestamp for each row.
    # This will be useful afterwards to shift timestamps.
    # preprocessed_dataset["firstRequestTimestampOfSession [s]"] = \
    #     preprocessed_dataset.apply(
    #         lambda row: row["requestTimestamps [us]"][0] / 1000000, axis=1)
    preprocessed_dataset["firstRequestTimestampOfSession [s]"] = \
        preprocessed_dataset.apply(lambda row: first_session_timestamp(row),
                                   axis=1)

    # List all the requests in separate rows.
    preprocessed_dataset = preprocessed_dataset.explode(
        ["requestTimestamps [us]", "serviceTimes [us]", "serverAddresses"],
        ignore_index=True)

    # Add request number to each row.
    preprocessed_dataset["requestNumber"] = \
        preprocessed_dataset.groupby(["seedClient"]).cumcount() + 1

    # Convert timestamps to seconds.
    preprocessed_dataset["requestTimestamps [s]"] = \
        preprocessed_dataset["requestTimestamps [us]"] / 1000000

    # Shift timestamps so that they represent the
    # time passed since the beginning of the run.
    preprocessed_dataset["shiftedRequestTimestamps [s]"] = \
        preprocessed_dataset["requestTimestamps [s]"] - \
        preprocessed_dataset["firstRequestTimestampOfSession [s]"]

    preprocessed_dataset["shiftedMigrationNotificationTimestamp [s]"] = \
        preprocessed_dataset["migrationNotificationTimestamp [s]"] - \
        preprocessed_dataset["firstRequestTimestampOfSession [s]"]

    preprocessed_dataset["shiftedMigrationTriggerTimestamp [s]"] = \
        preprocessed_dataset["migrationTriggerTimestamp [s]"] - \
        preprocessed_dataset["firstRequestTimestampOfSession [s]"]

    # Convert service times to milliseconds and seconds.
    preprocessed_dataset["serviceTimes [ms]"] = \
        preprocessed_dataset["serviceTimes [us]"] / 1000
    preprocessed_dataset["serviceTimes [s]"] = \
        preprocessed_dataset["serviceTimes [ms]"] / 1000

    return preprocessed_dataset


def service_times_figure_save_path():
    return "plots/exp4_service_times_{}.png".format(str(time.time()))


def adjust_y_margin(ax, loss, protocol, interval, technique):
    if not loss:
        if protocol == "Pool of Addresses (3)" \
                and (interval == 260 or interval == 1000):
            ax.set_ymargin(0.007)
        return

    if protocol == "Reactive Explicit":
        if (technique == "Pre-copy" and interval == 260) \
                or (technique == "Hybrid" and interval == 0):
            ax.set_ymargin(0.005)
        else:
            ax.set_ymargin(0.007)
        return

    if protocol == "Pool of Addresses (3)":
        if technique == "Cold":
            ax.set_ymargin(0.002)
        elif technique == "Pre-copy":
            ax.set_ymargin(0.001)
        elif technique == "Post-copy" and interval == 0:
            ax.set_ymargin(0.002)
        elif technique == "Post-copy" and interval == 260:
            ax.set_ymargin(0.003)
        elif technique == "Post-copy" and interval == 1000:
            ax.set_ymargin(0.001)
        elif technique == "Hybrid" and (interval == 0 or interval == 260):
            ax.set_ymargin(0.001)
        elif technique == "Hybrid" and interval == 1000:
            ax.set_ymargin(0.004)
        else:
            ax.set_ymargin(0.007)
        return

    if protocol == "Symmetric":
        if technique == "Cold" and (interval == 0 or interval == 260):
            ax.set_ymargin(0.007)
        elif technique == "Pre-copy" and interval == 1000:
            ax.set_ymargin(0.007)
        elif technique == "Pre-copy" and (interval == 0 or interval == 260):
            ax.set_ymargin(0.002)
        elif technique == "Post-copy":
            ax.set_ymargin(0.007)
        elif technique == "Hybrid" and (interval == 0 or interval == 260):
            ax.set_ymargin(0.007)


def plot_service_times_over_time(dataset, title, loss):
    protocol_list = ["Reactive Explicit", "Symmetric", "Pool of Addresses (3)"]
    interval_list = [0, 260, 1000]
    technique_list = ["Cold", "Pre-copy", "Post-copy", "Hybrid"]

    sns.set_style("whitegrid")
    for technique in technique_list:
        fig, axes = plt.subplots(ncols=3, nrows=3, figsize=(35.60, 21.60))

        for i, protocol in enumerate(protocol_list):
            for j, interval in enumerate(interval_list):
                df = dataset[(dataset["protocol"] == protocol) &
                             (dataset["migrationTechnique"] == technique) &
                             (dataset[
                                  "memoryFootprintInflation [MB]"] == 0) &
                             (dataset[
                                  "intervalBetweenRequests [ms]"] == interval) &
                             (dataset["shiftedRequestTimestamps [s]"] <= 140) &
                             (dataset["shiftedRequestTimestamps [s]"] >= 30) &
                             (dataset["connectionEndedDueToTimeout"] == False)]
                ax = axes[i, j]

                n_colors = len(df["seedClient"].unique())
                palette = sns.cubehelix_palette(start=-.2, rot=.6,
                                                reverse=True, n_colors=n_colors)
                sns.lineplot(x="shiftedRequestTimestamps [s]",
                             y="serviceTimes [s]", hue="seedClient", data=df,
                             ci=None, ax=ax, legend=False, palette=palette)

                migration_notification_timestamp = \
                    df["shiftedMigrationNotificationTimestamp [s]"].iloc[0]
                ax.axvline(migration_notification_timestamp, 0, 1,
                           color="black", zorder=10,
                           linewidth=2, linestyle=":",
                           label="Imminent migration notification")

                migration_trigger_timestamp = \
                    df["shiftedMigrationTriggerTimestamp [s]"].iloc[0]
                ax.axvline(migration_trigger_timestamp, 0, 1, color="black",
                           zorder=10, linewidth=2, linestyle="--",
                           label="Migration trigger")

                ax.set_xmargin(0)
                adjust_y_margin(ax, loss, protocol, interval, technique)

                ax.set_ylim(top=6)
                ax.set_yticks(np.arange(0, 7, 1))
                ax.set_xticks(np.arange(30, 150, 10))

                ax.tick_params(axis="both", which="major", labelsize=14)
                ax.tick_params(axis="both", which="minor", labelsize=14)
                ax.legend(loc="upper left", fontsize=13)
                ax.set(xlabel=None, ylabel=None)

        for ax, col in zip(axes[0, :],
                           ["Back-to-back requests", "Requests every 260 ms",
                            "Requests every 1 s"]):
            ax.annotate(col, (0.5, 1), xytext=(0, 10), ha="center", va="bottom",
                        size=20, xycoords="axes fraction",
                        textcoords="offset points")

        for ax, row in zip(axes[:, 0], ["QUIC protocol: {}".format(e) for e in
                                        protocol_list]):
            ax.annotate(row, (0, 0.5), xytext=(-95, 0), ha="right", va="center",
                        size=20, rotation=90, xycoords="axes fraction",
                        textcoords="offset points")

        axes[2, 0].set_xlabel("Request time [s]", fontsize=20, labelpad=20)
        axes[2, 1].set_xlabel("Request time [s]", fontsize=20, labelpad=20)
        axes[2, 2].set_xlabel("Request time [s]", fontsize=20, labelpad=20)
        axes[0, 0].set_ylabel("Service time [s]", fontsize=20, labelpad=20)
        axes[1, 0].set_ylabel("Service time [s]", fontsize=20, labelpad=20)
        axes[2, 0].set_ylabel("Service time [s]", fontsize=20, labelpad=20)

        fig.suptitle("{}, {} migration".format(title, technique),
                     fontsize=30, y=0.95)
        plt.savefig(service_times_figure_save_path(), format="png",
                    dpi=300, bbox_inches="tight")
        plt.show()


def main():
    base_path = "data/nopacketloss/exp4/"
    no_packet_loss_paths = {
        "serviceTimes": base_path + "experiment4_service_times.csv",
        "migrationTimes": base_path + "experiment4_migration_times.csv",
        "restoreTimes": base_path + "experiment4_restore_times.csv",
        "preProcessedDataset": base_path + "df_no_loss.pickle"
    }

    base_path = "data/packetloss/exp4/"
    packet_loss_paths = {
        "serviceTimes": base_path + "experiment4_service_times.csv",
        "migrationTimes": base_path + "experiment4_migration_times.csv",
        "restoreTimes": base_path + "experiment4_restore_times.csv",
        "preProcessedDataset": base_path + "df_loss.pickle"
    }
    n_clients = 30

    try:
        dataset_no_loss = pd.read_pickle(
            no_packet_loss_paths["preProcessedDataset"])
    except:
        dataset_no_loss = parse_dataset(no_packet_loss_paths)
        dataset_no_loss.to_pickle(no_packet_loss_paths["preProcessedDataset"])

    try:
        dataset_loss = pd.read_pickle(packet_loss_paths["preProcessedDataset"])
    except:
        dataset_loss = parse_dataset(packet_loss_paths)
        dataset_loss.to_pickle(packet_loss_paths["preProcessedDataset"])

    preprocessed_dataset_no_loss = preprocess_dataset(dataset_no_loss,
                                                      n_clients)
    preprocessed_dataset_loss = preprocess_dataset(dataset_loss,
                                                   n_clients)

    os.makedirs("./plots", exist_ok=True)
    plot_service_times_over_time(preprocessed_dataset_no_loss,
                                 "No packet loss",
                                 loss=False)
    plot_service_times_over_time(preprocessed_dataset_loss,
                                 "Packet loss 3 %",
                                 loss=True)


if __name__ == "__main__":
    main()

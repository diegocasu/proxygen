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
        "serverAddresses": pd.eval,
        "handoverTimestamps [s]": pd.eval,
        "migrationNotificationTimestamps [s]": pd.eval,
        "migrationTriggerTimestamps [s]": pd.eval})

    baseline = pd.read_csv(dataset_paths["baseline"], converters={
        "requestTimestamps [us]": pd.eval,
        "serviceTimes [us]": pd.eval,
        "serverAddresses": pd.eval,
        "handoverTimestamps [s]": pd.eval})

    return service_times, baseline


def convert_protocol_name(name):
    if name == "reactiveExplicit":
        return "Reactive Explicit"
    elif name == "symmetric":
        return "Symmetric"


def preprocess_dataset(dataset):
    preprocessed_dataset = dataset.copy(deep=True)

    # Change the name of the protocols to be more clear in the plots.
    preprocessed_dataset["protocol"] = preprocessed_dataset["protocol"] \
        .map(lambda name: convert_protocol_name(name))

    # Save in a separate column the first request timestamp for each row.
    # This will be useful afterwards to shift timestamps.
    preprocessed_dataset["firstRequestTimestampOfSession [s]"] = \
        preprocessed_dataset.apply(
            lambda row: row["requestTimestamps [us]"][0] / 1000000,
            axis=1)

    def shiftTimestampInList(row, label):
        shifted_timestamps = []
        for timestamp in row[label]:
            shifted_timestamps.append(
                timestamp - row["firstRequestTimestampOfSession [s]"])
        return shifted_timestamps

    # Shift timestamps of events, so that they represent the
    # time passed since the beginning of the run.
    preprocessed_dataset["shiftedHandoverTimestamps [s]"] = \
        preprocessed_dataset.apply(
            lambda row: shiftTimestampInList(row, "handoverTimestamps [s]"),
            axis=1)

    preprocessed_dataset["shiftedMigrationNotificationTimestamps [s]"] = \
        preprocessed_dataset.apply(
            lambda row: shiftTimestampInList(
                row, "migrationNotificationTimestamps [s]"),
            axis=1)

    preprocessed_dataset["shiftedMigrationTriggerTimestamps [s]"] = \
        preprocessed_dataset.apply(
            lambda row: shiftTimestampInList(
                row, "migrationTriggerTimestamps [s]"),
            axis=1)

    # List all the requests in separate rows.
    preprocessed_dataset = preprocessed_dataset.explode(
        ["requestTimestamps [us]", "serviceTimes [us]", "serverAddresses"],
        ignore_index=True)

    # Add request number to each row.
    preprocessed_dataset["requestNumber"] = \
        preprocessed_dataset.groupby(["seed"]).cumcount() + 1

    # Convert timestamps to seconds.
    preprocessed_dataset["requestTimestamps [s]"] = \
        preprocessed_dataset["requestTimestamps [us]"] / 1000000

    # Shift timestamps of requests, so that they represent the
    # time passed since the beginning of the run.
    preprocessed_dataset["shiftedRequestTimestamps [s]"] = \
        preprocessed_dataset["requestTimestamps [s]"] - \
        preprocessed_dataset["firstRequestTimestampOfSession [s]"]

    # Convert service times to milliseconds and seconds.
    preprocessed_dataset["serviceTimes [ms]"] = \
        preprocessed_dataset["serviceTimes [us]"] / 1000
    preprocessed_dataset["serviceTimes [s]"] = \
        preprocessed_dataset["serviceTimes [ms]"] / 1000

    return preprocessed_dataset


def preprocess_baseline(dataset):
    preprocessed_dataset = dataset.copy(deep=True)

    # Save in a separate column the first request timestamp for each row.
    # This will be useful afterwards to shift timestamps.
    preprocessed_dataset["firstRequestTimestampOfSession [s]"] = \
        preprocessed_dataset.apply(
            lambda row: row["requestTimestamps [us]"][0] / 1000000,
            axis=1)

    def shiftTimestampInList(row, label):
        shifted_timestamps = []
        for timestamp in row[label]:
            shifted_timestamps.append(
                timestamp - row["firstRequestTimestampOfSession [s]"])
        return shifted_timestamps

    # List all the requests in separate rows.
    preprocessed_dataset = preprocessed_dataset.explode(
        ["requestTimestamps [us]", "serviceTimes [us]", "serverAddresses"],
        ignore_index=True)

    # Shift timestamps of events, so that they represent the
    # time passed since the beginning of the run.
    preprocessed_dataset["shiftedHandoverTimestamps [s]"] = \
        preprocessed_dataset.apply(
            lambda row: shiftTimestampInList(row, "handoverTimestamps [s]"),
            axis=1)

    # Add request number to each row.
    preprocessed_dataset["requestNumber"] = \
        preprocessed_dataset.groupby(["seed"]).cumcount() + 1

    # Convert timestamps to seconds.
    preprocessed_dataset["requestTimestamps [s]"] = \
        preprocessed_dataset["requestTimestamps [us]"] / 1000000

    # Shift timestamps so that they represent the
    # time passed since the beginning of the run.
    preprocessed_dataset["shiftedRequestTimestamps [s]"] = \
        preprocessed_dataset["requestTimestamps [s]"] - \
        preprocessed_dataset["firstRequestTimestampOfSession [s]"]

    # Convert service times to milliseconds and seconds.
    preprocessed_dataset["serviceTimes [ms]"] = \
        preprocessed_dataset["serviceTimes [us]"] / 1000
    preprocessed_dataset["serviceTimes [s]"] = \
        preprocessed_dataset["serviceTimes [ms]"] / 1000

    return preprocessed_dataset


def service_times_figure_save_path():
    return "plots/exp5_service_times_{}.pdf".format(str(time.time()))


def plot_service_times_over_time(dataset, title, marker_label, color):
    sns.set_style("whitegrid")
    plt.figure(figsize=(19.80, 10.80))

    ax = sns.lineplot(x="shiftedRequestTimestamps [s]", y="serviceTimes [s]",
                      data=dataset, estimator=None, ci=None, color=color,
                      marker="o", markeredgewidth=0, markersize=4,
                      rasterized=True)

    ax.scatter(dataset["shiftedHandoverTimestamps [s]"].iloc[0],
               np.full((len(dataset["shiftedHandoverTimestamps [s]"].iloc[0])),
                       0),
               s=120, c="black", alpha=1, marker="x", zorder=10,
               label=marker_label, rasterized=True)

    ax.set_yticks(np.arange(0, 9, 1))
    ax.set_xticks(np.arange(0, 4500, 500))
    ax.set_xlim(0, 3800)
    ax.set_ylim(ymax=8)

    ax.tick_params(axis="both", which="major", labelsize=14)
    ax.tick_params(axis="both", which="minor", labelsize=14)
    ax.legend(loc="upper left", fontsize=13)

    ax.set_xlabel("Request time [s]", fontsize=20, labelpad=30)
    ax.set_ylabel("Service time [s]", fontsize=20, labelpad=30)
    ax.legend(loc="upper left", fontsize=14)
    ax.set_title(title, fontsize=20)

    plt.savefig(service_times_figure_save_path(), format="pdf",
                dpi=300, bbox_inches="tight")
    plt.show()


def plot_service_times_during_handover(dataset, baseline):
    sns.set_style("whitegrid")
    plt.figure(figsize=(19.80, 10.80))
    palette = sns.color_palette("Set2").as_hex()

    df_handover = dataset[(dataset["shiftedRequestTimestamps [s]"] >= 590) &
                          (dataset["shiftedRequestTimestamps [s]"] <= 620)]
    df_baseline = baseline[(baseline["shiftedRequestTimestamps [s]"] >= 590) &
                           (baseline["shiftedRequestTimestamps [s]"] <= 620)]

    fig, (ax1, ax2) = plt.subplots(ncols=2, nrows=1, figsize=(19.20, 10.80))

    sns.lineplot(x="shiftedRequestTimestamps [s]", y="serviceTimes [ms]",
                 data=df_handover, estimator=None, ci=None,
                 marker="o", markeredgewidth=0, ax=ax1, color=palette[0])
    ax1.scatter(df_handover["shiftedHandoverTimestamps [s]"].iloc[0][0], 7,
                s=120, c="black", alpha=1, marker="x", zorder=10,
                label="Client handover")
    ax1.scatter(df_handover["shiftedMigrationTriggerTimestamps [s]"].iloc[0][0],
                7, s=120, c="black", alpha=1, marker="o", zorder=10,
                label="Server migration")

    sns.lineplot(x="shiftedRequestTimestamps [s]", y="serviceTimes [ms]",
                 data=df_baseline, estimator=None, ci=None,
                 marker="o", markeredgewidth=0, ax=ax2, color=palette[1])
    ax2.scatter(df_baseline["shiftedHandoverTimestamps [s]"].iloc[0][0], 7,
                s=120, c="black", alpha=1, marker="x", zorder=10,
                label="Client handover")

    ax1.tick_params(axis="both", which="major", labelsize=14)
    ax1.tick_params(axis="both", which="minor", labelsize=14)
    ax1.legend(loc="upper left", fontsize=13)
    ax1.set(xlabel=None, ylabel=None)

    ax2.tick_params(axis="both", which="major", labelsize=14)
    ax2.tick_params(axis="both", which="minor", labelsize=14)
    ax2.legend(loc="upper left", fontsize=13)
    ax2.set(xlabel=None, ylabel=None)

    ax1.set_yscale("log")
    ax1.set_yticks([10 ** i for i in range(1, 5)])
    ax1.set_xticks(np.arange(590, 630, 5))
    ax1.set_xlim(590, 620)
    ax1.set_ylim(ymin=5, ymax=10 ** 4)

    ax2.set_yscale("log")
    ax2.set_yticks([10 ** i for i in range(1, 5)])
    ax2.set_xticks(np.arange(590, 630, 5))
    ax2.set_xlim(590, 620)
    ax2.set_ylim(ymin=5, ymax=10 ** 4)

    ax1.set_xlabel("Request time [s]", fontsize=20, labelpad=30)
    ax2.set_xlabel("Request time [s]", fontsize=20, labelpad=30)
    ax1.set_ylabel("Service time [ms]", fontsize=20, labelpad=30)

    ax1.legend(loc="upper right", fontsize=14)
    ax1.set_title("With server migration", fontsize=20)

    ax2.legend(loc="upper right", fontsize=14)
    ax2.set_title("Without server migration", fontsize=20)

    plt.savefig(service_times_figure_save_path(), format="pdf",
                dpi=300, bbox_inches="tight")
    plt.show()


def main():
    base_path = "data/packetloss/"
    paths = {
        "baseline": base_path + "exp6/experiment6_service_times.csv",
        "serviceTimes": base_path + "exp5/experiment5_service_times.csv",
    }

    dataset, baseline = parse_dataset(paths)
    preprocessed_dataset = preprocess_dataset(dataset)
    preprocessed_baseline = preprocess_baseline(baseline)

    os.makedirs("./plots", exist_ok=True)

    palette = sns.color_palette("Set2").as_hex()
    df_symmetric = preprocessed_dataset[
        (preprocessed_dataset["protocol"] == "Symmetric")]

    plot_service_times_over_time(df_symmetric, "With server migration",
                                 "Client handover and server migration",
                                 palette[0])
    plot_service_times_over_time(preprocessed_baseline,
                                 "Without server migration",
                                 "Client handover", palette[1])
    plot_service_times_during_handover(df_symmetric, preprocessed_baseline)


if __name__ == "__main__":
    main()

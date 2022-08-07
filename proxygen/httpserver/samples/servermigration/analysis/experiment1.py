import os
import time
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


def parse_dataset(dataset_paths):
    def custom_eval(x):
        return np.NaN if x == "" else pd.eval(x)

    service_times = pd.read_csv(
        dataset_paths["serviceTimes"],
        converters={"serviceTimes [us]": lambda x: custom_eval(x),
                    "serverAddresses": lambda x: custom_eval(x)})

    migration_times = pd.read_csv(dataset_paths["migrationTimes"])

    restore_times = pd.read_csv(
        dataset_paths["restoreTimes"],
        converters={"restoreTime [s]": lambda x: custom_eval(x)})

    quic_baseline = pd.read_csv(
        dataset_paths["baseline"],
        converters={"serviceTimes [us]": pd.eval,
                    "serverAddresses": pd.eval})

    dataset = pd.merge(service_times, migration_times, how="outer")
    dataset = pd.merge(dataset, restore_times, how="outer")
    dataset = pd.concat([dataset, quic_baseline], ignore_index=True)
    return dataset


def convert_protocol_name(name):
    if name == "proactiveExplicit":
        return "Proactive Explicit"
    elif name == "reactiveExplicit":
        return "Reactive Explicit"
    elif name == "poolOfAddresses1":
        return "Pool of Addresses (1)"
    elif name == "poolOfAddresses2":
        return "Pool of Addresses (2)"
    elif name == "poolOfAddresses3":
        return "Pool of Addresses (3)"
    elif name == "symmetric":
        return "Symmetric"
    elif name == "quicBaseline":
        return "QUIC baseline"


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

    # The service times are saved as a list, but in this experiment
    # only one service time is saved, so convert to a normal number.
    # Do the same for the corresponding server addresses.
    preprocessed_dataset = preprocessed_dataset.explode("serviceTimes [us]")
    preprocessed_dataset = preprocessed_dataset.explode("serverAddresses")

    # Create a column with the service times expressed in milliseconds.
    preprocessed_dataset["serviceTimes [ms]"] = \
        preprocessed_dataset["serviceTimes [us]"] / 1000

    # Change the name of the protocols to be more clear in the plots.
    preprocessed_dataset["protocol"] = preprocessed_dataset["protocol"] \
        .map(lambda name: convert_protocol_name(name))

    return preprocessed_dataset


def figure_save_path():
    return "plots/exp1_service_times_{}.png".format(str(time.time()))


def set_labels_over_bars(ax, label_height_increments):
    for i, bar in enumerate(ax.patches):
        height_increment = label_height_increments[i]
        ax.annotate(format(bar.get_height(), ".2f"),
                    (bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + height_increment),
                    ha="center", va="center", size=16, xytext=(0, 5),
                    fontweight="bold", textcoords="offset points")


def plot_service_times(dataset, label_height_increases, title):
    plt.figure(figsize=(19.20, 10.80))
    sns.set_style("whitegrid")
    sns.set_palette(sns.color_palette("hls"))

    ax = sns.barplot(x="protocol", y="serviceTimes [ms]", data=dataset,
                     saturation=1, ci=95, estimator=np.mean, capsize=0.05,
                     seed=1, n_boot=1000)
    ax.set_title(title, fontsize=20)
    ax.set_xlabel("QUIC migration protocol", fontsize=20, labelpad=30)
    ax.set_ylabel("Service time [ms]", fontsize=20, labelpad=30)

    ax.tick_params(axis="both", which="major", labelsize=14)
    ax.tick_params(axis="both", which="minor", labelsize=14)
    set_labels_over_bars(ax, label_height_increases)

    plt.yticks(np.arange(0, 3250, 250))
    plt.savefig(figure_save_path(), format="png", dpi=300, bbox_inches="tight")
    plt.show()


def plot_service_times_together(dataset_no_loss, dataset_loss, figsize):
    sns.set_style("whitegrid")
    sns.set_palette(sns.color_palette("hls"))
    f, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize)

    sns.barplot(x="protocol", y="serviceTimes [ms]", data=dataset_no_loss,
                saturation=1, ci=95, estimator=np.mean, capsize=0.05,
                seed=1, n_boot=1000, ax=ax1)
    sns.barplot(x="protocol", y="serviceTimes [ms]", data=dataset_loss,
                saturation=1, ci=95, estimator=np.mean, capsize=0.05,
                seed=1, n_boot=1000, ax=ax2)

    ax1.set_title("No packet loss", fontsize=20)
    ax1.set(xlabel=None)
    ax1.set_ylabel("Service time [ms]", fontsize=20, labelpad=30)
    ax1.tick_params(axis="both", which="major", labelsize=14)
    ax1.tick_params(axis="both", which="minor", labelsize=14)
    set_labels_over_bars(ax1, [80, 80, 100, 120, 180, 80, 80])

    ax2.set_title("Packet loss 3 %", fontsize=20)
    ax2.set_ylabel("Service time [ms]", fontsize=20, labelpad=30)
    ax2.set_xlabel("QUIC migration protocol", fontsize=20, labelpad=30)
    ax2.tick_params(axis="both", which="major", labelsize=14)
    ax2.tick_params(axis="both", which="minor", labelsize=14)
    set_labels_over_bars(ax2, [80, 80, 150, 260, 1060, 80, 80])

    plt.setp(f.axes, yticks=np.arange(0, 3250, 250))
    plt.tight_layout(h_pad=10)
    plt.savefig(figure_save_path(), format="png", dpi=300, bbox_inches="tight")
    plt.show()


def main():
    base_path = "data/nopacketloss/"
    no_packet_loss_paths = {
        "baseline": base_path + "exp0/experiment0_service_times.csv",
        "serviceTimes": base_path + "exp1/experiment1_service_times.csv",
        "migrationTimes": base_path + "exp1/experiment1_migration_times.csv",
        "restoreTimes": base_path + "exp1/experiment1_restore_times.csv"
    }

    base_path = "data/packetloss/"
    packet_loss_paths = {
        "baseline": base_path + "exp0/experiment0_service_times.csv",
        "serviceTimes": base_path + "exp1/experiment1_service_times.csv",
        "migrationTimes": base_path + "exp1/experiment1_migration_times.csv",
        "restoreTimes": base_path + "exp1/experiment1_restore_times.csv"
    }

    dataset_no_loss = parse_dataset(no_packet_loss_paths)
    dataset_loss = parse_dataset(packet_loss_paths)
    preprocessed_dataset_no_loss = preprocess_dataset(dataset_no_loss)
    preprocessed_dataset_loss = preprocess_dataset(dataset_loss)

    os.makedirs("./plots", exist_ok=True)
    plot_service_times(preprocessed_dataset_no_loss,
                       label_height_increases=[40, 40, 60, 80, 140, 40, 40],
                       title="No packet loss")
    plot_service_times(preprocessed_dataset_loss,
                       label_height_increases=[40, 40, 110, 220, 1020, 40, 40],
                       title="Packet loss 3 %")
    plot_service_times_together(preprocessed_dataset_no_loss,
                                preprocessed_dataset_loss,
                                figsize=(19.20, 10.80))


if __name__ == "__main__":
    main()

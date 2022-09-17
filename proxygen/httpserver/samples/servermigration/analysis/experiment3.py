import os
import time
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


def parse_dataset(dataset_path):
    return pd.read_csv(dataset_path)


def preprocess_dataset(dataset):
    preprocessed_dataset = dataset.copy(deep=True)

    # Create a column with the max migration notification time in milliseconds.
    preprocessed_dataset["migrationNotificationTime [ms]"] = \
        preprocessed_dataset["migrationNotificationTime [us]"] / 1000

    # Check if any client closed the connection during the experiment.
    if not preprocessed_dataset["expectedNumberOfClients"] \
            .equals(preprocessed_dataset["actualNumberOfClients"]):
        print("expectedNumberOfClients and actualNumberOfClients do not match. "
              "It looks like some clients disconnected during the experiments."
              "Check the data!")
    else:
        print("expectedNumberOfClients and actualNumberOfClients match")

    return preprocessed_dataset


def figure_save_path():
    return "plots/exp3_migration_notification_times_{}.pdf" \
        .format(str(time.time()))


def plot_migration_notification_times(dataset, title):
    plt.figure(figsize=(19.20, 10.80))
    sns.set_style("whitegrid")
    sns.set_palette(sns.color_palette("Paired"))
    ax = sns.pointplot(data=dataset, x="actualNumberOfClients",
                       y="migrationNotificationTime [ms]", hue="protocol",
                       capsize=0.05, saturation=1, estimator=np.mean, ci=95,
                       seed=1, n_boot=1000)

    ax.set_xlabel("Number of clients", fontsize=20, labelpad=30)
    ax.set_ylabel("Migration notification time [ms]", fontsize=20,
                  labelpad=30)
    ax.tick_params(axis="both", which="major", labelsize=14)
    ax.tick_params(axis="both", which="minor", labelsize=14)
    ax.set_title(title, fontsize=20)

    patches, _ = ax.get_legend_handles_labels()
    ax.legend(handles=patches, loc="upper right", fontsize=15,
              labels=["With SERVER_MIGRATION frame",
                      "Without SERVER_MIGRATION frame"])
    plt.yticks(np.arange(0, 210, 10))
    plt.savefig(figure_save_path(), format="pdf", dpi=300, bbox_inches="tight")
    plt.show()


def plot_migration_notification_times_together(dataset_18, dataset_122):
    plt.figure(figsize=(19.20, 10.80))
    sns.set_style("whitegrid")
    palette = sns.color_palette("Paired")

    sns.pointplot(data=dataset_18, x="actualNumberOfClients",
                  y="migrationNotificationTime [ms]", hue="protocol",
                  capsize=0.05, saturation=1, estimator=np.mean, ci=95,
                  seed=1, n_boot=1000, palette=palette[2:4])

    ax = sns.pointplot(data=dataset_122, x="actualNumberOfClients",
                       y="migrationNotificationTime [ms]", hue="protocol",
                       capsize=0.05, saturation=1, estimator=np.mean, ci=95,
                       seed=1, n_boot=1000, palette=palette[0:2])

    ax.set_xlabel("Number of clients", fontsize=20, labelpad=30)
    ax.set_ylabel("Migration notification time [ms]", fontsize=20,
                  labelpad=30)
    ax.tick_params(axis="both", which="major", labelsize=14)
    ax.tick_params(axis="both", which="minor", labelsize=14)

    patches, _ = ax.get_legend_handles_labels()
    ax.legend(handles=patches, loc="upper center", fontsize=15,
              labels=["18 ms RTT, with SERVER_MIGRATION frame",
                      "18 ms RTT, without SERVER_MIGRATION frame",
                      "122 ms RTT, with SERVER_MIGRATION frame",
                      "122 ms RTT, without SERVER_MIGRATION frame"],
              framealpha=1, bbox_to_anchor=(0.5, 1.05), ncol=2)

    plt.yticks(np.arange(0, 210, 10))
    plt.savefig(figure_save_path(), format="pdf", dpi=300, bbox_inches="tight")
    plt.show()


def main():
    base_path_122 = "data/nopacketloss/exp3/122ms_rtt/"
    dataset_path_122 = \
        base_path_122 + "experiment3_migration_notification_times.csv"
    dataset_122 = parse_dataset(dataset_path_122)
    preprocessed_dataset_122 = preprocess_dataset(dataset_122)

    base_path_18 = "data/nopacketloss/exp3/18ms_rtt/"
    dataset_path_18 = \
        base_path_18 + "experiment3_migration_notification_times.csv"
    dataset_18 = parse_dataset(dataset_path_18)
    preprocessed_dataset_18 = preprocess_dataset(dataset_18)

    os.makedirs("./plots", exist_ok=True)
    plot_migration_notification_times(preprocessed_dataset_18, "18 ms RTT")
    plot_migration_notification_times(preprocessed_dataset_122, "122 ms RTT")
    plot_migration_notification_times_together(preprocessed_dataset_18,
                                               preprocessed_dataset_122)


if __name__ == "__main__":
    main()

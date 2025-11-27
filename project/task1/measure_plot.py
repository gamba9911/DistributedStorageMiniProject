import os
import time
import csv
import requests
from collections import defaultdict
import statistics as stats
import matplotlib.pyplot as plt

BASE_URL = "http://localhost:9000"

N_MEASUREMENTS = 100

FILE_SIZES = [
    ("100kB", 100 * 1024),
    ("1MB", 1 * 1024 * 1024),
    ("10MB", 10 * 1024 * 1024),
    ("100MB", 100 * 1024 * 1024),
]

MEAS_PATH = "measure.csv"


def log_measurement(path, row):

    new_file = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(
                ["timestamp", "file_id", "filename",
                "size_bytes", "metric", "value_sec"]
            )
        writer.writerow(row)

def upload_file(size_label: str, data: bytes, run_idx: int) -> int:

    filename = f"bench_{size_label}_{run_idx}.bin"
    files = {
        "file": (filename, data, "application/octet-stream"),
    }

    resp = requests.post(f"{BASE_URL}/files", files=files)
    resp.raise_for_status()
    file_id = resp.json()["id"]
    return file_id,filename,len(data)


def download_file(file_id: int,filename,size) -> None:

    t0 = time.time()  
    resp = requests.get(f"{BASE_URL}/files/{file_id}")
    resp.raise_for_status()
    _ = resp.content
    t1 = time.time()
    download_time = t1 - t0
    log_measurement(MEAS_PATH,[time.time(), file_id, filename, size, "download", download_time])  


def run_measurements():

    print("Starting measurements...")
    start_ts = time.time()  

    for size_label, size_bytes in FILE_SIZES:

        data = os.urandom(size_bytes)
        for i in range(N_MEASUREMENTS):

            file_id,filename,size = upload_file(size_label, data, i)
            download_file(file_id,filename,size)
        print(f"\n  Done {N_MEASUREMENTS} uploads+downloads for {size_label}")

    print("\nAll measurements done.")
    return start_ts


def load_measurements(since_ts: float):

    replication = defaultdict(list)  # size_bytes -> [times]
    download = defaultdict(list)     # size_bytes -> [times]

    with open(MEAS_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = float(row["timestamp"])
            if ts < since_ts:
                continue  

            size = int(row["size_bytes"])
            metric = row["metric"]
            value = float(row["value_sec"])

            if metric == "replication":
                replication[size].append(value)
            elif metric == "download":
                download[size].append(value)

    return replication, download


def plot_histograms(data_dict, metric_name: str):

    for size_label, size_bytes in FILE_SIZES:
        times = data_dict.get(size_bytes, [])
        if not times:
            print(f"No {metric_name} data for size {size_label}")
            continue

        mean_v = stats.mean(times)
        median_v = stats.median(times)

        plt.figure()
        plt.hist(times, bins=20)
        plt.axvline(mean_v, linestyle="dashed", linewidth=1,
                    label=f"mean={mean_v:.4f}s")
        plt.axvline(median_v, linestyle="dotted", linewidth=1,
                    label=f"median={median_v:.4f}s")
        plt.title(f"{metric_name.capitalize()} time histogram ({size_label})")
        plt.xlabel("Time (s)")
        plt.ylabel("Count")
        plt.legend()
        plt.tight_layout()

        out_name = f"hist_{metric_name}_{size_label}.png"
        plt.savefig(out_name)
        plt.close()
        print(f"Saved {out_name}")


def main():

    start_ts = run_measurements()
    print("Measurements done")

    replication, download = load_measurements(start_ts)
    plot_histograms(replication, "replication")
    plot_histograms(download, "download")


if __name__ == "__main__":
    main()

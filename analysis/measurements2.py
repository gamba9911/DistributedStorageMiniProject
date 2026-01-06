import os
import time
import uuid
import csv
import requests
import matplotlib.pyplot as plt

# =============================
# CONFIGURATION
# =============================
API_URL = "http://127.0.0.1:5000"

TEST_RUNS = 10   # not 100 like task 1 specifies, to save time
FILE_SIZES = [
    ("100KB", 100_000),
    ("1MB", 1_000_000),
    ("10MB", 10_000_000),
    ("100MB", 100_000_000),
]

STRATEGIES = ["random", "min_copysets", "buddy"]

C = 4   # erasure parameter c
L = 2   # erasure parameter l

OUTPUT_DIR = "testData_task2_N24"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = "task2_results_24.csv"


# =============================
# HELPERS
# =============================

def generate_test_file(size_bytes: int, path: str):
    with open(path, "wb") as f:
        f.write(os.urandom(size_bytes))


def upload_coded(filepath: str, strategy: str):
    """
    Store file using erasure coding.
    Measure ingest time.
    """
    with open(filepath, "rb") as f:
        start = time.perf_counter()
        r = requests.post(
            f"{API_URL}/store_coded",
            files={"file": f},
            data={"c": C, "l": L, "strategy": strategy},
        )
        end = time.perf_counter()

    if r.status_code != 201:
        raise RuntimeError(f"store_coded failed: {r.status_code} {r.text}")

    object_id = r.json()["object_id"]
    return object_id, end - start


def download_coded(object_id: str):
    """
    Retrieve coded file and measure download time.
    """
    start = time.perf_counter()
    r = requests.get(f"{API_URL}/retrieve_coded/{object_id}")
    end = time.perf_counter()

    if r.status_code != 200:
        raise RuntimeError(f"retrieve_coded failed: {r.status_code} {r.text}")

    # we discard the content here, only time matters
    _ = r.content
    return end - start


# =============================
# MAIN EXPERIMENT
# =============================

def run_experiments():
    results = []

    print("\n🚀 Starting Task 2 (erasure coding) Measurement Tests")

    for label, size in FILE_SIZES:
        testfile = f"test_{label}.bin"
        print(f"\n📌 Creating file: {label} ({size/1e6:.2f} MB)")
        generate_test_file(size, testfile)

        for strategy in STRATEGIES:
            ingest_times = []
            download_times = []

            print(f"\n➡️ Strategy={strategy} | File={label} | c={C}, l={L}")

            for run in range(TEST_RUNS):
                print(f"   Run {run+1}/{TEST_RUNS}...", end="", flush=True)

                object_id, ingest_t = upload_coded(testfile, strategy)
                dl_t = download_coded(object_id)

                ingest_times.append(ingest_t)
                download_times.append(dl_t)

                print(f" ingest={ingest_t:.3f}s | download={dl_t:.3f}s")

                results.append([
                    label,
                    size,
                    strategy,
                    C,
                    L,
                    ingest_t,
                    dl_t,
                ])

            # ---- Plot histograms ----
            # Ingest
            plt.figure()
            plt.hist(ingest_times, bins=8)
            plt.title(f"EC Ingest Times – {label} – {strategy}")
            plt.xlabel("seconds")
            plt.ylabel("frequency")
            plt.savefig(os.path.join(OUTPUT_DIR, f"ec_ingest_{label}_{strategy}.png"))
            plt.close()

            # Download
            plt.figure()
            plt.hist(download_times, bins=8)
            plt.title(f"EC Download Times – {label} – {strategy}")
            plt.xlabel("seconds")
            plt.ylabel("frequency")
            plt.savefig(os.path.join(OUTPUT_DIR, f"ec_download_{label}_{strategy}.png"))
            plt.close()

    # =============================
    # SAVE RESULTS TO CSV
    # =============================
    csv_path = os.path.join(OUTPUT_DIR, OUTPUT_CSV)
    print(f"\n💾 Saving Task 2 results to {csv_path}")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "file_label",
            "file_size_bytes",
            "strategy",
            "c",
            "l",
            "ingest_time_s",
            "download_time_s",
        ])
        writer.writerows(results)

    print("\n🎉 Task 2 measurement completed!")
    print(f"📁 Check output in folder: {OUTPUT_DIR}/")
    print("📊 CSV + histograms ready\n")


if __name__ == "__main__":
    run_experiments()

import os
import time
import uuid
import requests
import csv
import matplotlib.pyplot as plt

# =============================
# CONFIGURATION
# =============================
API_URL = "http://127.0.0.1:5000"
TEST_RUNS = 10                   # set to 100 for final assignment
FILE_SIZES = [
    ("100KB", 100_000),
    ("1MB", 1_000_000),
    ("10MB", 10_000_000),
    ("100MB", 100_000_000),
]
STRATEGIES = ["random", "min_copysets", "buddy"]
K = 3
OUTPUT_CSV = "task1_results.csv"

# ---- Output folder for plots + csv ----
OUTPUT_DIR = "testData"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# =============================
# HELPER FUNCTIONS
# =============================

def generate_test_file(size_bytes: int, path: str):
    """Create a random binary file for testing."""
    with open(path, "wb") as f:
        f.write(os.urandom(size_bytes))


def upload_file(filepath: str, strategy: str):
    """Store file → return object_id and ingest time."""
    with open(filepath, "rb") as f:
        start = time.perf_counter()
        r = requests.post(
            f"{API_URL}/store",
            files={"file": f},
            data={"k": K, "strategy": strategy}
        )
        end = time.perf_counter()
    if r.status_code != 201:
        raise RuntimeError(f"Upload failed: {r.text}")
    object_id = r.json()["object_id"]
    return object_id, end - start


def download_file(object_id: str):
    """Retrieve file → return download time."""
    start = time.perf_counter()
    r = requests.get(f"{API_URL}/retrieve/{object_id}")
    end = time.perf_counter()
    if r.status_code != 200:
        raise RuntimeError(f"Download failed: {r.text}")
    return end - start


# =============================
# MEASUREMENT RUNNER
# =============================

def run_experiments():
    results = []

    print("\n🚀 Starting Task 1 Measurement Tests")

    for label, size in FILE_SIZES:
        testfile = f"test_{label}.bin"
        print(f"\n📌 Creating file: {label} ({size/1e6:.2f} MB)")
        generate_test_file(size, testfile)

        for strategy in STRATEGIES:
            ingest_times = []
            download_times = []

            print(f"\n➡️ Strategy={strategy} | File={label}")

            for run in range(TEST_RUNS):
                print(f"   Run {run+1}/{TEST_RUNS}...", end="", flush=True)

                object_id, ingest_t = upload_file(testfile, strategy)
                dl_t = download_file(object_id)

                ingest_times.append(ingest_t)
                download_times.append(dl_t)

                print(f" ingest={ingest_t:.3f}s | download={dl_t:.3f}s")

                results.append([
                    label, size, strategy, ingest_t, dl_t
                ])

            # Ingest
            plt.figure()
            plt.hist(ingest_times, bins=8)
            plt.title(f"Ingest Times – {label} – {strategy}")
            plt.xlabel("seconds")
            plt.ylabel("frequency")
            plt.savefig(os.path.join(OUTPUT_DIR, f"hist_ingest_{label}_{strategy}.png"))
            plt.close()

            # Download
            plt.figure()
            plt.hist(download_times, bins=8)
            plt.title(f"Download Times – {label} – {strategy}")
            plt.xlabel("seconds")
            plt.ylabel("frequency")
            plt.savefig(os.path.join(OUTPUT_DIR, f"hist_download_{label}_{strategy}.png"))
            plt.close()

    # =============================
    # SAVE RESULTS TO CSV
    # =============================
    csv_path = os.path.join(OUTPUT_DIR, OUTPUT_CSV)
    print(f"\n💾 Saving results to {csv_path}")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["file_label", "file_size_bytes", "strategy", "ingest_time_s", "download_time_s"])
        writer.writerows(results)

    print("\n🎉 Measurement completed!")
    print(f"📁 Check output in folder: {OUTPUT_DIR}/")
    print("📊 CSV + histograms ready.\n")


if __name__ == "__main__":
    run_experiments()

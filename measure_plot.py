import os
import time
import csv
import requests
import subprocess
import sys
import matplotlib.pyplot as plt
import random

BASE_URL = "http://localhost:9000"

N_MEASUREMENTS = 100

FILE_SIZES = 1 * 1024 * 1024

S_VALUES = [2, 3, 4, 6, 8]


NODE_NAMES_ENV = os.getenv(
    "NODE_NAMES",
    "node1,node2,node3,node4,node5,node6,node7,node8,node9,node10,node11,node12"
)
NODE_NAMES = [n.strip() for n in NODE_NAMES_ENV.split(",") if n.strip()]

def start_storage_nodes():

    node_procs = []
    script_dir = os.path.dirname(os.path.abspath(__file__))
    storage_node_path = os.path.join(script_dir, "storage-node.py")

    for name in NODE_NAMES:
        os.makedirs(name, exist_ok=True)

        cmd = [sys.executable, storage_node_path, name]
        env = os.environ.copy()

        print(f"Starting storage node {name}: {cmd}")
        p = subprocess.Popen(cmd, env=env)
        node_procs.append({"name": name, "proc": p})

    time.sleep(2)
    return node_procs

def kill_nodes_to_reach_s(target_s, node_procs):

    dead = [np for np in node_procs if np["proc"].poll() is not None]
    dead_count = len(dead)

    if dead_count >= target_s:
        print(f"Already have {dead_count} dead nodes, no need to kill more.")
        return []

    need_to_kill = target_s - dead_count

    alive = [np for np in node_procs if np["proc"].poll() is None]
    if need_to_kill > len(alive):
        need_to_kill = len(alive)

    victims = random.sample(alive, need_to_kill)

    killed_names = []
    for v in victims:
        print(f"Killing node {v['name']} (PID {v['proc'].pid}) to reach s={target_s}")
        try:
            v["proc"].terminate()
        except Exception as e:
            print(f"Error terminating {v['name']}: {e}")
        killed_names.append(v["name"])

    return killed_names

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

def upload_file():

    file_ids = []
    for i in range(N_MEASUREMENTS):
        data = os.urandom(FILE_SIZES)
        files = {
            "file": (f"file_{i}.bin", data),
        }
        form = {
            "filename": f"file_{i}.bin",
            "content_type": "application/octet-stream",
            "storage_mode": "replication",
        }

        resp = requests.post(f"{BASE_URL}/files", files=files, data=form, timeout=60)
        resp.raise_for_status()
        file_id = resp.json()["id"]
        file_ids.append(file_id)
        print(f"Uploaded file {i+1}/{N_MEASUREMENTS}, id={file_id}")
    return file_ids

def wait_for_s_and_measure(target_s, poll_interval=1.0):

    url = f"{BASE_URL}/services/loss_fraction"

    while True:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        dead_nodes = data.get("dead_nodes", [])
        current_s = len(dead_nodes)

        print(
            f"[s={target_s}] waiting for {target_s} dead nodes, "
            f"currently {current_s} ...",
            end="\r",
            flush=True,
        )

        if current_s == target_s:
            print()  
            return data

        time.sleep(poll_interval)


def run_measurements():

    print("Starting storage nodes ...")
    node_procs = start_storage_nodes()

    print("Resetting database ...")
    requests.post(f"{BASE_URL}/services/reset_db", timeout=10)

    try:
        print(f"\nUploading {N_MEASUREMENTS} files of {FILE_SIZES} bytes each ...")
        upload_file()
        print("Upload done.\n")

        results = {}

        for s in S_VALUES:
            print("=" * 40)
            print(f"Now measuring loss fraction for s = {s}")

            killed = kill_nodes_to_reach_s(s, node_procs)
            if killed:
                print(f"Killed nodes for this step: {killed}")
            else:
                print("No additional nodes killed in this step.")


            info = wait_for_s_and_measure(s)
            frac = info.get("lost_fraction", 0.0)
            lost_files = info.get("lost_files", 0)
            total_files = info.get("total_files", 0)

            print(
                f"s = {s}: lost_fraction = {frac:.4f} "
                f"({lost_files}/{total_files} files lost)"
            )

            results[s] = {
                "lost_fraction": frac,
                "lost_files": lost_files,
                "total_files": total_files,
                "dead_nodes": info.get("dead_nodes", []),
                "live_nodes": info.get("live_nodes", []),
            }

        return results

    finally:
        print("\nShutting down storage nodes ...")
        for np in node_procs:
            if np["proc"].poll() is None:
                try:
                    np["proc"].terminate()
                except Exception as e:
                    print(f"Error terminating {np['name']}: {e}")



def plot_results(results):

    s_vals = sorted(results.keys())
    fracs = [results[s]["lost_fraction"] for s in s_vals]

    plt.figure()
    plt.bar([str(s) for s in s_vals], fracs)
    plt.xlabel("s (number of dead nodes)")
    plt.ylabel("Fraction of lost files")
    plt.ylim(0, 1)
    plt.title("Replication: fraction of lost files vs s")
    plt.tight_layout()
    placement = os.getenv("PLACEMENT_MODE", "unknown")
    img_name = f"loss_plot_{placement}_k=3.png"
    plt.savefig(img_name, dpi=150)
    plt.show()


def main():

    results = run_measurements()
    print("Measurements done")

    for s in sorted(results.keys()):
        print(f"s = {s}: lost_fraction = {results[s]['lost_fraction']:.4f}")

    plot_results(results)

    placement = os.getenv("PLACEMENT_MODE", "unknown")
    csv_name = f"results_{placement}.csv"

    with open(csv_name, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["placement_mode", "s", "lost_fraction", "lost_files", "total_files"])

        for s in sorted(results.keys()):
            r = results[s]
            writer.writerow([
                placement,
                s,
                r["lost_fraction"],
                r["lost_files"],
                r["total_files"]
            ])

    print(f"\nCSV saved to: {csv_name}")

if __name__ == "__main__":
    main()

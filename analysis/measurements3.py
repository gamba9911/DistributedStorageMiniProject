import os
import time
import uuid
import requests
import matplotlib.pyplot as plt

from control.cluster_controller import ClusterController

import shutil

DATA_DIR = "data"

def cleanup_data_dir():
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)
        print("[CLEANUP] removed data/ directory")

API = "http://127.0.0.1:5000"
OUTDIR = "testData_task3_buddy"
os.makedirs(OUTDIR, exist_ok=True)

S_VALUES = [2, 3, 4, 6, 8]
STRATEGIES = ["buddy"]
#STRATEGIES = ["random", "min_copysets", "buddy"]

FILE_COUNT = 100
FILE_SIZE = 1_000_000  # 1MB


def make_file(path: str, size: int):
    with open(path, "wb") as f:
        f.write(os.urandom(size))


def store_files_replication(strategy: str, k: int) -> list[str]:
    ids = []
    for _ in range(FILE_COUNT):
        object_id = None
        with open("task3.bin", "rb") as f:
            r = requests.post(f"{API}/store", files={"file": f}, data={"k": k, "strategy": strategy})
        if r.status_code != 201:
            raise RuntimeError(f"store failed: {r.status_code} {r.text}")
        object_id = r.json()["object_id"]
        ids.append(object_id)
    return ids


def store_files_coded(strategy: str, c: int, l: int) -> list[str]:
    ids = []
    for _ in range(FILE_COUNT):
        with open("task3.bin", "rb") as f:
            r = requests.post(f"{API}/store_coded", files={"file": f}, data={"c": c, "l": l, "strategy": strategy})
        if r.status_code != 201:
            raise RuntimeError(f"store_coded failed: {r.status_code} {r.text}")
        ids.append(r.json()["object_id"])
    return ids


def fraction_lost_replication(object_ids: list[str]) -> float:
    lost = 0
    for oid in object_ids:
        r = requests.get(f"{API}/retrieve/{oid}")
        if r.status_code != 200:
            lost += 1
    return lost / len(object_ids)


def fraction_lost_coded(object_ids: list[str]) -> float:
    lost = 0
    for oid in object_ids:
        r = requests.get(f"{API}/retrieve_coded/{oid}")
        if r.status_code != 200:
            lost += 1
    return lost / len(object_ids)


def run_for_N(N: int):
    make_file("task3.bin", FILE_SIZE)
    results = []

    for strategy in STRATEGIES:
        for s in S_VALUES:
            print(f"Running N={N}, strategy={strategy}, s={s}")
            # Start fresh cluster for this (strategy, s)
            ctrl = ClusterController()
            ctrl.start_nodes(N)
            ctrl.start_lead_api(N)
            time.sleep(2)

            # Store files while all nodes are alive
            rep_ids = store_files_replication(strategy=strategy, k=3)
            ec_ids_l2 = store_files_coded(strategy=strategy, c=4, l=2)
            ec_ids_l3 = store_files_coded(strategy=strategy, c=4, l=3)

            # Kill exactly s nodes
            ctrl.stop_random_nodes(s)

            # Measure loss
            rep_loss = fraction_lost_replication(rep_ids)
            ec_loss_l2 = fraction_lost_coded(ec_ids_l2)
            ec_loss_l3 = fraction_lost_coded(ec_ids_l3)

            results.append((N, strategy, "rep_k3", s, rep_loss))
            results.append((N, strategy, "ec_c4_l2", s, ec_loss_l2))
            results.append((N, strategy, "ec_c4_l3", s, ec_loss_l3))

            # Stop everything before next s
            ctrl.stop_all()
            cleanup_data_dir()
            time.sleep(1)

    return results



def plot_results(all_results):
    # simple plot: one figure per N, lines per system+strategy
    Ns = sorted(set(r[0] for r in all_results))

    for N in Ns:
        subset = [r for r in all_results if r[0] == N]
        plt.figure()
        for strategy in STRATEGIES:
            for sysname in ["rep_k3", "ec_c4_l2", "ec_c4_l3"]:
                ys = []
                for s in S_VALUES:
                    v = [r for r in subset if r[1] == strategy and r[2] == sysname and r[3] == s][0]
                    ys.append(v[4])
                plt.plot(S_VALUES, ys, marker="o", label=f"{sysname}-{strategy}")

        plt.xlabel("s (nodes removed)")
        plt.ylabel("fraction of files lost")
        plt.title(f"Task 3: Loss fraction vs removed nodes (N={N})")
        plt.legend(fontsize=7)
        plt.savefig(os.path.join(OUTDIR, f"task3_loss_fraction_N{N}.png"), dpi=150)
        plt.close()


if __name__ == "__main__":
    all_results = []
    for N in [12, 24, 36]:
        all_results.extend(run_for_N(N))

    plot_results(all_results)
    print(f"Done. Plots in {OUTDIR}/")

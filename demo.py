import os

from dsm.lead import LeadNodeSocket
from dsm.config import PlacementStrategy


def main():
    # Config: 6 nodes, each running node_server.py on a different port
    node_addresses = {
        0: ("127.0.0.1", 6000),
        1: ("127.0.0.1", 6001),
        2: ("127.0.0.1", 6002),
        3: ("127.0.0.1", 6003),
        4: ("127.0.0.1", 6004),
        5: ("127.0.0.1", 6005),
    }

    N = len(node_addresses)
    k = 3
    file_id = "file001"
    file_path = "test.bin"

    # create a test file if it doesn't exist
    if not os.path.exists(file_path):
        with open(file_path, "wb") as f:
            f.write(os.urandom(200_000))  # ~200 KB

    lead = LeadNodeSocket(node_addresses=node_addresses)

    strategy = PlacementStrategy.BUDDY  # or RANDOM / MIN_COPYSETS

    placement_info = lead.store_file(
        file_id=file_id,
        file_path=file_path,
        replica_count=k,
        strategy=strategy,
    )

    print("\n=== Placement Result (socket-based) ===")
    print(placement_info)
    print("\nCheck the data/node_*/ directories created by each node_server.py process.")


if __name__ == "__main__":
    main()

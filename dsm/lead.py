import pickle
import socket
from typing import List, Dict, Tuple

from dsm.config import NUM_FRAGMENTS, PlacementStrategy
from dsm.file_utils import split_file_into_fragments
from dsm.placement import StrategySelector


class LeadNodeSocket:
    """
    Lead/coordinator that sends fragments to nodes over TCP sockets.
    - Does NOT assume local directories; nodes are separate processes.
    - Knows node addresses: {node_id: (host, port)}.
    """

    def __init__(self, node_addresses: Dict[int, Tuple[str, int]]):
        """
        node_addresses: mapping node_id -> (host, port)
        """
        self.node_addresses = node_addresses
        self.node_ids = sorted(node_addresses.keys())
        self.selector = StrategySelector(self.node_ids)

    def _send_fragment_to_node(
        self,
        node_id: int,
        file_id: str,
        fragment_idx: int,
        replica_idx: int,
        data: bytes,
    ):
        """
        Open a TCP connection to the given node and send a 'store_fragment' message.
        """
        host, port = self.node_addresses[node_id]

        # Build message object
        msg = {
            "op": "store_fragment",
            "file_id": file_id,
            "fragment_idx": fragment_idx,
            "replica_idx": replica_idx,
            "data": data,
        }

        payload = pickle.dumps(msg)
        length = len(payload)
        header = length.to_bytes(8, byteorder="big")

        with socket.create_connection((host, port)) as sock:
            sock.sendall(header + payload)
            try:
                sock.recv(2)
            except Exception:
                pass  # ignore if no ACK

    def store_file(
        self,
        file_id: str,
        file_path: str,
        replica_count: int,
        strategy: PlacementStrategy = PlacementStrategy.RANDOM,
    ):
        """
        Split the file into NUM_FRAGMENTS, select nodes for each fragment
        according to 'strategy', and send fragments to nodes over sockets.
        """
        fragments = split_file_into_fragments(file_path, NUM_FRAGMENTS)

        placement_info = {
            "file_id": file_id,
            "strategy": strategy.value,
            "replicas_per_fragment": replica_count,
            "fragments": [],
        }

        for frag_idx, frag_data in enumerate(fragments):
            # Decide which nodes will store this fragment's replicas
            selected_nodes = self.selector.select_nodes(
                file_id=file_id,
                fragment_idx=frag_idx,
                k=replica_count,
                strategy=strategy,
            )

            placement_info["fragments"].append({
                "fragment": frag_idx,
                "nodes": selected_nodes,
            })

            # Send to each selected node
            for rep_idx, node_id in enumerate(selected_nodes):
                self._send_fragment_to_node(
                    node_id=node_id,
                    file_id=file_id,
                    fragment_idx=frag_idx,
                    replica_idx=rep_idx,
                    data=frag_data,
                )

        return placement_info

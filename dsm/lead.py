import os
import pickle
import socket
from pathlib import Path
from typing import Dict, List, Tuple

from dsm.config import (
    NUM_FRAGMENTS,
    PlacementStrategy,
    ERASURE_C,
    ERASURE_L,
)
from dsm.file_utils import split_file_into_fragments
from dsm.placement import StrategySelector
from dsm.erasure_coding import ErasureCoder, ErasureMeta, CodedFragment


class LeadNodeSocket:
    """
    Lead/coordinator that:
      - exposes store/reconstruct operations for replicated files (Task 1)
      - exposes store/reconstruct operations for erasure-coded files (Task 2)
      - sends fragments to nodes over TCP sockets using a simple binary protocol
    """

    def __init__(self, node_addresses: Dict[int, Tuple[str, int]]):
        """
        node_addresses: mapping node_id -> (host, port)
        """
        self.node_addresses = node_addresses
        self.node_ids = sorted(node_addresses.keys())
        self.selector = StrategySelector(self.node_ids)

        # for erasure-coded files (Task 2)
        # file_id -> placement + meta
        self.coded_metadata: Dict[str, dict] = {}

    # =========================================================
    # Low-level node communication
    # =========================================================

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
        The node.py process must understand this protocol.
        """
        host, port = self.node_addresses[node_id]

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
            # Optional: read a tiny ACK
            try:
                sock.recv(2)
            except Exception:
                # ignore if no ack
                pass

    # =========================================================
    # Task 1: Replication-based storage
    # =========================================================

    def store_file(
        self,
        file_id: str,
        file_path: str,
        replica_count: int,
        strategy: PlacementStrategy = PlacementStrategy.RANDOM,
    ) -> dict:
        """
        Split the file into NUM_FRAGMENTS, select nodes for each fragment
        according to 'strategy', and send fragments to nodes over sockets.
        """
        fragments = split_file_into_fragments(file_path, NUM_FRAGMENTS)

        placement_info = {
            "file_id": file_id,
            "strategy": strategy.value,
            "replicas_per_fragment": replica_count,
            "fragments": [],  # list of {fragment, nodes}
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

    def reconstruct_file(
        self,
        file_id: str,
        placement_info: dict,
        data_dir_base: str = "data"
    ) -> bytes:
        """
        Reconstruct a replicated file (Task 1) using the placement_info
        returned by store_file(...).

        Assumes fragments are stored as:
          {data_dir_base}/node_<node_id>/<file_id>_frag<frag_idx>_rep0.bin

        For each fragment, we read replica_idx = 0 from the first node THAT IS ALIVE
        in the node candidte list.
        """
        fragments_data: List[bytes] = []

        for frag_meta in placement_info["fragments"]:
            frag_idx = frag_meta["fragment"]
            candidates = frag_meta["nodes"]

            frag_bytes = None

            for rep_idx, node_id in enumerate(candidates):
                # optional: skip dead nodes early
                if not self.is_node_alive(node_id):
                    continue

                fragment_path = Path(data_dir_base) / f"node_{node_id}" / f"{file_id}_frag{frag_idx}_rep{rep_idx}.bin"
                if fragment_path.exists():
                    frag_bytes = fragment_path.read_bytes()
                    break

            if frag_bytes is None:
                raise RuntimeError(f"File lost: no surviving replica for fragment {frag_idx}")

            fragments_data.append(frag_bytes)

        return b"".join(fragments_data)

    # =========================================================
    # Task 2: Erasure-coded storage
    # =========================================================

    def store_coded_file(
        self,
        file_id: str,
        file_path: str,
        c: int = ERASURE_C,
        l: int = ERASURE_L,
        strategy: PlacementStrategy = PlacementStrategy.RANDOM,
    ) -> dict:
        """
        Encode the file using erasure coding (c data + l coded fragments)
        and place EACH coded fragment on exactly one node according to
        the chosen strategy.

        Returns a placement dictionary for reporting/measurements.
        """
        # Read file
        with open(file_path, "rb") as f:
            data = f.read()

        coder = ErasureCoder(c=c, l=l)
        meta, coded_frags = coder.encode(data)

        placement_info = {
            "file_id": file_id,
            "strategy": strategy.value,
            "c": c,
            "l": l,
            "fragments": [],   # list of {frag_id, node_id, kind, symbol_index, coeffs_hex}
            "meta": {
                "c": meta.c,
                "l": meta.l,
                "symbol_bytes": meta.symbol_bytes,
                "data_len": meta.data_len,
            },
        }

        # Place each coded fragment on a node
        for frag in coded_frags:
            # For Task 2: exactly ONE node per coded fragment.
            selected_nodes = self.selector.select_nodes(
                file_id=file_id,
                fragment_idx=frag.frag_id,
                k=1,
                strategy=strategy,
            )
            node_id = selected_nodes[0]

            # write to node (replica_idx = 0)
            self._send_fragment_to_node(
                node_id=node_id,
                file_id=file_id,
                fragment_idx=frag.frag_id,
                replica_idx=0,
                data=frag.data,
            )

            placement_info["fragments"].append({
                "frag_id": frag.frag_id,
                "node_id": node_id,
                "kind": frag.kind,
                "symbol_index": frag.symbol_index,
                "coeffs_hex": frag.coeffs.hex() if frag.coeffs is not None else None,
            })

        # Remember everything for decode/retrieve
        self.coded_metadata[file_id] = placement_info
        return placement_info

    def reconstruct_coded_file(self, file_id: str, data_dir_base: str = "data") -> bytes:
        """
        Reconstruct an erasure-coded file using the coded fragments stored on nodes.

        Assumes fragments are stored on disk by node_server.py as:
          {data_dir_base}/node_<node_id>/<file_id>_frag<frag_id>_rep0.bin

        We use whatever fragments are available; decoding succeeds as long
        as we have at least c linearly independent symbols.
        """
        info = self.coded_metadata.get(file_id)
        if info is None:
            raise KeyError(f"No coded metadata for file_id={file_id}")

        meta_dict = info["meta"]
        meta = ErasureMeta(
            c=meta_dict["c"],
            l=meta_dict["l"],
            symbol_bytes=meta_dict["symbol_bytes"],
            data_len=meta_dict["data_len"],
        )

        fragments: List[CodedFragment] = []

        for frag_meta in info["fragments"]:
            node_id = frag_meta["node_id"]
            frag_id = frag_meta["frag_id"]
            kind = frag_meta["kind"]
            symbol_index = frag_meta["symbol_index"]
            coeffs_hex = frag_meta["coeffs_hex"]

            node_dir = os.path.join(data_dir_base, f"node_{node_id}")
            fragment_filename = f"{file_id}_frag{frag_id}_rep0.bin"
            fragment_path = os.path.join(node_dir, fragment_filename)

            if not os.path.exists(fragment_path):
                # Node lost or fragment missing – skip, decoder will use others
                continue

            with open(fragment_path, "rb") as f:
                data = f.read()

            coeffs = bytes.fromhex(coeffs_hex) if coeffs_hex is not None else None
            fragments.append(
                CodedFragment(
                    frag_id=frag_id,
                    data=data,
                    kind=kind,
                    symbol_index=symbol_index,
                    coeffs=coeffs,
                )
            )

        coder = ErasureCoder(c=meta.c, l=meta.l)
        return coder.decode(meta, fragments)

    def is_node_alive(self, node_id: int, timeout: float = 0.2) -> bool:
        host, port = self.node_addresses[node_id]
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                msg = {"op": "ping"}
                payload = pickle.dumps(msg)
                sock.sendall(len(payload).to_bytes(8, "big") + payload)
                resp = sock.recv(2)
                return resp == b"OK"
        except Exception:
            return False

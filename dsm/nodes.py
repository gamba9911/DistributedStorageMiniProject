from pathlib import Path


class StorageNode:
    """
    A "node" in our storage system — represented as a folder on disk.
    """

    def __init__(self, node_id: int, base_dir: str = "data"):
        self.node_id = node_id
        self.base_dir = Path(base_dir) / f"node_{node_id}"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store_fragment(self, file_id: str, fragment_idx: int, replica_idx: int, data: bytes):
        """
        Store a fragment as a binary file.
        """
        filename = f"{file_id}_frag{fragment_idx}_rep{replica_idx}.bin"
        path = self.base_dir / filename
        path.write_bytes(data)

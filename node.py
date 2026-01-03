import argparse
import os
import pickle
import socket
import socketserver
from pathlib import Path


class NodeRequestHandler(socketserver.BaseRequestHandler):
    """
    Handles incoming TCP connections for one storage node.
    Protocol:
      - client sends 8-byte big-endian length header
      - then that many bytes of pickled Python object: {"op": "...", ...}
    """

    def handle(self):
        length_bytes = self._read_exact(8)
        if len(length_bytes) < 8:
            return

        msg_len = int.from_bytes(length_bytes, byteorder="big")
        payload = self._read_exact(msg_len)
        if len(payload) < msg_len:
            return

        msg = pickle.loads(payload)

        op = msg.get("op")
        if op == "ping":
            self.request.sendall(b"OK")
            return
        if op == "store_fragment":
            self._handle_store_fragment(msg)
            return
        self.request.sendall(b"??")


    def _read_exact(self, n: int) -> bytes:
        """
        Read exactly n bytes from the socket (or less if connection closes).
        """
        data = b""
        while len(data) < n:
            chunk = self.request.recv(n - len(data))
            if not chunk:
                break
            data += chunk
        return data

    def _handle_store_fragment(self, msg: dict):
        """
        Store fragment on disk in this node's base_dir.
        """
        file_id = msg["file_id"]
        fragment_idx = msg["fragment_idx"]
        replica_idx = msg["replica_idx"]
        data = msg["data"]

        server: "NodeTCPServer" = self.server  # type: ignore
        base_dir: Path = server.base_dir

        filename = f"{file_id}_frag{fragment_idx}_rep{replica_idx}.bin"
        path = base_dir / filename
        path.write_bytes(data)

        # Optional: send back a simple ACK
        self.request.sendall(b"OK")


class NodeTCPServer(socketserver.ThreadingTCPServer):
    """
    Custom TCP server that holds node-specific metadata (node_id, base_dir).
    """
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, node_id: int, base_dir: str):
        super().__init__(server_address, RequestHandlerClass)
        self.node_id = node_id
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True, help="Node ID")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument("--basedir", type=str, default="data", help="Base directory for all nodes")

    args = parser.parse_args()

    # Each node stores its data in baseDir/node_<id>
    node_dir = os.path.join(args.basedir, f"node_{args.id}")

    server = NodeTCPServer(
        server_address=("0.0.0.0", args.port),
        RequestHandlerClass=NodeRequestHandler,
        node_id=args.id,
        base_dir=node_dir,
    )

    print(f"[Node {args.id}] Listening on port {args.port}, storing data in {node_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"[Node {args.id}] Shutting down.")


if __name__ == "__main__":
    main()

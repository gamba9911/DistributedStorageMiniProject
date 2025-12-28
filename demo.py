from flask import Flask, request, jsonify, send_file, abort
import os
import uuid
from pathlib import Path

from dsm.lead import LeadNodeSocket
from dsm.config import PlacementStrategy

app = Flask(__name__)

# ---- Where the original uploaded files are stored temporarily ----
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---- Where node_server.py stores its data (data/node_<id>/...) ----
DATA_BASE_DIR = "data"

# ---- Configure your nodes (must match the ports for node_server.py) ----
NODE_ADDRESSES = {
    0: ("127.0.0.1", 6000),
    1: ("127.0.0.1", 6001),
    2: ("127.0.0.1", 6002),
    3: ("127.0.0.1", 6003),
    4: ("127.0.0.1", 6004),
    5: ("127.0.0.1", 6005),
}

# This LeadNodeSocket *is* your lead node and coordinator
lead = LeadNodeSocket(node_addresses=NODE_ADDRESSES)

# Keep placement metadata in memory
PLACEMENTS: dict[str, dict] = {}


def parse_strategy(name: str) -> PlacementStrategy:
    name = name.lower()
    if name == "random":
        return PlacementStrategy.RANDOM
    if name in ("min", "copyset", "copysets", "min_copysets"):
        return PlacementStrategy.MIN_COPYSETS
    if name == "buddy":
        return PlacementStrategy.BUDDY
    return PlacementStrategy.BUDDY


def reconstruct_from_nodes(file_id: str, placement_info: dict, output_path: str):
    """
    Reconstruct the original file from fragments stored on the nodes' disks.

    We assume node_server.py stores fragments as:
      data/node_<node_id>/<file_id>_frag<frag_idx>_rep<replica_idx>.bin
    and we read replica 0 from the first node in the list for each fragment.
    """
    fragments_data: list[bytes] = []

    for frag_meta in placement_info["fragments"]:
        frag_idx = frag_meta["fragment"]
        node_ids = frag_meta["nodes"]
        if not node_ids:
            raise RuntimeError(f"No nodes recorded for fragment {frag_idx}")

        # first node got replica_idx = 0
        node_id = node_ids[0]

        node_dir = Path(DATA_BASE_DIR) / f"node_{node_id}"
        fragment_filename = f"{file_id}_frag{frag_idx}_rep0.bin"
        fragment_path = node_dir / fragment_filename

        if not fragment_path.exists():
            raise FileNotFoundError(f"Missing fragment: {fragment_path}")

        frag_bytes = fragment_path.read_bytes()
        fragments_data.append(frag_bytes)

    with open(output_path, "wb") as f:
        for chunk in fragments_data:
            f.write(chunk)


# --- STORE FILE (lead node API) ---
@app.route("/store", methods=["POST"])
def store():
    """
    Upload a file:
      - Save it temporarily under UPLOAD_DIR
      - LeadNodeSocket.store_file(...) distributes fragments to nodes via sockets
      - Return object_id and placement info
    """
    if "file" not in request.files:
        return jsonify({"error": "Use multipart-form with key 'file'"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    # Generate unique id for this object
    object_id = str(uuid.uuid4())

    # Let client optionally choose k and strategy
    k = int(request.form.get("k", "3"))
    strategy_name = request.form.get("strategy", "buddy")
    strategy = parse_strategy(strategy_name)

    # Save uploaded file temporarily
    save_path = os.path.join(UPLOAD_DIR, object_id)
    file.save(save_path)

    # Distribute file using the lead node (sockets -> nodes)
    placement_info = lead.store_file(
        file_id=object_id,
        file_path=save_path,
        replica_count=k,
        strategy=strategy,
    )

    # Remember placement for retrieval
    PLACEMENTS[object_id] = placement_info

    return jsonify({
        "object_id": object_id,
        "filename": file.filename,
        "strategy": strategy.value,
        "replicas_per_fragment": k,
        "placement": placement_info,
    }), 201


# --- RETRIEVE FILE (lead node API) ---
@app.route("/retrieve/<object_id>", methods=["GET"])
def retrieve(object_id):
    """
    Reconstruct the file from the nodes and send it back to the client.
    """
    placement_info = PLACEMENTS.get(object_id)
    if placement_info is None:
        return abort(404, description="Unknown object_id")

    reconstructed_path = os.path.join(UPLOAD_DIR, f"{object_id}_reconstructed")

    try:
        reconstruct_from_nodes(object_id, placement_info, reconstructed_path)
    except FileNotFoundError:
        return abort(500, description="Missing fragment on nodes")
    except Exception as e:
        return abort(500, description=str(e))

    return send_file(reconstructed_path, as_attachment=True, download_name=f"{object_id}")


# --- OPTIONAL: see where fragments were placed ---
@app.route("/placement/<object_id>", methods=["GET"])
def placement(object_id):
    info = PLACEMENTS.get(object_id)
    if info is None:
        return abort(404)
    return jsonify(info)


if __name__ == "__main__":
    # This process is your lead node providing the Web API
    app.run(host="0.0.0.0", port=5000, debug=True)

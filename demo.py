from flask import Flask, request, jsonify, send_file, abort
import os
import uuid

from dsm.lead import LeadNodeSocket
from dsm.config import PlacementStrategy, ERASURE_C, ERASURE_L

app = Flask(__name__)

# Where original uploads/reconstructed files live (lead node local disk)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Where node_server.py stores its fragments:
DATA_BASE_DIR = "data"

def build_node_addresses():
    # Defaults
    n = int(os.environ.get("DSM_NODES", "6"))
    host = os.environ.get("DSM_HOST", "127.0.0.1")
    base_port = int(os.environ.get("DSM_BASE_PORT", "6000"))

    return {i: (host, base_port + i) for i in range(n)}

NODE_ADDRESSES = build_node_addresses()
lead = LeadNodeSocket(node_addresses=NODE_ADDRESSES)

# In-memory placement info for replicated files (Task 1)
PLACEMENTS: dict[str, dict] = {}

# In-memory placement info for coded files (Task 2) - (lead also stores it internally in metadata)
CODED_PLACEMENTS: dict[str, dict] = {}


def parse_strategy(name: str) -> PlacementStrategy:
    n = name.lower()
    if n == "random":
        return PlacementStrategy.RANDOM
    if n in ("min", "copyset", "copysets", "min_copysets"):
        return PlacementStrategy.MIN_COPYSETS
    if n == "buddy":
        return PlacementStrategy.BUDDY
    return PlacementStrategy.BUDDY


# =========================================================
# Task 1: Replication API
# =========================================================

@app.post("/store")
def store():
    """
    Upload a file and store it using replication (Task 1).
    """
    if "file" not in request.files:
        return jsonify({"error": "Use multipart-form with key 'file'"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    object_id = str(uuid.uuid4())
    k = int(request.form.get("k", "3"))
    strategy = parse_strategy(request.form.get("strategy", "buddy"))

    # Save original file on lead node
    save_path = os.path.join(UPLOAD_DIR, object_id)
    file.save(save_path)

    placement_info = lead.store_file(
        file_id=object_id,
        file_path=save_path,
        replica_count=k,
        strategy=strategy,
    )

    PLACEMENTS[object_id] = placement_info

    return jsonify({
        "object_id": object_id,
        "filename": file.filename,
        "strategy": strategy.value,
        "replicas_per_fragment": k,
        "placement": placement_info,
    }), 201


@app.get("/retrieve/<object_id>")
def retrieve(object_id: str):
    """
    Reconstruct and download a replicated file (Task 1).
    """
    placement_info = PLACEMENTS.get(object_id)
    if placement_info is None:
        return abort(404, description="Unknown object_id")

    try:
        data = lead.reconstruct_file(
            file_id=object_id,
            placement_info=placement_info,
            data_dir_base=DATA_BASE_DIR,
        )
    except FileNotFoundError:
        return abort(500, description="Missing fragment on nodes")
    except Exception as e:
        return abort(500, description=str(e))

    out_path = os.path.join(UPLOAD_DIR, f"{object_id}_reconstructed")
    with open(out_path, "wb") as f:
        f.write(data)

    return send_file(out_path, as_attachment=True, download_name=object_id)


@app.get("/placement/<object_id>")
def placement(object_id: str):
    info = PLACEMENTS.get(object_id)
    if info is None:
        return abort(404)
    return jsonify(info)


# =========================================================
# Task 2: Erasure-coded API
# =========================================================

@app.post("/store_coded")
def store_coded():
    """
    Upload a file and store it using erasure coding (Task 2).
    """
    if "file" not in request.files:
        return jsonify({"error": "Use multipart-form with key 'file'"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    object_id = str(uuid.uuid4())
    c = int(request.form.get("c", str(ERASURE_C)))
    l = int(request.form.get("l", str(ERASURE_L)))
    strategy = parse_strategy(request.form.get("strategy", "buddy"))

    save_path = os.path.join(UPLOAD_DIR, object_id)
    file.save(save_path)

    placement_info = lead.store_coded_file(
        file_id=object_id,
        file_path=save_path,
        c=c,
        l=l,
        strategy=strategy,
    )

    CODED_PLACEMENTS[object_id] = placement_info

    return jsonify({
        "object_id": object_id,
        "filename": file.filename,
        "strategy": strategy.value,
        "c": c,
        "l": l,
        "placement": placement_info,
    }), 201


@app.get("/retrieve_coded/<object_id>")
def retrieve_coded(object_id: str):
    """
    Reconstruct and download an erasure-coded file (Task 2).
    """
    if object_id not in CODED_PLACEMENTS and object_id not in lead.coded_metadata:
        return abort(404, description="Unknown object_id")

    try:
        data = lead.reconstruct_coded_file(
            file_id=object_id,
            data_dir_base=DATA_BASE_DIR,
        )
    except Exception as e:
        return abort(500, description=str(e))

    out_path = os.path.join(UPLOAD_DIR, f"{object_id}_reconstructed_coded")
    with open(out_path, "wb") as f:
        f.write(data)

    return send_file(out_path, as_attachment=True, download_name=object_id)


@app.get("/placement_coded/<object_id>")
def placement_coded(object_id: str):
    info = CODED_PLACEMENTS.get(object_id)
    if info is None:
        return abort(404)
    return jsonify(info)


if __name__ == "__main__":
    # This process *is* the lead node + Web API
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

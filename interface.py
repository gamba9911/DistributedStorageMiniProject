#install flask first - pip install flask
from flask import Flask, request, jsonify, send_file, abort
import os
import uuid

app = Flask(__name__)

STORAGE_DIR = "storage"
os.makedirs(STORAGE_DIR, exist_ok=True)

# --- STORE FILE ---
@app.route("/store", methods=["POST"])
def store():
    if "file" not in request.files:
        return jsonify({"error": "Use multipart-form with key 'file'"}), 400
    
    file = request.files["file"]
    object_id = str(uuid.uuid4())
    save_path = os.path.join(STORAGE_DIR, object_id)

    file.save(save_path)
    return jsonify({"object_id": object_id, "filename": file.filename}), 201

# --- RETRIEVE FILE ---
@app.route("/retrieve/<object_id>", methods=["GET"])
def retrieve(object_id):
    path = os.path.join(STORAGE_DIR, object_id)
    if not os.path.exists(path):
        return abort(404)
    return send_file(path, as_attachment=True)

# --- RUN CODE ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


# HOW TO RUN THIS CODE:
# python3 interface.py 

# HOW TO TEST THIS CODE:
# create a file with this command: echo "hello world" > test.txt
# test the store function: curl -F "file=@test.txt" http://localhost:5000/store
# it will return a json with object_id
# use that object_id to test the retrieve function: curl -O http://localhost:5000/retrieve/<object_id>
# an example with object id of 4f4e52fe-42f7-4deb-b10e-972f5d898daa: curl -O http://localhost:5000/retrieve/4f4e52fe-42f7-4deb-b10e-972f5d898daa


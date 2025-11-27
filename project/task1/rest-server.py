"""
Aarhus University - Distributed Storage course - Lab 4

REST Server, starter template for Week 4
"""

from flask import Flask, make_response, g, request, send_file
import sqlite3
import zmq # For ZMQ
import time # For waiting a second for ZMQ connections
import math # For cutting the file in half
import random # For selecting a random half when requesting chunks
import messages_pb2 # Generated Protobuf messages
import io # For sending binary data in a HTTP response
import os
import csv
from config_selection import select_nodes

# ---------------- Configuration ----------------
K_REPLICAS = int(os.getenv("K_REPLICAS", "3"))  # k full replicas
PLACEMENT_MODE = os.getenv("PLACEMENT_MODE", "random")
MEAS_FILE = "measure.csv"
NODE_NAMES = os.getenv("NODE_NAMES", "node1,node2,node3,node4")
NODE_NAMES = [n.strip() for n in NODE_NAMES.split(",") if n.strip()]
NODES_STATE = [{"name": name, "copies": 0} for name in NODE_NAMES]

if K_REPLICAS > len(NODE_NAMES):
    raise RuntimeError(
        f"K_REPLICAS={K_REPLICAS} > number of nodes={len(NODE_NAMES)}. "
    )

"""
Utility Functions
"""

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            'files.db',
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def random_string(length=8):
    """
    Returns a random alphanumeric string of the given length. 
    Only lowercase ascii letters and numbers are used.

    :param length: Length of the requested random string 
    :return: The random generated string
    """
    import random, string
    return ''.join([random.SystemRandom().choice(string.ascii_letters + string.digits) for n in range(length)])

def write_file(data, filename=None):
    """
    Write the given data to a local file with the given filename

    :param data: A bytes object that stores the file contents
    :param filename: The file name. If not given, a random string is generated
    :return: The file name of the newly written file, or None if there was an error
    """
    if not filename:
        # Generate random filename
        filename = random_string(length=8)
        # Add '.bin' extension
        filename += ".bin"
    
    try:
        # Open filename for writing binary content ('wb')
        # note: when a file is opened using the 'with' statment, 
        # it is closed automatically when the scope ends
        with open('./'+filename, 'wb') as f:
            f.write(data)
    except EnvironmentError as e:
        print("Error writing file: {}".format(e))
        return None
    
    return filename

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

# def select_nodes(strategy, k, nodes):
#     """
#     nodes list format:
#     [
#       {"name":"node1","copies":10,"endpoint":"tcp://127.0.0.1:6001"},
#       {"name":"node2","copies":8,"endpoint":"tcp://127.0.0.1:6002"},
#       ...
#     ]
#     """
#     if strategy == "random":
#         return random.sample(nodes, k)

#     elif strategy == "mincopy":
#         sorted_nodes = sorted(
#             nodes,
#             key=lambda n: (n.get("copies", 0), random.random())
#         )
#         return sorted_nodes[:k]

#     elif strategy == "buddy":
#         pass

#

# Initiate ZMQ sockets
context = zmq.Context()

# Publisher socket for store requests
store_pub_socket = context.socket(zmq.PUB)
store_pub_socket.bind("tcp://*:5557")

# Socket to receive messages from Storage Nodes
response_socket = context.socket(zmq.PULL)
response_socket.bind("tcp://*:5558")

# Publisher socket for data request broadcasts
data_req_socket = context.socket(zmq.PUB)
data_req_socket.bind("tcp://*:5559")

# Wait for all workers to start and connect.
time.sleep(1)
print("Listening to ZMQ messages on tcp://*:5558")

"""
REST API
"""

# Instantiate the Flask app (must be before the endpoint functions)
app = Flask(__name__)
# Close the DB connection after serving the request
app.teardown_appcontext(close_db)

@app.route('/')
def hello():
    return make_response({'message': 'Hello World!'})

@app.route('/files',  methods=['GET'])
def list_files():
    db = get_db()
    cursor = db.execute("SELECT * FROM `file`")
    if not cursor: 
        return make_response({"message": "Error connecting to the database"}, 500)
    
    files = cursor.fetchall()
    # Convert files from sqlite3.Row object (which is not JSON-encodable) to 
    # a standard Python dictionary simply by casting
    files = [dict(file) for file in files]
    
    return make_response({"files": files})
#

@app.route('/files/<int:file_id>',  methods=['GET'])
def download_file(file_id):

    db = get_db()
    cursor = db.execute("SELECT * FROM `file` WHERE `id`=?", [file_id])
    if not cursor: 
        return make_response({"message": "Error connecting to the database"}, 500)
    
    
    f = cursor.fetchone()
    # Convert to a Python dictionary
    f = dict(f)

    print("File requested: {}".format(f))

    # lists for each fragment
    part_lists = [
        f['part1_filenames'].split(','),
        f['part2_filenames'].split(','),
        f.get('part3_filenames', '').split(','),
        f.get('part4_filenames', '').split(',')
    ]
      
    # prevent void name
    part_lists = [[name for name in lst if name] for lst in part_lists]

    # choose 1 replicas randomly for each fragment
    chosen_names = [
        names[random.randint(0, len(names) - 1)]
        for names in part_lists
    ]

    print(f"Chosen chunk names: {chosen_names}")

    # Request 4 chunks in parallel
    for chunk_name in chosen_names:
        task = messages_pb2.getdata_request()
        task.filename = chunk_name
        data_req_socket.send(task.SerializeToString())

    # Receive 4 chunks and insert them to
    file_data_parts = [None, None, None, None]
    needed = {name: idx for idx, name in enumerate(chosen_names)}
    remaining = 4
    while remaining > 0:
        result = response_socket.recv_multipart()

        if len(result) != 2:
            # ignore ack
            continue
        # First frame: file name (string)
        filename_received = result[0].decode('utf-8')
        # Second frame: data
        chunk_data = result[1]

        print(f"Received {filename_received}, {len(chunk_data)} bytes")

        if filename_received in needed:
            idx = needed[filename_received]
            if file_data_parts[idx] is None:
                file_data_parts[idx] = chunk_data
                remaining -= 1

    print("All fragments received successfully")

    # Combine the parts and serve the file
    file_data = b''.join(file_data_parts)

    return send_file(io.BytesIO(file_data), mimetype=f['content_type'])
#

# HTTP HEAD requests are served by the GET endpoint of the same URL,
# so we'll introduce a new endpoint URL for requesting file metadata.
@app.route('/files/<int:file_id>/info',  methods=['GET'])
def get_file_metadata(file_id):

    db = get_db()
    cursor = db.execute("SELECT * FROM `file` WHERE `id`=?", [file_id])
    if not cursor: 
        return make_response({"message": "Error connecting to the database"}, 500)
    
    f = cursor.fetchone()
    if not f:
        return make_response({"message": "File {} not found".format(file_id)}, 404)

    # Convert to a Python dictionary
    f = dict(f)
    print("File: %s" % f)

    return make_response(f)
#

@app.route('/files/<int:file_id>',  methods=['DELETE'])
def delete_file(file_id):

    db = get_db()
    cursor = db.execute("SELECT * FROM `file` WHERE `id`=?", [file_id])
    if not cursor: 
        return make_response({"message": "Error connecting to the database"}, 500)
    
    f = cursor.fetchone()
    if not f:
        return make_response({"message": "File {} not found".format(file_id)}, 404)

    # Convert to a Python dictionary
    f = dict(f)
    print("File to delete: %s" % f)

    # Delete the file contents with os.remove()
    from os import remove
    remove(f['blob_name'])

    # Delete the file record from the DB
    db.execute("DELETE FROM `file` WHERE `id`=?", [file_id])
    db.commit()

    # Return empty 200 Ok response
    return make_response('')
#



@app.route('/files', methods=['POST'])
def add_files():
    payload = request.files['file']
    filename = request.form.get("filename", payload.filename)
    content_type = request.form.get("content_type", payload.content_type)
    file_data = payload.read()
    size = len(file_data)

    # four equal-sized fragments
    t_repl_start = time.time()
    fragment_size = math.ceil(size / 4.0)
    fragments = []
    for i in range(4):
        start = int(i * fragment_size)
        end = int(min((i + 1) * fragment_size, size))
        fragments.append(file_data[start:end])

    # Generate k random chunk names for each fragment
    fragment_filename_lists = []  # [[f11,f12,...,f1k], ..., [f41,...,f4k]]

    for idx, frag in enumerate(fragments):
        names = [random_string(8) for _ in range(K_REPLICAS)]
        fragment_filename_lists.append(names)
        print(f"Filenames for part {idx+1}: {names}")

        # Select nodes for this fragment according to placement strategy
        selected_nodes = select_nodes(PLACEMENT_MODE, K_REPLICAS, NODES_STATE)

        # Send each replica to its selected node
        for name, node in zip(names, selected_nodes):
            node_name = node["name"]
            node["copies"] += 1  # update placement statistics

            task = messages_pb2.storedata_request()
            task.filename = name
            # topic = node_name (so only that node receives it)
            store_pub_socket.send_multipart([
                node_name.encode("utf-8"),
                task.SerializeToString(),
                frag
            ])
            print(f"Sent chunk {name} (part {idx + 1}) to node {node_name}")

    # Wait until we receive 4*k responses from the workers
    for task_nbr in range(4*K_REPLICAS):
        resp = response_socket.recv_string()
    print(f"Received: {resp}")
    # At this point all chunks are stored, insert the File record in the DB

    t_repl_end = time.time()
    replication_time = t_repl_end - t_repl_start

    # Insert the File record in the DB
    db = get_db()
    cursor = db.execute(
        "INSERT INTO `file`(`filename`, `size`, `content_type`, "
        "`part1_filenames`, `part2_filenames`, `part3_filenames`, `part4_filenames`) "
        "VALUES(?,?,?,?,?,?,?)",
        (
            filename, size, content_type,
            ','.join(fragment_filename_lists[0]),
            ','.join(fragment_filename_lists[1]),
            ','.join(fragment_filename_lists[2]),
            ','.join(fragment_filename_lists[3])
        )
    )
    db.commit()

    # Save measurement 
    log_measurement(MEAS_FILE,[time.time(), cursor.lastrowid, filename, size, "replication", replication_time])

    # Return the ID of the new file record with HTTP 201 (Created) status code
    return make_response({"id": cursor.lastrowid }, 201)
#



@app.errorhandler(500)
def server_error(e):
    from logging import exception
    exception("Internal error: %s", e)

    return make_response({"error": str(e)}, 500)


# Start the Flask app (must be after the endpoint functions) 
host_local_computer = "localhost" # Listen for connections on the local computer
host_local_network = "0.0.0.0" # Listen for connections on the local network
app.run(host=host_local_computer, port=9000)
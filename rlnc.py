import pyerasure
import pyerasure.finite_field
import pyerasure.generator
import math
import random
from utils import random_string
import messages_pb2
import json

STORAGE_NODES_NUM = 4

def store_file(file_data, max_erasures, subfragments_per_node,
               send_task_socket, response_socket, node_names):

    # Make sure we can realize max_erasures with N storage nodes
    assert 0 <= max_erasures < STORAGE_NODES_NUM

    # At least one subfragment per node
    assert subfragments_per_node > 0

    # How many coded subfragments (=symbols) will be required to reconstruct the encoded data.
    symbols = (STORAGE_NODES_NUM - max_erasures) * subfragments_per_node
    # The size of one coded subfragment (total size/number of symbols, rounded up)
    symbol_size = math.ceil(len(file_data) / symbols)
    # Pyerasure RLNC encoder using 2^8 finite field
    field = pyerasure.finite_field.Binary8()
    encoder = pyerasure.Encoder(
        field=field,
        symbols=symbols,
        symbol_bytes=symbol_size,
    )
    # Padding, to make sure to get the correct separation in symbols
    encoder.set_symbols(file_data.ljust(symbol_size * symbols, b"\0"))

    #  Random coefficient generator
    gen = pyerasure.generator.RandomUniform(field, encoder.symbols)

    # Store the generated fragment names
    coded_fragment_names = []

    # Generate several coded subfragments for each Storage Node
    for node_idx, node_name in enumerate(node_names):
         # Generate a random name for them and save
        frag_name = random_string(8)
        coded_fragment_names.append(frag_name)

         # First frame: a Protobuf STORE DATA message
        task = messages_pb2.storedata_request()
        task.filename = frag_name
        frames = [
            node_name.encode("utf-8"),         # topic
            task.SerializeToString()           # protobuf
        ]

        # Next every frame = coeffs + symbol_data
        for j in range(subfragments_per_node):
             # Generate a fresh set of coefficients
            coeffs = gen.generate()    # len = symbols
             # Generate a coded symbol with these coefficients
            sym = encoder.encode_symbol(coeffs)
             # Add to the message frames
            frames.append(coeffs + bytearray(sym))

        # Send all frames as a multipart message
        send_task_socket.send_multipart(frames)

    # Wait until we receive a response for every message
    for _ in range(STORAGE_NODES_NUM):
        _ = response_socket.recv_string()

    return coded_fragment_names


def get_file(coded_fragments, max_erasures, file_size,
             data_req_socket, response_socket):

    # We need fragments from 4-max_erasures nodes to reconstruct the file, select this many
    # by randomly removing 'max_erasures' elements from the given chunk names.
    fragnames = coded_fragments[:]
    for _ in range(max_erasures):
        if fragnames:
            fragnames.remove(random.choice(fragnames))

     # Request the coded fragments in parallel. Nodes return all their subfragments
    for name in fragnames:
        task = messages_pb2.getdata_request()
        task.filename = name
        data_req_socket.send(task.SerializeToString())

    # Receive all chunks and insert them into the symbols array
    symbols = []
    for _ in range(len(fragnames)):
        result = response_socket.recv_multipart()
        # result[0] = filename, result[1:] = subfragment
        for i in range(1, len(result)):
            symbols.append({"data": bytearray(result[i])})

    if not symbols:
        return None
    
    #Reconstruct the original file data
    file_data = _decode_file(symbols)
    return file_data[:file_size]


def _decode_file(symbols):

    # Reconstruct the original data with a decoder
    symbols_num = len(symbols)

    symbol_size = len(symbols[0]["data"]) - symbols_num   #subtract the coefficients' size

    decoder = pyerasure.Decoder(
        field=pyerasure.finite_field.Binary8(),
        symbols=symbols_num,
        symbol_bytes=symbol_size
    )

    for symbol in symbols:
        # Separate the coefficients from the symbol data
        # (we know they are in the front and there are 'symbols_num' of them)
        coeffs = symbol["data"][:symbols_num]
        sym_data = symbol["data"][symbols_num:]

        # Feed it to the decoder
        decoder.decode_symbol(sym_data, coeffs)

    # Check that the decoder successfully reconstructed the file
    if not decoder.is_complete():
        print(f"Decoding failed, rank={decoder.rank}")
        return None

    print("File decoded successfully")

    # In a real system we might add more complex error handling
    return bytearray(decoder.block_data())
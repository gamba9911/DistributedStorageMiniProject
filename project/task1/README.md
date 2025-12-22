# Distributed Storage Mini Project

## Task 1

### Running instructions
[storage-node.py](storage-node.py) it should be called 4 instances 
<br> and with different nodeNames as sysarg:
<br> "node1", "node2" , "node3" and "node4"

[rest-server.py](rest-server.py) define the default ENVIRONMENT VARIABLES 
used to configure the application. 
<br> You can change these values here if needed before running the system.

[measure_plot.py](measure_plot.py) contains the main function,
and it should be the last instance to run

[rest-client.py](rest-client.py) calls rest-server 
and create a spreadsheet with time run for DOWNLOAD

### Extra Notes
[files.db](files.db) is already filled with results for files until size 1MB

[messages.proto](messages.proto) was already compiled 
and resulted in [messages_pb2.py](messages_pb2.py)


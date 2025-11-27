import time
import requests
import csv
import os

FILE_ID = 2
URL = f"http://localhost:9000/files/{FILE_ID}"
MEAS_FILE = "download_client.csv"

t0 = time.time()               
r = requests.get(URL)
data = r.content                  
t1 = time.time()

download_time = t1 - t0


new_file = not os.path.exists(MEAS_FILE)
with open(MEAS_FILE, "a", newline="") as f:
    writer = csv.writer(f)
    if new_file:
        writer.writerow(
            ["timestamp", "file_id", "size_bytes", "metric", "value_sec"]
        )
    writer.writerow([time.time(), FILE_ID, len(data),
                     "download_client", download_time])

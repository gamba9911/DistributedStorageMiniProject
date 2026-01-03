import os
import sys
import subprocess
import random
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class NodeProc:
    node_id: int
    port: int
    popen: subprocess.Popen

class ClusterController:
    def __init__(self, python_bin: str = sys.executable, base_port: int = 6000):
        self.python_bin = python_bin
        self.base_port = base_port
        self.nodes: Dict[int, NodeProc] = {}
        self.lead: subprocess.Popen | None = None

    def start_nodes(self, n: int):
        for i in range(n):
            port = self.base_port + i
            p = subprocess.Popen([self.python_bin, "node_server.py", "--id", str(i), "--port", str(port)])
            self.nodes[i] = NodeProc(node_id=i, port=port, popen=p)

    def start_lead_api(self, n: int):
        env = os.environ.copy()
        env["DSM_NODES"] = str(n)
        env["DSM_BASE_PORT"] = str(self.base_port)
        self.lead = subprocess.Popen([self.python_bin, "demo.py"], env=env)

    def stop_random_nodes(self, s: int, seed: int | None = None) -> List[int]:
        ids = list(self.nodes.keys())
        if seed is not None:
            random.seed(seed)
        victims = random.sample(ids, min(s, len(ids)))

        for node_id in victims:
            proc = self.nodes[node_id].popen
            proc.terminate()
        return victims

    def stop_all(self):
        if self.lead is not None:
            self.lead.terminate()

        for np in self.nodes.values():
            np.popen.terminate()

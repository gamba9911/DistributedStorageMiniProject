import random

def select_nodes(strategy, k, nodes):

    k = min(k, len(nodes))

    if strategy == "random":
        return random.sample(nodes, k)


    elif strategy == "mincopy":

        sorted_nodes = sorted(
            nodes,
            key=lambda n: (n.get("copies", 0), random.random())
        )
        return sorted_nodes[:k]


    elif strategy == "buddy":

        buddy_map = {}
        for i, node in enumerate(nodes):
            if i % 2 == 0 and i + 1 < len(nodes):
                buddy_map[node["name"]] = nodes[i + 1]["name"]
                buddy_map[nodes[i + 1]["name"]] = node["name"]

        selected = []
        blocked_names = set()  
        available = nodes[:]  

        while available and len(selected) < k:
            cand = random.choice(available)
            available.remove(cand)

            if cand["name"] in blocked_names:
                continue

            selected.append(cand)
            buddy = buddy_map.get(cand["name"])
            if buddy:
                blocked_names.add(buddy)

        if len(selected) < k:
            remaining = [n for n in nodes if n not in selected]
            if remaining:
                extra = random.sample(
                    remaining,
                    min(k - len(selected), len(remaining))
                )
                selected.extend(extra)

        return selected

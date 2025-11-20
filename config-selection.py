import random

size_fragments = 4  # defined in mini project


# k=3 replicas (this is common in distributed systems like Hadoop).
# Number of Nodes (N):The project requires testing with different cluster sizes:N=6,12,24.It needs to be N≥k
def select_node_strategy(strategy="random" | "copysets" | "buddy", k=3, n=4):
    if (strategy == "random"):
        return strategy
    elif (strategy == "copysets"):
        return strategy
    elif (strategy == "buddy"):
        return strategy


def place_replicas(strategy, nodes, k, existing_copysets=None, buddy_map=None):
    if strategy == "random":
        return random_placement(nodes, k)
    elif strategy == "copysets":
        return min_copysets_placement(nodes, k, existing_copysets)
    elif strategy == "buddy":
        return buddy_placement(nodes, k, buddy_map)


def random_placement(nodes, k):
    return random.sample(nodes, k)


def min_copysets_placement(nodes, k, existing_copysets):
    best_choice = None
    min_overlap = float('inf')
    for _ in range(100):  # try random samples
        candidate = set(random.sample(nodes, k))
        overlap = sum(len(candidate & cs) for cs in existing_copysets)
        if overlap < min_overlap:
            min_overlap = overlap
            best_choice = candidate
    return best_choice


def buddy_placement(nodes, k, buddy_map):
    selected = []
    available = set(nodes)
    while len(selected) < k and available:
        node = random.choice(list(available))
        selected.append(node)
        # Remove buddy from available
        if node in buddy_map:
            available.discard(buddy_map[node])
        available.discard(node)
    return selected

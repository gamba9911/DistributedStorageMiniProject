import random
from itertools import combinations
from typing import List, Dict

from dsm.config import PlacementStrategy


class MinCopysetManager:
    """
    Maintains a reduced set of copysets (size-k combinations)
    used for MIN_COPYSETS placement.
    """

    def __init__(self, node_ids: List[int], replica_count: int, num_copysets: int | None = None):
        self.node_ids = list(node_ids)
        self.replica_count = replica_count

        all_combos = list(combinations(node_ids, replica_count))

        if num_copysets is None:
            num_copysets = min(len(all_combos), 2 * len(node_ids))

        self.copysets = random.sample(all_combos, num_copysets)

    def choose_copyset(self) -> List[int]:
        return list(random.choice(self.copysets))


def choose_random_nodes(replica_count: int, node_ids: List[int]) -> List[int]:
    """
    RANDOM placement: choose k distinct nodes uniformly at random.
    """
    return random.sample(node_ids, replica_count)


def choose_buddy_nodes(
    file_id: str,
    fragment_idx: int,
    replica_count: int,
    node_ids: List[int],
) -> List[int]:
    """
    BUDDY placement:
    - Arrange nodes in a ring.
    - Use a simple hash(file_id, fragment_idx) to pick a primary node.
    - Next replica_count-1 nodes in the ring are buddies.
    """
    N = len(node_ids)
    start_idx = (hash(file_id) + fragment_idx) % N
    return [node_ids[(start_idx + offset) % N] for offset in range(replica_count)]


class StrategySelector:
    """
    Single interface for choosing nodes according to a placement strategy.
    """

    def __init__(self, node_ids: List[int]):
        self.node_ids = node_ids
        self.copyset_managers: Dict[int, MinCopysetManager] = {}

    def select_nodes(
        self,
        file_id: str,
        fragment_idx: int,
        k: int,
        strategy: PlacementStrategy,
    ) -> List[int]:
        if strategy == PlacementStrategy.RANDOM:
            return choose_random_nodes(k, self.node_ids)

        if strategy == PlacementStrategy.MIN_COPYSETS:
            if k not in self.copyset_managers:
                self.copyset_managers[k] = MinCopysetManager(self.node_ids, k)
            return self.copyset_managers[k].choose_copyset()

        if strategy == PlacementStrategy.BUDDY:
            return choose_buddy_nodes(file_id, fragment_idx, k, self.node_ids)

        raise ValueError(f"Unknown placement strategy: {strategy}")

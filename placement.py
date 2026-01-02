import random
from itertools import combinations
from typing import List, Dict

from config import PlacementStrategy
from config import BUDDY_GROUP_SIZE
from typing import Optional

class MinCopysetManager:
    """
    Maintains a reduced set of copysets (size-k combinations)
    used for MIN_COPYSETS placement.
    """

    def __init__(self, node_ids: List[int], replica_count: int, num_copysets: Optional[int] = None):
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


def _partition_into_buddy_groups(node_ids: List[int], group_size: int) -> List[List[int]]:
    """
    Partition sorted node_ids into contiguous buddy groups.

    Example: node_ids = [0,1,2,3,4,5,6,7], group_size = 3
      -> [[0,1,2], [3,4,5], [6,7]]
    """
    sorted_ids = sorted(node_ids)
    return [
        sorted_ids[i:i + group_size]
        for i in range(0, len(sorted_ids), group_size)
    ]


def choose_buddy_nodes(
    file_id: str,
    fragment_idx: int,
    replica_count: int,
    node_ids: List[int],
    group_size: Optional[int] = None,
) -> List[int]:
    """
    Facebook-style Buddy Group placement:
      - Groups nodes in fixed-size groups
      - Select a random group
      - Replicas are placed inside that group

    group_size priority:
        1. Explicit argument (override)
        2. dsm.config.BUDDY_GROUP_SIZE setting
        3. Automatic based on replica_count and cluster size
    """
    all_nodes = sorted(node_ids)

    # ========== Select Group Size ==========
    if group_size is not None:
        final_group_size = group_size
    elif BUDDY_GROUP_SIZE is not None:
        final_group_size = BUDDY_GROUP_SIZE
    else:
        # Automatic fallback:
        # - at least k
        # - try to form ~3 or more groups if possible
        N = len(all_nodes)
        final_group_size = max(replica_count, max(3, N // 3))

    buddy_groups = _partition_into_buddy_groups(all_nodes, final_group_size)
    valid_groups = [g for g in buddy_groups if len(g) >= replica_count]

    if not valid_groups:
        # safety fallback → RANDOM
        return choose_random_nodes(replica_count, all_nodes)

    group = random.choice(valid_groups)
    return random.sample(group, replica_count)


class StrategySelector:
    """
    Central interface:
      - RANDOM placement
      - MIN_COPYSETS placement
      - BUDDY GROUP placement (Facebook-style buddy groups)
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
            # Buddy *group* placement: choose group, then nodes within that group.
            return choose_buddy_nodes(
                file_id=file_id,
                fragment_idx=fragment_idx,
                replica_count=k,
                node_ids=self.node_ids,
                group_size=None,  # or set a fixed group size here if you prefer
            )

        raise ValueError(f"Unknown placement strategy: {strategy}")

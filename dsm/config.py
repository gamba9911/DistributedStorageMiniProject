from enum import Enum

NUM_FRAGMENTS = 4  # Required: file split into 4 fragments


class PlacementStrategy(str, Enum):
    RANDOM = "random"
    MIN_COPYSETS = "min_copysets"
    BUDDY = "buddy"

BUDDY_GROUP_SIZE = None

ERASURE_C = 4   # number of source fragments (c)
ERASURE_L = 2   # tolerated losses (l)
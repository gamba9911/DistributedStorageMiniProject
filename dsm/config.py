from enum import Enum

NUM_FRAGMENTS = 4  # Required: file split into 4 fragments


class PlacementStrategy(str, Enum):
    RANDOM = "random"
    MIN_COPYSETS = "min_copysets"
    BUDDY = "buddy"

import math
from typing import List


def split_file_into_fragments(file_path: str, num_fragments: int = 4) -> List[bytes]:
    """
    Read file and split it into `num_fragments` equal-sized fragments.
    """
    with open(file_path, "rb") as f:
        data = f.read()

    total_size = len(data)
    frag_size = math.ceil(total_size / num_fragments)

    return [
        data[i * frag_size:(i + 1) * frag_size]
        for i in range(num_fragments)
    ]

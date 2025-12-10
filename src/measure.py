import numpy as np

from numpy.typing import NDArray
from typing import Tuple

def find_min_max(array: NDArray) -> Tuple[float, float]:
    return (array.min(), array.max())


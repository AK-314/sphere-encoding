"""Raw Hamming-distance primitives."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from sphere_encoding.encodings.validation import validate_binary_codes

Int64Array = npt.NDArray[np.int64]


def _validate_binary_vector(
    values: npt.ArrayLike,
    *,
    name: str,
) -> npt.NDArray[np.uint8]:
    array = np.asarray(values)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    return validate_binary_codes(
        array.reshape(1, -1),
        require_injective=False,
    )[0]


def raw_hamming_distance(
    left: npt.ArrayLike,
    right: npt.ArrayLike,
) -> int:
    """Return the raw Hamming distance between two bitstrings."""
    left_array = _validate_binary_vector(left, name="left")
    right_array = _validate_binary_vector(right, name="right")

    if left_array.shape != right_array.shape:
        raise ValueError("bitstrings must have the same length")

    return int(np.count_nonzero(left_array != right_array))


def hamming_distances_for_pairs(
    codes: npt.ArrayLike,
    pairs: npt.ArrayLike,
) -> Int64Array:
    """Return raw Hamming distances in the supplied pair-row order."""
    code_array = validate_binary_codes(
        codes,
        require_injective=False,
    )
    pair_array = np.asarray(pairs)

    if pair_array.ndim != 2 or pair_array.shape[1] != 2:
        raise ValueError("pairs must have shape (K, 2)")
    if not np.issubdtype(pair_array.dtype, np.integer):
        raise ValueError("pair indices must be integral")

    pair_array = np.asarray(pair_array, dtype=np.int64)

    if np.any(pair_array < 0) or np.any(pair_array >= len(code_array)):
        raise ValueError("pair index out of range")
    if np.any(pair_array[:, 0] == pair_array[:, 1]):
        raise ValueError("pair contains identical row indices")

    distances = np.count_nonzero(
        code_array[pair_array[:, 0]]
        != code_array[pair_array[:, 1]],
        axis=1,
    )
    return np.asarray(distances, dtype=np.int64)

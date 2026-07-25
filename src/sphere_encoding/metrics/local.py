"""Local edge-Hamming metrics."""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from sphere_encoding.metrics.hamming import hamming_distances_for_pairs

Int64Array = npt.NDArray[np.int64]


def edge_hamming_distances(
    codes: npt.ArrayLike,
    edges: npt.ArrayLike,
) -> Int64Array:
    """Return edge Hamming distances while preserving edge-row order."""
    edge_array = np.asarray(edges)

    if edge_array.ndim != 2 or edge_array.shape[1] != 2:
        raise ValueError("edges must have shape (E, 2)")
    if len(edge_array) == 0:
        raise ValueError("edge array must not be empty")

    return hamming_distances_for_pairs(codes, edge_array)


def local_hamming_metrics(
    distances: npt.ArrayLike,
    *,
    code_length: int,
) -> dict[str, Any]:
    """Summarise a complete nonempty local Hamming-distance array."""
    array = np.asarray(distances)

    if code_length <= 0:
        raise ValueError("code_length must be positive")
    if array.ndim != 1:
        raise ValueError("distances must be one-dimensional")
    if len(array) == 0:
        raise ValueError("distances must not be empty")
    if not np.issubdtype(array.dtype, np.integer):
        raise ValueError("local Hamming distances must be integral")

    array = np.asarray(array, dtype=np.int64)

    if np.any(array < 0) or np.any(array > code_length):
        raise ValueError("local Hamming distance outside [0, m]")

    maximum = int(np.max(array))
    histogram = np.bincount(
        array,
        minlength=code_length + 1,
    )[: code_length + 1]

    return {
        "L_95": int(np.quantile(array, 0.95, method="higher")),
        "L_99": int(np.quantile(array, 0.99, method="higher")),
        "L_max": maximum,
        "L_max_edge_count": int(np.count_nonzero(array == maximum)),
        "L_mean": float(np.mean(array)),
        "L_minimum": int(np.min(array)),
        "L_standard_deviation": float(np.std(array, ddof=0)),
        "edge_count": len(array),
        "histogram": [int(value) for value in histogram],
    }

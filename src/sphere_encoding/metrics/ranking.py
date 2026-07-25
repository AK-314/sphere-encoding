"""Deterministic ranks and correlation statistics."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

Float64Array = npt.NDArray[np.float64]


def _validated_numeric_vector(
    values: npt.ArrayLike,
    *,
    name: str,
    minimum_length: int,
) -> Float64Array:
    array = np.asarray(values, dtype=np.float64)

    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if len(array) < minimum_length:
        raise ValueError(
            f"{name} must contain at least {minimum_length} values"
        )
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains non-finite values")

    return array


def average_ranks(
    values: npt.ArrayLike,
) -> Float64Array:
    """Assign one-based average ranks to exact ties."""
    array = _validated_numeric_vector(
        values,
        name="values",
        minimum_length=1,
    )
    order = np.argsort(array, kind="mergesort")
    sorted_values = array[order]
    sorted_ranks = np.empty(len(array), dtype=np.float64)

    start = 0
    while start < len(array):
        stop = start + 1
        while (
            stop < len(array)
            and sorted_values[stop] == sorted_values[start]
        ):
            stop += 1

        average_rank = ((start + 1) + stop) / 2.0
        sorted_ranks[start:stop] = average_rank
        start = stop

    ranks = np.empty(len(array), dtype=np.float64)
    ranks[order] = sorted_ranks
    return ranks


def pearson_correlation(
    left: npt.ArrayLike,
    right: npt.ArrayLike,
) -> float | None:
    """Return Pearson correlation, or None for a constant variable."""
    left_array = _validated_numeric_vector(
        left,
        name="left",
        minimum_length=2,
    )
    right_array = _validated_numeric_vector(
        right,
        name="right",
        minimum_length=2,
    )

    if left_array.shape != right_array.shape:
        raise ValueError("correlation inputs must have the same shape")

    left_centred = left_array - np.mean(left_array)
    right_centred = right_array - np.mean(right_array)

    denominator = float(
        np.linalg.norm(left_centred)
        * np.linalg.norm(right_centred)
    )
    if denominator == 0.0:
        return None

    return float(np.dot(left_centred, right_centred) / denominator)


def spearman_correlation(
    left: npt.ArrayLike,
    right: npt.ArrayLike,
) -> float | None:
    """Return Pearson correlation of deterministic average ranks."""
    left_ranks = average_ranks(left)
    right_ranks = average_ranks(right)

    if left_ranks.shape != right_ranks.shape:
        raise ValueError("correlation inputs must have the same shape")

    return pearson_correlation(left_ranks, right_ranks)

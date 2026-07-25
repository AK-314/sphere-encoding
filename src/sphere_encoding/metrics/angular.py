"""Normalised angular-distance and pair-enumeration primitives."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

Float64Array = npt.NDArray[np.float64]
Int64Array = npt.NDArray[np.int64]


def _validated_vertices(
    vertices: npt.ArrayLike,
    *,
    unit_atol: float = 1e-12,
) -> Float64Array:
    array = np.asarray(vertices, dtype=np.float64)

    if array.ndim != 2 or array.shape[1] < 1:
        raise ValueError("vertices must have shape (N, d)")
    if len(array) == 0:
        raise ValueError("vertices must not be empty")
    if not np.all(np.isfinite(array)):
        raise ValueError("vertices contain non-finite values")
    if unit_atol < 0.0:
        raise ValueError("unit_atol must be non-negative")
    if not np.allclose(
        np.linalg.norm(array, axis=1),
        1.0,
        atol=unit_atol,
        rtol=0.0,
    ):
        raise ValueError("vertices must be unit vectors")

    return array


def exhaustive_unordered_pairs(vertex_count: int) -> Int64Array:
    """Enumerate all unordered pairs in lexicographic i-then-j order."""
    if vertex_count < 2:
        raise ValueError("at least two vertices are required")

    left, right = np.triu_indices(vertex_count, k=1)
    return np.column_stack((left, right)).astype(np.int64, copy=False)


def normalised_angular_from_dot_products(
    dot_products: npt.ArrayLike,
) -> Float64Array:
    """Convert dot products to clipped angular distances divided by pi."""
    dots = np.asarray(dot_products, dtype=np.float64)
    if not np.all(np.isfinite(dots)):
        raise ValueError("dot products contain non-finite values")

    clipped = np.clip(dots, -1.0, 1.0)
    return np.asarray(np.arccos(clipped) / np.pi, dtype=np.float64)


def normalised_angular_distances(
    vertices: npt.ArrayLike,
    pairs: npt.ArrayLike,
) -> Float64Array:
    """Return normalised angular distances in supplied pair-row order."""
    vertex_array = _validated_vertices(vertices)
    pair_array = np.asarray(pairs)

    if pair_array.ndim != 2 or pair_array.shape[1] != 2:
        raise ValueError("pairs must have shape (K, 2)")
    if not np.issubdtype(pair_array.dtype, np.integer):
        raise ValueError("pair indices must be integral")

    pair_array = np.asarray(pair_array, dtype=np.int64)

    if np.any(pair_array < 0) or np.any(pair_array >= len(vertex_array)):
        raise ValueError("pair index out of range")
    if np.any(pair_array[:, 0] == pair_array[:, 1]):
        raise ValueError("pair contains identical vertex indices")

    dots = np.sum(
        vertex_array[pair_array[:, 0]]
        * vertex_array[pair_array[:, 1]],
        axis=1,
    )
    return normalised_angular_from_dot_products(dots)


def antipodal_pair_indices(
    vertices: npt.ArrayLike,
    *,
    atol: float,
    expected_count: int | None = None,
    require_complete_pairing: bool = False,
) -> Int64Array:
    """Enumerate antipodal pairs using the accepted Stage 2 tolerance."""
    if atol < 0.0:
        raise ValueError("atol must be non-negative")

    vertex_array = _validated_vertices(vertices)
    pairs = exhaustive_unordered_pairs(len(vertex_array))
    sums = (
        vertex_array[pairs[:, 0]]
        + vertex_array[pairs[:, 1]]
    )
    selected = pairs[np.linalg.norm(sums, axis=1) <= atol]

    if expected_count is not None:
        if expected_count < 0:
            raise ValueError("expected_count must be non-negative")
        if len(selected) != expected_count:
            raise ValueError("antipodal-pair count differs from expectation")

    if require_complete_pairing:
        if len(vertex_array) % 2 != 0:
            raise ValueError("complete antipodal pairing requires even N")
        if len(selected) != len(vertex_array) // 2:
            raise ValueError("antipodal pairing is incomplete or ambiguous")

        occurrences = np.bincount(
            selected.reshape(-1),
            minlength=len(vertex_array),
        )
        if not np.all(occurrences == 1):
            raise ValueError(
                "every vertex must occur in exactly one antipodal pair"
            )

    return np.asarray(selected, dtype=np.int64)

"""Common deterministic graph and sphere-geometry utilities."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from itertools import pairwise

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


def normalise_rows(values: npt.ArrayLike) -> FloatArray:
    """Return float64 rows normalised to unit Euclidean norm."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError("values must be a two-dimensional array")

    norms = np.linalg.norm(array, axis=1)
    if np.any(~np.isfinite(norms)) or np.any(norms <= 0.0):
        raise ValueError("all rows must have finite positive norm")

    return np.asarray(array / norms[:, None], dtype=np.float64)


def canonical_edges_from_faces(faces: npt.ArrayLike) -> IntArray:
    """Return unique, lexicographically sorted undirected face edges."""
    face_array = np.asarray(faces, dtype=np.int64)
    if face_array.ndim != 2 or face_array.shape[1] != 3:
        raise ValueError("faces must have shape (F, 3)")

    edge_set: set[tuple[int, int]] = set()
    for a, b, c in face_array:
        for left, right in ((a, b), (b, c), (c, a)):
            first, second = sorted((int(left), int(right)))
            edge_set.add((first, second))

    return np.asarray(sorted(edge_set), dtype=np.int64).reshape(-1, 2)


def canonical_edges_from_neighbours(
    neighbours: Sequence[Sequence[int]],
) -> IntArray:
    """Return the undirected union of directed neighbour selections."""
    edge_set: set[tuple[int, int]] = set()

    for source, selected in enumerate(neighbours):
        for target in selected:
            if source == target:
                raise ValueError("self-neighbours are forbidden")
            edge_set.add(tuple(sorted((source, int(target)))))

    return np.asarray(sorted(edge_set), dtype=np.int64).reshape(-1, 2)


def lexicographically_sorted_rows(values: npt.ArrayLike) -> bool:
    """Return whether rows are strictly lexicographically increasing."""
    array = np.asarray(values)
    if array.ndim != 2:
        raise ValueError("values must be two-dimensional")

    rows = [tuple(row.tolist()) for row in array]
    return all(left < right for left, right in pairwise(rows))


def has_near_duplicate_rows(
    values: npt.ArrayLike,
    *,
    atol: float,
) -> bool:
    """Return whether two distinct rows are within Euclidean tolerance."""
    if atol < 0.0:
        raise ValueError("atol must be non-negative")

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError("values must be two-dimensional")

    for index in range(len(array) - 1):
        distances = np.linalg.norm(
            array[index + 1 :] - array[index],
            axis=1,
        )
        if np.any(distances <= atol):
            return True

    return False


def degrees(vertex_count: int, edges: npt.ArrayLike) -> IntArray:
    """Return the degree of every vertex."""
    if vertex_count < 0:
        raise ValueError("vertex_count must be non-negative")

    edge_array = np.asarray(edges, dtype=np.int64)
    if edge_array.ndim != 2 or edge_array.shape[1] != 2:
        raise ValueError("edges must have shape (E, 2)")

    result = np.zeros(vertex_count, dtype=np.int64)
    for left, right in edge_array:
        result[int(left)] += 1
        result[int(right)] += 1
    return result


def degree_histogram(vertex_count: int, edges: npt.ArrayLike) -> dict[str, int]:
    """Return a JSON-compatible degree histogram."""
    counts = Counter(int(value) for value in degrees(vertex_count, edges))
    return {str(key): counts[key] for key in sorted(counts)}


def connected(vertex_count: int, edges: npt.ArrayLike) -> bool:
    """Return whether an undirected graph is connected."""
    if vertex_count <= 0:
        return False

    adjacency: list[list[int]] = [[] for _ in range(vertex_count)]
    for left, right in np.asarray(edges, dtype=np.int64):
        a = int(left)
        b = int(right)
        adjacency[a].append(b)
        adjacency[b].append(a)

    seen = {0}
    stack = [0]
    while stack:
        current = stack.pop()
        for neighbour in adjacency[current]:
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)

    return len(seen) == vertex_count


def angular_edge_lengths(
    vertices: npt.ArrayLike,
    edges: npt.ArrayLike,
) -> FloatArray:
    """Return edge angles in radians."""
    vertex_array = np.asarray(vertices, dtype=np.float64)
    edge_array = np.asarray(edges, dtype=np.int64)

    dots = np.sum(
        vertex_array[edge_array[:, 0]] * vertex_array[edge_array[:, 1]],
        axis=1,
    )
    return np.asarray(
        np.arccos(np.clip(dots, -1.0, 1.0)),
        dtype=np.float64,
    )


def distinct_tolerance_classes(
    values: npt.ArrayLike,
    *,
    atol: float,
) -> int:
    """Count sorted scalar classes separated by more than atol."""
    if atol < 0.0:
        raise ValueError("atol must be non-negative")

    array = np.sort(np.asarray(values, dtype=np.float64).reshape(-1))
    if len(array) == 0:
        return 0

    classes = 1
    representative = float(array[0])
    for value in array[1:]:
        scalar = float(value)
        if abs(scalar - representative) > atol:
            classes += 1
            representative = scalar
    return classes


def face_orientation_values(
    vertices: npt.ArrayLike,
    faces: npt.ArrayLike,
) -> FloatArray:
    """Return outward-orientation triple products for triangular faces."""
    vertex_array = np.asarray(vertices, dtype=np.float64)
    face_array = np.asarray(faces, dtype=np.int64)

    first = vertex_array[face_array[:, 0]]
    second = vertex_array[face_array[:, 1]]
    third = vertex_array[face_array[:, 2]]
    normals = np.cross(second - first, third - first)
    centroids = (first + second + third) / 3.0
    return np.asarray(np.sum(normals * centroids, axis=1), dtype=np.float64)


def antipodal_pair_count(
    vertices: npt.ArrayLike,
    *,
    atol: float,
) -> int:
    """Count unordered antipodal vertex pairs."""
    if atol < 0.0:
        raise ValueError("atol must be non-negative")

    array = np.asarray(vertices, dtype=np.float64)
    count = 0
    for left in range(len(array) - 1):
        sums = np.linalg.norm(array[left + 1 :] + array[left], axis=1)
        count += int(np.count_nonzero(sums <= atol))
    return count


def minimum_bits(vertex_count: int) -> int:
    """Return ceil(log2(vertex_count)) using exact integer arithmetic."""
    if vertex_count <= 0:
        raise ValueError("vertex_count must be positive")
    return (vertex_count - 1).bit_length()

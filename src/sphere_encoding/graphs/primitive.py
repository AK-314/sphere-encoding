"""Primitive integer-direction point sets and neighbourhood graphs."""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from typing import TypeAlias

import numpy as np
import numpy.typing as npt

from sphere_encoding.graphs.common import (
    FloatArray,
    IntArray,
    canonical_edges_from_neighbours,
    normalise_rows,
)

NeighbourRows: TypeAlias = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class PrimitiveDirectionGraph:
    """A tie-complete symmetric primitive-direction graph."""

    q: int
    nominal_k: int
    integer_vectors: IntArray
    vertices: FloatArray
    edges: IntArray
    directed_neighbours: NeighbourRows
    threshold_angles: FloatArray

    @property
    def graph_id(self) -> str:
        return f"primitive_q{self.q}_knn{self.nominal_k}"


def generate_primitive_integer_vectors(q: int) -> IntArray:
    """Generate oriented primitive integer vectors in lexicographic order."""
    if isinstance(q, bool) or q < 1:
        raise ValueError("q must be a positive integer")

    vectors: list[tuple[int, int, int]] = []
    for x in range(-q, q + 1):
        for y in range(-q, q + 1):
            for z in range(-q, q + 1):
                if x == 0 and y == 0 and z == 0:
                    continue
                if gcd(gcd(abs(x), abs(y)), abs(z)) == 1:
                    vectors.append((x, y, z))

    return np.asarray(vectors, dtype=np.int64)


def tie_complete_directed_neighbours(
    vertices: npt.ArrayLike,
    *,
    nominal_k: int,
    angular_tie_atol_radians: float,
) -> tuple[NeighbourRows, FloatArray]:
    """Select every point tied with the nominal k-th angular neighbour."""
    vertex_array = np.asarray(vertices, dtype=np.float64)
    vertex_count = len(vertex_array)

    if vertex_array.ndim != 2 or vertex_array.shape[1] != 3:
        raise ValueError("vertices must have shape (N, 3)")
    if isinstance(nominal_k, bool) or not 1 <= nominal_k < vertex_count:
        raise ValueError("nominal_k must satisfy 1 <= k < N")
    if angular_tie_atol_radians < 0.0:
        raise ValueError("angular tie tolerance must be non-negative")

    all_indices = np.arange(vertex_count, dtype=np.int64)
    neighbour_rows: list[tuple[int, ...]] = []
    thresholds = np.empty(vertex_count, dtype=np.float64)

    for source in range(vertex_count):
        mask = all_indices != source
        candidates = all_indices[mask]
        dots = vertex_array[candidates] @ vertex_array[source]
        angles = np.arccos(np.clip(dots, -1.0, 1.0))

        ordering = np.lexsort((candidates, angles))
        ordered_candidates = candidates[ordering]
        ordered_angles = angles[ordering]
        threshold = float(ordered_angles[nominal_k - 1])
        thresholds[source] = threshold

        selected = ordered_candidates[
            ordered_angles <= threshold + angular_tie_atol_radians
        ]
        neighbour_rows.append(tuple(sorted(int(value) for value in selected)))

    return tuple(neighbour_rows), thresholds


def build_primitive_direction_graph(
    q: int,
    nominal_k: int,
    *,
    angular_tie_atol_radians: float,
) -> PrimitiveDirectionGraph:
    """Build a canonical tie-complete symmetric primitive-direction graph."""
    integer_vectors = generate_primitive_integer_vectors(q)
    vertices = normalise_rows(integer_vectors)
    directed_neighbours, thresholds = tie_complete_directed_neighbours(
        vertices,
        nominal_k=nominal_k,
        angular_tie_atol_radians=angular_tie_atol_radians,
    )
    edges = canonical_edges_from_neighbours(directed_neighbours)

    return PrimitiveDirectionGraph(
        q=q,
        nominal_k=nominal_k,
        integer_vectors=integer_vectors,
        vertices=vertices,
        edges=edges,
        directed_neighbours=directed_neighbours,
        threshold_angles=thresholds,
    )

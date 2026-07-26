"""Exact threshold-oriented scoring with deterministic incremental updates."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from sphere_encoding.heuristic.state import SearchState
from sphere_encoding.metrics.local import edge_hamming_distances


class ScoringError(ValueError):
    """Raised when threshold-scoring inputs are malformed."""


@dataclass(frozen=True, order=True, slots=True)
class ThresholdScore:
    """Exact lexicographic threshold-feasibility objective.

    The final component stores total local Hamming distance rather than its
    mean. The edge count is fixed within an instance, so this preserves the
    declared mean-distance ordering without floating-point arithmetic.
    """

    violation_count: int
    total_excess: int
    maximum_excess: int
    maximum_distance_edge_count: int
    total_local_hamming: int

    def __post_init__(self) -> None:
        values = (
            self.violation_count,
            self.total_excess,
            self.maximum_excess,
            self.maximum_distance_edge_count,
            self.total_local_hamming,
        )
        if any(not isinstance(value, int) for value in values):
            raise ScoringError("objective components must be integers")
        if any(value < 0 for value in values):
            raise ScoringError("objective components must be non-negative")
        if self.maximum_distance_edge_count <= 0:
            raise ScoringError("maximum-distance edge count must be positive")

    @property
    def is_feasible(self) -> bool:
        """Return whether the target threshold has no violating edge."""
        return self.violation_count == 0

    def as_tuple(self) -> tuple[int, int, int, int, int]:
        """Return the frozen lexicographic comparison key."""
        return (
            self.violation_count,
            self.total_excess,
            self.maximum_excess,
            self.maximum_distance_edge_count,
            self.total_local_hamming,
        )

    def mean_local_hamming(self, edge_count: int) -> float:
        """Return the exact objective's final component as a mean."""
        if edge_count <= 0:
            raise ScoringError("edge count must be positive")
        return self.total_local_hamming / edge_count


def canonical_edges_array(
    edges: npt.ArrayLike,
    *,
    vertex_count: int,
) -> np.ndarray:
    """Validate and copy a canonical undirected edge array."""
    if vertex_count <= 0:
        raise ScoringError("vertex count must be positive")

    array = np.asarray(edges)
    if array.ndim != 2 or array.shape[1:] != (2,):
        raise ScoringError("edges must have shape (edge_count, 2)")
    if array.shape[0] <= 0:
        raise ScoringError("at least one edge is required")
    if not np.issubdtype(array.dtype, np.integer):
        raise ScoringError("edge endpoints must be integers")

    normalised = np.array(array, dtype=np.int64, order="C", copy=True)
    if np.any(normalised < 0) or np.any(normalised >= vertex_count):
        raise ScoringError("edge endpoint is outside the vertex range")
    if np.any(normalised[:, 0] >= normalised[:, 1]):
        raise ScoringError(
            "canonical undirected edges must satisfy first endpoint < second endpoint"
        )

    previous = normalised[:-1]
    following = normalised[1:]
    if len(previous) and np.any(
        (following[:, 0] < previous[:, 0])
        | ((following[:, 0] == previous[:, 0]) & (following[:, 1] <= previous[:, 1]))
    ):
        raise ScoringError("edges must be strictly lexicographically sorted")

    normalised.setflags(write=False)
    return normalised


def _normalise_edge_distances(edge_distances: npt.ArrayLike) -> np.ndarray:
    array = np.asarray(edge_distances)
    if array.ndim != 1 or array.size <= 0:
        raise ScoringError("edge distances must be a non-empty one-dimensional array")
    if not np.issubdtype(array.dtype, np.integer):
        raise ScoringError("edge distances must be integers")

    normalised = np.array(array, dtype=np.int64, order="C", copy=True)
    if np.any(normalised < 0):
        raise ScoringError("edge distances must be non-negative")
    normalised.setflags(write=False)
    return normalised


def score_edge_distances(
    edge_distances: npt.ArrayLike,
    target_r: int,
) -> ThresholdScore:
    """Compute the exact frozen lexicographic threshold objective."""
    if not isinstance(target_r, int) or target_r < 0:
        raise ScoringError("target threshold must be a non-negative integer")

    distances = _normalise_edge_distances(edge_distances)
    excess = np.maximum(distances - target_r, 0)
    maximum_distance = int(np.max(distances))

    return ThresholdScore(
        violation_count=int(np.count_nonzero(excess)),
        total_excess=int(np.sum(excess, dtype=np.int64)),
        maximum_excess=int(np.max(excess)),
        maximum_distance_edge_count=int(
            np.count_nonzero(distances == maximum_distance)
        ),
        total_local_hamming=int(np.sum(distances, dtype=np.int64)),
    )


def edge_distances_for_state(
    state: SearchState,
    edges: npt.ArrayLike,
) -> np.ndarray:
    """Recompute all local edge Hamming distances through the Stage 3 metric."""
    canonical_edges = canonical_edges_array(
        edges,
        vertex_count=state.vertex_count,
    )
    distances = np.asarray(
        edge_hamming_distances(state.codebook, canonical_edges),
        dtype=np.int64,
    )
    if distances.shape != (canonical_edges.shape[0],):
        raise ScoringError("Stage 3 metric returned an unexpected distance shape")

    distances = np.array(distances, dtype=np.int64, order="C", copy=True)
    distances.setflags(write=False)
    return distances


def score_codebook(
    state: SearchState,
    edges: npt.ArrayLike,
    target_r: int,
) -> ThresholdScore:
    """Fully recompute the threshold objective for a validated state."""
    return score_edge_distances(
        edge_distances_for_state(state, edges),
        target_r,
    )


@dataclass(frozen=True, slots=True)
class IncrementalScoringState:
    """Immutable edge-distance cache with exact lexicographic score."""

    target_r: int
    edge_distances: np.ndarray
    score: ThresholdScore

    @classmethod
    def from_search_state(
        cls,
        state: SearchState,
        edges: npt.ArrayLike,
        target_r: int,
    ) -> IncrementalScoringState:
        """Construct an exact cache from a validated codebook."""
        distances = edge_distances_for_state(state, edges)
        return cls(
            target_r=target_r,
            edge_distances=distances,
            score=score_edge_distances(distances, target_r),
        )

    def __post_init__(self) -> None:
        if not isinstance(self.target_r, int) or self.target_r < 0:
            raise ScoringError("target threshold must be a non-negative integer")
        distances = _normalise_edge_distances(self.edge_distances)
        expected_score = score_edge_distances(distances, self.target_r)
        if expected_score != self.score:
            raise ScoringError("cached score does not match cached edge distances")
        object.__setattr__(self, "edge_distances", distances)

    @property
    def edge_count(self) -> int:
        return int(self.edge_distances.size)

    def with_updates(
        self,
        edge_indices: tuple[int, ...],
        new_distances: tuple[int, ...],
    ) -> IncrementalScoringState:
        """Return a cache with a deterministic set of edge updates applied."""
        if len(edge_indices) != len(new_distances):
            raise ScoringError(
                "edge indices and replacement distances differ in length"
            )
        if not edge_indices:
            raise ScoringError("at least one edge update is required")
        if tuple(sorted(edge_indices)) != edge_indices:
            raise ScoringError("edge indices must be strictly ascending")
        if len(set(edge_indices)) != len(edge_indices):
            raise ScoringError("edge indices must be unique")
        if any(
            not isinstance(index, int) or index < 0 or index >= self.edge_count
            for index in edge_indices
        ):
            raise ScoringError("edge update index is outside the cache")
        if any(
            not isinstance(distance, int) or distance < 0 for distance in new_distances
        ):
            raise ScoringError(
                "replacement edge distances must be non-negative integers"
            )

        updated = np.array(
            self.edge_distances,
            dtype=np.int64,
            order="C",
            copy=True,
        )
        updated[np.asarray(edge_indices, dtype=np.int64)] = np.asarray(
            new_distances,
            dtype=np.int64,
        )
        updated.setflags(write=False)

        return IncrementalScoringState(
            target_r=self.target_r,
            edge_distances=updated,
            score=score_edge_distances(updated, self.target_r),
        )

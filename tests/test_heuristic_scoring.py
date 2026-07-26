from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.heuristic.scoring import (
    IncrementalScoringState,
    ScoringError,
    ThresholdScore,
    canonical_edges_array,
    edge_distances_for_state,
    score_codebook,
    score_edge_distances,
)
from sphere_encoding.heuristic.state import SearchState


def _triangle_state() -> SearchState:
    return SearchState.from_codebook(
        np.array(
            [
                [0, 0, 0],
                [0, 1, 1],
                [1, 0, 1],
            ],
            dtype=np.uint8,
        )
    )


def _triangle_edges() -> np.ndarray:
    return np.array(
        [
            [0, 1],
            [0, 2],
            [1, 2],
        ],
        dtype=np.int64,
    )


def test_hand_calculated_threshold_objective() -> None:
    score = score_edge_distances(
        np.array([2, 4, 1, 4], dtype=np.int64),
        target_r=2,
    )

    assert score == ThresholdScore(
        violation_count=2,
        total_excess=4,
        maximum_excess=2,
        maximum_distance_edge_count=2,
        total_local_hamming=11,
    )
    assert not score.is_feasible
    assert score.mean_local_hamming(4) == 2.75


def test_exact_feasibility_detection() -> None:
    score = score_edge_distances(
        np.array([0, 1, 2, 2], dtype=np.int64),
        target_r=2,
    )

    assert score.is_feasible
    assert score.violation_count == 0
    assert score.total_excess == 0
    assert score.maximum_excess == 0


def test_objective_priority_is_lexicographic_without_weighting() -> None:
    fewer_violations = ThresholdScore(1, 1000, 1000, 1000, 1000)
    more_violations = ThresholdScore(2, 2, 1, 1, 2)
    assert fewer_violations < more_violations

    less_total_excess = ThresholdScore(2, 3, 3, 1000, 1000)
    more_total_excess = ThresholdScore(2, 4, 1, 1, 2)
    assert less_total_excess < more_total_excess

    less_maximum_excess = ThresholdScore(2, 4, 2, 1000, 1000)
    more_maximum_excess = ThresholdScore(2, 4, 3, 1, 2)
    assert less_maximum_excess < more_maximum_excess

    fewer_maximum_edges = ThresholdScore(2, 4, 3, 1, 1000)
    more_maximum_edges = ThresholdScore(2, 4, 3, 2, 2)
    assert fewer_maximum_edges < more_maximum_edges

    smaller_local_total = ThresholdScore(2, 4, 3, 2, 10)
    larger_local_total = ThresholdScore(2, 4, 3, 2, 11)
    assert smaller_local_total < larger_local_total


def test_full_score_reuses_stage3_local_metric() -> None:
    state = _triangle_state()
    edges = _triangle_edges()

    np.testing.assert_array_equal(
        edge_distances_for_state(state, edges),
        np.array([2, 2, 2], dtype=np.int64),
    )
    assert score_codebook(state, edges, target_r=1) == ThresholdScore(
        violation_count=3,
        total_excess=3,
        maximum_excess=1,
        maximum_distance_edge_count=3,
        total_local_hamming=6,
    )


def test_incremental_cache_update_matches_direct_scoring() -> None:
    state = _triangle_state()
    cache = IncrementalScoringState.from_search_state(
        state,
        _triangle_edges(),
        target_r=1,
    )

    updated = cache.with_updates(
        (0, 2),
        (1, 3),
    )

    np.testing.assert_array_equal(
        updated.edge_distances,
        np.array([1, 2, 3], dtype=np.int64),
    )
    assert updated.score == score_edge_distances(
        np.array([1, 2, 3], dtype=np.int64),
        target_r=1,
    )


@pytest.mark.parametrize(
    "edges",
    [
        np.array([0, 1], dtype=np.int64),
        np.empty((0, 2), dtype=np.int64),
        np.array([[0, 0]], dtype=np.int64),
        np.array([[1, 0]], dtype=np.int64),
        np.array([[0, 3]], dtype=np.int64),
        np.array([[0, 2], [0, 1]], dtype=np.int64),
        np.array([[0, 1], [0, 1]], dtype=np.int64),
        np.array([[0.0, 1.0]], dtype=np.float64),
    ],
)
def test_malformed_edges_are_rejected(edges: np.ndarray) -> None:
    with pytest.raises(ScoringError):
        canonical_edges_array(edges, vertex_count=3)


@pytest.mark.parametrize(
    ("distances", "target"),
    [
        (np.array([], dtype=np.int64), 1),
        (np.array([[1]], dtype=np.int64), 1),
        (np.array([1.0]), 1),
        (np.array([-1], dtype=np.int64), 1),
        (np.array([1], dtype=np.int64), -1),
    ],
)
def test_malformed_objective_inputs_are_rejected(
    distances: np.ndarray,
    target: int,
) -> None:
    with pytest.raises(ScoringError):
        score_edge_distances(distances, target)

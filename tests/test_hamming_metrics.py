from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.metrics.hamming import (
    hamming_distances_for_pairs,
    raw_hamming_distance,
)
from sphere_encoding.metrics.local import (
    edge_hamming_distances,
    local_hamming_metrics,
)


def test_exact_raw_hamming_distance() -> None:
    assert raw_hamming_distance(
        np.array([0, 1, 1, 0], dtype=np.uint8),
        np.array([1, 1, 0, 0], dtype=np.uint8),
    ) == 2


def test_vectorised_hamming_matches_brute_force() -> None:
    codes = np.array(
        [
            [0, 0, 0],
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ],
        dtype=np.uint8,
    )
    pairs = np.array(
        [
            [2, 3],
            [0, 2],
            [1, 3],
            [0, 1],
        ],
        dtype=np.int64,
    )

    vectorised = hamming_distances_for_pairs(codes, pairs)
    brute_force = np.array(
        [
            raw_hamming_distance(codes[left], codes[right])
            for left, right in pairs
        ],
        dtype=np.int64,
    )

    assert np.array_equal(vectorised, brute_force)


def test_edge_order_is_preserved_exactly() -> None:
    codes = np.array(
        [
            [0, 0, 0],
            [0, 0, 1],
            [1, 1, 1],
        ],
        dtype=np.uint8,
    )
    edges = np.array(
        [
            [0, 2],
            [0, 1],
            [1, 2],
        ],
        dtype=np.int64,
    )

    assert edge_hamming_distances(codes, edges).tolist() == [3, 1, 2]


def test_empty_edges_are_rejected() -> None:
    codes = np.array([[0], [1]], dtype=np.uint8)

    with pytest.raises(ValueError, match="must not be empty"):
        edge_hamming_distances(
            codes,
            np.empty((0, 2), dtype=np.int64),
        )


def test_local_metrics_and_complete_histogram() -> None:
    distances = np.array([0, 1, 1, 3], dtype=np.int64)
    metrics = local_hamming_metrics(
        distances,
        code_length=4,
    )

    assert metrics["L_max"] == 3
    assert metrics["L_max_edge_count"] == 1
    assert metrics["L_minimum"] == 0
    assert metrics["edge_count"] == 4
    assert metrics["histogram"] == [1, 2, 0, 1, 0]
    assert metrics["L_mean"] == pytest.approx(1.25)
    assert metrics["L_standard_deviation"] == pytest.approx(
        np.std(distances, ddof=0)
    )


def test_higher_quantile_rule_uses_observed_tail_value() -> None:
    metrics = local_hamming_metrics(
        np.array([0, 1, 1, 3], dtype=np.int64),
        code_length=3,
    )

    assert metrics["L_95"] == 3
    assert metrics["L_99"] == 3


def test_higher_quantile_rule_on_short_repeated_array() -> None:
    metrics = local_hamming_metrics(
        np.array([2, 2], dtype=np.int64),
        code_length=3,
    )

    assert metrics["L_95"] == 2
    assert metrics["L_99"] == 2

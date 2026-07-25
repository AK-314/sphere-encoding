from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.metrics.global_metrics import (
    antipodal_hamming_metrics,
    evaluate_exhaustive_global,
    far_pair_metrics,
    global_distortion_metrics,
)


def test_exact_zero_distortion_example() -> None:
    metrics = global_distortion_metrics(
        np.array([0.0, 0.5, 1.0]),
        np.array([0, 1, 2], dtype=np.int64),
        code_length=2,
    )

    assert metrics["maximum_absolute_distortion"] == 0.0
    assert metrics["mean_absolute_distortion"] == 0.0
    assert metrics["mean_normalised_angular_distance"] == 0.5
    assert metrics["mean_normalised_hamming_distance"] == 0.5
    assert metrics["root_mean_squared_distortion"] == 0.0
    assert metrics["spearman_angular_hamming_correlation"] == pytest.approx(
        1.0
    )
    assert metrics["unordered_pair_count"] == 3


def test_global_distortion_matches_brute_force_reference() -> None:
    angular = np.array([0.2, 0.7, 0.9])
    raw = np.array([1, 2, 4], dtype=np.int64)
    normalised = raw / 4
    difference = normalised - angular

    metrics = global_distortion_metrics(
        angular,
        raw,
        code_length=4,
    )

    assert metrics["mean_absolute_distortion"] == pytest.approx(
        np.mean(np.abs(difference))
    )
    assert metrics["root_mean_squared_distortion"] == pytest.approx(
        np.sqrt(np.mean(np.square(difference)))
    )
    assert metrics["maximum_absolute_distortion"] == pytest.approx(
        np.max(np.abs(difference))
    )


def test_far_pair_threshold_includes_exactly_point_75() -> None:
    metrics = far_pair_metrics(
        np.array([0.749999, 0.75, 1.0]),
        np.array([1, 2, 4], dtype=np.int64),
        code_length=4,
        threshold=0.75,
    )

    assert metrics["far_pair_count"] == 2
    assert metrics["minimum_raw_hamming_distance"] == 2
    assert metrics["mean_raw_hamming_distance"] == pytest.approx(3.0)
    assert metrics["minimum_normalised_hamming_distance"] == 0.5
    assert metrics["mean_normalised_hamming_distance"] == 0.75


def test_antipodal_hamming_metrics() -> None:
    metrics = antipodal_hamming_metrics(
        np.array([2, 4], dtype=np.int64),
        code_length=4,
    )

    assert metrics == {
        "antipodal_pair_count": 2,
        "maximum_raw_hamming_distance": 4,
        "mean_normalised_hamming_distance": 0.75,
        "mean_raw_hamming_distance": 3.0,
        "minimum_normalised_hamming_distance": 0.5,
        "minimum_raw_hamming_distance": 2,
    }


def test_exhaustive_global_pair_and_antipodal_counts() -> None:
    vertices = np.array(
        [
            [1.0, 0.0],
            [-1.0, 0.0],
            [0.0, 1.0],
            [0.0, -1.0],
        ]
    )
    codes = np.array(
        [
            [0, 0],
            [0, 1],
            [1, 0],
            [1, 1],
        ],
        dtype=np.uint8,
    )

    result = evaluate_exhaustive_global(
        vertices,
        codes,
        far_threshold=0.75,
        antipodal_atol=1e-12,
        expected_antipodal_count=2,
    )

    assert result["global"]["unordered_pair_count"] == 6
    assert result["antipodal_pairs"]["antipodal_pair_count"] == 2
    assert result["far_pairs"]["far_pair_count"] == 2

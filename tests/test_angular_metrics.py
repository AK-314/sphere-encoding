from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.metrics.angular import (
    antipodal_pair_indices,
    exhaustive_unordered_pairs,
    normalised_angular_distances,
    normalised_angular_from_dot_products,
)


def test_identical_orthogonal_and_antipodal_angles() -> None:
    dots = np.array([1.0, 0.0, -1.0], dtype=np.float64)

    assert normalised_angular_from_dot_products(dots) == pytest.approx(
        [0.0, 0.5, 1.0]
    )


def test_dot_products_are_clipped_at_floating_boundaries() -> None:
    dots = np.array(
        [
            1.0 + 1e-14,
            -1.0 - 1e-14,
        ],
        dtype=np.float64,
    )

    assert normalised_angular_from_dot_products(dots) == pytest.approx(
        [0.0, 1.0]
    )


def test_exhaustive_unordered_pair_ordering() -> None:
    pairs = exhaustive_unordered_pairs(4)

    assert pairs.tolist() == [
        [0, 1],
        [0, 2],
        [0, 3],
        [1, 2],
        [1, 3],
        [2, 3],
    ]


def test_normalised_angular_distances_preserve_pair_order() -> None:
    vertices = np.array(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [-1.0, 0.0],
        ]
    )
    pairs = np.array(
        [
            [0, 2],
            [0, 1],
        ],
        dtype=np.int64,
    )

    assert normalised_angular_distances(
        vertices,
        pairs,
    ) == pytest.approx([1.0, 0.5])


def test_antipodal_pairs_are_complete_and_lexicographic() -> None:
    vertices = np.array(
        [
            [1.0, 0.0],
            [-1.0, 0.0],
            [0.0, 1.0],
            [0.0, -1.0],
        ]
    )

    pairs = antipodal_pair_indices(
        vertices,
        atol=1e-12,
        expected_count=2,
        require_complete_pairing=True,
    )

    assert pairs.tolist() == [[0, 1], [2, 3]]


def test_incomplete_antipodal_pairing_is_rejected() -> None:
    vertices = np.array(
        [
            [1.0, 0.0],
            [-1.0, 0.0],
            [0.0, 1.0],
        ]
    )

    with pytest.raises(ValueError):
        antipodal_pair_indices(
            vertices,
            atol=1e-12,
            require_complete_pairing=True,
        )

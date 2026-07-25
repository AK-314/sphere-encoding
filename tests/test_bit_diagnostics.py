from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.metrics.bit_diagnostics import (
    bit_balance_diagnostics,
    bit_redundancy_diagnostics,
    collision_diagnostics,
)


def test_perfectly_balanced_bits() -> None:
    codes = np.array(
        [
            [0, 0],
            [0, 1],
            [1, 0],
            [1, 1],
        ],
        dtype=np.uint8,
    )

    metrics = bit_balance_diagnostics(codes)

    assert metrics == {
        "constant_bit_count": 0,
        "maximum_absolute_deviation_from_half": 0.0,
        "mean_absolute_deviation_from_half": 0.0,
        "per_bit_fraction_of_ones": [0.5, 0.5],
    }


def test_constant_bits_are_reported() -> None:
    codes = np.array(
        [
            [0, 1, 0],
            [0, 1, 1],
            [0, 1, 0],
            [0, 1, 1],
        ],
        dtype=np.uint8,
    )

    balance = bit_balance_diagnostics(codes)
    redundancy = bit_redundancy_diagnostics(codes)

    assert balance["constant_bit_count"] == 2
    assert balance["maximum_absolute_deviation_from_half"] == 0.5
    assert redundancy["complementary_bit_column_pair_count"] == 1
    assert redundancy["maximum_absolute_pearson_correlation"] is None


def test_duplicate_and_complementary_columns() -> None:
    first = np.array([0, 0, 1, 1], dtype=np.uint8)
    second = first.copy()
    third = 1 - first
    codes = np.column_stack((first, second, third))

    metrics = bit_redundancy_diagnostics(codes)

    assert metrics["duplicate_bit_column_pair_count"] == 1
    assert metrics["complementary_bit_column_pair_count"] == 2
    assert metrics["maximum_absolute_pearson_correlation"] == pytest.approx(
        1.0
    )


def test_correlated_and_anticorrelated_columns() -> None:
    first = np.array([0, 0, 1, 1], dtype=np.uint8)
    second = np.array([0, 1, 1, 1], dtype=np.uint8)
    third = 1 - second
    codes = np.column_stack((first, second, third))

    metrics = bit_redundancy_diagnostics(codes)

    assert metrics["maximum_absolute_pearson_correlation"] == pytest.approx(
        1.0
    )


def test_collision_diagnostics_are_reexported() -> None:
    codes = np.array(
        [
            [0, 0],
            [0, 0],
            [1, 1],
        ],
        dtype=np.uint8,
    )

    assert collision_diagnostics(codes)["collision_count"] == 1

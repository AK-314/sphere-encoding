from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.metrics.ranking import (
    average_ranks,
    pearson_correlation,
    spearman_correlation,
)


def test_average_ranks_without_ties() -> None:
    assert average_ranks([30, 10, 20]).tolist() == [3.0, 1.0, 2.0]


def test_average_ranks_with_ties() -> None:
    assert average_ranks([10, 20, 20, 40]).tolist() == [
        1.0,
        2.5,
        2.5,
        4.0,
    ]


def test_perfect_increasing_and_decreasing_spearman() -> None:
    assert spearman_correlation(
        [1, 2, 3, 4],
        [10, 20, 30, 40],
    ) == pytest.approx(1.0)

    assert spearman_correlation(
        [1, 2, 3, 4],
        [40, 30, 20, 10],
    ) == pytest.approx(-1.0)


def test_constant_rank_variable_returns_none() -> None:
    assert spearman_correlation(
        [1, 1, 1],
        [1, 2, 3],
    ) is None

    assert pearson_correlation(
        [0, 0, 0],
        [1, 2, 3],
    ) is None


def test_tied_reference_example() -> None:
    # Average ranks are [1, 2.5, 2.5, 4] and [4, 1.5, 1.5, 3].
    # Their independently hand-calculated Pearson correlation is -1/3.
    assert spearman_correlation(
        [1, 2, 2, 3],
        [4, 1, 1, 2],
    ) == pytest.approx(-1.0 / 3.0)


def test_rank_input_must_be_finite() -> None:
    with pytest.raises(ValueError):
        average_ranks(np.array([1.0, np.nan]))

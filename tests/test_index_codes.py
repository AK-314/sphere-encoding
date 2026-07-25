from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.encodings.index_codes import (
    canonical_index_binary,
    canonical_index_gray,
    fixed_width_binary,
    reflected_gray_values,
)


def test_fixed_width_binary_is_msb_first() -> None:
    values = np.array([0, 1, 2, 5], dtype=np.int64)

    assert fixed_width_binary(values, width=3).tolist() == [
        [0, 0, 0],
        [0, 0, 1],
        [0, 1, 0],
        [1, 0, 1],
    ]


def test_fixed_width_binary_rejects_insufficient_width() -> None:
    with pytest.raises(ValueError, match="insufficient"):
        fixed_width_binary(
            np.array([0, 4], dtype=np.int64),
            width=2,
        )


def test_reflected_gray_integer_examples() -> None:
    values = np.arange(8, dtype=np.int64)

    assert reflected_gray_values(values).tolist() == [
        0,
        1,
        3,
        2,
        6,
        7,
        5,
        4,
    ]


def test_canonical_index_binary_exact_example() -> None:
    codes = canonical_index_binary(5)

    assert codes.dtype == np.uint8
    assert codes.shape == (5, 3)
    assert codes.tolist() == [
        [0, 0, 0],
        [0, 0, 1],
        [0, 1, 0],
        [0, 1, 1],
        [1, 0, 0],
    ]


def test_canonical_index_gray_exact_example() -> None:
    codes = canonical_index_gray(5)

    assert codes.dtype == np.uint8
    assert codes.shape == (5, 3)
    assert codes.tolist() == [
        [0, 0, 0],
        [0, 0, 1],
        [0, 1, 1],
        [0, 1, 0],
        [1, 1, 0],
    ]


@pytest.mark.parametrize(
    "encoder",
    [
        canonical_index_binary,
        canonical_index_gray,
    ],
)
def test_index_encoders_are_injective_and_minimum_width(
    encoder,
) -> None:
    codes = encoder(13)

    assert codes.shape == (13, 4)
    assert len(np.unique(codes, axis=0)) == 13


@pytest.mark.parametrize("vertex_count", [-1, 0, 1])
def test_index_encoders_require_at_least_two_vertices(
    vertex_count: int,
) -> None:
    with pytest.raises(ValueError):
        canonical_index_binary(vertex_count)

    with pytest.raises(ValueError):
        canonical_index_gray(vertex_count)

from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.encodings.cartesian_codes import (
    cartesian_coordinate_binary,
    cartesian_coordinate_gray,
    coordinate_bit_width,
)


@pytest.mark.parametrize(
    ("q", "expected_width"),
    [
        (2, 3),
        (3, 3),
        (4, 4),
    ],
)
def test_coordinate_bit_width(
    q: int,
    expected_width: int,
) -> None:
    assert coordinate_bit_width(q) == expected_width


def test_cartesian_binary_exact_xyz_concatenation() -> None:
    vectors = np.array(
        [
            [-2, 0, 2],
            [2, -2, 0],
        ],
        dtype=np.int64,
    )

    codes = cartesian_coordinate_binary(vectors, q=2)

    assert codes.dtype == np.uint8
    assert codes.shape == (2, 9)
    assert codes.tolist() == [
        [0, 0, 0, 0, 1, 0, 1, 0, 0],
        [1, 0, 0, 0, 0, 0, 0, 1, 0],
    ]


def test_cartesian_gray_exact_xyz_concatenation() -> None:
    vectors = np.array(
        [
            [-2, 0, 2],
            [2, -2, 0],
        ],
        dtype=np.int64,
    )

    codes = cartesian_coordinate_gray(vectors, q=2)

    assert codes.dtype == np.uint8
    assert codes.shape == (2, 9)
    assert codes.tolist() == [
        [0, 0, 0, 0, 1, 1, 1, 1, 0],
        [1, 1, 0, 0, 0, 0, 0, 1, 1],
    ]


@pytest.mark.parametrize(
    "encoder",
    [
        cartesian_coordinate_binary,
        cartesian_coordinate_gray,
    ],
)
def test_cartesian_encoders_preserve_row_order_and_are_injective(
    encoder,
) -> None:
    vectors = np.array(
        [
            [0, 0, 1],
            [-1, 0, 0],
            [0, 1, 0],
            [1, 0, 0],
        ],
        dtype=np.int64,
    )

    codes = encoder(vectors, q=1)

    assert codes.shape == (4, 6)
    assert len(np.unique(codes, axis=0)) == 4

    reversed_codes = encoder(vectors[::-1], q=1)
    assert np.array_equal(reversed_codes, codes[::-1])


@pytest.mark.parametrize(
    "encoder",
    [
        cartesian_coordinate_binary,
        cartesian_coordinate_gray,
    ],
)
def test_cartesian_encoders_reject_out_of_range_coordinates(
    encoder,
) -> None:
    vectors = np.array(
        [
            [0, 0, 0],
            [3, 0, 0],
        ],
        dtype=np.int64,
    )

    with pytest.raises(ValueError, match="outside"):
        encoder(vectors, q=2)


@pytest.mark.parametrize(
    "encoder",
    [
        cartesian_coordinate_binary,
        cartesian_coordinate_gray,
    ],
)
def test_duplicate_vectors_are_rejected_as_noninjective(
    encoder,
) -> None:
    vectors = np.array(
        [
            [1, 0, 0],
            [1, 0, 0],
        ],
        dtype=np.int64,
    )

    with pytest.raises(ValueError, match="injective"):
        encoder(vectors, q=1)

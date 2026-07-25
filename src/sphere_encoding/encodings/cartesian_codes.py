"""Cartesian-coordinate binary and reflected-Gray baseline encoders."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from sphere_encoding.encodings.index_codes import (
    fixed_width_binary,
    reflected_gray_values,
)
from sphere_encoding.encodings.validation import validate_binary_codes
from sphere_encoding.graphs.common import minimum_bits

UInt8Array = npt.NDArray[np.uint8]


def coordinate_bit_width(q: int) -> int:
    """Return ceil(log2(2q+1)) using exact integer arithmetic."""
    if q <= 0:
        raise ValueError("q must be positive")
    return minimum_bits(2 * q + 1)


def _validated_integer_vectors(
    integer_vectors: npt.ArrayLike,
    *,
    q: int,
) -> npt.NDArray[np.int64]:
    if q <= 0:
        raise ValueError("q must be positive")

    array = np.asarray(integer_vectors)

    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("integer_vectors must have shape (N, 3)")
    if len(array) == 0:
        raise ValueError("integer_vectors must not be empty")
    if not np.issubdtype(array.dtype, np.integer):
        raise ValueError("integer_vectors must be integral")

    integer_array = np.asarray(array, dtype=np.int64)

    if np.any(np.abs(integer_array) > q):
        raise ValueError("integer coordinate lies outside [-q, q]")

    return integer_array


def _concatenate_coordinate_codes(
    coordinate_values: npt.NDArray[np.int64],
    *,
    width: int,
) -> UInt8Array:
    encoded_coordinates = [
        fixed_width_binary(
            coordinate_values[:, coordinate_index],
            width=width,
        )
        for coordinate_index in range(3)
    ]
    return np.concatenate(encoded_coordinates, axis=1).astype(
        np.uint8,
        copy=False,
    )


def cartesian_coordinate_binary(
    integer_vectors: npt.ArrayLike,
    *,
    q: int,
) -> UInt8Array:
    """Encode shifted x, y, z coordinates in fixed-width binary."""
    vectors = _validated_integer_vectors(integer_vectors, q=q)
    width = coordinate_bit_width(q)
    shifted = vectors + q
    codes = _concatenate_coordinate_codes(
        shifted,
        width=width,
    )

    return validate_binary_codes(
        codes,
        expected_vertex_count=len(vectors),
        expected_code_length=3 * width,
    )


def cartesian_coordinate_gray(
    integer_vectors: npt.ArrayLike,
    *,
    q: int,
) -> UInt8Array:
    """Encode shifted x, y, z coordinates with reflected Gray codes."""
    vectors = _validated_integer_vectors(integer_vectors, q=q)
    width = coordinate_bit_width(q)
    shifted = vectors + q

    gray_coordinates = np.column_stack(
        [
            reflected_gray_values(
                shifted[:, coordinate_index],
            )
            for coordinate_index in range(3)
        ]
    ).astype(np.int64, copy=False)

    codes = _concatenate_coordinate_codes(
        gray_coordinates,
        width=width,
    )

    return validate_binary_codes(
        codes,
        expected_vertex_count=len(vectors),
        expected_code_length=3 * width,
    )

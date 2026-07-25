"""Canonical-index binary and reflected-Gray baseline encoders."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from sphere_encoding.encodings.validation import validate_binary_codes
from sphere_encoding.graphs.common import minimum_bits

UInt8Array = npt.NDArray[np.uint8]


def fixed_width_binary(
    values: npt.ArrayLike,
    *,
    width: int,
) -> UInt8Array:
    """Encode non-negative integers in fixed-width MSB-first binary."""
    array = np.asarray(values)

    if array.ndim != 1:
        raise ValueError("values must be one-dimensional")
    if len(array) == 0:
        raise ValueError("values must not be empty")
    if not np.issubdtype(array.dtype, np.integer):
        raise ValueError("values must be integral")
    if width <= 0:
        raise ValueError("width must be positive")

    integer_array = np.asarray(array, dtype=np.int64)

    if np.any(integer_array < 0):
        raise ValueError("values must be non-negative")
    if np.any(integer_array >= 1 << width):
        raise ValueError("width is insufficient for at least one value")

    shifts = np.arange(
        width - 1,
        -1,
        -1,
        dtype=np.int64,
    )
    codes = (integer_array[:, None] >> shifts[None, :]) & 1
    return np.asarray(codes, dtype=np.uint8)


def reflected_gray_values(
    values: npt.ArrayLike,
) -> npt.NDArray[np.int64]:
    """Return reflected-Gray integer values g(v)=v xor (v >> 1)."""
    array = np.asarray(values)

    if array.ndim != 1:
        raise ValueError("values must be one-dimensional")
    if len(array) == 0:
        raise ValueError("values must not be empty")
    if not np.issubdtype(array.dtype, np.integer):
        raise ValueError("values must be integral")

    integer_array = np.asarray(array, dtype=np.int64)

    if np.any(integer_array < 0):
        raise ValueError("values must be non-negative")

    return np.asarray(
        integer_array ^ (integer_array >> 1),
        dtype=np.int64,
    )


def canonical_index_binary(
    vertex_count: int,
) -> UInt8Array:
    """Encode canonical row indices using minimum-width standard binary."""
    if vertex_count < 2:
        raise ValueError("vertex_count must be at least two")

    width = minimum_bits(vertex_count)
    indices = np.arange(vertex_count, dtype=np.int64)
    codes = fixed_width_binary(indices, width=width)

    return validate_binary_codes(
        codes,
        expected_vertex_count=vertex_count,
        expected_code_length=width,
    )


def canonical_index_gray(
    vertex_count: int,
) -> UInt8Array:
    """Encode canonical row indices using minimum-width reflected Gray."""
    if vertex_count < 2:
        raise ValueError("vertex_count must be at least two")

    width = minimum_bits(vertex_count)
    indices = np.arange(vertex_count, dtype=np.int64)
    gray_values = reflected_gray_values(indices)
    codes = fixed_width_binary(gray_values, width=width)

    return validate_binary_codes(
        codes,
        expected_vertex_count=vertex_count,
        expected_code_length=width,
    )

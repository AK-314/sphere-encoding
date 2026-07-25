"""Strict validation for hard-binary code arrays."""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

UInt8Array = npt.NDArray[np.uint8]


class EncodingValidationError(ValueError):
    """Raised when an encoding violates a frozen Stage 3 validity rule."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EncodingValidationError(message)


def validate_binary_codes(
    codes: npt.ArrayLike,
    *,
    expected_vertex_count: int | None = None,
    expected_code_length: int | None = None,
    require_injective: bool = True,
) -> UInt8Array:
    """Validate and return a canonical uint8 hard-binary code matrix."""
    array = np.asarray(codes)

    _require(array.ndim == 2, "codes must have shape (N, m)")
    vertex_count, code_length = array.shape
    _require(vertex_count > 0, "codes must contain at least one row")
    _require(code_length > 0, "code length must be positive")
    _require(
        np.issubdtype(array.dtype, np.bool_)
        or np.issubdtype(array.dtype, np.integer),
        "codes must use Boolean or integer dtype",
    )

    if expected_vertex_count is not None:
        _require(
            expected_vertex_count > 0,
            "expected vertex count must be positive",
        )
        _require(
            vertex_count == expected_vertex_count,
            "code row count does not match expected vertex count",
        )

    if expected_code_length is not None:
        _require(
            expected_code_length > 0,
            "expected code length must be positive",
        )
        _require(
            code_length == expected_code_length,
            "code column count does not match expected code length",
        )

    _require(
        bool(np.all((array == 0) | (array == 1))),
        "codes must contain only zero and one",
    )

    canonical = np.asarray(array, dtype=np.uint8)

    if require_injective:
        diagnostics = collision_diagnostics(canonical)
        _require(
            diagnostics["collision_count"] == 0,
            "definitive encoding must be injective",
        )

    return canonical


def collision_diagnostics(
    codes: npt.ArrayLike,
) -> dict[str, Any]:
    """Return deterministic codeword-collision diagnostics."""
    array = validate_binary_codes(
        codes,
        require_injective=False,
    )
    _, counts = np.unique(array, axis=0, return_counts=True)

    unique_count = len(counts)
    collision_count = int(len(array) - unique_count)
    largest_class = int(np.max(counts))
    multi_member_classes = int(np.count_nonzero(counts > 1))

    return {
        "collision_count": collision_count,
        "largest_collision_class_size": largest_class,
        "multi_member_collision_class_count": multi_member_classes,
        "unique_codeword_count": unique_count,
    }

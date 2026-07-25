from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.encodings.validation import (
    EncodingValidationError,
    collision_diagnostics,
    validate_binary_codes,
)


def test_valid_binary_integer_array_is_canonical_uint8() -> None:
    codes = np.array(
        [
            [0, 0],
            [0, 1],
            [1, 0],
        ],
        dtype=np.int64,
    )

    validated = validate_binary_codes(
        codes,
        expected_vertex_count=3,
        expected_code_length=2,
    )

    assert validated.dtype == np.uint8
    assert np.array_equal(validated, codes)


def test_valid_boolean_array_is_accepted() -> None:
    codes = np.array(
        [
            [False, False],
            [False, True],
            [True, False],
        ],
        dtype=np.bool_,
    )

    assert validate_binary_codes(codes).dtype == np.uint8


@pytest.mark.parametrize(
    "codes",
    [
        np.array([[0.0, 1.0]], dtype=np.float64),
        np.array([[0, 2]], dtype=np.int64),
        np.array([[0, -1]], dtype=np.int64),
    ],
)
def test_nonbinary_or_nonintegral_arrays_are_rejected(
    codes: np.ndarray,
) -> None:
    with pytest.raises(EncodingValidationError):
        validate_binary_codes(codes, require_injective=False)


def test_shape_mismatch_is_rejected() -> None:
    codes = np.array([[0, 1], [1, 0]], dtype=np.uint8)

    with pytest.raises(EncodingValidationError):
        validate_binary_codes(
            codes,
            expected_vertex_count=3,
        )

    with pytest.raises(EncodingValidationError):
        validate_binary_codes(
            codes,
            expected_code_length=3,
        )


def test_empty_or_zero_length_code_array_is_rejected() -> None:
    with pytest.raises(EncodingValidationError):
        validate_binary_codes(
            np.empty((0, 2), dtype=np.uint8),
            require_injective=False,
        )

    with pytest.raises(EncodingValidationError):
        validate_binary_codes(
            np.empty((2, 0), dtype=np.uint8),
            require_injective=False,
        )


def test_collision_detection_and_injective_rejection() -> None:
    codes = np.array(
        [
            [0, 0],
            [0, 0],
            [1, 1],
        ],
        dtype=np.uint8,
    )

    assert collision_diagnostics(codes) == {
        "collision_count": 1,
        "largest_collision_class_size": 2,
        "multi_member_collision_class_count": 1,
        "unique_codeword_count": 2,
    }

    with pytest.raises(EncodingValidationError):
        validate_binary_codes(codes)

"""Binary-encoding construction, applicability and validation."""

from sphere_encoding.encodings.applicability import (
    BASELINE_ENCODING_IDS,
    CARTESIAN_INAPPLICABLE_REASON,
    build_applicability_matrix,
    encoding_is_applicable,
    validate_frozen_stage3_applicability,
)
from sphere_encoding.encodings.cartesian_codes import (
    cartesian_coordinate_binary,
    cartesian_coordinate_gray,
    coordinate_bit_width,
)
from sphere_encoding.encodings.index_codes import (
    canonical_index_binary,
    canonical_index_gray,
    fixed_width_binary,
    reflected_gray_values,
)
from sphere_encoding.encodings.validation import (
    EncodingValidationError,
    collision_diagnostics,
    validate_binary_codes,
)

__all__ = [
    "BASELINE_ENCODING_IDS",
    "CARTESIAN_INAPPLICABLE_REASON",
    "EncodingValidationError",
    "build_applicability_matrix",
    "canonical_index_binary",
    "canonical_index_gray",
    "cartesian_coordinate_binary",
    "cartesian_coordinate_gray",
    "collision_diagnostics",
    "coordinate_bit_width",
    "encoding_is_applicable",
    "fixed_width_binary",
    "reflected_gray_values",
    "validate_binary_codes",
    "validate_frozen_stage3_applicability",
]

"""Binary-encoding construction and validation."""

from sphere_encoding.encodings.validation import (
    EncodingValidationError,
    collision_diagnostics,
    validate_binary_codes,
)

__all__ = [
    "EncodingValidationError",
    "collision_diagnostics",
    "validate_binary_codes",
]

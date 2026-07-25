"""Collision, bit-balance and bit-redundancy diagnostics."""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from sphere_encoding.encodings.validation import (
    collision_diagnostics,
    validate_binary_codes,
)
from sphere_encoding.metrics.ranking import pearson_correlation


def bit_balance_diagnostics(
    codes: npt.ArrayLike,
) -> dict[str, Any]:
    """Return frozen per-bit balance diagnostics."""
    array = validate_binary_codes(
        codes,
        require_injective=False,
    )
    fractions = np.mean(array, axis=0, dtype=np.float64)
    deviations = np.abs(fractions - 0.5)
    constant = (fractions == 0.0) | (fractions == 1.0)

    return {
        "constant_bit_count": int(np.count_nonzero(constant)),
        "maximum_absolute_deviation_from_half": float(
            np.max(deviations)
        ),
        "mean_absolute_deviation_from_half": float(
            np.mean(deviations)
        ),
        "per_bit_fraction_of_ones": [
            float(value)
            for value in fractions
        ],
    }


def bit_redundancy_diagnostics(
    codes: npt.ArrayLike,
) -> dict[str, Any]:
    """Return exact duplicate/complement and nonconstant correlation data."""
    array = validate_binary_codes(
        codes,
        require_injective=False,
    )
    columns = array.T
    constant_mask = np.all(columns == columns[:, :1], axis=1)

    duplicate_count = 0
    complementary_count = 0

    for left in range(len(columns) - 1):
        for right in range(left + 1, len(columns)):
            if np.array_equal(columns[left], columns[right]):
                duplicate_count += 1
            if np.array_equal(columns[left], 1 - columns[right]):
                complementary_count += 1

    nonconstant_indices = np.flatnonzero(~constant_mask)
    correlations: list[float] = []

    for position, left in enumerate(nonconstant_indices[:-1]):
        for right in nonconstant_indices[position + 1 :]:
            correlation = pearson_correlation(
                columns[left],
                columns[right],
            )
            if correlation is None:
                raise RuntimeError(
                    "nonconstant bit pair produced undefined correlation"
                )
            correlations.append(abs(correlation))

    maximum_correlation = (
        float(max(correlations))
        if correlations
        else None
    )

    return {
        "complementary_bit_column_pair_count": complementary_count,
        "duplicate_bit_column_pair_count": duplicate_count,
        "maximum_absolute_pearson_correlation": maximum_correlation,
    }


__all__ = [
    "bit_balance_diagnostics",
    "bit_redundancy_diagnostics",
    "collision_diagnostics",
]

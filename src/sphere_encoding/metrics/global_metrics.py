"""Exhaustive global angular-Hamming diagnostics."""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from sphere_encoding.encodings.validation import validate_binary_codes
from sphere_encoding.metrics.angular import (
    antipodal_pair_indices,
    exhaustive_unordered_pairs,
    normalised_angular_distances,
)
from sphere_encoding.metrics.hamming import hamming_distances_for_pairs
from sphere_encoding.metrics.ranking import spearman_correlation


def _validated_distance_arrays(
    angular_distances: npt.ArrayLike,
    raw_hamming_distances: npt.ArrayLike,
    *,
    code_length: int,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.int64]]:
    if code_length <= 0:
        raise ValueError("code_length must be positive")

    angular = np.asarray(angular_distances, dtype=np.float64)
    raw = np.asarray(raw_hamming_distances)

    if angular.ndim != 1 or raw.ndim != 1:
        raise ValueError("distance arrays must be one-dimensional")
    if len(angular) == 0 or len(raw) == 0:
        raise ValueError("distance arrays must not be empty")
    if angular.shape != raw.shape:
        raise ValueError("distance arrays must have the same shape")
    if not np.all(np.isfinite(angular)):
        raise ValueError("angular distances contain non-finite values")
    if np.any(angular < 0.0) or np.any(angular > 1.0):
        raise ValueError("normalised angular distance outside [0, 1]")
    if not np.issubdtype(raw.dtype, np.integer):
        raise ValueError("raw Hamming distances must be integral")

    raw = np.asarray(raw, dtype=np.int64)
    if np.any(raw < 0) or np.any(raw > code_length):
        raise ValueError("raw Hamming distance outside [0, m]")

    return angular, raw


def global_distortion_metrics(
    angular_distances: npt.ArrayLike,
    raw_hamming_distances: npt.ArrayLike,
    *,
    code_length: int,
) -> dict[str, Any]:
    """Calculate frozen exhaustive global distortion diagnostics."""
    angular, raw = _validated_distance_arrays(
        angular_distances,
        raw_hamming_distances,
        code_length=code_length,
    )
    normalised_hamming = raw.astype(np.float64) / code_length
    signed_difference = normalised_hamming - angular
    absolute_distortion = np.abs(signed_difference)

    return {
        "maximum_absolute_distortion": float(
            np.max(absolute_distortion)
        ),
        "mean_absolute_distortion": float(
            np.mean(absolute_distortion)
        ),
        "mean_normalised_angular_distance": float(
            np.mean(angular)
        ),
        "mean_normalised_hamming_distance": float(
            np.mean(normalised_hamming)
        ),
        "root_mean_squared_distortion": float(
            np.sqrt(np.mean(np.square(signed_difference)))
        ),
        "spearman_angular_hamming_correlation": (
            spearman_correlation(angular, normalised_hamming)
        ),
        "unordered_pair_count": len(angular),
    }


def far_pair_metrics(
    angular_distances: npt.ArrayLike,
    raw_hamming_distances: npt.ArrayLike,
    *,
    code_length: int,
    threshold: float,
) -> dict[str, Any]:
    """Calculate frozen diagnostics for angularly far pairs."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("far-pair threshold must lie in [0, 1]")

    angular, raw = _validated_distance_arrays(
        angular_distances,
        raw_hamming_distances,
        code_length=code_length,
    )
    selected = raw[angular >= threshold]

    if len(selected) == 0:
        raise ValueError("far-pair set is empty")

    normalised = selected.astype(np.float64) / code_length
    return {
        "far_pair_count": len(selected),
        "mean_normalised_hamming_distance": float(
            np.mean(normalised)
        ),
        "mean_raw_hamming_distance": float(np.mean(selected)),
        "minimum_normalised_hamming_distance": float(
            np.min(normalised)
        ),
        "minimum_raw_hamming_distance": int(np.min(selected)),
    }


def antipodal_hamming_metrics(
    raw_hamming_distances: npt.ArrayLike,
    *,
    code_length: int,
) -> dict[str, Any]:
    """Calculate frozen Hamming diagnostics for accepted antipodal pairs."""
    raw = np.asarray(raw_hamming_distances)

    if code_length <= 0:
        raise ValueError("code_length must be positive")
    if raw.ndim != 1:
        raise ValueError("raw Hamming distances must be one-dimensional")
    if len(raw) == 0:
        raise ValueError("antipodal-pair set is empty")
    if not np.issubdtype(raw.dtype, np.integer):
        raise ValueError("raw Hamming distances must be integral")

    raw = np.asarray(raw, dtype=np.int64)
    if np.any(raw < 0) or np.any(raw > code_length):
        raise ValueError("raw Hamming distance outside [0, m]")

    normalised = raw.astype(np.float64) / code_length
    return {
        "antipodal_pair_count": len(raw),
        "maximum_raw_hamming_distance": int(np.max(raw)),
        "mean_normalised_hamming_distance": float(
            np.mean(normalised)
        ),
        "mean_raw_hamming_distance": float(np.mean(raw)),
        "minimum_normalised_hamming_distance": float(
            np.min(normalised)
        ),
        "minimum_raw_hamming_distance": int(np.min(raw)),
    }


def evaluate_exhaustive_global(
    vertices: npt.ArrayLike,
    codes: npt.ArrayLike,
    *,
    far_threshold: float,
    antipodal_atol: float,
    expected_antipodal_count: int,
) -> dict[str, Any]:
    """Evaluate all frozen global, far-pair and antipodal diagnostics."""
    code_array = validate_binary_codes(codes)
    pairs = exhaustive_unordered_pairs(len(code_array))
    angular = normalised_angular_distances(vertices, pairs)
    raw_hamming = hamming_distances_for_pairs(code_array, pairs)

    antipodal_pairs = antipodal_pair_indices(
        vertices,
        atol=antipodal_atol,
        expected_count=expected_antipodal_count,
        require_complete_pairing=True,
    )
    antipodal_raw = hamming_distances_for_pairs(
        code_array,
        antipodal_pairs,
    )

    return {
        "antipodal_pairs": antipodal_hamming_metrics(
            antipodal_raw,
            code_length=code_array.shape[1],
        ),
        "far_pairs": far_pair_metrics(
            angular,
            raw_hamming,
            code_length=code_array.shape[1],
            threshold=far_threshold,
        ),
        "global": global_distortion_metrics(
            angular,
            raw_hamming,
            code_length=code_array.shape[1],
        ),
    }

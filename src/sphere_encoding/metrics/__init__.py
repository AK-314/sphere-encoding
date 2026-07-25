"""Deterministic Stage 3 encoding metrics."""

from sphere_encoding.metrics.angular import (
    antipodal_pair_indices,
    exhaustive_unordered_pairs,
    normalised_angular_distances,
    normalised_angular_from_dot_products,
)
from sphere_encoding.metrics.bit_diagnostics import (
    bit_balance_diagnostics,
    bit_redundancy_diagnostics,
)
from sphere_encoding.metrics.global_metrics import (
    antipodal_hamming_metrics,
    evaluate_exhaustive_global,
    far_pair_metrics,
    global_distortion_metrics,
)
from sphere_encoding.metrics.hamming import (
    hamming_distances_for_pairs,
    raw_hamming_distance,
)
from sphere_encoding.metrics.local import (
    edge_hamming_distances,
    local_hamming_metrics,
)
from sphere_encoding.metrics.ranking import (
    average_ranks,
    pearson_correlation,
    spearman_correlation,
)

__all__ = [
    "antipodal_hamming_metrics",
    "antipodal_pair_indices",
    "average_ranks",
    "bit_balance_diagnostics",
    "bit_redundancy_diagnostics",
    "edge_hamming_distances",
    "evaluate_exhaustive_global",
    "exhaustive_unordered_pairs",
    "far_pair_metrics",
    "global_distortion_metrics",
    "hamming_distances_for_pairs",
    "local_hamming_metrics",
    "normalised_angular_distances",
    "normalised_angular_from_dot_products",
    "pearson_correlation",
    "raw_hamming_distance",
    "spearman_correlation",
]

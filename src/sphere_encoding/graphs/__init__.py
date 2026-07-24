"""Deterministic finite sphere-graph generation and validation."""

from sphere_encoding.graphs.common import (
    angular_edge_lengths,
    antipodal_pair_count,
    canonical_edges_from_faces,
    connected,
    degree_histogram,
    degrees,
    distinct_tolerance_classes,
    face_orientation_values,
    has_near_duplicate_rows,
    lexicographically_sorted_rows,
    minimum_bits,
    normalise_rows,
)
from sphere_encoding.graphs.icosphere import (
    Icosphere,
    generate_icosphere,
)
from sphere_encoding.graphs.primitive import (
    PrimitiveDirectionGraph,
    build_primitive_direction_graph,
    generate_primitive_integer_vectors,
    tie_complete_directed_neighbours,
)
from sphere_encoding.graphs.validation import (
    GraphValidationError,
    validate_icosphere,
    validate_primitive_graph,
)

__all__ = [
    "GraphValidationError",
    "Icosphere",
    "PrimitiveDirectionGraph",
    "angular_edge_lengths",
    "antipodal_pair_count",
    "build_primitive_direction_graph",
    "canonical_edges_from_faces",
    "connected",
    "degree_histogram",
    "degrees",
    "distinct_tolerance_classes",
    "face_orientation_values",
    "generate_icosphere",
    "generate_primitive_integer_vectors",
    "has_near_duplicate_rows",
    "lexicographically_sorted_rows",
    "minimum_bits",
    "normalise_rows",
    "tie_complete_directed_neighbours",
    "validate_icosphere",
    "validate_primitive_graph",
]

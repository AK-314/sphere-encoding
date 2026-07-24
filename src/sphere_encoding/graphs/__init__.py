"""Deterministic finite sphere-graph generation and validation."""

from sphere_encoding.graphs.artifacts import (
    collect_file_hashes,
    deterministic_tar_gz_bytes,
    flatten_neighbours,
    generate_stage2_package,
    npy_bytes,
    read_npy,
    unflatten_neighbours,
    write_deterministic_tar_gz,
    write_npy,
)
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
    "collect_file_hashes",
    "connected",
    "degree_histogram",
    "degrees",
    "deterministic_tar_gz_bytes",
    "distinct_tolerance_classes",
    "face_orientation_values",
    "flatten_neighbours",
    "generate_icosphere",
    "generate_primitive_integer_vectors",
    "generate_stage2_package",
    "has_near_duplicate_rows",
    "lexicographically_sorted_rows",
    "minimum_bits",
    "normalise_rows",
    "npy_bytes",
    "read_npy",
    "tie_complete_directed_neighbours",
    "unflatten_neighbours",
    "validate_icosphere",
    "validate_primitive_graph",
    "write_deterministic_tar_gz",
    "write_npy",
]

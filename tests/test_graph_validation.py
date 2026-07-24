from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.graphs import (
    GraphValidationError,
    Icosphere,
    PrimitiveDirectionGraph,
    build_primitive_direction_graph,
    generate_icosphere,
    validate_icosphere,
    validate_primitive_graph,
)

TOLERANCES = {
    "angular_tie_atol_radians": 1e-12,
    "antipodal_atol": 1e-12,
    "duplicate_vertex_atol": 1e-12,
    "edge_length_class_atol_radians": 1e-12,
    "face_orientation_atol": 1e-15,
    "unit_norm_atol": 1e-12,
}


def test_icosphere_validation_rejects_duplicate_edge() -> None:
    mesh = generate_icosphere(0)
    malformed = Icosphere(
        subdivision_level=mesh.subdivision_level,
        vertices=mesh.vertices,
        edges=np.vstack([mesh.edges, mesh.edges[0]]),
        faces=mesh.faces,
    )

    with pytest.raises(GraphValidationError, match=r"sorted|duplicate"):
        validate_icosphere(malformed, tolerances=TOLERANCES)


def test_icosphere_validation_rejects_inward_face() -> None:
    mesh = generate_icosphere(0)
    faces = mesh.faces.copy()
    faces[0, 1], faces[0, 2] = faces[0, 2], faces[0, 1]
    malformed = Icosphere(
        subdivision_level=mesh.subdivision_level,
        vertices=mesh.vertices,
        edges=mesh.edges,
        faces=faces,
    )

    with pytest.raises(GraphValidationError, match="outward"):
        validate_icosphere(malformed, tolerances=TOLERANCES)


def test_primitive_validation_rejects_self_loop() -> None:
    graph = build_primitive_direction_graph(
        2,
        4,
        angular_tie_atol_radians=1e-12,
    )
    malformed_edges = graph.edges.copy()
    malformed_edges[0] = [0, 0]
    malformed = PrimitiveDirectionGraph(
        q=graph.q,
        nominal_k=graph.nominal_k,
        integer_vectors=graph.integer_vectors,
        vertices=graph.vertices,
        edges=malformed_edges,
        directed_neighbours=graph.directed_neighbours,
        threshold_angles=graph.threshold_angles,
    )

    with pytest.raises(GraphValidationError, match="canonical"):
        validate_primitive_graph(malformed, tolerances=TOLERANCES)

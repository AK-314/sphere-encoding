"""Strict validation for canonical sphere graphs."""

from __future__ import annotations

from collections import Counter
from math import gcd
from typing import Any

import numpy as np

from sphere_encoding.graphs.common import (
    angular_edge_lengths,
    antipodal_pair_count,
    canonical_edges_from_faces,
    canonical_edges_from_neighbours,
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
from sphere_encoding.graphs.icosphere import Icosphere
from sphere_encoding.graphs.primitive import PrimitiveDirectionGraph


class GraphValidationError(ValueError):
    """Raised when a graph violates a frozen structural rule."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GraphValidationError(message)


def _validate_canonical_edges(
    edges: np.ndarray,
    *,
    vertex_count: int,
) -> None:
    _require(edges.ndim == 2 and edges.shape[1] == 2, "invalid edge shape")
    _require(np.issubdtype(edges.dtype, np.integer), "edges must be integral")
    _require(np.all(edges >= 0), "negative edge index")
    _require(np.all(edges < vertex_count), "edge index out of range")
    _require(np.all(edges[:, 0] < edges[:, 1]), "non-canonical edge")
    _require(lexicographically_sorted_rows(edges), "edges are not sorted")
    _require(len({tuple(row) for row in edges.tolist()}) == len(edges), "duplicate edge")


def validate_icosphere(
    mesh: Icosphere,
    *,
    tolerances: dict[str, float],
    expected: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Validate one deterministic icosphere and return diagnostics."""
    vertices = np.asarray(mesh.vertices)
    edges = np.asarray(mesh.edges)
    faces = np.asarray(mesh.faces)
    vertex_count = len(vertices)

    unit_atol = tolerances["unit_norm_atol"]
    duplicate_atol = tolerances["duplicate_vertex_atol"]
    orientation_atol = tolerances["face_orientation_atol"]
    antipodal_atol = tolerances["antipodal_atol"]
    class_atol = tolerances["edge_length_class_atol_radians"]

    _require(
        vertices.ndim == 2 and vertices.shape[1] == 3,
        "vertices must have shape (N, 3)",
    )
    _require(np.issubdtype(vertices.dtype, np.floating), "vertices must be floating")
    _require(np.all(np.isfinite(vertices)), "non-finite vertex coordinate")
    _require(
        np.allclose(
            np.linalg.norm(vertices, axis=1),
            1.0,
            atol=unit_atol,
            rtol=0.0,
        ),
        "non-unit vertex",
    )
    _require(
        not has_near_duplicate_rows(vertices, atol=duplicate_atol),
        "duplicate vertex",
    )

    _require(faces.ndim == 2 and faces.shape[1] == 3, "invalid face shape")
    _require(np.issubdtype(faces.dtype, np.integer), "faces must be integral")
    _require(np.all(faces >= 0), "negative face index")
    _require(np.all(faces < vertex_count), "face index out of range")
    _require(
        np.all(
            (faces[:, 0] != faces[:, 1])
            & (faces[:, 1] != faces[:, 2])
            & (faces[:, 2] != faces[:, 0])
        ),
        "face contains repeated vertex",
    )

    canonical_faces = [tuple(sorted(row)) for row in faces.tolist()]
    _require(
        len(set(canonical_faces)) == len(canonical_faces),
        "duplicate face",
    )
    _require(
        np.all(face_orientation_values(vertices, faces) > orientation_atol),
        "face is not consistently outward",
    )

    _validate_canonical_edges(edges, vertex_count=vertex_count)
    expected_edges = canonical_edges_from_faces(faces)
    _require(np.array_equal(edges, expected_edges), "edge set differs from faces")
    _require(connected(vertex_count, edges), "graph is disconnected")

    incidence = Counter()
    for face in faces:
        a, b, c = (int(value) for value in face)
        for left, right in ((a, b), (b, c), (c, a)):
            incidence[tuple(sorted((left, right)))] += 1
    _require(
        set(incidence.values()) == {2},
        "triangulation edge incidence is not exactly two",
    )

    _require(
        vertex_count - len(edges) + len(faces) == 2,
        "Euler characteristic is not two",
    )

    degree_values = degrees(vertex_count, edges)
    degree_counts = Counter(int(value) for value in degree_values)
    if mesh.subdivision_level == 0:
        _require(degree_counts == {5: 12}, "unexpected level-zero degrees")
    else:
        _require(degree_counts.get(5, 0) == 12, "expected twelve degree-five vertices")
        _require(
            degree_counts.get(6, 0) == vertex_count - 12,
            "all other vertices must have degree six",
        )
        _require(set(degree_counts) == {5, 6}, "unexpected icosphere degree")

    antipodal_pairs = antipodal_pair_count(vertices, atol=antipodal_atol)
    _require(
        antipodal_pairs == vertex_count // 2,
        "incomplete or ambiguous antipodal pairing",
    )

    if expected is not None:
        _require(vertex_count == expected["vertices"], "unexpected vertex count")
        _require(len(edges) == expected["edges"], "unexpected edge count")
        _require(len(faces) == expected["faces"], "unexpected face count")
        _require(
            minimum_bits(vertex_count) == expected["minimum_bits"],
            "unexpected minimum-bit count",
        )
        _require(
            mesh.subdivision_level == expected["subdivision_level"],
            "unexpected subdivision level",
        )

    edge_angles = angular_edge_lengths(vertices, edges)
    return {
        "antipodal_pair_count": antipodal_pairs,
        "connected": True,
        "degree_histogram": degree_histogram(vertex_count, edges),
        "edge_count": len(edges),
        "edge_length_class_count": distinct_tolerance_classes(
            edge_angles,
            atol=class_atol,
        ),
        "face_count": len(faces),
        "maximum_degree": int(np.max(degree_values)),
        "maximum_edge_angle": float(np.max(edge_angles)),
        "minimum_bits": minimum_bits(vertex_count),
        "minimum_degree": int(np.min(degree_values)),
        "minimum_edge_angle": float(np.min(edge_angles)),
        "subdivision_level": mesh.subdivision_level,
        "topology_checks": {
            "edge_incidence_two": True,
            "euler_characteristic_two": True,
            "outward_faces": True,
        },
        "vertex_count": vertex_count,
    }


def validate_primitive_graph(
    graph: PrimitiveDirectionGraph,
    *,
    tolerances: dict[str, float],
    expected_point_count: int | None = None,
) -> dict[str, Any]:
    """Validate one primitive-direction graph and return diagnostics."""
    integer_vectors = np.asarray(graph.integer_vectors)
    vertices = np.asarray(graph.vertices)
    edges = np.asarray(graph.edges)
    vertex_count = len(vertices)

    unit_atol = tolerances["unit_norm_atol"]
    duplicate_atol = tolerances["duplicate_vertex_atol"]
    antipodal_atol = tolerances["antipodal_atol"]
    tie_atol = tolerances["angular_tie_atol_radians"]

    _require(
        integer_vectors.ndim == 2 and integer_vectors.shape[1] == 3,
        "invalid integer-vector shape",
    )
    _require(
        np.issubdtype(integer_vectors.dtype, np.integer),
        "integer vectors must be integral",
    )
    _require(np.all(np.abs(integer_vectors) <= graph.q), "coordinate exceeds q")
    _require(
        np.all(np.any(integer_vectors != 0, axis=1)),
        "zero integer vector",
    )
    _require(
        lexicographically_sorted_rows(integer_vectors),
        "integer vectors are not lexicographically ordered",
    )
    _require(
        len({tuple(row) for row in integer_vectors.tolist()}) == vertex_count,
        "duplicate integer vector",
    )

    for row in integer_vectors:
        x, y, z = (abs(int(value)) for value in row)
        _require(gcd(gcd(x, y), z) == 1, "non-primitive integer vector")

    _require(
        vertices.shape == integer_vectors.shape,
        "integer and floating row shapes differ",
    )
    _require(np.all(np.isfinite(vertices)), "non-finite vertex coordinate")
    _require(
        np.allclose(
            np.linalg.norm(vertices, axis=1),
            1.0,
            atol=unit_atol,
            rtol=0.0,
        ),
        "non-unit vertex",
    )
    _require(
        np.allclose(
            vertices,
            normalise_rows(integer_vectors),
            atol=unit_atol,
            rtol=0.0,
        ),
        "integer-to-floating row correspondence failure",
    )
    _require(
        not has_near_duplicate_rows(vertices, atol=duplicate_atol),
        "duplicate oriented direction",
    )

    vector_set = {tuple(row) for row in integer_vectors.tolist()}
    _require(
        all(tuple(-int(value) for value in row) in vector_set for row in vector_set),
        "missing antipodal integer vector",
    )
    antipodal_pairs = antipodal_pair_count(vertices, atol=antipodal_atol)
    _require(
        antipodal_pairs == vertex_count // 2,
        "incomplete or ambiguous antipodal pairing",
    )

    _validate_canonical_edges(edges, vertex_count=vertex_count)
    _require(connected(vertex_count, edges), "graph is disconnected")

    _require(
        len(graph.directed_neighbours) == vertex_count,
        "wrong directed-neighbour row count",
    )
    _require(
        graph.threshold_angles.shape == (vertex_count,),
        "wrong threshold-angle shape",
    )

    all_indices = np.arange(vertex_count, dtype=np.int64)
    for source, selected_tuple in enumerate(graph.directed_neighbours):
        selected = set(selected_tuple)
        _require(source not in selected, "directed self-neighbour")
        _require(len(selected) >= graph.nominal_k, "fewer than nominal k neighbours")

        mask = all_indices != source
        candidates = all_indices[mask]
        angles = np.arccos(
            np.clip(vertices[candidates] @ vertices[source], -1.0, 1.0)
        )
        threshold = float(graph.threshold_angles[source])
        expected_selected = {
            int(value)
            for value in candidates[angles <= threshold + tie_atol]
        }
        _require(
            selected == expected_selected,
            "directed selection is not tie-complete",
        )

    expected_edges = canonical_edges_from_neighbours(graph.directed_neighbours)
    _require(
        np.array_equal(edges, expected_edges),
        "undirected graph is not the directed-selection union",
    )

    degree_values = degrees(vertex_count, edges)
    _require(
        np.all(degree_values >= graph.nominal_k),
        "degree below nominal k",
    )

    directed_counts = np.asarray(
        [len(row) for row in graph.directed_neighbours],
        dtype=np.int64,
    )
    _require(
        np.all(degree_values >= directed_counts),
        "symmetrisation removed a directed neighbour",
    )

    if expected_point_count is not None:
        _require(
            vertex_count == expected_point_count,
            "unexpected primitive point count",
        )

    edge_angles = angular_edge_lengths(vertices, edges)
    return {
        "antipodal_pair_count": antipodal_pairs,
        "connected": True,
        "degree_histogram": degree_histogram(vertex_count, edges),
        "directed_selection_count_maximum": int(np.max(directed_counts)),
        "directed_selection_count_minimum": int(np.min(directed_counts)),
        "edge_count": len(edges),
        "maximum_degree": int(np.max(degree_values)),
        "maximum_edge_angle": float(np.max(edge_angles)),
        "minimum_bits": minimum_bits(vertex_count),
        "minimum_degree": int(np.min(degree_values)),
        "minimum_edge_angle": float(np.min(edge_angles)),
        "nominal_k": graph.nominal_k,
        "q": graph.q,
        "symmetrisation_degree_gain_total": int(
            np.sum(degree_values - directed_counts)
        ),
        "tie_completion_extra_selection_total": int(
            np.sum(directed_counts - graph.nominal_k)
        ),
        "threshold_angle_maximum": float(np.max(graph.threshold_angles)),
        "threshold_angle_minimum": float(np.min(graph.threshold_angles)),
        "vertex_count": vertex_count,
    }

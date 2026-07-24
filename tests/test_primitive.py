from __future__ import annotations

from math import gcd

import numpy as np
import pytest

from sphere_encoding.graphs import (
    build_primitive_direction_graph,
    generate_primitive_integer_vectors,
    tie_complete_directed_neighbours,
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

EXPECTED_COUNTS = {2: 98, 3: 290, 4: 578}


@pytest.mark.parametrize("q", [2, 3, 4])
def test_primitive_integer_vector_counts_and_order(q: int) -> None:
    vectors = generate_primitive_integer_vectors(q)

    assert len(vectors) == EXPECTED_COUNTS[q]
    rows = [tuple(row) for row in vectors.tolist()]
    assert rows == sorted(rows)
    assert np.all(np.any(vectors != 0, axis=1))
    assert np.all(np.abs(vectors) <= q)

    vector_set = {tuple(row) for row in vectors.tolist()}
    for row in vectors:
        x, y, z = (abs(int(value)) for value in row)
        assert gcd(gcd(x, y), z) == 1
        assert tuple(-int(value) for value in row) in vector_set


@pytest.mark.parametrize("q", [2, 3, 4])
@pytest.mark.parametrize("nominal_k", [4, 6, 8])
def test_all_frozen_primitive_graphs_validate(
    q: int,
    nominal_k: int,
) -> None:
    graph = build_primitive_direction_graph(
        q,
        nominal_k,
        angular_tie_atol_radians=1e-12,
    )

    diagnostics = validate_primitive_graph(
        graph,
        tolerances=TOLERANCES,
        expected_point_count=EXPECTED_COUNTS[q],
    )

    assert diagnostics["connected"] is True
    assert diagnostics["minimum_degree"] >= nominal_k
    assert diagnostics["antipodal_pair_count"] == EXPECTED_COUNTS[q] // 2


def test_primitive_graph_generation_is_deterministic() -> None:
    first = build_primitive_direction_graph(
        3,
        6,
        angular_tie_atol_radians=1e-12,
    )
    second = build_primitive_direction_graph(
        3,
        6,
        angular_tie_atol_radians=1e-12,
    )

    assert np.array_equal(first.integer_vectors, second.integer_vectors)
    assert np.array_equal(first.vertices, second.vertices)
    assert np.array_equal(first.edges, second.edges)
    assert first.directed_neighbours == second.directed_neighbours
    assert np.array_equal(first.threshold_angles, second.threshold_angles)


def test_tie_complete_rule_includes_entire_distance_shell() -> None:
    vertices = np.asarray(
        [
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, -1.0],
        ],
        dtype=np.float64,
    )

    neighbours, thresholds = tie_complete_directed_neighbours(
        vertices,
        nominal_k=2,
        angular_tie_atol_radians=1e-12,
    )

    assert neighbours[0] == (1, 2, 3, 4)
    assert thresholds[0] == pytest.approx(np.pi / 2.0)


def test_primitive_generation_rejects_non_positive_q() -> None:
    with pytest.raises(ValueError, match="positive"):
        generate_primitive_integer_vectors(0)

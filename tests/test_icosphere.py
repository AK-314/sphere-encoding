from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.graphs import generate_icosphere, validate_icosphere

TOLERANCES = {
    "angular_tie_atol_radians": 1e-12,
    "antipodal_atol": 1e-12,
    "duplicate_vertex_atol": 1e-12,
    "edge_length_class_atol_radians": 1e-12,
    "face_orientation_atol": 1e-15,
    "unit_norm_atol": 1e-12,
}

EXPECTED = {
    0: {
        "edges": 30,
        "faces": 20,
        "minimum_bits": 4,
        "subdivision_level": 0,
        "vertices": 12,
    },
    1: {
        "edges": 120,
        "faces": 80,
        "minimum_bits": 6,
        "subdivision_level": 1,
        "vertices": 42,
    },
    2: {
        "edges": 480,
        "faces": 320,
        "minimum_bits": 8,
        "subdivision_level": 2,
        "vertices": 162,
    },
    3: {
        "edges": 1920,
        "faces": 1280,
        "minimum_bits": 10,
        "subdivision_level": 3,
        "vertices": 642,
    },
}


@pytest.mark.parametrize("level", [0, 1, 2, 3])
def test_icosphere_exact_counts_and_full_validation(level: int) -> None:
    mesh = generate_icosphere(level)

    diagnostics = validate_icosphere(
        mesh,
        tolerances=TOLERANCES,
        expected=EXPECTED[level],
    )

    assert diagnostics["connected"] is True
    assert diagnostics["topology_checks"] == {
        "edge_incidence_two": True,
        "euler_characteristic_two": True,
        "outward_faces": True,
    }
    assert diagnostics["antipodal_pair_count"] == len(mesh.vertices) // 2


@pytest.mark.parametrize("level", [0, 1, 2, 3])
def test_icosphere_generation_is_byte_stable_in_memory(level: int) -> None:
    first = generate_icosphere(level)
    second = generate_icosphere(level)

    assert np.array_equal(first.vertices, second.vertices)
    assert np.array_equal(first.edges, second.edges)
    assert np.array_equal(first.faces, second.faces)


def test_first_subdivision_reuses_all_shared_midpoints() -> None:
    level_zero = generate_icosphere(0)
    level_one = generate_icosphere(1)

    assert len(level_one.vertices) - len(level_zero.vertices) == len(
        level_zero.edges
    )
    assert len(level_one.vertices) == 42


def test_icosphere_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        generate_icosphere(-1)

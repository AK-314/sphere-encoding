from __future__ import annotations

import hashlib

import numpy as np
import pytest
from ortools.sat.python import cp_model

from sphere_encoding.exact.model import (
    build_exact_feasibility_model,
    canonicalise_hint_codes,
    deterministic_odd_cycle,
    model_proto_bytes,
    structural_lower_bound,
)

TRIANGLE = np.array(
    [
        [0, 1],
        [0, 2],
        [1, 2],
    ],
    dtype=np.int64,
)

PATH_THREE = np.array(
    [
        [0, 1],
        [1, 2],
    ],
    dtype=np.int64,
)


def solve_status(model: cp_model.CpModel) -> int:
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.cp_model_presolve = True
    return solver.Solve(model)


def extracted_codes(
    built,
    solver: cp_model.CpSolver,
) -> np.ndarray:
    return np.asarray(
        [
            [
                solver.Value(variable)
                for variable in vertex_variables
            ]
            for vertex_variables in built.bit_variables
        ],
        dtype=np.uint8,
    )


def test_triangle_has_deterministic_odd_cycle_and_lower_bound_two() -> None:
    first = deterministic_odd_cycle(3, TRIANGLE)
    second = deterministic_odd_cycle(3, TRIANGLE)

    assert first == second == (1, 0, 2)

    evidence = structural_lower_bound(3, TRIANGLE)
    assert evidence.lower_bound == 2
    assert evidence.bipartite is False
    assert evidence.odd_cycle == (1, 0, 2)


def test_path_has_only_distinctness_lower_bound() -> None:
    assert deterministic_odd_cycle(3, PATH_THREE) is None

    evidence = structural_lower_bound(3, PATH_THREE)
    assert evidence.lower_bound == 1
    assert evidence.bipartite is True
    assert evidence.odd_cycle is None


def test_edgeless_graph_has_zero_structural_lower_bound() -> None:
    evidence = structural_lower_bound(
        3,
        np.empty((0, 2), dtype=np.int64),
    )

    assert evidence.lower_bound == 0
    assert evidence.bipartite is True
    assert evidence.odd_cycle is None


def test_triangle_tiny_optimum_is_two() -> None:
    target_one = build_exact_feasibility_model(
        vertex_count=3,
        edges=TRIANGLE,
        code_length=2,
        target_r=1,
    )
    target_two = build_exact_feasibility_model(
        vertex_count=3,
        edges=TRIANGLE,
        code_length=2,
        target_r=2,
    )

    assert solve_status(target_one.model) == cp_model.INFEASIBLE
    assert solve_status(target_two.model) in {
        cp_model.FEASIBLE,
        cp_model.OPTIMAL,
    }


def test_capacity_infeasibility_is_enforced_by_all_different() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=np.empty((0, 2), dtype=np.int64),
        code_length=1,
        target_r=0,
    )

    assert solve_status(built.model) == cp_model.INFEASIBLE


@pytest.mark.parametrize("target_r", [1, 2])
def test_symmetry_breaking_preserves_triangle_feasibility(
    target_r: int,
) -> None:
    with_symmetry = build_exact_feasibility_model(
        vertex_count=3,
        edges=TRIANGLE,
        code_length=2,
        target_r=target_r,
        symmetry_breaking=True,
    )
    without_symmetry = build_exact_feasibility_model(
        vertex_count=3,
        edges=TRIANGLE,
        code_length=2,
        target_r=target_r,
        symmetry_breaking=False,
    )

    assert solve_status(with_symmetry.model) == solve_status(
        without_symmetry.model
    )


def test_model_serialisation_and_hash_are_deterministic() -> None:
    first = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )
    second = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )

    first_bytes = model_proto_bytes(first.model)
    second_bytes = model_proto_bytes(second.model)

    assert first_bytes == second_bytes
    assert first.model_sha256 == second.model_sha256
    assert first.model_sha256 == hashlib.sha256(first_bytes).hexdigest()
    assert first.variable_count == second.variable_count
    assert first.constraint_count == second.constraint_count
    assert first.variable_count > 0
    assert first.constraint_count > 0
    assert first.first_neighbour == 1


def test_exact_xor_constraints_match_extracted_solution() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0

    status = solver.Solve(built.model)
    assert status in {cp_model.FEASIBLE, cp_model.OPTIMAL}

    codes = extracted_codes(built, solver)
    assert len({tuple(row) for row in codes.tolist()}) == 3

    distances = np.count_nonzero(
        codes[PATH_THREE[:, 0]] != codes[PATH_THREE[:, 1]],
        axis=1,
    )
    assert distances.tolist() == [
        sum(
            solver.Value(variable)
            for variable in xor_row
        )
        for xor_row in built.xor_variables
    ]
    assert int(np.max(distances)) <= 1
    assert codes[0].tolist() == [0, 0]
    assert codes[1].tolist() in ([1, 0],)


def test_target_feasible_hint_is_canonicalised_and_added() -> None:
    hint = np.array(
        [
            [1, 0],
            [0, 0],
            [0, 1],
        ],
        dtype=np.uint8,
    )

    canonical = canonicalise_hint_codes(
        hint,
        edges=PATH_THREE,
        target_r=1,
    )

    assert canonical.tolist() == [
        [0, 0],
        [1, 0],
        [1, 1],
    ]

    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
        hint_codes=hint,
    )

    proto = built.model.Proto()
    assert len(proto.solution_hint.vars) == 9
    assert len(proto.solution_hint.values) == 9
    assert solve_status(built.model) in {
        cp_model.FEASIBLE,
        cp_model.OPTIMAL,
    }


@pytest.mark.parametrize(
    ("hint", "message"),
    [
        (
            np.array(
                [[0, 0], [0, 0], [1, 0]],
                dtype=np.uint8,
            ),
            "injective",
        ),
        (
            np.array(
                [[0, 0], [2, 0], [1, 0]],
                dtype=np.int64,
            ),
            "binary",
        ),
        (
            np.array(
                [[0, 0], [1, 1], [0, 1]],
                dtype=np.uint8,
            ),
            "violates",
        ),
    ],
)
def test_corrupted_or_target_infeasible_hint_is_rejected(
    hint: np.ndarray,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        canonicalise_hint_codes(
            hint,
            edges=PATH_THREE,
            target_r=1,
        )


@pytest.mark.parametrize(
    ("kwargs", "exception", "message"),
    [
        (
            {
                "vertex_count": 0,
                "edges": [],
                "code_length": 1,
                "target_r": 0,
            },
            ValueError,
            "positive",
        ),
        (
            {
                "vertex_count": 2,
                "edges": [[1, 0]],
                "code_length": 1,
                "target_r": 1,
            },
            ValueError,
            "u < v",
        ),
        (
            {
                "vertex_count": 2,
                "edges": [[0, 1], [0, 1]],
                "code_length": 1,
                "target_r": 1,
            },
            ValueError,
            "duplicates",
        ),
        (
            {
                "vertex_count": 2,
                "edges": [[0, 1]],
                "code_length": 1,
                "target_r": 2,
            },
            ValueError,
            "between zero and code length",
        ),
    ],
)
def test_invalid_model_inputs_are_rejected(
    kwargs,
    exception,
    message: str,
) -> None:
    with pytest.raises(exception, match=message):
        build_exact_feasibility_model(**kwargs)

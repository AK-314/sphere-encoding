from __future__ import annotations

import numpy as np
import pytest
from ortools.sat.python import cp_model

from sphere_encoding.exact.model import build_exact_feasibility_model
from sphere_encoding.exact.solver import (
    ExactSolverStatus,
    interpret_solver_status,
    recompute_edge_hamming,
    solve_exact_feasibility_model,
    validate_exact_witness,
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


@pytest.mark.parametrize(
    (
        "raw_status",
        "expected",
        "has_witness",
        "certifies_infeasibility",
        "resolves_threshold",
        "implementation_failure",
    ),
    [
        (
            cp_model.OPTIMAL,
            ExactSolverStatus.OPTIMAL,
            True,
            False,
            True,
            False,
        ),
        (
            cp_model.FEASIBLE,
            ExactSolverStatus.FEASIBLE,
            True,
            False,
            True,
            False,
        ),
        (
            cp_model.INFEASIBLE,
            ExactSolverStatus.INFEASIBLE,
            False,
            True,
            True,
            False,
        ),
        (
            cp_model.MODEL_INVALID,
            ExactSolverStatus.MODEL_INVALID,
            False,
            False,
            False,
            True,
        ),
        (
            cp_model.UNKNOWN,
            ExactSolverStatus.UNKNOWN,
            False,
            False,
            False,
            False,
        ),
    ],
)
def test_status_interpretation(
    raw_status,
    expected,
    has_witness: bool,
    certifies_infeasibility: bool,
    resolves_threshold: bool,
    implementation_failure: bool,
) -> None:
    interpretation = interpret_solver_status(int(raw_status))

    assert interpretation.status is expected
    assert interpretation.has_feasible_witness is has_witness
    assert (
        interpretation.certifies_infeasibility
        is certifies_infeasibility
    )
    assert interpretation.resolves_threshold is resolves_threshold
    assert (
        interpretation.implementation_failure
        is implementation_failure
    )


def test_unknown_status_code_is_rejected() -> None:
    with pytest.raises(ValueError, match="unrecognised"):
        interpret_solver_status(999999)


def test_feasible_path_witness_is_extracted_and_validated() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )

    result = solve_exact_feasibility_model(
        built,
        max_time_seconds=5.0,
        log_search_progress=False,
    )

    assert result.status is ExactSolverStatus.OPTIMAL
    assert result.has_feasible_witness is True
    assert result.certifies_infeasibility is False
    assert result.resolves_threshold is True
    assert result.codebook is not None
    assert result.codebook.flags.writeable is False
    assert result.validation is not None
    assert result.validation.unique_codeword_count == 3
    assert result.validation.maximum_edge_hamming_distance == 1
    assert result.validation.edge_hamming_histogram == (0, 2, 0)
    assert result.validation.codebook_sha256
    assert result.model_sha256 == built.model_sha256
    assert result.wall_time_seconds >= 0.0
    assert result.user_time_seconds >= 0.0
    assert result.conflict_count >= 0
    assert result.branch_count >= 0
    assert result.response_stats
    assert result.solver_log == ""


def test_infeasible_triangle_target_certifies_lower_bound() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=TRIANGLE,
        code_length=2,
        target_r=1,
    )

    result = solve_exact_feasibility_model(
        built,
        max_time_seconds=5.0,
        log_search_progress=False,
    )

    assert result.status is ExactSolverStatus.INFEASIBLE
    assert result.has_feasible_witness is False
    assert result.certifies_infeasibility is True
    assert result.resolves_threshold is True
    assert result.codebook is None
    assert result.validation is None


def test_zero_time_limit_is_unknown_and_proves_nothing() -> None:
    built = build_exact_feasibility_model(
        vertex_count=80,
        edges=np.empty((0, 2), dtype=np.int64),
        code_length=7,
        target_r=0,
    )

    result = solve_exact_feasibility_model(
        built,
        max_time_seconds=0.0,
        log_search_progress=False,
    )

    assert result.status is ExactSolverStatus.UNKNOWN
    assert result.has_feasible_witness is False
    assert result.certifies_infeasibility is False
    assert result.resolves_threshold is False
    assert result.implementation_failure is False
    assert result.codebook is None
    assert result.validation is None


def test_edge_hamming_recomputation() -> None:
    codes = np.array(
        [
            [0, 0, 0],
            [1, 0, 0],
            [1, 1, 0],
        ],
        dtype=np.uint8,
    )

    distances = recompute_edge_hamming(codes, PATH_THREE)
    assert distances.tolist() == [1, 1]


def test_independent_validation_rejects_duplicate_codeword() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )
    corrupted = np.array(
        [
            [0, 0],
            [1, 0],
            [1, 0],
        ],
        dtype=np.uint8,
    )

    with pytest.raises(ValueError, match="injective"):
        validate_exact_witness(corrupted, built)


def test_independent_validation_rejects_non_binary_value() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )
    corrupted = np.array(
        [
            [0, 0],
            [1, 0],
            [1, 2],
        ],
        dtype=np.int64,
    )

    with pytest.raises(ValueError, match="non-binary"):
        validate_exact_witness(corrupted, built)


def test_independent_validation_rejects_wrong_shape() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )

    with pytest.raises(ValueError, match="shape"):
        validate_exact_witness(
            np.zeros((3, 3), dtype=np.uint8),
            built,
        )


def test_independent_validation_rejects_target_violation() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )
    corrupted = np.array(
        [
            [0, 0],
            [1, 1],
            [1, 0],
        ],
        dtype=np.uint8,
    )

    with pytest.raises(ValueError, match="edge-Hamming target"):
        validate_exact_witness(corrupted, built)


def test_independent_validation_rejects_anchor_violation() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )
    corrupted = np.array(
        [
            [1, 0],
            [0, 0],
            [0, 1],
        ],
        dtype=np.uint8,
    )

    with pytest.raises(ValueError, match="anchor-code"):
        validate_exact_witness(corrupted, built)


def test_independent_validation_rejects_first_neighbour_violation() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=3,
        target_r=2,
    )
    corrupted = np.array(
        [
            [0, 0, 0],
            [0, 1, 0],
            [0, 1, 1],
        ],
        dtype=np.uint8,
    )

    with pytest.raises(ValueError, match="first-neighbour"):
        validate_exact_witness(corrupted, built)


@pytest.mark.parametrize(
    ("kwargs", "exception", "message"),
    [
        (
            {"max_time_seconds": -1.0},
            ValueError,
            "non-negative",
        ),
        (
            {
                "max_time_seconds": 1.0,
                "num_search_workers": 2,
            },
            ValueError,
            "one search worker",
        ),
        (
            {
                "max_time_seconds": 1.0,
                "random_seed": 1,
            },
            ValueError,
            "seed zero",
        ),
        (
            {
                "max_time_seconds": float("inf"),
            },
            ValueError,
            "finite",
        ),
    ],
)
def test_invalid_solver_settings_are_rejected(
    kwargs,
    exception,
    message: str,
) -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )

    with pytest.raises(exception, match=message):
        solve_exact_feasibility_model(
            built,
            log_search_progress=False,
            **kwargs,
        )


def test_single_worker_repeated_solve_is_reproducible() -> None:
    built = build_exact_feasibility_model(
        vertex_count=3,
        edges=PATH_THREE,
        code_length=2,
        target_r=1,
    )

    first = solve_exact_feasibility_model(
        built,
        max_time_seconds=5.0,
        log_search_progress=False,
    )
    second = solve_exact_feasibility_model(
        built,
        max_time_seconds=5.0,
        log_search_progress=False,
    )

    assert first.status is second.status
    assert first.validation is not None
    assert second.validation is not None
    assert (
        first.validation.codebook_sha256
        == second.validation.codebook_sha256
    )
    assert np.array_equal(first.codebook, second.codebook)


def test_witness_validation_computes_frozen_global_diagnostics() -> None:
    edges = np.array(
        [[0, 1], [0, 3], [1, 2], [2, 3]],
        dtype=np.int64,
    )
    built = build_exact_feasibility_model(
        vertex_count=4,
        edges=edges,
        code_length=2,
        target_r=1,
    )
    codes = np.array(
        [[0, 0], [1, 0], [1, 1], [0, 1]],
        dtype=np.uint8,
    )
    vertices = np.array(
        [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]],
        dtype=np.float64,
    )

    validation = validate_exact_witness(
        codes,
        built,
        vertices=vertices,
        far_threshold=0.75,
        antipodal_atol=1e-12,
        expected_antipodal_count=2,
    )

    assert validation.global_diagnostics is not None
    assert validation.global_diagnostics["global"][
        "unordered_pair_count"
    ] == 6
    assert validation.global_diagnostics["far_pairs"][
        "far_pair_count"
    ] == 2
    assert validation.global_diagnostics["antipodal_pairs"][
        "antipodal_pair_count"
    ] == 2

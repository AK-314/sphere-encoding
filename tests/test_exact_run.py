from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from sphere_encoding.exact.plan import (
    BaselineChoice,
    InstancePlan,
    TargetPlan,
)
from sphere_encoding.exact.run import (
    InstanceClassification,
    TargetExecution,
    classify_instance_executions,
    execute_instance_plan,
)
from sphere_encoding.exact.solver import ExactSolverStatus


def instance_plan() -> InstancePlan:
    baseline = BaselineChoice(
        graph_id="icosphere_l0",
        requested_code_length=4,
        encoding_id="canonical_index_binary",
        native_code_length=4,
        padding_bits=0,
        l_max=4,
        minimum_lmax_tie_count=1,
        source_codes_path="baseline.npy",
        source_codes_sha256="a" * 64,
        selected_codebook_sha256="b" * 64,
        vertex_count=12,
        unique_codeword_count=12,
    )
    return InstancePlan(
        execution_order=1,
        instance_class="test",
        graph_id="icosphere_l0",
        code_length=4,
        vertex_count=12,
        edge_count=30,
        structural_lower_bound=2,
        odd_cycle=(1, 0, 5),
        baseline=baseline,
        total_budget_seconds=300,
        per_target_budget_seconds=150,
        targets=(
            TargetPlan(1, 2, 150, False),
            TargetPlan(2, 3, 150, False),
        ),
    )


def execution(
    order: int,
    target_r: int,
    status: ExactSolverStatus,
    *,
    witness_l_max: int | None = None,
) -> TargetExecution:
    return TargetExecution(
        target_order_within_instance=order,
        target_r=target_r,
        budget_seconds=150,
        status=status,
        model_sha256="c" * 64,
        variable_count=1,
        constraint_count=1,
        wall_time_seconds=0.1,
        user_time_seconds=0.1,
        conflict_count=0,
        branch_count=0,
        response_stats="stats",
        has_feasible_witness=status in {
            ExactSolverStatus.OPTIMAL,
            ExactSolverStatus.FEASIBLE,
        },
        certifies_infeasibility=(
            status is ExactSolverStatus.INFEASIBLE
        ),
        witness_l_max=witness_l_max,
        witness_codebook_sha256=(
            "d" * 64 if witness_l_max is not None else None
        ),
    )


def test_all_infeasible_targets_establish_baseline_optimum() -> None:
    result = classify_instance_executions(
        instance_plan(),
        (
            execution(1, 2, ExactSolverStatus.INFEASIBLE),
            execution(2, 3, ExactSolverStatus.INFEASIBLE),
        ),
    )

    assert result.classification is InstanceClassification.EXACT
    assert (result.final_lower_bound, result.final_upper_bound) == (4, 4)


def test_infeasible_then_feasible_establishes_exact_optimum() -> None:
    result = classify_instance_executions(
        instance_plan(),
        (
            execution(1, 2, ExactSolverStatus.INFEASIBLE),
            execution(
                2,
                3,
                ExactSolverStatus.OPTIMAL,
                witness_l_max=3,
            ),
        ),
    )

    assert result.classification is InstanceClassification.EXACT
    assert (result.final_lower_bound, result.final_upper_bound) == (3, 3)


def test_unknown_proves_nothing_and_yields_bounded_result() -> None:
    result = classify_instance_executions(
        instance_plan(),
        (
            execution(1, 2, ExactSolverStatus.UNKNOWN),
            execution(
                2,
                3,
                ExactSolverStatus.FEASIBLE,
                witness_l_max=3,
            ),
        ),
    )

    assert result.classification is InstanceClassification.BOUNDED
    assert (result.final_lower_bound, result.final_upper_bound) == (2, 3)
    assert result.unknown_target_count == 1


def test_no_execution_retains_baseline_upper_bound_only() -> None:
    result = classify_instance_executions(instance_plan(), ())

    assert result.classification is InstanceClassification.UPPER_BOUND_ONLY
    assert (result.final_lower_bound, result.final_upper_bound) == (2, 4)


def test_model_invalid_is_failure() -> None:
    result = classify_instance_executions(
        instance_plan(),
        (execution(1, 2, ExactSolverStatus.MODEL_INVALID),),
    )

    assert result.classification is InstanceClassification.FAILURE


def test_out_of_order_execution_is_rejected() -> None:
    wrong = execution(1, 3, ExactSolverStatus.UNKNOWN)

    try:
        classify_instance_executions(instance_plan(), (wrong,))
    except ValueError as error:
        assert "frozen order" in str(error)
    else:
        raise AssertionError("out-of-order execution was accepted")


def test_tiny_solver_instance_executes_and_stops_at_exact_result(
    tmp_path: Path,
) -> None:
    planned = instance_plan()
    graph_root = tmp_path / "results" / "raw" / "synthetic" / "triangle"
    graph_root.mkdir(parents=True)
    np.save(
        graph_root / "edges.npy",
        np.array([[0, 1], [0, 2], [1, 2]], dtype=np.int64),
        allow_pickle=False,
    )

    tiny = replace(
        planned,
        graph_id="triangle",
        vertex_count=3,
        edge_count=3,
        code_length=2,
        structural_lower_bound=1,
        odd_cycle=None,
        baseline=replace(
            planned.baseline,
            graph_id="triangle",
            requested_code_length=2,
            native_code_length=2,
            l_max=2,
            vertex_count=3,
            unique_codeword_count=3,
        ),
        total_budget_seconds=5,
        per_target_budget_seconds=5,
        targets=(TargetPlan(1, 1, 5, False),),
    )

    result = execute_instance_plan(
        tmp_path,
        stage2_run_id="synthetic",
        instance=tiny,
        log_search_progress=False,
    )

    assert result.targets_attempted == 1
    assert result.classification is InstanceClassification.EXACT
    assert (result.final_lower_bound, result.final_upper_bound) == (2, 2)
    assert result.executions[0].model_sha256
    assert result.executions[0].variable_count > 0
    assert result.executions[0].constraint_count > 0

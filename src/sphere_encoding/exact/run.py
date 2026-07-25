"""Ordered Stage 4 target execution and evidence-based classification."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np

from sphere_encoding.exact.model import build_exact_feasibility_model
from sphere_encoding.exact.plan import InstancePlan
from sphere_encoding.exact.solver import (
    ExactSolveResult,
    ExactSolverStatus,
    solve_exact_feasibility_model,
)


class InstanceClassification(StrEnum):
    """Frozen Stage 4 instance-level result classes."""

    EXACT = "exact"
    BOUNDED = "bounded"
    UPPER_BOUND_ONLY = "upper_bound_only"
    FAILURE = "failure"


@dataclass(frozen=True)
class TargetExecution:
    """Preserved evidence for one attempted threshold."""

    target_order_within_instance: int
    target_r: int
    budget_seconds: int
    status: ExactSolverStatus
    model_sha256: str
    variable_count: int
    constraint_count: int
    wall_time_seconds: float
    user_time_seconds: float
    conflict_count: int
    branch_count: int
    response_stats: str
    solver_log: str
    model_bytes: bytes
    witness_codebook: np.ndarray | None
    has_feasible_witness: bool
    certifies_infeasibility: bool
    witness_l_max: int | None
    witness_codebook_sha256: str | None
    global_diagnostics: dict[str, Any] | None


@dataclass(frozen=True)
class InstanceExecution:
    """Final bounds and classification for one frozen instance."""

    execution_order: int
    graph_id: str
    code_length: int
    structural_lower_bound: int
    baseline_upper_bound: int
    final_lower_bound: int
    final_upper_bound: int
    classification: InstanceClassification
    targets_planned: int
    targets_attempted: int
    unknown_target_count: int
    executions: tuple[TargetExecution, ...]


SolveFunction = Callable[..., ExactSolveResult]


def classify_instance_executions(
    instance: InstancePlan,
    executions: Sequence[TargetExecution],
) -> InstanceExecution:
    """Derive conservative final bounds from ordered target evidence."""

    ordered = tuple(executions)
    if len(ordered) > len(instance.targets):
        raise ValueError("more target executions than frozen targets")

    expected = instance.targets[: len(ordered)]
    for target, execution in zip(expected, ordered, strict=True):
        if (
            execution.target_order_within_instance
            != target.target_order_within_instance
            or execution.target_r != target.target_r
            or execution.budget_seconds != target.budget_seconds
        ):
            raise ValueError("target execution differs from frozen order")

    if any(
        execution.status is ExactSolverStatus.MODEL_INVALID
        for execution in ordered
    ):
        classification = InstanceClassification.FAILURE
    else:
        classification = InstanceClassification.UPPER_BOUND_ONLY

    lower_bound = instance.structural_lower_bound
    upper_bound = instance.baseline.l_max
    unknown_count = 0

    for execution in ordered:
        if execution.status is ExactSolverStatus.UNKNOWN:
            unknown_count += 1
        elif execution.certifies_infeasibility:
            if execution.target_r == lower_bound:
                lower_bound += 1
        elif execution.has_feasible_witness:
            if execution.witness_l_max is None:
                raise ValueError("feasible execution lacks witness evidence")
            if execution.witness_l_max > execution.target_r:
                raise ValueError("witness exceeds its target threshold")
            upper_bound = min(upper_bound, execution.witness_l_max)

    if classification is not InstanceClassification.FAILURE:
        if lower_bound == upper_bound:
            classification = InstanceClassification.EXACT
        elif unknown_count:
            classification = InstanceClassification.BOUNDED
        elif lower_bound > instance.structural_lower_bound:
            classification = InstanceClassification.BOUNDED
        else:
            classification = InstanceClassification.UPPER_BOUND_ONLY

    if lower_bound > upper_bound:
        raise ValueError("derived lower bound exceeds upper bound")

    return InstanceExecution(
        execution_order=instance.execution_order,
        graph_id=instance.graph_id,
        code_length=instance.code_length,
        structural_lower_bound=instance.structural_lower_bound,
        baseline_upper_bound=instance.baseline.l_max,
        final_lower_bound=lower_bound,
        final_upper_bound=upper_bound,
        classification=classification,
        targets_planned=len(instance.targets),
        targets_attempted=len(ordered),
        unknown_target_count=unknown_count,
        executions=ordered,
    )


def execute_instance_plan(
    repository_root: Path,
    *,
    stage2_run_id: str,
    instance: InstancePlan,
    solve_function: SolveFunction = solve_exact_feasibility_model,
    log_search_progress: bool = True,
) -> InstanceExecution:
    """Execute one instance in frozen ascending-target order."""

    graph_root = (
        repository_root
        / "results"
        / "raw"
        / stage2_run_id
        / instance.graph_id
    )
    edges_path = graph_root / "edges.npy"
    if not edges_path.is_file():
        raise FileNotFoundError(f"missing graph edges: {edges_path}")

    edges = np.load(edges_path, allow_pickle=False)
    if edges.shape != (instance.edge_count, 2):
        raise ValueError("graph edges differ from frozen instance plan")

    vertices_path = graph_root / "vertices.npy"
    metadata_path = graph_root / "metadata.json"
    stage3_config_path = repository_root / "configs" / "stage3_baselines.json"
    diagnostic_kwargs: dict[str, Any] = {}
    if (
        vertices_path.is_file()
        and metadata_path.is_file()
        and stage3_config_path.is_file()
    ):
        import json

        from sphere_encoding.config import load_json_config

        vertices = np.load(vertices_path, allow_pickle=False)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        stage3_config = load_json_config(stage3_config_path)
        diagnostic_kwargs = {
            "antipodal_atol": stage3_config["antipodal_pairs"][
                "accepted_stage2_atol"
            ],
            "expected_antipodal_count": metadata["diagnostics"][
                "antipodal_pair_count"
            ],
            "far_threshold": stage3_config["far_pairs"]["threshold"],
            "vertices": vertices,
        }

    executions: list[TargetExecution] = []
    for target in instance.targets:
        built = build_exact_feasibility_model(
            vertex_count=instance.vertex_count,
            edges=edges,
            code_length=instance.code_length,
            target_r=target.target_r,
            symmetry_breaking=True,
        )
        result = solve_function(
            built,
            max_time_seconds=target.budget_seconds,
            num_search_workers=1,
            random_seed=0,
            cp_model_presolve=True,
            log_search_progress=log_search_progress,
            **diagnostic_kwargs,
        )

        validation = result.validation
        execution = TargetExecution(
            target_order_within_instance=(
                target.target_order_within_instance
            ),
            target_r=target.target_r,
            budget_seconds=target.budget_seconds,
            status=result.status,
            model_sha256=built.model_sha256,
            variable_count=built.variable_count,
            constraint_count=built.constraint_count,
            wall_time_seconds=result.wall_time_seconds,
            user_time_seconds=result.user_time_seconds,
            conflict_count=result.conflict_count,
            branch_count=result.branch_count,
            response_stats=result.response_stats,
            solver_log=result.solver_log,
            model_bytes=built.model_bytes,
            witness_codebook=result.codebook,
            has_feasible_witness=result.has_feasible_witness,
            certifies_infeasibility=result.certifies_infeasibility,
            witness_l_max=(
                validation.maximum_edge_hamming_distance
                if validation is not None
                else None
            ),
            witness_codebook_sha256=(
                validation.codebook_sha256
                if validation is not None
                else None
            ),
            global_diagnostics=(
                validation.global_diagnostics
                if validation is not None
                else None
            ),
        )
        executions.append(execution)

        partial = classify_instance_executions(instance, executions)
        if (
            partial.classification is InstanceClassification.EXACT
            or partial.classification is InstanceClassification.FAILURE
        ):
            break

    return classify_instance_executions(instance, executions)

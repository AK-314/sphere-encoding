from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from sphere_encoding.exact.artifacts import (
    write_instance_artifacts,
    write_stage4_tables,
)
from sphere_encoding.exact.run import (
    InstanceClassification,
    InstanceExecution,
    TargetExecution,
)
from sphere_encoding.exact.solver import ExactSolverStatus
from sphere_encoding.graphs.artifacts import npy_bytes


def target_execution(*, feasible: bool) -> TargetExecution:
    model_bytes = b"deterministic model"
    codebook = (
        np.array([[0, 0], [1, 0], [1, 1]], dtype=np.uint8)
        if feasible
        else None
    )
    return TargetExecution(
        target_order_within_instance=1,
        target_r=1,
        budget_seconds=5,
        status=(
            ExactSolverStatus.OPTIMAL
            if feasible
            else ExactSolverStatus.INFEASIBLE
        ),
        model_sha256=hashlib.sha256(model_bytes).hexdigest(),
        variable_count=10,
        constraint_count=8,
        wall_time_seconds=0.1,
        user_time_seconds=0.1,
        conflict_count=2,
        branch_count=3,
        response_stats="response stats\n",
        solver_log="solver log\n",
        model_bytes=model_bytes,
        witness_codebook=codebook,
        has_feasible_witness=feasible,
        certifies_infeasibility=not feasible,
        witness_l_max=1 if feasible else None,
        witness_codebook_sha256=(
            hashlib.sha256(npy_bytes(codebook)).hexdigest()
            if codebook is not None
            else None
        ),
    )


def instance_execution(*, feasible: bool) -> InstanceExecution:
    return InstanceExecution(
        execution_order=1,
        graph_id="triangle",
        code_length=2,
        structural_lower_bound=1,
        baseline_upper_bound=2,
        final_lower_bound=1 if feasible else 2,
        final_upper_bound=1 if feasible else 2,
        classification=InstanceClassification.EXACT,
        targets_planned=1,
        targets_attempted=1,
        unknown_target_count=0,
        executions=(target_execution(feasible=feasible),),
    )


@pytest.mark.parametrize("feasible", [False, True])
def test_instance_artifacts_preserve_complete_target_evidence(
    tmp_path: Path,
    feasible: bool,
) -> None:
    hashes = write_instance_artifacts(
        tmp_path,
        instance_execution(feasible=feasible),
    )
    instance_root = tmp_path / "triangle" / "m2"
    target_root = instance_root / "targets" / "r1"

    assert hashes
    assert (target_root / "model.pb").read_bytes() == (
        b"deterministic model"
    )
    assert (target_root / "response_stats.txt").read_text() == (
        "response stats\n"
    )
    assert (target_root / "solver.log").read_text() == "solver log\n"

    target = json.loads((target_root / "target.json").read_text())
    assert target["raw_status"] == (
        "OPTIMAL" if feasible else "INFEASIBLE"
    )
    assert target["certifies_infeasibility"] is (not feasible)
    assert target["has_feasible_witness"] is feasible
    assert (target_root / "codebook.npy").exists() is feasible

    instance = json.loads((instance_root / "instance.json").read_text())
    assert instance["classification"] == "exact"
    assert instance["targets_attempted"] == 1


def test_corrupted_preserved_model_is_rejected_without_partial_output(
    tmp_path: Path,
) -> None:
    execution = instance_execution(feasible=False)
    corrupted_target = TargetExecution(
        **{
            **execution.executions[0].__dict__,
            "model_bytes": b"corrupted",
        }
    )
    corrupted = InstanceExecution(
        **{
            **execution.__dict__,
            "executions": (corrupted_target,),
        }
    )

    with pytest.raises(ValueError, match="model bytes"):
        write_instance_artifacts(tmp_path, corrupted)

    assert not (tmp_path / "triangle" / "m2").exists()


def test_existing_instance_destination_is_rejected(tmp_path: Path) -> None:
    write_instance_artifacts(
        tmp_path,
        instance_execution(feasible=False),
    )

    with pytest.raises(FileExistsError, match="destination exists"):
        write_instance_artifacts(
            tmp_path,
            instance_execution(feasible=False),
        )


def test_stage4_tables_have_frozen_schemas_and_content(
    tmp_path: Path,
) -> None:
    run_id = "stage4-test-run"
    exact = instance_execution(feasible=True)
    bounded = InstanceExecution(
        **{
            **instance_execution(feasible=False).__dict__,
            "execution_order": 2,
            "graph_id": "path",
            "classification": InstanceClassification.BOUNDED,
            "final_lower_bound": 1,
            "final_upper_bound": 2,
            "unknown_target_count": 1,
        }
    )

    hashes = write_stage4_tables(
        tmp_path,
        run_id=run_id,
        executions=(exact, bounded),
    )

    assert len(hashes) == 4
    target_rows = list(
        csv.DictReader(
            (tmp_path / f"{run_id}_target_results.csv").open(
                encoding="utf-8",
                newline="",
            )
        )
    )
    instance_rows = list(
        csv.DictReader(
            (tmp_path / f"{run_id}_instance_bounds.csv").open(
                encoding="utf-8",
                newline="",
            )
        )
    )
    exact_rows = list(
        csv.DictReader(
            (tmp_path / f"{run_id}_exact_optima.csv").open(
                encoding="utf-8",
                newline="",
            )
        )
    )
    gap_rows = list(
        csv.DictReader(
            (tmp_path / f"{run_id}_baseline_gaps.csv").open(
                encoding="utf-8",
                newline="",
            )
        )
    )

    assert len(target_rows) == 2
    assert [row["classification"] for row in instance_rows] == [
        "exact",
        "bounded",
    ]
    assert exact_rows == [
        {
            "execution_order": "1",
            "graph_id": "triangle",
            "code_length": "2",
            "exact_l_star_free": "1",
        }
    ]
    assert [row["baseline_gap_closed"] for row in gap_rows] == [
        "1",
        "0",
    ]

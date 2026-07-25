from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sphere_encoding.exact.artifacts import generate_stage4_artifacts
from sphere_encoding.exact.plan import (
    BaselineChoice,
    FrozenInputIdentity,
    InstancePlan,
    Stage4Plan,
    TargetPlan,
)
from sphere_encoding.exact.reproduce import (
    audit_stage4_package,
    reproduce_stage4_solver_results,
)
from sphere_encoding.exact.run import execute_instance_plan
from sphere_encoding.exact.solver import solve_exact_feasibility_model


def build_fixture(tmp_path: Path):
    stage2_run = "stage2-test"
    graph_root = (
        tmp_path / "results" / "raw" / stage2_run / "triangle"
    )
    graph_root.mkdir(parents=True)
    np.save(
        graph_root / "edges.npy",
        np.array([[0, 1], [0, 2], [1, 2]], dtype=np.int64),
        allow_pickle=False,
    )
    baseline = BaselineChoice(
        graph_id="triangle",
        requested_code_length=2,
        encoding_id="baseline",
        native_code_length=2,
        padding_bits=0,
        l_max=2,
        minimum_lmax_tie_count=1,
        source_codes_path="baseline.npy",
        source_codes_sha256="1" * 64,
        selected_codebook_sha256="2" * 64,
        vertex_count=3,
        unique_codeword_count=3,
    )
    instance = InstancePlan(
        execution_order=1,
        instance_class="test",
        graph_id="triangle",
        code_length=2,
        vertex_count=3,
        edge_count=3,
        structural_lower_bound=1,
        odd_cycle=(1, 0, 2),
        baseline=baseline,
        total_budget_seconds=5,
        per_target_budget_seconds=5,
        targets=(TargetPlan(1, 1, 5, False),),
    )
    identity = FrozenInputIdentity(
        stage_name="stage2",
        run_id=stage2_run,
        manifest_path="manifest.json",
        archive_path="archive.tar.gz",
        package_path=f"results/raw/{stage2_run}",
        configuration_sha256="3" * 64,
        package_tree_sha256="4" * 64,
        archive_sha256="5" * 64,
        table_set_sha256=None,
    )
    plan = Stage4Plan(
        stage=4,
        stage_name="Exact Free-Codebook Optimisation",
        configuration_path="config.json",
        configuration_sha256="6" * 64,
        input_identities=(identity,),
        instances=(instance,),
        instance_count=1,
        target_count=1,
        total_budget_seconds=5,
        hint_eligible_target_count=0,
        baseline_tie_instance_count=0,
        plan_sha256="7" * 64,
    )
    result = execute_instance_plan(
        tmp_path,
        stage2_run_id=stage2_run,
        instance=instance,
        log_search_progress=False,
    )
    package = tmp_path / "package"
    generate_stage4_artifacts(
        plan=plan,
        executions=(result,),
        package_root=package,
        table_root=tmp_path / "tables",
        archive_path=tmp_path / "archive.tar.gz",
        run_id="stage4-test",
    )
    return plan, package


def test_package_audit_regenerates_models_and_validates_evidence(
    tmp_path: Path,
) -> None:
    plan, package = build_fixture(tmp_path)

    audit = audit_stage4_package(
        tmp_path,
        plan=plan,
        package_root=package,
    )

    assert audit["instance_count"] == 1
    assert audit["model_count"] == 1
    assert audit["witness_count"] == 0


def test_package_audit_rejects_corrupted_model(tmp_path: Path) -> None:
    plan, package = build_fixture(tmp_path)
    model = package / "triangle" / "m2" / "targets" / "r1" / "model.pb"
    model.write_bytes(b"corrupted")

    with pytest.raises(ValueError, match="file hashes"):
        audit_stage4_package(
            tmp_path,
            plan=plan,
            package_root=package,
        )


def test_claim_bearing_solver_result_reproduces(tmp_path: Path) -> None:
    plan, package = build_fixture(tmp_path)

    result = reproduce_stage4_solver_results(
        tmp_path,
        plan=plan,
        package_root=package,
        solve_function=solve_exact_feasibility_model,
        log_search_progress=False,
    )

    assert result == {
        "instance_count": 1,
        "status_disagreement_count": 0,
    }


def test_infeasible_disagreement_is_reproduction_failure(
    tmp_path: Path,
) -> None:
    plan, package = build_fixture(tmp_path)

    def unknown_solver(built, **kwargs):
        kwargs["max_time_seconds"] = 0.0
        return solve_exact_feasibility_model(built, **kwargs)

    with pytest.raises(ValueError, match="INFEASIBLE"):
        reproduce_stage4_solver_results(
            tmp_path,
            plan=plan,
            package_root=package,
            solve_function=unknown_solver,
            log_search_progress=False,
        )

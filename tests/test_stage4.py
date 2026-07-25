from __future__ import annotations

from dataclasses import replace

import pytest

from sphere_encoding.exact.plan import FrozenInputIdentity, Stage4Plan
from sphere_encoding.exact.run import (
    InstanceClassification,
    InstanceExecution,
)
from sphere_encoding.stage4 import (
    build_stage4_manifest_payload,
    derive_stage4_run_id,
)


def test_stage4_run_identifier() -> None:
    assert derive_stage4_run_id("a" * 64, "b" * 40) == (
        "stage4-exact-free-codebook-aaaaaaaaaaaa-bbbbbbbbbbbb"
    )
    with pytest.raises(ValueError, match="configuration"):
        derive_stage4_run_id("short", "b" * 40)
    with pytest.raises(ValueError, match="commit"):
        derive_stage4_run_id("a" * 64, "short")


def execution() -> InstanceExecution:
    return InstanceExecution(
        execution_order=1,
        graph_id="triangle",
        code_length=2,
        structural_lower_bound=1,
        baseline_upper_bound=2,
        final_lower_bound=2,
        final_upper_bound=2,
        classification=InstanceClassification.EXACT,
        targets_planned=1,
        targets_attempted=1,
        unknown_target_count=0,
        executions=(),
    )


def plan() -> Stage4Plan:
    identity = FrozenInputIdentity(
        stage_name="stage2",
        run_id="stage2-test",
        manifest_path="manifests/stage2-test.json",
        archive_path="results/archives/stage2-test.tar.gz",
        package_path="results/raw/stage2-test",
        configuration_sha256="1" * 64,
        package_tree_sha256="2" * 64,
        archive_sha256="3" * 64,
        table_set_sha256=None,
    )
    return Stage4Plan(
        stage=4,
        stage_name="Exact Free-Codebook Optimisation",
        configuration_path="configs/stage4_exact.json",
        configuration_sha256="a" * 64,
        input_identities=(identity,),
        instances=(),
        instance_count=1,
        target_count=1,
        total_budget_seconds=5,
        hint_eligible_target_count=0,
        baseline_tie_instance_count=0,
        plan_sha256="b" * 64,
    )


def generated() -> dict[str, object]:
    return {
        "archive_member_count": 9,
        "archive_sha256": "c" * 64,
        "file_count": 5,
        "files": {"package_metadata.json": "d" * 64},
        "instance_count": 1,
        "package_tree_sha256": "e" * 64,
        "table_file_count": 4,
        "table_files": {"table.csv": "f" * 64},
        "table_set_sha256": "0" * 64,
        "target_count_attempted": 1,
    }


def test_stage4_manifest_payload_binds_all_identities() -> None:
    payload = build_stage4_manifest_payload(
        plan=plan(),
        executions=(execution(),),
        generated=generated(),
        implementation_commit="9" * 40,
        run_id="stage4-test",
        config_path="configs/stage4_exact.json",
        package_path="results/raw/stage4-test",
        archive_path="results/archives/stage4-test.tar.gz",
        manifest_path="manifests/stage4-test.json",
        table_paths={"target_results": "results/tables/target.csv"},
    )

    assert payload["plan_sha256"] == "b" * 64
    assert payload["implementation_commit"] == "9" * 40
    assert payload["classifications"] == {
        "exact": 1,
        "bounded": 0,
        "upper_bound_only": 0,
        "failure": 0,
    }
    assert payload["upstream_inputs"]["stage2"]["run_id"] == (
        "stage2-test"
    )
    assert payload["deterministic_outputs"]["tables"][
        "table_set_sha256"
    ] == ("0" * 64)


def test_manifest_rejects_count_disagreement() -> None:
    bad = replace(plan(), instance_count=2)
    with pytest.raises(ValueError, match="execution count"):
        build_stage4_manifest_payload(
            plan=bad,
            executions=(execution(),),
            generated=generated(),
            implementation_commit="9" * 40,
            run_id="stage4-test",
            config_path="config.json",
            package_path="raw",
            archive_path="archive",
            manifest_path="manifest",
            table_paths={},
        )

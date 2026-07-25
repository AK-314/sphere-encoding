from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from sphere_encoding.config import config_sha256, pretty_json_dumps
from sphere_encoding.exact.plan import (
    BaselineChoice,
    FrozenInputIdentity,
    InstancePlan,
    Stage4Plan,
)
from sphere_encoding.exact.run import (
    InstanceClassification,
    InstanceExecution,
)
from sphere_encoding.stage4 import (
    build_stage4_manifest_payload,
    derive_stage4_run_id,
    execute_stage4_plan,
    install_definitive_stage4_artifacts,
    install_prepared_stage4_artifacts,
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


def run_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def initialise_stage4_repository(repository: Path) -> tuple[dict, str]:
    repository.mkdir()
    run_git(repository, "init")
    run_git(repository, "config", "user.name", "Stage Four Test")
    run_git(
        repository,
        "config",
        "user.email",
        "stage4@example.invalid",
    )
    config = {
        "outputs": {
            "archive_directory": "results/archives",
            "baseline_gap_table_suffix": "_baseline_gaps.csv",
            "exact_table_suffix": "_exact_optima.csv",
            "instance_table_suffix": "_instance_bounds.csv",
            "manifest_directory": "manifests",
            "raw_directory": "results/raw",
            "table_directory": "results/tables",
            "target_table_suffix": "_target_results.csv",
        },
        "stage": 4,
        "stage_name": "Exact Free-Codebook Optimisation",
    }
    config_path = repository / "configs" / "stage4_exact.json"
    config_path.parent.mkdir()
    config_path.write_text(pretty_json_dumps(config), encoding="utf-8")
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "implementation")
    return config, run_git(repository, "rev-parse", "HEAD")


def prepared_plan(config: dict) -> tuple[Stage4Plan, InstanceExecution]:
    baseline = BaselineChoice(
        graph_id="empty",
        requested_code_length=1,
        encoding_id="baseline",
        native_code_length=1,
        padding_bits=0,
        l_max=0,
        minimum_lmax_tie_count=1,
        source_codes_path="baseline.npy",
        source_codes_sha256="1" * 64,
        selected_codebook_sha256="2" * 64,
        vertex_count=1,
        unique_codeword_count=1,
    )
    instance = InstancePlan(
        execution_order=1,
        instance_class="test",
        graph_id="empty",
        code_length=1,
        vertex_count=1,
        edge_count=0,
        structural_lower_bound=0,
        odd_cycle=None,
        baseline=baseline,
        total_budget_seconds=1,
        per_target_budget_seconds=1,
        targets=(),
    )
    result = InstanceExecution(
        execution_order=1,
        graph_id="empty",
        code_length=1,
        structural_lower_bound=0,
        baseline_upper_bound=0,
        final_lower_bound=0,
        final_upper_bound=0,
        classification=InstanceClassification.EXACT,
        targets_planned=0,
        targets_attempted=0,
        unknown_target_count=0,
        executions=(),
    )
    prepared = Stage4Plan(
        stage=4,
        stage_name=config["stage_name"],
        configuration_path="configs/stage4_exact.json",
        configuration_sha256=config_sha256(config),
        input_identities=(),
        instances=(instance,),
        instance_count=1,
        target_count=0,
        total_budget_seconds=1,
        hint_eligible_target_count=0,
        baseline_tie_instance_count=0,
        plan_sha256="3" * 64,
    )
    return prepared, result


def test_prepared_stage4_install_is_atomic_and_manifested(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    config, commit = initialise_stage4_repository(repository)
    prepared, result = prepared_plan(config)

    installed = install_prepared_stage4_artifacts(
        repository_path=repository,
        config_path="configs/stage4_exact.json",
        plan=prepared,
        executions=(result,),
    )

    expected_run = derive_stage4_run_id(config_sha256(config), commit)
    assert installed["run_id"] == expected_run
    assert installed["target_count_attempted"] == 0
    assert installed["package_file_count"] == 2
    assert (repository / installed["output_directory"]).is_dir()
    assert (repository / installed["archive_path"]).is_file()
    manifest_path = repository / installed["manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["stage"] == 4
    assert manifest["repository"]["commit"] == commit
    assert manifest["repository"]["clean"] is True
    assert manifest["payload"]["plan_sha256"] == "3" * 64
    assert manifest["payload"]["classifications"]["exact"] == 1
    assert len(installed["table_paths"]) == 4


def test_prepared_install_rejects_dirty_repository(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    config, _ = initialise_stage4_repository(repository)
    prepared, result = prepared_plan(config)
    (repository / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(ValueError, match="clean"):
        install_prepared_stage4_artifacts(
            repository_path=repository,
            config_path="configs/stage4_exact.json",
            plan=prepared,
            executions=(result,),
        )


def plan_with_stage2_identity(config: dict) -> tuple[Stage4Plan, InstanceExecution]:
    prepared, result = prepared_plan(config)
    identity = FrozenInputIdentity(
        stage_name="stage2",
        run_id="stage2-test",
        manifest_path="manifest.json",
        archive_path="archive.tar.gz",
        package_path="raw/stage2-test",
        configuration_sha256="4" * 64,
        package_tree_sha256="5" * 64,
        archive_sha256="6" * 64,
        table_set_sha256=None,
    )
    return replace(prepared, input_identities=(identity,)), result


def test_stage4_execution_uses_frozen_order_and_stage2_identity() -> None:
    prepared, expected = plan_with_stage2_identity(
        {
            "stage_name": "Exact Free-Codebook Optimisation",
        }
    )
    calls = []

    def fake_execute(repository, **kwargs):
        calls.append((repository, kwargs))
        return expected

    results = execute_stage4_plan(
        Path.cwd(),
        prepared,
        execute_function=fake_execute,
        log_search_progress=False,
    )

    assert results == (expected,)
    assert calls[0][1]["stage2_run_id"] == "stage2-test"
    assert calls[0][1]["instance"] is prepared.instances[0]
    assert calls[0][1]["log_search_progress"] is False


def test_definitive_entry_point_executes_then_installs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    config, _ = initialise_stage4_repository(repository)
    prepared, expected = plan_with_stage2_identity(config)
    monkeypatch.setattr(
        "sphere_encoding.stage4.derive_stage4_plan",
        lambda *args, **kwargs: prepared,
    )

    def fake_execute(repository, **kwargs):
        return expected

    installed = install_definitive_stage4_artifacts(
        repository_path=repository,
        config_path="configs/stage4_exact.json",
        execute_function=fake_execute,
        log_search_progress=False,
    )

    assert installed["target_count_attempted"] == 0
    assert (repository / installed["manifest_path"]).is_file()

"""Definitive Stage 4 run identity and manifest construction."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sphere_encoding.config import config_sha256, load_json_config
from sphere_encoding.exact.artifacts import generate_stage4_artifacts
from sphere_encoding.exact.plan import Stage4Plan, derive_stage4_plan
from sphere_encoding.exact.run import (
    InstanceClassification,
    InstanceExecution,
    execute_instance_plan,
)
from sphere_encoding.provenance import (
    atomic_write_bytes,
    build_manifest,
    capture_repository,
    write_manifest,
)

InstanceExecuteFunction = Callable[..., InstanceExecution]


def derive_stage4_run_id(
    config_hash: str,
    implementation_commit: str,
) -> str:
    """Derive the deterministic Stage 4 run identifier."""

    if len(config_hash) != 64:
        raise ValueError("invalid Stage 4 configuration hash")
    if len(implementation_commit) != 40:
        raise ValueError("invalid implementation commit hash")
    return (
        "stage4-exact-free-codebook-"
        f"{config_hash[:12]}-{implementation_commit[:12]}"
    )


def build_stage4_manifest_payload(
    *,
    plan: Stage4Plan,
    executions: Sequence[InstanceExecution],
    generated: Mapping[str, Any],
    implementation_commit: str,
    run_id: str,
    config_path: str,
    package_path: str,
    archive_path: str,
    manifest_path: str,
    table_paths: Mapping[str, str],
) -> dict[str, Any]:
    """Bind frozen inputs, execution evidence, and installed outputs."""

    if len(implementation_commit) != 40:
        raise ValueError("invalid implementation commit hash")
    if len(executions) != plan.instance_count:
        raise ValueError("execution count differs from frozen plan")
    attempted = sum(item.targets_attempted for item in executions)
    if attempted != int(generated["target_count_attempted"]):
        raise ValueError("generated target count differs from executions")
    if int(generated["instance_count"]) != plan.instance_count:
        raise ValueError("generated instance count differs from plan")

    classification_counts = {
        name: sum(item.classification.value == name for item in executions)
        for name in ("exact", "bounded", "upper_bound_only", "failure")
    }
    status_counts: dict[str, int] = {}
    for instance in executions:
        for target in instance.executions:
            status_counts[target.status.value] = (
                status_counts.get(target.status.value, 0) + 1
            )

    upstream = {
        identity.stage_name: {
            "archive_sha256": identity.archive_sha256,
            "configuration_sha256": identity.configuration_sha256,
            "package_tree_sha256": identity.package_tree_sha256,
            "run_id": identity.run_id,
            "table_set_sha256": identity.table_set_sha256,
        }
        for identity in plan.input_identities
    }

    return {
        "archive": {
            "member_count": int(generated["archive_member_count"]),
            "path": archive_path,
            "sha256": str(generated["archive_sha256"]),
        },
        "classifications": classification_counts,
        "config": {
            "path": config_path,
            "sha256": plan.configuration_sha256,
        },
        "deterministic_outputs": {
            "raw_package": {
                "directory": package_path,
                "file_count": int(generated["file_count"]),
                "files": dict(generated["files"]),
                "package_tree_sha256": str(
                    generated["package_tree_sha256"]
                ),
            },
            "tables": {
                "file_count": int(generated["table_file_count"]),
                "files": dict(generated["table_files"]),
                "paths": dict(table_paths),
                "table_set_sha256": str(generated["table_set_sha256"]),
            },
        },
        "implementation_commit": implementation_commit,
        "instance_count": plan.instance_count,
        "manifest_path": manifest_path,
        "plan_sha256": plan.plan_sha256,
        "run_id": run_id,
        "solver_status_counts": dict(sorted(status_counts.items())),
        "stage_name": plan.stage_name,
        "target_count_attempted": attempted,
        "target_count_planned": plan.target_count,
        "total_budget_seconds": plan.total_budget_seconds,
        "upstream_inputs": upstream,
    }


def _repository_relative(repository: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repository.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside repository: {path}") from exc


def install_prepared_stage4_artifacts(
    *,
    repository_path: str | Path,
    config_path: str | Path,
    plan: Stage4Plan,
    executions: Sequence[InstanceExecution],
) -> dict[str, Any]:
    """Install already-computed Stage 4 evidence from a clean commit."""

    repository = Path(repository_path).resolve()
    configuration_path = Path(config_path)
    if not configuration_path.is_absolute():
        configuration_path = repository / configuration_path
    configuration_path = configuration_path.resolve()
    configuration = load_json_config(configuration_path)
    configuration_hash = config_sha256(configuration)
    if configuration_hash != plan.configuration_sha256:
        raise ValueError("plan configuration hash differs from config")

    repository_before = capture_repository(repository)
    if repository_before["clean"] is not True:
        raise ValueError("repository must be clean before Stage 4 installation")
    implementation_commit = str(repository_before["commit"])
    run_id = derive_stage4_run_id(
        configuration_hash,
        implementation_commit,
    )

    outputs = configuration["outputs"]
    final_package = repository / outputs["raw_directory"] / run_id
    final_table_root = repository / outputs["table_directory"]
    final_archive = (
        repository / outputs["archive_directory"] / f"{run_id}.tar.gz"
    )
    final_manifest = (
        repository / outputs["manifest_directory"] / f"{run_id}.json"
    )
    table_names = {
        "target_results": f"{run_id}{outputs['target_table_suffix']}",
        "instance_bounds": f"{run_id}{outputs['instance_table_suffix']}",
        "exact_optima": f"{run_id}{outputs['exact_table_suffix']}",
        "baseline_gaps": f"{run_id}{outputs['baseline_gap_table_suffix']}",
    }
    final_tables = {
        key: final_table_root / filename
        for key, filename in table_names.items()
    }
    destinations = [
        final_package,
        final_archive,
        final_manifest,
        *final_tables.values(),
    ]
    for destination in destinations:
        if destination.exists():
            raise FileExistsError(
                f"definitive destination already exists: {destination}"
            )

    with tempfile.TemporaryDirectory(prefix=f"{run_id}-") as name:
        temporary_root = Path(name)
        temporary_package = temporary_root / "raw" / run_id
        temporary_tables = temporary_root / "tables"
        temporary_archive = temporary_root / f"{run_id}.tar.gz"
        generated = generate_stage4_artifacts(
            plan=plan,
            executions=tuple(executions),
            package_root=temporary_package,
            table_root=temporary_tables,
            archive_path=temporary_archive,
            run_id=run_id,
        )

        package_relative = _repository_relative(repository, final_package)
        archive_relative = _repository_relative(repository, final_archive)
        manifest_relative = _repository_relative(repository, final_manifest)
        table_relatives = {
            key: _repository_relative(repository, path)
            for key, path in final_tables.items()
        }
        payload = build_stage4_manifest_payload(
            plan=plan,
            executions=executions,
            generated=generated,
            implementation_commit=implementation_commit,
            run_id=run_id,
            config_path=_repository_relative(
                repository,
                configuration_path,
            ),
            package_path=package_relative,
            archive_path=archive_relative,
            manifest_path=manifest_relative,
            table_paths=table_relatives,
        )
        manifest = build_manifest(
            stage=4,
            payload=payload,
            repository_path=repository,
            distributions=["numpy", "ortools", "sphere-encoding"],
        )
        if manifest["repository"]["clean"] is not True:
            raise RuntimeError("repository became dirty before installation")
        if manifest["repository"]["commit"] != implementation_commit:
            raise RuntimeError("repository commit changed before installation")

        try:
            final_package.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(temporary_package, final_package)
            final_table_root.mkdir(parents=True, exist_ok=True)
            for key, destination in final_tables.items():
                atomic_write_bytes(
                    destination,
                    (temporary_tables / table_names[key]).read_bytes(),
                )
            atomic_write_bytes(final_archive, temporary_archive.read_bytes())
            write_manifest(final_manifest, manifest)
        except Exception:
            shutil.rmtree(final_package, ignore_errors=True)
            for destination in final_tables.values():
                destination.unlink(missing_ok=True)
            final_archive.unlink(missing_ok=True)
            final_manifest.unlink(missing_ok=True)
            raise

    return {
        "archive_path": archive_relative,
        "archive_sha256": generated["archive_sha256"],
        "manifest_path": manifest_relative,
        "output_directory": package_relative,
        "package_file_count": generated["file_count"],
        "run_id": run_id,
        "table_paths": table_relatives,
        "target_count_attempted": generated["target_count_attempted"],
    }


def execute_stage4_plan(
    repository_path: str | Path,
    plan: Stage4Plan,
    *,
    execute_function: InstanceExecuteFunction = execute_instance_plan,
    log_search_progress: bool = True,
) -> tuple[InstanceExecution, ...]:
    """Execute every frozen instance in order, stopping on failure."""

    repository = Path(repository_path).resolve()
    stage2_identities = tuple(
        identity
        for identity in plan.input_identities
        if identity.stage_name == "stage2"
    )
    if len(stage2_identities) != 1:
        raise ValueError("plan must contain exactly one Stage 2 identity")
    stage2_run_id = stage2_identities[0].run_id

    results: list[InstanceExecution] = []
    for instance in plan.instances:
        result = execute_function(
            repository,
            stage2_run_id=stage2_run_id,
            instance=instance,
            log_search_progress=log_search_progress,
        )
        expected_identity = (
            instance.execution_order,
            instance.graph_id,
            instance.code_length,
        )
        actual_identity = (
            result.execution_order,
            result.graph_id,
            result.code_length,
        )
        if actual_identity != expected_identity:
            raise RuntimeError("instance executor returned the wrong identity")
        if result.classification is InstanceClassification.FAILURE:
            raise RuntimeError(
                f"Stage 4 instance failed: {instance.graph_id}, "
                f"m={instance.code_length}"
            )
        if (
            result.classification is not InstanceClassification.EXACT
            and result.targets_attempted != result.targets_planned
        ):
            raise RuntimeError("non-exact instance omitted frozen targets")
        results.append(result)

    if len(results) != plan.instance_count:
        raise RuntimeError("not all frozen Stage 4 instances were executed")
    return tuple(results)


def install_definitive_stage4_artifacts(
    *,
    repository_path: str | Path,
    config_path: str | Path,
    execute_function: InstanceExecuteFunction = execute_instance_plan,
    log_search_progress: bool = True,
) -> dict[str, Any]:
    """Execute and install the definitive Stage 4 scientific outputs."""

    repository = Path(repository_path).resolve()
    repository_before = capture_repository(repository)
    if repository_before["clean"] is not True:
        raise ValueError("repository must be clean before definitive Stage 4")
    resolved_config_path = Path(config_path)
    if not resolved_config_path.is_absolute():
        resolved_config_path = repository / resolved_config_path
    plan = derive_stage4_plan(
        repository,
        config_path=resolved_config_path,
    )
    executions = execute_stage4_plan(
        repository,
        plan,
        execute_function=execute_function,
        log_search_progress=log_search_progress,
    )
    repository_after = capture_repository(repository)
    if repository_after != repository_before:
        raise RuntimeError("repository changed during definitive Stage 4 solve")
    return install_prepared_stage4_artifacts(
        repository_path=repository,
        config_path=resolved_config_path,
        plan=plan,
        executions=executions,
    )

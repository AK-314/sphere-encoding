"""Definitive Stage 4 run identity and manifest construction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sphere_encoding.exact.plan import Stage4Plan
from sphere_encoding.exact.run import InstanceExecution


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

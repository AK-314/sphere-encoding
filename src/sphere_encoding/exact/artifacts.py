"""Lossless Stage 4 target and instance artifact serialization."""

from __future__ import annotations

import csv
import hashlib
import io
import shutil
import tempfile
from pathlib import Path
from typing import Any

from sphere_encoding.config import canonical_json_dumps, pretty_json_dumps
from sphere_encoding.exact.plan import Stage4Plan
from sphere_encoding.exact.run import InstanceExecution, TargetExecution
from sphere_encoding.graphs.artifacts import (
    collect_file_hashes,
    npy_bytes,
    write_deterministic_tar_gz,
)
from sphere_encoding.hashing import sha256_bytes, sha256_file
from sphere_encoding.provenance import atomic_write_bytes, atomic_write_text

TARGET_FIELDS = (
    "execution_order",
    "graph_id",
    "code_length",
    "target_order_within_instance",
    "target_r",
    "budget_seconds",
    "status",
    "model_sha256",
    "variable_count",
    "constraint_count",
    "wall_time_seconds",
    "user_time_seconds",
    "conflict_count",
    "branch_count",
    "has_feasible_witness",
    "certifies_infeasibility",
    "witness_l_max",
    "witness_codebook_sha256",
)

INSTANCE_FIELDS = (
    "execution_order",
    "graph_id",
    "code_length",
    "classification",
    "structural_lower_bound",
    "baseline_upper_bound",
    "final_lower_bound",
    "final_upper_bound",
    "targets_planned",
    "targets_attempted",
    "unknown_target_count",
)

EXACT_FIELDS = (
    "execution_order",
    "graph_id",
    "code_length",
    "exact_l_star_free",
)

GAP_FIELDS = (
    "execution_order",
    "graph_id",
    "code_length",
    "baseline_upper_bound",
    "final_upper_bound",
    "baseline_gap_closed",
)


def _target_payload(execution: TargetExecution) -> dict[str, Any]:
    validation = None
    if execution.has_feasible_witness:
        validation = {
            "codebook_sha256": execution.witness_codebook_sha256,
            "maximum_edge_hamming_distance": execution.witness_l_max,
        }

    return {
        "budget_seconds": execution.budget_seconds,
        "certifies_infeasibility": execution.certifies_infeasibility,
        "constraint_count": execution.constraint_count,
        "has_feasible_witness": execution.has_feasible_witness,
        "model_sha256": execution.model_sha256,
        "raw_status": execution.status.value,
        "runtime": {
            "branch_count": execution.branch_count,
            "conflict_count": execution.conflict_count,
            "user_time_seconds": execution.user_time_seconds,
            "wall_time_seconds": execution.wall_time_seconds,
        },
        "target_order_within_instance": (
            execution.target_order_within_instance
        ),
        "target_r": execution.target_r,
        "validation": validation,
        "variable_count": execution.variable_count,
    }


def _validate_preserved_evidence(execution: TargetExecution) -> None:
    actual_model_hash = hashlib.sha256(execution.model_bytes).hexdigest()
    if actual_model_hash != execution.model_sha256:
        raise ValueError("preserved model bytes do not match model hash")

    if execution.has_feasible_witness:
        if execution.witness_codebook is None:
            raise ValueError("feasible target lacks preserved codebook")
        if execution.witness_codebook_sha256 is None:
            raise ValueError("feasible target lacks codebook hash")
        actual_codebook_hash = hashlib.sha256(
            npy_bytes(execution.witness_codebook)
        ).hexdigest()
        if actual_codebook_hash != execution.witness_codebook_sha256:
            raise ValueError("preserved codebook does not match its hash")
    elif execution.witness_codebook is not None:
        raise ValueError("non-feasible target contains a codebook")


def write_instance_artifacts(
    output_root: Path,
    execution: InstanceExecution,
) -> dict[str, str]:
    """Write all raw evidence for one completed instance atomically."""

    destination = (
        output_root
        / execution.graph_id
        / f"m{execution.code_length}"
    )
    if destination.exists():
        raise FileExistsError(
            f"instance artifact destination exists: {destination}"
        )

    target_root = destination / "targets"
    target_root.mkdir(parents=True)

    try:
        for target in execution.executions:
            _validate_preserved_evidence(target)
            target_path = target_root / f"r{target.target_r}"
            target_path.mkdir()

            atomic_write_bytes(target_path / "model.pb", target.model_bytes)
            atomic_write_text(
                target_path / "response_stats.txt",
                target.response_stats.rstrip("\n") + "\n",
            )
            atomic_write_text(
                target_path / "solver.log",
                target.solver_log.rstrip("\n") + "\n",
            )
            atomic_write_text(
                target_path / "target.json",
                pretty_json_dumps(_target_payload(target)),
            )
            if target.witness_codebook is not None:
                atomic_write_bytes(
                    target_path / "codebook.npy",
                    npy_bytes(target.witness_codebook),
                )

        instance_payload = {
            "baseline_upper_bound": execution.baseline_upper_bound,
            "classification": execution.classification.value,
            "code_length": execution.code_length,
            "execution_order": execution.execution_order,
            "final_lower_bound": execution.final_lower_bound,
            "final_upper_bound": execution.final_upper_bound,
            "graph_id": execution.graph_id,
            "structural_lower_bound": execution.structural_lower_bound,
            "targets_attempted": execution.targets_attempted,
            "targets_planned": execution.targets_planned,
            "unknown_target_count": execution.unknown_target_count,
        }
        atomic_write_text(
            destination / "instance.json",
            pretty_json_dumps(instance_payload),
        )
    except Exception:
        import shutil

        shutil.rmtree(destination, ignore_errors=True)
        raise

    return collect_file_hashes(destination)


def _csv_bytes(
    fieldnames: tuple[str, ...],
    rows: list[dict[str, Any]],
) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=fieldnames,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def write_stage4_tables(
    table_root: Path,
    *,
    run_id: str,
    executions: tuple[InstanceExecution, ...],
) -> dict[str, str]:
    """Write the four frozen Stage 4 result tables."""

    if not run_id.startswith("stage4-"):
        raise ValueError("invalid Stage 4 run identifier")
    orders = tuple(item.execution_order for item in executions)
    if orders != tuple(sorted(orders)) or len(set(orders)) != len(orders):
        raise ValueError("instance executions are not uniquely ordered")

    target_rows: list[dict[str, Any]] = []
    instance_rows: list[dict[str, Any]] = []
    exact_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []

    for instance in executions:
        for target in instance.executions:
            target_rows.append(
                {
                    "execution_order": instance.execution_order,
                    "graph_id": instance.graph_id,
                    "code_length": instance.code_length,
                    "target_order_within_instance": (
                        target.target_order_within_instance
                    ),
                    "target_r": target.target_r,
                    "budget_seconds": target.budget_seconds,
                    "status": target.status.value,
                    "model_sha256": target.model_sha256,
                    "variable_count": target.variable_count,
                    "constraint_count": target.constraint_count,
                    "wall_time_seconds": target.wall_time_seconds,
                    "user_time_seconds": target.user_time_seconds,
                    "conflict_count": target.conflict_count,
                    "branch_count": target.branch_count,
                    "has_feasible_witness": target.has_feasible_witness,
                    "certifies_infeasibility": (
                        target.certifies_infeasibility
                    ),
                    "witness_l_max": (
                        ""
                        if target.witness_l_max is None
                        else target.witness_l_max
                    ),
                    "witness_codebook_sha256": (
                        target.witness_codebook_sha256 or ""
                    ),
                }
            )

        instance_rows.append(
            {
                "execution_order": instance.execution_order,
                "graph_id": instance.graph_id,
                "code_length": instance.code_length,
                "classification": instance.classification.value,
                "structural_lower_bound": (
                    instance.structural_lower_bound
                ),
                "baseline_upper_bound": instance.baseline_upper_bound,
                "final_lower_bound": instance.final_lower_bound,
                "final_upper_bound": instance.final_upper_bound,
                "targets_planned": instance.targets_planned,
                "targets_attempted": instance.targets_attempted,
                "unknown_target_count": instance.unknown_target_count,
            }
        )
        if instance.classification.value == "exact":
            exact_rows.append(
                {
                    "execution_order": instance.execution_order,
                    "graph_id": instance.graph_id,
                    "code_length": instance.code_length,
                    "exact_l_star_free": instance.final_upper_bound,
                }
            )
        gap_rows.append(
            {
                "execution_order": instance.execution_order,
                "graph_id": instance.graph_id,
                "code_length": instance.code_length,
                "baseline_upper_bound": instance.baseline_upper_bound,
                "final_upper_bound": instance.final_upper_bound,
                "baseline_gap_closed": (
                    instance.baseline_upper_bound
                    - instance.final_upper_bound
                ),
            }
        )

    table_root.mkdir(parents=True, exist_ok=True)
    tables = {
        f"{run_id}_target_results.csv": (TARGET_FIELDS, target_rows),
        f"{run_id}_instance_bounds.csv": (INSTANCE_FIELDS, instance_rows),
        f"{run_id}_exact_optima.csv": (EXACT_FIELDS, exact_rows),
        f"{run_id}_baseline_gaps.csv": (GAP_FIELDS, gap_rows),
    }
    hashes: dict[str, str] = {}
    for filename, (fields, rows) in tables.items():
        path = table_root / filename
        if path.exists():
            raise FileExistsError(f"table destination exists: {path}")
        content = _csv_bytes(fields, rows)
        atomic_write_bytes(path, content)
        hashes[filename] = hashlib.sha256(content).hexdigest()

    return hashes


def generate_stage4_artifacts(
    *,
    plan: Stage4Plan,
    executions: tuple[InstanceExecution, ...],
    package_root: Path,
    table_root: Path,
    archive_path: Path,
    run_id: str,
) -> dict[str, Any]:
    """Build a complete Stage 4 package, table set, and archive."""

    if package_root.exists():
        raise FileExistsError(f"package destination exists: {package_root}")
    if archive_path.exists():
        raise FileExistsError(f"archive destination exists: {archive_path}")
    if len(executions) != plan.instance_count:
        raise ValueError("execution count differs from frozen plan")

    expected_instances = tuple(
        (item.execution_order, item.graph_id, item.code_length)
        for item in plan.instances
    )
    actual_instances = tuple(
        (item.execution_order, item.graph_id, item.code_length)
        for item in executions
    )
    if actual_instances != expected_instances:
        raise ValueError("executions differ from frozen instance order")
    if any(
        item.targets_attempted != item.targets_planned
        and item.classification.value not in {"exact", "failure"}
        for item in executions
    ):
        raise ValueError("incomplete non-terminal instance execution")

    package_root.mkdir(parents=True)
    try:
        for execution in executions:
            write_instance_artifacts(package_root, execution)

        table_files = write_stage4_tables(
            table_root,
            run_id=run_id,
            executions=executions,
        )
        deterministic_files = collect_file_hashes(package_root)
        package_tree_hash = sha256_bytes(
            canonical_json_dumps(deterministic_files).encode("utf-8")
        )
        table_set_hash = sha256_bytes(
            canonical_json_dumps(table_files).encode("utf-8")
        )
        metadata = {
            "baseline_tie_instance_count": (
                plan.baseline_tie_instance_count
            ),
            "classification_counts": {
                name: sum(
                    execution.classification.value == name
                    for execution in executions
                )
                for name in ("exact", "bounded", "upper_bound_only", "failure")
            },
            "configuration_sha256": plan.configuration_sha256,
            "deterministic_file_count_without_package_metadata": len(
                deterministic_files
            ),
            "deterministic_files": deterministic_files,
            "instance_count": len(executions),
            "package_tree_sha256": package_tree_hash,
            "plan_sha256": plan.plan_sha256,
            "run_id": run_id,
            "schema_version": 1,
            "stage": 4,
            "stage_name": plan.stage_name,
            "table_file_count": len(table_files),
            "table_files": table_files,
            "table_set_sha256": table_set_hash,
            "target_count_attempted": sum(
                execution.targets_attempted for execution in executions
            ),
            "target_count_planned": plan.target_count,
            "total_budget_seconds": plan.total_budget_seconds,
        }
        atomic_write_text(
            package_root / "package_metadata.json",
            pretty_json_dumps(metadata),
        )

        with tempfile.TemporaryDirectory(
            prefix=f"{run_id}-archive-"
        ) as temporary_name:
            archive_root = Path(temporary_name) / "contents"
            raw_destination = archive_root / "raw" / run_id
            tables_destination = archive_root / "tables"
            shutil.copytree(package_root, raw_destination)
            tables_destination.mkdir(parents=True)
            for filename in sorted(table_files):
                shutil.copyfile(
                    table_root / filename,
                    tables_destination / filename,
                )
            write_deterministic_tar_gz(archive_root, archive_path)

        all_files = collect_file_hashes(package_root)
        return {
            "archive_member_count": len(all_files) + len(table_files),
            "archive_sha256": sha256_file(archive_path),
            "file_count": len(all_files),
            "files": all_files,
            "instance_count": len(executions),
            "package_tree_sha256": package_tree_hash,
            "table_file_count": len(table_files),
            "table_files": table_files,
            "table_set_sha256": table_set_hash,
            "target_count_attempted": sum(
                execution.targets_attempted for execution in executions
            ),
        }
    except Exception:
        shutil.rmtree(package_root, ignore_errors=True)
        for filename in (
            f"{run_id}_target_results.csv",
            f"{run_id}_instance_bounds.csv",
            f"{run_id}_exact_optima.csv",
            f"{run_id}_baseline_gaps.csv",
        ):
            (table_root / filename).unlink(missing_ok=True)
        archive_path.unlink(missing_ok=True)
        raise

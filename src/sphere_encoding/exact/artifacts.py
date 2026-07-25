"""Lossless Stage 4 target and instance artifact serialization."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sphere_encoding.config import pretty_json_dumps
from sphere_encoding.exact.run import InstanceExecution, TargetExecution
from sphere_encoding.graphs.artifacts import collect_file_hashes, npy_bytes
from sphere_encoding.provenance import atomic_write_bytes, atomic_write_text


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

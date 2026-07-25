"""Independent Stage 4 artifact and solver reproduction checks."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from sphere_encoding.config import canonical_json_dumps, load_json_config
from sphere_encoding.exact.artifacts import load_instance_artifacts
from sphere_encoding.exact.model import build_exact_feasibility_model
from sphere_encoding.exact.plan import Stage4Plan
from sphere_encoding.exact.run import (
    InstanceClassification,
    SolveFunction,
    classify_instance_executions,
    execute_instance_plan,
)
from sphere_encoding.exact.solver import validate_exact_witness
from sphere_encoding.graphs.artifacts import collect_file_hashes
from sphere_encoding.hashing import sha256_bytes


def audit_stage4_package(
    repository_path: Path,
    *,
    plan: Stage4Plan,
    package_root: Path,
) -> dict[str, Any]:
    """Regenerate all models and independently validate stored evidence."""

    metadata_path = package_root / "package_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata["stage"] != 4:
        raise ValueError("artifact package is not Stage 4")
    if metadata["plan_sha256"] != plan.plan_sha256:
        raise ValueError("artifact plan hash differs from frozen plan")
    if metadata["configuration_sha256"] != plan.configuration_sha256:
        raise ValueError("artifact config hash differs from frozen plan")

    all_files = collect_file_hashes(package_root)
    metadata_hash = all_files.pop("package_metadata.json", None)
    if metadata_hash is None:
        raise ValueError("package metadata is absent from file inventory")
    if all_files != metadata["deterministic_files"]:
        raise ValueError("artifact file hashes differ from package metadata")
    tree_hash = sha256_bytes(
        canonical_json_dumps(all_files).encode("utf-8")
    )
    if tree_hash != metadata["package_tree_sha256"]:
        raise ValueError("artifact package-tree hash is inconsistent")

    stage2 = tuple(
        identity
        for identity in plan.input_identities
        if identity.stage_name == "stage2"
    )
    if len(stage2) != 1:
        raise ValueError("plan must contain one Stage 2 identity")
    graph_root = repository_path / "results" / "raw" / stage2[0].run_id
    stage3_config = load_json_config(
        repository_path / "configs" / "stage3_baselines.json"
    )

    model_count = 0
    witness_count = 0
    results = []
    for instance in plan.instances:
        stored = load_instance_artifacts(
            package_root,
            graph_id=instance.graph_id,
            code_length=instance.code_length,
        )
        derived = classify_instance_executions(instance, stored.executions)
        if derived != stored:
            raise ValueError("stored instance classification is inconsistent")
        edges = np.load(
            graph_root / instance.graph_id / "edges.npy",
            allow_pickle=False,
        )
        vertices = np.load(
            graph_root / instance.graph_id / "vertices.npy",
            allow_pickle=False,
        )
        graph_metadata = json.loads(
            (
                graph_root / instance.graph_id / "metadata.json"
            ).read_text(encoding="utf-8")
        )
        for target, execution in zip(
            instance.targets,
            stored.executions,
            strict=False,
        ):
            if target.target_r != execution.target_r:
                raise ValueError("stored target differs from frozen plan")
            built = build_exact_feasibility_model(
                vertex_count=instance.vertex_count,
                edges=edges,
                code_length=instance.code_length,
                target_r=target.target_r,
                symmetry_breaking=True,
            )
            if built.model_sha256 != execution.model_sha256:
                raise ValueError("regenerated model hash differs")
            if built.model_bytes != execution.model_bytes:
                raise ValueError("regenerated model bytes differ")
            if (
                built.variable_count != execution.variable_count
                or built.constraint_count != execution.constraint_count
            ):
                raise ValueError("regenerated model size differs")
            model_count += 1
            if execution.witness_codebook is not None:
                validation = validate_exact_witness(
                    execution.witness_codebook,
                    built,
                    vertices=vertices,
                    far_threshold=stage3_config["far_pairs"]["threshold"],
                    antipodal_atol=stage3_config["antipodal_pairs"][
                        "accepted_stage2_atol"
                    ],
                    expected_antipodal_count=graph_metadata["diagnostics"][
                        "antipodal_pair_count"
                    ],
                )
                if (
                    validation.codebook_sha256
                    != execution.witness_codebook_sha256
                    or validation.maximum_edge_hamming_distance
                    != execution.witness_l_max
                ):
                    raise ValueError("stored witness validation differs")
                if validation.global_diagnostics != (
                    execution.global_diagnostics
                ):
                    raise ValueError("stored global diagnostics differ")
                witness_count += 1
        results.append(stored)

    if len(results) != plan.instance_count:
        raise ValueError("artifact instance count differs from plan")
    return {
        "instance_count": len(results),
        "model_count": model_count,
        "package_tree_sha256": tree_hash,
        "witness_count": witness_count,
    }


def reproduce_stage4_solver_results(
    repository_path: Path,
    *,
    plan: Stage4Plan,
    package_root: Path,
    solve_function: SolveFunction,
    log_search_progress: bool = True,
) -> dict[str, Any]:
    """Re-solve attempted targets and enforce claim-bearing agreement."""

    stage2 = tuple(
        identity
        for identity in plan.input_identities
        if identity.stage_name == "stage2"
    )
    if len(stage2) != 1:
        raise ValueError("plan must contain one Stage 2 identity")

    status_disagreements = 0
    reproduced_instances = 0
    for instance in plan.instances:
        original = load_instance_artifacts(
            package_root,
            graph_id=instance.graph_id,
            code_length=instance.code_length,
        )
        truncated = replace(
            instance,
            targets=instance.targets[: original.targets_attempted],
        )
        reproduced = execute_instance_plan(
            repository_path,
            stage2_run_id=stage2[0].run_id,
            instance=truncated,
            solve_function=solve_function,
            log_search_progress=log_search_progress,
        )
        for first, second in zip(
            original.executions,
            reproduced.executions,
            strict=True,
        ):
            if first.model_sha256 != second.model_sha256:
                raise ValueError("reproduction model hash differs")
            if first.status != second.status:
                status_disagreements += 1
            if first.certifies_infeasibility and not (
                second.certifies_infeasibility
            ):
                raise ValueError("INFEASIBLE status did not reproduce")

        if original.classification is InstanceClassification.EXACT:
            if (
                reproduced.classification is not InstanceClassification.EXACT
                or reproduced.final_lower_bound != original.final_lower_bound
                or reproduced.final_upper_bound != original.final_upper_bound
            ):
                raise ValueError("exact classification did not reproduce")
        reproduced_instances += 1

    return {
        "instance_count": reproduced_instances,
        "status_disagreement_count": status_disagreements,
    }

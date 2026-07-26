"""Deterministic Stage 5 run, target, instance, table, and archive artifacts."""

from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import numpy as np

from sphere_encoding.config import (
    canonical_json_dumps,
    pretty_json_dumps,
)
from sphere_encoding.graphs.artifacts import (
    collect_file_hashes,
    npy_bytes,
    write_deterministic_tar_gz,
)
from sphere_encoding.hashing import sha256_bytes, sha256_file
from sphere_encoding.heuristic.search import (
    SearchKernelCheckpoint,
    SearchKernelResult,
    search_kernel_config_payload,
    search_kernel_config_sha256,
)
from sphere_encoding.heuristic.state import SearchState
from sphere_encoding.heuristic.verification import (
    SearchVerificationReport,
)
from sphere_encoding.provenance import (
    atomic_write_bytes,
    atomic_write_text,
)

RUN_SCHEMA_VERSION: Final = "stage5_heuristic_run_v1"
TARGET_SCHEMA_VERSION: Final = "stage5_heuristic_target_v1"
INSTANCE_SCHEMA_VERSION: Final = "stage5_heuristic_instance_v1"
PACKAGE_SCHEMA_VERSION: Final = 1

RUN_TABLE_SUFFIX: Final = "_run_results.csv"
TARGET_TABLE_SUFFIX: Final = "_target_results.csv"
INSTANCE_TABLE_SUFFIX: Final = "_instance_bounds.csv"
EXACT_TABLE_SUFFIX: Final = "_exact_optima.csv"

NEGATIVE_RESULT_INTERPRETATION: Final = (
    "No feasible witness was found within the frozen heuristic budget; "
    "this is not evidence of infeasibility or optimality."
)

InstanceMode = Literal[
    "search_completed",
    "exact_by_accepted_transfer",
]
ResultClassification = Literal[
    "exact_by_accepted_transfer",
    "exact_by_heuristic_witness",
    "heuristic_upper_bound_improved",
    "no_heuristic_improvement",
]

RUN_FIELDS: Final = (
    "execution_order",
    "graph_id",
    "code_length",
    "target_order_within_instance",
    "target_r",
    "run_order_within_target",
    "initialisation_class",
    "initialisation_id",
    "restart_index",
    "seed",
    "kernel_config_sha256",
    "proposal_budget",
    "proposals_executed",
    "swap_proposals",
    "replacement_proposals",
    "accepted_moves",
    "stopping_reason",
    "success",
    "first_success_proposal",
    "initial_violation_count",
    "initial_total_excess",
    "initial_maximum_excess",
    "initial_maximum_distance_edge_count",
    "initial_total_local_hamming",
    "best_violation_count",
    "best_total_excess",
    "best_maximum_excess",
    "best_maximum_distance_edge_count",
    "best_total_local_hamming",
    "final_violation_count",
    "final_total_excess",
    "final_maximum_excess",
    "final_maximum_distance_edge_count",
    "final_total_local_hamming",
    "initial_state_sha256",
    "best_state_sha256",
    "final_state_sha256",
    "checkpoint_sha256",
)

TARGET_FIELDS: Final = (
    "execution_order",
    "graph_id",
    "code_length",
    "target_order_within_instance",
    "target_r",
    "run_count",
    "success",
    "best_run_order",
    "best_initialisation_class",
    "best_initialisation_id",
    "best_restart_index",
    "best_seed",
    "best_violation_count",
    "best_total_excess",
    "best_maximum_excess",
    "best_maximum_distance_edge_count",
    "best_total_local_hamming",
    "first_success_proposal",
    "negative_result_interpretation",
)

INSTANCE_FIELDS: Final = (
    "execution_order",
    "graph_id",
    "code_length",
    "mode",
    "classification",
    "accepted_lower_bound",
    "accepted_upper_bound",
    "final_lower_bound",
    "final_upper_bound",
    "targets_planned",
    "targets_attempted",
    "successful_target_count",
    "exact_optimum_established",
    "upper_bound_improvement",
    "negative_result_interpretation",
)

EXACT_FIELDS: Final = (
    "execution_order",
    "graph_id",
    "code_length",
    "exact_l_star_free",
    "established_by",
)


class ArtifactError(ValueError):
    """Raised when deterministic Stage 5 evidence is inconsistent."""


def _canonical_mapping(
    value: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    try:
        encoded = canonical_json_dumps(dict(value))
        decoded = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ArtifactError(f"{label} is not deterministic JSON") from error
    if not isinstance(decoded, dict):
        raise ArtifactError(f"{label} must be a JSON object")
    return decoded


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _score_payload(
    score: tuple[int, int, int, int, int],
) -> dict[str, int]:
    return {
        "maximum_distance_edge_count": score[3],
        "maximum_excess": score[2],
        "total_excess": score[1],
        "total_local_hamming": score[4],
        "violation_count": score[0],
    }


def _score_tuple(payload: object) -> tuple[int, int, int, int, int]:
    if not isinstance(payload, dict):
        raise ArtifactError("score payload must be an object")
    try:
        score = (
            int(payload["violation_count"]),
            int(payload["total_excess"]),
            int(payload["maximum_excess"]),
            int(payload["maximum_distance_edge_count"]),
            int(payload["total_local_hamming"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ArtifactError("invalid score payload") from error
    if any(value < 0 for value in score):
        raise ArtifactError("score components must be non-negative")
    return score


def _score_columns(
    prefix: str,
    score: tuple[int, int, int, int, int],
) -> dict[str, int]:
    return {
        f"{prefix}_violation_count": score[0],
        f"{prefix}_total_excess": score[1],
        f"{prefix}_maximum_excess": score[2],
        f"{prefix}_maximum_distance_edge_count": score[3],
        f"{prefix}_total_local_hamming": score[4],
    }


def _trajectory_bytes(
    checkpoint: SearchKernelCheckpoint,
) -> bytes:
    steps = checkpoint.payload()["steps"]
    if not isinstance(steps, list):
        raise ArtifactError("checkpoint trajectory payload is not a list")
    return b"".join(
        canonical_json_dumps(step).encode("utf-8") + b"\n" for step in steps
    )


def _verification_payload(
    report: SearchVerificationReport,
) -> dict[str, object]:
    return {
        "accepted_moves_verified": report.accepted_moves_verified,
        "best_score": _score_payload(report.best_score),
        "best_state_sha256": report.best_state_sha256,
        "final_score": _score_payload(report.final_score),
        "final_state_sha256": report.final_state_sha256,
        "first_success_proposal": report.first_success_proposal,
        "proposals_verified": report.proposals_verified,
        "replacement_proposals_verified": (report.replacement_proposals_verified),
        "stopping_reason": report.stopping_reason,
        "swap_proposals_verified": report.swap_proposals_verified,
    }


def _verification_from_payload(
    payload: object,
) -> SearchVerificationReport:
    if not isinstance(payload, dict):
        raise ArtifactError("verification payload must be an object")
    try:
        first_success_value = payload["first_success_proposal"]
        first_success = (
            None if first_success_value is None else int(first_success_value)
        )
        return SearchVerificationReport(
            proposals_verified=int(payload["proposals_verified"]),
            swap_proposals_verified=int(payload["swap_proposals_verified"]),
            replacement_proposals_verified=int(
                payload["replacement_proposals_verified"]
            ),
            accepted_moves_verified=int(payload["accepted_moves_verified"]),
            first_success_proposal=first_success,
            final_state_sha256=str(payload["final_state_sha256"]),
            best_state_sha256=str(payload["best_state_sha256"]),
            final_score=_score_tuple(payload["final_score"]),
            best_score=_score_tuple(payload["best_score"]),
            stopping_reason=str(payload["stopping_reason"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ArtifactError("invalid verification payload") from error


@dataclass(frozen=True, slots=True)
class HeuristicRunExecution:
    """One complete deterministic initialisation/restart search run."""

    run_order_within_target: int
    initialisation_class: str
    initialisation_id: str
    restart_index: int
    seed: int
    initialisation_metadata: dict[str, object]
    result: SearchKernelResult
    verification: SearchVerificationReport

    def __post_init__(self) -> None:
        if (
            not isinstance(self.run_order_within_target, int)
            or self.run_order_within_target <= 0
        ):
            raise ArtifactError("run order must be a positive integer")
        if not self.initialisation_class:
            raise ArtifactError("initialisation class must be non-empty")
        if not self.initialisation_id:
            raise ArtifactError("initialisation identifier must be non-empty")
        if not isinstance(self.restart_index, int) or self.restart_index < 0:
            raise ArtifactError("restart index must be non-negative")
        if not isinstance(self.seed, int) or self.seed < 0:
            raise ArtifactError("run seed must be non-negative")
        if self.seed != self.result.seed:
            raise ArtifactError("run seed differs from search result")

        metadata = _canonical_mapping(
            self.initialisation_metadata,
            label="initialisation metadata",
        )
        object.__setattr__(self, "initialisation_metadata", metadata)

        report = self.verification
        result = self.result
        if report.proposals_verified != result.proposals_executed:
            raise ArtifactError("verified proposal count differs")
        if report.swap_proposals_verified != result.swap_proposals:
            raise ArtifactError("verified swap count differs")
        if report.replacement_proposals_verified != result.replacement_proposals:
            raise ArtifactError("verified replacement count differs")
        if report.accepted_moves_verified != result.accepted_moves:
            raise ArtifactError("verified accepted count differs")
        if report.first_success_proposal != result.first_success_proposal:
            raise ArtifactError("verified success point differs")
        if report.final_state_sha256 != result.final_state.state_sha256():
            raise ArtifactError("verified final-state hash differs")
        if report.best_state_sha256 != result.best_state.state_sha256():
            raise ArtifactError("verified best-state hash differs")
        if report.final_score != result.final_scoring.score.as_tuple():
            raise ArtifactError("verified final score differs")
        if report.best_score != result.best_scoring.score.as_tuple():
            raise ArtifactError("verified best score differs")
        if report.stopping_reason != result.stopping_reason:
            raise ArtifactError("verified stopping reason differs")

        if result.stopping_reason == "checkpoint_reached":
            raise ArtifactError(
                "partial checkpoint results cannot be packaged as completed runs"
            )
        if result.stopping_reason == "proposal_budget_exhausted":
            if result.proposals_executed != result.checkpoint.config.proposal_budget:
                raise ArtifactError("completed run did not exhaust its budget")
        if self.success != result.success:
            raise ArtifactError("run success state is inconsistent")

    @property
    def success(self) -> bool:
        return self.result.best_scoring.score.is_feasible

    @property
    def best_score(self) -> tuple[int, int, int, int, int]:
        return self.result.best_scoring.score.as_tuple()

    @property
    def final_score(self) -> tuple[int, int, int, int, int]:
        return self.result.final_scoring.score.as_tuple()

    @property
    def initial_score(self) -> tuple[int, int, int, int, int]:
        return self.result.initial_score.as_tuple()


@dataclass(frozen=True, slots=True)
class HeuristicTargetExecution:
    """All frozen runs attempted for one threshold."""

    target_order_within_instance: int
    target_r: int
    runs: tuple[HeuristicRunExecution, ...]
    best_run_order: int
    success: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.target_order_within_instance, int)
            or self.target_order_within_instance <= 0
        ):
            raise ArtifactError("target order must be positive")
        if not isinstance(self.target_r, int) or self.target_r < 0:
            raise ArtifactError("target threshold must be non-negative")
        if not self.runs:
            raise ArtifactError("target execution must preserve at least one run")
        if tuple(run.run_order_within_target for run in self.runs) != tuple(
            range(1, len(self.runs) + 1)
        ):
            raise ArtifactError("target run order is not contiguous")
        if any(run.result.checkpoint.target_r != self.target_r for run in self.runs):
            raise ArtifactError("run target differs from target execution")

        expected_best = min(
            self.runs,
            key=lambda run: (
                run.best_score,
                run.run_order_within_target,
            ),
        )
        if self.best_run_order != expected_best.run_order_within_target:
            raise ArtifactError("best run does not follow frozen tie-breaking")
        if self.success != expected_best.success:
            raise ArtifactError("target success differs from best run")

    @property
    def best_run(self) -> HeuristicRunExecution:
        return self.runs[self.best_run_order - 1]


@dataclass(frozen=True, slots=True)
class HeuristicInstanceExecution:
    """Completed Stage 5 evidence for one graph-length candidate."""

    execution_order: int
    graph_id: str
    code_length: int
    accepted_lower_bound: int
    accepted_upper_bound: int
    mode: InstanceMode
    targets_planned: tuple[int, ...]
    target_executions: tuple[HeuristicTargetExecution, ...]
    transfer_witness: SearchState | None
    transfer_metadata: dict[str, object] | None

    def __post_init__(self) -> None:
        if not isinstance(self.execution_order, int) or self.execution_order <= 0:
            raise ArtifactError("instance execution order must be positive")
        if not self.graph_id:
            raise ArtifactError("graph identifier must be non-empty")
        if not isinstance(self.code_length, int) or self.code_length <= 0:
            raise ArtifactError("code length must be positive")
        if (
            not isinstance(self.accepted_lower_bound, int)
            or not isinstance(self.accepted_upper_bound, int)
            or self.accepted_lower_bound < 0
            or self.accepted_upper_bound < self.accepted_lower_bound
        ):
            raise ArtifactError("accepted instance bounds are invalid")

        expected_targets = tuple(
            range(self.accepted_lower_bound, self.accepted_upper_bound)
        )
        if self.targets_planned != expected_targets:
            raise ArtifactError(
                "planned targets are not the complete ascending accepted gap"
            )

        if self.mode == "exact_by_accepted_transfer":
            if self.accepted_lower_bound != self.accepted_upper_bound:
                raise ArtifactError("transfer-exact bounds must coincide")
            if self.targets_planned or self.target_executions:
                raise ArtifactError("transfer-exact instance cannot have targets")
            if self.transfer_witness is None:
                raise ArtifactError("transfer-exact instance lacks a witness")
            if self.transfer_witness.code_length != self.code_length:
                raise ArtifactError("transfer witness width differs")
            if self.transfer_metadata is None:
                raise ArtifactError("transfer witness lacks provenance")
            metadata = _canonical_mapping(
                self.transfer_metadata,
                label="transfer metadata",
            )
            object.__setattr__(self, "transfer_metadata", metadata)
            return

        if self.mode != "search_completed":
            raise ArtifactError(f"unrecognised instance mode: {self.mode!r}")
        if self.transfer_witness is not None or self.transfer_metadata is not None:
            raise ArtifactError("search instance cannot carry transfer evidence")
        if not self.targets_planned:
            raise ArtifactError("search instance must have an unresolved gap")

        attempted_values = tuple(target.target_r for target in self.target_executions)
        if attempted_values != self.targets_planned[: len(attempted_values)]:
            raise ArtifactError("attempted targets are not an ascending prefix")
        if tuple(
            target.target_order_within_instance for target in self.target_executions
        ) != tuple(range(1, len(self.target_executions) + 1)):
            raise ArtifactError("attempted target order is not contiguous")
        if not self.target_executions:
            raise ArtifactError("completed search instance attempted no targets")
        if any(
            run.result.best_state.code_length != self.code_length
            for target in self.target_executions
            for run in target.runs
        ):
            raise ArtifactError("search run width differs from instance")

        successful_indices = [
            index
            for index, target in enumerate(self.target_executions)
            if target.success
        ]
        if len(successful_indices) > 1:
            raise ArtifactError("search continued across multiple successes")
        if successful_indices:
            if successful_indices[0] != len(self.target_executions) - 1:
                raise ArtifactError("search continued after first success")
        elif len(self.target_executions) != len(self.targets_planned):
            raise ArtifactError(
                "unsuccessful instance did not exhaust every planned target"
            )

    @property
    def successful_target_count(self) -> int:
        return sum(target.success for target in self.target_executions)

    @property
    def final_lower_bound(self) -> int:
        return self.accepted_lower_bound

    @property
    def final_upper_bound(self) -> int:
        successful = next(
            (target.target_r for target in self.target_executions if target.success),
            None,
        )
        return self.accepted_upper_bound if successful is None else successful

    @property
    def exact_optimum_established(self) -> bool:
        return self.final_lower_bound == self.final_upper_bound

    @property
    def upper_bound_improvement(self) -> int:
        return self.accepted_upper_bound - self.final_upper_bound

    @property
    def classification(self) -> ResultClassification:
        if self.mode == "exact_by_accepted_transfer":
            return "exact_by_accepted_transfer"
        if self.exact_optimum_established:
            return "exact_by_heuristic_witness"
        if self.upper_bound_improvement > 0:
            return "heuristic_upper_bound_improved"
        return "no_heuristic_improvement"


def _run_payload(
    execution: HeuristicRunExecution,
) -> dict[str, object]:
    result = execution.result
    checkpoint = result.checkpoint
    return {
        "accepted_moves": result.accepted_moves,
        "best_score": _score_payload(execution.best_score),
        "best_state_sha256": result.best_state.state_sha256(),
        "checkpoint_sha256": checkpoint.checkpoint_sha256(),
        "final_score": _score_payload(execution.final_score),
        "final_state_sha256": result.final_state.state_sha256(),
        "first_success_proposal": result.first_success_proposal,
        "initial_score": _score_payload(execution.initial_score),
        "initial_state_sha256": result.initial_state_hash,
        "initialisation_class": execution.initialisation_class,
        "initialisation_id": execution.initialisation_id,
        "initialisation_metadata": execution.initialisation_metadata,
        "kernel_config": search_kernel_config_payload(checkpoint.config),
        "kernel_config_sha256": search_kernel_config_sha256(checkpoint.config),
        "proposal_budget": checkpoint.config.proposal_budget,
        "proposals_executed": result.proposals_executed,
        "replacement_proposals": result.replacement_proposals,
        "restart_index": execution.restart_index,
        "run_order_within_target": execution.run_order_within_target,
        "schema_version": RUN_SCHEMA_VERSION,
        "seed": execution.seed,
        "stopping_reason": result.stopping_reason,
        "success": execution.success,
        "swap_proposals": result.swap_proposals,
        "target_r": checkpoint.target_r,
        "verification": _verification_payload(execution.verification),
    }


def _target_payload(
    execution: HeuristicTargetExecution,
) -> dict[str, object]:
    best = execution.best_run
    return {
        "best_initialisation_class": best.initialisation_class,
        "best_initialisation_id": best.initialisation_id,
        "best_restart_index": best.restart_index,
        "best_run_order": execution.best_run_order,
        "best_score": _score_payload(best.best_score),
        "best_seed": best.seed,
        "best_state_sha256": best.result.best_state.state_sha256(),
        "first_success_proposal": best.result.first_success_proposal,
        "negative_result_interpretation": (
            None if execution.success else NEGATIVE_RESULT_INTERPRETATION
        ),
        "run_count": len(execution.runs),
        "schema_version": TARGET_SCHEMA_VERSION,
        "success": execution.success,
        "target_order_within_instance": (execution.target_order_within_instance),
        "target_r": execution.target_r,
    }


def _instance_payload(
    execution: HeuristicInstanceExecution,
) -> dict[str, object]:
    return {
        "accepted_lower_bound": execution.accepted_lower_bound,
        "accepted_upper_bound": execution.accepted_upper_bound,
        "classification": execution.classification,
        "code_length": execution.code_length,
        "exact_optimum_established": (execution.exact_optimum_established),
        "execution_order": execution.execution_order,
        "final_lower_bound": execution.final_lower_bound,
        "final_upper_bound": execution.final_upper_bound,
        "graph_id": execution.graph_id,
        "mode": execution.mode,
        "negative_result_interpretation": (
            NEGATIVE_RESULT_INTERPRETATION
            if execution.classification == "no_heuristic_improvement"
            else None
        ),
        "schema_version": INSTANCE_SCHEMA_VERSION,
        "successful_target_count": execution.successful_target_count,
        "targets_attempted": len(execution.target_executions),
        "targets_planned": list(execution.targets_planned),
        "upper_bound_improvement": execution.upper_bound_improvement,
    }


def write_run_artifacts(
    run_root: Path,
    execution: HeuristicRunExecution,
) -> dict[str, str]:
    """Write all deterministic evidence for one complete search run."""
    if run_root.exists():
        raise FileExistsError(f"run destination exists: {run_root}")
    run_root.mkdir(parents=True)

    result = execution.result
    checkpoint = result.checkpoint
    try:
        atomic_write_text(
            run_root / "run.json",
            pretty_json_dumps(_run_payload(execution)),
        )
        atomic_write_bytes(
            run_root / "checkpoint.bin",
            checkpoint.to_bytes(),
        )
        atomic_write_bytes(
            run_root / "initial_codebook.npy",
            npy_bytes(checkpoint.initial_state.codebook),
        )
        atomic_write_bytes(
            run_root / "best_codebook.npy",
            npy_bytes(result.best_state.codebook),
        )
        atomic_write_bytes(
            run_root / "final_codebook.npy",
            npy_bytes(result.final_state.codebook),
        )
        atomic_write_bytes(
            run_root / "initial_edge_hamming.npy",
            npy_bytes(checkpoint.initial_scoring.edge_distances),
        )
        atomic_write_bytes(
            run_root / "best_edge_hamming.npy",
            npy_bytes(result.best_scoring.edge_distances),
        )
        atomic_write_bytes(
            run_root / "final_edge_hamming.npy",
            npy_bytes(result.final_scoring.edge_distances),
        )
        atomic_write_bytes(
            run_root / "trajectory.jsonl",
            _trajectory_bytes(checkpoint),
        )
    except Exception:
        shutil.rmtree(run_root, ignore_errors=True)
        raise

    return collect_file_hashes(run_root)


def load_run_artifacts(
    run_root: Path,
) -> HeuristicRunExecution:
    """Load and independently cross-check one preserved run package."""
    if not run_root.is_dir():
        raise ArtifactError(f"run root is not a directory: {run_root}")

    metadata_path = run_root / "run.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ArtifactError("could not read run metadata") from error
    if not isinstance(metadata, dict):
        raise ArtifactError("run metadata must be an object")
    if metadata.get("schema_version") != RUN_SCHEMA_VERSION:
        raise ArtifactError("unexpected run schema version")
    if metadata_path.read_text(encoding="utf-8") != pretty_json_dumps(metadata):
        raise ArtifactError("run metadata is not canonical")

    checkpoint = SearchKernelCheckpoint.read(run_root / "checkpoint.bin")
    if checkpoint.checkpoint_sha256() != metadata.get("checkpoint_sha256"):
        raise ArtifactError("checkpoint hash differs from run metadata")

    result = SearchKernelResult(
        seed=checkpoint.seed,
        initial_state_hash=checkpoint.initial_state.state_sha256(),
        initial_score=checkpoint.initial_scoring.score,
        final_state=checkpoint.current_state,
        final_scoring=checkpoint.current_scoring,
        best_state=checkpoint.best_state,
        best_scoring=checkpoint.best_scoring,
        steps=checkpoint.steps,
        first_success_proposal=checkpoint.first_success_proposal,
        stopping_reason=str(metadata["stopping_reason"]),
        swap_proposals=checkpoint.swap_proposals,
        replacement_proposals=checkpoint.replacement_proposals,
        accepted_moves=checkpoint.accepted_moves,
        checkpoint=checkpoint,
    )
    verification = _verification_from_payload(metadata["verification"])

    execution = HeuristicRunExecution(
        run_order_within_target=int(metadata["run_order_within_target"]),
        initialisation_class=str(metadata["initialisation_class"]),
        initialisation_id=str(metadata["initialisation_id"]),
        restart_index=int(metadata["restart_index"]),
        seed=int(metadata["seed"]),
        initialisation_metadata=_canonical_mapping(
            metadata["initialisation_metadata"],
            label="loaded initialisation metadata",
        ),
        result=result,
        verification=verification,
    )

    if _run_payload(execution) != metadata:
        raise ArtifactError("loaded run metadata differs from reconstructed run")

    expected_arrays = {
        "initial_codebook.npy": checkpoint.initial_state.codebook,
        "best_codebook.npy": result.best_state.codebook,
        "final_codebook.npy": result.final_state.codebook,
        "initial_edge_hamming.npy": (checkpoint.initial_scoring.edge_distances),
        "best_edge_hamming.npy": result.best_scoring.edge_distances,
        "final_edge_hamming.npy": result.final_scoring.edge_distances,
    }
    for filename, expected in expected_arrays.items():
        try:
            actual = np.load(
                run_root / filename,
                allow_pickle=False,
            )
        except (OSError, ValueError) as error:
            raise ArtifactError(
                f"could not load preserved array: {filename}"
            ) from error
        if not np.array_equal(actual, expected):
            raise ArtifactError(f"preserved array differs from checkpoint: {filename}")

    if (run_root / "trajectory.jsonl").read_bytes() != _trajectory_bytes(checkpoint):
        raise ArtifactError("preserved trajectory differs from checkpoint")

    return execution


def write_target_artifacts(
    target_root: Path,
    execution: HeuristicTargetExecution,
) -> dict[str, str]:
    """Write all run evidence and the selected incumbent for one target."""
    if target_root.exists():
        raise FileExistsError(f"target destination exists: {target_root}")
    target_root.mkdir(parents=True)

    try:
        runs_root = target_root / "runs"
        for run in execution.runs:
            write_run_artifacts(
                runs_root / f"run_{run.run_order_within_target:03d}",
                run,
            )

        atomic_write_text(
            target_root / "target.json",
            pretty_json_dumps(_target_payload(execution)),
        )
        atomic_write_bytes(
            target_root / "best_codebook.npy",
            npy_bytes(execution.best_run.result.best_state.codebook),
        )
        atomic_write_bytes(
            target_root / "best_edge_hamming.npy",
            npy_bytes(execution.best_run.result.best_scoring.edge_distances),
        )
    except Exception:
        shutil.rmtree(target_root, ignore_errors=True)
        raise

    return collect_file_hashes(target_root)


def write_instance_artifacts(
    output_root: Path,
    execution: HeuristicInstanceExecution,
) -> dict[str, str]:
    """Write one complete Stage 5 graph-length evidence package."""
    instance_root = output_root / execution.graph_id / f"m{execution.code_length}"
    if instance_root.exists():
        raise FileExistsError(f"instance destination exists: {instance_root}")
    instance_root.mkdir(parents=True)

    try:
        if execution.mode == "search_completed":
            for target in execution.target_executions:
                write_target_artifacts(
                    instance_root / "targets" / f"r{target.target_r}",
                    target,
                )
        else:
            transfer_root = instance_root / "transfer"
            transfer_root.mkdir()
            assert execution.transfer_witness is not None
            assert execution.transfer_metadata is not None
            atomic_write_bytes(
                transfer_root / "codebook.npy",
                npy_bytes(execution.transfer_witness.codebook),
            )
            atomic_write_text(
                transfer_root / "transfer.json",
                pretty_json_dumps(
                    {
                        "codebook_state_sha256": (
                            execution.transfer_witness.state_sha256()
                        ),
                        "metadata": execution.transfer_metadata,
                    }
                ),
            )

        atomic_write_text(
            instance_root / "instance.json",
            pretty_json_dumps(_instance_payload(execution)),
        )
    except Exception:
        shutil.rmtree(instance_root, ignore_errors=True)
        raise

    return collect_file_hashes(instance_root)


def _csv_bytes(
    fields: tuple[str, ...],
    rows: Sequence[Mapping[str, object]],
) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fields,
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(row))
    return buffer.getvalue().encode("utf-8")


def _run_table_row(
    instance: HeuristicInstanceExecution,
    target: HeuristicTargetExecution,
    run: HeuristicRunExecution,
) -> dict[str, object]:
    result = run.result
    return {
        "execution_order": instance.execution_order,
        "graph_id": instance.graph_id,
        "code_length": instance.code_length,
        "target_order_within_instance": (target.target_order_within_instance),
        "target_r": target.target_r,
        "run_order_within_target": run.run_order_within_target,
        "initialisation_class": run.initialisation_class,
        "initialisation_id": run.initialisation_id,
        "restart_index": run.restart_index,
        "seed": run.seed,
        "kernel_config_sha256": search_kernel_config_sha256(result.checkpoint.config),
        "proposal_budget": result.checkpoint.config.proposal_budget,
        "proposals_executed": result.proposals_executed,
        "swap_proposals": result.swap_proposals,
        "replacement_proposals": result.replacement_proposals,
        "accepted_moves": result.accepted_moves,
        "stopping_reason": result.stopping_reason,
        "success": run.success,
        "first_success_proposal": (
            ""
            if result.first_success_proposal is None
            else result.first_success_proposal
        ),
        **_score_columns("initial", run.initial_score),
        **_score_columns("best", run.best_score),
        **_score_columns("final", run.final_score),
        "initial_state_sha256": result.initial_state_hash,
        "best_state_sha256": result.best_state.state_sha256(),
        "final_state_sha256": result.final_state.state_sha256(),
        "checkpoint_sha256": result.checkpoint.checkpoint_sha256(),
    }


def _target_table_row(
    instance: HeuristicInstanceExecution,
    target: HeuristicTargetExecution,
) -> dict[str, object]:
    best = target.best_run
    return {
        "execution_order": instance.execution_order,
        "graph_id": instance.graph_id,
        "code_length": instance.code_length,
        "target_order_within_instance": (target.target_order_within_instance),
        "target_r": target.target_r,
        "run_count": len(target.runs),
        "success": target.success,
        "best_run_order": target.best_run_order,
        "best_initialisation_class": best.initialisation_class,
        "best_initialisation_id": best.initialisation_id,
        "best_restart_index": best.restart_index,
        "best_seed": best.seed,
        **_score_columns("best", best.best_score),
        "first_success_proposal": (
            ""
            if best.result.first_success_proposal is None
            else best.result.first_success_proposal
        ),
        "negative_result_interpretation": (
            "" if target.success else NEGATIVE_RESULT_INTERPRETATION
        ),
    }


def _instance_table_row(
    instance: HeuristicInstanceExecution,
) -> dict[str, object]:
    return {
        "execution_order": instance.execution_order,
        "graph_id": instance.graph_id,
        "code_length": instance.code_length,
        "mode": instance.mode,
        "classification": instance.classification,
        "accepted_lower_bound": instance.accepted_lower_bound,
        "accepted_upper_bound": instance.accepted_upper_bound,
        "final_lower_bound": instance.final_lower_bound,
        "final_upper_bound": instance.final_upper_bound,
        "targets_planned": len(instance.targets_planned),
        "targets_attempted": len(instance.target_executions),
        "successful_target_count": instance.successful_target_count,
        "exact_optimum_established": (instance.exact_optimum_established),
        "upper_bound_improvement": instance.upper_bound_improvement,
        "negative_result_interpretation": (
            NEGATIVE_RESULT_INTERPRETATION
            if instance.classification == "no_heuristic_improvement"
            else ""
        ),
    }


def _exact_table_row(
    instance: HeuristicInstanceExecution,
) -> dict[str, object]:
    if not instance.exact_optimum_established:
        raise ArtifactError("non-exact instance cannot enter exact table")
    return {
        "execution_order": instance.execution_order,
        "graph_id": instance.graph_id,
        "code_length": instance.code_length,
        "exact_l_star_free": instance.final_upper_bound,
        "established_by": instance.classification,
    }


def write_stage5_tables(
    table_root: Path,
    *,
    run_id: str,
    executions: tuple[HeuristicInstanceExecution, ...],
) -> dict[str, str]:
    """Write the frozen deterministic Stage 5 CSV table set."""
    if not run_id:
        raise ArtifactError("run identifier must be non-empty")
    table_root.mkdir(parents=True, exist_ok=True)

    run_rows = [
        _run_table_row(instance, target, run)
        for instance in executions
        for target in instance.target_executions
        for run in target.runs
    ]
    target_rows = [
        _target_table_row(instance, target)
        for instance in executions
        for target in instance.target_executions
    ]
    instance_rows = [_instance_table_row(instance) for instance in executions]
    exact_rows = [
        _exact_table_row(instance)
        for instance in executions
        if instance.exact_optimum_established
    ]

    table_payloads = {
        f"{run_id}{RUN_TABLE_SUFFIX}": _csv_bytes(
            RUN_FIELDS,
            run_rows,
        ),
        f"{run_id}{TARGET_TABLE_SUFFIX}": _csv_bytes(
            TARGET_FIELDS,
            target_rows,
        ),
        f"{run_id}{INSTANCE_TABLE_SUFFIX}": _csv_bytes(
            INSTANCE_FIELDS,
            instance_rows,
        ),
        f"{run_id}{EXACT_TABLE_SUFFIX}": _csv_bytes(
            EXACT_FIELDS,
            exact_rows,
        ),
    }

    for filename in table_payloads:
        if (table_root / filename).exists():
            raise FileExistsError(f"table destination exists: {table_root / filename}")

    try:
        for filename, data in sorted(table_payloads.items()):
            atomic_write_bytes(table_root / filename, data)
    except Exception:
        for filename in table_payloads:
            (table_root / filename).unlink(missing_ok=True)
        raise

    return {
        filename: sha256_bytes(data)
        for filename, data in sorted(table_payloads.items())
    }


def generate_stage5_artifacts(
    *,
    plan_sha256: str,
    configuration_sha256: str,
    executions: tuple[HeuristicInstanceExecution, ...],
    package_root: Path,
    table_root: Path,
    archive_path: Path,
    run_id: str,
) -> dict[str, object]:
    """Build a complete deterministic Stage 5 package and archive."""
    if not _valid_sha256(plan_sha256):
        raise ArtifactError("invalid Stage 5 plan hash")
    if not _valid_sha256(configuration_sha256):
        raise ArtifactError("invalid Stage 5 configuration hash")
    if not run_id:
        raise ArtifactError("run identifier must be non-empty")
    if package_root.exists():
        raise FileExistsError(f"package destination exists: {package_root}")
    if archive_path.exists():
        raise FileExistsError(f"archive destination exists: {archive_path}")
    if not executions:
        raise ArtifactError("Stage 5 package cannot be empty")
    if tuple(execution.execution_order for execution in executions) != tuple(
        range(1, len(executions) + 1)
    ):
        raise ArtifactError("instance execution order is not contiguous")
    if len(
        {(execution.graph_id, execution.code_length) for execution in executions}
    ) != len(executions):
        raise ArtifactError("duplicate graph-length execution")

    package_root.mkdir(parents=True)
    table_names = (
        f"{run_id}{RUN_TABLE_SUFFIX}",
        f"{run_id}{TARGET_TABLE_SUFFIX}",
        f"{run_id}{INSTANCE_TABLE_SUFFIX}",
        f"{run_id}{EXACT_TABLE_SUFFIX}",
    )

    try:
        for execution in executions:
            write_instance_artifacts(package_root, execution)

        table_files = write_stage5_tables(
            table_root,
            run_id=run_id,
            executions=executions,
        )
        deterministic_files = collect_file_hashes(package_root)
        package_tree_sha256 = sha256_bytes(
            canonical_json_dumps(deterministic_files).encode("utf-8")
        )
        table_set_sha256 = sha256_bytes(
            canonical_json_dumps(table_files).encode("utf-8")
        )
        classification_counts = {
            name: sum(execution.classification == name for execution in executions)
            for name in (
                "exact_by_accepted_transfer",
                "exact_by_heuristic_witness",
                "heuristic_upper_bound_improved",
                "no_heuristic_improvement",
            )
        }
        run_count = sum(
            len(target.runs)
            for execution in executions
            for target in execution.target_executions
        )
        target_count_attempted = sum(
            len(execution.target_executions) for execution in executions
        )

        package_metadata = {
            "classification_counts": classification_counts,
            "configuration_sha256": configuration_sha256,
            "deterministic_file_count_without_package_metadata": len(
                deterministic_files
            ),
            "deterministic_files": deterministic_files,
            "exact_optimum_count": sum(
                execution.exact_optimum_established for execution in executions
            ),
            "instance_count": len(executions),
            "negative_result_interpretation": (NEGATIVE_RESULT_INTERPRETATION),
            "package_tree_sha256": package_tree_sha256,
            "plan_sha256": plan_sha256,
            "run_count": run_count,
            "run_id": run_id,
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "stage": 5,
            "stage_name": "Scalable Free-Codebook Heuristic Search",
            "table_file_count": len(table_files),
            "table_files": table_files,
            "table_set_sha256": table_set_sha256,
            "target_count_attempted": target_count_attempted,
        }
        atomic_write_text(
            package_root / "package_metadata.json",
            pretty_json_dumps(package_metadata),
        )

        with tempfile.TemporaryDirectory(prefix=f"{run_id}-archive-") as temporary_name:
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
            write_deterministic_tar_gz(
                archive_root,
                archive_path,
            )

        all_files = collect_file_hashes(package_root)
        return {
            "archive_member_count": len(all_files) + len(table_files),
            "archive_sha256": sha256_file(archive_path),
            "classification_counts": classification_counts,
            "exact_optimum_count": sum(
                execution.exact_optimum_established for execution in executions
            ),
            "file_count": len(all_files),
            "files": all_files,
            "instance_count": len(executions),
            "package_tree_sha256": package_tree_sha256,
            "run_count": run_count,
            "table_file_count": len(table_files),
            "table_files": table_files,
            "table_set_sha256": table_set_sha256,
            "target_count_attempted": target_count_attempted,
        }
    except Exception:
        shutil.rmtree(package_root, ignore_errors=True)
        for filename in table_names:
            (table_root / filename).unlink(missing_ok=True)
        archive_path.unlink(missing_ok=True)
        raise

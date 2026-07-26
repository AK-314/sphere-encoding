"""Replayable proposal, acceptance, checkpoint, and resume kernel."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

from sphere_encoding.config import canonical_json_dumps
from sphere_encoding.heuristic.moves import (
    Move,
    ReplacementMove,
    SwapMove,
    apply_evaluated_move,
    evaluate_move,
)
from sphere_encoding.heuristic.schedule import (
    AcceptanceDecision,
    LinearTemperatureSchedule,
    acceptance_decision,
)
from sphere_encoding.heuristic.scoring import (
    IncrementalScoringState,
    ThresholdScore,
    canonical_edges_array,
)
from sphere_encoding.heuristic.state import (
    SearchState,
    SearchStateError,
)

_CHECKPOINT_MAGIC: Final = b"SPHERE_ENCODING_HEURISTIC_SEARCH_CHECKPOINT_V1\n"
_CHECKPOINT_SCHEMA: Final = "sphere_encoding.heuristic.search_checkpoint.v1"


class SearchError(ValueError):
    """Raised when the deterministic search kernel is misconfigured."""


@dataclass(frozen=True, slots=True)
class SearchKernelConfig:
    """Deterministic local-search kernel settings."""

    proposal_budget: int
    swap_probability: float
    temperature_schedule: LinearTemperatureSchedule
    stop_on_feasible: bool

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_budget, int) or self.proposal_budget <= 0:
            raise SearchError("proposal budget must be a positive integer")
        if self.temperature_schedule.proposal_budget != self.proposal_budget:
            raise SearchError("temperature schedule and kernel proposal budgets differ")
        if (
            not isinstance(self.swap_probability, (int, float))
            or not math.isfinite(float(self.swap_probability))
            or not 0.0 <= self.swap_probability <= 1.0
        ):
            raise SearchError("swap probability must lie in [0, 1]")
        if not isinstance(self.stop_on_feasible, bool):
            raise SearchError("stop_on_feasible must be boolean")


@dataclass(frozen=True, slots=True)
class SearchStep:
    """One deterministic proposal, evaluation, and acceptance record."""

    proposal_index: int
    move: Move
    temperature: float
    acceptance: AcceptanceDecision
    score_before: ThresholdScore
    candidate_score: ThresholdScore
    score_after: ThresholdScore
    state_hash_before: str
    candidate_state_hash: str
    state_hash_after: str
    best_state_hash_after: str

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_index, int) or self.proposal_index < 0:
            raise SearchError("proposal index must be non-negative")
        if not isinstance(self.temperature, (int, float)) or not math.isfinite(
            float(self.temperature)
        ):
            raise SearchError("step temperature must be finite")
        if self.temperature < 0:
            raise SearchError("step temperature must be non-negative")

        hashes = (
            self.state_hash_before,
            self.candidate_state_hash,
            self.state_hash_after,
            self.best_state_hash_after,
        )
        if any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in hashes
        ):
            raise SearchError("step state hashes must be lowercase SHA-256 values")


def search_kernel_config_payload(
    config: SearchKernelConfig,
) -> dict[str, object]:
    """Return deterministic JSON-compatible kernel configuration."""
    return {
        "proposal_budget": config.proposal_budget,
        "stop_on_feasible": config.stop_on_feasible,
        "swap_probability": float(config.swap_probability),
        "temperature_schedule": {
            "end_temperature": float(config.temperature_schedule.end_temperature),
            "proposal_budget": config.temperature_schedule.proposal_budget,
            "start_temperature": float(config.temperature_schedule.start_temperature),
            "type": "linear",
        },
    }


def search_kernel_config_sha256(config: SearchKernelConfig) -> str:
    """Hash the deterministic kernel configuration."""
    return hashlib.sha256(
        canonical_json_dumps(search_kernel_config_payload(config)).encode("utf-8")
    ).hexdigest()


def search_edges_sha256(
    edges: npt.ArrayLike,
    *,
    vertex_count: int,
) -> str:
    """Hash canonical graph edges with shape and dtype metadata."""
    canonical = canonical_edges_array(
        edges,
        vertex_count=vertex_count,
    )
    header = canonical_json_dumps(
        {
            "dtype": "int64",
            "shape": list(canonical.shape),
        }
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(header)
    digest.update(b"\n")
    digest.update(canonical.tobytes(order="C"))
    return digest.hexdigest()


def _score_payload(score: ThresholdScore) -> dict[str, int]:
    return {
        "maximum_distance_edge_count": score.maximum_distance_edge_count,
        "maximum_excess": score.maximum_excess,
        "total_excess": score.total_excess,
        "total_local_hamming": score.total_local_hamming,
        "violation_count": score.violation_count,
    }


def _score_from_payload(payload: object) -> ThresholdScore:
    if not isinstance(payload, dict):
        raise SearchError("checkpoint score payload must be an object")
    try:
        return ThresholdScore(
            violation_count=int(payload["violation_count"]),
            total_excess=int(payload["total_excess"]),
            maximum_excess=int(payload["maximum_excess"]),
            maximum_distance_edge_count=int(payload["maximum_distance_edge_count"]),
            total_local_hamming=int(payload["total_local_hamming"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SearchError("invalid checkpoint score payload") from error


def _scoring_payload(
    scoring: IncrementalScoringState,
) -> dict[str, object]:
    return {
        "edge_distances": [int(value) for value in scoring.edge_distances.tolist()],
        "score": _score_payload(scoring.score),
        "target_r": scoring.target_r,
    }


def _scoring_from_payload(payload: object) -> IncrementalScoringState:
    if not isinstance(payload, dict):
        raise SearchError("checkpoint scoring payload must be an object")
    try:
        target_r = int(payload["target_r"])
        distances = np.asarray(
            payload["edge_distances"],
            dtype=np.int64,
        )
        score = _score_from_payload(payload["score"])
        return IncrementalScoringState(
            target_r=target_r,
            edge_distances=distances,
            score=score,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SearchError("invalid checkpoint scoring payload") from error


def _move_payload(move: Move) -> dict[str, object]:
    if isinstance(move, SwapMove):
        return {
            "first_vertex": move.first_vertex,
            "move_type": "swap",
            "second_vertex": move.second_vertex,
        }
    return {
        "move_type": "replacement",
        "new_codeword_id": move.new_codeword_id,
        "vertex": move.vertex,
    }


def _move_from_payload(payload: object) -> Move:
    if not isinstance(payload, dict):
        raise SearchError("checkpoint move payload must be an object")
    try:
        move_type = str(payload["move_type"])
        if move_type == "swap":
            return SwapMove(
                int(payload["first_vertex"]),
                int(payload["second_vertex"]),
            )
        if move_type == "replacement":
            return ReplacementMove(
                vertex=int(payload["vertex"]),
                new_codeword_id=int(payload["new_codeword_id"]),
            )
    except (KeyError, TypeError, ValueError) as error:
        raise SearchError("invalid checkpoint move payload") from error
    raise SearchError(f"unrecognised checkpoint move type: {move_type!r}")


def _acceptance_payload(
    decision: AcceptanceDecision,
) -> dict[str, object]:
    return {
        "accepted": decision.accepted,
        "first_difference_index": decision.first_difference_index,
        "first_difference_magnitude": decision.first_difference_magnitude,
        "probability": decision.probability,
        "random_draw": decision.random_draw,
        "relation": decision.relation,
    }


def _acceptance_from_payload(payload: object) -> AcceptanceDecision:
    if not isinstance(payload, dict):
        raise SearchError("checkpoint acceptance payload must be an object")
    try:
        relation = str(payload["relation"])
        if relation not in {"improving", "equal", "worsening"}:
            raise SearchError("invalid checkpoint acceptance relation")
        accepted = payload["accepted"]
        if not isinstance(accepted, bool):
            raise SearchError("checkpoint accepted field must be Boolean")
        difference_index_value = payload["first_difference_index"]
        difference_index = (
            None if difference_index_value is None else int(difference_index_value)
        )
        return AcceptanceDecision(
            accepted=accepted,
            relation=relation,
            probability=float(payload["probability"]),
            random_draw=float(payload["random_draw"]),
            first_difference_index=difference_index,
            first_difference_magnitude=int(payload["first_difference_magnitude"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SearchError("invalid checkpoint acceptance payload") from error


def _step_payload(step: SearchStep) -> dict[str, object]:
    return {
        "acceptance": _acceptance_payload(step.acceptance),
        "best_state_hash_after": step.best_state_hash_after,
        "candidate_score": _score_payload(step.candidate_score),
        "candidate_state_hash": step.candidate_state_hash,
        "move": _move_payload(step.move),
        "proposal_index": step.proposal_index,
        "score_after": _score_payload(step.score_after),
        "score_before": _score_payload(step.score_before),
        "state_hash_after": step.state_hash_after,
        "state_hash_before": step.state_hash_before,
        "temperature": step.temperature,
    }


def _step_from_payload(payload: object) -> SearchStep:
    if not isinstance(payload, dict):
        raise SearchError("checkpoint step payload must be an object")
    try:
        return SearchStep(
            proposal_index=int(payload["proposal_index"]),
            move=_move_from_payload(payload["move"]),
            temperature=float(payload["temperature"]),
            acceptance=_acceptance_from_payload(payload["acceptance"]),
            score_before=_score_from_payload(payload["score_before"]),
            candidate_score=_score_from_payload(payload["candidate_score"]),
            score_after=_score_from_payload(payload["score_after"]),
            state_hash_before=str(payload["state_hash_before"]),
            candidate_state_hash=str(payload["candidate_state_hash"]),
            state_hash_after=str(payload["state_hash_after"]),
            best_state_hash_after=str(payload["best_state_hash_after"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SearchError("invalid checkpoint step payload") from error


def _config_from_payload(payload: object) -> SearchKernelConfig:
    if not isinstance(payload, dict):
        raise SearchError("checkpoint config payload must be an object")
    try:
        schedule_payload = payload["temperature_schedule"]
        if not isinstance(schedule_payload, dict):
            raise SearchError("checkpoint temperature schedule must be an object")
        if schedule_payload.get("type") != "linear":
            raise SearchError("checkpoint temperature schedule is not linear")
        stop_on_feasible = payload["stop_on_feasible"]
        if not isinstance(stop_on_feasible, bool):
            raise SearchError("checkpoint stop flag must be Boolean")

        schedule = LinearTemperatureSchedule(
            proposal_budget=int(schedule_payload["proposal_budget"]),
            start_temperature=float(schedule_payload["start_temperature"]),
            end_temperature=float(schedule_payload["end_temperature"]),
        )
        return SearchKernelConfig(
            proposal_budget=int(payload["proposal_budget"]),
            swap_probability=float(payload["swap_probability"]),
            temperature_schedule=schedule,
            stop_on_feasible=stop_on_feasible,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SearchError("invalid checkpoint config payload") from error


def _state_payload(state: SearchState) -> str:
    return state.to_bytes().hex()


def _state_from_payload(payload: object) -> SearchState:
    if not isinstance(payload, str):
        raise SearchError("checkpoint state payload must be hexadecimal text")
    try:
        raw = bytes.fromhex(payload)
        return SearchState.from_bytes(raw)
    except (ValueError, SearchStateError) as error:
        raise SearchError("invalid checkpoint state payload") from error


def _canonical_rng_state(
    state: object,
) -> dict[str, object]:
    if not isinstance(state, dict):
        raise SearchError("RNG state must be an object")
    try:
        encoded = canonical_json_dumps(state)
        decoded = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise SearchError("RNG state is not deterministic JSON") from error
    if not isinstance(decoded, dict):
        raise SearchError("canonical RNG state is not an object")
    if decoded.get("bit_generator") != "PCG64":
        raise SearchError("checkpoint RNG must use PCG64")
    return decoded


@dataclass(frozen=True, slots=True)
class SearchKernelCheckpoint:
    """Complete deterministic state required for exact search resumption."""

    schema_version: str
    seed: int
    target_r: int
    config: SearchKernelConfig
    edges_sha256: str
    initial_state: SearchState
    initial_scoring: IncrementalScoringState
    current_state: SearchState
    current_scoring: IncrementalScoringState
    best_state: SearchState
    best_scoring: IncrementalScoringState
    steps: tuple[SearchStep, ...]
    first_success_proposal: int | None
    swap_proposals: int
    replacement_proposals: int
    accepted_moves: int
    rng_state: dict[str, object]

    def __post_init__(self) -> None:
        if self.schema_version != _CHECKPOINT_SCHEMA:
            raise SearchError("unexpected checkpoint schema")
        if not isinstance(self.seed, int) or self.seed < 0:
            raise SearchError("checkpoint seed must be non-negative")
        if not isinstance(self.target_r, int) or self.target_r < 0:
            raise SearchError("checkpoint target must be non-negative")
        if len(self.edges_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.edges_sha256
        ):
            raise SearchError("checkpoint edge hash is invalid")

        state_shapes = {
            (
                state.vertex_count,
                state.code_length,
            )
            for state in (
                self.initial_state,
                self.current_state,
                self.best_state,
            )
        }
        if len(state_shapes) != 1:
            raise SearchError("checkpoint state dimensions differ")

        scoring_states = (
            self.initial_scoring,
            self.current_scoring,
            self.best_scoring,
        )
        if any(scoring.target_r != self.target_r for scoring in scoring_states):
            raise SearchError("checkpoint scoring target differs")
        if len({scoring.edge_count for scoring in scoring_states}) != 1:
            raise SearchError("checkpoint scoring edge counts differ")

        expected_indices = tuple(range(len(self.steps)))
        actual_indices = tuple(step.proposal_index for step in self.steps)
        if actual_indices != expected_indices:
            raise SearchError("checkpoint proposal indices are not contiguous")
        if len(self.steps) > self.config.proposal_budget:
            raise SearchError("checkpoint exceeds proposal budget")

        swap_count = sum(isinstance(step.move, SwapMove) for step in self.steps)
        replacement_count = sum(
            isinstance(step.move, ReplacementMove) for step in self.steps
        )
        accepted_count = sum(step.acceptance.accepted for step in self.steps)
        if self.swap_proposals != swap_count:
            raise SearchError("checkpoint swap count is inconsistent")
        if self.replacement_proposals != replacement_count:
            raise SearchError("checkpoint replacement count is inconsistent")
        if self.accepted_moves != accepted_count:
            raise SearchError("checkpoint accepted count is inconsistent")
        if swap_count + replacement_count != len(self.steps):
            raise SearchError("checkpoint move count is inconsistent")

        initial_hash = self.initial_state.state_sha256()
        current_hash = self.current_state.state_sha256()
        best_hash = self.best_state.state_sha256()

        if self.steps:
            if self.steps[0].state_hash_before != initial_hash:
                raise SearchError(
                    "checkpoint trajectory does not start at initial state"
                )
            for previous, following in zip(
                self.steps,
                self.steps[1:],
                strict=False,
            ):
                if previous.state_hash_after != following.state_hash_before:
                    raise SearchError("checkpoint state-hash chain is broken")
                if previous.score_after != following.score_before:
                    raise SearchError("checkpoint score chain is broken")
            if self.steps[-1].state_hash_after != current_hash:
                raise SearchError("checkpoint current state differs from trajectory")
            if self.steps[-1].score_after != self.current_scoring.score:
                raise SearchError("checkpoint current score differs from trajectory")
            if self.steps[-1].best_state_hash_after != best_hash:
                raise SearchError("checkpoint best state differs from trajectory")
        else:
            if current_hash != initial_hash:
                raise SearchError(
                    "zero-step checkpoint current state differs from initial"
                )
            if best_hash != initial_hash:
                raise SearchError(
                    "zero-step checkpoint best state differs from initial"
                )
            if self.current_scoring.score != self.initial_scoring.score:
                raise SearchError(
                    "zero-step checkpoint current score differs from initial"
                )
            if self.best_scoring.score != self.initial_scoring.score:
                raise SearchError(
                    "zero-step checkpoint best score differs from initial"
                )

        if self.best_scoring.score > self.current_scoring.score:
            raise SearchError("checkpoint best score is worse than current")

        expected_success: int | None
        if self.initial_scoring.score.is_feasible:
            expected_success = 0
        else:
            expected_success = next(
                (
                    step.proposal_index + 1
                    for step in self.steps
                    if step.score_after.is_feasible
                ),
                None,
            )
        if self.first_success_proposal != expected_success:
            raise SearchError("checkpoint first-success proposal is inconsistent")
        if (
            self.config.stop_on_feasible
            and self.first_success_proposal is not None
            and len(self.steps) != self.first_success_proposal
        ):
            raise SearchError("stop-on-feasible checkpoint continues after success")

        object.__setattr__(
            self,
            "rng_state",
            _canonical_rng_state(self.rng_state),
        )

    @property
    def proposals_executed(self) -> int:
        return len(self.steps)

    def payload(self) -> dict[str, object]:
        """Return deterministic JSON-compatible checkpoint content."""
        return {
            "accepted_moves": self.accepted_moves,
            "best_scoring": _scoring_payload(self.best_scoring),
            "best_state": _state_payload(self.best_state),
            "config": search_kernel_config_payload(self.config),
            "current_scoring": _scoring_payload(self.current_scoring),
            "current_state": _state_payload(self.current_state),
            "edges_sha256": self.edges_sha256,
            "first_success_proposal": self.first_success_proposal,
            "initial_scoring": _scoring_payload(self.initial_scoring),
            "initial_state": _state_payload(self.initial_state),
            "replacement_proposals": self.replacement_proposals,
            "rng_state": self.rng_state,
            "schema_version": self.schema_version,
            "seed": self.seed,
            "steps": [_step_payload(step) for step in self.steps],
            "swap_proposals": self.swap_proposals,
            "target_r": self.target_r,
        }

    def to_bytes(self) -> bytes:
        """Serialise the checkpoint canonically."""
        return (
            _CHECKPOINT_MAGIC
            + canonical_json_dumps(self.payload()).encode("utf-8")
            + b"\n"
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> SearchKernelCheckpoint:
        """Parse and fully validate a canonical checkpoint."""
        if not isinstance(data, bytes):
            raise SearchError("checkpoint input must be bytes")
        if not data.startswith(_CHECKPOINT_MAGIC):
            raise SearchError("checkpoint magic is missing or invalid")

        payload_bytes = data[len(_CHECKPOINT_MAGIC) :]
        if not payload_bytes.endswith(b"\n"):
            raise SearchError("checkpoint lacks its final newline")
        try:
            payload = json.loads(payload_bytes[:-1].decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise SearchError("checkpoint JSON is malformed") from error
        if not isinstance(payload, dict):
            raise SearchError("checkpoint payload must be an object")

        try:
            first_success_value = payload["first_success_proposal"]
            first_success = (
                None if first_success_value is None else int(first_success_value)
            )
            steps_payload = payload["steps"]
            if not isinstance(steps_payload, list):
                raise SearchError("checkpoint steps must be a list")

            checkpoint = cls(
                schema_version=str(payload["schema_version"]),
                seed=int(payload["seed"]),
                target_r=int(payload["target_r"]),
                config=_config_from_payload(payload["config"]),
                edges_sha256=str(payload["edges_sha256"]),
                initial_state=_state_from_payload(payload["initial_state"]),
                initial_scoring=_scoring_from_payload(payload["initial_scoring"]),
                current_state=_state_from_payload(payload["current_state"]),
                current_scoring=_scoring_from_payload(payload["current_scoring"]),
                best_state=_state_from_payload(payload["best_state"]),
                best_scoring=_scoring_from_payload(payload["best_scoring"]),
                steps=tuple(_step_from_payload(step) for step in steps_payload),
                first_success_proposal=first_success,
                swap_proposals=int(payload["swap_proposals"]),
                replacement_proposals=int(payload["replacement_proposals"]),
                accepted_moves=int(payload["accepted_moves"]),
                rng_state=_canonical_rng_state(payload["rng_state"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise SearchError("checkpoint payload is incomplete") from error

        if checkpoint.to_bytes() != data:
            raise SearchError("checkpoint serialisation is not canonical")
        return checkpoint

    def checkpoint_sha256(self) -> str:
        """Hash the exact canonical checkpoint bytes."""
        return hashlib.sha256(self.to_bytes()).hexdigest()

    def write(self, path: str | Path) -> None:
        """Write a checkpoint atomically."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_bytes()

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()

    @classmethod
    def read(cls, path: str | Path) -> SearchKernelCheckpoint:
        """Read and validate a checkpoint file."""
        try:
            data = Path(path).read_bytes()
        except OSError as error:
            raise SearchError("could not read search checkpoint") from error
        return cls.from_bytes(data)


@dataclass(frozen=True, slots=True)
class SearchKernelResult:
    """Complete result of a fixed-budget seeded kernel execution."""

    seed: int
    initial_state_hash: str
    initial_score: ThresholdScore
    final_state: SearchState
    final_scoring: IncrementalScoringState
    best_state: SearchState
    best_scoring: IncrementalScoringState
    steps: tuple[SearchStep, ...]
    first_success_proposal: int | None
    stopping_reason: str
    swap_proposals: int
    replacement_proposals: int
    accepted_moves: int
    checkpoint: SearchKernelCheckpoint

    def __post_init__(self) -> None:
        checkpoint = self.checkpoint
        if self.seed != checkpoint.seed:
            raise SearchError("result seed differs from checkpoint")
        if self.initial_state_hash != (checkpoint.initial_state.state_sha256()):
            raise SearchError("result initial state differs from checkpoint")
        if self.initial_score != checkpoint.initial_scoring.score:
            raise SearchError("result initial score differs from checkpoint")
        if self.final_state.to_bytes() != checkpoint.current_state.to_bytes():
            raise SearchError("result final state differs from checkpoint")
        if self.best_state.to_bytes() != checkpoint.best_state.to_bytes():
            raise SearchError("result best state differs from checkpoint")
        if self.final_scoring.score != checkpoint.current_scoring.score:
            raise SearchError("result final score differs from checkpoint")
        if self.best_scoring.score != checkpoint.best_scoring.score:
            raise SearchError("result best score differs from checkpoint")
        if self.steps != checkpoint.steps:
            raise SearchError("result trajectory differs from checkpoint")
        if self.first_success_proposal != (checkpoint.first_success_proposal):
            raise SearchError("result success point differs from checkpoint")
        if self.swap_proposals != checkpoint.swap_proposals:
            raise SearchError("result swap count differs from checkpoint")
        if self.replacement_proposals != (checkpoint.replacement_proposals):
            raise SearchError("result replacement count differs from checkpoint")
        if self.accepted_moves != checkpoint.accepted_moves:
            raise SearchError("result accepted count differs from checkpoint")

    @property
    def proposals_executed(self) -> int:
        return len(self.steps)

    @property
    def success(self) -> bool:
        return self.first_success_proposal is not None


def propose_move(
    state: SearchState,
    rng: np.random.Generator,
    *,
    swap_probability: float,
) -> Move:
    """Draw one move under a fixed replayable proposal distribution."""
    if state.vertex_count < 2 and swap_probability > 0:
        raise SearchError("swap proposals require at least two vertices")
    if state.unused_codeword_count == 0 and swap_probability < 1:
        raise SearchError("replacement proposals require at least one unused codeword")

    selector = float(rng.random())
    if selector < swap_probability:
        first = int(rng.integers(state.vertex_count))
        second_reduced = int(rng.integers(state.vertex_count - 1))
        second = second_reduced if second_reduced < first else second_reduced + 1
        first, second = sorted((first, second))
        return SwapMove(first, second)

    vertex = int(rng.integers(state.vertex_count))
    unused_index = int(rng.integers(state.unused_codeword_count))
    return ReplacementMove(
        vertex=vertex,
        new_codeword_id=state.unused_codeword_id_at(unused_index),
    )


def _new_rng(seed: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(seed))


def _restored_rng(
    state: dict[str, object],
) -> np.random.Generator:
    rng = _new_rng(0)
    try:
        rng.bit_generator.state = _canonical_rng_state(state)
    except (TypeError, ValueError) as error:
        raise SearchError("checkpoint RNG state cannot be restored") from error
    return rng


def _build_checkpoint(
    *,
    seed: int,
    target_r: int,
    config: SearchKernelConfig,
    edges_sha256: str,
    initial_state: SearchState,
    initial_scoring: IncrementalScoringState,
    current_state: SearchState,
    current_scoring: IncrementalScoringState,
    best_state: SearchState,
    best_scoring: IncrementalScoringState,
    steps: tuple[SearchStep, ...],
    first_success_proposal: int | None,
    swap_proposals: int,
    replacement_proposals: int,
    accepted_moves: int,
    rng: np.random.Generator,
) -> SearchKernelCheckpoint:
    return SearchKernelCheckpoint(
        schema_version=_CHECKPOINT_SCHEMA,
        seed=seed,
        target_r=target_r,
        config=config,
        edges_sha256=edges_sha256,
        initial_state=SearchState.from_codebook(initial_state.codebook),
        initial_scoring=initial_scoring,
        current_state=SearchState.from_codebook(current_state.codebook),
        current_scoring=current_scoring,
        best_state=SearchState.from_codebook(best_state.codebook),
        best_scoring=best_scoring,
        steps=steps,
        first_success_proposal=first_success_proposal,
        swap_proposals=swap_proposals,
        replacement_proposals=replacement_proposals,
        accepted_moves=accepted_moves,
        rng_state=_canonical_rng_state(rng.bit_generator.state),
    )


def _result_from_checkpoint(
    checkpoint: SearchKernelCheckpoint,
    *,
    stopping_reason: str,
) -> SearchKernelResult:
    return SearchKernelResult(
        seed=checkpoint.seed,
        initial_state_hash=checkpoint.initial_state.state_sha256(),
        initial_score=checkpoint.initial_scoring.score,
        final_state=checkpoint.current_state,
        final_scoring=checkpoint.current_scoring,
        best_state=checkpoint.best_state,
        best_scoring=checkpoint.best_scoring,
        steps=checkpoint.steps,
        first_success_proposal=checkpoint.first_success_proposal,
        stopping_reason=stopping_reason,
        swap_proposals=checkpoint.swap_proposals,
        replacement_proposals=checkpoint.replacement_proposals,
        accepted_moves=checkpoint.accepted_moves,
        checkpoint=checkpoint,
    )


def run_search_kernel(
    initial_state: SearchState,
    edges: npt.ArrayLike,
    *,
    target_r: int,
    seed: int,
    config: SearchKernelConfig,
    resume_from: SearchKernelCheckpoint | None = None,
    stop_after_proposals: int | None = None,
) -> SearchKernelResult:
    """Execute or exactly resume a deterministic search kernel."""
    if not isinstance(seed, int) or seed < 0:
        raise SearchError("seed must be a non-negative integer")
    if not isinstance(target_r, int) or target_r < 0:
        raise SearchError("target threshold must be non-negative")

    canonical_edges = canonical_edges_array(
        edges,
        vertex_count=initial_state.vertex_count,
    )
    edges_hash = search_edges_sha256(
        canonical_edges,
        vertex_count=initial_state.vertex_count,
    )

    if resume_from is None:
        rng = _new_rng(seed)
        frozen_initial_state = SearchState.from_codebook(initial_state.codebook)
        initial_scoring = IncrementalScoringState.from_search_state(
            frozen_initial_state,
            canonical_edges,
            target_r,
        )
        current_state = SearchState.from_codebook(frozen_initial_state.codebook)
        current_scoring = initial_scoring
        best_state = SearchState.from_codebook(frozen_initial_state.codebook)
        best_scoring = initial_scoring
        steps: list[SearchStep] = []
        first_success = 0 if initial_scoring.score.is_feasible else None
        swap_proposals = 0
        replacement_proposals = 0
        accepted_moves = 0
    else:
        if resume_from.seed != seed:
            raise SearchError("resume seed differs from checkpoint")
        if resume_from.target_r != target_r:
            raise SearchError("resume target differs from checkpoint")
        if resume_from.config != config:
            raise SearchError("resume configuration differs from checkpoint")
        if resume_from.edges_sha256 != edges_hash:
            raise SearchError("resume graph differs from checkpoint")
        if resume_from.initial_state.to_bytes() != initial_state.to_bytes():
            raise SearchError("resume initial state differs from checkpoint")

        rng = _restored_rng(resume_from.rng_state)
        frozen_initial_state = resume_from.initial_state
        initial_scoring = resume_from.initial_scoring
        current_state = resume_from.current_state
        current_scoring = resume_from.current_scoring
        best_state = resume_from.best_state
        best_scoring = resume_from.best_scoring
        steps = list(resume_from.steps)
        first_success = resume_from.first_success_proposal
        swap_proposals = resume_from.swap_proposals
        replacement_proposals = resume_from.replacement_proposals
        accepted_moves = resume_from.accepted_moves

    current_count = len(steps)
    if stop_after_proposals is None:
        proposal_limit = config.proposal_budget
    else:
        if (
            not isinstance(stop_after_proposals, int)
            or stop_after_proposals < current_count
            or stop_after_proposals > config.proposal_budget
        ):
            raise SearchError(
                "stop_after_proposals must lie between the current "
                "proposal count and the total budget"
            )
        proposal_limit = stop_after_proposals

    if first_success == 0 and config.stop_on_feasible:
        checkpoint = _build_checkpoint(
            seed=seed,
            target_r=target_r,
            config=config,
            edges_sha256=edges_hash,
            initial_state=frozen_initial_state,
            initial_scoring=initial_scoring,
            current_state=current_state,
            current_scoring=current_scoring,
            best_state=best_state,
            best_scoring=best_scoring,
            steps=tuple(steps),
            first_success_proposal=first_success,
            swap_proposals=swap_proposals,
            replacement_proposals=replacement_proposals,
            accepted_moves=accepted_moves,
            rng=rng,
        )
        return _result_from_checkpoint(
            checkpoint,
            stopping_reason="initial_state_feasible",
        )

    if first_success is not None and config.stop_on_feasible:
        checkpoint = _build_checkpoint(
            seed=seed,
            target_r=target_r,
            config=config,
            edges_sha256=edges_hash,
            initial_state=frozen_initial_state,
            initial_scoring=initial_scoring,
            current_state=current_state,
            current_scoring=current_scoring,
            best_state=best_state,
            best_scoring=best_scoring,
            steps=tuple(steps),
            first_success_proposal=first_success,
            swap_proposals=swap_proposals,
            replacement_proposals=replacement_proposals,
            accepted_moves=accepted_moves,
            rng=rng,
        )
        return _result_from_checkpoint(
            checkpoint,
            stopping_reason="target_feasible",
        )

    reached_feasible = False

    for proposal_index in range(current_count, proposal_limit):
        state_hash_before = current_state.state_sha256()
        score_before = current_scoring.score

        move = propose_move(
            current_state,
            rng,
            swap_probability=config.swap_probability,
        )
        if isinstance(move, SwapMove):
            swap_proposals += 1
        else:
            replacement_proposals += 1

        evaluation = evaluate_move(
            current_state,
            canonical_edges,
            current_scoring,
            move,
        )
        candidate_state, candidate_scoring = apply_evaluated_move(
            current_state,
            current_scoring,
            evaluation,
        )
        candidate_hash = candidate_state.state_sha256()

        temperature = config.temperature_schedule.temperature_at(proposal_index)
        random_draw = float(rng.random())
        decision = acceptance_decision(
            score_before,
            candidate_scoring.score,
            temperature=temperature,
            random_draw=random_draw,
        )

        if decision.accepted:
            current_state = candidate_state
            current_scoring = candidate_scoring
            accepted_moves += 1

        if current_scoring.score < best_scoring.score:
            best_state = SearchState.from_codebook(current_state.codebook)
            best_scoring = current_scoring

        if first_success is None and current_scoring.score.is_feasible:
            first_success = proposal_index + 1

        steps.append(
            SearchStep(
                proposal_index=proposal_index,
                move=move,
                temperature=temperature,
                acceptance=decision,
                score_before=score_before,
                candidate_score=candidate_scoring.score,
                score_after=current_scoring.score,
                state_hash_before=state_hash_before,
                candidate_state_hash=candidate_hash,
                state_hash_after=current_state.state_sha256(),
                best_state_hash_after=best_state.state_sha256(),
            )
        )

        if first_success is not None and config.stop_on_feasible:
            reached_feasible = True
            break

    checkpoint = _build_checkpoint(
        seed=seed,
        target_r=target_r,
        config=config,
        edges_sha256=edges_hash,
        initial_state=frozen_initial_state,
        initial_scoring=initial_scoring,
        current_state=current_state,
        current_scoring=current_scoring,
        best_state=best_state,
        best_scoring=best_scoring,
        steps=tuple(steps),
        first_success_proposal=first_success,
        swap_proposals=swap_proposals,
        replacement_proposals=replacement_proposals,
        accepted_moves=accepted_moves,
        rng=rng,
    )

    if reached_feasible:
        stopping_reason = "target_feasible"
    elif checkpoint.proposals_executed == config.proposal_budget:
        stopping_reason = "proposal_budget_exhausted"
    else:
        stopping_reason = "checkpoint_reached"

    return _result_from_checkpoint(
        checkpoint,
        stopping_reason=stopping_reason,
    )

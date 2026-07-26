"""Replayable proposal and acceptance kernel for Stage 5 calibration."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

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
from sphere_encoding.heuristic.state import SearchState


class SearchError(ValueError):
    """Raised when the deterministic search kernel is misconfigured."""


@dataclass(frozen=True, slots=True)
class SearchKernelConfig:
    """Non-definitive deterministic local-search kernel settings."""

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
            or not 0.0 <= self.swap_probability <= 1.0
        ):
            raise SearchError("swap probability must lie in [0, 1]")
        if not isinstance(self.stop_on_feasible, bool):
            raise SearchError("stop_on_feasible must be boolean")


@dataclass(frozen=True, slots=True)
class SearchStep:
    """One deterministic proposal, evaluation and acceptance record."""

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


def run_search_kernel(
    initial_state: SearchState,
    edges: npt.ArrayLike,
    *,
    target_r: int,
    seed: int,
    config: SearchKernelConfig,
) -> SearchKernelResult:
    """Execute a deterministic proposal-indexed search kernel."""
    if not isinstance(seed, int) or seed < 0:
        raise SearchError("seed must be a non-negative integer")

    canonical_edges = canonical_edges_array(
        edges,
        vertex_count=initial_state.vertex_count,
    )
    rng = np.random.Generator(np.random.PCG64(seed))

    current_state = SearchState.from_codebook(initial_state.codebook)
    current_scoring = IncrementalScoringState.from_search_state(
        current_state,
        canonical_edges,
        target_r,
    )
    best_state = SearchState.from_codebook(current_state.codebook)
    best_scoring = current_scoring

    initial_hash = current_state.state_sha256()
    first_success = 0 if current_scoring.score.is_feasible else None

    if first_success == 0 and config.stop_on_feasible:
        return SearchKernelResult(
            seed=seed,
            initial_state_hash=initial_hash,
            initial_score=current_scoring.score,
            final_state=current_state,
            final_scoring=current_scoring,
            best_state=best_state,
            best_scoring=best_scoring,
            steps=(),
            first_success_proposal=0,
            stopping_reason="initial_state_feasible",
            swap_proposals=0,
            replacement_proposals=0,
            accepted_moves=0,
        )

    steps: list[SearchStep] = []
    swap_proposals = 0
    replacement_proposals = 0
    accepted_moves = 0
    stopping_reason = "proposal_budget_exhausted"

    for proposal_index in range(config.proposal_budget):
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
            stopping_reason = "target_feasible"
            break

    return SearchKernelResult(
        seed=seed,
        initial_state_hash=initial_hash,
        initial_score=IncrementalScoringState.from_search_state(
            initial_state,
            canonical_edges,
            target_r,
        ).score,
        final_state=current_state,
        final_scoring=current_scoring,
        best_state=best_state,
        best_scoring=best_scoring,
        steps=tuple(steps),
        first_success_proposal=first_success,
        stopping_reason=stopping_reason,
        swap_proposals=swap_proposals,
        replacement_proposals=replacement_proposals,
        accepted_moves=accepted_moves,
    )

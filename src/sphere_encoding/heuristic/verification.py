"""Independent deterministic replay verification for Stage 5 searches."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from sphere_encoding.heuristic.moves import (
    ReplacementMove,
    SwapMove,
    apply_evaluated_move,
    evaluate_move,
)
from sphere_encoding.heuristic.schedule import acceptance_decision
from sphere_encoding.heuristic.scoring import (
    IncrementalScoringState,
    canonical_edges_array,
)
from sphere_encoding.heuristic.search import (
    SearchKernelConfig,
    SearchKernelResult,
    search_edges_sha256,
)
from sphere_encoding.heuristic.state import SearchState


class VerificationError(ValueError):
    """Raised when a stored search result fails exact replay."""


@dataclass(frozen=True, slots=True)
class SearchVerificationReport:
    """Deterministic replay and integrity diagnostics."""

    proposals_verified: int
    swap_proposals_verified: int
    replacement_proposals_verified: int
    accepted_moves_verified: int
    first_success_proposal: int | None
    final_state_sha256: str
    best_state_sha256: str
    final_score: tuple[int, int, int, int, int]
    best_score: tuple[int, int, int, int, int]
    stopping_reason: str


def verify_search_result(
    result: SearchKernelResult,
    edges: npt.ArrayLike,
    *,
    target_r: int,
    config: SearchKernelConfig,
) -> SearchVerificationReport:
    """Replay every stored move and decision from the initial state."""
    checkpoint = result.checkpoint
    if checkpoint.target_r != target_r:
        raise VerificationError("verification target differs from result")
    if checkpoint.config != config:
        raise VerificationError("verification configuration differs from result")

    canonical_edges = canonical_edges_array(
        edges,
        vertex_count=checkpoint.initial_state.vertex_count,
    )
    edge_hash = search_edges_sha256(
        canonical_edges,
        vertex_count=checkpoint.initial_state.vertex_count,
    )
    if edge_hash != checkpoint.edges_sha256:
        raise VerificationError("verification graph differs from result")

    current_state = SearchState.from_codebook(checkpoint.initial_state.codebook)
    current_scoring = IncrementalScoringState.from_search_state(
        current_state,
        canonical_edges,
        target_r,
    )
    if current_scoring.score != checkpoint.initial_scoring.score:
        raise VerificationError("initial score does not recompute")
    np.testing.assert_array_equal(
        current_scoring.edge_distances,
        checkpoint.initial_scoring.edge_distances,
    )

    best_state = SearchState.from_codebook(current_state.codebook)
    best_scoring = current_scoring
    first_success = 0 if current_scoring.score.is_feasible else None
    swap_count = 0
    replacement_count = 0
    accepted_count = 0

    for expected_index, step in enumerate(result.steps):
        if step.proposal_index != expected_index:
            raise VerificationError("proposal order is not contiguous")
        if step.state_hash_before != current_state.state_sha256():
            raise VerificationError("state hash before proposal differs")
        if step.score_before != current_scoring.score:
            raise VerificationError("score before proposal differs")

        expected_temperature = config.temperature_schedule.temperature_at(
            expected_index
        )
        if step.temperature != expected_temperature:
            raise VerificationError("proposal temperature differs")

        if isinstance(step.move, SwapMove):
            swap_count += 1
        elif isinstance(step.move, ReplacementMove):
            replacement_count += 1
        else:
            raise VerificationError("stored move type is unsupported")

        evaluation = evaluate_move(
            current_state,
            canonical_edges,
            current_scoring,
            step.move,
        )
        candidate_state, candidate_scoring = apply_evaluated_move(
            current_state,
            current_scoring,
            evaluation,
        )

        if step.candidate_state_hash != candidate_state.state_sha256():
            raise VerificationError("candidate state hash differs")
        if step.candidate_score != candidate_scoring.score:
            raise VerificationError("candidate score differs")

        expected_decision = acceptance_decision(
            current_scoring.score,
            candidate_scoring.score,
            temperature=expected_temperature,
            random_draw=step.acceptance.random_draw,
        )
        if step.acceptance != expected_decision:
            raise VerificationError("acceptance decision differs")

        if expected_decision.accepted:
            current_state = candidate_state
            current_scoring = candidate_scoring
            accepted_count += 1

        if current_scoring.score < best_scoring.score:
            best_state = SearchState.from_codebook(current_state.codebook)
            best_scoring = current_scoring

        if first_success is None and current_scoring.score.is_feasible:
            first_success = expected_index + 1

        if step.state_hash_after != current_state.state_sha256():
            raise VerificationError("state hash after proposal differs")
        if step.score_after != current_scoring.score:
            raise VerificationError("score after proposal differs")
        if step.best_state_hash_after != best_state.state_sha256():
            raise VerificationError("best-state hash after proposal differs")

    if current_state.to_bytes() != result.final_state.to_bytes():
        raise VerificationError("final state does not replay")
    if best_state.to_bytes() != result.best_state.to_bytes():
        raise VerificationError("best state does not replay")
    if current_scoring.score != result.final_scoring.score:
        raise VerificationError("final score does not replay")
    if best_scoring.score != result.best_scoring.score:
        raise VerificationError("best score does not replay")
    np.testing.assert_array_equal(
        current_scoring.edge_distances,
        result.final_scoring.edge_distances,
    )
    np.testing.assert_array_equal(
        best_scoring.edge_distances,
        result.best_scoring.edge_distances,
    )

    if first_success != result.first_success_proposal:
        raise VerificationError("first-success proposal differs")
    if swap_count != result.swap_proposals:
        raise VerificationError("swap proposal count differs")
    if replacement_count != result.replacement_proposals:
        raise VerificationError("replacement proposal count differs")
    if accepted_count != result.accepted_moves:
        raise VerificationError("accepted move count differs")

    if result.stopping_reason == "proposal_budget_exhausted":
        if result.proposals_executed != config.proposal_budget:
            raise VerificationError("budget-exhausted result did not use full budget")
    elif result.stopping_reason == "checkpoint_reached":
        if result.proposals_executed >= config.proposal_budget:
            raise VerificationError("checkpoint result is not short of full budget")
        if result.success and config.stop_on_feasible:
            raise VerificationError("checkpoint result continued despite success")
    elif result.stopping_reason == "initial_state_feasible":
        if result.proposals_executed != 0 or first_success != 0:
            raise VerificationError("initial-feasible stopping record is inconsistent")
    elif result.stopping_reason == "target_feasible":
        if not result.success or not config.stop_on_feasible:
            raise VerificationError("target-feasible stopping record is inconsistent")
        if result.proposals_executed != first_success:
            raise VerificationError("target-feasible result continued after success")
    else:
        raise VerificationError(
            f"unrecognised stopping reason: {result.stopping_reason}"
        )

    return SearchVerificationReport(
        proposals_verified=result.proposals_executed,
        swap_proposals_verified=swap_count,
        replacement_proposals_verified=replacement_count,
        accepted_moves_verified=accepted_count,
        first_success_proposal=first_success,
        final_state_sha256=current_state.state_sha256(),
        best_state_sha256=best_state.state_sha256(),
        final_score=current_scoring.score.as_tuple(),
        best_score=best_scoring.score.as_tuple(),
        stopping_reason=result.stopping_reason,
    )

"""Deterministic scalable free-codebook search primitives."""

from sphere_encoding.heuristic.initialisation import (
    InitialisationError,
    InitialisationResult,
    derive_seed,
    load_stage3_baseline,
    load_stage4_witness,
    random_injective_initialisation,
    zero_pad_state,
)
from sphere_encoding.heuristic.moves import (
    MoveEvaluation,
    ReplacementMove,
    SwapMove,
    affected_edge_indices,
    apply_evaluated_move,
    apply_move,
    evaluate_move,
)
from sphere_encoding.heuristic.schedule import (
    AcceptanceDecision,
    LinearTemperatureSchedule,
    ScheduleError,
    acceptance_decision,
)
from sphere_encoding.heuristic.scoring import (
    IncrementalScoringState,
    ScoringError,
    ThresholdScore,
    canonical_edges_array,
    score_codebook,
    score_edge_distances,
)
from sphere_encoding.heuristic.search import (
    SearchError,
    SearchKernelConfig,
    SearchKernelResult,
    SearchStep,
    propose_move,
    run_search_kernel,
)
from sphere_encoding.heuristic.state import (
    SearchState,
    SearchStateError,
    codeword_id_to_row,
    codeword_rows_to_ids,
)

__all__ = [
    "AcceptanceDecision",
    "IncrementalScoringState",
    "InitialisationError",
    "InitialisationResult",
    "LinearTemperatureSchedule",
    "MoveEvaluation",
    "ReplacementMove",
    "ScheduleError",
    "ScoringError",
    "SearchError",
    "SearchKernelConfig",
    "SearchKernelResult",
    "SearchState",
    "SearchStateError",
    "SearchStep",
    "SwapMove",
    "ThresholdScore",
    "acceptance_decision",
    "affected_edge_indices",
    "apply_evaluated_move",
    "apply_move",
    "canonical_edges_array",
    "codeword_id_to_row",
    "codeword_rows_to_ids",
    "derive_seed",
    "evaluate_move",
    "load_stage3_baseline",
    "load_stage4_witness",
    "propose_move",
    "random_injective_initialisation",
    "run_search_kernel",
    "score_codebook",
    "score_edge_distances",
    "zero_pad_state",
]

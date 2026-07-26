"""Injectivity-preserving swap and unused-code replacement moves."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from sphere_encoding.heuristic.scoring import (
    IncrementalScoringState,
    ScoringError,
    ThresholdScore,
    canonical_edges_array,
)
from sphere_encoding.heuristic.state import (
    SearchState,
    SearchStateError,
    codeword_id_to_row,
)


class MoveError(ValueError):
    """Raised when a heuristic move is malformed or inapplicable."""


@dataclass(frozen=True, slots=True)
class SwapMove:
    """Exchange the assigned codewords of two distinct vertices."""

    first_vertex: int
    second_vertex: int

    def __post_init__(self) -> None:
        if not isinstance(self.first_vertex, int) or not isinstance(
            self.second_vertex, int
        ):
            raise MoveError("swap vertices must be integers")
        if self.first_vertex < 0 or self.second_vertex < 0:
            raise MoveError("swap vertices must be non-negative")
        if self.first_vertex == self.second_vertex:
            raise MoveError("self-swaps are not permitted")


@dataclass(frozen=True, slots=True)
class ReplacementMove:
    """Assign one vertex a currently unused codeword."""

    vertex: int
    new_codeword_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.vertex, int) or not isinstance(
            self.new_codeword_id,
            int,
        ):
            raise MoveError("replacement fields must be integers")
        if self.vertex < 0:
            raise MoveError("replacement vertex must be non-negative")
        if self.new_codeword_id < 0:
            raise MoveError("replacement codeword identifier must be non-negative")


Move = SwapMove | ReplacementMove


@dataclass(frozen=True, slots=True)
class MoveEvaluation:
    """Exact incremental result for one proposed move."""

    move: Move
    affected_edge_indices: tuple[int, ...]
    new_edge_distances: tuple[int, ...]
    score: ThresholdScore

    def __post_init__(self) -> None:
        if not self.affected_edge_indices:
            raise MoveError("a valid move must affect at least one graph edge")
        if len(self.affected_edge_indices) != len(self.new_edge_distances):
            raise MoveError("affected edges and replacement distances differ in length")
        if tuple(sorted(self.affected_edge_indices)) != self.affected_edge_indices:
            raise MoveError("affected edge indices must be strictly ascending")
        if len(set(self.affected_edge_indices)) != len(self.affected_edge_indices):
            raise MoveError("affected edge indices must be unique")


def _validate_vertex(vertex: int, state: SearchState) -> None:
    if vertex < 0 or vertex >= state.vertex_count:
        raise MoveError("move vertex is outside the state")


def _validate_move(state: SearchState, move: Move) -> None:
    if isinstance(move, SwapMove):
        _validate_vertex(move.first_vertex, state)
        _validate_vertex(move.second_vertex, state)
        return

    _validate_vertex(move.vertex, state)
    if move.new_codeword_id >= state.capacity:
        raise MoveError("replacement codeword identifier is outside the code space")
    if state.is_codeword_used(move.new_codeword_id):
        raise MoveError("replacement move must use a currently unused codeword")


def _touched_vertices(move: Move) -> tuple[int, ...]:
    if isinstance(move, SwapMove):
        return tuple(sorted((move.first_vertex, move.second_vertex)))
    return (move.vertex,)


def affected_edge_indices(
    edges: npt.ArrayLike,
    *,
    vertex_count: int,
    move: Move,
) -> tuple[int, ...]:
    """Return all and only edges incident to a moved vertex."""
    canonical_edges = canonical_edges_array(
        edges,
        vertex_count=vertex_count,
    )
    touched = _touched_vertices(move)
    mask = np.zeros(canonical_edges.shape[0], dtype=np.bool_)
    for vertex in touched:
        if vertex < 0 or vertex >= vertex_count:
            raise MoveError("move vertex is outside the graph")
        mask |= (canonical_edges[:, 0] == vertex) | (canonical_edges[:, 1] == vertex)

    indices = tuple(int(index) for index in np.flatnonzero(mask))
    if not indices:
        raise MoveError("move does not affect any graph edge")
    return indices


def _row_after_move(
    state: SearchState,
    move: Move,
    vertex: int,
) -> np.ndarray:
    if isinstance(move, SwapMove):
        if vertex == move.first_vertex:
            return state.codebook[move.second_vertex]
        if vertex == move.second_vertex:
            return state.codebook[move.first_vertex]
        return state.codebook[vertex]

    if vertex == move.vertex:
        return codeword_id_to_row(
            move.new_codeword_id,
            state.code_length,
        )
    return state.codebook[vertex]


def evaluate_move(
    state: SearchState,
    edges: npt.ArrayLike,
    scoring_state: IncrementalScoringState,
    move: Move,
) -> MoveEvaluation:
    """Evaluate a move by recomputing exactly its incident edge distances."""
    _validate_move(state, move)
    canonical_edges = canonical_edges_array(
        edges,
        vertex_count=state.vertex_count,
    )
    if scoring_state.edge_count != canonical_edges.shape[0]:
        raise MoveError("scoring cache and graph have different edge counts")

    indices = affected_edge_indices(
        canonical_edges,
        vertex_count=state.vertex_count,
        move=move,
    )
    new_distances: list[int] = []

    for edge_index in indices:
        first_vertex, second_vertex = canonical_edges[edge_index]
        first_row = _row_after_move(state, move, int(first_vertex))
        second_row = _row_after_move(state, move, int(second_vertex))
        new_distances.append(int(np.count_nonzero(first_row != second_row)))

    try:
        updated_scoring = scoring_state.with_updates(
            indices,
            tuple(new_distances),
        )
    except ScoringError as error:
        raise MoveError("incremental scoring update failed") from error

    return MoveEvaluation(
        move=move,
        affected_edge_indices=indices,
        new_edge_distances=tuple(new_distances),
        score=updated_scoring.score,
    )


def apply_move(state: SearchState, move: Move) -> SearchState:
    """Apply an injectivity-preserving move and return a validated state."""
    _validate_move(state, move)
    codebook = np.array(state.codebook, dtype=np.uint8, order="C", copy=True)

    if isinstance(move, SwapMove):
        temporary = codebook[move.first_vertex].copy()
        codebook[move.first_vertex] = codebook[move.second_vertex]
        codebook[move.second_vertex] = temporary
    else:
        codebook[move.vertex] = codeword_id_to_row(
            move.new_codeword_id,
            state.code_length,
        )

    try:
        return SearchState.from_codebook(codebook)
    except SearchStateError as error:
        raise MoveError("move produced an invalid search state") from error


def apply_evaluated_move(
    state: SearchState,
    scoring_state: IncrementalScoringState,
    evaluation: MoveEvaluation,
) -> tuple[SearchState, IncrementalScoringState]:
    """Commit a previously evaluated move and its exact cache update."""
    updated_state = apply_move(state, evaluation.move)
    try:
        updated_scoring = scoring_state.with_updates(
            evaluation.affected_edge_indices,
            evaluation.new_edge_distances,
        )
    except ScoringError as error:
        raise MoveError("evaluated move contains an invalid score update") from error

    if updated_scoring.score != evaluation.score:
        raise MoveError("evaluated move score does not match its cache update")

    return updated_state, updated_scoring

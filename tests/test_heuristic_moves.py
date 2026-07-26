from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.heuristic.moves import (
    MoveError,
    ReplacementMove,
    SwapMove,
    affected_edge_indices,
    apply_evaluated_move,
    apply_move,
    evaluate_move,
)
from sphere_encoding.heuristic.scoring import (
    IncrementalScoringState,
    edge_distances_for_state,
    score_codebook,
)
from sphere_encoding.heuristic.state import SearchState


def _state() -> SearchState:
    return SearchState.from_codebook(
        np.array(
            [
                [0, 0, 0],
                [0, 0, 1],
                [1, 1, 0],
                [1, 1, 1],
            ],
            dtype=np.uint8,
        )
    )


def _edges() -> np.ndarray:
    return np.array(
        [
            [0, 1],
            [0, 2],
            [1, 3],
            [2, 3],
        ],
        dtype=np.int64,
    )


def test_swap_preserves_injectivity_and_selected_subset() -> None:
    state = _state()
    move = SwapMove(0, 1)

    updated = apply_move(state, move)

    assert updated.assigned_codeword_ids == (1, 0, 6, 7)
    assert updated.used_codeword_ids == state.used_codeword_ids
    assert len(set(updated.assigned_codeword_ids)) == updated.vertex_count


def test_replacement_changes_selected_subset_and_preserves_injectivity() -> None:
    state = _state()
    move = ReplacementMove(vertex=1, new_codeword_id=2)

    updated = apply_move(state, move)

    assert updated.assigned_codeword_ids == (0, 2, 6, 7)
    assert updated.is_codeword_used(2)
    assert not updated.is_codeword_used(1)
    assert len(set(updated.assigned_codeword_ids)) == updated.vertex_count


def test_swap_affected_edge_set_is_exact() -> None:
    assert affected_edge_indices(
        _edges(),
        vertex_count=4,
        move=SwapMove(0, 1),
    ) == (0, 1, 2)


def test_replacement_affected_edge_set_is_exact() -> None:
    assert affected_edge_indices(
        _edges(),
        vertex_count=4,
        move=ReplacementMove(1, 2),
    ) == (0, 2)


@pytest.mark.parametrize(
    "move",
    [
        SwapMove(0, 1),
        ReplacementMove(1, 2),
    ],
)
def test_incremental_move_score_matches_full_recomputation(
    move: SwapMove | ReplacementMove,
) -> None:
    state = _state()
    edges = _edges()
    cache = IncrementalScoringState.from_search_state(
        state,
        edges,
        target_r=1,
    )

    evaluation = evaluate_move(state, edges, cache, move)
    updated_state, updated_cache = apply_evaluated_move(
        state,
        cache,
        evaluation,
    )

    np.testing.assert_array_equal(
        updated_cache.edge_distances,
        edge_distances_for_state(updated_state, edges),
    )
    assert updated_cache.score == score_codebook(
        updated_state,
        edges,
        target_r=1,
    )
    assert updated_cache.score == evaluation.score


def test_brute_force_random_move_sequence_matches_full_recomputation() -> None:
    rng = np.random.default_rng(20260726)
    code_length = 5
    vertex_count = 8
    selected = rng.choice(
        1 << code_length,
        size=vertex_count,
        replace=False,
    )
    codebook = np.stack(
        [
            np.array(
                [
                    (int(identifier) >> shift) & 1
                    for shift in range(code_length - 1, -1, -1)
                ],
                dtype=np.uint8,
            )
            for identifier in selected
        ]
    )
    state = SearchState.from_codebook(codebook)

    all_pairs = [
        (first, second)
        for first in range(vertex_count)
        for second in range(first + 1, vertex_count)
    ]
    chosen_pair_indices = sorted(
        int(index)
        for index in rng.choice(
            len(all_pairs),
            size=14,
            replace=False,
        )
    )
    edges = np.array(
        [all_pairs[index] for index in chosen_pair_indices],
        dtype=np.int64,
    )
    cache = IncrementalScoringState.from_search_state(
        state,
        edges,
        target_r=2,
    )

    for proposal_index in range(200):
        if proposal_index % 2 == 0:
            vertices = rng.choice(vertex_count, size=2, replace=False)
            move: SwapMove | ReplacementMove = SwapMove(
                int(vertices[0]),
                int(vertices[1]),
            )
        else:
            unused_index = int(rng.integers(state.unused_codeword_count))
            move = ReplacementMove(
                vertex=int(rng.integers(vertex_count)),
                new_codeword_id=state.unused_codeword_id_at(unused_index),
            )

        evaluation = evaluate_move(state, edges, cache, move)
        state, cache = apply_evaluated_move(state, cache, evaluation)

        np.testing.assert_array_equal(
            cache.edge_distances,
            edge_distances_for_state(state, edges),
        )
        assert cache.score == score_codebook(
            state,
            edges,
            target_r=2,
        )


def test_explicit_move_sequence_replays_deterministically() -> None:
    edges = _edges()
    moves = (
        SwapMove(0, 1),
        ReplacementMove(2, 2),
        SwapMove(1, 3),
        ReplacementMove(0, 4),
    )

    results: list[tuple[str, tuple[int, ...], tuple[int, ...]]] = []
    for _ in range(2):
        state = _state()
        cache = IncrementalScoringState.from_search_state(
            state,
            edges,
            target_r=1,
        )
        for move in moves:
            evaluation = evaluate_move(state, edges, cache, move)
            state, cache = apply_evaluated_move(state, cache, evaluation)

        results.append(
            (
                state.state_sha256(),
                tuple(int(value) for value in cache.edge_distances),
                cache.score.as_tuple(),
            )
        )

    assert results[0] == results[1]


def test_rejected_evaluation_does_not_mutate_state() -> None:
    state = _state()
    edges = _edges()
    cache = IncrementalScoringState.from_search_state(
        state,
        edges,
        target_r=1,
    )
    original_state_hash = state.state_sha256()
    original_distances = cache.edge_distances.copy()

    evaluate_move(
        state,
        edges,
        cache,
        ReplacementMove(1, 2),
    )

    assert state.state_sha256() == original_state_hash
    np.testing.assert_array_equal(cache.edge_distances, original_distances)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: SwapMove(1, 1),
        lambda: SwapMove(-1, 1),
        lambda: ReplacementMove(-1, 2),
        lambda: ReplacementMove(1, -1),
    ],
)
def test_malformed_move_construction_is_rejected(factory: object) -> None:
    with pytest.raises(MoveError):
        factory()


@pytest.mark.parametrize(
    "move",
    [
        SwapMove(0, 4),
        ReplacementMove(4, 2),
        ReplacementMove(1, 1),
        ReplacementMove(1, 8),
    ],
)
def test_inapplicable_moves_are_rejected(
    move: SwapMove | ReplacementMove,
) -> None:
    state = _state()
    cache = IncrementalScoringState.from_search_state(
        state,
        _edges(),
        target_r=1,
    )

    with pytest.raises(MoveError):
        evaluate_move(state, _edges(), cache, move)

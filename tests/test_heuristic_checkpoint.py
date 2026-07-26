from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sphere_encoding.heuristic.initialisation import (
    random_injective_initialisation,
)
from sphere_encoding.heuristic.schedule import LinearTemperatureSchedule
from sphere_encoding.heuristic.search import (
    SearchError,
    SearchKernelCheckpoint,
    SearchKernelConfig,
    run_search_kernel,
)


def _edges() -> np.ndarray:
    return np.array(
        [
            [0, 1],
            [0, 2],
            [0, 3],
            [1, 2],
            [1, 4],
            [2, 5],
            [3, 4],
            [3, 5],
            [4, 5],
        ],
        dtype=np.int64,
    )


def _initial_state():
    return random_injective_initialisation(
        vertex_count=6,
        code_length=4,
        seed=9101,
    ).state


def _config() -> SearchKernelConfig:
    return SearchKernelConfig(
        proposal_budget=240,
        swap_probability=0.45,
        temperature_schedule=LinearTemperatureSchedule(
            proposal_budget=240,
            start_temperature=2.5,
            end_temperature=0.0,
        ),
        stop_on_feasible=False,
    )


def test_checkpoint_resume_matches_uninterrupted_execution_exactly() -> None:
    initial = _initial_state()
    config = _config()

    uninterrupted = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9102,
        config=config,
    )
    partial = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9102,
        config=config,
        stop_after_proposals=73,
    )
    resumed = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9102,
        config=config,
        resume_from=partial.checkpoint,
    )

    assert partial.stopping_reason == "checkpoint_reached"
    assert partial.proposals_executed == 73
    assert resumed.steps == uninterrupted.steps
    assert resumed.final_state.to_bytes() == (uninterrupted.final_state.to_bytes())
    assert resumed.best_state.to_bytes() == (uninterrupted.best_state.to_bytes())
    assert resumed.final_scoring.score == uninterrupted.final_scoring.score
    assert resumed.best_scoring.score == uninterrupted.best_scoring.score
    assert resumed.swap_proposals == uninterrupted.swap_proposals
    assert resumed.replacement_proposals == (uninterrupted.replacement_proposals)
    assert resumed.accepted_moves == uninterrupted.accepted_moves
    assert resumed.checkpoint.to_bytes() == (uninterrupted.checkpoint.to_bytes())


def test_multiple_resume_boundaries_are_exact() -> None:
    initial = _initial_state()
    config = _config()

    first = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9103,
        config=config,
        stop_after_proposals=40,
    )
    second = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9103,
        config=config,
        resume_from=first.checkpoint,
        stop_after_proposals=125,
    )
    final = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9103,
        config=config,
        resume_from=second.checkpoint,
    )
    uninterrupted = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9103,
        config=config,
    )

    assert first.proposals_executed == 40
    assert second.proposals_executed == 125
    assert final.checkpoint.to_bytes() == (uninterrupted.checkpoint.to_bytes())


def test_checkpoint_serialisation_is_canonical_and_byte_stable() -> None:
    result = run_search_kernel(
        _initial_state(),
        _edges(),
        target_r=1,
        seed=9104,
        config=_config(),
        stop_after_proposals=55,
    )

    data = result.checkpoint.to_bytes()
    restored = SearchKernelCheckpoint.from_bytes(data)

    assert restored.to_bytes() == data
    assert restored.checkpoint_sha256() == (result.checkpoint.checkpoint_sha256())


def test_checkpoint_file_round_trip_is_byte_identical(
    tmp_path: Path,
) -> None:
    result = run_search_kernel(
        _initial_state(),
        _edges(),
        target_r=1,
        seed=9105,
        config=_config(),
        stop_after_proposals=31,
    )
    path = tmp_path / "checkpoint.bin"

    result.checkpoint.write(path)
    restored = SearchKernelCheckpoint.read(path)

    assert path.read_bytes() == result.checkpoint.to_bytes()
    assert restored.to_bytes() == result.checkpoint.to_bytes()


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not-a-checkpoint",
        (b"SPHERE_ENCODING_HEURISTIC_SEARCH_CHECKPOINT_V1\n{}\n"),
    ],
)
def test_invalid_checkpoint_bytes_are_rejected(data: bytes) -> None:
    with pytest.raises(SearchError):
        SearchKernelCheckpoint.from_bytes(data)


def test_truncated_checkpoint_is_rejected() -> None:
    result = run_search_kernel(
        _initial_state(),
        _edges(),
        target_r=1,
        seed=9106,
        config=_config(),
        stop_after_proposals=25,
    )
    data = result.checkpoint.to_bytes()

    with pytest.raises(SearchError):
        SearchKernelCheckpoint.from_bytes(data[:-7])


def test_resume_context_mismatch_is_rejected() -> None:
    initial = _initial_state()
    partial = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9107,
        config=_config(),
        stop_after_proposals=20,
    )

    with pytest.raises(SearchError):
        run_search_kernel(
            initial,
            _edges(),
            target_r=2,
            seed=9107,
            config=_config(),
            resume_from=partial.checkpoint,
        )

    changed_edges = _edges().copy()
    changed_edges[-1] = [2, 4]
    changed_edges = changed_edges[
        np.lexsort((changed_edges[:, 1], changed_edges[:, 0]))
    ]
    with pytest.raises(SearchError):
        run_search_kernel(
            initial,
            changed_edges,
            target_r=1,
            seed=9107,
            config=_config(),
            resume_from=partial.checkpoint,
        )


def test_resume_cannot_move_backwards_or_exceed_budget() -> None:
    initial = _initial_state()
    config = _config()
    partial = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9108,
        config=config,
        stop_after_proposals=50,
    )

    with pytest.raises(SearchError):
        run_search_kernel(
            initial,
            _edges(),
            target_r=1,
            seed=9108,
            config=config,
            resume_from=partial.checkpoint,
            stop_after_proposals=49,
        )

    with pytest.raises(SearchError):
        run_search_kernel(
            initial,
            _edges(),
            target_r=1,
            seed=9108,
            config=config,
            resume_from=partial.checkpoint,
            stop_after_proposals=241,
        )

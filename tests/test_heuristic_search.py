from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sphere_encoding.heuristic.initialisation import (
    load_stage4_witness,
    random_injective_initialisation,
)
from sphere_encoding.heuristic.schedule import LinearTemperatureSchedule
from sphere_encoding.heuristic.scoring import (
    edge_distances_for_state,
    score_codebook,
)
from sphere_encoding.heuristic.search import (
    SearchError,
    SearchKernelConfig,
    run_search_kernel,
)

STAGE2_RUN_ID = "stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50"
STAGE4_RUN_ID = "stage4-exact-free-codebook-97021c6cac03-7adb5b49f2cb"
STAGE2_ROOT = Path("results/raw") / STAGE2_RUN_ID
STAGE4_ROOT = Path("results/raw") / STAGE4_RUN_ID


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


def _config(
    *,
    budget: int = 100,
    stop_on_feasible: bool = False,
) -> SearchKernelConfig:
    return SearchKernelConfig(
        proposal_budget=budget,
        swap_probability=0.5,
        temperature_schedule=LinearTemperatureSchedule(
            proposal_budget=budget,
            start_temperature=2.0,
            end_temperature=0.0,
        ),
        stop_on_feasible=stop_on_feasible,
    )


def test_fixed_seed_replays_proposals_and_decisions_exactly() -> None:
    initial = random_injective_initialisation(
        vertex_count=6,
        code_length=4,
        seed=100,
    ).state

    first = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=200,
        config=_config(),
    )
    second = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=200,
        config=_config(),
    )

    assert first.steps == second.steps
    assert first.final_state.to_bytes() == second.final_state.to_bytes()
    assert first.best_state.to_bytes() == second.best_state.to_bytes()
    assert first.final_scoring.score == second.final_scoring.score
    assert first.best_scoring.score == second.best_scoring.score


def test_fixed_budget_and_move_accounting() -> None:
    initial = random_injective_initialisation(
        vertex_count=6,
        code_length=4,
        seed=101,
    ).state

    result = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=201,
        config=_config(budget=200),
    )

    assert result.proposals_executed == 200
    assert result.swap_proposals + result.replacement_proposals == 200
    assert result.swap_proposals > 0
    assert result.replacement_proposals > 0
    assert 0 <= result.accepted_moves <= 200
    assert result.stopping_reason == "proposal_budget_exhausted"


def test_cached_final_and_best_scores_match_full_recomputation() -> None:
    initial = random_injective_initialisation(
        vertex_count=6,
        code_length=4,
        seed=102,
    ).state

    result = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=202,
        config=_config(),
    )

    np.testing.assert_array_equal(
        result.final_scoring.edge_distances,
        edge_distances_for_state(result.final_state, _edges()),
    )
    assert result.final_scoring.score == score_codebook(
        result.final_state,
        _edges(),
        target_r=1,
    )
    assert result.best_scoring.score == score_codebook(
        result.best_state,
        _edges(),
        target_r=1,
    )
    assert result.best_scoring.score <= result.final_scoring.score


def test_initial_feasible_state_stops_without_proposals() -> None:
    initial = random_injective_initialisation(
        vertex_count=6,
        code_length=4,
        seed=103,
    ).state

    result = run_search_kernel(
        initial,
        _edges(),
        target_r=4,
        seed=203,
        config=_config(stop_on_feasible=True),
    )

    assert result.success
    assert result.first_success_proposal == 0
    assert result.proposals_executed == 0
    assert result.stopping_reason == "initial_state_feasible"


def test_exact_stage4_calibration_witness_is_valid_at_target_two() -> None:
    witness = load_stage4_witness(
        STAGE4_ROOT,
        graph_id="icosphere_l0",
        source_code_length=4,
        target_r=2,
        target_code_length=4,
    ).state
    edges = np.load(
        STAGE2_ROOT / "icosphere_l0" / "edges.npy",
        allow_pickle=False,
    )

    result = run_search_kernel(
        witness,
        edges,
        target_r=2,
        seed=0,
        config=_config(stop_on_feasible=True),
    )

    assert result.success
    assert result.first_success_proposal == 0
    assert result.best_scoring.score.is_feasible
    assert max(int(value) for value in result.best_scoring.edge_distances) == 2


def test_exact_stage4_calibration_never_false_reports_below_optimum() -> None:
    witness = load_stage4_witness(
        STAGE4_ROOT,
        graph_id="icosphere_l0",
        source_code_length=4,
        target_r=2,
        target_code_length=4,
    ).state
    edges = np.load(
        STAGE2_ROOT / "icosphere_l0" / "edges.npy",
        allow_pickle=False,
    )

    result = run_search_kernel(
        witness,
        edges,
        target_r=1,
        seed=123,
        config=_config(budget=250),
    )

    assert not result.success
    assert not result.best_scoring.score.is_feasible
    assert result.first_success_proposal is None


def test_invalid_kernel_settings_are_rejected() -> None:
    schedule = LinearTemperatureSchedule(10, 1.0, 0.0)

    with pytest.raises(SearchError):
        SearchKernelConfig(
            proposal_budget=9,
            swap_probability=0.5,
            temperature_schedule=schedule,
            stop_on_feasible=False,
        )
    with pytest.raises(SearchError):
        SearchKernelConfig(
            proposal_budget=10,
            swap_probability=1.1,
            temperature_schedule=schedule,
            stop_on_feasible=False,
        )

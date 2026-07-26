from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from sphere_encoding.heuristic.initialisation import (
    load_stage4_witness,
    random_injective_initialisation,
)
from sphere_encoding.heuristic.schedule import LinearTemperatureSchedule
from sphere_encoding.heuristic.scoring import ThresholdScore
from sphere_encoding.heuristic.search import (
    SearchKernelConfig,
    run_search_kernel,
)
from sphere_encoding.heuristic.verification import (
    VerificationError,
    verify_search_result,
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
    budget: int = 180,
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


def test_complete_trajectory_replays_exactly() -> None:
    initial = random_injective_initialisation(
        vertex_count=6,
        code_length=4,
        seed=9201,
    ).state
    config = _config()
    result = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9202,
        config=config,
    )

    report = verify_search_result(
        result,
        _edges(),
        target_r=1,
        config=config,
    )

    assert report.proposals_verified == 180
    assert report.swap_proposals_verified + report.replacement_proposals_verified == 180
    assert report.accepted_moves_verified == result.accepted_moves
    assert report.final_state_sha256 == result.final_state.state_sha256()
    assert report.best_state_sha256 == result.best_state.state_sha256()
    assert report.best_score <= report.final_score
    assert report.stopping_reason == "proposal_budget_exhausted"


def test_partial_checkpoint_trajectory_replays_exactly() -> None:
    initial = random_injective_initialisation(
        vertex_count=6,
        code_length=4,
        seed=9203,
    ).state
    config = _config()
    result = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9204,
        config=config,
        stop_after_proposals=61,
    )

    report = verify_search_result(
        result,
        _edges(),
        target_r=1,
        config=config,
    )

    assert report.proposals_verified == 61
    assert report.stopping_reason == "checkpoint_reached"


def test_tampered_candidate_score_is_detected() -> None:
    initial = random_injective_initialisation(
        vertex_count=6,
        code_length=4,
        seed=9205,
    ).state
    config = _config()
    result = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9206,
        config=config,
        stop_after_proposals=30,
    )

    first = result.steps[0]
    tampered_score = ThresholdScore(
        violation_count=first.candidate_score.violation_count,
        total_excess=first.candidate_score.total_excess,
        maximum_excess=first.candidate_score.maximum_excess,
        maximum_distance_edge_count=(first.candidate_score.maximum_distance_edge_count),
        total_local_hamming=(first.candidate_score.total_local_hamming + 1),
    )
    tampered_step = replace(
        first,
        candidate_score=tampered_score,
    )
    tampered_steps = (tampered_step, *result.steps[1:])
    tampered_checkpoint = replace(
        result.checkpoint,
        steps=tampered_steps,
    )
    tampered_result = replace(
        result,
        steps=tampered_steps,
        checkpoint=tampered_checkpoint,
    )

    with pytest.raises(VerificationError):
        verify_search_result(
            tampered_result,
            _edges(),
            target_r=1,
            config=config,
        )


def test_wrong_graph_or_configuration_is_detected() -> None:
    initial = random_injective_initialisation(
        vertex_count=6,
        code_length=4,
        seed=9207,
    ).state
    config = _config()
    result = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9208,
        config=config,
        stop_after_proposals=20,
    )

    changed_edges = _edges().copy()
    changed_edges[-1] = [2, 4]
    changed_edges = changed_edges[
        np.lexsort((changed_edges[:, 1], changed_edges[:, 0]))
    ]

    with pytest.raises(VerificationError):
        verify_search_result(
            result,
            changed_edges,
            target_r=1,
            config=config,
        )

    with pytest.raises(VerificationError):
        verify_search_result(
            result,
            _edges(),
            target_r=1,
            config=_config(budget=181),
        )


def test_exact_stage4_overlap_replays_as_initial_success() -> None:
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
    config = _config(
        budget=25,
        stop_on_feasible=True,
    )
    result = run_search_kernel(
        witness,
        edges,
        target_r=2,
        seed=0,
        config=config,
    )

    report = verify_search_result(
        result,
        edges,
        target_r=2,
        config=config,
    )

    assert result.first_success_proposal == 0
    assert result.proposals_executed == 0
    assert result.stopping_reason == "initial_state_feasible"
    assert report.first_success_proposal == 0
    assert report.best_score[0] == 0


def test_budget_accounting_and_best_incumbent_integrity() -> None:
    initial = random_injective_initialisation(
        vertex_count=6,
        code_length=4,
        seed=9209,
    ).state
    config = _config(budget=250)
    result = run_search_kernel(
        initial,
        _edges(),
        target_r=1,
        seed=9210,
        config=config,
    )

    report = verify_search_result(
        result,
        _edges(),
        target_r=1,
        config=config,
    )

    assert report.proposals_verified == config.proposal_budget
    assert result.proposals_executed == config.proposal_budget
    assert result.best_scoring.score <= result.final_scoring.score
    assert result.best_scoring.score <= result.initial_score

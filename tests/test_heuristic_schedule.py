from __future__ import annotations

import math

import pytest

from sphere_encoding.heuristic.schedule import (
    LinearTemperatureSchedule,
    ScheduleError,
    acceptance_decision,
)
from sphere_encoding.heuristic.scoring import ThresholdScore


def _score(
    violation_count: int,
    total_excess: int = 0,
    maximum_excess: int = 0,
    maximum_distance_edge_count: int = 1,
    total_local_hamming: int = 1,
) -> ThresholdScore:
    return ThresholdScore(
        violation_count,
        total_excess,
        maximum_excess,
        maximum_distance_edge_count,
        total_local_hamming,
    )


def test_linear_temperature_schedule_endpoints() -> None:
    schedule = LinearTemperatureSchedule(
        proposal_budget=5,
        start_temperature=4.0,
        end_temperature=0.0,
    )

    assert schedule.temperature_at(0) == 4.0
    assert schedule.temperature_at(2) == 2.0
    assert schedule.temperature_at(4) == 0.0


def test_improving_and_equal_moves_are_accepted() -> None:
    current = _score(2, 3, 2, 2, 10)

    improving = acceptance_decision(
        current,
        _score(1, 100, 100, 100, 100),
        temperature=0.0,
        random_draw=0.999,
    )
    equal = acceptance_decision(
        current,
        current,
        temperature=0.0,
        random_draw=0.999,
    )

    assert improving.accepted
    assert improving.relation == "improving"
    assert improving.probability == 1.0
    assert equal.accepted
    assert equal.relation == "equal"
    assert equal.probability == 1.0


def test_worsening_probability_uses_first_lexicographic_difference() -> None:
    current = _score(2, 3, 2, 2, 10)
    candidate = _score(2, 5, 0, 1, 1)

    decision = acceptance_decision(
        current,
        candidate,
        temperature=2.0,
        random_draw=0.2,
    )

    assert decision.relation == "worsening"
    assert decision.first_difference_index == 1
    assert decision.first_difference_magnitude == 2
    assert decision.probability == pytest.approx(math.exp(-1.0))
    assert decision.accepted


def test_zero_temperature_rejects_worsening_move() -> None:
    decision = acceptance_decision(
        _score(1),
        _score(2),
        temperature=0.0,
        random_draw=0.0,
    )

    assert not decision.accepted
    assert decision.probability == 0.0


def test_acceptance_is_deterministic_for_fixed_draw() -> None:
    arguments = {
        "current": _score(1),
        "candidate": _score(2),
        "temperature": 2.0,
        "random_draw": 0.4,
    }
    assert acceptance_decision(**arguments) == acceptance_decision(**arguments)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: LinearTemperatureSchedule(0, 1.0, 0.0),
        lambda: LinearTemperatureSchedule(5, -1.0, 0.0),
        lambda: LinearTemperatureSchedule(5, 1.0, 2.0),
        lambda: LinearTemperatureSchedule(5, float("nan"), 0.0),
    ],
)
def test_invalid_schedule_is_rejected(factory: object) -> None:
    with pytest.raises(ScheduleError):
        factory()

"""Deterministic temperature and lexicographic acceptance schedules."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from sphere_encoding.heuristic.scoring import ThresholdScore


class ScheduleError(ValueError):
    """Raised when a temperature or acceptance setting is invalid."""


@dataclass(frozen=True, slots=True)
class LinearTemperatureSchedule:
    """A fixed proposal-indexed linear temperature schedule."""

    proposal_budget: int
    start_temperature: float
    end_temperature: float

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_budget, int) or self.proposal_budget <= 0:
            raise ScheduleError("proposal budget must be a positive integer")
        for value in (self.start_temperature, self.end_temperature):
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ScheduleError("temperatures must be finite")
            if value < 0:
                raise ScheduleError("temperatures must be non-negative")
        if self.end_temperature > self.start_temperature:
            raise ScheduleError(
                "linear cooling requires end temperature <= start temperature"
            )

    def temperature_at(self, proposal_index: int) -> float:
        """Return the temperature for a zero-based proposal index."""
        if (
            not isinstance(proposal_index, int)
            or proposal_index < 0
            or proposal_index >= self.proposal_budget
        ):
            raise ScheduleError("proposal index is outside the schedule")
        if self.proposal_budget == 1:
            return float(self.start_temperature)

        fraction = proposal_index / (self.proposal_budget - 1)
        return float(
            self.start_temperature
            + fraction * (self.end_temperature - self.start_temperature)
        )


@dataclass(frozen=True, slots=True)
class AcceptanceDecision:
    """A fully replayable acceptance decision."""

    accepted: bool
    relation: Literal["improving", "equal", "worsening"]
    probability: float
    random_draw: float
    first_difference_index: int | None
    first_difference_magnitude: int

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ScheduleError("acceptance probability must lie in [0, 1]")
        if not 0.0 <= self.random_draw < 1.0:
            raise ScheduleError("acceptance draw must lie in [0, 1)")
        if self.first_difference_magnitude < 0:
            raise ScheduleError("first-difference magnitude must be non-negative")


def acceptance_decision(
    current: ThresholdScore,
    candidate: ThresholdScore,
    *,
    temperature: float,
    random_draw: float,
) -> AcceptanceDecision:
    """Apply lexicographic Metropolis acceptance without scalar weighting."""
    if not isinstance(temperature, (int, float)) or not math.isfinite(temperature):
        raise ScheduleError("temperature must be finite")
    if temperature < 0:
        raise ScheduleError("temperature must be non-negative")
    if not isinstance(random_draw, (int, float)) or not 0.0 <= random_draw < 1.0:
        raise ScheduleError("acceptance draw must lie in [0, 1)")

    current_key = current.as_tuple()
    candidate_key = candidate.as_tuple()

    if candidate_key == current_key:
        return AcceptanceDecision(
            accepted=True,
            relation="equal",
            probability=1.0,
            random_draw=float(random_draw),
            first_difference_index=None,
            first_difference_magnitude=0,
        )

    first_difference = next(
        index
        for index, (current_value, candidate_value) in enumerate(
            zip(current_key, candidate_key, strict=True)
        )
        if current_value != candidate_value
    )
    delta = candidate_key[first_difference] - current_key[first_difference]

    if delta < 0:
        return AcceptanceDecision(
            accepted=True,
            relation="improving",
            probability=1.0,
            random_draw=float(random_draw),
            first_difference_index=first_difference,
            first_difference_magnitude=-delta,
        )

    probability = 0.0 if temperature == 0 else math.exp(-delta / float(temperature))
    return AcceptanceDecision(
        accepted=float(random_draw) < probability,
        relation="worsening",
        probability=probability,
        random_draw=float(random_draw),
        first_difference_index=first_difference,
        first_difference_magnitude=delta,
    )

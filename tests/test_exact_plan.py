from __future__ import annotations

from pathlib import Path

import pytest

from sphere_encoding.exact.plan import (
    derive_stage4_plan,
    equal_target_budget,
    select_baseline_row,
    stage4_plan_payload,
)


def synthetic_row(
    *,
    graph_id: str,
    encoding_id: str,
    code_length: int,
    l_max: int,
    vertex_count: int = 12,
) -> dict[str, str]:
    return {
        "graph_id": graph_id,
        "encoding_id": encoding_id,
        "vertex_count": str(vertex_count),
        "code_length": str(code_length),
        "L_max": str(l_max),
        "collision_count": "0",
        "unique_codeword_count": str(vertex_count),
    }


def test_cartesian_baseline_requires_exact_requested_length() -> None:
    rows = (
        synthetic_row(
            graph_id="g",
            encoding_id="cartesian_coordinate_gray",
            code_length=9,
            l_max=2,
        ),
        synthetic_row(
            graph_id="g",
            encoding_id="canonical_index_gray",
            code_length=7,
            l_max=5,
        ),
    )

    selected, tie_count = select_baseline_row(
        rows,
        graph_id="g",
        requested_code_length=7,
    )

    assert selected["encoding_id"] == "canonical_index_gray"
    assert tie_count == 1


def test_index_baseline_may_be_zero_padded() -> None:
    rows = (
        synthetic_row(
            graph_id="g",
            encoding_id="canonical_index_binary",
            code_length=4,
            l_max=4,
        ),
        synthetic_row(
            graph_id="g",
            encoding_id="canonical_index_gray",
            code_length=4,
            l_max=3,
        ),
    )

    selected, tie_count = select_baseline_row(
        rows,
        graph_id="g",
        requested_code_length=8,
    )

    assert selected["encoding_id"] == "canonical_index_gray"
    assert tie_count == 1


def test_baseline_tie_break_uses_native_length_then_id() -> None:
    rows = (
        synthetic_row(
            graph_id="g",
            encoding_id="canonical_index_gray",
            code_length=5,
            l_max=4,
        ),
        synthetic_row(
            graph_id="g",
            encoding_id="canonical_index_zeta",
            code_length=4,
            l_max=4,
        ),
        synthetic_row(
            graph_id="g",
            encoding_id="canonical_index_binary",
            code_length=4,
            l_max=4,
        ),
    )

    selected, tie_count = select_baseline_row(
        rows,
        graph_id="g",
        requested_code_length=8,
    )

    assert selected["encoding_id"] == "canonical_index_binary"
    assert tie_count == 3


def test_noninjective_candidate_is_rejected() -> None:
    row = synthetic_row(
        graph_id="g",
        encoding_id="canonical_index_gray",
        code_length=4,
        l_max=3,
    )
    row["collision_count"] = "1"
    row["unique_codeword_count"] = "11"

    with pytest.raises(ValueError, match="non-injective"):
        select_baseline_row(
            (row,),
            graph_id="g",
            requested_code_length=4,
        )


@pytest.mark.parametrize(
    ("total", "count", "expected"),
    [
        (300, 2, 150),
        (1200, 3, 400),
        (3600, 4, 900),
        (10800, 3, 3600),
    ],
)
def test_equal_target_budget(
    total: int,
    count: int,
    expected: int,
) -> None:
    assert (
        equal_target_budget(
            total_budget_seconds=total,
            target_count=count,
        )
        == expected
    )


def test_nondivisible_budget_is_rejected() -> None:
    with pytest.raises(ValueError, match="divide equally"):
        equal_target_budget(
            total_budget_seconds=10,
            target_count=3,
        )


def test_definitive_plan_has_frozen_counts_and_budget() -> None:
    plan = derive_stage4_plan(Path.cwd())

    assert plan.stage == 4
    assert plan.instance_count == 21
    assert plan.target_count == 68
    assert plan.total_budget_seconds == 81600
    assert plan.hint_eligible_target_count == 0
    assert plan.baseline_tie_instance_count == 8
    assert len(plan.input_identities) == 2
    assert {
        identity.stage_name
        for identity in plan.input_identities
    } == {"stage2", "stage3"}


def test_definitive_plan_has_expected_boundary_instances() -> None:
    plan = derive_stage4_plan(Path.cwd())

    first = plan.instances[0]
    last = plan.instances[-1]

    assert first.execution_order == 1
    assert first.graph_id == "icosphere_l0"
    assert first.code_length == 4
    assert first.structural_lower_bound == 2
    assert first.baseline.encoding_id == (
        "canonical_index_binary"
    )
    assert tuple(
        target.target_r
        for target in first.targets
    ) == (2, 3)

    assert last.execution_order == 21
    assert last.graph_id == "primitive_q3_knn8"
    assert last.code_length == 9
    assert last.structural_lower_bound == 2
    assert last.baseline.encoding_id == (
        "cartesian_coordinate_gray"
    )
    assert tuple(
        target.target_r
        for target in last.targets
    ) == (2, 3, 4)


def test_definitive_plan_preserves_all_frozen_budget_classes() -> None:
    plan = derive_stage4_plan(Path.cwd())

    observed = {
        (
            instance.graph_id,
            instance.code_length,
        ): (
            instance.total_budget_seconds,
            instance.per_target_budget_seconds,
        )
        for instance in plan.instances
    }

    assert observed[("icosphere_l0", 4)] == (300, 150)
    assert observed[("icosphere_l1", 6)] == (1200, 400)
    assert observed[("primitive_q2_knn4", 7)] == (
        3600,
        900,
    )
    assert observed[("icosphere_l2", 8)] == (5400, 900)
    assert observed[("primitive_q3_knn4", 9)] == (
        10800,
        3600,
    )


def test_definitive_plan_hash_is_deterministic() -> None:
    first = derive_stage4_plan(Path.cwd())
    second = derive_stage4_plan(Path.cwd())

    assert first.plan_sha256 == second.plan_sha256
    assert stage4_plan_payload(first) == stage4_plan_payload(
        second
    )
    assert len(first.plan_sha256) == 64


def test_all_definitive_targets_are_below_selected_baseline() -> None:
    plan = derive_stage4_plan(Path.cwd())

    assert all(
        target.target_r < instance.baseline.l_max
        and target.baseline_hint_eligible is False
        for instance in plan.instances
        for target in instance.targets
    )


def test_all_definitive_graphs_have_odd_cycle_witnesses() -> None:
    plan = derive_stage4_plan(Path.cwd())

    assert all(
        instance.structural_lower_bound == 2
        and instance.odd_cycle is not None
        and len(instance.odd_cycle) % 2 == 1
        for instance in plan.instances
    )

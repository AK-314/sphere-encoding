from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from sphere_encoding.heuristic.planning import (
    CODE_LENGTH_OFFSETS,
    GRAPH_ORDER,
    PlanningError,
    build_stage5_plan,
    stage5_plan_payload,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plan():
    return build_stage5_plan(ROOT)


def _instance(plan, graph_id: str, code_length: int):
    return next(
        instance
        for instance in plan.instances
        if (instance.graph_id == graph_id and instance.code_length == code_length)
    )


def test_global_grid_partition_and_counts(plan) -> None:
    assert plan.graph_order == GRAPH_ORDER
    assert plan.code_length_offsets == CODE_LENGTH_OFFSETS
    assert len(plan.graphs) == 13
    assert plan.global_grid_pair_count == 52
    assert plan.direct_stage4_exact_pair_count == 9
    assert plan.candidate_instance_count == 43
    assert plan.search_required_instance_count == 42
    assert plan.exact_by_transfer_instance_count == 1
    assert plan.unresolved_target_count == 159


def test_every_graph_has_the_frozen_four_lengths(plan) -> None:
    direct = {
        (pair.graph_id, pair.code_length) for pair in plan.direct_stage4_exact_pairs
    }
    candidates = {
        (instance.graph_id, instance.code_length) for instance in plan.instances
    }

    expected = {
        (
            graph.graph_id,
            graph.minimum_code_length + offset,
        )
        for graph in plan.graphs
        for offset in CODE_LENGTH_OFFSETS
    }
    assert direct.isdisjoint(candidates)
    assert direct | candidates == expected


def test_direct_stage4_exact_pairs_are_excluded(plan) -> None:
    exact = {
        (
            pair.graph_id,
            pair.code_length,
            pair.exact_l_star_free,
        )
        for pair in plan.direct_stage4_exact_pairs
    }

    assert exact == {
        ("icosphere_l0", 4, 2),
        ("icosphere_l0", 5, 2),
        ("icosphere_l0", 6, 2),
        ("icosphere_l0", 8, 2),
        ("icosphere_l1", 6, 2),
        ("icosphere_l1", 7, 2),
        ("icosphere_l1", 8, 2),
        ("icosphere_l1", 10, 2),
        ("primitive_q2_knn4", 9, 2),
    }


def test_all_graphs_have_structural_lower_bound_two(plan) -> None:
    assert all(graph.structural_lower_bound == 2 for graph in plan.graphs)
    assert all(not graph.bipartite for graph in plan.graphs)
    assert all(graph.odd_cycle is not None for graph in plan.graphs)


def test_execution_and_target_orders_are_contiguous(plan) -> None:
    assert tuple(instance.execution_order for instance in plan.instances) == tuple(
        range(1, 44)
    )

    for instance in plan.instances:
        assert tuple(
            target.target_order_within_instance for target in instance.targets
        ) == tuple(range(1, len(instance.targets) + 1))


def test_stage4_transfer_improves_icosphere_l2_m12_upper_bound(plan) -> None:
    instance = _instance(plan, "icosphere_l2", 12)

    assert instance.accepted_lower_bound == 2
    assert instance.accepted_upper_bound == 3
    assert tuple(target.target_r for target in instance.targets) == (2,)
    assert instance.accepted_upper_bound_source.source_class == ("stage4_witness")
    assert instance.accepted_upper_bound_source.source_code_length == 10
    assert instance.accepted_upper_bound_source.stage4_target_r == 3
    assert instance.accepted_upper_bound_source.zero_padding_bits == 2


def test_q2_knn4_m11_is_retained_as_exact_by_transfer(plan) -> None:
    instance = _instance(plan, "primitive_q2_knn4", 11)

    assert instance.classification == "exact_by_accepted_transfer"
    assert instance.accepted_lower_bound == 2
    assert instance.accepted_upper_bound == 2
    assert instance.targets == ()
    assert instance.accepted_upper_bound_source.source_class == ("stage4_witness")
    assert instance.accepted_upper_bound_source.source_code_length == 9
    assert instance.accepted_upper_bound_source.stage4_target_r == 2
    assert instance.accepted_upper_bound_source.zero_padding_bits == 2


def test_q4_upper_bounds_use_matching_stage3_sources(plan) -> None:
    m10 = _instance(plan, "primitive_q4_knn8", 10)
    m12 = _instance(plan, "primitive_q4_knn8", 12)
    m14 = _instance(plan, "primitive_q4_knn8", 14)

    assert m10.accepted_upper_bound == 9
    assert m10.stage3_initialisation.stage3_encoding_id == ("canonical_index_gray")
    assert m10.stage3_initialisation.zero_padding_bits == 0

    assert m12.accepted_upper_bound == 8
    assert m12.stage3_initialisation.stage3_encoding_id == ("cartesian_coordinate_gray")
    assert m12.stage3_initialisation.zero_padding_bits == 0

    assert m14.accepted_upper_bound == 8
    assert m14.stage3_initialisation.stage3_encoding_id == ("cartesian_coordinate_gray")
    assert m14.stage3_initialisation.zero_padding_bits == 2


def test_unavailable_stage4_initialisations_are_explicit(plan) -> None:
    assert _instance(plan, "icosphere_l3", 10).stage4_initialisation is None
    assert (
        _instance(
            plan,
            "primitive_q3_knn6",
            13,
        ).stage4_initialisation
        is None
    )
    assert (
        _instance(
            plan,
            "primitive_q4_knn4",
            14,
        ).stage4_initialisation
        is None
    )


def test_available_stage4_source_transfers_to_longer_q3_instance(plan) -> None:
    instance = _instance(plan, "primitive_q3_knn4", 13)

    assert instance.accepted_upper_bound == 4
    assert instance.stage4_initialisation is not None
    assert instance.stage4_initialisation.source_code_length == 9
    assert instance.stage4_initialisation.stage4_target_r == 4
    assert instance.stage4_initialisation.zero_padding_bits == 4
    assert tuple(target.target_r for target in instance.targets) == (2, 3)


def test_all_source_paths_and_hashes_are_recorded(plan) -> None:
    initialisations = []
    for instance in plan.instances:
        initialisations.extend(
            [
                instance.accepted_upper_bound_source,
                instance.stage3_initialisation,
            ]
        )
        if instance.stage4_initialisation is not None:
            initialisations.append(instance.stage4_initialisation)

    assert initialisations
    for initialisation in initialisations:
        path = ROOT / initialisation.source_path
        assert path.is_file()
        assert len(initialisation.source_sha256) == 64
        assert initialisation.target_code_length >= (initialisation.source_code_length)


def test_plan_is_byte_stable_under_repeated_construction(plan) -> None:
    repeated = build_stage5_plan(ROOT)

    assert repeated == plan
    assert repeated.plan_sha256 == plan.plan_sha256
    assert stage5_plan_payload(repeated) == stage5_plan_payload(plan)
    assert len(plan.plan_sha256) == 64


def test_no_target_is_planned_at_or_above_accepted_upper_bound(plan) -> None:
    for instance in plan.instances:
        assert all(
            instance.accepted_lower_bound
            <= target.target_r
            < instance.accepted_upper_bound
            for target in instance.targets
        )


def test_plan_validation_rejects_inconsistent_counts(plan) -> None:
    with pytest.raises(PlanningError):
        replace(
            plan,
            candidate_instance_count=plan.candidate_instance_count + 1,
        )

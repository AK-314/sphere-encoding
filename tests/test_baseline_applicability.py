from __future__ import annotations

import pytest

from sphere_encoding.encodings.applicability import (
    BASELINE_ENCODING_IDS,
    CARTESIAN_INAPPLICABLE_REASON,
    build_applicability_matrix,
    encoding_is_applicable,
    validate_frozen_stage3_applicability,
)

GRAPH_RECORDS = [
    {
        "family": "icosphere_triangulation",
        "graph_id": f"icosphere_l{level}",
    }
    for level in range(4)
] + [
    {
        "family": "primitive_integer_directions",
        "graph_id": f"primitive_q{q}_knn{k}",
    }
    for q in (2, 3, 4)
    for k in (4, 6, 8)
]


def test_frozen_applicability_matrix_counts_and_order() -> None:
    rows = build_applicability_matrix(GRAPH_RECORDS)
    diagnostics = validate_frozen_stage3_applicability(rows)

    assert diagnostics == {
        "applicable_instance_count": 44,
        "applicable_instance_counts_by_encoding": {
            "canonical_index_binary": 13,
            "canonical_index_gray": 13,
            "cartesian_coordinate_binary": 9,
            "cartesian_coordinate_gray": 9,
        },
        "full_matrix_row_count": 52,
        "inapplicable_instance_count": 8,
    }

    assert [row["encoding_id"] for row in rows[:4]] == list(
        BASELINE_ENCODING_IDS
    )
    assert {row["graph_id"] for row in rows[:4]} == {
        "icosphere_l0"
    }


def test_only_icosphere_cartesian_rows_are_inapplicable() -> None:
    rows = build_applicability_matrix(GRAPH_RECORDS)
    inapplicable = [
        row
        for row in rows
        if row["applicable"] is False
    ]

    assert len(inapplicable) == 8
    assert all(
        row["family"] == "icosphere_triangulation"
        for row in inapplicable
    )
    assert all(
        row["encoding_id"].startswith("cartesian_coordinate_")
        for row in inapplicable
    )
    assert all(
        row["inapplicable_reason"]
        == CARTESIAN_INAPPLICABLE_REASON
        for row in inapplicable
    )


@pytest.mark.parametrize(
    ("family", "encoding_id", "expected"),
    [
        (
            "icosphere_triangulation",
            "canonical_index_binary",
            True,
        ),
        (
            "icosphere_triangulation",
            "canonical_index_gray",
            True,
        ),
        (
            "icosphere_triangulation",
            "cartesian_coordinate_binary",
            False,
        ),
        (
            "primitive_integer_directions",
            "cartesian_coordinate_gray",
            True,
        ),
    ],
)
def test_individual_applicability_rules(
    family: str,
    encoding_id: str,
    expected: bool,
) -> None:
    applicable, reason = encoding_is_applicable(
        graph_family=family,
        encoding_id=encoding_id,
    )

    assert applicable is expected
    assert (reason is None) is expected


def test_duplicate_graph_identifiers_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        build_applicability_matrix(
            [
                GRAPH_RECORDS[0],
                GRAPH_RECORDS[0],
            ]
        )


def test_unknown_graph_family_or_encoder_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported graph family"):
        encoding_is_applicable(
            graph_family="unknown",
            encoding_id="canonical_index_binary",
        )

    with pytest.raises(ValueError, match="unsupported baseline"):
        encoding_is_applicable(
            graph_family="icosphere_triangulation",
            encoding_id="unknown",
        )

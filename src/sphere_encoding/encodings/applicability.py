"""Deterministic Stage 3 graph-encoding applicability rules."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

BASELINE_ENCODING_IDS = (
    "canonical_index_binary",
    "canonical_index_gray",
    "cartesian_coordinate_binary",
    "cartesian_coordinate_gray",
)

SUPPORTED_GRAPH_FAMILIES = (
    "icosphere_triangulation",
    "primitive_integer_directions",
)

CARTESIAN_INAPPLICABLE_REASON = (
    "authoritative integer coordinates are unavailable for icosphere graphs"
)


def encoding_is_applicable(
    *,
    graph_family: str,
    encoding_id: str,
) -> tuple[bool, str | None]:
    """Return frozen Stage 3 applicability and any explicit reason."""
    if graph_family not in SUPPORTED_GRAPH_FAMILIES:
        raise ValueError(f"unsupported graph family: {graph_family}")
    if encoding_id not in BASELINE_ENCODING_IDS:
        raise ValueError(f"unsupported baseline encoding: {encoding_id}")

    if encoding_id.startswith("canonical_index_"):
        return True, None

    if graph_family == "primitive_integer_directions":
        return True, None

    return False, CARTESIAN_INAPPLICABLE_REASON


def build_applicability_matrix(
    graph_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build graph-major, encoder-minor applicability rows."""
    if len(graph_records) == 0:
        raise ValueError("graph_records must not be empty")

    graph_ids: list[str] = []
    rows: list[dict[str, Any]] = []

    for record in graph_records:
        try:
            graph_id = str(record["graph_id"])
            family = str(record["family"])
        except KeyError as exc:
            raise ValueError(
                f"graph record is missing required field: {exc.args[0]}"
            ) from exc

        if not graph_id:
            raise ValueError("graph_id must not be empty")
        if family not in SUPPORTED_GRAPH_FAMILIES:
            raise ValueError(f"unsupported graph family: {family}")

        graph_ids.append(graph_id)

        for encoding_id in BASELINE_ENCODING_IDS:
            applicable, reason = encoding_is_applicable(
                graph_family=family,
                encoding_id=encoding_id,
            )
            rows.append(
                {
                    "applicable": applicable,
                    "encoding_id": encoding_id,
                    "family": family,
                    "graph_id": graph_id,
                    "inapplicable_reason": reason,
                }
            )

    duplicate_graph_ids = sorted(
        graph_id
        for graph_id, count in Counter(graph_ids).items()
        if count > 1
    )
    if duplicate_graph_ids:
        raise ValueError(
            f"duplicate graph identifiers: {duplicate_graph_ids}"
        )

    return rows


def validate_frozen_stage3_applicability(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate the frozen 52-row, 44-applicable Stage 3 matrix."""
    if len(rows) != 52:
        raise ValueError("Stage 3 applicability matrix must contain 52 rows")

    applicable_rows = [
        row
        for row in rows
        if row["applicable"] is True
    ]
    inapplicable_rows = [
        row
        for row in rows
        if row["applicable"] is False
    ]

    if len(applicable_rows) != 44:
        raise ValueError("Stage 3 must contain 44 applicable instances")
    if len(inapplicable_rows) != 8:
        raise ValueError("Stage 3 must contain eight inapplicable instances")

    counts = Counter(
        str(row["encoding_id"])
        for row in applicable_rows
    )
    expected_counts = {
        "canonical_index_binary": 13,
        "canonical_index_gray": 13,
        "cartesian_coordinate_binary": 9,
        "cartesian_coordinate_gray": 9,
    }

    if dict(counts) != expected_counts:
        raise ValueError(
            "applicable instance counts differ from the frozen rules"
        )

    if any(
        row["inapplicable_reason"] is not None
        for row in applicable_rows
    ):
        raise ValueError("applicable row has an inapplicable reason")

    if any(
        row["inapplicable_reason"] != CARTESIAN_INAPPLICABLE_REASON
        for row in inapplicable_rows
    ):
        raise ValueError("inapplicable row has an unexpected reason")

    return {
        "applicable_instance_count": len(applicable_rows),
        "applicable_instance_counts_by_encoding": expected_counts,
        "full_matrix_row_count": len(rows),
        "inapplicable_instance_count": len(inapplicable_rows),
    }

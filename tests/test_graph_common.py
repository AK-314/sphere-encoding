from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.graphs.common import (
    canonical_edges_from_faces,
    distinct_tolerance_classes,
    lexicographically_sorted_rows,
    minimum_bits,
    normalise_rows,
)


@pytest.mark.parametrize(
    ("vertex_count", "expected"),
    [(1, 0), (2, 1), (12, 4), (42, 6), (162, 8), (642, 10)],
)
def test_minimum_bits(vertex_count: int, expected: int) -> None:
    assert minimum_bits(vertex_count) == expected


def test_normalise_rows_produces_unit_float64_rows() -> None:
    rows = normalise_rows([[3, 0, 0], [0, -4, 0]])

    assert rows.dtype == np.float64
    assert np.array_equal(rows, np.asarray([[1, 0, 0], [0, -1, 0]]))


def test_canonical_edges_from_faces_is_unique_and_sorted() -> None:
    faces = np.asarray([[2, 0, 1], [2, 1, 3]], dtype=np.int64)

    edges = canonical_edges_from_faces(faces)

    assert edges.tolist() == [
        [0, 1],
        [0, 2],
        [1, 2],
        [1, 3],
        [2, 3],
    ]
    assert lexicographically_sorted_rows(edges)


def test_distinct_tolerance_classes_clusters_near_values() -> None:
    values = np.asarray([1.0, 1.0 + 1e-13, 2.0])

    assert distinct_tolerance_classes(values, atol=1e-12) == 2

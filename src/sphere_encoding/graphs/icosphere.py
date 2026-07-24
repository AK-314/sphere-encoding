"""Deterministic recursively subdivided icosphere construction."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np

from sphere_encoding.graphs.common import (
    FloatArray,
    IntArray,
    canonical_edges_from_faces,
    face_orientation_values,
    normalise_rows,
)


@dataclass(frozen=True)
class Icosphere:
    """A canonical triangular icosphere mesh."""

    subdivision_level: int
    vertices: FloatArray
    edges: IntArray
    faces: IntArray

    @property
    def graph_id(self) -> str:
        return f"icosphere_l{self.subdivision_level}"


def _base_icosahedron() -> tuple[FloatArray, IntArray]:
    phi = (1.0 + sqrt(5.0)) / 2.0
    vertices = normalise_rows(
        [
            (-1.0, phi, 0.0),
            (1.0, phi, 0.0),
            (-1.0, -phi, 0.0),
            (1.0, -phi, 0.0),
            (0.0, -1.0, phi),
            (0.0, 1.0, phi),
            (0.0, -1.0, -phi),
            (0.0, 1.0, -phi),
            (phi, 0.0, -1.0),
            (phi, 0.0, 1.0),
            (-phi, 0.0, -1.0),
            (-phi, 0.0, 1.0),
        ]
    )
    faces = np.asarray(
        [
            (0, 11, 5),
            (0, 5, 1),
            (0, 1, 7),
            (0, 7, 10),
            (0, 10, 11),
            (1, 5, 9),
            (5, 11, 4),
            (11, 10, 2),
            (10, 7, 6),
            (7, 1, 8),
            (3, 9, 4),
            (3, 4, 2),
            (3, 2, 6),
            (3, 6, 8),
            (3, 8, 9),
            (4, 9, 5),
            (2, 4, 11),
            (6, 2, 10),
            (8, 6, 7),
            (9, 8, 1),
        ],
        dtype=np.int64,
    )
    return vertices, _orient_faces_outward(vertices, faces)


def _orient_faces_outward(vertices: FloatArray, faces: IntArray) -> IntArray:
    result = np.asarray(faces, dtype=np.int64).copy()
    orientation = face_orientation_values(vertices, result)

    for index, value in enumerate(orientation):
        if value < 0.0:
            result[index, 1], result[index, 2] = (
                result[index, 2],
                result[index, 1],
            )

    return result


def _subdivide(
    vertices: FloatArray,
    faces: IntArray,
) -> tuple[FloatArray, IntArray]:
    vertex_list = [row.copy() for row in vertices]
    midpoint_indices: dict[tuple[int, int], int] = {}
    child_faces: list[tuple[int, int, int]] = []

    def midpoint_index(left: int, right: int) -> int:
        key = tuple(sorted((left, right)))
        existing = midpoint_indices.get(key)
        if existing is not None:
            return existing

        midpoint = vertices[left] + vertices[right]
        midpoint /= np.linalg.norm(midpoint)
        index = len(vertex_list)
        vertex_list.append(np.asarray(midpoint, dtype=np.float64))
        midpoint_indices[key] = index
        return index

    for a_value, b_value, c_value in faces:
        a = int(a_value)
        b = int(b_value)
        c = int(c_value)
        ab = midpoint_index(a, b)
        bc = midpoint_index(b, c)
        ca = midpoint_index(c, a)

        child_faces.extend(
            [
                (a, ab, ca),
                (b, bc, ab),
                (c, ca, bc),
                (ab, bc, ca),
            ]
        )

    new_vertices = np.asarray(vertex_list, dtype=np.float64)
    new_faces = np.asarray(child_faces, dtype=np.int64)
    return new_vertices, _orient_faces_outward(new_vertices, new_faces)


def generate_icosphere(subdivision_level: int) -> Icosphere:
    """Generate a canonical icosphere at the requested subdivision level."""
    if isinstance(subdivision_level, bool) or subdivision_level < 0:
        raise ValueError("subdivision_level must be a non-negative integer")

    vertices, faces = _base_icosahedron()
    for _ in range(subdivision_level):
        vertices, faces = _subdivide(vertices, faces)

    edges = canonical_edges_from_faces(faces)
    return Icosphere(
        subdivision_level=subdivision_level,
        vertices=np.asarray(vertices, dtype=np.float64),
        edges=edges,
        faces=np.asarray(faces, dtype=np.int64),
    )

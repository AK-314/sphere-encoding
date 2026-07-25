"""Deterministic CP-SAT feasibility models for exact free codebooks."""

from __future__ import annotations

import hashlib
import tempfile
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ortools.sat.python import cp_model


@dataclass(frozen=True)
class StructuralLowerBound:
    """Elementary graph-theoretic lower-bound evidence."""

    lower_bound: int
    bipartite: bool
    odd_cycle: tuple[int, ...] | None


@dataclass(frozen=True)
class ExactFeasibilityModel:
    """A deterministic threshold-feasibility model and its metadata."""

    model: cp_model.CpModel
    bit_variables: tuple[tuple[cp_model.IntVar, ...], ...]
    code_variables: tuple[cp_model.IntVar, ...]
    xor_variables: tuple[tuple[cp_model.IntVar, ...], ...]
    edges: np.ndarray
    vertex_count: int
    code_length: int
    target_r: int
    symmetry_breaking: bool
    first_neighbour: int | None
    model_sha256: str
    model_bytes: bytes
    variable_count: int
    constraint_count: int


def _normalise_edges(
    vertex_count: int,
    edges: Sequence[Sequence[int]] | np.ndarray,
) -> np.ndarray:
    if not isinstance(vertex_count, int) or isinstance(vertex_count, bool):
        raise TypeError("vertex_count must be an integer")
    if vertex_count < 1:
        raise ValueError("vertex_count must be positive")

    array = np.asarray(edges)
    if array.size == 0:
        return np.empty((0, 2), dtype=np.int64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("edges must have shape (E, 2)")
    if not (
        np.issubdtype(array.dtype, np.integer)
        or np.issubdtype(array.dtype, np.bool_)
    ):
        raise TypeError("edges must use an integer dtype")

    normalised = np.asarray(array, dtype=np.int64)
    if np.any(normalised < 0) or np.any(normalised >= vertex_count):
        raise ValueError("edge endpoint is outside the vertex range")
    if np.any(normalised[:, 0] >= normalised[:, 1]):
        raise ValueError(
            "each undirected edge must be stored canonically with u < v"
        )

    rows = [tuple(int(value) for value in row) for row in normalised]
    if rows != sorted(rows):
        raise ValueError("edges must be lexicographically sorted")
    if len(set(rows)) != len(rows):
        raise ValueError("edges contain duplicates")

    return normalised.copy()


def _adjacency(
    vertex_count: int,
    edges: np.ndarray,
) -> tuple[tuple[int, ...], ...]:
    neighbours: list[list[int]] = [[] for _ in range(vertex_count)]
    for raw_u, raw_v in edges.tolist():
        u = int(raw_u)
        v = int(raw_v)
        neighbours[u].append(v)
        neighbours[v].append(u)

    return tuple(
        tuple(sorted(vertex_neighbours))
        for vertex_neighbours in neighbours
    )


def deterministic_odd_cycle(
    vertex_count: int,
    edges: Sequence[Sequence[int]] | np.ndarray,
) -> tuple[int, ...] | None:
    """Return a deterministic odd-cycle witness, or None if bipartite."""

    edge_array = _normalise_edges(vertex_count, edges)
    adjacency = _adjacency(vertex_count, edge_array)

    colour = [-1] * vertex_count
    parent = [-1] * vertex_count
    depth = [0] * vertex_count

    for start in range(vertex_count):
        if colour[start] != -1:
            continue

        colour[start] = 0
        queue: deque[int] = deque([start])

        while queue:
            u = queue.popleft()

            for v in adjacency[u]:
                if colour[v] == -1:
                    colour[v] = 1 - colour[u]
                    parent[v] = u
                    depth[v] = depth[u] + 1
                    queue.append(v)
                    continue

                if colour[v] != colour[u]:
                    continue

                path_u = [u]
                path_v = [v]
                a = u
                b = v

                while depth[a] > depth[b]:
                    a = parent[a]
                    path_u.append(a)

                while depth[b] > depth[a]:
                    b = parent[b]
                    path_v.append(b)

                while a != b:
                    a = parent[a]
                    b = parent[b]
                    path_u.append(a)
                    path_v.append(b)

                cycle = tuple(path_u + list(reversed(path_v[:-1])))
                if len(cycle) < 3 or len(cycle) % 2 != 1:
                    raise RuntimeError(
                        "internal odd-cycle reconstruction failure"
                    )
                return cycle

    return None


def structural_lower_bound(
    vertex_count: int,
    edges: Sequence[Sequence[int]] | np.ndarray,
) -> StructuralLowerBound:
    """Compute only the frozen distinctness and odd-cycle bounds."""

    edge_array = _normalise_edges(vertex_count, edges)
    if len(edge_array) == 0:
        return StructuralLowerBound(
            lower_bound=0,
            bipartite=True,
            odd_cycle=None,
        )

    odd_cycle = deterministic_odd_cycle(vertex_count, edge_array)
    if odd_cycle is None:
        return StructuralLowerBound(
            lower_bound=1,
            bipartite=True,
            odd_cycle=None,
        )

    return StructuralLowerBound(
        lower_bound=2,
        bipartite=False,
        odd_cycle=odd_cycle,
    )


def _edge_hamming_distances(
    codes: np.ndarray,
    edges: np.ndarray,
) -> np.ndarray:
    if len(edges) == 0:
        return np.empty(0, dtype=np.int64)

    return np.count_nonzero(
        codes[edges[:, 0]] != codes[edges[:, 1]],
        axis=1,
    ).astype(np.int64, copy=False)


def canonicalise_hint_codes(
    codes: Sequence[Sequence[int]] | np.ndarray,
    *,
    edges: Sequence[Sequence[int]] | np.ndarray,
    target_r: int,
) -> np.ndarray:
    """Canonicalise a target-feasible hint under valid Hamming symmetries."""

    array = np.asarray(codes)
    if array.ndim != 2:
        raise ValueError("hint codes must have shape (N, m)")
    if not (
        np.issubdtype(array.dtype, np.integer)
        or np.issubdtype(array.dtype, np.bool_)
    ):
        raise TypeError("hint codes must use Boolean or integer dtype")

    binary = np.asarray(array, dtype=np.uint8)
    if np.any((binary != 0) & (binary != 1)):
        raise ValueError("hint codes must be binary")

    vertex_count, code_length = binary.shape
    if vertex_count < 1:
        raise ValueError("hint codes must contain at least one vertex")
    if code_length < 1:
        raise ValueError("hint code length must be positive")
    if not isinstance(target_r, int) or isinstance(target_r, bool):
        raise TypeError("target_r must be an integer")
    if target_r < 0 or target_r > code_length:
        raise ValueError("target_r must lie between zero and code length")

    edge_array = _normalise_edges(vertex_count, edges)

    packed = np.packbits(binary, axis=1, bitorder="little")
    if len({bytes(row) for row in packed}) != vertex_count:
        raise ValueError("hint codebook must be injective")

    distances = _edge_hamming_distances(binary, edge_array)
    if len(distances) and int(np.max(distances)) > target_r:
        raise ValueError("hint codebook violates the requested target")

    anchored = np.bitwise_xor(binary, binary[0])

    adjacency = _adjacency(vertex_count, edge_array)
    first_neighbour = adjacency[0][0] if adjacency[0] else None
    if first_neighbour is None:
        return anchored

    neighbour_bits = anchored[first_neighbour]
    one_columns = [
        index
        for index, value in enumerate(neighbour_bits.tolist())
        if value == 1
    ]
    zero_columns = [
        index
        for index, value in enumerate(neighbour_bits.tolist())
        if value == 0
    ]
    permutation = one_columns + zero_columns
    canonical = anchored[:, permutation]

    weight = len(one_columns)
    if weight < 1 or weight > target_r:
        raise ValueError(
            "hint cannot satisfy the frozen first-neighbour symmetry"
        )

    expected = np.zeros(code_length, dtype=np.uint8)
    expected[:weight] = 1
    if not np.array_equal(canonical[first_neighbour], expected):
        raise RuntimeError("internal hint canonicalisation failure")

    return canonical


def _model_proto(model: cp_model.CpModel):
    proto_method = getattr(model, "Proto", None)
    if callable(proto_method):
        return proto_method()
    return model.proto


def model_proto_bytes(model: cp_model.CpModel) -> bytes:
    """Export a CP-SAT model in the frozen OR-Tools binary format."""

    with tempfile.TemporaryDirectory(
        prefix="sphere-encoding-cp-sat-model-",
    ) as temporary_name:
        destination = Path(temporary_name) / "model.pb"
        exported = model.export_to_file(str(destination))
        if not exported:
            raise RuntimeError("OR-Tools failed to export the CP-SAT model")
        serialised = destination.read_bytes()

    if not serialised:
        raise RuntimeError("OR-Tools exported an empty CP-SAT model")

    return serialised


def _model_validation_error(model: cp_model.CpModel) -> str:
    validate_method = getattr(model, "Validate", None)
    if callable(validate_method):
        return str(validate_method())
    return str(model.validate())


def build_exact_feasibility_model(
    *,
    vertex_count: int,
    edges: Sequence[Sequence[int]] | np.ndarray,
    code_length: int,
    target_r: int,
    symmetry_breaking: bool = True,
    hint_codes: Sequence[Sequence[int]] | np.ndarray | None = None,
) -> ExactFeasibilityModel:
    """Build the frozen exact threshold-feasibility CP-SAT model."""

    if not isinstance(code_length, int) or isinstance(code_length, bool):
        raise TypeError("code_length must be an integer")
    if code_length < 1:
        raise ValueError("code_length must be positive")
    if not isinstance(target_r, int) or isinstance(target_r, bool):
        raise TypeError("target_r must be an integer")
    if target_r < 0 or target_r > code_length:
        raise ValueError("target_r must lie between zero and code length")
    if not isinstance(symmetry_breaking, bool):
        raise TypeError("symmetry_breaking must be Boolean")

    edge_array = _normalise_edges(vertex_count, edges)
    adjacency = _adjacency(vertex_count, edge_array)
    first_neighbour = adjacency[0][0] if adjacency[0] else None

    canonical_hint = None
    if hint_codes is not None:
        canonical_hint = canonicalise_hint_codes(
            hint_codes,
            edges=edge_array,
            target_r=target_r,
        )
        if canonical_hint.shape != (vertex_count, code_length):
            raise ValueError(
                "hint dimensions differ from vertex_count and code_length"
            )

    model = cp_model.CpModel()

    bit_variables = tuple(
        tuple(
            model.NewBoolVar(f"b_v{vertex}_j{bit}")
            for bit in range(code_length)
        )
        for vertex in range(vertex_count)
    )

    code_variables = tuple(
        model.NewIntVar(
            0,
            (1 << code_length) - 1,
            f"c_v{vertex}",
        )
        for vertex in range(vertex_count)
    )

    for vertex in range(vertex_count):
        model.Add(
            code_variables[vertex]
            == sum(
                (1 << bit) * bit_variables[vertex][bit]
                for bit in range(code_length)
            )
        )

    model.AddAllDifferent(code_variables)

    xor_rows: list[tuple[cp_model.IntVar, ...]] = []
    for edge_index, (raw_u, raw_v) in enumerate(edge_array.tolist()):
        u = int(raw_u)
        v = int(raw_v)
        xor_row = tuple(
            model.NewBoolVar(f"x_e{edge_index}_j{bit}")
            for bit in range(code_length)
        )
        for bit, xor_variable in enumerate(xor_row):
            model.AddAbsEquality(
                xor_variable,
                bit_variables[u][bit] - bit_variables[v][bit],
            )
        model.Add(sum(xor_row) <= target_r)
        xor_rows.append(xor_row)

    if symmetry_breaking:
        model.Add(code_variables[0] == 0)

        if first_neighbour is not None:
            allowed_codes = [
                [(1 << weight) - 1]
                for weight in range(1, target_r + 1)
            ]
            if allowed_codes:
                model.AddAllowedAssignments(
                    [code_variables[first_neighbour]],
                    allowed_codes,
                )
            else:
                model.Add(0 == 1)

    if canonical_hint is not None:
        for vertex in range(vertex_count):
            integer_code = 0
            for bit in range(code_length):
                value = int(canonical_hint[vertex, bit])
                integer_code |= value << bit
                model.AddHint(bit_variables[vertex][bit], value)
            model.AddHint(code_variables[vertex], integer_code)

    validation_error = _model_validation_error(model)
    if validation_error:
        raise ValueError(
            f"constructed CP-SAT model is invalid: {validation_error}"
        )

    proto = _model_proto(model)
    serialised = model_proto_bytes(model)

    return ExactFeasibilityModel(
        model=model,
        bit_variables=bit_variables,
        code_variables=code_variables,
        xor_variables=tuple(xor_rows),
        edges=edge_array,
        vertex_count=vertex_count,
        code_length=code_length,
        target_r=target_r,
        symmetry_breaking=symmetry_breaking,
        first_neighbour=first_neighbour,
        model_sha256=hashlib.sha256(serialised).hexdigest(),
        model_bytes=serialised,
        variable_count=len(proto.variables),
        constraint_count=len(proto.constraints),
    )

"""Threshold-feasibility CP-SAT example for an icosahedron."""

from __future__ import annotations

import numpy as np
from ortools.sat.python import cp_model
from sphere_encoding.graphs.icosphere import generate_icosphere


def build_model(
    edges: np.ndarray,
    *,
    vertex_count: int,
    bit_count: int,
    threshold: int,
) -> tuple[cp_model.CpModel, list[list[cp_model.IntVar]]]:
    """Build the injective threshold-feasibility model."""
    model = cp_model.CpModel()
    bits = [
        [model.NewBoolVar(f"b_{v}_{j}") for j in range(bit_count)]
        for v in range(vertex_count)
    ]
    codes = [
        model.NewIntVar(0, (1 << bit_count) - 1, f"code_{v}")
        for v in range(vertex_count)
    ]

    for v in range(vertex_count):
        model.Add(
            codes[v]
            == sum((1 << j) * bits[v][j] for j in range(bit_count))
        )
    model.AddAllDifferent(codes)

    for edge_index, (u_raw, v_raw) in enumerate(edges):
        u, v = int(u_raw), int(v_raw)
        differences = []
        for j in range(bit_count):
            different = model.NewBoolVar(f"xor_{edge_index}_{j}")
            model.AddAbsEquality(different, bits[u][j] - bits[v][j])
            differences.append(different)
        model.Add(sum(differences) <= threshold)

    # Complementing every bit preserves Hamming distance, so one word may be
    # fixed without changing feasibility.
    model.Add(codes[0] == 0)
    return model, bits


def solve(threshold: int) -> tuple[str, list[str] | None]:
    graph = generate_icosphere(0)
    model, bits = build_model(
        graph.edges,
        vertex_count=len(graph.vertices),
        bit_count=4,
        threshold=threshold,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return solver.StatusName(status), None

    codewords = [
        "".join(str(solver.Value(bit)) for bit in reversed(row))
        for row in bits
    ]
    return solver.StatusName(status), codewords


def main() -> None:
    for threshold in (1, 2):
        status, codewords = solve(threshold)
        print(f"threshold={threshold}: {status}")
        if codewords is not None:
            for vertex, codeword in enumerate(codewords):
                print(f"  {vertex:2d} -> {codeword}")


if __name__ == "__main__":
    main()

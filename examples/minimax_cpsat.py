"""Direct minimax CP-SAT example for an icosahedron."""

from __future__ import annotations

from ortools.sat.python import cp_model
from sphere_encoding.graphs.icosphere import generate_icosphere


def main() -> None:
    graph = generate_icosphere(0)
    vertex_count = len(graph.vertices)
    bit_count = 4

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
    model.Add(codes[0] == 0)

    worst_edge_distance = model.NewIntVar(0, bit_count, "L_max")
    for edge_index, (u_raw, v_raw) in enumerate(graph.edges):
        u, v = int(u_raw), int(v_raw)
        differences = []
        for j in range(bit_count):
            different = model.NewBoolVar(f"xor_{edge_index}_{j}")
            model.AddAbsEquality(different, bits[u][j] - bits[v][j])
            differences.append(different)
        model.Add(sum(differences) <= worst_edge_distance)

    model.Minimize(worst_edge_distance)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.Solve(model)
    print(f"status: {solver.StatusName(status)}")
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return

    print(f"minimum worst edge distance: {solver.Value(worst_edge_distance)}")
    for vertex, row in enumerate(bits):
        codeword = "".join(
            str(solver.Value(bit)) for bit in reversed(row)
        )
        print(f"  {vertex:2d} -> {codeword}")


if __name__ == "__main__":
    main()

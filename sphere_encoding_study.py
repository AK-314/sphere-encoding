#!/usr/bin/env python3

"""
Finite-precision sphere-encoding mini-study.

The experiment:

1. Construct primitive integer directions on S^2.
2. Connect each point to its nearest angular neighbours.
3. Encode the points using Cartesian binary and Cartesian Gray codes.
4. Keep all codes unique while swapping them between sphere points.
5. Search for an assignment with smaller local Hamming changes.

Example:

    uv run python sphere_encoding_study.py --steps 10000 --seeds 1
"""

from __future__ import annotations

import argparse
import itertools
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def gray(value: int) -> int:
    """Return the binary-reflected Gray code of a non-negative integer."""
    return value ^ (value >> 1)


def int_to_bits(value: int, width: int) -> np.ndarray:
    """Convert an integer to a fixed-width bit vector."""
    return np.array(
        [
            (value >> position) & 1
            for position in range(width - 1, -1, -1)
        ],
        dtype=np.uint8,
    )


def primitive_sphere_points(
    q: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate primitive integer vectors in [-q,q]^3 and normalise them.

    Vectors such as (1,1,0) and (2,2,0) represent the same direction.
    Requiring gcd=1 removes these duplicate representations.

    Opposite vectors are retained because they are different oriented points
    on the sphere.
    """
    integer_vectors: list[tuple[int, int, int]] = []
    unit_vectors: list[np.ndarray] = []

    for vector_tuple in itertools.product(
        range(-q, q + 1),
        repeat=3,
    ):
        if vector_tuple == (0, 0, 0):
            continue

        divisor = math.gcd(
            math.gcd(
                abs(vector_tuple[0]),
                abs(vector_tuple[1]),
            ),
            abs(vector_tuple[2]),
        )

        if divisor != 1:
            continue

        vector = np.array(vector_tuple, dtype=float)

        integer_vectors.append(vector_tuple)
        unit_vectors.append(vector / np.linalg.norm(vector))

    return (
        np.array(integer_vectors, dtype=int),
        np.array(unit_vectors, dtype=float),
    )


def angular_distance_matrix(points: np.ndarray) -> np.ndarray:
    """
    Return angular distances divided by pi.

    Values therefore lie between 0 and 1.
    """
    dot_products = np.clip(points @ points.T, -1.0, 1.0)
    return np.arccos(dot_products) / np.pi


def symmetric_knn_edges(
    distances: np.ndarray,
    k: int,
) -> np.ndarray:
    """
    Create a symmetric k-nearest-neighbour graph.

    An undirected edge is included when either point selects the other.
    """
    edge_set: set[tuple[int, int]] = set()

    for point_index in range(len(distances)):
        neighbours = np.argsort(
            distances[point_index]
        )[1 : k + 1]

        for neighbour_index in neighbours:
            first, second = sorted(
                (point_index, int(neighbour_index))
            )
            edge_set.add((first, second))

    return np.array(sorted(edge_set), dtype=int)


def cartesian_codes(
    integer_vectors: np.ndarray,
    q: int,
    use_gray: bool,
) -> np.ndarray:
    """Encode x, y and z separately, then concatenate their bits."""
    bits_per_coordinate = math.ceil(
        math.log2(2 * q + 1)
    )

    encoded_vectors: list[list[int]] = []

    for vector in integer_vectors:
        encoded_row: list[int] = []

        for coordinate in vector:
            shifted_value = int(coordinate + q)

            if use_gray:
                shifted_value = gray(shifted_value)

            encoded_row.extend(
                int_to_bits(
                    shifted_value,
                    bits_per_coordinate,
                ).tolist()
            )

        encoded_vectors.append(encoded_row)

    return np.array(encoded_vectors, dtype=np.uint8)


def edge_hamming_distances(
    codes: np.ndarray,
    edges: np.ndarray,
) -> np.ndarray:
    """Hamming distances on all geometric-neighbour edges."""
    return np.sum(
        codes[edges[:, 0]] != codes[edges[:, 1]],
        axis=1,
    )


def all_pair_global_metrics(
    codes: np.ndarray,
    angular_distances: np.ndarray,
) -> tuple[float, float, float]:
    """
    Compare normalised Hamming distances with angular distances.

    These metrics are calculated only for final assignments, not during
    every optimisation step.
    """
    point_count = len(codes)
    upper_triangle = np.triu_indices(point_count, 1)

    hamming_matrix = np.sum(
        codes[:, None, :] != codes[None, :, :],
        axis=2,
    )

    hamming_distances = (
        hamming_matrix[upper_triangle] / codes.shape[1]
    )
    angular_values = angular_distances[upper_triangle]

    spearman = pd.Series(angular_values).corr(
        pd.Series(hamming_distances),
        method="spearman",
    )

    mean_absolute_error = float(
        np.mean(
            np.abs(
                angular_values - hamming_distances
            )
        )
    )

    maximum_error = float(
        np.max(
            np.abs(
                angular_values - hamming_distances
            )
        )
    )

    return (
        float(spearman),
        mean_absolute_error,
        maximum_error,
    )


@dataclass(frozen=True)
class LocalScore:
    l_max: int
    maximum_edge_count: int
    violations_above_four: int
    excess_above_four: int
    l_95: float
    l_mean: float


def local_score(
    codes: np.ndarray,
    edges: np.ndarray,
) -> LocalScore:
    distances = edge_hamming_distances(codes, edges)
    maximum = int(distances.max())

    violations = distances > 4

    return LocalScore(
        l_max=maximum,
        maximum_edge_count=int(
            np.count_nonzero(distances == maximum)
        ),
        violations_above_four=int(
            np.count_nonzero(violations)
        ),
        excess_above_four=int(
            np.sum(np.maximum(distances - 4, 0))
        ),
        l_95=float(np.quantile(distances, 0.95)),
        l_mean=float(distances.mean()),
    )


def scalar_energy(score: LocalScore) -> float:
    """
    Turn the lexicographic score into an annealing energy.

    The large gaps preserve the intended priority order.
    """
    # Stage-one feasibility objective:
    # first eliminate all neighbour edges with Hamming distance above 4.
    # Mean distance matters only weakly until feasibility is achieved.
    return (
        100000.0 * score.violations_above_four
        + 1000.0 * score.excess_above_four
        + score.l_mean
    )


def result_row(
    name: str,
    codes: np.ndarray,
    edges: np.ndarray,
    angular_distances: np.ndarray,
) -> dict[str, float | int | str]:
    local_distances = edge_hamming_distances(
        codes,
        edges,
    )

    unique_codes = {
        tuple(row.tolist())
        for row in codes
    }

    spearman, global_mae, global_max_error = (
        all_pair_global_metrics(
            codes,
            angular_distances,
        )
    )

    return {
        "encoding": name,
        "bits": int(codes.shape[1]),
        "collisions": int(
            len(codes) - len(unique_codes)
        ),
        "L_max": int(local_distances.max()),
        "max_edge_count": int(
            np.count_nonzero(
                local_distances
                == local_distances.max()
            )
        ),
        "L_95": float(
            np.quantile(local_distances, 0.95)
        ),
        "L_mean": float(local_distances.mean()),
        "spearman_angular_hamming": spearman,
        "mean_abs_global_error": global_mae,
        "max_global_error": global_max_error,
    }


def optimise_by_swaps(
    initial_codes: np.ndarray,
    edges: np.ndarray,
    steps: int,
    seed: int,
    start_temperature: float,
    end_temperature: float,
    report_every: int,
) -> tuple[np.ndarray, LocalScore]:
    """
    Reassign existing unique codes by swapping two point labels at a time.

    Swapping preserves injectivity automatically.
    """
    rng = np.random.default_rng(seed)

    codes = initial_codes.copy()
    current_score = local_score(codes, edges)
    current_energy = scalar_energy(current_score)

    best_codes = codes.copy()
    best_score = current_score
    best_energy = current_energy

    for step in range(1, steps + 1):
        first, second = rng.choice(
            len(codes),
            size=2,
            replace=False,
        )

        codes[[first, second]] = codes[[second, first]]

        candidate_score = local_score(codes, edges)
        candidate_energy = scalar_energy(candidate_score)

        progress = step / steps
        temperature = start_temperature * (
            end_temperature / start_temperature
        ) ** progress

        energy_change = (
            candidate_energy - current_energy
        )

        if energy_change <= 0:
            accept = True
        else:
            acceptance_probability = math.exp(
                -energy_change
                / max(temperature, 1e-12)
            )
            accept = (
                rng.random()
                < acceptance_probability
            )

        if accept:
            current_score = candidate_score
            current_energy = candidate_energy

            if candidate_energy < best_energy:
                best_score = candidate_score
                best_energy = candidate_energy
                best_codes = codes.copy()
        else:
            codes[[first, second]] = codes[[second, first]]

        if (
            report_every > 0
            and step % report_every == 0
        ):
            print(
                f"step={step:,} | "
                f"current Lmax={current_score.l_max}, "
                f"violations>4={current_score.violations_above_four}, "
                f"mean={current_score.l_mean:.3f} | "
                f"best Lmax={best_score.l_max}, "
                f"violations>4={best_score.violations_above_four}, "
                f"mean={best_score.l_mean:.3f}"
            )

    return best_codes, best_score


def plot_local_boxplot(
    named_codes: list[tuple[str, np.ndarray]],
    edges: np.ndarray,
    output_path: Path,
) -> None:
    labels = [
        name
        for name, _ in named_codes
    ]

    values = [
        edge_hamming_distances(codes, edges)
        for _, codes in named_codes
    ]

    plt.figure(figsize=(9, 5))
    plt.boxplot(
        values,
        tick_labels=labels,
        showfliers=True,
    )
    plt.ylabel(
        "Hamming distance on neighbour edges"
    )
    plt.title(
        "Local bit changes on the finite sphere"
    )
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def plot_local_distribution(
    named_codes: list[tuple[str, np.ndarray]],
    edges: np.ndarray,
    output_path: Path,
) -> None:
    plt.figure(figsize=(8, 5))

    for name, codes in named_codes:
        values = edge_hamming_distances(
            codes,
            edges,
        )

        proportions = (
            pd.Series(values)
            .value_counts(normalize=True)
            .sort_index()
        )

        plt.plot(
            proportions.index,
            proportions.values,
            marker="o",
            label=name,
        )

    plt.xlabel(
        "Neighbour-edge Hamming distance"
    )
    plt.ylabel("Proportion of neighbour edges")
    plt.title("Distribution of local bit changes")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--q",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--k",
        type=int,
        default=6,
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=100_000,
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--start-temperature",
        type=float,
        default=100.0,
    )
    parser.add_argument(
        "--end-temperature",
        type=float,
        default=0.01,
    )
    parser.add_argument(
        "--report-every",
        type=int,
        default=10_000,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sphere_encoding_output"),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    integer_vectors, sphere_points = (
        primitive_sphere_points(args.q)
    )

    angular_distances = (
        angular_distance_matrix(sphere_points)
    )

    edges = symmetric_knn_edges(
        angular_distances,
        args.k,
    )

    binary_codes = cartesian_codes(
        integer_vectors,
        args.q,
        use_gray=False,
    )

    gray_codes = cartesian_codes(
        integer_vectors,
        args.q,
        use_gray=True,
    )

    bit_count = gray_codes.shape[1]

    if len(sphere_points) > 2**bit_count:
        raise ValueError(
            f"{len(sphere_points)} points cannot fit "
            f"injectively into {bit_count} bits."
        )

    gray_unique_count = len(
        {
            tuple(row.tolist())
            for row in gray_codes
        }
    )

    if gray_unique_count != len(gray_codes):
        raise RuntimeError(
            "The starting Cartesian Gray encoding "
            "is not injective."
        )

    print(
        f"Sphere points: {len(sphere_points)}"
    )
    print(
        f"Neighbour edges: {len(edges)}"
    )
    print(
        f"Code length: {bit_count} bits"
    )
    print(
        f"Cartesian Gray starting score: "
        f"{local_score(gray_codes, edges)}"
    )

    best_codes: np.ndarray | None = None
    best_score: LocalScore | None = None

    for seed in range(args.seeds):
        print(
            f"\n=== Optimisation seed {seed} ==="
        )

        candidate_codes, candidate_score = (
            optimise_by_swaps(
                initial_codes=gray_codes,
                edges=edges,
                steps=args.steps,
                seed=seed,
                start_temperature=(
                    args.start_temperature
                ),
                end_temperature=args.end_temperature,
                report_every=args.report_every,
            )
        )

        if (
            best_score is None
            or candidate_score < best_score
        ):
            best_score = candidate_score
            best_codes = candidate_codes.copy()

    if best_codes is None or best_score is None:
        raise RuntimeError(
            "Optimisation produced no result."
        )

    rows = [
        result_row(
            "Cartesian binary",
            binary_codes,
            edges,
            angular_distances,
        ),
        result_row(
            "Cartesian Gray",
            gray_codes,
            edges,
            angular_distances,
        ),
        result_row(
            "Injective swap optimiser",
            best_codes,
            edges,
            angular_distances,
        ),
    ]

    results = pd.DataFrame(rows)

    results.to_csv(
        args.output / "results.csv",
        index=False,
    )

    np.save(
        args.output / "integer_vectors.npy",
        integer_vectors,
    )
    np.save(
        args.output / "sphere_points.npy",
        sphere_points,
    )
    np.save(
        args.output / "edges.npy",
        edges,
    )
    np.save(
        args.output / "cartesian_gray_codes.npy",
        gray_codes,
    )
    np.save(
        args.output / "best_codes.npy",
        best_codes,
    )

    named_codes = [
        ("Cartesian binary", binary_codes),
        ("Cartesian Gray", gray_codes),
        ("Injective optimiser", best_codes),
    ]

    plot_local_boxplot(
        named_codes,
        edges,
        args.output / "local_boxplot.png",
    )

    plot_local_distribution(
        named_codes,
        edges,
        args.output / "local_distribution.png",
    )

    print("\n=== Final results ===")
    print(results.to_string(index=False))

    print(
        "\nBest optimiser score:",
        best_score,
    )

    print(
        "\nOutputs saved to:",
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()

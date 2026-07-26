#!/usr/bin/env python3
"""Regenerate the interim-report tables from accepted project artifacts."""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

STAGE2_RUN_ID = "stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50"
STAGE3_RUN_ID = "stage3-deterministic-baselines-3fad68b97de9-f07ae893574e"
STAGE4_RUN_ID = "stage4-exact-free-codebook-97021c6cac03-7adb5b49f2cb"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    root = args.repository_root.resolve()
    out = (args.output_dir or root / "results" / "tables" / "report").resolve()
    out.mkdir(parents=True, exist_ok=True)

    graph_path = root / "results" / "raw" / STAGE2_RUN_ID / "graph_summary.csv"
    stage3_path = root / "results" / "tables" / f"{STAGE3_RUN_ID}_baseline_summary.csv"
    bounds_path = root / "results" / "tables" / f"{STAGE4_RUN_ID}_instance_bounds.csv"

    graphs = read_rows(graph_path)
    stage3 = read_rows(stage3_path)
    bounds = read_rows(bounds_path)

    graph_rows: list[dict[str, object]] = []
    for row in graphs:
        if row["family"] == "icosphere_triangulation":
            parameter = f"level {row['subdivision_level']}"
            neighbours = "closed-sphere triangulation adjacency"
        else:
            parameter = f"q={row['q']}, k={row['nominal_k']}"
            neighbours = "tie-complete symmetric angular k-nearest neighbours"
        graph_rows.append(
            {
                "graph_id": row["graph_id"],
                "family": row["family"],
                "resolution_parameter": parameter,
                "vertices": row["vertex_count"],
                "edges": row["edge_count"],
                "minimum_injective_bits": row["minimum_bits"],
                "neighbour_definition": neighbours,
            }
        )
    write_rows(
        out / "table1_graph_families.csv",
        list(graph_rows[0]),
        graph_rows,
    )

    selected: list[dict[str, object]] = []
    for row in stage3:
        is_ico = row["family"] == "icosphere_triangulation" and row["encoding_id"] == "canonical_index_gray"
        is_primitive = row["family"] == "primitive_integer_directions" and row["encoding_id"] == "cartesian_coordinate_gray"
        if not (is_ico or is_primitive):
            continue
        selected.append(
            {
                "graph_id": row["graph_id"],
                "code_length": row["code_length"],
                "baseline_method": row["encoding_id"],
                "L_max": row["L_max"],
                "mean_local_Hamming_distance": f"{float(row['L_mean']):.3f}",
                "Spearman_angular_Hamming_correlation": f"{float(row['spearman_angular_hamming_correlation']):.3f}",
                "mean_absolute_global_distortion": f"{float(row['mean_absolute_distortion']):.3f}",
            }
        )
    write_rows(out / "table2_selected_deterministic_baselines.csv", list(selected[0]), selected)
    shutil.copyfile(stage3_path, out / "appendix_full_stage3_baseline_summary.csv")

    exact_rows: list[dict[str, object]] = []
    bounded_rows: list[dict[str, object]] = []
    interval_rows: list[dict[str, object]] = []
    for row in bounds:
        interval_rows.append(
            {
                "execution_order": row["execution_order"],
                "graph_id": row["graph_id"],
                "code_length": row["code_length"],
                "lower_bound": row["final_lower_bound"],
                "upper_bound": row["final_upper_bound"],
                "classification": row["classification"],
            }
        )
        if row["classification"] == "exact":
            exact_rows.append(
                {
                    "graph_id": row["graph_id"],
                    "code_length": row["code_length"],
                    "Stage_3_upper_bound": row["baseline_upper_bound"],
                    "Stage_4_optimum": row["final_upper_bound"],
                    "improvement": int(row["baseline_upper_bound"]) - int(row["final_upper_bound"]),
                }
            )
        else:
            bounded_rows.append(
                {
                    "graph_id": row["graph_id"],
                    "code_length": row["code_length"],
                    "pre_Stage_4_upper_bound": row["baseline_upper_bound"],
                    "Stage_4_lower_bound": row["final_lower_bound"],
                    "Stage_4_upper_bound": row["final_upper_bound"],
                    "classification": row["classification"],
                }
            )
    write_rows(out / "table3_exact_stage4_optima.csv", list(exact_rows[0]), exact_rows)
    write_rows(out / "table4_stage4_bounded_instances.csv", list(bounded_rows[0]), bounded_rows)
    write_rows(out / "stage4_complete_intervals.csv", list(interval_rows[0]), interval_rows)

    headline = [
        {
            "graph_id": "primitive_q2_knn4",
            "code_length": 9,
            "method": "Cartesian-coordinate Gray",
            "status": "deterministic baseline",
            "L_max": 3,
        },
        {
            "graph_id": "primitive_q2_knn4",
            "code_length": 9,
            "method": "unrestricted injective codebook",
            "status": "exact optimum",
            "L_max": 2,
        },
    ]
    write_rows(out / "table5_headline_same_rate_comparison.csv", list(headline[0]), headline)

    sys.path.insert(0, str(root / "src"))
    from sphere_encoding.heuristic.planning import build_stage5_plan

    plan = build_stage5_plan(root)
    stage5_rows = [
        {"measure": "global graph-length pairs", "value": plan.global_grid_pair_count},
        {"measure": "direct Stage 4 exact pairs excluded", "value": plan.direct_stage4_exact_pair_count},
        {"measure": "Stage 5 candidates", "value": plan.candidate_instance_count},
        {"measure": "search-required candidates", "value": plan.search_required_instance_count},
        {"measure": "exact by zero-padding transfer", "value": plan.exact_by_transfer_instance_count},
        {"measure": "unresolved targets", "value": plan.unresolved_target_count},
    ]
    write_rows(out / "table6_current_stage5_scope.csv", ["measure", "value"], stage5_rows)

    claim_rows = [
        {
            "claim": "Nine Stage 4 graph-length instances have exact unrestricted optimum 2.",
            "evidence": f"results/tables/{STAGE4_RUN_ID}_exact_optima.csv (9 rows)",
            "audit_status": "verified",
            "required_qualification": "Finite frozen graph-length instances only.",
        },
        {
            "claim": "The 42-vertex icosphere has exact optimum 2 at six bits.",
            "evidence": f"results/tables/{STAGE4_RUN_ID}_instance_bounds.csv; icosphere_l1,m=6",
            "audit_status": "verified",
            "required_qualification": "Unrestricted lookup-table codebook; six bits is the injective minimum.",
        },
        {
            "claim": "Cartesian Gray is not locally optimal on primitive_q2_knn4 at nine bits.",
            "evidence": f"results/tables/{STAGE3_RUN_ID}_baseline_summary.csv and {STAGE4_RUN_ID}_exact_optima.csv",
            "audit_status": "verified",
            "required_qualification": "Same frozen graph and code length; no universal or asymptotic claim.",
        },
        {
            "claim": "Stage 5 is scientifically complete.",
            "evidence": "No definitive Stage 5 manifest or result package exists at report commit.",
            "audit_status": "prohibited",
            "required_qualification": "Describe infrastructure and planned scope only.",
        },
        {
            "claim": "The full Stage 4 solver workload was independently rerun.",
            "evidence": "No second full solver execution is recorded.",
            "audit_status": "prohibited",
            "required_qualification": "Witnesses can be independently verified without rerunning the workload.",
        },
    ]
    write_rows(out / "scientific_claim_audit.csv", list(claim_rows[0]), claim_rows)

    print(f"wrote {len(list(out.glob('*.csv')))} report tables to {out}")


if __name__ == "__main__":
    main()

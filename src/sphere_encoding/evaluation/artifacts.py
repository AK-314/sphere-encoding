"""Deterministic Stage 3 baseline-evaluation package construction."""

from __future__ import annotations

import csv
import io
import json
import re
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from sphere_encoding.config import (
    canonical_json_dumps,
    config_sha256,
    pretty_json_dumps,
)
from sphere_encoding.encodings import (
    BASELINE_ENCODING_IDS,
    build_applicability_matrix,
    canonical_index_binary,
    canonical_index_gray,
    cartesian_coordinate_binary,
    cartesian_coordinate_gray,
    collision_diagnostics,
    validate_frozen_stage3_applicability,
)
from sphere_encoding.graphs.artifacts import (
    collect_file_hashes,
    read_npy,
    write_npy,
)
from sphere_encoding.graphs.common import minimum_bits
from sphere_encoding.hashing import sha256_bytes, sha256_file
from sphere_encoding.metrics import (
    antipodal_hamming_metrics,
    antipodal_pair_indices,
    bit_balance_diagnostics,
    bit_redundancy_diagnostics,
    edge_hamming_distances,
    exhaustive_unordered_pairs,
    far_pair_metrics,
    global_distortion_metrics,
    hamming_distances_for_pairs,
    local_hamming_metrics,
    normalised_angular_distances,
)
from sphere_encoding.provenance import atomic_write_text

SUMMARY_FIELDS = (
    "graph_id",
    "family",
    "encoding_id",
    "vertex_count",
    "edge_count",
    "code_length",
    "minimum_injective_length",
    "excess_bits",
    "L_max",
    "L_max_edge_count",
    "L_99",
    "L_95",
    "L_mean",
    "L_standard_deviation",
    "L_minimum",
    "unordered_pair_count",
    "spearman_angular_hamming_correlation",
    "mean_absolute_distortion",
    "root_mean_squared_distortion",
    "maximum_absolute_distortion",
    "mean_normalised_hamming_distance",
    "mean_normalised_angular_distance",
    "far_pair_count",
    "far_minimum_raw_hamming_distance",
    "far_mean_raw_hamming_distance",
    "far_minimum_normalised_hamming_distance",
    "far_mean_normalised_hamming_distance",
    "antipodal_pair_count",
    "antipodal_minimum_raw_hamming_distance",
    "antipodal_maximum_raw_hamming_distance",
    "antipodal_mean_raw_hamming_distance",
    "antipodal_minimum_normalised_hamming_distance",
    "antipodal_mean_normalised_hamming_distance",
    "collision_count",
    "unique_codeword_count",
    "largest_collision_class_size",
    "multi_member_collision_class_count",
    "constant_bit_count",
    "maximum_absolute_deviation_from_half",
    "mean_absolute_deviation_from_half",
    "duplicate_bit_column_pair_count",
    "complementary_bit_column_pair_count",
    "maximum_absolute_pearson_correlation",
)

HISTOGRAM_FIELDS = (
    "graph_id",
    "family",
    "encoding_id",
    "code_length",
    "hamming_distance",
    "edge_count",
    "edge_fraction",
)

APPLICABILITY_FIELDS = (
    "graph_id",
    "family",
    "encoding_id",
    "applicable",
    "inapplicable_reason",
)

SAFE_RUN_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
FROZEN_STAGE3_CONFIG_SHA256 = (
    "3fad68b97de95f82cbf65d31c9dc10d0"
    "39efd375a9cf0f29f1a79396dbf77896"
)


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _csv_text(
    rows: Sequence[Mapping[str, Any]],
    *,
    fieldnames: Sequence[str],
) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=fieldnames,
        lineterminator="\n",
    )
    writer.writeheader()

    for row in rows:
        writer.writerow(
            {
                field: _csv_value(row.get(field))
                for field in fieldnames
            }
        )

    return stream.getvalue()


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read JSON object {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")

    return value


def _validate_run_id(run_id: str) -> None:
    if SAFE_RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError(
            "run_id must contain only lowercase letters, digits and hyphens"
        )


def _validate_stage2_package(
    config: Mapping[str, Any],
    stage2_root: Path,
) -> dict[str, Any]:
    if not stage2_root.is_dir():
        raise ValueError(
            f"Stage 2 package root is not a directory: {stage2_root}"
        )

    metadata_path = stage2_root / "package_metadata.json"
    metadata = _load_json_object(metadata_path)
    expected_input = config["input"]

    if metadata.get("stage") != 2:
        raise ValueError("input package is not a Stage 2 package")

    if (
        metadata.get("config_sha256")
        != expected_input["stage2_configuration_sha256"]
    ):
        raise ValueError("Stage 2 configuration hash differs from freeze")

    if (
        metadata.get("package_tree_sha256")
        != expected_input["stage2_package_tree_sha256"]
    ):
        raise ValueError("Stage 2 package-tree hash differs from freeze")

    deterministic_files = metadata.get("deterministic_files")
    if not isinstance(deterministic_files, dict):
        raise ValueError("Stage 2 deterministic file map is invalid")

    if len(deterministic_files) != 80:
        raise ValueError("Stage 2 deterministic file map must contain 80 files")

    calculated_tree_hash = sha256_bytes(
        canonical_json_dumps(deterministic_files).encode("utf-8")
    )
    if calculated_tree_hash != metadata["package_tree_sha256"]:
        raise ValueError("Stage 2 package metadata tree hash is inconsistent")

    expected_paths = sorted(
        [*deterministic_files, "package_metadata.json"]
    )
    actual_paths = sorted(
        path.relative_to(stage2_root).as_posix()
        for path in stage2_root.rglob("*")
        if path.is_file()
    )

    if actual_paths != expected_paths:
        raise ValueError("Stage 2 loose-package file set is not exact")

    hash_mismatches = [
        relative_path
        for relative_path, expected_hash in sorted(
            deterministic_files.items()
        )
        if sha256_file(stage2_root / relative_path) != expected_hash
    ]
    if hash_mismatches:
        raise ValueError(
            "Stage 2 deterministic file hashes differ from metadata: "
            f"{hash_mismatches}"
        )

    graph_ids = metadata.get("graph_ids")
    if graph_ids != config["applicability"]["graph_ids"]:
        raise ValueError("Stage 2 graph order differs from Stage 3 freeze")

    if metadata.get("graph_count") != 13:
        raise ValueError("Stage 2 package must contain 13 graphs")

    return metadata


def _load_graph(
    stage2_root: Path,
    graph_id: str,
    *,
    stage2_config_hash: str,
) -> dict[str, Any]:
    graph_root = stage2_root / graph_id
    metadata = _load_json_object(graph_root / "metadata.json")

    if metadata.get("graph_id") != graph_id:
        raise ValueError(f"graph metadata identifier mismatch: {graph_id}")
    if metadata.get("stage") != 2:
        raise ValueError(f"graph metadata stage mismatch: {graph_id}")
    if metadata.get("config_sha256") != stage2_config_hash:
        raise ValueError(f"graph configuration hash mismatch: {graph_id}")

    vertices = read_npy(graph_root / "vertices.npy")
    edges = read_npy(graph_root / "edges.npy")
    diagnostics = metadata["diagnostics"]

    if vertices.shape != (diagnostics["vertex_count"], 3):
        raise ValueError(f"vertex shape mismatch: {graph_id}")
    if vertices.dtype != np.float64:
        raise ValueError(f"vertex dtype mismatch: {graph_id}")
    if edges.shape != (diagnostics["edge_count"], 2):
        raise ValueError(f"edge shape mismatch: {graph_id}")
    if edges.dtype != np.int64:
        raise ValueError(f"edge dtype mismatch: {graph_id}")

    minimum_length = minimum_bits(len(vertices))
    if minimum_length != diagnostics["minimum_bits"]:
        raise ValueError(f"minimum-bit diagnostic mismatch: {graph_id}")

    result: dict[str, Any] = {
        "antipodal_pair_count": diagnostics["antipodal_pair_count"],
        "edges": edges,
        "family": metadata["family"],
        "graph_id": graph_id,
        "metadata": metadata,
        "minimum_injective_length": minimum_length,
        "vertices": vertices,
    }

    if metadata["family"] == "primitive_integer_directions":
        integer_vectors = read_npy(graph_root / "integer_vectors.npy")
        q = metadata["construction"]["q"]

        if integer_vectors.shape != vertices.shape:
            raise ValueError(f"integer-vector shape mismatch: {graph_id}")
        if integer_vectors.dtype != np.int64:
            raise ValueError(f"integer-vector dtype mismatch: {graph_id}")
        if np.any(np.abs(integer_vectors) > q):
            raise ValueError(f"integer coordinate outside [-q,q]: {graph_id}")

        result["integer_vectors"] = integer_vectors
        result["q"] = q

    return result


def _build_codes(
    graph: Mapping[str, Any],
    *,
    encoding_id: str,
) -> npt.NDArray[np.uint8]:
    vertex_count = len(graph["vertices"])

    if encoding_id == "canonical_index_binary":
        return canonical_index_binary(vertex_count)
    if encoding_id == "canonical_index_gray":
        return canonical_index_gray(vertex_count)
    if encoding_id == "cartesian_coordinate_binary":
        return cartesian_coordinate_binary(
            graph["integer_vectors"],
            q=graph["q"],
        )
    if encoding_id == "cartesian_coordinate_gray":
        return cartesian_coordinate_gray(
            graph["integer_vectors"],
            q=graph["q"],
        )

    raise ValueError(f"unsupported encoding identifier: {encoding_id}")


def _summary_row(metrics: Mapping[str, Any]) -> dict[str, Any]:
    local = metrics["local"]
    global_metrics = metrics["global"]
    far = metrics["far_pairs"]
    antipodal = metrics["antipodal_pairs"]
    collisions = metrics["collision_diagnostics"]
    balance = metrics["bit_balance"]
    redundancy = metrics["bit_redundancy"]
    lengths = metrics["code_length"]

    return {
        "L_95": local["L_95"],
        "L_99": local["L_99"],
        "L_max": local["L_max"],
        "L_max_edge_count": local["L_max_edge_count"],
        "L_mean": local["L_mean"],
        "L_minimum": local["L_minimum"],
        "L_standard_deviation": local["L_standard_deviation"],
        "antipodal_maximum_raw_hamming_distance": antipodal[
            "maximum_raw_hamming_distance"
        ],
        "antipodal_mean_normalised_hamming_distance": antipodal[
            "mean_normalised_hamming_distance"
        ],
        "antipodal_mean_raw_hamming_distance": antipodal[
            "mean_raw_hamming_distance"
        ],
        "antipodal_minimum_normalised_hamming_distance": antipodal[
            "minimum_normalised_hamming_distance"
        ],
        "antipodal_minimum_raw_hamming_distance": antipodal[
            "minimum_raw_hamming_distance"
        ],
        "antipodal_pair_count": antipodal["antipodal_pair_count"],
        "code_length": lengths["m"],
        "collision_count": collisions["collision_count"],
        "complementary_bit_column_pair_count": redundancy[
            "complementary_bit_column_pair_count"
        ],
        "constant_bit_count": balance["constant_bit_count"],
        "duplicate_bit_column_pair_count": redundancy[
            "duplicate_bit_column_pair_count"
        ],
        "edge_count": metrics["graph"]["edge_count"],
        "encoding_id": metrics["encoding_id"],
        "excess_bits": lengths["excess_bits"],
        "family": metrics["graph"]["family"],
        "far_mean_normalised_hamming_distance": far[
            "mean_normalised_hamming_distance"
        ],
        "far_mean_raw_hamming_distance": far[
            "mean_raw_hamming_distance"
        ],
        "far_minimum_normalised_hamming_distance": far[
            "minimum_normalised_hamming_distance"
        ],
        "far_minimum_raw_hamming_distance": far[
            "minimum_raw_hamming_distance"
        ],
        "far_pair_count": far["far_pair_count"],
        "graph_id": metrics["graph"]["graph_id"],
        "largest_collision_class_size": collisions[
            "largest_collision_class_size"
        ],
        "maximum_absolute_deviation_from_half": balance[
            "maximum_absolute_deviation_from_half"
        ],
        "maximum_absolute_distortion": global_metrics[
            "maximum_absolute_distortion"
        ],
        "maximum_absolute_pearson_correlation": redundancy[
            "maximum_absolute_pearson_correlation"
        ],
        "mean_absolute_deviation_from_half": balance[
            "mean_absolute_deviation_from_half"
        ],
        "mean_absolute_distortion": global_metrics[
            "mean_absolute_distortion"
        ],
        "mean_normalised_angular_distance": global_metrics[
            "mean_normalised_angular_distance"
        ],
        "mean_normalised_hamming_distance": global_metrics[
            "mean_normalised_hamming_distance"
        ],
        "minimum_injective_length": lengths["m0"],
        "multi_member_collision_class_count": collisions[
            "multi_member_collision_class_count"
        ],
        "root_mean_squared_distortion": global_metrics[
            "root_mean_squared_distortion"
        ],
        "spearman_angular_hamming_correlation": global_metrics[
            "spearman_angular_hamming_correlation"
        ],
        "unique_codeword_count": collisions["unique_codeword_count"],
        "unordered_pair_count": global_metrics["unordered_pair_count"],
        "vertex_count": metrics["graph"]["vertex_count"],
    }


def _histogram_rows(
    metrics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    local = metrics["local"]
    edge_count = local["edge_count"]

    return [
        {
            "code_length": metrics["code_length"]["m"],
            "edge_count": count,
            "edge_fraction": count / edge_count,
            "encoding_id": metrics["encoding_id"],
            "family": metrics["graph"]["family"],
            "graph_id": metrics["graph"]["graph_id"],
            "hamming_distance": distance,
        }
        for distance, count in enumerate(local["histogram"])
    ]


def _evaluate_instance(
    *,
    config: Mapping[str, Any],
    config_hash: str,
    graph: Mapping[str, Any],
    encoding_id: str,
    codes: npt.NDArray[np.uint8],
    output_root: Path,
    pair_indices: npt.NDArray[np.int64],
    angular_distances: npt.NDArray[np.float64],
    antipodal_pairs: npt.NDArray[np.int64],
) -> dict[str, Any]:
    instance_root = output_root / graph["graph_id"] / encoding_id
    instance_root.mkdir(parents=True)

    local_distances = edge_hamming_distances(codes, graph["edges"])
    global_hamming = hamming_distances_for_pairs(codes, pair_indices)
    antipodal_hamming = hamming_distances_for_pairs(
        codes,
        antipodal_pairs,
    )

    code_length = codes.shape[1]
    minimum_length = graph["minimum_injective_length"]

    collisions = collision_diagnostics(codes)
    if collisions["collision_count"] != 0:
        raise RuntimeError(
            f"definitive baseline is not injective: "
            f"{graph['graph_id']} / {encoding_id}"
        )

    write_npy(instance_root / "codes.npy", codes)
    write_npy(
        instance_root / "local_edge_hamming.npy",
        local_distances,
    )

    array_files = {
        "codes.npy": sha256_file(instance_root / "codes.npy"),
        "local_edge_hamming.npy": sha256_file(
            instance_root / "local_edge_hamming.npy"
        ),
    }

    metrics = {
        "antipodal_pairs": antipodal_hamming_metrics(
            antipodal_hamming,
            code_length=code_length,
        ),
        "array_files": array_files,
        "bit_balance": bit_balance_diagnostics(codes),
        "bit_redundancy": bit_redundancy_diagnostics(codes),
        "code_length": {
            "excess_bits": code_length - minimum_length,
            "m": code_length,
            "m0": minimum_length,
        },
        "collision_diagnostics": collisions,
        "config_sha256": config_hash,
        "encoding_definition": config["baseline_encodings"][
            encoding_id
        ],
        "encoding_id": encoding_id,
        "far_pairs": far_pair_metrics(
            angular_distances,
            global_hamming,
            code_length=code_length,
            threshold=config["far_pairs"]["threshold"],
        ),
        "global": global_distortion_metrics(
            angular_distances,
            global_hamming,
            code_length=code_length,
        ),
        "graph": {
            "edge_count": len(graph["edges"]),
            "family": graph["family"],
            "graph_id": graph["graph_id"],
            "vertex_count": len(graph["vertices"]),
        },
        "local": local_hamming_metrics(
            local_distances,
            code_length=code_length,
        ),
        "schema_version": 1,
        "stage": 3,
        "stage2_run_id": config["input"]["stage2_run_id"],
        "stage_name": config["stage_name"],
        "validity": {
            "binary": True,
            "canonical_vertex_row_order": True,
            "injective": True,
        },
    }

    atomic_write_text(
        instance_root / "metrics.json",
        pretty_json_dumps(metrics),
    )
    return metrics


def generate_stage3_package(
    config: Mapping[str, Any],
    *,
    stage2_package_root: str | Path,
    output_root: str | Path,
    table_root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Generate deterministic Stage 3 raw outputs and three CSV tables."""
    _validate_run_id(run_id)

    destination = Path(output_root)
    tables = Path(table_root)
    stage2_root = Path(stage2_package_root)

    if destination.exists():
        raise FileExistsError(
            f"artifact directory already exists: {destination}"
        )

    config_hash = config_sha256(config)
    if config_hash != FROZEN_STAGE3_CONFIG_SHA256:
        raise ValueError(
            "configuration differs from the frozen Stage 3 configuration"
        )

    metadata = _validate_stage2_package(config, stage2_root)

    if tuple(config["baseline_encodings"]["encoding_ids"]) != (
        BASELINE_ENCODING_IDS
    ):
        raise ValueError("baseline encoding order differs from implementation")

    suffixes = config["outputs"]
    table_paths = {
        "applicability": tables
        / f"{run_id}{suffixes['applicability_table_suffix']}",
        "baseline_summary": tables
        / f"{run_id}{suffixes['baseline_summary_table_suffix']}",
        "local_histograms": tables
        / f"{run_id}{suffixes['local_histogram_table_suffix']}",
    }

    for table_path in table_paths.values():
        if table_path.exists():
            raise FileExistsError(
                f"table destination already exists: {table_path}"
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    tables.mkdir(parents=True, exist_ok=True)

    generated_table_paths: list[Path] = []

    try:
        graph_records = []
        graphs: dict[str, dict[str, Any]] = {}

        for graph_id in metadata["graph_ids"]:
            graph = _load_graph(
                stage2_root,
                graph_id,
                stage2_config_hash=config["input"][
                    "stage2_configuration_sha256"
                ],
            )
            graphs[graph_id] = graph
            graph_records.append(
                {
                    "family": graph["family"],
                    "graph_id": graph_id,
                }
            )

        applicability_rows = build_applicability_matrix(graph_records)
        applicability_diagnostics = (
            validate_frozen_stage3_applicability(applicability_rows)
        )

        summary_rows: list[dict[str, Any]] = []
        histogram_rows: list[dict[str, Any]] = []
        instance_paths: list[str] = []

        for graph_id in metadata["graph_ids"]:
            graph = graphs[graph_id]
            pair_indices = exhaustive_unordered_pairs(
                len(graph["vertices"])
            )
            angular_distances = normalised_angular_distances(
                graph["vertices"],
                pair_indices,
            )
            antipodal_pairs = antipodal_pair_indices(
                graph["vertices"],
                atol=config["antipodal_pairs"]["accepted_stage2_atol"],
                expected_count=graph["antipodal_pair_count"],
                require_complete_pairing=True,
            )

            graph_rows = [
                row
                for row in applicability_rows
                if row["graph_id"] == graph_id
            ]

            for row in graph_rows:
                if row["applicable"] is not True:
                    continue

                encoding_id = row["encoding_id"]
                codes = _build_codes(
                    graph,
                    encoding_id=encoding_id,
                )
                metrics = _evaluate_instance(
                    config=config,
                    config_hash=config_hash,
                    graph=graph,
                    encoding_id=encoding_id,
                    codes=codes,
                    output_root=destination,
                    pair_indices=pair_indices,
                    angular_distances=angular_distances,
                    antipodal_pairs=antipodal_pairs,
                )

                summary_rows.append(_summary_row(metrics))
                histogram_rows.extend(_histogram_rows(metrics))
                instance_paths.append(f"{graph_id}/{encoding_id}")

        if len(instance_paths) != 44:
            raise RuntimeError(
                f"expected 44 applicable instances, got {len(instance_paths)}"
            )

        atomic_write_text(
            table_paths["applicability"],
            _csv_text(
                applicability_rows,
                fieldnames=APPLICABILITY_FIELDS,
            ),
        )
        generated_table_paths.append(table_paths["applicability"])

        atomic_write_text(
            table_paths["baseline_summary"],
            _csv_text(
                summary_rows,
                fieldnames=SUMMARY_FIELDS,
            ),
        )
        generated_table_paths.append(table_paths["baseline_summary"])

        atomic_write_text(
            table_paths["local_histograms"],
            _csv_text(
                histogram_rows,
                fieldnames=HISTOGRAM_FIELDS,
            ),
        )
        generated_table_paths.append(table_paths["local_histograms"])

        deterministic_files = collect_file_hashes(destination)
        if len(deterministic_files) != 132:
            raise RuntimeError(
                "expected 132 instance files before package metadata, "
                f"got {len(deterministic_files)}"
            )

        package_tree_hash = sha256_bytes(
            canonical_json_dumps(deterministic_files).encode("utf-8")
        )
        table_files = {
            table_path.name: sha256_file(table_path)
            for table_path in sorted(table_paths.values())
        }
        table_set_hash = sha256_bytes(
            canonical_json_dumps(table_files).encode("utf-8")
        )

        package_metadata = {
            "applicability_row_count": applicability_diagnostics[
                "full_matrix_row_count"
            ],
            "applicable_instance_count": applicability_diagnostics[
                "applicable_instance_count"
            ],
            "config_sha256": config_hash,
            "deterministic_file_count_without_package_metadata": len(
                deterministic_files
            ),
            "deterministic_files": deterministic_files,
            "encoding_ids": list(BASELINE_ENCODING_IDS),
            "graph_count": len(metadata["graph_ids"]),
            "graph_ids": metadata["graph_ids"],
            "inapplicable_instance_count": applicability_diagnostics[
                "inapplicable_instance_count"
            ],
            "instance_paths": instance_paths,
            "package_tree_sha256": package_tree_hash,
            "run_id": run_id,
            "schema_version": 1,
            "stage": 3,
            "stage2": {
                "config_sha256": config["input"][
                    "stage2_configuration_sha256"
                ],
                "package_tree_sha256": config["input"][
                    "stage2_package_tree_sha256"
                ],
                "run_id": config["input"]["stage2_run_id"],
            },
            "stage_name": config["stage_name"],
            "table_file_count": len(table_files),
            "table_files": table_files,
            "table_set_sha256": table_set_hash,
        }

        atomic_write_text(
            destination / "package_metadata.json",
            pretty_json_dumps(package_metadata),
        )

        all_package_files = collect_file_hashes(destination)
        if len(all_package_files) != 133:
            raise RuntimeError(
                "expected 133 package files including package metadata, "
                f"got {len(all_package_files)}"
            )

        return {
            "applicability_row_count": len(applicability_rows),
            "applicable_instance_count": len(instance_paths),
            "config_sha256": config_hash,
            "file_count": len(all_package_files),
            "files": all_package_files,
            "graph_count": len(metadata["graph_ids"]),
            "graph_ids": metadata["graph_ids"],
            "histogram_row_count": len(histogram_rows),
            "inapplicable_instance_count": 8,
            "instance_paths": instance_paths,
            "package_tree_sha256": package_tree_hash,
            "run_id": run_id,
            "summary_row_count": len(summary_rows),
            "table_file_count": len(table_files),
            "table_files": table_files,
            "table_set_sha256": table_set_hash,
        }
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        for table_path in generated_table_paths:
            table_path.unlink(missing_ok=True)
        raise

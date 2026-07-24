"""Deterministic serialization for canonical Stage 2 graph artifacts."""

from __future__ import annotations

import csv
import gzip
import io
import shutil
import tarfile
from collections.abc import Mapping, Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from sphere_encoding.config import (
    canonical_json_dumps,
    config_sha256,
    pretty_json_dumps,
)
from sphere_encoding.graphs.icosphere import generate_icosphere
from sphere_encoding.graphs.primitive import (
    build_primitive_direction_graph,
)
from sphere_encoding.graphs.validation import (
    validate_icosphere,
    validate_primitive_graph,
)
from sphere_encoding.hashing import sha256_bytes, sha256_file
from sphere_encoding.provenance import (
    atomic_write_bytes,
    atomic_write_text,
)

SUMMARY_FIELDS = (
    "graph_id",
    "family",
    "q",
    "nominal_k",
    "subdivision_level",
    "vertex_count",
    "edge_count",
    "face_count",
    "minimum_bits",
    "minimum_degree",
    "maximum_degree",
    "antipodal_pair_count",
    "edge_length_class_count",
    "tie_completion_extra_selection_total",
    "symmetrisation_degree_gain_total",
)


def npy_bytes(array: npt.ArrayLike) -> bytes:
    """Serialize an array to deterministic NumPy NPY bytes."""
    stream = io.BytesIO()
    np.save(
        stream,
        np.asarray(array),
        allow_pickle=False,
    )
    return stream.getvalue()


def write_npy(
    file_path: str | Path,
    array: npt.ArrayLike,
) -> None:
    """Write a NumPy array atomically with pickling disabled."""
    atomic_write_bytes(file_path, npy_bytes(array))


def read_npy(file_path: str | Path) -> np.ndarray[Any, Any]:
    """Read an NPY array with pickling disabled."""
    with Path(file_path).open("rb") as stream:
        return np.load(stream, allow_pickle=False)


def flatten_neighbours(
    neighbours: Sequence[Sequence[int]],
) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]]:
    """Convert ragged neighbour rows into deterministic offsets and indices."""
    offsets = np.zeros(len(neighbours) + 1, dtype=np.int64)
    flattened: list[int] = []

    for row_index, row in enumerate(neighbours):
        flattened.extend(int(value) for value in row)
        offsets[row_index + 1] = len(flattened)

    return offsets, np.asarray(flattened, dtype=np.int64)


def unflatten_neighbours(
    offsets: npt.ArrayLike,
    indices: npt.ArrayLike,
) -> tuple[tuple[int, ...], ...]:
    """Reconstruct ragged neighbour rows from offsets and indices."""
    offset_array = np.asarray(offsets, dtype=np.int64)
    index_array = np.asarray(indices, dtype=np.int64)

    if offset_array.ndim != 1 or index_array.ndim != 1:
        raise ValueError("offsets and indices must be one-dimensional")
    if len(offset_array) == 0 or int(offset_array[0]) != 0:
        raise ValueError("offsets must begin at zero")
    if np.any(offset_array[1:] < offset_array[:-1]):
        raise ValueError("offsets must be non-decreasing")
    if int(offset_array[-1]) != len(index_array):
        raise ValueError("final offset must equal index count")

    rows = []
    for start, stop in pairwise(offset_array):
        rows.append(
            tuple(
                int(value)
                for value in index_array[int(start) : int(stop)]
            )
        )

    return tuple(rows)


def collect_file_hashes(
    root_path: str | Path,
) -> dict[str, str]:
    """Hash every regular file below a root in relative-path order."""
    root = Path(root_path)
    if not root.is_dir():
        raise ValueError(f"artifact root is not a directory: {root}")

    result: dict[str, str] = {}
    for file_path in sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
    ):
        relative = file_path.relative_to(root).as_posix()
        result[relative] = sha256_file(file_path)

    return result


def _write_metadata(
    file_path: Path,
    metadata: Mapping[str, Any],
) -> None:
    atomic_write_text(
        file_path,
        pretty_json_dumps(dict(metadata)),
    )


def _summary_csv(rows: Sequence[Mapping[str, Any]]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=SUMMARY_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: row.get(field, "")
                for field in SUMMARY_FIELDS
            }
        )
    return stream.getvalue()


def generate_stage2_package(
    config: Mapping[str, Any],
    output_root: str | Path,
) -> dict[str, Any]:
    """Generate the deterministic 13-graph Stage 2 package."""
    destination = Path(output_root)
    if destination.exists():
        raise FileExistsError(
            f"artifact directory already exists: {destination}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()

    config_hash = config_sha256(config)
    tolerances = dict(config["tolerances"])
    summary_rows: list[dict[str, Any]] = []
    graph_ids: list[str] = []

    try:
        primary_instances = sorted(
            config["primary"]["expected_instances"].items(),
            key=lambda item: item[1]["subdivision_level"],
        )

        for graph_id, expected_value in primary_instances:
            expected = dict(expected_value)
            mesh = generate_icosphere(expected["subdivision_level"])
            diagnostics = validate_icosphere(
                mesh,
                tolerances=tolerances,
                expected=expected,
            )

            graph_directory = destination / graph_id
            graph_directory.mkdir()

            arrays = {
                "edges.npy": mesh.edges,
                "faces.npy": mesh.faces,
                "vertices.npy": mesh.vertices,
            }
            for filename, array in arrays.items():
                write_npy(graph_directory / filename, array)

            array_hashes = {
                filename: sha256_file(graph_directory / filename)
                for filename in sorted(arrays)
            }

            metadata = {
                "array_files": array_hashes,
                "config_sha256": config_hash,
                "construction": {
                    "canonical_ordering": config["primary"][
                        "canonical_ordering"
                    ],
                    "subdivision_level": mesh.subdivision_level,
                },
                "diagnostics": diagnostics,
                "family": config["primary"]["family"],
                "graph_id": graph_id,
                "schema_version": 1,
                "stage": 2,
            }
            _write_metadata(
                graph_directory / "metadata.json",
                metadata,
            )

            graph_ids.append(graph_id)
            summary_rows.append(
                {
                    "antipodal_pair_count": diagnostics[
                        "antipodal_pair_count"
                    ],
                    "edge_count": diagnostics["edge_count"],
                    "edge_length_class_count": diagnostics[
                        "edge_length_class_count"
                    ],
                    "face_count": diagnostics["face_count"],
                    "family": config["primary"]["family"],
                    "graph_id": graph_id,
                    "maximum_degree": diagnostics["maximum_degree"],
                    "minimum_bits": diagnostics["minimum_bits"],
                    "minimum_degree": diagnostics["minimum_degree"],
                    "subdivision_level": mesh.subdivision_level,
                    "vertex_count": diagnostics["vertex_count"],
                }
            )

        secondary = config["secondary"]
        for q in secondary["coordinate_bounds"]:
            for nominal_k in secondary["nominal_k_values"]:
                graph = build_primitive_direction_graph(
                    q,
                    nominal_k,
                    angular_tie_atol_radians=tolerances[
                        "angular_tie_atol_radians"
                    ],
                )
                diagnostics = validate_primitive_graph(
                    graph,
                    tolerances=tolerances,
                    expected_point_count=secondary[
                        "expected_point_counts"
                    ][str(q)],
                )

                graph_directory = destination / graph.graph_id
                graph_directory.mkdir()

                offsets, indices = flatten_neighbours(
                    graph.directed_neighbours
                )
                arrays = {
                    "directed_indices.npy": indices,
                    "directed_offsets.npy": offsets,
                    "edges.npy": graph.edges,
                    "integer_vectors.npy": graph.integer_vectors,
                    "threshold_angles.npy": graph.threshold_angles,
                    "vertices.npy": graph.vertices,
                }
                for filename, array in arrays.items():
                    write_npy(graph_directory / filename, array)

                array_hashes = {
                    filename: sha256_file(graph_directory / filename)
                    for filename in sorted(arrays)
                }

                metadata = {
                    "array_files": array_hashes,
                    "config_sha256": config_hash,
                    "construction": {
                        "angular_tie_atol_radians": tolerances[
                            "angular_tie_atol_radians"
                        ],
                        "integer_vector_ordering": secondary[
                            "integer_vector_ordering"
                        ],
                        "neighbourhood": secondary["neighbourhood"],
                        "nominal_k": nominal_k,
                        "opposite_vectors_distinct": secondary[
                            "opposite_vectors_distinct"
                        ],
                        "oriented_vectors": secondary[
                            "oriented_vectors"
                        ],
                        "q": q,
                    },
                    "diagnostics": diagnostics,
                    "family": secondary["family"],
                    "graph_id": graph.graph_id,
                    "schema_version": 1,
                    "stage": 2,
                }
                _write_metadata(
                    graph_directory / "metadata.json",
                    metadata,
                )

                graph_ids.append(graph.graph_id)
                summary_rows.append(
                    {
                        "antipodal_pair_count": diagnostics[
                            "antipodal_pair_count"
                        ],
                        "edge_count": diagnostics["edge_count"],
                        "face_count": "",
                        "family": secondary["family"],
                        "graph_id": graph.graph_id,
                        "maximum_degree": diagnostics[
                            "maximum_degree"
                        ],
                        "minimum_bits": diagnostics["minimum_bits"],
                        "minimum_degree": diagnostics[
                            "minimum_degree"
                        ],
                        "nominal_k": nominal_k,
                        "q": q,
                        "symmetrisation_degree_gain_total": diagnostics[
                            "symmetrisation_degree_gain_total"
                        ],
                        "tie_completion_extra_selection_total": diagnostics[
                            "tie_completion_extra_selection_total"
                        ],
                        "vertex_count": diagnostics["vertex_count"],
                    }
                )

        atomic_write_text(
            destination / "graph_summary.csv",
            _summary_csv(summary_rows),
        )

        deterministic_files = collect_file_hashes(destination)
        tree_hash = sha256_bytes(
            canonical_json_dumps(deterministic_files).encode("utf-8")
        )

        package_metadata = {
            "config_sha256": config_hash,
            "deterministic_file_count_without_package_metadata": len(
                deterministic_files
            ),
            "deterministic_files": deterministic_files,
            "graph_count": len(graph_ids),
            "graph_ids": graph_ids,
            "package_tree_sha256": tree_hash,
            "schema_version": 1,
            "stage": 2,
            "stage_name": config["stage_name"],
        }
        _write_metadata(
            destination / "package_metadata.json",
            package_metadata,
        )

        all_files = collect_file_hashes(destination)
        if len(graph_ids) != 13:
            raise RuntimeError(
                f"expected 13 graphs, generated {len(graph_ids)}"
            )
        if len(all_files) != 81:
            raise RuntimeError(
                f"expected 81 package files, generated {len(all_files)}"
            )

        return {
            "config_sha256": config_hash,
            "file_count": len(all_files),
            "files": all_files,
            "graph_count": len(graph_ids),
            "graph_ids": graph_ids,
            "package_tree_sha256": tree_hash,
        }
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def deterministic_tar_gz_bytes(
    source_root: str | Path,
) -> bytes:
    """Create deterministic tar.gz bytes for all files below a root."""
    root = Path(source_root)
    if not root.is_dir():
        raise ValueError(f"archive source is not a directory: {root}")

    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
    )

    tar_stream = io.BytesIO()
    with tarfile.open(
        fileobj=tar_stream,
        mode="w",
        format=tarfile.GNU_FORMAT,
    ) as archive:
        for file_path in files:
            relative = file_path.relative_to(root).as_posix()
            data = file_path.read_bytes()

            information = tarfile.TarInfo(name=relative)
            information.size = len(data)
            information.mode = 0o644
            information.mtime = 0
            information.uid = 0
            information.gid = 0
            information.uname = ""
            information.gname = ""

            archive.addfile(
                information,
                io.BytesIO(data),
            )

    compressed_stream = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        compresslevel=9,
        fileobj=compressed_stream,
        mtime=0,
    ) as compressed:
        compressed.write(tar_stream.getvalue())

    return compressed_stream.getvalue()


def write_deterministic_tar_gz(
    source_root: str | Path,
    archive_path: str | Path,
) -> None:
    """Write a deterministic archive atomically."""
    atomic_write_bytes(
        archive_path,
        deterministic_tar_gz_bytes(source_root),
    )

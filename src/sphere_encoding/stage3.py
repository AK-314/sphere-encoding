"""Definitive Stage 3 deterministic-baseline workflow."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sphere_encoding.config import (
    config_sha256,
    load_json_config,
)
from sphere_encoding.evaluation.artifacts import (
    generate_stage3_package,
)
from sphere_encoding.graphs.artifacts import (
    write_deterministic_tar_gz,
)
from sphere_encoding.hashing import sha256_file
from sphere_encoding.provenance import (
    atomic_write_bytes,
    build_manifest,
    capture_repository,
    write_manifest,
)


def derive_stage3_run_id(
    config_hash: str,
    implementation_commit: str,
) -> str:
    """Derive the deterministic Stage 3 run identifier."""
    if len(config_hash) != 64:
        raise ValueError("invalid Stage 3 configuration hash")
    if len(implementation_commit) != 40:
        raise ValueError("invalid implementation commit hash")

    return (
        "stage3-deterministic-baselines-"
        f"{config_hash[:12]}-{implementation_commit[:12]}"
    )


def _repository_relative(
    repository: Path,
    path: Path,
) -> str:
    try:
        return path.resolve().relative_to(repository).as_posix()
    except ValueError as exc:
        raise ValueError(
            f"path is outside repository: {path}"
        ) from exc


def _resolve_repository_path(
    repository: Path,
    path_value: str | Path,
) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = repository / path
    return path.resolve()


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"could not read JSON object {path}: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")

    return value


def _validate_stage2_input_identity(
    repository: Path,
    config: Mapping[str, Any],
) -> dict[str, Path]:
    frozen = config["input"]

    package_path = _resolve_repository_path(
        repository,
        frozen["stage2_package_path"],
    )
    archive_path = _resolve_repository_path(
        repository,
        frozen["stage2_archive_path"],
    )
    manifest_path = _resolve_repository_path(
        repository,
        frozen["stage2_manifest_path"],
    )

    if not package_path.is_dir():
        raise ValueError(
            f"accepted Stage 2 package is missing: {package_path}"
        )
    if not archive_path.is_file():
        raise ValueError(
            f"accepted Stage 2 archive is missing: {archive_path}"
        )
    if not manifest_path.is_file():
        raise ValueError(
            f"accepted Stage 2 manifest is missing: {manifest_path}"
        )

    actual_archive_hash = sha256_file(archive_path)
    expected_archive_hash = frozen["stage2_archive_sha256"]

    if actual_archive_hash != expected_archive_hash:
        raise ValueError(
            "accepted Stage 2 archive hash differs from Stage 3 freeze"
        )

    manifest = _load_json_object(manifest_path)
    payload = manifest.get("payload")

    if manifest.get("stage") != 2 or not isinstance(payload, dict):
        raise ValueError("accepted Stage 2 manifest schema is invalid")

    if payload.get("run_id") != frozen["stage2_run_id"]:
        raise ValueError("accepted Stage 2 run identifier differs from freeze")

    manifest_config = payload.get("config")
    manifest_outputs = payload.get("deterministic_outputs")
    manifest_archive = payload.get("archive")

    if not isinstance(manifest_config, dict):
        raise ValueError("accepted Stage 2 config manifest entry is invalid")
    if not isinstance(manifest_outputs, dict):
        raise ValueError("accepted Stage 2 output manifest entry is invalid")
    if not isinstance(manifest_archive, dict):
        raise ValueError("accepted Stage 2 archive manifest entry is invalid")

    if (
        manifest_config.get("sha256")
        != frozen["stage2_configuration_sha256"]
    ):
        raise ValueError(
            "accepted Stage 2 configuration hash differs from freeze"
        )

    if (
        manifest_outputs.get("package_tree_sha256")
        != frozen["stage2_package_tree_sha256"]
    ):
        raise ValueError(
            "accepted Stage 2 package-tree hash differs from freeze"
        )

    if manifest_archive.get("sha256") != expected_archive_hash:
        raise ValueError(
            "accepted Stage 2 manifest archive hash differs from freeze"
        )

    if (
        manifest_outputs.get("directory")
        != frozen["stage2_package_path"]
    ):
        raise ValueError(
            "accepted Stage 2 package path differs from freeze"
        )

    if manifest_archive.get("path") != frozen["stage2_archive_path"]:
        raise ValueError(
            "accepted Stage 2 archive path differs from freeze"
        )

    return {
        "archive": archive_path,
        "manifest": manifest_path,
        "package": package_path,
    }


def _build_archive_root(
    *,
    package_root: Path,
    table_root: Path,
    table_files: Mapping[str, str],
    archive_root: Path,
    run_id: str,
) -> None:
    raw_destination = archive_root / "raw" / run_id
    table_destination = archive_root / "tables"

    shutil.copytree(package_root, raw_destination)
    table_destination.mkdir(parents=True)

    for filename in sorted(table_files):
        source = table_root / filename
        if not source.is_file():
            raise RuntimeError(
                f"generated Stage 3 table is missing: {source}"
            )
        shutil.copyfile(
            source,
            table_destination / filename,
        )


def generate_stage3_artifacts(
    *,
    repository_path: str | Path,
    config_path: str | Path,
    package_root: str | Path,
    table_root: str | Path,
    archive_path: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Generate deterministic Stage 3 package, tables and archive."""
    repository = Path(repository_path).resolve()
    configuration_path = _resolve_repository_path(
        repository,
        config_path,
    )
    configuration = load_json_config(configuration_path)

    inputs = _validate_stage2_input_identity(
        repository,
        configuration,
    )

    package = Path(package_root)
    tables = Path(table_root)
    archive = Path(archive_path)

    if archive.exists():
        raise FileExistsError(
            f"archive destination already exists: {archive}"
        )

    generated = generate_stage3_package(
        configuration,
        stage2_package_root=inputs["package"],
        output_root=package,
        table_root=tables,
        run_id=run_id,
    )

    try:
        with tempfile.TemporaryDirectory(
            prefix=f"{run_id}-archive-",
        ) as temporary_name:
            archive_root = Path(temporary_name) / "contents"
            archive_root.mkdir()

            _build_archive_root(
                package_root=package,
                table_root=tables,
                table_files=generated["table_files"],
                archive_root=archive_root,
                run_id=run_id,
            )
            write_deterministic_tar_gz(
                archive_root,
                archive,
            )
    except Exception:
        shutil.rmtree(package, ignore_errors=True)
        for filename in generated["table_files"]:
            (tables / filename).unlink(missing_ok=True)
        archive.unlink(missing_ok=True)
        raise

    archive_member_count = (
        generated["file_count"] + generated["table_file_count"]
    )

    return {
        **generated,
        "archive_member_count": archive_member_count,
        "archive_sha256": sha256_file(archive),
    }


def install_definitive_stage3_artifacts(
    *,
    repository_path: str | Path,
    config_path: str | Path,
) -> dict[str, Any]:
    """Install definitive Stage 3 outputs from a clean implementation commit."""
    repository = Path(repository_path).resolve()
    configuration_path = _resolve_repository_path(
        repository,
        config_path,
    )
    configuration_relative = _repository_relative(
        repository,
        configuration_path,
    )
    configuration = load_json_config(configuration_path)
    configuration_hash = config_sha256(configuration)

    repository_before = capture_repository(repository)
    if repository_before["clean"] is not True:
        raise ValueError(
            "repository must be clean before definitive Stage 3 generation"
        )

    implementation_commit = str(repository_before["commit"])
    run_id = derive_stage3_run_id(
        configuration_hash,
        implementation_commit,
    )

    outputs = configuration["outputs"]

    final_package = (
        repository / outputs["raw_directory"] / run_id
    )
    final_tables_root = (
        repository / outputs["table_directory"]
    )
    final_archive = (
        repository
        / outputs["results_archive_directory"]
        / f"{run_id}.tar.gz"
    )
    final_manifest = (
        repository
        / outputs["manifest_directory"]
        / f"{run_id}.json"
    )

    table_names = {
        "applicability": (
            f"{run_id}{outputs['applicability_table_suffix']}"
        ),
        "baseline_summary": (
            f"{run_id}{outputs['baseline_summary_table_suffix']}"
        ),
        "local_histograms": (
            f"{run_id}{outputs['local_histogram_table_suffix']}"
        ),
    }
    final_table_paths = {
        key: final_tables_root / filename
        for key, filename in table_names.items()
    }

    destinations = [
        final_package,
        final_archive,
        final_manifest,
        *final_table_paths.values(),
    ]
    for destination in destinations:
        if destination.exists():
            raise FileExistsError(
                f"definitive destination already exists: {destination}"
            )

    with tempfile.TemporaryDirectory(
        prefix=f"{run_id}-",
    ) as temporary_name:
        temporary_root = Path(temporary_name)
        temporary_package = temporary_root / "raw" / run_id
        temporary_tables = temporary_root / "tables"
        temporary_archive = temporary_root / f"{run_id}.tar.gz"

        generated = generate_stage3_artifacts(
            repository_path=repository,
            config_path=configuration_path,
            package_root=temporary_package,
            table_root=temporary_tables,
            archive_path=temporary_archive,
            run_id=run_id,
        )

        package_relative = _repository_relative(
            repository,
            final_package,
        )
        archive_relative = _repository_relative(
            repository,
            final_archive,
        )
        manifest_relative = _repository_relative(
            repository,
            final_manifest,
        )
        table_relatives = {
            key: _repository_relative(repository, path)
            for key, path in final_table_paths.items()
        }

        payload: Mapping[str, Any] = {
            "archive": {
                "member_count": generated["archive_member_count"],
                "path": archive_relative,
                "sha256": generated["archive_sha256"],
            },
            "applicability": {
                "applicable_instance_count": generated[
                    "applicable_instance_count"
                ],
                "full_matrix_row_count": generated[
                    "applicability_row_count"
                ],
                "inapplicable_instance_count": generated[
                    "inapplicable_instance_count"
                ],
            },
            "config": {
                "path": configuration_relative,
                "sha256": configuration_hash,
            },
            "deterministic_outputs": {
                "combined_file_count": (
                    generated["file_count"]
                    + generated["table_file_count"]
                ),
                "raw_package": {
                    "directory": package_relative,
                    "file_count": generated["file_count"],
                    "files": generated["files"],
                    "package_tree_sha256": generated[
                        "package_tree_sha256"
                    ],
                },
                "tables": {
                    "directory": outputs["table_directory"],
                    "file_count": generated["table_file_count"],
                    "files": generated["table_files"],
                    "paths": table_relatives,
                    "table_set_sha256": generated[
                        "table_set_sha256"
                    ],
                },
            },
            "graph_count": generated["graph_count"],
            "graph_ids": generated["graph_ids"],
            "histogram_row_count": generated[
                "histogram_row_count"
            ],
            "implementation_commit": implementation_commit,
            "instance_paths": generated["instance_paths"],
            "manifest_path": manifest_relative,
            "run_id": run_id,
            "stage2_input": {
                "archive_sha256": configuration["input"][
                    "stage2_archive_sha256"
                ],
                "configuration_sha256": configuration["input"][
                    "stage2_configuration_sha256"
                ],
                "package_tree_sha256": configuration["input"][
                    "stage2_package_tree_sha256"
                ],
                "run_id": configuration["input"]["stage2_run_id"],
            },
            "stage_name": configuration["stage_name"],
            "summary_row_count": generated["summary_row_count"],
        }

        manifest = build_manifest(
            stage=3,
            payload=payload,
            repository_path=repository,
            distributions=["numpy", "sphere-encoding"],
        )

        if manifest["repository"]["clean"] is not True:
            raise RuntimeError(
                "repository became dirty before Stage 3 installation"
            )
        if manifest["repository"]["commit"] != implementation_commit:
            raise RuntimeError(
                "repository commit changed during Stage 3 preparation"
            )

        try:
            final_package.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                temporary_package,
                final_package,
            )

            final_tables_root.mkdir(parents=True, exist_ok=True)
            for key, final_path in final_table_paths.items():
                source = temporary_tables / table_names[key]
                atomic_write_bytes(
                    final_path,
                    source.read_bytes(),
                )

            atomic_write_bytes(
                final_archive,
                temporary_archive.read_bytes(),
            )
            write_manifest(
                final_manifest,
                manifest,
            )
        except Exception:
            shutil.rmtree(final_package, ignore_errors=True)
            for table_path in final_table_paths.values():
                table_path.unlink(missing_ok=True)
            final_archive.unlink(missing_ok=True)
            final_manifest.unlink(missing_ok=True)
            raise

    return {
        "archive_member_count": generated["archive_member_count"],
        "archive_path": archive_relative,
        "archive_sha256": generated["archive_sha256"],
        "applicability_row_count": generated[
            "applicability_row_count"
        ],
        "applicable_instance_count": generated[
            "applicable_instance_count"
        ],
        "histogram_row_count": generated["histogram_row_count"],
        "inapplicable_instance_count": generated[
            "inapplicable_instance_count"
        ],
        "manifest_path": manifest_relative,
        "output_directory": package_relative,
        "package_file_count": generated["file_count"],
        "run_id": run_id,
        "summary_row_count": generated["summary_row_count"],
        "table_file_count": generated["table_file_count"],
        "table_paths": table_relatives,
    }

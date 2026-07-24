"""Definitive Stage 2 canonical-graph generation workflow."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sphere_encoding.config import config_sha256, load_json_config
from sphere_encoding.graphs.artifacts import (
    generate_stage2_package,
    write_deterministic_tar_gz,
)
from sphere_encoding.hashing import sha256_file
from sphere_encoding.provenance import (
    atomic_write_bytes,
    build_manifest,
    capture_repository,
    write_manifest,
)


def derive_stage2_run_id(
    config_hash: str,
    implementation_commit: str,
) -> str:
    """Derive the deterministic Stage 2 run identifier."""
    if len(config_hash) != 64 or len(implementation_commit) != 40:
        raise ValueError("invalid configuration or commit hash")
    return (
        f"stage2-canonical-graphs-"
        f"{config_hash[:12]}-{implementation_commit[:12]}"
    )


def generate_stage2_artifacts(
    *,
    config_path: str | Path,
    package_root: str | Path,
    archive_path: str | Path,
) -> dict[str, Any]:
    """Generate deterministic package and archive without provenance."""
    config = load_json_config(config_path)
    package = generate_stage2_package(config, package_root)
    write_deterministic_tar_gz(package_root, archive_path)

    archive_hash = sha256_file(archive_path)
    return {
        **package,
        "archive_sha256": archive_hash,
    }


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


def install_definitive_stage2_artifacts(
    *,
    repository_path: str | Path,
    config_path: str | Path,
) -> dict[str, str]:
    """Generate and install the definitive Stage 2 package and manifest."""
    repository = Path(repository_path).resolve()
    configuration_path = Path(config_path)
    if not configuration_path.is_absolute():
        configuration_path = repository / configuration_path
    configuration_path = configuration_path.resolve()

    configuration_relative = _repository_relative(
        repository,
        configuration_path,
    )
    config = load_json_config(configuration_path)
    config_hash = config_sha256(config)

    repository_before = capture_repository(repository)
    if repository_before["clean"] is not True:
        raise ValueError(
            "repository must be clean before definitive Stage 2 generation"
        )

    implementation_commit = str(repository_before["commit"])
    run_id = derive_stage2_run_id(
        config_hash,
        implementation_commit,
    )

    final_package = repository / "results" / "raw" / run_id
    final_archive = (
        repository / "results" / "archives" / f"{run_id}.tar.gz"
    )
    final_manifest = repository / "manifests" / f"{run_id}.json"

    for destination in (
        final_package,
        final_archive,
        final_manifest,
    ):
        if destination.exists():
            raise FileExistsError(
                f"definitive destination already exists: {destination}"
            )

    with tempfile.TemporaryDirectory(
        prefix=f"{run_id}-",
    ) as temporary_name:
        temporary_root = Path(temporary_name)
        temporary_package = temporary_root / run_id
        temporary_archive = temporary_root / f"{run_id}.tar.gz"

        generated = generate_stage2_artifacts(
            config_path=configuration_path,
            package_root=temporary_package,
            archive_path=temporary_archive,
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

        payload: Mapping[str, Any] = {
            "archive": {
                "member_count": generated["file_count"],
                "path": archive_relative,
                "sha256": generated["archive_sha256"],
            },
            "config": {
                "path": configuration_relative,
                "sha256": config_hash,
            },
            "deterministic_outputs": {
                "directory": package_relative,
                "file_count": generated["file_count"],
                "files": generated["files"],
                "package_tree_sha256": generated[
                    "package_tree_sha256"
                ],
            },
            "graph_count": generated["graph_count"],
            "graph_ids": generated["graph_ids"],
            "implementation_commit": implementation_commit,
            "manifest_path": manifest_relative,
            "run_id": run_id,
            "stage_name": config["stage_name"],
        }

        manifest = build_manifest(
            stage=2,
            payload=payload,
            repository_path=repository,
            distributions=["numpy", "sphere-encoding"],
        )
        if manifest["repository"]["clean"] is not True:
            raise RuntimeError(
                "repository became dirty before artifact installation"
            )
        if manifest["repository"]["commit"] != implementation_commit:
            raise RuntimeError(
                "repository commit changed during artifact preparation"
            )

        try:
            final_package.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                temporary_package,
                final_package,
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
            final_archive.unlink(missing_ok=True)
            final_manifest.unlink(missing_ok=True)
            raise

    return {
        "archive_path": archive_relative,
        "manifest_path": manifest_relative,
        "output_directory": package_relative,
        "run_id": run_id,
    }

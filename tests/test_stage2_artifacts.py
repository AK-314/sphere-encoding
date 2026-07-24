from __future__ import annotations

import gzip
import json
import subprocess
import tarfile
from pathlib import Path

import numpy as np
import pytest

from sphere_encoding.config import load_json_config
from sphere_encoding.graphs.artifacts import (
    collect_file_hashes,
    flatten_neighbours,
    generate_stage2_package,
    npy_bytes,
    read_npy,
    unflatten_neighbours,
    write_deterministic_tar_gz,
    write_npy,
)
from sphere_encoding.hashing import sha256_file
from sphere_encoding.stage2 import (
    derive_stage2_run_id,
    generate_stage2_artifacts,
    install_definitive_stage2_artifacts,
)

CONFIG_PATH = Path("configs/stage2_graph_suite.json")


def run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def initialise_repository(repository: Path) -> str:
    repository.mkdir()
    run_git(repository, "init")
    run_git(repository, "config", "user.name", "Stage Two Test")
    run_git(
        repository,
        "config",
        "user.email",
        "stage2@example.invalid",
    )

    config_destination = (
        repository / "configs" / "stage2_graph_suite.json"
    )
    config_destination.parent.mkdir()
    config_destination.write_bytes(CONFIG_PATH.read_bytes())

    marker = repository / "implementation.txt"
    marker.write_text("committed implementation\n", encoding="utf-8")

    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "implementation")
    return run_git(repository, "rev-parse", "HEAD")


def test_npy_serialization_is_stable_and_pickle_free(
    tmp_path: Path,
) -> None:
    array = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    destination = tmp_path / "array.npy"

    first = npy_bytes(array)
    second = npy_bytes(array)
    assert first == second

    write_npy(destination, array)
    loaded = read_npy(destination)

    assert np.array_equal(loaded, array)
    assert destination.read_bytes() == first


def test_neighbour_flattening_round_trip() -> None:
    neighbours = ((1, 3), (), (0, 4, 7))

    offsets, indices = flatten_neighbours(neighbours)

    assert offsets.tolist() == [0, 2, 2, 5]
    assert indices.tolist() == [1, 3, 0, 4, 7]
    assert unflatten_neighbours(offsets, indices) == neighbours


def test_stage2_package_is_independently_reproducible(
    tmp_path: Path,
) -> None:
    config = load_json_config(CONFIG_PATH)
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first = generate_stage2_package(config, first_root)
    second = generate_stage2_package(config, second_root)

    assert first == second
    assert first["graph_count"] == 13
    assert first["file_count"] == 81
    assert collect_file_hashes(first_root) == collect_file_hashes(
        second_root
    )

    summary_lines = (
        first_root / "graph_summary.csv"
    ).read_text(encoding="utf-8").splitlines()
    assert len(summary_lines) == 14

    package_metadata = json.loads(
        (first_root / "package_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    assert package_metadata["graph_count"] == 13
    assert (
        package_metadata[
            "deterministic_file_count_without_package_metadata"
        ]
        == 80
    )


def test_deterministic_archive_has_exact_member_set(
    tmp_path: Path,
) -> None:
    config = load_json_config(CONFIG_PATH)
    package = tmp_path / "package"
    first_archive = tmp_path / "first.tar.gz"
    second_archive = tmp_path / "second.tar.gz"

    generate_stage2_package(config, package)
    write_deterministic_tar_gz(package, first_archive)
    write_deterministic_tar_gz(package, second_archive)

    assert first_archive.read_bytes() == second_archive.read_bytes()

    with gzip.open(first_archive, "rb") as compressed:
        with tarfile.open(fileobj=compressed, mode="r:") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]

    expected_names = sorted(collect_file_hashes(package))
    assert names == expected_names
    assert len(names) == 81
    assert all(member.isfile() for member in members)
    assert all(member.mtime == 0 for member in members)
    assert all(member.uid == 0 for member in members)
    assert all(member.gid == 0 for member in members)


def test_combined_artifact_generation_is_reproducible(
    tmp_path: Path,
) -> None:
    first_package = tmp_path / "first-package"
    second_package = tmp_path / "second-package"
    first_archive = tmp_path / "first.tar.gz"
    second_archive = tmp_path / "second.tar.gz"

    first = generate_stage2_artifacts(
        config_path=CONFIG_PATH,
        package_root=first_package,
        archive_path=first_archive,
    )
    second = generate_stage2_artifacts(
        config_path=CONFIG_PATH,
        package_root=second_package,
        archive_path=second_archive,
    )

    assert first == second
    assert sha256_file(first_archive) == sha256_file(second_archive)


def test_definitive_install_captures_pre_output_clean_commit(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    implementation_commit = initialise_repository(repository)

    result = install_definitive_stage2_artifacts(
        repository_path=repository,
        config_path="configs/stage2_graph_suite.json",
    )

    expected_run_id = derive_stage2_run_id(
        load_json_config(
            repository / "configs/stage2_graph_suite.json"
        )
        and result["run_id"].split("-")[-2]
        + "0" * 52,
        implementation_commit,
    )
    assert result["run_id"].startswith(
        "stage2-canonical-graphs-"
    )
    assert result["run_id"].endswith(
        implementation_commit[:12]
    )
    assert expected_run_id.endswith(implementation_commit[:12])

    manifest_path = repository / result["manifest_path"]
    archive_path = repository / result["archive_path"]
    output_directory = repository / result["output_directory"]

    assert manifest_path.is_file()
    assert archive_path.is_file()
    assert output_directory.is_dir()
    assert len(collect_file_hashes(output_directory)) == 81

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    assert manifest["stage"] == 2
    assert manifest["repository"]["clean"] is True
    assert manifest["repository"]["commit"] == implementation_commit
    assert manifest["payload"]["graph_count"] == 13
    assert (
        manifest["payload"]["archive"]["sha256"]
        == sha256_file(archive_path)
    )

    assert run_git(repository, "status", "--porcelain")

    with pytest.raises(ValueError, match="must be clean"):
        install_definitive_stage2_artifacts(
            repository_path=repository,
            config_path="configs/stage2_graph_suite.json",
        )

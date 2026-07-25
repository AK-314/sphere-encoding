from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from sphere_encoding.config import (
    config_sha256,
    load_json_config,
)
from sphere_encoding.graphs.artifacts import collect_file_hashes
from sphere_encoding.hashing import sha256_file
from sphere_encoding.stage3 import (
    derive_stage3_run_id,
    generate_stage3_artifacts,
    install_definitive_stage3_artifacts,
)

CONFIG_PATH = Path("configs/stage3_baselines.json")
STAGE2_RUN_ID = (
    "stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50"
)
STAGE2_PACKAGE = Path("results/raw") / STAGE2_RUN_ID
STAGE2_ARCHIVE = (
    Path("results/archives") / f"{STAGE2_RUN_ID}.tar.gz"
)
STAGE2_MANIFEST = (
    Path("manifests") / f"{STAGE2_RUN_ID}.json"
)


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
    run_git(repository, "config", "user.name", "Stage Three Test")
    run_git(
        repository,
        "config",
        "user.email",
        "stage3@example.invalid",
    )

    config_destination = (
        repository / "configs" / "stage3_baselines.json"
    )
    config_destination.parent.mkdir()
    config_destination.write_bytes(CONFIG_PATH.read_bytes())

    package_destination = (
        repository / "results" / "raw" / STAGE2_RUN_ID
    )
    package_destination.parent.mkdir(parents=True)
    shutil.copytree(
        STAGE2_PACKAGE,
        package_destination,
    )

    archive_destination = (
        repository
        / "results"
        / "archives"
        / f"{STAGE2_RUN_ID}.tar.gz"
    )
    archive_destination.parent.mkdir(parents=True)
    archive_destination.write_bytes(STAGE2_ARCHIVE.read_bytes())

    manifest_destination = (
        repository / "manifests" / f"{STAGE2_RUN_ID}.json"
    )
    manifest_destination.parent.mkdir()
    manifest_destination.write_bytes(STAGE2_MANIFEST.read_bytes())

    marker = repository / "implementation.txt"
    marker.write_text(
        "committed Stage 3 implementation\n",
        encoding="utf-8",
    )

    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "implementation")
    return run_git(repository, "rev-parse", "HEAD")


def test_stage3_run_identifier() -> None:
    config_hash = "a" * 64
    commit_hash = "b" * 40

    assert derive_stage3_run_id(
        config_hash,
        commit_hash,
    ) == (
        "stage3-deterministic-baselines-"
        "aaaaaaaaaaaa-bbbbbbbbbbbb"
    )

    with pytest.raises(ValueError, match="configuration"):
        derive_stage3_run_id("short", commit_hash)

    with pytest.raises(ValueError, match="commit"):
        derive_stage3_run_id(config_hash, "short")


def test_combined_stage3_artifacts_are_reproducible(
    tmp_path: Path,
) -> None:
    run_id = "stage3-combined-artifact-test"

    first_package = tmp_path / "first" / "raw" / run_id
    second_package = tmp_path / "second" / "raw" / run_id
    first_tables = tmp_path / "first" / "tables"
    second_tables = tmp_path / "second" / "tables"
    first_archive = tmp_path / "first" / f"{run_id}.tar.gz"
    second_archive = tmp_path / "second" / f"{run_id}.tar.gz"

    first = generate_stage3_artifacts(
        repository_path=Path.cwd(),
        config_path=CONFIG_PATH,
        package_root=first_package,
        table_root=first_tables,
        archive_path=first_archive,
        run_id=run_id,
    )
    second = generate_stage3_artifacts(
        repository_path=Path.cwd(),
        config_path=CONFIG_PATH,
        package_root=second_package,
        table_root=second_tables,
        archive_path=second_archive,
        run_id=run_id,
    )

    assert first == second
    assert first["file_count"] == 133
    assert first["table_file_count"] == 3
    assert first["archive_member_count"] == 136
    assert first["applicable_instance_count"] == 44
    assert first["inapplicable_instance_count"] == 8

    assert collect_file_hashes(first_package) == collect_file_hashes(
        second_package
    )
    assert collect_file_hashes(first_tables) == collect_file_hashes(
        second_tables
    )
    assert first_archive.read_bytes() == second_archive.read_bytes()

    with tarfile.open(first_archive, mode="r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]

    expected_names = sorted(
        [
            *(
                f"raw/{run_id}/{relative_path}"
                for relative_path in collect_file_hashes(first_package)
            ),
            *(
                f"tables/{relative_path}"
                for relative_path in collect_file_hashes(first_tables)
            ),
        ]
    )

    assert names == expected_names
    assert len(members) == 136
    assert all(member.isfile() for member in members)
    assert all(member.mode == 0o644 for member in members)
    assert all(member.mtime == 0 for member in members)
    assert all(member.uid == 0 for member in members)
    assert all(member.gid == 0 for member in members)
    assert all(member.uname == "" for member in members)
    assert all(member.gname == "" for member in members)


def test_definitive_stage3_install_captures_clean_commit(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    implementation_commit = initialise_repository(repository)

    result = install_definitive_stage3_artifacts(
        repository_path=repository,
        config_path="configs/stage3_baselines.json",
    )

    configuration = load_json_config(
        repository / "configs" / "stage3_baselines.json"
    )
    expected_run_id = derive_stage3_run_id(
        config_sha256(configuration),
        implementation_commit,
    )

    assert result["run_id"] == expected_run_id
    assert result["package_file_count"] == 133
    assert result["table_file_count"] == 3
    assert result["archive_member_count"] == 136
    assert result["applicable_instance_count"] == 44
    assert result["inapplicable_instance_count"] == 8
    assert result["applicability_row_count"] == 52
    assert result["summary_row_count"] == 44
    assert result["histogram_row_count"] == 436

    package_path = repository / result["output_directory"]
    archive_path = repository / result["archive_path"]
    manifest_path = repository / result["manifest_path"]

    assert package_path.is_dir()
    assert archive_path.is_file()
    assert manifest_path.is_file()
    assert len(collect_file_hashes(package_path)) == 133

    for relative_path in result["table_paths"].values():
        assert (repository / relative_path).is_file()

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    assert manifest["stage"] == 3
    assert manifest["repository"]["clean"] is True
    assert manifest["repository"]["commit"] == implementation_commit
    assert manifest["payload"]["run_id"] == expected_run_id
    assert (
        manifest["payload"]["implementation_commit"]
        == implementation_commit
    )
    assert (
        manifest["payload"]["archive"]["sha256"]
        == sha256_file(archive_path)
    )
    assert manifest["payload"]["archive"]["member_count"] == 136
    assert (
        manifest["payload"]["deterministic_outputs"][
            "combined_file_count"
        ]
        == 136
    )
    assert (
        manifest["payload"]["deterministic_outputs"][
            "raw_package"
        ]["file_count"]
        == 133
    )
    assert (
        manifest["payload"]["deterministic_outputs"]["tables"][
            "file_count"
        ]
        == 3
    )

    assert run_git(repository, "status", "--porcelain")

    with pytest.raises(ValueError, match="must be clean"):
        install_definitive_stage3_artifacts(
            repository_path=repository,
            config_path="configs/stage3_baselines.json",
        )


def test_corrupted_stage2_archive_is_rejected(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    initialise_repository(repository)

    archive_path = (
        repository
        / "results"
        / "archives"
        / f"{STAGE2_RUN_ID}.tar.gz"
    )
    archive_path.write_bytes(
        archive_path.read_bytes() + b"corruption"
    )

    with pytest.raises(ValueError, match="archive hash"):
        generate_stage3_artifacts(
            repository_path=repository,
            config_path="configs/stage3_baselines.json",
            package_root=tmp_path / "package",
            table_root=tmp_path / "tables",
            archive_path=tmp_path / "stage3.tar.gz",
            run_id="stage3-corrupted-input-test",
        )

    assert not (tmp_path / "package").exists()

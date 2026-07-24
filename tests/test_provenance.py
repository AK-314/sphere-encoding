from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sphere_encoding.provenance import (
    ProvenanceError,
    atomic_write_bytes,
    atomic_write_text,
    build_manifest,
    capture_environment,
    capture_repository,
    repository_is_clean,
    write_manifest,
)


def run_git(
    repository: Path,
    *arguments: str,
) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def initialise_repository(
    repository: Path,
) -> tuple[str, str]:
    run_git(repository, "init")
    run_git(
        repository,
        "config",
        "user.name",
        "Stage One Test",
    )
    run_git(
        repository,
        "config",
        "user.email",
        "stage1@example.invalid",
    )

    tracked = repository / "tracked.txt"
    tracked.write_text("baseline\n", encoding="utf-8")

    run_git(repository, "add", "tracked.txt")
    run_git(repository, "commit", "-m", "baseline")

    commit = run_git(repository, "rev-parse", "HEAD")
    branch = run_git(repository, "branch", "--show-current")
    return commit, branch


def test_atomic_write_bytes_creates_and_replaces_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "nested" / "payload.bin"

    atomic_write_bytes(destination, b"first")
    atomic_write_bytes(destination, b"second")

    assert destination.read_bytes() == b"second"
    assert list(destination.parent.iterdir()) == [destination]


def test_atomic_write_text_uses_requested_encoding(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "text.txt"

    atomic_write_text(
        destination,
        "sphere café",
        encoding="utf-8",
    )

    assert destination.read_text(encoding="utf-8") == "sphere café"


def test_write_manifest_is_stable_sorted_json(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "manifest.json"

    write_manifest(
        destination,
        {
            "z": 1,
            "a": {
                "y": 2,
                "b": 3,
            },
        },
    )

    assert destination.read_text(encoding="utf-8") == (
        '{\n'
        '  "a": {\n'
        '    "b": 3,\n'
        '    "y": 2\n'
        '  },\n'
        '  "z": 1\n'
        '}\n'
    )


def test_capture_environment_records_python_and_versions() -> None:
    environment = capture_environment(
        [
            "pytest",
            "missing-stage1-package",
        ]
    )

    assert environment["captured_at_utc"]
    assert environment["python_version"]
    assert environment["python_executable"]
    assert environment["python_implementation"]
    assert environment["machine"]
    assert environment["operating_system"]
    assert environment["package_versions"]["pytest"]
    assert (
        environment["package_versions"]["missing-stage1-package"]
        is None
    )


def test_capture_repository_reports_clean_commit(
    tmp_path: Path,
) -> None:
    commit, branch = initialise_repository(tmp_path)

    repository = capture_repository(tmp_path)

    assert repository == {
        "branch": branch,
        "clean": True,
        "commit": commit,
        "root": str(tmp_path.resolve()),
    }


def test_repository_is_clean_detects_untracked_file(
    tmp_path: Path,
) -> None:
    initialise_repository(tmp_path)

    assert repository_is_clean(tmp_path)

    untracked = tmp_path / "untracked.txt"
    untracked.write_text("dirty\n", encoding="utf-8")

    assert not repository_is_clean(tmp_path)
    assert capture_repository(tmp_path)["clean"] is False


def test_capture_repository_detects_modified_file(
    tmp_path: Path,
) -> None:
    initialise_repository(tmp_path)

    tracked = tmp_path / "tracked.txt"
    tracked.write_text("modified\n", encoding="utf-8")

    assert not repository_is_clean(tmp_path)


def test_capture_repository_rejects_non_repository(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ProvenanceError,
        match="git rev-parse",
    ):
        capture_repository(tmp_path)


def test_build_manifest_wraps_payload_and_provenance(
    tmp_path: Path,
) -> None:
    commit, _ = initialise_repository(tmp_path)

    manifest = build_manifest(
        stage=1,
        payload={"purpose": "test"},
        repository_path=tmp_path,
        distributions=["pytest"],
    )

    assert manifest["schema_version"] == 1
    assert manifest["stage"] == 1
    assert manifest["payload"] == {"purpose": "test"}
    assert manifest["repository"]["commit"] == commit
    assert manifest["repository"]["clean"] is True
    assert manifest["environment"]["package_versions"]["pytest"]


def test_build_manifest_rejects_non_positive_stage(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="positive",
    ):
        build_manifest(
            stage=0,
            payload={},
            repository_path=tmp_path,
        )

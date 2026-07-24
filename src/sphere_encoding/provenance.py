"""Atomic writing and repository/environment provenance helpers."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sphere_encoding.config import pretty_json_dumps


class ProvenanceError(RuntimeError):
    """Raised when required provenance information cannot be captured."""


def atomic_write_bytes(
    file_path: str | Path,
    data: bytes,
) -> None:
    """Atomically replace a file with bytes on the same filesystem."""
    destination = Path(file_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def atomic_write_text(
    file_path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Atomically replace a text file."""
    atomic_write_bytes(
        file_path,
        text.encode(encoding),
    )


def _run_git(
    repository_path: str | Path,
    arguments: list[str],
) -> str:
    repository = Path(repository_path)
    environment = dict(os.environ)
    environment["LC_ALL"] = "C"

    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        message = (
            completed.stderr.strip()
            or completed.stdout.strip()
            or "unknown git error"
        )
        raise ProvenanceError(
            f"git {' '.join(arguments)} failed in "
            f"{repository}: {message}"
        )

    return completed.stdout.strip()


def repository_is_clean(
    repository_path: str | Path,
) -> bool:
    """Return whether tracked and untracked repository state is clean."""
    status = _run_git(
        repository_path,
        [
            "status",
            "--porcelain=v1",
            "--untracked-files=normal",
        ],
    )
    return status == ""


def capture_repository(
    repository_path: str | Path,
) -> dict[str, Any]:
    """Capture root, branch, full commit, and working-tree cleanliness."""
    root = _run_git(
        repository_path,
        ["rev-parse", "--show-toplevel"],
    )
    commit = _run_git(
        repository_path,
        ["rev-parse", "HEAD"],
    )
    branch = _run_git(
        repository_path,
        ["branch", "--show-current"],
    )

    return {
        "branch": branch,
        "clean": repository_is_clean(repository_path),
        "commit": commit,
        "root": str(Path(root).resolve()),
    }


def capture_environment(
    distributions: Iterable[str] = (),
) -> dict[str, Any]:
    """Capture Python, operating-system, and package versions."""
    versions: dict[str, str | None] = {}

    for distribution in sorted(set(distributions)):
        try:
            versions[distribution] = importlib.metadata.version(
                distribution
            )
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None

    return {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "machine": platform.machine(),
        "operating_system": platform.system(),
        "operating_system_release": platform.release(),
        "package_versions": versions,
        "python_executable": str(Path(sys.executable).resolve()),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }


def build_manifest(
    *,
    stage: int,
    payload: Mapping[str, Any],
    repository_path: str | Path,
    distributions: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a standard manifest envelope without writing it."""
    if stage < 1:
        raise ValueError("stage must be positive")

    return {
        "environment": capture_environment(distributions),
        "payload": dict(payload),
        "repository": capture_repository(repository_path),
        "schema_version": 1,
        "stage": stage,
    }


def write_manifest(
    file_path: str | Path,
    manifest: Mapping[str, Any],
) -> None:
    """Write a manifest atomically using stable sorted JSON."""
    atomic_write_text(
        file_path,
        pretty_json_dumps(dict(manifest)),
    )

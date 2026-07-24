"""SHA-256 helpers used by configuration and provenance code."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest of data."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(
    file_path: str | Path,
    *,
    chunk_size: int = 1024 * 1024,
) -> str:
    """Return a file digest without loading the whole file into memory."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    digest = hashlib.sha256()

    with Path(file_path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()

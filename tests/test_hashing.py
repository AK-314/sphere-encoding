from __future__ import annotations

import hashlib

import pytest

from sphere_encoding.hashing import sha256_bytes, sha256_file


def test_sha256_bytes_matches_hashlib() -> None:
    data = b"sphere-encoding"

    assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()


def test_sha256_file_matches_hashlib(tmp_path) -> None:
    data = b"abc" * 1000
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(data)

    assert sha256_file(file_path) == hashlib.sha256(data).hexdigest()


def test_sha256_file_is_independent_of_chunk_size(tmp_path) -> None:
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(bytes(range(256)) * 20)

    assert sha256_file(file_path, chunk_size=1) == sha256_file(
        file_path,
        chunk_size=257,
    )


@pytest.mark.parametrize("chunk_size", [0, -1])
def test_sha256_file_rejects_non_positive_chunk_size(
    tmp_path,
    chunk_size: int,
) -> None:
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(b"data")

    with pytest.raises(ValueError, match="positive"):
        sha256_file(file_path, chunk_size=chunk_size)

"""Deterministic unrestricted-codebook initialisation sources."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np

from sphere_encoding.heuristic.state import (
    SearchState,
    SearchStateError,
    codeword_id_to_row,
)

_SEED_SCHEMA: Final = "sphere_encoding.heuristic.seed.v1"


class InitialisationError(ValueError):
    """Raised when a codebook initialisation cannot be constructed."""


@dataclass(frozen=True, slots=True)
class InitialisationResult:
    """A validated initial state and its deterministic provenance."""

    state: SearchState
    initialisation_class: str
    initialisation_id: str
    source_path: str | None
    source_sha256: str | None
    source_code_length: int
    target_code_length: int
    zero_padding_bits: int
    seed: int | None

    def __post_init__(self) -> None:
        if not self.initialisation_class:
            raise InitialisationError("initialisation class must be non-empty")
        if not self.initialisation_id:
            raise InitialisationError("initialisation identifier must be non-empty")
        if self.source_code_length <= 0 or self.target_code_length <= 0:
            raise InitialisationError("code lengths must be positive")
        if self.target_code_length != self.state.code_length:
            raise InitialisationError("target code length does not match state")
        if self.zero_padding_bits != (
            self.target_code_length - self.source_code_length
        ):
            raise InitialisationError("zero-padding metadata is inconsistent")
        if self.zero_padding_bits < 0:
            raise InitialisationError("negative zero padding is invalid")
        if (self.source_path is None) != (self.source_sha256 is None):
            raise InitialisationError("source path and hash must appear together")

    def metadata(self) -> dict[str, int | str | None]:
        """Return deterministic JSON-compatible provenance."""
        return {
            "initialisation_class": self.initialisation_class,
            "initialisation_id": self.initialisation_id,
            "seed": self.seed,
            "source_code_length": self.source_code_length,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "target_code_length": self.target_code_length,
            "zero_padding_bits": self.zero_padding_bits,
        }


def file_sha256(path: str | Path) -> str:
    """Hash a source artifact without altering it."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def derive_seed(
    master_seed: int,
    namespace: str,
    *components: int | str,
) -> int:
    """Derive a stable unsigned 64-bit seed from canonical JSON."""
    if not isinstance(master_seed, int) or master_seed < 0:
        raise InitialisationError("master seed must be a non-negative integer")
    if not namespace:
        raise InitialisationError("seed namespace must be non-empty")
    if any(not isinstance(value, (int, str)) for value in components):
        raise InitialisationError("seed components must be integers or strings")

    payload = {
        "components": list(components),
        "master_seed": master_seed,
        "namespace": namespace,
        "schema": _SEED_SCHEMA,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")


def zero_pad_state(
    state: SearchState,
    target_code_length: int,
) -> SearchState:
    """Append deterministic zero-valued low-significance columns."""
    if not isinstance(target_code_length, int) or target_code_length <= 0:
        raise InitialisationError("target code length must be positive")
    if target_code_length < state.code_length:
        raise InitialisationError(
            "a longer codebook cannot initialise a shorter-bit problem"
        )
    if target_code_length == state.code_length:
        return SearchState.from_codebook(state.codebook)

    padding = np.zeros(
        (state.vertex_count, target_code_length - state.code_length),
        dtype=np.uint8,
    )
    return SearchState.from_codebook(np.concatenate((state.codebook, padding), axis=1))


def _load_npy_state(path: Path) -> SearchState:
    if not path.is_file():
        raise InitialisationError(f"codebook source does not exist: {path}")
    try:
        codebook = np.load(path, allow_pickle=False)
        return SearchState.from_codebook(codebook)
    except (OSError, ValueError, SearchStateError) as error:
        raise InitialisationError(f"invalid codebook source: {path}") from error


def _source_result(
    *,
    state: SearchState,
    target_code_length: int,
    initialisation_class: str,
    initialisation_id: str,
    source_path: Path,
) -> InitialisationResult:
    source_code_length = state.code_length
    padded = zero_pad_state(state, target_code_length)
    return InitialisationResult(
        state=padded,
        initialisation_class=initialisation_class,
        initialisation_id=initialisation_id,
        source_path=source_path.as_posix(),
        source_sha256=file_sha256(source_path),
        source_code_length=source_code_length,
        target_code_length=target_code_length,
        zero_padding_bits=target_code_length - source_code_length,
        seed=None,
    )


def load_stage3_baseline(
    stage3_root: str | Path,
    *,
    graph_id: str,
    encoding_id: str,
    target_code_length: int,
) -> InitialisationResult:
    """Load a committed Stage 3 baseline codebook by exact identity."""
    if not graph_id or not encoding_id:
        raise InitialisationError("graph and encoding identifiers are required")
    path = Path(stage3_root) / graph_id / encoding_id / "codes.npy"
    state = _load_npy_state(path)
    return _source_result(
        state=state,
        target_code_length=target_code_length,
        initialisation_class="stage3_baseline",
        initialisation_id=f"stage3_{encoding_id}",
        source_path=path,
    )


def load_stage4_witness(
    stage4_root: str | Path,
    *,
    graph_id: str,
    source_code_length: int,
    target_r: int,
    target_code_length: int,
) -> InitialisationResult:
    """Load a committed Stage 4 feasible witness by exact identity."""
    if not graph_id:
        raise InitialisationError("graph identifier is required")
    if source_code_length <= 0:
        raise InitialisationError("source code length must be positive")
    if target_r < 0:
        raise InitialisationError("target threshold must be non-negative")

    path = (
        Path(stage4_root)
        / graph_id
        / f"m{source_code_length}"
        / "targets"
        / f"r{target_r}"
        / "codebook.npy"
    )
    state = _load_npy_state(path)
    if state.code_length != source_code_length:
        raise InitialisationError(
            "Stage 4 witness width does not match its path identity"
        )
    return _source_result(
        state=state,
        target_code_length=target_code_length,
        initialisation_class="stage4_witness",
        initialisation_id=(f"stage4_m{source_code_length}_r{target_r}"),
        source_path=path,
    )


def random_injective_initialisation(
    *,
    vertex_count: int,
    code_length: int,
    seed: int,
) -> InitialisationResult:
    """Construct a deterministic uniformly sampled injective codebook."""
    if not isinstance(vertex_count, int) or vertex_count <= 0:
        raise InitialisationError("vertex count must be positive")
    if not isinstance(code_length, int) or code_length <= 0:
        raise InitialisationError("code length must be positive")
    if not isinstance(seed, int) or seed < 0:
        raise InitialisationError("seed must be a non-negative integer")

    capacity = 1 << code_length
    if vertex_count > capacity:
        raise InitialisationError(
            "code space is too small for an injective random initialisation"
        )

    rng = np.random.Generator(np.random.PCG64(seed))
    selected = rng.choice(
        capacity,
        size=vertex_count,
        replace=False,
        shuffle=True,
    )
    codebook = np.stack(
        [codeword_id_to_row(int(identifier), code_length) for identifier in selected]
    )
    state = SearchState.from_codebook(codebook)
    return InitialisationResult(
        state=state,
        initialisation_class="deterministic_random",
        initialisation_id=f"random_seed_{seed}",
        source_path=None,
        source_sha256=None,
        source_code_length=code_length,
        target_code_length=code_length,
        zero_padding_bits=0,
        seed=seed,
    )

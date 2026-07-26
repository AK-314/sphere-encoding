"""Validated deterministic state for unrestricted binary codebooks."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from bisect import bisect_left, bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

_CHECKPOINT_MAGIC: Final = b"SPHERE_ENCODING_HEURISTIC_STATE_V1\\n"
_CHECKPOINT_SCHEMA: Final = "sphere_encoding.heuristic.state.v1"


class SearchStateError(ValueError):
    """Raised when a heuristic search state is malformed."""


def codeword_rows_to_ids(codebook: npt.ArrayLike) -> tuple[int, ...]:
    """Convert binary rows to canonical big-endian integer identifiers."""
    array = np.asarray(codebook)
    if array.ndim != 2:
        raise SearchStateError("codebook must be a two-dimensional array")
    if array.dtype != np.uint8:
        raise SearchStateError("codebook dtype must be uint8")
    if not np.all((array == 0) | (array == 1)):
        raise SearchStateError("codebook values must be binary")

    identifiers: list[int] = []
    for row in array:
        identifier = 0
        for bit in row:
            identifier = (identifier << 1) | int(bit)
        identifiers.append(identifier)
    return tuple(identifiers)


def codeword_id_to_row(codeword_id: int, code_length: int) -> np.ndarray:
    """Convert a canonical integer identifier to a binary uint8 row."""
    if code_length <= 0:
        raise SearchStateError("code length must be positive")
    capacity = 1 << code_length
    if codeword_id < 0 or codeword_id >= capacity:
        raise SearchStateError("codeword identifier is outside the code space")

    row = np.fromiter(
        ((codeword_id >> shift) & 1 for shift in range(code_length - 1, -1, -1)),
        dtype=np.uint8,
        count=code_length,
    )
    row.setflags(write=False)
    return row


def _normalise_codebook(codebook: npt.ArrayLike) -> np.ndarray:
    array = np.asarray(codebook)
    if array.ndim != 2:
        raise SearchStateError("codebook must be a two-dimensional array")
    if array.dtype != np.uint8:
        raise SearchStateError("codebook dtype must be uint8")

    vertex_count, code_length = array.shape
    if vertex_count <= 0:
        raise SearchStateError("codebook must contain at least one vertex")
    if code_length <= 0:
        raise SearchStateError("code length must be positive")
    if vertex_count > 1 << code_length:
        raise SearchStateError("code space is too small for an injective codebook")
    if not np.all((array == 0) | (array == 1)):
        raise SearchStateError("codebook values must be binary")

    normalised = np.array(array, dtype=np.uint8, order="C", copy=True)
    assigned_ids = codeword_rows_to_ids(normalised)
    if len(set(assigned_ids)) != vertex_count:
        raise SearchStateError("codebook must be injective")

    normalised.setflags(write=False)
    return normalised


def _codebook_sha256(codebook: np.ndarray) -> str:
    return hashlib.sha256(codebook.tobytes(order="C")).hexdigest()


@dataclass(frozen=True, slots=True)
class SearchState:
    """Immutable injective codebook state in canonical vertex order."""

    _codebook: np.ndarray
    _assigned_codeword_ids: tuple[int, ...]
    _occupancy: tuple[tuple[int, int], ...]

    @classmethod
    def from_codebook(cls, codebook: npt.ArrayLike) -> SearchState:
        """Validate and construct a deterministic search state."""
        normalised = _normalise_codebook(codebook)
        assigned_ids = codeword_rows_to_ids(normalised)
        occupancy = tuple(
            sorted(
                (codeword_id, vertex_index)
                for vertex_index, codeword_id in enumerate(assigned_ids)
            )
        )
        return cls(
            _codebook=normalised,
            _assigned_codeword_ids=assigned_ids,
            _occupancy=occupancy,
        )

    @property
    def codebook(self) -> np.ndarray:
        """Return a read-only view of the binary codebook."""
        view = self._codebook.view()
        view.setflags(write=False)
        return view

    @property
    def vertex_count(self) -> int:
        return int(self._codebook.shape[0])

    @property
    def code_length(self) -> int:
        return int(self._codebook.shape[1])

    @property
    def capacity(self) -> int:
        return 1 << self.code_length

    @property
    def assigned_codeword_ids(self) -> tuple[int, ...]:
        """Return identifiers in canonical vertex order."""
        return self._assigned_codeword_ids

    @property
    def occupancy(self) -> tuple[tuple[int, int], ...]:
        """Return sorted ``(codeword_id, vertex_index)`` occupancy entries."""
        return self._occupancy

    @property
    def used_codeword_ids(self) -> tuple[int, ...]:
        """Return occupied codeword identifiers in ascending order."""
        return tuple(codeword_id for codeword_id, _ in self._occupancy)

    @property
    def unused_codeword_count(self) -> int:
        return self.capacity - self.vertex_count

    def is_codeword_used(self, codeword_id: int) -> bool:
        """Return whether an identifier is occupied."""
        self._validate_codeword_id(codeword_id)
        used = self.used_codeword_ids
        position = bisect_left(used, codeword_id)
        return position < len(used) and used[position] == codeword_id

    def vertex_for_codeword(self, codeword_id: int) -> int | None:
        """Return the occupying vertex, or ``None`` when unused."""
        self._validate_codeword_id(codeword_id)
        used = self.used_codeword_ids
        position = bisect_left(used, codeword_id)
        if position >= len(used) or used[position] != codeword_id:
            return None
        return self._occupancy[position][1]

    def unused_codeword_id_at(self, unused_index: int) -> int:
        """Return the zero-based ``unused_index``-th free codeword identifier."""
        if unused_index < 0 or unused_index >= self.unused_codeword_count:
            raise SearchStateError("unused-codeword index is outside the free set")

        used = self.used_codeword_ids
        low = 0
        high = self.capacity - 1
        target_rank = unused_index + 1

        while low < high:
            midpoint = (low + high) // 2
            used_at_or_below = bisect_right(used, midpoint)
            unused_at_or_below = midpoint + 1 - used_at_or_below
            if unused_at_or_below >= target_rank:
                high = midpoint
            else:
                low = midpoint + 1

        if self.is_codeword_used(low):
            raise SearchStateError("internal unused-codeword selection failure")
        return low

    def iter_unused_codeword_ids(self) -> Iterator[int]:
        """Yield free codeword identifiers in canonical ascending order."""
        for index in range(self.unused_codeword_count):
            yield self.unused_codeword_id_at(index)

    def codebook_sha256(self) -> str:
        """Hash the canonical raw codebook bytes."""
        return _codebook_sha256(self._codebook)

    def to_bytes(self) -> bytes:
        """Serialise the state deterministically."""
        header = {
            "codebook_sha256": self.codebook_sha256(),
            "dtype": "uint8",
            "order": "C",
            "schema": _CHECKPOINT_SCHEMA,
            "shape": [self.vertex_count, self.code_length],
        }
        header_bytes = json.dumps(
            header,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return (
            _CHECKPOINT_MAGIC
            + header_bytes
            + b"\\n"
            + self._codebook.tobytes(order="C")
        )

    @classmethod
    def from_bytes(cls, payload: bytes) -> SearchState:
        """Load and validate a deterministic state serialisation."""
        if not payload.startswith(_CHECKPOINT_MAGIC):
            raise SearchStateError("invalid checkpoint magic")

        remainder = payload[len(_CHECKPOINT_MAGIC) :]
        try:
            header_bytes, raw_codebook = remainder.split(b"\\n", maxsplit=1)
            header = json.loads(header_bytes.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise SearchStateError("invalid checkpoint header") from error

        expected_keys = {
            "codebook_sha256",
            "dtype",
            "order",
            "schema",
            "shape",
        }
        if set(header) != expected_keys:
            raise SearchStateError("checkpoint header fields are invalid")
        if header["schema"] != _CHECKPOINT_SCHEMA:
            raise SearchStateError("unsupported checkpoint schema")
        if header["dtype"] != "uint8" or header["order"] != "C":
            raise SearchStateError("unsupported checkpoint array representation")

        shape = header["shape"]
        if (
            not isinstance(shape, list)
            or len(shape) != 2
            or not all(isinstance(value, int) for value in shape)
        ):
            raise SearchStateError("checkpoint shape is invalid")

        vertex_count, code_length = shape
        expected_size = vertex_count * code_length
        if len(raw_codebook) != expected_size:
            raise SearchStateError("checkpoint payload size does not match shape")

        actual_hash = hashlib.sha256(raw_codebook).hexdigest()
        if actual_hash != header["codebook_sha256"]:
            raise SearchStateError("checkpoint codebook hash mismatch")

        codebook = np.frombuffer(raw_codebook, dtype=np.uint8).reshape(
            vertex_count,
            code_length,
        )
        return cls.from_codebook(codebook)

    def state_sha256(self) -> str:
        """Hash the complete deterministic state serialisation."""
        return hashlib.sha256(self.to_bytes()).hexdigest()

    def write_checkpoint(self, path: str | Path) -> None:
        """Atomically write a deterministic state checkpoint."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        descriptor, temporary_name = tempfile.mkstemp(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(self.to_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    @classmethod
    def read_checkpoint(cls, path: str | Path) -> SearchState:
        """Read and validate a deterministic state checkpoint."""
        return cls.from_bytes(Path(path).read_bytes())

    def _validate_codeword_id(self, codeword_id: int) -> None:
        if not isinstance(codeword_id, int):
            raise SearchStateError("codeword identifier must be an integer")
        if codeword_id < 0 or codeword_id >= self.capacity:
            raise SearchStateError("codeword identifier is outside the code space")

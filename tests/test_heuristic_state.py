from __future__ import annotations

import numpy as np
import pytest

from sphere_encoding.heuristic.state import (
    SearchState,
    SearchStateError,
    codeword_id_to_row,
    codeword_rows_to_ids,
)


def _codebook() -> np.ndarray:
    return np.array(
        [
            [0, 0, 0],
            [0, 1, 1],
            [1, 0, 1],
        ],
        dtype=np.uint8,
    )


def test_valid_state_tracks_assigned_used_and_unused_codewords() -> None:
    state = SearchState.from_codebook(_codebook())

    assert state.vertex_count == 3
    assert state.code_length == 3
    assert state.capacity == 8
    assert state.assigned_codeword_ids == (0, 3, 5)
    assert state.used_codeword_ids == (0, 3, 5)
    assert state.occupancy == ((0, 0), (3, 1), (5, 2))
    assert tuple(state.iter_unused_codeword_ids()) == (1, 2, 4, 6, 7)
    assert state.unused_codeword_count == 5


def test_codebook_is_copied_and_exposed_read_only() -> None:
    original = _codebook()
    state = SearchState.from_codebook(original)
    original[0, 0] = 1

    assert state.codebook[0, 0] == 0
    with pytest.raises(ValueError):
        state.codebook[0, 0] = 1


def test_codeword_identifier_round_trip() -> None:
    codebook = _codebook()
    identifiers = codeword_rows_to_ids(codebook)

    rebuilt = np.stack(
        [codeword_id_to_row(identifier, 3) for identifier in identifiers]
    )
    np.testing.assert_array_equal(rebuilt, codebook)


def test_sparse_occupancy_queries_are_deterministic() -> None:
    state = SearchState.from_codebook(_codebook())

    assert state.is_codeword_used(3)
    assert not state.is_codeword_used(4)
    assert state.vertex_for_codeword(5) == 2
    assert state.vertex_for_codeword(6) is None
    assert [state.unused_codeword_id_at(index) for index in range(5)] == [
        1,
        2,
        4,
        6,
        7,
    ]


def test_state_hash_is_stable_across_equivalent_memory_layouts() -> None:
    contiguous = _codebook()
    fortran_order = np.asfortranarray(contiguous)

    first = SearchState.from_codebook(contiguous)
    second = SearchState.from_codebook(fortran_order)

    assert first.to_bytes() == second.to_bytes()
    assert first.codebook_sha256() == second.codebook_sha256()
    assert first.state_sha256() == second.state_sha256()


def test_deterministic_serialisation_round_trip() -> None:
    state = SearchState.from_codebook(_codebook())

    restored = SearchState.from_bytes(state.to_bytes())

    np.testing.assert_array_equal(restored.codebook, state.codebook)
    assert restored.occupancy == state.occupancy
    assert restored.to_bytes() == state.to_bytes()
    assert restored.state_sha256() == state.state_sha256()


def test_checkpoint_write_is_byte_identical(tmp_path) -> None:
    state = SearchState.from_codebook(_codebook())
    first = tmp_path / "first.state"
    second = tmp_path / "second.state"

    state.write_checkpoint(first)
    state.write_checkpoint(second)

    assert first.read_bytes() == second.read_bytes()
    restored = SearchState.read_checkpoint(first)
    assert restored.to_bytes() == state.to_bytes()


@pytest.mark.parametrize(
    "malformed",
    [
        np.array([0, 1], dtype=np.uint8),
        np.empty((0, 3), dtype=np.uint8),
        np.empty((2, 0), dtype=np.uint8),
        np.array([[0, 1], [1, 0]], dtype=np.int64),
        np.array([[0, 2], [1, 0]], dtype=np.uint8),
        np.array([[0, 0], [0, 0]], dtype=np.uint8),
        np.zeros((3, 1), dtype=np.uint8),
    ],
)
def test_malformed_states_are_rejected(malformed: np.ndarray) -> None:
    with pytest.raises(SearchStateError):
        SearchState.from_codebook(malformed)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"not-a-checkpoint",
        (b'SPHERE_ENCODING_HEURISTIC_STATE_V1\n{"codebook_sha256":"bad"}\n'),
    ],
)
def test_malformed_checkpoints_are_rejected(payload: bytes) -> None:
    with pytest.raises(SearchStateError):
        SearchState.from_bytes(payload)


def test_invalid_codeword_and_unused_indices_are_rejected() -> None:
    state = SearchState.from_codebook(_codebook())

    with pytest.raises(SearchStateError):
        state.is_codeword_used(-1)
    with pytest.raises(SearchStateError):
        state.is_codeword_used(8)
    with pytest.raises(SearchStateError):
        state.unused_codeword_id_at(-1)
    with pytest.raises(SearchStateError):
        state.unused_codeword_id_at(state.unused_codeword_count)
    with pytest.raises(SearchStateError):
        codeword_id_to_row(8, 3)

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sphere_encoding.heuristic.initialisation import (
    InitialisationError,
    derive_seed,
    load_stage3_baseline,
    load_stage4_witness,
    random_injective_initialisation,
    zero_pad_state,
)
from sphere_encoding.heuristic.state import SearchState

STAGE3_RUN_ID = "stage3-deterministic-baselines-3fad68b97de9-f07ae893574e"
STAGE4_RUN_ID = "stage4-exact-free-codebook-97021c6cac03-7adb5b49f2cb"
STAGE3_ROOT = Path("results/raw") / STAGE3_RUN_ID
STAGE4_ROOT = Path("results/raw") / STAGE4_RUN_ID


def test_loads_accepted_stage3_baseline() -> None:
    result = load_stage3_baseline(
        STAGE3_ROOT,
        graph_id="primitive_q2_knn4",
        encoding_id="cartesian_coordinate_gray",
        target_code_length=9,
    )

    assert result.initialisation_class == "stage3_baseline"
    assert result.state.code_length == 9
    assert result.source_sha256 == (
        "18647a175779d3a8ea05730085a1584875d22a50a2d0b4627a57a44b838643f9"
    )
    assert result.zero_padding_bits == 0


def test_loads_accepted_stage4_witness() -> None:
    result = load_stage4_witness(
        STAGE4_ROOT,
        graph_id="primitive_q2_knn4",
        source_code_length=9,
        target_r=2,
        target_code_length=9,
    )

    assert result.initialisation_class == "stage4_witness"
    assert result.state.code_length == 9
    assert result.source_sha256 == (
        "e31e5ff7a640a149181ed572509fe5f991c2005b531b07d2deb8dc6be305f88f"
    )
    assert result.zero_padding_bits == 0


def test_zero_padding_appends_columns_and_preserves_injectivity() -> None:
    original = SearchState.from_codebook(
        np.array(
            [
                [0, 0],
                [0, 1],
                [1, 0],
            ],
            dtype=np.uint8,
        )
    )

    padded = zero_pad_state(original, 5)

    np.testing.assert_array_equal(
        padded.codebook[:, :2],
        original.codebook,
    )
    np.testing.assert_array_equal(
        padded.codebook[:, 2:],
        np.zeros((3, 3), dtype=np.uint8),
    )
    assert len(set(padded.assigned_codeword_ids)) == padded.vertex_count


def test_stage4_witness_can_zero_pad_to_longer_length() -> None:
    result = load_stage4_witness(
        STAGE4_ROOT,
        graph_id="primitive_q2_knn4",
        source_code_length=9,
        target_r=2,
        target_code_length=11,
    )

    assert result.source_code_length == 9
    assert result.target_code_length == 11
    assert result.zero_padding_bits == 2
    np.testing.assert_array_equal(
        result.state.codebook[:, -2:],
        np.zeros((result.state.vertex_count, 2), dtype=np.uint8),
    )


def test_longer_to_shorter_initialisation_is_rejected() -> None:
    result = load_stage4_witness(
        STAGE4_ROOT,
        graph_id="primitive_q2_knn4",
        source_code_length=9,
        target_r=2,
        target_code_length=9,
    )

    with pytest.raises(InitialisationError):
        zero_pad_state(result.state, 8)


def test_random_initialisation_reproduces_exactly() -> None:
    first = random_injective_initialisation(
        vertex_count=20,
        code_length=6,
        seed=123456,
    )
    second = random_injective_initialisation(
        vertex_count=20,
        code_length=6,
        seed=123456,
    )

    assert first.state.to_bytes() == second.state.to_bytes()
    assert first.metadata() == second.metadata()
    assert len(set(first.state.assigned_codeword_ids)) == 20


def test_random_initialisation_changes_with_seed() -> None:
    first = random_injective_initialisation(
        vertex_count=20,
        code_length=6,
        seed=1,
    )
    second = random_injective_initialisation(
        vertex_count=20,
        code_length=6,
        seed=2,
    )

    assert first.state.state_sha256() != second.state.state_sha256()


def test_capacity_failure_is_explicit() -> None:
    with pytest.raises(InitialisationError):
        random_injective_initialisation(
            vertex_count=5,
            code_length=2,
            seed=0,
        )


def test_stable_seed_derivation() -> None:
    first = derive_seed(
        20260726,
        "stage5_restart",
        "icosphere_l3",
        12,
        2,
        "random",
        0,
    )
    second = derive_seed(
        20260726,
        "stage5_restart",
        "icosphere_l3",
        12,
        2,
        "random",
        0,
    )
    changed = derive_seed(
        20260726,
        "stage5_restart",
        "icosphere_l3",
        12,
        2,
        "random",
        1,
    )

    assert first == second
    assert first != changed
    assert 0 <= first < 2**64


def test_missing_or_malformed_source_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(InitialisationError):
        load_stage3_baseline(
            tmp_path,
            graph_id="missing",
            encoding_id="missing",
            target_code_length=4,
        )

    path = tmp_path / "graph" / "encoding"
    path.mkdir(parents=True)
    np.save(
        path / "codes.npy",
        np.array([[0, 0], [0, 0]], dtype=np.uint8),
        allow_pickle=False,
    )
    with pytest.raises(InitialisationError):
        load_stage3_baseline(
            tmp_path,
            graph_id="graph",
            encoding_id="encoding",
            target_code_length=2,
        )

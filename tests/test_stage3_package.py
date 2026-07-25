from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from sphere_encoding.config import load_json_config
from sphere_encoding.evaluation.artifacts import (
    generate_stage3_package,
)
from sphere_encoding.graphs.artifacts import collect_file_hashes

CONFIG_PATH = Path("configs/stage3_baselines.json")
STAGE2_RUN_ID = (
    "stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50"
)
STAGE2_PACKAGE = Path("results/raw") / STAGE2_RUN_ID
TEST_RUN_ID = "stage3-deterministic-baselines-test"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        return list(csv.DictReader(stream))


def test_stage3_package_is_independently_reproducible(
    tmp_path: Path,
) -> None:
    config = load_json_config(CONFIG_PATH)

    first_package = tmp_path / "first-package"
    second_package = tmp_path / "second-package"
    first_tables = tmp_path / "first-tables"
    second_tables = tmp_path / "second-tables"

    first = generate_stage3_package(
        config,
        stage2_package_root=STAGE2_PACKAGE,
        output_root=first_package,
        table_root=first_tables,
        run_id=TEST_RUN_ID,
    )
    second = generate_stage3_package(
        config,
        stage2_package_root=STAGE2_PACKAGE,
        output_root=second_package,
        table_root=second_tables,
        run_id=TEST_RUN_ID,
    )

    assert first == second
    assert first["file_count"] == 133
    assert first["table_file_count"] == 3
    assert first["graph_count"] == 13
    assert first["applicability_row_count"] == 52
    assert first["applicable_instance_count"] == 44
    assert first["inapplicable_instance_count"] == 8
    assert first["summary_row_count"] == 44
    assert len(first["instance_paths"]) == 44

    assert collect_file_hashes(first_package) == collect_file_hashes(
        second_package
    )
    assert collect_file_hashes(first_tables) == collect_file_hashes(
        second_tables
    )


def test_stage3_package_structure_and_tables(
    tmp_path: Path,
) -> None:
    config = load_json_config(CONFIG_PATH)
    package = tmp_path / "package"
    tables = tmp_path / "tables"

    generated = generate_stage3_package(
        config,
        stage2_package_root=STAGE2_PACKAGE,
        output_root=package,
        table_root=tables,
        run_id=TEST_RUN_ID,
    )

    metadata = json.loads(
        (package / "package_metadata.json").read_text(
            encoding="utf-8"
        )
    )

    assert metadata["stage"] == 3
    assert metadata["run_id"] == TEST_RUN_ID
    assert metadata["applicable_instance_count"] == 44
    assert metadata["inapplicable_instance_count"] == 8
    assert metadata["applicability_row_count"] == 52
    assert metadata[
        "deterministic_file_count_without_package_metadata"
    ] == 132
    assert metadata["table_file_count"] == 3
    assert len(metadata["deterministic_files"]) == 132
    assert len(metadata["instance_paths"]) == 44

    metrics_paths = sorted(package.glob("*/*/metrics.json"))
    code_paths = sorted(package.glob("*/*/codes.npy"))
    local_paths = sorted(
        package.glob("*/*/local_edge_hamming.npy")
    )

    assert len(metrics_paths) == 44
    assert len(code_paths) == 44
    assert len(local_paths) == 44

    for metrics_path in metrics_paths:
        metrics = json.loads(
            metrics_path.read_text(encoding="utf-8")
        )
        codes = np.load(
            metrics_path.with_name("codes.npy"),
            allow_pickle=False,
        )
        local = np.load(
            metrics_path.with_name("local_edge_hamming.npy"),
            allow_pickle=False,
        )

        assert metrics["stage"] == 3
        assert metrics["validity"] == {
            "binary": True,
            "canonical_vertex_row_order": True,
            "injective": True,
        }
        assert metrics["collision_diagnostics"]["collision_count"] == 0
        assert codes.dtype == np.uint8
        assert local.dtype == np.int64
        assert codes.shape[0] == metrics["graph"]["vertex_count"]
        assert codes.shape[1] == metrics["code_length"]["m"]
        assert len(local) == metrics["graph"]["edge_count"]
        assert sum(metrics["local"]["histogram"]) == len(local)

    summary_path = (
        tables / f"{TEST_RUN_ID}_baseline_summary.csv"
    )
    histogram_path = (
        tables / f"{TEST_RUN_ID}_local_histograms.csv"
    )
    applicability_path = (
        tables / f"{TEST_RUN_ID}_applicability.csv"
    )

    summary_rows = read_csv_rows(summary_path)
    histogram_rows = read_csv_rows(histogram_path)
    applicability_rows = read_csv_rows(applicability_path)

    assert len(summary_rows) == 44
    assert len(applicability_rows) == 52
    assert sum(
        row["applicable"] == "true"
        for row in applicability_rows
    ) == 44
    assert sum(
        row["applicable"] == "false"
        for row in applicability_rows
    ) == 8

    expected_histogram_rows = sum(
        int(row["code_length"]) + 1
        for row in summary_rows
    )
    assert len(histogram_rows) == expected_histogram_rows
    assert generated["histogram_row_count"] == expected_histogram_rows

    assert {
        row["encoding_id"]
        for row in summary_rows
    } == {
        "canonical_index_binary",
        "canonical_index_gray",
        "cartesian_coordinate_binary",
        "cartesian_coordinate_gray",
    }


def test_exact_icosphere_index_binary_codes(
    tmp_path: Path,
) -> None:
    config = load_json_config(CONFIG_PATH)
    package = tmp_path / "package"
    tables = tmp_path / "tables"

    generate_stage3_package(
        config,
        stage2_package_root=STAGE2_PACKAGE,
        output_root=package,
        table_root=tables,
        run_id=TEST_RUN_ID,
    )

    codes = np.load(
        package
        / "icosphere_l0"
        / "canonical_index_binary"
        / "codes.npy",
        allow_pickle=False,
    )

    assert codes.shape == (12, 4)
    assert codes[:5].tolist() == [
        [0, 0, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 0],
        [0, 0, 1, 1],
        [0, 1, 0, 0],
    ]


def test_corrupted_stage2_input_is_rejected(
    tmp_path: Path,
) -> None:
    config = load_json_config(CONFIG_PATH)
    corrupted = tmp_path / "corrupted-stage2"
    shutil.copytree(STAGE2_PACKAGE, corrupted)

    vertex_path = corrupted / "icosphere_l0" / "vertices.npy"
    vertex_path.write_bytes(vertex_path.read_bytes() + b"corruption")

    package = tmp_path / "package"
    tables = tmp_path / "tables"

    with pytest.raises(ValueError, match="hashes differ"):
        generate_stage3_package(
            config,
            stage2_package_root=corrupted,
            output_root=package,
            table_root=tables,
            run_id=TEST_RUN_ID,
        )

    assert not package.exists()


def test_modified_stage3_configuration_is_rejected(
    tmp_path: Path,
) -> None:
    config = load_json_config(CONFIG_PATH)
    config["stage_name"] = "Modified Stage 3"

    with pytest.raises(
        ValueError,
        match="frozen Stage 3 configuration",
    ):
        generate_stage3_package(
            config,
            stage2_package_root=STAGE2_PACKAGE,
            output_root=tmp_path / "package",
            table_root=tmp_path / "tables",
            run_id=TEST_RUN_ID,
        )

    assert not (tmp_path / "package").exists()


@pytest.mark.parametrize(
    "run_id",
    [
        "",
        "UPPERCASE",
        "contains_underscore",
        "../escape",
    ],
)
def test_invalid_run_identifiers_are_rejected(
    tmp_path: Path,
    run_id: str,
) -> None:
    config = load_json_config(CONFIG_PATH)

    with pytest.raises(ValueError, match="run_id"):
        generate_stage3_package(
            config,
            stage2_package_root=STAGE2_PACKAGE,
            output_root=tmp_path / "package",
            table_root=tmp_path / "tables",
            run_id=run_id,
        )

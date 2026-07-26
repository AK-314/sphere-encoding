from __future__ import annotations

import csv
import io
import json
import tarfile
from pathlib import Path

import numpy as np
import pytest

from sphere_encoding.graphs.artifacts import collect_file_hashes
from sphere_encoding.heuristic.artifacts import (
    EXACT_FIELDS,
    INSTANCE_FIELDS,
    NEGATIVE_RESULT_INTERPRETATION,
    RUN_FIELDS,
    TARGET_FIELDS,
    ArtifactError,
    HeuristicInstanceExecution,
    HeuristicRunExecution,
    HeuristicTargetExecution,
    generate_stage5_artifacts,
    load_run_artifacts,
    write_run_artifacts,
    write_stage5_tables,
)
from sphere_encoding.heuristic.schedule import LinearTemperatureSchedule
from sphere_encoding.heuristic.search import (
    SearchKernelConfig,
    run_search_kernel,
)
from sphere_encoding.heuristic.state import SearchState
from sphere_encoding.heuristic.verification import verify_search_result

TRIANGLE_EDGES = np.array(
    [
        [0, 1],
        [0, 2],
        [1, 2],
    ],
    dtype=np.int64,
)
TRIANGLE_CODEBOOK = SearchState.from_codebook(
    np.array(
        [
            [0, 0],
            [0, 1],
            [1, 1],
        ],
        dtype=np.uint8,
    )
)


def _run(
    *,
    run_order: int,
    seed: int,
    target_r: int,
    budget: int,
    stop_on_feasible: bool,
    initialisation_id: str,
) -> HeuristicRunExecution:
    config = SearchKernelConfig(
        proposal_budget=budget,
        swap_probability=0.5,
        temperature_schedule=LinearTemperatureSchedule(
            proposal_budget=budget,
            start_temperature=2.0,
            end_temperature=0.0,
        ),
        stop_on_feasible=stop_on_feasible,
    )
    result = run_search_kernel(
        TRIANGLE_CODEBOOK,
        TRIANGLE_EDGES,
        target_r=target_r,
        seed=seed,
        config=config,
    )
    report = verify_search_result(
        result,
        TRIANGLE_EDGES,
        target_r=target_r,
        config=config,
    )
    return HeuristicRunExecution(
        run_order_within_target=run_order,
        initialisation_class="deterministic_random",
        initialisation_id=initialisation_id,
        restart_index=run_order - 1,
        seed=seed,
        initialisation_metadata={
            "source": "synthetic_triangle",
            "zero_padding_bits": 0,
        },
        result=result,
        verification=report,
    )


def _best_order(
    runs: tuple[HeuristicRunExecution, ...],
) -> int:
    return min(
        runs,
        key=lambda run: (
            run.best_score,
            run.run_order_within_target,
        ),
    ).run_order_within_target


def _exact_heuristic_instance() -> HeuristicInstanceExecution:
    runs = (
        _run(
            run_order=1,
            seed=101,
            target_r=2,
            budget=12,
            stop_on_feasible=True,
            initialisation_id="accepted_control",
        ),
    )
    target = HeuristicTargetExecution(
        target_order_within_instance=1,
        target_r=2,
        runs=runs,
        best_run_order=_best_order(runs),
        success=True,
    )
    return HeuristicInstanceExecution(
        execution_order=1,
        graph_id="triangle_exact",
        code_length=2,
        accepted_lower_bound=2,
        accepted_upper_bound=3,
        mode="search_completed",
        targets_planned=(2,),
        target_executions=(target,),
        transfer_witness=None,
        transfer_metadata=None,
    )


def _negative_instance() -> HeuristicInstanceExecution:
    runs = (
        _run(
            run_order=1,
            seed=201,
            target_r=1,
            budget=20,
            stop_on_feasible=False,
            initialisation_id="random_0",
        ),
        _run(
            run_order=2,
            seed=202,
            target_r=1,
            budget=20,
            stop_on_feasible=False,
            initialisation_id="random_1",
        ),
    )
    target = HeuristicTargetExecution(
        target_order_within_instance=1,
        target_r=1,
        runs=runs,
        best_run_order=_best_order(runs),
        success=False,
    )
    return HeuristicInstanceExecution(
        execution_order=2,
        graph_id="triangle_negative_control",
        code_length=2,
        accepted_lower_bound=1,
        accepted_upper_bound=2,
        mode="search_completed",
        targets_planned=(1,),
        target_executions=(target,),
        transfer_witness=None,
        transfer_metadata=None,
    )


def _transfer_instance() -> HeuristicInstanceExecution:
    return HeuristicInstanceExecution(
        execution_order=3,
        graph_id="triangle_transfer",
        code_length=2,
        accepted_lower_bound=2,
        accepted_upper_bound=2,
        mode="exact_by_accepted_transfer",
        targets_planned=(),
        target_executions=(),
        transfer_witness=TRIANGLE_CODEBOOK,
        transfer_metadata={
            "source_class": "stage4_witness",
            "source_code_length": 2,
            "target_r": 2,
            "zero_padding_bits": 0,
        },
    )


def _executions() -> tuple[HeuristicInstanceExecution, ...]:
    return (
        _exact_heuristic_instance(),
        _negative_instance(),
        _transfer_instance(),
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_run_artifacts_preserve_complete_replay_evidence(
    tmp_path: Path,
) -> None:
    run = _negative_instance().target_executions[0].runs[0]
    root = tmp_path / "run"

    hashes = write_run_artifacts(root, run)
    loaded = load_run_artifacts(root)

    assert hashes
    assert loaded.result.checkpoint.to_bytes() == (run.result.checkpoint.to_bytes())
    assert loaded.result.steps == run.result.steps
    assert loaded.verification == run.verification
    assert np.array_equal(
        np.load(root / "best_codebook.npy", allow_pickle=False),
        run.result.best_state.codebook,
    )
    trajectory_lines = (
        (root / "trajectory.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(trajectory_lines) == run.result.proposals_executed
    assert all(isinstance(json.loads(line), dict) for line in trajectory_lines)


def test_corrupted_preserved_run_is_rejected(tmp_path: Path) -> None:
    run = _negative_instance().target_executions[0].runs[0]
    root = tmp_path / "run"
    write_run_artifacts(root, run)

    corrupted = np.load(
        root / "best_codebook.npy",
        allow_pickle=False,
    )
    corrupted = np.array(corrupted, copy=True)
    corrupted[0, 0] = 1 - corrupted[0, 0]
    with (root / "best_codebook.npy").open("wb") as handle:
        np.save(handle, corrupted, allow_pickle=False)

    with pytest.raises(ArtifactError, match="preserved array"):
        load_run_artifacts(root)


def test_instance_validation_enforces_terminal_target_sequence() -> None:
    negative = _negative_instance()

    with pytest.raises(ArtifactError, match="exhaust"):
        HeuristicInstanceExecution(
            execution_order=1,
            graph_id="bad",
            code_length=2,
            accepted_lower_bound=1,
            accepted_upper_bound=3,
            mode="search_completed",
            targets_planned=(1, 2),
            target_executions=negative.target_executions,
            transfer_witness=None,
            transfer_metadata=None,
        )


def test_stage5_tables_have_frozen_schemas_and_interpretation(
    tmp_path: Path,
) -> None:
    table_root = tmp_path / "tables"
    files = write_stage5_tables(
        table_root,
        run_id="stage5-test",
        executions=_executions(),
    )

    assert len(files) == 4

    run_path = table_root / "stage5-test_run_results.csv"
    target_path = table_root / "stage5-test_target_results.csv"
    instance_path = table_root / "stage5-test_instance_bounds.csv"
    exact_path = table_root / "stage5-test_exact_optima.csv"

    assert tuple(next(csv.reader(io.StringIO(run_path.read_text())))) == RUN_FIELDS
    assert (
        tuple(next(csv.reader(io.StringIO(target_path.read_text())))) == TARGET_FIELDS
    )
    assert (
        tuple(next(csv.reader(io.StringIO(instance_path.read_text()))))
        == INSTANCE_FIELDS
    )
    assert tuple(next(csv.reader(io.StringIO(exact_path.read_text())))) == EXACT_FIELDS

    runs = _read_csv(run_path)
    targets = _read_csv(target_path)
    instances = _read_csv(instance_path)
    exact = _read_csv(exact_path)

    assert len(runs) == 3
    assert len(targets) == 2
    assert len(instances) == 3
    assert len(exact) == 2

    negative_target = next(row for row in targets if row["target_r"] == "1")
    assert negative_target["success"] == "False"
    assert negative_target["negative_result_interpretation"] == (
        NEGATIVE_RESULT_INTERPRETATION
    )

    negative_instance = next(
        row for row in instances if row["graph_id"] == "triangle_negative_control"
    )
    assert negative_instance["classification"] == ("no_heuristic_improvement")
    assert negative_instance["negative_result_interpretation"] == (
        NEGATIVE_RESULT_INTERPRETATION
    )

    established_by = {row["established_by"] for row in exact}
    assert established_by == {
        "exact_by_heuristic_witness",
        "exact_by_accepted_transfer",
    }


def test_combined_stage5_artifacts_are_reproducible(
    tmp_path: Path,
) -> None:
    results = []

    for index in range(2):
        root = tmp_path / f"reproduction_{index}"
        generated = generate_stage5_artifacts(
            plan_sha256="a" * 64,
            configuration_sha256="b" * 64,
            executions=_executions(),
            package_root=root / "raw" / "stage5-test-run",
            table_root=root / "tables",
            archive_path=root / "stage5-test-run.tar.gz",
            run_id="stage5-test-run",
        )
        results.append((root, generated))

    assert results[0][1] == results[1][1]
    assert collect_file_hashes(results[0][0] / "raw") == collect_file_hashes(
        results[1][0] / "raw"
    )
    assert (results[0][0] / "stage5-test-run.tar.gz").read_bytes() == (
        results[1][0] / "stage5-test-run.tar.gz"
    ).read_bytes()

    generated = results[0][1]
    assert generated["instance_count"] == 3
    assert generated["run_count"] == 3
    assert generated["target_count_attempted"] == 2
    assert generated["table_file_count"] == 4
    assert generated["exact_optimum_count"] == 2
    assert generated["classification_counts"] == {
        "exact_by_accepted_transfer": 1,
        "exact_by_heuristic_witness": 1,
        "heuristic_upper_bound_improved": 0,
        "no_heuristic_improvement": 1,
    }

    metadata_path = results[0][0] / "raw" / "stage5-test-run" / "package_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["negative_result_interpretation"] == (
        NEGATIVE_RESULT_INTERPRETATION
    )
    assert metadata["run_count"] == 3

    with tarfile.open(
        results[0][0] / "stage5-test-run.tar.gz",
        mode="r:gz",
    ) as archive:
        members = archive.getmembers()

    assert len(members) == generated["archive_member_count"]
    assert all(member.mtime == 0 for member in members)


def test_existing_artifact_destinations_are_rejected(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "raw"
    package_root.mkdir()

    with pytest.raises(FileExistsError):
        generate_stage5_artifacts(
            plan_sha256="a" * 64,
            configuration_sha256="b" * 64,
            executions=_executions(),
            package_root=package_root,
            table_root=tmp_path / "tables",
            archive_path=tmp_path / "archive.tar.gz",
            run_id="stage5-test",
        )


def test_invalid_hashes_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError, match="plan hash"):
        generate_stage5_artifacts(
            plan_sha256="short",
            configuration_sha256="b" * 64,
            executions=_executions(),
            package_root=tmp_path / "raw",
            table_root=tmp_path / "tables",
            archive_path=tmp_path / "archive.tar.gz",
            run_id="stage5-test",
        )

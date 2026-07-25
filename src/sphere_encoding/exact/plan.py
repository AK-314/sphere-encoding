"""Frozen Stage 4 input validation and deterministic target planning."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from sphere_encoding.config import config_sha256, load_json_config
from sphere_encoding.exact.model import structural_lower_bound
from sphere_encoding.exact.solver import recompute_edge_hamming
from sphere_encoding.graphs.artifacts import npy_bytes
from sphere_encoding.hashing import sha256_file


@dataclass(frozen=True)
class FrozenInputIdentity:
    """Verified identity of one accepted upstream stage."""

    stage_name: str
    run_id: str
    manifest_path: str
    archive_path: str
    package_path: str
    configuration_sha256: str
    package_tree_sha256: str
    archive_sha256: str
    table_set_sha256: str | None


@dataclass(frozen=True)
class BaselineChoice:
    """Deterministically selected Stage 3 upper-bound codebook."""

    graph_id: str
    requested_code_length: int
    encoding_id: str
    native_code_length: int
    padding_bits: int
    l_max: int
    minimum_lmax_tie_count: int
    source_codes_path: str
    source_codes_sha256: str
    selected_codebook_sha256: str
    vertex_count: int
    unique_codeword_count: int


@dataclass(frozen=True)
class TargetPlan:
    """One frozen threshold-feasibility target."""

    target_order_within_instance: int
    target_r: int
    budget_seconds: int
    baseline_hint_eligible: bool


@dataclass(frozen=True)
class InstancePlan:
    """One frozen graph/code-length exact-search instance."""

    execution_order: int
    instance_class: str
    graph_id: str
    code_length: int
    vertex_count: int
    edge_count: int
    structural_lower_bound: int
    odd_cycle: tuple[int, ...] | None
    baseline: BaselineChoice
    total_budget_seconds: int
    per_target_budget_seconds: int
    targets: tuple[TargetPlan, ...]


@dataclass(frozen=True)
class Stage4Plan:
    """Complete deterministic Stage 4 execution plan."""

    stage: int
    stage_name: str
    configuration_path: str
    configuration_sha256: str
    input_identities: tuple[FrozenInputIdentity, ...]
    instances: tuple[InstancePlan, ...]
    instance_count: int
    target_count: int
    total_budget_seconds: int
    hint_eligible_target_count: int
    baseline_tie_instance_count: int
    plan_sha256: str


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def verify_frozen_input_identities(
    repository_root: Path,
    config: dict[str, Any],
) -> tuple[FrozenInputIdentity, ...]:
    """Verify all frozen Stage 2 and Stage 3 identities."""

    root = repository_root.resolve()
    identities: list[FrozenInputIdentity] = []

    for stage_name in ("stage2", "stage3"):
        frozen = config["input"][stage_name]
        run_id = str(frozen["run_id"])

        manifest_path = root / "manifests" / f"{run_id}.json"
        archive_path = (
            root / "results" / "archives" / f"{run_id}.tar.gz"
        )
        package_path = root / "results" / "raw" / run_id

        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"missing frozen manifest: {manifest_path}"
            )
        if not archive_path.is_file():
            raise FileNotFoundError(
                f"missing frozen archive: {archive_path}"
            )
        if not package_path.is_dir():
            raise FileNotFoundError(
                f"missing frozen package: {package_path}"
            )

        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        payload = manifest["payload"]

        actual_archive_sha256 = sha256_file(archive_path)
        expected_archive_sha256 = str(frozen["archive_sha256"])

        if actual_archive_sha256 != expected_archive_sha256:
            raise ValueError(
                f"{stage_name} archive identity mismatch"
            )

        actual_config_sha256 = str(payload["config"]["sha256"])
        expected_config_sha256 = str(
            frozen["configuration_sha256"]
        )

        if actual_config_sha256 != expected_config_sha256:
            raise ValueError(
                f"{stage_name} configuration identity mismatch"
            )

        if stage_name == "stage2":
            actual_package_tree_sha256 = str(
                payload["deterministic_outputs"][
                    "package_tree_sha256"
                ]
            )
            actual_table_set_sha256 = None
        else:
            actual_package_tree_sha256 = str(
                payload["deterministic_outputs"]["raw_package"][
                    "package_tree_sha256"
                ]
            )
            actual_table_set_sha256 = str(
                payload["deterministic_outputs"]["tables"][
                    "table_set_sha256"
                ]
            )

        expected_package_tree_sha256 = str(
            frozen["package_tree_sha256"]
        )

        if (
            actual_package_tree_sha256
            != expected_package_tree_sha256
        ):
            raise ValueError(
                f"{stage_name} package-tree identity mismatch"
            )

        expected_table_set_sha256 = frozen.get(
            "table_set_sha256"
        )

        if expected_table_set_sha256 is not None:
            if (
                actual_table_set_sha256
                != str(expected_table_set_sha256)
            ):
                raise ValueError(
                    f"{stage_name} table-set identity mismatch"
                )

        identities.append(
            FrozenInputIdentity(
                stage_name=stage_name,
                run_id=run_id,
                manifest_path=_relative_path(root, manifest_path),
                archive_path=_relative_path(root, archive_path),
                package_path=_relative_path(root, package_path),
                configuration_sha256=actual_config_sha256,
                package_tree_sha256=actual_package_tree_sha256,
                archive_sha256=actual_archive_sha256,
                table_set_sha256=actual_table_set_sha256,
            )
        )

    return tuple(identities)


def load_stage3_baseline_rows(
    repository_root: Path,
    stage3_run_id: str,
) -> tuple[dict[str, str], ...]:
    """Load the accepted Stage 3 summary in committed row order."""

    path = (
        repository_root
        / "results"
        / "tables"
        / f"{stage3_run_id}_baseline_summary.csv"
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"missing Stage 3 baseline summary: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        rows = tuple(csv.DictReader(stream))

    if not rows:
        raise ValueError("Stage 3 baseline summary is empty")

    required_columns = {
        "graph_id",
        "encoding_id",
        "vertex_count",
        "code_length",
        "L_max",
        "collision_count",
        "unique_codeword_count",
    }
    missing = required_columns - set(rows[0])

    if missing:
        raise ValueError(
            "Stage 3 baseline summary is missing columns: "
            f"{sorted(missing)}"
        )

    return rows


def select_baseline_row(
    rows: tuple[dict[str, str], ...],
    *,
    graph_id: str,
    requested_code_length: int,
) -> tuple[dict[str, str], int]:
    """Apply the frozen baseline applicability and tie-break rules."""

    candidates: list[
        tuple[int, int, str, dict[str, str]]
    ] = []

    for row in rows:
        if row["graph_id"] != graph_id:
            continue

        encoding_id = row["encoding_id"]
        native_code_length = int(row["code_length"])
        l_max = int(row["L_max"])
        vertex_count = int(row["vertex_count"])
        collision_count = int(row["collision_count"])
        unique_count = int(row["unique_codeword_count"])

        if (
            collision_count != 0
            or unique_count != vertex_count
        ):
            raise ValueError(
                f"non-injective baseline row: "
                f"{graph_id}/{encoding_id}"
            )

        is_cartesian = encoding_id.startswith(
            "cartesian_coordinate_"
        )

        if is_cartesian:
            eligible = (
                native_code_length == requested_code_length
            )
        else:
            eligible = (
                native_code_length <= requested_code_length
            )

        if eligible:
            candidates.append(
                (
                    l_max,
                    native_code_length,
                    encoding_id,
                    row,
                )
            )

    if not candidates:
        raise ValueError(
            f"no eligible baseline for "
            f"{graph_id}, m={requested_code_length}"
        )

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    selected = candidates[0]
    minimum_lmax = selected[0]
    minimum_lmax_tie_count = sum(
        candidate[0] == minimum_lmax
        for candidate in candidates
    )

    return selected[3], minimum_lmax_tie_count


def equal_target_budget(
    *,
    total_budget_seconds: int,
    target_count: int,
) -> int:
    """Validate and return the frozen equal per-target budget."""

    if (
        not isinstance(total_budget_seconds, int)
        or isinstance(total_budget_seconds, bool)
    ):
        raise TypeError(
            "total_budget_seconds must be an integer"
        )
    if (
        not isinstance(target_count, int)
        or isinstance(target_count, bool)
    ):
        raise TypeError("target_count must be an integer")
    if total_budget_seconds <= 0:
        raise ValueError(
            "total_budget_seconds must be positive"
        )
    if target_count <= 0:
        raise ValueError("target_count must be positive")
    if total_budget_seconds % target_count != 0:
        raise ValueError(
            "instance budget must divide equally among targets"
        )

    return total_budget_seconds // target_count


def _load_selected_baseline(
    *,
    repository_root: Path,
    stage3_run_id: str,
    graph_id: str,
    requested_code_length: int,
    row: dict[str, str],
    minimum_lmax_tie_count: int,
    edges: np.ndarray,
) -> BaselineChoice:
    encoding_id = row["encoding_id"]
    native_code_length = int(row["code_length"])
    expected_l_max = int(row["L_max"])
    vertex_count = int(row["vertex_count"])

    source_path = (
        repository_root
        / "results"
        / "raw"
        / stage3_run_id
        / graph_id
        / encoding_id
        / "codes.npy"
    )

    if not source_path.is_file():
        raise FileNotFoundError(
            f"missing selected baseline codebook: {source_path}"
        )

    native_codes = np.load(
        source_path,
        allow_pickle=False,
    )

    if native_codes.shape != (
        vertex_count,
        native_code_length,
    ):
        raise ValueError(
            "selected baseline codebook has an invalid shape"
        )

    if not np.issubdtype(native_codes.dtype, np.integer):
        raise TypeError(
            "selected baseline codebook must use integer dtype"
        )

    if np.any(
        (native_codes != 0) & (native_codes != 1)
    ):
        raise ValueError(
            "selected baseline codebook is not binary"
        )

    is_cartesian = encoding_id.startswith(
        "cartesian_coordinate_"
    )

    if is_cartesian:
        if native_code_length != requested_code_length:
            raise ValueError(
                "Cartesian baseline may not be length-adjusted"
            )
        selected_codes = np.asarray(
            native_codes,
            dtype=np.uint8,
        )
        padding_bits = 0
    else:
        if native_code_length > requested_code_length:
            raise ValueError(
                "index baseline is longer than requested length"
            )
        padding_bits = (
            requested_code_length - native_code_length
        )
        padding = np.zeros(
            (vertex_count, padding_bits),
            dtype=np.uint8,
        )
        selected_codes = np.concatenate(
            [
                np.asarray(native_codes, dtype=np.uint8),
                padding,
            ],
            axis=1,
        )

    selected_codes = np.ascontiguousarray(selected_codes)

    packed = np.packbits(
        selected_codes,
        axis=1,
        bitorder="little",
    )
    unique_count = len(
        {bytes(row_values) for row_values in packed}
    )

    if unique_count != vertex_count:
        raise ValueError(
            "selected baseline codebook is not injective"
        )

    distances = recompute_edge_hamming(
        selected_codes,
        edges,
    )
    actual_l_max = (
        int(np.max(distances))
        if len(distances)
        else 0
    )

    if actual_l_max != expected_l_max:
        raise ValueError(
            "selected baseline L_max differs from Stage 3"
        )

    return BaselineChoice(
        graph_id=graph_id,
        requested_code_length=requested_code_length,
        encoding_id=encoding_id,
        native_code_length=native_code_length,
        padding_bits=padding_bits,
        l_max=actual_l_max,
        minimum_lmax_tie_count=minimum_lmax_tie_count,
        source_codes_path=_relative_path(
            repository_root,
            source_path,
        ),
        source_codes_sha256=sha256_file(source_path),
        selected_codebook_sha256=hashlib.sha256(
            npy_bytes(selected_codes)
        ).hexdigest(),
        vertex_count=vertex_count,
        unique_codeword_count=unique_count,
    )


def _plan_payload_without_hash(
    *,
    stage: int,
    stage_name: str,
    configuration_path: str,
    configuration_sha256_value: str,
    input_identities: tuple[FrozenInputIdentity, ...],
    instances: tuple[InstancePlan, ...],
    instance_count: int,
    target_count: int,
    total_budget_seconds: int,
    hint_eligible_target_count: int,
    baseline_tie_instance_count: int,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "stage_name": stage_name,
        "configuration_path": configuration_path,
        "configuration_sha256": (
            configuration_sha256_value
        ),
        "input_identities": [
            asdict(identity)
            for identity in input_identities
        ],
        "instances": [
            asdict(instance)
            for instance in instances
        ],
        "instance_count": instance_count,
        "target_count": target_count,
        "total_budget_seconds": total_budget_seconds,
        "hint_eligible_target_count": (
            hint_eligible_target_count
        ),
        "baseline_tie_instance_count": (
            baseline_tie_instance_count
        ),
    }


def stage4_plan_payload(
    plan: Stage4Plan,
) -> dict[str, Any]:
    """Return the canonical serialisable plan payload."""

    payload = asdict(plan)
    return payload


def derive_stage4_plan(
    repository_root: Path,
    *,
    config_path: Path | None = None,
) -> Stage4Plan:
    """Derive the complete frozen Stage 4 execution plan."""

    root = repository_root.resolve()
    resolved_config_path = (
        config_path.resolve()
        if config_path is not None
        else root / "configs" / "stage4_exact.json"
    )

    config = load_json_config(resolved_config_path)
    configuration_sha256_value = config_sha256(config)

    input_identities = verify_frozen_input_identities(
        root,
        config,
    )

    stage2_run_id = str(
        config["input"]["stage2"]["run_id"]
    )
    stage3_run_id = str(
        config["input"]["stage3"]["run_id"]
    )

    rows = load_stage3_baseline_rows(
        root,
        stage3_run_id,
    )

    instances: list[InstancePlan] = []

    for frozen_instance in config["suite"]["instances"]:
        execution_order = int(
            frozen_instance["execution_order"]
        )
        graph_id = str(frozen_instance["graph_id"])
        code_length = int(
            frozen_instance["code_length"]
        )
        total_budget_seconds = int(
            frozen_instance["total_budget_seconds"]
        )
        instance_class = str(
            frozen_instance["instance_class"]
        )

        graph_root = (
            root
            / "results"
            / "raw"
            / stage2_run_id
            / graph_id
        )

        metadata_path = graph_root / "metadata.json"
        edges_path = graph_root / "edges.npy"

        if not metadata_path.is_file():
            raise FileNotFoundError(
                f"missing graph metadata: {metadata_path}"
            )
        if not edges_path.is_file():
            raise FileNotFoundError(
                f"missing graph edges: {edges_path}"
            )

        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
        diagnostics = metadata["diagnostics"]
        vertex_count = int(diagnostics["vertex_count"])
        expected_edge_count = int(
            diagnostics["edge_count"]
        )

        edges = np.load(
            edges_path,
            allow_pickle=False,
        )

        if edges.shape != (expected_edge_count, 2):
            raise ValueError(
                f"graph edge shape mismatch: {graph_id}"
            )

        evidence = structural_lower_bound(
            vertex_count,
            edges,
        )

        row, tie_count = select_baseline_row(
            rows,
            graph_id=graph_id,
            requested_code_length=code_length,
        )

        baseline = _load_selected_baseline(
            repository_root=root,
            stage3_run_id=stage3_run_id,
            graph_id=graph_id,
            requested_code_length=code_length,
            row=row,
            minimum_lmax_tie_count=tie_count,
            edges=edges,
        )

        target_values = tuple(
            range(
                evidence.lower_bound,
                baseline.l_max,
            )
        )

        per_target_budget_seconds = equal_target_budget(
            total_budget_seconds=total_budget_seconds,
            target_count=len(target_values),
        )

        targets = tuple(
            TargetPlan(
                target_order_within_instance=index,
                target_r=target_r,
                budget_seconds=per_target_budget_seconds,
                baseline_hint_eligible=(
                    baseline.l_max <= target_r
                ),
            )
            for index, target_r in enumerate(
                target_values,
                start=1,
            )
        )

        instances.append(
            InstancePlan(
                execution_order=execution_order,
                instance_class=instance_class,
                graph_id=graph_id,
                code_length=code_length,
                vertex_count=vertex_count,
                edge_count=len(edges),
                structural_lower_bound=(
                    evidence.lower_bound
                ),
                odd_cycle=evidence.odd_cycle,
                baseline=baseline,
                total_budget_seconds=(
                    total_budget_seconds
                ),
                per_target_budget_seconds=(
                    per_target_budget_seconds
                ),
                targets=targets,
            )
        )

    instance_tuple = tuple(instances)

    expected_orders = tuple(
        range(1, len(instance_tuple) + 1)
    )
    actual_orders = tuple(
        instance.execution_order
        for instance in instance_tuple
    )

    if actual_orders != expected_orders:
        raise ValueError(
            "frozen instance execution order is not contiguous"
        )

    instance_count = len(instance_tuple)
    target_count = sum(
        len(instance.targets)
        for instance in instance_tuple
    )
    total_budget_seconds = sum(
        instance.total_budget_seconds
        for instance in instance_tuple
    )
    hint_eligible_target_count = sum(
        target.baseline_hint_eligible
        for instance in instance_tuple
        for target in instance.targets
    )
    baseline_tie_instance_count = sum(
        instance.baseline.minimum_lmax_tie_count > 1
        for instance in instance_tuple
    )

    configured_instance_count = int(
        config["suite"]["instance_count"]
    )

    if instance_count != configured_instance_count:
        raise ValueError(
            "derived instance count differs from config"
        )

    payload = _plan_payload_without_hash(
        stage=int(config["stage"]),
        stage_name=str(config["stage_name"]),
        configuration_path=_relative_path(
            root,
            resolved_config_path,
        ),
        configuration_sha256_value=(
            configuration_sha256_value
        ),
        input_identities=input_identities,
        instances=instance_tuple,
        instance_count=instance_count,
        target_count=target_count,
        total_budget_seconds=total_budget_seconds,
        hint_eligible_target_count=(
            hint_eligible_target_count
        ),
        baseline_tie_instance_count=(
            baseline_tie_instance_count
        ),
    )

    plan_sha256 = hashlib.sha256(
        _canonical_json_bytes(payload)
    ).hexdigest()

    return Stage4Plan(
        stage=int(config["stage"]),
        stage_name=str(config["stage_name"]),
        configuration_path=_relative_path(
            root,
            resolved_config_path,
        ),
        configuration_sha256=configuration_sha256_value,
        input_identities=input_identities,
        instances=instance_tuple,
        instance_count=instance_count,
        target_count=target_count,
        total_budget_seconds=total_budget_seconds,
        hint_eligible_target_count=hint_eligible_target_count,
        baseline_tie_instance_count=baseline_tie_instance_count,
        plan_sha256=plan_sha256,
    )

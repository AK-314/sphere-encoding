"""Deterministic Stage 5 suite and initialisation planning."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Literal

import numpy as np

from sphere_encoding.config import canonical_json_dumps
from sphere_encoding.exact.model import structural_lower_bound
from sphere_encoding.heuristic.initialisation import file_sha256
from sphere_encoding.heuristic.scoring import edge_distances_for_state
from sphere_encoding.heuristic.state import SearchState, SearchStateError

STAGE2_RUN_ID: Final = "stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50"
STAGE3_RUN_ID: Final = "stage3-deterministic-baselines-3fad68b97de9-f07ae893574e"
STAGE4_RUN_ID: Final = "stage4-exact-free-codebook-97021c6cac03-7adb5b49f2cb"

GRAPH_ORDER: Final = (
    "icosphere_l0",
    "icosphere_l1",
    "icosphere_l2",
    "icosphere_l3",
    "primitive_q2_knn4",
    "primitive_q2_knn6",
    "primitive_q2_knn8",
    "primitive_q3_knn4",
    "primitive_q3_knn6",
    "primitive_q3_knn8",
    "primitive_q4_knn4",
    "primitive_q4_knn6",
    "primitive_q4_knn8",
)
CODE_LENGTH_OFFSETS: Final = (0, 1, 2, 4)
PLAN_SCHEMA_VERSION: Final = "stage5_heuristic_plan_v1"

SourceClass = Literal["stage3_baseline", "stage4_witness"]
InstanceClassification = Literal[
    "search_required",
    "exact_by_accepted_transfer",
]


class PlanningError(ValueError):
    """Raised when accepted inputs cannot produce the frozen Stage 5 plan."""


@dataclass(frozen=True, slots=True)
class GraphPlanningRecord:
    """Accepted graph identity and structural lower-bound evidence."""

    graph_id: str
    graph_order: int
    vertex_count: int
    edge_count: int
    minimum_code_length: int
    structural_lower_bound: int
    bipartite: bool
    odd_cycle: tuple[int, ...] | None
    metadata_path: str
    metadata_sha256: str
    edges_path: str
    edges_sha256: str


@dataclass(frozen=True, slots=True)
class NativeCodebookSource:
    """One accepted native-width Stage 3 or Stage 4 codebook."""

    source_class: SourceClass
    graph_id: str
    source_id: str
    source_code_length: int
    local_l_max: int
    source_path: str
    source_sha256: str
    stage3_encoding_id: str | None
    stage4_target_r: int | None

    def __post_init__(self) -> None:
        if self.source_class not in {
            "stage3_baseline",
            "stage4_witness",
        }:
            raise PlanningError("unrecognised codebook source class")
        if not self.graph_id or not self.source_id:
            raise PlanningError("source identity must be non-empty")
        if self.source_code_length <= 0:
            raise PlanningError("source code length must be positive")
        if self.local_l_max < 0:
            raise PlanningError("source L_max must be non-negative")
        if len(self.source_sha256) != 64:
            raise PlanningError("source SHA-256 must contain 64 hex characters")

        if self.source_class == "stage3_baseline":
            if self.stage3_encoding_id is None:
                raise PlanningError("Stage 3 source lacks encoding identity")
            if self.stage4_target_r is not None:
                raise PlanningError("Stage 3 source has a Stage 4 target")
        else:
            if self.stage3_encoding_id is not None:
                raise PlanningError("Stage 4 source has a Stage 3 encoding")
            if self.stage4_target_r is None:
                raise PlanningError("Stage 4 source lacks target identity")
            if self.local_l_max > self.stage4_target_r:
                raise PlanningError("Stage 4 witness exceeds its target")


@dataclass(frozen=True, slots=True)
class PlannedInitialisation:
    """One accepted source adapted to a Stage 5 target code length."""

    source_class: SourceClass
    graph_id: str
    source_id: str
    source_code_length: int
    target_code_length: int
    zero_padding_bits: int
    transfer_rule: Literal["same_length", "append_zero_bits"]
    local_l_max: int
    source_path: str
    source_sha256: str
    stage3_encoding_id: str | None
    stage4_target_r: int | None

    def __post_init__(self) -> None:
        if self.target_code_length < self.source_code_length:
            raise PlanningError("longer-to-shorter initialisation is prohibited")
        if self.zero_padding_bits != (
            self.target_code_length - self.source_code_length
        ):
            raise PlanningError("zero-padding metadata is inconsistent")
        expected_rule = (
            "same_length" if self.zero_padding_bits == 0 else "append_zero_bits"
        )
        if self.transfer_rule != expected_rule:
            raise PlanningError("initialisation transfer rule is inconsistent")


@dataclass(frozen=True, slots=True)
class Stage5TargetPlan:
    """One unresolved threshold attempted in ascending order."""

    target_order_within_instance: int
    target_r: int

    def __post_init__(self) -> None:
        if self.target_order_within_instance <= 0:
            raise PlanningError("target order must be positive")
        if self.target_r < 0:
            raise PlanningError("target threshold must be non-negative")


@dataclass(frozen=True, slots=True)
class DirectStage4ExactPair:
    """A global-grid pair excluded because Stage 4 solved it directly."""

    graph_id: str
    code_length: int
    exact_l_star_free: int


@dataclass(frozen=True, slots=True)
class Stage5InstancePlan:
    """One global-grid pair not directly exact in Stage 4."""

    execution_order: int
    graph_id: str
    graph_order: int
    vertex_count: int
    edge_count: int
    minimum_code_length: int
    code_length: int
    excess_bits: int
    accepted_lower_bound: int
    accepted_upper_bound: int
    classification: InstanceClassification
    accepted_upper_bound_source: PlannedInitialisation
    stage3_initialisation: PlannedInitialisation
    stage4_initialisation: PlannedInitialisation | None
    random_initialisation_class: str
    targets: tuple[Stage5TargetPlan, ...]

    def __post_init__(self) -> None:
        if self.execution_order <= 0:
            raise PlanningError("instance execution order must be positive")
        if self.code_length < self.minimum_code_length:
            raise PlanningError("instance code length is below m0")
        if self.excess_bits != self.code_length - self.minimum_code_length:
            raise PlanningError("instance excess-bit count is inconsistent")
        if self.accepted_lower_bound > self.accepted_upper_bound:
            raise PlanningError("accepted lower bound exceeds upper bound")
        if self.random_initialisation_class != "deterministic_random":
            raise PlanningError("random initialisation class differs from freeze")

        expected_targets = tuple(
            range(self.accepted_lower_bound, self.accepted_upper_bound)
        )
        actual_targets = tuple(target.target_r for target in self.targets)
        if actual_targets != expected_targets:
            raise PlanningError("target list is not the complete ascending gap")
        if tuple(
            target.target_order_within_instance for target in self.targets
        ) != tuple(range(1, len(self.targets) + 1)):
            raise PlanningError("target execution order is not contiguous")

        expected_classification: InstanceClassification = (
            "exact_by_accepted_transfer"
            if self.accepted_lower_bound == self.accepted_upper_bound
            else "search_required"
        )
        if self.classification != expected_classification:
            raise PlanningError("instance classification is inconsistent")
        if self.classification == "exact_by_accepted_transfer" and self.targets:
            raise PlanningError("exact transfer instance must have no targets")


@dataclass(frozen=True, slots=True)
class Stage5Plan:
    """Complete deterministic pre-budget Stage 5 planning inventory."""

    schema_version: str
    stage2_run_id: str
    stage3_run_id: str
    stage4_run_id: str
    graph_order: tuple[str, ...]
    code_length_offsets: tuple[int, ...]
    graphs: tuple[GraphPlanningRecord, ...]
    direct_stage4_exact_pairs: tuple[DirectStage4ExactPair, ...]
    instances: tuple[Stage5InstancePlan, ...]
    global_grid_pair_count: int
    direct_stage4_exact_pair_count: int
    candidate_instance_count: int
    search_required_instance_count: int
    exact_by_transfer_instance_count: int
    unresolved_target_count: int
    plan_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != PLAN_SCHEMA_VERSION:
            raise PlanningError("unexpected plan schema version")
        if self.graph_order != GRAPH_ORDER:
            raise PlanningError("graph order differs from the frozen order")
        if self.code_length_offsets != CODE_LENGTH_OFFSETS:
            raise PlanningError("code-length offsets differ from the frozen grid")
        if self.global_grid_pair_count != (
            len(self.graphs) * len(self.code_length_offsets)
        ):
            raise PlanningError("global-grid pair count is inconsistent")
        if self.direct_stage4_exact_pair_count != len(self.direct_stage4_exact_pairs):
            raise PlanningError("direct-exact pair count is inconsistent")
        if self.candidate_instance_count != len(self.instances):
            raise PlanningError("candidate instance count is inconsistent")
        if (
            self.direct_stage4_exact_pair_count + self.candidate_instance_count
            != self.global_grid_pair_count
        ):
            raise PlanningError("global-grid partition is incomplete")
        if self.search_required_instance_count != sum(
            instance.classification == "search_required" for instance in self.instances
        ):
            raise PlanningError("search-required count is inconsistent")
        if self.exact_by_transfer_instance_count != sum(
            instance.classification == "exact_by_accepted_transfer"
            for instance in self.instances
        ):
            raise PlanningError("transfer-exact count is inconsistent")
        if self.unresolved_target_count != sum(
            len(instance.targets) for instance in self.instances
        ):
            raise PlanningError("unresolved target count is inconsistent")
        if len(self.plan_sha256) != 64:
            raise PlanningError("plan hash must contain 64 hex characters")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PlanningError(f"required accepted table is missing: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise PlanningError(f"required accepted table is empty: {path}")
    return rows


def _read_json_object(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise PlanningError(f"required accepted JSON is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PlanningError(f"could not read accepted JSON: {path}") from error
    if not isinstance(value, dict):
        raise PlanningError(f"accepted JSON is not an object: {path}")
    return value


def _relative(repository_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as error:
        raise PlanningError(f"path is outside repository: {path}") from error


def _truthy(value: str) -> bool:
    normalised = value.strip().lower()
    if normalised in {"true", "1", "yes"}:
        return True
    if normalised in {"false", "0", "no"}:
        return False
    raise PlanningError(f"invalid Boolean table value: {value!r}")


def _load_graphs(
    repository_root: Path,
) -> tuple[tuple[GraphPlanningRecord, ...], dict[str, np.ndarray]]:
    stage2_root = repository_root / "results" / "raw" / STAGE2_RUN_ID
    records: list[GraphPlanningRecord] = []
    edges_by_graph: dict[str, np.ndarray] = {}

    for graph_order, graph_id in enumerate(GRAPH_ORDER, start=1):
        graph_root = stage2_root / graph_id
        metadata_path = graph_root / "metadata.json"
        edges_path = graph_root / "edges.npy"
        metadata = _read_json_object(metadata_path)

        diagnostics = metadata.get("diagnostics")
        if not isinstance(diagnostics, dict):
            raise PlanningError(f"graph diagnostics are missing: {graph_id}")

        vertex_count = int(diagnostics["vertex_count"])
        edge_count = int(diagnostics["edge_count"])
        minimum_code_length = int(diagnostics["minimum_bits"])

        try:
            edges = np.load(edges_path, allow_pickle=False)
        except (OSError, ValueError) as error:
            raise PlanningError(f"could not load graph edges: {graph_id}") from error

        if edges.shape != (edge_count, 2):
            raise PlanningError(f"graph edge shape differs: {graph_id}")

        bound = structural_lower_bound(vertex_count, edges)
        immutable_edges = np.array(
            edges,
            dtype=np.int64,
            order="C",
            copy=True,
        )
        immutable_edges.setflags(write=False)
        edges_by_graph[graph_id] = immutable_edges

        records.append(
            GraphPlanningRecord(
                graph_id=graph_id,
                graph_order=graph_order,
                vertex_count=vertex_count,
                edge_count=edge_count,
                minimum_code_length=minimum_code_length,
                structural_lower_bound=bound.lower_bound,
                bipartite=bound.bipartite,
                odd_cycle=bound.odd_cycle,
                metadata_path=_relative(repository_root, metadata_path),
                metadata_sha256=file_sha256(metadata_path),
                edges_path=_relative(repository_root, edges_path),
                edges_sha256=file_sha256(edges_path),
            )
        )

    return tuple(records), edges_by_graph


def _validate_source_codebook(
    *,
    repository_root: Path,
    path: Path,
    graph_id: str,
    source_code_length: int,
    expected_l_max: int,
    expected_vertex_count: int,
    edges: np.ndarray,
) -> str:
    try:
        state = SearchState.from_codebook(np.load(path, allow_pickle=False))
    except (OSError, ValueError, SearchStateError) as error:
        raise PlanningError(f"invalid accepted codebook: {path}") from error

    if state.vertex_count != expected_vertex_count:
        raise PlanningError(f"codebook vertex count differs: {path}")
    if state.code_length != source_code_length:
        raise PlanningError(f"codebook width differs: {path}")

    distances = edge_distances_for_state(state, edges)
    actual_l_max = int(np.max(distances))
    if actual_l_max != expected_l_max:
        raise PlanningError(
            f"accepted L_max differs for {graph_id}: "
            f"expected {expected_l_max}, found {actual_l_max}"
        )

    return _relative(repository_root, path)


def _load_stage3_sources(
    repository_root: Path,
    graph_records: dict[str, GraphPlanningRecord],
    edges_by_graph: dict[str, np.ndarray],
) -> dict[str, tuple[NativeCodebookSource, ...]]:
    table_path = (
        repository_root / "results" / "tables" / f"{STAGE3_RUN_ID}_baseline_summary.csv"
    )
    rows = _read_csv(table_path)
    by_graph: dict[str, list[NativeCodebookSource]] = {
        graph_id: [] for graph_id in GRAPH_ORDER
    }

    for row in rows:
        graph_id = row["graph_id"]
        if graph_id not in graph_records:
            raise PlanningError(f"unexpected Stage 3 graph: {graph_id}")

        encoding_id = row["encoding_id"]
        source_code_length = int(row["code_length"])
        local_l_max = int(row["L_max"])
        path = (
            repository_root
            / "results"
            / "raw"
            / STAGE3_RUN_ID
            / graph_id
            / encoding_id
            / "codes.npy"
        )

        relative_path = _validate_source_codebook(
            repository_root=repository_root,
            path=path,
            graph_id=graph_id,
            source_code_length=source_code_length,
            expected_l_max=local_l_max,
            expected_vertex_count=graph_records[graph_id].vertex_count,
            edges=edges_by_graph[graph_id],
        )

        by_graph[graph_id].append(
            NativeCodebookSource(
                source_class="stage3_baseline",
                graph_id=graph_id,
                source_id=encoding_id,
                source_code_length=source_code_length,
                local_l_max=local_l_max,
                source_path=relative_path,
                source_sha256=file_sha256(path),
                stage3_encoding_id=encoding_id,
                stage4_target_r=None,
            )
        )

    for graph_id in GRAPH_ORDER:
        if not by_graph[graph_id]:
            raise PlanningError(f"Stage 3 source set is empty: {graph_id}")
        by_graph[graph_id].sort(
            key=lambda source: (
                source.source_code_length,
                source.source_id,
                source.source_path,
            )
        )

    return {graph_id: tuple(by_graph[graph_id]) for graph_id in GRAPH_ORDER}


def _load_stage4_inputs(
    repository_root: Path,
    graph_records: dict[str, GraphPlanningRecord],
    edges_by_graph: dict[str, np.ndarray],
) -> tuple[
    dict[str, tuple[NativeCodebookSource, ...]],
    dict[tuple[str, int], int],
    tuple[DirectStage4ExactPair, ...],
]:
    tables_root = repository_root / "results" / "tables"
    target_rows = _read_csv(tables_root / f"{STAGE4_RUN_ID}_target_results.csv")
    bound_rows = _read_csv(tables_root / f"{STAGE4_RUN_ID}_instance_bounds.csv")
    exact_rows = _read_csv(tables_root / f"{STAGE4_RUN_ID}_exact_optima.csv")

    by_graph: dict[str, list[NativeCodebookSource]] = {
        graph_id: [] for graph_id in GRAPH_ORDER
    }

    for row in target_rows:
        if not _truthy(row["has_feasible_witness"]):
            continue

        graph_id = row["graph_id"]
        if graph_id not in graph_records:
            raise PlanningError(f"unexpected Stage 4 graph: {graph_id}")

        source_code_length = int(row["code_length"])
        target_r = int(row["target_r"])
        local_l_max = int(row["witness_l_max"])
        path = (
            repository_root
            / "results"
            / "raw"
            / STAGE4_RUN_ID
            / graph_id
            / f"m{source_code_length}"
            / "targets"
            / f"r{target_r}"
            / "codebook.npy"
        )

        relative_path = _validate_source_codebook(
            repository_root=repository_root,
            path=path,
            graph_id=graph_id,
            source_code_length=source_code_length,
            expected_l_max=local_l_max,
            expected_vertex_count=graph_records[graph_id].vertex_count,
            edges=edges_by_graph[graph_id],
        )
        actual_hash = file_sha256(path)
        recorded_hash = row["witness_codebook_sha256"]
        if actual_hash != recorded_hash:
            raise PlanningError(f"Stage 4 witness hash differs: {path}")

        by_graph[graph_id].append(
            NativeCodebookSource(
                source_class="stage4_witness",
                graph_id=graph_id,
                source_id=f"m{source_code_length}_r{target_r}",
                source_code_length=source_code_length,
                local_l_max=local_l_max,
                source_path=relative_path,
                source_sha256=actual_hash,
                stage3_encoding_id=None,
                stage4_target_r=target_r,
            )
        )

    for graph_id in GRAPH_ORDER:
        by_graph[graph_id].sort(
            key=lambda source: (
                source.source_code_length,
                source.stage4_target_r,
                source.source_path,
            )
        )

    final_lower_bounds: dict[tuple[str, int], int] = {}
    for row in bound_rows:
        pair = (row["graph_id"], int(row["code_length"]))
        if pair in final_lower_bounds:
            raise PlanningError(f"duplicate Stage 4 bound row: {pair}")
        final_lower_bounds[pair] = int(row["final_lower_bound"])

    graph_rank = {graph_id: index for index, graph_id in enumerate(GRAPH_ORDER)}
    exact_pairs = []
    for row in exact_rows:
        exact_pairs.append(
            DirectStage4ExactPair(
                graph_id=row["graph_id"],
                code_length=int(row["code_length"]),
                exact_l_star_free=int(row["exact_l_star_free"]),
            )
        )
    exact_pairs.sort(
        key=lambda pair: (
            graph_rank[pair.graph_id],
            pair.code_length,
        )
    )

    if len({(pair.graph_id, pair.code_length) for pair in exact_pairs}) != len(
        exact_pairs
    ):
        raise PlanningError("duplicate Stage 4 exact pair")

    return (
        {graph_id: tuple(by_graph[graph_id]) for graph_id in GRAPH_ORDER},
        final_lower_bounds,
        tuple(exact_pairs),
    )


def _adapt_source(
    source: NativeCodebookSource,
    target_code_length: int,
) -> PlannedInitialisation:
    if source.source_code_length > target_code_length:
        raise PlanningError("longer source cannot initialise shorter target")
    zero_padding_bits = target_code_length - source.source_code_length
    return PlannedInitialisation(
        source_class=source.source_class,
        graph_id=source.graph_id,
        source_id=source.source_id,
        source_code_length=source.source_code_length,
        target_code_length=target_code_length,
        zero_padding_bits=zero_padding_bits,
        transfer_rule=("same_length" if zero_padding_bits == 0 else "append_zero_bits"),
        local_l_max=source.local_l_max,
        source_path=source.source_path,
        source_sha256=source.source_sha256,
        stage3_encoding_id=source.stage3_encoding_id,
        stage4_target_r=source.stage4_target_r,
    )


def _initialisation_rank(
    initialisation: PlannedInitialisation,
) -> tuple[int, int, int, str, str]:
    source_class_rank = {
        "stage4_witness": 0,
        "stage3_baseline": 1,
    }
    return (
        initialisation.local_l_max,
        initialisation.zero_padding_bits,
        source_class_rank[initialisation.source_class],
        initialisation.source_id,
        initialisation.source_path,
    )


def _eligible_initialisations(
    sources: tuple[NativeCodebookSource, ...],
    target_code_length: int,
) -> tuple[PlannedInitialisation, ...]:
    return tuple(
        _adapt_source(source, target_code_length)
        for source in sources
        if source.source_code_length <= target_code_length
    )


def _plan_payload_without_hash(
    *,
    graphs: tuple[GraphPlanningRecord, ...],
    direct_exact_pairs: tuple[DirectStage4ExactPair, ...],
    instances: tuple[Stage5InstancePlan, ...],
) -> dict[str, object]:
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "stage2_run_id": STAGE2_RUN_ID,
        "stage3_run_id": STAGE3_RUN_ID,
        "stage4_run_id": STAGE4_RUN_ID,
        "graph_order": list(GRAPH_ORDER),
        "code_length_offsets": list(CODE_LENGTH_OFFSETS),
        "graphs": [asdict(graph) for graph in graphs],
        "direct_stage4_exact_pairs": [asdict(pair) for pair in direct_exact_pairs],
        "instances": [asdict(instance) for instance in instances],
        "global_grid_pair_count": (len(graphs) * len(CODE_LENGTH_OFFSETS)),
        "direct_stage4_exact_pair_count": len(direct_exact_pairs),
        "candidate_instance_count": len(instances),
        "search_required_instance_count": sum(
            instance.classification == "search_required" for instance in instances
        ),
        "exact_by_transfer_instance_count": sum(
            instance.classification == "exact_by_accepted_transfer"
            for instance in instances
        ),
        "unresolved_target_count": sum(len(instance.targets) for instance in instances),
    }


def stage5_plan_payload(plan: Stage5Plan) -> dict[str, object]:
    """Return the complete deterministic JSON-compatible plan payload."""
    payload = _plan_payload_without_hash(
        graphs=plan.graphs,
        direct_exact_pairs=plan.direct_stage4_exact_pairs,
        instances=plan.instances,
    )
    payload["plan_sha256"] = plan.plan_sha256
    return payload


def build_stage5_plan(
    repository_root: str | Path,
) -> Stage5Plan:
    """Derive the complete pre-budget Stage 5 inventory from accepted inputs."""
    root = Path(repository_root).resolve()
    graphs, edges_by_graph = _load_graphs(root)
    graph_records = {graph.graph_id: graph for graph in graphs}

    stage3_sources = _load_stage3_sources(
        root,
        graph_records,
        edges_by_graph,
    )
    (
        stage4_sources,
        stage4_lower_bounds,
        direct_exact_pairs,
    ) = _load_stage4_inputs(
        root,
        graph_records,
        edges_by_graph,
    )

    direct_exact_keys = {
        (pair.graph_id, pair.code_length) for pair in direct_exact_pairs
    }
    instances: list[Stage5InstancePlan] = []

    for graph in graphs:
        for offset in CODE_LENGTH_OFFSETS:
            code_length = graph.minimum_code_length + offset
            pair = (graph.graph_id, code_length)

            if pair in direct_exact_keys:
                continue

            eligible_stage3 = _eligible_initialisations(
                stage3_sources[graph.graph_id],
                code_length,
            )
            if not eligible_stage3:
                raise PlanningError(f"no eligible Stage 3 initialisation: {pair}")

            eligible_stage4 = _eligible_initialisations(
                stage4_sources[graph.graph_id],
                code_length,
            )
            all_evidence = (*eligible_stage3, *eligible_stage4)
            if not all_evidence:
                raise PlanningError(f"no accepted upper-bound source: {pair}")

            stage3_initialisation = min(
                eligible_stage3,
                key=_initialisation_rank,
            )
            stage4_initialisation = (
                min(eligible_stage4, key=_initialisation_rank)
                if eligible_stage4
                else None
            )
            upper_source = min(
                all_evidence,
                key=_initialisation_rank,
            )

            accepted_lower_bound = stage4_lower_bounds.get(
                pair,
                graph.structural_lower_bound,
            )
            if accepted_lower_bound < graph.structural_lower_bound:
                raise PlanningError(
                    f"accepted lower bound weakens structural evidence: {pair}"
                )
            accepted_upper_bound = upper_source.local_l_max
            if accepted_upper_bound < accepted_lower_bound:
                raise PlanningError(f"accepted bounds are inconsistent: {pair}")

            target_values = tuple(range(accepted_lower_bound, accepted_upper_bound))
            targets = tuple(
                Stage5TargetPlan(
                    target_order_within_instance=index,
                    target_r=target_r,
                )
                for index, target_r in enumerate(
                    target_values,
                    start=1,
                )
            )

            classification: InstanceClassification = (
                "exact_by_accepted_transfer"
                if accepted_lower_bound == accepted_upper_bound
                else "search_required"
            )
            instances.append(
                Stage5InstancePlan(
                    execution_order=len(instances) + 1,
                    graph_id=graph.graph_id,
                    graph_order=graph.graph_order,
                    vertex_count=graph.vertex_count,
                    edge_count=graph.edge_count,
                    minimum_code_length=graph.minimum_code_length,
                    code_length=code_length,
                    excess_bits=offset,
                    accepted_lower_bound=accepted_lower_bound,
                    accepted_upper_bound=accepted_upper_bound,
                    classification=classification,
                    accepted_upper_bound_source=upper_source,
                    stage3_initialisation=stage3_initialisation,
                    stage4_initialisation=stage4_initialisation,
                    random_initialisation_class="deterministic_random",
                    targets=targets,
                )
            )

    instance_tuple = tuple(instances)
    payload = _plan_payload_without_hash(
        graphs=graphs,
        direct_exact_pairs=direct_exact_pairs,
        instances=instance_tuple,
    )
    plan_sha256 = hashlib.sha256(
        canonical_json_dumps(payload).encode("utf-8")
    ).hexdigest()

    return Stage5Plan(
        schema_version=PLAN_SCHEMA_VERSION,
        stage2_run_id=STAGE2_RUN_ID,
        stage3_run_id=STAGE3_RUN_ID,
        stage4_run_id=STAGE4_RUN_ID,
        graph_order=GRAPH_ORDER,
        code_length_offsets=CODE_LENGTH_OFFSETS,
        graphs=graphs,
        direct_stage4_exact_pairs=direct_exact_pairs,
        instances=instance_tuple,
        global_grid_pair_count=int(payload["global_grid_pair_count"]),
        direct_stage4_exact_pair_count=int(payload["direct_stage4_exact_pair_count"]),
        candidate_instance_count=int(payload["candidate_instance_count"]),
        search_required_instance_count=int(payload["search_required_instance_count"]),
        exact_by_transfer_instance_count=int(
            payload["exact_by_transfer_instance_count"]
        ),
        unresolved_target_count=int(payload["unresolved_target_count"]),
        plan_sha256=plan_sha256,
    )

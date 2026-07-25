"""Deterministic CP-SAT execution and independent witness validation."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from enum import StrEnum
from numbers import Real

import numpy as np
from ortools.sat.python import cp_model

from sphere_encoding.exact.model import ExactFeasibilityModel


class ExactSolverStatus(StrEnum):
    """Frozen status vocabulary for Stage 4 exact solving."""

    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    MODEL_INVALID = "MODEL_INVALID"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class StatusInterpretation:
    """Evidential meaning of a raw CP-SAT status."""

    status: ExactSolverStatus
    raw_status_code: int
    raw_status_name: str
    has_feasible_witness: bool
    certifies_infeasibility: bool
    resolves_threshold: bool
    implementation_failure: bool


@dataclass(frozen=True)
class WitnessValidation:
    """Independent recomputation for a feasible codebook."""

    vertex_count: int
    edge_count: int
    code_length: int
    target_r: int
    unique_codeword_count: int
    maximum_edge_hamming_distance: int
    edge_hamming_histogram: tuple[int, ...]
    codebook_sha256: str


@dataclass(frozen=True)
class ExactSolveResult:
    """A raw exact-solver result plus independently checked evidence."""

    status: ExactSolverStatus
    raw_status_code: int
    raw_status_name: str
    model_sha256: str
    wall_time_seconds: float
    user_time_seconds: float
    conflict_count: int
    branch_count: int
    response_stats: str
    codebook: np.ndarray | None
    validation: WitnessValidation | None
    has_feasible_witness: bool
    certifies_infeasibility: bool
    resolves_threshold: bool
    implementation_failure: bool


def interpret_solver_status(status_code: int) -> StatusInterpretation:
    """Map an OR-Tools status code to the frozen Stage 4 semantics."""

    mapping = {
        int(cp_model.OPTIMAL): StatusInterpretation(
            status=ExactSolverStatus.OPTIMAL,
            raw_status_code=int(cp_model.OPTIMAL),
            raw_status_name="OPTIMAL",
            has_feasible_witness=True,
            certifies_infeasibility=False,
            resolves_threshold=True,
            implementation_failure=False,
        ),
        int(cp_model.FEASIBLE): StatusInterpretation(
            status=ExactSolverStatus.FEASIBLE,
            raw_status_code=int(cp_model.FEASIBLE),
            raw_status_name="FEASIBLE",
            has_feasible_witness=True,
            certifies_infeasibility=False,
            resolves_threshold=True,
            implementation_failure=False,
        ),
        int(cp_model.INFEASIBLE): StatusInterpretation(
            status=ExactSolverStatus.INFEASIBLE,
            raw_status_code=int(cp_model.INFEASIBLE),
            raw_status_name="INFEASIBLE",
            has_feasible_witness=False,
            certifies_infeasibility=True,
            resolves_threshold=True,
            implementation_failure=False,
        ),
        int(cp_model.MODEL_INVALID): StatusInterpretation(
            status=ExactSolverStatus.MODEL_INVALID,
            raw_status_code=int(cp_model.MODEL_INVALID),
            raw_status_name="MODEL_INVALID",
            has_feasible_witness=False,
            certifies_infeasibility=False,
            resolves_threshold=False,
            implementation_failure=True,
        ),
        int(cp_model.UNKNOWN): StatusInterpretation(
            status=ExactSolverStatus.UNKNOWN,
            raw_status_code=int(cp_model.UNKNOWN),
            raw_status_name="UNKNOWN",
            has_feasible_witness=False,
            certifies_infeasibility=False,
            resolves_threshold=False,
            implementation_failure=False,
        ),
    }

    try:
        return mapping[int(status_code)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"unrecognised OR-Tools status code: {status_code!r}"
        ) from exc


def _normalise_codebook(
    codebook: np.ndarray,
    *,
    vertex_count: int,
    code_length: int,
) -> np.ndarray:
    array = np.asarray(codebook)

    if array.shape != (vertex_count, code_length):
        raise ValueError(
            "codebook shape differs from the exact model dimensions"
        )
    if not (
        np.issubdtype(array.dtype, np.integer)
        or np.issubdtype(array.dtype, np.bool_)
    ):
        raise TypeError("codebook must use Boolean or integer dtype")

    binary = np.asarray(array, dtype=np.uint8)
    if np.any((binary != 0) & (binary != 1)):
        raise ValueError("codebook contains non-binary values")

    return np.ascontiguousarray(binary)


def _codebook_npy_sha256(codebook: np.ndarray) -> str:
    stream = io.BytesIO()
    np.save(stream, codebook, allow_pickle=False)
    return hashlib.sha256(stream.getvalue()).hexdigest()


def recompute_edge_hamming(
    codebook: np.ndarray,
    edges: np.ndarray,
) -> np.ndarray:
    """Independently recompute raw Hamming distance on every graph edge."""

    binary = np.asarray(codebook)
    edge_array = np.asarray(edges, dtype=np.int64)

    if edge_array.ndim != 2 or edge_array.shape[1] != 2:
        raise ValueError("edges must have shape (E, 2)")

    if len(edge_array) == 0:
        return np.empty(0, dtype=np.int64)

    return np.count_nonzero(
        binary[edge_array[:, 0]] != binary[edge_array[:, 1]],
        axis=1,
    ).astype(np.int64, copy=False)


def validate_exact_witness(
    codebook: np.ndarray,
    built: ExactFeasibilityModel,
) -> WitnessValidation:
    """Independently validate a feasible assignment from CP-SAT."""

    binary = _normalise_codebook(
        codebook,
        vertex_count=built.vertex_count,
        code_length=built.code_length,
    )

    packed = np.packbits(binary, axis=1, bitorder="little")
    unique_count = len({bytes(row) for row in packed})
    if unique_count != built.vertex_count:
        raise ValueError("codebook is not injective")

    distances = recompute_edge_hamming(binary, built.edges)
    maximum = int(np.max(distances)) if len(distances) else 0

    if maximum > built.target_r:
        raise ValueError(
            "codebook violates the exact model edge-Hamming target"
        )

    if built.symmetry_breaking:
        if np.any(binary[0] != 0):
            raise ValueError("codebook violates the anchor-code symmetry")

        if built.first_neighbour is not None:
            neighbour = binary[built.first_neighbour]
            integer_code = sum(
                int(value) << bit
                for bit, value in enumerate(neighbour.tolist())
            )
            allowed = {
                (1 << weight) - 1
                for weight in range(1, built.target_r + 1)
            }
            if integer_code not in allowed:
                raise ValueError(
                    "codebook violates the first-neighbour symmetry"
                )

    histogram = np.bincount(
        distances,
        minlength=built.code_length + 1,
    )
    if len(histogram) != built.code_length + 1:
        raise RuntimeError("edge-Hamming histogram has invalid length")
    if int(np.sum(histogram)) != len(built.edges):
        raise RuntimeError("edge-Hamming histogram does not sum to edges")

    immutable = binary.copy()
    immutable.setflags(write=False)

    return WitnessValidation(
        vertex_count=built.vertex_count,
        edge_count=len(built.edges),
        code_length=built.code_length,
        target_r=built.target_r,
        unique_codeword_count=unique_count,
        maximum_edge_hamming_distance=maximum,
        edge_hamming_histogram=tuple(
            int(value) for value in histogram.tolist()
        ),
        codebook_sha256=_codebook_npy_sha256(immutable),
    )


def _extract_codebook(
    solver: cp_model.CpSolver,
    built: ExactFeasibilityModel,
) -> np.ndarray:
    codebook = np.asarray(
        [
            [
                solver.Value(variable)
                for variable in vertex_variables
            ]
            for vertex_variables in built.bit_variables
        ],
        dtype=np.uint8,
    )
    codebook.setflags(write=False)
    return codebook


def _validate_solver_settings(
    *,
    max_time_seconds: Real,
    num_search_workers: int,
    random_seed: int,
    cp_model_presolve: bool,
    log_search_progress: bool,
) -> float:
    if isinstance(max_time_seconds, bool) or not isinstance(
        max_time_seconds,
        Real,
    ):
        raise TypeError("max_time_seconds must be a real number")

    time_limit = float(max_time_seconds)
    if not np.isfinite(time_limit) or time_limit < 0.0:
        raise ValueError(
            "max_time_seconds must be finite and non-negative"
        )
    if num_search_workers != 1:
        raise ValueError(
            "Stage 4 exact solving requires exactly one search worker"
        )
    if random_seed != 0:
        raise ValueError("Stage 4 exact solving requires random seed zero")
    if not isinstance(cp_model_presolve, bool):
        raise TypeError("cp_model_presolve must be Boolean")
    if not isinstance(log_search_progress, bool):
        raise TypeError("log_search_progress must be Boolean")

    return time_limit


def solve_exact_feasibility_model(
    built: ExactFeasibilityModel,
    *,
    max_time_seconds: Real,
    num_search_workers: int = 1,
    random_seed: int = 0,
    cp_model_presolve: bool = True,
    log_search_progress: bool = True,
) -> ExactSolveResult:
    """Solve one frozen threshold model and validate any witness."""

    time_limit = _validate_solver_settings(
        max_time_seconds=max_time_seconds,
        num_search_workers=num_search_workers,
        random_seed=random_seed,
        cp_model_presolve=cp_model_presolve,
        log_search_progress=log_search_progress,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = num_search_workers
    solver.parameters.random_seed = random_seed
    solver.parameters.cp_model_presolve = cp_model_presolve
    solver.parameters.log_search_progress = log_search_progress

    raw_status = solver.Solve(built.model)
    interpretation = interpret_solver_status(int(raw_status))

    solver_name = solver.StatusName(raw_status)
    if solver_name != interpretation.raw_status_name:
        raise RuntimeError(
            "OR-Tools status name differs from frozen interpretation"
        )

    codebook = None
    validation = None

    if interpretation.has_feasible_witness:
        codebook = _extract_codebook(solver, built)
        validation = validate_exact_witness(codebook, built)

    return ExactSolveResult(
        status=interpretation.status,
        raw_status_code=interpretation.raw_status_code,
        raw_status_name=solver_name,
        model_sha256=built.model_sha256,
        wall_time_seconds=float(solver.WallTime()),
        user_time_seconds=float(solver.UserTime()),
        conflict_count=int(solver.NumConflicts()),
        branch_count=int(solver.NumBranches()),
        response_stats=str(solver.ResponseStats()),
        codebook=codebook,
        validation=validation,
        has_feasible_witness=interpretation.has_feasible_witness,
        certifies_infeasibility=interpretation.certifies_infeasibility,
        resolves_threshold=interpretation.resolves_threshold,
        implementation_failure=interpretation.implementation_failure,
    )

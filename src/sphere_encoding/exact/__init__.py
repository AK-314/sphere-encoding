"""Exact unrestricted-codebook optimisation primitives."""

from sphere_encoding.exact.model import (
    ExactFeasibilityModel,
    StructuralLowerBound,
    build_exact_feasibility_model,
    canonicalise_hint_codes,
    deterministic_odd_cycle,
    model_proto_bytes,
    structural_lower_bound,
)
from sphere_encoding.exact.solver import (
    ExactSolveResult,
    ExactSolverStatus,
    StatusInterpretation,
    WitnessValidation,
    interpret_solver_status,
    recompute_edge_hamming,
    solve_exact_feasibility_model,
    validate_exact_witness,
)

__all__ = [
    "ExactFeasibilityModel",
    "ExactSolveResult",
    "ExactSolverStatus",
    "StatusInterpretation",
    "StructuralLowerBound",
    "WitnessValidation",
    "build_exact_feasibility_model",
    "canonicalise_hint_codes",
    "deterministic_odd_cycle",
    "interpret_solver_status",
    "model_proto_bytes",
    "recompute_edge_hamming",
    "solve_exact_feasibility_model",
    "structural_lower_bound",
    "validate_exact_witness",
]

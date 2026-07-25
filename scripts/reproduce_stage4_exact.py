"""Audit or independently re-solve definitive Stage 4 outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from sphere_encoding.config import pretty_json_dumps
from sphere_encoding.exact.plan import derive_stage4_plan
from sphere_encoding.exact.reproduce import (
    audit_stage4_package,
    reproduce_stage4_solver_results,
)
from sphere_encoding.exact.solver import solve_exact_feasibility_model
from sphere_encoding.provenance import capture_repository


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit or independently re-solve Stage 4 outputs."
    )
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/stage4_exact.json"),
    )
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="Repeat the long solver run after the structural audit.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    repository = arguments.repository.resolve()
    config = arguments.config
    if not config.is_absolute():
        config = repository / config
    package = arguments.package
    if not package.is_absolute():
        package = repository / package

    plan = derive_stage4_plan(repository, config_path=config)
    output = {
        "artifact_audit": audit_stage4_package(
            repository,
            plan=plan,
            package_root=package,
        )
    }
    if arguments.resolve:
        provenance = capture_repository(repository)
        if provenance["clean"] is not True:
            raise SystemExit("reproduction worktree must be clean")
        if provenance["branch"] != "":
            raise SystemExit(
                "full reproduction must run in a detached worktree"
            )
        output["solver_reproduction"] = reproduce_stage4_solver_results(
            repository,
            plan=plan,
            package_root=package,
            solve_function=solve_exact_feasibility_model,
        )

    print(pretty_json_dumps(output), end="")


if __name__ == "__main__":
    main()

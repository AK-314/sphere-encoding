"""Generate the definitive Stage 4 exact free-codebook outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sphere_encoding.config import pretty_json_dumps
from sphere_encoding.exact.run import execute_instance_plan
from sphere_encoding.stage4 import install_definitive_stage4_artifacts


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run and install the definitive Stage 4 exact free-codebook "
            "optimisation outputs."
        )
    )
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
        help="Repository root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/stage4_exact.json"),
        help="Frozen Stage 4 configuration path.",
    )
    parser.add_argument(
        "--confirm-definitive",
        action="store_true",
        help=(
            "Confirm execution of the frozen long-running scientific run. "
            "Without this flag no solver is invoked."
        ),
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    if not arguments.confirm_definitive:
        raise SystemExit(
            "Refusing to start definitive Stage 4 without "
            "--confirm-definitive"
        )

    def execute_with_progress(repository, **kwargs):
        instance = kwargs["instance"]
        print(
            "starting Stage 4 instance "
            f"{instance.execution_order:02d}/21: "
            f"{instance.graph_id}, m={instance.code_length}",
            file=sys.stderr,
            flush=True,
        )
        result = execute_instance_plan(repository, **kwargs)
        print(
            "completed Stage 4 instance "
            f"{instance.execution_order:02d}/21: "
            f"classification={result.classification.value}, "
            f"bounds=[{result.final_lower_bound},"
            f"{result.final_upper_bound}]",
            file=sys.stderr,
            flush=True,
        )
        return result

    result = install_definitive_stage4_artifacts(
        repository_path=arguments.repository,
        config_path=arguments.config,
        execute_function=execute_with_progress,
    )
    print(pretty_json_dumps(result), end="")


if __name__ == "__main__":
    main()

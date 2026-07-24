"""Generate the definitive Stage 2 canonical sphere-graph package."""

from __future__ import annotations

import argparse
from pathlib import Path

from sphere_encoding.config import pretty_json_dumps
from sphere_encoding.stage2 import (
    install_definitive_stage2_artifacts,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and install the definitive Stage 2 canonical "
            "sphere-graph package."
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
        default=Path("configs/stage2_graph_suite.json"),
        help="Stage 2 graph-suite configuration path.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    result = install_definitive_stage2_artifacts(
        repository_path=arguments.repository,
        config_path=arguments.config,
    )
    print(pretty_json_dumps(result), end="")


if __name__ == "__main__":
    main()

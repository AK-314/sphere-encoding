"""Generate the definitive Stage 4 exact free-codebook outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from sphere_encoding.config import pretty_json_dumps
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
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    result = install_definitive_stage4_artifacts(
        repository_path=arguments.repository,
        config_path=arguments.config,
    )
    print(pretty_json_dumps(result), end="")


if __name__ == "__main__":
    main()

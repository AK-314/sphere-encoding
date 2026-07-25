"""Run the non-solving definitive Stage 4 preflight audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from sphere_encoding.config import pretty_json_dumps
from sphere_encoding.stage4 import preflight_definitive_stage4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/stage4_exact.json"),
    )
    arguments = parser.parse_args()
    result = preflight_definitive_stage4(
        repository_path=arguments.repository,
        config_path=arguments.config,
    )
    print(pretty_json_dumps(result), end="")


if __name__ == "__main__":
    main()

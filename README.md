# Sphere Encoding

This repository studies reproducible binary encodings of finite point sets on
unit spheres.

The authoritative project begins with a protocol-first workflow. Material
created before the protocol is preserved under
`exploratory/pre_protocol_2026-07/` and is scientifically non-definitive.

## Current status

Stage 1 establishes repository, protocol, configuration, hashing, provenance,
testing, and environment foundations.

No definitive sphere graph has been generated, no encoding instance has been
solved, and no definitive encoder has been trained.

## Environment

The project uses Python 3.11 and `uv`.

Primary validation commands:

    uv sync --dev
    uv run pytest
    uv run ruff check .
    git diff --check

A malformed shell `PATH` was observed during the initial audit. Commands require
normal system executable directories, including `/usr/bin`, `/bin`,
`/usr/sbin`, and `/sbin`, together with the directory containing `uv`.

## Repository layout

- `src/sphere_encoding/`: reusable project infrastructure
- `tests/`: unit tests
- `manifests/`: definitive run manifests
- `results/`: definitive tables, figures, raw outputs, and archives
- `scripts/`: controlled project entry points
- `exploratory/`: excluded pre-protocol work

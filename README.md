# Sphere Encoding

This repository studies reproducible binary encodings of finite point sets on
unit spheres.

The authoritative project begins with a protocol-first workflow. Material
created before the protocol is preserved under
`exploratory/pre_protocol_2026-07/` and is scientifically non-definitive.

## Current status

Stage 1 established the repository, protocol, deterministic configuration,
hashing, provenance, test, and archive infrastructure.

Stage 2, Canonical Sphere Graphs, is complete. The definitive suite contains
four icosphere triangulation graphs and nine primitive integer-direction
graphs, for 13 canonical graph instances in total.

The definitive Stage 2 run is:

`stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50`

Its 81-file deterministic package, 81-member archive, and manifest were
independently reproduced byte-for-byte and committed at
`23a5669125e0bfb71e71330bde6bcf9d7ae25723`.

Stage 3 has not started. No definitive encoding metrics, baseline encoders,
optimisation results, solver bounds, or neural-encoder results exist yet.

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

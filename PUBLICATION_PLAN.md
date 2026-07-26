# GitHub Publication Plan

## Proposed repository

- Name: `sphere-encoding`
- Description: Exact and scalable search for binary encodings of discretised unit-sphere vectors with low worst-case local Hamming sensitivity.
- Topics: `gray-code`, `sphere`, `binary-embedding`, `hamming-distance`, `graph-embedding`, `combinatorial-optimisation`, `cp-sat`, `coding-theory`
- Proposed licence: MIT

No remote repository has been created and nothing has been pushed. Publication requires explicit user approval.

## Publish

- `.gitignore`
- `.python-version`
- `README.md`
- `LICENSE`
- `CITATION.cff`
- `pyproject.toml`
- `uv.lock`
- `experimental_protocol.md`
- `implementation_order.md`
- `PROJECT_STATE.md`
- `configs/`
- `manifests/`
- `src/sphere_encoding/`
- `tests/`
- the existing Stage 2-4 generation and audit scripts
- `scripts/reproduce_report_figures.py`
- `scripts/reproduce_report_tables.py`
- `scripts/verify_report_results.py`
- `scripts/build_interim_report.py`
- `report/Sphere_Encoding_Interim_Report.md`
- `report/Sphere_Encoding_Interim_Report.docx`
- `report/Sphere_Encoding_Interim_Report.pdf`
- `report/Executive_Summary.md`
- `report/REPORT_REPRODUCTION.md`
- `results/figures/report/`
- `results/tables/report/`
- accepted Stage 2-4 summary tables, manifests, graph arrays, and deterministic archives required by the lightweight verifier

## Intentionally exclude

- `.DS_Store`
- `.venv/`, `.pytest_cache/`, `.ruff_cache/`, and `__pycache__/`
- machine-specific editor state and temporary render directories
- local absolute paths or shell histories
- ad hoc calibration outputs not accepted as scientific results
- duplicated extracted Stage 4 solver logs and model files when the deterministic archive already preserves them
- exploratory pre-protocol outputs from the public scientific narrative (retain privately for provenance if desired)
- any future Stage 5 pilot artifacts that have not passed the scientific acceptance gate

Before publication, review repository size and GitHub file-size limits for the accepted archives. If an archive is unsuitable for ordinary Git storage, publish it as a versioned release asset and preserve its manifest SHA-256 in the repository.


# Report Reproduction

This guide regenerates and checks the interim report package without altering accepted Stage 2-4 scientific outputs.

## Environment

- Python: 3.11.15 (the repository's `.python-version`)
- Dependency manager: `uv`
- Stage 4 solver recorded in the accepted manifest: OR-Tools 9.15.6755
- Report-only figure dependency: Pillow
- DOCX/PDF build dependency: `python-docx`, LibreOffice, and Poppler

From the repository root:

```bash
uv sync --frozen
```

The accepted Stage 2-4 computations predate the report branch. Their manifests and immutable archives remain the scientific authority.

## Accepted identities

| Stage | Run identifier | Accepted commit role |
|---|---|---|
| Stage 2 | `stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50` | canonical graph package |
| Stage 3 | `stage3-deterministic-baselines-3fad68b97de9-f07ae893574e` | deterministic baseline package |
| Stage 4 | `stage4-exact-free-codebook-97021c6cac03-7adb5b49f2cb` | exact free-codebook package |

Stage 4 implementation commit: `7adb5b49f2cb010d01feef1e693f5e6f9ce31975`  
Stage 4 output commit: `ddf6dd0d85a8ae818e3d5a858ce4b6ee5445d268`  
Report branch base: `984a8efe5f5aa36740a864b311b5bd7f3938e647`

## Verify accepted hashes and witnesses

The lightweight verifier checks the Stage 2-4 archive SHA-256 values and member counts against their manifests, checks the Stage 4 classification totals and headline Stage 3 row, then independently reloads and validates all 36 archived Stage 4 codebooks:

```bash
uv run python scripts/verify_report_results.py
```

This recomputes injectivity and every saved witness's edge Hamming distances. It does **not** rerun the complete Stage 4 CP-SAT workload.

The repository's deeper Stage 4 structural audit can be run after extracting the deterministic archive to a temporary directory:

```bash
mkdir -p /tmp/sphere-stage4-audit
tar -xzf results/archives/stage4-exact-free-codebook-97021c6cac03-7adb5b49f2cb.tar.gz -C /tmp/sphere-stage4-audit
uv run python scripts/reproduce_stage4_exact.py \
  --package /tmp/sphere-stage4-audit/raw/stage4-exact-free-codebook-97021c6cac03-7adb5b49f2cb
```

Do not add `--resolve` unless deliberately scheduling the long independent solver reproduction in a clean detached worktree. The complete workload was not rerun for this report.

## Regenerate tables

```bash
uv run python scripts/reproduce_report_tables.py
```

Outputs are written to `results/tables/report/`. They are derived from committed Stage 2 graph summaries, Stage 3 baseline tables, Stage 4 bounds, and the deterministic Stage 5 planning object.

## Regenerate figures

Pillow is report-only and can be supplied ephemerally:

```bash
uv run --with pillow python scripts/reproduce_report_figures.py
```

Outputs are written to `results/figures/report/`. Figures 2 and 8 use committed NumPy graph arrays; Figure 8 reads its accepted witness from the committed Stage 4 archive.

## Rebuild Word and PDF

```bash
uv run --with python-docx --with pillow python scripts/build_interim_report.py
```

The builder reads the Markdown report, report CSV tables, and PNG figures, then writes `report/Sphere_Encoding_Interim_Report.docx`. Render it with LibreOffice and inspect every page before distribution:

```bash
python /path/to/documents-skill/render_docx.py \
  report/Sphere_Encoding_Interim_Report.docx \
  --output_dir /tmp/sphere-report-render \
  --emit_pdf
```

Copy the rendered PDF to `report/Sphere_Encoding_Interim_Report.pdf` only after visual review.

## Long-computation boundary

Regenerating tables, figures, the DOCX, and the PDF is lightweight. Verifying archived witnesses is also lightweight. The original Stage 4 target-solving workload had an accepted total budget of 81,600 seconds and is intentionally not part of ordinary report reproduction. Stage 5 definitive computation has not yet been run or reported.


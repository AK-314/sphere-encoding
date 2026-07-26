# Sphere Encoding

Exact and scalable search for binary encodings of discretised unit-sphere vectors with low worst-case local Hamming sensitivity.

## Research question

Can a finite sphere discretisation be assigned unique (m)-bit words whose worst local Hamming transition is smaller than a Cartesian product of Gray codes at the same code length?

For graph (G=(V,\mathcal E)), the unrestricted benchmark is

\[
L^*_{\mathrm{free}}(G,m)=
\min_{E:V\to\{0,1\}^m,\ E\text{ injective}}
\max_{(u,v)\in\mathcal E}d_H(E(u),E(v)).
\]

## Headline result

On the accepted 98-vertex `primitive_q2_knn4` graph at nine bits:

- Cartesian-coordinate Gray: (L_{\max}=3)
- exact unrestricted optimum: (L^*_{\mathrm{free}}=2)

This is a strict same-rate improvement. It proves that Cartesian-coordinate Gray is not locally optimal on this frozen instance. It does not provide a universal or circuit-efficient sphere encoder.

![Same-rate comparison](results/figures/report/figure5_same_rate_comparison.png)

## What is included

- deterministic full-sphere graph construction for icospheres and primitive integer directions;
- canonical-index and Cartesian binary/Gray baselines;
- exact CP-SAT threshold models with independent witness verification;
- accepted Stage 2-4 manifests, tables, and deterministic archives;
- deterministic Stage 5 free-codebook search infrastructure;
- an interim technical report in Markdown, Word, and PDF;
- reproducible report figures, tables, and claim checks.

Nine Stage 4 instances have exact optimum two. The complete 42-vertex `icosphere_l1` graph attains two at six bits, its minimum injective length. Twelve larger Stage 4 instances retain explicit lower-upper intervals.

## Reports

- [Interim report (PDF)](report/Sphere_Encoding_Interim_Report.pdf)
- [Interim report (Markdown)](report/Sphere_Encoding_Interim_Report.md)
- [Executive summary](report/Executive_Summary.md)
- [Reproduction guide](report/REPORT_REPRODUCTION.md)

## Reproduction

```bash
uv sync --frozen
uv run python scripts/verify_report_results.py
uv run python scripts/reproduce_report_tables.py
uv run --with pillow python scripts/reproduce_report_figures.py
```

See the [full reproduction guide](report/REPORT_REPRODUCTION.md) for the DOCX/PDF build and the boundary between lightweight witness verification and long solver reproduction.

## Repository map

- `src/sphere_encoding/`: graph, encoding, metric, exact, and heuristic implementation
- `configs/`: frozen Stage 2-4 configurations
- `manifests/`: accepted package identities and hashes
- `results/tables/`: accepted and report-facing tables
- `results/figures/report/`: report figures
- `results/archives/`: deterministic accepted archives
- `scripts/`: generation, verification, and report reproduction entry points
- `report/`: report, executive summary, and reproduction guide

## Current Stage 5 status

The deterministic scalable-search implementation includes injective states, incremental threshold scoring, swap and replacement moves, deterministic schedules, checkpoint/resume, replay verification, and artifact packaging. The definitive Stage 5 configuration, budgets, seeds, workload, scientific audit, and reproduction remain pending. Control pilots are engineering calibration and are not interpreted as mathematical infeasibility.

## Limitations

- finite discretisations and frozen neighbour graphs only;
- unrestricted codebooks are lookup tables, not explicit encoders for unseen inputs;
- no asymptotic theorem or continuous-sphere result;
- no circuit-complexity result;
- global angular-Hamming distortion is diagnostic, not the Stage 4 objective;
- twelve Stage 4 instances are bounded rather than exact;
- no second full Stage 4 solver workload was run for the report.

## Licence and citation

Code is proposed for release under the MIT License. Citation metadata is provided in `CITATION.cff`. Review both before first public publication.

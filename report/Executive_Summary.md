# Executive Summary

## Beyond Cartesian Gray Codes

The project asks whether finite samples of the unit sphere can be assigned unique binary words with fewer worst-case bit changes between neighbouring directions than a matched Cartesian product of Gray codes.

The answer is **yes on at least one fixed, same-rate instance**.

For the accepted `primitive_q2_knn4` graph:

| Quantity | Result |
|---|---:|
| Sphere directions | 98 |
| Local-neighbour edges | 264 |
| Code length | 9 bits |
| Cartesian-coordinate Gray (L_{\max}) | 3 |
| Exact unrestricted optimum (L^*_{\mathrm{free}}) | 2 |

Both assignments are injective and use the same nine-bit rate. Exact optimisation therefore establishes

\[
L^*_{\mathrm{free}}=2<3=L_{\max,\mathrm{Cartesian\ Gray}}.
\]

This proves that Cartesian-coordinate Gray coding is not locally optimal on this frozen sphere discretisation. It does not establish a universal spherical Gray code or an efficient formula for unseen directions.

![Headline comparison](../results/figures/report/figure5_same_rate_comparison.png)

## What was optimised

Each sphere discretisation is represented by a complete undirected neighbour graph. Every vertex receives a distinct (m)-bit word. The primary score is the largest Hamming distance across any graph edge:

\[
L_{\max}=\max_{(u,v)\in\mathcal E}d_H(E(u),E(v)).
\]

Stage 4 used deterministic CP-SAT threshold-feasibility models with exact injectivity constraints and independently checked codebook witnesses. Across 21 graph-length instances, it established nine exact optima and twelve rigorous intervals. All nine exact optima equal two.

The complete 42-vertex `icosphere_l1` graph is an especially strong small result. It attains (L^*_{\mathrm{free}}=2) at six bits, the minimum length capable of assigning 42 distinct words. All 120 triangulation edges on the closed sphere were included; no chart seam or wrap-around boundary was omitted.

## How to interpret the result

The unrestricted codebooks answer an existence question: *what local smoothness is combinatorially possible?* They may require a lookup table of size proportional to the number of points times the number of bits. They do not yet answer whether the same advantage can be achieved with a compact circuit, a closed-form geometry-aware rule, or an encoder that generalises to arbitrary continuous sphere vectors.

This distinction sets the research direction. The exact results provide targets for scalable search and for later explicit encoder classes.

## Current Stage 5 status

The deterministic scalable-search foundation is substantially implemented: injective search states, incremental scoring, swap and unused-word replacement moves, deterministic initialisation and temperature schedules, checkpoint/resume, independent replay verification, and deterministic artifact packaging.

The frozen planning layer contains 52 graph-length pairs. Nine direct Stage 4 exact pairs are excluded; 43 remain as Stage 5 candidates, 42 require search, and one is exact by zero-padding transfer. The definitive search configuration, budgets, seeds, workload, audit, and reproduction are still pending. Short control pilots are engineering calibration only and are not scientific negative results.

## Bottom line

The finite exact evidence establishes that coordinate-wise Gray coding can be improved at the same rate when the codebook is allowed to follow sphere geometry. The remaining problem is constructive: retain that advantage in a simple, scalable, and efficiently computable sphere encoder.


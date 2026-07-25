# Experimental Protocol

## 1. Status and scope

This document is the authoritative scientific protocol for the
sphere-encoding project.

It governs all definitive computation beginning with Stage 2. Work preserved
under `exploratory/pre_protocol_2026-07/` predates this protocol and is excluded
from definitive analysis.

The project studies binary encodings of finite point sets on unit spheres,
with particular emphasis on whether geometrically nearby points can be assigned
codes that differ in few bits while retaining injectivity and acceptable global
geometric behaviour.

Stage 1 creates infrastructure only. It does not generate a definitive graph,
solve an encoding instance, train an encoder, or establish a scientific result.

## 2. Formal notation

Let:

- \(X = \{x_1,\ldots,x_N\}\) be a finite set of distinct points on the unit
  sphere \(S^{d-1}\);
- \(G=(X,\mathcal{E})\) be an undirected geometric-neighbour graph;
- \(m\) be the binary code length;
- \(C:X\rightarrow\{0,1\}^{m}\) be an encoding;
- \(d_H\) be unnormalised Hamming distance;
- \(d_\angle(x_i,x_j)=\arccos(\langle x_i,x_j\rangle)/\pi\) be normalised
  angular distance in \([0,1]\).

The primary quality measure is:

\[
L_{\max}(C)
=
\max_{(u,v)\in\mathcal{E}}
d_H(C(u),C(v)).
\]

Unless otherwise stated, local metrics are computed over the full undirected
edge set \(\mathcal{E}\), with every edge counted once.

A definitive encoding is valid only when it is injective on the evaluated
finite point set:

\[
u\neq v \Longrightarrow C(u)\neq C(v).
\]

## 3. Scientific questions

The project asks:

1. What local Hamming smoothness is achievable at a given point-set size,
   graph, code length, and encoding class?
2. How much additional code length is required to improve worst-case local
   smoothness?
3. What trade-off exists between local smoothness and preservation of global
   angular geometry?
4. How much performance is lost when moving from arbitrary codebooks to
   explicit, compact, or circuit-efficient encoders?
5. Which conclusions remain stable across graph resolutions, neighbourhood
   definitions, random seeds, and related sphere domains?

## 4. Domain families

### 4.1 Primary domain family

The primary domain family is the family of triangulation graphs obtained from
icosphere subdivisions of \(S^2\).

Each definitive icosphere instance must record:

- subdivision level;
- point count;
- face count;
- edge count;
- vertex coordinates;
- construction implementation and version;
- deterministic canonical ordering;
- duplicate and norm checks;
- graph-connectivity checks;
- hashes of all saved arrays and metadata.

No primary resolution may be selected because it produces favourable encoding
results.

### 4.2 Secondary domain family

The secondary family consists of primitive integer-direction point sets on
\(S^2\).

For a coordinate bound \(q\), nonzero primitive integer vectors in
\([-q,q]^3\) are normalised to the sphere. Opposite directions remain distinct.

These point sets must be evaluated across a prespecified neighbourhood grid.
The already explored \(q=3,\ k=6\) case is not privileged and cannot be selected
as the sole secondary graph because of its preliminary results.

The neighbourhood grid and included \(q\) values must be frozen in Stage 2
before definitive encoding optimisation begins.

#### Stage 2 prospective graph-suite resolution

Before any definitive Stage 2 graph was generated, the secondary graph suite
was frozen prospectively as:

- coordinate bounds \(q\in\{2,3,4\}\);
- nominal neighbour counts \(k\in\{4,6,8\}\);
- oriented primitive integer vectors, with antipodal vectors retained as
  distinct points;
- tie-complete symmetric angular nearest-neighbour construction;
- deterministic lexicographic integer-vector ordering.

For each vertex, the nominal \(k\)-th angular-distance threshold includes every
point tied within an absolute angular tolerance of \(10^{-12}\) radians. The
undirected graph is then the union of all directed selections. This rule is
prospective and must not be replaced by exact-\(k\) truncation to reproduce an
exploratory edge count.

The complete Stage 2 configuration, expected graph counts, serialization rules,
archive rules, and numerical tolerances are frozen in
`configs/stage2_graph_suite.json`. No encoding outcome had been generated or
inspected when this resolution was recorded.

### 4.3 Optional higher-dimensional family

Experiments on \(S^3\) are optional and remain pending. They may proceed only
after a prospective compute and implementation review. Their inclusion cannot
depend on favourable \(S^2\) outcomes.

## 5. Graph-construction principles

Every graph-construction method must be deterministic from its declared inputs.

For every definitive graph:

- vertices must correspond one-to-one with the saved point set;
- self-loops are forbidden;
- duplicate undirected edges are forbidden;
- graph ordering must be canonical;
- graph connectivity must be checked and reported;
- degree statistics must be reported;
- angular edge-length statistics must be reported;
- point norms must be numerically verified;
- duplicate or near-duplicate points must be detected under a declared
  tolerance;
- all construction parameters must appear in a manifest.

The primary icosphere graph uses triangulation adjacency, not a retrospectively
selected nearest-neighbour value.

Secondary integer-direction graphs may use prespecified symmetric
nearest-neighbour or radius-based constructions. Ties must be resolved
deterministically and documented.

Graph variants are separate experimental conditions. Results from multiple
graph variants must not be pooled as though they came from one graph.

## 6. Code-length candidates

For a point set of size \(N\), define:

\[
m_0=\lceil\log_2 N\rceil.
\]

The candidate code-length grid is frozen as:

\[
m\in\{m_0,\ m_0+1,\ m_0+2,\ m_0+4\}.
\]

A later prospective compute-projection decision may omit some candidates on the
largest graph instances. Such an omission must be decided from implementation
or compute evidence before seeing scientific outcomes at those candidates.

In particular, whether \(m_0+4\) is run at the largest resolution is pending.

No code length may be added, removed, or highlighted because it gives a
favourable result.

## 7. Encoding classes

The definitive programme compares the following classes.

### 7.1 Unrestricted injective codebooks

An unrestricted codebook directly assigns one distinct \(m\)-bit word to each
point in the evaluated finite set.

This class provides a combinatorial benchmark. It is not an explicit encoder
for unseen points and must not be described as one.

### 7.2 Cartesian binary and Gray encodings

Coordinates are quantised according to a fully specified deterministic rule,
encoded independently, and concatenated.

Binary and binary-reflected Gray variants must use matched quantisation,
coordinate ordering, bit allocation, and total code length wherever a fair
comparison is claimed.

### 7.3 Random threshold encoders

Bits are generated by random hyperplane or threshold rules with frozen sampling
distributions and seeds.

Reported results must distinguish:

- a single prespecified random draw;
- a distribution over random draws;
- the best of several draws.

Best-of-many random selection must include its selection budget.

### 7.4 Optimised linear and affine threshold encoders

Each bit has the form:

\[
C_j(x)=\mathbf{1}[w_j^\top x+b_j\geq 0].
\]

The linear subclass has \(b_j=0\). Optimisation method, initialisation, budget,
constraint handling, and stopping rule must be frozen prospectively.

### 7.5 Compact neural encoders

A neural encoder maps coordinates to \(m\) binary outputs through a compact
declared architecture.

A network evaluated only on the finite points used for training may merely
memorise the codebook. Therefore:

- training-set performance alone is not evidence of geometric generalisation;
- parameter count and architecture must be reported;
- discretisation of logits must be specified;
- injectivity must be checked after discretisation;
- robustness and held-out or perturbed-point behaviour belong to Stage 11.

The final compact architecture subset remains pending.

### 7.6 Explicit geometry-aware constructions

These are deterministic constructions motivated by sphere geometry, charts,
hierarchies, partitions, polyhedral structure, spherical coordinates, or other
explicit mathematical rules.

An explicit construction must specify how to encode a valid input without
storing an arbitrary lookup table containing one code per evaluated point.

### 7.7 Post hoc codebook compression

Any attempt to compress an optimised arbitrary codebook into a circuit, formula,
decision tree, or compact model must be reported separately from the original
codebook result.

Approximate reproduction of a codebook does not inherit the original
codebook's metric values unless those values are recomputed on the compressed
encoder's actual outputs.

## 8. Mandatory validity requirements

Every definitive encoding must satisfy all applicable validity checks.

### 8.1 Injectivity

Collision count must be zero on the evaluated finite point set.

An encoding with one or more collisions is invalid for primary comparison,
regardless of its local Hamming score.

Collision count must still be reported for diagnostics.

### 8.2 Binary outputs

Every evaluated code must contain exactly \(m\) binary values.

Continuous logits, relaxed bits, or probabilities are not codes until a
declared deterministic discretisation rule has been applied.

### 8.3 Point-set identity

Metrics may be compared only when encodings are evaluated on exactly the same
saved point set and graph, verified through identifiers or hashes.

### 8.4 Reproducible ordering

The point ordering, edge ordering, bit ordering, and codeword ordering must be
deterministic and recorded.

## 9. Primary and secondary local metrics

The primary metric is \(L_{\max}\).

The following local metrics are mandatory for every valid definitive encoding:

- \(L_{\max}\);
- number of graph edges attaining \(L_{\max}\);
- 99th percentile of local Hamming distance;
- 95th percentile of local Hamming distance;
- mean local Hamming distance;
- full local-distance distribution.

Percentile interpolation and implementation must be fixed centrally before
definitive metric tables are produced.

Where useful, normalised Hamming distance \(d_H/m\) may be reported as a
secondary presentation metric, but it does not replace the unnormalised primary
metric.

## 10. Global-distortion diagnostics

Local smoothness alone can produce misleading encodings. The following global
diagnostics are mandatory:

- Spearman correlation between angular and Hamming distances;
- mean absolute global distortion;
- maximum global distortion;
- far-pair behaviour;
- antipodal or near-antipodal behaviour;
- collision count;
- per-bit balance;
- bit redundancy.

The default normalised global Hamming distance is \(d_H/m\).

The exact global-distortion target, pair sampling rule for instances too large
for all-pairs evaluation, far-pair threshold, antipodal tolerance, and bit
redundancy statistic must be frozen before the relevant definitive analysis.

Global metrics are diagnostics and Pareto objectives. They do not override the
primary local metric unless a later protocol amendment explicitly creates a
different prespecified composite endpoint.

## 11. Exact and heuristic interpretation

Evidence must be described according to what the method actually proves.

- A valid feasible code proves an upper bound on the optimum \(L_{\max}\).
- Solver-certified infeasibility at threshold \(L\) proves that the optimum is
  greater than \(L\), subject to the exact model and validated solver.
- A solver-certified optimum proves matching upper and lower bounds.
- A timeout proves neither feasibility nor infeasibility beyond any incumbent
  solution already found.
- Heuristic failure proves neither a lower bound nor impossibility.
- Repeated heuristic success strengthens empirical confidence in feasibility
  but does not become a proof of optimality.
- A solver result is exact only when its status, model, inputs, version, and
  certificate or independently checkable evidence are preserved.
- Numerical tolerances must be reported where they can affect feasibility.

The exact solver, solver version, exact time budget, and largest exact instance
remain pending.

## 12. Circuit-efficiency interpretation

Circuit efficiency is conceptually separate from codebook quality.

For explicit encoders, the project may report:

- parameter count;
- arithmetic operation count;
- Boolean gate count or an explicitly stated proxy;
- circuit depth;
- evaluation time;
- memory use;
- description length;
- training or fitting cost.

No single efficiency proxy may be called circuit complexity without a precise
model of computation.

An unrestricted codebook may require lookup storage proportional to \(Nm\).
Its strong local score, if any, does not establish a compact computable
encoding.

Neural-network parameter count is not automatically equivalent to Boolean gate
count. Any conversion must state assumptions about numerical precision,
activation implementation, and thresholding.

## 13. Rate-smoothness and Pareto interpretation

The rate-smoothness analysis compares code length against attainable local
smoothness on fixed graph instances.

The local-global Pareto analysis compares local metrics with global-distortion
diagnostics.

A method dominates another only when validity conditions are matched and it is
no worse on every declared objective while being strictly better on at least
one.

Results at different point sets, graphs, code lengths, or validity conditions
must not be described as direct domination without qualification.

## 14. Negative-result rules

Negative findings are valid scientific outputs when their evidential limits are
stated correctly.

Required rules:

- heuristic non-discovery is reported as non-discovery, not impossibility;
- timeout is reported as timeout, not infeasibility;
- invalid colliding solutions do not establish feasible bounds;
- a failed neural training run is not evidence that the architecture class
  cannot succeed;
- failure on one graph does not generalise automatically to another graph;
- absence of improvement over a baseline must include the search budget,
  number of seeds, and best valid incumbent;
- empty feasible families or missing outputs must be reported explicitly;
- post hoc exclusions of inconvenient runs are forbidden;
- runs affected by implementation defects must be retained in an error log but
  excluded from scientific aggregation under a documented rule.

Null or adverse results must not trigger unplanned changes to graphs, code
lengths, metrics, or budgets without a protocol amendment.

## 15. Reproduction requirements

Every definitive run must preserve enough information to reconstruct and audit
the result.

At minimum, record:

- stage and run identifier;
- repository commit;
- clean-working-tree status;
- configuration and configuration hash;
- input file hashes;
- output file hashes;
- random seeds;
- Python version and executable;
- operating-system and machine information;
- relevant package and solver versions;
- start and end timestamps in UTC;
- command or controlled entry point;
- stopping reason;
- runtime;
- validity checks;
- errors or warnings;
- exact versus heuristic status.

Deterministic outputs must be reproducible byte-for-byte where practical.

When byte identity is not practical, the project must define invariant
reproduction checks before relying on the output.

Archives must contain a manifest and must not silently omit loose outputs used
in the scientific analysis.

## 16. Frozen decisions

The following decisions are frozen as of Stage 1.

### 16.1 Primary metric

\[
L_{\max}(C)
=
\max_{(u,v)\in\mathcal{E}}
d_H(C(u),C(v)).
\]

### 16.2 Mandatory validity

Every definitive encoding must be injective on the evaluated finite point set.

### 16.3 Primary graph family

Icosphere triangulation graphs.

### 16.4 Secondary graph family

Primitive integer-direction sphere sets evaluated across a prespecified
neighbourhood grid, rather than selecting only the previously explored
\(q=3,\ k=6\) condition.

### 16.5 Code-length candidates

\[
m=\lceil\log_2N\rceil+\{0,1,2,4\}.
\]

A prospective compute decision may reduce the candidates run on the largest
graphs, but scientific outcomes may not influence that decision.

### 16.6 Local metrics

- \(L_{\max}\);
- number of edges attaining \(L_{\max}\);
- 99th percentile;
- 95th percentile;
- mean local Hamming distance;
- full local-distance distribution.

### 16.7 Global diagnostics

- Spearman angular-Hamming correlation;
- mean absolute global distortion;
- maximum global distortion;
- far-pair and antipodal behaviour;
- collision count;
- bit balance and redundancy.

### 16.8 Evidential interpretation

- feasible code implies an upper bound;
- solver-certified infeasibility implies a lower bound;
- timeout implies neither;
- heuristic failure implies neither;
- arbitrary codebooks are not explicit encoders;
- training-point neural performance may be memorisation.

## 17. Pending decisions and resolution points

The following decisions remain pending and must be resolved prospectively.

| Decision | Required basis | Resolution deadline |
|---|---|---|
| Exact solver and frozen version | Model support, reproducibility, licence, certificate/status reliability, benchmark implementation evidence | Before Stage 4 definitive solving |
| Exact-solver time budget | Prospective runtime scaling and available compute | Before Stage 4 definitive solving |
| Largest exact instance | Prospective benchmark scaling, not observed scientific favourability | Before Stage 4 definitive solving |
| Large-instance heuristic budget | Prospective runtime and convergence diagnostics | Before Stage 5 definitive search |
| Final compact neural architecture subset | Implementation feasibility, parameter budget, and pilot stability without selecting on final scientific outcomes | Before Stage 9 definitive training |
| Whether \(S^3\) experiments proceed | Prospective scientific value and compute projection | Before Stage 11 robustness work |
| Whether \(m_0+4\) runs at the largest resolution | Prospective memory and runtime projection | Before the largest Stage 6 run |

Each resolution must be committed in the protocol, project state, or a
versioned amendment before affected definitive outcomes are inspected.

## 18. Amendment rules

A protocol amendment must:

1. identify the original rule;
2. state the proposed change;
3. explain why the change is necessary;
4. identify the evidence used to make the decision;
5. state whether any affected scientific outcomes had already been inspected;
6. specify which runs are affected;
7. preserve the previous protocol in Git history;
8. be committed before new affected definitive runs begin.

A change made after observing relevant scientific outcomes is post hoc and must
be labelled as such.

Post hoc exploratory analyses may be scientifically useful, but they must be
separated from confirmatory or protocol-governed analyses.

Silent amendments are forbidden.

## 19. Exploratory-work exclusion

All material under `exploratory/pre_protocol_2026-07/` is preserved for
provenance only.

It may be used to understand implementation history, formulate hypotheses, or
identify possible failure modes. It may not:

- count as a definitive run;
- determine the primary graph;
- determine the neighbourhood grid;
- determine the code-length grid;
- establish a validated upper or lower bound;
- be pooled with definitive output;
- be presented as independently reproduced evidence.

The two preserved exploratory result tables report optimiser values of
\(L_{\max}=5\).

The remembered claim that a heuristic assignment reached \(L_{\max}=4\) is not
backed by an artefact preserved in this repository. The original
`sphere_encoding_feasibility_l4/` directory was empty at the Stage 1 audit.
Accordingly, the claim remains unverified exploratory context.

## 20. Stage boundary

Stage 1 ends after repository foundation, protocol documentation, minimal
infrastructure, tests, style checks, provenance commits, and a clean final
audit.

Stage 1 must not:

- generate canonical icosphere datasets;
- run the exploratory annealer;
- implement or invoke an exact encoding solver;
- train a neural encoder;
- generate definitive scientific tables;
- interpret pre-protocol results as validated evidence;
- begin Stage 2.

## 18. Stage 3 prospective metric and baseline freeze

This section was frozen prospectively before any definitive Stage 3
encoding-performance output was calculated.

- Stage 3 starting HEAD:
  `8a4e70aeb0fb46d37c6e1d7d14f0219363cfe65c`;
- frozen configuration:
  `configs/stage3_baselines.json`;
- configuration SHA-256:
  `3fad68b97de95f82cbf65d31c9dc10d039efd375a9cf0f29f1a79396dbf77896`;
- accepted Stage 2 source run:
  `stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50`.

### 18.1 Hard-code validity

Every evaluated code array must have shape `(N, m)`, where `m` is strictly
positive. Values must have Boolean or integer dtype, must be finite and
nonmissing, and must belong exactly to `{0,1}`. Rows must preserve the
canonical Stage 2 vertex order.

Every definitive Stage 3 baseline must be injective. Collision-tolerant
arrays may be evaluated only when explicitly designated as collision
diagnostics; no such baseline is included in definitive Stage 3.

Definitive `codes.npy` arrays use `uint8`.

### 18.2 Hamming and angular distances

For bitstrings \(a,b\in\{0,1\}^m\),

\[
d_H(a,b)=\sum_{j=1}^m \mathbf{1}[a_j\ne b_j].
\]

Raw Hamming distance is used for local sensitivity. Normalised Hamming
distance is

\[
\bar d_H(a,b)=d_H(a,b)/m
\]

and is used for comparison with angular distance.

For unit vectors \(x,y\),

\[
d_\angle(x,y)
=
\arccos(\operatorname{clip}(x^\top y,-1,1))/\pi.
\]

### 18.3 Local edge metrics

Local distances are computed in the preserved canonical Stage 2 edge-row
order. Every graph edge is counted exactly once.

Report:

- \(L_{\max}\);
- number of edges attaining \(L_{\max}\);
- 99th percentile;
- 95th percentile;
- mean;
- population standard deviation with `ddof=0`;
- minimum;
- complete integer histogram from zero through `m`;
- edge count.

Both percentiles use NumPy quantiles with `method="higher"`. No interpolation
between discrete Hamming values is permitted.

Definitive `local_edge_hamming.npy` arrays use `int64`.

### 18.4 Exhaustive global metrics

Stage 3 uses every unordered pair `(i,j)` with `i<j`, ordered
lexicographically by `i` and then `j`. Pair subsampling is prohibited.

For each pair, distortion is

\[
\left|\bar d_H(E(x_i),E(x_j))-d_\angle(x_i,x_j)\right|.
\]

Report:

- unordered-pair count;
- Spearman angular-Hamming correlation;
- mean absolute distortion;
- root mean squared distortion;
- maximum absolute distortion;
- mean normalised Hamming distance;
- mean normalised angular distance.

### 18.5 Deterministic ranks and correlations

Tied observations receive average ranks. Spearman correlation is the
Pearson correlation of the two deterministic rank arrays.

Pearson correlation is calculated as the centred dot product divided by
the product of the centred Euclidean norms. If either ranked variable is
constant, Spearman correlation is undefined and is serialised as JSON
`null`, not as a misleading numeric value.

### 18.6 Far and antipodal pairs

The far-pair set is frozen as all exhaustive pairs satisfying

\[
d_\angle(x_i,x_j)\ge 0.75.
\]

Report far-pair count, minimum and mean raw Hamming distance, and minimum
and mean normalised Hamming distance.

Antipodal pairs reuse the accepted Stage 2 rule rather than introducing a
new threshold. They are the lexicographically enumerated unordered pairs
satisfying

```text
norm(vertices[i] + vertices[j]) <= 1e-12
```

where `1e-12` is the frozen `antipodal_atol` in
`configs/stage2_graph_suite.json`.

The resulting pairs must equal the Stage 2 metadata count, must total
`N/2`, and must use every vertex exactly once.

Report antipodal-pair count, minimum, maximum and mean raw Hamming distance,
and minimum and mean normalised Hamming distance.

### 18.7 Collision and bit diagnostics

Collision diagnostics report unique codeword count, `N` minus unique
codeword count, largest collision-class size, and number of collision
classes larger than one.

Bit balance reports every bit's fraction of ones, mean and maximum absolute
deviation from `0.5`, and constant-bit count.

Two distinct bit positions are duplicates when their full columns are
exactly equal. They are complementary when one full column equals one
minus the other. Constant columns participate in these exact duplicate and
complementary counts.

Maximum absolute inter-bit Pearson correlation is calculated only over
pairs of distinct nonconstant bit positions. Pairs containing a constant
column are excluded. If fewer than two nonconstant bit positions exist,
the statistic is undefined and serialised as JSON `null`.

These diagnostics do not establish circuit complexity.

### 18.8 Frozen deterministic baselines

Stage 3 implements exactly four encoders.

1. `canonical_index_binary`: fixed-width standard binary of canonical
   index `i`, using `m0=ceil(log2(N))` bits.
2. `canonical_index_gray`: fixed-width reflected Gray value
   `i xor (i >> 1)`, using `m0` bits.
3. `cartesian_coordinate_binary`: for each authoritative Stage 2 integer
   coordinate `c` in `[-q,q]`, encode `c+q` using
   `bq=ceil(log2(2q+1))` bits, concatenating `x`, then `y`, then `z`.
4. `cartesian_coordinate_gray`: apply reflected Gray coding separately to
   each shifted coordinate and concatenate `x`, then `y`, then `z`.

Fixed-width integer bits are ordered most-significant to least-significant.
Floating coordinates must not be requantised.

The two index encoders apply to all 13 graphs. The two Cartesian encoders
apply only to the nine primitive-direction graphs. The complete
applicability matrix therefore contains 52 rows: 44 applicable instances
and eight explicit inapplicable instances.

Index encoders are ordering controls and must not be described as
geometry-aware constructions. Cartesian Gray is Adam's direct baseline but
is not an intrinsic spherical Gray code.

### 18.9 Code-length reporting

Every baseline records code length `m`, minimum injective length
`m0=ceil(log2(N))`, and excess bits `m-m0`.

Raw \(L_{\max}\) values at different code lengths must not be compared
without explicitly reporting the code-length difference. Stage 3 does not
perform rate-adjusted optimisation.

### 18.10 Stage boundary

Stage 3 excludes random codebooks, random or optimised hyperplanes, affine
threshold encoders, spherical-coordinate codes, hierarchical icosahedral
encoders, space-filling encoders, learned hashing, neural encoders and
solver-generated assignments.

Stage 3 may report definitive descriptive baseline measurements. It may
not claim optimality, prove a lower bound, infer generalisation beyond the
frozen graphs, or begin Stage 4.

## 19. Stage 4 exact-solver prospective amendment

### 19.1 Original pending decisions

Section 17 left the exact solver and version, exact-solver time budget, and
largest exact instance unresolved before Stage 4 definitive solving.

### 19.2 Prospective resolution

Before any Stage 4 solver outcome was generated or inspected, these decisions
were frozen as follows:

- solver: Google OR-Tools CP-SAT `9.15.6755`;
- dependency constraint: `ortools>=9.15,<9.16`, resolved in `uv.lock`;
- definitive settings: one search worker, random seed zero, search logging
  enabled, and CP-SAT presolve enabled;
- exact-core graphs: `icosphere_l0`, `icosphere_l1`, and the three
  `primitive_q2_*` graphs at the code lengths listed in
  `configs/stage4_exact.json`;
- frontier graphs: `icosphere_l2` and the three `primitive_q3_*` direct
  comparisons at the frozen code lengths;
- total suite: exactly 21 graph-bit instances;
- per-instance budgets: 5 minutes for `icosphere_l0`, 20 minutes for
  `icosphere_l1`, 90 minutes for `icosphere_l2`, 60 minutes for each
  `primitive_q2_*` instance, and 180 minutes for each `primitive_q3_*`
  instance;
- candidate targets are allocated equal shares of each instance budget before
  its first solve and are attempted in ascending local-bound order;
- unused time is not transferred between instances.

The complete formulation, source identities, instance order, baseline rules,
symmetry breaking, classifications, outputs, and reproduction requirements are
frozen in `configs/stage4_exact.json`.

### 19.3 Basis and inspected evidence

The resolution used the accepted Stage 2 graph sizes and hashes, accepted
Stage 3 baseline upper bounds, elementary structural lower bounds, anticipated
CP-SAT scaling, deterministic single-worker reproducibility, and the available
compute budget. No Stage 4 feasibility, infeasibility, timeout, witness, or
scientific result had been generated or inspected.

### 19.4 Interpretation correction check

No authoritative file contained the stronger claim that Cartesian Gray is
asymptotically unbounded. The permitted interpretation remains: across tested
primitive resolutions \(q=2,3,4\), Cartesian Gray worst-case local sensitivity
increased from 3 to 5 to 8, while asymptotic boundedness and the growth rate
remain unresolved.

### 19.5 Affected runs and boundary

This amendment governs all definitive Stage 4 targets. Stage 5 heuristic
free-codebook search remains prohibited until Stage 4 is complete and accepted.

### 19.6 Pre-execution implementation readiness

Before the first definitive target was invoked, the complete implementation,
artifact, installation and reproduction workflow passed 226 ordinary tests,
Ruff and whitespace checks. The independently derived execution plan contains
exactly 21 instances, 68 ordered targets and 81,600 seconds of maximum frozen
target budget, with plan SHA-256
`a31795f8057b66594a1127ee877f05b4b5c8ab4feed8737a413ce834ace6f200`.

All 68 CP-SAT models were constructed without solving. Their individual
serialisations matched their recorded SHA-256 values; together they contain
336,918 variables, 288,600 constraints and 22,076,467 serialised bytes. The
ordered set of 68 model hashes has aggregate SHA-256
`2d0a08e15818bad33c084ec74a335c7a3459c49c4b8cd27135905b54f43a74d9`.
This readiness audit generated no feasibility status, witness, bound or other
Stage 4 scientific outcome.

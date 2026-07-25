# Project State

## State-record context

This state record was created during Stage 1 immediately before the
authoritative Stage 1 foundation commit and final acceptance audit.

- Repository path: `/Users/alexkolesnikov/Projects/sphere-encoding`
- Branch: `main`
- Recorded repository HEAD: `e16e474d7362215ec220805acf26335822976c4d`
- Meaning of recorded HEAD: accepted pre-foundation exploratory-inventory commit
- Working-tree state at document creation: dirty with intended uncommitted Stage 1 foundation files
- Expected final state: all Stage 1 files committed and working tree clean
- Final Stage 1 HEAD: to be reported in the Stage 1 completion report because a
  file cannot contain the hash of the commit that first contains that same file

## Current stage

Stage 3 of 13, Metrics and Deterministic Baseline Encodings, is active at
the prospective metric-and-baseline freeze step.

Stage 2 of 13, Canonical Sphere Graphs, remains complete and accepted.

Stage 1 remains accepted at commit
`05b2b96ef1e86fc2505d33cd0c5c916090267335`.

The definitive Stage 2 graph suite was generated from the clean committed
implementation at `f2baeb7dbb50676051c85fa562f2ead89a5c65c9` and committed at
`23a5669125e0bfb71e71330bde6bcf9d7ae25723`.

The definitive run identifier is:

`stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50`

Stage 3 has begun only through the prospective definition freeze. No
definitive encoding metric or baseline result has been generated, and no
optimisation, solver, heuristic search or neural-encoder work has started.

## Stage 3 prospective freeze record

Stage 3 began from clean `main` at:

`8a4e70aeb0fb46d37c6e1d7d14f0219363cfe65c`

The prospective Stage 3 configuration is:

`configs/stage3_baselines.json`

Its SHA-256 under the repository's canonical configuration hashing rule is:

`3fad68b97de95f82cbf65d31c9dc10d039efd375a9cf0f29f1a79396dbf77896`

The freeze records:

- exact hard-binary validity and injectivity requirements;
- raw and normalised Hamming distance;
- clipped normalised angular distance;
- complete local metrics, `method="higher"` percentiles and `ddof=0`;
- exhaustive unordered global pairs with no subsampling;
- deterministic average ranks and explicit Spearman handling;
- far-pair threshold `0.75`;
- reuse of Stage 2 antipodal tolerance `1e-12`, with unique pairing;
- collision, bit-balance and bit-redundancy diagnostics;
- canonical-index binary and Gray baselines on all 13 graphs;
- Cartesian-coordinate binary and Gray baselines on nine primitive graphs;
- 44 applicable instances and eight explicit inapplicable combinations;
- deterministic raw, table, manifest, archive and reproduction rules.

Random threshold baselines and all other random, optimised, learned or
solver-generated encoders are excluded from Stage 3.

No definitive Stage 3 output existed when these decisions were frozen.

## Repository history

The repository did not contain Git history when Stage 1 began.

The initial history is:

1. `2a7e6bc2839aefe7f0b0a2be1bc5777bd6e00b28`:
   preserved the pre-protocol exploratory baseline;
2. `e16e474d7362215ec220805acf26335822976c4d`:
   relocated and inventoried the pre-protocol exploratory material.

The forthcoming Stage 1 foundation commit will contain the authoritative
protocol, implementation order, project state, package infrastructure, tests,
environment lock, and repository directory structure.

## Exploratory work present

Pre-protocol material is preserved under:

`exploratory/pre_protocol_2026-07/`

The inventory records 20 entries:

- one exploratory Python script;
- two exploratory result directories containing eight files each;
- the original exploratory README;
- the original exploratory requirements file;
- one originally empty feasibility-output directory.

The 19 original files were verified byte-identical after relocation.

The original empty directory is represented by an explanatory notice because
Git does not track empty directories.

All preserved exploratory material is scientifically non-definitive.

## Exploratory findings and limitations

The preserved exploratory work used:

- 290 primitive integer directions;
- coordinate bound \(q=3\);
- a symmetric 6-nearest-neighbour graph;
- 1,032 undirected edges;
- 9-bit codes;
- Cartesian binary and Gray baselines;
- a heuristic injective swap optimiser.

Both preserved exploratory result tables report an optimiser value of
\(L_{\max}=5\).

The remembered exploratory claim that a heuristic assignment reached
\(L_{\max}=4\) is not supported by an artefact preserved in this repository.

The original `sphere_encoding_feasibility_l4/` directory was empty during the
Stage 1 audit.

No exploratory result may be treated as a validated upper bound, lower bound,
primary-graph result, or definitive scientific result.

## Scientific claims currently permitted

The following claims are currently permitted:

- the repository foundation and protocol infrastructure exist;
- pre-protocol work is preserved and inventoried;
- deterministic configuration, hashing, atomic writing, environment capture,
  repository capture, and manifest-writing helpers are implemented and tested;
- the primary and secondary Stage 2 graph families were frozen prospectively;
- four canonical icosphere triangulation graphs were generated and validated;
- nine canonical primitive integer-direction graphs were generated and
  validated using the frozen tie-complete symmetric neighbourhood rule;
- all 13 definitive graph instances were serialized deterministically,
  manifested, hashed, archived, and independently reproduced byte-for-byte;
- the Stage 2 graph suite is an accepted experimental-input package, not an
  encoding-performance result;
- no Stage 3 encoding result exists yet.

The following claims are not currently permitted:

- that \(L_{\max}=4\) has been validated definitively;
- that \(q=3,\ k=6\) is the primary experimental condition;
- that any current codebook is optimal;
- that any solver-certified lower bound exists;
- that any explicit or neural encoder has been evaluated definitively;
- that any rate-smoothness or Pareto conclusion has been established.

## Frozen decisions

### Primary metric

\[
L_{\max}(C)
=
\max_{(u,v)\in\mathcal{E}}
d_H(C(u),C(v)).
\]

### Mandatory validity

Every definitive encoding must be injective on the evaluated finite point set.

### Primary graph family

Icosphere triangulation graphs.

### Secondary graph family

Primitive integer-direction sphere sets with:

- \(q\in\{2,3,4\}\);
- nominal \(k\in\{4,6,8\}\);
- oriented vectors with antipodal partners retained;
- tie-complete symmetric angular nearest-neighbour construction;
- deterministic lexicographic integer-vector ordering.

The angular tie tolerance is frozen at \(10^{-12}\) radians. The prior
\(q=3,\ k=6\) condition is not privileged.

### Code-length candidates

For \(m_0=\lceil\log_2N\rceil\):

\[
m\in\{m_0,\ m_0+1,\ m_0+2,\ m_0+4\}.
\]

Any omission on the largest graph must be decided prospectively from compute
evidence rather than scientific outcomes.

### Mandatory local metrics

- \(L_{\max}\);
- number of edges attaining \(L_{\max}\);
- 99th percentile;
- 95th percentile;
- mean local Hamming distance;
- full local-distance distribution.

### Mandatory global diagnostics

- Spearman angular-Hamming correlation;
- mean absolute global distortion;
- maximum global distortion;
- far-pair behaviour;
- antipodal behaviour;
- collision count;
- bit balance;
- bit redundancy.

### Evidential interpretation

- a feasible valid code proves an upper bound;
- solver-certified infeasibility proves a lower bound;
- timeout proves neither;
- heuristic failure proves neither;
- an arbitrary codebook is not an explicit encoder;
- neural performance on training points may be memorisation.

## Pending decisions

The following decisions remain unresolved:

| Decision | Resolution deadline |
|---|---|
| Exact solver and frozen version | Before Stage 4 definitive solving |
| Exact-solver time budget | Before Stage 4 definitive solving |
| Largest exact instance | Before Stage 4 definitive solving |
| Large-instance heuristic budget | Before Stage 5 definitive search |
| Final compact neural architecture subset | Before Stage 9 definitive training |
| Whether higher-dimensional \(S^3\) experiments proceed | Before Stage 11 |
| Whether \(m_0+4\) runs at the largest resolution | Before the largest Stage 6 run |

These decisions must be resolved prospectively from implementation feasibility,
compute projection, reproducibility, or methodological evidence.

They may not be selected using favourable scientific outcomes.

## Infrastructure state

Implemented:

- Python package under `src/sphere_encoding/`;
- deterministic canonical JSON serialisation;
- deterministic human-readable JSON serialisation;
- duplicate-key rejection;
- non-finite JSON-number rejection;
- deterministic configuration hashing;
- SHA-256 byte hashing;
- streaming SHA-256 file hashing;
- safe atomic byte and text writing;
- Python, operating-system, machine, and package-version capture;
- Git root, branch, commit, and cleanliness capture;
- deterministic manifest construction and writing;
- unit tests;
- Ruff configuration;
- `uv` lock file;
- manifests, results, archives, scripts, and test directories.

Authoritative Stage 2 scientific modules now exist for deterministic
icosphere construction, primitive integer-direction generation, tie-complete
symmetric neighbourhood construction, structural validation, deterministic
serialization, archive creation, and definitive Stage 2 execution.

The definitive Stage 2 implementation identity is
`f2baeb7dbb50676051c85fa562f2ead89a5c65c9`.

## Environment state

Authoritative development environment:

- Python: 3.11.15;
- package manager: `uv 0.11.28`;
- test framework: pytest 8.4.2;
- linter: Ruff 0.16.0.

The initial shell audit found a malformed `PATH` containing only a relative
repository entry. Standard macOS executable directories must remain available.

The Stage 1 `uv sync --dev` environment intentionally contains only project
and development dependencies. The scientific packages used by the
pre-protocol exploratory script are not authoritative Stage 1 dependencies.

## Known limitations

- no definitive encoding metric or baseline result has been generated;
- the definitive secondary suite is restricted to the frozen \(q\in\{2,3,4\}\), nominal \(k\in\{4,6,8\}\) grid;
- no exact solver has been selected;
- no solver certificate or lower bound exists;
- no large-instance heuristic budget has been frozen;
- percentile interpolation and some global-diagnostic details remain to be
  frozen before definitive metric analysis;
- no encoder class has been evaluated under the authoritative protocol;
- no robustness or generalisation evidence exists;
- the preserved exploratory \(L_{\max}=4\) claim lacks a repository artefact;
- repository provenance begins only from Stage 1 because no prior Git history
  existed.

## Definitive execution state

- Definitive sphere graphs generated: no.
- Definitive encoding instances solved: no.
- Exact solver invoked: no.
- Heuristic optimiser rerun: no.
- Neural encoder trained: no.
- Definitive scientific tables generated: no.
- Definitive scientific figures generated: no.
- Stage 2 outputs present: yes, 83 committed output files.
- Stage 2 complete: yes; Stage 3 has not started.

## Stage 2 completion record

Stage 2 was completed through four controlled commits:

1. prospective graph-suite freeze:
   `b666da99febaf07c003dbfd0d5118518b9f32e35`;
2. deterministic graph-generator implementation:
   `24b2d10d7d116df8a3a3f184613a631b2ae1b02c`;
3. deterministic artifact and definitive-run pipeline:
   `f2baeb7dbb50676051c85fa562f2ead89a5c65c9`;
4. definitive graph-suite outputs:
   `23a5669125e0bfb71e71330bde6bcf9d7ae25723`.

Definitive identity:

- run ID: `stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50`;
- primary graphs: four icosphere triangulation graphs, levels 0 through 3;
- secondary graphs: nine primitive integer-direction graphs from
  \(q\in\{2,3,4\}\) and nominal \(k\in\{4,6,8\}\);
- total graph count: 13;
- deterministic package files: 81;
- deterministic archive members: 81;
- total committed Stage 2 output files: 83;
- configuration SHA-256: `b0acb6e8683a7d10cff99891c7346043de0ee7b3a0087cf71545d5df299eef01`;
- package-tree SHA-256: `24208510f0cc946ac3f5fc1108367234654ab95af685c2ffc41f1b39d3562ea7`;
- archive SHA-256: `30ff508a8b87c22808d6448fd7147017d6f65d8b52bb22b77b6b5304f8610a71`.

Acceptance evidence:

- all 13 graphs passed structural and geometric validation;
- graph identifiers and canonical ordering were stable;
- all package files were individually hashed and manifested;
- the deterministic archive metadata and member set were audited;
- independent regeneration reproduced every package file and the archive
  byte-for-byte;
- 68 tests passed;
- Ruff passed;
- `git diff --check` passed;
- the repository was clean after the output commit;
- no Stage 3 implementation or execution was present.

Scientific interpretation:

The Stage 2 outputs define canonical experimental domains for later encoding
work. They establish no encoding-performance upper bound, lower bound,
optimality claim, or comparison between encoding classes.

## Active Stage 2 configuration

The prospective Stage 2 graph suite is recorded in
`configs/stage2_graph_suite.json`.

Frozen primary instances:

- `icosphere_l0`;
- `icosphere_l1`;
- `icosphere_l2`;
- `icosphere_l3`.

Frozen secondary instances are the Cartesian product of:

- \(q\in\{2,3,4\}\);
- nominal \(k\in\{4,6,8\}\).

This yields nine primitive-direction graph instances using tie-complete
symmetric angular nearest-neighbour construction.

No definitive graph output existed when this configuration was frozen.

## Active work and next boundary

Stage 3 is complete and accepted at commit
`3c5b8d8332326b65da6acaee666df7730cd916bd`.

Active work is Stage 4 of 13: Exact Free-Codebook Optimisation.

The exact solver is frozen as Google OR-Tools CP-SAT `9.15.6755` under
the locked constraint `ortools>=9.15,<9.16`. The fixed 21-instance suite,
budgets, execution order, formulation, source identities, status
interpretation, and reproduction rules are recorded prospectively in
`configs/stage4_exact.json`.

The Stage 4 implementation is complete through the following controlled
commits:

- exact feasibility models: `0545e73ee098c052230e0a7e333be39cd90c19f0`;
- solver execution and independent witness validation:
  `d06122c19a8df229d41a1473925eec5db52c791c`;
- frozen target planning: `d187d600ccb449d48cf0b24e2070bf26406c99a7`;
- target execution and classification:
  `923df71f6d7e204fea247f3f0b3b5bd5917de230`;
- evidence preservation, tables, packaging, manifests, installation and
  reproduction safeguards: commits `358f2287caeb6dd5055da55eef72c259133b09c0`
  through `f4f85c1e99eef1d40f7740ea978409784c753bb5`.

The derived plan contains exactly 21 instances, 68 ordered targets and
81,600 seconds of frozen maximum target budget. Its SHA-256 is
`a31795f8057b66594a1127ee877f05b4b5c8ab4feed8737a413ce834ace6f200`.
The 68 regenerated deterministic model hashes have aggregate SHA-256
`2d0a08e15818bad33c084ec74a335c7a3459c49c4b8cd27135905b54f43a74d9`.
All 225 ordinary tests, Ruff and whitespace checks pass.

No definitive Stage 4 target has been solved and no Stage 4 scientific output
exists. The next controlled step is the first definitive execution from the
clean implementation commit. Stage 5 has not started and remains prohibited
until Stage 4 is complete and accepted.

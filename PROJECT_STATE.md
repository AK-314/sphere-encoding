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

Stage 1 of 13: Repository Baseline and Protocol Foundation.

Implementation is complete in the working tree and remains subject to final
staging, commit, and forensic acceptance checks.

Stage 2 has not started.

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
- the project has frozen its primary metric, graph families, code-length grid,
  validity requirements, mandatory diagnostics, and evidential interpretation;
- no definitive graph or encoding result exists yet.

The following claims are not currently permitted:

- that \(L_{\max}=4\) has been validated;
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

Primitive integer-direction sphere sets evaluated across a prespecified
neighbourhood grid.

The prior \(q=3,\ k=6\) condition is not privileged.

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

The authoritative scientific algorithm modules do not yet exist.

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

- no canonical icosphere graph has been generated;
- no definitive secondary neighbourhood grid has been frozen yet;
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
- Stage 2 outputs present: no.
- Stage 2 started: no.

## Next stage

Stage 2 of 13: Canonical Sphere Graphs.

Stage 2 may begin only after:

- the Stage 1 foundation commit succeeds;
- all tests pass;
- Ruff passes;
- whitespace checks pass;
- the exact committed file set is recorded;
- the final working tree is clean;
- the Stage 1 completion report is accepted by the main project chat.

Stage 2 must create deterministic and validated graph inputs only.

It must stop before Stage 3 metrics and baseline encodings.

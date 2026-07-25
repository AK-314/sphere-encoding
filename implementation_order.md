# Implementation Order

## 1. Purpose and authority

This document defines the complete implementation sequence for the
sphere-encoding project.

The stages are ordered so that graph definitions, metrics, baselines,
optimisation methods, compute budgets, and evidential rules are fixed before
they are used for definitive scientific interpretation.

A later stage may depend on outputs from an earlier accepted stage, but it may
not silently alter an earlier stage's frozen scientific decisions.

Every stage ends at an explicit boundary. Work belonging to the next stage must
not begin before the current stage has passed its acceptance gate and its
completion report has been reviewed in the main project chat.

## 2. General stage rules

For every stage:

- begin from a recorded clean repository state;
- verify the expected starting commit;
- preserve deterministic inputs and configuration;
- use controlled scripts rather than ad hoc notebook state;
- write manifests before or alongside definitive execution;
- hash all scientific inputs and outputs;
- run the full test suite;
- run Ruff;
- run `git diff --check`;
- record all implementation and scientific errors;
- distinguish exact results, heuristic results, and diagnostics;
- stop at the stage boundary;
- commit only after the acceptance gate passes.

Definitive scientific execution begins only in the stage that explicitly
authorises it.

## 3. Stage 1: Repository and protocol foundation

### Purpose

Create the authoritative project foundation before any further scientific
computation.

### Dependencies

- existing repository directory;
- existing pre-protocol exploratory material, if present;
- Python 3.11;
- `uv`;
- Git.

### Expected implementation

- inspect repository and environment without modification;
- identify Git status and initialise Git if absent;
- preserve and inventory all pre-protocol exploratory files;
- relocate exploratory material into an explicitly excluded location where
  safe;
- create `experimental_protocol.md`;
- create `implementation_order.md`;
- create `PROJECT_STATE.md`;
- create `pyproject.toml`;
- establish `src/sphere_encoding/`;
- establish `tests/`;
- establish `manifests/`;
- establish `results/tables/`;
- establish `results/figures/`;
- establish `results/raw/`;
- establish `results/archives/`;
- establish `scripts/`;
- implement deterministic JSON serialisation and loading;
- implement SHA-256 file and byte hashing;
- implement atomic file writing;
- implement environment and repository provenance capture;
- implement deterministic manifest writing;
- document shell and environment requirements.

### Required tests

- deterministic canonical JSON ordering;
- duplicate JSON-key rejection;
- non-finite JSON-number rejection;
- deterministic configuration hashing;
- file hashing across chunk sizes;
- invalid hash chunk-size rejection;
- atomic file creation and replacement;
- UTF-8 atomic text writing;
- deterministic manifest formatting;
- environment-version capture;
- clean and dirty Git-state detection;
- Git commit, branch, and root capture;
- manifest envelope construction;
- invalid stage-number rejection.

### Scientific outputs

None.

The exploratory inventory is a provenance output, not a scientific result.

### Reproduction expectations

A new environment must be able to run:

    uv sync --dev
    uv run pytest
    uv run ruff check .
    git diff --check

The exploratory inventory must contain original paths, relocated paths,
classification, hashes, baseline tracking status, and a non-definitive label.

### Acceptance gate

Stage 1 passes only when:

- repository identity is verified;
- Git branch and history are understood;
- exploratory work is preserved and inventoried;
- authoritative protocol documents exist;
- package and test structure exists;
- provenance helpers are tested;
- all tests pass;
- Ruff passes;
- whitespace checks pass;
- implementation commits are recorded;
- the working tree is clean;
- no definitive graph output exists;
- no definitive scientific execution has begun.

### Exact stopping boundary

Stop after the structured Stage 1 completion report.

Do not generate an icosphere, construct a definitive graph, rerun the
exploratory optimiser, implement an exact encoding solver, or train an encoder.
Do not begin Stage 2.

## 4. Stage 2: Canonical sphere graphs

### Purpose

Create deterministic, validated, versioned graph instances that define the
domains for all later encoding experiments.

### Dependencies

- accepted Stage 1;
- frozen graph-family rules from `experimental_protocol.md`;
- accepted repository and manifest infrastructure.

### Expected implementation

- implement deterministic icosphere subdivision;
- establish canonical vertex and face ordering;
- construct primary triangulation adjacency;
- implement primitive integer-direction point generation;
- define and freeze the secondary neighbourhood grid;
- implement deterministic symmetric neighbourhood construction;
- implement graph identifiers derived from configuration and content hashes;
- save points, faces where applicable, edges, metadata, and manifests;
- implement validation summaries;
- document prospective graph-resolution choices;
- freeze all definitive Stage 2 graph configurations before encoding results
  exist.

### Required tests

- expected low-resolution icosphere vertex, face, and edge counts;
- unit-norm validation;
- duplicate-point rejection;
- self-loop rejection;
- duplicate-edge rejection;
- canonical undirected edge ordering;
- deterministic repeated generation;
- graph connectivity;
- expected degree structure for low-resolution icospheres;
- deterministic primitive-direction generation;
- opposite-direction retention;
- primitive-vector filtering;
- deterministic tie handling in secondary graphs;
- manifest and content-hash stability.

### Scientific outputs

- canonical primary graph files;
- canonical secondary graph files;
- graph summary table;
- graph-validation table;
- degree and edge-angle diagnostic figures;
- Stage 2 graph manifests.

These outputs define experimental inputs. They are not encoding-performance
results.

### Reproduction expectations

Independent regeneration from the same configuration and commit must reproduce
all deterministic graph arrays and metadata byte-for-byte where practical.

Graph identities and hashes must be independently checked after regeneration.

### Acceptance gate

Stage 2 passes only when:

- every planned graph is generated from frozen configuration;
- every graph passes structural validation;
- graph identifiers are stable;
- repeated generation is deterministic;
- all saved files are manifested and hashed;
- the secondary neighbourhood grid is frozen;
- no encoding optimisation has been run;
- tests, Ruff, whitespace, repository, and archive checks pass.

### Exact stopping boundary

Stop after accepted graph files, manifests, validation outputs, commits, and the
Stage 2 completion report.

Do not implement definitive encoding metrics or baseline encoders beyond any
minimal graph-test fixtures required for validation. Do not begin Stage 3.

## 5. Stage 3: Metrics and deterministic baseline encodings

### Purpose

Freeze and implement the complete deterministic evaluation layer, then
evaluate only the four prespecified non-optimised baselines before any
optimisation method is introduced.

### Dependencies

- accepted Stage 2 run
  `stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50`;
- verified Stage 2 configuration, package-tree and archive hashes;
- canonical graph identifiers and saved arrays;
- prospectively frozen Stage 3 configuration and metric definitions.

### Prospective freeze

Before definitive results:

- freeze hard-binary validity and injectivity;
- freeze raw and normalised Hamming distance;
- freeze clipped normalised angular distance;
- freeze the complete local metric set;
- freeze NumPy quantiles with `method="higher"`;
- freeze population local standard deviation with `ddof=0`;
- freeze exhaustive unordered-pair evaluation;
- freeze deterministic average ranks and Spearman implementation;
- freeze far pairs at normalised angular distance at least `0.75`;
- reuse Stage 2 antipodal tolerance `1e-12`;
- freeze collision, bit-balance and bit-redundancy diagnostics;
- freeze applicability and deterministic serialisation.

### Expected implementation

- implement reusable hard-binary encoding validation;
- implement collision and injectivity diagnostics;
- implement vectorised and reference Hamming calculations;
- preserve canonical edge order;
- implement all frozen local metrics and complete histograms;
- implement clipped angular distance and exhaustive pair enumeration;
- implement tied average ranks and deterministic Spearman correlation;
- implement global distortion, far-pair and antipodal diagnostics;
- implement bit-balance and redundancy diagnostics;
- implement canonical-index binary;
- implement canonical-index Gray;
- implement Cartesian-coordinate binary from Stage 2 integer vectors;
- implement Cartesian-coordinate Gray from Stage 2 integer vectors;
- create the complete 52-row applicability matrix;
- evaluate exactly 44 applicable graph-encoding instances;
- create deterministic raw arrays, JSON metrics and CSV tables;
- create the Stage 3 manifest and deterministic archive;
- independently reproduce every deterministic output.

### Required tests

- valid and malformed code arrays;
- collision detection and injectivity;
- exact binary and reflected Gray examples;
- fixed-width and insufficient-width handling;
- Cartesian coordinate order, widths and range validation;
- exact and vectorised Hamming examples;
- canonical edge-order preservation;
- complete local histograms;
- exact `method="higher"` percentile fixtures;
- angular clipping and exhaustive pair ordering;
- tied average ranks and constant-variable handling;
- exact Spearman reference examples;
- exact global-distortion and far-threshold fixtures;
- accepted antipodal pairing and count validation;
- balanced, constant, duplicate and complementary bit fixtures;
- defined constant-column treatment;
- exactly 44 evaluated instances and 52 applicability rows;
- deterministic JSON, CSV, NPY, manifest and archive output;
- archive member parity and deterministic recreation;
- independent reproduction.

### Scientific outputs

- one raw directory per applicable graph-encoding instance;
- `codes.npy`;
- `local_edge_hamming.npy`;
- `metrics.json`;
- baseline-summary table;
- complete local-histogram table;
- full applicability table;
- Stage 3 manifest;
- deterministic Stage 3 archive.

### Reproduction expectations

Every deterministic Stage 3 output must reproduce byte-for-byte from a
clean detached worktree at the exact implementation commit. Runtime-bearing
fields must be explicitly classified and compared semantically.

### Acceptance gate

Stage 3 passes only when:

- the metric and baseline definitions were committed before definitive
  execution;
- Stage 2 inputs match all accepted hashes;
- all metric and encoder tests pass;
- exactly 44 applicable instances exist;
- all definitive encodings are injective;
- all eight inapplicable combinations are recorded;
- local histograms sum exactly to graph edge counts;
- exhaustive pair counts equal `N(N-1)/2`;
- antipodal counts equal accepted Stage 2 metadata;
- all output hashes match the manifest;
- archive member parity and deterministic regeneration pass;
- independent detached-worktree reproduction passes;
- full tests, Ruff and whitespace checks pass;
- results are committed and the repository is clean;
- Stage 4 has not started.

### Exact stopping boundary

Do not implement random codebooks, random or optimised hyperplanes,
threshold encoders, exact solvers, heuristic codebook search, learned
encoders or neural training.

Stop after deterministic baseline evaluation and the Stage 3 completion
report. Do not begin Stage 4.

## 6. Stage 4: Exact free-codebook optimisation

### Purpose

Establish solver-certified bounds or optima for the largest prospectively
feasible small instances.

### Dependencies

- accepted Stage 3;
- exact solver choice and version frozen;
- exact-solver time budget frozen;
- largest exact instance frozen;
- validated metric and graph infrastructure.

### Expected implementation

- formalise threshold-feasibility models for \(L_{\max}\);
- enforce injectivity exactly;
- implement deterministic model construction;
- implement symmetry breaking where valid;
- implement solver-status interpretation;
- preserve incumbents, bounds, certificates, and logs;
- implement threshold search or direct optimisation;
- independently validate every feasible code;
- independently verify solver claims where possible;
- distinguish optimum, feasible, infeasible, unknown, and timeout statuses.

### Required tests

- tiny instances with manually known optima;
- injectivity-constraint tests;
- threshold-feasibility fixtures;
- infeasible-capacity fixtures;
- symmetry-breaking equivalence tests;
- deterministic model generation;
- solver-status parsing;
- timeout handling;
- incumbent validation;
- corrupted-solution rejection;
- independent objective recomputation.

### Scientific outputs

- exact-result table;
- certified lower-bound table;
- feasible upper-bound table;
- solver-status table;
- runtime table;
- exact codebooks;
- solver logs and certificates where available;
- Stage 4 manifests.

### Reproduction expectations

Every exact claim must preserve:

- solver name and frozen version;
- complete model configuration;
- deterministic input hashes;
- solver command or API settings;
- time and resource limits;
- raw status;
- best incumbent;
- lower bound;
- certificate or independently checkable evidence where supported.

### Acceptance gate

Stage 4 passes only when:

- every exact claim has validated status;
- every feasible code passes independent injectivity and metric recomputation;
- every lower bound is tied to certified infeasibility or a valid solver bound;
- timeouts are not described as negative proofs;
- all frozen small instances are attempted;
- outputs, archives, manifests, tests, Ruff, and whitespace checks pass.

### Exact stopping boundary

Stop after exact small-instance analysis and the Stage 4 completion report.

Do not launch large-scale heuristic optimisation. Do not begin Stage 5.

## 7. Stage 5: Scalable free-codebook search

### Purpose

Search larger unrestricted-codebook instances under a frozen heuristic budget.

### Dependencies

- accepted Stage 4;
- large-instance heuristic budget frozen;
- validated unrestricted-codebook representation;
- validated local metric implementation.

### Expected implementation

- implement one or more scalable search methods;
- preserve injectivity throughout or repair and revalidate it;
- use frozen initialisation and seed schedules;
- implement incremental objective updates where justified;
- preserve convergence traces;
- checkpoint long runs;
- distinguish best-of-budget results from typical-seed behaviour;
- compare heuristic results with exact optima or bounds on overlapping instances;
- implement restart and recovery handling.

### Required tests

- objective-delta correctness;
- swap or move validity;
- injectivity preservation;
- checkpoint round-trip;
- deterministic fixed-seed behaviour;
- restart equivalence;
- convergence-trace integrity;
- best-incumbent preservation;
- budget enforcement;
- exact-overlap regression tests;
- invalid checkpoint rejection.

### Scientific outputs

- best valid codebooks;
- per-seed result tables;
- convergence tables and figures;
- budget-use tables;
- exact-versus-heuristic overlap comparisons;
- Stage 5 manifests and archives.

### Reproduction expectations

Each run must preserve:

- seed;
- initialisation;
- move schedule;
- objective settings;
- full budget;
- stopping reason;
- best incumbent;
- convergence trace;
- checkpoint lineage;
- exact input and output hashes.

### Acceptance gate

Stage 5 passes only when:

- all frozen seeds and budgets are run;
- every reported codebook is valid;
- best-of-many selection is explicit;
- failed runs and timeouts are retained;
- overlap with exact instances is correctly interpreted;
- no heuristic failure is called infeasibility;
- outputs, archives, manifests, tests, Ruff, and whitespace checks pass.

### Exact stopping boundary

Stop after scalable unrestricted-codebook results and the Stage 5 completion
report.

Do not aggregate the full rate-smoothness curve or alter code-length choices
based on observed favourable outcomes. Do not begin Stage 6.

## 8. Stage 6: Rate-smoothness curve

### Purpose

Measure the relationship between code length and attainable local smoothness
across frozen graph instances.

### Dependencies

- accepted Stages 3 to 5;
- frozen code-length grid;
- prospective decision on any largest-instance omissions;
- validated exact and heuristic outputs.

### Expected implementation

- integrate valid baseline, exact, and heuristic results;
- evaluate all frozen code lengths that remain in scope;
- compute matched rate-smoothness tables;
- distinguish certified optima, bounded results, and heuristic upper bounds;
- implement uncertainty or seed summaries for stochastic methods;
- create plots that preserve evidential status;
- document any prospectively omitted largest-instance candidate.

### Required tests

- code-length-grid construction;
- matched-instance joins;
- evidential-status propagation;
- omission-rule enforcement;
- certified-bound plotting fixtures;
- no cross-graph accidental pooling;
- deterministic table ordering;
- figure-data consistency.

### Scientific outputs

- rate-smoothness tables;
- certified and empirical bound plots;
- method-by-code-length comparisons;
- omission and coverage table;
- Stage 6 analysis manifest.

### Reproduction expectations

Integrated tables must be reproducible directly from committed earlier-stage
outputs without rerunning optimisation.

Every plotted point must map to a specific source manifest and evidential
status.

### Acceptance gate

Stage 6 passes only when:

- the frozen candidate grid is respected;
- all omissions were decided prospectively;
- certified and heuristic points are visually and textually distinguished;
- every aggregate traces to valid source outputs;
- no favourable point is selectively highlighted without the full grid;
- tests, Ruff, whitespace, manifests, and repository checks pass.

### Exact stopping boundary

Stop after the accepted rate-smoothness analysis and Stage 6 completion report.

Do not optimise a composite local-global objective. Do not begin Stage 7.

## 9. Stage 7: Local-global Pareto frontier

### Purpose

Characterise trade-offs between worst-case local smoothness and preservation of
global angular geometry.

### Dependencies

- accepted Stage 6;
- frozen global-diagnostic definitions;
- accepted valid codebooks and baselines;
- frozen pair-sampling rules where needed.

### Expected implementation

- recompute or verify all mandatory global diagnostics;
- construct local-global objective records;
- identify nondominated solutions under declared objectives;
- implement controlled multi-objective search only if prospectively specified;
- distinguish observed frontiers from complete Pareto frontiers;
- analyse far-pair and antipodal behaviour;
- analyse bit balance and redundancy;
- preserve all dominated valid solutions needed for context.

### Required tests

- Pareto-dominance fixtures;
- duplicate-point handling in objective space;
- stable nondominated sorting;
- source-manifest traceability;
- pair-sampling determinism;
- far-pair and antipodal selection;
- figure-data consistency;
- no invalid-code inclusion.

### Scientific outputs

- local-global diagnostic table;
- observed Pareto-frontier table;
- Pareto figures;
- far-pair and antipodal analysis;
- bit-balance and redundancy analysis;
- Stage 7 manifest.

### Reproduction expectations

Frontier membership must be reproducible from committed metric tables.

Any additional multi-objective search must preserve its own frozen
configuration, seeds, budgets, and manifests.

### Acceptance gate

Stage 7 passes only when:

- all included encodings are valid;
- observed and complete frontiers are not conflated;
- every frontier point is traceable;
- local and global measures are not collapsed into an unprespecified composite;
- all diagnostics and source coverage are complete;
- tests, Ruff, whitespace, and repository checks pass.

### Exact stopping boundary

Stop after the accepted Pareto analysis and Stage 7 completion report.

Do not implement optimised linear or affine threshold encoders. Do not begin
Stage 8.

## 10. Stage 8: Linear and affine threshold encoders

### Purpose

Evaluate explicit hyperplane-based encoders that can encode points without an
arbitrary per-point lookup table.

### Dependencies

- accepted Stage 7;
- frozen threshold-optimisation budget;
- validated random threshold baselines;
- accepted graph and metric infrastructure.

### Expected implementation

- implement linear threshold encoders;
- implement affine threshold encoders;
- implement deterministic parameter serialisation;
- implement optimisation under frozen seeds and budgets;
- enforce or penalise collisions with final exact validation;
- record parameter counts and evaluation cost;
- compare random, optimised linear, and optimised affine encoders;
- evaluate all frozen graphs and code lengths in scope.

### Required tests

- threshold evaluation fixtures;
- bias-free linear special case;
- deterministic parameter loading;
- bit-order stability;
- collision checks after discretisation;
- fixed-seed optimisation repeatability where expected;
- budget enforcement;
- parameter-count correctness;
- objective recomputation;
- malformed-parameter rejection.

### Scientific outputs

- threshold-encoder parameter files;
- per-seed tables;
- local and global metric tables;
- random-versus-optimised comparisons;
- linear-versus-affine comparisons;
- efficiency tables;
- Stage 8 manifests and archives.

### Reproduction expectations

Every encoder must be reproducible from saved parameters and evaluation code.

Training or fitting traces, seeds, budgets, and stopping reasons must be
preserved.

### Acceptance gate

Stage 8 passes only when:

- every primary result is injective;
- invalid colliding runs are reported but excluded;
- linear and affine subclasses are clearly separated;
- all parameter and metric files are hashed;
- efficiency claims use declared proxies;
- tests, Ruff, whitespace, archives, and repository checks pass.

### Exact stopping boundary

Stop after threshold-encoder analysis and the Stage 8 completion report.

Do not train neural encoders. Do not begin Stage 9.

## 11. Stage 9: Small neural encoders

### Purpose

Evaluate compact neural encoders while separating finite-set memorisation from
evidence of geometric generalisation.

### Dependencies

- accepted Stage 8;
- final architecture subset frozen prospectively;
- training budget and seed schedule frozen;
- discretisation rule frozen;
- parameter-budget reporting defined.

### Expected implementation

- implement the frozen compact architectures;
- implement deterministic initialisation and training controls where possible;
- implement binary discretisation;
- enforce final injectivity checks;
- record training and evaluation curves;
- compare parameter count and lookup-table storage;
- evaluate training-point performance;
- reserve robustness and held-out geometric tests for Stage 11;
- preserve failed, colliding, and unstable runs.

### Required tests

- architecture output shapes;
- parameter-count fixtures;
- deterministic data ordering;
- discretisation rules;
- collision detection;
- checkpoint save and load;
- training-resume behaviour;
- fixed-seed regression on a tiny fixture;
- evaluation-mode correctness;
- invalid checkpoint rejection.

### Scientific outputs

- trained compact encoder checkpoints;
- per-seed training records;
- finite-set local and global metric tables;
- collision and validity tables;
- parameter and runtime tables;
- Stage 9 manifests and archives.

### Reproduction expectations

Each run must preserve:

- architecture identifier;
- full hyperparameters;
- seed;
- optimiser configuration;
- training budget;
- checkpoint hashes;
- discretisation rule;
- final binary codes;
- validity results;
- runtime and stopping reason.

### Acceptance gate

Stage 9 passes only when:

- all frozen architectures and seeds are accounted for;
- training-point performance is not called generalisation;
- every primary finite-set result is injective;
- failed and colliding runs remain visible;
- parameter and compute comparisons are qualified;
- tests, Ruff, whitespace, archives, and repository checks pass.

### Exact stopping boundary

Stop after finite-set neural-encoder analysis and the Stage 9 completion report.

Do not introduce explicit geometry-aware constructions or robustness claims.
Do not begin Stage 10.

## 12. Stage 10: Explicit geometry-aware constructions

### Purpose

Design and evaluate deterministic encoders derived explicitly from sphere
geometry rather than arbitrary pointwise assignments.

### Dependencies

- accepted Stage 9;
- accepted baseline and explicit-encoder evaluation infrastructure;
- prospectively documented construction families.

### Expected implementation

- implement prespecified geometry-aware constructions;
- document encoding algorithms independently of evaluated point order;
- record description length and computational interpretation;
- ensure deterministic tie and boundary handling;
- evaluate matched graphs and code lengths;
- compare with Cartesian, threshold, neural, and unrestricted-codebook results;
- separate construction design iterations from final protocol-governed variants.

### Required tests

- deterministic encoding of fixed coordinates;
- boundary and tie handling;
- point-order invariance;
- bit-length correctness;
- injectivity checks;
- construction-specific mathematical invariants;
- serialisation round-trips;
- matched-evaluation fixtures;
- malformed-input rejection.

### Scientific outputs

- explicit construction specifications;
- construction parameter files;
- matched local and global metric tables;
- efficiency and description-length tables;
- comparative figures;
- Stage 10 manifests and archives.

### Reproduction expectations

A reader must be able to encode a valid input using the saved construction
specification without loading an arbitrary point-to-code lookup table.

All parameters, boundary conventions, and source hashes must be preserved.

### Acceptance gate

Stage 10 passes only when:

- every claimed explicit encoder is genuinely evaluable from its declared rule;
- no hidden arbitrary codebook is required;
- all primary results are injective;
- construction variants were not selected solely on final favourable outcomes;
- comparisons are matched and traceable;
- tests, Ruff, whitespace, archives, and repository checks pass.

### Exact stopping boundary

Stop after explicit-construction analysis and the Stage 10 completion report.

Do not run robustness, transfer, or higher-dimensional experiments. Do not begin
Stage 11.

## 13. Stage 11: Robustness and generalisation

### Purpose

Test whether conclusions persist under perturbations, related graphs, unseen
points, seed changes, and optional higher-dimensional domains.

### Dependencies

- accepted Stage 10;
- prospective decision on \(S^3\);
- frozen perturbation and transfer protocols;
- accepted encoder implementations.

### Expected implementation

- define and freeze geometric perturbation distributions;
- test code stability under small point perturbations;
- test transfer across graph resolutions where meaningful;
- test neural and threshold encoders on held-out or newly generated points;
- evaluate sensitivity to graph-neighbourhood variants;
- evaluate seed stability;
- run optional \(S^3\) experiments only if prospectively approved;
- distinguish robustness diagnostics from original primary endpoints.

### Required tests

- deterministic perturbation generation;
- perturbation norm bounds;
- held-out split integrity;
- no train-test leakage;
- transferred-encoder identity;
- graph-variant traceability;
- seed aggregation;
- optional \(S^3\) dimension checks;
- robustness-table source mapping.

### Scientific outputs

- perturbation-stability tables;
- held-out generalisation tables;
- resolution-transfer tables;
- graph-variant sensitivity tables;
- seed-stability analysis;
- optional \(S^3\) results;
- Stage 11 manifests and archives.

### Reproduction expectations

Every robustness condition must have a frozen configuration, deterministic seed
schedule, source encoder identity, and complete input/output hashes.

### Acceptance gate

Stage 11 passes only when:

- perturbation and transfer conditions were frozen before outcome inspection;
- train-test leakage is excluded;
- finite-set memorisation and geometric generalisation are clearly separated;
- optional domains are labelled secondary;
- all planned robustness conditions are accounted for;
- tests, Ruff, whitespace, archives, and repository checks pass.

### Exact stopping boundary

Stop after robustness and generalisation analysis and the Stage 11 completion
report.

Do not assemble the final integrated report. Do not begin Stage 12.

## 14. Stage 12: Integrated analysis and report

### Purpose

Integrate all accepted stage outputs into a complete scientific analysis without
changing earlier evidential status.

### Dependencies

- accepted Stages 1 to 11;
- complete source manifests and archives;
- frozen analysis inclusion rules.

### Expected implementation

- create a source-of-truth integrated dataset;
- verify every included result against its source manifest;
- construct final tables and figures;
- distinguish exact optima, certified bounds, heuristic upper bounds, invalid
  results, and diagnostics;
- summarise local, global, efficiency, robustness, and generalisation findings;
- document limitations and negative results;
- draft the final technical report;
- produce a reproduction guide;
- produce a machine-readable output index.

### Required tests

- integrated-row source traceability;
- duplicate-result rejection;
- evidential-status preservation;
- table-to-figure consistency;
- no invalid-result promotion;
- no missing planned condition without explanation;
- deterministic table ordering;
- reproduction-command validation;
- archive membership checks.

### Scientific outputs

- final integrated tables;
- final figures;
- final technical report;
- reproduction guide;
- complete output index;
- final analysis manifest;
- final results archive.

### Reproduction expectations

The integrated analysis must be regenerable from committed accepted stage
outputs without rerunning expensive scientific searches unless explicitly
documented.

Every final claim must trace to one or more source records.

### Acceptance gate

Stage 12 passes only when:

- every final result is traceable;
- all evidential labels are preserved;
- no selective omission is unexplained;
- negative results and limitations are included;
- final tables, figures, report, and archive are internally consistent;
- all tests, Ruff, whitespace, reproduction, and repository checks pass.

### Exact stopping boundary

Stop after the integrated report, archive, commit, and Stage 12 completion
report.

Do not conduct the independent forensic audit within the implementation stage.
Do not begin Stage 13.

## 15. Stage 13: Independent forensic audit

### Purpose

Independently verify repository integrity, provenance, reproducibility, output
completeness, and scientific claim traceability.

### Dependencies

- accepted Stage 12;
- clean committed repository;
- final manifests, archives, report, tables, and figures;
- no uncommitted scientific changes.

### Expected implementation

- verify expected repository HEAD and parent lineage;
- verify clean working tree;
- verify complete committed file set;
- verify all manifest hashes;
- verify archive membership and byte identity;
- independently regenerate deterministic outputs;
- rerun all tests and style checks;
- verify graph and code validity;
- independently recompute key metrics;
- inspect exact and heuristic status interpretation;
- trace every major report claim to source outputs;
- verify Stage 13 does not silently modify scientific outputs;
- produce a forensic audit report.

### Required tests

The full project test suite is mandatory.

Additional audit scripts must check:

- repository identity;
- manifest identity;
- archive completeness;
- loose-versus-archived byte identity;
- deterministic-output reproduction;
- graph structural invariants;
- code injectivity;
- metric recomputation;
- integrated-table provenance;
- final-report source mapping;
- absence of later-stage artefacts.

### Scientific outputs

No new scientific result is created.

The Stage 13 output is an audit report stating pass, qualified pass, or fail,
with exact defects and resolutions.

### Reproduction expectations

The audit must be executable from the final committed state using documented
commands and a fresh environment.

Audit-generated temporary files must be separated from committed scientific
outputs unless an explicit audit artefact is intentionally committed.

### Acceptance gate

Stage 13 passes only when:

- repository identity is exact;
- the working tree is clean;
- tests and Ruff pass;
- whitespace checks pass;
- manifests and archives are complete;
- deterministic reproduction passes;
- independently recomputed metrics match;
- scientific claims preserve correct evidential interpretation;
- no unexplained file, hash, or provenance mismatch remains.

### Exact stopping boundary

Stop after the final forensic audit report and any explicitly authorised audit
commit.

Do not begin a new scientific extension, protocol amendment, or exploratory
follow-up within Stage 13.

## 16. Complete stage sequence

The authoritative order is:

1. repository and protocol foundation;
2. canonical sphere graphs;
3. metrics and baseline encodings;
4. exact free-codebook optimisation;
5. scalable free-codebook search;
6. rate-smoothness curve;
7. local-global Pareto frontier;
8. linear and affine threshold encoders;
9. small neural encoders;
10. explicit geometry-aware constructions;
11. robustness and generalisation;
12. integrated analysis and report;
13. independent forensic audit.

A stage may be repeated to repair a defect, but its scientific scope must not be
expanded silently. Any scope change must follow the protocol amendment rules.

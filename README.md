# Sphere Encoding

This repository studies injective binary encodings of finite point sets on the unit sphere. The objective is to minimise the largest Hamming distance between codewords assigned to neighbouring directions in a fixed graph:

$$
L^*_{\mathrm{free}}(G,m)=
\min_{E:V\rightarrow\{0,1\}^m\,\text{injective}}
\max_{(u,v)\in\mathcal E} d_H(E(u),E(v)).
$$

The graph families are closed icosphere triangulations and primitive integer directions with symmetric angular nearest-neighbour adjacency. The repository contains their construction, deterministic binary and Gray-code baselines, exact CP-SAT models, scalable search routines, independent witness checks, and the resulting data.

## Results

For the 98-vertex `primitive_q2_knn4` graph at nine bits, Cartesian-coordinate Gray coding has worst local Hamming distance 3, while the exact unrestricted optimum is 2. The complete 42-vertex `icosphere_l1` graph also has optimum 2 at six bits, the minimum injective code length. Nine evaluated graph-length pairs have certified optimum 2; the remaining evaluated cases are retained as lower–upper intervals.

These are finite-graph results for unrestricted lookup-table codebooks. They do not by themselves define an encoder for arbitrary sphere vectors.

## Repository

- `src/sphere_encoding/` — graph construction, encodings, metrics, exact optimisation, and scalable search
- `examples/` — short CP-SAT programs and readable example codebooks
- `configs/` — fixed experiment configurations
- `results/` — accepted tables, arrays, codebooks, and deterministic archives
- `manifests/` — hashes and identities for accepted result packages
- `scripts/` — generation, verification, and reproduction commands
- `tests/` — unit and integration tests

## Running the code

Python 3.11 and [`uv`](https://docs.astral.sh/uv/) are used for the computational environment.

```bash
uv sync --frozen
uv run pytest
uv run python scripts/verify_results.py
```

Small, runnable examples are collected in [`examples/`](examples/):

```bash
uv run python examples/threshold_cpsat.py
uv run python examples/minimax_cpsat.py
```

The verification command checks the accepted archive identities and independently recomputes injectivity and edge Hamming distances for all saved exact witnesses. Re-running the full exact optimisation is substantially more expensive and is kept separate from this lightweight check.

## Next steps

The immediate next step is to extend the search to larger graph and code-length combinations using the scalable optimiser already included here. The subsequent objective is to identify compact, geometry-aware encoders that retain the observed local smoothness without requiring a lookup table.

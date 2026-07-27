# Examples

The two programs below give compact versions of the exact CP-SAT model on the
12-vertex icosahedron.

- [`threshold_cpsat.py`](threshold_cpsat.py) formulates the decision problem:
  does an injective codebook exist whose edge Hamming distances are at most a
  prescribed threshold? It checks thresholds one and two.
- [`minimax_cpsat.py`](minimax_cpsat.py) minimizes the largest edge Hamming
  distance directly.

Run them from the repository root after installing the project environment:

```bash
uv sync --frozen
uv run python examples/threshold_cpsat.py
uv run python examples/minimax_cpsat.py
```

## Example encodings

The [`encodings/`](encodings/) directory contains complete, human-readable
codebooks from the accepted exact results:

- [`icosphere_l0_m4.csv`](encodings/icosphere_l0_m4.csv): 12 directions, four
  bits, worst edge distance two.
- [`primitive_q2_knn4_m9.csv`](encodings/primitive_q2_knn4_m9.csv): 98
  directions, nine bits, worst edge distance two.

Each row gives the canonical vertex index, its unit-vector coordinates, the
codeword written most-significant bit first, and the same codeword as an
integer. The CSV row order matches the graph arrays stored in the accepted
result archive.

# Sphere-Encoding Mini-Study

We represent 290 finite-precision directions on the unit sphere using unique
9-bit codes.

Nearby sphere points should ideally have codes differing in only a few bits.

The study compares:

1. Cartesian binary encoding
2. Cartesian Gray encoding
3. An injective code assignment improved by simulated annealing

The primary score is:

    L_max = the largest Hamming distance between any neighbouring pair

Lower is better.

## Quick run

    uv run python sphere_encoding_study.py --steps 10000 --seeds 1

## Main run

    uv run python sphere_encoding_study.py --steps 100000 --seeds 5

## Larger run

    uv run python sphere_encoding_study.py --steps 1000000 --seeds 20

Results are saved in:

    sphere_encoding_output/

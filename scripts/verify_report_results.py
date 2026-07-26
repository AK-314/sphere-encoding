#!/usr/bin/env python3
"""Verify report claims, accepted archive identities, and Stage 4 witnesses."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.repository_root.resolve()

    manifest_paths = sorted((root / "manifests").glob("stage[234]-*.json"))
    if len(manifest_paths) != 3:
        raise SystemExit("expected exactly three accepted Stage 2-4 manifests")
    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        archive_record = manifest["payload"]["archive"]
        archive_path = root / archive_record["path"]
        if sha256(archive_path) != archive_record["sha256"]:
            raise SystemExit(f"archive hash mismatch: {archive_path}")
        with tarfile.open(archive_path) as archive:
            if len(archive.getmembers()) != int(archive_record["member_count"]):
                raise SystemExit(f"archive member-count mismatch: {archive_path}")

    stage4_manifest = next(path for path in manifest_paths if path.name.startswith("stage4-"))
    stage4 = json.loads(stage4_manifest.read_text(encoding="utf-8"))
    run_id = stage4["payload"]["run_id"]
    bounds_path = root / stage4["payload"]["deterministic_outputs"]["tables"]["paths"]["instance_bounds"]
    bounds = rows(bounds_path)
    exact = [row for row in bounds if row["classification"] == "exact"]
    bounded = [row for row in bounds if row["classification"] == "bounded"]
    if len(bounds) != 21 or len(exact) != 9 or len(bounded) != 12:
        raise SystemExit("Stage 4 classification counts differ from the report")
    if {int(row["final_upper_bound"]) for row in exact} != {2}:
        raise SystemExit("an exact Stage 4 optimum differs from two")

    stage3_path = next((root / "results" / "tables").glob("stage3-*_baseline_summary.csv"))
    stage3 = rows(stage3_path)
    headline = next(
        row
        for row in stage3
        if row["graph_id"] == "primitive_q2_knn4"
        and row["encoding_id"] == "cartesian_coordinate_gray"
    )
    if int(headline["code_length"]) != 9 or int(headline["L_max"]) != 3:
        raise SystemExit("headline Cartesian Gray row differs from the report")

    archive_path = root / stage4["payload"]["archive"]["path"]
    stage2_root = root / "results" / "raw" / "stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50"
    witness_count = 0
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            match = re.fullmatch(
                rf"raw/{re.escape(run_id)}/([^/]+)/m(\d+)/targets/r(\d+)/codebook\.npy",
                member.name,
            )
            if not match:
                continue
            graph_id, code_length, target = match.group(1), int(match.group(2)), int(match.group(3))
            extracted = archive.extractfile(member)
            if extracted is None:
                raise SystemExit(f"could not read witness: {member.name}")
            codebook = np.load(io.BytesIO(extracted.read()), allow_pickle=False)
            edges = np.load(stage2_root / graph_id / "edges.npy", allow_pickle=False)
            if codebook.shape[1] != code_length:
                raise SystemExit(f"witness width mismatch: {member.name}")
            packed = np.packbits(codebook, axis=1)
            if len({bytes(row) for row in packed}) != len(codebook):
                raise SystemExit(f"non-injective witness: {member.name}")
            distances = np.count_nonzero(codebook[edges[:, 0]] != codebook[edges[:, 1]], axis=1)
            if int(distances.max(initial=0)) > target:
                raise SystemExit(f"threshold violation: {member.name}")
            witness_count += 1
    if witness_count != 36:
        raise SystemExit(f"expected 36 validated witnesses, found {witness_count}")

    print("verified Stage 2-4 archive hashes and member counts")
    print("verified 21 Stage 4 classifications: 9 exact and 12 bounded")
    print("verified headline nine-bit Cartesian Gray L_max=3")
    print("independently recomputed all 36 archived Stage 4 witnesses")


if __name__ == "__main__":
    main()

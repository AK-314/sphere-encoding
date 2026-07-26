#!/usr/bin/env python3
"""Regenerate publication-quality report figures from committed artifacts."""

from __future__ import annotations

import argparse
import csv
import io
import math
import tarfile
from itertools import pairwise
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

STAGE2_RUN_ID = "stage2-canonical-graphs-b0acb6e8683a-f2baeb7dbb50"
STAGE3_RUN_ID = "stage3-deterministic-baselines-3fad68b97de9-f07ae893574e"
STAGE4_RUN_ID = "stage4-exact-free-codebook-97021c6cac03-7adb5b49f2cb"

INK = "#14213D"
NAVY = "#0B2545"
BLUE = "#2E74B5"
TEAL = "#2A9D8F"
GOLD = "#E9C46A"
ORANGE = "#F4A261"
RED = "#C44536"
PALE = "#EDF3F8"
GRID = "#CAD5DF"
MUTED = "#5C677D"
WHITE = "#FFFFFF"


def font(size: int, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    suffix = " Bold" if bold else " Italic" if italic else ""
    path = Path(f"/System/Library/Fonts/Supplemental/Arial{suffix}.ttf")
    if not path.exists():
        path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size=size)


def canvas(width: int, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (width, height), WHITE)
    return image, ImageDraw.Draw(image)


def title(draw: ImageDraw.ImageDraw, text: str, width: int, subtitle: str | None = None) -> int:
    draw.text((width // 2, 70), text, font=font(58, bold=True), fill=NAVY, anchor="ma")
    if subtitle:
        draw.text((width // 2, 145), subtitle, font=font(30), fill=MUTED, anchor="ma")
        return 220
    return 165


def rounded_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, fill: str = PALE) -> None:
    draw.rounded_rectangle(box, radius=30, fill=fill, outline=BLUE, width=5)
    x0, y0, x1, y1 = box
    lines = label.split("\n")
    total = len(lines) * 46
    for index, line in enumerate(lines):
        draw.text(((x0 + x1) // 2, (y0 + y1 - total) // 2 + index * 46), line, font=font(34, bold=index == 0), fill=INK, anchor="ma")


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], colour: str = BLUE) -> None:
    draw.line((start, end), fill=colour, width=8)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    for delta in (2.55, -2.55):
        p = (end[0] + 30 * math.cos(angle + delta), end[1] + 30 * math.sin(angle + delta))
        draw.line((end, p), fill=colour, width=8)


def figure1(out: Path) -> None:
    image, draw = canvas(2400, 1200)
    title(draw, "From sphere samples to a locally smooth binary code", 2400)
    boxes = [
        (90, 390, 500, 690, "Sphere\ndiscretisation"),
        (570, 390, 980, 690, "Neighbour\ngraph"),
        (1050, 390, 1460, 690, "Unique binary\ncodewords"),
        (1530, 390, 1940, 690, "Edge Hamming\ndistances"),
        (2010, 390, 2320, 690, "Minimise\nworst edge"),
    ]
    for x0, y0, x1, y1, label in boxes:
        rounded_box(draw, (x0, y0, x1, y1), label)
    for left, right in pairwise(boxes):
        arrow(draw, (left[2] + 15, 540), (right[0] - 15, 540))
    cx, cy, r = 295, 900, 105
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BLUE, width=5)
    draw.arc((cx - r, cy - 45, cx + r, cy + 45), 0, 360, fill=GRID, width=4)
    draw.arc((cx - 45, cy - r, cx + 45, cy + r), 90, 270, fill=GRID, width=4)
    draw.ellipse((190, 835, 206, 851), fill=TEAL)
    draw.ellipse((362, 865, 378, 881), fill=TEAL)
    draw.line((198, 843, 370, 873), fill=TEAL, width=5)
    draw.text((745, 900), "000101", font=font(46, bold=True), fill=NAVY, anchor="mm")
    draw.text((1195, 900), "000111", font=font(46, bold=True), fill=NAVY, anchor="mm")
    arrow(draw, (860, 900), (1070, 900), TEAL)
    draw.text((1520, 900), "dH = 1", font=font(46, bold=True), fill=TEAL, anchor="mm")
    draw.text((2015, 900), "Lmax = maxedge dH", font=font(42, bold=True), fill=NAVY, anchor="mm")
    image.save(out / "figure1_problem_schematic.png", dpi=(300, 300))


def project(vertices: np.ndarray, center: tuple[float, float], scale: float) -> tuple[np.ndarray, np.ndarray]:
    az, el = math.radians(28), math.radians(-18)
    rz = np.array([[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, math.cos(el), -math.sin(el)], [0, math.sin(el), math.cos(el)]])
    rot = vertices @ rz.T @ rx.T
    xy = np.column_stack((center[0] + scale * rot[:, 0], center[1] - scale * rot[:, 1]))
    return xy, rot[:, 2]


def draw_graph(draw: ImageDraw.ImageDraw, vertices: np.ndarray, edges: np.ndarray, center: tuple[int, int], scale: int, node_size: int = 8) -> None:
    xy, depth = project(vertices, center, scale)
    order = np.argsort((depth[edges[:, 0]] + depth[edges[:, 1]]) / 2)
    for edge_index in order:
        u, v = edges[edge_index]
        z = (depth[u] + depth[v]) / 2
        shade = int(176 + 55 * (z + 1) / 2)
        draw.line((*xy[u], *xy[v]), fill=(shade - 20, shade, min(245, shade + 10)), width=3)
    for idx in np.argsort(depth):
        x, y = xy[idx]
        fill = TEAL if depth[idx] >= 0 else "#9CCFC8"
        draw.ellipse((x - node_size, y - node_size, x + node_size, y + node_size), fill=fill, outline=WHITE, width=1)


def figure2(root: Path, out: Path) -> None:
    image, draw = canvas(2400, 1200)
    title(draw, "Canonical full-sphere graph families", 2400, "Actual committed vertices and edges; orthographic renderings")
    graph_root = root / "results" / "raw" / STAGE2_RUN_ID
    panels = [
        ("icosphere_l0", 400, "Icosphere level 0\n12 vertices, 30 edges"),
        ("icosphere_l1", 1200, "Icosphere level 1\n42 vertices, 120 edges"),
        ("primitive_q2_knn4", 2000, "Primitive q=2, k=4\n98 vertices, 264 edges"),
    ]
    for graph_id, cx, label in panels:
        vertices = np.load(graph_root / graph_id / "vertices.npy", allow_pickle=False)
        edges = np.load(graph_root / graph_id / "edges.npy", allow_pickle=False)
        draw_graph(draw, vertices, edges, (cx, 630), 300, node_size=12 if len(vertices) < 50 else 8)
        draw.multiline_text((cx, 1010), label, font=font(34, bold=True), fill=NAVY, anchor="ma", align="center", spacing=10)
    image.save(out / "figure2_graph_families.png", dpi=(300, 300))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def axes(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], x_label: str, y_label: str) -> None:
    x0, y0, x1, y1 = box
    draw.line((x0, y1, x1, y1), fill=INK, width=5)
    draw.line((x0, y0, x0, y1), fill=INK, width=5)
    draw.text(((x0 + x1) // 2, y1 + 105), x_label, font=font(34, bold=True), fill=INK, anchor="mm")
    draw.text((x0 - 140, (y0 + y1) // 2), y_label, font=font(34, bold=True), fill=INK, anchor="mm")


def figure3(root: Path, out: Path) -> None:
    rows = read_csv(root / "results" / "tables" / f"{STAGE3_RUN_ID}_baseline_summary.csv")
    values = []
    for q in (2, 3, 4):
        graph_id = f"primitive_q{q}_knn4"
        row = next(r for r in rows if r["graph_id"] == graph_id and r["encoding_id"] == "cartesian_coordinate_gray")
        values.append((q, int(row["L_max"])))
    image, draw = canvas(2000, 1350)
    title(draw, "Cartesian-coordinate Gray baseline on tested resolutions", 2000)
    box = (300, 260, 1780, 1080)
    axes(draw, box, "Primitive coordinate bound q", "Worst local Hamming distance Lmax")
    for y in range(0, 10, 2):
        py = box[3] - y / 9 * (box[3] - box[1])
        draw.line((box[0], py, box[2], py), fill=GRID, width=2)
        draw.text((box[0] - 35, py), str(y), font=font(30), fill=MUTED, anchor="rm")
    pts = []
    for q, value in values:
        px = box[0] + (q - 1.7) / 2.6 * (box[2] - box[0])
        py = box[3] - value / 9 * (box[3] - box[1])
        pts.append((px, py))
        draw.text((px, box[3] + 45), str(q), font=font(32), fill=INK, anchor="ma")
    draw.line(pts, fill=BLUE, width=9)
    for (px, py), (_, value) in zip(pts, values, strict=True):
        draw.ellipse((px - 18, py - 18, px + 18, py + 18), fill=TEAL, outline=WHITE, width=5)
        draw.text((px, py - 55), str(value), font=font(38, bold=True), fill=NAVY, anchor="ms")
    draw.text((1000, 1260), "Three finite tested resolutions only; no asymptotic trend is inferred.", font=font(30, italic=True), fill=RED, anchor="mm")
    image.save(out / "figure3_cartesian_gray_baseline.png", dpi=(300, 300))


def short_label(graph_id: str, m: str) -> str:
    return f"{graph_id.replace('primitive_', 'prim. ').replace('icosphere_', 'ico. ')}, m={m}"


def figure4(table_dir: Path, out: Path) -> None:
    rows = read_csv(table_dir / "stage4_complete_intervals.csv")
    image, draw = canvas(2600, 2400)
    title(draw, "Stage 4 exact optima and accepted bounds", 2600, "Twenty-one graph-length instances; horizontal bars are unresolved intervals")
    x0, x1, top, bottom = 1150, 2440, 300, 2200
    for value in range(2, 9):
        px = x0 + (value - 2) / 6 * (x1 - x0)
        draw.line((px, top, px, bottom), fill=GRID, width=2)
        draw.text((px, bottom + 55), str(value), font=font(30), fill=INK, anchor="ma")
    draw.text(((x0 + x1) // 2, bottom + 125), "Worst local Hamming distance", font=font(34, bold=True), fill=INK, anchor="ma")
    row_h = (bottom - top) / len(rows)
    for index, row in enumerate(rows):
        y = top + (index + 0.5) * row_h
        if index and row["graph_id"] != rows[index - 1]["graph_id"]:
            draw.line((110, y - row_h / 2, x1, y - row_h / 2), fill="#E2E8EF", width=2)
        draw.text((1100, y), short_label(row["graph_id"], row["code_length"]), font=font(27), fill=INK, anchor="rm")
        lo, hi = int(row["lower_bound"]), int(row["upper_bound"])
        px0 = x0 + (lo - 2) / 6 * (x1 - x0)
        px1 = x0 + (hi - 2) / 6 * (x1 - x0)
        if lo == hi:
            draw.ellipse((px0 - 14, y - 14, px0 + 14, y + 14), fill=TEAL, outline=WHITE, width=3)
        else:
            draw.line((px0, y, px1, y), fill=GOLD, width=12)
            draw.ellipse((px0 - 11, y - 11, px0 + 11, y + 11), fill=WHITE, outline=ORANGE, width=4)
            draw.ellipse((px1 - 13, y - 13, px1 + 13, y + 13), fill=ORANGE, outline=WHITE, width=3)
    draw.ellipse((350, 2315, 378, 2343), fill=TEAL)
    draw.text((395, 2329), "exact", font=font(28), fill=INK, anchor="lm")
    draw.line((600, 2329, 700, 2329), fill=GOLD, width=12)
    draw.ellipse((687, 2316, 713, 2342), fill=ORANGE)
    draw.text((735, 2329), "bounded interval", font=font(28), fill=INK, anchor="lm")
    image.save(out / "figure4_stage4_intervals.png", dpi=(300, 300))


def figure5(table_dir: Path, out: Path) -> None:
    rows = read_csv(table_dir / "table5_headline_same_rate_comparison.csv")
    image, draw = canvas(1800, 1300)
    title(draw, "Same graph, same nine-bit rate", 1800, "primitive_q2_knn4: 98 sphere points and 264 neighbour edges")
    base_y, top_y = 1050, 310
    for value in range(5):
        py = base_y - value / 4 * (base_y - top_y)
        draw.line((250, py, 1650, py), fill=GRID, width=2)
        draw.text((210, py), str(value), font=font(30), fill=MUTED, anchor="rm")
    positions = [590, 1210]
    colours = [BLUE, TEAL]
    labels = ["Cartesian-coordinate\nGray", "Exact unrestricted\noptimum"]
    for row, px, colour, label in zip(rows, positions, colours, labels, strict=True):
        value = int(row["L_max"])
        py = base_y - value / 4 * (base_y - top_y)
        draw.rounded_rectangle((px - 180, py, px + 180, base_y), radius=18, fill=colour)
        draw.text((px, py - 45), str(value), font=font(62, bold=True), fill=NAVY, anchor="ms")
        draw.multiline_text((px, base_y + 55), label, font=font(34, bold=True), fill=INK, anchor="ma", align="center", spacing=8)
    draw.text((900, 1225), "Strict reduction in worst local bit flips: 3 to 2", font=font(36, bold=True), fill=RED, anchor="mm")
    image.save(out / "figure5_same_rate_comparison.png", dpi=(300, 300))


def figure6(table_dir: Path, out: Path) -> None:
    rows = [r for r in read_csv(table_dir / "table3_exact_stage4_optima.csv") if r["graph_id"] in {"icosphere_l0", "icosphere_l1"}]
    image, draw = canvas(2200, 1350)
    title(draw, "Exact unrestricted optima on complete icospheres", 2200, "All tested code lengths attain L*free = 2")
    box = (300, 300, 2040, 1050)
    axes(draw, box, "Code length m", "Exact optimum")
    for y in (0, 1, 2, 3, 4):
        py = box[3] - y / 4 * (box[3] - box[1])
        draw.line((box[0], py, box[2], py), fill=GRID, width=2)
        draw.text((box[0] - 35, py), str(y), font=font(30), fill=MUTED, anchor="rm")
    for graph_id, colour, offset in (("icosphere_l0", BLUE, -14), ("icosphere_l1", TEAL, 14)):
        group = [r for r in rows if r["graph_id"] == graph_id]
        pts = []
        for row in group:
            m = int(row["code_length"])
            px = box[0] + (m - 3.5) / 7 * (box[2] - box[0]) + offset
            py = box[3] - 2 / 4 * (box[3] - box[1])
            pts.append((px, py))
            draw.text((px, box[3] + 42), str(m), font=font(28), fill=INK, anchor="ma")
        draw.line(pts, fill=colour, width=7)
        for px, py in pts:
            draw.ellipse((px - 15, py - 15, px + 15, py + 15), fill=colour, outline=WHITE, width=4)
    draw.rectangle((460, 1165, 500, 1205), fill=BLUE)
    draw.text((525, 1185), "icosphere_l0 (minimum m=4)", font=font(30), fill=INK, anchor="lm")
    draw.rectangle((1240, 1165, 1280, 1205), fill=TEAL)
    draw.text((1305, 1185), "icosphere_l1 (minimum m=6)", font=font(30), fill=INK, anchor="lm")
    image.save(out / "figure6_icosphere_exact_results.png", dpi=(300, 300))


def figure7(out: Path) -> None:
    image, draw = canvas(2500, 1200)
    title(draw, "Deterministic Stage 5 scalable-search architecture", 2500, "Implementation status only; definitive scientific workload remains pending")
    labels = [
        "Initial\ncodebook",
        "Swap or\nreplacement",
        "Incremental\nedge update",
        "Lexicographic\nscore",
        "Deterministic\nacceptance",
        "Checkpoint\nand replay",
        "Validated\nwitness",
    ]
    w, gap, x, y0, y1 = 280, 55, 85, 430, 720
    for index, label in enumerate(labels):
        fill = "#E8F4F2" if index in (0, 6) else PALE
        rounded_box(draw, (x, y0, x + w, y1), label, fill=fill)
        if index < len(labels) - 1:
            arrow(draw, (x + w + 8, (y0 + y1) // 2), (x + w + gap - 8, (y0 + y1) // 2))
        x += w + gap
    draw.text((1250, 925), "Injectivity is preserved throughout; replay independently recomputes every accepted move.", font=font(34), fill=NAVY, anchor="mm")
    image.save(out / "figure7_stage5_architecture.png", dpi=(300, 300))


def colour_for_code(value: int, maximum: int) -> tuple[int, int, int]:
    t = value / max(1, maximum)
    a = np.array([42, 157, 143])
    b = np.array([233, 196, 106])
    c = np.array([196, 69, 54])
    rgb = (1 - 2 * t) * a + 2 * t * b if t <= 0.5 else (2 - 2 * t) * b + (2 * t - 1) * c
    return tuple(int(v) for v in rgb)


def figure8(root: Path, out: Path) -> None:
    graph_root = root / "results" / "raw" / STAGE2_RUN_ID / "icosphere_l1"
    vertices = np.load(graph_root / "vertices.npy", allow_pickle=False)
    edges = np.load(graph_root / "edges.npy", allow_pickle=False)
    archive = root / "results" / "archives" / f"{STAGE4_RUN_ID}.tar.gz"
    member = f"raw/{STAGE4_RUN_ID}/icosphere_l1/m6/targets/r2/codebook.npy"
    with tarfile.open(archive) as handle:
        extracted = handle.extractfile(member)
        if extracted is None:
            raise FileNotFoundError(member)
        codebook = np.load(io.BytesIO(extracted.read()), allow_pickle=False)
    values = codebook.dot(1 << np.arange(codebook.shape[1] - 1, -1, -1))
    distances = np.count_nonzero(codebook[edges[:, 0]] != codebook[edges[:, 1]], axis=1)

    image, draw = canvas(2400, 1450)
    title(draw, "One accepted exact six-bit codebook on icosphere_l1", 2400, "The displayed assignment is a witness, not a unique or canonical labelling")
    xy, depth = project(vertices, (720, 800), 470)
    for edge_index in np.argsort((depth[edges[:, 0]] + depth[edges[:, 1]]) / 2):
        u, v = edges[edge_index]
        draw.line((*xy[u], *xy[v]), fill="#B9C7D4", width=4)
    for idx in np.argsort(depth):
        x, y = xy[idx]
        draw.ellipse((x - 18, y - 18, x + 18, y + 18), fill=colour_for_code(int(values[idx]), 63), outline=WHITE, width=3)
    draw.text((720, 1320), "Vertices coloured by six-bit code value", font=font(32, bold=True), fill=NAVY, anchor="mm")

    counts = {d: int(np.count_nonzero(distances == d)) for d in sorted(set(distances.tolist()))}
    left, right, top, base = 1500, 2220, 420, 1120
    draw.text(((left + right) // 2, 330), "Edge Hamming-distance histogram", font=font(38, bold=True), fill=NAVY, anchor="mm")
    max_count = max(counts.values())
    for pos, (d, count) in enumerate(counts.items()):
        cx = left + 170 + pos * 300
        py = base - count / max_count * (base - top)
        draw.rounded_rectangle((cx - 100, py, cx + 100, base), radius=16, fill=TEAL if d <= 2 else RED)
        draw.text((cx, py - 35), str(count), font=font(36, bold=True), fill=NAVY, anchor="ms")
        draw.text((cx, base + 45), f"dH={d}", font=font(32), fill=INK, anchor="ma")
    draw.text(((left + right) // 2, 1250), f"All {len(edges)} graph edges satisfy dH <= {int(distances.max())}.", font=font(34, bold=True), fill=TEAL, anchor="mm")
    image.save(out / "figure8_example_exact_codebook.png", dpi=(300, 300))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--table-dir", type=Path)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    out = (args.output_dir or root / "results" / "figures" / "report").resolve()
    table_dir = (args.table_dir or root / "results" / "tables" / "report").resolve()
    out.mkdir(parents=True, exist_ok=True)
    figure1(out)
    figure2(root, out)
    figure3(root, out)
    figure4(table_dir, out)
    figure5(table_dir, out)
    figure6(table_dir, out)
    figure7(out)
    figure8(root, out)
    print(f"wrote 8 report figures to {out}")


if __name__ == "__main__":
    main()

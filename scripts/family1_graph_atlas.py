#!/usr/bin/env python3
"""Build exact SVG drawings and an offline atlas of Family 1 graph candidates.

Uses the Python standard library. --png additionally requires matplotlib, e.g.
uv run --with matplotlib python scripts/family1_graph_atlas.py --input RUN --out ATLAS --png
Input may be JSONL files or directories containing champions/maximizers exports.
Every supplied graph is retained; the gallery initially shows ALL ties for the
largest certified lower bound at each size. No heuristic search becomes a proof
of global maximality through this presentation layer.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
from html import escape
import json
import math
from pathlib import Path
import random


WIDTH, HEIGHT = 520, 450
PORT_COLORS = ("#2563b7", "#dd6b20")
PREFERRED_EXPORTS = ("champions.jsonl", "maximizers.jsonl", "best_lower_bound.jsonl", "graphs.jsonl")


def input_file(path: Path) -> Path:
    if path.is_file():
        return path
    for name in PREFERRED_EXPORTS:
        if (path / name).is_file():
            return path / name
    raise ValueError(f"No graph export found in {path}")


def load_summary(path: Path) -> dict:
    summary = path.parent / "summary.json"
    return json.loads(summary.read_text(encoding="utf-8-sig")) if summary.is_file() else {}


def coverage(record: dict, summary: dict) -> tuple[bool, bool]:
    """Use explicit certificates only; graph size alone never proves coverage."""
    matching = next((item for item in summary.get("sizes", []) if item.get("m") == record["m"]), {})
    exhaustive = matching.get("enumeration_complete") is True
    certified = matching.get("maximum_certified") is True or (
        matching.get("maximum_value_certified") is True and matching.get("maximizing_collection_complete") is True)
    maximum = matching.get("maximum_merge_length", matching.get("maximum_value", matching.get("maximum")))
    proved_maximum = certified and type(maximum) is int and maximum == record.get("merge_length") and record.get("status") == "exact"
    return exhaustive, proved_maximum


def normalize(raw: dict, source: Path, summary: dict) -> dict:
    record = deepcopy(raw)
    m = record.get("m")
    table = record.get("canonical_table", record.get("table"))
    if type(m) is not int or not 1 <= m <= 20 or not isinstance(table, list) or len(table) != m:
        raise ValueError(f"Invalid graph size/table in {source}")
    if any(not isinstance(row, list) or len(row) != 2 or
           any(not isinstance(target, int) or isinstance(target, bool) or not 0 <= target < m for target in row)
           for row in table):
        raise ValueError(f"Invalid successor in {source}")
    key = "".join(f"{target:02d}" for row in table for target in row)
    lower = record.get("lower_bound", record.get("merge_length", 1))
    upper = record.get("upper_bound")
    if record.get("status") == "exact":
        upper = record.get("merge_length", upper)
        lower = upper
    if not isinstance(lower, int) or isinstance(lower, bool) or lower < 1:
        raise ValueError(f"Invalid certified lower bound in {source}")
    if upper is not None and (not isinstance(upper, int) or isinstance(upper, bool) or upper < lower):
        raise ValueError(f"Invalid certified upper bound in {source}")
    witness = record.get("witness")
    if upper is not None:
        if (not isinstance(witness, list) or len(witness) != 2 or witness[0] == witness[1]
                or any(not isinstance(word, str) or len(word) != upper or set(word) - {"0", "1"} for word in witness)):
            raise ValueError(f"Missing/invalid collision witness in {source}")
    exhaustive, proved_maximum = coverage(record, summary)
    return {"m": m, "key": key, "canonical_table": table,
            "lower_bound": lower, "upper_bound": upper,
            "merge_length": upper if lower == upper else None,
            "status": "exact" if lower == upper else "bounded" if upper is not None else "lower-bound",
            "witness": witness if upper is not None else None,
            "enumeration_complete": exhaustive, "maximum_certified": proved_maximum,
            "sources": [str(source)], "original_keys": [record.get("key", key)],
            "source_statuses": [record.get("status", "unknown")]}


def load_records(paths: list[Path]) -> list[dict]:
    merged = {}
    for supplied in paths:
        source = input_file(supplied)
        summary = load_summary(source)
        for line_number, line in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            try:
                incoming = normalize(json.loads(line), source, summary)
            except (ValueError, TypeError, KeyError) as error:
                raise ValueError(f"{source}:{line_number}: {error}") from error
            identity = incoming["m"], incoming["key"]
            if identity not in merged:
                merged[identity] = incoming
                continue
            existing = merged[identity]
            existing["lower_bound"] = max(existing["lower_bound"], incoming["lower_bound"])
            if incoming["upper_bound"] is not None and (existing["upper_bound"] is None or incoming["upper_bound"] < existing["upper_bound"]):
                existing["upper_bound"] = incoming["upper_bound"]
                existing["witness"] = incoming["witness"]
            if existing["upper_bound"] is not None and existing["lower_bound"] > existing["upper_bound"]:
                raise ValueError(f"Contradictory certificates for m={identity[0]} graph {identity[1]}")
            existing["enumeration_complete"] |= incoming["enumeration_complete"]
            existing["maximum_certified"] |= incoming["maximum_certified"]
            for field in ("sources", "original_keys", "source_statuses"):
                existing[field] = sorted(set(existing[field] + incoming[field]))
            lower, upper = existing["lower_bound"], existing["upper_bound"]
            existing["status"] = "exact" if lower == upper else "bounded" if upper is not None else "lower-bound"
            existing["merge_length"] = upper if lower == upper else None
    records = [merged[key] for key in sorted(merged)]
    if not records:
        raise ValueError("No graph records supplied")
    best = defaultdict(int)
    for record in records:
        best[record["m"]] = max(best[record["m"]], record["lower_bound"])
    for record in records:
        record["best_bound_tie"] = record["lower_bound"] == best[record["m"]]
    return records


def score_label(record: dict, ascii_only: bool = False) -> str:
    lower, upper = record["lower_bound"], record["upper_bound"]
    if lower == upper:
        return f"H = {lower}"
    if upper is not None:
        return f"{lower} <= H <= {upper}" if ascii_only else f"{lower} ≤ H ≤ {upper}"
    return f"H >= {lower}" if ascii_only else f"H ≥ {lower}"


def layout(record: dict) -> list[tuple[float, float]]:
    """Deterministic small-graph spring layout, with overlap-safe circle fallback."""
    m = record["m"]
    if m == 1:
        return [(WIDTH / 2, HEIGHT / 2 + 8)]
    seed = int(hashlib.sha256(record["key"].encode()).hexdigest()[:16], 16)
    random_source = random.Random(seed)
    positions = [[150 * math.cos(-math.pi / 2 + 2 * math.pi * s / m) + random_source.uniform(-4, 4),
                  150 * math.sin(-math.pi / 2 + 2 * math.pi * s / m) + random_source.uniform(-4, 4)] for s in range(m)]
    edges = sorted({tuple(sorted((s, target))) for s, row in enumerate(record["canonical_table"]) for target in row if s != target})
    k = math.sqrt(125000 / m) * 0.65
    for iteration in range(420):
        forces = [[-0.025 * x, -0.025 * y] for x, y in positions]
        for a in range(m):
            for b in range(a + 1, m):
                dx, dy = positions[a][0] - positions[b][0], positions[a][1] - positions[b][1]
                distance = max(0.1, math.hypot(dx, dy))
                force = k * k / distance
                fx, fy = force * dx / distance, force * dy / distance
                forces[a][0] += fx; forces[a][1] += fy
                forces[b][0] -= fx; forces[b][1] -= fy
        for a, b in edges:
            dx, dy = positions[a][0] - positions[b][0], positions[a][1] - positions[b][1]
            distance = max(0.1, math.hypot(dx, dy))
            force = distance * distance / k
            fx, fy = force * dx / distance, force * dy / distance
            forces[a][0] -= fx; forces[a][1] -= fy
            forces[b][0] += fx; forces[b][1] += fy
        temperature = 20 * (1 - iteration / 420) + 0.25
        for s in range(m):
            force = max(0.1, math.hypot(*forces[s]))
            positions[s][0] += forces[s][0] / force * min(temperature, force)
            positions[s][1] += forces[s][1] / force * min(temperature, force)
    center = [sum(p[axis] for p in positions) / m for axis in (0, 1)]
    angle = -math.pi / 2 - math.atan2(positions[0][1] - center[1], positions[0][0] - center[0])
    positions = [[(x - center[0]) * math.cos(angle) - (y - center[1]) * math.sin(angle),
                  (x - center[0]) * math.sin(angle) + (y - center[1]) * math.cos(angle)] for x, y in positions]
    span_x = max(p[0] for p in positions) - min(p[0] for p in positions)
    span_y = max(p[1] for p in positions) - min(p[1] for p in positions)
    scale = min((WIDTH - 140) / max(span_x, 1), (HEIGHT - 155) / max(span_y, 1))
    midpoint = [(min(p[axis] for p in positions) + max(p[axis] for p in positions)) / 2 for axis in (0, 1)]
    result = [(WIDTH / 2 + (x - midpoint[0]) * scale, HEIGHT / 2 + 12 + (y - midpoint[1]) * scale) for x, y in positions]
    if any(math.dist(result[a], result[b]) < 39 for a in range(m) for b in range(a + 1, m)):
        radius = (HEIGHT - 155) / 2
        result = [(WIDTH / 2 + radius * math.cos(-math.pi / 2 + 2 * math.pi * s / m),
                   HEIGHT / 2 + 12 + radius * math.sin(-math.pi / 2 + 2 * math.pi * s / m)) for s in range(m)]
    return result


def point(center: tuple[float, float], angle: float, distance: float) -> tuple[float, float]:
    return center[0] + math.cos(angle) * distance, center[1] + math.sin(angle) * distance


def edge_geometry(record: dict, positions: list[tuple[float, float]]) -> list[dict]:
    table = record["canonical_table"]
    result = []
    for source, row in enumerate(table):
        for port, target in enumerate(row):
            start, end = positions[source], positions[target]
            source_radius, target_radius = (18 if source == 0 else 15), (18 if target == 0 else 15)
            if source == target:
                outward = math.atan2(start[1] - HEIGHT / 2, start[0] - WIDTH / 2)
                if record["m"] == 1:
                    outward = -math.pi / 2
                angle = outward + (-0.7 if port == 0 else 0.7)
                points = [point(start, angle - 0.48, source_radius + 1), point(start, angle - 0.9, source_radius + 48),
                          point(start, angle + 0.9, source_radius + 48), point(start, angle + 0.48, source_radius + 5)]
                label = (sum(p[0] * weight for p, weight in zip(points, (0.125, 0.375, 0.375, 0.125))),
                         sum(p[1] * weight for p, weight in zip(points, (0.125, 0.375, 0.375, 0.125))))
                kind = "cubic"
            else:
                dx, dy = end[0] - start[0], end[1] - start[1]
                length = math.hypot(dx, dy)
                normal = -dy / length, dx / length
                parallel = row[0] == row[1]
                reverse = source in table[target]
                bend = ((15 + 22 * port) if reverse else (-18 if port == 0 else 18)) if parallel else (20 if reverse else (8 if port == 0 else -8))
                control = (start[0] + end[0]) / 2 + normal[0] * bend, (start[1] + end[1]) / 2 + normal[1] * bend
                start_angle = math.atan2(control[1] - start[1], control[0] - start[0])
                end_angle = math.atan2(control[1] - end[1], control[0] - end[0])
                points = [point(start, start_angle, source_radius + 1), control, point(end, end_angle, target_radius + 5)]
                label = ((points[0][0] + 2 * control[0] + points[2][0]) / 4 + normal[0] * 5,
                         (points[0][1] + 2 * control[1] + points[2][1]) / 4 + normal[1] * 5)
                kind = "quadratic"
            result.append({"source": source, "target": target, "port": port, "kind": kind, "points": points, "label": label})
    return result


def graph_svg(record: dict, positions: list[tuple[float, float]] | None = None) -> str:
    positions = positions or layout(record)
    graph_id = f"m{record['m']}_{record['key']}"
    metadata = escape(json.dumps({k: record[k] for k in ("m", "key", "canonical_table", "status", "lower_bound", "upper_bound", "witness", "maximum_certified")}))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="Family 1 graph with {record["m"]} states">',
             f'<title>m={record["m"]}; {escape(score_label(record))}</title><metadata>{metadata}</metadata>',
             '<rect width="100%" height="100%" rx="14" fill="#fff"/>',
             '<defs>']
    for port, color in enumerate(PORT_COLORS):
        parts.append(f'<marker id="{graph_id}_arrow{port}" markerWidth="9" markerHeight="8" refX="8" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 Z" fill="{color}"/></marker>')
    parts += ['</defs>', f'<text x="22" y="29" font-family="Arial,sans-serif" font-size="19" font-weight="700" fill="#15293b">m = {record["m"]} · {escape(score_label(record))}</text>']
    badge = "PROVED MAXIMUM · complete maximizing collection" if record["maximum_certified"] else "UNRESOLVED GLOBAL MAXIMUM · certified candidate only"
    parts.append(f'<text x="22" y="49" font-family="Arial,sans-serif" font-size="12" fill="{("#247459" if record["maximum_certified"] else "#95611c")}">{badge}</text>')
    for edge in edge_geometry(record, positions):
        points = edge["points"]
        command = "C" if edge["kind"] == "cubic" else "Q"
        path = f'M {points[0][0]:.3f},{points[0][1]:.3f} {command} ' + " ".join(f"{x:.3f},{y:.3f}" for x, y in points[1:])
        port, source, target = edge["port"], edge["source"], edge["target"]
        dash = ' stroke-dasharray="6 4"' if port else ""
        parts.append(f'<path class="edge" data-source="{source}" data-target="{target}" data-port="{port}" d="{path}" fill="none" stroke="{PORT_COLORS[port]}" stroke-width="2.1"{dash} marker-end="url(#{graph_id}_arrow{port})"/>')
        x, y = edge["label"]
        parts.append(f'<text x="{x:.3f}" y="{y + 4:.3f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="11" font-weight="700" fill="{PORT_COLORS[port]}" stroke="#fff" stroke-width="4" paint-order="stroke">{port}</text>')
    for state, (x, y) in enumerate(positions):
        radius = 18 if state == 0 else 15
        fill = "#e3f2ed" if state == 0 else "#f5f8fb"
        parts.append(f'<g class="node" data-state="{state}"><circle cx="{x:.3f}" cy="{y:.3f}" r="{radius}" fill="{fill}" stroke="#314858" stroke-width="1.6"/>')
        if state == 0:
            parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="14" fill="none" stroke="#314858" stroke-width="1.2"/>')
        parts.append(f'<text x="{x:.3f}" y="{y + 4.5:.3f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" font-weight="600" fill="#15293b">{state}</text></g>')
    parts += ['<text x="22" y="432" font-family="Arial,sans-serif" font-size="11" fill="#526572">Root: double circle</text>',
              '<text x="220" y="432" font-family="Arial,sans-serif" font-size="11" fill="#2563b7">τ0: blue solid</text>',
              '<text x="355" y="432" font-family="Arial,sans-serif" font-size="11" fill="#dd6b20">τ1: orange dashed</text>', '</svg>']
    return "\n".join(parts)


def contact_sheet(records: list[dict], svgs: list[str], columns: int = 4) -> str:
    columns = min(columns, len(records))
    cell_width, cell_height, header = 300, 280, 95
    rows = math.ceil(len(records) / columns)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{columns * cell_width}" height="{header + rows * cell_height}" viewBox="0 0 {columns * cell_width} {header + rows * cell_height}">',
             '<rect width="100%" height="100%" fill="#edf2f5"/>',
             '<text x="22" y="30" font-family="Arial,sans-serif" font-size="22" font-weight="700" fill="#15293b">Family 1 graph atlas</text>',
             f'<text x="22" y="53" font-family="Arial,sans-serif" font-size="13" fill="#425768">All {len(records)} supplied distinct graphs · {sum(r["best_bound_tie"] for r in records)} tied best-bound candidates</text>',
             '<text x="22" y="74" font-family="Arial,sans-serif" font-size="12" fill="#425768">Exact H and certified lower bounds are different. Candidate searches do not prove global maxima.</text>']
    for index, (record, svg) in enumerate(zip(records, svgs)):
        x, y = index % columns * cell_width + 5, header + index // columns * cell_height
        inside = svg[svg.find(">") + 1:svg.rfind("</svg>")]
        parts.append(f'<svg x="{x}" y="{y}" width="290" height="251" viewBox="0 0 {WIDTH} {HEIGHT}">{inside}</svg>')
        label = "tied best bound" if record["best_bound_tie"] else "earlier/weaker bound"
        parts.append(f'<text x="{x + 12}" y="{y + 267}" font-family="Arial,sans-serif" font-size="10" fill="#536777">{label} · {record["key"][:28]}{"…" if len(record["key"]) > 28 else ""}</text>')
    parts.append('</svg>')
    return "\n".join(parts)


def png_sheet(records: list[dict], positions: list[list[tuple[float, float]]], destination: Path, columns: int = 4) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Circle, FancyArrowPatch
        from matplotlib.path import Path as MplPath
    except ImportError as error:
        raise RuntimeError("--png requires matplotlib: uv run --with matplotlib python scripts/family1_graph_atlas.py ... --png") from error
    columns = min(columns, len(records))
    rows = math.ceil(len(records) / columns)
    figure, axes = plt.subplots(rows, columns, figsize=(columns * 3.2, rows * 2.95 + 0.7), squeeze=False)
    figure.patch.set_facecolor("#edf2f5")
    heading = ("Family 1 graph atlas\nScores and certified bounds" if columns == 1 else
               "Family 1 graph atlas · every supplied graph\nExact scores and certified lower bounds shown separately")
    figure.suptitle(heading, fontsize=12 if columns == 1 else 13, y=0.997)
    for index, axis in enumerate(axes.flat):
        axis.set_xlim(0, WIDTH); axis.set_ylim(HEIGHT, 0); axis.set_aspect("equal"); axis.axis("off")
        if index >= len(records):
            continue
        record, node_positions = records[index], positions[index]
        for edge in edge_geometry(record, node_positions):
            codes = [MplPath.MOVETO] + ([MplPath.CURVE4] * 3 if edge["kind"] == "cubic" else [MplPath.CURVE3] * 2)
            axis.add_patch(FancyArrowPatch(path=MplPath(edge["points"], codes), arrowstyle="-|>", mutation_scale=8,
                                          linewidth=0.8, color=PORT_COLORS[edge["port"]], linestyle="--" if edge["port"] else "-"))
            x, y = edge["label"]
            axis.text(x, y, str(edge["port"]), fontsize=5, color=PORT_COLORS[edge["port"]], ha="center", va="center",
                      bbox={"boxstyle": "round,pad=.04", "facecolor": "white", "edgecolor": "none", "alpha": .9})
        for state, (x, y) in enumerate(node_positions):
            axis.add_patch(Circle((x, y), 18 if state == 0 else 15, facecolor="#e3f2ed" if state == 0 else "#f5f8fb", edgecolor="#314858", linewidth=.7))
            if state == 0:
                axis.add_patch(Circle((x, y), 14, fill=False, edgecolor="#314858", linewidth=.5))
            axis.text(x, y, str(state), fontsize=6, fontweight="bold", ha="center", va="center", color="#15293b")
        axis.text(18, 24, f'm = {record["m"]} · {score_label(record)}', fontsize=8.5, fontweight="bold", color="#15293b")
        axis.text(18, 46, "PROVED MAXIMUM" if record["maximum_certified"] else "UNRESOLVED GLOBAL MAXIMUM", fontsize=6.5,
                  color="#247459" if record["maximum_certified"] else "#95611c")
    figure.subplots_adjust(left=.01, right=.99, top=1 - .8 / (rows * 2.95 + .7), bottom=.005, wspace=.03, hspace=.06)
    figure.savefig(destination, dpi=150, facecolor=figure.get_facecolor())
    plt.close(figure)


def html_gallery(records: list[dict], svgs: list[str]) -> str:
    payload = json.dumps([dict(record, svg=svg) for record, svg in zip(records, svgs)], separators=(",", ":")).replace("<", "\\u003c")
    return r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Family 1 graph atlas</title><style>
:root{font-family:system-ui,sans-serif;color:#183044;background:#edf2f5}*{box-sizing:border-box}body{margin:0}main{max-width:1540px;margin:auto;padding:28px}h1{font-size:30px;margin:0 0 8px}.lead{max-width:1000px;color:#4f6576;line-height:1.55}.controls{display:flex;gap:18px;align-items:center;flex-wrap:wrap;background:white;border-radius:12px;padding:16px;margin:22px 0;position:sticky;top:0;z-index:2;box-shadow:0 2px 8px #17304312}select{font:inherit;padding:8px;border:1px solid #c6d3dc;border-radius:7px}#count{font-weight:600}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px}.card{background:white;border-radius:14px;overflow:hidden;border:1px solid #d9e2e8}.card svg{width:100%;height:auto;display:block}.details{padding:0 20px 18px;font-size:13px;color:#506576}.key{font:11px ui-monospace,monospace;overflow-wrap:anywhere;color:#647b8c}.badge{display:inline-block;border-radius:5px;padding:4px 7px;margin:0 5px 7px 0;background:#fff1d7;color:#875612}.proved{background:#def1e9;color:#256e55}.exact{background:#e4edf9;color:#245c96}summary{cursor:pointer;padding:5px 0;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}a{color:#2563b7}#coverage{margin:-8px 0 20px;color:#506576}.empty{padding:40px;background:white;border-radius:12px}</style>
<main><h1>Family 1 graph atlas</h1><p class="lead">Each graph is one rooted seed with two outgoing ports. Blue solid edges are τ0; orange dashed edges are τ1. The root is a double circle. A bound H ≥ d proves there is no equal-length merge before d; it does not assert an exact score or a global maximum. Every supplied graph is preserved, including every tied candidate.</p>
<p><a href="contact-sheet.svg">All-graph contact sheet (SVG)</a> · <a href="graphs.jsonl">Graph tables and score certificates</a> · <a href="manifest.json">Atlas coverage manifest</a></p>
<div class="controls"><label>Reachable states <select id="size"></select></label><label>Collection <select id="collection"><option value="best">All ties at best certified bound</option><option value="all">Every supplied graph</option></select></label><span id="count"></span></div><div id="coverage"></div><div id="gallery" class="grid"></div></main>
<script id="atlas-data" type="application/json">''' + payload + r'''</script><script>
const records=JSON.parse(document.getElementById('atlas-data').textContent),size=document.getElementById('size'),collection=document.getElementById('collection'),gallery=document.getElementById('gallery');
for(let m=1;m<=20;m++){const option=document.createElement('option');option.value=m;option.textContent=`m = ${m}`;size.appendChild(option)}
const initial=records.some(r=>r.m===20)?20:records[0].m;size.value=initial;
function text(tag,value,className){const element=document.createElement(tag);element.textContent=value;if(className)element.className=className;return element}
function update(){const m=Number(size.value),all=records.filter(r=>r.m===m),selected=all.filter(r=>collection.value==='all'||r.best_bound_tie);gallery.replaceChildren();document.getElementById('count').textContent=`${selected.length} graph${selected.length===1?'':'s'} shown · ${all.length} supplied`;
document.getElementById('coverage').textContent=all.some(r=>r.maximum_certified)?'PROVED: exhaustive enumeration and exact scoring certify the maximum and complete maximizing collection shown for this size.':'UNRESOLVED: the global maximum and full maximizing collection are not proved. Individual scores and bounds are certified by the source computation.';
for(const r of selected){const card=document.createElement('article');card.className='card';const picture=document.createElement('div');picture.innerHTML=r.svg;card.appendChild(picture);const details=document.createElement('div');details.className='details';details.appendChild(text('span',r.status==='exact'?'Exact graph score':'Certified interval / lower bound','badge exact'));details.appendChild(text('span',r.maximum_certified?'Proved global maximizer':'Global maximality unproved',r.maximum_certified?'badge proved':'badge'));if(r.best_bound_tie)details.appendChild(text('span','Tied best certified bound','badge'));details.appendChild(text('div',r.key,'key'));const download=document.createElement('a');download.href=`svg/m${r.m}_${r.key}.svg`;download.textContent='Standalone SVG';details.appendChild(download);const fold=document.createElement('details');fold.appendChild(text('summary','Transition table, witness and provenance'));fold.appendChild(text('pre',JSON.stringify({canonical_table:r.canonical_table,witness:r.witness,sources:r.sources},null,2)));details.appendChild(fold);card.appendChild(details);gallery.appendChild(card)}if(!selected.length)gallery.appendChild(text('div','No graphs supplied for this size.','empty'));}
size.addEventListener('change',update);collection.addEventListener('change',update);update();</script></html>'''


def build_atlas(paths: list[Path], destination: Path, png: bool = False) -> dict:
    records = load_records(paths)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "svg").mkdir(exist_ok=True)
    positions = [layout(record) for record in records]
    svgs = [graph_svg(record, nodes) for record, nodes in zip(records, positions)]
    for record, svg in zip(records, svgs):
        (destination / "svg" / f'm{record["m"]}_{record["key"]}.svg').write_text(svg + "\n", encoding="utf-8")
    (destination / "graphs.jsonl").write_text("".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records), encoding="utf-8")
    (destination / "contact-sheet.svg").write_text(contact_sheet(records, svgs) + "\n", encoding="utf-8")
    (destination / "index.html").write_text(html_gallery(records, svgs), encoding="utf-8")
    sizes = []
    for m in range(1, 21):
        selected = [record for record in records if record["m"] == m]
        sizes.append({"m": m, "graphs": len(selected), "best_bound_ties": sum(record["best_bound_tie"] for record in selected),
                      "largest_certified_lower_bound": max((record["lower_bound"] for record in selected), default=None),
                      "maximum_certified": any(record["maximum_certified"] for record in selected)})
    manifest = {"schema": 1, "graphs": len(records), "svg_files": len(svgs), "sources": [str(path) for path in paths],
                "drawing": "one node per state, both directed ports retained; deterministic spring layout with overlap-safe fallback",
                "graph_coverage": "per-source certificates only; larger candidate searches are not exhaustive", "sizes": sizes}
    if png:
        png_sheet(records, positions, destination / "contact-sheet.png")
        manifest["png"] = "contact-sheet.png"
        largest = max(record["m"] for record in records)
        selected = [index for index, record in enumerate(records) if record["m"] == largest and record["best_bound_tie"]]
        png_sheet([records[index] for index in selected], [positions[index] for index in selected], destination / f"m{largest}-best-candidates.png")
        manifest["largest_size_preview"] = f"m{largest}-best-candidates.png"
        proved = [index for index, record in enumerate(records) if record["maximum_certified"]]
        if proved:
            png_sheet([records[index] for index in proved], [positions[index] for index in proved], destination / "proved-maxima.png")
            manifest["proved_preview"] = "proved-maxima.png"
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True, help="JSONL graph export or run directory; repeatable")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--png", action="store_true", help="Also draw a contact-sheet PNG using matplotlib")
    arguments = parser.parse_args()
    manifest = build_atlas(arguments.input, arguments.out, arguments.png)
    print(json.dumps({"graphs": manifest["graphs"], "gallery": str(arguments.out / "index.html"), "contact_sheet": str(arguments.out / "contact-sheet.svg")}))


if __name__ == "__main__":
    main()

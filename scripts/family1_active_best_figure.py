#!/usr/bin/env python3
"""Draw every active estimated-best tie, without converting estimates to proofs."""
import argparse
import json
from pathlib import Path
import re
import subprocess

import family1_tikz_atlas as drawing
import family1_grouped_atlas as grouping
from family1_graph_candidate_search import verify_witness
from family1_layer_certificate import reference

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=REPO / "results/family1-m8-estimates/best-candidates.jsonl")
    parser.add_argument("--out", type=Path, default=REPO / "output/pdf/family1-m8-active-best")
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("Use a fresh figure directory")
    records = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    assert records and len({row["estimated_merge_length"] for row in records}) == 1
    args.out.mkdir(parents=True, exist_ok=True)
    body, audit, groups = [], [], {}
    for row in records:
        verify_witness(row["canonical_table"], row["witness"])
        shape = grouping.certified.underlying_shape_key(row["canonical_table"])
        groups.setdefault(shape, []).append(row)
    grouped_records = []
    for number, (shape, sources) in enumerate(sorted(groups.items()), 1):
        row = min(sources, key=lambda item: item["key"])
        root_audit = grouping.root_audit(row["canonical_table"], {item["key"] for item in sources})
        starts = [item["vertex"] for item in root_audit if item["selected"]]
        assert {item["rooted_key"] for item in root_audit if item["selected"]} == {item["key"] for item in sources}
        verification = verify_witness(row["canonical_table"], row["witness"])
        picture, _ = drawing.tikz_picture(row, "none")
        picture = grouping.unlabel_picture(picture, starts)
        edges = {tuple(map(int, match)) for match in re.findall(r"^% edge (\d+) (\d+) (\d+)$", picture, re.M)}
        expected = {(s, p, target) for s, ports in enumerate(row["canonical_table"]) for p, target in enumerate(ports)}
        assert edges == expected and len(edges) == 2 * row["m"]
        filename = f"graph-{number:02}.tex"
        (args.out / filename).write_text(picture, encoding="utf-8")
        low, high = min(item["estimated_band"][0] for item in sources), max(item["estimated_band"][1] for item in sources)
        point = row["estimated_merge_length"]
        start_text = ",".join(map(str, starts))
        body += [r"\begin{tikzpicture}",
                 r"\node[font=\large\bfseries] at (0,4.3) {Eight-state estimated leader};",
                 rf"\node[font=\large] at (0,3.85) {{$\widehat H={point}\quad\text{{(rough range }}{low}\text{{--}}{high}\text{{)}}$}};",
                 rf"\node[inner sep=0pt] at (0,0) {{\scalebox{{1.2}}{{\input{{{filename}}}}}}};",
                 rf"\node[align=center,font=\small] at (0,-4.05) {{Verified pair length: {row['upper_bound']}. Best estimated start(s): $\{{{start_text}\}}$.\\The shortest length is estimated; all arrows are unlabelled.}};",
                 r"\node[align=center,font=\small] at (0,-4.7) {Marked vertices are alternative starting states, chosen one at a time.\\Isomorphic rooted cases share one graph drawing.};",
                 rf"\node[font=\scriptsize\ttfamily] at (0,-5.2) {{{row['key']}}};",
                 r"\end{tikzpicture}"]
        audit.append({"key": row["key"], "shape_key": shape, "marked_start_vertices": starts,
                      "root_audit": root_audit, "edge_table_checked": True, "witness_verification": verification})
        grouped_records.append({"shape_key": shape, "representative_key": row["key"],
                                "canonical_table": row["canonical_table"], "marked_start_vertices": starts,
                                "source_rooted_cases": sources, "root_audit": root_audit})
    source = r"""\documentclass[tikz,border=8pt,multi=tikzpicture]{standalone}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{amsmath}
\usetikzlibrary{arrows.meta}
\begin{document}
""" + "\n".join(body) + "\n\\end{document}\n"
    (args.out / "active-best.tex").write_text(source, encoding="utf-8")
    with (args.out / "build.log").open("w") as log:
        result = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "active-best.tex"],
                                cwd=args.out, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError(f"TeX failed: {args.out / 'build.log'}")
    (args.out / "records.json").write_text(json.dumps({"source": reference(args.input), "all_top_ties": records,
        "underlying_graphs": grouped_records, "graph_and_witness_audit": audit,
        "all_edges_unlabelled_and_solid": True, "heuristic_estimates_are_certificates": False}, indent=2) + "\n")
    manifest = {path.name: reference(path) for path in args.out.iterdir() if path.is_file()}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"pages": len(groups), "rooted_cases": len(records), "all_top_ties_drawn": True,
                      "pdf": reference(args.out / "active-best.pdf")}, indent=2))


if __name__ == "__main__":
    main()

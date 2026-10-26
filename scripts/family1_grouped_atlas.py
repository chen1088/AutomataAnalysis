#!/usr/bin/env python3
"""Group the certified Family 1 winners by underlying graph, retaining all roots.

This is a presentation/export step, not a search or an extremality proof. The
source exact certificates are checked and preserved. The m=8 panel is explicitly
a heuristic leader; the larger panels retain the existing proved lower examples.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

import family1_certified_tikz as certified
import family1_tikz_atlas as drawing

REPO = Path(__file__).resolve().parents[1]
MAXIMA = [1, 3, 6, 10, 15, 23, 34]
ROOTED_COUNTS = [1, 1, 2, 1, 5, 2, 8]
SHAPE_COUNTS = [1, 1, 1, 1, 4, 1, 4]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def pinned(path):
    return {"path": str(path.relative_to(REPO)).replace("\\", "/"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def root_audit(table, winner_keys):
    result = []
    for root in range(len(table)):
        if not certified.accessible(table, root):
            result.append({"vertex": root, "accessible": False, "selected": False})
            continue
        canonical, mapping = certified.rooted_canonical(table, root, return_mapping=True)
        key = certified.key_for(canonical)
        # Check the entire table under the saved isomorphism, not its hash.
        mapped = [None] * len(table)
        for source, row in enumerate(table):
            mapped[mapping[source]] = tuple(sorted(mapping[target] for target in row))
        assert tuple(mapped) == canonical
        result.append({"vertex": root, "accessible": True, "rooted_key": key,
                       "vertex_to_rooted_labels": list(mapping), "selected": key in winner_keys})
    return result


def unlabel_picture(text, starts):
    """Preserve original edge paths while forgetting the arbitrary port order."""
    text = re.sub(r",dash pattern=on [^}\n]+", "", text)
    # Labels in manual drawings occur between edge[...] and its endpoint.
    text = re.sub(r"\s+node\[[^\]]*label[^\]]*\]\s*\{\$\s*[01]\s*\$\}", "", text)
    text = re.sub(r"^\\node\[[^\]]*label[^\]]*\].*\n", "", text, flags=re.MULTILINE)
    parts = []
    for line in text.splitlines():
        match = re.search(r"\\node\[([^\]]+)\]\s*\(q(\d+)\)", line)
        if match:
            style, state = match.group(1), int(match.group(2))
            style = re.sub(r"\b(f1m[57] root|f1atlas root)\b", lambda m: m.group(0).replace("root", "vertex" if "f1m" in m.group(0) else "state"), style)
            if state in starts:
                style = re.sub(r"\b(f1m[57] vertex|f1atlas state)\b", lambda m: m.group(0).replace("vertex", "root").replace("state", "root"), style)
                style += ",fill=black!10"
            line = line[:match.start(1)] + style + line[match.end(1):]
        parts.append(line)
    result = "\n".join(parts) + "\n"
    assert "dash pattern" not in result
    assert not re.search(r"\\node\[[^\]]*label[^\]]*\]", result)
    return result


def overview(groups):
    lines = [r"{\LARGE\bfseries Family 1: grouped graph atlas}\par\vspace{3mm}",
             r"{\large Exact reachable sizes $1$ through $20$}\par\vspace{4mm}",
             r"Each vertex has two outgoing edges and unrestricted indegree. Loops and parallel edges are allowed. Arrows have identical styles: their local port order is immaterial. Vertex numbers identify possible starting states.\par\vspace{2mm}",
             r"For a chosen start, $H(G)$ is the shortest positive length of two distinct equal-length words whose endpoint vectors agree for every static mask. Different starting states are scored separately. A double circle marks an alternative start, never a simultaneous collection of roots.\par\vspace{3mm}",
             r"\begin{center}\small\begin{tabular}{rcrrl}\toprule $m$ & $F(m)$ & Rooted winners & Shapes & Evidence \\\midrule"]
    for m in range(1, 21):
        if m <= 7:
            lines.append(f"{m} & ${MAXIMA[m-1]}$ & {ROOTED_COUNTS[m-1]} & {SHAPE_COUNTS[m-1]} & Certified complete " + r"\\")
        elif m == 8:
            lines.append(r"8 & $\ge35$ & -- & -- & Global maximum unresolved \\")
        else:
            lines.append(f"{m} & $\\ge34$ & -- & -- & Constructive lower example " + r"\\")
    lines += [r"\bottomrule\end{tabular}\end{center}\vspace{2mm}",
              r"For $m\le7$, the 20 certified maximizing rooted classes are grouped into 13 ordinary graph shapes. Every vertex giving one of those rooted classes is marked, including automorphically equivalent vertices. The source witnesses and full root-to-class mappings are preserved in the accompanying JSON.\par\vspace{2mm}",
              r"At $m=8$, the picture is the current heuristic leader: finder length $50$, estimated $H\approx49$ (rough range $48$--$50$), rigorous graph bound $1\le H\le50$. The independently certified global lower bound $F(8)\ge35$ comes from a different graph. No exact score or global maximality is claimed for the pictured graph.\par\vspace{2mm}",
              r"For $9\le m\le20$, a marked vertex is only the start of an example with $H\ge34$, proved by projection to a certified seven-state graph. These are not asserted to be winners.\par\vspace{2mm}",
              r"Exactly $m$ reachable vertices is distinct from a cumulative budget $1,\ldots,m$. Deleting unreachable vertices preserves all rooted trajectories and $H(G)$; the cumulative optimum is therefore the maximum over the exact reachable sizes. No strong connectivity assumption is imposed."]
    return "\n".join(lines)


def panel_caption(group):
    roots = ", ".join(str(root) for root in group["selected_vertices"])
    if group["kind"] == "certified-maximizer":
        count = len(group["source_rooted_classes"])
        return rf"$H={group['merge_length']}$. Optimal starts: $\{{{roots}\}}$.\\{count} distinct rooted maximizing class{'es' if count != 1 else ''}."
    if group["m"] == 8:
        return rf"Best current estimated start: ${roots}$.\\Finder length $50$; working estimate $H\approx49$."
    return rf"Example start: ${roots}$. Proved $H\ge34$.\\Exact score and global maximum unresolved."


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figures", type=Path, default=REPO / "figures/family1-grouped-atlas")
    parser.add_argument("--results", type=Path, default=REPO / "results/family1-grouped-atlas")
    parser.add_argument("--output", type=Path, default=REPO / "output/pdf/family1-grouped-atlas")
    args = parser.parse_args(argv)
    for path in (args.figures / "snippets", args.figures / "standalone", args.results, args.output):
        path.mkdir(parents=True, exist_ok=True)

    current_path = REPO / "results/family1-atlas-current/champions.jsonl"
    best_path = REPO / "results/family1-m8-estimates/best-candidates.jsonl"
    old_manifest = REPO / "figures/family1-atlas/source-manifest.json"
    current, best = read_jsonl(current_path), read_jsonl(best_path)
    assert len(best) == 1 and best[0]["verified_finder_length"] == 50
    groups, sources, certified_coverage = [], [pinned(current_path), pinned(best_path), pinned(old_manifest)], []
    manual = drawing.manual_map(REPO / "figures/family1-m5") | drawing.manual_map(REPO / "figures/family1-m7")

    for m in range(1, 8):
        directory = REPO / ("results/family1-m1-m6" if m <= 6 else "results/family1-m7")
        raw_summary = json.loads((directory / "summary.json").read_text(encoding="utf-8-sig"))
        certificate = next(item for item in raw_summary["sizes"] if item["m"] == m) if "sizes" in raw_summary else raw_summary
        assert certificate["enumeration_complete"] is True
        assert certificate.get("maximum_certified", certificate.get("maximum_value_certified")) is True
        assert certificate.get("scoring_complete", certificate.get("maximizing_collection_complete")) is True
        raw_rows = [row for row in read_jsonl(directory / "maximizers.jsonl") if row["m"] == m]
        rows = [row for row in current if row["m"] == m]
        assert {certified.key_for(row["canonical_table"]) for row in raw_rows} == {row["key"] for row in rows}
        assert len(raw_rows) == len(rows) == certificate["maximizer_count"]
        for row in rows:
            assert row["status"] == "exact" and row["lower_bound"] == row["upper_bound"] == row["merge_length"]
            assert certified.key_for(row["canonical_table"]) == row["key"]
            assert certified.rooted_canonical(row["canonical_table"]) == tuple(tuple(targets) for targets in row["canonical_table"])
            certified.verify_witness(row["canonical_table"], row["merge_length"], row["witness"])
        source_pin = {"summary": pinned(directory / "summary.json"), "maximizers": pinned(directory / "maximizers.jsonl")}
        assert len(rows) == ROOTED_COUNTS[m-1]
        assert {row["merge_length"] for row in rows} == {MAXIMA[m-1]}
        displayed = {row["key"] for row in current if row["m"] == m}
        assert displayed == {row["key"] for row in rows}
        by_shape = defaultdict(list)
        for row in rows:
            by_shape[certified.underlying_shape_key(row["canonical_table"])].append(row)
        assert len(by_shape) == SHAPE_COUNTS[m-1]
        size_winners = {row["key"] for row in rows}
        covered = []
        for shape_key, shape_rows in sorted(by_shape.items()):
            representative = min(shape_rows, key=lambda row: row["key"])
            audit = root_audit(representative["canonical_table"], size_winners)
            selected = [item["vertex"] for item in audit if item["selected"]]
            found = {item["rooted_key"] for item in audit if item["selected"]}
            expected = {row["key"] for row in shape_rows}
            assert found == expected
            covered.extend(found)
            groups.append({"m": m, "key": representative["key"], "canonical_table": representative["canonical_table"],
                           "shape_key": shape_key, "kind": "certified-maximizer", "merge_length": MAXIMA[m-1],
                           "lower_bound": MAXIMA[m-1], "upper_bound": MAXIMA[m-1],
                           "maximum_value_certified": True, "maximizing_collection_complete": True,
                           "selected_vertices": selected, "root_audit": audit,
                           "source_rooted_classes": shape_rows, "source_certificate": source_pin})
        assert sorted(covered) == sorted(size_winners)
        certified_coverage.append({"m": m, "global_maximum": MAXIMA[m-1], "rooted_classes": len(rows),
                                   "ordinary_shapes": len(by_shape), "every_source_class_retained_once": True,
                                   "every_accessible_vertex_checked": True, "all_upper_witnesses_replayed": True})

    leader = best[0]
    certified.verify_witness(leader["canonical_table"], 50, leader["witness"])
    audit = root_audit(leader["canonical_table"], {leader["key"]})
    groups.append({"m": 8, "key": leader["key"], "canonical_table": leader["canonical_table"],
                   "shape_key": certified.underlying_shape_key(leader["canonical_table"]),
                   "kind": "heuristic-leader", "lower_bound": 1, "upper_bound": 50,
                   "estimated_merge_length": 49, "estimated_band": [48, 50], "merge_length": None,
                   "maximum_value_certified": False, "maximizing_collection_complete": False,
                   "selected_vertices": [row["vertex"] for row in audit if row["selected"]],
                   "root_audit": audit, "source_record": leader, "global_lower_bound_from_different_graph": 35})
    m8_audit_path = REPO / "out/family1-m8-root-audit/audit.json"
    if m8_audit_path.is_file():
        heuristic_audit = json.loads(m8_audit_path.read_text(encoding="utf-8-sig"))
        assert heuristic_audit["winning_rooted_key"] == leader["key"]
        assert heuristic_audit["top_starting_vertices_in_winning_table"] == groups[-1]["selected_vertices"] == [0]
        assert [item["verified_finder_length"] for item in heuristic_audit["roots"]] == [50, 42, 49, 39, 43, 47, 43, 46]
        assert heuristic_audit["refined_rooted_class_count"] == 311
        assert heuristic_audit["archived_rooted_class_count"] == 45004
        assert heuristic_audit["near_top_within_two_rooted_class_count"] == 5
        groups[-1]["heuristic_root_audit_source"] = pinned(m8_audit_path)
        groups[-1]["heuristic_root_audit"] = heuristic_audit
        sources.append(pinned(m8_audit_path))
    for m in range(9, 21):
        row = next(row for row in current if row["m"] == m)
        groups.append(dict(row, shape_key=certified.underlying_shape_key(row["canonical_table"]),
                           kind="constructive-lower-example", selected_vertices=[0],
                           maximum_value_certified=False, maximizing_collection_complete=False,
                           source_record=row))
    assert len(groups) == 26

    pages = [{"page": 1, "kind": "overview"}]
    document = [r"\documentclass[11pt,a4paper]{article}", r"\usepackage[margin=16mm]{geometry}",
                r"\usepackage{tikz,amsmath,booktabs,lmodern,graphicx}", r"\usetikzlibrary{arrows.meta}",
                r"\setlength{\parindent}{0pt}", r"\begin{document}", overview(groups)]
    for m in range(1, 21):
        selected = [group for group in groups if group["m"] == m]
        document += [r"\clearpage", rf"{{\LARGE\bfseries $m={m}$}}\par\vspace{{3mm}}"]
        if m <= 7:
            document.append(rf"Global maximum $F({m})={MAXIMA[m-1]}$; all {ROOTED_COUNTS[m-1]} rooted maximizing classes, grouped into {len(selected)} ordinary shape{'s' if len(selected) != 1 else ''}.\par\vspace{{2mm}}")
            document.append(r"Double-circled vertices are all optimal starting states. Choose one marked start at a time; each choice defines a separate rooted graph.\par\vspace{3mm}")
        elif m == 8:
            document.append(r"\textbf{One candidate found.} The working estimate is $49$ (rough range $48$--$50$), with a verified pair of length $50$. The marked start $0$ gives the best current estimate; start $2$ of the same graph is the runner-up.\par\vspace{2mm}")
            document.append(r"All eight starting states of this graph were checked heuristically. The returned pair lengths are:\par\smallskip\begin{center}\begin{tabular}{r|rrrrrrrr}Start &0&1&2&3&4&5&6&7\\\hline Pair length &50&42&49&39&43&47&43&46\end{tabular}\end{center}\vspace{2mm}")
        else:
            document.append(r"\textbf{Constructive lower-bound example.} The indicated start gives $H\ge34$ by a static-mask projection onto a certified seven-state maximizer. This graph has not been certified globally optimal; its exact score is unresolved.\par\vspace{3mm}")
        for index, group in enumerate(selected, 1):
            name = f"m{m:02d}-shape-{index:02d}"
            if group["key"] in manual:
                picture = manual[group["key"]]["text"]
                group["layout_source"] = {key: value for key, value in manual[group["key"]].items() if key != "text"}
            else:
                picture, positions = drawing.tikz_picture(group, "none", drawing.construction_positions(group))
                group["layout_positions"] = positions
            picture = unlabel_picture(picture, set(group["selected_vertices"]))
            edge_entries = [tuple(map(int, match)) for match in re.findall(r"^% edge (\d+) (\d+) (\d+)\s*$", picture, re.MULTILINE)]
            expected_edges = {(state, port, target) for state, row in enumerate(group["canonical_table"]) for port, target in enumerate(row)}
            assert len(edge_entries) == 2*m and set(edge_entries) == expected_edges
            marked = sorted(int(match) for match in re.findall(r"\\node\[[^\]]* root[^\]]*\]\s*\(q(\d+)\)", picture))
            assert marked == group["selected_vertices"], (name, marked, group["selected_vertices"])
            snippet = args.figures / "snippets" / f"{name}.tex"
            snippet.write_text(picture, encoding="utf-8")
            group["snippet"] = f"snippets/{name}.tex"
            group["snippet_sha256"] = hashlib.sha256(snippet.read_bytes()).hexdigest()
            (args.figures / "standalone" / f"{name}.tex").write_text(
                "\\documentclass[border=3mm]{standalone}\n\\usepackage{tikz}\n\\usetikzlibrary{arrows.meta}\n\\begin{document}\n\\input{../snippets/" + name + ".tex}\n\\end{document}\n", encoding="utf-8")
            width = ".48" if len(selected) > 1 else ".94"
            image_width = "6.9cm" if len(selected) > 1 else "10.3cm"
            document += [rf"\begin{{minipage}}[t]{{{width}\textwidth}}\centering", rf"\resizebox{{{image_width}}}{{!}}{{\input{{snippets/{name}.tex}}}}\par",
                         rf"\small\textbf{{({chr(96+index)})}} {panel_caption(group)}\par\end{{minipage}}"]
            if len(selected) > 1:
                document.append(r"\hfill" if index % 2 else r"\par\vspace{5mm}")
        pages.append({"page": m+1, "m": m, "shape_keys": [group["shape_key"] for group in selected]})
    document += [r"\end{document}"]
    (args.figures / "atlas.tex").write_text("\n".join(document) + "\n", encoding="utf-8")
    manifest = {"schema": 1, "description": "Ordinary shapes with all qualifying alternative roots marked separately",
                "sources": sources, "graphs": 26, "page_count": 21, "port_labels": "none", "all_edges_solid": True,
                "certified_rooted_classes": 20, "certified_ordinary_shapes": 13,
                "certificate_coverage": certified_coverage, "pages": pages, "drawings": groups,
                "m8_global_maximum_certified": False, "m8_leader_rigorous_interval": [1, 50],
                "m8_global_lower_bound_from_different_graph": 35}
    dump(args.figures / "source-manifest.json", manifest)
    dump(args.results / "summary.json", {key: value for key, value in manifest.items() if key != "drawings"})
    (args.results / "graphs.jsonl").write_text("".join(json.dumps(group, ensure_ascii=True, separators=(",", ":")) + "\n" for group in groups), encoding="utf-8")
    readme = """# Family 1 grouped atlas

The 20 certified rooted maximizers through seven states are preserved as 13
ordinary shapes. Each marked vertex is a separate starting-state choice. All
accessible vertices were root-canonicalized; automorphic starts are included.
The JSON retains every original rooted record, proof source, witness and mapping.
Arbitrary local port labels/styles have been removed; parallel multiplicity stays.

The eight-state drawing is the current heuristic leader, estimate 49, finder
length 50, rigorous graph interval [1,50]. It is not a certified global optimum.
The independent global lower bound F(8)>=35 belongs to another graph.
The remaining pages are existing lower examples, not asserted maxima.

Reproduce from repository root:

    uv run --no-project python scripts/family1_grouped_atlas.py
    & "$env:APPDATA/TinyTeX/bin/windows/pdflatex.exe" '-interaction=nonstopmode' '-halt-on-error' '-output-directory=../../output/pdf/family1-grouped-atlas' atlas.tex

Run the TeX command with working directory figures/family1-grouped-atlas.
Reusable tikzpicture snippets and standalone wrappers are under that directory.
"""
    (args.results / "README.md").write_text(readme, encoding="utf-8")
    (args.output / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps({"graphs": len(groups), "certified_shapes": 13, "certified_rooted_classes": 20,
                      "pages": 21, "figures": str(args.figures), "results": str(args.results)}))


if __name__ == "__main__":
    main()

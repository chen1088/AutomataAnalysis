#!/usr/bin/env python3
"""Draw every active estimated-best tie, without converting estimates to proofs."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

import family1_tikz_atlas as drawing
import family1_grouped_atlas as grouping
from family1_graph_candidate_search import verify_witness
from hard_pair_witness_figure import parameter_label, reference, witness_record

REPO = Path(__file__).resolve().parents[1]


def refinement_label(row):
    observations = row.get("observations", [])
    completed = sorted({item["k"] for item in observations if item.get("completed_stage") is True})
    incomplete = sorted({item["k"] for item in observations if item.get("completed_stage") is False})
    if not completed and not incomplete:
        return "Separate refinement k metadata unavailable."
    pieces = []
    if completed:
        pieces.append("completed common-suffix k=" + ",".join(map(str, completed)))
    if incomplete:
        pieces.append("attempted k=" + ",".join(map(str, incomplete)) + " (incomplete)")
    return "Separate refinement: " + "; ".join(pieces) + "."


def preserved_picture(row, starts, directory):
    """Keep the current publication's curves, including its rounded coordinates."""
    if directory.is_dir():
        for path in sorted(directory.glob("graph-*.tex")):
            picture = path.read_text()
            if f"key={row['key']}." not in picture:
                continue
            roots = {int(state) for state in re.findall(r"^\\node\[f1atlas root[^\n]*\(q(\d+)\)", picture, re.M)}
            if roots == set(starts):
                return picture, reference(path)
    picture, _ = drawing.tikz_picture(row, "none")
    return grouping.unlabel_picture(picture, starts), None


def matplotlib_pdf(groups, destination, preview):
    """Vector fallback using exactly the established atlas edge geometry."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Circle, FancyArrowPatch
    from matplotlib.path import Path as MplPath

    with PdfPages(destination) as pdf:
        for index, item in enumerate(groups):
            row, starts, certificate = item["row"], item["starts"], item["certificate"]
            figure = plt.figure(figsize=(8.5, 10))
            figure.patch.set_facecolor("white")
            figure.text(.5, .965, "Eight-state estimated leader", ha="center", fontsize=17, weight="bold")
            figure.text(.5, .935, f"Verified upper bound H ≤ {certificate['length']}; shortestness unproved", ha="center", fontsize=13)
            figure.text(.5, .91, f"Working estimate {row['estimated_merge_length']} (historical conjecture)", ha="center", fontsize=10)
            axis = figure.add_axes([.18, .48, .64, .43])
            axis.set_xlim(-3, 3)
            axis.set_ylim(-3, 3)
            axis.set_aspect("equal")
            axis.axis("off")
            picture = item["picture"]
            curves = re.findall(r"^\\draw\[f1atlas port[01]\] (.+);$", picture, re.M)
            if len(curves) != 2 * row["m"]:
                raise ValueError("Matplotlib fallback requires the checked atlas cubic-curve snippets")
            for curve in curves:
                points = [tuple(map(float, pair)) for pair in re.findall(r"\((-?[0-9.]+),(-?[0-9.]+)\)", curve)]
                if len(points) != 4:
                    raise ValueError("Invalid preserved atlas cubic curve")
                axis.add_patch(FancyArrowPatch(path=MplPath(points, [MplPath.MOVETO] + [MplPath.CURVE4] * 3), arrowstyle="-|>", mutation_scale=9,
                                              linewidth=.8, color="black"))
            positions = re.findall(r"^\\node\[[^\n]*\(q(\d+)\) at \((-?[0-9.]+),(-?[0-9.]+)\)", picture, re.M)
            if len(positions) != row["m"]:
                raise ValueError("Preserved drawing does not contain every graph vertex")
            for state, x, y in positions:
                state, x, y = int(state), float(x), float(y)
                axis.add_patch(Circle((x, y), .20769 if state in starts else .17308, facecolor="white", edgecolor="black", linewidth=.8))
                if state in starts:
                    axis.add_patch(Circle((x, y), .16154, fill=False, edgecolor="black", linewidth=.6))
                axis.text(x, y, str(state), fontsize=9, ha="center", va="center")
            figure.text(.5, .49, f"Marked start(s): {','.join(map(str, starts))}; all arrows unlabelled and solid.", ha="center", fontsize=9)
            figure.text(.5, .463, f"The pair below is verified for representative start 0 on all {certificate['family_size']} static masks.", ha="center", fontsize=9)
            figure.text(.5, .43, "u = " + certificate["first"], ha="center", fontsize=9, family="monospace")
            figure.text(.5, .405, "v = " + certificate["second"], ha="center", fontsize=9, family="monospace")
            figure.text(.5, .372, parameter_label(certificate["search_parameters"]), ha="center", fontsize=10)
            figure.text(.5, .349, refinement_label(row), ha="center", fontsize=8.5)
            trace_axis = figure.add_axes([.14, .13, .74, .17])
            trace_axis.plot([entry["length"] for entry in certificate["trace"]],
                            [entry["differing"] for entry in certificate["trace"]], color="#1b5d8c", linewidth=1.5)
            trace_axis.set_xlim(0, certificate["length"])
            trace_axis.set_ylim(0, certificate["family_size"])
            trace_axis.set_xlabel("Joint symbols read", fontsize=9)
            trace_axis.set_ylabel("Differing DFAs, D", fontsize=9)
            trace_axis.tick_params(labelsize=8)
            trace_axis.spines[["top", "right"]].set_visible(False)
            figure.text(.5, .32, "D(i) counts different endpoints; D(empty)=0. Agreement can later be lost.", ha="center", fontsize=9)
            figure.text(.5, .055, row["key"], ha="center", fontsize=8, family="monospace")
            pdf.savefig(figure, facecolor="white")
            if index == 0 and preview:
                preview.parent.mkdir(parents=True, exist_ok=True)
                figure.savefig(preview, dpi=120, facecolor="white")
            plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=REPO / "results/family1-m8-estimates/best-candidates.jsonl")
    parser.add_argument("--out", type=Path, default=REPO / "output/pdf/family1-m8-active-best")
    parser.add_argument("--renderer", choices=("auto", "tex", "matplotlib"), default="auto")
    parser.add_argument("--preview", type=Path, help="Optional local PNG preview with the matplotlib renderer")
    parser.add_argument("--drawing-source", type=Path, default=REPO / "output/pdf/family1-m8-active-best",
                        help="Reuse matching established graph snippets without recomputing their geometry")
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("Use a fresh figure directory")
    records = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    assert records and len({row["estimated_merge_length"] for row in records}) == 1
    args.out.mkdir(parents=True, exist_ok=True)
    body, audit, groups, certificates, rendered_groups = [], [], {}, [], []
    for row in records:
        verify_witness(row["canonical_table"], row["witness"])
        certificates.append(witness_record(row))
        shape = grouping.certified.underlying_shape_key(row["canonical_table"])
        groups.setdefault(shape, []).append(row)
    grouped_records = []
    for number, (shape, sources) in enumerate(sorted(groups.items()), 1):
        row = min(sources, key=lambda item: item["key"])
        root_audit = grouping.root_audit(row["canonical_table"], {item["key"] for item in sources})
        starts = [item["vertex"] for item in root_audit if item["selected"]]
        assert {item["rooted_key"] for item in root_audit if item["selected"]} == {item["key"] for item in sources}
        verification = verify_witness(row["canonical_table"], row["witness"])
        certificate = next(item for item in certificates if item["key"] == row["key"])
        picture, drawing_source = preserved_picture(row, starts, args.drawing_source)
        edges = {tuple(map(int, match)) for match in re.findall(r"^% edge (\d+) (\d+) (\d+)$", picture, re.M)}
        expected = {(s, p, target) for s, ports in enumerate(row["canonical_table"]) for p, target in enumerate(ports)}
        assert edges == expected and len(edges) == 2 * row["m"]
        filename = f"graph-{number:02}.tex"
        (args.out / filename).write_text(picture, encoding="utf-8")
        low, high = min(item["estimated_band"][0] for item in sources), max(item["estimated_band"][1] for item in sources)
        point = row["estimated_merge_length"]
        start_text = ",".join(map(str, starts))
        producing_k = certificate["search_parameters"]["k"]
        k_text = str(producing_k) if producing_k is not None else "unknown"
        points = " -- ".join(f"({-4 + 8 * entry['length'] / certificate['length']:.4f},{-8.5 + entry['differing'] / certificate['family_size']:.4f})"
                             for entry in certificate["trace"])
        body += [r"\begin{tikzpicture}",
                 r"\node[font=\large\bfseries] at (0,4.3) {Eight-state estimated leader};",
                 rf"\node[font=\large] at (0,3.85) {{$\widehat H={point}\quad\text{{(rough range }}{low}\text{{--}}{high}\text{{)}}$}};",
                 rf"\node[inner sep=0pt] at (0,0) {{\scalebox{{1.2}}{{\input{{{filename}}}}}}};",
                 rf"\node[align=center,font=\small] at (0,-4.05) {{Verified upper pair length: {row['upper_bound']}; shortestness unproved.\\Best estimated start(s): $\{{{start_text}\}}$. All arrows are unlabelled.}};",
                 r"\node[align=center,font=\small] at (0,-4.7) {Marked vertices are alternative starting states, chosen one at a time.\\Isomorphic rooted cases share one graph drawing.};",
                 rf"\node[font=\small\ttfamily] at (0,-5.2) {{u = {certificate['first']}}};",
                 rf"\node[font=\small\ttfamily] at (0,-5.65) {{v = {certificate['second']}}};",
                 rf"\node[font=\small] at (0,-6.1) {{Pair producer: common-suffix window; $k=\text{{{k_text}}}$. Beam/prefix settings unknown.}};",
                 rf"\node[font=\scriptsize] at (0,-6.55) {{{refinement_label(row)}}};",
                 rf"\node[font=\small] at (0,-7) {{Pair above: representative start 0; all {certificate['family_size']} original static masks replayed.}};",
                 r"\node[font=\small] at (0,-7.35) {$D(i)$ counts different endpoints; $D(\epsilon,\epsilon)=0$. Agreement may be lost.};",
                 r"\draw[gray] (-4,-7.5) -- (-4,-8.5) -- (4,-8.5);",
                 r"\node[font=\tiny,anchor=east] at (-4,-7.5) {256};",
                 r"\node[font=\tiny,anchor=east] at (-4,-8.5) {0};",
                 rf"\draw[blue!60!black,line width=.7pt] {points};",
                 rf"\node[font=\scriptsize] at (0,-8.9) {{Joint symbols read: $0\ldots {certificate['length']}$}};",
                 rf"\node[font=\scriptsize\ttfamily] at (0,-9.4) {{{row['key']}}};",
                 r"\end{tikzpicture}"]
        audit.append({"key": row["key"], "shape_key": shape, "marked_start_vertices": starts,
                      "root_audit": root_audit, "edge_table_checked": True, "witness_verification": verification,
                      "scalar_witness_certificate": certificate, "preserved_drawing_source": drawing_source})
        grouped_records.append({"shape_key": shape, "representative_key": row["key"],
                                "canonical_table": row["canonical_table"], "marked_start_vertices": starts,
                                "source_rooted_cases": sources, "root_audit": root_audit})
        rendered_groups.append({"row": row, "starts": starts, "certificate": certificate, "picture": picture})
    source = r"""\documentclass[tikz,border=8pt,multi=tikzpicture]{standalone}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{amsmath}
\usetikzlibrary{arrows.meta}
\begin{document}
""" + "\n".join(body) + "\n\\end{document}\n"
    (args.out / "active-best.tex").write_text(source, encoding="utf-8")
    renderer = args.renderer
    if renderer == "auto":
        renderer = "tex" if shutil.which("pdflatex") else "matplotlib"
    if renderer == "tex":
        with (args.out / "build.log").open("w") as log:
            result = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "active-best.tex"],
                                    cwd=args.out, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError(f"TeX failed: {args.out / 'build.log'}")
    else:
        matplotlib_pdf(rendered_groups, args.out / "active-best.pdf", args.preview)
    (args.out / "witnesses.json").write_text(json.dumps({"source": reference(args.input), "witnesses": certificates}, indent=2) + "\n")
    (args.out / "records.json").write_text(json.dumps({"source": reference(args.input), "all_top_ties": records,
        "underlying_graphs": grouped_records, "graph_and_witness_audit": audit,
        "all_edges_unlabelled_and_solid": True, "heuristic_estimates_are_certificates": False,
        "pdf_renderer": renderer, "generator": reference(Path(__file__)),
        "renderer_sources": [reference(Path(drawing.__file__)), reference(Path(grouping.__file__)),
                             reference(Path(__file__).with_name("hard_pair_witness_figure.py"))]}, indent=2) + "\n")
    leader = certificates[0]
    (args.out / "README.md").write_text("# Active eight-state candidate and its pair\n\n"
        + f"The figure displays the verified length-{leader['length']} upper witness below. The shortest length and global maximum remain unproved. "
        + "The displayed estimate 49 is a historical working conjecture.\n\n"
        + f"u = `{leader['first']}`\n\nv = `{leader['second']}`\n\n"
        + parameter_label(leader["search_parameters"]) + ". Producing beam and prefix settings are unknown. "
        + refinement_label(records[0]) + " These values do not identify the producer of this imported pair.\n\n"
        + f"Independent scalar replay checks all {leader['family_size']} original static masks, including duplicate realizations from coincident ports. "
        + "D(i) is the number with different endpoints after both prefixes of length i; D(empty)=0. witnesses.json retains both words, every prefix score, search provenance and verification.\n\n"
        + "graph-01.tex preserves the complete original transition drawing. All arrows remain solid and unlabelled; marked vertices are alternative starts chosen separately. "
        + "The displayed pair belongs to representative start 0. records.json retains all source-rooted cases and audits.\n\n"
        + "Regenerate in a fresh directory with `python3 scripts/family1_active_best_figure.py --out out/my-active-best-figure`. "
        + "The default renderer uses TeX when available and otherwise writes a vector PDF with matplotlib using the same atlas edge geometry. "
        + "Editable TikZ is emitted in both cases.\n", encoding="utf-8")
    manifest = {path.name: reference(path) for path in args.out.iterdir() if path.is_file()}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"pages": len(groups), "rooted_cases": len(records), "all_top_ties_drawn": True,
                      "k": leader["search_parameters"]["k"], "window_kind": leader["search_parameters"]["window_kind"],
                      "pdf_renderer": renderer,
                      "pdf": reference(args.out / "active-best.pdf")}, indent=2))


if __name__ == "__main__":
    main()

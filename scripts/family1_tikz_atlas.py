#!/usr/bin/env python3
"""Create reusable monochrome TikZ graphs and an A4 atlas for sizes 1..20.

Every observed graph tied for the best certified lower bound is retained.
Global maximality is labeled only when the input summary supplies a certificate.
Requires only the Python standard library; TeX compilation is a separate step.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("family1_graph_atlas", Path(__file__).with_name("family1_graph_atlas.py"))
atlas = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(atlas)


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def key_for(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def certificate(summary, m):
    item = next((item for item in summary.get("sizes", []) if item.get("m") == m), {})
    value = next((item.get(field) for field in ("global_maximum", "maximum_merge_length", "maximum_value", "maximum")
                  if type(item.get(field)) is int), None)
    proved = item.get("maximum_value_certified") is True or item.get("maximum_certified") is True
    complete = item.get("maximizing_collection_complete") is True or (
        item.get("enumeration_complete") is True and item.get("scoring_complete") is True and item.get("maximum_certified") is True)
    expected = item.get("maximizer_count", item.get("best_lower_bound_ties"))
    upper = item.get("global_upper_bound") if item.get("global_upper_bound_certified") is True else value if proved else None
    return {"value": value if proved else None, "collection_complete": complete,
            "expected_count": expected if type(expected) is int else None, "upper_bound": upper}


def load_records(paths):
    records = atlas.load_records(paths)
    sources = []
    certificates = defaultdict(list)
    constructions = {}
    bound_certificates = {}
    for supplied in paths:
        source = atlas.input_file(supplied)
        summary = atlas.load_summary(source)
        for line in source.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                item = json.loads(line)
                if "construction" in item:
                    constructions[(item["m"], key_for(item["canonical_table"]))] = item["construction"]
                if "lower_certificate" in item:
                    bound_certificates[(item["m"], key_for(item["canonical_table"]))] = item["lower_certificate"]
        sources.append({"path": str(source.resolve()), "sha256": digest(source),
                        "summary_sha256": digest(source.parent / "summary.json") if (source.parent / "summary.json").is_file() else None})
        for m in range(1, 21):
            certificates[m].append(certificate(summary, m))
    selected = [record for record in records if record["best_bound_tie"]]
    grouped = defaultdict(list)
    for record in selected:
        m = record["m"]
        if (m, record["key"]) in constructions:
            record["construction"] = constructions[(m, record["key"])]
        if (m, record["key"]) in bound_certificates:
            record["lower_certificate"] = bound_certificates[(m, record["key"])]
        valid_uppers = [item["upper_bound"] for item in certificates[m] if item["upper_bound"] is not None]
        if valid_uppers:
            upper = min(valid_uppers)
            record["upper_bound"] = min(record["upper_bound"], upper) if record["upper_bound"] is not None else upper
        if record["upper_bound"] is not None and record["lower_bound"] > record["upper_bound"]:
            raise ValueError(f"conflicting global and graph certificates at m={m}")
        record["merge_length"] = record["lower_bound"] if record["lower_bound"] == record["upper_bound"] else None
        grouped[m].append(record)
    page_info = {}
    for m in range(1, 21):
        values = {item["value"] for item in certificates[m] if item["value"] is not None}
        if len(values) > 1:
            raise ValueError(f"conflicting global maximum certificates at m={m}")
        maximum = next(iter(values), None)
        complete = any(item["collection_complete"] and item["expected_count"] == len(grouped[m]) for item in certificates[m])
        complete = bool(complete and grouped[m] and all(record["merge_length"] == maximum for record in grouped[m]))
        page_info[m] = {"m": m, "maximum_value_certified": maximum is not None,
                        "global_maximum": maximum, "maximizing_collection_complete": complete,
                        "displayed_graphs": len(grouped[m]),
                        "largest_displayed_lower_bound": max((record["lower_bound"] for record in grouped[m]), default=None)}
        for record in grouped[m]:
            record["maximum_value_certified"] = maximum is not None and record["merge_length"] == maximum
            record["maximizing_collection_complete"] = complete
    return selected, page_info, sources


def cubic_points(edge):
    points = edge["points"]
    if edge["kind"] == "cubic":
        return points
    start, control, end = points
    first = tuple(start[axis] + 2 * (control[axis] - start[axis]) / 3 for axis in (0, 1))
    second = tuple(end[axis] + 2 * (control[axis] - end[axis]) / 3 for axis in (0, 1))
    return start, first, second, end


def show_port_labels(mode, m):
    if mode not in ("all", "small", "none"):
        raise ValueError("port labels must be all, small, or none")
    return mode == "all" or (mode == "small" and m <= 6)


def tikz_picture(record, port_labels="small", positions=None):
    positions = atlas.layout(record) if positions is None else positions
    edges = atlas.edge_geometry(record, positions)
    scale = 6 / max(atlas.WIDTH, atlas.HEIGHT)

    def point(value):
        return (value[0] - atlas.WIDTH / 2) * scale, (atlas.HEIGHT / 2 - value[1]) * scale

    def xy(value):
        x, y = point(value)
        return f"({x:.5f},{y:.5f})"

    parts = [f"% Family 1 rooted seed, m={record['m']}; key={record['key']}.",
             "% Requires \\usepackage{tikz} and \\usetikzlibrary{arrows.meta}.",
             "% Score and global-maximality metadata belong in the surrounding caption.",
             r"\begin{tikzpicture}[x=1cm,y=1cm,",
             r"  f1atlas state/.style={circle,draw=black,fill=white,line width=.5pt,inner sep=0pt,font=\fontsize{7}{8}\selectfont},",
             r"  f1atlas root/.style={f1atlas state,double,double distance=.42mm},",
             r"  f1atlas port0/.style={-{Stealth[length=1.45mm,width=1.05mm]},draw=black,line width=.48pt},",
             r"  f1atlas port1/.style={f1atlas port0,dash pattern=on 2.5pt off 1.6pt},",
             r"  f1atlas label/.style={font=\fontsize{6}{7}\selectfont,fill=white,inner sep=.4pt}",
             "]", r"\path[use as bounding box] (-3,-3) rectangle (3,3);"]
    for edge in edges:
        source, target, port = edge["source"], edge["target"], edge["port"]
        start, first, second, end = cubic_points(edge)
        parts += [f"% edge {source} {port} {target}",
                  f"\\draw[f1atlas port{port}] {xy(start)} .. controls {xy(first)} and {xy(second)} .. {xy(end)};"]
    if show_port_labels(port_labels, record["m"]):
        for edge in edges:
            parts.append(f"\\node[f1atlas label] at {xy(edge['label'])} {{$ {edge['port']} $}};")
    for state, position in enumerate(positions):
        radius = 18 if state == 0 else 15
        style = "f1atlas root" if state == 0 else "f1atlas state"
        parts += [f"% state {state}",
                  f"\\node[{style},minimum size={radius * 20 * scale:.4f}mm] (q{state}) at {xy(position)} {{$ {state} $}};"]
    parts.append(r"\end{tikzpicture}")
    return "\n".join(parts) + "\n", positions


def manual_map(directory):
    if directory is None or not (directory / "source-manifest.json").is_file():
        return {}
    manifest = json.loads((directory / "source-manifest.json").read_text(encoding="utf-8-sig"))
    result = {}
    items = manifest.get("drawings") or manifest.get("graphs", [])
    if not isinstance(items, list):
        raise ValueError(f"layout manifest has no graph list: {directory}")
    for item in items:
        table = item["canonical_table"]
        source = directory / item.get("file", item.get("snippet", ""))
        text = source.read_text(encoding="utf-8-sig")
        actual = [tuple(map(int, edge)) for edge in re.findall(r"^% edge (\d+) (\d+) (\d+)\s*$", text, re.MULTILINE)]
        expected = {(state, port, target) for state, row in enumerate(table) for port, target in enumerate(row)}
        if len(actual) != 2 * len(table) or set(actual) != expected:
            raise ValueError(f"manual TikZ edge metadata disagrees with its table: {source}")
        result[key_for(table)] = {"text": text, "source": str(source.resolve()), "sha256": digest(source)}
    return result


def construction_positions(record):
    """Keep the old seven states fixed while drawing the expanding root cycle."""
    construction = record.get("construction", {})
    if construction.get("name") != "expand-base-root-loop-into-cycle-with-second-ports-to-state-1":
        return None
    m = record["m"]
    raw = [(260, 220), (260, 290), (85, 345), (260, 360), (85, 425), (435, 425), (435, 335)]
    for index in range(m - 7):
        angle = math.pi / 2 + 2 * math.pi * (index + 1) / (m - 6)
        raw.append((260 + 195 * math.cos(angle), 125 + 95 * math.sin(angle)))
    positions = [None] * m
    for old, new in enumerate(construction["raw_to_canonical_labels"]):
        positions[new] = raw[old]
    return positions


def overview_document(page_info):
    """One proof-aware overview. Unknown maxima never receive guessed values."""
    parts = [r"{\LARGE\bfseries Family 1 graph atlas}\par\vspace{3mm}",
             r"{\large Exact reachable sizes $1$ through $20$}\par\vspace{5mm}",
             r"A seed has a distinguished root, two outgoing ports at every vertex, and unrestricted indegree. Loops and coincident ports are allowed. Only root-accessibility is required.\par\vspace{2mm}",
             r"Every mask is static: $\delta_\sigma(s,x)=\tau_{x\mathbin{\oplus}\sigma(s)}(s)$. The score $H(G)$ is the shortest positive length of two distinct, equal-length words whose endpoint vectors agree for all masks.\par\vspace{2mm}",
             r"Let $F(m)=\max_{|G|=m} H(G)$, where exactly $m$ states are reachable. Root-preserving relabeling and independent port swaps identify graph classes. Different roots can therefore give different classes of the same ordinary shape.\par\vspace{4mm}",
             r"\begin{center}\small\begin{tabular}{rcrrl}",
             r"\toprule $m$ & $F(m)$ & Rooted winners & Shapes & Coverage \\ \midrule"]
    shapes = [1, 1, 1, 1, 4, 1, 4]
    for m in range(1, 21):
        info = page_info[m]
        if info["maximum_value_certified"]:
            shape = str(shapes[m - 1]) if m <= len(shapes) else "--"
            parts.append(f"{m} & ${info['global_maximum']}$ & {info['displayed_graphs']} & {shape} & Certified complete " + r"\\")
        else:
            lower = info["largest_displayed_lower_bound"]
            bound = rf"$\ge {lower}$" if lower is not None else "Unknown"
            parts.append(f"{m} & {bound} & -- & -- & Global maximum unresolved " + r"\\")
    parts += [r"\bottomrule\end{tabular}\end{center}\vspace{2mm}",
              r"For $m\le7$, every maximizing rooted class is drawn. For $8\le m\le20$, each drawing is an explicit construction with $H(G)\ge34$, proved by a projection onto a certified seven-state maximizer. These pages give neither an exact graph score nor a global upper bound.\par\vspace{2mm}",
              r"The cumulative size budget $1,\ldots,m$ is a different optimization problem. Removing unreachable vertices preserves every rooted trajectory and $H(G)$, so that budget reduces to the maximum over the exact reachable sizes. No strong-connectivity reduction is used.\par\vspace{2mm}",
              r"Root $0$ is double-circled; solid and dashed arcs distinguish the two ports. Each snippet retains the full directed transition table.\par"]
    return "\n".join(parts)


def analysis_document(ancestry, edit_distances=None):
    """Append measured ancestry; this is not a proof of an extremal recurrence."""
    pairs = ancestry.get("pairs", [ancestry])
    parts = [r"{\Large\bfseries Graph edits and extremal growth}\par\vspace{4mm}",
             r"We work on rooted isomorphism classes: vertex relabeling and independent port swaps cost zero. A port retarget changes one outgoing target and costs one. A routing insertion also costs one: choose two distinct edge occurrences $a\to b$ and $c\to d$, add a nonroot vertex $v$, and replace them by\[a\to v,\qquad c\to v,\qquad v\to b,\qquad v\to d.\]Sources or targets may coincide; edge occurrences remain distinct. Its inverse removes a nonroot vertex of indegree two without a loop and reconnects its incoming occurrences to its outgoing targets in either bijection.\par\vspace{2mm}",
             r"The loop version replaces $a\to b$ by $a\to v$, $v\to v$, $v\to b$; its inverse smooths that nonroot vertex. Every intermediate seed must remain root-accessible and have two outgoing ports. The root is never deleted. The distance is the minimum number of these edits; this is a chosen unit cost for a growth operation, rather than a count of changed arcs.\par\vspace{3mm}",
             r"\textbf{Consecutive sizes.} The table exhausts all allowed one-vertex smoothings of every certified maximizing child. It does not assume that a maximizing child must have a maximizing parent.\par\vspace{3mm}",
             r"\begin{center}\small\begin{tabular}{crrrll}",
             r"\toprule Sizes & Parent $F$ & Child $F$ & Winners & One insertion & Edit distances \\ \midrule"]
    for pair in pairs:
        child_count = pair.get("child_count", pair.get("child_maximizer_count", len(pair.get("children", []))))
        distances = next((item["distances"] for item in (edit_distances or {}).get("pairs", [])
                          if item["target_m"] == pair["child_m"]), None)
        display = ",".join(map(str, distances)) if distances else "--"
        parts.append(f"${pair['parent_m']}\\to{pair['child_m']}$ & {pair['parent_global_maximum']} & {pair['child_global_maximum']} & {child_count} & {pair['children_with_global_maximizing_parent']}/{child_count} & ${display}$ " + r"\\")
    parts += [r"\bottomrule\end{tabular}\end{center}\vspace{3mm}",
              r"Edit distances are listed in child panel order. Each is the minimum distance to the entire previous-size winning collection. Complete unit neighborhoods exclude shorter paths, and explicit saved paths attain every displayed distance. The paths may pass through graphs that are not maximizers.\par\vspace{2mm}" if edit_distances else "",
              r"For $5\to6$, five-state panels (a) and (b) both grow into six-state panel (a), raising $H$ from $15$ to $23$. From panel (b), split $0\to1$ and $2\to3$ through the new vertex $5$, with outgoing targets $\{1,3\}$. All five previous winners are included in the comparison; panels (c), (d), and (e) have no winning child by this single insertion.\par\vspace{2mm}",
              r"Six-state panel (b) has best predecessor score $14$, below $F(5)=15$. One such predecessor has the same ordinary shape as a five-state winner but a different root. Retaining only rooted winning parents would already omit a winning child.\par\vspace{2mm}",
              r"With retargeting allowed, six-state panel (b) is at distance two from the five-state winning collection: one retarget followed by one insertion suffices. Thus every winning child through seven states lies within three edits of some previous-size winner under this metric.\par\vspace{2mm}" if edit_distances else "",
              r"The six-state winner reached from five-state winners is panel (a), whereas the six-state winner leading to a seven-state winner is panel (b). Hence there is no chain of maximizing rooted graphs $5\to6\to7$ using only one such insertion at each step.\par\vspace{2mm}",
              r"The edits preserve old indegrees and give the new vertex indegree two. This operation is a structural comparison, not an enumeration rule for all two-outdegree graphs. In particular, it imposes no indegree restriction on the original global search.\par",
              r"\clearpage", r"{\Large\bfseries Seven-state predecessors}\par\vspace{4mm}",
              r"All eight rooted seven-state winners have $H=34$. Their best six-state smoothing predecessors are:\par\vspace{3mm}",
              r"\begin{center}\begin{tabular}{crrr}",
              r"\toprule Child panel & Distinct parents & Best parent $H$ & Increase in $H$ \\ \midrule"]
    final_pair = next((pair for pair in pairs if pair["child_m"] == 7), pairs[-1])
    for index, child in enumerate(final_pair["children"]):
        parts.append(f"({chr(97 + index)}) & {child['accessible_parent_count']} & {child['best_parent_merge_length']} & {child['increase_from_best_parent']} " + r"\\")
    parts += [r"\bottomrule\end{tabular}\end{center}\vspace{4mm}",
              r"\textbf{A one-edit maximizing extension.} Start with the six-state maximizer\[\begin{array}{c|rrrrrr}s&0&1&2&3&4&5\\\hline\{\tau_0(s),\tau_1(s)\}&\{1,2\}&\{0,3\}&\{4,5\}&\{2,3\}&\{0,1\}&\{4,5\}\end{array}\]Replace $0\to1$ and $1\to0$ by $0\to6$ and $1\to6$, and give vertex $6$ the targets $\{0,1\}$. The result is seven-state panel (d), up to a root-preserving relabeling and port swaps. Its score increases from $23$ to $34$. The graph distance is one; the score difference is eleven.\par\vspace{3mm}",
              r"Exactly one of the eight rooted winners has a rooted six-state winning parent under this insertion. If only the predecessor's root is ignored, three of the four ordinary seven-state shapes have a predecessor of the ordinary winning six-state shape; their inherited-root scores are $20$, $23$, and $22$. Changing the root is not a free edit.\par\vspace{4mm}",
              r"\textbf{Eight-state forecast.} The certified values $10,15,23,34$ have increments $5,8,11$. Continuing that increment pattern gives $F(8)\approx48$. An informal range $40$--$55$ expresses uncertainty; neither the point guess nor the range is a certified bound or a statistical confidence interval. These small values do not distinguish quadratic from cubic asymptotics.\par\vspace{3mm}",
              r"The complete tables, witnesses, source hashes, all allowed predecessor operations, and reversible edit descriptions accompany the reusable TikZ sources.\par"]
    return "\n".join(parts)


def tex_score(record):
    lower, upper = record["lower_bound"], record["upper_bound"]
    if lower == upper:
        return rf"$H(G)={lower}$"
    if upper is not None:
        return rf"${lower}\le H(G)\le {upper}$"
    return rf"$H(G)\ge {lower}$"


def panel_caption(record, index):
    letters = ""
    while index:
        index, digit = divmod(index - 1, 26)
        letters = chr(ord("a") + digit) + letters
    label = f"({letters}) " + tex_score(record) + "."
    if record["maximum_value_certified"]:
        label += r"\par Proved maximum."
    else:
        label += r"\par Global maximum unresolved."
    return label


def atlas_document(grouped, page_info, max_panels, overview=False, ancestry=None, edit_distances=None):
    parts = [r"\documentclass[10pt,a4paper]{article}", r"\usepackage[margin=13mm]{geometry}",
             r"\usepackage{tikz,graphicx,booktabs,amsmath,amssymb}", r"\usetikzlibrary{arrows.meta}",
             r"\setlength{\parindent}{0pt}", r"\setlength{\parskip}{0pt}",
             r"\pagestyle{plain}", r"\begin{document}"]
    pages, first = [], True
    if overview:
        parts.append(overview_document(page_info))
        pages.append({"page": 1, "kind": "overview", "graph_keys": []})
        first = False
    for m in range(1, 21):
        graphs = grouped[m]
        panel_limit = 4 if m == 7 and len(graphs) == 8 and max_panels >= 4 else max_panels
        chunks = [graphs[start:start + panel_limit] for start in range(0, len(graphs), panel_limit)] or [[]]
        for continuation, chunk in enumerate(chunks):
            if not first:
                parts.append(r"\clearpage")
            first = False
            suffix = f" (continued {continuation + 1}/{len(chunks)})" if len(chunks) > 1 else ""
            parts += [rf"{{\Large\bfseries Family 1: $m={m}$}}{suffix}\par", r"\vspace{2mm}"]
            info = page_info[m]
            if info["maximum_value_certified"]:
                sentence = rf"The maximum merge length is proved to be ${info['global_maximum']}$; "
                sentence += "the maximizing collection is complete." if info["maximizing_collection_complete"] else "the maximizing collection is incomplete."
            else:
                sentence = "The global maximum remains unresolved. "
                if info["largest_displayed_lower_bound"] is not None:
                    sentence += rf"The largest displayed certified lower bound is ${info['largest_displayed_lower_bound']}$."
            parts += [rf"{{\small {sentence}}}\par", r"\vspace{1mm}",
                      r"{\small Root $0$: double circle. Port $0$: solid; port $1$: dashed.}\par", r"\vspace{3mm}"]
            if overview and m >= 8:
                proof = chunk[0].get("lower_certificate", {}) if len(chunk) == 1 else {}
                if (m == 8 and proof.get("full_family_injectivity_certified") is True
                        and proof.get("lower_bound") == chunk[0]["lower_bound"]
                        and proof.get("depth") + 1 == chunk[0]["lower_bound"] and chunk[0]["upper_bound"] is not None):
                    parts += [rf"{{\small Displayed candidate only: its exact score is unknown. A complete length-${proof['depth']}$ collision check proves $H(G)\ge{chunk[0]['lower_bound']}$; a verified length-${chunk[0]['upper_bound']}$ pair proves $H(G)\le{chunk[0]['upper_bound']}$.}}\par\vspace{{2mm}}"]
                else:
                    parts += [r"{\small Constructive example only: its individual exact score is unknown. A static-mask projection onto a certified seven-state maximizer proves $H(G)\ge34$.}\par\vspace{2mm}"]
            if not chunk:
                parts.append(r"\vspace{25mm}{\small No candidate graph was supplied for this size.}\par")
            else:
                width = "14cm" if len(chunk) == 1 and m >= 10 else "9cm" if len(chunk) == 1 else "8.2cm" if len(chunk) <= 4 else "5.7cm"
                for start in range(0, len(chunk), 2):
                    parts.append(r"\noindent\hfill")
                    row = chunk[start:start + 2]
                    column = ".96" if len(row) == 1 else ".48"
                    for record in row:
                        parts += [rf"\begin{{minipage}}[t]{{{column}\textwidth}}\centering",
                                  rf"\resizebox{{{width}}}{{!}}{{\input{{{record['snippet']}}}}}\par",
                                  rf"{{\footnotesize {panel_caption(record, record['index'])}}}\par",
                                  r"\end{minipage}\hfill"]
                    parts.append(r"\par\vspace{2.5mm}")
            pages.append({"page": len(pages) + 1, "m": m, "continuation": continuation + 1,
                          "graph_keys": [record["key"] for record in chunk]})
    if ancestry is not None:
        parts += [r"\clearpage", analysis_document(ancestry, edit_distances)]
        pages += [{"page": len(pages) + 1, "kind": "graph-edits", "graph_keys": []},
                  {"page": len(pages) + 2, "kind": "seven-state-predecessors", "graph_keys": []}]
    parts += [r"\end{document}", ""]
    return "\n".join(parts), pages


def generate(inputs, output, manual_directory=None, max_panels=6, port_labels="small",
             manual_m7_directory=None, overview=False, ancestry_path=None, edit_distances_path=None):
    records, page_info, sources = load_records(inputs)
    output.mkdir(parents=True, exist_ok=True)
    (output / "snippets").mkdir(exist_ok=True)
    (output / "standalone").mkdir(exist_ok=True)
    manual = manual_map(manual_directory)
    manual.update(manual_map(manual_m7_directory))
    ancestry = json.loads(ancestry_path.read_text(encoding="utf-8-sig")) if ancestry_path else None
    edit_distances = json.loads(edit_distances_path.read_text(encoding="utf-8-sig")) if edit_distances_path else None
    grouped, drawings = defaultdict(list), []
    for record in records:
        m = record["m"]
        index = len(grouped[m]) + 1
        basename = f"m{m:02d}-graph-{index:02d}"
        destination = output / "snippets" / f"{basename}.tex"
        if record["key"] in manual:
            picture, positions = manual[record["key"]]["text"], None
            if not show_port_labels(port_labels, m):
                picture = re.sub(r"\s+node\[f1m5 label[^\]]*\]\s*\{\$\s*[01]\s*\$\}", "", picture)
            layout_source = manual[record["key"]]
        else:
            positions = construction_positions(record)
            picture, positions = tikz_picture(record, port_labels, positions)
            layout_source = {"source": "fixed base and expanding root cycle" if record.get("construction") else "family1_graph_atlas.layout and edge_geometry",
                             "sha256": digest(Path(__file__)) if record.get("construction") else digest(Path(__file__).with_name("family1_graph_atlas.py"))}
        destination.write_text(picture, encoding="utf-8", newline="\n")
        wrapper = "\n".join([r"\documentclass[border=3mm]{standalone}", r"\usepackage{tikz}",
                              r"\usetikzlibrary{arrows.meta}", r"\begin{document}",
                              rf"\input{{../snippets/{basename}.tex}}", r"\end{document}", ""])
        (output / "standalone" / f"{basename}.tex").write_text(wrapper, encoding="utf-8", newline="\n")
        record = dict(record, index=index, snippet=f"snippets/{basename}.tex", standalone=f"standalone/{basename}.tex")
        grouped[m].append(record)
        drawings.append(dict(record, port_labels_shown=show_port_labels(port_labels, m),
                             layout_source={key: value for key, value in layout_source.items() if key != "text"},
                             positions_svg=positions, outgoing_ports_verified=2 * m))
    text, pages = atlas_document(grouped, page_info, max_panels, overview, ancestry, edit_distances)
    (output / "atlas.tex").write_text(text, encoding="utf-8", newline="\n")
    manifest = {"schema": 1, "graphs": len(drawings), "page_count": len(pages), "port_labels": port_labels, "sources": sources,
                "description": "All supplied best-certified-lower-bound ties, with exact maxima and unresolved global bounds labeled separately.",
                "manual_m5_directory": str(manual_directory.resolve()) if manual_directory else None,
                "manual_m7_directory": str(manual_m7_directory.resolve()) if manual_m7_directory else None,
                "overview": overview,
                "ancestry_source": {"path": str(ancestry_path.resolve()), "sha256": digest(ancestry_path)} if ancestry_path else None,
                "edit_distances_source": {"path": str(edit_distances_path.resolve()), "sha256": digest(edit_distances_path)} if edit_distances_path else None,
                "pages": pages, "sizes": [page_info[m] for m in range(1, 21)], "drawings": drawings}
    (output / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "graphs.jsonl").write_text("".join(json.dumps(record, separators=(",", ":")) + "\n" for record in drawings), encoding="utf-8")
    readme = """# Family 1 TikZ atlas

`atlas.tex` contains every retained best-certified-bound tie, grouped by size
1 through 20. Global maxima are labeled proved only when the source summary
contains a certificate. Candidate bounds are not claims of global maximality.

Each `snippets/mXX-graph-NN.tex` is a reusable TikZ picture without a caption.
In a paper, load `tikz`, call `\\usetikzlibrary{arrows.meta}`, and use
`\\input{snippets/mXX-graph-NN.tex}`. The root is a double circle; port 0 is
solid and port 1 is dashed. Every node and both outgoing ports are preserved.
The default `--port-labels small` prints per-edge numerals through six states;
larger graphs use the solid/dashed distinction and page legend. Use
`--port-labels all` or `--port-labels none` to change only the redundant numerals.

Compile `atlas.tex` from this directory. Compile an individual wrapper from
the `standalone/` directory, for example:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error atlas.tex
Set-Location standalone
pdflatex -interaction=nonstopmode -halt-on-error m20-graph-01.tex
```

The five-state hand-arranged pictures are copied by verified transition table;
the certified seven-state pictures retain their shared shape embeddings when
`--manual-m7` is supplied. Their original files are not modified. The manifest records every table,
input hash, source layout, score interval, status, and page assignment.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, default=REPO / "figures/family1-atlas")
    parser.add_argument("--manual-m5", type=Path, default=REPO / "figures/family1-m5")
    parser.add_argument("--manual-m7", type=Path, default=REPO / "figures/family1-m7")
    parser.add_argument("--overview", action="store_true")
    parser.add_argument("--ancestry", type=Path, help="Consecutive-size ancestry summary for two analysis pages")
    parser.add_argument("--edit-distances", type=Path, help="Certified consecutive-size edit distances")
    parser.add_argument("--max-panels-per-page", type=int, default=6)
    parser.add_argument("--port-labels", choices=("all", "small", "none"), default="small")
    args = parser.parse_args(argv)
    if not 1 <= args.max_panels_per_page <= 6:
        parser.error("max-panels-per-page must lie in 1..6")
    manifest = generate([path.resolve() for path in args.input], args.out.resolve(),
                        args.manual_m5.resolve(), args.max_panels_per_page, args.port_labels,
                        args.manual_m7.resolve(), args.overview, args.ancestry.resolve() if args.ancestry else None,
                        args.edit_distances.resolve() if args.edit_distances else None)
    print(json.dumps({"graphs": manifest["graphs"], "pages": manifest["page_count"], "out": str(args.out.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

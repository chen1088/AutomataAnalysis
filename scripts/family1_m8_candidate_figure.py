#!/usr/bin/env python3
"""Reusable TikZ comparison of a certified7-state seed and its8-state lift."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from family1_layer_certificate import validate_manifest

REPO = Path(__file__).resolve().parents[1]
KEY = "01020002030403040506000705070206"
ALT = "01020002030403040506010705070206"
BASE = "0001020302030405000604060105"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def reference(path):
    return {"path": str(Path(path).resolve()), "sha256": sha(path)}


def select(path, key):
    values = [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    return next(row for row in values if row["key"] == key)


def verify_word(table, word, mask):
    state = 0
    for letter in word:
        state = table[state][int(letter) ^ ((mask >> state) & 1)]
    return state


def verify_upper(row):
    words, upper, table = row["witness"], row["upper_bound"], row["canonical_table"]
    if (not isinstance(upper, int) or not isinstance(words, list) or len(words) != 2 or words[0] == words[1]
            or any(len(word) != upper or set(word) - {"0", "1"} for word in words)):
        raise ValueError("Invalid candidate upper witness")
    for mask in range(1 << len(table)):
        if verify_word(table, words[0], mask) != verify_word(table, words[1], mask):
            raise ValueError("Upper witness failed independent scalar static-mask replay")


STYLES = r"""x=1cm,y=1cm,
  f1 state/.style={circle,draw=black,fill=white,line width=.55pt,minimum size=6.4mm,inner sep=0pt,font=\small},
  f1 root/.style={f1 state,double,double distance=1.25pt},
  f1 fibre/.style={fill=blue!10},
  f1 port0/.style={-{Latex[length=2mm,width=1.35mm]},line width=.58pt,draw=black},
  f1 port1/.style={f1 port0,dash pattern=on 2.7pt off 1.7pt},
  f1 label/.style={fill=white,inner sep=.6pt,font=\scriptsize},
  f1 title/.style={font=\normalsize\bfseries},
  f1 note/.style={font=\small,align=center}
"""


def draw_graph(base=False, alternate=False):
    positions = {0: (-2, 3), 1: (0, 3), 2: (2, 2.2), 3: (2, .4), 4: (0, .4), 5: (-2, -1.4), 6: (0, -1.4), 7: (2, -1.4)}
    if base:
        positions = {0: positions[0], **{s - 1: positions[s] for s in range(2, 8)}}
    elif alternate:
        positions[0], positions[1] = positions[1], positions[0]
    prefix = "b" if base else "q"
    output = []
    for state, (x, y) in positions.items():
        style = "f1 root" if state == 0 else "f1 state"
        if state == 0 or (not base and state == 1):
            style += ",f1 fibre"
        output.append(rf"\node[{style}] ({prefix}{state}) at ({x},{y}) {{$ {state} $}};")
    def edge(source, target, port, geometry="", label="above"):
        output.append(f"% edge {source} {port} {target}")
        output.append(rf"\draw[f1 port{port}] ({prefix}{source}) to[{geometry}] node[f1 label,{label}] {{$ {port} $}} ({prefix}{target});")
    if base:
        edge(0, 0, 0, "out=125,in=55,loop,looseness=7", "above")
        edge(0, 1, 1, "", "above")
        edge(1, 2, 0, "", "right")
        edge(1, 3, 1, "", "above left")
        edge(2, 2, 0, "loop right,looseness=7", "right")
        edge(2, 3, 1, "", "below")
        edge(3, 4, 0, "", "above left")
        edge(3, 5, 1, "", "right")
        edge(4, 0, 0, "", "left")
        edge(4, 6, 1, "out=-50,in=-130,looseness=1.05", "below")
        edge(5, 4, 0, "", "above")
        edge(5, 6, 1, "bend left=19", "above")
        edge(6, 5, 1, "bend left=19", "below")
        edge(6, 1, 0, "out=0,in=0,looseness=1.35", "right")
    else:
        left, right = (1, 0) if alternate else (0, 1)
        edge(left, right, 0, "bend left=19", "above")
        edge(right, left, 0, "bend left=19", "below")
        edge(left, 2, 1, "out=-45,in=175", "below")
        edge(right, 2, 1, "bend left=9", "above")
        edge(2, 3, 0, "", "right")
        edge(2, 4, 1, "", "above left")
        edge(3, 3, 0, "loop right,looseness=7", "right")
        edge(3, 4, 1, "", "below")
        edge(4, 5, 0, "", "above left")
        edge(4, 6, 1, "", "right")
        edge(5, left, 0, "", "left")
        edge(5, 7, 1, "out=-50,in=-130,looseness=1.05", "below")
        edge(6, 5, 0, "", "above")
        edge(6, 7, 1, "bend left=19", "above")
        edge(7, 6, 1, "bend left=19", "below")
        edge(7, 2, 0, "out=0,in=0,looseness=1.35", "right")
    return "\n".join(output)


def picture(lower, upper, draft=False, single=False, alternate=False):
    parts = ["% Requires \\usepackage{tikz}; \\usetikzlibrary{arrows.meta}.",
             "% Labels0/1 are seed ports. A static mask swaps them independently at each vertex.",
             r"\begin{tikzpicture}[" + STYLES + "]"]
    if not single:
        parts += [r"\begin{scope}", draw_graph(base=True),
                  r"\node[f1 title] at (1,4.45) {(a) Seven-state seed};",
                  r"\node[f1 note] at (1,4.03) {$H(G_7)=34$};", r"\end{scope}",
                  r"\begin{scope}[xshift=8cm]", draw_graph(alternate=alternate),
                  r"\node[f1 title] at (1,4.45) {(b) Eight-state candidate};",
                  rf"\node[f1 note] at (1,4.03) {{${lower}\le H(G_8)\le {upper}$}};", r"\end{scope}",
                  r"\draw[-{Latex[length=2mm]},line width=.65pt] (5.65,.4) -- node[above,font=\small] {$\pi$} (4.35,.4);",
                  r"\node[f1 note] at (5,-3.32) {$\pi(0)=\pi(1)=0,\qquad \pi(s)=s-1\quad(2\le s\le7).$};",
                  r"\node[f1 note,text width=14cm] at (5,-3.9) {The shaded fibre splits the root loop into a two-cycle. The projection respects both ports.};",
                  r"\node[font=\footnotesize,align=center,text width=14cm] at (5,-4.5) {Solid arrows: port $0$. Dashed arrows: port $1$. The double circle marks the root.\\Port labels describe the seed; a static mask swaps them independently by vertex.\\The eight-state exact score and the global maximum remain unresolved.};"]
    else:
        parts += [draw_graph(alternate=alternate), rf"\node[f1 note] at (1,4.1) {{Eight-state candidate: ${lower}\le H(G)\le {upper}$}};"]
    if draft:
        parts.append(r"\node[font=\scriptsize,text=gray] at (5,5) {LAYOUT PREVIEW};")
    parts.append(r"\end{tikzpicture}")
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "output/pdf/family1-m8-search")
    parser.add_argument("--bounds", type=Path, default=REPO / "out/family1-m8-search-v1/root-lift8-scored/records.jsonl")
    parser.add_argument("--extra-upper", action="append", type=Path, default=[])
    parser.add_argument("--lower-report", type=Path, default=REPO / "out/family1-m8-lower34-root-lift/report.json")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()
    baseline_file = REPO / "results/family1-edit-priority/root-lift-candidates.jsonl"
    base_file = REPO / "results/family1-m7/maximizers.jsonl"
    base = select(base_file, BASE)
    if base["status"] != "exact" or base["merge_length"] != 34:
        raise ValueError("Parent exact score changed")
    base_upper = {**base, "upper_bound": 34}; verify_upper(base_upper)
    proof = validate_manifest(args.lower_report.parent / "certificate-run.json", args.lower_report)
    if proof["key"] != KEY:
        raise ValueError("Lower certificate belongs to another graph")
    records = []
    projection_records, upper_records = [], []
    for key in (KEY, ALT):
        lower = select(baseline_file, key)
        scored = select(args.bounds, key)
        upper_sources = [args.bounds]
        verify_upper(scored)
        for extra in args.extra_upper:
            try:
                new = select(extra, key)
            except StopIteration:
                continue
            if new.get("upper_bound") is not None and new["upper_bound"] < scored["upper_bound"]:
                verify_upper(new); scored = new; upper_sources = [extra]
        projection = lower["construction"]["canonical_projection_to_base"]
        flips = lower["construction"]["canonical_mask_lift_xor"]
        table = scored["canonical_table"]
        if "".join(f"{target:02d}" for row in table for target in row) != key:
            raise ValueError("Figure key/table mismatch")
        for mask in range(128):
            lifted = sum((((mask >> projection[s]) & 1) ^ flips[s]) << s for s in range(8))
            for s in range(8):
                for bit in range(2):
                    if projection[table[s][bit ^ ((lifted >> s) & 1)]] != base["canonical_table"][projection[s]][bit ^ ((mask >> projection[s]) & 1)]:
                        raise ValueError("Projection/static mask lift failed")
        certified_lower = proof["lower_bound"] if key == KEY else lower["lower_bound"]
        records.append({"m": 8, "key": key, "canonical_table": table, "lower_bound": certified_lower,
                        "upper_bound": scored["upper_bound"], "witness": scored["witness"], "exact_score_certified": False,
                        "global_maximum_certified": False, "status": "bounded", "projection": projection, "mask_lift_xor": flips,
                        "upper_sources": [reference(path) for path in upper_sources], "projection_source": reference(baseline_file),
                        "lower_report": reference(args.lower_report) if key == KEY else None})
        projection_records.append(lower); upper_records.append(scored)
    for text, record in ((draw_graph(base=True), base), (draw_graph(), records[0]), (draw_graph(alternate=True), records[1])):
        actual = [tuple(map(int, item)) for item in re.findall(r"^% edge (\d+) (\d+) (\d+)$", text, re.MULTILINE)]
        expected = {(source, port, target) for source, row in enumerate(record["canonical_table"]) for port, target in enumerate(row)}
        if len(actual) != len(expected) or set(actual) != expected:
            raise ValueError("TikZ does not draw every seed port exactly once")
    args.out.mkdir(parents=True, exist_ok=True)
    primary, alternate = records
    for name, text in (("snippet.tex", picture(primary["lower_bound"], primary["upper_bound"], args.draft)),
                       ("snippet-candidate.tex", picture(primary["lower_bound"], primary["upper_bound"], single=True)),
                       ("snippet-alternate.tex", picture(alternate["lower_bound"], alternate["upper_bound"], single=True, alternate=True))):
        (args.out / name).write_text(text, encoding="utf-8")
    (args.out / "candidate.tex").write_text(r"""\documentclass[tikz,border=6pt]{standalone}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{amsmath}
\usetikzlibrary{arrows.meta}
\begin{document}
\input{snippet.tex}
\end{document}
""", encoding="utf-8")
    data = {"schema": 1, "candidate": primary, "alternate_root": alternate, "parent": base,
            "parent_source": reference(base_file), "lower_certificate_manifest": reference(args.lower_report.parent / "certificate-run.json"),
            "lower_certificate_summary": proof, "layout": "two-panels-aligned-projection-fibres-v1", "draft": args.draft,
            "generator": reference(Path(__file__)), "upper_bound_records": upper_records,
            "projection_records": projection_records,
            "certificate_run_manifest": json.loads((args.lower_report.parent / "certificate-run.json").read_text()),
            "validation": {"tikz_all_port_occurrences_verified": True, "projection_base_masks": 128,
                           "independent_scalar_upper_masks_per_graph": 256, "mask_bits_static_on_revisits": True}}
    (args.out / "records.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if args.compile:
        compiler = shutil.which("pdflatex") or str(Path(os.environ["APPDATA"]) / "TinyTeX/bin/windows/pdflatex.exe")
        build = REPO / "tmp/pdfs/family1-m8-search-build"; build.mkdir(parents=True, exist_ok=True)
        process = subprocess.run([compiler, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", f"-output-directory={build}", "candidate.tex"], cwd=args.out, capture_output=True, text=True)
        (build / "compile.log").write_text(process.stdout + process.stderr, encoding="utf-8")
        if process.returncode:
            raise RuntimeError(f"TikZ compilation failed: {build / 'compile.log'}")
        shutil.copy2(build / "candidate.pdf", args.out / "candidate.pdf")
    manifest = {"schema": 1, "files": {path.name: {"sha256": sha(path), "bytes": path.stat().st_size}
                                      for path in sorted(args.out.iterdir()) if path.is_file() and path.name != "manifest.json"}}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "lower_bound": primary["lower_bound"], "upper_bound": primary["upper_bound"], "compiled": args.compile}))


if __name__ == "__main__":
    main()

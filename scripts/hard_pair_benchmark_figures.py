#!/usr/bin/env python3
"""Render every positive final benchmark record and index every miss.

Reads saved fixtures/results; launches no search or random generator. Every
positive undergoes independent scalar replay against the complete saved DFA
family. Only its base graphs are drawn. The full local gallery stays in out/.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

import hard_pair_witness_figure as drawing


REPO = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def row_digest(row):
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def output_reference(path, root):
    result = drawing.reference(path)
    result["path"] = path.relative_to(root).as_posix()
    require(result["bytes"] <= 1 << 20, f"Generated file exceeds 1 MiB: {path}")
    return result


def build_gallery(benchmark, destination):
    fixtures_path = benchmark / "fixtures.json"
    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8-sig"))
    cases = {case["id"]: case for case in fixtures["cases"]}
    require(len(cases) == len(fixtures["cases"]) and cases, "Missing/duplicate benchmark fixture ids")
    record_paths = sorted(benchmark.glob("records-*.jsonl"))
    require(bool(record_paths), "No final records-*.jsonl inputs")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Use a fresh gallery directory")
    destination.mkdir(parents=True, exist_ok=True)
    fixture_reference = drawing.reference(fixtures_path)
    generator_reference = drawing.reference(Path(__file__))
    renderer_reference = drawing.reference(Path(drawing.__file__))
    geometry_reference = drawing.reference(Path(drawing.atlas.__file__))
    input_paths = {fixtures_path, *record_paths, *benchmark.glob("run-*.json")}
    if (benchmark / "summary.json").is_file():
        input_paths.add(benchmark / "summary.json")
    inputs = [drawing.reference(path) for path in sorted(input_paths)]
    source_references = {item["path"]: item for item in inputs}
    index, manifest_rows, files = [], [], []
    totals = Counter()
    groups = []
    for record_path in record_paths:
        match = re.fullmatch(r"records-(.+)-k(\d+)\.jsonl", record_path.name)
        require(match is not None, f"Unrecognized final record filename: {record_path.name}")
        mode, file_k = match.group(1), int(match.group(2))
        rows = [json.loads(line) for line in record_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        require(len(rows) == len(cases) and {row["id"] for row in rows} == set(cases),
                f"File does not contain every fixture exactly once: {record_path}")
        source = source_references[str(record_path.resolve())]
        group_rows = []
        for line_number, row in enumerate(rows, 1):
            case = cases[row["id"]]
            require(re.fullmatch(r"[A-Za-z0-9_.-]+", row["id"]) is not None, "Unsafe figure id")
            require(row["k"] == file_k and row["alphabet"] == drawing.ALPHABET,
                    "Record k/alphabet disagrees with its file")
            require(row["family_size"] == case["family_size"] == len(case["family"]), "Fixture family size mismatch")
            require(case.get("bases") and len(case["bases"]) <= 4, "Missing base graphs or too many for one complete plate")
            totals["rows"] += 1
            entry = {"source_file": record_path.name, "source_line": line_number, "row_sha256": row_digest(row),
                     "mode": mode, "id": row["id"], "kind": row["kind"], "k": row["k"],
                     "ranking": row.get("ranking", row.get("score", "total-D,lex")),
                     "startup": json.dumps(row.get("startup"), sort_keys=True, separators=(",", ":")),
                     "family_size": row["family_size"], "base_graphs": len(case["bases"]),
                     "upper_bound": row["upper_bound"], "reference_H": row.get("reference_H"),
                     "reference_k": "N/A", "reference_upper": row.get("reference_upper"),
                     "gap": row.get("gap"), "gap_to_known_upper": row.get("gap_to_known_upper"),
                     "ratio": row.get("ratio"), "first": "", "second": "", "first_difference_position": None,
                     "figure": "", "witness_record": "", "outcome": "miss"}
            pin = {key: entry[key] for key in ("source_file", "source_line", "row_sha256", "mode", "id", "k", "ranking", "startup")}
            if row["witness"] is None:
                require(row["upper_bound"] is None and row.get("verified_d_trace") is None,
                        "Miss has a numeric upper or positive trace")
                totals["misses"] += 1
                pin["outcome"] = "miss"
            else:
                certificate = drawing.witness_record(row, case["family"],
                    {"source": fixture_reference, "case_id": case["id"]})
                require(certificate["length"] == row["upper_bound"], "Witness/upper mismatch")
                if row.get("reference_H") is not None:
                    require(row["gap"] == certificate["length"] - row["reference_H"], "Saved gap mismatch")
                certificate["source"] = source
                certificate["source_line"] = line_number
                certificate["source_row_sha256"] = entry["row_sha256"]
                certificate["generator"] = renderer_reference
                certificate["gallery_generator"] = generator_reference
                certificate["graph_geometry_source"] = geometry_reference
                certificate["base_dfas"] = case["bases"]
                certificate["drawn_graphs_are_base_dfas"] = True
                leaf = destination / f"{mode}-k{row['k']}" / row["id"]
                leaf.mkdir(parents=True, exist_ok=False)
                witness_path, svg_path = leaf / "witness.json", leaf / "witness.svg"
                witness_path.write_text(json.dumps(certificate, indent=2) + "\n", encoding="utf-8")
                svg_path.write_text(drawing.figure_svg(certificate, case["bases"]), encoding="utf-8")
                witness_ref, svg_ref = output_reference(witness_path, destination), output_reference(svg_path, destination)
                files.extend((witness_ref, svg_ref))
                pin.update({"outcome": "verified-upper", "witness_record": witness_ref, "figure": svg_ref})
                entry.update({"outcome": "verified-upper", "first": certificate["first"], "second": certificate["second"],
                              "first_difference_position": certificate["first_difference_position"],
                              "figure": svg_ref["path"], "witness_record": witness_ref["path"]})
                totals["positive_figures"] += 1
                totals["scalar_dfa_replays"] += certificate["family_size"]
                totals["scalar_prefix_updates"] += certificate["family_size"] * certificate["length"]
            manifest_rows.append(pin)
            index.append(entry)
            group_rows.append(entry)
        groups.append({"source_file": record_path.name, "rows": group_rows})
    csv_path = destination / "index.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(index[0]))
        writer.writeheader()
        writer.writerows(index)
    markdown = ["# Full hard-pair benchmark witness gallery", "",
        f"All {totals['rows']} final records are indexed: **{totals['positive_figures']} independently verified positive figures** and **{totals['misses']} retained misses**.", "",
        "Every SVG shows both words, the complete prefix D trace, joint k, startup/ranking, and family size. Only the saved base graphs are drawn; the entire saved family is scalar-replayed. Permutation ranking is experimental. A positive is a search upper witness; exact H and L−H come from the separately labeled reference (reference k=N/A).", "",
        "[CSV index, including both words and all misses](index.csv) · [Every row/input/output hash](manifest.json)", ""]
    for group in groups:
        markdown += [f"## {group['source_file']}", "",
                    "| Case | Joint k | DFAs | Upper L | Reference H (k=N/A) | L−H | Outcome / records |",
                    "|---|---:|---:|---:|---:|---:|---|"]
        for entry in group["rows"]:
            outcome = "miss (no figure)" if not entry["figure"] else f"[SVG]({entry['figure']}) · [pair and D trace]({entry['witness_record']})"
            reference_h = entry["reference_H"] if entry["reference_H"] is not None else "unknown; upper " + str(entry["reference_upper"])
            markdown.append(f"| {entry['id']} | {entry['k']} | {entry['family_size']} | {entry['upper_bound'] if entry['upper_bound'] is not None else '—'} | {reference_h} | {entry['gap'] if entry['gap'] is not None else '—'} | {outcome} |")
        markdown.append("")
    markdown += ["Reproduce from the repository root:", "", "```bash",
                 "python3 scripts/hard_pair_benchmark_figures.py \\",
                 f"  --benchmark {benchmark.relative_to(REPO).as_posix() if benchmark.is_relative_to(REPO) else benchmark.as_posix()} \\",
                 "  --out out/hard-pair-joint-benchmark-figures-20261026", "```", ""]
    markdown_path = destination / "index.md"
    markdown_path.write_text("\n".join(markdown), encoding="utf-8")
    files += [output_reference(csv_path, destination), output_reference(markdown_path, destination)]
    manifest = {"schema": 1, "benchmark": str(benchmark.resolve()), "generator": generator_reference,
                "witness_renderer": renderer_reference, "graph_geometry_source": geometry_reference,
                "counts": dict(totals), "input_files": inputs, "outputs": files,
                "row_hash_encoding": "sha256 of UTF-8 json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False)",
                "ordered_row_hashes_sha256": hashlib.sha256("\n".join(row["row_sha256"] for row in manifest_rows).encode()).hexdigest(),
                "all_supplied_rows_indexed": True, "all_positive_families_scalar_replayed": True,
                "partial_gallery": False, "base_graphs_only": True, "search_launched": False,
                "randomness_used": False, "reference_k": None, "rows": manifest_rows}
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    require(manifest_path.stat().st_size <= 1 << 20, "Gallery manifest exceeds 1 MiB")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=REPO / "results/hard-pair-joint-benchmark-20261026")
    parser.add_argument("--out", type=Path, default=REPO / "out/hard-pair-joint-benchmark-figures-20261026")
    args = parser.parse_args()
    manifest = build_gallery(args.benchmark.resolve(), args.out.resolve())
    print(json.dumps({"out": str(args.out), "joint_k": sorted({row["k"] for row in manifest["rows"]}),
                      **manifest["counts"], "manifest": drawing.reference(args.out / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()

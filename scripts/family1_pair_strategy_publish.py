#!/usr/bin/env python3
"""Publish compact complete refinement or broader-validation tables."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil

from family1_pair_refine_benchmark import ref, rows, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--kind", choices=["refinement", "heldout", "development"], required=True)
    args = parser.parse_args()
    assert not args.out.exists() or not any(args.out.iterdir()), "Use a fresh publication directory"
    args.out.mkdir(parents=True, exist_ok=True)
    summary = json.loads((args.source / "summary.json").read_text())
    manifest = json.loads((args.source / "manifest.json").read_text())
    seal = json.loads((args.source / "query-seal.json").read_text())
    for name in ["summary.json", "cases.csv"]:
        shutil.copy2(args.source / name, args.out / name)
    save(args.out / "run.json", manifest)
    save(args.out / "query-audit.json", seal)
    cases = rows(args.source / "input-cases.jsonl")
    if args.kind == "refinement":
        fields = ["id", "m", "key", "input_joint_k", "first", "second", "source_path", "source_sha256"]
        inputs = [{"id": row["id"], "m": row["m"], "key": row["key"], "input_joint_k": row["input_joint_k"],
                   "first": row["input_witness"][0], "second": row["input_witness"][1],
                   "source_path": row["source"]["path"], "source_sha256": row["source"]["sha256"]} for row in cases]
        validation = {"all_output_and_local_positive_pairs_scalar_verified": True,
                      "verification": summary["verification"],
                      "self_test": json.loads((args.source / "self-test.json").read_text()),
                      "partial_evaluated_neighborhoods": sum(row["partial_evaluated_neighborhoods"] for row in summary["modes"]),
                      "budget_refused_cases": sum(row["budget_refused_cases"] for row in summary["modes"]),
                      "source_manifest": ref(args.source / "manifest.json"),
                      "query_seal": ref(args.source / "query-seal.json"),
                      "complete_rows": len(list(csv.DictReader((args.out / "cases.csv").open())))}
    else:
        fields = ["m", "key", "training_overlap", "canonical_table"]
        inputs = [{**row, "canonical_table": json.dumps(row["canonical_table"], separators=(",", ":"))} for row in cases]
        validation = {"all_final_positive_pairs_scalar_verified": True,
                      "independent_mask_replays": summary["independent_mask_replays"],
                      "source_manifest": ref(args.source / "manifest.json"),
                      "query_seal": ref(args.source / "query-seal.json"),
                      "complete_rows": len(list(csv.DictReader((args.out / "cases.csv").open()))),
                      "all_cases_scored": summary["all_cases_scored"],
                      "scope": "initial scored-seed heldout" if args.kind == "heldout" else "post-hoc development reuse of the original heldout pool"}
        optional = args.source / "portfolio-summary.json"
        if optional.exists():
            shutil.copy2(optional, args.out / "analysis.json")
        worst = args.source / "worst-cases.json"
        if worst.exists():
            values = json.loads(worst.read_text())
            with (args.out / "worst-cases.csv").open("w", newline="") as stream:
                columns = ["m", "key", "H", "original_upper", "compact_upper", "min_gap",
                           "original_first", "original_second", "compact_first", "compact_second"]
                writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader()
                for row in values:
                    writer.writerow({key: row[key] for key in ["m", "key", "H", "original_upper", "compact_upper", "min_gap"]} |
                                     {"original_first": row["original_witness"][0], "original_second": row["original_witness"][1],
                                      "compact_first": row["compact_witness"][0], "compact_second": row["compact_witness"][1]})
    with (args.out / "input-cases.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(inputs)
    validation["publisher"] = ref(Path(__file__))
    save(args.out / "validation.json", validation)
    files = sorted(path for path in args.out.iterdir() if path.is_file())
    assert all(path.stat().st_size <= 1048576 for path in files)
    save(args.out / "publication-manifest.json", {"files": [{"path": path.name, **{k: v for k, v in ref(path).items() if k != "path"}}
                                                         for path in files]})
    print(json.dumps({"out": str(args.out), "kind": args.kind, "complete_rows": validation["complete_rows"],
                      "files": len(files) + 1, "all_files_under_1MiB": True}))


if __name__ == "__main__":
    main()

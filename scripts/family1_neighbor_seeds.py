#!/usr/bin/env python3
"""Export certified near-top small seeds and unresolved possible near-top seeds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from family1_study import REPO, compact, file_hash, fixed_key


def build(small_journal, seven_journal, output, margin=2):
    maxima = {1: 1, 2: 3, 3: 6, 4: 10, 5: 15, 6: 23, 7: 34}
    winners_path = REPO / "results/family1-m7/maximizers.jsonl"
    winners = {row["key"]: row for line in winners_path.read_text().splitlines() if (row := json.loads(line))}
    records = []
    counts = {m: 0 for m in maxima}
    for source, sizes in ((small_journal, range(1, 7)), (seven_journal, [7])):
        with source.open(encoding="utf-8-sig") as stream:
            for line in stream:
                # Skip almost all large journal records without parsing their tables.
                if source == seven_journal:
                    start = line.index('"upper_bound":') + len('"upper_bound":')
                    upper_text = line[start:line.index(',', start)]
                    if upper_text != "null" and int(upper_text) < maxima[7] - margin:
                        continue
                row = json.loads(line)
                m = row["m"]
                if m not in sizes:
                    continue
                upper = row.get("upper_bound", row.get("merge_length"))
                if upper is not None and upper < maxima[m] - margin:
                    continue
                key = fixed_key(row["canonical_table"])
                if m == 7 and key in winners:
                    row = dict(winners[key])
                row["key"] = key
                row["upper_bound"] = row.get("upper_bound", row.get("merge_length"))
                certain = row["lower_bound"] >= maxima[m] - margin
                row["neighbor_seed_selection"] = {
                    "previous_global_maximum": maxima[m], "score_margin": margin,
                    "threshold": maxima[m] - margin,
                    "status": "certified-near-top" if certain else "possible-near-top-unresolved",
                    "note": "Generation priority only; this does not exclude any unselected graph from global optimality.",
                }
                counts[m] += 1
                records.append(row)
    records.sort(key=lambda row: (row["m"], row["key"]))
    if margin == 2 and list(counts.values()) != [1, 6, 25, 48, 139, 69, 55]:
        raise ValueError(f"source coverage changed: {counts}")
    output.mkdir(parents=True, exist_ok=True)
    target = output / "near-top.jsonl"
    target.write_text("".join(compact(row) + "\n" for row in records), encoding="utf-8")
    summary = {"schema": 1, "method": "certified-upper-aware-near-top-priority", "margin": margin,
               "counts": counts, "records": len(records), "global_pruning_rule": False,
               "sources": [{"path": str(path.relative_to(REPO)), "sha256": file_hash(path)}
                           for path in (small_journal, seven_journal, winners_path)],
               "output_sha256": file_hash(target),
               "unresolved_note": "Seven-state upper >=32 permits near-optimality; only a sufficient lower bound certifies it."}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--small-journal", type=Path, default=REPO / "out/family1-m1-m6/graphs.jsonl")
    parser.add_argument("--seven-journal", type=Path, default=REPO / "out/family1-m7-global-certificate-v3/refined-checkpoint.jsonl")
    parser.add_argument("--out", type=Path, default=REPO / "results/family1-neighbor-seeds")
    parser.add_argument("--margin", type=int, default=2)
    args = parser.parse_args()
    if args.margin < 0:
        parser.error("margin must be nonnegative")
    result = build(args.small_journal.resolve(), args.seven_journal.resolve(), args.out.resolve(), args.margin)
    print(json.dumps({"records": result["records"], "counts": result["counts"]}))


if __name__ == "__main__":
    main()

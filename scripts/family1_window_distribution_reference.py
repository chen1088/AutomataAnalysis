#!/usr/bin/env python3
"""Exact scalar distributions of agreement gains over every length-k window.

This is a word-pair diagnostic, not a search over graphs or a lower-bound
certificate. Every static mask and all 2^k windows are evaluated explicitly.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
from pathlib import Path
import statistics

REPO = Path(__file__).resolve().parents[1]


def endpoint(table, mask, word, state=0):
    for symbol in word:
        state = table[state][int(symbol) ^ ((mask >> state) & 1)]
    return state


def describe(values):
    return {"count": len(values), "min": min(values), "mean": statistics.fmean(values),
            "median": statistics.median(values), "max": max(values),
            "population_stddev": statistics.pstdev(values), "range": max(values) - min(values),
            "zero_count": sum(value == 0 for value in values),
            "positive_count": sum(value > 0 for value in values)}


def distribution(table, first, second, k, *, label, ordinal=None, stage=0, expected_S=None):
    assert first != second and len(first) == len(second) > 0
    m, masks = len(table), 1 << len(table)
    left = [endpoint(table, mask, first) for mask in range(masks)]
    right = [endpoint(table, mask, second) for mask in range(masks)]
    initial = sum(a == b for a, b in zip(left, right))
    if expected_S is not None:
        assert initial == expected_S
    remaining = masks - initial
    windows = list(map("".join, itertools.product("01", repeat=k)))
    scores = []
    for window in windows:
        score = sum(endpoint(table, mask, window, left[mask]) == endpoint(table, mask, window, right[mask])
                    for mask in range(masks))
        assert initial <= score <= masks
        scores.append(score)
    drops = [value - initial for value in scores]
    normalized = [value / remaining for value in drops] if remaining else None
    return {"label": label, "m": m, "ordinal": ordinal, "canonical_table": table,
            "initial_words": [first, second], "initial_word_length": len(first),
            "common_suffix_stage": stage, "window_k": k, "window_count": 1 << k,
            "score_scope": "full", "total_masks": masks, "initial_S": initial,
            "remaining_coordinates": remaining, "window_order": "lexicographic-0-before-1",
            "windows": windows, "drop_vector": drops, "scores_after": scores,
            "normalized_drop_vector": normalized,
            "drop_histogram": {str(value): count for value, count in sorted(Counter(drops).items())},
            "drop_stats": describe(drops), "normalized_drop_stats": describe(normalized) if normalized is not None else None,
            "complete_merge_windows": sum(value == masks for value in scores),
            "claim": "Exact distribution for this particular graph, pair and window length; no graph-search or generic concentration claim."}


def reference(path):
    path = Path(path)
    return {"path": path.relative_to(REPO).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run(args):
    cases = []
    plateau = ((0, 1), (1, 2), (0, 0))
    for k in (1, 2, 4):
        cases.append(distribution(plateau, "01", "10", k, label=f"plateau-k{k}", expected_S=4))
    known = [json.loads(line) for line in args.source.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    assert len(known) == 8
    for index, record in enumerate(known, 1):
        table = record["canonical_table"]
        first, second = record["initial_words"]
        for stage in (0, 8, 16, 24):
            if stage > len(record["suffix"]):
                continue
            suffix = record["suffix"][:stage]
            case = distribution(table, first + suffix, second + suffix, 4,
                                label=f"m7-class{index}-stage{stage}-k4", ordinal=record["ordinal"],
                                stage=stage, expected_S=record["full_score_trace"][stage])
            if len(first) + stage + 4 < 34:
                assert case["complete_merge_windows"] == 0
            case["source_prefix_words"] = [first, second]
            case["source_known_common_suffix"] = record["suffix"]
            cases.append(case)
    first = known[0]
    cases.append(distribution(first["canonical_table"], *first["initial_words"], 8,
                              label="m7-class1-stage0-k8", ordinal=first["ordinal"], expected_S=first["full_score_trace"][0]))
    assert len(cases) == 25
    assert cases[0]["drop_vector"] == [0, 0]
    assert cases[1]["drop_vector"] == [4, 0, 0, 4]
    assert all(case["window_count"] == len(case["windows"]) == len(case["drop_vector"]) for case in cases)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "cases.jsonl").write_text("".join(json.dumps(case, separators=(",", ":")) + "\n" for case in cases), encoding="utf-8")
    summary = {"schema": 1, "method": "independent-scalar-all-static-masks-all-length-k-common-windows",
               "definition": "D(w)=S_G(u w,v w)-S_G(u,v)", "cases": len(cases),
               "total_window_evaluations": sum(case["window_count"] for case in cases),
               "all_masks_enumerated": True, "all_windows_enumerated": True,
               "source": reference(args.source), "generator": reference(Path(__file__).resolve()),
               "scope": "Pair-specific exact finite distributions; no general conclusion about rich families or larger graphs.",
               "case_stats": [{name: case[name] for name in ("label", "m", "ordinal", "common_suffix_stage", "window_k", "window_count", "initial_S", "remaining_coordinates", "drop_stats", "normalized_drop_stats", "complete_merge_windows")} for case in cases]}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    columns = ["label", "m", "ordinal", "stage", "k", "S", "remaining", "min", "mean", "median", "max", "stddev", "zero_windows", "window_count", "normalized_mean", "normalized_stddev", "complete_merge_windows"]
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for case in cases:
            stats, norm = case["drop_stats"], case["normalized_drop_stats"]
            writer.writerow({"label": case["label"], "m": case["m"], "ordinal": case["ordinal"], "stage": case["common_suffix_stage"], "k": case["window_k"], "S": case["initial_S"], "remaining": case["remaining_coordinates"],
                             **{field: stats[field] for field in ("min", "mean", "median", "max")}, "stddev": stats["population_stddev"], "zero_windows": stats["zero_count"], "window_count": case["window_count"],
                             "normalized_mean": norm["mean"] if norm else None, "normalized_stddev": norm["population_stddev"] if norm else None, "complete_merge_windows": case["complete_merge_windows"]})
    lines = ["# Exact common-window gain distributions", "",
             "Every mask and every length-k binary window is evaluated by ordinary scalar simulation. D(w) counts newly agreeing coordinates. Normalized gains divide by the coordinates still unequal before the window. Counts and vectors concern these specific pairs, rather than a random sample or a theorem about graph richness.", "",
             "| Case | S / total | Remaining | k | Gain min / mean / max | Stddev | Zero windows |",
             "|---|---:|---:|---:|---|---:|---:|"]
    for case in cases:
        s=case["drop_stats"]
        lines.append(f"| {case['label']} | {case['initial_S']}/{case['total_masks']} | {case['remaining_coordinates']} | {case['window_k']} | {s['min']} / {s['mean']:.4g} / {s['max']} | {s['population_stddev']:.4g} | {s['zero_count']}/{s['count']} |")
    lines.extend(["", "`cases.jsonl` retains all window strings, full gain vectors, endpoint-agreement counts, normalized gains, histograms, and summary statistics. `summary.csv` is intended for plotting. Seven-state stages append 0,8,16,24 letters of the previously saved common suffix whenever that stage exists. Original common prefixes are retained in the two words; no cancellation is used.", "",
                  "```powershell", "uv run --no-project python scripts/family1_window_distribution_reference.py", "```", "",
                  "These are scalar reference distributions, not native performance measurements. No witness search or global maximum is certified by this diagnostic.", ""])
    (args.output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"cases": len(cases), "window_evaluations": summary["total_window_evaluations"], "output": str(args.output)}))
    for label in ("plateau-k1", "plateau-k2", "plateau-k4", "m7-class1-stage0-k4", "m7-class1-stage24-k4", "m7-class1-stage0-k8"):
        case = next(case for case in cases if case["label"] == label)
        print(json.dumps({"label": label, "S": case["initial_S"], "remaining": case["remaining_coordinates"], "histogram": case["drop_histogram"], "stats": case["drop_stats"], "normalized": case["normalized_drop_stats"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=REPO / "results/family1-guided-validation/known-m7-traces.jsonl")
    parser.add_argument("--output", type=Path, default=REPO / "results/family1-window-distributions")
    run(parser.parse_args())


if __name__ == "__main__":
    main()

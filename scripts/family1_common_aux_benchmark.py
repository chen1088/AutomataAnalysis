#!/usr/bin/env python3
"""Fixed deterministic COMMON-suffix auxiliary, never joint-alphabet coverage."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from family1_pair_refine_benchmark import REPO, ref, replay, rows, save, save_rows

BAD_M7 = "0102000304050203000604050003"
HELD_M8 = "01020003040501060003020705060407"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "out/family1-finder-strategies-20261026/common-aux")
    parser.add_argument("--input", type=Path, action="append", help="Geometry source; default is the two committed winner-table files")
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/joint-solid-linux/Family1Offline")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--resume-native", action="store_true", help="Validate completed native batches and redo analysis without querying")
    args = parser.parse_args()
    if not args.input:
        args.input = [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"]
    assert args.jobs > 0 and (args.resume_native or not (args.out / "manifest.json").exists())
    args.out.mkdir(parents=True, exist_ok=True)
    evidence = args.out / "evidence"
    evidence.mkdir(exist_ok=True)
    exe = evidence / "Family1Offline"
    if not exe.exists():
        shutil.copy2(args.exe, exe)
    cases = []
    for path in args.input:
        for row in rows(path):
            table = row.get("canonical_table")
            key = "".join(f"{q:02d}" for ports in table for q in ports) if table else row["key"]
            cases.append({"m": row["m"], "key": key})
    assert len(cases) == 20 and len({row["key"] for row in cases}) == 20
    cases += [{"m": 7, "key": BAD_M7}, {"m": 8, "key": HELD_M8}]
    cases.sort(key=lambda row: (row["m"], row["key"]))
    if args.resume_native:
        assert rows(args.out / "input-cases.jsonl") == cases
    else:
        save_rows(args.out / "input-cases.jsonl", cases)
    pending, copied = ["family1_offline.cpp"], set()
    while pending:
        name = pending.pop()
        if name in copied:
            continue
        path = REPO / name
        if not args.resume_native:
            shutil.copy2(path, evidence / path.name)
        copied.add(name)
        pending += [item for item in re.findall(r'#include "([^"]+)"', path.read_text()) if (REPO / item).is_file()]
    for path in REPO.glob("Family1*.cpp"):
        if path.name in ["Family1ExactPacked.cpp", "Family1LargeGraph.cpp", "Family1EditSearch.cpp", "Family1SeedGraphs.cpp"]:
            if not args.resume_native:
                shutil.copy2(path, evidence / path.name)
    if not args.resume_native:
        shutil.copy2(__file__, evidence / "driver.py")
    constants = ["--heuristics", "on", "--exact-depth", "24", "--max-layer-states", "16777216",
                 "--memory-mib", "256", "--per-graph-ms", "0", "--wall-seconds", "0", "--max-graphs", "0",
                 "--beam", "8", "--prefix-depth", "20", "--prefix-words", "1048576", "--prefix-pairs", "128",
                 "--common-prefix-depth", "8", "--tail-threshold", "8", "--tail-states", "50000",
                 "--tail-depth", "80", "--expansions", "2000000", "--max-length", "80", "--target-upper", "0"]
    manifest = {"schema": 1, "input_cases": ref(args.out / "input-cases.jsonl"), "case_count": 22,
                "geometry_sources": [ref(path) for path in args.input],
                "configured_common_ks": [8, 12], "common_alphabet": ["00", "11"],
                "coverage": "restricted suffix after distinct graph-derived prefixes; not full-joint search",
                "leaves_per_full_window": "2^k, not 4^k", "native_executable": ref(exe),
                "fixed_arguments": constants, "target_labels_used_in_queries": False,
                "randomness": False, "time_caps": False, "sources": [ref(path) for path in sorted(evidence.iterdir())]}
    if args.resume_native:
        original_manifest = json.loads((args.out / "manifest.json").read_text())
        assert original_manifest["fixed_arguments"] == constants and original_manifest["case_count"] == 22
        assert original_manifest["native_executable"]["sha256"] == ref(exe)["sha256"]
    else:
        save(args.out / "manifest.json", manifest)
    tasks = []
    for k in [8, 12]:
        for m in range(1, 9):
            keys = [row["key"] for row in cases if row["m"] == m]
            for index in range(0, len(keys), 3):
                tasks.append((k, m, index // 3, keys[index:index + 3]))
    started = time.monotonic()

    def run(task):
        k, m, index, keys = task
        directory = args.out / f"common-k{k}" / f"m{m}-batch-{index}"
        command = [str(exe), "--m", str(m), "--out", str(directory),
                   "--window", str(k), "--max-window", str(k)] + constants
        for key in keys:
            command += ["--graph", key]
        before = time.monotonic()
        if args.resume_native:
            assert json.loads((directory / "command.json").read_text()) == command
            summary = json.loads((directory / "summary.json").read_text())
            # This older CLI reserves scoring_complete for exact scores;
            # bounded heuristic results still count as completed evaluations.
            assert summary["evaluated_graphs"] == len(keys)
            assert summary["pending_graphs"] == summary["unfinished_graphs"] == 0
            assert summary["stopped_by_budget_or_interrupt"] is False
        else:
            process = subprocess.run(command, capture_output=True, text=True, check=True)
            save(directory / "command.json", command)
            (directory / "console.txt").write_text(process.stdout + process.stderr)
        values = rows(directory / "records.jsonl")
        assert [row["key"] for row in values] == keys
        for row in values:
            assert row["heuristics"] is True
            if row["prefix_attempts"] == 0 and row["expanded_nodes"] == 0:
                assert row["status"] == "exact" and row["window_k"] == 0
            else:
                assert row["window_k"] == k
            for report in row["window_distributions"]:
                assert 0 <= report["window_k"] <= k
                assert report["window_count"] <= 1 << report["window_k"]
                assert report["expanded_nodes"] <= (1 << (report["window_k"] + 1)) - 2
                if report["complete"]:
                    assert report["window_count"] == 1 << report["window_k"]
                    assert report["expanded_nodes"] == (1 << (report["window_k"] + 1)) - 2
                assert sum(count for _, count in report["histogram"]) == report["window_count"]
        return k, m, index, values, time.monotonic() - before

    results = {8: [], 12: []}
    timings = []
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures = [workers.submit(run, task) for task in tasks]
        for future in as_completed(futures):
            k, m, index, values, seconds = future.result()
            results[k] += values
            timings.append({"common_k": k, "m": m, "batch": index, "seconds": seconds})
            save(args.out / "progress.json", {"completed_batches": len(timings), "total_batches": len(tasks),
                                             "graphs": sum(len(value) for value in results.values()),
                                             "seconds": time.monotonic() - started})
    raw = []
    for k in [8, 12]:
        results[k].sort(key=lambda row: (row["m"], row["key"]))
        assert [(row["m"], row["key"]) for row in results[k]] == [(row["m"], row["key"]) for row in cases]
        path = args.out / f"native-common-k{k}.jsonl"
        save_rows(path, results[k])
        raw.append(ref(path))
    save(args.out / "query-seal.json", {"manifest": ref(args.out / "manifest.json"),
                                      "native_outputs": raw, "all44queries_completed": True, "truth_read": False})
    # Exhaustive benchmark scores and known uppers are attached only now.
    truth = {}
    truth_paths = [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"]
    for path in truth_paths:
        for row in rows(path):
            key = "".join(f"{q:02d}" for ports in row["canonical_table"] for q in ports)
            truth[key] = row["merge_length"]
    csv_rows, summary_modes = [], []
    mask_checks = 0
    for k in [8, 12]:
        values = results[k]
        for row in values:
            row["configured_common_k"] = k
            row["common_alphabet"] = ["00", "11"]
            row["strategy_scope"] = "auxiliary restricted common suffix after distinct prefixes"
            exact_prescore = row["status"] == "exact" and row["prefix_attempts"] == 0 and row["expanded_nodes"] == 0
            row["producing_k"] = None if exact_prescore else k
            row["producing_window"] = "exact-word-layers" if exact_prescore else "common-suffix-with-conditional-exact-tail"
            if row["upper_bound"] is not None:
                trace, checks = replay(row["key"], row["witness"])
                row["witness_metric_trace"] = trace
                row["synchronized_count_trace"] = [(1 << row["m"]) - d for d in trace]
                mask_checks += checks
            else:
                row["witness_metric_trace"] = None
                row["synchronized_count_trace"] = None
            H = truth.get(row["key"])
            row["reference_H"] = H
            row["gap"] = row["upper_bound"] - H if H is not None and row["upper_bound"] is not None else None
            assert row["gap"] is None or row["gap"] >= 0
            row["reference_upper"] = 33 if row["key"] == BAD_M7 else 50 if row["key"] == HELD_M8 else None
            csv_rows.append({"m": row["m"], "key": row["key"], "configured_common_k": k,
                             "producing_k": row["producing_k"], "producing_window": row["producing_window"],
                             "status": row["status"], "lower_bound": row["lower_bound"], "upper_bound": row["upper_bound"],
                             "reference_H": H, "gap": row["gap"], "reference_upper": row["reference_upper"],
                             "first": row["witness"][0] if row["upper_bound"] else "",
                             "second": row["witness"][1] if row["upper_bound"] else "",
                             "prefix_attempts": row["prefix_attempts"], "expanded_nodes": row["expanded_nodes"],
                             "tail_calls": row["tail_calls"],
                             "D_trace": json.dumps(row["witness_metric_trace"], separators=(",", ":"))})
        save_rows(args.out / f"records-common-k{k}.jsonl", values)
        winners = [row for row in values if row["reference_H"] is not None]
        gaps = [row["gap"] for row in winners if row["gap"] is not None]
        summary_modes.append({"common_k": k, "winner_cases": len(winners),
                              "winner_misses": sum(row["upper_bound"] is None for row in winners),
                              "optimal": gaps.count(0), "within_two": sum(gap <= 2 for gap in gaps),
                              "maximum_positive_gap": max(gaps, default=None),
                              "m7_winner_lengths": [row["upper_bound"] for row in winners if row["m"] == 7],
                              "bad_m7_upper": next(row["upper_bound"] for row in values if row["key"] == BAD_M7),
                              "held_m8_upper": next(row["upper_bound"] for row in values if row["key"] == HELD_M8),
                              "expanded_nodes": sum(row["expanded_nodes"] for row in values),
                              "tail_calls": sum(row["tail_calls"] for row in values),
                              "retained_metric_complete_reports": sum(report["complete"] for row in values for report in row["window_distributions"]),
                              "retained_metric_incomplete_reports": sum(not report["complete"] for row in values for report in row["window_distributions"]),
                              "window_reports_truncated": sum(row["window_reports_truncated"] for row in values)})
    with (args.out / "cases.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0])); writer.writeheader(); writer.writerows(csv_rows)
    summary = {"schema": 1, "manifest": ref(args.out / "manifest.json"),
               "analysis_source": ref(Path(__file__)), "analysis_reused_native_batches": args.resume_native,
               "query_seal": ref(args.out / "query-seal.json"), "cases": 22, "queries": 44,
               "configured_common_ks": [8, 12], "truth_k": None, "scope": manifest["coverage"],
               "metrics": summary_modes, "independent_final_mask_replays": mask_checks,
               "truth_sources": [ref(path) for path in truth_paths], "scores_used_after_queries_only": True,
               "batch_times": timings,
               "timing_scope": "post-query validation only; native batches reused" if args.resume_native else "native queries and validation",
               "wall_seconds": None if args.resume_native else time.monotonic() - started,
               "analysis_seconds": time.monotonic() - started,
               "limits": ["The unpruned common-tail tree has2^k leaves, not4^k; native proof pruning can omit branches.",
                          "Incomplete retained metric reports and truncation counts are preserved, not claimed as exhaustive metric distributions.",
                          "Known H labels qualify only the20 certified winners; m7/m8 extra H remains unknown.",
                          "Every found pair is independently scalar-verified; a heuristic miss gives no hardness bound."]}
    save(args.out / "summary.json", summary)
    print(json.dumps({"out": str(args.out), "metrics": summary_modes, "mask_checks": mask_checks}))


if __name__ == "__main__":
    main()

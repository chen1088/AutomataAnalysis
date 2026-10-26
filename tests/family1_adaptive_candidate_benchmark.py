#!/usr/bin/env python3
"""Graph-only calibration of the adaptive finder on the eight known m7 winners.

Known H and saved words never control queries. Truth is read only after the
baseline and adaptive schedule finish, to measure gaps and rough-band coverage.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import redirect_stdout
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import family1_adaptive_candidate_search as adaptive
import family1_graph_candidate_search as scoring


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("calibration requires fresh output")
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    source = REPO / "results/family1-m7/maximizers.jsonl"
    # Whitelist graph metadata. No word, score or bound enters the finder.
    graphs = [scoring.graph_metadata(row) for _, row in scoring.jsonl(source)]
    if len(graphs) != 8 or any(graph["m"] != 7 for graph in graphs):
        raise ValueError("expected the fixed eight-graph calibration cohort")
    binary = args.out / "binary"
    binary.mkdir()
    exe = binary / args.exe.name
    shutil.copy2(args.exe, exe)
    for path in args.exe.parent.glob("*.dll"):
        shutil.copy2(path, binary / path.name)
    shutil.copy2(Path(__file__), args.out / "driver-used.py")
    scoring.atomic_json(args.out / "run.json", {
        "schema": 1, "method": "graph-only-adaptive-m7-calibration", "cohort_source": scoring.reference(source),
        "graphs": graphs, "baseline_length_cap": 64, "baseline_k": 6, "samples": 1024,
        "seed": 1088, "beam": 16, "seconds_per_query": args.seconds, "jobs": args.jobs,
        "exe": scoring.reference(exe), "adaptive_module": scoring.reference(Path(adaptive.__file__)),
        "driver": scoring.reference(Path(__file__)), "truth_used_for_query_control": False, "saved_word_hints_used": False})
    baseline = []
    def work(graph):
        stage = adaptive.build_stage(graph, 6, 64, seconds=args.seconds)
        answer = adaptive.query(exe, graph, stage, 64, args.out / "baseline" / graph["key"], "fixed-graph-only-baseline")
        positive = answer["best_positive"]
        return {**graph, "lower_bound": 1, "upper_bound": positive["upper_bound"] if positive else None,
                "witness": positive["witness"] if positive else None, "upper_certificate": positive,
                "completed_standard_stage": answer["completed_stage"], "outcome": answer["outcome"]}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for future in as_completed([pool.submit(work, graph) for graph in graphs]):
            row = future.result()
            baseline.append(row)
            print(scoring.compact({"baseline_key": row["key"], "upper": row["upper_bound"],
                                   "completed_stage": row["completed_standard_stage"]}), flush=True)
    baseline.sort(key=lambda row: row["key"])
    scoring.write_jsonl(args.out / "baseline.jsonl", baseline)
    qualified = [row for row in baseline if row["completed_standard_stage"]]
    scoring.write_jsonl(args.out / "qualified.jsonl", qualified)
    with (args.out / "adaptive.log").open("w", encoding="utf-8") as log, redirect_stdout(log):
        adaptive.main(["--records", str(args.out / "baseline.jsonl"), "--refined-records", str(args.out / "qualified.jsonl"),
                       "--out", str(args.out / "adaptive"), "--exe", str(exe), "--m", "7", "--jobs", str(args.jobs),
                       "--query-seconds", str(args.seconds), "--wall-seconds", "90", "--max-queries", "32"])
    scoring.atomic_json(args.out / "scoring-seal.json", {
        "baseline": scoring.reference(args.out / "baseline.jsonl"), "adaptive_run": scoring.reference(args.out / "adaptive/run.json"),
        "adaptive_summary": scoring.reference(args.out / "adaptive/summary.json"), "truth_not_yet_loaded": True})
    # Retrospective truth evaluation only, after all candidate search plans end.
    truth = {row["key"]: row["merge_length"] for _, row in scoring.jsonl(source)}
    final = {row["key"]: row for _, row in scoring.jsonl(args.out / "adaptive/records.jsonl")}
    cases = []
    for old in baseline:
        row = final.get(old["key"], old)
        actual, length = truth[row["key"]], row["upper_bound"]
        estimate = adaptive.estimate(length) if length is not None else None
        cases.append({"key": row["key"], "known_H_from_prior_certificate": actual,
                      "baseline_upper": old["upper_bound"], "final_upper": length,
                      "witness_gap": length - actual if length is not None else None,
                      "drop": old["upper_bound"] - length if length is not None and old["upper_bound"] is not None else None,
                      "heuristic_estimate": estimate,
                      "rough_band_contains_known_H": estimate["rough_band"][0] <= actual <= estimate["rough_band"][1] if estimate else None,
                      "completed_k": row.get("completed_k"), "shortestness_newly_proved": False})
    summary = scoring.read_json(args.out / "adaptive/summary.json")
    report = {"schema": 1, "graphs": 8, "saved_words_or_truth_used_for_queries": False,
              "cases": cases, "adaptive_query_count": summary["query_count"],
              "crowding_by_batch": [{"k": batch["window_k"], "band_count_before": batch["pre_batch_band_size"],
                                      "active_upper_before": batch["pre_batch_active_length"]} for batch in summary["batches"]],
              "active_heuristic_ties": summary["active_best_ties"], "rough_bands_are_not_proof_intervals": True,
              "rough_band_truth_coverage": sum(bool(row["rough_band_contains_known_H"]) for row in cases),
              "global_or_new_exact_score_claim": False}
    scoring.atomic_json(args.out / "report.json", report)
    scoring.write_jsonl(args.out / "cases.jsonl", cases)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

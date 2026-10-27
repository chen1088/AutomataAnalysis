#!/usr/bin/env python3
"""Frozen all-case validation of two scored-seed configurations.

The 116-case pool has all 69 exact m6 frontier graphs and 47 m7 nonwinners.
Two m6 graphs overlap the tuned winners; strict held-out metrics exclude them.
Only keys and fixed parameters reach native search; truth enters after sealing.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import time

from family1_pair_refine_benchmark import REPO, ref, replay, rows, save, save_rows


def key_of(row):
    return "".join(f"{q:02d}" for ports in row["canonical_table"] for q in ports)


def analyze(args, source, training_keys, cases, configurations, results, timings, started):
    # Source score/status fields are used for the first time below the seal.
    truth = {}
    for row in source:
        key = key_of(row)
        if row["m"] == 6:
            assert row["status"] == "exact" and row["lower_bound"] == row["upper_bound"] == row["merge_length"]
            truth[key] = {"H": row["merge_length"], "champion": row["merge_length"] == 23}
        elif row["m"] == 7 and key not in training_keys:
            assert row["status"] != "exact" and row["upper_bound"] <= 33
            truth[key] = {"H": None, "champion": False, "certified_upper": row["upper_bound"]}
    case_map = {row["key"]: row for row in cases}
    verified_masks = 0
    all_csv, summaries = [], []
    for config in configurations:
        values = results[config["id"]]
        for row in values:
            case = case_map[row["key"]]
            row["training_overlap"] = case["training_overlap"]
            row["configuration"] = config["id"]
            row["search_parameters"] = config
            row["producing_k"] = None if row["exact"] else config["joint_k"]
            row["producing_window"] = "exact-word-layers" if row["exact"] else "joint-pair"
            if row["upper_bound"] is not None:
                trace, checks = replay(row["key"], row["witness"])
                assert trace == row["metric_trace"]
                verified_masks += checks
                row["witness_metric_trace"] = trace
                row["synchronized_count_trace"] = [(1 << row["m"]) - d for d in trace]
                row["static_masks_verified"] = checks
                assert row["upper_bound"] == len(row["witness"][0])
            else:
                assert row["witness"] == ["", ""] and row["metric_trace"] == [0]
                row["witness"] = None
                row["static_masks_verified"] = 0
            H = truth[row["key"]]["H"]
            gap = row["upper_bound"] - H if H is not None and row["upper_bound"] is not None else None
            assert gap is None or gap >= 0
            row["reference_H"] = H
            row["gap"] = gap
            all_csv.append({"configuration": config["id"], "m": row["m"], "key": row["key"],
                            "configured_joint_k": config["joint_k"], "producing_k": row["producing_k"],
                            "producing_window": row["producing_window"], "training_overlap": case["training_overlap"],
                            "upper_bound": row["upper_bound"], "reference_H": H, "gap": gap,
                            "first": row["witness"][0] if row["witness"] else "",
                            "second": row["witness"][1] if row["witness"] else "",
                            "expanded_nodes": row["expanded_nodes"], "complete_windows": row["complete_windows"],
                            "D_trace": json.dumps(row.get("witness_metric_trace"), separators=(",", ":"))})
        save_rows(args.out / f"records-{config['id']}.jsonl", values)
        for strict in [False, True]:
            selected = [row for row in values if not strict or not row["training_overlap"]]
            m6 = [row for row in selected if row["m"] == 6]
            m7 = [row for row in selected if row["m"] == 7]
            gaps = [row["gap"] for row in m6 if row["gap"] is not None]
            summaries.append({"configuration": config, "strict_heldout": strict, "cases": len(selected),
                              "positive_count": sum(row["upper_bound"] is not None for row in selected),
                              "misses": sum(row["upper_bound"] is None for row in selected),
                              "m6": {"cases": len(m6), "misses": sum(row["upper_bound"] is None for row in m6),
                                     "optimal": gaps.count(0), "within_two": sum(gap <= 2 for gap in gaps),
                                     "median_gap_if_found": statistics.median(gaps) if gaps else None,
                                     "maximum_gap_if_found": max(gaps, default=None),
                                     "gap_histogram": dict(sorted(Counter(gaps).items()))},
                              "m7": {"cases": len(m7), "misses": sum(row["upper_bound"] is None for row in m7),
                                     "verified_exclusions_upper_le33": sum(row["upper_bound"] is not None and row["upper_bound"] <= 33 for row in m7),
                                     "finite_false_compatible_upper_ge34": sum(row["upper_bound"] is not None and row["upper_bound"] >= 34 for row in m7),
                                     "exact_H_not_claimed": True},
                              "expanded_nodes": sum(row["expanded_nodes"] for row in selected),
                              "complete_windows": sum(row["complete_windows"] for row in selected)})
    with (args.out / "cases.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(all_csv[0]))
        writer.writeheader(); writer.writerows(all_csv)
    summary = {"schema": 1, "manifest": ref(args.out / "manifest.json"), "query_seal": ref(args.out / "query-seal.json"),
               "analysis_source": ref(Path(__file__)),
               "input_cases": len(cases), "graph_queries": sum(len(values) for values in results.values()),
               "strict_heldout_cases": 114, "training_overlap_cases": 2, "all_cases_scored": True,
               "configured_joint_ks": [4], "exact_reference_k": None,
               "scores_used_after_queries_only": True, "independent_mask_replays": verified_masks,
               "native_expansion_cap_cannot_be_reached": {"max_possible_nodes_per_attempt": 20 * 16 * 340,
                                                          "cap": 2000000, "assumptions": "k4, B16, no diagonal or unequal beam, L<=80"},
               "metrics": summaries, "batch_times": timings, "wall_seconds": time.monotonic() - started,
               "limits": ["Held out from new scored-seed tuning, not a representative sample of full m6/m7 universes.",
                          "Two m6 champions overlap training; strict metrics omit them.",
                          "m7 labels supply nonwinner membership, not exact H or numerical gaps.",
                          "Returned upper bounds do not prove shortestness unless exact=true."]}
    save(args.out / "summary.json", summary)
    print(json.dumps({"out": str(args.out), "cases": len(cases), "queries": summary["graph_queries"],
                      "strict_heldout_cases": 114, "metrics": summaries}))



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "out/family1-finder-strategies-20261026/heldout")
    parser.add_argument("--source", type=Path, default=REPO / "results/family1-neighbor-seeds/near-top.jsonl")
    parser.add_argument("--tuned-input", type=Path, default=REPO / "out/family1-finder-strategies-20261026/refine/scored-portfolio-input.json")
    parser.add_argument("--frozen-source", type=Path, default=REPO / "out/family1-finder-strategies-20261026/scored-seeds/fast-source")
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--analyze-only", action="store_true", help="Replay and analyze already sealed native outputs without querying")
    args = parser.parse_args()
    if args.analyze_only:
        manifest = json.loads((args.out / "manifest.json").read_text())
        seal = json.loads((args.out / "query-seal.json").read_text())
        assert seal["all_configurations_and_cases_completed"] is True and seal["truth_read"] is False
        for field in ["source", "tuned_input", "input_cases"]:
            item = manifest[field]
            assert ref(Path(item["path"]))["sha256"] == item["sha256"]
        for item in seal["native_records"]:
            assert ref(Path(item["path"]))["sha256"] == item["sha256"]
        source = rows(Path(manifest["source"]["path"]))
        training_keys = {row["key"] for row in rows(Path(manifest["tuned_input"]["path"]))}
        cases = rows(args.out / "input-cases.jsonl")
        configurations = manifest["configurations"]
        results = {config["id"]: rows(args.out / f"native-{config['id']}.jsonl") for config in configurations}
        progress = json.loads((args.out / "progress.json").read_text())
        started = time.monotonic() - progress["seconds"]
        analyze(args, source, training_keys, cases, configurations, results, [], started)
        return
    assert args.jobs > 0 and (not args.out.exists() or not any(args.out.iterdir()))
    args.out.mkdir(parents=True, exist_ok=True)
    training_keys = {row["key"] for row in rows(args.tuned_input)}
    source = rows(args.source)
    cases = []
    for row in source:
        m, key = row["m"], key_of(row)
        if m == 6 or (m == 7 and key not in training_keys):
            cases.append({"m": m, "key": key, "canonical_table": row["canonical_table"],
                          "training_overlap": key in training_keys})
    cases.sort(key=lambda row: (row["m"], row["key"]))
    assert len(cases) == 116 and sum(row["m"] == 6 for row in cases) == 69
    assert sum(row["training_overlap"] for row in cases) == 2
    assert len({row["key"] for row in cases}) == len(cases)
    evidence = args.out / "evidence"
    evidence.mkdir()
    frozen_manifest = json.loads((args.frozen_source / "manifest.json").read_text())
    for item in frozen_manifest["files"]:
        path = REPO / item["archive"]
        assert ref(path)["sha256"] == item["sha256"]
        shutil.copy2(path, evidence / path.name)
    shutil.copy2(args.frozen_source / "manifest.json", evidence / "original-source-manifest.json")
    for name in ["Family1LargeGraph.h", "Family1LargeGraph.cpp", "Family1PairAgreement.h", "Family1CliArtifacts.h"]:
        shutil.copy2(REPO / name, evidence / name)
    shutil.copy2(__file__, evidence / "driver.py")
    shutil.copy2(REPO / "scripts/family1_pair_refine_benchmark.py", evidence / "scalar-replay.py")
    exe = evidence / "Family1ScoredSeedFastBenchmark"
    save_rows(args.out / "input-cases.jsonl", cases)
    configurations = [
        {"id": "original", "joint_k": 4, "beam": 16, "prefix_depth": 20, "prefix_words": 1048576,
         "catalogue": 16384, "selected": 512, "exact_depth": 16, "fast": False},
        {"id": "compact", "joint_k": 4, "beam": 16, "prefix_depth": 20, "prefix_words": 1048576,
         "catalogue": 4096, "selected": 512, "exact_depth": 16, "fast": True},
    ]
    manifest = {"schema": 1, "source": ref(args.source), "tuned_input": ref(args.tuned_input),
                "input_cases": ref(args.out / "input-cases.jsonl"), "case_count": len(cases),
                "strict_heldout_count": 114, "training_overlaps": 2, "configurations": configurations,
                "sources": [ref(path) for path in sorted(evidence.iterdir()) if path.is_file()],
                "native_executable": ref(exe), "query_fields": ["graph key", "fixed parameters"],
                "truth_used_in_queries": False, "randomness": False, "time_limits": False,
                "caps": {"max_length": 80, "max_expansions_per_attempt": 2000000},
                "scope": "held out from scored-seed strategy tuning, deliberately enriched frontier rather than full universes"}
    save(args.out / "manifest.json", manifest)
    batches = [cases[index::4] for index in range(4)]
    tasks = [(config, index) for config in configurations for index in range(4)]
    started = time.monotonic()

    def run(task):
        config, index = task
        directory = args.out / config["id"] / f"batch-{index}"
        directory.mkdir(parents=True)
        keys = directory / "keys.txt"
        keys.write_text("".join(row["key"] + "\n" for row in batches[index]))
        command = [str(exe), str(keys), str(config["joint_k"]), str(config["beam"]),
                   str(config["prefix_depth"]), str(config["prefix_words"]), str(config["catalogue"]),
                   str(config["selected"]), str(config["exact_depth"])]
        if config["fast"]:
            command.append("fast")
        save(directory / "command.json", command)
        before = time.monotonic()
        with (directory / "native.jsonl").open("w") as output, (directory / "stderr.txt").open("w") as errors:
            subprocess.run(command, stdout=output, stderr=errors, check=True)
        result = rows(directory / "native.jsonl")
        assert [row["key"] for row in result] == [row["key"] for row in batches[index]]
        return config["id"], index, result, time.monotonic() - before

    results = {config["id"]: [] for config in configurations}
    timings = []
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures = [workers.submit(run, task) for task in tasks]
        for future in as_completed(futures):
            mode, index, values, elapsed = future.result()
            results[mode] += values
            timings.append({"configuration": mode, "batch": index, "seconds": elapsed})
            save(args.out / "progress.json", {"completed_batches": len(timings), "total_batches": len(tasks),
                                             "completed_graph_queries": sum(len(r) for r in results.values()),
                                             "seconds": time.monotonic() - started})
    native_files = []
    for config in configurations:
        result = results[config["id"]]
        result.sort(key=lambda row: (row["m"], row["key"]))
        assert [row["key"] for row in result] == [row["key"] for row in cases]
        native_path = args.out / f"native-{config['id']}.jsonl"
        save_rows(native_path, result)
        native_files.append(ref(native_path))
    save(args.out / "query-seal.json", {"manifest": ref(args.out / "manifest.json"),
                                      "native_records": native_files, "truth_read": False,
                                      "all_configurations_and_cases_completed": True})
    analyze(args, source, training_keys, cases, configurations, results, timings, started)


if __name__ == "__main__":
    main()

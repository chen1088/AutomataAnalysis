#!/usr/bin/env python3
"""Post-hoc canonical-prefix comparison on every member of the 116-case pool.

This pool informed the request for these extra comparisons, so these runs are
development validation, not a fresh held-out qualification.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from family1_pair_refine_benchmark import REPO, ref, rows, save, save_rows
from family1_scored_seed_heldout import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, default=REPO / "out/family1-finder-strategies-20261026/heldout")
    parser.add_argument("--out", type=Path, default=REPO / "out/family1-finder-strategies-20261026/heldout-prefix")
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/joint-solid-linux/Family1Joint")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    assert args.jobs > 0 and not (args.out / "manifest.json").exists()
    args.out.mkdir(parents=True, exist_ok=True)
    evidence = args.out / "evidence"
    evidence.mkdir(exist_ok=True)
    exe = evidence / "Family1Joint"
    if not exe.exists():
        shutil.copy2(args.exe, exe)
    parent = json.loads((args.pool / "manifest.json").read_text())
    cases_path = args.pool / "input-cases.jsonl"
    assert ref(cases_path)["sha256"] == parent["input_cases"]["sha256"]
    cases = rows(cases_path)
    assert len(cases) == 116
    shutil.copy2(cases_path, args.out / "input-cases.jsonl")
    pending = ["family1_joint.cpp"]
    copied = set()
    while pending:
        name = pending.pop()
        if name in copied:
            continue
        path = REPO / name
        assert path.is_file(), name
        shutil.copy2(path, evidence / path.name)
        copied.add(name)
        pending += [item for item in re.findall(r'#include "([^"]+)"', path.read_text()) if (REPO / item).is_file()]
    for name in ["Family1ExactPacked.cpp", "Family1LargeGraph.cpp"]:
        shutil.copy2(REPO / name, evidence / name)
    shutil.copy2(__file__, evidence / "driver.py")
    configurations = [
        {"id": "canonical-deep", "joint_k": 4, "beam": 64, "prefix_pairs": 128,
         "prefix_depth": 20, "prefix_words": 1048576, "score": "permutation", "common_prefix_depth": 8},
        {"id": "canonical-wide", "joint_k": 4, "beam": 16, "prefix_pairs": 512,
         "prefix_depth": 16, "prefix_words": 65536, "score": "permutation", "common_prefix_depth": 8},
    ]
    manifest = {"schema": 1, "source": parent["source"], "tuned_input": parent["tuned_input"],
                "input_cases": ref(args.out / "input-cases.jsonl"), "case_count": len(cases),
                "strict_heldout_count": 114, "training_overlaps": 2, "configurations": configurations,
                "sources": [ref(path) for path in sorted(evidence.iterdir()) if path.is_file()],
                "native_executable": ref(exe), "query_fields": ["graph key", "fixed parameters"],
                "truth_used_in_queries": False, "randomness": False, "time_limits": False,
                "caps": {"max_length": 80, "max_expansions_per_attempt": 2000000},
                "scope": "post-hoc development comparison after first scored-seed held-out failure; not a fresh holdout"}
    save(args.out / "manifest.json", manifest)
    tasks = []
    for config in configurations:
        for m in [6, 7]:
            values = [case for case in cases if case["m"] == m]
            for index in range(4):
                tasks.append((config, m, index, values[index::4]))
    started = time.monotonic()

    def run(task):
        config, m, index, values = task
        directory = args.out / config["id"] / f"m{m}-batch-{index}"
        command = [str(exe), "--m", str(m), "--out", str(directory), "--k", str(config["joint_k"]),
                   "--beam", str(config["beam"]), "--diagonal-beam", "0", "--unequal-beam", "0",
                   "--startup", "legacy", "--score", config["score"], "--prefix-pairs", str(config["prefix_pairs"]),
                   "--prefix-depth", str(config["prefix_depth"]), "--prefix-words", str(config["prefix_words"]),
                   "--common-prefix-depth", str(config["common_prefix_depth"]), "--max-length", "80",
                   "--expansions", "2000000", "--target-upper", "0", "--trace-records", "64"]
        for case in values:
            command += ["--graph", case["key"]]
        before = time.monotonic()
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        (directory / "console.txt").write_text(process.stdout + process.stderr)
        save(directory / "command.json", command)
        results = rows(directory / "records.jsonl")
        assert [row["key"] for row in results] == [case["key"] for case in values]
        for row in results:
            assert row["k"] == config["joint_k"] and row["beam_width"] == config["beam"]
            assert row["prefix_pairs"] == config["prefix_pairs"] and row["deterministic"] is True
            assert row["alphabet"] == ["00", "01", "10", "11"] and row["partial_windows"] == 0
            assert row["score"] == "permutation" and not row["minimality_certified"]
            row["exact"] = False
            row["metric_trace"] = row["witness_metric_trace"] if row["upper_bound"] is not None else [0]
            if row["upper_bound"] is None:
                row["witness"] = ["", ""]
        return config["id"], m, index, results, time.monotonic() - before

    results = {config["id"]: [] for config in configurations}
    timings = []
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures = [workers.submit(run, task) for task in tasks]
        for future in as_completed(futures):
            mode, m, index, values, elapsed = future.result()
            results[mode] += values
            timings.append({"configuration": mode, "m": m, "batch": index, "seconds": elapsed})
            save(args.out / "progress.json", {"completed_batches": len(timings), "total_batches": len(tasks),
                                             "completed_graph_queries": sum(len(r) for r in results.values()),
                                             "seconds": time.monotonic() - started})
    files = []
    for config in configurations:
        values = results[config["id"]]
        values.sort(key=lambda row: (row["m"], row["key"]))
        assert [row["key"] for row in values] == [row["key"] for row in cases]
        path = args.out / f"native-{config['id']}.jsonl"
        save_rows(path, values)
        files.append(ref(path))
    save(args.out / "query-seal.json", {"manifest": ref(args.out / "manifest.json"), "native_records": files,
                                      "truth_read": False, "all_configurations_and_cases_completed": True})
    source = rows(Path(parent["source"]["path"]))
    training_keys = {row["key"] for row in rows(Path(parent["tuned_input"]["path"]))}
    analyze(args, source, training_keys, cases, configurations, results, timings, started)
    summary = json.loads((args.out / "summary.json").read_text())
    summary["scope"] = manifest["scope"]
    summary.pop("native_expansion_cap_cannot_be_reached", None)  # That bound assumed B16 in the first driver.
    summary["actual_expansion_capped_cases"] = {
        mode: sum(row["expansion_limit_reached"] for row in values) for mode, values in results.items()}
    save(args.out / "summary.json", summary)


if __name__ == "__main__":
    main()

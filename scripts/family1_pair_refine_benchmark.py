#!/usr/bin/env python3
"""Measure complete deterministic refinements of pairs found by an algorithm.

Only graph keys, producing joint k, and the actual found words reach native
search. Exhaustive scores are read after all native outputs are sealed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

REPO = Path(__file__).resolve().parents[1]
SOURCE_FILES = [
    "Family1PairRefine.h", "Family1ExactPacked.h", "Family1ExactPacked.cpp",
    "Family1LargeGraph.h", "Family1LargeGraph.cpp", "tests/Family1PairRefineBenchmark.cpp",
]


def rows(path):
    value = path.read_text(encoding="utf-8-sig")
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        return [json.loads(line) for line in value.splitlines() if line.strip()]


def ref(path):
    path = path.resolve()
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def save_rows(path, values):
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in values))


def table_from_key(key):
    assert len(key) % 4 == 0 and len(key) >= 4
    values = [int(key[i:i + 2]) for i in range(0, len(key), 2)]
    table = [values[i:i + 2] for i in range(0, len(values), 2)]
    assert all(0 <= q < len(table) for row in table for q in row)
    return table


def replay(key, pair):
    table = table_from_key(key)
    assert len(pair) == 2 and pair[0] != pair[1] and len(pair[0]) == len(pair[1])
    assert all(word and set(word) <= {"0", "1"} for word in pair)
    trace = [0] * (len(pair[0]) + 1)
    for mask in range(1 << len(table)):
        left = right = 0
        for depth, (a, b) in enumerate(zip(*pair), 1):
            left = table[left][int(a) ^ ((mask >> left) & 1)]
            right = table[right][int(b) ^ ((mask >> right) & 1)]
            trace[depth] += left != right
        assert left == right, (key, mask, pair)
    return trace, 1 << len(table)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--strategy", help="Optional exact strategy field to retain")
    parser.add_argument("--modes", nargs="+", default=["deletion", "mixed", "edits4", "tail16", "prefix16"])
    parser.add_argument("--max-words", type=int, default=100000000)
    parser.add_argument("--max-catalog", type=int, default=100000000)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    assert args.max_words > 0 and args.max_catalog > 0
    assert not args.out.exists() or not any(args.out.iterdir()), "Use a fresh output directory"
    args.out.mkdir(parents=True, exist_ok=True)
    cases = []
    input_checks = 0
    for path in args.input:
        for ordinal, row in enumerate(rows(path)):
            if args.strategy and row.get("strategy") != args.strategy:
                continue
            pair = row.get("witness")
            if not pair:
                continue
            producing_k = row.get("k", row.get("input_joint_k"))
            assert isinstance(producing_k, int) and producing_k > 0
            key = row["key"]
            _, checks = replay(key, pair)
            input_checks += checks
            case = {"key": key, "m": len(key) // 4, "input_joint_k": producing_k, "input_witness": pair,
                    "source": ref(path), "source_ordinal": ordinal,
                    "source_strategy": row.get("strategy", row.get("mode"))}
            case["id"] = key + "-" + hashlib.sha256(("\n".join(pair)).encode()).hexdigest()[:12]
            cases.append(case)
    cases.sort(key=lambda case: (case["m"], case["key"], case["input_witness"], case["source"]["path"]))
    assert cases and len({case["id"] for case in cases}) == len(cases), "Supply distinct found input pairs"
    evidence = args.out / "evidence"
    evidence.mkdir()
    sources = []
    for name in SOURCE_FILES:
        original = REPO / name
        destination = evidence / Path(name).name
        shutil.copy2(original, destination)
        sources.append({"original": ref(original), "snapshot": ref(destination)})
    shutil.copy2(__file__, evidence / "runner.py")
    exe = evidence / "Family1PairRefineBenchmark"
    command = [args.cxx, "-std=c++23", "-O3", "-I", str(evidence),
               str(evidence / "Family1PairRefineBenchmark.cpp"),
               str(evidence / "Family1ExactPacked.cpp"), str(evidence / "Family1LargeGraph.cpp"),
               "-o", str(exe)]
    subprocess.run(command, check=True)
    self_test = subprocess.run([str(exe), "--self-test"], text=True, capture_output=True, check=True)
    save(args.out / "self-test.json", json.loads(self_test.stdout))
    input_path = args.out / "input.tsv"
    input_path.write_text("".join(f"{case['key']}\t{case['input_joint_k']}\t"
                                 f"{case['input_witness'][0]}\t{case['input_witness'][1]}\n" for case in cases))
    save_rows(args.out / "input-cases.jsonl", cases)
    manifest = {"schema": 1, "input": ref(input_path), "input_cases": ref(args.out / "input-cases.jsonl"),
                "sources": sources, "runner": ref(evidence / "runner.py"), "compile_command": command,
                "executable": ref(exe), "modes": args.modes, "max_words": args.max_words,
                "max_catalog": args.max_catalog, "randomness": False, "time_caps": False,
                "query_fields": ["graph key", "actual found pair", "input producing joint k"],
                "truth_used_in_queries": False}
    save(args.out / "manifest.json", manifest)
    results = {}
    verification = {"input_mask_replays": input_checks, "output_and_improvement_mask_replays": 0}
    work = {}
    for mode in args.modes:
        native = args.out / f"native-{mode}.jsonl"
        command = [str(exe), mode, str(input_path), str(native), str(args.max_words), str(args.max_catalog)]
        started = time.monotonic()
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        wall = time.monotonic() - started
        (args.out / f"log-{mode}.txt").write_text(process.stdout + process.stderr)
        values = rows(native)
        assert len(values) == len(cases)
        for case, row in zip(cases, values):
            assert row["key"] == case["key"] and row["input_joint_k"] == case["input_joint_k"]
            assert row["input_witness"] == case["input_witness"]
            assert row["initial_length"] == len(case["input_witness"][0])
            assert row["upper_bound"] == len(row["witness"][0]) <= row["initial_length"]
            assert row["minimality_certified"] is False
            trace, checks = replay(row["key"], row["witness"])
            row["witness_metric_trace"] = trace
            row["synchronized_count_trace"] = [(1 << row["m"]) - d for d in trace]
            row["static_masks_verified"] = checks
            verification["output_and_improvement_mask_replays"] += checks
            for pair in row["improvements"]:
                _, checks = replay(row["key"], pair)
                verification["output_and_improvement_mask_replays"] += checks
            for neighborhood in row["neighborhoods"]:
                if neighborhood["refused_by_budget"]:
                    assert neighborhood["evaluated_words"] == 0 and not neighborhood["evaluated_complete"]
                else:
                    assert neighborhood["generated_complete"] and neighborhood["evaluated_complete"]
                    assert neighborhood["candidate_words"] == neighborhood["evaluated_words"]
                if neighborhood["found"]:
                    _, checks = replay(row["key"], neighborhood["witness"])
                    verification["output_and_improvement_mask_replays"] += checks
            row["case_id"] = case["id"]
            row["input_source"] = case["source"]
            row["deterministic"] = True
        save_rows(args.out / f"records-{mode}.jsonl", values)
        results[mode] = values
        work[mode] = {"seconds": wall, "native": ref(native), "command": command}
    save(args.out / "query-seal.json", {"manifest": ref(args.out / "manifest.json"),
                                      "native_outputs": [value["native"] for value in work.values()],
                                      "all_queries_completed": True, "target_truth_read": False})
    # Target scores enter only after the complete native output seal.
    scores = {}
    truth_paths = [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"]
    for path in truth_paths:
        for row in rows(path):
            # Older m<=6 archives use one digit per destination; native and
            # current generation always use two. Normalize from the table.
            key = "".join(f"{q:02d}" for ports in row["canonical_table"] for q in ports)
            scores[key] = row["merge_length"]
    summaries, csv_rows = [], []
    for mode, values in results.items():
        known = [row for row in values if row["key"] in scores]
        gaps = [row["upper_bound"] - scores[row["key"]] for row in known]
        assert all(gap >= 0 for gap in gaps)
        summaries.append({"mode": mode, "cases": len(values),
                          "improved_cases": sum(row["upper_bound"] < row["initial_length"] for row in values),
                          "reference_cases": len(known), "optimal": gaps.count(0),
                          "within_two": sum(gap <= 2 for gap in gaps), "maximum_gap": max(gaps, default=None),
                          "evaluated_candidates": sum(row["evaluated_words"] for row in values),
                          "profile_steps": sum(row["profile_steps"] for row in values),
                          "budget_refused_cases": sum(row["budget_refused"] for row in values),
                          "evaluated_neighborhoods": sum(not n["refused_by_budget"] for row in values for n in row["neighborhoods"]),
                          "partial_evaluated_neighborhoods": 0, **work[mode]})
        for row in values:
            csv_rows.append({name: row[name] for name in [
                "case_id", "m", "key", "input_joint_k", "refinement_k", "refinement_window_kind", "mode",
                "initial_length", "upper_bound", "budget_refused", "evaluated_words", "profile_steps"]} |
                {"reference_H": scores.get(row["key"]), "first": row["witness"][0], "second": row["witness"][1],
                 "D_trace": json.dumps(row["witness_metric_trace"], separators=(",", ":"))})
    with (args.out / "cases.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]))
        writer.writeheader(); writer.writerows(csv_rows)
    summary = {"schema": 1, "manifest": ref(args.out / "manifest.json"), "query_seal": ref(args.out / "query-seal.json"),
               "truth_k": None, "truth_window_kind": "N/A: exhaustive reference", "truth_used_after_search_only": True,
               "truth_sources": [ref(path) for path in truth_paths], "input_count": len(cases),
               "input_joint_ks": sorted({case["input_joint_k"] for case in cases}), "modes": summaries,
               "verification": verification, "randomness": False, "minimality_certified": False,
               "limits": ["A local minimum is not a global shortestness certificate.",
                          "Common-tail k counts binary common-continuation steps, not joint steps.",
                          "Prefix-replacement k counts binary replacement-prefix symbols, not joint steps.",
                          "A refused neighborhood was not evaluated and is never labeled complete."]}
    save(args.out / "summary.json", summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()

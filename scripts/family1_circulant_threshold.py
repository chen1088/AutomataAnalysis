#!/usr/bin/env python3
"""Run and preserve fixed-length tests of the user's circulant family m=8..20.

This checks one rooted class per size; translations identify its starting
vertices. A query returning UNKNOWN is preserved without strengthening bounds.
Global optimality over other graph classes is never inferred.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess

from family1_study import REPO, canonical_table, compact, file_hash, fixed_key, jsonl, validate_table


def atomic_text(path, text):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def load_graphs(path):
    records = []
    for _, record in jsonl(path):
        if not 8 <= record["m"] <= 20:
            continue
        m, k = record["m"], record["m"] // 3
        raw = tuple(((state + 1) % m, (state + k) % m) for state in range(m))
        table = canonical_table(validate_table(raw))
        if (tuple(map(tuple, record["canonical_table"])) != table or record["key"] != fixed_key(table)
                or table[0][0] == table[0][1]):
            raise ValueError(f"record does not match the specified accessible circulant at m={m}")
        records.append(record)
    records.sort(key=lambda record: (record["m"], record["key"]))
    if [record["m"] for record in records] != list(range(8, 21)):
        raise ValueError("require exactly one circulant record at every size8..20")
    return records


def query(record, args):
    directory = args.out / "queries" / f"m{record['m']:02d}-{record['key']}"
    command = [str(args.exe), "--graph", record["key"], "--length", str(args.length), "--out", str(directory),
               "--timeout-ms", str(args.timeout_ms), "--solve-timeout-ms", str(args.solve_timeout_ms),
               "--max-refinements", str(args.max_refinements), "--projection-masks", str(args.projection_masks)]
    if (directory / "run.json").exists():
        command.append("--resume")
    completed = subprocess.run(command, cwd=REPO, text=True, capture_output=True,
                               timeout=max(60, args.timeout_ms / 1000 + 60))
    if completed.returncode:
        raise RuntimeError(f"m={record['m']} native query failed: {completed.stderr[-2000:]}")
    result_path = directory / "result.json"
    result_bytes = result_path.read_bytes()
    answer = json.loads(result_bytes)
    if json.loads(completed.stdout) != answer:
        raise ValueError("native stdout and published result disagree")
    if (directory / "result.sha256").read_text().strip() != hashlib.sha256(result_bytes).hexdigest():
        raise ValueError("native result integrity mismatch")
    config_bytes = (directory / "run.json").read_bytes().removesuffix(b"\n")
    if answer["config_sha256"] != hashlib.sha256(config_bytes).hexdigest():
        raise ValueError("native configuration hash mismatch")
    if (answer["key"], answer["m"], answer["length"]) != (record["key"], record["m"], args.length):
        raise ValueError("native result belongs to another graph or threshold")
    if answer["canonical_table"] != record["canonical_table"]:
        raise ValueError("native result transition table mismatch")
    decision = answer["decision"]
    expected = {"collision": (1, args.length), "no_collision": (args.length + 1, None), "unknown": (1, None)}
    if decision not in expected or (answer["lower_bound"], answer["upper_bound"]) != expected[decision]:
        raise ValueError("invalid native threshold decision interval")
    masks = answer["sampled_masks"]
    if (len(masks) != answer["mask_count"] or len(masks) != len(set(masks))
            or any(type(mask) is not int or not 0 <= mask < 1 << record["m"] for mask in masks)):
        raise ValueError("invalid static-mask trace")
    if decision == "collision":
        witness = answer["witness"]
        if (not isinstance(witness, list) or len(witness) != 2 or witness[0] == witness[1]
                or any(not isinstance(word, str) or len(word) != args.length or set(word) - {"0", "1"} for word in witness)
                or answer["scalar_witness_masks_verified"] != 1 << record["m"]):
            raise ValueError("collision lacks a complete scalar static-mask witness check")
    elif answer["witness"] is not None or answer["upper_bound"] is not None:
        raise ValueError("UNKNOWN/no_collision cannot supply an upper witness")
    # Distinct root ports independently give H>=2; no imported lower is trusted.
    lower = max(2, answer["lower_bound"])
    upper = answer["upper_bound"]
    if upper is not None and lower > upper:
        raise ValueError("native upper contradicts distinct-root-port lower bound")
    return {"m": record["m"], "key": record["key"], "canonical_table": record["canonical_table"],
            "status": "exact" if lower == upper else "bounded" if upper is not None else "lower-bound",
            "lower_bound": lower, "upper_bound": upper, "merge_length": lower if lower == upper else None,
            "witness": answer["witness"], "threshold_decision": decision,
            "reason": answer["reason"], "native_result": {"path": str(result_path.resolve()), "sha256": file_hash(result_path)},
            "native_answer": answer, "input_record": record,
            "lower_bound_justification": "Distinct root ports give H>=2; no_collision at L additionally gives H>=L+1.",
            "root_coverage": "Translations identify every starting vertex with root0; one rooted class per size.",
            "maximum_value_certified": False, "maximizing_collection_complete": False,
            "enumeration_complete": False}


def export(args, results, configuration):
    records = [results[m] for m in sorted(results)]
    atomic_text(args.out / "graphs.jsonl", "".join(compact(record) + "\n" for record in records))
    counts = {decision: sum(record["threshold_decision"] == decision for record in records)
              for decision in ("collision", "no_collision", "unknown")}
    summary = {"schema": 1, "method": "circulant-family-fixed-length-native-queries",
               "family": "tau0(i)=(i+1) modm; tau1(i)=(i+floor(m/3)) modm",
               "min_m": 8, "max_m": 20, "length": args.length, "requested_graphs": 13,
               "completed_graphs": len(records), "all_requested_queries_complete": len(records) == 13,
               "decision_counts": counts, "pending_sizes": [m for m in range(8, 21) if m not in results],
               "sizes": [{"m": record["m"], "decision": record["threshold_decision"],
                          "lower_bound": record["lower_bound"], "upper_bound": record["upper_bound"],
                          "reason": record["reason"], "mask_count": record["native_answer"]["mask_count"],
                          "seconds": record["native_answer"]["seconds"]} for record in records],
               "configuration": configuration,
               "coverage": "One supplied family, one rooted class per size by translations; no global optimality claim.",
               "unknown_semantics": "UNKNOWN is preserved and supplies no bound beyond the independently checked H>=2.",
               "maximum_value_certified": False, "maximizing_collection_complete": False,
               "enumeration_complete": False}
    atomic_text(args.out / "summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=REPO / "results/family1-circulant-family/champions.jsonl")
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Threshold.exe")
    parser.add_argument("--out", type=Path, default=REPO / "out/family1-circulant-threshold34")
    parser.add_argument("--length", type=int, default=34)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("--solve-timeout-ms", type=int, default=5000)
    parser.add_argument("--max-refinements", type=int, default=256)
    parser.add_argument("--projection-masks", type=int, default=64)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if (not 1 <= args.length <= 4096 or not 1 <= args.jobs <= 32 or not 1 <= args.projection_masks <= 64
            or min(args.timeout_ms, args.solve_timeout_ms, args.max_refinements) < 1):
        parser.error("require length1..4096, jobs1..32, masks1..64 and positive SAT budgets")
    args.input, args.exe, args.out = args.input.resolve(), args.exe.resolve(), args.out.resolve()
    records = load_graphs(args.input)
    configuration = {"schema": 1, "input": {"path": str(args.input), "sha256": file_hash(args.input)},
                     "native_executable": {"path": str(args.exe), "sha256": file_hash(args.exe)},
                     "driver": {"path": str(Path(__file__).resolve()), "sha256": file_hash(Path(__file__))},
                     "length": args.length, "jobs": args.jobs, "timeout_ms": args.timeout_ms,
                     "solve_timeout_ms": args.solve_timeout_ms, "max_refinements": args.max_refinements,
                     "projection_masks": args.projection_masks,
                     "sizes": list(range(8, 21)), "keys": [record["key"] for record in records]}
    args.out.mkdir(parents=True, exist_ok=True)
    run_path = args.out / "run.json"
    if args.resume:
        if json.loads(run_path.read_text()) != configuration:
            raise ValueError("resume requires identical pinned input/executable/driver and query settings")
    else:
        if any(args.out.iterdir()):
            raise ValueError("new batch requires an empty output directory; use --resume")
        atomic_text(run_path, json.dumps(configuration, indent=2) + "\n")
    results = {}
    export(args, results, configuration)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(query, record, args): record["m"] for record in records}
        for future in as_completed(futures):
            record = future.result()
            results[record["m"]] = record
            export(args, results, configuration)
            print(compact({"m": record["m"], "decision": record["threshold_decision"],
                           "lower_bound": record["lower_bound"], "upper_bound": record["upper_bound"],
                           "reason": record["reason"], "seconds": record["native_answer"]["seconds"]}), flush=True)
    summary = export(args, results, configuration)
    print(compact({"out": str(args.out), "completed": len(results), "decision_counts": summary["decision_counts"]}))


if __name__ == "__main__":
    main()

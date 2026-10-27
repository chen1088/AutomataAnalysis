#!/usr/bin/env python3
"""Freeze graph-only inputs, run the new finder, then attach exhaustive truth."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

REPO = Path(__file__).resolve().parents[1]


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def ref(path):
    path = path.resolve()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def key(table):
    return "".join(f"{q:02d}" for row in table for q in row)


def replay(row):
    first, second = row["witness"]
    assert first != second and len(first) == len(second) == row["upper_bound"]
    assert row["upper_bound"] <= row["max_length"]
    assert all(word and set(word) <= {"0", "1"} for word in [first, second])
    table = row["canonical_table"]
    trace = [0] * (len(first) + 1)
    for mask in range(1 << len(table)):
        left = right = 0
        for i, (a, b) in enumerate(zip(first, second), 1):
            left = table[left][int(a) ^ ((mask >> left) & 1)]
            right = table[right][int(b) ^ ((mask >> right) & 1)]
            trace[i] += left != right
        assert left == right
    assert row["witness_metric_trace"] == trace
    assert row["synchronized_count_trace"] == [(1 << len(table)) - d for d in trace]
    assert row["static_masks_verified"] == 1 << len(table)
    assert row["minimality_certified"] == (row["lower_bound"] == row["upper_bound"])
    assert row["k"] == (None if row["producer"] == "exact-word-layers" else row["configured_joint_k"])
    return 1 << len(table)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pool", action="append", type=Path)
    parser.add_argument("--exact", action="append", type=Path, default=[])
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--beam", type=int, default=16)
    parser.add_argument("--seed-mode", choices=["scored", "compact"], default="scored")
    parser.add_argument("--seed-ranking", choices=["full", "common-max", "common-sum", "portfolio"], default="portfolio")
    parser.add_argument("--fallback-compact", choices=["on", "off"], default="on")
    parser.add_argument("--catalogue", type=int, default=16384)
    parser.add_argument("--starts", type=int, default=512)
    parser.add_argument("--prefix-depth", type=int, default=20)
    parser.add_argument("--prefix-words", type=int, default=1048576)
    parser.add_argument("--exact-depth", type=int, default=24)
    parser.add_argument("--exact-words", type=int, default=16777216)
    parser.add_argument("--exact-memory-mib", type=int, default=256)
    parser.add_argument("--max-length", type=int, default=80)
    parser.add_argument("--expansions", type=int, default=2000000)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    sources = args.pool or [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"]
    cases = {}
    for path in sources:
        for row in rows(path):
            table = row["canonical_table"]
            identity = len(table), key(table)
            cases[identity] = {"m": len(table), "key": identity[1], "canonical_table": table}
    cases = [cases[identity] for identity in sorted(cases)]
    assert cases
    config = {name: str(value.resolve()) if isinstance(value, Path) else value
              for name, value in vars(args).items() if name not in ["resume", "pool", "exact"]}
    manifest = {"configuration": config, "candidate_sources": [ref(path) for path in sources],
                "query_inputs": "canonical graph tables and frozen configuration only; no answer/pair hints",
                "script": ref(Path(__file__)), "executable": ref(args.exe), "cases": cases, "randomness": False}
    args.out.mkdir(parents=True, exist_ok=True)
    if (args.out / "manifest.json").exists():
        assert args.resume and json.loads((args.out / "manifest.json").read_text()) == manifest
    else:
        assert not args.resume and not any(args.out.iterdir())
        save(args.out / "manifest.json", manifest)
        shutil.copy2(__file__, args.out / "benchmark-source.py")
    batches = []
    for m in sorted({case["m"] for case in cases}):
        group = [case for case in cases if case["m"] == m]
        for offset in range(0, len(group), args.batch):
            batches.append(group[offset:offset + args.batch])
    started = time.monotonic()

    def query(index, batch):
        folder = args.out / "batches" / f"{index:05d}"
        command = [str(args.exe.resolve()), "--m", str(batch[0]["m"]), "--out", str(folder.resolve()),
                   "--k", str(args.k), "--beam", str(args.beam), "--seed-mode", args.seed_mode,
                   "--seed-ranking", args.seed_ranking,
                   "--fallback-compact", args.fallback_compact,
                   "--catalogue", str(args.catalogue), "--starts", str(args.starts),
                   "--prefix-depth", str(args.prefix_depth), "--prefix-words", str(args.prefix_words),
                   "--exact-depth", str(args.exact_depth), "--exact-words", str(args.exact_words),
                   "--exact-memory-mib", str(args.exact_memory_mib), "--max-length", str(args.max_length),
                   "--expansions", str(args.expansions)]
        for case in batch:
            command += ["--graph", case["key"]]
        if not (folder / "summary.json").exists():
            folder.parent.mkdir(parents=True, exist_ok=True)
            run = subprocess.run(command, capture_output=True, text=True)
            assert run.returncode == 0, run.stderr
        native = json.loads((folder / "run.json").read_text())
        summary = json.loads((folder / "summary.json").read_text())
        result = rows(folder / "records.jsonl")
        assert native["executable_sha256"] == manifest["executable"]["sha256"]
        assert native["configured_joint_k"] == args.k and native["seed_mode"] == args.seed_mode
        assert native["seed_ranking"] == args.seed_ranking
        assert native["beam_width"] == args.beam and native["selected_pairs"] == args.starts
        for field, expected in {"catalogue_size": args.catalogue, "prefix_depth": args.prefix_depth,
                                "prefix_words": args.prefix_words, "exact_depth": args.exact_depth,
                                "exact_max_words": args.exact_words, "exact_memory_bytes": args.exact_memory_mib << 20,
                                "max_length": args.max_length, "expansion_cap": args.expansions}.items():
            assert native[field] == expected, field
        assert native["retry_compact_on_miss"] == (args.fallback_compact == "on")
        assert native["graphs"] == [case["key"] for case in batch]
        assert summary["all_supplied_graphs_tested"] is True
        assert summary["records_sha256"] == ref(folder / "records.jsonl")["sha256"]
        assert summary["run_sha256"] == ref(folder / "run.json")["sha256"]
        assert summary["witnesses_sha256"] == ref(folder / "witnesses.jsonl")["sha256"]
        assert [row["key"] for row in result] == native["graphs"]
        replays = 0
        for row in result + rows(folder / "witnesses.jsonl"):
            assert row["deterministic"] is True and row["configured_joint_k"] == args.k
            assert row["run_sha256"] == summary["run_sha256"]
            assert row["alphabet"] == ["00", "01", "10", "11"]
            if row["upper_bound"] is not None:
                replays += replay(row)
            else:
                assert row["witness"] is None and not row["minimality_certified"]
        assert all(row["partial_windows"] == 0 for row in result)
        return result, replays

    result, checks = [], 0
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures = [workers.submit(query, index, batch) for index, batch in enumerate(batches)]
        for count, future in enumerate(as_completed(futures), 1):
            current, replayed = future.result()
            result += current
            checks += replayed
            print(json.dumps({"batches": count, "total": len(batches), "graphs": len(result),
                              "joint_k": args.k, "seconds": round(time.monotonic() - started, 3)}), flush=True)
    result.sort(key=lambda row: (row["m"], row["key"]))
    assert [(row["m"], row["key"]) for row in result] == [(case["m"], case["key"]) for case in cases]
    output = args.out / "records.jsonl"
    output.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in result))
    save(args.out / "query-seal.json", {"records": ref(output), "all_cases_queried": True, "truth_not_used_in_queries": True})
    champions, exact = set(), {}
    truth_sources = [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"]
    for path in truth_sources:
        for row in rows(path):
            identity = row["m"], key(row["canonical_table"])
            champions.add(identity); exact[identity] = row["merge_length"]
    for path in args.exact:
        for row in rows(path):
            if row.get("status") == "exact":
                identity = len(row["canonical_table"]), key(row["canonical_table"])
                if identity in exact:
                    assert exact[identity] == row["merge_length"], "conflicting exact reference"
                exact[identity] = row["merge_length"]
    measurements = []
    for row in result:
        identity = row["m"], row["key"]
        h = exact.get(identity)
        upper = row["upper_bound"]
        gap = None if h is None or upper is None else upper - h
        assert gap is None or gap >= 0
        if h is not None:
            assert row["lower_bound"] <= h
            if row["exact"]:
                assert upper == h, "false exactness claim"
        measurements.append({"m": row["m"], "key": row["key"], "configured_joint_k": args.k,
                             "producing_k": row["k"], "producer": row["producer"],
                             "reference_H": h, "champion": identity in champions,
                             "upper": upper, "lower": row["lower_bound"], "exact_certified": row["exact"],
                             "gap": gap, "first": row["witness"][0] if upper is not None else "",
                             "second": row["witness"][1] if upper is not None else "",
                             "D_trace": json.dumps(row["witness_metric_trace"], separators=(",", ":")),
                             "nodes": row["expanded_nodes"], "exact_words": row["exact_evaluated_words"],
                             "prefix_words": row["prefix_words_evaluated"]})
    with (args.out / "cases.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(measurements[0]))
        writer.writeheader(); writer.writerows(measurements)
    evaluated = [row for row in measurements if row["reference_H"] is not None]
    gaps = [row["gap"] for row in evaluated if row["gap"] is not None]
    summary = {"cases": len(result), "configured_joint_k": args.k, "seed_mode": args.seed_mode, "seed_ranking": args.seed_ranking,
               "oracle_producing_k": None, "oracle_depth": args.exact_depth,
               "found": sum(row["upper_bound"] is not None for row in result),
               "misses": sum(row["upper_bound"] is None for row in result),
               "exact_reference_cases": len(evaluated), "optimal_pairs": gaps.count(0),
               "within_one": sum(gap <= 1 for gap in gaps),
               "within_two": sum(gap <= 2 for gap in gaps), "maximum_gap_if_found": max(gaps) if gaps else None,
               "all_exact_reference_cases_within_one": (len(gaps) == len(evaluated) and all(gap <= 1 for gap in gaps)) if evaluated else None,
               "all_exact_reference_cases_within_two": (len(gaps) == len(evaluated) and all(gap <= 2 for gap in gaps)) if evaluated else None,
               "all_exact_reference_cases_optimal": (len(gaps) == len(evaluated) and all(gap == 0 for gap in gaps)) if evaluated else None,
               "upper_histogram": dict(sorted(Counter(row["upper_bound"] for row in result if row["upper_bound"] is not None).items())),
               "m7_lengths": [row["upper_bound"] for row in result if row["m"] == 7],
               "expanded_nodes": sum(row["expanded_nodes"] for row in result),
               "exact_evaluated_words": sum(row["exact_evaluated_words"] for row in result),
               "prefix_words_evaluated": sum(row["prefix_words_evaluated"] for row in result),
               "partial_windows": sum(row["partial_windows"] for row in result),
               "expansion_capped_graphs": sum(row["expansion_limit_reached"] for row in result),
               "independent_final_and_improvement_mask_replays": checks,
               "observed_wall_seconds": time.monotonic() - started, "records": ref(output),
               "truth_loaded_after_query_seal": True, "truth_sources": [ref(path) for path in truth_sources + args.exact],
               "universal_error_bound_certified": False}
    save(args.out / "summary.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()

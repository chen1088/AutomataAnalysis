#!/usr/bin/env python3
"""Run deterministic graph-only adaptive-window queries before attaching truth."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

REPO = Path(__file__).resolve().parents[1]
SOURCES = [
    "tests/Family1AdaptiveWindowBenchmark.cpp", "HardPairJointAdaptive.h",
    "Family1ScoredSeeds.h", "Family1TailScoredSeeds.h", "Family1JointPair.h",
    "Family1JointSeeds.h", "HardPairJointFinder.h", "HardPairPrefixSeeds.h",
    "Family1ExactPacked.h", "Family1ExactPacked.cpp", "Family1LargeGraph.h",
    "Family1LargeGraph.cpp", "Family1PairAgreement.h", "Family1CliArtifacts.h",
    "HardPairViability.h",
]
DEFAULT_CONFIGS = [
    "block4:fixed-block:4:4:16:0:1:block",
    "rolling4:fixed-roll:4:4:16:0:1:first",
    "rolling2:fixed-roll:2:2:16:0:1:first",
    "rolling5:fixed-roll:5:5:16:0:1:first",
    "variance-low:total-roll:2:5:16:1000:1:first",
    "variance-mid:total-roll:2:5:16:10000:1:first",
    "variance-high:total-roll:2:5:16:40000:1:first",
    "action-low:action-roll:2:5:16:1000:1:first",
    "action-mid:action-roll:2:5:16:10000:1:first",
    "variance-deeper:total-roll:4:6:16:10000:1:first",
    "variance-progress:progress-roll:2:6:16:10000:1:first",
]


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def ref(path):
    path = path.resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def graph_key(table):
    return "".join(f"{q:02d}" for ports in table for q in ports)


def replay(row, table):
    pair = row["witness"]
    if pair is None:
        assert row["upper_bound"] is None
        return 0
    a, b = pair
    assert a != b and len(a) == len(b) == row["upper_bound"]
    assert all(word and set(word) <= {"0", "1"} for word in pair)
    trace = [0] * (len(a) + 1)
    for mask in range(1 << len(table)):
        q = r = 0
        for i, (x, y) in enumerate(zip(a, b), 1):
            q = table[q][int(x) ^ ((mask >> q) & 1)]
            r = table[r][int(y) ^ ((mask >> r) & 1)]
            trace[i] += q != r
        assert q == r
    assert trace == row["witness_metric_trace"]
    if "synchronized_count_trace" in row:
        assert row["synchronized_count_trace"] == [(1 << len(table)) - d for d in trace]
    return 1 << len(table)


def configuration(text):
    fields = text.split(":")
    if len(fields) != 8:
        raise ValueError("config needs name:policy:min_k:max_k:beam:threshold_ppm:priority:advance")
    name, policy, lo, hi, beam, threshold, priority, advance = fields
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
        raise ValueError("invalid configuration name")
    if policy not in {"fixed-block", "fixed-roll", "total-roll", "action-roll", "progress-roll"}:
        raise ValueError("invalid policy")
    result = dict(name=name, policy=policy, min_k=int(lo), max_k=int(hi), beam_width=int(beam),
                  threshold_ppm=int(threshold), priority=bool(int(priority)), advance=advance)
    assert 1 <= result["min_k"] <= result["max_k"] <= 8
    assert 1 <= result["beam_width"] <= 4096 and 0 <= result["threshold_ppm"] <= 1000000
    assert priority in {"0", "1"} and advance in {"first", "block"}
    assert advance == ("block" if policy == "fixed-block" else "first")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pool", type=Path, action="append", default=[])
    parser.add_argument("--config", action="append")
    parser.add_argument("--starts", type=int, default=64)
    parser.add_argument("--max-length", type=int, default=80)
    parser.add_argument("--expansions", type=int, default=2000000)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    assert args.starts > 0 and args.jobs > 0 and args.expansions > 0
    if args.out.exists():
        raise ValueError("output directory must be fresh")
    args.out.mkdir(parents=True)
    pools = args.pool or [REPO / "results/family1-m1-m6/maximizers.jsonl",
                          REPO / "results/family1-m7/maximizers.jsonl"]
    geometry = {}
    for path in pools:
        for row in rows(path):
            table = row["canonical_table"]
            key = graph_key(table)
            geometry[len(table), key] = dict(m=len(table), key=key, canonical_table=table)
    cases = [geometry[identity] for identity in sorted(geometry)]
    configs = [configuration(text) for text in (args.config or DEFAULT_CONFIGS)]
    assert cases and len({c["name"] for c in configs}) == len(configs)
    native = args.out / "native"
    native.mkdir()
    exe = native / args.exe.name
    shutil.copy2(args.exe, exe)
    inventory = []
    for name in SOURCES:
        source = REPO / name
        target = native / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        inventory.append(dict(path=name, sha256=ref(source)["sha256"]))
    fingerprint = hashlib.sha256("".join(item["sha256"] + "\n" for item in inventory).encode()).hexdigest()
    (args.out / "keys.txt").write_text("".join(c["key"] + "\n" for c in cases))
    config_file = args.out / "configs.txt"
    config_file.write_text("".join(" ".join(str(int(c[f])) if f == "priority" else str(c[f]) for f in
        ["name", "policy", "min_k", "max_k", "beam_width", "threshold_ppm", "priority", "advance"]) + "\n" for c in configs))
    save(args.out / "manifest.json", dict(schema=1, cases=cases, configurations=configs,
         exact_depth=0, oracle_disabled=True, alphabet=["00", "01", "10", "11"],
         starts_per_ranking=args.starts, seed_ranking="full-D then common-max", catalogue_size=16384,
         prefix_depth=20, prefix_words=1048576, max_length=args.max_length,
         expansions_per_attempt=args.expansions, randomness=False, time_caps=False,
         executable=ref(exe), source_inventory=inventory, source_sha256=fingerprint,
         geometry_sources=[ref(p) for p in pools], runner=ref(Path(__file__))))
    started = time.monotonic()

    def query(index, case):
        folder = args.out / "queries" / f"{index:04d}-{case['key']}"
        folder.mkdir(parents=True)
        keys = folder / "keys.txt"
        keys.write_text(case["key"] + "\n")
        with (folder / "stdout.log").open("w") as log:
            subprocess.run([str(exe.resolve()), str(keys.resolve()), str(config_file.resolve()),
                            str((folder / 'native').resolve()), str(args.starts), str(args.max_length),
                            str(args.expansions)], check=True, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
        records = rows(folder / "native/records.jsonl")
        assert len(records) == len(configs)
        assert {r["config"] for r in records} == {c["name"] for c in configs}
        for row in records:
            assert row["key"] == case["key"] and row["source_sha256"] == fingerprint
            assert row["canonical_table"] == case["canonical_table"]
            assert row["exact_depth"] == 0 and row["partial_windows"] == 0
            config = next(c for c in configs if c["name"] == row["config"])
            for field, native_field in [("min_k", "configured_k_min"), ("max_k", "configured_k_max"),
                                        ("beam_width", "beam_width"), ("threshold_ppm", "threshold_ppm"),
                                        ("priority", "priority"), ("policy", "policy"), ("advance", "advance")]:
                assert row[native_field] == config[field], (native_field, row["config"])
            assert row["randomness"] is False and row["time_caps"] is False
            assert row["max_length"] == args.max_length and row["expansion_cap"] == args.expansions
            assert row["starts_per_ranking"] == args.starts and row["lower_bound"] == 1
            assert row["alphabet"] == ["00", "01", "10", "11"]
            assert row["expanded_nodes"] == sum(4 ** k * n for k, n in enumerate(row["completed_k_histogram"]))
            assert row["complete_layers"] == sum(row["completed_k_histogram"])
            assert row["criterion_windows"] == sum(row["tested_k_histogram"])
            assert row["attempts"] + row["skipped_starts"] == row["selected_starts"]
            replay(row, case["canonical_table"])
        for row in rows(folder / "native/improvements.jsonl"):
            assert row["key"] == case["key"]
            replay(row, case["canonical_table"])
        return records

    output = []
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        pending = [workers.submit(query, i, c) for i, c in enumerate(cases)]
        for future in as_completed(pending):
            output.extend(future.result())
            print(json.dumps(dict(completed_cases=len(output) // len(configs), cases=len(cases),
                                  configured_k_ranges=sorted({(c['min_k'], c['max_k']) for c in configs}),
                                  seconds=round(time.monotonic() - started, 3))), flush=True)
    output.sort(key=lambda r: (r["m"], r["key"], r["config"]))
    assert {(r["key"], r["config"]) for r in output} == {(c["key"], s["name"]) for c in cases for s in configs}
    path = args.out / "records.jsonl"
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in output))
    save(args.out / "query-seal.json", dict(records=ref(path), all_configured_cases_completed=True,
         case_count=len(cases), configuration_count=len(configs), rows=len(output),
         truth_not_used_in_queries=True, truth_not_loaded_until_after_query_seal=True,
         native_journals=[ref(p) for p in sorted((args.out / "queries").glob("*/native/*.jsonl"))]))
    # Only after sealing all query bytes may exact H labels enter the analysis.
    truth = {}
    for source in [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"]:
        for row in rows(source):
            truth[graph_key(row["canonical_table"])] = row["merge_length"]
    summaries = []
    for config in configs:
        data = [r for r in output if r["config"] == config["name"]]
        known = [r for r in data if r["key"] in truth]
        gaps = [r["upper_bound"] - truth[r["key"]] for r in known if r["upper_bound"] is not None]
        assert all(g >= 0 for g in gaps)
        summaries.append(dict(configuration=config, cases=len(data), found=sum(r["upper_bound"] is not None for r in data),
             reference_cases=len(known), optimal=gaps.count(0), within_one=sum(g <= 1 for g in gaps),
             within_two=sum(g <= 2 for g in gaps), max_gap=max(gaps, default=None),
             m7_winner_lengths=[r["upper_bound"] for r in known if r["m"] == 7],
             expanded_nodes=sum(r["expanded_nodes"] for r in data)))
    save(args.out / "summary.json", dict(configurations=summaries, oracle_disabled=True,
         all_configured_cases_completed=True, query_seal=ref(args.out / "query-seal.json"),
         wall_seconds=time.monotonic() - started))
    print(json.dumps(summaries, indent=2), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Benchmark deterministic graph-derived starts with full joint continuation."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import time

REPO = Path(__file__).resolve().parents[1]


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def ref(path):
    path = path.resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def scalar(row):
    table, pair = row["canonical_table"], row["witness"]
    assert pair[0] != pair[1] and len(pair[0]) == len(pair[1]) == row["upper_bound"]
    trace = [0] * (len(pair[0]) + 1)
    for mask in range(1 << len(table)):
        a = b = 0
        for depth, (x, y) in enumerate(zip(*pair), 1):
            a = table[a][int(x) ^ ((mask >> a) & 1)]
            b = table[b][int(y) ^ ((mask >> b) & 1)]
            trace[depth] += a != b
        assert a == b
    assert trace == row["witness_metric_trace"]
    return 1 << len(table)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/joint-solid-linux/Family1Joint")
    parser.add_argument("--out", type=Path, default=REPO / "out/family1-finder-strategies-20261026/prefix")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--config", action="append", help="Override matrix: k:beam:prefix_pairs:total|permutation")
    parser.add_argument("--prefix-depth", type=int, default=16)
    parser.add_argument("--prefix-words", type=int, default=65536)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    sources = [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"]
    # Geometry only. Scores and reference witnesses are not native query inputs.
    cases = sorted([{"m": row["m"], "key": "".join(f"{v:02d}" for p in row["canonical_table"] for v in p),
                     "canonical_table": row["canonical_table"]} for src in sources for row in rows(src)],
                   key=lambda row: (row["m"], row["key"]))
    configurations = [
        {"k": 4, "beam": 1, "score": "total", "prefix_pairs": 128},
        {"k": 4, "beam": 1, "score": "permutation", "prefix_pairs": 128},
        {"k": 4, "beam": 4, "score": "permutation", "prefix_pairs": 128},
        {"k": 6, "beam": 1, "score": "permutation", "prefix_pairs": 128},
        {"k": 4, "beam": 1, "score": "permutation", "prefix_pairs": 1024},
        {"k": 4, "beam": 4, "score": "permutation", "prefix_pairs": 1024},
    ]
    if args.config:
        configurations = []
        for value in args.config:
            k, beam, pairs, score = value.split(":")
            assert score in ["total", "permutation"]
            configurations.append({"k": int(k), "beam": int(beam), "prefix_pairs": int(pairs), "score": score})
    for config in configurations:
        config["id"] = f"k{config['k']}-b{config['beam']}-{config['score']}-p{config['prefix_pairs']}"
    manifest = {"cases": cases, "configurations": configurations, "executable": ref(args.exe),
                "source": ref(Path(__file__)), "candidate_sources": [ref(path) for path in sources],
                "fixed": {"max_length": 80, "expansions_per_attempt": 2000000, "prefix_depth": args.prefix_depth,
                          "prefix_words": args.prefix_words, "common_prefix_strata": 8, "diagonal": 0,
                          "unequal": 0, "target_upper": 0},
                "search_randomness": False, "alphabet": ["00", "01", "10", "11"]}
    if (args.out / "manifest.json").exists():
        assert args.resume and json.loads((args.out / "manifest.json").read_text()) == manifest
    else:
        assert not args.resume
        save(args.out / "manifest.json", manifest)
        (args.out / "candidates.jsonl").write_text("".join(json.dumps(case) + "\n" for case in cases))
    started = time.monotonic()

    def query(case, config):
        out = args.out / config["id"] / case["key"]
        command = [str(args.exe.resolve()), "--m", str(case["m"]), "--graph", case["key"],
                   "--k", str(config["k"]), "--beam", str(config["beam"]), "--diagonal-beam", "0",
                   "--startup", "legacy", "--score", config["score"], "--prefix-pairs", str(config["prefix_pairs"]),
                   "--prefix-depth", str(args.prefix_depth), "--prefix-words", str(args.prefix_words), "--common-prefix-depth", "8",
                   "--max-length", "80", "--expansions", "2000000", "--out", str(out.resolve())]
        if not (out / "summary.json").exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            run = subprocess.run(command, text=True, capture_output=True)
            assert run.returncode == 0, run.stderr
        native = json.loads((out / "run.json").read_text())
        assert native["executable_sha256"] == manifest["executable"]["sha256"]
        assert native["k"] == config["k"] and native["score"] == config["score"]
        record, = rows(out / "records.jsonl")
        assert record["key"] == case["key"] and record["partial_windows"] == 0
        if record["upper_bound"] is not None:
            scalar(record)
        for improvement in rows(out / "witnesses.jsonl"):
            scalar(improvement)
        record["strategy"] = config["id"]
        return record

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(query, case, config) for config in configurations for case in cases]
        for index, future in enumerate(as_completed(futures), 1):
            record = future.result()
            results.append(record)
            print(json.dumps({"complete": index, "total": len(futures), "m": record["m"], "key": record["key"],
                              "strategy": record["strategy"], "upper": record["upper_bound"],
                              "seconds": round(time.monotonic() - started, 2)}), flush=True)
    results.sort(key=lambda row: (row["strategy"], row["m"], row["key"]))
    output = args.out / "records.jsonl"
    output.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in results))
    save(args.out / "query-seal.json", {"records": ref(output), "all_queries_complete": True})
    # The target scores enter only after the full query output is sealed.
    truth = {(row["m"], "".join(f"{v:02d}" for p in row["canonical_table"] for v in p)): row["merge_length"]
             for src in sources for row in rows(src)}
    analysis = []
    for config in configurations:
        selected = [row for row in results if row["strategy"] == config["id"]]
        positives = [row for row in selected if row["upper_bound"] is not None]
        gaps = [row["upper_bound"] - truth[row["m"], row["key"]] for row in positives]
        assert all(gap >= 0 for gap in gaps)
        analysis.append({"configuration": config, "cases": len(selected), "found": len(positives),
                         "exact": gaps.count(0), "within_two": sum(gap <= 2 for gap in gaps),
                         "max_gap": max(gaps) if gaps else None,
                         "m7_lengths": [row["upper_bound"] for row in selected if row["m"] == 7],
                         "nodes": sum(row["expanded_nodes"] for row in selected)})
    save(args.out / "summary.json", {"analysis": analysis, "records": ref(output),
                                     "wall_seconds": time.monotonic() - started})
    print(json.dumps(analysis), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Test every supplied graph with deterministic four-symbol joint lookahead."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

REPO = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def rows(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def checked_batch(directory, keys, config):
    native = json.loads((directory / "run.json").read_text())
    summary = json.loads((directory / "summary.json").read_text())
    result = rows(directory / "records.jsonl")
    assert native["executable_sha256"] == config["executable_sha256"]
    assert native["k"] == config["k"] and native["deterministic"] is True
    assert native["beam_width"] == config["beam"] and native["diagonal_width"] == config["diagonal_beam"]
    assert native.get("unequal_width", 0) == config["unequal_beam"]
    assert native.get("prefix_pairs", 0) == config["prefix_pairs"]
    assert native.get("target_upper", 0) == config["target_upper"]
    assert native["max_length"] == config["max_length"] and native["max_expansions"] == config["expansions"]
    assert native["m"] == config["m"] and native["graphs"] == keys
    assert summary["records_sha256"] == digest(directory / "records.jsonl")
    assert summary["all_supplied_graphs_tested"] is True and summary["graphs"] == len(keys)
    assert [record["key"] for record in result] == keys
    for record in result:
        assert record["k"] == config["k"] and record["alphabet"] == ["00", "01", "10", "11"]
        assert record["partial_windows"] == 0 and record["deterministic"] is True
        assert record["lower_bound"] == 1 and record["minimality_certified"] is False
        for window in record["window_reports"]:
            assert window["complete"] is True
            assert window["leaves"] == window["expected_leaves"] == 4 ** window["span"]
            assert window["nodes"] == sum(4 ** depth for depth in range(1, window["span"] + 1))
        if record["upper_bound"] is not None:
            first, second = record["witness"]
            assert first != second and len(first) == len(second) == record["upper_bound"]
            assert record["static_masks_verified"] == 1 << config["m"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--beam", type=int, default=1)
    parser.add_argument("--diagonal-beam", type=int, default=0)
    parser.add_argument("--unequal-beam", type=int, default=0)
    parser.add_argument("--prefix-pairs", type=int, default=0)
    parser.add_argument("--prefix-depth", type=int, default=16)
    parser.add_argument("--prefix-words", type=int, default=65536)
    parser.add_argument("--common-prefix-depth", type=int, default=8)
    parser.add_argument("--target-upper", type=int, default=0)
    parser.add_argument("--max-length", type=int, default=80)
    parser.add_argument("--expansions", type=int, default=2000000)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    assert 1 <= args.k <= 8 and 1 <= args.beam <= 4096 and 0 <= args.diagonal_beam <= 4096
    assert 0 <= args.unequal_beam <= 4096 and args.prefix_pairs >= 0 and args.target_upper >= 0
    assert args.jobs > 0 and args.batch > 0 and args.expansions > 0
    supplied = rows(args.candidates)
    keyed = {row["key"]: row for row in supplied}
    assert len(keyed) == len(supplied) and supplied, "candidate list must be nonempty and unique"
    sizes = {len(row["canonical_table"]) for row in supplied}
    assert len(sizes) == 1, "one exact graph size per campaign"
    m = sizes.pop()
    for key, row in keyed.items():
        assert row.get("m", m) == m and len(key) == 4 * m
        assert key == "".join(f"{target:02d}" for ports in row["canonical_table"] for target in ports)
    keys = sorted(keyed)
    args.out = args.out.resolve()
    config = {name: str(value.resolve()) if isinstance(value, Path) else value
              for name, value in vars(args).items() if name != "resume"}
    config.update({"m": m, "candidate_count": len(keys), "candidate_sha256": digest(args.candidates),
                   "executable_sha256": digest(args.exe), "script_sha256": digest(__file__),
                   "alphabet": ["00", "01", "10", "11"], "deterministic": True,
                   "coverage_rule": "every supplied candidate tested; no selection, sampling, or time caps"})
    manifest = args.out / "campaign.json"
    if manifest.exists():
        assert args.resume and json.loads(manifest.read_text()) == config, "resume requires identical inputs and settings"
    else:
        assert not args.resume and (not args.out.exists() or not any(args.out.iterdir())), "use a fresh output directory"
        args.out.mkdir(parents=True, exist_ok=True)
        save(manifest, config)
        shutil.copy2(args.candidates, args.out / "candidates.jsonl")
        shutil.copy2(__file__, args.out / "campaign-source.py")
    batches = [keys[start:start + args.batch] for start in range(0, len(keys), args.batch)]
    started = time.monotonic()

    def evaluate(index):
        directory = args.out / "batches" / f"{index:05d}"
        directory.mkdir(parents=True, exist_ok=True)
        attempts = sorted(directory.glob("attempt-*"))
        for attempt in attempts:
            if (attempt / "summary.json").exists():
                return checked_batch(attempt, batches[index], config)
        attempt = directory / f"attempt-{len(attempts):03d}"
        command = [str(args.exe.resolve()), "--m", str(m), "--out", str(attempt),
                   "--k", str(args.k), "--beam", str(args.beam),
                   "--diagonal-beam", str(args.diagonal_beam), "--max-length", str(args.max_length),
                   "--expansions", str(args.expansions)]
        if args.unequal_beam:
            command += ["--unequal-beam", str(args.unequal_beam)]
        if args.prefix_pairs:
            command += ["--prefix-pairs", str(args.prefix_pairs), "--prefix-depth", str(args.prefix_depth),
                        "--prefix-words", str(args.prefix_words), "--common-prefix-depth", str(args.common_prefix_depth)]
        if args.target_upper:
            command += ["--target-upper", str(args.target_upper)]
        for key in batches[index]:
            command += ["--graph", key]
        save(directory / f"command-{len(attempts):03d}.json", command)
        process = subprocess.run(command, capture_output=True, text=True)
        (directory / f"log-{len(attempts):03d}.txt").write_text(process.stdout + process.stderr)
        if process.returncode:
            raise RuntimeError(f"joint k={args.k} batch {index} failed: {process.stderr}")
        return checked_batch(attempt, batches[index], config)

    records = []
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures = [workers.submit(evaluate, index) for index in range(len(batches))]
        for count, future in enumerate(as_completed(futures), 1):
            records.extend(future.result())
            if count % 10 == 0 or count == len(batches):
                print(json.dumps({"joint_k": args.k, "completed_batches": count, "total_batches": len(batches),
                                  "graphs": len(records), "pairs": sum(row["upper_bound"] is not None for row in records),
                                  "seconds": round(time.monotonic() - started, 2)}), flush=True)
    records.sort(key=lambda row: row["key"])
    assert [row["key"] for row in records] == keys
    output = args.out / "records.jsonl"
    output.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in records))
    lengths = Counter(row["upper_bound"] for row in records if row["upper_bound"] is not None)
    summary = {"m": m, "k": args.k, "alphabet": config["alphabet"], "deterministic": True,
               "candidate_count": len(keys), "all_candidates_tested": True,
               "positive_count": sum(lengths.values()), "no_pair": len(keys) - sum(lengths.values()),
               "upper_at_most_50": sum(count for length, count in lengths.items() if length <= 50),
               "upper_above_50": sum(count for length, count in lengths.items() if length > 50),
               "upper_histogram": dict(sorted(lengths.items())),
               "complete_windows": sum(row["complete_windows"] for row in records),
               "partial_windows": sum(row["partial_windows"] for row in records),
               "expansion_capped_graphs": sum(row["expansion_limit_reached"] for row in records),
               "minimality_certified": False, "global_maximum_certified": False,
               "records_sha256": digest(output), "campaign_sha256": digest(manifest),
               "wall_seconds": round(time.monotonic() - started, 3)}
    save(args.out / "summary.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()

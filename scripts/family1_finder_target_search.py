#!/usr/bin/env python3
"""Adaptive blind target experiment on the eight certified m7 maximizers.

Each graph stops after an independently verified target-length hit. This is a
recovery experiment, not a controlled comparison of k values. Saved witness
strings are never supplied to the finder. A new empty output directory is used.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

REPO = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def integers(values):
    return [int(part) for value in values for part in str(value).split(",")]


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def verify(table, words):
    if (not isinstance(words, list) or len(words) != 2 or words[0] == words[1]
            or len(words[0]) != len(words[1]) or not words[0]
            or any(not isinstance(w, str) or set(w) - {"0", "1"} for w in words)):
        raise ValueError("Invalid distinct equal-length binary witness")
    for mask in range(128):
        states = [0, 0]
        for side, word in enumerate(words):
            for letter in word:
                state = states[side]
                states[side] = table[state][int(letter) ^ ((mask >> state) & 1)]
        if states[0] != states[1]:
            raise ValueError(f"Witness fails independent static mask {mask}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--k", nargs="+", default=[2, 4, 6])
    parser.add_argument("--beam", nargs="+", default=[4])
    parser.add_argument("--tail", nargs="+", default=[8])
    parser.add_argument("--seeds", nargs="+", default=[1088])
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--attempts", type=int, default=128)
    parser.add_argument("--prefix-max-pairs", type=int, default=128)
    parser.add_argument("--prefix-depth", type=int, default=16)
    parser.add_argument("--prefix-max-words", type=int, default=65536)
    parser.add_argument("--prefix-samples-per-depth", type=int, default=16384)
    parser.add_argument("--tail-max-states", type=int, default=100000)
    parser.add_argument("--max-expansions", type=int)
    parser.add_argument("--distance-coordinates", type=int, default=0)
    parser.add_argument("--beam-ranking", choices=("drop", "remaining"), default="drop")
    parser.add_argument("--prefix-common-depth", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--length", type=int, default=34)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    ks, beams, tails, seeds = map(integers, (args.k, args.beam, args.tail, args.seeds))
    if (not ks or not beams or not tails or not seeds or min(ks + beams) < 1 or min(tails + seeds) < 0
            or min(args.attempts, args.prefix_max_pairs, args.prefix_depth, args.prefix_max_words,
                   args.prefix_samples_per_depth, args.tail_max_states, args.length) < 1
            or not 1 <= args.jobs <= 32 or (args.max_expansions is not None and args.max_expansions < 1)):
        parser.error("Require positive search budgets/k/beam, nonnegative tails/seeds, and jobs1..32")
    args.out, args.exe = args.out.resolve(), args.exe.resolve()
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("A target experiment requires a new empty output directory")
    source = REPO / "results/family1-m7/maximizers.jsonl"
    # Whitelist non-witness fields. Known H controls reporting/target only.
    cases = [{field: row[field] for field in ("m", "ordinal", "key", "canonical_table", "merge_length")}
             for line in source.read_text(encoding="utf-8-sig").splitlines() if (row := json.loads(line))]
    if args.cases:
        selected = set(integers(args.cases))
        cases = [case for case in cases if case["ordinal"] in selected]
        if {case["ordinal"] for case in cases} != selected:
            raise ValueError("Unknown requested m7 case ordinal")
    cases.sort(key=lambda case: case["ordinal"])
    if not cases or any(case["m"] != 7 or case["merge_length"] != 34 for case in cases):
        raise ValueError("Expected certified seven-state H34 cases")
    args.out.mkdir(parents=True, exist_ok=True)
    executable = args.out / "Family1Sample-used.exe"
    shutil.copyfile(args.exe, executable)
    shutil.copyfile(Path(__file__), args.out / "driver-used.py")
    configurations = [dict(k=k, beam=beam, tail=tail, seed=seed)
                      for k, beam, tail, seed in itertools.product(ks, beams, tails, seeds)]
    settings = {name: value for name, value in vars(args).items() if name not in ("exe", "out", "cases", "k", "beam", "tail", "seeds")}
    pin = {"schema": 1, "experiment": "adaptive-target34-recovery-not-controlled-k-grid", "source": {"path": str(source), "sha256": digest(source)},
           "executable": {"original_path": str(args.exe), "saved_file": executable.name, "sha256": digest(executable)},
           "driver_sha256": digest(Path(__file__)), "cases": cases, "configurations": configurations, "settings": settings,
           "saved_witness_or_witness_derived_prefix_hints_used": False, "stop_rule": "Stop further configurations for a graph after verified length34"}
    atomic_json(args.out / "run.json", pin)
    observations, finished = {}, {}
    lock = threading.Lock()

    def export():
        values = [row for key in sorted(observations) for row in observations[key]]
        temporary = args.out / "attempts.jsonl.tmp"
        temporary.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in values), encoding="utf-8")
        temporary.replace(args.out / "attempts.jsonl")
        atomic_json(args.out / "summary.json", {"schema": 1, "cases": len(cases), "finished_cases": len(finished),
            "all_selected_cases_finished": len(finished) == len(cases), "target_hits": sum(row["hit"] for row in finished.values()),
            "native_attempts": len(values), "misses": sum(row["outcome"] == "miss" for row in values),
            "errors": sum(row["outcome"] == "error" for row in values), "results": [finished[key] for key in sorted(finished)],
            "proof_scope": "Every hit independently replayed on all128 static masks; misses give no lower bound; adaptive configs are not a controlled k comparison."})

    def run_case(case):
        ordinal = case["ordinal"]
        directory = args.out / f"case-{ordinal}"; directory.mkdir()
        records, hit = [], False
        for index, config in enumerate(configurations):
            attempt = directory / f"attempt-{index:03d}"; attempt.mkdir()
            native = attempt / "native"
            command = [str(executable), "--graph", case["key"], "--out", str(native), "--mode", "finder",
                "--length", str(args.length), "--samples", str(args.attempts), "--window-k", str(config["k"]),
                "--beam-width", str(config["beam"]), "--tail-threshold", str(config["tail"]), "--seed", str(config["seed"]),
                "--tail-max-states", str(args.tail_max_states), "--prefix-max-pairs", str(args.prefix_max_pairs),
                "--prefix-depth", str(args.prefix_depth), "--prefix-max-words", str(args.prefix_max_words),
                "--prefix-samples-per-depth", str(args.prefix_samples_per_depth)]
            if args.max_expansions is not None:
                command += ["--max-expansions", str(args.max_expansions)]
            if args.distance_coordinates:
                command += ["--distance-coordinates", str(args.distance_coordinates)]
            if args.beam_ranking != "drop":
                command += ["--beam-ranking", args.beam_ranking]
            if args.prefix_common_depth:
                command += ["--prefix-common-depth", str(args.prefix_common_depth)]
            record = {"ordinal": ordinal, "key": case["key"], "known_H": 34, "configuration_index": index,
                      "configuration": config, "command": command, "outcome": "error", "hit": False}
            atomic_json(attempt / "invocation.json", record)
            started = time.perf_counter()
            environment = dict(os.environ)
            environment["PATH"] = str(args.exe.parent) + os.pathsep + environment.get("PATH", "")
            try:
                process = subprocess.run(command, cwd=REPO, env=environment, text=True,
                                         capture_output=True, timeout=args.timeout)
            except subprocess.TimeoutExpired as error:
                from types import SimpleNamespace
                def decoded(value):
                    return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
                process = SimpleNamespace(returncode=124, stdout=decoded(error.stdout),
                                          stderr=decoded(error.stderr) + "\nConfigured native timeout reached.")
                record["timed_out"] = True
            record.update(returncode=process.returncode, invocation_seconds=time.perf_counter() - started)
            (attempt / "stdout.txt").write_text(process.stdout, encoding="utf-8")
            (attempt / "stderr.txt").write_text(process.stderr, encoding="utf-8")
            result_path = native / "result.json"
            try:
                if process.returncode:
                    raise ValueError(f"Native exit {process.returncode}: {process.stderr[-1000:]}")
                answer = json.loads(result_path.read_text(encoding="utf-8-sig"))
                checksum = digest(result_path)
                if (native / "result.sha256").read_text().strip() != checksum or answer["key"] != case["key"] or answer["canonical_table"] != case["canonical_table"]:
                    raise ValueError("Native result hash/graph mismatch")
                if answer["config_sha256"] != digest(native / "run.json"):
                    raise ValueError("Native configuration hash mismatch")
                record.update(native_result={"path": str(result_path), "sha256": checksum}, native_answer=answer,
                              native_seconds=answer.get("seconds"), caps=answer.get("module_stats", {}))
                if answer["decision"] == "collision":
                    verify(case["canonical_table"], answer["witness"])
                    length = len(answer["witness"][0])
                    if length < 34 or length > args.length or answer["upper_bound"] != length:
                        raise ValueError("Witness contradicts known H or the configured length cap")
                    hit = length == 34
                    record.update(outcome="hit" if hit else "above-target", hit=hit, witness_length=length,
                                  independent_scalar_masks_verified=128)
                elif answer["decision"] == "unknown" and answer["lower_bound"] == 1 and answer["upper_bound"] is None and answer["witness"] is None:
                    record["outcome"] = "miss"
                else:
                    raise ValueError("Invalid miss/certificate semantics")
            except Exception as error:
                record["error"] = str(error)
            atomic_json(attempt / "attempt.json", record)
            records.append(record)
            with lock:
                observations[ordinal] = list(records); export()
                print(json.dumps({"case": ordinal, **config, "outcome": record["outcome"], "length": record.get("witness_length"), "seconds": record["invocation_seconds"]}), flush=True)
            if hit:
                break
        report = {"ordinal": ordinal, "key": case["key"], "hit": hit, "attempts": len(records),
                  "winning_configuration": records[-1]["configuration"] if hit else None}
        with lock:
            finished[ordinal] = report; export()
        return report

    export()
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures = [workers.submit(run_case, case) for case in cases]
        for future in as_completed(futures):
            future.result()
    print(json.dumps({"out": str(args.out), "target_hits": sum(row["hit"] for row in finished.values()), "cases": len(cases)}))


if __name__ == "__main__":
    main()

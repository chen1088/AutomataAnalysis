#!/usr/bin/env python3
"""Fresh two-stage, word-hint-free calibration run on all eight m7 maximizers.

Uses the existing target runner. Stage1 is deliberately cheaper; only graphs
without an independently verified34 proceed to stage2. This is a calibrated
portfolio, not a certificate that its heuristic search is globally complete.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]


def ref(path):
    path = Path(path).resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def endpoint(table, mask, word):
    state = 0
    for letter in word:
        state = table[state][int(letter) ^ ((mask >> state) & 1)]
    return state


def verify(table, words):
    assert isinstance(words, list) and len(words) == 2 and words[0] != words[1]
    assert len(words[0]) == len(words[1]) == 34 and set(words[0] + words[1]) <= {"0", "1"}
    first = [endpoint(table, mask, words[0]) for mask in range(128)]
    second = [endpoint(table, mask, words[1]) for mask in range(128)]
    assert first == second
    return {"words": words, "length": 34, "masks_independently_verified": 128,
            "first_product_state": first, "second_product_state": second}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--out", type=Path, required=True, help="New empty artifact directory.")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=180, help="Per native graph invocation, seconds.")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 32 or args.timeout < 1:
        parser.error("jobs must be1..32 and timeout positive")
    exe, output = args.exe.resolve(), args.out.resolve()
    if not exe.is_file():
        parser.error("Native executable does not exist")
    if output.exists() and any(output.iterdir()):
        parser.error("Use a new empty output directory")
    output.mkdir(parents=True, exist_ok=True)
    runner = REPO / "scripts/family1_finder_target_search.py"
    # Only constructed-grid metadata is read here. The existing target runner
    # separately whitelists graph metadata from the certified graph catalogue;
    # neither driver supplies saved word pairs or derived prefix hints.
    graph_source = REPO / "results/family1-finder-lookahead-grid-v2/runs.jsonl"
    graphs = {}
    for line in graph_source.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        ordinal, key = int(row["ordinal"]), row["key"]
        values = [int(key[i:i+2]) for i in range(0, len(key), 2)]
        graphs[ordinal] = {"ordinal": ordinal, "key": key, "m": 7, "known_H": 34,
                           "canonical_table": [values[i:i+2] for i in range(0, len(values), 2)]}
    assert len(graphs) == 8
    shutil.copy2(Path(__file__), output / "portfolio-used.py")
    shutil.copy2(runner, output / "target-runner-used.py")
    native_pin = ref(exe)
    stages = [
        {"name": "stage1-k6", "k": 6, "attempts": 1024, "prefix_pairs": 1024,
         "prefix_depth": 16, "prefix_words": 65536, "distance": 0,
         "ranking": "drop", "common": 0, "expansions": 10000},
        {"name": "stage2-k16", "k": 16, "attempts": 65536, "prefix_pairs": 65536,
         "prefix_depth": 21, "prefix_words": 2097152, "distance": 128,
         "ranking": "remaining", "common": 8, "expansions": 50000},
    ]
    manifest = {"schema": 1, "method": "calibrated-two-stage-m7-finder-portfolio-v1",
                "native_executable": native_pin, "portfolio_script": ref(output / "portfolio-used.py"),
                "target_runner": ref(output / "target-runner-used.py"), "graph_metadata_source": ref(graph_source),
                "graphs": [graphs[o] for o in sorted(graphs)], "stages": stages,
                "jobs": args.jobs, "native_timeout_seconds": args.timeout, "target_length": 34,
                "seed": 1088, "beam_width": 16, "tail_threshold": 8, "tail_max_states": 100000,
                "saved_word_or_witness_derived_prefix_hints_used": False,
                "stage2_selection": "Only graphs lacking a stage1 independently verified length34 result.",
                "scope": "Retrospective calibrated portfolio. Known H=34 comes from the separate exhaustive certificate; bounded misses give no lower bound."}
    write_json(output / "run.json", manifest)
    accepted, attempts, stage_results = {}, [], []
    started = time.perf_counter()
    for stage in stages:
        remaining = sorted(set(graphs) - set(accepted))
        if not remaining:
            break
        assert ref(exe) == native_pin, "Native executable changed during portfolio run"
        stage_dir = output / stage["name"]
        command = [sys.executable, str(runner), "--exe", str(exe), "--out", str(stage_dir),
                   "--k", str(stage["k"]), "--beam", "16", "--tail", "8", "--seeds", "1088",
                   "--cases", *map(str, remaining), "--attempts", str(stage["attempts"]),
                   "--prefix-max-pairs", str(stage["prefix_pairs"]), "--prefix-depth", str(stage["prefix_depth"]),
                   "--prefix-max-words", str(stage["prefix_words"]), "--prefix-samples-per-depth", "16384",
                   "--tail-max-states", "100000", "--max-expansions", str(stage["expansions"]),
                   "--distance-coordinates", str(stage["distance"]), "--beam-ranking", stage["ranking"],
                   "--prefix-common-depth", str(stage["common"]), "--length", "34",
                   "--jobs", str(args.jobs), "--timeout", str(args.timeout)]
        write_json(output / (stage["name"] + "-invocation.json"), {"command": command, "selected_graph_ordinals": remaining})
        stage_started = time.perf_counter()
        with (output / (stage["name"] + ".log")).open("w", encoding="utf-8") as log:
            process = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, text=True)
        for path in sorted(stage_dir.glob("case-*/attempt-*/attempt.json")):
            metadata = read_json(path)
            ordinal = int(metadata["ordinal"])
            record = {"stage": stage["name"], "ordinal": ordinal, "attempt_metadata": ref(path),
                      "outcome": "time_capped_incomplete" if metadata.get("timed_out") else metadata["outcome"],
                      "native_result": metadata.get("native_result"), "returncode": metadata.get("returncode"),
                      "invocation_seconds": metadata.get("invocation_seconds")}
            native_path = path.parent / "native/result.json"
            if metadata.get("hit"):
                native = read_json(native_path)
                assert native["decision"] == "collision" and native["upper_bound"] == 34
                assert native["key"] == graphs[ordinal]["key"]
                checksum = ref(native_path)
                assert checksum["sha256"] == metadata["native_result"]["sha256"]
                verified = verify(graphs[ordinal]["canonical_table"], native["witness"])
                accepted[ordinal] = {"ordinal": ordinal, "key": graphs[ordinal]["key"], "stage": stage["name"],
                                     "known_H": 34, "globally_shortest_using_prior_H_certificate": True,
                                     "native_result": checksum, "native_configuration": ref(native_path.with_name("run.json")),
                                     "native_executable": ref(stage_dir / "Family1Sample-used.exe"),
                                     "attempt_metadata": ref(path), **verified}
                record["independent_scalar_masks_verified"] = 128
            attempts.append(record)
        stage_summary = read_json(stage_dir / "summary.json") if (stage_dir / "summary.json").is_file() else None
        stage_results.append({"stage": stage["name"], "selected_graph_ordinals": remaining,
                              "returncode": process.returncode, "whole_stage_seconds": time.perf_counter()-stage_started,
                              "summary": stage_summary, "summary_reference": ref(stage_dir / "summary.json") if stage_summary else None})
        print(json.dumps({"stage": stage["name"], "verified_total": len(accepted), "remaining": sorted(set(graphs)-set(accepted))}), flush=True)
        write_json(output / "partial.json", {"verified_graph_ordinals": sorted(accepted), "stages": stage_results, "attempts": attempts})
    summary = {"schema": 1, "method": manifest["method"], "run": ref(output / "run.json"),
               "graph_count": 8, "verified_length34_graph_ordinals": sorted(accepted),
               "all_eight_verified": len(accepted)==8, "missing_graph_ordinals": sorted(set(graphs)-set(accepted)),
               "total_native_attempts": len(attempts), "outcomes": dict(Counter(r["outcome"] for r in attempts)),
               "whole_portfolio_seconds": time.perf_counter()-started, "stages": stage_results,
               "no_saved_word_hints": True, "misses_give_no_lower_bound": True,
               "known_H_from_separate_certificate": True}
    write_json(output / "summary.json", summary)
    write_json(output / "attempt-inventory.json", attempts)
    (output / "verified-pairs.jsonl").write_text("".join(json.dumps(accepted[o], separators=(",", ":"))+"\n" for o in sorted(accepted)), encoding="utf-8")
    lines = ["# Calibrated two-stage seven-state finder", "",
             f"Fresh run: {len(accepted)}/8 independently verified length-34 pairs, {len(attempts)} native invocations, {summary['whole_portfolio_seconds']:.3f} seconds wall time. Each accepted pair was independently replayed over all128 static masks. Both endpoint vectors, source hashes and complete raw stage outputs are retained.", "",
             "Stage1 uses k6, beam16, tail threshold8,1024 outer attempts/prefix pairs, prefix depth16/65536 words per layer,10000 expansions, drop ranking and no distance/common-prefix option. Only its nonhits proceed to stage2: k16, beam16, tail8,65536 attempts/pairs, prefix depth21/2097152 words per layer, common-prefix depth8,128 distance coordinates, remaining-count ranking and50000 expansions. Both stages use length cap34 and seed1088, without saved word hints.", "",
             "This is a retrospective calibrated portfolio, not a uniform single-window configuration or a globally complete shortest-pair algorithm. The recovered34 pairs are shortest because the separate exhaustive certificate gives H=34. A miss or timeout provides no lower bound. Stage2 selection depends only on verified stage1 hits, not graph identity or saved witness strings.", "",
             "Reproduce with a fresh output directory:", "", "```powershell",
             "uv run --no-project python scripts/family1_finder_calibrated_portfolio.py --exe out/build/msvc-vcpkg/Release/Family1Sample.exe --out out/family1-calibrated-portfolio-repeat --jobs 4 --timeout 180", "```", ""]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if len(accepted)==8 else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Blind automatic-seed finder benchmark against known exact fixed-graph H.

All20 certified maximizing rooted classes m1..7 are retained, followed by four
separately labeled circulants m7/8. No saved witness or prefix is passed to
the native finder. Known H is used only to report quality and set a common cap.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time

REPO = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def graph_key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def endpoint(table, mask, word):
    state = 0
    for letter in word:
        state = table[state][int(letter) ^ ((mask >> state) & 1)]
    return state


def reference(path):
    path = Path(path)
    try:
        name = path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        name = str(path.resolve())
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_cases():
    cases = []
    sources = []
    for filename in ("results/family1-m1-m6/maximizers.jsonl", "results/family1-m7/maximizers.jsonl"):
        path = REPO / filename
        sources.append(reference(path))
        for record in read_jsonl(path):
            assert record["status"] == "exact"
            cases.append({"label": f"max-m{record['m']}-{record['ordinal']}", "kind": "certified-maximizer",
                          "m": record["m"], "key": graph_key(record["canonical_table"]),
                          "canonical_table": record["canonical_table"], "H": record["merge_length"]})
    assert len(cases) == 20
    for variant, filename in (("literal", "results/family1-circulant-family/champions.jsonl"),
                              ("manuscript-reference", "results/family1-circulant-manuscript-reference/champions.jsonl")):
        path = REPO / filename
        sources.append(reference(path))
        for record in read_jsonl(path):
            if record["m"] not in (7, 8):
                continue
            assert record["status"] == "exact"
            cases.append({"label": f"{variant}-m{record['m']}", "kind": variant,
                          "m": record["m"], "key": record["key"], "canonical_table": record["canonical_table"], "H": record["merge_length"]})
    assert len(cases) == 24 and len({(case["m"], case["key"]) for case in cases}) == 24
    return cases, sources


def run_case(args, case, threshold):
    name = "window-only" if threshold == 0 else f"tail-{threshold}"
    output = args.work_dir / case["label"] / name
    maximum = 2 * case["H"] + 8
    command = [str(args.exe), "--graph", case["key"], "--out", str(output), "--mode", "finder",
               "--length", str(maximum), "--samples", str(args.seeds), "--seed", str(args.seed),
               "--window-k", str(args.window_k), "--beam-width", str(args.beam_width),
               "--tail-threshold", str(threshold), "--tail-max-states", str(args.tail_max_states),
               "--best-of-seeds"]
    if (output / "run.json").exists():
        command.append("--resume")
    started = time.perf_counter()
    completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(f"finder failed {case['label']} {name}: {completed.stdout}\n{completed.stderr}")
    result = json.loads(completed.stdout)
    result_bytes = (output / "result.json").read_bytes()
    assert json.loads(result_bytes) == result
    assert (output / "result.sha256").read_text().strip() == hashlib.sha256(result_bytes).hexdigest()
    assert result["canonical_table"] == case["canonical_table"]
    assert result["lower_bound"] == 1
    found = result["decision"] == "collision"
    length = result["upper_bound"] if found else None
    if found:
        first, second = result["witness"]
        assert first != second and len(first) == len(second) == length <= maximum
        assert case["H"] <= length
        assert all(endpoint(case["canonical_table"], mask, first) == endpoint(case["canonical_table"], mask, second)
                   for mask in range(1 << case["m"]))
    else:
        assert result["decision"] == "unknown" and result["upper_bound"] is None and result["witness"] is None
    module = result.get("module_stats", {})
    tail = result.get("exact_tail", module.get("last_tail", {}))
    return {"case": case["label"], "kind": case["kind"], "m": case["m"], "key": case["key"],
            "H": case["H"], "found_length": length, "gap": length - case["H"] if found else None,
            "ratio": length / case["H"] if found else None, "miss": not found,
            "maximum_pair_length": maximum, "automatic_seed_budget": args.seeds,
            "samples_completed": result["samples_completed"], "tail_threshold": threshold,
            "window_k": args.window_k, "beam_width": args.beam_width,
            "whole_invocation_seconds": elapsed, "native_seconds": result.get("seconds"),
            "module_stats": module, "exact_tail": tail,
            "tail_calls": module.get("tail_calls", 0), "tail_states": module.get("tail_states", 0),
            "exact_tail_status": tail.get("status") if tail else None,
            "exact_tail_depth": tail.get("depth") if tail else None,
            "exact_tail_shortest_conditional": tail.get("shortest_conditional", False) if tail else False,
            "reused_completed_result": "--resume" in command,
            "witness": result["witness"], "native_result": reference(output / "result.json"),
            "native_command": command,
            "exact_tail_caution": "A shortest common suffix is conditional on its starting pair; it does not certify globally shortest word-pair length."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=REPO / "results/family1-finder-blind-benchmark")
    parser.add_argument("--work-dir", type=Path, default=REPO / "out/family1-finder-blind-benchmark")
    parser.add_argument("--seeds", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1088)
    parser.add_argument("--window-k", type=int, default=2)
    parser.add_argument("--beam-width", type=int, default=4)
    parser.add_argument("--tail-threshold", type=int, default=2)
    parser.add_argument("--tail-grid", type=int, nargs="+", default=[0, 2, 8],
                        help="Predeclared engineering grid, evaluated for every graph; default0,2,8.")
    parser.add_argument("--tail-max-states", type=int, default=100000)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--case", action="append", help="Restrict to an exact case label for a smoke test.")
    parser.add_argument("--no-window-only", action="store_true")
    args = parser.parse_args()
    args.exe = args.exe.resolve()
    assert args.exe.is_file()
    assert args.tail_threshold in args.tail_grid and all(0 <= value <= 1024 for value in args.tail_grid)
    executable_before = reference(args.exe)
    cases, sources = load_cases()
    if args.case:
        wanted = set(args.case)
        assert wanted <= {case["label"] for case in cases}
        cases = [case for case in cases if case["label"] in wanted]
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in cases:
        thresholds = sorted(set(args.tail_grid) - ({0} if args.no_window_only else set()))
        for threshold in thresholds:
            row = run_case(args, case, threshold)
            rows.append(row)
            print(json.dumps({"case": row["case"], "tail_threshold": threshold, "H": row["H"],
                              "found": row["found_length"], "gap": row["gap"], "seconds": row["native_seconds"]}), flush=True)
            # Publish a complete per-run audit row as soon as it is available.
            (args.output / "runs.jsonl").write_text("".join(json.dumps(item, separators=(",", ":")) + "\n" for item in rows), encoding="utf-8")
    summary = {"schema": 1, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "cases": len(cases), "runs": len(rows), "automatic_seed_budget": args.seeds,
               "witness_derived_prefix_hints_used": False, "maximum_pair_length_rule": "2*known_H+8",
               "source_scores": sources, "native_executable": executable_before, "driver": reference(Path(__file__)),
               "all_accepted_pairs_all_static_masks_independently_replayed": True,
               "configuration": {"window_k": args.window_k, "beam_width": args.beam_width,
                                 "tail_threshold": args.tail_threshold, "tail_max_states": args.tail_max_states},
               "comparisons": [], "global_shortestness_claimed": False}
    assert reference(args.exe) == executable_before, "native executable changed during the benchmark"
    summary["configuration"]["predeclared_tail_grid"] = sorted(set(args.tail_grid))
    for case in cases:
        current = {row["tail_threshold"]: row for row in rows if row["case"] == case["label"]}
        tail = current[args.tail_threshold]
        baseline = current.get(0)
        summary["comparisons"].append({"case": case["label"], "m": case["m"], "H": case["H"],
                                        "window_only_length": baseline["found_length"] if baseline else None,
                                        "tail_length": tail["found_length"], "gap": tail["gap"], "ratio": tail["ratio"],
                                        "all_settings": {str(threshold): {name: row[name] for name in
                                                                          ("found_length", "gap", "ratio", "miss", "tail_calls", "tail_states", "native_seconds", "exact_tail_status", "exact_tail_shortest_conditional")}
                                                         for threshold, row in sorted(current.items())},
                                        "tail_beats_window_only": bool(baseline and not tail["miss"] and
                                                                      (baseline["miss"] or tail["found_length"] < baseline["found_length"]))})
    for threshold in sorted({row["tail_threshold"] for row in rows}):
        subset = [row for row in rows if row["tail_threshold"] == threshold]
        ratios = [row["ratio"] for row in subset if row["ratio"] is not None]
        summary.setdefault("aggregate", []).append({"tail_threshold": threshold, "runs": len(subset),
                                                    "hits": len(ratios), "misses": len(subset) - len(ratios),
                                                    "exact_H_hits": sum(row["gap"] == 0 for row in subset),
                                                    "mean_hit_ratio": statistics.fmean(ratios) if ratios else None,
                                                    "max_hit_ratio": max(ratios) if ratios else None,
                                                    "native_seconds": sum(row["native_seconds"] or 0 for row in subset)})
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    columns = ["case", "kind", "m", "H", "tail_threshold", "found_length", "gap", "ratio", "miss",
               "samples_completed", "tail_calls", "tail_states", "exact_tail_status", "exact_tail_depth",
               "exact_tail_shortest_conditional", "native_seconds", "whole_invocation_seconds"]
    with (args.output / "runs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    lines = ["# Blind automatic-seed finder benchmark", "",
             "All20 certified maximizing rooted classes through size7 and four separately labeled circulants are included in the full run. Saved witnesses and witness-derived prefixes are never passed to the finder. The known exact H supplies the reporting baseline and the common pair-length cap 2H+8.", "",
             "The predeclared threshold grid is 0,2,8 for every graph, with the same128 automatic-seed budget, k=2, beam4, and tail-state cap100,000. All settings are reported; the table does not select only a favorable setting.", "",
             "| Graph | H | T=0 L | T=2 L | T=8 L |",
             "|---|---:|---:|---:|---:|"]
    for item in summary["comparisons"]:
        lengths = [item["all_settings"].get(str(value), {}).get("found_length") for value in (0, 2, 8)]
        lines.append(f"| {item['case']} | {item['H']} | " + " | ".join(str(value) if value is not None else "miss" for value in lengths) + " |")
    lines.extend(["", "Each accepted pair is independently replayed over every static mask. `runs.jsonl` and `runs.csv` retain every setting's gap, ratio, runtime, module statistics, exact-tail status/state counts, native result hashes, and commands. A tail BFS proves a shortest common suffix from its particular starting pair only. It does not prove that the resulting whole word pair is globally shortest, or that all shortest pairs were collected. Misses retain no new score bound.", ""])
    (args.output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"completed_cases": len(cases), "runs": len(rows), "aggregate": summary.get("aggregate")}))


if __name__ == "__main__":
    main()

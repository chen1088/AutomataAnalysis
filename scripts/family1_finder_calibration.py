#!/usr/bin/env python3
"""Aggregate controlled grids and adaptive target34 runs; replay every new34.

This script does not read the original saved-witness/maximizer dataset.
Graph keys and newly constructed words come only from finder outputs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTROLLED = ["family1-finder-lookahead-grid-v1", "family1-finder-lookahead-grid-v2",
              "family1-finder-target34-k6-w16"]


def ref(path):
    path = Path(path).resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest_value(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def table(key):
    values = [int(key[i:i + 2]) for i in range(0, len(key), 2)]
    assert len(values) == 14 and all(0 <= x < 7 for x in values)
    return [values[i:i + 2] for i in range(0, len(values), 2)]


def endpoint(tau, mask, word):
    state = 0
    for letter in word:
        state = tau[state][int(letter) ^ ((mask >> state) & 1)]
    return state


def verify_pair(tau, native):
    first, second = native["witness"]
    assert first != second and len(first) == len(second) == 34
    assert set(first + second) <= {"0", "1"}
    a = [endpoint(tau, mask, first) for mask in range(128)]
    b = [endpoint(tau, mask, second) for mask in range(128)]
    assert a == b
    attempt = native.get("guided_attempt", {})
    trace_audit = None
    if attempt.get("initial_words") and attempt.get("score_scope") == "full":
        initial = attempt["initial_words"]
        suffix = attempt["suffix"]
        assert initial[0] + suffix == first and initial[1] + suffix == second
        p = [endpoint(tau, mask, initial[0]) for mask in range(128)]
        q = [endpoint(tau, mask, initial[1]) for mask in range(128)]
        scores = [sum(x == y for x, y in zip(p, q))]
        for letter in suffix:
            bit = int(letter)
            p = [tau[state][bit ^ ((mask >> state) & 1)] for mask, state in enumerate(p)]
            q = [tau[state][bit ^ ((mask >> state) & 1)] for mask, state in enumerate(q)]
            scores.append(sum(x == y for x, y in zip(p, q)))
        assert scores == attempt["score_trace"]
        assert all(x <= y for x, y in zip(scores, scores[1:]))
        trace_audit = {"initial_words": initial, "suffix": suffix, "score_trace": scores,
                       "total_masks": 128, "full_trace_matches_native": True}
    return {"words": [first, second], "length": 34, "masks_independently_verified": 128,
            "first_product_state": a, "second_product_state": b, "full_score_trace_audit": trace_audit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/family1-finder-calibration")
    args = parser.parse_args()
    output = REPO / args.output
    output.mkdir(parents=True, exist_ok=True)
    records, graphs, inputs = {}, {}, []

    def add(native_path, ordinal, key, batch, source, command, metadata=None, expected=None):
        path = Path(native_path)
        if not path.is_absolute():
            path = REPO / path
        row = {"source_batch": batch, "ordinal": int(ordinal), "key": key,
               "known_H": 34, "source": source, "command": command}
        assert ordinal not in graphs or graphs[ordinal]["key"] == key
        graphs[int(ordinal)] = {"ordinal": int(ordinal), "key": key, "m": 7,
                                "canonical_table": table(key), "known_H": 34}
        if metadata is not None:
            row["attempt_metadata"] = metadata
            row["invocation_seconds"] = metadata.get("invocation_seconds")
        config_path = path.with_name("run.json")
        config = read(config_path) if config_path.is_file() else None
        exe_path = Path(command[0]) if command else None
        executable = ref(exe_path) if exe_path and exe_path.is_file() else None
        if config is not None:
            row.update({"native_configuration": config, "native_configuration_file": ref(config_path),
                        "executable": executable, "window_k": config["window_k"],
                        "beam_width": config["beam_width"], "tail_threshold": config["tail_threshold"],
                        "length_cap": config["length"], "requested_samples": config["samples"],
                        "prefix_max_pairs": config["prefix_max_pairs"]})
            settings = {k: v for k, v in config.items() if k not in {"source_key", "source_key_sha256", "key", "m"}}
            row["configuration_signature"] = digest_value({"settings": settings,
                                                           "executable_sha256": executable["sha256"] if executable else None})
        if not path.is_file():
            row["native_result"] = None
            if (metadata or {}).get("timed_out"):
                row["outcome"] = "time_capped_incomplete"
                row["caps"] = {"time_capped": True}
            elif (metadata or {}).get("returncode", 0):
                row["outcome"] = "process_error"
            else:
                row["outcome"] = "no_completed_native_result"
            row["native_result_data"] = None
            records[source["path"]] = row
            return
        native_ref = ref(path)
        if expected is not None:
            assert native_ref["sha256"] == expected
        native = read(path)
        assert native["key"] == key and native["m"] == 7
        assert config is not None
        row.update({"native_result": native_ref, "native_result_data": native})
        found = native.get("upper_bound") if native.get("decision") == "collision" else None
        if found is not None:
            assert native.get("witness") and found >= 34
        row["found_length"] = found
        row["gap"] = found - 34 if found is not None else None
        row["outcome"] = "minimum34" if found == 34 else ("near_collision" if found else "unknown")
        row["window_k"] = config["window_k"]
        row["beam_width"] = config["beam_width"]
        row["tail_threshold"] = config["tail_threshold"]
        row["length_cap"] = config["length"]
        row["requested_samples"] = config["samples"]
        row["prefix_max_pairs"] = config["prefix_max_pairs"]
        row["native_seconds"] = native.get("seconds")
        row["caps"] = {
            "time_capped": False,
            "expansion_limit_events": native.get("module_stats", {}).get("expansion_limits_reached", 0),
            "exact_tail_capped": bool((native.get("exact_tail") or {}).get("capped", False)),
            "prefix_depth_capped": bool(native.get("prefix_seed_stats", {}).get("depth_capped", False)),
            "prefix_word_capped": bool(native.get("prefix_seed_stats", {}).get("word_capped", False)),
            "prefix_pair_capped": bool(native.get("prefix_seed_stats", {}).get("pair_capped", False)),
        }
        if found == 34:
            row["independent_scalar_verification"] = verify_pair(graphs[int(ordinal)]["canonical_table"], native)
        records[native_ref["path"]] = row

    for name in CONTROLLED:
        path = REPO / "results" / name / "runs.jsonl"
        container = ref(path)
        inputs.append(container)
        binding = path.with_name("binding.json")
        if binding.is_file():
            inputs.append(ref(binding))
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            native = row["native_result"]
            add(native["path"], row["ordinal"], row["key"], name,
                {**container, "run_id": row["run_id"]}, row["command"], expected=native["sha256"])
    target_roots = [root for root in (REPO / "out").glob("family1-target34*") if root.is_dir()]
    portfolio_root = REPO / "out/family1-finder-calibrated-portfolio"
    if portfolio_root.is_dir():
        target_roots.extend(root for root in portfolio_root.glob("stage*") if root.is_dir())
        if (portfolio_root / "run.json").is_file():
            inputs.append(ref(portfolio_root / "run.json"))
    for root in sorted(target_roots):
        if not root.is_dir():
            continue
        manifest = root / "run.json"
        if manifest.is_file():
            inputs.append(ref(manifest))
        for path in sorted(root.glob("case-*/attempt-*/attempt.json")):
            attempt = read(path)
            expected = attempt.get("native_result", {}).get("sha256")
            metadata = {k: v for k, v in attempt.items() if k != "native_answer"}
            add(path.parent / "native" / "result.json", attempt["ordinal"], attempt["key"],
                root.relative_to(REPO / "out").as_posix(), ref(path), attempt.get("command"), metadata, expected)

    rows = sorted(records.values(), key=lambda r: (r["source_batch"], r["ordinal"], r["source"]["path"]))
    assert len(graphs) == 8
    hits = [r for r in rows if r["outcome"] == "minimum34"]
    successful = {}
    for ordinal in sorted(graphs):
        candidates = [r for r in hits if r["ordinal"] == ordinal]
        if candidates:
            successful[ordinal] = min(candidates, key=lambda r: (r["window_k"], r["requested_samples"],
                                                                 r["native_seconds"], r["native_result"]["path"]))
    groups = []
    by_signature = defaultdict(list)
    for row in rows:
        if row.get("configuration_signature"):
            by_signature[row["configuration_signature"]].append(row)
    for signature, members in sorted(by_signature.items()):
        covered = sorted({r["ordinal"] for r in members if r["outcome"] == "minimum34"})
        groups.append({"signature": signature, "case_count": len(members),
                       "tested_graph_ordinals": sorted({r["ordinal"] for r in members}),
                       "minimum34_graph_ordinals": covered,
                       "uniform_all_eight_recovered": len(covered) == 8,
                       "native_configuration_example": members[0]["native_configuration"],
                       "executable": members[0]["executable"],
                       "native_results": [r["native_result"] for r in members]})
    batches = []
    for batch in sorted({r["source_batch"] for r in rows}):
        subset = [r for r in rows if r["source_batch"] == batch]
        batches.append({"batch": batch, "cases": len(subset), "outcomes": dict(Counter(r["outcome"] for r in subset)),
                        "minimum34_graph_ordinals": sorted({r["ordinal"] for r in subset if r["outcome"] == "minimum34"}),
                        "expansion_capped_cases": sum(bool(r.get("caps", {}).get("expansion_limit_events")) for r in subset),
                        "exact_tail_capped_cases": sum(r.get("caps", {}).get("exact_tail_capped", False) for r in subset),
                        "time_capped_incomplete_cases": sum(r["outcome"] == "time_capped_incomplete" for r in subset),
                        "native_seconds_total": sum(r.get("native_seconds") or 0 for r in subset)})
    summary = {"schema": 1, "method": "finder-calibration-constructed-pair-aggregation",
               "script": ref(Path(__file__)), "input_containers": inputs,
               "original_saved_witness_files_read": False, "known_H": 34,
               "known_H_source": "Existing exhaustive m7 global certificate; no lower-bound inference from these heuristic runs.",
               "case_count": len(rows), "graph_count": len(graphs),
               "outcomes": dict(Counter(r["outcome"] for r in rows)),
               "independently_verified_minimum34_native_results": len(hits),
               "independent_mask_coordinate_verifications": len(hits) * 128,
               "direct_minimum34_graph_ordinals": sorted(successful),
               "all_eight_directly_rediscovered": len(successful) == 8,
               "uniform_configuration_signatures_recovering_all_eight": [g["signature"] for g in groups if g["uniform_all_eight_recovered"]],
               "smallest_tested_successful_k_is_not_necessary_k_proof": True,
               "controlled_and_adaptive_runs_are_separate": True, "batches": batches}
    portfolio_summary_path = portfolio_root / "summary.json"
    if portfolio_summary_path.is_file():
        portfolio = read(portfolio_summary_path)
        summary["fresh_calibrated_portfolio"] = {
            "summary": ref(portfolio_summary_path), "all_eight_verified": portfolio["all_eight_verified"],
            "native_attempts": portfolio["total_native_attempts"],
            "whole_portfolio_seconds": portfolio["whole_portfolio_seconds"],
            "distinct_from_uniform_single_configuration": True,
        }

    def json_out(name, value):
        (output / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def jsonl_out(name, values):
        (output / name).write_text("".join(json.dumps(value, separators=(",", ":")) + "\n" for value in values), encoding="utf-8")

    json_out("summary.json", summary)
    json_out("configuration-groups.json", groups)
    jsonl_out("cases.jsonl", rows)
    jsonl_out("graphs.jsonl", [graphs[o] for o in sorted(graphs)])
    jsonl_out("smallest-tested-successful-k.jsonl", [successful[o] for o in sorted(successful)])
    jsonl_out("verified-minimum34.jsonl", [
        {"ordinal": r["ordinal"], "key": r["key"], "source_batch": r["source_batch"],
         "native_result": r["native_result"], "executable": r["executable"],
         "native_configuration_file": r["native_configuration_file"],
         "configuration_signature": r["configuration_signature"],
         **r["independent_scalar_verification"]} for r in hits])
    csv_fields = ["source_batch", "ordinal", "window_k", "beam_width", "tail_threshold",
                  "length_cap", "requested_samples", "prefix_max_pairs", "outcome",
                  "found_length", "gap", "native_seconds", "configuration_signature"]
    with (output / "cases.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in csv_fields})
    lines = ["# Seven-state finder calibration", "",
             f"The direct finder outputs rediscover length34 on **{len(successful)} of all eight** certified maximizing seven-state rooted graph classes. Every one of the {len(hits)} collected length-34 native results was independently replayed by this script over all128 static masks; both full endpoint vectors and full agreement traces are retained. No original saved optimal witness file is read.", "",
             "These recovered pairs are globally shortest because the earlier exhaustive graph scoring already certified H=34. A heuristic hit alone supplies an upper bound; a failed bounded run supplies no new graph lower bound. Conditional suffix BFS supplies its stated conditional shortestness only.", "",
             "| Ordinal | Smallest tested successful k | Beam | Tail threshold | Prefix pairs / outer attempts | Prefix depth / words per layer | Distance coordinates | Common-prefix depth | Native seconds | Native / executable SHA prefixes | Source batch |",
             "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for ordinal in sorted(graphs):
        if ordinal not in successful:
            lines.append(f"| {ordinal} | not found | | | | | | | | | |")
            continue
        r = successful[ordinal]
        c = r["native_configuration"]
        lines.append(f"| {ordinal} | {r['window_k']} | {r['beam_width']} | {r['tail_threshold']} | {c['prefix_max_pairs']} / {c['samples']} | {c['prefix_depth']} / {c['prefix_max_words']} | {c.get('distance_coordinates', 0)} | {c.get('prefix_common_depth', 0)} | {r['native_seconds']:.3f} | {r['native_result']['sha256'][:12]} / {r['executable']['sha256'][:12]} | {r['source_batch']} |")
    lines += ["", "The table uses SHA-256 prefixes for readability; `smallest-tested-successful-k.jsonl` contains the complete hashes, exact commands, complete native settings and witness provenance. The smallest successful tested k is tied to the complete configuration shown and is not a proof that smaller k cannot work. The controlled v1 and v2 grids keep their own fixed settings; the adaptive recovery runs also increase prefix coverage, seed budget, common-prefix diversity and/or distance pruning. Their outcomes must not be attributed to k alone. This is retrospective calibration on known seven-state maximizers, not a held-out estimate of success on other graphs or state sizes.", "",
             "| Batch | Cases | Length34 results | Longer collisions | Unknown / other incomplete | Time capped incomplete | Distinct graph classes with34 | Native seconds |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for batch in batches:
        counts = batch["outcomes"]
        lines.append(f"| {batch['batch']} | {batch['cases']} | {counts.get('minimum34', 0)} | {counts.get('near_collision', 0)} | {counts.get('unknown', 0) + counts.get('no_completed_native_result', 0) + counts.get('process_error', 0)} | {counts.get('time_capped_incomplete', 0)} | {len(batch['minimum34_graph_ordinals'])} | {batch['native_seconds_total']:.3f} |")
    uniform = summary["uniform_configuration_signatures_recovering_all_eight"]
    lines += ["", ("At least one identical executable and complete nongraph native configuration recovered34 on all eight graph classes. Its full configuration and all source hashes are listed in `configuration-groups.json`." if uniform else "No single complete configuration has yet been observed recovering34 on all eight classes in this snapshot. Direct union coverage across configurations must be distinguished from uniform-configuration coverage."), "",
              "`cases.jsonl` preserves every completed controlled/adaptive native answer, its complete run configuration, all cap fields, and hashes of native output, native configuration, executable, and container/attempt metadata. Process attempts without a completed native result are retained separately. A timed-out invocation is `time_capped_incomplete`, with its wall time and configuration retained; it is not an algorithmic failure or a graph lower-bound certificate. Native-seconds totals sum completed native answers and exclude timed-out wall time. Prefix/depth/pair caps and exact-tail caps remain explicit; none is promoted to an exhaustive graph score.", "",
              "`verified-minimum34.jsonl` retains each independently replayed pair, both complete128-state vectors and scalar common-suffix score traces. `smallest-tested-successful-k.jsonl` contains the fully provenanced selected table rows. `configuration-groups.json` groups only identical executable hashes and complete nongraph run settings. `summary.json` lists whole-experiment counts and input hashes. No transfer/subsequence reduction result is counted as a direct finder hit.", "",
              "Rebuild this aggregate after additional completed target attempts:", "", "```powershell",
              "uv run --no-project python scripts/family1_finder_calibration.py", "```", ""]
    if summary.get("fresh_calibrated_portfolio", {}).get("all_eight_verified"):
        detail = summary["fresh_calibrated_portfolio"]
        lines[2:2] = [
            f"A **single fresh automatic two-stage portfolio recovered34 on all eight** in {detail['native_attempts']} native invocations and {detail['whole_portfolio_seconds']:.3f} seconds wall time. Stage1 runs k6 on all eight; only its five nonhits proceed to the fixed k16 second stage. Selection uses verified hits, not graph identity or saved word pairs. This is a calibrated portfolio, distinct from one uniform k16 configuration. Both uniform k16 experiments recovered seven classes and timed out on ordinal539749 after180 seconds.", "",
            "The fresh portfolio is published in [the compact report and full raw-evidence archive](../family1-finder-calibrated-portfolio/README.md). Its thirteen stage cases are included below and every new length34 pair is replayed again by this aggregate.", "",
        ]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["case_count", "outcomes", "direct_minimum34_graph_ordinals", "all_eight_directly_rediscovered", "uniform_configuration_signatures_recovering_all_eight"]}, indent=2))


if __name__ == "__main__":
    main()

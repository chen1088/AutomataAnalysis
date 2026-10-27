#!/usr/bin/env python3
"""Audit completed full-joint campaigns and report every supplied candidate.

New witnesses are chosen only from the supplied joint campaigns. Optional
historical bounds are compared separately and never become new search hits.
All lookahead spans count joint steps over 00,01,10,11, with 4**span leaves.
Inputs must be immutable completed campaigns; cached hashes are local to this
report process. This program launches no search and uses no randomness.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from functools import lru_cache
import hashlib
import json
from pathlib import Path


ALPHABET = ["00", "01", "10", "11"]
CAP_FIELDS = ("expansion_limit_reached", "length_limit_reached", "beam_truncated",
              "capped", "interrupted", "prefix_pair_capped", "prefix_word_capped")


def require(condition, message):
    if not condition:
        raise ValueError(message)


@lru_cache(maxsize=None)
def digest(path):
    """Cache hashes only for finalized immutable report inputs."""
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def reference(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def checked_table(row):
    table = row.get("canonical_table")
    require(isinstance(table, list) and 1 <= len(table) <= 20, "invalid graph table")
    m = len(table)
    require(row.get("m", m) == m, "graph size/table mismatch")
    require(all(isinstance(ports, list) and len(ports) == 2
                and all(type(target) is int and 0 <= target < m for target in ports)
                for ports in table), "invalid graph transitions")
    key = "".join(f"{target:02d}" for ports in table for target in ports)
    require(row.get("key") == key, "graph key/table mismatch")
    reached, pending = {0}, [0]
    while pending:
        for target in table[pending.pop()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    require(len(reached) == m, f"graph is not root-accessible: {key}")
    return table


def checked_pair(row):
    pair, upper = row.get("witness"), row.get("upper_bound")
    if pair is None:
        require(upper is None and row["status"] == "unresolved", "unknown result has a numeric bound")
        require(row["static_masks_verified"] == 0, "unknown result claims positive replay")
        return None
    require(type(upper) is int and 1 <= upper <= row["max_length"], "invalid new upper length")
    require(isinstance(pair, list) and len(pair) == 2
            and all(isinstance(word, str) and word and not (set(word) - {"0", "1"}) for word in pair)
            and pair[0] != pair[1] and len(pair[0]) == len(pair[1]) == upper,
            "invalid distinct equal-length binary witness")
    require(row["status"] == "verified-upper" and row["static_masks_verified"] == 1 << row["m"],
            "new witness lacks complete static-mask replay metadata")
    return tuple(sorted(pair))


def scalar_replay(table, pair):
    """Replay every original static mask independently of native bit planes."""
    first, second = pair[0].encode(), pair[1].encode()
    for mask in range(1 << len(table)):
        left = right = 0
        for a, b in zip(first, second):
            left = table[left][(a - 48) ^ ((mask >> left) & 1)]
            right = table[right][(b - 48) ^ ((mask >> right) & 1)]
        require(left == right, f"scalar positive replay failed on mask {mask}")
    return 1 << len(table)


def parameters(campaign):
    return {"m": campaign["m"], "k": campaign["k"], "B": campaign["beam"],
            "D": campaign["diagonal_beam"], "U": campaign.get("unequal_beam", 0),
            "P": campaign.get("prefix_pairs", 0), "max_length": campaign["max_length"],
            "expansions": campaign["expansions"], "target_upper": campaign.get("target_upper", 0)}


def check_parameters(record, campaign, native=False):
    wanted = parameters(campaign)
    require(record["m"] == wanted["m"] and record["k"] == wanted["k"], "joint m/k metadata mismatch")
    require(record["alphabet"] == ALPHABET and record["deterministic"] is True,
            "run is not deterministic full-four-symbol joint search")
    for field, expected in (("beam_width", wanted["B"]), ("diagonal_width", wanted["D"]),
                            ("unequal_width", wanted["U"]), ("prefix_pairs", wanted["P"]),
                            ("target_upper", wanted["target_upper"])):
        require(record.get(field, 0) == expected, f"joint parameter mismatch: {field}")
    require(record["max_length"] == wanted["max_length"], "maximum length mismatch")
    require(record["max_expansions" if native else "expansion_cap"] == wanted["expansions"],
            "expansion budget mismatch")
    if wanted["P"]:
        for field in ("prefix_depth", "prefix_words", "common_prefix_depth"):
            require(record[field] == campaign[field], f"joint prefix parameter mismatch: {field}")
        if native:
            require("no sampling" in record["prefix_selection"] and "graph-only" in record["prefix_selection"],
                    "prefix selection does not state graph-only deterministic enumeration")


def validate_windows(row):
    require(row["partial_windows"] == 0, "joint run contains a partial window")
    reports = row["window_reports"]
    truncated = row.get("window_reports_truncated", 0)
    require(type(truncated) is int and truncated >= 0, "invalid report truncation count")
    require(len(reports) + truncated == row["complete_windows"], "window reports/counts disagree")
    nodes = leaves = 0
    for report in reports:
        span = report["span"]
        require(type(span) is int and 1 <= span <= row["k"], "invalid joint-window span")
        require(report["complete"] is True, "retained joint window is incomplete")
        require(report["leaves"] == report["expected_leaves"] == 4 ** span,
                "joint window does not contain all 4**span leaves")
        require(report["nodes"] == (4 ** (span + 1) - 4) // 3,
                "joint-window node count is not the full four-ary tree")
        if "attempt" in report:
            require(1 <= report["attempt"] <= row.get("attempts", 1), "window attempt ID is invalid")
        nodes += report["nodes"]
        leaves += report["leaves"]
    require(nodes <= row["expanded_nodes"] and leaves <= row["visited_leaves"], "retained totals exceed run counters")
    if not truncated:
        require(nodes == row["expanded_nodes"] and leaves == row["visited_leaves"], "complete report totals disagree")
    # This identity holds for sums of complete four-ary windows of ANY spans,
    # so aggregate counters remain independently checked when reports truncate.
    require(3 * row["expanded_nodes"] == 4 * (row["visited_leaves"] - row["complete_windows"]),
            "aggregate counters do not describe complete four-ary windows")
    attempts = row.get("attempts", 1)
    require(type(attempts) is int and attempts >= 1 and row.get("empty_root_attempts", 1) == 1,
            "joint search lacks its mandatory empty-root attempt")
    require(attempts == 1 + row.get("prefix_attempts", 0), "joint attempt accounting disagrees")
    require(row["expanded_nodes"] <= attempts * row["expansion_cap"], "per-attempt expansion caps were exceeded")
    for field in CAP_FIELDS:
        if field in row:
            require(type(row[field]) is bool, f"invalid cap flag: {field}")
    for count, flag in (("expansion_capped_attempts", "expansion_limit_reached"),
                        ("length_capped_attempts", "length_limit_reached")):
        if count in row:
            require(0 <= row[count] <= attempts and bool(row[count]) == row[flag], "cap counts/flags disagree")
    if "capped" in row:
        require(row["capped"] == (row["expansion_limit_reached"] or row["length_limit_reached"]
                                  or row.get("interrupted", False)), "aggregate cap flag disagrees")


def audit_run(directory, candidates, run_index):
    campaign_path, records_path = directory / "campaign.json", directory / "records.jsonl"
    summary_path, copy_path = directory / "summary.json", directory / "candidates.jsonl"
    campaign, summary = read_json(campaign_path), read_json(summary_path)
    require(campaign["alphabet"] == ALPHABET and campaign["deterministic"] is True, "invalid campaign alphabet/mode")
    require(summary["campaign_sha256"] == digest(campaign_path), "campaign hash mismatch")
    require(summary["records_sha256"] == digest(records_path), "campaign records hash mismatch")
    require(campaign["candidate_sha256"] == digest(copy_path), "campaign copied-candidate hash mismatch")
    require(campaign["script_sha256"] == digest(directory / "campaign-source.py"), "campaign producer hash mismatch")
    require(summary["all_candidates_tested"] is True, "campaign is not finalized for every supplied candidate")
    require(summary["k"] == campaign["k"] and summary["alphabet"] == ALPHABET, "campaign summary k/alphabet mismatch")
    require(summary["global_maximum_certified"] is False and summary["minimality_certified"] is False,
            "bounded joint campaign claims minimality or global optimality")
    supplied = read_rows(copy_path)
    supplied_by_key = {row["key"]: row for row in supplied}
    require(len(supplied) == len(supplied_by_key) == campaign["candidate_count"] == summary["candidate_count"],
            "campaign candidate counts disagree")
    require(set(supplied_by_key) <= set(candidates), "campaign contains graphs outside the complete report candidate set")
    for key, row in supplied_by_key.items():
        require(checked_table(row) == candidates[key]["canonical_table"], "campaign graph differs from report candidate")
    result = read_rows(records_path)
    keyed = {row["key"]: row for row in result}
    require(len(result) == len(keyed) and set(keyed) == set(supplied_by_key), "campaign records omit or duplicate graphs")
    for key, row in keyed.items():
        check_parameters(row, campaign)
        require(checked_table(row) == candidates[key]["canonical_table"], "result graph differs from supplied graph")
        require(row["lower_bound"] == 1 and row["minimality_certified"] is False, "new run manufactured a lower bound")
        checked_pair(row)
        validate_windows(row)

    batch_references = []
    keys, batch_size = sorted(supplied_by_key), campaign["batch"]
    require(type(batch_size) is int and batch_size > 0, "invalid native batch size")
    expected_directories = {f"{index:05d}" for index in range((len(keys) + batch_size - 1) // batch_size)}
    actual_directories = {path.name for path in (directory / "batches").iterdir() if path.is_dir()}
    require(actual_directories == expected_directories, "native batch directories disagree with supplied graph count")
    for index, offset in enumerate(range(0, len(keys), batch_size)):
        batch_keys = keys[offset:offset + batch_size]
        completed = [path for path in sorted((directory / "batches" / f"{index:05d}").glob("attempt-*"))
                     if (path / "summary.json").is_file()]
        require(bool(completed), "native batch has no completed attempt")
        attempt = completed[0]  # Same immutable completed attempt used by the campaign producer.
        native, native_summary = read_json(attempt / "run.json"), read_json(attempt / "summary.json")
        check_parameters(native, campaign, native=True)
        require(native["executable_sha256"] == campaign["executable_sha256"], "native executable hash mismatch")
        require(native["graphs"] == batch_keys, "native batch graph list mismatch")
        require(native_summary["all_supplied_graphs_tested"] is True and native_summary["graphs"] == len(batch_keys),
                "native batch did not test every supplied graph")
        require(native_summary["k"] == campaign["k"] and native_summary["alphabet"] == ALPHABET
                and native_summary["deterministic"] is True, "native summary is not the declared full joint search")
        require(native_summary["records_sha256"] == digest(attempt / "records.jsonl"), "native records hash mismatch")
        native_rows = read_rows(attempt / "records.jsonl")
        require([row["key"] for row in native_rows] == batch_keys, "native records coverage/order mismatch")
        require(all(row == keyed[row["key"]] for row in native_rows), "campaign records differ from native evidence")
        require(native_summary["verified_pairs"] == sum(row["witness"] is not None for row in native_rows)
                and native_summary["no_pair"] == sum(row["witness"] is None for row in native_rows),
                "native positive/miss counts disagree")
        batch_references.append({"configuration": reference(attempt / "run.json"),
                                 "summary": reference(attempt / "summary.json"),
                                 "records": reference(attempt / "records.jsonl")})
    positive_count = sum(row["upper_bound"] is not None for row in result)
    require(summary["positive_count"] == positive_count and summary["no_pair"] == len(result) - positive_count,
            "campaign positive/miss counts disagree")
    require(summary["complete_windows"] == sum(row["complete_windows"] for row in result)
            and summary["partial_windows"] == 0, "campaign window totals disagree")
    require(summary["expansion_capped_graphs"] == sum(row["expansion_limit_reached"] for row in result),
            "campaign cap totals disagree")
    params = parameters(campaign)
    report = {"run_index": run_index, "directory": str(directory), **params,
              "candidate_count": len(result), "covers_entire_candidate_file": set(keyed) == set(candidates),
              "positive_count": positive_count, "no_pair": len(result) - positive_count,
              "cap_flag_graph_counts": {field: sum(row.get(field) is True for row in result) for field in CAP_FIELDS},
              "cap_flag_unreported_graph_counts": {field: sum(field not in row for row in result) for field in CAP_FIELDS},
              "complete_windows": sum(row["complete_windows"] for row in result),
              "retained_window_reports_checked": sum(len(row["window_reports"]) for row in result),
              "complete_window_reports_truncated": sum(row.get("window_reports_truncated", 0) for row in result),
              "windows_refused": sum(row["windows_refused"] for row in result),
              "joint_attempts": sum(row.get("attempts", 1) for row in result),
              "prefix_attempts": sum(row.get("prefix_attempts", 0) for row in result),
              "inputs": {"campaign": reference(campaign_path), "records": reference(records_path),
                         "summary": reference(summary_path), "candidates": reference(copy_path),
                         "producer": reference(directory / "campaign-source.py")},
              "native_batches": batch_references}
    return keyed, report


def observation(row, run):
    return {"run_index": run["run_index"], "k": run["k"], "B": run["B"], "D": run["D"],
            "U": run["U"], "P": run["P"], "status": row["status"], "upper_bound": row["upper_bound"],
            "cap_flags": {field: row.get(field) for field in CAP_FIELDS},
            "attempts": row.get("attempts", 1), "prefix_attempts": row.get("prefix_attempts", 0),
            "complete_windows": row["complete_windows"], "partial_windows": row["partial_windows"],
            "windows_refused": row["windows_refused"], "expanded_nodes": row["expanded_nodes"],
            "window_reports_truncated": row.get("window_reports_truncated", 0)}


def historical_comparison(path, candidates):
    comparisons = {}
    if path is None:
        return comparisons
    source = reference(path)
    for line, row in enumerate(read_rows(path), 1):
        key, upper = row.get("key"), row.get("upper_bound")
        if key not in candidates or upper is None:
            continue
        require(type(upper) is int and upper >= 1, "invalid imported historical upper bound")
        if "canonical_table" in row:
            require(checked_table(row) == candidates[key]["canonical_table"], "historical graph/key mismatch")
        if key not in comparisons or upper < comparisons[key]["upper_bound"]:
            comparisons[key] = {"upper_bound": upper, "lower_bound": row.get("lower_bound"),
                                "source": source, "line": line,
                                "role": "imported prior bound for comparison only; no historical words copied or searched",
                                "new_joint_k": None}
    return comparisons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--historical", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.candidates, args.out = args.candidates.resolve(), args.out.resolve()
    args.run = [path.resolve() for path in args.run]
    require(len(set(args.run)) == len(args.run), "duplicate campaign inputs")
    if args.historical:
        args.historical = args.historical.resolve()
    require(not args.out.exists() or not any(args.out.iterdir()), "use a fresh empty report directory")
    require(all(args.out != path and args.out not in path.parents for path in
                (args.candidates, *args.run, *((args.historical,) if args.historical else ()))),
            "report output must not contain an input")
    supplied = read_rows(args.candidates)
    candidates = {row["key"]: row for row in supplied}
    require(supplied and len(supplied) == len(candidates), "complete candidate file must be nonempty and unique")
    sizes = set()
    for row in supplied:
        sizes.add(len(checked_table(row)))
    require(len(sizes) == 1, "report inputs must have one exact graph size")
    m = sizes.pop()
    run_records, run_reports, covered = [], [], set()
    for index, directory in enumerate(args.run):
        records, report = audit_run(directory, candidates, index)
        require(report["m"] == m, "campaign graph size differs from report candidate size")
        run_records.append(records)
        run_reports.append(report)
        covered.update(records)
    require(covered == set(candidates), "completed runs do not cover the entire initial candidate file")
    prior = historical_comparison(args.historical, candidates)
    findings, chosen_k, chosen_parameters = [], Counter(), Counter()
    masks_replayed = 0
    for key in sorted(candidates):
        options, observations = [], []
        for records, report in zip(run_records, run_reports):
            if key not in records:
                continue
            row = records[key]
            observations.append(observation(row, report))
            if row["witness"] is not None:
                pair = checked_pair(row)
                rank = (row["upper_bound"], pair, report["k"], report["P"], report["B"],
                        report["D"], report["U"], report["directory"])
                options.append((rank, pair, report))
        chosen = min(options, key=lambda item: item[0]) if options else None
        upper, pair, source = None, None, None
        if chosen:
            rank, pair, run = chosen
            upper = rank[0]
            masks_replayed += scalar_replay(candidates[key]["canonical_table"], pair)
            source = {name: run[name] for name in ("run_index", "directory", "k", "P", "B", "D", "U")}
            chosen_k[str(run["k"])] += 1
            chosen_parameters[(run["k"], run["B"], run["P"], run["D"], run["U"])] += 1
        previous = prior.get(key)
        prior_upper = previous["upper_bound"] if previous else None
        prior_excludes = prior_upper is not None and prior_upper <= 50
        new_excludes = upper is not None and upper <= 50
        findings.append({"m": m, "key": key, "canonical_table": candidates[key]["canonical_table"],
                         "new_status": "verified-upper" if chosen else "unresolved", "new_lower_bound": 1,
                         "new_upper_bound": upper, "new_witness": list(pair) if pair else None,
                         "new_source": source, "new_observations": observations,
                         "new_miss": chosen is None, "historical_comparison": previous,
                         "historically_excluded_above_50": prior_excludes,
                         "potential_above_50": not (prior_excludes or new_excludes),
                         "potential_means_unexcluded_not_proved": True,
                         "static_masks_replayed_for_new_chosen_witness": (1 << m) if chosen else 0,
                         "minimality_certified": False})

    args.out.mkdir(parents=True, exist_ok=True)
    jsonl = args.out / "all-cases.jsonl"
    jsonl.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                             for row in findings), encoding="utf-8")
    csv_path = args.out / "all-cases.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("key", "new_upper", "source_k", "source_P", "source_B", "source_D", "source_U",
                         "prior_upper", "miss", "potential_above_50", "first_word", "second_word"))
        for row in findings:
            source, comparison = row["new_source"] or {}, row["historical_comparison"] or {}
            first, second = row["new_witness"] or ("", "")
            writer.writerow((row["key"], row["new_upper_bound"], source.get("k"), source.get("P"), source.get("B"),
                             source.get("D"), source.get("U"), comparison.get("upper_bound"),
                             row["new_miss"], row["potential_above_50"], first, second))
    summary = {"m": m, "joint_alphabet": ALPHABET, "k_values": sorted({run["k"] for run in run_reports}),
               "candidate_count": len(findings), "all_candidate_keys_match_input_union": True,
               "new_verified_positive_count": sum(not row["new_miss"] for row in findings),
               "new_upper_at_most_50": sum(row["new_upper_bound"] is not None and row["new_upper_bound"] <= 50 for row in findings),
               "new_upper_above_50": sum(row["new_upper_bound"] is not None and row["new_upper_bound"] > 50 for row in findings),
               "new_no_hit": sum(row["new_miss"] for row in findings),
               "historically_excluded_above_50": sum(row["historically_excluded_above_50"] for row in findings),
               "additional_historical_exclusions_after_new_weak_or_miss": sum(
                   row["historically_excluded_above_50"] and (row["new_upper_bound"] is None or row["new_upper_bound"] > 50)
                   for row in findings),
               "potential_above_50_after_separate_prior_comparison": sum(row["potential_above_50"] for row in findings),
               "chosen_source_k_counts": dict(sorted(chosen_k.items())),
               "chosen_source_parameter_counts": [{"k": k, "B": b, "P": p, "D": d, "U": u, "count": count}
                                                    for (k, b, p, d, u), count in sorted(chosen_parameters.items())],
               "new_chosen_witness_scalar_mask_checks": masks_replayed,
               "all_original_masks_per_chosen_positive": 1 << m,
               "runs": run_reports, "candidates": reference(args.candidates),
               "historical_input": reference(args.historical) if args.historical else None,
               "historical_words_used_in_new_search_or_new_witness_selection": False,
               "historical_bounds_independently_replayed_by_this_report": False,
               "historical_bounds_role": "imported prior certificates for separate comparison only",
               "agreement_monotonicity_assumed": False, "minimality_certified": False,
               "global_maximum_certified": False, "one_or_two_step_estimate_guarantee": False,
               "interpretation": "A new positive is an upper certificate. A miss or an upper above50 does not prove a graph exceeds50. Potential means unexcluded by the supplied new and prior bounds.",
               "window_audit_scope": "Every retained complete window checked against4**span leaves; truncated complete-window totals checked with the exact four-ary aggregate identity.",
               "output_jsonl": reference(jsonl), "output_csv": reference(csv_path),
               "auditor": reference(Path(__file__).resolve())}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({name: summary[name] for name in
                      ("k_values", "candidate_count", "new_upper_at_most_50", "new_upper_above_50",
                       "new_no_hit", "historically_excluded_above_50",
                       "potential_above_50_after_separate_prior_comparison", "new_chosen_witness_scalar_mask_checks")}))


if __name__ == "__main__":
    main()

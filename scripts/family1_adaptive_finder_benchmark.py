#!/usr/bin/env python3
"""Controlled deterministic joint-finder benchmark on frozen Family 1 pools.

Generation and membership come from supplied files.  The native query receives
only m, the canonical graph table, and the fixed search configuration.  Exact
scores and the complete maximizing-class lists are read only after all native
queries have completed.  A missing witness is always unresolved.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import time

REPO = Path(__file__).resolve().parents[1]
ALPHABET = ["00", "01", "10", "11"]
GLOBAL_H = {1: 1, 2: 3, 3: 6, 4: 10, 5: 15, 6: 23, 7: 34}


def rows(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def reference(path):
    path = Path(path).resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "sha256": digest(path), "bytes": path.stat().st_size}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def save_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in values))
    temporary.replace(path)


def table_key(table):
    m = len(table)
    assert m and all(len(pair) == 2 and all(type(x) is int and 0 <= x < m for x in pair) for pair in table)
    return "".join(f"{target:02d}" for pair in table for target in pair)


def pool_arguments(arguments):
    pools = []
    for argument in arguments:
        label, separator, filename = argument.partition("=")
        assert separator and label and filename, "--pool requires NAME=FILE.jsonl"
        path = Path(filename).resolve()
        assert path.is_file()
        pools.append((label, path))
    assert len({label for label, _ in pools}) == len(pools), "pool labels must be unique"
    return pools


def load_candidates(pools):
    """Intentionally ignore every score, pair, ordinal, and truth field."""
    cases = {}
    for label, path in pools:
        seen = set()
        for supplied in rows(path):
            table = supplied["canonical_table"]
            key, m = table_key(table), len(table)
            assert supplied.get("m", m) == m
            identity = m, key
            assert identity not in seen, f"duplicate member in pool {label}: {key}"
            seen.add(identity)
            case = cases.setdefault(identity, {"m": m, "key": key, "canonical_table": table, "pools": []})
            case["pools"].append(label)
        assert seen, f"empty pool {label}"
    return [cases[key] for key in sorted(cases)]


def scalar_trace(table, pair):
    assert isinstance(pair, list) and len(pair) == 2
    first, second = pair
    assert first != second and len(first) == len(second) and first and not (set(first + second) - {"0", "1"})
    states = [[0, 0] for _ in range(1 << len(table))]
    trace = [0]
    for a, b in zip(first, second):
        a, b = int(a), int(b)
        for mask, state in enumerate(states):
            left, right = state
            state[0] = table[left][a ^ ((mask >> left) & 1)]
            state[1] = table[right][b ^ ((mask >> right) & 1)]
        trace.append(sum(left != right for left, right in states))
    assert trace[-1] == 0, "positive fails independent all-mask scalar replay"
    return trace


def validate_native(directory, expected, config, exe_sha):
    native = json.loads((directory / "run.json").read_text())
    summary = json.loads((directory / "summary.json").read_text())
    assert native["executable_sha256"] == exe_sha
    for field, value in {"m": expected[0]["m"], "k": config["k"], "score": config["score"],
                         "startup": "divergence", "common_depth": config["common_depth"],
                         "beam_width": config["beam"], "diagonal_width": 0, "unequal_width": 0,
                         "max_length": config["max_length"], "max_expansions": config["expansions"],
                         "prefix_pairs": 0, "target_upper": 0, "deterministic": True}.items():
        assert native[field] == value, (field, native[field], value)
    assert native["graphs"] == [case["key"] for case in expected]
    assert native["alphabet"] == ALPHABET
    assert summary["all_supplied_graphs_tested"] is True
    assert summary["records_sha256"] == digest(directory / "records.jsonl")
    records = rows(directory / "records.jsonl")
    assert [row["key"] for row in records] == native["graphs"]
    verifications = 0
    by_key = {case["key"]: case for case in expected}
    for record in records:
        assert record["canonical_table"] == by_key[record["key"]]["canonical_table"]
        assert record["k"] == config["k"] and record["score"] == config["score"]
        assert record["alphabet"] == ALPHABET and record["partial_windows"] == 0
        assert record["lower_bound"] == 1 and record["minimality_certified"] is False
        assert record["divergence_startup_evaluated_all"] is True
        for window in record["window_reports"]:
            span = window["span"]
            assert window["complete"] is True
            assert window["leaves"] == window["expected_leaves"] == 4 ** span
            assert window["nodes"] == sum(4 ** depth for depth in range(1, span + 1))
        if record["upper_bound"] is None:
            assert record["witness"] is None
        else:
            trace = scalar_trace(record["canonical_table"], record["witness"])
            assert len(trace) - 1 == record["upper_bound"]
            assert record["witness_metric_trace"] == trace
            assert record["synchronized_count_trace"] == [(1 << record["m"]) - x for x in trace]
            verifications += 1 << record["m"]
    improvement_path = directory / "witnesses.jsonl"
    for row in rows(improvement_path):
        table = by_key[row["key"]]["canonical_table"]
        trace = scalar_trace(table, row["witness"])
        assert len(trace) - 1 == row["upper_bound"]
        if "witness_metric_trace" in row:
            assert row["witness_metric_trace"] == trace
        verifications += 1 << len(table)
    return records, verifications


def run_config(args, cases, config, exe_sha):
    label = config["id"]
    directory = args.out / label
    grouped = defaultdict(list)
    for case in cases:
        grouped[case["m"]].append(case)
    batches = [(m, start // args.batch, group[start:start + args.batch])
               for m, group in sorted(grouped.items()) for start in range(0, len(group), args.batch)]
    started = time.monotonic()

    def evaluate(specification):
        m, index, batch = specification
        batch_dir = directory / f"m{m}" / f"batch-{index:05d}"
        batch_dir.mkdir(parents=True, exist_ok=True)
        attempts = sorted(batch_dir.glob("attempt-*"))
        for attempt in attempts:
            if (attempt / "summary.json").exists():
                record, checked = validate_native(attempt, batch, config, exe_sha)
                return record, checked, 0.0, True
        attempt = batch_dir / f"attempt-{len(attempts):03d}"
        command = [str(args.exe), "--m", str(m), "--out", str(attempt), "--k", str(config["k"]),
                   "--beam", str(config["beam"]), "--diagonal-beam", "0", "--unequal-beam", "0",
                   "--max-length", str(config["max_length"]), "--expansions", str(config["expansions"]),
                   "--startup", "divergence", "--common-depth", str(config["common_depth"]),
                   "--score", config["score"], "--trace-records", "64"]
        for case in batch:
            command += ["--graph", case["key"]]
        save(batch_dir / f"command-{len(attempts):03d}.json", command)
        before = time.monotonic()
        process = subprocess.run(command, capture_output=True, text=True)
        seconds = time.monotonic() - before
        (batch_dir / f"log-{len(attempts):03d}.txt").write_text(process.stdout + process.stderr)
        save(batch_dir / f"timing-{len(attempts):03d}.json", {"subprocess_seconds": seconds, "returncode": process.returncode})
        if process.returncode:
            raise RuntimeError(f"{label} m={m} batch={index}: {process.stdout}\n{process.stderr}")
        record, checked = validate_native(attempt, batch, config, exe_sha)
        return record, checked, seconds, False

    all_records, replayed, subprocess_seconds, reused = [], 0, 0.0, 0
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures = [workers.submit(evaluate, batch) for batch in batches]
        for number, future in enumerate(as_completed(futures), 1):
            record, checked, seconds, cached = future.result()
            all_records.extend(record)
            replayed += checked
            subprocess_seconds += seconds
            reused += cached
            if number % 10 == 0 or number == len(batches):
                print(json.dumps({"configuration": label, "joint_k": config["k"], "complete_batches": number,
                                  "total_batches": len(batches), "complete_graphs": len(all_records),
                                  "seconds": round(time.monotonic() - started, 3)}), flush=True)
    all_records.sort(key=lambda row: (row["m"], row["key"]))
    assert [(row["m"], row["key"]) for row in all_records] == [(case["m"], case["key"]) for case in cases]
    save_rows(directory / "records.jsonl", all_records)
    save(directory / "run-audit.json", {"configuration": config, "graphs": len(cases),
          "all_supplied_candidates_tested": True, "scalar_mask_replays_final_and_improvements": replayed,
          "reused_completed_batches": reused, "subprocess_seconds_this_invocation": subprocess_seconds,
          "wall_seconds_this_invocation": time.monotonic() - started,
          "records": reference(directory / "records.jsonl")})
    return all_records


def load_truth(exact_paths):
    champion_paths = [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"]
    champions, scores = set(), {}
    for path in champion_paths:
        for row in rows(path):
            identity = row["m"], table_key(row["canonical_table"])
            assert row["status"] == "exact" and row["merge_length"] == GLOBAL_H[row["m"]]
            champions.add(identity)
            scores[identity] = row["merge_length"]
    for path in exact_paths:
        for row in rows(path):
            if row.get("status") != "exact" and row.get("exact") is not True and "reference_H" not in row:
                continue
            table = row["canonical_table"]
            identity = len(table), table_key(table)
            score = row.get("reference_H", row.get("merge_length", row.get("H")))
            assert isinstance(score, int) and 1 <= score <= GLOBAL_H[identity[0]]
            if identity in scores:
                assert scores[identity] == score
            assert (score == GLOBAL_H[identity[0]]) == (identity in champions), "exact corpus contradicts complete champion list"
            scores[identity] = score
    return champions, scores, [reference(path) for path in champion_paths + exact_paths]


def pool_metrics(cases, records, champions, scores, config, crowd_band, crowd_min, crowd_fraction):
    keyed = {(row["m"], row["key"]): row for row in records}
    groups = defaultdict(list)
    for case in cases:
        for pool in case["pools"]:
            groups[pool, case["m"]].append(case)
    result = []
    for (pool, m), group in sorted(groups.items()):
        identities = [(m, case["key"]) for case in group]
        known_winners = set(identities) & champions
        finite = {identity: keyed[identity]["upper_bound"] for identity in identities if keyed[identity]["upper_bound"] is not None}
        misses = set(identities) - set(finite)
        maximum_proxy = max(finite.values()) if finite else None
        apparent = {identity for identity, length in finite.items() if length >= maximum_proxy - crowd_band}
        safe_excluded = {identity for identity, length in finite.items() if length < GLOBAL_H[m]}
        safe_survivors = set(identities) - safe_excluded
        assert not (safe_excluded & known_winners), "a verified upper bound excluded a true winner"
        exact_ids = set(identities) & scores.keys()
        gaps = [finite[identity] - scores[identity] for identity in exact_ids & finite.keys()]
        assert all(gap >= 0 for gap in gaps)
        count, share = len(apparent), len(apparent) / len(group)
        configurations = {"k": config["k"], "score": config["score"], "common_depth": config["common_depth"],
                          "beam_width": config["beam"], "max_length": config["max_length"],
                          "max_expansions_per_attempt": config["expansions"]}
        result.append({"pool": pool, "m": m, "configuration": config["id"], **configurations,
            "candidate_count": len(group), "true_champions_in_pool": len(known_winners), "global_exact_maximum": GLOBAL_H[m],
            "finite_verified_upper_count": len(finite), "unresolved_misses": len(misses), "largest_finite_upper_proxy": maximum_proxy,
            "relative_top_band": crowd_band, "relative_top_count": count, "relative_top_fraction": share,
            "crowding_trigger": count >= crowd_min and share >= crowd_fraction,
            "crowding_min_count": crowd_min, "crowding_min_fraction": crowd_fraction,
            "relative_top_true_champions": len(apparent & known_winners),
            "relative_top_false_apparent_champions": len(apparent - known_winners),
            "relative_top_champion_recall": len(apparent & known_winners) / len(known_winners) if known_winners else None,
            "relative_top_champion_precision": len(apparent & known_winners) / count if count else None,
            "relative_top_is_a_ranking_diagnostic_never_a_discard_rule": True,
            "finite_upper_above_global_maximum": sum(length > GLOBAL_H[m] for length in finite.values()),
            "bound_certified_exclusions_at_global_maximum": len(safe_excluded),
            "bound_safe_shortlist_size_including_misses": len(safe_survivors),
            "bound_safe_shortlist_true_champions": len(safe_survivors & known_winners),
            "bound_safe_shortlist_false_survivors": len(safe_survivors - known_winners),
            "bound_safe_champion_recall": len(safe_survivors & known_winners) / len(known_winners) if known_winners else None,
            "exact_H_cases": len(exact_ids), "exact_H_finite_cases": len(gaps),
            "exact_H_found_optimal": sum(gap == 0 for gap in gaps), "exact_H_found_within_two": sum(gap <= 2 for gap in gaps),
            "exact_H_median_gap_if_found": statistics.median(gaps) if gaps else None,
            "exact_H_max_gap_if_found": max(gaps) if gaps else None,
            "expanded_nodes": sum(keyed[identity]["expanded_nodes"] for identity in identities),
            "complete_windows": sum(keyed[identity]["complete_windows"] for identity in identities),
            "partial_windows": sum(keyed[identity]["partial_windows"] for identity in identities),
            "work_measurement": "sum of all queried configurations" if any("portfolio_work" in keyed[x] for x in identities) else "single configuration",
            "selected_witness_expanded_nodes": sum(keyed[x].get("selected_witness_expanded_nodes", keyed[x]["expanded_nodes"]) for x in identities),
            "expansion_capped_graphs": sum(keyed[identity]["expansion_limit_reached"] for identity in identities),
            "length_capped_graphs": sum(keyed[identity]["length_limit_reached"] for identity in identities),
            "upper_histogram": dict(sorted(Counter(finite.values()).items()))})
    return result


def comparison_rows(cases, configs, by_config, metrics):
    baseline = configs[0]
    base = {(row["m"], row["key"]): row for row in by_config[baseline["id"]]}
    result = []
    for config in configs[1:]:
        current = {(row["m"], row["key"]): row for row in by_config[config["id"]]}
        individual = []
        union = []
        for case in cases:
            identity = case["m"], case["key"]
            a, b = base[identity]["upper_bound"], current[identity]["upper_bound"]
            delta = None if a is None or b is None else b - a
            individual.append({"m": case["m"], "key": case["key"], "pools": case["pools"],
                "baseline_configuration": baseline["id"], "baseline_k": baseline["k"],
                "new_configuration": config["id"], "new_k": config["k"], "baseline_upper": a,
                "new_upper": b, "finite_length_delta": delta, "miss_resolved": a is None and b is not None,
                "positive_lost_in_independent_run": a is not None and b is None})
            selected = base[identity] if b is None or (a is not None and a <= b) else current[identity]
            # Bounds use the best verified witness, while work includes BOTH
            # configurations.  Copy first: native records remain immutable.
            portfolio = {**selected, "portfolio_work": True,
                         "selected_witness_expanded_nodes": selected["expanded_nodes"]}
            for field in ("expanded_nodes", "complete_windows", "partial_windows"):
                portfolio[field] = base[identity][field] + current[identity][field]
            for field in ("expansion_limit_reached", "length_limit_reached"):
                portfolio[field] = base[identity][field] or current[identity][field]
            union.append(portfolio)
        result.append({"baseline": baseline["id"], "baseline_k": baseline["k"], "new": config["id"],
                       "new_k": config["k"], "rows": individual, "portfolio": union})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", action="append", required=True, help="NAME=FILE.jsonl; all supplied members are tested")
    parser.add_argument("--exact", action="append", type=Path, default=[], help="Full exact-H corpus, read only for final analysis")
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ks", type=int, nargs="+", default=[2, 4, 6])
    parser.add_argument("--scores", nargs="+", choices=["total", "permutation"], default=["total", "permutation"])
    parser.add_argument("--common-depth", type=int, default=2)
    parser.add_argument("--beam", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=80)
    parser.add_argument("--expansions", type=int, default=2000000)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--crowd-band", type=int, default=2)
    parser.add_argument("--crowd-min", type=int, default=3)
    parser.add_argument("--crowd-fraction", type=float, default=0.1)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.exe, args.out = args.exe.resolve(), args.out.resolve()
    assert args.exe.is_file() and args.jobs > 0 and args.batch > 0
    assert all(1 <= k <= 8 for k in args.ks) and len(set(args.ks)) == len(args.ks)
    assert len(set(args.scores)) == len(args.scores) and 0 <= args.common_depth <= 8
    assert args.beam > 0 and args.max_length > 0 and args.expansions > 0
    assert args.crowd_band >= 0 and args.crowd_min > 0 and 0 <= args.crowd_fraction <= 1
    pools = pool_arguments(args.pool)
    cases = load_candidates(pools)
    configs = [{"id": f"{score}-c{args.common_depth}-k{k}", "k": k, "score": score,
                "common_depth": args.common_depth, "beam": args.beam, "max_length": args.max_length,
                "expansions": args.expansions} for k in args.ks for score in args.scores]
    exe_before = reference(args.exe)
    manifest = {"schema": 1, "driver": reference(__file__), "executable": exe_before,
                "pools": [{"name": label, **reference(path)} for label, path in pools],
                "exact_sources_not_passed_to_search": [reference(path) for path in args.exact],
                "configurations": configs, "alphabet": ALPHABET, "deterministic": True,
                "candidate_count": len(cases), "fixed_candidate_list": True, "all_members_tested": True,
                "candidate_scores_pairs_and_order_hints_used_by_search": False,
                "randomness_used": False, "time_caps_used": False, "jobs": args.jobs, "batch": args.batch,
                "crowding_rule": {"band_below_largest_finite_upper": args.crowd_band,
                    "minimum_count": args.crowd_min, "minimum_pool_fraction": args.crowd_fraction,
                    "misses_count_towards_trigger": False, "used_to_discard_candidates": False}}
    manifest_path = args.out / "manifest.json"
    if manifest_path.exists():
        assert args.resume and json.loads(manifest_path.read_text()) == manifest, "resume requires exact frozen inputs/configuration"
    else:
        assert not args.resume and (not args.out.exists() or not any(args.out.iterdir())), "fresh output required"
        args.out.mkdir(parents=True, exist_ok=True)
        save(manifest_path, manifest)
        save_rows(args.out / "candidates-used.jsonl", cases)
        shutil.copy2(__file__, args.out / "driver-source.py")
    records = {}
    started = time.monotonic()
    for config in configs:
        records[config["id"]] = run_config(args, cases, config, exe_before["sha256"])
    # Do not move this above the native runs: oracle data is an audit, never a search hint.
    champions, exact_scores, truth_sources = load_truth(args.exact)
    assert reference(args.exe) == exe_before, "native binary changed during benchmark"
    summaries = []
    for config in configs:
        summaries += pool_metrics(cases, records[config["id"]], champions, exact_scores, config,
                                  args.crowd_band, args.crowd_min, args.crowd_fraction)
    comparisons = comparison_rows(cases, configs, records, summaries)
    portfolio_summaries, delta_summaries = [], []
    for comparison, config in zip(comparisons, configs[1:]):
        baseline = configs[0]
        portfolio_config = {**config, "id": baseline["id"] + "+" + config["id"], "k": [baseline["k"], config["k"]]}
        portfolio_summaries += pool_metrics(cases, comparison["portfolio"], champions, exact_scores, portfolio_config,
                                            args.crowd_band, args.crowd_min, args.crowd_fraction)
        save_rows(args.out / f"deltas-{config['id']}.jsonl", comparison["rows"])
        rows_ = comparison["rows"]
        delta_summaries.append({"baseline": baseline["id"], "baseline_k": baseline["k"],
            "new": config["id"], "new_k": config["k"], "candidate_count": len(rows_),
            "finite_improvements": sum(row["finite_length_delta"] is not None and row["finite_length_delta"] < 0 for row in rows_),
            "finite_regressions": sum(row["finite_length_delta"] is not None and row["finite_length_delta"] > 0 for row in rows_),
            "misses_resolved": sum(row["miss_resolved"] for row in rows_),
            "positives_lost_in_independent_run": sum(row["positive_lost_in_independent_run"] for row in rows_)})
    save_rows(args.out / "metrics.jsonl", summaries)
    save_rows(args.out / "portfolio-metrics.jsonl", portfolio_summaries)
    summary = {"schema": 1, "alphabet": ALPHABET, "joint_ks": args.ks, "configurations": configs,
               "candidate_count": len(cases), "query_count": len(cases) * len(configs),
               "deterministic": True, "all_candidates_tested_in_every_configuration": True,
               "truth_read_only_after_all_searches": True, "truth_sources": truth_sources,
               "metrics": summaries, "portfolio_metrics": portfolio_summaries, "deltas": delta_summaries,
               "wall_seconds_this_invocation": time.monotonic() - started,
               "manifest": reference(manifest_path), "global_shortestness_certified_by_finder": False,
               "relative_proxy_shortlists_are_diagnostic_only": True,
               "bound_safe_shortlists_use_exhaustive_global_H_only_for_this_retrospective_audit": True}
    save(args.out / "summary.json", summary)
    print(json.dumps({"joint_ks": args.ks, "configurations": len(configs), "cases": len(cases),
                      "summary": str(args.out / "summary.json")}), flush=True)


if __name__ == "__main__":
    main()

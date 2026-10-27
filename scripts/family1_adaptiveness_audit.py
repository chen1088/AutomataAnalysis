#!/usr/bin/env python3
"""Audit exhaustive truth and evaluation of every declared edit neighborhood.

This launches no search. It replays every final witness on every original
static mask, checks exact small-size histograms, and joins sealed edit keys to
completed evaluations. An evaluated neighborhood is not a global search.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COUNTS = {1: 1, 2: 6, 3: 57, 4: 678, 5: 10398}
MAXIMA = {1: 1, 2: 3, 3: 6, 4: 10, 5: 15}


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def reference(path):
    path = path.resolve()
    return {"path": path.relative_to(REPO).as_posix(), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def table_key(table):
    m = len(table)
    assert m and all(len(row) == 2 and all(type(q) is int and 0 <= q < m for q in row) for row in table)
    return "".join(f"{q:02d}" for row in table for q in row)


def replay(row):
    pair = row["witness"]
    assert len(pair) == 2 and pair[0] != pair[1] and len(pair[0]) == len(pair[1]) == row["upper_bound"]
    assert all(word and set(word) <= {"0", "1"} for word in pair)
    table, m = row["canonical_table"], row["m"]
    trace = [0] * (len(pair[0]) + 1)
    for mask in range(1 << m):
        left = right = 0
        for i, (a, b) in enumerate(zip(*pair), 1):
            left = table[left][int(a) ^ ((mask >> left) & 1)]
            right = table[right][int(b) ^ ((mask >> right) & 1)]
            trace[i] += left != right
        assert left == right, (m, row["key"], mask)
    assert trace[0] == trace[-1] == 0
    if "witness_metric_trace" in row:
        assert row["witness_metric_trace"] == trace
        assert row["synchronized_count_trace"] == [(1 << m) - d for d in trace]
    return (1 << m), (1 << m) * len(pair[0])


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=REPO / "out/family1-adaptiveness-20261026")
    parser.add_argument("--exact-template", default="out/family1-m8-challenger-20261026/target-full-cli-test/exact-{m}/records.jsonl")
    parser.add_argument("--exact-m5", type=Path, default=REPO / "out/family1-adaptiveness-20261026/exact-m5/records.jsonl")
    parser.add_argument("--out", type=Path, default=REPO / "results/family1-adaptiveness-20261026/evaluation-audit.json")
    args = parser.parse_args()
    distributions_path = REPO / "results/family1-m1-m6/score-distributions.json"
    distributions = json.loads(distributions_path.read_text())
    winner_paths = [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"]
    winners = {(row["m"], table_key(row["canonical_table"])) for path in winner_paths for row in read_rows(path)}
    records_by_m, source_by_m, truth = {}, {}, []
    mask_checks = prefix_updates = verified_pairs = 0
    for m in range(1, 6):
        path = args.exact_m5 if m == 5 else REPO / args.exact_template.format(m=m)
        summary_path = path.parent / "summary.json"
        summary = json.loads(summary_path.read_text())
        assert all(summary[field] is True for field in ["enumeration_complete", "scoring_complete", "global_maximum_certified", "maximizing_collection_complete"])
        records = read_rows(path)
        keyed = {row["key"]: row for row in records}
        assert len(keyed) == len(records) == COUNTS[m]
        histogram = Counter()
        for key, row in keyed.items():
            assert row["m"] == m and key == table_key(row["canonical_table"])
            assert row["status"] == "exact" and row["lower_bound"] == row["upper_bound"] == row["merge_length"]
            length = row["merge_length"]
            histogram[str(length)] += 1
            assert ((m, key) in winners) == (length == MAXIMA[m])
            count, updates = replay(row)
            mask_checks += count
            prefix_updates += updates
            verified_pairs += 1
        assert dict(histogram) == distributions[str(m)]
        assert summary["records_sha256"] == reference(path)["sha256"]
        records_by_m[m], source_by_m[m] = keyed, reference(path)
        truth.append({"m": m, "k": None, "window_kind": "exact-word-layer-oracle", "count": len(records),
                      "maximum": MAXIMA[m], "winner_count": histogram[str(MAXIMA[m])], "histogram": dict(histogram),
                      "records": reference(path), "summary": reference(summary_path)})

    joint_runs = []
    for m in [6, 7]:
        path = args.work / f"policy/m{m}/total-c2-k2/records.jsonl"
        rows = read_rows(path)
        keyed = {row["key"]: row for row in rows}
        assert len(rows) == len(keyed)
        for row in rows:
            assert row["m"] == m and row["key"] == table_key(row["canonical_table"])
            assert row["k"] == 2 and row["score"] == "total" and row["deterministic"] is True
            assert row["alphabet"] == ["00", "01", "10", "11"] and row["partial_windows"] == 0
            assert row["minimality_certified"] is False and row["lower_bound"] == 1
            for window in row["window_reports"]:
                assert window["complete"] is True
                assert window["leaves"] == window["expected_leaves"] == 4 ** window["span"]
                assert window["nodes"] == sum(4 ** depth for depth in range(1, window["span"] + 1))
            if row["upper_bound"] is not None:
                count, updates = replay(row)
                mask_checks += count
                prefix_updates += updates
                verified_pairs += 1
        records_by_m[m], source_by_m[m] = keyed, reference(path)
        joint_runs.append({"m": m, "k": 2, "window_kind": "joint-pair", "score": "total", "count": len(rows),
                           "positive_count": sum(row["upper_bound"] is not None for row in rows),
                           "miss_count": sum(row["upper_bound"] is None for row in rows), "records": reference(path)})

    seal_path = args.work / "edit/generation-seal.json"
    seal = json.loads(seal_path.read_text())
    assert seal["randomness"] is False and seal["target_truth_loaded"] is False
    pools = []
    for entry in seal["pools"]:
        assert entry["generation_complete"] is True and entry["randomness"] is False
        path = REPO / entry["candidates"]["path"]
        assert reference(path)["sha256"] == entry["candidates"]["sha256"]
        candidates = read_rows(path)
        m = entry["target_m"]
        keys = {row["key"] for row in candidates}
        assert len(keys) == len(candidates) == entry["candidates_all_roots"]
        assert not keys - records_by_m[m].keys(), "Unevaluated candidate in declared complete pool"
        for closure in [False, True]:
            members = keys if closure else {row["key"] for row in candidates if row["root_fixed"]}
            assert len(members) == entry["candidates_all_roots" if closure else "candidates_root_fixed"]
            pools.append({"pool": entry["pool_id"], "m": m, "radius": entry["radius"], "root_closure": closure,
                          "generation_k": None, "generation_window": "N/A: graph generation",
                          "evaluation_k": None if m <= 5 else 2,
                          "evaluation_window": "exact-word-layer-oracle" if m <= 5 else "joint-pair",
                          "candidate_count": len(members), "evaluated_count": len(members), "missing_count": 0,
                          "all_members_evaluated": True, "evaluation_records": source_by_m[m]})
    assert len(pools) == 40
    report = {"schema": 1, "passed": True, "search_launched": False, "randomness": False,
              "exact_truth_k": None, "exact_truth_window": "N/A: exhaustive word-layer oracle",
              "truth": truth, "baseline_complete_joint_runs": joint_runs,
              "declared_neighborhood_comparisons": len(pools), "all_declared_neighborhood_members_evaluated": True,
              "unique_evaluated_graphs_through_m7": sum(len(values) for values in records_by_m.values()),
              "verification": {"method": "independent Python scalar replay on every original static mask",
                               "final_pairs_replayed": verified_pairs, "word_pair_mask_checks": mask_checks,
                               "joint_prefix_mask_updates": prefix_updates, "all_passed": True},
              "neighborhoods": pools, "generation_seal": reference(seal_path),
              "truth_sources": [reference(distributions_path)] + [reference(path) for path in winner_paths],
              "audit_source": reference(Path(__file__)),
              "limits": ["Exact numerical nonwinner H is available here through m5 only.",
                         "A completed bounded pair-finder query may miss; it is still recorded as an evaluation.",
                         "Complete candidate neighborhoods and correct witness certificates do not prove global optimality at m8."]}
    write_json(args.out, report)
    print(json.dumps({"out": str(args.out), "passed": True, "neighborhoods": len(pools),
                      "graphs": report["unique_evaluated_graphs_through_m7"], "verification": report["verification"]}))


if __name__ == "__main__":
    main()

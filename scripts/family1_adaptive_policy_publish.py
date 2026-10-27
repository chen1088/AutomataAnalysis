#!/usr/bin/env python3
"""Publish complete candidate-by-candidate bounds and adaptive-policy audits.

This read-only analysis validates sealed native outputs and writes small CSV
shards. Every finite bound includes its actual two strings and joint k. Native
misses are represented by empty upper/witness cells, never fabricated scores.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil

REPO = Path(__file__).resolve().parents[1]


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def write_csv(path, values):
    assert values
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def policy_cell(metric, initial, forced, action, trigger):
    portfolio = "runs" in metric["configuration"]
    return {
        "m": metric["m"], "initial_pool": initial["pool"], "action": action,
        "forced_factorial": forced, "baseline_finite_topband_count": initial["operational_topband"]["size"],
        "crowding_tau": initial["operational_topband"]["crowding_threshold"],
        "crowding_gate_fired": trigger, "result_pool": metric["pool"],
        "configuration": metric["configuration"]["id"], "joint_k": ";".join(map(str, metric["k"])),
        "unique_candidates": metric["queries"], "native_graph_queries": metric["queries"] * (2 if portfolio else 1),
        "true_winners_in_pool": metric["winner_count_in_pool"], "complete_winner_count": metric["all_exhaustive_winners"],
        "finite_verified_pairs": metric["finite_verified_pairs"], "unresolved": metric["unresolved_no_pair"],
        "reference_cutoff_survivors": metric["reference_cutoff"]["survivors"],
        "reference_cutoff_false_finite": metric["reference_cutoff"]["finite_false_apparent_champions"],
        "reference_cutoff_false_survivors": metric["reference_cutoff"]["false_survivors"],
        "operational_topband_count": metric["operational_topband"]["size"],
        "operational_topband_true_winners": metric["operational_topband"]["true_winners"],
        "operational_topband_shapes": metric["operational_topband"]["shapes"],
        "expanded_nodes": metric["expanded_nodes"], "complete_windows": metric["complete_windows"],
    }


def publish(source, target, chunk):
    target.mkdir(parents=True, exist_ok=True)
    summary = json.loads((source / "summary.json").read_text())
    manifest = json.loads((source / "manifest.json").read_text())
    seal = json.loads((source / "query-seal.json").read_text())
    assert seal["all_configurations_and_candidates_completed"] and seal["target_truth_opened_during_scoring"] is False
    for ref in seal["records"]:
        path = REPO / ref["path"]
        assert digest(path) == ref["sha256"]
    cases = rows(source / "candidates-used.jsonl")
    keys = [case["key"] for case in cases]
    assert keys == sorted(set(keys)) and len(keys) == summary["candidate_count"]
    m = summary["m"]
    winner_files = [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"]
    champions = {row["key"] for path in winner_files for row in rows(path) if row["m"] == m}
    config_records, all_records, stats = {}, [], []
    for config in summary["configurations"]:
        label = config["id"]
        records = rows(source / label / "records.jsonl")
        assert [row["key"] for row in records] == keys
        assert all(row["m"] == m and row["k"] == config["k"] and row["score"] == config["score"] for row in records)
        assert all(row["partial_windows"] == 0 for row in records)
        config_records[label] = {row["key"]: row for row in records}
        all_records.extend(records)
        audit = json.loads((source / label / "run-audit.json").read_text())
        assert audit["all_supplied_candidates_tested"] and audit["graphs"] == len(cases)
        stats.append({"configuration": config, "graphs": len(records), "all_candidates_tested": True,
                      "expanded_nodes": sum(row["expanded_nodes"] for row in records),
                      "complete_windows": sum(row["complete_windows"] for row in records),
                      "partial_windows": sum(row["partial_windows"] for row in records),
                      "expansion_capped_graphs": sum(row["expansion_limit_reached"] for row in records),
                      "independent_scalar_mask_replays": audit["scalar_mask_replays_final_and_improvements"],
                      "run_audit_sha256": digest(source / label / "run-audit.json")})
    compact = []
    examples = []
    example_keys = set(champions)
    for metric in summary["metrics"]:
        pool, label = metric["pool"], metric["configuration"]["id"]
        maximum = metric["operational_topband"]["maximum_finite_upper"]
        for case in cases:
            record = config_records[label][case["key"]]
            if pool in case["pools"] and record["upper_bound"] is not None and record["upper_bound"] >= maximum - 2:
                example_keys.add(case["key"])
    for case in cases:
        key = case["key"]
        value = {"m": m, "key": key, "shape_key": case["shape_key"], "pools": ";".join(case["pools"]),
                 "certified_champion": key in champions, "exhaustive_global_maximum": summary["certified_maximum"]}
        for config in summary["configurations"]:
            label = config["id"]
            record = config_records[label][key]
            pair = record["witness"] or ["", ""]
            for field, content in {"k": record["k"], "upper": record["upper_bound"], "u": pair[0], "v": pair[1],
                                   "nodes": record["expanded_nodes"], "windows": record["complete_windows"]}.items():
                value[label + "_" + field] = content
            if key in example_keys:
                examples.append({"m": m, "key": key, "configuration": label, "joint_k": config["k"],
                    "startup": "divergence", "common_depth": config["common_depth"], "score": config["score"],
                    "certified_champion": key in champions, "verified_upper": record["upper_bound"],
                    "u": pair[0], "v": pair[1], "D_trace": json.dumps(record["witness_metric_trace"]),
                    "scalar_masks_verified": (1 << m) if record["upper_bound"] is not None else 0,
                    "source": (source / label / "records.jsonl").relative_to(REPO).as_posix()})
        compact.append(value)
    for start in range(0, len(compact), chunk):
        write_csv(target / f"records-{start // chunk:03d}.csv", compact[start:start + chunk])
    write_csv(target / "example-witnesses.csv", examples)
    forced, gated = [], []
    baseline = summary["configurations"][0]["id"]
    indexed = {(metric["pool"], metric["configuration"]["id"]): metric for metric in summary["metrics"] + summary["retained_upper_portfolios"]}
    for roots in ("fixedroot", "allroots"):
        initial = indexed["winners-" + roots, baseline]
        trigger = initial["operational_topband"]["crowding_triggered"]
        treatments = [baseline] + [metric["configuration"]["id"] for metric in summary["retained_upper_portfolios"] if metric["pool"] == initial["pool"]]
        for edited in (False, True):
            pool = ("near2-" if edited else "winners-") + roots
            for treatment in treatments:
                action = ("broaden-parents" if edited else "keep-parents") + "/" + ("keep-finder" if treatment == baseline else treatment)
                requested = indexed[pool, treatment]
                forced.append(policy_cell(requested, initial, True, action, trigger))
                actual = requested if trigger else initial
                gated.append(policy_cell(actual, initial, False, action, trigger))
    write_csv(target / "forced-factorial.csv", forced)
    write_csv(target / "crowding-gated.csv", gated)
    shutil.copy2(source / "summary.json", target / "summary.json")
    shutil.copy2(source / "manifest.json", target / "run.json")
    save(target / "query-audit.json", seal)
    save(target / "validation.json", {"m": m, "candidate_count": len(cases), "configurations": stats,
        "all_candidate_keys_and_query_hashes_verified": True, "all_finite_pairs_in_public_csv": True,
        "finite_pairs": sum(row["upper_bound"] is not None for row in all_records),
        "misses": sum(row["upper_bound"] is None for row in all_records),
        "target_labels_used_only_after_query_seal": True,
        "portfolio_bounds": "minimum of earlier and refinement verified uppers; misses never replace positives",
        "portfolio_cost": "sum of both queried configurations, including unresolved attempts",
        "crowding_gate": "finite upper within2 of maximum finite upper, count>=3; no misses included",
        "forced_and_gated_policy_cells_are_separate": True,
        "query_driver_snapshot_sha256": digest(source / "policy-driver-source.py"),
        "finder_helper_snapshot_sha256": digest(source / "finder-driver-source.py"),
        "publisher_sha256": digest(Path(__file__))})
    public_files = sorted(path for path in target.iterdir() if path.is_file() and path.name != "publication-manifest.json")
    assert all(path.stat().st_size < 1 << 20 for path in public_files)
    save(target / "publication-manifest.json", {"files": [{"path": path.name, "sha256": digest(path),
          "bytes": path.stat().st_size} for path in public_files]})
    print(json.dumps({"m": m, "joint_k": summary["k"], "candidates": len(cases),
                      "public_csv_shards": (len(compact) + chunk - 1) // chunk, "target": str(target)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--chunk", type=int, default=1000)
    args = parser.parse_args()
    assert args.chunk > 0
    publish(args.source.resolve(), args.out.resolve(), args.chunk)


if __name__ == "__main__":
    main()

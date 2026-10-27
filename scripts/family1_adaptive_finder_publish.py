#!/usr/bin/env python3
"""Publish compact, complete finder audit tables; no search is launched."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

import family1_adaptive_finder_benchmark as B

REPO = Path(__file__).resolve().parents[1]


def csv_file(path, values):
    values = list(values)
    assert values
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="Completed benchmark's local output directory")
    parser.add_argument("--followup", action="append", type=Path, default=[], help="Additional completed benchmark, e.g. fixed-pool k8")
    parser.add_argument("--out", type=Path, required=True, help="Compact public artifact directory")
    args = parser.parse_args()
    OUT = args.out.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [args.run.resolve()] + [path.resolve() for path in args.followup]
    source_runs, public_files, summaries, winners, all_deltas, verification = [], [], [], [], [], []
    for root in paths:
        summary = json.loads((root / "summary.json").read_text())
        manifest = json.loads((root / "manifest.json").read_text())
        exact_paths = [REPO / reference["path"] for reference in manifest["exact_sources_not_passed_to_search"]]
        champions, exact, _ = B.load_truth(exact_paths)
        cases = B.rows(root / "candidates-used.jsonl")
        case_map = {(x["m"], x["key"]): x for x in cases}
        records_by_config = {config["id"]: B.rows(root / config["id"] / "records.jsonl")
                             for config in summary["configurations"]}
        rule = manifest["crowding_rule"]
        metric_args = (rule["band_below_largest_finite_upper"], rule["minimum_count"], rule["minimum_pool_fraction"])
        summary["metrics"] = [metric for config in summary["configurations"] for metric in
            B.pool_metrics(cases, records_by_config[config["id"]], champions, exact, config, *metric_args)]
        comparisons = B.comparison_rows(cases, summary["configurations"], records_by_config, summary["metrics"])
        summary["portfolio_metrics"] = []
        baseline = summary["configurations"][0]
        for comparison, config in zip(comparisons, summary["configurations"][1:]):
            portfolio_config = {**config, "id": baseline["id"] + "+" + config["id"], "k": [baseline["k"], config["k"]]}
            summary["portfolio_metrics"] += B.pool_metrics(cases, comparison["portfolio"], champions, exact,
                                                          portfolio_config, *metric_args)
        summary["analysis_driver"] = B.reference(REPO / "scripts/family1_adaptive_finder_benchmark.py")
        summary["portfolio_work_definition"] = "sum all native node/window costs of baseline plus treatment; chosen-witness-only cost is separate"
        B.save(root / "summary.json", summary)
        source_runs.append({"manifest": B.reference(root / "manifest.json"),
                            "summary": B.reference(root / "summary.json"),
                            "driver_snapshot": B.reference(root / "driver-source.py"),
                            "native_executable": manifest["executable"],
                            "truth_sources": summary["truth_sources"],
                            "candidate_pools": manifest["pools"]})
        for config in summary["configurations"]:
            records = records_by_config[config["id"]]
            audit = json.loads((root / config["id"] / "run-audit.json").read_text())
            assert audit["records"]["sha256"] == B.digest(root / config["id"] / "records.jsonl")
            compact, replays = [], 0
            for record in records:
                assert record["k"] == config["k"] and record["score"] == config["score"]
                assert record["startup"] == "divergence" and record["common_depth"] == config["common_depth"]
                assert record["alphabet"] == B.ALPHABET and record["deterministic"] is True
                identity = record["m"], record["key"]
                pair = record["witness"]
                trace = B.scalar_trace(record["canonical_table"], pair) if pair else None
                if pair:
                    assert trace == record["witness_metric_trace"]
                    replays += 1 << record["m"]
                winner = identity in champions
                winning = record.get("winning_attempt") or {}
                row = {"m": record["m"], "key": record["key"],
                       "pools": ";".join(case_map[identity]["pools"]),
                       "k": config["k"], "window_kind": "joint-pair", "alphabet": "00;01;10;11",
                       "startup": "divergence", "common_depth": config["common_depth"], "score": config["score"],
                       "beam_width": config["beam"], "diagonal_width": 0, "unequal_width": 0,
                       "max_length": config["max_length"], "expansion_cap_per_attempt": config["expansions"],
                       "reference_H": exact.get(identity), "reference_global_H": B.GLOBAL_H[record["m"]],
                       "true_champion": winner, "upper_bound": record["upper_bound"],
                       "miss_unresolved": pair is None,
                       "gap_to_exact_H": record["upper_bound"] - exact[identity] if pair and identity in exact else None,
                       "witness_first": pair[0] if pair else None, "witness_second": pair[1] if pair else None,
                       "D_trace": json.dumps(trace, separators=(",", ":")) if pair else None,
                       "synchronized_trace": json.dumps(record["synchronized_count_trace"], separators=(",", ":")) if pair else None,
                       "first_difference_position": record.get("first_difference_position"),
                       "winning_start_common_prefix": winning.get("common_prefix"),
                       "winning_start_orientation": winning.get("orientation"),
                       "first_greedy_depth": winning.get("first_greedy_depth"),
                       "attempts": record["attempts"], "expanded_nodes": record["expanded_nodes"],
                       "complete_windows": record["complete_windows"], "partial_windows": record["partial_windows"],
                       "expansion_limit_reached": record["expansion_limit_reached"],
                       "length_limit_reached": record["length_limit_reached"],
                       "minimality_certified_by_finder": False}
                compact.append(row)
                if winner:
                    winners.append({"configuration": config["id"], **row})
            assert len(compact) == len(cases)
            output = OUT / f"cases-{config['id']}.csv"
            csv_file(output, compact)
            public_files.append({"configuration": config, "cases": len(compact),
                                 "native_records": B.reference(root / config["id"] / "records.jsonl"),
                                 "public_cases": B.reference(output)})
            verification.append({"configuration": config["id"], "k": config["k"], "case_count": len(compact),
                "positive_count": sum(not row["miss_unresolved"] for row in compact),
                "miss_count": sum(row["miss_unresolved"] for row in compact),
                "scalar_final_mask_replays_at_publication": replays,
                "scalar_final_and_improvement_mask_replays_at_run": audit["scalar_mask_replays_final_and_improvements"],
                "expanded_nodes": sum(row["expanded_nodes"] for row in compact),
                "complete_windows": sum(row["complete_windows"] for row in compact),
                "partial_windows": sum(row["partial_windows"] for row in compact),
                "expansion_capped_graphs": sum(row["expansion_limit_reached"] for row in compact),
                "run_wall_seconds": audit["wall_seconds_this_invocation"],
                "run_sum_subprocess_seconds": audit["subprocess_seconds_this_invocation"]})
        summaries.append({"source": str(root.relative_to(REPO)), "joint_ks": summary["joint_ks"],
                          "candidate_count": summary["candidate_count"], "query_count": summary["query_count"],
                          "metrics": summary["metrics"], "portfolio_metrics": summary["portfolio_metrics"],
                          "delta_summary": summary["deltas"], "crowding_rule": manifest["crowding_rule"]})
        for config in summary["configurations"][1:]:
            all_deltas.extend(B.rows(root / f"deltas-{config['id']}.jsonl"))
    csv_file(OUT / "true-champion-results.csv", winners)
    csv_file(OUT / "per-case-deltas.csv", all_deltas)
    csv_file(OUT / "work-and-verification.csv", verification)
    public_files.extend(B.reference(OUT / name) for name in
                        ["true-champion-results.csv", "per-case-deltas.csv", "work-and-verification.csv"])
    result = {"schema": 1, "joint_ks": sorted({x["k"] for x in verification}),
        "deterministic": True, "alphabet": B.ALPHABET,
        "source_runs": source_runs, "public_artifacts": public_files, "runs": summaries,
        "total_case_queries": sum(x["case_count"] for x in verification),
        "total_positive_cases": sum(x["positive_count"] for x in verification),
        "total_unresolved_misses": sum(x["miss_count"] for x in verification),
        "total_expanded_nodes": sum(x["expanded_nodes"] for x in verification),
        "total_complete_windows": sum(x["complete_windows"] for x in verification),
        "total_partial_windows": sum(x["partial_windows"] for x in verification),
        "total_expansion_capped_graphs": sum(x["expansion_capped_graphs"] for x in verification),
        "total_run_wall_seconds": sum(x["run_wall_seconds"] for x in verification),
        "independent_scalar_replay": True, "all_supplied_cases_tested_in_every_declared_configuration": True,
        "truth_scores_not_passed_to_search": True, "misses_are_unresolved_and_never_champions_or_exclusions": True,
        "rank_shortlist_is_diagnostic_never_an_exclusion_rule": True,
        "audit_bound_safe_shortlist_rule": "retain missing bounds and verified L >= exhaustive global H; exclude only L < H",
        "audit_bound_safe_rule_needs_a_certified_incumbent_lower_bound_in_an_unknown_size": True,
        "m7_nonwinner_truth": "The 55-row near-top pool has 8 exact winners and 47 certified nonwinners (H<=33), whose exact H is not asserted.",
        "pool_scope": "Full rooted universes through m4; all saved near-top rows m5/6/7. Larger pools are intentionally enriched, not global samples.",
        "runtime_scope": "Observed time, no search deadlines; configurations use fixed expansion caps per start.",
        "publication_source": B.reference(__file__)}
    B.save(OUT / "summary.json", result)
    print(json.dumps({"joint_ks": result["joint_ks"], "case_queries": result["total_case_queries"],
                      "positive_cases": result["total_positive_cases"], "unresolved": result["total_unresolved_misses"],
                      "output": str(OUT)}))


if __name__ == "__main__":
    main()

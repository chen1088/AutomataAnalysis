#!/usr/bin/env python3
"""Score complete sealed edit pools, then audit deterministic adaptive policies.

The scorer receives only tables and a fixed finder configuration. Exhaustive
champion labels are opened after every requested scoring run has been sealed.
All pairs, misses, and complete-window work counts survive in the native files.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import shutil

REPO = Path(__file__).resolve().parents[1]


def frozen_helper(out):
    source = REPO / "scripts/family1_adaptive_finder_benchmark.py"
    archive = out / "finder-driver-source.py"
    if not archive.exists():
        shutil.copy2(source, archive)
    spec = importlib.util.spec_from_file_location("frozen_adaptive_finder", archive)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.REPO = REPO
    return module


def load_pool_cases(helper, args):
    """Only geometry/generation fields, never scores or witnesses."""
    pool_specs, cases, seals = {}, {}, []
    for selection in ("winners", "near2"):
        folder = args.edit / f"m{args.m}-{selection}-r{args.radius}"
        seal_path = folder / "seal.json"
        seal = json.loads(seal_path.read_text())
        path = folder / "candidates.jsonl"
        assert seal["generation_complete"] is True and seal["randomness"] is False
        assert seal["candidates"]["sha256"] == helper.digest(path)
        seals += [helper.reference(path), helper.reference(seal_path)]
        values = helper.rows(path)
        seen = set()
        for value in values:
            table, key = value["canonical_table"], value["key"]
            assert len(table) == args.m and helper.table_key(table) == key and key not in seen
            seen.add(key)
            case = cases.setdefault(key, {"m": args.m, "key": key, "canonical_table": table,
                                          "shape_key": value["shape_key"], "pools": []})
            assert case["canonical_table"] == table and case["shape_key"] == value["shape_key"]
            case["pools"].append(selection + "-allroots")
            if value["root_fixed"]:
                case["pools"].append(selection + "-fixedroot")
        assert len(values) == seal["candidates_all_roots"]
        assert sum(value["root_fixed"] for value in values) == seal["candidates_root_fixed"]
        pool_specs[selection] = seen
    assert pool_specs["winners"] <= pool_specs["near2"]
    return [cases[key] for key in sorted(cases)], seals


def bound_metrics(cases, results, champions, maximum, config, band, tau):
    found = {key: row for key, row in results.items() if row["upper_bound"] is not None}
    upper = {key: row["upper_bound"] for key, row in found.items()}
    allkeys = {case["key"] for case in cases}
    winners = allkeys & champions
    finite_compatible = {key for key, length in upper.items() if length >= maximum}
    unresolved = allkeys - upper.keys()
    compatible = finite_compatible | unresolved
    excluded = allkeys - compatible
    assert not excluded & champions
    top = max(upper.values()) if upper else None
    shortlist = {key for key, length in upper.items() if length >= top - band} if top is not None else set()
    shapes = {case["key"]: case["shape_key"] for case in cases}
    return {
        "m": cases[0]["m"], "queries": len(cases), "configuration": config,
        "k": sorted({row["k"] for row in results.values()}),
        "full_joint_alphabet": ["00", "01", "10", "11"],
        "winner_count_in_pool": len(winners), "winner_recall": len(winners) / len(champions),
        "all_exhaustive_winners": len(champions), "certified_global_maximum": maximum,
        "finite_verified_pairs": len(upper), "unresolved_no_pair": len(unresolved),
        "reference_cutoff": {
            "rule": "survive iff no verified pair or best verified upper >= certified global maximum",
            "survivors": len(compatible), "true_winners": len(compatible & champions),
            "finite_compatible": len(finite_compatible),
            "finite_false_apparent_champions": len(finite_compatible - champions),
            "unresolved_nonwinners": len(unresolved - champions),
            "false_survivors": len(compatible - champions),
            "finite_champion_precision": len(finite_compatible & champions) / len(finite_compatible) if finite_compatible else None,
            "survivor_champion_precision": len(compatible & champions) / len(compatible) if compatible else None,
            "witness_excluded_nonwinners": len(excluded),
        },
        "operational_topband": {
            "rule": "finite verified upper >= maximum finite upper - band; preserve every tie",
            "band": band, "maximum_finite_upper": top,
            "size": len(shortlist), "shapes": len({shapes[key] for key in shortlist}),
            "true_winners": len(shortlist & champions), "false_apparent_champions": len(shortlist - champions),
            "winner_recall_global": len(shortlist & champions) / len(champions),
            "winners_in_pool_outside_topband": len(winners - shortlist),
            "finite_winners_outside_topband": len((winners & upper.keys()) - shortlist),
            "unresolved_winners": len(winners & unresolved),
            "crowding_threshold": tau, "crowding_triggered": len(shortlist) >= tau,
            "misses_are_not_in_the_finite_topband": True,
        },
        "expanded_nodes": sum(row.get("expanded_nodes", 0) for row in results.values()),
        "complete_windows": sum(row.get("complete_windows", 0) for row in results.values()),
        "partial_windows": sum(row.get("partial_windows", 0) for row in results.values()),
        "expansion_capped_graphs": sum(row.get("expansion_limit_reached", False) for row in results.values()),
        "actual_H_not_inferred_from_upper_or_miss": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m", type=int, default=7)
    parser.add_argument("--radius", type=int, default=1)
    parser.add_argument("--edit", type=Path, default=REPO / "out/family1-adaptiveness-20261026/edit/sealed-pools")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/joint-solid-linux/Family1Joint")
    parser.add_argument("--configs", nargs="+", default=["total:2", "total:4", "permutation:4"])
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--common-depth", type=int, default=2)
    parser.add_argument("--beam", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=80)
    parser.add_argument("--expansions", type=int, default=2000000)
    parser.add_argument("--band", type=int, default=2)
    parser.add_argument("--tau", type=int, default=3)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--score-only", action="store_true", help="Seal queries without opening target labels")
    args = parser.parse_args()
    args.out, args.edit, args.exe = args.out.resolve(), args.edit.resolve(), args.exe.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    helper = frozen_helper(args.out)
    cases, seals = load_pool_cases(helper, args)
    configs = []
    for token in args.configs:
        score, _, k = token.partition(":")
        assert score in ("total", "permutation") and 1 <= int(k) <= 8
        configs.append({"id": f"{score}-c{args.common_depth}-k{k}", "score": score, "k": int(k),
                        "common_depth": args.common_depth, "beam": args.beam,
                        "max_length": args.max_length, "expansions": args.expansions})
    assert len({config["id"] for config in configs}) == len(configs)
    manifest = {"m": args.m, "radius": args.radius, "cases": len(cases), "configs": configs,
                "sources": seals, "finder_helper": helper.reference(args.out / "finder-driver-source.py"),
                "driver": helper.reference(__file__), "executable": helper.reference(args.exe),
                "alphabet": helper.ALPHABET, "search_randomness": False,
                "query_inputs": "canonical tables and fixed configuration only",
                "every_candidate_scored_in_every_configuration": True}
    manifest_path = args.out / "manifest.json"
    if manifest_path.exists():
        assert args.resume and json.loads(manifest_path.read_text()) == manifest
    else:
        assert not args.resume
        helper.save(manifest_path, manifest)
        helper.save_rows(args.out / "candidates-used.jsonl", cases)
    query_results = {}
    for config in configs:
        records = helper.run_config(args, cases, config, manifest["executable"]["sha256"])
        query_results[config["id"]] = {row["key"]: row for row in records}
    helper.save(args.out / "query-seal.json", {"manifest": helper.reference(manifest_path),
                 "records": [helper.reference(args.out / config["id"] / "records.jsonl") for config in configs],
                 "all_configurations_and_candidates_completed": True,
                 "target_truth_opened_during_scoring": False})
    if args.score_only:
        return
    # Exact target references are read only after the query seal above.
    champions_all, _, truth_sources = helper.load_truth([])
    champions = {key for m, key in champions_all if m == args.m}
    maximum = helper.GLOBAL_H[args.m]
    metrics = []
    for pool in sorted({pool for case in cases for pool in case["pools"]}):
        selected = [case for case in cases if pool in case["pools"]]
        for config in configs:
            result = {case["key"]: query_results[config["id"]][case["key"]] for case in selected}
            value = bound_metrics(selected, result, champions, maximum, config, args.band, args.tau)
            value["pool"] = pool
            metrics.append(value)
    # Retain every previously verified upper: refinement failure never erases evidence.
    baseline = configs[0]
    portfolios = []
    for treatment in configs[1:]:
        combined = {}
        for case in cases:
            key = case["key"]
            base, extra = query_results[baseline["id"]][key], query_results[treatment["id"]][key]
            positives = [row for row in (base, extra) if row["upper_bound"] is not None]
            best = min(positives, key=lambda row: (row["upper_bound"], row["witness"])) if positives else base
            combined[key] = dict(best)
            combined[key]["expanded_nodes"] = base["expanded_nodes"] + extra["expanded_nodes"]
            combined[key]["complete_windows"] = base["complete_windows"] + extra["complete_windows"]
            combined[key]["partial_windows"] = base["partial_windows"] + extra["partial_windows"]
            combined[key]["expansion_limit_reached"] = base["expansion_limit_reached"] or extra["expansion_limit_reached"]
        for pool in sorted({pool for case in cases for pool in case["pools"]}):
            selected = [case for case in cases if pool in case["pools"]]
            result = {case["key"]: combined[case["key"]] for case in selected}
            config = {"id": baseline["id"] + "+" + treatment["id"], "retain_minimum_upper": True,
                      "joint_k_used": [baseline["k"], treatment["k"]], "runs": [baseline, treatment]}
            value = bound_metrics(selected, result, champions, maximum, config, args.band, args.tau)
            value["pool"] = pool
            value["k"] = sorted({baseline["k"], treatment["k"]})
            portfolios.append(value)
    helper.save_rows(args.out / "metrics.jsonl", metrics)
    helper.save_rows(args.out / "portfolio-metrics.jsonl", portfolios)
    summary = {"m": args.m, "k": [config["k"] for config in configs], "window": "full four-symbol joint",
               "candidate_count": len(cases), "configurations": configs,
               "all_candidates_scored": True, "truth_sources": truth_sources,
               "certified_maximum": maximum, "complete_champion_count": len(champions),
               "metrics": metrics, "retained_upper_portfolios": portfolios,
               "limits": ["Verified witness lengths are upper bounds; misses are unresolved.",
                          "m7 nonwinner labels imply H<=33, not exact nonwinner gaps.",
                          "A global rarity rate is not the null rate in an enriched edit pool.",
                          "Threshold tau3 is diagnostic, not a calibrated champion count test."],
               "query_seal": helper.reference(args.out / "query-seal.json")}
    helper.save(args.out / "summary.json", summary)
    print(json.dumps({"m": args.m, "joint_k": summary["k"], "candidates": len(cases),
                      "configurations": len(configs), "summary": str(args.out / "summary.json")}), flush=True)


if __name__ == "__main__":
    main()

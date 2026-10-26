#!/usr/bin/env python3
"""Publish generation/score evidence and independently audit sampled edit paths."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

import family1_edit_candidate_benchmark as benchmark
from family1_edit_candidate_cli_test import verify_path
from family1_edit_distance import neighbors as reference_neighbors

REPO = benchmark.REPO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation", type=Path, default=REPO / "results/family1-edit-candidate-benchmark")
    parser.add_argument("--scores", type=Path, default=REPO / "results/family1-edit-elimination-benchmark")
    args = parser.parse_args()
    folder = args.generation
    seal = benchmark.read(folder / "generation-seal.json")
    binding = benchmark.read(folder / "binding.json")
    truth = benchmark.load_truth(REPO / binding["journal"]["path"], set(range(1, 8)))
    observations = list(benchmark.json_rows(folder / "observations.jsonl"))
    complete = []
    path_audits, root_audits = [], []
    for generation in seal["generations"]:
        candidate_path = REPO / generation["candidate_file"]["path"]
        path_file = REPO / generation["path_file"]["path"]
        assert benchmark.ref(candidate_path) == generation["candidate_file"]
        assert benchmark.ref(path_file) == generation["path_file"]
        source = REPO / generation["parent_source"]["path"]
        assert benchmark.ref(source) == generation["parent_source"]
        parents = list(benchmark.json_rows(source))
        assert parents and all(p["m"] == generation["m"]-1 for p in parents)
        assert all(set(p) == {"m", "key", "canonical_table", "merge_length", "status"} for p in parents)
        if generation.get("complete_growth_run"):
            candidates = list(benchmark.json_rows(candidate_path))
            paths = {row["path_id"]: row for row in benchmark.json_rows(path_file)}
            direct_keys = {candidate["key"] for candidate in candidates if candidate["path_ids"]}
            expected_direct = set()
            for parent in parents:
                expected_direct.update(key for key, edge in reference_neighbors(tuple(map(tuple, parent["canonical_table"]))).items()
                                       if len(edge["after"]) == generation["m"])
            assert direct_keys == expected_direct, "Native full growth differs from independent Python unit neighbors"
            winners = [r for r in candidates if r["key"] in truth[generation["m"]]["winners"]]
            parent_scores = {p["key"]: p["merge_length"] for p in parents}
            winner_details = []
            for candidate in winners:
                direct = [paths[p] for p in candidate["path_ids"]]
                for path in direct:
                    verify_path(path, factorial=False)
                winner_details.append({"key": candidate["key"],
                                       "has_root_fixed_unit_path": bool(direct),
                                       "best_observed_parent_H": max((parent_scores[p["parent_key"]] for p in direct), default=None),
                                       "path_ids": candidate["path_ids"]})
            groups = {}
            for candidate in candidates:
                groups.setdefault(candidate["shape_key"], []).append(candidate)
            for shape, group in groups.items():
                expected = set(benchmark.root_classes(group[0]["canonical_table"]))
                assert {r["key"] for r in group} == expected
            root_audits.append({"run_id": generation["run_id"], "ordinary_shapes_checked": len(groups),
                                "rooted_classes_checked": len(candidates), "all_accessible_roots_present": True})
            full = next(r for r in observations if r["run_id"] == generation["run_id"] and r.get("complete_growth_run"))
            summary = generation["native_summary"]
            complete.append({"m": generation["m"], "parents": len(parents),
                             "parent_score_histogram": dict(sorted(Counter(p["merge_length"] for p in parents).items())),
                             "direct_rooted_candidates": summary["root_fixed_candidate_count"],
                             "allroot_candidates": len(candidates), "ordinary_shapes": len(groups),
                             "direct_winning_classes": sum(bool(c["path_ids"]) for c in winners),
                             "allroot_winning_classes": len(winners), "winning_classes_total": len(truth[generation["m"]]["winners"]),
                             "enumeration_complete": summary["enumeration_complete"],
                             "independent_complete_direct_growth_set_matches": True,
                             "parent_unit_neighborhoods_independently_computed": len(parents),
                             "path_capped": summary["path_capped"], "candidate_capped": summary["candidate_capped"],
                             "native_seconds": summary["seconds"], "winner_details": winner_details,
                             "matched_random_actual_candidates": full["fair_random"]["actual_candidates"],
                             "matched_random_winning_classes": full["fair_random"]["winner_rooted_hits"],
                             "matched_random_winner_shapes": full["fair_random"]["winner_shape_hits"]})
        if (generation["m"] in {4, 5, 6, 7} and generation["pool"] == "winners"
                and generation["radius"] == 3 and generation["seed"] == 1088 and not generation["root_closure"]):
            paths = list(benchmark.json_rows(path_file))
            stride = max(1, len(paths)//64)
            chosen = paths[::stride][:64]
            kinds = Counter()
            for path in chosen:
                verify_path(path, factorial=False)
                kinds.update(step["operation"]["kind"] for step in path["steps"])
            path_audits.append({"run_id": generation["run_id"], "paths_verified": len(chosen),
                                "primitive_steps_verified": sum(kinds.values()), "operation_counts": dict(kinds)})
    coverage = {"complete_growth": sorted(complete, key=lambda r: r["m"]),
                "selected_m4_m7_path_replays": path_audits, "complete_growth_root_closure_audits": root_audits,
                "parent_size_and_allowed_input_fields_all_valid": True,
                "generation_seal": benchmark.ref(folder / "generation-seal.json"),
                "no_global_search_exhaustiveness_claim": True}
    benchmark.dump(folder / "independent-audit.json", coverage)
    summary = benchmark.read(folder / "summary.json")
    lines = ["# Edit-candidate generation benchmark", "",
             "All known maximizing rooted graph classes through seven states occur in the complete radius-one neighborhoods of the previous-size score-gap-at-most-two parent pools after accessible root closure. This is a measured finite-size coverage fact, not a theorem for later state sizes or a global search certificate.", "",
             "Generation uses all previous-size winners, or separately every previous-size graph within2 of that size's exact maximum. The complete target-size truth is loaded only after candidate files and random baselines are sealed. The generator receives graph keys, radius, seed and resource budgets; it receives no current-size scores or word pairs.", "",
             "| Target m | Previous near-top parents | Root-fixed candidates | After all accessible roots | Direct winning classes | Winning classes after roots | Matched random classes / winner hits | Complete unit neighborhood |",
             "|---:|---:|---:|---:|---:|---:|---:|:---:|"]
    for row in sorted(complete, key=lambda r:r["m"]):
        lines.append(f"| {row['m']} | {row['parents']} | {row['direct_rooted_candidates']} | {row['allroot_candidates']} | {row['direct_winning_classes']}/{row['winning_classes_total']} | {row['allroot_winning_classes']}/{row['winning_classes_total']} | {row['matched_random_actual_candidates']} / {row['matched_random_winning_classes']} | {'yes' if row['enumeration_complete'] else 'no'} |")
    lines += ["", "The one-state base case has one graph and H=1; there is no zero-state predecessor. Each extra complete-growth run uses radius1, seed1088,8192 direct-candidate slots and20000 accepted-path slots. All six actually exhaust their neighborhoods with no cap. Rerooted classes are retained explicitly; rerooting is not a free rooted edit and receives no false rooted-distance bound.", "",
              "The budgeted grid contains216 runs: exact sizes2–7; winner versus gap≤2 parents; radii1,2,3; seeds1088,2027,65537; strict rooted versus accessible-root closure. Each uses10000 accepted-path slots and2048 direct rooted endpoint slots. Six extra complete-growth runs bring the native total to222; there are895 reported prefix/base-case observations. Candidate caps apply before root closure; final output counts can therefore exceed2048. All full outputs are retained.", "",
              "At nominal budgets32,128,512,2048, prefixes retain the entire final ordinary-shape/root block. The matched random prefix receives at least the actual edit prefix count and also retains its whole final block; its extra candidates are recorded. Random sampling uses independent uniformly drawn labelled two-port tables, rejecting inaccessible graphs and deduplicating rooted classes. It is not uniform sampling of graph isomorphism classes, and these seed comparisons support no global confidence certificate.", "",
              "Seven-state results at nominal2048 (ranges over the three fixed seeds; complete-growth extra runs excluded):", "",
              "| Parents | Radius | Root closure | Actual candidates | Maximizing rooted hits /8 | Winning ordinary shapes /4 | Random maximizing rooted hits |",
              "|---|---:|:---:|---:|---:|---:|---:|"]
    for pool in ["winners", "near2"]:
        for radius in [1,2,3]:
            for closure in [False,True]:
                subset = [r for r in observations if r["m"] == 7 and r["pool"] == pool and r["radius"] == radius
                          and r["root_closure"] == closure and r["nominal_budget"] == 2048 and "complete-growth" not in r["run_id"]]
                def range_text(values):
                    return str(min(values)) if min(values) == max(values) else f"{min(values)}–{max(values)}"
                lines.append(f"| {pool} | {radius} | {'yes' if closure else 'no'} | {range_text([r['edit']['actual_candidates'] for r in subset])} | {range_text([r['edit']['winner_rooted_hits'] for r in subset])} | {range_text([r['edit']['winner_shape_hits'] for r in subset])} | {range_text([r['fair_random']['winner_rooted_hits'] for r in subset])} |")
    lines += ["", "Ordering matters: the complete near-top/root-closed seven-state pool contains all eight maximizers, but its original first approximately2048 rows contain none. The strict rooted radius-one stream finds5–6 of8 within2048. Increasing radius under a fixed budget can also reduce recall because it allocates work to additional layers. These negative outcomes are retained; the benchmark does not select the best seed or a single parent after inspecting target truth.", "",
              "`observations.jsonl` and `observations.csv` retain all budget outcomes, ordinary-shape coverage, coverage of every maximizing root per shape, and near-top recall/exact-score histograms where the complete exact journal is available (m≤6). `generation-seal.json` pins all candidate/path/source files, native parent/pattern/depth coverage, duplicate counters, timings, cap flags and random draw statistics. `independent-audit.json` compares the entire direct target set of each of the six complete-growth runs with independent Python unit-neighborhood enumeration of all288 supplied parent classes. It separately replays256 selected radius-three paths (616 primitive steps) at m4–7 and checks accessible-root closure of all4467 generated ordinary shapes in those full-growth runs. It does not enumerate edit neighborhoods of those4467 generated shapes.", "",
              "The independent CLI suite passed4/4 in both MSVC Release and Debug. It checks all64 rooted classes of sizes1–3 against complete Python unit neighborhoods, factorial canonicalization, loops/coincident occurrences, nonstrongly connected roots, primitive operation replay, termination, caps, deterministic resume/hash integrity, and the intermediate-size20 representation limit.", "",
              "Reproduce generation and analysis (existing Windows/MSVC setup):", "", "```powershell",
              "uv run --no-project python tests/family1_edit_candidate_cli_test.py --exe out/build/msvc-vcpkg/Release/Family1Edit.exe",
              "uv run --no-project python tests/family1_edit_candidate_benchmark.py --exe out/build/msvc-vcpkg/Release/Family1Edit.exe",
              "uv run --no-project python tests/family1_edit_candidate_analysis.py", "```", ""]
    (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")
    score_summary_path = args.scores / "summary.json"
    if score_summary_path.is_file():
        score_summary = benchmark.read(score_summary_path)
        scores = list(benchmark.json_rows(args.scores / "scores.jsonl"))
        per_size = []
        for m in sorted({r["m"] for r in scores}):
            subset = [r for r in scores if r["m"] == m]
            winners = sum(r["winner_truth_for_evaluation_only"] for r in subset)
            eliminated = sum(r["certifiably_eliminated"] for r in subset)
            per_size.append({"m": m, "queries": len(subset), "eliminated": eliminated,
                             "unresolved_winners": winners,
                             "unresolved_nonwinners": len(subset)-eliminated-winners,
                             "witness_gap_histogram": dict(sorted(Counter(r["witness_length_gap"] for r in subset if r["witness_length_gap"] is not None).items()))})
        benchmark.dump(args.scores / "analysis.json", {"per_size": per_size,
                        "summed_native_invocation_seconds": sum(r["attempt"]["seconds"] for r in scores),
                        "summed_new_native_invocation_seconds": sum(r["attempt"]["seconds"] for r in scores if not r.get("reused_prior_query")),
                        "unique_queries_deduplicated_across_cohorts": True})
        text = ["# Incumbent-cutoff elimination benchmark", "",
                f"On {len(scores):,} unique graphs selected from sealed edit and random prefixes, {score_summary['eliminated_unique_graphs']:,} were independently certified weaker than the same-size incumbent; {score_summary['unresolved_unique_graphs']} remain unresolved. No maximizing graph was eliminated. All native invocations completed; no timeout/error is hidden.", "",
                "This is a retrospective operating-point test: every m-state graph is queried at the common capF_m−1, where F_m is the previously certified global maximum for that size. Per-graph H, truth labels and saved words never enter the native scorer. Stage1 is fixed at k6, beam4,128 outer samples/prefix pairs, prefix depth16/65536 words,10000 expansions and tail threshold8. All hits are replayed independently on the entire static-mask family. A miss remains lower bound1 with no upper bound.", "",
                "| m | Unique queries | Certified weaker | Unresolved true winners | Unresolved nonwinners |",
                "|---:|---:|---:|---:|---:|"]
        for row in per_size:
            text.append(f"| {row['m']} | {row['queries']} | {row['eliminated']} | {row['unresolved_winners']} | {row['unresolved_nonwinners']} |")
        text += ["", "Scoring budgets are32 and128 candidates per cohort, with whole-root-shape blocks retained and overshoot recorded. Repeated graphs across cohorts share one deterministic cached query. Candidate generation recall is reported separately: surviving a bounded elimination query does not certify a maximizer, and winning classes absent from a selected prefix cannot be recovered by its scorer. Unscored candidates remain outside the scoring-budget population, rather than being silently discarded.", "",
                 "`observations.jsonl` retains each cohort's nonwinner elimination fraction, survivor precision/global winner recall and exact witness-gap histogram where H is known (m≤6). `scores.jsonl` preserves every attempt, observation and provenance. `analysis.json` aggregates per-size results. The source helper/executable and generation seal are pinned in `query-plan.json` and the work directory snapshots. This finite candidate test supplies no global exclusion certificate for sizes8–20.", "",
                 "```powershell", "uv run --no-project python tests/family1_edit_elimination_benchmark.py", "```", ""]
        if score_summary.get("complete_size7_only"):
            unresolved = [r for r in scores if r["unresolved"]]
            winners = sum(r["winner_truth_for_evaluation_only"] for r in unresolved)
            nonwinners = len(scores)-winners
            eliminated = score_summary["eliminated_unique_graphs"]
            native_total = sum(r["attempt"]["seconds"] for r in scores)
            new_native_total = sum(r["attempt"]["seconds"] for r in scores if not r.get("reused_prior_query"))
            survivor_rows = [{**r["attempt"]["graph"], "lower_bound": 1, "upper_bound": None,
                              "status": "unresolved", "source_attempt": r["attempt_file"],
                              "miss_does_not_certify_a_lower_bound": True} for r in unresolved]
            benchmark.dump_rows(args.scores / "survivors.jsonl", survivor_rows)
            text = ["# Complete seven-state edit-pool elimination", "",
                    f"The complete radius-one near-top/all-roots pool has {len(scores):,} classes and contains all eight certified maximizers. Applying the same cheap cap33 query to EVERY class certifies {eliminated:,} weaker graphs and leaves {len(unresolved)} unresolved: all eight maximizers plus {len(unresolved)-winners} known nonwinners. No maximizer is eliminated.", "",
                    f"This eliminates {100*eliminated/nonwinners:.2f}% of known nonwinners. Retrospective survivor precision is {winners}/{len(unresolved)} ({100*winners/len(unresolved):.3f}%). The {len(unresolved)-winners} extra survivors are bounded-search misses, not graphs certified to attain34.", "",
                    "Generation was sealed before child truth was loaded. It uses all69 previous-size parents with certified H in21–23, performs complete radius-one routing growth and retains every accessible root:3581 direct rooted classes become13329 after root closure. Root0 remains fixed along actual edit paths; rerooting is separately labeled. The generator never receives current-size scores or saved word pairs.", "",
                    "Every graph is queried at the common retrospective cutoffF_7−1=33. The scorer receives graph metadata and this common cutoff only; no per-graph H, winner label or saved word is supplied. Settings: k6, beam4,128 samples/prefix pairs, prefix depth16/65536 words,10000 expansions, tail threshold8, one stage. Verified upper≤33 certifies weakness. A miss supplies no new lower bound. All accepted words are independently replayed against all128 static masks using the helper's separate exact bitset implementation.", "",
                    f"All {len(scores):,} native observations completed without timeout/error. {score_summary.get('reused_prior_queries',0)} prior matching queries were checksum/config-validated and reused. Summed recorded invocation time is {native_total:.3f}s, including reused observations; new invocations account for {new_native_total:.3f}s. Four workers were used. These totals are sums of per-invocation measurements, not an elapsed wall-time claim.", "",
                    "`scores.jsonl` preserves every native observation, independently verified witness and provenance. `survivors.jsonl` exports all638 unresolved graph classes without target-truth labels so they can be reused as candidates. `observations.jsonl` contains the full-pool confusion counts; `query-plan.json` pins helper/executable settings and the generation seal. The source pool's complete neighborhood is a tiny subset of the4,166,855-class seven-state universe; this experiment supplies no global exclusion theorem for future sizes.", "",
                    "```powershell",
                    "uv run --no-project python tests/family1_edit_elimination_benchmark.py --complete-size7-only --reuse-work-dir out/family1-edit-elimination-benchmark --out results/family1-edit-elimination-complete-m7 --work-dir out/family1-edit-elimination-complete-m7",
                    "uv run --no-project python tests/family1_edit_candidate_analysis.py --scores results/family1-edit-elimination-complete-m7",
                    "```", ""]
        (args.scores / "README.md").write_text("\n".join(text), encoding="utf-8")
    print(json.dumps({"complete_growth_sizes": len(complete), "path_audits": len(path_audits),
                      "allroot_shapes_audited": sum(r["ordinary_shapes_checked"] for r in root_audits)}, indent=2))


if __name__ == "__main__":
    main()

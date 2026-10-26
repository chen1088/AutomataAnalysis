#!/usr/bin/env python3
"""Bounded, resumable edit/rank/upper-witness screening at every size8..20.

This forwards a limited frontier without deleting unselected observations.
Every upper certificate is independently checked by the general scorer. A
surviving graph is a potential challenger, not a proved high-score graph.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write(path, value):
    data = (json.dumps(value, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Saved materialized input differs: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def graph_key(row):
    return "".join(f"{target:02d}" for edge in row["canonical_table"] for target in edge)


def save_rows(path, values):
    data = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in values).encode()
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f"Saved parent frontier differs: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)


def invoke(command, log):
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
    log.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Pipeline command failed ({result.returncode}); see {log}: {result.stderr[-1000:]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--edit-exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Edit.exe")
    parser.add_argument("--finder-exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--seeds", type=Path, default=REPO / "results/family1-neighbor-seeds/near-top.jsonl")
    parser.add_argument("--baseline-bounds", type=Path, default=REPO / "results/family1-edit-priority/root-lift-candidates.jsonl")
    parser.add_argument("--min-m", type=int, default=8)
    parser.add_argument("--max-m", type=int, default=20)
    parser.add_argument("--radius", type=int, default=3)
    parser.add_argument("--max-paths", type=int, default=4096)
    parser.add_argument("--max-candidates", type=int, default=256)
    parser.add_argument("--score-shapes", type=int, default=2)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--native-timeout", type=int, default=2)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1088)
    parser.add_argument("--incumbent-lower", type=int, default=34)
    parser.add_argument("--parent-margin", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if (not 8 <= args.min_m <= args.max_m <= 20 or args.radius not in (1, 2, 3)
            or min(args.max_paths, args.max_candidates, args.score_shapes, args.jobs, args.native_timeout,
                   args.samples, args.incumbent_lower) < 1 or args.parent_margin < 0):
        parser.error("Require sizes8..20, radius1..3 and positive budgets")
    for name in ("out", "edit_exe", "finder_exe", "seeds", "baseline_bounds"):
        setattr(args, name, getattr(args, name).resolve())
    ranker = REPO / "scripts/family1_rank_edit_candidates.py"
    scorer = REPO / "scripts/family1_graph_candidate_search.py"
    paths = [Path(__file__), ranker, scorer, REPO / "scripts/family1_study.py",
             REPO / "Family1EditSearch.cpp", REPO / "Family1EditSearch.h", REPO / "family1_edit.cpp",
             REPO / "Family1LargeGraph.cpp", REPO / "Family1LargeGraph.h", REPO / "family1_sample.cpp",
             REPO / "HardPairFinder.h", REPO / "HardPairPrefixSeeds.h", REPO / "HardPairViability.h",
             REPO / "Family1PairAgreement.h", REPO / "Family1CliArtifacts.h", args.edit_exe,
             args.finder_exe, args.seeds, args.baseline_bounds]
    settings = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()
                if key not in ("resume", "out")}
    binding = {"schema": 1, "settings": settings,
               "pins": {str(path): digest(path) for path in paths},
               "method": "bounded-edit-frontier-parent-strata-and-upper-witness-screening",
               "no_global_coverage_or_optimality_claim": True}
    if args.out.exists() and any(args.out.iterdir()):
        if not args.resume or json.loads((args.out / "run.json").read_text()) != binding:
            raise ValueError("Use a new output directory, or --resume with identical sources and settings")
    args.out.mkdir(parents=True, exist_ok=True)
    write(args.out / "run.json", binding)
    snapshot = args.out / "sources-used"
    snapshot.mkdir(exist_ok=True)
    for path in paths:
        if path.suffix not in (".exe", ".jsonl") and not (snapshot / path.name).exists():
            shutil.copy2(path, snapshot / path.name)
    seeds, baselines = rows(args.seeds), rows(args.baseline_bounds)
    previous = [row for row in seeds + baselines if row["m"] == args.min_m - 1]
    reports = []
    for m in range(args.min_m, args.max_m + 1):
        directory = args.out / f"m{m}"
        directory.mkdir(exist_ok=True)
        parents = {}
        for row in previous + [row for row in baselines if row["m"] == m - 1]:
            if row["m"] != m - 1:
                continue
            upper = row.get("upper_bound", row.get("merge_length") if row.get("status") == "exact" else None)
            if upper is not None and upper < max(1, args.incumbent_lower - args.parent_margin):
                continue
            key = graph_key(row)
            old = parents.get(key)
            if old is None or row.get("lower_bound", 1) > old.get("lower_bound", 1):
                parents[key] = {**row, "key": key, "selection_scope": "bounded previous frontier or certified construction"}
        if not parents:
            raise ValueError(f"No eligible previous-size parents for {m}")
        parent_file = directory / "parents.jsonl"
        save_rows(parent_file, [parents[key] for key in sorted(parents)])
        generated, ranked, scored = (directory / name for name in ("generated", "ranked", "scored"))
        command = [str(args.edit_exe)]
        for key in sorted(parents):
            command += ["--graph", key]
        command += ["--target-m", str(m), "--radius", str(args.radius), "--max-paths", str(args.max_paths),
                    "--max-candidates", str(args.max_candidates), "--seed", str(args.seed + m), "--root-closure", "--out", str(generated)]
        if (generated / "summary.json").exists():
            command.append("--resume")
        invoke(command, directory / "generation.log")
        command = [sys.executable, str(ranker), "--candidates", str(generated / "candidates.jsonl"),
                   "--paths", str(generated / "paths.jsonl"), "--parents", str(parent_file),
                   "--strategy", "parent-strata", "--seed", str(args.seed), "--out", str(ranked)]
        if (ranked / "run.json").exists():
            command.append("--resume")
        invoke(command, directory / "ranking.log")
        command = [sys.executable, str(scorer), "--candidates", str(ranked / "candidates.jsonl"),
                   "--bounds", str(args.baseline_bounds), "--exe", str(args.finder_exe), "--out", str(scored),
                   "--incumbent-lower", str(args.incumbent_lower), "--max-shapes", str(args.score_shapes),
                   "--jobs", str(args.jobs), "--beam-width", "4", "--memory-mib", "256",
                   "--stage1-samples", str(args.samples), "--stage1-prefix-pairs", str(args.samples),
                   "--stage1-timeout", str(args.native_timeout)]
        if (scored / "run.json").exists():
            command.append("--resume")
        invoke(command, directory / "scoring.log")
        generation = json.loads((generated / "summary.json").read_text())
        scoring = json.loads((scored / "summary.json").read_text())
        plan = json.loads((scored / "plan.json").read_text())
        selected_keys = {root["key"] for shape in plan["shapes"] if shape["selected"] for root in shape["roots"]}
        previous = [row for row in rows(scored / "records.jsonl") if row["m"] == m and row["key"] in selected_keys]
        eliminated_selected = sum(row.get("upper_bound") is not None and row["upper_bound"] < args.incumbent_lower
                                  for row in previous)
        observations = rows(scored / "observations.jsonl")
        outcomes = {}
        for row in observations:
            outcome = row.get("outcome", "unknown")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        report = {"m": m, "parent_rooted_classes": len(parents),
                  "generated_rooted_classes": generation["candidate_count"],
                  "direct_rooted_endpoints": generation["root_fixed_candidate_count"],
                  "generation_complete": generation["enumeration_complete"],
                  "selected_root_classes": len(selected_keys), "all_selected_roots_screened": scoring["all_selected_roots_scored"],
                  "eliminated_recorded_classes": scoring["eliminated_recorded_classes"],
                  "surviving_recorded_classes": scoring["surviving_recorded_classes"],
                  "eliminated_selected_classes": eliminated_selected,
                  "surviving_selected_classes": len(previous) - eliminated_selected,
                  "attempt_outcomes": outcomes,
                  "native_attempts": scoring["native_attempt_count"],
                  "global_maximum_certified": False, "survival_gives_no_lower_bound": True,
                  "generation_summary": {"path": str(generated / "summary.json"), "sha256": digest(generated / "summary.json")},
                  "scoring_summary": {"path": str(scored / "summary.json"), "sha256": digest(scored / "summary.json")}}
        reports.append(report)
        summary = {"schema": 1, "min_m": args.min_m, "max_m": args.max_m, "sizes": reports,
                   "all_requested_sizes_finished": len(reports) == args.max_m - args.min_m + 1,
                   "global_maximum_certified": False, "enumeration_complete": False,
                   "frontier_is_a_budget_not_an_exclusion_proof": True}
        temporary = args.out / "summary.json.tmp"
        temporary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.out / "summary.json")
        print(json.dumps(report), flush=True)
    print(json.dumps({"out": str(args.out), "finished_sizes": len(reports)}))


if __name__ == "__main__":
    main()

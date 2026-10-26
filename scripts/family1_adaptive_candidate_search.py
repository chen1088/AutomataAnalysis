#!/usr/bin/env python3
"""Adaptive heuristic candidate refinement, separate from certified intervals.

Only explicitly qualified refined graphs enter the active estimate leaderboard.
All cheap candidates, all ties, minimum verified uppers and raw evidence survive
in the archive. The user's estimate L-1 / rough[L-2,L] is not a lower proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import gzip
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time

import family1_graph_candidate_search as scoring

REPO = Path(__file__).resolve().parents[1]
WINDOWS = (6, 8, 10, 12, 16)
DEFAULT_REFINED = (REPO / "results/family1-m8-upper-refinement/records.jsonl",
                   REPO / "results/family1-m8-fresh-prefix-refinement/records.jsonl")


def rows(path):
    opener = gzip.open if Path(path).suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig") as source:
        for line, value in enumerate(source, 1):
            if value.strip():
                yield line, json.loads(value)


def estimate(length):
    return {"point": length - 1, "rough_band": [max(1, length - 2), length],
            "certified": False, "rule": "user heuristic: H approximately L-1, rough[L-2,L]"}


def window_cost(k, beam, remaining):
    total, width = 0, 1
    while remaining:
        span = min(k, remaining)
        total += width * ((1 << (span + 1)) - 2)
        width = min(beam, width * (1 << span))
        remaining -= span
    return total


def expansion_budget(k, beam, cap, multiplier=4, minimum=100000):
    return max(minimum, multiplier * ((1 << (k + 1)) - 2) * beam,
               window_cost(k, beam, max(0, cap - 1)))


def build_stage(graph, k, cap, *, seed=1088, samples=1024, beam=16,
                memory_mib=512, strong_prefix=False, seconds=20, multiplier=4, minimum=100000):
    helper = scoring.arguments(["--candidates", __file__, "--out", "out/adaptive-stage-unused", "--enable-stage2",
                                "--memory-mib", str(memory_mib), "--beam-width", str(beam)])
    stage = scoring.stage_settings(graph, helper)[1 if strong_prefix else 0]
    payload = graph["m"] * (1 << graph["m"]) // 4
    working = (3 * beam + k + 8) * payload
    available = memory_mib * (1 << 20) - working
    per_word = 3 * (128 + 4 * stage["distinct_permutation_dfas"])
    word_limit = max(1, available // per_word)
    words = min(stage["prefix_words"], 1 << (word_limit.bit_length() - 1))
    return {**stage, "name": f"adaptive-k{k}", "window_k": k, "samples": samples, "prefix_pairs": samples,
            "seed": seed, "beam_width": beam, "distance_coordinates": min(1024, 1 << graph["m"]),
            "viability_coordinates": min(1024, 1 << graph["m"]), "ranking": "remaining", "common_prefix_depth": 8,
            "expansions": expansion_budget(k, beam, cap, multiplier, minimum), "timeout_seconds": seconds,
            "prefix_words": words, "prefix_samples_per_depth": min(stage["prefix_samples_per_depth"], words),
            "estimated_pair_working_bytes": working, "pair_working_estimate_exceeds_budget": available <= 0,
            "prefix_word_budget_scaled": words != stage["requested_prefix_words"],
            "expansion_scope": "per prefix seed across all beam parents/windows",
            "window_blocks_unit": "retained length-k leaves, not complete rounds",
            "global_word_coverage_claimed": False}


@lru_cache(maxsize=100000)
def replay_pair(table, first, second):
    checked = scoring.verify_witness(table, [first, second])
    scalar = []
    for mask in range(1 << len(table)):
        endpoints = []
        for word in (first, second):
            state = 0
            for symbol in word:
                state = table[state][int(symbol) ^ ((mask >> state) & 1)]
            endpoints.append(state)
        if endpoints[0] != endpoints[1]:
            raise ValueError("independent scalar mask replay rejected a witness")
        scalar.append(endpoints[0])
    return {**checked, "independent_scalar_masks_verified": len(scalar)}


def positive_evidence(native, graph, stage, cap):
    """Rebuild every positive from its committed native result/checkpoint."""
    config_path = native / "run.json"
    if not config_path.exists():
        return [], None
    config = scoring.read_json(config_path)
    if config.get("key") != graph["key"] or config.get("length") != cap or config.get("best_of_seeds") is not True:
        raise ValueError("native graph/cap/best-of configuration mismatch")
    scoring.validate_native_configuration(config_path, {"config_sha256": scoring.digest(config_path)}, graph, stage, cap)
    if config.get("checkpoint_every") != 16:
        raise ValueError("native checkpoint frequency differs from pinned settings")
    candidates, result = [], None
    result_path = native / "result.json"
    if result_path.exists():
        if result_path.with_name("result.sha256").read_text().strip() != scoring.digest(result_path):
            raise ValueError("native result integrity mismatch")
        result = scoring.read_json(result_path)
        scoring.validate_native_configuration(config_path, result, graph, stage, cap)
        answer = scoring.normalize_native(result, graph, cap)
        if answer["upper_bound"] is not None:
            words = answer["witness"]
            candidates.append({"upper_bound": answer["upper_bound"], "witness": words,
                               "proof": scoring.reference(result_path), "proof_kind": "completed-native-result",
                               "verification": replay_pair(graph["canonical_table"], *words)})
    binding = scoring.digest(config_path)
    for path in sorted((native / "checkpoints").glob("*.txt")):
        sidecar = path.with_suffix(".txt.sha256")
        if not sidecar.exists():
            raise ValueError("checkpoint lacks its commit checksum")
        if sidecar.read_text().strip() != scoring.digest(path):
            raise ValueError("checkpoint integrity mismatch")
        lines = path.read_text().splitlines()
        if lines[0] != "FAMILY1SAMPLE1" or lines[1] != binding:
            raise ValueError("checkpoint is not bound to the expected native configuration")
        tag = next((index for index, value in enumerate(lines) if value.startswith("GUIDED1 ")), None)
        if tag is None:
            continue
        flags = lines[tag + 1].split()
        if flags[0] != "1" or flags[2] != "1":
            continue
        first, second, suffix = shlex.split(lines[tag + 2])
        words = [first + suffix, second + suffix]
        if len(words[0]) > cap:
            raise ValueError("checkpoint witness exceeds query cap")
        candidates.append({"upper_bound": len(words[0]), "witness": words,
                           "proof": scoring.reference(path), "proof_kind": "positive-checkpoint",
                           "verification": replay_pair(graph["canonical_table"], *words)})
    return candidates, result


def query(executable, graph, stage, cap, directory, plan_sha):
    spec = json.loads(scoring.compact({"graph": graph, "stage": stage, "cap": cap, "batch_plan_sha256": plan_sha}))
    metadata_path = directory / "observation.json"
    if metadata_path.exists():
        saved = scoring.read_json(metadata_path)
        if saved["query"] != spec:
            raise ValueError("query settings changed on resume")
        candidates, result = positive_evidence(directory / "native", graph, stage, cap)
        config_path = directory / "native/run.json"
        expected_ref = scoring.reference(config_path) if config_path.exists() else None
        if saved["native_configuration"] != expected_ref:
            raise ValueError("resumed native configuration reference changed")
        rebuilt = min(candidates, key=lambda value: (value["upper_bound"], value["witness"])) if candidates else None
        if saved["best_positive"] != rebuilt:
            raise ValueError("resumed observation disagrees with its checked native evidence")
        if bool(result is not None and result.get("traversal_complete") and saved["returncode"] == 0) != saved["completed_stage"]:
            raise ValueError("invalid completed-stage claim")
        return saved
    directory.mkdir(parents=True, exist_ok=True)
    native = directory / "native"
    command = scoring.native_command(executable, graph, stage, cap, native) + ["--best-of-seeds", "--checkpoint-every", "16"]
    if (native / "run.json").exists():
        command.append("--resume")
    scoring.atomic_json(directory / "invocation.json", {"query": spec, "command": command})
    started, outcome, code, stdout, stderr = time.monotonic(), "error", None, "", ""
    if stage["pair_working_estimate_exceeds_budget"]:
        outcome, stderr = "resource-budget", "Conservative full-family beam estimate exceeds planning budget."
    else:
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=stage["timeout_seconds"])
            code, stdout, stderr = process.returncode, process.stdout, process.stderr
            outcome = "completed" if code == 0 else "error"
        except subprocess.TimeoutExpired as error:
            outcome = "timeout"
            stdout, stderr = error.stdout or "", error.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
    (directory / "stdout.txt").write_text(stdout)
    (directory / "stderr.txt").write_text(stderr)
    candidates, result = positive_evidence(native, graph, stage, cap)
    answer = {"query": spec, "outcome": outcome, "returncode": code, "seconds": time.monotonic() - started,
              "best_positive": min(candidates, key=lambda value: (value["upper_bound"], value["witness"])) if candidates else None,
              "completed_stage": bool(code == 0 and result and result.get("traversal_complete")),
              "all_positive_artifacts_replayed": len(candidates), "global_word_coverage_claimed": False,
              "native_configuration": scoring.reference(native / "run.json") if (native / "run.json").exists() else None,
              "native_budget_diagnostics": result.get("module_stats") if result else None,
              "node_budget_cap_reported": bool(result.get("module_stats", {}).get("expansion_limits_reached", 0)) if result else None}
    scoring.atomic_json(metadata_path, answer)
    return answer


def load_archive(source, refined, m):
    archive = {}
    source_ref = scoring.reference(source)
    for line, row in rows(source):
        if row["m"] != m:
            continue
        graph = scoring.graph_metadata(row)
        lower, upper = row.get("lower_bound", 1), row.get("upper_bound")
        if type(lower) is not int or lower < 1 or upper is not None and (type(upper) is not int or upper < lower):
            raise ValueError("invalid sealed certified interval")
        archive[graph["key"]] = {**graph, "lower_bound": lower, "upper_bound": upper, "witness": row.get("witness"),
                                 "eligible": False, "completed_k": None, "max_attempted_k": None,
                                 "provenance": [{"source": source_ref, "line": line, "role": "sealed-corpus"}],
                                 "observations": []}
    for path in refined:
        source_ref = scoring.reference(path)
        for line, row in rows(path):
            if row["m"] != m:
                continue
            incoming = scoring.interval_record(row)
            key = incoming["key"]
            if key not in archive:
                archive[key] = {**scoring.graph_metadata(row), "lower_bound": 1, "upper_bound": None, "witness": None,
                                "eligible": False, "completed_k": None, "max_attempted_k": None, "provenance": [], "observations": []}
            old = archive[key]
            lower = max(old["lower_bound"], incoming["lower_bound"])
            if incoming["upper_bound"] is not None and (old["upper_bound"] is None or incoming["upper_bound"] < old["upper_bound"]):
                old.update(upper_bound=incoming["upper_bound"], witness=incoming["witness"])
            if old["upper_bound"] is not None and lower > old["upper_bound"]:
                raise ValueError("refined witness contradicts a certified lower source")
            old.update(lower_bound=lower, eligible=True, completed_k=6, max_attempted_k=6)
            old["provenance"].append({"source": source_ref, "line": line, "role": "explicit-prior-refinement-qualification"})
    return archive


def leaderboard(archive):
    return sorted((row for row in archive.values() if row["eligible"] and row["upper_bound"] is not None),
                  key=lambda row: (-row["upper_bound"], row["key"]))


def crowded_band(archive, width):
    ordered = leaderboard(archive)
    return [row for row in ordered if row["upper_bound"] >= ordered[0]["upper_bound"] - width] if ordered else []


def write_gzip(path, values):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as output:
            for value in values:
                output.write((scoring.compact(value) + "\n").encode())
    temporary.replace(path)


def export(args, archive, batches, observations, reason):
    eligible = leaderboard(archive)
    decorated = [{**row, "estimate": estimate(row["upper_bound"]),
                  "status": "exact" if row["lower_bound"] == row["upper_bound"] else "bounded",
                  "merge_length": row["lower_bound"] if row["lower_bound"] == row["upper_bound"] else None} for row in eligible]
    best_length = eligible[0]["upper_bound"] if eligible else None
    active = [row for row in decorated if row["upper_bound"] == best_length]
    pending = sorted((row for row in archive.values() if not row["eligible"]),
                     key=lambda row: (row["upper_bound"] is None, -(row["upper_bound"] or 0), row["key"]))
    scoring.write_jsonl(args.out / "records.jsonl", decorated)
    scoring.write_jsonl(args.out / "active-best.jsonl", active)
    scoring.write_jsonl(args.out / "eligible-leaderboard.jsonl", decorated)
    scoring.write_jsonl(args.out / "observations.jsonl", observations)
    write_gzip(args.out / "archive-records.jsonl.gz", [archive[key] for key in sorted(archive)])
    write_gzip(args.out / "pending-coarse.jsonl.gz", pending)
    summary = {"schema": 1, "method": "crowding-adaptive-heuristic-candidate-refinement", "m": args.m,
               "archived_classes": len(archive), "eligible_refined_classes": len(eligible), "pending_coarse_classes": len(pending),
               "active_best_ties": len(active), "active_verified_upper_length": best_length,
               "active_estimate": estimate(best_length) if best_length else None,
               "crowded_top_band": len(crowded_band(archive, args.band_width)), "crowding_threshold": args.crowding_threshold,
               "batches": batches, "query_count": len(observations), "outcomes": dict(Counter(row["outcome"] for row in observations)),
               "stopping_reason": reason, "all_raw_graphs_and_ties_archived": True,
               "active_selection_is_heuristic": True, "pending_coarse_could_contain_better_graphs": True,
               "rough_bands_are_certified_intervals": False, "misses_change_lower_bounds": False,
               "global_maximum_certified": False, "run_sha256": scoring.digest(args.out / "run.json")}
    scoring.atomic_json(args.out / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=REPO / "results/family1-m8-search/records.jsonl.gz")
    parser.add_argument("--refined-records", type=Path, action="append")
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--m", type=int, default=8)
    parser.add_argument("--jobs", type=int, default=12)
    parser.add_argument("--wall-seconds", type=int, default=240)
    parser.add_argument("--max-queries", type=int, default=64)
    parser.add_argument("--query-seconds", type=int, default=20)
    parser.add_argument("--crowding-threshold", type=int, default=3)
    parser.add_argument("--band-width", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--window-multiplier", type=int, default=4)
    parser.add_argument("--min-expansions", type=int, default=100000)
    parser.add_argument("--memory-mib", type=int, default=512)
    parser.add_argument("--strong-prefix", action="store_true")
    parser.add_argument("--seed", type=int, default=1088)
    parser.add_argument("--start-window", type=int, choices=WINDOWS, default=8)
    parser.add_argument("--admission-window", type=int, choices=WINDOWS, default=8)
    parser.add_argument("--admit-first", action="store_true", help="Qualify pending challengers before starting the requested continuation ladder.")
    parser.add_argument("--admit-pending", type=int, default=0)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--stop-after-batches", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if (not 1 <= args.m <= 20 or not 1 <= args.jobs <= 12 or min(args.wall_seconds, args.max_queries, args.query_seconds,
        args.crowding_threshold, args.batch_size, args.window_multiplier, args.min_expansions, args.memory_mib) < 1
        or args.band_width < 0 or not 0 <= args.admit_pending <= 8 or not 1 <= args.max_length <= 4096
        or not 0 <= args.seed < 1 << 64 or args.stop_after_batches < 0):
        parser.error("invalid adaptive resource/crowding budget")
    args.out, args.records, args.exe = args.out.resolve(), args.records.resolve(), args.exe.resolve()
    refined = list(dict.fromkeys(path.resolve() for path in [*DEFAULT_REFINED, *(args.refined_records or [])]))
    dependencies = [Path(__file__), Path(scoring.__file__), REPO / "scripts/family1_study.py"]
    config = {"schema": 1, "method": "crowding-adaptive-heuristic-candidate-refinement",
              "sources": [scoring.reference(path) for path in [args.records, *refined]],
              "code": [scoring.reference(path) for path in dependencies], "exe": scoring.reference(args.exe),
              "dlls": [scoring.reference(path) for path in sorted(args.exe.parent.glob("*.dll"))],
              "settings": {key: value for key, value in vars(args).items()
                           if key not in ("out", "records", "exe", "refined_records", "resume", "stop_after_batches")}}
    if args.out.exists() and any(args.out.iterdir()):
        if not args.resume or scoring.read_json(args.out / "run.json") != config:
            raise ValueError("use fresh output or identical pinned --resume")
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        native = args.out / "native-used"
        native.mkdir()
        shutil.copy2(args.exe, native / args.exe.name)
        for path in args.exe.parent.glob("*.dll"):
            shutil.copy2(path, native / path.name)
        inputs = args.out / "inputs-used"
        inputs.mkdir()
        shutil.copy2(args.records, inputs / args.records.name)
        for index, path in enumerate(refined):
            shutil.copy2(path, inputs / f"refined-{index:02d}.jsonl")
        source_dir = args.out / "sources-used"
        source_dir.mkdir()
        for path in dependencies:
            shutil.copy2(path, source_dir / path.name)
        scoring.atomic_json(args.out / "run.json", config)
    executable = args.out / "native-used" / args.exe.name
    if scoring.digest(executable) != config["exe"]["sha256"]:
        raise ValueError("pinned native executable changed")
    for item in config["dlls"]:
        if scoring.digest(executable.parent / Path(item["path"]).name) != item["sha256"]:
            raise ValueError("pinned DLL changed")
    archive = load_archive(args.records, refined, args.m)
    batches, observations, stage_index, admitted = [], [], WINDOWS.index(args.start_window), 0
    admission_attempted = set()
    started = time.monotonic()
    for batch_index in range(args.max_queries):
        band = crowded_band(archive, args.band_width)
        admission = False
        force_admission = args.admit_first and admitted < args.admit_pending
        if not force_admission and len(band) >= args.crowding_threshold and stage_index < len(WINDOWS):
            k = WINDOWS[stage_index]
            selected = band[:min(args.batch_size, args.max_queries - len(observations))]
            trigger = "crowded eligible top band; increase window"
            stage_index += 1
        elif args.admit_pending > admitted:
            k, admission = args.admission_window, True
            selected = sorted((row for row in archive.values() if not row["eligible"] and row["upper_bound"] is not None
                               and row["key"] not in admission_attempted),
                              key=lambda row: (-row["upper_bound"], row["key"]))[:min(args.admit_pending - admitted, args.batch_size,
                                                                                     args.max_queries - len(observations))]
            trigger = "optional pending challenger qualification; no coarse estimate promotion"
        else:
            reason = "eligible top band not crowded" if len(band) < args.crowding_threshold else "maximum configured window reached"
            break
        if not selected or len(observations) >= args.max_queries:
            reason = "query budget exhausted"
            break
        prior_hash = scoring.digest(args.out / "plans" / f"batch-{batch_index - 1}.json") if batch_index else None
        plans = []
        for row in selected:
            cap = min(args.max_length, row["upper_bound"] - 1)
            if cap < 1:
                continue
            stage = build_stage(scoring.graph_metadata(row), k, cap, seed=args.seed, memory_mib=args.memory_mib,
                                strong_prefix=args.strong_prefix, seconds=args.query_seconds,
                                multiplier=args.window_multiplier, minimum=args.min_expansions)
            if stage["expansions"] > 1000000000:
                raise ValueError("requested conservative expansion budget exceeds native CLI limit")
            plans.append({"key": row["key"], "cap": cap, "stage": stage})
        plan = {"index": batch_index, "window_k": k, "trigger": trigger, "previous_plan_sha256": prior_hash,
                "pre_batch_band_size": len(band), "pre_batch_active_length": leaderboard(archive)[0]["upper_bound"] if leaderboard(archive) else None,
                "admission": admission, "queries": plans}
        plan_path = args.out / "plans" / f"batch-{batch_index}.json"
        if plan_path.exists():
            if scoring.read_json(plan_path) != plan:
                raise ValueError("deterministic batch plan changed on resume")
        else:
            if time.monotonic() - started + args.query_seconds > args.wall_seconds:
                reason = "wall budget reached before launching another batch"
                break
            scoring.atomic_json(plan_path, plan)
        plan_sha = scoring.digest(plan_path)
        batch_results = []
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(query, executable, scoring.graph_metadata(archive[item["key"]]), item["stage"], item["cap"],
                                   args.out / "queries" / f"batch-{batch_index}" / item["key"], plan_sha): item for item in plans}
            for future in as_completed(futures):
                item, answer = futures[future], future.result()
                batch_results.append((item, answer))
                print(scoring.compact({"batch": batch_index, "k": k, "key": item["key"], "outcome": answer["outcome"],
                                       "new_upper": answer["best_positive"]["upper_bound"] if answer["best_positive"] else None,
                                       "completed_stage": answer["completed_stage"]}), flush=True)
        for item, answer in sorted(batch_results, key=lambda value: value[0]["key"]):
            row = archive[item["key"]]
            positive = answer["best_positive"]
            if positive and (row["upper_bound"] is None or positive["upper_bound"] < row["upper_bound"]):
                if positive["upper_bound"] < row["lower_bound"]:
                    raise ValueError("verified upper contradicts an existing lower certificate")
                row.update(upper_bound=positive["upper_bound"], witness=positive["witness"], upper_certificate=positive)
            row["max_attempted_k"] = max(row["max_attempted_k"] or 0, k)
            if answer["completed_stage"]:
                row.update(eligible=True, completed_k=max(row["completed_k"] or 0, k))
            row["observations"].append({"batch": batch_index, "k": k, "completed_stage": answer["completed_stage"],
                                         "outcome": answer["outcome"], "node_budget_cap_reported": answer["node_budget_cap_reported"],
                                         "native_configuration": answer["native_configuration"]})
            observations.append({"batch": batch_index, **answer})
        if admission:
            admitted += len(plans)
            admission_attempted.update(item["key"] for item in plans)
            stage_index = min(stage_index, WINDOWS.index(min(10, WINDOWS[-1])))
        batches.append({**plan, "plan_sha256": plan_sha, "completed_stages": sum(answer["completed_stage"] for _, answer in batch_results)})
        export(args, archive, batches, observations, "batch checkpoint")
        if args.stop_after_batches and batch_index + 1 >= args.stop_after_batches:
            reason = "requested batch checkpoint"
            break
    else:
        reason = "query budget exhausted"
    summary = export(args, archive, batches, observations, reason)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

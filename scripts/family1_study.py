#!/usr/bin/env python3
"""Combine exact small cases and reproducible heuristic Family 1 challenger runs.

The study reports certificates for individual graph scores and score intervals.
Heuristic graph coverage never establishes a maximum over all rooted graphs.
All graph classes, observations, and best certified lower-bound ties are retained.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
CLASS_COUNTS = {1: 1, 2: 6, 3: 57, 4: 678, 5: 10398, 6: 192181}
GENERATION_DESCRIPTION = (
    "Deterministic restart seeds; edge-splitting growth, accepted accessible "
    "mutations, and cycle-plus-random-edge candidates. This is not uniform "
    "sampling of graph classes and supplies no statistical confidence claim."
)
GLOBAL_METHOD = "family1-global-synthesis"
GLOBAL_ENCODER = "family1-accessible-prior-incoming-static-mask-separation-cnf-v1"
GLOBAL_ENCODERS = {GLOBAL_ENCODER, "family1-accessible-discovery-static-mask-separation-cnf-v2"}


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source, 1):
            if line.strip():
                yield line_number, json.loads(line)


def file_hash(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fixed_key(table) -> str:
    return "".join(f"{target:02d}" for row in table for target in row)


def table_from_key(key: str, m: int):
    if not isinstance(key, str) or not key.isascii() or not key.isdigit():
        raise ValueError("invalid graph key")
    if len(key) == 4 * m:
        values = [int(key[offset:offset + 2]) for offset in range(0, len(key), 2)]
    elif m <= 6 and len(key) == 2 * m:
        values = list(map(int, key))
    else:
        raise ValueError("graph key length disagrees with size")
    return tuple(zip(values[::2], values[1::2]))


def validate_table(table):
    table = tuple(tuple(row) for row in table)
    m = len(table)
    if not 1 <= m <= 20 or any(len(row) != 2 for row in table):
        raise ValueError("expected 1..20 vertices with two ports each")
    if any(type(target) is not int or not 0 <= target < m for row in table for target in row):
        raise ValueError("transition target outside seed")
    reached, pending = {0}, [0]
    while pending:
        for target in table[pending.pop()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    if len(reached) != m:
        raise ValueError("study graph is not root-accessible")
    return table


def canonical_table(table):
    """Exact rooted lex-min table; at most 512 discovery labelings for m=20."""
    table = validate_table(table)
    m = len(table)
    old_to_new = [-1] * m
    new_to_old = [0] * m
    old_to_new[0] = 0
    rows = [None] * m
    best = None

    def discover(row, known):
        nonlocal best
        if row == m:
            candidate = tuple(rows)
            if best is None or candidate < best:
                best = candidate
            return
        if row >= known:
            raise AssertionError("accessible graph discovery stopped early")
        a, b = table[new_to_old[row]]
        new_a, new_b = old_to_new[a] < 0, old_to_new[b] < 0

        def continue_row(next_known):
            rows[row] = tuple(sorted((old_to_new[a], old_to_new[b])))
            if best is not None and tuple(rows[:row + 1]) > best[:row + 1]:
                return
            discover(row + 1, next_known)

        if new_a and new_b and a != b:
            for first, second in ((a, b), (b, a)):
                old_to_new[first], old_to_new[second] = known, known + 1
                new_to_old[known], new_to_old[known + 1] = first, second
                continue_row(known + 2)
            old_to_new[a] = old_to_new[b] = -1
        elif new_a or new_b:
            unseen = a if new_a else b
            old_to_new[unseen] = known
            new_to_old[known] = unseen
            continue_row(known + 1)
            old_to_new[unseen] = -1
        else:
            continue_row(known)

    discover(0, 1)
    return best


def record_table(record):
    m = record.get("m")
    if type(m) is not int or not 1 <= m <= 20:
        raise ValueError("invalid graph size")
    table = record.get("canonical_table")
    if table is None:
        table = table_from_key(record["key"], m)
    table = validate_table(table)
    if len(table) != m:
        raise ValueError("record size disagrees with transition table")
    if "key" in record and table_from_key(record["key"], m) != table:
        raise ValueError("record key disagrees with transition table")
    return canonical_table(table)


def score_interval(record):
    lower = record.get("lower_bound", record.get("merge_length") if record.get("status") == "exact" else 1)
    upper = record.get("upper_bound")
    exact = record.get("merge_length") if record.get("status") == "exact" else None
    if exact is not None:
        if type(exact) is not int or exact < 1:
            raise ValueError("invalid exact merge length")
        if upper is not None and upper != exact:
            raise ValueError("exact merge length disagrees with upper bound")
        upper = exact
    if type(lower) is not int or lower < 1:
        raise ValueError("invalid score lower bound")
    if upper is not None and (type(upper) is not int or upper < lower):
        raise ValueError("inconsistent score interval")
    if exact is not None and lower != exact:
        raise ValueError("exact merge length disagrees with lower bound")
    witness = record.get("witness")
    if upper is not None:
        if not isinstance(witness, (list, tuple)) or len(witness) != 2:
            raise ValueError("known upper bound requires a witness pair")
        if any(not isinstance(word, str) or len(word) != upper or set(word) - {"0", "1"} for word in witness) or witness[0] == witness[1]:
            raise ValueError("invalid upper-bound witness")
        witness = tuple(sorted(witness))
    elif witness is not None:
        raise ValueError("witness without a known upper bound")
    return lower, upper, witness


def expected_seed_keys(path: Path):
    keys = {(len(table), fixed_key(table)) for _, record in jsonl(path)
            for table in [record_table(record)]}
    if not keys:
        raise ValueError("empty warm-seed file")
    return [key for _, key in sorted(keys)]


def restart_seed(seed: int, index: int) -> int:
    return (seed + index * 0x9E3779B97F4A7C15) & ((1 << 64) - 1)


def requested_run_config(args, seed, seed_keys):
    return {
        "min_m": 7, "max_m": 20, "candidates": args.candidates, "beam": args.beam,
        "jobs": args.jobs, "seed": seed, "timeout_ms": args.timeout_ms,
        "solve_timeout_ms": args.solve_timeout_ms, "max_length": args.max_length,
        "max_refinements": args.max_refinements, "projection_depth": args.projection_depth,
        "projection_max_states": args.projection_max_states,
        "projection_masks": args.projection_masks, "graph": "", "seed_graphs": seed_keys,
    }


def config_matches(actual, expected):
    if not isinstance(actual, dict):
        return False
    defaults = {"jobs": 1, "projection_masks": 64}
    return all(actual.get(key, defaults.get(key)) == value for key, value in expected.items())


def orchestrate_restarts(args):
    """Run no work when restarts=0; every scheduled size uses the same budgets."""
    if not args.restarts:
        return [], []
    if not args.exe.is_file():
        raise ValueError(f"missing Family1Explore executable: {args.exe}")
    seed_keys = expected_seed_keys(args.seeds)
    directories, commands = [], []
    for index in range(args.restarts):
        seed = restart_seed(args.seed, index)
        directory = args.out / "restarts" / f"restart-{index:03d}-seed-{seed}"
        expected = requested_run_config(args, seed, seed_keys)
        metadata = load_json(directory / "run.json")
        summary = load_json(directory / "summary.json", {})
        if metadata is not None and not config_matches(metadata, expected):
            raise ValueError(f"existing restart has different generation settings or budgets: {directory}")
        command = [str(args.exe), "--out", str(directory), "--min-m", "7", "--max-m", "20",
                   "--candidates", str(args.candidates), "--beam", str(args.beam), "--jobs", str(args.jobs),
                   "--seed", str(seed), "--timeout-ms", str(args.timeout_ms),
                   "--solve-timeout-ms", str(args.solve_timeout_ms), "--max-length", str(args.max_length),
                   "--max-refinements", str(args.max_refinements), "--projection-depth", str(args.projection_depth),
                   "--projection-max-states", str(args.projection_max_states), "--projection-masks", str(args.projection_masks),
                   "--seeds", str(args.seeds)]
        if metadata is not None:
            command.append("--resume")
        reused = bool(metadata is not None and summary.get("candidate_traversal_complete") is True)
        if not reused:
            print(f"Restart {index + 1}/{args.restarts}: seed={seed}, sizes=7..20", flush=True)
            subprocess.run(command, cwd=REPO, check=True)
        if not (directory / "graphs.jsonl").is_file():
            raise ValueError(f"restart produced no graph export: {directory}")
        commands.append({"index": index, "seed": seed, "command": command,
                         "directory": str(directory), "reused_completed_run": reused})
        directories.append(directory)
    return directories, commands


def atomic_json(path: Path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_jsonl(path: Path, values):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as out:
        for value in values:
            out.write(compact(value) + "\n")
    temporary.replace(path)


def validate_global_report(report):
    if not isinstance(report, dict) or report.get("schema") != 1 or report.get("method") != GLOBAL_METHOD or report.get("encoder_version") not in GLOBAL_ENCODERS:
        raise ValueError("unrecognized global certificate schema, method, or encoder")
    m, threshold = report.get("states"), report.get("threshold")
    if type(m) is not int or not 1 <= m <= 20 or type(threshold) is not int or threshold < 1:
        raise ValueError("invalid global certificate scope")
    decision = report.get("decision")
    if decision not in ("impossible", "challenger", "unknown"):
        raise ValueError("invalid global certificate decision")
    if decision == "impossible":
        if report.get("global_upper_bound_certified") is not True or report.get("proven_upper_bound") != threshold:
            raise ValueError("impossible report lacks a consistent certified upper bound")
    elif report.get("global_upper_bound_certified") is True or report.get("proven_upper_bound") not in (None, 0):
        raise ValueError("non-impossibility report claims a global upper bound")
    pairs = report.get("learned_pairs")
    if not isinstance(pairs, list):
        raise ValueError("global report lacks replayable learned pairs")
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]:
            raise ValueError("invalid learned word pair")
        if any(not isinstance(word, str) or not 1 <= len(word) <= threshold or set(word) - {"0", "1"} for word in pair) or len(pair[0]) != len(pair[1]):
            raise ValueError("learned pair lies outside the certified threshold")
    return m, threshold, decision


def import_global_certificates(args):
    """Accept upper bounds only after the native encoder replays them as UNSAT."""
    attempts, upper_bounds = [], {}
    for supplied in args.global_certificate:
        supplied = supplied.resolve()
        result_path = supplied / "result.json" if supplied.is_dir() else supplied
        report = load_json(result_path)
        m, threshold, decision = validate_global_report(report)
        cnf_path = result_path.parent / "graph-space.cnf"
        binding = {"result_sha256": file_hash(result_path),
                   "original_cnf_sha256": file_hash(cnf_path) if cnf_path.is_file() else None,
                   "encoder_version": report["encoder_version"]}
        attempt = {
            "certificate_id": len(attempts), "result_file": str(result_path), "states": m,
            "threshold": threshold, "reported_decision": decision, "report": report,
            "source_binding": binding, "replay_verified": False, "verified_global_upper_bound": None,
        }
        if decision != "impossible":
            attempt["formal_status"] = "unresolved-no-global-upper-bound"
            attempts.append(attempt)
            continue
        if args.global_exe is None or not args.global_exe.is_file():
            raise ValueError("an impossible report requires --global-exe PATH for a fresh or cached verified replay")
        binding["global_executable_sha256"] = file_hash(args.global_exe)
        cache_id = hashlib.sha256(compact(binding).encode("utf-8")).hexdigest()
        cache_directory = args.out / "proof-replays" / cache_id
        cache_directory.mkdir(parents=True, exist_ok=True)
        manifest_path = cache_directory / "verified-replay.json"
        manifest = load_json(manifest_path, {})
        replay_path = Path(manifest.get("result_file", ""))
        cached = bool(manifest.get("source_binding") == binding and replay_path.is_file()
                      and manifest.get("result_sha256") == file_hash(replay_path))
        replay = load_json(replay_path) if cached else None
        if not cached:
            # Freeze the supplied pairs and scope in the native CLI's compact
            # JSON syntax; arbitrary JSON filenames/whitespace remain supported.
            replay_input = cache_directory / "input"
            replay_input.mkdir(exist_ok=True)
            (replay_input / "result.json").write_text(compact(report) + "\n", encoding="utf-8")
            if cnf_path.is_file():
                shutil.copyfile(cnf_path, replay_input / "graph-space.cnf")
            index = 0
            while (cache_directory / f"attempt-{index:03d}").exists():
                index += 1
            replay_directory = cache_directory / f"attempt-{index:03d}"
            command = [str(args.global_exe), "--replay", str(replay_input), "--out", str(replay_directory),
                       "--timeout-ms", str(args.proof_timeout_ms), "--solve-timeout-ms", str(args.proof_timeout_ms)]
            subprocess.run(command, cwd=REPO, check=True)
            replay_path = replay_directory / "result.json"
            replay = load_json(replay_path)
            attempt["replay_command"] = command
        replay_m, replay_threshold, replay_decision = validate_global_report(replay)
        if (replay_m, replay_threshold) != (m, threshold) or replay["encoder_version"] != report["encoder_version"]:
            raise ValueError("replay result scope disagrees with supplied certificate")
        attempt.update({"replay_result_file": str(replay_path), "replay_result_sha256": file_hash(replay_path),
                        "replay_cached": cached, "replay_report": replay})
        if replay_decision == "impossible":
            attempt.update({"replay_verified": True, "verified_global_upper_bound": threshold,
                            "formal_status": "global-upper-bound-replay-verified"})
            atomic_json(manifest_path, {"source_binding": binding, "result_file": str(replay_path),
                                        "result_sha256": file_hash(replay_path)})
            old = upper_bounds.get(m)
            if old is None or threshold < old["upper_bound"]:
                upper_bounds[m] = {"upper_bound": threshold, "certificate_ids": [attempt["certificate_id"]]}
            elif threshold == old["upper_bound"]:
                old["certificate_ids"].append(attempt["certificate_id"])
        else:
            attempt["formal_status"] = "unresolved-replay-did-not-prove-impossible"
        attempts.append(attempt)
    return attempts, upper_bounds


def merge_record(merged, table, record, observation_id, source_id):
    m, key = len(table), fixed_key(table)
    lower, upper, witness = score_interval(record)
    identity = (m, key)
    item = merged.get(identity)
    if item is None:
        item = merged[identity] = {
            "m": m, "key": key, "canonical_table": table,
            "lower_bound": lower, "upper_bound": upper, "witness": witness,
            "observation_ids": [], "source_ids": set(),
            "lower_bound_observation_ids": [], "upper_bound_observation_ids": [],
        }
    if lower > item["lower_bound"]:
        item["lower_bound"] = lower
        item["lower_bound_observation_ids"] = []
    if lower == item["lower_bound"]:
        item["lower_bound_observation_ids"].append(observation_id)
    if upper is not None:
        if item["upper_bound"] is None or upper < item["upper_bound"]:
            item["upper_bound"] = upper
            item["upper_bound_observation_ids"] = []
            item["witness"] = witness
        if upper == item["upper_bound"]:
            item["upper_bound_observation_ids"].append(observation_id)
            item["witness"] = min(item["witness"], witness)
    if item["upper_bound"] is not None and item["lower_bound"] > item["upper_bound"]:
        raise ValueError(f"contradictory score certificates for m={m}, key={key}: lower={item['lower_bound']}, upper={item['upper_bound']}")
    item["observation_ids"].append(observation_id)
    item["source_ids"].add(source_id)


def complete_small_coverage(source, source_records):
    """Only explicit exhaustive small-run evidence can certify global maxima."""
    if not source["is_exact_run"]:
        return {}
    by_size = defaultdict(dict)
    for identity, score in source_records.items():
        by_size[identity[0]][identity] = score
    result = {}
    for summary in source.get("summary", {}).get("sizes", []):
        m = summary.get("m")
        if m not in CLASS_COUNTS:
            continue
        scores = by_size[m]
        if not (summary.get("enumeration_complete") is True and summary.get("scoring_complete") is True
                and summary.get("maximum_certified") is True):
            continue
        if len(scores) != CLASS_COUNTS[m] or len(scores) != summary.get("evaluated"):
            raise ValueError(f"exhaustive coverage count disagrees at m={m}")
        if any(lower != upper for lower, upper in scores.values()):
            raise ValueError(f"claimed exhaustive exact scores are unresolved at m={m}")
        maximum = max(lower for lower, _ in scores.values())
        ties = sum(lower == maximum for lower, _ in scores.values())
        if maximum != summary.get("maximum_merge_length") or ties != summary.get("maximizer_count"):
            raise ValueError(f"claimed exact maximum disagrees with graph records at m={m}")
        result[m] = {"maximum": maximum, "source_id": source["source_id"], "classes": len(scores)}
    return result


CSV_FIELDS = [
    "m", "unique_graphs", "observations", "source_runs", "restart_seeds", "exact_graphs", "unresolved_graphs",
    "best_known_lower_bound", "observed_maximum_upper_bound", "best_lower_bound_ties", "best_exact_merge_length",
    "best_exact_ties", "strong_challengers", "competitive_cases", "unresolved_competitive_cases",
    "observed_maximum_certified", "observed_maximum", "global_upper_bound", "maximum_value_certified",
    "maximizing_collection_complete", "global_maximum_certified", "global_maximum", "formal_global_status",
]


def aggregate(args, run_directories, commands):
    args.out.mkdir(parents=True, exist_ok=True)
    directories = []
    for directory in [args.exact_run, *args.existing_run, *run_directories]:
        directory = directory.resolve()
        if directory not in directories:
            directories.append(directory)
    merged, sources, coverage = {}, [], {}
    observation_count = 0
    observations_tmp = args.out / "observations.jsonl.tmp"
    with observations_tmp.open("w", encoding="utf-8", newline="\n") as observations:
        for source_id, directory in enumerate(directories):
            graph_path = directory / "graphs.jsonl"
            if not graph_path.is_file():
                raise ValueError(f"missing evaluated-graph export: {graph_path}")
            metadata = load_json(directory / "run.json", {})
            source = {
                "source_id": source_id, "directory": str(directory), "graphs_file": str(graph_path),
                "graphs_sha256": file_hash(graph_path), "is_exact_run": directory == args.exact_run.resolve(),
                "metadata": metadata, "summary": load_json(directory / "summary.json", {}),
                "observation_count": 0, "unique_graphs": 0, "sizes": {},
            }
            seen = {}
            source_counts = Counter()
            for line_number, record in jsonl(graph_path):
                table = record_table(record)
                lower, upper, _ = score_interval(record)
                identity = (len(table), fixed_key(table))
                merge_record(merged, table, record, observation_count, source_id)
                observations.write(compact({"observation_id": observation_count, "source_id": source_id,
                                            "source_line": line_number, "m": identity[0], "canonical_key": identity[1],
                                            "record": record}) + "\n")
                observation_count += 1
                source["observation_count"] += 1
                source_counts[identity[0]] += 1
                if identity in seen:
                    old_lower, old_upper = seen[identity]
                    known_upper = [value for value in (old_upper, upper) if value is not None]
                    seen[identity] = max(lower, old_lower), min(known_upper) if known_upper else None
                else:
                    seen[identity] = lower, upper
            source["unique_graphs"] = len(seen)
            source["sizes"] = dict(sorted(source_counts.items()))
            sources.append(source)
            coverage.update(complete_small_coverage(source, seen))
    proof_attempts, global_upper_bounds = import_global_certificates(args)
    for m, certificate in coverage.items():
        previous = global_upper_bounds.get(m)
        if previous is not None and previous["upper_bound"] < certificate["maximum"]:
            raise ValueError(f"global upper certificate contradicts the exhaustive maximum at m={m}")
        global_upper_bounds[m] = {
            "upper_bound": certificate["maximum"],
            "certificate_ids": previous["certificate_ids"] if previous and previous["upper_bound"] == certificate["maximum"] else [],
            "exhaustive_source_id": certificate["source_id"],
        }

    records = []
    by_size = defaultdict(list)
    for identity, item in sorted(merged.items()):
        item["source_ids"] = sorted(item["source_ids"])
        item["observation_count"] = len(item["observation_ids"])
        lower, upper = item["lower_bound"], item["upper_bound"]
        item["status"] = "exact" if upper == lower else "bounded" if upper is not None else "lower-bound" if lower > 1 else "incomplete"
        item["merge_length"] = lower if upper == lower else None
        global_bound = global_upper_bounds.get(item["m"])
        effective_upper = upper
        if global_bound is not None:
            effective_upper = min(upper, global_bound["upper_bound"]) if upper is not None else global_bound["upper_bound"]
            if lower > effective_upper:
                raise ValueError(f"global upper certificate contradicts an attained lower bound at m={item['m']}, key={item['key']}")
        item["effective_upper_bound"] = effective_upper
        item["effective_status"] = "exact" if effective_upper == lower else "bounded" if effective_upper is not None else item["status"]
        item["effective_merge_length"] = lower if effective_upper == lower else None
        item["global_upper_bound_certificate_ids"] = global_bound["certificate_ids"] if global_bound else []
        item["global_upper_bound_exhaustive_source_id"] = global_bound.get("exhaustive_source_id") if global_bound else None
        records.append(item)
        by_size[identity[0]].append(item)

    champions, best_exact, challengers, competitive = [], [], [], []
    sizes = []
    for m in range(1, 21):
        graphs = by_size[m]
        lower = max((graph["lower_bound"] for graph in graphs), default=None)
        exact = [graph for graph in graphs if graph["effective_status"] == "exact"]
        best = max((graph["effective_merge_length"] for graph in exact), default=None)
        selected_lower = [graph for graph in graphs if graph["lower_bound"] == lower]
        selected_exact = [graph for graph in exact if graph["effective_merge_length"] == best]
        strong = [graph for graph in graphs if graph["effective_upper_bound"] is None or graph["effective_upper_bound"] > lower]
        possible = [graph for graph in graphs if graph["effective_upper_bound"] is None or graph["effective_upper_bound"] >= lower]
        upper = max((graph["effective_upper_bound"] for graph in graphs), default=None) if graphs and all(graph["effective_upper_bound"] is not None for graph in graphs) else None
        pool_certified = lower is not None and upper == lower
        source_ids = {source_id for graph in graphs for source_id in graph["source_ids"]}
        seeds = {sources[source_id]["metadata"]["seed"] for source_id in source_ids
                 if not sources[source_id]["is_exact_run"] and "seed" in sources[source_id]["metadata"]}
        certificate = coverage.get(m)
        if certificate and (len(graphs) != certificate["classes"] or lower != certificate["maximum"] or not pool_certified):
            raise ValueError(f"merged records contradict exhaustive coverage at m={m}")
        global_bound = global_upper_bounds.get(m)
        maximum_value_certified = bool(certificate or (global_bound is not None and lower == global_bound["upper_bound"]))
        collection_complete = certificate is not None
        sized_attempts = [attempt for attempt in proof_attempts if attempt["states"] == m]
        formal_status = (
            "exhaustive-maximum-and-collection-certified" if certificate else
            "maximum-value-certified-collection-incomplete" if maximum_value_certified else
            "global-upper-bound-certified-attainment-unresolved" if global_bound is not None else
            "unresolved"
        )
        item = {
            "m": m, "unique_graphs": len(graphs), "observations": sum(graph["observation_count"] for graph in graphs),
            "source_runs": len(source_ids), "restart_seeds": len(seeds), "seed_values": sorted(seeds),
            "exact_graphs": len(exact), "unresolved_graphs": len(graphs) - len(exact),
            "best_known_lower_bound": lower, "observed_maximum_upper_bound": upper,
            "best_lower_bound_ties": len(selected_lower), "best_exact_merge_length": best, "best_exact_ties": len(selected_exact),
            "strong_challengers": len(strong), "competitive_cases": len(possible),
            "unresolved_competitive_cases": sum(graph["effective_status"] != "exact" for graph in possible),
            "observed_maximum_certified": pool_certified, "observed_maximum": lower if pool_certified else None,
            "maximum_value_certified": maximum_value_certified, "maximizing_collection_complete": collection_complete,
            "global_maximum_certified": maximum_value_certified, "global_maximum": lower if maximum_value_certified else None,
            "global_upper_bound_certified": global_bound is not None,
            "global_upper_bound": global_bound["upper_bound"] if global_bound else None,
            "global_upper_bound_certificate_ids": global_bound["certificate_ids"] if global_bound else [],
            "formal_global_status": formal_status, "formal_attempts": len(sized_attempts),
            "global_certificate": certificate,
            "coverage": "exhaustive-rooted-classes" if certificate else "global-value-certified-collection-incomplete" if maximum_value_certified else "observed-classes-only",
        }
        sizes.append(item)
        champions.extend(selected_lower)
        best_exact.extend(selected_exact)
        challengers.extend(strong)
        competitive.extend(possible)

    summary = {
        "schema": 1, "study": "Family 1 separate-seed score study, sizes 1..20",
        "generation_description": GENERATION_DESCRIPTION,
        "enumeration_complete": all(item["maximizing_collection_complete"] for item in sizes),
        "maximum_certified": all(item["maximum_value_certified"] for item in sizes),
        "maximum_value_certified": all(item["maximum_value_certified"] for item in sizes),
        "maximizing_collection_complete": all(item["maximizing_collection_complete"] for item in sizes),
        "global_maximum_over_budget_1_to_20": max((item["global_maximum"] for item in sizes), default=None)
            if all(item["global_maximum_certified"] for item in sizes) else None,
        "best_known_lower_bound_over_budget_1_to_20": max((item["best_known_lower_bound"] for item in sizes if item["best_known_lower_bound"] is not None), default=None),
        "unique_graphs": len(records), "observations": observation_count, "source_runs": len(sources),
        "champion_definition": "every observed graph tied for the largest certified lower bound at its size; not a claim of a global maximum",
        "best_exact_definition": "largest effective exact score among observed graphs, including composition with replay-verified global upper bounds; unresolved graphs may exceed it",
        "strong_challenger_definition": "upper bound unknown or strictly greater than the best known lower bound at that size",
        "competitive_case_definition": "upper bound unknown or at least the best known lower bound; includes possible ties",
        "witness_verification": "input individual score certificates are preserved; global impossibility certificates are replayed with the native encoder. A derived effective exact score may lack an explicit collision witness.",
        "global_proof_imports": {"attempts": len(proof_attempts), "replay_verified_impossible": sum(attempt["replay_verified"] for attempt in proof_attempts)},
        "sizes": sizes,
    }
    observations_tmp.replace(args.out / "observations.jsonl")
    for name, values in (("graphs.jsonl", records), ("champions.jsonl", champions), ("best_exact.jsonl", best_exact),
                         ("challengers.jsonl", challengers), ("competitive_cases.jsonl", competitive)):
        atomic_jsonl(args.out / name, values)
    atomic_json(args.out / "summary.json", summary)
    atomic_json(args.out / "provenance.json", {"schema": 1, "generation_description": GENERATION_DESCRIPTION,
                                              "scheduled_restarts": commands, "sources": sources,
                                              "global_certificate_attempts": proof_attempts})
    csv_tmp = args.out / "study.csv.tmp"
    with csv_tmp.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sizes)
    csv_tmp.replace(args.out / "study.csv")
    atomic_json(args.out / "study-run.json", {
        "schema": 1, "exact_run": str(args.exact_run), "existing_runs": [str(path) for path in args.existing_run],
        "requested_restarts": args.restarts, "scheduled_commands": commands,
        "global_certificates": [str(path) for path in args.global_certificate],
        "scoring_budgets": {key: getattr(args, key) for key in ("candidates", "beam", "jobs", "timeout_ms", "solve_timeout_ms", "max_length",
                                                               "max_refinements", "projection_depth", "projection_max_states", "projection_masks")},
    })
    return summary


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Explore.exe")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--restarts", type=int, default=0, help="0 imports existing runs without starting a search")
    parser.add_argument("--candidates", type=int, default=8)
    parser.add_argument("--beam", type=int, default=4)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1088)
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("--solve-timeout-ms", type=int, default=2000)
    parser.add_argument("--max-length", type=int, default=64)
    parser.add_argument("--max-refinements", type=int, default=256)
    parser.add_argument("--projection-depth", type=int, default=20)
    parser.add_argument("--projection-max-states", type=int, default=1 << 20)
    parser.add_argument("--projection-masks", type=int, default=64)
    parser.add_argument("--seeds", type=Path, default=REPO / "results/family1-m1-m6/maximizers.jsonl")
    parser.add_argument("--existing-run", type=Path, action="append", default=[])
    parser.add_argument("--exact-run", type=Path, default=REPO / "out/family1-m1-m6")
    parser.add_argument("--global-certificate", type=Path, action="append", default=[])
    parser.add_argument("--global-exe", type=Path, help="native Family1GlobalCheck replay verifier; required for impossible imports")
    parser.add_argument("--proof-timeout-ms", type=int, default=30000)
    args = parser.parse_args(argv)
    if not 0 <= args.restarts <= 100000 or not 1 <= args.candidates <= 100000 or not 1 <= args.beam <= 100000 or not 1 <= args.jobs <= 32:
        parser.error("require nonnegative restarts, candidates/beam 1..100000, jobs 1..32")
    if not 0 <= args.seed < 1 << 64 or min(args.timeout_ms, args.solve_timeout_ms, args.max_refinements, args.proof_timeout_ms) < 1:
        parser.error("require a 64-bit nonnegative seed and positive SAT budgets")
    if not 1 <= args.max_length <= 4096 or not 0 <= args.projection_depth <= 26 or not 1 <= args.projection_max_states <= 1 << 26 or not 1 <= args.projection_masks <= 64:
        parser.error("invalid length or projection budget")
    for name in ("exe", "out", "seeds", "exact_run"):
        setattr(args, name, getattr(args, name).resolve())
    args.existing_run = [path.resolve() for path in args.existing_run]
    args.global_certificate = [path.resolve() for path in args.global_certificate]
    if args.global_exe is not None:
        args.global_exe = args.global_exe.resolve()
    if args.out == args.exact_run or args.out in args.existing_run:
        parser.error("study output must differ from every imported run directory")
    return args


def main(argv=None):
    args = parse_args(argv)
    runs, commands = orchestrate_restarts(args)
    summary = aggregate(args, runs, commands)
    for item in summary["sizes"]:
        print(f"m={item['m']} unique={item['unique_graphs']} exact={item['exact_graphs']} "
              f"best_lower={item['best_known_lower_bound']} unresolved={item['unresolved_graphs']} "
              f"strong_challengers={item['strong_challengers']} global_maximum={item['global_maximum']}")
    print(f"Unified study: {args.out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"family1_study: {error}", file=sys.stderr)
        raise SystemExit(1)

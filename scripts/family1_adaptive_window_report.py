#!/usr/bin/env python3
"""Independently audit and publish sealed deterministic adaptive-window runs.

This script launches no search. Reference H and historical pair certificates
are loaded only after native output seals, geometry, arithmetic and every new
positive have been checked. Historical certificate floors never receive
credit as results of the new finder.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import statistics

REPO = Path(__file__).resolve().parents[1]
ALPHABET = ["00", "01", "10", "11"]
BAD_M7 = "0102000304050203000604050003"
M8_LEADER = "01020003040501060003020705060407"


def rows(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def pin(path):
    path = Path(path).resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def check_pin(value):
    path = Path(value["path"])
    if not path.is_absolute():
        path = REPO / path
    actual = pin(path)
    assert actual["sha256"] == value["sha256"], f"Changed sealed file: {path}"
    if "bytes" in value:
        assert actual["bytes"] == value["bytes"], path
    return path


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def table_key(table):
    assert table and all(len(p) == 2 for p in table)
    assert all(type(q) is int and 0 <= q < len(table) for p in table for q in p)
    seen, todo = {0}, [0]
    while todo:
        for q in table[todo.pop()]:
            if q not in seen:
                seen.add(q)
                todo.append(q)
    assert len(seen) == len(table), "Family 1 input must be root-accessible"
    return "".join(f"{q:02d}" for p in table for q in p)


def graph_only_cases(paths):
    """Importable preparation helper: discard every score, pair and ordinal."""
    result = {}
    for path in paths:
        for row in rows(path):
            table = row["canonical_table"]
            key = table_key(table)
            result[len(table), key] = {"m": len(table), "key": key, "canonical_table": table}
    return [result[key] for key in sorted(result)]


class ScalarAudit:
    """Independent scalar endpoints on every ORIGINAL static mask."""
    def __init__(self, cases):
        self.tables = {row["key"]: row["canonical_table"] for row in cases}
        self.profiles = {key: {"": (0,) * (1 << len(table))} for key, table in self.tables.items()}
        self.permutations = {}
        self.positive_mask_replays = 0
        self.parent_mask_comparisons = 0
        self.profile_mask_steps = 0

    def profile(self, key, word):
        assert set(word) <= {"0", "1"}
        cache, table = self.profiles[key], self.tables[key]
        if word in cache:
            return cache[word]
        depth = len(word)
        while word[:depth] not in cache:
            depth -= 1
        for end in range(depth + 1, len(word) + 1):
            symbol = int(word[end - 1])
            previous = cache[word[:end - 1]]
            cache[word[:end]] = tuple(table[q][symbol ^ ((mask >> q) & 1)]
                                      for mask, q in enumerate(previous))
            self.profile_mask_steps += len(previous)
        return cache[word]

    def metric(self, key, first, second):
        left, right = self.profile(key, first), self.profile(key, second)
        if key not in self.permutations:
            table = self.tables[key]
            m = len(table)
            self.permutations[key] = tuple(
                all(len({table[q][symbol ^ ((mask >> q) & 1)] for q in range(m)}) == m
                    for symbol in [0, 1]) for mask in range(1 << m))
        flags = self.permutations[key]
        return sum(a != b for a, b in zip(left, right)), sum(
            a != b and eligible for a, b, eligible in zip(left, right, flags))

    def positive(self, key, pair, expected_trace=None):
        assert isinstance(pair, list) and len(pair) == 2
        a, b = pair
        assert a and a != b and len(a) == len(b) and set(a + b) <= {"0", "1"}
        trace = [self.metric(key, a[:i], b[:i])[0] for i in range(len(a) + 1)]
        assert trace[0] == trace[-1] == 0, (key, pair)
        if expected_trace is not None:
            assert trace == expected_trace, (key, "scalar prefix trace mismatch")
        self.positive_mask_replays += 1 << len(self.tables[key])
        return trace


def histogram(value):
    if isinstance(value, list):
        result = {i: int(n) for i, n in enumerate(value) if n}
    else:
        result = {int(k): int(n) for k, n in value.items() if n}
    assert all(1 <= k <= 8 and n > 0 for k, n in result.items())
    return result


def json_cell(value):
    return json.dumps(value, separators=(",", ":"))


def k_label(row):
    sequence = row["producing_k_sequence"]
    if not sequence:
        return "N/A (bounded seed collision)" if row["upper_bound"] is not None else "no witness"
    runs = []
    for k in sequence:
        if runs and runs[-1][0] == k:
            runs[-1][1] += 1
        else:
            runs.append([k, 1])
    path = "→".join(str(k) if n == 1 else f"{k}×{n}" for k, n in runs)
    lo, hi = row["configured_k_min"], row["configured_k_max"]
    return f"{lo}" + (f"..{hi}" if hi != lo else "") + f"; winning lookaheads {path}"


def verify_record(row, config, case, manifest, scalar):
    assert row["key"] == case["key"] and row["m"] == case["m"]
    assert row["canonical_table"] == case["canonical_table"]
    assert row["source_sha256"] == manifest["source_sha256"]
    assert row["config"] == config["name"] and row["policy"] == config["policy"]
    for a, b in [("configured_k_min", "min_k"), ("configured_k_max", "max_k"),
                 ("threshold_ppm", "threshold_ppm"), ("beam_width", "beam_width"),
                 ("priority", "priority"), ("advance", "advance")]:
        assert row[a] == config[b], (row["config"], a)
    assert row["exact_depth"] == 0 and row["lower_bound"] == 1
    assert row["randomness"] is False and row["time_caps"] is False
    assert row["alphabet"] == ALPHABET and row["partial_windows"] == 0
    assert row["max_length"] == manifest["max_length"]
    assert row["expansion_cap"] == manifest["expansions_per_attempt"]
    completed = histogram(row["completed_k_histogram"])
    tested = histogram(row["tested_k_histogram"])
    selected = histogram(row["selected_k_histogram"])
    assert sum(completed.values()) == row["complete_layers"] == row["completed_layers"]
    assert sum(tested.values()) == row["criterion_windows"] == row["complete_windows"]
    assert sum((4 ** k) * n for k, n in completed.items()) == row["expanded_nodes"]
    assert all(tested.get(k, 0) <= completed.get(k, 0) for k in tested)
    assert all(n <= tested.get(k, 0) for k, n in selected.items())
    assert all(k <= config["max_k"] for h in [completed, tested, selected] for k in h)
    assert row["attempts"] + row["skipped_starts"] == row["selected_starts"]
    assert row["starts_per_ranking"] == manifest["starts_per_ranking"]
    assert 0 <= row["capped_attempts"] <= row["attempts"]
    sequence = row["producing_k_sequence"]
    assert all(type(k) is int and 1 <= k <= config["max_k"] for k in sequence)
    if row["upper_bound"] is None:
        assert row["witness"] is None and not sequence and row["winning_k"] is None
        assert row["witness_metric_trace"] == row["synchronized_count_trace"] == []
        assert not row["minimality_certified"]
        return
    trace = scalar.positive(row["key"], row["witness"], row["witness_metric_trace"])
    assert row["upper_bound"] == len(row["witness"][0]) <= row["max_length"]
    assert row["synchronized_count_trace"] == [(1 << row["m"]) - d for d in trace]
    assert row["minimality_certified"] == (row["upper_bound"] == 1)
    a, b = row["winning_seed"]
    assert a and a != b and len(a) == len(b)
    assert row["witness"][0].startswith(a) and row["witness"][1].startswith(b)
    if sequence:
        assert row["winning_k"] == sequence[-1] and row["producer"] == "joint-window"
    else:
        assert row["winning_k"] is None and row["producer"] == "bounded-seed-collision"
        assert row["winning_seed"] == row["witness"]


def verify_moment(window, parent, config, mask_count):
    k = int(window["k"])
    n, total, square = (int(window[name]) for name in ["n", "sumD", "sumD2"])
    assert n == 4 ** k and 1 <= k <= config["max_k"]
    assert 0 <= window["minD"] <= window["maxD"] <= mask_count
    assert n * window["minD"] <= total <= n * window["maxD"]
    assert n * window["minD"] ** 2 <= square <= n * window["maxD"] ** 2
    assert len(window["action_n"]) == len(window["action_sumD"]) == 4
    assert window["action_n"] == [n // 4] * 4
    assert sum(window["action_sumD"]) == total
    assert all(0 <= value <= n // 4 * mask_count for value in window["action_sumD"])
    numerator = n * square - total * total
    action = 4 * sum(value * value for value in window["action_sumD"]) - total * total
    denominator = n * n * mask_count * mask_count
    assert numerator == int(window["total_numerator"]) >= action == int(window["action_numerator"]) >= 0
    assert denominator == int(window["denominator"]) and 4 * numerator <= denominator
    if "D_histogram" in window:
        bins = window["D_histogram"]
        assert bins and [d for d, _ in bins] == sorted({d for d, _ in bins})
        assert all(type(d) is int and 0 <= d <= mask_count and type(count) is int and count > 0
                   for d, count in bins)
        assert sum(count for _, count in bins) == n
        assert sum(d * count for d, count in bins) == total
        assert sum(d * d * count for d, count in bins) == square
        assert bins[0][0] == window["minD"] and bins[-1][0] == window["maxD"]
    eligible = k >= min(config["min_k"], parent["selected_k"])
    assert window["criterion_eligible"] == eligible
    chosen = action if config["policy"] == "action-roll" else numerator
    met = chosen * 1000000 >= denominator * config["threshold_ppm"]
    if eligible:
        assert window["criterion_met"] == met
    if "action_minD" in window:
        assert len(window["action_minD"]) == 4
        assert min(window["action_minD"]) == window["minD"]
        assert all(window["minD"] <= d <= window["maxD"] for d in window["action_minD"])
    if "progress_met" in window:
        best = int(window["best_leaf_priority"]), int(window["best_leaf_D"])
        assert 0 <= best[0] <= best[1] <= mask_count
        old = int(parent["parent_priority"]), int(parent["parent_D"])
        assert window["progress_met"] == (best < old)
        required = config.get("require_improvement", config["policy"] == "progress-roll")
        assert window["adequate"] == (window["criterion_met"] and (not required or window["progress_met"]))
    assert 0 <= window["positive_leaves"] <= n
    if window["positive_leaves"]:
        assert window["minD"] == 0
    if "D_histogram" in window:
        zero_count = next((count for d, count in window["D_histogram"] if d == 0), 0)
        assert window["positive_leaves"] <= zero_count
        if parent["parent_first"] != parent["parent_second"]:
            assert window["positive_leaves"] == zero_count
    return numerator, action, denominator


def inspect_decisions(values, indexed, configs, scalar):
    moments, decisions = [], []
    seen = set()
    for trace in values:
        identity = trace["key"], trace["config"]
        assert identity not in seen and identity in indexed
        seen.add(identity)
        row, config = indexed[identity], configs[trace["config"]]
        assert trace["winning_seed"] == row["winning_seed"]
        assert trace["producing_k_sequence"] == row["producing_k_sequence"]
        assert trace["moments_available"] == (config["policy"] != "fixed-block")
        if not trace["moments_available"]:
            assert not trace["decisions"]
            continue
        observed_sequence = []
        for index, parent in enumerate(trace["decisions"]):
            a, b = parent["parent_first"], parent["parent_second"]
            assert len(a) == len(b) == parent["depth"]
            D, P = scalar.metric(row["key"], a, b)
            scalar.parent_mask_comparisons += 1 << row["m"]
            assert D == parent["parent_D"]
            assert parent["parent_priority"] == (P if config["priority"] else 0)
            if row["witness"]:
                assert row["witness"][0].startswith(a) and row["witness"][1].startswith(b)
            windows = parent["windows"]
            if parent["minimum_refused"]:
                assert not windows and parent["selected_k"] == 0
            else:
                assert [w["k"] for w in windows] == list(range(1, parent["selected_k"] + 1))
            if parent["selected_k"]:
                observed_sequence.append(parent["selected_k"])
            base = dict(config=row["config"], m=row["m"], key=row["key"], decision_index=index,
                        depth=parent["depth"], parent_first=a, parent_second=b,
                        parent_D=D, parent_priority=parent["parent_priority"], selected_k=parent["selected_k"],
                        reason=parent["reason"], selected=parent["selected"], minimum_refused=parent["minimum_refused"])
            decisions.append(base)
            for window in windows:
                total, action, denominator = verify_moment(window, parent, config, 1 << row["m"])
                moments.append(base | {name: json_cell(value) if isinstance(value, list) else value
                                       for name, value in window.items()} |
                               {"total_variance_ppm": total * 1000000 / denominator,
                                "action_variance_ppm": action * 1000000 / denominator,
                                "moment_population": "all 4^k joint leaves",
                                "trace_scope": "winning-attempt ancestry only"})
        assert observed_sequence == row["producing_k_sequence"]
    assert seen == set(indexed), "Missing decision journal row"
    return decisions, moments


def load_references(cases, scalar):
    """Called ONLY after every native byte seal and new witness is verified."""
    keys = {case["key"] for case in cases}
    truth, prior, sources, prior_checks = {}, {}, [], 0
    paths = [REPO / "results/family1-m1-m6/maximizers.jsonl",
             REPO / "results/family1-m7/maximizers.jsonl",
             REPO / "results/family1-neighbor-seeds/near-top.jsonl",
             REPO / "results/family1-adaptive-search-final/records.jsonl",
             REPO / "results/family1-finder-strategies-20261026/near/records-frontier.jsonl",
             REPO / "results/family1-finder-strategies-20261026/near/records-m8.jsonl"]
    champions = set()
    for path in paths:
        if not path.exists():
            continue
        sources.append(pin(path))
        for row in rows(path):
            key = table_key(row["canonical_table"])
            if path.name == "maximizers.jsonl":
                champions.add(key)
            if key not in keys:
                continue
            if row.get("status") == "exact":
                H = row.get("merge_length", row.get("upper_bound"))
                if H is not None:
                    assert key not in truth or truth[key] == H
                    truth[key] = H
            upper = row.get("upper_bound", row.get("merge_length"))
            pair = row.get("witness")
            if upper is None or not pair:
                continue
            assert len(pair[0]) == upper
            scalar.positive(key, pair)
            prior_checks += 1 << len(row["canonical_table"])
            if key not in prior or upper < prior[key]["upper"]:
                if row.get("producer") == "exact-word-layers":
                    label = "N/A (exact word layers)"
                elif row.get("alphabet") == ALPHABET and isinstance(row.get("k"), int):
                    label = f"joint k={row['k']}"
                else:
                    label = "unknown (historical certificate)"
                prior[key] = dict(upper=upper, witness=pair, source=pin(path), producing_k_label=label)
    assert len({key for key in champions if len(key) == 28}) == 8
    return truth, prior, champions, sources, prior_checks


def quality(group, truth, prior, champions, band):
    positive = [r for r in group if r["upper_bound"] is not None]
    known = [r for r in group if r["key"] in truth]
    gaps = [r["upper_bound"] - truth[r["key"]] for r in known if r["upper_bound"] is not None]
    assert all(gap >= 0 for gap in gaps)
    hist = lambda field: dict(sorted(sum((Counter(histogram(r[field])) for r in group), Counter()).items()))
    non7 = [r for r in group if r["m"] == 7 and r["key"] not in champions]
    top = max((r["upper_bound"] for r in positive), default=None)
    head = [r for r in positive if r["upper_bound"] >= top - band] if top is not None else []
    proven = [{"key": r["key"], "returned_upper": r["upper_bound"], "prior_verified_upper": prior[r["key"]]["upper"],
               "error_lower_bound": r["upper_bound"] - prior[r["key"]]["upper"]}
              for r in positive if r["key"] in prior and r["upper_bound"] > prior[r["key"]]["upper"] + 2]
    return dict(cases=len(group), found=len(positive), misses=len(group) - len(positive),
                exact_reference_cases=len(known), optimal=sum(gap == 0 for gap in gaps),
                within_one=sum(gap <= 1 for gap in gaps), within_two=sum(gap <= 2 for gap in gaps),
                median_gap_if_found=statistics.median(gaps) if gaps else None,
                maximum_gap_if_found=max(gaps, default=None), bounded_seed_collisions=sum(
                    r["producer"] == "bounded-seed-collision" for r in positive),
                expanded_nodes=sum(r["expanded_nodes"] for r in group),
                complete_layers=sum(r["complete_layers"] for r in group),
                criterion_windows=sum(r["criterion_windows"] for r in group),
                capped_attempts=sum(r["capped_attempts"] for r in group),
                refused_layers=sum(r["refused_layers"] for r in group),
                completed_k_histogram=hist("completed_k_histogram"),
                tested_k_histogram=hist("tested_k_histogram"), selected_k_histogram=hist("selected_k_histogram"),
                per_policy_preprocessing_words=sum(r["seed_words"] for r in group),
                per_policy_candidates_scored=sum(r["candidates_scored"] for r in group),
                m7_nonwinner_cases=len(non7),
                m7_new_finder_exclusions=sum(r["upper_bound"] is not None and r["upper_bound"] <= 33 for r in non7),
                m7_false_finite_compatible=sum(r["upper_bound"] is not None and r["upper_bound"] >= 34 for r in non7),
                m7_nonwinner_misses=sum(r["upper_bound"] is None for r in non7),
                finite_topband=dict(width=band, maximum_upper=top, cases=len(head),
                                    certified_winners=sum(r["key"] in champions for r in head),
                                    rows=[{"key": r["key"], "upper": r["upper_bound"]} for r in head]),
                proven_error_above_two=proven)


def write_csv_chunks(folder, stem, values, limit=750000):
    if not values:
        return []
    fields = list(dict.fromkeys(name for value in values for name in value))
    chunks, current = [], []
    def encode(data):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)
        return stream.getvalue()
    # Keep complete rows; every shard repeats the header.
    size = len(encode([]).encode())
    for value in values:
        stream = io.StringIO(newline="")
        csv.DictWriter(stream, fieldnames=fields).writerow(value)
        row_size = len(stream.getvalue().encode())
        assert row_size < limit, "One CSV row exceeds the artifact size limit"
        if current and size + row_size > limit:
            chunks.append(current)
            current, size = [], len(encode([]).encode())
        current.append(value)
        size += row_size
    if current:
        chunks.append(current)
    paths = []
    for i, data in enumerate(chunks):
        path = folder / (f"{stem}.csv" if len(chunks) == 1 else f"{stem}-{i:03d}.csv")
        path.write_text(encode(data))
        assert path.stat().st_size <= 1048576
        paths.append(path)
    return paths


def figures(folder, records, cases, decisions, truth, prior, champions, manifest, all_figures):
    import hard_pair_witness_figure as drawing
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    folder.mkdir(parents=True, exist_ok=True)
    if any(folder.iterdir()):
        raise ValueError("Use a fresh figure directory")
    lines = ["# Adaptive joint-window figures", "",
             "Exact oracle disabled. k labels state the configured range and actual winning lookahead sequence.",
             "An empty sequence is a bounded seed collision (k=N/A), not an exact-layer search.", "",
             "Default display selects one shortest NEW result per graph, breaking ties by configuration name.",
             "This is post-hoc display selection, not an evaluated portfolio or a quality/cost improvement.",
             "Every case/configuration pair remains in the complete CSV tables.", "",
             "| Configuration | m | Key | Producing k | L | Figure |", "|---|---:|---|---|---:|---|"]
    count = 0
    display = records
    if not all_figures:
        best = {}
        for row in records:
            if row["upper_bound"] is not None:
                key = row["key"]
                if key not in best or (row["upper_bound"], row["config"]) < (best[key]["upper_bound"], best[key]["config"]):
                    best[key] = row
        worst = sorted((r["upper_bound"] - prior[r["key"]]["upper"], r["key"])
                       for r in best.values() if r["key"] in prior)
        shown = champions | {BAD_M7, M8_LEADER} | {key for gap, key in worst[-3:] if gap > 2}
        display = sorted((r for key, r in best.items() if key in shown), key=lambda r: (r["m"], r["key"]))
    for row in display:
        if row["upper_bound"] is None:
            lines.append(f"| {row['config']} | {row['m']} | {row['key']} | no witness | miss | — |")
            continue
        raw = dict(row, k=None, window_kind="adaptive-joint-pair",
                   score="permutation then D" if row["priority"] else "total D",
                   greedy_advance="one joint symbol" if row["advance"] == "first" else "whole joint window block")
        a, b = row["winning_seed"]
        raw["winning_attempt"] = dict(initial_first=a, initial_second=b, initial_length=len(a),
                                     first_greedy_depth=len(a) + row["producing_k_sequence"][0]
                                     if row["producing_k_sequence"] else 0)
        if row["key"] in truth:
            raw.update(reference_H=truth[row["key"]], gap=row["upper_bound"] - truth[row["key"]])
        elif row["key"] in prior:
            raw.update(reference_upper=prior[row["key"]]["upper"],
                       gap_to_known_upper=row["upper_bound"] - prior[row["key"]]["upper"])
        record = drawing.witness_record(raw)
        record["search_parameters"].update(
            k=None, producer_k_known=True, single_k_applicable=False,
            configured_k_min=row["configured_k_min"], configured_k_max=row["configured_k_max"],
            producing_k_sequence=row["producing_k_sequence"], k_label=k_label(row),
            policy=row["policy"], threshold_ppm=row["threshold_ppm"],
            priority=row["priority"], advance=row["advance"], exact_depth=0)
        record["source_native_minimality_certified"] = row["minimality_certified"]
        record["new_finder_result_not_historical_floor"] = True
        record["source"] = dict(manifest=pin(cases["work"] / "manifest.json"),
                                records=pin(cases["work"] / "records.jsonl"))
        visual = deepcopy(record)
        visual["search_parameters"]["k"] = k_label(row) + f"; {row['policy']}; threshold {row['threshold_ppm']}ppm"
        directory = folder / f"{row['config']}-m{row['m']}-{row['key']}"
        directory.mkdir()
        save(directory / "witness.json", record)
        (directory / "witness.svg").write_text(drawing.figure_svg(visual, [row["canonical_table"]]))
        lines.append(f"| {row['config']} | {row['m']} | {row['key']} | {k_label(row)} | {row['upper_bound']} | "
                     f"[pair and D trace]({directory.name}/witness.svg) |")
        count += 1
    (folder / "README.md").write_text("\n".join(lines) + "\n")
    return count


def chart(folder, summaries, starts):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(summaries)
    labels = []
    for name in names:
        config = summaries[name]["configuration"]
        span = str(config["min_k"])
        if config["max_k"] != config["min_k"]:
            span += ".." + str(config["max_k"])
        threshold = ("N/A" if config["policy"].startswith("fixed-")
                     else f"{config['threshold_ppm']:,} ppm")
        labels.append(f"{name}\njoint k={span}\nthreshold {threshold}")
    x = list(range(len(names)))
    plt.rcParams["svg.hashsalt"] = "family1-adaptive-window-20261027"
    fig, axes = plt.subplots(2, 2, figsize=(max(14, len(names) * 1.8), 10))
    for ax, subset, title in [(axes[0, 0], "all", "All cases"),
                               (axes[0, 1], "m6_m7", "m=6,7 subset: window-policy stress cases")]:
        for shift, field, label, color in [(-0.25, "found", "Found", "#98a8b4"),
                                           (0, "within_one", "L ≤ H+1", "#248e88"),
                                           (0.25, "optimal", "L = H", "#725e95")]:
            ax.bar([i + shift for i in x], [summaries[name][subset][field] for name in names],
                   width=.23, label=label, color=color)
        ax.set_title(title, loc="left")
        ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper right")
        ax.set_ylim(0, max((summaries[name][subset]["cases"] for name in names), default=1) * 1.2)
        ax.set_ylabel("Cases")
    work = [summaries[name]["all"]["expanded_nodes"] / 1e6 for name in names]
    axes[1, 0].bar(x, work, color="#536f84")
    axes[1, 0].set_title("All attempted joint work (million node expansions)", loc="left")
    bottom = [0.0] * len(names)
    for k in range(1, 9):
        values = []
        for name in names:
            h = summaries[name]["all"]["selected_k_histogram"]
            values.append(h.get(k, 0) / max(1, sum(h.values())))
        if any(values):
            axes[1, 1].bar(x, values, bottom=bottom, label=f"k={k}")
            bottom = [a + b for a, b in zip(bottom, values)]
    axes[1, 1].set_title("Selected/provisional parent-probe horizons", loc="left")
    axes[1, 1].legend(frameon=False, ncol=3, fontsize=8, loc="upper right")
    axes[1, 1].set_ylim(0, 1.25)
    for ax in axes.flat:
        ax.set_xticks(x, labels, rotation=65, ha="right", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.15)
        ax.set_axisbelow(True)
    fig.text(.06, .025, f"Oracle disabled; {starts} starts per ranking; all4 joint symbols. "
             "Growing k reuses completed layers. Known-H quality metrics retain misses in their denominators.\n"
             "Seed collisions have no producing k. Provisional horizons may belong to budget-aborted attempts; "
             "winning sequences are recorded separately.", fontsize=9)
    fig.subplots_adjust(left=.06, right=.99, top=.94, bottom=.25, wspace=.24, hspace=1.15)
    fig.savefig(folder / "quality-and-work.svg", facecolor="white", metadata={"Date": None})
    plt.close(fig)


def publication_readme(folder, manifest, summaries, case_files, moment_files):
    lines = ["# Deterministic adaptive joint-window benchmark", "",
             f"This sealed run contains {len(manifest['cases'])} graphs and {len(summaries)} configurations. "
             f"Each configuration uses {manifest['starts_per_ranking']} starts per seed ranking. "
             "The exact oracle is disabled (`exact_depth=0`); every returned distinct word pair was independently "
             "replayed on every original static mask before reference values were loaded.", "",
             "All joint lookaheads use the complete alphabet `00,01,10,11`. A complete depth-k window "
             "contains all `4^k` leaves, including identical word pairs for its moments. Only distinct word pairs "
             "can supply positive certificates. The empty pair has D=0; D counts unequal endpoints and the "
             "synchronized count is N−D, where N=2^m.", "",
             "For n=4^k, the normalized total variance is `(n sum(D^2) − sum(D)^2)/(n^2 N^2)`. "
             "The normalized action variance is `(4 sum_a(sum_a D)^2 − sum(D)^2)/(n^2 N^2)`: "
             "the population variance of the four conditional **mean** D values, not their minima. "
             "Thresholds use parts per million and comparisons use exact integer arithmetic. "
             "Growing k reuses the completed layers; work is `sum_k 4^k * completed_layers[k]`.", "",
             "| Configuration | Policy | Joint k | Threshold ppm | Found | L=H | L≤H+1 | L≤H+2 | m=6,7 L=H | Joint expansions | Capped attempts |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, value in summaries.items():
        config, all_cases, hard = value["configuration"], value["all"], value["m6_m7"]
        k = str(config["min_k"])
        if config["max_k"] != config["min_k"]:
            k += ".." + str(config["max_k"])
        lines.append(f"| {name} | {config['policy']} | {k} | {config['threshold_ppm']} | "
                     f"{all_cases['found']}/{all_cases['cases']} | {all_cases['optimal']}/{all_cases['exact_reference_cases']} | "
                     f"{all_cases['within_one']}/{all_cases['exact_reference_cases']} | "
                     f"{all_cases['within_two']}/{all_cases['exact_reference_cases']} | "
                     f"{hard['optimal']}/{hard['exact_reference_cases']} | {all_cases['expanded_nodes']:,} | "
                     f"{all_cases['capped_attempts']} |")
    lines += ["", "Known-H columns include every exact-reference graph in their denominators; misses do not count "
              "as within any gap. Unknown-H results remain upper-bound certificates. Historical verified upper "
              "bounds are stored separately from each new finder result and receive no new-finder success credit.", "",
              "The seed catalogue and rankings are shared across compared configurations for each graph. "
              "Per-policy joint work includes all attempts, including failed or capped ones. Seed preprocessing "
              "is reported both once per graph and as the cost each policy would incur alone; selecting the "
              "shortest display pair does not define a costed portfolio.", "",
              "Detailed moments cover **winning-attempt ancestry only**. Aggregate k histograms cover all attempts. "
              "Selected-k histograms may include provisional horizons from aborted decisions; actual winning "
              "sequences are recorded separately. A refused growth layer ends that attempt without committing "
              "a last-eligible-k fallback. A bounded failure supplies no negative proof.", "",
              "Actual words, D traces, configured k ranges and producing k sequences are retained in every "
              "case/configuration CSV row. A bounded seed collision has producing k=N/A; its empty sequence "
              "does not indicate a missing parameter. The default figure display chooses one shortest new result "
              "per graph with a lexical configuration tie break, explicitly as post-hoc display selection.", "",
              "The variance criterion is not a global quality certificate. Even an eligible adequate window need "
              "not lower D at the next committed symbol, and permutation-first progress can improve its primary "
              "objective while increasing D. Local search results never certify a universal approximation error.", "",
              "Files:", "", "- [Summary and subgroup metrics](summary.json)",
              "- [Independent validation](validation.json)", "- [Frozen run parameters](run.json)",
              "- [Query seals](query-audit.json)"]
    lines += [f"- [Actual pair results: {path.name}]({path.name})" for path in case_files]
    lines += [f"- [Winning ancestry moments: {path.name}]({path.name})" for path in moment_files]
    (folder / "README.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--figures", type=Path)
    parser.add_argument("--no-figures", action="store_true")
    parser.add_argument("--all-pair-figures", action="store_true")
    parser.add_argument("--band", type=int, default=2)
    args = parser.parse_args()
    args.work, args.out = args.work.resolve(), args.out.resolve()
    assert args.band >= 0 and (not args.out.exists() or not any(args.out.iterdir()))
    manifest = json.loads((args.work / "manifest.json").read_text())
    seal = json.loads((args.work / "query-seal.json").read_text())
    assert manifest["oracle_disabled"] and manifest["exact_depth"] == 0
    assert manifest["randomness"] is False and manifest["time_caps"] is False
    assert manifest["alphabet"] == ALPHABET
    assert seal["all_configured_cases_completed"] and seal["truth_not_used_in_queries"]
    assert check_pin(seal["records"]) == args.work / "records.jsonl"
    check_pin(manifest["executable"])
    for item in manifest["source_inventory"]:
        path = args.work / "native/sources" / item["path"]
        assert pin(path)["sha256"] == item["sha256"]
    fingerprint = hashlib.sha256("".join(item["sha256"] + "\n" for item in manifest["source_inventory"]).encode()).hexdigest()
    assert fingerprint == manifest["source_sha256"]
    cases = manifest["cases"]
    assert len({row["key"] for row in cases}) == len(cases)
    for row in cases:
        assert not {"witness", "H", "reference_H", "merge_length", "upper_bound", "lower_bound"} & row.keys()
        assert row["key"] == table_key(row["canonical_table"]) and row["m"] == len(row["canonical_table"])
    configs = {row["name"]: row for row in manifest["configurations"]}
    case_map = {row["key"]: row for row in cases}
    records = rows(args.work / "records.jsonl")
    indexed = {(row["key"], row["config"]): row for row in records}
    expected = {(case["key"], config) for case in cases for config in configs}
    assert len(records) == len(indexed) == len(expected) and set(indexed) == expected
    assert seal["rows"] == len(records) and seal["case_count"] == len(cases)
    scalar = ScalarAudit(cases)
    for row in records:
        verify_record(row, configs[row["config"]], case_map[row["key"]], manifest, scalar)
    native_decisions, improvement_count = [], 0
    last_improvement = {}
    for item in seal["native_journals"]:
        path = check_pin(item)
        if path.name == "decisions.jsonl":
            native_decisions.extend(rows(path))
        elif path.name == "improvements.jsonl":
            for row in rows(path):
                identity = row["key"], row["config"]
                assert identity in indexed
                assert row["upper_bound"] == len(row["witness"][0])
                assert row["upper_bound"] < last_improvement.get(identity, 1 << 60)
                last_improvement[identity] = row["upper_bound"]
                scalar.positive(row["key"], row["witness"], row["witness_metric_trace"])
                improvement_count += 1
        elif path.name == "records.jsonl":
            for row in rows(path):
                assert row == indexed[row["key"], row["config"]]
    for identity, row in indexed.items():
        assert row["upper_bound"] == last_improvement.get(identity)
    decisions, moments = inspect_decisions(native_decisions, indexed, configs, scalar)
    # Prior certificates and H labels cannot affect any validation/query above.
    new_mask_checks = scalar.positive_mask_replays
    truth, prior, champions, reference_sources, prior_checks = load_references(cases, scalar)
    summaries, output_rows = {}, []
    for name, config in configs.items():
        group = [row for row in records if row["config"] == name]
        summaries[name] = dict(configuration=config)
        for subset, selected in [("all", group), ("m6_m7", [r for r in group if r["m"] in [6, 7]]),
                                 ("m7", [r for r in group if r["m"] == 7])]:
            summaries[name][subset] = quality(selected, truth, prior, champions, args.band)
        for row in group:
            upper = row["upper_bound"]
            H = truth.get(row["key"])
            if upper is not None and H is not None:
                assert upper >= H
            certificate = prior.get(row["key"])
            old_upper = certificate["upper"] if certificate else None
            floor = min(value for value in [upper, old_upper] if value is not None) if upper is not None or old_upper is not None else None
            output_rows.append({name: row[name] for name in [
                "config", "m", "key", "policy", "advance", "priority", "configured_k_min", "configured_k_max",
                "threshold_ppm", "beam_width", "producer", "upper_bound", "lower_bound", "expanded_nodes",
                "complete_layers", "criterion_windows", "capped_attempts", "refused_layers", "attempts",
                "skipped_starts", "selected_starts", "seed_words", "candidates_scored"]} |
                dict(producing_k_label=k_label(row), producing_k_sequence=json_cell(row["producing_k_sequence"]),
                     completed_k_histogram=json_cell(row["completed_k_histogram"]),
                     tested_k_histogram=json_cell(row["tested_k_histogram"]),
                     selected_k_histogram=json_cell(row["selected_k_histogram"]),
                     reference_H=H, gap_if_H_known=upper - H if upper is not None and H is not None else None,
                     prior_verified_upper=old_upper, prior_producing_k_label=certificate["producing_k_label"] if certificate else "",
                     excess_over_prior_upper=upper - old_upper if upper is not None and old_upper is not None else None,
                     certificate_floor_upper=floor, floor_is_new_finder_result=False,
                     certificate_floor_owner="none" if floor is None else "new" if upper is not None and upper == floor else "historical",
                     prior_improves_floor=old_upper is not None and (upper is None or old_upper < upper),
                     first=row["witness"][0] if upper is not None else "", second=row["witness"][1] if upper is not None else "",
                     D_trace=json_cell(row["witness_metric_trace"])))
    shared_words = shared_scored = 0
    for case in cases:
        group = [indexed[case["key"], name] for name in configs]
        for field in ["seed_words", "candidates_scored", "selected_starts", "catalogue_sha256"]:
            assert len({row[field] for row in group}) == 1, f"Unmatched seed inputs: {field}"
        shared_words += group[0]["seed_words"]
        shared_scored += group[0]["candidates_scored"]
    args.out.mkdir(parents=True, exist_ok=True)
    case_files = write_csv_chunks(args.out, "cases", output_rows)
    decision_files = write_csv_chunks(args.out, "winning-decisions", decisions)
    moment_files = write_csv_chunks(args.out, "winning-window-moments", moments)
    write_csv_chunks(args.out, "input-cases", [dict(m=r["m"], key=r["key"], canonical_table=json_cell(r["canonical_table"])) for r in cases])
    save(args.out / "run.json", manifest)
    save(args.out / "query-audit.json", seal)
    save(args.out / "summary.json", dict(
        schema=1, work=pin(args.work / "manifest.json"), query_seal=pin(args.work / "query-seal.json"),
        graph_cases=len(cases), graph_queries=len(records), oracle_disabled=True, exact_depth=0,
        configurations=summaries, seed_words_shared_once_per_graph=shared_words,
        candidates_scored_shared_once_per_graph=shared_scored, truth_sources=reference_sources,
        prior_certificate_floor_separate_from_new_finder=True, universal_error_bound_certified=False,
        moment_scope="complete all-leaf moments along winning-attempt ancestry only; misses have no winning moments",
        histogram_scope="all attempts; selected horizons can be provisional on budget-aborted decisions",
        budget_policy="a refused growth layer ends that attempt; no commit of a last-eligible-k fallback",
        variance_definition="D counts ORIGINAL unequal endpoint coordinates; synchronized count N-D has the same variance",
        action_variance_definition="population variance across the four conditional MEAN D values, not action minima",
        source_fingerprint=fingerprint))
    figure_count = 0
    if not args.no_figures:
        figure_folder = args.figures
        if figure_folder is None:
            try:
                relative = args.out.relative_to(REPO / "results")
                figure_folder = REPO / "output/figures" / relative
            except ValueError:
                figure_folder = args.out / "figures"
        figure_count = figures(figure_folder, records, {"work": args.work}, decisions, truth, prior,
                               champions, manifest, args.all_pair_figures)
        chart(figure_folder, summaries, manifest["starts_per_ranking"])
    save(args.out / "validation.json", dict(
        passed=True, graph_queries=len(records), all_case_config_combinations_verified=True,
        positive_and_improvement_mask_replays=new_mask_checks, historical_certificate_mask_replays=prior_checks,
        parent_metric_mask_comparisons=scalar.parent_mask_comparisons, scalar_profile_mask_steps=scalar.profile_mask_steps,
        native_improvements_checked=improvement_count, winning_decisions_checked=len(decisions),
        winning_window_moments_checked=len(moments), moments_use_exact_integer_arithmetic=True,
        source_and_executable_pins_checked=True, partial_windows=0, positive_figures=figure_count,
        cases_files=[pin(path) for path in case_files], decision_files=[pin(path) for path in decision_files],
        moments_files=[pin(path) for path in moment_files], report_source=pin(Path(__file__))))
    publication_readme(args.out, manifest, summaries, case_files, moment_files)
    files = sorted(path for path in args.out.iterdir() if path.is_file())
    assert all(path.stat().st_size <= 1048576 for path in files)
    save(args.out / "publication-manifest.json", {"files": [pin(path) for path in files]})
    print(json.dumps(dict(out=str(args.out), queries=len(records), configurations=len(configs),
                          winning_moments_checked=len(moments), figures=figure_count, passed=True)))


if __name__ == "__main__":
    main()

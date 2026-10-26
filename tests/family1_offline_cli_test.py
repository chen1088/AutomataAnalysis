#!/usr/bin/env python3
"""Independent integration checks for the dependency-free Family1Offline CLI.

The reference enumerates every labelled sorted-port table and every root-fixing
permutation. Its scorer keeps fresh scalar static-mask vectors at each length.
It imports no search, canonicalization or finder implementation from the repo.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
from itertools import combinations_with_replacement, permutations, product
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def reachable(table):
    seen, todo = {0}, [0]
    while todo:
        for target in table[todo.pop()]:
            if target not in seen:
                seen.add(target)
                todo.append(target)
    return len(seen) == len(table)


def canonical(table):
    result = []
    for tail in permutations(range(1, len(table))):
        order = (0, *tail)
        inverse = {old: new for new, old in enumerate(order)}
        result.append(tuple(tuple(sorted(inverse[t] for t in table[old])) for old in order))
    return min(result)


def key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def endpoint(table, mask, word):
    state = 0
    for symbol in word:
        state = table[state][int(symbol) ^ ((mask >> state) & 1)]
    return state


def shortest(table):
    """Direct breadth layers, without a visited set shared between lengths."""
    masks = range(1 << len(table))
    previous = [tuple(0 for _ in masks)]
    for depth in range(1, 17):
        seen, following = {}, []
        for profile in previous:
            for symbol in (0, 1):
                successor = tuple(table[state][symbol ^ ((mask >> state) & 1)]
                                  for mask, state in enumerate(profile))
                if successor in seen:
                    return depth
                seen[successor] = True
                following.append(successor)
        previous = following
    raise AssertionError("small reference depth unexpectedly exhausted")


@lru_cache(maxsize=None)
def reference(m):
    rows = list(combinations_with_replacement(range(m), 2))
    classes = set()
    for table in product(rows, repeat=m):
        if reachable(table):
            classes.add(canonical(table))
    return {key(table): (table, shortest(table)) for table in sorted(classes)}


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def read_run(directory):
    rows = read_rows(directory / "records.jsonl")
    best = read_rows(directory / "best.jsonl")
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8-sig"))
    return rows, best, summary


def verify_record(record):
    table = tuple(tuple(row) for row in record["canonical_table"])
    m = record["m"]
    assert len(table) == m and all(len(row) == 2 for row in table), record
    assert all(type(t) is int and 0 <= t < m for row in table for t in row), record
    assert reachable(table) and canonical(table) == table and key(table) == record["key"], record
    lower, upper = record["lower_bound"], record["upper_bound"]
    assert type(lower) is int and lower >= 1, record
    assert upper is None or type(upper) is int and upper >= lower, record
    witness = record["witness"]
    if witness is not None:
        assert len(witness) == 2 and witness[0] != witness[1], record
        assert len(witness[0]) == len(witness[1]) == upper, record
        assert all(set(word) <= {"0", "1"} for word in witness), record
        assert all(endpoint(table, mask, witness[0]) == endpoint(table, mask, witness[1])
                   for mask in range(1 << m)), record
        assert record["static_masks_verified"] == 1 << m, record
    else:
        assert upper is None, record
    if record["status"] == "exact":
        assert record["merge_length"] == lower == upper and witness is not None, record
        assert record["estimate_certified"] is True, record
    else:
        assert record["merge_length"] is None and record["estimate_certified"] is False, record
        if upper is not None:
            assert record["estimated_merge_length"] == max(lower, upper - 1), record
    return table


def verify_distributions(record, maximum):
    reports = record["window_distributions"]
    assert len(reports) <= maximum and type(record["window_reports_truncated"]) is int
    assert record["window_reports_truncated"] >= 0
    for report in reports:
        span, count = report["window_k"], report["window_count"]
        assert 1 <= span <= 16 and 0 <= count <= 1 << span, report
        assert report["mask_count"] == 1 << record["m"], report
        assert 0 <= report["initial_remaining"] <= report["mask_count"], report
        if report["complete"]:
            assert count == 1 << span, report
        assert 0 <= report["expanded_nodes"] <= (1 << (span + 1)) - 2, report
        histogram = report["histogram"]
        assert len(histogram) <= 64 and sum(frequency for _, frequency in histogram) == count, report
        assert [drop for drop, _ in histogram] == sorted({drop for drop, _ in histogram}), report
        assert all(type(frequency) is int and frequency > 0 for _, frequency in histogram), report
        assert report["histogram_bin_width"] >= 1
        assert not ({"ranked", "leaves", "windows"} & report.keys()), report
        if count:
            assert 0 <= report["min_drop"] <= report["mean_drop"] <= report["max_drop"] <= report["initial_remaining"], report
            assert report["min_drop"] <= report["median_drop"] <= report["max_drop"], report
            assert report["variance_drop"] >= 0 and report["stddev_drop"] >= 0, report
            assert math.isclose(report["variance_drop"], report["stddev_drop"] ** 2, rel_tol=1e-9, abs_tol=1e-9), report
            if report["histogram_exact"]:
                assert report["histogram_bin_width"] == 1
                assert histogram[0][0] == report["min_drop"] and histogram[-1][0] == report["max_drop"], report
                mean = sum(drop * frequency for drop, frequency in histogram) / count
                assert math.isclose(mean, report["mean_drop"], rel_tol=1e-9, abs_tol=1e-9), report
                assert dict(histogram).get(0, 0) == report["zero_drop_count"], report


def exercise(executable, directory):
    directory.mkdir(parents=True, exist_ok=True)
    invocations = 0

    def run(name, m, mode="off", *extra, success=True, reuse=False):
        nonlocal invocations
        target = directory / name
        command = [str(executable), "--m", str(m), "--heuristics", mode,
                   "--out", str(target), "--per-graph-ms", "10000", "--memory-mib", "64", *extra]
        if reuse:
            command.append("--resume")
        completed = subprocess.run(command, text=True, capture_output=True, timeout=120)
        invocations += 1
        assert (completed.returncode == 0) is success, (command, completed.returncode, completed.stdout, completed.stderr)
        return target

    exact = {}
    for m, count, maximum, ties in ((1, 1, 1, 1), (2, 6, 3, 1), (3, 57, 6, 2), (4, 678, 10, 1)):
        expected = reference(m)
        assert len(expected) == count and max(score for _, score in expected.values()) == maximum
        target = run(f"exact-{m}", m, "off", "--depth", "12", "--dot")
        rows, best, summary = read_run(target)
        assert len(rows) == count and len({r["key"] for r in rows}) == count, summary
        assert [r["key"] for r in rows] == sorted(expected), (m, "nondeterministic or omitted classes")
        for record in rows:
            table = verify_record(record)
            assert expected[record["key"]] == (table, record["merge_length"]), record
        winners = {graph for graph, (_, score) in expected.items() if score == maximum}
        assert len(winners) == ties and {row["key"] for row in best} == winners, (m, best)
        assert len(best) == ties
        assert summary["enumeration_complete"] is True and summary["scoring_complete"] is True, summary
        assert summary["global_maximum_certified"] is True, summary
        assert summary["maximizing_collection_complete"] is True and summary["maximum_merge_length"] == maximum, summary
        assert list(target.rglob("*.dot")), "--dot did not export drawings"
        exact[m] = (target, rows, best, summary)
    print("Independent exhaustive agreement: every score and maximizing class for m=1,2,3,4.")

    # The m=2 maximum has loops and mask-dependent revisits. A global visited
    # set across lengths, or changing a mask bit on revisit, gives a wrong score.
    two = ((0, 1), (0, 1))
    assert shortest(two) == 3
    assert all(endpoint(two, mask, "010") == endpoint(two, mask, "100") for mask in range(4))
    assert any(endpoint(two, mask, "0") != endpoint(two, mask, "1") for mask in range(4))

    capped = run("depth-capped", 3, "off", "--depth", "2")
    rows, _, summary = read_run(capped)
    assert summary["enumeration_complete"] is True and summary["scoring_complete"] is False, summary
    assert not summary["global_maximum_certified"] and summary["maximum_merge_length"] is None, summary
    assert not summary["maximizing_collection_complete"], summary
    assert any(row["status"] == "depth-capped" for row in rows), rows
    for record in rows:
        verify_record(record)
        if record["status"] == "depth-capped":
            assert record["lower_bound"] == 3 and record["merge_length"] is None, record
    print("Depth-capped scores preserve lower bounds and withhold global claims.")

    constrained = run("resource-capped", 2, "off", "--depth", "12", "--max-layer-states", "1")
    rows, best, summary = read_run(constrained)
    assert len(rows) == 6 and not best and summary["enumeration_complete"] is True, summary
    assert not summary["scoring_complete"] and not summary["global_maximum_certified"], summary
    for record in rows:
        verify_record(record)
        assert record["status"] == "incomplete" and record["lower_bound"] == 1, record

    limited = run("graph-capped", 4, "off", "--depth", "12", "--max-graphs", "3")
    rows, _, summary = read_run(limited)
    assert len(rows) == 3 and not summary["enumeration_complete"], summary
    assert not summary["global_maximum_certified"] and summary["maximum_merge_length"] is None, summary
    assert not summary["maximizing_collection_complete"], summary
    first_keys = [row["key"] for row in rows]
    run("graph-capped", 4, "off", "--depth", "12", "--max-graphs", "3", reuse=True)
    rows, _, summary = read_run(limited)
    assert len(rows) == 6 and [row["key"] for row in rows[:3]] == first_keys, (rows, summary)
    assert not summary["global_maximum_certified"], summary

    # Two genuinely distinct rooted classes attain H=6; keep both even when the
    # supplied subset is not the complete graph universe.
    winners3 = exact[3][2]
    extras = ["--depth", "12"]
    for row in winners3:
        extras += ["--graph", row["key"]]
    subset = run("subset-ties", 3, "off", *extras)
    rows, best, summary = read_run(subset)
    assert len(rows) == len(best) == 2 and {r["key"] for r in best} == {r["key"] for r in winners3}
    assert not summary["global_maximum_certified"] and summary["maximum_merge_length"] is None, summary

    before = {name: (subset / name).read_bytes() for name in ("run.json", "records.jsonl", "best.jsonl")}
    run("subset-ties", 3, "off", *extras, reuse=True)
    assert all((subset / name).read_bytes() == value for name, value in before.items()), "Completed resume changed saved scores"
    run("subset-ties", 3, "off", *extras, "--seed", "17", reuse=True, success=False)
    assert all((subset / name).read_bytes() == value for name, value in before.items()), "Rejected resume modified saved results"
    print("Subset ties retained; identical resume reused scores and mismatched configuration was rejected.")

    tampered = run("tampered-journal", 2, "off", "--depth", "12")
    journal = tampered / "checkpoint.journal"
    content = journal.read_bytes()
    assert content and content.endswith(b"\n")
    # Flip a complete committed byte without changing line length or truncating
    # the record. A checksum failure must not be treated as a torn final write.
    journal.write_bytes((b"0" if content[:1] != b"0" else b"1") + content[1:])
    before = {path.relative_to(tampered): path.read_bytes() for path in tampered.rglob("*") if path.is_file()}
    run("tampered-journal", 2, "off", "--depth", "12", reuse=True, success=False)
    after = {path.relative_to(tampered): path.read_bytes() for path in tampered.rglob("*") if path.is_file()}
    assert before == after, "Rejected corrupted journal changed the saved evidence"
    print("Complete checksum-corrupted journal rejected without modifying saved evidence.")

    # Force the native heuristic route by disabling exact prescoring. These
    # inputs cover loops, coincident ports, and a static-mask revisit collision.
    heuristic_options = ["--exact-depth", "0", "--window", "2", "--max-window", "2", "--beam", "4",
                         "--prefix-depth", "6", "--prefix-words", "128", "--prefix-pairs", "32",
                         "--tail-threshold", "8", "--tail-states", "10000", "--tail-depth", "16",
                         "--expansions", "100000", "--max-length", "16"]
    for label, table in (("one", ((0, 0),)), ("coincident", ((1, 1), (1, 1))), ("revisit", two)):
        target = run(f"heuristic-{label}", len(table), "on", "--graph", key(table), *heuristic_options)
        rows, best, summary = read_run(target)
        assert len(rows) == 1 and rows[0]["evaluated"] is True and rows[0]["window_k"] == 2, rows
        record = rows[0]
        verify_record(record)
        assert record["witness"] is not None and record["upper_bound"] >= shortest(table), record
        assert record["lower_bound"] == 1, record
        if record["upper_bound"] > 1:
            assert record["merge_length"] is None and not record["estimate_certified"], record
        assert not summary["global_maximum_certified"], summary
        assert len(best) == 1 and best[0]["key"] == record["key"]
    print("Native heuristic path finds independently replayed static-mask witnesses without exact prescoring.")

    # H=3 is independently known, so a bounded two-letter miss must remain an
    # unknown result rather than manufacture a numerical hardness estimate.
    target = run("heuristic-miss", 2, "on", "--graph", key(two), *heuristic_options,
                 "--max-length", "2", "--prefix-depth", "2")
    rows, best, summary = read_run(target)
    assert len(rows) == 1 and not best, (rows, best)
    verify_record(rows[0])
    assert rows[0]["upper_bound"] is None and rows[0]["estimated_merge_length"] is None, rows[0]
    assert rows[0]["lower_bound"] == 1 and not summary["global_maximum_certified"], summary

    # Disable conditional tails so the common-window route must enumerate
    # actual windows. Short fixed prefixes leave several complete layers before
    # a collision; retaining only one report must record the discarded count.
    window_graph = ((0, 1), (1, 2), (0, 1))
    window_options = ["--graph", key(window_graph), "--exact-depth", "0", "--window", "2", "--max-window", "2",
                      "--beam", "2", "--prefix-depth", "2", "--prefix-words", "4", "--prefix-pairs", "4",
                      "--prefix-samples", "0", "--common-prefix-depth", "0", "--tail-threshold", "0",
                      "--viability-coordinates", "0", "--distance-coordinates", "0",
                      "--tail-states", "100", "--tail-depth", "8", "--expansions", "100", "--max-length", "10"]
    full_windows = run("window-reports-full", 3, "on", *window_options, "--window-reports", "64")
    rows, _, _ = read_run(full_windows)
    record = rows[0]
    verify_record(record)
    verify_distributions(record, 64)
    assert record["window_distributions"] and any(report["complete"] and report["window_k"] == 2
                                                 for report in record["window_distributions"]), record
    assert record["window_reports_truncated"] == 0 and record["expanded_nodes"] > 0 and record["tail_calls"] == 0, record
    limited_windows = run("window-reports-limited", 3, "on", *window_options, "--window-reports", "1")
    rows, _, _ = read_run(limited_windows)
    verify_distributions(rows[0], 1)
    assert len(rows[0]["window_distributions"]) == 1 and rows[0]["window_reports_truncated"] > 0, rows[0]
    assert rows[0]["window_reports_truncated"] + 1 == len(record["window_distributions"]), rows[0]
    disabled_windows = run("window-reports-disabled", 3, "on", *window_options, "--window-reports", "0")
    rows, _, _ = read_run(disabled_windows)
    verify_distributions(rows[0], 0)
    assert rows[0]["window_reports_truncated"] == len(record["window_distributions"]), rows[0]
    assert rows[0]["window_distributions"] == [] and rows[0]["upper_bound"] == record["upper_bound"], rows[0]

    constrained = run("heuristic-memory-capped", 3, "on", "--graph", key(window_graph), *heuristic_options,
                      "--memory-mib", "1", "--window-reports", "1")
    rows, best, summary = read_run(constrained)
    verify_record(rows[0])
    verify_distributions(rows[0], 1)
    assert rows[0]["lower_bound"] == 1 and rows[0]["upper_bound"] is None, rows[0]
    assert rows[0]["estimated_merge_length"] is None and not best and not summary["global_maximum_certified"], summary
    assert "memory budget" in rows[0]["reason"], rows[0]
    print("Window distributions retain complete leaf counts, bounded histograms and truncation metadata; memory caps prove no new bound.")

    generated = run("heuristic-generated", 3, "on", "--exact-depth", "6", "--max-graphs", "1",
                    "--max-paths", "30", "--max-candidates", "5", "--radius", "1")
    rows, _, summary = read_run(generated)
    assert len(rows) > 1 and sum(row["evaluated"] for row in rows) == 1, summary
    assert not summary["global_maximum_certified"] and summary["maximum_merge_length"] is None, summary
    assert summary["pending_graphs"] == len(rows) - 1, summary
    assert [row["key"] for row in rows] == sorted({row["key"] for row in rows})
    for record in rows:
        verify_record(record)
        if not record["evaluated"]:
            assert record["status"] == "not-evaluated" and record["lower_bound"] == 1, record
    run("heuristic-generated", 3, "on", "--exact-depth", "6", "--max-graphs", "1",
        "--max-paths", "30", "--max-candidates", "5", "--radius", "1", reuse=True)
    resumed, _, summary = read_run(generated)
    assert len(resumed) == len(rows) and sum(row["evaluated"] for row in resumed) == 2, summary
    print("Native candidate generation exports pending roots and resumes the bounded evaluation plan.")

    # Direct noncanonical port order must be normalized; repeated class inputs
    # cannot create duplicate entries or collapse a different rooted class.
    duplicate = run("duplicate-inputs", 2, "off", "--graph", key(two), "--graph", key(((1, 0), (1, 0))), "--depth", "12")
    rows, _, _ = read_run(duplicate)
    assert len(rows) == 1 and rows[0]["key"] == key(two), rows

    # Prove the package needs neither the source/data tree nor Python on PATH.
    isolated = directory / "isolated"
    isolated.mkdir()
    portable = isolated / executable.name
    shutil.copy2(executable, portable)
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("VCPKG_ROOT", None)
    environment["PATH"] = str(Path(environment.get("SystemRoot", "C:/Windows")) / "System32") if os.name == "nt" else "/usr/bin:/bin"
    completed = subprocess.run([str(portable), "--m", "2", "--heuristics", "off", "--depth", "8", "--out", "findings"],
                               cwd=isolated, env=environment, text=True, capture_output=True, timeout=120)
    invocations += 1
    assert completed.returncode == 0, (completed.returncode, completed.stdout, completed.stderr)
    _, _, summary = read_run(isolated / "findings")
    assert summary["global_maximum_certified"] and summary["maximum_merge_length"] == 3, summary
    print("Isolated copied executable runs with no source, data, Python, or build-dependency directories on PATH.")

    for options in (("--m", "0"), ("--m", "21"), ("--heuristics", "maybe"), ("--window", "0"),
                    ("--memory-mib", "0"), ("--radius", "4"), ("--viability-coordinates", "1025"),
                    ("--distance-coordinates", "1025"), ("--unknown-option", "1")):
        completed = subprocess.run([str(executable), "--m", "2", "--heuristics", "on", "--out", str(directory / "invalid"), *options],
                                   text=True, capture_output=True, timeout=30)
        invocations += 1
        assert completed.returncode != 0, (options, "invalid configuration accepted")
    print(f"PASS: independent offline CLI validation, {invocations} native invocations.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    executable = args.exe.resolve()
    if args.out:
        exercise(executable, args.out.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="family1-offline-test-") as temporary:
            exercise(executable, Path(temporary))


if __name__ == "__main__":
    main()

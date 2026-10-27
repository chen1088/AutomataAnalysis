#!/usr/bin/env python3
"""Independent scalar and artifact checks for the production near-pair CLI.

Reference enumeration has k=N/A. Native joint examples explicitly use k=4;
only an actual exact-word-layer witness has producing k=null in the journal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from family1_joint_cli_test import (
    canonical, graph_key, pair_metric_trace, profile, reachable,
    read_rows, single_word_shortest, small_classes,
)

REPO = Path(__file__).resolve().parents[1]
ALPHABET = ["00", "01", "10", "11"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_fingerprint():
    cmake = (REPO / "CMakeLists.txt").read_text()
    names = re.search(r"set\(FAMILY1_NEAR_COMPILE_SOURCES\s+(.*?)\)", cmake, re.S)
    assert names, "CMake must declare the compiled source fingerprint inputs"
    paths = [REPO / name for name in names.group(1).split()]
    return hashlib.sha256("".join(sha(path) + "\n" for path in paths).encode()).hexdigest()


def references():
    result = {}
    counts, maxima = {1: 1, 2: 6, 3: 57}, {1: 1, 2: 3, 3: 6}
    for m in range(1, 4):
        tables = small_classes(m)
        assert len(tables) == counts[m]
        result[m] = {}
        for table in tables:
            answer = single_word_shortest(table, max_depth=6)
            assert answer is not None
            result[m][graph_key(table)] = (table, answer[0])
        assert max(answer[1] for answer in result[m].values()) == maxima[m]
    return result


def validate_pair(row, reference):
    table = tuple(tuple(ports) for ports in row["canonical_table"])
    m, key = row["m"], row["key"]
    assert reachable(table) and table == canonical(table) and graph_key(table) == key
    assert row["alphabet"] == ALPHABET and row["configured_joint_k"] == 4
    assert row["deterministic"] is True and row["randomness"] is False and row["time_caps"] is False
    assert row["score"] == "permutation" and row["diagonal_width"] == row["unequal_width"] == 0
    assert row["dfa_count"] == 1 << m
    assert row["global_maximum_certified"] is False and row["near_shortest_error_bound_certified"] is False
    assert row["exact"] == row["minimality_certified"]
    assert 1 <= row["lower_bound"]
    if key in reference:
        assert table == reference[key][0] and row["lower_bound"] <= reference[key][1]
    pair = row["witness"]
    if pair is None:
        assert row["status"] == "unresolved" and row["upper_bound"] is row["producer"] is None
        assert row["exact"] is False and row["static_masks_verified"] == 0
        assert row["witness_metric_trace"] is row["synchronized_count_trace"] is None
        assert row["first_difference_position"] is row["winning_attempt"] is None
        assert row["k"] == 4 and row["window_kind"] == "joint-pair"
        return
    assert len(pair) == 2 and pair[0] != pair[1] and all(word and set(word) <= {"0", "1"} for word in pair)
    assert len(pair[0]) == len(pair[1]) == row["upper_bound"] <= row["max_length"]
    assert row["lower_bound"] <= row["upper_bound"]
    assert row["exact"] == (row["lower_bound"] == row["upper_bound"])
    assert row["status"] == ("exact" if row["exact"] else "verified-upper")
    if key in reference:
        assert row["upper_bound"] >= reference[key][1]
        if row["exact"]:
            assert row["upper_bound"] == reference[key][1]
    assert profile(table, pair[0]) == profile(table, pair[1])
    trace = pair_metric_trace(table, pair)
    assert trace == row["witness_metric_trace"] and trace[0] == trace[-1] == 0
    assert row["synchronized_count_trace"] == [(1 << m) - value for value in trace]
    assert row["static_masks_verified"] == 1 << m
    difference = next(i + 1 for i, (a, b) in enumerate(zip(*pair)) if a != b)
    assert row["first_difference_position"] == difference
    winning = row["winning_attempt"]
    assert winning["first_difference_depth"] == difference
    assert winning["kind"] == row["producer"]
    if row["producer"] == "exact-word-layers":
        assert row["k"] is None and row["window_kind"] == "exact-oracle"
        assert row["oracle_word_alphabet"] == ["0", "1"] and row["exact"]
        assert winning["initial_first"] == winning["initial_second"] == ""
        assert winning["initial_length"] == winning["first_greedy_depth"] == 0
    else:
        assert row["producer"] == "scored-seed-joint"
        assert row["k"] == 4 and row["window_kind"] == "joint-pair"
        first, second = winning["initial_first"], winning["initial_second"]
        assert first and first != second and len(first) == len(second) == winning["initial_length"]
        assert pair[0].startswith(first) and pair[1].startswith(second)
        if trace[len(first)] == 0:
            assert winning["first_greedy_depth"] == 0
        else:
            assert winning["first_greedy_depth"] == len(first) + min(4, winning["effective_max_length"] - len(first))


def cli_checks(executable, directory):
    refs = references()
    directory.mkdir(parents=True, exist_ok=True)
    native_hash, sources_hash = sha(executable), source_fingerprint()
    invocations = pair_checks = mask_checks = 0

    def invoke(name, m, keys, *extra):
        nonlocal invocations, pair_checks, mask_checks
        target = directory / name
        command = [str(executable), "--m", str(m), "--k", "4", "--prefix-depth", "6",
                   "--prefix-words", "64", "--catalogue", "64", "--starts", "16",
                   "--max-length", "8", "--out", str(target)]
        for key in keys:
            command += ["--graph", key]
        command += list(extra)
        process = subprocess.run(command, capture_output=True, text=True, timeout=120)
        invocations += 1
        assert process.returncode == 0, (command, process.stdout, process.stderr)
        assert not list(target.glob("*.tmp")) and not list(target.glob("*.partial.jsonl"))
        for filename in ["run.json", "records.jsonl", "witnesses.jsonl", "summary.json"]:
            assert (target / filename).is_file()
        run = json.loads((target / "run.json").read_text())
        summary = json.loads((target / "summary.json").read_text())
        records, journal = read_rows(target / "records.jsonl"), read_rows(target / "witnesses.jsonl")
        expected = sorted({graph_key(canonical(tuple(tuple(int(key[i + j:i + j + 2]) for j in (0, 2))
                                      for i in range(0, len(key), 4)))) for key in keys})
        assert run["graphs"] == [row["key"] for row in records] == expected
        assert run["supplied_graph_arguments"] == len(keys) and run["unique_graphs"] == len(expected)
        assert run["executable_sha256"] == native_hash and run["source_sha256"] == sources_hash
        assert run["source_fingerprint_method"] == "compile-time build fingerprint"
        run_hash = sha(target / "run.json")
        assert summary["run_sha256"] == run_hash
        assert summary["records_sha256"] == sha(target / "records.jsonl")
        assert summary["witnesses_sha256"] == sha(target / "witnesses.jsonl")
        assert summary["graphs"] == len(records) == len(expected)
        assert summary["all_supplied_graphs_tested"] is True and summary["partial_windows"] == 0
        assert summary["global_maximum_certified"] is summary["near_shortest_error_bound_certified"] is False
        assert summary["verified_pairs"] == sum(row["witness"] is not None for row in records)
        assert summary["no_pair"] == sum(row["witness"] is None for row in records)
        assert summary["exact_graphs"] == sum(row["exact"] for row in records)
        assert summary["journal_pairs"] == len(journal)
        assert summary["expanded_nodes"] == sum(row["expanded_nodes"] for row in records)
        assert summary["complete_windows"] == sum(row["complete_windows"] for row in records)
        assert summary["joint_attempts"] == sum(row["attempts"] for row in records)
        expected_histogram = {}
        for row in records:
            if row["upper_bound"] is not None:
                key = str(row["upper_bound"]); expected_histogram[key] = expected_histogram.get(key, 0) + 1
        assert summary["upper_histogram"] == expected_histogram
        per_graph = {}
        for row in records + journal:
            assert row["run_sha256"] == run_hash and row["m"] == m
            validate_pair(row, refs.get(m, {}))
            pair_checks += row["witness"] is not None
            if row["witness"] is not None:
                mask_checks += 1 << m
        for row in journal:
            assert row["event"] == "improvement" and row["witness"] is not None
            previous = per_graph.setdefault(row["key"], [])
            assert not previous or row["upper_bound"] < previous[-1]["upper_bound"]
            previous.append(row)
        for row in records:
            assert row["event"] == "final" and row["partial_windows"] == 0
            assert row["improvements"] == len(per_graph.get(row["key"], []))
            if row["witness"] is not None:
                assert per_graph[row["key"]][-1]["witness"] == row["witness"]
            else:
                assert row["key"] not in per_graph
        return records, run, target, command

    # Every independently enumerated small class must be found and proved exact.
    for m in range(1, 4):
        records, _, _, _ = invoke(f"all-m{m}", m, list(refs[m]), "--exact-depth", "16")
        assert all(row["exact"] and row["producer"] == "exact-word-layers" and row["k"] is None for row in records)
        assert all(row["attempts"] == row["expanded_nodes"] == 0 for row in records)
        assert all(row["upper_bound"] == refs[m][row["key"]][1] for row in records)

    # Raw port orders and root-fixing relabelings normalize before deduplication.
    table = refs[3]["000101020001"][0]
    order = (0, 2, 1); inverse = {old: new for new, old in enumerate(order)}
    raw = tuple(tuple(inverse[target] for target in reversed(table[old])) for old in order)
    raw_key = graph_key(raw)
    records, run, _, _ = invoke("raw-dedup", 3,
        ["000101020001", raw_key, "000101020001", "010202020101"])
    assert run["supplied_graph_arguments"] == 4 and len(records) == 2

    # A joint-produced witness can meet the exact lower without being an
    # oracle-produced witness. Its producing k must remain joint k=4.
    records, _, target, command = invoke("joint-meets-lower", 2, ["00010001"], "--exact-depth", "2")
    row = records[0]
    assert row["exact"] and row["lower_bound"] == row["upper_bound"] == 3
    assert row["producer"] == "scored-seed-joint" and row["k"] == 4
    repeated, _, again, _ = invoke("joint-repeat", 2, ["00010001"], "--exact-depth", "2")
    assert repeated == records
    assert {p.name: p.read_bytes() for p in target.iterdir()} == {p.name: p.read_bytes() for p in again.iterdir()}

    records, _, _, _ = invoke("too-short", 2, ["00010001"], "--max-length", "2")
    row = records[0]
    assert row["witness"] is None and row["lower_bound"] == 3 and row["length_limit_reached"]
    assert row["attempts"] == row["candidates_scored"] == 0

    records, _, _, _ = invoke("whole-window-refusal", 2, ["00010001"],
        "--exact-depth", "0", "--prefix-depth", "2", "--prefix-words", "4", "--expansions", "1")
    row = records[0]
    assert row["witness"] is None and row["lower_bound"] == 1
    assert row["expanded_nodes"] == row["complete_windows"] == row["partial_windows"] == 0
    assert row["windows_refused"] > 0 and row["expansion_limit_reached"] and row["exact_status"] == "disabled"

    records, _, _, _ = invoke("compact", 2, ["00010001"], "--exact-depth", "0",
        "--seed-mode", "compact", "--seed-ranking", "full", "--catalogue", "4", "--starts", "2")
    row = records[0]
    assert row["upper_bound"] == 3 and row["producer"] == "scored-seed-joint"
    assert row["seed_mode"] == "compact" and row["prefix_pair_capped"]
    assert "per-layer" in row["seed_catalogue_rule"]
    assert row["candidates_scored"] <= row["catalogue_size"] * row["prefix_completed_depth"]
    assert row["seed_candidates_selected"] <= row["selected_pairs"] == 2

    for ranking in ["common-max", "common-sum", "portfolio"]:
        records, run, _, _ = invoke(f"ranking-{ranking}", 2, ["00010001"],
            "--exact-depth", "0", "--seed-ranking", ranking)
        row = records[0]
        assert row["upper_bound"] == 3 and not row["exact"] and row["k"] == 4
        assert run["seed_ranking"] == row["seed_ranking"] == ranking
        assert row["common_distance_pair_states"] == 16
        assert row["prefix_words_evaluated"] == 126
    records, _, _, _ = invoke("compact-common", 2, ["00010001"], "--exact-depth", "0",
        "--seed-mode", "compact", "--seed-ranking", "common-max", "--catalogue", "4", "--starts", "2")
    assert records[0]["upper_bound"] == 3 and records[0]["common_distance_pair_states"] == 16
    assert records[0]["prefix_words_evaluated"] == 126

    records, _, _, _ = invoke("compact-fallback", 8, ["01010202030304040505060607070000"],
        "--exact-depth", "0", "--seed-mode", "compact", "--prefix-depth", "3",
        "--prefix-words", "8", "--catalogue", "4", "--starts", "2")
    row = records[0]
    assert row["upper_bound"] == 1 and row["exact"] and row["static_masks_verified"] == 256
    assert row["producer"] == "scored-seed-joint" and row["k"] == 4
    assert row["witness_metric_trace"] == [0, 0]
    assert "global" in row["seed_catalogue_rule"] and row["candidates_scored"] <= 4

    # Existing output must be immutable, including an otherwise valid rerun.
    saved = {p.name: p.read_bytes() for p in target.iterdir()}
    process = subprocess.run(command, capture_output=True, text=True, timeout=120); invocations += 1
    assert process.returncode != 0 and "fresh empty" in process.stderr
    assert saved == {p.name: p.read_bytes() for p in target.iterdir()}
    occupied = directory / "occupied"; occupied.mkdir(); (occupied / "marker").write_text("preserve")
    bad = [str(executable), "--m", "2", "--graph", "00010001", "--out", str(occupied)]
    process = subprocess.run(bad, capture_output=True, text=True, timeout=120); invocations += 1
    assert process.returncode != 0 and (occupied / "marker").read_text() == "preserve"
    assert list(occupied.iterdir()) == [occupied / "marker"]

    bad_options = [
        ["--k", "0"], ["--k", "9"], ["--beam", "0"], ["--max-length", "0"],
        ["--exact-depth", "31"], ["--exact-words", "0"], ["--prefix-words", "0"],
        ["--expansions", "0"], ["--expansions", "-1"], ["--seed-mode", "random"],
        ["--seed-mode", "compact", "--catalogue", "1", "--starts", "2"],
        ["--exact-memory-mib", "18446744073709551615"], ["--seconds", "1"],
        ["--graph", "00000101"], ["--m", "3"],
        ["--seed-ranking", "random"],
    ]
    for index, extra in enumerate(bad_options):
        out = directory / f"invalid-{index:02d}"
        command = [str(executable), "--m", "2", "--graph", "00010001", "--out", str(out)] + extra
        process = subprocess.run(command, capture_output=True, text=True, timeout=120); invocations += 1
        assert process.returncode != 0, (command, process.stdout, process.stderr)
        assert not out.exists() or not list(out.iterdir())
    assert sha(executable) == native_hash
    return {"passed": True, "reference_k": None, "joint_k": 4,
            "independent_small_classes": sum(len(values) for values in refs.values()),
            "cli_invocations": invocations, "verified_pair_rows": pair_checks,
            "independent_word_pair_mask_replays": mask_checks,
            "executable_sha256": native_hash, "source_sha256": sources_hash,
            "script_sha256": sha(Path(__file__)), "artifact_hashes_and_immutability": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out:
        assert not args.out.exists(), "use a fresh output directory"
        result = cli_checks(args.exe.resolve(), args.out.resolve())
        (args.out / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    else:
        with tempfile.TemporaryDirectory(prefix="family1-near-cli-") as temporary:
            result = cli_checks(args.exe.resolve(), Path(temporary))
    print(json.dumps(result))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Independently check Family1 adapter traces and conditional exact-tail proofs."""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from family1_threshold_cli_test import canonical, classes, endpoint, exact_score, key


def remaining_pairs(table, first, second):
    result = []
    for mask in range(1 << len(table)):
        a, b = endpoint(table, mask, first), endpoint(table, mask, second)
        if a != b:
            result.append((mask, a, b))
    return tuple(result)


def shortest_suffix(table, coordinates):
    initial = tuple(tuple(item) for item in coordinates if item[1] != item[2])
    queue, seen = deque([(initial, "")]), {initial}
    while queue:
        pairs, suffix = queue.popleft()
        if not pairs:
            return suffix
        for letter in (0, 1):
            result = []
            for mask, a, b in pairs:
                a = table[a][letter ^ ((mask >> a) & 1)]
                b = table[b][letter ^ ((mask >> b) & 1)]
                if a != b:
                    result.append((mask, a, b))
            state = tuple(result)
            if state not in seen:
                seen.add(state)
                assert len(seen) <= 100000
                queue.append((state, suffix + str(letter)))
    return None


def verify_result(result, table):
    table = canonical(table)
    assert result["canonical_table"] == list(map(list, table)) and result["key"] == key(table)
    assert result["lower_bound"] == 1 and result["shortest_proved"] is False
    attempt = result["guided_attempt"]
    assert attempt["score_scope"] == "full" and attempt["total_masks"] == 1 << len(table)
    first, second = attempt["initial_words"]
    suffix = attempt["suffix"]
    expected = [(1 << len(table)) - len(remaining_pairs(table, first + suffix[:n], second + suffix[:n]))
                for n in range(len(suffix) + 1)]
    assert attempt["score_trace"] == expected and attempt["merged_count"] == expected[-1]
    assert expected == sorted(expected)
    if result["decision"] == "collision":
        left, right = result["witness"]
        assert left != right and len(left) == len(right) == result["upper_bound"] <= result["length"]
        assert not remaining_pairs(table, left, right)
        assert result["scalar_witness_masks_verified"] == 1 << len(table)
    else:
        assert result["decision"] == "unknown" and result["upper_bound"] is None and result["witness"] is None
    proof = result["exact_tail"]
    if proof is not None:
        assert proof["global_shortest"] is False
        coordinates = proof["conditional_coordinates"]
        assert len({item[0] for item in coordinates}) == len(coordinates)
        if proof["shortest_conditional"]:
            assert proof["status"] == "found" and not proof["capped"]
            reference = shortest_suffix(table, coordinates)
            assert reference is not None and len(reference) == len(proof["suffix"])
        if proof["capped"]:
            assert proof["shortest_conditional"] is False
        if proof["status"] == "unreachable":
            assert shortest_suffix(table, coordinates) is None
        if proof.get("chosen_for_best_witness"):
            a, b = proof["conditional_prefix_words"]
            actual = remaining_pairs(table, a, b)
            assert {item[0] for item in actual} == {item[0] for item in coordinates}
            by_mask = {mask: {x, y} for mask, x, y in actual}
            assert all({item[1], item[2]} == by_mask[item[0]] for item in coordinates)
            tail = proof["conditional_tail_suffix"]
            assert result["witness"] == [a + tail, b + tail]


def snapshot(directory):
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


def exercise(executable, directory):
    directory.mkdir(parents=True, exist_ok=True)
    counter = proofs = 0

    def run(table, length=None, *extra):
        nonlocal counter, proofs
        counter += 1
        output = directory / f"case-{counter:03d}"
        length = length or (2 * exact_score(table) + 8)
        command = [str(executable), "--graph", key(table), "--out", str(output), "--mode", "finder",
                   "--length", str(length), "--samples", "16", "--seed", "1088", "--window-k", "2",
                   "--beam-width", "4", "--tail-threshold", "4", "--tail-max-states", "100000",
                   "--best-of-seeds", *extra]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        assert completed.returncode == 0, (command, completed.stdout, completed.stderr)
        result = json.loads(completed.stdout)
        verify_result(result, table)
        assert result["config_sha256"] == hashlib.sha256((output / "run.json").read_bytes()).hexdigest()
        if result["traversal_complete"]:
            data = (output / "result.json").read_bytes()
            assert json.loads(data) == result
            assert (output / "result.sha256").read_text().strip() == hashlib.sha256(data).hexdigest()
        else:
            assert not (output / "result.json").exists()
        if result["exact_tail"] and result["exact_tail"]["shortest_conditional"]:
            proofs += 1
        return result, output, command

    hits = distance_hits = 0
    for m in (1, 2, 3):
        for table in classes(m):
            result, _, _ = run(table)
            if result["decision"] == "collision":
                hits += 1
                assert result["upper_bound"] >= exact_score(table)
            bounded, _, _ = run(table, None, "--distance-coordinates", "128", "--viability-coordinates", "128",
                                 "--beam-ranking", "remaining")
            if bounded["decision"] == "collision":
                distance_hits += 1
                assert bounded["upper_bound"] >= exact_score(table)
    assert counter == 128

    two = ((0, 1), (0, 1))
    result, _, _ = run(two)
    assert result["decision"] == "collision" and result["upper_bound"] == 3
    plateau = ((0, 1), (1, 2), (0, 0))
    result, _, _ = run(plateau)
    assert result["upper_bound"] == 4
    hard = ((0, 1), (1, 2), (0, 1))
    result, _, _ = run(hard, None, "--samples", "1", "--tail-max-states", "1")
    assert result["module_stats"]["tail_calls"] >= 1
    assert result["last_exact_tail"]["capped"] is True
    assert result["last_exact_tail"]["shortest_conditional"] is False

    partial, output, command = run(two, None, "--samples", "16", "--limit-samples", "1")
    assert partial["samples_completed"] == 1 and partial["traversal_complete"] is False
    resumed = subprocess.run(command + ["--resume", "--limit-samples", "0"], capture_output=True, text=True, timeout=30)
    assert resumed.returncode == 0, resumed.stderr
    resumed = json.loads(resumed.stdout)
    verify_result(resumed, two)
    assert resumed["traversal_complete"] is True and resumed["upper_bound"] == 3
    before = snapshot(output)
    for extra in (("--window-k", "1"), ("--tail-threshold", "2"), ("--tail-max-states", "1"),
                  ("--max-expansions", "10001")):
        failed = subprocess.run(command + ["--resume", *extra], capture_output=True, text=True, timeout=30)
        assert failed.returncode != 0
        assert before == snapshot(output)

    # Large windows still detect intermediate completions, and their work is
    # bounded by the explicitly pinned per-seed node budget.
    for k in (8, 10, 12, 16):
        result, output, _ = run(plateau, 4, "--samples", "1", "--window-k", str(k),
                                "--first-prefix", "01", "--second-prefix", "10",
                                "--tail-threshold", "0", "--max-expansions", "200000",
                                "--prefix-depth", "1", "--prefix-max-words", "4194304",
                                "--prefix-samples-per-depth", "4194304")
        assert result["upper_bound"] == 4
        assert result["module_stats"]["max_expansions_per_seed"] == 200000
        config = json.loads((output / "run.json").read_text())
        assert config["max_expansions"] == config["full_guidance_max_nodes"] == 200000
    result, _, _ = run(plateau, 4, "--samples", "1", "--window-k", "16",
                       "--first-prefix", "01", "--second-prefix", "10",
                       "--tail-threshold", "0", "--max-expansions", "1")
    assert result["decision"] == "unknown" and result["module_stats"]["expanded_nodes"] == 1
    assert result["module_stats"]["expansion_limits_reached"] == 1

    result, output, command = run(plateau, 3, "--samples", "1", "--first-prefix", "01", "--second-prefix", "10",
                                  "--tail-threshold", "0", "--viability-coordinates", "0",
                                  "--distance-coordinates", "128", "--beam-ranking", "remaining")
    assert result["decision"] == "unknown" and result["module_stats"]["expanded_nodes"] == 0
    assert result["module_stats"]["distance_bound_checks"] == result["module_stats"]["distance_bound_pruned_nodes"] == 1
    config = json.loads((output / "run.json").read_text())
    assert config["distance_coordinates"] == 128 and config["beam_ranking"] == "remaining"
    before = snapshot(output)
    for changed in (("--distance-coordinates", "127"), ("--beam-ranking", "drop")):
        failed = subprocess.run(command + ["--resume", *changed], capture_output=True, text=True, timeout=30)
        assert failed.returncode != 0 and snapshot(output) == before
    partial, output, command = run(plateau, 4, "--samples", "16", "--first-prefix", "01", "--second-prefix", "10",
                                  "--tail-threshold", "0", "--viability-coordinates", "1024",
                                  "--distance-coordinates", "128", "--beam-ranking", "remaining", "--limit-samples", "1")
    resumed = subprocess.run(command + ["--resume", "--limit-samples", "0"], capture_output=True, text=True, timeout=30)
    assert resumed.returncode == 0, resumed.stderr
    resumed = json.loads(resumed.stdout)
    verify_result(resumed, plateau)
    uninterrupted, _, _ = run(plateau, 4, "--samples", "16", "--first-prefix", "01", "--second-prefix", "10",
                              "--tail-threshold", "0", "--viability-coordinates", "1024",
                              "--distance-coordinates", "128", "--beam-ranking", "remaining")
    for field in ("expanded_nodes", "distance_bound_checks", "distance_bound_pruned_nodes", "obstruction_pruned_nodes"):
        assert resumed["module_stats"][field] == uninterrupted["module_stats"][field]
    assert resumed["witness"] == uninterrupted["witness"]
    result, output, command = run(two, 8, "--samples", "16", "--prefix-depth", "4",
                                  "--prefix-max-words", "16", "--prefix-max-pairs", "16",
                                  "--prefix-common-depth", "2")
    assert result["upper_bound"] == 3
    prefix_stats = result["prefix_seed_stats"]
    assert prefix_stats["common_prefix_depth"] == 2
    assert sum(row["pairs"] for row in prefix_stats["selected_pairs_by_actual_common_prefix"]) == prefix_stats["pairs"]
    assert json.loads((output / "run.json").read_text())["prefix_common_depth"] == 2
    before = snapshot(output)
    failed = subprocess.run(command + ["--resume", "--prefix-common-depth", "1"],
                            capture_output=True, text=True, timeout=30)
    assert failed.returncode != 0 and snapshot(output) == before

    # Independently replay all 4096 windows from an exact full-family plateau.
    distribution_command = [str(executable), "--graph", key(plateau), "--mode", "distribution",
                            "--first-prefix", "01", "--second-prefix", "10", "--window-k", "12"]
    for budget in (10000, 20):
        output = directory / f"large-distribution-{budget}"
        completed = subprocess.run(distribution_command + ["--out", str(output), "--max-expansions", str(budget)],
                                   capture_output=True, text=True, timeout=30)
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        distribution = result["window_distribution"]
        assert distribution["expanded_nodes"] <= budget
        assert distribution["complete"] is (budget == 10000)
        assert distribution["expansion_limit_reached"] is (budget == 20)
        entries = distribution["windows"]
        if budget == 10000:
            assert len(entries) == 4096
        assert len({entry["window"] for entry in entries}) == len(entries)
        for entry in entries:
            expected_remaining = len(remaining_pairs(plateau, "01" + entry["window"], "10" + entry["window"]))
            assert entry["remaining_count"] == expected_remaining
            assert entry["drop"] == 4 - expected_remaining
        if budget == 10000:
            assert distribution["expanded_nodes"] == 8190
            assert distribution["zero_drop_count"] == 2 and distribution["full_merge_count"] == 4094
        else:
            assert not (output / "result.json").exists()
    print(json.dumps({"passed": True, "rooted_classes": 64, "hits": hits, "distance_remaining_hits": distance_hits,
                      "conditional_proofs_independently_checked": proofs,
                      "all_mask_witnesses_replayed": True, "full_metric_traces_checked": True,
                      "capped_tails_not_shortest": True, "partial_resume_checked": True,
                      "large_windows_checked": [8, 10, 12, 16], "large_distribution_windows_replayed": 4096,
                      "explicit_expansion_caps_and_resume_guard_checked": True,
                      "admissible_distance_pruning_and_rank_resume_checked": True,
                      "common_prefix_stratification_flag_and_resume_checked": True,
                      "global_shortestness_not_inferred_from_suffix_BFS": True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    executable = args.exe.resolve()
    if args.work_dir:
        exercise(executable, args.work_dir.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="family1-finder-cli-") as temporary:
            exercise(executable, Path(temporary))


if __name__ == "__main__":
    main()

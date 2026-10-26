#!/usr/bin/env python3
"""Independent coordinate-score, plateau, permutation-gate and guided CLI checks."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import tempfile

from family1_threshold_cli_test import canonical, classes, endpoint, exact_score, key


def permutation_masks(table):
    m = len(table)
    return [mask for mask in range(1 << m)
            if all(len({table[state][letter ^ ((mask >> state) & 1)] for state in range(m)}) == m
                   for letter in (0, 1))]


def coordinate_score(table, first, second, masks=None):
    masks = list(range(1 << len(table))) if masks is None else list(masks)
    matched_bits = sum((endpoint(table, mask, first) == endpoint(table, mask, second)) << index
                       for index, mask in enumerate(masks))
    count = sum(endpoint(table, mask, first) == endpoint(table, mask, second) for mask in masks)
    assert matched_bits.bit_count() == count
    return count


def trace(table, first, second, suffix, masks=None):
    return [coordinate_score(table, first + suffix[:length], second + suffix[:length], masks)
            for length in range(len(suffix) + 1)]


def mathematical_checks():
    graph_count = pair_count = trace_count = 0
    for m in (1, 2, 3):
        for table in classes(m):
            graph_count += 1
            perm = permutation_masks(table)
            for n in range(1, 4):
                words = list(map("".join, itertools.product("01", repeat=n)))
                for first, second in itertools.combinations(words, 2):
                    pair_count += 1
                    obstruction = sum(endpoint(table, mask, first) != endpoint(table, mask, second) for mask in perm)
                    for depth in range(3):
                        for suffix in map("".join, itertools.product("01", repeat=depth)):
                            values = trace(table, first, second, suffix)
                            assert values == sorted(values)
                            assert values[-1] <= (1 << m) - obstruction
                            trace_count += 1
    assert graph_count == 64 and pair_count == 2240
    plateau = ((0, 1), (1, 2), (0, 0))
    assert exact_score(plateau) == 4 and permutation_masks(plateau) == []
    assert trace(plateau, "01", "10", "00") == [4, 4, 8]
    assert trace(plateau, "01", "10", "11") == [4, 4, 8]
    assert coordinate_score(plateau, "010", "100") == coordinate_score(plateau, "011", "101") == 4
    gated = ((0, 1), (0, 2), (1, 2))
    assert permutation_masks(gated) == [2, 5] and exact_score(gated) == 4
    assert all(endpoint(gated, mask, "01") != endpoint(gated, mask, "10") for mask in (2, 5))
    assert coordinate_score(gated, "01", "10") == 0
    print(f"PASS: {graph_count} tiny classes, {pair_count} pairs, {trace_count} complete-mask suffix traces/popcounts, monotonicity and permutation obstruction.")
    return {"rooted_classes": graph_count, "word_pairs": pair_count, "suffix_traces": trace_count,
            "plateau": {"key": key(plateau), "initial_words": ["01", "10"], "suffix": "00", "full_score_trace": [4, 4, 8], "denominator": 8, "exact_H": 4},
            "gate": {"key": key(gated), "initial_words": ["01", "10"], "permutation_masks": [2, 5], "mismatch_count": 2, "full_score": 0, "denominator": 8}}


def verify_attempt(result):
    table = result["canonical_table"]
    attempt = result["guided_attempt"]
    assert attempt is not None
    first, second = attempt["initial_words"]
    assert first != second and len(first) == len(second) > 0 and set(first + second) <= {"0", "1"}
    suffix = attempt["suffix"]
    assert set(suffix) <= {"0", "1"}
    masks = attempt["sampled_masks"]
    assert 1 <= len(masks) <= 64 and len(masks) == len(set(masks))
    assert all(0 <= mask < (1 << len(table)) for mask in masks)
    assert attempt["total_masks"] == len(masks)
    expected = trace(table, first, second, suffix, masks)
    assert attempt["score_trace"] == expected, (attempt, expected)
    assert expected == sorted(expected) and attempt["merged_count"] == expected[-1]
    full = len(masks) == (1 << len(table))
    assert attempt["score_scope"] == ("full" if full else "sampled")
    perm = permutation_masks(table)
    mismatches = sum(endpoint(table, mask, first) != endpoint(table, mask, second) for mask in perm)
    assert attempt["permutation_mismatch_count"] == mismatches
    assert attempt["gate_blocked"] is (mismatches > 0)
    assert result["permutation_gate_checked_all_masks"] is True
    assert result["permutation_mask_count"] == len(perm)
    assert result["permutation_masks"] == perm
    exact = result["exact_best_agreement"]
    full_trace = trace(table, first, second, suffix)
    assert exact["score_scope"] == "full" and exact["total_masks"] == 1 << len(table)
    assert exact["score_trace"] == full_trace and exact["merged_count"] == full_trace[-1]
    assert exact["permutation_mismatch_count"] == mismatches
    if attempt["scalar_first_separator"] is not None:
        separator = attempt["scalar_first_separator"]
        assert 0 <= separator < (1 << len(table))
        assert endpoint(table, separator, first + suffix) != endpoint(table, separator, second + suffix)
    if mismatches:
        assert suffix == "" and result["decision"] == "unknown"
    if result["decision"] == "collision":
        witness = result["witness"]
        assert witness == [first + suffix, second + suffix]
        assert witness[0] != witness[1]
        assert result["upper_bound"] == result["witness_length"] == len(witness[0]) == len(witness[1])
        assert result["witness_length"] <= result["requested_length"]
        assert coordinate_score(table, *witness) == 1 << len(table)
        assert attempt["full_scalar_verified"] is True
    else:
        assert result["decision"] == "unknown" and result["upper_bound"] is None and result["witness"] is None
    assert result["lower_bound"] == 1
    return attempt


def exercise(executable, directory):
    directory.mkdir(parents=True, exist_ok=True)
    counter = 0

    def run(table, length=6, *extra):
        nonlocal counter
        counter += 1
        output = directory / f"case-{counter:03d}"
        args = [str(executable), "--graph", key(table), "--out", str(output), "--length", str(length),
                "--mode", "guided", "--samples", "1", "--seed", "1088", "--masks", "64",
                "--beam-width", "16", "--lookahead", "4", "--full-agreement", *extra]
        completed = subprocess.run(args, text=True, capture_output=True, timeout=30)
        assert completed.returncode == 0, (args, completed.stdout, completed.stderr)
        result = json.loads(completed.stdout)
        assert result["canonical_table"] == list(map(list, canonical(table)))
        assert result["requested_length"] == length
        verify_attempt(result)
        configuration = (output / "run.json").read_bytes()
        assert result["config_sha256"] == hashlib.sha256(configuration).hexdigest()
        if result["traversal_complete"]:
            data = (output / "result.json").read_bytes()
            assert json.loads(data) == result
            assert (output / "result.sha256").read_text().strip() == hashlib.sha256(data).hexdigest()
        else:
            assert not (output / "result.json").exists()
        return result, output, args

    for m in (1, 2, 3):
        for table in classes(m):
            result, _, _ = run(table)
            assert result["guided_attempt"]["score_scope"] == "full"
            if result["decision"] == "collision":
                assert result["upper_bound"] >= exact_score(table)
    print("PASS: native guided scores/popcounts and monotone suffix traces independently checked on all64 tiny classes.")

    plateau = ((0, 1), (1, 2), (0, 0))
    result, _, _ = run(plateau, 4, "--lookahead", "2", "--beam-width", "4", "--hash-bits", "0")
    assert result["decision"] == "collision" and result["upper_bound"] == 4
    assert result["guided_attempt"]["score_trace"] == [4, 4, 8]
    assert result["guided_attempt"]["suffix"] in ("00", "11")
    neutral, _, _ = run(plateau, 4, "--lookahead", "0", "--beam-width", "4")
    assert neutral["decision"] == "collision" and neutral["upper_bound"] == 4
    assert neutral["guided_attempt"]["score_trace"] == [4, 4, 8]

    gated = ((0, 1), (0, 2), (1, 2))
    result, _, _ = run(gated, 8)
    assert result["decision"] == "unknown" and result["guided_attempt"]["permutation_mismatch_count"] == 2
    assert result["guided_attempt"]["gate_blocked"] is True
    run(((0, 1), (0, 1)), 8, "--first-prefix", "0", "--second-prefix", "1")

    # A sampled score is bound to the masks that produced that trace, even if
    # the all-mask verifier later replaces a sampled mask by a counterexample.
    sampled, _, _ = run(plateau, 4, "--masks", "1")
    assert sampled["guided_attempt"]["score_scope"] == "sampled"
    assert sampled["guided_attempt"]["total_masks"] < 8

    hard = ((0, 1), (1, 2), (0, 1))
    result, output, args = run(hard, 6)
    assert result["decision"] == "collision" and result["upper_bound"] == 6
    assert result["guided_attempt"]["full_scalar_verified"] is True
    original = {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
    resumed = subprocess.run(args + ["--resume"], capture_output=True, text=True, timeout=30)
    assert resumed.returncode == 0 and json.loads(resumed.stdout) == result
    for extra in (("--beam-width", "2"), ("--lookahead", "1"), ("--first-prefix", "00", "--second-prefix", "11")):
        failed = subprocess.run(args + ["--resume", *extra], capture_output=True, text=True, timeout=30)
        assert failed.returncode != 0
        assert original == {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}

    # A blocked fixed prefix lets us pause a genuine guided run without finding
    # a witness. The checkpoint must retain its own score masks and trace.
    partial, _, partial_args = run(gated, 8, "--samples", "4", "--limit-samples", "1",
                                   "--first-prefix", "01", "--second-prefix", "10")
    assert partial["traversal_complete"] is False and partial["samples_completed"] == 1
    continued = subprocess.run(partial_args + ["--resume", "--limit-samples", "0"],
                               capture_output=True, text=True, timeout=30)
    assert continued.returncode == 0, continued.stderr
    continued = json.loads(continued.stdout)
    verify_attempt(continued)
    uninterrupted, _, _ = run(gated, 8, "--samples", "4", "--first-prefix", "01", "--second-prefix", "10")
    normalize = lambda data: {name: value for name, value in data.items() if name != "seconds"}
    assert normalize(continued) == normalize(uninterrupted)

    invalid_settings = (("--beam-width", "0"), ("--beam-width", "33"), ("--lookahead", "5"),
                        ("--first-prefix", "0", "--second-prefix", "0"),
                        ("--first-prefix", "0", "--second-prefix", "11"),
                        ("--first-prefix", "02", "--second-prefix", "10"))
    for index, extra in enumerate(invalid_settings):
        invalid = [str(executable), "--graph", key(plateau), "--out", str(directory / f"invalid-{index}"),
                   "--length", "4", "--mode", "guided", *extra]
        completed = subprocess.run(invalid, capture_output=True, text=True, timeout=30)
        assert completed.returncode != 0, extra
    print("PASS: shortest plateau H4 and hard H6 witnesses, neutral steps, full permutation gate, sampled/full labels, trace-mask binding, resume configuration guards.")
    return {"native_rooted_classes_checked": 64, "plateau_witness_length": 4, "hard_witness_length": 6,
            "all_traces_scalar_verified": True, "sampled_full_denominators_checked": True,
            "permutation_gate_checked": True, "resume_guards_checked": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    evidence = mathematical_checks()
    if args.exe:
        executable = args.exe.resolve()
        assert executable.is_file()
        if args.work_dir:
            evidence.update(exercise(executable, args.work_dir.resolve()))
        else:
            with tempfile.TemporaryDirectory(prefix="family1-guided-cli-") as temporary:
                evidence.update(exercise(executable, Path(temporary)))
        evidence["native_exe_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(evidence, indent=2) + "\n")
    print("Family1 guided coordinate-score checks passed.")


if __name__ == "__main__":
    main()

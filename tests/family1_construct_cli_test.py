#!/usr/bin/env python3
"""Independently validate compressed constructive witnesses on all64 tiny classes.

The reference enumerates scalar static masks and ordinary functional orbits.
It shares no C++ transition, powering, canonicalization, or witness code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import tempfile
import time

from family1_threshold_cli_test import canonical, classes, endpoint, exact_score, key

REPO = Path(__file__).resolve().parents[1]


def orbit(function, root):
    path, index = [], {}
    state = root
    while state not in index:
        index[state] = len(path)
        path.append(state)
        state = function[state]
    return path, index[state], len(path) - index[state]


def orbit_power(function, root, exponent):
    path, tail, period = orbit(function, root)
    return path[exponent] if exponent < len(path) else path[tail + (exponent - tail) % period]


def reference_parameters(table):
    m = len(table)
    a, prefix_cycles = 0, set()
    for mask in range(1 << m):
        zero = [table[state][(mask >> state) & 1] for state in range(m)]
        _, tail, period = orbit(zero, 0)
        a = max(a, tail)
        prefix_cycles.add(period)
    b, suffix_cycles = 0, set()
    for mask in range(1 << m):
        zero = [table[state][(mask >> state) & 1] for state in range(m)]
        state = orbit_power(zero, 0, a)
        state = table[state][1 ^ ((mask >> state) & 1)]
        _, tail, period = orbit(zero, state)
        b = max(b, tail)
        suffix_cycles.add(period)
    return {"A": a, "B": b, "P": math.lcm(*prefix_cycles, *suffix_cycles),
            "prefix_cycle_lengths": sorted(prefix_cycles), "suffix_cycle_lengths": sorted(suffix_cycles)}


def endpoint_rle(table, mask, word):
    functions = [[table[state][letter ^ ((mask >> state) & 1)] for state in range(len(table))]
                 for letter in (0, 1)]
    state = 0
    for letter, count in word:
        assert letter in ("0", "1") and type(count) is int and count >= 0
        state = orbit_power(functions[int(letter)], state, count)
    return state


def normalized_rle(word):
    result = []
    for letter, count in word:
        assert letter in ("0", "1") and type(count) is int and count >= 0
        if not count:
            continue
        if result and result[-1][0] == letter:
            result[-1][1] += count
        else:
            result.append([letter, count])
    return result


def verify_result(result):
    table = result["canonical_table"]
    m = len(table)
    assert result["m"] == m and result["key"] == key(canonical(table))
    expected = reference_parameters(table)
    for name in ("A", "B", "P"):
        assert type(result[name]) is int and result[name] == expected[name], (name, result, expected)
    for name in ("prefix_cycle_lengths", "suffix_cycle_lengths"):
        assert sorted(result[name]) == expected[name]
    a, b, p = result["A"], result["B"], result["P"]
    assert 0 <= a <= m - 1 and 0 <= b <= m - 1 and p >= 1
    assert result["length"] == result["upper_bound"] == a + b + p + 1
    assert result["lower_bound"] == 1 and result["exact_score_certified"] is False
    assert result["static_masks"] is True and result["mask_enumeration_complete"] is True
    assert result["merge_length"] is None and result["distinct_words"] is True
    assert result["prefix_period"] == math.lcm(*expected["prefix_cycle_lengths"])
    assert result["one_positions_zero_based"] == [a + p, a]
    generic = result["generic_construction"]
    assert generic["A"] == generic["B"] == m - 1
    assert generic["P"] == math.lcm(*range(1, m + 1))
    assert generic["length"] == generic["P"] + 2 * m - 1
    words = result["word_rle"]
    assert words == [[["0", a + p], ["1", 1], ["0", b]],
                     [["0", a], ["1", 1], ["0", b + p]]]
    assert normalized_rle(words[0]) != normalized_rle(words[1])
    assert all(sum(run[1] for run in word) == result["length"] for word in words)
    assert result["masks_enumerated"] == 1 << m
    verification = result["universal_verification"]
    assert verification["passed"] is True and verification["mask_count"] == 1 << m
    for mask in range(1 << m):
        assert endpoint_rle(table, mask, words[0]) == endpoint_rle(table, mask, words[1])
    materialized = result["word_strings"]
    if materialized is not None:
        assert materialized == ["".join(letter * count for letter, count in word) for word in words]
        assert materialized[0] != materialized[1]
        for mask in range(1 << m):
            assert endpoint(table, mask, materialized[0]) == endpoint(table, mask, materialized[1])
    return expected


def exercise(executable, directory):
    directory.mkdir(parents=True, exist_ok=True)
    counter, saved = 0, None

    def run(table, materialize=100000):
        nonlocal counter
        counter += 1
        output = directory / f"case-{counter:03d}"
        command = [str(executable), "--graph", key(table), "--out", str(output),
                   "--materialize-limit", str(materialize)]
        completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
        assert completed.returncode == 0, (command, completed.stdout, completed.stderr)
        result = json.loads((output / "result.json").read_text())
        assert json.loads(completed.stdout) == result
        result_bytes = (output / "result.json").read_bytes()
        assert (output / "result.sha256").read_text().strip() == hashlib.sha256(result_bytes).hexdigest()
        config = (output / "run.json").read_bytes().removesuffix(b"\n")
        assert result["config_sha256"] == hashlib.sha256(config).hexdigest()
        assert result["source_key_sha256"] == hashlib.sha256(key(table).encode()).hexdigest()
        assert result["canonical_key_sha256"] == hashlib.sha256(result["key"].encode()).hexdigest()
        assert result["source_key"] == key(table)
        assert result["canonical_table"] == list(map(list, canonical(table)))
        verify_result(result)
        return result, output, command

    for m, expected in ((1, 1), (2, 6), (3, 57)):
        tables = classes(m)
        assert len(tables) == expected
        for table in tables:
            result, output, command = run(table)
            assert result["word_strings"] is not None
            assert result["length"] >= exact_score(table)
            generic_p = math.lcm(*range(1, m + 1))
            generic = [[["0", m - 1 + generic_p], ["1", 1], ["0", m - 1]],
                       [["0", m - 1], ["1", 1], ["0", m - 1 + generic_p]]]
            for mask in range(1 << m):
                assert endpoint_rle(table, mask, generic[0]) == endpoint_rle(table, mask, generic[1])
            saved = result, output, command
    assert counter == 64
    print("PASS: all64 rooted classes m<=3, exact scalar orbit parameters, generic formula, every mask, distinct equal-length words.")

    # Noncanonical labels and port order must be accepted within the rooted class.
    run(((2, 1), (2, 0), (2, 1)))
    compact, _, _ = run(((0, 1), (0, 1)), materialize=0)
    assert compact["word_strings"] is None
    assert compact["length"] > 0

    # Repeated fixed bits and arbitrary long powers are checked without expanding.
    table = ((0, 1), (0, 1))
    for mask in range(4):
        for exponent in (0, 1, 2, 3, 17, 1000000007):
            function = [row[(mask >> state) & 1] for state, row in enumerate(table)]
            assert endpoint_rle(table, mask, [["0", exponent]]) == orbit_power(function, 0, exponent)

    result, output, command = saved
    snapshot = {path.name: path.read_bytes() for path in output.iterdir()}
    resumed = subprocess.run(command + ["--resume"], capture_output=True, text=True, timeout=30)
    assert resumed.returncode == 0 and json.loads(resumed.stdout) == result
    assert snapshot == {path.name: path.read_bytes() for path in output.iterdir()}
    for suffix in ([], ["--resume", "--graph", "0000"], ["--resume", "--materialize-limit", "0"]):
        rejected = subprocess.run(command + suffix, capture_output=True, text=True, timeout=30)
        assert rejected.returncode != 0
        assert snapshot == {path.name: path.read_bytes() for path in output.iterdir()}

    (output / "result.json").write_bytes(snapshot["result.json"] + b" ")
    corrupt = subprocess.run(command + ["--resume"], capture_output=True, text=True, timeout=30)
    assert corrupt.returncode != 0 and "integrity" in corrupt.stderr

    # An interruption before atomic result publication can rerun safely.
    incomplete = directory / "incomplete"
    incomplete.mkdir()
    (incomplete / "run.json").write_bytes(snapshot["run.json"])
    (incomplete / "result.json.tmp").write_text("incomplete fragment")
    retry = list(command)
    retry[retry.index("--out") + 1] = str(incomplete)
    completed = subprocess.run(retry + ["--resume"], capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0
    verify_result(json.loads(completed.stdout))
    assert not (incomplete / "result.json.tmp").exists()

    for bad in ("", "000000", "00000101", "000x", "99" * 2):
        failed = subprocess.run([str(executable), "--graph", bad, "--out", str(directory / "invalid")],
                                capture_output=True, text=True, timeout=30)
        assert failed.returncode != 0, (bad, failed.stdout, failed.stderr)
    print("PASS: loops, coincident ports, static revisits, powers, noncanonical input, compressed output, resume and overwrite/config guards.")


def benchmark(executable, directory, m, repeats):
    # Keep the raw labeled table here: factorial canonicalization belongs only
    # to the tiny-case reference, not to a timed larger-size benchmark.
    table = tuple(((state + 1) % m, (state + m // 3) % m) for state in range(m))
    python_times, native_times = [], []
    expected = None
    for repeat in range(repeats):
        started = time.perf_counter()
        expected = reference_parameters(table)
        a, b, p = expected["A"], expected["B"], expected["P"]
        words = [[["0", a + p], ["1", 1], ["0", b]], [["0", a], ["1", 1], ["0", b + p]]]
        for mask in range(1 << m):
            assert endpoint_rle(table, mask, words[0]) == endpoint_rle(table, mask, words[1])
        python_times.append(time.perf_counter() - started)
        output = directory / f"benchmark-{m}-{repeat}"
        command = [str(executable), "--graph", key(table), "--out", str(output), "--materialize-limit", "0"]
        started = time.perf_counter()
        completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        native_times.append(time.perf_counter() - started)
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        assert all(result[name] == expected[name] for name in ("A", "B", "P"))
        assert result["universal_verification"]["passed"] is True
    report = {"m": m, "graph_key": key(table), "mask_count": 1 << m, "repeats": repeats,
              "task": "compute A/B/P over all masks and verify compressed witness over all masks",
              "python_method": "independent scalar functional orbits; parameters plus full verification; no output I/O",
              "native_method": "complete executable invocation including process startup and output I/O",
              "python_seconds": python_times, "native_seconds": native_times,
              "python_median_seconds": statistics.median(python_times),
              "native_median_seconds": statistics.median(native_times),
              "observed_ratio": statistics.median(python_times) / statistics.median(native_times),
              "native_exe_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
              "parameters": expected}
    (directory / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--benchmark-m", type=int, choices=range(1, 21))
    parser.add_argument("--benchmark-repeats", type=int, default=3)
    args = parser.parse_args()
    executable = args.exe.resolve()
    assert executable.is_file(), executable
    assert args.benchmark_repeats > 0
    def run(directory):
        exercise(executable, directory)
        if args.benchmark_m:
            benchmark(executable, directory, args.benchmark_m, args.benchmark_repeats)
    if args.work_dir:
        run(args.work_dir.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="family1-construct-cli-") as temporary:
            run(Path(temporary))
    print("Family1Construct independent CLI checks passed.")


if __name__ == "__main__":
    main()

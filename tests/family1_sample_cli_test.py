#!/usr/bin/env python3
"""Independent scalar validation of the native structured/static-mask sampler."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from family1_threshold_cli_test import canonical, classes, endpoint, exact_score, key


def snapshot(directory):
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


def stable(result):
    return {name: value for name, value in result.items() if name not in ("seconds", "packed_seconds", "scalar_seconds", "scalar_over_packed_speedup")}


def verify_result(result, table, length):
    table = canonical(table)
    assert result["canonical_table"] == list(map(list, table))
    assert result["key"] == key(table) and result["m"] == len(table) and result["length"] == length
    assert result["lower_bound"] == 1
    assert result["shortest_proved"] is False and result["all_witnesses_collected"] is False
    assert result["global_maximum_certified"] is False
    masks = result["sampled_masks"]
    assert 1 <= len(masks) <= min(result["requested_masks"], 1 << len(table))
    assert len(masks) == len(set(masks)) and all(0 <= mask < (1 << len(table)) for mask in masks)
    assert 0 <= result["samples_completed"] <= result["requested_samples"]
    if result["decision"] == "collision":
        first, second = result["witness"]
        assert first != second and len(first) == len(second) == length
        assert set(first + second) <= {"0", "1"}
        assert result["upper_bound"] == length
        assert result["scalar_witness_masks_verified"] == 1 << len(table)
        assert all(endpoint(table, mask, first) == endpoint(table, mask, second)
                   for mask in range(1 << len(table)))
    else:
        assert result["decision"] == "unknown"
        assert result["witness"] is None and result["upper_bound"] is None
        assert result["scalar_witness_masks_verified"] == 0


def exercise(executable, directory):
    directory.mkdir(parents=True, exist_ok=True)
    counter = 0

    def command(table, length, output, *extra):
        return [str(executable), "--graph", key(table), "--out", str(output), "--length", str(length),
                "--samples", "128", "--seed", "1088", "--masks", "64", "--mode", "random",
                "--checkpoint-every", "4096", *extra]

    def run(table, length, *extra):
        nonlocal counter
        counter += 1
        output = directory / f"case-{counter:03d}"
        args = command(table, length, output, *extra)
        completed = subprocess.run(args, capture_output=True, text=True, timeout=30)
        assert completed.returncode == 0, (args, completed.stdout, completed.stderr)
        result = json.loads(completed.stdout)
        verify_result(result, table, length)
        config = (output / "run.json").read_bytes()
        assert result["config_sha256"] == hashlib.sha256(config).hexdigest()
        if result["traversal_complete"]:
            data = (output / "result.json").read_bytes()
            assert json.loads(data) == result
            assert (output / "result.sha256").read_text().strip() == hashlib.sha256(data).hexdigest()
        else:
            assert not (output / "result.json").exists()
            assert json.loads((output / f"partial-{result['samples_completed']}.json").read_text()) == result
        return result, output, args

    accepted = 0
    for m, expected in ((1, 1), (2, 6), (3, 57)):
        tables = classes(m)
        assert len(tables) == expected
        for table in tables:
            length = exact_score(table)
            result, _, _ = run(table, length)
            # The documented random startup exhausts all words of length<=8.
            # At most64 words therefore suffice at every tiny exact score.
            assert result["decision"] == "collision", (table, length, result)
            assert result["samples_completed"] <= 1 << length
            accepted += 1
    assert accepted == 64
    print("PASS: all64 rooted classes m<=3, deterministic tiny-word startup, every accepted pair independently replayed on all masks.")

    two = ((0, 1), (0, 1))
    found, _, _ = run(two, 3, "--mode", "commutator")
    assert found["decision"] == "collision" and found["witness"] == ["010", "100"]
    assert found["samples_completed"] == 1
    # Hash equality is deliberately worthless; unequal full states must survive.
    miss, _, _ = run(two, 2, "--hash-bits", "0")
    assert miss["decision"] == "unknown" and miss["hash_matches"] > 0
    assert miss["hash_matches"] > miss["projected_profile_equalities"]

    hard = ((0, 1), (1, 2), (0, 1))
    assert exact_score(hard) == 6
    refuted, _, _ = run(hard, 5, "--masks", "1", "--hash-bits", "0")
    assert refuted["decision"] == "unknown" and refuted["counterexample_masks"] >= 1
    assert refuted["scalar_candidate_checks"] >= 1

    # Every full-mask acceptance at larger tiny sizes is scalar-checked too.
    for m in (4, 5, 6):
        cycle = tuple((((state + 1) % m), ((state + 1) % m)) for state in range(m))
        result, _, _ = run(cycle, 1, "--mode", "commutator")
        assert result["decision"] == "collision"
    run(((2, 1), (2, 0), (2, 1)), 6)

    # Reproducibility is about samples and counters, not elapsed wall time.
    repeated, output, args = run(hard, 5, "--masks", "1", "--hash-bits", "0")
    assert stable(repeated) == stable(refuted)
    before = snapshot(output)
    resumed = subprocess.run(args + ["--resume"], capture_output=True, text=True, timeout=30)
    assert resumed.returncode == 0 and json.loads(resumed.stdout) == repeated
    assert before == snapshot(output)
    for suffix in ([], ["--resume", "--seed", "99"], ["--resume", "--length", "4"],
                   ["--resume", "--samples", "129"]):
        failed = subprocess.run(args + suffix, capture_output=True, text=True, timeout=30)
        assert failed.returncode != 0
        assert before == snapshot(output)

    # Partial runs preserve a deterministic checkpoint and no completed proof.
    partial, partial_dir, partial_args = run(two, 2, "--limit-samples", "1")
    assert partial["traversal_complete"] is False and partial["samples_completed"] == 1
    checkpoint = partial_dir / "checkpoints/sample-1.txt"
    assert checkpoint.exists()
    checkpoint_files = snapshot(partial_dir)
    resumed = subprocess.run(partial_args + ["--resume", "--limit-samples", "0"], capture_output=True, text=True, timeout=30)
    assert resumed.returncode == 0
    continued = json.loads(resumed.stdout)
    verify_result(continued, two, 2)
    assert continued["traversal_complete"] is True and continued["decision"] == "unknown"
    for name, data in checkpoint_files.items():
        assert (partial_dir / name).read_bytes() == data
    uninterrupted, _, _ = run(two, 2)
    assert stable(uninterrupted) == stable(continued)

    # Checkpoint and completed-result corruption must not become certificates.
    bad_partial, bad_dir, bad_args = run(two, 2, "--limit-samples", "1")
    damaged = bad_dir / "checkpoints/sample-1.txt"
    damaged.write_bytes(damaged.read_bytes() + b" ")
    rejected = subprocess.run(bad_args + ["--resume"], capture_output=True, text=True, timeout=30)
    assert rejected.returncode != 0 and "SHA256" in rejected.stderr
    (output / "result.json").write_bytes(before["result.json"] + b" ")
    rejected = subprocess.run(args + ["--resume"], capture_output=True, text=True, timeout=30)
    assert rejected.returncode != 0 and "SHA256" in rejected.stderr

    for extra in (("--length", "0"), ("--masks", "0"), ("--masks", "65"), ("--hash-bits", "65"),
                  ("--samples", "0"), ("--mode", "invalid"), ("--max-profiles", "0")):
        invalid = command(two, 2, directory / "invalid", *extra)
        completed = subprocess.run(invalid, capture_output=True, text=True, timeout=30)
        assert completed.returncode != 0, extra
    print("PASS: m2 structured witness, forced hash collisions, false projected hits, m4..6 masks, deterministic seeds/checkpoints/resume, miss-no-bound and corruption guards.")


def benchmark(executable, directory):
    # Both native kernels process exactly the same deterministic10,000 words,
    # all64 sampled coordinates, and complete states. Hit frequency is irrelevant.
    m = 16
    table = tuple(((state + 1) % m, (state + m // 3) % m) for state in range(m))
    output = directory / "benchmark"
    args = [str(executable), "--graph", key(table), "--out", str(output), "--length", "64",
            "--samples", "10000", "--masks", "64", "--seed", "1088", "--mode", "benchmark"]
    completed = subprocess.run(args, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["benchmark_profiles_equal"] is True
    assert report["benchmark_words"] == report["samples_completed"] == 10000
    assert len(report["sampled_masks"]) == 64
    assert report["decision"] == "unknown" and report["lower_bound"] == 1 and report["upper_bound"] is None
    assert report["packed_seconds"] > 0 and report["scalar_seconds"] > 0
    expected = report["scalar_seconds"] / report["packed_seconds"]
    assert abs(report["scalar_over_packed_speedup"] - expected) <= 1e-12 * max(1, expected)
    print(json.dumps({name: report[name] for name in ("benchmark_words", "packed_seconds", "scalar_seconds", "scalar_over_packed_speedup", "benchmark_checksum")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args()
    executable = args.exe.resolve()
    assert executable.is_file(), executable
    def run(directory):
        exercise(executable, directory)
        if args.benchmark:
            benchmark(executable, directory)
    if args.work_dir:
        run(args.work_dir.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="family1-sample-cli-") as temporary:
            run(Path(temporary))
    print("Family1Sample independent CLI checks passed.")


if __name__ == "__main__":
    main()

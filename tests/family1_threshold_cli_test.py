#!/usr/bin/env python3
"""Independently check fixed-length SAT decisions on every rooted class m<=3.

The reference uses ordinary integer states, every static mask, every word, and
factorial root-fixing canonicalization. It shares no production search code.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def accessible(table):
    reached, pending = {0}, [0]
    while pending:
        for target in table[pending.pop()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    return len(reached) == len(table)


def canonical(table):
    best = None
    for tail in itertools.permutations(range(1, len(table))):
        mapping = (0,) + tail
        result = [None] * len(table)
        for source, row in enumerate(table):
            result[mapping[source]] = tuple(sorted(mapping[target] for target in row))
        candidate = tuple(result)
        best = candidate if best is None else min(best, candidate)
    return best


def endpoint(table, mask, word):
    state = 0
    for symbol in word:
        state = table[state][int(symbol) ^ ((mask >> state) & 1)]
    return state


def collision(table, length, masks=None):
    masks = range(1 << len(table)) if masks is None else masks
    seen = {}
    for letters in itertools.product("01", repeat=length):
        word = "".join(letters)
        profile = tuple(endpoint(table, mask, word) for mask in masks)
        if profile in seen:
            return seen[profile], word
        seen[profile] = word
    return None


def exact_score(table):
    for length in range(1, 10):
        if collision(table, length):
            return length
    raise AssertionError("tiny reference did not terminate")


def classes(m):
    tables = set()
    for targets in itertools.product(range(m), repeat=2 * m):
        table = tuple(zip(targets[::2], targets[1::2]))
        if accessible(table):
            tables.add(canonical(table))
    return sorted(tables)


def exercise(executable, directory):
    directory.mkdir(parents=True, exist_ok=True)
    counter = 0

    def command(table, length, output, *extra):
        return [str(executable), "--graph", key(table), "--length", str(length), "--out", str(output),
                "--timeout-ms", "5000", "--solve-timeout-ms", "5000", *extra]

    def run(table, length, *extra):
        nonlocal counter
        counter += 1
        output = directory / f"case-{counter:03d}"
        args = command(table, length, output, *extra)
        completed = subprocess.run(args, text=True, capture_output=True, timeout=30)
        assert completed.returncode == 0, (args, completed.stdout, completed.stderr)
        result_bytes = (output / "result.json").read_bytes()
        assert completed.stdout.strip() == result_bytes.decode().strip()
        result = json.loads(result_bytes)
        assert (output / "result.sha256").read_text().strip() == hashlib.sha256(result_bytes).hexdigest()
        config = (output / "run.json").read_bytes().removesuffix(b"\n")
        assert result["config_sha256"] == hashlib.sha256(config).hexdigest()
        assert result["source_key_sha256"] == hashlib.sha256(key(table).encode()).hexdigest()
        assert result["canonical_key_sha256"] == hashlib.sha256(result["key"].encode()).hexdigest()
        assert result["canonical_table"] == list(map(list, canonical(table)))
        assert result["key"] == key(canonical(table))
        assert result["m"] == len(table) and result["length"] == length
        masks = result["sampled_masks"]
        assert len(masks) == result["mask_count"] == len(set(masks))
        assert all(type(mask) is int and 0 <= mask < (1 << len(table)) for mask in masks)
        assert result["static_masks"] is True
        for flag in ("exact_score_certified", "maximum_value_certified", "maximizing_collection_complete", "enumeration_complete"):
            assert result[flag] is False, result
        return result, output, args

    decisions = 0
    saved = None
    for m, expected in ((1, 1), (2, 6), (3, 57)):
        tables = classes(m)
        assert len(tables) == expected
        for table in tables:
            score = exact_score(table)
            lengths = sorted({max(1, score - 1), score, score + 1})
            for length in lengths:
                result, output, args = run(table, length)
                expected_collision = score <= length
                assert result["decision"] == ("collision" if expected_collision else "no_collision"), (table, score, result)
                if expected_collision:
                    witness = result["witness"]
                    assert result["lower_bound"] == 1 and result["upper_bound"] == length
                    assert result["scalar_witness_masks_verified"] == 1 << m
                    assert len(witness) == 2 and witness[0] != witness[1]
                    assert all(len(word) == length and set(word) <= {"0", "1"} for word in witness)
                    assert all(endpoint(table, mask, witness[0]) == endpoint(table, mask, witness[1]) for mask in range(1 << m))
                else:
                    assert result["lower_bound"] == length + 1 and result["upper_bound"] is None
                    assert result["witness"] is None and result["scalar_witness_masks_verified"] == 0
                    # The exported static-mask subset itself certifies injectivity.
                    assert collision(table, length, result["sampled_masks"]) is None
                decisions += 1
                saved = output, args
    print(f"All64 rooted classes m<=3: {decisions} independent threshold decisions passed (loops, coincident ports, revisits).")

    # Under one sampled mask, length5 necessarily has a collision (32 words,
    # only3 states). This graph has H=6, so the first pair must be refuted and
    # max-refinements1 must return UNKNOWN, irrespective of the SAT model chosen.
    hard = ((0, 1), (1, 2), (0, 1))
    assert exact_score(hard) == 6
    result, _, _ = run(hard, 5, "--projection-masks", "1", "--max-refinements", "1")
    assert result["decision"] == "unknown" and result["reason"] == "max-refinements"
    assert result["lower_bound"] == 1 and result["upper_bound"] is None and result["witness"] is None
    assert result["scalar_witness_masks_verified"] == 0
    assert result["refinements"] == 1 and result["mask_count"] == 2

    # A noncanonical label/port order is accepted and scored in its rooted class.
    result, _, _ = run(((2, 1), (2, 0), (2, 1)), 6)
    assert result["decision"] == "collision"

    output, args = saved
    snapshot = {path.name: path.read_bytes() for path in output.iterdir()}
    resumed = subprocess.run(args + ["--resume"], capture_output=True, text=True, timeout=30)
    assert resumed.returncode == 0 and json.loads(resumed.stdout)["decision"] in ("collision", "no_collision")
    assert snapshot == {path.name: path.read_bytes() for path in output.iterdir()}
    for suffix in ([], ["--resume", "--length", "100"], ["--resume", "--timeout-ms", "1"]):
        rejected = subprocess.run(args + suffix, capture_output=True, text=True, timeout=30)
        assert rejected.returncode != 0
        assert snapshot == {path.name: path.read_bytes() for path in output.iterdir()}

    # Corruption is rejected; no damaged file becomes a resumed certificate.
    (output / "result.json").write_bytes(snapshot["result.json"] + b" ")
    corrupt = subprocess.run(args + ["--resume"], capture_output=True, text=True, timeout=30)
    assert corrupt.returncode != 0 and "integrity" in corrupt.stderr

    # A pre-publication interruption can be retried with exactly the same config.
    incomplete = directory / "incomplete"
    incomplete.mkdir()
    (incomplete / "run.json").write_bytes(snapshot["run.json"])
    (incomplete / "result.json.tmp").write_text("incomplete fragment")
    retry = list(args)
    retry[retry.index("--out") + 1] = str(incomplete)
    rerun = subprocess.run(retry + ["--resume"], capture_output=True, text=True, timeout=30)
    assert rerun.returncode == 0
    assert (incomplete / "result.json").is_file() and not (incomplete / "result.json.tmp").exists()
    assert json.loads(rerun.stdout)["decision"] in ("collision", "no_collision")

    for table, length in ((((0, 0), (1, 1)), 1), (((0, 0),), 0)):
        invalid = subprocess.run(command(table, length, directory / f"invalid-{length}"), capture_output=True, text=True, timeout=30)
        assert invalid.returncode != 0
    print("UNKNOWN carries no score proof; provenance SHA256, canonicalization, resume, corruption, and atomic-publication checks passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    executable = args.exe.resolve()
    assert executable.is_file(), executable
    help_result = subprocess.run([str(executable), "--help"], text=True, capture_output=True, timeout=30)
    assert help_result.returncode == 0 and "unknown proves neither" in help_result.stdout
    if args.work_dir:
        exercise(executable, args.work_dir.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="family1-threshold-cli-") as temporary:
            exercise(executable, Path(temporary))
    print("Family1Threshold CLI integration checks passed.")


if __name__ == "__main__":
    main()

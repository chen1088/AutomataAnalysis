"""Optional GPU validation; never a required CTest/dependency installation.

Run with the isolated GPU interpreter, for example:
out/family1-gpu-venv/Scripts/python.exe tests/family1_gpu_witnesses_test.py --require-gpu
Only tiny GPU arrays are used. No full deep word layers are allocated.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/family1_gpu_witnesses.py"
HARD_KEY = "0001020304050406020605060001"


def key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def endpoints(table, word, root=0):
    result = []
    for mask in range(128):
        state = root
        for letter in word:
            state = table[state][int(letter) ^ ((mask >> state) & 1)]
        result.append(state)
    return tuple(result)


def checked_positive(table, result, depth):
    assert result["absence_is_not_lower_proof"] is True
    assert result["lower_bound"] is None
    if result["witness"] is None:
        assert result["status"] == "unresolved" and result["upper_bound"] is None
        return False
    first, second = result["witness"]
    assert first != second and len(first) == len(second) == depth
    assert set(first + second) <= {"0", "1"}
    assert endpoints(table, first) == endpoints(table, second)
    assert result["status"] == "verified-upper" and result["upper_bound"] == depth
    return True


def full_profile_checks(module):
    engine = module.Engine(3)
    rng = random.Random(20261025)
    tables = [
        [(0, 0)] * 7,
        [(min(state + 1, 6),) * 2 for state in range(7)],
        [(0, 1), (0, 0)] + [(state, state) for state in range(2, 7)],
        [((state + 1) % 7, (state + 2) % 7) for state in range(7)],
        [(0, 1), (2, 3), (4, 5), (4, 6), (2, 6), (5, 6), (0, 1)],
        [(0, 1), (2, 4), (3, 5), (0, 4), (2, 5), (3, 6), (1, 6)],
    ]
    tables += [[(rng.randrange(7), rng.randrange(7)) for _ in range(7)] for _ in range(30)]
    count = 0
    for table in tables:
        for depth in (0, 1, 2, 3, 4, 7, 15, 31, 40, 60):
            indices = [0, (1 << depth) - 1] + [rng.getrandbits(depth) for _ in range(8)]
            profiles = engine.profiles(key(table), indices, depth)
            for index, planes in zip(indices, profiles):
                word = f"{index:0{depth}b}" if depth else ""
                actual = tuple(sum(((int(planes[2 * bit + mask // 64]) >> (mask % 64)) & 1) << bit
                                   for bit in range(3)) for mask in range(128))
                assert actual == endpoints(table, word), (table, depth, word)
                count += 1
    assert count == 3600
    revisit = tables[2]
    assert endpoints(revisit, "0000")[1] == 0 and endpoints(revisit, "000")[1] == 1
    print(f"PASS: {count} complete 128-mask GPU profiles, depths 0..60", flush=True)
    return count


def small_layer_checks(module):
    engine = module.Engine(0)
    tables = []
    for m in (1, 2):
        for entries in itertools.product(range(m), repeat=2 * m):
            tables.append([tuple(entries[2 * state:2 * state + 2]) for state in range(m)]
                          + [(state, state) for state in range(m, 7)])
    rng = random.Random(1088)
    tables += [[(rng.randrange(3), rng.randrange(3)) for _ in range(3)]
               + [(state, state) for state in range(3, 7)] for _ in range(100)]
    count = 0
    for table in tables:
        for depth in range(1, 8):
            words = (f"{index:0{depth}b}" for index in range(1 << depth))
            vectors = [endpoints(table, word) for word in words]
            collision = len(set(vectors)) < len(vectors)
            result = engine.probe(key(table), depth)
            assert checked_positive(table, result, depth) == collision, (table, depth, result)
            count += 1
    assert count == 819
    # Exercise the production chunk size separately, including actual nonhits.
    chunked = module.Engine(3)
    hard = module.table_from_key(HARD_KEY)
    for depth in (4, 5, 6, 7):
        assert not checked_positive(hard, chunked.probe(HARD_KEY, depth), depth)
    for table in tables[:2]:
        for depth in (4, 7):
            assert checked_positive(table, chunked.probe(key(table), depth), depth)
    print(f"PASS: {count} independent small-layer truth cases and 8 chunked checks", flush=True)
    return count + 8


def forced_hash_checks(module):
    # Test-only in-memory kernel variant. Production has no forced-hash flag;
    # its file and the running follower's module remain entirely unchanged.
    original_source = module.source
    needle = "return mix(lo^((hi<<29)|(hi>>35))^0xd6e8feb86659fd93ULL);"

    def constant_source(chunk=3):
        text = original_source(chunk)
        assert text.count(needle) == 1
        return text.replace(needle, "return 0ULL;")

    module.source = constant_source
    try:
        engine = module.Engine(0)
    finally:
        module.source = original_source
    hard = module.table_from_key(HARD_KEY)
    count = 0
    for depth in (4, 6, 8):
        result = engine.probe(HARD_KEY, depth)
        assert result["candidate_groups"] == (1 << (depth - 1)) - 1
        assert not checked_positive(hard, result, depth)
        count += 1
    # The least collision here is between nonadjacent indices in a constant
    # fingerprint bucket, exercising the v2 all-pairs check rather than an
    # adjacent-only check. Complements are included in the full-state test.
    table = [(0, 1), (1, 2), (0, 1)] + [(state, state) for state in range(3, 7)]
    assert not checked_positive(table, engine.probe(key(table), 5), 5)
    assert checked_positive(table, engine.probe(key(table), 6), 6)
    count += 2
    # A GPU hit must fail closed when the separate CPU verification rejects it.
    original_scalar = module.base.scalar
    module.base.scalar = lambda *_: False
    try:
        try:
            engine.probe(key([(0, 0)] * 7), 4)
        except RuntimeError as error:
            assert "CPU scalar" in str(error)
        else:
            raise AssertionError("GPU hit bypassed the CPU scalar gate")
    finally:
        module.base.scalar = original_scalar
    print(f"PASS: {count} constant-hash cases and CPU rejection gate", flush=True)
    return count + 1


def window_checks(module):
    engine = module.Engine(3)
    rng = random.Random(310032)
    tables = [
        module.table_from_key(HARD_KEY),
        [(0, 0)] * 7,
        [(0, 1), (1, 2), (0, 1)] + [(state, state) for state in range(3, 7)],
        [(0, 1), (0, 0)] + [(state, state) for state in range(2, 7)],
        [(rng.randrange(7), rng.randrange(7)) for _ in range(7)],
    ]
    count, missed_global_collisions = 0, 0

    def truth(table, depth, bits, offset):
        words = [f"{index:0{depth}b}" for index in range(offset, offset + (1 << bits))]
        # The window also compares each representative against complements of
        # all representatives in that SAME window. Other windows are excluded.
        words += ["".join("1" if bit == "0" else "0" for bit in word) for word in words]
        vectors = [endpoints(table, word) for word in words]
        return len(set(vectors)) != len(vectors)

    for table in tables:
        global_vectors = [endpoints(table, f"{index:08b}") for index in range(256)]
        global_collision = len(set(global_vectors)) < len(global_vectors)
        for offset in range(0, 128, 8):
            result = engine.probe_window(key(table), 8, 3, offset)
            expected = truth(table, 8, 3, offset)
            assert checked_positive(table, result, 8) == expected
            assert result["window_bits"] == 3 and result["window_offset"] == offset
            missed_global_collisions += global_collision and not expected
            count += 1
    assert missed_global_collisions > 0, "Window misses should remain inconclusive for the full layer"
    # High global word offsets exercise the prefix arithmetic without deep
    # allocation: each call still contains only EIGHT representatives.
    hard = tables[0]
    for depth in (31, 32, 40):
        for offset in (0, (1 << (depth - 1)) - 8):
            result = engine.probe_window(HARD_KEY, depth, 3, offset)
            assert checked_positive(hard, result, depth) == truth(hard, depth, 3, offset)
            count += 1
    for depth in (32, 40):
        result = engine.probe(HARD_KEY, depth, window_bits=3, max_blocks=2)
        checked_positive(hard, result, depth)
        assert result["total_windows"] == 1 << (depth - 4)
        assert 1 <= result["windows_tested"] <= 2
        assert result["cross_window_pairs_checked"] is False
        assert result["absence_is_not_lower_proof"] is True and result["lower_bound"] is None
        count += 1
    for depth, bits, offset in ((8, 2, 0), (8, 3, 1), (8, 3, 128), (8, 8, 0), (41, 3, 0)):
        try:
            engine.probe_window(HARD_KEY, depth, bits, offset)
        except ValueError:
            count += 1
        else:
            raise AssertionError("Invalid GPU window limits accepted")
    print(f"PASS: {count} bounded-window/high-offset/guard cases; missed global collisions remain unresolved", flush=True)
    return count


def cli_checks(module):
    count = 0
    with tempfile.TemporaryDirectory(prefix="family1-gpu-test-", dir=ROOT / "out") as name:
        temporary = Path(name).resolve()
        assert temporary.is_relative_to((ROOT / "out").resolve())
        tables = sorted([
            [(min(state + 1, 6),) * 2 for state in range(7)],
            [((state + 1) % 7,) * 2 for state in range(7)],
        ], key=key)
        records = [dict(m=7, ordinal=index, key=key(table), canonical_table=table,
                        status="depth-capped", lower_bound=1, upper_bound=None,
                        merge_length=None, witness=None, reason="test-prefix")
                   for index, table in enumerate(tables)]

        def source(name, values=records, *, complete=False, raw=None):
            folder = temporary / name
            folder.mkdir()
            path = folder / "checkpoint.jsonl"
            path.write_text(raw if raw is not None else "".join(json.dumps(value) + "\n" for value in values), encoding="utf-8")
            if complete:
                (folder / "summary.json").write_text(json.dumps({"enumeration_complete": True}))
            return path

        def command(journal, output, extra=()):
            return [sys.executable, str(SCRIPT), "--journal", str(journal), "--out", str(output),
                    "--depths", "4,5", "--threshold", "31", *map(str, extra)]

        def run(journal, output, *, extra=(), success=True):
            nonlocal count
            before = journal.read_bytes()
            result = subprocess.run(command(journal, output, extra), cwd=ROOT, capture_output=True,
                                    text=True, timeout=45)
            count += 1
            assert (result.returncode == 0) == success, result.stdout + result.stderr
            assert journal.read_bytes() == before
            if success:
                report = json.loads((output / "summary.json").read_text())
                assert report["maximum_value_certified"] is False
                assert report["maximizing_collection_complete"] is False
                assert report["no_hit_is_inconclusive"] is True
                for line in (output / "upper-witnesses.jsonl").read_text().splitlines():
                    value = json.loads(line)
                    assert value["upper_bound"] == len(value["witness"][0])
                    assert endpoints(value["canonical_table"], value["witness"][0]) == endpoints(value["canonical_table"], value["witness"][1])
                    assert value["cpu_scalar_masks_verified"] == 128
                    assert "lower_bound" not in value and "merge_length" not in value
                for line in (output / "attempts.jsonl").read_text().splitlines():
                    attempt = json.loads(line)
                    assert attempt["absence_is_not_lower_proof"] is True
                    for probe in attempt["results"]:
                        if probe["status"] != "incomplete":
                            assert probe["lower_bound"] is None and probe["absence_is_not_lower_proof"] is True
                return report
            return result

        journal = source("complete-input", complete=True)
        output = temporary / "resumed"
        first = run(journal, output, extra=("--limit-graphs", 1))
        assert first["total_attempted"] == first["total_verified_uppers"] == 1
        second = run(journal, output, extra=("--resume",))
        assert second["source_enumeration_complete"] and second["records_read"] == 2
        assert second["total_attempted"] == second["total_verified_uppers"] == 2
        before = {path.name: path.read_bytes() for path in output.iterdir()}
        run(journal, output, success=False)
        assert before == {path.name: path.read_bytes() for path in output.iterdir()}
        run(journal, output, extra=("--resume", "--depths", "4,6"), success=False)
        assert before == {path.name: path.read_bytes() for path in output.iterdir()}

        # Strict revalidation of prior positive metadata on resume.
        witness_path = output / "upper-witnesses.jsonl"
        original = witness_path.read_bytes()
        prior = [json.loads(line) for line in original.decode().splitlines()]
        mutations = [dict(upper_bound=5), dict(m=6), dict(ordinal=-1), dict(canonical_table=[[0, 0]] * 7)]
        for changes in mutations:
            bad = deepcopy(prior)
            bad[0].update(changes)
            witness_path.write_text("".join(json.dumps(value) + "\n" for value in bad))
            damaged = witness_path.read_bytes()
            run(journal, output, extra=("--resume",), success=False)
            assert witness_path.read_bytes() == damaged
        witness_path.write_bytes(original)
        for filename in ("attempts.jsonl", "upper-witnesses.jsonl"):
            path = output / filename
            saved = path.read_bytes()
            path.write_bytes(saved + b'{"torn":')
            run(journal, output, extra=("--resume",), success=False)
            assert path.read_bytes() == saved + b'{"torn":'
            path.write_bytes(saved)

        # A short configured depth below an inherited lower bound must be
        # skipped, rather than misreported as a contradiction or lower proof.
        value = deepcopy(records[:1])
        value[0]["lower_bound"] = 5
        lower_journal = source("lower-five", value)
        lower_output = temporary / "lower-five-output"
        run(lower_journal, lower_output)
        attempt = json.loads((lower_output / "attempts.jsonl").read_text())
        assert [probe["depth"] for probe in attempt["results"]] == [5]
        value[0]["lower_bound"] = 31
        skipped = source("all-depths-skipped", value)
        skipped_output = temporary / "all-depths-skipped-output"
        report = run(skipped, skipped_output)
        assert report["total_verified_uppers"] == 0 and report["unresolved_this_execution"] == 1
        assert json.loads((skipped_output / "attempts.jsonl").read_text())["results"] == []

        # Input guards reject bad records before emitting a false upper.
        for name, changes in (("ordinal", dict(ordinal=1)), ("size", dict(m=6)),
                              ("table", dict(canonical_table=[[0, 0]] * 7)), ("key", dict(key="bad"))):
            bad = deepcopy(records[:1]); bad[0].update(changes)
            bad_journal = source("bad-" + name, bad)
            bad_output = temporary / ("bad-" + name + "-output")
            run(bad_journal, bad_output, success=False)
            assert not (bad_output / "upper-witnesses.jsonl").read_text()
        for options in (("--depths", "5,4"), ("--depths", "3"), ("--threshold", "4"), ("--limit-graphs", "-1")):
            invalid_output = temporary / ("invalid-" + str(count))
            run(journal, invalid_output, extra=options, success=False)
            assert not invalid_output.exists()
        for options in (("--window-bits", "2"), ("--max-window-blocks", "-1")):
            invalid_output = temporary / ("invalid-" + str(count))
            run(journal, invalid_output, extra=options, success=False)
            assert not invalid_output.exists()
        equal_threshold = temporary / "equal-threshold-output"
        report = run(journal, equal_threshold, extra=("--depths", "4", "--threshold", "4"))
        assert report["total_verified_uppers"] == 2 and report["threshold"] == 4
        bounded_window_output = temporary / "bounded-window-output"
        report = run(journal, bounded_window_output,
                     extra=("--depths", "32", "--threshold", "32", "--window-bits", "3", "--max-window-blocks", "1"))
        assert report["total_verified_uppers"] == 2 and report["window_bits"] == 3
        assert report["max_window_blocks"] == 1
        # Only tiny windows were searched, and even a verified length-32
        # witness supplies no lower bound or global optimality certificate.
        for line in (bounded_window_output / "attempts.jsonl").read_text().splitlines():
            value = json.loads(line)["results"][0]
            assert value["cross_window_pairs_checked"] is False and value["windows_tested"] == 1

        # A torn producer record is left intact while following. Only append
        # its remainder; publish the completion summary atomically.
        first_line, second_line = (json.dumps(record) + "\n" for record in records)
        split = len(second_line) // 2
        following = source("following-input", raw=first_line + second_line[:split])
        following_output = temporary / "following-output"
        process = subprocess.Popen(command(following, following_output, ("--follow",)), cwd=ROOT,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                attempts = following_output / "attempts.jsonl"
                if attempts.exists() and len(attempts.read_text().splitlines()) == 1:
                    break
                assert process.poll() is None
                time.sleep(.05)
            else:
                raise AssertionError("Follower did not commit its first complete record")
            assert process.poll() is None
            with following.open("a", encoding="utf-8", newline="") as stream:
                stream.write(second_line[split:])
            producer = following.parent / "summary.json"
            temporary_summary = producer.with_suffix(".tmp")
            temporary_summary.write_text('{"enumeration_complete":true}')
            temporary_summary.replace(producer)
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stdout + stderr
            count += 1
            report = json.loads((following_output / "summary.json").read_text())
            assert report["source_enumeration_complete"] and report["total_verified_uppers"] == 2
            assert report["maximum_value_certified"] is report["maximizing_collection_complete"] is False
            assert following.read_text() == first_line + second_line
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=10)

        # GPU/runtime errors leave a durable unresolved attempt with no lower
        # or upper inference. Inject the exception only in this test process.
        class ErrorEngine:
            def __init__(self, *_):
                pass

            def probe(self, *_):
                raise module.cp.cuda.runtime.CUDARuntimeError(2)

        error_journal = source("gpu-error", records[:1])
        error_output = temporary / "gpu-error-output"
        old_engine, old_argv = module.Engine, sys.argv
        module.Engine = ErrorEngine
        sys.argv = [str(SCRIPT), "--journal", str(error_journal), "--out", str(error_output), "--depths", "4"]
        try:
            with redirect_stdout(io.StringIO()):
                module.main()
        finally:
            module.Engine, sys.argv = old_engine, old_argv
        report = json.loads((error_output / "summary.json").read_text())
        assert report["errors"] == report["unresolved_this_execution"] == 1
        assert report["total_verified_uppers"] == 0 and not report["maximum_value_certified"]
        count += 1
    print(f"PASS: {count} CLI/resume/follower/error guards; no false lower/global certificates", flush=True)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-gpu", action="store_true", help="Fail rather than skip if the optional GPU runtime is unavailable")
    args = parser.parse_args()
    try:
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError("no CUDA device")
    except Exception as error:
        if args.require_gpu:
            raise
        print(f"SKIP optional GPU validation: {error}")
        return 0
    spec = importlib.util.spec_from_file_location("family1_gpu_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    profile_count = full_profile_checks(module)
    layer_count = small_layer_checks(module)
    forced_count = forced_hash_checks(module)
    window_count = window_checks(module)
    cli_count = cli_checks(module)
    print(f"PASS optional GPU suite: {profile_count} full profiles, {layer_count} layers, "
          f"{forced_count} forced-hash/gate cases, {window_count} window cases and {cli_count} CLI guards. GPU absence remains unresolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

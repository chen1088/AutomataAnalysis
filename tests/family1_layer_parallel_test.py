"""Independent scalar regression/stress tests for parallel compact lower checks.

Uses only tiny layers, plus <=64 MiB arrays in interrupted runs. No GPU or
production scorer is used, and no witness is assumed shortest merely because
one equal-length layer contains a collision.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import random
import subprocess
import tempfile

from family1_exhaustive_cli_test import oracle


ROOT = Path(__file__).resolve().parents[1]
HARD_KEY = "0001020304050406020605060001"


def key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def endpoints(table, word):
    result = []
    for mask in range(128):
        state = 0
        for letter in word:
            state = table[state][int(letter) ^ ((mask >> state) & 1)]
        result.append(state)
    return tuple(result)


def collision_at(table, depth):
    vectors = [endpoints(table, f"{index:0{depth}b}") for index in range(1 << depth)]
    return len(set(vectors)) < len(vectors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    args = parser.parse_args()
    executable = args.exe.resolve()
    assert executable.is_file(), executable
    invocations = 0
    with tempfile.TemporaryDirectory(prefix="family1-parallel-layer-", dir=ROOT / "out") as name:
        temporary = Path(name).resolve()
        assert temporary.is_relative_to((ROOT / "out").resolve())
        report = temporary / "report.json"

        def run(table, depth, threads=1, *, forced=False, extra=(), success=True, compact=True):
            nonlocal invocations
            command = [str(executable), "--key", key(table), "--depth", str(depth),
                       "--out", str(report), "--max-working-mib", "8", "--threads", str(threads)]
            if compact:
                command.append("--compact")
            if forced:
                command.append("--force-hash-collisions")
            command += list(map(str, extra))
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
            invocations += 1
            assert (result.returncode == 0) == success, (command, result.stdout, result.stderr)
            data = json.loads(report.read_text())
            if not success:
                assert data["status"] == "incomplete" and data["reason"], data
                assert data["lower_bound"] == 1 and data["upper_bound"] is None and data["witness"] is None
            return data

        def check(table, depth, expected, *, forced=False, thread_counts=(1, 2, 4, 8)):
            for threads in thread_counts:
                data = run(table, depth, threads, forced=forced)
                assert data["threads"] == threads
                assert data["compact_storage"] is True
                assert data["reason"] == ""
                if expected:
                    assert data["status"] == "collision-found" and data["upper_bound"] == depth
                    assert data["lower_bound"] == 1
                    a, b = data["witness"]
                    assert a != b and len(a) == len(b) == depth and set(a + b) <= {"0", "1"}
                    assert endpoints(table, a) == endpoints(table, b), (threads, table, data)
                else:
                    assert data["status"] == "collision-free" and data["lower_bound"] == depth + 1
                    assert data["upper_bound"] is None and data["witness"] is None
                    assert data["generated_representatives"] == 1 << (depth - 1)

        # All ordered one/two-state tables, including unreachable tails, loops,
        # coincident ports and static-mask revisits, padded to seven vertices.
        for m in (1, 2):
            for entries in itertools.product(range(m), repeat=2 * m):
                table = [tuple(entries[2 * state:2 * state + 2]) for state in range(m)]
                table += [(state, state) for state in range(m, 7)]
                for depth in range(1, 5):
                    check(table, depth, collision_at(table, depth))
        print(f"PASS ordered m<=2 tables: {invocations} serial/parallel runs", flush=True)

        # Every rooted accessible three-state class is independently generated
        # from ALL ordered labelled tables, with whole-word scalar exact scores.
        for length, small, _ in oracle().values():
            table = list(small) + [(state, state) for state in range(3, 7)]
            for depth in sorted({max(1, length - 1), length, length + 1}):
                check(table, depth, depth >= length)
        print(f"PASS all 57 independent m=3 classes: {invocations} total runs", flush=True)

        rng = random.Random(80321025)
        for _ in range(20):
            table = [((state + 1) % 7, rng.randrange(7)) for state in range(7)]
            for depth in (4, 7):
                check(table, depth, collision_at(table, depth))

        hard = [tuple(int(HARD_KEY[4 * state + 2 * port:4 * state + 2 * port + 2]) for port in range(2))
                for state in range(7)]
        small = [(0, 1), (1, 2), (0, 1)] + [(state, state) for state in range(3, 7)]
        # Constant fingerprints force a single large bucket. The hard negative
        # requires complete-profile comparisons to reject every hash match;
        # the positive m=3 pair is not an adjacent-only bucket shortcut.
        for table, depth in ((hard, 8), (small, 5), (small, 6)):
            check(table, depth, collision_at(table, depth), forced=True)
        # Exercise actual parallel radix buckets above the small-sort threshold.
        check(hard, 12, collision_at(hard, 12))

        # Repeated early own-complement hits must join all workers before the
        # backing array and report are released. No shortest score is claimed.
        loops = [(0, 0)] * 7
        for _ in range(40):
            check(loops, 16, True, thread_counts=(8,))
        for threads in (1, 2, 4, 8):
            run(hard, 24, threads, extra=("--max-working-mib", 1), success=False)
            run(hard, 24, threads, extra=("--max-working-mib", 96, "--timeout-ms", 1), success=False)
            # Hashes fit into 1MiB, but all matching complete states do not.
            # Every parallel overflow/cancellation must remain incomplete.
            run(hard, 16, threads, forced=True, extra=("--max-working-mib", 1), success=False)

        for invalid in (0, -1, 65, "bad"):
            run(hard, 4, invalid, success=False)
        run(hard, 4, 2, compact=False, success=False)
        # Existing serial normal-storage mode remains supported.
        serial = run(hard, 8, 1, compact=False)
        assert serial["status"] == "collision-free" and serial["lower_bound"] == 9
        # The default without a --threads option is still serial.
        result = subprocess.run([str(executable), "--key", HARD_KEY, "--depth", "4",
                                 "--out", str(report), "--compact"], capture_output=True, text=True, timeout=30)
        invocations += 1
        assert result.returncode == 0 and json.loads(report.read_text())["threads"] == 1
    print(f"PASS: {invocations} independent serial/2/4/8-thread cases, full128-mask witnesses, "
          "constant hashes, radix buckets, early-hit joins and fail-closed resource/timeout/thread guards.")


if __name__ == "__main__":
    main()

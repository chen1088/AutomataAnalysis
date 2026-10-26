"""Cross-check the independent single-layer native verifier by word/mask loops."""
import argparse
from itertools import combinations_with_replacement, product
import json
from pathlib import Path
import random
import subprocess
import tempfile


def endpoints(table, word):
    states = []
    for mask in range(128):
        state = 0
        for letter in word:
            state = table[state][int(letter) ^ ((mask >> state) & 1)]
        states.append(state)
    return tuple(states)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    args = parser.parse_args()
    cases = []
    for m in (1, 2):
        pairs = list(combinations_with_replacement(range(m), 2))
        for rows in product(pairs, repeat=m):
            table = list(rows) + [(i, i) for i in range(m, 7)]
            cases.extend((table, d, False) for d in range(1, 5))
    # Both sides of the least collision, with arbitrary revisits and fixed bits.
    table = [(0, 1), (1, 2), (0, 1)] + [(i, i) for i in range(3, 7)]
    cases.extend((table, d, forced) for d in range(1, 7) for forced in (False, True))
    rng = random.Random(20261025)
    for _ in range(8):
        table = [(rng.randrange(7), rng.randrange(7)) for _ in range(7)]
        cases.extend((table, d, forced) for d in (4, 6) for forced in (False, True))
    hard = [(0, 1), (2, 3), (4, 5), (4, 6), (2, 6), (5, 6), (0, 1)]
    # Exercise actual in-place radix buckets above the small-sort threshold,
    # and a deliberately constant hash bucket with distinct complete states.
    cases.extend((hard, d, forced) for d, forced in ((8, False), (8, True), (12, False)))
    with tempfile.TemporaryDirectory() as temp:
        report = Path(temp) / "report.json"
        for table, depth, forced in cases:
          for compact in (False, True):
            key = "".join(f"{v:02}" for row in table for v in row)
            words = ["".join(w) for w in product("01", repeat=depth)]
            states = [endpoints(table, w) for w in words]
            free = len(set(states)) == len(states)
            command = [str(args.exe.resolve()), "--key", key, "--depth", str(depth), "--out", str(report)]
            if forced:
                command.append("--force-hash-collisions")
            if compact:
                command.append("--compact")
            result = subprocess.run(command, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr + result.stdout
            data = json.loads(report.read_text())
            assert data["status"] == ("collision-free" if free else "collision-found"), (key, depth, forced, data)
            if free:
                assert data["lower_bound"] == depth + 1
                assert data["generated_representatives"] == 2 ** (depth - 1)
            else:
                a, b = data["witness"]
                assert a != b and len(a) == len(b) == depth
                assert endpoints(table, a) == endpoints(table, b)
        key = "0001020304050406020605060001"
        result = subprocess.run([str(args.exe.resolve()), "--key", key, "--depth", "28", "--out", str(report),
                                 "--max-working-mib", "1"], capture_output=True, text=True)
        assert result.returncode != 0
        data = json.loads(report.read_text())
        assert data["status"] == "incomplete" and data["lower_bound"] == 1 and data["witness"] is None
        result = subprocess.run([str(args.exe.resolve()), "--key", '"' + key[1:], "--depth", "2",
                                 "--out", str(report)], capture_output=True, text=True)
        assert result.returncode != 0
        assert json.loads(report.read_text())["status"] == "incomplete"
        for bad in ("4294967297", "-1", "2junk"):
            result = subprocess.run([str(args.exe.resolve()), "--out", str(report), "--key", key,
                                     "--depth", bad], capture_output=True, text=True)
            assert result.returncode != 0
            assert json.loads(report.read_text())["status"] == "incomplete"
    print(f"PASS: {2 * len(cases)} independently enumerated layer checks, forced hashes and memory cap")


if __name__ == "__main__":
    main()

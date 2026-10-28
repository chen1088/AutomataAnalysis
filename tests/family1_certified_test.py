"""Analytic and adversarial checks for the certified multi-seed finder.

The oracle here uses literal seed/mask/word loops, never the native products.
"""
import argparse
import copy
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "scripts/family1_check_certificate.py"


def key(rows):
    return "".join(f"{v:02d}" for row in rows for v in row)


def chain(r):
    return [(j, j + 1) for j in range(r)] + [(r, r)]


def prefix_two():
    return [(1, 2), (3, 4), (5, 6)] + [(j, j) for j in range(3, 7)]


def delayed_chain(r):
    return [(1, 2), (3, 3), (3, 3)] + [(3+j, 4+j) for j in range(r)] + [(3+r, 3+r)]


def endpoint(rows, mask, word, root=0):
    state = root
    for letter in word:
        state = rows[state][int(letter) ^ ((mask >> state) & 1)]
    return state


def profile(seeds, word):
    return tuple(endpoint(rows, mask, word, root) for rows, root in seeds
                 for mask in range(1 << len(rows)))


def oracle_collision(seeds, horizon):
    seen = {}
    for letters in product("01", repeat=horizon):
        word = "".join(letters)
        value = profile(seeds, word)
        if value in seen:
            return seen[value], word
        seen[value] = word
    return None


def signature(u, v, kind):
    a, b = u.count("1"), v.count("1")
    if kind == "count":
        return a, b, -1, -1
    first = next((j for j, pair in enumerate(zip(u, v)) if pair[0] != pair[1]), -1)
    return a, b, first, u[:first].count("1") if first >= 0 else -1


def local_signatures(rows, mask, prefix_u, prefix_v, horizon, kind):
    words = ["".join(w) for w in product("01", repeat=horizon)]
    result = set()
    for u in words:
        for v in words:
            if prefix_u + u != prefix_v + v and endpoint(rows, mask, prefix_u + u) == endpoint(rows, mask, prefix_v + v):
                result.add(signature(u, v, kind))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    executable = args.exe.resolve()
    checks = 0
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        serial = 0

        def run(seeds, horizon=None, extra=(), check=True):
            nonlocal serial, checks
            serial += 1
            output = directory / f"case-{serial}.json"
            command = [str(executable)]
            for rows, root in seeds:
                command += ["--seed", key(rows), "--root", str(root)]
            if horizon is not None:
                command += ["--horizon", str(horizon)]
            command += ["--timeout-ms", "30000", "--out", str(output), *map(str, extra)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=50)
            assert output.is_file(), (command, completed.returncode, completed.stdout, completed.stderr)
            report = json.loads(output.read_text())
            assert report["schema"] == "family1-certified-v1", report
            assert report["family"]["observer_count"] == sum(1 << len(rows) for rows, _ in seeds)
            assert [seed["ports"] for seed in report["family"]["seeds"]] == [[list(row) for row in rows] for rows, _ in seeds]
            assert [seed["root"] for seed in report["family"]["seeds"]] == [root for _, root in seeds]
            if check:
                checked = subprocess.run([sys.executable, str(CHECKER), str(output),
                                          "--max-work", "10000000", "--max-states", "1000000"],
                                         capture_output=True, text=True, timeout=50)
                assert checked.returncode == 0, (report, checked.stdout, checked.stderr)
            checks += 1
            return report, output, completed

        def analytic(seeds, horizon, collision):
            report, path, completed = run(seeds, horizon)
            assert completed.returncode == 0, completed.stderr
            assert report["status"] == ("witness" if collision else "excluded"), report
            assert bool(oracle_collision(seeds, horizon)) == collision
            if collision:
                witness = report["witness"]
                u, v = witness["u"], witness["v"]
                assert len(u) == len(v) == horizon and u != v
                assert profile(seeds, u) == profile(seeds, v)
                assert report["upper_bound"] == horizon
            else:
                assert report["lower_bound"] == horizon + 1 and report["upper_bound"] is None
                assert report["proof"]["kind"] == "paired-layers"
            return report, path

        # Full closures, both sides of each exact chain horizon, and the empty
        # layer: identical empty words must never become an upper witness.
        excluded, excluded_path = analytic([(chain(1), 0)], 1, False)
        analytic([(chain(1), 0)], 0, False)
        for r in (1, 2, 3):
            analytic([(chain(r), 0)], 2*r-1, False)
            analytic([(chain(r), 0)], 2*r, True)

        # A fixed horizon larger than the first selected collision must still
        # return a pair of the requested length (common-suffix padding).
        analytic([([(0, 0)], 0)], 7, True)

        # Different state counts and two entire original closures share words.
        for r in (1, 2):
            seeds = [(prefix_two(), 0), (delayed_chain(r), 0)]
            analytic(seeds, 2*r+1, False)
            analytic(seeds, 2*r+2, True)

        last_bit = [(0, 1), (0, 1)]
        clock = [(1, 1), (0, 0)]
        product_seed = [(1, 3), (0, 2), (1, 3), (0, 2)]
        analytic([(last_bit, 0), (clock, 0)], 3, True)
        analytic([(product_seed, 0)], 3, False)
        analytic([(product_seed, 0)], 4, True)
        duplicate, _ = analytic([(last_bit, 0), (last_bit, 0)], 2, False)
        assert duplicate["family"]["observer_count"] == 8
        analytic([(last_bit, 1)], 2, False)
        analytic([(last_bit, 1)], 3, True)

        # Count joins can preserve incompatible local word choices. A richer
        # order statistic must remove the surviving cases on this chain.
        for kind, expected in (("count", "signature-survives"), ("first-difference", "excluded")):
            report, _, _ = run([(chain(2), 0)], 3, ("--signature", kind))
            assert report["status"] == expected, report
            if expected == "excluded":
                assert report["lower_bound"] == 4
                signature_exclusion = copy.deepcopy(report)
            else:
                assert report["lower_bound"] == 1 and report["upper_bound"] is None

        # The prefixes have already differed, so equal continuations are legal.
        # Scalar projection tables independently establish remaining bound 4.
        rows = chain(3)
        for horizon in (3, 4):
            report, _, _ = run([(rows, 0)], horizon, ("--signature", "count", "--prefix-u", "01", "--prefix-v", "10"))
            sets = [local_signatures(rows, mask, "01", "10", horizon, "count") for mask in range(1 << len(rows))]
            intersection = set.intersection(*sets)
            assert bool(intersection) == (horizon == 4)
            assert report["status"] == ("signature-survives" if intersection else "excluded"), report
            assert report["lower_bound"] == 1, "residual proof must not raise global bound"
            if not intersection:
                assert report["remaining_lower_bound"] == 4
            proof = report.get("proof")
            if proof:
                for group in proof["groups"]:
                    assert len(group["observers"]) == 1
                    mask = group["observers"][0]["mask"]
                    assert {tuple(value) for value in group["accepted"]} == sets[mask]

        # Original mask and reached state remain correlated after common prefix.
        report, _, _ = run([(chain(1), 0)], 3, ("--upper-u", "001", "--upper-v", "011"))
        assert report["upper_bound"] == 3 and report["witness"] is not None

        # A verified incumbent survives unfinished proof work; the counters are
        # cumulative across queries/refinements, not a fresh budget each time.
        report, _, _ = run([(last_bit, 0)], 2, ("--states", "1", "--upper-u", "000", "--upper-v", "110"))
        assert report["status"] == "unresolved" and report["lower_bound"] == 1 and report["upper_bound"] == 3
        report, _, _ = run([(last_bit, 0)], 2, ("--work", "1"))
        assert report["status"] == "unresolved" and report["lower_bound"] == 1 and report["upper_bound"] is None
        report, _, _ = run([(last_bit, 0)], 3, ("--verifier-steps", "1"))
        assert report["status"] == "unresolved" and report["upper_bound"] is None
        report, _, _ = run([(chain(2), 0)], 3, ("--signature", "first-difference", "--states", "1"))
        assert report["status"] == "unresolved" and report["lower_bound"] == 1

        report, _, _ = run([(last_bit, 0)], None, ("--gap", "0", "--upper-u", "000", "--upper-v", "110"))
        assert report["status"] == "interval-certified" and report["lower_bound"] == report["upper_bound"] == 3
        report, _, _ = run([(last_bit, 0), (clock, 0)], None,
                           ("--gap", "0", "--heuristic-expansions", "1000", "--heuristic-k", "2",
                            "--heuristic-beam", "2", "--heuristic-length", "8"))
        assert report["status"] == "interval-certified" and report["lower_bound"] == report["upper_bound"] == 3
        assert report["heuristic"]["enabled"] and report["heuristic"]["expansions"] > 0
        report, _, _ = run([(last_bit, 0), (clock, 0)], None,
                           ("--gap", "0", "--upper-u", "000", "--upper-v", "110",
                            "--heuristic-expansions", "1000", "--work", "1"))
        assert report["status"] == "unresolved" and report["lower_bound"] == 1 and report["upper_bound"] == 3
        # An imported exact incumbent already meets the gap. Optional work must
        # not consume the tiny budget and turn that success into unresolved.
        report, _, _ = run([([(0, 0)], 0)], None,
                           ("--gap", "0", "--upper-u", "0", "--upper-v", "1",
                            "--heuristic-expansions", "1000", "--states", "1"))
        assert report["status"] == "interval-certified" and report["lower_bound"] == report["upper_bound"] == 1
        assert report["work"]["states"] == 0 and report["heuristic"]["expansions"] == 0
        # This L run adds one observer at horizon7 and another at horizon2.
        # The refinement cap must apply to the complete multi-query run.
        for cap in (1, 2):
            report, _, _ = run([(last_bit, 0)], None,
                               ("--gap", "0", "--upper-u", "00000000", "--upper-v", "11000000",
                                "--refinements", str(cap)))
            additions = sum(len(attempt.get("refinements", [])) for attempt in report["attempts"])
            assert report["work"]["refinements"] == additions == cap
            assert len(report["attempts"]) > 1 and report["upper_bound"] == 3
            if cap == 1:
                assert report["status"] == "unresolved" and report["lower_bound"] == 1
            else:
                assert report["status"] == "interval-certified" and report["lower_bound"] == 3

        # The verifier may not import a witness for one closure as a witness for
        # their union. Such input is an error or unresolved with no upper bound.
        serial += 1
        invalid_out = directory / f"invalid-{serial}.json"
        bad = subprocess.run([str(executable), "--seed", key(prefix_two()), "--seed", key(delayed_chain(1)),
                              "--horizon", "3", "--upper-u", "000", "--upper-v", "001", "--out", str(invalid_out)],
                             capture_output=True, text=True, timeout=30)
        assert bad.returncode != 0, bad.stdout
        if invalid_out.exists():
            assert json.loads(invalid_out.read_text()).get("upper_bound") is None

        # A separate checker must reject missing proof branches, inflated bounds,
        # and a certificate pinned to a different declared family.
        for mutation in ("missing-layer", "inflated-bound", "false-exact", "false-interval"):
            tampered = copy.deepcopy(excluded)
            if mutation == "missing-layer":
                tampered["proof"]["layers"][-1] = []
            elif mutation == "inflated-bound":
                tampered["lower_bound"] += 1
            elif mutation == "false-exact":
                tampered["exact"] = True
            else:
                tampered["status"] = "interval-certified"
                tampered["requested_gap"] = 0
            path = directory / f"{mutation}.json"
            path.write_text(json.dumps(tampered))
            checked = subprocess.run([sys.executable, str(CHECKER), str(path)], capture_output=True, text=True)
            assert checked.returncode != 0, (mutation, checked.stdout)
        tampered = copy.deepcopy(signature_exclusion)
        group = next(group for group in tampered["proof"]["groups"] if group["accepted"])
        group["accepted"] = []
        path = directory / "missing-signatures.json"
        path.write_text(json.dumps(tampered))
        checked = subprocess.run([sys.executable, str(CHECKER), str(path)], capture_output=True, text=True)
        assert checked.returncode != 0, checked.stdout
        checked = subprocess.run([sys.executable, str(CHECKER), str(excluded_path), "--max-work", "1"], capture_output=True, text=True)
        assert checked.returncode == 2, (checked.stdout, checked.stderr)
        mismatch = directory / "wrong-input.json"
        mismatch.write_text(json.dumps({"seeds": [{"name": "other", "root": 0, "ports": [[0, 0]]}]}))
        checked = subprocess.run([sys.executable, str(CHECKER), str(excluded_path), "--input", str(mismatch)], capture_output=True, text=True)
        assert checked.returncode != 0, checked.stdout

    print(f"PASS: {checks} certified reports, analytic/scalar oracles, resource caps, and adversarial proof checks")


if __name__ == "__main__":
    main()

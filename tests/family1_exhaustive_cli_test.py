"""Exercise the exhaustive CLI against an independent small scalar oracle."""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def canonical(table):
    best = None
    for tail in itertools.permutations(range(1, len(table))):
        permutation = (0,) + tail
        transformed = [None] * len(table)
        for source, row in enumerate(table):
            transformed[permutation[source]] = tuple(sorted(permutation[t] for t in row))
        candidate = tuple(transformed)
        best = candidate if best is None else min(best, candidate)
    return best


def endpoint(table, mask, word):
    state = 0
    for letter in word:
        state = table[state][int(letter) ^ ((mask >> state) & 1)]
    return state


def oracle():
    result = {}
    for values in itertools.product(range(3), repeat=6):
        table = tuple(tuple(values[2 * state:2 * state + 2]) for state in range(3))
        seen = {0}
        while True:
            expanded = seen | {target for state in seen for target in table[state]}
            if expanded == seen:
                break
            seen = expanded
        if len(seen) != 3:
            continue
        table = canonical(table)
        key = "".join(f"{target:02d}" for row in table for target in row)
        if key in result:
            continue
        for depth in range(1, 7):
            profiles = {}
            witness = None
            for number in range(1 << depth):
                word = f"{number:0{depth}b}"
                profile = tuple(endpoint(table, mask, word) for mask in range(8))
                if profile in profiles:
                    witness = (profiles[profile], word)
                    break
                profiles[profile] = word
            if witness:
                result[key] = (depth, table, witness)
                break
        assert key in result
    assert len(result) == 57
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path,
                        default=ROOT / "out/build/msvc-vcpkg/Release/Family1Exhaustive.exe")
    args = parser.parse_args()
    executable = args.exe.resolve()
    expected = oracle()

    with tempfile.TemporaryDirectory(prefix="family1-exhaustive-test-", dir=ROOT / "out") as name:
        temporary = Path(name).resolve()
        assert temporary.is_relative_to((ROOT / "out").resolve())

        def run(directory, depth=6, extra=(), success=True):
            command = [str(executable), "--out", str(directory), "--states", "3",
                       "--target", "6", "--depth", str(depth), "--max-layer-states", "64",
                       "--batch-size", "11", "--jobs", "3", *map(str, extra)]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            assert (completed.returncode == 0) == success, completed.stdout + completed.stderr
            return completed

        def records(directory):
            return [json.loads(line) for line in (directory / "checkpoint.jsonl").read_text().splitlines()]

        def validate(directory):
            values = records(directory)
            assert len(values) == len(expected)
            for ordinal, value in enumerate(values):
                assert value["ordinal"] == ordinal
                score, table, _ = expected[value["key"]]
                assert value["canonical_table"] == list(map(list, table))
                assert value["lower_bound"] <= score
                if value["upper_bound"] is not None:
                    assert value["upper_bound"] >= score
                    a, b = value["witness"]
                    assert len(a) == len(b) == value["upper_bound"] and a != b
                    assert all(endpoint(table, mask, a) == endpoint(table, mask, b) for mask in range(8))
                if value["status"] == "exact":
                    assert value["merge_length"] == score
            return values

        preserved = temporary / "preserved"
        preserved.mkdir()
        sentinel = preserved / "unrelated.txt"
        sentinel.write_bytes(b"preserve existing user data\n")
        run(preserved, success=False)
        assert sentinel.read_bytes() == b"preserve existing user data\n"
        assert list(preserved.iterdir()) == [sentinel]

        full = temporary / "full"
        run(full)
        validate(full)
        summary = json.loads((full / "summary.json").read_text())
        assert summary["maximum_value_certified"] and summary["maximizing_collection_complete"]
        assert summary["maximum_merge_length"] == 6 and summary["maximizer_count"] == 2
        assert len((full / "maximizers.jsonl").read_text().splitlines()) == 2
        single = temporary / "single"
        run(single, extra=("--jobs", "1"))
        assert (single / "checkpoint.jsonl").read_bytes() == (full / "checkpoint.jsonl").read_bytes()

        resumed = temporary / "resumed"
        run(resumed, extra=("--limit-graphs", "13"))
        assert len(records(resumed)) == 13
        assert not json.loads((resumed / "summary.json").read_text())["enumeration_complete"]
        with (resumed / "checkpoint.jsonl").open("ab") as stream:
            stream.write(b'{"torn":')
        run(resumed, extra=("--resume",))
        assert (resumed / "checkpoint.jsonl").read_bytes() == (full / "checkpoint.jsonl").read_bytes()
        before_alias = (resumed / "checkpoint.jsonl").read_bytes()
        run(resumed, extra=("--resume", "--input", resumed / "checkpoint.jsonl"), success=False)
        assert (resumed / "checkpoint.jsonl").read_bytes() == before_alias

        shallow = temporary / "shallow"
        run(shallow, depth=2)
        before = validate(shallow)
        assert not json.loads((shallow / "summary.json").read_text())["maximum_value_certified"]
        refined = temporary / "refined"
        run(refined, extra=("--input", shallow / "checkpoint.jsonl"))
        after = validate(refined)
        for old, new in zip(before, after):
            assert new["lower_bound"] >= old["lower_bound"]
            if old["upper_bound"] is not None:
                assert new["upper_bound"] <= old["upper_bound"]
        assert json.loads((refined / "summary.json").read_text())["maximizer_count"] == 2

        weighted_seed = temporary / "weighted-seed.jsonl"
        weighted_seed.write_text('{"witness":["0","1"],"frequency":5}\n'
                                 '{"witness":["0","1"]}\n')
        weighted = temporary / "weighted"
        run(weighted, extra=("--seed", weighted_seed))
        validate(weighted)
        weights = [json.loads(line) for line in (weighted / "initial-witnesses.jsonl").read_text().splitlines()]
        assert weights == [{"witness": ["0", "1"], "frequency": 6}]
        assert json.loads((weighted / "summary.json").read_text())["maximizer_count"] == 2
        zero_seed = temporary / "zero-seed.jsonl"
        zero_seed.write_text('{"witness":["0","1"],"frequency":0}\n')
        run(temporary / "bad-seed", extra=("--seed", zero_seed), success=False)

        # An independently simulated completed layer provides a valid fixture
        # for import plumbing. The CLI retains its bytes and source provenance;
        # a report is never described as a self-verifying proof trace.
        winner_key, (length, table, witness) = next((key, value) for key, value in expected.items() if value[0] == 6)
        layer = temporary / "layer-free.json"
        layer.write_text(json.dumps({
            "method": "independent-one-hot-DFS-hash-radix-full-state-replay",
            "m": 3, "key": winner_key, "depth": 5, "status": "collision-free",
            "lower_bound": 6, "upper_bound": None, "witness": None,
            "generated_representatives": 16, "hash_matches_replayed": 0,
            "seconds": 0, "reason": "",
        }, separators=(",", ":")) + "\n")
        upper = temporary / "layer-collision.json"
        upper.write_text(json.dumps({
            "method": "independent-one-hot-DFS-hash-radix-full-state-replay",
            "m": 3, "key": winner_key, "depth": length, "status": "collision-found",
            "lower_bound": 1, "upper_bound": length, "witness": witness,
            "generated_representatives": 32, "hash_matches_replayed": 1,
            "seconds": 0, "reason": "",
        }, separators=(",", ":")) + "\n")
        imported = temporary / "imported"
        run(imported, depth=0, extra=("--layer-report", layer, "--layer-report", upper))
        found = next(value for value in validate(imported) if value["key"] == winner_key)
        assert found["status"] == "exact" and found["merge_length"] == 6
        provenance = [json.loads(line) for line in (imported / "layer-report-provenance.jsonl").read_text().splitlines()]
        assert provenance[0]["byte_content"] == layer.read_bytes().decode()
        assert provenance[1]["byte_content"] == upper.read_bytes().decode()
        imported_summary = json.loads((imported / "summary.json").read_text())
        assert imported_summary["external_lower_reports_imported"] == 1
        assert imported_summary["external_upper_reports_imported"] == 1
        changed_report = json.loads(layer.read_text())
        changed_report["seconds"] = 1
        layer.write_text(json.dumps(changed_report, separators=(",", ":")) + "\n")
        run(imported, depth=0, extra=("--resume", "--layer-report", layer, "--layer-report", upper), success=False)
        invalid_layer = temporary / "bad-layer.json"
        bad = json.loads(layer.read_text())
        bad["generated_representatives"] = 15
        invalid_layer.write_text(json.dumps(bad, separators=(",", ":")))
        run(temporary / "bad-import", extra=("--layer-report", invalid_layer), success=False)

        lines = (resumed / "checkpoint.jsonl").read_text().splitlines()
        bad = json.loads(lines[0])
        bad["lower_bound"] = 999
        lines[0] = json.dumps(bad, separators=(",", ":"))
        (resumed / "checkpoint.jsonl").write_text("\n".join(lines) + "\n")
        run(resumed, extra=("--resume",), success=False)

        seven = temporary / "seven-layer"
        completed = subprocess.run([
            str(executable), "--out", str(seven), "--states", "7", "--target", "31",
            "--depth", "8", "--max-layer-states", "256", "--max-working-mib", "16",
            "--batch-size", "4", "--jobs", "2", "--limit-graphs", "8", "--backend", "layer",
        ], cwd=ROOT, text=True, capture_output=True)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        for value in records(seven):
            table = value["canonical_table"]
            exact = None
            for depth in range(1, 9):
                profiles = set()
                for number in range(1 << depth):
                    word = f"{number:0{depth}b}"
                    state = tuple(endpoint(table, mask, word) for mask in range(128))
                    if state in profiles:
                        exact = depth
                        break
                    profiles.add(state)
                if exact is not None:
                    break
            if exact is not None:
                assert value["lower_bound"] <= exact
                assert value["upper_bound"] is not None and value["upper_bound"] >= exact
            else:
                assert value["lower_bound"] <= 9 and value["upper_bound"] is None
            if value["upper_bound"] is not None:
                a, b = value["witness"]
                assert a != b and len(a) == len(b) == value["upper_bound"]
                assert all(endpoint(table, mask, a) == endpoint(table, mask, b) for mask in range(128))
        assert not json.loads((seven / "summary.json").read_text())["maximum_value_certified"]
        configuration = json.loads((seven / "run.json").read_text())
        assert configuration["method"] == "family1-exhaustive-witness-cover-layer-v1"
        assert configuration["layer_step"] == 2
        assert configuration["layer_storage"] == "packed"

    print("Exhaustive CLI passed: independent 57-class oracle, all ties, bounded coverage, deterministic resume, refinement, and layer provenance.")


if __name__ == "__main__":
    main()

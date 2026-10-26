"""Proof-preserving journal transport, including interruption and rejection."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    transport = module("journal_transport", ROOT / "scripts/family1_merge_journals.py")
    reference = module("small_scalar_oracle", ROOT / "tests/family1_exhaustive_cli_test.py").oracle()
    exact = []
    for ordinal, (key, (length, table, witness)) in enumerate(sorted(reference.items())):
        exact.append(dict(m=3, ordinal=ordinal, key=key, canonical_table=table, status="exact",
                          lower_bound=length, upper_bound=length, merge_length=length,
                          witness=witness, reason="independent-small-oracle"))
    base_records = [dict(r, status="depth-capped", lower_bound=1, upper_bound=None,
                         merge_length=None, witness=None, reason="depth") for r in exact]
    encode = lambda rows: b"".join(json.dumps(r, separators=(",", ":")).encode() + b"\n" for r in rows)
    with tempfile.TemporaryDirectory(prefix="family1-merge-test-", dir=ROOT / "out") as temporary:
        directory = Path(temporary).resolve()
        assert directory.is_relative_to((ROOT / "out").resolve())
        base, refinement = directory / "base.jsonl", directory / "refinement.jsonl"
        base.write_bytes(encode(base_records))
        for n, fragment in ((0, b""), (23, b'{"torn"'), (57, b"")):
            refinement.write_bytes(encode(exact[:n]) + fragment)
            before = [p.read_bytes() for p in (base, refinement)]
            output = directory / f"success-{n}"
            report = transport.merge(base, refinement, output, 3, 57)
            assert report["records"] == 57 and report["refined_prefix_records"] == n
            assert report["ignored_final_fragment_bytes"] == len(fragment)
            assert (output / "checkpoint.jsonl").read_bytes() == encode(exact[:n] + base_records[n:])
            assert report["merged_sha256"] == hashlib.sha256((output / "checkpoint.jsonl").read_bytes()).hexdigest()
            assert [p.read_bytes() for p in (base, refinement)] == before
            assert not (output / "summary.json").exists()  # transport certifies no scores

        def rejected(rows, name, expected=57):
            refinement.write_bytes(encode(rows))
            before = [p.read_bytes() for p in (base, refinement)]
            output = directory / name
            try:
                transport.merge(base, refinement, output, 3, expected)
            except (ValueError, KeyError):
                pass
            else:
                raise AssertionError("invalid merge accepted: " + name)
            assert [p.read_bytes() for p in (base, refinement)] == before
            assert not (output / "checkpoint.jsonl").exists()

        rejected([dict(exact[0], ordinal=1)], "bad-ordinal")
        rejected([dict(exact[0], key="bad")], "bad-key")
        rejected([dict(exact[0], lower_bound=0)], "bad-lower")
        rejected([dict(exact[0], witness=["0", "0"])], "bad-witness")
        rejected(exact[:1], "bad-total", expected=58)
        base.write_bytes(encode(exact))
        old = exact[0]
        weaker = dict(old, status="bounded", upper_bound=old["upper_bound"] + 1, merge_length=None,
                      witness=[word + "0" for word in old["witness"]])
        rejected([weaker], "weaker-upper")
        refinement.write_bytes(encode(exact[:1]))
        sentinel = directory / "preserved"
        sentinel.mkdir()
        (sentinel / "keep.txt").write_text("keep")
        try:
            transport.merge(base, refinement, sentinel, 3, 57)
        except ValueError:
            pass
        else:
            raise AssertionError("nonempty output accepted")
        assert (sentinel / "keep.txt").read_text() == "keep"
    print("PASS: 57-class oracle journal overlay, partial-prefix salvage, bound integrity and source/output preservation")


if __name__ == "__main__":
    main()

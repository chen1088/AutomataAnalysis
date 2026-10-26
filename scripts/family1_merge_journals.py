"""Overlay a completed refinement prefix on a full ordered graph journal.

Sources are never modified. Only a final unterminated refinement fragment is
ignored. This transports existing bounds; it does not certify their proofs.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def validate(data, ordinal, states, previous):
    require(data["m"] == states and data["ordinal"] == ordinal, "journal is not a consecutive selected-size prefix")
    table = data["canonical_table"]
    require(len(table) == states and all(len(row) == 2 and all(type(v) is int and 0 <= v < states for v in row)
                                      for row in table), "invalid table")
    require(data["key"] == "".join(f"{v:02d}" for row in table for v in row), "table/key mismatch")
    require(not previous or previous < data["key"], "keys are not strictly increasing")
    lower, upper = data["lower_bound"], data["upper_bound"]
    require(type(lower) is int and lower >= 1, "invalid lower bound")
    require(upper is None or (type(upper) is int and upper >= lower), "invalid upper bound")
    require(data["status"] in ("exact", "bounded", "depth-capped", "incomplete"), "invalid status")
    if data["status"] == "exact":
        require(data["merge_length"] == lower == upper, "invalid exact bounds")
    else:
        require(data["merge_length"] is None, "nonexact record claims merge length")
    if upper is None:
        require(data["witness"] is None, "witness lacks upper bound")
    else:
        pair = data["witness"]
        require(isinstance(pair, list) and len(pair) == 2 and pair[0] != pair[1]
                and all(isinstance(w, str) and len(w) == upper and set(w) <= {"0", "1"} for w in pair),
                "invalid upper witness shape")


def merge(base, refinement, output, states, expected_count):
    base, refinement, output = Path(base).resolve(), Path(refinement).resolve(), Path(output).resolve()
    require(base.is_file() and refinement.is_file() and base != refinement, "two different input journals are required")
    require(not output.exists() or (output.is_dir() and not any(output.iterdir())), "output must be new or empty")
    require(not base.is_relative_to(output) and not refinement.is_relative_to(output), "output cannot contain a source")
    output.mkdir(parents=True, exist_ok=True)
    before = [(p.stat().st_size, p.stat().st_mtime_ns) for p in (base, refinement)]
    hashes = [hashlib.sha256(), hashlib.sha256()]
    merged_hash = hashlib.sha256()
    count = refined = ignored = 0
    previous = ""
    pairs = Counter()
    partial = output / "checkpoint.partial"
    with base.open("rb") as original, refinement.open("rb") as newer, partial.open("xb") as destination:
        while True:
            line = newer.readline()
            if not line:
                break
            hashes[1].update(line)
            if not line.endswith(b"\n"):
                ignored = len(line)
                break
            baseline = original.readline()
            require(baseline.endswith(b"\n"), "refinement exceeds the committed base")
            hashes[0].update(baseline)
            old, new = json.loads(baseline), json.loads(line)
            validate(old, count, states, previous)
            validate(new, count, states, previous)
            require(old["key"] == new["key"] and old["canonical_table"] == new["canonical_table"],
                    "refinement changed graph identity")
            require(new["lower_bound"] >= old["lower_bound"], "refinement weakened a lower bound")
            require(old["upper_bound"] is None or (new["upper_bound"] is not None
                    and new["upper_bound"] <= old["upper_bound"]), "refinement weakened an upper bound")
            destination.write(line)
            merged_hash.update(line)
            if new["witness"] is not None:
                pairs[tuple(new["witness"])] += 1
            previous = new["key"]
            count += 1
            refined += 1
        for line in original:
            require(line.endswith(b"\n"), "base contains an uncommitted fragment")
            hashes[0].update(line)
            record = json.loads(line)
            validate(record, count, states, previous)
            destination.write(line)
            merged_hash.update(line)
            previous = record["key"]
            count += 1
    require(count == expected_count, f"expected {expected_count} base classes, found {count}")
    require(before == [(p.stat().st_size, p.stat().st_mtime_ns) for p in (base, refinement)],
            "source changed during merge; stop its writer first")
    # Exclusive output directory prevents replacing any existing checkpoint.
    partial.rename(output / "checkpoint.jsonl")
    with (output / "refinement-witnesses.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for pair, frequency in sorted(pairs.items()):
            stream.write(json.dumps({"witness": pair, "frequency": frequency}, separators=(",", ":")) + "\n")
    provenance = {"m": states, "records": count, "refined_prefix_records": refined,
                  "ignored_final_fragment_bytes": ignored,
                  "sources": [{"path": str(p), "sha256": h.hexdigest()} for p, h in zip((base, refinement), hashes)],
                  "merged_sha256": merged_hash.hexdigest(), "witness_pairs": len(pairs),
                  "note": "No source changed. Bound transport only; witness and lower proofs require their verifiers."}
    (output / "merge-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(f"Merged {count} classes: {refined} refined prefix records; {ignored} trailing fragment bytes ignored")
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--refinement", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--states", type=int, default=7)
    parser.add_argument("--expected-count", type=int, default=4166855)
    args = parser.parse_args()
    require(1 <= args.states <= 20 and args.expected_count > 0, "invalid state/count arguments")
    merge(args.base, args.refinement, args.out, args.states, args.expected_count)


if __name__ == "__main__":
    main()

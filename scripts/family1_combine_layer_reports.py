"""Combine completed single-layer runs for one exact individual graph score."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lower", type=Path, required=True)
    parser.add_argument("--upper", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    lower = json.loads(args.lower.read_text())
    upper = json.loads(args.upper.read_text())
    method = "independent-one-hot-DFS-hash-radix-full-state-replay"
    assert lower["method"] == upper["method"] == method
    assert lower["m"] == upper["m"] == 7 and lower["key"] == upper["key"]
    assert lower["status"] == "collision-free" and not lower["reason"] and not upper["reason"]
    assert lower["generated_representatives"] == 2 ** (lower["depth"] - 1)
    length = lower["depth"] + 1
    assert upper["status"] == "collision-found" and upper["depth"] == length
    key = lower["key"]
    table = [[int(key[i:i + 2]), int(key[i + 2:i + 4])] for i in range(0, 28, 4)]
    a, b = upper["witness"]
    assert a != b and len(a) == len(b) == length
    for mask in range(128):
        endpoints = []
        for word in (a, b):
            state = 0
            for c in word:
                state = table[state][int(c) ^ ((mask >> state) & 1)]
            endpoints.append(state)
        assert endpoints[0] == endpoints[1]
    result = {"m": 7, "key": key, "canonical_table": table, "status": "exact",
              "merge_length": length, "lower_bound": length, "upper_bound": length,
              "witness": [a, b], "global_maximum_certified": False,
              "provenance_note": "Individual completed-run evidence; lower proof requires rerunning the independent checker.",
              "source_reports": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                 for p in (args.lower, args.upper)]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Exact individual H={length}; witness independently replayed on all 128 masks; no global claim")


if __name__ == "__main__":
    main()

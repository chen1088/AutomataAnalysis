#!/usr/bin/env python3
"""Replay newly constructed pairs across graph classes, without saved witnesses.

The only graph inputs are keys in the controlled lookahead-grid rows. Pair
inputs are native finder results referenced by those rows or explicit target34
attempt directories. No maximizer/known-witness dataset is opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = [
    "results/family1-finder-lookahead-grid-v1/runs.jsonl",
    "results/family1-finder-lookahead-grid-v2/runs.jsonl",
    "results/family1-finder-target34-k6-w16/runs.jsonl",
]
DEFAULT_ATTEMPTS = [
    "out/family1-target34-k8-complete-prefix20",
    "out/family1-target34-k16-complete-prefix20",
    "out/family1-target34-distance-k8-16-prefix20",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path: Path) -> dict:
    path = path.resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "sha256": sha256(path)}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def table_from_key(key: str) -> list[list[int]]:
    assert len(key) == 28 and key.isdigit()
    values = [int(key[i:i + 2]) for i in range(0, len(key), 2)]
    assert all(0 <= value < 7 for value in values)
    return [values[i:i + 2] for i in range(0, len(values), 2)]


def endpoint(table: list[list[int]], mask: int, word: str) -> int:
    state = 0
    for bit in word:
        # The same bit of mask is read every time this state is revisited.
        state = table[state][int(bit) ^ ((mask >> state) & 1)]
    return state


def canonical_pair(pair) -> tuple[str, str]:
    assert len(pair) == 2 and pair[0] != pair[1]
    assert len(pair[0]) == len(pair[1]) == 34
    assert set(pair[0] + pair[1]) <= {"0", "1"}
    return tuple(sorted(pair))


def pair_id(pair: tuple[str, str]) -> str:
    return hashlib.sha256((pair[0] + "\n" + pair[1] + "\n").encode()).hexdigest()


def self_check() -> None:
    # A revisit must use the original mask bit; both loops/coincident ports occur.
    table = [[0, 1], [1, 1]]
    assert endpoint(table, 0, "0001") == 1
    assert endpoint(table, 1, "0001") == 1
    assert endpoint(table, 0, "000") == 0
    assert endpoint(table, 1, "000") == 1
    # Complementing each input bit is precisely complementing every mask bit.
    for mask in range(4):
        for word in ["", "01001", "11100"]:
            other = word.translate(str.maketrans("01", "10"))
            assert endpoint(table, mask, other) == endpoint(table, mask ^ 3, word)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", default=DEFAULT_RUNS)
    parser.add_argument("--attempt-roots", nargs="+", default=DEFAULT_ATTEMPTS)
    parser.add_argument("--output", default="results/family1-constructed-pair-transfer")
    args = parser.parse_args()
    self_check()
    graphs = {}
    inventory = {}
    provenance = {}
    containers = []

    def consider(path: Path, expected_hash=None, origin=None) -> None:
        source = reference(path)
        if expected_hash is not None:
            assert source["sha256"] == expected_hash, f"Native result changed: {path}"
        data = read_json(path)
        key = data.get("key", data.get("source_key"))
        assert key in {g["key"] for g in graphs.values()}
        ordinal = next(o for o, g in graphs.items() if g["key"] == key)
        found = data.get("upper_bound") == 34 and data.get("witness") is not None
        entry = inventory.setdefault(source["path"], {
            **source, "ordinal": ordinal, "key": key,
            "decision": data.get("decision"), "upper_bound": data.get("upper_bound"),
            "length34_pair_collected": found, "containers": [],
        })
        if origin and origin not in entry["containers"]:
            entry["containers"].append(origin)
        config = path.with_name("run.json")
        if config.is_file():
            entry["native_configuration"] = reference(config)
        if not found:
            return
        pair = canonical_pair(data["witness"])
        assert data["decision"] == "collision"
        own_table = graphs[ordinal]["canonical_table"]
        assert all(endpoint(own_table, mask, pair[0]) == endpoint(own_table, mask, pair[1])
                   for mask in range(128)), f"Source pair fails replay: {path}"
        sources = provenance.setdefault(pair, {})
        sources[source["path"]] = entry

    # Read only controlled rows, which contain newly constructed finder results.
    rows_by_file = []
    for name in args.runs:
        path = REPO / name
        container = reference(path)
        containers.append(container)
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        for row in rows:
            ordinal, key = int(row["ordinal"]), row["key"]
            graph = {"ordinal": ordinal, "key": key, "canonical_table": table_from_key(key),
                     "m": 7, "H": 34}
            if ordinal in graphs:
                assert graphs[ordinal] == graph
            graphs[ordinal] = graph
        rows_by_file.append((container, rows))
    assert len(graphs) == 8
    for container, rows in rows_by_file:
        for row in rows:
            native = row["native_result"]
            consider(REPO / native["path"], native["sha256"], {
                "row_file": container, "run_id": row["run_id"],
                "window_k": row["window_k"], "beam_width": row["beam_width"],
                "tail_threshold": row["tail_threshold"], "length_cap": row["length_cap"],
            })
    for name in args.attempt_roots:
        root = REPO / name
        assert root.is_dir(), root
        for path in sorted(root.glob("case-*/attempt-*/native/result.json")):
            origin = {"attempt_root": root.relative_to(REPO).as_posix()}
            attempt = path.parent.parent / "attempt.json"
            if attempt.is_file():
                origin["attempt_metadata"] = reference(attempt)
            consider(path, origin=origin)

    pair_records = []
    variants = {}
    complement = str.maketrans("01", "10")
    for pair, sources in sorted(provenance.items()):
        identifier = pair_id(pair)
        pair_records.append({"pair_id": identifier, "words": pair, "length": 34,
                             "sources": list(sources.values())})
        transforms = {
            "original": pair,
            "global_complement": tuple(w.translate(complement) for w in pair),
            "reverse": tuple(w[::-1] for w in pair),
            "reverse_global_complement": tuple(w[::-1].translate(complement) for w in pair),
        }
        for transform, raw_words in transforms.items():
            words = canonical_pair(raw_words)
            variant = variants.setdefault(words, {
                "variant_id": pair_id(words), "words": words, "length": 34, "derivations": [],
            })
            variant["derivations"].append({"constructed_pair_id": identifier, "transform": transform})

    replays = []
    for pair, variant in sorted(variants.items()):
        successes = []
        for ordinal, graph in sorted(graphs.items()):
            first = [endpoint(graph["canonical_table"], mask, pair[0]) for mask in range(128)]
            second = [endpoint(graph["canonical_table"], mask, pair[1]) for mask in range(128)]
            equal = [a == b for a, b in zip(first, second)]
            success = all(equal)
            if success:
                successes.append(ordinal)
            replays.append({"variant_id": variant["variant_id"], "ordinal": ordinal,
                            "key": graph["key"], "masks_verified": 128,
                            "first_product_state": first, "second_product_state": second,
                            "merged_count": sum(equal), "total_masks": 128,
                            "universal_collision": success,
                            "first_separating_mask": next((i for i, same in enumerate(equal) if not same), None)})
        variant["successful_graph_ordinals"] = successes

    direct = sorted({entry["ordinal"] for entry in inventory.values() if entry["length34_pair_collected"]})
    original_coverage = sorted({ordinal for variant in variants.values()
                               if any(d["transform"] == "original" for d in variant["derivations"])
                               for ordinal in variant["successful_graph_ordinals"]})
    all_coverage = sorted({ordinal for variant in variants.values() for ordinal in variant["successful_graph_ordinals"]})
    original_cross_class = []
    for record in pair_records:
        source_ordinals = {s["ordinal"] for s in record["sources"]}
        matches = variants[tuple(record["words"])]["successful_graph_ordinals"]
        original_cross_class.extend({"pair_id": record["pair_id"], "ordinal": o}
                                    for o in matches if o not in source_ordinals)
    summary = {
        "schema": 1, "method": "independent-scalar-static-mask-constructed-pair-transfer",
        "source_script": reference(Path(__file__)),
        "original_saved_witness_files_read": False,
        "known_H": 34, "pair_length": 34, "graph_count": 8, "masks_per_graph": 128,
        "constructed_pair_count": len(pair_records), "variant_count": len(variants),
        "native_results_examined": len(inventory),
        "native_length34_results": sum(x["length34_pair_collected"] for x in inventory.values()),
        "replays": len(replays), "mask_coordinate_replays": len(replays) * 128,
        "direct_rediscovery_graph_ordinals": direct,
        "original_pair_coverage_graph_ordinals": original_coverage,
        "all_variant_coverage_graph_ordinals": all_coverage,
        "missing_graph_ordinals": sorted(set(graphs) - set(all_coverage)),
        "new_original_cross_class_transfers": original_cross_class,
        "independent_autofind_coverage_claimed": False,
        "conditional_suffix_bfs_implies_global_shortest": False,
        "scope": "Finite reuse of constructed candidates; successful length34 pairs are optimal only using separately certified H=34.",
    }
    output = REPO / args.output
    output.mkdir(parents=True, exist_ok=True)

    def write_json(name, value):
        (output / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def write_jsonl(name, values):
        (output / name).write_text("".join(json.dumps(value, separators=(",", ":")) + "\n"
                                          for value in values), encoding="utf-8")

    write_json("summary.json", summary)
    write_json("source-inventory.json", {"row_sources": containers, "native_results": list(inventory.values())})
    write_jsonl("graphs.jsonl", [graphs[o] for o in sorted(graphs)])
    write_jsonl("constructed-pairs.jsonl", pair_records)
    write_jsonl("variants.jsonl", [variants[pair] for pair in sorted(variants)])
    write_jsonl("replays.jsonl", replays)
    lines = [
        "# Constructed length-34 pair transfer", "",
        f"{len(pair_records)} distinct pairs from {summary['native_length34_results']} newly constructed native results were replayed on all eight seven-state maximizing rooted classes. Each replay independently simulates all 128 static masks and retains both complete endpoint vectors.", "",
        "| Graph ordinal | Direct new length-34 result in pool | Original-pair reuse succeeds | Any listed variant succeeds |",
        "|---:|:---:|:---:|:---:|",
    ]
    for ordinal in sorted(graphs):
        lines.append(f"| {ordinal} | {'yes' if ordinal in direct else 'no'} | {'yes' if ordinal in original_coverage else 'no'} | {'yes' if ordinal in all_coverage else 'no'} |")
    lines += ["", "Original-pair reuse found no additional graph classes. Global complements have the same success sets, as expected: complementing every input letter is exactly replacing each mask by its bitwise complement. Reverse and reverse-complement words were tested as new candidates; neither transformation produced a successful pair on any of these eight graphs.", "",
              "The uncovered classes are " + ", ".join(map(str, summary["missing_graph_ordinals"])) + ". This is a finite candidate-pool transfer experiment, not an independent automatic search and not evidence that no other length-34 pair exists. Successful length-34 pairs are globally shortest only because H=34 was separately certified for these graphs.", "",
              "Inputs are controlled v1/v2 lookahead results, the k6/W16 target34 results, and completed k8/k16/distance target34 native attempts. The script never opens the original saved-witness/maximizer datasets. Each collected pair records the native JSON SHA-256 and its run/attempt provenance. Graph transition tables are reconstructed from the keys in the controlled rows.", "",
              "Files: `constructed-pairs.jsonl` contains the source pairs and provenance; `variants.jsonl` lists all tested transformations and successful classes; `replays.jsonl` retains every full product-state comparison; `source-inventory.json` pins all examined native outputs and row containers; `summary.json` gives counts and claim boundaries.", "",
              "Reproduce from the repository root:", "", "```powershell", "uv run --no-project python scripts/family1_constructed_pair_transfer.py", "```", ""]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

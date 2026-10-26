#!/usr/bin/env python3
"""Combine an eight-state search without promoting sampled misses to bounds.

Inputs remain separate evidence sources. Every finite upper is replayed over
all 256 static masks. Lower bounds above one require an explicit projection
construction or a completed, independently checked layer report.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from family1_graph_candidate_search import verify_witness
from family1_layer_certificate import validate_manifest
from family1_study import canonical_table, fixed_key, validate_table

REPO = Path(__file__).resolve().parents[1]


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def rows(path):
    data = Path(path).read_bytes()
    require(not data or data.endswith(b"\n"), f"Uncommitted JSONL: {path}")
    return [json.loads(line) for line in data.decode("utf-8-sig").splitlines() if line.strip()]


def reference(path):
    path = Path(path).resolve()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "sha256": digest, "bytes": path.stat().st_size}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_rows(path, values):
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            for value in values:
                stream.write((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode())


def check_projection(row):
    construction = row["construction"]
    require(row["m"] == 8 and row["lower_bound"] == 34, "Unexpected projection baseline")
    base = tuple((int(construction["base_key"][i:i + 2]), int(construction["base_key"][i + 2:i + 4]))
                 for i in range(0, len(construction["base_key"]), 4))
    lower_path = REPO / "results/family1-m7" / ("lower-" + construction["base_key"] + ".json")
    proof = read(lower_path)
    require(proof["status"] == "collision-free" and proof["lower_bound"] == 34
            and proof["depth"] == 33 and proof["m"] == 7 and proof["key"] == construction["base_key"]
            and proof["method"] == "independent-one-hot-DFS-hash-radix-full-state-replay"
            and proof["reason"] == "" and proof["generated_representatives"] == 1 << 32,
            "Missing certified base lower bound")
    provenance_path = REPO / "results/family1-m7/copy-provenance.json"
    provenance = read(provenance_path)
    expected = next(item for item in provenance["copied_files"] if item["path"] == lower_path.name)
    require(reference(lower_path)["sha256"] == expected["sha256"], "Base lower certificate provenance changed")
    table = validate_table(row["canonical_table"])
    projection = construction["canonical_projection_to_base"]
    swaps = construction["canonical_mask_lift_xor"]
    require(len(projection) == len(swaps) == 8 and projection[0] == 0, "Invalid rooted projection")
    for state in range(8):
        for symbol in range(2):
            require(projection[table[state][symbol ^ swaps[state]]] == base[projection[state]][symbol],
                    "Projection does not commute with transitions")
    return {"method": "static-mask-projection", "construction": construction,
            "base_lower_report": reference(lower_path), "base_provenance": reference(provenance_path)}


def publish(args):
    require(not args.out.exists() or not any(args.out.iterdir()), "Publication output must be empty")
    generation = read(args.pool / "generation-r1/summary.json")
    universe = read(args.pool / "rooted-universe.json")
    universe8 = next(row["rooted_classes"] for row in universe["sizes"] if row["m"] == 8)
    require(generation["completed"] and generation["target_m"] == 8, "Incomplete generation")
    inputs, records, observations, requested_lowers = [], {}, [], {}

    def record_for(row):
        require(row["m"] == 8, "Only eight-state records accepted")
        table = validate_table(row["canonical_table"])
        require(len(table) == 8 and fixed_key(table) == row["key"], "Key/table mismatch")
        if row["key"] not in records:
            require(canonical_table(table) == table, "Noncanonical rooted class")
            records[row["key"]] = {"m": 8, "key": row["key"], "canonical_table": table,
                "shape_key": row.get("shape_key"), "lower_bound": 1, "upper_bound": None,
                "witness": None, "lower_certificates": [], "upper_certificates": [],
                "record_sources": [], "evaluation_count": 0}
        result = records[row["key"]]
        require(result["canonical_table"] == table, "Conflicting duplicate class")
        return result

    for path in args.records:
        source = reference(path)
        inputs.append(source)
        for row in rows(path):
            result = record_for(row)
            result["record_sources"].append(source["sha256"])
            lower = row.get("lower_bound", 1)
            requested_lowers[row["key"]] = max(requested_lowers.get(row["key"], 1), lower)
            if lower > 1:
                if "construction" in row:
                    proof = check_projection(row)
                    result["lower_bound"] = max(result["lower_bound"], lower)
                    result["lower_certificates"].append(proof)
                else:
                    # Derived aggregate records may repeat a supplied lower;
                    # they cannot introduce a proof by asserting the number.
                    require(lower <= 34, "New lower bound requires --lower-report")
            upper, words = row.get("upper_bound"), row.get("witness")
            if upper is not None:
                require(isinstance(upper, int) and upper >= 1 and words and len(words[0]) == upper,
                        "Finite upper must have an equal-length witness")
                verification = verify_witness(result["canonical_table"], words)
                certificate = {"source_sha256": source["sha256"], "upper_bound": upper,
                               "witness": words, "verification": verification}
                result["upper_certificates"].append(certificate)
                if result["upper_bound"] is None or upper < result["upper_bound"]:
                    result["upper_bound"], result["witness"] = upper, words

    require(len(args.lower_reports) == len(args.lower_manifests), "Each layer report requires its pinned run manifest")
    for path, manifest in zip(args.lower_reports, args.lower_manifests):
        proof, source = validate_manifest(manifest, path), reference(path)
        require(proof["m"] == 8 and proof["status"] == "collision-free"
                and proof["lower_bound"] == proof["depth"] + 1, "Layer did not certify injectivity")
        require(proof["key"] in records, "Lower proof is outside the exported graph corpus")
        result = records[proof["key"]]
        result["lower_bound"] = max(result["lower_bound"], proof["lower_bound"])
        result["lower_certificates"].append({"method": proof["method"], "report": source,
                                              "run_manifest": reference(manifest)})
        inputs.append(source)

    attempt_sources = []
    for path in args.observations:
        source = reference(path)
        attempt_sources.append(source)
        for attempt in rows(path):
            graph = attempt.get("graph", attempt.get("observation", {}))
            key = graph.get("key", attempt.get("key"))
            require(key in records, "Observation is outside the exported graph corpus")
            records[key]["evaluation_count"] += 1
            observations.append({"source_sha256": source["sha256"], **attempt})

    ordered = [records[key] for key in sorted(records)]
    generated_keys = {row["key"] for row in rows(args.pool / "generation-r1/candidates.jsonl")}
    require(len(generated_keys) == generation["candidate_count"] and generated_keys <= records.keys(),
            "Publication lost generated classes")
    extra_generations = []
    for index, directory in enumerate(args.extra_generations):
        extra_summary = read(directory / "summary.json")
        extra_rows = rows(directory / "candidates.jsonl")
        keys = {row["key"] for row in extra_rows}
        require(extra_summary["completed"] and extra_summary["target_m"] == 8
                and len(keys) == extra_summary["candidate_count"] and keys <= records.keys(),
                "Publication lost classes from an additional neighborhood")
        extra_generations.append({"summary": reference(directory / "summary.json"),
            "radius": extra_summary["radius"], "rooted_classes": len(keys),
            "enumeration_complete": extra_summary["enumeration_complete"],
            "path_capped": extra_summary["path_capped"], "candidate_capped": extra_summary["candidate_capped"],
            "output_stem": f"extra-generation-{index}"})
    for row in ordered:
        lower, upper = row["lower_bound"], row["upper_bound"]
        require(lower >= requested_lowers.get(row["key"], 1), "Input lower bound has no checked proof source")
        require(upper is None or lower <= upper, "Contradictory certified bounds")
        row["status"] = "exact" if upper == lower else "bounded" if upper is not None else "incomplete"
        row["merge_length"] = lower if upper == lower else None
    best = max(row["lower_bound"] for row in ordered)
    best_rows = [row for row in ordered if row["lower_bound"] == best]
    potential = [row for row in ordered if row["upper_bound"] is None or row["upper_bound"] >= best]
    challengers = [row for row in potential if row["upper_bound"] is None or row["upper_bound"] > best]
    summary = {"schema": 1, "m": 8, "accessible_rooted_classes_in_full_universe": universe8,
        "generated_local_rooted_classes": generation["candidate_count"],
        "generated_local_ordinary_shapes": generation["ordinary_shape_count"],
        "direct_rooted_endpoints": generation["root_fixed_candidate_count"],
        "exported_rooted_classes": len(ordered), "native_attempts": len(observations),
        "evaluated_rooted_classes": sum(row["evaluation_count"] > 0 for row in ordered),
        "additional_neighborhoods": extra_generations,
        "complete_local_radius1_enumeration": generation["enumeration_complete"],
        "global_enumeration_complete": False, "global_maximum_certified": False,
        "best_certified_lower_bound": best, "graphs_with_best_certified_lower_bound": len(best_rows),
        "potential_maximizers_retained": len(potential), "unresolved_strict_challengers": len(challengers),
        "upper_histogram": dict(sorted(Counter(row["upper_bound"] for row in ordered
                                               if row["upper_bound"] is not None).items())),
        "no_verified_upper": sum(row["upper_bound"] is None for row in ordered),
        "exact_scores": sum(row["status"] == "exact" for row in ordered),
        "sampling_misses_are_lower_certificates": False,
        "all_classes_and_potential_ties_exported": True}
    args.out.mkdir(parents=True, exist_ok=True)
    for name, data in (("records", ordered), ("best-certified-lower", best_rows),
                       ("potential-maximizers", potential), ("unresolved-challengers", challengers),
                       ("observations", observations)):
        write_rows(args.out / (name + ".jsonl.gz"), data)
    (args.out / "best-certified-lower.jsonl").write_text("".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in best_rows), encoding="utf-8")
    for name in ("candidates", "paths"):
        write_rows(args.out / ("generation-" + name + ".jsonl.gz"), rows(args.pool / "generation-r1" / (name + ".jsonl")))
    for index, directory in enumerate(args.extra_generations):
        for name in ("candidates", "paths"):
            write_rows(args.out / f"extra-generation-{index}-{name}.jsonl.gz", rows(directory / (name + ".jsonl")))
    write_json(args.out / "summary.json", summary)
    write_json(args.out / "inputs.json", {"records": inputs, "observations": attempt_sources,
        "generation": reference(args.pool / "generation-r1/summary.json"),
        "universe_count": reference(args.pool / "rooted-universe.json"), "publisher": reference(Path(__file__)),
        "witness_verifier": reference(REPO / "scripts/family1_graph_candidate_search.py")})
    write_json(args.out / "manifest.json", {path.name: reference(path)
               for path in sorted(args.out.iterdir()) if path.is_file()})
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, default=REPO / "out/family1-m8-search-v1")
    parser.add_argument("--records", type=Path, action="append", required=True)
    parser.add_argument("--observations", type=Path, action="append", default=[])
    parser.add_argument("--lower-report", dest="lower_reports", type=Path, action="append", default=[])
    parser.add_argument("--lower-manifest", dest="lower_manifests", type=Path, action="append", default=[])
    parser.add_argument("--extra-generation", dest="extra_generations", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    publish(parser.parse_args())


if __name__ == "__main__":
    main()

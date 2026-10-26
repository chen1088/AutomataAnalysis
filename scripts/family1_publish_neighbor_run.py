#!/usr/bin/env python3
"""Audit and publish a completed bounded neighborhood run and all raw evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import zipfile


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(path):
    data = path.read_bytes()
    require(not data or data.endswith(b"\n"), f"Uncommitted final JSONL fragment: {path}")
    return [json.loads(line) for line in data.decode("utf-8-sig").splitlines() if line.strip()]


def identity(row):
    return row["m"], row["key"]


def table_check(row):
    m, table = row["m"], row["canonical_table"]
    require(type(m) is int and 1 <= m <= 20 and len(table) == m, "Invalid graph size")
    require(all(len(r) == 2 and all(type(t) is int and 0 <= t < m for t in r) for r in table), "Invalid outgoing port")
    require(row["key"] == "".join(f"{t:02d}" for r in table for t in r), "Transition table/key mismatch")


def query_check(row, run, executable_hash):
    table_check(row)
    recorded = row["native_result"]["path"]
    parts = (PureWindowsPath(recorded) if "\\" in recorded else PurePosixPath(recorded)).parts
    require("queries" in parts, "Native result is outside query layout")
    path = run.joinpath(*parts[parts.index("queries"):]).resolve()
    require(path.is_relative_to(run), "Native query path escapes run")
    checksum = digest(path)
    require(checksum == row["native_result"]["sha256"], "Native result hash mismatch")
    require((path.parent / "result.sha256").read_text().strip() == checksum, "Native result.sha256 mismatch")
    answer = read(path)
    require(answer == row["native_answer"], "Journal native_answer differs from hashed native JSON")
    require(identity(answer) == identity(row) and answer["canonical_table"] == row["canonical_table"], "Native graph mismatch")
    require(row["native_executable_sha256"] == executable_hash, "Native executable provenance mismatch")
    require(answer["config_sha256"] == digest(path.parent / "run.json"), "Native configuration hash mismatch")
    require(answer.get("traversal_complete") is True, "Native query traversal is incomplete")
    for field in ("decision", "lower_bound", "upper_bound", "witness"):
        require(row[field] == answer[field], f"Journal/native {field} mismatch")
    require(answer["lower_bound"] == 1, "Sampling/query result manufactures a lower bound")
    require(answer.get("global_maximum_certified") is not True, "Native query claims a global optimum")
    if answer["decision"] == "collision":
        upper, words = answer["upper_bound"], answer["witness"]
        require(type(upper) is int and upper > 0 and isinstance(words, list) and len(words) == 2 and words[0] != words[1], "Invalid upper witness")
        require(all(isinstance(w, str) and len(w) == upper and not set(w) - {"0", "1"} for w in words), "Witness length/alphabet mismatch")
        require(answer["scalar_witness_masks_verified"] == 1 << row["m"], "Witness lacks complete scalar mask count")
        require(answer.get("witness_length", upper) == upper and upper <= answer.get("requested_length", answer["length"]), "Witness exceeds query cap")
    else:
        require(answer["decision"] == "unknown" and answer["upper_bound"] is None and answer["witness"] is None, "Miss has a false certificate")
        require(answer.get("scalar_witness_masks_verified", 0) == 0, "Miss claims witness verification")
    return path


def publish(run, out):
    run, out = run.resolve(), out.resolve()
    require(run.is_dir() and not out.is_relative_to(run), "Output must be outside the existing run")
    require(not out.exists() or not any(out.iterdir()), "Publication requires a new empty output directory")
    summary, configuration = read(run / "summary.json"), read(run / "run.json")
    require(summary["all_selected_query_traversal_complete"] is True and not summary.get("generation_only"), "Run has pending selected queries")
    require(all(summary.get(f) is not True for f in ("enumeration_complete", "maximum_value_certified", "maximizing_collection_complete")), "Neighborhood run claims global exhaustive coverage")
    files = sorted(path for path in run.rglob("*") if path.is_file())
    require(all(not path.is_symlink() and path.resolve().is_relative_to(run) for path in files), "Raw run contains external symbolic links")
    inventory = {path.relative_to(run).as_posix(): {"sha256": digest(path), "bytes": path.stat().st_size} for path in files}
    executable_hash = configuration["native_executable_sha256"]
    require(any(info["sha256"] == executable_hash for info in inventory.values()), "Saved used executable is missing")
    driver_hash = configuration.get("program_hashes", {}).get("family1_neighbor_search.py")
    require(driver_hash and any(info["sha256"] == driver_hash for info in inventory.values()), "Saved used Python driver is missing")
    journal = rows(run / "query-results.jsonl")
    query_map = {identity(row): row for row in journal}
    require(len(query_map) == len(journal), "Duplicate query identity")
    selected, shapes = set(), set()
    for m in range(summary["min_m"], summary["max_m"] + 1):
        directory = run / "plans" / f"m{m}"
        for name, checksum in read(directory / "integrity.json")["sha256"].items():
            require(digest(directory / name) == checksum, "Plan integrity mismatch")
        for shape in read(directory / "plan.json")["selected_shapes"]:
            require(shape["all_vertices_accounted_for"] is True, "Selected shape omits starting vertices")
            shape_id = m, shape["shape_key"]
            require(shape_id not in shapes, "Duplicate selected shape")
            shapes.add(shape_id)
            for root in shape["roots"]:
                table_check(root)
                selected.add(identity(root))
    require(selected == set(query_map), "Selected root set differs from completed query keys")
    native_paths = {query_check(row, run, executable_hash) for row in journal}
    require(len(native_paths) == len(journal), "Different query rows reuse a native result")
    require(native_paths == {p.resolve() for p in (run / "queries").rglob("result.json")}, "Unreferenced or missing native results")
    profiles = rows(run / "root-profiles.jsonl")
    require({(p["m"], p["shape_key"]) for p in profiles} == shapes and len(profiles) == len(shapes), "Root-profile shape coverage differs")
    for profile in profiles:
        require(profile["all_accessible_roots_queried"] is True, "Root profile is incomplete")
        for root in profile["roots"]:
            require(root["query_complete"] is True and identity(root) in query_map, "Pending root in profiles")
            require(root.get("query_decision", root.get("threshold_decision")) == query_map[identity(root)]["decision"], "Root-profile decision mismatch")
    records = rows(run / "records.jsonl")
    record_map = {identity(row): row for row in records}
    require(len(record_map) == len(records) and selected <= set(record_map), "Record coverage/uniqueness mismatch")
    for row in records:
        table_check(row)
        require(type(row["lower_bound"]) is int and row["lower_bound"] >= 1 and (row["upper_bound"] is None or row["lower_bound"] <= row["upper_bound"]), "Contradictory record bounds")
    incumbent = {identity(r) for r in rows(run / "incumbents.jsonl")}
    possible = {identity(r) for r in rows(run / "potential-competitive.jsonl")}
    leaders = {m: max(r["lower_bound"] for r in records if r["m"] == m) for m in {r["m"] for r in records}}
    require(incumbent == {identity(r) for r in records if r["lower_bound"] == leaders[r["m"]]}, "Incumbent ties were dropped")
    require(possible == {identity(r) for r in records if r["upper_bound"] is None or r["upper_bound"] >= leaders[r["m"]]}, "Potential challengers were dropped")
    require(summary["native_query_results"] == len(journal) and summary["root_profiles"] == len(profiles), "Summary counts mismatch")
    sizes = []
    for item in summary["sizes"]:
        m = item["m"]
        if not summary["min_m"] <= m <= summary["max_m"]: continue
        queries = [r for r in journal if r["m"] == m]; counts = Counter(r["decision"] for r in queries)
        require(item["pending_selected_roots"] == 0 and item["selected_root_classes"] == len(queries) and item["all_selected_roots_queried"], "Per-size selected queries incomplete")
        require(all(item.get(f) is not True for f in ("enumeration_complete", "maximum_value_certified", "maximizing_collection_complete")), "Larger size claims a global certificate")
        sizes.append({"m": m, "selected_roots": len(queries), "selected_shapes": sum(p["m"] == m for p in profiles), "upper_witnesses": counts["collision"], "unknown": counts["unknown"], "best_known_lower_bound": leaders[m], "best_lower_bound_ties": sum(r["m"] == m and r["lower_bound"] == leaders[m] for r in records)})
    audit = {"schema": 1, "passed": True, "run": str(run), "queries": len(journal), "selected_shapes": len(shapes), "records": len(records), "decisions": dict(Counter(r["decision"] for r in journal)), "sizes": sizes, "selected_root_query_sets_equal": True, "native_json_content_and_hashes_verified": True, "all_upper_witness_scalar_counts_verified": True, "fresh_all_mask_scalar_replay_performed": False, "misses_add_no_lower_bound": True, "all_incumbent_ties_and_potential_challengers_preserved": True, "global_coverage_claim": False, "publisher_sha256": digest(Path(__file__).resolve())}
    out.mkdir(parents=True, exist_ok=True)
    compact = ("run.json", "summary.json", "records.jsonl", "incumbents.jsonl", "potential-competitive.jsonl", "root-profiles.jsonl", "query-results.jsonl")
    for name in compact:
        shutil.copyfile(run / name, out / name)
        require(digest(out / name) == inventory[name]["sha256"], "Compact copy hash mismatch")
    archive = out / "complete-evidence.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for path in files: target.write(path, f"{run.name}/{path.relative_to(run).as_posix()}")
    with zipfile.ZipFile(archive) as source:
        require(len(source.infolist()) == len(inventory), "Archive file count mismatch")
        for name, info in inventory.items():
            require(hashlib.sha256(source.read(f"{run.name}/{name}")).hexdigest() == info["sha256"], "Archived evidence hash mismatch")
    (out / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    manifest = {"schema": 1, "raw_run": str(run), "all_raw_files": inventory, "raw_file_count": len(files), "exclusions": [], "archive": {"file": archive.name, "bytes": archive.stat().st_size, "sha256": digest(archive)}, "compact_files": {name: digest(out / name) for name in compact}, "audit_sha256": digest(out / "audit.json")}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    table = "\n".join(f"| {r['m']} | {r['selected_shapes']} | {r['selected_roots']} | {r['upper_witnesses']} | {r['unknown']} | {r['best_known_lower_bound']} |" for r in sizes)
    (out / "README.md").write_text(f"# Audited bounded neighborhood run\n\nAll {len(journal)} selected rooted classes across {len(shapes)} shapes were queried. The audit preserves every record, lower-bound tie, and unresolved potential challenger. This is bounded graph coverage; global maxima and complete maximizing collections remain unresolved at these larger sizes.\n\n| m | Selected shapes | Rooted classes | Upper witnesses | UNKNOWN | Best inherited lower bound |\n|---:|---:|---:|---:|---:|---:|\n{table}\n\nUpper witnesses certify individual graph upper bounds. UNKNOWN adds no lower bound. The inherited bounds remain identified in record provenance. Native witness metadata confirms independent scalar checks over all 2^m masks; this publication audit checked hashes, contents, witness lengths and counts, and did not repeat that scalar computation.\n\n`complete-evidence.zip` contains every raw run file, including its saved used executable and Python driver, with no exclusions. `manifest.json` pins all original and archived file bytes; `audit.json` records coverage and consistency checks. The seven compact exports are unchanged copies.\n\nReproduce publication to a new empty directory:\n\n```powershell\nuv run --no-project python scripts/family1_publish_neighbor_run.py --run {run.relative_to(Path(__file__).resolve().parents[1]).as_posix()} --out results/neighbor-publication-new\n```\n", encoding="utf-8")
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    audit = publish(args.run, args.out)
    print(json.dumps({"out": str(args.out), "queries": audit["queries"], "decisions": audit["decisions"], "passed": audit["passed"]}))


if __name__ == "__main__":
    main()

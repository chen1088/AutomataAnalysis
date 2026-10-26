#!/usr/bin/env python3
"""Audit and publish a completed8..20 edit/rank/upper-witness pilot.

Every raw file is preserved in a deduplicated content-addressed ZIP. Compact
JSONL exports retain all observed classes, paths, rankings and selected misses.
Imported lower certificates remain separately attributed; survival proves none.
"""
import argparse
from collections import Counter
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

from family1_study import canonical_table, fixed_key, validate_table
from family1_graph_candidate_search import graph_metadata, load_attempt, validate_native_configuration

REPO = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def rows(path):
    data = Path(path).read_bytes()
    require(not data or data.endswith(b"\n"), f"Uncommitted JSONL fragment: {path}")
    return [json.loads(line) for line in data.decode("utf-8-sig").splitlines() if line.strip()]


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_rows(path, values):
    if str(path).endswith(".gz"):
        with Path(path).open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            for value in values:
                stream.write((compact(value) + "\n").encode())
    else:
        Path(path).write_text("".join(compact(value) + "\n" for value in values), encoding="utf-8")


def identity(row):
    return row["m"], row["key"]


def checked_graph(row):
    table = validate_table(row["canonical_table"])
    require(len(table) == row["m"] and fixed_key(table) == row["key"], "Graph key/table mismatch")
    return table


def check_ref(reference):
    path = Path(reference["path"])
    require(path.is_file() and digest(path) == reference["sha256"], f"Pinned reference changed: {path}")
    return path


def check_sidecar(directory, stem, extension):
    path = directory / (stem + extension)
    require((directory / (stem + ".sha256")).read_text().strip() == digest(path), f"Bad sidecar: {path}")


@lru_cache(maxsize=None)
def canon(table):
    return canonical_table(table)


@lru_cache(maxsize=None)
def check_step(serialized):
    step = json.loads(serialized)
    before = validate_table(step["before_table"])
    after = validate_table(step["after_table"])
    expected = validate_table(step["raw_after_edit"])
    require(canon(before) == before and canon(after) == after, "Noncanonical path endpoint")
    require(fixed_key(before) == step["before_key"] and fixed_key(after) == step["after_key"], "Path key mismatch")
    operation = step["operation"]
    edges, kind = operation["edges"], operation["kind"]
    selected = {(edge["source"], edge["port"]) for edge in edges}
    require(len(selected) == len(edges), "Repeated edge occurrence")
    for edge in edges:
        require(before[edge["source"]][edge["port"]] == edge["target"], "Primitive input target mismatch")
    raw = list(map(list, before))
    if kind == "retarget":
        require(len(edges) == 1 and edges[0]["target"] != operation["new_target"], "Invalid retarget")
        raw[edges[0]["source"]][edges[0]["port"]] = operation["new_target"]
    elif kind in ("insert-two-edges", "insert-loop"):
        vertex = len(before)
        require(operation["vertex"] == vertex and len(edges) == (2 if kind == "insert-two-edges" else 1), "Invalid routing insertion")
        targets = [edge["target"] for edge in edges]
        require(operation["outgoing"] == (targets if len(edges) == 2 else targets + [vertex]), "Wrong inserted row")
        for edge in edges:
            raw[edge["source"]][edge["port"]] = vertex
        raw.append(operation["outgoing"])
    elif kind in ("smooth-two-edges", "smooth-loop"):
        vertex = operation["vertex"]
        require(0 < vertex < len(before), "Root deletion")
        incoming = {(s, p) for s, row in enumerate(before) if s != vertex for p, target in enumerate(row) if target == vertex}
        outgoing = {p for p, target in enumerate(before[vertex]) if target != vertex}
        require(selected == incoming and set(operation["outgoing_ports"]) == outgoing
                and len(edges) == len(operation["outgoing_ports"]) == (2 if kind == "smooth-two-edges" else 1), "Invalid smoothing bijection")
        require(tuple(operation["outgoing"]) == before[vertex], "Wrong deleted row")
        for edge, port in zip(edges, operation["outgoing_ports"]):
            raw[edge["source"]][edge["port"]] = before[vertex][port]
        retained = [s for s in range(len(before)) if s != vertex]
        labels = {old: new for new, old in enumerate(retained)}
        raw = [[labels[target] for target in raw[source]] for source in retained]
    else:
        raise ValueError("Unknown primitive edit")
    require(tuple(map(tuple, raw)) == expected and canon(expected) == after, "Primitive reconstruction/canonicalization failed")


def check_paths(paths, parent_keys, radius):
    require([path["path_id"] for path in paths] == list(range(len(paths))), "Noncontiguous path IDs")
    for path in paths:
        current = validate_table(path["source_table"])
        require(path["parent_key"] in parent_keys and fixed_key(current) == path["parent_key"], "Path parent absent")
        require(len(path["steps"]) == path["distance_upper_bound"] <= radius and path["root_fixed"] is True, "Invalid rooted path length")
        for step in path["steps"]:
            require(current == tuple(map(tuple, step["before_table"])), "Disconnected path")
            check_step(compact(step))
            current = tuple(map(tuple, step["after_table"]))
        require(current == tuple(map(tuple, path["endpoint_table"])) and fixed_key(current) == path["endpoint_key"], "Path endpoint mismatch")


def merge_record(records, row, source_m, baseline):
    key = identity(row)
    checked_graph(row)
    require(type(row["lower_bound"]) is int and row["lower_bound"] >= 1, "Invalid lower bound")
    if row["lower_bound"] > 1:
        require(key in baseline and row["lower_bound"] == baseline[key]["lower_bound"] == 34, "Unattributed new lower bound")
    old = records.get(key)
    if old is None:
        records[key] = {**row, "publication_source_sizes": [source_m]}
        return
    require(old["canonical_table"] == row["canonical_table"], "Duplicate identity/table conflict")
    old["lower_bound"] = max(old["lower_bound"], row["lower_bound"])
    uppers = [upper for upper in (old["upper_bound"], row["upper_bound"]) if upper is not None]
    old["upper_bound"] = min(uppers) if uppers else None
    require(old["upper_bound"] is None or old["lower_bound"] <= old["upper_bound"], "Contradictory intervals")
    if row.get("witness") and row["upper_bound"] == old["upper_bound"]:
        old["witness"] = row["witness"]
    for field in ("provenance", "observations"):
        for value in row.get(field, []):
            if value not in old.setdefault(field, []):
                old[field].append(value)
    old["publication_source_sizes"].append(source_m)


def publish(run, out):
    run, out = run.resolve(), out.resolve()
    require(run.is_dir() and not out.is_relative_to(run), "Publication must be outside the raw run")
    require(not out.exists() or not any(out.iterdir()), "Use a new empty publication directory")
    configuration, pilot = read(run / "run.json"), read(run / "summary.json")
    require(pilot["all_requested_sizes_finished"] and [row["m"] for row in pilot["sizes"]] == list(range(8, 21)), "Incomplete size coverage")
    require(pilot["global_maximum_certified"] is False and pilot["enumeration_complete"] is False, "Unsupported global claim")
    files = sorted(path for path in run.rglob("*") if path.is_file())
    require(all(not path.is_symlink() and path.resolve().is_relative_to(run) for path in files), "External symbolic link in raw run")
    inventory = {path.relative_to(run).as_posix(): {"sha256": digest(path), "bytes": path.stat().st_size} for path in files}
    objects = {meta["sha256"]: run / name for name, meta in inventory.items()}
    external = {}
    for name, checksum in configuration["pins"].items():
        path = check_ref({"path": name, "sha256": checksum})
        external[name] = {"sha256": checksum, "bytes": path.stat().st_size}
        objects.setdefault(checksum, path)
        if path.suffix not in (".exe", ".jsonl"):
            require(digest(run / "sources-used" / path.name) == checksum, "Saved pilot source pin mismatch")
    baseline_path = Path(configuration["settings"]["baseline_bounds"])
    baseline_rows = rows(baseline_path)
    baseline = {identity(row): row for row in baseline_rows}
    require(len(baseline) == len(baseline_rows) == 104 and all(row["lower_bound"] == 34 and row["upper_bound"] is None for row in baseline_rows), "Baseline tie collection changed")
    records, generated_all, ranked_all, paths_all, features_all, observations, selected_rows, size_rows = {}, [], [], [], [], [], [], []
    generated_keys, outcomes, positive, queried = set(), Counter(), 0, set()
    for m in range(8, 21):
        directory = run / f"m{m}"
        gen, rank, score = (directory / name for name in ("generated", "ranked", "scored"))
        grun, gs, rrun, rs, srun, ss = (read(path) for path in (gen / "run.json", gen / "summary.json", rank / "run.json", rank / "summary.json", score / "run.json", score / "summary.json"))
        for stem, extension in (("run", ".json"), ("summary", ".json"), ("candidates", ".jsonl"), ("paths", ".jsonl")):
            check_sidecar(gen, stem, extension)
        require(gs["completed"] and gs["config_sha256"] == digest(gen / "run.json") and gs["target_m"] == m, "Generation commit/config mismatch")
        require(gs["candidates_sha256"] == digest(gen / "candidates.jsonl") and gs["paths_sha256"] == digest(gen / "paths.jsonl"), "Generation summary/content hash mismatch")
        require(gs["enumeration_complete"] is False and gs["scoring_performed"] is False and gs["global_optimality_claim"] is False, "Generation overclaims coverage/score")
        require(grun["executable_sha256"] == configuration["pins"][configuration["settings"]["edit_exe"]], "Generation executable pin differs")
        parents = rows(directory / "parents.jsonl")
        require(set(grun["parents"]) == {row["key"] for row in parents}, "Generation parent list differs")
        generated, ranked, paths = rows(gen / "candidates.jsonl"), rows(rank / "candidates.jsonl"), rows(gen / "paths.jsonl")
        require(len({identity(row) for row in generated}) == len(generated) == gs["candidate_count"], "Generated duplicate/count mismatch")
        check_paths(paths, set(grun["parents"]), grun["radius"])
        require(len(paths) == gs["materialized_paths"] and len(paths) - len(parents) == gs["accepted_paths"], "Path totals disagree")
        original = {identity(row): row for row in generated}
        require(len(ranked) == len(original) and {identity(row) for row in ranked} == set(original), "Ranking lost an observed class")
        for row in generated:
            checked_graph(row)
            require(row["m"] == m and row["lower_bound"] == 1 and row["upper_bound"] is None and row["shape_roots_complete"], "Generation fabricates a score/omits root closure")
            for path_id in row["path_ids"]:
                require(paths[path_id]["endpoint_key"] == row["key"], "Rerooting mislabeled as direct rooted path")
            for origin in row["root_metadata"]:
                path = paths[origin["path_id"]]
                require(path["endpoint_key"] == origin["endpoint_key"] and 0 <= origin["root_in_endpoint"] < m, "Bad root/path origin")
                require(origin["root_fixed_path"] == (origin["endpoint_key"] == row["key"]), "Root distance scope mismatch")
        for row in ranked:
            require(all(row.get(field) == value for field, value in original[identity(row)].items() if field != "selection_index"), "Ranking changed graph/path provenance")
        for name, checksum in read(rank / "manifest.json")["files"].items():
            require(digest(rank / name) == checksum, "Ranker manifest mismatch")
        for reference in [rrun["candidates"], rrun["paths"], rrun["source_run"], rrun["source_summary"]] + rrun["sources"] + rrun["parent_lower_certificate_sources"]:
            check_ref(reference)
        require(rs["all_rows_retained"] and rs["root_multiset_unchanged"] and rs["candidate_score_upper_or_witness_used"] is False, "Ranker coverage/proof scope differs")
        require(srun["plan_sha256"] == digest(score / "plan.json") and ss["run_sha256"] == digest(score / "run.json"), "Scorer plan/config pin mismatch")
        require(ss["all_selected_roots_scored"] and not ss["global_maximum_certified"] and not ss["enumeration_complete"], "Pending roots or unsupported scoring claim")
        check_ref(srun["native_executable"])
        require(digest(score / "native-used" / Path(srun["native_executable"]["path"]).name) == srun["native_executable"]["sha256"], "Saved scorer executable differs")
        for reference in srun["sources"] + srun["native_dlls"] + srun["candidates"] + srun["bounds"]:
            path = check_ref(reference)
            if reference in srun["sources"]:
                require(digest(score / "sources-used" / path.name) == reference["sha256"], "Saved scorer source differs")
            if reference in srun["native_dlls"]:
                require(digest(score / "native-used" / path.name) == reference["sha256"], "Saved scorer DLL differs")
        plan = read(score / "plan.json")
        all_roots = {identity(root) for shape in plan["shapes"] for root in shape["roots"]}
        selected = {identity(root) for shape in plan["shapes"] if shape["selected"] for root in shape["roots"]}
        require(all_roots == set(original), "Scorer plan lost/generated an unexpected root class")
        require(all(shape["all_vertices_accounted_for"] for shape in plan["shapes"]), "Root accounting incomplete")
        journal = rows(score / "observations.jsonl")
        require({identity(row["graph"]) for row in journal} == selected and len(journal) == len(selected), "Selected query coverage differs")
        attempt_files = list((score / "queries").rglob("attempt.json"))
        require(len(attempt_files) == len(journal), "Unjournaled/duplicate query attempt")
        attempt_map = {identity(read(path)["graph"]): path.parent for path in attempt_files}
        for row in journal:
            graph = graph_metadata(row["graph"])
            checked = load_attempt(attempt_map[identity(graph)], graph, row["stage"], row["length_cap"])
            require(checked == row and row["length_cap"] == 33 and row["observation"]["lower_bound"] == 1, "Journal/hash/config answer differs")
            partial_config = attempt_map[identity(graph)] / "native/run.json"
            if partial_config.exists():
                validate_native_configuration(partial_config, {"config_sha256": digest(partial_config)}, graph, row["stage"], row["length_cap"])
            outcomes[row["outcome"]] += 1
            answer = row["observation"]
            if answer["upper_bound"] is not None:
                positive += 1  # load_attempt independently replays ALL static masks.
            else:
                require(answer["decision"] == "unknown" and answer["witness"] is None, "Miss fabricates a bound")
            observations.append(row)
            selected_rows.append({**row["graph"], "query_outcome": row["outcome"], "observation": answer,
                                  "native_result": row["native_result"], "stage": row["stage"], "seconds": row["seconds"]})
            require(identity(graph) not in queried, "Repeated cross-size selected root")
            queried.add(identity(graph))
        scored_rows = rows(score / "records.jsonl")
        require(len({identity(row) for row in scored_rows}) == len(scored_rows), "Duplicate scoring record")
        require({identity(row) for row in scored_rows} == set(original) | set(baseline), "Scorer lost a generated/baseline class")
        for row in scored_rows:
            merge_record(records, row, m, baseline)
        generated_keys.update(original)
        generated_all.extend(generated); ranked_all.extend(ranked)
        paths_all.extend({"target_m": m, **path} for path in paths)
        features_all.extend({"target_m": m, **feature} for feature in rows(rank / "features.jsonl"))
        size_rows.append({"m": m, "generated_classes": len(generated), "direct_endpoints": gs["root_fixed_candidate_count"],
                          "selected_roots": len(selected), "outcomes": dict(Counter(row["outcome"] for row in journal)),
                          "eliminations": sum(row["observation"]["upper_bound"] is not None and row["observation"]["upper_bound"] < 34 for row in journal),
                          "generation_complete": gs["enumeration_complete"], "representation_capped": gs["representation_capped"],
                          "path_capped": gs["path_capped"], "candidate_capped": gs["candidate_capped"], "depths": gs["depths"]})
        print(compact({"audited_m": m, "generated": len(generated), "selected": len(selected)}), flush=True)
    require(generated_keys <= set(records) and set(baseline) <= set(records), "Merged export loses observations/ties")
    values = [records[key] for key in sorted(records)]
    for row in values:
        row["status"] = "exact" if row["lower_bound"] == row["upper_bound"] else "bounded" if row["upper_bound"] is not None else "incomplete"
        row["merge_length"] = row["lower_bound"] if row["status"] == "exact" else None
    ties = [row for row in values if row["lower_bound"] == 34]
    require({identity(row) for row in ties} == set(baseline), "Imported lower-bound tie collection lost/changed")
    require(all(row["upper_bound"] is None or row["upper_bound"] >= row["lower_bound"] for row in values), "Invalid merged interval")
    # Inputs are now audited; publication mutations begin only here.
    out.mkdir(parents=True, exist_ok=True)
    for name, data in (("records.jsonl.gz", values), ("generated-candidates.jsonl.gz", generated_all),
                       ("ranked-candidates.jsonl.gz", ranked_all), ("paths.jsonl.gz", paths_all),
                       ("ranking-features.jsonl.gz", features_all), ("observations.jsonl", observations),
                       ("selected-roots.jsonl", selected_rows), ("top-lower-bound-ties.jsonl", ties),
                       ("baseline-import.jsonl", baseline_rows)):
        write_rows(out / name, data)
    audit = {"schema": 1, "passed": True, "sizes": size_rows, "generated_classes": len(generated_keys), "merged_classes": len(values),
             "imported_lower34_ties": len(ties), "selected_roots": len(queried), "attempts": len(observations), "outcomes": dict(outcomes),
             "positive_upper_certificates": positive, "eliminations_below34": sum(row["upper_bound"] is not None and row["upper_bound"] < 34 for row in values),
             "unique_primitive_steps_replayed": check_step.cache_info().currsize,
             "all_generated_and_ranked_classes_retained": True, "all_selected_roots_processed_including_timeouts": True,
             "all104_imported_lower_ties_preserved": True, "new_lower_bound_claims": 0, "enumeration_complete": False,
             "global_maximum_certified": False, "survival_gives_no_lower_bound": True,
             "imported_projection_lower_proofs_attributed_not_reproved": True,
             "source_run": str(run), "pilot_run_sha256": digest(run / "run.json"), "pilot_summary_sha256": digest(run / "summary.json"),
             "publisher_sha256": digest(Path(__file__))}
    write_json(out / "audit.json", audit)
    write_json(out / "raw-inventory.json", {"schema": 1, "files": inventory, "file_count": len(inventory), "bytes": sum(meta["bytes"] for meta in inventory.values())})
    write_json(out / "external-pins.json", external)
    archive = out / "evidence.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for checksum, path in sorted(objects.items()):
            require(digest(path) == checksum, "Source changed while publishing")
            target.write(path, "objects/" + checksum)
    with zipfile.ZipFile(archive) as source:
        for checksum in objects:
            with source.open("objects/" + checksum) as stream:
                require(hashlib.file_digest(stream, "sha256").hexdigest() == checksum, "Archive object verification failed")
    require({path.relative_to(run).as_posix() for path in run.rglob("*") if path.is_file()} == set(inventory), "Raw file set changed while publishing")
    for name, meta in inventory.items():
        require(digest(run / name) == meta["sha256"], "Raw bytes changed while publishing")
    table = ["| m | Generated classes | Selected roots | Completed UNKNOWN | Timeout |", "|---:|---:|---:|---:|---:|"]
    table += [f"| {row['m']} | {row['generated_classes']:,} | {row['selected_roots']} | {row['outcomes'].get('completed',0)} | {row['outcomes'].get('timeout',0)} |" for row in size_rows]
    readme = f"""# Bounded edit-candidate pilot, sizes8–20

The run retains {len(generated_keys):,} generated rooted graph classes and all104 imported projection-certified H≥34 classes: {len(values):,} distinct (m,key) records. It processed every root of the two selected ordinary shapes at each size, {len(queried)} queries total. There were {outcomes['completed']} completed native UNKNOWN results and {outcomes['timeout']} timeouts, with {positive} upper witnesses and0 eliminations below34. Survival supplies no lower bound. No global maximum or exhaustive graph coverage is certified.

The search used radius3, at most256 direct rooted target endpoints per size, and4096 accepted path slots. Optional root closure adds every accessible root of observed shapes outside that endpoint budget. All thirteen runs are candidate-capped; the20-state run also records the representation boundary at intermediate size20. Rerooting is separate from root-fixed edit distance. All observed generated/ranked classes and path provenance remain in the gzip JSONL exports. All104 H≥34 baseline ties are preserved in top-lower-bound-ties.jsonl; their supplied projection proof provenance is attributed, not reproved by this publisher.

{chr(10).join(table)}

audit.json records graph/key, primitive path replay, canonicalization, input/source/executable pins, ranking preservation, selected-root coverage, native JSON/config hashes, miss semantics and baseline-tie checks. Every positive witness would be independently replayed on all static masks; this run has none. The fixed2-second timeout was a pilot work budget.

evidence.zip stores each distinct raw byte sequence once at objects/SHA256. raw-inventory.json maps all{len(inventory):,} original relative file paths ({sum(meta['bytes'] for meta in inventory.values()):,} bytes) to those objects. It excludes no raw files. external-pins.json additionally preserves pinned original inputs/executables through the same object store. Restore into a NEW empty directory:

```python
import hashlib, json, pathlib, zipfile
publication = pathlib.Path('results/family1-edit-candidate-pilot-8-20')
destination = pathlib.Path('out/restored-edit-candidate-pilot')
destination.mkdir(exist_ok=False)
with zipfile.ZipFile(publication / 'evidence.zip') as archive:
    for name, meta in json.loads((publication / 'raw-inventory.json').read_text())['files'].items():
        data = archive.read('objects/' + meta['sha256'])
        assert hashlib.sha256(data).hexdigest() == meta['sha256']
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
```

Reproduce the pipeline with `uv run --no-project python scripts/family1_edit_candidate_pilot.py --out NEW_DIRECTORY` using its pinned native executables and inputs. Publish/audit a completed run with `uv run --no-project python scripts/family1_publish_edit_candidate_pilot.py --run out/family1-edit-candidate-pilot-8-20 --out NEW_PUBLICATION_DIRECTORY`. Source snapshots and exact settings remain in the restored run. The raw run's absolute path references describe the original machine; restoring files does not automatically resume under a different path.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    manifest = {"schema": 1, "raw_files": len(inventory), "unique_archive_objects": len(objects),
                "raw_bytes": sum(meta["bytes"] for meta in inventory.values()), "archive_bytes": archive.stat().st_size,
                "files": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in sorted(out.iterdir()) if path.is_file()}}
    write_json(out / "manifest.json", manifest)
    print(compact({"out": str(out), "generated": len(generated_keys), "merged": len(values), "selected": len(queried), "outcomes": dict(outcomes), "archive_bytes": archive.stat().st_size}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    publish(arguments.run, arguments.out)

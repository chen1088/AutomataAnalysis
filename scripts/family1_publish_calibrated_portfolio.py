#!/usr/bin/env python3
"""Publish a completed fresh portfolio, scalar replay and full raw-evidence ZIP."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="out/family1-finder-calibrated-portfolio")
    parser.add_argument("--output", default="results/family1-finder-calibrated-portfolio")
    args = parser.parse_args()
    source, output = (REPO / args.source).resolve(), (REPO / args.output).resolve()
    assert source.is_relative_to(REPO) and source.is_dir()
    summary = read(source / "summary.json")
    assert summary["all_eight_verified"] is True and len(summary["verified_length34_graph_ordinals"]) == 8
    assert summary["total_native_attempts"] == 13
    pairs = [json.loads(line) for line in (source / "verified-pairs.jsonl").read_text().splitlines()]
    assert len(pairs) == 8 and len({p["ordinal"] for p in pairs}) == 8
    audits = []
    for record in pairs:
        key = record["key"]
        flat = [int(key[i:i+2]) for i in range(0, len(key), 2)]
        assert len(flat) == 14 and all(0 <= x < 7 for x in flat)
        first, second = record["words"]
        assert len(first) == len(second) == 34 and first != second and set(first+second) <= {"0", "1"}
        profiles = [[], []]
        for mask in range(128):
            for side, word in enumerate([first, second]):
                state = 0
                for bit in word:
                    port = int(bit) ^ ((mask >> state) & 1)
                    state = flat[2 * state + port]
                profiles[side].append(state)
        assert profiles[0] == profiles[1]
        assert profiles[0] == record["first_product_state"] and profiles[1] == record["second_product_state"]
        native_path = REPO / record["native_result"]["path"]
        assert native_path.resolve().is_relative_to(source)
        assert sha(native_path) == record["native_result"]["sha256"]
        native = read(native_path)
        assert native["key"] == key and native["witness"] == record["words"] and native["upper_bound"] == 34
        audits.append({"ordinal": record["ordinal"], "key": key, "stage": record["stage"],
                       "native_result": record["native_result"], "masks_verified": 128,
                       "word_length": 34, "distinct_words": True,
                       "first_product_state": profiles[0], "second_product_state": profiles[1],
                       "matches_portfolio_and_native": True})
    output.mkdir(parents=True, exist_ok=True)
    for name in ["run.json", "summary.json", "verified-pairs.jsonl", "attempt-inventory.json", "README.md"]:
        shutil.copy2(source / name, output / name)
    readme = (output / "README.md").read_text(encoding="utf-8")
    readme = readme.replace("& C:\\Users\\chenxu\\.local\\bin\\python3.11.exe ", "uv run --no-project python ")
    readme += "\nPublication replay independently checked all eight pairs again (1,024 mask coordinates). `independent-validation.json` retains both complete vectors. `raw-evidence.zip` preserves every file from the fresh run, including exact original driver snapshots, both complete stages, executable copies, native configurations, checkpoints, logs, attempts and witnesses. `manifest.json` records every archive entry and publication-file SHA-256; the manifest itself is excluded from its own hash map. Extract the archive at the repository root to retain the recorded repo-relative paths.\n"
    (output / "README.md").write_text(readme, encoding="utf-8")
    validation = {"schema": 1, "method": "publication-independent-scalar-flat-table-replay",
                  "all_eight_passed": True, "mask_coordinates_replayed": 1024,
                  "shortestness_source": "Separate exhaustive H=34 certificate, not a heuristic minimum proof.",
                  "records": audits}
    (output / "independent-validation.json").write_text(json.dumps(validation, indent=2)+"\n", encoding="utf-8")
    raw_files = sorted(path for path in source.rglob("*") if path.is_file())
    raw_entries = []
    archive = output / "raw-evidence.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in raw_files:
            assert path.resolve().is_relative_to(source)
            name = path.relative_to(REPO).as_posix()
            raw_entries.append({"path": name, "sha256": sha(path), "bytes": path.stat().st_size})
            zipped.write(path, name)
    # Verify every stored member against its independently hashed raw source.
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        assert set(zipped.namelist()) == {entry["path"] for entry in raw_entries}
        for entry in raw_entries:
            assert hashlib.sha256(zipped.read(entry["path"])).hexdigest() == entry["sha256"]
    publication = {path.name: sha(path) for path in output.iterdir() if path.is_file() and path.name != "manifest.json"}
    manifest = {"schema": 1, "source_directory": source.relative_to(REPO).as_posix(),
                "raw_file_count": len(raw_entries), "raw_file_bytes": sum(e["bytes"] for e in raw_entries),
                "archive": {"path": archive.name, "sha256": sha(archive), "bytes": archive.stat().st_size,
                            "all_members_hash_verified": True},
                "raw_entries": raw_entries, "publication_file_sha256": publication,
                "publisher_script": {"path": Path(__file__).resolve().relative_to(REPO).as_posix(), "sha256": sha(__file__)},
                "original_driver_snapshots_preserved_exactly": True,
                "all_eight_scalar_replay_passed": True}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"published": str(output), "all_eight_passed": True,
                      "raw_file_count": len(raw_entries), "archive_bytes": archive.stat().st_size,
                      "archive_sha256": sha(archive)}, indent=2))


if __name__ == "__main__":
    main()

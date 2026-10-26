"""Package a completed seven-state certificate and its independent sources.

This does not rerun the mathematical verification. It checks the completed
certificate's identities, evidence hashes and winner set, then archives the
exact inputs needed to execute that verification again on another Windows PC.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile


EXPECTED = 4166855
METHOD = "independently-checked-complete-upper-cover-and-every-frontier-lower"
LOWER_METHOD = "independent-one-hot-DFS-hash-radix-full-state-replay"
SOURCE_NAMES = {
    "family1_verify_global_certificate.py": "verification/scripts/family1_verify_global_certificate.py",
    "family1_burnside_count.py": "verification/tests/family1_burnside_count.py",
    "Family1ExhaustiveVerify.cpp": "verification/tests/Family1ExhaustiveVerify.cpp",
    "Family1LayerVerify.cpp": "verification/tests/Family1LayerVerify.cpp",
}
SMALL_LIMIT = 64 * 1024 * 1024
CHUNK = 1024 * 1024


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)


def load_jsonl(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        return [json.loads(line, object_pairs_hook=unique_object) for line in stream]


def checksum(value):
    require(isinstance(value, str) and len(value) == 64
            and not (set(value) - set("0123456789abcdef")), "Invalid SHA256")
    return value


def checked_file(path, expected=None):
    path = Path(path).resolve(strict=True)
    require(path.is_file(), f"Not a regular file: {path}")
    actual = digest(path)
    if expected is not None:
        require(actual == checksum(expected), f"Recorded SHA256 does not match: {path}")
    return path, actual


def local_evidence(directory, reference):
    require(isinstance(reference, dict) and isinstance(reference.get("path"), str),
            "Missing certificate evidence reference")
    relative = Path(reference["path"])
    require(not relative.is_absolute() and relative.parts
            and all(part not in (".", "..") for part in relative.parts), "Evidence path must stay inside certificate directory")
    path = (directory / relative).resolve(strict=True)
    require(path.is_relative_to(directory), "Evidence path escapes certificate directory")
    require(path.suffix.lower() in (".json", ".jsonl", ".log") and path.stat().st_size <= SMALL_LIMIT,
            "Referenced evidence must belong to the pinned small-file inventory")
    return checked_file(path, reference["sha256"])[0]


def valid_key(key):
    return (isinstance(key, str) and len(key) == 28 and key.isascii()
            and key.isdigit() and all(0 <= int(key[i:i + 2]) < 7 for i in range(0, 28, 2)))


def key_list(value):
    require(isinstance(value, list) and value and all(valid_key(key) for key in value)
            and len(value) == len(set(value)), "Invalid or repeated frontier keys")
    return value


def table_for(record, upper, winner=False):
    require(type(record.get("m")) is int and record["m"] == 7
            and type(record.get("ordinal")) is int and 0 <= record["ordinal"] < EXPECTED,
            "Invalid graph state count or ordinal")
    table = record.get("canonical_table")
    require(isinstance(table, list) and len(table) == 7, "Invalid graph table")
    for row in table:
        require(isinstance(row, list) and len(row) == 2
                and all(type(v) is int and 0 <= v < 7 for v in row) and row[0] <= row[1],
                "Invalid graph transition row")
    require(record.get("key") == "".join(f"{v:02d}" for row in table for v in row), "Graph table/key mismatch")
    require(type(record.get("upper_bound")) is int and record["upper_bound"] == upper
            and type(record.get("lower_bound")) is int and 1 <= record["lower_bound"] <= upper,
            "Graph bounds do not match frontier")
    if winner:
        require(record.get("status") == "exact" and type(record.get("merge_length")) is int
                and record["merge_length"] == record["lower_bound"] == upper,
                "Winner is not an exact frontier record")
    return table


def scalar_witness(table, witness, length):
    require(type(length) is int and length > 0 and isinstance(witness, list) and len(witness) == 2
            and all(isinstance(word, str) and len(word) == length and not (set(word) - {"0", "1"}) for word in witness)
            and witness[0] != witness[1], "Invalid equal-length distinct witness")
    for mask in range(128):
        endpoints = []
        for word in witness:
            state = 0
            for letter in word:
                state = table[state][int(letter) ^ ((mask >> state) & 1)]
            endpoints.append(state)
        require(endpoints[0] == endpoints[1], f"Witness fails original static mask {mask}")


def validate_audit(audit):
    require(audit.get("verification_passed") is True and audit.get("enumeration_complete") is True
            and audit.get("m") == 7 and audit.get("records_verified") == EXPECTED
            and audit.get("upper_witnesses_verified") == EXPECTED
            and audit.get("records_without_verified_upper") == 0
            and audit.get("burnside_expected_classes") == EXPECTED
            and audit.get("root_fixed_permutations_checked_per_graph") == 720
            and audit.get("original_static_masks_checked_per_upper_witness") == 128,
            "Native audit does not establish the full seven-state upper cover")
    upper = audit.get("global_upper_bound_verified")
    require(type(upper) is int and 1 <= upper <= 34, "Unsupported verified upper bound")
    keys = key_list(audit.get("keys_at_largest_verified_upper_bound"))
    distribution = audit.get("upper_bound_distribution")
    require(isinstance(distribution, dict) and all(isinstance(k, str) and k.isascii() and k.isdigit()
            and 1 <= int(k) <= upper and type(v) is int and v > 0 for k, v in distribution.items())
            and sum(distribution.values()) == EXPECTED and distribution.get(str(upper)) == len(keys),
            "Invalid native upper distribution")
    return upper, keys


def validate_certificate(directory):
    summary = load_json(directory / "summary.json")
    require(summary.get("maximum_value_certified") is True and summary.get("maximizing_collection_complete") is True
            and summary.get("enumeration_complete") is True and summary.get("m") == 7
            and summary.get("method") == METHOD and summary.get("evaluated") == EXPECTED,
            "A completed full seven-state certificate is required")
    upper = summary.get("maximum_merge_length")
    require(type(upper) is int and 1 <= upper <= 34, "Unsupported certificate maximum")
    keys = key_list(summary.get("maximizer_keys"))
    require(type(summary.get("maximizer_count")) is int and summary["maximizer_count"] == len(keys)
            and summary.get("all_other_graphs_have_verified_upper_at_most") == upper - 1,
            "Certificate winner count or strict exclusion bound is invalid")
    model = summary.get("graph_model", {})
    require(model.get("root") == 0 and model.get("reachable_states") == 7
            and model.get("outgoing_ports_per_state") == 2 and model.get("loops_allowed") is True
            and model.get("coincident_ports_allowed") is True and model.get("indegree_restriction", "missing") is None
            and model.get("strong_connectivity_required") is False and model.get("each_seed_scored_separately") is True
            and model.get("equivalence") == "root-preserving vertex relabeling and independent port swaps",
            "Certificate graph model does not match the requested class")
    journal_ref = summary.get("journal", {})
    journal, journal_hash = checked_file(journal_ref["path"], journal_ref["sha256"])
    audit = load_json(local_evidence(directory, summary["upper_audit"]))
    actual_upper, actual_keys = validate_audit(audit)
    require(actual_upper == upper and set(actual_keys) == set(keys), "Final native frontier differs from certified winners")
    initial_audit = load_json(local_evidence(directory, summary["initial_upper_audit"]))
    initial_upper, initial_keys = validate_audit(initial_audit)
    require(initial_upper == upper and summary.get("initial_frontier_count") == len(initial_keys), "Initial frontier mismatch")
    count = load_json(local_evidence(directory, summary["independent_count"]))
    require(count.get("method") == "independent-root-fixed-Burnside-reachable-set-recurrence"
            and count.get("brute_fixed_set_check_through_m") == 4
            and [(r["m"], r["rooted_classes"]) for r in count["sizes"]]
            == list(enumerate([1, 6, 57, 678, 10398, 192181, EXPECTED], start=1)),
            "Independent count report is incomplete or inconsistent")
    winners = load_jsonl(directory / "maximizers.jsonl")
    require(len(winners) == len(keys) and {r.get("key") for r in winners} == set(keys), "Winner export differs from certificate")
    for record in winners:
        scalar_witness(table_for(record, upper, winner=True), record.get("witness"), upper)
    initial_records = load_jsonl(directory / "initial-frontier-records.jsonl")
    require(len(initial_records) == len(initial_keys) and {r.get("key") for r in initial_records} == set(initial_keys),
            "Initial frontier export differs from its native audit")
    records = {record["key"]: record for record in initial_records}
    for record in initial_records:
        scalar_witness(table_for(record, upper), record.get("witness"), upper)
    require(all(record["ordinal"] == records[record["key"]]["ordinal"] for record in winners),
            "Winner ordinal differs from initial frontier identity")
    outcomes = summary.get("initial_frontier_checks")
    proofs = summary.get("independent_lower_checks")
    require(isinstance(outcomes, list) and len(outcomes) == len(initial_keys)
            and {r.get("key") for r in outcomes} == set(initial_keys), "Missing or repeated fresh frontier checks")
    require(isinstance(proofs, list) and len(proofs) == len(keys) and {r.get("key") for r in proofs} == set(keys),
            "Every winner needs its matching fresh lower proof")
    free, collisions = {}, 0
    for outcome in outcomes:
        key = outcome["key"]
        if upper == 1 and outcome.get("trivial_positive_length_bound") is True:
            require(outcome.get("outcome") == "collision-free" and outcome.get("lower_bound") == 1,
                    "Invalid trivial positive-length lower proof")
            free[key] = outcome
            continue
        report = load_json(local_evidence(directory, outcome))
        require(report.get("method") == LOWER_METHOD and report.get("m") == 7 and report.get("key") == key
                and report.get("depth") == upper - 1 and report.get("reason") == "",
                "Lower proof identity or completion mismatch")
        if outcome.get("outcome") == "collision-free":
            require(report.get("status") == "collision-free" and report.get("lower_bound") == upper
                    and outcome.get("lower_bound") == upper and report.get("upper_bound") is None
                    and report.get("witness") is None and type(report.get("generated_representatives")) is int
                    and report["generated_representatives"] == 1 << (upper - 2), "Incomplete winner lower proof")
            free[key] = outcome
        else:
            require(outcome.get("outcome") == "collision-found" and report.get("status") == "collision-found"
                    and outcome.get("upper_bound") == report.get("upper_bound") == upper - 1
                    and outcome.get("witness") == report.get("witness")
                    and outcome.get("cpu_scalar_masks_verified") == 128, "Invalid frontier refinement proof")
            require(records[key]["lower_bound"] <= upper - 1, "Refinement contradicts an inherited lower bound")
            scalar_witness(records[key]["canonical_table"], report.get("witness"), upper - 1)
            collisions += 1
    require(set(free) == set(keys) and all(free[r["key"]] == r for r in proofs)
            and summary.get("frontier_upper_refinements") == collisions, "Fresh lower proof set differs from all winners")
    require(not collisions or summary.get("refine_frontier") is True, "Refinement proofs require refinement mode")
    sources = summary.get("verification_sources")
    require(isinstance(sources, list) and len(sources) == len(SOURCE_NAMES), "Missing independent verification sources")
    source_files = {}
    for reference in sources:
        path, actual = checked_file(reference["path"], reference["sha256"])
        require(path.name in SOURCE_NAMES and path.name not in source_files, "Unexpected or duplicate verification source")
        source_files[path.name] = (path, actual)
    require(set(source_files) == set(SOURCE_NAMES), "Independent source snapshot is incomplete")
    return summary, journal, journal_hash, source_files


def evidence_files(directory, journal):
    result = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".json", ".jsonl", ".log"):
            continue
        require(not path.is_symlink(), f"Symbolic certificate evidence is unsupported: {path}")
        if path.resolve() == journal:
            continue  # The one full journal is archived as data/checkpoint.jsonl.
        require(path.stat().st_size <= SMALL_LIMIT, f"Unexpected large evidence file (would duplicate a journal): {path}")
        result.append(path.resolve())
    return result


def archive_readme(summary):
    return f"""# Portable seven-state Family 1 certificate

The saved certificate reports maximum {summary['maximum_merge_length']} with
{summary['maximizer_count']} distinct ROOTED maximizing classes, covering all
{EXPECTED:,} accessible seven-state classes. Loops, coincident outgoing ports
and arbitrary indegrees are allowed. Each graph uses all 128 static XOR masks.

Layout:
- data/checkpoint.jsonl: exact certified full journal, stored once.
- certificate/: unchanged small certificate JSON, JSONL and execution logs.
- verification/scripts/ and verification/tests/: exact hash-pinned independent
  verification sources; no producer/search code, GPU dependency or executable.
- archive-manifest.json: archived SHA256 values, sizes and original file paths.

Original absolute paths in certificate reports are provenance, not extraction
locations. Use the explicit archive paths below. Saved JSON reports describe
executions; replay actually repeats all coverage, witness and lower checks.
The packer validates saved identities/hashes but does not rerun those checks.

Extract into a new directory. Open an x64 Visual Studio Developer PowerShell
(MSVC C++ standard library/Windows SDK), then run FROM THE EXTRACTED ROOT:

```powershell
New-Item -ItemType Directory -Path verification\\bin | Out-Null
cl.exe /nologo /O2 /EHsc /std:c++latest /Feverification\\bin\\Family1ExhaustiveVerify.exe /Foverification\\bin\\Family1ExhaustiveVerify.obj verification\\tests\\Family1ExhaustiveVerify.cpp
if ($LASTEXITCODE -ne 0) {{ throw 'Upper verifier build failed' }}
cl.exe /nologo /O2 /EHsc /std:c++latest /Feverification\\bin\\Family1LayerVerify.exe /Foverification\\bin\\Family1LayerVerify.obj verification\\tests\\Family1LayerVerify.cpp
if ($LASTEXITCODE -ne 0) {{ throw 'Lower verifier build failed' }}
uv run --no-project --python 3.11 python verification\\scripts\\family1_verify_global_certificate.py --journal data\\checkpoint.jsonl --out replay-certificate --upper-exe verification\\bin\\Family1ExhaustiveVerify.exe --layer-exe verification\\bin\\Family1LayerVerify.exe --jobs 1 --max-total-working-mib 40000 --lower-threads 8 --lower-timeout-ms 1200000 --refine-frontier
if ($LASTEXITCODE -ne 0) {{ throw 'Certificate replay did not complete' }}
```

Alternatively use an installed Python 3.11+ in place of `uv run ... python`.
The standalone C++ verifiers need no vcpkg or external libraries. At depth 33,
the lower checker shares one 32 GiB hash array between its eight threads;
allow at least 40,000 MiB available memory and additional operating-system RAM.
Use a new replay output directory; existing results are never overwritten.
Successful replay must again set BOTH maximum_value_certified and
maximizing_collection_complete to true, and reproduce the winner keys.
Rebuilt executable hashes may differ from the original MSVC build and will be
recorded as new provenance. No original absolute path or GPU is needed.
"""


def write_entry(archive, source, name, expected):
    actual = hashlib.sha256()
    with source.open("rb") as stream, archive.open(name, "w", force_zip64=True) as destination:
        for block in iter(lambda: stream.read(CHUNK), b""):
            destination.write(block)
            actual.update(block)
    require(actual.hexdigest() == expected, f"File changed while being archived: {source}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Completed independent certificate directory")
    parser.add_argument("--out", type=Path, required=True, help="New ZIP path (must not exist)")
    args = parser.parse_args()
    directory = args.input.resolve(strict=True)
    require(directory.is_dir(), "Certificate input must be a directory")
    destination = args.out.absolute()
    partial = destination.with_name(destination.name + ".partial")
    require(destination.suffix.lower() == ".zip", "Output must be a new .zip file")
    require(not destination.exists() and not destination.is_symlink()
            and not partial.exists() and not partial.is_symlink(), "Output or staging path already exists; nothing was overwritten")
    # Pin every file BEFORE interpreting it, including summary/source paths.
    # Validation itself reads no files beyond this complete pinned inventory.
    summary_path, summary_hash = checked_file(directory / "summary.json")
    provisional = load_json(summary_path)
    require(provisional.get("maximum_value_certified") is True
            and provisional.get("maximizing_collection_complete") is True,
            "A completed full certificate is required; no output was created")
    journal, journal_hash = checked_file(provisional["journal"]["path"], provisional["journal"]["sha256"])
    small = evidence_files(directory, journal)
    pins = {path: digest(path) for path in small}
    require(pins.get(summary_path) == summary_hash, "Summary changed while initializing pins")
    pins[journal] = journal_hash
    for reference in provisional["verification_sources"]:
        path, actual = checked_file(reference["path"], reference["sha256"])
        pins[path] = actual
    sizes = {path: path.stat().st_size for path in pins}
    # Validate BEFORE creating any output, including for an unfinished run.
    summary, validated_journal, validated_hash, sources = validate_certificate(directory)
    require(validated_journal == journal and validated_hash == journal_hash, "Certified journal identity changed")
    require(evidence_files(directory, journal) == small, "Certificate inventory changed during validation")
    for path, expected in pins.items():
        require(path.stat().st_size == sizes[path] and digest(path) == expected, f"Pinned input changed during validation: {path}")
    entries = [(journal, "data/checkpoint.jsonl", journal_hash)]
    entries += [(path, "certificate/" + path.relative_to(directory).as_posix(), pins[path]) for path in small]
    entries += [(path, SOURCE_NAMES[name], actual) for name, (path, actual) in sorted(sources.items())]
    require(len({name for _, name, _ in entries}) == len(entries), "Repeated archive path")
    require({path: actual for path, _, actual in entries} == pins, "Validated archive sources differ from initial pins")
    manifest = {"schema": 1, "method": "source-only-hash-pinned-completed-family1-certificate-package-v1",
                "maximum_merge_length": summary["maximum_merge_length"], "maximizer_count": summary["maximizer_count"],
                "maximizer_keys": summary["maximizer_keys"], "mathematical_checks_rerun_by_packer": False,
                "source_only": True, "zip_compression_level": 1,
                "certified_journal": {"archive_path": "data/checkpoint.jsonl", "sha256": journal_hash},
                "files": [{"archive_path": name, "original_path": str(path), "sha256": actual, "bytes": sizes[path]}
                          for path, name, actual in entries]}
    destination.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with partial.open("xb") as output:
            created = True
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
                for path, name, actual in entries:
                    write_entry(archive, path, name, actual)
                archive.writestr("README.md", archive_readme(summary))
                archive.writestr("archive-manifest.json", json.dumps(manifest, indent=2) + "\n")
            output.flush()
            os.fsync(output.fileno())
        require(evidence_files(directory, journal) == small, "Certificate evidence inventory changed during packaging")
        for path, expected in pins.items():
            require(path.stat().st_size == sizes[path] and digest(path) == expected, f"Pinned input changed during packaging: {path}")
        # Hard-link publication is atomic and fails if ANY destination exists.
        # Unlike replace/rename on some platforms, it cannot overwrite a file.
        os.link(partial, destination)
        partial.unlink()
        created = False
        print(json.dumps({"archive": str(destination), "bytes": destination.stat().st_size,
                          "sha256": digest(destination), "source_only": True,
                          "journal_sha256": journal_hash, "archived_input_files": len(entries)}, indent=2))
    finally:
        if created and partial.exists():
            partial.unlink()  # Only the staging file created by THIS invocation.


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Certificate packaging failed: {error}", file=sys.stderr)
        sys.exit(1)

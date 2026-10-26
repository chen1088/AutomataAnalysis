"""Atomically merge independently checked upper witnesses into a complete journal.

Every proposed pair is simulated on every original static mask. Existing lower
bounds are inherited unchanged; this utility does not certify a global maximum
or a complete maximizing collection. Run the independent certificate verifier
on the resulting journal for those conclusions.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time


SEVEN_STATE_CLASSES = 4_166_855
BASE_FIELDS = {"m", "ordinal", "key", "canonical_table", "status", "lower_bound",
               "upper_bound", "merge_length", "witness", "reason"}
PROPOSAL_FIELDS = {"m", "ordinal", "key", "upper_bound", "witness"}
STATUSES = {"exact", "bounded", "depth-capped", "incomplete"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, f"{name} must be an integer >= {minimum}")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def parse_line(raw, number, source):
    text = raw.decode("utf-8-sig" if number == 1 else "utf-8")
    require(text.strip(), f"Blank JSONL record in {source} at line {number}")
    value = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    require(isinstance(value, dict), f"Expected a JSON object in {source} at line {number}")
    return value


def file_sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def same_path(first, second):
    first, second = Path(first), Path(second)
    if first.exists() and second.exists() and os.path.samefile(first, second):
        return True
    return os.path.normcase(str(first.resolve())) == os.path.normcase(str(second.resolve()))


def table_and_key(record):
    m = integer(record["m"], "m", 1)
    require(m <= 7, "This all-mask applicator supports uniform journals with m=1..7")
    table = record["canonical_table"]
    require(isinstance(table, list) and len(table) == m, "Transition table has the wrong number of rows")
    for row in table:
        require(isinstance(row, list) and len(row) == 2, "Each transition row needs two ports")
        require(all(type(target) is int and 0 <= target < m for target in row), "Transition target out of range")
        require(row[0] <= row[1], "Canonical table has unsorted outgoing ports")
    key = "".join(f"{target:02d}" for row in table for target in row)
    require(isinstance(record["key"], str) and record["key"] == key, "Transition table/key mismatch")
    reached, pending = {0}, [0]
    while pending:
        for target in table[pending.pop()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    require(len(reached) == m, "Transition table has vertices unreachable from root 0")
    return m, table, key


def words(value, upper):
    integer(upper, "upper_bound", 1)
    require(isinstance(value, list) and len(value) == 2, "Witness must contain two words")
    require(all(isinstance(word, str) and len(word) == upper and not (set(word) - {"0", "1"})
                for word in value), "Witness words must be binary and have the stated equal positive length")
    require(value[0] != value[1], "Witness words must be distinct")
    return value


def verify_witness(table, witness):
    # Bits belong to vertices, are shared by BOTH paths, and stay fixed on
    # every revisit. Coincident ports and loops require no special treatment.
    inputs = [[ord(letter) - ord("0") for letter in word] for word in witness]
    for mask in range(1 << len(table)):
        endpoints = []
        for word in inputs:
            state = 0
            for letter in word:
                state = table[state][letter ^ ((mask >> state) & 1)]
            endpoints.append(state)
        require(endpoints[0] == endpoints[1], f"Proposed witness is separated by static mask {mask}")


def validate_base(record, ordinal, previous_key, states):
    require(BASE_FIELDS <= record.keys(), "Base record is missing required journal fields")
    m, table, key = table_and_key(record)
    require(states is None or states == m, "Base journal mixes state sizes")
    require(integer(record["ordinal"], "ordinal") == ordinal, "Base ordinals must be consecutive from zero")
    require(previous_key is None or previous_key < key, "Base keys must be distinct and strictly increasing")
    lower = integer(record["lower_bound"], "lower_bound", 1)
    upper = record["upper_bound"]
    if upper is None:
        require(record["witness"] is None, "Base witness has no upper bound")
    else:
        integer(upper, "upper_bound", 1)
        require(lower <= upper, "Base lower bound exceeds its upper bound")
        words(record["witness"], upper)
    require(isinstance(record["status"], str) and record["status"] in STATUSES
            and isinstance(record["reason"], str), "Invalid base status or reason")
    if record["status"] == "exact":
        require(type(record["merge_length"]) is int and record["merge_length"] == lower == upper,
                "Base exact score has inconsistent merge/lower/upper bounds")
    else:
        require(record["merge_length"] is None, "Nonexact base record has a merge length")
        if record["status"] == "bounded":
            require(upper is not None, "Bounded base record has no upper witness")
    return m, table, key


@dataclass
class Proposal:
    states: int
    ordinal: int
    key: str
    upper: int
    witness: list[str]
    table: list[list[int]] | None


def load_proposals(path, copy_path, expected_count):
    by_ordinal, keys = {}, set()
    with Path(path).open("rb") as source, Path(copy_path).open("wb") as copied:
        for line_number, raw in enumerate(source, 1):
            record = parse_line(raw, line_number, path)
            require(PROPOSAL_FIELDS <= record.keys(), "Proposed record is missing required fields")
            m = integer(record["m"], "proposal m", 1)
            require(m <= 7, "Proposal state count must be in 1..7")
            ordinal = integer(record["ordinal"], "proposal ordinal")
            require(ordinal < expected_count, "Proposal ordinal is outside the expected base range")
            key = record["key"]
            require(isinstance(key, str) and len(key) == 4 * m and key.isascii() and key.isdigit(),
                    "Invalid proposed graph key")
            targets = [int(key[i:i + 2]) for i in range(0, len(key), 2)]
            require(all(target < m for target in targets), "Proposed key has an out-of-range target")
            require(key not in keys, "Duplicate proposed graph key")
            require(ordinal not in by_ordinal, "Duplicate proposed ordinal")
            witness = words(record["witness"], record["upper_bound"])
            table = record.get("canonical_table")
            if table is not None:
                table_and_key(dict(record, canonical_table=table))
            by_ordinal[ordinal] = Proposal(m, ordinal, key, record["upper_bound"], witness, table)
            keys.add(key)
            copied.write(raw)
        copied.flush()
        os.fsync(copied.fileno())
    return by_ordinal


def assert_sources_unchanged(sources):
    for path, expected in sources.items():
        require(file_sha256(path) == expected, f"Source SHA256 changed during application: {path}")


def write_json(path, value):
    with Path(path).open("wb") as stream:
        stream.write((json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())


def apply_upper_witnesses(journal, witnesses, out, expected_count=SEVEN_STATE_CLASSES):
    started = time.monotonic()
    integer(expected_count, "expected_count", 1)
    journal, witnesses = Path(journal).resolve(), Path(witnesses).resolve()
    requested_out = Path(out)
    require(not requested_out.is_symlink() and not (hasattr(requested_out, "is_junction") and requested_out.is_junction()),
            "Output directory must not be a link or junction")
    out = requested_out.resolve()
    require(journal.is_file() and witnesses.is_file(), "Journal and witness inputs must be existing files")
    require(not same_path(journal, witnesses), "Journal and witness input paths must differ")
    require(not same_path(out, journal) and not same_path(out, witnesses), "Output path must differ from input paths")
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())), "Output directory must be new or empty")
    out.parent.mkdir(parents=True, exist_ok=True)
    source_hashes = {journal: file_sha256(journal), witnesses: file_sha256(witnesses)}
    stage = Path(tempfile.mkdtemp(prefix=f".{out.name}.tmp-", dir=out.parent)).resolve()
    published = False
    try:
        proposals = load_proposals(witnesses, stage / "sparse-upper-witnesses.jsonl", expected_count)
        require(file_sha256(stage / "sparse-upper-witnesses.jsonl") == source_hashes[witnesses],
                "Witness source changed while being copied")
        matched, count, updated, improved, equal, ignored = 0, 0, 0, 0, 0, 0
        states, previous_key = None, None
        output_hash = hashlib.sha256()
        with journal.open("rb") as source, (stage / "checkpoint.jsonl").open("wb") as target:
            for line_number, raw in enumerate(source, 1):
                require(count < expected_count, "Base contains more records than expected")
                record = parse_line(raw, line_number, journal)
                states, table, key = validate_base(record, count, previous_key, states)
                proposal = proposals.get(count)
                data = raw
                if proposal is not None:
                    require(proposal.states == states and proposal.key == key,
                            "Proposed m/ordinal/key does not match the full base record")
                    require(proposal.table is None or proposal.table == table, "Proposed transition table does not match base")
                    require(proposal.upper >= record["lower_bound"], "Proposed upper bound contradicts the base lower bound")
                    verify_witness(table, proposal.witness)
                    matched += 1
                    old_upper = record["upper_bound"]
                    if old_upper is not None and proposal.upper > old_upper:
                        ignored += 1  # Verified evidence is retained, but the stronger base score stays byte-for-byte.
                    else:
                        updated += 1
                        if old_upper == proposal.upper:
                            equal += 1
                        else:
                            improved += 1
                        exact = record["lower_bound"] == proposal.upper
                        record.update(upper_bound=proposal.upper, witness=proposal.witness,
                                      status="exact" if exact else "bounded",
                                      merge_length=proposal.upper if exact else None,
                                      reason="independently-verified-positive-upper-witness")
                        data = (json.dumps(record, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
                target.write(data)
                output_hash.update(data)
                count += 1
                previous_key = key
            target.flush()
            os.fsync(target.fileno())
        require(count == expected_count, f"Base record count {count} differs from expected {expected_count}")
        require(matched == len(proposals), "At least one proposed graph is missing from the base journal")
        assert_sources_unchanged(source_hashes)
        checkpoint_hash = output_hash.hexdigest()
        summary = {"schema": 1, "method": "independently-scalar-verified-upper-witness-merge-v1",
                   "m": states, "records_processed": count, "expected_count": expected_count,
                   "record_count_matches_expected": True,
                   "full_seven_state_journal_count": states == 7 and count == SEVEN_STATE_CLASSES,
                   "proposals_verified": matched, "records_updated": updated,
                   "upper_bounds_improved": improved, "equal_upper_witnesses_replaced": equal,
                   "weaker_verified_proposals_ignored": ignored,
                   "records_preserved_byte_for_byte": count - updated,
                   "original_static_masks_checked_per_proposal": 1 << states,
                   "source_lower_bounds_preserved": True, "lower_proofs_independently_checked": False,
                   "base_upper_witnesses_rechecked": False,
                   "enumeration_complete": False, "maximum_value_certified": False,
                   "maximum_merge_length": None, "maximizing_collection_complete": False,
                   "coverage_note": "Record counts and identities were checked. Rooted isomorphism-class coverage and global maximum/ties require the independent certificate verifier.",
                   "checkpoint_sha256": checkpoint_hash, "seconds": time.monotonic() - started}
        provenance = {"schema": 1, "method": summary["method"],
                      "sources": {"journal": {"path": str(journal), "sha256": source_hashes[journal]},
                                  "witnesses": {"path": str(witnesses), "sha256": source_hashes[witnesses]}},
                      "output": {"checkpoint": "checkpoint.jsonl", "sha256": checkpoint_hash,
                                 "copied_witnesses": "sparse-upper-witnesses.jsonl"},
                      "proposal_fields_validated": ["m", "ordinal", "key", "upper_bound", "witness"],
                      "proposal_lower_bounds_and_exact_claims_ignored": True,
                      "verification": "Distinct equal-length binary words, simulated separately for every original static mask with one fixed bit per vertex shared by both trajectories.",
                      "global_maximum_certified": False, "maximizing_collection_complete": False}
        write_json(stage / "summary.json", summary)
        write_json(stage / "provenance.json", provenance)
        assert_sources_unchanged(source_hashes)
        require(not out.exists() or (out.is_dir() and not any(out.iterdir())), "Output directory changed or is no longer empty")
        removed_empty_out = out.exists()
        if removed_empty_out:
            out.rmdir()  # Empty directory only; no recursive deletion of a user destination.
        try:
            os.replace(stage, out)  # Same-parent staging gives an atomic publication of all completed files.
        except OSError:
            if removed_empty_out and not out.exists():
                out.mkdir()  # Restore the caller's empty directory if publication itself fails.
            raise
        published = True
        return summary
    finally:
        if not published and stage.exists():
            require(stage.resolve() == stage and stage.parent == out.parent
                    and stage.name.startswith(f".{out.name}.tmp-"), "Unsafe staging cleanup path")
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--witnesses", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=SEVEN_STATE_CLASSES,
                        help="Expected records (default: complete m7 class count); overrides never imply complete coverage")
    args = parser.parse_args()
    try:
        result = apply_upper_witnesses(args.journal, args.witnesses, args.out, args.expected_count)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Upper-witness application failed: {error}\n")
    print(f"Applied {result['proposals_verified']} verified proposals to {result['records_processed']} records; "
          f"improved {result['upper_bounds_improved']} upper bounds. Global maximum and ties remain uncertified.")


if __name__ == "__main__":
    main()

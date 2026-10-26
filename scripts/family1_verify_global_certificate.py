"""Independently verify a seven-state global maximum AND every tied class.

Checks the entire journal with the independent native verifier, then actually
reruns the independent complete-mask lower checker for EVERY graph at the
largest verified upper bound. No producer maximum/tie claims are trusted.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
METHOD = "independent-one-hot-DFS-hash-radix-full-state-replay"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(command, log):
    with log.open("w", encoding="utf-8") as output:
        result = subprocess.run(list(map(str, command)), stdout=output, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"Verifier failed; see {log}")


def check_pins(journal, original_hash, verifier_hashes, source_hashes=None):
    require(digest(journal) == original_hash, "Journal changed during verification")
    require(all(digest(path) == checksum for path, checksum in verifier_hashes.items()),
            "Verifier executable changed during verification")
    require(all(digest(path) == checksum for path, checksum in (source_hashes or {}).items()),
            "Verification source changed during verification")


def validate_upper_audit(audit, expected):
    require(audit["verification_passed"] is True and audit["enumeration_complete"] is True,
            "Upper audit did not independently establish complete coverage")
    require(audit["records_verified"] == audit["upper_witnesses_verified"] == expected,
            "Every class needs a verified upper witness")
    upper = audit["global_upper_bound_verified"]
    require(type(upper) is int and upper >= 1, "Missing verified global upper bound")
    keys = audit["keys_at_largest_verified_upper_bound"]
    require(isinstance(keys, list) and keys and all(isinstance(key, str) and len(key) == 28
            and key.isascii() and key.isdigit() for key in keys), "Missing or invalid upper-frontier keys")
    require(len(keys) == len(set(keys)), "Repeated upper-frontier class")
    require(audit["upper_bound_distribution"][str(upper)] == len(keys), "Upper-frontier count mismatch")
    return upper, keys


def validate_frontier_record(record, ordinal, upper):
    require(type(record.get("m")) is int and record["m"] == 7
            and type(record.get("ordinal")) is int and record["ordinal"] == ordinal,
            "Frontier record state count or ordinal mismatch")
    table = record.get("canonical_table")
    require(isinstance(table, list) and len(table) == 7, "Invalid frontier transition table")
    for row in table:
        require(isinstance(row, list) and len(row) == 2 and all(type(v) is int and 0 <= v < 7 for v in row)
                and row[0] <= row[1], "Invalid frontier transition row")
    require(record.get("key") == "".join(f"{v:02d}" for row in table for v in row),
            "Frontier transition table/key mismatch")
    require(type(record.get("lower_bound")) is int and 1 <= record["lower_bound"] <= upper
            and type(record.get("upper_bound")) is int and record["upper_bound"] == upper,
            "Frontier bounds do not match the audited upper frontier")
    return table


def verify_scalar_witness(table, witness, depth):
    require(isinstance(witness, list) and len(witness) == 2 and all(isinstance(word, str)
            and len(word) == depth and not (set(word) - {"0", "1"}) for word in witness)
            and depth > 0 and witness[0] != witness[1], "Invalid distinct equal-length binary witness")
    inputs = [[ord(c) - 48 for c in word] for word in witness]
    for mask in range(128):
        endpoints = []
        for word in inputs:
            state = 0
            for letter in word:
                state = table[state][letter ^ ((mask >> state) & 1)]
            endpoints.append(state)
        require(endpoints[0] == endpoints[1], f"Collision witness is separated by static mask {mask}")


def load_frontier_records(journal, keys, upper, expected):
    wanted, records, count = set(keys), {}, 0
    with Path(journal).open(encoding="utf-8-sig") as stream:
        for ordinal, line in enumerate(stream):
            record = json.loads(line)
            count += 1
            if record["key"] not in wanted:
                continue
            table = validate_frontier_record(record, ordinal, upper)
            require(record["key"] not in records, "Repeated frontier key in journal")
            verify_scalar_witness(table, record["witness"], upper)
            records[record["key"]] = record
    require(count == expected and set(records) == wanted, "Audited frontier records disappeared or journal count changed")
    return records


def lower_command(args, key, depth, working_mib, path):
    command = [args.layer_exe.resolve(), "--key", key, "--depth", str(depth), "--compact",
               "--max-working-mib", str(working_mib), "--timeout-ms", str(args.lower_timeout_ms), "--out", path]
    if args.lower_threads > 1:
        command += ["--threads", str(args.lower_threads)]
    return command


def interpret_lower_report(report, key, upper, record, allow_collision):
    depth = upper - 1
    require(report["method"] == METHOD and type(report["m"]) is int and report["m"] == 7
            and report["key"] == key and type(report["depth"]) is int and report["depth"] == depth,
            f"Lower checker identity mismatch for {key}")
    require(isinstance(report["reason"], str) and report["reason"] == "", f"Lower check incomplete for {key}")
    if report["status"] == "collision-free":
        require(type(report["generated_representatives"]) is int
                and report["generated_representatives"] == 1 << (depth - 1)
                and type(report["lower_bound"]) is int and report["lower_bound"] == upper
                and report["witness"] is None and report["upper_bound"] is None,
                f"Incomplete full-mask injectivity proof for {key}")
        return {"key": key, "outcome": "collision-free", "lower_bound": upper}
    require(allow_collision and report["status"] == "collision-found",
            f"Upper-frontier graph {key} has not been proved to attain {upper}; refine the journal")
    require(type(report["upper_bound"]) is int and report["upper_bound"] == depth,
            f"Collision bound does not match requested depth for {key}")
    validate_frontier_record(record, record["ordinal"], upper)
    verify_scalar_witness(record["canonical_table"], report["witness"], depth)
    return {"key": key, "outcome": "collision-found", "upper_bound": depth, "witness": report["witness"],
            "cpu_scalar_masks_verified": 128}


def execute_frontier_checks(args, records, upper, directory):
    keys = list(records)
    if upper == 1:
        return [{"key": key, "outcome": "collision-free", "lower_bound": 1, "trivial_positive_length_bound": True}
                for key in keys]
    depth = upper - 1
    require(depth <= 33, "Independent lower checker currently supports depth through 33")
    working_mib = ((1 << (depth - 1)) * 8 + 1048575) // 1048576 + 64
    require(working_mib <= args.max_total_working_mib, "Insufficient total lower-check memory budget")
    jobs = min(args.jobs, args.max_total_working_mib // working_mib)

    def lower_check(key):
        path = directory / f"lower-{key}.json"
        try:
            run(lower_command(args, key, depth, working_mib, path), directory / f"lower-{key}.log")
            outcome = interpret_lower_report(json.loads(path.read_text()), key, upper, records[key], args.refine_frontier)
            outcome.update(path=path.name, sha256=digest(path))
            print(f"Fresh {outcome['outcome']}: {key}", flush=True)
            return outcome
        except Exception as error:
            if not args.refine_frontier:
                raise
            # In refinement mode, even a failed graph must not cancel pending
            # original-frontier checks. Every key gets an actual execution.
            outcome = {"key": key, "outcome": "incomplete", "error": str(error)}
            if path.exists():
                outcome.update(path=path.name, sha256=digest(path))
            print(f"Fresh incomplete check: {key}: {error}", flush=True)
            return outcome

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(lower_check, keys))


def write_refined_journal(journal, destination, records, outcomes, upper, expected):
    collisions = {outcome["key"]: outcome for outcome in outcomes if outcome["outcome"] == "collision-found"}
    by_ordinal = {}
    for key, outcome in collisions.items():
        record = records[key]
        validate_frontier_record(record, record["ordinal"], upper)
        require(outcome["upper_bound"] == upper - 1, "Refinement does not lower the frontier by one")
        verify_scalar_witness(record["canonical_table"], outcome["witness"], upper - 1)
        require(record["lower_bound"] <= upper - 1, f"Refinement contradicts inherited lower bound for {key}")
        require(record["ordinal"] not in by_ordinal, "Repeated refined ordinal")
        by_ordinal[record["ordinal"]] = (key, outcome)
    require(not destination.exists(), "Refined journal destination already exists")
    temporary = destination.with_name(destination.name + ".tmp")
    require(not temporary.exists(), "Refined journal staging path already exists")
    count, applied = 0, set()
    checksum = hashlib.sha256()
    try:
        with Path(journal).open("rb") as source, temporary.open("xb") as output:
            for ordinal, raw in enumerate(source):
                require(count < expected, "Refined journal has too many records")
                data = raw
                if ordinal in by_ordinal:
                    key, outcome = by_ordinal[ordinal]
                    record = json.loads(raw.decode("utf-8-sig" if ordinal == 0 else "utf-8"))
                    require(record == records[key], "Frontier record changed before refinement")
                    validate_frontier_record(record, ordinal, upper)
                    new_upper = outcome["upper_bound"]
                    exact = record["lower_bound"] == new_upper
                    record.update(upper_bound=new_upper, witness=outcome["witness"],
                                  status="exact" if exact else "bounded",
                                  merge_length=new_upper if exact else None,
                                  reason="independently-scalar-verified-frontier-collision")
                    data = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
                    applied.add(key)
                output.write(data)
                checksum.update(data)
                count += 1
            output.flush()
            os.fsync(output.fileno())
        require(count == expected and applied == set(collisions), "Refined journal lost records or updates")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return checksum.hexdigest(), list(collisions.values())


def surviving_frontier(upper, outcomes, audit):
    free = [outcome["key"] for outcome in outcomes if outcome["outcome"] == "collision-free"]
    require(all(outcome["outcome"] in {"collision-free", "collision-found"} for outcome in outcomes),
            "Some initial frontier checks were incomplete; refined journal retained for another invocation")
    require(free, "All initial frontier graphs collided: verified upper decreased; rerun on the retained refined journal")
    require(audit["global_upper_bound_verified"] == upper
            and set(audit["keys_at_largest_verified_upper_bound"]) == set(free),
            "Refined upper frontier does not equal the freshly proved lower frontier")
    return free


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--upper-exe", type=Path, default=ROOT / "out/build/msvc-vcpkg/Release/Family1ExhaustiveVerify.exe")
    parser.add_argument("--layer-exe", type=Path, default=ROOT / "out/build/msvc-vcpkg/Release/Family1LayerVerify.exe")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--max-total-working-mib", type=int, default=16384)
    parser.add_argument("--lower-timeout-ms", type=int, default=600000)
    parser.add_argument("--lower-threads", type=int, default=1,
                        help="Threads per independent CPU lower check (1..64; default1)")
    parser.add_argument("--refine-frontier", action="store_true",
                        help="Check every original frontier, retain verified collisions in a new journal, and audit it again")
    args = parser.parse_args()
    directory = args.out.resolve()
    require(args.journal.is_file(), "Journal must exist")
    require(args.jobs > 0 and args.max_total_working_mib > 0 and args.lower_timeout_ms >= 0
            and 1 <= args.lower_threads <= 64, "Invalid resource limit")
    require(not directory.exists() or (directory.is_dir() and not any(directory.iterdir())),
            "Certificate output must be new or empty; existing files are preserved")
    directory.mkdir(parents=True, exist_ok=True)
    completed, failure = False, ""
    retained_refinement = None
    original_hash = None
    verifier_hashes, source_hashes = {}, {}
    try:
        original_hash = digest(args.journal)
        verifier_hashes = {str(path.resolve()): digest(path) for path in (args.upper_exe, args.layer_exe)}
        source_paths = (Path(__file__), ROOT / "tests/family1_burnside_count.py",
                        ROOT / "tests/Family1ExhaustiveVerify.cpp", ROOT / "tests/Family1LayerVerify.cpp")
        source_hashes = {str(path.resolve()): digest(path) for path in source_paths}
        count_path = directory / "independent-burnside-counts.json"
        run([sys.executable, ROOT / "tests/family1_burnside_count.py", "--max-m", "7", "--out", count_path],
            directory / "burnside-count.log")
        expected = json.loads(count_path.read_text())["sizes"][-1]["rooted_classes"]
        require(expected == 4166855, "Independent Burnside count differs")
        initial_audit_path = directory / "independent-upper-audit.json"
        print("Checking every rooted canonical class and every full-mask upper witness...", flush=True)
        run([args.upper_exe.resolve(), "--states", "7", "--journal", args.journal.resolve(),
             "--expected-count", str(expected), "--out", initial_audit_path], directory / "upper-audit.log")
        initial_audit = json.loads(initial_audit_path.read_text())
        upper, initial_keys = validate_upper_audit(initial_audit, expected)
        records = load_frontier_records(args.journal, initial_keys, upper, expected)
        check_pins(args.journal, original_hash, verifier_hashes, source_hashes)
        (directory / "initial-frontier-records.jsonl").write_text(
            "".join(json.dumps(records[key], separators=(",", ":")) + "\n" for key in initial_keys), encoding="utf-8")
        print(f"Verified global upper {upper}; independently checking ALL {len(initial_keys)} initial frontier classes...", flush=True)
        outcomes = execute_frontier_checks(args, records, upper, directory)
        require(len(outcomes) == len(initial_keys) and {r["key"] for r in outcomes} == set(initial_keys),
                "Not every initial upper-frontier key received a fresh CPU check")
        check_pins(args.journal, original_hash, verifier_hashes, source_hashes)

        certified_journal, certified_hash = args.journal.resolve(), original_hash
        audit_path, audit = initial_audit_path, initial_audit
        if args.refine_frontier:
            refined = directory / "refined-checkpoint.jsonl"
            refined_hash, collisions = write_refined_journal(args.journal, refined, records, outcomes, upper, expected)
            retained_refinement = {"path": str(refined.resolve()), "sha256": refined_hash,
                                   "records": expected, "upper_bounds_refined": len(collisions)}
            refinements_path = directory / "frontier-upper-refinements.jsonl"
            with refinements_path.open("w", encoding="utf-8") as stream:
                for outcome in collisions:
                    old = records[outcome["key"]]
                    proposal = {"m": 7, "ordinal": old["ordinal"], "key": old["key"],
                                "canonical_table": old["canonical_table"], "upper_bound": outcome["upper_bound"],
                                "witness": outcome["witness"], "cpu_scalar_masks_verified": 128}
                    stream.write(json.dumps(proposal, separators=(",", ":")) + "\n")
            audit_path = directory / "independent-refined-upper-audit.json"
            print(f"Rechecking the complete refined journal ({len(collisions)} verified upper refinements)...", flush=True)
            run([args.upper_exe.resolve(), "--states", "7", "--journal", refined,
                 "--expected-count", str(expected), "--out", audit_path], directory / "refined-upper-audit.log")
            audit = json.loads(audit_path.read_text())
            validate_upper_audit(audit, expected)
            require(digest(refined) == refined_hash, "Refined journal changed during its native audit")
            check_pins(args.journal, original_hash, verifier_hashes, source_hashes)
            keys = surviving_frontier(upper, outcomes, audit)
            certified_journal, certified_hash = refined, refined_hash
        else:
            keys = initial_keys
            require(all(r["outcome"] == "collision-free" for r in outcomes),
                    "Strict verification requires every original frontier lower proof")

        wanted, winners = set(keys), []
        with certified_journal.open(encoding="utf-8-sig") as stream:
            for line in stream:
                record = json.loads(line)
                if record["key"] in wanted:
                    require(record["upper_bound"] == upper, "Frontier upper changed")
                    winners.append(dict(record, status="exact", merge_length=upper,
                                        lower_bound=upper, upper_bound=upper,
                                        reason="independent-global-upper-and-full-mask-lower"))
        require(len(winners) == len(keys), "Frontier records disappeared or repeated")
        require(digest(certified_journal) == certified_hash, "Certified journal changed during winner export")
        check_pins(args.journal, original_hash, verifier_hashes, source_hashes)
        (directory / "maximizers.jsonl").write_text(
            "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in winners), encoding="utf-8")
        proofs = [r for r in outcomes if r["outcome"] == "collision-free"]
        certificate = {"schema": 1, "m": 7,
                       "method": "independently-checked-complete-upper-cover-and-every-frontier-lower",
                       "graph_model": {"root": 0, "reachable_states": 7, "outgoing_ports_per_state": 2,
                                       "loops_allowed": True, "coincident_ports_allowed": True,
                                       "indegree_restriction": None, "strong_connectivity_required": False,
                                       "equivalence": "root-preserving vertex relabeling and independent port swaps",
                                       "each_seed_scored_separately": True},
                       "score_definition": "Least positive equal-length collision of distinct words over all static local XOR masks",
                       "evaluated": expected, "enumeration_complete": True,
                       "maximum_value_certified": True, "maximum_merge_length": upper,
                       "maximizing_collection_complete": True, "maximizer_count": len(keys),
                       "maximizer_keys": keys, "all_other_graphs_have_verified_upper_at_most": upper - 1,
                       "journal": {"path": str(certified_journal.resolve()), "sha256": certified_hash},
                       "input_journal": {"path": str(args.journal.resolve()), "sha256": original_hash},
                       "upper_audit": {"path": audit_path.name, "sha256": digest(audit_path)},
                       "initial_upper_audit": {"path": initial_audit_path.name, "sha256": digest(initial_audit_path)},
                       "independent_count": {"path": count_path.name, "sha256": digest(count_path)},
                       "independent_lower_checks": proofs,
                       "initial_frontier_checks": outcomes,
                       "initial_frontier_count": len(initial_keys),
                       "refine_frontier": args.refine_frontier,
                       "frontier_upper_refinements": sum(r["outcome"] == "collision-found" for r in outcomes),
                       "lower_threads": args.lower_threads,
                       "verifiers": [{"path": path, "sha256": checksum} for path, checksum in verifier_hashes.items()],
                       "verification_sources": [{"path": path, "sha256": checksum} for path, checksum in source_hashes.items()],
                       "reproduction": "Rerun this script on journal.path in a new output directory; CPU lower checks are executed, not imported."}
        (directory / "summary.json").write_text(json.dumps(certificate, indent=2) + "\n", encoding="utf-8")
        completed = True
        print(f"CERTIFIED: seven-state global maximum {upper}, every tie retained ({len(keys)} rooted classes).", flush=True)
    except Exception as error:
        failure = str(error)
        raise
    finally:
        if not completed:
            incomplete = {"maximum_value_certified": False, "maximizing_collection_complete": False,
                          "failure": failure, "refine_frontier": args.refine_frontier}
            if retained_refinement is not None:
                incomplete["retained_refined_journal"] = retained_refinement
            if original_hash is not None:
                try:
                    check_pins(args.journal, original_hash, verifier_hashes, source_hashes)
                    incomplete["source_and_verifier_pins_stable"] = True
                except Exception as error:
                    incomplete["source_and_verifier_pins_stable"] = False
                    incomplete["pin_failure"] = str(error)
            (directory / "incomplete.json").write_text(json.dumps(incomplete, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

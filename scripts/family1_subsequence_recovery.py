#!/usr/bin/env python3
"""Try complete subsequence pools of newly constructed best near-pairs only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil

REPO = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = ["results/family1-finder-lookahead-grid-v1/runs.jsonl",
                "results/family1-finder-lookahead-grid-v2/runs.jsonl"]


def ref(path):
    path = Path(path).resolve()
    return {"path": path.relative_to(REPO).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def endpoint(table, mask, word):
    state = 0
    for bit in word:
        state = table[state][int(bit) ^ ((mask >> state) & 1)]
    return state


def distinct_count(word, target):
    # Independent length-count DP: sequences ending in the latest occurrence
    # of either letter partition the distinct nonempty subsequences.
    ends = [[0] * (target + 1) for _ in range(2)]
    total = [1] + [0] * target
    for bit in word:
        letter = int(bit)
        for length in range(target, 0, -1):
            ends[letter][length] = total[length - 1]
            total[length] = ends[0][length] + ends[1][length]
    return total[target]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", default="out/family1-subsequence-recovery/Family1SubsequenceRecovery.exe")
    parser.add_argument("--runs", nargs="+", default=DEFAULT_RUNS)
    parser.add_argument("--ordinals", type=int, nargs="+", default=[679758, 2221624, 2471796])
    parser.add_argument("--target", type=int, default=34)
    parser.add_argument("--output", default="results/family1-subsequence-recovery")
    parser.add_argument("--work-dir", default="out/family1-subsequence-recovery/minimum-pools")
    parser.add_argument("--max-nodes", type=int, default=10000000)
    parser.add_argument("--max-profiles", type=int, default=1000000)
    parser.add_argument("--max-words", type=int, default=1000000)
    parser.add_argument("--selection", choices=["minimum", "upto"], default="minimum")
    parser.add_argument("--max-source-length", type=int, default=42)
    parser.add_argument("--substitutions", type=int, choices=[0, 1], default=0,
                        help="Also enumerate subsequences of every single-bit substitution of each constructed source word.")
    args = parser.parse_args()
    exe = (REPO / args.exe).resolve()
    output, work = REPO / args.output, REPO / args.work_dir
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    snapshot = work / "source-snapshot"
    snapshot.mkdir(parents=True, exist_ok=True)
    for source in [exe, Path(__file__), REPO / "tests/Family1SubsequenceRecovery.cpp"]:
        destination = snapshot / source.name
        if destination.exists():
            assert destination.read_bytes() == source.read_bytes(), "Use a new work directory for changed implementation."
        else:
            shutil.copy2(source, destination)
    self_test = subprocess.run([str(exe), "--self-test"], capture_output=True, text=True, check=True)
    (output / "native-self-test.log").write_text(self_test.stdout, encoding="utf-8")
    rows = []
    containers = []
    for name in args.runs:
        path = REPO / name
        container = ref(path)
        containers.append(container)
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["ordinal"] in args.ordinals and row.get("witness"):
                row["row_source"] = container
                rows.append(row)
    outcomes = []
    all_sources = []
    for ordinal in args.ordinals:
        candidates = [r for r in rows if r["ordinal"] == ordinal]
        best = min(r["found_length"] for r in candidates)
        candidates = sorted((r for r in candidates if (r["found_length"] == best if args.selection == "minimum"
                                                      else r["found_length"] <= args.max_source_length)),
                            key=lambda r: (r["row_source"]["path"], r["run_id"]))
        keys = {r["key"] for r in candidates}
        assert len(keys) == 1
        key = keys.pop()
        values = [int(key[i:i + 2]) for i in range(0, len(key), 2)]
        table = list(zip(values[::2], values[1::2]))
        words, pairs, sources = set(), set(), []
        for row in candidates:
            native = REPO / row["native_result"]["path"]
            native_ref = ref(native)
            assert native_ref == row["native_result"]
            result = json.loads(native.read_text(encoding="utf-8"))
            length = row["found_length"]
            assert result["witness"] == row["witness"] and result["upper_bound"] == length
            pair = tuple(sorted(row["witness"]))
            assert pair[0] != pair[1] and len(pair[0]) == len(pair[1]) == length
            assert all(endpoint(table, mask, pair[0]) == endpoint(table, mask, pair[1]) for mask in range(128))
            words.update(pair)
            pairs.add(pair)
            sources.append({"ordinal": ordinal, "run_id": row["run_id"], "row_source": row["row_source"],
                            "native_result": native_ref, "words": pair, "length": length})
        folder = work / str(ordinal)
        folder.mkdir(parents=True, exist_ok=True)
        word_file = folder / "input-words.txt"
        input_words = set(words)
        if args.substitutions:
            for word in words:
                for position, bit in enumerate(word):
                    input_words.add(word[:position] + str(1-int(bit)) + word[position+1:])
        ordered_words = sorted(input_words, key=lambda word: (len(word), word))
        word_file.write_text("\n".join(ordered_words) + "\n", encoding="ascii")
        command = [str(exe), "--graph", key, "--input-file", str(word_file),
                   "--target", str(args.target), "--out", str(folder), "--max-nodes", str(args.max_nodes),
                   "--max-profiles", str(args.max_profiles), "--max-words", str(args.max_words)]
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        (folder / "native.log").write_text(process.stdout + process.stderr, encoding="utf-8")
        result = json.loads((folder / "result.json").read_text())
        assert result["input_words"] == ordered_words
        count_reference = [distinct_count(w, args.target) for w in ordered_words]
        for actual, expected, complete in zip(result["unique_subsequences_per_input"], count_reference,
                                               result["subsequence_space_complete_per_input"]):
            assert actual == expected if complete else actual <= expected
        verified = []
        for first, second in result["witnesses"]:
            assert len(first) == len(second) == args.target and first != second
            first_states = [endpoint(table, mask, first) for mask in range(128)]
            second_states = [endpoint(table, mask, second) for mask in range(128)]
            assert first_states == second_states
            verified.append({"words": [first, second], "first_product_state": first_states,
                             "second_product_state": second_states, "masks_verified": 128})
        outcome = {"ordinal": ordinal, "key": key, "known_H": 34,
                   "source_near_length": best, "distinct_source_pairs": len(pairs),
                   "source_length_range": [min(map(len, words)), max(map(len, words))],
                   "distinct_source_words": len(words), "target_length": args.target,
                   "substitution_radius": args.substitutions, "distinct_input_words": len(input_words),
                   "decision": result["decision"], "upper_bound": result["upper_bound"],
                   "complete_within_subsequence_space": result["complete_within_subsequence_space"],
                   "no_pair_in_subsequence_space": result["no_pair_in_subsequence_space"],
                   "union_distinct_subsequences": result["union_distinct_subsequences"],
                   "unique_complete_profiles": result["unique_complete_profiles"],
                   "colliding_profiles": result["colliding_profiles"],
                   "native_seconds": result["seconds"], "nodes": result["nodes"],
                   "cap_reason": result["cap_reason"],
                   "complete_inputs": sum(result["subsequence_space_complete_per_input"]),
                   "per_input_count_reference": count_reference,
                   "native_result": ref(folder / "result.json"), "input_words": ref(word_file),
                   "independent_length_count_dp_passed": True,
                   "stored_witnesses_scalar_verified": verified,
                   "command": command, "sources": sources}
        outcomes.append(outcome)
        all_sources.extend(sources)
        dump(output / f"m7-{ordinal}.json", outcome)
        print(ordinal, best, len(pairs), len(words), result["decision"],
              result["union_distinct_subsequences"], result["seconds"], flush=True)
    summary = {"schema": 1, "method": "best-near-pair-exhaustive-subsequence-union",
               "source_script": ref(snapshot / Path(__file__).name), "native_source": ref(snapshot / "Family1SubsequenceRecovery.cpp"),
               "native_executable": ref(snapshot / exe.name), "row_sources": containers,
               "original_saved_witness_files_read": False,
               "candidate_selection": args.selection, "max_source_length": args.max_source_length,
               "substitution_radius": args.substitutions,
               "max_nodes": args.max_nodes, "max_profiles": args.max_profiles, "max_words": args.max_words,
               "graph_count": len(outcomes), "target_length": args.target,
               "recovered_graph_ordinals": [r["ordinal"] for r in outcomes if r["decision"] == "collision"],
               "restricted_complete_negative_ordinals": [r["ordinal"] for r in outcomes if r["no_pair_in_subsequence_space"]],
               "no_global_lower_bound_claimed": True, "outcomes": outcomes}
    dump(output / "summary.json", summary)
    lines = ["# Subsequence reduction of constructed near-pairs", "",
             "The inputs are newly constructed near-pairs from the controlled v1/v2 lookahead grids. For each of the three remaining seven-state classes, take every distinct eligible pair, form the union of distinct length-34 subsequences of all its input words, and compare complete endpoint vectors over all 128 static masks. Saved optimal witnesses are not read. Selection mode: `" + args.selection + "`; maximum source length " + str(args.max_source_length) + "; substitution radius " + str(args.substitutions) + ". Radius1 adds every single-bit substitution of every constructed source word before taking subsequences. Those mutated inputs are new candidates and are not themselves asserted to be universally hard pairs. Words are processed by increasing length, then lexicographically.", "",
             "| Ordinal | Source length range | Source pairs | Source words | Input words incl. mutations | Distinct subsequences | Recovered length34 | Complete within this pool | Native seconds |",
             "|---:|---:|---:|---:|---:|---:|:---:|:---:|---:|"]
    for row in outcomes:
        lines.append(f"| {row['ordinal']} | {row['source_length_range'][0]}–{row['source_length_range'][1]} | {row['distinct_source_pairs']} | {row['distinct_source_words']} | {row['distinct_input_words']} | {row['union_distinct_subsequences']} | {'yes' if row['decision']=='collision' else 'no'} | {'yes' if row['complete_within_subsequence_space'] else 'no'} | {row['native_seconds']:.6f} |")
    lines += ["", "Each negative result excludes a collision only inside the explicitly described subsequence pool. It supplies no graph score lower bound and does not rule out other length-34 pairs. Equal hashes are always checked against complete product-state vectors, and identical words are excluded even when they occur in several source pools.", "",
              "The standalone MSVC/O2 implementation generates each distinct subsequence once per source word by choosing the earliest available occurrence of its next letter; a later equal occurrence can only remove possible suffixes. It shares endpoint computations along this enumeration tree. Cross-input duplicates are deduplicated as actual words. All retained words from all inputs share one complete-profile table, so cross-input and within-input collisions are both detected.", "",
              "The native self-test compares all 1,538 binary-word/target-length spaces through source length7 against a separate positional-subset implementation, replays cached profiles, forces all hashes equal, checks loops/coincident ports, and checks resource-cap labeling. The Python runner independently checks each source pair over128 masks, checks each per-input subsequence count by a distinct-subsequence dynamic program, and replays every reported hit independently.", "",
              f"Limits: {args.max_nodes:,} enumeration nodes; {args.max_profiles:,} distinct complete profiles; {args.max_words:,} distinct words. A resource cap marks the entire union incomplete; per-input flags identify fully enumerated inputs. Incomplete counts are compared with upper totals from the independent counting DP. No negative result from a capped pool is treated as exhaustive.", "",
              "Per-graph JSON pins the native result, source rows, newly constructed source pairs, full product states of any accepted hits, and reproduction command. No CMake or existing experiment files were changed.", "",
              "```powershell", "cmd.exe /c out\\family1-subsequence-recovery\\build.cmd",
              "uv run --no-project python scripts/family1_subsequence_recovery.py", "```", ""]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

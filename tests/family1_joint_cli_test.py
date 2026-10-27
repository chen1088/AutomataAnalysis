#!/usr/bin/env python3
"""Independent scalar reference and CLI checks for four-letter joint search.

Every joint step appends one of 00, 01, 10, 11 to the two words. The reference
starts with two empty words and retains every original static local mask.
The scalar reference uses no repository implementation, historical witness,
prefix seed or randomness. CLI checks may enable graph-only deterministic
multistarts. Run without --exe for the small exhaustive scalar checks alone.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
from itertools import combinations_with_replacement, permutations, product
import json
from pathlib import Path
import subprocess
import tempfile


ALPHABET = ((0, 0), (0, 1), (1, 0), (1, 1))
ALPHABET_TEXT = ["00", "01", "10", "11"]


def reachable(table):
    seen, pending = {0}, [0]
    while pending:
        for target in table[pending.pop()]:
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return len(seen) == len(table)


def canonical(table):
    tables = []
    for tail in permutations(range(1, len(table))):
        order = (0, *tail)
        inverse = {old: new for new, old in enumerate(order)}
        tables.append(tuple(tuple(sorted(inverse[target] for target in table[old]))
                            for old in order))
    return min(tables)


def graph_key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def endpoint(table, mask, word):
    state = 0
    for symbol in word:
        state = table[state][int(symbol) ^ ((mask >> state) & 1)]
    return state


def profile(table, word):
    return tuple(endpoint(table, mask, word) for mask in range(1 << len(table)))


def permutation_masks(table):
    return tuple(mask for mask in range(1 << len(table))
                 if all(len({table[state][letter ^ ((mask >> state) & 1)]
                             for state in range(len(table))}) == len(table)
                        for letter in range(2)))


def pair_metric_trace(table, pair, masks=None):
    if masks is None:
        masks = range(1 << len(table))
    return [sum(endpoint(table, mask, pair[0][:depth]) != endpoint(table, mask, pair[1][:depth])
                for mask in masks) for depth in range(len(pair[0]) + 1)]


def single_word_shortest(table, max_depth=6):
    """Find the first collision using fresh single-word tables at each length."""
    for depth in range(1, max_depth + 1):
        seen = {}
        for letters in product("01", repeat=depth):
            word = "".join(letters)
            vector = profile(table, word)
            if vector in seen:
                return depth, (seen[vector], word)
            seen[vector] = word
    return None


def initial_pair(table):
    zero = (0,) * (1 << len(table))
    return "", "", zero, zero


def append_joint(table, state, letters):
    first, second, left, right = state
    a, b = letters
    left = tuple(table[at][a ^ ((mask >> at) & 1)] for mask, at in enumerate(left))
    right = tuple(table[at][b ^ ((mask >> at) & 1)] for mask, at in enumerate(right))
    return first + str(a), second + str(b), left, right


def disagreement(state):
    return sum(a != b for a, b in zip(state[2], state[3]))


def joint_layer(table, frontier):
    return [append_joint(table, state, letters)
            for state in frontier for letters in ALPHABET]


def full_joint_window(table, k):
    """Unpruned four-ary traversal: k means k joint steps and 4**k leaves."""
    frontier = [initial_pair(table)]
    for _ in range(k):
        frontier = joint_layer(table, frontier)
    assert len(frontier) == 4 ** k
    return frontier


def joint_shortest(table, max_depth=6):
    frontier = [initial_pair(table)]
    for depth in range(1, max_depth + 1):
        frontier = joint_layer(table, frontier)
        assert len(frontier) == 4 ** depth
        matches = [(first, second) for first, second, left, right in frontier
                   if first != second and left == right]
        if matches:
            pair = min(matches)
            assert profile(table, pair[0]) == profile(table, pair[1])
            return depth, pair
    return None


@lru_cache(maxsize=None)
def small_classes(m):
    choices = list(combinations_with_replacement(range(m), 2))
    tables = {canonical(table) for table in product(choices, repeat=m) if reachable(table)}
    return tuple(sorted(tables))


def scalar_checks():
    expected_counts = {1: 1, 2: 6, 3: 57}
    expected_maxima = {1: 1, 2: 3, 3: 6}
    expected_ties = {1: 1, 2: 1, 3: 2}
    references = {}
    for m in range(1, 4):
        tables = small_classes(m)
        assert len(tables) == expected_counts[m]
        scores = {}
        for table in tables:
            single, joint = single_word_shortest(table), joint_shortest(table)
            assert single is not None and joint is not None and single[0] == joint[0], (table, single, joint)
            scores[graph_key(table)] = (table, single[0])
        maximum = max(score for _, score in scores.values())
        assert maximum == expected_maxima[m]
        assert sum(score == maximum for _, score in scores.values()) == expected_ties[m]
        references[m] = scores

    two = ((0, 1), (0, 1))
    leaves = full_joint_window(two, 2)
    assert len({(first, second) for first, second, _, _ in leaves}) == 16
    assert any(first == "00" and second == "11" for first, second, _, _ in leaves)
    assert any(first == "01" and second == "10" for first, second, _, _ in leaves)
    for first, second, left, right in leaves:
        assert profile(two, first) == left and profile(two, second) == right

    # Independent inputs can destroy an existing agreement. Even when the
    # total disagreement count stays equal, the agreeing mask set can change.
    root = initial_pair(two)
    split = append_joint(two, root, (0, 1))
    partial_merge = append_joint(two, split, (0, 0))
    exchange = append_joint(two, partial_merge, (0, 1))
    assert disagreement(root) == 0 and disagreement(split) == 4
    assert disagreement(partial_merge) == 2
    assert partial_merge[2][0] == partial_merge[3][0] and exchange[2][0] != exchange[3][0]
    assert partial_merge[2][1] != partial_merge[3][1] and exchange[2][1] == exchange[3][1]
    return references


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def validate_record(row, expected_m, expected_k, reference):
    assert row["m"] == expected_m and row["k"] == expected_k, row
    assert row["alphabet"] == ALPHABET_TEXT, row
    table = tuple(tuple(ports) for ports in row["canonical_table"])
    assert reachable(table) and canonical(table) == table and graph_key(table) == row["key"], row
    assert table == reference[row["key"]][0]
    assert row["lower_bound"] == 1 and row["minimality_certified"] is False, row
    assert row["score"] in {"total", "permutation"} and row["startup"] in {"legacy", "divergence"}, row
    assert row["dfa_count"] == 1 << expected_m, row
    selected = permutation_masks(table) if row["score"] == "permutation" else ()
    assert row["priority_coordinate_count"] == len(selected), row
    pair, upper = row["witness"], row["upper_bound"]
    if pair is None:
        assert upper is None and row["status"] == "unresolved" and row["static_masks_verified"] == 0, row
        assert row["witness_metric_trace"] is row["synchronized_count_trace"] is None, row
        assert row["winning_attempt"] is row["first_difference_position"] is None, row
        assert row["round_trace_role"] == "last-attempt", row
    else:
        assert row["status"] == "verified-upper" and len(pair) == 2 and pair[0] != pair[1], row
        assert len(pair[0]) == len(pair[1]) == upper and upper >= reference[row["key"]][1], row
        assert all(word and set(word) <= {"0", "1"} for word in pair), row
        assert profile(table, pair[0]) == profile(table, pair[1]), row
        assert row["static_masks_verified"] == 1 << expected_m, row
        trace = pair_metric_trace(table, pair)
        assert row["witness_metric_trace"] == trace and trace[0] == trace[-1] == 0, row
        assert row["synchronized_count_trace"] == [(1 << expected_m) - value for value in trace], row
        difference = next(at + 1 for at, (a, b) in enumerate(zip(*pair)) if a != b)
        assert row["first_difference_position"] == difference, row
        winning = row["winning_attempt"]
        assert winning["kind"] in {"empty", "legacy-prefix", "divergence"}, row
        assert 1 <= winning["number"] <= row["attempts"] and row["trace_attempt"] == winning["number"], row
        initial = winning["initial_first"], winning["initial_second"]
        initial_length = winning["initial_length"]
        assert len(initial[0]) == len(initial[1]) == initial_length <= upper, row
        assert all(word.startswith(prefix) for word, prefix in zip(pair, initial)), row
        assert winning["first_difference_depth"] == difference, row
        assert row["trace_initial_length"] == initial_length and row["trace_initial_D"] == trace[initial_length], row
        priority_trace = pair_metric_trace(table, pair, selected)
        assert row["trace_initial_priority_D"] == priority_trace[initial_length], row
        assert row["round_trace_role"] == "winning-attempt", row
        if winning["kind"] == "divergence":
            common = winning["common_prefix"]
            orientation = winning["orientation"]
            assert orientation in {"01", "10"} and len(common) + 1 == initial_length == difference, row
            assert initial == tuple(common + letter for letter in orientation), row
    assert row["expanded_nodes"] <= row["expansion_cap"] * row["attempts"], row
    if row["startup"] == "divergence":
        planned = 2 * (2 ** (row["common_depth"] + 1) - 1)
        assert row["divergence_starts_planned"] == planned, row
        assert row["attempts"] == row["divergence_attempts"] and row["empty_root_attempts"] == row["prefix_attempts"] == 0, row
        accounted = row["divergence_attempts"] + row["divergence_starts_skipped_by_length"]
        assert accounted <= planned and row["divergence_startup_evaluated_all"] == (accounted == planned), row
    for trace in row["round_trace"]:
        assert trace["endpoint_depth"] == trace["parent_depth"] + trace["span"], row
        assert 1 <= trace["span"] <= expected_k and trace["parents_expanded"] <= trace["parent_count"], row
        assert 0 <= trace["min_parent_D"] <= trace["max_parent_D"] <= 1 << expected_m, row
        assert trace["min_parent_priority_D"] <= trace["max_parent_priority_D"] <= len(selected), row
        if trace["retained_count"]:
            selected_pair = trace["selected_first"], trace["selected_second"]
            assert len(selected_pair[0]) == len(selected_pair[1]) == trace["endpoint_depth"], row
            assert trace["selected_D"] == pair_metric_trace(table, selected_pair)[-1], row
            assert trace["selected_priority_D"] == pair_metric_trace(table, selected_pair, selected)[-1], row
    for window in row["window_reports"]:
        span = window["span"]
        assert 1 <= span <= expected_k and window["expected_leaves"] == 4 ** span, (row["k"], window)
        assert 0 <= window["leaves"] <= 4 ** span, (row["k"], window)
        if window["complete"]:
            assert window["leaves"] == 4 ** span, (row["k"], window)
            assert window["nodes"] == (4 ** (span + 1) - 4) // 3, (row["k"], window)


def cli_checks(executable, directory, references):
    directory.mkdir(parents=True, exist_ok=True)
    invocations = 0

    def run(name, m, keys, k, *extra):
        nonlocal invocations
        target = directory / name
        command = [str(executable), "--m", str(m), "--k", str(k), "--beam", "1024",
                   "--diagonal-beam", "64", "--max-length", "6", "--expansions", "100000",
                   "--out", str(target)]
        for key in keys:
            command += ["--graph", key]
        command += extra
        completed = subprocess.run(command, text=True, capture_output=True, timeout=120)
        invocations += 1
        assert completed.returncode == 0, (command, completed.returncode, completed.stdout, completed.stderr)
        rows = read_rows(target / "records.jsonl")
        summary = json.loads((target / "summary.json").read_text(encoding="utf-8-sig"))
        config = json.loads((target / "run.json").read_text(encoding="utf-8-sig"))
        assert summary["m"] == m and summary["k"] == k and summary["alphabet"] == ALPHABET_TEXT, summary
        assert summary["graphs"] == len(set(keys)) == len(rows), summary
        assert summary["all_supplied_graphs_tested"] and summary["deterministic"] is True, summary
        assert summary["global_maximum_certified"] is False, summary
        assert config["k"] == k, config
        assert {row["key"] for row in rows} == set(keys), rows
        for row in rows:
            validate_record(row, m, k, references[m])
        # Every accepted improvement is persisted separately, with its pair
        # independently replayed over every original mask, even if superseded.
        journal = read_rows(target / "witnesses.jsonl")
        for entry in journal:
            validate_record(entry, m, k, references[m])
            assert entry["witness"] is not None, entry
        for row in rows:
            improvements = [entry for entry in journal if entry["key"] == row["key"]]
            assert len(improvements) == row["accepted_positives_scalar_verified"], (row, improvements)
            assert [entry["accepted_positives_scalar_verified"] for entry in improvements] == list(range(1, len(improvements) + 1)), improvements
            assert all(a["upper_bound"] > b["upper_bound"] for a, b in zip(improvements, improvements[1:])), improvements
            if row["witness"] is not None:
                assert improvements[-1]["witness"] == row["witness"] and improvements[-1]["upper_bound"] == row["upper_bound"], (row, improvements)
            else:
                assert not improvements, (row, improvements)
        assert summary["verified_pairs"] == sum(row["witness"] is not None for row in rows), summary
        assert summary["no_pair"] == sum(row["witness"] is None for row in rows), summary
        return rows

    # k=1 with these widths retains every possible joint prefix before the
    # maximal reference depth six. Exactness is checked by the independent
    # oracle here; the executable must continue to report upper certificates.
    for m in range(1, 4):
        rows = run(f"all-m{m}-k1", m, sorted(references[m]), 1)
        assert all(row["upper_bound"] == references[m][row["key"]][1] for row in rows), rows

    two_key = graph_key(((0, 1), (0, 1)))
    rows = run("joint-k2", 2, [two_key], 2)
    assert rows[0]["witness"] is not None
    assert rows[0]["unequal_width"] == rows[0]["prefix_pairs"] == rows[0]["prefix_attempts"] == 0, rows[0]
    assert rows[0]["attempts"] == rows[0]["empty_root_attempts"] == 1, rows[0]
    assert rows[0]["prefix_plan_generated"] is False, rows[0]
    assert any(window["span"] == 2 and window["complete"] and window["leaves"] == 16
               for window in rows[0]["window_reports"]), rows[0]
    repeated = run("joint-k2-repeat", 2, [two_key, two_key], 2)
    assert repeated == rows, (rows, repeated)

    capped = run("joint-k2-expansion-cap", 2, [two_key], 2, "--expansions", "1")[0]
    assert capped["witness"] is None and capped["expansion_limit_reached"], capped
    assert capped["expanded_nodes"] <= 1 and capped["windows_refused"] >= 1, capped
    assert capped["complete_windows"] == capped["partial_windows"] == 0, capped
    short = run("joint-k1-length-cap", 2, [two_key], 1, "--max-length", "2")[0]
    assert short["witness"] is None and short["length_limit_reached"], short

    # Joint k=1, beam1/diagonal0 uses fresh graph-only multistarts to recover
    # H=3. The independently enumerated oracle supplies the expected length;
    # neither source words nor a score are passed to the executable.
    prefix_options = ("--beam", "1", "--diagonal-beam", "0", "--prefix-pairs", "8",
                      "--prefix-depth", "4", "--prefix-words", "16")
    started = run("joint-k1-multistart", 2, [two_key], 1, *prefix_options)
    start = started[0]
    assert start["upper_bound"] == references[2][two_key][1] == 3, start
    assert start["prefix_plan_generated"] is True and start["prefix_attempts"] > 0, start
    assert start["prefix_pairs"] == 8 and start["prefix_pairs_available"] <= 8, start
    assert start["attempts"] == start["empty_root_attempts"] + start["prefix_attempts"], start
    assert start["empty_root_attempts"] == 1 and start["prefix_words_evaluated"] > 0, start
    repeated = run("joint-k1-multistart-repeat", 2, [two_key], 1, *prefix_options)
    assert repeated == started, (started, repeated)

    # A target hit finishes only that graph. The second accessible graph has
    # coincident ports and must still receive its empty-root joint attempt.
    coincident_key = graph_key(((1, 1), (1, 1)))
    targeted = run("joint-k1-multistart-target", 2, [two_key, coincident_key], 1,
                   *prefix_options, "--target-upper", "3")
    target_by_key = {row["key"]: row for row in targeted}
    assert target_by_key[two_key]["prefix_attempts"] > 0, target_by_key
    assert target_by_key[coincident_key]["prefix_attempts"] == 0, target_by_key
    assert target_by_key[coincident_key]["prefix_plan_generated"] is False, target_by_key
    assert target_by_key[coincident_key]["upper_bound"] == 1, target_by_key
    for row in targeted:
        assert row["target_upper"] == 3 and row["target_upper_reached"] is True, row
        assert row["empty_root_attempts"] == 1 and row["accepted_positives_scalar_verified"] > 0, row
    target_directory = directory / "joint-k1-multistart-target"
    target_config = json.loads((target_directory / "run.json").read_text(encoding="utf-8-sig"))
    target_summary = json.loads((target_directory / "summary.json").read_text(encoding="utf-8-sig"))
    assert target_config["prefix_pairs"] == 8 and target_config["target_upper"] == 3, target_config
    assert "no sampling or saved words" in target_config["prefix_selection"], target_config
    assert target_summary["target_reached_graphs"] == 2 and target_summary["target_upper"] == 3, target_summary
    assert target_summary["prefix_attempts"] == sum(row["prefix_attempts"] for row in targeted), target_summary

    unequal = run("joint-k1-unequal-quota", 2, [two_key], 1,
                  "--beam", "1", "--diagonal-beam", "0", "--unequal-beam", "1")[0]
    assert unequal["unequal_width"] == 1 and unequal["prefix_attempts"] == 0, unequal
    assert unequal["upper_bound"] == references[2][two_key][1], unequal
    unequal_config = json.loads((directory / "joint-k1-unequal-quota" / "run.json").read_text(encoding="utf-8-sig"))
    assert unequal_config["unequal_width"] == 1 and unequal["unequal_leaves"] > 0, unequal

    # H=6 independently excludes every length<=5 positive, allowing many
    # short fixed attempts to exercise bounded diagnostics without relying
    # on a missed existing witness or changing the four-symbol search space.
    winner3 = next(key for key, (_, score) in references[3].items() if score == 6)
    diagnostic = run("joint-k1-bounded-diagnostics", 3, [winner3], 1,
                     "--beam", "1", "--diagonal-beam", "0", "--max-length", "5",
                     "--prefix-pairs", "32", "--prefix-depth", "4", "--prefix-words", "16")[0]
    retained = json.loads((directory / "joint-k1-bounded-diagnostics" / "run.json").read_text(encoding="utf-8-sig"))["window_reports_retained_per_graph"]
    assert diagnostic["witness"] is None and diagnostic["lower_bound"] == 1, diagnostic
    assert diagnostic["prefix_attempts"] > 0 and diagnostic["window_reports_truncated"] > 0, diagnostic
    assert len(diagnostic["window_reports"]) <= retained, diagnostic
    assert len(diagnostic["window_reports"]) + diagnostic["window_reports_truncated"] == diagnostic["complete_windows"] + diagnostic["partial_windows"], diagnostic
    assert all(1 <= window["attempt"] <= diagnostic["attempts"] for window in diagnostic["window_reports"]), diagnostic

    # Delay the first D ranking until a forced first difference plus a FULL
    # joint k=2 window. Both orientations are independently attempted.
    divergence_options = ("--beam", "1", "--diagonal-beam", "0", "--startup", "divergence",
                          "--common-depth", "0", "--score", "total")
    divergence = run("joint-k2-divergence-c0-total", 2, [two_key], 2, *divergence_options)[0]
    assert divergence["upper_bound"] == 3 and divergence["witness_metric_trace"] == [0, 4, 2, 0], divergence
    assert divergence["synchronized_count_trace"] == [4, 0, 2, 4], divergence
    assert divergence["divergence_attempts"] == divergence["divergence_starts_planned"] == 2, divergence
    assert divergence["divergence_startup_evaluated_all"] is True, divergence
    winning = divergence["winning_attempt"]
    assert winning["kind"] == "divergence" and winning["initial_length"] == winning["first_difference_depth"] == 1, divergence
    assert winning["common_prefix"] == "" and winning["orientation"] == "01" and winning["first_greedy_depth"] == 3, divergence
    assert divergence["round_trace"][0]["parent_depth"] == 1 and divergence["round_trace"][0]["span"] == 2, divergence

    permutation = run("joint-k2-divergence-c0-permutation", 2, [two_key], 2,
                      *divergence_options, "--score", "permutation")[0]
    assert permutation["score"] == "permutation" and permutation["priority_coordinate_count"] == 2, permutation
    assert permutation["upper_bound"] == 3 and permutation["divergence_startup_evaluated_all"], permutation
    assert permutation["trace_initial_priority_D"] == 2, permutation
    for name in ("joint-k2-divergence-c0-total", "joint-k2-divergence-c0-permutation"):
        config = json.loads((directory / name / "run.json").read_text(encoding="utf-8-sig"))
        summary = json.loads((directory / name / "summary.json").read_text(encoding="utf-8-sig"))
        expected_score = "permutation" if name.endswith("permutation") else "total"
        assert config["startup"] == summary["startup"] == "divergence" and config["common_depth"] == summary["common_depth"] == 0, (config, summary)
        assert config["score"] == summary["score"] == expected_score, (config, summary)

    # This rooted graph needs a nonempty common prefix: the two absorbing
    # components cannot meet after a first difference at the root. At c=1,
    # divergence after one common symbol is already a valid distinct D=0 pair.
    common_table = ((1, 2), (1, 1), (2, 2))
    common_key = graph_key(common_table)
    common_miss = run("joint-k2-common-prefix-c0", 3, [common_key], 2, *divergence_options)[0]
    assert common_miss["witness"] is None and common_miss["divergence_startup_evaluated_all"], common_miss
    common_hit = run("joint-k2-common-prefix-c1", 3, [common_key], 2,
                     *divergence_options, "--common-depth", "1")[0]
    assert common_hit["upper_bound"] == 2 and common_hit["witness_metric_trace"] == [0, 0, 0], common_hit
    assert common_hit["synchronized_count_trace"] == [8, 8, 8], common_hit
    assert common_hit["first_difference_position"] == common_hit["winning_attempt"]["initial_length"] == 2, common_hit
    assert common_hit["winning_attempt"]["first_greedy_depth"] == 0 and common_hit["round_trace"] == [], common_hit
    assert common_hit["divergence_starts_planned"] == 6 and common_hit["divergence_startup_evaluated_all"], common_hit
    assert common_hit["divergence_starts_skipped_by_length"] > 0, common_hit

    targeted_divergence = run("joint-k2-divergence-target", 2, [two_key], 2,
                              *divergence_options, "--common-depth", "1", "--target-upper", "3")[0]
    assert targeted_divergence["upper_bound"] == 3 and targeted_divergence["target_upper_reached"], targeted_divergence
    assert targeted_divergence["divergence_attempts"] == 1 and targeted_divergence["divergence_starts_planned"] == 6, targeted_divergence
    assert targeted_divergence["divergence_startup_evaluated_all"] is False, targeted_divergence

    no_trace = run("joint-k2-divergence-no-trace", 2, [two_key], 2,
                   *divergence_options, "--trace-records", "0")[0]
    diagnostic_fields = {"round_trace", "round_trace_records_truncated"}
    assert {key: value for key, value in divergence.items() if key not in diagnostic_fields} == {
        key: value for key, value in no_trace.items() if key not in diagnostic_fields}, (divergence, no_trace)
    assert no_trace["round_trace"] == [] and no_trace["round_trace_records_truncated"] > 0, no_trace
    assert no_trace["witness_metric_trace"] == divergence["witness_metric_trace"], no_trace

    for index, invalid in enumerate((("--prefix-depth", "0"), ("--prefix-depth", "64"),
                                     ("--prefix-words", "0"), ("--prefix-pairs", "-1"),
                                     ("--common-prefix-depth", "9"), ("--startup", "unknown"),
                                     ("--score", "unknown"), ("--common-depth", "9"),
                                     ("--common-depth", "-1"), ("--trace-records", "4097"),
                                     ("--startup", "divergence", "--prefix-pairs", "1"))):
        completed = subprocess.run([str(executable), "--m", "2", "--graph", two_key,
                                    "--k", "1", "--out", str(directory / f"invalid-prefix-{index}"), *invalid],
                                   text=True, capture_output=True, timeout=30)
        invocations += 1
        assert completed.returncode != 0, (invalid, "invalid prefix configuration accepted")
    print(json.dumps({"passed": True, "k_values_checked": [1, 2], "joint_alphabet": ALPHABET_TEXT,
                      "native_invocations": invocations, "independent_small_graphs": 64,
                      "graph_only_multistarts_checked_at_joint_k": 1,
                      "target_continues_to_other_graphs": True,
                      "unequal_quota_and_bounded_diagnostics_checked": True,
                      "divergence_common_depths_checked": [0, 1],
                      "ranking_policies_checked": ["total", "permutation"],
                      "all_accepted_pairs_journaled_and_replayed": True,
                      "witness_and_synchronized_metric_traces_checked": True,
                      "trace_disabled_preserves_search": True,
                      "all_original_masks_replayed": True, "global_maximum_claimed": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    references = scalar_checks()
    if args.exe:
        if args.out:
            cli_checks(args.exe.resolve(), args.out.resolve(), references)
        else:
            with tempfile.TemporaryDirectory(prefix="family1-joint-test-") as directory:
                cli_checks(args.exe.resolve(), Path(directory), references)
    else:
        print(json.dumps({"passed": True, "joint_alphabet": ALPHABET_TEXT,
                          "k_window_checked": 2, "joint_window_leaves": 16,
                          "joint_breadth_depth_checked_through": 6,
                          "independent_small_graphs": 64,
                          "single_word_and_joint_minima_agree": True,
                          "agreement_can_increase_and_decrease": True}))


if __name__ == "__main__":
    main()

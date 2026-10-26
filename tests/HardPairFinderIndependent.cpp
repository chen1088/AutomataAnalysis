#include "HardPairFinder.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <numeric>
#include <queue>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

// This adapter is deliberately independent of every Family1 production class.
// Its coordinates may have different state counts and different roots.
namespace {
using Row = std::array<std::uint32_t, 2>;
using Table = std::vector<Row>;
using Pair = hardpair::CoordinatePair;
struct DFA { Table table; std::uint32_t root = 0; };
struct ExplicitFamily { std::vector<DFA> automata; };

void require(bool value, const std::string& message)
{
    if (!value) throw std::runtime_error(message);
}
std::uint32_t transition(const ExplicitFamily& family, std::size_t id, std::uint32_t state, bool letter)
{
    require(id < family.automata.size(), "coordinate identity lost");
    const auto& table = family.automata[id].table;
    require(state < table.size(), "state count assumed equal across coordinates");
    return table[state][letter ? 1 : 0];
}
std::uint32_t endpoint(const DFA& dfa, const std::string& word)
{
    auto state = dfa.root;
    for (char c : word) state = dfa.table[state][c == '1'];
    return state;
}
struct PairState {
    std::shared_ptr<const ExplicitFamily> family;
    std::vector<Pair> pairs;
    std::uint64_t remaining_count() const { return pairs.size(); }
    std::uint64_t mask_count() const { return family->automata.size(); }
    PairState append_common(bool letter) const
    {
        PairState result{family, {}};
        for (const auto& p : pairs) {
            auto a = transition(*family, p.coordinate, p.first, letter);
            auto b = transition(*family, p.coordinate, p.second, letter);
            if (a != b) result.pairs.push_back({p.coordinate, a, b});
        }
        return result;
    }
    friend bool operator==(const PairState& a, const PairState& b)
    {
        if (a.family != b.family || a.pairs.size() != b.pairs.size()) return false;
        for (std::size_t i = 0; i < a.pairs.size(); ++i)
            if (a.pairs[i].coordinate != b.pairs[i].coordinate || a.pairs[i].first != b.pairs[i].first
                || a.pairs[i].second != b.pairs[i].second) return false;
        return true;
    }
};
PairState pair_state(std::shared_ptr<const ExplicitFamily> family, const std::string& a, const std::string& b)
{
    PairState result{family, {}};
    for (std::size_t id = 0; id < family->automata.size(); ++id) {
        auto x = endpoint(family->automata[id], a), y = endpoint(family->automata[id], b);
        if (x != y) result.pairs.push_back({id, x, y});
    }
    return result;
}
PairState append(PairState state, const std::string& word)
{
    for (char c : word) state = state.append_common(c == '1');
    return state;
}

// Reference BFS uses an ordered set of full scalar vectors; no production
// state hashing, coordinate pruning implementation, or queue code is reused.
struct ReferenceTail { bool found; std::string suffix; std::uint64_t states; };
std::vector<std::uint64_t> state_key(const PairState& state)
{
    std::vector<std::uint64_t> values;
    for (const auto& p : state.pairs) {
        values.push_back(p.coordinate); values.push_back(p.first); values.push_back(p.second);
    }
    return values;
}
ReferenceTail reference_bfs(const PairState& initial)
{
    std::queue<std::pair<PairState, std::string>> queue;
    std::set<std::vector<std::uint64_t>> visited;
    queue.push({initial, ""}); visited.insert(state_key(initial));
    while (!queue.empty()) {
        auto [state, word] = std::move(queue.front()); queue.pop();
        if (!state.remaining_count()) return {true, word, visited.size()};
        for (bool letter : {false, true}) {
            auto next = state.append_common(letter);
            if (visited.insert(state_key(next)).second) {
                require(visited.size() <= 100000, "independent tiny BFS unexpectedly large");
                queue.push({std::move(next), word + (letter ? '1' : '0')});
            }
        }
    }
    return {false, "", visited.size()};
}
hardpair::TailResult native_tail(const PairState& state, hardpair::TailLimits limits)
{
    return hardpair::exact_suffix_bfs(state.pairs,
        [&](std::size_t id, std::uint32_t s, bool x) { return transition(*state.family, id, s, x); }, limits);
}

bool accessible(const Table& table)
{
    std::set<std::uint32_t> reached{0}; std::vector<std::uint32_t> todo{0};
    while (!todo.empty()) {
        auto s = todo.back(); todo.pop_back();
        for (auto target : table[s]) if (reached.insert(target).second) todo.push_back(target);
    }
    return reached.size() == table.size();
}
Table canonical(const Table& table)
{
    std::vector<std::uint32_t> mapping(table.size()); std::iota(mapping.begin(), mapping.end(), 0);
    Table best;
    do {
        Table rows(table.size());
        for (std::size_t s = 0; s < table.size(); ++s) {
            rows[mapping[s]] = {mapping[table[s][0]], mapping[table[s][1]]};
            std::sort(rows[mapping[s]].begin(), rows[mapping[s]].end());
        }
        if (best.empty() || rows < best) best = std::move(rows);
    } while (std::next_permutation(mapping.begin() + 1, mapping.end()));
    return best;
}
std::set<Table> classes(unsigned int m)
{
    std::set<Table> result; std::uint64_t count = 1;
    for (unsigned int i = 0; i < 2 * m; ++i) count *= m;
    for (std::uint64_t code = 0; code < count; ++code) {
        auto value = code; Table table(m);
        for (auto& row : table) for (auto& target : row) { target = value % m; value /= m; }
        if (accessible(table)) result.insert(canonical(table));
    }
    return result;
}
std::shared_ptr<const ExplicitFamily> realize(const Table& table)
{
    auto family = std::make_shared<ExplicitFamily>();
    for (std::uint32_t mask = 0; mask < (1U << table.size()); ++mask) {
        DFA dfa; dfa.table.resize(table.size());
        for (std::size_t s = 0; s < table.size(); ++s)
            dfa.table[s] = {table[s][(mask >> s) & 1U], table[s][1U ^ ((mask >> s) & 1U)]};
        family->automata.push_back(std::move(dfa));
    }
    return family;
}
std::vector<std::string> words(unsigned int length)
{
    std::vector<std::string> result;
    for (unsigned int code = 0; code < (1U << length); ++code) {
        std::string word(length, '0');
        for (unsigned int i = 0; i < length; ++i) word[length - 1 - i] += (code >> i) & 1U;
        result.push_back(std::move(word));
    }
    return result;
}
void compare_tail(const PairState& initial, bool forced)
{
    const auto expected = reference_bfs(initial);
    hardpair::TailLimits limits; limits.max_states = 100000; limits.max_depth = 4096;
    limits.force_hash_collisions = forced;
    const auto actual = native_tail(initial, limits);
    require(!actual.capped && !actual.interrupted, "uncapped tiny BFS stopped early");
    require(actual.found == expected.found, "generic BFS disagrees with scalar reference");
    if (actual.found) {
        require(actual.shortest_conditional, "complete BFS does not certify conditional suffix");
        require(actual.suffix.size() == expected.suffix.size(), "suffix is not shortest from fixed pair");
        require(append(initial, actual.suffix).remaining_count() == 0, "reported suffix fails scalar replay");
    } else require(actual.unreachable, "exhausted unreachable pair not marked unreachable");
}
void compare_distribution(const PairState& initial, unsigned int k, std::uint64_t max_expansions = 10000)
{
    const auto actual = hardpair::enumerate_window_distribution(initial, k, max_expansions);
    require(actual.complete && !actual.interrupted && !actual.expansion_limit_reached, "small complete distribution capped");
    require(actual.window_count == (1ULL << k) && actual.ranked.size() == (1ULL << k), "not every binary window retained");
    std::vector<double> values; std::set<std::string> seen;
    std::uint64_t zeros = 0, goals = 0;
    for (const auto& entry : actual.ranked) {
        require(entry.window.size() == k && seen.insert(entry.window).second, "duplicate/invalid window");
        const auto remaining = append(initial, entry.window).remaining_count();
        const auto drop = initial.remaining_count() - remaining;
        require(entry.remaining_count == remaining && entry.drop == drop && entry.all_merged == (remaining == 0), "window gain differs from scalar states");
        if (initial.remaining_count()) require(std::abs(entry.normalized_drop - double(drop) / initial.remaining_count()) < 1e-12, "normalized gain denominator wrong");
        values.push_back(double(drop)); zeros += drop == 0; goals += remaining == 0;
    }
    std::sort(values.begin(), values.end());
    const auto mean = std::accumulate(values.begin(), values.end(), 0.0) / values.size();
    double variance = 0; for (double v : values) variance += (v - mean) * (v - mean); variance /= values.size();
    const auto middle = values.size() / 2;
    const auto median = values.size() % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2;
    require(actual.min_drop == values.front() && actual.max_drop == values.back(), "window extrema wrong");
    require(actual.zero_drop_count == zeros && actual.full_merge_count == goals, "window counts wrong");
    require(std::abs(actual.mean_drop - mean) < 1e-12 && std::abs(actual.median_drop - median) < 1e-12
        && std::abs(actual.variance_drop - variance) < 1e-12 && std::abs(actual.stddev_drop - std::sqrt(variance)) < 1e-12, "window distribution moments wrong");
}

struct Counters { std::uint64_t classes = 0, conditional_pairs = 0, forced_hash_cases = 0, distributions = 0; };
Counters tiny_family_checks()
{
    Counters counts;
    for (unsigned int m = 1; m <= 3; ++m) {
        const auto tables = classes(m);
        require(tables.size() == (m == 1 ? 1 : m == 2 ? 6 : 57), "independent class enumeration wrong");
        for (const auto& table : tables) {
            ++counts.classes; const auto family = realize(table);
            bool forced = false;
            for (unsigned int n = 1; n <= 3; ++n) {
                const auto values = words(n);
                for (std::size_t a = 0; a < values.size(); ++a) for (std::size_t b = a + 1; b < values.size(); ++b) {
                    auto initial = pair_state(family, values[a], values[b]);
                    if (initial.remaining_count() > 4) continue;
                    compare_tail(initial, false); ++counts.conditional_pairs;
                    if (!forced && initial.remaining_count()) { compare_tail(initial, true); forced = true; ++counts.forced_hash_cases; }
                }
            }
            auto initial = pair_state(family, "01", "10");
            compare_distribution(initial, 2); compare_distribution(initial, 4); counts.distributions += 2;
        }
    }
    require(counts.classes == 64, "missing tiny family");
    return counts;
}

std::shared_ptr<const ExplicitFamily> heterogeneous()
{
    auto family = std::make_shared<ExplicitFamily>();
    family->automata.push_back({{{0,0},{0,1}},1});
    family->automata.push_back({{{1,0},{2,1},{2,2}},0});
    family->automata.push_back({{{1,0},{2,1},{3,2},{4,3},{4,4}},0});
    return family;
}
hardpair::FinderResult finder(const PairState& initial, hardpair::FinderOptions options)
{
    auto answer = hardpair::find_hard_pair_suffix(initial, options,
        [&](const PairState& state, const hardpair::TailLimits& limits) { return native_tail(state, limits); });
    const auto replay = append(initial, answer.suffix);
    require(answer.remaining_count == replay.remaining_count(), "finder count differs from scalar suffix replay");
    require(answer.mask_count == initial.mask_count() && answer.found == (replay.remaining_count() == 0), "finder success count wrong");
    require(answer.suffix.size() <= options.max_suffix, "finder exceeded suffix budget");
    require(answer.remaining_trace.size() == answer.suffix.size() + 1, "finder trace length wrong");
    auto current = initial;
    for (std::size_t i = 0; i < answer.remaining_trace.size(); ++i) {
        require(answer.remaining_trace[i] == current.remaining_count(), "finder trace differs from scalar states");
        require(answer.score_trace[i] == current.mask_count() - current.remaining_count(), "finder agreement trace wrong");
        if (i < answer.suffix.size()) current = current.append_common(answer.suffix[i] == '1');
    }
    if (answer.shortest_conditional) {
        require(answer.exact_tail_prefix_length <= answer.suffix.size(), "conditional prefix offset invalid");
        auto base = append(initial, answer.suffix.substr(0, answer.exact_tail_prefix_length));
        auto reference = reference_bfs(base);
        require(reference.found && reference.suffix.size() == answer.exact_tail_suffix.size(), "conditional shortest-tail claim false");
        require(answer.suffix == answer.suffix.substr(0, answer.exact_tail_prefix_length) + answer.exact_tail_suffix,
            "conditional tail not attached to recorded prefix");
    }
    if (answer.shortest_for_initial_pair) {
        auto expected = reference_bfs(initial);
        require(expected.found && expected.suffix.size() == answer.suffix.size(), "initial-pair shortestness claim false");
    }
    return answer;
}

struct DistanceState {
    PairState value;
    bool unknown = false;
    std::uint64_t remaining_count() const { return value.remaining_count(); }
    std::uint64_t mask_count() const { return value.mask_count(); }
    DistanceState append_common(bool letter) const { return {value.append_common(letter), unknown}; }
    std::uint64_t minimum_completion_length() const
    {
        if (unknown) return 0;
        std::uint64_t bound = 0;
        for (const auto& pair : value.pairs) {
            const auto reference = reference_bfs({value.family, {pair}});
            if (!reference.found) return std::numeric_limits<std::uint64_t>::max();
            bound = std::max(bound, static_cast<std::uint64_t>(reference.suffix.size()));
        }
        return bound;
    }
};
void distance_bound_checks()
{
    hardpair::FinderOptions options;
    options.window_k = 4; options.beam_width = 4; options.max_suffix = 4;
    options.tail_threshold = 0; options.max_expansions = 10000;
    for (unsigned int m = 1; m <= 3; ++m) for (const auto& table : classes(m)) {
        auto initial = pair_state(realize(table), "01", "10");
        const auto reference = reference_bfs(initial);
        const bool expected = reference.found && reference.suffix.size() <= options.max_suffix;
        for (const bool remaining_first : {false, true}) for (const bool unknown : {false, true}) {
            options.rank_by_remaining = remaining_first;
            const auto actual = hardpair::find_hard_pair_suffix(DistanceState{initial, unknown}, options,
                [](const DistanceState&, const hardpair::TailLimits&) { return hardpair::TailResult{}; });
            require(actual.found == expected, "admissible bound/ranking changed exhaustive fixed-pair answer");
            if (actual.found) require(append(initial, actual.suffix).remaining_count() == 0,
                "distance-pruned search returned an invalid witness");
            if (unknown) require(!actual.distance_bound_pruned_nodes, "unknown bound pruned a branch");
        }
    }
    const Table plateau{{0,1},{1,2},{0,0}};
    auto initial = pair_state(realize(plateau), "01", "10");
    require(DistanceState{initial}.minimum_completion_length() == 2, "distance lower-bound fixture wrong");
    options.max_suffix = 1;
    auto pruned = hardpair::find_hard_pair_suffix(DistanceState{initial}, options,
        [](const DistanceState&, const hardpair::TailLimits&) { return hardpair::TailResult{}; });
    require(!pruned.found && pruned.distance_bound_checks == 1 && pruned.distance_bound_pruned_nodes == 1
        && !pruned.expanded_nodes, "over-budget initial pair was not safely pruned");
}
struct Improvement { bool found = false; unsigned int route = 0; std::uint64_t seed = 0; int window = -1, tail = -1; };
Improvement tail_improvement_check()
{
    // A pair must read one specific three-letter route to merge. Any wrong
    // letter enters disjoint absorbing sinks. A two-letter window sees no
    // immediate drop; exact BFS from the fixed pair finds the shortest route.
    for (unsigned int route = 0; route < 8; ++route) {
        auto family = std::make_shared<ExplicitFamily>(); DFA dfa; dfa.table.resize(10);
        dfa.root = 9; dfa.table[9] = {0,1};
        dfa.table[2] = {2,2}; dfa.table[3] = {3,3}; dfa.table[8] = {8,8};
        const std::array<std::array<unsigned int,2>,3> levels{{{0,1},{4,5},{6,7}}};
        for (unsigned int level = 0; level < 3; ++level) {
            const auto wanted = (route >> (2-level)) & 1U;
            for (unsigned int side = 0; side < 2; ++side) {
                const auto state = levels[level][side];
                dfa.table[state][1-wanted] = 2+side;
                dfa.table[state][wanted] = level == 2 ? 8 : levels[level+1][side];
            }
        }
        family->automata.push_back(dfa);
        auto initial = pair_state(family,"0","1");
        require(reference_bfs(initial).suffix.size() == 3, "route fixture shortest length wrong");
        for (unsigned int seed = 0; seed < 64; ++seed) {
            hardpair::FinderOptions options; options.window_k=2; options.beam_width=1; options.max_suffix=4;
            options.tail_threshold=0; options.tie_seed=seed;
            auto window = finder(initial, options);
            require(window.tail_calls == 0, "window-only mode unexpectedly ran exact BFS");
            options.tail_threshold=1; options.tail_limits.max_states=100000;
            auto tail = finder(initial, options);
            require(tail.found && tail.suffix.size()==3 && tail.shortest_for_initial_pair, "exact initial tail failed conditional optimum");
            if (!window.found || window.suffix.size()>tail.suffix.size())
                return {true,route,seed,window.found ? int(window.suffix.size()) : -1,int(tail.suffix.size())};
        }
    }
    throw std::runtime_error("no controlled tail-improvement fixture found");
}
void generic_checks()
{
    auto family = heterogeneous(); auto initial = pair_state(family, "0", "1");
    require(initial.remaining_count() == 3, "heterogeneous fixture invalid");
    auto answer = reference_bfs(initial); require(answer.found && answer.suffix.size() == 4, "heterogeneous shortest suffix fixture wrong");
    compare_tail(initial, false); compare_tail(initial, true); compare_distribution(initial, 2); compare_distribution(initial, 4);
    hardpair::FinderOptions options; options.window_k=2; options.beam_width=4; options.max_suffix=16;
    options.tail_threshold=4; options.tail_limits.max_states=100000;
    auto optimized = finder(initial,options);
    require(optimized.found && optimized.suffix.size()==4 && optimized.shortest_for_initial_pair,
        "heterogeneous exact-tail finder not optimal for fixed pair");
    options.tail_threshold=0;
    auto window = finder(initial,options); require(window.found, "heterogeneous window fixture unexpectedly missed");
    hardpair::TailLimits limits; limits.max_states = 1; limits.max_depth = 20;
    auto capped = native_tail(initial, limits);
    require(capped.capped && capped.state_capped && !capped.shortest_conditional, "state cap made an exact claim");
    limits.max_states = 100000; limits.max_depth = 1;
    capped = native_tail(initial, limits);
    require(capped.capped && capped.depth_capped && !capped.shortest_conditional, "depth cap made an exact claim");

    auto permanent = std::make_shared<ExplicitFamily>();
    permanent->automata.push_back({{{0,1},{1,0}},0});
    auto blocked = pair_state(permanent, "0", "1");
    compare_tail(blocked, true); compare_distribution(blocked, 4);
    for (const auto k : {8U, 10U, 12U, 16U})
        compare_distribution(blocked, k, (1ULL << (k + 1)) - 2);
    options.window_k = 16; options.max_suffix = 16; options.max_expansions = 17;
    options.tail_threshold = 0;
    const auto budgeted = finder(blocked, options);
    require(!budgeted.found && budgeted.expansion_limit_reached && budgeted.expanded_nodes == 17
        && !budgeted.shortest_conditional, "large window ignored its explicit node budget");
    bool invalid_window_rejected = false;
    try { hardpair::enumerate_window_distribution(blocked, 17); }
    catch (const std::invalid_argument&) { invalid_window_rejected = true; }
    require(invalid_window_rejected, "unsupported window depth not rejected");
    auto unreachable = native_tail(blocked, hardpair::TailLimits{});
    require(unreachable.unreachable && !unreachable.found && !unreachable.capped && unreachable.states_seen <= 2,
            "global visited failed on permutation loop");

    auto prefix = std::make_shared<ExplicitFamily>();
    prefix->automata.push_back({{{1,2},{1,1},{2,2}},0});
    require(!reference_bfs(pair_state(prefix,"0","1")).found, "prefix cannot-cancel fixture wrong");
    require(reference_bfs(pair_state(prefix,"00","01")).suffix.empty(), "common prefix was incorrectly cancelled");

    const auto limited = hardpair::enumerate_window_distribution(initial, 4, 1);
    require(!limited.complete && limited.expansion_limit_reached, "partial distribution claimed completeness");
    volatile std::sig_atomic_t stopped=1;
    limits.interrupted=&stopped; limits.max_depth=64;
    auto interrupted=native_tail(initial,limits);
    require(interrupted.interrupted && !interrupted.shortest_conditional, "interrupted BFS made an exact claim");
}

} // namespace
int main()
{
    try {
        const auto counts = tiny_family_checks(); generic_checks(); distance_bound_checks(); const auto improvement=tail_improvement_check();
        std::cout << "{\"passed\":true,\"independent_rooted_classes\":" << counts.classes
            << ",\"conditional_bfs_pairs\":" << counts.conditional_pairs << ",\"forced_hash_cases\":" << counts.forced_hash_cases
            << ",\"complete_window_distributions\":" << counts.distributions
            << ",\"heterogeneous_state_counts\":[2,3,5],\"heterogeneous_shortest_conditional_suffix_length\":4"
            << ",\"caps_preserve_incompleteness\":true,\"global_visited_checked\":true,\"common_prefix_cancellation_rejected\":true"
            << ",\"admissible_distance_bounds_and_unknown_checked\":true,\"both_beam_rankings_checked\":true"
            << ",\"tail_improvement\":{\"route_code\":"<<improvement.route<<",\"tie_seed\":"<<improvement.seed
            <<",\"window_only_suffix_length\":"<<improvement.window<<",\"exact_tail_suffix_length\":"<<improvement.tail<<"}}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "HardPairFinderIndependent: " << error.what() << '\n'; return 1;
    }
}

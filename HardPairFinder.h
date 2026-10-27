#pragma once
// Reusable binary-family common-suffix search. No Family 1 types are required.
// Window drops are properties of the supplied family, with no independence
// assumption. Search misses never establish lower bounds on shortest hard pairs.
#include <algorithm>
#include <cmath>
#include <chrono>
#include <csignal>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <numeric>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace hardpair {

struct CoordinatePair {
    std::size_t coordinate;
    std::uint32_t first, second;
};
struct TailLimits {
    std::size_t max_states = 50000;
    unsigned int max_depth = 256;
    bool force_hash_collisions = false;
    const volatile std::sig_atomic_t* interrupted = nullptr;
};
struct TailResult {
    std::string suffix, status = "none";
    bool found = false, shortest_conditional = false, complete = false;
    bool capped = false, depth_capped = false, state_capped = false;
    bool unreachable = false, interrupted = false;
    std::size_t states_seen = 0, expanded_states = 0;
    unsigned int depth_reached = 0;
    double seconds = 0;
};
struct WindowEntry {
    std::string window;
    std::uint64_t remaining_count = 0, drop = 0;
    double normalized_drop = 0;
    bool all_merged = false;
};
struct WindowDistribution {
    unsigned int window_k = 0;
    std::uint64_t initial_remaining = 0, mask_count = 0, expanded_nodes = 0, window_count = 0;
    std::uint64_t min_drop = 0, max_drop = 0, zero_drop_count = 0, full_merge_count = 0;
    double mean_drop = 0, median_drop = 0, variance_drop = 0, stddev_drop = 0;
    bool complete = false, interrupted = false, expansion_limit_reached = false;
    bool normalization_defined = false;
    std::vector<WindowEntry> ranked;
    std::vector<std::pair<std::uint64_t, std::uint64_t>> histogram;
    double seconds = 0;
};
struct FinderOptions {
    unsigned int window_k = 2, beam_width = 4, max_suffix = 64;
    bool rank_by_remaining = false;
    // Enumerate letters in 0,1 order and break every search tie by the suffix
    // itself. This path never derives search order from tie_seed or its hash.
    bool deterministic = false;
    std::uint64_t tail_threshold = 2, max_expansions = 10000, tie_seed = 1088, max_tail_calls = 16;
    TailLimits tail_limits;
    const volatile std::sig_atomic_t* interrupted = nullptr;
    // Optional diagnostic retention only: defaults preserve the complete
    // historical reports. Search decisions never depend on these controls.
    bool retain_ranked_windows = true;
    std::size_t max_window_reports = std::numeric_limits<std::size_t>::max();
};
struct FinderResult {
    std::string suffix, exact_tail_suffix;
    std::vector<std::uint64_t> remaining_trace, score_trace;
    std::uint64_t remaining_count = 0, merged_count = 0, mask_count = 0, permutation_mismatch_count = 0;
    std::uint64_t expanded_nodes = 0, window_blocks = 0, tail_calls = 0, tail_states = 0, replayed_tail_steps = 0;
    std::uint64_t obstruction_checks = 0, obstruction_pruned_nodes = 0;
    std::uint64_t distance_bound_checks = 0, distance_bound_pruned_nodes = 0;
    unsigned int exact_tail_prefix_length = 0;
    bool found = false, all_merged = false, shortest_conditional = false, shortest_for_initial_pair = false;
    bool tail_capped = false, interrupted = false, expansion_limit_reached = false;
    bool proven_obstruction = false;
    std::uint64_t window_reports_truncated = 0;
    TailResult last_tail;
    std::vector<WindowDistribution> window_distributions;
    double seconds = 0;
};

namespace detail {
inline std::uint64_t mix(std::uint64_t x)
{
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}
template<class State> std::uint64_t remaining(const State& state)
{
    if constexpr (requires { state.remaining_count(); }) return state.remaining_count();
    else return state.mask_count() - state.merged_count();
}
template<class State> std::uint64_t obstruction(const State& state)
{
    if constexpr (requires { state.permutation_mismatch_count(); }) return state.permutation_mismatch_count();
    else return 0;
}
inline std::uint64_t pair_code(std::uint32_t a, std::uint32_t b)
{
    if (a == b) return 0; // Absorbing merged marker; state0 is still a valid DFA state.
    if (a > b) std::swap(a, b);
    return (static_cast<std::uint64_t>(a) << 32) | b;
}
inline void summarize(WindowDistribution& report)
{
    report.window_count = report.ranked.size();
    report.normalization_defined = report.initial_remaining != 0;
    report.histogram.clear();
    report.zero_drop_count = report.full_merge_count = 0;
    if (report.ranked.empty()) return;
    std::map<std::uint64_t, std::uint64_t> histogram;
    std::vector<std::uint64_t> drops;
    long double sum = 0;
    for (auto& entry : report.ranked) {
        entry.drop = report.initial_remaining - entry.remaining_count;
        entry.normalized_drop = report.normalization_defined ? static_cast<double>(entry.drop) / report.initial_remaining : 0;
        entry.all_merged = entry.remaining_count == 0;
        ++histogram[entry.drop]; drops.push_back(entry.drop); sum += entry.drop;
        report.zero_drop_count += entry.drop == 0; report.full_merge_count += entry.all_merged;
    }
    std::sort(drops.begin(), drops.end());
    report.min_drop = drops.front(); report.max_drop = drops.back();
    const auto n = drops.size();
    report.mean_drop = static_cast<double>(sum / n);
    report.median_drop = n % 2 ? static_cast<double>(drops[n / 2])
        : (static_cast<long double>(drops[n / 2 - 1]) + drops[n / 2]) / 2;
    long double squares = 0;
    for (auto drop : drops) { const long double difference = drop - sum / n; squares += difference * difference; }
    report.variance_drop = static_cast<double>(squares / n); // Population variance of the complete set, when complete.
    report.stddev_drop = std::sqrt(std::max(0.0, report.variance_drop));
    report.histogram.assign(histogram.begin(), histogram.end());
    std::sort(report.ranked.begin(), report.ranked.end(), [](const auto& a, const auto& b) {
        return a.drop != b.drop ? a.drop > b.drop : a.window < b.window;
    });
}
}

// This is reachability of a fixed pair product, NOT detection of equal-length
// collisions from a DFA root. Global visited states are safe for the former:
// the future from an identical complete pair vector is independent of its depth.
template<class Transition>
TailResult exact_suffix_bfs(const std::vector<CoordinatePair>& coordinates,
                            Transition transition, const TailLimits& limits = {})
{
    if (!limits.max_states) throw std::invalid_argument("exact tail needs a positive state budget");
    const auto started = std::chrono::steady_clock::now();
    TailResult result;
    struct Node { std::vector<std::uint64_t> state; std::size_t parent; bool letter; unsigned int depth; };
    std::vector<CoordinatePair> active;
    std::vector<std::uint64_t> initial;
    for (const auto& coordinate : coordinates) if (coordinate.first != coordinate.second) {
        active.push_back(coordinate); initial.push_back(detail::pair_code(coordinate.first, coordinate.second));
    }
    std::vector<Node> nodes;
    nodes.reserve(std::min<std::size_t>(limits.max_states, 1024));
    constexpr auto root_parent = std::numeric_limits<std::size_t>::max();
    nodes.push_back({std::move(initial), root_parent, false, 0});
    result.states_seen = 1;
    auto finish = [&]() {
        result.capped = result.state_capped || result.depth_capped;
        result.complete = result.found || result.unreachable;
        result.status = result.found ? "found" : result.interrupted ? "interrupted" : result.capped ? "capped" : result.unreachable ? "unreachable" : "none";
        result.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        return result;
    };
    if (active.empty()) { result.found = result.shortest_conditional = true; return finish(); }
    const auto hash = [&](const auto& state) {
        if (limits.force_hash_collisions) return std::uint64_t{0};
        std::uint64_t value = 0x4841524450414952ULL;
        for (auto pair : state) value = detail::mix(value ^ detail::mix(pair));
        return value;
    };
    std::unordered_map<std::uint64_t, std::vector<std::size_t>> buckets;
    buckets[hash(nodes[0].state)].push_back(0);
    for (std::size_t head = 0; head < nodes.size(); ++head) {
        if (limits.interrupted && *limits.interrupted) { result.interrupted = true; return finish(); }
        const auto depth = nodes[head].depth;
        if (depth >= limits.max_depth) { result.depth_capped = true; continue; }
        const auto current = nodes[head].state; // Stable across vector reallocations.
        ++result.expanded_states;
        for (unsigned int letter = 0; letter < 2; ++letter) {
            auto next = current;
            for (std::size_t i = 0; i < next.size(); ++i) if (next[i]) {
                const auto a = static_cast<std::uint32_t>(next[i] >> 32), b = static_cast<std::uint32_t>(next[i]);
                next[i] = detail::pair_code(transition(active[i].coordinate, a, letter != 0), transition(active[i].coordinate, b, letter != 0));
            }
            auto& bucket = buckets[hash(next)];
            bool seen = false;
            for (auto index : bucket) if (nodes[index].state == next) { seen = true; break; }
            if (seen) continue; // Matching hashes ALWAYS compare the complete state vector.
            if (nodes.size() >= limits.max_states) { result.state_capped = true; return finish(); }
            const auto index = nodes.size();
            const bool goal = std::all_of(next.begin(), next.end(), [](auto pair) { return pair == 0; });
            nodes.push_back({std::move(next), head, letter != 0, depth + 1}); bucket.push_back(index);
            result.states_seen = nodes.size(); result.depth_reached = std::max(result.depth_reached, depth + 1);
            if (goal) {
                for (auto at = index; nodes[at].parent != root_parent; at = nodes[at].parent)
                    result.suffix += nodes[at].letter ? '1' : '0';
                std::reverse(result.suffix.begin(), result.suffix.end());
                result.found = result.shortest_conditional = true;
                return finish();
            }
        }
    }
    result.unreachable = !result.depth_capped;
    return finish();
}

template<class State>
WindowDistribution enumerate_window_distribution(const State& initial, unsigned int k,
    std::uint64_t max_expansions = 10000, const volatile std::sig_atomic_t* interrupted = nullptr)
{
    // Depth-first traversal retains only one State per recursion level. The
    // node budget bounds work independently of the opt-in window size.
    if (!k || k > 16) throw std::invalid_argument("window length must be1..16");
    const auto started = std::chrono::steady_clock::now();
    WindowDistribution result;
    result.window_k = k; result.initial_remaining = detail::remaining(initial); result.mask_count = initial.mask_count();
    if (result.initial_remaining > result.mask_count) throw std::logic_error("remaining count exceeds family size");
    auto visit = [&](auto&& self, const State& state, const std::string& word) -> void {
        if (word.size() == k) { result.ranked.push_back({word, detail::remaining(state)}); return; }
        for (unsigned int letter = 0; letter < 2; ++letter) {
            if (interrupted && *interrupted) { result.interrupted = true; return; }
            if (result.expanded_nodes >= max_expansions) { result.expansion_limit_reached = true; return; }
            auto next = state.append_common(letter != 0); ++result.expanded_nodes;
            if (next.mask_count() != result.mask_count || detail::remaining(next) > detail::remaining(state))
                throw std::logic_error("common-letter family count is not monotone");
            self(self, next, word + static_cast<char>('0' + letter));
            if (result.interrupted || result.expansion_limit_reached) return;
        }
    };
    visit(visit, initial, "");
    result.complete = result.ranked.size() == (std::size_t{1} << k);
    detail::summarize(result);
    result.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    return result;
}

// State: remaining_count()/mask_count() (or merged_count()/mask_count()),
// append_common(bool), optional permutation_mismatch_count(), and optional
// has_proven_obstruction(). The latter may return true ONLY for a proven
// impossibility of common-suffix completion; resource-capped/unknown is false.
// ExactTail: callback(const State&, const TailLimits&) -> TailResult.
template<class State, class ExactTail>
FinderResult find_hard_pair_suffix(State initial, const FinderOptions& options, ExactTail exact_tail)
{
    if (!options.window_k || options.window_k > 16 || !options.beam_width || options.beam_width > 64)
        throw std::invalid_argument("finder requires window1..16 and beam1..64");
    const auto started = std::chrono::steady_clock::now();
    FinderResult result;
    result.mask_count = initial.mask_count(); result.remaining_count = detail::remaining(initial);
    if (result.remaining_count > result.mask_count) throw std::logic_error("remaining count exceeds family size");
    result.permutation_mismatch_count = detail::obstruction(initial);
    result.remaining_trace = {result.remaining_count};
    struct Node {
        State state; std::string suffix; std::vector<std::uint64_t> trace;
        std::uint64_t token = 0, drop = 0; std::size_t parent = 0;
    };
    auto best_token = options.deterministic ? std::uint64_t{0} : detail::mix(options.tie_seed);
    const auto blocked = [&](const State& state) {
        if constexpr (requires { state.has_proven_obstruction(); }) {
            ++result.obstruction_checks;
            if (state.has_proven_obstruction()) { ++result.obstruction_pruned_nodes; return true; }
        }
        return false;
    };
    // The optional bound must be admissible for the supplied fixed pair:
    // unknown/capped analyses return0, while a proved obstruction may return
    // UINT64_MAX. Compare by subtraction to avoid overflow in depth+bound.
    const auto beyond_budget = [&](const State& state, std::size_t depth) {
        if constexpr (requires { state.minimum_completion_length(); }) {
            ++result.distance_bound_checks;
            if (state.minimum_completion_length() > options.max_suffix - depth) {
                ++result.distance_bound_pruned_nodes; return true;
            }
        }
        return false;
    };
    auto finish = [&]() {
        result.merged_count = result.mask_count - result.remaining_count;
        result.all_merged = result.found = result.remaining_count == 0;
        result.score_trace.clear();
        for (auto remaining : result.remaining_trace) result.score_trace.push_back(result.mask_count - remaining);
        if (options.interrupted && *options.interrupted) result.interrupted = true;
        result.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        return result;
    };
    auto consider = [&](const Node& node) {
        const auto remaining = detail::remaining(node.state);
        const bool preferred_tie = options.deterministic ? node.suffix < result.suffix : node.token < best_token;
        if (remaining < result.remaining_count || (remaining == result.remaining_count && node.suffix.size() > result.suffix.size())
            || (remaining == result.remaining_count && node.suffix.size() == result.suffix.size() && preferred_tie)) {
            result.remaining_count = remaining; result.suffix = node.suffix; result.remaining_trace = node.trace; best_token = node.token;
        }
    };
    auto try_tail = [&](const Node& node) -> bool {
        const auto remaining = detail::remaining(node.state);
        if (!remaining) return true;
        if (!options.tail_threshold || remaining > options.tail_threshold || result.tail_calls >= options.max_tail_calls) return false;
        auto limits = options.tail_limits;
        limits.max_depth = std::min(limits.max_depth, options.max_suffix - static_cast<unsigned int>(node.suffix.size()));
        if (!limits.interrupted) limits.interrupted = options.interrupted;
        result.last_tail = exact_tail(node.state, limits); ++result.tail_calls;
        result.tail_states += result.last_tail.states_seen; result.tail_capped |= result.last_tail.capped;
        if (result.last_tail.interrupted) { result.interrupted = true; return true; }
        if (!result.last_tail.found) return false;
        if (result.last_tail.suffix.size() > limits.max_depth || result.last_tail.suffix.find_first_not_of("01") != std::string::npos)
            throw std::logic_error("exact-tail callback returned an invalid suffix");
        Node completed = node;
        for (char letter : result.last_tail.suffix) {
            completed.state = completed.state.append_common(letter == '1'); ++result.replayed_tail_steps;
            completed.suffix += letter; completed.trace.push_back(detail::remaining(completed.state));
        }
        if (detail::remaining(completed.state)) throw std::logic_error("exact-tail witness fails family-state replay");
        consider(completed);
        result.shortest_conditional = result.last_tail.shortest_conditional;
        result.exact_tail_prefix_length = static_cast<unsigned int>(node.suffix.size());
        result.exact_tail_suffix = result.last_tail.suffix;
        result.shortest_for_initial_pair = node.suffix.empty() && result.last_tail.shortest_conditional;
        return true;
    };
    if (!result.remaining_count) { result.shortest_conditional = result.shortest_for_initial_pair = true; return finish(); }
    if (result.permutation_mismatch_count || (options.interrupted && *options.interrupted)) return finish();
    if (blocked(initial)) { result.proven_obstruction = true; return finish(); }
    if (beyond_budget(initial, 0)) return finish();
    std::vector<Node> beam;
    beam.push_back({std::move(initial), "", result.remaining_trace, best_token, 0, 0});
    if (try_tail(beam.front())) return finish();
    if (result.tail_calls && result.last_tail.unreachable) return finish();
    auto better = [&](const Node& a, const Node& b) {
        if (options.rank_by_remaining && detail::remaining(a.state) != detail::remaining(b.state))
            return detail::remaining(a.state) < detail::remaining(b.state);
        if (a.drop != b.drop) return a.drop > b.drop;
        if (detail::remaining(a.state) != detail::remaining(b.state)) return detail::remaining(a.state) < detail::remaining(b.state);
        if (options.deterministic)
            return a.suffix != b.suffix ? a.suffix < b.suffix : a.parent < b.parent;
        return a.token != b.token ? a.token < b.token : a.suffix < b.suffix;
    };
    while (!beam.empty() && beam.front().suffix.size() < options.max_suffix) {
        std::vector<Node> pool;
        pool.reserve(options.beam_width);
        std::vector<std::optional<Node>> parent_best(beam.size());
        bool stop = false;
        for (std::size_t parent = 0; parent < beam.size() && !stop; ++parent) {
            const auto& start = beam[parent];
            const auto span = std::min(options.window_k, options.max_suffix - static_cast<unsigned int>(start.suffix.size()));
            WindowDistribution report;
            report.window_k = span; report.initial_remaining = detail::remaining(start.state); report.mask_count = result.mask_count;
            const auto report_start = std::chrono::steady_clock::now();
            auto visit = [&](auto&& self, const Node& node, unsigned int depth, const std::string& block) -> void {
                if (stop) return;
                if (depth == span) {
                    ++result.window_blocks; report.ranked.push_back({block, detail::remaining(node.state)});
                    Node candidate = node; candidate.drop = report.initial_remaining - detail::remaining(node.state); candidate.parent = parent;
                    if (!parent_best[parent] || better(candidate, *parent_best[parent])) parent_best[parent] = candidate;
                    if (pool.size() < options.beam_width) pool.push_back(std::move(candidate));
                    else {
                        std::size_t worst = 0;
                        for (std::size_t i = 1; i < pool.size(); ++i) if (better(pool[worst], pool[i])) worst = i;
                        if (better(candidate, pool[worst])) pool[worst] = std::move(candidate);
                    }
                    return;
                }
                for (unsigned int letter = 0; letter < 2 && !stop; ++letter) {
                    if (options.interrupted && *options.interrupted) { result.interrupted = report.interrupted = stop = true; return; }
                    if (result.expanded_nodes >= options.max_expansions) { result.expansion_limit_reached = report.expansion_limit_reached = stop = true; return; }
                    auto next_state = node.state.append_common(letter != 0); ++result.expanded_nodes; ++report.expanded_nodes;
                    const auto remaining = detail::remaining(next_state);
                    if (next_state.mask_count() != result.mask_count || remaining > detail::remaining(node.state))
                        throw std::logic_error("common-letter family count is not monotone");
                    Node next{std::move(next_state), node.suffix + static_cast<char>('0' + letter), node.trace,
                              options.deterministic ? std::uint64_t{0}
                                  : detail::mix(node.token ^ (0xd1b54a32d192ed03ULL + letter)), 0, parent};
                    next.trace.push_back(remaining);
                    if (remaining && blocked(next.state)) continue;
                    if (remaining && beyond_budget(next.state, next.suffix.size())) continue;
                    consider(next);
                    if (!remaining) { stop = true; return; }
                    const auto previous_tail_calls = result.tail_calls;
                    if (try_tail(next)) { stop = true; return; }
                    if (result.tail_calls != previous_tail_calls && result.last_tail.unreachable) continue;
                    self(self, next, depth + 1, block + static_cast<char>('0' + letter));
                }
            };
            visit(visit, start, 0, "");
            report.complete = report.ranked.size() == (std::size_t{1} << span);
            detail::summarize(report);
            report.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - report_start).count();
            if (!options.retain_ranked_windows) std::vector<WindowEntry>().swap(report.ranked);
            if (!options.max_window_reports) ++result.window_reports_truncated;
            else {
                if (result.window_distributions.size() == options.max_window_reports) {
                    result.window_distributions.erase(result.window_distributions.begin());
                    ++result.window_reports_truncated;
                }
                result.window_distributions.push_back(std::move(report));
            }
        }
        if (stop) return finish();
        if (pool.empty()) break;
        std::sort(pool.begin(), pool.end(), better);
        // On a flat layer keep representatives of distinct parents first;
        // otherwise favor the strongest actual window drops.
        const bool flat = std::all_of(pool.begin(), pool.end(), [](const auto& node) { return node.drop == 0; });
        std::vector<Node> next;
        next.reserve(options.beam_width);
        auto add_distinct = [&](const Node& node) {
            if (next.size() >= options.beam_width) return;
            if (std::none_of(next.begin(), next.end(), [&](const auto& existing) { return existing.suffix == node.suffix; })) next.push_back(node);
        };
        if (flat) for (const auto& node : parent_best) if (node) add_distinct(*node);
        for (const auto& node : pool) add_distinct(node);
        if (!flat && next.size() >= 2) {
            const Node* absolute = nullptr;
            for (const auto& node : parent_best) if (node && (!absolute
                || detail::remaining(node->state) < detail::remaining(absolute->state)
                || (options.deterministic && detail::remaining(node->state) == detail::remaining(absolute->state)
                    && node->suffix < absolute->suffix))) absolute = &*node;
            if (absolute && std::none_of(next.begin(), next.end(), [&](const auto& node) { return node.suffix == absolute->suffix; })) next.back() = *absolute;
        }
        beam = std::move(next);
    }
    return finish();
}

template<class State>
FinderResult find_hard_pair_suffix(State initial, FinderOptions options = {})
{
    options.tail_threshold = 0;
    return find_hard_pair_suffix(std::move(initial), options, [](const auto&, const TailLimits&) { return TailResult{}; });
}

}

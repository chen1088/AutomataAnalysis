#pragma once
// Deterministic lookahead for pairs of binary words. The alphabet is the four
// ORDERED pairs 00,01,10,11: agreement can be lost at any later joint step.
// Every state must retain every coordinate, including currently equal ones.
// A positive result is an upper witness; beam retention never proves a minimum.
#include <algorithm>
#include <csignal>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace hardpair::joint {

struct Options {
    unsigned int window_k = 3, beam_width = 8, diagonal_width = 1, max_length = 64;
    // Optional additional endpoints reached using 01 or 10 somewhere in the
    // CURRENT window. They supplement the ordinary minimum-D beam.
    unsigned int unequal_width = 0;
    // Experimental ranking only: first minimize mismatches in a supplied
    // permutation-DFA subset, then total D. Success still requires total D=0.
    bool prioritize_permutation = false;
    std::uint64_t max_expansions = 1000000;
    // Diagnostics do not influence branch selection. Zero disables traces.
    unsigned int max_trace_records = 64;
    // Checked between complete windows. A started window always finishes.
    const volatile std::sig_atomic_t* interrupted = nullptr;
};

struct Window {
    unsigned int span = 0;
    std::uint64_t expected_leaves = 0, leaves = 0, nodes = 0;
    bool complete = false;
};

// One completed or interrupted block-greedy round. D always counts unequal
// endpoint coordinates. Identical input words have D=0 but are not witnesses.
struct RoundTrace {
    unsigned int round = 0, parent_depth = 0, span = 0, endpoint_depth = 0;
    std::uint64_t parent_count = 0, parents_expanded = 0;
    std::uint64_t min_parent_remaining = 0, max_parent_remaining = 0;
    std::uint64_t min_parent_priority_remaining = 0, max_parent_priority_remaining = 0;
    bool has_divergent_leaf = false, has_unequal_leaf = false;
    std::uint64_t min_divergent_leaf_remaining = 0, min_unequal_leaf_remaining = 0;
    std::uint64_t min_divergent_leaf_priority_remaining = 0;
    std::uint64_t divergent_leaves = 0, unequal_leaves = 0;
    std::uint64_t retained_count = 0, min_retained_remaining = 0, max_retained_remaining = 0;
    std::uint64_t min_retained_priority_remaining = 0, max_retained_priority_remaining = 0;
    std::string selected_first, selected_second;
    std::uint64_t selected_remaining = 0;
    std::uint64_t selected_priority_remaining = 0;
    bool positive_found = false, stopped = false;
    unsigned int positive_length = 0;
};

struct Result {
    bool found = false;
    std::string first, second;
    unsigned int length = 0, window_k = 0, beam_width = 0, diagonal_width = 0, max_length = 0;
    unsigned int unequal_width = 0;
    unsigned int maximum_depth_visited = 0;
    std::uint64_t mask_count = 0, expansion_cap = 0, expanded_nodes = 0;
    std::uint64_t complete_windows = 0, partial_windows = 0, windows_refused = 0;
    std::uint64_t visited_leaves = 0, divergent_leaves = 0, diagonal_leaves = 0, rounds = 0;
    std::uint64_t equivalent_leaves = 0;
    std::uint64_t unequal_leaves = 0, cross_pool_equivalent_leaves = 0;
    bool expansion_limit_reached = false, length_limit_reached = false;
    bool beam_truncated = false, interrupted = false, capped = false;
    // Deliberately conservative even when the first root window is exhaustive.
    bool minimality_certified = false;
    // first_greedy_depth is the endpoint of the first fully enumerated window
    // (zero if no window fits the work budget), even if that window finds a
    // witness before a next beam needs to be committed.
    unsigned int initial_length = 0, first_greedy_depth = 0;
    std::uint64_t initial_remaining = 0;
    bool initial_distinct = false;
    bool prioritize_permutation = false;
    std::string rank_policy = "total-disagreement";
    std::uint64_t initial_priority_remaining = 0;
    std::uint64_t trace_records_truncated = 0;
    std::vector<Window> windows;
    std::vector<RoundTrace> round_trace;
};

template<class State>
struct DivergenceStart {
    State state;
    std::string common_prefix;
    unsigned int first_difference_depth = 0; // One-based joint-symbol position.
    std::string orientation; // Exactly "01" or "10"; neither is discarded.
};

template<class State>
struct DivergenceStartPlan {
    std::vector<DivergenceStart<State>> starts;
    unsigned int common_depth = 0;
    std::uint64_t common_prefix_count = 0, expected_starts = 0;
    bool complete = false;
};

// Enumerate every possible first difference after every common binary prefix
// of length 0..common_depth. Each returned state is an INDEPENDENT find_pair
// attempt: its first comparison follows k full joint steps AFTER the forced
// difference, unless max_length permits only a shorter final window. Never
// rank prefixes with different first-difference ages
// against one another using D. The caller must run every start to describe the
// configured startup set as exhaustive. No score, PRNG or profile deduplication
// changes the configured set, even when different prefixes reach equal states.
template<class State>
DivergenceStartPlan<State> divergence_starts(const State& initial, unsigned int common_depth)
{
    if (common_depth > 8)
        throw std::invalid_argument("divergence startup requires common depth 0..8");
    if (!initial.first_word().empty() || !initial.second_word().empty() || initial.distinct())
        throw std::invalid_argument("divergence startup requires the empty identical-word state");
    if (initial.remaining_count())
        throw std::logic_error("empty joint words have unequal complete coordinate profiles");
    DivergenceStartPlan<State> result;
    result.common_depth = common_depth;
    result.common_prefix_count = (std::uint64_t{1} << (common_depth + 1)) - 1;
    result.expected_starts = 2 * result.common_prefix_count;
    result.starts.reserve(static_cast<std::size_t>(result.expected_starts));
    std::vector<State> layer{initial};
    for (unsigned int depth = 0; depth <= common_depth; ++depth) {
        std::vector<State> next;
        if (depth < common_depth) next.reserve(2 * layer.size());
        for (const auto& state : layer) {
            result.starts.push_back({state.append_pair(false, true), state.first_word(), depth + 1, "01"});
            result.starts.push_back({state.append_pair(true, false), state.first_word(), depth + 1, "10"});
            if (depth < common_depth) {
                next.push_back(state.append_pair(false, false));
                next.push_back(state.append_pair(true, true));
            }
        }
        layer = std::move(next);
    }
    result.complete = result.starts.size() == result.expected_starts;
    if (!result.complete) throw std::logic_error("divergence startup lost a configured prefix");
    return result;
}

// State is copyable and provides append_pair(bool,bool), remaining_count(),
// mask_count(), distinct(), and first_word()/second_word(). All coordinates
// must survive append_pair; D is neither monotone nor an admissible depth bound.
template<class State>
Result find_pair(State initial, const Options& options = {})
{
    if (!options.window_k || options.window_k > 16 || !options.beam_width
        || options.beam_width > 4096 || options.diagonal_width > 4096 || options.unequal_width > 4096
        || options.max_trace_records > 4096
        || !options.max_length || options.max_length > 4096 || !options.max_expansions)
        throw std::invalid_argument("joint finder requires k1..16, beam1..4096, diagonal/unequal/trace0..4096, length1..4096 and positive expansions");
    Result result;
    result.window_k = options.window_k; result.beam_width = options.beam_width;
    result.diagonal_width = options.diagonal_width; result.max_length = options.max_length;
    result.unequal_width = options.unequal_width;
    result.prioritize_permutation = options.prioritize_permutation;
    if (options.prioritize_permutation) result.rank_policy = "permutation-disagreement-then-total";
    result.expansion_cap = options.max_expansions; result.mask_count = initial.mask_count();
    if (!result.mask_count) throw std::invalid_argument("joint finder requires a nonempty coordinate family");
    struct Node {
        State state;
        std::uint64_t remaining;
        bool distinct;
        std::uint64_t priority = 0;
    };
    const auto priority_value = [&](const State& state) -> std::uint64_t {
        if (!options.prioritize_permutation) return 0; // No priority accessor calls when disabled.
        if constexpr (requires { state.priority_remaining_count(); }) {
            const auto value = static_cast<std::uint64_t>(state.priority_remaining_count());
            if (value > state.remaining_count())
                throw std::logic_error("joint priority disagreements exceed total disagreements");
            return value;
        } else {
            throw std::invalid_argument("permutation-first ranking requires State.priority_remaining_count()");
        }
    };
    const auto inspect = [&](const State& state, std::size_t expected_length) {
        if (state.first_word().size() != expected_length || state.second_word().size() != expected_length
            || state.mask_count() != result.mask_count || state.remaining_count() > result.mask_count
            || state.distinct() != (state.first_word() != state.second_word()))
            throw std::logic_error("joint state has invalid lengths, coordinate count or word-distinctness flag");
        if (!state.distinct() && state.remaining_count())
            throw std::logic_error("identical words have unequal complete coordinate profiles");
    };
    const auto initial_length = initial.first_word().size();
    if (initial_length > options.max_length)
        throw std::invalid_argument("initial joint words exceed the maximum pair length");
    inspect(initial, initial_length);
    result.initial_length = static_cast<unsigned int>(initial_length);
    result.initial_remaining = initial.remaining_count(); result.initial_distinct = initial.distinct();
    result.initial_priority_remaining = priority_value(initial);
    result.maximum_depth_visited = static_cast<unsigned int>(initial_length);
    const auto words_before = [](const auto& a, const auto& b) {
        const auto& first_a = a.first_word(); const auto& first_b = b.first_word();
        return first_a != first_b ? first_a < first_b : a.second_word() < b.second_word();
    };
    const auto better = [&](const Node& a, const Node& b) {
        if (a.priority != b.priority) return a.priority < b.priority;
        return a.remaining != b.remaining ? a.remaining < b.remaining : words_before(a.state, b.state);
    };
    const auto consider = [&](const Node& node) {
        if (!node.distinct || node.remaining) return;
        const auto length = static_cast<unsigned int>(node.state.first_word().size());
        if (!result.found || length < result.length || (length == result.length
            && (node.state.first_word() < result.first || (node.state.first_word() == result.first
                && node.state.second_word() < result.second)))) {
            result.found = true; result.length = length;
            result.first = node.state.first_word(); result.second = node.state.second_word();
        }
    };
    const auto finish = [&]() {
        result.length_limit_reached = result.maximum_depth_visited == options.max_length;
        result.capped = result.expansion_limit_reached || result.length_limit_reached || result.interrupted;
        return result;
    };
    Node root{std::move(initial), 0, false};
    root.remaining = root.state.remaining_count(); root.distinct = root.state.distinct();
    root.priority = result.initial_priority_remaining;
    consider(root);
    if (result.found) return finish();
    std::vector<Node> beam;
    beam.push_back(std::move(root));
    while (!beam.empty() && beam.front().state.first_word().size() < options.max_length) {
        ++result.rounds;
        RoundTrace trace;
        trace.round = static_cast<unsigned int>(result.rounds);
        trace.parent_depth = static_cast<unsigned int>(beam.front().state.first_word().size());
        trace.span = std::min(options.window_k, options.max_length - trace.parent_depth);
        trace.endpoint_depth = trace.parent_depth + trace.span;
        trace.parent_count = beam.size();
        trace.min_parent_remaining = trace.max_parent_remaining = beam.front().remaining;
        trace.min_parent_priority_remaining = trace.max_parent_priority_remaining = beam.front().priority;
        for (const auto& parent : beam) {
            trace.min_parent_remaining = std::min(trace.min_parent_remaining, parent.remaining);
            trace.max_parent_remaining = std::max(trace.max_parent_remaining, parent.remaining);
            trace.min_parent_priority_remaining = std::min(trace.min_parent_priority_remaining, parent.priority);
            trace.max_parent_priority_remaining = std::max(trace.max_parent_priority_remaining, parent.priority);
        }
        const auto record_trace = [&]() {
            trace.positive_found = result.found; trace.stopped = result.interrupted || result.expansion_limit_reached;
            trace.positive_length = result.found ? result.length : 0;
            if (result.round_trace.size() < options.max_trace_records) result.round_trace.push_back(std::move(trace));
            else ++result.trace_records_truncated;
        };
        std::vector<Node> divergent, diagonal, unequal;
        divergent.reserve(options.beam_width); diagonal.reserve(options.diagonal_width);
        unequal.reserve(options.unequal_width);
        const auto retain = [&](std::vector<Node>& pool, unsigned int limit, const Node& node) {
            if (!limit) { result.beam_truncated = true; return; }
            // At this SAME depth, equivalent ordered full profiles plus the
            // distinct-word flag have exactly the same future joint moves.
            // Optional equality may ignore the actual word strings, retaining
            // their lexically smallest representative. Never deduplicate over
            // depths, or by disagreement count/hash alone.
            if constexpr (requires { static_cast<bool>(node.state == node.state); }) {
                for (auto& existing : pool) if (existing.remaining == node.remaining
                    && existing.priority == node.priority
                    && existing.distinct == node.distinct && existing.state == node.state) {
                    ++result.equivalent_leaves;
                    if (words_before(node.state, existing.state)) {
                        existing = node; std::make_heap(pool.begin(), pool.end(), better);
                    }
                    return;
                }
            }
            // better is an ascending ranking, so the heap front is its worst
            // retained leaf. The complete incoming window is still enumerated.
            if (pool.size() < limit) {
                pool.push_back(node); std::push_heap(pool.begin(), pool.end(), better);
            } else {
                result.beam_truncated = true;
                if (better(node, pool.front())) {
                    std::pop_heap(pool.begin(), pool.end(), better);
                    pool.back() = node; std::push_heap(pool.begin(), pool.end(), better);
                }
            }
        };
        bool stop = false;
        for (const auto& parent : beam) {
            if (options.interrupted && *options.interrupted) { result.interrupted = stop = true; break; }
            Window window;
            window.span = std::min(options.window_k,
                options.max_length - static_cast<unsigned int>(parent.state.first_word().size()));
            std::uint64_t level = 1, required_nodes = 0;
            for (unsigned int depth = 0; depth < window.span; ++depth) {
                level *= 4; required_nodes += level;
            }
            window.expected_leaves = level;
            // The expansion cap never truncates a window or pretends a
            // smaller visited alphabet supplied a complete k-step comparison.
            if (required_nodes > options.max_expansions - result.expanded_nodes) {
                result.expansion_limit_reached = stop = true; ++result.windows_refused; break;
            }
            auto visit = [&](auto&& self, const Node& node, unsigned int depth, bool window_unequal) -> void {
                if (depth == window.span) {
                    ++window.leaves; ++result.visited_leaves;
                    if (node.distinct) {
                        if (!trace.has_divergent_leaf || node.priority < trace.min_divergent_leaf_priority_remaining)
                            trace.min_divergent_leaf_priority_remaining = node.priority;
                        if (!trace.has_divergent_leaf || node.remaining < trace.min_divergent_leaf_remaining)
                            trace.min_divergent_leaf_remaining = node.remaining;
                        trace.has_divergent_leaf = true; ++trace.divergent_leaves;
                    }
                    if (node.distinct) { ++result.divergent_leaves; retain(divergent, options.beam_width, node); }
                    else { ++result.diagonal_leaves; retain(diagonal, options.diagonal_width, node); }
                    if (window_unequal) {
                        if (!trace.has_unequal_leaf || node.remaining < trace.min_unequal_leaf_remaining)
                            trace.min_unequal_leaf_remaining = node.remaining;
                        trace.has_unequal_leaf = true; ++trace.unequal_leaves;
                        ++result.unequal_leaves;
                        if (options.unequal_width) retain(unequal, options.unequal_width, node);
                    }
                    return;
                }
                // Do not identify 01 with 10: their ordered full profiles
                // may have different later joint continuations.
                for (unsigned int symbol = 0; symbol < 4; ++symbol) {
                    State state = node.state.append_pair((symbol & 2U) != 0, (symbol & 1U) != 0);
                    ++window.nodes; ++result.expanded_nodes;
                    const auto length = node.state.first_word().size() + 1;
                    inspect(state, length);
                    Node next{std::move(state), 0, false};
                    next.remaining = next.state.remaining_count(); next.distinct = next.state.distinct();
                    next.priority = priority_value(next.state);
                    result.maximum_depth_visited = std::max(result.maximum_depth_visited,
                        static_cast<unsigned int>(length));
                    consider(next); // Include positives before the window's final depth.
                    self(self, next, depth + 1, window_unequal || symbol == 1 || symbol == 2);
                }
            };
            visit(visit, parent, 0, false);
            window.complete = window.leaves == window.expected_leaves && window.nodes == required_nodes;
            if (!window.complete) throw std::logic_error("joint window traversal lost a joint symbol");
            ++result.complete_windows; result.windows.push_back(window);
            ++trace.parents_expanded;
        }
        // A complete round visits every retained parent through its full
        // window. Any next round starts after every positive length just seen.
        if (trace.parents_expanded && !result.first_greedy_depth)
            result.first_greedy_depth = trace.endpoint_depth;
        if (result.found || stop) { record_trace(); return finish(); }
        std::sort(divergent.begin(), divergent.end(), better);
        std::sort(unequal.begin(), unequal.end(), better);
        std::sort(diagonal.begin(), diagonal.end(), better);
        beam.clear();
        const auto assemble = [&](Node node) {
            for (auto& existing : beam) {
                bool same = false;
                if (existing.remaining == node.remaining && existing.priority == node.priority
                    && existing.distinct == node.distinct) {
                    if constexpr (requires { static_cast<bool>(existing.state == node.state); })
                        same = existing.state == node.state;
                    else same = existing.state.first_word() == node.state.first_word()
                        && existing.state.second_word() == node.state.second_word();
                }
                if (same) {
                    ++result.cross_pool_equivalent_leaves;
                    if (words_before(node.state, existing.state)) existing = std::move(node);
                    return;
                }
            }
            beam.push_back(std::move(node));
        };
        // Preserve the ordinary beam and its ordering. Mixed-symbol endpoints
        // are additional opportunities, never a restriction on every path.
        for (auto& node : divergent) assemble(std::move(node));
        for (auto& node : unequal) assemble(std::move(node));
        for (auto& node : diagonal) assemble(std::move(node));
        trace.retained_count = beam.size();
        if (!beam.empty()) {
            trace.min_retained_remaining = trace.max_retained_remaining = beam.front().remaining;
            trace.min_retained_priority_remaining = trace.max_retained_priority_remaining = beam.front().priority;
            for (const auto& node : beam) {
                trace.min_retained_remaining = std::min(trace.min_retained_remaining, node.remaining);
                trace.max_retained_remaining = std::max(trace.max_retained_remaining, node.remaining);
                trace.min_retained_priority_remaining = std::min(trace.min_retained_priority_remaining, node.priority);
                trace.max_retained_priority_remaining = std::max(trace.max_retained_priority_remaining, node.priority);
            }
            trace.selected_first = beam.front().state.first_word();
            trace.selected_second = beam.front().state.second_word();
            trace.selected_remaining = beam.front().remaining;
            trace.selected_priority_remaining = beam.front().priority;
        }
        record_trace();
    }
    return finish();
}

} // namespace hardpair::joint

#include "HardPairJointFinder.h"
#include <array>
#include <iostream>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {
void require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
}

struct Dfa {
    std::vector<std::array<unsigned int, 2>> table;
    unsigned int root = 0;
};
struct Fixture {
    std::vector<Dfa> dfas;
    std::set<std::pair<std::string, std::string>> appended;
};

// A scalar adapter independent of the packed Family 1 implementation. Its
// append log makes the exact four-symbol window coverage directly observable.
struct State {
    std::shared_ptr<Fixture> fixture;
    std::vector<unsigned int> left, right;
    std::string first, second;

    explicit State(std::shared_ptr<Fixture> value) : fixture(std::move(value))
    {
        for (const auto& dfa : fixture->dfas) { left.push_back(dfa.root); right.push_back(dfa.root); }
    }
    State append_pair(bool a, bool b) const
    {
        State next = *this;
        next.first += a ? '1' : '0'; next.second += b ? '1' : '0';
        for (std::size_t i = 0; i < left.size(); ++i) {
            next.left[i] = fixture->dfas[i].table[left[i]][a];
            next.right[i] = fixture->dfas[i].table[right[i]][b];
        }
        fixture->appended.emplace(next.first, next.second);
        return next;
    }
    std::uint64_t remaining_count() const
    {
        std::uint64_t result = 0;
        for (std::size_t i = 0; i < left.size(); ++i) result += left[i] != right[i];
        return result;
    }
    std::uint64_t mask_count() const { return fixture->dfas.size(); }
    bool distinct() const { return first != second; }
    const std::string& first_word() const { return first; }
    const std::string& second_word() const { return second; }
    bool operator==(const State& other) const
    {
        return fixture == other.fixture && left == other.left && right == other.right
            && distinct() == other.distinct();
    }
};

std::shared_ptr<Fixture> fixture()
{
    // Both input maps are permutations; the second DFA has a nonzero root.
    return std::make_shared<Fixture>(Fixture{{
        {{{1, 0}, {0, 1}}, 0},
        {{{1, 2}, {2, 0}, {0, 1}}, 2}
    }, {}});
}

void startup_set_is_exhaustive()
{
    State initial(fixture());
    require(initial.remaining_count() == 0 && !initial.distinct(), "empty D must be zero");
    for (unsigned int c = 0; c <= 8; ++c) {
        const auto plan = hardpair::joint::divergence_starts(initial, c);
        const std::uint64_t prefixes = (std::uint64_t{1} << (c + 1)) - 1;
        require(plan.complete && plan.common_depth == c && plan.common_prefix_count == prefixes,
                "startup metadata does not cover the full prefix tree");
        require(plan.expected_starts == 2 * prefixes && plan.starts.size() == 2 * prefixes,
                "startup lost an orientation or a prefix");
        std::set<std::pair<std::string, std::string>> actual;
        unsigned int previous_depth = 0;
        std::string previous_prefix;
        for (std::size_t i = 0; i < plan.starts.size(); ++i) {
            const auto& start = plan.starts[i];
            const auto depth = static_cast<unsigned int>(start.common_prefix.size());
            require(depth <= c && start.first_difference_depth == depth + 1,
                    "first difference position is wrong");
            require(start.orientation == (i % 2 ? "10" : "01"), "orientation order is wrong");
            require(start.state.first == start.common_prefix + start.orientation[0]
                    && start.state.second == start.common_prefix + start.orientation[1],
                    "startup words do not have their declared first difference");
            require(start.state.distinct(), "startup retained an identical word pair");
            require(depth >= previous_depth, "common prefixes are not in length order");
            if (depth == previous_depth && i % 2 == 0)
                require(previous_prefix <= start.common_prefix, "common prefixes are not in lexical order");
            previous_depth = depth; previous_prefix = start.common_prefix;
            require(actual.emplace(start.state.first, start.state.second).second, "startup duplicated a word pair");
        }
        std::vector<std::string> layer{""};
        for (unsigned int depth = 0; depth <= c; ++depth) {
            std::vector<std::string> next;
            for (const auto& prefix : layer) {
                require(actual.contains({prefix + '0', prefix + '1'})
                        && actual.contains({prefix + '1', prefix + '0'}), "explicit prefix/orientation is absent");
                next.push_back(prefix + '0'); next.push_back(prefix + '1');
            }
            layer = std::move(next);
        }
    }
    bool rejected = false;
    try { (void)hardpair::joint::divergence_starts(initial, 9); }
    catch (const std::invalid_argument&) { rejected = true; }
    require(rejected, "startup accepted unsupported common depth");
    rejected = false;
    try { (void)hardpair::joint::divergence_starts(initial.append_pair(false, false), 0); }
    catch (const std::invalid_argument&) { rejected = true; }
    require(rejected, "startup accepted a nonempty initial pair");
}

void first_greedy_round_is_after_divergence_plus_k()
{
    auto data = fixture(); State initial(data);
    const auto plan = hardpair::joint::divergence_starts(initial, 2);
    hardpair::joint::Options options;
    options.window_k = 2; options.beam_width = 1; options.diagonal_width = 0;
    options.max_length = 5; options.max_expansions = 20;
    for (const auto& start : plan.starts) {
        data->appended.clear();
        const auto result = hardpair::joint::find_pair(start.state, options);
        require(result.initial_distinct && result.initial_length == start.first_difference_depth
                && result.initial_remaining == start.state.remaining_count(), "initial trace is wrong");
        if (!result.initial_remaining) {
            require(result.found && result.length == result.initial_length && !result.expanded_nodes,
                    "an initial hard pair was not inspected before the first window");
            continue;
        }
        require(result.complete_windows == 1 && result.partial_windows == 0
                && result.expanded_nodes == 20 && result.visited_leaves == 16,
                "first startup window was not a complete four-ary k=2 tree");
        require(result.first_greedy_depth == start.first_difference_depth + options.window_k,
                "D-based selection did not wait until first difference plus k");
        require(result.round_trace.size() >= 1, "first greedy round trace is absent");
        const auto& trace = result.round_trace.front();
        require(trace.parent_depth == start.first_difference_depth && trace.span == 2
                && trace.endpoint_depth == start.first_difference_depth + 2
                && trace.parents_expanded == 1 && trace.parent_count == 1
                && trace.divergent_leaves == 16, "first greedy round trace is inconsistent");
        // Explicitly require every suffix pair, independently of node counters.
        for (unsigned int a = 0; a < 4; ++a) for (unsigned int b = 0; b < 4; ++b) {
            std::string first = start.state.first, second = start.state.second;
            for (unsigned int symbol : {a, b}) {
                first += symbol & 2U ? '1' : '0'; second += symbol & 1U ? '1' : '0';
            }
            require(data->appended.contains({first, second}), "first greedy window missed a joint suffix");
        }
    }
}

void diagnostics_do_not_change_search()
{
    auto data = fixture(); State initial(data);
    hardpair::joint::Options options;
    options.window_k = 1; options.beam_width = 1; options.diagonal_width = 0;
    options.max_length = 7; options.max_expansions = 100;
    auto first = hardpair::joint::find_pair(initial, options);
    options.max_trace_records = 0;
    const auto disabled = hardpair::joint::find_pair(initial, options);
    require(first.found == disabled.found && first.first == disabled.first && first.second == disabled.second
            && first.expanded_nodes == disabled.expanded_nodes && first.complete_windows == disabled.complete_windows
            && first.equivalent_leaves == disabled.equivalent_leaves, "tracing changed branch selection");
    require(disabled.round_trace.empty() && disabled.trace_records_truncated == disabled.rounds,
            "disabled trace metadata is wrong");
    options.max_trace_records = 1;
    const auto limited = hardpair::joint::find_pair(initial, options);
    require(limited.round_trace.size() == 1 && limited.trace_records_truncated + 1 == limited.rounds,
            "trace record cap did not preserve the exact omitted count");
    require(first.initial_length == 0 && first.initial_remaining == 0 && !first.initial_distinct,
            "empty startup trace did not preserve D=0");

    options.window_k = 2; options.max_expansions = 19; options.max_trace_records = 64;
    const auto refused = hardpair::joint::find_pair(initial, options);
    require(refused.expanded_nodes == 0 && refused.windows_refused == 1
            && refused.expansion_limit_reached && refused.first_greedy_depth == 0,
            "budget truncation was incorrectly reported as a greedy comparison");
    require(refused.round_trace.size() == 1 && refused.round_trace[0].parents_expanded == 0
            && refused.round_trace[0].stopped, "refused window trace is wrong");
}

void initial_positive_is_distinct_and_needs_no_window()
{
    auto data = std::make_shared<Fixture>(Fixture{{{{{0, 0}}, 0}}, {}});
    State initial(data);
    const auto plan = hardpair::joint::divergence_starts(initial, 2);
    hardpair::joint::Options options;
    options.window_k = 2; options.beam_width = 1; options.diagonal_width = 0;
    options.max_length = 5; options.max_expansions = 1;
    for (const auto& start : plan.starts) {
        const auto result = hardpair::joint::find_pair(start.state, options);
        require(result.found && result.length == start.first_difference_depth
                && result.first == start.state.first && result.second == start.state.second
                && result.initial_distinct && result.initial_remaining == 0
                && !result.expanded_nodes && result.round_trace.empty(),
                "a distinct D=0 startup pair was not accepted without a window");
    }
    const auto identical = hardpair::joint::find_pair(initial, options);
    require(!identical.found && identical.initial_remaining == 0 && !identical.initial_distinct,
            "the empty identical D=0 pair was accepted as a witness");
}
} // namespace

int main()
{
    try {
        startup_set_is_exhaustive();
        first_greedy_round_is_after_divergence_plus_k();
        diagnostics_do_not_change_search();
        initial_positive_is_distinct_and_needs_no_window();
        std::cout << "joint startup tests passed (joint k=1,2; complete common-prefix depths c=0..8)\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}

#include "Family1JointPair.h"
#include "HardPairJointFinder.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace {
void require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
}

unsigned int endpoint(const family1::LargeGraph& graph, unsigned int mask, const std::string& word)
{
    unsigned int state = 0;
    for (const char letter : word)
        state = graph.ports[state][static_cast<unsigned int>(letter - '0') ^ ((mask >> state) & 1U)];
    return state;
}

// Independent scalar bijectivity check. This uses neither PairAgreementContext
// nor any compressed packed-product mask bookkeeping.
bool permutation(const family1::LargeGraph& graph, unsigned int mask)
{
    for (unsigned int letter = 0; letter < 2; ++letter) {
        std::vector<bool> seen(graph.size());
        for (unsigned int state = 0; state < graph.size(); ++state) {
            const auto target = graph.ports[state][letter ^ ((mask >> state) & 1U)];
            if (seen[target]) return false;
            seen[target] = true;
        }
    }
    return true;
}

struct Counts { std::uint64_t total = 0, priority = 0, zero_class = 0; };
Counts scalar_counts(const family1::LargeGraph& graph, const std::vector<bool>& selected,
                     const std::string& first, const std::string& second)
{
    Counts result;
    unsigned int active_bits = 0;
    for (unsigned int state = 0; state < graph.size(); ++state)
        if (graph.ports[state][0] != graph.ports[state][1]) active_bits |= 1U << state;
    for (unsigned int mask = 0; mask < selected.size(); ++mask) {
        const bool different = endpoint(graph, mask, first) != endpoint(graph, mask, second);
        result.total += different; result.priority += different && selected[mask];
        result.zero_class += different && !(mask & active_bits);
    }
    return result;
}

std::uint64_t states_checked = 0, scalar_masks_checked = 0;
void check_graph(const family1::LargeGraph& graph)
{
    auto product = std::make_shared<family1::ExactPackedProduct>(graph);
    const auto selection = family1::permutation_priority_selection(product, graph);
    std::vector<bool> selected(1U << graph.size());
    std::uint64_t selected_count = 0;
    for (unsigned int mask = 0; mask < selected.size(); ++mask) {
        selected[mask] = permutation(graph, mask); selected_count += selected[mask];
    }
    require(selection->selected_count() == selected_count, "permutation selector differs from scalar bijectivity");
    const auto zero_class = product->select_mask_classes({0, 0}); // Duplicate representatives do not add weight.
    unsigned int omitted_bits = 0;
    for (const auto& row : graph.ports) omitted_bits += row[0] == row[1];
    require(zero_class.selected_count() == (std::uint64_t{1} << omitted_bits),
            "coincident-port mask-class multiplicity is wrong");
    family1::JointPairState initial(product, graph.size(), selection);
    const auto visit = [&](auto&& self, const family1::JointPairState& state, unsigned int depth) -> void {
        const auto expected = scalar_counts(graph, selected, state.first_word(), state.second_word());
        require(state.remaining_count() == expected.total && state.priority_remaining_count() == expected.priority,
                "joint total/priority mismatch count differs from scalar replay");
        require(state.priority_mask_count() == selected_count, "joint priority family size changed");
        require(product->disagreement_count(state.left_profile(), state.right_profile(), zero_class) == expected.zero_class,
                "selected packed disagreements lost coincident-port multiplicity");
        for (unsigned int mask = 0; mask < selected.size(); ++mask) {
            require(product->endpoint(state.left_profile(), mask) == endpoint(graph, mask, state.first_word())
                    && product->endpoint(state.right_profile(), mask) == endpoint(graph, mask, state.second_word()),
                    "priority support changed the complete endpoint profiles");
        }
        ++states_checked; scalar_masks_checked += selected.size();
        if (depth == 4) return;
        for (unsigned int symbol = 0; symbol < 4; ++symbol)
            self(self, state.append_pair(symbol & 2U, symbol & 1U), depth + 1);
    };
    visit(visit, initial, 0);
    bool rejected = false;
    try { (void)product->select_mask_classes({1U << graph.size()}); }
    catch (const std::out_of_range&) { rejected = true; }
    require(rejected, "mask selector accepted an out-of-family representative");
    auto other_product = std::make_shared<family1::ExactPackedProduct>(graph);
    rejected = false;
    try { (void)other_product->disagreement_count(initial.left_profile(), initial.right_profile(), *selection); }
    catch (const std::invalid_argument&) { rejected = true; }
    require(rejected, "mask selection was accepted by a different packed product");
}

struct RejectPriorityAccess {
    family1::JointPairState state;
    RejectPriorityAccess append_pair(bool first, bool second) const { return {state.append_pair(first, second)}; }
    std::uint64_t remaining_count() const { return state.remaining_count(); }
    std::uint64_t mask_count() const { return state.mask_count(); }
    bool distinct() const { return state.distinct(); }
    const std::string& first_word() const { return state.first_word(); }
    const std::string& second_word() const { return state.second_word(); }
    std::uint64_t priority_remaining_count() const { throw std::logic_error("disabled policy called priority accessor"); }
    bool operator==(const RejectPriorityAccess& other) const { return state == other.state; }
};

void same_search(const hardpair::joint::Result& a, const hardpair::joint::Result& b)
{
    require(a.found == b.found && a.first == b.first && a.second == b.second && a.length == b.length
            && a.expanded_nodes == b.expanded_nodes && a.complete_windows == b.complete_windows
            && a.visited_leaves == b.visited_leaves && a.equivalent_leaves == b.equivalent_leaves
            && a.cross_pool_equivalent_leaves == b.cross_pool_equivalent_leaves
            && a.unequal_leaves == b.unequal_leaves && a.maximum_depth_visited == b.maximum_depth_visited
            && a.expansion_limit_reached == b.expansion_limit_reached && a.rounds == b.rounds,
            "disabled priority support changed baseline witnesses or work counters");
}

void check_ranking_and_disabled_policy()
{
    const auto graph = family1::LargeGraph::from_key("0001020302030405000604060105");
    auto product = std::make_shared<family1::ExactPackedProduct>(graph);
    auto selection = family1::permutation_priority_selection(product, graph);
    family1::JointPairState plain(product, "0000", "0010");
    family1::JointPairState prioritized(product, "0000", "0010", selection);
    hardpair::joint::Options options;
    options.window_k = 2; options.beam_width = 1; options.diagonal_width = 0;
    options.max_length = 6; options.max_expansions = 20;
    const auto baseline = hardpair::joint::find_pair(plain, options);
    same_search(baseline, hardpair::joint::find_pair(prioritized, options));
    same_search(baseline, hardpair::joint::find_pair(RejectPriorityAccess{plain}, options));
    require(!baseline.found && baseline.round_trace.size() == 1
            && baseline.round_trace[0].selected_first == "000011"
            && baseline.round_trace[0].selected_second == "001001"
            && baseline.round_trace[0].selected_remaining == 100, "total-D baseline ranking changed");

    std::vector<bool> selected(1U << graph.size());
    for (unsigned int mask = 0; mask < selected.size(); ++mask) selected[mask] = permutation(graph, mask);
    using Rank = std::tuple<std::uint64_t, std::uint64_t, std::string, std::string>;
    std::vector<Rank> exhaustive;
    for (unsigned int a = 0; a < 4; ++a) for (unsigned int b = 0; b < 4; ++b) {
        std::string first = plain.first_word(), second = plain.second_word();
        for (unsigned int symbol : {a, b}) {
            first += symbol & 2U ? '1' : '0'; second += symbol & 1U ? '1' : '0';
        }
        const auto expected = scalar_counts(graph, selected, first, second);
        exhaustive.emplace_back(expected.priority, expected.total, first, second);
    }
    const auto expected_best = *std::min_element(exhaustive.begin(), exhaustive.end());
    require(expected_best == Rank{3, 108, "000010", "001011"}, "independent ranking fixture changed");
    options.prioritize_permutation = true;
    const auto result = hardpair::joint::find_pair(prioritized, options);
    require(!result.found && result.rank_policy == "permutation-disagreement-then-total"
            && result.prioritize_permutation && result.round_trace.size() == 1,
            "priority rank policy was not recorded");
    const auto& trace = result.round_trace[0];
    require(Rank{trace.selected_priority_remaining, trace.selected_remaining,
                 trace.selected_first, trace.selected_second} == expected_best,
            "priority ranking disagrees with exhaustive scalar joint k=2 comparison");
    require(result.initial_priority_remaining == scalar_counts(graph, selected, "0000", "0010").priority,
            "initial priority mismatch count is wrong");
    require(result.complete_windows == 1 && result.visited_leaves == 16 && result.expanded_nodes == 20,
            "priority ranking skipped a joint-alphabet continuation");
    bool rejected = false;
    try { (void)hardpair::joint::find_pair(plain, options); }
    catch (const std::logic_error&) { rejected = true; }
    require(rejected, "priority policy accepted a state without its required subset");
}
} // namespace

int main()
{
    try {
        for (unsigned int m = 1; m <= 8; ++m) {
            for (unsigned int variant = 0; variant < 3; ++variant) {
                std::vector<family1::LargeGraph::Row> ports;
                for (unsigned int state = 0; state < m; ++state) {
                    const auto first = (state + 1) % m;
                    const auto second = variant == 0 ? first : variant == 1 ? (state + 2) % m : (3 * state + 1) % m;
                    ports.push_back({first, second});
                }
                check_graph(family1::LargeGraph(std::move(ports)));
            }
        }
        check_graph(family1::LargeGraph::from_key("0001020302030405000604060105"));
        check_graph(family1::LargeGraph::from_key("01020003040501060003020705060407"));
        check_ranking_and_disabled_policy();
        std::cout << "joint permutation-priority tests passed: " << states_checked << " pair states, "
                  << scalar_masks_checked << " independent scalar mask checks; joint k=2 ranking\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}

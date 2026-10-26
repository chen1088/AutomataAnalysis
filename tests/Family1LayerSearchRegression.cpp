#include "Family1LayerSearch.h"
#include <array>
#include <csignal>
#include <iostream>
#include <map>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using family1::LargeGraph;
using State = std::array<unsigned char, 128>;
void require(bool value, const char* reason) { if (!value) throw std::runtime_error(reason); }
std::string word(unsigned int value, unsigned int depth)
{
    std::string result(depth, '0');
    for (unsigned int i = 0; i < depth; ++i) { result[depth - i - 1] += value & 1U; value >>= 1; }
    return result;
}
State profile(const LargeGraph& graph, const std::string& word)
{
    State result{};
    for (unsigned int mask = 0; mask < 128; ++mask)
        for (char c : word) result[mask] = static_cast<unsigned char>(
            graph.ports[result[mask]][(c - '0') ^ ((mask >> result[mask]) & 1)]);
    return result;
}
unsigned int brute(const LargeGraph& graph, unsigned int cap)
{
    for (unsigned int depth = 1; depth <= cap; ++depth) {
        std::map<State, unsigned int> seen;
        for (unsigned int index = 0; index < (1U << depth); ++index)
            if (!seen.emplace(profile(graph, word(index, depth)), index).second) return depth;
    }
    return 0;
}
void check(const LargeGraph& graph, unsigned int depth, bool expected_collision, bool forced = false)
{
    for (unsigned int storage = 0; storage < 3; ++storage) {
    family1::LayerLimits limits;
    limits.depth = depth; limits.max_layer_states = 1ULL << depth;
    limits.max_working_bytes = 16ULL << 20; limits.force_hash_collisions = forced;
    limits.retain_word_indices = storage != 0;
    limits.pack_word_indices = storage == 2;
    const auto score = family1::search_layer(graph, limits);
    require(score.reason.empty(), "small single-layer search hit a resource cap");
    require(score.peak_working_bytes <= limits.max_working_bytes, "single-layer payload budget exceeded");
    if (expected_collision) {
        require(score.status == "collision" && score.upper_bound == depth && score.lower_bound == 1,
            "single-layer collision presented as a shortest/exact score");
        require(score.witness[0] != score.witness[1] && score.witness[0].size() == depth
            && score.witness[1].size() == depth, "single-layer witness words are invalid");
        require(profile(graph, score.witness[0]) == profile(graph, score.witness[1]),
            "single-layer witness fails independent original-mask trajectories");
    } else {
        require(score.status == "collision-free" && score.upper_bound == 0 && score.lower_bound == depth + 1
            && score.witness[0].empty(), "collision-free layer lower bound is wrong");
    }
    }
}
}

int main()
{
    try {
        unsigned int tables_checked = 0;
        for (unsigned int size = 1; size <= 3; ++size) {
            unsigned int tables = 1;
            for (unsigned int slot = 0; slot < 2 * size; ++slot) tables *= size;
            for (unsigned int number = 0; number < tables; ++number) {
                auto value = number;
                std::vector<LargeGraph::Row> rows(7, {0, 0});
                for (unsigned int state = 0; state < size; ++state)
                    for (auto& target : rows[state]) { target = value % size; value /= size; }
                const LargeGraph graph(std::move(rows));
                const auto exact = brute(graph, 6);
                require(exact > 0, "independent padded small oracle exceeded its cap");
                for (unsigned int depth = 0; depth <= exact + 1; ++depth)
                    check(graph, depth, depth >= exact, (number % 17) == 0);
                ++tables_checked;
            }
        }
        std::mt19937 random(1088);
        for (unsigned int trial = 0; trial < 40; ++trial) {
            std::vector<LargeGraph::Row> rows(7);
            for (unsigned int state = 0; state < 7; ++state) rows[state] = {(state + 1) % 7, random() % 7};
            const LargeGraph graph(std::move(rows));
            const auto exact = brute(graph, 9);
            check(graph, 9, exact != 0, trial == 0);
        }
        const auto hard = LargeGraph::from_key("0001020301040506030500020005");
        check(hard, 20, false);
        const LargeGraph two(std::vector<LargeGraph::Row>(7, {0, 1}));
        family1::LayerLimits limits;
        limits.depth = 3; limits.max_working_bytes = 1;
        auto result = family1::search_layer(two, limits);
        require(result.status == "incomplete" && result.lower_bound == 1 && result.upper_bound == 0
            && result.reason == "max-working-bytes", "layer memory cap became a proof");
        limits.max_working_bytes = 16ULL << 20; limits.max_layer_states = 4;
        result = family1::search_layer(two, limits);
        require(result.status == "incomplete" && result.reason == "max-layer-states"
            && result.lower_bound == 1, "layer state cap became a proof");
        volatile std::sig_atomic_t interrupted = 1;
        limits.interrupted = &interrupted;
        result = family1::search_layer(two, limits);
        require(result.status == "incomplete" && result.reason == "interrupted", "layer interruption ignored");
        std::cout << "Layer search passed " << tables_checked
            << " independently scored padded tables, 40 accessible seven-state cases, forced hash collisions and resource caps.\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}

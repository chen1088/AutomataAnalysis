#include "Family1ExactPacked.h"
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
void require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
}

std::string word(unsigned int number, unsigned int length)
{
    std::string result(length, '0');
    for (unsigned int i = 0; i < length; ++i) {
        result[length - i - 1] += number & 1;
        number >>= 1;
    }
    return result;
}

unsigned int endpoint(const LargeGraph& graph, unsigned int mask, const std::string& input)
{
    unsigned int state = 0;
    for (char c : input) state = graph.ports[state][(c - '0') ^ ((mask >> state) & 1)];
    return state;
}

std::vector<unsigned int> profile(const LargeGraph& graph, const std::string& input)
{
    std::vector<unsigned int> result;
    for (unsigned int mask = 0; mask < (1U << graph.size()); ++mask)
        result.push_back(endpoint(graph, mask, input));
    return result;
}

// Straightforward, independent full-vector search, with a NEW table for each
// length. It has no packed planes, omitted mask coordinates or hashes.
unsigned int brute_score(const LargeGraph& graph, unsigned int cap)
{
    for (unsigned int depth = 1; depth <= cap; ++depth) {
        std::map<std::vector<unsigned int>, unsigned int> seen;
        for (unsigned int index = 0; index < (1U << depth); ++index)
            if (!seen.emplace(profile(graph, word(index, depth)), index).second) return depth;
    }
    return 0;
}

void check_score(const LargeGraph& graph, unsigned int expected, bool force_hash_collisions = false,
    std::uint64_t byte_budget = 16ULL << 20, bool repeat = true)
{
    family1::PackedLimits limits;
    limits.depth = expected;
    limits.max_layer_states = 1ULL << expected;
    limits.max_working_bytes = byte_budget;
    limits.force_hash_collisions = force_hash_collisions;
    for (bool quotient : {false, true}) {
        limits.quotient_complements = quotient;
        const auto result = family1::score_packed(graph, limits);
        require(result.status == "exact" && result.merge_length == expected
            && result.lower_bound == expected, "packed score differs from independent exhaustive score");
        require(result.witness[0] != result.witness[1]
            && result.witness[0].size() == expected && result.witness[1].size() == expected,
            "packed witness has wrong length or equal words");
        require(!quotient || result.witness[0][0] == '0', "quotient witness is not normalized to first input zero");
        require(profile(graph, result.witness[0]) == profile(graph, result.witness[1]),
            "packed witness fails full original-mask simulation");
        require(result.peak_working_bytes <= limits.max_working_bytes, "packed byte cap exceeded");
        require(result.evaluated_words == result.profiles_evaluated * (quotient ? 2 : 1),
            "representative and derived-word counters disagree");
        if (repeat) {
            const auto repeated = family1::score_packed(graph, limits);
            require(repeated.witness == result.witness && repeated.evaluated_words == result.evaluated_words,
                "packed scoring order is nondeterministic");
        }
    }
}

void check_product(const LargeGraph& graph, const std::vector<std::string>& words,
    const std::vector<unsigned int>& masks)
{
    family1::ExactPackedProduct product(graph);
    for (const auto& input : words) {
        const auto packed = product.evaluate(input);
        for (auto mask : masks)
            require(product.endpoint(packed, mask) == endpoint(graph, mask, input),
                "packed endpoint disagrees with static-mask simulation on revisit");
        auto incremental = product.evaluate("");
        for (char c : input) incremental = product.step(incremental, c == '1');
        require(incremental == packed, "packed step/evaluate mismatch");
    }
}

std::vector<unsigned int> all_masks(unsigned int size)
{
    std::vector<unsigned int> result;
    for (unsigned int mask = 0; mask < (1U << size); ++mask) result.push_back(mask);
    return result;
}
}

int main()
{
    try {
        unsigned int checked = 0;
        for (unsigned int size = 1; size <= 3; ++size) {
            unsigned int tables = 1;
            for (unsigned int entry = 0; entry < 2 * size; ++entry) tables *= size;
            for (unsigned int number = 0; number < tables; ++number) {
                auto value = number;
                std::vector<LargeGraph::Row> table(size);
                for (auto& row : table)
                    for (auto& target : row) { target = value % size; value /= size; }
                const LargeGraph graph(std::move(table));
                const auto expected = brute_score(graph, 6);
                require(expected != 0, "small independent search unexpectedly capped");
                check_score(graph, expected, (number % 7) == 0);
                ++checked;
            }
        }

        // Root loops produce recurrences at different lengths before the first
        // valid equal-length merge. Static bits remain fixed during revisits.
        const LargeGraph two({{0, 1}, {0, 1}});
        check_score(two, 3, true);
        std::vector<std::string> revisit_words;
        for (unsigned int depth = 0; depth <= 8; ++depth)
            for (unsigned int index = 0; index < (1U << depth); ++index)
                revisit_words.push_back(word(index, depth));
        check_product(two, revisit_words, all_masks(2));

        // Depth fifteen crosses several storage chunks and repeatedly expands
        // the layer in place, beyond all the small all-table comparisons above.
        const LargeGraph five({{0, 1}, {2, 3}, {0, 1}, {3, 4}, {2, 4}});
        require(brute_score(five, 15) == 15, "independent five-state merge length changed");
        check_score(five, 15);

        // Both globally verified m=6 maximizers. Exact full-mask searches with
        // quotienting on/off must agree, and every new witness is independently
        // replayed against all 64 original static masks.
        check_score(LargeGraph({{0, 1}, {2, 3}, {3, 4}, {2, 5}, {0, 1}, {4, 5}}), 23,
            false, 1ULL << 30, false);
        check_score(LargeGraph({{1, 2}, {0, 3}, {4, 5}, {2, 3}, {0, 1}, {4, 5}}), 23,
            false, 1ULL << 30, false);

        std::mt19937 random(1088);
        for (unsigned int size : {7U, 8U, 10U}) {
            std::vector<LargeGraph::Row> table(size);
            for (unsigned int state = 0; state < size; ++state) table[state] = {state, (state + 1) % size};
            const LargeGraph graph(std::move(table));
            family1::ExactPackedProduct product(graph);
            require(product.effective_mask_bits() == size && product.mask_count() == (1U << size),
                "noncoincident mask bit incorrectly omitted");
            std::vector<std::string> words{"", "0", "1", "00000000", "01010101010101010101"};
            for (unsigned int i = 0; i < 8; ++i) words.push_back(word(random(), 24));
            check_product(graph, words, all_masks(size));
        }

        // Deliberately retain unreachable noncoincident vertices here to test
        // the complement transform across multiple 64-mask blocks in the
        // scorer itself. The rooted behavior is the independently checked
        // two-state example; no mask bit is omitted by the product backend.
        for (unsigned int size : {7U, 8U, 20U}) {
            const LargeGraph padded(std::vector<LargeGraph::Row>(size, {0, 1}));
            check_score(padded, 3, false, 64ULL << 20, false);
        }

        // At m=20 only eight bits matter here. Check original-mask expansion,
        // including bits at coincident vertices, against independent simulation.
        std::vector<LargeGraph::Row> compressed_table(20);
        for (unsigned int state = 0; state < 20; ++state)
            compressed_table[state] = {(state + 1) % 20, state < 8 ? state : (state + 1) % 20};
        const LargeGraph compressed(std::move(compressed_table));
        family1::ExactPackedProduct compressed_product(compressed);
        require(compressed_product.effective_mask_bits() == 8 && compressed_product.mask_count() == 256
            && compressed_product.profile_planes() == 20, "coincident-port compression is wrong");
        std::vector<unsigned int> sample_masks{0, (1U << 20) - 1};
        for (unsigned int i = 0; i < 2048; ++i) sample_masks.push_back(random() & ((1U << 20) - 1));
        check_product(compressed, {"01010101010101010101010101010101", "11110000111100001111000011110000"}, sample_masks);

        // Full 2^20-mask construction uses algebraic bit patterns, and retains
        // all state bits (including the fifth bit at vertices 16..19).
        std::vector<LargeGraph::Row> full_table(20), coincident_table(20);
        for (unsigned int state = 0; state < 20; ++state) {
            full_table[state] = {state, (state + 1) % 20};
            coincident_table[state] = {(state + 1) % 20, (state + 1) % 20};
        }
        const LargeGraph full(std::move(full_table)), coincident(std::move(coincident_table));
        {
            family1::ExactPackedProduct full_product(full);
            require(full_product.effective_mask_bits() == 20 && full_product.mask_count() == (1U << 20)
                && full_product.profile_planes() == 81920, "full m20 product shape is wrong");
            const auto packed = full_product.evaluate("01011010");
            for (auto mask : sample_masks)
                require(full_product.endpoint(packed, mask) == endpoint(full, mask, "01011010"),
                    "full m20 packed endpoint mismatch");
        }
        family1::ExactPackedProduct coincident_product(coincident);
        require(coincident_product.mask_count() == 1 && coincident_product.profile_planes() == 5,
            "all-coincident family not reduced to one coordinate");
        const auto same = family1::score_packed(coincident);
        require(same.status == "exact" && same.merge_length == 1, "coincident graph should merge at length one");
        check_product(coincident, {"00000000000000000", "11111111111111111111111"}, sample_masks);

        const LargeGraph six({{0, 1}, {2, 3}, {0, 1}, {3, 4}, {2, 5}, {4, 5}});
        family1::PackedLimits limits;
        limits.depth = 2;
        auto capped = family1::score_packed(two, limits);
        require(capped.status == "depth-capped" && capped.lower_bound == 3
            && capped.merge_length == 0 && capped.witness[0].empty(), "depth cap presented as exact");
        limits.depth = 3;
        limits.max_layer_states = 4;
        capped = family1::score_packed(two, limits);
        require(capped.status == "incomplete" && capped.reason == "max-layer-states"
            && capped.lower_bound == 3 && capped.merge_length == 0, "state cap loses completed lower bound");
        limits.max_layer_states = 1ULL << 24;
        limits.max_working_bytes = 256;
        capped = family1::score_packed(six, limits);
        require(capped.status == "incomplete" && capped.reason == "max-working-bytes"
            && capped.merge_length == 0 && capped.lower_bound == 1, "memory cap presented as exact");
        volatile std::sig_atomic_t stop = 1;
        limits.interrupted = &stop;
        capped = family1::score_packed(two, limits);
        require(capped.status == "incomplete" && capped.reason == "interrupted" && capped.lower_bound == 1,
            "preexisting interruption ignored");
        bool rejected = false;
        try { coincident_product.evaluate("012"); } catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "nonbinary word accepted");
        rejected = false;
        try { coincident_product.endpoint(coincident_product.evaluate(""), 1U << 20); }
        catch (const std::out_of_range&) { rejected = true; }
        require(rejected, "out-of-family mask accepted");
        std::cout << "Packed exact regression passed: " << checked
            << " independently scored ordered tables; full-mask products through m20; caps and static revisits.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}

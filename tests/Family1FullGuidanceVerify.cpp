#include "Family1FullGuidance.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <memory>
#include <numeric>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Table = std::vector<family1::LargeGraph::Row>;
void require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
}
unsigned int endpoint(const Table& table, std::uint32_t mask, const std::string& word)
{
    unsigned int state = 0;
    for (char letter : word) state = table[state][(letter - '0') ^ ((mask >> state) & 1U)];
    return state;
}
bool permutation(const Table& table, std::uint32_t mask)
{
    std::array<unsigned int, 20> a{}, b{};
    for (unsigned int source = 0; source < table.size(); ++source) {
        const auto bit = (mask >> source) & 1U;
        ++a[table[source][bit]]; ++b[table[source][1U ^ bit]];
    }
    for (unsigned int state = 0; state < table.size(); ++state) if (a[state] != 1 || b[state] != 1) return false;
    return true;
}
std::vector<std::uint64_t> scalar_trace(const Table& table, const std::string& first,
                                      const std::string& second, const std::string& suffix, std::uint64_t& blocked)
{
    std::vector<std::uint64_t> result(suffix.size() + 1);
    blocked = 0;
    for (std::uint32_t mask = 0; mask < (1U << table.size()); ++mask) {
        auto a = endpoint(table, mask, first), b = endpoint(table, mask, second);
        blocked += a != b && permutation(table, mask);
        result[0] += a == b;
        for (std::size_t step = 0; step < suffix.size(); ++step) {
            const auto bit = static_cast<unsigned int>(suffix[step] - '0');
            a = table[a][bit ^ ((mask >> a) & 1U)];
            b = table[b][bit ^ ((mask >> b) & 1U)];
            result[step + 1] += a == b;
        }
    }
    return result;
}
void verify(const Table& table, const std::string& first, const std::string& second,
            const family1::FullSuffixBeamResult& result, unsigned int cap, std::uint64_t budget)
{
    std::uint64_t blocked = 0;
    const auto expected = scalar_trace(table, first, second, result.suffix, blocked);
    require(result.score_trace == expected, "full objective trace differs from all-mask scalar replay");
    require(result.mask_count == (1U << table.size()) && result.merged_count == expected.back(), "full progress denominator/count mismatch");
    require(result.permutation_mismatch_count == blocked, "full guidance permutation obstruction is wrong");
    require(result.all_merged == (expected.back() == result.mask_count), "miss incorrectly marked as a universal collision");
    require(result.suffix.size() <= cap && result.depth_reached <= cap, "suffix length exceeds search cap");
    require(result.expanded_nodes + result.lookahead_nodes <= budget, "expansion budget exceeded");
    require(std::is_sorted(expected.begin(), expected.end()), "common suffix decreased progress");
    if (blocked) require(result.suffix.empty() && !result.expanded_nodes && !result.lookahead_nodes, "permutation-blocked prefix was not rejected");
}
Table canonical(const Table& table)
{
    std::vector<unsigned int> map(table.size()); std::iota(map.begin(), map.end(), 0U);
    Table best;
    do {
        Table candidate(table.size());
        for (unsigned int source = 0; source < table.size(); ++source) {
            auto a = map[table[source][0]], b = map[table[source][1]];
            candidate[map[source]] = {std::min(a, b), std::max(a, b)};
        }
        if (best.empty() || candidate < best) best = candidate;
    } while (std::next_permutation(map.begin() + 1, map.end()));
    return best;
}
bool reachable(const Table& table)
{
    std::set<unsigned int> seen{0}; std::vector<unsigned int> queue{0};
    for (std::size_t i = 0; i < queue.size(); ++i)
        for (auto target : table[queue[i]]) if (seen.insert(target).second) queue.push_back(target);
    return seen.size() == table.size();
}
void tiny()
{
    unsigned int classes = 0, searches = 0;
    for (unsigned int m = 1; m <= 3; ++m) {
        unsigned int total = 1; for (unsigned int i = 0; i < 2 * m; ++i) total *= m;
        std::set<Table> tables;
        for (unsigned int code = 0; code < total; ++code) {
            auto value = code; Table table(m);
            for (auto& row : table) for (auto& target : row) { target = value % m; value /= m; }
            if (reachable(table)) tables.insert(canonical(table));
        }
        require(tables.size() == std::array<unsigned int, 4>{0, 1, 6, 57}[m], "tiny independent class enumeration is wrong");
        for (const auto& table : tables) {
            ++classes;
            auto ctx = std::make_shared<family1::PairAgreementContext>(family1::LargeGraph(table));
            for (const auto& words : std::array<std::pair<std::string, std::string>, 2>{std::pair{"01", "10"}, std::pair{"00", "11"}})
                for (unsigned int lookahead = 0; lookahead <= 1; ++lookahead) {
                    const auto result = family1::full_suffix_beam(ctx, words.first, words.second, 8, 4, lookahead, 1088, nullptr, 1000);
                    verify(table, words.first, words.second, result, 8, 1000);
                    ++searches;
                }
        }
    }
    const Table plateau{{0, 1}, {1, 2}, {0, 0}};
    auto ctx = std::make_shared<family1::PairAgreementContext>(family1::LargeGraph(plateau));
    for (unsigned int lookahead = 0; lookahead <= 1; ++lookahead) {
        const auto a = family1::full_suffix_beam(ctx, "01", "10", 2, 4, lookahead, 1088);
        const auto b = family1::full_suffix_beam(ctx, "01", "10", 2, 4, lookahead, 1088);
        verify(plateau, "01", "10", a, 2, 10000);
        require(a.all_merged && a.score_trace == std::vector<std::uint64_t>{4, 4, 8}, "neutral H4 plateau was lost");
        require(a.suffix == b.suffix && a.score_trace == b.score_trace
            && a.expanded_nodes == b.expanded_nodes && a.lookahead_nodes == b.lookahead_nodes, "seeded full guidance is not deterministic");
    }
    const auto limited = family1::full_suffix_beam(ctx, "01", "10", 8, 4, 1, 1088, nullptr, 2);
    verify(plateau, "01", "10", limited, 8, 2);
    require(limited.expansion_limit_reached && !limited.all_merged, "limited miss incorrectly certified a result");
    volatile std::sig_atomic_t interrupted = 1;
    const auto canceled = family1::full_suffix_beam(ctx, "01", "10", 8, 4, 1, 1088, &interrupted);
    require(canceled.interrupted && !canceled.expanded_nodes && !canceled.all_merged, "canceled search did not preserve exact initial status");
    std::cout << "tiny_classes=" << classes << " full_guidance_searches=" << searches << " neutral_H4_trace=4,4,8 passed\n";
}
void large()
{
    for (unsigned int m : {7U, 20U}) {
        Table table(m);
        for (unsigned int state = 0; state < m; ++state) table[state] = {(state + 1) % m, (state + m / 3) % m};
        auto ctx = std::make_shared<family1::PairAgreementContext>(family1::LargeGraph(table));
        const auto budget = m == 7 ? 10000U : 1000U;
        const auto first = family1::full_suffix_beam(ctx, "01", "10", 30, 4, 1, 1088, nullptr, budget);
        verify(table, "01", "10", first, 30, budget);
        std::cout << "m=" << m << " prefix=01/10 suffix=" << first.suffix << " exact_score=" << first.merged_count << '/' << first.mask_count
            << " blocked=" << first.permutation_mismatch_count << " expansions=" << first.expanded_nodes << '+' << first.lookahead_nodes
            << " seconds=" << first.seconds << " passed\n";
        if (m == 20) {
            const auto ordered = family1::full_suffix_beam(ctx, "0000011111", "1111100000", 30, 4, 1, 1088, nullptr, 1000);
            verify(table, "0000011111", "1111100000", ordered, 30, 1000);
            require(!ordered.permutation_mismatch_count, "period5 blocks should pass the exact permutation gate");
            std::cout << "m=20 prefix=0^5,1^5 commutator suffix=" << ordered.suffix << " exact_score=" << ordered.merged_count << '/' << ordered.mask_count
                << " expansions=" << ordered.expanded_nodes << '+' << ordered.lookahead_nodes << " seconds=" << ordered.seconds << " passed\n";
        }
    }
}
}
int main()
{
    try { tiny(); large(); std::cout << "all_full_guidance_checks_passed\n"; return 0; }
    catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}

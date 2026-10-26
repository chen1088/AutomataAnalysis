#include "Family1PairAgreement.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <memory>
#include <numeric>
#include <random>
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
bool reachable(const Table& table)
{
    std::vector<unsigned int> queue{0};
    std::vector<bool> seen(table.size()); seen[0] = true;
    for (std::size_t i = 0; i < queue.size(); ++i)
        for (auto target : table[queue[i]]) if (!seen[target]) { seen[target] = true; queue.push_back(target); }
    return queue.size() == table.size();
}
Table canonical(const Table& table)
{
    Table best;
    std::vector<unsigned int> map(table.size()); std::iota(map.begin(), map.end(), 0U);
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
std::set<Table> all_classes(unsigned int m)
{
    std::uint64_t count = 1;
    for (unsigned int i = 0; i < 2 * m; ++i) count *= m;
    std::set<Table> result;
    for (std::uint64_t code = 0; code < count; ++code) {
        auto value = code; Table table(m);
        for (auto& row : table) for (auto& target : row) { target = value % m; value /= m; }
        if (reachable(table)) result.insert(canonical(table));
    }
    return result;
}
unsigned int endpoint(const Table& table, std::uint32_t mask, const std::string& word)
{
    unsigned int state = 0;
    for (char letter : word) state = table[state][(letter - '0') ^ ((mask >> state) & 1U)];
    return state;
}
bool permutation(const Table& table, std::uint32_t mask)
{
    std::array<unsigned int, 20> zero{}, one{};
    for (unsigned int source = 0; source < table.size(); ++source) {
        const auto bit = (mask >> source) & 1U;
        ++zero[table[source][bit]]; ++one[table[source][1U ^ bit]];
    }
    for (unsigned int state = 0; state < table.size(); ++state)
        if (zero[state] != 1 || one[state] != 1) return false;
    return true;
}
void check_mask(const Table& table, const family1::ExactPairAgreement& pair,
                std::uint32_t mask, const std::string& first, const std::string& second)
{
    const auto left = endpoint(table, mask, first), right = endpoint(table, mask, second);
    require(pair.agrees_on_mask(mask) == (left == right), "agreement lane differs from scalar endpoints");
    const auto saved = pair.unmerged_endpoints(mask);
    if (left == right) require(!saved, "merged coordinates must be discarded");
    else require(saved && saved->first == left && saved->second == right, "stored complete endpoints differ from scalar simulation");
}
void check_full(const Table& table, const family1::PairAgreementContext& context,
                const family1::ExactPairAgreement& pair, const std::string& first, const std::string& second)
{
    std::uint64_t merged = 0, perm_count = 0, perm_mismatch = 0;
    for (std::uint32_t mask = 0; mask < (1U << table.size()); ++mask) {
        const auto equal = endpoint(table, mask, first) == endpoint(table, mask, second);
        const auto perm = permutation(table, mask);
        merged += equal; perm_count += perm; perm_mismatch += perm && !equal;
        require(context.is_permutation_mask(mask) == perm, "permutation mask XOR constraints differ from scalar indegrees");
        check_mask(table, pair, mask, first, second);
    }
    require(pair.merged_count() == merged && pair.mask_count() == (1U << table.size()), "full all-mask agreement count is wrong");
    require(context.permutation_mask_count() == perm_count, "permutation mask total is wrong");
    require(pair.permutation_mismatch_count() == perm_mismatch, "permutation mismatch count is wrong");
    require(pair.all_merged() == (merged == pair.mask_count()), "all_merged reports a sampling miss as a proof");
}
void tiny_cases()
{
    const std::array<std::pair<std::string, std::string>, 5> words{
        std::pair{"0", "1"}, std::pair{"00", "11"}, std::pair{"01", "10"},
        std::pair{"000100", "010000"}, std::pair{"001011", "011001"}};
    unsigned int classes = 0, pairs = 0;
    for (unsigned int m = 1; m <= 3; ++m) {
        const auto tables = all_classes(m);
        require(tables.size() == std::array<unsigned int, 4>{0, 1, 6, 57}[m], "independent tiny class count is wrong");
        for (const auto& table : tables) {
            ++classes;
            auto context = std::make_shared<family1::PairAgreementContext>(family1::LargeGraph(table));
            for (const auto& [u, v] : words) {
                ++pairs; std::string first = u, second = v;
                family1::ExactPairAgreement pair(context, first, second);
                check_full(table, *context, pair, first, second);
                const auto initial_permutation_mismatch = pair.permutation_mismatch_count();
                for (char letter : std::string("011010")) {
                    const auto prior = pair.merged_count();
                    const auto other = pair.append_common(letter != '1');
                    check_full(table, *context, other, first + (letter == '1' ? '0' : '1'), second + (letter == '1' ? '0' : '1'));
                    require(pair.merged_count() == prior, "copying suffix branch changed its parent");
                    pair = pair.append_common(letter == '1');
                    first += letter; second += letter;
                    check_full(table, *context, pair, first, second);
                    require(pair.merged_count() >= prior, "common suffix decreased exact agreement");
                    require(pair.permutation_mismatch_count() == initial_permutation_mismatch, "permutation mismatch changed under common suffix");
                }
            }
        }
    }
    std::cout << "tiny_rooted_classes=" << classes << " distinct_pairs=" << pairs << " scalar_full_counts_and_copy_branches=passed\n";
}
void large_cases()
{
    std::mt19937 random(20261026);
    for (unsigned int kind = 0; kind < 3; ++kind) {
        Table table(20);
        for (unsigned int state = 0; state < 20; ++state) {
            const auto next = (state + 1) % 20;
            table[state] = {next, kind == 0 ? (state + 6) % 20 : kind == 1 ? 0U : next};
        }
        auto context = std::make_shared<family1::PairAgreementContext>(family1::LargeGraph(table));
        std::string first(24, '0'), second(24, '0');
        for (unsigned int i = 0; i < first.size(); ++i) { first[i] += random() & 1; second[i] += random() & 1; }
        require(first != second, "random fixture words must be distinct");
        family1::ExactPairAgreement pair(context, first, second);
        check_full(table, *context, pair, first, second);
        require(pair.storage_bytes() < (6U << 20), "paired all-mask tracker exceeds expected payload");
        const auto original_perm_mismatch = pair.permutation_mismatch_count();
        for (char bit : std::string("01011001")) {
            const auto before = pair.merged_count();
            pair = pair.append_common(bit == '1'); first += bit; second += bit;
            require(pair.merged_count() >= before, "m20 common-suffix count decreased");
            require(pair.permutation_mismatch_count() == original_perm_mismatch, "m20 permutation mismatch changed");
            for (unsigned int sample = 0; sample < 256; ++sample)
                check_mask(table, pair, random() & ((1U << 20) - 1), first, second);
        }
        check_full(table, *context, pair, first, second);
        require(context->permutation_mask_count() == (kind == 0 ? 32U : kind == 1 ? 0U : (1U << 20)), "m20 known permutation mask count is wrong");
        std::cout << "m20_kind=" << kind << " exact_masks=" << pair.mask_count() << " merged=" << pair.merged_count()
            << " permutation_masks=" << context->permutation_mask_count() << " payload_bytes=" << pair.storage_bytes() << " passed\n";
    }
}
void rejected_inputs()
{
    auto context = std::make_shared<family1::PairAgreementContext>(family1::LargeGraph(Table{{0, 0}}));
    unsigned int rejected = 0;
    for (const auto& words : std::array<std::pair<std::string, std::string>, 4>{
        std::pair{"", ""}, std::pair{"0", "0"}, std::pair{"0", "01"}, std::pair{"0", "x"}}) {
        try { family1::ExactPairAgreement pair(context, words.first, words.second); }
        catch (const std::invalid_argument&) { ++rejected; }
    }
    try { family1::ExactPairAgreement pair(nullptr, "0", "1"); }
    catch (const std::invalid_argument&) { ++rejected; }
    require(rejected == 5, "invalid pair inputs were not rejected");
}
}
int main()
{
    try {
        tiny_cases(); large_cases(); rejected_inputs();
        std::cout << "all_exact_pair_agreement_checks_passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}

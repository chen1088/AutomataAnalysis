#include "Family1Search.h"
#include <algorithm>
#include <csignal>
#include <functional>
#include <iostream>
#include <map>
#include <numeric>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Table = std::vector<Family1Graph::Row>;

void require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
}

std::string binary_word(unsigned value, unsigned depth)
{
    std::string word(depth, '0');
    for (unsigned i = 0; i < depth; ++i) {
        word[depth - i - 1] += (value & 1);
        value >>= 1;
    }
    return word;
}

// Deliberately simulate each mask separately, without bitplanes or incremental
// product states. The same mask is consulted on every visit to a vertex.
std::vector<unsigned> brute_profile(const Table& graph, const std::string& word)
{
    std::vector<unsigned> result;
    for (unsigned mask = 0; mask < (1U << graph.size()); ++mask) {
        unsigned state = 0;
        for (char c : word)
            state = graph[state][(c - '0') ^ ((mask >> state) & 1)];
        result.push_back(state);
    }
    return result;
}

unsigned brute_score(const Table& graph, unsigned cap = 10)
{
    for (unsigned depth = 1; depth <= cap; ++depth) {
        std::set<std::vector<unsigned>> profiles;
        for (unsigned i = 0; i < (1U << depth); ++i)
            if (!profiles.insert(brute_profile(graph, binary_word(i, depth))).second)
                return depth;
    }
    return 0;
}

bool brute_accessible(const Table& graph)
{
    std::set<unsigned> seen{0};
    std::vector<unsigned> pending{0};
    while (!pending.empty()) {
        const auto state = pending.back(); pending.pop_back();
        for (auto next : graph[state])
            if (seen.insert(next).second) pending.push_back(next);
    }
    return seen.size() == graph.size();
}

// Here permutation maps OLD vertices to NEW vertices, independently of the
// production implementation's inverse convention.
Table brute_canonical(const Table& graph)
{
    std::vector<unsigned> permutation(graph.size());
    std::iota(permutation.begin(), permutation.end(), 0U);
    Table best;
    do {
        Table candidate(graph.size());
        for (unsigned old = 0; old < graph.size(); ++old) {
            candidate[permutation[old]] = {permutation[graph[old][0]], permutation[graph[old][1]]};
            std::sort(candidate[permutation[old]].begin(), candidate[permutation[old]].end());
        }
        if (best.empty() || candidate < best) best = std::move(candidate);
    } while (std::next_permutation(permutation.begin() + 1, permutation.end()));
    return best;
}

std::set<Table> brute_classes(unsigned m)
{
    Table graph(m);
    std::set<Table> classes;
    // All m^(2m) ORDERED labelled tables, with no generation restrictions.
    std::function<void(unsigned)> generate = [&](unsigned edge) {
        if (edge == 2 * m) {
            if (brute_accessible(graph)) classes.insert(brute_canonical(graph));
            return;
        }
        for (unsigned target = 0; target < m; ++target) {
            graph[edge / 2][edge % 2] = target;
            generate(edge + 1);
        }
    };
    generate(0);
    return classes;
}

void check_witness(const Family1Graph& graph, const family1::Score& result)
{
    require(result.status == "exact", "expected an exact score");
    require(result.merge_length > 0 && result.lower_bound == result.merge_length,
        "exact result has inconsistent bounds");
    require(result.witness[0] != result.witness[1], "witness words are identical");
    for (const auto& word : result.witness)
        require(word.size() == result.merge_length, "witness has wrong length");
    require(brute_profile(graph.ports, result.witness[0]) == brute_profile(graph.ports, result.witness[1]),
        "witness fails independent mask simulation");
}

void test_product()
{
    const std::vector<Table> samples{
        {{0, 0}},
        {{1, 1}, {1, 1}},
        {{0, 1}, {0, 0}},
        {{1, 2}, {0, 2}, {1, 1}},
        {{1, 0}, {2, 0}, {3, 1}, {3, 3}},
        {{1, 0}, {2, 0}, {3, 1}, {4, 2}, {0, 4}},
        {{1, 0}, {2, 0}, {3, 1}, {4, 2}, {5, 3}, {0, 5}},
    };
    for (const auto& table : samples) {
        const Family1Graph graph(table);
        const family1::Product product(graph);
        for (unsigned depth = 0; depth <= 7; ++depth) {
            for (unsigned index = 0; index < (1U << depth); ++index) {
                const auto word = binary_word(index, depth);
                const auto expected = brute_profile(table, word);
                const auto actual = product.evaluate(word);
                for (unsigned mask = 0; mask < expected.size(); ++mask)
                    require(product.endpoint(actual, mask) == expected[mask],
                        "bitplane product differs from static-mask simulation");
                if (depth > 0) {
                    const auto parent = product.evaluate(word.substr(0, depth - 1));
                    require(product.step(parent, word.back() == '1') == actual,
                        "evaluate and incremental step disagree");
                }
            }
        }
    }
    const family1::Product revisit(Family1Graph({{0, 1}, {0, 0}}));
    require(revisit.endpoint(revisit.evaluate("0000"), 1) == 0, "revisit mask changed");
    require(revisit.endpoint(revisit.evaluate("000"), 1) == 1, "revisit path is wrong");
    require(revisit.evaluate("0") == revisit.evaluate("10"), "cross-depth regression setup changed");
    require(!(revisit.evaluate("0") == revisit.evaluate("1")), "length-one words unexpectedly collide");

    bool threw = false;
    try { revisit.evaluate("02"); } catch (const std::invalid_argument&) { threw = true; }
    require(threw, "nonbinary word accepted");
    threw = false;
    try { revisit.endpoint({}, 4); } catch (const std::out_of_range&) { threw = true; }
    require(threw, "invalid mask accepted");
}

void test_canonical_invariance()
{
    const Table source{{1, 2}, {0, 3}, {2, 2}, {1, 0}};
    const auto expected = brute_canonical(source);
    std::vector<unsigned> permutation{0, 1, 2, 3};
    do {
        for (unsigned swaps = 0; swaps < 16; ++swaps) {
            Table candidate(4);
            for (unsigned old = 0; old < 4; ++old) {
                candidate[permutation[old]] = {
                    permutation[source[old][0]], permutation[source[old][1]]};
                if (swaps & (1U << old))
                    std::swap(candidate[permutation[old]][0], candidate[permutation[old]][1]);
            }
            require(GraphBasedPDFAEnumerator::canonical(Family1Graph(candidate)).ports == expected,
                "canonical table changes under root-preserving relabelling or port swaps");
        }
    } while (std::next_permutation(permutation.begin() + 1, permutation.end()));
}

void test_enumeration_and_scores()
{
    for (unsigned m = 1; m <= 4; ++m) {
        const auto expected = brute_classes(m);
        std::vector<Table> actual;
        GraphBasedPDFAEnumerator enumerator(m);
        require(enumerator.enumerate([&](const Family1Graph& graph) {
            require(graph.accessible() && brute_accessible(graph.ports), "inaccessible seed enumerated");
            require(GraphBasedPDFAEnumerator::is_canonical(graph), "noncanonical seed enumerated");
            require(graph.ports == brute_canonical(graph.ports), "independent canonical key differs");
            actual.push_back(graph.ports);
            if (m <= 3) {
                const auto result = family1::score(graph);
                check_witness(graph, result);
                require(result.merge_length == brute_score(graph.ports), "score differs from independent exhaustive scorer");
                family1::Limits collisions;
                collisions.force_hash_collisions = true;
                const auto forced = family1::score(graph, collisions);
                require(forced.status == result.status && forced.merge_length == result.merge_length
                    && forced.witness == result.witness, "hash collision changed score or witness");
            }
            return true;
        }), "complete enumeration reported interruption");
        require(std::is_sorted(actual.begin(), actual.end()), "enumeration is not deterministic lexicographic order");
        require(std::set<Table>(actual.begin(), actual.end()).size() == actual.size(), "duplicate class enumerated");
        require(std::set<Table>(actual.begin(), actual.end()) == expected, "enumeration missed or added a rooted class");

        unsigned visits = 0;
        require(!enumerator.enumerate([&](const Family1Graph& graph) {
            require(graph.ports == actual.front(), "restart order changed");
            ++visits; return false;
        }), "enumerator ignored requested termination");
        require(visits == 1, "enumerator called visitor after termination");
        std::cout << "Independent enumeration m=" << m << ": " << actual.size() << " classes\n";
    }
}

void test_bounds_and_interruption()
{
    const Family1Graph revisits({{0, 1}, {0, 0}});
    const auto exact = family1::score(revisits);
    check_witness(revisits, exact);
    require(exact.merge_length == 2, "cross-depth recurrence was counted as equal-length collision");
    family1::Limits capped;
    capped.depth = 1;
    const auto short_result = family1::score(revisits, capped);
    require(short_result.status == "depth-capped" && short_result.merge_length == 0
        && short_result.lower_bound == 2 && short_result.witness[0].empty(), "depth-capped result claims an exact score");
    capped.depth = 0;
    const auto zero = family1::score(revisits, capped);
    require(zero.status == "depth-capped" && zero.lower_bound == 1, "zero-depth bound is incorrect");

    family1::Limits tiny;
    tiny.max_layer_states = 1;
    const auto partial_first = family1::score(revisits, tiny);
    require(partial_first.status == "incomplete" && partial_first.lower_bound == 1
        && partial_first.merge_length == 0 && partial_first.reason == "max-layer-states",
        "partial first layer increased certified lower bound");

    Table hard;
    for (const auto& table : brute_classes(2)) if (brute_score(table) == 3) { hard = table; break; }
    require(!hard.empty(), "no independent m=2 maximum found");
    tiny.max_layer_states = 2;
    const auto partial_second = family1::score(Family1Graph(hard), tiny);
    require(partial_second.status == "incomplete" && partial_second.lower_bound == 2
        && partial_second.reason == "max-layer-states", "partial second layer increased certified lower bound");

    volatile std::sig_atomic_t stop = 1;
    family1::Limits interrupted;
    interrupted.interrupted = &stop;
    const auto stopped = family1::score(revisits, interrupted);
    require(stopped.status == "incomplete" && stopped.lower_bound == 1
        && stopped.reason == "interrupted", "interrupt reported an exact or stronger score");
    stop = 0;
    require(family1::score(revisits, interrupted).merge_length == exact.merge_length,
        "cleared interrupt changed score");

    // An unreachable vertex merely repeats the endpoint coordinates as its
    // unused mask bit varies, and cannot affect equality of product states.
    const Family1Graph unreachable({{0, 1}, {0, 0}, {2, 2}});
    require(!unreachable.accessible(), "unreachable regression setup changed");
    require(family1::score(unreachable).merge_length == exact.merge_length,
        "removing an unreachable vertex changed the shortest merge");
}
}

int main()
{
    try {
        test_product();
        test_canonical_invariance();
        test_enumeration_and_scores();
        test_bounds_and_interruption();
        std::cout << "Family 1 regression tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Family 1 regression failure: " << error.what() << '\n';
        return 1;
    }
}

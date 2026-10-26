#include "Family1LargeGraph.h"
#include <algorithm>
#include <functional>
#include <iostream>
#include <numeric>
#include <random>
#include <set>
#include <stdexcept>

namespace {
using Graph = family1::LargeGraph;
using Table = std::vector<Graph::Row>;

void require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
}

Table brute_canonical(const Table& source)
{
    std::vector<unsigned int> permutation(source.size());
    std::iota(permutation.begin(), permutation.end(), 0U);
    Table best;
    do {
        Table candidate(source.size());
        for (unsigned int old = 0; old < source.size(); ++old) {
            auto& row = candidate[permutation[old]];
            row = {permutation[source[old][0]], permutation[source[old][1]]};
            std::sort(row.begin(), row.end());
        }
        if (best.empty() || candidate < best) best = std::move(candidate);
    } while (std::next_permutation(permutation.begin() + 1, permutation.end()));
    return best;
}

void test_all_small_tables()
{
    constexpr unsigned int expected_classes[]{0, 1, 6, 57, 678};
    for (unsigned int m = 1; m <= 4; ++m) {
        Table table(m);
        std::set<Table> classes;
        std::function<void(unsigned int)> enumerate = [&](unsigned int edge) {
            if (edge == m * 2) {
                const Graph graph(table);
                if (!graph.accessible()) return;
                const auto canonical = graph.canonical();
                require(canonical.ports == brute_canonical(table),
                    "discovery canonicalization differs from all root-fixed permutations");
                require(canonical.canonical() == canonical, "canonicalization is not idempotent");
                require(Graph::from_key(canonical.key()) == canonical, "graph key failed round trip");
                classes.insert(canonical.ports);
                return;
            }
            for (unsigned int target = 0; target < m; ++target) {
                table[edge / 2][edge % 2] = target;
                enumerate(edge + 1);
            }
        };
        enumerate(0);
        require(classes.size() == expected_classes[m], "rooted class count changed");
        std::cout << "Large-graph canonicalization m=" << m << ": " << classes.size() << " classes\n";
    }
}

void test_large_permutations()
{
    std::mt19937 rng(910754);
    // A complete binary discovery tree realizes nine binary branching decisions
    // before the final leaf. Extra edges, loops and repeated ports exercise the
    // remaining comparisons. The first successor cycle guarantees accessibility.
    for (unsigned int sample = 0; sample < 40; ++sample) {
        Table table(20);
        if (sample == 0) {
            for (unsigned int source = 0; source < 20; ++source)
                table[source] = {std::min(19U, 2 * source + 1), std::min(19U, 2 * source + 2)};
        } else {
            for (unsigned int source = 0; source < 20; ++source)
                table[source] = {(source + 1) % 20, rng() % 20};
        }
        const auto canonical = Graph(table).canonical();
        require(canonical.accessible(), "canonical graph lost accessibility");
        require(canonical == canonical.canonical(), "large canonicalization not idempotent");
        require(Graph::from_key(canonical.key()) == canonical, "large key failed round trip");
        for (unsigned int trial = 0; trial < 80; ++trial) {
            std::vector<unsigned int> permutation(20);
            std::iota(permutation.begin(), permutation.end(), 0U);
            std::shuffle(permutation.begin() + 1, permutation.end(), rng);
            Table transformed(20);
            for (unsigned int source = 0; source < 20; ++source) {
                auto& row = transformed[permutation[source]];
                row = {permutation[table[source][0]], permutation[table[source][1]]};
                if (rng() & 1) std::swap(row[0], row[1]);
            }
            require(Graph(std::move(transformed)).canonical() == canonical,
                "large graph class changed under root relabeling and port swaps");
        }
    }
}

void test_validation()
{
    auto throws = [](const auto& function) {
        bool caught = false;
        try { function(); } catch (const std::invalid_argument&) { caught = true; }
        require(caught, "invalid graph input accepted");
    };
    throws([] { Graph graph(Table{}); });
    throws([] { Graph graph(Table(21)); });
    throws([] { Graph graph({{0, 1}}); });
    throws([] { Graph::from_key("000"); });
    throws([] { Graph::from_key("000x"); });
    throws([] { Graph::from_key("0020"); });
    const Graph unreachable({{0, 0}, {1, 1}});
    require(!unreachable.accessible(), "unreachable vertex accepted");
    throws([&] { unreachable.canonical(); });
    require(Graph({{0, 0}}).canonical().ports == Table{{0, 0}}, "one-vertex coincident loop changed");

    // Fixed-width keys compare in the same order as numeric transition tables.
    const Graph a({{1, 1}, {2, 2}, {3, 3}, {4, 4}, {5, 5}, {6, 6}, {7, 7},
        {8, 8}, {9, 9}, {10, 10}, {11, 11}, {0, 0}});
    auto b = a;
    b.ports[0] = {2, 2};
    require(a.ports < b.ports && a.key() < b.key(), "key numeric ordering changed");
}
}

int main()
{
    try {
        test_all_small_tables();
        test_large_permutations();
        test_validation();
        std::cout << "Large Family 1 graph regression tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Large graph regression failure: " << error.what() << '\n';
        return 1;
    }
}

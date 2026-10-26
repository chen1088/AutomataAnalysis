#include "Family1LargeEnumerator.h"

#include <algorithm>
#include <chrono>
#include <functional>
#include <iostream>
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

bool brute_accessible(const Table& table)
{
    std::set<unsigned int> reached{0};
    std::vector<unsigned int> pending{0};
    while (!pending.empty()) {
        const auto source = pending.back();
        pending.pop_back();
        for (auto target : table[source])
            if (reached.insert(target).second) pending.push_back(target);
    }
    return reached.size() == table.size();
}

// A separate canonicalizer tries every root-fixing permutation, with no
// discovery-order reduction. permutation maps old vertex names to new names.
Table brute_canonical(const Table& table)
{
    std::vector<unsigned int> permutation(table.size());
    std::iota(permutation.begin(), permutation.end(), 0U);
    Table best;
    do {
        Table current(table.size());
        for (unsigned int old = 0; old < table.size(); ++old) {
            current[permutation[old]] = {
                permutation[table[old][0]], permutation[table[old][1]]};
            std::sort(current[permutation[old]].begin(), current[permutation[old]].end());
        }
        if (best.empty() || current < best) best = std::move(current);
    } while (std::next_permutation(permutation.begin() + 1, permutation.end()));
    return best;
}

std::set<Table> brute_classes(unsigned int states)
{
    Table table(states);
    std::set<Table> classes;
    // Generate ALL ordered labelled tables, independently of restricted growth
    // and of sorted rows in the production enumerator.
    const auto recurse = [&](auto&& self, unsigned int port) -> void {
        if (port == 2 * states) {
            if (brute_accessible(table)) classes.insert(brute_canonical(table));
            return;
        }
        for (unsigned int target = 0; target < states; ++target) {
            table[port / 2][port % 2] = target;
            self(self, port + 1);
        }
    };
    recurse(recurse, 0);
    return classes;
}

void check_small_classes()
{
    constexpr unsigned int expected_counts[]{0, 1, 6, 57, 678, 10398, 192181};
    for (unsigned int states = 1; states <= 6; ++states) {
        const family1::LargeEnumerator enumerator(states);
        require(enumerator.size() == states, "enumerator reports the wrong size");
        std::set<Table> classes;
        Table previous;
        const auto started = std::chrono::steady_clock::now();
        require(enumerator.enumerate([&](const family1::LargeGraph& graph) {
            require(graph.size() == states && brute_accessible(graph.ports), "invalid or inaccessible graph enumerated");
            require(previous.empty() || previous < graph.ports, "class order is not strict lexicographic order");
            require(classes.insert(graph.ports).second, "duplicate rooted class enumerated");
            if (states <= 4)
                require(brute_canonical(graph.ports) == graph.ports, "independent canonical table differs");
            previous = graph.ports;
            return true;
        }), "complete enumeration reported interruption");
        require(classes.size() == expected_counts[states], "known rooted class count differs");
        if (states <= 4)
            require(classes == brute_classes(states), "complete class set differs from exhaustive ordered-labelled generation");
        // Replay a short prefix twice. A false visitor return must stop without
        // subsequent callbacks and must be reported as incomplete traversal.
        std::vector<Table> prefix;
        const auto length = std::min<std::size_t>(3, classes.size());
        require(!enumerator.enumerate([&](const family1::LargeGraph& graph) {
            prefix.push_back(graph.ports);
            return prefix.size() < length;
        }), "visitor stop was reported as exhaustive completion");
        require(prefix.size() == length, "visitor was called after it requested termination");
        auto wanted = classes.begin();
        for (const auto& table : prefix) require(table == *wanted++, "restart changed the ordinal order");
        std::size_t index = 0;
        require(!enumerator.enumerate([&](const family1::LargeGraph& graph) {
            require(graph.ports == prefix.at(index++), "second restart changed the ordinal order");
            return index < prefix.size();
        }), "second stopped run was reported as complete");
        std::cout << "Large enumeration m=" << states << ": " << classes.size()
                  << " classes, " << std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count()
                  << " s\n";
    }
}

void check_range_and_termination()
{
    for (unsigned int invalid : {0U, 21U}) {
        bool threw = false;
        try { const family1::LargeEnumerator bad(invalid); }
        catch (const std::invalid_argument&) { threw = true; }
        require(threw, "invalid enumeration size accepted");
    }
    bool threw = false;
    try { family1::LargeEnumerator(1).enumerate({}); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "empty enumeration visitor accepted");
    for (unsigned int states = 7; states <= 20; ++states) {
        unsigned int calls = 0;
        Table previous;
        require(!family1::LargeEnumerator(states).enumerate([&](const family1::LargeGraph& graph) {
            require(graph.accessible() && graph.size() == states, "large prefix contains invalid graph");
            require(previous.empty() || previous < graph.ports, "large prefix order differs");
            require(graph.canonical().ports == graph.ports, "large prefix contains a noncanonical graph");
            previous = graph.ports;
            return ++calls < 3;
        }), "partial large enumeration claimed completion");
        require(calls == 3, "large enumeration ignored visitor termination");
    }
}

void benchmark_m7_prefix()
{
    constexpr unsigned int limit = 100000;
    unsigned int calls = 0;
    Table previous;
    const auto started = std::chrono::steady_clock::now();
    require(!family1::LargeEnumerator(7).enumerate([&](const family1::LargeGraph& graph) {
        require(previous.empty() || previous < graph.ports, "m=7 benchmark order differs");
        previous = graph.ports;
        return ++calls < limit;
    }), "m=7 stopped benchmark claimed exhaustive completion");
    require(calls == limit, "m=7 benchmark did not reach the requested prefix");
    std::cout << "m=7 prefix benchmark: " << calls << " canonical classes in "
              << std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count()
              << " s (interrupted; no exhaustive m=7 claim)\n";
}
}

int main(int argc, char** argv)
{
    try {
        check_small_classes();
        check_range_and_termination();
        if (argc == 2 && std::string(argv[1]) == "--benchmark-m7") benchmark_m7_prefix();
        else require(argc == 1, "unknown test argument");
        std::cout << "Large enumerator regression tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Large enumerator regression failure: " << error.what() << '\n';
        return 1;
    }
}

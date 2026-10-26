#include "GraphBasedPDFAEnumerator.h"
#include <algorithm>
#include <numeric>
#include <stdexcept>

Family1Graph::Family1Graph(std::vector<Row> table)
    : TwoRegularDigraph(static_cast<unsigned int>(table.size())), ports(std::move(table))
{
    if (size == 0 || size > 6) throw std::invalid_argument("Family 1 backend requires 1 <= m <= 6");
    for (const auto& row : ports)
        for (auto target : row)
            if (target >= size) throw std::invalid_argument("transition target outside seed");
}
unsigned int Family1Graph::get_next_v(unsigned int state, bool port) { return ports.at(state)[port]; }
void Family1Graph::set_next_v(unsigned int state, bool port, unsigned int value)
{
    if (value >= size) throw std::out_of_range("transition target outside seed");
    ports.at(state)[port] = value;
}
void Family1Graph::set_e0(std::vector<unsigned int> edges)
{
    if (edges.size() != size) throw std::invalid_argument("wrong edge count");
    for (unsigned int s = 0; s < size; ++s) set_next_v(s, false, edges[s]);
}
void Family1Graph::set_e1(std::vector<unsigned int> edges)
{
    if (edges.size() != size) throw std::invalid_argument("wrong edge count");
    for (unsigned int s = 0; s < size; ++s) set_next_v(s, true, edges[s]);
}
bool Family1Graph::accessible() const
{
    unsigned int seen = 1;
    for (;;) {
        auto previous = seen;
        for (unsigned int s = 0; s < size; ++s)
            if (seen & (1U << s)) seen |= (1U << ports[s][0]) | (1U << ports[s][1]);
        if (seen == previous) return seen == ((1U << size) - 1);
    }
}
std::string Family1Graph::key() const
{
    std::string result;
    for (const auto& row : ports) for (auto v : row) result += static_cast<char>('0' + v);
    return result;
}

GraphBasedPDFAEnumerator::GraphBasedPDFAEnumerator(unsigned int states) : states_(states)
{
    if (states == 0 || states > 6) throw std::invalid_argument("enumeration supports 1 <= m <= 6");
}

namespace {
// permutation[new vertex] = old vertex. Sorting each relabelled row quotients
// precisely the independent port swaps, including loops and coincident ports.
std::vector<Family1Graph::Row> relabel(const Family1Graph& graph, const std::vector<unsigned int>& permutation)
{
    std::vector<unsigned int> inverse(graph.size);
    for (unsigned int s = 0; s < graph.size; ++s) inverse[permutation[s]] = s;
    std::vector<Family1Graph::Row> result(graph.size);
    for (unsigned int s = 0; s < graph.size; ++s) {
        auto a = inverse[graph.ports[permutation[s]][0]];
        auto b = inverse[graph.ports[permutation[s]][1]];
        result[s] = {std::min(a, b), std::max(a, b)};
    }
    return result;
}
}

Family1Graph GraphBasedPDFAEnumerator::canonical(const Family1Graph& graph)
{
    std::vector<unsigned int> permutation(graph.size);
    std::iota(permutation.begin(), permutation.end(), 0U);
    auto best = relabel(graph, permutation);
    while (std::next_permutation(permutation.begin() + 1, permutation.end()))
        best = std::min(best, relabel(graph, permutation));
    return Family1Graph(std::move(best));
}

bool GraphBasedPDFAEnumerator::is_canonical(const Family1Graph& graph)
{
    std::array<unsigned int, 6> permutation{0, 1, 2, 3, 4, 5};
    do {
        std::array<unsigned int, 6> inverse{};
        for (unsigned int s = 0; s < graph.size; ++s) inverse[permutation[s]] = s;
        for (unsigned int s = 0; s < graph.size; ++s) {
            auto a = inverse[graph.ports[permutation[s]][0]];
            auto b = inverse[graph.ports[permutation[s]][1]];
            Family1Graph::Row row{std::min(a, b), std::max(a, b)};
            if (row < graph.ports[s]) return false;
            if (row > graph.ports[s]) break;
        }
    } while (std::next_permutation(permutation.begin() + 1, permutation.begin() + graph.size));
    return true;
}

bool GraphBasedPDFAEnumerator::enumerate(const std::function<bool(const Family1Graph&)>& visit) const
{
    Family1Graph graph{std::vector<Family1Graph::Row>(states_)};
    // Canonical accessible tables have restricted growth: the first target not
    // already named must get the smallest unused label. At row s, s must have
    // been discovered. This is an enumeration reduction, not an extra graph
    // hypothesis. The full permutation test below removes remaining duplicates.
    std::function<bool(unsigned int, unsigned int)> recurse = [&](unsigned int row, unsigned int known) {
        if (row == states_) return !is_canonical(graph) || visit(graph);
        if (row >= known) return true;
        for (unsigned int a = 0; a < states_ && a <= known; ++a) {
            auto after_a = std::max(known, a + 1);
            for (unsigned int b = a; b < states_ && b <= after_a; ++b) {
                graph.ports[row] = {a, b};
                if (!recurse(row + 1, std::max(after_a, b + 1))) return false;
            }
        }
        return true;
    };
    return recurse(0, 1);
}

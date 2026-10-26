#include "Family1LargeGraph.h"
#include <algorithm>
#include <cstdint>
#include <functional>
#include <stdexcept>
#include <utility>

namespace family1 {

LargeGraph::LargeGraph(std::vector<Row> table) : ports(std::move(table))
{
    validate();
}

void LargeGraph::validate() const
{
    if (ports.empty() || ports.size() > 20)
        throw std::invalid_argument("large Family 1 seeds require 1 <= m <= 20");
    for (const auto& row : ports)
        for (auto target : row)
            if (target >= ports.size())
                throw std::invalid_argument("transition target outside seed");
}

bool LargeGraph::accessible() const
{
    validate();
    std::uint32_t seen = 1;
    for (;;) {
        const auto previous = seen;
        for (unsigned int source = 0; source < size(); ++source)
            if (seen & (1U << source))
                seen |= (1U << ports[source][0]) | (1U << ports[source][1]);
        if (seen == previous) return seen == ((1U << size()) - 1);
    }
}

LargeGraph LargeGraph::canonical() const
{
    if (!accessible())
        throw std::invalid_argument("large graph canonicalization requires root accessibility");

    // The least root-fixed, row-sorted table has discovery labels: while rows
    // are scanned in increasing order, every first unseen target receives the
    // smallest unused label. Otherwise exchanging that target with the skipped
    // label decreases the first differing table entry. Accessibility also means
    // each source is discovered before its row is processed.
    //
    // Only a row with TWO distinct unseen targets has a labeling choice. Both
    // assignments must be considered because the source ports are unordered.
    // Each such branch consumes two vertices, so an m-vertex graph has at most
    // 2^floor((m-1)/2) leaves (512 for m=20), rather than (m-1)! permutations.
    std::array<int, 20> old_to_new;
    old_to_new.fill(-1);
    std::array<unsigned int, 20> new_to_old{};
    old_to_new[0] = 0;
    new_to_old[0] = 0;
    std::vector<Row> current(size());
    std::vector<Row> best;

    std::function<void(unsigned int, unsigned int)> discover;
    discover = [&](unsigned int row, unsigned int known) {
        if (row == size()) {
            if (best.empty() || current < best) best = current;
            return;
        }
        if (row >= known) throw std::logic_error("accessible graph discovery stopped early");

        const auto a = ports[new_to_old[row]][0];
        const auto b = ports[new_to_old[row]][1];
        const bool new_a = old_to_new[a] < 0;
        const bool new_b = old_to_new[b] < 0;

        auto continue_row = [&](unsigned int next_known) {
            const auto first = static_cast<unsigned int>(old_to_new[a]);
            const auto second = static_cast<unsigned int>(old_to_new[b]);
            current[row] = {std::min(first, second), std::max(first, second)};
            if (!best.empty()) {
                for (unsigned int prefix = 0; prefix <= row; ++prefix) {
                    if (current[prefix] > best[prefix]) return;
                    if (current[prefix] < best[prefix]) break;
                }
            }
            discover(row + 1, next_known);
        };

        if (new_a && new_b && a != b) {
            old_to_new[a] = static_cast<int>(known);
            old_to_new[b] = static_cast<int>(known + 1);
            new_to_old[known] = a;
            new_to_old[known + 1] = b;
            continue_row(known + 2);

            old_to_new[a] = static_cast<int>(known + 1);
            old_to_new[b] = static_cast<int>(known);
            new_to_old[known] = b;
            new_to_old[known + 1] = a;
            continue_row(known + 2);
            old_to_new[a] = old_to_new[b] = -1;
        } else if (new_a || new_b) {
            const auto unseen = new_a ? a : b;
            old_to_new[unseen] = static_cast<int>(known);
            new_to_old[known] = unseen;
            continue_row(known + 1);
            old_to_new[unseen] = -1;
        } else {
            continue_row(known);
        }
    };
    discover(0, 1);
    return LargeGraph(std::move(best));
}

std::string LargeGraph::key() const
{
    validate();
    std::string result;
    result.reserve(ports.size() * 4);
    for (const auto& row : ports)
        for (auto target : row) {
            result.push_back(static_cast<char>('0' + target / 10));
            result.push_back(static_cast<char>('0' + target % 10));
        }
    return result;
}

LargeGraph LargeGraph::from_key(const std::string& key)
{
    if (key.empty() || key.size() % 4 != 0 || key.size() > 80
        || key.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("invalid large graph key");
    std::vector<Row> table(key.size() / 4);
    for (std::size_t source = 0; source < table.size(); ++source)
        for (unsigned int port = 0; port < 2; ++port) {
            const auto offset = source * 4 + port * 2;
            table[source][port] = 10U * (key[offset] - '0') + (key[offset + 1] - '0');
        }
    return LargeGraph(std::move(table));
}

}

#include "Family1LargeEnumerator.h"

#include <algorithm>
#include <stdexcept>
#include <vector>

namespace family1 {

LargeEnumerator::LargeEnumerator(unsigned int states) : states_(states)
{
    if (states == 0 || states > 20)
        throw std::invalid_argument("large Family 1 enumeration requires 1 <= m <= 20");
}

bool LargeEnumerator::enumerate(const std::function<bool(const LargeGraph&)>& visit) const
{
    if (!visit) throw std::invalid_argument("large Family 1 enumeration requires a visitor");
    LargeGraph graph{std::vector<LargeGraph::Row>(states_)};

    // In the lexicographically least table each first unseen target must take
    // the smallest unused label. Exchanging it with a skipped label otherwise
    // decreases the first differing entry. Row sorting accounts exactly for
    // independent port swaps; a source must already have been discovered when
    // its row is scanned. Every accessible rooted class has such a discovery
    // labelling, even when it has loops, coincident ports or transient states.
    //
    // Restricted growth still permits both discovery orders when a row names
    // two different new vertices. Exact canonicalization at complete leaves
    // removes these remaining duplicates, preserving one class representative.
    const auto recurse = [&](auto&& self, unsigned int row, unsigned int known) -> bool {
        if (row == states_) {
            if (known != states_)
                throw std::logic_error("incomplete discovery reached an enumeration leaf");
            return graph.canonical().ports != graph.ports || visit(graph);
        }
        if (row >= known) return true;
        // Even giving every remaining port a fresh target cannot finish.
        if (known + 2 * (states_ - row) < states_) return true;
        const auto largest_a = std::min(states_ - 1, known);
        for (unsigned int a = 0; a <= largest_a; ++a) {
            const auto after_a = std::max(known, a + 1);
            const auto largest_b = std::min(states_ - 1, after_a);
            for (unsigned int b = a; b <= largest_b; ++b) {
                const auto after_b = std::max(after_a, b + 1);
                if (after_b + 2 * (states_ - row - 1) < states_) continue;
                graph.ports[row] = {a, b};
                if (!self(self, row + 1, after_b)) return false;
            }
        }
        return true;
    };
    return recurse(recurse, 0, 1);
}

}

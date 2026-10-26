#pragma once

#include "Family1LargeGraph.h"
#include <functional>

namespace family1 {

// Exact enumeration of rooted accessible seeds, modulo root-preserving vertex
// relabelling and independent outgoing-port swaps. There is no strong
// connectivity or indegree assumption. Supports the graph domain 1 <= m <= 20;
// this range describes validity, not a promise that every size is tractable.
class LargeEnumerator {
public:
    explicit LargeEnumerator(unsigned int states);
    unsigned int size() const { return states_; }

    // Canonical tables arrive once each, in strictly increasing lexicographic
    // order. The callback number starting at zero is a reproducible ordinal.
    // A false callback return stops immediately and this function returns
    // false. Only complete exhaustion returns true. Repeated calls restart the
    // same ordering. The graph reference is valid only during the callback.
    bool enumerate(const std::function<bool(const LargeGraph&)>& visit) const;

private:
    unsigned int states_;
};

}

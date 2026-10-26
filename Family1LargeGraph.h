#pragma once
#include <array>
#include <string>
#include <vector>

namespace family1 {

// Finite seeds for the symbolic search. This deliberately does not inherit the
// legacy reset graph's additional sink or the six-vertex bitplane restriction.
class LargeGraph {
public:
    using Row = std::array<unsigned int, 2>;
    std::vector<Row> ports;

    explicit LargeGraph(std::vector<Row> table);
    unsigned int size() const { return static_cast<unsigned int>(ports.size()); }
    void validate() const;
    bool accessible() const;

    // Exact lexicographically least transition table under root-fixing vertex
    // permutations and independent port swaps. Requires root accessibility.
    LargeGraph canonical() const;

    // Fixed two-digit destinations, four characters per vertex. For canonical
    // graphs this is a stable class identifier and preserves numeric ordering.
    std::string key() const;
    static LargeGraph from_key(const std::string& key);

    bool operator==(const LargeGraph&) const = default;
};

}

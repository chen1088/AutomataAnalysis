#pragma once
#include "GraphBasedPDFAEnumerator.h"
#include <array>
#include <csignal>
#include <cstdint>
#include <string>

namespace family1 {
struct Profile {
    // Endpoint vector encoded without loss as three bitplanes, one bit/mask.
    std::array<std::uint64_t, 3> planes{};
    bool operator==(const Profile&) const = default;
};
struct Score {
    std::string status = "incomplete";
    unsigned int merge_length = 0;
    unsigned int lower_bound = 1; // H >= lower_bound
    std::array<std::string, 2> witness{};
    std::string reason;
};
struct Limits {
    unsigned int depth = 30;
    std::uint64_t max_layer_states = 1ULL << 24;
    const volatile std::sig_atomic_t* interrupted = nullptr;
    bool force_hash_collisions = false; // test complete-state equality
};
class Product {
public:
    explicit Product(const Family1Graph& graph);
    Profile step(const Profile& state, bool input) const;
    Profile evaluate(const std::string& word) const;
    unsigned int endpoint(const Profile& state, unsigned int mask) const;
private:
    std::array<std::array<std::array<std::uint64_t, 3>, 6>, 2> destinations_{};
    unsigned int size_;
};
Score score(const Family1Graph& graph, const Limits& limits = {});
}

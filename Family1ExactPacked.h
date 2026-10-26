#pragma once
#include "Family1LargeGraph.h"
#include <array>
#include <csignal>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace family1 {

struct PackedLimits {
    unsigned int depth = 31;
    std::uint64_t max_layer_states = 1ULL << 24;
    // Bound on allocated array payload, including product tables, profile
    // chunks, hash indices and scratch space. Allocator/runtime overhead is
    // outside this bound. No profile-vector reallocations are performed.
    std::uint64_t max_working_bytes = 2ULL << 30;
    std::uint64_t timeout_ms = 0; // zero means no clock limit
    const volatile std::sig_atomic_t* interrupted = nullptr;
    bool force_hash_collisions = false; // regression: still compare all planes
    // Store words beginning with 0 and compare profiles up to simultaneous
    // complement of every mask bit. This accounts for ALL words: the other
    // half are exactly their bitwise-complement words. max_layer_states still
    // bounds the full 2^depth words, rather than only stored representatives.
    bool quotient_complements = true;
};

struct PackedScore {
    std::string status = "incomplete";
    unsigned int merge_length = 0; // nonzero only when exact
    unsigned int lower_bound = 1; // H >= lower_bound
    std::array<std::string, 2> witness{};
    std::string reason;
    unsigned int effective_mask_bits = 0;
    unsigned int mask_count = 0;
    unsigned int profile_planes = 0;
    std::uint64_t peak_working_bytes = 0;
    std::uint64_t evaluated_words = 0; // includes derived complement words
    std::uint64_t profiles_evaluated = 0; // physically expanded representatives
    double seconds = 0;
};

// Complete product over all static masks, packed into state-bit planes. A mask
// bit is omitted only when its vertex has coincident ports: changing that bit
// changes no transition, on any revisit. Every remaining bit is retained.
// endpoint() accepts the ORIGINAL m-bit mask, including omitted bits.
class ExactPackedProduct {
public:
    using Profile = std::vector<std::uint64_t>;
    explicit ExactPackedProduct(const LargeGraph& graph);
    Profile step(const Profile& state, bool input) const;
    Profile evaluate(const std::string& word) const;
    unsigned int endpoint(const Profile& state, std::uint32_t full_mask) const;
    unsigned int effective_mask_bits() const { return effective_bits_; }
    unsigned int mask_count() const { return masks_; }
    unsigned int profile_planes() const { return width_ * blocks_; }

private:
    unsigned int size_, width_, blocks_, masks_, effective_bits_;
    std::array<int, 20> mask_positions_{};
    std::unique_ptr<std::uint64_t[]> destinations_;
    // Source and destination must not overlap.
    void step_into(const std::uint64_t* source, bool input, std::uint64_t* destination) const;
    friend PackedScore score_packed(const LargeGraph&, const PackedLimits&);
};

// Exact individual scoring, not a claim of exhaustive graph enumeration.
// A fresh complete-state table is used at each positive length. Before the
// first collision, word indices are binary lexicographic word numbers. Reverse
// in-place expansion preserves parents and avoids storing two full layers.
PackedScore score_packed(const LargeGraph& graph, const PackedLimits& limits = {});

}

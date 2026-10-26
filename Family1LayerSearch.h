#pragma once
#include "Family1LargeGraph.h"
#include <array>
#include <csignal>
#include <cstdint>
#include <string>

namespace family1 {
struct LayerLimits {
    unsigned int depth = 20; // one equal-length layer; 0 gives only H >= 1
    std::uint64_t max_layer_states = 1ULL << 24; // ALL words, including complements
    std::uint64_t max_working_bytes = 64ULL << 20;
    std::uint64_t timeout_ms = 0;
    const volatile std::sig_atomic_t* interrupted = nullptr;
    bool force_hash_collisions = false;
    // Indexed mode uses 16 bytes/word and replays only matching words. Compact
    // mode uses 8 bytes/word and regenerates a layer for each repeated hash.
    bool retain_word_indices = true;
    // At depths <=27, encode the index into the low depth-1 bits of an 8-byte
    // entry. The remaining fingerprint bits are only an accelerator; every
    // matching fingerprint is replayed against all 128 mask coordinates.
    bool pack_word_indices = true;
};
struct LayerScore {
    std::string status = "incomplete"; // collision, collision-free, incomplete
    unsigned int lower_bound = 1;
    unsigned int upper_bound = 0;
    std::array<std::string, 2> witness{};
    std::string reason;
    std::uint64_t generated_representatives = 0;
    std::uint64_t hash_matches_replayed = 0;
    std::uint64_t peak_working_bytes = 0;
    double seconds = 0;
};

// Fixed seven-state COMPLETE 128-static-mask product. Generates only words
// beginning with 0, accounting for their complements by reversing mask
// coordinates. Stores a 64-bit fingerprint and optionally its word index per
// representative; repeated fingerprints are NEVER accepted as collisions
// without complete-state replay.
//
// This searches one layer, not all shortest lengths: collision => H <= depth;
// collision-free => H >= depth+1 because every shorter collision extends by a
// common suffix. A collision is exact only when combined with a matching
// separately certified lower bound. Supports depths 0..33 with resource caps.
LayerScore search_layer(const LargeGraph& graph, const LayerLimits& limits = {});
}

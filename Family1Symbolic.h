#pragma once
#include "Family1LargeGraph.h"
#include <array>
#include <csignal>
#include <cstdint>
#include <string>
#include <vector>

namespace family1 {
struct SymbolicLimits {
    unsigned int max_length = 64;
    unsigned int max_refinements = 256;
    unsigned int projection_depth = 20;
    unsigned int projection_masks = 64;
    std::uint32_t projection_seed = 0x46414d31U;
    std::uint64_t projection_max_states = 1ULL << 20;
    std::uint64_t timeout_ms = 10000; // aggregate per graph/query, including encoding
    std::uint64_t solve_timeout_ms = 2000;
    const volatile std::sig_atomic_t* interrupted = nullptr;
};
enum class LengthDecision { collision, no_collision, unknown };
struct SymbolicDecision {
    LengthDecision decision = LengthDecision::unknown;
    std::array<std::string, 2> witness;
    std::string reason;
    unsigned int refinements = 0;
};
enum class WitnessDecision { universal_collision, counterexample, unknown };
struct WitnessCheck {
    WitnessDecision decision = WitnessDecision::unknown;
    std::uint32_t counterexample_mask = 0;
    std::string reason;
};
struct SymbolicScore {
    std::string status = "incomplete";
    unsigned int lower_bound = 1;
    unsigned int upper_bound = 0; // zero means unknown, never an exact score
    std::array<std::string, 2> witness;
    std::string reason;
    unsigned int queries = 0;
    unsigned int mask_count = 0;
    unsigned int projection_lower_bound = 1;
    unsigned int projection_mask_count = 0;
    double seconds = 0;
};
WitnessCheck verify_witness(const LargeGraph& graph, const std::array<std::string, 2>& words,
                           const SymbolicLimits& limits = {});
SymbolicDecision decide_length(const LargeGraph& graph, unsigned int length,
                               std::vector<std::uint32_t>& sampled_masks,
                               const SymbolicLimits& limits = {});
SymbolicScore certify(const LargeGraph& graph, const SymbolicLimits& limits = {});
}

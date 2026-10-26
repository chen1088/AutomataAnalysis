#pragma once
#include "Family1LargeGraph.h"
#include <array>
#include <csignal>
#include <cstdint>
#include <string>
#include <vector>

namespace family1 {

enum class SynthesisDecision { impossible, challenger, unknown };
inline constexpr const char* synthesis_encoder_v1 = "family1-accessible-prior-incoming-static-mask-separation-cnf-v1";
inline constexpr const char* synthesis_encoder_v2 = "family1-accessible-discovery-static-mask-separation-cnf-v2";

struct SynthesisLimits {
    std::uint64_t timeout_ms = 30000; // Aggregate encoding, graph SAT, and candidate scoring.
    std::uint64_t solve_timeout_ms = 2000;
    std::uint64_t candidate_timeout_ms = 5000;
    unsigned int max_candidates = 256;
    unsigned int max_refinements = 256;
    unsigned int max_postponed_models = 256;
    std::uint64_t candidate_max_layer_states = 1ULL << 24;
    std::uint64_t candidate_max_working_bytes = 2ULL << 30;
    bool discovery_labels = false; // Optional complete BFS discovery-label reduction.
    const volatile std::sig_atomic_t* interrupted = nullptr;
};

struct PostponedCandidate {
    std::string key;
    std::vector<LargeGraph::Row> table;
    unsigned int lower_bound = 1;
    unsigned int upper_bound = 0;
    std::string reason;
};

struct SynthesisResult {
    std::string encoder_version = synthesis_encoder_v1;
    SynthesisDecision decision = SynthesisDecision::unknown;
    unsigned int states = 0;
    unsigned int threshold = 0;
    unsigned int proven_upper_bound = 0; // Only nonzero after graph SAT is UNSAT.
    unsigned int challenger_lower_bound = 0; // Only nonzero for a certified challenger.
    std::vector<LargeGraph::Row> challenger_table;
    std::string challenger_key;
    std::string reason;
    unsigned int candidates_checked = 0;
    unsigned int sat_variables = 0;
    std::uint64_t sat_clauses = 0;
    // Search may temporarily exclude unresolved labelled models by guarded
    // assumptions. These exclusions NEVER enter a certificate or replay CNF.
    unsigned int postponed_models = 0;
    unsigned int search_sat_variables = 0;
    std::uint64_t search_sat_clauses = 0;
    std::vector<PostponedCandidate> postponed_candidates;
    double seconds = 0;
    std::string cnf; // Exact DIMACS graph formula, populated only on certified UNSAT.
    // Generated pairs were universally verified on rejected candidates; initial
    // pairs may be any valid equal-length pair of length <= threshold. Every
    // H>threshold graph must separate EACH such pair, so replay does not need
    // to trust the learner. These pairs and the encoder version reconstruct CNF.
    std::vector<std::array<std::string, 2>> learned_pairs;
};

// Searches ALL rooted accessible m-state graph classes for H(G) > threshold.
// "impossible" proves the global upper bound H(G) <= threshold, but does not
// enumerate all graphs attaining that bound or prove that it is attained.
// "challenger" provides one graph with H(G) >= threshold+1.
// UNKNOWN preserves no global non-improvability conclusion.
SynthesisResult synthesize_challenger(unsigned int states, unsigned int threshold,
                                     const SynthesisLimits& limits = {},
    const std::vector<std::array<std::string, 2>>& initial_pairs = {});

// Independently reconstructs the necessary graph constraints from a saved
// learned-pair collection. UNSAT proves the same global upper bound; SAT says
// only that this collection does not prove it, never that a challenger exists.
SynthesisResult replay_synthesis_upper_bound(unsigned int states, unsigned int threshold,
    const std::vector<std::array<std::string, 2>>& learned_pairs,
    const SynthesisLimits& limits = {});

}

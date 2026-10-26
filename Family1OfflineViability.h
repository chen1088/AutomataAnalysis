#pragma once
#include "Family1PairAgreement.h"
#include "HardPairViability.h"
#include <algorithm>
#include <cstdint>
#include <functional>
#include <limits>
#include <sstream>
#include <unordered_map>

namespace family1::offline {

// The cache concerns a FIXED prefix pair in individual static-mask DFAs.
// A negative coordinate excludes a common suffix for that prefix pair only.
// It never supplies a lower bound on H of the graph or excludes the graph.
class ViabilityCache {
public:
    ViabilityCache(const LargeGraph& graph, unsigned int coordinates,
                   unsigned int distances, std::function<void()> check,
                   const volatile std::sig_atomic_t* interrupted)
        : graph_(graph), coordinates_(coordinates), distances_(distances),
          check_(std::move(check)), interrupted_(interrupted)
    {
        for (unsigned int s = 0; s < graph.size(); ++s)
            if (graph.ports[s][0] != graph.ports[s][1]) relevant_ |= 1U << s;
    }

    bool has_obstruction(const ExactPairAgreement& pair)
    {
        ++checks_;
        if (!coordinates_) return false;
        for (const auto& triple : pair.remaining_coordinate_pairs(coordinates_)) {
            check_(); ++coordinates_checked_;
            const auto* result = table(triple[0]);
            if (result && result->proven_unmergeable(triple[1], triple[2])) {
                ++obstructions_; return true;
            }
        }
        return false;
    }

    std::uint64_t minimum_distance(const ExactPairAgreement& pair)
    {
        ++distance_checks_;
        std::uint64_t bound = 0;
        if (!distances_) return 0;
        for (const auto& triple : pair.remaining_coordinate_pairs(distances_)) {
            check_(); ++distance_coordinates_checked_;
            const auto* result = table(triple[0]);
            if (!result) continue; // An unfinished analysis contributes zero.
            if (result->proven_unmergeable(triple[1], triple[2])) {
                ++obstructions_; return std::numeric_limits<std::uint64_t>::max();
            }
            const auto distance = result->distance[static_cast<std::size_t>(triple[1]) * graph_.size() + triple[2]];
            if (distance == hardpair::PairMergeabilityResult::unreachable_distance)
                throw std::logic_error("complete mergeable coordinate lacks a finite distance");
            bound = std::max(bound, static_cast<std::uint64_t>(distance));
        }
        return bound;
    }

    std::string json() const
    {
        std::ostringstream out;
        out << "{\"coordinate_limit\":" << coordinates_ << ",\"distance_coordinate_limit\":" << distances_
            << ",\"checks\":" << checks_ << ",\"coordinates_checked\":" << coordinates_checked_
            << ",\"distance_checks\":" << distance_checks_ << ",\"distance_coordinates_checked\":" << distance_coordinates_checked_
            << ",\"table_analyses\":" << analyses_ << ",\"unknown_analyses_not_pruned\":" << unknown_
            << ",\"cache_hits\":" << hits_ << ",\"cache_entries\":" << tables_.size() << ",\"cache_resets\":" << resets_
            << ",\"cache_capacity\":4096,\"proven_prefix_obstructions\":" << obstructions_
            << ",\"selection\":\"first N unmerged original mask IDs; hits and misses both consume the coordinate limit\""
            << ",\"statistics_scope\":\"latest graph/window pass; cache shared across prefixes and reset on a new pass or resume\""
            << ",\"distance_rule\":\"maximum complete individual-DFA shortest merge distance; unknown contributes zero\""
            << ",\"graph_score_lower_bound_claimed\":false}";
        return out.str();
    }

private:
    const hardpair::PairMergeabilityResult* table(std::uint32_t mask)
    {
        const auto key = mask & relevant_;
        auto found = tables_.find(key);
        if (found != tables_.end()) { ++hits_; return &found->second; }
        hardpair::PairMergeabilityLimits limits;
        limits.max_pair_states = static_cast<std::uint64_t>(graph_.size()) * graph_.size();
        limits.interrupted = interrupted_;
        auto result = hardpair::analyze_pair_mergeability(graph_.size(), [&](std::uint32_t state, bool input) {
            check_(); return graph_.ports[state][static_cast<unsigned int>(input) ^ ((key >> state) & 1U)];
        }, limits);
        ++analyses_;
        if (!result.complete) { ++unknown_; return nullptr; }
        if (tables_.size() >= 4096) { tables_.clear(); ++resets_; }
        return &tables_.emplace(key, std::move(result)).first->second;
    }

    LargeGraph graph_;
    unsigned int coordinates_, distances_;
    std::uint32_t relevant_ = 0;
    std::function<void()> check_;
    const volatile std::sig_atomic_t* interrupted_;
    std::unordered_map<std::uint32_t, hardpair::PairMergeabilityResult> tables_;
    std::uint64_t checks_ = 0, coordinates_checked_ = 0, distance_checks_ = 0, distance_coordinates_checked_ = 0;
    std::uint64_t analyses_ = 0, unknown_ = 0, hits_ = 0, resets_ = 0, obstructions_ = 0;
};

}

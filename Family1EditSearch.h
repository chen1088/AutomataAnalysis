#pragma once
#include "Family1LargeGraph.h"
#include <array>
#include <csignal>
#include <cstdint>
#include <string>
#include <vector>

namespace family1::edit {

enum class Kind { Retarget, InsertTwoEdges, InsertLoop, SmoothTwoEdges, SmoothLoop };
const char* kind_name(Kind kind);
struct EdgeOccurrence { unsigned int source = 0, port = 0, target = 0; };
struct Operation {
    Kind kind = Kind::Retarget;
    unsigned int vertex = 0, new_target = 0;
    std::vector<EdgeOccurrence> edges;
    LargeGraph::Row outgoing{};
    std::vector<unsigned int> outgoing_ports;
};
struct Step { LargeGraph before, raw_after_edit, after; Operation operation; };

// Every distinct accessible rooted neighbor, with one primitive witness per
// kind/neighbor. No indegree or strong-connectivity restriction is imposed.
std::vector<Step> unit_edits(const LargeGraph& graph, Kind kind);
// Independently useful for replay: validates an operation and rebuilds its
// ordered table. Canonical relabeling is not part of this primitive edit.
LargeGraph apply_operation(const LargeGraph& graph, const Operation& operation);

struct Options {
    unsigned int target_m = 0, radius = 1;
    std::uint64_t max_paths = 10000, max_candidates = 1000, seed = 1088;
    bool root_closure = false;
    const volatile std::sig_atomic_t* interrupted = nullptr;
};
struct Path {
    std::uint64_t id = 0;
    std::string parent_key, endpoint_key;
    std::vector<Step> steps;
};
struct RootOrigin {
    std::uint64_t path_id = 0;
    std::string endpoint_key;
    unsigned int root_in_endpoint = 0;
    bool root_fixed_path = false;
};
struct Candidate {
    LargeGraph graph;
    std::string shape_key;
    std::uint64_t discovery_index = 0;
    unsigned int generation_depth = 0;
    std::vector<std::uint64_t> path_ids;
    std::vector<RootOrigin> root_metadata;
};
struct ParentCoverage {
    std::string key;
    std::uint64_t raw_proposals = 0, accepted_paths = 0;
    std::array<std::uint64_t, 5> pattern_paths{}, pattern_proposals{};
};
struct DepthCoverage {
    unsigned int depth = 0;
    std::uint64_t frontier_nodes = 0, raw_proposals = 0, accepted_paths = 0, new_rooted_candidates = 0;
    bool complete = false, path_capped = false, candidate_capped = false;
};
struct Result {
    std::vector<Path> paths; // Includes a distance-zero base path per parent.
    std::vector<Candidate> candidates; // Deterministic discovery order.
    std::vector<ParentCoverage> parents;
    std::vector<DepthCoverage> depths;
    std::uint64_t accepted_paths = 0, raw_proposals = 0, inaccessible_rejected = 0;
    std::uint64_t same_class_rejected = 0, duplicate_neighbors_rejected = 0;
    std::uint64_t root_fixed_candidate_count = 0, size_bound_pruned = 0;
    bool enumeration_complete = false, supported_universe_complete = false;
    bool unsupported_size_paths_possible = false, interrupted = false;
    bool path_capped = false, candidate_capped = false;
    double seconds = 0;
};

// Budgeted breadth layers receive fair shares of remaining work; parents and
// primitive patterns are round-robin within each layer. This deliberately
// reaches deeper layers without exhausting an explosive earlier layer.
// A cap never proves exclusion of an unvisited class. Sizes1..20 supported.
Result search(const std::vector<LargeGraph>& parents, const Options& options);

}

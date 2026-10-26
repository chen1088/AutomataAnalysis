#include "Family1EditSearch.h"
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <stdexcept>
#include <tuple>

namespace family1::edit {
namespace {
std::uint64_t mix(std::uint64_t value) {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}
std::uint64_t text_hash(const std::string& text) {
    std::uint64_t value = 1469598103934665603ULL;
    for (unsigned char c : text) { value ^= c; value *= 1099511628211ULL; }
    return value;
}
void require(bool condition, const char* message) { if (!condition) throw std::invalid_argument(message); }
int size_change(Kind kind) {
    if (kind == Kind::InsertTwoEdges || kind == Kind::InsertLoop) return 1;
    if (kind == Kind::SmoothTwoEdges || kind == Kind::SmoothLoop) return -1;
    return 0;
}
std::vector<EdgeOccurrence> incoming(const LargeGraph& graph, unsigned int vertex) {
    std::vector<EdgeOccurrence> edges;
    for (unsigned int s = 0; s < graph.size(); ++s) if (s != vertex)
        for (unsigned int p = 0; p < 2; ++p) if (graph.ports[s][p] == vertex) edges.push_back({s,p,vertex});
    return edges;
}
std::vector<Operation> inverse_operations(const LargeGraph& graph, Kind kind) {
    std::vector<Operation> result;
    for (unsigned int vertex = 1; vertex < graph.size(); ++vertex) {
        auto edges = incoming(graph, vertex);
        std::vector<unsigned int> outgoing;
        for (unsigned int p = 0; p < 2; ++p) if (graph.ports[vertex][p] != vertex) outgoing.push_back(p);
        const auto count = kind == Kind::SmoothTwoEdges ? 2U : 1U;
        if (edges.size() != count || outgoing.size() != count) continue;
        do { result.push_back({kind,vertex,0,edges,graph.ports[vertex],outgoing}); }
        while (std::next_permutation(outgoing.begin(), outgoing.end()));
    }
    return result;
}

// Compact random-access operation enumeration: a work queue can rotate over
// thousands of frontier nodes without materializing each full neighborhood.
struct ProposalCursor {
    Kind kind;
    std::uint64_t count = 0, emitted = 0, offset = 0, stride = 1;
    std::vector<Operation> inverses;
    ProposalCursor(const LargeGraph& graph, Kind selected, std::uint64_t seed, bool shuffle) : kind(selected) {
        const std::uint64_t edges = 2 * graph.size();
        if (kind == Kind::Retarget) count = edges * (graph.size() - 1);
        else if (kind == Kind::InsertTwoEdges) count = graph.size() < 20 ? edges * (edges - 1) / 2 : 0;
        else if (kind == Kind::InsertLoop) count = graph.size() < 20 ? edges : 0;
        else { inverses = inverse_operations(graph, kind); count = inverses.size(); }
        if (shuffle && count) {
            offset = mix(seed) % count; stride = mix(seed ^ 0x535452494445ULL) % count + 1;
            while (std::gcd(stride, count) != 1) { ++stride; if (stride > count) stride = 1; }
        }
    }
    std::optional<Operation> next(const LargeGraph& graph) {
        if (emitted == count) return std::nullopt;
        auto index = (offset + emitted++ * stride) % count;
        if (kind == Kind::SmoothTwoEdges || kind == Kind::SmoothLoop) return inverses[index];
        Operation operation; operation.kind = kind;
        if (kind == Kind::Retarget) {
            const auto edge = static_cast<unsigned int>(index / (graph.size() - 1));
            const auto old = graph.ports[edge / 2][edge % 2];
            auto target = static_cast<unsigned int>(index % (graph.size() - 1)); if (target >= old) ++target;
            operation.edges.push_back({edge / 2,edge % 2,old}); operation.new_target = target;
        } else if (kind == Kind::InsertLoop) {
            const auto edge = static_cast<unsigned int>(index);
            const auto target = graph.ports[edge / 2][edge % 2];
            operation.vertex = graph.size(); operation.edges.push_back({edge / 2,edge % 2,target});
            operation.outgoing = {target,graph.size()};
        } else {
            unsigned int first = 0; const auto edges = 2 * graph.size();
            while (index >= edges - first - 1) { index -= edges - first - 1; ++first; }
            const auto second = first + 1 + static_cast<unsigned int>(index);
            operation.vertex = graph.size();
            operation.edges = {{first / 2,first % 2,graph.ports[first / 2][first % 2]},
                               {second / 2,second % 2,graph.ports[second / 2][second % 2]}};
            operation.outgoing = {operation.edges[0].target,operation.edges[1].target};
        }
        return operation;
    }
};

LargeGraph reroot(const LargeGraph& graph, unsigned int root) {
    auto label = [root](unsigned int state) { return state == root ? 0U : state == 0 ? root : state; };
    std::vector<LargeGraph::Row> table(graph.size());
    for (unsigned int state = 0; state < graph.size(); ++state)
        table[label(state)] = {label(graph.ports[state][0]),label(graph.ports[state][1])};
    return LargeGraph(std::move(table));
}
struct RootFamily { std::string shape_key; std::vector<std::pair<unsigned int,LargeGraph>> roots; };
RootFamily root_family(const LargeGraph& graph) {
    RootFamily result;
    for (unsigned int root = 0; root < graph.size(); ++root) {
        auto rooted = reroot(graph, root); if (!rooted.accessible()) continue;
        rooted = rooted.canonical(); const auto key = rooted.key();
        if (result.shape_key.empty() || key < result.shape_key) result.shape_key = key;
        result.roots.emplace_back(root,std::move(rooted));
    }
    return result;
}
}

const char* kind_name(Kind kind) {
    switch (kind) {
    case Kind::Retarget: return "retarget";
    case Kind::InsertTwoEdges: return "insert-two-edges";
    case Kind::InsertLoop: return "insert-loop";
    case Kind::SmoothTwoEdges: return "smooth-two-edges";
    case Kind::SmoothLoop: return "smooth-loop";
    }
    throw std::invalid_argument("unknown edit kind");
}

LargeGraph apply_operation(const LargeGraph& graph, const Operation& operation) {
    graph.validate(); auto table = graph.ports;
    std::set<std::pair<unsigned int,unsigned int>> selected;
    for (const auto& edge : operation.edges) {
        require(edge.source < graph.size() && edge.port < 2, "edit occurrence outside graph");
        require(graph.ports[edge.source][edge.port] == edge.target, "edit occurrence target mismatch");
        require(selected.emplace(edge.source,edge.port).second, "edit occurrences must be distinct");
    }
    if (operation.kind == Kind::Retarget) {
        require(operation.edges.size() == 1 && operation.new_target < graph.size(), "invalid retarget");
        const auto& edge = operation.edges[0]; require(edge.target != operation.new_target, "retarget must change a target");
        table[edge.source][edge.port] = operation.new_target;
    } else if (operation.kind == Kind::InsertLoop || operation.kind == Kind::InsertTwoEdges) {
        require(graph.size() < 20 && operation.vertex == graph.size(), "invalid routing insertion vertex");
        const auto count = operation.kind == Kind::InsertLoop ? 1U : 2U;
        require(operation.edges.size() == count, "invalid insertion occurrence count");
        const LargeGraph::Row expected = count == 1 ? LargeGraph::Row{operation.edges[0].target,graph.size()}
            : LargeGraph::Row{operation.edges[0].target,operation.edges[1].target};
        require(operation.outgoing == expected, "invalid inserted outgoing occurrences");
        for (const auto& edge : operation.edges) table[edge.source][edge.port] = graph.size();
        table.push_back(operation.outgoing);
    } else {
        require(operation.kind == Kind::SmoothLoop || operation.kind == Kind::SmoothTwoEdges, "unknown edit kind");
        const auto vertex = operation.vertex;
        require(vertex > 0 && vertex < graph.size(), "smoothing cannot delete root");
        require(operation.outgoing == graph.ports[vertex], "deleted row mismatch");
        const auto actual_incoming = incoming(graph, vertex);
        const auto count = operation.kind == Kind::SmoothLoop ? 1U : 2U;
        require(operation.edges.size() == count && actual_incoming.size() == count
            && operation.outgoing_ports.size() == count, "invalid smoothing degree");
        std::set<std::pair<unsigned int,unsigned int>> actual;
        for (const auto& edge : actual_incoming) actual.emplace(edge.source,edge.port);
        require(selected == actual, "smoothing must reconnect every external incoming occurrence");
        std::set<unsigned int> outgoing;
        for (auto port : operation.outgoing_ports) {
            require(port < 2 && graph.ports[vertex][port] != vertex, "invalid smoothing outgoing occurrence");
            require(outgoing.insert(port).second, "outgoing occurrences must be matched bijectively");
        }
        unsigned int nonloops = 0;
        for (auto target : graph.ports[vertex]) nonloops += target != vertex;
        require(nonloops == count, "smoothing loop count mismatch");
        for (std::size_t i = 0; i < operation.edges.size(); ++i) {
            const auto& edge = operation.edges[i]; table[edge.source][edge.port] = graph.ports[vertex][operation.outgoing_ports[i]];
        }
        table.erase(table.begin() + vertex);
        for (auto& row : table) for (auto& target : row) {
            require(target != vertex, "unreconnected incoming occurrence"); if (target > vertex) --target;
        }
    }
    return LargeGraph(std::move(table));
}

std::vector<Step> unit_edits(const LargeGraph& input, Kind kind) {
    const auto graph = input.canonical(); ProposalCursor cursor(graph,kind,0,false);
    std::map<std::string,Step> neighbors;
    while (auto operation = cursor.next(graph)) {
        auto raw = apply_operation(graph,*operation); if (!raw.accessible()) continue;
        auto after = raw.canonical(); if (after == graph) continue;
        const auto key = after.key();
        neighbors.try_emplace(key,Step{graph,std::move(raw),std::move(after),std::move(*operation)});
    }
    std::vector<Step> result; for (auto& [key,step] : neighbors) result.push_back(std::move(step)); return result;
}

Result search(const std::vector<LargeGraph>& inputs, const Options& options) {
    require(options.target_m >= 1 && options.target_m <= 20 && options.radius >= 1 && options.radius <= 3,
        "require target_m1..20 and radius1..3");
    require(options.max_paths && options.max_candidates && !inputs.empty(), "require positive budgets and at least one parent");
    const auto started = std::chrono::steady_clock::now(); Result result;
    std::map<std::string,LargeGraph> canonical_parents;
    for (const auto& graph : inputs) { auto parent = graph.canonical(); canonical_parents.try_emplace(parent.key(),std::move(parent)); }
    std::map<std::string,std::size_t> candidate_index;
    std::set<std::string> direct_candidates;
    std::map<std::string,RootFamily> root_cache;
    auto record_candidate = [&](const Path& path) {
        const auto& endpoint = path.steps.empty() ? canonical_parents.at(path.parent_key) : path.steps.back().after;
        if (endpoint.size() != options.target_m) return false;
        const bool fresh = direct_candidates.insert(endpoint.key()).second;
        if (!root_cache.contains(endpoint.key())) root_cache.emplace(endpoint.key(),root_family(endpoint));
        const auto& family = root_cache.at(endpoint.key());
        for (const auto& [root,graph] : family.roots) {
            if (!options.root_closure && root != 0) continue;
            const auto key = graph.key();
            auto [entry,created] = candidate_index.try_emplace(key,result.candidates.size());
            if (created) result.candidates.push_back({graph,family.shape_key,static_cast<std::uint64_t>(result.candidates.size()),
                static_cast<unsigned int>(path.steps.size()),{}, {}});
            auto& candidate = result.candidates[entry->second];
            candidate.generation_depth = std::min(candidate.generation_depth,static_cast<unsigned int>(path.steps.size()));
            const bool fixed = key == endpoint.key();
            if (fixed && (candidate.path_ids.empty() || candidate.path_ids.back() != path.id)) candidate.path_ids.push_back(path.id);
            candidate.root_metadata.push_back({path.id,endpoint.key(),root,fixed});
        }
        result.root_fixed_candidate_count = direct_candidates.size(); return fresh;
    };
    struct Node { std::size_t parent; LargeGraph graph; std::uint64_t path_id; };
    std::vector<Node> frontier;
    std::vector<std::set<std::string>> visited;
    for (const auto& [key,graph] : canonical_parents) {
        const auto parent = result.parents.size(); result.parents.push_back({key}); visited.push_back({key});
        result.paths.push_back({static_cast<std::uint64_t>(result.paths.size()),key,key,{}});
        record_candidate(result.paths.back());
        if (std::abs(static_cast<int>(graph.size()) - static_cast<int>(options.target_m)) <= static_cast<int>(options.radius))
            frontier.push_back({parent,graph,result.paths.back().id});
    }
    std::vector<std::size_t> parent_order(result.parents.size()); std::iota(parent_order.begin(),parent_order.end(),0);
    std::sort(parent_order.begin(),parent_order.end(),[&](auto a, auto b) {
        return std::pair{mix(options.seed ^ text_hash(result.parents[a].key)),a} < std::pair{mix(options.seed ^ text_hash(result.parents[b].key)),b};
    });
    const auto canceled = [&]() { return options.interrupted && *options.interrupted; };
    for (unsigned int depth = 1; depth <= options.radius; ++depth) {
        DepthCoverage coverage; coverage.depth = depth; coverage.frontier_nodes = frontier.size();
        if (canceled()) { result.interrupted = true; result.depths.push_back(coverage); break; }
        if (result.accepted_paths >= options.max_paths || result.root_fixed_candidate_count >= options.max_candidates) {
            coverage.path_capped = result.path_capped = result.accepted_paths >= options.max_paths;
            coverage.candidate_capped = result.candidate_capped = result.root_fixed_candidate_count >= options.max_candidates;
            result.depths.push_back(coverage); break;
        }
        const auto levels = options.radius - depth + 1;
        const auto path_budget = std::max<std::uint64_t>(1,(options.max_paths - result.accepted_paths) / levels);
        const auto candidate_budget = std::max<std::uint64_t>(1,(options.max_candidates - result.root_fixed_candidate_count) / levels);
        struct Work {
            std::size_t node; ProposalCursor cursor; std::set<std::string> neighbors;
            Work(std::size_t index, const Node& item, Kind kind, std::uint64_t seed) : node(index),
                cursor(item.graph,kind,seed,true) {}
        };
        struct Queue { std::vector<Work> work; std::size_t next = 0; bool exhausted = false; };
        std::vector<std::array<Queue,5>> queues(result.parents.size());
        for (std::size_t index = 0; index < frontier.size(); ++index) for (unsigned int k = 0; k < 5; ++k) {
            const auto& node = frontier[index];
            const auto next_size = static_cast<int>(node.graph.size()) + size_change(static_cast<Kind>(k));
            if (next_size > 20 && std::abs(next_size - static_cast<int>(options.target_m)) <= static_cast<int>(options.radius - depth))
                result.unsupported_size_paths_possible = true;
            queues[node.parent][k].work.emplace_back(index,node,static_cast<Kind>(k),
                mix(options.seed ^ text_hash(node.graph.key()) ^ (std::uint64_t{k} << 32) ^ depth));
        }
        std::vector<Node> next_frontier;
        bool exhausted = false, stop_depth = false;
        while (!stop_depth) {
            bool progress = false;
            for (auto parent : parent_order) {
                std::array<unsigned int,5> kinds{0,1,2,3,4};
                std::sort(kinds.begin(),kinds.end(),[&](auto a,auto b) {
                    return std::pair{mix(options.seed ^ text_hash(result.parents[parent].key) ^ depth ^ (a + 17)),a}
                        < std::pair{mix(options.seed ^ text_hash(result.parents[parent].key) ^ depth ^ (b + 17)),b};
                });
                for (auto k : kinds) {
                    auto& queue = queues[parent][k]; if (queue.exhausted) continue;
                    std::optional<Operation> operation; Work* chosen = nullptr;
                    for (std::size_t tried = 0; tried < queue.work.size(); ++tried) {
                        auto& work = queue.work[queue.next++ % queue.work.size()];
                        operation = work.cursor.next(frontier[work.node].graph);
                        if (operation) { chosen = &work; break; }
                    }
                    if (!operation) { queue.exhausted = true; continue; }
                    progress = true; ++coverage.raw_proposals; ++result.raw_proposals;
                    auto& parent_stats = result.parents[parent]; ++parent_stats.raw_proposals; ++parent_stats.pattern_proposals[k];
                    const auto& node = frontier[chosen->node];
                    const auto next_size = static_cast<int>(node.graph.size()) + size_change(operation->kind);
                    if (std::abs(next_size - static_cast<int>(options.target_m)) > static_cast<int>(options.radius - depth)) { ++result.size_bound_pruned; continue; }
                    auto raw = apply_operation(node.graph,*operation);
                    if (!raw.accessible()) { ++result.inaccessible_rejected; continue; }
                    auto after = raw.canonical(); const auto key = after.key();
                    if (after == node.graph) { ++result.same_class_rejected; continue; }
                    if (!chosen->neighbors.insert(key).second) { ++result.duplicate_neighbors_rejected; continue; }
                    auto path = result.paths[node.path_id]; path.id = result.paths.size(); path.endpoint_key = key;
                    path.steps.push_back({node.graph,std::move(raw),after,std::move(*operation)});
                    result.paths.push_back(std::move(path)); ++coverage.accepted_paths; ++result.accepted_paths;
                    ++parent_stats.accepted_paths; ++parent_stats.pattern_paths[k];
                    if (record_candidate(result.paths.back())) ++coverage.new_rooted_candidates;
                    if (depth < options.radius && visited[parent].insert(key).second)
                        next_frontier.push_back({parent,std::move(after),result.paths.back().id});
                    if (coverage.accepted_paths >= path_budget || coverage.new_rooted_candidates >= candidate_budget || canceled()) {
                        coverage.path_capped = coverage.accepted_paths >= path_budget;
                        coverage.candidate_capped = coverage.new_rooted_candidates >= candidate_budget;
                        result.path_capped |= coverage.path_capped; result.candidate_capped |= coverage.candidate_capped;
                        result.interrupted |= canceled(); stop_depth = true; break;
                    }
                }
                if (stop_depth) break;
            }
            if (!progress) { exhausted = true; break; }
            if (canceled()) { result.interrupted = true; break; }
        }
        coverage.complete = exhausted && !result.interrupted; result.depths.push_back(coverage);
        frontier = std::move(next_frontier); if (result.interrupted) break;
    }
    result.supported_universe_complete = !result.interrupted && result.depths.size() == options.radius
        && std::all_of(result.depths.begin(),result.depths.end(),[](const auto& depth) { return depth.complete; });
    result.enumeration_complete = result.supported_universe_complete && !result.unsupported_size_paths_possible;
    result.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count(); return result;
}
}

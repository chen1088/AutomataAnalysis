#include "Family1CliArtifacts.h"
#include "Family1EditSearch.h"
#include "Family1ExactPacked.h"
#include "Family1LargeEnumerator.h"
#include "Family1OfflineSeeds.h"
#include "Family1OfflineViability.h"
#include "Family1PairAgreement.h"
#include "HardPairFinder.h"
#include "HardPairPrefixSeeds.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace fs = std::filesystem;
namespace cli = family1_cli;
using Graph = family1::LargeGraph;
using Clock = std::chrono::steady_clock;
namespace {
volatile std::sig_atomic_t interrupted = 0;
void stop(int) { interrupted = 1; }
const char* boolean(bool value) { return value ? "true" : "false"; }
struct Deadline {};
struct Options {
    unsigned int m = 0, depth = 24, exact_depth = 8, memory_mib = 512;
    unsigned int radius = 1, window = 8, max_window = 12, beam = 8;
    unsigned int prefix_depth = 16, common_prefix_depth = 8, tail_depth = 64, max_length = 128;
    unsigned int target_upper = 0;
    unsigned int crowding = 3, band_width = 2, window_reports = 16;
    unsigned int viability_coordinates = 256, distance_coordinates = 256;
    std::uint64_t max_layer_states = 1ULL << 20, per_graph_ms = 2000, wall_seconds = 0;
    std::uint64_t max_graphs = 0, seed = 1088, max_paths = 10000, max_candidates = 128;
    std::uint64_t prefix_words = 65536, prefix_pairs = 128, prefix_samples = 16384;
    std::uint64_t tail_threshold = 8, tail_states = 50000, expansions = 1000000;
    bool heuristics = false, mode_set = false, resume = false, dot = false;
    bool deterministic = true;
    fs::path out;
    std::vector<std::string> graphs, parents;
};
std::uint64_t number(const std::string& text) {
    if (text.empty() || text.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("expected a nonnegative integer: " + text);
    return std::stoull(text);
}
unsigned int unsigned_number(const std::string& text) {
    const auto value = number(text);
    if (value > std::numeric_limits<unsigned int>::max()) throw std::invalid_argument("integer is too large");
    return static_cast<unsigned int>(value);
}
void help() {
    std::cout <<
        "Family1Offline --m M --heuristics on|off --out DIR [options]\n"
        "A self-contained, offline Family 1 graph search. No Python, GPU, DLL\n"
        "package, saved word witnesses, or network connection is needed.\n\n"
        "Modes: off enumerates all rooted accessible classes with exact fresh-\n"
        "layer scoring. on explores bounded edited graph neighborhoods and uses\n"
        "full-static-mask k-window/beam word search plus an exact conditional tail.\n"
        "A found pair is an upper bound. Sampling misses never prove hardness.\n\n"
        "Common: --m 1..20 --graph KEY (repeatable supplied subset) --out DIR\n"
        " --depth 24 (exact mode,0..31) --max-layer-states 1048576\n"
        " --memory-mib 512 --per-graph-ms 2000 (0 unlimited)\n"
        " --deterministic (always enabled: canonical candidates, exhaustive\n"
        " prefix layers, lexical beam ties; no random sampling or shuffles)\n"
        " --max-graphs N (NEW evaluations per invocation; off default0/unlimited,\n"
        "               on default1000) --wall-seconds 0\n"
        " --seed and --prefix-samples are accepted for old command compatibility\n"
        " but have no effect in this deterministic runner.\n"
        " --resume (same configuration/executable; skip finished journal rows)\n"
        " --dot (export unlabelled edges for every current best tie)\n\n"
        "Heuristic graph controls: --parent KEY (repeatable; overrides parents)\n"
        " --radius 1 (1..3) --max-paths 10000 --max-candidates 128\n"
        " All accessible roots of generated shapes are retained. Root closure\n"
        " may exceed max-candidates, which counts endpoints before closure.\n"
        " Built-in graph-only seeds include all known small winners; at larger\n"
        " sizes root-stem extensions and a circulant baseline bootstrap the run.\n\n"
        "Heuristic word controls: --exact-depth 8 (0 disables exact prescoring)\n"
        " --window 8 --max-window 12 (1..16, >=window) --beam 8 (1..64)\n"
        " --prefix-depth 16 (1..63) --prefix-words 65536 --prefix-pairs 128\n"
        " --prefix-samples 16384 --common-prefix-depth 8 (0..8)\n"
        " --tail-threshold 8 --tail-states 50000 --tail-depth 64\n"
        " --viability-coordinates 256 --distance-coordinates 256 (0..1024)\n"
        " Proved unmergeable individual coordinates prune only a fixed prefix\n"
        " pair; individual shortest distances lower-bound its remaining suffix.\n"
        " --expansions 1000000 (per prefix, automatically raised to cover\n"
        " complete beam windows at the chosen k) --max-length 128 (1..4096)\n"
        " --target-upper 0 (0 disabled,1..4096: stop a graph after a verified\n"
        " pair at or below this length; no shortest-length claim or adaptive\n"
        " refinement for a graph that has reached this upper-bound target)\n"
        " --crowding 3 --band-width 2 (crowded leaders trigger larger k)\n\n"
        " --window-reports 16 (retain latest compact distributions per graph;\n"
        " 0 disables; histograms use at most64 bins, never all ranked leaves)\n\n"
        "Output: records.jsonl, best.jsonl, summary.json, run.json, checked\n"
        "checkpoint.journal, and optional dot/. No tie collection is truncated.\n"
        "Depth/memory/work/time caps remain explicit; only exhaustive enumeration\n"
        "and exact scoring can certify a global maximum. Time limits are soft\n"
        "around canonicalization, graph generation, initialization and replay.\n"
        "Memory controls cover planned search payload, not process-wide memory.\n";
}
Options parse(int argc, char** argv) {
    Options o;
    bool max_graphs_set = false;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--help" || a == "-h") { help(); std::exit(0); }
        if (a == "--resume") { o.resume = true; continue; }
        if (a == "--dot") { o.dot = true; continue; }
        if (a == "--deterministic") { o.deterministic = true; continue; }
        if (++i == argc) throw std::invalid_argument("missing value: " + a);
        const std::string v = argv[i];
        if (a == "--m") o.m = unsigned_number(v);
        else if (a == "--heuristics") { if (v != "on" && v != "off") throw std::invalid_argument("heuristics must be on or off"); o.heuristics = v == "on"; o.mode_set = true; }
        else if (a == "--out") o.out = v;
        else if (a == "--graph") o.graphs.push_back(v);
        else if (a == "--parent") o.parents.push_back(v);
        else if (a == "--depth") o.depth = unsigned_number(v);
        else if (a == "--exact-depth") o.exact_depth = unsigned_number(v);
        else if (a == "--memory-mib") o.memory_mib = unsigned_number(v);
        else if (a == "--max-layer-states") o.max_layer_states = number(v);
        else if (a == "--per-graph-ms") o.per_graph_ms = number(v);
        else if (a == "--wall-seconds") o.wall_seconds = number(v);
        else if (a == "--max-graphs") { o.max_graphs = number(v); max_graphs_set = true; }
        else if (a == "--seed") o.seed = number(v);
        else if (a == "--radius") o.radius = unsigned_number(v);
        else if (a == "--max-paths") o.max_paths = number(v);
        else if (a == "--max-candidates") o.max_candidates = number(v);
        else if (a == "--window") o.window = unsigned_number(v);
        else if (a == "--max-window") o.max_window = unsigned_number(v);
        else if (a == "--beam") o.beam = unsigned_number(v);
        else if (a == "--prefix-depth") o.prefix_depth = unsigned_number(v);
        else if (a == "--prefix-words") o.prefix_words = number(v);
        else if (a == "--prefix-pairs") o.prefix_pairs = number(v);
        else if (a == "--prefix-samples") o.prefix_samples = number(v);
        else if (a == "--common-prefix-depth") o.common_prefix_depth = unsigned_number(v);
        else if (a == "--tail-threshold") o.tail_threshold = number(v);
        else if (a == "--tail-states") o.tail_states = number(v);
        else if (a == "--tail-depth") o.tail_depth = unsigned_number(v);
        else if (a == "--expansions") o.expansions = number(v);
        else if (a == "--max-length") o.max_length = unsigned_number(v);
        else if (a == "--target-upper") o.target_upper = unsigned_number(v);
        else if (a == "--crowding") o.crowding = unsigned_number(v);
        else if (a == "--band-width") o.band_width = unsigned_number(v);
        else if (a == "--window-reports") o.window_reports = unsigned_number(v);
        else if (a == "--viability-coordinates") o.viability_coordinates = unsigned_number(v);
        else if (a == "--distance-coordinates") o.distance_coordinates = unsigned_number(v);
        else throw std::invalid_argument("unknown option: " + a);
    }
    if (!o.m || o.m > 20 || !o.mode_set || o.out.empty()) throw std::invalid_argument("require --m 1..20, --heuristics on|off and --out DIR");
    if (o.depth > 31 || o.exact_depth > 31 || !o.memory_mib || o.memory_mib > (1U << 20)
        || !o.max_layer_states || o.max_layer_states > (1ULL << 31)) throw std::invalid_argument("invalid exact depth/layer/memory budget");
    if (!o.radius || o.radius > 3 || !o.max_paths || !o.max_candidates || !o.window || o.max_window > 16
        || o.window > o.max_window || !o.beam || o.beam > 64 || !o.prefix_depth || o.prefix_depth > 63
        || !o.prefix_words || o.prefix_words > (1ULL << 24) || !o.prefix_pairs || o.prefix_pairs > 1000000
        || o.common_prefix_depth > 8 || !o.tail_states || o.tail_states > (1ULL << 32) || !o.expansions || !o.max_length || o.max_length > 4096
        || o.target_upper > 4096 || !o.crowding || o.window_reports > 1000 || o.viability_coordinates > 1024 || o.distance_coordinates > 1024
        || o.per_graph_ms > 31536000000ULL || o.wall_seconds > 31536000ULL)
        throw std::invalid_argument("invalid heuristic or time budget");
    if (!o.heuristics && !o.parents.empty()) throw std::invalid_argument("--parent requires heuristics on");
    if (o.heuristics && !max_graphs_set) o.max_graphs = 1000;
    auto canonical_keys = [](std::vector<std::string>& keys, unsigned int required) {
        for (auto& key : keys) { auto g = Graph::from_key(key); if (!g.accessible() || (required && g.size() != required)) throw std::invalid_argument("graph must be accessible and have the requested size"); key = g.canonical().key(); }
        std::sort(keys.begin(), keys.end()); keys.erase(std::unique(keys.begin(), keys.end()), keys.end());
    };
    canonical_keys(o.graphs, o.m); canonical_keys(o.parents, 0);
    o.out = fs::absolute(o.out);
    return o;
}
void replace(const fs::path& path, const std::string& text) {
    const fs::path temporary(path.string() + ".tmp");
    cli::write(temporary, text);
#ifdef _WIN32
    if (!MoveFileExW(temporary.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        throw std::runtime_error("cannot atomically publish " + path.string());
#else
    fs::rename(temporary, path);
#endif
}
std::string executable_sha(const char* argument) {
    fs::path path(argument);
#ifdef _WIN32
    std::vector<wchar_t> name(32768);
    const auto count = GetModuleFileNameW(nullptr, name.data(), static_cast<DWORD>(name.size()));
    if (!count || count == name.size()) throw std::runtime_error("cannot locate this executable");
    path = std::wstring(name.data(), count);
#else
    std::error_code ec;
    auto resolved = fs::read_symlink("/proc/self/exe", ec);
    if (!ec) path = resolved;
#endif
    return cli::sha256(cli::read(path));
}
std::string configuration(const Options& o, const std::string& exe) {
    std::ostringstream s;
    s << "{\"schema\":1,\"program\":\"Family1Offline/1\",\"executable_sha256\":" << cli::quote(exe)
      << ",\"m\":" << o.m << ",\"heuristics\":" << boolean(o.heuristics)
      << ",\"deterministic\":" << boolean(o.deterministic)
      << ",\"candidate_order\":\"canonical parents and neighbors; fixed edit-kind round robin\""
      << ",\"prefix_selection\":\"complete binary layers within word budget; no sampling\""
      << ",\"finder_ties\":\"lexicographic suffix\"";
#define CONFIG(field) s << ",\"" #field "\":" << o.field
    CONFIG(depth); CONFIG(exact_depth); CONFIG(memory_mib); CONFIG(max_layer_states); CONFIG(per_graph_ms);
    CONFIG(wall_seconds); CONFIG(max_graphs); CONFIG(seed); CONFIG(radius); CONFIG(max_paths); CONFIG(max_candidates);
    CONFIG(window); CONFIG(max_window); CONFIG(beam); CONFIG(prefix_depth); CONFIG(prefix_words); CONFIG(prefix_pairs);
    CONFIG(prefix_samples); CONFIG(common_prefix_depth); CONFIG(tail_threshold); CONFIG(tail_states); CONFIG(tail_depth);
    CONFIG(expansions); CONFIG(max_length); CONFIG(target_upper); CONFIG(crowding); CONFIG(band_width); CONFIG(window_reports);
    CONFIG(viability_coordinates); CONFIG(distance_coordinates);
#undef CONFIG
    s << ",\"dot\":" << boolean(o.dot) << ",\"max_graphs_scope\":\"new evaluations per invocation\",\"graphs\":[";
    for (std::size_t i = 0; i < o.graphs.size(); ++i) { if (i) s << ','; s << cli::quote(o.graphs[i]); }
    s << "],\"parents\":[";
    for (std::size_t i = 0; i < o.parents.size(); ++i) { if (i) s << ','; s << cli::quote(o.parents[i]); }
    s << "],\"time_budget_hard\":false,\"memory_budget_process_wide\":false}";
    return s.str();
}
struct Record {
    std::string key, status = "not-evaluated", first, second, reason;
    unsigned int lower = 1, upper = 0, merge = 0, window = 0, depth = 0;
    bool evaluated = false, finished = false;
    std::uint64_t attempts = 0, expansions = 0, prefix_words = 0, prefix_coordinates = 0;
    std::uint64_t effective_expansions = 0, estimated_working_bytes = 0, tail_calls = 0;
    std::uint64_t dropped_reports = 0;
    std::vector<std::string> reports;
    std::string viability = "null";
};
using Records = std::map<std::string, Record>;
bool target_reached(const Options& o, const Record& r) {
    return o.heuristics && o.target_upper && r.upper && r.upper <= o.target_upper;
}
void describe_target_reached(const Options& o, Record& r) {
    if (target_reached(o, r) && !r.merge)
        r.reason = "target upper reached: verified pair length " + std::to_string(r.upper)
            + " <= " + std::to_string(o.target_upper)
            + "; stopped at threshold witness, shortest merge length not certified";
}
unsigned int estimate(const Record& r) { return r.merge ? r.merge : r.upper ? std::max(r.lower, r.upper - 1) : 0; }
std::string record_json(const Record& r, bool heuristic) {
    auto g = Graph::from_key(r.key);
    std::ostringstream s;
    s << "{\"m\":" << g.size() << ",\"key\":" << cli::quote(r.key) << ",\"canonical_table\":[";
    for (unsigned int i = 0; i < g.size(); ++i) { if (i) s << ','; s << '[' << g.ports[i][0] << ',' << g.ports[i][1] << ']'; }
    s << "],\"status\":" << cli::quote(r.status) << ",\"merge_length\":" << (r.merge ? std::to_string(r.merge) : "null")
      << ",\"lower_bound\":" << r.lower << ",\"upper_bound\":" << (r.upper ? std::to_string(r.upper) : "null")
      << ",\"witness\":";
    if (r.upper) s << '[' << cli::quote(r.first) << ',' << cli::quote(r.second) << ']'; else s << "null";
    s << ",\"estimated_merge_length\":" << (estimate(r) ? std::to_string(estimate(r)) : "null")
      << ",\"estimate_certified\":" << boolean(r.merge != 0) << ",\"estimated_band\":";
    if (r.upper) s << '[' << (r.merge ? r.merge : std::max(r.lower, r.upper > 2 ? r.upper - 2 : 1)) << ',' << r.upper << ']'; else s << "null";
    s << ",\"heuristics\":" << boolean(heuristic) << ",\"evaluated\":" << boolean(r.evaluated)
      << ",\"finished\":" << boolean(r.finished) << ",\"window_k\":" << r.window << ",\"exact_depth\":" << r.depth
      << ",\"prefix_attempts\":" << r.attempts << ",\"expanded_nodes\":" << r.expansions << ",\"tail_calls\":" << r.tail_calls
      << ",\"effective_prefix_words\":" << r.prefix_words << ",\"prefix_constraint_coordinates\":" << r.prefix_coordinates
      << ",\"prefix_generation_trivial_coordinate\":" << boolean(r.prefix_words && r.prefix_coordinates == 0)
      << ",\"effective_expansions_per_prefix\":" << r.effective_expansions << ",\"estimated_working_bytes\":" << r.estimated_working_bytes
      << ",\"static_masks_verified\":" << (r.upper ? (1ULL << g.size()) : 0) << ",\"window_reports_truncated\":" << r.dropped_reports
      << ",\"window_distributions\":[";
    for (std::size_t i = 0; i < r.reports.size(); ++i) { if (i) s << ','; s << r.reports[i]; }
    s << "],\"viability\":" << r.viability
      << ",\"finder_counter_scope\":\"returned finder calls; deadline-aborted call counters can be partial\",\"reason\":" << cli::quote(r.reason) << '}';
    return s.str();
}
std::string serialized(const Record& r) {
    std::string reason = r.reason;
    for (char& c : reason) if (c == '\n' || c == '\r' || c == '\t') c = ' ';
    std::ostringstream s;
    s << r.key << ' ' << r.status << ' ' << r.lower << ' ' << r.upper << ' ' << r.merge << ' ' << r.window << ' ' << r.depth
      << ' ' << r.evaluated << ' ' << r.finished << ' ' << r.attempts << ' ' << r.expansions << ' ' << r.prefix_words
      << ' ' << r.prefix_coordinates << ' ' << r.effective_expansions << ' ' << r.estimated_working_bytes << ' ' << r.tail_calls
      << ' ' << std::quoted(r.first) << ' ' << std::quoted(r.second) << ' ' << std::quoted(reason)
      << ' ' << std::quoted(r.viability) << ' ' << r.dropped_reports << ' ' << r.reports.size();
    for (const auto& report : r.reports) s << ' ' << std::quoted(report);
    return s.str();
}
Record deserialize(const std::string& payload) {
    Record r;
    std::istringstream s(payload);
    s >> r.key >> r.status >> r.lower >> r.upper >> r.merge >> r.window >> r.depth >> r.evaluated >> r.finished
      >> r.attempts >> r.expansions >> r.prefix_words >> r.prefix_coordinates >> r.effective_expansions
      >> r.estimated_working_bytes >> r.tail_calls >> std::quoted(r.first) >> std::quoted(r.second) >> std::quoted(r.reason);
    std::size_t report_count = 0;
    s >> std::quoted(r.viability) >> r.dropped_reports >> report_count;
    if (report_count > 1000) throw std::runtime_error("invalid checkpoint report count");
    for (std::size_t i = 0; i < report_count; ++i) { std::string report; s >> std::quoted(report); r.reports.push_back(std::move(report)); }
    if (!s || (s >> std::ws, !s.eof())) throw std::runtime_error("invalid checkpoint payload");
    return r;
}
void verify(const Graph& graph, const std::string& first, const std::string& second) {
    if (first.empty() || first == second || first.size() != second.size() || first.find_first_not_of("01") != std::string::npos
        || second.find_first_not_of("01") != std::string::npos) throw std::runtime_error("invalid positive witness words");
    for (std::uint32_t mask = 0; mask < (1U << graph.size()); ++mask) {
        unsigned int a = 0, b = 0;
        for (std::size_t i = 0; i < first.size(); ++i) {
            a = graph.ports[a][static_cast<unsigned int>(first[i] - '0') ^ ((mask >> a) & 1U)];
            b = graph.ports[b][static_cast<unsigned int>(second[i] - '0') ^ ((mask >> b) & 1U)];
        }
        if (a != b) throw std::runtime_error("full scalar static-mask replay rejected a positive witness");
    }
}
struct Journal {
    fs::path path;
    std::string chain;
    Records records;
    Journal(const Options& o, const std::string& config) : path(o.out / "checkpoint.journal"), chain(cli::sha256(config)) {
        if (o.resume) {
            if (cli::read(o.out / "run.json") != config) throw std::runtime_error("resume configuration/executable differs");
            if (!fs::exists(path)) throw std::runtime_error("resume journal is missing");
            const auto data = cli::read(path);
            if (!data.empty() && data.back() != '\n') throw std::runtime_error("incomplete checkpoint journal tail; preserve and repair before resuming");
            std::istringstream input(data);
            std::string line;
            while (std::getline(input, line)) {
                if (line.size() < 66 || line[64] != '\t') throw std::runtime_error("invalid checkpoint journal line");
                const auto payload = line.substr(65);
                const auto next = cli::sha256(chain + "\n" + payload);
                if (line.substr(0, 64) != next) throw std::runtime_error("checkpoint journal checksum mismatch");
                auto r = deserialize(payload);
                auto g = Graph::from_key(r.key);
                if (g.size() != o.m || !g.accessible() || g.canonical().key() != r.key || !r.lower
                    || (r.upper && r.lower > r.upper) || (r.merge && (r.merge != r.lower || r.merge != r.upper)))
                    throw std::runtime_error("invalid checkpoint graph/interval");
                if (r.upper) verify(g, r.first, r.second);
                records[r.key] = std::move(r); chain = next;
            }
        } else {
            if (fs::exists(o.out) && !fs::is_empty(o.out)) throw std::runtime_error("fresh output directory required; use identical --resume");
            fs::create_directories(o.out);
            cli::publish(o.out / "run.json", config);
            cli::publish(path, "");
        }
    }
    void save(const Record& r) {
        const auto payload = serialized(r), next = cli::sha256(chain + "\n" + payload);
        std::ofstream out(path, std::ios::binary | std::ios::app);
        out << next << '\t' << payload << '\n'; out.close();
        if (!out) throw std::runtime_error("failed writing checked checkpoint journal");
        chain = next; records[r.key] = r;
    }
};
Graph stem(Graph graph, unsigned int target) {
    while (graph.size() < target) {
        std::vector<Graph::Row> table{{1, 1}};
        for (const auto& row : graph.ports) table.push_back({row[0] + 1, row[1] + 1});
        graph = Graph(std::move(table)).canonical();
    }
    return graph;
}
std::vector<Graph> bootstrap(unsigned int m) {
    auto keys = family1::offline_seeds::keys_by_size(m);
    unsigned int smaller = m;
    while (keys.empty() && smaller > 1) keys = family1::offline_seeds::keys_by_size(--smaller);
    std::vector<Graph> out;
    for (const auto& key : keys) out.push_back(stem(Graph::from_key(key), m));
    return out;
}
struct Pool {
    std::vector<Graph> graphs;
    bool generation_complete = false, path_capped = false, candidate_capped = false;
    std::uint64_t accepted_paths = 0;
    std::string scope;
};
Pool generate(const Options& o) {
    Pool pool;
    std::map<std::string, Graph> all;
    std::vector<std::string> order;
    auto add = [&](const Graph& graph) { auto c = graph.canonical(); auto key = c.key(); if (all.emplace(key, std::move(c)).second) order.push_back(key); };
    auto add_shape = [&](const Graph& graph) {
        for (unsigned int root = 0; root < graph.size(); ++root) {
            std::vector<unsigned int> map(graph.size());
            unsigned int next = 1; map[root] = 0;
            for (unsigned int v = 0; v < graph.size(); ++v) if (v != root) map[v] = next++;
            std::vector<Graph::Row> table(graph.size());
            for (unsigned int v = 0; v < graph.size(); ++v) table[map[v]] = {map[graph.ports[v][0]], map[graph.ports[v][1]]};
            Graph rerooted(std::move(table));
            if (rerooted.accessible()) add(rerooted);
        }
    };
    for (const auto& key : o.graphs) add(Graph::from_key(key));
    if (!o.graphs.empty() && o.parents.empty()) { pool.generation_complete = true; pool.scope = "supplied graph subset"; }
    else {
        pool.scope = "bounded edit neighborhoods with every accessible root, graph-only bootstrap and circulant baseline";
        std::vector<Graph> parents;
        if (o.parents.empty()) {
            for (const auto& graph : bootstrap(o.m)) add_shape(graph);
            std::vector<Graph::Row> table(o.m);
            for (unsigned int s = 0; s < o.m; ++s) table[s] = {(s + 1) % o.m, (s + o.m / 3) % o.m};
            add_shape(Graph(std::move(table)));
            if (o.m > 1) parents = bootstrap(o.m - 1);
        } else for (const auto& key : o.parents) parents.push_back(Graph::from_key(key));
        if (!parents.empty()) {
            family1::edit::Options edit;
            edit.target_m = o.m; edit.radius = o.radius; edit.max_paths = o.max_paths;
            edit.max_candidates = o.max_candidates; edit.seed = o.seed; edit.root_closure = true; edit.interrupted = &interrupted;
            edit.deterministic = o.deterministic;
            auto result = family1::edit::search(parents, edit);
            pool.generation_complete = result.enumeration_complete;
            pool.path_capped = result.path_capped; pool.candidate_capped = result.candidate_capped; pool.accepted_paths = result.accepted_paths;
            for (const auto& c : result.candidates) add(c.graph);
        } else pool.generation_complete = true;
    }
    // Bootstrap shapes run first; edit discovery order remains deterministic.
    // Public archives and every tie collection are still sorted by canonical key.
    for (const auto& key : order) pool.graphs.push_back(std::move(all.at(key)));
    return pool;
}
struct TimedPair {
    family1::ExactPairAgreement pair;
    Clock::time_point deadline;
    std::shared_ptr<family1::offline::ViabilityCache> viability;
    void check() const { if (interrupted || Clock::now() >= deadline) throw Deadline{}; }
    std::uint64_t remaining_count() const { return pair.remaining_count(); }
    std::uint64_t mask_count() const { return pair.mask_count(); }
    std::uint64_t permutation_mismatch_count() const { return pair.permutation_mismatch_count(); }
    TimedPair append_common(bool input) const { check(); return {pair.append_common(input), deadline, viability}; }
    bool has_proven_obstruction() const { check(); return viability && viability->has_obstruction(pair); }
    std::uint64_t minimum_completion_length() const { check(); return viability ? viability->minimum_distance(pair) : 0; }
};
std::uint64_t expansion_quota(const Options& o, unsigned int k) {
    // Cover every retained beam parent and multiple windows; quota is per seed.
    std::uint64_t rounds = 0, width = 1;
    unsigned int left = o.max_length;
    while (left) { auto span = std::min(left, k); rounds += width * ((1ULL << (span + 1)) - 2); width = o.beam; left -= span; }
    return std::max<std::uint64_t>({o.expansions, 4ULL * ((1ULL << (k + 1)) - 2) * o.beam, rounds});
}
Clock::time_point deadline(Clock::time_point started, std::uint64_t milliseconds) {
    return milliseconds ? started + std::chrono::milliseconds(milliseconds) : Clock::time_point::max();
}
void accept(const Graph& g, Record& r, const std::string& first, const std::string& second, Journal& journal) {
    if (r.upper && first.size() >= r.upper) return;
    verify(g, first, second);
    if (first.size() < r.lower) throw std::runtime_error("positive witness contradicts a certified lower bound");
    r.upper = static_cast<unsigned int>(first.size()); r.first = first; r.second = second;
    r.merge = r.lower == r.upper ? r.upper : 0;
    r.status = r.merge ? "exact" : "heuristic";
    // Save every shorter verified pair before any next expensive seed/window.
    journal.save(r);
}
void exact(const Graph& g, const Options& o, Record& r, unsigned int depth, Clock::time_point end) {
    family1::PackedLimits limits;
    limits.depth = depth; limits.max_layer_states = o.max_layer_states;
    limits.max_working_bytes = static_cast<std::uint64_t>(o.memory_mib) << 20; limits.interrupted = &interrupted;
    if (end != Clock::time_point::max()) {
        if (Clock::now() >= end) { r.status = "incomplete"; r.reason = "time budget before exact scoring"; return; }
        limits.timeout_ms = std::max<std::int64_t>(1, std::chrono::duration_cast<std::chrono::milliseconds>(end - Clock::now()).count());
    }
    const auto score = family1::score_packed(g, limits);
    r.evaluated = true; r.depth = depth; r.lower = std::max(r.lower, score.lower_bound); r.status = score.status; r.reason = score.reason;
    if (score.merge_length) {
        verify(g, score.witness[0], score.witness[1]);
        r.merge = r.lower = r.upper = score.merge_length; r.first = score.witness[0]; r.second = score.witness[1];
    }
    if (r.upper && r.upper == r.lower) { r.merge = r.upper; r.status = "exact"; }
}
void retain_reports(const hardpair::FinderResult& result, Record& record, unsigned int limit) {
    record.dropped_reports += result.window_reports_truncated;
    for (const auto& report : result.window_distributions) {
        if (!limit) { ++record.dropped_reports; continue; }
        std::uint64_t width = 1;
        if (report.histogram.size() > 64) width = (report.max_drop - report.min_drop) / 64 + 1;
        std::map<std::uint64_t, std::uint64_t> bins;
        for (const auto& [drop, count] : report.histogram) bins[report.min_drop + ((drop - report.min_drop) / width) * width] += count;
        std::ostringstream out;
        out << std::setprecision(17) << "{\"prefix_attempt\":" << record.attempts << ",\"window_k\":" << report.window_k
            << ",\"initial_remaining\":" << report.initial_remaining << ",\"mask_count\":" << report.mask_count
            << ",\"complete\":" << boolean(report.complete) << ",\"window_count\":" << report.window_count
            << ",\"expanded_nodes\":" << report.expanded_nodes << ",\"min_drop\":" << report.min_drop
            << ",\"max_drop\":" << report.max_drop << ",\"mean_drop\":" << report.mean_drop
            << ",\"median_drop\":" << report.median_drop << ",\"variance_drop\":" << report.variance_drop
            << ",\"stddev_drop\":" << report.stddev_drop << ",\"zero_drop_count\":" << report.zero_drop_count
            << ",\"full_merge_count\":" << report.full_merge_count << ",\"histogram_exact\":" << boolean(width == 1)
            << ",\"histogram_bin_width\":" << width << ",\"histogram\":[";
        bool comma = false;
        for (const auto& [drop, count] : bins) { if (comma) out << ','; comma = true; out << '[' << drop << ',' << count << ']'; }
        out << "]}";
        if (record.reports.size() == limit) { record.reports.erase(record.reports.begin()); ++record.dropped_reports; }
        record.reports.push_back(out.str());
    }
}
void heuristic(const Graph& g, const Options& o, Record& r, unsigned int k, Clock::time_point end, Journal& journal) {
    if (target_reached(o, r)) { describe_target_reached(o, r); return; }
    r.window = k; r.evaluated = true; r.finished = false;
    r.status = r.upper ? "heuristic" : "incomplete";
    if (Clock::now() >= end || interrupted) { r.reason = "time budget or interrupt"; return; }
    auto context = std::make_shared<family1::PairAgreementContext>(g);
    // Retain a small graph-dependent constraint family to generate prefixes;
    // every candidate then faces the complete permutation gate/full-mask metric.
    std::vector<std::uint32_t> masks;
    for (std::uint32_t mask = 0; mask < (1U << g.size()) && masks.size() < 64; ++mask)
        if (context->is_permutation_mask(mask)) masks.push_back(mask);
    r.prefix_coordinates = masks.size();
    const auto available = static_cast<std::uint64_t>(o.memory_mib) << 20;
    const auto pair_bytes = 16ULL * g.size() * context->block_count() + 16ULL * context->block_count();
    const auto state_plan = (3ULL * o.beam + 2ULL * k + 12) * pair_bytes;
    const auto tail_plan = o.tail_states * (256ULL + 16ULL * std::min<std::uint64_t>(o.tail_threshold, 1ULL << g.size()));
    const auto cache_plan = (o.viability_coordinates || o.distance_coordinates)
        ? 4096ULL * (256ULL + 5ULL * g.size() * g.size()) : 0;
    // One live full window needs leaves, summary scratch and map nodes. Retained
    // reports keep exact histograms but no ranked leaves, capped inside finder.
    const auto report_plan = (1ULL << k) * (256ULL + 16ULL * o.window_reports) + 1024ULL * o.window_reports;
    const auto fixed_plan = state_plan + tail_plan + cache_plan + report_plan;
    if (fixed_plan >= available) { r.reason = "planned finder/tail/cache/diagnostic working payload exceeds memory budget"; r.estimated_working_bytes = fixed_plan; return; }
    const auto per_word = 256ULL + 16ULL * masks.size();
    const auto word_budget = std::max<std::uint64_t>(1, (available - fixed_plan) / per_word);
    hardpair::PrefixSeedOptions prefixes;
    prefixes.max_depth = std::min(o.prefix_depth, o.max_length);
    prefixes.max_words = std::min(o.prefix_words, word_budget);
    prefixes.max_pairs = o.prefix_pairs; prefixes.samples_per_depth = std::min(o.prefix_samples, prefixes.max_words);
    prefixes.common_prefix_depth = o.common_prefix_depth; prefixes.seed = o.seed; prefixes.interrupted = &interrupted;
    prefixes.deterministic = o.deterministic;
    if (!o.deterministic && prefixes.samples_per_depth && prefixes.max_depth > 1) {
        for (unsigned int d = std::max(1U, prefixes.max_depth / 2); d <= prefixes.max_depth; ++d) prefixes.sample_depths.push_back(d);
    }
    r.prefix_words = prefixes.max_words;
    r.estimated_working_bytes = fixed_plan + prefixes.max_words * per_word;
    r.effective_expansions = expansion_quota(o, k);
    auto transition = [&](std::size_t coordinate, std::uint32_t state, bool input) {
        if (Clock::now() >= end || interrupted) throw Deadline{};
        // A dummy absorbing coordinate implements the vacuous constraint family
        // without changing the reusable module's empty-family API convention.
        if (masks.empty()) return 0U;
        return context->transition(masks[coordinate], state, input);
    };
    auto seeds = hardpair::enumerate_prefix_seeds(std::vector<std::uint32_t>(std::max<std::size_t>(1, masks.size()), 0), transition, prefixes);
    if (seeds.pairs.empty()) { r.reason = "no prefix seed pair within the bounded prefix plan"; return; }
    auto viability = std::make_shared<family1::offline::ViabilityCache>(g, o.viability_coordinates, o.distance_coordinates,
        [end]() { if (interrupted || Clock::now() >= end) throw Deadline{}; }, &interrupted);
    struct SaveStatistics {
        Record& record;
        std::shared_ptr<family1::offline::ViabilityCache> cache;
        ~SaveStatistics() noexcept { try { record.viability = cache->json(); } catch (...) {} }
    } save_statistics{r, viability};
    for (const auto& seed : seeds.pairs) {
        if (Clock::now() >= end || interrupted) throw Deadline{};
        const auto cap = std::min(o.max_length, r.upper ? r.upper - 1 : o.max_length);
        if (seed.first.size() > cap) continue;
        TimedPair initial{family1::ExactPairAgreement(context, seed.first, seed.second), end, viability};
        ++r.attempts;
        hardpair::FinderOptions find;
        find.window_k = k; find.beam_width = o.beam; find.max_suffix = cap - static_cast<unsigned int>(seed.first.size());
        find.rank_by_remaining = true; find.tail_threshold = o.tail_threshold; find.max_expansions = r.effective_expansions;
        find.tie_seed = o.seed ^ r.attempts; find.interrupted = &interrupted;
        find.deterministic = o.deterministic;
        find.retain_ranked_windows = false; find.max_window_reports = o.window_reports;
        find.tail_limits.max_states = static_cast<std::size_t>(o.tail_states); find.tail_limits.max_depth = o.tail_depth;
        auto tail = [&](const TimedPair& state, const hardpair::TailLimits& limits) {
            state.check();
            std::vector<hardpair::CoordinatePair> coordinates;
            for (const auto& pair : state.pair.remaining_coordinate_pairs()) coordinates.push_back({pair[0], pair[1], pair[2]});
            return hardpair::exact_suffix_bfs(coordinates, [&](std::size_t mask, std::uint32_t at, bool input) {
                state.check(); return context->transition(static_cast<std::uint32_t>(mask), at, input);
            }, limits);
        };
        auto result = hardpair::find_hard_pair_suffix(std::move(initial), find, tail);
        r.expansions += result.expanded_nodes; r.tail_calls += result.tail_calls;
        r.viability = viability->json();
        retain_reports(result, r, o.window_reports);
        if (result.found) accept(g, r, seed.first + result.suffix, seed.second + result.suffix, journal);
        if (target_reached(o, r)) { describe_target_reached(o, r); return; }
        if (r.merge) break;
    }
    r.reason = r.upper ? "verified upper witness; bounded prefix/window search completed" : "bounded prefix/window search found no universal pair";
}
void write_dot(const fs::path& path, const Record& r) {
    auto graph = Graph::from_key(r.key);
    std::ostringstream s;
    s << "digraph Family1 {\n  rankdir=LR;\n  start [shape=point]; start -> 0;\n";
    for (unsigned int i = 0; i < graph.size(); ++i) {
        s << "  " << i << " [shape=" << (i ? "circle" : "doublecircle") << "];\n";
        for (auto target : graph.ports[i]) s << "  " << i << " -> " << target << ";\n";
    }
    s << "}\n"; replace(path, s.str());
}
std::string publish(const Options& o, const Journal& journal, const Pool& pool, bool enumeration_complete,
                    bool stopped, std::uint64_t new_evaluations) {
    unsigned int best_exact = 0, best_estimate = 0;
    std::uint64_t evaluated = 0, exact_count = 0, unfinished = 0;
    for (const auto& [key, r] : journal.records) {
        evaluated += r.evaluated; exact_count += r.merge != 0; unfinished += r.evaluated && !r.finished;
        best_exact = std::max(best_exact, r.merge); best_estimate = std::max(best_estimate, estimate(r));
    }
    const bool scoring_complete = evaluated == journal.records.size() && exact_count == evaluated && !unfinished;
    const bool global = !o.heuristics && o.graphs.empty() && enumeration_complete && scoring_complete;
    std::ostringstream records, best;
    std::uint64_t ties = 0;
    if (o.dot) fs::create_directories(o.out / "dot");
    std::set<std::string> wanted_dots;
    for (const auto& [key, r] : journal.records) {
        const auto line = record_json(r, o.heuristics);
        records << line << '\n';
        if (o.heuristics ? (best_estimate && estimate(r) == best_estimate) : (best_exact && r.merge == best_exact)) {
            best << line << '\n'; ++ties;
            if (o.dot) { auto name = key + ".dot"; wanted_dots.insert(name); write_dot(o.out / "dot" / name, r); }
        }
    }
    if (o.dot) for (const auto& entry : fs::directory_iterator(o.out / "dot"))
        if (entry.is_regular_file() && entry.path().extension() == ".dot" && !wanted_dots.contains(entry.path().filename().string())) fs::remove(entry.path());
    replace(o.out / "records.jsonl", records.str()); replace(o.out / "best.jsonl", best.str());
    std::ostringstream s;
    s << "{\"schema\":1,\"m\":" << o.m << ",\"heuristics\":" << boolean(o.heuristics)
      << ",\"deterministic\":" << boolean(o.deterministic)
      << ",\"scope\":" << cli::quote(o.heuristics ? pool.scope : o.graphs.empty() ? "all rooted accessible classes of exactly m states" : "supplied graph subset")
      << ",\"enumeration_complete\":" << boolean(enumeration_complete)
      << ",\"neighborhood_generation_complete\":" << boolean(pool.generation_complete)
      << ",\"scoring_complete\":" << boolean(scoring_complete) << ",\"global_maximum_certified\":" << boolean(global)
      << ",\"maximizing_collection_complete\":" << boolean(global) << ",\"maximum_merge_length\":" << (global ? std::to_string(best_exact) : "null")
      << ",\"best_exact_merge_length\":" << (best_exact ? std::to_string(best_exact) : "null")
      << ",\"best_estimated_merge_length\":" << (best_estimate ? std::to_string(best_estimate) : "null")
      << ",\"best_count\":" << ties << ",\"enumerated_graphs\":" << journal.records.size() << ",\"evaluated_graphs\":" << evaluated
      << ",\"exact_graphs\":" << exact_count << ",\"pending_graphs\":" << (journal.records.size() - evaluated)
      << ",\"unfinished_graphs\":" << unfinished << ",\"new_evaluations\":" << new_evaluations
      << ",\"stopped_by_budget_or_interrupt\":" << boolean(stopped || interrupted)
      << ",\"path_capped\":" << boolean(pool.path_capped) << ",\"candidate_capped\":" << boolean(pool.candidate_capped)
      << ",\"accepted_edit_paths\":" << pool.accepted_paths << ",\"journal_chain_sha256\":" << cli::quote(journal.chain)
      << ",\"records_sha256\":" << cli::quote(cli::sha256(records.str()))
      << ",\"time_budget_hard\":false,\"memory_budget_process_wide\":false,\"estimate_rule\":\"exact H when proved, otherwise max(certified lower,L-1); rough band is heuristic, not a certificate\"}";
    replace(o.out / "summary.json", s.str());
    return s.str();
}
}

int main(int argc, char** argv) {
    try {
        auto o = parse(argc, argv);
        std::signal(SIGINT, stop); std::signal(SIGTERM, stop);
        const auto start = Clock::now();
        const auto wall_end = o.wall_seconds ? start + std::chrono::seconds(o.wall_seconds) : Clock::time_point::max();
        Journal journal(o, configuration(o, executable_sha(argv[0])));
        Pool pool;
        bool enumeration_complete = false, stopped = false;
        std::uint64_t new_evaluations = 0;
        auto budget = [&]() { return interrupted || Clock::now() >= wall_end || (o.max_graphs && new_evaluations >= o.max_graphs); };
        auto evaluate = [&](const Graph& graph) {
            auto key = graph.key();
            auto found = journal.records.find(key);
            if (found != journal.records.end() && found->second.finished) return true;
            if (budget()) { stopped = true; return false; }
            Record r = found == journal.records.end() ? Record{} : found->second;
            r.key = key; r.finished = false; r.evaluated = true; ++new_evaluations;
            const auto graph_end = std::min(wall_end, deadline(Clock::now(), o.per_graph_ms));
            exact(graph, o, r, o.heuristics ? o.exact_depth : o.depth, graph_end);
            describe_target_reached(o, r);
            journal.save(r);
            if (o.heuristics && !r.merge && !target_reached(o, r) && !interrupted && Clock::now() < graph_end) {
                try { heuristic(graph, o, r, o.window, graph_end, journal); }
                catch (const Deadline&) { r.reason = interrupted ? "interrupted during bounded finder" : "time budget during bounded finder"; }
                catch (const std::bad_alloc&) { r.reason = "allocation failed during bounded finder"; }
            }
            r.finished = !interrupted; journal.save(r);
            if (new_evaluations <= 5 || new_evaluations % 100 == 0)
                std::cerr << "evaluated " << new_evaluations << " new graphs; " << key << ' ' << r.status
                          << " lower=" << r.lower << " upper=" << r.upper << '\n';
            return !budget();
        };
        if (!o.heuristics && o.graphs.empty()) {
            enumeration_complete = family1::LargeEnumerator(o.m).enumerate(evaluate);
            stopped |= !enumeration_complete;
        } else {
            if (o.heuristics) pool = generate(o);
            else { pool.scope = "supplied graph subset"; pool.generation_complete = true; for (const auto& key : o.graphs) pool.graphs.push_back(Graph::from_key(key)); }
            for (const auto& graph : pool.graphs) if (!journal.records.contains(graph.key())) { Record pending; pending.key = graph.key(); journal.records.emplace(pending.key, pending); }
            for (const auto& graph : pool.graphs) if (!evaluate(graph)) { stopped = true; break; }
            // Supplied graph completion is separate from complete graph-space enumeration.
            enumeration_complete = false;
        }
        if (o.heuristics && !stopped && !interrupted && Clock::now() < wall_end) {
            unsigned int k = o.window;
            while (k < o.max_window && !interrupted && Clock::now() < wall_end) {
                unsigned int top = 0;
                for (const auto& [key, r] : journal.records) if (!r.merge && !target_reached(o, r)) top = std::max(top, r.upper);
                std::vector<std::string> band;
                for (const auto& [key, r] : journal.records)
                    if (!r.merge && !target_reached(o, r) && r.upper && top - r.upper <= o.band_width) band.push_back(key);
                if (band.size() < o.crowding) break;
                k = std::min(o.max_window, k + 2);
                for (const auto& key : band) {
                    if (interrupted || Clock::now() >= wall_end) break;
                    auto r = journal.records.at(key); r.finished = false;
                    try { heuristic(Graph::from_key(key), o, r, k, std::min(wall_end, deadline(Clock::now(), o.per_graph_ms)), journal); }
                    catch (const Deadline&) { r.reason = interrupted ? "interrupted during adaptive finder" : "time budget during adaptive finder"; }
                    catch (const std::bad_alloc&) { r.reason = "allocation failed during adaptive finder"; }
                    r.finished = !interrupted; journal.save(r);
                }
            }
        }
        std::cout << publish(o, journal, pool, enumeration_complete, stopped, new_evaluations) << '\n';
        return interrupted ? 130 : 0;
    } catch (const std::exception& error) {
        std::cerr << "Family1Offline: " << error.what() << '\n'; return 2;
    }
}

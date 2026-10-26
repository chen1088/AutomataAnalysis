#include "Family1Symbolic.h"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <future>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <map>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>

namespace fs = std::filesystem;
namespace {
using Graph = family1::LargeGraph;
volatile std::sig_atomic_t interrupted = 0;
void interrupt(int) { interrupted = 1; }

struct Options {
    unsigned int min_m = 7, max_m = 20, candidates = 8, beam = 4, jobs = 1;
    std::uint64_t seed = 1088, limit_graphs = 0;
    family1::SymbolicLimits limits;
    fs::path out, seed_file = "results/family1-m1-m6/maximizers.jsonl";
    std::string graph_key;
    bool resume = false, dot = false;
};
struct Record {
    unsigned int m = 0;
    std::string key;
    family1::SymbolicScore score;
};
using Records = std::map<std::string, Record>;
using Seeds = std::map<unsigned int, std::vector<Graph>>;

std::string quote(const std::string& value)
{
    std::string out = "\"";
    const char* hex = "0123456789abcdef";
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 32) { out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15]; }
        else out += static_cast<char>(c);
    }
    return out + '"';
}
std::string unquote(const std::string& value)
{
    if (value.size() < 2 || value.front() != '"' || value.back() != '"')
        throw std::runtime_error("invalid checkpoint string");
    std::string out;
    for (std::size_t i = 1; i + 1 < value.size(); ++i) {
        char c = value[i];
        if (c != '\\') { out += c; continue; }
        if (++i + 1 >= value.size()) throw std::runtime_error("invalid checkpoint escape");
        c = value[i];
        if (c == '\\' || c == '"' || c == '/') out += c;
        else if (c == 'n') out += '\n';
        else if (c == 'r') out += '\r';
        else if (c == 't') out += '\t';
        else if (c == 'b') out += '\b';
        else if (c == 'f') out += '\f';
        else if (c == 'u' && i + 4 < value.size() && value[i + 1] == '0' && value[i + 2] == '0') {
            auto hex = [](char d) -> unsigned int {
                if (d >= '0' && d <= '9') return d - '0';
                if (d >= 'a' && d <= 'f') return d - 'a' + 10;
                if (d >= 'A' && d <= 'F') return d - 'A' + 10;
                throw std::runtime_error("invalid checkpoint hex escape");
            };
            out += static_cast<char>((hex(value[i + 3]) << 4) | hex(value[i + 4])); i += 4;
        } else throw std::runtime_error("unsupported checkpoint escape");
    }
    return out;
}
std::string field(const std::string& line, const std::string& name)
{
    auto start = line.find(quote(name) + ':');
    if (start == std::string::npos) throw std::runtime_error("missing checkpoint field: " + name);
    start += name.size() + 3;
    bool in_string = false, escape = false;
    unsigned int brackets = 0;
    for (auto i = start; i < line.size(); ++i) {
        const char c = line[i];
        if (in_string) {
            if (escape) escape = false;
            else if (c == '\\') escape = true;
            else if (c == '"') in_string = false;
        } else if (c == '"') in_string = true;
        else if (c == '[' || c == '{') ++brackets;
        else if (c == ']' || c == '}') {
            if (brackets == 0) return line.substr(start, i - start);
            --brackets;
        } else if (c == ',' && brackets == 0) return line.substr(start, i - start);
    }
    throw std::runtime_error("unterminated checkpoint field");
}
std::uint64_t number(const std::string& value)
{
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("expected nonnegative integer: " + value);
    return std::stoull(value);
}
unsigned int uint_number(const std::string& value)
{
    const auto parsed = number(value);
    if (parsed > std::numeric_limits<unsigned int>::max()) throw std::runtime_error("integer exceeds supported range");
    return static_cast<unsigned int>(parsed);
}
std::string id(unsigned int m, const std::string& key)
{
    return (m < 10 ? "0" : "") + std::to_string(m) + '_' + key;
}
std::string json(const Record& record)
{
    const auto graph = Graph::from_key(record.key);
    const auto& score = record.score;
    std::ostringstream out;
    out.imbue(std::locale::classic());
    out << "{\"m\":" << record.m << ",\"key\":" << quote(record.key) << ",\"canonical_table\":[";
    for (unsigned int s = 0; s < graph.size(); ++s) {
        if (s) out << ',';
        out << '[' << graph.ports[s][0] << ',' << graph.ports[s][1] << ']';
    }
    out << "],\"status\":" << quote(score.status) << ",\"lower_bound\":" << score.lower_bound << ",\"upper_bound\":";
    if (score.upper_bound) out << score.upper_bound; else out << "null";
    out << ",\"merge_length\":";
    if (score.status == "exact") out << score.upper_bound; else out << "null";
    out << ",\"witness\":";
    if (score.upper_bound) out << '[' << quote(score.witness[0]) << ',' << quote(score.witness[1]) << ']';
    else out << "null";
    out << ",\"seconds\":" << std::setprecision(std::numeric_limits<double>::max_digits10) << score.seconds
        << ",\"queries\":" << score.queries << ",\"mask_count\":" << score.mask_count
        << ",\"projection_lower_bound\":" << score.projection_lower_bound << ",\"projection_mask_count\":" << score.projection_mask_count
        << ",\"reason\":" << quote(score.reason) << '}';
    return out.str();
}
Record parse(const std::string& line)
{
    Record record;
    record.m = uint_number(field(line, "m"));
    record.key = unquote(field(line, "key"));
    auto& score = record.score;
    score.status = unquote(field(line, "status"));
    score.lower_bound = uint_number(field(line, "lower_bound"));
    const auto upper = field(line, "upper_bound");
    score.upper_bound = upper == "null" ? 0 : uint_number(upper);
    score.queries = uint_number(field(line, "queries"));
    score.mask_count = uint_number(field(line, "mask_count"));
    score.projection_lower_bound = uint_number(field(line, "projection_lower_bound"));
    score.projection_mask_count = uint_number(field(line, "projection_mask_count"));
    score.reason = unquote(field(line, "reason"));
    std::size_t parsed = 0;
    auto seconds = field(line, "seconds");
    score.seconds = std::stod(seconds, &parsed);
    if (parsed != seconds.size() || !std::isfinite(score.seconds) || score.seconds < 0)
        throw std::runtime_error("invalid checkpoint duration");
    if (score.upper_bound) {
        auto witness = field(line, "witness");
        if (witness.size() < 7 || witness.front() != '[' || witness.back() != ']') throw std::runtime_error("invalid checkpoint witness");
        auto middle = witness.find("\",\"");
        if (middle == std::string::npos) throw std::runtime_error("invalid checkpoint witness pair");
        score.witness = {unquote(witness.substr(1, middle)), unquote(witness.substr(middle + 2, witness.size() - middle - 3))};
        if (score.witness[0].size() != score.upper_bound || score.witness[1].size() != score.upper_bound
            || score.witness[0] == score.witness[1]
            || score.witness[0].find_first_not_of("01") != std::string::npos || score.witness[1].find_first_not_of("01") != std::string::npos)
            throw std::runtime_error("invalid checkpoint witness words");
    }
    const auto graph = Graph::from_key(record.key);
    if (record.m != graph.size() || !graph.accessible() || graph.canonical().key() != record.key || score.lower_bound == 0
        || (score.upper_bound && score.lower_bound > score.upper_bound) || score.mask_count > (1U << record.m)
        || !score.projection_lower_bound || score.projection_lower_bound > score.lower_bound
        || score.projection_mask_count > std::min(64U, 1U << record.m)
        || (score.status != "exact" && score.status != "bounded" && score.status != "lower-bound" && score.status != "incomplete")
        || (score.status == "exact" && (!score.upper_bound || score.lower_bound != score.upper_bound))
        || (score.status == "bounded" && (!score.upper_bound || score.lower_bound == score.upper_bound))
        || ((score.status == "lower-bound" || score.status == "incomplete") && score.upper_bound)
        || json(record) != line)
        throw std::runtime_error("invalid or incompatible checkpoint record");
    return record;
}
std::ofstream output(const fs::path& path)
{
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    out.exceptions(std::ios::badbit | std::ios::failbit);
    return out;
}
Seeds load_seeds(const Options& options)
{
    Seeds result;
    if (!options.graph_key.empty()) return result;
    std::ifstream input(options.seed_file, std::ios::binary);
    if (!input) throw std::runtime_error("missing seed results; run from repository root or use --seeds FILE");
    std::string line;
    std::map<std::string, Graph> unique;
    while (std::getline(input, line)) {
        if (line.empty()) continue;
        auto m = uint_number(field(line, "m"));
        auto key = unquote(field(line, "key"));
        Graph graph = [&] {
            if (key.size() == 4 * m) return Graph::from_key(key);
            if (m > 6 || key.size() != 2 * m || key.find_first_not_of("012345") != std::string::npos)
                throw std::runtime_error("invalid seed graph key");
            std::vector<Graph::Row> rows(m);
            for (unsigned int s = 0; s < m; ++s) rows[s] = {static_cast<unsigned int>(key[2 * s] - '0'), static_cast<unsigned int>(key[2 * s + 1] - '0')};
            return Graph(std::move(rows));
        }();
        if (graph.size() != m || !graph.accessible()) throw std::runtime_error("invalid inaccessible seed");
        graph = graph.canonical();
        unique.emplace(id(m, graph.key()), std::move(graph));
    }
    if (input.bad()) throw std::runtime_error("seed results read failed");
    if (unique.empty()) throw std::runtime_error("seed results contain no graph");
    for (auto& [key, graph] : unique) result[graph.size()].push_back(std::move(graph));
    return result;
}
std::string config(const Options& options, const Seeds& seeds)
{
    std::ostringstream out;
    out << "{\"schema\":1,\"method\":\"heuristic-growth-mutation-static-mask-sat-v1\",\"min_m\":" << options.min_m
        << ",\"max_m\":" << options.max_m << ",\"candidates\":" << options.candidates << ",\"beam\":" << options.beam;
    // Keep the original jobs=1 configuration byte-identical for existing runs.
    if (options.jobs != 1) out << ",\"jobs\":" << options.jobs;
    if (options.limits.projection_masks != 64) out << ",\"projection_masks\":" << options.limits.projection_masks;
    if (options.limits.projection_seed != 0x46414d31U) out << ",\"projection_seed\":" << options.limits.projection_seed;
    out << ",\"seed\":" << options.seed << ",\"timeout_ms\":" << options.limits.timeout_ms
        << ",\"solve_timeout_ms\":" << options.limits.solve_timeout_ms << ",\"max_length\":" << options.limits.max_length
        << ",\"max_refinements\":" << options.limits.max_refinements
        << ",\"projection_depth\":" << options.limits.projection_depth << ",\"projection_max_states\":" << options.limits.projection_max_states
        << ",\"graph\":" << quote(options.graph_key) << ",\"seed_graphs\":[";
    bool comma = false;
    for (const auto& [m, graphs] : seeds) for (const auto& graph : graphs) {
        if (comma) out << ',';
        comma = true;
        out << quote(graph.key());
    }
    out << "]}";
    return out.str();
}
Records load(const Options& options, const std::string& configuration)
{
    std::ifstream metadata(options.out / "run.json", std::ios::binary);
    std::string line;
    std::getline(metadata, line);
    if (!metadata || line != configuration) throw std::runtime_error("resume requires the same generation settings, scoring limits, and seed graphs");
    const auto path = options.out / "checkpoint.jsonl";
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("missing checkpoint.jsonl");
    Records result;
    std::uintmax_t valid_bytes = 0;
    while (std::getline(input, line)) {
        if (input.eof()) break;
        auto record = parse(line);
        if (record.m < options.min_m || record.m > options.max_m || record.score.lower_bound > options.limits.max_length + 1
            || record.score.upper_bound > options.limits.max_length
            || (!options.graph_key.empty() && record.key != options.graph_key))
            throw std::runtime_error("checkpoint score outside configured scope");
        result[id(record.m, record.key)] = std::move(record);
        valid_bytes += line.size() + 1;
    }
    if (input.bad()) throw std::runtime_error("checkpoint read failed");
    input.close();
    if (fs::file_size(path) != valid_bytes) {
        fs::resize_file(path, valid_bytes);
        std::cerr << "Discarded uncommitted final checkpoint fragment\n";
    }
    return result;
}

// The engine and explicit modulus choices make candidate generation independent
// of the standard library's uniform-distribution implementation. This is a
// heuristic distribution, not a uniform sample of rooted graph classes.
unsigned int choice(std::mt19937_64& random, unsigned int bound)
{
    return static_cast<unsigned int>(random() % bound);
}
Graph random_graph(unsigned int m, std::mt19937_64& random)
{
    std::vector<Graph::Row> rows(m);
    for (unsigned int s = 0; s < m; ++s) rows[s] = {(s + 1) % m, choice(random, m)};
    return Graph(std::move(rows)).canonical();
}
Graph grow(const Graph& parent, std::mt19937_64& random)
{
    auto rows = parent.ports;
    const auto source = choice(random, parent.size()), port = choice(random, 2);
    const auto target = rows[source][port];
    rows[source][port] = parent.size();
    rows.push_back({target, choice(random, parent.size() + 1)});
    // Replacing s->t with s->new->t preserves all old root paths and reaches new.
    return Graph(std::move(rows)).canonical();
}
Graph mutate(const Graph& parent, std::mt19937_64& random)
{
    auto rows = parent.ports;
    const auto changes = 1 + choice(random, 2);
    for (unsigned int i = 0; i < changes; ++i)
        rows[choice(random, parent.size())][choice(random, 2)] = choice(random, parent.size());
    Graph candidate(std::move(rows));
    return candidate.accessible() ? candidate.canonical() : parent;
}
std::vector<Graph> initial_parents(const Options& options, const Seeds& seeds, std::mt19937_64& random)
{
    std::vector<Graph> parents;
    for (const auto& [m, graphs] : seeds) {
        if (m >= options.min_m) break;
        parents = graphs;
    }
    if (parents.empty()) parents.emplace_back(std::vector<Graph::Row>{{0, 0}});
    if (parents.size() > options.beam) parents.erase(parents.begin() + options.beam, parents.end());
    while (parents.front().size() + 1 < options.min_m)
        for (auto& parent : parents) parent = grow(parent, random);
    return parents;
}
std::vector<Graph> candidate_pool(unsigned int m, const Options& options, const Seeds& seeds,
                                  const std::vector<Graph>& parents, std::mt19937_64& random)
{
    if (!options.graph_key.empty()) return {Graph::from_key(options.graph_key)};
    std::map<std::string, Graph> unique;
    if (auto known = seeds.find(m); known != seeds.end())
        for (const auto& graph : known->second) unique.emplace(graph.key(), graph);
    unsigned int target = std::max(options.candidates, static_cast<unsigned int>(unique.size()));
    constexpr unsigned int small_classes[]{0, 1, 6, 57, 678, 10398, 192181};
    if (m <= 6) target = std::min(target, small_classes[m]);
    auto parent_candidate = [&](unsigned int index) {
        const auto& parent = parents[index % parents.size()];
        return parent.size() < m ? grow(parent, random) : mutate(parent, random);
    };
    const auto max_attempts = std::max<std::uint64_t>(10000, static_cast<std::uint64_t>(target) * 1000);
    for (std::uint64_t attempt = 0; unique.size() < target && attempt < max_attempts && !interrupted; ++attempt) {
        Graph graph = [&] {
            if (attempt < parents.size()) return parent_candidate(static_cast<unsigned int>(attempt));
            const auto mode = choice(random, 4);
            if (mode == 0) return random_graph(m, random);
            if (mode == 1 || unique.empty()) return parent_candidate(choice(random, static_cast<unsigned int>(parents.size())));
            auto base = unique.begin();
            std::advance(base, choice(random, static_cast<unsigned int>(unique.size())));
            return mutate(base->second, random);
        }();
        unique.emplace(graph.key(), std::move(graph));
    }
    std::vector<Graph> result;
    for (auto& [key, graph] : unique) result.push_back(std::move(graph));
    return result;
}
std::vector<Graph> select_parents(const std::vector<Graph>& pool, const Records& records, unsigned int beam)
{
    auto ordered = pool;
    ordered.erase(std::remove_if(ordered.begin(), ordered.end(), [&](const Graph& graph) {
        return records.find(id(graph.size(), graph.key())) == records.end();
    }), ordered.end());
    std::sort(ordered.begin(), ordered.end(), [&](const Graph& a, const Graph& b) {
        const auto& left = records.at(id(a.size(), a.key())).score;
        const auto& right = records.at(id(b.size(), b.key())).score;
        if (left.lower_bound != right.lower_bound) return left.lower_bound > right.lower_bound;
        if ((left.status == "exact") != (right.status == "exact")) return left.status == "exact";
        if (left.upper_bound != right.upper_bound) return left.upper_bound > right.upper_bound;
        return a.key() < b.key();
    });
    if (ordered.size() > beam) ordered.erase(ordered.begin() + beam, ordered.end());
    return ordered;
}
void drawing(const Options& options, const Record& record)
{
    fs::create_directories(options.out / "dot");
    auto out = output(options.out / "dot" / ("m" + std::to_string(record.m) + '_' + record.key + ".dot"));
    const auto graph = Graph::from_key(record.key);
    out << "digraph Family1 {\n  rankdir=LR;\n  start [shape=point]; start -> 0;\n";
    for (unsigned int s = 0; s < record.m; ++s) {
        out << "  " << s << " [shape=" << (s ? "circle" : "doublecircle") << "];\n";
        for (unsigned int p = 0; p < 2; ++p) out << "  " << s << " -> " << graph.ports[s][p] << " [label=\"tau" << p << "\"];\n";
    }
    out << "}\n";
}
void exports(const Options& options, const Records& records, bool traversal_complete)
{
    struct Summary { unsigned int evaluated = 0, exact = 0, lower = 0, best_exact = 0, lower_ties = 0, exact_ties = 0; };
    std::array<Summary, 21> summary{};
    for (const auto& [key, record] : records) {
        auto& item = summary[record.m];
        ++item.evaluated;
        if (record.score.lower_bound > item.lower) { item.lower = record.score.lower_bound; item.lower_ties = 0; }
        if (record.score.lower_bound == item.lower) ++item.lower_ties;
        if (record.score.status == "exact") {
            ++item.exact;
            if (record.score.upper_bound > item.best_exact) { item.best_exact = record.score.upper_bound; item.exact_ties = 0; }
            if (record.score.upper_bound == item.best_exact) ++item.exact_ties;
        }
    }
    auto all = output(options.out / "graphs.jsonl");
    auto lower = output(options.out / "best_lower_bound.jsonl");
    auto exact = output(options.out / "best_exact.jsonl");
    auto potential = output(options.out / "potential_best.jsonl");
    for (const auto& [key, record] : records) {
        const auto text = json(record);
        const auto& item = summary[record.m];
        all << text << '\n';
        const bool best_lower = record.score.lower_bound == item.lower;
        const bool best_exact = record.score.status == "exact" && record.score.upper_bound == item.best_exact;
        if (best_lower) lower << text << '\n';
        if (best_exact) exact << text << '\n';
        if (!record.score.upper_bound || record.score.upper_bound >= item.lower) potential << text << '\n';
        if (options.dot && (best_lower || best_exact)) drawing(options, record);
    }
    auto out = output(options.out / "summary.json");
    out << "{\"schema\":1,\"method\":\"heuristic-graph-exploration\",\"enumeration_complete\":false,\"maximum_certified\":false,\"global_maximum\":null,\"candidate_traversal_complete\":"
        << (traversal_complete ? "true" : "false") << ",\"min_m\":" << options.min_m << ",\"max_m\":" << options.max_m << ",\"sizes\":[";
    for (unsigned int m = options.min_m; m <= options.max_m; ++m) {
        if (m != options.min_m) out << ',';
        const auto& item = summary[m];
        out << "{\"m\":" << m << ",\"enumeration_complete\":false,\"maximum_certified\":false,\"global_maximum\":null,\"evaluated\":"
            << item.evaluated << ",\"exact\":" << item.exact << ",\"largest_certified_lower_bound\":";
        if (item.lower) out << item.lower; else out << "null";
        out << ",\"best_exact_merge_length\":";
        if (item.best_exact) out << item.best_exact; else out << "null";
        out << ",\"best_lower_bound_count\":" << item.lower_ties << ",\"best_exact_count\":" << item.exact_ties << '}';
        std::cout << "m=" << m << " evaluated=" << item.evaluated << " exact=" << item.exact << " largest_certified_lower_bound=" << item.lower
                  << " lower_ties=" << item.lower_ties << " best_exact=" << item.best_exact << " exact_ties=" << item.exact_ties << " global_maximum=unproved\n";
    }
    out << "]}\n";
}
Options options(int argc, char** argv)
{
    Options result;
    bool min_set = false, max_set = false;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help") {
            std::cout << "Family1Explore --out DIR [--min-m 7 --max-m 20 --candidates 8 --beam 4]\n"
                "  [--seed 1088 --timeout-ms 10000 --solve-timeout-ms 2000 --max-length 64]\n"
                "  [--max-refinements 256 --projection-depth 20 --projection-max-states 1048576]\n"
                "  [--projection-masks 64 --mask-seed 1178684721]\n"
                "  [--jobs 1 --resume --dot --limit-graphs N --seeds FILE]\n"
                "  [--graph FIXED_WIDTH_KEY] scores one supplied root-accessible graph.\n"
                "Graph coverage is heuristic. Per-graph SAT scores/bounds are certified.\n"
                "All evaluated graphs and all best exact/lower-bound ties are retained.\n"
                "Projection depth supports 0..26 and states 1..2^26.\n"
                "Jobs 1..32 score independent graphs concurrently; memory scales with jobs.\n";
            std::exit(0);
        }
        if (arg == "--resume") result.resume = true;
        else if (arg == "--dot") result.dot = true;
        else {
            if (++i >= argc) throw std::runtime_error("missing option value: " + arg);
            const std::string value = argv[i];
            if (arg == "--out") result.out = value;
            else if (arg == "--seeds") result.seed_file = value;
            else if (arg == "--graph") result.graph_key = value;
            else if (arg == "--min-m") { result.min_m = uint_number(value); min_set = true; }
            else if (arg == "--max-m") { result.max_m = uint_number(value); max_set = true; }
            else if (arg == "--candidates") result.candidates = uint_number(value);
            else if (arg == "--beam") result.beam = uint_number(value);
            else if (arg == "--jobs") result.jobs = uint_number(value);
            else if (arg == "--seed") result.seed = number(value);
            else if (arg == "--timeout-ms") result.limits.timeout_ms = number(value);
            else if (arg == "--solve-timeout-ms") result.limits.solve_timeout_ms = number(value);
            else if (arg == "--max-length") result.limits.max_length = uint_number(value);
            else if (arg == "--max-refinements") result.limits.max_refinements = uint_number(value);
            else if (arg == "--projection-depth") result.limits.projection_depth = uint_number(value);
            else if (arg == "--projection-masks") result.limits.projection_masks = uint_number(value);
            else if (arg == "--mask-seed") result.limits.projection_seed = uint_number(value);
            else if (arg == "--projection-max-states") result.limits.projection_max_states = number(value);
            else if (arg == "--limit-graphs") result.limit_graphs = number(value);
            else throw std::runtime_error("unknown option: " + arg);
        }
    }
    if (!result.graph_key.empty()) {
        auto graph = Graph::from_key(result.graph_key);
        if (!graph.accessible()) throw std::runtime_error("supplied graph is not root-accessible");
        if ((min_set && result.min_m != graph.size()) || (max_set && result.max_m != graph.size()))
            throw std::runtime_error("supplied graph size disagrees with requested range");
        result.min_m = result.max_m = graph.size(); result.graph_key = graph.canonical().key();
    }
    if (result.out.empty() || result.min_m < 1 || result.min_m > result.max_m || result.max_m > 20
        || !result.candidates || result.candidates > 100000 || !result.beam || result.beam > 100000 || !result.jobs || result.jobs > 32
        || !result.limits.timeout_ms || !result.limits.solve_timeout_ms || !result.limits.max_refinements
        || !result.limits.max_length || result.limits.max_length > 4096 || result.limits.projection_depth > 26
        || !result.limits.projection_masks || result.limits.projection_masks > 64
        || !result.limits.projection_max_states || result.limits.projection_max_states > (1ULL << 26))
        throw std::runtime_error("require --out DIR, 1 <= min-m <= max-m <= 20, candidates/beam in 1..100000, jobs 1..32, length 1..4096, positive SAT budgets");
    result.limits.interrupted = &interrupted;
    return result;
}
}

int main(int argc, char** argv)
{
    try {
        const auto opts = options(argc, argv);
        std::signal(SIGINT, interrupt); std::signal(SIGTERM, interrupt);
        const auto seeds = load_seeds(opts);
        const auto configuration = config(opts, seeds);
        fs::create_directories(opts.out);
        Records records;
        if (opts.resume) records = load(opts, configuration);
        else {
            if (!fs::is_empty(opts.out)) throw std::runtime_error("new run requires an empty output directory; use --resume");
            auto metadata = output(opts.out / "run.json"); metadata << configuration << '\n';
        }
        std::ofstream journal(opts.out / "checkpoint.jsonl", std::ios::binary | std::ios::app);
        journal.exceptions(std::ios::badbit | std::ios::failbit);
        std::mt19937_64 random(opts.seed);
        auto parents = initial_parents(opts, seeds, random);
        std::set<std::string> visited;
        bool complete = true;
        std::uint64_t newly_evaluated = 0;
        for (unsigned int m = opts.min_m; m <= opts.max_m && complete; ++m) {
            const auto pool = candidate_pool(m, opts, seeds, parents, random);
            struct Pending {
                std::string key, record_id;
                std::future<family1::SymbolicScore> result;
            };
            std::vector<Pending> pending;
            pending.reserve(opts.jobs);
            // Workers finish independently, but commits always follow pool order.
            // No worker mutates shared records, candidate state, or journal data.
            auto commit = [&] {
                for (auto& item : pending) {
                    Record record; record.m = m; record.key = item.key;
                    record.score = item.result.get();
                    if (interrupted && record.score.status != "exact") record.score.reason = "interrupted";
                    journal << json(record) << '\n'; journal.flush();
                    records[item.record_id] = record;
                    std::cout << "evaluated m=" << m << " key=" << item.key << " status=" << record.score.status
                        << " lower=" << record.score.lower_bound << " upper=";
                    if (record.score.upper_bound) std::cout << record.score.upper_bound; else std::cout << "unknown";
                    std::cout << " seconds=" << record.score.seconds << " reason=" << record.score.reason << std::endl;
                }
                pending.clear();
            };
            for (const auto& graph : pool) {
                auto key = graph.key(), record_id = id(m, key);
                visited.insert(record_id);
                auto found = records.find(record_id);
                if (found != records.end() && found->second.score.reason != "interrupted") continue;
                if (interrupted || (opts.limit_graphs && newly_evaluated >= opts.limit_graphs)) { complete = false; break; }
                auto task = std::async(std::launch::async, [graph, limits = opts.limits] {
                    try { return family1::certify(graph, limits); }
                    catch (const std::exception& error) {
                        family1::SymbolicScore score;
                        score.reason = std::string("worker-error: ") + error.what();
                        return score;
                    }
                });
                pending.push_back({std::move(key), std::move(record_id), std::move(task)});
                // Count launches rather than commits so a partially filled batch
                // cannot evaluate beyond the caller's per-invocation graph limit.
                ++newly_evaluated;
                if (pending.size() == opts.jobs) {
                    commit();
                    if (interrupted) { complete = false; break; }
                }
            }
            // Joining here also drains a partial batch after a limit or signal.
            commit();
            if (!complete || interrupted) { complete = false; break; }
            parents = select_parents(pool, records, opts.beam);
            if (parents.empty()) { complete = false; break; }
        }
        journal.close();
        if (complete) for (const auto& [key, record] : records)
            if (!visited.contains(key)) throw std::runtime_error("checkpoint graph is outside the deterministic candidate traversal");
        exports(opts, records, complete);
        std::cout << "Heuristic exploration results: " << fs::absolute(opts.out).string() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Family1Explore: " << error.what() << '\n'; return 1;
    }
}

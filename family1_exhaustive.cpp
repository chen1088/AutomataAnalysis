#include "Family1ExactPacked.h"
#include "Family1LayerSearch.h"
#include "Family1LargeEnumerator.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <future>
#include <iostream>
#include <iterator>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
namespace {
using Graph = family1::LargeGraph;
using Pair = std::array<std::string, 2>;
volatile std::sig_atomic_t interrupted = 0;
void stop(int) { interrupted = 1; }

struct Options {
    unsigned int states = 7, target = 29, jobs = 8, batch_size = 4096;
    unsigned int witness_limit = 0;
    unsigned int layer_step = 2;
    std::string backend = "packed";
    std::string layer_storage = "packed";
    std::uint64_t limit_graphs = 0;
    family1::PackedLimits limits;
    fs::path out;
    fs::path input;
    std::vector<fs::path> seeds;
    std::vector<fs::path> layer_reports;
    bool resume = false;
    Options() {
        limits.depth = 16;
        limits.max_layer_states = 1ULL << 16;
        limits.max_working_bytes = 32ULL << 20;
        limits.timeout_ms = 10000;
        limits.interrupted = &interrupted;
    }
};
struct Record {
    unsigned int m = 0;
    std::uint64_t ordinal = 0;
    std::string key, status = "incomplete", reason;
    unsigned int lower = 1, upper = 0, exact = 0;
    Pair witness{};
};

std::string quote(const std::string& value)
{
    std::string result = "\"";
    for (unsigned char c : value) {
        if (c == '\\' || c == '"') { result += '\\'; result += c; }
        else if (c == '\n') result += "\\n";
        else if (c == '\r') result += "\\r";
        else if (c == '\t') result += "\\t";
        else if (c < 32) throw std::runtime_error("unsupported JSON control character");
        else result += c;
    }
    return result + '"';
}
std::string field(const std::string& line, const std::string& name)
{
    auto begin = line.find(quote(name) + ':');
    if (begin == std::string::npos) throw std::runtime_error("missing JSON field: " + name);
    begin += name.size() + 3;
    bool quoted = false, escape = false;
    unsigned int nesting = 0;
    for (auto index = begin; index < line.size(); ++index) {
        const auto c = line[index];
        if (quoted) {
            if (escape) escape = false;
            else if (c == '\\') escape = true;
            else if (c == '"') quoted = false;
        } else if (c == '"') quoted = true;
        else if (c == '[' || c == '{') ++nesting;
        else if (c == ']' || c == '}') {
            if (!nesting) return line.substr(begin, index - begin);
            --nesting;
        } else if (c == ',' && !nesting) return line.substr(begin, index - begin);
    }
    throw std::runtime_error("unterminated JSON field: " + name);
}
std::string unquote(const std::string& value)
{
    if (value.size() < 2 || value.front() != '"' || value.back() != '"'
        || value.find('\\') != std::string::npos) throw std::runtime_error("invalid generated JSON string");
    return value.substr(1, value.size() - 2);
}
std::uint64_t number(const std::string& value)
{
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("invalid unsigned integer: " + value);
    return std::stoull(value);
}
unsigned int uint_number(const std::string& value)
{
    const auto n = number(value);
    if (n > std::numeric_limits<unsigned int>::max()) throw std::runtime_error("integer exceeds unsigned range");
    return static_cast<unsigned int>(n);
}
Pair pair_from(const std::string& value)
{
    if (value.size() < 7 || value.substr(0, 2) != "[\"" || value.substr(value.size() - 2) != "\"]")
        throw std::runtime_error("invalid witness pair");
    const auto middle = value.find("\",\"", 2);
    if (middle == std::string::npos) throw std::runtime_error("invalid witness pair separator");
    Pair result{value.substr(2, middle - 2), value.substr(middle + 3, value.size() - middle - 5)};
    if (result[0].empty() || result[0].size() != result[1].size() || result[0] == result[1]
        || result[0].find_first_not_of("01") != std::string::npos
        || result[1].find_first_not_of("01") != std::string::npos)
        throw std::runtime_error("witness must have distinct positive equal-length binary words");
    return result;
}
Pair normalize(Pair result)
{
    if (result[0] > result[1]) std::swap(result[0], result[1]);
    auto complement = result;
    for (auto& word : complement) for (auto& c : word) c = c == '0' ? '1' : '0';
    if (complement[0] > complement[1]) std::swap(complement[0], complement[1]);
    return std::min(result, complement);
}
std::string pair_json(const Pair& pair)
{
    return '[' + quote(pair[0]) + ',' + quote(pair[1]) + ']';
}

// Independent ordinary-state trajectories over EVERY ORIGINAL static mask.
// This is the sole authorization to emit a verified upper-bound witness.
bool collision(const Graph& graph, const Pair& words)
{
    const auto masks = 1U << graph.size();
    for (unsigned int mask = 0; mask < masks; ++mask) {
        unsigned int a = 0, b = 0;
        for (unsigned int index = 0; index < words[0].size(); ++index) {
            a = graph.ports[a][(words[0][index] - '0') ^ ((mask >> a) & 1U)];
            b = graph.ports[b][(words[1][index] - '0') ^ ((mask >> b) & 1U)];
        }
        if (a != b) return false;
    }
    return true;
}
std::string json(const Record& record)
{
    const auto graph = Graph::from_key(record.key);
    std::ostringstream output;
    output << "{\"m\":" << record.m << ",\"ordinal\":" << record.ordinal << ",\"key\":" << quote(record.key)
        << ",\"canonical_table\":[";
    for (unsigned int state = 0; state < record.m; ++state) {
        if (state) output << ',';
        output << '[' << graph.ports[state][0] << ',' << graph.ports[state][1] << ']';
    }
    output << "],\"status\":" << quote(record.status) << ",\"lower_bound\":" << record.lower
        << ",\"upper_bound\":" << (record.upper ? std::to_string(record.upper) : "null")
        << ",\"merge_length\":" << (record.exact ? std::to_string(record.exact) : "null")
        << ",\"witness\":" << (record.upper ? pair_json(record.witness) : "null")
        << ",\"reason\":" << quote(record.reason) << '}';
    return output.str();
}
Record parse(const std::string& line)
{
    Record record;
    record.m = uint_number(field(line, "m"));
    record.ordinal = number(field(line, "ordinal"));
    record.key = unquote(field(line, "key"));
    record.status = unquote(field(line, "status"));
    record.reason = unquote(field(line, "reason"));
    record.lower = uint_number(field(line, "lower_bound"));
    auto value = field(line, "upper_bound");
    record.upper = value == "null" ? 0 : uint_number(value);
    value = field(line, "merge_length");
    record.exact = value == "null" ? 0 : uint_number(value);
    if (record.upper) record.witness = pair_from(field(line, "witness"));
    const auto graph = Graph::from_key(record.key);
    if (graph.size() != record.m || !graph.accessible() || graph.canonical() != graph || !record.lower
        || (record.upper && (record.upper < record.lower || record.witness[0].size() != record.upper))
        || (record.status != "bounded" && record.status != "exact"
            && record.status != "depth-capped" && record.status != "incomplete")
        || (record.status == "exact") != (record.exact != 0)
        || (record.exact && (record.exact != record.lower || record.exact != record.upper))
        || (record.status == "bounded" && !record.upper)
        || json(record) != line)
        throw std::runtime_error("invalid exhaustive checkpoint record");
    if (record.upper && !collision(graph, record.witness)) throw std::runtime_error("checkpoint witness is false");
    return record;
}

struct Library {
    struct Node { unsigned int parent = 0, child[2]{}; unsigned char input = 0; };
    struct Entry { Pair words; std::uint64_t frequency; std::array<unsigned int, 2> terminal; };
    std::map<Pair, std::uint64_t> frequencies;
    std::vector<Node> nodes{Node{}};
    std::vector<Entry> ordered;
    unsigned int insert(const std::string& word) {
        unsigned int node = 0;
        for (auto letter : word) {
            const auto input = static_cast<unsigned int>(letter - '0');
            if (!nodes[node].child[input]) {
                const auto next = static_cast<unsigned int>(nodes.size());
                nodes[node].child[input] = next;
                nodes.push_back({node, {0, 0}, static_cast<unsigned char>(input)});
            }
            node = nodes[node].child[input];
        }
        return node;
    }
    void rebuild() {
        ordered.clear(); ordered.reserve(frequencies.size());
        for (const auto& [pair, frequency] : frequencies)
            ordered.push_back({pair, frequency, {insert(pair[0]), insert(pair[1])}});
        std::sort(ordered.begin(), ordered.end(), [](const auto& a, const auto& b) {
            return a.frequency != b.frequency ? a.frequency > b.frequency : a.words < b.words;
        });
    }
    void learn(const Record& record, unsigned int target) {
        if (record.upper && record.upper <= target) ++frequencies[normalize(record.witness)];
    }
};
struct Imported {
    unsigned int lower = 1, upper = 0;
    Pair witness{};
};
struct Reports {
    std::map<std::string, Imported> graphs;
    unsigned int lower_reports = 0, upper_reports = 0;
};
Reports read_reports(const Options& options)
{
    Reports reports;
    std::ostringstream provenance;
    for (const auto& path : options.layer_reports) {
        std::ifstream input(path, std::ios::binary);
        if (!input) throw std::runtime_error("cannot read layer report: " + path.string());
        const std::string bytes((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
        auto line = bytes;
        while (!line.empty() && (line.back() == '\n' || line.back() == '\r')) line.pop_back();
        if (unquote(field(line, "method")) != "independent-one-hot-DFS-hash-radix-full-state-replay"
            || uint_number(field(line, "m")) != options.states || !unquote(field(line, "reason")).empty())
            throw std::runtime_error("incomplete or incompatible external layer report");
        const auto key = unquote(field(line, "key"));
        const auto graph = Graph::from_key(key);
        const auto depth = uint_number(field(line, "depth"));
        const auto status = unquote(field(line, "status"));
        if (graph.size() != options.states || !graph.accessible() || graph.canonical() != graph
            || !depth || depth > 33) throw std::runtime_error("invalid external layer graph/depth");
        auto& bound = reports.graphs[key];
        if (status == "collision-free") {
            const auto lower = uint_number(field(line, "lower_bound"));
            if (lower != depth + 1 || field(line, "upper_bound") != "null" || field(line, "witness") != "null"
                || number(field(line, "generated_representatives")) != (1ULL << (depth - 1)))
                throw std::runtime_error("invalid completed collision-free layer report");
            bound.lower = std::max(bound.lower, lower);
            ++reports.lower_reports;
        } else if (status == "collision-found") {
            const auto upper = uint_number(field(line, "upper_bound"));
            const auto words = pair_from(field(line, "witness"));
            if (uint_number(field(line, "lower_bound")) != 1 || upper != depth || words[0].size() != upper
                || !collision(graph, words)) throw std::runtime_error("invalid external layer collision witness");
            if (!bound.upper || upper < bound.upper) { bound.upper = upper; bound.witness = words; }
            ++reports.upper_reports;
        } else throw std::runtime_error("external layer report is not a completed decision");
        if (bound.upper && bound.lower > bound.upper) throw std::runtime_error("external layer reports contradict");
        provenance << "{\"source\":" << quote(path.generic_string()) << ",\"key\":" << quote(key)
            << ",\"kind\":" << quote(status) << ",\"byte_content\":" << quote(bytes) << "}\n";
    }
    if (!options.layer_reports.empty()) {
        const auto path = options.out / "layer-report-provenance.jsonl";
        if (options.resume) {
            std::ifstream input(path, std::ios::binary);
            if (!input) throw std::runtime_error("missing imported layer report provenance");
            const std::string previous((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
            if (previous != provenance.str()) throw std::runtime_error("imported layer report changed since checkpoint");
        } else {
            std::ofstream output(path, std::ios::binary | std::ios::trunc);
            output << provenance.str();
            if (!output) throw std::runtime_error("layer provenance write failed");
        }
    }
    return reports;
}
struct Worker {
    struct Cache { std::array<std::uint32_t, 4> epoch{}; std::array<unsigned char, 4> state{}; };
    std::vector<Cache> cache;
    std::uint32_t epoch = 0;
    unsigned int endpoint(const Graph& graph, const Library& library, unsigned int node,
        unsigned int slot, unsigned int mask) {
        std::array<unsigned int, 64> path{};
        unsigned int count = 0, current = node;
        while (current && cache[current].epoch[slot] != epoch) {
            if (count == path.size()) throw std::runtime_error("witness cache depth exceeds 64");
            path[count++] = current;
            current = library.nodes[current].parent;
        }
        unsigned int state = current ? cache[current].state[slot] : 0;
        while (count) {
            current = path[--count];
            state = graph.ports[state][library.nodes[current].input ^ ((mask >> state) & 1U)];
            cache[current].epoch[slot] = epoch;
            cache[current].state[slot] = static_cast<unsigned char>(state);
        }
        return state;
    }
    Record evaluate(const Graph& graph, std::uint64_t ordinal, const Library& library, const Options& options,
        const Record* prior, const Reports& reports) {
        if (++epoch == 0) { cache.clear(); epoch = 1; }
        cache.resize(library.nodes.size());
        Record record;
        record.m = graph.size(); record.ordinal = ordinal; record.key = graph.key();
        if (prior) {
            if (prior->ordinal != ordinal || prior->key != record.key || prior->m != record.m)
                throw std::runtime_error("refinement input differs from deterministic enumeration");
            record = *prior;
        }
        if (const auto found = reports.graphs.find(record.key); found != reports.graphs.end()) {
            const auto& bound = found->second;
            record.lower = std::max(record.lower, bound.lower);
            if (bound.upper && (!record.upper || bound.upper < record.upper)) {
                record.upper = bound.upper; record.witness = bound.witness;
            }
            if (record.upper && record.lower > record.upper) throw std::runtime_error("imported bounds contradict prior record");
            if (record.upper && record.lower == record.upper) {
                record.status = "exact"; record.exact = record.upper;
                record.reason = "completed-layer-report-provenance";
            }
        }
        if (record.upper && record.lower == record.upper) {
            record.status = "exact"; record.exact = record.upper;
            if (record.reason.empty()) record.reason = "verified-upper-plus-prior-lower";
        }
        if (record.exact || (record.upper && record.upper < options.target)) return record;
        const auto all = (1U << graph.size()) - 1;
        const std::array<unsigned int, 4> masks{0, all, all & 0x55555555U, all & 0xaaaaaaaaU};
        for (const auto& entry : library.ordered) {
            if (interrupted) { record.reason = "interrupted"; return record; }
            // A prior completed layer has already ruled out every shorter
            // collision. Refinement need not resimulate those library pairs.
            if (entry.words[0].size() < record.lower) continue;
            bool possible = true;
            for (unsigned int slot = 0; slot < masks.size(); ++slot)
                if (endpoint(graph, library, entry.terminal[0], slot, masks[slot])
                    != endpoint(graph, library, entry.terminal[1], slot, masks[slot])) { possible = false; break; }
            if (possible && collision(graph, entry.words)) {
                const auto upper = static_cast<unsigned int>(entry.words[0].size());
                if (upper < record.lower) throw std::runtime_error("new upper witness contradicts prior lower bound");
                if (!record.upper || upper < record.upper) { record.upper = upper; record.witness = entry.words; }
                if (record.lower == record.upper) {
                    record.status = "exact"; record.exact = record.upper;
                    record.reason = "verified-upper-plus-prior-lower";
                    return record;
                }
                if (record.upper < options.target) {
                    record.status = "bounded"; record.reason = "verified-witness-below-target";
                    return record;
                }
                // A witness at the target can still be a tie. Continue
                // looking for a strictly shorter certificate before scoring.
                continue;
            }
        }
        auto limits = options.limits;
        if (record.upper) limits.depth = std::min(limits.depth, record.upper - 1);
        if (record.lower >= limits.depth + 1) {
            if (!prior && record.lower == 1) { record.status = "depth-capped"; record.reason = "depth"; }
            return record;
        }
        if (options.backend == "layer") {
            const auto started = std::chrono::steady_clock::now();
            while (true) {
                const auto horizon = record.upper ? std::min(options.limits.depth, record.upper - 1) : options.limits.depth;
                if (record.lower > horizon) {
                    record.status = "depth-capped"; record.reason = "depth"; return record;
                }
                family1::LayerLimits layer_limits;
                layer_limits.depth = std::min(horizon, record.lower + options.layer_step - 1);
                layer_limits.max_layer_states = options.limits.max_layer_states;
                layer_limits.max_working_bytes = options.limits.max_working_bytes;
                layer_limits.interrupted = options.limits.interrupted;
                layer_limits.retain_word_indices = options.layer_storage != "compact";
                layer_limits.pack_word_indices = options.layer_storage == "packed";
                if (options.limits.timeout_ms) {
                    const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                        std::chrono::steady_clock::now() - started).count();
                    if (elapsed >= options.limits.timeout_ms) {
                        record.status = "incomplete"; record.reason = "timeout"; return record;
                    }
                    layer_limits.timeout_ms = options.limits.timeout_ms - elapsed;
                }
                const auto layer = family1::search_layer(graph, layer_limits);
                record.lower = std::max(record.lower, layer.lower_bound);
                if (layer.status == "collision") {
                    if (!collision(graph, layer.witness)) throw std::runtime_error("layer witness fails scalar all-mask check");
                    if (!record.upper || layer.upper_bound < record.upper) {
                        record.upper = layer.upper_bound; record.witness = layer.witness;
                    }
                    if (record.lower > record.upper) throw std::runtime_error("layer collision contradicts prior lower");
                } else if (layer.status == "incomplete") {
                    record.status = "incomplete"; record.reason = layer.reason; return record;
                } else if (layer.status != "collision-free") throw std::runtime_error("invalid single-layer outcome");
                if (record.upper && record.lower == record.upper) {
                    record.status = "exact"; record.exact = record.upper;
                    record.reason = "verified-upper-plus-layer-lower"; return record;
                }
                if (record.upper && record.upper < options.target) {
                    record.status = "bounded"; record.reason = "verified-layer-witness-below-target"; return record;
                }
            }
        }
        const auto previous_lower = record.lower;
        const auto score = family1::score_packed(graph, limits);
        record.lower = std::max(record.lower, score.lower_bound);
        record.status = score.status;
        record.reason = score.reason;
        if (score.status == "exact") {
            if (!collision(graph, score.witness)) throw std::runtime_error("packed witness fails scalar all-mask check");
            if ((record.upper && score.merge_length > record.upper) || score.merge_length < previous_lower)
                throw std::runtime_error("packed score contradicts prior bound");
            record.exact = record.upper = score.merge_length;
            record.witness = score.witness;
        } else if (record.upper && record.lower == record.upper) {
            record.status = "exact"; record.exact = record.upper;
            record.reason = "verified-upper-plus-complete-lower";
        } else if (record.upper && record.lower > record.upper) throw std::runtime_error("packed lower exceeds verified upper");
        return record;
    }
};

std::string config(const Options& options)
{
    std::ostringstream output;
    output << "{\"schema\":1,\"method\":\"family1-exhaustive-witness-cover-" << options.backend << "-v1\",\"m\":" << options.states
        << ",\"target\":" << options.target << ",\"depth\":" << options.limits.depth
        << ",\"max_layer_states\":" << options.limits.max_layer_states
        << ",\"max_working_bytes\":" << options.limits.max_working_bytes
        << ",\"timeout_ms\":" << options.limits.timeout_ms << ",\"batch_size\":" << options.batch_size;
    if (options.backend == "layer") output << ",\"layer_step\":" << options.layer_step
        << ",\"layer_storage\":" << quote(options.layer_storage)
        << ",\"layer_hash\":\"quotient-halfhash-v2\"";
    if (!options.input.empty()) output << ",\"input\":" << quote(options.input.generic_string());
    if (!options.layer_reports.empty()) {
        output << ",\"layer_reports\":[";
        for (std::size_t i = 0; i < options.layer_reports.size(); ++i) {
            if (i) output << ',';
            output << quote(options.layer_reports[i].generic_string());
        }
        output << ']';
    }
    output << '}';
    return output.str();
}
void save_library(const fs::path& path, const Library& library)
{
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot write witness library");
    for (const auto& [pair, frequency] : library.frequencies)
        output << "{\"witness\":" << pair_json(pair) << ",\"frequency\":" << frequency << "}\n";
    if (!output) throw std::runtime_error("witness library write failed");
}
Library initial_library(const Options& options)
{
    Library library;
    if (options.resume) {
        std::ifstream input(options.out / "initial-witnesses.jsonl", std::ios::binary);
        if (!input) throw std::runtime_error("missing initial witness library");
        for (std::string line; std::getline(input, line);) {
            const auto pair = pair_from(field(line, "witness"));
            const auto frequency = number(field(line, "frequency"));
            if (!frequency || pair != normalize(pair) || !library.frequencies.emplace(pair, frequency).second)
                throw std::runtime_error("invalid initial witness library");
        }
    } else {
        for (const auto& path : options.seeds) {
            std::ifstream input(path, std::ios::binary);
            if (!input) throw std::runtime_error("cannot open seed witness file: " + path.string());
            for (std::string line; std::getline(input, line);) {
                if (line.empty()) continue;
                const auto value = field(line, "witness");
                if (value == "null") continue;
                const auto pair = pair_from(value);
                if (pair[0].size() <= options.target) {
                    const auto frequency = line.find("\"frequency\":") == std::string::npos
                        ? 1ULL : number(field(line, "frequency"));
                    auto& total = library.frequencies[normalize(pair)];
                    if (!frequency || frequency > std::numeric_limits<std::uint64_t>::max() - total)
                        throw std::runtime_error("invalid or overflowing seed frequency");
                    total += frequency;
                }
            }
        }
        library.rebuild();
        if (options.witness_limit && library.ordered.size() > options.witness_limit) {
            library.ordered.resize(options.witness_limit);
            library.frequencies.clear();
            for (const auto& entry : library.ordered) library.frequencies.emplace(entry.words, entry.frequency);
        }
        save_library(options.out / "initial-witnesses.jsonl", library);
    }
    library.rebuild();
    return library;
}

struct Summary {
    std::uint64_t evaluated = 0, bounded = 0, exact = 0, unresolved = 0, unresolved_at_target = 0;
    unsigned int best_exact = 0, best_lower = 0, largest_upper = 0;
    bool unknown_upper = false, complete = false, value_certified = false, ties_complete = false;
    std::uint64_t best_exact_count = 0;
};
void exports(const Options& options, const std::vector<Record>& records, bool complete,
    const Library& library, const Reports& reports, double seconds)
{
    Summary summary;
    summary.evaluated = records.size(); summary.complete = complete;
    for (const auto& record : records) {
        summary.best_lower = std::max(summary.best_lower, record.lower);
        summary.best_exact = std::max(summary.best_exact, record.exact);
        if (record.exact) ++summary.exact;
        else if (record.status == "bounded") ++summary.bounded;
        if (!record.exact && (!record.upper || record.upper >= options.target)) ++summary.unresolved_at_target;
    }
    bool all_upper = summary.best_exact != 0, all_ties = summary.best_exact != 0;
    auto write = [&](const std::string& filename) {
        std::ofstream output(options.out / filename, std::ios::binary | std::ios::trunc);
        if (!output) throw std::runtime_error("cannot create export " + filename);
        return output;
    };
    auto graphs = write("graphs.jsonl"), best = write("best-exact.jsonl"), unresolved = write("unresolved.jsonl");
    for (const auto& record : records) {
        const auto line = json(record);
        graphs << line << '\n';
        if (record.exact && record.exact == summary.best_exact) { best << line << '\n'; ++summary.best_exact_count; }
        if (!record.upper || record.upper > summary.best_exact) all_upper = false;
        if (!record.exact && (!record.upper || record.upper >= summary.best_exact)) all_ties = false;
        if (!record.exact && (!record.upper || record.upper >= summary.best_exact)) {
            unresolved << line << '\n'; ++summary.unresolved;
            if (!record.upper) summary.unknown_upper = true;
            summary.largest_upper = std::max(summary.largest_upper, record.upper);
        }
    }
    summary.value_certified = complete && all_upper;
    summary.ties_complete = summary.value_certified && all_ties;
    if (!graphs || !best || !unresolved) throw std::runtime_error("graph export write failed");
    auto maxima = write("maximizers.jsonl");
    if (summary.ties_complete)
        for (const auto& record : records)
            if (record.exact == summary.best_exact) maxima << json(record) << '\n';
    auto output = write("summary.json");
    output << "{\"m\":" << options.states << ",\"evaluated\":" << summary.evaluated
        << ",\"enumeration_complete\":" << (complete ? "true" : "false")
        << ",\"exact\":" << summary.exact << ",\"upper_bounded\":" << summary.bounded
        << ",\"unresolved_competitors\":" << summary.unresolved
        << ",\"target\":" << options.target << ",\"unresolved_at_target\":" << summary.unresolved_at_target
        << ",\"best_attained_exact_score\":" << (summary.best_exact ? std::to_string(summary.best_exact) : "null")
        << ",\"best_proven_lower_bound\":" << summary.best_lower
        << ",\"largest_unresolved_upper\":" << (summary.unknown_upper ? "null" : std::to_string(summary.largest_upper))
        << ",\"maximum_value_certified\":" << (summary.value_certified ? "true" : "false")
        << ",\"maximum_merge_length\":" << (summary.value_certified ? std::to_string(summary.best_exact) : "null")
        << ",\"maximizing_collection_complete\":" << (summary.ties_complete ? "true" : "false")
        << ",\"maximizer_count\":" << (summary.ties_complete ? summary.best_exact_count : 0)
        << ",\"best_exact_count\":" << summary.best_exact_count
        << ",\"witness_library_size\":" << library.frequencies.size()
        << ",\"external_lower_reports_imported\":" << reports.lower_reports
        << ",\"external_upper_reports_imported\":" << reports.upper_reports
        << ",\"lower_proof_note\":\"External completed-run reports are retained as provenance, not self-verifying proof traces; independently replay lower proofs before relying on imported exact minima.\""
        << ",\"seconds\":" << seconds << "}\n";
    save_library(options.out / "learned-witnesses.jsonl", library);
}

Options options_from(int argc, char** argv)
{
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string name = argv[index];
        if (name == "--help") {
            std::cout << "Family1Exhaustive --out DIR [--states 7 --target 29 --seed JSONL ...]\n"
                " [--depth 16 --max-layer-states 65536 --max-working-mib 32 --timeout-ms 10000]\n"
                " [--jobs 8 --batch-size 4096 --witness-limit 0 --limit-graphs N --resume]\n"
                " [--input PRIOR_ORDERED_JOURNAL --layer-report COMPLETED_LAYER_REPORT ...]\n";
            std::cout << " [--backend packed|layer --layer-step 2 --layer-storage packed|indexed|compact] (layer requires seven states)\n";
            std::exit(0);
        }
        if (name == "--resume") { options.resume = true; continue; }
        if (++index == argc) throw std::runtime_error("missing option value");
        const std::string value = argv[index];
        if (name == "--out") options.out = value;
        else if (name == "--input") options.input = value;
        else if (name == "--layer-report") options.layer_reports.emplace_back(value);
        else if (name == "--backend") options.backend = value;
        else if (name == "--layer-step") options.layer_step = uint_number(value);
        else if (name == "--layer-storage") options.layer_storage = value;
        else if (name == "--seed") options.seeds.emplace_back(value);
        else if (name == "--states") options.states = uint_number(value);
        else if (name == "--target") options.target = uint_number(value);
        else if (name == "--depth") options.limits.depth = uint_number(value);
        else if (name == "--max-layer-states") options.limits.max_layer_states = number(value);
        else if (name == "--max-working-mib") {
            const auto mib = number(value);
            if (mib > (std::numeric_limits<std::uint64_t>::max() >> 20)) throw std::runtime_error("memory budget overflows bytes");
            options.limits.max_working_bytes = mib << 20;
        }
        else if (name == "--timeout-ms") options.limits.timeout_ms = number(value);
        else if (name == "--jobs") options.jobs = uint_number(value);
        else if (name == "--batch-size") options.batch_size = uint_number(value);
        else if (name == "--witness-limit") options.witness_limit = uint_number(value);
        else if (name == "--limit-graphs") options.limit_graphs = number(value);
        else throw std::runtime_error("unknown option: " + name);
    }
    if (options.out.empty() || !options.states || options.states > 20 || !options.target || options.target > 64
        || !options.jobs || options.jobs > 32 || !options.batch_size || options.batch_size > 65536
        || (options.backend != "packed" && options.backend != "layer") || !options.layer_step || options.layer_step > 33
        || (options.layer_storage != "packed" && options.layer_storage != "indexed" && options.layer_storage != "compact")
        || (options.backend == "layer" && options.states != 7)
        || options.limits.depth > (options.backend == "layer" ? 33U : 31U)
        || !options.limits.max_layer_states || options.limits.max_layer_states > (1ULL << (options.backend == "layer" ? 33 : 31))
        || !options.limits.max_working_bytes)
        throw std::runtime_error("invalid exhaustive search options");
    return options;
}
}

int main(int argc, char** argv)
{
    try {
        const auto options = options_from(argc, argv);
        std::signal(SIGINT, stop);
        std::signal(SIGTERM, stop);
        const auto started = std::chrono::steady_clock::now();
        fs::create_directories(options.out);
        const auto journal_path = options.out / "checkpoint.jsonl";
        if (!options.resume && !fs::is_empty(options.out))
            throw std::runtime_error("new run requires an empty output directory; use --resume or a new directory");
        if (!options.input.empty() && fs::weakly_canonical(options.input) == fs::weakly_canonical(journal_path))
            throw std::runtime_error("refinement input must differ from the output checkpoint");
        if (options.resume) {
            std::ifstream input(options.out / "run.json", std::ios::binary);
            std::string line; std::getline(input, line);
            if (!input || line != config(options)) throw std::runtime_error("resume configuration does not match");
        } else {
            std::ofstream output(options.out / "run.json", std::ios::binary);
            output << config(options) << '\n';
            if (!output) throw std::runtime_error("cannot write run metadata");
        }
        auto library = initial_library(options);
        const auto reports = read_reports(options);
        for (const auto& [key, bound] : reports.graphs)
            if (bound.upper && bound.upper <= options.target)
                ++library.frequencies[normalize(bound.witness)];
        library.rebuild();
        std::vector<Record> prior;
        if (!options.input.empty()) {
            std::ifstream input(options.input, std::ios::binary);
            if (!input) throw std::runtime_error("cannot open refinement input");
            for (std::string line; std::getline(input, line);) {
                if (input.eof()) throw std::runtime_error("refinement input has an uncommitted final fragment");
                auto record = parse(line);
                if (record.m != options.states || record.ordinal != prior.size())
                    throw std::runtime_error("refinement input is not an ordered prefix");
                prior.push_back(std::move(record));
            }
            if (input.bad()) throw std::runtime_error("refinement input read failed");
            std::cout << "Loaded " << prior.size() << " prior certificates\n";
        }
        std::vector<Record> records;
        if (options.resume) {
            std::ifstream input(journal_path, std::ios::binary);
            if (!input) throw std::runtime_error("missing resume checkpoint");
            std::uintmax_t committed = 0;
            for (std::string line; std::getline(input, line);) {
                if (input.eof()) break;
                auto record = parse(line);
                if (record.m != options.states || record.ordinal != records.size()) throw std::runtime_error("checkpoint is not an ordered prefix");
                records.push_back(std::move(record));
                committed += line.size() + 1;
            }
            if (input.bad()) throw std::runtime_error("checkpoint read failed");
            input.close();
            if (fs::file_size(journal_path) != committed) fs::resize_file(journal_path, committed);
            // Recreate precisely the library snapshots of complete batches.
            const auto complete_prefix = records.size() / options.batch_size * options.batch_size;
            for (std::size_t begin = 0; begin < complete_prefix; begin += options.batch_size) {
                for (auto index = begin; index < begin + options.batch_size; ++index) library.learn(records[index], options.target);
                library.rebuild();
            }
        }
        std::ofstream journal(journal_path, std::ios::binary | std::ios::app);
        if (!journal) throw std::runtime_error("cannot append checkpoint");
        std::vector<Worker> workers(options.jobs);
        std::vector<Graph> batch;
        batch.reserve(options.batch_size);
        std::uint64_t ordinal = 0, new_graphs = 0;
        const auto existing = records.size();
        auto process = [&]() {
            if (batch.empty()) return;
            const auto begin = records.size();
            std::vector<Record> results(batch.size());
            std::vector<std::future<void>> tasks;
            for (unsigned int worker = 0; worker < options.jobs; ++worker)
                tasks.push_back(std::async(std::launch::async, [&, worker] {
                    for (std::size_t index = worker; index < batch.size(); index += options.jobs)
                        results[index] = workers[worker].evaluate(batch[index], begin + index, library, options,
                            begin + index < prior.size() ? &prior[begin + index] : nullptr, reports);
                }));
            for (auto& task : tasks) task.get();
            for (auto& record : results) {
                journal << json(record) << '\n';
                records.push_back(std::move(record));
                ++new_graphs;
            }
            journal.flush();
            if (!journal) throw std::runtime_error("checkpoint write failed");
            // Learn only at fixed ordinal boundaries, including a resumed
            // partial batch. This preserves results across interruption.
            if (records.size() % options.batch_size == 0) {
                const auto boundary = records.size() - options.batch_size;
                for (auto index = boundary; index < records.size(); ++index) library.learn(records[index], options.target);
                library.rebuild();
            }
            std::cout << "Committed " << records.size() << " classes; witnesses " << library.frequencies.size()
                << "; elapsed " << std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count() << " s\n";
            std::cout.flush();
            batch.clear();
        };
        const bool exhausted = family1::LargeEnumerator(options.states).enumerate([&](const auto& graph) {
            const auto current = ordinal++;
            if (current < existing) {
                if (records[current].key != graph.key()) throw std::runtime_error("checkpoint differs from deterministic enumeration");
                return true;
            }
            if (interrupted || (options.limit_graphs && new_graphs + batch.size() >= options.limit_graphs)) return false;
            batch.push_back(graph);
            const auto boundary = options.batch_size - (records.size() % options.batch_size);
            if (batch.size() == boundary) process();
            return !interrupted;
        });
        process();
        if (exhausted && (ordinal < existing || ordinal < prior.size()))
            throw std::runtime_error("checkpoint/refinement has records beyond complete enumeration");
        const bool complete = exhausted && !interrupted;
        exports(options, records, complete, library, reports,
            std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count());
        std::cout << "Enumeration complete: " << (complete ? "true" : "false") << "; records " << records.size() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Family1Exhaustive: " << error.what() << '\n';
        return 1;
    }
}

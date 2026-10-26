#include "Family1LargeGraph.h"
#include "Family1CliArtifacts.h"
#include "Family1PairAgreement.h"
#include "Family1FullGuidance.h"
#include "HardPairFinder.h"
#include "HardPairPrefixSeeds.h"
#include "HardPairViability.h"
#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace fs = std::filesystem;
namespace cli = family1_cli;
namespace {
using Graph = family1::LargeGraph;
using Clock = std::chrono::steady_clock;
volatile std::sig_atomic_t interrupted = 0;
void stop(int) { interrupted = 1; }

std::uint64_t number(const std::string& value)
{
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("expected a nonnegative integer");
    return std::stoull(value);
}
unsigned int small_number(const std::string& value)
{
    auto result = number(value);
    if (result > std::numeric_limits<unsigned int>::max()) throw std::invalid_argument("integer is too large");
    return static_cast<unsigned int>(result);
}
std::uint64_t mix(std::uint64_t value)
{
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}
struct Random {
    std::uint64_t state;
    std::uint64_t next() { state += 0x9e3779b97f4a7c15ULL; return mix(state); }
    unsigned int choice(unsigned int bound) { return static_cast<unsigned int>(next() % bound); }
    std::string word(unsigned int length) {
        std::string result(length, '0');
        std::uint64_t bits = 0;
        for (unsigned int i = 0; i < length; ++i) {
            if (!(i % 64)) bits = next();
            result[i] += bits & 1; bits >>= 1;
        }
        return result;
    }
};
struct Options {
    fs::path out;
    std::string source_key, mode = "commutator", beam_ranking = "drop";
    std::string first_prefix, second_prefix;
    unsigned int length = 0, masks = 64, hash_bits = 64, self_check = 16;
    unsigned int beam_width = 8, lookahead = 3;
    unsigned int window_k = 2;
    unsigned int prefix_depth = 16;
    unsigned int prefix_common_depth = 0;
    std::uint64_t tail_threshold = 2, tail_max_states = 50000, max_expansions = 10000;
    std::uint64_t prefix_max_words = 65536, prefix_max_pairs = 128;
    std::uint64_t prefix_samples_per_depth = 16384;
    unsigned int viability_coordinates = 8;
    unsigned int distance_coordinates = 0;
    std::uint64_t samples = 10000, seed = 1088, max_profiles = 65536, checkpoint_every = 4096, limit_samples = 0;
    bool resume = false, full_agreement = false, full_guidance = false, best_of_seeds = false;
};
Options options(int argc, char** argv)
{
    Options result;
    bool beam_explicit = false, lookahead_explicit = false;
    for (int i = 1; i < argc; ++i) {
        std::string argument = argv[i];
        if (argument == "--help") {
            std::cout << "Family1Sample --graph KEY --out DIR --length L [--samples 10000 --seed 1088]\n"
                " [--masks 64 --mode commutator|random|mixed|benchmark|guided|finder|distribution --resume]\n"
                " [--max-profiles 65536 --hash-bits 64 --self-check 16]\n"
                " [--checkpoint-every 4096 --limit-samples N]\n"
                " [--beam-width 8 --lookahead 3 --first-prefix U --second-prefix V --full-agreement]\n"
                " [--full-guidance] uses ALL masks inside the beam (default beam4/lookahead1).\n"
                " [--window-k 2 --max-expansions 10000 --tail-threshold 2 --tail-max-states 50000 --best-of-seeds]\n"
                "Finder/distribution support window-k1..16; max-expansions is per prefix seed.\n"
                " [--prefix-depth 16 --prefix-max-words 65536 --prefix-max-pairs 128]\n"
                " [--prefix-common-depth 0] optionally stratifies learned pairs by common prefix (0..8).\n"
                " [--prefix-samples-per-depth 16384] additionally samples lengths20/24/28/32.\n"
                " [--viability-coordinates 8] checks a fixed prefix of unmerged coordinates.\n"
                " [--distance-coordinates 0 --beam-ranking drop|remaining] finder-only admissible pruning/ranking.\n"
                "Finder uses a reusable full-family window/beam/exact-tail module.\n"
                "Distribution requires two explicit prefixes and enumerates ALL 2^k windows.\n"
                "Samples static-mask endpoint profiles for one rooted graph. Hash matches\n"
                "are checked against complete sampled states; every accepted word pair\n"
                "is independently replayed over all 2^m masks. A miss proves no lower bound.\n"
                "Commutator candidates have p A B z / p B A z, with noncommuting blocks.\n"
                "Benchmark compares exact packed and scalar profiles on the same fixed words.\n"
                "Guided maximizes sampled common-suffix agreement, checks every permutation\n"
                "coloring, and may verify a witness SHORTER than the requested length limit.\n"
                "Completed results and partial checkpoints require identical settings on resume.\n";
            std::exit(0);
        }
        if (argument == "--resume") { result.resume = true; continue; }
        if (argument == "--full-agreement") { result.full_agreement = true; continue; }
        if (argument == "--full-guidance") { result.full_guidance = true; continue; }
        if (argument == "--best-of-seeds") { result.best_of_seeds = true; continue; }
        if (++i >= argc) throw std::invalid_argument("missing option value: " + argument);
        const std::string value = argv[i];
        if (argument == "--graph") result.source_key = value;
        else if (argument == "--out") result.out = value;
        else if (argument == "--length") result.length = small_number(value);
        else if (argument == "--samples") result.samples = number(value);
        else if (argument == "--seed") result.seed = number(value);
        else if (argument == "--masks") result.masks = small_number(value);
        else if (argument == "--mode") result.mode = value;
        else if (argument == "--max-profiles") result.max_profiles = number(value);
        else if (argument == "--hash-bits") result.hash_bits = small_number(value);
        else if (argument == "--self-check") result.self_check = small_number(value);
        else if (argument == "--checkpoint-every") result.checkpoint_every = number(value);
        else if (argument == "--limit-samples") result.limit_samples = number(value);
        else if (argument == "--beam-width") { result.beam_width = small_number(value); beam_explicit = true; }
        else if (argument == "--lookahead") { result.lookahead = small_number(value); lookahead_explicit = true; }
        else if (argument == "--first-prefix") result.first_prefix = value;
        else if (argument == "--second-prefix") result.second_prefix = value;
        else if (argument == "--window-k") result.window_k = small_number(value);
        else if (argument == "--max-expansions") result.max_expansions = number(value);
        else if (argument == "--tail-threshold") result.tail_threshold = number(value);
        else if (argument == "--tail-max-states") result.tail_max_states = number(value);
        else if (argument == "--prefix-depth") result.prefix_depth = small_number(value);
        else if (argument == "--prefix-common-depth") result.prefix_common_depth = small_number(value);
        else if (argument == "--prefix-max-words") result.prefix_max_words = number(value);
        else if (argument == "--prefix-max-pairs") result.prefix_max_pairs = number(value);
        else if (argument == "--prefix-samples-per-depth") result.prefix_samples_per_depth = number(value);
        else if (argument == "--viability-coordinates" || argument == "--viability-checks") result.viability_coordinates = small_number(value);
        else if (argument == "--distance-coordinates") result.distance_coordinates = small_number(value);
        else if (argument == "--beam-ranking") result.beam_ranking = value;
        else throw std::invalid_argument("unknown option: " + argument);
    }
    if (result.mode == "finder" || result.mode == "distribution") result.full_guidance = true;
    if (result.mode == "distribution") {
        if (result.first_prefix.empty() || result.second_prefix.empty())
            throw std::invalid_argument("distribution requires --first-prefix and --second-prefix");
        const auto total = result.first_prefix.size() + result.window_k;
        if (total > 4096 || (result.length && result.length != total))
            throw std::invalid_argument("distribution length, if supplied, must equal prefix length plus window-k <=4096");
        result.length = static_cast<unsigned int>(total);
    }
    if (result.source_key.empty() || result.out.empty() || !result.length || result.length > 4096
        || !result.samples || result.samples > 1000000000ULL || !result.masks || result.masks > 64
        || result.hash_bits > 64 || !result.max_profiles || result.max_profiles > 1000000
        || !result.checkpoint_every || result.checkpoint_every > 1000000000ULL
        || (result.mode != "commutator" && result.mode != "random" && result.mode != "mixed" && result.mode != "benchmark"
            && result.mode != "guided" && result.mode != "finder" && result.mode != "distribution")
        || (result.mode == "benchmark" && (result.samples > 100000 || result.limit_samples)))
        throw std::invalid_argument("require graph/out, length1..4096, samples1..1e9, masks1..64, hash-bits0..64, positive bounded cache/checkpoint settings; benchmark <=100000 words and no limit-samples");
    if (result.full_guidance) {
        if (!beam_explicit) result.beam_width = 4;
        if (!lookahead_explicit) result.lookahead = 1;
        if (result.mode == "guided" && result.lookahead > 1) throw std::invalid_argument("full guidance supports lookahead0..1");
    }
    if (!result.beam_width || result.beam_width > 32 || result.lookahead > 4
        || (result.first_prefix.empty() != result.second_prefix.empty())
        || (!result.first_prefix.empty() && (result.first_prefix == result.second_prefix
            || result.first_prefix.size() != result.second_prefix.size() || result.first_prefix.size() > result.length
            || result.first_prefix.find_first_not_of("01") != std::string::npos
            || result.second_prefix.find_first_not_of("01") != std::string::npos)))
        throw std::invalid_argument("guided requires beam-width1..32, lookahead0..4, and optional distinct equal-length binary prefixes no longer than L");
    if (result.mode != "guided" && result.mode != "finder" && result.mode != "distribution"
        && (result.full_agreement || result.full_guidance || !result.first_prefix.empty()))
        throw std::invalid_argument("prefix/full-agreement options require guided mode");
    if (!result.window_k || result.window_k > 16 || result.tail_threshold > 1024 || !result.tail_max_states
        || result.tail_max_states > 10000000 || !result.max_expansions || result.max_expansions > 1000000000ULL)
        throw std::invalid_argument("require window-k1..16, max-expansions1..1e9, tail-threshold0..1024, tail-max-states1..1e7");
    if (result.max_expansions != 10000 && result.mode != "finder" && result.mode != "distribution")
        throw std::invalid_argument("custom max-expansions requires finder or distribution mode");
    if (!result.prefix_depth || result.prefix_depth > 32 || !result.prefix_max_words || result.prefix_max_words > 4194304
        || !result.prefix_max_pairs || result.prefix_max_pairs > 100000 || result.viability_coordinates > 1024
        || !result.prefix_samples_per_depth || result.prefix_samples_per_depth > 4194304)
        throw std::invalid_argument("require prefix-depth1..32, prefix-max-words/prefix-samples-per-depth1..4194304, prefix-max-pairs1..100000");
    if (result.distance_coordinates > 1024 || result.prefix_common_depth > 8
        || (result.beam_ranking != "drop" && result.beam_ranking != "remaining")
        || (result.mode != "finder" && (result.distance_coordinates || result.beam_ranking != "drop" || result.prefix_common_depth)))
        throw std::invalid_argument("finder requires distance-coordinates0..1024, prefix-common-depth0..8 and beam-ranking drop|remaining");
    return result;
}

std::string configuration(const Options& options, const Graph& graph)
{
    std::ostringstream output;
    output << "{\"schema\":1,\"method\":\"family1-graph-adapted-static-mask-sampler-v1\""
        << ",\"source_key\":" << cli::quote(options.source_key) << ",\"source_key_sha256\":" << cli::quote(cli::sha256(options.source_key))
        << ",\"key\":" << cli::quote(graph.key()) << ",\"m\":" << graph.size()
        << ",\"length\":" << options.length << ",\"samples\":" << options.samples << ",\"seed\":" << options.seed
        << ",\"masks\":" << options.masks << ",\"mode\":" << cli::quote(options.mode)
        << ",\"max_profiles\":" << options.max_profiles << ",\"hash_bits\":" << options.hash_bits
        << ",\"self_check\":" << options.self_check << ",\"checkpoint_every\":" << options.checkpoint_every;
    if (options.mode == "guided") output << ",\"beam_width\":" << options.beam_width << ",\"lookahead\":" << options.lookahead
        << ",\"first_prefix\":" << cli::quote(options.first_prefix) << ",\"second_prefix\":" << cli::quote(options.second_prefix)
        << ",\"full_agreement\":" << (options.full_agreement ? "true" : "false");
    if (options.full_guidance) output << ",\"full_guidance\":true,\"full_guidance_max_nodes\":" << options.max_expansions;
    // Keep legacy default configurations byte-identical for resumable runs.
    if (options.max_expansions != 10000) output << ",\"max_expansions\":" << options.max_expansions;
    if (options.distance_coordinates) output << ",\"distance_coordinates\":" << options.distance_coordinates;
    if (options.beam_ranking != "drop") output << ",\"beam_ranking\":" << cli::quote(options.beam_ranking);
    if (options.prefix_common_depth) output << ",\"prefix_common_depth\":" << options.prefix_common_depth;
    if (options.mode == "finder" || options.mode == "distribution")
        output << ",\"window_k\":" << options.window_k << ",\"tail_threshold\":" << options.tail_threshold
            << ",\"tail_max_states\":" << options.tail_max_states << ",\"best_of_seeds\":" << (options.best_of_seeds ? "true" : "false")
            << ",\"first_prefix\":" << cli::quote(options.first_prefix) << ",\"second_prefix\":" << cli::quote(options.second_prefix)
            << ",\"beam_width\":" << options.beam_width;
    if (options.mode == "finder")
        output << ",\"prefix_seed_method\":\"permutation-profile-depth-diverse-v2\",\"prefix_depth\":" << options.prefix_depth
            << ",\"prefix_max_words\":" << options.prefix_max_words << ",\"prefix_max_pairs\":" << options.prefix_max_pairs
            << ",\"prefix_sample_depths\":[20,24,28,32],\"prefix_samples_per_depth\":" << options.prefix_samples_per_depth
            << ",\"viability_coordinates\":" << options.viability_coordinates << ",\"viability_cache_max\":4096";
    output << '}';
    return output.str();
}

unsigned int endpoint(const Graph& graph, std::uint32_t mask, const std::string& word)
{
    unsigned int state = 0;
    for (char symbol : word) state = graph.ports[state][static_cast<unsigned int>(symbol - '0') ^ ((mask >> state) & 1U)];
    return state;
}

// Each state plane is a 64-bit membership bitset, one bit per STATIC mask.
// A transition splits those bits by sigma[s], then routes both subsets.
struct Profile {
    std::array<std::uint64_t, 20> planes{};
    bool operator==(const Profile&) const = default;
};
class Packed {
    Graph graph;
    std::vector<std::uint32_t> masks;
    std::array<std::uint64_t, 20> sigma{};
    std::uint64_t active;
    std::array<Profile, 511> prefixes{};
    std::array<bool, 511> known{};
public:
    Packed(const Graph& value, std::vector<std::uint32_t> sample_masks) : graph(value), masks(std::move(sample_masks)),
        active(masks.size() == 64 ? ~std::uint64_t{0} : (std::uint64_t{1} << masks.size()) - 1)
    {
        for (unsigned int s = 0; s < graph.size(); ++s)
            for (unsigned int k = 0; k < masks.size(); ++k)
                if (masks[k] & (1U << s)) sigma[s] |= std::uint64_t{1} << k;
        prefixes[0].planes[0] = active; known[0] = true;
    }
    Profile step(const Profile& before, unsigned int input) const
    {
        Profile after;
        for (unsigned int s = 0; s < graph.size(); ++s) {
            auto at = before.planes[s];
            if (graph.ports[s][0] == graph.ports[s][1]) after.planes[graph.ports[s][0]] |= at;
            else {
                const auto port_one = input ? ~sigma[s] : sigma[s];
                after.planes[graph.ports[s][0]] |= at & ~port_one;
                after.planes[graph.ports[s][1]] |= at & port_one;
            }
        }
        return after;
    }
    Profile run(const std::string& word)
    {
        unsigned int node = 0, offset = 0;
        for (; offset < std::min<std::size_t>(8, word.size()); ++offset) {
            auto next = 2 * node + 1 + static_cast<unsigned int>(word[offset] - '0');
            if (!known[next]) { prefixes[next] = step(prefixes[node], word[offset] - '0'); known[next] = true; }
            node = next;
        }
        auto result = prefixes[node];
        for (; offset < word.size(); ++offset) result = step(result, word[offset] - '0');
        return result;
    }
    Profile suffix(Profile state, const std::string& word) const
    {
        for (char input : word) state = step(state, input - '0');
        return state;
    }
    void check(const Profile& profile, const std::string& word) const
    {
        Profile scalar;
        for (unsigned int k = 0; k < masks.size(); ++k)
            scalar.planes[endpoint(graph, masks[k], word)] |= std::uint64_t{1} << k;
        if (scalar != profile) throw std::logic_error("packed static-mask profile disagrees with scalar simulation");
    }
};
std::uint64_t profile_hash(const Profile& profile, unsigned int bits)
{
    std::uint64_t value = 0x46414d3148415348ULL;
    for (auto plane : profile.planes) value = mix(value ^ mix(plane));
    return bits == 64 ? value : value & ((std::uint64_t{1} << bits) - 1);
}
std::vector<std::uint32_t> initial_masks(const Graph& graph, const Options& options)
{
    const unsigned int total = 1U << graph.size(), count = std::min(options.masks, total);
    std::vector<std::uint32_t> result{0};
    if (count > 1) result.push_back(total - 1);
    if (count == total) {
        result.clear(); for (unsigned int mask = 0; mask < total; ++mask) result.push_back(mask);
        return result;
    }
    for (unsigned int s = 0; s < graph.size() && result.size() < count; ++s)
        if (std::find(result.begin(), result.end(), 1U << s) == result.end()) result.push_back(1U << s);
    Random random{mix(options.seed ^ 0x4d41534bULL)};
    while (result.size() < count) {
        auto mask = static_cast<std::uint32_t>(random.next() % total);
        if (std::find(result.begin(), result.end(), mask) == result.end()) result.push_back(mask);
    }
    return result;
}
std::string random_word(std::uint64_t index, const Options& options)
{
    // Exhaustive tiny startup makes small-case regression deterministic.
    const auto startup = options.length < 8 ? std::uint64_t{1} << options.length : 256;
    if (index < startup) {
        std::string result(options.length, '0');
        for (unsigned int offset = 0; offset < std::min(8U, options.length); ++offset)
            result[options.length - offset - 1] += (index >> offset) & 1;
        return result;
    }
    Random random{mix(options.seed ^ mix(index) ^ 0x574f5244ULL)};
    return random.word(options.length);
}
struct Candidate {
    std::string prefix, a, b, suffix, first, second;
};
Candidate commutator(std::uint64_t index, const Options& options)
{
    Candidate result;
    if (options.length == 1) { result.first = "0"; result.second = "1"; return result; }
    Random random{mix(options.seed ^ mix(index) ^ 0x5041425aULL)};
    unsigned int a = 1, b = 1, p = 0;
    if (index != 0) {
        const auto style = static_cast<unsigned int>(index % 4);
        if (style == 0) {
            a = 1 + random.choice(options.length - 1);
            b = 1 + random.choice(options.length - a);
        } else if (style == 1) {
            a = 1 + random.choice(std::min(4U, options.length - 1));
            b = 1 + random.choice(std::min(4U, options.length - a));
        }
        p = random.choice(options.length - a - b + 1);
        result.prefix = random.word(p);
        result.suffix = random.word(options.length - a - b - p);
        if (style == 1) {
            result.a = random.word(a); result.b = random.word(b);
            if (result.a + result.b == result.b + result.a) { result.a.assign(a, '0'); result.b.assign(b, '1'); }
        }
    } else result.suffix.assign(options.length - 2, '0');
    if (result.a.empty()) { result.a.assign(a, '0'); result.b.assign(b, '1'); }
    result.first = result.prefix + result.a + result.b + result.suffix;
    result.second = result.prefix + result.b + result.a + result.suffix;
    if (result.first == result.second || result.first.size() != options.length || result.second.size() != options.length)
        throw std::logic_error("invalid equal-length commutator candidate");
    return result;
}

struct Counters {
    std::uint64_t hash_matches = 0, projected_equalities = 0, scalar_candidate_checks = 0;
    std::uint64_t scalar_masks_checked = 0, counterexamples = 0, cache_resets = 0, self_checks = 0;
};
struct Entry { std::uint64_t index; Profile profile; };
struct GuidedAttempt {
    bool present = false, gate_blocked = false, scalar_verified = false, full_scope = false, proven_obstruction = false;
    std::uint64_t full_mask_count = 0;
    std::string first, second, suffix;
    std::vector<std::uint32_t> masks;
    std::vector<unsigned int> trace;
    std::uint64_t permutation_mismatches = 0;
    std::int64_t first_separator = -1;
};
struct GuidedCounts {
    std::uint64_t prefix_gates_checked = 0, prefix_gates_blocked = 0, beam_nodes = 0, lookahead_nodes = 0;
    std::uint64_t expansion_limits = 0;
};
struct State {
    std::uint64_t next = 0;
    std::vector<std::uint32_t> masks;
    Counters counts;
    std::vector<std::uint64_t> cache_indices;
    bool guided = false, full_guidance = false;
    GuidedAttempt best;
    GuidedCounts guided_counts;
    std::uint64_t finder_window_blocks = 0, finder_tail_calls = 0, finder_tail_states = 0;
    std::string finder_last_tail_json = "null";
    std::string finder_best_tail_json = "null";
    std::string finder_prefix_stats_json = "null";
    std::string finder_viability_json = "null";
    std::uint64_t finder_obstruction_pruned = 0;
    std::uint64_t finder_distance_checks = 0, finder_distance_pruned = 0;
};
std::string checkpoint_text(const State& state, const std::string& configuration_hash)
{
    std::ostringstream out;
    const auto& c = state.counts;
    out << "FAMILY1SAMPLE1\n" << configuration_hash << '\n' << state.next << '\n'
        << c.hash_matches << ' ' << c.projected_equalities << ' ' << c.scalar_candidate_checks << ' '
        << c.scalar_masks_checked << ' ' << c.counterexamples << ' ' << c.cache_resets << ' ' << c.self_checks << '\n';
    out << state.masks.size(); for (auto mask : state.masks) out << ' ' << mask;
    out << '\n' << state.cache_indices.size(); for (auto index : state.cache_indices) out << ' ' << index;
    out << '\n';
    if (state.guided) {
        const auto& a = state.best; const auto& g = state.guided_counts;
        out << "GUIDED1 " << g.prefix_gates_checked << ' ' << g.prefix_gates_blocked << ' ' << g.beam_nodes << ' ' << g.lookahead_nodes << '\n';
        out << a.present << ' ' << a.gate_blocked << ' ' << a.scalar_verified << ' ' << a.permutation_mismatches << ' ' << a.first_separator << '\n'
            << std::quoted(a.first) << ' ' << std::quoted(a.second) << ' ' << std::quoted(a.suffix) << '\n';
        out << a.masks.size(); for (auto mask : a.masks) out << ' ' << mask;
        out << '\n' << a.trace.size(); for (auto score : a.trace) out << ' ' << score;
        out << '\n';
        if (state.full_guidance) out << "FULL1 " << a.full_scope << ' ' << a.full_mask_count << ' ' << g.expansion_limits << '\n';
        if (state.finder_window_blocks || state.finder_tail_calls || state.finder_tail_states || state.finder_prefix_stats_json != "null")
            out << "FINDER1 " << state.finder_window_blocks << ' ' << state.finder_tail_calls << ' ' << state.finder_tail_states
                << ' ' << state.finder_obstruction_pruned
                << '\n' << std::quoted(state.finder_last_tail_json) << '\n' << std::quoted(state.finder_best_tail_json)
                << '\n' << std::quoted(state.finder_prefix_stats_json) << '\n' << std::quoted(state.finder_viability_json)
                << '\n' << a.proven_obstruction << '\n';
        if (state.finder_distance_checks || state.finder_distance_pruned)
            out << "DISTANCE1 " << state.finder_distance_checks << ' ' << state.finder_distance_pruned << '\n';
    }
    return out.str();
}
void save_checkpoint(const Options& options, const State& state, const std::string& configuration_hash)
{
    const auto directory = options.out / "checkpoints"; fs::create_directories(directory);
    auto path = directory / ("sample-" + std::to_string(state.next) + ".txt");
    const auto value = checkpoint_text(state, configuration_hash);
    if (fs::exists(path)) {
        if (cli::read(path) != value || !fs::exists(path.string() + ".sha256")
            || cli::read(path.string() + ".sha256") != cli::sha256(value))
            throw std::runtime_error("existing checkpoint differs from deterministic state");
        return;
    }
    // The data file is the commit marker. An orphan checksum is safe to replace;
    // readers ignore it until the complete data file is atomically published.
    cli::write(path.string() + ".sha256", cli::sha256(value)); cli::publish(path, value);
}
State load_checkpoint(const Options& options, const Graph& graph, const std::string& configuration_hash)
{
    State result; result.masks = initial_masks(graph, options);
    const auto directory = options.out / "checkpoints";
    if (!fs::exists(directory)) return result;
    fs::path newest; std::uint64_t newest_index = 0;
    for (const auto& entry : fs::directory_iterator(directory)) {
        const auto name = entry.path().filename().string();
        if (name.rfind("sample-", 0) != 0 || entry.path().extension() != ".txt") continue;
        const auto index = number(name.substr(7, name.size() - 11));
        if (newest.empty() || index > newest_index) { newest = entry.path(); newest_index = index; }
    }
    if (newest.empty()) return result;
    auto value = cli::read(newest);
    if (!fs::exists(newest.string() + ".sha256") || cli::read(newest.string() + ".sha256") != cli::sha256(value))
        throw std::runtime_error("checkpoint SHA256 mismatch");
    std::istringstream input(value); std::string magic, binding;
    input >> magic >> binding >> result.next;
    auto& c = result.counts;
    input >> c.hash_matches >> c.projected_equalities >> c.scalar_candidate_checks >> c.scalar_masks_checked
        >> c.counterexamples >> c.cache_resets >> c.self_checks;
    std::size_t count = 0; input >> count;
    if (magic != "FAMILY1SAMPLE1" || binding != configuration_hash || result.next != newest_index || result.next > options.samples
        || !count || count > std::min(options.masks, 1U << graph.size())) throw std::runtime_error("invalid checkpoint metadata");
    result.masks.resize(count); for (auto& mask : result.masks) input >> mask;
    input >> count;
    if (count > options.max_profiles) throw std::runtime_error("invalid checkpoint cache size");
    result.cache_indices.resize(count); for (auto& index : result.cache_indices) input >> index;
    if (!input || std::any_of(result.masks.begin(), result.masks.end(), [&](auto mask) { return mask >= (1U << graph.size()); })
        || std::set<std::uint32_t>(result.masks.begin(), result.masks.end()).size() != result.masks.size()
        || std::any_of(result.cache_indices.begin(), result.cache_indices.end(), [&](auto index) { return index >= result.next; }))
        throw std::runtime_error("invalid checkpoint state");
    if (options.mode == "guided" || options.mode == "finder") {
        result.guided = true; auto& a = result.best; auto& g = result.guided_counts;
        input >> magic >> g.prefix_gates_checked >> g.prefix_gates_blocked >> g.beam_nodes >> g.lookahead_nodes;
        input >> a.present >> a.gate_blocked >> a.scalar_verified >> a.permutation_mismatches >> a.first_separator
            >> std::quoted(a.first) >> std::quoted(a.second) >> std::quoted(a.suffix);
        input >> count; if (count > 64) throw std::runtime_error("invalid guided checkpoint mask count");
        a.masks.resize(count); for (auto& mask : a.masks) input >> mask;
        input >> count; if (count > options.length + 1) throw std::runtime_error("invalid guided checkpoint trace");
        a.trace.resize(count); for (auto& score : a.trace) input >> score;
        if (options.full_guidance) {
            result.full_guidance = true;
            input >> binding >> a.full_scope >> a.full_mask_count >> g.expansion_limits;
            if (binding != "FULL1" || (a.present && (!a.full_scope || a.full_mask_count != (1U << graph.size()))))
                throw std::runtime_error("invalid full-guidance checkpoint metadata");
        }
        if (!input || magic != "GUIDED1" || (a.present && ((!a.full_scope && a.masks.empty()) || a.trace.size() != a.suffix.size() + 1
            || a.first.empty() || a.first == a.second || a.first.size() != a.second.size()
            || a.first.size() + a.suffix.size() > options.length
            || !std::is_sorted(a.trace.begin(), a.trace.end()) || a.trace.back() > (a.full_scope ? a.full_mask_count : a.masks.size()))))
            throw std::runtime_error("invalid guided checkpoint state");
        if (options.mode == "finder") {
            input >> std::ws;
            if (!input.eof()) {
                input >> binding >> result.finder_window_blocks >> result.finder_tail_calls >> result.finder_tail_states
                    >> result.finder_obstruction_pruned;
                input >> std::quoted(result.finder_last_tail_json);
                input >> std::quoted(result.finder_best_tail_json);
                input >> std::quoted(result.finder_prefix_stats_json);
                input >> std::quoted(result.finder_viability_json) >> a.proven_obstruction;
                if (!input || binding != "FINDER1") throw std::runtime_error("invalid finder checkpoint counters");
                input >> std::ws;
                if (!input.eof()) {
                    input >> binding >> result.finder_distance_checks >> result.finder_distance_pruned;
                    if (!input || binding != "DISTANCE1") throw std::runtime_error("invalid finder distance counters");
                }
            }
        }
    }
    input >> std::ws; if (!input.eof()) throw std::runtime_error("trailing checkpoint content");
    return result;
}

// No packed tables or hashes are used by this independent all-mask replay.
// -1 is a universal collision, -2 interruption, otherwise a separating mask.
std::int64_t full_check(const Graph& graph, const std::string& first, const std::string& second, Counters& counts)
{
    ++counts.scalar_candidate_checks;
    for (std::uint32_t mask = 0; mask < (1U << graph.size()); ++mask) {
        if (!(mask & 4095U) && interrupted) return -2;
        ++counts.scalar_masks_checked;
        if (endpoint(graph, mask, first) != endpoint(graph, mask, second)) return mask;
    }
    return -1;
}

std::vector<std::uint32_t> permutation_masks(const Graph& graph)
{
    using Occurrence = std::pair<unsigned int, unsigned int>;
    std::vector<std::vector<Occurrence>> incoming(graph.size()), constraints(graph.size());
    for (unsigned int s = 0; s < graph.size(); ++s)
        for (unsigned int p = 0; p < 2; ++p) incoming[graph.ports[s][p]].push_back({s, p});
    for (const auto& row : incoming) if (row.size() != 2) return {};
    for (const auto& row : incoming) {
        const auto [s, p] = row[0]; const auto [t, q] = row[1];
        const auto bit = 1U ^ p ^ q;
        constraints[s].push_back({t, bit}); constraints[t].push_back({s, bit});
    }
    std::vector<int> parity(graph.size(), -1);
    std::vector<std::uint32_t> components; std::uint32_t base = 0;
    for (unsigned int root = 0; root < graph.size(); ++root) {
        if (parity[root] >= 0) continue;
        std::vector<unsigned int> pending{root}; parity[root] = 0; std::uint32_t component = 0;
        while (!pending.empty()) {
            auto s = pending.back(); pending.pop_back(); component |= 1U << s;
            for (const auto& [t, bit] : constraints[s]) {
                auto wanted = parity[s] ^ static_cast<int>(bit);
                if (parity[t] < 0) { parity[t] = wanted; pending.push_back(t); }
                else if (parity[t] != wanted) return {};
            }
        }
        components.push_back(component);
    }
    for (unsigned int s = 0; s < graph.size(); ++s) if (parity[s]) base |= 1U << s;
    std::vector<std::uint32_t> result; result.reserve(std::size_t{1} << components.size());
    for (std::uint32_t choice = 0; choice < (1U << components.size()); ++choice) {
        auto mask = base;
        for (unsigned int c = 0; c < components.size(); ++c) if (choice & (1U << c)) mask ^= components[c];
        // Independently validate BOTH letter maps, including loops and port multiplicities.
        for (unsigned int x = 0; x < 2; ++x) {
            std::uint32_t seen = 0;
            for (unsigned int s = 0; s < graph.size(); ++s) {
                auto target = graph.ports[s][x ^ ((mask >> s) & 1U)];
                if (seen & (1U << target)) throw std::logic_error("XOR permutation enumeration failed scalar validation");
                seen |= 1U << target;
            }
        }
        result.push_back(mask);
    }
    std::sort(result.begin(), result.end()); return result;
}

std::array<unsigned int, 2> permutation_orders(const Graph& graph, const std::vector<std::uint32_t>& permutations, unsigned int cap)
{
    std::array<unsigned int, 2> orders{1, 1};
    for (auto mask : permutations) for (unsigned int x = 0; x < 2; ++x) {
        if (!orders[x]) continue;
        std::uint32_t seen = 0;
        for (unsigned int start = 0; start < graph.size(); ++start) {
            if (seen & (1U << start)) continue;
            unsigned int state = start, length = 0;
            do { seen |= 1U << state; ++length; state = graph.ports[state][x ^ ((mask >> state) & 1U)]; } while (state != start);
            auto factor = length / std::gcd(length, orders[x]);
            if (orders[x] > cap / factor) { orders[x] = 0; break; }
            orders[x] *= factor;
        }
    }
    return orders;
}

std::vector<std::uint32_t> guided_masks(const Graph& graph, const Options& options, const std::vector<std::uint32_t>& permutations)
{
    auto count = std::min(options.masks, 1U << graph.size());
    std::vector<std::uint32_t> result;
    auto add = [&](std::uint32_t mask) {
        if (result.size() < count && std::find(result.begin(), result.end(), mask) == result.end()) result.push_back(mask);
    };
    if (permutations.size() <= count) for (auto mask : permutations) add(mask);
    else if (count > 1) for (unsigned int i = 0; i < count / 2; ++i) add(permutations[i * permutations.size() / (count / 2)]);
    for (auto mask : initial_masks(graph, options)) add(mask);
    Random random{mix(options.seed ^ 0x475549444544ULL)};
    while (result.size() < count) add(static_cast<std::uint32_t>(random.next() % (1U << graph.size())));
    return result;
}

std::array<std::string, 2> guided_prefix(std::uint64_t index, const Options& options, const std::array<unsigned int, 2>& orders)
{
    if (!options.first_prefix.empty()) return {options.first_prefix, options.second_prefix};
    if (options.length == 1) return {"0", "1"};
    if (index == 0) return {"01", "10"};
    if (index == 1 && orders[0] && orders[0] < options.length) {
        std::string block(orders[0], '0'); return {block + '1', '1' + block};
    }
    if (index == 2 && orders[1] && orders[1] < options.length) {
        std::string block(orders[1], '1'); return {'0' + block, block + '0'};
    }
    if (index >= 3) {
        auto value = index - 3;
        for (unsigned int length = 1; length <= std::min(8U, options.length); ++length) {
            auto count = std::uint64_t{1} << (length - 1);
            if (value >= count) { value -= count; continue; }
            std::string first(length, '0'), second;
            for (unsigned int bit = 0; bit + 1 < length; ++bit) first[length - bit - 1] += (value >> bit) & 1;
            second = first; for (auto& c : second) c = c == '0' ? '1' : '0';
            return {first, second};
        }
    }
    Random random{mix(options.seed ^ mix(index) ^ 0x505245464958ULL)};
    auto letter = static_cast<unsigned int>(index % 2);
    if (orders[letter] && orders[letter] < options.length) {
        auto other_length = 1 + random.choice(std::min(4U, options.length - orders[letter]));
        auto prefix = random.word(random.choice(std::min(4U, options.length - orders[letter] - other_length) + 1));
        std::string a(orders[letter], static_cast<char>('0' + letter)), b(other_length, static_cast<char>('1' - letter));
        return {prefix + a + b, prefix + b + a};
    }
    auto small = options; small.length = std::min(24U, options.length);
    auto candidate = commutator(index, small);
    return {candidate.prefix + candidate.a + candidate.b, candidate.prefix + candidate.b + candidate.a};
}

unsigned int agreement(const Profile& left, const Profile& right)
{
    std::uint64_t equal = 0;
    for (unsigned int s = 0; s < 20; ++s) equal |= left.planes[s] & right.planes[s];
    return std::popcount(equal);
}
unsigned int forecast(Packed& packed, const Profile& left, const Profile& right, unsigned int depth,
                      unsigned int total, GuidedCounts& counts)
{
    ++counts.lookahead_nodes;
    auto score = agreement(left, right);
    if (!depth || score == total) return score;
    for (unsigned int x = 0; x < 2; ++x)
        score = std::max(score, forecast(packed, packed.step(left, x), packed.step(right, x), depth - 1, total, counts));
    return score;
}
struct BeamNode {
    Profile left, right;
    std::string suffix;
    std::vector<unsigned int> trace;
    unsigned int lookahead_score = 0;
    std::uint64_t tie = 0;
};
class Family1ViabilityCache {
    Graph graph;
    unsigned int coordinate_limit, distance_limit;
    std::uint32_t relevant = 0;
    std::unordered_map<std::uint32_t, hardpair::PairMergeabilityResult> tables;
    std::vector<std::string> proofs;
    std::uint64_t calls = 0, checked = 0, hits = 0, analyses = 0, unknown = 0, blocked = 0, resets = 0;
    std::uint64_t distance_calls = 0, distance_checked = 0;
    std::string closed_proof(std::uint32_t mask, unsigned int first, unsigned int second) const
    {
        const auto n = graph.size();
        std::vector<bool> seen(n * n, false);
        std::vector<unsigned int> queue{first * n + second}; seen[queue[0]] = true;
        for (std::size_t head = 0; head < queue.size(); ++head) {
            const auto a = queue[head] / n, b = queue[head] % n;
            if (a == b) throw std::logic_error("viability negative proof reaches the diagonal");
            for (unsigned int x = 0; x < 2; ++x) {
                const auto next_a = graph.ports[a][x ^ ((mask >> a) & 1U)];
                const auto next_b = graph.ports[b][x ^ ((mask >> b) & 1U)];
                auto code = next_a * n + next_b;
                if (!seen[code]) { seen[code] = true; queue.push_back(code); }
            }
        }
        std::ostringstream out;
        out << "{\"mask\":" << mask << ",\"endpoints\":[" << first << ',' << second
            << "],\"proof_kind\":\"complete reachable closed ordered-pair set excluding every diagonal\",\"closed_pairs\":[";
        for (std::size_t i = 0; i < queue.size(); ++i) {
            if (i) out << ',';
            out << '[' << queue[i] / n << ',' << queue[i] % n << ']';
        }
        out << "]}"; return out.str();
    }
public:
    Family1ViabilityCache(const Graph& value, unsigned int limit, unsigned int distances = 0)
        : graph(value), coordinate_limit(limit), distance_limit(distances)
    {
        for (unsigned int s = 0; s < graph.size(); ++s) if (graph.ports[s][0] != graph.ports[s][1]) relevant |= 1U << s;
    }
    bool has_obstruction(const family1::ExactPairAgreement& pair)
    {
        ++calls;
        if (!coordinate_limit) return false;
        // Cache hits consume the same fixed coordinate budget as misses.
        for (const auto& triple : pair.remaining_coordinate_pairs(coordinate_limit)) {
            ++checked; const auto mask = triple[0], key = mask & relevant;
            auto found = tables.find(key);
            if (found == tables.end()) {
                hardpair::PairMergeabilityLimits limits;
                limits.max_pair_states = static_cast<std::uint64_t>(graph.size()) * graph.size();
                limits.interrupted = &interrupted;
                auto transition = [&](std::uint32_t state, bool input) {
                    return graph.ports[state][static_cast<unsigned int>(input) ^ ((key >> state) & 1U)];
                };
                auto table = hardpair::analyze_pair_mergeability(graph.size(), transition, limits); ++analyses;
                if (!table.complete) { ++unknown; continue; }
                if (tables.size() >= 4096) { tables.clear(); ++resets; }
                found = tables.emplace(key, std::move(table)).first;
            } else ++hits;
            if (found->second.proven_unmergeable(triple[1], triple[2])) {
                ++blocked;
                if (proofs.size() < 8) proofs.push_back(closed_proof(mask, triple[1], triple[2]));
                return true;
            }
        }
        return false;
    }
    std::uint64_t minimum_distance(const family1::ExactPairAgreement& pair)
    {
        if (!distance_limit) return 0;
        ++distance_calls;
        std::uint64_t bound = 0;
        // Every selected coordinate needs at least its own shortest merging
        // suffix. Their maximum is admissible for the full product. Cache
        // hits and misses consume exactly the same deterministic budget.
        for (const auto& triple : pair.remaining_coordinate_pairs(distance_limit)) {
            ++distance_checked; const auto mask = triple[0], key = mask & relevant;
            auto found = tables.find(key);
            if (found == tables.end()) {
                hardpair::PairMergeabilityLimits limits;
                limits.max_pair_states = static_cast<std::uint64_t>(graph.size()) * graph.size();
                limits.interrupted = &interrupted;
                auto transition = [&](std::uint32_t state, bool input) {
                    return graph.ports[state][static_cast<unsigned int>(input) ^ ((key >> state) & 1U)];
                };
                auto table = hardpair::analyze_pair_mergeability(graph.size(), transition, limits); ++analyses;
                if (!table.complete) { ++unknown; continue; }
                if (tables.size() >= 4096) { tables.clear(); ++resets; }
                found = tables.emplace(key, std::move(table)).first;
            } else ++hits;
            const auto& table = found->second;
            if (!table.complete) continue;
            if (table.proven_unmergeable(triple[1], triple[2])) {
                ++blocked;
                if (proofs.size() < 8) proofs.push_back(closed_proof(mask, triple[1], triple[2]));
                return std::numeric_limits<std::uint64_t>::max();
            }
            const auto distance = table.distance[static_cast<std::size_t>(triple[1]) * graph.size() + triple[2]];
            if (distance == hardpair::PairMergeabilityResult::unreachable_distance)
                throw std::logic_error("complete mergeable coordinate has no finite distance");
            bound = std::max(bound, static_cast<std::uint64_t>(distance));
        }
        return bound;
    }
    std::string json() const
    {
        std::ostringstream out;
        out << "{\"coordinate_limit\":" << coordinate_limit
            << ",\"distance_coordinate_limit\":" << distance_limit
            << ",\"distance_bound_checks\":" << distance_calls << ",\"distance_coordinates_checked\":" << distance_checked
            << ",\"distance_bound_rule\":\"maximum complete single-DFA shortest merge distance; unknown contributes zero\""
            << ",\"selection\":\"first N unmerged mask IDs in deterministic order; cache hits count toward N\""
            << ",\"statistics_scope\":\"this invocation; cache is cold after resume; decisions are cache-independent\""
            << ",\"checks\":" << calls << ",\"coordinates_checked\":" << checked << ",\"cache_hits\":" << hits
            << ",\"complete_or_unknown_analyses\":" << analyses << ",\"unknown_analyses_not_pruned\":" << unknown
            << ",\"proven_obstructions\":" << blocked << ",\"cache_entries\":" << tables.size()
            << ",\"cache_resets\":" << resets << ",\"cache_capacity\":4096,\"proof_examples\":[";
        for (std::size_t i = 0; i < proofs.size(); ++i) { if (i) out << ','; out << proofs[i]; }
        out << "],\"proof_examples_truncated\":" << (blocked > proofs.size() ? "true" : "false")
            << ",\"graph_score_lower_bound_claimed\":false}";
        return out.str();
    }
};
struct Family1FinderState {
    family1::ExactPairAgreement pair;
    std::shared_ptr<Family1ViabilityCache> viability;
    std::uint64_t remaining_count() const { return pair.mask_count() - pair.merged_count(); }
    std::uint64_t mask_count() const { return pair.mask_count(); }
    std::uint64_t permutation_mismatch_count() const { return pair.permutation_mismatch_count(); }
    Family1FinderState append_common(bool input) const { return {pair.append_common(input), viability}; }
    bool has_proven_obstruction() const { return viability && viability->has_obstruction(pair); }
    std::uint64_t minimum_completion_length() const { return viability ? viability->minimum_distance(pair) : 0; }
};

std::vector<std::array<std::string, 2>> finder_cores(
    const Graph& graph, const Options& options, const std::vector<std::uint32_t>& permutations,
    const std::array<unsigned int, 2>& orders)
{
    using Words = std::array<std::string, 2>;
    if (!options.first_prefix.empty()) return {{options.first_prefix, options.second_prefix}};
    if (options.length == 1 || graph.ports[0][0] == graph.ports[0][1]) return {{"0", "1"}};
    std::uint32_t relevant = 0;
    for (unsigned int s = 0; s < graph.size(); ++s) if (graph.ports[s][0] != graph.ports[s][1]) relevant |= 1U << s;
    std::set<std::uint32_t> representatives;
    for (auto mask : permutations) representatives.insert(mask & relevant);
    auto compatible = [&](const Words& words) {
        return std::all_of(representatives.begin(), representatives.end(), [&](auto mask) {
            return endpoint(graph, mask, words[0]) == endpoint(graph, mask, words[1]);
        });
    };
    std::vector<Words> grids, complements, all_grids, all_complements, result{{"01", "10"}};
    for (unsigned int total = 2; total <= std::min(2U * graph.size(), options.length); ++total)
        for (unsigned int a = 1; a < total; ++a) {
            auto b = total - a;
            if (a > graph.size() || b > graph.size()) continue;
            Words words{std::string(a, '0') + std::string(b, '1'), std::string(b, '1') + std::string(a, '0')};
            if (words != result[0]) {
                all_grids.push_back(words);
                if (compatible(words)) grids.push_back(std::move(words));
            }
        }
    for (unsigned int length = 1; length <= std::min(8U, options.length); ++length)
        for (std::uint64_t index = 0; index < (std::uint64_t{1} << (length - 1)); ++index) {
            Words words{std::string(length, '0'), ""};
            for (unsigned int bit = 0; bit + 1 < length; ++bit) words[0][length - bit - 1] += (index >> bit) & 1;
            words[1] = words[0]; for (auto& c : words[1]) c = c == '0' ? '1' : '0';
            if (words != result[0]) {
                all_complements.push_back(words);
                if (compatible(words)) complements.push_back(std::move(words));
            }
        }
    auto add = [&](const Words& words) {
        if (std::find(result.begin(), result.end(), words) == result.end()) result.push_back(words);
    };
    // Root compatibility is a priority, never a deletion: a nonempty common
    // prefix changes the starting state and can repair a root-incompatible core.
    for (std::size_t i = 0; i < std::max({grids.size(), complements.size(), all_grids.size(), all_complements.size()}); ++i) {
        if (i < grids.size()) add(grids[i]);
        if (i < complements.size()) add(complements[i]);
        if (i < all_grids.size()) add(all_grids[i]);
        if (i < all_complements.size()) add(all_complements[i]);
    }
    for (std::uint64_t index : {1ULL, 2ULL}) add(guided_prefix(index, options, orders));
    return result;
}

std::array<std::string, 2> finder_prefix(std::uint64_t index, unsigned int cap, const Options& options,
    const std::vector<std::array<std::string, 2>>& learned,
    const std::vector<std::array<std::string, 2>>& templates, const std::array<unsigned int, 2>& orders)
{
    if (!options.first_prefix.empty()) return {options.first_prefix, options.second_prefix};
    const std::array<std::string, 4> common{"", "0", "00", "01"};
    std::string prefix;
    const std::vector<std::array<std::string, 2>>* source = &templates;
    std::uint64_t core_index = index / common.size();
    if (!learned.empty() && index % 4 != 3) {
        source = &learned; core_index = (index / 4) * 3 + index % 4;
        const auto round = core_index / learned.size();
        if (round) prefix = common[1 + (round - 1) % 3];
    } else if (!learned.empty()) {
        prefix = common[(core_index + core_index / templates.size()) % common.size()];
    } else prefix = common[static_cast<std::size_t>(index % common.size())];
    if (prefix.size() >= cap) prefix.clear();
    auto remaining = cap - static_cast<unsigned int>(prefix.size());
    std::array<std::string, 2> core;
    bool found = false;
    for (std::size_t offset = 0; offset < source->size(); ++offset) {
        const auto& candidate = (*source)[static_cast<std::size_t>((core_index + offset) % source->size())];
        if (candidate[0].size() <= remaining) { core = candidate; found = true; break; }
    }
    if (!found) {
        auto smaller = options; smaller.length = remaining;
        core = guided_prefix(core_index, smaller, orders);
    }
    return {prefix + core[0], prefix + core[1]};
}

std::pair<std::vector<std::array<std::string, 2>>, std::string> permutation_profile_cores(
    const Graph& graph, const Options& options, const std::vector<std::uint32_t>& permutations)
{
    std::uint32_t relevant = 0;
    for (unsigned int s = 0; s < graph.size(); ++s) if (graph.ports[s][0] != graph.ports[s][1]) relevant |= 1U << s;
    std::vector<std::uint32_t> unique;
    unique.reserve(permutations.size());
    for (auto mask : permutations) unique.push_back(mask & relevant);
    std::sort(unique.begin(), unique.end()); unique.erase(std::unique(unique.begin(), unique.end()), unique.end());
    hardpair::PrefixSeedOptions limits;
    limits.max_depth = std::min(options.prefix_depth, options.length);
    limits.max_words = static_cast<std::size_t>(options.prefix_max_words);
    limits.max_pairs = static_cast<std::size_t>(options.prefix_max_pairs);
    limits.samples_per_depth = options.prefix_samples_per_depth; limits.seed = options.seed;
    limits.common_prefix_depth = options.prefix_common_depth;
    for (unsigned int depth : {20U, 24U, 28U, 32U}) if (depth <= options.length) limits.sample_depths.push_back(depth);
    limits.interrupted = &interrupted;
    hardpair::PrefixSeedResult report;
    report.coordinate_count = unique.size();
    report.empty_coordinate_family = unique.empty();
    if (options.first_prefix.empty()) {
        std::vector<std::uint32_t> initial(unique.size(), 0);
        auto transition = [&](std::size_t coordinate, std::uint32_t state, bool input) {
            return graph.ports[state][static_cast<unsigned int>(input) ^ ((unique[coordinate] >> state) & 1U)];
        };
        report = hardpair::enumerate_prefix_seeds(initial, transition, limits);
    }
    std::vector<std::array<std::string, 2>> result;
    for (const auto& pair : report.pairs) {
        if (pair.first.empty() || pair.first == pair.second || pair.first.size() != pair.second.size()
            || pair.first.size() > options.length)
            throw std::logic_error("generic prefix helper returned invalid equal-length words");
        // Independently gate each returned profile collision against every
        // distinct permutation DFA. This never accepts a full-family witness.
        for (auto mask : unique)
            if (endpoint(graph, mask, pair.first) != endpoint(graph, mask, pair.second))
                throw std::logic_error("generic prefix profile collision fails scalar permutation replay");
        result.push_back({pair.first, pair.second});
    }
    std::ostringstream out; out << std::setprecision(17);
    std::map<std::size_t, std::size_t> lengths;
    std::map<std::size_t, std::size_t> common_lengths;
    for (const auto& pair : report.pairs) ++lengths[pair.first.size()];
    for (const auto& pair : report.pairs) {
        std::size_t common = 0;
        while (common < pair.first.size() && pair.first[common] == pair.second[common]) ++common;
        ++common_lengths[common];
    }
    out << "{\"method\":\"permutation-profile-depth-diverse-v2\",\"logical_permutation_masks\":" << permutations.size()
        << ",\"unique_permutation_dfas\":" << unique.size() << ",\"pairs\":" << report.pairs.size()
        << ",\"first_collision_length\":" << report.first_collision_length << ",\"completed_depth\":" << report.completed_depth
        << ",\"words_evaluated\":" << report.words_evaluated << ",\"profiles_retained\":" << report.profiles_retained
        << ",\"buckets_with_collisions\":" << report.buckets_with_collisions
        << ",\"complete_first_collision_layer\":" << (report.complete_first_collision_layer ? "true" : "false")
        << ",\"first_collision_proved_minimum\":" << (report.first_collision_proved_minimum ? "true" : "false")
        << ",\"complete_pair_collection\":" << (report.complete_pair_collection ? "true" : "false")
        << ",\"pair_count_saturated\":" << (report.pair_count_saturated ? "true" : "false")
        << ",\"depth_capped\":" << (report.depth_capped ? "true" : "false")
        << ",\"word_capped\":" << (report.word_capped ? "true" : "false")
        << ",\"pair_capped\":" << (report.pair_capped ? "true" : "false")
        << ",\"interrupted\":" << (report.interrupted ? "true" : "false")
        << ",\"empty_coordinate_family\":" << (report.empty_coordinate_family ? "true" : "false")
        << ",\"depth_diversified\":" << (report.depth_diversified ? "true" : "false")
        << ",\"sampling_capped\":" << (report.sampling_capped ? "true" : "false")
        << ",\"largest_sampled_depth\":" << report.largest_sampled_depth
        << ",\"sampled_words_evaluated\":" << report.sampled_words_evaluated
        << ",\"explicit_prefix_pair\":" << (!options.first_prefix.empty() ? "true" : "false")
        << ",\"max_depth\":" << limits.max_depth << ",\"max_words\":" << limits.max_words << ",\"max_pairs\":" << limits.max_pairs
        << ",\"seconds\":" << report.seconds << ",\"selected_pairs_by_depth\":[";
    bool comma = false;
    for (const auto& [depth, count] : lengths) {
        if (comma) out << ','; comma = true;
        out << "{\"depth\":" << depth << ",\"pairs\":" << count << '}';
    }
    out << "]";
    if (options.prefix_common_depth) {
        out << ",\"common_prefix_depth\":" << options.prefix_common_depth << ",\"selected_pairs_by_actual_common_prefix\":[";
        bool separator = false;
        for (const auto& [common, count] : common_lengths) {
            if (separator) out << ','; separator = true;
            out << "{\"common_prefix_length\":" << common << ",\"pairs\":" << count << '}';
        }
        out << ']';
    }
    out << ",\"per_depth\":[";
    for (std::size_t i = 0; i < report.per_depth.size(); ++i) {
        if (i) out << ',';
        const auto& layer = report.per_depth[i];
        out << "{\"depth\":" << layer.depth << ",\"words\":" << layer.words << ",\"unique_profiles\":" << layer.unique_profiles
            << ",\"colliding_buckets\":" << layer.colliding_buckets << ",\"total_pairs_available\":" << layer.total_pairs_available
            << ",\"retained_candidates\":" << layer.retained_candidates << ",\"selected_pairs\":" << layer.selected_pairs
            << ",\"complete_enumeration\":" << (layer.complete_enumeration ? "true" : "false")
            << ",\"sampled\":" << (layer.sampled ? "true" : "false")
            << ",\"pair_count_saturated\":" << (layer.pair_count_saturated ? "true" : "false") << '}';
    }
    out << "],\"sample_depths\":[";
    for (std::size_t i = 0; i < limits.sample_depths.size(); ++i) { if (i) out << ','; out << limits.sample_depths[i]; }
    out << "],\"samples_per_depth\":" << limits.samples_per_depth
        << ",\"seed_schedule\":\"three learned root pairs then one unfiltered template with rotating common prefix; later learned rounds also rotate prefixes\""
        << ",\"proof_scope\":\"compatible equal-length endpoints on the permutation subfamily only; every complete prefixed pair is gated again; no full-family score claimed\"}";
    return {std::move(result), out.str()};
}

std::string tail_json(const hardpair::TailResult& tail, const std::vector<hardpair::CoordinatePair>& coordinates, bool last_query = true)
{
    const char* status = tail.found ? "found" : tail.interrupted ? "interrupted" : tail.capped ? "capped"
        : tail.unreachable ? "unreachable" : "unknown";
    std::ostringstream out; out << std::setprecision(17);
    out << "{\"status\":" << cli::quote(status) << ",\"shortest_conditional\":" << (tail.shortest_conditional ? "true" : "false")
        << ",\"states\":" << tail.states_seen << ",\"expanded_states\":" << tail.expanded_states
        << ",\"depth\":" << (tail.found ? tail.suffix.size() : tail.depth_reached)
        << ",\"capped\":" << (tail.capped ? "true" : "false")
        << ",\"depth_capped\":" << (tail.depth_capped ? "true" : "false")
        << ",\"state_capped\":" << (tail.state_capped ? "true" : "false")
        << ",\"suffix\":" << cli::quote(tail.suffix) << ",\"seconds\":" << tail.seconds
        << ",\"last_query_only\":" << (last_query ? "true" : "false") << ",\"global_shortest\":false,\"conditional_coordinates\":[";
    for (std::size_t i = 0; i < coordinates.size(); ++i) {
        if (i) out << ',';
        out << '[' << coordinates[i].coordinate << ',' << coordinates[i].first << ',' << coordinates[i].second << ']';
    }
    out << "]}"; return out.str();
}

std::string window_distribution_json(const hardpair::WindowDistribution& distribution)
{
    std::ostringstream out; out << std::setprecision(17);
    out << "{\"window_k\":" << distribution.window_k << ",\"initial_remaining\":" << distribution.initial_remaining
        << ",\"mask_count\":" << distribution.mask_count << ",\"expanded_nodes\":" << distribution.expanded_nodes
        << ",\"window_count\":" << distribution.window_count << ",\"expected_window_count\":" << (1U << distribution.window_k)
        << ",\"min_drop\":" << distribution.min_drop << ",\"max_drop\":" << distribution.max_drop
        << ",\"mean_drop\":" << distribution.mean_drop << ",\"median_drop\":" << distribution.median_drop
        << ",\"variance_drop\":" << distribution.variance_drop << ",\"stddev_drop\":" << distribution.stddev_drop
        << ",\"zero_drop_count\":" << distribution.zero_drop_count << ",\"full_merge_count\":" << distribution.full_merge_count
        << ",\"complete\":" << (distribution.complete ? "true" : "false")
        << ",\"interrupted\":" << (distribution.interrupted ? "true" : "false")
        << ",\"expansion_limit_reached\":" << (distribution.expansion_limit_reached ? "true" : "false")
        << ",\"normalization_defined\":" << (distribution.normalization_defined ? "true" : "false")
        << ",\"normalized_drop_denominator\":" << distribution.initial_remaining
        << ",\"all_scores_exact\":true,\"score_scope\":\"full\",\"seconds\":" << distribution.seconds
        << ",\"windows\":[";
    for (std::size_t i = 0; i < distribution.ranked.size(); ++i) {
        if (i) out << ',';
        const auto& entry = distribution.ranked[i];
        out << "{\"window\":" << cli::quote(entry.window) << ",\"drop\":" << entry.drop
            << ",\"remaining_count\":" << entry.remaining_count << ",\"merged_count\":" << distribution.mask_count - entry.remaining_count
            << ",\"normalized_drop\":" << entry.normalized_drop << ",\"all_merged\":" << (entry.all_merged ? "true" : "false") << '}';
    }
    out << "],\"histogram\":[";
    for (std::size_t i = 0; i < distribution.histogram.size(); ++i) {
        if (i) out << ',';
        out << "{\"drop\":" << distribution.histogram[i].first << ",\"count\":" << distribution.histogram[i].second << '}';
    }
    out << "]}"; return out.str();
}
void retain_attempt(State& state, GuidedAttempt attempt)
{
    auto& best = state.best;
    const auto old_blocked = best.gate_blocked || best.proven_obstruction;
    const auto new_blocked = attempt.gate_blocked || attempt.proven_obstruction;
    if (!best.present || attempt.scalar_verified || (old_blocked && !new_blocked)
        || (old_blocked == new_blocked && (attempt.trace.back() > best.trace.back()
            || (attempt.trace.back() == best.trace.back() && attempt.permutation_mismatches < best.permutation_mismatches))))
        best = std::move(attempt);
}

std::string guided_attempt_json(const GuidedAttempt& a, unsigned int m)
{
    if (!a.present) return "null";
    std::ostringstream out;
    out << "{\"initial_words\":[" << cli::quote(a.first) << ',' << cli::quote(a.second) << "]"
        << ",\"suffix\":" << cli::quote(a.suffix) << ",\"merged_count\":" << a.trace.back()
        << ",\"total_masks\":" << (a.full_scope ? a.full_mask_count : a.masks.size()) << ",\"score_scope\":"
        << cli::quote(a.full_scope || a.masks.size() == (1U << m) ? "full" : "sampled") << ",\"sampled_masks\":";
    if (a.full_scope && a.masks.empty()) out << "null";
    else { out << '['; for (std::size_t i = 0; i < a.masks.size(); ++i) { if (i) out << ','; out << a.masks[i]; } out << ']'; }
    if (a.full_scope) out << ",\"mask_range\":[0," << a.full_mask_count << ']';
    out << ",\"score_trace\":[";
    for (std::size_t i = 0; i < a.trace.size(); ++i) { if (i) out << ','; out << a.trace[i]; }
    out << "],\"permutation_mismatch_count\":" << a.permutation_mismatches
        << ",\"gate_blocked\":" << (a.gate_blocked ? "true" : "false")
        << ",\"proven_obstruction\":" << (a.proven_obstruction ? "true" : "false")
        << ",\"full_scalar_verified\":" << (a.scalar_verified ? "true" : "false")
        << ",\"scalar_first_separator\":";
    if (a.first_separator < 0) out << "null"; else out << a.first_separator;
    out << '}'; return out.str();
}

std::string result_json(const Options& options, const Graph& graph, const State& state,
                        const std::string& configuration_hash, const std::array<std::string, 2>& witness,
                        double seconds, bool complete, double packed_seconds = 0, double scalar_seconds = 0,
                        std::uint64_t benchmark_checksum = 0, const std::vector<std::uint32_t>* permutations = nullptr,
                        const std::string& exact_agreement_json = "")
{
    const bool found = !witness[0].empty(); const auto& c = state.counts;
    std::ostringstream out; out << std::setprecision(17);
    out << "{\"schema\":1,\"method\":\"family1-graph-adapted-static-mask-sampler-v1\",\"m\":" << graph.size()
        << ",\"key\":" << cli::quote(graph.key()) << ",\"source_key\":" << cli::quote(options.source_key)
        << ",\"config_sha256\":" << cli::quote(configuration_hash) << ",\"canonical_table\":[";
    for (unsigned int s = 0; s < graph.size(); ++s) {
        if (s) out << ','; out << '[' << graph.ports[s][0] << ',' << graph.ports[s][1] << ']';
    }
    out << "],\"length\":" << options.length << ",\"mode\":" << cli::quote(options.mode)
        << ",\"seed\":" << options.seed << ",\"requested_samples\":" << options.samples
        << ",\"samples_completed\":" << state.next << ",\"requested_masks\":" << options.masks << ",\"sampled_masks\":";
    if (options.full_guidance) out << "null";
    else { out << '['; for (std::size_t i = 0; i < state.masks.size(); ++i) { if (i) out << ','; out << state.masks[i]; } out << ']'; }
    out << ",\"decision\":" << cli::quote(found ? "collision" : "unknown")
        << ",\"lower_bound\":1,\"upper_bound\":";
    if (found) out << (options.mode == "guided" || options.mode == "finder" || options.mode == "distribution" ? witness[0].size() : options.length); else out << "null";
    out << ",\"witness\":";
    if (found) out << '[' << cli::quote(witness[0]) << ',' << cli::quote(witness[1]) << ']'; else out << "null";
    out << ",\"scalar_witness_masks_verified\":" << (found ? 1U << graph.size() : 0)
        << ",\"hash_matches\":" << c.hash_matches << ",\"projected_profile_equalities\":" << c.projected_equalities
        << ",\"scalar_candidate_checks\":" << c.scalar_candidate_checks << ",\"scalar_masks_checked\":" << c.scalar_masks_checked
        << ",\"counterexample_masks\":" << c.counterexamples << ",\"profile_cache_resets\":" << c.cache_resets
        << ",\"packed_scalar_self_checks\":" << c.self_checks << ",\"seconds\":" << seconds
        << ",\"traversal_complete\":" << (complete ? "true" : "false")
        << ",\"shortest_proved\":false,\"all_witnesses_collected\":false,\"global_maximum_certified\":false"
        << ",\"reason\":" << cli::quote(found ? "all-static-masks-independent-scalar-replay" : complete ? "sampling-miss-is-not-a-lower-bound" : "partial-sampling-no-lower-bound");
    if (options.mode == "benchmark") out << ",\"benchmark_profiles_equal\":true,\"benchmark_words\":" << state.next
        << ",\"packed_seconds\":" << packed_seconds << ",\"scalar_seconds\":" << scalar_seconds
        << ",\"scalar_over_packed_speedup\":" << (packed_seconds > 0 ? scalar_seconds / packed_seconds : 0)
        << ",\"benchmark_checksum\":" << benchmark_checksum;
    if (options.mode == "guided" || options.mode == "finder" || options.mode == "distribution") {
        out << ",\"requested_length\":" << options.length << ",\"witness_length\":";
        if (found) out << witness[0].size(); else out << "null";
        out << ",\"beam_width\":" << options.beam_width << ",\"lookahead\":" << options.lookahead
            << ",\"guidance_scope\":" << cli::quote(options.full_guidance ? "full" : "sampled")
            << ",\"guided_attempt\":" << guided_attempt_json(state.best, graph.size())
            << ",\"permutation_gate_checked_all_masks\":true,\"permutation_mask_count\":" << (permutations ? permutations->size() : 0)
            << ",\"permutation_masks\":";
        if (permutations && permutations->size() <= 1024) {
            out << '['; for (std::size_t i = 0; i < permutations->size(); ++i) { if (i) out << ','; out << (*permutations)[i]; } out << ']';
        } else out << "null";
        out << ",\"permutation_prefix_seeds_checked\":" << state.guided_counts.prefix_gates_checked
            << ",\"permutation_prefix_seeds_blocked\":" << state.guided_counts.prefix_gates_blocked
            << ",\"beam_nodes_expanded\":" << state.guided_counts.beam_nodes
            << ",\"lookahead_nodes\":" << state.guided_counts.lookahead_nodes
            << ",\"guidance_expansion_limits_reached\":" << state.guided_counts.expansion_limits;
        if (!exact_agreement_json.empty()) out << ",\"exact_best_agreement\":" << exact_agreement_json;
    }
    if (options.mode == "finder") {
        out << ",\"best_of_seeds\":" << (options.best_of_seeds ? "true" : "false")
            << ",\"module_stats\":{\"window_k\":" << options.window_k << ",\"max_expansions_per_seed\":" << options.max_expansions
            << ",\"window_blocks\":" << state.finder_window_blocks
            << ",\"expanded_nodes\":" << state.guided_counts.beam_nodes << ",\"tail_threshold\":" << options.tail_threshold
            << ",\"tail_calls\":" << state.finder_tail_calls << ",\"tail_states\":" << state.finder_tail_states
            << ",\"expansion_limits_reached\":" << state.guided_counts.expansion_limits
            << ",\"prefix_seeds_checked\":" << state.guided_counts.prefix_gates_checked
            << ",\"obstruction_pruned_nodes\":" << state.finder_obstruction_pruned
            << ",\"distance_coordinates\":" << options.distance_coordinates
            << ",\"distance_bound_checks\":" << state.finder_distance_checks
            << ",\"distance_bound_pruned_nodes\":" << state.finder_distance_pruned
            << ",\"beam_ranking\":" << cli::quote(options.beam_ranking)
            << ",\"common_prefix_variants\":[\"\",\"0\",\"00\",\"01\"]"
            << ",\"seed_coverage\":\"finite heuristic list; root-core compatibility only prioritizes; every complete prefixed pair is gated\"}"
            << ",\"exact_tail\":" << (state.finder_best_tail_json != "null" ? state.finder_best_tail_json : state.finder_last_tail_json)
            << ",\"last_exact_tail\":" << state.finder_last_tail_json
            << ",\"prefix_seed_stats\":" << state.finder_prefix_stats_json
            << ",\"viability\":" << state.finder_viability_json;
    }
    out << '}'; return out.str();
}

std::string exact_trace_json(const Graph& graph, const GuidedAttempt& attempt, std::size_t expected_permutations)
{
    if (!attempt.present) return "null";
    auto context = std::make_shared<family1::PairAgreementContext>(graph);
    if (context->permutation_mask_count() != expected_permutations)
        throw std::logic_error("independent exact context and XOR permutation counts disagree");
    family1::ExactPairAgreement pair(context, attempt.first, attempt.second);
    std::vector<std::uint64_t> trace{pair.merged_count()};
    for (char input : attempt.suffix) {
        pair = pair.append_common(input == '1');
        if (pair.merged_count() < trace.back()) throw std::logic_error("exact common-suffix agreement decreased");
        trace.push_back(pair.merged_count());
    }
    if (attempt.scalar_verified && !pair.all_merged()) throw std::logic_error("exact tracker disagrees with positive scalar replay");
    std::ostringstream out;
    out << "{\"score_scope\":\"full\",\"merged_count\":" << pair.merged_count()
        << ",\"total_masks\":" << pair.mask_count() << ",\"permutation_mismatch_count\":" << pair.permutation_mismatch_count()
        << ",\"initial_words\":[" << cli::quote(attempt.first) << ',' << cli::quote(attempt.second)
        << "],\"suffix\":" << cli::quote(attempt.suffix) << ",\"score_trace\":[";
    for (std::size_t i = 0; i < trace.size(); ++i) { if (i) out << ','; out << trace[i]; }
    out << "]}"; return out.str();
}

int run_finder(const Options& options, const Graph& graph, const std::string& config_hash)
{
    const auto started = Clock::now();
    const auto permutations = permutation_masks(graph);
    const auto orders = permutation_orders(graph, permutations, options.length - 1);
    const auto templates = finder_cores(graph, options, permutations, orders);
    auto [learned, prefix_statistics] = permutation_profile_cores(graph, options, permutations);
    auto context = std::make_shared<family1::PairAgreementContext>(graph);
    auto viability = std::make_shared<Family1ViabilityCache>(graph, options.viability_coordinates, options.distance_coordinates);
    if (context->permutation_mask_count() != permutations.size())
        throw std::logic_error("finder context and XOR permutation enumeration disagree");
    auto state = load_checkpoint(options, graph, config_hash);
    if (state.finder_prefix_stats_json == "null") state.finder_prefix_stats_json = prefix_statistics;
    state.guided = true; state.full_guidance = true;
    std::array<std::string, 2> witness;
    if (state.best.present && state.best.scalar_verified)
        witness = {state.best.first + state.best.suffix, state.best.second + state.best.suffix};
    const auto invocation_end = options.limit_samples ? state.next + std::min(options.samples - state.next, options.limit_samples) : options.samples;
    for (; state.next < invocation_end && !interrupted; ++state.next) {
        if (!witness[0].empty() && witness[0].size() == 1) break;
        const auto previous_witness_length = witness[0].size();
        auto cap = options.length;
        if (options.best_of_seeds && !witness[0].empty()) cap = static_cast<unsigned int>(witness[0].size() - 1);
        auto initial_words = finder_prefix(state.next, cap, options, learned, templates, orders);
        if (initial_words[0].size() > cap) continue; // Fixed explicit prefix cannot yield a shorter completion.
        Family1FinderState initial{family1::ExactPairAgreement(context, initial_words[0], initial_words[1]), viability};
        hardpair::FinderOptions limits;
        limits.window_k = options.window_k; limits.beam_width = options.beam_width;
        limits.rank_by_remaining = options.beam_ranking == "remaining";
        limits.max_suffix = cap - static_cast<unsigned int>(initial_words[0].size());
        limits.tail_threshold = options.tail_threshold; limits.max_expansions = options.max_expansions;
        limits.tie_seed = mix(options.seed ^ state.next); limits.interrupted = &interrupted;
        limits.tail_limits.max_states = static_cast<std::size_t>(options.tail_max_states);
        limits.tail_limits.max_depth = limits.max_suffix; limits.tail_limits.interrupted = &interrupted;
        std::vector<hardpair::CoordinatePair> last_coordinates;
        auto exact_tail = [&](const Family1FinderState& current, const hardpair::TailLimits& tail_limits) {
            last_coordinates.clear();
            for (const auto& triple : current.pair.remaining_coordinate_pairs())
                last_coordinates.push_back({triple[0], triple[1], triple[2]});
            auto transition = [&](std::size_t coordinate, std::uint32_t value, bool input) {
                return graph.ports[value][static_cast<unsigned int>(input) ^ ((static_cast<std::uint32_t>(coordinate) >> value) & 1U)];
            };
            auto tail = hardpair::exact_suffix_bfs(last_coordinates, transition, tail_limits);
            state.finder_last_tail_json = tail_json(tail, last_coordinates);
            return tail;
        };
        auto result = hardpair::find_hard_pair_suffix(std::move(initial), limits, exact_tail);
        ++state.guided_counts.prefix_gates_checked;
        state.guided_counts.prefix_gates_blocked += result.permutation_mismatch_count != 0;
        state.guided_counts.beam_nodes += result.expanded_nodes;
        state.guided_counts.expansion_limits += result.expansion_limit_reached;
        state.finder_window_blocks += result.window_blocks;
        state.finder_tail_calls += result.tail_calls; state.finder_tail_states += result.tail_states;
        state.finder_obstruction_pruned += result.obstruction_pruned_nodes;
        if (options.distance_coordinates) {
            state.finder_distance_checks += result.distance_bound_checks;
            state.finder_distance_pruned += result.distance_bound_pruned_nodes;
        }
        if (result.score_trace.size() != result.suffix.size() + 1 || result.mask_count != context->mask_count()
            || result.score_trace.back() != result.merged_count)
            throw std::logic_error("invalid generic finder score trace");
        GuidedAttempt attempt;
        attempt.present = true; attempt.full_scope = true; attempt.full_mask_count = result.mask_count;
        attempt.first = initial_words[0]; attempt.second = initial_words[1]; attempt.suffix = result.suffix;
        attempt.permutation_mismatches = result.permutation_mismatch_count; attempt.gate_blocked = result.permutation_mismatch_count != 0;
        attempt.proven_obstruction = result.proven_obstruction;
        for (auto score : result.score_trace) attempt.trace.push_back(static_cast<unsigned int>(score));
        if (result.mask_count <= 64)
            for (std::uint32_t mask = 0; mask < result.mask_count; ++mask) attempt.masks.push_back(mask);
        if (result.found || result.all_merged) {
            auto first = initial_words[0] + result.suffix, second = initial_words[1] + result.suffix;
            const auto before = state.counts;
            auto verified = full_check(graph, first, second, state.counts);
            if (verified == -2) { state.counts = before; retain_attempt(state, std::move(attempt)); break; }
            if (verified != -1) throw std::logic_error("generic finder hit failed independent all-mask scalar replay");
            attempt.scalar_verified = true; witness = {first, second};
            state.finder_best_tail_json = "null";
            if (result.shortest_conditional && result.last_tail.found) {
                auto proof = tail_json(result.last_tail, last_coordinates, false);
                proof.pop_back();
                auto before_tail = result.suffix.substr(0, result.exact_tail_prefix_length);
                proof += ",\"chosen_for_best_witness\":true,\"conditional_prefix_words\":["
                    + cli::quote(initial_words[0] + before_tail) + ',' + cli::quote(initial_words[1] + before_tail)
                    + "],\"conditional_tail_suffix\":" + cli::quote(result.exact_tail_suffix)
                    + ",\"shortest_for_initial_pair\":" + (result.shortest_for_initial_pair ? "true" : "false") + '}';
                state.finder_best_tail_json = std::move(proof);
            }
        }
        retain_attempt(state, std::move(attempt));
        const bool improved = options.best_of_seeds && !witness[0].empty()
            && (!previous_witness_length || witness[0].size() < previous_witness_length);
        if (improved) {
            state.finder_viability_json = viability->json();
            ++state.next; save_checkpoint(options, state, config_hash); --state.next;
        }
        if (!witness[0].empty() && (!options.best_of_seeds || witness[0].size() == 1)) { ++state.next; break; }
        if (result.interrupted || interrupted) break;
        if (!improved && options.checkpoint_every && (state.next + 1) % options.checkpoint_every == 0) {
            state.finder_viability_json = viability->json();
            ++state.next; save_checkpoint(options, state, config_hash); --state.next;
        }
    }
    const bool complete = state.next == options.samples || (!witness[0].empty() && (!options.best_of_seeds || witness[0].size() == 1));
    state.finder_viability_json = viability->json();
    if (!complete) save_checkpoint(options, state, config_hash);
    auto text = result_json(options, graph, state, config_hash, witness,
        std::chrono::duration<double>(Clock::now() - started).count(), complete, 0, 0, 0, &permutations);
    if (complete) {
        cli::write(options.out / "result.sha256", cli::sha256(text)); cli::publish(options.out / "result.json", text);
    } else {
        auto path = options.out / ("partial-" + std::to_string(state.next) + ".json");
        if (!fs::exists(path)) cli::publish(path, text);
    }
    std::cout << text << '\n'; return interrupted ? 130 : 0;
}

int run_distribution(const Options& options, const Graph& graph, const std::string& config_hash)
{
    const auto started = Clock::now();
    const auto permutations = permutation_masks(graph);
    auto context = std::make_shared<family1::PairAgreementContext>(graph);
    if (context->permutation_mask_count() != permutations.size())
        throw std::logic_error("distribution context and XOR permutation enumeration disagree");
    Family1FinderState initial{family1::ExactPairAgreement(context, options.first_prefix, options.second_prefix)};
    auto distribution = hardpair::enumerate_window_distribution(initial, options.window_k, options.max_expansions, &interrupted);
    if (distribution.mask_count != context->mask_count()
        || (distribution.complete && distribution.ranked.size() != (std::size_t{1} << options.window_k)))
        throw std::logic_error("invalid exact window distribution");
    auto suffix = distribution.ranked.empty() ? std::string{} : distribution.ranked.front().window;
    if (!initial.remaining_count()) suffix.clear();
    auto pair = initial.pair;
    GuidedAttempt attempt;
    attempt.present = true; attempt.full_scope = true; attempt.full_mask_count = pair.mask_count();
    attempt.first = options.first_prefix; attempt.second = options.second_prefix;
    attempt.suffix = suffix; attempt.trace = {static_cast<unsigned int>(pair.merged_count())};
    attempt.permutation_mismatches = pair.permutation_mismatch_count(); attempt.gate_blocked = attempt.permutation_mismatches != 0;
    for (char input : suffix) { pair = pair.append_common(input == '1'); attempt.trace.push_back(static_cast<unsigned int>(pair.merged_count())); }
    if (pair.mask_count() <= 64) for (std::uint32_t mask = 0; mask < pair.mask_count(); ++mask) attempt.masks.push_back(mask);
    State state; state.guided = true; state.full_guidance = true; state.next = distribution.window_count;
    std::array<std::string, 2> witness;
    if (pair.all_merged()) {
        auto first = options.first_prefix + suffix, second = options.second_prefix + suffix;
        const auto answer = full_check(graph, first, second, state.counts);
        if (answer >= 0) throw std::logic_error("exact distribution hit failed scalar replay");
        if (answer == -1) { witness = {first, second}; attempt.scalar_verified = true; }
    }
    state.best = std::move(attempt);
    auto text = result_json(options, graph, state, config_hash, witness,
        std::chrono::duration<double>(Clock::now() - started).count(), distribution.complete, 0, 0, 0, &permutations);
    text.pop_back(); text += ",\"window_distribution\":" + window_distribution_json(distribution) + '}';
    if (distribution.complete && !interrupted) {
        cli::write(options.out / "result.sha256", cli::sha256(text)); cli::publish(options.out / "result.json", text);
    } else {
        auto path = options.out / ("distribution-partial-" + std::to_string(distribution.expanded_nodes) + ".json");
        if (!fs::exists(path)) cli::publish(path, text);
    }
    std::cout << text << '\n'; return interrupted ? 130 : 0;
}

int run_full_guided(const Options& options, const Graph& graph, const std::string& config_hash)
{
    const auto started = Clock::now();
    const auto permutations = permutation_masks(graph);
    const auto orders = permutation_orders(graph, permutations, options.length - 1);
    auto context = std::make_shared<family1::PairAgreementContext>(graph);
    if (context->permutation_mask_count() != permutations.size())
        throw std::logic_error("XOR and independent exact-context permutation counts disagree");
    auto state = load_checkpoint(options, graph, config_hash);
    state.guided = true; state.full_guidance = true;
    std::array<std::string, 2> witness;
    const auto invocation_end = options.limit_samples ? state.next + std::min(options.samples - state.next, options.limit_samples) : options.samples;
    for (; state.next < invocation_end && !interrupted; ++state.next) {
        const auto initial = guided_prefix(state.next, options, orders);
        auto result = family1::full_suffix_beam(context, initial[0], initial[1],
            options.length - static_cast<unsigned int>(initial[0].size()), options.beam_width, options.lookahead,
            mix(options.seed ^ state.next), &interrupted, 10000);
        if (result.score_trace.empty() || result.score_trace.size() != result.suffix.size() + 1
            || result.score_trace.back() != result.merged_count || result.mask_count != context->mask_count())
            throw std::logic_error("invalid exact full-guidance result");
        ++state.guided_counts.prefix_gates_checked;
        state.guided_counts.prefix_gates_blocked += result.permutation_mismatch_count != 0;
        state.guided_counts.beam_nodes += result.expanded_nodes;
        state.guided_counts.lookahead_nodes += result.lookahead_nodes;
        state.guided_counts.expansion_limits += result.expansion_limit_reached;
        GuidedAttempt attempt;
        attempt.present = true; attempt.full_scope = true; attempt.full_mask_count = result.mask_count;
        attempt.first = initial[0]; attempt.second = initial[1]; attempt.suffix = result.suffix;
        attempt.permutation_mismatches = result.permutation_mismatch_count;
        attempt.gate_blocked = result.permutation_mismatch_count != 0;
        for (auto score : result.score_trace) {
            if (score > result.mask_count) throw std::logic_error("exact guidance score exceeds mask count");
            attempt.trace.push_back(static_cast<unsigned int>(score));
        }
        // Tiny full sets are explicitly listed for independent scalar audits.
        // Larger full sets use the exact implicit integer range [0,2^m).
        if (result.mask_count <= 64)
            for (std::uint32_t mask = 0; mask < result.mask_count; ++mask) attempt.masks.push_back(mask);
        if (result.all_merged) {
            const auto before = state.counts;
            const auto checked = full_check(graph, initial[0] + result.suffix, initial[1] + result.suffix, state.counts);
            if (checked == -2) { state.counts = before; retain_attempt(state, std::move(attempt)); break; }
            if (checked != -1) throw std::logic_error("exact full-guidance collision failed independent scalar replay");
            attempt.scalar_verified = true;
            witness = {initial[0] + result.suffix, initial[1] + result.suffix};
        }
        retain_attempt(state, std::move(attempt));
        if (!witness[0].empty()) { ++state.next; break; }
        if (result.interrupted || interrupted) break;
        if (options.checkpoint_every && (state.next + 1) % options.checkpoint_every == 0) {
            ++state.next; save_checkpoint(options, state, config_hash); --state.next;
        }
    }
    const bool complete = !witness[0].empty() || state.next == options.samples;
    if (!complete) save_checkpoint(options, state, config_hash);
    const auto exact = options.full_agreement ? guided_attempt_json(state.best, graph.size()) : "";
    auto text = result_json(options, graph, state, config_hash, witness,
                            std::chrono::duration<double>(Clock::now() - started).count(), complete, 0, 0, 0, &permutations, exact);
    if (complete) {
        cli::write(options.out / "result.sha256", cli::sha256(text)); cli::publish(options.out / "result.json", text);
    } else {
        auto path = options.out / ("partial-" + std::to_string(state.next) + ".json");
        if (!fs::exists(path)) cli::publish(path, text);
    }
    std::cout << text << '\n'; return interrupted ? 130 : 0;
}

int run_guided(const Options& options, const Graph& graph, const std::string& config_hash)
{
    if (options.full_guidance) return run_full_guided(options, graph, config_hash);
    const auto started = Clock::now();
    const auto permutations = permutation_masks(graph);
    const auto orders = permutation_orders(graph, permutations, options.length - 1);
    auto state = load_checkpoint(options, graph, config_hash);
    if (!state.guided) state.masks = guided_masks(graph, options, permutations);
    state.guided = true;
    Packed packed(graph, state.masks);
    std::array<std::string, 2> witness;
    auto invocation_end = options.limit_samples ? state.next + std::min(options.samples - state.next, options.limit_samples) : options.samples;
    for (; state.next < invocation_end && !interrupted; ++state.next) {
        const auto initial = guided_prefix(state.next, options, orders);
        if (initial[0].empty() || initial[0] == initial[1] || initial[0].size() != initial[1].size()
            || initial[0].size() > options.length) throw std::logic_error("invalid guided prefix pair");
        std::uint64_t mismatches = 0;
        for (auto mask : permutations)
            if (endpoint(graph, mask, initial[0]) != endpoint(graph, mask, initial[1])) ++mismatches;
        ++state.guided_counts.prefix_gates_checked;
        if (mismatches) {
            ++state.guided_counts.prefix_gates_blocked;
            auto left = packed.run(initial[0]), right = packed.run(initial[1]);
            GuidedAttempt attempt;
            attempt.present = true; attempt.gate_blocked = true; attempt.first = initial[0]; attempt.second = initial[1];
            attempt.masks = state.masks; attempt.trace = {agreement(left, right)}; attempt.permutation_mismatches = mismatches;
            retain_attempt(state, std::move(attempt));
            continue;
        }
        // A scalar separator refines the sampled objective, then restarts this
        // promising prefix pair. The exact permutation gate is unchanged.
        for (unsigned int refinement = 0; refinement < 16 && !interrupted; ++refinement) {
            const auto mask_snapshot = state.masks;
            auto left = packed.run(initial[0]), right = packed.run(initial[1]);
            if (state.next < options.self_check) {
                packed.check(left, initial[0]); packed.check(right, initial[1]); state.counts.self_checks += 2;
            }
            std::vector<BeamNode> beam{{left, right, "", {agreement(left, right)}, 0, 0}};
            bool refined = false;
            const auto suffix_limit = options.length - static_cast<unsigned int>(initial[0].size());
            for (unsigned int depth = 0; !interrupted; ++depth) {
                const auto& top = beam.front();
                GuidedAttempt attempt;
                attempt.present = true; attempt.first = initial[0]; attempt.second = initial[1];
                attempt.suffix = top.suffix; attempt.trace = top.trace; attempt.masks = mask_snapshot;
                if (top.trace.back() == mask_snapshot.size()) {
                    ++state.counts.projected_equalities;
                    auto counts_before = state.counts;
                    const auto answer = full_check(graph, initial[0] + top.suffix, initial[1] + top.suffix, state.counts);
                    if (answer == -2) { state.counts = counts_before; retain_attempt(state, std::move(attempt)); break; }
                    if (answer == -1) {
                        attempt.scalar_verified = true; retain_attempt(state, std::move(attempt));
                        witness = {initial[0] + top.suffix, initial[1] + top.suffix}; break;
                    }
                    attempt.first_separator = answer; retain_attempt(state, std::move(attempt));
                    auto mask = static_cast<std::uint32_t>(answer);
                    if (std::find(state.masks.begin(), state.masks.end(), mask) != state.masks.end())
                        throw std::logic_error("guided scalar separator was already sampled");
                    ++state.counts.counterexamples;
                    std::size_t keep = permutations.size() < state.masks.size() ? permutations.size() : state.masks.size() / 2;
                    auto slot = keep + (state.counts.counterexamples - 1) % (state.masks.size() - keep);
                    state.masks[static_cast<std::size_t>(slot)] = mask;
                    packed = Packed(graph, state.masks); ++state.counts.cache_resets; refined = true; break;
                }
                if (depth == suffix_limit) { retain_attempt(state, std::move(attempt)); break; }
                std::vector<BeamNode> expanded;
                for (const auto& node : beam) for (unsigned int input = 0; input < 2; ++input) {
                    BeamNode child;
                    child.left = packed.step(node.left, input); child.right = packed.step(node.right, input);
                    child.suffix = node.suffix + static_cast<char>('0' + input); child.trace = node.trace;
                    const auto score = agreement(child.left, child.right);
                    if (score < child.trace.back()) throw std::logic_error("sampled common-suffix agreement decreased");
                    child.trace.push_back(score); ++state.guided_counts.beam_nodes;
                    if (std::any_of(expanded.begin(), expanded.end(), [&](const auto& prior) {
                        return prior.left == child.left && prior.right == child.right;
                    })) continue;
                    auto ahead = std::min(options.lookahead ? options.lookahead - 1 : 0, suffix_limit - depth - 1);
                    child.lookahead_score = forecast(packed, child.left, child.right, ahead,
                                                     static_cast<unsigned int>(mask_snapshot.size()), state.guided_counts);
                    child.tie = mix(profile_hash(child.left, 64) ^ std::rotl(profile_hash(child.right, 64), 19) ^ mix(state.next));
                    expanded.push_back(std::move(child));
                }
                std::sort(expanded.begin(), expanded.end(), [](const auto& a, const auto& b) {
                    if (a.lookahead_score != b.lookahead_score) return a.lookahead_score > b.lookahead_score;
                    if (a.trace.back() != b.trace.back()) return a.trace.back() > b.trace.back();
                    if (a.tie != b.tie) return a.tie < b.tie;
                    return a.suffix < b.suffix;
                });
                if (expanded.size() > options.beam_width) expanded.resize(options.beam_width);
                if (expanded.empty()) throw std::logic_error("guided beam unexpectedly empty");
                beam = std::move(expanded);
            }
            if (!witness[0].empty() || !refined || interrupted) break;
        }
        if (!witness[0].empty()) { ++state.next; break; }
        if (options.checkpoint_every && (state.next + 1) % options.checkpoint_every == 0) {
            ++state.next; save_checkpoint(options, state, config_hash); --state.next;
        }
    }
    const bool complete = !witness[0].empty() || state.next == options.samples;
    if (!complete) save_checkpoint(options, state, config_hash);
    const auto exact = options.full_agreement ? exact_trace_json(graph, state.best, permutations.size()) : "";
    auto text = result_json(options, graph, state, config_hash, witness,
                            std::chrono::duration<double>(Clock::now() - started).count(), complete, 0, 0, 0, &permutations, exact);
    if (complete) {
        cli::write(options.out / "result.sha256", cli::sha256(text)); cli::publish(options.out / "result.json", text);
    } else {
        auto path = options.out / ("partial-" + std::to_string(state.next) + ".json");
        if (!fs::exists(path)) cli::publish(path, text);
    }
    std::cout << text << '\n'; return interrupted ? 130 : 0;
}

int run(const Options& options, const Graph& graph, const std::string& config_hash)
{
    if (options.mode == "finder") return run_finder(options, graph, config_hash);
    if (options.mode == "distribution") return run_distribution(options, graph, config_hash);
    if (options.mode == "guided") return run_guided(options, graph, config_hash);
    auto start = Clock::now(); State state = load_checkpoint(options, graph, config_hash);
    auto masks = state.masks;
    Packed packed(graph, masks);
    if (options.mode == "benchmark") {
        std::vector<Profile> profiles; profiles.reserve(static_cast<std::size_t>(options.samples));
        auto packed_start = Clock::now(); std::uint64_t packed_checksum = 0;
        for (std::uint64_t i = 0; i < options.samples; ++i) {
            profiles.push_back(packed.run(random_word(i, options)));
            packed_checksum ^= mix(profile_hash(profiles.back(), 64) + i);
        }
        auto packed_seconds = std::chrono::duration<double>(Clock::now() - packed_start).count();
        auto scalar_start = Clock::now(); std::uint64_t checksum = 0;
        for (std::uint64_t i = 0; i < options.samples; ++i) {
            packed.check(profiles[static_cast<std::size_t>(i)], random_word(i, options));
            checksum ^= mix(profile_hash(profiles[static_cast<std::size_t>(i)], 64) + i);
        }
        auto scalar_seconds = std::chrono::duration<double>(Clock::now() - scalar_start).count();
        if (checksum != packed_checksum) throw std::logic_error("benchmark checksums disagree");
        state.next = options.samples; state.counts.self_checks = options.samples;
        auto text = result_json(options, graph, state, config_hash, {}, std::chrono::duration<double>(Clock::now() - start).count(),
                                true, packed_seconds, scalar_seconds, checksum);
        cli::write(options.out / "result.sha256", cli::sha256(text)); cli::publish(options.out / "result.json", text);
        std::cout << text << '\n'; return 0;
    }
    std::vector<Entry> cache;
    std::unordered_map<std::uint64_t, std::vector<std::size_t>> lookup;
    auto insert = [&](std::uint64_t index, const Profile& profile) {
        auto key = profile_hash(profile, options.hash_bits);
        lookup[key].push_back(cache.size()); cache.push_back({index, profile});
    };
    for (auto index : state.cache_indices) insert(index, packed.run(random_word(index, options)));
    state.cache_indices.clear();
    auto checkpoint = [&] {
        state.cache_indices.clear(); for (const auto& entry : cache) state.cache_indices.push_back(entry.index);
        save_checkpoint(options, state, config_hash);
    };
    const auto invocation_end = options.limit_samples ? state.next + std::min(options.samples - state.next, options.limit_samples) : options.samples;
    std::array<std::string, 2> witness;
    for (; state.next < invocation_end && !interrupted; ++state.next) {
        const auto counts_before = state.counts;
        std::string first, second; Profile left, right;
        const bool structured = options.mode == "commutator" || (options.mode == "mixed" && !(state.next & 1));
        bool equality = false, duplicate_word = false;
        if (structured) {
            auto candidate = commutator(state.next, options); first = candidate.first; second = candidate.second;
            if (options.length == 1) { left = packed.run(first); right = packed.run(second); }
            else {
                auto prefix = packed.run(candidate.prefix);
                left = packed.suffix(packed.suffix(packed.suffix(prefix, candidate.a), candidate.b), candidate.suffix);
                right = packed.suffix(packed.suffix(packed.suffix(prefix, candidate.b), candidate.a), candidate.suffix);
            }
            if (state.next < options.self_check) { packed.check(left, first); packed.check(right, second); state.counts.self_checks += 2; }
            if (profile_hash(left, options.hash_bits) == profile_hash(right, options.hash_bits)) {
                ++state.counts.hash_matches; equality = left == right;
            }
        } else {
            second = random_word(state.next, options); right = packed.run(second);
            if (state.next < options.self_check) { packed.check(right, second); ++state.counts.self_checks; }
            auto bucket = lookup.find(profile_hash(right, options.hash_bits));
            if (bucket != lookup.end()) for (auto slot : bucket->second) {
                ++state.counts.hash_matches;
                if (cache[slot].profile != right) continue;
                first = random_word(cache[slot].index, options);
                if (first != second) equality = true;
                else duplicate_word = true;
                break;
            }
        }
        if (equality) {
            ++state.counts.projected_equalities;
            auto separating = full_check(graph, first, second, state.counts);
            if (separating == -2) { state.counts = counts_before; break; }
            if (separating == -1) { witness = {first, second}; ++state.next; break; }
            ++state.counts.counterexamples;
            auto mask = static_cast<std::uint32_t>(separating);
            if (std::find(masks.begin(), masks.end(), mask) != masks.end()) throw std::logic_error("scalar separator was already a sampled mask");
            const auto keep = masks.size() > 2 ? 2 : 0;
            const auto slot = keep + (state.counts.counterexamples - 1) % (masks.size() - keep);
            masks[static_cast<std::size_t>(slot)] = mask; state.masks = masks;
            packed = Packed(graph, masks); cache.clear(); lookup.clear(); ++state.counts.cache_resets;
            if (!structured) right = packed.run(second);
        }
        if (!structured && !duplicate_word) {
            if (cache.size() >= options.max_profiles) { cache.clear(); lookup.clear(); ++state.counts.cache_resets; }
            insert(state.next, right);
        }
        if (options.checkpoint_every && (state.next + 1) % options.checkpoint_every == 0) {
            ++state.next; checkpoint(); --state.next;
        }
    }
    const bool complete = !witness[0].empty() || state.next == options.samples;
    if (!complete) checkpoint();
    auto text = result_json(options, graph, state, config_hash, witness,
                            std::chrono::duration<double>(Clock::now() - start).count(), complete);
    if (complete) {
        cli::write(options.out / "result.sha256", cli::sha256(text)); cli::publish(options.out / "result.json", text);
    } else {
        auto path = options.out / ("partial-" + std::to_string(state.next) + ".json");
        if (!fs::exists(path)) cli::publish(path, text);
    }
    std::cout << text << '\n'; return interrupted ? 130 : 0;
}
}

int main(int argc, char** argv)
{
    try {
        auto opts = options(argc, argv);
        auto source = Graph::from_key(opts.source_key);
        if (!source.accessible()) throw std::invalid_argument("graph is not root-accessible");
        auto graph = source.canonical(); const auto config = configuration(opts, graph), binding = cli::sha256(config);
        fs::create_directories(opts.out);
        if (opts.resume) {
            if (!fs::exists(opts.out / "run.json") || cli::read(opts.out / "run.json") != config)
                throw std::runtime_error("resume requires identical graph, sampling settings, and seed");
            if (fs::exists(opts.out / "result.json")) {
                auto text = cli::read(opts.out / "result.json");
                if (!fs::exists(opts.out / "result.sha256") || cli::read(opts.out / "result.sha256") != cli::sha256(text))
                    throw std::runtime_error("completed result SHA256 mismatch");
                std::cout << text << '\n'; return 0;
            }
        } else {
            if (!fs::is_empty(opts.out)) throw std::runtime_error("new run requires an empty output directory");
            cli::publish(opts.out / "run.json", config);
        }
        std::signal(SIGINT, stop); std::signal(SIGTERM, stop);
        return run(opts, graph, binding);
    } catch (const std::exception& error) {
        std::cerr << "Family1Sample: " << error.what() << '\n'; return 1;
    }
}

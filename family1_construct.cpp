#include "Family1LargeGraph.h"
#include "Family1CliArtifacts.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;
namespace {
using family1_cli::quote;
using family1_cli::sha256;
using Graph = family1::LargeGraph;
volatile std::sig_atomic_t interrupted = 0;
void stop(int) { interrupted = 1; }

std::uint64_t number(const std::string& text)
{
    if (text.empty() || text.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("expected a nonnegative integer");
    return std::stoull(text);
}

struct Options {
    std::string key;
    fs::path out;
    std::uint64_t materialize_limit = 0;
    bool resume = false;
};

Options options(int argc, char** argv)
{
    Options result;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        if (argument == "--help") {
            std::cout << "Family1Construct --graph FIXED_WIDTH_KEY --out DIR\n"
                " [--materialize-limit N --resume]\n"
                "Constructs distinct equal-length words colliding for ALL static masks.\n"
                "All 2^m masks are enumerated, with 1<=m<=20 and root0 fixed.\n"
                "Outputs three RLE runs per word (including zero-count runs).\n"
                "Full word strings are emitted only when length<=N; default N=0.\n"
                "The universal collision certifies only an upper bound on H(G).\n"
                "Independent modular functional powers verify both endpoints for every mask.\n"
                "New runs require an empty DIR; --resume checks identical settings\n"
                "and reuses an intact completed result.json.\n";
            std::exit(0);
        }
        if (argument == "--resume") { result.resume = true; continue; }
        if (++i >= argc) throw std::invalid_argument("missing option value: " + argument);
        const std::string value = argv[i];
        if (argument == "--graph") result.key = value;
        else if (argument == "--out") result.out = value;
        else if (argument == "--materialize-limit") result.materialize_limit = number(value);
        else throw std::invalid_argument("unknown option: " + argument);
    }
    if (result.key.empty() || result.out.empty()) throw std::invalid_argument("require --graph KEY --out DIR");
    return result;
}

struct Orbit { unsigned int tail, cycle; };

// Construction uses Floyd's algorithm on the ordinary zero-letter transition.
// No word enumeration or product-state table is needed.
Orbit orbit(const std::array<unsigned int, 20>& zero, unsigned int start)
{
    auto slow = zero[start], fast = zero[zero[start]];
    while (slow != fast) { slow = zero[slow]; fast = zero[zero[fast]]; }
    unsigned int tail = 0;
    slow = start;
    while (slow != fast) { slow = zero[slow]; fast = zero[fast]; ++tail; }
    unsigned int cycle = 1;
    fast = zero[slow];
    while (slow != fast) { fast = zero[fast]; ++cycle; }
    return {tail, cycle};
}

void poll(std::uint32_t mask)
{
    if ((mask & 4095U) == 0 && interrupted) throw std::runtime_error("interrupted; no completed constructor certificate");
}

// Independent verifier: retain the visited scalar states and reduce the
// remaining exponent only after observing a repeat. It does not use Floyd's
// orbit data, the constructor's periods, or any state hashes.
unsigned int zero_power(const Graph& graph, std::uint32_t mask, unsigned int state, std::uint64_t exponent)
{
    std::array<int, 20> seen;
    seen.fill(-1);
    unsigned int step = 0;
    while (exponent) {
        if (seen[state] >= 0) {
            exponent %= step - static_cast<unsigned int>(seen[state]);
            break;
        }
        seen[state] = static_cast<int>(step++);
        state = graph.ports[state][(mask >> state) & 1U];
        --exponent;
    }
    while (exponent) { state = graph.ports[state][(mask >> state) & 1U]; --exponent; }
    return state;
}

unsigned int word_endpoint(const Graph& graph, std::uint32_t mask, std::uint64_t prefix, std::uint64_t suffix)
{
    auto state = zero_power(graph, mask, 0, prefix);
    state = graph.ports[state][1U ^ ((mask >> state) & 1U)];
    return zero_power(graph, mask, state, suffix);
}

void rle(std::ostream& output, std::uint64_t prefix, std::uint64_t suffix)
{
    output << "[[\"0\"," << prefix << "],[\"1\",1],[\"0\"," << suffix << "]]";
}

std::string configuration(const Options& options, const Graph& graph)
{
    std::ostringstream output;
    output << "{\"schema\":1,\"method\":\"family1-root-orbit-commutation-v1\""
        << ",\"source_key\":" << quote(options.key) << ",\"source_key_sha256\":" << quote(sha256(options.key))
        << ",\"key\":" << quote(graph.key()) << ",\"canonical_key_sha256\":" << quote(sha256(graph.key()))
        << ",\"m\":" << graph.size() << ",\"materialize_limit\":" << options.materialize_limit << '}';
    return output.str();
}

std::string construct(const Options& options, const Graph& graph, const std::string& config_hash)
{
    const auto started = std::chrono::steady_clock::now();
    const auto m = graph.size(), masks = 1U << m;
    unsigned int A = 0, B = 0;
    std::uint64_t prefix_period = 1, period = 1, generic_period = 1;
    std::set<unsigned int> prefix_cycles, suffix_cycles;
    std::array<unsigned int, 20> zero{};
    std::array<std::uint64_t, 21> prefix_counts{}, suffix_counts{};
    for (unsigned int state = 0; state < m; ++state) zero[state] = graph.ports[state][0];
    for (std::uint32_t index = 0; index < masks; ++index) {
        poll(index);
        const auto mask = index ^ (index >> 1);
        if (index) {
            const auto changed = std::countr_zero(index);
            zero[changed] = graph.ports[changed][(mask >> changed) & 1U];
        }
        const auto shape = orbit(zero, 0);
        A = std::max(A, shape.tail);
        if (prefix_counts[shape.cycle]++ == 0) {
            prefix_cycles.insert(shape.cycle);
            prefix_period = std::lcm(prefix_period, static_cast<std::uint64_t>(shape.cycle));
        }
    }
    period = prefix_period;
    for (unsigned int state = 0; state < m; ++state) zero[state] = graph.ports[state][0];
    for (std::uint32_t index = 0; index < masks; ++index) {
        poll(index);
        const auto mask = index ^ (index >> 1);
        if (index) {
            const auto changed = std::countr_zero(index);
            zero[changed] = graph.ports[changed][(mask >> changed) & 1U];
        }
        unsigned int state = 0;
        for (unsigned int step = 0; step < A; ++step) state = zero[state];
        state = graph.ports[state][1U ^ ((mask >> state) & 1U)];
        const auto shape = orbit(zero, state);
        B = std::max(B, shape.tail);
        if (suffix_counts[shape.cycle]++ == 0) {
            suffix_cycles.insert(shape.cycle);
            period = std::lcm(period, static_cast<std::uint64_t>(shape.cycle));
        }
    }
    for (unsigned int cycle = 1; cycle <= m; ++cycle) generic_period = std::lcm(generic_period, static_cast<std::uint64_t>(cycle));
    const std::uint64_t length = A + B + period + 1;
    // Accessibility lets a static zero-mask follow a simple root path into
    // any directed cycle. Thus root-orbit cycles already contain every cycle
    // length which can appear in the suffix phase.
    if (!period || generic_period % period || A >= m || B >= m || period != prefix_period
        || !std::includes(prefix_cycles.begin(), prefix_cycles.end(), suffix_cycles.begin(), suffix_cycles.end()))
        throw std::logic_error("invalid functional orbit construction");
    const auto construction_seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    for (std::uint32_t mask = 0; mask < masks; ++mask) {
        poll(mask);
        const auto first = word_endpoint(graph, mask, A + period, B);
        const auto second = word_endpoint(graph, mask, A, B + period);
        if (first != second) throw std::logic_error("constructed words fail independent full-mask verification");
    }
    if (interrupted) throw std::runtime_error("interrupted; no completed constructor certificate");
    const auto seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    std::ostringstream output;
    output << "{\"schema\":1,\"method\":\"family1-root-orbit-commutation-v1\""
        << ",\"source_key\":" << quote(options.key) << ",\"source_key_sha256\":" << quote(sha256(options.key))
        << ",\"key\":" << quote(graph.key()) << ",\"canonical_key_sha256\":" << quote(sha256(graph.key()))
        << ",\"config_sha256\":" << quote(config_hash) << ",\"m\":" << m << ",\"canonical_table\":[";
    for (unsigned int state = 0; state < m; ++state) {
        if (state) output << ',';
        output << '[' << graph.ports[state][0] << ',' << graph.ports[state][1] << ']';
    }
    output << "],\"masks_enumerated\":" << masks << ",\"construction_passes\":2,\"construction_mask_order\":\"binary-reflected-gray-code\",\"mask_enumeration_complete\":true"
        << ",\"A\":" << A << ",\"B\":" << B << ",\"P\":" << period << ",\"prefix_period\":" << prefix_period
        << ",\"length\":" << length << ",\"upper_bound\":" << length << ",\"lower_bound\":1,\"merge_length\":null"
        << ",\"word_rle\":[";
    rle(output, A + period, B); output << ','; rle(output, A, B + period);
    output << "],\"word_strings\":";
    if (length <= options.materialize_limit) {
        const auto first = std::string(static_cast<std::size_t>(A + period), '0') + '1' + std::string(B, '0');
        const auto second = std::string(A, '0') + '1' + std::string(static_cast<std::size_t>(B + period), '0');
        output << '[' << quote(first) << ',' << quote(second) << ']';
    } else output << "null";
    output << ",\"materialize_limit\":" << options.materialize_limit << ",\"prefix_cycle_lengths\":[";
    bool comma = false;
    for (auto cycle : prefix_cycles) { if (comma) output << ','; comma = true; output << cycle; }
    output << "],\"suffix_cycle_lengths\":[";
    comma = false;
    for (auto cycle : suffix_cycles) { if (comma) output << ','; comma = true; output << cycle; }
    output << "],\"prefix_cycle_histogram\":{";
    comma = false;
    for (auto cycle : prefix_cycles) { if (comma) output << ','; comma = true; output << quote(std::to_string(cycle)) << ':' << prefix_counts[cycle]; }
    output << "},\"suffix_cycle_histogram\":{";
    comma = false;
    for (auto cycle : suffix_cycles) { if (comma) output << ','; comma = true; output << quote(std::to_string(cycle)) << ':' << suffix_counts[cycle]; }
    output << "},\"generic_construction\":{\"A\":" << m - 1 << ",\"B\":" << m - 1
        << ",\"P\":" << generic_period << ",\"length\":" << generic_period + 2 * (m - 1) + 1
        << ",\"justification\":\"every functional tail has length<=m-1 and every cycle length divides lcm(1,...,m)\"}"
        << ",\"distinct_words\":true,\"one_positions_zero_based\":[" << A + period << ',' << A << ']'
        << ",\"universal_verification\":{\"method\":\"independent-scalar-direct-orbit-modular-powers\""
        << ",\"mask_count\":" << masks << ",\"passed\":true,\"hashes_used_for_endpoint_equality\":false}"
        << ",\"static_masks\":true,\"exact\":false,\"exact_score_certified\":false,\"maximum_value_certified\":false"
        << ",\"maximizing_collection_complete\":false,\"enumeration_complete\":false"
        << ",\"construction_seconds\":" << std::setprecision(17) << construction_seconds << ",\"seconds\":" << seconds << "}\n";
    return output.str();
}
}

int main(int argc, char** argv)
{
    try {
        const auto options_ = options(argc, argv);
        const auto supplied = Graph::from_key(options_.key);
        if (!supplied.accessible()) throw std::invalid_argument("supplied graph is not root-accessible");
        const auto graph = supplied.canonical();
        const auto config = configuration(options_, graph), config_hash = sha256(config);
        fs::create_directories(options_.out);
        const auto run_path = options_.out / "run.json", result_path = options_.out / "result.json";
        if (options_.resume) {
            if (family1_cli::read(run_path) != config + '\n') throw std::runtime_error("resume requires identical graph and materialization settings");
            if (fs::exists(result_path)) {
                const auto result = family1_cli::read(result_path);
                if (family1_cli::read(options_.out / "result.sha256") != sha256(result) + '\n'
                    || result.find("\"config_sha256\":" + quote(config_hash)) == std::string::npos)
                    throw std::runtime_error("completed result integrity/configuration check failed");
                std::cout << result;
                return 0;
            }
        } else {
            if (!fs::is_empty(options_.out)) throw std::runtime_error("new run requires an empty output directory; use --resume");
            family1_cli::publish(run_path, config + '\n');
        }
        std::signal(SIGINT, stop); std::signal(SIGTERM, stop);
        const auto result = construct(options_, graph, config_hash);
        family1_cli::write(options_.out / "result.sha256", sha256(result) + '\n');
        family1_cli::publish(result_path, result);
        std::cout << result;
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Family1Construct: " << error.what() << '\n';
        return 1;
    }
}

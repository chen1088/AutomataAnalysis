#include "Family1Symbolic.h"
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
#include <iterator>
#include <limits>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
namespace {
volatile std::sig_atomic_t interrupted = 0;
void stop(int) { interrupted = 1; }

// SHA-256 is used for provenance/cache integrity, never as a graph identity.
std::string sha256(const std::string& input)
{
    constexpr std::array<std::uint32_t, 64> constants{
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    std::array<std::uint32_t, 8> hash{
        0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    std::vector<unsigned char> bytes(input.begin(), input.end());
    const auto bit_count = static_cast<std::uint64_t>(bytes.size()) * 8;
    bytes.push_back(0x80);
    while (bytes.size() % 64 != 56) bytes.push_back(0);
    for (int shift = 56; shift >= 0; shift -= 8) bytes.push_back(static_cast<unsigned char>(bit_count >> shift));
    for (std::size_t offset = 0; offset < bytes.size(); offset += 64) {
        std::array<std::uint32_t, 64> word{};
        for (unsigned int i = 0; i < 16; ++i)
            for (unsigned int j = 0; j < 4; ++j) word[i] = (word[i] << 8) | bytes[offset + 4 * i + j];
        for (unsigned int i = 16; i < 64; ++i) {
            auto a = word[i - 15], b = word[i - 2];
            word[i] = word[i - 16] + (std::rotr(a, 7) ^ std::rotr(a, 18) ^ (a >> 3))
                + word[i - 7] + (std::rotr(b, 17) ^ std::rotr(b, 19) ^ (b >> 10));
        }
        auto a = hash[0], b = hash[1], c = hash[2], d = hash[3];
        auto e = hash[4], f = hash[5], g = hash[6], h = hash[7];
        for (unsigned int i = 0; i < 64; ++i) {
            auto first = h + (std::rotr(e, 6) ^ std::rotr(e, 11) ^ std::rotr(e, 25))
                + ((e & f) ^ (~e & g)) + constants[i] + word[i];
            auto second = (std::rotr(a, 2) ^ std::rotr(a, 13) ^ std::rotr(a, 22))
                + ((a & b) ^ (a & c) ^ (b & c));
            h = g; g = f; f = e; e = d + first; d = c; c = b; b = a; a = first + second;
        }
        hash[0] += a; hash[1] += b; hash[2] += c; hash[3] += d;
        hash[4] += e; hash[5] += f; hash[6] += g; hash[7] += h;
    }
    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (auto value : hash) output << std::setw(8) << value;
    return output.str();
}

std::string quote(const std::string& value)
{
    std::string result = "\"";
    const char* hex = "0123456789abcdef";
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') { result += '\\'; result += static_cast<char>(c); }
        else if (c < 32) { result += "\\u00"; result += hex[c >> 4]; result += hex[c & 15]; }
        else result += static_cast<char>(c);
    }
    return result + '"';
}

std::uint64_t number(const std::string& value)
{
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("expected a nonnegative integer");
    return std::stoull(value);
}
unsigned int uint_number(const std::string& value)
{
    const auto parsed = number(value);
    if (parsed > std::numeric_limits<unsigned int>::max()) throw std::invalid_argument("integer exceeds supported range");
    return static_cast<unsigned int>(parsed);
}

struct Options {
    std::string source_key;
    fs::path out;
    unsigned int length = 0, projection_masks = 64;
    std::uint32_t mask_seed = 0x46414d31U;
    bool resume = false;
    family1::SymbolicLimits limits;
};

Options options(int argc, char** argv)
{
    Options result;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        if (argument == "--help") {
            std::cout << "Family1Threshold --graph FIXED_WIDTH_KEY --length L --out DIR\n"
                " [--timeout-ms 10000 --solve-timeout-ms 2000 --max-refinements 256]\n"
                " [--projection-masks 64 --mask-seed 1178684721 --resume]\n"
                "Tests ONE positive equal-length layer for ONE root-accessible graph.\n"
                "no_collision proves H>=L+1; collision proves H<=L; unknown proves neither.\n"
                "Masks are static on revisits. All sampled masks are exported.\n"
                "Every positive witness is replayed over all 2^m masks after the SAT query.\n"
                "The timeout bounds the SAT query; independent witness replay is additional.\n"
                "Writes atomic result.json and run.json; new runs require an empty DIR.\n"
                "--resume requires identical settings and reuses an intact completed result.\n"
                "No global maximum or exhaustive graph coverage is asserted.\n";
            std::exit(0);
        }
        if (argument == "--resume") { result.resume = true; continue; }
        if (++i >= argc) throw std::invalid_argument("missing option value: " + argument);
        const std::string value = argv[i];
        if (argument == "--graph") result.source_key = value;
        else if (argument == "--length") result.length = uint_number(value);
        else if (argument == "--out") result.out = value;
        else if (argument == "--timeout-ms") result.limits.timeout_ms = number(value);
        else if (argument == "--solve-timeout-ms") result.limits.solve_timeout_ms = number(value);
        else if (argument == "--max-refinements") result.limits.max_refinements = uint_number(value);
        else if (argument == "--projection-masks") result.projection_masks = uint_number(value);
        else if (argument == "--mask-seed") result.mask_seed = uint_number(value);
        else throw std::invalid_argument("unknown option: " + argument);
    }
    if (result.source_key.empty() || result.out.empty() || !result.length || result.length > 4096
        || !result.limits.timeout_ms || !result.limits.solve_timeout_ms || !result.limits.max_refinements
        || !result.projection_masks || result.projection_masks > 64)
        throw std::invalid_argument("require --graph KEY --length 1..4096 --out DIR, positive SAT budgets, and masks 1..64");
    result.limits.max_length = result.length;
    result.limits.projection_depth = 0;
    result.limits.interrupted = &interrupted;
    return result;
}

std::string configuration(const Options& options, const family1::LargeGraph& graph)
{
    std::ostringstream output;
    output << "{\"schema\":1,\"method\":\"family1-fixed-length-static-mask-cegis-v1\""
        << ",\"source_key\":" << quote(options.source_key) << ",\"source_key_sha256\":" << quote(sha256(options.source_key))
        << ",\"key\":" << quote(graph.key()) << ",\"canonical_key_sha256\":" << quote(sha256(graph.key()))
        << ",\"m\":" << graph.size() << ",\"length\":" << options.length
        << ",\"timeout_ms\":" << options.limits.timeout_ms << ",\"solve_timeout_ms\":" << options.limits.solve_timeout_ms
        << ",\"max_refinements\":" << options.limits.max_refinements << ",\"projection_masks\":" << options.projection_masks
        << ",\"mask_seed\":" << options.mask_seed << '}';
    return output.str();
}

std::string read(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot read " + path.string());
    std::string result((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    if (input.bad()) throw std::runtime_error("failed reading " + path.string());
    return result;
}

void write(const fs::path& path, const std::string& text)
{
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    output << text;
    output.close();
    if (!output) throw std::runtime_error("failed writing " + path.string());
}

void publish(const fs::path& path, const std::string& text)
{
    if (fs::exists(path)) throw std::runtime_error("refusing to overwrite " + path.string());
    const auto temporary = fs::path(path.string() + ".tmp");
    write(temporary, text);
    fs::rename(temporary, path);
}

std::vector<std::uint32_t> initial_masks(unsigned int m, unsigned int requested, std::uint32_t seed)
{
    const auto count = std::min(requested, 1U << m), all = (1U << m) - 1;
    std::vector<std::uint32_t> result;
    if (count == all + 1) {
        for (std::uint32_t mask = 0; mask <= all; ++mask) result.push_back(mask);
    } else {
        result.push_back(0);
        if (count > 1) result.push_back(all);
        std::mt19937 random(seed + m);
        while (result.size() < count) {
            const auto mask = random() & all;
            if (std::find(result.begin(), result.end(), mask) == result.end()) result.push_back(mask);
        }
    }
    return result;
}

unsigned int scalar_endpoint(const family1::LargeGraph& graph, std::uint32_t mask, const std::string& word)
{
    unsigned int state = 0;
    for (auto symbol : word) state = graph.ports[state][(symbol - '0') ^ ((mask >> state) & 1U)];
    return state;
}

std::string decide(const Options& options, const family1::LargeGraph& graph, const std::string& config_hash)
{
    const auto start = std::chrono::steady_clock::now();
    auto samples = initial_masks(graph.size(), options.projection_masks, options.mask_seed);
    auto answer = family1::decide_length(graph, options.length, samples, options.limits);
    std::uint64_t verified_masks = 0;
    if (answer.decision == family1::LengthDecision::collision) {
        if (answer.witness[0] == answer.witness[1]
            || answer.witness[0].size() != options.length || answer.witness[1].size() != options.length)
            throw std::logic_error("SAT returned an invalid equal-length witness");
        for (const auto& word : answer.witness)
            if (word.find_first_not_of("01") != std::string::npos) throw std::logic_error("SAT returned a nonbinary witness");
        for (std::uint32_t mask = 0; mask < (1U << graph.size()); ++mask) {
            if (interrupted) {
                answer.decision = family1::LengthDecision::unknown;
                answer.reason = "interrupted-during-scalar-witness-check";
                break;
            }
            if (scalar_endpoint(graph, mask, answer.witness[0]) != scalar_endpoint(graph, mask, answer.witness[1]))
                throw std::logic_error("symbolic collision fails independent scalar static-mask replay");
            ++verified_masks;
        }
    }
    const bool collision = answer.decision == family1::LengthDecision::collision;
    const bool no_collision = answer.decision == family1::LengthDecision::no_collision;
    const auto seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    std::ostringstream output;
    output << "{\"schema\":1,\"method\":\"family1-fixed-length-static-mask-cegis-v1\""
        << ",\"source_key\":" << quote(options.source_key) << ",\"source_key_sha256\":" << quote(sha256(options.source_key))
        << ",\"key\":" << quote(graph.key()) << ",\"canonical_key_sha256\":" << quote(sha256(graph.key()))
        << ",\"config_sha256\":" << quote(config_hash) << ",\"m\":" << graph.size()
        << ",\"length\":" << options.length << ",\"canonical_table\":[";
    for (unsigned int state = 0; state < graph.size(); ++state) {
        if (state) output << ',';
        output << '[' << graph.ports[state][0] << ',' << graph.ports[state][1] << ']';
    }
    output << "],\"decision\":" << quote(collision ? "collision" : no_collision ? "no_collision" : "unknown")
        << ",\"lower_bound\":" << (no_collision ? options.length + 1 : 1) << ",\"upper_bound\":";
    if (collision) output << options.length; else output << "null";
    output << ",\"witness\":";
    if (collision) output << '[' << quote(answer.witness[0]) << ',' << quote(answer.witness[1]) << ']';
    else output << "null";
    output << ",\"sampled_masks\":[";
    for (std::size_t i = 0; i < samples.size(); ++i) { if (i) output << ','; output << samples[i]; }
    output << "],\"mask_count\":" << samples.size() << ",\"refinements\":" << answer.refinements
        << ",\"scalar_witness_masks_verified\":" << (collision ? verified_masks : 0)
        << ",\"reason\":" << quote(answer.reason) << ",\"seconds\":" << std::setprecision(17) << seconds
        << ",\"static_masks\":true,\"exact_score_certified\":false,\"maximum_value_certified\":false"
        << ",\"maximizing_collection_complete\":false,\"enumeration_complete\":false}\n";
    return output.str();
}
}

int main(int argc, char** argv)
{
    try {
        const auto options_ = options(argc, argv);
        auto supplied = family1::LargeGraph::from_key(options_.source_key);
        if (!supplied.accessible()) throw std::invalid_argument("supplied graph is not root-accessible");
        const auto graph = supplied.canonical();
        const auto config = configuration(options_, graph), config_hash = sha256(config);
        fs::create_directories(options_.out);
        const auto run_path = options_.out / "run.json", result_path = options_.out / "result.json";
        if (options_.resume) {
            if (read(run_path) != config + '\n') throw std::runtime_error("resume requires identical graph and scoring settings");
            if (fs::exists(result_path)) {
                const auto result = read(result_path);
                if (read(options_.out / "result.sha256") != sha256(result) + '\n'
                    || result.find("\"config_sha256\":" + quote(config_hash)) == std::string::npos)
                    throw std::runtime_error("completed result integrity/configuration check failed");
                std::cout << result;
                return 0;
            }
        } else {
            if (!fs::is_empty(options_.out)) throw std::runtime_error("new run requires an empty output directory; use --resume");
            publish(run_path, config + '\n');
        }
        std::signal(SIGINT, stop); std::signal(SIGTERM, stop);
        const auto result = decide(options_, graph, config_hash);
        // result.json is the final publication/commit point. A partially written
        // .tmp is never a certificate; resume can rerun before publication.
        write(options_.out / "result.sha256", sha256(result) + '\n');
        publish(result_path, result);
        std::cout << result;
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Family1Threshold: " << error.what() << '\n';
        return 1;
    }
}

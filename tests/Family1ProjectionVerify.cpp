// Independent replay of a deterministic mask-projection lower-bound certificate.
// This deliberately does not call the production graph parser, bitplane step,
// projection scorer, or SAT solver. Every coordinate is an ordinary byte state.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <new>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Row = std::array<unsigned int, 2>;
using Graph = std::vector<Row>;
using Profile = std::array<unsigned char, 64>;
constexpr std::size_t state_limit = std::size_t{1} << 26;

Graph parse_graph(const std::string& key)
{
    if (key.empty() || key.size() % 4 || key.size() > 80
        || key.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("graph key must contain four decimal digits per state, for 1..20 states");
    Graph graph(key.size() / 4);
    for (std::size_t state = 0; state < graph.size(); ++state) {
        for (unsigned int port = 0; port < 2; ++port) {
            const auto offset = state * 4 + port * 2;
            auto target = static_cast<unsigned int>((key[offset] - '0') * 10 + key[offset + 1] - '0');
            if (target >= graph.size()) throw std::invalid_argument("graph target outside seed");
            graph[state][port] = target;
        }
    }
    // Independent root-accessibility check, including coincident ports and loops.
    std::array<bool, 20> reached{};
    std::vector<unsigned int> pending{0}; reached[0] = true;
    unsigned int count = 1;
    while (!pending.empty()) {
        auto source = pending.back(); pending.pop_back();
        for (auto target : graph[source]) {
            if (!reached[target]) {
                reached[target] = true; ++count; pending.push_back(target);
            }
        }
    }
    if (count != graph.size()) throw std::invalid_argument("graph is not root-accessible");
    return graph;
}

std::vector<std::uint32_t> masks_for(unsigned int size)
{
    // This public deterministic sequence identifies the certificate's projected
    // coordinates. It matches production, while state evolution below is independent.
    const auto all = (std::uint32_t{1} << size) - 1;
    std::vector<std::uint32_t> masks;
    if (size <= 6) {
        for (std::uint32_t value = 0; value <= all; ++value) masks.push_back(value);
    } else {
        masks = {0, all};
        std::mt19937 random(0x46414d31U + size);
        while (masks.size() < 64) {
            const auto value = static_cast<std::uint32_t>(random()) & all;
            if (std::find(masks.begin(), masks.end(), value) == masks.end()) masks.push_back(value);
        }
    }
    return masks;
}

std::uint64_t hash_profile(const Profile& state)
{
    // FNV-1a over all endpoint bytes, unrelated to production's bitplane hash.
    std::uint64_t result = 14695981039346656037ULL;
    for (auto endpoint : state) {
        result ^= endpoint;
        result *= 1099511628211ULL;
    }
    return result;
}

std::string word(std::uint32_t index, unsigned int length)
{
    std::string result(length, '0');
    for (unsigned int i = 0; i < length; ++i) {
        result[length - i - 1] = static_cast<char>('0' + (index & 1));
        index >>= 1;
    }
    return result;
}

unsigned int parse_depth(const std::string& value)
{
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("depth must be an integer in 0..26");
    const auto parsed = std::stoull(value);
    if (parsed > 26) throw std::invalid_argument("depth must be in 0..26 (at most 2^26 stored states)");
    return static_cast<unsigned int>(parsed);
}

int verify(const std::string& key, unsigned int requested_depth)
{
    const auto graph = parse_graph(key);
    const auto masks = masks_for(static_cast<unsigned int>(graph.size()));
    const auto started = std::chrono::steady_clock::now();
    std::vector<Profile> layer(1); // Every realization starts in root zero.
    for (unsigned int depth = 1; depth <= requested_depth; ++depth) {
        const auto count = layer.size() * 2;
        if (count > state_limit) throw std::length_error("independent replay exceeds 2^26 state guard");
        std::vector<Profile> next;
        next.reserve(count);
        std::size_t slots = 2;
        while (slots < count * 2) slots *= 2;
        constexpr auto vacant = std::numeric_limits<std::uint32_t>::max();
        std::vector<std::uint32_t> index(slots, vacant); // Fresh at every length.
        for (std::uint32_t number = 0; number < count; ++number) {
            Profile state{};
            const auto& previous = layer[number / 2];
            const auto input = number & 1;
            for (std::size_t coordinate = 0; coordinate < masks.size(); ++coordinate) {
                const auto source = previous[coordinate];
                const auto static_bit = (masks[coordinate] >> source) & 1;
                state[coordinate] = static_cast<unsigned char>(graph[source][input ^ static_bit]);
            }
            auto slot = hash_profile(state) & (slots - 1);
            // A hash match is never sufficient: compare the complete byte vector.
            while (index[slot] != vacant && next[index[slot]] != state) slot = (slot + 1) & (slots - 1);
            if (index[slot] != vacant) {
                std::cout << "{\"status\":\"projected-collision\",\"m\":" << graph.size()
                    << ",\"mask_count\":" << masks.size() << ",\"first_collision_depth\":" << depth
                    << ",\"completed_depth\":" << depth - 1 << ",\"certified_lower_bound\":" << depth
                    << ",\"witness\":[\"" << word(index[slot], depth) << "\",\"" << word(number, depth)
                    << "\"],\"full_family_collision_claimed\":false}\n";
                return 2;
            }
            index[slot] = static_cast<std::uint32_t>(next.size());
            next.push_back(state);
        }
        layer = std::move(next);
        std::cout << "{\"completed_depth\":" << depth << ",\"distinct_endpoint_vectors\":" << layer.size() << "}\n";
    }
    const auto seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    std::cout << "{\"status\":\"verified\",\"m\":" << graph.size() << ",\"mask_count\":" << masks.size()
        << ",\"completed_depth\":" << requested_depth << ",\"certified_lower_bound\":" << requested_depth + 1
        << ",\"first_collision_depth\":null,\"key\":\"" << key << "\",\"seconds\":" << seconds << "}\n";
    return 0;
}
}

int main(int argc, char** argv)
{
    try {
        std::string key;
        unsigned int depth = 0;
        bool have_depth = false;
        for (int i = 1; i < argc; ++i) {
            const std::string option = argv[i];
            if (option == "--help") {
                std::cout << "Family1ProjectionVerify --graph FIXED_WIDTH_KEY --depth N\n"
                    "Independently replays static-mask endpoint vectors; depth 0..26.\n"
                    "Exit 0 proves H>=N+1; exit 2 reports the first projected collision.\n"
                    "At most 2^26 profiles are stored (peak memory below 7 GiB).\n";
                return 0;
            }
            if (++i >= argc) throw std::invalid_argument("missing option value");
            if (option == "--graph") key = argv[i];
            else if (option == "--depth") { depth = parse_depth(argv[i]); have_depth = true; }
            else throw std::invalid_argument("unknown option: " + option);
        }
        if (key.empty() || !have_depth) throw std::invalid_argument("require --graph FIXED_WIDTH_KEY and --depth N");
        return verify(key, depth);
    } catch (const std::bad_alloc&) {
        std::cerr << "Independent projection replay allocation failed; no completed certificate is claimed\n";
        return 3;
    } catch (const std::exception& error) {
        std::cerr << "Family1ProjectionVerify: " << error.what() << '\n';
        return 1;
    }
}

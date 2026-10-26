#include "Family1Search.h"
#include <algorithm>
#include <limits>
#include <new>
#include <stdexcept>
#include <vector>

namespace family1 {
Product::Product(const Family1Graph& graph) : size_(graph.size)
{
    const unsigned int masks = 1U << size_;
    for (unsigned int s = 0; s < size_; ++s) {
        for (unsigned int mask = 0; mask < masks; ++mask) {
            for (unsigned int input = 0; input < 2; ++input) {
                auto target = graph.ports[s][input ^ ((mask >> s) & 1)];
                for (unsigned int p = 0; p < 3; ++p)
                    if (target & (1U << p)) destinations_[input][s][p] |= std::uint64_t{1} << mask;
            }
        }
    }
}
Profile Product::step(const Profile& state, bool input) const
{
    Profile result;
    for (unsigned int s = 0; s < size_; ++s) {
        auto at = (s & 1 ? state.planes[0] : ~state.planes[0])
                & (s & 2 ? state.planes[1] : ~state.planes[1])
                & (s & 4 ? state.planes[2] : ~state.planes[2]);
        // Destination masks contain bits only for real family coordinates.
        result.planes[0] |= at & destinations_[input][s][0];
        result.planes[1] |= at & destinations_[input][s][1];
        result.planes[2] |= at & destinations_[input][s][2];
    }
    return result;
}
Profile Product::evaluate(const std::string& word) const
{
    Profile state;
    for (char c : word) {
        if (c != '0' && c != '1') throw std::invalid_argument("nonbinary word");
        state = step(state, c == '1');
    }
    return state;
}
unsigned int Product::endpoint(const Profile& state, unsigned int mask) const
{
    if (mask >= (1U << size_)) throw std::out_of_range("mask outside family");
    unsigned int result = 0;
    for (unsigned int p = 0; p < 3; ++p) result |= ((state.planes[p] >> mask) & 1) << p;
    return result;
}
namespace {
std::uint64_t hash(const Profile& profile)
{
    std::uint64_t result = 0x9e3779b97f4a7c15ULL;
    for (auto value : profile.planes) {
        value ^= value >> 30; value *= 0xbf58476d1ce4e5b9ULL;
        value ^= value >> 27; value *= 0x94d049bb133111ebULL;
        result ^= (value ^ (value >> 31)) + (result << 6) + (result >> 2);
    }
    return result;
}
std::string word(std::uint64_t index, unsigned int depth)
{
    std::string result(depth, '0');
    for (unsigned int i = 0; i < depth; ++i) {
        result[depth - 1 - i] = static_cast<char>('0' + (index & 1)); index >>= 1;
    }
    return result;
}
}
Score score(const Family1Graph& graph, const Limits& limits)
{
    if (limits.depth > 31 || limits.max_layer_states == 0 || limits.max_layer_states > (1ULL << 31))
        throw std::invalid_argument("depth must be <=31 and layer budget in 1..2^31");
    Score result;
    Product product(graph);
    try {
        std::vector<Profile> layer(1);
        for (unsigned int depth = 1; depth <= limits.depth; ++depth) {
            // Before the first collision, indices ARE the lexicographic word
            // numbers: all 2^(depth-1) previous words remain distinct.
            const auto capacity = static_cast<std::size_t>(std::min<std::uint64_t>(layer.size() * 2ULL, limits.max_layer_states));
            std::vector<Profile> next;
            next.reserve(capacity);
            std::size_t table_size = 2;
            while (table_size < capacity * 2) table_size *= 2;
            constexpr auto empty = std::numeric_limits<std::uint32_t>::max();
            std::vector<std::uint32_t> table(table_size, empty);
            for (std::size_t i = 0; i < layer.size() * 2; ++i) {
                if ((i & 4095) == 0 && limits.interrupted && *limits.interrupted) {
                    result.reason = "interrupted"; return result;
                }
                auto state = product.step(layer[i / 2], (i & 1) != 0);
                auto slot = (limits.force_hash_collisions ? 0 : hash(state)) & (table_size - 1);
                while (table[slot] != empty && !(next[table[slot]] == state)) slot = (slot + 1) & (table_size - 1);
                if (table[slot] != empty) {
                    result.status = "exact";
                    result.merge_length = result.lower_bound = depth;
                    result.witness = {word(table[slot], depth), word(i, depth)};
                    return result;
                }
                if (next.size() == capacity) {
                    result.reason = "max-layer-states"; return result;
                }
                table[slot] = static_cast<std::uint32_t>(next.size());
                next.push_back(state);
            }
            layer = std::move(next);
            result.lower_bound = depth + 1;
        }
        result.status = "depth-capped";
        result.reason = "depth";
    } catch (const std::bad_alloc&) { result.reason = "allocation-failed"; }
    return result;
}
}

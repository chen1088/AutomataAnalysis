#include "Family1LayerSearch.h"
#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <limits>
#include <memory>
#include <new>
#include <stdexcept>
#include <type_traits>

namespace family1 {
namespace {
using Clock = std::chrono::steady_clock;
using Profile = std::array<std::array<std::uint64_t, 2>, 7>;
using Table = std::array<std::array<unsigned int, 2>, 7>;
struct Entry { std::uint64_t hash, index; };
std::uint64_t radix_key(std::uint64_t value) { return value; }
std::uint64_t radix_key(const Entry& value) { return value.hash; }
constexpr std::uint64_t patterns[] = {0xaaaaaaaaaaaaaaaaULL, 0xccccccccccccccccULL,
    0xf0f0f0f0f0f0f0f0ULL, 0xff00ff00ff00ff00ULL,
    0xffff0000ffff0000ULL, 0xffffffff00000000ULL};

std::uint64_t reverse(std::uint64_t value)
{
    value = ((value >> 1) & 0x5555555555555555ULL) | ((value & 0x5555555555555555ULL) << 1);
    value = ((value >> 2) & 0x3333333333333333ULL) | ((value & 0x3333333333333333ULL) << 2);
    value = ((value >> 4) & 0x0f0f0f0f0f0f0f0fULL) | ((value & 0x0f0f0f0f0f0f0f0fULL) << 4);
    return std::byteswap(value);
}
Profile step(const Table& table, const Profile& source, bool input)
{
    Profile result{};
    for (unsigned int state = 0; state < 7; ++state)
        for (unsigned int block = 0; block < 2; ++block) {
            const auto sigma = state < 6 ? patterns[state] : block ? ~std::uint64_t{0} : 0;
            const auto one = input ? ~sigma : sigma;
            result[table[state][0]][block] |= source[state][block] & ~one;
            result[table[state][1]][block] |= source[state][block] & one;
        }
    return result;
}
std::uint64_t quotient_hash(const Profile& profile)
{
    // Transition propagation is cheaper in one-hot form. Fingerprinting uses
    // its lossless three-bit endpoint encoding instead of hashing seven rows.
    // T complements every mask coordinate: it swaps the two 64-mask blocks
    // and reverses their bits. Thus the two halves below exchange under T.
    // Combining their sorted hashes is exactly T-invariant and hashes each
    // endpoint plane only once, rather than hashing both orientations fully.
    // Fingerprint matches still require the complete-state checks below.
    const auto mix = [](std::uint64_t value) {
        value ^= value >> 30; value *= 0xbf58476d1ce4e5b9ULL;
        value ^= value >> 27; value *= 0x94d049bb133111ebULL;
        return value ^ (value >> 31);
    };
    const auto half = [&](std::uint64_t first, std::uint64_t second, std::uint64_t third) {
        return mix(first + 0x9e3779b97f4a7c15ULL)
            ^ std::rotl(mix(second + 0x3c6ef372fe94f82aULL), 21)
            ^ std::rotl(mix(third + 0xdaa66d2c7ddef83fULL), 42);
    };
    const auto first = half(profile[1][0] | profile[3][0] | profile[5][0],
        profile[2][0] | profile[3][0] | profile[6][0],
        profile[4][0] | profile[5][0] | profile[6][0]);
    const auto second = half(reverse(profile[1][1] | profile[3][1] | profile[5][1]),
        reverse(profile[2][1] | profile[3][1] | profile[6][1]),
        reverse(profile[4][1] | profile[5][1] | profile[6][1]));
    return mix(std::min(first, second) ^ std::rotl(std::max(first, second), 29)
        ^ 0x9e3779b97f4a7c15ULL);
}
bool complemented_equal(const Profile& first, const Profile& second)
{
    for (unsigned int state = 0; state < 7; ++state)
        if (first[state][0] != reverse(second[state][1]) || first[state][1] != reverse(second[state][0])) return false;
    return true;
}
std::string word(std::uint64_t index, unsigned int depth)
{
    std::string result(depth, '0');
    for (unsigned int bit = 0; bit < depth; ++bit) {
        result[depth - bit - 1] += index & 1;
        index >>= 1;
    }
    return result;
}
std::string complement(std::string word)
{
    for (auto& c : word) c = c == '0' ? '1' : '0';
    return word;
}
template<class Value, class Check>
void radix(Value* hashes, std::uint64_t begin, std::uint64_t end,
    unsigned int shift, const Check& check)
{
    check();
    if (end - begin < 64) {
        std::sort(hashes + begin, hashes + end,
            [](const auto& a, const auto& b) { return radix_key(a) < radix_key(b); });
        return;
    }
    std::array<std::uint64_t, 256> count{}, start{}, next{};
    for (auto index = begin; index < end; ++index) {
        if ((index & 65535) == 0) check();
        ++count[(radix_key(hashes[index]) >> shift) & 255];
    }
    auto sum = begin;
    for (unsigned int bucket = 0; bucket < 256; ++bucket) {
        start[bucket] = next[bucket] = sum;
        sum += count[bucket];
    }
    std::uint64_t moved = 0;
    for (unsigned int bucket = 0; bucket < 256; ++bucket) {
        const auto stop = start[bucket] + count[bucket];
        while (next[bucket] < stop) {
            if ((moved++ & 65535) == 0) check();
            const auto target = (radix_key(hashes[next[bucket]]) >> shift) & 255;
            if (target == bucket) ++next[bucket];
            else std::swap(hashes[next[bucket]], hashes[next[target]++]);
        }
    }
    if (shift)
        for (unsigned int bucket = 0; bucket < 256; ++bucket)
            if (count[bucket] > 1) radix(hashes, start[bucket], start[bucket] + count[bucket], shift - 8, check);
}
struct ResourceStop { std::string reason; };

Profile evaluate(const Table& table, std::uint64_t index, unsigned int depth)
{
    Profile result{};
    result[0] = {~std::uint64_t{0}, ~std::uint64_t{0}};
    while (depth) {
        --depth;
        result = step(table, result, ((index >> depth) & 1) != 0);
    }
    return result;
}
template<bool Packed, class Check>
bool indexed_search(const Table& table, const LayerLimits& limits, LayerScore& result, const Check& check)
{
    using Stored = std::conditional_t<Packed, std::uint64_t, Entry>;
    const auto count = 1ULL << (limits.depth - 1);
    const auto index_bits = limits.depth - 1;
    const auto index_mask = (1ULL << index_bits) - 1;
    const auto group_key = [&](const Stored& entry) -> std::uint64_t {
        if constexpr (Packed) return entry >> index_bits;
        else return entry.hash;
    };
    const auto word_index = [&](const Stored& entry) -> std::uint64_t {
        if constexpr (Packed) return entry & index_mask;
        else return entry.index;
    };
    constexpr std::uint64_t fixed_bytes = sizeof(Profile) * 36 + sizeof(Table)
        + 8 * 3 * sizeof(std::array<std::uint64_t, 256>);
    const auto entry_bytes = count * sizeof(Stored);
    if (fixed_bytes > limits.max_working_bytes || entry_bytes > limits.max_working_bytes - fixed_bytes)
        throw ResourceStop{"max-working-bytes"};
    std::unique_ptr<Stored[]> entries(new Stored[static_cast<std::size_t>(count)]);
    result.peak_working_bytes = fixed_bytes + entry_bytes;
    std::array<Profile, 34> stack{};
    stack[0][0] = {~std::uint64_t{0}, ~std::uint64_t{0}};
    stack[1] = step(table, stack[0], false);
    const auto visit = [&](auto&& self, unsigned int level, std::uint64_t index) -> bool {
        if (level == limits.depth) {
            if ((result.generated_representatives & 65535) == 0) check();
            ++result.generated_representatives;
            const auto& profile = stack[level];
            if (complemented_equal(profile, profile)) {
                result.witness = {word(index, limits.depth), complement(word(index, limits.depth))};
                return false;
            }
            const auto fingerprint = limits.force_hash_collisions ? 0
                : quotient_hash(profile);
            if constexpr (Packed) entries[index] = (fingerprint << index_bits) | index;
            else entries[index] = {fingerprint, index};
            return true;
        }
        stack[level + 1] = step(table, stack[level], false);
        if (!self(self, level + 1, index * 2)) return false;
        stack[level + 1] = step(table, stack[level], true);
        return self(self, level + 1, index * 2 + 1);
    };
    if (!visit(visit, 1, 0)) return false;
    radix(entries.get(), 0, count, 56, check);
    for (std::uint64_t begin = 0; begin < count;) {
        if ((begin & 65535) == 0) check();
        auto end = begin + 1;
        while (end < count && group_key(entries[end]) == group_key(entries[begin])) {
            if ((end & 65535) == 0) check();
            ++end;
        }
        if (end > begin + 1) {
            for (auto index = begin + 1; index < end; ++index) {
                check();
                const auto current_index = word_index(entries[index]);
                const auto current = evaluate(table, current_index, limits.depth);
                for (auto old = begin; old < index; ++old) {
                    if ((result.hash_matches_replayed++ & 4095) == 0) check();
                    const auto previous_index = word_index(entries[old]);
                    const auto previous = evaluate(table, previous_index, limits.depth);
                    if (current == previous) {
                        result.witness = {word(previous_index, limits.depth), word(current_index, limits.depth)};
                        return false;
                    }
                    if (complemented_equal(current, previous)) {
                        result.witness = {word(previous_index, limits.depth), complement(word(current_index, limits.depth))};
                        return false;
                    }
                }
            }
        }
        begin = end;
    }
    return true;
}
}

LayerScore search_layer(const LargeGraph& graph, const LayerLimits& limits)
{
    graph.validate();
    if (graph.size() != 7 || limits.depth > 33 || !limits.max_layer_states || !limits.max_working_bytes)
        throw std::invalid_argument("single-layer search requires seven states, depth0..33 and positive resource caps");
    const auto started = Clock::now();
    LayerScore result;
    const auto finish = [&]() {
        result.seconds = std::chrono::duration<double>(Clock::now() - started).count();
        return result;
    };
    const auto check = [&]() {
        if (limits.interrupted && *limits.interrupted) throw ResourceStop{"interrupted"};
        if (limits.timeout_ms && std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - started).count()
            >= limits.timeout_ms) throw ResourceStop{"timeout"};
    };
    try {
        check();
        if (!limits.depth) { result.status = "collision-free"; return finish(); }
        const auto all_words = 1ULL << limits.depth;
        if (all_words > limits.max_layer_states) throw ResourceStop{"max-layer-states"};
        if (limits.retain_word_indices) {
            Table table{};
            std::copy(graph.ports.begin(), graph.ports.end(), table.begin());
            const bool free = limits.pack_word_indices && limits.depth <= 27
                ? indexed_search<true>(table, limits, result, check)
                : indexed_search<false>(table, limits, result, check);
            if (free) {
                result.status = "collision-free"; result.lower_bound = limits.depth + 1;
            } else { result.status = "collision"; result.upper_bound = limits.depth; }
            return finish();
        }
        const auto count = all_words / 2;
        // Account all array payload: DFS stack, copied table, worst-case eight
        // radix frames and any complete profiles retained during hash replay.
        constexpr std::uint64_t fixed_bytes = sizeof(Profile) * 34 + sizeof(Table)
            + 8 * 3 * sizeof(std::array<std::uint64_t, 256>);
        const auto hash_bytes = count * sizeof(std::uint64_t);
        if (fixed_bytes > limits.max_working_bytes || hash_bytes > limits.max_working_bytes - fixed_bytes)
            throw ResourceStop{"max-working-bytes"};
        const auto base_bytes = fixed_bytes + hash_bytes;
        std::unique_ptr<std::uint64_t[]> hashes(new std::uint64_t[static_cast<std::size_t>(count)]);
        result.peak_working_bytes = base_bytes;
        Table table{};
        std::copy(graph.ports.begin(), graph.ports.end(), table.begin());
        std::array<Profile, 34> stack{};
        stack[0][0] = {~std::uint64_t{0}, ~std::uint64_t{0}};
        stack[1] = step(table, stack[0], false);
        const auto visit = [&](auto&& self, unsigned int level, std::uint64_t index, auto&& leaf) -> bool {
            if (level == limits.depth) return leaf(stack[level], index);
            stack[level + 1] = step(table, stack[level], false);
            if (!self(self, level + 1, index * 2, leaf)) return false;
            stack[level + 1] = step(table, stack[level], true);
            return self(self, level + 1, index * 2 + 1, leaf);
        };
        const auto fingerprint = [&](const Profile& profile) {
            return limits.force_hash_collisions ? 0 : quotient_hash(profile);
        };
        const bool generated = visit(visit, 1, 0, [&](const Profile& profile, std::uint64_t index) {
            if ((result.generated_representatives & 65535) == 0) check();
            ++result.generated_representatives;
            if (complemented_equal(profile, profile)) {
                result.witness = {word(index, limits.depth), complement(word(index, limits.depth))};
                return false;
            }
            hashes[index] = fingerprint(profile);
            return true;
        });
        if (!generated) {
            result.status = "collision"; result.upper_bound = limits.depth; return finish();
        }
        radix(hashes.get(), 0, count, 56, check);
        for (std::uint64_t begin = 0; begin < count;) {
            if ((begin & 65535) == 0) check();
            auto end = begin + 1;
            while (end < count && hashes[end] == hashes[begin]) {
                if ((end & 65535) == 0) check();
                ++end;
            }
            if (end > begin + 1) {
                struct Seen { Profile profile; std::uint64_t index; };
                const auto capacity = std::min<std::uint64_t>(end - begin,
                    (limits.max_working_bytes - base_bytes) / sizeof(Seen));
                if (!capacity) throw ResourceStop{"max-working-bytes-hash-replay"};
                std::unique_ptr<Seen[]> seen(new Seen[static_cast<std::size_t>(capacity)]);
                result.peak_working_bytes = std::max(result.peak_working_bytes, base_bytes + capacity * sizeof(Seen));
                std::uint64_t seen_count = 0, replayed = 0;
                const auto wanted = hashes[begin];
                const bool checked = visit(visit, 1, 0, [&](const Profile& profile, std::uint64_t index) {
                    if ((replayed++ & 65535) == 0) check();
                    if (fingerprint(profile) != wanted) return true;
                    for (std::uint64_t old = 0; old < seen_count; ++old) {
                        ++result.hash_matches_replayed;
                        if (profile == seen[old].profile) {
                            result.witness = {word(seen[old].index, limits.depth), word(index, limits.depth)};
                            return false;
                        }
                        if (complemented_equal(profile, seen[old].profile)) {
                            result.witness = {word(seen[old].index, limits.depth), complement(word(index, limits.depth))};
                            return false;
                        }
                    }
                    if (seen_count == capacity) throw ResourceStop{"max-working-bytes-hash-replay"};
                    seen[seen_count++] = {profile, index};
                    return true;
                });
                if (!checked) {
                    result.status = "collision"; result.upper_bound = limits.depth; return finish();
                }
            }
            begin = end;
        }
        result.status = "collision-free";
        result.lower_bound = limits.depth + 1;
    } catch (const ResourceStop& stopped) { result.reason = stopped.reason; }
    catch (const std::bad_alloc&) { result.reason = "allocation-failed"; }
    return finish();
}
}

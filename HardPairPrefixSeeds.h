#pragma once
// Construct equal-length prefix pairs satisfying a chosen finite family's
// endpoint constraints. Complete short layers and optional sampled long layers
// share the pair budget across depths. These are seeds, not certificates for an
// unexamined larger family. EVERY length uses a fresh profile collision table.
#include <algorithm>
#include <array>
#include <chrono>
#include <csignal>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <iterator>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace hardpair {

struct PrefixSeedOptions {
    unsigned int max_depth = 16;
    std::uint64_t max_words = 65536; // Complete words PER layer, not cumulative work.
    std::uint64_t max_pairs = 128;
    unsigned int common_prefix_depth = 0; // Opt-in actual-LCP strata0..D; D<=8.
    bool force_hash_collisions = false;
    std::vector<unsigned int> sample_depths; // Explicit, independently sampled longer layers.
    std::uint64_t samples_per_depth = 16384, seed = 1088;
    // Strict traversal: complete lexicographic word layers only, canonical
    // pair order and actual-LCP strata. Ignores sample_depths and seed. The
    // explicit word/depth/pair limits still make the collection bounded.
    bool deterministic = false;
    const volatile std::sig_atomic_t* interrupted = nullptr;
};
struct PrefixSeedPair {
    std::string first, second;
    std::vector<std::uint32_t> profile;
    std::uint64_t first_word_id = 0, second_word_id = 0;
};
struct PrefixSeedLayer {
    unsigned int depth = 0;
    std::uint64_t words = 0, unique_profiles = 0, colliding_buckets = 0;
    std::uint64_t total_pairs_available = 0, retained_candidates = 0, selected_pairs = 0;
    bool pair_count_saturated = false;
    bool complete_enumeration = false, sampled = false;
};
struct PrefixSeedResult {
    std::vector<PrefixSeedPair> pairs;
    std::vector<PrefixSeedLayer> per_depth;
    unsigned int first_collision_length = 0, completed_depth = 0;
    std::uint64_t words_evaluated = 0, profiles_retained = 0, buckets_with_collisions = 0;
    std::uint64_t coordinate_count = 0, unique_profiles = 0, total_pairs_available = 0;
    bool complete_first_collision_layer = false, complete_pair_collection = false;
    bool depth_capped = false, word_capped = false, pair_capped = false;
    bool interrupted = false, empty_coordinate_family = false, pair_count_saturated = false;
    bool depth_diversified = false;
    bool first_collision_proved_minimum = false, sampling_capped = false;
    unsigned int largest_sampled_depth = 0;
    std::uint64_t sampled_words_evaluated = 0;
    double seconds = 0;
};

namespace prefix_seed_detail {
inline std::uint64_t mix(std::uint64_t value)
{
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}
inline std::string word(std::uint64_t id, unsigned int length)
{
    std::string result(length, '0');
    for (unsigned int at = 0; at < length; ++at) { result[length - 1 - at] += id & 1U; id >>= 1; }
    return result;
}
// Enumerate all unordered index pairs without materializing O(n^2) entries.
// Short gaps preserve common prefixes; a coprime stride spreads each round
// across different word/parent positions rather than exhausting one star.
struct PairCursor {
    std::size_t size = 0, gap = 1, offset = 0, emitted = 0, stride = 1;
    bool canonical_order = false;
    explicit PairCursor(std::size_t count, bool canonical = false)
        : size(count), canonical_order(canonical) { reset_round(); }
    void reset_round()
    {
        emitted = offset = 0;
        if (gap >= size) return;
        const auto count = size - gap;
        if (canonical_order) { stride = 1; return; }
        stride = count / 2 + 1;
        if (stride >= count) stride = 1;
        while (std::gcd(stride, count) != 1) { ++stride; if (stride >= count) stride = 1; }
    }
    std::optional<std::pair<std::size_t, std::size_t>> next()
    {
        if (gap >= size) return std::nullopt;
        if (emitted == size - gap) { ++gap; reset_round(); if (gap >= size) return std::nullopt; }
        const auto first = offset, second = offset + gap, count = size - gap;
        offset = (offset + stride) % count; ++emitted;
        return std::pair{first, second};
    }
};
struct DiversePairCursor {
    std::size_t size;
    PairCursor exhaustive;
    std::set<std::pair<std::size_t, std::size_t>> seen;
    std::uint64_t proposal = 0;
    explicit DiversePairCursor(std::size_t count) : size(count), exhaustive(count) {}
    std::optional<std::pair<std::size_t, std::size_t>> next()
    {
        if (size < 2) return std::nullopt;
        for (unsigned int attempt = 0; attempt < 32; ++attempt) {
            const auto round = proposal / 4, style = proposal++ % 4;
            std::size_t a = 0, b = 1;
            if (style == 0) { // Adjacent words expose long common prefixes.
                a = round ? mix(round) % (size - 1) : 0; b = a + 1;
            } else if (style == 1) { // Opposite ends expose a different scale.
                a = round % (size / 2); b = size - 1 - a;
            } else if (style == 2) {
                const auto gap = std::max<std::size_t>(1, size / 2);
                a = mix(round ^ 0x535452494445ULL) % (size - gap); b = a + gap;
            } else {
                a = mix(round ^ 0x4649525354ULL) % size;
                b = mix(round ^ 0x5345434f4e44ULL) % (size - 1);
                if (b >= a) ++b;
                if (a > b) std::swap(a, b);
            }
            if (seen.insert({a, b}).second) return std::pair{a, b};
        }
        while (const auto pair = exhaustive.next())
            if (seen.insert(*pair).second) return pair;
        return std::nullopt;
    }
};
}

// transition(coordinate_index, state, bool_letter) -> uint32 state.
// Every layer retains a complete endpoint profile for each actual word ID.
// Hash matches are checked against complete vectors, including under the
// forced-collision regression mode. Initial states may differ by coordinate.
template<class Transition>
PrefixSeedResult enumerate_prefix_seeds(const std::vector<std::uint32_t>& initial_states,
                                       Transition transition, const PrefixSeedOptions& options = {})
{
    if (options.max_depth > 63) throw std::invalid_argument("prefix word IDs support depth0..63");
    if (options.common_prefix_depth > 8) throw std::invalid_argument("common prefix strata support depth0..8");
    auto sampled_depths = options.sample_depths;
    std::sort(sampled_depths.begin(), sampled_depths.end());
    sampled_depths.erase(std::unique(sampled_depths.begin(), sampled_depths.end()), sampled_depths.end());
    for (auto depth : sampled_depths) if (!depth || depth > 63) throw std::invalid_argument("sampled prefix depths must be1..63");
    // Strict mode never draws or substitutes a sampled long word. A complete
    // layer that exceeds max_words stops the lexicographic layer traversal;
    // the word_capped flag below preserves that coverage limitation.
    if (options.deterministic) sampled_depths.clear();
    const auto started = std::chrono::steady_clock::now();
    PrefixSeedResult result; result.coordinate_count = initial_states.size();
    std::vector<std::vector<PrefixSeedPair>> layer_candidates;
    std::vector<std::size_t> layer_legacy_counts;
    std::vector<std::vector<std::vector<std::size_t>>> layer_strata;
    auto finish = [&]() {
        std::vector<std::size_t> eligible;
        for (std::size_t i = 0; i < layer_candidates.size(); ++i) if (!layer_candidates[i].empty()) eligible.push_back(i);
        std::vector<std::size_t> order;
        for (std::size_t left = 0, right = eligible.size(); left < right;) {
            order.push_back(eligible[left++]); if (left < right) order.push_back(eligible[--right]);
        }
        if (!options.common_prefix_depth) { // Preserve the original sequence exactly.
            std::vector<std::size_t> next(layer_candidates.size());
            bool progress = true;
            while (result.pairs.size() < options.max_pairs && progress) {
                progress = false;
                for (auto index : order) {
                    auto& candidates = layer_candidates[index];
                    if (next[index] == candidates.size()) continue;
                    result.pairs.push_back(std::move(candidates[next[index]++]));
                    ++result.per_depth[index].selected_pairs; progress = true;
                    if (result.pairs.size() == options.max_pairs) break;
                }
            }
        } else {
            // Round-robin (depth, actual LCP) channels, rotating the depth for
            // each p so a small final budget still reaches different strata.
            struct Channel { std::size_t layer, p, next = 0; };
            std::vector<Channel> channels;
            for (std::size_t round = 0; round < order.size(); ++round)
                for (unsigned int p = 0; p <= options.common_prefix_depth; ++p) {
                    const auto index = order[(round + p) % order.size()];
                    if (!layer_strata[index][p].empty()) channels.push_back({index, p});
                }
            std::vector<std::size_t> legacy_next(layer_candidates.size());
            std::size_t legacy_at = 0, stratum_at = 0;
            auto take_legacy = [&]() -> std::optional<std::pair<std::size_t, std::size_t>> {
                for (std::size_t tried = 0; tried < order.size(); ++tried) {
                    const auto index = order[legacy_at++ % order.size()];
                    if (legacy_next[index] < layer_legacy_counts[index]) return std::pair{index, legacy_next[index]++};
                }
                return std::nullopt;
            };
            auto take_stratum = [&]() -> std::optional<std::pair<std::size_t, std::size_t>> {
                for (std::size_t tried = 0; tried < channels.size(); ++tried) {
                    auto& channel = channels[stratum_at++ % channels.size()];
                    const auto& indices = layer_strata[channel.layer][channel.p];
                    if (channel.next < indices.size()) return std::pair{channel.layer, indices[channel.next++]};
                }
                return std::nullopt;
            };
            std::set<std::tuple<unsigned int, std::uint64_t, std::uint64_t>> seen;
            for (std::uint64_t turn = 0; result.pairs.size() < options.max_pairs; ++turn) {
                auto selected = turn % 2 ? take_legacy() : take_stratum();
                if (!selected) selected = turn % 2 ? take_stratum() : take_legacy();
                if (!selected) break;
                const auto [index, candidate] = *selected;
                auto& pair = layer_candidates[index][candidate];
                if (!seen.emplace(result.per_depth[index].depth, pair.first_word_id, pair.second_word_id).second) continue;
                result.pairs.push_back(std::move(pair)); ++result.per_depth[index].selected_pairs;
            }
        }
        result.pair_capped = result.pair_count_saturated || result.total_pairs_available > result.pairs.size();
        result.complete_pair_collection = !result.empty_coordinate_family && !result.pair_capped && !result.word_capped
            && !result.interrupted && !result.sampling_capped
            && std::none_of(result.per_depth.begin(), result.per_depth.end(), [](const auto& layer) { return layer.sampled; });
        result.depth_diversified = std::count_if(result.per_depth.begin(), result.per_depth.end(), [](const auto& layer) { return layer.selected_pairs != 0; }) > 1;
        result.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        return result;
    };
    const auto canceled = [&]() { return options.interrupted && *options.interrupted; };
    if (initial_states.empty()) { result.empty_coordinate_family = true; return finish(); }
    if (canceled()) { result.interrupted = true; return finish(); }
    using Profile = std::vector<std::uint32_t>;
    auto collect = [&](unsigned int depth, const std::vector<Profile>& profiles,
                       const std::vector<std::uint64_t>& ids, bool sampled) {
        struct Bucket { std::size_t representative; std::vector<std::uint64_t> words; };
        std::vector<Bucket> groups;
        std::unordered_map<std::uint64_t, std::vector<std::size_t>> hash_buckets; // Fresh at EVERY length.
        const auto hash = [&](const Profile& profile) {
            if (options.force_hash_collisions) return std::uint64_t{0};
            std::uint64_t value = 0x5052454649585345ULL;
            for (auto state : profile) value = prefix_seed_detail::mix(value ^ prefix_seed_detail::mix(state));
            return value;
        };
        for (std::size_t index = 0; index < profiles.size(); ++index) {
            auto& same_hash = hash_buckets[hash(profiles[index])];
            bool matched = false;
            for (auto group_id : same_hash) {
                auto& group = groups[group_id];
                if (profiles[group.representative] == profiles[index]) { group.words.push_back(ids[index]); matched = true; break; }
            }
            if (!matched) { same_hash.push_back(groups.size()); groups.push_back({index, {ids[index]}}); }
        }
        PrefixSeedLayer layer; layer.depth = depth; layer.words = profiles.size(); layer.unique_profiles = groups.size();
        layer.sampled = sampled; layer.complete_enumeration = !sampled;
        result.unique_profiles = groups.size();
        std::vector<std::size_t> colliding;
        std::vector<prefix_seed_detail::DiversePairCursor> cursors;
        std::vector<prefix_seed_detail::PairCursor> canonical_cursors;
        for (std::size_t group_id = 0; group_id < groups.size(); ++group_id) {
            const auto size = groups[group_id].words.size(); if (size < 2) continue;
            colliding.push_back(group_id);
            if (options.deterministic) canonical_cursors.emplace_back(size, true);
            else cursors.emplace_back(size);
            const auto a = size % 2 ? size : size / 2, b = size % 2 ? (size - 1) / 2 : size - 1;
            if (b && a > (std::numeric_limits<std::uint64_t>::max() - layer.total_pairs_available) / b) {
                layer.total_pairs_available = std::numeric_limits<std::uint64_t>::max(); layer.pair_count_saturated = true;
            } else if (!layer.pair_count_saturated) layer.total_pairs_available += static_cast<std::uint64_t>(a) * b;
        }
        layer.colliding_buckets = colliding.size(); result.buckets_with_collisions += colliding.size();
        if (!colliding.empty() && !result.first_collision_length) {
            result.first_collision_length = depth;
            result.complete_first_collision_layer = !sampled;
            result.first_collision_proved_minimum = !sampled && result.completed_depth >= depth;
        }
        if (layer.pair_count_saturated || layer.total_pairs_available > std::numeric_limits<std::uint64_t>::max() - result.total_pairs_available) {
            result.total_pairs_available = std::numeric_limits<std::uint64_t>::max(); result.pair_count_saturated = true;
        } else if (!result.pair_count_saturated) result.total_pairs_available += layer.total_pairs_available;
        const auto wanted = std::min(options.max_pairs, layer.total_pairs_available);
        std::vector<PrefixSeedPair> candidates; candidates.reserve(static_cast<std::size_t>(wanted));
        bool progress = true;
        while (candidates.size() < wanted && progress) {
            progress = false;
            for (std::size_t i = 0; i < colliding.size() && candidates.size() < wanted; ++i) {
                // Canonical mode visits adjacent word IDs across the bucket,
                // then gap two, etc.; no seeded/hash-based proposals execute.
                const auto selected = options.deterministic ? canonical_cursors[i].next() : cursors[i].next();
                if (!selected) continue; progress = true;
                const auto& group = groups[colliding[i]];
                const auto first_id = group.words[selected->first], second_id = group.words[selected->second];
                candidates.push_back({prefix_seed_detail::word(first_id, depth), prefix_seed_detail::word(second_id, depth), profiles[group.representative], first_id, second_id});
            }
        }
        layer_legacy_counts.push_back(candidates.size());
        std::vector<std::vector<std::size_t>> strata(options.common_prefix_depth + 1);
        if (options.common_prefix_depth && wanted) {
            // Adjacent IDs on opposite sides of a binary-trie branch have
            // exact LCP p. No O(bucket_size^2) pair collection is needed.
            const auto lcp = [depth](std::uint64_t a, std::uint64_t b) {
                auto difference = a ^ b; unsigned int width = 0;
                while (difference) { difference >>= 1; ++width; }
                return depth - width;
            };
            std::array<std::uint64_t, 9> counts{}, quota{};
            for (auto id : colliding) {
                const auto& words = groups[id].words; // IDs arrive sorted in both layer modes.
                for (std::size_t j = 1; j < words.size(); ++j) {
                    const auto p = lcp(words[j - 1], words[j]);
                    if (p <= options.common_prefix_depth) ++counts[p];
                }
            }
            // At most max_pairs new candidates per layer in total, shared
            // fairly among its nonempty p strata. The legacy budget is kept.
            std::uint64_t allocated = 0; bool more = true;
            while (allocated < wanted && more) {
                more = false;
                for (unsigned int p = 0; p <= options.common_prefix_depth && allocated < wanted; ++p)
                    if (quota[p] < counts[p]) { ++quota[p]; ++allocated; more = true; }
            }
            // Two bounded reservoirs: one representative per profile group,
            // and one spread of branch boundaries. Strict traversal keeps
            // lexical boundaries, rather than using seeded ranks. The same
            // quotas and depth/LCP channels retain fair stratum coverage.
            using Boundary = std::tuple<std::uint64_t, std::size_t, std::uint64_t, std::uint64_t>;
            std::array<std::multiset<Boundary>, 9> spread, group_spread;
            const auto offer = [&](auto& reservoir, unsigned int p, const Boundary& boundary) {
                if (!quota[p]) return;
                reservoir.insert(boundary);
                if (reservoir.size() > quota[p]) reservoir.erase(std::prev(reservoir.end()));
            };
            for (auto id : colliding) {
                std::array<std::optional<Boundary>, 9> best;
                const auto& words = groups[id].words;
                for (std::size_t j = 1; j < words.size(); ++j) {
                    const auto a = words[j - 1], b = words[j];
                    const auto p = lcp(a, b);
                    if (p > options.common_prefix_depth || !quota[p]) continue;
                    const auto rank = options.deterministic ? a
                        : prefix_seed_detail::mix(options.seed ^ prefix_seed_detail::mix(a)
                            ^ prefix_seed_detail::mix(b ^ (std::uint64_t{depth} << 56)));
                    Boundary boundary{rank, id, a, b}; offer(spread[p], p, boundary);
                    if (!best[p] || boundary < *best[p]) best[p] = boundary;
                }
                for (unsigned int p = 0; p <= options.common_prefix_depth; ++p)
                    if (best[p]) offer(group_spread[p], p, *best[p]);
            }
            std::map<std::pair<std::uint64_t, std::uint64_t>, std::size_t> indices;
            for (std::size_t i = 0; i < candidates.size(); ++i)
                indices.emplace(std::pair{candidates[i].first_word_id, candidates[i].second_word_id}, i);
            for (unsigned int p = 0; p <= options.common_prefix_depth; ++p) {
                auto group_next = group_spread[p].begin(), raw_next = spread[p].begin();
                std::set<std::pair<std::uint64_t, std::uint64_t>> used;
                for (std::uint64_t turn = 0; strata[p].size() < quota[p]; ++turn) {
                    const bool use_group = (turn % 2 == 0 && group_next != group_spread[p].end()) || raw_next == spread[p].end();
                    if ((use_group && group_next == group_spread[p].end()) || (!use_group && raw_next == spread[p].end())) break;
                    const auto& boundary = use_group ? *group_next++ : *raw_next++;
                    const auto [rank, id, a, b] = boundary;
                    if (!used.emplace(a, b).second) continue;
                    const auto [entry, inserted] = indices.emplace(std::pair{a, b}, candidates.size());
                    if (inserted) candidates.push_back({prefix_seed_detail::word(a, depth), prefix_seed_detail::word(b, depth), profiles[groups[id].representative], a, b});
                    strata[p].push_back(entry->second);
                }
            }
        }
        layer_strata.push_back(std::move(strata));
        layer.retained_candidates = candidates.size(); result.per_depth.push_back(layer); layer_candidates.push_back(std::move(candidates));
    };
    std::vector<Profile> previous{initial_states};
    for (unsigned int depth = 1; depth <= options.max_depth; ++depth) {
        if (previous.size() > options.max_words / 2 || previous.size() > std::numeric_limits<std::size_t>::max() / 2) { result.word_capped = true; break; }
        const auto count = previous.size() * 2;
        std::vector<Profile> current; current.reserve(count);
        std::vector<std::uint64_t> ids; ids.reserve(count);
        for (std::size_t parent = 0; parent < previous.size(); ++parent) for (unsigned int letter = 0; letter < 2; ++letter) {
            if (canceled()) { result.interrupted = true; return finish(); }
            Profile profile(initial_states.size());
            for (std::size_t coordinate = 0; coordinate < profile.size(); ++coordinate)
                profile[coordinate] = transition(coordinate, previous[parent][coordinate], letter != 0);
            ids.push_back(current.size()); current.push_back(std::move(profile)); ++result.words_evaluated;
            result.profiles_retained = std::max<std::uint64_t>(result.profiles_retained, previous.size() + current.size());
        }
        result.completed_depth = depth;
        collect(depth, current, ids, false);
        previous = std::move(current);
    }
    result.depth_capped = result.completed_depth == options.max_depth;
    std::vector<Profile>().swap(previous);
    for (auto depth : sampled_depths) {
        if (depth <= result.completed_depth) continue; // Already exhaustively examined.
        const auto population = std::uint64_t{1} << depth;
        const auto wanted = std::min({options.samples_per_depth, options.max_words, population});
        if (options.samples_per_depth > options.max_words) result.word_capped = true;
        std::vector<std::uint64_t> ids; ids.reserve(static_cast<std::size_t>(wanted));
        if (wanted == population) { for (std::uint64_t id = 0; id < wanted; ++id) ids.push_back(id); }
        else {
            std::unordered_set<std::uint64_t> seen;
            const auto draw_budget = wanted > std::numeric_limits<std::uint64_t>::max() / 16 ? std::numeric_limits<std::uint64_t>::max() : std::max<std::uint64_t>(1024, wanted * 16);
            for (std::uint64_t draw = 0; ids.size() < wanted && draw < draw_budget; ++draw) {
                if (canceled()) { result.interrupted = true; return finish(); }
                const auto id = prefix_seed_detail::mix(options.seed ^ prefix_seed_detail::mix(depth) ^ prefix_seed_detail::mix(draw)) & (population - 1);
                if (seen.insert(id).second) ids.push_back(id);
            }
            if (ids.size() < wanted) result.sampling_capped = true;
        }
        std::sort(ids.begin(), ids.end());
        std::vector<Profile> profiles; profiles.reserve(ids.size());
        for (auto id : ids) {
            if (canceled()) { result.interrupted = true; return finish(); }
            Profile profile = initial_states;
            for (unsigned int left = depth; left; --left) {
                const auto letter = ((id >> (left - 1)) & 1U) != 0;
                for (std::size_t coordinate = 0; coordinate < profile.size(); ++coordinate)
                    profile[coordinate] = transition(coordinate, profile[coordinate], letter);
            }
            profiles.push_back(std::move(profile)); ++result.words_evaluated; ++result.sampled_words_evaluated;
            result.profiles_retained = std::max<std::uint64_t>(result.profiles_retained, profiles.size());
        }
        if (!profiles.empty()) result.largest_sampled_depth = depth;
        collect(depth, profiles, ids, true); // Sampled layers NEVER claim exhaustive coverage.
    }
    return finish();
}

}

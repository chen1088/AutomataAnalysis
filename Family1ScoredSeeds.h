#pragma once
// Deterministic full-family scoring of a bounded graph-derived seed catalogue.
// Prefix word layers are complete up to their declared budget. The catalogue
// itself is a bounded heuristic, not all compatible pairs in those layers.
#include "Family1JointPair.h"
#include "Family1JointSeeds.h"
#include <algorithm>
#include <bit>
#include <limits>
#include <map>
#include <set>
#include <tuple>
#include <vector>

namespace family1 {
struct ScoredSeed {
    std::string first, second;
    std::uint64_t disagreement = 0;
};
struct ScoredSeedPlan {
    JointSeedPlan catalogue;
    std::vector<ScoredSeed> selected;
    std::uint64_t candidates_scored = 0;
    std::string catalogue_rule = "global bounded catalogue from complete word layers";
};

inline ScoredSeedPlan scored_joint_seeds(const LargeGraph& graph,
    const std::shared_ptr<const ExactPackedProduct>& product,
    unsigned int depth, std::uint64_t words, std::uint64_t catalogue_size,
    std::uint64_t selected_size, unsigned int common_depth = 8)
{
    if (!product || product->graph_key() != graph.key())
        throw std::invalid_argument("scored seed product differs from graph");
    if (!selected_size || !catalogue_size || selected_size > catalogue_size)
        throw std::invalid_argument("scored seeds need 1 <= selected <= catalogue");
    ScoredSeedPlan result;
    result.catalogue = joint_prefix_seeds(graph, depth, words, catalogue_size, common_depth);
    using Channel = std::pair<unsigned int, unsigned int>;
    std::map<Channel, std::vector<ScoredSeed>> groups;
    for (const auto& [first, second] : result.catalogue.pairs) {
        unsigned int lcp = 0;
        while (lcp < first.size() && first[lcp] == second[lcp]) ++lcp;
        auto left = product->evaluate(first), right = product->evaluate(second);
        groups[{static_cast<unsigned int>(first.size()), lcp}].push_back(
            {first, second, product->disagreement_count(left, right)});
        ++result.candidates_scored;
    }
    const auto before = [](const ScoredSeed& a, const ScoredSeed& b) {
        return std::tie(a.disagreement, a.first, a.second) < std::tie(b.disagreement, b.first, b.second);
    };
    for (auto& [channel, candidates] : groups) std::sort(candidates.begin(), candidates.end(), before);
    std::map<Channel, std::size_t> next;
    bool progress = true;
    while (result.selected.size() < selected_size && progress) {
        progress = false;
        for (auto& [channel, candidates] : groups) {
            auto& index = next[channel];
            if (index == candidates.size()) continue;
            result.selected.push_back(candidates[index++]); progress = true;
            if (result.selected.size() == selected_size) break;
        }
    }
    return result;
}

// Compact complete permutation-profile layers. The cap applies separately to
// the canonically enumerated pair catalogue in each layer. Every catalogue
// pair is full-D scored; no claim covers uncollected compatible pairs.
inline ScoredSeedPlan fast_scored_joint_seeds(const LargeGraph& graph,
    const std::shared_ptr<const ExactPackedProduct>& product,
    unsigned int depth, std::uint64_t words, std::uint64_t pairs_per_layer,
    std::uint64_t selected_size)
{
    if (!product || product->graph_key() != graph.key())
        throw std::invalid_argument("scored seed product differs from graph");
    if (!pairs_per_layer || !selected_size || selected_size > pairs_per_layer || !words || depth > 30)
        throw std::invalid_argument("fast seeds require positive budgets, selected <= pair budget, depth <= 30");
    PairAgreementContext context(graph);
    std::vector<std::uint32_t> masks;
    for (std::uint32_t mask = 0; mask < context.mask_count() && masks.size() < 64; ++mask)
        if (context.is_permutation_mask(mask)) masks.push_back(mask);
    const auto width = std::bit_width(graph.size() - 1U);
    if (width * masks.size() > 64)
        return scored_joint_seeds(graph, product, depth, words, pairs_per_layer, selected_size);
    ScoredSeedPlan result;
    result.catalogue.permutation_coordinates = masks.size();
    result.catalogue_rule = "per-layer bounded catalogue in numeric packed-profile then word-ID bucket order";
    using Channel = std::pair<unsigned int, unsigned int>;
    std::map<Channel, std::vector<ScoredSeed>> channels;
    std::vector<std::uint64_t> previous{0};
    const auto encode_word = [](std::uint32_t id, unsigned int n) {
        std::string word(n, '0');
        for (unsigned int at = 0; at < n; ++at) { word[n - 1 - at] += id & 1U; id >>= 1; }
        return word;
    };
    struct Row { std::uint64_t profile; std::uint32_t word; };
    for (unsigned int n = 1; n <= depth; ++n) {
        if (previous.size() > words / 2) { result.catalogue.word_capped = true; break; }
        std::vector<std::uint64_t> next(2 * previous.size());
        std::vector<Row> ordered(next.size());
        for (std::size_t parent = 0; parent < previous.size(); ++parent) {
            for (unsigned int x = 0; x < 2; ++x) {
                std::uint64_t profile = 0;
                for (std::size_t i = 0; i < masks.size(); ++i) {
                    const auto q = static_cast<std::uint32_t>((previous[parent] >> (width * i)) & ((1U << width) - 1));
                    profile |= static_cast<std::uint64_t>(context.transition(masks[i], q, x != 0)) << (width * i);
                }
                const auto id = 2 * parent + x;
                next[id] = profile; ordered[id] = {profile, static_cast<std::uint32_t>(id)};
            }
        }
        result.catalogue.words_evaluated += next.size(); result.catalogue.completed_depth = n;
        std::sort(ordered.begin(), ordered.end(), [](auto a, auto b) {
            return std::tie(a.profile, a.word) < std::tie(b.profile, b.word);
        });
        struct Cursor { std::size_t begin, count, gap = 1, at = 0; };
        std::vector<Cursor> buckets;
        std::uint64_t available = 0;
        for (std::size_t begin = 0; begin < ordered.size();) {
            auto end = begin + 1;
            while (end < ordered.size() && ordered[end].profile == ordered[begin].profile) ++end;
            const auto count = end - begin;
            if (count > 1) { buckets.push_back({begin, count}); available += count * (count - 1) / 2; }
            begin = end;
        }
        if (available > pairs_per_layer) result.catalogue.pair_capped = true;
        std::uint64_t scored = 0;
        while (scored < std::min(available, pairs_per_layer)) {
            bool progress = false;
            for (auto& bucket : buckets) {
                if (bucket.gap >= bucket.count) continue;
                const auto a = ordered[bucket.begin + bucket.at].word;
                const auto b = ordered[bucket.begin + bucket.at + bucket.gap].word;
                if (++bucket.at == bucket.count - bucket.gap) { ++bucket.gap; bucket.at = 0; }
                auto first = encode_word(a, n), second = encode_word(b, n);
                const auto lcp = n - std::bit_width(a ^ b);
                const auto d = product->disagreement_count(product->evaluate(first), product->evaluate(second));
                result.catalogue.pairs.emplace_back(first, second);
                channels[{n, lcp}].push_back({std::move(first), std::move(second), d});
                ++scored; ++result.candidates_scored; progress = true;
                if (scored == pairs_per_layer) break;
            }
            if (!progress) break;
        }
        previous = std::move(next);
    }
    const auto before = [](const ScoredSeed& a, const ScoredSeed& b) {
        return std::tie(a.disagreement, a.first, a.second) < std::tie(b.disagreement, b.first, b.second);
    };
    for (auto& [channel, seeds] : channels) std::sort(seeds.begin(), seeds.end(), before);
    std::map<Channel, std::size_t> indices;
    bool progress = true;
    while (progress && result.selected.size() < selected_size) {
        progress = false;
        for (auto& [channel, seeds] : channels) {
            auto& index = indices[channel]; if (index == seeds.size()) continue;
            result.selected.push_back(seeds[index++]); progress = true;
            if (result.selected.size() == selected_size) break;
        }
    }
    return result;
}
}

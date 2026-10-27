#pragma once
// Graph-only deterministic multistart selection for full joint-word search.
// Endpoint agreement on selected permutation masks is a prefix-selection
// preference only: later 00/01/10/11 steps may change those agreements. This
// bounded catalogue neither excludes other prefixes nor proves minimality.
#include "Family1LargeGraph.h"
#include "Family1PairAgreement.h"
#include "HardPairPrefixSeeds.h"
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace family1 {

struct JointSeedPlan {
    std::vector<std::pair<std::string, std::string>> pairs;
    std::uint64_t words_evaluated = 0;
    unsigned int completed_depth = 0;
    bool pair_capped = false, word_capped = false;
    unsigned int permutation_coordinates = 0;
};

inline JointSeedPlan joint_prefix_seeds(const LargeGraph& graph,
                                       unsigned int max_depth,
                                       std::uint64_t max_words,
                                       std::uint64_t max_pairs,
                                       unsigned int common_prefix_depth = 8)
{
    if (!graph.accessible()) throw std::invalid_argument("joint prefix seeds require root accessibility");
    if (!max_words) throw std::invalid_argument("joint prefix seed word budget must be positive");
    PairAgreementContext context(graph);
    std::vector<std::uint32_t> masks;
    for (std::uint32_t mask = 0; mask < context.mask_count() && masks.size() < 64; ++mask)
        if (context.is_permutation_mask(mask)) masks.push_back(mask);

    hardpair::PrefixSeedOptions options;
    options.max_depth = max_depth;
    options.max_words = max_words;
    options.max_pairs = max_pairs;
    options.common_prefix_depth = common_prefix_depth;
    options.deterministic = true;
    options.samples_per_depth = 0;
    // No sampled depths, seed-dependent ordering, saved words or score labels.
    // A dummy absorbing coordinate makes the no-permutation constraint family
    // vacuous while preserving the reusable module's empty-family semantics.
    const auto initial = std::vector<std::uint32_t>(std::max<std::size_t>(1, masks.size()), 0);
    auto result = hardpair::enumerate_prefix_seeds(initial,
        [&](std::size_t coordinate, std::uint32_t state, bool symbol) {
            return masks.empty() ? 0U : context.transition(masks[coordinate], state, symbol);
        }, options);

    JointSeedPlan plan;
    plan.words_evaluated = result.words_evaluated;
    plan.completed_depth = result.completed_depth;
    plan.pair_capped = result.pair_capped;
    plan.word_capped = result.word_capped;
    plan.permutation_coordinates = static_cast<unsigned int>(masks.size());
    plan.pairs.reserve(result.pairs.size());
    for (auto& pair : result.pairs)
        plan.pairs.emplace_back(std::move(pair.first), std::move(pair.second));
    return plan;
}

}

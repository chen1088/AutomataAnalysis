#pragma once
// Accuracy-oriented deterministic Family 1 hard-pair pipeline. The exact short
// layer phase and the bounded scored-seed joint phase have separate provenance.
#include "Family1ScoredSeeds.h"
#include "Family1TailScoredSeeds.h"
#include "HardPairJointFinder.h"
#include <algorithm>
#include <functional>
#include <limits>
#include <memory>
#include <string>
#include <vector>

namespace family1::near_pair {

enum class SeedRanking { FullDisagreement, CommonMaximum, CommonSum, Portfolio };

struct Options {
    hardpair::joint::Options joint;
    unsigned int exact_depth = 24, prefix_depth = 20;
    std::uint64_t exact_max_words = 16777216, exact_memory_bytes = std::uint64_t{256} << 20;
    std::uint64_t prefix_words = 1048576, catalogue_size = 16384, selected_pairs = 512;
    std::uint64_t fallback_catalogue_size = 4096;
    bool compact = false, retry_compact_on_miss = true;
    SeedRanking seed_ranking = SeedRanking::Portfolio;
    Options() {
        joint.window_k = 4; joint.beam_width = 16; joint.diagonal_width = 0;
        joint.unequal_width = 0; joint.prioritize_permutation = true;
        joint.max_length = 80; joint.max_expansions = 2000000; joint.max_trace_records = 0;
    }
};

struct Improvement {
    std::string first, second, producer, seed_first, seed_second;
    unsigned int upper_bound = 0, lower_bound = 1;
    bool exact = false;
    std::vector<std::uint64_t> metric_trace;
    std::uint64_t verified_masks = 0;
    std::string seed_mode;
};

struct Result {
    bool found = false, exact = false;
    unsigned int lower_bound = 1, upper_bound = 0;
    std::string first, second, producer, winning_seed_first, winning_seed_second;
    std::vector<std::uint64_t> metric_trace;
    std::uint64_t verified_masks = 0, exact_evaluated_words = 0, exact_peak_bytes = 0;
    std::string exact_status, exact_reason, seed_catalogue_rule;
    std::uint64_t seed_words = 0, candidates_scored = 0, seed_candidates_selected = 0;
    std::uint64_t attempts = 0, skipped_seeds = 0, nodes = 0, complete_windows = 0, partial_windows = 0;
    std::uint64_t improvements = 0, windows_refused = 0;
    std::uint64_t common_pair_states = 0;
    unsigned int prefix_completed_depth = 0;
    bool expansion_capped = false, seed_pair_capped = false, seed_word_capped = false;
    bool length_capped = false, beam_truncated = false, interrupted = false;
    bool retried_compact = false;
    std::string winning_seed_mode;
};

using ImprovementCallback = std::function<void(const Improvement&)>;

// Scalar replay is independent of the packed transitions used by the search.
inline std::vector<std::uint64_t> scalar_trace(const LargeGraph& graph,
    const std::string& first, const std::string& second)
{
    if (first.empty() || first == second || first.size() != second.size())
        throw std::logic_error("invalid near-pair witness words");
    for (const auto* word : {&first, &second})
        if (word->find_first_not_of("01") != std::string::npos)
            throw std::logic_error("nonbinary near-pair witness");
    std::vector<std::uint64_t> trace(first.size() + 1, 0);
    for (std::uint32_t mask = 0; mask < (std::uint32_t{1} << graph.size()); ++mask) {
        unsigned int left = 0, right = 0;
        for (std::size_t at = 0; at < first.size(); ++at) {
            left = graph.ports[left][static_cast<unsigned int>(first[at] == '1') ^ ((mask >> left) & 1U)];
            right = graph.ports[right][static_cast<unsigned int>(second[at] == '1') ^ ((mask >> right) & 1U)];
            trace[at + 1] += left != right;
        }
        if (left != right) throw std::logic_error("near-pair witness fails scalar replay");
    }
    return trace;
}

inline Result find_pair(const LargeGraph& graph, const Options& options = {},
                        const ImprovementCallback& on_improvement = {})
{
    graph.validate();
    if (!graph.accessible()) throw std::invalid_argument("near-pair graph must be accessible");
    if (options.exact_depth > 30 || !options.exact_max_words || !options.exact_memory_bytes
        || !options.prefix_depth || options.prefix_depth > 30 || !options.prefix_words
        || !options.catalogue_size || !options.fallback_catalogue_size || !options.selected_pairs || options.selected_pairs > options.catalogue_size
        || !options.joint.window_k || options.joint.window_k > 8 || !options.joint.beam_width
        || options.joint.beam_width > 4096 || options.joint.diagonal_width > 4096
        || options.joint.unequal_width > 4096 || !options.joint.max_length
        || options.joint.max_length > 4096 || !options.joint.max_expansions)
        throw std::invalid_argument("invalid near-pair options");
    Result result;
    const auto accept = [&](const std::string& first, const std::string& second,
                            const std::string& producer,
                            const std::string& seed_first, const std::string& seed_second,
                            const std::string& seed_mode = "") {
        const auto length = static_cast<unsigned int>(first.size());
        if (result.found && length >= result.upper_bound) return;
        if (length < result.lower_bound) throw std::logic_error("positive contradicts exact layer lower bound");
        auto trace = scalar_trace(graph, first, second);
        result.found = true; result.upper_bound = length; result.first = first; result.second = second;
        result.exact = result.lower_bound == length; result.producer = producer;
        result.winning_seed_first = seed_first; result.winning_seed_second = seed_second;
        result.winning_seed_mode = seed_mode;
        result.metric_trace = std::move(trace); result.verified_masks = std::uint64_t{1} << graph.size();
        ++result.improvements;
        if (on_improvement) on_improvement({first, second, producer, seed_first, seed_second,
            length, result.lower_bound, result.exact, result.metric_trace, result.verified_masks, seed_mode});
    };
    if (options.exact_depth) {
        PackedLimits limits;
        limits.depth = std::min(options.exact_depth, options.joint.max_length);
        limits.max_layer_states = options.exact_max_words; limits.max_working_bytes = options.exact_memory_bytes;
        limits.timeout_ms = 0; limits.interrupted = options.joint.interrupted;
        auto answer = score_packed(graph, limits);
        result.lower_bound = answer.lower_bound; result.exact_status = answer.status;
        result.exact_reason = answer.reason; result.exact_evaluated_words = answer.evaluated_words;
        result.exact_peak_bytes = answer.peak_working_bytes;
        if (answer.status == "exact") {
            accept(answer.witness[0], answer.witness[1], "exact-word-layers", "", "");
            return result;
        }
    } else result.exact_status = "disabled";
    if (options.joint.interrupted && *options.joint.interrupted) { result.interrupted = true; return result; }
    if (result.lower_bound > options.joint.max_length) { result.length_capped = true; return result; }
    auto product = std::make_shared<const ExactPackedProduct>(graph);
    auto priority = permutation_priority_selection(product, graph);
    JointSeedPlan cached_catalogue;
    const auto search_stage = [&](bool compact, std::uint64_t catalogue_size, std::string mode,
                                  SeedRanking ranking, bool cache, const JointSeedPlan* supplied) {
        ScoredSeedPlan plan;
        bool generated_words = !supplied;
        if (ranking == SeedRanking::FullDisagreement) {
            plan = compact
                ? fast_scored_joint_seeds(graph, product, options.prefix_depth, options.prefix_words,
                                         catalogue_size, options.selected_pairs)
                : scored_joint_seeds(graph, product, options.prefix_depth, options.prefix_words,
                                     catalogue_size, options.selected_pairs);
            mode += "/full-D";
        } else {
            ScoredSeedPlan compact_catalogue;
            if (compact && !supplied) {
                compact_catalogue = fast_scored_joint_seeds(graph, product, options.prefix_depth,
                    options.prefix_words, catalogue_size, options.selected_pairs);
                supplied = &compact_catalogue.catalogue;
                result.candidates_scored += compact_catalogue.candidates_scored;
            }
            const auto rank_mode = ranking == SeedRanking::CommonMaximum ? 0U : 1U;
            auto tail = tail_scored_joint_seeds(graph, product, options.prefix_depth, options.prefix_words,
                                               catalogue_size, options.selected_pairs, rank_mode, supplied);
            result.common_pair_states += tail.common_pair_states;
            plan.catalogue = std::move(tail.catalogue); plan.candidates_scored = tail.candidates_scored;
            plan.catalogue_rule = rank_mode == 0 ? "same catalogue ranked by common infinity count, maximum, sum, D"
                                                : "same catalogue ranked by common infinity count, sum, maximum, D";
            for (auto& seed : tail.selected)
                plan.selected.push_back({std::move(seed.first), std::move(seed.second), seed.score.disagreement});
            mode += rank_mode == 0 ? "/common-max" : "/common-sum";
        }
        if (cache) cached_catalogue = plan.catalogue;
        result.seed_words += generated_words ? plan.catalogue.words_evaluated : 0;
        result.candidates_scored += plan.candidates_scored;
        result.seed_candidates_selected += plan.selected.size();
        if (!result.seed_catalogue_rule.empty()) result.seed_catalogue_rule += "; then ";
        result.seed_catalogue_rule += plan.catalogue_rule;
        result.prefix_completed_depth = std::max(result.prefix_completed_depth, plan.catalogue.completed_depth);
        result.seed_pair_capped |= plan.catalogue.pair_capped; result.seed_word_capped |= plan.catalogue.word_capped;
        for (const auto& seed : plan.selected) {
            if (options.joint.interrupted && *options.joint.interrupted) { result.interrupted = true; break; }
            auto joint = options.joint;
            joint.max_length = result.found ? std::min(joint.max_length, result.upper_bound - 1) : joint.max_length;
            if (seed.first.size() > joint.max_length) { ++result.skipped_seeds; continue; }
            auto answer = hardpair::joint::find_pair(JointPairState(product, seed.first, seed.second, priority), joint);
            ++result.attempts; result.nodes += answer.expanded_nodes;
            result.complete_windows += answer.complete_windows; result.partial_windows += answer.partial_windows;
            result.windows_refused += answer.windows_refused;
            result.expansion_capped |= answer.expansion_limit_reached; result.length_capped |= answer.length_limit_reached;
            result.beam_truncated |= answer.beam_truncated; result.interrupted |= answer.interrupted;
            if (answer.partial_windows) throw std::logic_error("near-pair evaluated a partial window");
            if (answer.found) accept(answer.first, answer.second, "scored-seed-joint", seed.first, seed.second, mode);
            if (result.exact || result.interrupted) break;
        }
    };
    const auto first_ranking = options.seed_ranking == SeedRanking::Portfolio
        ? SeedRanking::FullDisagreement : options.seed_ranking;
    search_stage(options.compact, options.catalogue_size, options.compact ? "compact" : "scored",
                 first_ranking, options.seed_ranking == SeedRanking::Portfolio, nullptr);
    if (!result.found && !result.interrupted && !options.compact && options.retry_compact_on_miss) {
        result.retried_compact = true;
        search_stage(true, std::max(options.fallback_catalogue_size, options.selected_pairs), "compact-fallback",
                     SeedRanking::FullDisagreement, false, nullptr);
    }
    if (options.seed_ranking == SeedRanking::Portfolio && !result.exact && !result.interrupted)
        search_stage(false, options.catalogue_size, "cached", SeedRanking::CommonMaximum, false, &cached_catalogue);
    return result;
}
}

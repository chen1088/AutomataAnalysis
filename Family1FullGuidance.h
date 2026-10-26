#pragma once
// Bounded common-suffix beam search whose objective counts EVERY static mask.
// A miss proves no lower bound; a hit still requires the caller's independent
// scalar replay before it is accepted as a universal-collision witness.
#include "Family1PairAgreement.h"
#include <algorithm>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <memory>
#include <numeric>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace family1 {

struct FullSuffixBeamResult {
    std::string suffix;
    std::vector<std::uint64_t> score_trace;
    std::uint64_t merged_count = 0, mask_count = 0, permutation_mismatch_count = 0;
    std::uint64_t expanded_nodes = 0, lookahead_nodes = 0, neutral_nodes = 0;
    unsigned int depth_reached = 0;
    bool all_merged = false, interrupted = false, expansion_limit_reached = false;
    double seconds = 0;
};

namespace full_guidance_detail {
inline std::uint64_t mix(std::uint64_t value)
{
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}
struct Node {
    ExactPairAgreement pair;
    std::string suffix;
    std::vector<std::uint64_t> trace;
    std::uint64_t token = 0, rank = 0, parent_score = 0;
    unsigned int parent = 0;
    bool letter = false;
};
}

inline FullSuffixBeamResult full_suffix_beam(
    std::shared_ptr<const PairAgreementContext> context,
    const std::string& first, const std::string& second,
    unsigned int max_suffix, unsigned int beam_width, unsigned int lookahead,
    std::uint64_t tie_seed, const volatile std::sig_atomic_t* interrupted = nullptr,
    std::uint64_t max_nodes = 10000)
{
    using full_guidance_detail::Node;
    using full_guidance_detail::mix;
    if (!beam_width || beam_width > 64 || lookahead > 1)
        throw std::invalid_argument("full guidance requires beam width1..64 and lookahead0..1");
    const auto started = std::chrono::steady_clock::now();
    ExactPairAgreement initial(std::move(context), first, second);
    FullSuffixBeamResult result;
    result.mask_count = initial.mask_count();
    result.merged_count = initial.merged_count();
    result.permutation_mismatch_count = initial.permutation_mismatch_count();
    result.score_trace = {initial.merged_count()};
    result.all_merged = initial.all_merged();
    auto best_token = mix(tie_seed);
    auto finish = [&]() {
        if (interrupted && *interrupted) result.interrupted = true;
        result.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        return result;
    };
    auto available = [&]() {
        if (interrupted && *interrupted) { result.interrupted = true; return false; }
        if (result.expanded_nodes + result.lookahead_nodes >= max_nodes) {
            result.expansion_limit_reached = true;
            return false;
        }
        return true;
    };
    auto consider = [&](const ExactPairAgreement& pair, const std::string& suffix,
                        const std::vector<std::uint64_t>& trace, std::uint64_t token) {
        result.depth_reached = std::max(result.depth_reached, static_cast<unsigned int>(suffix.size()));
        // Preserve a progressed neutral path on a plateau rather than reporting
        // only the initial prefix. Full hits are returned at the first layer.
        if (pair.merged_count() > result.merged_count
            || (pair.merged_count() == result.merged_count && suffix.size() > result.suffix.size())
            || (pair.merged_count() == result.merged_count && suffix.size() == result.suffix.size() && token < best_token)) {
            result.merged_count = pair.merged_count();
            result.suffix = suffix;
            result.score_trace = trace;
            result.all_merged = pair.all_merged();
            best_token = token;
        }
    };
    if (result.all_merged || result.permutation_mismatch_count || !max_suffix) return finish();
    if (interrupted && *interrupted) { result.interrupted = true; return finish(); }
    std::vector<Node> beam;
    beam.push_back({std::move(initial), "", result.score_trace, mix(tie_seed), result.merged_count, result.merged_count, 0, false});
    for (unsigned int depth = 0; depth < max_suffix; ++depth) {
        std::vector<Node> candidates;
        candidates.reserve(2 * beam.size());
        // Generate both immediate letters before looking ahead. No positive
        // score increment is required, so neutral bridges remain searchable.
        for (unsigned int parent = 0; parent < beam.size(); ++parent) {
            const auto& node = beam[parent];
            for (unsigned int letter = 0; letter < 2; ++letter) {
                if (!available()) return finish();
                auto pair = node.pair.append_common(letter != 0);
                ++result.expanded_nodes;
                auto suffix = node.suffix + static_cast<char>('0' + letter);
                auto trace = node.trace; trace.push_back(pair.merged_count());
                const auto token = mix(node.token ^ (0xd1b54a32d192ed03ULL + letter)
                                       ^ (static_cast<std::uint64_t>(depth) << 32));
                if (pair.merged_count() == node.pair.merged_count()) ++result.neutral_nodes;
                consider(pair, suffix, trace, token);
                if (pair.all_merged()) return finish();
                const auto rank = pair.merged_count(), prior = node.pair.merged_count();
                candidates.push_back({std::move(pair), std::move(suffix), std::move(trace), token, rank, prior, parent, letter != 0});
            }
        }
        if (lookahead && depth + 1 < max_suffix) {
            for (auto& node : candidates) {
                // Lookahead1 adds one further common letter. Its exact score
                // ranks this candidate; the current node's trace stays actual.
                for (unsigned int letter = 0; letter < 2; ++letter) {
                    if (!available()) return finish();
                    auto pair = node.pair.append_common(letter != 0);
                    ++result.lookahead_nodes;
                    auto suffix = node.suffix + static_cast<char>('0' + letter);
                    auto trace = node.trace; trace.push_back(pair.merged_count());
                    const auto token = mix(node.token ^ (0xd1b54a32d192ed03ULL + letter)
                                           ^ (static_cast<std::uint64_t>(depth + 1) << 32));
                    if (pair.merged_count() == node.pair.merged_count()) ++result.neutral_nodes;
                    node.rank = std::max(node.rank, pair.merged_count());
                    consider(pair, suffix, trace, token);
                    if (pair.all_merged()) return finish();
                }
            }
        }
        std::vector<std::size_t> order(candidates.size());
        std::iota(order.begin(), order.end(), std::size_t{0});
        const auto better = [&](std::size_t a, std::size_t b) {
            const auto& left = candidates[a]; const auto& right = candidates[b];
            if (left.rank != right.rank) return left.rank > right.rank;
            if (left.pair.merged_count() != right.pair.merged_count()) return left.pair.merged_count() > right.pair.merged_count();
            if (left.token != right.token) return left.token < right.token;
            return left.suffix < right.suffix;
        };
        std::sort(order.begin(), order.end(), better);
        std::vector<std::size_t> chosen;
        std::vector<bool> used(candidates.size()), parent_used(beam.size());
        std::array<unsigned int, 2> letter_count{};
        while (chosen.size() < beam_width && chosen.size() < candidates.size()) {
            const auto first_unused = std::find_if(order.begin(), order.end(), [&](auto index) { return !used[index]; });
            if (first_unused == order.end()) break;
            const auto leading = *first_unused;
            auto selected = leading;
            for (auto index : order) {
                if (used[index]) continue;
                const auto& candidate = candidates[index];
                if (candidate.rank != candidates[leading].rank
                    || candidate.pair.merged_count() != candidates[leading].pair.merged_count()) continue;
                const auto& prior = candidates[selected];
                if (parent_used[candidate.parent] != parent_used[prior.parent]) {
                    if (!parent_used[candidate.parent]) selected = index;
                } else if (letter_count[candidate.letter] < letter_count[prior.letter]) selected = index;
            }
            used[selected] = true;
            parent_used[candidates[selected].parent] = true;
            ++letter_count[candidates[selected].letter];
            chosen.push_back(selected);
        }
        // With width>=2 reserve one neutral bridge when none survived the
        // score ranking. This explores plateaus even beside tempting gains.
        if (chosen.size() >= 2
            && std::none_of(chosen.begin(), chosen.end(), [&](auto index) { return candidates[index].pair.merged_count() == candidates[index].parent_score; })) {
            const auto neutral = std::find_if(order.begin(), order.end(), [&](auto index) {
                return candidates[index].pair.merged_count() == candidates[index].parent_score;
            });
            if (neutral != order.end()) chosen.back() = *neutral;
        }
        std::vector<Node> next;
        next.reserve(chosen.size());
        for (auto index : chosen) next.push_back(std::move(candidates[index]));
        beam = std::move(next);
    }
    return finish();
}

}

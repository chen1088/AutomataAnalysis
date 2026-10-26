#pragma once
// Complete single-DFA pair mergeability. No Family1 dependency. Negative
// answers are exposed as proofs only after the entire reverse BFS completes.
#include <chrono>
#include <csignal>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace hardpair {

struct PairMergeabilityLimits {
    std::uint64_t max_pair_states = 1000000;
    const volatile std::sig_atomic_t* interrupted = nullptr;
};
struct PairMergeabilityResult {
    unsigned int state_count = 0;
    std::vector<std::uint8_t> mergeable;
    std::vector<std::uint32_t> distance;
    std::uint64_t pair_states = 0, pair_edges = 0, mergeable_pairs = 0;
    bool complete = false, state_capped = false, interrupted = false;
    double seconds = 0;
    static constexpr auto unreachable_distance = std::numeric_limits<std::uint32_t>::max();

    bool proven_unmergeable(unsigned int first, unsigned int second) const
    {
        if (first >= state_count || second >= state_count)
            throw std::out_of_range("pair viability state out of range");
        return complete && !mergeable[static_cast<std::size_t>(first) * state_count + second];
    }
};

// transition(state,bool_letter) -> an integer state in [0,n).
// Every ordered pair is a vertex. Reverse reachability from all diagonals
// identifies exactly the pairs admitting a common merging word, and BFS
// distances give the shortest such word length. No hashes are involved.
template<class Transition>
PairMergeabilityResult analyze_pair_mergeability(unsigned int n, Transition transition,
                                                  const PairMergeabilityLimits& limits = {})
{
    if (!n) throw std::invalid_argument("pair mergeability requires a positive state count");
    const auto started = std::chrono::steady_clock::now();
    PairMergeabilityResult result; result.state_count = n;
    result.pair_states = static_cast<std::uint64_t>(n) * n;
    auto finish = [&]() {
        result.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        return result;
    };
    auto stopped = [&]() {
        if (limits.interrupted && *limits.interrupted) { result.interrupted = true; return true; }
        return false;
    };
    if (stopped()) return finish();
    // uint32 distances and bounded allocation are part of the API. A cap is
    // UNKNOWN: complete stays false and proven_unmergeable always returns false.
    if (result.pair_states > limits.max_pair_states
        || result.pair_states >= std::numeric_limits<std::uint32_t>::max()
        || result.pair_states > (std::numeric_limits<std::size_t>::max() - 1) / 2) {
        result.state_capped = true; return finish();
    }
    const auto count = static_cast<std::size_t>(result.pair_states);
    result.pair_edges = 2 * result.pair_states;
    std::vector<std::uint32_t> zero(n), one(n);
    for (unsigned int s = 0; s < n; ++s) {
        if (stopped()) return finish();
        const auto a = transition(s, false), b = transition(s, true);
        if (a >= n || b >= n) throw std::invalid_argument("pair mergeability transition target out of range");
        zero[s] = a; one[s] = b;
    }
    std::vector<std::size_t> offsets(count + 1, 0);
    for (std::size_t p = 0; p < count; ++p) {
        if (!(p & 4095U) && stopped()) return finish();
        const auto a = p / n, b = p % n;
        ++offsets[static_cast<std::size_t>(zero[a]) * n + zero[b] + 1];
        ++offsets[static_cast<std::size_t>(one[a]) * n + one[b] + 1];
    }
    for (std::size_t p = 1; p < offsets.size(); ++p) offsets[p] += offsets[p - 1];
    auto cursor = offsets;
    std::vector<std::size_t> predecessors(2 * count);
    for (std::size_t p = 0; p < count; ++p) {
        if (!(p & 4095U) && stopped()) return finish();
        const auto a = p / n, b = p % n;
        auto target = static_cast<std::size_t>(zero[a]) * n + zero[b]; predecessors[cursor[target]++] = p;
        target = static_cast<std::size_t>(one[a]) * n + one[b]; predecessors[cursor[target]++] = p;
    }
    result.mergeable.assign(count, 0);
    result.distance.assign(count, PairMergeabilityResult::unreachable_distance);
    std::vector<std::size_t> queue; queue.reserve(count);
    for (unsigned int s = 0; s < n; ++s) {
        const auto p = static_cast<std::size_t>(s) * n + s;
        result.mergeable[p] = 1; result.distance[p] = 0; queue.push_back(p);
    }
    for (std::size_t head = 0; head < queue.size(); ++head) {
        if (!(head & 4095U) && stopped()) return finish();
        const auto target = queue[head];
        for (auto at = offsets[target]; at < offsets[target + 1]; ++at) {
            const auto before = predecessors[at];
            if (result.mergeable[before]) continue;
            result.mergeable[before] = 1; result.distance[before] = result.distance[target] + 1;
            queue.push_back(before);
        }
    }
    if (stopped()) return finish();
    result.mergeable_pairs = queue.size(); result.complete = true;
    return finish();
}

// Concise alias for callers interested in the complete mergeability table.
template<class Transition>
PairMergeabilityResult pair_mergeability(unsigned int n, Transition transition,
                                         const PairMergeabilityLimits& limits = {})
{
    return analyze_pair_mergeability(n, transition, limits);
}
} // namespace hardpair

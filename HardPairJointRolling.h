#pragma once
// Experimental deterministic receding-horizon beam search over 00,01,10,11.
// Every evaluated k-window is complete. Only its first symbol is committed.
// Beam retention and optional cycle avoidance make this a witness heuristic.
#include <algorithm>
#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_set>
#include <utility>
#include <vector>

namespace hardpair::rolling {
struct Options {
    unsigned int k = 3, beam = 16, max_length = 80;
    // 0: immediate score then lexical; 1: number of best leaves; 2: total
    // future scores. These are deterministic secondary lookahead objectives.
    unsigned int tie_mode = 0;
    std::uint64_t max_expansions = 2000000;
    bool priority = false, diverse = false, avoid_cycles = false;
};
struct Result {
    std::string first, second;
    unsigned int length = 0, rounds = 0;
    std::uint64_t expanded_nodes = 0, windows = 0, leaves = 0;
    std::uint64_t deduplicated = 0, cycles_avoided = 0;
    bool capped = false, found = false;
};

template<class State>
Result find_pair(std::vector<State> beam, const Options& options)
{
    if (beam.empty() || !options.k || options.k > 8 || !options.beam || options.beam>4096 ||
        !options.max_length || options.max_length>4096 || !options.max_expansions || options.tie_mode>2)
        throw std::invalid_argument("invalid rolling search options");
    Result result;
    const auto initial_depth = beam.front().first_word().size();
    if(initial_depth>options.max_length)throw std::invalid_argument("rolling starts exceed maximum length");
    for (const auto& state : beam)
        if (state.first_word().size() != initial_depth || state.second_word().size() != initial_depth)
            throw std::invalid_argument("rolling search starts must have the same length");
    const auto priority = [&](const State& state) {
        return options.priority ? state.priority_remaining_count() : 0;
    };
    const auto words = [](const State& a, const State& b) {
        return std::tie(a.first_word(), a.second_word()) < std::tie(b.first_word(), b.second_word());
    };
    const auto consider = [&](const State& state) {
        if (!state.distinct() || state.remaining_count()) return;
        const auto n = state.first_word().size();
        if (!result.found || n < result.length ||
            (n == result.length && std::tie(state.first_word(), state.second_word()) < std::tie(result.first, result.second))) {
            result.found = true; result.length = n;
            result.first = state.first_word(); result.second = state.second_word();
        }
    };
    std::sort(beam.begin(), beam.end(), words);
    for (const auto& state : beam) consider(state);
    if (result.found) return result;
    std::unordered_set<std::string> expanded;
    while (!beam.empty() && beam.front().first_word().size() < options.max_length) {
        ++result.rounds;
        const auto depth = beam.front().first_word().size();
        const auto span = std::min<std::size_t>(options.k, options.max_length - depth);
        std::uint64_t level = 1, required = 0;
        for (unsigned int i = 0; i < span; ++i) { level *= 4; required += level; }
        struct Candidate {
            State state;
            std::uint64_t future_priority = UINT64_MAX, future_remaining = UINT64_MAX;
            std::uint64_t best_leaves = 0, sum_priority = 0, sum_remaining = 0;
        };
        std::vector<Candidate> candidates;
        for (const auto& state : beam) if (options.avoid_cycles) expanded.insert(state.state_key());
        for (const auto& parent : beam) {
            if (required > options.max_expansions - result.expanded_nodes) { result.capped = true; break; }
            const auto nodes_before=result.expanded_nodes,leaves_before=result.leaves;
            for (unsigned int symbol = 0; symbol < 4; ++symbol) {
                Candidate candidate{parent.append_pair(symbol & 2, symbol & 1)};
                ++result.expanded_nodes;
                consider(candidate.state);
                auto visit = [&](auto&& self, const State& state, unsigned int remaining) -> void {
                    if (!remaining) {
                        ++result.leaves;
                        const auto p = priority(state), d = state.remaining_count();
                        candidate.sum_priority=p>UINT64_MAX-candidate.sum_priority?UINT64_MAX:candidate.sum_priority+p;
                        candidate.sum_remaining+=d;
                        if (std::tie(p, d) < std::tie(candidate.future_priority, candidate.future_remaining)) {
                            candidate.future_priority = p; candidate.future_remaining = d;candidate.best_leaves=1;
                        }else if(std::tie(p,d)==std::tie(candidate.future_priority,candidate.future_remaining))++candidate.best_leaves;
                        return;
                    }
                    for (unsigned int next = 0; next < 4; ++next) {
                        auto child = state.append_pair(next & 2, next & 1);
                        ++result.expanded_nodes; consider(child);
                        self(self, child, remaining - 1);
                    }
                };
                visit(visit, candidate.state, span - 1);
                if (candidate.state.distinct()) candidates.push_back(std::move(candidate));
                // Common-word paths are represented by the separately enumerated
                // common-prefix start catalogue; they do not consume this beam.
            }
            if(result.expanded_nodes-nodes_before!=required || result.leaves-leaves_before!=level)
                throw std::logic_error("rolling window did not enumerate the full joint alphabet");
            ++result.windows;
        }
        if (result.found || result.capped) return result;
        const auto better = [&](const Candidate& a, const Candidate& b) {
            if (a.future_priority != b.future_priority) return a.future_priority < b.future_priority;
            if (a.future_remaining != b.future_remaining) return a.future_remaining < b.future_remaining;
            if(options.tie_mode==1 && a.best_leaves!=b.best_leaves)return a.best_leaves>b.best_leaves;
            if(options.tie_mode==2){
                if(a.sum_priority!=b.sum_priority)return a.sum_priority<b.sum_priority;
                if(a.sum_remaining!=b.sum_remaining)return a.sum_remaining<b.sum_remaining;
            }
            if (priority(a.state) != priority(b.state)) return priority(a.state) < priority(b.state);
            if (a.state.remaining_count() != b.state.remaining_count()) return a.state.remaining_count() < b.state.remaining_count();
            return words(a.state, b.state);
        };
        std::sort(candidates.begin(), candidates.end(), better);
        std::vector<Candidate> unique;
        std::unordered_set<std::string> present;
        for (auto& candidate : candidates) {
            auto key = candidate.state.state_key();
            if (options.avoid_cycles && expanded.contains(key)) { ++result.cycles_avoided; continue; }
            if (!present.insert(std::move(key)).second) { ++result.deduplicated; continue; }
            unique.push_back(std::move(candidate));
        }
        beam.clear();
        if (!options.diverse) {
            for (unsigned int i = 0; i < std::min<std::size_t>(options.beam, unique.size()); ++i)
                beam.push_back(std::move(unique[i].state));
        } else {
            const auto ordinary = std::min<std::size_t>((options.beam + 1) / 2, unique.size());
            std::vector<bool> selected(unique.size());
            for (unsigned int i = 0; i < ordinary; ++i) {
                beam.push_back(unique[i].state); selected[i] = true;
            }
            std::map<std::pair<std::uint64_t, std::uint64_t>, std::vector<std::size_t>> tiers;
            for (unsigned int i = ordinary; i < unique.size(); ++i)
                tiers[{priority(unique[i].state), unique[i].state.remaining_count()}].push_back(i);
            for (unsigned int round = 0; beam.size() < options.beam; ++round) {
                bool added = false;
                for (const auto& [tier, indices] : tiers)
                    if (round < indices.size() && beam.size() < options.beam) {
                        beam.push_back(unique[indices[round]].state); added = true;
                    }
                if (!added) break;
            }
        }
        std::sort(beam.begin(), beam.end(), words);
    }
    return result;
}
} // namespace hardpair::rolling

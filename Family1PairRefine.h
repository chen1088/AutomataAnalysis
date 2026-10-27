#pragma once
// Deterministic complete local neighborhoods of an already verified pair.
// No result here proves global shortestness. Each evaluated neighborhood is
// generated in full, then every distinct candidate word is profile-tested.
#include "Family1ExactPacked.h"
#include <algorithm>
#include <cstdint>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace family1::refine {

struct Options {
    unsigned int max_deletions = 3;
    // After deleting d<=substituted_deletions positions, allow zero or one
    // substitution in every resulting word. Both input-word neighborhoods
    // are united; collisions within either side are tested too.
    unsigned int substituted_deletions = 0;
    // Alternative complete family: exactly d deletions and at most
    // total_edit_budget-d substitutions for every d=1..total_edit_budget.
    // Insertions are deliberately outside this declared neighborhood.
    unsigned int total_edit_budget = 0;
    bool contiguous_blocks = false;
    bool block_substitution = false;
    std::uint64_t max_catalog_words = 1000000;
    std::uint64_t max_words = 20000000;
    unsigned int max_improvements = 100;
};

struct Neighborhood {
    std::string move;
    unsigned int input_length = 0, output_length = 0, deletions = 0, substitutions = 0;
    unsigned int common_suffix_k = 0, prefix_length = 0;
    unsigned int binary_prefix_k = 0, replaced_prefix_length = 0;
    std::uint64_t candidate_words = 0, evaluated_words = 0, profile_steps = 0;
    bool generated_complete = false, evaluated_complete = false;
    bool refused_by_budget = false, found = false;
    std::string first, second;
};

struct Result {
    std::string first, second;
    std::uint64_t evaluated_words = 0, profile_steps = 0;
    unsigned int initial_length = 0;
    bool local_minimum = false, budget_refused = false, minimality_certified = false;
    std::string counter_scope = "distinct neighborhood words";
    std::vector<Neighborhood> neighborhoods;
    std::vector<std::pair<std::string, std::string>> improvements;
};

inline std::uint64_t bounded_choose(unsigned int n, unsigned int d, std::uint64_t limit)
{
    if (d > n) return 0;
    d = std::min(d, n - d);
    std::uint64_t value = 1;
    for (unsigned int i = 1; i <= d; ++i) {
        if (value > std::numeric_limits<std::uint64_t>::max() / (n - d + i)) return limit + 1;
        value = value * (n - d + i) / i;
        if (value > limit) return limit + 1;
    }
    return value;
}

inline std::set<std::string> deleted_words(const std::string& word, unsigned int deletions)
{
    std::set<std::string> result;
    std::string current;
    current.reserve(word.size() - deletions);
    const auto visit = [&](auto&& self, unsigned int position, unsigned int left) -> void {
        if (left > word.size() - position) return;
        if (position == word.size()) {
            if (!left) result.insert(current);
            return;
        }
        if (left) self(self, position + 1, left - 1);
        if (word.size() - position > left) {
            current.push_back(word[position]);
            self(self, position + 1, left);
            current.pop_back();
        }
    };
    visit(visit, 0, deletions);
    return result;
}

inline Neighborhood test_catalog(const ExactPackedProduct& product, std::set<std::string>& words,
                                  Neighborhood result, std::uint64_t remaining_work)
{
    result.generated_complete = true;
    result.candidate_words = words.size();
    if (words.size() > remaining_work) {
        result.refused_by_budget = true;
        return result; // No candidate has been evaluated.
    }
    using Profile = ExactPackedProduct::Profile;
    struct Hash {
        std::size_t operator()(const Profile& profile) const {
            std::uint64_t hash = 1469598103934665603ULL;
            for (auto plane : profile) {
                hash ^= plane;
                hash *= 1099511628211ULL;
                hash ^= hash >> 32;
            }
            return static_cast<std::size_t>(hash);
        }
    };
    std::unordered_map<Profile, std::string_view, Hash> first;
    first.reserve(words.size());
    std::vector<Profile> prefix(result.output_length + 1);
    prefix[0] = product.evaluate("");
    std::string previous;
    for (const auto& word : words) {
        std::size_t common = 0;
        while (common < previous.size() && common < word.size() && previous[common] == word[common]) ++common;
        for (auto depth = common; depth < word.size(); ++depth) {
            prefix[depth + 1] = product.step(prefix[depth], word[depth] == '1');
            ++result.profile_steps;
        }
        auto [it, inserted] = first.emplace(prefix.back(), word);
        if (!inserted && it->second != word) {
            const std::pair<std::string, std::string> pair{std::string(it->second), word};
            if (!result.found || pair < std::pair{result.first, result.second}) {
                result.found = true; result.first = pair.first; result.second = pair.second;
            }
        }
        previous = word;
        ++result.evaluated_words;
    }
    result.evaluated_complete = result.evaluated_words == result.candidate_words;
    if (!result.evaluated_complete) throw std::logic_error("partial refinement neighborhood");
    return result;
}

inline Result refine_pair(const ExactPackedProduct& product, std::string first, std::string second,
                          const Options& options = {})
{
    if (first.empty() || first.size() != second.size() || first == second
        || first.find_first_not_of("01") != std::string::npos
        || second.find_first_not_of("01") != std::string::npos
        || !options.max_catalog_words || !options.max_words || !options.max_improvements)
        throw std::invalid_argument("refinement requires a nonempty distinct verified equal-length binary pair and positive budgets");
    if (product.evaluate(first) != product.evaluate(second))
        throw std::invalid_argument("refinement input is not a hard pair");
    if (second < first) std::swap(first, second);
    Result result;
    result.first = std::move(first); result.second = std::move(second);
    result.initial_length = static_cast<unsigned int>(result.first.size());
    const auto accept = [&](Neighborhood neighborhood) {
        result.evaluated_words += neighborhood.evaluated_words;
        result.profile_steps += neighborhood.profile_steps;
        result.budget_refused |= neighborhood.refused_by_budget;
        const auto improved = neighborhood.found;
        if (improved) {
            if (neighborhood.first.size() >= result.first.size())
                throw std::logic_error("refinement did not shorten the pair");
            result.first = neighborhood.first; result.second = neighborhood.second;
            result.improvements.emplace_back(result.first, result.second);
        }
        result.neighborhoods.push_back(std::move(neighborhood));
        return improved;
    };
    const auto attempt = [&](unsigned int d, bool contiguous, unsigned int substitutions) {
        Neighborhood neighborhood;
        const auto n = static_cast<unsigned int>(result.first.size());
        neighborhood.input_length = n; neighborhood.output_length = n - d;
        neighborhood.deletions = d; neighborhood.substitutions = substitutions;
        neighborhood.move = contiguous ? "contiguous-block" : "arbitrary-deletions";
        if (substitutions) neighborhood.move += "-and-bounded-substitutions";
        const auto deletions = contiguous ? std::uint64_t(n - d + 1)
            : bounded_choose(n, d, options.max_catalog_words);
        std::uint64_t variants = 0;
        for (unsigned int s = 0; s <= std::min(substitutions, n - d); ++s) {
            const auto count = bounded_choose(n - d, s, options.max_catalog_words);
            if (count > options.max_catalog_words - std::min(options.max_catalog_words, variants)) {
                variants = options.max_catalog_words + 1; break;
            }
            variants += count;
        }
        if (deletions > options.max_catalog_words / (2 * variants)) {
            neighborhood.refused_by_budget = true;
            return accept(std::move(neighborhood)); // Conservative bound, no generation started.
        }
        std::set<std::string> words;
        for (const auto* base : {&result.first, &result.second}) {
            if (contiguous) {
                for (unsigned int position = 0; position + d <= n; ++position)
                    words.insert(base->substr(0, position) + base->substr(position + d));
            } else {
                auto generated = deleted_words(*base, d);
                words.insert(generated.begin(), generated.end());
            }
        }
        if (substitutions) {
            const std::vector<std::string> original(words.begin(), words.end());
            for (auto word : original)
                {
                    const auto mutate = [&](auto&& self, unsigned int start, unsigned int left) -> void {
                        words.insert(word);
                        if (!left) return;
                        for (unsigned int position = start; position < word.size(); ++position) {
                            word[position] = word[position] == '0' ? '1' : '0';
                            self(self, position + 1, left - 1);
                            word[position] = word[position] == '0' ? '1' : '0';
                        }
                    };
                    mutate(mutate, 0, substitutions);
                }
        }
        if (words.size() > options.max_catalog_words)
            throw std::logic_error("refinement catalogue exceeded its conservative size bound");
        return accept(test_catalog(product, words, std::move(neighborhood), options.max_words - result.evaluated_words));
    };
    while (result.improvements.size() < options.max_improvements) {
        bool changed = false;
        const auto n = static_cast<unsigned int>(result.first.size());
        if (n <= 1) { result.local_minimum = true; break; }
        if (options.total_edit_budget) {
            for (unsigned int d = std::min(options.total_edit_budget, n - 1); d && !changed; --d)
                changed = attempt(d, false, options.total_edit_budget - d);
            if (changed) continue;
            result.local_minimum = !result.budget_refused;
            break;
        }
        for (unsigned int d = std::min(options.max_deletions, n - 1); d && !changed; --d)
            changed = attempt(d, false, 0);
        if (changed) continue;
        for (unsigned int d = std::min(options.substituted_deletions, n - 1); d && !changed; --d)
            changed = attempt(d, false, 1);
        if (changed) continue;
        if (options.contiguous_blocks)
            for (unsigned int d = n - 1; d && !changed; --d)
                changed = attempt(d, true, options.block_substitution ? 1 : 0);
        if (changed) continue;
        result.local_minimum = !result.budget_refused;
        break;
    }
    return result;
}

// Local replacement of both tails by every COMMON binary continuation of
// length 0..k, after each distinct prefix pair. This is a declared restricted
// refinement operator, not a four-symbol joint finder. Every started prefix
// window exhausts its complete binary tree even if a positive is found early.
inline Result refine_common_suffix(const ExactPackedProduct& product, std::string first, std::string second,
                                   unsigned int k = 16, std::uint64_t max_nodes = 100000000)
{
    if (!k || k > 24 || !max_nodes || first.empty() || first.size() != second.size() || first == second
        || first.find_first_not_of("01") != std::string::npos || second.find_first_not_of("01") != std::string::npos
        || product.evaluate(first) != product.evaluate(second))
        throw std::invalid_argument("common suffix refinement requires k1..24 and a verified distinct pair");
    if (second < first) std::swap(first, second);
    Result result;
    result.first = std::move(first); result.second = std::move(second);
    result.initial_length = static_cast<unsigned int>(result.first.size());
    result.counter_scope = "common suffix continuations; each continuation tests one word pair";
    for (unsigned int round = 0; round < 100; ++round) {
        const auto old_first = result.first, old_second = result.second;
        const auto n = static_cast<unsigned int>(old_first.size());
        unsigned int first_difference = 0;
        while (first_difference < n && old_first[first_difference] == old_second[first_difference]) ++first_difference;
        bool improved = false;
        for (unsigned int r = first_difference + 1; r < n; ++r) {
            const auto span = std::min(k, n - r - 1);
            const auto candidates = (std::uint64_t{1} << (span + 1)) - 1;
            Neighborhood neighborhood;
            neighborhood.move = "complete-common-suffix-replacement";
            neighborhood.input_length = n; neighborhood.output_length = 0;
            neighborhood.common_suffix_k = span; neighborhood.prefix_length = r;
            neighborhood.candidate_words = candidates; neighborhood.generated_complete = true;
            if (candidates > max_nodes - result.evaluated_words) {
                neighborhood.refused_by_budget = true; result.budget_refused = true;
                result.neighborhoods.push_back(std::move(neighborhood)); continue;
            }
            const auto a = old_first.substr(0, r), b = old_second.substr(0, r);
            std::string suffix;
            const auto visit = [&](auto&& self, const ExactPackedProduct::Profile& left,
                                   const ExactPackedProduct::Profile& right, unsigned int depth) -> void {
                ++neighborhood.evaluated_words;
                if (left == right) {
                    const auto first_word = a + suffix, second_word = b + suffix;
                    if (!neighborhood.found || first_word.size() < neighborhood.first.size()
                        || (first_word.size() == neighborhood.first.size()
                            && std::pair{first_word, second_word} < std::pair{neighborhood.first, neighborhood.second})) {
                        neighborhood.found = true; neighborhood.first = first_word;
                        neighborhood.second = second_word; neighborhood.output_length = first_word.size();
                    }
                }
                if (depth == span) return;
                for (bool bit : {false, true}) {
                    suffix.push_back(bit ? '1' : '0');
                    auto next_left = product.step(left, bit), next_right = product.step(right, bit);
                    neighborhood.profile_steps += 2;
                    self(self, next_left, next_right, depth + 1);
                    suffix.pop_back();
                }
            };
            visit(visit, product.evaluate(a), product.evaluate(b), 0);
            neighborhood.evaluated_complete = neighborhood.evaluated_words == candidates;
            if (!neighborhood.evaluated_complete) throw std::logic_error("partial common suffix replacement window");
            result.evaluated_words += neighborhood.evaluated_words; result.profile_steps += neighborhood.profile_steps;
            if (neighborhood.found && (neighborhood.first.size() < result.first.size()
                || (neighborhood.first.size() == result.first.size()
                    && std::pair{neighborhood.first, neighborhood.second} < std::pair{result.first, result.second}))) {
                result.first = neighborhood.first; result.second = neighborhood.second; improved = true;
            }
            result.neighborhoods.push_back(std::move(neighborhood));
        }
        if (!improved) { result.local_minimum = !result.budget_refused; break; }
        result.improvements.emplace_back(result.first, result.second);
    }
    return result;
}

// For each cut r, keep either original suffix after r and replace the entire
// prefix by EVERY binary word of each length d=0..min(k,r-1). At each d, test
// collisions among the full union of both suffix families, including within
// either family. These are complete finite local neighborhoods, not hints
// from a reference pair. k counts binary replacement-prefix symbols.
inline Result refine_prefix_replacements(const ExactPackedProduct& product, std::string first, std::string second,
                                         unsigned int k = 16, std::uint64_t max_words = 100000000)
{
    if (!k || k > 24 || !max_words || first.empty() || first.size() != second.size() || first == second
        || first.find_first_not_of("01") != std::string::npos || second.find_first_not_of("01") != std::string::npos
        || product.evaluate(first) != product.evaluate(second))
        throw std::invalid_argument("prefix replacement requires k1..24 and a verified distinct pair");
    if (second < first) std::swap(first, second);
    using Profile = ExactPackedProduct::Profile;
    struct Hash {
        std::size_t operator()(const Profile& profile) const {
            std::uint64_t hash = 1469598103934665603ULL;
            for (auto plane : profile) { hash ^= plane; hash *= 1099511628211ULL; hash ^= hash >> 32; }
            return static_cast<std::size_t>(hash);
        }
    };
    Result result;
    result.first = std::move(first); result.second = std::move(second);
    result.initial_length = static_cast<unsigned int>(result.first.size());
    result.counter_scope = "replacement words, deduplicated per cut and total output length";
    const auto empty = product.evaluate("");
    for (unsigned int round = 0; round < 100; ++round) {
        const auto old_first = result.first, old_second = result.second;
        const auto n = static_cast<unsigned int>(old_first.size());
        bool improved = false;
        for (unsigned int r = n; r; --r) {
            const auto span = std::min(k, r - 1);
            std::vector<std::string> suffixes{old_first.substr(r), old_second.substr(r)};
            std::sort(suffixes.begin(), suffixes.end());
            suffixes.erase(std::unique(suffixes.begin(), suffixes.end()), suffixes.end());
            const auto candidates = ((std::uint64_t{1} << (span + 1)) - 1) * suffixes.size();
            Neighborhood neighborhood;
            neighborhood.move = "complete-binary-prefix-replacement";
            neighborhood.input_length = n; neighborhood.output_length = 0;
            neighborhood.binary_prefix_k = span; neighborhood.replaced_prefix_length = r;
            neighborhood.candidate_words = candidates; neighborhood.generated_complete = true;
            if (candidates > max_words - result.evaluated_words) {
                neighborhood.refused_by_budget = true; result.budget_refused = true;
                result.neighborhoods.push_back(std::move(neighborhood)); continue;
            }
            std::vector<std::unordered_map<Profile, std::string, Hash>> first_by_depth(span + 1);
            for (unsigned int depth = 0; depth <= span; ++depth)
                first_by_depth[depth].reserve((std::size_t{1} << depth) * suffixes.size());
            std::string prefix;
            const auto visit = [&](auto&& self, const Profile& profile, unsigned int depth) -> void {
                for (const auto& suffix : suffixes) {
                    auto final = profile;
                    for (auto bit : suffix) { final = product.step(final, bit == '1'); ++neighborhood.profile_steps; }
                    const auto word = prefix + suffix;
                    auto [it, inserted] = first_by_depth[depth].emplace(std::move(final), word);
                    if (!inserted && it->second != word) {
                        const std::pair pair{it->second, word};
                        if (!neighborhood.found || word.size() < neighborhood.first.size()
                            || (word.size() == neighborhood.first.size()
                                && pair < std::pair{neighborhood.first, neighborhood.second})) {
                            neighborhood.found = true; neighborhood.first = pair.first;
                            neighborhood.second = pair.second; neighborhood.output_length = word.size();
                        }
                    }
                    ++neighborhood.evaluated_words;
                }
                if (depth == span) return;
                for (bool bit : {false, true}) {
                    prefix.push_back(bit ? '1' : '0');
                    auto next = product.step(profile, bit);
                    ++neighborhood.profile_steps;
                    self(self, next, depth + 1);
                    prefix.pop_back();
                }
            };
            visit(visit, empty, 0);
            neighborhood.evaluated_complete = neighborhood.evaluated_words == candidates;
            if (!neighborhood.evaluated_complete) throw std::logic_error("partial prefix replacement neighborhood");
            result.evaluated_words += neighborhood.evaluated_words; result.profile_steps += neighborhood.profile_steps;
            if (neighborhood.found && (neighborhood.first.size() < result.first.size()
                || (neighborhood.first.size() == result.first.size()
                    && std::pair{neighborhood.first, neighborhood.second} < std::pair{result.first, result.second}))) {
                result.first = neighborhood.first; result.second = neighborhood.second; improved = true;
            }
            result.neighborhoods.push_back(std::move(neighborhood));
        }
        if (!improved) { result.local_minimum = !result.budget_refused; break; }
        result.improvements.emplace_back(result.first, result.second);
    }
    return result;
}

}

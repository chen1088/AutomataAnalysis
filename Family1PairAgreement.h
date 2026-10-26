#pragma once
// Exact all-static-mask progress for a fixed pair and its common suffixes.
// Hashes are not used. This header does not accept a witness: callers still
// independently replay every positive collision before recording an upper.
#include "Family1LargeGraph.h"
#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <memory>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace family1 {

class ExactPairAgreement;

class PairAgreementContext {
public:
    explicit PairAgreementContext(const LargeGraph& graph) : graph_(graph)
    {
        graph_.validate();
        states_ = graph_.size();
        masks_ = std::uint32_t{1} << states_;
        blocks_ = (masks_ + 63) / 64;
        valid_ = masks_ < 64 ? (std::uint64_t{1} << masks_) - 1 : ~std::uint64_t{0};
        permutation_masks_.assign(blocks_, 0);
        std::array<std::vector<std::pair<unsigned int, unsigned int>>, 20> incoming;
        for (unsigned int source = 0; source < states_; ++source)
            for (unsigned int port = 0; port < 2; ++port)
                incoming[graph_.ports[source][port]].push_back({source, port});
        // Two bijective letter maps give total seed indegree2 at every vertex.
        // Arbitrary-indegree seeds are supported; they simply have no such mask.
        for (unsigned int state = 0; state < states_; ++state)
            if (incoming[state].size() != 2) return;
        for (unsigned int block = 0; block < blocks_; ++block) {
            auto good = valid_;
            for (unsigned int target = 0; target < states_ && good; ++target) {
                const auto [s, p] = incoming[target][0];
                const auto [r, q] = incoming[target][1];
                const auto different = sigma(s, block) ^ sigma(r, block);
                // Exactly one of the incoming port occurrences is selected:
                // sigma[s] XOR sigma[r] = 1 XOR p XOR q.
                good &= (1U ^ p ^ q) ? different : ~different;
            }
            permutation_masks_[block] = good;
            permutation_count_ += std::popcount(good);
        }
    }

    std::uint64_t mask_count() const { return masks_; }
    std::uint64_t permutation_mask_count() const { return permutation_count_; }
    unsigned int state_count() const { return states_; }
    unsigned int block_count() const { return blocks_; }
    unsigned int transition(std::uint32_t mask, unsigned int state, bool input) const
    {
        if (mask >= masks_ || state >= states_) throw std::out_of_range("static mask/state outside graph");
        return graph_.ports[state][static_cast<unsigned int>(input) ^ ((mask >> state) & 1U)];
    }
    bool is_permutation_mask(std::uint32_t mask) const
    {
        if (mask >= masks_) throw std::out_of_range("static mask outside graph");
        return (permutation_masks_[mask / 64] >> (mask % 64)) & 1U;
    }

private:
    friend class ExactPairAgreement;
    static std::uint64_t sigma(unsigned int state, unsigned int block)
    {
        constexpr std::array<std::uint64_t, 6> pattern{
            0xaaaaaaaaaaaaaaaaULL, 0xccccccccccccccccULL, 0xf0f0f0f0f0f0f0f0ULL,
            0xff00ff00ff00ff00ULL, 0xffff0000ffff0000ULL, 0xffffffff00000000ULL};
        return state < 6 ? pattern[state]
            : ((block >> (state - 6)) & 1U) ? ~std::uint64_t{0} : 0;
    }

    LargeGraph graph_;
    unsigned int states_ = 0, masks_ = 0, blocks_ = 0;
    std::uint64_t valid_ = 0, permutation_count_ = 0;
    std::vector<std::uint64_t> permutation_masks_;
};

class ExactPairAgreement {
public:
    ExactPairAgreement(std::shared_ptr<const PairAgreementContext> context,
                       const std::string& first, const std::string& second)
        : context_(std::move(context))
    {
        if (!context_) throw std::invalid_argument("missing pair agreement context");
        if (first == second || first.size() != second.size()
            || first.find_first_not_of("01") != std::string::npos
            || second.find_first_not_of("01") != std::string::npos)
            throw std::invalid_argument("pair requires distinct equal-length binary words");
        const auto count = static_cast<std::size_t>(context_->blocks_) * context_->states_;
        left_.resize(count);
        right_.resize(count);
        active_.assign(context_->blocks_, context_->valid_);
        for (unsigned int block = 0; block < context_->blocks_; ++block) {
            auto* left = left_.data() + static_cast<std::size_t>(block) * context_->states_;
            auto* right = right_.data() + static_cast<std::size_t>(block) * context_->states_;
            left[0] = right[0] = context_->valid_;
            for (char input : first) propagate_word(left, block, input == '1');
            for (char input : second) propagate_word(right, block, input == '1');
            remove_merged(block, left, right);
            permutation_mismatch_ += std::popcount(active_[block] & context_->permutation_masks_[block]);
            if (active_[block]) active_blocks_.push_back(block);
        }
        release_completed_planes();
    }

    std::uint64_t merged_count() const { return merged_; }
    std::uint64_t mask_count() const { return context_->mask_count(); }
    std::uint64_t remaining_count() const { return mask_count() - merged_count(); }
    std::uint64_t permutation_mismatch_count() const { return permutation_mismatch_; }
    bool all_merged() const { return merged_ == mask_count(); }
    std::size_t active_block_count() const { return active_blocks_.size(); }
    std::size_t storage_bytes() const
    {
        return sizeof(std::uint64_t) * (left_.capacity() + right_.capacity() + active_.capacity())
            + sizeof(unsigned int) * active_blocks_.capacity();
    }

    // Export only active coordinates, for an exact shortest-suffix tail search.
    // IDs are original static masks, preserving all multiplicities and flips.
    std::vector<std::array<std::uint32_t, 3>> remaining_coordinate_pairs(
        std::size_t limit = std::numeric_limits<std::size_t>::max()) const
    {
        std::vector<std::array<std::uint32_t, 3>> result;
        result.reserve(std::min<std::size_t>(static_cast<std::size_t>(remaining_count()), limit));
        if (!limit) return result;
        for (auto block : active_blocks_) {
            auto lanes = active_[block];
            const auto start = static_cast<std::size_t>(block) * context_->states_;
            while (lanes) {
                const auto lane = std::countr_zero(lanes);
                const auto bit = std::uint64_t{1} << lane;
                unsigned int left = context_->states_, right = context_->states_;
                for (unsigned int state = 0; state < context_->states_; ++state) {
                    if (left_[start + state] & bit) left = state;
                    if (right_[start + state] & bit) right = state;
                }
                if (left == context_->states_ || right == context_->states_ || left == right)
                    throw std::logic_error("invalid active coordinate export");
                result.push_back({block * 64 + lane, left, right});
                if (result.size() >= limit) return result;
                lanes &= lanes - 1;
            }
        }
        return result;
    }

    // Already merged coordinates stay equal under every common suffix; their
    // actual states are discarded. Unmerged states remain available for audits.
    bool agrees_on_mask(std::uint32_t mask) const
    {
        if (mask >= mask_count()) throw std::out_of_range("static mask outside graph");
        return !(active_[mask / 64] & (std::uint64_t{1} << (mask % 64)));
    }
    std::optional<std::pair<unsigned int, unsigned int>> unmerged_endpoints(std::uint32_t mask) const
    {
        if (agrees_on_mask(mask)) return std::nullopt;
        const auto start = static_cast<std::size_t>(mask / 64) * context_->states_;
        const auto lane = std::uint64_t{1} << (mask % 64);
        unsigned int left = context_->states_, right = context_->states_;
        for (unsigned int state = 0; state < context_->states_; ++state) {
            if (left_[start + state] & lane) left = state;
            if (right_[start + state] & lane) right = state;
        }
        if (left == context_->states_ || right == context_->states_ || left == right)
            throw std::logic_error("invalid unmerged endpoint profile");
        return std::pair{left, right};
    }

    ExactPairAgreement append_common(bool input) const
    {
        ExactPairAgreement result(*this);
        result.advance(input);
        return result;
    }

private:
    void propagate_word(std::uint64_t* state, unsigned int block, bool input) const
    {
        std::array<std::uint64_t, 20> next{};
        for (unsigned int source = 0; source < context_->states_; ++source) {
            const auto& row = context_->graph_.ports[source];
            if (row[0] == row[1]) next[row[0]] |= state[source];
            else {
                auto one = PairAgreementContext::sigma(source, block);
                if (input) one = ~one;
                next[row[0]] |= state[source] & ~one;
                next[row[1]] |= state[source] & one;
            }
        }
        for (unsigned int target = 0; target < context_->states_; ++target) state[target] = next[target];
    }

    std::uint64_t remove_merged(unsigned int block, std::uint64_t* left, std::uint64_t* right)
    {
        std::uint64_t equal = 0;
        for (unsigned int state = 0; state < context_->states_; ++state) equal |= left[state] & right[state];
        equal &= active_[block];
        merged_ += std::popcount(equal);
        active_[block] &= ~equal;
        for (unsigned int state = 0; state < context_->states_; ++state) {
            left[state] &= active_[block];
            right[state] &= active_[block];
        }
        return equal;
    }

    void advance(bool input)
    {
        std::size_t kept = 0;
        for (auto block : active_blocks_) {
            auto* left = left_.data() + static_cast<std::size_t>(block) * context_->states_;
            auto* right = right_.data() + static_cast<std::size_t>(block) * context_->states_;
            propagate_word(left, block, input);
            propagate_word(right, block, input);
            const auto newly_equal = remove_merged(block, left, right);
            if (newly_equal & context_->permutation_masks_[block])
                throw std::logic_error("a common letter merged unequal permutation coordinates");
            if (active_[block]) active_blocks_[kept++] = block;
        }
        active_blocks_.resize(kept);
        release_completed_planes();
    }

    void release_completed_planes()
    {
        if (active_blocks_.empty()) {
            std::vector<std::uint64_t>().swap(left_);
            std::vector<std::uint64_t>().swap(right_);
        }
    }

    std::shared_ptr<const PairAgreementContext> context_;
    std::vector<std::uint64_t> left_, right_, active_;
    std::vector<unsigned int> active_blocks_;
    std::uint64_t merged_ = 0, permutation_mismatch_ = 0;
};

}

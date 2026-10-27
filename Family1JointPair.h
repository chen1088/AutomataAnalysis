#pragma once
// Complete ordered endpoint profiles for independent left/right input words.
// Agreement is not absorbing: appending 01 or 10 may separate equal endpoints.
// Every compressed coordinate remains stored, including currently equal ones.
#include "Family1ExactPacked.h"
#include "Family1PairAgreement.h"
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>

namespace family1 {

// Build once per graph, then share the immutable compressed bit selector
// across every state and deterministic start in a permutation-first run.
// The subset contains ALL masks with two bijective letter maps. Omitted
// coincident-port bits do not affect that property or the exact multiplicity.
inline std::shared_ptr<const ExactPackedProduct::MaskSelection> permutation_priority_selection(
    const std::shared_ptr<const ExactPackedProduct>& product, const LargeGraph& graph)
{
    if (!product || product->graph_key() != graph.key())
        throw std::invalid_argument("permutation selection graph differs from packed product");
    PairAgreementContext context(graph);
    std::vector<std::uint32_t> masks;
    masks.reserve(static_cast<std::size_t>(context.permutation_mask_count()));
    for (std::uint32_t mask = 0; mask < context.mask_count(); ++mask)
        if (context.is_permutation_mask(mask)) masks.push_back(mask);
    auto result = std::make_shared<const ExactPackedProduct::MaskSelection>(product->select_mask_classes(masks));
    if (result->selected_count() != context.permutation_mask_count())
        throw std::logic_error("compressed permutation selection lost original-mask multiplicity");
    return result;
}

class JointPairState {
public:
    using Profile = ExactPackedProduct::Profile;
    using PrioritySelection = ExactPackedProduct::MaskSelection;

    explicit JointPairState(std::shared_ptr<const ExactPackedProduct> product,
                            std::string first = "", std::string second = "",
                            std::shared_ptr<const PrioritySelection> priority_selection = {})
        : product_(std::move(product)), priority_selection_(std::move(priority_selection)),
          first_(std::move(first)), second_(std::move(second))
    {
        if (!product_) throw std::invalid_argument("missing joint-pair product");
        if (first_.size() != second_.size())
            throw std::invalid_argument("joint pair requires equal-length words");
        left_ = product_->evaluate(first_);
        right_ = product_->evaluate(second_);
        distinct_ = first_ != second_;
        remaining_ = product_->disagreement_count(left_, right_);
        if (priority_selection_) priority_remaining_ = product_->disagreement_count(left_, right_, *priority_selection_);
    }

    JointPairState(std::shared_ptr<const ExactPackedProduct> product, unsigned int m,
                   std::shared_ptr<const PrioritySelection> priority_selection = {})
        : JointPairState(std::move(product), "", "", std::move(priority_selection))
    {
        if (m != product_->state_count())
            throw std::invalid_argument("joint-pair size differs from product");
    }

    JointPairState append_pair(bool left, bool right) const
    {
        auto first = first_, second = second_;
        first.push_back(left ? '1' : '0');
        second.push_back(right ? '1' : '0');
        return JointPairState(product_, product_->step(left_, left), product_->step(right_, right),
                              std::move(first), std::move(second), distinct_ || left != right, priority_selection_);
    }

    std::uint64_t remaining_count() const { return remaining_; }
    std::uint64_t priority_remaining_count() const
    {
        if (!priority_selection_) throw std::logic_error("joint pair has no permutation-priority selection");
        return priority_remaining_;
    }
    std::uint64_t priority_mask_count() const
    {
        if (!priority_selection_) throw std::logic_error("joint pair has no permutation-priority selection");
        return priority_selection_->selected_count();
    }
    std::uint64_t mask_count() const { return product_->full_mask_count(); }
    bool distinct() const { return distinct_; }
    const std::string& first_word() const { return first_; }
    const std::string& second_word() const { return second_; }
    const Profile& left_profile() const { return left_; }
    const Profile& right_profile() const { return right_; }
    const std::shared_ptr<const ExactPackedProduct>& product() const { return product_; }

    // Exact Markov-state key, scoped to one product context. Word histories
    // need not enter a BFS visited key, but their distinctness must. Neither a
    // hash nor the disagreement count replaces the complete ordered profiles.
    std::string state_key() const
    {
        std::string result;
        result.reserve(3 + 8 * (left_.size() + right_.size()));
        result.push_back(static_cast<char>(product_->state_count()));
        result.push_back(static_cast<char>(product_->effective_mask_bits()));
        result.push_back(distinct_ ? '\1' : '\0');
        for (const auto* profile : {&left_, &right_})
            for (auto plane : *profile)
                for (unsigned int byte = 0; byte < 8; ++byte)
                    result.push_back(static_cast<char>((plane >> (8 * byte)) & 255));
        return result;
    }

    std::string key() const { return state_key(); }

    bool operator==(const JointPairState& other) const
    {
        return product_.get() == other.product_.get() && priority_selection_.get() == other.priority_selection_.get()
            && distinct_ == other.distinct_
            && left_ == other.left_ && right_ == other.right_;
    }

private:
    JointPairState(std::shared_ptr<const ExactPackedProduct> product, Profile left, Profile right,
                   std::string first, std::string second, bool distinct,
                   std::shared_ptr<const PrioritySelection> priority_selection)
        : product_(std::move(product)), priority_selection_(std::move(priority_selection)),
          left_(std::move(left)), right_(std::move(right)),
          first_(std::move(first)), second_(std::move(second)), distinct_(distinct),
          remaining_(product_->disagreement_count(left_, right_))
    {
        if (priority_selection_) priority_remaining_ = product_->disagreement_count(left_, right_, *priority_selection_);
    }

    std::shared_ptr<const ExactPackedProduct> product_;
    std::shared_ptr<const PrioritySelection> priority_selection_;
    Profile left_, right_;
    std::string first_, second_;
    bool distinct_ = false;
    std::uint64_t remaining_ = 0, priority_remaining_ = 0;
};

}

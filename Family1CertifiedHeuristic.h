#pragma once
// Upper-candidate adapter for the original union of complete Family 1 closures.
// This scalar baseline deliberately keeps every indexed mask, including masks
// whose behavior coincides. Beam retention supplies no lower-bound evidence.
#include "Family1Certified.h"
#include "HardPairJointFinder.h"
#include <memory>
#include <new>
#include <stdexcept>
#include <utility>

namespace family1::certified {

struct UpperResult {
    // True only after scalar full-family verification succeeds.
    bool candidate = false;
    std::array<std::string, 2> witness{};
    std::string status = "unresolved", reason;
    std::uint64_t expanded_nodes = 0, coordinates = 0;
    hardpair::joint::Result search;
    Verification verification;
};

namespace heuristic_detail {
struct BudgetStop {};
struct Context {
    const Family* family;
    Budget* budget;
    std::vector<Observer> observers;
    std::uint64_t expanded_nodes = 0;
};

// The generic finder copies these states while enumerating complete windows.
// Equality ignores words only after preserving their distinctness flag and
// the complete ordered left/right profiles for this exact context.
class PairState {
public:
    explicit PairState(std::shared_ptr<Context> context)
        : context_(std::move(context))
    {
        if (!context_->budget->add_state()) throw BudgetStop{};
        endpoints_.reserve(context_->observers.size() * 2);
        for (const auto observer : context_->observers) {
            const auto root = context_->family->seeds()[observer.seed].root;
            endpoints_.push_back(root);
            endpoints_.push_back(root);
        }
    }

    PairState append_pair(bool left, bool right) const
    {
        auto& budget = *context_->budget;
        if (!budget.add_state()) throw BudgetStop{};
        PairState result = *this;
        result.first_.push_back(left ? '1' : '0');
        result.second_.push_back(right ? '1' : '0');
        result.distinct_ = distinct_ || left != right;
        result.remaining_ = 0;
        for (std::size_t i = 0; i < context_->observers.size(); ++i) {
            // One unit is one paired coordinate transition in this adapter.
            // Per-coordinate checks also make large families interruptible.
            if (!budget.add_work()) throw BudgetStop{};
            const auto observer = context_->observers[i];
            const auto& ports = context_->family->seeds()[observer.seed].ports;
            const auto u = endpoints_[2*i], v = endpoints_[2*i+1];
            const auto next_u = ports[u][unsigned(left) ^ ((observer.mask >> u) & 1)];
            const auto next_v = ports[v][unsigned(right) ^ ((observer.mask >> v) & 1)];
            result.endpoints_[2*i] = next_u;
            result.endpoints_[2*i+1] = next_v;
            result.remaining_ += next_u != next_v;
        }
        ++context_->expanded_nodes;
        return result;
    }

    std::uint64_t remaining_count() const { return remaining_; }
    std::uint64_t mask_count() const { return context_->observers.size(); }
    bool distinct() const { return distinct_; }
    const std::string& first_word() const { return first_; }
    const std::string& second_word() const { return second_; }

    std::string state_key() const
    {
        std::string key;
        key.reserve(1 + 4 * endpoints_.size());
        key.push_back(distinct_ ? '\1' : '\0');
        for (const auto endpoint : endpoints_)
            for (unsigned shift = 0; shift < 32; shift += 8)
                key.push_back(static_cast<char>((endpoint >> shift) & 255));
        return key;
    }
    std::string key() const { return state_key(); }
    bool operator==(const PairState& other) const
    {
        return context_.get() == other.context_.get()
            && distinct_ == other.distinct_ && endpoints_ == other.endpoints_;
    }

private:
    std::shared_ptr<Context> context_;
    std::vector<unsigned> endpoints_;
    std::string first_, second_;
    bool distinct_ = false;
    std::uint64_t remaining_ = 0;
};
} // namespace heuristic_detail

// All resource counters are cumulative in the supplied budget. Coordinate
// creation and generated pair states both consume max_states; transitions
// consume one work unit per original indexed observer. If a budget interrupts
// a window, the unfinished search supplies neither a bound nor a witness.
inline UpperResult find_upper(const Family& family, const hardpair::joint::Options& options,
                              Budget& budget)
{
    if (options.prioritize_permutation)
        throw std::invalid_argument("certified multi-seed heuristic supports total-disagreement ranking only");
    UpperResult result;
    auto context = std::make_shared<heuristic_detail::Context>();
    context->family = &family;
    context->budget = &budget;
    try {
        for (std::size_t seed = 0; seed < family.seeds().size(); ++seed) {
            const auto masks = std::uint64_t{1} << family.seeds()[seed].ports.size();
            for (std::uint64_t mask = 0; mask < masks; ++mask) {
                if (!budget.add_state()) throw heuristic_detail::BudgetStop{};
                context->observers.push_back({seed, mask});
            }
        }
        result.coordinates = context->observers.size();
        result.search = hardpair::joint::find_pair(heuristic_detail::PairState(context), options);
        result.expanded_nodes = context->expanded_nodes;
        if (!result.search.found) {
            result.reason = result.search.interrupted ? "interrupted"
                : result.search.expansion_limit_reached ? "heuristic-expansion-cap"
                : "heuristic-length-cap";
            return result;
        }
        result.verification = family.verify(result.search.first, result.search.second, budget);
        if (result.verification.status == "verified") {
            result.candidate = true;
            result.status = "witness";
            result.witness = {result.search.first, result.search.second};
        } else if (result.verification.status == "separated") {
            // Complete adapter profiles and independent replay must agree.
            throw std::logic_error("multi-seed heuristic candidate failed scalar verification");
        } else result.reason = result.verification.reason;
    } catch (const heuristic_detail::BudgetStop&) {
        result.reason = budget.reason;
    } catch (const std::bad_alloc&) {
        budget.reason = "allocation-failed";
        result.reason = budget.reason;
    }
    result.coordinates = context->observers.size();
    result.expanded_nodes = context->expanded_nodes;
    return result;
}

} // namespace family1::certified

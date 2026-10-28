#include "Family1Signatures.h"
#include <algorithm>
#include <iterator>
#include <limits>
#include <new>
#include <set>
#include <stdexcept>
#include <utility>

namespace family1::certified {

bool SignatureNode::operator<(const SignatureNode& other) const
{
    if (state < other.state) return true;
    if (other.state < state) return false;
    return signature < other.signature;
}

std::string signature_name(SignatureKind kind)
{
    switch (kind) {
    case SignatureKind::Count: return "count";
    case SignatureKind::FirstDifference: return "first-difference";
    }
    throw std::invalid_argument("unknown signature kind");
}

Signature advance_signature(const Signature& signature, SignatureKind kind,
                            unsigned position, unsigned left, unsigned right)
{
    if (left > 1 || right > 1)
        throw std::invalid_argument("signature updates require binary paired moves");
    if (position >= static_cast<unsigned>(std::numeric_limits<int>::max()))
        throw std::invalid_argument("signature horizon exceeds integer range");
    Signature next = signature;
    if (kind == SignatureKind::FirstDifference && signature[2] < 0 && left != right) {
        next[2] = static_cast<int>(position);
        next[3] = signature[0];
    }
    next[0] += static_cast<int>(left);
    next[1] += static_cast<int>(right);
    return next;
}

SignatureResult signature_intersection(
    const Family& family, const std::vector<std::vector<Observer>>& groups,
    unsigned horizon, SignatureKind kind, Budget& budget,
    const std::string& prefix_u, const std::string& prefix_v)
{
    if (groups.empty())
        throw std::invalid_argument("signature certificate needs at least one observer group");
    if (horizon > static_cast<unsigned>(std::numeric_limits<int>::max()))
        throw std::invalid_argument("signature horizon exceeds integer range");
    // Also validates the enumeration value before creating a proof.
    (void)signature_name(kind);
    if (prefix_u.size() != prefix_v.size()
        || prefix_u.find_first_not_of("01") != std::string::npos
        || prefix_v.find_first_not_of("01") != std::string::npos)
        throw std::invalid_argument("signature prefixes must be equal-length binary words");
    for (const auto& observers : groups) family.validate_selection(observers);

    SignatureResult result;
    result.kind = kind;
    result.horizon = horizon;
    result.prefixes = {prefix_u, prefix_v};
    auto unresolved = [&]() {
        result.status = "unresolved";
        result.reason = budget.reason;
        // Partial tables never represent exclusions. Completed earlier groups
        // can be recomputed on a subsequent pass; keeping them is unnecessary.
        result.groups.clear();
        result.intersection.clear();
        return result;
    };

    try {
    for (const auto& observers : groups) {
        if (!budget.check()) return unresolved();
        SignatureGroupProof proof;
        proof.observers = observers;
        State initial = family.initial(observers);
        for (std::size_t position = 0; position < prefix_u.size(); ++position) {
            if (!budget.add_work()) return unresolved();
            initial = family.step(observers, initial,
                static_cast<unsigned>(prefix_u[position] - '0'),
                static_cast<unsigned>(prefix_v[position] - '0'));
        }
        if (!budget.add_state()) return unresolved();
        proof.layers.push_back({SignatureNode{std::move(initial), {0, 0, -1, -1}}});
        for (unsigned position = 0; position < horizon; ++position) {
            std::set<SignatureNode> next;
            for (const auto& node : proof.layers.back()) {
                for (unsigned left = 0; left < 2; ++left) {
                    for (unsigned right = 0; right < 2; ++right) {
                        if (!budget.add_work()) return unresolved();
                        SignatureNode successor{
                            family.step(observers, node.state, left, right),
                            advance_signature(node.signature, kind, position, left, right)};
                        if (!next.contains(successor)) {
                            if (!budget.add_state()) return unresolved();
                            next.insert(std::move(successor));
                        }
                    }
                }
            }
            proof.layers.emplace_back(next.begin(), next.end());
        }

        std::set<Signature> accepted;
        for (const auto& node : proof.layers.back()) {
            if (!budget.check()) return unresolved();
            if (goal(node.state)) accepted.insert(node.signature);
        }
        proof.accepted.assign(accepted.begin(), accepted.end());
        if (result.groups.empty()) {
            result.intersection = proof.accepted;
        } else {
            std::vector<Signature> intersection;
            std::set_intersection(result.intersection.begin(), result.intersection.end(),
                proof.accepted.begin(), proof.accepted.end(), std::back_inserter(intersection));
            result.intersection = std::move(intersection);
        }
        result.groups.push_back(std::move(proof));
        if (result.intersection.empty()) {
            result.status = "excluded";
            return result;
        }
    }
    result.status = "survives";
    return result;
    } catch (const std::bad_alloc&) {
        budget.reason = "allocation-failed";
        return unresolved();
    }
}

} // namespace family1::certified

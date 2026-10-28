#pragma once
#include "Family1Certified.h"
#include <array>
#include <string>
#include <vector>

namespace family1::certified {

enum class SignatureKind { Count, FirstDifference };
// Continuation counts, zero-based first differing position (-1 if none),
// and ones strictly before that position (-1 if no difference). Count mode
// leaves the final two coordinates at -1 throughout.
using Signature = std::array<int, 4>;
struct SignatureNode {
    State state;
    Signature signature{0, 0, -1, -1};
    bool operator==(const SignatureNode&) const = default;
    bool operator<(const SignatureNode& other) const;
};
struct SignatureGroupProof {
    std::vector<Observer> observers;
    // Complete reachable layers under all four paired moves, including
    // distinctness inherited from prefixes. These are proof obligations,
    // rather than samples or a beam.
    std::vector<std::vector<SignatureNode>> layers;
    std::vector<Signature> accepted;
};
struct SignatureResult {
    std::string status = "unresolved"; // excluded, survives, unresolved
    std::string reason;
    SignatureKind kind = SignatureKind::Count;
    unsigned horizon = 0;
    std::array<std::string, 2> prefixes{};
    std::vector<SignatureGroupProof> groups;
    // A surviving shared signature need not have one shared pair of words.
    std::vector<Signature> intersection;
};

std::string signature_name(SignatureKind kind);
Signature advance_signature(const Signature& signature, SignatureKind kind,
                            unsigned position, unsigned left, unsigned right);
SignatureResult signature_intersection(
    const Family& family, const std::vector<std::vector<Observer>>& groups,
    unsigned horizon, SignatureKind kind, Budget& budget,
    const std::string& prefix_u = "", const std::string& prefix_v = "");

} // namespace family1::certified

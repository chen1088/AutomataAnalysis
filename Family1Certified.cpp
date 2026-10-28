#include "Family1Certified.h"
#include <algorithm>
#include <limits>
#include <map>
#include <new>
#include <set>
#include <stdexcept>
#include <tuple>
#include <utility>

namespace family1::certified {

bool Observer::operator<(const Observer& other) const
{
    return std::tie(seed, mask) < std::tie(other.seed, other.mask);
}
bool State::operator<(const State& other) const
{
    return std::tie(endpoints, distinct) < std::tie(other.endpoints, other.distinct);
}
Budget::Budget(Limits supplied) : limits(supplied), start_(std::chrono::steady_clock::now()) {}
double Budget::seconds() const
{
    return std::chrono::duration<double>(std::chrono::steady_clock::now() - start_).count();
}
bool Budget::check()
{
    if (!reason.empty()) return false;
    if (limits.interrupted && *limits.interrupted) reason = "interrupted";
    else if (limits.timeout_ms && seconds() * 1000 >= limits.timeout_ms) reason = "timeout";
    return reason.empty();
}
bool Budget::add_state()
{
    if (!check()) return false;
    if (states >= limits.max_states) { reason = "max-states"; return false; }
    ++states;
    return true;
}
bool Budget::add_work()
{
    if (!check()) return false;
    if (work >= limits.max_work) { reason = "max-work"; return false; }
    ++work;
    return true;
}
bool Budget::add_verifier_step()
{
    if (!check()) return false;
    if (verifier_steps >= limits.max_verifier_steps) { reason = "max-verifier-steps"; return false; }
    ++verifier_steps;
    return true;
}
Family::Family(std::vector<Seed> seeds) : seeds_(std::move(seeds))
{
    if (seeds_.empty()) throw std::invalid_argument("at least one seed is required");
    for (const auto& seed : seeds_) {
        if (seed.ports.empty() || seed.ports.size() > 20)
            throw std::invalid_argument("certified seeds require 1 <= states <= 20");
        if (seed.root >= seed.ports.size()) throw std::invalid_argument("seed root outside table");
        for (const auto& row : seed.ports)
            for (auto target : row)
                if (target >= seed.ports.size()) throw std::invalid_argument("transition target outside seed");
    }
    (void)observer_count();
}
std::uint64_t Family::observer_count() const
{
    std::uint64_t count = 0;
    for (const auto& seed : seeds_) {
        const auto masks = std::uint64_t{1} << seed.ports.size();
        if (count > std::numeric_limits<std::uint64_t>::max() - masks)
            throw std::overflow_error("indexed mask count overflows");
        count += masks;
    }
    return count;
}
void Family::validate_observer(Observer observer) const
{
    if (observer.seed >= seeds_.size()) throw std::invalid_argument("observer seed outside family");
    if (observer.mask >= (std::uint64_t{1} << seeds_[observer.seed].ports.size()))
        throw std::invalid_argument("observer mask outside seed closure");
}
void Family::validate_selection(const std::vector<Observer>& selected) const
{
    std::set<Observer> seen;
    for (auto observer : selected) {
        validate_observer(observer);
        if (!seen.insert(observer).second) throw std::invalid_argument("repeated selected observer");
    }
}
void Family::validate_state(const std::vector<Observer>& selected, const State& state) const
{
    validate_selection(selected);
    if (selected.size() > std::numeric_limits<std::size_t>::max() / 2 ||
        state.endpoints.size() != selected.size() * 2)
        throw std::invalid_argument("paired endpoint vector has wrong dimension");
    for (std::size_t i = 0; i < selected.size(); ++i)
        if (state.endpoints[2*i] >= seeds_[selected[i].seed].ports.size() ||
            state.endpoints[2*i+1] >= seeds_[selected[i].seed].ports.size())
            throw std::invalid_argument("paired endpoint outside selected seed");
}
State Family::initial(const std::vector<Observer>& selected, bool distinct) const
{
    validate_selection(selected);
    State result;
    result.distinct = distinct;
    result.endpoints.reserve(selected.size() * 2);
    for (auto observer : selected) {
        result.endpoints.push_back(seeds_[observer.seed].root);
        result.endpoints.push_back(seeds_[observer.seed].root);
    }
    return result;
}
State Family::step(const std::vector<Observer>& selected, const State& state,
                   unsigned left, unsigned right) const
{
    if (left > 1 || right > 1) throw std::invalid_argument("paired action is not binary");
    // Callers validate a projected initial state once. Each successor preserves
    // dimensions/ranges, so the inner transition loop needs no set allocation.
    if (state.endpoints.size() != selected.size() * 2)
        throw std::invalid_argument("paired endpoint vector has wrong dimension");
    State result;
    result.distinct = state.distinct || left != right;
    result.endpoints.resize(state.endpoints.size());
    for (std::size_t i = 0; i < selected.size(); ++i) {
        const auto observer = selected[i];
        const auto& table = seeds_.at(observer.seed).ports;
        const auto u = state.endpoints[2*i], v = state.endpoints[2*i+1];
        result.endpoints[2*i] = table.at(u)[left ^ ((observer.mask >> u) & 1)];
        result.endpoints[2*i+1] = table.at(v)[right ^ ((observer.mask >> v) & 1)];
    }
    return result;
}
Verification Family::verify(const std::string& left, const std::string& right,
                            Budget& budget) const
{
    if (left.size() != right.size() || left == right ||
        left.find_first_not_of("01") != std::string::npos ||
        right.find_first_not_of("01") != std::string::npos)
        throw std::invalid_argument("witness must be distinct equal-length binary words");
    Verification result;
    for (std::size_t i = 0; i < seeds_.size(); ++i) {
        const auto& seed = seeds_[i];
        const auto masks = std::uint64_t{1} << seed.ports.size();
        for (std::uint64_t mask = 0; mask < masks; ++mask) {
            if (!budget.check()) { result.reason = budget.reason; return result; }
            unsigned u = seed.root, v = seed.root;
            // Deliberately scalar replay: no selected-query products, quotient
            // mask tables, hashes, or endpoint-profile assumptions are reused.
            for (std::size_t j = 0; j < left.size(); ++j) {
                if (!budget.add_verifier_step()) { result.reason = budget.reason; return result; }
                u = seed.ports[u][unsigned(left[j] - '0') ^ ((mask >> u) & 1)];
                if (!budget.add_verifier_step()) { result.reason = budget.reason; return result; }
                v = seed.ports[v][unsigned(right[j] - '0') ^ ((mask >> v) & 1)];
            }
            ++result.observers_checked;
            if (u != v) {
                result.status = "separated";
                result.separator = Observer{i, mask};
                return result;
            }
        }
    }
    result.status = "verified";
    return result;
}
bool goal(const State& state)
{
    if (!state.distinct) return false;
    for (std::size_t i = 0; i < state.endpoints.size(); i += 2)
        if (state.endpoints[i] != state.endpoints[i+1]) return false;
    return true;
}

QueryResult decide(const Family& family, const std::vector<Observer>& selected,
                   unsigned horizon, Budget& budget, const std::optional<State>& supplied)
{
    family.validate_selection(selected);
    const State initial = supplied ? *supplied : family.initial(selected);
    family.validate_state(selected, initial);
    QueryResult result;
    struct Parent { std::size_t index; unsigned action; };
    std::vector<std::vector<Parent>> parents;
    auto unresolved = [&]() {
        result.status = "unresolved";
        result.reason = budget.reason;
        // Partial tables are deliberately absent from a proof-bearing field.
        result.layers.clear();
        return std::move(result);
    };
    auto witness = [&](std::size_t depth, std::size_t index) {
        result.status = "witness";
        result.witness = {std::string(horizon, '0'), std::string(horizon, '0')};
        for (std::size_t d = depth; d > 0; --d) {
            const auto parent = parents[d][index];
            result.witness[0][d-1] = char('0' + (parent.action >> 1));
            result.witness[1][d-1] = char('0' + (parent.action & 1));
            index = parent.index;
        }
        result.layers.clear();
        return std::move(result);
    };
    try {
        if (!budget.add_state()) return unresolved();
        result.layers.push_back({initial});
        parents.push_back({Parent{0, 0}});
        if (goal(initial)) return witness(0, 0);
        for (unsigned depth = 0; depth < horizon; ++depth) {
            std::vector<State> next;
            std::vector<Parent> next_parents;
            std::map<State, std::size_t> indices;
            const auto& current = result.layers.back();
            for (std::size_t i = 0; i < current.size(); ++i) {
                for (unsigned action = 0; action < 4; ++action) {
                    if (!budget.add_work()) return unresolved();
                    auto child = family.step(selected, current[i], action >> 1, action & 1);
                    if (indices.find(child) != indices.end()) continue;
                    if (!budget.add_state()) return unresolved();
                    const auto index = next.size();
                    indices.emplace(child, index);
                    next.push_back(std::move(child));
                    next_parents.push_back({i, action});
                    if (goal(next.back())) {
                        // An earlier selected collision extends with common
                        // zeros to the exact requested horizon.
                        result.layers.push_back(std::move(next));
                        parents.push_back(std::move(next_parents));
                        return witness(depth + 1, index);
                    }
                }
            }
            result.layers.push_back(std::move(next));
            parents.push_back(std::move(next_parents));
        }
        result.status = "excluded";
        return result;
    } catch (const std::bad_alloc&) {
        budget.reason = "allocation-failed";
        return unresolved();
    }
}
RefinementResult refine(const Family& family, unsigned horizon, Budget& budget,
                        std::vector<Observer> selected)
{
    family.validate_selection(selected);
    RefinementResult result;
    result.selected = std::move(selected);
    for (;;) {
        if (!budget.check()) { result.reason = budget.reason; return result; }
        result.query = decide(family, result.selected, horizon, budget);
        if (result.query.status == "excluded") { result.status = "excluded"; return result; }
        if (result.query.status == "unresolved") { result.reason = result.query.reason; return result; }
        result.verification = family.verify(result.query.witness[0], result.query.witness[1], budget);
        if (result.verification.status == "verified") { result.status = "witness"; return result; }
        if (result.verification.status == "unresolved") { result.reason = result.verification.reason; return result; }
        if (budget.refinements >= budget.limits.max_refinements) {
            budget.reason = "max-refinements";
            result.reason = budget.reason;
            return result;
        }
        const auto separator = *result.verification.separator;
        if (std::find(result.selected.begin(), result.selected.end(), separator) != result.selected.end())
            throw std::logic_error("selected candidate failed a selected observer");
        result.refinements.push_back({result.query.witness, separator});
        result.selected.push_back(separator);
        ++budget.refinements;
    }
}

} // namespace family1::certified

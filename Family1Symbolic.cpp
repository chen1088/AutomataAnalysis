#include "Family1Symbolic.h"
#include "Family1SatSolver.h"
#include <algorithm>
#include <chrono>
#include <limits>
#include <random>
#include <stdexcept>

namespace family1 {
namespace {
using Clock = std::chrono::steady_clock;
using Bits = std::vector<int>;
struct Budget {
    const SymbolicLimits& limits;
    Clock::time_point start = Clock::now();
    std::uint64_t remaining() const {
        if (limits.interrupted && *limits.interrupted) return 0;
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - start).count();
        return elapsed >= static_cast<std::int64_t>(limits.timeout_ms) ? 0 : limits.timeout_ms - elapsed;
    }
    std::uint64_t solve_time() const { return std::min(remaining(), limits.solve_timeout_ms); }
};
unsigned int width(unsigned int size)
{
    unsigned int result = 1;
    while ((1U << result) < size) ++result;
    return result;
}
Bits variables(SatSolver& solver, unsigned int count)
{
    Bits result;
    for (unsigned int i = 0; i < count; ++i) result.push_back(solver.new_variable());
    return result;
}
void equal(SatSolver& solver, const Bits& a, const Bits& b)
{
    for (unsigned int p = 0; p < a.size(); ++p) {
        solver.add_clause({-a[p], b[p]}); solver.add_clause({a[p], -b[p]});
    }
}
int different_bit(SatSolver& solver, int a, int b)
{
    int d = solver.new_variable();
    solver.add_clause({-a, -b, -d}); solver.add_clause({a, b, -d});
    solver.add_clause({a, -b, d}); solver.add_clause({-a, b, d});
    return d;
}
void different(SatSolver& solver, const Bits& a, const Bits& b)
{
    Bits clause;
    for (unsigned int p = 0; p < a.size(); ++p) clause.push_back(different_bit(solver, a[p], b[p]));
    solver.add_clause(clause);
}
void word_symmetry(SatSolver& solver, const Bits& a, const Bits& b, int truth)
{
    // Root-input complementation permutes all masks; swapping the words is safe.
    // A collision can therefore be represented with a[0]=0 and a<b.
    solver.add_clause({-a[0]});
    int prefix_equal = truth;
    Bits differences;
    for (unsigned int i = 0; i < a.size(); ++i) {
        int d = different_bit(solver, a[i], b[i]); differences.push_back(d);
        solver.add_clause({-prefix_equal, -a[i], b[i]});
        int next = solver.new_variable();
        solver.add_clause({-next, prefix_equal}); solver.add_clause({-next, -d});
        solver.add_clause({-prefix_equal, d, next});
        prefix_equal = next;
    }
    solver.add_clause(differences);
}
// State bits use ordinary binary vertex numbers. Starting at a valid vertex,
// exactly one source guard holds and forces all bits of the next valid vertex.
// Thus invalid binary codes never occur; no one-hot or range axioms are needed.
Bits run(SatSolver& solver, const LargeGraph& graph, const Bits& inputs,
         const Bits& mask, int truth, const Budget& budget)
{
    const auto bits = width(graph.size());
    Bits state(bits, -truth);
    for (int input : inputs) {
        if (!budget.remaining()) return {};
        auto next = variables(solver, bits);
        for (unsigned int s = 0; s < graph.size(); ++s) {
            Bits mismatch;
            for (unsigned int p = 0; p < bits; ++p) mismatch.push_back(s & (1U << p) ? -state[p] : state[p]);
            // q = input XOR sigma[s]. Use two guards if either is constant,
            // four only when both are symbolic (not needed by public queries).
            const bool fixed_input = input == truth || input == -truth;
            const bool fixed_mask = mask[s] == truth || mask[s] == -truth;
            for (unsigned int x = 0; x < 2; ++x) {
                if (fixed_input && x != static_cast<unsigned int>(input == truth)) continue;
                for (unsigned int sigma = 0; sigma < 2; ++sigma) {
                    if (fixed_mask && sigma != static_cast<unsigned int>(mask[s] == truth)) continue;
                    auto guard = mismatch;
                    if (!fixed_input) guard.push_back(x ? -input : input);
                    if (!fixed_mask) guard.push_back(sigma ? -mask[s] : mask[s]);
                    auto target = graph.ports[s][x ^ sigma];
                    for (unsigned int p = 0; p < bits; ++p) {
                        auto clause = guard;
                        clause.push_back(target & (1U << p) ? next[p] : -next[p]);
                        solver.add_clause(clause);
                    }
                }
            }
        }
        state = std::move(next);
    }
    return state;
}
void validate_limits(const SymbolicLimits& limits)
{
    if (limits.max_length == 0 || limits.max_length > 4096 || !limits.timeout_ms || !limits.solve_timeout_ms || !limits.max_refinements
        || limits.projection_depth > 26 || !limits.projection_masks || limits.projection_masks > 64
        || !limits.projection_max_states || limits.projection_max_states > (1ULL << 26))
        throw std::invalid_argument("symbolic length 1..4096 and positive budgets required");
}
std::string model_word(const SatSolver& solver, const Bits& input)
{
    std::string result;
    for (int v : input) result += solver.value(v) ? '1' : '0';
    return result;
}
struct ProjectedProfile {
    std::array<std::uint64_t, 5> planes{};
    bool operator==(const ProjectedProfile&) const = default;
};
struct Projection {
    unsigned int lower_bound = 1;
    std::array<std::string, 2> witness;
    bool collision = false;
};
std::string index_word(std::uint64_t value, unsigned int length)
{
    std::string result(length, '0');
    for (unsigned int i = 0; i < length; ++i) { result[length - i - 1] += value & 1; value >>= 1; }
    return result;
}
std::uint64_t profile_hash(const ProjectedProfile& p)
{
    std::uint64_t h = 0x9e3779b97f4a7c15ULL;
    for (auto x : p.planes) {
        x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL;
        x ^= x >> 27; x *= 0x94d049bb133111ebULL;
        h ^= (x ^ (x >> 31)) + (h << 6) + (h >> 2);
    }
    return h;
}
unsigned int reset_path_bound(const LargeGraph& graph)
{
    // Along a simple path with rows {root,next}, choose a mask that makes the
    // first word advance at every step. A different word resets on its first
    // disagreement and cannot catch up before the path ends.
    unsigned int bound = 1, current = 0;
    std::uint32_t seen = 1;
    for (;;) {
        const auto& row = graph.ports[current];
        if (row[0] != 0 && row[1] != 0) break;
        const auto next = row[0] == 0 ? row[1] : row[0];
        if (seen & (1U << next)) break;
        seen |= 1U << next; ++bound; current = next;
    }
    return bound;
}
std::vector<std::uint32_t> projection_masks(unsigned int m, unsigned int count, std::uint32_t seed)
{
    const auto all = (1U << m) - 1;
    std::vector<std::uint32_t> masks;
    if (count >= all + 1) {
        for (std::uint32_t mask = 0; mask <= all; ++mask) masks.push_back(mask);
    } else {
        masks = {0};
        if (count > 1) masks.push_back(all);
        std::mt19937 random(seed + m);
        while (masks.size() < count) {
            auto mask = random() & all;
            if (std::find(masks.begin(), masks.end(), mask) == masks.end()) masks.push_back(mask);
        }
    }
    return masks;
}
Projection project(const LargeGraph& graph, const std::vector<std::uint32_t>& masks, const Budget& budget)
{
    using Destination = std::array<std::array<std::array<std::uint64_t, 5>, 20>, 2>;
    Destination destinations{};
    const auto bits = width(graph.size());
    for (unsigned int s = 0; s < graph.size(); ++s)
        for (unsigned int k = 0; k < masks.size(); ++k)
            for (unsigned int x = 0; x < 2; ++x) {
                auto target = graph.ports[s][x ^ ((masks[k] >> s) & 1)];
                for (unsigned int p = 0; p < bits; ++p)
                    if (target & (1U << p)) destinations[x][s][p] |= std::uint64_t{1} << k;
            }
    Projection result;
    std::vector<ProjectedProfile> layer(1);
    for (unsigned int depth = 1; depth <= std::min(budget.limits.projection_depth, budget.limits.max_length); ++depth) {
        const auto capacity = static_cast<std::size_t>(std::min<std::uint64_t>(layer.size() * 2ULL, budget.limits.projection_max_states));
        std::vector<ProjectedProfile> next; next.reserve(capacity);
        std::size_t table_size = 2;
        while (table_size < 2 * capacity) table_size *= 2;
        constexpr auto empty = std::numeric_limits<std::uint32_t>::max();
        std::vector<std::uint32_t> table(table_size, empty);
        for (std::size_t i = 0; i < 2 * layer.size(); ++i) {
            if ((i & 4095) == 0 && !budget.remaining()) return result;
            const auto& previous = layer[i / 2];
            ProjectedProfile state;
            for (unsigned int s = 0; s < graph.size(); ++s) {
                std::uint64_t at = ~std::uint64_t{0};
                for (unsigned int p = 0; p < bits; ++p) at &= s & (1U << p) ? previous.planes[p] : ~previous.planes[p];
                for (unsigned int p = 0; p < bits; ++p) state.planes[p] |= at & destinations[i & 1][s][p];
            }
            auto slot = profile_hash(state) & (table_size - 1);
            while (table[slot] != empty && !(next[table[slot]] == state)) slot = (slot + 1) & (table_size - 1);
            if (table[slot] != empty) {
                result.collision = true;
                result.witness = {index_word(table[slot], depth), index_word(i, depth)};
                return result;
            }
            if (next.size() == capacity) return result;
            table[slot] = static_cast<std::uint32_t>(next.size()); next.push_back(state);
        }
        result.lower_bound = depth + 1;
        layer = std::move(next);
    }
    return result;
}
}

WitnessCheck verify_witness(const LargeGraph& graph, const std::array<std::string, 2>& words, const SymbolicLimits& limits)
{
    validate_limits(limits);
    if (words[0].empty() || words[0].size() != words[1].size() || words[0] == words[1])
        throw std::invalid_argument("witness requires distinct positive equal-length words");
    for (const auto& word : words)
        if (word.find_first_not_of("01") != std::string::npos) throw std::invalid_argument("nonbinary word");
    Budget budget{limits};
    SatSolver solver;
    int truth = solver.new_variable(); solver.add_clause({truth});
    auto masks = variables(solver, graph.size()); // ONE static mask, shared by both runs
    std::array<Bits, 2> endpoints;
    for (unsigned int side = 0; side < 2; ++side) {
        Bits input;
        for (char c : words[side]) input.push_back(c == '1' ? truth : -truth);
        endpoints[side] = run(solver, graph, input, masks, truth, budget);
        if (endpoints[side].empty()) return {WitnessDecision::unknown, 0, "encoding-timeout"};
    }
    different(solver, endpoints[0], endpoints[1]);
    auto time = budget.solve_time();
    if (!time) return {WitnessDecision::unknown, 0, "timeout"};
    auto answer = solver.solve({}, time);
    if (answer == SolveResult::unsat) return {WitnessDecision::universal_collision, 0, {}};
    if (answer == SolveResult::unknown) {
        // Checking one fixed pair over 2^20 masks is affordable even when the
        // symbolic query times out. It stores no word layer and remains exact.
        const auto count = 1U << graph.size();
        for (std::uint32_t mask = 0; mask < count; ++mask) {
            if ((mask & 4095) == 0 && !budget.remaining()) return {WitnessDecision::unknown, 0, solver.reason_unknown()};
            unsigned int first = 0, second = 0;
            for (unsigned int i = 0; i < words[0].size(); ++i) {
                first = graph.ports[first][(words[0][i] - '0') ^ ((mask >> first) & 1)];
                second = graph.ports[second][(words[1][i] - '0') ^ ((mask >> second) & 1)];
            }
            if (first != second) return {WitnessDecision::counterexample, mask, {}};
        }
        return {WitnessDecision::universal_collision, 0, {}};
    }
    std::uint32_t mask = 0;
    for (unsigned int s = 0; s < graph.size(); ++s) if (solver.value(masks[s])) mask |= 1U << s;
    return {WitnessDecision::counterexample, mask, {}};
}

SymbolicDecision decide_length(const LargeGraph& graph, unsigned int length, std::vector<std::uint32_t>& samples,
                               const SymbolicLimits& limits)
{
    validate_limits(limits);
    if (!length || length > limits.max_length) throw std::invalid_argument("query length outside limit");
    const auto all = (1U << graph.size()) - 1;
    for (auto mask : samples) if (mask > all) throw std::invalid_argument("sample mask outside graph");
    if (samples.empty()) samples = {0, all, all & 0x55555555U, all & 0xAAAAAAAAU};
    std::sort(samples.begin(), samples.end()); samples.erase(std::unique(samples.begin(), samples.end()), samples.end());
    Budget budget{limits};
    SatSolver candidate;
    int truth = candidate.new_variable(); candidate.add_clause({truth});
    auto first = variables(candidate, length), second = variables(candidate, length);
    word_symmetry(candidate, first, second, truth);
    unsigned int encoded = 0;
    SymbolicDecision result;
    for (;;) {
        while (encoded < samples.size()) {
            Bits masks;
            for (unsigned int s = 0; s < graph.size(); ++s) masks.push_back(samples[encoded] & (1U << s) ? truth : -truth);
            auto a = run(candidate, graph, first, masks, truth, budget);
            auto b = run(candidate, graph, second, masks, truth, budget);
            if (a.empty() || b.empty()) { result.reason = "encoding-timeout"; return result; }
            equal(candidate, a, b);
            ++encoded;
        }
        auto time = budget.solve_time();
        if (!time) { result.reason = "timeout"; return result; }
        auto answer = candidate.solve({}, time);
        if (answer == SolveResult::unsat) { result.decision = LengthDecision::no_collision; return result; }
        if (answer == SolveResult::unknown) { result.reason = candidate.reason_unknown(); return result; }
        std::array<std::string, 2> words{model_word(candidate, first), model_word(candidate, second)};
        auto verifier_limits = limits; verifier_limits.timeout_ms = budget.remaining();
        if (!verifier_limits.timeout_ms) { result.reason = "timeout"; return result; }
        auto check = verify_witness(graph, words, verifier_limits);
        if (check.decision == WitnessDecision::universal_collision) {
            result.decision = LengthDecision::collision; result.witness = std::move(words); return result;
        }
        if (check.decision == WitnessDecision::unknown) { result.reason = "verifier-" + check.reason; return result; }
        if (std::find(samples.begin(), samples.end(), check.counterexample_mask) != samples.end())
            throw std::logic_error("SAT encoding violated an existing sampled mask");
        samples.push_back(check.counterexample_mask);
        if (++result.refinements >= limits.max_refinements) { result.reason = "max-refinements"; return result; }
    }
}

SymbolicScore certify(const LargeGraph& graph, const SymbolicLimits& limits)
{
    validate_limits(limits);
    Budget budget{limits};
    SymbolicScore result;
    if (limits.interrupted && *limits.interrupted) { result.reason = "interrupted"; return result; }
    unsigned int lo = std::min(limits.max_length, reset_path_bound(graph) - 1), hi = 0, next = std::max(1U, lo + 1);
    std::vector<std::uint32_t> samples;
    if (limits.projection_depth) {
        auto masks = projection_masks(graph.size(), limits.projection_masks, limits.projection_seed);
        try {
            auto projected = project(graph, masks, budget);
            result.projection_lower_bound = projected.lower_bound;
            result.projection_mask_count = static_cast<unsigned int>(masks.size());
            lo = std::max(lo, projected.lower_bound - 1);
            if (projected.collision && budget.remaining()) {
                WitnessCheck verified;
                if (masks.size() == (1U << graph.size())) verified.decision = WitnessDecision::universal_collision;
                else {
                    auto verifier_limits = limits; verifier_limits.timeout_ms = budget.remaining();
                    verified = verify_witness(graph, projected.witness, verifier_limits);
                }
                if (verified.decision == WitnessDecision::universal_collision) {
                    hi = static_cast<unsigned int>(projected.witness[0].size());
                    result.witness = projected.witness;
                } else if (verified.decision == WitnessDecision::counterexample) samples.push_back(verified.counterexample_mask);
            }
        } catch (const std::bad_alloc&) { result.reason = "projection-allocation-failed"; }
        if (hi) next = lo + (hi - lo) / 2;
        else next = std::min(limits.max_length, std::max(1U, (lo + 1) * 2));
    }
    unsigned int uncertain = 0;
    while (budget.remaining()) {
        if ((hi && hi == lo + 1) || lo == limits.max_length) break;
        auto query_limits = limits; query_limits.timeout_ms = budget.remaining();
        SymbolicDecision answer;
        try { answer = decide_length(graph, next, samples, query_limits); }
        catch (const std::bad_alloc&) { result.reason = "sat-allocation-failed"; break; }
        ++result.queries;
        if (answer.decision == LengthDecision::no_collision) lo = std::max(lo, next);
        else if (answer.decision == LengthDecision::collision) {
            hi = next; result.witness = answer.witness;
        } else {
            result.reason = answer.reason;
            uncertain = next;
            if (next <= lo + 1) break;
            next = lo + (next - lo) / 2;
            continue;
        }
        if (hi && hi == lo + 1) break;
        if (hi) {
            const auto boundary = uncertain ? std::min(hi, uncertain) : hi;
            if (lo + 1 >= boundary) break;
            next = lo + (boundary - lo) / 2;
        }
        else if (lo == limits.max_length) { result.reason = "max-length"; break; }
        else if (uncertain) {
            if (lo + 1 >= uncertain) break;
            next = lo + (uncertain - lo) / 2;
        } else next = std::min(limits.max_length, next * 2);
    }
    result.lower_bound = lo + 1; result.upper_bound = hi;
    result.mask_count = static_cast<unsigned int>(samples.size());
    result.seconds = std::chrono::duration<double>(Clock::now() - budget.start).count();
    if (hi && hi == lo + 1) { result.status = "exact"; result.reason.clear(); }
    else if (hi) result.status = "bounded";
    else if (lo) result.status = "lower-bound";
    if (result.status != "exact" && result.reason.empty()) result.reason = lo == limits.max_length ? "max-length" : "timeout";
    return result;
}
}

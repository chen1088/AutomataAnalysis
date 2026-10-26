#include "Family1Synthesis.h"
#include "Family1SatSolver.h"
#include "Family1Search.h"
#include "Family1ExactPacked.h"
#include "Family1Symbolic.h"
#include <algorithm>
#include <chrono>
#include <limits>
#include <new>
#include <stdexcept>
#include <utility>

namespace family1 {
namespace {
using Bits = std::vector<int>;
using Clock = std::chrono::steady_clock;

struct Budget {
    const SynthesisLimits& limits;
    Clock::time_point start = Clock::now();
    std::uint64_t remaining() const {
        if (limits.interrupted && *limits.interrupted) return 0;
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - start).count();
        if (elapsed < 0 || static_cast<std::uint64_t>(elapsed) >= limits.timeout_ms) return 0;
        return limits.timeout_ms - static_cast<std::uint64_t>(elapsed);
    }
};

unsigned int width(unsigned int states)
{
    unsigned int result = 1;
    while ((1U << result) < states) ++result;
    return result;
}

Bits variables(SatSolver& solver, unsigned int count)
{
    Bits result;
    for (unsigned int i = 0; i < count; ++i) result.push_back(solver.new_variable());
    return result;
}

void validate(unsigned int states, unsigned int threshold, const SynthesisLimits& limits)
{
    if (!states || states > 20 || !threshold || threshold > 4096 || !limits.timeout_ms
        || !limits.solve_timeout_ms || !limits.candidate_timeout_ms || !limits.max_candidates || !limits.max_refinements
        || !limits.max_postponed_models || !limits.candidate_max_layer_states
        || !limits.candidate_max_working_bytes
        || limits.candidate_max_layer_states > (1ULL << 31))
        throw std::invalid_argument("synthesis requires m=1..20, threshold=1..4096, and positive budgets");
}

void validate_pair(const std::array<std::string, 2>& words, unsigned int threshold)
{
    if (words[0].empty() || words[0].size() != words[1].size() || words[0].size() > threshold
        || words[0] == words[1] || words[0].find_first_not_of("01") != std::string::npos
        || words[1].find_first_not_of("01") != std::string::npos)
        throw std::invalid_argument("learned pairs must be distinct binary equal-length words of length 1..threshold");
}

int xor_bit(SatSolver& solver, int a, int b)
{
    const auto d = solver.new_variable();
    solver.add_clause({-a, -b, -d}); solver.add_clause({a, b, -d});
    solver.add_clause({a, -b, d}); solver.add_clause({-a, b, d});
    return d;
}

// One shared variable graph. Equality literals make target domains, unordered
// ports, and a complete accessibility symmetry reduction straightforward.
class GraphFormula {
public:
    SatSolver& solver;
    unsigned int states, bits;
    int truth;
    std::vector<std::array<Bits, 2>> target;
    std::vector<std::array<Bits, 2>> edge_equals;

    GraphFormula(SatSolver& engine, unsigned int size, bool discovery_labels = false)
        : solver(engine), states(size), bits(width(size)), truth(solver.new_variable()),
          target(size), edge_equals(size)
    {
        solver.add_clause({truth});
        for (unsigned int source = 0; source < states; ++source) {
            for (unsigned int port = 0; port < 2; ++port) {
                target[source][port] = variables(solver, bits);
                auto& equals = edge_equals[source][port];
                equals = variables(solver, states);
                for (unsigned int value = 0; value < states; ++value) {
                    Bits reverse{equals[value]};
                    for (unsigned int p = 0; p < bits; ++p) {
                        const auto match = value & (1U << p) ? target[source][port][p] : -target[source][port][p];
                        solver.add_clause({-equals[value], match});
                        reverse.push_back(-match);
                    }
                    solver.add_clause(reverse);
                }
                solver.add_clause(equals); // Excludes invalid binary target codes.
            }
            for (unsigned int first = 1; first < states; ++first)
                for (unsigned int second = 0; second < first; ++second)
                    solver.add_clause({-edge_equals[source][0][first], -edge_equals[source][1][second]});
        }
        for (unsigned int vertex = 1; vertex < states; ++vertex) {
            Bits incoming;
            for (unsigned int source = 0; source < vertex; ++source)
                for (unsigned int port = 0; port < 2; ++port)
                    incoming.push_back(edge_equals[source][port][vertex]);
            solver.add_clause(incoming);
        }
        // Each vertex q>0 has a predecessor with a smaller label, so induction
        // gives root accessibility. Conversely every root-accessible graph has
        // a BFS labeling with this property. Sorted ports do not alter it.
        // Consequently this formula contains a representative of EVERY rooted
        // accessible class; no connectivity or indegree condition was added.
        if (discovery_labels) {
            for (unsigned int position = 0; position < 2 * states; ++position) {
                for (unsigned int value = 2; value < states; ++value) {
                    Bits introduced_predecessor{-edge_equals[position / 2][position % 2][value]};
                    for (unsigned int previous = 0; previous < position; ++previous)
                        introduced_predecessor.push_back(edge_equals[previous / 2][previous % 2][value - 1]);
                    solver.add_clause(introduced_predecessor);
                }
            }
            // First occurrences in flattened sorted rows are 1,2,...,m-1.
            // BFS discovery labels give this order for every accessible rooted
            // class. Existing successors precede newly introduced successors;
            // only two distinct new successors in one row can be exchanged.
            // Thus this reduces labels without omitting any rooted class.
        }
    }

    LargeGraph model() const
    {
        std::vector<LargeGraph::Row> table(states);
        for (unsigned int source = 0; source < states; ++source) {
            for (unsigned int port = 0; port < 2; ++port) {
                unsigned int value = 0;
                for (unsigned int p = 0; p < bits; ++p)
                    if (solver.value(target[source][port][p])) value |= 1U << p;
                table[source][port] = value;
            }
        }
        LargeGraph graph(std::move(table));
        if (!graph.accessible()) throw std::logic_error("synthesized graph violates accessibility encoding");
        return graph;
    }

    int postpone_model(const LargeGraph& graph)
    {
        // With selector=false this clause excludes this ONE labelled table.
        // With no assumptions selector=true satisfies it for every graph.
        // Therefore free selectors do not change the base graph formula.
        const auto selector = solver.new_variable();
        Bits clause{selector};
        for (unsigned int source = 0; source < states; ++source)
            for (unsigned int port = 0; port < 2; ++port)
                for (unsigned int p = 0; p < bits; ++p)
                    clause.push_back(graph.ports[source][port] & (1U << p)
                        ? -target[source][port][p] : target[source][port][p]);
        solver.add_clause(clause);
        return -selector;
    }

    Bits run(const std::string& word, const Bits& mask, const Budget& budget)
    {
        Bits current(bits, -truth);
        for (char input : word) {
            if (!budget.remaining()) return {};
            auto next = variables(solver, bits);
            for (unsigned int source = 0; source < states; ++source) {
                Bits mismatch;
                for (unsigned int p = 0; p < bits; ++p)
                    mismatch.push_back(source & (1U << p) ? -current[p] : current[p]);
                for (unsigned int sigma = 0; sigma < 2; ++sigma) {
                    auto guard = mismatch;
                    guard.push_back(sigma ? -mask[source] : mask[source]);
                    const auto port = static_cast<unsigned int>(input - '0') ^ sigma;
                    for (unsigned int p = 0; p < bits; ++p) {
                        auto positive = guard; positive.push_back(-target[source][port][p]); positive.push_back(next[p]);
                        auto negative = guard; negative.push_back(target[source][port][p]); negative.push_back(-next[p]);
                        solver.add_clause(positive); solver.add_clause(negative);
                    }
                }
            }
            current = std::move(next);
        }
        return current;
    }

    bool require_separation(const std::array<std::string, 2>& words, const Budget& budget)
    {
        // A different existential static mask is allowed for each learned word
        // pair, but its bits are shared by BOTH paths and EVERY revisit.
        const auto mask = variables(solver, states);
        const auto a = run(words[0], mask, budget);
        const auto b = run(words[1], mask, budget);
        if (a.empty() || b.empty()) return false;
        Bits endpoint_difference;
        for (unsigned int p = 0; p < bits; ++p) endpoint_difference.push_back(xor_bit(solver, a[p], b[p]));
        solver.add_clause(endpoint_difference);
        return true;
    }
};
}

SynthesisResult synthesize_challenger(unsigned int states, unsigned int threshold, const SynthesisLimits& limits,
    const std::vector<std::array<std::string, 2>>& initial_pairs)
{
    validate(states, threshold, limits);
    for (const auto& pair : initial_pairs) validate_pair(pair, threshold);
    Budget budget{limits};
    SynthesisResult result; result.states = states; result.threshold = threshold;
    result.encoder_version = limits.discovery_labels ? synthesis_encoder_v2 : synthesis_encoder_v1;
    SatSolver solver(true);
    auto finish = [&]() {
        result.search_sat_variables = solver.variable_count();
        result.search_sat_clauses = solver.clause_count();
        result.sat_variables = solver.variable_count(); result.sat_clauses = solver.clause_count();
        if (result.decision == SynthesisDecision::impossible) {
            if (!result.postponed_models) result.cnf = solver.dimacs();
            else {
                // The bare search formula was proved UNSAT, but its selector
                // variables interrupt the stable base-encoder numbering.
                // Reconstruct ONLY graph+learned-pair clauses for the portable
                // artifact, without any temporary exclusion. Encoding is a
                // deterministic finalization step after the proof, so finish
                // it even if the search wall budget has just expired.
                SatSolver base(true);
                GraphFormula base_graph(base, states, limits.discovery_labels);
                auto encoding_limits = limits;
                encoding_limits.timeout_ms = std::numeric_limits<std::uint64_t>::max();
                encoding_limits.interrupted = nullptr;
                Budget encoding_budget{encoding_limits};
                for (const auto& pair : result.learned_pairs)
                    if (!base_graph.require_separation(pair, encoding_budget))
                        throw std::logic_error("failed to reconstruct certified base formula");
                result.sat_variables = base.variable_count(); result.sat_clauses = base.clause_count();
                result.cnf = base.dimacs();
            }
        }
        result.seconds = std::chrono::duration<double>(Clock::now() - budget.start).count();
        return result;
    };
    try {
        GraphFormula graph_formula(solver, states, limits.discovery_labels);
        Bits postponement_assumptions;
        for (const auto& pair : initial_pairs) {
            if (!graph_formula.require_separation(pair, budget)) {
                result.reason = "separation-encoding-timeout"; return finish();
            }
            result.learned_pairs.push_back(pair);
        }
        for (;;) {
            const auto remaining = budget.remaining();
            if (!remaining) { result.reason = "timeout-or-interrupted"; return finish(); }
            auto answer = solver.solve(postponement_assumptions, std::min(remaining, limits.solve_timeout_ms));
            if (answer == SolveResult::unknown) { result.reason = "graph-solver-" + solver.reason_unknown(); return finish(); }
            if (answer == SolveResult::unsat) {
                if (!postponement_assumptions.empty()) {
                    // UNSAT under temporary blocks proves only that no NEW
                    // candidate remains. Remove EVERY assumption and ask the
                    // complete graph space before making any global claim.
                    const auto bare_remaining = budget.remaining();
                    if (!bare_remaining) { result.reason = "timeout-or-interrupted"; return finish(); }
                    answer = solver.solve({}, std::min(bare_remaining, limits.solve_timeout_ms));
                    if (answer != SolveResult::unsat) {
                        result.reason = answer == SolveResult::sat ? "postponed-candidates-remain"
                            : "base-graph-solver-" + solver.reason_unknown();
                        return finish();
                    }
                }
                result.decision = SynthesisDecision::impossible;
                result.proven_upper_bound = threshold;
                return finish();
            }
            if (result.candidates_checked >= limits.max_candidates) {
                result.reason = "max-candidates"; return finish();
            }
            auto candidate = graph_formula.model();
            ++result.candidates_checked;
            SymbolicLimits candidate_limits;
            candidate_limits.max_length = threshold;
            candidate_limits.max_refinements = limits.max_refinements;
            candidate_limits.projection_depth = std::min(20U, threshold);
            candidate_limits.projection_max_states = std::min<std::uint64_t>(1ULL << 20, limits.candidate_max_layer_states);
            candidate_limits.timeout_ms = std::min(budget.remaining(), limits.candidate_timeout_ms);
            candidate_limits.solve_timeout_ms = limits.solve_timeout_ms;
            candidate_limits.interrupted = limits.interrupted;
            if (!candidate_limits.timeout_ms) { result.reason = "timeout-or-interrupted"; return finish(); }
            SymbolicScore score;
            if (states <= 6) {
                // The full-mask bitplane backend is substantially cheaper than
                // SAT on these supported sizes, and has already been checked
                // against independent exhaustive ordinary-state simulation.
                // It may exceed this invocation's remaining wall budget while
                // finishing one graph; only completed layers support bounds.
                Limits legacy_limits;
                legacy_limits.depth = std::min(threshold, 31U);
                legacy_limits.max_layer_states = limits.candidate_max_layer_states;
                legacy_limits.interrupted = limits.interrupted;
                const auto exact = family1::score(Family1Graph(candidate.ports), legacy_limits);
                score.lower_bound = exact.lower_bound;
                score.reason = exact.reason;
                if (exact.status == "exact") {
                    score.status = "exact";
                    score.upper_bound = exact.merge_length;
                    score.witness = exact.witness;
                } else score.status = exact.lower_bound > 1 ? "lower-bound" : "incomplete";
            } else if (states <= 8 || std::count_if(candidate.ports.begin(), candidate.ports.end(),
                [](const auto& row) { return row[0] != row[1]; }) <= 8) {
                PackedLimits packed_limits;
                packed_limits.depth = std::min(threshold, 31U);
                packed_limits.max_layer_states = limits.candidate_max_layer_states;
                packed_limits.max_working_bytes = limits.candidate_max_working_bytes;
                packed_limits.timeout_ms = candidate_limits.timeout_ms;
                packed_limits.interrupted = limits.interrupted;
                const auto exact = score_packed(candidate, packed_limits);
                score.lower_bound = exact.lower_bound;
                score.reason = exact.reason;
                if (exact.status == "exact") {
                    score.status = "exact";
                    score.upper_bound = exact.merge_length;
                    score.witness = exact.witness;
                } else {
                    score.status = exact.lower_bound > 1 ? "lower-bound" : "incomplete";
                    const auto left = budget.remaining();
                    const auto packed_ms = static_cast<std::uint64_t>(exact.seconds * 1000);
                    if (score.lower_bound <= threshold && left && packed_ms < candidate_limits.timeout_ms) {
                        candidate_limits.timeout_ms = std::min(left, candidate_limits.timeout_ms - packed_ms);
                        const auto symbolic = certify(candidate, candidate_limits);
                        score.lower_bound = std::max(score.lower_bound, symbolic.lower_bound);
                        score.upper_bound = symbolic.upper_bound;
                        score.witness = symbolic.witness;
                        score.reason += ";symbolic-" + symbolic.reason;
                    }
                }
            } else score = certify(candidate, candidate_limits);
            if (score.lower_bound > threshold) {
                const auto canonical = candidate.canonical();
                result.decision = SynthesisDecision::challenger;
                result.challenger_lower_bound = threshold + 1;
                result.challenger_table = canonical.ports;
                result.challenger_key = canonical.key();
                return finish();
            }
            if (!score.upper_bound || score.upper_bound > threshold) {
                const auto canonical = candidate.canonical();
                if (std::none_of(result.postponed_candidates.begin(), result.postponed_candidates.end(),
                    [&](const PostponedCandidate& record) { return record.key == canonical.key(); }))
                    result.postponed_candidates.push_back({canonical.key(), canonical.ports,
                        score.lower_bound, score.upper_bound, score.reason});
                if (result.postponed_models >= limits.max_postponed_models) {
                    result.reason = "max-postponed-models";
                    return finish();
                }
                postponement_assumptions.push_back(graph_formula.postpone_model(candidate));
                ++result.postponed_models;
                continue;
            }
            auto words = score.witness;
            validate_pair(words, threshold);
            if (words[1] < words[0]) std::swap(words[0], words[1]);
            if (std::find(result.learned_pairs.begin(), result.learned_pairs.end(), words) != result.learned_pairs.end())
                throw std::logic_error("synthesized candidate violates an already learned separation constraint");
            if (!graph_formula.require_separation(words, budget)) {
                result.reason = "separation-encoding-timeout"; return finish();
            }
            result.learned_pairs.push_back(std::move(words));
            // Permanent constraints use only universally colliding pairs;
            // these reject all copies and retain every H>threshold graph.
        }
    } catch (const std::bad_alloc&) {
        result.decision = SynthesisDecision::unknown;
        result.proven_upper_bound = 0;
        result.cnf.clear();
        result.reason = "allocation-failed";
        return finish();
    }
}

SynthesisResult replay_synthesis_upper_bound(unsigned int states, unsigned int threshold,
    const std::vector<std::array<std::string, 2>>& learned_pairs, const SynthesisLimits& limits)
{
    validate(states, threshold, limits);
    for (const auto& pair : learned_pairs) validate_pair(pair, threshold);
    Budget budget{limits};
    SynthesisResult result; result.states = states; result.threshold = threshold;
    result.encoder_version = limits.discovery_labels ? synthesis_encoder_v2 : synthesis_encoder_v1;
    SatSolver solver(true);
    auto finish = [&]() {
        result.sat_variables = solver.variable_count(); result.sat_clauses = solver.clause_count();
        result.search_sat_variables = result.sat_variables;
        result.search_sat_clauses = result.sat_clauses;
        if (result.decision == SynthesisDecision::impossible) result.cnf = solver.dimacs();
        result.seconds = std::chrono::duration<double>(Clock::now() - budget.start).count();
        return result;
    };
    try {
        GraphFormula graph_formula(solver, states, limits.discovery_labels);
        for (const auto& pair : learned_pairs) {
            if (!graph_formula.require_separation(pair, budget)) {
                result.reason = "separation-encoding-timeout"; return finish();
            }
            result.learned_pairs.push_back(pair);
        }
        const auto remaining = budget.remaining();
        if (!remaining) { result.reason = "timeout-or-interrupted"; return finish(); }
        const auto answer = solver.solve({}, std::min(remaining, limits.solve_timeout_ms));
        if (answer == SolveResult::unsat) {
            result.decision = SynthesisDecision::impossible;
            result.proven_upper_bound = threshold;
        } else if (answer == SolveResult::sat) result.reason = "constraints-satisfiable";
        else result.reason = "graph-solver-" + solver.reason_unknown();
        return finish();
    } catch (const std::bad_alloc&) {
        result.reason = "allocation-failed";
        return finish();
    }
}
}

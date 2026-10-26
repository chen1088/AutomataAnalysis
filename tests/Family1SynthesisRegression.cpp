#include "Family1Synthesis.h"
#include "GraphBasedPDFAEnumerator.h"
#include <algorithm>
#include <array>
#include <csignal>
#include <iostream>
#include <map>
#include <numeric>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using family1::LargeGraph;
using Words = std::array<std::string, 2>;

void require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
}

unsigned int endpoint(const LargeGraph& graph, unsigned int mask, const std::string& word)
{
    unsigned int state = 0;
    for (char input : word) state = graph.ports[state][(input - '0') ^ ((mask >> state) & 1)];
    return state;
}

bool universal(const LargeGraph& graph, const Words& words)
{
    for (unsigned int mask = 0; mask < (1U << graph.size()); ++mask)
        if (endpoint(graph, mask, words[0]) != endpoint(graph, mask, words[1])) return false;
    return true;
}

std::string word(unsigned int value, unsigned int length)
{
    std::string result(length, '0');
    for (unsigned int i = 0; i < length; ++i) {
        result[length - i - 1] += value & 1;
        value >>= 1;
    }
    return result;
}

unsigned int brute_score(const LargeGraph& graph)
{
    for (unsigned int length = 1; length <= 10; ++length) {
        std::map<std::vector<unsigned int>, unsigned int> states;
        for (unsigned int value = 0; value < (1U << length); ++value) {
            auto input = word(value, length);
            std::vector<unsigned int> profile;
            for (unsigned int mask = 0; mask < (1U << graph.size()); ++mask)
                profile.push_back(endpoint(graph, mask, input));
            if (!states.emplace(std::move(profile), value).second) return length;
        }
    }
    throw std::runtime_error("small synthesis oracle depth exceeded");
}

std::vector<LargeGraph> classes(unsigned int m)
{
    std::vector<LargeGraph> result;
    require(GraphBasedPDFAEnumerator(m).enumerate([&](const Family1Graph& graph) {
        result.emplace_back(graph.ports);
        return true;
    }), "small canonical enumeration stopped");
    const unsigned int expected[] = {0, 1, 6, 57};
    require(result.size() == expected[m], "wrong number of synthesis oracle classes");
    return result;
}

void validate_learned_pairs(const family1::SynthesisResult& result, const std::vector<LargeGraph>& graphs)
{
    for (const auto& pair : result.learned_pairs) {
        require(pair[0] != pair[1] && pair[0].size() >= 1 && pair[0].size() <= result.threshold && pair[1].size() == pair[0].size(),
            "learned pair is not a distinct equal-length threshold pair");
        require(pair[0].find_first_not_of("01") == std::string::npos && pair[1].find_first_not_of("01") == std::string::npos,
            "learned pair contains nonbinary input");
        require(std::any_of(graphs.begin(), graphs.end(), [&](const LargeGraph& graph) { return universal(graph, pair); }),
            "learned pair is not universally colliding on any encoded graph class");
    }
}

void validate_global_cover(const family1::SynthesisResult& result, const std::vector<LargeGraph>& graphs)
{
    require(result.decision == family1::SynthesisDecision::impossible,
        "expected globally impossible threshold was not certified");
    require(result.proven_upper_bound == result.threshold && !result.challenger_lower_bound
        && result.challenger_table.empty() && result.challenger_key.empty(),
        "global upper-bound result contains conflicting challenger claims");
    require(!result.learned_pairs.empty(), "nontrivial global certificate has no learned collision pairs");
    validate_learned_pairs(result, graphs);
    // Independently replay the certificate across EVERY small graph class.
    // A graph can meet all learned separation constraints iff none of these
    // pairs collides universally on it. Complete coverage proves no challenger.
    for (const auto& graph : graphs)
        require(std::any_of(result.learned_pairs.begin(), result.learned_pairs.end(),
            [&](const Words& pair) { return universal(graph, pair); }),
            "UNSAT certificate's learned pairs do not cover every graph class");
}

family1::SynthesisLimits ordinary_limits(bool discovery_labels = false)
{
    family1::SynthesisLimits limits;
    limits.timeout_ms = 60000;
    limits.solve_timeout_ms = 5000;
    limits.candidate_timeout_ms = 5000;
    limits.max_candidates = 128;
    limits.discovery_labels = discovery_labels;
    return limits;
}

void test_known_global_upper_bounds(bool discovery_labels)
{
    const unsigned int maxima[] = {0, 1, 3, 6};
    for (unsigned int m = 1; m <= 3; ++m) {
        const auto all = classes(m);
        const auto proof = family1::synthesize_challenger(m, maxima[m], ordinary_limits(discovery_labels));
        require(proof.encoder_version == (discovery_labels ? family1::synthesis_encoder_v2 : family1::synthesis_encoder_v1),
            "discovery mode uses the wrong encoder version");
        validate_global_cover(proof, all);
        const auto replay = family1::replay_synthesis_upper_bound(m, maxima[m], proof.learned_pairs, ordinary_limits(discovery_labels));
        require(replay.encoder_version == proof.encoder_version && replay.sat_variables == proof.sat_variables
            && replay.sat_clauses == proof.sat_clauses && replay.learned_pairs == proof.learned_pairs
            && !proof.cnf.empty() && replay.cnf == proof.cnf,
            "saved synthesis certificate does not reconstruct the identical finite graph formula");
        validate_global_cover(replay, all);
        const auto resumed = family1::synthesize_challenger(m, maxima[m], ordinary_limits(discovery_labels), proof.learned_pairs);
        require(resumed.candidates_checked == 0 && resumed.cnf == proof.cnf
            && resumed.learned_pairs == proof.learned_pairs,
            "completed synthesis resume lost its learned constraints or rescored rejected candidates");
        validate_global_cover(resumed, all);
        require(proof.candidates_checked <= all.size(),
            "learned universal pairs failed to exclude an isomorphic rejected class");
        require(proof.sat_variables > 0 && proof.sat_clauses > 0,
            "global synthesis result omits formula statistics");
        std::cout << "Global synthesis m=" << m << " proves H<=" << maxima[m]
            << "; rejected=" << proof.candidates_checked << "; learned=" << proof.learned_pairs.size()
            << "; clauses=" << proof.sat_clauses << "; seconds=" << proof.seconds << '\n';
    }
}

void validate_challenger(const family1::SynthesisResult& result)
{
    require(result.decision == family1::SynthesisDecision::challenger,
        "existing small challenger was not found");
    require(result.challenger_lower_bound == result.threshold + 1 && !result.proven_upper_bound,
        "challenger contains an incorrect global upper-bound claim");
    const LargeGraph graph(result.challenger_table);
    require(graph.size() == result.states && graph.accessible() && graph.key() == result.challenger_key,
        "returned challenger table/key/scope is inconsistent");
    require(GraphBasedPDFAEnumerator::canonical(Family1Graph(graph.ports)).ports == graph.ports,
        "returned challenger is not independently canonical");
    require(brute_score(graph) > result.threshold,
        "returned challenger fails independent exact scoring");
}

void test_existing_challengers(bool discovery_labels)
{
    for (const auto [m, threshold] : {std::array<unsigned int, 2>{2, 2}, {3, 5}}) {
        const auto result = family1::synthesize_challenger(m, threshold, ordinary_limits(discovery_labels));
        validate_challenger(result);
        validate_learned_pairs(result, classes(m));
        std::cout << "Global synthesis m=" << m << " finds H>" << threshold
            << "; candidates=" << result.candidates_checked << "; seconds=" << result.seconds << '\n';
    }
}

void test_incomplete_and_invalid_inputs()
{
    volatile std::sig_atomic_t stop = 1;
    auto stopped = ordinary_limits(); stopped.interrupted = &stop;
    const auto interrupted = family1::synthesize_challenger(3, 6, stopped);
    require(interrupted.decision == family1::SynthesisDecision::unknown
        && !interrupted.proven_upper_bound && !interrupted.challenger_lower_bound
        && interrupted.candidates_checked == 0 && !interrupted.reason.empty(),
        "interrupted synthesis claimed global non-improvability");

    const auto insufficient = family1::replay_synthesis_upper_bound(3, 6, {}, ordinary_limits());
    require(insufficient.decision == family1::SynthesisDecision::unknown && !insufficient.proven_upper_bound
        && !insufficient.challenger_lower_bound && insufficient.reason == "constraints-satisfiable",
        "satisfiable replay formula was incorrectly treated as a genuine challenger or a global proof");

    auto one = ordinary_limits(); one.max_candidates = 1;
    const auto limited = family1::synthesize_challenger(3, 6, one);
    validate_learned_pairs(limited, classes(3));
    if (limited.decision == family1::SynthesisDecision::impossible)
        validate_global_cover(limited, classes(3));
    else
        require(limited.decision == family1::SynthesisDecision::unknown && !limited.proven_upper_bound
            && !limited.challenger_lower_bound && !limited.reason.empty(),
            "candidate limit silently blocked unresolved graphs before claiming a proof");

    auto tiny = ordinary_limits(); tiny.timeout_ms = 1;
    const auto timeout = family1::synthesize_challenger(3, 6, tiny);
    if (timeout.decision == family1::SynthesisDecision::impossible)
        validate_global_cover(timeout, classes(3));
    else
        require(timeout.decision == family1::SynthesisDecision::unknown && !timeout.proven_upper_bound
            && !timeout.challenger_lower_bound && !timeout.reason.empty(),
            "tiny synthesis budget turned UNKNOWN into a global upper bound");

    bool threw = false;
    try { family1::synthesize_challenger(0, 1); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "zero-state synthesis scope accepted");
    threw = false;
    try { family1::synthesize_challenger(21, 1); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "unsupported synthesis size accepted");
    threw = false;
    try { family1::synthesize_challenger(2, 0); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "zero threshold accepted");
    threw = false;
    try { auto bad = ordinary_limits(); bad.candidate_timeout_ms = 0; family1::synthesize_challenger(2, 3, bad); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "zero candidate budget accepted");
    threw = false;
    try { family1::replay_synthesis_upper_bound(2, 3, {{"0", "0"}}); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "invalid saved proof word pair accepted");
}

void test_postponed_models_do_not_prove_bounds(bool discovery_labels)
{
    auto limited = ordinary_limits(discovery_labels);
    limited.candidate_max_layer_states = 1;
    limited.max_postponed_models = 32;
    const auto result = family1::synthesize_challenger(2, 3, limited);
    require(result.decision == family1::SynthesisDecision::unknown
        && !result.proven_upper_bound && !result.challenger_lower_bound && result.cnf.empty(),
        "temporary candidate blocks were mistaken for a global proof");
    require(result.postponed_models > 1 && result.candidates_checked > 1
        && !result.postponed_candidates.empty() && result.reason == "postponed-candidates-remain",
        "unresolved candidate stopped learning or bare graph formula was not rechecked");
    require(result.search_sat_variables == result.sat_variables
        && result.search_sat_clauses == result.sat_clauses,
        "incomplete search formula statistics are inconsistent");
    for (const auto& postponed : result.postponed_candidates) {
        const LargeGraph graph(postponed.table);
        require(graph.accessible() && graph.key() == postponed.key && !postponed.upper_bound
            && postponed.lower_bound <= brute_score(graph),
            "postponed candidate record contains an unverified score or inconsistent table");
    }
    validate_learned_pairs(result, classes(2));
    // Without the temporary exclusions, the learned necessary conditions
    // MUST remain satisfiable. Replaying has no access to the block list.
    const auto replay = family1::replay_synthesis_upper_bound(2, 3, result.learned_pairs, ordinary_limits(discovery_labels));
    require(replay.decision == family1::SynthesisDecision::unknown
        && replay.reason == "constraints-satisfiable" && !replay.proven_upper_bound,
        "portable learned-pair replay inherited temporary exclusions");

    limited.max_postponed_models = 1;
    const auto capped = family1::synthesize_challenger(2, 3, limited);
    require(capped.decision == family1::SynthesisDecision::unknown
        && capped.postponed_models == 1 && !capped.proven_upper_bound && capped.cnf.empty()
        && capped.reason == "max-postponed-models",
        "postponement resource cap produced a global proof");
}

bool discovery_admissible(const LargeGraph& graph)
{
    for (unsigned int vertex = 1; vertex < graph.size(); ++vertex) {
        bool incoming = false;
        for (unsigned int source = 0; source < vertex; ++source)
            for (auto target : graph.ports[source]) incoming |= target == vertex;
        if (!incoming) return false;
    }
    std::vector<bool> seen(graph.size()); seen[0] = true;
    unsigned int next = 1;
    for (auto row : graph.ports) {
        if (row[0] > row[1]) return false;
        for (auto target : row) {
            if (seen[target]) continue;
            if (target != next) return false;
            seen[target] = true; ++next;
        }
    }
    return next == graph.size();
}

void test_discovery_label_coverage()
{
    // Exhaust EVERY ordered labelled table through m=4 independently of the
    // canonical generator. Every accessible one must admit an allowed root-
    // fixed labeling after its two ports are independently sorted per row.
    const unsigned int expected_small[] = {0, 1, 12, 432};
    for (unsigned int m = 1; m <= 4; ++m) {
        std::uint64_t tables = 1;
        for (unsigned int i = 0; i < 2 * m; ++i) tables *= m;
        unsigned int accessible = 0;
        for (std::uint64_t code = 0; code < tables; ++code) {
            auto remaining = code;
            LargeGraph original{std::vector<LargeGraph::Row>(m)};
            for (auto& row : original.ports) for (auto& target : row) {
                target = static_cast<unsigned int>(remaining % m); remaining /= m;
            }
            if (!original.accessible()) continue;
            ++accessible;
            std::vector<unsigned int> permutation(m); std::iota(permutation.begin(), permutation.end(), 0);
            std::set<std::string> admitted;
            do {
                LargeGraph relabeled{std::vector<LargeGraph::Row>(m)};
                for (unsigned int source = 0; source < m; ++source) {
                    auto& row = relabeled.ports[permutation[source]];
                    row = {permutation[original.ports[source][0]], permutation[original.ports[source][1]]};
                    if (row[0] > row[1]) std::swap(row[0], row[1]);
                }
                if (discovery_admissible(relabeled)) admitted.insert(relabeled.key());
            } while (std::next_permutation(permutation.begin() + 1, permutation.end()));
            require(!admitted.empty(), "discovery constraints omit a rooted accessible isomorphism class");
            require(admitted.size() <= (1U << ((m - 1) / 2)), "discovery labeling exceeds its independent two-new-successor bound");
        }
        if (m <= 3) require(accessible == expected_small[m], "independent ordered-table scope is incorrect");
        std::cout << "Discovery-label cover m=" << m << ": " << accessible << " ordered accessible tables\n";
    }
}
}

int main()
{
    try {
        for (bool discovery_labels : {false, true}) {
            test_known_global_upper_bounds(discovery_labels);
            test_existing_challengers(discovery_labels);
            test_postponed_models_do_not_prove_bounds(discovery_labels);
        }
        test_incomplete_and_invalid_inputs();
        test_discovery_label_coverage();
        std::cout << "Family 1 graph-synthesis regression tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Family 1 graph-synthesis regression failure: " << error.what() << '\n';
        return 1;
    }
}

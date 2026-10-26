#include "Family1Symbolic.h"
#include "GraphBasedPDFAEnumerator.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <csignal>
#include <iostream>
#include <map>
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

std::string binary_word(unsigned int number, unsigned int length)
{
    std::string result(length, '0');
    for (unsigned int i = 0; i < length; ++i) {
        result[length - i - 1] += number & 1;
        number >>= 1;
    }
    return result;
}

// Independent ordinary-state simulation. A single mask is shared by both
// trajectories, and the bit at a vertex never changes during a word.
unsigned int endpoint(const LargeGraph& graph, unsigned int mask, const std::string& word)
{
    unsigned int state = 0;
    for (char c : word) state = graph.ports[state][(c - '0') ^ ((mask >> state) & 1)];
    return state;
}

std::vector<unsigned int> profile(const LargeGraph& graph, const std::string& word)
{
    std::vector<unsigned int> result;
    for (unsigned int mask = 0; mask < (1U << graph.size()); ++mask)
        result.push_back(endpoint(graph, mask, word));
    return result;
}

bool universal(const LargeGraph& graph, const Words& words)
{
    return profile(graph, words[0]) == profile(graph, words[1]);
}

struct BruteScore {
    unsigned int length;
    Words witness;
};

BruteScore brute_score(const LargeGraph& graph)
{
    for (unsigned int length = 1; length <= 10; ++length) {
        std::map<std::vector<unsigned int>, std::string> states;
        for (unsigned int number = 0; number < (1U << length); ++number) {
            const auto word = binary_word(number, length);
            const auto state = profile(graph, word);
            auto [position, inserted] = states.emplace(state, word);
            if (!inserted) return {length, {position->second, word}};
        }
    }
    throw std::runtime_error("small independent scoring cap exceeded");
}

void check_words(const LargeGraph& graph, const Words& words, unsigned int length)
{
    require(words[0] != words[1], "solver witness words are identical");
    require(words[0].size() == length && words[1].size() == length,
        "solver witness words have wrong lengths");
    require(words[0].find_first_not_of("01") == std::string::npos
        && words[1].find_first_not_of("01") == std::string::npos,
        "solver witness is nonbinary");
    require(universal(graph, words), "solver witness fails independent full-mask simulation");
}

family1::SymbolicLimits ordinary_limits()
{
    family1::SymbolicLimits limits;
    limits.max_length = 16;
    limits.timeout_ms = 10000;
    limits.solve_timeout_ms = 5000;
    return limits;
}

void check_verifier(const LargeGraph& graph, const Words& words)
{
    const bool expected = universal(graph, words);
    const auto actual = family1::verify_witness(graph, words, ordinary_limits());
    require(actual.decision != family1::WitnessDecision::unknown,
        "small witness verification did not finish");
    if (expected) {
        require(actual.decision == family1::WitnessDecision::universal_collision,
            "verifier rejected independently universal pair");
    } else {
        require(actual.decision == family1::WitnessDecision::counterexample,
            "verifier accepted independently separable pair");
        require(actual.counterexample_mask < (1U << graph.size()),
            "verifier counterexample mask is out of range");
        require(endpoint(graph, actual.counterexample_mask, words[0])
            != endpoint(graph, actual.counterexample_mask, words[1]),
            "reported counterexample mask does not separate words");
    }
}

void check_score_bounds(const LargeGraph& graph, const family1::SymbolicScore& score,
                       unsigned int expected)
{
    require(score.lower_bound >= 1 && score.lower_bound <= expected,
        "symbolic score overstates certified lower bound");
    if (score.upper_bound) {
        require(score.upper_bound >= expected && score.lower_bound <= score.upper_bound,
            "symbolic score understates verified upper bound");
        check_words(graph, score.witness, score.upper_bound);
    } else {
        require(score.witness[0].empty() && score.witness[1].empty(),
            "absent upper bound has an unexplained witness");
    }
    if (score.status == "exact")
        require(score.lower_bound == expected && score.upper_bound == expected,
            "exact score has nonexact bounds");
    else
        require(!score.reason.empty(), "unfinished symbolic score lacks a reason");
}

void test_all_small_graphs()
{
    unsigned int evaluated = 0;
    for (unsigned int m = 1; m <= 3; ++m) {
        unsigned int count = 0;
        require(GraphBasedPDFAEnumerator(m).enumerate([&](const Family1Graph& seed) {
            LargeGraph graph(seed.ports);
            const auto expected = brute_score(graph);
            std::vector<std::uint32_t> samples; // Production chooses initial samples.
            std::set<unsigned int> lengths{expected.length, expected.length + 1};
            if (expected.length > 1) lengths.insert(expected.length - 1);
            for (auto length : lengths) {
                const auto decision = family1::decide_length(graph, length, samples, ordinary_limits());
                require(decision.decision != family1::LengthDecision::unknown,
                    "small length decision did not finish");
                if (length < expected.length)
                    require(decision.decision == family1::LengthDecision::no_collision,
                        "SAT claims a collision shorter than independent H");
                else {
                    require(decision.decision == family1::LengthDecision::collision,
                        "SAT misses a collision at or above independent H");
                    check_words(graph, decision.witness, length);
                }
                require(!samples.empty(), "initial static-mask samples were not populated");
                require(std::set<std::uint32_t>(samples.begin(), samples.end()).size() == samples.size(),
                    "counterexample refinement duplicated a sampled mask");
                for (auto mask : samples)
                    require(mask < (1U << m), "sampled static mask outside graph");
            }
            const auto actual = family1::certify(graph, ordinary_limits());
            check_score_bounds(graph, actual, expected.length);
            require(actual.status == "exact", "small graph did not receive an exact symbolic score");
            check_verifier(graph, expected.witness);
            // Exercise valid and invalid fixed pairs independently of solver
            // witness choices, including shared prefixes and repeated visits.
            check_verifier(graph, {"0", "1"});
            check_verifier(graph, {"0000", "0010"});
            ++count; ++evaluated;
            return true;
        }), "small enumeration unexpectedly stopped");
        const unsigned int expected_count[] = {0, 1, 6, 57};
        require(count == expected_count[m], "wrong number of small symbolic test graphs");
        std::cout << "Independent symbolic exact scores m=" << m << ": " << count << " classes\n";
    }
    require(evaluated == 64, "not all small graph classes were checked");
}

void test_static_masks_and_refinement()
{
    const LargeGraph revisits({{0, 1}, {0, 0}});
    require(endpoint(revisits, 1, "000") == 1 && endpoint(revisits, 1, "0000") == 0,
        "static revisit regression setup changed");
    check_verifier(revisits, {"00", "10"});
    check_verifier(revisits, {"0000", "0100"});
    const auto score = family1::certify(revisits, ordinary_limits());
    require(score.status == "exact" && score.lower_bound == 2 && score.upper_bound == 2,
        "cross-length recurrence was incorrectly treated as equal-length collision");

    const LargeGraph hard({{0, 1}, {0, 1}}); // H=3, whereas mask zero forgets all but the final input.
    std::vector<std::uint32_t> samples{0};
    auto limited = ordinary_limits(); limited.max_refinements = 1;
    const auto partial = family1::decide_length(hard, 2, samples, limited);
    require(partial.decision == family1::LengthDecision::unknown
        && partial.reason == "max-refinements" && samples.size() == 2,
        "refinement limit produced a false SAT/UNSAT certificate");
    const auto completed = family1::decide_length(hard, 2, samples, ordinary_limits());
    require(completed.decision == family1::LengthDecision::no_collision,
        "resuming with learned static mask failed to exclude a false collision");
    const auto collision = family1::decide_length(hard, 3, samples, ordinary_limits());
    require(collision.decision == family1::LengthDecision::collision,
        "refined candidate solver missed exact H");
    check_words(hard, collision.witness, 3);
}

void test_twenty_states()
{
    std::vector<LargeGraph::Row> rows;
    for (unsigned int s = 0; s < 20; ++s) rows.push_back({(s + 1) % 20, (s + 1) % 20});
    const LargeGraph coincident_cycle(rows);
    require(coincident_cycle.accessible(), "twenty-state cycle is not accessible");
    auto limits = ordinary_limits();
    const auto witness = family1::verify_witness(coincident_cycle, {"0", "1"}, limits);
    require(witness.decision == family1::WitnessDecision::universal_collision,
        "twenty-state coincident cycle witness was not universal");
    const auto score = family1::certify(coincident_cycle, limits);
    require(score.status == "exact" && score.lower_bound == 1 && score.upper_bound == 1,
        "twenty-state H=1 graph was not scored exactly");

    for (unsigned int s = 0; s < 20; ++s) rows[s] = {(s + 1) % 20, 0};
    const LargeGraph reset_cycle(rows);
    // This bound needs no word or mask enumeration: every two words of length
    // <20 are separated by a mask that advances one and resets the other.
    auto structural = ordinary_limits();
    structural.max_length = 19; structural.projection_depth = 0;
    const auto structural_score = family1::certify(reset_cycle, structural);
    require(structural_score.lower_bound == 20 && !structural_score.upper_bound
        && structural_score.queries == 0 && structural_score.reason == "max-length",
        "reset-path structural bound was not applied");
    const Words pair{"0", "1"};
    const auto counterexample = family1::verify_witness(reset_cycle, pair, limits);
    require(counterexample.decision == family1::WitnessDecision::counterexample,
        "twenty-state verifier failed to find an evident separating mask");
    require(counterexample.counterexample_mask < (1U << 20)
        && endpoint(reset_cycle, counterexample.counterexample_mask, pair[0])
            != endpoint(reset_cycle, counterexample.counterexample_mask, pair[1]),
        "twenty-state reported mask does not separate fixed words");
}

void test_limits_and_validation()
{
    const LargeGraph hard({{0, 1}, {1, 2}, {0, 1}}); // Independently known H=6.
    require(brute_score(hard).length == 6, "budget regression setup changed");
    auto capped = ordinary_limits(); capped.max_length = 2;
    const auto lower = family1::certify(hard, capped);
    check_score_bounds(hard, lower, 6);
    require(lower.status == "lower-bound" && lower.lower_bound == 3 && !lower.upper_bound
        && lower.reason == "max-length", "length cap claimed a shortest merge score");

    // A wall-clock timeout is hardware dependent. Whatever a one-millisecond
    // budget returns must remain consistent with independently proved H=6.
    auto tiny = ordinary_limits(); tiny.timeout_ms = tiny.solve_timeout_ms = 1;
    const auto short_score = family1::certify(hard, tiny);
    check_score_bounds(hard, short_score, 6);
    require(short_score.status == "exact" || short_score.status == "bounded"
        || short_score.status == "lower-bound" || short_score.status == "incomplete",
        "unexpected score status after tiny time budget");

    volatile std::sig_atomic_t stop = 1;
    auto stopped = ordinary_limits(); stopped.interrupted = &stop;
    std::vector<std::uint32_t> samples;
    const auto decision = family1::decide_length(hard, 6, samples, stopped);
    require(decision.decision == family1::LengthDecision::unknown && !decision.reason.empty(),
        "interrupted length query returned a false certificate");
    const auto check = family1::verify_witness(hard, {"000100", "010000"}, stopped);
    require(check.decision == family1::WitnessDecision::unknown && !check.reason.empty(),
        "interrupted witness verification returned a false certificate");
    const auto score = family1::certify(hard, stopped);
    require(score.status == "incomplete" && score.lower_bound == 1 && !score.upper_bound
        && score.queries == 0, "pre-interrupted score claims progress");

    bool threw = false;
    try { family1::verify_witness(hard, {"0", "0"}); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "identical witness words accepted");
    threw = false;
    try { family1::verify_witness(hard, {"0", "10"}); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "unequal witness lengths accepted");
    threw = false;
    try { family1::verify_witness(hard, {"0", "2"}); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "nonbinary witness accepted");
    threw = false;
    try { std::vector<std::uint32_t> invalid{8}; family1::decide_length(hard, 1, invalid); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "out-of-range sampled mask accepted");
    threw = false;
    try { std::vector<std::uint32_t> empty; family1::decide_length(hard, 0, empty); }
    catch (const std::invalid_argument&) { threw = true; }
    require(threw, "zero-length collision query accepted");
}
}

int main()
{
    try {
        test_all_small_graphs();
        test_static_masks_and_refinement();
        test_twenty_states();
        test_limits_and_validation();
        std::cout << "Family 1 symbolic regression tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Family 1 symbolic regression failure: " << error.what() << '\n';
        return 1;
    }
}

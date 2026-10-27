#include "Family1NearPair.h"
#include <iostream>
#include <stdexcept>

static void require(bool condition, const char* message) {
    if (!condition) throw std::logic_error(message);
}

int main() {
    try {
        using namespace family1;
        near_pair::Options options;
        options.prefix_depth = 6; options.prefix_words = 64;
        options.catalogue_size = 64; options.selected_pairs = 16;
        auto graph = LargeGraph::from_key("00010001");
        unsigned int callbacks = 0;
        auto record = [&](const near_pair::Improvement& value) {
            ++callbacks;
            require(value.first != value.second && value.metric_trace.front() == 0
                && value.metric_trace.back() == 0 && value.verified_masks == 4, "callback certificate");
        };
        auto exact = near_pair::find_pair(graph, options, record);
        require(exact.found && exact.exact && exact.lower_bound == 3 && exact.upper_bound == 3
            && exact.producer == "exact-word-layers" && callbacks == 1 && exact.attempts == 0, "exact fallback");
        options.exact_depth = 2; callbacks = 0;
        auto meeting = near_pair::find_pair(graph, options, record);
        require(meeting.found && meeting.exact && meeting.lower_bound == 3 && meeting.upper_bound == 3
            && meeting.producer == "scored-seed-joint" && callbacks > 0, "joint meets proved lower");
        auto repeated = near_pair::find_pair(graph, options);
        require(repeated.first == meeting.first && repeated.second == meeting.second
            && repeated.nodes == meeting.nodes && repeated.attempts == meeting.attempts, "deterministic repeat");
        options.exact_depth = 0; options.seed_ranking = near_pair::SeedRanking::FullDisagreement;
        auto full = near_pair::find_pair(graph, options);
        options.seed_ranking = near_pair::SeedRanking::Portfolio;
        auto portfolio = near_pair::find_pair(graph, options);
        require(portfolio.found && portfolio.upper_bound <= full.upper_bound && portfolio.seed_words == full.seed_words
            && portfolio.candidates_scored == 2 * full.candidates_scored && portfolio.common_pair_states == 16,
            "portfolio preserves certificate and reuses word catalogue");
        options.seed_ranking = near_pair::SeedRanking::CommonMaximum;
        auto common = near_pair::find_pair(graph, options);
        require(common.found && common.upper_bound == 3 && common.common_pair_states == 16,
            "common-distance preference retains full-family success");
        options.seed_ranking = near_pair::SeedRanking::Portfolio; options.exact_depth = 2;
        options.joint.max_length = 2;
        auto too_short = near_pair::find_pair(graph, options);
        require(!too_short.found && too_short.lower_bound == 3 && too_short.upper_bound == 0
            && too_short.length_capped && !too_short.attempts, "no pair within cap");
        options.joint.max_length = 80; options.exact_depth = 0; options.joint.max_expansions = 1;
        options.prefix_depth = 2; options.prefix_words = 4;
        auto refused = near_pair::find_pair(graph, options);
        require(!refused.found && refused.lower_bound == 1 && refused.nodes == 0
            && refused.expansion_capped && refused.windows_refused > 0 && refused.partial_windows == 0, "whole-window budget refusal");
        options.prefix_depth = 1; options.prefix_words = 2; options.retry_compact_on_miss = false;
        auto no_retry = near_pair::find_pair(graph, options);
        options.retry_compact_on_miss = true;
        auto retry = near_pair::find_pair(graph, options);
        require(!no_retry.found && !no_retry.retried_compact && !retry.found && retry.retried_compact
            && retry.lower_bound == 1 && retry.seed_words == 2 * no_retry.seed_words,
            "deterministic miss retry and total work");
        options = near_pair::Options{};
        auto prefix = near_pair::find_pair(LargeGraph::from_key("010201010202"), options);
        require(prefix.exact && prefix.upper_bound == 2 && prefix.metric_trace == std::vector<std::uint64_t>({0,0,0}),
            "common prefix is retained");
        auto coincident = near_pair::find_pair(LargeGraph::from_key("01010202030304040505060607070707"), options);
        require(coincident.exact && coincident.upper_bound == 1 && coincident.verified_masks == 256
            && coincident.metric_trace == std::vector<std::uint64_t>({0,0}), "original-mask multiplicity");
        bool rejected = false;
        options.selected_pairs = options.catalogue_size + 1;
        try { near_pair::find_pair(graph, options); } catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "invalid budget rejected");
        std::cout << "near-pair independent fallback, bounds, producer, scalar, deterministic and budget checks passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}

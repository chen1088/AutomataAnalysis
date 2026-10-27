#include "Family1ScoredSeeds.h"
#include "Family1CliArtifacts.h"
#include "HardPairJointFinder.h"
#include <fstream>
#include <iostream>
#include <memory>

int main(int argc, char** argv) {
    try {
        if (argc != 9 && argc != 10) throw std::invalid_argument("keys_file k beam prefix_depth prefix_words catalogue selected exact_depth [fast]");
        std::ifstream input(argv[1]);
        const auto k = std::stoul(argv[2]), beam = std::stoul(argv[3]), depth = std::stoul(argv[4]);
        const auto words = std::stoull(argv[5]), catalogue = std::stoull(argv[6]), selected = std::stoull(argv[7]);
        const auto exact_depth = std::stoul(argv[8]);
        std::string key;
        while (input >> key) {
            auto graph = family1::LargeGraph::from_key(key);
            auto product = std::make_shared<const family1::ExactPackedProduct>(graph);
            auto priority = family1::permutation_priority_selection(product, graph);
            std::string first, second; unsigned int upper = 0; std::uint64_t nodes = 0, windows = 0, attempts = 0;
            std::uint64_t scored = 0, seed_words = 0, exact_words = 0; bool exact = false;
            if (exact_depth) {
                family1::PackedLimits limits;
                limits.depth = exact_depth; limits.max_layer_states = std::uint64_t{1} << exact_depth;
                limits.max_working_bytes = std::uint64_t{256} << 20; limits.timeout_ms = 0;
                auto answer = family1::score_packed(graph, limits);
                exact_words = answer.evaluated_words;
                if (answer.status == "exact") {
                    first = answer.witness[0]; second = answer.witness[1]; upper = answer.merge_length; exact = true;
                }
            }
            if (!exact) {
                auto plan = argc == 10 ? family1::fast_scored_joint_seeds(graph, product, depth, words, catalogue, selected)
                    : family1::scored_joint_seeds(graph, product, depth, words, catalogue, selected);
                scored = plan.candidates_scored; seed_words = plan.catalogue.words_evaluated;
                for (const auto& seed : plan.selected) {
                    if (upper && seed.first.size() >= upper) continue;
                    hardpair::joint::Options options;
                    options.window_k = k; options.beam_width = beam; options.diagonal_width = 0;
                    options.max_length = upper ? upper - 1 : 80; options.max_expansions = 2000000;
                    options.prioritize_permutation = true; options.max_trace_records = 0;
                    auto answer = hardpair::joint::find_pair(family1::JointPairState(product, seed.first, seed.second, priority), options);
                    nodes += answer.expanded_nodes; windows += answer.complete_windows; ++attempts;
                    if (answer.partial_windows) throw std::logic_error("partial window");
                    if (answer.found && (!upper || answer.length < upper)) {
                        upper = answer.length; first = answer.first; second = answer.second;
                    }
                }
            }
            const auto quote = family1_cli::quote;
            std::cout << "{\"m\":" << graph.size() << ",\"key\":" << quote(key) << ",\"k\":" << k
                << ",\"beam\":" << beam << ",\"exact_depth\":" << exact_depth << ",\"exact\":" << (exact ? "true" : "false")
                << ",\"upper_bound\":" << (upper ? std::to_string(upper) : "null")
                << ",\"witness\":[" << quote(first) << ',' << quote(second) << "],\"expanded_nodes\":" << nodes
                << ",\"complete_windows\":" << windows << ",\"attempts\":" << attempts
                << ",\"catalogue_scored\":" << scored << ",\"seed_words\":" << seed_words << ",\"exact_words\":" << exact_words
                << ",\"metric_trace\":[0";
            if (upper) {
                family1::JointPairState state(product, graph.size());
                for (std::size_t at = 0; at < first.size(); ++at) {
                    state = state.append_pair(first[at] == '1', second[at] == '1');
                    std::cout << ',' << state.remaining_count();
                }
                if (state.remaining_count() || first == second) throw std::logic_error("bad witness");
            }
            std::cout << "]}\n" << std::flush;
        }
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}

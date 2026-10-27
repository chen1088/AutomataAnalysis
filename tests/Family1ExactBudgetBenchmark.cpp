#include "Family1ExactPacked.h"
#include "Family1CliArtifacts.h"
#include <fstream>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::invalid_argument("keys-file exact-depth memory-mib");
        family1::PackedLimits limits;
        limits.depth = std::stoul(argv[2]);
        if (limits.depth > 30) throw std::invalid_argument("oracle depth must be <=30");
        limits.max_layer_states = std::uint64_t{1} << limits.depth;
        limits.max_working_bytes = std::stoull(argv[3]) << 20;
        limits.timeout_ms = 0;
        std::ifstream input(argv[1]);
        if (!input) throw std::invalid_argument("cannot open keys file");
        std::string key;
        while (input >> key) {
            const auto graph = family1::LargeGraph::from_key(key);
            const auto result = family1::score_packed(graph, limits);
            const auto quote = family1_cli::quote;
            std::cout << "{\"key\":" << quote(key) << ",\"m\":" << graph.size()
                      << ",\"k\":null,\"window_kind\":\"exact-word-layers\",\"depth_cap\":" << limits.depth
                      << ",\"memory_cap_bytes\":" << limits.max_working_bytes
                      << ",\"max_layer_states\":" << limits.max_layer_states
                      << ",\"status\":" << quote(result.status)
                      << ",\"lower_bound\":" << result.lower_bound
                      << ",\"upper_bound\":" << (result.merge_length ? std::to_string(result.merge_length) : "null")
                      << ",\"witness\":[" << quote(result.witness[0]) << ',' << quote(result.witness[1]) << ']'
                      << ",\"evaluated_words\":" << result.evaluated_words
                      << ",\"physically_evaluated_profiles\":" << result.profiles_evaluated
                      << ",\"peak_payload_bytes\":" << result.peak_working_bytes
                      << ",\"seconds\":" << result.seconds
                      << ",\"reason\":" << quote(result.reason) << "}\n" << std::flush;
        }
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}

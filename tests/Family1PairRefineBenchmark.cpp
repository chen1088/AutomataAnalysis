#include "Family1PairRefine.h"
#include <bit>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

static void quote(std::ostream& out, const std::string& value) { out << '"' << value << '"'; }
static void pair(std::ostream& out, const std::string& a, const std::string& b) {
    out << '['; quote(out, a); out << ','; quote(out, b); out << ']';
}
static void self_test() {
    std::uint64_t catalog_checks = 0;
    for (unsigned int n = 1; n <= 8; ++n)
        for (unsigned int bits = 0; bits < (1U << n); ++bits) {
            std::string word(n, '0');
            for (unsigned int i = 0; i < n; ++i) word[i] = ((bits >> (n - i - 1)) & 1U) ? '1' : '0';
            for (unsigned int d = 1; d <= std::min(3U, n); ++d) {
                std::set<std::string> expected;
                for (unsigned int removed = 0; removed < (1U << n); ++removed) {
                    if (std::popcount(removed) != d) continue;
                    std::string value;
                    for (unsigned int i = 0; i < n; ++i) if (!(removed & (1U << i))) value += word[i];
                    expected.insert(value);
                }
                if (family1::refine::deleted_words(word, d) != expected)
                    throw std::logic_error("complete deletion catalog differs from independent subset enumeration");
                ++catalog_checks;
            }
        }
    for (const auto& key : {std::string("00010001"), std::string("010201010202")}) {
        const family1::ExactPackedProduct product(family1::LargeGraph::from_key(key));
        const auto a = key.size() == 8 ? std::string("00000101") : std::string("000000");
        const auto b = key.size() == 8 ? std::string("11000101") : std::string("010000");
        const auto target = key.size() == 8 ? 3U : 2U;
        family1::refine::Options options;
        const auto deletion = family1::refine::refine_pair(product, a, b, options);
        const auto tail = family1::refine::refine_common_suffix(product, a, b, 5, 1000000);
        const auto prefix = family1::refine::refine_prefix_replacements(product, a, b, 5, 1000000);
        for (const auto* result : {&deletion, &tail, &prefix}) {
            if (result->first.size() != target || result->first == result->second
                || product.evaluate(result->first) != product.evaluate(result->second)
                || !result->local_minimum || result->budget_refused || result->minimality_certified)
                throw std::logic_error("local refinement semantic fixture failed");
            for (const auto& neighborhood : result->neighborhoods)
                if (!neighborhood.generated_complete || !neighborhood.evaluated_complete
                    || neighborhood.candidate_words != neighborhood.evaluated_words)
                    throw std::logic_error("semantic fixture used a partial neighborhood");
        }
        options.max_catalog_words = 1;
        const auto refused = family1::refine::refine_pair(product, a, b, options);
        if (!refused.budget_refused || refused.evaluated_words || refused.local_minimum
            || refused.first.size() != a.size())
            throw std::logic_error("refinement budget did not refuse before evaluating");
    }
    std::cout << "{\"self_test\":true,\"deletion_catalogs_checked\":" << catalog_checks
              << ",\"semantic_graphs\":2,\"partial_neighborhoods\":0}\n";
}
int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--self-test") { self_test(); return 0; }
        if (argc < 4 || argc > 6) throw std::runtime_error("mode input.tsv output.jsonl [max-words] [max-catalog]");
        const std::string mode = argv[1];
        family1::refine::Options options;
        if (mode == "deletion") {}
        else if (mode == "mixed") { options.substituted_deletions = 2; options.contiguous_blocks = true; options.block_substitution = true; }
        else if (mode == "blocks") { options.max_deletions = 1; options.contiguous_blocks = true; options.block_substitution = true; }
        else if (mode == "edits4") { options.total_edit_budget = 4; }
        else if (mode == "edits5") { options.total_edit_budget = 5; }
        else if (mode == "edits6") { options.total_edit_budget = 6; }
        else if (mode == "tail16" || mode == "tail18") {}
        else if (mode == "prefix12" || mode == "prefix16") {}
        else throw std::runtime_error("unknown refinement mode");
        if (argc > 4) options.max_words = std::stoull(argv[4]);
        if (argc > 5) options.max_catalog_words = std::stoull(argv[5]);
        std::ifstream input(argv[2]); std::ofstream out(argv[3]);
        std::string line;
        while (std::getline(input, line)) {
            if (line.empty()) continue;
            std::istringstream row(line);
            std::string key, a, b; unsigned int input_k;
            if (!(row >> key >> input_k >> a >> b)) throw std::runtime_error("bad input row");
            const auto graph = family1::LargeGraph::from_key(key);
            const family1::ExactPackedProduct product(graph);
            const auto result = mode.starts_with("prefix")
                ? family1::refine::refine_prefix_replacements(product, a, b, mode == "prefix12" ? 12 : 16, options.max_words)
                : mode == "tail16" || mode == "tail18"
                ? family1::refine::refine_common_suffix(product, a, b, mode == "tail16" ? 16 : 18, options.max_words)
                : family1::refine::refine_pair(product, a, b, options);
            out << "{\"key\":\"" << key << "\",\"m\":" << graph.size()
                << ",\"input_joint_k\":" << input_k << ",\"refinement_k\":";
            if (mode.starts_with("prefix")) out << (mode == "prefix12" ? 12 : 16);
            else if (mode == "tail16" || mode == "tail18") out << (mode == "tail16" ? 16 : 18);
            else out << "null";
            out << ",\"refinement_window_kind\":\"" << (mode.starts_with("prefix") ? "binary-prefix-local-replacement"
                : mode.starts_with("tail") ? "common-suffix-local-replacement" : "N/A: finite edit neighborhood")
                << "\",\"mode\":\"" << mode << '"'
                << ",\"initial_length\":" << result.initial_length << ",\"upper_bound\":" << result.first.size()
                << ",\"input_witness\":"; pair(out, a, b);
            out
                << ",\"witness\":"; pair(out, result.first, result.second);
            out << ",\"local_minimum\":" << (result.local_minimum ? "true" : "false")
                << ",\"counter_scope\":\"" << result.counter_scope << '"'
                << ",\"minimality_certified\":false,\"budget_refused\":" << (result.budget_refused ? "true" : "false")
                << ",\"evaluated_words\":" << result.evaluated_words << ",\"profile_steps\":" << result.profile_steps
                << ",\"improvements\":[";
            for (std::size_t i = 0; i < result.improvements.size(); ++i) {
                if (i) out << ','; pair(out, result.improvements[i].first, result.improvements[i].second);
            }
            out << "],\"neighborhoods\":[";
            for (std::size_t i = 0; i < result.neighborhoods.size(); ++i) {
                if (i) out << ',';
                const auto& n = result.neighborhoods[i];
                out << "{\"move\":\"" << n.move << "\",\"input_length\":" << n.input_length
                    << ",\"output_length\":" << n.output_length << ",\"deletions\":" << n.deletions
                    << ",\"common_suffix_k\":" << n.common_suffix_k << ",\"prefix_length\":" << n.prefix_length
                    << ",\"binary_prefix_k\":" << n.binary_prefix_k << ",\"replaced_prefix_length\":" << n.replaced_prefix_length
                    << ",\"substitutions\":" << n.substitutions << ",\"candidate_words\":" << n.candidate_words
                    << ",\"evaluated_words\":" << n.evaluated_words << ",\"profile_steps\":" << n.profile_steps
                    << ",\"generated_complete\":" << (n.generated_complete ? "true" : "false")
                    << ",\"evaluated_complete\":" << (n.evaluated_complete ? "true" : "false")
                    << ",\"refused_by_budget\":" << (n.refused_by_budget ? "true" : "false")
                    << ",\"found\":" << (n.found ? "true" : "false");
                if (n.found) { out << ",\"witness\":"; pair(out, n.first, n.second); }
                out << '}';
            }
            out << "]}\n"; out.flush();
            std::cerr << "refinement mode=" << mode << " input joint k=" << input_k << " m=" << graph.size() << " "
                << result.initial_length << " -> " << result.first.size() << " words=" << result.evaluated_words << '\n';
        }
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}

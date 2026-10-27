#include "Family1CliArtifacts.h"
#include "Family1JointPair.h"
#include "Family1JointSeeds.h"
#include "HardPairJointFinder.h"
#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#endif

namespace fs = std::filesystem;
namespace cli = family1_cli;
namespace {
struct Options {
    unsigned int m = 0;
    unsigned int prefix_depth = 16, common_prefix_depth = 8, target_upper = 0;
    unsigned int common_depth = 2;
    std::string startup = "legacy", score = "total";
    std::uint64_t prefix_pairs = 0, prefix_words = 65536;
    hardpair::joint::Options finder;
    fs::path out;
    std::vector<std::string> keys;
    Options() {
        finder.window_k = 4;
        finder.beam_width = 1;
        finder.diagonal_width = 0;
        finder.max_length = 80;
    }
};
const char* boolean(bool value) { return value ? "true" : "false"; }
std::uint64_t number(const std::string& value) {
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("expected nonnegative integer: " + value);
    return std::stoull(value);
}
void help() {
    std::cout << "Family1Joint --m M --graph KEY [--graph KEY ...] --out DIR\n"
        "Deterministic search for DISTINCT equal-length word pairs over the\n"
        "joint alphabet 00,01,10,11. All static-mask coordinates are retained,\n"
        "including agreements that can be lost under later unequal inputs.\n"
        " --k 1..8: pair-symbol lookahead, complete window has 4^k leaves\n"
        " --beam N (default1: greedy) --diagonal-beam N (default0)\n"
        " --unequal-beam N (default0): additional leaves using 01/10 in\n"
        "   the current window; every window still enumerates all 4^k choices\n"
        "   Optional divergent/equal-word endpoint budgets for wider searches\n"
        " --max-length N --expansions N: fixed finite work limits, no clocks\n"
        " --startup legacy|divergence (defaultlegacy) --common-depth 0..8\n"
        "   divergence enumerates every common prefix through the depth bound,\n"
        "   then both first differences01/10 and k full joint steps before ranking\n"
        " --score total|permutation (defaulttotal): experimental ranking policy\n"
        " --prefix-pairs N (default0: disabled) --prefix-depth16\n"
        " --prefix-words65536 --common-prefix-depth8: deterministic graph-only\n"
        "   multistart prefixes, each followed by the same full joint search\n"
        " --target-upper L (default0: disabled): stop a graph only after a\n"
        "   scalar-verified pair at most L; every supplied graph is tested\n"
        " --trace-records 0..4096 (default64): diagnostic rounds per attempt\n"
        "Every supplied graph is tested. Positives are replayed over all masks.\n"
        "A bounded beam miss gives no lower bound; shortest length is unproved.\n";
}
Options parse(int argc, char** argv) {
    Options o;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") { help(); std::exit(0); }
        if (++i == argc) throw std::invalid_argument("missing value: " + arg);
        const std::string value = argv[i];
        if (arg == "--out") o.out = value;
        else if (arg == "--graph") o.keys.push_back(value);
        else if (arg == "--startup") o.startup = value;
        else if (arg == "--score") o.score = value;
        else if (arg == "--expansions") o.finder.max_expansions = number(value);
        else if (arg == "--prefix-pairs") o.prefix_pairs = number(value);
        else if (arg == "--prefix-words") o.prefix_words = number(value);
        else {
            const auto n = number(value);
            if (n > 4096) throw std::invalid_argument("option out of range: " + arg);
            if (arg == "--m") o.m = static_cast<unsigned int>(n);
            else if (arg == "--k") o.finder.window_k = static_cast<unsigned int>(n);
            else if (arg == "--beam") o.finder.beam_width = static_cast<unsigned int>(n);
            else if (arg == "--diagonal-beam") o.finder.diagonal_width = static_cast<unsigned int>(n);
            else if (arg == "--unequal-beam") o.finder.unequal_width = static_cast<unsigned int>(n);
            else if (arg == "--max-length") o.finder.max_length = static_cast<unsigned int>(n);
            else if (arg == "--prefix-depth") o.prefix_depth = static_cast<unsigned int>(n);
            else if (arg == "--common-prefix-depth") o.common_prefix_depth = static_cast<unsigned int>(n);
            else if (arg == "--target-upper") o.target_upper = static_cast<unsigned int>(n);
            else if (arg == "--common-depth") o.common_depth = static_cast<unsigned int>(n);
            else if (arg == "--trace-records") o.finder.max_trace_records = static_cast<unsigned int>(n);
            else throw std::invalid_argument("unknown option: " + arg);
        }
    }
    if (!o.m || o.m > 20 || o.keys.empty() || o.out.empty() || !o.finder.window_k
        || o.finder.window_k > 8 || !o.finder.beam_width || !o.finder.max_length
        || !o.finder.max_expansions || !o.prefix_depth || o.prefix_depth > 63
        || !o.prefix_words || o.common_prefix_depth > 8 || o.common_depth > 8
        || (o.startup != "legacy" && o.startup != "divergence")
        || (o.score != "total" && o.score != "permutation")
        || (o.startup == "divergence" && o.prefix_pairs))
        throw std::invalid_argument("require m1..20, supplied graphs, output and positive work budgets");
    o.finder.prioritize_permutation = o.score == "permutation";
    for (auto& key : o.keys) {
        auto graph = family1::LargeGraph::from_key(key);
        if (graph.size() != o.m || !graph.accessible()) throw std::invalid_argument("graph must be accessible and have m vertices");
        key = graph.canonical().key();
    }
    std::sort(o.keys.begin(), o.keys.end());
    o.keys.erase(std::unique(o.keys.begin(), o.keys.end()), o.keys.end());
    o.out = fs::absolute(o.out);
    return o;
}
std::string binary_hash(const char* arg) {
    fs::path path(arg);
#ifdef _WIN32
    std::vector<wchar_t> name(32768);
    auto count = GetModuleFileNameW(nullptr, name.data(), static_cast<DWORD>(name.size()));
    if (!count || count == name.size()) throw std::runtime_error("cannot locate executable");
    path = std::wstring(name.data(), count);
#else
    std::error_code error;
    const auto resolved = fs::read_symlink("/proc/self/exe", error);
    if (!error) path = resolved;
#endif
    return cli::sha256(cli::read(path));
}
void verify(const family1::LargeGraph& g, const hardpair::joint::Result& r) {
    if (!r.found) return;
    if (r.first == r.second || r.first.size() != r.second.size() || r.first.empty()
        || r.first.size() != r.length || r.first.find_first_not_of("01") != std::string::npos
        || r.second.find_first_not_of("01") != std::string::npos)
        throw std::runtime_error("invalid pair from joint finder");
    for (unsigned int mask = 0; mask < (1U << g.size()); ++mask) {
        unsigned int first = 0, second = 0;
        for (unsigned int i = 0; i < r.length; ++i) {
            first = g.ports[first][static_cast<unsigned int>(r.first[i] - '0') ^ ((mask >> first) & 1U)];
            second = g.ports[second][static_cast<unsigned int>(r.second[i] - '0') ^ ((mask >> second) & 1U)];
        }
        if (first != second) throw std::runtime_error("joint pair failed scalar full-mask replay");
    }
}
struct GraphSearch {
    hardpair::joint::Result result;
    family1::JointSeedPlan seed_plan;
    std::uint64_t attempts = 0, prefix_attempts = 0, skipped_seeds = 0;
    std::uint64_t accepted_positives = 0, expansion_capped_attempts = 0, length_capped_attempts = 0;
    std::uint64_t window_reports_truncated = 0;
    std::vector<std::uint64_t> report_attempts;
    std::uint64_t empty_root_attempts = 0, divergence_attempts = 0;
    std::uint64_t divergence_starts_planned = 0, divergence_starts_skipped = 0;
    std::string winning_kind, winning_initial_first, winning_initial_second, winning_common_prefix, winning_orientation;
    unsigned int winning_initial_length = 0, winning_first_greedy_depth = 0;
    std::uint64_t winning_attempt = 0;
    std::uint64_t priority_coordinates = 0;
    std::uint64_t trace_attempt = 0;
    bool seed_plan_generated = false, target_reached = false;
};
GraphSearch search_graph(const family1::LargeGraph& g, const Options& o,
                         const std::function<void(const GraphSearch&)>& improvement = {}) {
    GraphSearch search;
    auto product = std::make_shared<family1::ExactPackedProduct>(g);
    std::shared_ptr<const family1::ExactPackedProduct::MaskSelection> priority;
    if (o.finder.prioritize_permutation)
        priority = family1::permutation_priority_selection(product, g);
    search.priority_coordinates = priority ? priority->selected_count() : 0;
    auto& total = search.result;
    const auto attempt = [&](const std::string& first, const std::string& second, unsigned int cap,
                             const std::string& kind, const std::string& common, const std::string& orientation) {
        auto limits = o.finder;
        limits.max_length = cap;
        auto current = hardpair::joint::find_pair(family1::JointPairState(product, first, second, priority), limits);
        ++search.attempts;
        search.expansion_capped_attempts += current.expansion_limit_reached;
        search.length_capped_attempts += current.length_limit_reached;
        const auto capture_trace = [&]() {
            total.round_trace = current.round_trace;
            total.trace_records_truncated = current.trace_records_truncated;
            total.initial_length = current.initial_length;
            total.initial_remaining = current.initial_remaining;
            total.initial_distinct = current.initial_distinct;
            total.initial_priority_remaining = current.initial_priority_remaining;
            search.trace_attempt = search.attempts;
        };
        if (!total.found) capture_trace();
        total.expanded_nodes += current.expanded_nodes;
        total.complete_windows += current.complete_windows;
        total.partial_windows += current.partial_windows;
        total.windows_refused += current.windows_refused;
        total.visited_leaves += current.visited_leaves;
        total.divergent_leaves += current.divergent_leaves;
        total.diagonal_leaves += current.diagonal_leaves;
        total.unequal_leaves += current.unequal_leaves;
        total.equivalent_leaves += current.equivalent_leaves;
        total.cross_pool_equivalent_leaves += current.cross_pool_equivalent_leaves;
        total.rounds += current.rounds;
        total.maximum_depth_visited = std::max(total.maximum_depth_visited, current.maximum_depth_visited);
        total.expansion_limit_reached |= current.expansion_limit_reached;
        total.length_limit_reached |= current.length_limit_reached;
        total.beam_truncated |= current.beam_truncated;
        total.interrupted |= current.interrupted;
        total.capped |= current.capped;
        for (const auto& window : current.windows) {
            if (total.windows.size() == 16) {
                total.windows.erase(total.windows.begin());
                search.report_attempts.erase(search.report_attempts.begin());
                ++search.window_reports_truncated;
            }
            total.windows.push_back(window);
            search.report_attempts.push_back(search.attempts);
        }
        bool improved = false;
        if (current.found && (!total.found || current.length < total.length
            || (current.length == total.length && std::pair{current.first, current.second}
                < std::pair{total.first, total.second}))) {
            verify(g, current);
            total.found = true; total.length = current.length;
            total.first = current.first; total.second = current.second;
            capture_trace();
            search.winning_kind = kind; search.winning_initial_first = first; search.winning_initial_second = second;
            search.winning_initial_length = static_cast<unsigned int>(first.size());
            search.winning_first_greedy_depth = current.first_greedy_depth;
            search.winning_common_prefix = common; search.winning_orientation = orientation;
            search.winning_attempt = search.attempts;
            ++search.accepted_positives;
            improved = true;
        }
        search.target_reached = o.target_upper && total.found && total.length <= o.target_upper;
        if (improved && improvement) improvement(search);
    };
    if (o.startup == "divergence") {
        auto starts = hardpair::joint::divergence_starts(family1::JointPairState(product, g.size(), priority), o.common_depth);
        search.divergence_starts_planned = starts.expected_starts;
        for (const auto& start : starts.starts) {
            if (search.target_reached) break;
            const auto cap = total.found ? std::min(o.finder.max_length, total.length - 1) : o.finder.max_length;
            if (start.state.first_word().size() > cap) { ++search.divergence_starts_skipped; continue; }
            ++search.divergence_attempts;
            attempt(start.state.first_word(), start.state.second_word(), cap, "divergence", start.common_prefix, start.orientation);
        }
    } else {
        ++search.empty_root_attempts;
        attempt("", "", o.finder.max_length, "empty", "", "");
    }
    if (o.prefix_pairs && !search.target_reached) {
        search.seed_plan = family1::joint_prefix_seeds(g, o.prefix_depth, o.prefix_words,
                                                     o.prefix_pairs, o.common_prefix_depth);
        search.seed_plan_generated = true;
        for (const auto& [first, second] : search.seed_plan.pairs) {
            if (search.target_reached) break;
            const auto cap = total.found ? std::min(o.finder.max_length, total.length - 1) : o.finder.max_length;
            if (first.size() > cap) { ++search.skipped_seeds; continue; }
            ++search.prefix_attempts;
            unsigned int common = 0;
            while (common < first.size() && first[common] == second[common]) ++common;
            attempt(first, second, cap, "legacy-prefix", first.substr(0, common),
                common < first.size() ? std::string{first[common], second[common]} : "");
        }
    }
    return search;
}
std::vector<unsigned int> witness_trace(const family1::LargeGraph& g, const hardpair::joint::Result& r) {
    if (!r.found) return {};
    const auto count = 1U << g.size();
    std::vector<unsigned int> left(count), right(count), trace{0};
    for (unsigned int at = 0; at < r.length; ++at) {
        unsigned int different = 0;
        for (unsigned int mask = 0; mask < count; ++mask) {
            left[mask] = g.ports[left[mask]][static_cast<unsigned int>(r.first[at] - '0') ^ ((mask >> left[mask]) & 1U)];
            right[mask] = g.ports[right[mask]][static_cast<unsigned int>(r.second[at] - '0') ^ ((mask >> right[mask]) & 1U)];
            different += left[mask] != right[mask];
        }
        trace.push_back(different);
    }
    if (trace.back()) throw std::runtime_error("witness trace failed full scalar replay");
    return trace;
}
std::string record(const family1::LargeGraph& g, const Options& o, const GraphSearch& search) {
    const auto& r = search.result;
    std::ostringstream s;
    s << "{\"m\":" << g.size() << ",\"key\":" << cli::quote(g.key()) << ",\"canonical_table\":[";
    for (unsigned int v = 0; v < g.size(); ++v) { if (v) s << ','; s << '[' << g.ports[v][0] << ',' << g.ports[v][1] << ']'; }
    s << "],\"status\":" << cli::quote(r.found ? "verified-upper" : "unresolved")
      << ",\"lower_bound\":1,\"upper_bound\":" << (r.found ? std::to_string(r.length) : "null")
      << ",\"witness\":";
    if (r.found) s << '[' << cli::quote(r.first) << ',' << cli::quote(r.second) << ']'; else s << "null";
    s << ",\"k\":" << o.finder.window_k << ",\"alphabet\":[\"00\",\"01\",\"10\",\"11\"]"
      << ",\"startup\":" << cli::quote(o.startup) << ",\"common_depth\":" << o.common_depth
      << ",\"score\":" << cli::quote(o.score)
      << ",\"priority_coordinate_count\":" << search.priority_coordinates
      << ",\"dfa_count\":" << (1U << g.size())
      << ",\"metric_definition\":\"number of original static-mask DFA coordinates with unequal endpoints\""
      << ",\"greedy_advance\":\"whole joint window block\""
      << ",\"deterministic\":true,\"beam_width\":" << o.finder.beam_width
      << ",\"diagonal_width\":" << o.finder.diagonal_width << ",\"max_length\":" << o.finder.max_length
      << ",\"unequal_width\":" << o.finder.unequal_width
      << ",\"expansion_cap\":" << o.finder.max_expansions << ",\"expanded_nodes\":" << r.expanded_nodes
      << ",\"complete_windows\":" << r.complete_windows << ",\"partial_windows\":" << r.partial_windows
      << ",\"windows_refused\":" << r.windows_refused << ",\"visited_leaves\":" << r.visited_leaves
      << ",\"rounds\":" << r.rounds << ",\"expansion_limit_reached\":" << boolean(r.expansion_limit_reached)
      << ",\"length_limit_reached\":" << boolean(r.length_limit_reached)
      << ",\"beam_truncated\":" << boolean(r.beam_truncated) << ",\"capped\":" << boolean(r.capped)
      << ",\"interrupted\":" << boolean(r.interrupted) << ",\"maximum_depth_visited\":" << r.maximum_depth_visited
      << ",\"divergent_leaves\":" << r.divergent_leaves << ",\"diagonal_leaves\":" << r.diagonal_leaves
      << ",\"attempts\":" << search.attempts << ",\"empty_root_attempts\":" << search.empty_root_attempts
      << ",\"divergence_attempts\":" << search.divergence_attempts
      << ",\"divergence_starts_planned\":" << search.divergence_starts_planned
      << ",\"divergence_starts_skipped_by_length\":" << search.divergence_starts_skipped
      << ",\"divergence_startup_evaluated_all\":"
      << boolean(o.startup == "divergence" && search.divergence_attempts + search.divergence_starts_skipped == search.divergence_starts_planned)
      << ",\"prefix_attempts\":" << search.prefix_attempts
      << ",\"target_upper\":" << o.target_upper << ",\"target_upper_reached\":" << boolean(search.target_reached)
      << ",\"prefix_pairs\":" << o.prefix_pairs << ",\"prefix_depth\":" << o.prefix_depth
      << ",\"prefix_words\":" << o.prefix_words << ",\"common_prefix_depth\":" << o.common_prefix_depth
      << ",\"prefix_plan_generated\":" << boolean(search.seed_plan_generated)
      << ",\"prefix_pairs_available\":" << search.seed_plan.pairs.size()
      << ",\"prefix_words_evaluated\":" << search.seed_plan.words_evaluated
      << ",\"prefix_completed_depth\":" << search.seed_plan.completed_depth
      << ",\"prefix_pair_capped\":" << boolean(search.seed_plan.pair_capped)
      << ",\"prefix_word_capped\":" << boolean(search.seed_plan.word_capped)
      << ",\"prefix_permutation_coordinates\":" << search.seed_plan.permutation_coordinates
      << ",\"prefix_seeds_skipped_by_length_cap\":" << search.skipped_seeds
      << ",\"accepted_positives_scalar_verified\":" << search.accepted_positives
      << ",\"expansion_cap_scope\":\"per joint attempt\",\"expansion_capped_attempts\":" << search.expansion_capped_attempts
      << ",\"length_capped_attempts\":" << search.length_capped_attempts
      << ",\"unequal_leaves\":" << r.unequal_leaves << ",\"equivalent_leaves\":" << r.equivalent_leaves
      << ",\"cross_pool_equivalent_leaves\":" << r.cross_pool_equivalent_leaves
      << ",\"window_reports_truncated\":" << search.window_reports_truncated
      << ",\"minimality_certified\":false,\"static_masks_verified\":" << (r.found ? (1U << g.size()) : 0)
      << ",\"window_reports\":[";
    for (std::size_t i = 0; i < r.windows.size(); ++i) {
        if (i) s << ',';
        const auto& w = r.windows[i];
        s << "{\"attempt\":" << search.report_attempts[i] << ",\"span\":" << w.span << ",\"expected_leaves\":" << w.expected_leaves
          << ",\"leaves\":" << w.leaves << ",\"nodes\":" << w.nodes << ",\"complete\":" << boolean(w.complete) << '}';
    }
    s << "],\"witness_metric_trace\":";
    auto trace = witness_trace(g, r);
    if (r.found) {
        s << '[';
        for (std::size_t i = 0; i < trace.size(); ++i) { if (i) s << ','; s << trace[i]; }
        s << "],\"synchronized_count_trace\":[";
        for (std::size_t i = 0; i < trace.size(); ++i) { if (i) s << ','; s << (1U << g.size()) - trace[i]; }
        unsigned int first_difference = 0;
        while (first_difference < r.length && r.first[first_difference] == r.second[first_difference]) ++first_difference;
        s << "],\"first_difference_position\":" << first_difference + 1
          << ",\"winning_attempt\":{\"kind\":" << cli::quote(search.winning_kind)
          << ",\"number\":" << search.winning_attempt << ",\"initial_length\":" << search.winning_initial_length
          << ",\"initial_first\":" << cli::quote(search.winning_initial_first)
          << ",\"initial_second\":" << cli::quote(search.winning_initial_second)
          << ",\"common_prefix\":" << cli::quote(search.winning_common_prefix)
          << ",\"orientation\":" << cli::quote(search.winning_orientation)
          << ",\"first_difference_depth\":" << first_difference + 1
          << ",\"first_greedy_depth\":" << search.winning_first_greedy_depth << '}';
    } else s << "null,\"synchronized_count_trace\":null,\"first_difference_position\":null,\"winning_attempt\":null";
    s << ",\"round_trace_role\":" << cli::quote(r.found ? "winning-attempt" : "last-attempt")
      << ",\"trace_attempt\":" << search.trace_attempt
      << ",\"trace_initial_length\":" << r.initial_length
      << ",\"trace_initial_D\":" << r.initial_remaining
      << ",\"trace_initial_priority_D\":" << r.initial_priority_remaining
      << ",\"round_trace_records_truncated\":" << r.trace_records_truncated << ",\"round_trace\":[";
    for (std::size_t i = 0; i < r.round_trace.size(); ++i) {
        if (i) s << ',';
        const auto& t = r.round_trace[i];
        s << "{\"round\":" << t.round << ",\"parent_depth\":" << t.parent_depth
          << ",\"span\":" << t.span << ",\"endpoint_depth\":" << t.endpoint_depth
          << ",\"parent_count\":" << t.parent_count << ",\"parents_expanded\":" << t.parents_expanded
          << ",\"min_parent_D\":" << t.min_parent_remaining << ",\"max_parent_D\":" << t.max_parent_remaining
          << ",\"min_parent_priority_D\":" << t.min_parent_priority_remaining
          << ",\"max_parent_priority_D\":" << t.max_parent_priority_remaining
          << ",\"min_leaf_D\":";
        if (t.has_divergent_leaf) s << t.min_divergent_leaf_remaining; else s << "null";
        s << ",\"retained_count\":" << t.retained_count << ",\"min_retained_D\":" << t.min_retained_remaining
          << ",\"max_retained_D\":" << t.max_retained_remaining << ",\"selected_D\":" << t.selected_remaining
          << ",\"selected_priority_D\":" << t.selected_priority_remaining
          << ",\"selected_first\":" << cli::quote(t.selected_first) << ",\"selected_second\":" << cli::quote(t.selected_second)
          << ",\"positive_found\":" << boolean(t.positive_found) << ",\"positive_length\":" << t.positive_length << '}';
    }
    s << "]}";
    return s.str();
}
}
int main(int argc, char** argv) {
    try {
        auto o = parse(argc, argv);
        if (fs::exists(o.out) && !fs::is_empty(o.out)) throw std::runtime_error("use a fresh empty output directory");
        fs::create_directories(o.out);
        std::ostringstream config;
        config << "{\"program\":\"Family1Joint/3\",\"m\":" << o.m << ",\"k\":" << o.finder.window_k
          << ",\"startup\":" << cli::quote(o.startup) << ",\"common_depth\":" << o.common_depth
          << ",\"score\":" << cli::quote(o.score)
          << ",\"trace_records_per_attempt\":" << o.finder.max_trace_records
          << ",\"alphabet\":[\"00\",\"01\",\"10\",\"11\"],\"deterministic\":true"
          << ",\"beam_width\":" << o.finder.beam_width << ",\"diagonal_width\":" << o.finder.diagonal_width
          << ",\"max_length\":" << o.finder.max_length << ",\"max_expansions\":" << o.finder.max_expansions
          << ",\"unequal_width\":" << o.finder.unequal_width << ",\"prefix_pairs\":" << o.prefix_pairs
          << ",\"prefix_depth\":" << o.prefix_depth << ",\"prefix_words\":" << o.prefix_words
          << ",\"common_prefix_depth\":" << o.common_prefix_depth << ",\"target_upper\":" << o.target_upper
          << ",\"prefix_selection\":\"deterministic complete word layers; graph-only seeds; no sampling or saved words\""
          << ",\"expansion_cap_scope\":\"per joint attempt\",\"window_reports_retained_per_graph\":16"
          << ",\"executable_sha256\":" << cli::quote(binary_hash(argv[0])) << ",\"graphs\":[";
        for (std::size_t i = 0; i < o.keys.size(); ++i) { if (i) config << ','; config << cli::quote(o.keys[i]); }
        config << "]}";
        cli::publish(o.out / "run.json", config.str() + '\n');
        std::string records;
        std::ofstream witnesses(o.out / "witnesses.jsonl", std::ios::binary | std::ios::app);
        if (!witnesses) throw std::runtime_error("cannot open verified-witness journal");
        unsigned int positives = 0;
        std::uint64_t joint_attempts = 0, prefix_attempts = 0, target_reached_graphs = 0;
        for (const auto& key : o.keys) {
            auto g = family1::LargeGraph::from_key(key);
            auto search = search_graph(g, o, [&](const GraphSearch& accepted) {
                witnesses << record(g, o, accepted) << '\n';
                witnesses.flush();
                if (!witnesses) throw std::runtime_error("cannot persist verified pair");
            });
            auto row = record(g, o, search);
            records += row + '\n';
            cli::write(o.out / "records.partial.jsonl", records);
            positives += search.result.found;
            joint_attempts += search.attempts;
            prefix_attempts += search.prefix_attempts;
            target_reached_graphs += search.target_reached;
        }
        cli::publish(o.out / "records.jsonl", records);
        std::ostringstream summary;
        summary << "{\"m\":" << o.m << ",\"k\":" << o.finder.window_k
          << ",\"startup\":" << cli::quote(o.startup) << ",\"common_depth\":" << o.common_depth
          << ",\"score\":" << cli::quote(o.score)
          << ",\"alphabet\":[\"00\",\"01\",\"10\",\"11\"],\"graphs\":" << o.keys.size()
          << ",\"beam_width\":" << o.finder.beam_width << ",\"diagonal_width\":" << o.finder.diagonal_width
          << ",\"unequal_width\":" << o.finder.unequal_width << ",\"prefix_pairs\":" << o.prefix_pairs
          << ",\"prefix_depth\":" << o.prefix_depth << ",\"prefix_words\":" << o.prefix_words
          << ",\"common_prefix_depth\":" << o.common_prefix_depth << ",\"target_upper\":" << o.target_upper
          << ",\"verified_pairs\":" << positives << ",\"no_pair\":" << (o.keys.size() - positives)
          << ",\"joint_attempts\":" << joint_attempts << ",\"prefix_attempts\":" << prefix_attempts
          << ",\"target_reached_graphs\":" << target_reached_graphs
          << ",\"all_supplied_graphs_tested\":true,\"deterministic\":true,\"global_maximum_certified\":false"
          << ",\"minimality_certified\":false,\"records_sha256\":" << cli::quote(cli::sha256(records)) << '}';
        cli::publish(o.out / "summary.json", summary.str() + '\n');
        fs::remove(o.out / "records.partial.jsonl");
        std::cout << summary.str() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Family1Joint: " << error.what() << '\n';
        return 2;
    }
}

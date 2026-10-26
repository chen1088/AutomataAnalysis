#include "Family1Synthesis.h"
#include <algorithm>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <regex>
#include <sstream>
#include <stdexcept>

namespace fs = std::filesystem;
namespace {
volatile std::sig_atomic_t interrupted = 0;
void interrupt(int) { interrupted = 1; }
std::string quote(const std::string& value)
{
    std::string result = "\"";
    for (char c : value) {
        if (c == '"' || c == '\\') result += '\\';
        if (c == '\n' || c == '\r') result += ' '; else result += c;
    }
    return result + '"';
}
unsigned int number(const std::string& value)
{
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos) throw std::runtime_error("expected unsigned integer");
    const auto parsed = std::stoull(value);
    if (parsed > 0xffffffffULL) throw std::runtime_error("integer too large");
    return static_cast<unsigned int>(parsed);
}
std::string read(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot read " + path.string());
    return {std::istreambuf_iterator<char>(input), {}};
}
unsigned int integer_field(const std::string& data, const std::string& field)
{
    std::smatch match;
    if (!std::regex_search(data, match, std::regex("\"" + field + "\":([0-9]+)"))) throw std::runtime_error("missing certificate field " + field);
    return number(match[1].str());
}
std::vector<std::array<std::string, 2>> read_pairs(const std::string& data)
{
    const auto begin = data.find("\"learned_pairs\":[");
    if (begin == std::string::npos) throw std::runtime_error("missing learned pairs");
    std::vector<std::array<std::string, 2>> pairs;
    const std::regex pattern("\\[\"([01]+)\",\"([01]+)\"\\]");
    const auto suffix = data.substr(begin);
    for (auto it = std::sregex_iterator(suffix.begin(), suffix.end(), pattern); it != std::sregex_iterator(); ++it)
        pairs.push_back({(*it)[1].str(), (*it)[2].str()});
    return pairs;
}
void write(const fs::path& path, const std::string& value)
{
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    output.exceptions(std::ios::badbit | std::ios::failbit);
    output << value;
}
}
int main(int argc, char** argv)
{
    try {
        unsigned int states = 0, threshold = 0;
        family1::SynthesisLimits limits;
        fs::path out, replay, resume;
        std::vector<fs::path> seed_sources;
        for (int i = 1; i < argc; ++i) {
            std::string option = argv[i];
            if (option == "--help") {
                std::cout << "Family1GlobalCheck --states M --threshold L --out NEWDIR\n"
                    "  [--timeout-ms 30000 --candidate-timeout-ms 5000 --solve-timeout-ms 2000]\n"
                    "  [--max-candidates 256 --max-refinements 256 --max-postponed-models 256]\n"
                    "  [--candidate-max-layer-states 16777216 --candidate-max-working-mib 2048]\n"
                    "  [--seed-pairs RUNDIR ...] (other sizes allowed; pairs longer than L skipped)\n"
                    "  [--discovery-labels] (complete BFS discovery reduction, encoder v2)\n"
                    "Family1GlobalCheck --replay CERTDIR --out NEWDIR [--timeout-ms 30000]\n"
                    "Family1GlobalCheck --resume RUNDIR --out NEWDIR [--timeout-ms 30000]\n"
                    "UNSAT certifies H(G)<=L for EVERY rooted accessible M-state graph.\n"
                    "UNKNOWN certifies no global bound. Maximizers are not enumerated.\n";
                return 0;
            }
            if (option == "--discovery-labels") { limits.discovery_labels = true; continue; }
            if (++i >= argc) throw std::runtime_error("missing option value");
            std::string value = argv[i];
            if (option == "--states") states = number(value);
            else if (option == "--threshold") threshold = number(value);
            else if (option == "--out") out = value;
            else if (option == "--replay") replay = value;
            else if (option == "--resume") resume = value;
            else if (option == "--seed-pairs") seed_sources.emplace_back(value);
            else if (option == "--timeout-ms") limits.timeout_ms = number(value);
            else if (option == "--candidate-timeout-ms") limits.candidate_timeout_ms = number(value);
            else if (option == "--solve-timeout-ms") limits.solve_timeout_ms = number(value);
            else if (option == "--max-candidates") limits.max_candidates = number(value);
            else if (option == "--max-refinements") limits.max_refinements = number(value);
            else if (option == "--max-postponed-models") limits.max_postponed_models = number(value);
            else if (option == "--candidate-max-layer-states") limits.candidate_max_layer_states = number(value);
            else if (option == "--candidate-max-working-mib") limits.candidate_max_working_bytes = static_cast<std::uint64_t>(number(value)) << 20;
            else throw std::runtime_error("unknown option: " + option);
        }
        if (out.empty()) throw std::runtime_error("--out is required");
        if (fs::exists(out) && !fs::is_empty(out)) throw std::runtime_error("output directory must be empty");
        fs::create_directories(out);
        std::signal(SIGINT, interrupt); std::signal(SIGTERM, interrupt); limits.interrupted = &interrupted;
        family1::SynthesisResult result;
        if (!replay.empty() && !resume.empty()) throw std::runtime_error("choose either replay or resume");
        if (!replay.empty() && !seed_sources.empty()) throw std::runtime_error("seed pairs cannot alter a replay certificate");
        std::vector<std::array<std::string, 2>> pairs;
        if (!replay.empty() || !resume.empty()) {
            const auto source = replay.empty() ? resume : replay;
            const auto data = read(source / "result.json");
            if (data.find("\"method\":\"family1-global-synthesis\"") == std::string::npos)
                throw std::runtime_error("incompatible certificate encoder");
            if (data.find("\"encoder_version\":" + quote(family1::synthesis_encoder_v1)) != std::string::npos)
                limits.discovery_labels = false;
            else if (data.find("\"encoder_version\":" + quote(family1::synthesis_encoder_v2)) != std::string::npos)
                limits.discovery_labels = true;
            else throw std::runtime_error("incompatible certificate encoder");
            states = integer_field(data, "states"); threshold = integer_field(data, "threshold");
            pairs = read_pairs(data);
        }
        std::ostringstream seed_metadata;
        seed_metadata << '[';
        for (unsigned int i = 0; i < seed_sources.size(); ++i) {
            const auto data = read(seed_sources[i] / "result.json");
            if (data.find("\"method\":\"family1-global-synthesis\"") == std::string::npos)
                throw std::runtime_error("seed source must be a Family1GlobalCheck run");
            unsigned int imported = 0, skipped = 0, duplicates = 0;
            for (auto pair : read_pairs(data)) {
                if (pair[0] == pair[1] || pair[0].size() != pair[1].size())
                    throw std::runtime_error("seed pair must contain distinct equal-length binary words");
                if (pair[0].size() > threshold) { ++skipped; continue; }
                if (pair[1] < pair[0]) std::swap(pair[0], pair[1]);
                if (std::find(pairs.begin(), pairs.end(), pair) != pairs.end()) { ++duplicates; continue; }
                pairs.push_back(std::move(pair)); ++imported;
            }
            if (i) seed_metadata << ',';
            seed_metadata << "{\"directory\":" << quote(seed_sources[i].generic_string())
                << ",\"states\":" << integer_field(data, "states")
                << ",\"threshold\":" << integer_field(data, "threshold")
                << ",\"imported_pairs\":" << imported << ",\"skipped_long_pairs\":" << skipped
                << ",\"duplicate_pairs\":" << duplicates << '}';
        }
        seed_metadata << ']';
        result = replay.empty() ? family1::synthesize_challenger(states, threshold, limits, pairs)
            : family1::replay_synthesis_upper_bound(states, threshold, pairs, limits);
        if (!replay.empty() && !result.cnf.empty() && fs::exists(replay / "graph-space.cnf") && result.cnf != read(replay / "graph-space.cnf"))
            throw std::runtime_error("replayed CNF differs from saved graph formula");
        const auto decision = result.decision == family1::SynthesisDecision::impossible ? "impossible"
            : result.decision == family1::SynthesisDecision::challenger ? "challenger" : "unknown";
        std::ostringstream json;
        json.precision(17);
        json << "{\"schema\":1,\"method\":\"family1-global-synthesis\",\"encoder_version\":" << quote(result.encoder_version)
             << ",\"decision\":" << quote(decision) << ",\"states\":" << states << ",\"threshold\":" << threshold
             << ",\"global_upper_bound_certified\":" << (result.proven_upper_bound ? "true" : "false") << ",\"proven_upper_bound\":";
        if (result.proven_upper_bound) json << result.proven_upper_bound; else json << "null";
        json << ",\"challenger_lower_bound\":";
        if (result.challenger_lower_bound) json << result.challenger_lower_bound; else json << "null";
        json << ",\"challenger_key\":" << quote(result.challenger_key) << ",\"challenger_table\":[";
        for (unsigned int s = 0; s < result.challenger_table.size(); ++s) {
            if (s) json << ',';
            json << '[' << result.challenger_table[s][0] << ',' << result.challenger_table[s][1] << ']';
        }
        json << "],\"candidates_checked\":" << result.candidates_checked << ",\"sat_variables\":" << result.sat_variables
             << ",\"sat_clauses\":" << result.sat_clauses
             << ",\"search_sat_variables\":" << result.search_sat_variables
             << ",\"search_sat_clauses\":" << result.search_sat_clauses
             << ",\"postponed_models\":" << result.postponed_models
             << ",\"postponed_candidates\":[";
        for (unsigned int i = 0; i < result.postponed_candidates.size(); ++i) {
            const auto& candidate = result.postponed_candidates[i];
            if (i) json << ',';
            json << "{\"key\":" << quote(candidate.key) << ",\"table\":[";
            for (unsigned int s = 0; s < candidate.table.size(); ++s) {
                if (s) json << ',';
                json << '[' << candidate.table[s][0] << ',' << candidate.table[s][1] << ']';
            }
            json << "],\"lower_bound\":" << candidate.lower_bound << ",\"upper_bound\":";
            if (candidate.upper_bound) json << candidate.upper_bound; else json << "null";
            json << ",\"reason\":" << quote(candidate.reason) << '}';
        }
        json << "],\"seed_pair_sources\":" << seed_metadata.str()
             << ",\"seconds\":" << result.seconds << ",\"reason\":" << quote(result.reason)
             << ",\"learned_pairs\":[";
        for (unsigned int i = 0; i < result.learned_pairs.size(); ++i) {
            if (i) json << ',';
            json << '[' << quote(result.learned_pairs[i][0]) << ',' << quote(result.learned_pairs[i][1]) << ']';
        }
        json << "]}\n";
        write(out / "result.json", json.str());
        if (!result.cnf.empty()) write(out / "graph-space.cnf", result.cnf);
        std::cout << "m=" << states << " threshold=" << threshold << " decision=" << decision
                  << " checked=" << result.candidates_checked << " constraints=" << result.learned_pairs.size()
                  << " postponed=" << result.postponed_models
                  << " seconds=" << result.seconds << " reason=" << result.reason << '\n';
        return 0;
    } catch (const std::exception& error) { std::cerr << "Family1GlobalCheck: " << error.what() << '\n'; return 1; }
}

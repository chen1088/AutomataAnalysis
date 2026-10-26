// Standalone independent global m=5 audit. This file deliberately includes no
// production headers and calls no production enumerator, canonicalizer,
// packed product or scorer.
#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {
constexpr unsigned int size = 5;
constexpr unsigned int mask_count = 1U << size;
using Row = std::array<unsigned char, 2>;
using Table = std::array<Row, size>;
using State = std::array<unsigned char, mask_count>;
using Clock = std::chrono::steady_clock;

std::string quote(const std::string& value)
{
    std::string result = "\"";
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') { result += '\\'; result += c; }
        else if (c == '\n') result += "\\n";
        else if (c == '\r') result += "\\r";
        else if (c == '\t') result += "\\t";
        else if (c < 32) throw std::runtime_error("unexpected control character in JSON text");
        else result += c;
    }
    return result + '"';
}

bool accessible(const Table& table)
{
    std::array<bool, size> seen{};
    std::array<unsigned char, size> queue{};
    seen[0] = true;
    unsigned int head = 0, tail = 1;
    while (head != tail) {
        const auto state = queue[head++];
        for (auto target : table[state])
            if (!seen[target]) { seen[target] = true; queue[tail++] = target; }
    }
    return tail == size;
}

// Test ALL 24 root-fixing permutations, sorting each transformed port pair.
// Unlike discovery-label production code, this uses no canonical augmentation.
std::string canonical_key(const Table& table)
{
    std::array<unsigned int, size> permutation{0, 1, 2, 3, 4};
    std::string best;
    unsigned int checked = 0;
    do {
        std::string key(2 * size, '0');
        for (unsigned int state = 0; state < size; ++state) {
            auto a = permutation[table[state][0]], b = permutation[table[state][1]];
            if (a > b) std::swap(a, b);
            key[2 * permutation[state]] += a;
            key[2 * permutation[state] + 1] += b;
        }
        if (best.empty() || key < best) best = std::move(key);
        ++checked;
    } while (std::next_permutation(permutation.begin() + 1, permutation.end()));
    if (checked != 24) throw std::runtime_error("independent permutation enumeration did not visit 24 maps");
    return best;
}

Table decode(const std::string& key)
{
    if (key.size() != 2 * size) throw std::runtime_error("wrong independent canonical-key length");
    Table result;
    for (unsigned int state = 0; state < size; ++state)
        for (unsigned int port = 0; port < 2; ++port) {
            const auto c = key[2 * state + port];
            if (c < '0' || c >= '0' + size) throw std::runtime_error("canonical-key target out of range");
            result[state][port] = static_cast<unsigned char>(c - '0');
        }
    return result;
}

State step(const Table& table, const State& state, unsigned int input)
{
    State result;
    for (unsigned int mask = 0; mask < mask_count; ++mask) {
        const auto source = state[mask];
        result[mask] = table[source][input ^ ((mask >> source) & 1U)];
    }
    return result;
}

struct StateHash {
    std::size_t operator()(const State& state) const
    {
        std::uint64_t result = 14695981039346656037ULL;
        for (auto endpoint : state) { result ^= endpoint; result *= 1099511628211ULL; }
        return static_cast<std::size_t>(result);
    }
};

std::string word(std::uint32_t index, unsigned int length)
{
    std::string result(length, '0');
    for (unsigned int i = 0; i < length; ++i) {
        result[length - i - 1] += index & 1U;
        index >>= 1;
    }
    return result;
}

struct Score {
    unsigned int length;
    std::array<std::string, 2> witness;
};

Score score(const Table& table)
{
    std::vector<State> current(1); // all 32 masks begin at root zero
    // This is a resource cap, not the expected answer: it is well above 15.
    // Any reached cap is an audit FAILURE, never an exhaustive/exact result.
    constexpr std::uint64_t maximum_layer = 1ULL << 22;
    for (unsigned int length = 1; length <= 30; ++length) {
        const auto children = current.size() * 2ULL;
        if (children > maximum_layer) throw std::runtime_error("independent m5 scorer hit state budget");
        // NEW map for this length only. std::equal_to<State> checks ALL 32
        // endpoint bytes after hash matches; cross-length revisits are ignored.
        std::unordered_map<State, std::uint32_t, StateHash> seen;
        seen.reserve(static_cast<std::size_t>(children));
        std::vector<State> next;
        next.reserve(static_cast<std::size_t>(children));
        for (std::uint32_t index = 0; index < children; ++index) {
            const auto state = step(table, current[index / 2], index & 1U);
            auto [position, inserted] = seen.emplace(state, index);
            if (!inserted) return {length, {word(position->second, length), word(index, length)}};
            next.push_back(state);
        }
        current = std::move(next);
    }
    throw std::runtime_error("independent m5 scorer hit depth budget");
}

void verify_witness(const Table& table, const Score& score)
{
    if (!score.length || score.witness[0] == score.witness[1]
        || score.witness[0].size() != score.length || score.witness[1].size() != score.length)
        throw std::runtime_error("independent scorer emitted invalid witness words");
    // A separate direct word trajectory, not the layer-step routine above.
    for (unsigned int mask = 0; mask < mask_count; ++mask) {
        std::array<unsigned int, 2> endpoint{};
        for (unsigned int side = 0; side < 2; ++side)
            for (char letter : score.witness[side]) {
                if (letter != '0' && letter != '1') throw std::runtime_error("nonbinary independent witness");
                const auto source = endpoint[side];
                const auto port = static_cast<unsigned int>(letter - '0') ^ ((mask >> source) & 1U);
                endpoint[side] = table[source][port];
            }
        if (endpoint[0] != endpoint[1]) throw std::runtime_error("independent witness failed an original static mask");
    }
}

std::size_t value_position(const std::string& line, const std::string& field)
{
    auto position = line.find('"' + field + "\":");
    if (position == std::string::npos) throw std::runtime_error("missing reference JSON field " + field);
    position += field.size() + 3;
    while (position < line.size() && std::isspace(static_cast<unsigned char>(line[position]))) ++position;
    return position;
}

unsigned int json_unsigned(const std::string& line, const std::string& field)
{
    const auto position = value_position(line, field);
    if (position == line.size() || line[position] < '0' || line[position] > '9')
        throw std::runtime_error("reference field is not an unsigned integer: " + field);
    return static_cast<unsigned int>(std::stoul(line.substr(position)));
}

std::string json_string(const std::string& line, const std::string& field)
{
    const auto position = value_position(line, field);
    if (position == line.size() || line[position] != '"') throw std::runtime_error("reference field is not a string");
    const auto end = line.find('"', position + 1);
    if (end == std::string::npos) throw std::runtime_error("unterminated reference string");
    auto result = line.substr(position + 1, end - position - 1);
    if (result.find('\\') != std::string::npos) throw std::runtime_error("escaped reference key/status is unsupported");
    return result;
}

std::map<std::string, unsigned int> read_reference(const std::filesystem::path& path)
{
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open reference JSONL: " + path.string());
    std::map<std::string, unsigned int> result;
    for (std::string line; std::getline(input, line);) {
        if (line.empty() || json_unsigned(line, "m") != size) continue;
        if (json_string(line, "status") != "exact") throw std::runtime_error("reference contains nonexact m5 record");
        auto [position, inserted] = result.emplace(json_string(line, "key"), json_unsigned(line, "merge_length"));
        if (!inserted) throw std::runtime_error("duplicate m5 reference key: " + position->first);
    }
    if (!input.eof()) throw std::runtime_error("reference JSONL read failure");
    return result;
}

void write_graph(std::ostream& output, const std::string& key, const Table& table, const Score& score)
{
    output << "{\"m\":5,\"key\":" << quote(key) << ",\"canonical_table\":[";
    for (unsigned int state = 0; state < size; ++state) {
        if (state) output << ',';
        output << '[' << static_cast<unsigned int>(table[state][0]) << ','
            << static_cast<unsigned int>(table[state][1]) << ']';
    }
    output << "],\"status\":\"exact\",\"merge_length\":" << score.length
        << ",\"lower_bound\":" << score.length << ",\"witness\":["
        << quote(score.witness[0]) << ',' << quote(score.witness[1]) << "]}\n";
}

struct Audit {
    std::uint64_t labelled_tables = 0, labelled_accessible = 0, classes = 0, scored = 0;
    bool enumeration_complete = false, scoring_complete = false, reference_equal = false;
    unsigned int maximum = 0;
    std::vector<std::string> maximizers;
    std::map<unsigned int, std::uint64_t> distribution;
    double enumeration_seconds = 0, scoring_seconds = 0;
    std::string failure;
};

void write_report(const std::filesystem::path& directory, const std::filesystem::path& reference,
    const Audit& audit)
{
    std::ofstream output(directory / "report.json", std::ios::binary);
    if (!output) throw std::runtime_error("cannot create audit report");
    const bool passed = audit.enumeration_complete && audit.scoring_complete && audit.reference_equal
        && audit.labelled_tables == 759375 && audit.classes == 10398 && audit.maximum == 15
        && audit.maximizers.size() == 5 && audit.failure.empty();
    output << "{\n  \"method\":\"independent-labelled-unordered-all-root-permutations-full-static-mask-vectors-v1\",\n"
        << "  \"m\":5,\n  \"ports_unordered\":true,\n  \"root_preserved\":true,\n  \"strong_connectivity_required\":false,\n"
        << "  \"labelled_tables\":" << audit.labelled_tables << ",\n  \"accessible_labelled_tables\":" << audit.labelled_accessible
        << ",\n  \"root_fixed_permutations_per_accessible_table\":24,\n  \"rooted_classes\":" << audit.classes
        << ",\n  \"graphs_scored\":" << audit.scored << ",\n  \"full_static_masks_per_graph\":32,\n"
        << "  \"enumeration_complete\":" << (audit.enumeration_complete ? "true" : "false")
        << ",\n  \"scoring_complete\":" << (audit.scoring_complete ? "true" : "false")
        << ",\n  \"reference\":" << quote(reference.generic_string())
        << ",\n  \"entire_reference_map_equal\":" << (audit.reference_equal ? "true" : "false")
        << ",\n  \"maximum\":" << audit.maximum << ",\n  \"maximizer_keys\":[";
    for (std::size_t i = 0; i < audit.maximizers.size(); ++i) {
        if (i) output << ',';
        output << quote(audit.maximizers[i]);
    }
    output << "],\n  \"score_distribution\":{";
    bool first = true;
    for (const auto& [length, count] : audit.distribution) {
        if (!first) output << ',';
        output << quote(std::to_string(length)) << ':' << count;
        first = false;
    }
    output << "},\n  \"enumeration_seconds\":" << audit.enumeration_seconds
        << ",\n  \"scoring_seconds\":" << audit.scoring_seconds
        << ",\n  \"regression_passed\":" << (passed ? "true" : "false")
        << ",\n  \"failure\":" << quote(audit.failure) << "\n}\n";
    if (!output) throw std::runtime_error("audit report write failure");
}
}

int main(int argc, char** argv)
{
    std::filesystem::path directory = "out/family1-independent-m5";
    std::filesystem::path reference = "out/family1-m1-m6/graphs.jsonl";
    Audit audit;
    try {
        for (int i = 1; i < argc; ++i) {
            const std::string option = argv[i];
            if (option == "--help") {
                std::cout << "Family1IndependentM5 [--out DIRECTORY] [--reference graphs.jsonl]\n";
                return 0;
            }
            if (++i == argc) throw std::runtime_error("missing option value");
            if (option == "--out") directory = argv[i];
            else if (option == "--reference") reference = argv[i];
            else throw std::runtime_error("unknown option: " + option);
        }
        std::filesystem::create_directories(directory);
        const auto expected = read_reference(reference);
        std::vector<Row> pairs;
        for (unsigned char a = 0; a < size; ++a)
            for (unsigned char b = a; b < size; ++b) pairs.push_back({a, b});
        std::uint64_t tables = 1;
        for (unsigned int state = 0; state < size; ++state) tables *= pairs.size();
        const auto enumeration_started = Clock::now();
        std::set<std::string> classes;
        for (std::uint64_t number = 0; number < tables; ++number) {
            auto value = number;
            Table table;
            for (auto& row : table) { row = pairs[value % pairs.size()]; value /= pairs.size(); }
            ++audit.labelled_tables;
            if (!accessible(table)) continue;
            ++audit.labelled_accessible;
            classes.insert(canonical_key(table));
        }
        audit.enumeration_complete = true;
        audit.classes = classes.size();
        audit.enumeration_seconds = std::chrono::duration<double>(Clock::now() - enumeration_started).count();
        std::cout << "Enumerated " << audit.labelled_tables << " labelled tables; " << audit.labelled_accessible
            << " accessible; " << audit.classes << " rooted classes in " << audit.enumeration_seconds << " s.\n";
        std::cout.flush();
        std::ofstream graphs(directory / "graphs.jsonl", std::ios::binary);
        if (!graphs) throw std::runtime_error("cannot create independent graph dataset");
        const auto scoring_started = Clock::now();
        std::map<std::string, unsigned int> actual;
        for (const auto& key : classes) {
            const auto table = decode(key);
            const auto result = score(table);
            verify_witness(table, result);
            write_graph(graphs, key, table, result);
            if (!graphs) throw std::runtime_error("independent graph dataset write failure");
            actual.emplace(key, result.length);
            ++audit.scored;
            ++audit.distribution[result.length];
            if (result.length > audit.maximum) { audit.maximum = result.length; audit.maximizers.clear(); }
            if (result.length == audit.maximum) audit.maximizers.push_back(key);
            if ((audit.scored % 1000) == 0) {
                std::cout << "Scored " << audit.scored << '/' << audit.classes << " classes.\n";
                std::cout.flush();
            }
        }
        graphs.close();
        if (!graphs) throw std::runtime_error("independent graph dataset close failure");
        audit.scoring_complete = true;
        audit.scoring_seconds = std::chrono::duration<double>(Clock::now() - scoring_started).count();
        audit.reference_equal = actual == expected;
        if (!audit.reference_equal) audit.failure = "entire independent class-to-score map differs from production reference";
        else if (audit.classes != 10398 || audit.maximum != 15 || audit.maximizers.size() != 5)
            audit.failure = "independent exhaustive result differs from expected m5 regression";
        write_report(directory, reference, audit);
        std::cout << "Global m5 " << (audit.failure.empty() ? "PASS" : "FAIL") << ": " << audit.scored
            << " exact classes, maximum " << audit.maximum << ", " << audit.maximizers.size()
            << " maximizers, full reference equality " << (audit.reference_equal ? "true" : "false")
            << ", scoring " << audit.scoring_seconds << " s.\n";
        return audit.failure.empty() ? 0 : 1;
    } catch (const std::exception& error) {
        audit.failure = error.what();
        std::cerr << "Independent m5 audit incomplete: " << error.what() << '\n';
        try {
            std::filesystem::create_directories(directory);
            write_report(directory, reference, audit);
        } catch (...) {}
        return 1;
    }
}

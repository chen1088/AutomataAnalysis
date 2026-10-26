// Independent journal verifier: deliberately no production headers or code.
// Rooted canonicalization tries every (m-1)! vertex permutation, and witnesses
// use scalar trajectories for every original static mask.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Table = std::vector<std::array<unsigned int, 2>>;
constexpr std::array<std::uint64_t, 8> burnside_counts{0, 1, 6, 57, 678, 10398, 192181, 4166855};

void require(bool condition, const std::string& message)
{
    if (!condition) throw std::runtime_error(message);
}

struct Record {
    std::uint64_t m = 0, ordinal = 0, lower = 0;
    std::optional<std::uint64_t> upper, merge;
    std::string key, status, reason;
    Table table;
    std::optional<std::array<std::string, 2>> witness;
};

// A strict parser for the documented journal schema. Unknown/duplicate fields,
// extra row entries, noninteger numbers, malformed escapes and trailing text
// fail the audit instead of being silently ignored.
class Parser {
    const std::string& text_;
    std::size_t at_ = 0;
    void space() { while (at_ < text_.size() && (text_[at_] == ' ' || text_[at_] == '\t' || text_[at_] == '\r' || text_[at_] == '\n')) ++at_; }
    bool take(char c) { space(); if (at_ < text_.size() && text_[at_] == c) { ++at_; return true; } return false; }
    void need(char c) { require(take(c), std::string("expected JSON character ") + c); }
    unsigned int hex4()
    {
        unsigned int value = 0;
        for (unsigned int i = 0; i < 4; ++i) {
            require(at_ < text_.size(), "truncated JSON Unicode escape");
            const char c = text_[at_++];
            unsigned int digit;
            if (c >= '0' && c <= '9') digit = c - '0';
            else if (c >= 'a' && c <= 'f') digit = c - 'a' + 10;
            else if (c >= 'A' && c <= 'F') digit = c - 'A' + 10;
            else throw std::runtime_error("invalid JSON Unicode escape");
            value = 16 * value + digit;
        }
        return value;
    }
    static void utf8(std::string& out, unsigned int value)
    {
        if (value < 0x80) out += static_cast<char>(value);
        else if (value < 0x800) { out += static_cast<char>(0xc0 | (value >> 6)); out += static_cast<char>(0x80 | (value & 63)); }
        else if (value < 0x10000) {
            out += static_cast<char>(0xe0 | (value >> 12)); out += static_cast<char>(0x80 | ((value >> 6) & 63)); out += static_cast<char>(0x80 | (value & 63));
        } else {
            out += static_cast<char>(0xf0 | (value >> 18)); out += static_cast<char>(0x80 | ((value >> 12) & 63));
            out += static_cast<char>(0x80 | ((value >> 6) & 63)); out += static_cast<char>(0x80 | (value & 63));
        }
    }
    std::string string()
    {
        need('"');
        std::string value;
        while (at_ < text_.size()) {
            const unsigned char c = text_[at_++];
            if (c == '"') return value;
            require(c >= 32, "unescaped control character in JSON string");
            if (c != '\\') { value += static_cast<char>(c); continue; }
            require(at_ < text_.size(), "truncated JSON escape");
            switch (text_[at_++]) {
            case '"': value += '"'; break;
            case '\\': value += '\\'; break;
            case '/': value += '/'; break;
            case 'b': value += '\b'; break;
            case 'f': value += '\f'; break;
            case 'n': value += '\n'; break;
            case 'r': value += '\r'; break;
            case 't': value += '\t'; break;
            case 'u': {
                auto point = hex4();
                if (point >= 0xd800 && point <= 0xdbff) {
                    require(at_ + 2 <= text_.size() && text_[at_] == '\\' && text_[at_ + 1] == 'u', "missing JSON low surrogate");
                    at_ += 2;
                    const auto low = hex4();
                    require(low >= 0xdc00 && low <= 0xdfff, "invalid JSON low surrogate");
                    point = 0x10000 + ((point - 0xd800) << 10) + low - 0xdc00;
                } else require(point < 0xdc00 || point > 0xdfff, "unexpected JSON low surrogate");
                utf8(value, point); break;
            }
            default: throw std::runtime_error("invalid JSON string escape");
            }
        }
        throw std::runtime_error("unterminated JSON string");
    }
    std::uint64_t number()
    {
        space();
        require(at_ < text_.size() && text_[at_] >= '0' && text_[at_] <= '9', "expected unsigned JSON integer");
        const auto start = at_;
        std::uint64_t value = 0;
        while (at_ < text_.size() && text_[at_] >= '0' && text_[at_] <= '9') {
            const auto digit = static_cast<unsigned int>(text_[at_++] - '0');
            require(value <= (std::numeric_limits<std::uint64_t>::max() - digit) / 10, "JSON integer overflow");
            value = 10 * value + digit;
        }
        require(at_ - start == 1 || text_[start] != '0', "JSON integer has a leading zero");
        return value;
    }
    bool null()
    {
        space();
        if (text_.compare(at_, 4, "null") != 0) return false;
        at_ += 4; return true;
    }
public:
    explicit Parser(const std::string& line) : text_(line) {}
    Record parse()
    {
        Record record;
        unsigned int seen = 0;
        need('{');
        if (!take('}')) for (;;) {
            const auto field = string(); need(':');
            static const std::array<std::string, 11> names{
                "m", "ordinal", "key", "canonical_table", "status", "lower_bound", "upper_bound", "merge_length", "witness", "reason", ""};
            const auto found = std::find(names.begin(), names.end() - 1, field);
            require(found != names.end() - 1, "unknown journal field: " + field);
            const auto index = static_cast<unsigned int>(found - names.begin());
            require((seen & (1U << index)) == 0, "duplicate journal field: " + field);
            seen |= 1U << index;
            switch (index) {
            case 0: record.m = number(); break;
            case 1: record.ordinal = number(); break;
            case 2: record.key = string(); break;
            case 3:
                need('[');
                if (!take(']')) for (;;) {
                    need('['); const auto a = number(); need(','); const auto b = number(); need(']');
                    require(a <= 20 && b <= 20, "transition target out of supported range");
                    record.table.push_back({static_cast<unsigned int>(a), static_cast<unsigned int>(b)});
                    if (take(']')) break;
                    need(',');
                }
                break;
            case 4: record.status = string(); break;
            case 5: record.lower = number(); break;
            case 6: if (!null()) record.upper = number(); break;
            case 7: if (!null()) record.merge = number(); break;
            case 8:
                if (!null()) {
                    need('['); const auto first = string(); need(','); const auto second = string(); need(']');
                    record.witness = std::array<std::string, 2>{first, second};
                }
                break;
            case 9: record.reason = string(); break;
            }
            if (take('}')) break;
            need(',');
        }
        require(seen == (1U << 10) - 1, "journal record is missing a required field");
        space(); require(at_ == text_.size(), "trailing text after journal record");
        return record;
    }
};

using Permutation = std::array<unsigned int, 7>;
struct Relabelling { Permutation old_to_new{}, new_to_old{}; };
std::vector<Relabelling> all_root_permutations(unsigned int states)
{
    Permutation permutation{};
    std::iota(permutation.begin(), permutation.end(), 0U);
    std::vector<Relabelling> permutations;
    do {
        Relabelling relabel; relabel.old_to_new = permutation;
        for (unsigned int old = 0; old < states; ++old) relabel.new_to_old[permutation[old]] = old;
        permutations.push_back(relabel);
    } while (std::next_permutation(permutation.begin() + 1, permutation.begin() + states));
    return permutations;
}

void check_canonical(const Table& table, const std::vector<Relabelling>& permutations)
{
    for (const auto& map : permutations) {
        for (unsigned int source = 0; source < table.size(); ++source) {
            const auto& old_row = table[map.new_to_old[source]];
            auto a = map.old_to_new[old_row[0]], b = map.old_to_new[old_row[1]];
            if (a > b) std::swap(a, b);
            const std::array<unsigned int, 2> candidate{a, b};
            require(candidate >= table[source], "transition table is not rooted canonical under all vertex permutations and port swaps");
            if (candidate > table[source]) break;
        }
    }
}

void check_accessible(const Table& table)
{
    std::array<bool, 7> reached{};
    std::array<unsigned int, 7> pending{};
    reached[0] = true;
    unsigned int head = 0, tail = 1;
    while (head < tail) {
        for (auto target : table[pending[head++]])
            if (!reached[target]) { reached[target] = true; pending[tail++] = target; }
    }
    require(tail == table.size(), "graph contains a vertex unreachable from root 0");
}

void check_upper_witness(const Record& record)
{
    require(record.upper.has_value() == record.witness.has_value(), "upper bound and witness must either both be present or both be null");
    if (!record.upper) return;
    const auto& words = *record.witness;
    require(*record.upper > 0 && words[0].size() == *record.upper && words[1].size() == *record.upper,
        "upper witness length does not match upper bound");
    require(words[0] != words[1], "upper witness contains identical words");
    for (const auto& word : words)
        require(word.find_first_not_of("01") == std::string::npos, "upper witness contains a nonbinary letter");
    for (unsigned int mask = 0; mask < (1U << record.m); ++mask) {
        std::array<unsigned int, 2> state{};
        for (unsigned int side = 0; side < 2; ++side)
            for (char letter : words[side]) {
                const auto source = state[side];
                state[side] = record.table[source][(letter - '0') ^ ((mask >> source) & 1U)];
            }
        require(state[0] == state[1], "upper witness is separated by original static mask " + std::to_string(mask));
    }
}

std::string quote(const std::string& value)
{
    static constexpr char hex[] = "0123456789abcdef";
    std::string out = "\"";
    for (unsigned char c : value) {
        if (c == '\\' || c == '"') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 32) { out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15]; }
        else out += static_cast<char>(c);
    }
    return out + '"';
}

struct Audit {
    unsigned int states = 0;
    std::filesystem::path journal, output = "out/family1-exhaustive-verify.json";
    std::optional<std::uint64_t> requested_count;
    std::uint64_t records = 0, upper_verified = 0, exact_claims = 0, bounded = 0, capped = 0, incomplete = 0;
    std::uint64_t maximum_verified_upper = 0, largest_claimed_lower = 1, lower_claims_above_one = 0, line = 0;
    std::map<std::uint64_t, std::uint64_t> upper_bound_distribution;
    std::vector<std::string> keys_at_largest_verified_upper_bound;
    std::size_t permutations = 0;
    bool passed = false;
    std::string failure;
    double seconds = 0;
};

bool same_file(const std::filesystem::path& first, const std::filesystem::path& second)
{
    std::error_code error;
    if (std::filesystem::equivalent(first, second, error)) return true;
    return std::filesystem::absolute(first).lexically_normal() == std::filesystem::absolute(second).lexically_normal();
}

void write_report(const Audit& audit)
{
    if (audit.output.has_parent_path()) std::filesystem::create_directories(audit.output.parent_path());
    std::ofstream out(audit.output, std::ios::binary);
    require(static_cast<bool>(out), "cannot write verifier report: " + audit.output.string());
    const auto expected = audit.states > 0 && audit.states < burnside_counts.size() ? burnside_counts[audit.states] : 0;
    const bool complete = audit.passed && audit.records == expected && expected != 0;
    const bool upper_complete = complete && audit.upper_verified == audit.records;
    out << "{\n  \"schema\":1,\n  \"verifier\":\"independent-root-permutations-scalar-static-masks-v1\",\n"
        << "  \"m\":" << audit.states << ",\n  \"journal\":" << quote(audit.journal.generic_string())
        << ",\n  \"verification_passed\":" << (audit.passed ? "true" : "false")
        << ",\n  \"records_verified\":" << audit.records << ",\n  \"burnside_expected_classes\":" << expected
        << ",\n  \"requested_expected_count\":" << (audit.requested_count ? std::to_string(*audit.requested_count) : "null")
        << ",\n  \"root_fixed_permutations_checked_per_graph\":" << audit.permutations
        << ",\n  \"original_static_masks_checked_per_upper_witness\":" << (audit.states <= 7 ? (1U << audit.states) : 0)
        << ",\n  \"enumeration_complete\":" << (complete ? "true" : "false")
        << ",\n  \"upper_witnesses_verified\":" << audit.upper_verified
        << ",\n  \"records_without_verified_upper\":" << (audit.records - audit.upper_verified)
        << ",\n  \"global_upper_bound_verified\":" << (upper_complete ? std::to_string(audit.maximum_verified_upper) : "null")
        << ",\n  \"largest_verified_individual_upper_bound\":" << (audit.upper_verified ? std::to_string(audit.maximum_verified_upper) : "null");
    out << ",\n  \"upper_bound_distribution\":{";
    bool first_bound = true;
    for (const auto& [bound, count] : audit.upper_bound_distribution) {
        if (!first_bound) out << ',';
        first_bound = false;
        out << quote(std::to_string(bound)) << ':' << count;
    }
    out << "},\n  \"keys_at_largest_verified_upper_bound\":[";
    for (std::size_t index = 0; index < audit.keys_at_largest_verified_upper_bound.size(); ++index) {
        if (index) out << ',';
        out << quote(audit.keys_at_largest_verified_upper_bound[index]);
    }
    out << "]"
        << ",\n  \"claimed_exact_records\":" << audit.exact_claims << ",\n  \"bounded_records\":" << audit.bounded
        << ",\n  \"depth_capped_records\":" << audit.capped << ",\n  \"incomplete_records\":" << audit.incomplete
        << ",\n  \"largest_inherited_claimed_lower_bound\":" << audit.largest_claimed_lower
        << ",\n  \"inherited_lower_bound_claims_above_one\":" << audit.lower_claims_above_one
        << ",\n  \"independently_verified_lower_bound_per_graph\":1,\n  \"lower_proofs_checked\":false,\n"
        << "  \"maximum_value_certified\":false,\n  \"maximizing_collection_complete\":false,\n"
        << "  \"scope\":\"Checks every parsed graph for root accessibility, exact table/key agreement, consecutive zero-based ordinals, strict key order, and canonicality under all root-fixing vertex permutations with independent port swaps. Every upper witness is independently simulated over every original static mask. Complete coverage requires the known Burnside count, regardless of --expected-count.\",\n"
        << "  \"lower_bound_warning\":\"Input lower bounds greater than 1 and claimed exact minimal lengths are inherited claims, not independently proved by this verifier. No shortest-length proof or complete tie certificate is claimed.\",\n"
        << "  \"upper_frontier_note\":\"The distribution and frontier keys describe independently verified witness upper bounds. Identifying actual maximizers additionally requires independently checked matching lower proofs for every frontier graph.\",\n"
        << "  \"seconds\":" << audit.seconds << ",\n  \"failure_line\":" << (audit.failure.empty() ? "null" : std::to_string(audit.line))
        << ",\n  \"failure\":" << quote(audit.failure) << "\n}\n";
    require(static_cast<bool>(out), "verifier report write failed");
}
}

int main(int argc, char** argv)
{
    Audit audit;
    const auto started = std::chrono::steady_clock::now();
    try {
        for (int i = 1; i < argc; ++i) {
            const std::string option = argv[i];
            if (option == "--help") {
                std::cout << "Family1ExhaustiveVerify --journal FILE --states 1..7 [--out REPORT.json] [--expected-count N]\n"
                    << "Audits prefixes too. --expected-count asserts a record count; global coverage always requires the Burnside count.\n"
                    << "Upper witnesses are independently proved. Nontrivial lower bounds and exact minimality are NOT independently proved.\n";
                return 0;
            }
            require(i + 1 < argc, "missing value for " + option);
            const std::string value = argv[++i];
            if (option == "--journal") audit.journal = value;
            else if (option == "--out") audit.output = value;
            else if (option == "--states" || option == "--expected-count") {
                std::size_t consumed = 0;
                require(!value.empty() && value.find_first_not_of("0123456789") == std::string::npos, "invalid numeric command argument");
                const auto number = std::stoull(value, &consumed);
                require(consumed == value.size(), "invalid numeric command argument");
                if (option == "--states") { require(number >= 1 && number <= 7, "states must be in 1..7"); audit.states = static_cast<unsigned int>(number); }
                else audit.requested_count = number;
            } else throw std::runtime_error("unknown option: " + option);
        }
        require(audit.states >= 1 && audit.states <= 7 && !audit.journal.empty(), "--states and --journal are required");
        require(!same_file(audit.journal, audit.output), "report path must differ from journal path");
        const auto permutations = all_root_permutations(audit.states);
        audit.permutations = permutations.size();
        std::ifstream input(audit.journal, std::ios::binary);
        require(static_cast<bool>(input), "cannot open journal: " + audit.journal.string());
        std::string previous_key;
        for (std::string line; std::getline(input, line);) {
            ++audit.line;
            if (audit.line == 1 && line.compare(0, 3, "\xef\xbb\xbf") == 0) line.erase(0, 3);
            const auto record = Parser(line).parse();
            require(record.m == audit.states && record.table.size() == audit.states, "record state count differs from --states");
            require(record.ordinal == audit.records, "record ordinal is not consecutive from zero");
            std::string key;
            for (const auto& row : record.table) for (auto target : row) {
                require(target < audit.states, "transition target lies outside graph");
                key += static_cast<char>('0' + target / 10); key += static_cast<char>('0' + target % 10);
            }
            require(key == record.key, "canonical_table and fixed-two-digit key disagree");
            require(previous_key.empty() || previous_key < key, "keys are duplicated or not in strict lexicographic order");
            check_accessible(record.table);
            check_canonical(record.table, permutations);
            require(record.lower >= 1, "lower bound must be positive");
            if (record.upper) require(record.lower <= *record.upper, "claimed lower bound exceeds verified upper bound");
            require(record.status == "exact" || record.status == "bounded" || record.status == "depth-capped" || record.status == "incomplete", "unknown record status");
            if (record.status == "exact") {
                require(record.merge && record.upper && *record.merge == record.lower && *record.merge == *record.upper,
                    "claimed exact score has inconsistent merge/lower/upper bounds");
            } else {
                require(!record.merge, "nonexact record contains merge_length");
                if (record.status == "bounded") require(record.upper.has_value(), "bounded record has no upper witness");
            }
            check_upper_witness(record);
            // Only update verified counters after ALL checks pass for a record.
            previous_key = key;
            ++audit.records;
            require(audit.records <= burnside_counts[audit.states], "journal exceeds Burnside class count");
            if (record.upper) {
                ++audit.upper_verified;
                ++audit.upper_bound_distribution[*record.upper];
                if (*record.upper > audit.maximum_verified_upper) {
                    audit.maximum_verified_upper = *record.upper;
                    audit.keys_at_largest_verified_upper_bound.clear();
                }
                if (*record.upper == audit.maximum_verified_upper)
                    audit.keys_at_largest_verified_upper_bound.push_back(record.key);
            }
            audit.largest_claimed_lower = std::max(audit.largest_claimed_lower, record.lower);
            audit.lower_claims_above_one += record.lower > 1;
            if (record.status == "exact") ++audit.exact_claims;
            else if (record.status == "bounded") ++audit.bounded;
            else if (record.status == "depth-capped") ++audit.capped;
            else ++audit.incomplete;
        }
        require(input.eof(), "journal read failure");
        if (audit.requested_count) require(audit.records == *audit.requested_count, "journal record count differs from --expected-count");
        audit.passed = true;
        audit.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        write_report(audit);
        std::cout << "PASS: " << audit.records << " canonical graphs, " << audit.upper_verified << " scalar all-mask upper witnesses; "
            << "coverage " << (audit.records == burnside_counts[audit.states] ? "complete" : "prefix/incomplete")
            << "; nontrivial lower proofs unchecked. Report: " << audit.output.string() << '\n';
        return 0;
    } catch (const std::exception& error) {
        audit.failure = error.what(); audit.passed = false;
        audit.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        std::cerr << "FAIL at journal line " << audit.line << ": " << audit.failure << '\n';
        // Never replace the journal, even when invalid output arguments caused
        // the failure. Other invalid runs still receive an explicit report.
        try {
            if (audit.journal.empty() || !same_file(audit.journal, audit.output)) write_report(audit);
        } catch (const std::exception& report_error) { std::cerr << "Report failure: " << report_error.what() << '\n'; }
        return 1;
    }
}

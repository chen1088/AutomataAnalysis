// Dependency-free scalar benchmark for the generic four-letter pair finder.
// The exact reference enumerates SINGLE words independently at each length.
// No fixture label, saved witness, random source, or packed Family1 code enters
// either this adapter or the reference search.
#include "HardPairJointFinder.h"
#include <array>
#include <chrono>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using Clock = std::chrono::steady_clock;
struct DFA {
    unsigned root = 0;
    std::vector<std::array<unsigned, 2>> table;
    bool both_letters_permutations = false;
};
using Family = std::vector<DFA>;
using Profile = std::vector<unsigned>;

static Profile start(const Family& family) {
    Profile p;
    for (const auto& dfa : family) p.push_back(dfa.root);
    return p;
}
static Profile advance(const Family& family, const Profile& p, bool letter) {
    Profile next;
    next.reserve(family.size());
    for (std::size_t i = 0; i < family.size(); ++i)
        next.push_back(family[i].table[p[i]][letter]);
    return next;
}
static Profile replay(const Family& family, const std::string& word) {
    Profile p = start(family);
    for (char letter : word) p = advance(family, p, letter == '1');
    return p;
}
struct ScalarPair {
    std::shared_ptr<const Family> family;
    Profile left, right;
    std::string first, second;
    explicit ScalarPair(std::shared_ptr<const Family> f)
        : family(std::move(f)), left(start(*family)), right(left) {}
    ScalarPair append_pair(bool a, bool b) const {
        ScalarPair next(*this);
        next.left = advance(*family, left, a);
        next.right = advance(*family, right, b);
        next.first += a ? '1' : '0'; next.second += b ? '1' : '0';
        return next;
    }
    std::uint64_t remaining_count() const {
        std::uint64_t count = 0;
        for (std::size_t i = 0; i < left.size(); ++i) count += left[i] != right[i];
        return count;
    }
    std::uint64_t mask_count() const { return family->size(); }
    std::uint64_t priority_remaining_count() const {
        std::uint64_t count = 0;
        for (std::size_t i = 0; i < left.size(); ++i)
            count += left[i] != right[i] && (*family)[i].both_letters_permutations;
        return count;
    }
    bool distinct() const { return first != second; }
    const std::string& first_word() const { return first; }
    const std::string& second_word() const { return second; }
    bool operator==(const ScalarPair& other) const {
        return family == other.family && left == other.left && right == other.right
            && distinct() == other.distinct();
    }
};

struct Oracle {
    bool found = false, capped = false;
    unsigned length = 0, completed_depth = 0;
    std::string first, second;
    std::uint64_t expansions = 0, cap = 0;
    double seconds = 0;
};
static Oracle exact(const Family& family, unsigned max_depth, std::uint64_t cap) {
    const auto began = Clock::now();
    Oracle out; out.cap = cap;
    // Before the first collision each profile has exactly one word at this
    // length. Equality is the entire heterogeneous endpoint vector, not D.
    std::map<Profile, std::string> layer{{start(family), ""}};
    for (unsigned depth = 1; depth <= max_depth; ++depth) {
        if (layer.size() > (cap - out.expansions) / 2) {
            out.capped = true; break; // the next full layer was not started
        }
        std::map<Profile, std::string> next;
        for (const auto& [profile, word] : layer) for (unsigned bit = 0; bit < 2; ++bit) {
            Profile target = advance(family, profile, bit != 0);
            std::string text = word + char('0' + bit);
            ++out.expansions;
            const auto [at, inserted] = next.emplace(std::move(target), text);
            if (!inserted) {
                out.found = true; out.length = depth;
                out.first = at->second; out.second = text;
                if (out.first > out.second) std::swap(out.first, out.second);
                out.seconds = std::chrono::duration<double>(Clock::now() - began).count();
                return out;
            }
        }
        layer = std::move(next); out.completed_depth = depth;
    }
    out.seconds = std::chrono::duration<double>(Clock::now() - began).count();
    return out;
}
static std::string quote(const std::string& text) {
    std::string out = "\"";
    for (char c : text) {
        if (c == '\\' || c == '"') out += '\\';
        if (c == '\n') out += "\\n";
        else out += c;
    }
    return out + '"';
}
static std::string pair_json(bool found, const std::string& a, const std::string& b) {
    return found ? "[" + quote(a) + "," + quote(b) + "]" : "null";
}

int main(int argc, char** argv) try {
    std::string input;
    unsigned max_length = 48, beam = 1, diagonal = 1, unequal = 0, oracle_depth = 40;
    int common_depth = -1;
    bool prioritize_permutation = false;
    std::uint64_t expansion_cap = 500000, oracle_cap = 150000;
    std::vector<unsigned> ks{2, 4, 6};
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (i + 1 >= argc) throw std::invalid_argument("missing option value");
        const std::string value = argv[++i];
        if (arg == "--input") input = value;
        else if (arg == "--k") {
            ks.clear(); std::istringstream stream(value); std::string item;
            while (std::getline(stream, item, ',')) ks.push_back(std::stoul(item));
        } else if (arg == "--beam") beam = std::stoul(value);
        else if (arg == "--diagonal") diagonal = std::stoul(value);
        else if (arg == "--unequal") unequal = std::stoul(value);
        else if (arg == "--max-length") max_length = std::stoul(value);
        else if (arg == "--expansions") expansion_cap = std::stoull(value);
        else if (arg == "--oracle-depth") oracle_depth = std::stoul(value);
        else if (arg == "--oracle-cap") oracle_cap = std::stoull(value);
        else if (arg == "--startup-common-depth") common_depth = std::stoi(value);
        else if (arg == "--prioritize-permutation") prioritize_permutation = std::stoul(value) != 0;
        else throw std::invalid_argument("unknown option: " + arg);
    }
    std::ifstream stream(input);
    unsigned count = 0;
    if (!(stream >> count) || !count) throw std::invalid_argument("empty family input");
    auto family = std::make_shared<Family>();
    for (unsigned i = 0; i < count; ++i) {
        unsigned n = 0, root = 0;
        if (!(stream >> n >> root) || !n || root >= n) throw std::invalid_argument("bad DFA header");
        DFA dfa; dfa.root = root; dfa.table.resize(n);
        for (auto& row : dfa.table) for (auto& target : row)
            if (!(stream >> target) || target >= n) throw std::invalid_argument("bad DFA target");
        dfa.both_letters_permutations = true;
        for (unsigned bit = 0; bit < 2; ++bit) {
            std::vector<bool> seen(n, false);
            for (const auto& row : dfa.table) {
                if (seen[row[bit]]) dfa.both_letters_permutations = false;
                seen[row[bit]] = true;
            }
        }
        family->push_back(std::move(dfa));
    }
    std::string extra;
    if (stream >> extra) throw std::invalid_argument("unexpected trailing input");
    const auto oracle = exact(*family, oracle_depth, oracle_cap);
    if (oracle.found && (oracle.first == oracle.second
        || replay(*family, oracle.first) != replay(*family, oracle.second)))
        throw std::logic_error("exact oracle witness failed scalar replay");
    for (const auto k : ks) {
        hardpair::joint::Options options;
        options.window_k = k; options.beam_width = beam; options.diagonal_width = diagonal;
        options.unequal_width = unequal; options.max_length = max_length;
        options.max_expansions = expansion_cap;
        options.prioritize_permutation = prioritize_permutation;
        struct Attempt {
            std::string prefix, orientation;
            unsigned difference_depth = 0;
            hardpair::joint::Result result;
        };
        std::vector<Attempt> attempts;
        const auto began = Clock::now();
        if (common_depth < 0) attempts.push_back({"", "", 0,
            hardpair::joint::find_pair(ScalarPair(family), options)});
        else {
            const auto plan = hardpair::joint::divergence_starts(ScalarPair(family), common_depth);
            if (!plan.complete) throw std::logic_error("incomplete startup plan");
            for (const auto& entry : plan.starts) {
                if (entry.state.first_word().size() > max_length)
                    throw std::invalid_argument("maximum length shorter than startup set");
                attempts.push_back({entry.common_prefix, entry.orientation, entry.first_difference_depth,
                    hardpair::joint::find_pair(entry.state, options)});
            }
        }
        const auto seconds = std::chrono::duration<double>(Clock::now() - began).count();
        hardpair::joint::Result result;
        std::uint64_t expanded_nodes = 0, complete_windows = 0, partial_windows = 0;
        std::uint64_t refused_windows = 0, visited_leaves = 0, expansion_capped_attempts = 0;
        unsigned maximum_depth = 0;
        bool beam_truncated = false, length_reached = false;
        for (const auto& attempt : attempts) {
            const auto& r = attempt.result;
            const bool verified = !r.found || (r.first != r.second && r.first.size() == r.second.size()
                && replay(*family, r.first) == replay(*family, r.second));
            if (!verified || r.partial_windows) throw std::logic_error("invalid heuristic result");
            if (r.found && (!result.found || std::pair{r.length, std::pair{r.first, r.second}}
                < std::pair{result.length, std::pair{result.first, result.second}})) result = r;
            expanded_nodes += r.expanded_nodes; complete_windows += r.complete_windows;
            partial_windows += r.partial_windows; refused_windows += r.windows_refused;
            visited_leaves += r.visited_leaves; expansion_capped_attempts += r.expansion_limit_reached;
            maximum_depth = std::max(maximum_depth, r.maximum_depth_visited);
            beam_truncated |= r.beam_truncated; length_reached |= r.length_limit_reached;
            for (const auto& window : r.windows) {
                std::uint64_t leaves = 1, nodes = 0;
                for (unsigned d = 0; d < window.span; ++d) { leaves *= 4; nodes += leaves; }
                if (!window.complete || window.leaves != leaves || window.nodes != nodes)
                    throw std::logic_error("incomplete four-letter comparison");
            }
        }
        if (result.found && oracle.found && result.length < oracle.length)
            throw std::logic_error("heuristic shorter than exact independent oracle");
        std::cout << "{\"k\":" << k << ",\"beam\":" << beam
            << ",\"diagonal_beam\":" << diagonal << ",\"unequal_beam\":" << unequal
            << ",\"max_length\":" << max_length << ",\"family_size\":" << family->size()
            << ",\"ranking\":\"" << (prioritize_permutation ? "permutation-D,total-D,lex" : "total-D,lex") << '"'
            << ",\"permutation_coordinate_count\":" << std::count_if(family->begin(), family->end(),
                [](const auto& dfa) { return dfa.both_letters_permutations; })
            << ",\"expansion_cap_per_attempt\":" << expansion_cap
            << ",\"expansion_cap\":" << expansion_cap * attempts.size()
            << ",\"coordinate_weight_policy\":\"one-per-distinct-rooted-DFA-table\""
            << ",\"startup\":{\"mode\":\"" << (common_depth < 0 ? "empty-root" : "all-common-prefixes-then-first-difference")
            << "\",\"common_depth\":";
        if (common_depth < 0) std::cout << "null"; else std::cout << common_depth;
        std::cout << ",\"expected_starts\":" << attempts.size()
            << ",\"attempted_starts\":" << attempts.size() << ",\"all_starts_tested\":true},\"status\":\""
            << (result.found ? "verified-upper" : "unresolved") << "\",\"upper_bound\":";
        if (result.found) std::cout << result.length; else std::cout << "null";
        std::cout << ",\"witness\":" << pair_json(result.found, result.first, result.second)
            << ",\"scalar_replay_coordinates\":" << (result.found ? family->size() : 0)
            << ",\"seconds\":" << seconds << ",\"expanded_nodes\":" << expanded_nodes
            << ",\"complete_windows\":" << complete_windows
            << ",\"partial_windows\":" << partial_windows
            << ",\"refused_windows\":" << refused_windows
            << ",\"visited_leaves\":" << visited_leaves
            << ",\"maximum_depth_visited\":" << maximum_depth
            << ",\"beam_truncated\":" << (beam_truncated ? "true" : "false")
            << ",\"expansion_limit_reached\":" << (expansion_capped_attempts ? "true" : "false")
            << ",\"expansion_capped_attempts\":" << expansion_capped_attempts
            << ",\"length_limit_reached\":" << (length_reached ? "true" : "false")
            << ",\"minimality_certified\":false,\"attempts\":[";
        for (std::size_t index = 0; index < attempts.size(); ++index) {
            const auto& a = attempts[index]; const auto& r = a.result;
            if (index) std::cout << ',';
            std::cout << "{\"common_prefix\":" << quote(a.prefix)
                << ",\"orientation\":" << quote(a.orientation)
                << ",\"first_difference_depth\":" << a.difference_depth
                << ",\"initial_D\":" << r.initial_remaining
                << ",\"initial_distinct\":" << (r.initial_distinct ? "true" : "false")
                << ",\"first_greedy_depth\":" << r.first_greedy_depth
                << ",\"witness\":" << pair_json(r.found, r.first, r.second)
                << ",\"upper_bound\":";
            if (r.found) std::cout << r.length; else std::cout << "null";
            std::cout << ",\"expanded_nodes\":" << r.expanded_nodes
                << ",\"complete_windows\":" << r.complete_windows
                << ",\"expansion_limit_reached\":" << (r.expansion_limit_reached ? "true" : "false")
                << ",\"length_limit_reached\":" << (r.length_limit_reached ? "true" : "false") << '}';
        }
        std::cout << "],\"oracle\":{\"method\":\"independent-single-word-layer-profile-collision\",\"k\":null,\"exact\":"
            << (oracle.found ? "true" : "false") << ",\"H\":";
        if (oracle.found) std::cout << oracle.length; else std::cout << "null";
        std::cout << ",\"witness\":" << pair_json(oracle.found, oracle.first, oracle.second)
            << ",\"completed_collision_free_depth\":" << oracle.completed_depth
            << ",\"lower_bound\":" << oracle.completed_depth + 1
            << ",\"expansions\":" << oracle.expansions << ",\"expansion_cap\":" << oracle.cap
            << ",\"capped\":" << (oracle.capped ? "true" : "false")
            << ",\"seconds\":" << oracle.seconds << "}}\n";
    }
    return 0;
} catch (const std::exception& error) {
    std::cerr << error.what() << '\n'; return 2;
}

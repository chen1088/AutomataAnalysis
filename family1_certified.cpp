#include "Family1Certified.h"
#include "Family1Signatures.h"
#include "Family1CertifiedHeuristic.h"
#include "Family1CliArtifacts.h"
#include "Family1LargeGraph.h"
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace cert = family1::certified;
namespace cli = family1_cli;
namespace {
volatile std::sig_atomic_t stopped = 0;
void interrupt(int) { stopped = 1; }
struct Options {
    std::vector<cert::Seed> seeds;
    std::vector<cert::Observer> observers;
    std::vector<std::vector<cert::Observer>> projections;
    cert::Limits limits;
    hardpair::joint::Options heuristic;
    unsigned horizon = 0, gap = 0;
    bool has_horizon = false, has_gap = false, has_upper = false;
    bool left_upper = false, right_upper = false;
    std::string signature, prefix_u, prefix_v, upper_u, upper_v;
    cli::fs::path out;
    Options() { heuristic.max_expansions = 0; heuristic.window_k = 4; heuristic.beam_width = 16; }
};
std::uint64_t number(const std::string& value) {
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("expected nonnegative integer: " + value);
    return std::stoull(value);
}
unsigned small(const std::string& value) {
    const auto n = number(value);
    if (n > 4096) throw std::invalid_argument("option exceeds 4096");
    return static_cast<unsigned>(n);
}
cert::Observer observer(const std::string& value) {
    const auto colon = value.find(':');
    if (colon == std::string::npos) throw std::invalid_argument("observer requires seed:mask");
    return {static_cast<std::size_t>(number(value.substr(0, colon))), number(value.substr(colon + 1))};
}
void help() {
    std::cout << "Family1Certified --seed KEY [--seed KEY ...] --horizon T --out FILE\n"
        "The target is the UNION of all original static-mask closures. KEY uses\n"
        "the existing four-digits-per-row graph encoding; seed order is retained.\n"
        " --root N / --name TEXT: set the preceding seed's root/name\n"
        " --observer seed:mask: initial selected observer, repeatable\n"
        " --signature count|first-difference: exact projection signature mode\n"
        " --projection seed:mask,seed:mask: repeatable observer groups\n"
        "   Default groups are selected singletons, else all original singletons.\n"
        " --prefix-u WORD --prefix-v WORD: signature residual diagnostic only\n"
        " --upper-u WORD --upper-v WORD: independently verify imported incumbent\n"
        " --gap D: instead of --horizon, certify U-D <= H <= U when possible\n"
        " --heuristic-expansions N: optional existing joint finder, full union\n"
        " --heuristic-k K --heuristic-beam N --heuristic-length N\n"
        " --states N (100000) --work N (1000000) --verifier-steps N (10000000)\n"
        " --timeout-ms N (10000; 0 disables) --refinements N (1024)\n"
        "Caps are cumulative. An unfinished proof gives no new lower bound.\n"
        "Check the JSON artifact using scripts/family1_check_certificate.py.\n";
}
Options parse(int argc, char** argv) {
    Options o;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") { help(); std::exit(0); }
        if (++i == argc) throw std::invalid_argument("missing value for " + arg);
        const std::string value = argv[i];
        if (arg == "--seed") {
            auto g = family1::LargeGraph::from_key(value);
            o.seeds.push_back({"seed-" + std::to_string(o.seeds.size()), 0, g.ports});
        } else if (arg == "--root" || arg == "--name") {
            if (o.seeds.empty()) throw std::invalid_argument(arg + " requires a preceding --seed");
            if (arg == "--root") o.seeds.back().root = small(value); else o.seeds.back().name = value;
        } else if (arg == "--observer") o.observers.push_back(observer(value));
        else if (arg == "--projection") {
            std::vector<cert::Observer> group;
            std::istringstream stream(value);
            std::string item;
            while (std::getline(stream, item, ',')) group.push_back(observer(item));
            if (group.empty() || value.back() == ',') throw std::invalid_argument("empty projection");
            o.projections.push_back(std::move(group));
        } else if (arg == "--out") o.out = value;
        else if (arg == "--signature") o.signature = value;
        else if (arg == "--prefix-u") o.prefix_u = value;
        else if (arg == "--prefix-v") o.prefix_v = value;
        else if (arg == "--upper-u") { o.upper_u = value; o.left_upper = true; }
        else if (arg == "--upper-v") { o.upper_v = value; o.right_upper = true; }
        else if (arg == "--horizon") { o.horizon = small(value); o.has_horizon = true; }
        else if (arg == "--gap") { o.gap = small(value); o.has_gap = true; }
        else if (arg == "--states") o.limits.max_states = number(value);
        else if (arg == "--work") o.limits.max_work = number(value);
        else if (arg == "--verifier-steps") o.limits.max_verifier_steps = number(value);
        else if (arg == "--timeout-ms") o.limits.timeout_ms = number(value);
        else if (arg == "--refinements") o.limits.max_refinements = number(value);
        else if (arg == "--heuristic-expansions") o.heuristic.max_expansions = number(value);
        else if (arg == "--heuristic-k") o.heuristic.window_k = small(value);
        else if (arg == "--heuristic-beam") o.heuristic.beam_width = small(value);
        else if (arg == "--heuristic-length") o.heuristic.max_length = small(value);
        else throw std::invalid_argument("unknown option: " + arg);
    }
    if (o.seeds.empty() || o.out.empty() || o.has_horizon == o.has_gap)
        throw std::invalid_argument("require seeds, --out, and exactly one of --horizon/--gap");
    if (!o.signature.empty() && o.signature != "count" && o.signature != "first-difference")
        throw std::invalid_argument("unknown signature");
    if (!o.projections.empty() && o.signature.empty()) throw std::invalid_argument("projections require --signature");
    if (o.left_upper != o.right_upper) throw std::invalid_argument("both upper words are required");
    o.has_upper = o.left_upper;
    const bool residual = !o.prefix_u.empty() || !o.prefix_v.empty();
    if (o.prefix_u.size() != o.prefix_v.size() || o.prefix_u.size() > 4096 ||
        o.prefix_u.find_first_not_of("01") != std::string::npos ||
        o.prefix_v.find_first_not_of("01") != std::string::npos ||
        (residual && (o.signature.empty() || o.has_gap || o.has_upper || o.heuristic.max_expansions)))
        throw std::invalid_argument("prefixes require a signature horizon diagnostic and equal-length binary words");
    if (o.has_gap && !o.has_upper && !o.heuristic.max_expansions)
        throw std::invalid_argument("--gap requires imported upper words or a heuristic budget");
    if (!o.limits.max_states || !o.limits.max_work || !o.limits.max_verifier_steps)
        throw std::invalid_argument("state/work/verifier budgets must be positive");
    if (o.has_upper && (o.upper_u.size() > 4096 || o.upper_v.size() > 4096))
        throw std::invalid_argument("upper words exceed 4096 symbols");
    o.out = cli::fs::absolute(o.out);
    if (cli::fs::exists(o.out)) throw std::invalid_argument("refusing to overwrite " + o.out.string());
    return o;
}
void emit_observers(std::ostream& out, const std::vector<cert::Observer>& selected) {
    out << '[';
    for (std::size_t i = 0; i < selected.size(); ++i) {
        if (i) out << ',';
        out << "{\"seed\":" << selected[i].seed << ",\"mask\":" << selected[i].mask << '}';
    }
    out << ']';
}
void emit_state(std::ostream& out, const cert::State& state) {
    out << "\"endpoints\":[";
    for (std::size_t i = 0; i < state.endpoints.size(); i += 2) {
        if (i) out << ',';
        out << '[' << state.endpoints[i] << ',' << state.endpoints[i + 1] << ']';
    }
    out << "],\"distinct\":" << (state.distinct ? "true" : "false");
}
void emit_signature(std::ostream& out, const cert::Signature& s) {
    out << '[' << s[0] << ',' << s[1] << ',' << s[2] << ',' << s[3] << ']';
}
std::string paired_proof(unsigned horizon, const cert::RefinementResult& result) {
    std::ostringstream out;
    out << "{\"kind\":\"paired-layers\",\"horizon\":" << horizon << ",\"observers\":";
    emit_observers(out, result.selected);
    out << ",\"layers\":[";
    for (std::size_t d = 0; d < result.query.layers.size(); ++d) {
        if (d) out << ',';
        out << '[';
        for (std::size_t i = 0; i < result.query.layers[d].size(); ++i) {
            if (i) out << ',';
            out << '{'; emit_state(out, result.query.layers[d][i]); out << '}';
        }
        out << ']';
    }
    out << "]}";
    return out.str();
}
std::string signature_proof(const cert::SignatureResult& result) {
    std::ostringstream out;
    out << "{\"kind\":\"signature-intersection\",\"horizon\":" << result.horizon
        << ",\"signature\":" << cli::quote(cert::signature_name(result.kind))
        << ",\"prefix_u\":" << cli::quote(result.prefixes[0])
        << ",\"prefix_v\":" << cli::quote(result.prefixes[1]) << ",\"groups\":[";
    for (std::size_t g = 0; g < result.groups.size(); ++g) {
        if (g) out << ',';
        const auto& group = result.groups[g];
        out << "{\"observers\":"; emit_observers(out, group.observers); out << ",\"layers\":[";
        for (std::size_t d = 0; d < group.layers.size(); ++d) {
            if (d) out << ',';
            out << '[';
            for (std::size_t i = 0; i < group.layers[d].size(); ++i) {
                if (i) out << ',';
                out << '{'; emit_state(out, group.layers[d][i].state);
                out << ",\"signature\":"; emit_signature(out, group.layers[d][i].signature); out << '}';
            }
            out << ']';
        }
        out << "],\"accepted\":[";
        for (std::size_t i = 0; i < group.accepted.size(); ++i) {
            if (i) out << ',';
            emit_signature(out, group.accepted[i]);
        }
        out << "]}";
    }
    out << "],\"intersection\":[]}";
    return out.str();
}
void emit_family(std::ostream& out, const cert::Family& family) {
    out << "{\"mask_convention\":\"a_xor_bit_q\",\"observer_count\":" << family.observer_count() << ",\"seeds\":[";
    for (std::size_t i = 0; i < family.seeds().size(); ++i) {
        const auto& seed = family.seeds()[i];
        if (i) out << ',';
        out << "{\"name\":" << cli::quote(seed.name) << ",\"root\":" << seed.root << ",\"ports\":[";
        for (std::size_t q = 0; q < seed.ports.size(); ++q) {
            if (q) out << ',';
            out << '[' << seed.ports[q][0] << ',' << seed.ports[q][1] << ']';
        }
        out << "]}";
    }
    out << "]}";
}
}

int main(int argc, char** argv) {
    try {
        const auto o = parse(argc, argv);
        cert::Family family(o.seeds);
        family.validate_selection(o.observers);
        for (const auto& group : o.projections) family.validate_selection(group);
        std::signal(SIGINT, interrupt);
        std::signal(SIGTERM, interrupt);
        auto limits = o.limits; limits.interrupted = &stopped;
        cert::Budget budget(limits);
        unsigned lower = 1, upper = 0, remaining_lower = 0;
        std::array<std::string, 2> incumbent{};
        std::string proof = "null", status = "unresolved", reason;
        std::string signature_result = "null";
        std::vector<cert::Observer> selected = o.observers;
        std::vector<std::string> attempts;
        cert::UpperResult heuristic;
        bool ready = true;
        if (o.has_upper) {
            auto verified = family.verify(o.upper_u, o.upper_v, budget);
            if (verified.status == "separated") throw std::invalid_argument("imported upper pair fails seed " +
                std::to_string(verified.separator->seed) + " mask " + std::to_string(verified.separator->mask));
            if (verified.status == "verified") { incumbent = {o.upper_u, o.upper_v}; upper = unsigned(o.upper_u.size()); }
            else { ready = false; reason = verified.reason; }
        }
        if (ready && o.has_gap && upper && upper - lower <= o.gap) {
            status = "interval-certified";
            ready = false;
        }
        if (ready && o.heuristic.max_expansions) {
            auto h = o.heuristic; h.interrupted = &stopped;
            heuristic = cert::find_upper(family, h, budget);
            if (heuristic.candidate && (!upper || heuristic.witness[0].size() < upper)) {
                incumbent = heuristic.witness; upper = unsigned(incumbent[0].size());
            }
            if (!budget.check()) { ready = false; reason = budget.reason; }
        }
        if (ready && o.has_gap && upper && upper - lower <= o.gap) {
            status = "interval-certified";
            ready = false;
        }
        if (ready && o.has_gap && !upper) { ready = false; reason = "no-verified-upper"; }
        std::vector<std::vector<cert::Observer>> groups = o.projections;
        if (ready && !o.signature.empty() && groups.empty()) {
            if (!o.observers.empty()) for (auto ob : o.observers) groups.push_back({ob});
            else {
                for (std::size_t i = 0; i < family.seeds().size() && ready; ++i)
                    for (std::uint64_t mask = 0; mask < (std::uint64_t{1} << family.seeds()[i].ports.size()); ++mask) {
                        if (!budget.add_work()) { ready = false; reason = budget.reason; break; }
                        groups.push_back({cert::Observer{i, mask}});
                    }
            }
        }
        while (ready) {
            if (o.has_gap && upper - lower <= o.gap) { status = "interval-certified"; break; }
            const unsigned t = o.has_gap ? upper - o.gap - 1 : o.horizon;
            if (!o.signature.empty()) {
                auto sig = cert::signature_intersection(family, groups, t,
                    o.signature == "count" ? cert::SignatureKind::Count : cert::SignatureKind::FirstDifference,
                    budget, o.prefix_u, o.prefix_v);
                attempts.push_back("{\"kind\":\"signature\",\"horizon\":" + std::to_string(t) +
                    ",\"status\":" + cli::quote(sig.status) + ",\"reason\":" + cli::quote(sig.reason) + "}");
                std::ostringstream diagnostic;
                diagnostic << "{\"status\":" << cli::quote(sig.status) << ",\"intersection\":";
                if (sig.status == "unresolved") diagnostic << "null";
                else {
                    diagnostic << '[';
                    for (std::size_t i = 0; i < sig.intersection.size(); ++i) {
                        if (i) diagnostic << ',';
                        emit_signature(diagnostic, sig.intersection[i]);
                    }
                    diagnostic << ']';
                }
                diagnostic << ",\"completed_groups\":" << sig.groups.size() << '}';
                signature_result = diagnostic.str();
                if (sig.status == "excluded") {
                    proof = signature_proof(sig);
                    if (o.prefix_u.empty() && o.prefix_v.empty()) lower = std::max(lower, t + 1);
                    else remaining_lower = t + 1;
                    status = o.has_gap ? "interval-certified" : "excluded";
                    break;
                }
                if (sig.status == "unresolved") { status = "unresolved"; reason = sig.reason; break; }
                if (!o.has_gap) { status = "signature-survives"; reason = "shared-signatures-are-not-word-witnesses"; break; }
            }
            auto result = cert::refine(family, t, budget, selected);
            selected = result.selected;
            std::ostringstream attempt;
            attempt << "{\"kind\":\"observer-refinement\",\"horizon\":" << t
                << ",\"status\":" << cli::quote(result.status) << ",\"reason\":" << cli::quote(result.reason)
                << ",\"selected\":"; emit_observers(attempt, result.selected);
            attempt << ",\"refinements\":[";
            for (std::size_t i = 0; i < result.refinements.size(); ++i) {
                if (i) attempt << ',';
                const auto& r = result.refinements[i];
                attempt << "{\"u\":" << cli::quote(r.candidate[0]) << ",\"v\":" << cli::quote(r.candidate[1])
                    << ",\"separator\":{\"seed\":" << r.separator.seed << ",\"mask\":" << r.separator.mask << "}}";
            }
            attempt << "]}"; attempts.push_back(attempt.str());
            if (result.status == "excluded") {
                proof = paired_proof(t, result); lower = std::max(lower, t + 1);
                status = o.has_gap ? "interval-certified" : "excluded"; break;
            }
            if (result.status == "unresolved") { status = "unresolved"; reason = result.reason; break; }
            if (!upper || t < upper) { upper = t; incumbent = result.query.witness; }
            status = "witness";
            if (!o.has_gap) break;
        }
        if (lower > upper && upper) throw std::logic_error("contradictory certified endpoints");
        std::ostringstream out;
        out << "{\"schema\":\"family1-certified-v1\",\"family\":"; emit_family(out, family);
        out << ",\"source_sha256\":" << cli::quote(FAMILY1_CERTIFIED_SOURCE_SHA256)
            << ",\"status\":" << cli::quote(status) << ",\"reason\":" << cli::quote(reason)
            << ",\"lower_bound\":" << lower << ",\"upper_bound\":";
        if (upper) out << upper; else out << "null";
        out << ",\"witness\":";
        if (upper) out << "{\"u\":" << cli::quote(incumbent[0]) << ",\"v\":" << cli::quote(incumbent[1]) << '}';
        else out << "null";
        out << ",\"remaining_lower_bound\":";
        if (remaining_lower) out << remaining_lower; else out << "null";
        out << ",\"requested_gap\":";
        if (o.has_gap) out << o.gap; else out << "null";
        out << ",\"exact\":" << (upper && lower == upper ? "true" : "false")
            << ",\"proof\":" << proof << ",\"signature_result\":" << signature_result
            << ",\"configuration\":{\"mode\":" << cli::quote(o.has_gap ? "interval" : "horizon")
            << ",\"horizon\":";
        if (o.has_horizon) out << o.horizon; else out << "null";
        out << ",\"signature\":" << cli::quote(o.signature)
            << ",\"prefix_u\":" << cli::quote(o.prefix_u) << ",\"prefix_v\":" << cli::quote(o.prefix_v)
            << ",\"initial_observers\":";
        emit_observers(out, o.observers);
        out << ",\"projection_policy\":" << cli::quote(!o.projections.empty() ? "explicit" :
            !o.observers.empty() ? "selected-singletons" : "all-singletons") << ",\"declared_projections\":[";
        for (std::size_t i = 0; i < o.projections.size(); ++i) {
            if (i) out << ',';
            emit_observers(out, o.projections[i]);
        }
        out << "],\"imported_upper\":";
        if (o.has_upper) out << "{\"u\":" << cli::quote(o.upper_u) << ",\"v\":" << cli::quote(o.upper_v) << '}';
        else out << "null";
        out << "},\"limits\":{\"max_states\":" << limits.max_states
            << ",\"max_work\":" << limits.max_work << ",\"max_verifier_steps\":" << limits.max_verifier_steps
            << ",\"timeout_ms\":" << limits.timeout_ms << ",\"max_refinements\":" << limits.max_refinements
            << "},\"work\":{\"states\":" << budget.states << ",\"work_units\":" << budget.work
            << ",\"refinements\":" << budget.refinements
            << ",\"verifier_steps\":" << budget.verifier_steps << ",\"seconds\":" << budget.seconds()
            << "},\"heuristic\":{\"enabled\":" << (o.heuristic.max_expansions ? "true" : "false")
            << ",\"status\":" << cli::quote(heuristic.status) << ",\"reason\":" << cli::quote(heuristic.reason)
            << ",\"expansions\":" << heuristic.expanded_nodes
            << ",\"coordinates_built\":" << heuristic.coordinates
            << ",\"k\":" << o.heuristic.window_k << ",\"beam\":" << o.heuristic.beam_width
            << ",\"max_length\":" << o.heuristic.max_length << ",\"max_expansions\":" << o.heuristic.max_expansions
            << "},\"attempts\":[";
        for (std::size_t i = 0; i < attempts.size(); ++i) { if (i) out << ','; out << attempts[i]; }
        out << "]}\n";
        cli::publish(o.out, out.str());
        std::cout << status << " L=" << lower << " U=" << (upper ? std::to_string(upper) : "unavailable")
            << " masks=" << family.observer_count() << " reason=" << reason << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Family1Certified: " << error.what() << '\n';
        return 1;
    }
}

#include "Family1CliArtifacts.h"
#include "Family1NearPair.h"
#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <string>
#include <vector>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#endif
#ifndef FAMILY1_NEAR_SOURCE_SHA256
#define FAMILY1_NEAR_SOURCE_SHA256 ""
#endif

namespace fs = std::filesystem;
namespace cli = family1_cli;
namespace near_pair = family1::near_pair;

namespace {
const char* boolean(bool value) { return value ? "true" : "false"; }

struct Options {
    unsigned int m = 0;
    near_pair::Options finder;
    std::vector<std::string> keys;
    std::uint64_t supplied_graph_arguments = 0;
    fs::path out;
};

std::uint64_t number(const std::string& text) {
    if (text.empty() || text.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("expected a nonnegative integer: " + text);
    return std::stoull(text);
}

unsigned int bounded(const std::string& text, unsigned int maximum, const std::string& option) {
    const auto value = number(text);
    if (value > maximum) throw std::invalid_argument("option out of range: " + option);
    return static_cast<unsigned int>(value);
}

void help() {
    std::cout <<
        "Family1NearPair --m M --graph KEY [--graph KEY ...] --out DIR\n"
        "Deterministic near-shortest word-pair search for each supplied graph.\n"
        "Every original static-mask DFA coordinate is retained and replayed.\n"
        "No random choices or clock limits are used.\n"
        "  --k 1..8              Joint lookahead (default 4): all 4^k leaves\n"
        "  --beam 1..4096        Distinct endpoint beam (default 16)\n"
        "  --exact-depth 0..30   Complete word layers (default 24; 0 disables)\n"
        "  --exact-words N       Full-word layer budget (default 16777216)\n"
        "  --exact-memory-mib N  Exact array-payload budget (default 256)\n"
        "  --prefix-depth 1..30  Prefix catalogue word depth (default 20)\n"
        "  --prefix-words N      Complete words per prefix layer (default 1048576)\n"
        "  --catalogue N         Compatible seed catalogue size (default 16384)\n"
        "  --starts N            Starts per seed ranking (default 512)\n"
        "  --seed-mode scored|compact  Catalogue rule (default scored)\n"
        "  --seed-ranking full|common-max|common-sum|portfolio (default portfolio)\n"
        "  --fallback-compact on|off  Retry misses with a compact catalogue (default on)\n"
        "  --max-length 1..4096  Maximum word-pair length (default 80)\n"
        "  --expansions N        Fixed nodes per joint attempt (default 2000000)\n"
        "The joint alphabet is 00,01,10,11. Each evaluated window is complete.\n"
        "Exact-word-layer witnesses have producing k=N/A; configured joint k\n"
        "is recorded separately. Other positives are verified upper bounds.\n"
        "Bounded catalogues and beams can miss a pair or its shortest length.\n"
        "Use a fresh empty output directory. All improving pairs are flushed\n"
        "immediately to witnesses.jsonl with both words, D traces and parameters.\n";
}

Options parse(int argc, char** argv) {
    Options result;
    for (int i=1;i<argc;++i) {
        const std::string option=argv[i];
        if (option=="--help" || option=="-h") { help(); std::exit(0); }
        if (++i==argc) throw std::invalid_argument("missing value: "+option);
        const std::string value=argv[i];
        if (option=="--graph") { result.keys.push_back(value); ++result.supplied_graph_arguments; }
        else if (option=="--out") result.out=value;
        else if (option=="--m") result.m=bounded(value,20,option);
        else if (option=="--k") result.finder.joint.window_k=bounded(value,8,option);
        else if (option=="--beam") result.finder.joint.beam_width=bounded(value,4096,option);
        else if (option=="--exact-depth") result.finder.exact_depth=bounded(value,30,option);
        else if (option=="--exact-words") result.finder.exact_max_words=number(value);
        else if (option=="--exact-memory-mib") {
            const auto mib=number(value);
            if (mib>std::numeric_limits<std::uint64_t>::max()/(std::uint64_t{1}<<20))
                throw std::invalid_argument("exact memory budget overflows bytes");
            result.finder.exact_memory_bytes=mib<<20;
        }
        else if (option=="--prefix-depth") result.finder.prefix_depth=bounded(value,30,option);
        else if (option=="--prefix-words") result.finder.prefix_words=number(value);
        else if (option=="--catalogue") result.finder.catalogue_size=number(value);
        else if (option=="--starts") result.finder.selected_pairs=number(value);
        else if (option=="--max-length") result.finder.joint.max_length=bounded(value,4096,option);
        else if (option=="--expansions") result.finder.joint.max_expansions=number(value);
        else if (option=="--seed-mode") {
            if (value!="scored" && value!="compact") throw std::invalid_argument("seed mode must be scored or compact");
            result.finder.compact=value=="compact";
        }
        else if (option=="--fallback-compact") {
            if (value!="on" && value!="off") throw std::invalid_argument("fallback compact must be on or off");
            result.finder.retry_compact_on_miss=value=="on";
        }
        else if (option=="--seed-ranking") {
            if (value=="full") result.finder.seed_ranking=near_pair::SeedRanking::FullDisagreement;
            else if (value=="common-max") result.finder.seed_ranking=near_pair::SeedRanking::CommonMaximum;
            else if (value=="common-sum") result.finder.seed_ranking=near_pair::SeedRanking::CommonSum;
            else if (value=="portfolio") result.finder.seed_ranking=near_pair::SeedRanking::Portfolio;
            else throw std::invalid_argument("seed ranking must be full, common-max, common-sum or portfolio");
        }
        else throw std::invalid_argument("unknown option: "+option);
    }
    const auto& f=result.finder;
    if (!result.m || result.keys.empty() || result.out.empty() ||
        !f.joint.window_k || !f.joint.beam_width || !f.joint.max_length || !f.joint.max_expansions ||
        !f.exact_max_words || !f.exact_memory_bytes || !f.prefix_depth || !f.prefix_words ||
        !f.catalogue_size || !f.selected_pairs || f.selected_pairs>f.catalogue_size)
        throw std::invalid_argument("require m1..20, supplied graphs, output and valid positive work budgets");
    for (auto& key:result.keys) {
        auto graph=family1::LargeGraph::from_key(key);
        if (graph.size()!=result.m || !graph.accessible())
            throw std::invalid_argument("supplied graph must be accessible and have exactly m states");
        key=graph.canonical().key();
    }
    std::sort(result.keys.begin(),result.keys.end());
    result.keys.erase(std::unique(result.keys.begin(),result.keys.end()),result.keys.end());
    result.out=fs::absolute(result.out);
    return result;
}

std::string executable_hash(const char* argument) {
    fs::path path(argument);
#ifdef _WIN32
    std::vector<wchar_t> buffer(32768);
    const auto count=GetModuleFileNameW(nullptr,buffer.data(),static_cast<DWORD>(buffer.size()));
    if (!count || count==buffer.size()) throw std::runtime_error("cannot locate executable");
    path=std::wstring(buffer.data(),count);
#else
    std::error_code error;
    auto resolved=fs::read_symlink("/proc/self/exe",error);
    if (!error) path=resolved;
#endif
    return cli::sha256(cli::read(path));
}

std::string configuration(const Options& options) {
    const auto& f=options.finder;
    std::ostringstream out;
    out << "\"configured_joint_k\":"<<f.joint.window_k
        <<",\"alphabet\":[\"00\",\"01\",\"10\",\"11\"],\"deterministic\":true,\"randomness\":false"
        <<",\"score\":\"permutation\",\"greedy_advance\":\"whole joint window block\""
        <<",\"beam_width\":"<<f.joint.beam_width<<",\"diagonal_width\":"<<f.joint.diagonal_width
        <<",\"unequal_width\":"<<f.joint.unequal_width<<",\"max_length\":"<<f.joint.max_length
        <<",\"expansion_cap\":"<<f.joint.max_expansions
        <<",\"expansion_cap_scope\":\"per selected-seed joint attempt\",\"time_caps\":false"
        <<",\"exact_depth\":"<<f.exact_depth<<",\"exact_max_words\":"<<f.exact_max_words
        <<",\"exact_memory_bytes\":"<<f.exact_memory_bytes
        <<",\"prefix_depth\":"<<f.prefix_depth<<",\"prefix_words\":"<<f.prefix_words
        <<",\"catalogue_size\":"<<f.catalogue_size<<",\"selected_pairs\":"<<f.selected_pairs
        <<",\"seed_mode\":"<<cli::quote(f.compact?"compact":"scored")
        <<",\"seed_ranking\":"<<cli::quote(f.seed_ranking==near_pair::SeedRanking::FullDisagreement?"full":
            f.seed_ranking==near_pair::SeedRanking::CommonMaximum?"common-max":
            f.seed_ranking==near_pair::SeedRanking::CommonSum?"common-sum":"portfolio")
        <<",\"retry_compact_on_miss\":"<<boolean(f.retry_compact_on_miss)
        <<",\"fallback_catalogue_size\":"<<std::max(f.fallback_catalogue_size,f.selected_pairs);
    return out.str();
}

struct PairView {
    bool found=false,exact=false;
    unsigned int lower=1,upper=0;
    std::string first,second,producer,seed_first,seed_second;
    std::vector<std::uint64_t> trace;
    std::uint64_t masks=0;
    std::string seed_mode;
};
PairView pair_view(const near_pair::Result& result) {
    return {result.found,result.exact,result.lower_bound,result.upper_bound,
            result.first,result.second,result.producer,result.winning_seed_first,result.winning_seed_second,
            result.metric_trace,result.verified_masks,result.winning_seed_mode};
}
PairView pair_view(const near_pair::Improvement& result) {
    return {true,result.exact,result.lower_bound,result.upper_bound,
            result.first,result.second,result.producer,result.seed_first,result.seed_second,
            result.metric_trace,result.verified_masks,result.seed_mode};
}

void verify(const family1::LargeGraph& graph,const PairView& pair) {
    if (!pair.found) {
        if (pair.upper || pair.exact || !pair.first.empty() || !pair.second.empty() || !pair.trace.empty())
            throw std::logic_error("unresolved result carries a pair certificate");
        return;
    }
    if (pair.first.empty() || pair.first==pair.second || pair.first.size()!=pair.second.size() ||
        pair.first.size()!=pair.upper || pair.lower>pair.upper ||
        pair.first.find_first_not_of("01")!=std::string::npos || pair.second.find_first_not_of("01")!=std::string::npos ||
        pair.exact!=(pair.lower==pair.upper) || pair.masks!=(std::uint64_t{1}<<graph.size()))
        throw std::logic_error("invalid near-pair certificate fields");
    std::vector<std::uint64_t> trace(pair.upper+1);
    for (unsigned int mask=0;mask<(1U<<graph.size());++mask) {
        unsigned int left=0,right=0;
        for (unsigned int i=0;i<pair.upper;++i) {
            left=graph.ports[left][static_cast<unsigned int>(pair.first[i]-'0')^((mask>>left)&1U)];
            right=graph.ports[right][static_cast<unsigned int>(pair.second[i]-'0')^((mask>>right)&1U)];
            trace[i+1]+=left!=right;
        }
        if (left!=right) throw std::logic_error("near-pair scalar replay failed");
    }
    if (trace!=pair.trace) throw std::logic_error("near-pair prefix trace differs from scalar replay");
    if (pair.producer!="exact-word-layers" && pair.producer!="scored-seed-joint")
        throw std::logic_error("unknown witness producer");
    if (pair.producer=="scored-seed-joint" &&
        (pair.seed_first.empty() || pair.seed_first.size()!=pair.seed_second.size() ||
         !pair.first.starts_with(pair.seed_first) || !pair.second.starts_with(pair.seed_second)))
        throw std::logic_error("winning seed is not a prefix of the verified pair");
}

struct WitnessContext {
    unsigned int effective_max_length=0,first_greedy_depth=0;
};

std::string record(const family1::LargeGraph& graph,const Options& options,const PairView& pair,
                   const WitnessContext& context,const std::string& run_hash,
                   const near_pair::Result* final=nullptr) {
    const bool oracle=pair.producer=="exact-word-layers";
    const auto count=std::uint64_t{1}<<graph.size();
    std::ostringstream out;
    out<<"{\"program\":\"Family1NearPair/1\",\"event\":"<<cli::quote(final?"final":"improvement")
       <<",\"m\":"<<graph.size()<<",\"key\":"<<cli::quote(graph.key())<<",\"canonical_table\":[";
    for (unsigned int state=0;state<graph.size();++state) {
        if(state)out<<',';out<<'['<<graph.ports[state][0]<<','<<graph.ports[state][1]<<']';
    }
    out<<"],"<<configuration(options)
       <<",\"run_sha256\":"<<cli::quote(run_hash)
       <<",\"k\":"<<(oracle?"null":std::to_string(options.finder.joint.window_k))
       <<",\"window_kind\":"<<cli::quote(oracle?"exact-oracle":"joint-pair")
       <<",\"producer\":"<<(pair.found?cli::quote(pair.producer):"null")
       <<",\"status\":"<<cli::quote(pair.exact?"exact":pair.found?"verified-upper":"unresolved")
       <<",\"lower_bound\":"<<pair.lower<<",\"upper_bound\":"<<(pair.found?std::to_string(pair.upper):"null")
       <<",\"exact\":"<<boolean(pair.exact)<<",\"minimality_certified\":"<<boolean(pair.exact)
       <<",\"near_shortest_error_bound_certified\":false,\"global_maximum_certified\":false"
       <<",\"dfa_count\":"<<count<<",\"static_masks_verified\":"<<pair.masks
       <<",\"coordinate_weight_policy\":\"every original static mask; coincident-port duplicates retain multiplicity\""
       <<",\"metric_definition\":\"D counts original static-mask DFAs with unequal endpoints\""
       <<",\"witness\":";
    if(pair.found)out<<'['<<cli::quote(pair.first)<<','<<cli::quote(pair.second)<<']';else out<<"null";
    out<<",\"witness_metric_trace\":";
    if(pair.found){
        out<<'[';for(std::size_t i=0;i<pair.trace.size();++i){if(i)out<<',';out<<pair.trace[i];}
        out<<"],\"synchronized_count_trace\":[";
        for(std::size_t i=0;i<pair.trace.size();++i){if(i)out<<',';out<<count-pair.trace[i];}
        unsigned int difference=0;
        while(difference<pair.upper && pair.first[difference]==pair.second[difference])++difference;
        out<<"],\"first_difference_position\":"<<difference+1
           <<",\"winning_attempt\":{\"kind\":"<<cli::quote(pair.producer)
           <<",\"initial_first\":"<<cli::quote(pair.seed_first)<<",\"initial_second\":"<<cli::quote(pair.seed_second)
           <<",\"initial_length\":"<<pair.seed_first.size()<<",\"first_difference_depth\":"<<difference+1
           <<",\"seed_mode\":"<<cli::quote(pair.seed_mode)
           <<",\"first_greedy_depth\":"<<context.first_greedy_depth
           <<",\"effective_max_length\":"<<context.effective_max_length<<'}';
    }else out<<"null,\"synchronized_count_trace\":null,\"first_difference_position\":null,\"winning_attempt\":null";
    if(oracle)out<<",\"oracle_word_alphabet\":[\"0\",\"1\"]";
    if(final){
        out<<",\"exact_status\":"<<cli::quote(final->exact_status)<<",\"exact_reason\":"<<cli::quote(final->exact_reason)
           <<",\"exact_evaluated_words\":"<<final->exact_evaluated_words<<",\"exact_peak_bytes\":"<<final->exact_peak_bytes
           <<",\"seed_catalogue_rule\":"<<cli::quote(final->seed_catalogue_rule)
           <<",\"prefix_words_evaluated\":"<<final->seed_words<<",\"prefix_completed_depth\":"<<final->prefix_completed_depth
           <<",\"candidates_scored\":"<<final->candidates_scored<<",\"seed_candidates_selected\":"<<final->seed_candidates_selected
           <<",\"common_distance_pair_states\":"<<final->common_pair_states
           <<",\"attempts\":"<<final->attempts<<",\"skipped_seeds\":"<<final->skipped_seeds
           <<",\"expanded_nodes\":"<<final->nodes<<",\"complete_windows\":"<<final->complete_windows
           <<",\"partial_windows\":"<<final->partial_windows<<",\"windows_refused\":"<<final->windows_refused
           <<",\"improvements\":"<<final->improvements<<",\"expansion_limit_reached\":"<<boolean(final->expansion_capped)
           <<",\"length_limit_reached\":"<<boolean(final->length_capped)<<",\"beam_truncated\":"<<boolean(final->beam_truncated)
           <<",\"prefix_pair_capped\":"<<boolean(final->seed_pair_capped)<<",\"prefix_word_capped\":"<<boolean(final->seed_word_capped)
           <<",\"interrupted\":"<<boolean(final->interrupted);
        out<<",\"retried_compact\":"<<boolean(final->retried_compact);
    }
    out<<'}';return out.str();
}
} // namespace

int main(int argc,char**argv) {
    try {
        const auto options=parse(argc,argv);
        if(fs::exists(options.out) && !fs::is_empty(options.out))
            throw std::runtime_error("use a fresh empty output directory");
        fs::create_directories(options.out);
        std::ostringstream run;
        run<<"{\"program\":\"Family1NearPair/1\",\"m\":"<<options.m<<','<<configuration(options)
           <<",\"executable_sha256\":"<<cli::quote(executable_hash(argv[0]))
           <<",\"source_sha256\":";
        const std::string source_hash=FAMILY1_NEAR_SOURCE_SHA256;
        run<<(source_hash.empty()?"null":cli::quote(source_hash))
           <<",\"source_fingerprint_method\":"<<cli::quote(source_hash.empty()?"not supplied by this build":"compile-time build fingerprint")
           <<",\"supplied_graph_arguments\":"<<options.supplied_graph_arguments
           <<",\"unique_graphs\":"<<options.keys.size()<<",\"graphs\":[";
        for(std::size_t i=0;i<options.keys.size();++i){if(i)run<<',';run<<cli::quote(options.keys[i]);}
        run<<"]}";
        const auto run_text=run.str()+"\n",run_hash=cli::sha256(run_text);
        cli::publish(options.out/"run.json",run_text);
        std::ofstream witnesses(options.out/"witnesses.jsonl",std::ios::binary);
        if(!witnesses)throw std::runtime_error("cannot open witness journal");
        std::string records;
        std::uint64_t positive=0,exact=0,nodes=0,windows=0,partial=0,journal_pairs=0,attempts=0;
        std::map<unsigned int,std::uint64_t> histogram;
        for(const auto&key:options.keys){
            auto graph=family1::LargeGraph::from_key(key);
            WitnessContext winning_context;
            unsigned int previous_upper=0;
            auto result=near_pair::find_pair(graph,options.finder,[&](const near_pair::Improvement& improvement){
                auto pair=pair_view(improvement);verify(graph,pair);
                if(previous_upper && pair.upper>=previous_upper)throw std::logic_error("improvement did not improve upper");
                winning_context.effective_max_length=previous_upper?
                    std::min(options.finder.joint.max_length,previous_upper-1):options.finder.joint.max_length;
                winning_context.first_greedy_depth=0;
                if(pair.producer=="scored-seed-joint" && pair.trace[pair.seed_first.size()]!=0)
                    winning_context.first_greedy_depth=static_cast<unsigned int>(pair.seed_first.size())+
                        std::min(options.finder.joint.window_k,
                                 winning_context.effective_max_length-static_cast<unsigned int>(pair.seed_first.size()));
                witnesses<<record(graph,options,pair,winning_context,run_hash)<<'\n';witnesses.flush();
                if(!witnesses)throw std::runtime_error("cannot persist verified improvement");
                previous_upper=pair.upper;++journal_pairs;
            });
            auto pair=pair_view(result);verify(graph,pair);
            if(result.partial_windows)throw std::logic_error("near finder evaluated a partial joint window");
            if(pair.found && pair.upper!=previous_upper)throw std::logic_error("final pair differs from last accepted upper");
            records+=record(graph,options,pair,winning_context,run_hash,&result)+"\n";
            cli::write(options.out/"records.partial.jsonl",records);
            positive+=pair.found;exact+=pair.exact;nodes+=result.nodes;windows+=result.complete_windows;
            partial+=result.partial_windows;attempts+=result.attempts;
            if(pair.found)++histogram[pair.upper];
        }
        witnesses.close();if(!witnesses)throw std::runtime_error("cannot close witness journal");
        cli::publish(options.out/"records.jsonl",records);
        std::ostringstream summary;
        summary<<"{\"program\":\"Family1NearPair/1\",\"m\":"<<options.m<<','<<configuration(options)
               <<",\"graphs\":"<<options.keys.size()<<",\"all_supplied_graphs_tested\":true"
               <<",\"verified_pairs\":"<<positive<<",\"no_pair\":"<<options.keys.size()-positive
               <<",\"exact_graphs\":"<<exact<<",\"joint_attempts\":"<<attempts
               <<",\"expanded_nodes\":"<<nodes<<",\"complete_windows\":"<<windows<<",\"partial_windows\":"<<partial
               <<",\"journal_pairs\":"<<journal_pairs<<",\"upper_histogram\":{";
        bool first=true;
        for(const auto&[length,count]:histogram){if(!first)summary<<',';first=false;summary<<cli::quote(std::to_string(length))<<':'<<count;}
        summary<<"},\"global_maximum_certified\":false,\"near_shortest_error_bound_certified\":false"
               <<",\"run_sha256\":"<<cli::quote(run_hash)<<",\"records_sha256\":"<<cli::quote(cli::sha256(records))
               <<",\"witnesses_sha256\":"<<cli::quote(cli::sha256(cli::read(options.out/"witnesses.jsonl")))<<'}';
        cli::publish(options.out/"summary.json",summary.str()+"\n");
        fs::remove(options.out/"records.partial.jsonl");
        std::cout<<summary.str()<<'\n';return 0;
    }catch(const std::exception&error){
        std::cerr<<"Family1NearPair: "<<error.what()<<'\n';return 2;
    }
}

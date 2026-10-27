// Standalone graph-only benchmark. No reference H or saved witness is read.
#include "Family1CliArtifacts.h"
#include "Family1JointPair.h"
#include "Family1ScoredSeeds.h"
#include "Family1TailScoredSeeds.h"
#include "HardPairJointAdaptive.h"
#include "HardPairJointFinder.h"
#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

#ifndef FAMILY1_ADAPTIVE_SOURCE_SHA256
#define FAMILY1_ADAPTIVE_SOURCE_SHA256 "unconfigured"
#endif

using family1_cli::quote;
using hardpair::adaptive::DecisionTrace;

struct Configuration {
    std::string name, policy, advance;
    unsigned min_k=0,max_k=0,beam=0;
    std::uint64_t threshold=0;
    bool priority=false;
};

template<class Range> void numbers(std::ostream& out,const Range& values) {
    out << '[';bool comma=false;
    for(auto n:values){if(comma)out<<',';comma=true;out<<n;}out<<']';
}

void pair_json(std::ostream& out,const std::string& a,const std::string& b) {
    out << '[' << quote(a) << ',' << quote(b) << ']';
}

void decisions_json(std::ostream& out,const std::vector<DecisionTrace>& trace) {
    out << '[';
    for(std::size_t i=0;i<trace.size();++i){
        if(i)out<<',';const auto& d=trace[i];
        out<<"{\"depth\":"<<d.depth<<",\"parent_first\":"<<quote(d.parent_first)
           <<",\"parent_second\":"<<quote(d.parent_second)<<",\"parent_D\":"<<d.parent_D
           <<",\"parent_priority\":"<<d.parent_priority<<",\"selected_k\":"<<d.selected_k
           <<",\"reason\":"<<quote(d.reason)<<",\"selected\":"<<(d.selected?"true":"false")
           <<",\"minimum_refused\":"<<(d.minimum_refused?"true":"false")<<",\"windows\":[";
        for(std::size_t j=0;j<d.windows.size();++j){
            if(j)out<<',';const auto& w=d.windows[j];
            out<<"{\"k\":"<<w.k<<",\"n\":"<<w.n<<",\"sumD\":"<<w.sumD
               <<",\"sumD2\":"<<w.sumD2<<",\"minD\":"<<w.minD<<",\"maxD\":"<<w.maxD
               <<",\"action_n\":";numbers(out,w.action_n);out<<",\"action_sumD\":";numbers(out,w.action_sumD);
            out<<",\"action_minD\":";numbers(out,w.action_minD);
            out<<",\"D_histogram\":[";
            for(std::size_t h=0;h<w.D_histogram.size();++h){
                if(h)out<<',';out<<'['<<w.D_histogram[h].first<<','<<w.D_histogram[h].second<<']';
            }
            out<<']';
            out<<",\"total_numerator\":"<<quote(w.total_numerator.decimal())
               <<",\"action_numerator\":"<<quote(w.action_numerator.decimal())<<",\"denominator\":"<<quote(w.denominator.decimal())
               <<",\"criterion_eligible\":"<<(w.criterion_eligible?"true":"false")
               <<",\"criterion_met\":"<<(w.criterion_met?"true":"false")
               <<",\"progress_met\":"<<(w.progress_met?"true":"false")
               <<",\"adequate\":"<<(w.adequate?"true":"false")
               <<",\"best_leaf_D\":"<<w.best_leaf_D<<",\"best_leaf_priority\":"<<w.best_leaf_priority
               <<",\"positive_leaves\":"<<w.positive_leaves<<'}';
        }
        out<<"]}";
    }
    out<<']';
}

std::vector<std::uint64_t> scalar_trace(const family1::LargeGraph& graph,const std::string& a,const std::string& b) {
    if(a.empty()||a==b||a.size()!=b.size())throw std::logic_error("invalid witness pair");
    std::vector<std::uint64_t> trace(a.size()+1);
    for(unsigned mask=0;mask<(1U<<graph.size());++mask){
        unsigned q=0,r=0;
        for(std::size_t i=0;i<a.size();++i){
            q=graph.ports[q][(a[i]-'0')^((mask>>q)&1U)];
            r=graph.ports[r][(b[i]-'0')^((mask>>r)&1U)];
            trace[i+1]+=q!=r;
        }
        if(q!=r)throw std::logic_error("scalar witness replay failed");
    }
    return trace;
}

struct Outcome {
    bool found=false;
    unsigned length=0,winning_k=0,winning_max_length=0;
    std::string first,second,seed_first,seed_second,seed_rank;
    std::vector<unsigned> k_sequence;
    std::vector<DecisionTrace> decisions;
    std::uint64_t nodes=0,windows=0,layers=0,attempts=0,skipped=0,capped=0,refused=0,equivalent=0;
    std::array<std::uint64_t,9> completed{},tested{},selected{};
};

void table_json(std::ostream& out,const family1::LargeGraph& graph) {
    out<<'[';for(unsigned i=0;i<graph.size();++i){if(i)out<<',';out<<'['<<graph.ports[i][0]<<','<<graph.ports[i][1]<<']';}out<<']';
}

int main(int argc,char** argv) {
    try {
        if(argc!=7)throw std::invalid_argument("usage: Family1AdaptiveWindowBenchmark KEYS CONFIGS OUT STARTS MAXLEN EXPANSIONS");
        const auto starts=std::stoull(argv[4]),expansions=std::stoull(argv[6]);
        const unsigned max_length=std::stoul(argv[5]);
        if(!starts||starts>16384||!expansions||!max_length||max_length>4096)
            throw std::invalid_argument("invalid benchmark budgets");
        std::ifstream config_input(argv[2]);std::vector<Configuration> configs;Configuration c;
        while(config_input>>c.name>>c.policy>>c.min_k>>c.max_k>>c.beam>>c.threshold>>c.priority>>c.advance){
            if(c.policy!="fixed-block"&&c.policy!="fixed-roll"&&c.policy!="total-roll"&&c.policy!="action-roll"&&c.policy!="progress-roll")
                throw std::invalid_argument("unknown policy");
            if(c.advance!=(c.policy=="fixed-block"?"block":"first"))throw std::invalid_argument("advance/policy mismatch");
            if(!c.min_k||c.min_k>c.max_k||c.max_k>8||!c.beam||c.beam>4096||c.threshold>1000000)
                throw std::invalid_argument("invalid configuration");
            if((c.policy=="fixed-block"||c.policy=="fixed-roll")&&c.min_k!=c.max_k)
                throw std::invalid_argument("fixed policy needs one k");
            configs.push_back(c);
        }
        if(configs.empty()||!config_input.eof())throw std::invalid_argument("invalid configuration file");
        const std::filesystem::path folder(argv[3]);
        if(std::filesystem::exists(folder))throw std::invalid_argument("output directory must be fresh");
        std::filesystem::create_directories(folder);
        std::ofstream output(folder/"records.jsonl"),improvements(folder/"improvements.jsonl"),decisions(folder/"decisions.jsonl");
        std::ifstream input(argv[1]);std::string key;unsigned graphs=0;
        while(input>>key){
            auto graph=family1::LargeGraph::from_key(key);graph.validate();
            if(!graph.accessible())throw std::invalid_argument("graph must be accessible");
            auto product=std::make_shared<const family1::ExactPackedProduct>(graph);
            auto priority=family1::permutation_priority_selection(product,graph);
            auto full=family1::scored_joint_seeds(graph,product,20,1048576,16384,starts);
            auto tail=family1::tail_scored_joint_seeds(graph,product,20,1048576,16384,starts,0,&full.catalogue);
            struct Seed {std::string first,second,rank;};std::vector<Seed> seeds;
            for(const auto& s:full.selected)seeds.push_back({s.first,s.second,"full-D"});
            for(const auto& s:tail.selected)seeds.push_back({s.first,s.second,"common-max"});
            std::string catalogue_bytes;
            for(const auto& p:full.catalogue.pairs)catalogue_bytes+=p.first+" "+p.second+"\n";
            for(const auto& config:configs){
                Outcome best;
                for(const auto& seed:seeds){
                    const auto limit=best.found?std::min(max_length,best.length-1):max_length;
                    if(seed.first.size()>limit){++best.skipped;continue;}
                    family1::JointPairState initial(product,seed.first,seed.second,priority);
                    bool found=false;unsigned length=0,winning_k=0;
                    std::string first,second;std::vector<unsigned> k_sequence;
                    std::vector<DecisionTrace> winning_decisions;
                    if(config.policy=="fixed-block"){
                        hardpair::joint::Options options;
                        options.window_k=config.min_k;options.beam_width=config.beam;
                        options.diagonal_width=options.unequal_width=0;
                        options.max_length=limit;options.max_expansions=expansions;
                        options.prioritize_permutation=config.priority;options.max_trace_records=4096;
                        auto answer=hardpair::joint::find_pair(std::move(initial),options);
                        if(answer.partial_windows)throw std::logic_error("partial baseline window");
                        found=answer.found;length=answer.length;first=answer.first;second=answer.second;
                        best.nodes+=answer.expanded_nodes;best.windows+=answer.complete_windows;
                        best.refused+=answer.windows_refused;best.capped+=answer.expansion_limit_reached;
                        for(const auto& w:answer.windows){
                            if(!w.complete)throw std::logic_error("incomplete baseline window metadata");
                            ++best.tested.at(w.span);
                            for(unsigned k=1;k<=w.span;++k){++best.completed[k];++best.layers;}
                        }
                        for(const auto& round:answer.round_trace){
                            best.selected.at(round.span)+=round.parents_expanded;
                            if(found&&round.parents_expanded)k_sequence.push_back(round.span);
                        }
                        if(!k_sequence.empty())winning_k=k_sequence.back();
                    }else{
                        hardpair::adaptive::Options options;
                        options.min_k=config.min_k;options.max_k=config.max_k;options.beam=config.beam;
                        options.diagonal_width=0;options.max_length=limit;options.max_expansions=expansions;
                        options.threshold_ppm=config.threshold;options.priority=config.priority;
                        options.require_improvement=config.policy=="progress-roll";
                        options.avoid_cycles=false;options.max_trace_records=0;
                        options.advance=hardpair::adaptive::Advance::First;
                        options.policy=config.policy=="fixed-roll"?hardpair::adaptive::Policy::Fixed:
                            (config.policy=="total-roll"||config.policy=="progress-roll")?hardpair::adaptive::Policy::TotalVariance:
                                                       hardpair::adaptive::Policy::ActionVariance;
                        auto answer=hardpair::adaptive::find_pair(std::move(initial),options);
                        found=answer.found;length=answer.length;first=answer.first;second=answer.second;
                        winning_k=answer.winning_k;winning_decisions=std::move(answer.winning_decisions);
                        for(const auto& d:winning_decisions)if(d.selected_k)k_sequence.push_back(d.selected_k);
                        best.nodes+=answer.expanded_nodes;best.windows+=answer.criterion_windows;
                        best.layers+=answer.complete_layers;best.refused+=answer.budget_refused_layers;
                        best.capped+=answer.budget_refused;best.equivalent+=answer.equivalent_candidates;
                        for(unsigned k=0;k<9;++k){
                            best.completed[k]+=answer.completed_k_histogram[k];
                            best.tested[k]+=answer.tested_k_histogram[k];
                            best.selected[k]+=answer.selected_k_histogram[k];
                        }
                    }
                    ++best.attempts;
                    if(found&&(!best.found||length<best.length)){
                        scalar_trace(graph,first,second);
                        best.found=true;best.length=length;best.first=std::move(first);best.second=std::move(second);
                        best.seed_first=seed.first;best.seed_second=seed.second;best.seed_rank=seed.rank;
                        best.winning_max_length=limit;
                        best.winning_k=winning_k;best.k_sequence=std::move(k_sequence);best.decisions=std::move(winning_decisions);
                        improvements<<"{\"config\":"<<quote(config.name)<<",\"m\":"<<graph.size()<<",\"key\":"<<quote(key)
                                    <<",\"upper_bound\":"<<best.length<<",\"witness\":";
                        pair_json(improvements,best.first,best.second);
                        improvements<<",\"producing_k_sequence\":";numbers(improvements,best.k_sequence);
                        improvements<<",\"seed_ranking\":"<<quote(best.seed_rank)<<",\"witness_metric_trace\":";
                        numbers(improvements,scalar_trace(graph,best.first,best.second));improvements<<"}\n";improvements.flush();
                    }
                }
                const auto trace=best.found?scalar_trace(graph,best.first,best.second):std::vector<std::uint64_t>{};
                std::vector<std::uint64_t> sync;for(auto d:trace)sync.push_back((1ULL<<graph.size())-d);
                output<<"{\"program\":\"Family1AdaptiveWindowBenchmark/1\",\"config\":"<<quote(config.name)
                      <<",\"m\":"<<graph.size()<<",\"key\":"<<quote(key)<<",\"canonical_table\":";table_json(output,graph);
                output<<",\"source_sha256\":"<<quote(FAMILY1_ADAPTIVE_SOURCE_SHA256)
                      <<",\"configured_k_min\":"<<config.min_k<<",\"configured_k_max\":"<<config.max_k
                      <<",\"threshold_ppm\":"<<config.threshold<<",\"beam_width\":"<<config.beam
                      <<",\"policy\":"<<quote(config.policy)<<",\"advance\":"<<quote(config.advance)
                      <<",\"priority\":"<<(config.priority?"true":"false")
                      <<",\"exact_depth\":0,\"lower_bound\":1,\"minimality_certified\":"<<(best.found&&best.length==1?"true":"false")
                      <<",\"randomness\":false,\"time_caps\":false,\"alphabet\":[\"00\",\"01\",\"10\",\"11\"]"
                      <<",\"max_length\":"<<max_length<<",\"expansion_cap\":"<<expansions
                      <<",\"upper_bound\":"<<(best.found?std::to_string(best.length):"null")<<",\"witness\":";
                if(best.found)pair_json(output,best.first,best.second);else output<<"null";
                output<<",\"witness_metric_trace\":";numbers(output,trace);output<<",\"synchronized_count_trace\":";numbers(output,sync);
                output<<",\"producing_k_sequence\":";numbers(output,best.k_sequence);
                output<<",\"winning_k\":"<<(best.winning_k?std::to_string(best.winning_k):"null")
                      <<",\"producer\":"<<quote(!best.found?"none":best.k_sequence.empty()?"bounded-seed-collision":"joint-window")
                      <<",\"winning_seed\":";pair_json(output,best.seed_first,best.seed_second);
                output<<",\"winning_seed_ranking\":"<<quote(best.seed_rank)
                      <<",\"winning_attempt_max_length\":"<<best.winning_max_length
                      <<",\"seed_ranking\":\"full-D then common-max\",\"seed_words\":"<<full.catalogue.words_evaluated
                      <<",\"catalogue_sha256\":"<<quote(family1_cli::sha256(catalogue_bytes))
                      <<",\"candidates_scored\":"<<(full.candidates_scored+tail.candidates_scored)
                      <<",\"common_distance_pair_states\":"<<tail.common_pair_states
                      <<",\"seed_work_scope\":\"shared once per graph across configurations; counters repeat the per-policy preprocessing cost\""
                      <<",\"selected_starts\":"<<seeds.size()<<",\"starts_per_ranking\":"<<starts
                      <<",\"attempts\":"<<best.attempts<<",\"skipped_starts\":"<<best.skipped
                      <<",\"expanded_nodes\":"<<best.nodes<<",\"complete_windows\":"<<best.windows
                      <<",\"completed_layers\":"<<best.layers<<",\"complete_layers\":"<<best.layers
                      <<",\"criterion_windows\":"<<best.windows<<",\"partial_windows\":0,\"capped_attempts\":"<<best.capped
                      <<",\"refused_layers\":"<<best.refused<<",\"equivalent_candidates\":"<<best.equivalent
                      <<",\"completed_k_histogram\":";numbers(output,best.completed);
                output<<",\"tested_k_histogram\":";numbers(output,best.tested);
                output<<",\"selected_k_histogram\":";numbers(output,best.selected);output<<"}\n";output.flush();
                decisions<<"{\"config\":"<<quote(config.name)<<",\"key\":"<<quote(key)
                         <<",\"winning_seed\":";pair_json(decisions,best.seed_first,best.seed_second);
                decisions<<",\"producing_k_sequence\":";numbers(decisions,best.k_sequence);
                decisions<<",\"moments_available\":"<<(config.policy=="fixed-block"?"false":"true")<<",\"decisions\":";
                decisions_json(decisions,best.decisions);decisions<<"}\n";decisions.flush();
                std::cout<<config.name<<" joint k="<<config.min_k<<".."<<config.max_k<<" "<<key
                         <<" upper="<<(best.found?std::to_string(best.length):"miss")<<" nodes="<<best.nodes<<std::endl;
            }
            ++graphs;
        }
        if(!graphs||!input.eof()||!output||!improvements||!decisions)throw std::runtime_error("benchmark I/O failure");
        family1_cli::publish(folder/"summary.json","{\"graphs\":"+std::to_string(graphs)+",\"configurations\":"+
            std::to_string(configs.size())+",\"all_configured_cases_completed\":true,\"records_sha256\":"+
            quote(family1_cli::sha256(family1_cli::read(folder/"records.jsonl")))+"}\n");
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}

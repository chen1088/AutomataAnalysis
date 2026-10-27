#include "Family1TailScoredSeeds.h"
#include "Family1CliArtifacts.h"
#include "HardPairJointFinder.h"
#include <fstream>
#include <iostream>
#include <memory>
#include <queue>
#include <sstream>
#include <vector>

std::vector<std::uint64_t> scalar_trace(const family1::LargeGraph& g,const std::string&a,const std::string&b){
 if(a.empty()||a==b||a.size()!=b.size())throw std::logic_error("invalid witness");
 std::vector<std::uint64_t> trace(a.size()+1);
 for(unsigned int mask=0;mask<(1U<<g.size());++mask){unsigned int q=0,r=0;
  for(unsigned int i=0;i<a.size();++i){q=g.ports[q][(a[i]-'0')^((mask>>q)&1U)];r=g.ports[r][(b[i]-'0')^((mask>>r)&1U)];trace[i+1]+=q!=r;}
  if(q!=r)throw std::logic_error("scalar pair failure");
 }return trace;
}
std::uint64_t check_tables(const family1::LargeGraph& g){
 auto product=std::make_shared<const family1::ExactPackedProduct>(g);family1::CompleteCommonTailTables tables(g,product);
 const auto m=g.size();std::uint64_t checked=0;
 for(unsigned int mask=0;mask<(1U<<m);++mask)for(unsigned int q=0;q<m;++q)for(unsigned int r=0;r<m;++r){
  std::vector<int> distance(m*m,-1);std::queue<unsigned int> todo;distance[q*m+r]=0;todo.push(q*m+r);
  auto expected=hardpair::PairMergeabilityResult::unreachable_distance;
  while(!todo.empty()){auto at=todo.front();todo.pop();auto l=at/m,v=at%m;
   if(l==v){expected=distance[at];break;}
   for(unsigned int x=0;x<2;++x){auto l1=g.ports[l][x^((mask>>l)&1U)],v1=g.ports[v][x^((mask>>v)&1U)];auto next=l1*m+v1;
    if(distance[next]<0){distance[next]=distance[at]+1;todo.push(next);}}
  }
  if(tables.distance(mask,q,r)!=expected)throw std::logic_error("common-tail table differs from scalar forward BFS");++checked;
 }return checked;
}
int main(int argc,char**argv){try{
 if(argc==3 && std::string(argv[1])=="--verify-only"){
  std::ifstream input(argv[2]);std::string key;std::uint64_t checked=0,graphs=0;
  while(input>>key){checked+=check_tables(family1::LargeGraph::from_key(key));++graphs;}
  std::cout<<"{\"passed\":true,\"graphs\":"<<graphs<<",\"all_concrete_ordered_pair_checks\":"<<checked<<"}\n";return 0;
 }
 if(argc!=4)throw std::invalid_argument("keys rank-mode output (or --verify-only keys)");
 const unsigned int mode=std::stoul(argv[2]);if(mode>1)throw std::invalid_argument("rank mode0..1");
 std::ifstream input(argv[1]);std::ofstream output(argv[3]);std::string key;
 while(input>>key){
  auto g=family1::LargeGraph::from_key(key);if(g.canonical().key()!=key)throw std::invalid_argument("require canonical keys");
  family1::PackedLimits limits;limits.depth=24;limits.max_layer_states=std::uint64_t{1}<<24;limits.max_working_bytes=std::uint64_t{256}<<20;limits.timeout_ms=0;
  auto exact=family1::score_packed(g,limits);
  std::string first,second,producer,seed_first,seed_second,catalogue_hash;
  unsigned int upper=0;std::uint64_t nodes=0,windows=0,attempts=0,caps=0,skips=0,scored=0,seed_words=0,selected=0,pair_states=0;
  bool pair_capped=false,word_capped=false;family1::TailSeedScore winning_score;
  if(exact.status=="exact"){first=exact.witness[0];second=exact.witness[1];upper=exact.merge_length;producer="exact-word-layers";}
  else if(exact.lower_bound<=80){
   auto product=std::make_shared<const family1::ExactPackedProduct>(g);auto priority=family1::permutation_priority_selection(product,g);
   auto plan=family1::tail_scored_joint_seeds(g,product,20,1048576,16384,512,mode);
   scored=plan.candidates_scored;seed_words=plan.catalogue.words_evaluated;selected=plan.selected.size();pair_states=plan.common_pair_states;
   pair_capped=plan.catalogue.pair_capped;word_capped=plan.catalogue.word_capped;
   std::string fingerprint;for(const auto&[a,b]:plan.catalogue.pairs)fingerprint+=a+" "+b+"\n";
   catalogue_hash=family1_cli::sha256(fingerprint);
   for(const auto&seed:plan.selected){
    hardpair::joint::Options options;options.window_k=4;options.beam_width=16;options.diagonal_width=0;
    options.max_length=upper?upper-1:80;options.max_expansions=2000000;options.prioritize_permutation=true;options.max_trace_records=0;
    if(seed.first.size()>options.max_length){++skips;continue;}
    auto answer=hardpair::joint::find_pair(family1::JointPairState(product,seed.first,seed.second,priority),options);
    nodes+=answer.expanded_nodes;windows+=answer.complete_windows;caps+=answer.expansion_limit_reached;++attempts;
    if(answer.partial_windows)throw std::logic_error("partial joint window");
    if(answer.found && (!upper||answer.length<upper)){
     first=answer.first;second=answer.second;upper=answer.length;producer="tail-scored-seed-joint";
     seed_first=seed.first;seed_second=seed.second;winning_score=seed.score;
     scalar_trace(g,first,second);if(upper<exact.lower_bound)throw std::logic_error("upper contradicts lower");
    }
    if(upper && upper==exact.lower_bound)break;
   }
  }
  std::vector<std::uint64_t> trace;if(upper)trace=scalar_trace(g,first,second);
  using family1_cli::quote;
  output<<"{\"m\":"<<g.size()<<",\"key\":"<<quote(key)<<",\"canonical_table\":[";
  for(unsigned int i=0;i<g.size();++i){if(i)output<<',';output<<'['<<g.ports[i][0]<<','<<g.ports[i][1]<<']';}
  output<<"],\"tail_rank\":"<<quote(mode==0?"infinite-max-sum-D":"infinite-sum-max-D")
   <<",\"rank_mode\":"<<mode<<",\"configured_joint_k\":4,\"k\":"<<(producer=="exact-word-layers"?"null":"4")
   <<",\"alphabet\":[\"00\",\"01\",\"10\",\"11\"],\"window_kind\":"<<quote(producer=="exact-word-layers"?"exact-oracle":"joint-pair")
   <<",\"beam_width\":16,\"score\":\"permutation\",\"max_length\":80,\"expansion_cap\":2000000"
   <<",\"exact_depth\":24,\"exact_max_words\":16777216,\"exact_memory_bytes\":268435456"
   <<",\"prefix_depth\":20,\"prefix_words\":1048576,\"catalogue_size\":16384,\"selected_pairs\":512"
   <<",\"producer\":"<<(upper?quote(producer):"null")<<",\"upper_bound\":"<<(upper?std::to_string(upper):"null")
   <<",\"lower_bound\":"<<exact.lower_bound<<",\"minimality_certified\":"<<(upper && upper==exact.lower_bound?"true":"false")
   <<",\"witness\":";
  if(upper)output<<'['<<quote(first)<<','<<quote(second)<<']';else output<<"null";
  output<<",\"winning_seed\":["<<quote(seed_first)<<','<<quote(seed_second)<<"],\"winning_seed_score\":{\"infinite\":"<<winning_score.infinite_count
   <<",\"maximum_finite\":"<<winning_score.maximum_finite<<",\"sum_finite\":"<<winning_score.sum_finite<<",\"D\":"<<winning_score.disagreement<<'}'
   <<",\"witness_metric_trace\":[";
  for(unsigned int i=0;i<trace.size();++i){if(i)output<<',';output<<trace[i];}
  output<<"],\"synchronized_count_trace\":[";for(unsigned int i=0;i<trace.size();++i){if(i)output<<',';output<<(std::uint64_t{1}<<g.size())-trace[i];}
  output<<"],\"static_masks_verified\":"<<(upper?(std::uint64_t{1}<<g.size()):0)<<",\"expanded_nodes\":"<<nodes
   <<",\"complete_windows\":"<<windows<<",\"partial_windows\":0,\"attempts\":"<<attempts<<",\"skipped_seeds\":"<<skips
   <<",\"expansion_capped_attempts\":"<<caps<<",\"candidates_scored\":"<<scored<<",\"seed_words\":"<<seed_words
   <<",\"seed_candidates_selected\":"<<selected<<",\"common_pair_states\":"<<pair_states<<",\"catalogue_sha256\":"<<(catalogue_hash.empty()?"null":quote(catalogue_hash))
   <<",\"seed_pair_capped\":"<<(pair_capped?"true":"false")<<",\"seed_word_capped\":"<<(word_capped?"true":"false")
   <<",\"exact_evaluated_words\":"<<exact.evaluated_words<<",\"exact_peak_bytes\":"<<exact.peak_working_bytes
   <<",\"exact_status\":"<<quote(exact.status)<<",\"exact_reason\":"<<quote(exact.reason)<<",\"deterministic\":true,\"randomness\":false}\n";output.flush();
  std::cout<<"k=4 rank="<<mode<<" "<<key<<" upper="<<(upper?std::to_string(upper):"miss")<<" nodes="<<nodes<<std::endl;
 }
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}

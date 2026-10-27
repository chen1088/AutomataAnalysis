#include "HardPairJointAdaptive.h"
#include <array>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using u64=std::uint64_t;
namespace adaptive=hardpair::adaptive;
struct DFA {std::vector<std::array<unsigned int,2>> table;unsigned int root=0;};
using Family=std::vector<DFA>;
void require(bool value,const char*message){if(!value)throw std::logic_error(message);}
unsigned int endpoint(const DFA&dfa,const std::string&word){
    auto q=dfa.root;for(char c:word)q=dfa.table[q][c-'0'];return q;
}
bool permutation(const DFA&dfa){
    for(unsigned int a=0;a<2;++a){std::vector<bool> seen(dfa.table.size());
        for(const auto&row:dfa.table){if(seen[row[a]])return false;seen[row[a]]=true;}}
    return true;
}
std::string word(u64 id,unsigned int n){
    std::string out(n,'0');for(unsigned int i=0;i<n;++i){out[n-1-i]+=(id&1);id>>=1;}return out;
}
struct State {
    std::shared_ptr<const Family> family;
    std::vector<unsigned int> left,right;
    std::string first,second;
    State(std::shared_ptr<const Family> f,std::string a="",std::string b="")
        :family(std::move(f)),first(std::move(a)),second(std::move(b)){
        for(const auto&dfa:*family){left.push_back(endpoint(dfa,first));right.push_back(endpoint(dfa,second));}
    }
    State append_pair(bool a,bool b)const{
        auto out=*this;out.first+=a?'1':'0';out.second+=b?'1':'0';
        for(unsigned int i=0;i<family->size();++i){out.left[i]=(*family)[i].table[left[i]][a];out.right[i]=(*family)[i].table[right[i]][b];}
        return out;
    }
    u64 remaining_count()const{u64 out=0;for(unsigned int i=0;i<left.size();++i)out+=left[i]!=right[i];return out;}
    u64 priority_remaining_count()const{u64 out=0;for(unsigned int i=0;i<left.size();++i)out+=left[i]!=right[i]&&permutation((*family)[i]);return out;}
    u64 mask_count()const{return family->size();}
    bool distinct()const{return first!=second;}
    const std::string&first_word()const{return first;}
    const std::string&second_word()const{return second;}
    std::string state_key()const{
        std::string out(1,distinct()?'\1':'\0');
        for(unsigned int i=0;i<left.size();++i){out.push_back(static_cast<char>(left[i]));out.push_back(static_cast<char>(right[i]));}
        return out;
    }
};
std::shared_ptr<const Family> closure(const std::vector<std::array<unsigned int,2>>&base){
    auto family=std::make_shared<Family>();
    for(unsigned int mask=0;mask<(1U<<base.size());++mask){
        DFA dfa;for(unsigned int q=0;q<base.size();++q)
            dfa.table.push_back({base[q][(mask>>q)&1U],base[q][1U^((mask>>q)&1U)]});
        family->push_back(std::move(dfa));
    }return family;
}
unsigned int exact_H(const Family&family,unsigned int limit=8){
    for(unsigned int n=1;n<=limit;++n){
        std::map<std::vector<unsigned int>,std::string> seen;
        for(u64 id=0;id<(u64{1}<<n);++id){
            const auto w=word(id,n);std::vector<unsigned int> profile;
            for(const auto&dfa:family)profile.push_back(endpoint(dfa,w));
            if(!seen.emplace(profile,w).second)return n;
        }
    }return 0;
}
struct ReferenceStats {
    u64 n=0,sum=0,sum2=0,minimum=UINT64_MAX,maximum=0,positives=0,bestD=UINT64_MAX,bestP=UINT64_MAX;
    std::array<u64,4> action_n{},action_sum{},action_min{UINT64_MAX,UINT64_MAX,UINT64_MAX,UINT64_MAX};
    std::map<u64,u64> histogram;
};
ReferenceStats reference(const Family&family,const std::string&first,const std::string&second,unsigned int k,bool priority){
    ReferenceStats out;
    // Independent nested word enumeration, never the core's joint BFS.
    for(u64 a=0;a<(u64{1}<<k);++a)for(u64 b=0;b<(u64{1}<<k);++b){
        auto u=first+word(a,k),v=second+word(b,k);u64 d=0,p=0;
        for(const auto&dfa:family){const bool different=endpoint(dfa,u)!=endpoint(dfa,v);d+=different;p+=priority&&different&&permutation(dfa);}
        const auto action=2*((a>>(k-1))&1)+((b>>(k-1))&1);
        ++out.n;out.sum+=d;out.sum2+=d*d;out.minimum=std::min(out.minimum,d);out.maximum=std::max(out.maximum,d);
        ++out.action_n[action];out.action_sum[action]+=d;out.action_min[action]=std::min(out.action_min[action],d);++out.histogram[d];
        out.positives+=u!=v&&!d;
        if(u!=v&&(p<out.bestP||(p==out.bestP&&d<out.bestD))){out.bestP=p;out.bestD=d;}
    }return out;
}
u64 windows_checked=0;
void verify_decision(const Family&family,const adaptive::DecisionTrace&decision,const adaptive::Options&options){
    require(decision.depth==decision.parent_first.size()&&decision.depth==decision.parent_second.size(),"trace depth mismatch");
    State parent(std::make_shared<const Family>(family),decision.parent_first,decision.parent_second);
    require(parent.remaining_count()==decision.parent_D,"parent D mismatch");
    require((options.priority?parent.priority_remaining_count():0)==decision.parent_priority,"parent P mismatch");
    unsigned int expected_k=1;
    for(const auto&stats:decision.windows){
        require(stats.k==expected_k++,"layers not complete/increasing");
        const auto r=reference(family,decision.parent_first,decision.parent_second,stats.k,options.priority);
        require(stats.n==r.n&&stats.n==(u64{1}<<(2*stats.k)),"incomplete four-symbol leaf count");
        require(stats.sumD==r.sum&&stats.sumD2==r.sum2&&stats.minD==r.minimum&&stats.maxD==r.maximum,"moments differ");
        require(stats.D_histogram==std::vector<std::pair<u64,u64>>(r.histogram.begin(),r.histogram.end()),"full disagreement histogram differs");
        require(stats.action_n==r.action_n&&stats.action_sumD==r.action_sum&&stats.action_minD==r.action_min,"conditional action statistics differ");
        require(stats.positive_leaves==r.positives&&stats.best_leaf_D==r.bestD&&stats.best_leaf_priority==r.bestP,"distinct leaf rank differs");
        const u64 total=r.n*r.sum2-r.sum*r.sum;
        u64 squares=0;for(auto sum:r.action_sum)squares+=sum*sum;
        const u64 action=4*squares-r.sum*r.sum,denominator=r.n*r.n*family.size()*family.size();
        require(stats.total_numerator.decimal()==std::to_string(total),"total variance numerator differs");
        require(stats.action_numerator.decimal()==std::to_string(action),"action variance numerator differs");
        require(stats.denominator.decimal()==std::to_string(denominator),"variance denominator differs");
        const auto numerator=options.policy==adaptive::Policy::ActionVariance?action:total;
        require(stats.criterion_met==(numerator*1000000>=denominator*options.threshold_ppm),"exact criterion differs");
        const auto minimum=std::min(options.min_k,options.max_length-decision.depth);
        require(stats.criterion_eligible==(stats.k>=minimum),"criterion eligibility differs");
        const bool progress=r.bestP<decision.parent_priority||(r.bestP==decision.parent_priority&&r.bestD<decision.parent_D);
        require(stats.progress_met==progress,"numeric progress differs");
        require(stats.adequate==(stats.criterion_met&&(!options.require_improvement||progress)),"adequacy differs");
        ++windows_checked;
    }
    if(decision.selected){
        require(!decision.windows.empty()&&decision.selected_k==decision.windows.back().k,"selected k is not last complete layer");
        const auto&s=decision.windows.back();
        if(decision.reason=="variance")require(s.criterion_eligible&&s.adequate,"variance stopped without adequate signal");
        if(decision.reason=="success")require(s.positive_leaves>0,"success not observed in complete window");
    }else require(decision.minimum_refused&&decision.windows.empty(),"unselected decision has partial window");
}
void verify_result(const Family&family,const adaptive::Result&result,const adaptive::Options&options){
    u64 nodes=0,layers=0,tested=0,selected=0;
    for(unsigned int k=1;k<=8;++k){nodes+=result.completed_k_histogram[k]*(u64{1}<<(2*k));
        layers+=result.completed_k_histogram[k];tested+=result.tested_k_histogram[k];selected+=result.selected_k_histogram[k];}
    require(nodes==result.expanded_nodes&&layers==result.complete_layers&&tested==result.criterion_windows,"work histogram identity differs");
    for(const auto&decision:result.decisions)verify_decision(family,decision,options);
    for(const auto&decision:result.winning_decisions){
        verify_decision(family,decision,options);
        require(result.first.starts_with(decision.parent_first)&&result.second.starts_with(decision.parent_second),"winning ancestry is not a witness prefix");
    }
    if(result.found){
        require(result.first!=result.second&&result.first.size()==result.second.size()&&result.first.size()==result.length,"invalid witness");
        for(const auto&dfa:family)require(endpoint(dfa,result.first)==endpoint(dfa,result.second),"scalar witness failure");
        require(result.winning_decisions.empty()?result.winning_k==0:
                result.winning_k==result.winning_decisions.back().selected_k,"finishing k differs");
    }
    require(!result.minimality_certified,"heuristic claimed minimality");
}
void same(const adaptive::Result&a,const adaptive::Result&b){
    require(a.found==b.found&&a.first==b.first&&a.second==b.second&&a.length==b.length&&
            a.expanded_nodes==b.expanded_nodes&&a.completed_k_histogram==b.completed_k_histogram&&
            a.tested_k_histogram==b.tested_k_histogram&&a.selected_k_histogram==b.selected_k_histogram,"non-deterministic repeat");
}
void basic_families(){
    std::vector<std::shared_ptr<const Family>> families{
        closure({{0,0}}),closure({{0,1},{0,1}}),closure({{0,1},{1,2},{0,1}}),
        std::make_shared<const Family>(Family{{{{0,1},{1,0}},1},{{{1,2},{2,0},{0,1}},2}})};
    for(const auto&family:families){
        adaptive::Options o;o.min_k=o.max_k=1;o.policy=adaptive::Policy::Fixed;
        o.beam=o.diagonal_width=4096;o.max_length=6;o.max_expansions=500000;o.priority=false;o.max_trace_records=4096;
        auto answer=adaptive::find_pair(State(family),o);verify_result(*family,answer,o);
        require(answer.found&&answer.length==exact_H(*family,6),"full small frontier missed exact shortest pair");
        same(answer,adaptive::find_pair(State(family),o));
    }
}
void variance_and_rolling(){
    for(auto family:{closure({{0,1},{0,2},{2,2}}),closure({{0,1},{0,2},{0,2}})}){
        for(auto policy:{adaptive::Policy::Fixed,adaptive::Policy::TotalVariance,adaptive::Policy::ActionVariance}){
            adaptive::Options o;o.min_k=2;o.max_k=policy==adaptive::Policy::Fixed?2:4;
            o.policy=policy;o.priority=false;o.beam=3;o.max_length=7;o.max_expansions=200000;o.max_trace_records=4096;
            auto answer=adaptive::find_pair(State(family,"0","1"),o);verify_result(*family,answer,o);
            same(answer,adaptive::find_pair(State(family,"0","1"),o));
            for(const auto&d:answer.decisions)if(d.depth>1)require(d.depth<7,"rolling depth invalid");
        }
    }
    auto family=closure({{0,1},{0,2},{0,2}});
    adaptive::Options o;o.min_k=2;o.max_k=4;o.priority=false;o.policy=adaptive::Policy::ActionVariance;o.max_length=5;
    auto answer=adaptive::find_pair(State(family,"0","1"),o);verify_result(*family,answer,o);
    const auto&s=answer.decisions.front().windows[1];
    require(s.action_numerator.decimal()=="0"&&s.action_minD==std::array<u64,4>{4,3,4,4},"zero action-mean variance fixture changed");
}
void budgets_and_success(){
    auto family=closure({{0,1},{0,2},{0,2}});
    adaptive::Options o;o.min_k=2;o.max_k=4;o.priority=false;o.max_expansions=19;o.max_length=5;
    auto refused=adaptive::find_pair(State(family,"0","1"),o);verify_result(*family,refused,o);
    require(!refused.found&&refused.expanded_nodes==0&&refused.minimum_windows_refused==1&&refused.budget_refused,"minimum window not atomically refused");
    o.max_expansions=20;o.threshold_ppm=1000000;
    auto increment=adaptive::find_pair(State(family,"0","1"),o);verify_result(*family,increment,o);
    require(increment.expanded_nodes==20&&increment.budget_refused&&increment.decisions[0].selected_k==2&&
            increment.decisions[0].refused_k==3,"incremental layer not atomically refused");
    auto constant=closure({{0,0}});
    o.min_k=o.max_k=3;o.policy=adaptive::Policy::Fixed;o.max_expansions=1000;o.max_length=5;o.max_trace_records=0;
    auto early=adaptive::find_pair(State(constant),o);verify_result(*constant,early,o);
    require(early.found&&early.length==1&&early.expanded_nodes==84&&early.complete_layers==3,"early success truncated statistics");
    require(early.decisions.empty()&&!early.winning_decisions.empty()&&early.winning_k==3,"winning ancestry lost under zero trace cap");
    o.min_k=o.max_k=4;o.max_length=2;
    auto shortened=adaptive::find_pair(State(constant),o);verify_result(*constant,shortened,o);
    require(shortened.winning_k==2&&shortened.expanded_nodes==20,"final actual span was not recorded");
}
void multiple_parents_and_forecast_dedup(){
    auto family=std::make_shared<const Family>(Family{{{{0,1},{0,0}},0},{{{0,1},{1,0}},0}});
    adaptive::Options o;o.min_k=o.max_k=2;o.policy=adaptive::Policy::Fixed;o.priority=false;
    o.beam=8;o.max_length=5;o.max_expansions=10000;o.max_trace_records=4096;
    std::vector<State> starts{State(family,"00","10"),State(family,"01","10")};
    auto answer=adaptive::find_pair(starts,o);verify_result(*family,answer,o);
    require(answer.found&&answer.length==3&&answer.expanded_nodes==40&&
            answer.completed_k_histogram[1]==2&&answer.completed_k_histogram[2]==2,
            "first positive stopped before the shorter completion in another parent");
    require(answer.winning_decisions.back().parent_first=="01"&&answer.winning_decisions.back().parent_second=="10",
            "winning ancestry belongs to the wrong retained parent");

    // Complete-profile-equivalent immediate children can carry forecasts
    // from different selected horizons. Independent scalar enumeration gives
    // k2 for (0010,0101), k3 for (1110,1111). The latter's immediate child has
    // a strictly better forecast despite lexicographically larger words.
    family=closure({{0,1},{0,2},{0,2}});
    o.min_k=2;o.max_k=3;o.policy=adaptive::Policy::TotalVariance;o.threshold_ppm=40000;o.max_length=8;
    starts={State(family,"0010","0101"),State(family,"1110","1111")};
    answer=adaptive::find_pair(starts,o);verify_result(*family,answer,o);
    bool better_representative=false,worse_representative=false;
    for(const auto&decision:answer.decisions)if(decision.depth==5){
        better_representative|=decision.parent_first=="11101"&&decision.parent_second=="11110";
        worse_representative|=decision.parent_first=="00101"&&decision.parent_second=="01010";
    }
    require(better_representative&&!worse_representative&&answer.equivalent_candidates,
            "profile deduplication discarded a better already-evaluated variable-horizon forecast");
}
void priority_progress(){
    auto family=closure({{0,1},{2,3},{2,3},{4,5},{0,6},{4,6},{1,5}});
    adaptive::Options o;o.min_k=o.max_k=1;o.policy=adaptive::Policy::TotalVariance;
    o.priority=true;o.require_improvement=true;o.threshold_ppm=0;o.max_length=4;o.beam=2;
    auto answer=adaptive::find_pair(State(family,"010","100"),o);verify_result(*family,answer,o);
    const auto&decision=answer.decisions.front();const auto&stats=decision.windows.front();
    require(decision.parent_priority==4&&decision.parent_D==96&&
            stats.best_leaf_priority==3&&stats.best_leaf_D==120&&stats.progress_met&&stats.adequate,
            "P-first progress incorrectly required total D to decrease");
}
struct RepeatedParity {
    unsigned int left=0,right=1;std::string first="0",second="1";
    RepeatedParity append_pair(bool a,bool b)const{auto s=*this;s.left^=a;s.right^=b;s.first+=a?'1':'0';s.second+=b?'1':'0';return s;}
    u64 remaining_count()const{return left==right?0:65536;}
    u64 mask_count()const{return 65536;}
    bool distinct()const{return first!=second;}
    const std::string&first_word()const{return first;}
    const std::string&second_word()const{return second;}
    std::string state_key()const{return std::string{static_cast<char>(left),static_cast<char>(right),static_cast<char>(distinct())};}
};
void wide_arithmetic(){
    using adaptive::detail::product;
    require(product(UINT64_MAX,UINT64_MAX).decimal()=="340282366920938463426481119284349108225","wide64 multiplication differs");
    require(adaptive::Wide{1,0}.decimal()=="18446744073709551616","wide decimal conversion differs");
    adaptive::Options o;o.min_k=o.max_k=8;o.policy=adaptive::Policy::Fixed;o.priority=false;o.max_length=9;o.max_expansions=100000;o.max_trace_records=0;o.threshold_ppm=250000;
    auto answer=adaptive::find_pair(RepeatedParity{},o);
    require(answer.found&&answer.length==2&&answer.expanded_nodes==87380,"large exact window incomplete");
    const auto&s=answer.winning_decisions.back().windows.back();
    require(s.n==65536&&s.sumD==2147483648ULL&&s.sumD2==140737488355328ULL,"large window moments differ");
    require(s.denominator.decimal()=="18446744073709551616"&&s.total_numerator.decimal()=="4611686018427387904"&&
            s.action_numerator.decimal()=="0"&&s.criterion_met,"wide variance quarter boundary differs");
    o.threshold_ppm=250001;answer=adaptive::find_pair(RepeatedParity{},o);
    require(!answer.winning_decisions.back().windows.back().criterion_met,"wide threshold comparison rounded");
}
void invalid_options(){
    auto family=closure({{0,0}});adaptive::Options o;o.advance=adaptive::Advance::Block;
    bool rejected=false;try{adaptive::find_pair(State(family),o);}catch(const std::invalid_argument&){rejected=true;}
    require(rejected,"adaptive block mode was accepted");
}
} // namespace
int main(){
    try{basic_families();variance_and_rolling();budgets_and_success();multiple_parents_and_forecast_dedup();
        priority_progress();wide_arithmetic();invalid_options();
        std::cout<<"{\"passed\":true,\"independent_windows_checked\":"<<windows_checked<<"}\n";return 0;}
    catch(const std::exception&error){std::cerr<<error.what()<<'\n';return 1;}
}

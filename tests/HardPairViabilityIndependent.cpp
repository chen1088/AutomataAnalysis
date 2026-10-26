#include "HardPairViability.h"
#include "HardPairFinder.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <memory>
#include <queue>
#include <set>
#include <stdexcept>
#include <vector>

namespace {
using Table=std::vector<std::array<unsigned int,2>>;
void require(bool c,const char* s){if(!c)throw std::runtime_error(s);}
int forward_distance(const Table& t,unsigned int a,unsigned int b)
{
    struct Node{unsigned int a,b,d;};std::queue<Node> q;q.push({a,b,0});
    std::set<std::pair<unsigned int,unsigned int>> seen{{a,b}};
    while(!q.empty()){
        auto x=q.front();q.pop();if(x.a==x.b)return int(x.d);
        for(unsigned int s=0;s<2;++s){auto p=std::pair{t[x.a][s],t[x.b][s]};if(seen.insert(p).second)q.push({p.first,p.second,x.d+1});}
    }
    return -1;
}
struct Context {Table table;hardpair::PairMergeabilityResult result;};
struct State {
    std::shared_ptr<const Context> context;unsigned int a,b;
    std::uint64_t mask_count()const{return 1;}
    std::uint64_t remaining_count()const{return a!=b;}
    State append_common(bool x)const{return{context,context->table[a][x],context->table[b][x]};}
    bool has_proven_obstruction()const{return context->result.proven_unmergeable(a,b);}
};
std::shared_ptr<Context> context(Table t,std::uint64_t cap=1000000)
{
    auto c=std::make_shared<Context>();c->table=std::move(t);hardpair::PairMergeabilityLimits l;l.max_pair_states=cap;
    c->result=hardpair::analyze_pair_mergeability(unsigned(c->table.size()),[&](unsigned int s,bool x){return c->table[s][x];},l);
    return c;
}
}
int main()
{
    try{
        std::uint64_t dfas=0,pairs=0;
        for(unsigned int n=1;n<=3;++n){
            std::uint64_t count=1;for(unsigned int i=0;i<2*n;++i)count*=n;
            for(std::uint64_t code=0;code<count;++code){
                auto value=code;Table t(n);for(auto& row:t)for(auto& target:row){target=value%n;value/=n;}
                auto r=hardpair::analyze_pair_mergeability(n,[&](unsigned int s,bool x){return t[s][x];});
                require(r.complete&&!r.state_capped&&!r.interrupted,"small complete viability analysis failed");
                std::uint64_t positives=0;
                for(unsigned int a=0;a<n;++a)for(unsigned int b=0;b<n;++b){
                    const auto d=forward_distance(t,a,b);const auto id=a*n+b;
                    require(bool(r.mergeable[id])==(d>=0),"reverse reachability disagrees with independent forward BFS");
                    require(r.proven_unmergeable(a,b)==(d<0),"negative pair certificate wrong");
                    if(d>=0){require(r.distance[id]==unsigned(d),"shortest local distance wrong");++positives;}
                    else{
                        require(r.distance[id]==hardpair::PairMergeabilityResult::unreachable_distance,"unreachable distance sentinel wrong");
                        for(unsigned int x=0;x<2;++x)require(r.proven_unmergeable(t[a][x],t[b][x]),"negative pairs not closed");
                    }
                    ++pairs;
                }
                require(r.mergeable_pairs==positives,"mergeability population wrong");++dfas;
            }
        }
        require(dfas==746&&pairs==6626,"missing complete binary DFA tables or pairs");
        Table permanent{{0,1},{1,0}};
        auto full=context(permanent);auto unknown=context(permanent,1);
        require(!unknown->result.complete&&unknown->result.state_capped,"state cap did not return unknown");
        for(unsigned int a=0;a<2;++a)for(unsigned int b=0;b<2;++b)require(!unknown->result.proven_unmergeable(a,b),"capped analysis prunes a pair");
        hardpair::FinderOptions o;o.window_k=2;o.beam_width=2;o.max_suffix=4;o.tail_threshold=0;
        auto blocked=hardpair::find_hard_pair_suffix(State{full,0,1},o);
        require(blocked.proven_obstruction&&!blocked.found&&blocked.expanded_nodes==0,"initial proven obstruction not safely pruned");
        auto not_proven=hardpair::find_hard_pair_suffix(State{unknown,0,1},o);
        require(!not_proven.proven_obstruction&&!not_proven.found&&not_proven.expanded_nodes>0,"unknown cap pruned a branch");
        auto child=context({{2,0},{3,0},{2,2},{3,3}});
        auto found=hardpair::find_hard_pair_suffix(State{child,0,1},o);
        require(found.found&&found.suffix=="1"&&found.obstruction_pruned_nodes>=1,"dead child pruning lost the viable sibling");
        volatile std::sig_atomic_t stop=1;hardpair::PairMergeabilityLimits lim;lim.interrupted=&stop;
        auto interrupted=hardpair::analyze_pair_mergeability(2,[&](unsigned int s,bool x){return permanent[s][x];},lim);
        require(interrupted.interrupted&&!interrupted.complete&&!interrupted.proven_unmergeable(0,1),"cancelled analysis made a negative claim");
        bool rejected=false;try{hardpair::pair_mergeability(2,[](unsigned int,bool){return 2;});}catch(const std::invalid_argument&){rejected=true;}
        require(rejected,"invalid transition target accepted");
        std::cout<<"{\"passed\":true,\"explicit_binary_DFAs\":"<<dfas<<",\"ordered_pair_comparisons\":"<<pairs
            <<",\"negative_closed_sets_checked\":true,\"caps_and_interruptions_never_prune\":true,\"generic_initial_and_child_pruning_checked\":true}\n";
        return 0;
    }catch(const std::exception&e){std::cerr<<"HardPairViabilityIndependent: "<<e.what()<<'\n';return 1;}
}

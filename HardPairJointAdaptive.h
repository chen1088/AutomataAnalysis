#pragma once
// Deterministic complete joint-window moments and adaptive receding-horizon
// search. Moments include ALL leaves, even identical-word leaves. Success
// separately requires distinct words and D=0. No variance is a length bound.
#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <map>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

namespace hardpair::adaptive {
using u64 = std::uint64_t;
enum class Policy { Fixed, TotalVariance, ActionVariance };
enum class Advance { First, Block };

// Portable exact unsigned 128-bit value; no compiler extension or dependency.
struct Wide {
    u64 hi=0,lo=0;
    bool operator==(const Wide&)const=default;
    bool operator<(const Wide& other)const{return hi!=other.hi?hi<other.hi:lo<other.lo;}
    bool operator>=(const Wide& other)const{return !(*this<other);}
    std::string decimal()const{
        if(!hi && !lo)return "0";
        auto value=*this;std::string out;
        while(value.hi || value.lo){
            const std::array<std::uint32_t,4> limbs{
                static_cast<std::uint32_t>(value.hi>>32),static_cast<std::uint32_t>(value.hi),
                static_cast<std::uint32_t>(value.lo>>32),static_cast<std::uint32_t>(value.lo)};
            std::array<std::uint32_t,4> quotient{};u64 remainder=0;
            for(unsigned int i=0;i<4;++i){const u64 part=(remainder<<32)|limbs[i];quotient[i]=static_cast<std::uint32_t>(part/10);remainder=part%10;}
            out.push_back(static_cast<char>('0'+remainder));
            value={(static_cast<u64>(quotient[0])<<32)|quotient[1],
                   (static_cast<u64>(quotient[2])<<32)|quotient[3]};
        }
        std::reverse(out.begin(),out.end());return out;
    }
};
namespace detail {
inline Wide product(u64 a,u64 b){
    constexpr u64 mask=0xffffffffULL;
    const auto a0=a&mask,a1=a>>32,b0=b&mask,b1=b>>32;
    const u64 p0=a0*b0,p1=a0*b1,p2=a1*b0,p3=a1*b1;
    const u64 middle=(p0>>32)+(p1&mask)+(p2&mask);
    return {p3+(p1>>32)+(p2>>32)+(middle>>32),(middle<<32)|(p0&mask)};
}
inline Wide add(Wide a,Wide b){
    const auto lo=a.lo+b.lo;const auto carry=lo<a.lo;
    if(a.hi>std::numeric_limits<u64>::max()-b.hi || a.hi+b.hi>std::numeric_limits<u64>::max()-carry)
        throw std::overflow_error("adaptive wide addition overflow");
    return {a.hi+b.hi+carry,lo};
}
inline Wide subtract(Wide a,Wide b){
    if(a<b)throw std::logic_error("negative adaptive variance numerator");
    return {a.hi-b.hi-(a.lo<b.lo),a.lo-b.lo};
}
inline Wide scale(Wide a,std::uint32_t b){
    if(!b)return {};
    const auto low=product(a.lo,b);
    if(a.hi>(std::numeric_limits<u64>::max()-low.hi)/b)
        throw std::overflow_error("adaptive wide scaling overflow");
    return {a.hi*b+low.hi,low.lo};
}
template<class State>std::string key(const State& state){
    if constexpr(requires{std::string(state.state_key());})return std::string(state.state_key());
    else if constexpr(requires{std::string(state.key());})return std::string(state.key());
    else{static_assert(sizeof(State)==0,"adaptive State needs a complete state_key() or key()");}
}
template<class State>bool words_before(const State&a,const State&b){
    return a.first_word()!=b.first_word()?a.first_word()<b.first_word():a.second_word()<b.second_word();
}
} // namespace detail

struct Options {
    unsigned int min_k=2,max_k=6,beam=16,diagonal_width=0,max_length=80;
    u64 max_expansions=2000000,threshold_ppm=10000;
    Policy policy=Policy::TotalVariance;
    Advance advance=Advance::First;
    bool priority=true,avoid_cycles=false,require_improvement=false;
    unsigned int max_trace_records=64;
};
struct WindowStats {
    unsigned int k=0;
    u64 n=0,sumD=0,sumD2=0,minD=0,maxD=0;
    std::array<u64,4> action_n{},action_sumD{},action_minD{};
    std::vector<std::pair<u64,u64>> D_histogram; // Sorted (D,frequency), all leaves.
    Wide total_numerator,action_numerator,denominator;
    bool criterion_eligible=false,criterion_met=false,progress_met=false,adequate=false;
    u64 positive_leaves=0,best_leaf_D=0,best_leaf_priority=0;
};
struct DecisionTrace {
    unsigned int depth=0,selected_k=0,refused_k=0;
    std::string parent_first,parent_second,reason;
    u64 parent_D=0,parent_priority=0;
    std::vector<WindowStats> windows;
    bool selected=false,minimum_refused=false;
};
struct Result {
    bool found=false,budget_refused=false,length_capped=false,beam_truncated=false;
    bool minimality_certified=false;
    std::string first,second;
    unsigned int length=0,winning_k=0;
    u64 mask_count=0,expanded_nodes=0,complete_layers=0,criterion_windows=0;
    u64 budget_refused_layers=0,minimum_windows_refused=0,rounds=0,equivalent_candidates=0,cycles_avoided=0;
    std::array<u64,9> completed_k_histogram{},tested_k_histogram{},selected_k_histogram{};
    std::vector<DecisionTrace> decisions,winning_decisions;
    u64 trace_records_truncated=0;
};

// State retains the complete ordered endpoint profiles and distinct-word flag.
// state_key()/key() must encode that full Markov state, never only D or a hash.
// Optional priority_remaining_count() is the mismatch count in a subset of
// coordinates (P); it is not called when priority=false.
template<class State>Result find_pair(std::vector<State> initial,const Options& options={})
{
    if(initial.empty() || !options.min_k || options.min_k>options.max_k || options.max_k>8 ||
       !options.beam || options.beam>4096 || options.diagonal_width>4096 || !options.max_length ||
       options.max_length>4096 || !options.max_expansions || options.threshold_ppm>1000000 ||
       options.max_trace_records>4096 ||
       (options.policy==Policy::Fixed && options.min_k!=options.max_k) ||
       (options.policy!=Policy::Fixed && options.advance==Advance::Block))
        throw std::invalid_argument("adaptive finder needs k1..8, positive bounded beam/length/work, and adaptive first-symbol advance");
    Result result;result.mask_count=initial.front().mask_count();
    if(!result.mask_count || result.mask_count>65536)throw std::invalid_argument("adaptive moments support 1..65536 original coordinates");
    const auto priority=[&](const State&state)->u64{
        if(!options.priority)return 0;
        if constexpr(requires{state.priority_remaining_count();}){
            const auto p=static_cast<u64>(state.priority_remaining_count());
            if(p>state.remaining_count())throw std::logic_error("adaptive priority mismatches exceed D");
            return p;
        }else throw std::invalid_argument("adaptive priority requires a subset mismatch accessor");
    };
    const auto inspect=[&](const State&state,std::size_t depth){
        if(state.first_word().size()!=depth || state.second_word().size()!=depth || state.mask_count()!=result.mask_count ||
           state.remaining_count()>result.mask_count || state.distinct()!=(state.first_word()!=state.second_word()) ||
           (!state.distinct() && state.remaining_count()))
            throw std::logic_error("adaptive state violates full-coordinate or word invariants");
    };
    struct Path {DecisionTrace decision;std::shared_ptr<const Path> previous;};
    struct Node {
        State state;u64 D=0,P=0,futureD=0,futureP=0;
        std::shared_ptr<const Path> path;std::string key;
    };
    std::shared_ptr<const Path> winning_path;
    const auto consider=[&](const State&state,std::shared_ptr<const Path> path,unsigned int k){
        if(!state.distinct() || state.remaining_count())return;
        const auto depth=static_cast<unsigned int>(state.first_word().size());
        if(!result.found || depth<result.length ||
           (depth==result.length && (state.first_word()<result.first ||
            (state.first_word()==result.first && state.second_word()<result.second)))){
            result.found=true;result.length=depth;result.first=state.first_word();result.second=state.second_word();
            result.winning_k=k;winning_path=std::move(path);
        }
    };
    const auto finish=[&](){
        result.winning_decisions.clear();
        for(auto at=winning_path;at;at=at->previous)result.winning_decisions.push_back(at->decision);
        std::reverse(result.winning_decisions.begin(),result.winning_decisions.end());
        return result;
    };
    const auto initial_depth=initial.front().first_word().size();
    if(initial_depth>options.max_length)throw std::invalid_argument("adaptive initial words exceed maximum length");
    std::sort(initial.begin(),initial.end(),detail::words_before<State>);
    std::vector<Node> beam;
    for(auto&state:initial){
        inspect(state,initial_depth);consider(state,{},0);
        const u64 d=state.remaining_count(),p=priority(state);auto key=detail::key(state);
        beam.push_back({std::move(state),d,p,d,p,{},std::move(key)});
    }
    if(result.found)return finish();
    const auto better=[](const Node&a,const Node&b){
        if(a.futureP!=b.futureP)return a.futureP<b.futureP;
        if(a.futureD!=b.futureD)return a.futureD<b.futureD;
        if(a.P!=b.P)return a.P<b.P;
        if(a.D!=b.D)return a.D<b.D;
        return detail::words_before(a.state,b.state);
    };
    const auto trace=[&](const DecisionTrace& decision){
        if(result.decisions.size()<options.max_trace_records)result.decisions.push_back(decision);
        else ++result.trace_records_truncated;
    };
    std::unordered_set<std::string> expanded;
    while(!beam.empty() && beam.front().state.first_word().size()<options.max_length){
        ++result.rounds;
        std::vector<Node> ordinary,diagonal;
        bool stop_after_round=false;
        if(options.avoid_cycles)for(const auto&parent:beam)expanded.insert(parent.key);
        const auto retain=[&](Node node){
            if(options.avoid_cycles && expanded.contains(node.key)){++result.cycles_avoided;return;}
            auto&pool=node.state.distinct()?ordinary:diagonal;
            const auto limit=node.state.distinct()?options.beam:options.diagonal_width;
            if(!limit){result.beam_truncated=true;return;}
            for(auto&old:pool)if(old.key==node.key){
                ++result.equivalent_candidates;
                if(better(node,old))old=std::move(node);
                return;
            }
            if(pool.size()<limit){pool.push_back(std::move(node));return;}
            result.beam_truncated=true;
            const auto worst=std::max_element(pool.begin(),pool.end(),better);
            if(better(node,*worst))*worst=std::move(node);
        };
        for(const auto&parent:beam){
            const auto depth=static_cast<unsigned int>(parent.state.first_word().size());
            const auto remaining=options.max_length-depth;
            const auto minimum=std::min(options.min_k,remaining),maximum=std::min(options.max_k,remaining);
            DecisionTrace decision;decision.depth=depth;decision.parent_first=parent.state.first_word();
            decision.parent_second=parent.state.second_word();decision.parent_D=parent.D;decision.parent_priority=parent.P;
            u64 required_min=0,level=1;
            for(unsigned int k=1;k<=minimum;++k){level*=4;required_min+=level;}
            if(required_min>options.max_expansions-result.expanded_nodes){
                result.budget_refused=true;++result.budget_refused_layers;++result.minimum_windows_refused;
                decision.minimum_refused=true;decision.refused_k=minimum;decision.reason="minimum-budget-refused";
                trace(decision);stop_after_round=true;break;
            }
            struct Leaf {State state;u64 D=0,P=0;unsigned int action=0;};
            std::vector<Leaf> frontier{{parent.state,parent.D,parent.P,0}};
            std::array<std::optional<Leaf>,4> first_children;
            std::optional<Leaf> positive;
            for(unsigned int k=1;k<=maximum;++k){
                const u64 next_size=4*static_cast<u64>(frontier.size());
                if(next_size>options.max_expansions-result.expanded_nodes){
                    result.budget_refused=true;++result.budget_refused_layers;
                    decision.refused_k=k;decision.reason="budget-refused-increment";stop_after_round=true;break;
                }
                std::vector<Leaf> next;next.reserve(static_cast<std::size_t>(next_size));
                for(const auto&leaf:frontier)for(unsigned int symbol=0;symbol<4;++symbol){
                    auto state=leaf.state.append_pair((symbol&2U)!=0,(symbol&1U)!=0);
                    inspect(state,depth+k);const u64 d=state.remaining_count(),p=priority(state);
                    Leaf child{std::move(state),d,p,k==1?symbol:leaf.action};
                    ++result.expanded_nodes;
                    if(k==1)first_children[symbol]=child;
                    if(child.state.distinct() && !d && (!positive ||
                       child.state.first_word().size()<positive->state.first_word().size() ||
                       (child.state.first_word().size()==positive->state.first_word().size() &&
                        detail::words_before(child.state,positive->state))))positive=child;
                    next.push_back(std::move(child));
                }
                frontier=std::move(next);
                WindowStats stats;stats.k=k;stats.n=frontier.size();stats.minD=std::numeric_limits<u64>::max();
                stats.action_minD.fill(std::numeric_limits<u64>::max());
                std::map<u64,u64> histogram;
                bool best_set=false;
                for(const auto&leaf:frontier){
                    stats.sumD+=leaf.D;stats.sumD2+=leaf.D*leaf.D;
                    ++histogram[leaf.D];
                    stats.minD=std::min(stats.minD,leaf.D);stats.maxD=std::max(stats.maxD,leaf.D);
                    ++stats.action_n[leaf.action];stats.action_sumD[leaf.action]+=leaf.D;
                    stats.action_minD[leaf.action]=std::min(stats.action_minD[leaf.action],leaf.D);
                    stats.positive_leaves+=leaf.state.distinct() && !leaf.D;
                    if(leaf.state.distinct() && (!best_set || leaf.P<stats.best_leaf_priority ||
                       (leaf.P==stats.best_leaf_priority && leaf.D<stats.best_leaf_D))){
                        stats.best_leaf_priority=leaf.P;stats.best_leaf_D=leaf.D;best_set=true;
                    }
                }
                stats.D_histogram.assign(histogram.begin(),histogram.end());
                for(auto n:stats.action_n)if(n!=stats.n/4)throw std::logic_error("adaptive conditional action population is incomplete");
                const auto squared_sum=detail::product(stats.sumD,stats.sumD);
                stats.total_numerator=detail::subtract(detail::product(stats.n,stats.sumD2),squared_sum);
                Wide action_squares;
                for(auto sum:stats.action_sumD)action_squares=detail::add(action_squares,detail::product(sum,sum));
                stats.action_numerator=detail::subtract(detail::scale(action_squares,4),squared_sum);
                const auto nN=stats.n*result.mask_count;stats.denominator=detail::product(nN,nN);
                const auto& numerator=options.policy==Policy::ActionVariance?stats.action_numerator:stats.total_numerator;
                stats.criterion_met=detail::scale(numerator,1000000)>=detail::scale(stats.denominator,static_cast<std::uint32_t>(options.threshold_ppm));
                stats.criterion_eligible=k>=minimum;
                stats.progress_met=best_set && (stats.best_leaf_priority<parent.P ||
                    (stats.best_leaf_priority==parent.P && stats.best_leaf_D<parent.D));
                stats.adequate=stats.criterion_met && (!options.require_improvement || stats.progress_met);
                ++result.complete_layers;++result.completed_k_histogram[k];
                if(stats.criterion_eligible){++result.criterion_windows;++result.tested_k_histogram[k];decision.selected_k=k;}
                decision.windows.push_back(stats);
                if(!stats.criterion_eligible)continue;
                if(positive){decision.reason="success";break;}
                if(options.policy==Policy::Fixed){decision.reason="fixed";break;}
                if(stats.adequate){decision.reason="variance";break;}
                if(k==maximum){decision.reason=maximum<options.max_k?"length-limit":"maximum-k";break;}
            }
            if(!decision.selected_k)throw std::logic_error("adaptive minimum window was not completed after preflight");
            decision.selected=true;++result.selected_k_histogram[decision.selected_k];trace(decision);
            auto path=std::make_shared<const Path>(Path{decision,parent.path});
            if(positive)consider(positive->state,path,decision.selected_k);
            if(result.found || stop_after_round)continue;
            if(options.advance==Advance::First){
                std::array<const Leaf*,4> best{};
                for(const auto&leaf:frontier){
                    const auto old=best[leaf.action];
                    if(!old || leaf.P<old->P || (leaf.P==old->P &&
                       (leaf.D<old->D || (leaf.D==old->D && detail::words_before(leaf.state,old->state)))))
                        best[leaf.action]=&leaf;
                }
                for(unsigned int action=0;action<4;++action){
                    if(!best[action] || !first_children[action])throw std::logic_error("adaptive lookahead lost a first action");
                    auto child=*first_children[action];auto key=detail::key(child.state);
                    retain({std::move(child.state),child.D,child.P,best[action]->D,best[action]->P,path,std::move(key)});
                }
            }else{
                for(auto&leaf:frontier){auto key=detail::key(leaf.state);
                    retain({std::move(leaf.state),leaf.D,leaf.P,leaf.D,leaf.P,path,std::move(key)});}
            }
        }
        if(result.found || stop_after_round)return finish();
        std::sort(ordinary.begin(),ordinary.end(),better);std::sort(diagonal.begin(),diagonal.end(),better);
        beam.clear();
        for(auto&node:ordinary)beam.push_back(std::move(node));
        for(auto&node:diagonal)beam.push_back(std::move(node));
    }
    result.length_capped=!beam.empty() && beam.front().state.first_word().size()==options.max_length;
    return finish();
}

template<class State>Result find_pair(State initial,const Options& options={})
{
    std::vector<State> starts;starts.push_back(std::move(initial));
    return find_pair(std::move(starts),options);
}
} // namespace hardpair::adaptive

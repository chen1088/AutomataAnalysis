#pragma once
// Experimental common-suffix distance preference for the bounded seed
// catalogue. Infinite common-tail distance NEVER prunes a full-joint branch.
#include "Family1JointSeeds.h"
#include "Family1JointPair.h"
#include "HardPairViability.h"
#include <algorithm>
#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <tuple>
#include <vector>

namespace family1 {
struct TailSeedScore {
    std::uint64_t infinite_count=0,maximum_finite=0,sum_finite=0,disagreement=0;
};
struct TailScoredSeed {
    std::string first,second;
    TailSeedScore score;
};
struct TailScoredSeedPlan {
    JointSeedPlan catalogue;
    std::vector<TailScoredSeed> selected;
    std::uint64_t candidates_scored=0,common_pair_states=0;
    unsigned int rank_mode=0;
};

class CompleteCommonTailTables {
public:
    CompleteCommonTailTables(const LargeGraph& graph,const std::shared_ptr<const ExactPackedProduct>& product)
        :graph_(graph),product_(product)
    {
        if(!product_ || product_->graph_key()!=graph.key())throw std::invalid_argument("common-tail graph/product mismatch");
        const auto masks=std::uint32_t{1}<<graph.size();
        tables_.reserve(masks);
        hardpair::PairMergeabilityLimits limits;
        limits.max_pair_states=static_cast<std::uint64_t>(graph.size())*graph.size();
        for(std::uint32_t mask=0;mask<masks;++mask){
            auto answer=hardpair::analyze_pair_mergeability(graph.size(),[&](std::uint32_t q,bool symbol){
                return graph.ports[q][static_cast<unsigned int>(symbol)^((mask>>q)&1U)];
            },limits);
            if(!answer.complete)throw std::logic_error("incomplete common-tail distance table");
            tables_.push_back(std::move(answer.distance));
        }
    }
    std::uint32_t distance(std::uint32_t mask,unsigned int first,unsigned int second)const{
        return tables_.at(mask).at(static_cast<std::size_t>(first)*graph_.size()+second);
    }
    TailSeedScore score(const ExactPackedProduct::Profile& first,const ExactPackedProduct::Profile& second)const{
        TailSeedScore result;result.disagreement=product_->disagreement_count(first,second);
        std::uint64_t scalar_d=0;
        for(std::uint32_t mask=0;mask<tables_.size();++mask){
            const auto left=product_->endpoint(first,mask),right=product_->endpoint(second,mask);
            scalar_d+=left!=right;
            const auto d=distance(mask,left,right);
            if(d==hardpair::PairMergeabilityResult::unreachable_distance)++result.infinite_count;
            else{result.maximum_finite=std::max<std::uint64_t>(result.maximum_finite,d);result.sum_finite+=d;}
        }
        if(scalar_d!=result.disagreement)throw std::logic_error("common-tail scoring lost original-mask multiplicity");
        return result;
    }
    std::uint64_t pair_states()const{return tables_.size()*static_cast<std::uint64_t>(graph_.size())*graph_.size();}
private:
    LargeGraph graph_;
    std::shared_ptr<const ExactPackedProduct> product_;
    std::vector<std::vector<std::uint32_t>> tables_;
};

inline TailScoredSeedPlan tail_scored_joint_seeds(const LargeGraph& graph,
    const std::shared_ptr<const ExactPackedProduct>& product,
    unsigned int depth,std::uint64_t words,std::uint64_t catalogue_size,
    std::uint64_t selected_size,unsigned int rank_mode,const JointSeedPlan* supplied_catalogue=nullptr)
{
    if(!selected_size || !catalogue_size || selected_size>catalogue_size || rank_mode>1)
        throw std::invalid_argument("tail-scored seeds require positive catalogue/start limits and rank mode0..1");
    CompleteCommonTailTables tables(graph,product);
    TailScoredSeedPlan result;result.rank_mode=rank_mode;result.common_pair_states=tables.pair_states();
    result.catalogue=supplied_catalogue ? *supplied_catalogue
                                      : joint_prefix_seeds(graph,depth,words,catalogue_size,8);
    using Channel=std::pair<unsigned int,unsigned int>;
    std::map<Channel,std::vector<TailScoredSeed>> groups;
    for(const auto&[first,second]:result.catalogue.pairs){
        unsigned int lcp=0;while(lcp<first.size() && first[lcp]==second[lcp])++lcp;
        groups[{static_cast<unsigned int>(first.size()),lcp}].push_back(
            {first,second,tables.score(product->evaluate(first),product->evaluate(second))});
        ++result.candidates_scored;
    }
    const auto before=[&](const TailScoredSeed&a,const TailScoredSeed&b){
        if(rank_mode==0)return std::tie(a.score.infinite_count,a.score.maximum_finite,a.score.sum_finite,a.score.disagreement,a.first,a.second)
                            <std::tie(b.score.infinite_count,b.score.maximum_finite,b.score.sum_finite,b.score.disagreement,b.first,b.second);
        return std::tie(a.score.infinite_count,a.score.sum_finite,a.score.maximum_finite,a.score.disagreement,a.first,a.second)
             < std::tie(b.score.infinite_count,b.score.sum_finite,b.score.maximum_finite,b.score.disagreement,b.first,b.second);
    };
    for(auto&[channel,candidates]:groups)std::sort(candidates.begin(),candidates.end(),before);
    std::map<Channel,std::size_t> next;
    bool progress=true;
    while(progress && result.selected.size()<selected_size){
        progress=false;
        for(auto&[channel,candidates]:groups){
            auto&i=next[channel];if(i==candidates.size())continue;
            result.selected.push_back(candidates[i++]);progress=true;
            if(result.selected.size()==selected_size)break;
        }
    }
    return result;
}
} // namespace family1

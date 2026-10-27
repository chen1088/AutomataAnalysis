#pragma once
// Experimental rolling-search objective: independent joint distance to the
// diagonal, aggregated over every original static mask.
#include "Family1JointPair.h"
#include <bit>
#include <cstdint>
#include <memory>
#include <queue>
#include <vector>

namespace family1 {
class RollingDistanceScoring {
public:
    RollingDistanceScoring(const std::shared_ptr<const ExactPackedProduct>& product, unsigned int mode)
        : product_(product), mode_(mode), m_(product->state_count()),
          width_(std::max(1U, static_cast<unsigned int>(std::bit_width(m_ - 1)))), blocks_((product->mask_count() + 63) / 64),
          distances_(m_ * m_, 1000000U),
          base_(product->full_mask_count() * m_ * m_ + 1)
    {
        if(mode_>2)throw std::invalid_argument("rolling distance score mode must be 0..2");
        auto graph = LargeGraph::from_key(product->graph_key());
        std::vector<std::vector<unsigned int>> predecessors(m_ * m_);
        for (unsigned int q=0;q<m_;++q)for(unsigned int r=0;r<m_;++r)
            for(unsigned int a=0;a<2;++a)for(unsigned int b=0;b<2;++b)
                predecessors[graph.ports[q][a]*m_+graph.ports[r][b]].push_back(q*m_+r);
        std::queue<unsigned int> frontier;
        for(unsigned int q=0;q<m_;++q){distances_[q*m_+q]=0;frontier.push(q*m_+q);}
        while(!frontier.empty()){
            auto at=frontier.front();frontier.pop();
            for(auto before:predecessors[at])if(distances_[before]>distances_[at]+1){
                distances_[before]=distances_[at]+1;frontier.push(before);
            }
        }
    }

    std::uint64_t score(const JointPairState& state) const
    {
        if(state.product().get()!=product_.get())throw std::invalid_argument("rolling distance product differs");
        const auto& left=state.left_profile();const auto& right=state.right_profile();
        std::uint64_t sum=0, maximum=0;
        const auto multiplicity=product_->full_mask_count()/product_->mask_count();
        std::vector<std::uint64_t> lm(m_),rm(m_);
        for(unsigned int block=0;block<blocks_;++block){
            const auto active=std::min(64U,product_->mask_count()-64*block);
            const auto valid=active==64?~std::uint64_t{0}:(std::uint64_t{1}<<active)-1;
            for(unsigned int q=0;q<m_;++q){
                lm[q]=rm[q]=valid;
                for(unsigned int bit=0;bit<width_;++bit){
                    const auto lp=left[bit*blocks_+block],rp=right[bit*blocks_+block];
                    lm[q]&=(q&(1U<<bit))?lp:~lp;
                    rm[q]&=(q&(1U<<bit))?rp:~rp;
                }
            }
            for(unsigned int q=0;q<m_;++q)for(unsigned int r=0;r<m_;++r){
                const auto count=std::popcount(lm[q]&rm[r]);
                if(count){sum+=count*multiplicity*distances_[q*m_+r];maximum=std::max<std::uint64_t>(maximum,distances_[q*m_+r]);}
            }
        }
        if(maximum>=1000000U)return UINT64_MAX;
        if(mode_==0)return sum*base_+maximum; // sum, then maximum, then D
        if(mode_==1)return maximum*base_+sum; // maximum, then sum, then D
        return state.priority_remaining_count()*base_+sum; // P, then distance sum, then D
    }
private:
    std::shared_ptr<const ExactPackedProduct> product_;
    unsigned int mode_,m_,width_,blocks_;
    std::vector<unsigned int> distances_;
    std::uint64_t base_;
};

class RollingDistancePairState {
public:
    RollingDistancePairState(std::shared_ptr<const ExactPackedProduct> product,unsigned int m,
                            std::shared_ptr<const ExactPackedProduct::MaskSelection> selector,unsigned int mode)
        : state_(product,m,selector), scorer_(std::make_shared<RollingDistanceScoring>(product,mode)),
          score_(scorer_->score(state_)) {}
    RollingDistancePairState(std::shared_ptr<const ExactPackedProduct> product,std::string first,std::string second,
                            std::shared_ptr<const ExactPackedProduct::MaskSelection> selector,unsigned int mode)
        : state_(product,std::move(first),std::move(second),selector),scorer_(std::make_shared<RollingDistanceScoring>(product,mode)),
          score_(scorer_->score(state_)) {}
    RollingDistancePairState append_pair(bool first,bool second)const{
        return RollingDistancePairState(state_.append_pair(first,second),scorer_);
    }
    std::uint64_t remaining_count()const{return state_.remaining_count();}
    std::uint64_t priority_remaining_count()const{return score_;}
    std::uint64_t mask_count()const{return state_.mask_count();}
    bool distinct()const{return state_.distinct();}
    const std::string& first_word()const{return state_.first_word();}
    const std::string& second_word()const{return state_.second_word();}
    std::string state_key()const{return state_.state_key();}
private:
    RollingDistancePairState(JointPairState state,std::shared_ptr<const RollingDistanceScoring> scorer)
        :state_(std::move(state)),scorer_(std::move(scorer)),score_(scorer_->score(state_)){}
    JointPairState state_;
    std::shared_ptr<const RollingDistanceScoring> scorer_;
    std::uint64_t score_;
};
} // namespace family1

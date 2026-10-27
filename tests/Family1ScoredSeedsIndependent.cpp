#include "Family1ScoredSeeds.h"
#include "Family1LargeEnumerator.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

namespace {
using Seed=family1::ScoredSeed;
struct Reference {
    std::vector<Seed> selected;
    std::vector<std::uint64_t> available{0};
    std::vector<unsigned int> masks;
    std::uint64_t scalar_word_masks=0, scalar_pair_masks=0;
};
std::string word(unsigned int value,unsigned int length){
    std::string result;
    for(unsigned int at=0;at<length;++at)result+=((value>>(length-1-at))&1U)?'1':'0';
    return result;
}
unsigned int endpoint(const family1::LargeGraph& graph,unsigned int mask,const std::string& input){
    unsigned int q=0;
    for(char c:input)q=graph.ports[q][(c-'0')^((mask>>q)&1U)];
    return q;
}
std::vector<unsigned int> permutation_masks(const family1::LargeGraph& graph){
    std::vector<unsigned int> result;
    for(unsigned int mask=0;mask<(1U<<graph.size());++mask){
        bool good=true;
        for(unsigned int input=0;input<2;++input){
            std::vector<unsigned int> counts(graph.size(),0);
            for(unsigned int q=0;q<graph.size();++q)
                ++counts[graph.ports[q][input^((mask>>q)&1U)]];
            if(std::any_of(counts.begin(),counts.end(),[](auto n){return n!=1;})){good=false;break;}
        }
        if(good)result.push_back(mask);
    }
    return result;
}
Reference reference(const family1::LargeGraph& graph,unsigned int depth){
    Reference result;result.masks=permutation_masks(graph);if(result.masks.size()>64)result.masks.resize(64);
    std::map<std::pair<unsigned int,unsigned int>,std::vector<Seed>> channels;
    for(unsigned int n=1;n<=depth;++n){
        const auto count=1U<<n;
        std::vector<std::string> words;
        std::vector<std::vector<unsigned int>> states(count);
        for(unsigned int id=0;id<count;++id){
            words.push_back(word(id,n));
            for(unsigned int mask=0;mask<(1U<<graph.size());++mask)
                states[id].push_back(endpoint(graph,mask,words.back()));
            result.scalar_word_masks+=1U<<graph.size();
        }
        std::uint64_t available=0;
        for(unsigned int a=0;a<count;++a)for(unsigned int b=a+1;b<count;++b){
            if(std::any_of(result.masks.begin(),result.masks.end(),[&](auto mask){return states[a][mask]!=states[b][mask];}))continue;
            ++available;
            unsigned int d=0,lcp=0;
            for(unsigned int mask=0;mask<(1U<<graph.size());++mask)d+=states[a][mask]!=states[b][mask];
            result.scalar_pair_masks+=1U<<graph.size();
            while(words[a][lcp]==words[b][lcp])++lcp;
            channels[{n,lcp}].push_back({words[a],words[b],d});
        }
        result.available.push_back(available);
    }
    for(auto& [channel,seeds]:channels)
        std::sort(seeds.begin(),seeds.end(),[](const auto&a,const auto&b){
            return std::tie(a.disagreement,a.first,a.second)<std::tie(b.disagreement,b.first,b.second);
        });
    bool progress=true;
    std::map<std::pair<unsigned int,unsigned int>,std::size_t> positions;
    while(progress){
        progress=false;
        for(auto&[channel,seeds]:channels){
            auto& index=positions[channel];
            if(index<seeds.size()){result.selected.push_back(seeds[index++]);progress=true;}
        }
    }
    return result;
}
void require(bool value,const std::string& reason){if(!value)throw std::runtime_error(reason);}
bool same(const Seed&a,const Seed&b){return a.first==b.first&&a.second==b.second&&a.disagreement==b.disagreement;}
void equal(const family1::ScoredSeedPlan&a,const family1::ScoredSeedPlan&b){
    require(a.selected.size()==b.selected.size(),"repeat selected size");
    for(std::size_t i=0;i<a.selected.size();++i)require(same(a.selected[i],b.selected[i]),"repeat seed differs");
    require(a.candidates_scored==b.candidates_scored&&a.catalogue.words_evaluated==b.catalogue.words_evaluated
      &&a.catalogue.completed_depth==b.catalogue.completed_depth&&a.catalogue.pair_capped==b.catalogue.pair_capped
      &&a.catalogue.word_capped==b.catalogue.word_capped,"repeat counters differ");
}
void validate_selected(const family1::LargeGraph&graph,const Reference&ref,const family1::ScoredSeedPlan&plan){
    std::set<std::pair<std::string,std::string>> seen;
    for(const auto& seed:plan.selected){
        require(!seed.first.empty()&&seed.first.size()==seed.second.size()&&seed.first<seed.second,"pair canonical order");
        require(seen.emplace(seed.first,seed.second).second,"duplicate selected pair");
        unsigned int d=0;
        for(unsigned int mask=0;mask<(1U<<graph.size());++mask){
            const auto a=endpoint(graph,mask,seed.first),b=endpoint(graph,mask,seed.second);
            d+=a!=b;
            if(std::find(ref.masks.begin(),ref.masks.end(),mask)!=ref.masks.end())
                require(a==b,"noncompatible selected pair");
        }
        require(d==seed.disagreement,"full original-mask D differs");
    }
}
}
int main(int argc,char**argv){
    try{
        if(argc!=1&&argc!=3)throw std::runtime_error("[canonical-keys output-json]; no arguments enumerates every class through m4");
        std::vector<family1::LargeGraph> cases;
        if(argc==3){
            std::ifstream input(argv[1]);std::string key;
            require(input.good(),"missing canonical key input");
            while(input>>key)cases.push_back(family1::LargeGraph::from_key(key));
        }else{
            for(unsigned int m=1;m<=4;++m)
                require(family1::LargeEnumerator(m).enumerate([&](const auto& graph){cases.push_back(graph);return true;}),
                        "small graph enumeration incomplete");
            require(cases.size()==742,"wrong complete small-universe count");
        }
        const auto small=cases.size();
        cases.push_back(family1::LargeGraph::from_key("01020003040501060003020705060407"));
        std::vector<family1::LargeGraph::Row> cycle;
        for(unsigned int q=0;q<8;++q)cycle.push_back({(q+1)%8,(q+1)%8});
        cases.emplace_back(cycle);
        cases.emplace_back(std::vector<family1::LargeGraph::Row>{{1,2},{3,3},{1,2},{4,4},{5,5},{6,6},{7,7},{0,0}});
        // Sixteen permutation masks fit in 48 packed bits at state width3.
        std::vector<family1::LargeGraph::Row> sixteen;
        for(unsigned int q=0;q<8;++q){auto group=((q/2+1)%4)*2;sixteen.push_back({group,group+1});}
        cases.emplace_back(sixteen);
        std::uint64_t pair_checks=0,word_masks=0,pair_masks=0,bounded=0,fallbacks=0;
        std::map<unsigned int,unsigned int> widths;
        for(const auto& graph:cases){
            auto product=std::make_shared<family1::ExactPackedProduct>(graph);
            auto ref=reference(graph,6);
            auto plan=family1::fast_scored_joint_seeds(graph,product,6,64,65536,65536);
            require(plan.catalogue.completed_depth==6,"complete word depth");
            require(!plan.catalogue.word_capped&&!plan.catalogue.pair_capped,"unlimited catalogue unexpectedly capped");
            require(plan.selected.size()==ref.selected.size(),"complete compatible pair missing/extra");
            require(plan.candidates_scored==ref.selected.size(),"candidate count differs");
            require(plan.catalogue.permutation_coordinates==ref.masks.size(),"coordinate count differs");
            for(std::size_t i=0;i<plan.selected.size();++i)require(same(plan.selected[i],ref.selected[i]),"complete channel order or D differs");
            validate_selected(graph,ref,plan);
            pair_checks+=plan.selected.size();word_masks+=ref.scalar_word_masks;pair_masks+=ref.scalar_pair_masks;
            const auto width=graph.size()==1?0:graph.size()<=2?1:graph.size()<=4?2:3;
            ++widths[width];
            const bool fallback=width*ref.masks.size()>64;
            fallbacks+=fallback;
            for(unsigned int limit:{1U,4U,16U}){
                auto a=family1::fast_scored_joint_seeds(graph,product,6,64,limit,limit);
                auto b=family1::fast_scored_joint_seeds(graph,product,6,64,limit,limit);
                equal(a,b);validate_selected(graph,ref,a);++bounded;
                std::uint64_t expected=0;
                if(!fallback)for(unsigned int n=1;n<=6;++n)expected+=std::min<std::uint64_t>(limit,ref.available[n]);
                else expected=std::min<std::uint64_t>(limit,ref.selected.size());
                require(a.candidates_scored==expected,"bounded catalogue count differs from declared backend rule");
                const bool capped=fallback?ref.selected.size()>limit:
                    std::any_of(ref.available.begin(),ref.available.end(),[&](auto n){return n>limit;});
                require(a.catalogue.pair_capped==capped,"pair cap flag differs");
            }
            for(unsigned int budget:{1U,2U,5U,63U}){
                auto a=family1::fast_scored_joint_seeds(graph,product,6,budget,65536,65536);
                unsigned int depth=0;while((1U<<(depth+1))<=budget&&depth<6)++depth;
                require(a.catalogue.completed_depth==depth&&a.catalogue.word_capped==(depth<6),"word cap/depth flag differs");
                require(a.catalogue.words_evaluated==(depth?((1U<<(depth+1))-2):0),"word layer accounting differs");
                ++bounded;
            }
        }
        unsigned int guards=0;
        auto expect_invalid=[&](auto call){
            try{call();}catch(const std::invalid_argument&){++guards;return;}
            throw std::runtime_error("invalid seed options were accepted");
        };
        auto one=family1::LargeGraph::from_key("0000"),two=family1::LargeGraph::from_key("00010001");
        auto one_product=std::make_shared<family1::ExactPackedProduct>(one);
        std::shared_ptr<const family1::ExactPackedProduct> missing;
        expect_invalid([&]{family1::fast_scored_joint_seeds(one,one_product,6,0,16,16);});
        expect_invalid([&]{family1::fast_scored_joint_seeds(one,one_product,6,64,0,1);});
        expect_invalid([&]{family1::fast_scored_joint_seeds(one,one_product,6,64,16,0);});
        expect_invalid([&]{family1::fast_scored_joint_seeds(one,one_product,6,64,1,2);});
        expect_invalid([&]{family1::fast_scored_joint_seeds(one,one_product,31,64,16,16);});
        expect_invalid([&]{family1::fast_scored_joint_seeds(one,missing,6,64,16,16);});
        expect_invalid([&]{family1::fast_scored_joint_seeds(two,one_product,6,64,16,16);});
        expect_invalid([&]{family1::scored_joint_seeds(one,missing,6,64,16,16);});
        expect_invalid([&]{family1::scored_joint_seeds(two,one_product,6,64,16,16);});
        expect_invalid([&]{family1::scored_joint_seeds(one,one_product,6,64,1,2);});
        std::ofstream output;
        if(argc==3)output.open(argv[2]);
        std::ostream& out=argc==3?static_cast<std::ostream&>(output):std::cout;
        out<<"{\"passed\":true,\"k\":null,\"scope\":\"independent complete scalar compatible-pair enumeration through word depth6\","
           <<"\"small_graphs\":"<<small<<",\"extra_m8_graphs\":4,\"total_graphs\":"<<cases.size()
           <<",\"complete_seed_pairs_compared\":"<<pair_checks<<",\"scalar_word_mask_evaluations\":"<<word_masks
           <<",\"scalar_pair_mask_comparisons\":"<<pair_masks<<",\"bounded_repeat_and_cap_checks\":"<<bounded
           <<",\"fallback_graphs\":"<<fallbacks<<",\"width0_graphs\":"<<widths[0]<<",\"width3_graphs\":"<<widths[3]
           <<",\"invalid_option_guard_checks\":"<<guards
           <<",\"fallback_budget_semantics\":\"legacy global pair cap; compact path has per-layer cap\"}\n";
        std::cout<<"passed "<<cases.size()<<" graphs, "<<pair_checks<<" complete seed pairs\n";
    }catch(const std::exception&error){std::cerr<<error.what()<<"\n";return 1;}
}

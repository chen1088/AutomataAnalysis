#pragma once
// Deterministic full endpoint-profile graph search across unequal word lengths.
// If p reaches q and a,b are cycles at q beginning with different letters,
// p+a+b and p+b+a are distinct equal-length hard words. k is not applicable.
#include "Family1ExactPacked.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <optional>
#include <queue>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

namespace family1::profile_cycles {
struct Options {
    std::uint32_t max_states = 262144, max_roots = 64, max_length = 80;
    std::uint64_t max_return_edges = 100000000;
};
struct Result {
    bool found = false, state_capped = false, return_capped = false;
    unsigned int length = 0, component_count = 0;
    std::uint64_t profiles = 0, graph_edges = 0, return_edges = 0, roots_tested = 0;
    std::string first, second, common_prefix, first_cycle, second_cycle;
    std::string method;
};
struct ProfileHash {
    std::size_t operator()(const ExactPackedProduct::Profile& profile) const {
        std::uint64_t h = 0x9e3779b97f4a7c15ULL;
        for (auto x : profile) {
            x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL;
            x ^= x >> 27; x *= 0x94d049bb133111ebULL; x ^= x >> 31;
            h ^= x + 0x9e3779b97f4a7c15ULL + (h << 6) + (h >> 2);
        }
        return static_cast<std::size_t>(h);
    }
};
inline Result find_pair(const LargeGraph& graph, const Options& options = {}) {
    if (!options.max_states || !options.max_roots || !options.max_length || !options.max_return_edges)
        throw std::invalid_argument("positive profile-cycle budgets required");
    constexpr auto absent = std::numeric_limits<std::uint32_t>::max();
    ExactPackedProduct product(graph);
    using Profile = ExactPackedProduct::Profile;
    struct Node {
        Profile profile;
        std::array<std::uint32_t,2> edge{absent,absent};
        std::uint32_t parent=absent, depth=0;
        char symbol='0';
    };
    std::vector<Node> nodes;
    nodes.reserve(options.max_states);
    nodes.push_back({product.evaluate("")});
    std::unordered_map<Profile,std::uint32_t,ProfileHash> ids;
    ids.reserve(2*options.max_states);ids.emplace(nodes[0].profile,0);
    Result result;
    auto word = [&](std::uint32_t q) {
        std::string value;
        while(nodes[q].parent!=absent){value.push_back(nodes[q].symbol);q=nodes[q].parent;}
        std::reverse(value.begin(),value.end());return value;
    };
    auto consider = [&](std::string first,std::string second,const std::string& method,
                        const std::string& prefix="",const std::string& a="",const std::string& b="") {
        if(first==second || first.size()!=second.size() || first.size()>options.max_length)return;
        if(first>second)std::swap(first,second);
        if(!result.found || first.size()<result.length || (first.size()==result.length
           && std::tie(first,second)<std::tie(result.first,result.second))){
            if(product.evaluate(first)!=product.evaluate(second))throw std::logic_error("invalid profile-cycle certificate");
            result.found=true;result.length=first.size();result.first=std::move(first);result.second=std::move(second);
            result.method=method;result.common_prefix=prefix;result.first_cycle=a;result.second_cycle=b;
        }
    };
    std::unordered_map<std::uint32_t,std::pair<std::uint32_t,unsigned int>> layer_arrivals;
    std::uint32_t arrival_depth=0;
    for(std::uint32_t head=0;head<nodes.size();++head){
        if(nodes[head].depth>=options.max_length)continue;
        if(nodes[head].depth!=arrival_depth){layer_arrivals.clear();arrival_depth=nodes[head].depth;}
        for(unsigned int bit=0;bit<2;++bit){
            auto profile=product.step(nodes[head].profile,bit);
            auto position=ids.find(profile);
            std::uint32_t target=absent;
            if(position!=ids.end()){
                target=position->second;
                if(nodes[target].depth==nodes[head].depth+1)
                    consider(word(head)+char('0'+bit),word(target),"same-depth-profile-collision");
            }else if(nodes.size()<options.max_states){
                target=static_cast<std::uint32_t>(nodes.size());
                auto depth=nodes[head].depth+1;
                ids.emplace(profile,target);
                nodes.push_back({std::move(profile),{absent,absent},head,depth,char('0'+bit)});
            }else result.state_capped=true;
            nodes[head].edge[bit]=target;
            if(target!=absent){
                auto [position,inserted]=layer_arrivals.emplace(target,std::pair{head,bit});
                if(!inserted)consider(word(head)+char('0'+bit),
                    word(position->second.first)+char('0'+position->second.second),
                    "canonical-prefix-layer-collision");
            }
            ++result.graph_edges;
        }
    }
    result.profiles=nodes.size();
    // Iterative Kosaraju decomposition of the completely stored edge subgraph.
    std::vector<std::vector<std::uint32_t>> reverse(nodes.size());
    for(std::uint32_t q=0;q<nodes.size();++q)
        for(auto next:nodes[q].edge)if(next!=absent)reverse[next].push_back(q);
    std::vector<unsigned char> seen(nodes.size(),0);
    std::vector<std::uint32_t> order;order.reserve(nodes.size());
    for(std::uint32_t root=0;root<nodes.size();++root)if(!seen[root]){
        std::vector<std::pair<std::uint32_t,unsigned int>> stack{{root,0}};seen[root]=1;
        while(!stack.empty()){
            auto& [q,which]=stack.back();
            if(which==2){order.push_back(q);stack.pop_back();continue;}
            auto next=nodes[q].edge[which++];
            if(next!=absent && !seen[next]){seen[next]=1;stack.push_back({next,0});}
        }
    }
    std::vector<std::uint32_t> component(nodes.size(),absent), sizes;
    while(!order.empty()){
        auto root=order.back();order.pop_back();if(component[root]!=absent)continue;
        auto id=static_cast<std::uint32_t>(sizes.size());
        std::vector<std::uint32_t> stack{root};component[root]=id;std::uint32_t size=0;
        while(!stack.empty()){
            auto q=stack.back();stack.pop_back();++size;
            for(auto prev:reverse[q])if(component[prev]==absent){component[prev]=id;stack.push_back(prev);}
        }
        sizes.push_back(size);
    }
    result.component_count=sizes.size();
    std::vector<std::uint32_t> roots;
    for(std::uint32_t q=0;q<nodes.size();++q)
        if(nodes[q].edge[0]!=absent && nodes[q].edge[1]!=absent
           && component[nodes[q].edge[0]]==component[q] && component[nodes[q].edge[1]]==component[q])
            roots.push_back(q);
    // BFS node IDs already order roots by shortest prefix, then lexical word.
    if(roots.size()>options.max_roots)roots.resize(options.max_roots);
    std::vector<std::uint32_t> marks(nodes.size(),0), parent(nodes.size()), depths(nodes.size());
    std::vector<unsigned char> symbol(nodes.size());
    std::uint32_t generation=0;
    auto return_path = [&](std::uint32_t start,std::uint32_t root,unsigned int depth_cap)->std::optional<std::string>{
        if(start==root)return std::string{};
        ++generation;std::vector<std::uint32_t> queue{start};marks[start]=generation;parent[start]=absent;depths[start]=0;
        for(std::size_t head=0;head<queue.size();++head){
            auto q=queue[head];if(depths[q]>=depth_cap)continue;
            for(unsigned int bit=0;bit<2;++bit){
                if(result.return_edges>=options.max_return_edges){result.return_capped=true;return {};}
                ++result.return_edges;
                auto next=nodes[q].edge[bit];
                if(next==absent || component[next]!=component[root] || marks[next]==generation)continue;
                marks[next]=generation;parent[next]=q;symbol[next]=bit;depths[next]=depths[q]+1;
                if(next==root){
                    std::string value;
                    while(next!=start){value.push_back('0'+symbol[next]);next=parent[next];}
                    std::reverse(value.begin(),value.end());return value;
                }
                queue.push_back(next);
            }
        }
        return {};
    };
    for(auto q:roots){
        if(result.return_capped)break;
        const auto cap=result.found?result.length:options.max_length;
        if(nodes[q].depth+2>cap)continue;
        ++result.roots_tested;
        auto zero=return_path(nodes[q].edge[0],q,cap-nodes[q].depth-2);
        if(!zero)continue;
        std::string a="0"+*zero;
        auto one=return_path(nodes[q].edge[1],q,cap-nodes[q].depth-a.size()-1);
        if(!one)continue;
        std::string b="1"+*one,prefix=word(q);
        consider(prefix+a+b,prefix+b+a,"noncommuting-profile-cycles",prefix,a,b);
    }
    return result;
}
}

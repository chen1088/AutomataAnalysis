#include "Family1TailScoredSeeds.h"
#include "Family1LargeEnumerator.h"
#include <algorithm>
#include <iostream>
#include <limits>
#include <queue>

static std::uint32_t reference_distance(const family1::LargeGraph& graph, unsigned int mask,
                                        unsigned int left, unsigned int right) {
    const auto m = graph.size();
    std::vector<std::uint32_t> distance(m*m, std::numeric_limits<std::uint32_t>::max());
    std::queue<unsigned int> todo; const auto initial = left*m+right;
    distance[initial]=0;todo.push(initial);
    while(!todo.empty()) {
        const auto code=todo.front();todo.pop();left=code/m;right=code%m;
        if(left==right)return distance[code];
        for(unsigned int x=0;x<2;++x) {
            const auto a=graph.ports[left][x^((mask>>left)&1U)];
            const auto b=graph.ports[right][x^((mask>>right)&1U)];
            const auto next=a*m+b;
            if(distance[next]!=std::numeric_limits<std::uint32_t>::max())continue;
            distance[next]=distance[code]+1;todo.push(next);
        }
    }
    return std::numeric_limits<std::uint32_t>::max();
}

int main() {
    try {
        std::vector<family1::LargeGraph> graphs;
        for(unsigned int m=1;m<=4;++m)
            if(!family1::LargeEnumerator(m).enumerate([&](const auto& graph){graphs.push_back(graph);return true;}))
                throw std::logic_error("small enumeration incomplete");
        graphs.push_back(family1::LargeGraph::from_key("01010202030304040505060607070707"));
        graphs.push_back(family1::LargeGraph::from_key("01010202030304040505060607070000"));
        graphs.push_back(family1::LargeGraph::from_key("01020003040501060003020705060407"));
        std::uint64_t checked=0,aggregates=0;
        const std::vector<std::pair<std::string,std::string>> words{
            {"",""},{"0","1"},{"00","11"},{"01","10"},{"0011","1100"},{"01010","10101"}};
        for(const auto& graph:graphs) {
            auto product=std::make_shared<const family1::ExactPackedProduct>(graph);
            family1::CompleteCommonTailTables tables(graph,product);
            const auto m=graph.size();
            std::vector<std::vector<std::uint32_t>> distances(1U<<m,std::vector<std::uint32_t>(m*m));
            for(unsigned int mask=0;mask<(1U<<m);++mask)
                for(unsigned int a=0;a<m;++a)for(unsigned int b=0;b<m;++b) {
                    auto d=reference_distance(graph,mask,a,b);distances[mask][a*m+b]=d;
                    if(d!=tables.distance(mask,a,b))throw std::logic_error("common-distance mismatch");
                    ++checked;
                }
            for(const auto&[first,second]:words) {
                auto actual=tables.score(product->evaluate(first),product->evaluate(second));
                family1::TailSeedScore expected;
                for(unsigned int mask=0;mask<(1U<<m);++mask) {
                    unsigned int a=0,b=0;
                    for(char x:first)a=graph.ports[a][(x-'0')^((mask>>a)&1U)];
                    for(char x:second)b=graph.ports[b][(x-'0')^((mask>>b)&1U)];
                    expected.disagreement+=a!=b;
                    const auto d=distances[mask][a*m+b];
                    if(d==std::numeric_limits<std::uint32_t>::max())++expected.infinite_count;
                    else {expected.maximum_finite=std::max<std::uint64_t>(expected.maximum_finite,d);expected.sum_finite+=d;}
                }
                if(std::tie(actual.infinite_count,actual.maximum_finite,actual.sum_finite,actual.disagreement)
                    !=std::tie(expected.infinite_count,expected.maximum_finite,expected.sum_finite,expected.disagreement))
                    throw std::logic_error("common-score aggregation mismatch");
                ++aggregates;
            }
        }
        std::cout<<"common-distance forward reference passed on "<<graphs.size()<<" graphs, "
                 <<checked<<" pair-mask distances and "<<aggregates<<" full-mask score aggregates\n";
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}

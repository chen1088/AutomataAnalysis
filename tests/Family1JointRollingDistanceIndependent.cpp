#include "Family1JointRollingDistance.h"
#include <array>
#include <fstream>
#include <iostream>
#include <queue>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc,char**argv){
 try{
  if(argc!=2)throw std::runtime_error("supply graph-only key list");
  std::ifstream input(argv[1]);std::string key;
  std::uint64_t checked=0,scalar_checks=0;
  while(input>>key){
   const auto graph=family1::LargeGraph::from_key(key);const auto m=graph.size(),n=1U<<m;
   auto product=std::make_shared<family1::ExactPackedProduct>(graph);
   auto selector=family1::permutation_priority_selection(product,graph);
   std::vector<std::vector<unsigned int>> distance(n,std::vector<unsigned int>(m*m,1000000));
   std::vector<bool> permutation(n,true);
   for(unsigned int mask=0;mask<n;++mask){
    for(unsigned int a=0;a<2;++a){
     std::vector<bool> seen(m);
     for(unsigned int q=0;q<m;++q){auto t=graph.ports[q][a^((mask>>q)&1U)];if(seen[t])permutation[mask]=false;seen[t]=true;}
    }
    std::vector<std::vector<unsigned int>> pred(m*m);
    for(unsigned int q=0;q<m;++q)for(unsigned int r=0;r<m;++r)
     for(unsigned int a=0;a<2;++a)for(unsigned int b=0;b<2;++b){
      auto q1=graph.ports[q][a^((mask>>q)&1U)],r1=graph.ports[r][b^((mask>>r)&1U)];
      pred[q1*m+r1].push_back(q*m+r);
     }
    std::queue<unsigned int> todo;
    for(unsigned int q=0;q<m;++q){distance[mask][q*m+q]=0;todo.push(q*m+q);}
    while(!todo.empty()){auto at=todo.front();todo.pop();for(auto before:pred[at])if(distance[mask][before]>distance[mask][at]+1){
     distance[mask][before]=distance[mask][at]+1;todo.push(before);
    }}
   }
   std::vector<family1::RollingDistanceScoring> scorers;
   std::vector<family1::RollingDistancePairState> wrappers;
   for(unsigned int mode=0;mode<3;++mode){scorers.emplace_back(product,mode);wrappers.emplace_back(product,m,selector,mode);}
   family1::JointPairState root(product,m,selector);
   std::vector<std::array<unsigned int,2>> scalar(n,{0,0});
   auto visit=[&](auto&&self,const family1::JointPairState&state,const auto&wrapped,const auto&ends,unsigned int depth)->void{
    std::uint64_t sum=0,maximum=0,p=0,d=0;
    for(unsigned int mask=0;mask<n;++mask){
     auto delta=distance[mask][ends[mask][0]*m+ends[mask][1]];
     sum+=delta;maximum=std::max<std::uint64_t>(maximum,delta);
     d+=ends[mask][0]!=ends[mask][1];p+=permutation[mask]&&(ends[mask][0]!=ends[mask][1]);
    }
    if(state.remaining_count()!=d || state.priority_remaining_count()!=p)throw std::logic_error("packed endpoint counts differ");
    const std::uint64_t base=static_cast<std::uint64_t>(n)*m*m+1;
    std::array<std::uint64_t,3> expected{sum*base+maximum,maximum*base+sum,p*base+sum};
    if(maximum>=1000000U)expected.fill(UINT64_MAX);
    for(unsigned int mode=0;mode<3;++mode)
     if(scorers[mode].score(state)!=expected[mode] || wrapped[mode].priority_remaining_count()!=expected[mode])
      throw std::logic_error("distance aggregation differs from independent scalar reverse BFS");
    ++checked;scalar_checks+=n;
    if(depth==4)return;
    for(unsigned int symbol=0;symbol<4;++symbol){
     auto next=ends;auto nextwrapped=wrapped;
     for(auto&entry:nextwrapped)entry=entry.append_pair(symbol&2,symbol&1);
     for(unsigned int mask=0;mask<n;++mask){
      next[mask][0]=graph.ports[next[mask][0]][((symbol>>1)&1U)^((mask>>next[mask][0])&1U)];
      next[mask][1]=graph.ports[next[mask][1]][(symbol&1U)^((mask>>next[mask][1])&1U)];
     }
     self(self,state.append_pair(symbol&2,symbol&1),nextwrapped,next,depth+1);
    }
   };
   visit(visit,root,wrappers,scalar,0);
  }
  std::cout<<"{\"passed\":true,\"paired_states\":"<<checked<<",\"scalar_masks\":"<<scalar_checks<<"}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}

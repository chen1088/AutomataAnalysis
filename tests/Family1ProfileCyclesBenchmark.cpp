#include "Family1ProfileCycles.h"
#include <chrono>
#include <fstream>
#include <iostream>
#include <string>
int main(int argc,char**argv){
    if(argc!=6){std::cerr<<"keys states roots return-edges output\n";return 2;}
    family1::profile_cycles::Options options;
    options.max_states=std::stoul(argv[2]);options.max_roots=std::stoul(argv[3]);options.max_return_edges=std::stoull(argv[4]);
    std::ifstream input(argv[1]);std::ofstream out(argv[5]);std::string key;
    while(input>>key){
        auto graph=family1::LargeGraph::from_key(key);auto start=std::chrono::steady_clock::now();
        auto result=family1::profile_cycles::find_pair(graph,options);
        std::vector<unsigned int> trace(result.found?result.length+1:0);
        if(result.found)for(unsigned int mask=0;mask<(1U<<graph.size());++mask){
            unsigned int a=0,b=0;
            for(unsigned int i=0;i<result.length;++i){
                a=graph.ports[a][(result.first[i]-'0')^((mask>>a)&1U)];
                b=graph.ports[b][(result.second[i]-'0')^((mask>>b)&1U)];
                trace[i+1]+=a!=b;
            }
            if(a!=b)throw std::logic_error("scalar profile-cycle replay failed");
        }
        out<<"{\"m\":"<<graph.size()<<",\"key\":\""<<key<<"\",\"k\":null,\"method\":\""<<result.method
           <<"\",\"max_states\":"<<options.max_states<<",\"max_roots\":"<<options.max_roots
           <<",\"max_return_edges\":"<<options.max_return_edges<<",\"upper_bound\":";
        if(result.found)out<<result.length;else out<<"null";
        out<<",\"witness\":[\""<<result.first<<"\",\""<<result.second<<"\"],\"profiles\":"<<result.profiles
           <<",\"graph_edges\":"<<result.graph_edges<<",\"return_edges\":"<<result.return_edges
           <<",\"roots_tested\":"<<result.roots_tested<<",\"components\":"<<result.component_count
           <<",\"state_capped\":"<<result.state_capped<<",\"return_capped\":"<<result.return_capped
           <<",\"prefix\":\""<<result.common_prefix<<"\",\"first_cycle\":\""<<result.first_cycle
           <<"\",\"second_cycle\":\""<<result.second_cycle<<"\",\"Dtrace\":[";
        for(unsigned int i=0;i<trace.size();++i){if(i)out<<',';out<<trace[i];}
        out<<"],\"seconds\":"<<std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()<<"}\n";out.flush();
        std::cerr<<key<<" profiles="<<result.profiles<<" upper="<<result.length<<"\n";
    }
}

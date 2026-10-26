// Independent diagnostic only: scalar static-mask simulation followed by one
// ordinary DFA pair BFS per residual coordinate. No production headers used.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Delta = std::array<std::array<unsigned int,2>,20>;
using Pair = std::array<unsigned int,2>;
void check(bool value,const char* message) { if(!value) throw std::runtime_error(message); }
struct Local {
    bool mergeable=false; unsigned int distance=0; std::string word;
    std::vector<Pair> visited;
};
Local local_bfs(const Delta& delta,unsigned int m,unsigned int first,unsigned int second)
{
    if(first>second) std::swap(first,second);
    struct Node { unsigned int a,b,depth; int parent; char letter; };
    std::vector<Node> nodes{{first,second,0,-1,'0'}};
    std::array<bool,400> seen{}; seen[first*m+second]=true;
    Local result;
    for(std::size_t head=0;head<nodes.size();++head) {
        const auto node=nodes[head];
        if(node.a==node.b) {
            result.mergeable=true; result.distance=node.depth;
            for(auto at=int(head);nodes[at].parent>=0;at=nodes[at].parent) result.word+=nodes[at].letter;
            std::reverse(result.word.begin(),result.word.end());
            break;
        }
        for(unsigned int x=0;x<2;++x) {
            auto a=delta[node.a][x],b=delta[node.b][x];if(a>b)std::swap(a,b);
            if(!seen[a*m+b]) { seen[a*m+b]=true; nodes.push_back({a,b,node.depth+1,int(head),char('0'+x)}); }
        }
    }
    for(const auto& n:nodes) result.visited.push_back({n.a,n.b});
    if(result.mergeable) {
        auto a=first,b=second;
        for(char c:result.word) {a=delta[a][c-'0'];b=delta[b][c-'0'];}
        check(a==b && result.word.size()==result.distance,"local shortest witness fails scalar replay");
    } else {
        // Negative result has a compact closed-set certificate, independently
        // checked before publication and exported for external replay.
        for(const auto& p:result.visited) {
            check(p[0]!=p[1],"unmergeable certificate contains diagonal");
            for(unsigned int x=0;x<2;++x) {
                auto a=delta[p[0]][x],b=delta[p[1]][x];if(a>b)std::swap(a,b);
                check(seen[a*m+b],"unmergeable pair set is not transition closed");
            }
        }
    }
    return result;
}
unsigned int endpoint(const Delta& delta,const std::string& word,unsigned int root=0)
{
    for(char c:word) root=delta[root][c-'0'];return root;
}
void self_test()
{
    Delta d{};d[0]={0,1};d[1]={1,0};
    check(!local_bfs(d,2,0,1).mergeable,"permutation mismatch became mergeable");
    d[0]={0,0};d[1]={0,1};auto a=local_bfs(d,2,0,1);
    check(a.mergeable&&a.distance==1&&a.word=="0","one-step pair fixture wrong");
    d[0]={1,1};d[1]={2,2};d[2]={2,2};a=local_bfs(d,3,0,1);
    check(a.mergeable&&a.distance==2,"plateau pair fixture wrong");
}
std::uint64_t number(const std::string& text)
{
    check(!text.empty()&&text.find_first_not_of("0123456789")==std::string::npos,"invalid nonnegative integer");
    return std::stoull(text);
}
struct Record {std::uint32_t mask;unsigned int a,b;bool permutation;Local local;};
}
int main(int argc,char**argv)
{
    try {
        self_test();
        std::string key,first,second;std::filesystem::path output;
        std::uint64_t expected=~std::uint64_t{0};
        for(int i=1;i<argc;++i) {
            const std::string flag=argv[i];
            if(flag=="--self-test"){std::cout<<"{\"self_test_passed\":true}\n";return 0;}
            check(++i<argc,"missing option value");const std::string value=argv[i];
            if(flag=="--graph")key=value;else if(flag=="--first")first=value;
            else if(flag=="--second")second=value;else if(flag=="--out")output=value;
            else if(flag=="--expected-remaining")expected=number(value);else throw std::runtime_error("unknown option");
        }
        check(!key.empty()&&key.size()%4==0&&key.find_first_not_of("0123456789")==std::string::npos,"invalid fixed-width graph key");
        const auto m=static_cast<unsigned int>(key.size()/4);check(m>=1&&m<=20,"requires1..20 vertices");
        check(!first.empty()&&first!=second&&first.size()==second.size()&&first.find_first_not_of("01")==std::string::npos&&second.find_first_not_of("01")==std::string::npos,"requires distinct equal-length positive binary words");
        check(!output.empty()&&!std::filesystem::exists(output),"output must be a new file");
        Delta table{};
        for(unsigned int s=0;s<m;++s)for(unsigned int p=0;p<2;++p){table[s][p]=std::stoul(key.substr(4*s+2*p,2));check(table[s][p]<m,"target out of range");}
        std::array<bool,20> reached{};std::vector<unsigned int> todo{0};reached[0]=true;
        for(std::size_t h=0;h<todo.size();++h)for(auto target:table[todo[h]])if(!reached[target]){reached[target]=true;todo.push_back(target);}
        check(todo.size()==m,"seed not root-accessible");
        const auto started=std::chrono::steady_clock::now();
        std::vector<Record> records;std::map<unsigned int,std::uint64_t> histogram;
        std::uint64_t merged=0,unmergeable=0,permutations=0,permutation_mismatches=0,pair_states=0;
        for(std::uint32_t mask=0;mask<(1U<<m);++mask) {
            Delta delta{};std::array<std::uint32_t,2> targets{};bool permutation=true;
            for(unsigned int s=0;s<m;++s)for(unsigned int x=0;x<2;++x){
                auto t=table[s][x^((mask>>s)&1U)];delta[s][x]=t;
                if(targets[x]&(1U<<t))permutation=false;targets[x]|=1U<<t;
            }
            permutations+=permutation;
            auto a=endpoint(delta,first),b=endpoint(delta,second);
            if(a==b){++merged;continue;}
            permutation_mismatches+=permutation;
            auto local=local_bfs(delta,m,a,b);pair_states+=local.visited.size();
            if(local.mergeable)++histogram[local.distance];else++unmergeable;
            records.push_back({mask,a,b,permutation,std::move(local)});
        }
        check(expected==~std::uint64_t{0}||records.size()==expected,"unexpected residual coordinate count");
        const auto seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
        std::ostringstream text;text<<"{\"schema\":1,\"method\":\"independent-scalar-static-masks-and-single-coordinate-pair-BFS\",\"key\":\""<<key<<"\",\"m\":"<<m
            <<",\"first_word\":\""<<first<<"\",\"second_word\":\""<<second<<"\",\"word_length\":"<<first.size()
            <<",\"masks_enumerated\":"<<(1U<<m)<<",\"merged_count\":"<<merged<<",\"remaining_count\":"<<records.size()
            <<",\"individually_mergeable\":"<<records.size()-unmergeable<<",\"individually_unmergeable\":"<<unmergeable
            <<",\"permutation_mask_count\":"<<permutations<<",\"permutation_mismatches\":"<<permutation_mismatches
            <<",\"local_pair_states_explored\":"<<pair_states<<",\"distance_histogram\":{";
        bool comma=false;for(const auto& [distance,count]:histogram){if(comma)text<<',';comma=true;text<<'"'<<distance<<"\":"<<count;}
        text<<"},\"residual_coordinates\":[";comma=false;
        for(const auto& r:records){if(comma)text<<',';comma=true;
            text<<"{\"mask\":"<<r.mask<<",\"first_state\":"<<r.a<<",\"second_state\":"<<r.b
                <<",\"both_letters_permutations\":"<<(r.permutation?"true":"false")<<",\"mergeable\":"<<(r.local.mergeable?"true":"false")<<",\"shortest_local_distance\":";
            if(r.local.mergeable)text<<r.local.distance;else text<<"null";
            text<<",\"shortest_local_suffix\":";if(r.local.mergeable)text<<'"'<<r.local.word<<'"';else text<<"null";
            text<<",\"pair_states_seen\":"<<r.local.visited.size()<<",\"closed_unmerged_pair_set\":";
            if(r.local.mergeable)text<<"null";else{ text<<'[';bool sep=false;for(const auto&p:r.local.visited){if(sep)text<<',';sep=true;text<<'['<<p[0]<<','<<p[1]<<']';}text<<']';}
            text<<'}';
        }
        text<<"],\"all_local_searches_complete\":true,\"seconds\":"<<seconds
            <<",\"any_unmergeable_coordinate_forbids_a_common_suffix\":"<<(unmergeable?"true":"false")
            <<",\"all_individually_mergeable_does_not_certify_joint_completion\":true,\"global_H_claimed\":false}\n";
        if(!output.parent_path().empty())std::filesystem::create_directories(output.parent_path());
        std::ofstream file(output,std::ios::binary);check(bool(file),"cannot write output");file<<text.str();file.close();
        std::cout<<"{\"remaining\":"<<records.size()<<",\"mergeable\":"<<records.size()-unmergeable<<",\"unmergeable\":"<<unmergeable
            <<",\"permutation_mismatches\":"<<permutation_mismatches<<",\"seconds\":"<<seconds<<"}\n";
        return 0;
    }catch(const std::exception&error){std::cerr<<"ResidualPairDiagnostic: "<<error.what()<<'\n';return 1;}
}

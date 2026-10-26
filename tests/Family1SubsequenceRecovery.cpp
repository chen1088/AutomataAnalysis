// Independent experiment: exhaustive distinct fixed-length subsequences of
// automatically constructed near-pairs. No production headers or saved pairs.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
struct ProfileHash {
    unsigned bits=64;
    std::size_t operator()(const std::string& value) const {
        std::uint64_t h=1469598103934665603ull;
        for (unsigned char x:value) {h^=x;h*=1099511628211ull;}
        return std::size_t(bits==64?h:(bits==0?0:h&((1ull<<bits)-1)));
    }
};
struct Result {
    std::uint64_t nodes=0, generations=0;
    std::vector<std::uint64_t> source_counts;
    std::vector<bool> source_complete;
    std::vector<std::array<std::string,2>> witnesses;
    std::unordered_set<std::string> words;
    std::unordered_set<std::string,ProfileHash> colliding;
    std::unordered_map<std::string,std::string,ProfileHash> profiles;
    bool complete=true;
    std::string cap_reason;
    explicit Result(unsigned bits):colliding(0,ProfileHash{bits}),profiles(0,ProfileHash{bits}){}
};
struct Search {
    unsigned m,target,max_witnesses=16;
    std::uint64_t max_nodes=10000000,max_profiles=1000000,max_words=1000000;
    std::vector<std::array<unsigned,2>> table;
    std::vector<std::array<unsigned char,2>> delta;
    Result result;
    Search(std::string key,unsigned length,unsigned hash_bits):target(length),result(hash_bits) {
        require(key.size()%4==0,"Malformed graph key");m=unsigned(key.size()/4);
        require(m>=1 && m<=10,"Independent experiment supports one to ten states");
        for(unsigned s=0;s<m;++s) {
            std::array<unsigned,2> row{};
            for(unsigned x=0;x<2;++x) {
                auto value=key.substr(4*s+2*x,2);
                require(value.find_first_not_of("0123456789")==std::string::npos,"Non-digit key");
                row[x]=unsigned(std::stoul(value)); require(row[x]<m,"Graph target out of range");
            }
            table.push_back(row);
        }
        delta.resize((1ull<<m)*m);
        for(unsigned mask=0;mask<(1u<<m);++mask)for(unsigned s=0;s<m;++s)for(unsigned x=0;x<2;++x)
            delta[mask*m+s][x]=static_cast<unsigned char>(table[s][x^((mask>>s)&1)]);
    }
    unsigned endpoint(unsigned mask,const std::string& word) const {
        unsigned s=0;
        for(char x:word)s=table[s][unsigned(x-'0')^((mask>>s)&1)];
        return s;
    }
    void emit(const std::string& word,const std::string& profile,unsigned source) {
        ++result.generations;++result.source_counts[source];
        if(result.words.count(word))return;
        if(result.words.size()>=max_words){result.complete=false;result.cap_reason="distinct-word-limit";return;}
        auto existing=result.profiles.find(profile);
        if(existing==result.profiles.end() && result.profiles.size()>=max_profiles) {
            result.complete=false;result.cap_reason="complete-profile-limit";return;
        }
        result.words.insert(word);
        auto [it,inserted]=result.profiles.emplace(profile,word);
        if(!inserted && it->second!=word) {
            result.colliding.insert(profile);
            if(result.witnesses.size()<max_witnesses) {
                for(unsigned mask=0;mask<(1u<<m);++mask)
                    require(endpoint(mask,it->second)==endpoint(mask,word),"Independent scalar replay failed");
                result.witnesses.push_back({it->second,word});
            }
        }
    }
    void enumerate(const std::string& source,unsigned source_id) {
        require(source.find_first_not_of("01")==std::string::npos,"Nonbinary source word");
        require(source.size()>=target && source.size()<=256,"Invalid source length");
        if(result.source_counts.size()<=source_id)result.source_counts.resize(source_id+1,0);
        if(result.source_complete.size()<=source_id)result.source_complete.resize(source_id+1,false);
        std::vector<std::array<std::size_t,2>> next(source.size()+1);
        next.back()={source.size(),source.size()};
        for(std::size_t at=source.size();at>0;--at) {
            next[at-1]=next[at];next[at-1][source[at-1]-'0']=at-1;
        }
        std::string word;word.reserve(target);
        std::function<void(std::size_t,unsigned,const std::string&)> visit;
        visit=[&](std::size_t position,unsigned remaining,const std::string& profile) {
            if(!result.complete)return;
            if(result.nodes>=max_nodes){result.complete=false;result.cap_reason="enumeration-node-limit";return;}
            ++result.nodes;
            if(remaining==0){emit(word,profile,source_id);return;}
            // The earliest occurrence suffices for each possible next letter:
            // choosing a later equal letter only removes available suffixes.
            // This generates each distinct subsequence exactly once per input.
            for(unsigned x=0;x<2;++x) {
                auto at=next[position][x];
                if(at==source.size() || source.size()-at<remaining)continue;
                std::string child(profile.size(),'\0');
                for(unsigned mask=0;mask<(1u<<m);++mask)
                    child[mask]=char(delta[mask*m+static_cast<unsigned char>(profile[mask])][x]);
                word.push_back(char('0'+x));visit(at+1,remaining-1,child);word.pop_back();
                if(!result.complete)return;
            }
        };
        visit(0,target,std::string(1u<<m,'\0'));
        result.source_complete[source_id]=result.complete;
    }
};
std::unordered_set<std::string> brute(const std::string& source,unsigned target) {
    std::unordered_set<std::string> words;
    for(unsigned subset=0;subset<(1u<<source.size());++subset) {
        std::string word;
        for(unsigned i=0;i<source.size();++i)if(subset&(1u<<i))word+=source[i];
        if(word.size()==target)words.insert(word);
    }
    return words;
}
void self_test() {
    std::uint64_t cases=0;
    for(unsigned n=1;n<=7;++n)for(unsigned code=0;code<(1u<<n);++code) {
        std::string word;for(unsigned i=0;i<n;++i)word+=char('0'+((code>>i)&1));
        for(unsigned k=1;k<=n;++k) {
            Search search("00010101",k,0);search.enumerate(word,0);
            require(search.result.complete,"Unexpected enumeration cap");
            require(search.result.words==brute(word,k),"Distinct-subsequence enumeration differs from positional reference");
            for(const auto& [profile,w]:search.result.profiles)
                for(unsigned mask=0;mask<4;++mask)
                    require(static_cast<unsigned char>(profile[mask])==search.endpoint(mask,w),"Cached profile differs from scalar replay");
            ++cases;
        }
    }
    Search cap("00010101",3,64);cap.max_nodes=1;cap.enumerate("010101",0);
    require(!cap.result.complete && cap.result.witnesses.empty(),"Capped space mislabeled complete");
    Search collision("00010101",1,0);collision.enumerate("01",0);
    require(collision.result.witnesses.empty(),"Forced hash collision accepted unequal complete profiles");
    Search coincident("0000",1,0);coincident.enumerate("01",0);
    require(coincident.result.witnesses.size()==1,"Coincident-loop collision not found");
    std::cout<<"PASS "<<cases<<" exhaustive subsequence spaces; profiles, forced hashes, loops, caps\n";
}
}
int main(int argc,char**argv) {
    try {
        std::map<std::string,std::string> options;
        for(int i=1;i<argc;++i) {
            std::string name=argv[i];
            if(name=="--self-test"){self_test();return 0;}
            require(i+1<argc,"Missing option value");options[name]=argv[++i];
        }
        for(auto name:{"--graph","--target","--out"})
            require(options.count(name)!=0,"Required: --graph --target --out plus --first/--second or --input-file");
        std::vector<std::string> input_words;
        if(options.count("--input-file")) {
            std::ifstream input(options["--input-file"]);require(bool(input),"Cannot read input file");
            std::string word;while(std::getline(input,word)) {
                if(!word.empty() && word.back()=='\r')word.pop_back();
                if(!word.empty())input_words.push_back(word);
            }
            require(!input_words.empty(),"Empty input word file");
        }else {
            require(options.count("--first") && options.count("--second"),"Both input words required");
            input_words={options["--first"],options["--second"]};
        }
        auto start=std::chrono::steady_clock::now();
        unsigned target=unsigned(std::stoul(options["--target"]));require(target>0,"Target must be positive");
        unsigned bits=options.count("--hash-bits")?unsigned(std::stoul(options["--hash-bits"])):64;
        require(bits<=64,"Invalid hash bits");
        Search search(options["--graph"],target,bits);
        if(options.count("--max-nodes"))search.max_nodes=std::stoull(options["--max-nodes"]);
        if(options.count("--max-profiles"))search.max_profiles=std::stoull(options["--max-profiles"]);
        if(options.count("--max-words"))search.max_words=std::stoull(options["--max-words"]);
        if(options.count("--max-witnesses"))search.max_witnesses=unsigned(std::stoul(options["--max-witnesses"]));
        require(search.max_witnesses>0,"max-witnesses must be positive");
        for(unsigned i=0;i<input_words.size();++i)search.enumerate(input_words[i],i);
        const auto&r=search.result;
        double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        std::filesystem::path out=options["--out"];std::filesystem::create_directories(out);
        std::ofstream file(out/"result.json");require(bool(file),"Cannot create result");
        file<<"{\n\"schema\":1,\n\"method\":\"complete-profile-distinct-subsequence-pool-v1\",\n"
            <<"\"key\":\""<<options["--graph"]<<"\",\n\"m\":"<<search.m<<",\n\"target_length\":"<<target
            <<",\n\"input_words\":[";
        for(std::size_t i=0;i<input_words.size();++i){if(i)file<<",";file<<"\""<<input_words[i]<<"\"";}
        file<<"],\n"
            <<"\"complete_within_subsequence_space\":"<<(r.complete?"true":"false")
            <<",\n\"search_capped\":"<<(r.complete?"false":"true")
            <<",\n\"cap_reason\":\""<<r.cap_reason<<"\""
            <<",\n\"no_pair_in_subsequence_space\":"<<(r.complete&&r.witnesses.empty()?"true":"false")
            <<",\n\"graph_lower_bound_claimed\":false,\n\"nodes\":"<<r.nodes
            <<",\n\"unique_subsequences_per_input\":[";
        for(std::size_t i=0;i<r.source_counts.size();++i){if(i)file<<",";file<<r.source_counts[i];}
        file<<"],\n\"subsequence_space_complete_per_input\":[";
        for(std::size_t i=0;i<r.source_complete.size();++i){if(i)file<<",";file<<(r.source_complete[i]?"true":"false");}
        file<<"]"
            <<",\n\"subsequence_generations\":"<<r.generations<<",\n\"union_distinct_subsequences\":"<<r.words.size()
            <<",\n\"unique_complete_profiles\":"<<r.profiles.size()<<",\n\"colliding_profiles\":"<<r.colliding.size()
            <<",\n\"hash_bits\":"<<bits<<",\n\"mask_count\":"<<(1u<<search.m)
            <<",\n\"max_nodes\":"<<search.max_nodes<<",\n\"max_witnesses\":"<<search.max_witnesses
            <<",\n\"max_profiles\":"<<search.max_profiles<<",\n\"max_words\":"<<search.max_words
            <<",\n\"seconds\":"<<seconds<<",\n\"decision\":\""<<(r.witnesses.empty()?"unknown":"collision")<<"\",\n\"witnesses\":[";
        for(std::size_t i=0;i<r.witnesses.size();++i) {
            if(i)file<<",";
            file<<"[\""<<r.witnesses[i][0]<<"\",\""<<r.witnesses[i][1]<<"\"]";
        }
        file<<"],\n\"upper_bound\":"<<(r.witnesses.empty()?"null":std::to_string(target))
            <<",\n\"all_stored_witnesses_independently_scalar_verified\":true\n}\n";
        file.close();require(bool(file),"Result write failed");
        std::cout<<(r.witnesses.empty()?"UNKNOWN":"COLLISION")<<" complete="<<r.complete
            <<" words="<<r.words.size()<<" stored="<<r.witnesses.size()<<" seconds="<<seconds<<"\n";
        return 0;
    }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}

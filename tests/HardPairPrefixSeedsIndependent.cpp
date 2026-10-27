#include "HardPairPrefixSeeds.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Table=std::vector<std::array<std::uint32_t,2>>;
struct DFA{Table table;std::uint32_t root=0;};using Family=std::vector<DFA>;
using Pair=std::pair<std::string,std::string>;using Profile=std::vector<std::uint32_t>;
void require(bool c,const char*s){if(!c)throw std::runtime_error(s);}
std::string word(std::uint64_t id,unsigned int n){std::string w(n,'0');for(unsigned i=0;i<n;++i){w[n-1-i]+=id&1U;id>>=1;}return w;}
Profile profile(const Family& f,const std::string&w){Profile p;for(const auto&d:f){auto s=d.root;for(char c:w)s=d.table[s][c-'0'];p.push_back(s);}return p;}
std::set<Pair> reference(const Family&f,unsigned int depth)
{
    std::set<Pair> result;
    for(unsigned int n=1;n<=depth;++n){
        std::map<Profile,std::vector<std::string>> groups;
        for(std::uint64_t id=0;id<(1ULL<<n);++id){auto w=word(id,n);groups[profile(f,w)].push_back(w);}
        for(const auto&[p,words]:groups)for(std::size_t a=0;a<words.size();++a)for(std::size_t b=a+1;b<words.size();++b)result.insert({words[a],words[b]});
    }
    return result;
}
hardpair::PrefixSeedResult enumerate(const Family& f,hardpair::PrefixSeedOptions options)
{
    Profile initial;for(const auto&d:f)initial.push_back(d.root);
    return hardpair::enumerate_prefix_seeds(initial,[&](std::size_t id,std::uint32_t s,bool x){
        require(id<f.size()&&s<f[id].table.size(),"heterogeneous coordinate identity/state range lost");return f[id].table[s][x];},options);
}
std::set<Pair> validate(const Family&f,const hardpair::PrefixSeedResult&r)
{
    std::set<Pair> pairs;
    for(const auto&p:r.pairs){
        require(!p.first.empty()&&p.first!=p.second&&p.first.size()==p.second.size(),"cross-length or equal-word seed emitted");
        require(p.first.find_first_not_of("01")==std::string::npos&&p.second.find_first_not_of("01")==std::string::npos,"nonbinary seed");
        require(profile(f,p.first)==p.profile&&profile(f,p.second)==p.profile,"matching hash not checked against full profiles");
        require(word(p.first_word_id,unsigned(p.first.size()))==p.first&&word(p.second_word_id,unsigned(p.second.size()))==p.second,"word IDs lost leading zeros/order");
        auto ordered=std::minmax(p.first,p.second);require(pairs.insert({ordered.first,ordered.second}).second,"duplicate seed pair");
    }
    return pairs;
}
std::vector<Pair> ordered_pairs(const hardpair::PrefixSeedResult&r){std::vector<Pair>p;for(const auto&x:r.pairs)p.push_back({x.first,x.second});return p;}
std::size_t lcp(const std::string&a,const std::string&b){std::size_t p=0;while(p<a.size()&&a[p]==b[p])++p;return p;}
}
int main()
{
    try{
        std::uint64_t tables=0,total_pairs=0;
        for(unsigned int n=1;n<=3;++n){
            std::uint64_t count=1;for(unsigned int i=0;i<2*n;++i)count*=n;
            for(std::uint64_t code=0;code<count;++code){
                auto x=code;Table t(n);for(auto&row:t)for(auto&target:row){target=x%n;x/=n;}
                Family f{{t,0}};hardpair::PrefixSeedOptions o;o.max_depth=3;o.max_words=8;o.max_pairs=100000;
                const auto expected=reference(f,3);const auto r=enumerate(f,o);
                require(validate(f,r)==expected,"bounded complete seed collection differs from per-length exhaustive reference");
                require(r.completed_depth==3&&r.words_evaluated==14,"complete per-layer budget accounting wrong");
                require(r.total_pairs_available==expected.size()&&!r.pair_capped&&r.complete_pair_collection,"complete collection mislabeled");
                o.force_hash_collisions=true;const auto forced=enumerate(f,o);
                require(validate(f,forced)==expected&&ordered_pairs(r)==ordered_pairs(forced),"forced hash changed valid seeds/determinism");
                o.common_prefix_depth=3;const auto stratified=enumerate(f,o);
                require(validate(f,stratified)==expected&&stratified.complete_pair_collection,"LCP strata lost complete bounded pair collection");
                o.force_hash_collisions=false;
                require(ordered_pairs(stratified)==ordered_pairs(enumerate(f,o)),"LCP strata depended on matching hashes");
                o.deterministic=true;
                const auto canonical=enumerate(f,o);
                require(validate(f,canonical)==expected&&canonical.complete_pair_collection,"strict deterministic traversal lost exhaustive reference pairs");
                total_pairs+=expected.size();++tables;
            }
        }
        require(tables==746,"missing explicit binary DFA tables");
        // Root profile repeats at another length, but no equal-length collision
        // exists at either length1 or2. Both letter maps are permutations.
        Family cross{{{{1,2},{0,3},{2,1},{3,0}},0}};
        require(profile(cross,"")==profile(cross,"00"),"cross-length fixture lacks root revisit");
        hardpair::PrefixSeedOptions o;o.max_depth=2;o.max_words=4;o.max_pairs=128;o.force_hash_collisions=true;
        auto r=enumerate(cross,o);require(r.pairs.empty()&&r.first_collision_length==0&&r.completed_depth==2,"another-length visit became a collision seed");
        o.max_depth=3;o.max_words=8;r=enumerate(cross,o);
        require(r.first_collision_length==3&&!r.pairs.empty(),"true equal-length collision not found after root revisit");validate(cross,r);
        o.max_depth=3;o.max_words=3;r=enumerate(cross,o);
        require(r.word_capped&&r.completed_depth==1&&r.pairs.empty(),"incomplete layer exported invalid seeds");
        Family prefixed{{{{1,2},{1,1},{2,2}},0}};
        o.max_depth=3;o.max_words=8;o.max_pairs=10000;r=enumerate(prefixed,o);
        const auto all=validate(prefixed,r);require(all==reference(prefixed,3)&&all.count({"00","01"}),"common prefix was canceled from a valid pair");
        require(profile(prefixed,"0")!=profile(prefixed,"1"),"prefix counterexample invalid");
        Family heterogeneous{{{{0,0},{0,1}},1},{{{1,0},{2,1},{2,2}},0},{{{1,0},{2,1},{3,2},{4,3},{4,4}},0}};
        o.max_depth=4;o.max_words=16;o.max_pairs=100000;r=enumerate(heterogeneous,o);
        require(validate(heterogeneous,r)==reference(heterogeneous,4),"heterogeneous roots/state counts ignored");
        Family constant{{{{0,0}},0}};o.max_pairs=5;r=enumerate(constant,o);
        require(r.pairs.size()==5&&r.pair_capped&&!r.complete_pair_collection,"pair cap claims all seeds");
        std::set<std::size_t> depths;for(const auto&p:r.pairs)depths.insert(p.first.size());
        require(depths.size()==4,"shortest collision layer crowded out all later depths");validate(constant,r);
        auto empty=hardpair::enumerate_prefix_seeds(Profile{},[](std::size_t,std::uint32_t,bool){throw std::runtime_error("empty family called transition");return 0U;},o);
        require(empty.empty_coordinate_family&&empty.pairs.empty(),"empty selected family became pretend collision proof");
        volatile std::sig_atomic_t stopped=1;o.interrupted=&stopped;r=enumerate(cross,o);
        require(r.interrupted&&r.pairs.empty(),"cancelled prefix enumeration exported a proof");o.interrupted=nullptr;

        // Long birthday layers contain same-length real words, but are sampled
        // and must not be labeled exhaustive. Their seed list is reproducible.
        o=hardpair::PrefixSeedOptions{};o.max_depth=2;o.max_words=64;o.max_pairs=16;
        o.sample_depths={20,24};o.samples_per_depth=64;o.seed=1088;
        auto sampled=enumerate(cross,o);validate(cross,sampled);
        require(!sampled.pairs.empty()&&sampled.completed_depth==2,"long sampled seed fixture failed");
        bool sampled_layer=false;
        for(const auto&layer:sampled.per_depth)if(layer.depth>=20){sampled_layer=true;require(layer.sampled&&!layer.complete_enumeration,"sampled long layer claims exhaustive coverage");}
        require(sampled_layer,"long sampled layers missing metadata");
        for(const auto&p:sampled.pairs)require(p.first.size()==20||p.first.size()==24,"long sampled pair length invalid");
        require(ordered_pairs(sampled)==ordered_pairs(enumerate(cross,o)),"long sampled seeds nondeterministic");
        o.force_hash_collisions=true;require(ordered_pairs(sampled)==ordered_pairs(enumerate(cross,o)),"long sampled hash collision changed seeds");
        o.common_prefix_depth=8;const auto sampled_strata=enumerate(cross,o);validate(cross,sampled_strata);
        require(!sampled_strata.complete_pair_collection&&!sampled_strata.first_collision_proved_minimum,"sampled LCP strata fabricated completeness");
        require(ordered_pairs(sampled_strata)==ordered_pairs(enumerate(cross,o)),"sampled LCP strata nondeterministic");
        o=hardpair::PrefixSeedOptions{};o.max_depth=6;o.max_words=64;o.max_pairs=24;o.common_prefix_depth=4;
        const auto heterogeneous_strata=enumerate(heterogeneous,o);validate(heterogeneous,heterogeneous_strata);
        require(ordered_pairs(heterogeneous_strata)==ordered_pairs(enumerate(heterogeneous,o)),"heterogeneous LCP strata nondeterministic");
        // Opt-in LCP strata cover intermediate branch depths as well as the
        // very short/very long LCPs generated by the original diverse cursor.
        // A one-state family makes every profile valid, so this tests only
        // generic trie-boundary diversity, independently of Family1.
        o=hardpair::PrefixSeedOptions{};o.max_depth=10;o.max_words=1024;o.max_pairs=128;o.common_prefix_depth=8;
        const auto stratified=enumerate(constant,o);validate(constant,stratified);
        require(stratified.pairs.size()==128&&stratified.pair_capped,"stratified candidate budget lost cap semantics");
        std::map<std::size_t,std::set<std::string>> common;
        for(const auto&p:stratified.pairs)common[lcp(p.first,p.second)].insert(p.first.substr(0,lcp(p.first,p.second)));
        for(std::size_t p=0;p<=8;++p)require(common.count(p)!=0,"intermediate actual-LCP stratum omitted");
        require(common[6].size()>1&&common[7].size()>1,"one common prefix crowded out its whole LCP stratum");
        std::uint64_t selected=0;
        for(const auto&layer:stratified.per_depth){selected+=layer.selected_pairs;require(layer.retained_candidates<=2*o.max_pairs,"LCP candidates exceeded bounded memory budget");}
        require(selected==stratified.pairs.size(),"stratified selected-pair accounting lost deduplication");
        require(ordered_pairs(stratified)==ordered_pairs(enumerate(constant,o)),"LCP strata nondeterministic");
        o.force_hash_collisions=true;require(ordered_pairs(stratified)==ordered_pairs(enumerate(constant,o)),"LCP strata changed under forced hashes");
        o.max_pairs=1;require(validate(constant,enumerate(constant,o)).size()==1,"one-pair LCP budget failed");
        o.common_prefix_depth=9;bool rejected=false;try{enumerate(constant,o);}catch(const std::invalid_argument&){rejected=true;}
        require(rejected,"LCP strata depth guard missing");

        // Strict traversal must not use fixed-seed sampling or seeded pair
        // ranks. It still distributes a bounded pair budget across depths and
        // every available actual common-prefix stratum.
        o=hardpair::PrefixSeedOptions{};o.deterministic=true;
        o.max_depth=10;o.max_words=1024;o.max_pairs=128;o.common_prefix_depth=8;
        o.sample_depths={20,24,63};o.samples_per_depth=65536;o.seed=0;
        const auto strict=enumerate(constant,o);validate(constant,strict);
        o.seed=std::numeric_limits<std::uint64_t>::max();
        o.samples_per_depth=1;o.sample_depths={11,16};
        require(ordered_pairs(strict)==ordered_pairs(enumerate(constant,o)),"strict traversal depended on seed or sampled-word settings");
        o.force_hash_collisions=true;
        require(ordered_pairs(strict)==ordered_pairs(enumerate(constant,o)),"strict traversal depended on profile hash collisions");
        require(strict.completed_depth==10&&strict.sampled_words_evaluated==0&&strict.largest_sampled_depth==0,
                "strict traversal evaluated sampled words or skipped complete layers");
        std::set<std::size_t> strict_depths,strict_lcps;
        for(const auto&p:strict.pairs){strict_depths.insert(p.first.size());strict_lcps.insert(lcp(p.first,p.second));}
        require(strict_depths.size()==10,"strict traversal crowded out complete depths");
        for(std::size_t p=0;p<=8;++p)require(strict_lcps.count(p),"strict traversal crowded out an actual-LCP stratum");
        for(const auto&layer:strict.per_depth)
            require(layer.complete_enumeration&&!layer.sampled&&layer.retained_candidates<=2*o.max_pairs,
                    "strict traversal claimed sampled coverage or exceeded its candidate budget");
        o.max_words=256;const auto strict_capped=enumerate(constant,o);validate(constant,strict_capped);
        require(strict_capped.completed_depth==8&&strict_capped.word_capped&&!strict_capped.complete_pair_collection
                &&strict_capped.sampled_words_evaluated==0,"strict traversal bypassed the complete-word-layer cap");
        hardpair::prefix_seed_detail::PairCursor lexical(4,true);
        const std::array<std::pair<std::size_t,std::size_t>,6> lexical_expected{{{0,1},{1,2},{2,3},{0,2},{1,3},{0,3}}};
        for(const auto&expected:lexical_expected)require(lexical.next()==expected,"canonical bucket pair traversal is not gap-then-lexical");
        require(!lexical.next(),"canonical bucket traversal repeated a pair");
        std::cout<<"{\"passed\":true,\"explicit_binary_DFAs\":"<<tables<<",\"complete_reference_pairs\":"<<total_pairs
            <<",\"fresh_per_length_tables_checked\":true,\"full_profiles_checked_under_forced_hash\":true"
            <<",\"common_prefix_preserved\":true,\"heterogeneous_roots_checked\":true,\"depth_diversity_checked\":true"
            <<",\"long_sampled_layers_labeled_and_deterministic\":true,\"caps_interrupt_empty_family_checked\":true"
            <<",\"actual_LCP_0_through_8_diverse_and_bounded\":true,\"LCP_complete_reference_pairs_checked\":"<<total_pairs
            <<",\"strict_deterministic_seed_independence_and_caps_checked\":true}\n";
        return 0;
    }catch(const std::exception&e){std::cerr<<"HardPairPrefixSeedsIndependent: "<<e.what()<<'\n';return 1;}
}

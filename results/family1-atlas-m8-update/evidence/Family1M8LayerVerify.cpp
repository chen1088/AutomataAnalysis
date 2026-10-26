// Independent single-layer verifier, one to eight states. No production headers.
// Full profiles are one-hot mask-coordinate bitsets. Fingerprints only partition
// work: every repeated fingerprint is regenerated and checked as complete states.
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;
using Table = std::array<std::array<unsigned,2>,8>;
volatile std::sig_atomic_t interrupted = 0;
void stop(int) { interrupted=1; }
std::string quote(const std::string& value) {
    constexpr char digits[]="0123456789abcdef";std::string out="\"";
    for(unsigned char c:value) {
        if(c=='"'||c=='\\'){out+='\\';out+=char(c);}
        else if(c<32){out+="\\u00";out+=digits[c>>4];out+=digits[c&15];}
        else out+=char(c);
    }
    return out+'"';
}
std::uint64_t number(const std::string& text) {
    if(text.empty()||text.find_first_not_of("0123456789")!=std::string::npos)
        throw std::runtime_error("expected unsigned integer");
    return std::stoull(text);
}
unsigned uint_number(const std::string& text) {
    const auto value=number(text);
    if(value>std::numeric_limits<unsigned>::max())throw std::runtime_error("unsigned option out of range");
    return static_cast<unsigned>(value);
}
std::uint64_t bit_reverse(std::uint64_t x) {
    x=((x>>1)&0x5555555555555555ull)|((x&0x5555555555555555ull)<<1);
    x=((x>>2)&0x3333333333333333ull)|((x&0x3333333333333333ull)<<2);
    x=((x>>4)&0x0f0f0f0f0f0f0f0full)|((x&0x0f0f0f0f0f0f0f0full)<<4);
    x=((x>>8)&0x00ff00ff00ff00ffull)|((x&0x00ff00ff00ff00ffull)<<8);
    x=((x>>16)&0x0000ffff0000ffffull)|((x&0x0000ffff0000ffffull)<<16);
    return (x>>32)|(x<<32);
}
std::string binary_word(std::uint64_t index,unsigned depth) {
    std::string word(depth,'0');
    for(unsigned i=0;i<depth;++i){word[depth-1-i]+=char(index&1);index>>=1;}
    return word;
}
std::string complement(std::string word) {for(auto& c:word)c=c=='0'?'1':'0';return word;}

template<class Work> void parallel_tasks(unsigned tasks,unsigned threads,Work&& work) {
    std::atomic<unsigned> next{0};std::atomic<bool> canceled{false};
    std::exception_ptr error;std::mutex mutex;
    auto worker=[&] {
        try {
            while(!canceled.load(std::memory_order_relaxed)) {
                const auto task=next.fetch_add(1,std::memory_order_relaxed);
                if(task>=tasks)return;
                work(task,canceled);
            }
        }catch(...) {
            {std::lock_guard<std::mutex> lock(mutex);if(!error)error=std::current_exception();}
            canceled.store(true,std::memory_order_relaxed);
        }
    };
    std::vector<std::thread> workers;
    try {for(unsigned i=1;i<std::min(tasks,threads);++i)workers.emplace_back(worker);}
    catch(...){canceled=true;for(auto& t:workers)t.join();throw;}
    worker();for(auto& t:workers)t.join();if(error)std::rethrow_exception(error);
}
template<class Check> void radix_inplace(std::uint64_t* a,std::uint64_t begin,std::uint64_t end,unsigned shift,const Check& check) {
    check();if(end-begin<64){std::sort(a+begin,a+end);return;}
    std::array<std::uint64_t,256> counts{},start{},next{};
    for(auto i=begin;i<end;++i){if((i&1048575)==0)check();++counts[(a[i]>>shift)&255];}
    auto sum=begin;for(unsigned b=0;b<256;++b){start[b]=next[b]=sum;sum+=counts[b];}
    for(unsigned b=0;b<256;++b) {
        const auto stop=start[b]+counts[b];
        while(next[b]<stop) {
            if((next[b]&1048575)==0)check();
            const auto target=unsigned((a[next[b]]>>shift)&255);
            if(target==b)++next[b];else std::swap(a[next[b]],a[next[target]++]);
        }
    }
    if(shift)for(unsigned b=0;b<256;++b)if(counts[b]>1)radix_inplace(a,start[b],start[b]+counts[b],shift-8,check);
}
template<class Check> void radix_parallel(std::uint64_t* a,std::uint64_t count,unsigned threads,const Check& check) {
    if(count<64){radix_inplace(a,0,count,56,check);return;}
    std::array<std::uint64_t,256> sizes{},start{},next{};
    for(std::uint64_t i=0;i<count;++i){if((i&1048575)==0)check();++sizes[a[i]>>56];}
    std::uint64_t sum=0;for(unsigned b=0;b<256;++b){start[b]=next[b]=sum;sum+=sizes[b];}
    for(unsigned b=0;b<256;++b) {
        auto end=start[b]+sizes[b];
        while(next[b]<end) {
            if((next[b]&1048575)==0)check();const auto target=unsigned(a[next[b]]>>56);
            if(target==b)++next[b];else std::swap(a[next[b]],a[next[target]++]);
        }
    }
    parallel_tasks(256,threads,[&](unsigned b,const auto& canceled) {
        auto worker_check=[&]{if(canceled.load(std::memory_order_relaxed))throw std::runtime_error("sort canceled");check();};
        if(sizes[b]>1)radix_inplace(a,start[b],start[b]+sizes[b],48,worker_check);
    });
    check();
}

struct Options {
    std::string key,out,mask_text;
    unsigned m=0,depth=0,threads=1,prefix_bits=8,bucket_bits=1;
    std::uint64_t max_mib=40000,timeout_ms=0;
    bool force_hash=false;
    bool fingerprint_only=false,mask_argument_supplied=false,masks_valid=false;
    Table table{};std::vector<unsigned> masks;
};
struct Statistics {
    std::uint64_t expected=0,count_generated=0,fill_generated=0,replay_generated=0;
    std::uint64_t comparisons=0,repeated_hash_groups=0,repeated_hash_records=0,peak_payload=0;
    std::uint64_t self_symmetric_candidates=0;
    std::uint64_t full_self_checks=0,full_replay_records=0;
    unsigned completed_buckets=0;std::vector<std::uint64_t> bucket_sizes;
    std::string phase="initialization",reason;
    bool complete=false,selected_witness_verified=false,full_witness_verified=false;
    std::array<std::string,2>witness{};
};
using FullState=std::array<unsigned char,256>;
FullState full_scalar_profile(const Options& o,std::uint64_t index) {
    FullState profile{};
    for(unsigned mask=0;mask<(1u<<o.m);++mask) {
        unsigned state=0;
        for(unsigned bit=0;bit<o.depth;++bit)
            state=o.table[state][unsigned((index>>(o.depth-1-bit))&1)^((mask>>state)&1)];
        profile[mask]=static_cast<unsigned char>(state);
    }
    return profile;
}
bool full_symmetric(const FullState& state,unsigned m) {
    const auto all=(1u<<m)-1;
    for(unsigned mask=0;mask<=all;++mask)if(state[mask]!=state[mask^all])return false;
    return true;
}

template<unsigned Blocks> using Profile=std::array<std::array<std::uint64_t,Blocks>,8>;
constexpr std::array<std::uint64_t,6> patterns={0xaaaaaaaaaaaaaaaaull,0xccccccccccccccccull,
    0xf0f0f0f0f0f0f0f0ull,0xff00ff00ff00ff00ull,0xffff0000ffff0000ull,0xffffffff00000000ull};

template<unsigned Blocks,bool Full> struct Kernel {
    const Options& o;
    Profile<Blocks> sigma{},initial{};
    unsigned padding=Blocks*64;
    explicit Kernel(const Options& options):o(options) {
        padding-=unsigned(o.masks.size());
        for(unsigned i=0;i<o.masks.size();++i) {
            initial[0][i/64]|=1ull<<(i%64);
            for(unsigned s=0;s<8;++s)if((o.masks[i]>>s)&1)sigma[s][i/64]|=1ull<<(i%64);
        }
    }
    Profile<Blocks> step(const Profile<Blocks>& p,bool input) const {
        Profile<Blocks> out{};
        for(unsigned s=0;s<8;++s)for(unsigned b=0;b<Blocks;++b) {
            std::uint64_t bitmask;
            if constexpr(Full)bitmask=s<6?patterns[s]:(((b>>(s-6))&1)?~0ull:0ull);
            else bitmask=sigma[s][b];
            out[o.table[s][input?1:0]][b]|=p[s][b]&~bitmask;
            out[o.table[s][input?0:1]][b]|=p[s][b]&bitmask;
        }
        return out;
    }
    std::uint64_t complemented_word(const std::array<std::uint64_t,Blocks>& row,unsigned b) const {
        auto value=bit_reverse(row[Blocks-1-b]);
        if(!padding)return value;
        value>>=padding;
        if(b+1<Blocks)value|=bit_reverse(row[Blocks-2-b])<<(64-padding);
        return value;
    }
    std::pair<std::uint64_t,bool> fingerprint(const Profile<Blocks>& p) const {
        std::uint64_t a=0xcbf29ce484222325ull,b=a;bool symmetric=true;
        const auto mix=[](std::uint64_t h,std::uint64_t value) {
            value^=value>>30;value*=0xbf58476d1ce4e5b9ull;value^=value>>27;value*=0x94d049bb133111ebull;
            return (h^(value^(value>>31)))*0x100000001b3ull;
        };
        for(const auto& row:p)for(unsigned block=0;block<Blocks;++block) {
            auto x=row[block],y=complemented_word(row,block);symmetric&=x==y;
            a=mix(a,x);b=mix(b,y);
        }
        return {o.force_hash?0:std::min(a,b),symmetric};
    }
    bool complementary_equal(const Profile<Blocks>& a,const Profile<Blocks>& b) const {
        for(unsigned s=0;s<8;++s)for(unsigned j=0;j<Blocks;++j)
            if(a[s][j]!=complemented_word(b[s],j))return false;
        return true;
    }
    template<class Leaf,class Check>
    void traverse(unsigned prefix_bits,const Leaf& leaf,const Check& check,std::uint64_t& generated,
                  const std::atomic<std::uint64_t>* stop_index=nullptr) const {
        const auto tasks=1u<<prefix_bits;const auto suffix_bits=o.depth-1-prefix_bits;
        std::vector<std::uint64_t> counters(tasks,0);
        try {
            parallel_tasks(tasks,o.threads,[&](unsigned prefix,const auto& canceled) {
                struct Publish {std::uint64_t& saved;std::uint64_t count=0;~Publish(){saved=count;}}counter{counters[prefix]};
                std::array<Profile<Blocks>,37> stack{};stack[0]=initial;stack[1]=step(stack[0],false);
                for(unsigned bit=0;bit<prefix_bits;++bit)
                    stack[bit+2]=step(stack[bit+1],(prefix>>(prefix_bits-1-bit))&1);
                const auto visit=[&](auto&& self,unsigned level,std::uint64_t index)->void {
                    if(stop_index&&(index<<(o.depth-level))>=stop_index->load(std::memory_order_relaxed))return;
                    if(level==o.depth) {
                        if((counter.count&65535)==0){if(canceled.load(std::memory_order_relaxed))throw std::runtime_error("worker canceled");check();}
                        ++counter.count;leaf(prefix,stack[level],index);return;
                    }
                    stack[level+1]=step(stack[level],false);self(self,level+1,index*2);
                    stack[level+1]=step(stack[level],true);self(self,level+1,index*2+1);
                };
                (void)suffix_bits;visit(visit,prefix_bits+1,prefix);
            });
        }catch(...){for(auto n:counters)generated+=n;throw;}
        for(auto n:counters)generated+=n;
    }
};

template<unsigned Blocks,bool Full,class Check>
bool partitioned(const Options& o,Statistics& stats,const Check& check) {
    Kernel<Blocks,Full> kernel(o);
    const unsigned prefix_bits=std::min(o.prefix_bits,o.depth-1),tasks=1u<<prefix_bits,buckets=1u<<o.bucket_bits;
    const auto representative_count=1ull<<(o.depth-1),budget=o.max_mib*1048576ull;
    const std::uint64_t bookkeeping=std::uint64_t(tasks)*buckets*16+std::uint64_t(tasks)*24
        +std::uint64_t(o.threads)*(sizeof(Profile<Blocks>)*37+65536)+1048576;
    stats.peak_payload=bookkeeping;
    if(bookkeeping>=budget)throw std::runtime_error("max-working-mib: prefix/sort workspace exceeds budget");
    std::vector<std::uint64_t> counts(std::size_t(tasks)*buckets,0),offsets(counts.size(),0);
    std::atomic<std::uint64_t> symmetric_index{std::numeric_limits<std::uint64_t>::max()};
    std::atomic<std::uint64_t> self_symmetric_candidates{0};
    std::atomic<std::uint64_t> full_self_checks{0};
    stats.phase="count";
    kernel.traverse(prefix_bits,[&](unsigned prefix,const auto& p,std::uint64_t index) {
        const auto [fingerprint,symmetric]=kernel.fingerprint(p);
        if(symmetric) {
            self_symmetric_candidates.fetch_add(1,std::memory_order_relaxed);
            bool real=true;
            if(!Full&&o.fingerprint_only) {
                full_self_checks.fetch_add(1,std::memory_order_relaxed);
                real=full_symmetric(full_scalar_profile(o,index),o.m);
            }
            if(real) {
                auto old=symmetric_index.load(std::memory_order_relaxed);
                while(index<old&&!symmetric_index.compare_exchange_weak(old,index,std::memory_order_relaxed)){}
            }
        }
        ++counts[std::size_t(prefix)*buckets+(fingerprint&(buckets-1))];
    },check,stats.count_generated,&symmetric_index);
    stats.self_symmetric_candidates=self_symmetric_candidates.load();
    stats.full_self_checks=full_self_checks.load();
    auto symmetric=symmetric_index.load(std::memory_order_relaxed);
    if(symmetric!=std::numeric_limits<std::uint64_t>::max()) {
        stats.witness={binary_word(symmetric,o.depth),complement(binary_word(symmetric,o.depth))};return false;
    }
    if(stats.count_generated!=representative_count)throw std::runtime_error("incomplete count traversal");
    stats.bucket_sizes.assign(buckets,0);
    for(unsigned b=0;b<buckets;++b)for(unsigned prefix=0;prefix<tasks;++prefix) {
        offsets[std::size_t(prefix)*buckets+b]=stats.bucket_sizes[b];
        stats.bucket_sizes[b]+=counts[std::size_t(prefix)*buckets+b];
    }
    std::cout<<"Counted "<<representative_count<<" representatives across "<<buckets<<" low-bit hash buckets.\n"<<std::flush;
    struct Seen {FullState profile;std::uint64_t index;};
    for(unsigned bucket=0;bucket<buckets;++bucket) {
        check();const auto count=stats.bucket_sizes[bucket];
        if(count>(budget-bookkeeping)/sizeof(std::uint64_t))throw std::runtime_error("max-working-mib: counted hash bucket exceeds budget");
        const auto hash_bytes=count*sizeof(std::uint64_t);
        stats.peak_payload=std::max(stats.peak_payload,bookkeeping+hash_bytes);
        std::unique_ptr<std::uint64_t[]> fingerprints(count?new std::uint64_t[count]:nullptr);
        std::vector<std::uint64_t> positions(tasks,0);
        stats.phase="fill-bucket-"+std::to_string(bucket);
        const auto fill_before=stats.fill_generated;
        kernel.traverse(prefix_bits,[&](unsigned prefix,const auto& p,std::uint64_t) {
            const auto fingerprint=kernel.fingerprint(p).first;
            if((fingerprint&(buckets-1))!=bucket)return;
            const auto slot=positions[prefix]++;
            const auto expected=counts[std::size_t(prefix)*buckets+bucket];
            if(slot>=expected)throw std::runtime_error("fill exceeds counted per-prefix interval");
            fingerprints[offsets[std::size_t(prefix)*buckets+bucket]+slot]=fingerprint;
        },check,stats.fill_generated);
        if(stats.fill_generated-fill_before!=representative_count)throw std::runtime_error("incomplete bucket-fill traversal");
        for(unsigned prefix=0;prefix<tasks;++prefix)
            if(positions[prefix]!=counts[std::size_t(prefix)*buckets+bucket])throw std::runtime_error("bucket fill differs from exact count");
        stats.phase="sort-bucket-"+std::to_string(bucket);
        if(count)radix_parallel(fingerprints.get(),count,o.threads,check);
        struct Group {std::uint64_t hash,count,offset;};
        std::uint64_t repeated=0,group_count=0;
        for(std::uint64_t begin=0;begin<count;) {
            if((begin&1048575)==0)check();auto end=begin+1;
            while(end<count&&fingerprints[end]==fingerprints[begin])++end;
            if(end-begin>1){++group_count;repeated+=end-begin;}
            begin=end;
        }
        stats.repeated_hash_groups+=group_count;stats.repeated_hash_records+=repeated;
        if(group_count) {
            const std::uint64_t group_bytes=group_count*(sizeof(Group)+sizeof(std::atomic<std::uint64_t>));
            if(group_bytes>budget-bookkeeping-hash_bytes||repeated>(budget-bookkeeping-hash_bytes-group_bytes)/sizeof(Seen))
                throw std::runtime_error("max-working-mib: complete-profile hash replay exceeds budget");
            stats.peak_payload=std::max(stats.peak_payload,bookkeeping+hash_bytes+group_bytes+repeated*sizeof(Seen));
            std::vector<Group> groups;groups.reserve(std::size_t(group_count));
            std::uint64_t offset=0;
            for(std::uint64_t begin=0;begin<count;) {
                if((begin&1048575)==0)check();auto end=begin+1;
                while(end<count&&fingerprints[end]==fingerprints[begin])++end;
                if(end-begin>1){groups.push_back({fingerprints[begin],end-begin,offset});offset+=end-begin;}
                begin=end;
            }
            if(groups.size()!=group_count||offset!=repeated)throw std::runtime_error("repeated-group counting mismatch");
            std::unique_ptr<Seen[]> seen(new Seen[repeated]);
            std::unique_ptr<std::atomic<std::uint64_t>[]> found(new std::atomic<std::uint64_t>[groups.size()]);
            std::atomic<std::uint64_t> replayed_full{0};
            for(std::size_t i=0;i<groups.size();++i)found[i]=0;
            stats.phase="replay-bucket-"+std::to_string(bucket);auto replay_before=stats.replay_generated;
            kernel.traverse(prefix_bits,[&](unsigned,const auto& p,std::uint64_t index) {
                const auto fingerprint=kernel.fingerprint(p).first;
                const auto it=std::lower_bound(groups.begin(),groups.end(),fingerprint,[](const Group& g,std::uint64_t h){return g.hash<h;});
                if(it==groups.end()||it->hash!=fingerprint)return;
                const auto group=std::size_t(it-groups.begin()),slot=found[group].fetch_add(1,std::memory_order_relaxed);
                if(slot>=it->count)throw std::runtime_error("hash replay exceeds counted repeated group");
                seen[it->offset+slot]={full_scalar_profile(o,index),index};
                replayed_full.fetch_add(1,std::memory_order_relaxed);
            },check,stats.replay_generated);
            if(stats.replay_generated-replay_before!=representative_count)throw std::runtime_error("incomplete repeated-hash replay");
            if(replayed_full.load()!=repeated)throw std::runtime_error("incomplete full-state scalar replay");
            stats.full_replay_records+=replayed_full.load();
            stats.phase="compare-complete-bucket-"+std::to_string(bucket);
            for(std::size_t g=0;g<groups.size();++g) {
                const auto& group=groups[g];if(found[g]!=group.count)throw std::runtime_error("repeated-hash replay count mismatch");
                auto* start=seen.get()+group.offset;
                std::sort(start,start+group.count,[](const Seen&a,const Seen&b){return a.index<b.index;});
                for(std::uint64_t i=0;i<group.count;++i)for(std::uint64_t j=0;j<i;++j) {
                    if((stats.comparisons++&65535)==0)check();
                    bool same=true;
                    if(Full||o.fingerprint_only)same=start[i].profile==start[j].profile;
                    else for(auto mask:o.masks)if(start[i].profile[mask]!=start[j].profile[mask]){same=false;break;}
                    if(same) {
                        stats.witness={binary_word(start[j].index,o.depth),binary_word(start[i].index,o.depth)};return false;
                    }
                    same=true;const auto all=(1u<<o.m)-1;
                    if(Full||o.fingerprint_only) {
                        for(unsigned mask=0;mask<=all;++mask)
                            if(start[i].profile[mask]!=start[j].profile[mask^all]){same=false;break;}
                    }else for(auto mask:o.masks)
                        if(start[i].profile[mask]!=start[j].profile[mask^all]){same=false;break;}
                    if(same) {
                        stats.witness={binary_word(start[j].index,o.depth),complement(binary_word(start[i].index,o.depth))};return false;
                    }
                }
            }
        }
        ++stats.completed_buckets;
        std::cout<<"Completed bucket "<<bucket<<" ("<<count<<" fingerprints).\n"<<std::flush;
    }
    stats.phase="complete";return true;
}

template<unsigned Blocks,class Check> bool dispatch_mode(const Options&o,Statistics&s,const Check&check,bool full) {
    return full?partitioned<Blocks,true>(o,s,check):partitioned<Blocks,false>(o,s,check);
}
std::vector<unsigned> scalar(const Options& o,const std::string& word,const std::vector<unsigned>& masks) {
    std::vector<unsigned> states(masks.size(),0);
    for(std::size_t i=0;i<masks.size();++i)for(char bit:word)
        states[i]=o.table[states[i]][unsigned(bit-'0')^((masks[i]>>states[i])&1)];
    return states;
}
}

int main(int argc,char**argv) {
    Options o;Statistics stats;bool full=false;auto started=Clock::now();
    const auto seconds=[&]{return std::chrono::duration<double>(Clock::now()-started).count();};
    try {
        for(int i=1;i<argc;++i) {
            const std::string arg=argv[i];
            if(arg=="--force-hash-collisions"){o.force_hash=true;continue;}
            if(arg=="--help") {
                std::cout<<"Family1M8LayerVerify --key KEY --depth1..36 --out REPORT [--threads1..64 --prefix-bits8 --bucket-bits1 --max-working-mib40000 --timeout-ms0 --mask-list0,255,... --mask-file FILE --fingerprint-masks0,255,... --fingerprint-mask-file FILE --force-hash-collisions]\n";return 0;
            }
            if(++i>=argc)throw std::runtime_error("missing option value");const std::string value=argv[i];
            if(arg=="--key")o.key=value;else if(arg=="--out")o.out=value;
            else if(arg=="--depth")o.depth=uint_number(value);else if(arg=="--threads")o.threads=uint_number(value);
            else if(arg=="--prefix-bits")o.prefix_bits=uint_number(value);else if(arg=="--bucket-bits")o.bucket_bits=uint_number(value);
            else if(arg=="--max-working-mib")o.max_mib=number(value);else if(arg=="--timeout-ms")o.timeout_ms=number(value);
            else if(arg=="--mask-list"||arg=="--fingerprint-masks") {
                if(o.mask_argument_supplied)throw std::runtime_error("provide only one mask argument");
                o.mask_argument_supplied=true;o.mask_text=value;o.fingerprint_only=arg=="--fingerprint-masks";
            }
            else if(arg=="--mask-file"||arg=="--fingerprint-mask-file") {
                if(o.mask_argument_supplied)throw std::runtime_error("provide only one mask argument");
                o.mask_argument_supplied=true;o.fingerprint_only=arg=="--fingerprint-mask-file";
                std::ifstream file(value);if(!file)throw std::runtime_error("cannot read mask file");o.mask_text.assign(std::istreambuf_iterator<char>(file),{});
            }
            else throw std::runtime_error("unknown option: "+arg);
        }
        if(o.key.empty()||o.key.size()%4||o.key.size()>32||o.key.find_first_not_of("0123456789")!=std::string::npos)
            throw std::runtime_error("expected fixed two-digit key for one to eight states");
        o.m=unsigned(o.key.size()/4);
        if(!o.depth||o.depth>36||o.out.empty()||!o.threads||o.threads>64||o.prefix_bits>16||o.bucket_bits>12
            ||!o.max_mib||o.max_mib>std::numeric_limits<std::uint64_t>::max()/1048576)
            throw std::runtime_error("invalid depth/thread/partition/resource options");
        if(std::filesystem::exists(o.out))throw std::runtime_error("output already exists; use a fresh report path");
        for(unsigned s=0;s<o.m;++s)for(unsigned bit=0;bit<2;++bit) {
            o.table[s][bit]=unsigned(number(o.key.substr(4*s+2*bit,2)));
            if(o.table[s][bit]>=o.m)throw std::runtime_error("target outside graph");
        }
        std::array<bool,8> reached{};reached[0]=true;
        for(unsigned pass=0;pass<o.m;++pass)for(unsigned s=0;s<o.m;++s)if(reached[s])for(auto target:o.table[s])reached[target]=true;
        for(unsigned s=0;s<o.m;++s)if(!reached[s])throw std::runtime_error("graph is not root-accessible");
        if(!o.mask_argument_supplied)for(unsigned mask=0;mask<(1u<<o.m);++mask)o.masks.push_back(mask);
        else {
            for(auto& c:o.mask_text)if(c==','||c==';')c=' ';
            std::istringstream stream(o.mask_text);std::string item;
            while(stream>>item){auto mask=number(item);if(mask>=(1u<<o.m))throw std::runtime_error("mask outside graph family");o.masks.push_back(unsigned(mask));}
            std::sort(o.masks.begin(),o.masks.end());
            if(o.masks.empty()||std::adjacent_find(o.masks.begin(),o.masks.end())!=o.masks.end())throw std::runtime_error("empty or duplicate mask list");
        }
        for(auto mask:o.masks)if(!std::binary_search(o.masks.begin(),o.masks.end(),mask^((1u<<o.m)-1)))
            throw std::runtime_error("selected masks must be closed under bitwise complement");
        o.masks_valid=true;
        full=o.masks.size()==(1u<<o.m);stats.expected=1ull<<(o.depth-1);
        std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
        const auto check=[&]{if(interrupted)throw std::runtime_error("interrupted");if(o.timeout_ms&&seconds()*1000>=o.timeout_ms)throw std::runtime_error("timeout");};
        switch((o.masks.size()+63)/64) {
        case 1:stats.complete=dispatch_mode<1>(o,stats,check,full);break;
        case 2:stats.complete=dispatch_mode<2>(o,stats,check,full);break;
        case 3:stats.complete=dispatch_mode<3>(o,stats,check,full);break;
        case 4:stats.complete=dispatch_mode<4>(o,stats,check,full);break;
        default:throw std::runtime_error("unsupported mask width");
        }
        if(!stats.witness[0].empty()) {
            if(stats.witness[0]==stats.witness[1]||stats.witness[0].size()!=o.depth||stats.witness[1].size()!=o.depth)
                throw std::runtime_error("invalid equal-length distinct witness");
            if(scalar(o,stats.witness[0],o.masks)!=scalar(o,stats.witness[1],o.masks))throw std::runtime_error("selected-mask scalar witness mismatch");
            stats.selected_witness_verified=true;
            std::vector<unsigned> all;for(unsigned mask=0;mask<(1u<<o.m);++mask)all.push_back(mask);
            stats.full_witness_verified=scalar(o,stats.witness[0],all)==scalar(o,stats.witness[1],all);
            if((full||o.fingerprint_only)&&!stats.full_witness_verified)throw std::runtime_error("full-mask scalar witness mismatch");
        }
    }catch(const std::exception& error){stats.reason=error.what();stats.complete=false;stats.witness={};}
    const bool full_proof=full||o.fingerprint_only;
    const std::string status=!stats.reason.empty()?"incomplete":stats.complete?"collision-free":full_proof?"collision-found":"projection-collision";
    const bool upper=full_proof&&!stats.witness[0].empty()&&stats.full_witness_verified;
    if(!o.out.empty()) {
        // Never overwrite an earlier report, including on invalid arguments.
        if(std::filesystem::exists(o.out)){std::cerr<<"refusing to overwrite report\n";return 1;}
        std::ofstream report(o.out);if(!report){std::cerr<<"cannot write report\n";return 1;}
        report<<"{\"schema\":1,\"method\":\"independent-partitioned-complement-orbit-layer-v1\",\"key\":"<<quote(o.key)
            <<",\"m\":"<<o.m<<",\"depth\":"<<o.depth<<",\"status\":"<<quote(status)
            <<",\"lower_bound\":"<<(stats.complete?o.depth+1:1)<<",\"upper_bound\":"<<(upper?std::to_string(o.depth):"null")
            <<",\"witness\":"<<(stats.witness[0].empty()?"null":"["+quote(stats.witness[0])+","+quote(stats.witness[1])+"]")
            <<",\"selected_mask_count\":"<<o.masks.size()<<",\"full_mask_family\":"<<(full?"true":"false")<<",\"selected_masks\":[";
        for(std::size_t i=0;i<o.masks.size();++i){if(i)report<<',';report<<o.masks[i];}
        report<<"],\"complement_closed_masks\":"<<(o.masks_valid?"true":"false")
            <<",\"fingerprint_subset_with_full_replay\":"<<(o.fingerprint_only?"true":"false")
            <<",\"full_family_injectivity_certified\":"<<(stats.complete?"true":"false")
            <<",\"selected_scalar_witness_verified\":"<<(stats.selected_witness_verified?"true":"false")
            <<",\"full_scalar_witness_verified\":"<<(stats.full_witness_verified?"true":"false")
            <<",\"threads\":"<<o.threads<<",\"prefix_bits\":"<<o.prefix_bits<<",\"bucket_bits\":"<<o.bucket_bits
            <<",\"bucket_count\":"<<(o.bucket_bits<=12?(1u<<o.bucket_bits):0)<<",\"bucket_bit_policy\":\"low-bits-of-minimum-orientation-hash\""
            <<",\"expected_representatives\":"<<stats.expected<<",\"count_pass_representatives\":"<<stats.count_generated
            <<",\"fill_pass_representatives\":"<<stats.fill_generated<<",\"replay_pass_representatives\":"<<stats.replay_generated
            <<",\"completed_buckets\":"<<stats.completed_buckets<<",\"bucket_sizes\":[";
        for(std::size_t i=0;i<stats.bucket_sizes.size();++i){if(i)report<<',';report<<stats.bucket_sizes[i];}
        report<<"],\"repeated_hash_groups\":"<<stats.repeated_hash_groups<<",\"repeated_hash_records\":"<<stats.repeated_hash_records
            <<",\"complete_profile_comparisons\":"<<stats.comparisons<<",\"force_hash_collisions\":"<<(o.force_hash?"true":"false")
            <<",\"self_symmetric_fingerprint_candidates\":"<<stats.self_symmetric_candidates
            <<",\"full_scalar_self_symmetry_checks\":"<<stats.full_self_checks
            <<",\"full_scalar_hash_replay_records\":"<<stats.full_replay_records
            <<",\"max_working_mib\":"<<o.max_mib<<",\"accounted_peak_payload_bytes\":"<<stats.peak_payload
            <<",\"memory_scope\":\"fingerprint/full-profile arrays plus conservative per-thread workspace; not an OS RSS cap\""
            <<",\"timeout_ms\":"<<o.timeout_ms<<",\"phase\":"<<quote(stats.phase)<<",\"seconds\":"<<seconds()
            <<",\"reason\":"<<quote(stats.reason)<<",\"exact_score_certified\":false,\"global_optimality_claim\":false}\n";
        report.close();if(!report){std::cerr<<"report write failed\n";return 1;}
    }
    std::cout<<status<<" depth="<<o.depth<<" count="<<stats.count_generated<<" seconds="<<seconds()<<" reason="<<stats.reason<<'\n';
    return stats.reason.empty()?0:1;
}

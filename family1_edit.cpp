#include "Family1EditSearch.h"
#include "Family1CliArtifacts.h"
#include <algorithm>
#include <csignal>
#include <cstdlib>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>

namespace fs = std::filesystem;
namespace {
using family1_cli::quote;
using family1_cli::sha256;
using Graph = family1::LargeGraph;
namespace edit = family1::edit;
volatile std::sig_atomic_t interrupted = 0;
void stop(int) { interrupted = 1; }
const char* boolean(bool value) { return value ? "true" : "false"; }
std::uint64_t number(const std::string& value) {
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("expected a nonnegative integer");
    return std::stoull(value);
}
struct Options { std::vector<std::string> keys; edit::Options search; fs::path out; bool resume = false; };
Options parse(int argc,char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        if (argument == "--help") {
            std::cout << "Family1Edit --graph KEY [--graph KEY ...] --target-m M --radius R --out DIR\n"
                " [--max-paths 10000 --max-candidates 1000 --seed 1088 --root-closure --resume]\n"
                "Option values require spaces. Radius1..3; intermediate sizes1..20.\n"
                "Primitive rooted edits are retarget, two-edge routing insertion, loop\n"
                "routing insertion, and their exact inverses. Every intermediate is accessible.\n"
                "Loops/coincident ports and arbitrary indegrees are allowed.\n"
                "Budgets are shared across depths, parents, patterns and frontier vertices.\n"
                "max-paths counts accepted nonempty primitive paths; max-candidates counts\n"
                "unique rooted target endpoints BEFORE optional all-accessible-root closure.\n"
                "Closure can emit up to20 times that many classes; rerooting is NOT an edit.\n"
                "All observed classes/path provenance are exported, including capped runs.\n"
                "No Family1 score is computed and an edit cap gives no global graph bound.\n"
                "Fresh DIR required. --resume reuses only identical intact completed output.\n";
            std::exit(0);
        }
        if (argument == "--resume") { options.resume = true; continue; }
        if (argument == "--root-closure") { options.search.root_closure = true; continue; }
        if (++i >= argc) throw std::invalid_argument("missing option value: " + argument);
        const std::string value = argv[i];
        if (argument == "--graph") options.keys.push_back(value);
        else if (argument == "--out") options.out = value;
        else if (argument == "--target-m") { auto n = number(value); if (n > 20) throw std::invalid_argument("target-m<=20"); options.search.target_m = static_cast<unsigned int>(n); }
        else if (argument == "--radius") { auto n = number(value); if (n > 3) throw std::invalid_argument("radius<=3"); options.search.radius = static_cast<unsigned int>(n); }
        else if (argument == "--max-paths") options.search.max_paths = number(value);
        else if (argument == "--max-candidates") options.search.max_candidates = number(value);
        else if (argument == "--seed") options.search.seed = number(value);
        else throw std::invalid_argument("unknown option: " + argument);
    }
    if (options.keys.empty() || options.out.empty() || !options.search.target_m || !options.search.radius
        || !options.search.max_paths || !options.search.max_candidates)
        throw std::invalid_argument("require parents, target-m1..20, radius1..3, positive budgets and --out");
    std::sort(options.keys.begin(),options.keys.end()); options.search.interrupted = &interrupted; return options;
}
void table(std::ostream& out,const Graph& graph) {
    out << '['; for (unsigned int s=0;s<graph.size();++s) { if(s)out<<',';out<<'['<<graph.ports[s][0]<<','<<graph.ports[s][1]<<']'; } out<<']';
}
std::string configuration(const Options& options,const std::vector<Graph>& parents,const std::string& executable_hash) {
    std::ostringstream out; out << "{\"schema\":1,\"method\":\"family1-budgeted-rooted-unit-edits-v1\",\"source_keys\":[";
    for(std::size_t i=0;i<options.keys.size();++i){if(i)out<<',';out<<quote(options.keys[i]);}
    out<<"],\"parents\":[";for(std::size_t i=0;i<parents.size();++i){if(i)out<<',';out<<quote(parents[i].key());}
    const auto& s=options.search;
    out<<"],\"target_m\":"<<s.target_m<<",\"radius\":"<<s.radius<<",\"max_paths\":"<<s.max_paths
        <<",\"max_candidates\":"<<s.max_candidates<<",\"seed\":"<<s.seed<<",\"root_closure\":"<<boolean(s.root_closure)
        <<",\"intermediate_size_cap\":20,\"max_candidates_scope\":\"unique-rooted-target-endpoints-before-root-closure\""
        <<",\"executable_sha256\":"<<quote(executable_hash)<<'}';return out.str();
}
void operation(std::ostream& out,const edit::Operation& op) {
    out<<"{\"kind\":"<<quote(edit::kind_name(op.kind))<<",\"vertex\":"<<op.vertex<<",\"new_target\":"<<op.new_target<<",\"edges\":[";
    for(std::size_t i=0;i<op.edges.size();++i){if(i)out<<',';const auto&e=op.edges[i];out<<"{\"source\":"<<e.source<<",\"port\":"<<e.port<<",\"target\":"<<e.target<<'}';}
    out<<"],\"outgoing\":["<<op.outgoing[0]<<','<<op.outgoing[1]<<"],\"outgoing_ports\":[";
    for(std::size_t i=0;i<op.outgoing_ports.size();++i){if(i)out<<',';out<<op.outgoing_ports[i];}out<<']';
    if(op.kind==edit::Kind::Retarget){const auto&e=op.edges[0];out<<",\"source\":"<<e.source<<",\"port\":"<<e.port<<",\"old_target\":"<<e.target;}
    out<<'}';
}
std::string paths_jsonl(const edit::Result& result) {
    std::ostringstream out;
    for(const auto&path:result.paths){
        out<<"{\"path_id\":"<<path.id<<",\"parent_key\":"<<quote(path.parent_key)<<",\"source_table\":";table(out,Graph::from_key(path.parent_key));
        out<<",\"endpoint_key\":"<<quote(path.endpoint_key)<<",\"endpoint_table\":";table(out,Graph::from_key(path.endpoint_key));
        out<<",\"distance_upper_bound\":"<<path.steps.size()<<",\"distance_exact\":false,\"root_fixed\":true,\"steps\":[";
        for(std::size_t i=0;i<path.steps.size();++i){if(i)out<<',';const auto&step=path.steps[i];
            out<<"{\"before_key\":"<<quote(step.before.key())<<",\"after_key\":"<<quote(step.after.key())<<",\"before_table\":";table(out,step.before);
            out<<",\"raw_after_edit\":";table(out,step.raw_after_edit);out<<",\"after_table\":";table(out,step.after);out<<",\"operation\":";operation(out,step.operation);out<<'}';}
        out<<"]}\n";
    }return out.str();
}
std::vector<std::size_t> candidate_order(const edit::Result& result) {
    // Fair prefixes across observed edit depths, with all roots of a shape in
    // one contiguous closure block. Canonical keys break every remaining tie.
    std::map<std::string,std::vector<std::size_t>> shapes;
    for(std::size_t i=0;i<result.candidates.size();++i)shapes[result.candidates[i].shape_key].push_back(i);
    std::map<unsigned int,std::vector<std::vector<std::size_t>>> depths;
    for(auto&[shape,indices]:shapes){
        unsigned int depth=4;for(auto index:indices)depth=std::min(depth,result.candidates[index].generation_depth);
        std::sort(indices.begin(),indices.end(),[&](auto a,auto b){return result.candidates[a].graph.key()<result.candidates[b].graph.key();});
        depths[depth].push_back(std::move(indices));
    }
    std::vector<std::size_t> order;std::size_t round=0;bool progress=true;
    while(progress){progress=false;for(const auto&[depth,groups]:depths)if(round<groups.size()){order.insert(order.end(),groups[round].begin(),groups[round].end());progress=true;}++round;}
    return order;
}
std::string candidates_jsonl(const edit::Result& result,const Options& options) {
    std::ostringstream out;std::uint64_t selection_index=0;
    for(auto index:candidate_order(result)){
        const auto&candidate=result.candidates[index];const auto&graph=candidate.graph;
        out<<"{\"schema\":1,\"m\":"<<graph.size()<<",\"key\":"<<quote(graph.key())<<",\"canonical_table\":";table(out,graph);
        out<<",\"shape_key\":"<<quote(candidate.shape_key)<<",\"root_closure_block\":"<<quote(candidate.shape_key)
            <<",\"discovery_index\":"<<candidate.discovery_index<<",\"selection_index\":"<<selection_index++
            <<",\"generation_depth\":"<<candidate.generation_depth<<",\"path_ids\":[";
        for(std::size_t i=0;i<candidate.path_ids.size();++i){if(i)out<<',';out<<candidate.path_ids[i];}
        out<<"],\"root_metadata\":[";
        for(std::size_t i=0;i<candidate.root_metadata.size();++i){if(i)out<<',';const auto&root=candidate.root_metadata[i];
            out<<"{\"path_id\":"<<root.path_id<<",\"endpoint_key\":"<<quote(root.endpoint_key)<<",\"root_in_endpoint\":"<<root.root_in_endpoint
                <<",\"root_fixed_path\":"<<boolean(root.root_fixed_path)<<'}';}
        out<<"],\"rooted_edit_distance_upper_bound\":";
        if(candidate.path_ids.empty())out<<"null";else{std::size_t distance=4;for(auto id:candidate.path_ids)distance=std::min(distance,result.paths[id].steps.size());out<<distance;}
        out<<",\"rooted_edit_distance_exact\":false,\"shape_roots_complete\":"<<boolean(options.search.root_closure)
            <<",\"status\":\"not-evaluated\",\"merge_length\":null,\"lower_bound\":1,\"upper_bound\":null,\"witness\":null}\n";
    }return out.str();
}
std::string summary_json(const edit::Result& result,const Options& options,const std::string& config_hash,
                         const std::string& candidates_hash,const std::string& paths_hash) {
    std::set<std::string> shapes;for(const auto&c:result.candidates)shapes.insert(c.shape_key);
    std::ostringstream out;out<<"{\"schema\":1,\"completed\":"<<boolean(!result.interrupted)<<",\"config_sha256\":"<<quote(config_hash)
        <<",\"target_m\":"<<options.search.target_m<<",\"radius\":"<<options.search.radius
        <<",\"candidate_count\":"<<result.candidates.size()<<",\"root_fixed_candidate_count\":"<<result.root_fixed_candidate_count
        <<",\"ordinary_shape_count\":"<<shapes.size()<<",\"accepted_paths\":"<<result.accepted_paths<<",\"materialized_paths\":"<<result.paths.size()
        <<",\"raw_proposals\":"<<result.raw_proposals<<",\"inaccessible_rejected\":"<<result.inaccessible_rejected
        <<",\"same_class_rejected\":"<<result.same_class_rejected<<",\"duplicate_neighbors_rejected\":"<<result.duplicate_neighbors_rejected
        <<",\"size_bound_pruned\":"<<result.size_bound_pruned<<",\"enumeration_complete\":"<<boolean(result.enumeration_complete)
        <<",\"supported_universe_complete\":"<<boolean(result.supported_universe_complete)<<",\"intermediate_size_cap\":20"
        <<",\"representation_capped\":"<<boolean(result.unsupported_size_paths_possible)
        <<",\"path_capped\":"<<boolean(result.path_capped)<<",\"candidate_capped\":"<<boolean(result.candidate_capped)
        <<",\"interrupted\":"<<boolean(result.interrupted)<<",\"root_closure\":"<<boolean(options.search.root_closure)
        <<",\"candidates_sha256\":"<<quote(candidates_hash)<<",\"paths_sha256\":"<<quote(paths_hash)
        <<",\"seconds\":"<<result.seconds<<",\"scoring_performed\":false,\"global_optimality_claim\":false"
        <<",\"budget_policy\":\"Remaining path/unique rooted endpoint budgets shared across depths; parents, patterns and frontier nodes round-robin. Root closure outside candidate budget.\""
        <<",\"enumeration_scope\":\"Target-size rooted classes reachable by root-fixed unit edit paths of length at most radius; intermediate sizes1..20. Capped strata give no exclusion certificate.\""
        <<",\"depths\":[";
    for(std::size_t i=0;i<result.depths.size();++i){if(i)out<<',';const auto&d=result.depths[i];out<<"{\"depth\":"<<d.depth<<",\"frontier_nodes\":"<<d.frontier_nodes
        <<",\"raw_proposals\":"<<d.raw_proposals<<",\"accepted_paths\":"<<d.accepted_paths<<",\"new_rooted_candidates\":"<<d.new_rooted_candidates
        <<",\"complete\":"<<boolean(d.complete)<<",\"path_capped\":"<<boolean(d.path_capped)<<",\"candidate_capped\":"<<boolean(d.candidate_capped)<<'}';}
    out<<"],\"parents\":[";
    for(std::size_t i=0;i<result.parents.size();++i){if(i)out<<',';const auto&p=result.parents[i];out<<"{\"key\":"<<quote(p.key)<<",\"raw_proposals\":"<<p.raw_proposals<<",\"accepted_paths\":"<<p.accepted_paths<<",\"patterns\":{";
        for(unsigned int k=0;k<5;++k){if(k)out<<',';out<<quote(edit::kind_name(static_cast<edit::Kind>(k)))<<":{\"raw_proposals\":"<<p.pattern_proposals[k]<<",\"accepted_paths\":"<<p.pattern_paths[k]<<'}';}out<<"}}";}
    out<<"]}";return out.str();
}
void publish_pair(const fs::path& out,const std::string& stem,const std::string& extension,const std::string& bytes) {
    family1_cli::publish(out/(stem+".sha256"),sha256(bytes)+"\n");family1_cli::publish(out/(stem+extension),bytes);
}
void validate_pair(const fs::path& out,const std::string& stem,const std::string& extension) {
    const auto bytes=family1_cli::read(out/(stem+extension));
    if(family1_cli::read(out/(stem+".sha256"))!=sha256(bytes)+"\n")throw std::runtime_error("corrupt "+stem+" checksum");
}
}
int main(int argc,char**argv) {
    try{
        auto options=parse(argc,argv);std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
        std::map<std::string,Graph> unique;for(const auto&key:options.keys){auto graph=Graph::from_key(key).canonical();unique.try_emplace(graph.key(),std::move(graph));}
        std::vector<Graph> parents;for(const auto&[key,graph]:unique)parents.push_back(graph);
        const auto config=configuration(options,parents,sha256(family1_cli::read(fs::absolute(argv[0]))));const auto config_hash=sha256(config);
        if(options.resume){
            if(family1_cli::read(options.out/"run.json")!=config)throw std::runtime_error("resume settings/executable differ from saved run");
            for(const auto&pair:std::vector<std::pair<std::string,std::string>>{{"run",".json"},{"candidates",".jsonl"},{"paths",".jsonl"},{"summary",".json"}})validate_pair(options.out,pair.first,pair.second);
            const auto saved=family1_cli::read(options.out/"summary.json");
            if(saved.find("\"completed\":true")==std::string::npos||saved.find("\"config_sha256\":"+quote(config_hash))==std::string::npos)
                throw std::runtime_error("incomplete/mismatched publication; preserve it and use a new output directory");
            if(saved.find("\"candidates_sha256\":"+quote(sha256(family1_cli::read(options.out/"candidates.jsonl"))))==std::string::npos
                ||saved.find("\"paths_sha256\":"+quote(sha256(family1_cli::read(options.out/"paths.jsonl"))))==std::string::npos)
                throw std::runtime_error("summary does not match published graph/path bytes");
            std::cout<<saved<<'\n';return 0;
        }
        if(fs::exists(options.out)&&!fs::is_empty(options.out))throw std::runtime_error("refusing nonempty output; use new directory or matching --resume");
        fs::create_directories(options.out);publish_pair(options.out,"run",".json",config);
        const auto result=edit::search(parents,options.search);const auto candidates=candidates_jsonl(result,options),paths=paths_jsonl(result);
        publish_pair(options.out,"candidates",".jsonl",candidates);publish_pair(options.out,"paths",".jsonl",paths);
        const auto summary=summary_json(result,options,config_hash,sha256(candidates),sha256(paths));publish_pair(options.out,"summary",".json",summary);
        std::cout<<summary<<'\n';return result.interrupted?2:0;
    }catch(const std::exception&error){std::cerr<<"Family1Edit: "<<error.what()<<'\n';return 1;}
}

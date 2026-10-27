#include "Family1JointPair.h"
#include "Family1JointSeeds.h"
#include "HardPairJointFinder.h"
#include "HardPairJointRolling.h"
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv)
{
    try {
        if (argc != 12 && argc != 13) throw std::runtime_error("keys k beam c priority diverse avoidcycles grouped prefixpairs expansions output [tie-mode]");
        hardpair::rolling::Options options;
        options.k = std::stoul(argv[2]); options.beam = std::stoul(argv[3]);
        const unsigned int c = std::stoul(argv[4]);
        options.priority = std::stoul(argv[5]); options.diverse = std::stoul(argv[6]);
        options.avoid_cycles = std::stoul(argv[7]);
        const bool grouped = std::stoul(argv[8]);
        const std::uint64_t prefix_pairs = std::stoull(argv[9]);
        options.max_expansions = std::stoull(argv[10]);
        if(argc==13)options.tie_mode=std::stoul(argv[12]);
        std::ifstream input(argv[1]); std::ofstream output(argv[11]);
        std::string key;
        while (input >> key) {
            auto graph = family1::LargeGraph::from_key(key);
            auto product = std::make_shared<family1::ExactPackedProduct>(graph);
            auto selector = family1::permutation_priority_selection(product, graph);
            family1::JointPairState root(product, graph.size(), selector);
            std::map<unsigned int, std::vector<family1::JointPairState>> groups;
            if (prefix_pairs) {
                auto plan = family1::joint_prefix_seeds(graph, 16, 65536, prefix_pairs, c);
                for (const auto& [first, second] : plan.pairs)
                    groups[first.size()].emplace_back(product, first, second, selector);
            } else {
                auto plan = hardpair::joint::divergence_starts(root, c);
                for (auto& start : plan.starts) groups[start.first_difference_depth].push_back(std::move(start.state));
            }
            hardpair::rolling::Result best;
            std::uint64_t nodes = 0, windows = 0, leaves = 0, attempts = 0, starts = 0, cycles = 0, capped = 0;
            for (auto& [length, group] : groups) {
                starts += group.size();
                auto run = [&](std::vector<family1::JointPairState> states) {
                    auto local = options;
                    if (best.found) local.max_length = best.length;
                    if (length > local.max_length) return;
                    auto result = hardpair::rolling::find_pair(std::move(states), local);
                    ++attempts; nodes += result.expanded_nodes; windows += result.windows; leaves += result.leaves;
                    cycles += result.cycles_avoided; capped += result.capped;
                    if (result.found && (!best.found || result.length < best.length ||
                        (result.length == best.length && std::tie(result.first,result.second) < std::tie(best.first,best.second)))) best = result;
                };
                if (grouped) run(std::move(group));
                else for (const auto& state : group) run({state});
            }
            std::vector<unsigned int> trace(best.found ? best.length + 1 : 0);
            if (best.found) {
                for (unsigned int mask = 0; mask < (1U << graph.size()); ++mask) {
                    unsigned int left=0,right=0;
                    for (unsigned int i=0;i<best.length;++i) {
                        left=graph.ports[left][(best.first[i]-'0')^((mask>>left)&1U)];
                        right=graph.ports[right][(best.second[i]-'0')^((mask>>right)&1U)];
                        trace[i+1]+=left!=right;
                    }
                    if(left!=right)throw std::logic_error("scalar witness failure");
                }
            }
            output << "{\"m\":"<<graph.size()<<",\"key\":\""<<key<<"\",\"k\":"<<options.k
                <<",\"beam\":"<<options.beam<<",\"common_depth\":"<<c<<",\"grouped\":"<<grouped
                <<",\"priority\":"<<options.priority<<",\"tie_mode\":"<<options.tie_mode<<",\"diverse\":"<<options.diverse
                <<",\"avoid_cycles\":"<<options.avoid_cycles<<",\"prefix_pairs\":"<<prefix_pairs
                <<",\"expanded_nodes\":"<<nodes<<",\"complete_windows\":"<<windows<<",\"leaves\":"<<leaves
                <<",\"attempts\":"<<attempts<<",\"starts\":"<<starts<<",\"capped_attempts\":"<<capped
                <<",\"cycles_avoided\":"<<cycles<<",\"upper_bound\":";
            if (best.found) output<<best.length;else output<<"null";
            output<<",\"witness\":[\""<<best.first<<"\",\""<<best.second<<"\"],\"Dtrace\":[";
            for(unsigned int i=0;i<trace.size();++i){if(i)output<<',';output<<trace[i];}
            output<<"]}\n";output.flush();
            std::cout << "k="<<options.k<<" B="<<options.beam<<" "<<key<<" upper="<<(best.found?std::to_string(best.length):"miss")
                      <<" nodes="<<nodes<<" caps="<<capped<<std::endl;
        }
    } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}

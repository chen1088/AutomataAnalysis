#pragma once

#include <generator>
#include <vector>
#include <set>
#include "RegPDFA.h"
#include "FullBinaryTreeGenerator.h"
#include "VectorNGenerator.h"
#include <boost/dynamic_bitset/dynamic_bitset.hpp>
using namespace std;
using boost::dynamic_bitset;

// Use C++23 std::generator to produce RegPDFA instances.
// Enumerates all maps f0,f1 : [0..n-1] -> [0..n-1], total n^(2n).

class RegPDFAGenerator
{
public:
   // Returns a std::generator that yields the strings for RegPDFA objects
   static generator<string> generate_size(unsigned int n)
   {
      if (n == 0) co_return;
      // first we generate the leaf states
      for (auto leaves : FullBinaryTreeGenerator::generate(n+1))
      {
         // Create a new RegPDFA instance for each set of leaves
         // put all prefixes of the leaves (excluding the last character) into a set, without any duplicates.
         std::set<dynamic_bitset<>> states;
         // sort the leaves by length in ascending order
         // std::sort(leaves.begin(), leaves.end(),
         //           [](const dynamic_bitset<>& a, const dynamic_bitset<>& b) {
         //              return a.size() < b.size();
         //           });
         // for any leaves we need each of them be paired with a prefix that is not longer than the leaf itself.
         // The prefix came from the leaves, can be other leaves.
         // We need to enumerate every such case.
         // for example, we have 01,001 as leaves.
         // 01 can be paired with _, 0, 00. 001 can be paired with _,0,00. So it is basically 3 by 3 = 9 cases.
         for (const auto leaf : leaves) {
            dynamic_bitset<> prefix = dynamic_bitset<>(0);
            for (size_t i = 0; i < leaf.size(); ++i) {
               states.insert(dynamic_bitset<>(prefix));
               prefix.push_back(leaf[i]);
            }
         }
         
         for(auto strings : generatepairsoftransitions(leaves, states))
         {
            string res = "";
            for(size_t i = 0; i < strings.size(); ++i)
            {
               res += strings[i];
               if(i != strings.size() - 1) res += ",";
            }
            co_yield res;
         }
      }
   }
   static generator<vector<string>> generatepairsoftransitions(vector<dynamic_bitset<>> leafstates, const set<dynamic_bitset<>> states)
   { 
      if (leafstates.empty()) {
         co_yield vector<string>{};
         co_return;
      }
      dynamic_bitset<> current = leafstates.back();
      leafstates.pop_back();
      vector<dynamic_bitset<>> leafstates_copy = leafstates;
      // find the ones in states whose length is smaller than the leafstate.
      generator<vector<string>> prev_results = generatepairsoftransitions(leafstates_copy, states);
      for (const auto& prev : prev_results) {
         for (const auto& state : states) {
            if(state.size() <= current.size())
            {
               string res = "";
               for(size_t i = 0; i < current.size(); ++i)
               {
                  res += (current[i] ? '1' : '0');
               }
               res += "-";
               if(state.size() == 0) res += "_";
               else 
               {
                  for(size_t i = 0; i < state.size(); ++i)
                  {
                     res += (state[i] ? '1' : '0');
                  }
               }
               vector<string> prev_copy = prev;
               prev_copy.push_back(res);
               co_yield prev_copy;
            }
         }
      }
   }
   static void test()
   {
      // Example usage: generate RegPDFA with 3 states
      cout<< "Generating RegPDFA with 3 states..." << endl;
      for (auto str : generate_size(3))
      {
         std::cout << "RegPDFA: " << str << std::endl;
      }
   }
};


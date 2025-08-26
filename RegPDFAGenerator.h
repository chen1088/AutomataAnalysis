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
   // Returns a std::generator that yields RegPDFA objects by const reference
   // (backed by the coroutine frame).
   static generator<RegPDFA> generate_size(unsigned int n)
   {
      if (n == 0) co_return;
      // first we generate the leaf states
      for (auto leaves : FullBinaryTreeGenerator::generate(n+3))
      {
         // Create a new RegPDFA instance for each set of leaves
         // put all prefixes of the leaves (excluding the last character) into a set, without any duplicates.
         std::set<dynamic_bitset<>> prefixes;
         for (size_t len = 1; len < leaves.size(); ++len) {
            // for (size_t start = 0; start <= leaves.size() - len; ++start) {
            //    dynamic_bitset<> prefix;
            //    for (size_t i = start; i < start + len - 1; ++i) {
            //       prefix.push_back(leaves[i]);
            //    }
            //    prefixes.insert(prefix);
            // }
         }
         // get the size of the set
         size_t num_states = prefixes.size();
         // generate a vector of size n and each with num_states elements
         for (auto transitions : VectorNGenerator::generate(num_states, n))
         {
            // create the string for the dfa
            string dfa_str="";
            for (const auto& prefix : prefixes) {
               //dfa_str += to_string(prefix) + ",";
            }
            RegPDFA pdfa;
            pdfa.initwithstring(dfa_str);
            co_yield pdfa;
         }
      }
   }
};




#pragma once
#include "PDFA.h"
#include<boost/dynamic_bitset/dynamic_bitset.hpp>
class RegPDFA :
    public PDFA
{
public:
   int maxidx;
   map<boost::dynamic_bitset<>, boost::dynamic_bitset<>> congruence;
   // for <k,v> pairs we only record the v's whose k's are more than 1
   // A complete congruence is that for any string s there can be three cases:
   // 1. s is in the map, this is good.
   // 2. s is not in the map, and s can be reduced, we solve the congruence of s.
   // 3. s is not in the map, and s cannot be reduced, by default the sc(c is any character) is congruent to sc.

   RegPDFA();
   RegPDFA(unsigned int s);
   void reset_enumeration();
   vector<unsigned int> get_transitions_0();
   vector<unsigned int> get_transitions_1();
   void next();
   static map<boost::dynamic_bitset<>,boost::dynamic_bitset<>> compute_product(map<boost::dynamic_bitset<>, boost::dynamic_bitset<>> a, map<boost::dynamic_bitset<>, boost::dynamic_bitset<>> b)
   {
      // we might need to use bi-map from boost library
      // we should assume that the transition table is complete
      map<boost::dynamic_bitset<>, boost::dynamic_bitset<>> res;
      map<pair<boost::dynamic_bitset<>,boost::dynamic_bitset<>>, boost::dynamic_bitset<>> temp;
      for (auto i : a)
      {
         for (auto j : b)
         {
            
         }
      }
      return res;
   }
   static map<boost::dynamic_bitset<>,boost::dynamic_bitset<>> renamestates(
      map<pair<boost::dynamic_bitset<>,boost::dynamic_bitset<>>, pair<boost::dynamic_bitset<>, boost::dynamic_bitset<>>> a)
   {
      map<boost::dynamic_bitset<>,boost::dynamic_bitset<>> res;
      // breadth first search
      

      return res;
   }
   static map<boost::dynamic_bitset<>, boost::dynamic_bitset<>> purge(map<boost::dynamic_bitset<>, boost::dynamic_bitset<>>)
   {
      map<boost::dynamic_bitset<>, boost::dynamic_bitset<>> res;
      // breadth first search

      return res;
   }
};


#pragma once
#include<map>
#include<vector>
#include <queue>
#include <stack>
#include <set>
#include <ranges>
#include<flint/fmpz_poly.h>
#include<flint/fmpz_mpoly.h>
#include"urgf.h"
#include"urgfdag.h"
using namespace std;
#include<boost/dynamic_bitset/dynamic_bitset.hpp>
using boost::dynamic_bitset;
class RegPDFA
{
public:
   bool is_end = false;
   unsigned int size;
   // a state label is defined by the shortest string that reaches the state.
   // We are not storing the states which have only one incoming transition.
   map<dynamic_bitset<>, dynamic_bitset<>> congruence0;
   map<dynamic_bitset<>, dynamic_bitset<>> congruence1;
   map<dynamic_bitset<>, set<dynamic_bitset<>>> reversecongruence0;
   map<dynamic_bitset<>, set<dynamic_bitset<>>> reversecongruence1;
   // for <k,v> pairs we only record the v's whose k's are more than 1
   // A complete congruence is that for any string s there can be three cases:
   // 1. s is in the map, this is good.
   // 2. s is not in the map, and s can be reduced, we solve the congruence of s.
   // 3. s is not in the map, and s cannot be reduced, by default the sc(c is any character) is congruent to sc.
   // Plan changed. Now congruences must be complete.
   urgfdag* dag;
   RegPDFA();
   RegPDFA(unsigned int s);
   RegPDFA(string s);
   void reset_enumeration();
   void next();
   dynamic_bitset<> reduce(dynamic_bitset<> currentstate, dynamic_bitset<> str);
   RegPDFA cartesian_product(RegPDFA other);
   
   urgfdag* compute_urgfdag(dynamic_bitset<> state);
   urgfdag* compute_urgfdag_plusplus(dynamic_bitset<> src, dynamic_bitset<> dst);
   urgfdag* compute_urgfdag_plusminus(dynamic_bitset<> src, dynamic_bitset<> dst);
   urgfdag* compute_urgfdag_minusminus(dynamic_bitset<> src, dynamic_bitset<> dst);
   urgfdag* compute_urgfdag_minusplus(dynamic_bitset<> src, dynamic_bitset<> dst);
   urgfdag* compute_urgfdag_selfloop(dynamic_bitset<> state);
   // Compute the urgf tree for some state.
   bool check_completeness();

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


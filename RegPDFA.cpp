#include "RegPDFA.h"

RegPDFA::RegPDFA()
{
   size = 0;
}

RegPDFA::RegPDFA(unsigned int s)
{
   size = s;
}

void RegPDFA::reset_enumeration()
{
   // TODO: implement this function
   is_end = false;
}

void RegPDFA::next()
{
   // TODO: implement this function
   is_end = true;
}

dynamic_bitset<> RegPDFA::reduce(dynamic_bitset<> currentstate, dynamic_bitset<> str)
{
   auto res = dynamic_bitset<>(size);
   // 1. s is in the map, this is good.
   if (congruence0.find(currentstate) != congruence0.end())
   {
      return congruence0[currentstate];
   }
   else if(congruence1.find(currentstate) != congruence1.end())
   {
      return congruence1[currentstate];
   }
   // 2. s is not in the map, and s can be reduced, we solve the congruence of s.

   // 3. s is not in the map, and s cannot be reduced, by default the sc(c is any character) is congruent to sc.
   return res;
}
bool RegPDFA::check_completeness()
{
   // Given congruence0 and congruence1, check if they are complete.
   // i.e. {01,00,110,111,101,100} is complete.
   // {01,00,110,111} is not complete. node 1 has one branch which means it is incomplete.
   // for every string in the map, check if they form a complete congruence
   // This function should never be called.
   map<int,set<dynamic_bitset<>>> q;
   for (auto i : congruence0)
   {
      q[i.first.count()].insert(i.first);
   }
   for (auto i : congruence1)
   {
      q[i.first.count()].insert(i.first);
   }   
   auto ks = std::views::keys(q);
   auto vectorkey = vector<int>(ks.begin(),ks.end());
   // from the largest to the smallest
   
   return true;
}
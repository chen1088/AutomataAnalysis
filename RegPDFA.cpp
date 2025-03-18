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
   // Given a current state and a string, reduce the state to the final state.
   if (str.count() == 0)
      return currentstate;
   for(auto i = 0;i<str.count();i++)
   {
      if(str[i])
      {
         if(congruence1.find(currentstate) != congruence1.end())
            currentstate=congruence1[currentstate];
         else
            currentstate.append(true);
      }
      else
      {
         if(congruence0.find(currentstate) != congruence0.end())
            currentstate=congruence0[currentstate];
         else
            currentstate.append(false);
      }
   }
   return currentstate;
}

RegPDFA RegPDFA::product(RegPDFA other)
{
   RegPDFA res(size+other.size);
   res.congruence0 = compute_product(congruence0,other.congruence0);
   res.congruence1 = compute_product(congruence1,other.congruence1);
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
      auto t = i.first;
      t.push_back(0);
      q[t.count()].insert(t);
   }
   for (auto i : congruence1)
   {
      auto t = i.first;
      t.push_back(1);
      q[t.count()].insert(t);
   }   
   auto ks = std::views::keys(q);
   auto vectorkey = vector<int>(ks.begin(),ks.end());
   // from the largest to the smallest
   int max = *max_element(vectorkey.begin(),vectorkey.end());
   for(auto i = max; i > 0; i--)
   {
      for(auto j : q[i])
      {
         auto jj = j.flip(j.count()-1); // check this flip.
         if(q[i].find(jj) == q[i].end())
            return false; // if j is not complete, return false
         else
         {
            auto jjj = j; // check this copy.
            jjj.pop_back();
            q[i-1].insert(jjj);
            q[i].erase(jj);
            q[i].erase(j);
         }
      }
   }
   return true;
}
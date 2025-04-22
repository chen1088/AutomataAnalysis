#include "RegPDFA.h"

RegPDFA::RegPDFA()
{
   size = 0;
}

RegPDFA::RegPDFA(unsigned int s)
{
   size = s;
}

RegPDFA::RegPDFA(string s)
{
   size = s.size();
   for(auto i = 0;i<s.size();i++)
   {
      if(s[i] == '0')
         congruence0[dynamic_bitset<>(i)] = dynamic_bitset<>(i+1);
      else
         congruence1[dynamic_bitset<>(i)] = dynamic_bitset<>(i+1);
   }
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

RegPDFA RegPDFA::cartesian_product(RegPDFA other)
{
   RegPDFA res(size+other.size);
   // Given two PDFA, compute the cartesian product of the two PDFA.
   // empty string is the initial state.
   map<pair<dynamic_bitset<>,dynamic_bitset<>>,dynamic_bitset<>> visited;
   queue<pair<dynamic_bitset<>,dynamic_bitset<>>> q;
   q.push({dynamic_bitset<>(0),dynamic_bitset<>(0)});
   visited[{dynamic_bitset<>(0),dynamic_bitset<>(0)}] = dynamic_bitset<>(0);
   while(!q.empty())
   {
      auto t = q.front();
      auto tstate = visited[t];//tstate is a label of current state.
      q.pop();
      auto t00 = congruence0[t.first];
      auto t10 = other.congruence0[t.second];
      if(visited.find({t00,t10}) == visited.end())
      //first state appending 0 is not visited
      {
         auto tstate0 = dynamic_bitset<>(tstate);
         tstate0.append(0);
         visited[{t00,t10}] = tstate0;
         res.congruence0[tstate] = tstate0;
         q.push({t00,t10});
      }
      auto t01 = congruence1[t.first];
      auto t11 = other.congruence1[t.second];
      if(visited.find({t01,t11}) == visited.end())
      //first state appending 1 is not visited
      {
         auto tstate1 = dynamic_bitset<>(tstate);
         tstate1.append(1);
         visited[{t01,t11}] = tstate1;
         res.congruence1[tstate] = tstate1;
         q.push({t01,t11});
      }
   }
   return res;
}

urgftree RegPDFA::compute_urgftree(dynamic_bitset<> state)
{
   // Given a state, compute the urgf tree of the state.
   // Find the state first. And get the whole state in a vector.
   vector<pair<dynamic_bitset<>, urgftree*>> stateswithurgf;
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
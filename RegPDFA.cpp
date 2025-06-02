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
urgfdag* RegPDFA::compute_urgfdag_plusplus(dynamic_bitset<> src, dynamic_bitset<> dst)
{
   // Given a source state and a destination state, compute the pairwise urgf from src to dst with selfloop on both included.
   if(src == dst)
   {
      // if src and dst are the same, we have to compute the selfloop.
      return compute_urgfdag_selfloop(src);
   }
   // now we assume src and dst are different.
   // incoming and outgoing transitions do not count selfloops.
   map<dynamic_bitset<>,map<dynamic_bitset<>,vector<urgfdag*>>> incoming_trans;
   map<dynamic_bitset<>,map<dynamic_bitset<>,vector<urgfdag*>>> outgoing_trans;
   map<dynamic_bitset<>,vector<urgfdag*>> selfloop_trans;
   // initialize a queue to store the states.
   queue<dynamic_bitset<>> q;
   for(auto i : congruence0)
   {
      if(i.first == src || i.first == dst)
      {
         // we leave out the starting state and the target state.
         continue;
      }
      q.push(i.first);
   }
   for(auto i : congruence0)
   {
      if(i.first == i.second)
      {
         selfloop_trans[i.first].push_back(new urgfdag(urgf_operation::ATOMX));
         continue;
      }
      incoming_trans[i.second][i.first].push_back(new urgfdag(urgf_operation::ATOMX));
      outgoing_trans[i.first][i.second].push_back(new urgfdag(urgf_operation::ATOMX));
   }
   for(auto i : congruence1)
   {
      if(i.first == i.second)
      {
         selfloop_trans[i.first].push_back(new urgfdag(urgf_operation::ATOMY));
         continue;
      }
      incoming_trans[i.second][i.first].push_back(new urgfdag(urgf_operation::ATOMY));
      outgoing_trans[i.first][i.second].push_back(new urgfdag(urgf_operation::ATOMY));
   }
   
   while(!q.empty())
   {
      auto t = q.front();
      q.pop();
      // eliminate one state.
      auto incoming = incoming_trans[t];
      auto outgoing = outgoing_trans[t];
      auto selfloop = selfloop_trans[t];
      if(selfloop_trans[t].size() > 1)
      {
         // if there are more than one selfloops, we have to collect them.
         auto newtree = new urgfdag(urgf_operation::ADD);
         for(auto i : selfloop_trans[t])
         {
            newtree->children.push_back(i);
         }
         selfloop_trans[t].clear();
         selfloop_trans[t].push_back(newtree);
      }
      for(auto i : incoming_trans[t])
      {
         // collect the parrelled transitions.
         if(i.second.size() == 0)
         {
            // if this is empty, why would we store it?
            cout<<"Error: empty incoming transition."<<endl;
         }
         else if(i.second.size() > 1)
         {
            // if this is more than one, we have to collect them.
            auto newtree = new urgfdag(urgf_operation::ADD);
            for(auto j : i.second)
            {
               newtree->children.push_back(j);
            }
            i.second.clear();
            i.second.push_back(newtree);
            // update the outgoing transitions as well.
            outgoing_trans[i.first][t].clear();
            outgoing_trans[i.first][t].push_back(newtree);
         }
         
         for(auto j: outgoing_trans[t])
         {
            //collect the outgoing transitions.
            if(j.second.size() == 0)
            {
               // if this is empty, why would we store it?
               cout<<"Error: empty outgoing transition."<<endl;
            }
            else if(j.second.size() > 1)
            {
               // if this is more than one, we have to collect them.
               auto newtree = new urgfdag(urgf_operation::ADD);
               for(auto k : j.second)
               {
                  newtree->children.push_back(k);
               }
               j.second.clear();
               j.second.push_back(newtree);
               // update the incoming transitions as well.
               incoming_trans[j.first][t].clear();
               incoming_trans[j.first][t].push_back(newtree);
            }
            if(selfloop.size()==0)
            {
               // concatenate
               auto newtree = new urgfdag(urgf_operation::MULTIPLY);
               newtree->children.push_back(i.second[0]);
               newtree->children.push_back(j.second[0]);
               // replace with the new dag.
               // now i->t->j becomes i->j
               // remove i->t and remove t->j
               incoming_trans[i.first].erase(t);
               outgoing_trans[t].erase(j.first);
               if(i.first == j.first)
               {
                  // if i and j are the same, it is the selfloop.
                  selfloop_trans[i.first].push_back(newtree);
               }
               else
               {
                  // if i and j are not the same, add this i->j to incoming and outgoing transitions.
                  incoming_trans[i.first][j.first].push_back(newtree);
                  outgoing_trans[j.first][i.first].push_back(newtree);
               }
            }
            else if(selfloop.size() == 1)
            {
               // oneinverse then concatenate
               auto newtree = new urgfdag(urgf_operation::ONEMINUSINVERSE);
               newtree->children.push_back(selfloop[0]);
               auto newtree2 = new urgfdag(urgf_operation::MULTIPLY);
               newtree2->children.push_back(i.second[0]);
               newtree2->children.push_back(newtree);
               newtree2->children.push_back(j.second[0]);
               // replace with the new dag.
               // now i->t->j becomes i->j
               incoming_trans[i.first].erase(t);
               outgoing_trans[t].erase(j.first);
               selfloop_trans[t].clear();
               if(i.first == j.first)
               {
                  // if i and j are the same, it is the selfloop.
                  selfloop_trans[i.first].push_back(newtree2);
               }
               else
               {
                  // if i and j are not the same, add this i->j to incoming and outgoing transitions.
                  incoming_trans[i.first][j.first].push_back(newtree2);
                  outgoing_trans[j.first][i.first].push_back(newtree2);
               }
            }
            else
            {
               // not possible
               cout<<"Error: more than one selfloop."<<endl;
            }
         }
      }
   }
   // union the selfloop incoming and outgoing transitions.
   if(selfloop_trans[src].size() >= 1)
   {
      // if there are selfloops, we have to collect them.
      auto newtree = new urgfdag(urgf_operation::ADD);
      for(auto i : selfloop_trans[src])
      {
         newtree->children.push_back(i);
      }
      selfloop_trans[src].clear();
      selfloop_trans[src].push_back(newtree);
   }
   if(selfloop_trans[dst].size() >= 1)
   {
      // if there are selfloops, we have to collect them.
      auto newtree = new urgfdag(urgf_operation::ADD);
      for(auto i : selfloop_trans[dst])
      {
         newtree->children.push_back(i);
      }
      selfloop_trans[dst].clear();
      selfloop_trans[dst].push_back(newtree);
   }
   if(incoming_trans[src][dst].size() >= 1)
   {
      // if there are incoming transitions, we have to collect them.
      auto newtree = new urgfdag(urgf_operation::ADD);
      for(auto i : incoming_trans[src][dst])
      {
         newtree->children.push_back(i);
      }
      incoming_trans[src][dst].clear();
      incoming_trans[src][dst].push_back(newtree);
      outgoing_trans[dst][src].clear();
      outgoing_trans[dst][src].push_back(newtree);
   }
   if(incoming_trans[dst][src].size() >= 1)
   {
      // if there are incoming transitions from the destination state, we have to collect them.
      auto newtree = new urgfdag(urgf_operation::ADD);
      for(auto i : incoming_trans[dst][src])
      {
         newtree->children.push_back(i);
      }
      incoming_trans[dst][src].clear();
      incoming_trans[dst][src].push_back(newtree);
      outgoing_trans[src][dst].clear();
      outgoing_trans[src][dst].push_back(newtree);
   }
   // the result includes both selfloops.
   if(incoming_trans[dst][src].size() !=0)
   {
      // first part
      auto res = new urgfdag(urgf_operation::MULTIPLY);
      auto selfloopsrc = new urgfdag(urgf_operation::ONEMINUSINVERSE);
      if(selfloop_trans[src].size() != 0)
      {
         selfloopsrc->children.push_back(selfloop_trans[src][0]);
         res->children.push_back(selfloopsrc);
      }
      res->children.push_back(incoming_trans[dst][src][0]);
      // second part
      if(incoming_trans[src][dst].size() != 0)
      {
         // reduce a new selfloop that is dst->src(->src..)->dst.
         auto newselfloopdst = new urgfdag(urgf_operation::MULTIPLY);
         newselfloopdst->children.push_back(incoming_trans[src][dst][0]);
         if(selfloop_trans[src].size() != 0)
         {  
            newselfloopdst->children.push_back(selfloopsrc);
         }
         newselfloopdst->children.push_back(incoming_trans[src][dst][0]);
         // union the selfloop on dst.
         if(selfloop_trans[dst].size() != 0)
         {
            auto oldselfloopdst = new urgfdag(urgf_operation::ONEMINUSINVERSE);
            oldselfloopdst->children.push_back(selfloop_trans[dst][0]);
            auto allselfloopdst = new urgfdag(urgf_operation::ADD);
            allselfloopdst->children.push_back(oldselfloopdst);
            allselfloopdst->children.push_back(newselfloopdst);
            res->children.push_back(allselfloopdst);
            return res;
         }
         else
         {
            auto allselfloopdst = new urgfdag(urgf_operation::ONEMINUSINVERSE);
            allselfloopdst->children.push_back(newselfloopdst);
            res->children.push_back(allselfloopdst);
            return res;
         }
      }
      else
      {
         if(selfloop_trans[dst].size() != 0)
         {
            // if there is a selfloop on dst, concatenate it.
            auto allselfloopdst = new urgfdag(urgf_operation::ONEMINUSINVERSE);
            allselfloopdst->children.push_back(selfloop_trans[dst][0]);
            res->children.push_back(allselfloopdst);
            return res;
         }
         else
         {
            // if there is no selfloop on dst, and there is no transition from dst to src, that is an empty!
            return new urgfdag(urgf_operation::EMPTY);
         }
      } 
   }
   else
      return new urgfdag(urgf_operation::EMPTY);
}

urgfdag* RegPDFA::compute_urgfdag(dynamic_bitset<> state)
{
   return compute_urgfdag_plusplus(dynamic_bitset<>(0),state);
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
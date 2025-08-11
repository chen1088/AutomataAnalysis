#include "RegPDFA.h"

void eliminate_state(map<dynamic_bitset<>,map<dynamic_bitset<>,vector<urgfdag*>>> &incoming_trans,
                     map<dynamic_bitset<>,map<dynamic_bitset<>,vector<urgfdag*>>> &outgoing_trans,
                     map<dynamic_bitset<>,vector<urgfdag*>> &selfloop_trans,
                     dynamic_bitset<> t);
void print_transitions(map<dynamic_bitset<>,map<dynamic_bitset<>,vector<urgfdag*>>> transitions)
{
   for(auto i : transitions)
   {
      string i_str;
      boost::to_string(i.first, i_str);
      reverse(i_str.begin(), i_str.end());
      cout << "From state: " << i_str << endl;
      for(auto j : i.second)
      {
         string j_str;
         boost::to_string(j.first, j_str);
         reverse(j_str.begin(), j_str.end());
         cout << "  To state: " << j_str << " via " << j.second.size() << " transitions." << endl;
         for(auto k : j.second)
         {
            auto urgfstr = k->resolvetourgf_nocache().to_string();
            cout << "    urgf: " << urgfstr << endl;
         }
      }
   }
}
void print_incomingtransitions(map<dynamic_bitset<>,map<dynamic_bitset<>,vector<urgfdag*>>> incoming_trans)
{
   cout << "Incoming transitions:" << endl;
   for(auto i : incoming_trans)
   {
      string i_str;
      boost::to_string(i.first, i_str);
      reverse(i_str.begin(), i_str.end());
      for(auto j : i.second)
      {
         string j_str;
         boost::to_string(j.first, j_str);
         reverse(j_str.begin(), j_str.end());
         cout << j_str << " to " << i_str<< " via " << j.second.size() << " transitions." << endl;
         for(auto k : j.second)
         {
            auto urgfstr = k->resolvetourgf_nocache().to_string();
            cout << "    urgf: " << urgfstr << endl;
         }
      }
   }
}
void print_outgoingtransitions(map<dynamic_bitset<>,map<dynamic_bitset<>,vector<urgfdag*>>> outgoing_trans)
{
   cout << "Outgoing transitions:" << endl;
   for(auto i : outgoing_trans)
   {
      string i_str;
      boost::to_string(i.first, i_str);
      reverse(i_str.begin(), i_str.end());
      for(auto j : i.second)
      {
         string j_str;
         boost::to_string(j.first, j_str);
         reverse(j_str.begin(), j_str.end());
         cout << i_str << " to " << j_str << " via " << j.second.size() << " transitions." << endl;
         for(auto k : j.second)
         {
            auto urgfstr = k->resolvetourgf_nocache().to_string();
            cout << "    urgf: " << urgfstr << endl;
         }
      }
   }
}
void print_selflooptransitions(map<dynamic_bitset<>,vector<urgfdag*>> selfloop_trans)
{
   for(auto i : selfloop_trans)
   {
      string i_str;
      boost::to_string(i.first, i_str);
      reverse(i_str.begin(), i_str.end());
      cout << "Self-loop at state: " << i_str << endl;
      for(auto k : i.second)
      {
         auto urgfstr = k->resolvetourgf_nocache().to_string();
         cout << "    urgf: " << urgfstr << endl;
      }
   }
}

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
   initwithstring(s);
}

RegPDFA::~RegPDFA()
{
   if(dag != nullptr)
      delete dag;
}
void RegPDFA::initwithstring(string s)
{
   // the format of the string is "2 001-100,01-0,11-_"
   // the first number is the number of leaf states.
   // _ is the empty string.
   // the second part is the transitions.
   stringstream ss(s);
   int leaf_count;
   ss >> leaf_count;

   // Read the transitions.
   string transitions;
   ss >> transitions;

   // Parse the transitions.
   stringstream trans_ss(transitions);
   string transition;
   set<dynamic_bitset<>> src_prefixes;
   while (getline(trans_ss, transition, ','))
   {
      // Each transition is in the format "src-dst"
      stringstream trans_pair(transition);
      dynamic_bitset<> src, dst;
      string src_str, dst_str;
      getline(trans_pair, src_str, '-');
      reverse(src_str.begin(), src_str.end()); // reverse the string to match the bit order
      getline(trans_pair, dst_str);
      reverse(dst_str.begin(), dst_str.end()); // reverse the string to match the bit order
      src = dynamic_bitset<>(src_str);
      
      if (dst_str == "_")
      {
         // If the destination is "_", it means it is an empty state.
         dst = dynamic_bitset<>(0);
      }
      else
      {
         dst = dynamic_bitset<>(dst_str);
      }

      if(src_prefixes.find(src) != src_prefixes.end())
      {
         // if the src is already in the prefixes, we do not need to add it again.
         continue;
      }
      src_prefixes.insert(src);
      dynamic_bitset<> buffer(0);
      dynamic_bitset<> buffer_append(0);
      buffer_append.push_back(src[0]);
      for(int i = 0; i < src.size()-1; i++)
      {
         // add all prefixes of src to the transition table.
         if(issetransition(buffer, src[i]))
         {
            // if the transition already exists, we do not need to add it again.
            continue;
         }
         settransition(buffer, buffer_append, src[i]);
         buffer.push_back(src[i]);
         buffer_append.push_back(src[i+1]);
      }
      dynamic_bitset<> src_pop = src;
      src_pop.pop_back(); // remove the last character.
      if(issetransition(src_pop, src[src.size()-1]))
      {
         // if the transition already exists, we do not need to add it again.
         continue;
      }
      settransition(src_pop, dst, src[src.size()-1]);
   }
   size = leaf_count;
   // check completeness of the pdfa.
   
   return;
}
string RegPDFA::to_string()
{
   stringstream ss;
   ss << "RegPDFA with size: " << congruence0.size() << endl;
   ss << "Congruence0: " << endl;
   for (const auto& pair : congruence0)
   {
      string pair_first_reversed;
      boost::to_string(pair.first, pair_first_reversed);
      reverse(pair_first_reversed.begin(), pair_first_reversed.end());
      string pair_second_reversed;
      boost::to_string(pair.second, pair_second_reversed);
      reverse(pair_second_reversed.begin(), pair_second_reversed.end());
      ss << pair_first_reversed << " -> " << pair_second_reversed << endl;
   }
   ss << "Congruence1: " << endl;
   for (const auto& pair : congruence1)
   {
      string pair_first_reversed;
      boost::to_string(pair.first, pair_first_reversed);
      reverse(pair_first_reversed.begin(), pair_first_reversed.end());
      string pair_second_reversed;
      boost::to_string(pair.second, pair_second_reversed);
      reverse(pair_second_reversed.begin(), pair_second_reversed.end());
      ss << pair_first_reversed << " -> " << pair_second_reversed << endl;
   }
   return ss.str();
}

void RegPDFA::settransition(dynamic_bitset<> src, dynamic_bitset<> dst, char c)
{
   // Given a source state and a destination state, set the transition.
   if(c == '0')
   {
      // if c is 0, it is a congruence0.
      congruence0[src] = dst;
   }
   else if(c == '1')
   {
      // if c is 1, it is a congruence1.
      congruence1[src] = dst;
   }
}

bool RegPDFA::issetransition(dynamic_bitset<> src, char c)
{
   // Check if there is a transition from src with character c.
   if(c == '0')
   {
      return congruence0.contains(src);
   }
   else if(c == '1')
   {
      return congruence1.contains(src);
   }
   return false;
}
bool RegPDFA::issetransition(dynamic_bitset<> src, bool b)
{
   // Check if there is a transition from src with boolean b.
   if(b)
   {
      return congruence1.contains(src);
   }
   else
   {
      return congruence0.contains(src);
   }
}
void RegPDFA::settransition(dynamic_bitset<> src, dynamic_bitset<> dst, bool b)
{
   // Given a source state and a destination state, set the transition.
   if(b)
   {
      // if b is true, it is a congruence1.
      congruence1[src] = dst;
   }
   else
   {
      // if b is false, it is a congruence0.
      congruence0[src] = dst;
   }
}

dynamic_bitset<> RegPDFA::reduce(dynamic_bitset<> str)
{
   // Given a current state and a string, reduce the state to the final state.
   if(str.size() == 0)
   {
      // if the string is empty, return the starting state.
      return dynamic_bitset<>(0);
   }
   else if(str[str.size() - 1] == false)
   {
      auto strpopped = dynamic_bitset<>(str);
      strpopped.pop_back(); // remove the last character.
      return congruence0[reduce(strpopped)];
   }
   else
   {
      auto strpopped = dynamic_bitset<>(str);
      strpopped.pop_back(); // remove the last character.
      return congruence1[reduce(strpopped)];
   }
}

RegPDFA RegPDFA::cartesian_product(RegPDFA other)
{
   RegPDFA res;
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
      auto t00 = dynamic_bitset<>(t.first);
      t00.push_back(false);
      t00 = reduce(t00);
      auto t10 = dynamic_bitset<>(t.second);
      t10.push_back(false);
      t10 = other.reduce(t10);
      if(visited.find({t00,t10}) == visited.end())
      //first state appending 0 is not visited
      {
         auto tstate0 = dynamic_bitset<>(tstate);
         tstate0.push_back(false);
         visited[{t00,t10}] = tstate0;
         res.settransition(tstate,tstate0,false);
         q.push({t00,t10});
      }
      else
      {
         // t00,t10 the dst is found.
         // we can set the transition from tstate to tstate0.
         res.settransition(tstate, visited[{t00,t10}], false);
      }
      auto t01 = dynamic_bitset<>(t.first);
      t01.push_back(true); // append 1 to the first state.
      t01 = reduce(t01);
      auto t11 = dynamic_bitset<>(t.second);
      t11.push_back(true);
      t11 = other.reduce(t11);
      if(visited.find({t01,t11}) == visited.end())
      //first state appending 1 is not visited
      {
         auto tstate1 = dynamic_bitset<>(tstate);
         tstate1.push_back(true);
         visited[{t01,t11}] = tstate1;
         res.settransition(tstate,tstate1,true);
         q.push({t01,t11});
      }
      else
      {
         // t01,t11 the dst is found.
         // we can set the transition from tstate to tstate1.
         res.settransition(tstate, visited[{t01,t11}], true);
      }
   }
   return res;
}
vector<dynamic_bitset<>> RegPDFA::getallstates()
{
   // return all states in the PDFA.
   vector<dynamic_bitset<>> res;
   for(auto i : congruence0)
   {
      res.push_back(i.first);
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
   stack<dynamic_bitset<>> q;
   auto allstates = getallstates();
   for(auto i : allstates)
   {
      if(i != src && i != dst)
      {
         q.push(i);
      }
      auto i0 = dynamic_bitset<>(i);
      i0.push_back(false);
      auto i1 = dynamic_bitset<>(i);
      i1.push_back(true);
      auto trans0 = reduce(i0);
      auto trans1 = reduce(i1);
      if(trans0 == i)
      {
         selfloop_trans[i].push_back(new urgfdag(urgf_operation::ATOMX));
      }
      else
      {
         incoming_trans[trans0][i].push_back(new urgfdag(urgf_operation::ATOMX));
         outgoing_trans[i][trans0].push_back(new urgfdag(urgf_operation::ATOMX)); 
      }
      if(trans1 == i)
      {
         selfloop_trans[i].push_back(new urgfdag(urgf_operation::ATOMY));
      }
      else
      {
         incoming_trans[trans1][i].push_back(new urgfdag(urgf_operation::ATOMY));
         outgoing_trans[i][trans1].push_back(new urgfdag(urgf_operation::ATOMY));
      }
   }
   // print_incomingtransitions(incoming_trans);
   // print_outgoingtransitions(outgoing_trans);
   // print_selflooptransitions(selfloop_trans);

   while(!q.empty())
   {
      auto t = q.top();
      q.pop();
      // eliminate one state.
      eliminate_state(incoming_trans, outgoing_trans, selfloop_trans, t);
      
   }
   // union the selfloop incoming and outgoing transitions.
   if(selfloop_trans[src].size() >= 1)
   {
      // if there are selfloops, we have to collect them.
      auto newtree = new urgfdag(urgf_operation::ADD);
      for(auto i : selfloop_trans[src])
      {
         newtree->add_child(i);
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
         newtree->add_child(i);
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
         newtree->add_child(i);
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
         newtree->add_child(i);
      }
      incoming_trans[dst][src].clear();
      incoming_trans[dst][src].push_back(newtree);
      outgoing_trans[src][dst].clear();
      outgoing_trans[src][dst].push_back(newtree);
   }
   print_incomingtransitions(incoming_trans);
   print_outgoingtransitions(outgoing_trans);
   print_selflooptransitions(selfloop_trans);
   // the result includes both selfloops.
   if(incoming_trans[dst][src].size() !=0)
   {
      // first part
      auto res = new urgfdag(urgf_operation::MULTIPLY);
      auto selfloopsrc = new urgfdag(urgf_operation::ONEMINUSINVERSE);
      if(selfloop_trans[src].size() != 0)
      {
         selfloopsrc->add_child(selfloop_trans[src][0]);
         res->add_child(selfloopsrc);
      }
      res->add_child(incoming_trans[dst][src][0]);
      // second part
      if(incoming_trans[src][dst].size() != 0)
      {
         // reduce a new selfloop that is dst->src(->src..)->dst.
         auto newselfloopdst = new urgfdag(urgf_operation::MULTIPLY);
         newselfloopdst->add_child(incoming_trans[src][dst][0]);
         if(selfloop_trans[src].size() != 0)
         {  
            newselfloopdst->add_child(selfloopsrc);
         }
         newselfloopdst->add_child(incoming_trans[dst][src][0]);
         // union the selfloop on dst.
         if(selfloop_trans[dst].size() != 0)
         {
            auto allselfloopdst = new urgfdag(urgf_operation::ADD);
            allselfloopdst->add_child(selfloop_trans[dst][0]);
            allselfloopdst->add_child(newselfloopdst);
            auto allselfloopdstoneminusinverse = new urgfdag(urgf_operation::ONEMINUSINVERSE);
            allselfloopdstoneminusinverse->add_child(allselfloopdst);
            res->add_child(allselfloopdstoneminusinverse);
            return res;
         }
         else
         {
            auto allselfloopdst = new urgfdag(urgf_operation::ONEMINUSINVERSE);
            allselfloopdst->add_child(newselfloopdst);
            res->add_child(allselfloopdst);
            return res;
         }
      }
      else
      {
         if(selfloop_trans[dst].size() != 0)
         {
            // if there is a selfloop on dst, concatenate it.
            auto allselfloopdst = new urgfdag(urgf_operation::ONEMINUSINVERSE);
            allselfloopdst->add_child(selfloop_trans[dst][0]);
            res->add_child(allselfloopdst);
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
urgfdag* RegPDFA::compute_urgfdag_selfloop(dynamic_bitset<> state)
{
   // TODO: compute the selfloop for the state.
   return new urgfdag(urgf_operation::EMPTY);
}

urgfdag* RegPDFA::compute_urgfdag_minusminus(dynamic_bitset<> src, dynamic_bitset<> dst)
{
   // TODO: compute the minusminus for the state.
   return new urgfdag(urgf_operation::EMPTY);
}
urgfdag* RegPDFA::compute_urgfdag_minusplus(dynamic_bitset<> src, dynamic_bitset<> dst)
{
   // TODO: compute the minusplus for the state.
   return new urgfdag(urgf_operation::EMPTY);
}
urgfdag* RegPDFA::compute_urgfdag_plusminus(dynamic_bitset<> src, dynamic_bitset<> dst)
{
   // TODO: compute the plusminus for the state.
   return new urgfdag(urgf_operation::EMPTY);
}

bool RegPDFA::check_completeness()
{
   // Given congruence0 and congruence1, check if they are complete.
   // i.e. {01,00,110,111,101,100} is complete.
   // {01,00,110,111} is not complete. node 1 has one branch which means it is incomplete.
   // for every string in the map, check if they form a complete congruence
   // This function should never be called.
   map<int,set<dynamic_bitset<>>> q;
   auto allstates = getallstates();
   for(auto i : allstates)
   {
      // add all states to the queue.
      q[i.count()].insert(i);
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

void eliminate_state(map<dynamic_bitset<>,map<dynamic_bitset<>,vector<urgfdag*>>> &incoming_trans,
                     map<dynamic_bitset<>,map<dynamic_bitset<>,vector<urgfdag*>>> &outgoing_trans,
                     map<dynamic_bitset<>,vector<urgfdag*>> &selfloop_trans,
                     dynamic_bitset<> t)
{
   if(selfloop_trans[t].size() > 1)
   {
      // if there are more than one selfloops, we have to collect them.
      auto newtree = new urgfdag(urgf_operation::ADD);
      for(auto i : selfloop_trans[t])
      {
         newtree->add_child(i);
      }
      selfloop_trans[t].clear();
      selfloop_trans[t].push_back(newtree);
   }
   set<dynamic_bitset<>> markedasdelete_incoming;
   set<dynamic_bitset<>> markedasdelete_outgoing;
   for(auto i : incoming_trans[t])
   {
      // collect the parrelled transitions.
      if(i.second.size() == 0)
      {
         // This only happens if the state is the starting state.
         cout<<"Error: empty incoming transition."<<endl;
      }
      else if(i.second.size() > 1)
      {
         // if this is more than one, we have to collect them.
         auto newtree = new urgfdag(urgf_operation::ADD);
         for(auto j : i.second)
         {
            newtree->add_child(j);
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
               newtree->add_child(k);
            }
            j.second.clear();
            j.second.push_back(newtree);
            // update the incoming transitions as well.
            incoming_trans[j.first][t].clear();
            incoming_trans[j.first][t].push_back(newtree);
         }
         if(selfloop_trans[t].size()==0)
         {
            // concatenate
            auto newtree = new urgfdag(urgf_operation::MULTIPLY);
            newtree->add_child(i.second[0]);
            newtree->add_child(j.second[0]);
            // replace with the new dag.
            // now i->t->j becomes i->j
            if(i.first == j.first)
            {
               // if i and j are the same, it is the selfloop.
               selfloop_trans[i.first].push_back(newtree);
            }
            else
            {
               // if i and j are not the same, add this i->j to incoming and outgoing transitions.
               incoming_trans[j.first][i.first].push_back(newtree);
               outgoing_trans[i.first][j.first].push_back(newtree);
            }
         }
         else if(selfloop_trans[t].size() == 1)
         {
            // oneinverse then concatenate
            auto newtree = new urgfdag(urgf_operation::ONEMINUSINVERSE);
            newtree->add_child(selfloop_trans[t][0]);
            auto newtree2 = new urgfdag(urgf_operation::MULTIPLY);
            newtree2->add_child(i.second[0]);
            newtree2->add_child(newtree);
            newtree2->add_child(j.second[0]);
            // replace with the new dag.
            // now i->t->j becomes i->j
            if(i.first == j.first)
            {
               // if i and j are the same, it is the selfloop.
               selfloop_trans[i.first].push_back(newtree2);
            }
            else
            {
               // if i and j are not the same, add this i->j to incoming and outgoing transitions.
               incoming_trans[j.first][i.first].push_back(newtree2);
               outgoing_trans[i.first][j.first].push_back(newtree2);
            }
         }
         else
         {
            // not possible
            cout<<"Error: more than one selfloop."<<endl;
         }
      }
   }
   selfloop_trans.erase(t);
   for(auto k:incoming_trans[t])
   {
      markedasdelete_incoming.insert(k.first);
   }
   for(auto k: markedasdelete_incoming)
   {
      outgoing_trans[k].erase(t);
   }
   for(auto k: outgoing_trans[t])
   {
      markedasdelete_outgoing.insert(k.first);
   }
   for(auto k: markedasdelete_outgoing)
   {
      incoming_trans[k].erase(t);
   }
   outgoing_trans.erase(t);
   incoming_trans.erase(t);
   

}
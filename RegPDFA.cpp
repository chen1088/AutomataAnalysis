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
   initwithstring(s);
}

RegPDFA::~RegPDFA()
{
   // if(dag != nullptr)
   //    delete dag;
}
void RegPDFA::initwithstring(string s)
{
   // the format of the string is "001-100,01-0,11-_"
   // _ is the empty string.
   // the transitions are in the format of pair of "pppc-qqqq".
   stringstream ss(s);

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

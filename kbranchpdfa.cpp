#include"kbranchpdfa.h"
#include"VectorEnumerator.h"
kbranchpdfa::kbranchpdfa()
{
   size = 0;
}
kbranchpdfa::kbranchpdfa(unsigned int s)
{
   size = s;
}
kbranchpdfa::kbranchpdfa(string s) : RegPDFA(s)
{
   initwithstring(s);
}
kbranchpdfa* kbranchpdfa::next()
{
   // todo: implement this function
   return new kbranchpdfa(size + 1);
}
string kbranchpdfa::to_string()
{
   stringstream ss;
   ss << "kbranchpdfa with size: " << size << endl;
   ss << "Congruences: " << endl;
   for (const auto& pair : congruences)
   {
      ss << pair.first << " -> " << pair.second << endl;
   }
   return ss.str();
}

dynamic_bitset<> kbranchpdfa::reduce(dynamic_bitset<> str)
{
   // Reduce the k-branch PDFA state.
   if (str.size() == 0)
   {
      // If the string is empty, return the current state.
      return dynamic_bitset<>(0);
   }
   else
   {
      auto strpopped = dynamic_bitset<>(str);
      strpopped.pop_back(); 
      auto reduced = kbranchpdfa::reduce(strpopped);
      reduced.append(str[str.size() - 1]); 
      if(congruences.find(reduced) == congruences.end())
      {
         // if the reduced state is not found, we ignore this character.
         reduced.flip(reduced.size() - 1); // flip the last character.
         if(congruences.find(reduced) == congruences.end())
         {
            cout<<"something is wrong, reduced state not found: "<< reduced << endl;
            // treat it as a selfloop.
            reduced.pop_back(); 
            return reduced;
         }
         else
         {
            return congruences[reduced];
         }
         return congruences[reduced];
      }
      else
      {
         return congruences[reduced];
      }
   }
}
vector<dynamic_bitset<>> kbranchpdfa::getallstates()
{
   // Return all states in the k-branch PDFA.
   return RegPDFA::getallstates();
}
void kbranchpdfa::settransition(dynamic_bitset<> src, dynamic_bitset<> dst, char c)
{
   // we assume that src must be a leaf node.
   auto srcappend = dynamic_bitset<>(src);
   srcappend.append(c == '0' ? 0 : 1); // append the character to the source state.
   if(congruences[srcappend] == srcappend)
   {
      // if srcappend is already separated then we do not set the transition.
      cout<< "Already separated: " << srcappend << endl;
      return;
   }
   congruences[srcappend] = dst;
   // all of the prefixes of srcappend must be added too.
   auto dstappend0 = dynamic_bitset<>(dst);
   dstappend0.append(0);
   auto dstappend1 = dynamic_bitset<>(dst);
   dstappend1.append(1);
   if(congruences.find(dstappend0) == congruences.end()&& congruences.find(dstappend1) == congruences.end())
   {
      congruences[dstappend0] = dst;
      // if dst is not any prefixes then we put a selfloop on it.
   }
   for (size_t j = 0; j < src.size(); j++)
   {
      dynamic_bitset<> prefix = srcappend;
      prefix.resize(j);
      dynamic_bitset<> prefixnext = srcappend;
      prefixnext.resize(j + 1);
      congruences[prefix] = prefixnext;
   }
   // all of the prefixes of dst must be added too.
   for (size_t j = 0; j < dst.size(); j++)
   {
      dynamic_bitset<> prefix = dst;
      prefix.resize(j);
      dynamic_bitset<> prefixnext = dst;
      prefixnext.resize(j + 1);
      congruences[prefix] = prefixnext;
   }
}


void kbranchpdfa::initwithstring(string s)
{
   // The format of the string is "000 01 01 0" etc. Empty string is "_"
   // first number is the number of branches
   // We are initializing a k-branch dfa.
   // parse the string first.
   stringstream ss(s);
   int numberofbranches;
   ss >> numberofbranches;
   for(int i = 0; i < numberofbranches; i++)
   {
      dynamic_bitset<> currentstate;
      dynamic_bitset<> nextstate;
      ss >> currentstate >> nextstate;
      auto currentstatepopped = dynamic_bitset<>(currentstate);
      currentstatepopped.pop_back(); // remove the last character.
      kbranchpdfa::settransition(currentstatepopped, nextstate, currentstate[currentstate.size() - 1] ? '1' : '0');
   }
   
}
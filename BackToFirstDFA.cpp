#include "BackToFirstDFA.h"

BackToFirstDFA::BackToFirstDFA(unsigned int s) : graph(s), labels(s), PDFA(s)
{
}
unsigned int BackToFirstDFA::get_next_state(unsigned int currentstate, bool c)
{
   bool debug = labels[currentstate];
   return graph.get_next_v(currentstate, debug ^ c);// need a test
}

unsigned int BackToFirstDFA::get_next_state(unsigned int currentstate, boost::dynamic_bitset<> str)
{
   unsigned int res = 0;
   for (unsigned int i = 0; i < str.size(); ++i)
   {
      res = get_next_state(res, (bool)str[i]);
   }
   return res;
}

vector<unsigned int> BackToFirstDFA::get_transitions_0()
{
   vector<unsigned int> res;
   for (unsigned int i = 0; i < size; ++i)
   {
      res.push_back(get_next_state(i, false));
   }
   return res;
}

vector<unsigned int> BackToFirstDFA::get_transitions_1()
{
   vector<unsigned int> res;
   for (unsigned int i = 0; i < size; ++i)
   {
      res.push_back(get_next_state(i, true));
   }
   return res;
}

void BackToFirstDFA::setW(boost::dynamic_bitset<> w)
{
   labels = w;
   is_end = false;
}

void BackToFirstDFA::reset_enumeration()
{
   labels.reset();
   is_end = false;
}

void BackToFirstDFA::next()
{
   unsigned int cur = 0;
   while (labels[cur])
   {
      labels[cur] = false;
      if (cur < labels.size())
      {
         cur++;
      }
      else
      {
         is_end = true;
         return ;
      }
   }
   labels[cur] = true;
}


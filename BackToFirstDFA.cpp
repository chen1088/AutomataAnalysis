#include "BackToFirstDFA.h"
#include <stdexcept>

BackToFirstDFA::BackToFirstDFA(unsigned int s) : graph(s), labels(s), PDFA(s)
{
}
unsigned int BackToFirstDFA::get_next_state(unsigned int currentstate, bool c)
{
   // The legacy reset family has `size` labelled vertices and an additional
   // absorbing sink at `size`. Its two sink ports coincide, so no mask bit is
   // needed there. In particular, never index labels[size].
   if (currentstate > size)
      throw std::out_of_range("BackToFirstDFA state outside reset graph");
   if (currentstate == size)
      return size;
   return graph.get_next_v(currentstate, static_cast<bool>(labels[currentstate]) ^ c);
}

unsigned int BackToFirstDFA::get_next_state(unsigned int currentstate, boost::dynamic_bitset<> str)
{
   unsigned int res = currentstate;
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
   if (w.size() != size)
      throw std::invalid_argument("BackToFirstDFA mask must have size entries");
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
   if (!is_end)
      is_end = !VectorEnumerator::next(labels);
}


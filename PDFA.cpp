#include "PDFA.h"

PDFA::PDFA():size(1)
{
}

PDFA::PDFA(unsigned int s): size(s)
{

}

// metric diff
//static unsigned int computemetric(vector<unsigned int> a, vector<unsigned int> b)
//{
//   if (a.size() != b.size()) return (unsigned int)-1;
//   auto res = a.size();
//   for (unsigned int i = 0;i<a.size();++i)
//   {
//      res -= (a[i] == b[i]) ? 1 : 0;
//   }
//   return res;
//}

vector<unsigned int> PDFA::get_transitions_0()
{
   vector<unsigned int> res;
   for (unsigned int i = 0; i < size; ++i)
   {
      res.push_back(get_next_state(i, false));
   }
   return res;
}

vector<unsigned int> PDFA::get_transitions_1()
{
   vector<unsigned int> res;
   for (unsigned int i = 0; i < size; ++i)
   {
      res.push_back(get_next_state(i, true));
   }
   return res;
}

tuple<vector<unsigned int>, vector<unsigned int> > PDFA::get_transitions()
{
   return { get_transitions_0() , get_transitions_1() };
}
void PDFA::reset_enumeration()
{
   is_end = false;
}
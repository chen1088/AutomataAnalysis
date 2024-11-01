#include "ProductPDFA.h"

ProductPDFA::ProductPDFA(unique_ptr<PDFA> p)
{
   set(move(p));
}

void ProductPDFA::set(unique_ptr<PDFA> p)
{
   this->pdfa = move(p);
   this->pdfa->reset_enumeration();
}

StateLabel ProductPDFA::evaluate(boost::dynamic_bitset<> input)
{
   // We evaluate all labels
   StateLabel t;
   pdfa->reset_enumeration();
   vector<unsigned int> res;
   while (!pdfa->is_end)
   {
      res.push_back(pdfa->get_next_state(0, input));
      pdfa->next();
   }
   t.labels = res;
   return t;
}

StateLabel ProductPDFA::step(StateLabel t, bool input)
{
   StateLabel t2;
   vector<unsigned int> res;
   pdfa->reset_enumeration();
   for (auto current : t.labels)
   {
      res.push_back(pdfa->get_next_state(current, input));
      pdfa->next();
   }
   t2.labels = res;
   return t2;
}


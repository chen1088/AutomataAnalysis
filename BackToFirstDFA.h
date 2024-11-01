#pragma once
#include "PDFA.h"
class BackToFirstDFA : public PDFA
{
public:
   BackToFirstDFA(unsigned int s);
   InfTwoRegularDigraphBackToZero graph;   // for now we just have one graph
   boost::dynamic_bitset<> labels; // This is the w for the PDFA M_w
   unsigned int get_next_state(unsigned int currentstate, bool c);
   unsigned int get_next_state(unsigned int currentstate, boost::dynamic_bitset<> str);
   vector<unsigned int> get_transitions_0();
   vector<unsigned int> get_transitions_1();
   void setW(boost::dynamic_bitset<> w);
   void reset_enumeration();
   void next();
   
   static void test()
   {
      cout << "PDFA test" << endl;
      BackToFirstDFA p(2);
      p.labels = boost::dynamic_bitset<>(2, 2ul);
      cout << p.get_next_state(0, boost::dynamic_bitset<>(4, 4ul)) << endl;
   }
};


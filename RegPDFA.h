#pragma once
#include "PDFA.h"
#include<boost/dynamic_bitset/dynamic_bitset.hpp>
class RegPDFA :
    public PDFA
{
public:
   int maxidx;
   map<boost::dynamic_bitset<>, boost::dynamic_bitset<>> congruence;
   RegPDFA();
   RegPDFA(unsigned int s);
   void reset_enumeration();
   vector<unsigned int> get_transitions_0();
   vector<unsigned int> get_transitions_1();
   void next();
};


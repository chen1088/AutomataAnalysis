#pragma once
#include "TwoRegularDigraph.h"
class InfTwoRegularDigraphBackToZero:public TwoRegularDigraph
{
public:
   InfTwoRegularDigraphBackToZero();
   InfTwoRegularDigraphBackToZero(unsigned int s);
   unsigned int get_next_v(unsigned int vidx, bool whichedge);
   void set_next_v(unsigned int vidx, bool whichedge, unsigned int value);
   void set_e0(std::vector<unsigned int> e0);
   void set_e1(std::vector<unsigned int> e1);
   void reset_enumeration();
   void next();
};


#pragma once
#include <memory>
#include <map>
#include <vector>
class TwoRegularDigraph
{
public:
   unsigned int size;
   bool is_end = false;
   TwoRegularDigraph(unsigned int s);
   unsigned int virtual get_next_v(unsigned int vidx, bool whichedge) = 0;
   virtual void set_next_v(unsigned int vidx, bool whichedge, unsigned int value) = 0;
   virtual void set_e0(std::vector<unsigned int> e0) = 0;
   virtual void set_e1(std::vector<unsigned int> e1) = 0;
   virtual void reset_enumeration();
   virtual void next() = 0;
};


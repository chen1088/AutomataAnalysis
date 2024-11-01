#include "InfTwoRegularDigraphBackToZero.h"

InfTwoRegularDigraphBackToZero::InfTwoRegularDigraphBackToZero(unsigned int s):TwoRegularDigraph(s)
{
}

InfTwoRegularDigraphBackToZero::InfTwoRegularDigraphBackToZero():TwoRegularDigraph(0)
{
}

unsigned int InfTwoRegularDigraphBackToZero::get_next_v(unsigned int vidx, bool whichedge)
{
   return ((vidx == size )? vidx : ( whichedge ? 0 : vidx + 1 ));// base case is w equal to all 0s and 0 edges go to next state.
}

void InfTwoRegularDigraphBackToZero::set_next_v(unsigned int vidx, bool whichedge, unsigned int value)
{
   // Do nothing
}

void InfTwoRegularDigraphBackToZero::set_e0(std::vector<unsigned int> e0)
{
   // Do nothing
}

void InfTwoRegularDigraphBackToZero::set_e1(std::vector<unsigned int> e1)
{
   // Do nothing
}

void InfTwoRegularDigraphBackToZero::reset_enumeration()
{
   is_end = false;
}
void InfTwoRegularDigraphBackToZero::next()
{
   is_end = true;
}
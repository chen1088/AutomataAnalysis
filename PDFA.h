#pragma once
#include"VectorEnumerator.h"
#include<boost/dynamic_bitset.hpp>
using namespace std;
class PDFA
{
public:
   unsigned int size;
   bool is_end = false;
   PDFA();
   PDFA(unsigned int s);
   virtual unsigned int get_next_state(unsigned int currentstate, bool c) = 0; // input is a character
   virtual unsigned int get_next_state(unsigned int currentstate, boost::dynamic_bitset<> str) = 0; // input is a string
   virtual vector<unsigned int> get_transitions_0();
   virtual vector<unsigned int> get_transitions_1();
   virtual tuple<vector<unsigned int>, vector<unsigned int> > get_transitions();
   virtual void next() = 0;
   virtual void reset_enumeration();


};


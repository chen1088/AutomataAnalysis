#pragma once
#include"PDFA.h"
#include"StateLabel.h"
#include<boost/dynamic_bitset.hpp>
class ProductPDFA
{
   // for now lets just consider the PDFA with the same graph but with all labels altered.
public:
   ProductPDFA(unique_ptr<PDFA> p);

   shared_ptr<PDFA> pdfa;
   void set(unique_ptr<PDFA> pdfa);
   StateLabel evaluate(boost::dynamic_bitset<> input);
   StateLabel step(StateLabel t, bool input);
};


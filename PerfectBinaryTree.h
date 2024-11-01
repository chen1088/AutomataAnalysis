#pragma once
#include <vector>
using namespace std;
class PerfectBinaryTree
{
public:
   unsigned int num_of_leaves;
   bool is_end;
   vector<tuple<unsigned int,unsigned int> > get_current();
   PerfectBinaryTree(unsigned int n);
   void reset_enumeration();
   void next();
private:
   vector<unsigned int> m_decisions;
};


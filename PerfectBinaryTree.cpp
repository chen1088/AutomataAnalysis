#include "PerfectBinaryTree.h"

PerfectBinaryTree::PerfectBinaryTree(unsigned int n)
{
   num_of_leaves = n;
   is_end = false;
   m_decisions.resize(n);
   reset_enumeration();
}

void PerfectBinaryTree::reset_enumeration()
{
   is_end = false;
   for (unsigned int i = 0; i < num_of_leaves; ++i)
   {
      m_decisions[i] = 0;
   }
}

void PerfectBinaryTree::next()
{
   unsigned int i = 0;
   while (i < num_of_leaves && m_decisions[i] == i)
   {
      m_decisions[i] = 0;
      ++i;
   }
}
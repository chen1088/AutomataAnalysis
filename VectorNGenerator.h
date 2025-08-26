#pragma once
#include <generator>
#include <vector>
using namespace std;
class VectorNGenerator
{
public:
   static generator<vector<int>> generate(int n, int vector_size)
   {
      // It generates all vectors of length 'vector_size' where each element is in the range [0, n).
      if (vector_size <= 0) co_return;
      vector<int> current(vector_size, 0);
      while (true)
      {
         co_yield current;
         int i = 0;
         while (i < vector_size)
         {
            current[i]++;
            if (current[i] < n)
               break;
            current[i] = 0;
            i++;
         }
         if (i == vector_size)
            break;
      }
   }
   static void test()
   {
      int n = 3;
      int vector_size = 4;
      cout << "Generating all vectors of size " << vector_size << " with elements in [0, " << n << "):\n";
      for (const auto &vec : generate(n, vector_size))
      {
         cout << "[ ";
         for (int val : vec)
            cout << val << " ";
         cout << "]\n";
      }
   }
};
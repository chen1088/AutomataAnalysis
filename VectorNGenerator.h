#pragma once
#include <generator>
#include <vector>
using namespace std;
class VectorNGenerator
{
public:
   static generator<vector<int>> generate(const vector<int>& input)
   {
      // It generates all vectors of length 'vector_size' where each element is in the range [0, input[i]).
      if (input.empty()) co_return;
      vector<int> current(input.size(), 0);
      while (true)
      {
         co_yield current;
         int i = 0;
         while (i < input.size())
         {
            current[i]++;
            if (current[i] < input[i])
               break;
            current[i] = 0;
            i++;
         }
         if (i == input.size())
            break;
      }
   }
   static void test()
   {
      int n = 3;
      cout << "Generating all vectors with elements in the ranges specified by the input vector:\n";
      vector<int> input = {3, 3, 3, 5};
      for (const auto &vec : generate(input))
      {
         cout << "[ ";
         for (int val : vec)
            cout << val << " ";
         cout << "]\n";
      }
   }
};
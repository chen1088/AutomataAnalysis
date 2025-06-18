#include "VectorEnumerator.h"
bool VectorEnumerator::next(vector<unsigned int>& in)
{
   unsigned int cur = 0;
   while (in[cur] != 0)
   {
      in[cur] = 0;
      if (cur < in.size())
      {
         cur++;
      }
      else
      {
         return false;
      }
   }
   in[cur] = 1;
   return true;
}

bool VectorEnumerator::next(string& in)
{
   unsigned int cur = 0;
   while (in[cur] != '0')
   {
      in[cur] = '0';
      if (cur < in.size())
      {
         cur++;
      }
      else
      {
         return false;
      }
   }
   in[cur] = '1';
   return true;
}

bool VectorEnumerator::next(boost::dynamic_bitset<>& in)
{
   boost::dynamic_bitset<>::size_type cur = 0;
   while (in[cur])
   {
      in[cur] = false;
      if (cur < in.size())
      {
         cur++;
      }
      else
      {
         return false;
      }
   }
   in[cur] = true;
   return true;
}

dynamic_bitset<> VectorEnumerator::next_copy(const dynamic_bitset<> in)
{
   auto copy = dynamic_bitset<>(in);
   next(copy);
   return copy;
}

void VectorEnumerator::print(vector<unsigned int> in)
{
   for (auto t : in)
      cout << t << " ";
}

void VectorEnumerator::print(StateLabel in)
{
   for (auto t : in.labels)
      cout << t << " ";
}

void VectorEnumerator::print(boost::dynamic_bitset<> in)
{
   for (boost::dynamic_bitset<>::size_type i = 0; i < in.size(); ++i)
      cout << in[i];
}

bool VectorEnumerator::isend(const boost::dynamic_bitset<> in)
{
   return in.all();
}


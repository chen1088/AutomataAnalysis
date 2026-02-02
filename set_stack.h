#pragma once
#include <vector>
#include <set>
using namespace std;
template <typename T>
class set_stack{
public:
   set<T> internal_set;
   vector<T> internal_stack;
   bool push(const T& value)
   {
      if (internal_set.find(value) == internal_set.end())
      {
         internal_set.insert(value);
         internal_stack.push(value);
         return true;
      }
      return false;
   }
   void pop()
   {
      if (!internal_stack.empty())
      {
         T value = internal_stack.top();
         internal_stack.pop();
         internal_set.erase(value);
      }
   }
   bool contains(const T& value) const
   {
      return internal_set.find(value) != internal_set.end();
   }
   bool empty() const
   {
      return internal_stack.empty();
   }
   size_t size() const
   {
      return internal_stack.size();
   }
   T& top()
   {
      return internal_stack.top();
   }
   void clear()
   {
      while (!internal_stack.empty())
      {
         internal_stack.pop();
      }
      internal_set.clear();
   }
};
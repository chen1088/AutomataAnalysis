#pragma once
#include<vector>
#include<string>
using namespace std;
struct StateLabel
{
public:
   vector<unsigned int> labels; // Always keeps the most number of labels upto product DFA of all DFAs. For now, we just consider the special DFA of size m.
   bool operator<(const StateLabel& other) const {
      if (labels.size() < other.labels.size())
         return true;
      if (labels.size() > other.labels.size())
         return false;
      for (int i = 0; i < labels.size(); i++)
      {
         if (labels[i] < other.labels[i])
            return true;
         if (labels[i] > other.labels[i])
            return false;
      }
      return false;
   }
   StateLabel duplicatetwice()
   {
      StateLabel ret;
      vector<unsigned int> retlabels(labels);
      retlabels.insert(retlabels.end(), labels.begin(), labels.end());
      ret.labels = retlabels;
      return ret;
   }
   string to_string()
   {
      string ret = "";
      for (int i = 0; i < labels.size(); i++)
      {
         ret += std::to_string(labels[i]);
         ret += " ";
      }
      return ret;
   }
};


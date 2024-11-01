#pragma once
#include<vector>
#include<map>
#include<string>
#include"StateLabel.h"
#include"ProductPDFA.h"
using namespace std;

class ProductDFAExperiment
{
   // Assume all indices are 0-based.
public:
   ProductDFAExperiment();
   ~ProductDFAExperiment();
   void incrementn();
   void incrementm();
   void run();
   void printtable();
   unsigned int n, m;
   map<StateLabel, vector<boost::dynamic_bitset<>>> table;
};



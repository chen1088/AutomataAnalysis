#pragma once
#include"InfTwoRegularDigraphBackToZero.h"
#include<vector>
#include<iostream>
#include<string>
#include"StateLabel.h"
using namespace std;
#include<boost/dynamic_bitset.hpp>
using boost::dynamic_bitset;
class VectorEnumerator
{
public:
   static void print(const vector<unsigned int> in);
   static void print(const StateLabel in);
   static void print(const boost::dynamic_bitset<> in);
   static bool next(vector<unsigned int>& in);
   static bool next(string& in);// need a test
   static bool next(boost::dynamic_bitset<>& in);
   static dynamic_bitset<> next_copy(const dynamic_bitset<> in);
   static bool isend(const boost::dynamic_bitset<> in);
};


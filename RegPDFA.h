#include<map>
#include<vector>
#include <queue>
#include <stack>
#include <set>
#include <ranges>
#include <string>
#include <sstream>
#include<flint/fmpz_poly.h>
#include<flint/fmpz_mpoly.h>
using namespace std;
#include<boost/dynamic_bitset/dynamic_bitset.hpp>
using boost::dynamic_bitset;

class RegPDFA
{
public:
   unsigned int size;
   // a state label is defined by the shortest string that reaches the state.
   // We are not storing the states which have only one incoming transition.

   // for <k,v> pairs we only record the v's whose k's are more than 1
   // A complete congruence is that for any string s there can be three cases:
   // 1. s is in the map, this is good.
   // 2. s is not in the map, and s can be reduced, we solve the congruence of s.
   // 3. s is not in the map, and s cannot be reduced, by default the sc(c is any character) is congruent to sc.
   // Plan changed. Now congruences must be complete.
   
   RegPDFA();
   ~RegPDFA();
   RegPDFA(unsigned int s);
   // Construct a RegPDFA from a string.
   RegPDFA(string s);
   virtual dynamic_bitset<> reduce(dynamic_bitset<> str);
   virtual vector<dynamic_bitset<>> getallstates();
   virtual bool issetransition(dynamic_bitset<> src, char c);
   virtual bool issetransition(dynamic_bitset<> src, bool b);
   virtual void settransition(dynamic_bitset<> src, dynamic_bitset<> dst, char c);
   virtual void settransition(dynamic_bitset<> src, dynamic_bitset<> dst, bool b);
   virtual void initwithstring(string s);
   virtual string to_string();
   RegPDFA cartesian_product(RegPDFA other);
   bool check_completeness();
private:
   map<dynamic_bitset<>, dynamic_bitset<>> congruence0;
   map<dynamic_bitset<>, dynamic_bitset<>> congruence1;
};


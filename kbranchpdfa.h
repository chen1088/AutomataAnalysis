#include"RegPDFA.h"
class kbranchpdfa : public RegPDFA
{
public:
   kbranchpdfa();
   kbranchpdfa(unsigned int s);
   // Construct a k-branch PDFA from a string.
   kbranchpdfa(string s);
   virtual kbranchpdfa* next() override;
   virtual dynamic_bitset<> reduce(dynamic_bitset<> str) override;
   virtual vector<dynamic_bitset<>> getallstates() override;
   virtual void settransition(dynamic_bitset<> src, dynamic_bitset<> dst, char c) override;
   virtual void initwithstring(string s) override;
   virtual string to_string() override;
private:
   map<dynamic_bitset<>,dynamic_bitset<>> congruences;
   map<dynamic_bitset<>,dynamic_bitset<>> rawstringpairs;
};
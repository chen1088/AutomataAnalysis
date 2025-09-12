#include "rgfdag.h"
template <typename T>
class rgfdag_container
{
public:
   rgfdag_container() {}
   rgfdag_container(RegPDFA* pdfa)
   {
      this->pdfa = pdfa;
      auto states = pdfa->getallstates();
      for (auto state : states)
      {
         q.push(state);
      }
   }
   void collect_rdfdag(dynamic_bitset<> src, dynamic_bitset<> dst)
   {
      
   }

private:
   
   RegPDFA* pdfa;
   map<dynamic_bitset<>, map<dynamic_bitset<>, rgfdag<T> *>> pairwise_rgfdags;
   void merge_rdfdag(rgfdag<T>* dag)
   {
      for(auto i: pairwise_rgfdags)
      {
         for(auto j: i.second)
         {
            // TODO: things happen here
         }
      }
   }
};
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

   void compress()
   {
      auto comparator = [](const rgfdag<T>* a, const rgfdag<T>* b) {
         // solve c = a - b
         auto c = a->resolvetorgf_nocache() - b->resolvetorgf_nocache();
         // compute the first non-zero coefficient of c
         auto coeffs = c->rgf_instance;
         return fmpz_cmp(c.get_first_coefficient_in_fmpz(), b.get_first_coefficient_in_fmpz()) < 0;
      };
      map<rgfdag<T>*, rgfdag<T>*, decltype(comparator)> unique_rgfdags(comparator);

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
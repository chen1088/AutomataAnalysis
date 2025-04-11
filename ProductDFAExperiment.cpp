#include "ProductDFAExperiment.h"
#include"BackToFirstDFA.h"
ProductDFAExperiment::ProductDFAExperiment()
{
   n = 1;
   m = 1;
   // When n = 1 we have only two strings 0 and 1.
   // When m = 1 we have only two states. (one starting state and one sink state) We have two pDFAs.
   vector<unsigned int> v0 = { 1,0 };
   vector<unsigned int> v1 = { 0,1 };
   StateLabel t0;
   t0.labels = v0;
   StateLabel t1;
   t1.labels = v1;
   table[t0] = { boost::dynamic_bitset<>(1,0ul)};
   table[t1] = { boost::dynamic_bitset<>(1,1ul)};
}

ProductDFAExperiment::~ProductDFAExperiment()
{
}

void ProductDFAExperiment::incrementn()
{
   // Trivial implementation
   // Take out all the <k,v> in the table.
   // for every k, move along 0 edge and 1 edge.
   // update the strings as well.
   // put the two new <k,v> in the new table.
   map<StateLabel, vector<boost::dynamic_bitset<>>> newtable;
   ProductPDFA cartesian_product(unique_ptr<PDFA>(new BackToFirstDFA(m)));
   bool hardpairfound = false;
   for (auto it = table.begin(); it != table.end(); ++it)
   {
      StateLabel t = it->first;
      auto v = it->second;
      StateLabel t0 = cartesian_product.step(t, false);
      StateLabel t1 = cartesian_product.step(t, true);
      auto v0 = v;
      auto v1 = v;
      for (unsigned int i = 0; i < v.size(); ++i)
      {
         v0[i].push_back(false);
         v1[i].push_back(true);
      }
      if (newtable.find(t0) == newtable.end())
      {
         newtable[t0] = v0;
      }
      else
      {
         // if we found two strings for the same state, we need to merge them.
         auto v0new = newtable[t0];
         v0new.insert(v0new.end(), v0.begin(), v0.end());
         // newtable[t0] = v0new;
         // Pair that is not separated.
         hardpairfound = true;
         cout << "Hard pair found for n: " << n+1 << " m: " << m << " the pair: (";
         for (auto vit = v0new.begin(); vit != v0new.end(); ++vit)
         {
            VectorEnumerator::print(*vit);
            cout << " ";
         }
         cout << ")" << endl;
         VectorEnumerator::print(t0);
         cout << endl;
      }
      if (newtable.find(t1) == newtable.end())
      {
         newtable[t1] = v1;
      }
      else
      {
         // if we found two strings for the same state, we need to merge them.
         auto v1new = newtable[t1];
         v1new.insert(v1new.end(), v1.begin(), v1.end());
         //newtable[t1] = v1new;
         hardpairfound = true;
         cout << "Hard pair found for n: " << n+1 << " m: " << m << " the pair: (";
         for (auto vit = v1new.begin(); vit != v1new.end(); ++vit)
         {
            VectorEnumerator::print(*vit);
            cout << " ";
         }
         cout << ")" << endl;
         VectorEnumerator::print(t1);
         cout << endl;
      }
   }
   table = newtable;
   ++n;
   if (hardpairfound)
      incrementm();
}

void ProductDFAExperiment::incrementm()
{
   // Trivial implementation
   // Take out all the <k,v> in the table.
   // for every k, create a new vector of twice size and copy the old vector into it.
   // for every v, evaluate when the individual state is a sink state. We need to do this twice.
   // put the new <k,v> in the new table and merge if necessary.
   map<StateLabel, vector<boost::dynamic_bitset<>>> newtable;
   ++m;
   ProductPDFA cartesian_product(unique_ptr<PDFA>(new BackToFirstDFA(m)));
   for (auto it = table.begin(); it != table.end(); ++it)
   {
      // In trivial implementation, we consider every <k,v> in the table.
      // Strings are not changed, only the labels are changed.
      StateLabel t = it->first;
      auto v = it->second;
      // StateLabel tnew = t.duplicatetwice();
      for( auto vit = v.begin(); vit != v.end();++vit)
      {
         // evaluate when the individual state is a sink state.
         // now m-1 is the sink state.
         StateLabel tnew = cartesian_product.evaluate(*vit);
         if (newtable.find(tnew) == newtable.end())
         {
            newtable[tnew] = { *vit };
         }
         else
         {
            // if we found two strings for the same state, we need to merge them.
            newtable[tnew].push_back(*vit);
         }
      }
   }
   table = newtable;
}

void ProductDFAExperiment::printtable()
{
   for (auto it = table.begin(); it != table.end(); ++it)
   {
      StateLabel t = it->first;
      auto v = it->second;
      VectorEnumerator::print(t);
      for (auto vit = v.begin(); vit != v.end(); ++vit)
      {
         cout << *vit << " ";
      }
      cout << endl;
   }
}

void ProductDFAExperiment::run()
{
   ProductPDFA cartesian_product(unique_ptr<PDFA>(new BackToFirstDFA(2)));
   boost::dynamic_bitset<> teststr1(4, 4ul);
   VectorEnumerator::print(teststr1);
   boost::dynamic_bitset<> teststr2(4, 1ul);
   VectorEnumerator::print(teststr2);
   StateLabel s = cartesian_product.evaluate(teststr1);
   StateLabel s2 = cartesian_product.evaluate(teststr2);  

   VectorEnumerator::print(s);
   VectorEnumerator::print(s2);
}
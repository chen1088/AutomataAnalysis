#pragma once

#include <iostream>
#include <map>
#include <queue>
#include <stack>
#include <set>
#include <ranges>
#include <string>
#include <sstream>
#include <vector>
#include "RegPDFA.h"
#include <boost/dynamic_bitset.hpp>
#include "urgf.h"
#include "brgf.h"

using namespace std;
using boost::dynamic_bitset;
using std::reverse;

enum class rgf_operation
{
   ADD,
   MULTIPLY,
   ONEMINUSINVERSE,
   ATOMX, // 0
   ATOMY, // 1
   EMPTY,
};

// Template DAG for rational generating functions.
// T must provide: static getinstance(), atomx(), atomy(), empty(), f1_minus_inv(),
// operator+, operator*, operator-, operator/, clear(), to_string(), and default ctor/clear.
template <typename T>
class rgfdag
{
public:
   rgfdag() {}
   rgfdag(rgf_operation op)
   {
      operation = op;
   }

   ~rgfdag()
   {
      for (auto child : children)
      {
         if (child->ref_count == 1)
         {
            delete child;
         }
         else
         {
            child->ref_count--;
         }
      }
      children.clear();
   }

   // Resolve without using cached values.
   T resolvetorgf_nocache()
   {
      switch (operation)
      {
      case rgf_operation::ADD:
      {
         if (children.size() == 0)
         {
            cout << "Error: ADD operation with no children." << endl;
            return T::getinstance().empty();
         }
         T result = children[0]->resolvetorgf_nocache();
         for (int i = 1; i < children.size(); i++)
         {
            result = result + children[i]->resolvetorgf_nocache();
         }
         return result;
      }
      case rgf_operation::MULTIPLY:
      {
         if (children.size() == 0)
         {
            cout << "Error: MULTIPLY operation with no children." << endl;
            return T::getinstance().empty();
         }
         T result = children[0]->resolvetorgf_nocache();
         for (int i = 1; i < children.size(); i++)
         {
            result = result * children[i]->resolvetorgf_nocache();
         }
         return result;
      }
      case rgf_operation::ONEMINUSINVERSE:
      {
         if (children.size() != 1)
         {
            cout << "Error: ONEMINUSINVERSE operation with more than one child." << endl;
            return T::getinstance().empty();
         }
         T child_rgf = children[0]->resolvetorgf_nocache();
         return child_rgf.f1_minus_inv();
      }
      case rgf_operation::ATOMX:
      {
         return T::getinstance().atomx();
      }
      case rgf_operation::ATOMY:
      {
         return T::getinstance().atomy();
      }
      case rgf_operation::EMPTY:
         return T::getinstance().empty();
      default:
         throw std::runtime_error("Unknown operation in rgfdag.");
      }
   }

   // Resolve with caching and reference counting for children clearance.
   T resolvetorgf()
   {
      if (is_resolved)
      {
         return rgf_instance;
      }
      switch (operation)
      {
      case rgf_operation::ADD:
         {
            if (children.size() == 0)
            {
               cout << "Error: ADD operation with no children." << endl;
               return T::getinstance().empty();
            }
            T result = children[0]->resolvetorgf();
            for (int i = 1; i < children.size(); i++)
            {
               result = result + children[i]->resolvetorgf();
               children[i]->resolved_count++;
               if (children[i]->resolved_count == children[i]->ref_count)
               {
                  children[i]->clear();
               }
            }
            rgf_instance = result;
            is_resolved = true;
            return result;
         }
      case rgf_operation::MULTIPLY:
         {
            if (children.size() == 0)
            {
               cout << "Error: MULTIPLY operation with no children." << endl;
               return T::getinstance().empty();
            }
            T result = children[0]->resolvetorgf();
            for (int i = 1; i < children.size(); i++)
            {
               result = result * (children[i]->resolvetorgf());
               children[i]->resolved_count++;
               if (children[i]->resolved_count == children[i]->ref_count)
               {
                  children[i]->clear();
               }
            }
            rgf_instance = result;
            is_resolved = true;
            return result;
         }
      case rgf_operation::ONEMINUSINVERSE:
         {
            if (children.size() != 1)
            {
               cout << "Error: ONEMINUSINVERSE operation with more than one child." << endl;
               return T::getinstance().empty();
            }
            T child_rgf = children[0]->resolvetorgf();
            rgf_instance = child_rgf.f1_minus_inv();
            is_resolved = true;
            children[0]->resolved_count++;
            if (children[0]->resolved_count == children[0]->ref_count)
            {
               children[0]->clear();
            }
            return rgf_instance;
         }
      case rgf_operation::ATOMX:
         {
            rgf_instance = T::getinstance().atomx();
            is_resolved = true;
            return rgf_instance;
         }
      case rgf_operation::ATOMY:
         {
            rgf_instance = T::getinstance().atomy();
            is_resolved = true;
            return rgf_instance;
         }
      case rgf_operation::EMPTY:
         {
            rgf_instance = T::getinstance().empty();
            is_resolved = true;
            return rgf_instance;
         }
      default:
         throw std::runtime_error("Unknown operation in rgfdag.");
      }
   }

   string to_string()
   {
      string result = "";
      switch (operation)
      {
      case rgf_operation::ADD:
         result += "ADD, ";
         break;
      case rgf_operation::MULTIPLY:
         result += "MULTIPLY, ";
         break;
      case rgf_operation::ONEMINUSINVERSE:
         result += "ONEMINUSINVERSE, ";
         break;
      case rgf_operation::ATOMX:
         result += "ATOMX, ";
         break;
      case rgf_operation::ATOMY:
         result += "ATOMY, ";
         break;
      case rgf_operation::EMPTY:
         result += "EMPTY, ";
         break;
      }
      if (operation == rgf_operation::EMPTY || operation == rgf_operation::ATOMX || operation == rgf_operation::ATOMY)
      {
         return result + "No children.";
      }
      for (size_t i = 0; i < children.size(); i++)
      {
         result += "\nChild " + std::to_string(i) + ": " + children[i]->to_string() + ", ";
      }
      return result;
   }

   void clear()
   {
      rgf_instance.clear();
      is_resolved = false;
   }
   void add_child(rgfdag<T> *child)
   {
      children.push_back(child);
      child->ref_count++;
   }

   vector<rgfdag<T> *> children;
   rgf_operation operation;
   T rgf_instance;
   bool is_resolved = false;
   int ref_count = 0;
   int resolved_count = 0;

   //////////////////////////////////////////////////

   static void print_transitions(map<dynamic_bitset<>, map<dynamic_bitset<>, vector<rgfdag<T> *>>> transitions)
   {
      for (auto i : transitions)
      {
         string i_str;
         boost::to_string(i.first, i_str);
         reverse(i_str.begin(), i_str.end());
         cout << "From state: " << i_str << endl;
         for (auto j : i.second)
         {
            string j_str;
            boost::to_string(j.first, j_str);
            reverse(j_str.begin(), j_str.end());
            cout << "  To state: " << j_str << " via " << j.second.size() << " transitions." << endl;
            for (auto k : j.second)
            {
               auto rgfstr = k->resolvetorgf_nocache().to_string();
               cout << "   rgf: " << rgfstr << endl;
            }
         }
      }
   };

   static void print_incomingtransitions(map<dynamic_bitset<>, map<dynamic_bitset<>, vector<rgfdag<T> *>>> incoming_trans)
   {
      cout << "Incoming transitions:" << endl;
      for (auto i : incoming_trans)
      {
         string i_str;
         boost::to_string(i.first, i_str);
         reverse(i_str.begin(), i_str.end());
         for (auto j : i.second)
         {
            string j_str;
            boost::to_string(j.first, j_str);
            reverse(j_str.begin(), j_str.end());
            cout << j_str << " to " << i_str << " via " << j.second.size() << " transitions." << endl;
            for (auto k : j.second)
            {
               auto rgfstr = k->resolvetorgf_nocache().to_string();
               cout << "   rgf: " << rgfstr << endl;
            }
         }
      }
   };

   static void print_outgoingtransitions(map<dynamic_bitset<>, map<dynamic_bitset<>, vector<rgfdag<T> *>>> outgoing_trans)
   {
      cout << "Outgoing transitions:" << endl;
      for (auto i : outgoing_trans)
      {
         string i_str;
         boost::to_string(i.first, i_str);
         reverse(i_str.begin(), i_str.end());
         for (auto j : i.second)
         {
            string j_str;
            boost::to_string(j.first, j_str);
            reverse(j_str.begin(), j_str.end());
            cout << i_str << " to " << j_str << " via " << j.second.size() << " transitions." << endl;
            for (auto k : j.second)
            {
               auto rgfstr = k->resolvetorgf_nocache().to_string();
               cout << "   rgf: " << rgfstr << endl;
            }
         }
      }
   };

   static void print_selflooptransitions(map<dynamic_bitset<>, vector<rgfdag<T> *>> selfloop_trans)
   {
      for (auto i : selfloop_trans)
      {
         string i_str;
         boost::to_string(i.first, i_str);
         reverse(i_str.begin(), i_str.end());
         cout << "Self-loop at state: " << i_str << endl;
         for (auto k : i.second)
         {
            auto rgfstr = k->resolvetorgf_nocache().to_string();
            cout << "   rgf: " << rgfstr << endl;
         }
      }
   };

   static rgfdag<T> *compute_rgfdag_plusplus(RegPDFA pdfa, dynamic_bitset<> src, dynamic_bitset<> dst)
   {
      if (src == dst)
      {
         return compute_rgfdag_selfloop(pdfa, src);
      }
      map<dynamic_bitset<>, map<dynamic_bitset<>, vector<rgfdag<T> *>>> incoming_trans;
      map<dynamic_bitset<>, map<dynamic_bitset<>, vector<rgfdag<T> *>>> outgoing_trans;
      map<dynamic_bitset<>, vector<rgfdag<T> *>> selfloop_trans;
      stack<dynamic_bitset<>> q;
      auto allstates = pdfa.getallstates();
      for (auto i : allstates)
      {
         if (i != src && i != dst)
         {
            q.push(i);
         }
         auto i0 = dynamic_bitset<>(i);
         i0.push_back(false);
         auto i1 = dynamic_bitset<>(i);
         i1.push_back(true);
         auto trans0 = pdfa.reduce(i0);
         auto trans1 = pdfa.reduce(i1);
         if (trans0 == i)
         {
            selfloop_trans[i].push_back(new rgfdag<T>(rgf_operation::ATOMX));
         }
         else
         {
            incoming_trans[trans0][i].push_back(new rgfdag<T>(rgf_operation::ATOMX));
            outgoing_trans[i][trans0].push_back(new rgfdag<T>(rgf_operation::ATOMX));
         }
         if (trans1 == i)
         {
            selfloop_trans[i].push_back(new rgfdag<T>(rgf_operation::ATOMY));
         }
         else
         {
            incoming_trans[trans1][i].push_back(new rgfdag<T>(rgf_operation::ATOMY));
            outgoing_trans[i][trans1].push_back(new rgfdag<T>(rgf_operation::ATOMY));
         }
      }

      while (!q.empty())
      {
         auto t = q.top();
         q.pop();
         eliminate_state(incoming_trans, outgoing_trans, selfloop_trans, t);
      }
      if (selfloop_trans[src].size() >= 1)
      {
         auto newtree = new rgfdag<T>(rgf_operation::ADD);
         for (auto i : selfloop_trans[src]) newtree->add_child(i);
         selfloop_trans[src].clear();
         selfloop_trans[src].push_back(newtree);
      }
      if (selfloop_trans[dst].size() >= 1)
      {
         auto newtree = new rgfdag<T>(rgf_operation::ADD);
         for (auto i : selfloop_trans[dst]) newtree->add_child(i);
         selfloop_trans[dst].clear();
         selfloop_trans[dst].push_back(newtree);
      }
      if (incoming_trans[src][dst].size() >= 1)
      {
         auto newtree = new rgfdag<T>(rgf_operation::ADD);
         for (auto i : incoming_trans[src][dst]) newtree->add_child(i);
         incoming_trans[src][dst].clear();
         incoming_trans[src][dst].push_back(newtree);
         outgoing_trans[dst][src].clear();
         outgoing_trans[dst][src].push_back(newtree);
      }
      if (incoming_trans[dst][src].size() >= 1)
      {
         auto newtree = new rgfdag<T>(rgf_operation::ADD);
         for (auto i : incoming_trans[dst][src]) newtree->add_child(i);
         incoming_trans[dst][src].clear();
         incoming_trans[dst][src].push_back(newtree);
         outgoing_trans[src][dst].clear();
         outgoing_trans[src][dst].push_back(newtree);
      }
      if (incoming_trans[dst][src].size() != 0)
      {
         auto res = new rgfdag<T>(rgf_operation::MULTIPLY);
         auto selfloopsrc = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
         if (selfloop_trans[src].size() != 0)
         {
            selfloopsrc->add_child(selfloop_trans[src][0]);
            res->add_child(selfloopsrc);
         }
         res->add_child(incoming_trans[dst][src][0]);
         if (incoming_trans[src][dst].size() != 0)
         {
            auto newselfloopdst = new rgfdag<T>(rgf_operation::MULTIPLY);
            newselfloopdst->add_child(incoming_trans[src][dst][0]);
            if (selfloop_trans[src].size() != 0)
            {
               newselfloopdst->add_child(selfloopsrc);
            }
            newselfloopdst->add_child(incoming_trans[dst][src][0]);
            if (selfloop_trans[dst].size() != 0)
            {
               auto allselfloopdst = new rgfdag<T>(rgf_operation::ADD);
               allselfloopdst->add_child(selfloop_trans[dst][0]);
               allselfloopdst->add_child(newselfloopdst);
               auto allselfloopdstoneminusinverse = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
               allselfloopdstoneminusinverse->add_child(allselfloopdst);
               res->add_child(allselfloopdstoneminusinverse);
               return res;
            }
            else
            {
               auto allselfloopdst = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
               allselfloopdst->add_child(newselfloopdst);
               res->add_child(allselfloopdst);
               return res;
            }
         }
         else
         {
            if (selfloop_trans[dst].size() != 0)
            {
               auto allselfloopdst = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
               allselfloopdst->add_child(selfloop_trans[dst][0]);
               res->add_child(allselfloopdst);
               return res;
            }
            else
            {
               return new rgfdag<T>(rgf_operation::EMPTY);
            }
         }
      }
      else
         return new rgfdag<T>(rgf_operation::EMPTY);
   }

   static rgfdag<T> *compute_rgfdag(RegPDFA pdfa, dynamic_bitset<> state)
   {
      return compute_rgfdag_plusplus(pdfa, dynamic_bitset<>(0), state);
   }

   // Backwards-compatible static wrappers: older code calls compute_urgfdag / compute_brgfdag
   static rgfdag<T> *compute_urgfdag(RegPDFA pdfa, dynamic_bitset<> state)
   {
      return compute_rgfdag(pdfa, state);
   }
   static rgfdag<T> *compute_brgfdag(RegPDFA pdfa, dynamic_bitset<> state)
   {
      return compute_rgfdag(pdfa, state);
   }

   static rgfdag<T> *compute_rgfdag_selfloop(RegPDFA pdfa, dynamic_bitset<> state)
   {
      map<dynamic_bitset<>, map<dynamic_bitset<>, vector<rgfdag<T> *>>> incoming_trans;
      map<dynamic_bitset<>, map<dynamic_bitset<>, vector<rgfdag<T> *>>> outgoing_trans;
      map<dynamic_bitset<>, vector<rgfdag<T> *>> selfloop_trans;
      stack<dynamic_bitset<>> q;
      auto allstates = pdfa.getallstates();
      for (auto i : allstates)
      {
         if (i != state && i != dynamic_bitset<>(0)) q.push(i);
         auto i0 = dynamic_bitset<>(i); i0.push_back(false);
         auto i1 = dynamic_bitset<>(i); i1.push_back(true);
         auto trans0 = pdfa.reduce(i0);
         auto trans1 = pdfa.reduce(i1);
         if (trans0 == i) selfloop_trans[i].push_back(new rgfdag<T>(rgf_operation::ATOMX));
         else { incoming_trans[trans0][i].push_back(new rgfdag<T>(rgf_operation::ATOMX)); outgoing_trans[i][trans0].push_back(new rgfdag<T>(rgf_operation::ATOMX)); }
         if (trans1 == i) selfloop_trans[i].push_back(new rgfdag<T>(rgf_operation::ATOMY));
         else { incoming_trans[trans1][i].push_back(new rgfdag<T>(rgf_operation::ATOMY)); outgoing_trans[i][trans1].push_back(new rgfdag<T>(rgf_operation::ATOMY)); }
      }

      while (!q.empty()) { auto t = q.top(); q.pop(); eliminate_state(incoming_trans, outgoing_trans, selfloop_trans, t); }

      if (state == dynamic_bitset<>(0))
      {
         print_selflooptransitions(selfloop_trans);
         if (selfloop_trans[state].size() >= 1)
         {
            auto allselfloop = new rgfdag<T>(rgf_operation::ADD);
            for (auto i : selfloop_trans[state]) allselfloop->add_child(i);
            auto res = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
            res->add_child(allselfloop);
            return res;
         }
         else if (selfloop_trans[state].size() == 1)
         {
            auto res = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
            res->add_child(selfloop_trans[state][0]);
            return res;
         }
         else
         {
            return new rgfdag<T>(rgf_operation::EMPTY);
         }
      }

      if (selfloop_trans[state].size() >= 1)
      {
         auto newtree = new rgfdag<T>(rgf_operation::ADD);
         for (auto i : selfloop_trans[state]) newtree->add_child(i);
         selfloop_trans[state].clear(); selfloop_trans[state].push_back(newtree);
      }
      if (incoming_trans[state][dynamic_bitset<>(0)].size() >= 1)
      {
         auto newtree = new rgfdag<T>(rgf_operation::ADD);
         for (auto i : incoming_trans[state][dynamic_bitset<>(0)]) newtree->add_child(i);
         incoming_trans[state][dynamic_bitset<>(0)].clear(); incoming_trans[state][dynamic_bitset<>(0)].push_back(newtree);
         outgoing_trans[dynamic_bitset<>(0)][state].clear(); outgoing_trans[dynamic_bitset<>(0)][state].push_back(newtree);
      }
      if (incoming_trans[dynamic_bitset<>(0)][state].size() >= 1)
      {
         auto newtree = new rgfdag<T>(rgf_operation::ADD);
         for (auto i : incoming_trans[dynamic_bitset<>(0)][state]) newtree->add_child(i);
         incoming_trans[dynamic_bitset<>(0)][state].clear(); incoming_trans[dynamic_bitset<>(0)][state].push_back(newtree);
         outgoing_trans[dynamic_bitset<>(0)][state].clear(); outgoing_trans[dynamic_bitset<>(0)][state].push_back(newtree);
      }
      if (selfloop_trans[dynamic_bitset<>(0)].size() >= 1)
      {
         auto newtree = new rgfdag<T>(rgf_operation::ADD);
         for (auto i : selfloop_trans[dynamic_bitset<>(0)]) newtree->add_child(i);
         selfloop_trans[dynamic_bitset<>(0)].clear(); selfloop_trans[dynamic_bitset<>(0)].push_back(newtree);
      }

      if (incoming_trans[state][dynamic_bitset<>(0)].size() != 0 && incoming_trans[dynamic_bitset<>(0)][state].size() != 0)
      {
         auto newloop = new rgfdag<T>(rgf_operation::MULTIPLY);
         newloop->add_child(incoming_trans[dynamic_bitset<>(0)][state][0]);
         if (selfloop_trans[dynamic_bitset<>(0)].size() != 0)
         {
            auto selfloop0 = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
            selfloop0->add_child(selfloop_trans[dynamic_bitset<>(0)][0]);
            newloop->add_child(selfloop0);
         }
         newloop->add_child(incoming_trans[state][dynamic_bitset<>(0)][0]);
         if (selfloop_trans[state].size() != 0)
         {
            auto allloops = new rgfdag<T>(rgf_operation::ADD);
            allloops->add_child(selfloop_trans[state][0]);
            allloops->add_child(newloop);
            auto res = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
            res->add_child(allloops);
            return res;
         }
         else
         {
            auto res = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
            res->add_child(newloop);
            return res;
         }
         return newloop;
      }
      else
      {
         auto res = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
         res->add_child(selfloop_trans[state][0]);
         return res;
      }
   }

   static rgfdag<T> *compute_rgfdag_minusminus(RegPDFA pdfa, dynamic_bitset<> src, dynamic_bitset<> dst)
   {
      return new rgfdag<T>(rgf_operation::EMPTY);
   }
   static rgfdag<T> *compute_rgfdag_minusplus(RegPDFA pdfa, dynamic_bitset<> src, dynamic_bitset<> dst)
   {
      return new rgfdag<T>(rgf_operation::EMPTY);
   }
   static rgfdag<T> *compute_rgfdag_plusminus(RegPDFA pdfa, dynamic_bitset<> src, dynamic_bitset<> dst)
   {
      return new rgfdag<T>(rgf_operation::EMPTY);
   }

   static void eliminate_state(map<dynamic_bitset<>, map<dynamic_bitset<>, vector<rgfdag<T> *>>> &incoming_trans,
                               map<dynamic_bitset<>, map<dynamic_bitset<>, vector<rgfdag<T> *>>> &outgoing_trans,
                               map<dynamic_bitset<>, vector<rgfdag<T> *>> &selfloop_trans,
                               const dynamic_bitset<> t)
   {
      if (selfloop_trans[t].size() > 1)
      {
         auto newtree = new rgfdag<T>(rgf_operation::ADD);
         for (auto i : selfloop_trans[t]) newtree->add_child(i);
         selfloop_trans[t].clear(); selfloop_trans[t].push_back(newtree);
      }
      set<dynamic_bitset<>> markedasdelete_incoming;
      set<dynamic_bitset<>> markedasdelete_outgoing;
      for (auto i : incoming_trans[t])
      {
         if (i.second.size() == 0)
         {
            cout << "Error: empty incoming transition." << endl;
         }
         else if (i.second.size() > 1)
         {
            auto newtree = new rgfdag<T>(rgf_operation::ADD);
            for (auto j : i.second) newtree->add_child(j);
            i.second.clear(); i.second.push_back(newtree);
            outgoing_trans[i.first][t].clear(); outgoing_trans[i.first][t].push_back(newtree);
         }

         for (auto j : outgoing_trans[t])
         {
            if (j.second.size() == 0)
            {
               cout << "Error: empty outgoing transition." << endl;
            }
            else if (j.second.size() > 1)
            {
               auto newtree = new rgfdag<T>(rgf_operation::ADD);
               for (auto k : j.second) newtree->add_child(k);
               j.second.clear(); j.second.push_back(newtree);
               incoming_trans[j.first][t].clear(); incoming_trans[j.first][t].push_back(newtree);
            }
            if (selfloop_trans[t].size() == 0)
            {
               auto newtree = new rgfdag<T>(rgf_operation::MULTIPLY);
               newtree->add_child(i.second[0]);
               newtree->add_child(j.second[0]);
               if (i.first == j.first)
               {
                  selfloop_trans[i.first].push_back(newtree);
               }
               else
               {
                  incoming_trans[j.first][i.first].push_back(newtree);
                  outgoing_trans[i.first][j.first].push_back(newtree);
               }
            }
            else if (selfloop_trans[t].size() == 1)
            {
               auto newtree = new rgfdag<T>(rgf_operation::ONEMINUSINVERSE);
               newtree->add_child(selfloop_trans[t][0]);
               auto newtree2 = new rgfdag<T>(rgf_operation::MULTIPLY);
               newtree2->add_child(i.second[0]);
               newtree2->add_child(newtree);
               newtree2->add_child(j.second[0]);
               if (i.first == j.first)
               {
                  selfloop_trans[i.first].push_back(newtree2);
               }
               else
               {
                  incoming_trans[j.first][i.first].push_back(newtree2);
                  outgoing_trans[i.first][j.first].push_back(newtree2);
               }
            }
            else
            {
               cout << "Error: more than one selfloop." << endl;
            }
         }
      }
      selfloop_trans.erase(t);
      for (auto k : incoming_trans[t]) markedasdelete_incoming.insert(k.first);
      for (auto k : markedasdelete_incoming) outgoing_trans[k].erase(t);
      for (auto k : outgoing_trans[t]) markedasdelete_outgoing.insert(k.first);
      for (auto k : markedasdelete_outgoing) incoming_trans[k].erase(t);
      outgoing_trans.erase(t);
      incoming_trans.erase(t);
   }
   ///////////////////////////////////////////////////

   static void testfunctionmapping(map<int, vector<int>> &input)
   {
      input[2].push_back(3);
   }

   static void test()
   {
      map<int, vector<int>> testmap;
      testfunctionmapping(testmap);
      cout << testmap[2][0] << endl; // should print 3
   }

   // Backwards-compatible instance methods
   T resolvetourgf()
   {
      return resolvetorgf();
   }
   T resolvetobrgf()
   {
      return resolvetorgf();
   }
};

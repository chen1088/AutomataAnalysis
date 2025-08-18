#pragma once

#include <iostream>
#include <map>
#include <queue>
#include <stack>
#include <set>
#include <ranges>
#include <string>
#include <sstream>
#include "brgf.h"
#include "RegPDFA.h"
#include <boost/dynamic_bitset.hpp>
using namespace std;
using boost::dynamic_bitset;
using std::reverse;
enum class brgf_operation
{
   ADD,
   MULTIPLY,
   ONEMINUSINVERSE,
   ATOMX, // 0
   ATOMY, // 1
   EMPTY,
};
class brgfdag
{
public:
   brgfdag();
   brgfdag(brgf_operation op)
   {
      operation = op;
   }

   ~brgfdag()
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
   brgf resolvetobrgf_nocache()
   {
      // Resolve the brgf tree to a single brgf without caching.
      switch (operation)
      {
      case brgf_operation::ADD:
      {
         if (children.size() == 0)
         {
            cout << "Error: ADD operation with no children." << endl;
            return brgf::getinstance().empty();
         }
         brgf result = children[0]->resolvetobrgf_nocache();
         for (int i = 1; i < children.size(); i++)
         {
            result = result + children[i]->resolvetobrgf_nocache();
         }
         return result;
      }
      case brgf_operation::MULTIPLY:
      {
         if (children.size() == 0)
         {
            cout << "Error: MULTIPLY operation with no children." << endl;
            return brgf::getinstance().empty();
         }
         brgf result = children[0]->resolvetobrgf_nocache();
         for (int i = 1; i < children.size(); i++)
         {
            result = result * children[i]->resolvetobrgf_nocache();
         }
         return result;
      }
      case brgf_operation::ONEMINUSINVERSE:
      {
         if (children.size() != 1)
         {
            cout << "Error: ONEMINUSINVERSE operation with more than one child." << endl;
            return brgf::getinstance().empty();
         }
         brgf child_brgf = children[0]->resolvetobrgf_nocache();
         return child_brgf.f1_minus_inv();
      }
      case brgf_operation::ATOMX:
      {
         return brgf::getinstance().atomx();
      }
      case brgf_operation::ATOMY:
      {
         return brgf::getinstance().atomy();
      }
      case brgf_operation::EMPTY:
         return brgf::getinstance().empty();
      default:
         throw std::runtime_error("Unknown operation in brgfdag.");
      }
   }
   brgf resolvetobrgf()
   {
      if (is_resolved)
      {
         return brgf_instance;
      }
      switch (operation)
      {
      case brgf_operation::ADD:
         {
            if (children.size() == 0)
            {
               cout << "Error: ADD operation with no children." << endl;
               return brgf::getinstance().empty();
            }
            brgf result = children[0]->resolvetobrgf();
            for (int i = 1; i < children.size(); i++)
            {
               result = result + children[i]->resolvetobrgf();
               children[i]->resolved_count++;
               if (children[i]->resolved_count == children[i]->ref_count)
               {
                  children[i]->clear();
               }
            }
            brgf_instance = result;
            is_resolved = true;
            return result;
         }
      case brgf_operation::MULTIPLY:
         {
            if (children.size() == 0)
            {
               cout << "Error: MULTIPLY operation with no children." << endl;
               return brgf::getinstance().empty();
            }
            brgf result = children[0]->resolvetobrgf();

            for (int i = 1; i < children.size(); i++)
            {
               result = result * (children[i]->resolvetobrgf());
               children[i]->resolved_count++;
               if (children[i]->resolved_count == children[i]->ref_count)
               {
                  children[i]->clear();
               }
            }
            brgf_instance = result;
            is_resolved = true;
            return result;
         }
      case brgf_operation::ONEMINUSINVERSE:
         {
            if (children.size() != 1)
            {
               cout << "Error: ONEMINUSINVERSE operation with more than one child." << endl;
               return brgf::getinstance().empty();
            }
            brgf child_brgf = children[0]->resolvetobrgf();
            brgf_instance = child_brgf.f1_minus_inv();
            is_resolved = true;
            children[0]->resolved_count++;
            if (children[0]->resolved_count == children[0]->ref_count)
            {
               children[0]->clear();
            }
            return brgf_instance;
         }
      case brgf_operation::ATOMX:
         {
            brgf_instance = brgf::getinstance().atomx();
            is_resolved = true;
            return brgf_instance;
         }
      case brgf_operation::ATOMY:
         {
            brgf_instance = brgf::getinstance().atomy();
            is_resolved = true;
            return brgf_instance;
         }
      case brgf_operation::EMPTY:
         {
            brgf_instance = brgf::getinstance().empty();
            is_resolved = true;
            return brgf_instance;
         }
      default:
         throw std::runtime_error("Unknown operation in brgfdag.");
      }
   }
   string to_string()
   {
      string result = "";
      switch (operation)
      {
      case brgf_operation::ADD:
         result += "ADD, ";
         break;
      case brgf_operation::MULTIPLY:
         result += "MULTIPLY, ";
         break;
      case brgf_operation::ONEMINUSINVERSE:
         result += "ONEMINUSINVERSE, ";
         break;
      case brgf_operation::ATOMX:
         result += "ATOMX, ";
         break;
      case brgf_operation::ATOMY:
         result += "ATOMY, ";
         break;
      case brgf_operation::EMPTY:
         result += "EMPTY, ";
         break;
      }
      if (operation == brgf_operation::EMPTY || operation == brgf_operation::ATOMX || operation == brgf_operation::ATOMY)
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
      // clear brgf pointer
      brgf_instance.clear();
      is_resolved = false;
   }
   void add_child(brgfdag *child)
   {
      children.push_back(child);
      child->ref_count++;
   }
   vector<brgfdag *> children;
   brgf_operation operation;
   brgf brgf_instance;
   bool is_resolved = false;
   // The reference count for the dag node so we can make decision whether to clear the cache
   int ref_count = 0;
   // Record how many of parents have been resolved.
   int resolved_count = 0;

   //////////////////////////////////////////////////

   // For debugging purpose only
   static void print_transitions(map<dynamic_bitset<>, map<dynamic_bitset<>, vector<brgfdag *>>> transitions)
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
               auto brgfstr = k->resolvetobrgf_nocache().to_string();
               cout << "   brgf: " << brgfstr << endl;
            }
         }
      }
   };
   static void print_incomingtransitions(map<dynamic_bitset<>, map<dynamic_bitset<>, vector<brgfdag *>>> incoming_trans)
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
               auto brgfstr = k->resolvetobrgf_nocache().to_string();
               cout << "   brgf: " << brgfstr << endl;
            }
         }
      }
   };
   static void print_outgoingtransitions(map<dynamic_bitset<>, map<dynamic_bitset<>, vector<brgfdag *>>> outgoing_trans)
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
               auto brgfstr = k->resolvetobrgf_nocache().to_string();
               cout << "   brgf: " << brgfstr << endl;
            }
         }
      }
   };
   static void print_selflooptransitions(map<dynamic_bitset<>, vector<brgfdag *>> selfloop_trans)
   {
      for (auto i : selfloop_trans)
      {
         string i_str;
         boost::to_string(i.first, i_str);
         reverse(i_str.begin(), i_str.end());
         cout << "Self-loop at state: " << i_str << endl;
         for (auto k : i.second)
         {
            auto brgfstr = k->resolvetobrgf_nocache().to_string();
            cout << "   brgf: " << brgfstr << endl;
         }
      }
   };

   static brgfdag *compute_brgfdag_plusplus(RegPDFA pdfa, dynamic_bitset<> src, dynamic_bitset<> dst)
   {
      // Given a source state and a destination state, compute the pairwise brgf from src to dst with selfloop on both included.
      if (src == dst)
      {
         // if src and dst are the same, we have to compute the selfloop.
         return compute_brgfdag_selfloop(pdfa, src);
      }
      // now we assume src and dst are different.
      // incoming and outgoing transitions do not count selfloops.
      map<dynamic_bitset<>, map<dynamic_bitset<>, vector<brgfdag *>>> incoming_trans;
      map<dynamic_bitset<>, map<dynamic_bitset<>, vector<brgfdag *>>> outgoing_trans;
      map<dynamic_bitset<>, vector<brgfdag *>> selfloop_trans;
      // initialize a queue to store the states.
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
            selfloop_trans[i].push_back(new brgfdag(brgf_operation::ATOMX));
         }
         else
         {
            incoming_trans[trans0][i].push_back(new brgfdag(brgf_operation::ATOMX));
            outgoing_trans[i][trans0].push_back(new brgfdag(brgf_operation::ATOMX));
         }
         if (trans1 == i)
         {
            selfloop_trans[i].push_back(new brgfdag(brgf_operation::ATOMY));
         }
         else
         {
            incoming_trans[trans1][i].push_back(new brgfdag(brgf_operation::ATOMY));
            outgoing_trans[i][trans1].push_back(new brgfdag(brgf_operation::ATOMY));
         }
      }

      while (!q.empty())
      {
         auto t = q.top();
         q.pop();
         // eliminate one state.
         eliminate_state(incoming_trans, outgoing_trans, selfloop_trans, t);
      }
      // union the selfloop incoming and outgoing transitions.
      if (selfloop_trans[src].size() >= 1)
      {
         // if there are selfloops, we have to collect them.
         auto newtree = new brgfdag(brgf_operation::ADD);
         for (auto i : selfloop_trans[src])
         {
            newtree->add_child(i);
         }
         selfloop_trans[src].clear();
         selfloop_trans[src].push_back(newtree);
      }
      if (selfloop_trans[dst].size() >= 1)
      {
         // if there are selfloops, we have to collect them.
         auto newtree = new brgfdag(brgf_operation::ADD);
         for (auto i : selfloop_trans[dst])
         {
            newtree->add_child(i);
         }
         selfloop_trans[dst].clear();
         selfloop_trans[dst].push_back(newtree);
      }
      if (incoming_trans[src][dst].size() >= 1)
      {
         // if there are incoming transitions, we have to collect them.
         auto newtree = new brgfdag(brgf_operation::ADD);
         for (auto i : incoming_trans[src][dst])
         {
            newtree->add_child(i);
         }
         incoming_trans[src][dst].clear();
         incoming_trans[src][dst].push_back(newtree);
         outgoing_trans[dst][src].clear();
         outgoing_trans[dst][src].push_back(newtree);
      }
      if (incoming_trans[dst][src].size() >= 1)
      {
         // if there are incoming transitions from the destination state, we have to collect them.
         auto newtree = new brgfdag(brgf_operation::ADD);
         for (auto i : incoming_trans[dst][src])
         {
            newtree->add_child(i);
         }
         incoming_trans[dst][src].clear();
         incoming_trans[dst][src].push_back(newtree);
         outgoing_trans[src][dst].clear();
         outgoing_trans[src][dst].push_back(newtree);
      }
      // the result includes both selfloops.
      if (incoming_trans[dst][src].size() != 0)
      {
         // first part
         auto res = new brgfdag(brgf_operation::MULTIPLY);
         auto selfloopsrc = new brgfdag(brgf_operation::ONEMINUSINVERSE);
         if (selfloop_trans[src].size() != 0)
         {
            selfloopsrc->add_child(selfloop_trans[src][0]);
            res->add_child(selfloopsrc);
         }
         res->add_child(incoming_trans[dst][src][0]);
         // second part
         if (incoming_trans[src][dst].size() != 0)
         {
            // reduce a new selfloop that is dst->src(->src..)->dst.
            auto newselfloopdst = new brgfdag(brgf_operation::MULTIPLY);
            newselfloopdst->add_child(incoming_trans[src][dst][0]);
            if (selfloop_trans[src].size() != 0)
            {
               newselfloopdst->add_child(selfloopsrc);
            }
            newselfloopdst->add_child(incoming_trans[dst][src][0]);
            // union the selfloop on dst.
            if (selfloop_trans[dst].size() != 0)
            {
               auto allselfloopdst = new brgfdag(brgf_operation::ADD);
               allselfloopdst->add_child(selfloop_trans[dst][0]);
               allselfloopdst->add_child(newselfloopdst);
               auto allselfloopdstoneminusinverse = new brgfdag(brgf_operation::ONEMINUSINVERSE);
               allselfloopdstoneminusinverse->add_child(allselfloopdst);
               res->add_child(allselfloopdstoneminusinverse);
               return res;
            }
            else
            {
               auto allselfloopdst = new brgfdag(brgf_operation::ONEMINUSINVERSE);
               allselfloopdst->add_child(newselfloopdst);
               res->add_child(allselfloopdst);
               return res;
            }
         }
         else
         {
            if (selfloop_trans[dst].size() != 0)
            {
               // if there is a selfloop on dst, concatenate it.
               auto allselfloopdst = new brgfdag(brgf_operation::ONEMINUSINVERSE);
               allselfloopdst->add_child(selfloop_trans[dst][0]);
               res->add_child(allselfloopdst);
               return res;
            }
            else
            {
               // if there is no selfloop on dst, and there is no transition from dst to src, that is an empty!
               return new brgfdag(brgf_operation::EMPTY);
            }
         }
      }
      else
         return new brgfdag(brgf_operation::EMPTY);
   }

   static brgfdag *compute_brgfdag(RegPDFA pdfa, dynamic_bitset<> state)
   {
      return compute_brgfdag_plusplus(pdfa, dynamic_bitset<>(0), state);
   }
   static brgfdag *compute_brgfdag_selfloop(RegPDFA pdfa, dynamic_bitset<> state)
   {
      // now we assume src and dst are different.
      // incoming and outgoing transitions do not count selfloops.
      map<dynamic_bitset<>, map<dynamic_bitset<>, vector<brgfdag *>>> incoming_trans;
      map<dynamic_bitset<>, map<dynamic_bitset<>, vector<brgfdag *>>> outgoing_trans;
      map<dynamic_bitset<>, vector<brgfdag *>> selfloop_trans;
      // initialize a queue to store the states.
      stack<dynamic_bitset<>> q;
      auto allstates = pdfa.getallstates();
      for (auto i : allstates)
      {
         if (i != state && i != dynamic_bitset<>(0))
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
            selfloop_trans[i].push_back(new brgfdag(brgf_operation::ATOMX));
         }
         else
         {
            incoming_trans[trans0][i].push_back(new brgfdag(brgf_operation::ATOMX));
            outgoing_trans[i][trans0].push_back(new brgfdag(brgf_operation::ATOMX));
         }
         if (trans1 == i)
         {
            selfloop_trans[i].push_back(new brgfdag(brgf_operation::ATOMY));
         }
         else
         {
            incoming_trans[trans1][i].push_back(new brgfdag(brgf_operation::ATOMY));
            outgoing_trans[i][trans1].push_back(new brgfdag(brgf_operation::ATOMY));
         }
      }

      while (!q.empty())
      {
         auto t = q.top();
         q.pop();
         // eliminate one state.
         eliminate_state(incoming_trans, outgoing_trans, selfloop_trans, t);
      }
      if (state == dynamic_bitset<>(0))
      {
         print_selflooptransitions(selfloop_trans);
         // there is just one state left
         if (selfloop_trans[state].size() >= 1)
         {
            // if there is a selfloop, we need to include it.
            auto allselfloop = new brgfdag(brgf_operation::ADD);
            for (auto i : selfloop_trans[state])
            {
               allselfloop->add_child(i);
            }
            auto res = new brgfdag(brgf_operation::ONEMINUSINVERSE);
            res->add_child(allselfloop);
            return res;
         }
         else if (selfloop_trans[state].size() == 1)
         {
            // if there is exactly one selfloop, we need to include it.
            auto res = new brgfdag(brgf_operation::ONEMINUSINVERSE);
            res->add_child(selfloop_trans[state][0]);
            return res;
         }
         else
         {
            // if there is no selfloop, we return an empty brgfdag.
            return new brgfdag(brgf_operation::EMPTY);
         }
      }
      // union the selfloop incoming and outgoing transitions.
      if (selfloop_trans[state].size() >= 1)
      {
         // if there are selfloops, we have to collect them.
         auto newtree = new brgfdag(brgf_operation::ADD);
         for (auto i : selfloop_trans[state])
         {
            newtree->add_child(i);
         }
         selfloop_trans[state].clear();
         selfloop_trans[state].push_back(newtree);
      }
      if (incoming_trans[state][dynamic_bitset<>(0)].size() >= 1)
      {
         auto newtree = new brgfdag(brgf_operation::ADD);
         for (auto i : incoming_trans[state][dynamic_bitset<>(0)])
         {
            newtree->add_child(i);
         }
         incoming_trans[state][dynamic_bitset<>(0)].clear();
         incoming_trans[state][dynamic_bitset<>(0)].push_back(newtree);
         outgoing_trans[dynamic_bitset<>(0)][state].clear();
         outgoing_trans[dynamic_bitset<>(0)][state].push_back(newtree);
      }
      if (incoming_trans[dynamic_bitset<>(0)][state].size() >= 1)
      {
         auto newtree = new brgfdag(brgf_operation::ADD);
         for (auto i : incoming_trans[dynamic_bitset<>(0)][state])
         {
            newtree->add_child(i);
         }
         incoming_trans[dynamic_bitset<>(0)][state].clear();
         incoming_trans[dynamic_bitset<>(0)][state].push_back(newtree);
         outgoing_trans[dynamic_bitset<>(0)][state].clear();
         outgoing_trans[dynamic_bitset<>(0)][state].push_back(newtree);
      }
      if (selfloop_trans[dynamic_bitset<>(0)].size() >= 1)
      {
         // if there are selfloops, we have to collect them.
         auto newtree = new brgfdag(brgf_operation::ADD);
         for (auto i : selfloop_trans[dynamic_bitset<>(0)])
         {
            newtree->add_child(i);
         }
         selfloop_trans[dynamic_bitset<>(0)].clear();
         selfloop_trans[dynamic_bitset<>(0)].push_back(newtree);
      }
      // the result includes both selfloops.
      if (incoming_trans[state][dynamic_bitset<>(0)].size() != 0 &&
          incoming_trans[dynamic_bitset<>(0)][state].size() != 0)
      {
         // make a new loop
         auto newloop = new brgfdag(brgf_operation::MULTIPLY);
         newloop->add_child(incoming_trans[dynamic_bitset<>(0)][state][0]);
         if (selfloop_trans[dynamic_bitset<>(0)].size() != 0)
         {
            auto selfloop0 = new brgfdag(brgf_operation::ONEMINUSINVERSE);
            selfloop0->add_child(selfloop_trans[dynamic_bitset<>(0)][0]);
            newloop->add_child(selfloop0);
         }
         newloop->add_child(incoming_trans[state][dynamic_bitset<>(0)][0]);
         if (selfloop_trans[state].size() != 0)
         {
            auto allloops = new brgfdag(brgf_operation::ADD);
            allloops->add_child(selfloop_trans[state][0]);
            allloops->add_child(newloop);
            auto res = new brgfdag(brgf_operation::ONEMINUSINVERSE);
            res->add_child(allloops);
            return res;
         }
         else
         {
            auto res = new brgfdag(brgf_operation::ONEMINUSINVERSE);
            res->add_child(newloop);
            return res;
         }
         return newloop;
      }
      else
      {
         auto res = new brgfdag(brgf_operation::ONEMINUSINVERSE);
         res->add_child(selfloop_trans[state][0]);
         return res;
      }
   }

   static brgfdag *compute_brgfdag_minusminus(RegPDFA pdfa, dynamic_bitset<> src, dynamic_bitset<> dst)
   {
      // TODO: compute the minusminus for the state.
      return new brgfdag(brgf_operation::EMPTY);
   }
   static brgfdag *compute_brgfdag_minusplus(RegPDFA pdfa, dynamic_bitset<> src, dynamic_bitset<> dst)
   {
      // TODO: compute the minusplus for the state.
      return new brgfdag(brgf_operation::EMPTY);
   }
   static brgfdag *compute_brgfdag_plusminus(RegPDFA pdfa, dynamic_bitset<> src, dynamic_bitset<> dst)
   {
      // TODO: compute the plusminus for the state.
      return new brgfdag(brgf_operation::EMPTY);
   }

   static void eliminate_state(map<dynamic_bitset<>, map<dynamic_bitset<>, vector<brgfdag *>>> &incoming_trans,
                               map<dynamic_bitset<>, map<dynamic_bitset<>, vector<brgfdag *>>> &outgoing_trans,
                               map<dynamic_bitset<>, vector<brgfdag *>> &selfloop_trans,
                               const dynamic_bitset<> t)
   {
      if (selfloop_trans[t].size() > 1)
      {
         // if there are more than one selfloops, we have to collect them.
         auto newtree = new brgfdag(brgf_operation::ADD);
         for (auto i : selfloop_trans[t])
         {
            newtree->add_child(i);
         }
         selfloop_trans[t].clear();
         selfloop_trans[t].push_back(newtree);
      }
      set<dynamic_bitset<>> markedasdelete_incoming;
      set<dynamic_bitset<>> markedasdelete_outgoing;
      for (auto i : incoming_trans[t])
      {
         // collect the parrelled transitions.
         if (i.second.size() == 0)
         {
            // This only happens if the state is the starting state, and there is no incoming transitions to the starting state.
            cout << "Error: empty incoming transition." << endl;
         }
         else if (i.second.size() > 1)
         {
            // if this is more than one, we have to collect them.
            auto newtree = new brgfdag(brgf_operation::ADD);
            for (auto j : i.second)
            {
               newtree->add_child(j);
            }
            i.second.clear();
            i.second.push_back(newtree);
            // update the outgoing transitions as well.
            outgoing_trans[i.first][t].clear();
            outgoing_trans[i.first][t].push_back(newtree);
         }

         for (auto j : outgoing_trans[t])
         {
            // collect the outgoing transitions.
            if (j.second.size() == 0)
            {
               // It is impossible to have no outgoing transition.
               cout << "Error: empty outgoing transition." << endl;
            }
            else if (j.second.size() > 1)
            {
               // if this is more than one, we have to collect them.
               auto newtree = new brgfdag(brgf_operation::ADD);
               for (auto k : j.second)
               {
                  newtree->add_child(k);
               }
               j.second.clear();
               j.second.push_back(newtree);
               // update the incoming transitions as well.
               incoming_trans[j.first][t].clear();
               incoming_trans[j.first][t].push_back(newtree);
            }
            if (selfloop_trans[t].size() == 0)
            {
               // concatenate
               auto newtree = new brgfdag(brgf_operation::MULTIPLY);
               newtree->add_child(i.second[0]);
               newtree->add_child(j.second[0]);
               // replace with the new dag.
               // now i->t->j becomes i->j
               if (i.first == j.first)
               {
                  // if i and j are the same, it is the selfloop.
                  selfloop_trans[i.first].push_back(newtree);
               }
               else
               {
                  // if i and j are not the same, add this i->j to incoming and outgoing transitions.
                  incoming_trans[j.first][i.first].push_back(newtree);
                  outgoing_trans[i.first][j.first].push_back(newtree);
               }
            }
            else if (selfloop_trans[t].size() == 1)
            {
               // oneinverse then concatenate
               auto newtree = new brgfdag(brgf_operation::ONEMINUSINVERSE);
               newtree->add_child(selfloop_trans[t][0]);
               auto newtree2 = new brgfdag(brgf_operation::MULTIPLY);
               newtree2->add_child(i.second[0]);
               newtree2->add_child(newtree);
               newtree2->add_child(j.second[0]);
               // replace with the new dag.
               // now i->t->j becomes i->j
               if (i.first == j.first)
               {
                  // if i and j are the same, it is the selfloop.
                  selfloop_trans[i.first].push_back(newtree2);
               }
               else
               {
                  // if i and j are not the same, add this i->j to incoming and outgoing transitions.
                  incoming_trans[j.first][i.first].push_back(newtree2);
                  outgoing_trans[i.first][j.first].push_back(newtree2);
               }
            }
            else
            {
               // not possible
               cout << "Error: more than one selfloop." << endl;
            }
         }
      }
      selfloop_trans.erase(t);
      for (auto k : incoming_trans[t])
      {
         markedasdelete_incoming.insert(k.first);
      }
      for (auto k : markedasdelete_incoming)
      {
         outgoing_trans[k].erase(t);
      }
      for (auto k : outgoing_trans[t])
      {
         markedasdelete_outgoing.insert(k.first);
      }
      for (auto k : markedasdelete_outgoing)
      {
         incoming_trans[k].erase(t);
      }
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
      cout << testmap[2][0] << endl; // should print 3, since the map is passed by reference
   }
};


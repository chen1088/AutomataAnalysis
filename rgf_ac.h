# pragma once
#include <iostream>
#include <memory>
#include <vector>
#include "rgfdag.h"
#include <boost/dynamic_bitset.hpp>
using boost::dynamic_bitset;
using namespace std;
enum rgf_ac_op{
   ADD,
   MULTIPLY,
   ONE_MINUS_INVERSE,
   ATOM
};
class rgf_ac: public std::enable_shared_from_this<rgf_ac> {
public:
   rgf_ac();
   ~rgf_ac();
   string to_string() const;
   shared_ptr<rgf_ac> concatenate(shared_ptr<rgf_ac> other);
   shared_ptr<rgf_ac> disjoint_union(shared_ptr<rgf_ac> other);
   shared_ptr<rgf_ac> kleene_star();
   static shared_ptr<rgf_ac> create_add_node(shared_ptr<rgf_ac> left, shared_ptr<rgf_ac> right);
   static shared_ptr<rgf_ac> create_multiply_node(shared_ptr<rgf_ac> left, shared_ptr<rgf_ac> right);
   static shared_ptr<rgf_ac> create_oneminusinverse_node(shared_ptr<rgf_ac> child);
   static shared_ptr<rgf_ac> create_atom_node(shared_ptr<dynamic_bitset<>> label);
   static shared_ptr<rgf_ac> create_one_node();
   static shared_ptr<rgf_ac> construct_from_pdfa_with_source_and_dest_state_direct_pair(const RegPDFA& pdfa, const dynamic_bitset<>& source_state, const dynamic_bitset<>& dest_state);
   static shared_ptr<rgf_ac> construct_from_pdfa_with_source_and_dest_state(const RegPDFA& pdfa, const dynamic_bitset<>& source_state, const dynamic_bitset<>& dest_state);
   static vector<shared_ptr<rgf_ac>> construct_from_pdfa_with_dest_state(const RegPDFA& pdfa, const dynamic_bitset<>& dest_state);
   static map<dynamic_bitset<>, map<dynamic_bitset<>, weak_ptr<rgf_ac>>> construct_from_pdfa_with_all_pairs(const RegPDFA& pdfa);
   vector<shared_ptr<rgf_ac>> children;
   rgf_ac_op operation;
   shared_ptr<dynamic_bitset<>> label;
};
class operation_history{
public:
   
};
rgf_ac::rgf_ac() 
{
   // Constructor implementation (if needed)
}
rgf_ac::~rgf_ac() 
{
   // Destructor implementation (if needed)
}

string rgf_ac::to_string() const 
{
   stringstream ss;
   switch (operation) {
      case ADD:
         ss << "ADD: terms: " << children.size() << " [ ";
         for (const auto& child : children) {
            ss << child->to_string() << " ";
         }
         return ss.str() + "]";
      case MULTIPLY:
         return "MUL: (" + children[0]->to_string() + " * " + children[1]->to_string() + ")";
      case ONE_MINUS_INVERSE:
         return "ONE_MINUS_INVERSE: (1 - 1/" + children[0]->to_string() + ")";
      case ATOM: {
         string label_str;
         boost::to_string(*label, label_str);
         return label_str;
      }
      default:
         return "";
   }
}
shared_ptr<rgf_ac> rgf_ac::create_add_node(shared_ptr<rgf_ac> left, shared_ptr<rgf_ac> right) 
{
   if(left.get()->operation == ADD) {
      left.get()->children.push_back(right);
      return left;
   } else if(right.get()->operation == ADD) {
      right.get()->children.push_back(left);
      return right;
   } else {
      auto node = make_shared<rgf_ac>();
      node->operation = ADD;
      node->children.push_back(left);
      node->children.push_back(right);
      return node;
   }
}
shared_ptr<rgf_ac> rgf_ac::create_multiply_node(shared_ptr<rgf_ac> left, shared_ptr<rgf_ac> right) 
{
   auto node = make_shared<rgf_ac>();
   node->operation = MULTIPLY;
   node->children.push_back(left);
   node->children.push_back(right);
   return node;
}
shared_ptr<rgf_ac> rgf_ac::create_oneminusinverse_node(shared_ptr<rgf_ac> child) 
{
   auto node = make_shared<rgf_ac>();
   node->operation = ONE_MINUS_INVERSE;
   node->children.push_back(child);
   return node;
}
shared_ptr<rgf_ac> rgf_ac::create_atom_node(shared_ptr<dynamic_bitset<>> label) 
{
   auto node = make_shared<rgf_ac>();
   node->operation = ATOM;
   node->label = label;
   return node;
}
shared_ptr<rgf_ac> rgf_ac::concatenate(shared_ptr<rgf_ac> other) 
{
   return rgf_ac::create_multiply_node(shared_from_this(), other);
}
shared_ptr<rgf_ac> rgf_ac::disjoint_union(shared_ptr<rgf_ac> other) 
{
   if(this->operation == ADD && other->operation != ADD) 
   {
      this->children.push_back(other);
      return shared_from_this();
   } 
   else if (this->operation != ADD && other->operation != ADD)
   {
      return rgf_ac::create_add_node(shared_from_this(), other);
   } 
   else if(this->operation == ADD && other->operation == ADD)
   {
      this->children.insert(this->children.end(), other->children.begin(), other->children.end());
      // the other must be reset, but outside of this function.
      // this cannot happen.
      return shared_from_this();
   }
   else
   {
      return other->disjoint_union(shared_from_this());
   }
}
shared_ptr<rgf_ac> rgf_ac::kleene_star() 
{
   return rgf_ac::create_oneminusinverse_node(shared_from_this());
}
vector<shared_ptr<rgf_ac>> rgf_ac::construct_from_pdfa_with_dest_state(const RegPDFA& pdfa, const dynamic_bitset<>& dest_state) 
{
}

static void eliminate_state(map<dynamic_bitset<>, map<dynamic_bitset<>, weak_ptr<rgf_ac>>> &incoming_trans,
                               map<dynamic_bitset<>, map<dynamic_bitset<>, weak_ptr<rgf_ac>>> &outgoing_trans,
                               map<dynamic_bitset<>, weak_ptr<rgf_ac>> &selfloop_trans,
                               stack<operation_history> &revertible_ops,
                               const dynamic_bitset<> t)
{
   operation_history op_hist;
      bool noincoming_flag = false;
      bool hasselfloop = false;
      // if (selfloop_trans[t].size() > 1)
      // {
      //    auto newtree = make_shared<rgf_ac>();
      //    newtree->operation = ADD;
      //    for (auto i : selfloop_trans[t]) newtree->children.push_back(i.lock());
      //    selfloop_trans[t].clear(); selfloop_trans[t].push_back(newtree);
      // }
      // auto selffinal = make_shared<rgf_ac>();
      // selffinal->operation = ONE_MINUS_INVERSE;
      // if(selfloop_trans[t].size() == 1)
      // {
      //    selffinal->children.push_back(selfloop_trans[t][0].lock());
      //    hasselfloop = true;
      // }
      set<dynamic_bitset<>> markedasdelete_incoming;
      set<dynamic_bitset<>> markedasdelete_outgoing;
      map<dynamic_bitset<>, weak_ptr<rgf_ac>> pseudo_start;
      shared_ptr<rgf_ac> selfloop_node;
      if(selfloop_trans.find(t) != selfloop_trans.end())
      {
         selfloop_node = selfloop_trans[t].lock()->kleene_star();
         hasselfloop = true;
      }
      if(incoming_trans[t].size() == 0)
         noincoming_flag = true;
      for (auto i : incoming_trans[t])
      {
         // if (i.second.size() == 0)
         // {
         //    // This only happens when we have a start state with no incoming transitions
         //    // Shall we insert a pseudo incoming transition?
         //    i.second.push_back(new rgfdag<T>(rgf_operation::ONE));
         //    outgoing_trans[t][i.first].push_back(i.second[0]);
         //    noincoming_flag = true;
         // }
         // else if (i.second.size() > 1)
         // {
         //    auto newtree = new rgfdag<T>(rgf_operation::ADD);
         //    for (auto j : i.second) newtree->add_child(j);
         //    i.second.clear(); i.second.push_back(newtree);
         //    outgoing_trans[i.first][t].clear(); outgoing_trans[i.first][t].push_back(newtree);
         // }
         shared_ptr<rgf_ac> newtree_incoming;
         if(hasselfloop)
            newtree_incoming = rgf_ac::create_multiply_node(i.second.lock(), selfloop_node);
         else
            newtree_incoming = i.second.lock();
         for (auto j : outgoing_trans[t])
         {
            auto newtree_incoming_outgoing = rgf_ac::create_multiply_node(newtree_incoming, j.second.lock());
            if (i.first == j.first)
            {
               selfloop_trans[i.first].lock()->disjoint_union(newtree_incoming_outgoing);
            }
            else
            {
               if(!noincoming_flag)
               {
                  incoming_trans[j.first][i.first].lock()->disjoint_union(newtree_incoming_outgoing);
                  outgoing_trans[i.first][j.first].lock()->disjoint_union(newtree_incoming_outgoing);
               }
               else
               {
                  pseudo_start[j.first].lock()->disjoint_union(newtree_incoming_outgoing);
               }
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
      if(noincoming_flag)
      {
         for(auto i : pseudo_start)
         {
            incoming_trans[i.first][dynamic_bitset<>(0)].lock()->disjoint_union(i.second.lock());
            outgoing_trans[dynamic_bitset<>(0)][i.first].lock()->disjoint_union(i.second.lock());
         }
      }
   }
# pragma once
#include <iostream>
#include <memory>
#include <vector>
#include <map>
#include <set>
#include "rgfdag.h"
#include <boost/dynamic_bitset.hpp>
using boost::to_string;
using boost::dynamic_bitset;
using std::move;
using namespace std;
enum rgf_ac_op{
   ADD,
   MULTIPLY,
   ONE_MINUS_INVERSE,
   ATOM
};
class rgf_ac: public enable_shared_from_this<rgf_ac> {
public:
   rgf_ac();
   ~rgf_ac();
   string to_string() const;
   string to_string_nonrecursive() const;
   shared_ptr<rgf_ac> concatenate(shared_ptr<rgf_ac> other);
   shared_ptr<rgf_ac> disjoint_union_with_merge(shared_ptr<rgf_ac> other);
   shared_ptr<rgf_ac> disjoint_union_with_no_merge(shared_ptr<rgf_ac> other);
   shared_ptr<rgf_ac> kleene_star();
   static shared_ptr<rgf_ac> create_add_node_with_merge(shared_ptr<rgf_ac> left, shared_ptr<rgf_ac> right);
   static shared_ptr<rgf_ac> create_add_node_with_no_merge(shared_ptr<rgf_ac> left, shared_ptr<rgf_ac> right);
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
   static void test() {
      map<int, map<int, weak_ptr<rgf_ac>>> testmap;
      shared_ptr<rgf_ac> sp = rgf_ac::create_one_node();
      weak_ptr<rgf_ac> wp(sp);
      // testmap.insert(make_pair(1, map<int, weak_ptr<rgf_ac>>()));
      // testmap[1].insert({2, wp});
      cout<< wp.lock()->to_string_nonrecursive() << endl; // should print empty
      testmap[1][2] = wp;
      if(testmap[1][2].lock() != nullptr) {
         cout << "Not null" << endl;
         cout << testmap[1][2].lock()->to_string_nonrecursive() << endl; // should print empty
      } else
         cout << "Null" << endl;
   }
private:
   static void print_maps(const map<dynamic_bitset<>, map<dynamic_bitset<>, weak_ptr<rgf_ac>>>& incoming_trans,
                          const map<dynamic_bitset<>, map<dynamic_bitset<>, weak_ptr<rgf_ac>>>& outgoing_trans,
                          const map<dynamic_bitset<>, weak_ptr<rgf_ac>>& selfloop_trans)
   {
      cout << "Incoming Transitions:" << endl;
      for (const auto& [dest, src_map] : incoming_trans) {
         string dest_str;
         boost::to_string(dest, dest_str);
         for (const auto& [src, rgf_ptr] : src_map) {
            string src_str;
            boost::to_string(src, src_str);
            cout << "  From " << src_str << " to " << dest_str << ": " << rgf_ptr.lock()->to_string_nonrecursive() << endl;
         }
      }
      cout << "Outgoing Transitions:" << endl;
      for (const auto& [src, dest_map] : outgoing_trans) {
         string src_str;
         boost::to_string(src, src_str);
         for (const auto& [dest, rgf_ptr] : dest_map) {
            string dest_str;
            boost::to_string(dest, dest_str);
            cout << "  From " << src_str << " to " << dest_str << ": " << rgf_ptr.lock()->to_string_nonrecursive() << endl;
         }
      }
      cout << "Self-loop Transitions:" << endl;
      for (const auto& [state, rgf_ptr] : selfloop_trans) {
         string state_str;
         boost::to_string(state, state_str);
         cout << "  State " << state_str << ": " << rgf_ptr.lock()->to_string_nonrecursive() << endl;
      }
   }
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
string rgf_ac::to_string_nonrecursive() const 
{
   string result = "Operation: ";
   switch (operation) {
      case ADD:
         result += "ADD";
         break;
      case MULTIPLY:
         result += "MULTIPLY";
         break;
      case ONE_MINUS_INVERSE:
         result += "ONE_MINUS_INVERSE";
         break;
      case ATOM:
         string buffer;
         boost::to_string(*label, buffer);
         result += "ATOM: ";
         result += buffer;
         break;
   }
   result += ", Children size: " + std::to_string(children.size());
   return result;
}
shared_ptr<rgf_ac> rgf_ac::create_add_node_with_merge(shared_ptr<rgf_ac> left, shared_ptr<rgf_ac> right) 
{
   if(left.get()->operation == ADD) {
      left.get()->children.push_back(right);
      return move(left);
   } else if(right.get()->operation == ADD) {
      right.get()->children.push_back(left);
      return move(right);
   } else {
      auto node = make_shared<rgf_ac>();
      node->operation = ADD;
      node->children.push_back(left);
      node->children.push_back(right);
      return move(node);
   }
}
shared_ptr<rgf_ac> rgf_ac::create_add_node_with_no_merge(shared_ptr<rgf_ac> left, shared_ptr<rgf_ac> right) 
{
   auto node = make_shared<rgf_ac>();
   node->operation = ADD;
   node->children.push_back(left);
   node->children.push_back(right);
   return move(node);
}
shared_ptr<rgf_ac> rgf_ac::create_multiply_node(shared_ptr<rgf_ac> left, shared_ptr<rgf_ac> right) 
{
   auto node = make_shared<rgf_ac>();
   node->operation = MULTIPLY;
   node->children.push_back(left);
   node->children.push_back(right);
   return move(node);
}
shared_ptr<rgf_ac> rgf_ac::create_oneminusinverse_node(shared_ptr<rgf_ac> child) 
{
   auto node = make_shared<rgf_ac>();
   node->operation = ONE_MINUS_INVERSE;
   node->children.push_back(child);
   return move(node);
}
shared_ptr<rgf_ac> rgf_ac::create_atom_node(shared_ptr<dynamic_bitset<>> label) 
{
   auto node = make_shared<rgf_ac>();
   node->operation = ATOM;
   node->label = std::move(label);
   return move(node);
}
shared_ptr<rgf_ac> rgf_ac::create_one_node() 
{
   auto node = make_shared<rgf_ac>();
   node->operation = ATOM;
   node->label = make_shared<dynamic_bitset<>>(0);
   return move(node);
}
shared_ptr<rgf_ac> rgf_ac::concatenate(shared_ptr<rgf_ac> other) 
{
   return rgf_ac::create_multiply_node(shared_from_this(), other);
}
shared_ptr<rgf_ac> rgf_ac::disjoint_union_with_merge(shared_ptr<rgf_ac> other) 
{
   if(this->operation == ADD && other->operation != ADD) 
   {
      this->children.push_back(other);
      return shared_from_this();
   } 
   else if (this->operation != ADD && other->operation != ADD)
   {
      return rgf_ac::create_add_node_with_merge(shared_from_this(), other);
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
      return other->disjoint_union_with_merge(shared_from_this());
   }
}

shared_ptr<rgf_ac> rgf_ac::disjoint_union_with_no_merge(shared_ptr<rgf_ac> other) 
{
   return rgf_ac::create_add_node_with_no_merge(shared_from_this(), other);
}
shared_ptr<rgf_ac> rgf_ac::kleene_star() 
{
   return rgf_ac::create_oneminusinverse_node(shared_from_this());
}
vector<shared_ptr<rgf_ac>> rgf_ac::construct_from_pdfa_with_dest_state(const RegPDFA& pdfa, const dynamic_bitset<>& dest_state) 
{
   vector<shared_ptr<rgf_ac>> result;
   return result;
}
shared_ptr<rgf_ac> rgf_ac::construct_from_pdfa_with_source_and_dest_state_direct_pair(const RegPDFA& pdfa, const dynamic_bitset<>& source_state, const dynamic_bitset<>& dest_state) 
{
   shared_ptr<rgf_ac> result;
   return result;
}
static void eliminate_starting_state(map<dynamic_bitset<>, map<dynamic_bitset<>, weak_ptr<rgf_ac>>> &incoming_trans,
                                     map<dynamic_bitset<>, map<dynamic_bitset<>, weak_ptr<rgf_ac>>> &outgoing_trans,
                                     map<dynamic_bitset<>, weak_ptr<rgf_ac>> &selfloop_trans,
                                     stack<operation_history> &revertible_ops)
{
   operation_history op_hist;
   bool hasselfloop = false;
   set<dynamic_bitset<>> markedasdelete_incoming;
   set<dynamic_bitset<>> markedasdelete_outgoing;
   shared_ptr<rgf_ac> selfloop_node;
   if(selfloop_trans.contains(dynamic_bitset<>(0)))
   {
      selfloop_node = selfloop_trans[dynamic_bitset<>(0)].lock()->kleene_star();
      hasselfloop = true;
   }
   for (auto i : incoming_trans[dynamic_bitset<>(0)])
   {
      shared_ptr<rgf_ac> newtree_incoming;
      if(hasselfloop)
         newtree_incoming = rgf_ac::create_multiply_node(i.second.lock(), selfloop_node);
      else
         newtree_incoming = i.second.lock();
      for (auto j : outgoing_trans[dynamic_bitset<>(0)])
      {
         auto newtree_incoming_outgoing = rgf_ac::create_multiply_node(newtree_incoming, j.second.lock());
         if (i.first == j.first)
         {
            if(selfloop_trans.contains(i.first))
            {
               selfloop_trans[i.first].lock()->disjoint_union_with_no_merge(newtree_incoming_outgoing);
            }
            else  
            {
               selfloop_trans[i.first] = newtree_incoming_outgoing;
            }
         }
         else
         {
            if(incoming_trans.contains(j.first)&&incoming_trans.at(j.first).contains(i.first))
            {
               incoming_trans[j.first][i.first].lock()->disjoint_union_with_no_merge(newtree_incoming_outgoing);
               outgoing_trans[i.first][j.first].lock()->disjoint_union_with_no_merge(newtree_incoming_outgoing);
            }
            else
            {
               incoming_trans[j.first][i.first] = newtree_incoming_outgoing;
               outgoing_trans[i.first][j.first] = newtree_incoming_outgoing;
            }
         }
      }
   }
   if(hasselfloop)
   {
      for(auto i : outgoing_trans[dynamic_bitset<>(0)])
      {
         shared_ptr<rgf_ac> newpseudostart_outgoing;
         newpseudostart_outgoing = rgf_ac::create_multiply_node(selfloop_node, i.second.lock());
         incoming_trans[i.first][dynamic_bitset<>(0)] = newpseudostart_outgoing;
         outgoing_trans[dynamic_bitset<>(0)][i.first] = newpseudostart_outgoing;
      }
   }
   selfloop_trans.erase(dynamic_bitset<>(0));
   for (auto k : incoming_trans[dynamic_bitset<>(0)]) markedasdelete_incoming.insert(k.first);
   for (auto k : markedasdelete_incoming) outgoing_trans[k].erase(dynamic_bitset<>(0));
   incoming_trans.erase(dynamic_bitset<>(0));
}
static void eliminate_state(map<dynamic_bitset<>, map<dynamic_bitset<>, weak_ptr<rgf_ac>>> &incoming_trans,
                               map<dynamic_bitset<>, map<dynamic_bitset<>, weak_ptr<rgf_ac>>> &outgoing_trans,
                               map<dynamic_bitset<>, weak_ptr<rgf_ac>> &selfloop_trans,
                               stack<operation_history> &revertible_ops,
                               const dynamic_bitset<> t)
{
   if(t.size() == 0)
   {
      return eliminate_starting_state(incoming_trans, outgoing_trans, selfloop_trans, revertible_ops);
   }
   operation_history op_hist;
   bool hasselfloop = false;
   set<dynamic_bitset<>> markedasdelete_incoming;
   set<dynamic_bitset<>> markedasdelete_outgoing;
   shared_ptr<rgf_ac> selfloop_node;
   if(selfloop_trans.contains(t))
   {
      selfloop_node = selfloop_trans[t].lock()->kleene_star();
      hasselfloop = true;
   }
   for (auto i : incoming_trans[t])
   {
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
            if(selfloop_trans.contains(i.first))
            {
               selfloop_trans[i.first].lock()->disjoint_union_with_no_merge(newtree_incoming_outgoing);
            }
            else  
            {
               selfloop_trans[i.first] = newtree_incoming_outgoing;
            }
         }
         else
         {
            if(incoming_trans.contains(j.first)&&incoming_trans.at(j.first).contains(i.first))
            {
               incoming_trans[j.first][i.first].lock()->disjoint_union_with_no_merge(newtree_incoming_outgoing);
               outgoing_trans[i.first][j.first].lock()->disjoint_union_with_no_merge(newtree_incoming_outgoing);
            }
            else
            {
               incoming_trans[j.first][i.first] = newtree_incoming_outgoing;
               outgoing_trans[i.first][j.first] = newtree_incoming_outgoing;
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
}
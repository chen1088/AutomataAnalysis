# pragma once
#include <iostream>
#include <memory>
#include <vector>
#include <map>
#include <ranges>
#include <set>
#include "reversible_2d_bimap.h"
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

class rgf_ac_node: public enable_shared_from_this<rgf_ac_node> {
public:
   rgf_ac_node();
   ~rgf_ac_node();
   string to_string() const;
   string to_string_nonrecursive() const;
   shared_ptr<rgf_ac_node> concatenate(const shared_ptr<rgf_ac_node>& other);
   shared_ptr<rgf_ac_node> disjoint_union_with_merge(const shared_ptr<rgf_ac_node>& other);
   shared_ptr<rgf_ac_node> disjoint_union_with_no_merge(const shared_ptr<rgf_ac_node>& other);
   shared_ptr<rgf_ac_node> kleene_star();
   static shared_ptr<rgf_ac_node> create_add_node_with_merge(const shared_ptr<rgf_ac_node> &left, const shared_ptr<rgf_ac_node> &right);
   static shared_ptr<rgf_ac_node> create_add_node_with_no_merge(const shared_ptr<rgf_ac_node> &left, const shared_ptr<rgf_ac_node> &right);
   static shared_ptr<rgf_ac_node> create_multiply_node(const shared_ptr<rgf_ac_node> &left, const shared_ptr<rgf_ac_node> &right);
   static shared_ptr<rgf_ac_node> create_oneminusinverse_node(const shared_ptr<rgf_ac_node> &child);
   static shared_ptr<rgf_ac_node> create_atom_node(const shared_ptr<dynamic_bitset<>> &label);
   static shared_ptr<rgf_ac_node> create_one_node();

   vector<shared_ptr<rgf_ac_node>> children;
   rgf_ac_op operation;
   shared_ptr<dynamic_bitset<>> label;
   
   static void test() {
      map<int, map<int, weak_ptr<rgf_ac_node>>> testmap;
      shared_ptr<rgf_ac_node> sp = rgf_ac_node::create_one_node();
      weak_ptr<rgf_ac_node> wp(sp);
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
   
};

rgf_ac_node::rgf_ac_node() 
{
   // Constructor implementation (if needed)
}
rgf_ac_node::~rgf_ac_node() 
{
   // Destructor implementation (if needed)
}

string rgf_ac_node::to_string() const 
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
         reverse(label_str.begin(), label_str.end());
         return label_str;
      }
      default:
         return "";
   }
}
string rgf_ac_node::to_string_nonrecursive() const 
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
         reverse(buffer.begin(), buffer.end());
         result += buffer;
         break;
   }
   result += ", Children size: " + std::to_string(children.size());
   return result;
}
shared_ptr<rgf_ac_node> rgf_ac_node::create_add_node_with_merge(const shared_ptr<rgf_ac_node> &left, const shared_ptr<rgf_ac_node> &right) 
{
   if(left.get()->operation == ADD) {
      left.get()->children.push_back(right);
      return move(left);
   } else if(right.get()->operation == ADD) {
      right.get()->children.push_back(left);
      return move(right);
   } else {
      auto node = make_shared<rgf_ac_node>();
      node->operation = ADD;
      node->children.push_back(left);
      node->children.push_back(right);
      return move(node);
   }
}
shared_ptr<rgf_ac_node> rgf_ac_node::create_add_node_with_no_merge(const shared_ptr<rgf_ac_node> &left, const shared_ptr<rgf_ac_node> &right) 
{
   auto node = make_shared<rgf_ac_node>();
   node->operation = ADD;
   node->children.push_back(left);
   node->children.push_back(right);
   return move(node);
}
shared_ptr<rgf_ac_node> rgf_ac_node::create_multiply_node(const shared_ptr<rgf_ac_node> &left, const shared_ptr<rgf_ac_node> &right) 
{
   auto node = make_shared<rgf_ac_node>();
   node->operation = MULTIPLY;
   node->children.push_back(left);
   node->children.push_back(right);
   return move(node);
}
shared_ptr<rgf_ac_node> rgf_ac_node::create_oneminusinverse_node(const shared_ptr<rgf_ac_node> &child) 
{
   auto node = make_shared<rgf_ac_node>();
   node->operation = ONE_MINUS_INVERSE;
   node->children.push_back(child);
   return move(node);
}
shared_ptr<rgf_ac_node> rgf_ac_node::create_atom_node(const shared_ptr<dynamic_bitset<>> &label) 
{
   auto node = make_shared<rgf_ac_node>();
   node->operation = ATOM;
   node->label = std::move(label);
   return move(node);
}
shared_ptr<rgf_ac_node> rgf_ac_node::create_one_node() 
{
   auto node = make_shared<rgf_ac_node>();
   node->operation = ATOM;
   node->label = make_shared<dynamic_bitset<>>(0);
   return move(node);
}
shared_ptr<rgf_ac_node> rgf_ac_node::concatenate(const shared_ptr<rgf_ac_node> &other) 
{
   return rgf_ac_node::create_multiply_node(shared_from_this(), other);
}
shared_ptr<rgf_ac_node> rgf_ac_node::disjoint_union_with_merge(const shared_ptr<rgf_ac_node> &other) 
{
   if(this->operation == ADD && other->operation != ADD) 
   {
      this->children.push_back(other);
      return shared_from_this();
   } 
   else if (this->operation != ADD && other->operation != ADD)
   {
      return rgf_ac_node::create_add_node_with_merge(shared_from_this(), other);
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

shared_ptr<rgf_ac_node> rgf_ac_node::disjoint_union_with_no_merge(const shared_ptr<rgf_ac_node> &other) 
{
   return rgf_ac_node::create_add_node_with_no_merge(shared_from_this(), other);
}
shared_ptr<rgf_ac_node> rgf_ac_node::kleene_star() 
{
   return rgf_ac_node::create_oneminusinverse_node(shared_from_this());
}

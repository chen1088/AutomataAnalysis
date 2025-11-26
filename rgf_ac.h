#pragma once
#include <iostream>
#include <memory>
#include <vector>
#include <map>
#include <ranges>
#include <set>
#include "reversible_2d_bimap.h"
#include "rgf_ac_node.h"
#include "RegPDFA.h"
#include <boost/dynamic_bitset.hpp>
using boost::to_string;

class rgf_ac{
public:
   rgf_ac();
   rgf_ac(const RegPDFA& pdfa)
   {
      map<dynamic_bitset<>, map<dynamic_bitset<>, shared_ptr<rgf_ac_node>>> init;
      auto states = pdfa.getallstates();
      for (const auto& state : states) {
         auto state0 = state;
         state0.push_back(false);
         auto state1 = state;
         state1.push_back(true);
         auto dest0 = pdfa.reduce(state0);
         auto dest1 = pdfa.reduce(state1);
         init[state][dest0] = rgf_ac_node::create_atom_node(make_shared<dynamic_bitset<>>(state0));
         init[state][dest1] = rgf_ac_node::create_atom_node(make_shared<dynamic_bitset<>>(state1));
      }
      rgf_ac_bimap = reversible_2d_bimap<dynamic_bitset<>, dynamic_bitset<>, rgf_ac_node>(init);
   }
   static shared_ptr<rgf_ac_node> construct_from_pdfa_with_source_and_dest_state_direct_pair(const RegPDFA& pdfa, const dynamic_bitset<>& source_state, const dynamic_bitset<>& dest_state);
   static shared_ptr<rgf_ac_node> construct_from_pdfa_with_source_and_dest_state(const RegPDFA& pdfa, const dynamic_bitset<>& source_state, const dynamic_bitset<>& dest_state);
   static vector<shared_ptr<rgf_ac_node>> construct_from_pdfa_with_dest_state(const RegPDFA& pdfa, const dynamic_bitset<>& dest_state);
   static map<dynamic_bitset<>, map<dynamic_bitset<>, weak_ptr<rgf_ac_node>>> construct_from_pdfa_with_all_pairs(const RegPDFA& pdfa);
   reversible_2d_bimap<dynamic_bitset<>, dynamic_bitset<>, rgf_ac_node> rgf_ac_bimap;

   inline auto get_incoming_transitions(const dynamic_bitset<>& state) {
      return rgf_ac_bimap.incoming_transitions[state] | views::filter([&state](const auto& pair) {
         return pair.first != state;
      });
   }
   inline auto get_outgoing_transitions(const dynamic_bitset<>& state) {
      return rgf_ac_bimap.outgoing_transitions[state] | views::filter([&state](const auto& pair) {
         return pair.first != state;
      });
   }
   weak_ptr<rgf_ac_node> get_selfloop_transitions(const dynamic_bitset<>& state) {
      return rgf_ac_bimap.incoming_transitions.at(state).at(state);
   }
   bool has_selfloop_transition(const dynamic_bitset<>& state) {
      return rgf_ac_bimap.incoming_transitions.contains(state)&&rgf_ac_bimap.incoming_transitions.at(state).contains(state);
   }
   void add_transition(const dynamic_bitset<>& from_state, const dynamic_bitset<>& to_state, const shared_ptr<rgf_ac_node>& node) {

      rgf_ac_bimap.set_transition(from_state, to_state, node);
   }
   
   void revert_to_last_snapshot() {
      rgf_ac_bimap.revert_to_last_snapshot();
   }
   void eliminate_starting_state()
   {
      bool hasselfloop = false;
      shared_ptr<rgf_ac_node> selfloop_node;
      if(has_selfloop_transition(dynamic_bitset<>(0)))
      {
         //TODO: whenever a new node is created, check if it has been created before to avoid duplication
         selfloop_node = get_selfloop_transitions(dynamic_bitset<>(0)).lock()->kleene_star();
         hasselfloop = true;
      }
      for (auto& i : get_incoming_transitions(dynamic_bitset<>(0)))
      {
         shared_ptr<rgf_ac_node> newtree_incoming;
         if(hasselfloop)
            newtree_incoming = rgf_ac_node::create_multiply_node(i.second, selfloop_node);
         else
            newtree_incoming = i.second;
         for (auto& j : get_outgoing_transitions(dynamic_bitset<>(0)))
         {
            auto newtree_incoming_outgoing = rgf_ac_node::create_multiply_node(newtree_incoming, j.second.lock());
            if(rgf_ac_bimap.incoming_transitions.contains(j.first)&&rgf_ac_bimap.incoming_transitions.at(j.first).contains(i.first))
            {
               auto newadded_node = rgf_ac_node::create_add_node_with_no_merge(rgf_ac_bimap.incoming_transitions[j.first][i.first], newtree_incoming_outgoing);
               rgf_ac_bimap.set_transition(i.first, j.first, newadded_node);
            }
            else
            {
               rgf_ac_bimap.set_transition(i.first, j.first, newtree_incoming_outgoing);
            }
         }
      }
      if(hasselfloop)
      {
         for(auto& i : get_outgoing_transitions(dynamic_bitset<>(0)))
         {
            shared_ptr<rgf_ac_node> newpseudostart_outgoing = rgf_ac_node::create_multiply_node(selfloop_node, i.second.lock());
            rgf_ac_bimap.set_transition(dynamic_bitset<>(0), i.first, newpseudostart_outgoing);
         }
         rgf_ac_bimap.remove_transition(dynamic_bitset<>(0), dynamic_bitset<>(0));
      }
      // remove all transitions that goes into the starting state but keep the outgoing transitions from starting state
      set<dynamic_bitset<>> markedasdelete_incoming;
      for (auto& k : get_incoming_transitions(dynamic_bitset<>(0))) markedasdelete_incoming.insert(k.first);
      for (auto& k : markedasdelete_incoming) rgf_ac_bimap.remove_transition(k, dynamic_bitset<>(0));
   }
   void eliminate_state(const dynamic_bitset<> t)
   {
      if(t.size() == 0)
      {
         return eliminate_starting_state();
      }
      bool hasselfloop = false;
      shared_ptr<rgf_ac_node> selfloop_node;
      if(has_selfloop_transition(t))
      {
         selfloop_node = get_selfloop_transitions(t).lock()->kleene_star();
         hasselfloop = true;
      }
      for (auto i : get_incoming_transitions(t))
      {
         shared_ptr<rgf_ac_node> newtree_incoming;
         if(hasselfloop)
            newtree_incoming = rgf_ac_node::create_multiply_node(i.second, selfloop_node);
         else
            newtree_incoming = i.second;
         for (auto& j : get_outgoing_transitions(t))
         {
            auto newtree_incoming_outgoing = rgf_ac_node::create_multiply_node(newtree_incoming, j.second.lock());
            if(rgf_ac_bimap.incoming_transitions.contains(j.first)&&rgf_ac_bimap.incoming_transitions.at(j.first).contains(i.first))
            {
               auto newadded_node = rgf_ac_node::create_add_node_with_no_merge(rgf_ac_bimap.incoming_transitions[j.first][i.first], newtree_incoming_outgoing);
               rgf_ac_bimap.set_transition(i.first, j.first, newadded_node);
            }
            else
            {
               rgf_ac_bimap.set_transition(i.first, j.first, newtree_incoming_outgoing);
            }
         }
      }
      // remove all transitions related to state t
      set<dynamic_bitset<>> markedasdelete_incoming;
      set<dynamic_bitset<>> markedasdelete_outgoing;
      rgf_ac_bimap.remove_transition(t, t);
      for (auto k : get_incoming_transitions(t)) markedasdelete_incoming.insert(k.first);
      for (auto k : markedasdelete_incoming) rgf_ac_bimap.remove_transition(k, t);
      for (auto k : get_outgoing_transitions(t)) markedasdelete_outgoing.insert(k.first);
      for (auto k : markedasdelete_outgoing) rgf_ac_bimap.remove_transition(t, k);
   };
   void print_bimap()
   {
      for (const auto& from_pair : rgf_ac_bimap.incoming_transitions) {
         const dynamic_bitset<>& from_state = from_pair.first;
         for (const auto& to_pair : from_pair.second) {
            const dynamic_bitset<>& to_state = to_pair.first;
            string from,to;
            to_string(from_state,from);
            reverse(from.begin(), from.end());
            to_string(to_state,to);
            reverse(to.begin(), to.end());
            cout << from << " -> " << to << " Node: " << to_pair.second.get()->to_string_nonrecursive() << endl;
         }
      }
   }
   void eliminate_to_two_states_with_no_snapshot(const dynamic_bitset<>& source_state, const dynamic_bitset<>& dest_state)
   {
      
   }
   static void test()
   {
      RegPDFA pdfa;
      pdfa.initwithstring("001-00,000-0,01-0,10-_,11-1");
      rgf_ac rgfac_obj(pdfa);
      rgfac_obj.print_bimap();
      auto state_to_eliminate = dynamic_bitset<>(0);
      state_to_eliminate.push_back(false);
      rgfac_obj.eliminate_state(state_to_eliminate);
      cout << "After eliminating state 0:" << endl;
      rgfac_obj.print_bimap();
      rgfac_obj.revert_to_last_snapshot();
      cout << "After reverting to last snapshot:" << endl;
      rgfac_obj.print_bimap();
   }
};
#pragma once
#include <iostream>
#include <memory>
#include <vector>
#include <map>
#include <ranges>
using namespace std;
#include <stack>
#include <boost/dynamic_bitset.hpp>

template<typename T,typename U, typename V>
class reversible_2d_bimap {
public:
   struct snapshot{
      vector<tuple<T, U, shared_ptr<V>>> incoming_trans_to_restore;
      vector<pair<T, U>> keys_to_delete;
   };
   stack<snapshot> revertible_operations;
   map<T, map<U, shared_ptr<V>>> incoming_transitions;
   map<T, map<U, weak_ptr<V>>> outgoing_transitions;

   reversible_2d_bimap(){}
   reversible_2d_bimap(map<T, map<U, shared_ptr<V>>>& inc)
       : incoming_transitions(inc)
   {
      for (const auto& from_pair : incoming_transitions) {
         const T& to_state = from_pair.first;
         for (const auto& to_pair : from_pair.second) {
            const U& from_state = to_pair.first;
            outgoing_transitions[from_state][to_state] = to_pair.second;
         }
      }
      save_snapshot();
   }
   void save_snapshot() {
      revertible_operations.push(snapshot());
   }
   void revert_to_last_snapshot() {
      if(revertible_operations.empty()) {
         return;
      }
      auto& last_op = revertible_operations.top();
      const auto& incoming_trans_to_restore = last_op.incoming_trans_to_restore;
      const auto& keys_to_delete = last_op.keys_to_delete;
      for (const auto& [from_state, to_state, old_value] : incoming_trans_to_restore) {
         incoming_transitions[from_state][to_state] = old_value;
      }
      for(const auto& key: keys_to_delete)
      {
         incoming_transitions[key.first].erase(key.second);
         if(incoming_transitions[key.first].empty()) {
            incoming_transitions.erase(key.first);
         }
      }
      revertible_operations.pop();
      if(revertible_operations.empty()) {
         save_snapshot();
      }
   }
   // setters
   void set_transition(const T &from_state, const U &to_state, const weak_ptr<V>& rgf_ptr) {
      if(incoming_transitions.contains(to_state)&&incoming_transitions.at(to_state).contains(from_state))
      {
         // It exists already. We store as weak_ptr because we know it will not be deleted yet.
         record(to_state, from_state, incoming_transitions[to_state][from_state]);
      }
      else
      {
         // new entry
         record_new(to_state, from_state);
      }
      incoming_transitions[to_state][from_state] = rgf_ptr.lock();
      outgoing_transitions[from_state][to_state] = incoming_transitions[to_state][from_state];
   }
   void remove_transition(const T &from_state, const U &to_state) {
      if(incoming_transitions.contains(to_state)&&incoming_transitions.at(to_state).contains(from_state))
      {
         // It exists already. We store as weak_ptr because we know it will not be deleted yet.
         record(to_state, from_state, incoming_transitions[to_state][from_state]);
         incoming_transitions[to_state].erase(from_state);
         outgoing_transitions[from_state].erase(to_state);
         if(incoming_transitions[to_state].empty()) {
            incoming_transitions.erase(to_state);
         }
         if(outgoing_transitions[from_state].empty()) {
            outgoing_transitions.erase(from_state);
         }
      }
   }
   // testers
   static void test() {
      map<string, map<string, string>> testmap;
      testmap["a"]["b"] = "value1";
      testmap["a"]["a"] = "value2";
      testmap["b"]["a"] = "value3";
      auto incoming = testmap | views::filter([](const auto& pair) {
         return pair.first == "c";
      });
      for (const auto& v : views::values(incoming)) {
         for( const auto & vv:views::values(v))
         {
            cout << vv << endl;
         }
         
      }

   }
private:
   void record(T key, U key2, const shared_ptr<V>& old_value) {
      revertible_operations.top().incoming_trans_to_restore.push_back(make_tuple(key, key2, old_value));
   }
   void record_new(T key, U key2) {
      revertible_operations.top().keys_to_delete.push_back(make_pair(key, key2));
   }
};
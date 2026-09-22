#pragma once

#include "rgf_ac_node_v2.h"

#include <boost/dynamic_bitset.hpp>

#include <cstddef>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

// Tree-first implementation of the division-free paired recurrence from
// Chapter 3. Each rgf_ac_node_v2 is a numerator-denominator pair. Every
// occurrence of an operand is deep-cloned, so its two polynomial roots are
// disjoint strict trees rather than shared DAGs.
class rgf_ac_v2
{
public:
   using polynomial_node_type = rgf_ac_polynomial_node_v2;
   using node_type = rgf_ac_node_v2;
   using state_type = boost::dynamic_bitset<>;
   using circuit_row_type = std::map<state_type, node_type>;
   using circuit_table_type = std::map<state_type, circuit_row_type>;

   rgf_ac_v2() = default;

   template <typename Automaton>
   explicit rgf_ac_v2(const Automaton& automaton)
   {
      initialize_from_pdfa(automaton);
   }

   rgf_ac_v2(const rgf_ac_v2&) = delete;
   rgf_ac_v2& operator=(const rgf_ac_v2&) = delete;
   rgf_ac_v2(rgf_ac_v2&&) noexcept = default;
   rgf_ac_v2& operator=(rgf_ac_v2&&) noexcept = default;
   ~rgf_ac_v2() = default;

   // Chapter 3 base nodes.
   [[nodiscard]] node_type create_zero_node()
   {
      return build_circuit_node([this]() {
         return node_type{make_zero_polynomial(), make_one_polynomial()};
      });
   }

   [[nodiscard]] node_type create_one_node()
   {
      return build_circuit_node([this]() {
         return node_type{make_one_polynomial(), make_one_polynomial()};
      });
   }

   [[nodiscard]] node_type create_atom_node(const state_type& label)
   {
      return build_circuit_node([this, &label]() {
         return node_type{make_atom_polynomial(label), make_one_polynomial()};
      });
   }

   [[nodiscard]] node_type create_epsilon_node()
   {
      return create_atom_node(state_type{});
   }

   [[nodiscard]] node_type clone_node(const node_type& value)
   {
      require_owned_circuit_node(value);
      return build_circuit_node([this, &value]() {
         return node_type{
            clone_polynomial(value.numerator_root_),
            clone_polynomial(value.denominator_root_)};
      });
   }

   // (N1/D1) + (N2/D2) = (N1 D2 + N2 D1) / (D1 D2).
   [[nodiscard]] node_type disjoint_union(
      const node_type& left,
      const node_type& right)
   {
      require_owned_circuit_node(left);
      require_owned_circuit_node(right);
      return build_circuit_node([this, &left, &right]() {
         polynomial_node_type* left_term = attach_binary_polynomial(
            rgf_ac_polynomial_op_v2::MULTIPLY,
            clone_polynomial(left.numerator_root_),
            clone_polynomial(right.denominator_root_));
         polynomial_node_type* right_term = attach_binary_polynomial(
            rgf_ac_polynomial_op_v2::MULTIPLY,
            clone_polynomial(right.numerator_root_),
            clone_polynomial(left.denominator_root_));
         polynomial_node_type* numerator = attach_binary_polynomial(
            rgf_ac_polynomial_op_v2::ADD, left_term, right_term);
         polynomial_node_type* denominator = attach_binary_polynomial(
            rgf_ac_polynomial_op_v2::MULTIPLY,
            clone_polynomial(left.denominator_root_),
            clone_polynomial(right.denominator_root_));
         return node_type{numerator, denominator};
      });
   }

   // (N1/D1)(N2/D2) = (N1 N2)/(D1 D2).
   [[nodiscard]] node_type concatenate(
      const node_type& left,
      const node_type& right)
   {
      require_owned_circuit_node(left);
      require_owned_circuit_node(right);
      return build_circuit_node([this, &left, &right]() {
         polynomial_node_type* numerator = attach_binary_polynomial(
            rgf_ac_polynomial_op_v2::MULTIPLY,
            clone_polynomial(left.numerator_root_),
            clone_polynomial(right.numerator_root_));
         polynomial_node_type* denominator = attach_binary_polynomial(
            rgf_ac_polynomial_op_v2::MULTIPLY,
            clone_polynomial(left.denominator_root_),
            clone_polynomial(right.denominator_root_));
         return node_type{numerator, denominator};
      });
   }

   // (N/D)* = D/(D-N). D is cloned twice to preserve strict tree structure.
   [[nodiscard]] node_type kleene_star(const node_type& value)
   {
      require_owned_circuit_node(value);
      return build_circuit_node([this, &value]() {
         polynomial_node_type* numerator =
            clone_polynomial(value.denominator_root_);
         polynomial_node_type* denominator = attach_binary_polynomial(
            rgf_ac_polynomial_op_v2::SUBTRACT,
            clone_polynomial(value.denominator_root_),
            clone_polynomial(value.numerator_root_));
         return node_type{numerator, denominator};
      });
   }

   template <typename Automaton>
   void initialize_from_pdfa(const Automaton& automaton)
   {
      if (!polynomial_arena_.empty() ||
          !circuit_table_.empty() ||
          !remaining_states_.empty())
      {
         throw std::logic_error("rgf_ac_v2 can only be initialized once.");
      }

      // Build in a temporary arena so an exception from the automaton or an
      // allocation leaves this object empty and safe to retry.
      rgf_ac_v2 staged;
      staged.initialize_from_pdfa_in_place(automaton);
      *this = std::move(staged);
   }

   // Adds one literal transition. The first transition replaces the canonical
   // zero base node; genuinely parallel transitions use disjoint union.
   void add_transition_atom(
      const state_type& from,
      const state_type& to,
      const state_type& label)
   {
      ensure_state(from);
      ensure_state(to);

      node_type atom = create_atom_node(label);
      const node_type* direct = find_circuit(from, to);
      if (direct == nullptr)
      {
         throw std::logic_error("All-pairs circuit table is missing an entry.");
      }

      if (is_base_zero_node(*direct))
      {
         circuit_table_.at(from).insert_or_assign(to, atom);
         return;
      }

      node_type combined = disjoint_union(*direct, atom);
      circuit_table_.at(from).insert_or_assign(to, combined);
   }

   // Replaces one matrix entry with a deep tree copy of value.
   void set_circuit(
      const state_type& from,
      const state_type& to,
      const node_type& value)
   {
      node_type copied = clone_node(value);
      ensure_state(from);
      ensure_state(to);
      circuit_table_.at(from).insert_or_assign(to, copied);
   }

   [[nodiscard]] const node_type* find_circuit(
      const state_type& from,
      const state_type& to) const noexcept
   {
      const auto row = circuit_table_.find(from);
      if (row == circuit_table_.end())
      {
         return nullptr;
      }
      const auto entry = row->second.find(to);
      return entry == row->second.end() ? nullptr : &entry->second;
   }

   [[nodiscard]] bool has_circuit(
      const state_type& from,
      const state_type& to) const noexcept
   {
      return find_circuit(from, to) != nullptr;
   }

   // Performs C'_{p,q} = C_{p,q} + C_{p,r}(C_{r,r})*C_{r,q} from
   // an immutable old table, then removes every entry incident with r.
   bool eliminate_state(const state_type& state)
   {
      if (!remaining_states_.contains(state))
      {
         return false;
      }

      std::vector<state_type> survivors;
      survivors.reserve(remaining_states_.size() - 1);
      for (const state_type& candidate : remaining_states_)
      {
         if (candidate != state)
         {
            survivors.push_back(candidate);
         }
      }

      circuit_table_type next_table;
      if (!survivors.empty())
      {
         const node_type* loop = find_circuit(state, state);
         if (loop == nullptr)
         {
            throw std::logic_error(
               "All-pairs circuit table is missing the eliminated-state loop entry.");
         }
         node_type loop_star = kleene_star(*loop);

         for (const state_type& from : survivors)
         {
            const node_type* incoming = find_circuit(from, state);
            if (incoming == nullptr)
            {
               throw std::logic_error(
                  "All-pairs circuit table is missing an incoming entry.");
            }
            for (const state_type& to : survivors)
            {
               const node_type* outgoing = find_circuit(state, to);
               const node_type* direct = find_circuit(from, to);
               if (outgoing == nullptr || direct == nullptr)
               {
                  throw std::logic_error(
                     "All-pairs circuit table is missing an elimination entry.");
               }

               node_type incoming_and_loop = concatenate(*incoming, loop_star);
               node_type through = concatenate(incoming_and_loop, *outgoing);
               node_type updated = disjoint_union(*direct, through);
               next_table[from].insert_or_assign(to, updated);
            }
         }
      }

      eliminated_states_.push_back(state);
      circuit_table_ = std::move(next_table);
      remaining_states_.erase(state);
      return true;
   }

   [[nodiscard]] const circuit_table_type& pairwise_circuits() const noexcept
   {
      return circuit_table_;
   }

   [[nodiscard]] const std::set<state_type>& remaining_states() const noexcept
   {
      return remaining_states_;
   }

   [[nodiscard]] const std::vector<state_type>& eliminated_states() const noexcept
   {
      return eliminated_states_;
   }

   [[nodiscard]] std::size_t polynomial_node_count() const noexcept
   {
      return polynomial_arena_.size();
   }

   [[nodiscard]] bool owns(const polynomial_node_type* node) const noexcept
   {
      return node != nullptr && owned_polynomial_nodes_.contains(node);
   }

   [[nodiscard]] std::string to_string(const node_type& value) const
   {
      require_owned_circuit_node(value);
      return value.to_string();
   }

   // Checks global polynomial parent counts, arities, labels, and ownership.
   [[nodiscard]] bool validate_reference_counts() const noexcept
   {
      try
      {
         std::unordered_map<const polynomial_node_type*, std::size_t> expected;
         expected.reserve(polynomial_arena_.size());
         for (const auto& holder : polynomial_arena_)
         {
            expected.emplace(holder.get(), 0);
         }

         for (const auto& holder : polynomial_arena_)
         {
            const polynomial_node_type* node = holder.get();
            if (node->is_binary_gate())
            {
               if (node->left_ == nullptr ||
                   node->right_ == nullptr ||
                   node->left_ == node->right_ ||
                   !owns(node->left_) ||
                   !owns(node->right_) ||
                   node->has_label_)
               {
                  return false;
               }
               ++expected[node->left_];
               ++expected[node->right_];
            }
            else
            {
               if (node->left_ != nullptr || node->right_ != nullptr)
               {
                  return false;
               }
               if ((node->operation_ == rgf_ac_polynomial_op_v2::ATOM) !=
                   node->has_label_)
               {
                  return false;
               }
            }
         }

         for (const auto& holder : polynomial_arena_)
         {
            const polynomial_node_type* node = holder.get();
            if (node->parent_count_ != expected[node])
            {
               return false;
            }
         }
         return true;
      }
      catch (...)
      {
         return false;
      }
   }

   // Checks that a circuit node contains two disjoint strict polynomial trees.
   [[nodiscard]] bool validate_circuit_node(const node_type& value) const noexcept
   {
      try
      {
         if (!value.valid() ||
             !owns(value.numerator_root_) ||
             !owns(value.denominator_root_))
         {
            return false;
         }
         if (value.numerator_root_->parent_count_ != 0 ||
             value.denominator_root_->parent_count_ != 0)
         {
            return false;
         }

         std::unordered_set<const polynomial_node_type*> seen;
         return validate_polynomial_tree(
                   value.numerator_root_, true, seen) &&
                validate_polynomial_tree(
                   value.denominator_root_, true, seen);
      }
      catch (...)
      {
         return false;
      }
   }

private:
   template <typename Builder>
   [[nodiscard]] node_type build_circuit_node(Builder&& builder)
   {
      const std::size_t checkpoint = polynomial_arena_.size();
      try
      {
         node_type result = std::forward<Builder>(builder)();
         if (!validate_circuit_node(result))
         {
            throw std::logic_error(
               "Constructed rgf_ac_node_v2 is not a strict paired tree.");
         }
         return result;
      }
      catch (...)
      {
         rollback_polynomial_arena(checkpoint);
         throw;
      }
   }

   [[nodiscard]] polynomial_node_type* make_zero_polynomial()
   {
      return make_polynomial_leaf(
         rgf_ac_polynomial_op_v2::ZERO, {}, false);
   }

   [[nodiscard]] polynomial_node_type* make_one_polynomial()
   {
      return make_polynomial_leaf(
         rgf_ac_polynomial_op_v2::ONE, {}, false);
   }

   [[nodiscard]] polynomial_node_type* make_atom_polynomial(
      const state_type& label)
   {
      return make_polynomial_leaf(
         rgf_ac_polynomial_op_v2::ATOM, label, true);
   }

   [[nodiscard]] polynomial_node_type* make_polynomial_leaf(
      rgf_ac_polynomial_op_v2 operation,
      state_type label,
      bool has_label)
   {
      if (operation != rgf_ac_polynomial_op_v2::ZERO &&
          operation != rgf_ac_polynomial_op_v2::ONE &&
          operation != rgf_ac_polynomial_op_v2::ATOM)
      {
         throw std::invalid_argument(
            "Polynomial leaf factory requires ZERO, ONE, or ATOM.");
      }
      if ((operation == rgf_ac_polynomial_op_v2::ATOM) != has_label)
      {
         throw std::invalid_argument(
            "Only ATOM polynomial nodes may carry a label.");
      }

      std::unique_ptr<polynomial_node_type> holder(
         new polynomial_node_type(
            operation,
            nullptr,
            nullptr,
            std::move(label),
            has_label,
            next_polynomial_node_id_));
      return adopt_polynomial_node(std::move(holder));
   }

   [[nodiscard]] polynomial_node_type* clone_polynomial(
      const polynomial_node_type* root)
   {
      require_owned_polynomial(
         root, "Cannot clone a null or foreign polynomial node.");
      switch (root->operation_)
      {
      case rgf_ac_polynomial_op_v2::ZERO:
         return make_zero_polynomial();
      case rgf_ac_polynomial_op_v2::ONE:
         return make_one_polynomial();
      case rgf_ac_polynomial_op_v2::ATOM:
         return make_atom_polynomial(root->label_);
      case rgf_ac_polynomial_op_v2::ADD:
         return attach_binary_polynomial(
            rgf_ac_polynomial_op_v2::ADD,
            clone_polynomial(root->left_),
            clone_polynomial(root->right_));
      case rgf_ac_polynomial_op_v2::MULTIPLY:
         return attach_binary_polynomial(
            rgf_ac_polynomial_op_v2::MULTIPLY,
            clone_polynomial(root->left_),
            clone_polynomial(root->right_));
      case rgf_ac_polynomial_op_v2::SUBTRACT:
         return attach_binary_polynomial(
            rgf_ac_polynomial_op_v2::SUBTRACT,
            clone_polynomial(root->left_),
            clone_polynomial(root->right_));
      }
      throw std::logic_error(
         "Unknown rgf_ac_polynomial_op_v2 value while cloning.");
   }

   [[nodiscard]] polynomial_node_type* attach_binary_polynomial(
      rgf_ac_polynomial_op_v2 operation,
      polynomial_node_type* left,
      polynomial_node_type* right)
   {
      if (operation != rgf_ac_polynomial_op_v2::ADD &&
          operation != rgf_ac_polynomial_op_v2::MULTIPLY &&
          operation != rgf_ac_polynomial_op_v2::SUBTRACT)
      {
         throw std::invalid_argument(
            "Binary polynomial factory requires ADD, MULTIPLY, or SUBTRACT.");
      }
      require_owned_polynomial(
         left, "Left polynomial child is null or belongs to another arena.");
      require_owned_polynomial(
         right, "Right polynomial child is null or belongs to another arena.");
      if (left == right || left->parent_count_ != 0 || right->parent_count_ != 0)
      {
         throw std::logic_error(
            "A strict polynomial tree requires two unattached child roots.");
      }

      std::unique_ptr<polynomial_node_type> holder(
         new polynomial_node_type(
            operation,
            left,
            right,
            {},
            false,
            next_polynomial_node_id_));
      polynomial_node_type* result = adopt_polynomial_node(std::move(holder));
      ++left->parent_count_;
      ++right->parent_count_;
      return result;
   }

   // Adds one state and fills every newly created ordered pair with a fresh
   // zero node (0,1), making the current state table total.
   void ensure_state(const state_type& state)
   {
      if (remaining_states_.contains(state))
      {
         return;
      }

      std::vector<state_type> old_states(
         remaining_states_.begin(), remaining_states_.end());

      // Staging the small node handles adds no arithmetic parent edges and
      // preserves the old table if a map allocation fails.
      circuit_table_type next_table = circuit_table_;
      std::set<state_type> next_states = remaining_states_;
      circuit_row_type new_row;
      for (const state_type& old_state : old_states)
      {
         new_row.emplace(old_state, create_zero_node());
      }
      new_row.emplace(state, create_zero_node());

      for (const state_type& old_state : old_states)
      {
         next_table.at(old_state).emplace(state, create_zero_node());
      }
      next_table.emplace(state, std::move(new_row));
      next_states.insert(state);

      circuit_table_.swap(next_table);
      remaining_states_.swap(next_states);
   }

   template <typename Automaton>
   void initialize_from_pdfa_in_place(const Automaton& automaton)
   {
      for (const state_type& source : automaton.getallstates())
      {
         state_type label_zero = source;
         label_zero.push_back(false);
         state_type destination_zero = automaton.reduce(label_zero);
         add_transition_atom(source, destination_zero, label_zero);

         state_type label_one = source;
         label_one.push_back(true);
         state_type destination_one = automaton.reduce(label_one);
         add_transition_atom(source, destination_one, label_one);
      }
   }

   [[nodiscard]] polynomial_node_type* adopt_polynomial_node(
      std::unique_ptr<polynomial_node_type> holder)
   {
      polynomial_node_type* raw = holder.get();
      polynomial_arena_.push_back(std::move(holder));
      try
      {
         owned_polynomial_nodes_.insert(raw);
      }
      catch (...)
      {
         polynomial_arena_.pop_back();
         throw;
      }
      ++next_polynomial_node_id_;
      return raw;
   }

   void rollback_polynomial_arena(std::size_t checkpoint) noexcept
   {
      while (polynomial_arena_.size() > checkpoint)
      {
         owned_polynomial_nodes_.erase(polynomial_arena_.back().get());
         polynomial_arena_.pop_back();
      }
   }

   void require_owned_polynomial(
      const polynomial_node_type* node,
      const char* message) const
   {
      if (!owns(node))
      {
         throw std::invalid_argument(message);
      }
   }

   void require_owned_circuit_node(const node_type& value) const
   {
      if (!value.valid() ||
          !owns(value.numerator_root_) ||
          !owns(value.denominator_root_))
      {
         throw std::invalid_argument(
            "Circuit node is null or belongs to another rgf_ac_v2 arena.");
      }
   }

   [[nodiscard]] bool is_base_zero_node(const node_type& value) const noexcept
   {
      return value.valid() &&
             owns(value.numerator_root_) &&
             owns(value.denominator_root_) &&
             value.numerator_root_->operation_ ==
                rgf_ac_polynomial_op_v2::ZERO &&
             value.denominator_root_->operation_ ==
                rgf_ac_polynomial_op_v2::ONE &&
             value.numerator_root_->is_leaf() &&
             value.denominator_root_->is_leaf();
   }

   [[nodiscard]] bool validate_polynomial_tree(
      const polynomial_node_type* node,
      bool is_root,
      std::unordered_set<const polynomial_node_type*>& seen) const
   {
      if (!owns(node) || !seen.insert(node).second)
      {
         return false;
      }
      if (node->parent_count_ != (is_root ? 0u : 1u))
      {
         return false;
      }

      if (node->is_binary_gate())
      {
         if (node->left_ == nullptr ||
             node->right_ == nullptr ||
             node->left_ == node->right_ ||
             node->has_label_)
         {
            return false;
         }
         return validate_polynomial_tree(node->left_, false, seen) &&
                validate_polynomial_tree(node->right_, false, seen);
      }

      return node->left_ == nullptr &&
             node->right_ == nullptr &&
             ((node->operation_ == rgf_ac_polynomial_op_v2::ATOM) ==
                node->has_label_);
   }

   std::vector<std::unique_ptr<polynomial_node_type>> polynomial_arena_;
   std::unordered_set<const polynomial_node_type*> owned_polynomial_nodes_;
   std::size_t next_polynomial_node_id_ = 0;
   circuit_table_type circuit_table_;
   std::set<state_type> remaining_states_;
   std::vector<state_type> eliminated_states_;
};

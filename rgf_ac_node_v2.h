#pragma once

#include <boost/dynamic_bitset.hpp>

#include <algorithm>
#include <cstddef>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>

// Operations on one polynomial tree. Division is represented only by the
// numerator-denominator roots stored in rgf_ac_node_v2 below.
enum class rgf_ac_polynomial_op_v2
{
   ZERO,
   ONE,
   ATOM,
   ADD,
   MULTIPLY,
   SUBTRACT
};

class rgf_ac_v2;

// One gate in a numerator or denominator polynomial tree.
class rgf_ac_polynomial_node_v2
{
public:
   using label_type = boost::dynamic_bitset<>;

   rgf_ac_polynomial_node_v2(const rgf_ac_polynomial_node_v2&) = delete;
   rgf_ac_polynomial_node_v2& operator=(const rgf_ac_polynomial_node_v2&) = delete;
   rgf_ac_polynomial_node_v2(rgf_ac_polynomial_node_v2&&) = delete;
   rgf_ac_polynomial_node_v2& operator=(rgf_ac_polynomial_node_v2&&) = delete;
   ~rgf_ac_polynomial_node_v2() = default;

   [[nodiscard]] rgf_ac_polynomial_op_v2 operation() const noexcept
   {
      return operation_;
   }

   [[nodiscard]] const rgf_ac_polynomial_node_v2* left() const noexcept
   {
      return left_;
   }

   [[nodiscard]] const rgf_ac_polynomial_node_v2* right() const noexcept
   {
      return right_;
   }

   [[nodiscard]] const label_type* label() const noexcept
   {
      return has_label_ ? &label_ : nullptr;
   }

   // Number of distinct arithmetic-gate parents. A numerator or denominator
   // root handle is not an arithmetic parent.
   [[nodiscard]] std::size_t parent_count() const noexcept
   {
      return parent_count_;
   }

   [[nodiscard]] std::size_t id() const noexcept
   {
      return id_;
   }

   [[nodiscard]] bool is_leaf() const noexcept
   {
      return operation_ == rgf_ac_polynomial_op_v2::ZERO ||
             operation_ == rgf_ac_polynomial_op_v2::ONE ||
             operation_ == rgf_ac_polynomial_op_v2::ATOM;
   }

   [[nodiscard]] bool is_binary_gate() const noexcept
   {
      return operation_ == rgf_ac_polynomial_op_v2::ADD ||
             operation_ == rgf_ac_polynomial_op_v2::MULTIPLY ||
             operation_ == rgf_ac_polynomial_op_v2::SUBTRACT;
   }

   [[nodiscard]] std::string to_string_nonrecursive() const
   {
      std::string result = operation_name(operation_);
      if (operation_ == rgf_ac_polynomial_op_v2::ATOM)
      {
         result += "(" + atom_name() + ")";
      }
      result += " [id=" + std::to_string(id_) +
                ", parents=" + std::to_string(parent_count_) + "]";
      return result;
   }

   [[nodiscard]] std::string to_string() const
   {
      std::unordered_set<const rgf_ac_polynomial_node_v2*> active_path;
      return to_string_impl(active_path);
   }

   [[nodiscard]] static std::string operation_name(
      rgf_ac_polynomial_op_v2 operation)
   {
      switch (operation)
      {
      case rgf_ac_polynomial_op_v2::ZERO:
         return "ZERO";
      case rgf_ac_polynomial_op_v2::ONE:
         return "ONE";
      case rgf_ac_polynomial_op_v2::ATOM:
         return "ATOM";
      case rgf_ac_polynomial_op_v2::ADD:
         return "ADD";
      case rgf_ac_polynomial_op_v2::MULTIPLY:
         return "MULTIPLY";
      case rgf_ac_polynomial_op_v2::SUBTRACT:
         return "SUBTRACT";
      }
      throw std::logic_error("Unknown rgf_ac_polynomial_op_v2 value.");
   }

private:
   friend class rgf_ac_v2;

   rgf_ac_polynomial_node_v2(
      rgf_ac_polynomial_op_v2 operation,
      rgf_ac_polynomial_node_v2* left,
      rgf_ac_polynomial_node_v2* right,
      label_type label,
      bool has_label,
      std::size_t id)
      : operation_(operation),
        left_(left),
        right_(right),
        label_(std::move(label)),
        has_label_(has_label),
        id_(id)
   {
   }

   [[nodiscard]] std::string atom_name() const
   {
      if (!has_label_)
      {
         throw std::logic_error("ATOM polynomial node has no label.");
      }
      if (label_.empty())
      {
         return "x_epsilon";
      }

      std::string bits;
      boost::to_string(label_, bits);
      std::reverse(bits.begin(), bits.end());
      return "x_{" + bits + "}";
   }

   [[nodiscard]] std::string to_string_impl(
      std::unordered_set<const rgf_ac_polynomial_node_v2*>& active_path) const
   {
      if (!active_path.insert(this).second)
      {
         return "<cycle>";
      }

      std::string result;
      switch (operation_)
      {
      case rgf_ac_polynomial_op_v2::ZERO:
         result = "0";
         break;
      case rgf_ac_polynomial_op_v2::ONE:
         result = "1";
         break;
      case rgf_ac_polynomial_op_v2::ATOM:
         result = atom_name();
         break;
      case rgf_ac_polynomial_op_v2::ADD:
         result = "(" + left_->to_string_impl(active_path) + " + " +
                  right_->to_string_impl(active_path) + ")";
         break;
      case rgf_ac_polynomial_op_v2::MULTIPLY:
         result = "(" + left_->to_string_impl(active_path) + " * " +
                  right_->to_string_impl(active_path) + ")";
         break;
      case rgf_ac_polynomial_op_v2::SUBTRACT:
         result = "(" + left_->to_string_impl(active_path) + " - " +
                  right_->to_string_impl(active_path) + ")";
         break;
      }

      active_path.erase(this);
      return result;
   }

   rgf_ac_polynomial_op_v2 operation_;
   rgf_ac_polynomial_node_v2* left_ = nullptr;
   rgf_ac_polynomial_node_v2* right_ = nullptr;
   label_type label_;
   bool has_label_ = false;
   std::size_t parent_count_ = 0;
   std::size_t id_ = 0;
};

// One rational arithmetic-circuit node. It is the numerator-denominator pair
// requested by Chapter 3. This is a non-owning value handle: rgf_ac_v2 owns
// both polynomial trees, and copied handles must not outlive that arena.
class rgf_ac_node_v2
{
public:
   using polynomial_node_type = rgf_ac_polynomial_node_v2;

   rgf_ac_node_v2() = delete;
   rgf_ac_node_v2(const rgf_ac_node_v2&) noexcept = default;
   rgf_ac_node_v2& operator=(const rgf_ac_node_v2&) noexcept = default;
   rgf_ac_node_v2(rgf_ac_node_v2&&) noexcept = default;
   rgf_ac_node_v2& operator=(rgf_ac_node_v2&&) noexcept = default;
   ~rgf_ac_node_v2() = default;

   [[nodiscard]] const polynomial_node_type* numerator_root() const noexcept
   {
      return numerator_root_;
   }

   [[nodiscard]] const polynomial_node_type* denominator_root() const noexcept
   {
      return denominator_root_;
   }

   [[nodiscard]] bool valid() const noexcept
   {
      return numerator_root_ != nullptr && denominator_root_ != nullptr;
   }

   [[nodiscard]] std::string to_string() const
   {
      return "(" + numerator_root_->to_string() + ") / (" +
             denominator_root_->to_string() + ")";
   }

private:
   friend class rgf_ac_v2;

   rgf_ac_node_v2(
      polynomial_node_type* numerator_root,
      polynomial_node_type* denominator_root) noexcept
      : numerator_root_(numerator_root),
        denominator_root_(denominator_root)
   {
   }

   polynomial_node_type* numerator_root_;
   polynomial_node_type* denominator_root_;
};

#pragma once

#include <boost/dynamic_bitset.hpp>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <iterator>
#include <limits>
#include <ostream>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

// A sequence of symbols over an alphabet of size 2^k.
//
// Each symbol is stored in k consecutive bits of a boost::dynamic_bitset.
// Public symbol values are integers in [0, 2^k - 1]. The default k is 2,
// matching the alphabet {0, 1, 2, 3}.
class dynamic_alphabetset
{
public:
   // Unsigned integer type used to represent one alphabet symbol.
   using symbol_type = std::uint64_t;
   using size_type = std::size_t;
   using difference_type = std::ptrdiff_t;
   using block_type = boost::dynamic_bitset<>::block_type;

   // Default alphabet size is 2^2. At most 64 bits fit in symbol_type.
   static constexpr size_type default_bits_per_symbol = 2;
   static constexpr size_type max_bits_per_symbol = std::numeric_limits<symbol_type>::digits;
   static constexpr size_type bits_per_block = std::numeric_limits<block_type>::digits;
   static constexpr size_type npos = static_cast<size_type>(-1);

   // Const random-access iterator over decoded symbols.
   class const_iterator
   {
   public:
      using iterator_category = std::random_access_iterator_tag;
      using iterator_concept = std::random_access_iterator_tag;
      using value_type = symbol_type;
      using difference_type = dynamic_alphabetset::difference_type;
      using reference = symbol_type;
      using pointer = void;

      const_iterator() = default;

      [[nodiscard]] reference operator*() const
      {
         return owner_->at(index_);
      }

      [[nodiscard]] reference operator[](difference_type offset) const
      {
         return *(*this + offset);
      }

      const_iterator &operator++()
      {
         ++index_;
         return *this;
      }

      const_iterator operator++(int)
      {
         const_iterator copy = *this;
         ++(*this);
         return copy;
      }

      const_iterator &operator--()
      {
         --index_;
         return *this;
      }

      const_iterator operator--(int)
      {
         const_iterator copy = *this;
         --(*this);
         return copy;
      }

      const_iterator &operator+=(difference_type offset)
      {
         index_ = static_cast<size_type>(static_cast<difference_type>(index_) + offset);
         return *this;
      }

      const_iterator &operator-=(difference_type offset)
      {
         return *this += -offset;
      }

      friend const_iterator operator+(const_iterator iterator, difference_type offset)
      {
         iterator += offset;
         return iterator;
      }

      friend const_iterator operator+(difference_type offset, const_iterator iterator)
      {
         iterator += offset;
         return iterator;
      }

      friend const_iterator operator-(const_iterator iterator, difference_type offset)
      {
         iterator -= offset;
         return iterator;
      }

      friend difference_type operator-(const const_iterator &lhs, const const_iterator &rhs)
      {
         return static_cast<difference_type>(lhs.index_) - static_cast<difference_type>(rhs.index_);
      }

      friend bool operator==(const const_iterator &lhs, const const_iterator &rhs)
      {
         return lhs.owner_ == rhs.owner_ && lhs.index_ == rhs.index_;
      }

      friend bool operator!=(const const_iterator &lhs, const const_iterator &rhs)
      {
         return !(lhs == rhs);
      }

      friend bool operator<(const const_iterator &lhs, const const_iterator &rhs)
      {
         return lhs.index_ < rhs.index_;
      }

      friend bool operator>(const const_iterator &lhs, const const_iterator &rhs)
      {
         return rhs < lhs;
      }

      friend bool operator<=(const const_iterator &lhs, const const_iterator &rhs)
      {
         return !(rhs < lhs);
      }

      friend bool operator>=(const const_iterator &lhs, const const_iterator &rhs)
      {
         return !(lhs < rhs);
      }

   private:
      friend class dynamic_alphabetset;

      const_iterator(const dynamic_alphabetset *owner, size_type index)
          : owner_(owner), index_(index)
      {
      }

      const dynamic_alphabetset *owner_ = nullptr;
      size_type index_ = 0;
   };

   using iterator = const_iterator;
   using const_reverse_iterator = std::reverse_iterator<const_iterator>;
   using reverse_iterator = const_reverse_iterator;

   // Constructs the empty word over the default alphabet.
   dynamic_alphabetset() = default;

   // Constructs a word of symbol_count copies of fill_symbol.
   // Throws if bits_per_symbol is outside [1, 64] or fill_symbol is not in
   // the configured alphabet.
   explicit dynamic_alphabetset(
       std::size_t symbol_count,
       symbol_type fill_symbol = 0,
       std::size_t bits_per_symbol = default_bits_per_symbol)
       : bits_per_symbol_(checked_bits_per_symbol(bits_per_symbol))
   {
      resize(symbol_count, fill_symbol);
   }

   // Constructs from packed storage. bits.size() must be divisible by
   // bits_per_symbol.
   explicit dynamic_alphabetset(
       const boost::dynamic_bitset<> &bits,
       std::size_t bits_per_symbol = default_bits_per_symbol)
       : bits_per_symbol_(checked_bits_per_symbol(bits_per_symbol)), bits_(bits)
   {
      validate_storage_size();
   }

   // Move-constructs from packed storage. bits.size() must be divisible by
   // bits_per_symbol.
   explicit dynamic_alphabetset(
       boost::dynamic_bitset<> &&bits,
       std::size_t bits_per_symbol = default_bits_per_symbol)
       : bits_per_symbol_(checked_bits_per_symbol(bits_per_symbol)), bits_(std::move(bits))
   {
      validate_storage_size();
   }

   // Constructs from compact single-character symbols.
   //
   // Accepted input symbols are 0-9, A-Z, and a-z. The marker "_" denotes
   // the empty word. Use the numeric constructors for symbols >= 36.
   explicit dynamic_alphabetset(
       std::string_view symbols,
       std::size_t bits_per_symbol = default_bits_per_symbol)
       : bits_per_symbol_(checked_bits_per_symbol(bits_per_symbol))
   {
      assign(symbols);
   }

   // Constructs from numeric symbols.
   dynamic_alphabetset(
       std::initializer_list<symbol_type> symbols,
       std::size_t bits_per_symbol = default_bits_per_symbol)
       : bits_per_symbol_(checked_bits_per_symbol(bits_per_symbol))
   {
      assign(symbols);
   }

   // Constructs an empty word whose alphabet has size 2^bits_per_symbol.
   static dynamic_alphabetset with_bits_per_symbol(std::size_t bits_per_symbol)
   {
      dynamic_alphabetset result;
      result.bits_per_symbol_ = checked_bits_per_symbol(bits_per_symbol);
      return result;
   }

   // Constructs an empty word whose alphabet has the requested power-of-two
   // size. For example, with_alphabet_size(8) stores three bits per symbol.
   static dynamic_alphabetset with_alphabet_size(symbol_type alphabet_size)
   {
      return with_bits_per_symbol(bits_for_power_of_two_alphabet(alphabet_size));
   }

   // Lifts a binary bitset into this representation. A set bit becomes symbol
   // 1 and an unset bit becomes symbol 0.
   static dynamic_alphabetset from_binary_bitset(
       const boost::dynamic_bitset<> &binary,
       std::size_t bits_per_symbol = default_bits_per_symbol)
   {
      dynamic_alphabetset result = with_bits_per_symbol(bits_per_symbol);
      result.bits_.resize(binary.size() * result.bits_per_symbol_);
      for (std::size_t i = 0; i < binary.size(); ++i)
      {
         result.set_symbol(i, binary[i] ? 1u : 0u);
      }
      return result;
   }

   // Replaces the contents with compact single-character symbols.
   void assign(std::string_view symbols)
   {
      bits_.clear();
      if (symbols == "_")
      {
         return;
      }

      bits_.resize(symbols.size() * bits_per_symbol_);
      for (std::size_t i = 0; i < symbols.size(); ++i)
      {
         set_symbol(i, parse_symbol(symbols[i]));
      }
   }

   // Replaces the contents with numeric symbols.
   void assign(std::span<const symbol_type> symbols)
   {
      bits_.clear();
      bits_.resize(symbols.size() * bits_per_symbol_);
      for (std::size_t i = 0; i < symbols.size(); ++i)
      {
         set_symbol(i, symbols[i]);
      }
   }

   // Replaces the contents with numeric symbols.
   void assign(std::initializer_list<symbol_type> symbols)
   {
      assign(std::span<const symbol_type>(symbols.begin(), symbols.size()));
   }

   // Number of symbols in the word.
   [[nodiscard]] std::size_t size() const noexcept
   {
      return bits_.size() / bits_per_symbol_;
   }

   // Number of packed bits used by the word.
   [[nodiscard]] std::size_t bit_size() const noexcept
   {
      return bits_.size();
   }

   // True iff the word contains no symbols.
   [[nodiscard]] bool empty() const noexcept
   {
      return bits_.empty();
   }

   // Number of bits used to encode one symbol.
   [[nodiscard]] std::size_t bits_per_symbol() const noexcept
   {
      return bits_per_symbol_;
   }

   // Largest valid symbol value for this alphabet.
   [[nodiscard]] symbol_type max_symbol() const noexcept
   {
      return max_symbol_for(bits_per_symbol_);
   }

   // Removes all symbols while preserving the configured alphabet.
   void clear() noexcept
   {
      bits_.clear();
   }

   // Returns an iterator to the first symbol.
   [[nodiscard]] const_iterator begin() const noexcept
   {
      return const_iterator(this, 0);
   }

   // Returns an iterator past the last symbol.
   [[nodiscard]] const_iterator end() const noexcept
   {
      return const_iterator(this, size());
   }

   [[nodiscard]] const_iterator cbegin() const noexcept
   {
      return begin();
   }

   [[nodiscard]] const_iterator cend() const noexcept
   {
      return end();
   }

   [[nodiscard]] const_reverse_iterator rbegin() const noexcept
   {
      return const_reverse_iterator(end());
   }

   [[nodiscard]] const_reverse_iterator rend() const noexcept
   {
      return const_reverse_iterator(begin());
   }

   [[nodiscard]] const_reverse_iterator crbegin() const noexcept
   {
      return rbegin();
   }

   [[nodiscard]] const_reverse_iterator crend() const noexcept
   {
      return rend();
   }

   // Returns the first symbol. Throws if the word is empty.
   [[nodiscard]] symbol_type front() const
   {
      if (empty())
      {
         throw std::out_of_range("Cannot read the first symbol of an empty dynamic_alphabetset.");
      }
      return get_symbol(0);
   }

   // Returns the symbol at index. Throws if index is out of range.
   [[nodiscard]] symbol_type at(std::size_t index) const
   {
      ensure_symbol_index(index);
      return get_symbol(index);
   }

   // Returns the symbol at index with checked access.
   [[nodiscard]] symbol_type operator[](std::size_t index) const
   {
      return at(index);
   }

   // Returns the last symbol. Throws if the word is empty.
   [[nodiscard]] symbol_type back() const
   {
      if (empty())
      {
         throw std::out_of_range("Cannot read the last symbol of an empty dynamic_alphabetset.");
      }
      return get_symbol(size() - 1);
   }

   // Sets every symbol to the largest symbol in the alphabet.
   dynamic_alphabetset &set()
   {
      for (std::size_t i = 0; i < size(); ++i)
      {
         set_symbol(i, max_symbol());
      }
      return *this;
   }

   // Sets one symbol to the largest symbol in the alphabet.
   dynamic_alphabetset &set(std::size_t index)
   {
      ensure_symbol_index(index);
      set_symbol(index, max_symbol());
      return *this;
   }

   // Sets one symbol to a chosen value.
   dynamic_alphabetset &set(std::size_t index, symbol_type symbol)
   {
      ensure_symbol_index(index);
      set_symbol(index, symbol);
      return *this;
   }

   // Replaces one symbol and returns its old value.
   symbol_type test_set(std::size_t index, symbol_type symbol)
   {
      ensure_symbol_index(index);
      const auto old_symbol = get_symbol(index);
      set_symbol(index, symbol);
      return old_symbol;
   }

   // Resets every symbol to 0.
   dynamic_alphabetset &reset()
   {
      bits_.reset();
      return *this;
   }

   // Resets one symbol to 0.
   dynamic_alphabetset &reset(std::size_t index)
   {
      ensure_symbol_index(index);
      set_symbol(index, 0);
      return *this;
   }

   // Complements every symbol inside the configured alphabet.
   dynamic_alphabetset &flip()
   {
      for (std::size_t i = 0; i < size(); ++i)
      {
         set_symbol(i, max_symbol() ^ get_symbol(i));
      }
      return *this;
   }

   // Complements one symbol inside the configured alphabet.
   dynamic_alphabetset &flip(std::size_t index)
   {
      ensure_symbol_index(index);
      set_symbol(index, max_symbol() ^ get_symbol(index));
      return *this;
   }

   // True iff the symbol at index is nonzero.
   [[nodiscard]] bool test(std::size_t index) const
   {
      ensure_symbol_index(index);
      return get_symbol(index) != 0;
   }

   // Appends one symbol. Throws if the symbol is not in the alphabet.
   void push_back(symbol_type symbol)
   {
      validate_symbol(symbol);
      const auto symbol_index = size();
      bits_.resize(bits_.size() + bits_per_symbol_);
      set_symbol(symbol_index, symbol);
   }

   // Appends one symbol. Synonym for push_back.
   void append(symbol_type symbol)
   {
      push_back(symbol);
   }

   // Appends another word. Both words must use the same bits_per_symbol.
   void append(const dynamic_alphabetset &other)
   {
      ensure_same_alphabet(other);
      const auto original_size = size();
      bits_.resize(bits_.size() + other.bits_.size());
      for (std::size_t i = 0; i < other.size(); ++i)
      {
         set_symbol(original_size + i, other[i]);
      }
   }

   // Removes the last symbol. Throws if the word is empty.
   void pop_back()
   {
      if (empty())
      {
         throw std::out_of_range("Cannot pop from an empty dynamic_alphabetset.");
      }
      bits_.resize(bits_.size() - bits_per_symbol_);
   }

   // Resizes to symbol_count symbols. New symbols, if any, are fill_symbol.
   void resize(std::size_t symbol_count, symbol_type fill_symbol = 0)
   {
      const auto current_size = size();
      if (symbol_count <= current_size)
      {
         bits_.resize(symbol_count * bits_per_symbol_);
         return;
      }

      validate_symbol(fill_symbol);
      bits_.resize(symbol_count * bits_per_symbol_);
      for (std::size_t i = current_size; i < symbol_count; ++i)
      {
         set_symbol(i, fill_symbol);
      }
   }

   // Number of nonzero symbols.
   [[nodiscard]] std::size_t count() const
   {
      std::size_t result = 0;
      for (std::size_t i = 0; i < size(); ++i)
      {
         if (get_symbol(i) != 0)
         {
            ++result;
         }
      }
      return result;
   }

   // Number of occurrences of symbol.
   [[nodiscard]] std::size_t count(symbol_type symbol) const
   {
      validate_symbol(symbol);
      std::size_t result = 0;
      for (std::size_t i = 0; i < size(); ++i)
      {
         if (get_symbol(i) == symbol)
         {
            ++result;
         }
      }
      return result;
   }

   // True iff any symbol is nonzero.
   [[nodiscard]] bool any() const
   {
      return bits_.any();
   }

   // True iff no symbol is nonzero.
   [[nodiscard]] bool none() const
   {
      return bits_.none();
   }

   // True iff every symbol is the largest symbol in the alphabet.
   [[nodiscard]] bool all() const
   {
      return bits_.all();
   }

   // True iff symbol occurs in the word.
   [[nodiscard]] bool contains(symbol_type symbol) const
   {
      return find_first(symbol) != npos;
   }

   // Finds the first nonzero symbol, or npos.
   [[nodiscard]] std::size_t find_first() const
   {
      for (std::size_t i = 0; i < size(); ++i)
      {
         if (get_symbol(i) != 0)
         {
            return i;
         }
      }
      return npos;
   }

   // Finds the first occurrence of symbol, or npos.
   [[nodiscard]] std::size_t find_first(symbol_type symbol) const
   {
      validate_symbol(symbol);
      for (std::size_t i = 0; i < size(); ++i)
      {
         if (get_symbol(i) == symbol)
         {
            return i;
         }
      }
      return npos;
   }

   // Finds the first nonzero symbol after previous, or npos.
   [[nodiscard]] std::size_t find_next(std::size_t previous) const
   {
      if (previous >= size())
      {
         return npos;
      }
      for (std::size_t i = previous + 1; i < size(); ++i)
      {
         if (get_symbol(i) != 0)
         {
            return i;
         }
      }
      return npos;
   }

   // Finds the first occurrence of symbol after previous, or npos.
   [[nodiscard]] std::size_t find_next(std::size_t previous, symbol_type symbol) const
   {
      validate_symbol(symbol);
      if (previous >= size())
      {
         return npos;
      }
      for (std::size_t i = previous + 1; i < size(); ++i)
      {
         if (get_symbol(i) == symbol)
         {
            return i;
         }
      }
      return npos;
   }

   // Returns compact symbols as characters 0-9 and A-Z.
   // Throws if any symbol is >= 36. Use can_use_compact_symbol_string() first
   // or call to_delimited_symbol_string() for arbitrary symbol values.
   [[nodiscard]] std::string to_symbol_string(char empty_marker = '\0') const
   {
      if (empty())
      {
         return empty_marker == '\0' ? std::string() : std::string(1, empty_marker);
      }

      std::string result;
      result.reserve(size());
      for (std::size_t i = 0; i < size(); ++i)
      {
         result.push_back(symbol_to_char(get_symbol(i)));
      }
      return result;
   }

   // Returns decimal symbol values separated by separator.
   [[nodiscard]] std::string to_delimited_symbol_string(
       char separator = ',',
       std::string_view empty_marker = "") const
   {
      if (empty())
      {
         return std::string(empty_marker);
      }

      std::string result;
      for (std::size_t i = 0; i < size(); ++i)
      {
         if (i != 0)
         {
            result.push_back(separator);
         }
         result += std::to_string(get_symbol(i));
      }
      return result;
   }

   // True iff to_symbol_string() can represent every symbol.
   [[nodiscard]] bool can_use_compact_symbol_string() const
   {
      for (std::size_t i = 0; i < size(); ++i)
      {
         if (get_symbol(i) >= 36u)
         {
            return false;
         }
      }
      return true;
   }

   // Returns each symbol as a k-bit binary group, most-significant bit first
   // within each group.
   [[nodiscard]] std::string to_grouped_bit_string(char separator = ' ') const
   {
      if (empty())
      {
         return "";
      }

      std::string result;
      result.reserve(bit_size() + (separator == '\0' ? 0 : size() - 1));
      for (std::size_t i = 0; i < size(); ++i)
      {
         if (i != 0 && separator != '\0')
         {
            result.push_back(separator);
         }

         const auto symbol = get_symbol(i);
         for (std::size_t bit = bits_per_symbol_; bit > 0; --bit)
         {
            const auto offset = bit - 1;
            result.push_back((symbol & (symbol_type{1} << offset)) != 0u ? '1' : '0');
         }
      }
      return result;
   }

   // Returns boost::dynamic_bitset's full raw bit string.
   [[nodiscard]] std::string to_raw_bit_string() const
   {
      std::string result;
      boost::to_string(bits_, result);
      return result;
   }

   // Converts to a binary bitset. Throws unless all symbols are 0 or 1.
   [[nodiscard]] boost::dynamic_bitset<> to_binary_bitset() const
   {
      boost::dynamic_bitset<> binary(size());
      for (std::size_t i = 0; i < size(); ++i)
      {
         const auto symbol = get_symbol(i);
         if (symbol > 1u)
         {
            throw std::invalid_argument("Cannot convert symbols greater than 1 into a binary dynamic_bitset.");
         }
         binary[i] = symbol == 1u;
      }
      return binary;
   }

   // Shifts symbols toward lower indices. Vacated positions are filled with 0.
   dynamic_alphabetset &operator<<=(std::size_t shift)
   {
      const auto symbol_count = size();
      if (shift >= symbol_count)
      {
         return reset();
      }

      for (std::size_t i = 0; i + shift < symbol_count; ++i)
      {
         set_symbol(i, get_symbol(i + shift));
      }
      for (std::size_t i = symbol_count - shift; i < symbol_count; ++i)
      {
         set_symbol(i, 0);
      }
      return *this;
   }

   // Shifts symbols toward higher indices. Vacated positions are filled with 0.
   dynamic_alphabetset &operator>>=(std::size_t shift)
   {
      const auto symbol_count = size();
      if (shift >= symbol_count)
      {
         return reset();
      }

      for (std::size_t i = symbol_count; i-- > shift;)
      {
         set_symbol(i, get_symbol(i - shift));
      }
      for (std::size_t i = 0; i < shift; ++i)
      {
         set_symbol(i, 0);
      }
      return *this;
   }

   friend dynamic_alphabetset operator<<(dynamic_alphabetset value, std::size_t shift)
   {
      value <<= shift;
      return value;
   }

   friend dynamic_alphabetset operator>>(dynamic_alphabetset value, std::size_t shift)
   {
      value >>= shift;
      return value;
   }

   // Number of storage blocks needed for the packed representation.
   [[nodiscard]] std::size_t num_blocks() const
   {
      return bits_.num_blocks();
   }

   // Copies packed storage blocks to result.
   template <typename BlockOutputIterator>
   void to_block_range(BlockOutputIterator result) const
   {
      boost::to_block_range(bits_, result);
   }

   // Returns packed storage blocks.
   [[nodiscard]] std::vector<block_type> to_block_vector() const
   {
      std::vector<block_type> blocks;
      blocks.reserve(num_blocks());
      to_block_range(std::back_inserter(blocks));
      return blocks;
   }

   // Constructs from packed storage blocks. Extra high bits in the final block
   // are ignored.
   static dynamic_alphabetset from_blocks(
       std::span<const block_type> blocks,
       std::size_t symbol_count,
       std::size_t bits_per_symbol = default_bits_per_symbol)
   {
      const auto checked_bits = checked_bits_per_symbol(bits_per_symbol);
      const auto bit_count = checked_storage_bit_count(symbol_count, checked_bits);
      const auto required_blocks = (bit_count + bits_per_block - 1) / bits_per_block;
      if (blocks.size() < required_blocks)
      {
         throw std::invalid_argument("Not enough blocks to initialize dynamic_alphabetset storage.");
      }

      dynamic_alphabetset result = with_bits_per_symbol(checked_bits);
      result.bits_.resize(bit_count);
      for (std::size_t bit = 0; bit < bit_count; ++bit)
      {
         const auto block_index = bit / bits_per_block;
         const auto block_offset = bit % bits_per_block;
         result.bits_[bit] = (blocks[block_index] & (block_type{1} << block_offset)) != 0u;
      }
      return result;
   }

   // Appends the low bit_count bits from block. The resulting storage size must
   // still be divisible by bits_per_symbol().
   void append_bits(block_type block, std::size_t bit_count)
   {
      if (bit_count > bits_per_block)
      {
         throw std::invalid_argument("Cannot append more bits than a storage block contains.");
      }
      if ((bit_size() + bit_count) % bits_per_symbol_ != 0)
      {
         throw std::invalid_argument("Appending bits would violate the dynamic_alphabetset storage invariant.");
      }

      const auto original_bit_size = bit_size();
      bits_.resize(original_bit_size + bit_count);
      for (std::size_t offset = 0; offset < bit_count; ++offset)
      {
         bits_[original_bit_size + offset] = (block & (block_type{1} << offset)) != 0u;
      }
   }

   // Appends one full storage block.
   void append_block(block_type block)
   {
      append_bits(block, bits_per_block);
   }

   // Appends full storage blocks.
   template <typename BlockInputIterator>
   void append_blocks(BlockInputIterator first, BlockInputIterator last)
   {
      if (bits_per_block % bits_per_symbol_ != 0 && first != last)
      {
         throw std::invalid_argument("Full storage blocks do not align with this alphabet width.");
      }
      for (; first != last; ++first)
      {
         append_block(static_cast<block_type>(*first));
      }
   }

   // Appends raw storage bits. The resulting size must preserve the invariant.
   void append_bits(const boost::dynamic_bitset<> &bits)
   {
      if ((bit_size() + bits.size()) % bits_per_symbol_ != 0)
      {
         throw std::invalid_argument("Appending bits would violate the dynamic_alphabetset storage invariant.");
      }

      const auto original_bit_size = bit_size();
      bits_.resize(original_bit_size + bits.size());
      for (std::size_t i = 0; i < bits.size(); ++i)
      {
         bits_[original_bit_size + i] = bits[i];
      }
   }

   // Exposes the packed storage.
   [[nodiscard]] const boost::dynamic_bitset<> &raw_bits() const noexcept
   {
      return bits_;
   }

   // Exposes mutable packed storage. The caller is responsible for preserving
   // the storage-size invariant.
   [[nodiscard]] boost::dynamic_bitset<> &raw_bits() noexcept
   {
      return bits_;
   }

   // True iff every set storage bit in this word is also set in other.
   [[nodiscard]] bool is_subset_of(const dynamic_alphabetset &other) const
   {
      ensure_same_storage_shape(other);
      return bits_.is_subset_of(other.bits_);
   }

   // True iff this word is a strict storage-bit subset of other.
   [[nodiscard]] bool is_proper_subset_of(const dynamic_alphabetset &other) const
   {
      ensure_same_storage_shape(other);
      return bits_.is_proper_subset_of(other.bits_);
   }

   // True iff the two words share at least one set storage bit.
   [[nodiscard]] bool intersects(const dynamic_alphabetset &other) const
   {
      ensure_same_storage_shape(other);
      return bits_.intersects(other.bits_);
   }

   // Exchanges contents and alphabet widths.
   void swap(dynamic_alphabetset &other)
   {
      using std::swap;
      swap(bits_per_symbol_, other.bits_per_symbol_);
      bits_.swap(other.bits_);
   }

   friend void swap(dynamic_alphabetset &lhs, dynamic_alphabetset &rhs)
   {
      lhs.swap(rhs);
   }

   // Equality includes both the word contents and the alphabet encoding width.
   friend bool operator==(const dynamic_alphabetset &lhs, const dynamic_alphabetset &rhs)
   {
      return lhs.bits_per_symbol_ == rhs.bits_per_symbol_ && lhs.bits_ == rhs.bits_;
   }

   friend bool operator!=(const dynamic_alphabetset &lhs, const dynamic_alphabetset &rhs)
   {
      return !(lhs == rhs);
   }

   // Lexicographic order by symbol value, then word length, then encoding width.
   friend bool operator<(const dynamic_alphabetset &lhs, const dynamic_alphabetset &rhs)
   {
      const auto prefix_size = std::min(lhs.size(), rhs.size());
      for (std::size_t i = 0; i < prefix_size; ++i)
      {
         const auto lhs_symbol = lhs.get_symbol(i);
         const auto rhs_symbol = rhs.get_symbol(i);
         if (lhs_symbol != rhs_symbol)
         {
            return lhs_symbol < rhs_symbol;
         }
      }
      if (lhs.size() != rhs.size())
      {
         return lhs.size() < rhs.size();
      }
      return lhs.bits_per_symbol_ < rhs.bits_per_symbol_;
   }

   friend bool operator>(const dynamic_alphabetset &lhs, const dynamic_alphabetset &rhs)
   {
      return rhs < lhs;
   }

   friend bool operator<=(const dynamic_alphabetset &lhs, const dynamic_alphabetset &rhs)
   {
      return !(rhs < lhs);
   }

   friend bool operator>=(const dynamic_alphabetset &lhs, const dynamic_alphabetset &rhs)
   {
      return !(lhs < rhs);
   }

private:
   // Inside each symbol block, offset 0 is the least-significant bit.
   std::size_t bits_per_symbol_ = default_bits_per_symbol;
   boost::dynamic_bitset<> bits_;

   void validate_storage_size() const
   {
      if (bits_.size() % bits_per_symbol_ != 0)
      {
         throw std::invalid_argument("dynamic_alphabetset storage size must be divisible by bits_per_symbol.");
      }
   }

   void validate_symbol(symbol_type symbol) const
   {
      if (symbol > max_symbol())
      {
         throw std::invalid_argument("dynamic_alphabetset symbol is outside the configured alphabet.");
      }
   }

   void ensure_symbol_index(std::size_t index) const
   {
      if (index >= size())
      {
         throw std::out_of_range("dynamic_alphabetset index is out of range.");
      }
   }

   [[nodiscard]] symbol_type get_symbol(std::size_t index) const
   {
      const auto base = index * bits_per_symbol_;
      symbol_type symbol = 0;
      for (std::size_t offset = 0; offset < bits_per_symbol_; ++offset)
      {
         if (bits_[base + offset])
         {
            symbol |= symbol_type{1} << offset;
         }
      }
      return symbol;
   }

   void set_symbol(std::size_t index, symbol_type symbol)
   {
      validate_symbol(symbol);
      const auto base = index * bits_per_symbol_;
      for (std::size_t offset = 0; offset < bits_per_symbol_; ++offset)
      {
         bits_[base + offset] = (symbol & (symbol_type{1} << offset)) != 0u;
      }
   }

   symbol_type parse_symbol(char symbol) const
   {
      const auto value = single_character_symbol_value(symbol);
      validate_symbol(value);
      return value;
   }

   static char symbol_to_char(symbol_type symbol)
   {
      if (symbol < 10u)
      {
         return static_cast<char>('0' + symbol);
      }
      if (symbol < 36u)
      {
         return static_cast<char>('A' + (symbol - 10u));
      }
      throw std::invalid_argument("dynamic_alphabetset symbol has no single-character representation.");
   }

   void ensure_same_alphabet(const dynamic_alphabetset &other) const
   {
      if (bits_per_symbol_ != other.bits_per_symbol_)
      {
         throw std::invalid_argument("Cannot combine dynamic_alphabetset values with different alphabet sizes.");
      }
   }

   void ensure_same_storage_shape(const dynamic_alphabetset &other) const
   {
      ensure_same_alphabet(other);
      if (bit_size() != other.bit_size())
      {
         throw std::invalid_argument("dynamic_alphabetset storage operations require equal sizes.");
      }
   }

   static std::size_t checked_bits_per_symbol(std::size_t bits_per_symbol)
   {
      if (bits_per_symbol == 0 || bits_per_symbol > max_bits_per_symbol)
      {
         throw std::invalid_argument("dynamic_alphabetset bits_per_symbol must be in the range [1, 64].");
      }
      return bits_per_symbol;
   }

   static symbol_type max_symbol_for(std::size_t bits_per_symbol) noexcept
   {
      return bits_per_symbol == max_bits_per_symbol
                 ? std::numeric_limits<symbol_type>::max()
                 : (symbol_type{1} << bits_per_symbol) - 1u;
   }

   static std::size_t checked_storage_bit_count(std::size_t symbol_count, std::size_t bits_per_symbol)
   {
      if (symbol_count > std::numeric_limits<std::size_t>::max() / bits_per_symbol)
      {
         throw std::length_error("dynamic_alphabetset storage size overflow.");
      }
      return symbol_count * bits_per_symbol;
   }

   static std::size_t bits_for_power_of_two_alphabet(symbol_type alphabet_size)
   {
      if (alphabet_size < 2u || (alphabet_size & (alphabet_size - 1u)) != 0u)
      {
         throw std::invalid_argument("dynamic_alphabetset alphabet size must be a power of two greater than one.");
      }

      std::size_t bits = 0;
      for (auto value = alphabet_size - 1u; value != 0u; value >>= 1u)
      {
         ++bits;
      }
      return checked_bits_per_symbol(bits);
   }

   static symbol_type single_character_symbol_value(char symbol)
   {
      if (symbol >= '0' && symbol <= '9')
      {
         return static_cast<symbol_type>(symbol - '0');
      }
      if (symbol >= 'A' && symbol <= 'Z')
      {
         return static_cast<symbol_type>(10u + symbol - 'A');
      }
      if (symbol >= 'a' && symbol <= 'z')
      {
         return static_cast<symbol_type>(10u + symbol - 'a');
      }
      throw std::invalid_argument("dynamic_alphabetset expects symbols encoded as 0-9 or A-Z.");
   }
};

inline std::ostream &operator<<(std::ostream &out, const dynamic_alphabetset &value)
{
   if (value.can_use_compact_symbol_string())
   {
      out << value.to_symbol_string('_');
   }
   else
   {
      out << value.to_delimited_symbol_string(',', "_");
   }
   return out;
}

inline void to_string(const dynamic_alphabetset &value, std::string &out)
{
   out = value.can_use_compact_symbol_string()
             ? value.to_symbol_string()
             : value.to_delimited_symbol_string();
}

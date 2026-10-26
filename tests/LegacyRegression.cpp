#include "BackToFirstDFA.h"
#include "ProductDFAExperiment.h"
#include "RegPDFA.h"
#include "VectorEnumerator.h"
#include <iostream>
#include <set>
#include <stdexcept>

namespace {
void require(bool condition, const char* message)
{
   if (!condition)
      throw std::runtime_error(message);
}

boost::dynamic_bitset<> word(const std::string& input)
{
   boost::dynamic_bitset<> result;
   for (char c : input)
      result.push_back(c == '1');
   return result;
}

void test_enumerator()
{
   for (unsigned n = 0; n <= 5; ++n)
   {
      std::vector<unsigned> values(n);
      std::string text(n, '0');
      boost::dynamic_bitset<> bits(n);
      unsigned count = 1;
      while (VectorEnumerator::next(values))
      {
         require(VectorEnumerator::next(text), "string enumeration ended early");
         require(VectorEnumerator::next(bits), "bitset enumeration ended early");
         for (unsigned i = 0; i < n; ++i)
         {
            require(values[i] == static_cast<unsigned>(text[i] - '0'), "string enumeration differs");
            require(values[i] == static_cast<unsigned>(bits[i]), "bitset enumeration differs");
         }
         ++count;
      }
      require(!VectorEnumerator::next(text), "string enumeration did not terminate");
      require(!VectorEnumerator::next(bits), "bitset enumeration did not terminate");
      require(count == (1U << n), "incorrect number of binary vectors");

      BackToFirstDFA family(n);
      count = 0;
      while (!family.is_end)
      {
         ++count;
         family.next();
      }
      require(count == (1U << n), "incorrect number of legacy masks");
      family.next();
      require(family.is_end, "next after end reopened enumeration");
      family.reset_enumeration();
      require(!family.is_end && family.labels.none(), "reset failed");
   }
}

void test_reset_sink_and_static_mask()
{
   BackToFirstDFA reset(2);
   require(reset.get_next_state(0, word("00000")) == 2, "sink is not absorbing");
   require(reset.get_next_state(2, false) == 2 && reset.get_next_state(2, true) == 2,
      "sink ports must coincide");
   require(reset.get_next_state(1, word("0")) == 2, "word ignored initial state");

   reset.setW(boost::dynamic_bitset<>(2, 1UL));
   // At root, mask=1 swaps input 0 to the reset port, every time.
   require(reset.get_next_state(0, word("000000")) == 0, "mask changed during revisit");
   require(reset.get_next_state(0, word("1111")) == 0, "static masks not applied on revisits");

   ProductPDFA product(std::make_unique<BackToFirstDFA>(2));
   auto state = product.evaluate(word("000000"));
   require(state.labels.size() == 4, "sink introduced duplicate mask coordinates");
   for (unsigned mask = 0; mask < 4; ++mask)
   {
      reset.setW(boost::dynamic_bitset<>(2, mask));
      require(state.labels[mask] == reset.get_next_state(0, word("000000")),
         "product and single realization disagree");
   }
}

void test_witness_retention()
{
   ProductDFAExperiment experiment;
   for (unsigned n = 2; n <= 5; ++n)
   {
      experiment.incrementn();
      std::set<boost::dynamic_bitset<>> all_words;
      for (const auto& [state, words] : experiment.table)
      {
         require(state.labels.size() == (std::size_t{1} << experiment.m),
            "wrong product dimension after graph growth");
         for (const auto& w : words)
         {
            require(w.size() == n, "retained word has wrong length");
            require(all_words.insert(w).second, "retained duplicate word");
         }
      }
      require(all_words.size() == (std::size_t{1} << n),
         "merged words lost during graph growth");
   }
}

void test_shared_prefixes()
{
   RegPDFA graph("000-_,001-_,01-_,1-_");
   require(graph.reduce(word("00")) == word("00"), "shared prefix changed");
   require(graph.reduce(word("001")) == word(""), "shared prefix not consumed");
   require(graph.reduce(word("000")) == word(""), "first transition changed");
   require(graph.reduce(word("01")) == word(""), "shared root prefix not consumed");
   require(graph.reduce(word("001001")) == word(""), "repeated reduction differs");
}
}

int main()
{
   try
   {
      test_enumerator();
      test_reset_sink_and_static_mask();
      test_witness_retention();
      test_shared_prefixes();
      std::cout << "Legacy regression tests passed\n";
      return 0;
   }
   catch (const std::exception& error)
   {
      std::cerr << "Legacy regression failure: " << error.what() << '\n';
      return 1;
   }
}

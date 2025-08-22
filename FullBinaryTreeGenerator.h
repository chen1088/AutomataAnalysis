#pragma once

#include <generator>
#include <vector>
#include <algorithm>
#include <bit>
#include <iostream>
#include <boost/dynamic_bitset/dynamic_bitset.hpp>

// Generate all full binary tree leaf-sets with exactly n leaves.
// Each leaf is represented as a boost::dynamic_bitset<> where bit 0 is the
// first step from the root (0 = left, 1 = right). For example, the path
// left-left-right is represented as the bitset "001" (bit 0 = 0, bit1 = 0, bit2 = 1).
// The generator yields a vector of leaf bitsets for each full binary tree.

class FullBinaryTreeGenerator
{
public:
    // Returns a generator producing vector<dynamic_bitset<>> sets of leaves.
    // The leaves in the vector are sorted lexicographically (by length then bits)
    // to give deterministic ordering.
    static std::generator<std::vector<boost::dynamic_bitset<>>> generate(unsigned int n)
    {
        if (n == 0) co_return; // no trees with zero leaves

        // Base case: single leaf at the root (empty path)
        if (n == 1)
        {
            std::vector<boost::dynamic_bitset<>> v;
            v.emplace_back(0); // empty bitset (size 0) represents root-leaf
            co_yield v;
            co_return;
        }

        // For n >= 2, a full binary tree splits leaves into left (k) and right (n-k) where 1<=k<=n-1
        for (unsigned k = 1; k <= n - 1; ++k)
        {
            // recursively generate left subtrees with k leaves and right with n-k leaves
            for (auto left : generate(k))
            {
                for (auto right : generate(n - k))
                {
                    // prefix 0 to every left leaf, prefix 1 to every right leaf
                    std::vector<boost::dynamic_bitset<>> leaves;
                    leaves.reserve(left.size() + right.size());
                    for (auto &bs : left)
                    {
                        boost::dynamic_bitset<> nb(bs.size() + 1);
                        // set bit 0 = 0 (left)
                        for (size_t i = 0; i < bs.size(); ++i) nb[i + 1] = bs[i];
                        leaves.push_back(std::move(nb));
                    }
                    for (auto &bs : right)
                    {
                        boost::dynamic_bitset<> nb(bs.size() + 1);
                        nb[0] = 1; // right
                        for (size_t i = 0; i < bs.size(); ++i) nb[i + 1] = bs[i];
                        leaves.push_back(std::move(nb));
                    }
                    co_yield leaves;
                }
            }
        }
    }
    static void test()
    {
        // Example usage: generate trees with 3 leaves
        for (auto leaves : generate(4))
        {
            std::cout << "Leaves: ";
            for (const auto &bs : leaves)
            {
                std::cout << bs << " ";
            }
            std::cout << std::endl;
        }
    }
};

#pragma once
#include "TwoRegularDigraph.h"
#include <array>
#include <functional>
#include <string>
#include <vector>

// A finite seed, unlike the legacy reset graph (which adds an extra sink).
class Family1Graph : public TwoRegularDigraph
{
public:
    using Row = std::array<unsigned int, 2>;
    std::vector<Row> ports;
    explicit Family1Graph(std::vector<Row> table);
    unsigned int get_next_v(unsigned int state, bool port) override;
    void set_next_v(unsigned int state, bool port, unsigned int value) override;
    void set_e0(std::vector<unsigned int> edges) override;
    void set_e1(std::vector<unsigned int> edges) override;
    void next() override { is_end = true; }
    bool accessible() const;
    std::string key() const;
};

class GraphBasedPDFAEnumerator
{
public:
    // Exact backend supports m <= 6 (at most 64 static masks).
    explicit GraphBasedPDFAEnumerator(unsigned int states);
    // Lexicographic order of canonical transition tables. false stops traversal.
    bool enumerate(const std::function<bool(const Family1Graph&)>& visit) const;
    static Family1Graph canonical(const Family1Graph& graph);
    static bool is_canonical(const Family1Graph& graph);
private:
    unsigned int states_;
};


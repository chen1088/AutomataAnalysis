#include "Family1SatSolver.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <utility>
#include <vector>

namespace {
using family1::SatSolver;
using family1::SolveResult;
using Formula = std::vector<std::vector<int>>;

void require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
}

bool satisfies(const Formula& formula, unsigned int assignment)
{
    for (const auto& clause : formula) {
        bool satisfied = false;
        for (int literal : clause) {
            auto variable = static_cast<unsigned int>(literal < 0 ? -literal : literal);
            bool value = ((assignment >> (variable - 1)) & 1U) != 0;
            satisfied |= literal > 0 ? value : !value;
        }
        if (!satisfied) return false;
    }
    return true;
}

void test_basic_and_incremental()
{
    SatSolver empty;
    require(empty.solve() == SolveResult::sat, "empty formula must be SAT");
    empty.add_clause({});
    require(empty.solve() == SolveResult::unsat, "empty clause must be UNSAT");

    SatSolver solver;
    auto x = solver.new_variable(), y = solver.new_variable();
    require(x == 1 && y == 2 && solver.variable_count() == 2, "variable allocation mismatch");
    solver.add_clause({x, y});
    require(solver.solve({-x, -y}) == SolveResult::unsat, "inconsistent assumptions accepted");
    require(solver.solve() == SolveResult::sat, "assumptions persisted into later call");
    require(solver.value(x) || solver.value(y), "SAT model does not satisfy clause");
    solver.add_clause({-x});
    bool threw = false;
    try { (void)solver.value(x); } catch (const std::logic_error&) { threw = true; }
    require(threw, "formula mutation failed to invalidate model");
    require(solver.solve() == SolveResult::sat && !solver.value(x) && solver.value(y), "incremental model mismatch");
    solver.add_clause({-y});
    require(solver.solve() == SolveResult::unsat, "incremental contradiction missed");
    require(solver.clause_count() == 3, "incorrect clause count");
    require(solver.reason_unknown().empty(), "stale UNKNOWN reason after UNSAT");

    SatSolver movable;
    auto variable = movable.new_variable();
    movable.add_clause({variable});
    require(movable.solve() == SolveResult::sat, "move setup failed");
    SatSolver moved(std::move(movable));
    require(moved.value(variable), "move lost SAT model");
}

void test_against_exhaustive_truth_tables()
{
    std::uint32_t random = 0x1435BA19U;
    auto next = [&] {
        random ^= random << 13; random ^= random >> 17; random ^= random << 5;
        return random;
    };
    for (unsigned int instance = 0; instance < 100; ++instance) {
        const unsigned int variables = 1 + next() % 8;
        SatSolver solver;
        for (unsigned int i = 0; i < variables; ++i) solver.new_variable();
        Formula formula;
        for (unsigned int c = 0, clauses = next() % 40; c < clauses; ++c) {
            std::vector<int> clause;
            for (unsigned int j = 0, width = 1 + next() % 4; j < width; ++j) {
                int variable = 1 + next() % variables;
                clause.push_back(next() & 1U ? variable : -variable);
            }
            solver.add_clause(clause); formula.push_back(std::move(clause));
        }
        bool expected = false;
        for (unsigned int assignment = 0; assignment < (1U << variables); ++assignment)
            expected |= satisfies(formula, assignment);
        auto actual = solver.solve({}, 5000);
        require(actual != SolveResult::unknown, "small truth-table test unexpectedly timed out");
        require((actual == SolveResult::sat) == expected, "SAT result disagrees with exhaustive truth table");
        if (actual == SolveResult::sat) {
            unsigned int assignment = 0;
            for (unsigned int variable = 1; variable <= variables; ++variable)
                if (solver.value(variable)) assignment |= 1U << (variable - 1);
            require(satisfies(formula, assignment), "SAT model disagrees with original formula");
        }
    }
}

void test_timeout()
{
    // Fourteen pigeons cannot fit into thirteen holes. A tiny timeout usually
    // produces UNKNOWN; if preprocessing proves UNSAT, that is valid as well.
    SatSolver solver;
    std::vector<std::vector<int>> variable(14, std::vector<int>(13));
    for (auto& row : variable) for (auto& value : row) value = solver.new_variable();
    for (const auto& row : variable) solver.add_clause(row);
    for (unsigned int hole = 0; hole < 13; ++hole)
        for (unsigned int first = 0; first < 14; ++first)
            for (unsigned int second = first + 1; second < 14; ++second)
                solver.add_clause({-variable[first][hole], -variable[second][hole]});
    const auto result = solver.solve({}, 1);
    require(result != SolveResult::sat, "pigeonhole contradiction reported SAT");
    if (result == SolveResult::unknown)
        require(!solver.reason_unknown().empty(), "timeout lost UNKNOWN reason");
}
}

int main()
{
    try {
        test_basic_and_incremental();
        test_against_exhaustive_truth_tables();
        test_timeout();
        std::cout << "SAT wrapper regression checks passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "SAT wrapper regression failure: " << error.what() << '\n';
        return 1;
    }
}

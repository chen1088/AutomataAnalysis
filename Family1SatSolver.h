#pragma once
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace family1 {

enum class SolveResult { sat, unsat, unknown };

// Incremental Boolean CNF solver backed by Z3. Literals use the conventional
// signed, one-based integer representation. Variables must first be allocated
// with new_variable(). Instances are independent and are not shared by threads.
class SatSolver {
public:
    explicit SatSolver(bool retain_clauses = false);
    ~SatSolver();
    SatSolver(SatSolver&&) noexcept;
    SatSolver& operator=(SatSolver&&) noexcept;
    SatSolver(const SatSolver&) = delete;
    SatSolver& operator=(const SatSolver&) = delete;

    int new_variable();
    void add_clause(const std::vector<int>& literals);
    // The timeout is per call, in milliseconds; zero means no time limit.
    // Assumptions apply only to this call. A timeout/cancellation is UNKNOWN,
    // never UNSAT. The model is invalidated by every formula mutation or solve.
    SolveResult solve(const std::vector<int>& assumptions = {}, std::uint64_t timeout_ms = 0);
    bool value(int variable) const;
    const std::string& reason_unknown() const;
    unsigned int variable_count() const;
    std::uint64_t clause_count() const;
    std::string dimacs() const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}

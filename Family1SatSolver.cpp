#include "Family1SatSolver.h"
#include <z3++.h>
#include <algorithm>
#include <limits>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace family1 {

struct SatSolver::Impl {
    z3::context context;
    z3::solver solver;
    std::vector<z3::expr> variables;
    std::optional<z3::model> model;
    std::string unknown_reason;
    std::uint64_t clauses = 0;
    bool retain_clauses;
    std::vector<std::vector<int>> clause_log;

    explicit Impl(bool retain) : solver(context), retain_clauses(retain) {
        z3::params parameters(context);
        parameters.set("random_seed", 0U);
        solver.set(parameters);
    }

    z3::expr literal(int signed_variable) const {
        if (signed_variable == 0 || signed_variable == std::numeric_limits<int>::min())
            throw std::invalid_argument("SAT literal must be a nonzero allocated variable");
        const auto variable = static_cast<unsigned int>(signed_variable < 0 ? -signed_variable : signed_variable);
        if (variable > variables.size()) throw std::out_of_range("SAT literal uses an unallocated variable");
        const auto& expression = variables[variable - 1];
        return signed_variable < 0 ? !expression : expression;
    }
};

SatSolver::SatSolver(bool retain_clauses) : impl_(std::make_unique<Impl>(retain_clauses)) {}
SatSolver::~SatSolver() = default;
SatSolver::SatSolver(SatSolver&&) noexcept = default;
SatSolver& SatSolver::operator=(SatSolver&&) noexcept = default;

int SatSolver::new_variable()
{
    auto& state = *impl_;
    if (state.variables.size() >= static_cast<std::size_t>(std::numeric_limits<int>::max()))
        throw std::length_error("SAT variable limit reached");
    state.model.reset();
    const auto variable = static_cast<int>(state.variables.size() + 1);
    const auto name = "v" + std::to_string(variable);
    state.variables.push_back(state.context.bool_const(name.c_str()));
    return variable;
}

void SatSolver::add_clause(const std::vector<int>& literals)
{
    auto& state = *impl_;
    state.model.reset();
    z3::expr_vector clause(state.context);
    for (auto literal : literals) clause.push_back(state.literal(literal));
    state.solver.add(clause.empty() ? state.context.bool_val(false) : z3::mk_or(clause));
    if (state.retain_clauses) state.clause_log.push_back(literals);
    ++state.clauses;
}

SolveResult SatSolver::solve(const std::vector<int>& assumptions, std::uint64_t timeout_ms)
{
    auto& state = *impl_;
    state.model.reset();
    state.unknown_reason.clear();
    z3::params parameters(state.context);
    parameters.set("timeout", static_cast<unsigned int>(std::min<std::uint64_t>(timeout_ms, std::numeric_limits<unsigned int>::max())));
    state.solver.set(parameters);
    z3::expr_vector expressions(state.context);
    for (auto literal : assumptions) expressions.push_back(state.literal(literal));
    try {
        const auto result = state.solver.check(expressions);
        if (result == z3::sat) {
            state.model.emplace(state.solver.get_model());
            return SolveResult::sat;
        }
        if (result == z3::unsat) return SolveResult::unsat;
        state.unknown_reason = state.solver.reason_unknown();
        return SolveResult::unknown;
    } catch (const z3::exception& error) {
        // Resource/cancellation exceptions must never become UNSAT claims.
        // Ordinary API errors remain visible to the caller.
        const std::string message = error.msg();
        if (message.find("canceled") == std::string::npos && message.find("cancelled") == std::string::npos
            && message.find("timeout") == std::string::npos && message.find("out of memory") == std::string::npos)
            throw;
        state.unknown_reason = message;
        return SolveResult::unknown;
    }
}

bool SatSolver::value(int variable) const
{
    const auto& state = *impl_;
    if (variable <= 0 || static_cast<std::size_t>(variable) > state.variables.size())
        throw std::out_of_range("SAT model variable outside allocated range");
    if (!state.model) throw std::logic_error("SAT model requested without a SAT result");
    return state.model->eval(state.variables[variable - 1], true).is_true();
}

const std::string& SatSolver::reason_unknown() const { return impl_->unknown_reason; }
unsigned int SatSolver::variable_count() const { return static_cast<unsigned int>(impl_->variables.size()); }
std::uint64_t SatSolver::clause_count() const { return impl_->clauses; }
std::string SatSolver::dimacs() const
{
    const auto& state = *impl_;
    if (!state.retain_clauses) throw std::logic_error("DIMACS retention was not enabled");
    std::ostringstream out;
    out << "p cnf " << state.variables.size() << ' ' << state.clause_log.size() << '\n';
    for (const auto& clause : state.clause_log) {
        for (int literal : clause) out << literal << ' ';
        out << "0\n";
    }
    return out.str();
}

}

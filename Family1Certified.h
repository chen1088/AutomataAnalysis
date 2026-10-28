#pragma once
#include <array>
#include <chrono>
#include <csignal>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace family1::certified {

struct Seed {
    std::string name;
    unsigned root = 0;
    std::vector<std::array<unsigned, 2>> ports;
};
struct Observer {
    std::size_t seed = 0;
    std::uint64_t mask = 0;
    bool operator==(const Observer&) const = default;
    bool operator<(const Observer& other) const;
};
struct State {
    // Interleaved left/right endpoints, in selected-observer order.
    std::vector<unsigned> endpoints;
    bool distinct = false;
    bool operator==(const State&) const = default;
    bool operator<(const State& other) const;
};
struct Limits {
    std::uint64_t max_states = 100000;
    std::uint64_t max_work = 1000000;
    std::uint64_t max_verifier_steps = 10000000;
    std::uint64_t timeout_ms = 10000; // zero disables clock limit
    std::uint64_t max_refinements = 1024;
    const volatile std::sig_atomic_t* interrupted = nullptr;
};
class Budget {
public:
    explicit Budget(Limits limits = {});
    Limits limits;
    std::uint64_t states = 0, work = 0, verifier_steps = 0, refinements = 0;
    std::string reason;
    bool check();
    bool add_state();
    bool add_work();
    bool add_verifier_step();
    double seconds() const;
private:
    std::chrono::steady_clock::time_point start_;
};
struct Verification {
    std::string status = "unresolved"; // verified, separated, unresolved
    std::optional<Observer> separator;
    std::uint64_t observers_checked = 0;
    std::string reason;
};
class Family {
public:
    explicit Family(std::vector<Seed> seeds);
    const std::vector<Seed>& seeds() const { return seeds_; }
    std::uint64_t observer_count() const;
    void validate_observer(Observer observer) const;
    void validate_selection(const std::vector<Observer>& selected) const;
    void validate_state(const std::vector<Observer>& selected, const State& state) const;
    State initial(const std::vector<Observer>& selected, bool distinct = false) const;
    State step(const std::vector<Observer>& selected, const State& state,
               unsigned left, unsigned right) const;
    Verification verify(const std::string& left, const std::string& right,
                        Budget& budget) const;
private:
    std::vector<Seed> seeds_;
};
bool goal(const State& state);

struct QueryResult {
    std::string status = "unresolved"; // witness, excluded, unresolved
    std::string reason;
    std::array<std::string, 2> witness{};
    // On exclusion: layers[0] contains initial and every successor from
    // layers[d] appears in layers[d+1]; no final state is a goal.
    std::vector<std::vector<State>> layers;
};
QueryResult decide(const Family& family, const std::vector<Observer>& selected,
                   unsigned horizon, Budget& budget,
                   const std::optional<State>& initial = std::nullopt);
struct RefinementStep {
    std::array<std::string, 2> candidate;
    Observer separator;
};
struct RefinementResult {
    std::string status = "unresolved"; // witness, excluded, unresolved
    std::string reason;
    std::vector<Observer> selected;
    std::vector<RefinementStep> refinements;
    QueryResult query;
    Verification verification;
};
RefinementResult refine(const Family& family, unsigned horizon, Budget& budget,
                        std::vector<Observer> selected = {});

} // namespace family1::certified

// Independent complete-mask single-layer checker. No production headers.
// DFS uses one-hot endpoint sets and stores only hashes/word indices. Hash
// matches are replayed against COMPLETE vectors. Injectivity at depth d also
// proves injectivity at all shorter depths: a collision extends by any suffix.
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;
using Profile = std::array<std::array<std::uint64_t, 2>, 7>;
using Table = std::array<std::array<unsigned int, 2>, 7>;
struct Entry { std::uint64_t hash; std::uint32_t word; std::uint32_t reserved = 0; };
struct Seen { Profile p; std::uint64_t index; };
// Increment only this task-local counter in the hot loop. Publishing once on
// scope exit also retains partial progress on exceptions without false sharing
// between adjacent task slots.
struct CounterPublisher {
    std::uint64_t& destination;
    std::uint64_t value = 0;
    ~CounterPublisher() { destination = value; }
};
static_assert(sizeof(Entry) == 16);
std::string json_string(const std::string& value) {
    constexpr char digits[] = "0123456789abcdef";
    std::string result = "\"";
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') { result += '\\'; result += c; }
        else if (c < 32) { result += "\\u00"; result += digits[c >> 4]; result += digits[c & 15]; }
        else result += c;
    }
    return result + '"';
}
std::uint64_t number(const std::string& value) {
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("expected an unsigned integer");
    return std::stoull(value);
}
std::uint64_t reverse(std::uint64_t x) {
    x = ((x >> 1) & 0x5555555555555555ULL) | ((x & 0x5555555555555555ULL) << 1);
    x = ((x >> 2) & 0x3333333333333333ULL) | ((x & 0x3333333333333333ULL) << 2);
    x = ((x >> 4) & 0x0f0f0f0f0f0f0f0fULL) | ((x & 0x0f0f0f0f0f0f0f0fULL) << 4);
    x = ((x >> 8) & 0x00ff00ff00ff00ffULL) | ((x & 0x00ff00ff00ff00ffULL) << 8);
    x = ((x >> 16) & 0x0000ffff0000ffffULL) | ((x & 0x0000ffff0000ffffULL) << 16);
    return (x >> 32) | (x << 32);
}
const std::uint64_t patterns[] = {0xaaaaaaaaaaaaaaaaULL, 0xccccccccccccccccULL,
    0xf0f0f0f0f0f0f0f0ULL, 0xff00ff00ff00ff00ULL,
    0xffff0000ffff0000ULL, 0xffffffff00000000ULL};
Profile step(const Table& t, const Profile& p, bool input) {
    Profile out{};
    for (unsigned int s = 0; s < 7; ++s) {
        for (unsigned int b = 0; b < 2; ++b) {
            const auto sigma = s < 6 ? patterns[s] : b ? ~std::uint64_t{0} : 0;
            const auto selected = input ? ~sigma : sigma;
            out[t[s][0]][b] |= p[s][b] & ~selected;
            out[t[s][1]][b] |= p[s][b] & selected;
        }
    }
    return out;
}
std::uint64_t hash(const Profile& p, bool complement) {
    std::uint64_t h = 0xcbf29ce484222325ULL;
    for (const auto& row : p) {
        for (unsigned int b = 0; b < 2; ++b) {
            auto x = complement ? reverse(row[1 - b]) : row[b];
            x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL;
            x ^= x >> 27; x *= 0x94d049bb133111ebULL;
            h ^= x ^ (x >> 31); h *= 0x100000001b3ULL;
        }
    }
    return h;
}
bool symmetric(const Profile& p) {
    return std::all_of(p.begin(), p.end(), [](const auto& row) { return row[0] == reverse(row[1]); });
}
std::string word(std::uint64_t value, unsigned int depth) {
    std::string result(depth, '0');
    for (unsigned int i = 0; i < depth; ++i) { result[depth - 1 - i] += value & 1; value >>= 1; }
    return result;
}
std::string complement(std::string w) { for (auto& c : w) c = c == '0' ? '1' : '0'; return w; }
std::array<unsigned char, 128> scalar(const Table& t, const std::string& w) {
    std::array<unsigned char, 128> out{};
    for (unsigned int mask = 0; mask < 128; ++mask)
        for (char c : w) out[mask] = static_cast<unsigned char>(t[out[mask]][(c - '0') ^ ((mask >> out[mask]) & 1)]);
    return out;
}
template<class Check>
void radix_inplace(std::uint64_t* a, std::uint64_t begin, std::uint64_t end,
    unsigned int shift, const Check& check) {
    check();
    if (end - begin < 64) { std::sort(a + begin, a + end); return; }
    std::array<std::uint64_t, 256> count{}, start{}, next{};
    for (auto i = begin; i < end; ++i) ++count[(a[i] >> shift) & 255];
    auto sum = begin;
    for (unsigned int b = 0; b < 256; ++b) { start[b] = next[b] = sum; sum += count[b]; }
    for (unsigned int b = 0; b < 256; ++b) {
        const auto stop = start[b] + count[b];
        while (next[b] < stop) {
            const auto target = (a[next[b]] >> shift) & 255;
            if (target == b) ++next[b];
            else std::swap(a[next[b]], a[next[target]++]);
        }
    }
    if (shift) for (unsigned int b = 0; b < 256; ++b)
        if (count[b] > 1) radix_inplace(a, start[b], start[b] + count[b], shift - 8, check);
}

// A worker exception cancels outstanding work, but every started worker is
// joined before the exception escapes or any shared array can be destroyed.
template<class Work>
void parallel_tasks(unsigned int tasks, unsigned int threads, Work&& work) {
    std::atomic<unsigned int> next{0};
    std::atomic<bool> canceled{false};
    std::exception_ptr error;
    std::mutex error_mutex;
    const auto worker = [&] {
        try {
            while (!canceled.load(std::memory_order_relaxed)) {
                const auto task = next.fetch_add(1, std::memory_order_relaxed);
                if (task >= tasks) return;
                work(task, canceled);
            }
        } catch (...) {
            {
                std::lock_guard<std::mutex> lock(error_mutex);
                if (!error) error = std::current_exception();
            }
            canceled.store(true, std::memory_order_relaxed);
        }
    };
    std::vector<std::thread> workers;
    workers.reserve(std::min(tasks, threads) - 1);
    try {
        for (unsigned int i = 1; i < std::min(tasks, threads); ++i)
            workers.emplace_back(worker);
    } catch (...) {
        canceled.store(true, std::memory_order_relaxed);
        for (auto& thread : workers) thread.join();
        throw;
    }
    worker();
    for (auto& thread : workers) thread.join();
    if (error) std::rethrow_exception(error);
}

template<class Check>
void radix_parallel(std::uint64_t* a, std::uint64_t count,
    unsigned int threads, const Check& check) {
    if (count < 64) { radix_inplace(a, 0, count, 56, check); return; }
    std::array<std::uint64_t, 256> sizes{}, start{}, next{};
    for (std::uint64_t i = 0; i < count; ++i) {
        if ((i & 1048575) == 0) check();
        ++sizes[a[i] >> 56];
    }
    std::uint64_t sum = 0;
    for (unsigned int b = 0; b < 256; ++b) {
        start[b] = next[b] = sum;
        sum += sizes[b];
    }
    for (unsigned int b = 0; b < 256; ++b) {
        check();
        const auto end = start[b] + sizes[b];
        while (next[b] < end) {
            if ((next[b] & 1048575) == 0) check();
            const auto target = a[next[b]] >> 56;
            if (target == b) ++next[b];
            else std::swap(a[next[b]], a[next[target]++]);
        }
    }
    // Distinct top-byte buckets occupy disjoint ranges. Each worker's recursive
    // American-flag count/start/next arrays live on its own stack.
    parallel_tasks(256, threads, [&](unsigned int b, const auto& canceled) {
        const auto worker_check = [&] {
            if (canceled.load(std::memory_order_relaxed)) throw std::runtime_error("parallel worker canceled");
            check();
        };
        if (sizes[b] > 1)
            radix_inplace(a, start[b], start[b] + sizes[b], 48, worker_check);
    });
    check();
}

template<class Check>
bool generate_parallel(const Table& t, unsigned int depth, bool forced_hash,
    unsigned int threads, std::uint64_t* hashes, const Check& check,
    std::uint64_t& generated, std::array<std::string, 2>& witness) {
    unsigned int prefix_bits = 0;
    while (prefix_bits < depth - 1 && (1U << prefix_bits) < threads * 4)
        ++prefix_bits;
    const auto tasks = 1U << prefix_bits;
    const auto remaining = depth - 1 - prefix_bits;
    std::vector<std::uint64_t> task_generated(tasks, 0);
    std::atomic<std::uint64_t> first_symmetric{std::numeric_limits<std::uint64_t>::max()};
    try {
        parallel_tasks(tasks, threads, [&](unsigned int prefix, const auto& canceled) {
            CounterPublisher local_generated{task_generated[prefix]};
            check();
            if ((std::uint64_t{prefix} << remaining) >= first_symmetric.load(std::memory_order_relaxed)) return;
            std::array<Profile, 34> stack{};
            stack[0][0] = {~std::uint64_t{0}, ~std::uint64_t{0}};
            stack[1] = step(t, stack[0], false);
            for (unsigned int bit = 0; bit < prefix_bits; ++bit)
                stack[bit + 2] = step(t, stack[bit + 1], (prefix >> (prefix_bits - 1 - bit)) & 1);
            const auto visit = [&](auto&& self, unsigned int level, std::uint64_t index) -> bool {
                if (level == depth) {
                    if ((local_generated.value & 65535) == 0) {
                        if (canceled.load(std::memory_order_relaxed)) return false;
                        check();
                    }
                    if (index >= first_symmetric.load(std::memory_order_relaxed)) return false;
                    const auto& p = stack[level];
                    if (symmetric(p)) {
                        auto old = first_symmetric.load(std::memory_order_relaxed);
                        while (index < old && !first_symmetric.compare_exchange_weak(old, index, std::memory_order_relaxed)) {}
                        return false;
                    }
                    hashes[index] = forced_hash ? 0 : std::min(hash(p, false), hash(p, true));
                    ++local_generated.value;
                    return true;
                }
                stack[level + 1] = step(t, stack[level], false);
                if (!self(self, level + 1, index * 2)) return false;
                stack[level + 1] = step(t, stack[level], true);
                return self(self, level + 1, index * 2 + 1);
            };
            visit(visit, prefix_bits + 1, prefix);
        });
    } catch (...) {
        for (const auto n : task_generated) generated += n;
        throw;
    }
    for (const auto n : task_generated) generated += n;
    check();
    const auto first = first_symmetric.load(std::memory_order_relaxed);
    if (first != std::numeric_limits<std::uint64_t>::max()) {
        witness = {word(first, depth), complement(word(first, depth))};
        return false;
    }
    return true;
}

template<class Fingerprint, class Check>
bool replay_parallel(const Table& t, unsigned int depth, unsigned int threads,
    std::uint64_t wanted, std::uint64_t expected_matches, Seen* seen,
    std::uint64_t capacity, const Fingerprint& fingerprint, const Check& check,
    std::uint64_t& matches, std::array<std::string, 2>& witness) {
    unsigned int prefix_bits = 0;
    while (prefix_bits < depth - 1 && (1U << prefix_bits) < threads * 4)
        ++prefix_bits;
    const auto tasks = 1U << prefix_bits;
    std::vector<std::uint64_t> task_replayed(tasks, 0);
    std::atomic<std::uint64_t> seen_count{0};
    parallel_tasks(tasks, threads, [&](unsigned int prefix, const auto& canceled) {
        CounterPublisher local_replayed{task_replayed[prefix]};
        check();
        std::array<Profile, 34> stack{};
        stack[0][0] = {~std::uint64_t{0}, ~std::uint64_t{0}};
        stack[1] = step(t, stack[0], false);
        for (unsigned int bit = 0; bit < prefix_bits; ++bit)
            stack[bit + 2] = step(t, stack[bit + 1], (prefix >> (prefix_bits - 1 - bit)) & 1);
        const auto visit = [&](auto&& self, unsigned int level, std::uint64_t index) -> bool {
            if (level == depth) {
                if ((local_replayed.value & 65535) == 0) {
                    if (canceled.load(std::memory_order_relaxed)) return false;
                    check();
                }
                ++local_replayed.value;
                const auto& p = stack[level];
                if (fingerprint(p) == wanted) {
                    const auto slot = seen_count.fetch_add(1, std::memory_order_relaxed);
                    if (slot >= capacity)
                        throw std::runtime_error("max-working-mib: complete-state hash replay exceeds payload budget");
                    seen[slot] = {p, index};
                }
                return true;
            }
            stack[level + 1] = step(t, stack[level], false);
            if (!self(self, level + 1, index * 2)) return false;
            stack[level + 1] = step(t, stack[level], true);
            return self(self, level + 1, index * 2 + 1);
        };
        visit(visit, prefix_bits + 1, prefix);
    });
    std::uint64_t replayed = 0;
    for (const auto n : task_replayed) replayed += n;
    const auto matched = seen_count.load(std::memory_order_relaxed);
    if (replayed != (1ULL << (depth - 1)) || matched != expected_matches)
        throw std::runtime_error("incomplete complete-state hash replay");
    // The workers have all joined. Sort only the small group of COMPLETE
    // profiles to restore increasing word order before checking every pair.
    std::sort(seen, seen + matched, [](const Seen& a, const Seen& b) { return a.index < b.index; });
    for (std::uint64_t i = 0; i < matched; ++i) {
        for (std::uint64_t j = 0; j < i; ++j) {
            if ((matches & 65535) == 0) check();
            ++matches;
            if (seen[i].p == seen[j].p) {
                witness = {word(seen[j].index, depth), word(seen[i].index, depth)};
                return false;
            }
            bool same = true;
            for (unsigned int s = 0; s < 7; ++s)
                if (seen[i].p[s][0] != reverse(seen[j].p[s][1]) ||
                    seen[i].p[s][1] != reverse(seen[j].p[s][0])) { same = false; break; }
            if (same) {
                witness = {word(seen[j].index, depth), complement(word(seen[i].index, depth))};
                return false;
            }
        }
    }
    check();
    return true;
}

template<class Check>
bool compact_check(const Table& t, unsigned int depth, std::uint64_t budget,
    bool forced_hash, unsigned int threads, const Check& check, std::uint64_t& generated,
    std::uint64_t& matches, std::array<std::string, 2>& witness) {
    const auto count = 1ULL << (depth - 1);
    if (count * sizeof(std::uint64_t) > budget)
        throw std::runtime_error("max-working-mib: compact hash array exceeds payload budget");
    std::unique_ptr<std::uint64_t[]> hashes(new std::uint64_t[count]);
    std::array<Profile, 34> stack{};
    stack[0][0] = {~std::uint64_t{0}, ~std::uint64_t{0}};
    stack[1] = step(t, stack[0], false);
    const auto visit = [&](auto&& self, unsigned int level, std::uint64_t index, auto&& leaf) -> bool {
        if (level == depth) return leaf(stack[level], index);
        stack[level + 1] = step(t, stack[level], false);
        if (!self(self, level + 1, index * 2, leaf)) return false;
        stack[level + 1] = step(t, stack[level], true);
        return self(self, level + 1, index * 2 + 1, leaf);
    };
    const auto fingerprint = [&](const Profile& p) { return forced_hash ? 0 : std::min(hash(p, false), hash(p, true)); };
    if (threads > 1) {
        if (!generate_parallel(t, depth, forced_hash, threads, hashes.get(), check, generated, witness)) return false;
    } else if (!visit(visit, 1, 0, [&](const Profile& p, std::uint64_t index) {
        if ((generated & 65535) == 0) check();
        if (symmetric(p)) { witness = {word(index, depth), complement(word(index, depth))}; return false; }
        hashes[generated++] = fingerprint(p);
        return true;
    })) return false;
    if (generated != count) throw std::runtime_error("incomplete representative generation");
    std::cout << "Generated " << generated << " compact complete-mask hashes.\n" << std::flush;
    if (threads > 1) radix_parallel(hashes.get(), count, threads, check);
    else radix_inplace(hashes.get(), 0, count, 56, check);
    // Hashes alone prove nothing when repeated. For EACH repeated value, rerun
    // the full DFS and compare complete 128-mask one-hot profiles, in both
    // complement orientations. Most repeated values contain a true collision;
    // even adversarial false hashes are replayed, subject to the stated budget.
    for (std::uint64_t begin = 0; begin < count;) {
        if ((begin & 65535) == 0) check();
        auto end = begin + 1;
        while (end < count && hashes[end] == hashes[begin]) ++end;
        if (end > begin + 1) {
            const auto capacity = std::min(end - begin,
                (budget - count * sizeof(std::uint64_t)) / sizeof(Seen));
            if (!capacity) throw std::runtime_error("max-working-mib: no complete-state hash replay space");
            std::unique_ptr<Seen[]> seen(new Seen[capacity]);
            if (threads > 1) {
                if (!replay_parallel(t, depth, threads, hashes[begin], end - begin,
                    seen.get(), capacity, fingerprint, check, matches, witness)) return false;
                begin = end;
                continue;
            }
            std::uint64_t seen_count = 0;
            std::uint64_t replayed = 0;
            const auto wanted = hashes[begin];
            const bool finished = visit(visit, 1, 0, [&](const Profile& p, std::uint64_t index) {
                if ((replayed++ & 65535) == 0) check();
                if (fingerprint(p) != wanted) return true;
                for (std::uint64_t i = 0; i < seen_count; ++i) {
                    const auto& old = seen[i];
                    ++matches;
                    if (p == old.p) { witness = {word(old.index, depth), word(index, depth)}; return false; }
                    bool same = true;
                    for (unsigned int s = 0; s < 7; ++s)
                        if (p[s][0] != reverse(old.p[s][1]) || p[s][1] != reverse(old.p[s][0])) { same = false; break; }
                    if (same) { witness = {word(old.index, depth), complement(word(index, depth))}; return false; }
                }
                if (seen_count == capacity)
                    throw std::runtime_error("max-working-mib: complete-state hash replay exceeds payload budget");
                seen[seen_count++] = {p, index};
                return true;
            });
            if (!finished) return false;
        }
        begin = end;
    }
    return true;
}
}

int main(int argc, char** argv) {
    unsigned int depth = 0, threads = 1;
    std::string key, path;
    std::uint64_t max_mib = 16384, timeout_ms = 0, generated = 0, hash_matches = 0;
    bool forced_hash = false, completed = false, compact = false;
    std::array<std::string, 2> witness{};
    std::string reason;
    const auto started = Clock::now();
    const auto seconds = [&] { return std::chrono::duration<double>(Clock::now() - started).count(); };
    try {
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--force-hash-collisions") { forced_hash = true; continue; }
            if (arg == "--compact") { compact = true; continue; }
            if (arg == "--help") {
                std::cout << "Family1LayerVerify --key 28DIGITS --depth N --out REPORT [--max-working-mib 16384 --timeout-ms 0 --compact --threads 1..64 (compact only)]\n";
                return 0;
            }
            if (++i == argc) throw std::runtime_error("missing option value");
            if (arg == "--key") key = argv[i];
            else if (arg == "--depth") {
                const auto n = number(argv[i]);
                if (n > 33) throw std::runtime_error("depth exceeds 33");
                depth = static_cast<unsigned int>(n);
            }
            else if (arg == "--out") path = argv[i];
            else if (arg == "--max-working-mib") {
                max_mib = number(argv[i]);
                if (!max_mib || max_mib > std::numeric_limits<std::uint64_t>::max() / 1048576)
                    throw std::runtime_error("memory budget out of range");
            }
            else if (arg == "--timeout-ms") timeout_ms = number(argv[i]);
            else if (arg == "--threads") {
                const auto n = number(argv[i]);
                if (!n || n > 64) throw std::runtime_error("threads must be between 1 and 64");
                threads = static_cast<unsigned int>(n);
            }
            else throw std::runtime_error("unknown option: " + arg);
        }
        if (key.size() != 28 || key.find_first_not_of("0123456") != std::string::npos || depth == 0 || depth > (compact ? 33U : 31U) || path.empty())
            throw std::runtime_error("requires seven-state two-digit key, depth1..31 (compact1..33) and output path");
        if (threads > 1 && !compact) throw std::runtime_error("threads greater than one require --compact");
        Table t{};
        for (unsigned int s = 0; s < 7; ++s) for (unsigned int x = 0; x < 2; ++x) {
            const auto i = 4 * s + 2 * x;
            if (key[i] != '0') throw std::runtime_error("invalid two-digit target");
            t[s][x] = key[i + 1] - '0';
        }
        const std::uint64_t count = 1ULL << (depth - 1);
        const auto check_time = [&] {
            if (timeout_ms && seconds() * 1000 >= timeout_ms) throw std::runtime_error("timeout");
        };
        if (compact) {
            completed = compact_check(t, depth, max_mib * 1048576ULL, forced_hash, threads,
                check_time, generated, hash_matches, witness);
        } else {
        if (count * sizeof(Entry) * 2 > max_mib * 1048576ULL)
            throw std::runtime_error("max-working-mib: two radix arrays exceed payload budget");
        std::unique_ptr<Entry[]> entries(new Entry[count]), scratch(new Entry[count]);
        std::array<Profile, 32> stack{};
        stack[0][0] = {~std::uint64_t{0}, ~std::uint64_t{0}};
        stack[1] = step(t, stack[0], false);
        const auto visit = [&](auto&& self, unsigned int level, std::uint32_t index) -> bool {
            if (level == depth) {
                if ((generated & 65535) == 0) check_time();
                const auto& p = stack[level];
                if (symmetric(p)) { witness = {word(index, depth), complement(word(index, depth))}; return false; }
                entries[generated++] = {forced_hash ? 0 : std::min(hash(p, false), hash(p, true)), index, 0};
                return true;
            }
            stack[level + 1] = step(t, stack[level], false);
            if (!self(self, level + 1, index * 2)) return false;
            stack[level + 1] = step(t, stack[level], true);
            return self(self, level + 1, index * 2 + 1);
        };
        if (visit(visit, 1, 0)) {
            std::cout << "Generated " << generated << " complete-mask representatives in " << seconds() << " s.\n" << std::flush;
            // Stable eight-pass byte radix sort. No profiles or hash equality
            // are treated as proof of a collision; buckets are replayed below.
            for (unsigned int pass = 0; pass < 8; ++pass) {
                check_time();
                std::array<std::uint64_t, 256> offsets{};
                for (std::uint64_t i = 0; i < count; ++i) ++offsets[(entries[i].hash >> (8 * pass)) & 255];
                std::uint64_t sum = 0;
                for (auto& n : offsets) { const auto old = n; n = sum; sum += old; }
                for (std::uint64_t i = 0; i < count; ++i) scratch[offsets[(entries[i].hash >> (8 * pass)) & 255]++] = entries[i];
                entries.swap(scratch);
            }
            for (std::uint64_t begin = 0; begin < count && witness[0].empty();) {
                if ((begin & 65535) == 0) check_time();
                auto end = begin + 1;
                while (end < count && entries[end].hash == entries[begin].hash) ++end;
                for (auto i = begin; i < end && witness[0].empty(); ++i) {
                    for (auto j = i + 1; j < end; ++j) {
                        ++hash_matches;
                        const auto a = word(entries[i].word, depth), b = word(entries[j].word, depth);
                        const auto pa = scalar(t, a), pb = scalar(t, b);
                        if (pa == pb) { witness = {a, b}; break; }
                        bool reversed_equal = true;
                        for (unsigned int mask = 0; mask < 128; ++mask)
                            if (pa[mask] != pb[mask ^ 127]) { reversed_equal = false; break; }
                        if (reversed_equal) { witness = {a, complement(b)}; break; }
                    }
                }
                begin = end;
            }
            completed = witness[0].empty();
        }
        }
        if (!witness[0].empty() && (witness[0] == witness[1] || scalar(t, witness[0]) != scalar(t, witness[1])))
            throw std::runtime_error("internal error: full scalar witness mismatch");
    } catch (const std::exception& error) { reason = error.what(); completed = false; witness = {}; }
    const auto status = !reason.empty() ? "incomplete" : completed ? "collision-free" : "collision-found";
    if (!path.empty()) {
        std::ofstream report(path);
        if (!report) { std::cerr << "cannot write report\n"; return 1; }
        report << "{\"method\":\"independent-one-hot-DFS-hash-radix-full-state-replay\",\"m\":7,\"key\":" << json_string(key)
            << ",\"depth\":" << depth << ",\"status\":\"" << status << "\",\"lower_bound\":" << (completed ? depth + 1 : 1)
            << ",\"upper_bound\":" << (!witness[0].empty() ? std::to_string(depth) : "null")
            << ",\"witness\":" << (witness[0].empty() ? "null" : "[\"" + witness[0] + "\",\"" + witness[1] + "\"]")
            << ",\"compact_storage\":" << (compact ? "true" : "false")
            << ",\"threads\":" << threads
            << ",\"generated_representatives\":" << generated << ",\"hash_matches_replayed\":" << hash_matches
            << ",\"seconds\":" << seconds() << ",\"reason\":" << json_string(reason) << "}\n";
    }
    std::cout << status << ": depth=" << depth << ", representatives=" << generated << ", seconds=" << seconds() << ", reason=" << reason << '\n';
    return reason.empty() ? 0 : 1;
}

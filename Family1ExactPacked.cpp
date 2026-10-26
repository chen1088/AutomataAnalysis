#include "Family1ExactPacked.h"
#include <algorithm>
#include <bit>
#include <chrono>
#include <cstring>
#include <limits>
#include <memory>
#include <new>
#include <stdexcept>

namespace family1 {
namespace {
using Clock = std::chrono::steady_clock;

unsigned int state_width(unsigned int size)
{
    return std::max(1U, static_cast<unsigned int>(std::bit_width(size - 1)));
}

unsigned int mask_bits(const LargeGraph& graph)
{
    return static_cast<unsigned int>(std::count_if(graph.ports.begin(), graph.ports.end(),
        [](const auto& row) { return row[0] != row[1]; }));
}

std::uint64_t profile_hash(const std::uint64_t* planes, unsigned int count)
{
    std::uint64_t result = 0x9e3779b97f4a7c15ULL;
    for (unsigned int i = 0; i < count; ++i) {
        auto value = planes[i];
        value ^= value >> 30; value *= 0xbf58476d1ce4e5b9ULL;
        value ^= value >> 27; value *= 0x94d049bb133111ebULL;
        result ^= (value ^ (value >> 31)) + (result << 6) + (result >> 2);
    }
    return result;
}

std::string binary_word(std::uint64_t index, unsigned int depth)
{
    std::string result(depth, '0');
    for (unsigned int i = 0; i < depth; ++i) {
        result[depth - i - 1] += index & 1;
        index >>= 1;
    }
    return result;
}

std::string complemented_word(std::uint64_t index, unsigned int depth)
{
    auto result = binary_word(index, depth);
    for (auto& c : result) c = c == '0' ? '1' : '0';
    return result;
}

std::uint64_t reverse_bits(std::uint64_t value)
{
    value = ((value >> 1) & 0x5555555555555555ULL) | ((value & 0x5555555555555555ULL) << 1);
    value = ((value >> 2) & 0x3333333333333333ULL) | ((value & 0x3333333333333333ULL) << 2);
    value = ((value >> 4) & 0x0f0f0f0f0f0f0f0fULL) | ((value & 0x0f0f0f0f0f0f0f0fULL) << 4);
    return std::byteswap(value);
}

// T(profile(w)) = profile(complement(w)): complementing the input letters and
// all STATIC mask bits leaves every chosen port unchanged, on every revisit.
// Omitting coincident-port bits commutes with this operation. Coordinates are
// ordered binary masks, so T reverses their order within each state-bit plane.
void complement_profile(const std::uint64_t* source, std::uint64_t* destination,
    unsigned int planes, unsigned int masks)
{
    const auto blocks = (masks + 63) / 64;
    const auto shift = masks < 64 ? 64 - masks : 0;
    for (unsigned int plane = 0; plane < planes; plane += blocks)
        for (unsigned int block = 0; block < blocks; ++block)
            destination[plane + block] = reverse_bits(source[plane + blocks - block - 1]) >> shift;
}

// The loop bounds for ordinary seven/eight-state products are compile-time
// constants. The dynamic fallback still represents every mask through m=20.
template<unsigned int Width, unsigned int Blocks>
void packed_step(unsigned int size, unsigned int dynamic_width, unsigned int dynamic_blocks,
    const std::uint64_t* destinations, const std::uint64_t* source,
    bool input, std::uint64_t* destination)
{
    const auto width = Width == 0 ? dynamic_width : Width;
    const auto blocks = Blocks == 0 ? dynamic_blocks : Blocks;
    std::fill_n(destination, width * blocks, std::uint64_t{0});
    const auto* transition = destinations + static_cast<std::size_t>(input) * size * width * blocks;
    for (unsigned int block = 0; block < blocks; ++block) {
        for (unsigned int state = 0; state < size; ++state) {
            std::uint64_t at = ~std::uint64_t{0};
            for (unsigned int plane = 0; plane < width; ++plane) {
                const auto value = source[static_cast<std::size_t>(plane) * blocks + block];
                at &= state & (1U << plane) ? value : ~value;
            }
            const auto* target = transition + static_cast<std::size_t>(state) * width * blocks + block;
            for (unsigned int plane = 0; plane < width; ++plane)
                destination[static_cast<std::size_t>(plane) * blocks + block]
                    |= at & target[static_cast<std::size_t>(plane) * blocks];
        }
    }
}
}

ExactPackedProduct::ExactPackedProduct(const LargeGraph& graph)
    : size_(graph.size()), width_(state_width(graph.size())), effective_bits_(mask_bits(graph))
{
    graph.validate();
    masks_ = 1U << effective_bits_;
    blocks_ = (masks_ + 63) / 64;
    mask_positions_.fill(-1);
    unsigned int position = 0;
    for (unsigned int state = 0; state < size_; ++state)
        if (graph.ports[state][0] != graph.ports[state][1]) mask_positions_[state] = position++;

    destinations_.reset(new std::uint64_t[static_cast<std::size_t>(2) * size_ * width_ * blocks_]);
    constexpr std::uint64_t patterns[] = {
        0xaaaaaaaaaaaaaaaaULL, 0xccccccccccccccccULL, 0xf0f0f0f0f0f0f0f0ULL,
        0xff00ff00ff00ff00ULL, 0xffff0000ffff0000ULL, 0xffffffff00000000ULL
    };
    const auto valid = masks_ < 64 ? (std::uint64_t{1} << masks_) - 1 : ~std::uint64_t{0};
    for (unsigned int input = 0; input < 2; ++input) {
        for (unsigned int state = 0; state < size_; ++state) {
            const auto bit = mask_positions_[state];
            for (unsigned int block = 0; block < blocks_; ++block) {
                const auto sigma = bit < 0 ? 0 : bit < 6 ? patterns[bit]
                    : ((block >> (bit - 6)) & 1) ? ~std::uint64_t{0} : 0;
                const auto port_one = (input ? ~sigma : sigma) & valid;
                for (unsigned int plane = 0; plane < width_; ++plane) {
                    auto value = (graph.ports[state][0] & (1U << plane)) ? ~port_one & valid : 0;
                    if (graph.ports[state][1] & (1U << plane)) value |= port_one;
                    destinations_[((static_cast<std::size_t>(input) * size_ + state) * width_ + plane)
                        * blocks_ + block] = value;
                }
            }
        }
    }
}

void ExactPackedProduct::step_into(const std::uint64_t* source, bool input,
    std::uint64_t* destination) const
{
    if (width_ == 3) {
        if (blocks_ == 1) return packed_step<3, 1>(size_, width_, blocks_, destinations_.get(), source, input, destination);
        if (blocks_ == 2) return packed_step<3, 2>(size_, width_, blocks_, destinations_.get(), source, input, destination);
        if (blocks_ == 4) return packed_step<3, 4>(size_, width_, blocks_, destinations_.get(), source, input, destination);
    }
    if (blocks_ == 1) {
        if (width_ == 1) return packed_step<1, 1>(size_, width_, blocks_, destinations_.get(), source, input, destination);
        if (width_ == 2) return packed_step<2, 1>(size_, width_, blocks_, destinations_.get(), source, input, destination);
        if (width_ == 4) return packed_step<4, 1>(size_, width_, blocks_, destinations_.get(), source, input, destination);
        if (width_ == 5) return packed_step<5, 1>(size_, width_, blocks_, destinations_.get(), source, input, destination);
    }
    packed_step<0, 0>(size_, width_, blocks_, destinations_.get(), source, input, destination);
}

ExactPackedProduct::Profile ExactPackedProduct::step(const Profile& state, bool input) const
{
    if (state.size() != profile_planes()) throw std::invalid_argument("packed profile has wrong size");
    Profile result(profile_planes());
    step_into(state.data(), input, result.data());
    return result;
}

ExactPackedProduct::Profile ExactPackedProduct::evaluate(const std::string& word) const
{
    Profile state(profile_planes()), next(profile_planes());
    for (char c : word) {
        if (c != '0' && c != '1') throw std::invalid_argument("nonbinary word");
        step_into(state.data(), c == '1', next.data());
        state.swap(next);
    }
    return state;
}

unsigned int ExactPackedProduct::endpoint(const Profile& state, std::uint32_t full_mask) const
{
    if (state.size() != profile_planes()) throw std::invalid_argument("packed profile has wrong size");
    if (full_mask >= (1U << size_)) throw std::out_of_range("mask outside full family");
    unsigned int mask = 0;
    for (unsigned int vertex = 0; vertex < size_; ++vertex)
        if (mask_positions_[vertex] >= 0 && (full_mask & (1U << vertex)))
            mask |= 1U << mask_positions_[vertex];
    unsigned int result = 0;
    for (unsigned int plane = 0; plane < width_; ++plane)
        result |= static_cast<unsigned int>((state[static_cast<std::size_t>(plane) * blocks_ + mask / 64]
            >> (mask % 64)) & 1) << plane;
    return result;
}

PackedScore score_packed(const LargeGraph& graph, const PackedLimits& limits)
{
    graph.validate();
    if (limits.depth > 31 || limits.max_layer_states == 0 || limits.max_layer_states > (1ULL << 31)
        || limits.max_working_bytes == 0)
        throw std::invalid_argument("packed depth <=31, layer budget in 1..2^31, and positive byte budget required");
    const auto started = Clock::now();
    PackedScore result;
    result.effective_mask_bits = mask_bits(graph);
    result.mask_count = 1U << result.effective_mask_bits;
    result.profile_planes = state_width(graph.size()) * ((result.mask_count + 63) / 64);
    const auto finish = [&]() {
        result.seconds = std::chrono::duration<double>(Clock::now() - started).count();
        return result;
    };
    const auto stopped = [&]() {
        if (limits.interrupted && *limits.interrupted) { result.reason = "interrupted"; return true; }
        if (limits.timeout_ms != 0 && std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - started).count()
            >= limits.timeout_ms) { result.reason = "timeout"; return true; }
        return false;
    };
    if (stopped()) return finish();
    if (limits.depth == 0) {
        result.status = "depth-capped"; result.reason = "depth"; return finish();
    }
    if (limits.max_layer_states < 2) {
        result.reason = "max-layer-states"; return finish();
    }
    const auto profile_bytes = static_cast<std::uint64_t>(result.profile_planes) * sizeof(std::uint64_t);
    // Product destination planes, one scratch profile for the overlapping root
    // entry, and a separate T(profile) buffer when using complement symmetry.
    const auto scratch_profiles = limits.quotient_complements ? 2U : 1U;
    const auto fixed_bytes = profile_bytes * (2ULL * graph.size() + scratch_profiles);
    if (fixed_bytes >= limits.max_working_bytes) {
        result.reason = "max-working-bytes"; return finish();
    }
    try {
        ExactPackedProduct product(graph);
        result.peak_working_bytes = fixed_bytes - scratch_profiles * profile_bytes;
        std::unique_ptr<std::uint64_t[]> scratch(new std::uint64_t[result.profile_planes]);
        result.peak_working_bytes += profile_bytes;
        std::unique_ptr<std::uint64_t[]> complement_scratch;
        if (limits.quotient_complements)
            complement_scratch.reset(new std::uint64_t[result.profile_planes]);
        result.peak_working_bytes = fixed_bytes;
        const auto remaining = limits.max_working_bytes - fixed_bytes;
        const auto maximum_profiles = std::bit_floor(std::min(limits.max_layer_states
            / (limits.quotient_complements ? 2 : 1), remaining / profile_bytes));
        if (maximum_profiles < (limits.quotient_complements ? 1U : 2U)) {
            result.reason = "max-working-bytes"; return finish();
        }
        // Small power-of-two chunks grow without ever reallocating a previous
        // layer. Budget also limits chunk size for useful tiny-budget runs.
        const auto chunk_states = std::bit_floor(std::min({maximum_profiles, std::uint64_t{4096},
            std::max<std::uint64_t>(1, remaining / (4 * profile_bytes))}));
        const auto chunk_shift = std::countr_zero(chunk_states);
        const auto chunk_count = maximum_profiles / chunk_states;
        const auto pointer_bytes = chunk_count * sizeof(std::unique_ptr<std::uint64_t[]>);
        if (pointer_bytes > remaining) { result.reason = "max-working-bytes"; return finish(); }
        // One exact-size pointer array also avoids pointer-vector reallocations.
        std::unique_ptr<std::unique_ptr<std::uint64_t[]>[]> chunks(
            new std::unique_ptr<std::uint64_t[]>[static_cast<std::size_t>(chunk_count)]);
        std::uint64_t allocated_chunks = 0;
        std::uint64_t allocated_bytes = fixed_bytes + pointer_bytes;
        result.peak_working_bytes = allocated_bytes;
        const auto profile = [&](std::uint64_t index) {
            return chunks[index >> chunk_shift].get()
                + (index & (chunk_states - 1)) * result.profile_planes;
        };
        const auto ensure_profiles = [&](std::uint64_t count) {
            const auto needed = (count + chunk_states - 1) / chunk_states;
            while (allocated_chunks < needed) {
                chunks[allocated_chunks].reset(new std::uint64_t[static_cast<std::size_t>(chunk_states)
                    * result.profile_planes]);
                ++allocated_chunks;
                allocated_bytes += chunk_states * profile_bytes;
                result.peak_working_bytes = std::max(result.peak_working_bytes, allocated_bytes);
            }
        };
        // The very first root profile is zero. All other storage is filled by
        // step_into before it can be hashed or read as a current layer.
        const auto first_chunk_bytes = chunk_states * profile_bytes;
        if (allocated_bytes + first_chunk_bytes > limits.max_working_bytes) {
            result.reason = "max-working-bytes"; return finish();
        }
        ensure_profiles(1);
        std::fill_n(profile(0), result.profile_planes, std::uint64_t{0});
        result.peak_working_bytes = allocated_bytes;
        const auto poll_stride = std::bit_floor(std::max<std::uint64_t>(1,
            std::min<std::uint64_t>(4096, 65536 / (static_cast<std::uint64_t>(graph.size())
                * result.profile_planes))));
        for (unsigned int depth = 1; depth <= limits.depth; ++depth) {
            if (stopped()) return finish();
            const auto all_words = 1ULL << depth;
            if (all_words > limits.max_layer_states) {
                result.reason = "max-layer-states"; return finish();
            }
            const auto next_count = all_words / (limits.quotient_complements ? 2 : 1);
            if (next_count > maximum_profiles) {
                result.reason = "max-working-bytes"; return finish();
            }
            const auto needed_chunks = (next_count + chunk_states - 1) / chunk_states;
            const auto growth_bytes = (needed_chunks - allocated_chunks) * chunk_states * profile_bytes;
            const auto table_size = next_count * 2; // next_count is a power of two
            const auto table_bytes = table_size * sizeof(std::uint32_t);
            const auto working_bytes = allocated_bytes + growth_bytes + table_bytes;
            if (working_bytes > limits.max_working_bytes) {
                result.reason = "max-working-bytes"; return finish();
            }
            ensure_profiles(next_count);
            std::unique_ptr<std::uint32_t[]> table(new std::uint32_t[static_cast<std::size_t>(table_size)]);
            constexpr auto empty = std::numeric_limits<std::uint32_t>::max();
            std::fill_n(table.get(), static_cast<std::size_t>(table_size), empty);
            result.peak_working_bytes = std::max(result.peak_working_bytes, working_bytes);
            for (auto index = next_count; index-- > 0;) {
                if ((index & (poll_stride - 1)) == 0 && stopped()) return finish();
                auto* destination = profile(index);
                const auto* source = profile(index / 2);
                if (index == 0) {
                    product.step_into(source, false, scratch.get());
                    std::memcpy(destination, scratch.get(), static_cast<std::size_t>(profile_bytes));
                } else product.step_into(source, (index & 1) != 0, destination);
                ++result.profiles_evaluated;
                result.evaluated_words += limits.quotient_complements ? 2 : 1;
                auto hash = limits.force_hash_collisions ? 0 : profile_hash(destination, result.profile_planes);
                if (limits.quotient_complements) {
                    complement_profile(destination, complement_scratch.get(), result.profile_planes, result.mask_count);
                    if (std::memcmp(destination, complement_scratch.get(), static_cast<std::size_t>(profile_bytes)) == 0) {
                        result.status = "exact";
                        result.merge_length = result.lower_bound = depth;
                        result.witness = {binary_word(index, depth), complemented_word(index, depth)};
                        return finish();
                    }
                    if (!limits.force_hash_collisions)
                        hash = std::min(hash, profile_hash(complement_scratch.get(), result.profile_planes));
                }
                auto slot = hash & (table_size - 1);
                while (table[slot] != empty) {
                    const auto previous = table[slot];
                    const bool direct = std::memcmp(profile(previous), destination, static_cast<std::size_t>(profile_bytes)) == 0;
                    const bool complemented = !direct && limits.quotient_complements
                        && std::memcmp(profile(previous), complement_scratch.get(), static_cast<std::size_t>(profile_bytes)) == 0;
                    if (direct || complemented) {
                        result.status = "exact";
                        result.merge_length = result.lower_bound = depth;
                        result.witness = {binary_word(index, depth), complemented
                            ? complemented_word(previous, depth) : binary_word(previous, depth)};
                        return finish();
                    }
                    slot = (slot + 1) & (table_size - 1);
                }
                table[slot] = static_cast<std::uint32_t>(index);
            }
            result.lower_bound = depth + 1;
        }
        result.status = "depth-capped";
        result.reason = "depth";
    } catch (const std::bad_alloc&) { result.reason = "allocation-failed"; }
    return finish();
}

}

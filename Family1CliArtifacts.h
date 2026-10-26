#pragma once
// Shared artifact helpers for new standalone Family 1 tools. Graph equality
// never relies on hashes; SHA-256 pins provenance and complete file bytes.
#include <array>
#include <bit>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace family1_cli {
namespace fs = std::filesystem;

// SHA-256 is used for provenance/cache integrity, never as a graph identity.
inline std::string sha256(const std::string& input)
{
    constexpr std::array<std::uint32_t, 64> constants{
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    std::array<std::uint32_t, 8> hash{
        0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    std::vector<unsigned char> bytes(input.begin(), input.end());
    const auto bit_count = static_cast<std::uint64_t>(bytes.size()) * 8;
    bytes.push_back(0x80);
    while (bytes.size() % 64 != 56) bytes.push_back(0);
    for (int shift = 56; shift >= 0; shift -= 8) bytes.push_back(static_cast<unsigned char>(bit_count >> shift));
    for (std::size_t offset = 0; offset < bytes.size(); offset += 64) {
        std::array<std::uint32_t, 64> word{};
        for (unsigned int i = 0; i < 16; ++i)
            for (unsigned int j = 0; j < 4; ++j) word[i] = (word[i] << 8) | bytes[offset + 4 * i + j];
        for (unsigned int i = 16; i < 64; ++i) {
            auto a = word[i - 15], b = word[i - 2];
            word[i] = word[i - 16] + (std::rotr(a, 7) ^ std::rotr(a, 18) ^ (a >> 3))
                + word[i - 7] + (std::rotr(b, 17) ^ std::rotr(b, 19) ^ (b >> 10));
        }
        auto a = hash[0], b = hash[1], c = hash[2], d = hash[3];
        auto e = hash[4], f = hash[5], g = hash[6], h = hash[7];
        for (unsigned int i = 0; i < 64; ++i) {
            auto first = h + (std::rotr(e, 6) ^ std::rotr(e, 11) ^ std::rotr(e, 25))
                + ((e & f) ^ (~e & g)) + constants[i] + word[i];
            auto second = (std::rotr(a, 2) ^ std::rotr(a, 13) ^ std::rotr(a, 22))
                + ((a & b) ^ (a & c) ^ (b & c));
            h = g; g = f; f = e; e = d + first; d = c; c = b; b = a; a = first + second;
        }
        hash[0] += a; hash[1] += b; hash[2] += c; hash[3] += d;
        hash[4] += e; hash[5] += f; hash[6] += g; hash[7] += h;
    }
    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (auto value : hash) output << std::setw(8) << value;
    return output.str();
}

inline std::string quote(const std::string& value)
{
    std::string result = "\"";
    const char* hex = "0123456789abcdef";
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') { result += '\\'; result += static_cast<char>(c); }
        else if (c < 32) { result += "\\u00"; result += hex[c >> 4]; result += hex[c & 15]; }
        else result += static_cast<char>(c);
    }
    return result + '"';
}


inline std::string read(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot read " + path.string());
    std::string result((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    if (input.bad()) throw std::runtime_error("failed reading " + path.string());
    return result;
}

inline void write(const fs::path& path, const std::string& text)
{
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    output << text;
    output.close();
    if (!output) throw std::runtime_error("failed writing " + path.string());
}

inline void publish(const fs::path& path, const std::string& text)
{
    if (fs::exists(path)) throw std::runtime_error("refusing to overwrite " + path.string());
    const auto temporary = fs::path(path.string() + ".tmp");
    write(temporary, text);
    fs::rename(temporary, path);
}

}

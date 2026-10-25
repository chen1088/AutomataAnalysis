# MPFR overlay

This copies the official MPFR 4.2.2 port from vcpkg commit
`c748cb44f2a435fcf015c35225c9d5545fe0021c` with two configure fixes.
The repository manifest pins that same baseline. The upstream download
checksum and patches are unchanged.

The limb-width patch checks the identical
`GMP_NUMB_BITS == sizeof(mp_limb_t) * CHAR_BIT` equality at compile time, using
a typedef whose array size is negative on a mismatch. `GMP_NUMB_BITS` still
incorporates `GMP_NAIL_BITS`. This avoids executing a temporary program for
a constant-expression check; it never forces a successful result.

The supported `PRE_CONFIGURE_CMAKE_COMMANDS` hook supplies dependency DLLs to
the remaining runtime probes: `debug/bin` for Debug and `bin` for Release.
The vcpkg helper restores its saved process PATH after each configure run.
`ADD_BIN_TO_PATH` is not supported by this version of `vcpkg_make_configure`.

All other runtime checks remain enabled, including GMP version and ABI checks.
No Windows protection, policy, permissions, or certificates are changed.
The existing `AUTORECONF` step regenerates configure from the patched source.

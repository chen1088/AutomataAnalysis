# Native witness validation

Both independent Release CLI suites passed on 2026-10-26 using the existing
Windows MSVC/vcpkg build. `validation.json` pins the executable and reference
test hashes, commands, and scope of the checks.

Each suite independently enumerates all 64 rooted accessible graph classes
through three states. The constructor suite checks scalar orbit parameters,
compressed and materialized words, every static mask, and the generic proof.
The sampler suite verifies all tiny accepted pairs and additional acceptances
through six states; deliberately matching hashes and false sampled-mask hits
are checked against complete states. Both suites exercise deterministic resume,
configuration/overwrite protection, and corrupt-artifact rejection.

`constructor-benchmark.json` records three fixed-workload repeats at size16,
with 65,536 masks. Both implementations compute the same A/B/P parameters and
verify the resulting universal pair. The Python median was 0.62084 seconds;
the whole native CLI invocation, including startup and output, took a median
0.013159 seconds, an observed ratio of 47.18. This compares the stated independent
implementations, not language performance in isolation. The resulting parameters
are A=12, B=12, P=48 and the witness length is 73.

These tests and measurements certify witness correctness. They do not prove
that the constructed witnesses are shortest or that any tested seed is a
global maximizer. The sampler's separate packed-versus-scalar fixed-word
benchmark is not duplicated here.

# Adaptiveness figures and actual word pairs

[coverage.svg](coverage.svg) shows all-tie candidate coverage against exhaustive
Family 1 findings. It measures graph generation, **k=N/A**.
[policy.svg](policy.svg) compares edit-only, finder-only and combined changes
at m=7, using joint **k=2** and the retained minimum upper from
joint **k=2/total plus k=4/permutation-first**. Its JSON sidecar preserves all
four source rows and hashes. Champion presence in a candidate pool is
separate from whether the finder returned a pair on that champion.

The example figures contain the actual two words, producing k and ranking,
the graph, and D at every prefix. Every original static-mask DFA was
independently replayed. Each source JSON and witness sidecar is retained.

| Example | Figure | Producing k | Verified length | Reference |
|---|---|---|---:|---|
| Four-state graph 0001000200030203 | [inflated pair](inflated-k2/witness.svg) | Joint 2, total D | 15 | Exact H=8, oracle k=N/A |
| Same graph | [refined pair](refined-k4/witness.svg) | Joint 4, total D | 9 | Exact H=8, oracle k=N/A |
| Same graph | [exact pair](exact/witness.svg) | N/A, exhaustive word layers | 8 | Exact H=8 |
| Seven-state graph 0102030403040105020600050206 | [inflated pair](m7-inflated-k2/witness.svg) | Joint 2, total D | 67 | Verified H≤17; exact H unknown |
| Same graph | [refined pair](m7-refined-k4/witness.svg) | Joint 4, permutation first | 17 | Verified H≤17; exact H unknown |

The native finder examples enumerate all divergence starts through c=2, beam 1,
diagonal/unequal beams 0, maximum length 80 and 2,000,000 expansions per
attempt. Starts that cannot improve a pair already found can be skipped.
The seven-state illustration was selected after the full comparison;
it is not a held-out validation set. No finite finder upper is relabeled
as a shortestness proof.

Recreate an example in a fresh directory:

    python3 scripts/hard_pair_witness_figure.py \
      --input output/figures/family1-adaptiveness/inflated-k2-source.json \
      --out out/adaptive-example-repro

Use the matching source JSON for each other example. Recreate the policy
chart with scripts/family1_adaptive_policy_figure.py; coverage is produced by
scripts/family1_adaptive_edit_benchmark.py.

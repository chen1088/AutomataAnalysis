# Hard-pair figures and witness records

The current eight-state plate at `output/pdf/family1-m8-active-best/active-best.pdf`
shows both length-50 words, the full prefix disagreement trace, and the
verification count. The pair proves an upper bound. Its shortestness and the
global maximum remain unresolved. The working estimate 49 is a historical
conjecture. The producing common-suffix k is **unknown**: completed refinement
k=10,12 and the incomplete k=16 attempt do not identify the imported witness's
producer. Producing beam and prefix settings are also unknown.

`witnesses.json` beside the PDF records the words, graph table, every prefix
score, search provenance, and independent scalar verification. Each Family 1
coordinate is one original static mask, so identical DFA realizations caused
by coincident ports retain multiplicity. D(i) counts different endpoints after
the two prefixes of length i; the synchronized count is the family size minus
D(i). D(empty)=0. Under unequal joint symbols, agreeing endpoints may separate
again. A distinct pair with D(final)=0 is the required certificate.

To rebuild the current plate in a fresh directory:

```bash
python3 scripts/family1_active_best_figure.py --out out/active-pair-figure
```

The generator always emits editable TikZ. It compiles with `pdflatex` when
available; otherwise matplotlib writes a vector PDF using the same established
graph geometry. `--renderer tex` or `--renderer matplotlib` selects explicitly.

`scripts/hard_pair_witness_figure.py` creates a standalone SVG, `witness.json`,
and a short README for one found pair. It launches no search and uses no
randomness. A native joint record supplies its producing k and four-symbol
alphabet. A saved generic benchmark fixture supplies the complete DFA family:

```bash
python3 scripts/hard_pair_witness_figure.py \
  --input out/my-benchmark/records.jsonl \
  --fixtures out/my-benchmark/fixtures.json \
  --case generated-closure-union-05 --k 4 \
  --out out/my-benchmark-pair-k4
```

For Family 1 records containing `canonical_table`, omit `--fixtures`; all
original static masks are constructed and replayed. `--case` selects the graph
key. `--k` only selects an existing result, and never changes its search
parameters. The renderer checks every DFA at every prefix and rejects a saved
metric trace that disagrees with its independent replay. It retains k, window
kind, beam/prefix/startup settings, and source hashes. Generic figures count
the saved fixture entries, whose duplicate policy remains recorded separately.

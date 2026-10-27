# Active eight-state candidate and its pair

The figure displays the verified length-50 upper witness below. The shortest length and global maximum remain unproved. The displayed estimate 49 is a historical working conjecture.

u = `00001101101010101011000111100000011010010011100010`

v = `00100011011010101011000111100000011010010011100010`

k=unknown; common-suffix-historical. Producing beam and prefix settings are unknown. Separate refinement: completed common-suffix k=10,12; attempted k=16 (incomplete). These values do not identify the producer of this imported pair.

Independent scalar replay checks all 256 original static masks, including duplicate realizations from coincident ports. D(i) is the number with different endpoints after both prefixes of length i; D(empty)=0. witnesses.json retains both words, every prefix score, search provenance and verification.

graph-01.tex preserves the complete original transition drawing. All arrows remain solid and unlabelled; marked vertices are alternative starts chosen separately. The displayed pair belongs to representative start 0. records.json retains all source-rooted cases and audits.

Regenerate in a fresh directory with `python3 scripts/family1_active_best_figure.py --out out/my-active-best-figure`. The default renderer uses TeX when available and otherwise writes a vector PDF with matplotlib using the same atlas edge geometry. Editable TikZ is emitted in both cases.

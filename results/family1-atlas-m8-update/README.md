# Single m8 atlas interval overlay

This updates the existing illustrated eight-state root-lift graph to 35 <= H(G) <= 52. The graph, construction, root and layout metadata are unchanged. A complete check of words of length 34 supplies the lower certificate; a distinct pair of 52 symbols is independently replayed over all 256 static masks. The exact graph score and global maximum remain unresolved. No other size receives a new bound.

Use this one-record file together with results/family1-atlas-current/champions.jsonl. The original presentation dataset stays unchanged, including all 20 certified rooted winners through seven states and all thirteen larger examples. Do not substitute the full search corpus: that would change the atlas's selected scope. Checked native evidence and code snapshots are retained under evidence/; evidence-inventory.json maps original pins to these copies.

Recreate this overlay with uv run --no-project python scripts/family1_atlas_m8_overlay.py. Build the atlas using both --input results/family1-atlas-current and --input results/family1-atlas-m8-update/records.jsonl, preserving --overview, --ancestry and --edit-distances settings recorded in the atlas source manifest.

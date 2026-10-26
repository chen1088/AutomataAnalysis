# Consecutive-size ancestry of every certified winner through seven states

All rooted maximizing classes are retained at each size. Each step deletes a nonroot vertex of indegree two and routes its incoming ports to its outgoing ports; the single-loop case smooths one external edge and removes the loop. Every allowed routing is tested and every accessible predecessor receives its exact score from the full small-case journal. This is a defined growth relation, not a claim that all graph changes must have this form.

| Step | Maximum H | Rooted child winners | Children with a rooted winning parent | Previous winners reaching a winning child | Winner links |
|---|---:|---:|---:|---:|---:|
| 1 -> 2 | 1 -> 3 | 1 | 1/1 | 1/1 | 1 |
| 2 -> 3 | 3 -> 6 | 2 | 0/2 | 0/1 | 0 |
| 3 -> 4 | 6 -> 10 | 1 | 0/1 | 0/2 | 0 |
| 4 -> 5 | 10 -> 15 | 5 | 0/5 | 0/1 | 0 |
| 5 -> 6 | 15 -> 23 | 2 | 1/2 | 2/5 | 2 |
| 6 -> 7 | 23 -> 34 | 8 | 1/8 | 1/2 | 1 |

## All consecutive steps

### 1 to 2

[Complete operations, all best ties, and every previous winner](m1-m2/README.md).

| Child ordinal | Child key | Best parent H | Increase | Rooted winning parent keys |
|---:|---|---:|---:|---|
| 1 | `00010001` | 1 | 2 | `0000` |

### 2 to 3

[Complete operations, all best ties, and every previous winner](m2-m3/README.md).

| Child ordinal | Child key | Best parent H | Increase | Rooted winning parent keys |
|---:|---|---:|---:|---|
| 7 | `000101020001` | none | none | none |
| 45 | `010200010102` | 1 | 5 | none |

### 3 to 4

[Complete operations, all best ties, and every previous winner](m3-m4/README.md).

| Child ordinal | Child key | Best parent H | Increase | Rooted winning parent keys |
|---:|---|---:|---:|---|
| 443 | `0102000201030003` | 5 | 5 | none |

### 4 to 5

[Complete operations, all best ties, and every previous winner](m4-m5/README.md).

| Child ordinal | Child key | Best parent H | Increase | Rooted winning parent keys |
|---:|---|---:|---:|---|
| 1391 | `00010203000103040204` | 9 | 6 | none |
| 1511 | `00010203000301040204` | 9 | 6 | none |
| 5982 | `01020003010203040004` | 9 | 6 | none |
| 6241 | `01020003010402030104` | 9 | 6 | none |
| 6811 | `01020003030400030104` | 8 | 7 | none |

### 5 to 6

[Complete operations, all best ties, and every previous winner](m5-m6/README.md).

| Child ordinal | Child key | Best parent H | Increase | Rooted winning parent keys |
|---:|---|---:|---:|---|
| 33343 | `000102030304020500010405` | 15 | 8 | `00010203000103040204`, `00010203000301040204` |
| 117031 | `010200030405020300010405` | 14 | 9 | none |

### 6 to 7

[Complete operations, all best ties, and every previous winner](m6-m7/README.md).

| Child ordinal | Child key | Best parent H | Increase | Rooted winning parent keys |
|---:|---|---:|---:|---|
| 539749 | `0001020302030405000604060105` | 21 | 13 | none |
| 679758 | `0001020304050406050600010203` | 22 | 12 | none |
| 1783759 | `0102000301040204050600030506` | 21 | 13 | none |
| 2221624 | `0102000304050106000304050206` | 23 | 11 | `010200030405020300010405` |
| 2470130 | `0102010203040005030604060005` | 22 | 12 | none |
| 2471796 | `0102010203040005050600060304` | 22 | 12 | none |
| 3411148 | `0102020304050006000604050103` | 22 | 12 | none |
| 4099217 | `0102030405060001000203040506` | 22 | 12 | none |

## Reproduce

```powershell
uv run python scripts/family1_ancestry.py --all-sizes
uv run python tests/family1_ancestry_test.py
```

Each step has its own source hashes, exact parent witnesses, all operation details, canonical-parent insertion reconstructions, and explicit coverage of every previous maximizing class. The ordinary-shape comparison is reported separately and never changes a rooted score.

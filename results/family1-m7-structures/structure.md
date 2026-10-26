# Family 1 maximizing graph structures: m=7

Certified maximum H=34; complete collection of 8 rooted classes.

Indegrees count both ports and are sorted in descending order. Loop ports use `state:port`. The root column gives its positions in the ordinary canonical table. Automorphisms count vertex permutations.

| Class | Rooted key | H | Indegrees | Loop ports | Coincident states | SCC sizes | Shape | Root orbit | Aut |
| --- | --- | ---: | --- | --- | --- | --- | ---: | --- | ---: |
| 1 | `0001020302030405000604060105` | 34 | 2,2,2,2,2,2,2 | 0:0,2:0 | none | 7 | 2 | 0 | 1 |
| 2 | `0001020304050406050600010203` | 34 | 2,2,2,2,2,2,2 | 0:0 | none | 7 | 4 | 0 | 1 |
| 3 | `0102000301040204050600030506` | 34 | 2,2,2,2,2,2,2 | 6:1 | none | 7 | 4 | 3 | 1 |
| 4 | `0102000304050106000304050206` | 34 | 2,2,2,2,2,2,2 | 5:1,6:1 | none | 7 | 1 | 5 | 1 |
| 5 | `0102010203040005030604060005` | 34 | 2,2,2,2,2,2,2 | 1:0 | none | 7 | 3 | 5 | 1 |
| 6 | `0102010203040005050600060304` | 34 | 2,2,2,2,2,2,2 | 1:0 | none | 7 | 4 | 5 | 1 |
| 7 | `0102020304050006000604050103` | 34 | 2,2,2,2,2,2,2 | 5:1 | none | 7 | 4 | 2 | 1 |
| 8 | `0102030405060001000203040506` | 34 | 2,2,2,2,2,2,2 | 6:1 | none | 7 | 4 | 4 | 1 |

| Shape | Ordinary canonical key | Rooted classes | Canonical root orbits | Vertex automorphisms |
| ---: | --- | ---: | --- | ---: |
| 1 | `0001020302030405000601060405` | 1 | 5 | 1 |
| 2 | `0001020302030405000604060105` | 1 | 0 | 1 |
| 3 | `0001020303040506050600010204` | 1 | 5 | 1 |
| 4 | `0001020304050406050600010203` | 5 | 0; 3; 5; 2; 4 | 1 |

Observed within this finite certified collection:

- The certified m=7 collection contains 8 distinct rooted maximizing classes.
- 8 of these 8 rooted classes are strongly connected.
- Loop-port counts among the rooted classes: 1: 6 classes; 2: 2 classes.
- Coincident-port state counts among the rooted classes: 0: 8 classes.
- There are 1 distinct sorted indegree sequences in this collection.
- Allowing the root to move groups these 8 rooted classes into 4 ordinary shapes.

# GRAIN-1: derivations over the object basis (ARCGraph, one node one step)

Fable v35 rev 3 (the measurement programme at object level) and design_revision_minimal_grain_oct14 rev 6 (R1–R3).
Measurement only: nothing here is read by a probe or a build. Dev ids only. Every check compares a term's output with
the **reading's own output** on a training input (computed by running the reading's code), never with a test output.

Files: `grain1.py` (parser, static checker, expansion, ruler, interpreter), `grain1_check.py` (verification),
`SPEC_translate_obj1.md` (translator instructions). GRAIN-0 (`grain.py`, cell basis) is the cell-level baseline.

## What the basis is
- **Individuals are nodes** (objects) of an ARCGraph abstraction chosen per task (a parameter, not a leaf).
- **No cell type.** No operator reads or paints a cell by coordinates. A term knows a node's colours, size and
  bounding box, and relations between nodes. Cell-level code lives only inside the fixed node operations below.
- **Action leaves change one node by one step.** Larger actions are derivations: loops of steps under guards.
  "Move until it touches the wall" is `(while (free o 2) (move o 2))`.

## Translation format
```
{"task", "basis": "obj1", "abstraction": "nbccg"|"ccgbr"|"nbvcg"|"nbhcg"|"mcccg", "bg": "default"|"black"|"modal",
 "defs": [...], "leaves": [...], "main": TERM}
```
`defs` are macros, as in GRAIN-0: `{"name", "kind": "act"|"test"|"expr", "params", "body"}`; static expansion; a
definition may use only earlier definitions; recursion is `while`. A definition argument may be a term, a test or an
expression (it is checked after expansion). `leaves` are NEW leaves (see the end).

## Scenes
- `in`: the input grid segmented under the task's abstraction. Read-only.
- `out`: starts as a copy of `in` (same node ids). The output grid is the **rendering of out**: its canvas (H x W,
  background colour bg) with every node painted in id order (higher id on top); pixels off the canvas are dropped.
  The empty term `(skip)` therefore returns the input unchanged.
- Node ids: 1..n in row-major order of each node's first pixel at segmentation. Created nodes get fresh, higher ids.

| abstraction | nodes | default bg |
|---|---|---|
| nbccg | 4-connected single-colour components of non-bg cells | 0 (black) |
| ccgbr | 4-connected single-colour components of every colour, except bg-coloured ones touching a grid corner | 0 |
| nbvcg | vertical single-colour runs (one column each) of non-bg cells | modal colour |
| nbhcg | horizontal single-colour runs (one row each) of non-bg cells | modal colour |
| mcccg | 4-connected multicolour components of non-bg cells | 0 |

`"bg": "black"` or `"modal"` overrides the default (for the start and for every `(segment A)`). The modal colour is
the most common one; ties go to the colour seen first in row-major order (as Python's `Counter.most_common`). With
`"bg": "default"`, a `(segment A)` uses A's own default (so nbvcg then `(segment nbccg)` goes back to bg 0); set
`"bg": "modal"` when a translation switches abstractions on a non-black background.

## Grammar
```
TERM := (skip) | (seq TERM ...) | (if TEST TERM [TERM]) | (while TEST TERM) | ACTION | (DEF args) | (LEAF args)
```
Values are integers: node ids, colours 0..9, directions 0..7 (N E S W NE SE SW NW), counts, -1 for "none".
Registers: any other name; `(set r e)`; unset registers read 0. Reserved (not usable as registers): operator names,
`in`, `out`, `t0`..`t9`, the abstraction names and the rcc relation names `dc ec po eq tpp ntpp tppi ntppi`.

### Node actions (the one-step leaves; o, p are out nodes)
| action | effect |
|---|---|
| `(recolor o k)` | every pixel of o gets colour k |
| `(move o d)` | o moves one cell in direction d |
| `(extend o d)` | o grows one cell in direction d: each pixel whose d-neighbour is not in o adds that neighbour, same colour |
| `(shrink o d)` | o loses the outermost row or column of its box on side d (0 top, 1 right, 2 bottom, 3 left); a node cannot become empty |
| `(border o k)` | new node: the 8-neighbour ring of o, on the canvas and not covered by any node, colour k |
| `(fillrect o k)` | new node: the cells of o's bounding box not covered by any node, colour k |
| `(hollow o)` | o loses its pixels that are not on its bounding-box border |
| `(flip o a)` | one reflection inside o's box: a=0 left-right, 1 up-down, 2 main diagonal, 3 anti-diagonal (box top-left kept) |
| `(rotate o)` | a quarter turn clockwise (box top-left kept) |
| `(copy o)` | new node identical to o, on top |
| `(delete o)` | o is removed |
| `(merge o p)` | o takes p's pixels (p's colours win where they overlap); p is removed |
| `(split o m)` | m=0: o's 4-connected single-colour parts; m=1: o's single pixels. o keeps the first part (row-major), the others become new nodes |
| `(new k)` | new one-pixel node of colour k at the canvas origin (0, 0); place it with moves |

`(last)` is the id of the most recently created node (-1 after a creation that produced nothing; after `split`, the
last new part, or -1 if o was a single part).
`(split o 1)` and `(new k)` work at pixel level. They are allowed and counted (`pixel_level` in the checker).

### Bookkeeping and interface
| operator | effect |
|---|---|
| `(set r e)` | register |
| `(settag o e)`, `(tag o)` | an integer tag per out node (0 if never set): marks, labels, ranks |
| `(put t i e)`, `(get t i)` | integer tables t0..t9 indexed by any integer (0 if never set): counts, lists of ids |
| `(canvas h w k)` | out's canvas becomes h x w with background k; nodes are kept (move them as needed) |
| `(segment A)` | out is re-segmented from its own rendering under abstraction A (new ids; the rendering is unchanged) |

### Expressions
`(+ e e)`, `(- e e)`; `(first S)`, `(next S o)` (smallest live id greater than o; -1 at the end), `(count S)`,
`(last)`; node attributes `(color S o)` (-1 if o has several colours), `(ncolors S o)`, `(npix S o k)`, `(size S o)`,
`(top S o)`, `(left S o)`, `(bottom S o)`, `(right S o)` (bounding box, inclusive); `(H S)`, `(W S)`, `(bg S)`;
`(tag o)`, `(get t i)`; `(dist S o p)` = Chebyshev distance between the pixel sets of o and p.

### Tests
`(true)`, `(false)`, `(not T)`, `(and T T ...)`, `(or T T ...)`, `(= e e)`, `(!= e e)`, `(< e e)`, `(<= e e)`;
`(alive S o)`; `(inbounds o)` (every pixel of out node o on the canvas); `(free o d)` (o moved one step in d stays on
the canvas and covers no other out node); `(overlaps o)` (some pixel of out node o is covered by another out node).

O0 relations between two nodes o, p of one scene S (groundings as tools/dream/o0/items, read at node grain):
| test | true when |
|---|---|
| `(rcc S o p R)` | RCC-8 relation R in dc, ec, po, eq, tpp, ntpp, tppi, ntppi on filled regions (node cells plus the cells they enclose; connection = 4-adjacency) |
| `(dir_rel S o p d)` | o lies in direction d of p: N = o's box ends above p's box and their columns overlap; E, S, W alike; NE = above and right of, etc. |
| `(adjacent S o p d)` | o lies in direction d (0..3) of p, touching: d=0 means o's box ends on the row just above p's box, with their columns overlapping (same convention as dir_rel) |
| `(aligned S o p ax)` | the boxes share a row (ax 0) or a column (ax 1) |
| `(allen S o p ax rel)` | Allen relation on the row (ax 0) / column (ax 1) projections: rel 0 before, 1 meets, 2 overlaps, 3 during, 4 starts, 5 finishes, 6 equals |
| `(between S o p q ax)` | a cell of o lies strictly between a cell of p and a cell of q on one row (ax 0), column (1) or diagonal (2), with only empty cells or o's cells between them |
| `(sees S o p ax)` | o and p face each other along a row (0) / column (1) with only empty cells between |
| `(on_ray S o p d)` | a ray cast from p in direction d over empty cells first meets o |
| `(nearest S o p)` | p is a node at minimum Chebyshev distance from o (ties: all) |
| `(translate_of S o p)` | o and p are distinct with the same coloured shape |
| `(reflection_of S o p a)` | o is p reflected (a: 0 rows reversed, 1 columns reversed, 2 transpose, 3 anti-transpose), colours kept |
| `(rotation_of S o p k)` | o is p turned k quarter turns clockwise (k 1..3) |
| `(same_form S o p)` | same shape, colours ignored |
| `(mirror_cell S o p ax)` | every cell of o mirrors (across the canvas's middle row, ax 0, or middle column, ax 1) onto a cell of p |
| `(period S o p ax k)` | o has a cell k cells along the row (ax 0) or column (ax 1) from a cell of p, outside p |

## Iterating over nodes
There is no for-each leaf; it is a derivation (and M2 may find it as a construction):
```
(seq (set o (first out)) (while (!= o -1) (seq BODY (set o (next out o)))))
```
A loop over `out` also visits nodes that BODY creates (they get higher ids). To visit only the original nodes, loop
over `in` (ids are shared with `out` until a node is deleted; check `(alive out o)`), or stop at an id saved before
the loop.

## Notes that matter in practice
- Definitions are macros, not functions: registers used in a body that are not parameters are global, and every
  token equal to a parameter name is substituted (heads included). Use distinct register names per definition.
- `(split o m)` gives the new parts consecutive ids ending at `(last)`. A definition parameter may stand in head
  position (an operator name or a whole term passed as an argument); the expanded term is what is checked.
- `rcc` relations use filled regions (a node sitting in another's hole is inside it); for plain contact use a moved
  copy and `(dist S o p)` = 0. `between` needs three distinct nodes. `free`, `overlaps`, `border` and `fillrect` see
  every out node; nodes to be ignored can be moved off the canvas and back.
- Tags are keyed by node id only (not by scene). Unset tags and table entries read 0, not -1; node ids start at 1,
  so 0 also reads as "no node".
- `(canvas h w k)` keeps the nodes: a 1 x 1 output still shows any node covering (0, 0); delete or move nodes first.
- There is no multiplication, division or mod, and expressions have no `if`; use loops with counters, and act
  definitions that set a register. Tests cannot run actions: a check that needs scratch copies is an act definition
  that sets a register to 1 or 0. Definitions return results through registers or tables.
- `(free o d)` checks every cell o would occupy after the step, so another node lying on o's own cells (or just ahead)
  blocks it. `border` and `fillrect` never cover an existing node and stay on the canvas.
- The state recorded at each `while` head includes registers exactly and nodes, tags and tables by hash.

## Ruler
L(t) = operator nodes of the statically expanded term; operands are free; a loop counts once.

## Execution and termination
Step bound 3,000,000 operator evaluations. At each `while` head the state (registers, out's nodes, canvas, tags,
tables, last) is recorded; a repeated state rejects the run as non-terminating. A node may not drift more than 200
cells off the canvas; at most 3,000 nodes.

## New leaves (the exception)
Declare one only where no term over this basis reproduces the reading: `{"name", "kind", "params", "pre", "effect",
"py"}`. The py function is `def name(S, *args)`. Scene and table names arrive as strings, everything else as ints.
State API: `S.scene('in'|'out')` (`.H`, `.W`, `.bg`, `.nodes` = {id: {(y, x): colour}}), `S.node(scene, o)` (a
copy of the pixel dict), `S.set_node(o, pix)` (replace out node o), `S.add_node(pix)` -> new id, `S.delete(o)`,
`S.alive(scene, o)`. An act leaf may change at most one existing out node and create at most one node (checked at
run time: a violation aborts the run). Test and expression leaves may not change the state. Parameters are nodes,
colours, directions, counts or scene names, never cell coordinates.

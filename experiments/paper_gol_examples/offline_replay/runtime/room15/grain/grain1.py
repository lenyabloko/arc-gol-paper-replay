"""GRAIN-1: derivations over the OBJECT basis B_obj = ARCGraph (Fable v35 rev 3; design_revision_minimal_grain_oct14
rev 6, R1-R3). Terms range over nodes (objects), colours, directions and integers. There is NO cell type: no operator
reads or paints a cell by coordinates; cell-level code exists only inside the fixed definitions of the node operations
below (and inside declared new leaves, which are checked to change at most one node).

A translation is a JSON object
  {"task": id, "basis": "obj1", "abstraction": "nbccg"|"ccgbr"|"nbvcg"|"nbhcg"|"mcccg", "bg": "default"|"black"|"modal",
   "defs": [DEF...], "leaves": [LEAF...], "main": TERM}
DEF and LEAF as in GRAIN-0 (grain.py): definitions are macros (static expansion, no recursion); a LEAF is a NEW leaf
declared only where no term over the basis fits: {"name", "kind": "act"|"test"|"expr", "params", "pre", "effect", "py"}.
The py function is called as fn(S, *args) with the State API documented in README_obj1.md.

Scenes. `in` = the input grid segmented under the task's abstraction (read-only); `out` = a copy of `in` (the identity
is the interface default). A scene has a canvas (height H, width W, background colour bg) and nodes; a node has an id
(ids 1..n in row-major order of each node's first pixel at segmentation; created nodes get fresh ids, higher = on
top) and pixels {(y, x): colour}. The output grid is the rendering of `out`: the canvas filled with bg, then every
node painted in id order, pixels outside the canvas dropped. Rendering `in` gives the input grid back exactly.
Abstractions (ARGA, xu2023arga; background binding as this repo's candidate/ontology primary hypotheses):
  nbccg  4-connected single-colour components of non-bg cells; bg = 0 (literal black)
  ccgbr  4-connected single-colour components of every colour, except bg-coloured components that touch a corner
         (those are canvas); bg = 0
  nbvcg  vertical single-colour runs of non-bg cells (one column each); bg = modal colour
  nbhcg  horizontal single-colour runs of non-bg cells (one row each); bg = modal colour
  mcccg  4-connected multicolour components of non-bg cells; bg = 0
  "bg": "black" or "modal" overrides the binding (for the initial segmentation and every (segment A)).

Ruler (R3): L(t) = number of operator nodes of the statically expanded term; operands (literals, register, scene,
table, abstraction and relation names) are free; a loop counts once. Guards are evaluated outermost-first and lazily.
Termination: step bound FUEL; at each While head the full state (registers, out's nodes, canvas, tags, tables, last) is
recorded per loop entry; a repeated state means the loop cannot terminate and the run is rejected."""
import json, re
from grain import parse, unparse, _subst, _nodes, GrainError

DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1), (-1, 1), (1, 1), (1, -1), (-1, -1)]   # N E S W NE SE SW NW
N4 = DIRS[:4]
FUEL = 3_000_000
SCENES = ('in', 'out')
ABSTR = ('nbccg', 'ccgbr', 'nbvcg', 'nbhcg', 'mcccg')
TABLES = tuple('t%d' % i for i in range(10))
RCC = ('dc', 'ec', 'po', 'eq', 'tpp', 'ntpp', 'tppi', 'ntppi')
CONTROL = {'skip', 'seq', 'if', 'while'}

# operator -> (kind, argument slots). Slots: e expression, S scene name, A abstraction name, r register name,
# t table name, R rcc relation name. (and / or take 2+ tests; not takes one test.)
SIG = {
    # --- one-node actions (the ARCGraph node operations, one step each)
    'recolor': ('act', 'ee'),     # (recolor o k)      every pixel of o gets colour k
    'move': ('act', 'ee'),        # (move o d)         o moves one cell in direction d
    'extend': ('act', 'ee'),      # (extend o d)       o grows one cell in direction d (each face pixel's neighbour)
    'shrink': ('act', 'ee'),      # (shrink o d)       o loses its box's outermost row/column on side d (0..3)
    'border': ('act', 'ee'),      # (border o k)       new node: the 8-neighbour ring of o (free, on canvas), colour k
    'fillrect': ('act', 'ee'),    # (fillrect o k)     new node: the free cells of o's bounding box, colour k
    'hollow': ('act', 'e'),       # (hollow o)         o loses its pixels off its bounding-box border
    'flip': ('act', 'ee'),        # (flip o a)         one reflection of o in its box: 0 left-right, 1 up-down,
                                  #                    2 main diagonal, 3 anti-diagonal (box top-left kept)
    'rotate': ('act', 'e'),       # (rotate o)         a quarter turn clockwise (box top-left kept)
    'copy': ('act', 'e'),         # (copy o)           new node = o (same pixels), on top
    'delete': ('act', 'e'),       # (delete o)
    'merge': ('act', 'ee'),       # (merge o p)        o takes p's pixels (p's on top); p is deleted
    'split': ('act', 'ee'),       # (split o m)        m 0: o's 4-connected single-colour parts; m 1: o's pixels.
                                  #                    o keeps the first part; the rest are new nodes (row-major)
    'new': ('act', 'e'),          # (new k)            new one-pixel node of colour k at the canvas origin
    # --- bookkeeping (no grid content)
    'set': ('act', 're'),         # (set r e)          register r := e
    'settag': ('act', 'ee'),      # (settag o e)       the integer tag of out node o := e
    'put': ('act', 'tee'),        # (put t i e)        table t at index i := e
    # --- interface
    'canvas': ('act', 'eee'),     # (canvas h w k)     out's canvas becomes h x w with background k (nodes kept)
    'segment': ('act', 'A'),      # (segment A)        out is re-segmented from its own rendering under abstraction A
    # --- expressions
    '+': ('expr', 'ee'), '-': ('expr', 'ee'),
    'first': ('expr', 'S'),       # smallest live id of scene S (-1 if none)
    'next': ('expr', 'Se'),       # smallest live id of S greater than o (-1 if none)
    'count': ('expr', 'S'),       # number of nodes of S
    'last': ('expr', ''),         # id of the node most recently created in out (-1 if none)
    'color': ('expr', 'Se'),      # o's colour if it has one colour, else -1
    'ncolors': ('expr', 'Se'),    # number of distinct colours of o
    'npix': ('expr', 'See'),      # (npix S o k) number of o's pixels of colour k
    'size': ('expr', 'Se'),
    'top': ('expr', 'Se'), 'left': ('expr', 'Se'), 'bottom': ('expr', 'Se'), 'right': ('expr', 'Se'),
    'H': ('expr', 'S'), 'W': ('expr', 'S'), 'bg': ('expr', 'S'),
    'tag': ('expr', 'e'),         # (tag o) tag of out node o (0 if never set)
    'get': ('expr', 'te'),        # (get t i) table entry (0 if never set)
    'dist': ('expr', 'See'),      # Chebyshev distance between the pixel sets of o and p
    # --- tests
    'true': ('test', ''), 'false': ('test', ''), 'not': ('test', 'b'), 'and': ('test', '*'), 'or': ('test', '*'),
    '=': ('test', 'ee'), '!=': ('test', 'ee'), '<': ('test', 'ee'), '<=': ('test', 'ee'),
    'alive': ('test', 'Se'),      # o is a node of S
    'inbounds': ('test', 'e'),    # every pixel of out node o is on out's canvas
    'free': ('test', 'ee'),       # (free o d) o moved one step in d stays on the canvas and overlaps no other out node
    'overlaps': ('test', 'e'),    # (overlaps o) some pixel of out node o is also covered by another out node
    # O0 relations between nodes of one scene (README_obj1.md gives each grounding)
    'rcc': ('test', 'SeeR'), 'dir_rel': ('test', 'Seee'), 'adjacent': ('test', 'Seee'), 'aligned': ('test', 'Seee'),
    'allen': ('test', 'Seeee'), 'between': ('test', 'Seeee'), 'sees': ('test', 'Seee'), 'on_ray': ('test', 'Seee'),
    'nearest': ('test', 'See'), 'translate_of': ('test', 'See'), 'reflection_of': ('test', 'Seee'),
    'rotation_of': ('test', 'Seee'), 'same_form': ('test', 'See'), 'mirror_cell': ('test', 'Seee'),
    'period': ('test', 'Seeee'),
}
NODE_ACTIONS = ('recolor', 'move', 'extend', 'shrink', 'border', 'fillrect', 'hollow', 'flip', 'rotate', 'copy', 'delete',
                'merge', 'split', 'new')
# The bases. obj1 = B_obj (v35 rev 3 M1). obj1b = B_obj' for M3 (supervisor's reading of v35 rev 3: "a different
# abstraction as default (mcccg first) and the dihedral step removed as a leaf"): the only segmentation is mcccg (at
# the start and in (segment A)), and flip / rotate are not leaves (a reflection or turn must be derived).
BASES = {'obj1': {'removed': set(), 'abstractions': ('nbccg', 'ccgbr', 'nbvcg', 'nbhcg', 'mcccg')},
         'obj1b': {'removed': {'flip', 'rotate'}, 'abstractions': ('mcccg',)}}
RESERVED = set(SIG) | CONTROL | set(SCENES) | set(ABSTR) | set(TABLES) | set(RCC)
BASIS_OBJ1 = sorted(SIG)


class Abort(Exception): pass
class NonTerminating(Exception): pass
class OutOfFuel(Exception): pass


# ------------------------------------------------------------------ program (parse, static check, expansion, ruler)
class Program:
    def __init__(self, tr, extra=None):
        self.task = tr.get('task'); self.basis = tr.get('basis', 'obj1')
        if self.basis not in BASES: raise GrainError('basis must be one of %s' % sorted(BASES))
        self.removed = BASES[self.basis]['removed']; self.abstractions = BASES[self.basis]['abstractions']
        self.abstraction = tr.get('abstraction', self.abstractions[0])
        if self.abstraction not in self.abstractions:
            raise GrainError('basis %s allows the abstractions %s, got %s' % (self.basis, self.abstractions, self.abstraction))
        self.bgmode = tr.get('bg', 'default')
        if self.bgmode not in ('default', 'black', 'modal'): raise GrainError('bg must be default, black or modal')
        self.defs, self.leaves = {}, {}
        self.extra = dict(extra or {})          # M3 variants may remove or add basis operators
        for lf in tr.get('leaves', []):
            n = lf['name']
            if n in RESERVED or n in self.leaves: raise GrainError('leaf name taken: ' + n)
            for k in ('pre', 'effect', 'py', 'kind', 'params'):
                if k not in lf: raise GrainError('leaf %s lacks %s' % (n, k))
            if lf['kind'] not in ('act', 'test', 'expr'): raise GrainError('leaf %s: bad kind' % n)
            ns = {'__builtins__': __builtins__}
            exec(compile(lf['py'], 'leaf_' + n, 'exec'), ns)
            if not callable(ns.get(n)): raise GrainError('leaf %s: py defines no function %s' % (n, n))
            self.leaves[n] = {'kind': lf['kind'], 'params': list(lf['params']), 'fn': ns[n]}
        for d in tr.get('defs', []):
            n = d['name']
            if n in RESERVED or n in self.leaves or n in self.defs: raise GrainError('def name taken: ' + n)
            body = parse(d['body']) if isinstance(d['body'], str) else d['body']
            self.defs[n] = {'kind': d['kind'], 'params': list(d['params']), 'body': body}
            self._check(body, d['kind'], set(d['params']), n)
        self.main = parse(tr['main']) if isinstance(tr['main'], str) else tr['main']
        self._check(self.main, 'act', set(), 'main')
        self.expanded = self.expand(self.main)
        self._check(self.expanded, 'act', set(), 'expanded main')   # definition arguments checked where they land

    def sig(self, h):
        if h in self.removed: raise GrainError('%s is not a leaf of basis %s (derive it)' % (h, self.basis))
        if h in self.extra: return self.extra[h]
        if h in SIG: return SIG[h]
        if h in self.leaves: return self.leaves[h]['kind'], 'e' * len(self.leaves[h]['params'])
        if h in self.defs: return self.defs[h]['kind'], 'p' * len(self.defs[h]['params'])
        raise GrainError('unknown operator: %s' % h)

    def _check(self, x, kind, params, where):
        if not isinstance(x, list):
            if kind in ('act', 'test') and x not in params:
                raise GrainError('%s: a bare atom where a %s is expected: %s' % (where, 'term' if kind == 'act' else 'test', x))
            return
        if not x: raise GrainError(where + ': empty form')
        h = x[0]
        if not isinstance(h, str): raise GrainError('%s: operator must be a name: %s' % (where, unparse(x)))
        if h in params: return            # a definition parameter in head position: checked after expansion
        a = x[1:]
        if h == 'skip':
            if kind != 'act' or a: raise GrainError(where + ': bad skip')
            return
        if h == 'seq':
            if kind != 'act': raise GrainError(where + ': seq outside a term')
            for y in a: self._check(y, 'act', params, where)
            return
        if h == 'if':
            if kind != 'act' or len(a) not in (2, 3): raise GrainError(where + ': if takes a test and 1-2 terms')
            self._check(a[0], 'test', params, where)
            for y in a[1:]: self._check(y, 'act', params, where)
            return
        if h == 'while':
            if kind != 'act' or len(a) != 2: raise GrainError(where + ': while takes a test and a term')
            self._check(a[0], 'test', params, where); self._check(a[1], 'act', params, where)
            return
        k, slots = self.sig(h)
        if k != kind: raise GrainError('%s: %s is a %s used as a %s' % (where, h, k, kind))
        if slots == '*':
            if len(a) < 2: raise GrainError(where + ': and/or need 2+ tests')
            for y in a: self._check(y, 'test', params, where)
            return
        if len(a) != len(slots): raise GrainError('%s: %s takes %d arguments, got %d' % (where, h, len(slots), len(a)))
        for s, y in zip(slots, a):
            if s == 'b': self._check(y, 'test', params, where)
            elif s == 'e': self._check(y, 'expr', params, where)
            elif s == 'p': pass       # a definition argument (term, test or expression): checked after expansion
            elif s == 'S':
                if y not in SCENES and y not in params: raise GrainError('%s: %s needs a scene (in/out), got %s' % (where, h, y))
            elif s == 'A':
                if y not in self.abstractions and y not in params:
                    raise GrainError('%s: %s needs an abstraction of basis %s %s, got %s' % (where, h, self.basis, self.abstractions, y))
            elif s == 't':
                if y not in TABLES and y not in params: raise GrainError('%s: %s needs a table t0..t9, got %s' % (where, h, y))
            elif s == 'R':
                if y not in RCC and y not in params: raise GrainError('%s: rcc needs one of %s, got %s' % (where, RCC, y))
            elif s == 'r':
                if not isinstance(y, str) or y in RESERVED:
                    raise GrainError('%s: set needs a register name, got %s (reserved names: operators, scenes, tables t0-t9, '
                                     'abstractions, rcc relations dc ec po eq tpp ntpp tppi ntppi)' % (where, y))

    def expand(self, x, depth=0):
        if depth > 60: raise GrainError('definition nesting too deep (recursive definition?)')
        if not isinstance(x, list): return x
        h = x[0]
        if isinstance(h, str) and h in self.defs:
            d = self.defs[h]; sub = dict(zip(d['params'], [self.expand(y, depth) for y in x[1:]]))
            return self.expand(_subst(d['body'], sub), depth + 1)
        return [h] + [self.expand(y, depth) for y in x[1:]]

    def length(self):
        return _nodes(self.expanded)

    def stats(self):
        ops, depth = {}, [0]
        def walk(x, d):
            if not isinstance(x, list): return
            h = x[0]; ops[h] = ops.get(h, 0) + 1
            nd = d + 1 if h == 'while' else d
            depth[0] = max(depth[0], nd)
            for y in x[1:]: walk(y, nd)
        walk(self.expanded, 0)
        def kind(h):
            if h in self.extra: return self.extra[h][0]
            if h in SIG: return SIG[h][0]
            if h in self.leaves: return self.leaves[h]['kind']
            return ''
        guards = sorted(h for h in ops if kind(h) == 'test')
        return {'L': self.length(), 'loop_depth': depth[0], 'ops': ops, 'guards': guards,
                'node_actions': {h: ops[h] for h in NODE_ACTIONS if h in ops},
                'pixel_level': {'split_pixels': _count_split1(self.expanded), 'new': ops.get('new', 0)},
                'new_leaves': sorted(self.leaves), 'defs': len(self.defs), 'abstraction': self.abstraction,
                'L_unexpanded_main': _nodes(self.main), 'L_defs': {n: _nodes(d['body']) for n, d in self.defs.items()}}


def _count_split1(x):
    if not isinstance(x, list): return 0
    return (1 if x[0] == 'split' and len(x) == 3 and x[2] == 1 else 0) + sum(_count_split1(y) for y in x[1:])


# ------------------------------------------------------------------ scenes and segmentation
def modal(grid):
    """most common colour; ties go to the colour seen first in row-major order (as collections.Counter.most_common)"""
    c = {}
    for row in grid:
        for v in row: c[v] = c.get(v, 0) + 1
    return max(c, key=lambda k: c[k])        # dict order = first occurrence; max keeps the first of equal counts


def bg_of(grid, A, mode):
    if mode == 'black': return 0
    if mode == 'modal': return modal(grid)
    return modal(grid) if A in ('nbvcg', 'nbhcg') else 0


def segment(grid, A, mode='default'):
    """-> (bg, [pixel dicts]) in row-major order of first pixel"""
    H, W = len(grid), len(grid[0]); bg = bg_of(grid, A, mode); seen = set(); parts = []
    corners = {(0, 0), (0, W - 1), (H - 1, 0), (H - 1, W - 1)}
    for y in range(H):
        for x in range(W):
            if (y, x) in seen: continue
            c = grid[y][x]
            if A in ('nbccg', 'nbvcg', 'nbhcg', 'mcccg') and c == bg: continue
            if A == 'nbvcg': nb = [(-1, 0), (1, 0)]
            elif A == 'nbhcg': nb = [(0, -1), (0, 1)]
            else: nb = N4
            st = [(y, x)]; comp = {}; seen.add((y, x))
            while st:
                a, b = st.pop(); comp[(a, b)] = grid[a][b]
                for dy, dx in nb:
                    p, q = a + dy, b + dx
                    if 0 <= p < H and 0 <= q < W and (p, q) not in seen:
                        v = grid[p][q]
                        ok = (v != bg) if A == 'mcccg' else (v == c)
                        if ok: seen.add((p, q)); st.append((p, q))
            if A == 'ccgbr' and c == bg and corners & set(comp): continue
            parts.append(comp)
    parts.sort(key=lambda d: min(d))
    return bg, parts


_OFF = 1 << 40      # every hashed component shifted positive: CPython's hash(-1) == hash(-2)


class Scene:
    def __init__(self, H, W, bg):
        self.H, self.W, self.bg = H, W, bg
        self.nodes = {}            # id -> {(y, x): colour}
        self.nh = {}               # id -> node hash
        self.hsum = 0

    def clone(self):
        s = Scene(self.H, self.W, self.bg)
        s.nodes = {k: dict(v) for k, v in self.nodes.items()}; s.nh = dict(self.nh); s.hsum = self.hsum
        return s

    def _rehash(self, o):
        if o in self.nh: self.hsum = (self.hsum - self.nh.pop(o)) & 0xFFFFFFFFFFFFFFFF
        if o in self.nodes:
            h = hash((0x2545F491, o + _OFF, frozenset((y + _OFF, x + _OFF, c + _OFF) for (y, x), c in self.nodes[o].items()))) * 0x9E3779B97F4A7C15 & 0xFFFFFFFFFFFFFFFF
            self.nh[o] = h; self.hsum = (self.hsum + h) & 0xFFFFFFFFFFFFFFFF

    def render(self):
        g = [[self.bg] * self.W for _ in range(self.H)]
        for o in sorted(self.nodes):
            for (y, x), c in self.nodes[o].items():
                if 0 <= y < self.H and 0 <= x < self.W: g[y][x] = c
        return g


def box(pix):
    ys = [p[0] for p in pix]; xs = [p[1] for p in pix]
    return min(ys), min(xs), max(ys), max(xs)


def norm(pix, colours=True):
    t, l, _, _ = box(pix)
    return frozenset(((y - t, x - l, c) if colours else (y - t, x - l)) for (y, x), c in pix.items())


def region(pix):
    """cells of the node plus the cells it encloses (4-connectivity, within its box plus a margin)"""
    t, l, b, r = box(pix); P = set(pix)
    free = {(y, x) for y in range(t - 1, b + 2) for x in range(l - 1, r + 2)} - P
    st = [(t - 1, l - 1)]; seen = {(t - 1, l - 1)}
    while st:
        y, x = st.pop()
        for dy, dx in N4:
            q = (y + dy, x + dx)
            if q in free and q not in seen: seen.add(q); st.append(q)
    return P | (free - seen)


# ------------------------------------------------------------------ execution state
class State:
    """State API (also for declared new leaves): S.scene('in'|'out') -> Scene; S.node(scene, o) -> {(y, x): colour}
    (a copy); S.set_node(o, pix) replaces out node o's pixels; S.add_node(pix) -> new id (on top); S.delete(o);
    S.r registers (dict); S.settag(o, v) / S.tags; S.put(t, i, v) / S.tables (write through settag / put). A new act leaf
    may change at most one existing out node and create at most one."""
    def __init__(self, grid, A, mode):
        H, W = len(grid), len(grid[0]); bg, parts = segment(grid, A, mode)
        self.A, self.mode = A, mode
        s = Scene(H, W, bg)
        for i, p in enumerate(parts, 1): s.nodes[i] = dict(p); s._rehash(i)
        self.sc = {'in': s, 'out': s.clone()}
        self.next_id = len(parts) + 1; self.last = -1
        self.r = {}; self.tags = {}; self.tables = {}; self.th = 0     # th: incremental hash of tags and tables

    def scene(self, name):
        if name not in self.sc: raise Abort('no scene %s' % name)
        return self.sc[name]

    def alive(self, name, o):
        return isinstance(o, int) and o in self.scene(name).nodes

    def pix(self, name, o):
        s = self.scene(name)
        if o not in s.nodes: raise Abort('%s has no node %s' % (name, o))
        return s.nodes[o]

    def node(self, name, o): return dict(self.pix(name, o))

    def set_node(self, o, pix):
        s = self.sc['out']
        if o not in s.nodes: raise Abort('out has no node %s' % o)
        if not pix: raise Abort('a node cannot become empty (delete it)')
        for (y, x), c in pix.items():
            if not (isinstance(c, int) and 0 <= c <= 9): raise Abort('colour out of range: %s' % c)
            if abs(y) > 200 or abs(x) > 200: raise Abort('node far off the canvas')
        s.nodes[o] = dict(pix); s._rehash(o)

    def add_node(self, pix):
        if not pix: raise Abort('cannot create an empty node')
        o = self.next_id; self.next_id += 1
        self.sc['out'].nodes[o] = {}; self.set_node(o, pix); self.last = o
        if len(self.sc['out'].nodes) > 3000: raise Abort('more than 3000 nodes')
        return o

    def delete(self, o):
        s = self.sc['out']
        if o not in s.nodes: raise Abort('out has no node %s' % o)
        del s.nodes[o]; s._rehash(o)

    def occupied(self, but=None):
        occ = set()
        for k, p in self.sc['out'].nodes.items():
            if k != but: occ.update(p)
        return occ

    def settag(self, o, v):
        old = self.tags.get(o, 0)
        if old != v: self.th ^= _zh(1, o, old) ^ _zh(1, o, v)
        self.tags[o] = v

    def put(self, t, i, v):
        old = self.tables.get((t, i), 0); ti = TABLES.index(t) + 2
        if old != v: self.th ^= _zh(ti, i, old) ^ _zh(ti, i, v)
        self.tables[(t, i)] = v

    def key(self):
        # registers exactly; nodes, tags and tables by incremental 64-bit hashes (components offset positive)
        s = self.sc['out']
        return (s.hsum, self.th, s.H, s.W, s.bg, frozenset(self.r.items()), self.last, self.next_id)


def _zh(k, i, v):
    return hash((0x51ED27, k + _OFF, i + _OFF, v + _OFF)) * 0x9E3779B97F4A7C15 & 0xFFFFFFFFFFFFFFFF


# ------------------------------------------------------------------ the interpreter
class Run:
    def __init__(self, prog, fuel=FUEL):
        self.p, self.fuel, self.steps, self.max_loop_iters = prog, fuel, 0, 0

    def tick(self, n=1):
        self.steps += n
        if self.steps > self.fuel: raise OutOfFuel('step bound %d reached' % self.fuel)

    def E(self, S, e):
        if isinstance(e, int): return e
        if isinstance(e, str): return S.r.get(e, 0)
        self.tick(); h = e[0]; a = e[1:]
        if h == '+': return self.E(S, a[0]) + self.E(S, a[1])
        if h == '-': return self.E(S, a[0]) - self.E(S, a[1])
        if h == 'first':
            ks = S.scene(a[0]).nodes; return min(ks) if ks else -1
        if h == 'next':
            o = self.E(S, a[1]); ks = [k for k in S.scene(a[0]).nodes if k > o]; return min(ks) if ks else -1
        if h == 'count': return len(S.scene(a[0]).nodes)
        if h == 'last': return S.last
        if h in ('color', 'ncolors', 'size', 'top', 'left', 'bottom', 'right'):
            P = S.pix(a[0], self.E(S, a[1])); self.tick(len(P) // 16)
            if h == 'size': return len(P)
            if h in ('color', 'ncolors'):
                cs = set(P.values()); return len(cs) if h == 'ncolors' else (next(iter(cs)) if len(cs) == 1 else -1)
            return box(P)[('top', 'left', 'bottom', 'right').index(h)]
        if h == 'npix':
            P = S.pix(a[0], self.E(S, a[1])); k = self.E(S, a[2]); return sum(1 for c in P.values() if c == k)
        if h == 'H': return S.scene(a[0]).H
        if h == 'W': return S.scene(a[0]).W
        if h == 'bg': return S.scene(a[0]).bg
        if h == 'tag': return S.tags.get(self.E(S, a[0]), 0)
        if h == 'get': return S.tables.get((a[0], self.E(S, a[1])), 0)
        if h == 'dist':
            P = S.pix(a[0], self.E(S, a[1])); Q = S.pix(a[0], self.E(S, a[2])); self.tick(len(P) * len(Q) // 64)
            return min(max(abs(y - v), abs(x - u)) for (y, x) in P for (v, u) in Q)
        return self._leaf(S, h, a, 'expr')

    def d(self, S, e):
        d = self.E(S, e)
        if not (isinstance(d, int) and 0 <= d < 8): raise Abort('direction out of range: %s' % d)
        return d

    def T(self, S, b):
        self.tick(); h = b[0]; a = b[1:]
        if h == 'true': return True
        if h == 'false': return False
        if h == 'not': return not self.T(S, a[0])
        if h == 'and': return all(self.T(S, y) for y in a)
        if h == 'or': return any(self.T(S, y) for y in a)
        if h in ('=', '!=', '<', '<='):
            u, v = self.E(S, a[0]), self.E(S, a[1])
            return {'=': u == v, '!=': u != v, '<': u < v, '<=': u <= v}[h]
        if h == 'alive': return S.alive(a[0], self.E(S, a[1]))
        if h == 'inbounds':
            s = S.scene('out'); P = S.pix('out', self.E(S, a[0]))
            return all(0 <= y < s.H and 0 <= x < s.W for y, x in P)
        if h == 'free':
            o = self.E(S, a[0]); dy, dx = DIRS[self.d(S, a[1])]; s = S.scene('out'); P = S.pix('out', o)
            occ = S.occupied(but=o); self.tick(len(occ) // 32)
            return all(0 <= y + dy < s.H and 0 <= x + dx < s.W and (y + dy, x + dx) not in occ for y, x in P)
        if h == 'overlaps':
            o = self.E(S, a[0]); P = S.pix('out', o); occ = S.occupied(but=o); self.tick(len(occ) // 32)
            return any(q in occ for q in P)
        if h in REL: return REL[h](self, S, a)
        return bool(self._leaf(S, h, a, 'test'))

    def _leaf(self, S, h, a, kind):
        L = self.p.leaves.get(h)
        if L is None: raise Abort('unknown operator at run time: %s' % h)
        args = [x if (isinstance(x, str) and (x in SCENES or x in TABLES)) else self.E(S, x) for x in a]
        before = S.key(); nodes_before = {k: v for k, v in S.sc['out'].nh.items()}
        out = L['fn'](S, *args)
        self.tick(8)
        if kind != 'act':
            if S.key() != before: raise Abort('leaf %s (a %s) changed the state' % (h, kind))
            return out
        after = S.sc['out'].nh
        changed = sum(1 for k in nodes_before if after.get(k) != nodes_before[k])
        created = sum(1 for k in after if k not in nodes_before)
        if changed > 1 or created > 1:
            raise Abort('leaf %s changed %d nodes and created %d (one node, one step)' % (h, changed, created))
        return out

    def do(self, S, t):
        self.tick(); h = t[0]; a = t[1:]
        if h == 'skip': return
        if h == 'seq':
            for y in a: self.do(S, y)
            return
        if h == 'if':
            if self.T(S, a[0]): self.do(S, a[1])
            elif len(a) == 3: self.do(S, a[2])
            return
        if h == 'while':
            seen = set(); n = 0
            while self.T(S, a[0]):
                k = S.key()
                if k in seen: raise NonTerminating('state repeats at a while head: %s' % unparse(a[0])[:80])
                seen.add(k); n += 1
                self.do(S, a[1])
            self.max_loop_iters = max(self.max_loop_iters, n)
            return
        if h == 'set': S.r[a[0]] = self.E(S, a[1]); return
        if h == 'settag': S.settag(self.E(S, a[0]), self.E(S, a[1])); return
        if h == 'put': S.put(a[0], self.E(S, a[1]), self.E(S, a[2])); return
        if h in ACT: return ACT[h](self, S, a)
        self._leaf(S, h, a, 'act')


# ------------------------------------------------------------------ node actions
def _o(run, S, e):
    o = run.E(S, e)
    if not S.alive('out', o): raise Abort('out has no node %s' % o)
    return o


def a_recolor(run, S, a):
    o = _o(run, S, a[0]); k = run.E(S, a[1]); P = S.pix('out', o); run.tick(len(P) // 16)
    S.set_node(o, {p: k for p in P})


def a_move(run, S, a):
    o = _o(run, S, a[0]); dy, dx = DIRS[run.d(S, a[1])]; P = S.pix('out', o); run.tick(len(P) // 16)
    S.set_node(o, {(y + dy, x + dx): c for (y, x), c in P.items()})


def a_extend(run, S, a):
    o = _o(run, S, a[0]); dy, dx = DIRS[run.d(S, a[1])]; P = S.node('out', o); run.tick(len(P) // 16)
    add = {(y + dy, x + dx): c for (y, x), c in P.items() if (y + dy, x + dx) not in P}
    P.update(add); S.set_node(o, P)


def a_shrink(run, S, a):
    o = _o(run, S, a[0]); d = run.d(S, a[1]); P = S.pix('out', o)
    if d > 3: raise Abort('shrink takes a side 0..3')
    t, l, b, r = box(P); edge = (t, r, b, l)[d]; k = 0 if d in (0, 2) else 1
    keep = {q: c for q, c in P.items() if q[k] != edge}
    if not keep: raise Abort('shrink would leave the node empty (delete it)')
    S.set_node(o, keep)


def a_border(run, S, a):
    o = _o(run, S, a[0]); k = run.E(S, a[1]); P = S.pix('out', o); s = S.scene('out'); occ = S.occupied()
    ring = {(y + dy, x + dx) for (y, x) in P for dy, dx in DIRS} - occ
    ring = {p for p in ring if 0 <= p[0] < s.H and 0 <= p[1] < s.W}; run.tick(len(ring) // 16 + len(occ) // 32)
    if ring: S.add_node({p: k for p in ring})
    else: S.last = -1


def a_fillrect(run, S, a):
    o = _o(run, S, a[0]); k = run.E(S, a[1]); P = S.pix('out', o); s = S.scene('out'); occ = S.occupied()
    t, l, b, r = box(P)
    cells = {(y, x) for y in range(t, b + 1) for x in range(l, r + 1) if (y, x) not in occ and 0 <= y < s.H and 0 <= x < s.W}
    run.tick(len(cells) // 16 + len(occ) // 32)
    if cells: S.add_node({p: k for p in cells})
    else: S.last = -1


def a_hollow(run, S, a):
    o = _o(run, S, a[0]); P = S.pix('out', o); t, l, b, r = box(P)
    keep = {p: c for p, c in P.items() if p[0] in (t, b) or p[1] in (l, r)}
    S.set_node(o, keep)


def a_flip(run, S, a):
    o = _o(run, S, a[0]); ax = run.E(S, a[1]); P = S.pix('out', o); t, l, b, r = box(P); h, w = b - t + 1, r - l + 1
    if ax not in (0, 1, 2, 3): raise Abort('flip axis must be 0..3')
    f = {0: lambda y, x: (y, w - 1 - x), 1: lambda y, x: (h - 1 - y, x), 2: lambda y, x: (x, y),
         3: lambda y, x: (w - 1 - x, h - 1 - y)}[ax]
    S.set_node(o, {(t + f(y - t, x - l)[0], l + f(y - t, x - l)[1]): c for (y, x), c in P.items()})


def a_rotate(run, S, a):
    o = _o(run, S, a[0]); P = S.pix('out', o); t, l, b, r = box(P); h = b - t + 1
    S.set_node(o, {(t + (x - l), l + (h - 1 - (y - t))): c for (y, x), c in P.items()})


def a_copy(run, S, a):
    o = _o(run, S, a[0]); S.add_node(S.node('out', o))


def a_delete(run, S, a):
    S.delete(_o(run, S, a[0]))


def a_merge(run, S, a):
    o = _o(run, S, a[0]); p = _o(run, S, a[1])
    if o == p: raise Abort('merge of a node with itself')
    P = S.node('out', o); P.update(S.pix('out', p)); S.set_node(o, P); S.delete(p)


def a_split(run, S, a):
    o = _o(run, S, a[0]); m = run.E(S, a[1]); P = S.pix('out', o)
    if m == 1: parts = [{p: c} for p, c in sorted(P.items())]
    elif m == 0:
        seen = set(); parts = []
        for p in sorted(P):
            if p in seen: continue
            c = P[p]; st = [p]; seen.add(p); comp = {}
            while st:
                y, x = st.pop(); comp[(y, x)] = c
                for dy, dx in N4:
                    q = (y + dy, x + dx)
                    if q in P and q not in seen and P[q] == c: seen.add(q); st.append(q)
            parts.append(comp)
        parts.sort(key=lambda d: min(d))
    else: raise Abort('split mode must be 0 or 1')
    run.tick(len(P) // 8)
    S.set_node(o, parts[0]); S.last = -1
    for q in parts[1:]: S.add_node(q)


def a_new(run, S, a):
    k = run.E(S, a[0]); S.add_node({(0, 0): k})


def a_canvas(run, S, a):
    h, w, k = run.E(S, a[0]), run.E(S, a[1]), run.E(S, a[2])
    if not (1 <= h <= 60 and 1 <= w <= 60): raise Abort('canvas size out of range: %s x %s' % (h, w))
    if not (0 <= k <= 9): raise Abort('canvas colour out of range')
    s = S.sc['out']; s.H, s.W, s.bg = h, w, k


def a_segment(run, S, a):
    A = a[0]; g = S.sc['out'].render(); bg, parts = segment(g, A, S.mode); run.tick(len(g) * len(g[0]) // 8)
    s = Scene(len(g), len(g[0]), bg)          # the rendering is unchanged: cells of colour bg that are no node are canvas
    base = S.next_id
    for i, p in enumerate(parts): s.nodes[base + i] = dict(p); s._rehash(base + i)
    S.next_id = base + len(parts); S.sc['out'] = s; S.last = -1


ACT = {'recolor': a_recolor, 'move': a_move, 'extend': a_extend, 'shrink': a_shrink, 'border': a_border, 'fillrect': a_fillrect,
       'hollow': a_hollow, 'flip': a_flip, 'rotate': a_rotate, 'copy': a_copy, 'delete': a_delete, 'merge': a_merge,
       'split': a_split, 'new': a_new, 'canvas': a_canvas, 'segment': a_segment}


# ------------------------------------------------------------------ O0 relations between nodes (both in scene S)
def _two(run, S, a):
    return S.pix(a[0], run.E(S, a[1])), S.pix(a[0], run.E(S, a[2])), run.E(S, a[1]), run.E(S, a[2])


def r_rcc(run, S, a):
    P, Q, o, p = _two(run, S, a); rel = a[3]; run.tick((len(P) + len(Q)) // 8)
    X, Y = region(P), region(Q)
    if rel in ('tppi', 'ntppi'): X, Y = Y, X; rel = rel[:-1]
    if rel == 'eq': return X == Y
    inter = X & Y
    if rel == 'po': return bool(inter) and not X <= Y and not Y <= X
    if rel in ('dc', 'ec'):
        if inter: return False
        touch = any((y + dy, x + dx) in Y for (y, x) in X for dy, dx in N4)
        return touch if rel == 'ec' else not touch
    if rel in ('tpp', 'ntpp'):
        if not (X < Y): return False
        tang = any((y + dy, x + dx) not in Y for (y, x) in X for dy, dx in N4)
        return tang if rel == 'tpp' else not tang
    raise Abort('bad rcc relation')


def r_dir_rel(run, S, a):
    P, Q, o, p = _two(run, S, a); d = run.d(S, a[3]); t1, l1, b1, r1 = box(P); t2, l2, b2, r2 = box(Q)
    above, below, leftof, rightof = b1 < t2, t1 > b2, r1 < l2, l1 > r2
    rows_ov = not above and not below; cols_ov = not leftof and not rightof
    return [above and cols_ov, rightof and rows_ov, below and cols_ov, leftof and rows_ov,
            above and rightof, below and rightof, below and leftof, above and leftof][d]


def r_adjacent(run, S, a):
    P, Q, o, p = _two(run, S, a); d = run.d(S, a[3]); t1, l1, b1, r1 = box(P); t2, l2, b2, r2 = box(Q)
    rows_ov = t1 <= b2 and t2 <= b1; cols_ov = l1 <= r2 and l2 <= r1
    if d == 0: return b1 + 1 == t2 and cols_ov
    if d == 2: return t1 - 1 == b2 and cols_ov
    if d == 1: return l1 - 1 == r2 and rows_ov
    if d == 3: return r1 + 1 == l2 and rows_ov
    raise Abort('adjacent takes a cardinal direction 0..3')


def r_aligned(run, S, a):
    P, Q, o, p = _two(run, S, a); ax = run.E(S, a[3]); t1, l1, b1, r1 = box(P); t2, l2, b2, r2 = box(Q)
    if o == p: return False
    return (t1 <= b2 and t2 <= b1) if ax == 0 else (l1 <= r2 and l2 <= r1)


def r_allen(run, S, a):
    P, Q, o, p = _two(run, S, a); ax = run.E(S, a[3]); rel = run.E(S, a[4])
    t1, l1, b1, r1 = box(P); t2, l2, b2, r2 = box(Q)
    x0, x1, y0, y1 = (t1, b1, t2, b2) if ax == 0 else (l1, r1, l2, r2)
    if o == p: return False
    return [x1 + 1 < y0, x1 + 1 == y0, x0 < y0 <= x1 < y1, y0 < x0 and x1 < y1, x0 == y0 and x1 < y1,
            x1 == y1 and x0 > y0, x0 == y0 and x1 == y1][rel]


def _line_cells(a, b):
    (y1, x1), (y2, x2) = a, b; n = max(abs(y2 - y1), abs(x2 - x1))
    sy = (y2 > y1) - (y2 < y1); sx = (x2 > x1) - (x2 < x1)
    return [(y1 + k * sy, x1 + k * sx) for k in range(1, n)]


def _on_axis(a, b, ax):
    if ax == 0: return a[0] == b[0]
    if ax == 1: return a[1] == b[1]
    return abs(a[0] - b[0]) == abs(a[1] - b[1]) and a != b


def r_between(run, S, a):
    o, p, q = run.E(S, a[1]), run.E(S, a[2]), run.E(S, a[3]); ax = run.E(S, a[4])
    X, P, Q = S.pix(a[0], o), S.pix(a[0], p), S.pix(a[0], q)
    if len({o, p, q}) < 3: return False
    occ = set()
    for k, v in S.scene(a[0]).nodes.items():
        if k not in (o, p, q): occ.update(v)
    run.tick(len(P) * len(Q) // 16)
    for u in P:
        for v in Q:
            if not _on_axis(u, v, ax): continue
            mid = _line_cells(u, v)
            if any(c in X for c in mid) and not any(c in occ or c in P or c in Q for c in mid): return True
    return False


def r_sees(run, S, a):
    P, Q, o, p = _two(run, S, a); ax = run.E(S, a[3])
    if o == p: return False
    occ = set()
    for k, v in S.scene(a[0]).nodes.items():
        if k not in (o, p): occ.update(v)
    run.tick(len(P) * len(Q) // 16)
    for u in P:
        for v in Q:
            if (ax == 0 and u[0] == v[0]) or (ax == 1 and u[1] == v[1]):
                if not any(c in occ or c in P or c in Q for c in _line_cells(u, v)): return True
    return False


def r_on_ray(run, S, a):
    """(on_ray S o p d): a ray cast from p's face in direction d, over empty cells, first meets node o"""
    P, Q, o, p = _two(run, S, a); dy, dx = DIRS[run.d(S, a[3])]; s = S.scene(a[0])
    if o == p: return False
    owner = {}
    for k, v in s.nodes.items():
        if k != p:
            for c in v: owner[c] = k
    for (y, x) in Q:
        if (y + dy, x + dx) in Q: continue
        cy, cx = y + dy, x + dx
        while 0 <= cy < s.H and 0 <= cx < s.W:
            run.tick()
            if (cy, cx) in owner:
                if owner[(cy, cx)] == o: return True
                break
            cy, cx = cy + dy, cx + dx
    return False


def r_nearest(run, S, a):
    P, Q, o, p = _two(run, S, a)
    if o == p: return False
    dist = lambda A, B: min(max(abs(y - v), abs(x - u)) for (y, x) in A for (v, u) in B)
    ds = {}
    for k, v in S.scene(a[0]).nodes.items():
        if k != o: ds[k] = dist(P, v); run.tick(len(P) * len(v) // 64)
    return ds.get(p) == min(ds.values())


_REF = {0: lambda r, c: (-r, c), 1: lambda r, c: (r, -c), 2: lambda r, c: (c, r), 3: lambda r, c: (-c, -r)}
_ROT = {1: lambda r, c: (c, -r), 2: lambda r, c: (-r, -c), 3: lambda r, c: (-c, r)}


def _tnorm(P, f):
    Q = {f(y, x): c for (y, x), c in P.items()}
    return norm(Q)


def r_translate_of(run, S, a):
    P, Q, o, p = _two(run, S, a); return o != p and norm(P) == norm(Q)


def r_reflection_of(run, S, a):
    P, Q, o, p = _two(run, S, a); ax = run.E(S, a[3])
    if ax not in _REF: raise Abort('reflection axis 0..3')
    return o != p and norm(P) == _tnorm(Q, _REF[ax])


def r_rotation_of(run, S, a):
    P, Q, o, p = _two(run, S, a); k = run.E(S, a[3])
    if k not in _ROT: raise Abort('rotation 1..3')
    return o != p and norm(P) == _tnorm(Q, _ROT[k])


def r_same_form(run, S, a):
    P, Q, o, p = _two(run, S, a); return o != p and norm(P, False) == norm(Q, False)


def r_mirror_cell(run, S, a):
    P, Q, o, p = _two(run, S, a); ax = run.E(S, a[3]); s = S.scene(a[0])
    if o == p: return False
    f = (lambda y, x: (s.H - 1 - y, x)) if ax == 0 else (lambda y, x: (y, s.W - 1 - x))
    return all(f(y, x) in Q for (y, x) in P)


def r_period(run, S, a):
    o, p = run.E(S, a[1]), run.E(S, a[2]); P, Q = S.pix(a[0], o), S.pix(a[0], p); ax = run.E(S, a[3]); k = run.E(S, a[4])
    if o == p: return False
    for (y, x) in Q:
        for s in (k, -k):
            c = (y, x + s) if ax == 0 else (y + s, x)
            if c not in Q and c in P: return True
    return False


REL = {'rcc': r_rcc, 'dir_rel': r_dir_rel, 'adjacent': r_adjacent, 'aligned': r_aligned, 'allen': r_allen,
       'between': r_between, 'sees': r_sees, 'on_ray': r_on_ray, 'nearest': r_nearest, 'translate_of': r_translate_of,
       'reflection_of': r_reflection_of, 'rotation_of': r_rotation_of, 'same_form': r_same_form,
       'mirror_cell': r_mirror_cell, 'period': r_period}


def execute(prog, grid, fuel=FUEL):
    """-> (output grid or None, info)"""
    try:
        S = State(grid, prog.abstraction, prog.bgmode)
    except Exception as e:
        return None, {'steps': 0, 'status': 'error', 'detail': 'segmentation: %s' % e}
    R = Run(prog, fuel)
    try:
        R.do(S, prog.expanded)
        return S.sc['out'].render(), {'steps': R.steps, 'status': 'ok', 'max_loop_iters': R.max_loop_iters}
    except NonTerminating as e: return None, {'steps': R.steps, 'status': 'nonterminating', 'detail': str(e)}
    except OutOfFuel as e: return None, {'steps': R.steps, 'status': 'out_of_fuel', 'detail': str(e)}
    except Abort as e: return None, {'steps': R.steps, 'status': 'abort', 'detail': str(e)}
    except RecursionError: return None, {'steps': R.steps, 'status': 'abort', 'detail': 'recursion depth'}
    except Exception as e: return None, {'steps': R.steps, 'status': 'error', 'detail': '%s: %s' % (type(e).__name__, e)}

"""ARCGraph GOL extension (DSL side of the barrier): GOL's scenes and primitive operations, on ARCGraph.

A GOL scene is one ARCGraph plus a canvas (height, width, background colour). The interpreter (the container) holds
only handles: integers given to the reading's nodes by film layer, then first subnode in row-major order; a created
node gets the next free handle and is painted above every lower handle. Every primitive is a method here, called with
handles and values. It reads and writes the nodes' subnodes and colours in the ARCGraph (G.graph.nodes[key]: nodes,
color, size), with ARCGraph's own methods where their semantics are GRAIN-1's (move_node, update_color, remove_node,
_node_bbox, get_shape). Nothing that goes back to the container is a subnode: an act returns the handles it created,
a test a boolean, an expression an integer. The tracing support (snapshot, effect, attributes, relations, placement
in other readings) returns handles, numbers and typed labels.

The semantics are GRAIN-1's (room15/grain/grain1.py, at the paper pin), so plans written against GRAIN-1 run unchanged;
parity is checked on every traced demonstration (cx2/container/gol_parity.py). The scene keeps a write-through mirror
of each node's subnodes (for speed) and an incremental hash (for the interpreter's loop check); both live here.
"""
import copy

DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1), (-1, 1), (1, 1), (1, -1), (-1, -1)]   # N E S W NE SE SW NW
N4 = DIRS[:4]
RCC = ('dc', 'ec', 'po', 'eq', 'tpp', 'ntpp', 'tppi', 'ntppi')
_OFF = 1 << 40


class Refused(Exception):
    """the operation does not apply to these arguments (the interpreter aborts the run)"""


def _arcgraph():
    from ARCGraph import ARCGraph
    return ARCGraph


def _directions():
    from utils import Direction as D
    return [D.UP, D.RIGHT, D.DOWN, D.LEFT, D.UP_RIGHT, D.DOWN_RIGHT, D.DOWN_LEFT, D.UP_LEFT]


def cells(G, n):
    d = G.graph.nodes[n]
    pts = [tuple(map(int, p)) for p in d['nodes']]
    col = d['color']
    cols = [int(c) for c in col] if isinstance(col, (list, tuple)) else [int(col)] * len(pts)
    return dict(zip(pts, cols))


def box(P):
    ys = [p[0] for p in P]; xs = [p[1] for p in P]
    return min(ys), min(xs), max(ys), max(xs)


def norm(P, colours=True):
    t, l, _, _ = box(P)
    return frozenset(((y - t, x - l, c) if colours else (y - t, x - l)) for (y, x), c in P.items())


def region(P):
    t, l, b, r = box(P); S = set(P)
    free = {(y, x) for y in range(t - 1, b + 2) for x in range(l - 1, r + 2)} - S
    st = [(t - 1, l - 1)]; seen = {(t - 1, l - 1)}
    while st:
        y, x = st.pop()
        for dy, dx in N4:
            q = (y + dy, x + dx)
            if q in free and q not in seen: seen.add(q); st.append(q)
    return S | (free - seen)


def modal(grid):
    c = {}
    for row in grid:
        for v in row: c[v] = c.get(v, 0) + 1
    return max(c, key=lambda k: c[k])


def bg_of(grid, A, mode):
    if mode == 'black': return 0
    if mode == 'modal': return modal(grid)
    return modal(grid) if A in ('nbvcg', 'nbhcg') else 0


def _nb(t):
    return t


class GolScene:
    """one GOL scene over an ARCGraph. ids: the handle counter shared by a state's scenes (a one-element list)."""

    def __init__(self, G, H, W, bg, ids):
        self.G, self.H, self.W, self.bg, self.ids = G, H, W, bg, ids
        self.key, self.mir, self.nh, self.hsum = {}, {}, {}, 0

    # ---------------------------------------------------------------- construction
    @classmethod
    def of_graph(cls, G, H, W, bg, ids):
        """the scene of an ARCGraph reading: handles by film layer, then first subnode (row-major)"""
        s = cls(G, H, W, bg, ids)
        order = sorted(G.graph.nodes, key=lambda n: (G.graph.nodes[n].get('z_order', 0),
                                                     min(tuple(map(int, p)) for p in G.graph.nodes[n]['nodes'])))
        for n in order:
            h = ids[0]; ids[0] += 1
            s.key[h] = n; s.mir[h] = cells(G, n); s._rehash(h)
        return s

    def clone(self):
        s = GolScene.__new__(GolScene)
        s.G = copy.copy(self.G); s.G.graph = self.G.graph.copy()     # node data dicts copied; lists are replaced on write
        s.H, s.W, s.bg, s.ids = self.H, self.W, self.bg, self.ids
        s.key = dict(self.key); s.mir = {h: dict(p) for h, p in self.mir.items()}; s.nh = dict(self.nh); s.hsum = self.hsum
        return s

    # ---------------------------------------------------------------- handles
    def handles(self): return self.mir.keys()
    def alive(self, h): return isinstance(h, int) and h in self.mir

    def _p(self, h):
        if h not in self.mir: raise Refused('no node %s' % h)
        return self.mir[h]

    def _rehash(self, h):
        if h in self.nh: self.hsum = (self.hsum - self.nh.pop(h)) & 0xFFFFFFFFFFFFFFFF
        if h in self.mir:
            v = hash((0x2545F491, h + _OFF, frozenset((y + _OFF, x + _OFF, c + _OFF) for (y, x), c in self.mir[h].items()))) \
                * 0x9E3779B97F4A7C15 & 0xFFFFFFFFFFFFFFFF
            self.nh[h] = v; self.hsum = (self.hsum + v) & 0xFFFFFFFFFFFFFFFF

    def _check(self, P):
        if not P: raise Refused('a node cannot become empty (delete it)')
        for (y, x), c in P.items():
            if not (isinstance(c, int) and 0 <= c <= 9): raise Refused('colour out of range: %s' % c)
            if abs(y) > 200 or abs(x) > 200: raise Refused('node far off the canvas')

    def _data(self, P):
        pts = sorted(P); cols = [P[p] for p in pts]
        multi = getattr(self.G, 'is_multicolor', False) or len(set(cols)) > 1
        return {'nodes': pts, 'color': cols if multi else cols[0], 'size': len(pts)}

    def _write(self, h, P):
        self._check(P)
        self.G.graph.nodes[self.key[h]].update(self._data(P))
        self.mir[h] = dict(P); self._rehash(h)

    def _sync(self, h):
        """after a native ARCGraph method changed node h: read it back"""
        P = cells(self.G, self.key[h]); self._check(P); self.mir[h] = P; self._rehash(h)

    def _add(self, P):
        self._check(P)
        h = self.ids[0]; self.ids[0] += 1
        k = ('gol', h)
        self.G.graph.add_node(k, z_order=0, **self._data(P))
        self.key[h] = k; self.mir[h] = dict(P); self._rehash(h)
        if len(self.mir) > 3000: raise Refused('more than 3000 nodes')
        return h

    def _delete(self, h):
        self._p(h)
        self.G.remove_node(self.key.pop(h))            # ARCGraph.remove_node
        del self.mir[h]; self._rehash(h)

    def occupied(self, but=None):
        occ = set()
        for k, p in self.mir.items():
            if k != but: occ.update(p)
        return occ

    def render(self):
        g = [[self.bg] * self.W for _ in range(self.H)]
        for h in sorted(self.mir):
            for (y, x), c in self.mir[h].items():
                if 0 <= y < self.H and 0 <= x < self.W: g[y][x] = c
        return g

    # ---------------------------------------------------------------- expressions
    def attr(self, name, h, tick):
        P = self._p(h); tick(len(P) // 16)
        if name == 'size': return len(P)
        if name in ('color', 'ncolors'):
            cs = set(P.values()); return len(cs) if name == 'ncolors' else (next(iter(cs)) if len(cs) == 1 else -1)
        t, b, l, r = _arcgraph()._node_bbox(self.G, self.key[h])          # ARCGraph's box: rows, then columns
        return {'top': t, 'left': l, 'bottom': b, 'right': r}[name]

    def npix(self, h, k): return sum(1 for c in self._p(h).values() if c == k)

    def dist(self, o, p, tick):
        P, Q = self._p(o), self._p(p); tick(len(P) * len(Q) // 64)
        return min(max(abs(y - v), abs(x - u)) for (y, x) in P for (v, u) in Q)

    # ---------------------------------------------------------------- canvas tests
    def inbounds(self, h): return all(0 <= y < self.H and 0 <= x < self.W for y, x in self._p(h))

    def free(self, h, d, tick):
        dy, dx = DIRS[d]; P = self._p(h); occ = self.occupied(but=h); tick(len(occ) // 32)
        return all(0 <= y + dy < self.H and 0 <= x + dx < self.W and (y + dy, x + dx) not in occ for y, x in P)

    def overlaps(self, h, tick):
        P = self._p(h); occ = self.occupied(but=h); tick(len(occ) // 32)
        return any(q in occ for q in P)

    # ---------------------------------------------------------------- one-node acts: -> handles created
    def recolor(self, o, k, tick):
        P = self._p(o); tick(len(P) // 16)
        self._check({p: k for p in P})
        self.G.update_color(self.key[o], k)            # ARCGraph.update_color
        self._sync(o); return []

    def move(self, o, d, tick):
        P = self._p(o); tick(len(P) // 16); dy, dx = DIRS[d]
        self._check({(y + dy, x + dx): c for (y, x), c in P.items()})
        self.G.move_node(self.key[o], _directions()[d], 1)      # ARCGraph.move_node, one step
        self._sync(o); return []

    def extend(self, o, d, tick):
        P = dict(self._p(o)); tick(len(P) // 16); dy, dx = DIRS[d]
        P.update({(y + dy, x + dx): c for (y, x), c in P.items() if (y + dy, x + dx) not in P})
        self._write(o, P); return []

    def shrink(self, o, d, tick):
        P = self._p(o)
        if d > 3: raise Refused('shrink takes a side 0..3')
        t, l, b, r = box(P); edge = (t, r, b, l)[d]; k = 0 if d in (0, 2) else 1
        keep = {q: c for q, c in P.items() if q[k] != edge}
        if not keep: raise Refused('shrink would leave the node empty (delete it)')
        self._write(o, keep); return []

    def border(self, o, k, tick):
        P = self._p(o); occ = self.occupied()
        ring = {(y + dy, x + dx) for (y, x) in P for dy, dx in DIRS} - occ
        ring = {p for p in ring if 0 <= p[0] < self.H and 0 <= p[1] < self.W}; tick(len(ring) // 16 + len(occ) // 32)
        return [self._add({p: k for p in ring})] if ring else []

    def fillrect(self, o, k, tick):
        P = self._p(o); occ = self.occupied(); t, l, b, r = box(P)
        cs = {(y, x) for y in range(t, b + 1) for x in range(l, r + 1) if (y, x) not in occ and 0 <= y < self.H and 0 <= x < self.W}
        tick(len(cs) // 16 + len(occ) // 32)
        return [self._add({p: k for p in cs})] if cs else []

    def hollow(self, o, tick):
        P = self._p(o); t, l, b, r = box(P)
        self._write(o, {p: c for p, c in P.items() if p[0] in (t, b) or p[1] in (l, r)}); return []

    def flip(self, o, ax, tick):
        P = self._p(o); t, l, b, r = box(P); h, w = b - t + 1, r - l + 1
        if ax not in (0, 1, 2, 3): raise Refused('flip axis must be 0..3')
        f = {0: lambda y, x: (y, w - 1 - x), 1: lambda y, x: (h - 1 - y, x), 2: lambda y, x: (x, y),
             3: lambda y, x: (w - 1 - x, h - 1 - y)}[ax]
        self._write(o, {(t + f(y - t, x - l)[0], l + f(y - t, x - l)[1]): c for (y, x), c in P.items()}); return []

    def rotate(self, o, tick):
        P = self._p(o); t, l, b, r = box(P); h = b - t + 1
        self._write(o, {(t + (x - l), l + (h - 1 - (y - t))): c for (y, x), c in P.items()}); return []

    def copy(self, o, tick):
        return [self._add(dict(self._p(o)))]

    def delete(self, o, tick):
        self._delete(o); return []

    def merge(self, o, p, tick):
        if o == p: raise Refused('merge of a node with itself')
        P = dict(self._p(o)); P.update(self._p(p)); self._write(o, P); self._delete(p); return []

    def split(self, o, m, tick):
        P = self._p(o)
        if m == 1: parts = [{q: c} for q, c in sorted(P.items())]
        elif m == 0:
            seen = set(); parts = []
            for q in sorted(P):
                if q in seen: continue
                c = P[q]; st = [q]; seen.add(q); comp = {}
                while st:
                    y, x = st.pop(); comp[(y, x)] = c
                    for dy, dx in N4:
                        v = (y + dy, x + dx)
                        if v in P and v not in seen and P[v] == c: seen.add(v); st.append(v)
                parts.append(comp)
            parts.sort(key=lambda d: min(d))
        else: raise Refused('split mode must be 0 or 1')
        tick(len(P) // 8)
        self._write(o, parts[0])
        return [self._add(q) for q in parts[1:]]

    def new(self, k, tick):
        return [self._add({(0, 0): k})]

    def canvas(self, h, w, k):
        if not (1 <= h <= 60 and 1 <= w <= 60): raise Refused('canvas size out of range: %s x %s' % (h, w))
        if not (0 <= k <= 9): raise Refused('canvas colour out of range')
        self.H, self.W, self.bg = h, w, k

    def segment(self, A, mode, tick):
        """a new scene: this scene's rendering read again by ARCGraph under abstraction A"""
        g = self.render(); tick(len(g) * len(g[0]) // 8)
        bg = bg_of(g, A, mode)
        G = reading_of_grid(g, A, bg)
        s = GolScene(G, len(g), len(g[0]), bg, self.ids)
        order = sorted(G.graph.nodes, key=lambda n: min(tuple(map(int, p)) for p in G.graph.nodes[n]['nodes']))
        for n in order:
            h = self.ids[0]; self.ids[0] += 1
            s.key[h] = n; s.mir[h] = cells(G, n); s._rehash(h)
        return s

    # ---------------------------------------------------------------- relations (GRAIN-1's O0)
    def _two(self, o, p): return self._p(o), self._p(p)

    def rcc(self, o, p, rel, tick):
        P, Q = self._two(o, p); tick((len(P) + len(Q)) // 8)
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
        raise Refused('bad rcc relation')

    def dir_rel(self, o, p, d, tick):
        P, Q = self._two(o, p); t1, l1, b1, r1 = box(P); t2, l2, b2, r2 = box(Q)
        above, below, leftof, rightof = b1 < t2, t1 > b2, r1 < l2, l1 > r2
        rows_ov = not above and not below; cols_ov = not leftof and not rightof
        return [above and cols_ov, rightof and rows_ov, below and cols_ov, leftof and rows_ov,
                above and rightof, below and rightof, below and leftof, above and leftof][d]

    def adjacent(self, o, p, d, tick):
        P, Q = self._two(o, p); t1, l1, b1, r1 = box(P); t2, l2, b2, r2 = box(Q)
        rows_ov = t1 <= b2 and t2 <= b1; cols_ov = l1 <= r2 and l2 <= r1
        if d == 0: return b1 + 1 == t2 and cols_ov
        if d == 2: return t1 - 1 == b2 and cols_ov
        if d == 1: return l1 - 1 == r2 and rows_ov
        if d == 3: return r1 + 1 == l2 and rows_ov
        raise Refused('adjacent takes a cardinal direction 0..3')

    def aligned(self, o, p, ax, tick):
        P, Q = self._two(o, p); t1, l1, b1, r1 = box(P); t2, l2, b2, r2 = box(Q)
        if o == p: return False
        return (t1 <= b2 and t2 <= b1) if ax == 0 else (l1 <= r2 and l2 <= r1)

    def allen(self, o, p, ax, rel, tick):
        P, Q = self._two(o, p); t1, l1, b1, r1 = box(P); t2, l2, b2, r2 = box(Q)
        x0, x1, y0, y1 = (t1, b1, t2, b2) if ax == 0 else (l1, r1, l2, r2)
        if o == p: return False
        return [x1 + 1 < y0, x1 + 1 == y0, x0 < y0 <= x1 < y1, y0 < x0 and x1 < y1, x0 == y0 and x1 < y1,
                x1 == y1 and x0 > y0, x0 == y0 and x1 == y1][rel]

    @staticmethod
    def _line(a, b):
        (y1, x1), (y2, x2) = a, b; n = max(abs(y2 - y1), abs(x2 - x1))
        sy = (y2 > y1) - (y2 < y1); sx = (x2 > x1) - (x2 < x1)
        return [(y1 + k * sy, x1 + k * sx) for k in range(1, n)]

    @staticmethod
    def _on_axis(a, b, ax):
        if ax == 0: return a[0] == b[0]
        if ax == 1: return a[1] == b[1]
        return abs(a[0] - b[0]) == abs(a[1] - b[1]) and a != b

    def between(self, o, p, q, ax, tick):
        X, P, Q = self._p(o), self._p(p), self._p(q)
        if len({o, p, q}) < 3: return False
        occ = set()
        for k, v in self.mir.items():
            if k not in (o, p, q): occ.update(v)
        tick(len(P) * len(Q) // 16)
        for u in P:
            for v in Q:
                if not self._on_axis(u, v, ax): continue
                mid = self._line(u, v)
                if any(c in X for c in mid) and not any(c in occ or c in P or c in Q for c in mid): return True
        return False

    def sees(self, o, p, ax, tick):
        P, Q = self._two(o, p)
        if o == p: return False
        occ = set()
        for k, v in self.mir.items():
            if k not in (o, p): occ.update(v)
        tick(len(P) * len(Q) // 16)
        for u in P:
            for v in Q:
                if (ax == 0 and u[0] == v[0]) or (ax == 1 and u[1] == v[1]):
                    if not any(c in occ or c in P or c in Q for c in self._line(u, v)): return True
        return False

    def on_ray(self, o, p, d, tick):
        P, Q = self._two(o, p); dy, dx = DIRS[d]
        if o == p: return False
        owner = {}
        for k, v in self.mir.items():
            if k != p:
                for c in v: owner[c] = k
        for (y, x) in Q:
            if (y + dy, x + dx) in Q: continue
            cy, cx = y + dy, x + dx
            while 0 <= cy < self.H and 0 <= cx < self.W:
                tick(1)
                if (cy, cx) in owner:
                    if owner[(cy, cx)] == o: return True
                    break
                cy, cx = cy + dy, cx + dx
        return False

    def nearest(self, o, p, tick):
        P, Q = self._two(o, p)
        if o == p: return False
        dist = lambda A, B: min(max(abs(y - v), abs(x - u)) for (y, x) in A for (v, u) in B)
        ds = {}
        for k, v in self.mir.items():
            if k != o: ds[k] = dist(P, v); tick(len(P) * len(v) // 64)
        return ds.get(p) == min(ds.values())

    _REF = {0: lambda r, c: (-r, c), 1: lambda r, c: (r, -c), 2: lambda r, c: (c, r), 3: lambda r, c: (-c, -r)}
    _ROT = {1: lambda r, c: (c, -r), 2: lambda r, c: (-r, -c), 3: lambda r, c: (-c, r)}

    @staticmethod
    def _tnorm(P, f): return norm({f(y, x): c for (y, x), c in P.items()})

    def translate_of(self, o, p, tick):
        P, Q = self._two(o, p); return o != p and norm(P) == norm(Q)

    def reflection_of(self, o, p, ax, tick):
        P, Q = self._two(o, p)
        if ax not in self._REF: raise Refused('reflection axis 0..3')
        return o != p and norm(P) == self._tnorm(Q, self._REF[ax])

    def rotation_of(self, o, p, k, tick):
        P, Q = self._two(o, p)
        if k not in self._ROT: raise Refused('rotation 1..3')
        return o != p and norm(P) == self._tnorm(Q, self._ROT[k])

    def same_form(self, o, p, tick):
        P, Q = self._two(o, p); return o != p and norm(P, False) == norm(Q, False)

    def mirror_cell(self, o, p, ax, tick):
        P, Q = self._two(o, p)
        if o == p: return False
        f = (lambda y, x: (self.H - 1 - y, x)) if ax == 0 else (lambda y, x: (y, self.W - 1 - x))
        return all(f(y, x) in Q for (y, x) in P)

    def period(self, o, p, ax, k, tick):
        P, Q = self._two(o, p)
        if o == p: return False
        for (y, x) in Q:
            for s in (k, -k):
                c = (y, x + s) if ax == 0 else (y + s, x)
                if c not in Q and c in P: return True
        return False


ACTS = ('recolor', 'move', 'extend', 'shrink', 'border', 'fillrect', 'hollow', 'flip', 'rotate', 'copy', 'delete', 'merge',
        'split', 'new')
TESTS = ('rcc', 'dir_rel', 'adjacent', 'aligned', 'allen', 'between', 'sees', 'on_ray', 'nearest', 'translate_of',
         'reflection_of', 'rotation_of', 'same_form', 'mirror_cell', 'period')


# -------------------------------------------------------------------- readings
def reading(name, abstraction, background, derive=None):
    """an ARCGraph reading of a task grid (the room's arcroom.scene) and its canvas"""
    import arcroom as AR
    G = AR.scene(name, abstraction, background, derive)
    H, W = AR.size(name)
    cc = G.graph.graph.get('canvas_color')
    return G, H, W, (int(cc) if cc is not None and int(cc) >= 0 else 0)


def reading_of_grid(g, A, bg):
    """ARCGraph's abstraction A of a grid, with canvas colour bg"""
    import arcroom as AR
    img = AR._Image(AR._Task(), grid=g)
    img.binding = ('gol_segment', bg); img.background_color = bg
    G = getattr(img, img.abstraction_ops[A])()
    G.graph.graph['canvas_color'] = bg
    for n in G.graph.nodes: G.graph.nodes[n].setdefault('z_order', 0)
    return G


def offers(name, spec, scenes12=None, k=6):
    """the planner's reading of a grid and Image's shortest offers: {reading key: ARCGraph}"""
    import json, os
    import arcroom as AR
    s = spec['in']; out = {}
    out['%s/%s' % (s['abstraction'], s['background'])] = AR.scene(name, s['abstraction'], s['background'], s.get('derive'))
    if scenes12 and os.path.exists(scenes12):
        for o in sorted(json.load(open(scenes12))['scenes'], key=lambda o: o['dl_in_bits']):
            if len(out) > k: break
            dv = o.get('derive')
            key = '%s/%s%s' % (o['abstraction'], o['background'], ('+' + '+'.join(x['name'] if isinstance(x, dict) else x for x in dv)) if dv else '')
            if key in out: continue
            try: out[key] = AR.scene(name, o['abstraction'], o['background'], dv)
            except Exception: pass
    return out


# -------------------------------------------------------------------- tracing support (handles in, labels out)
def _attrs_of(P):
    import arcgraph_rel as X
    return X.node_attrs(P)


def attrs(scene, h):
    """a node's attributes (ARCGraph's methods), without shape sets"""
    a = _attrs_of(scene._p(h))
    return {k: v for k, v in a.items() if k not in ('shape', 'form', 'd4')}


def relations(scene, a, b):
    import arcgraph_rel as X
    ka, kb = scene.key.get(a), scene.key.get(b)
    e = (scene.G.graph.get_edge_data(ka, kb) or scene.G.graph.get_edge_data(kb, ka) or {}) if ka is not None and kb is not None else {}
    return sorted(X.relations_cells(scene._p(a), scene._p(b), e.get('direction')))


def symmetries(scene, h):
    import arcgraph_rel as X
    return sorted(X.symmetries_of(scene._p(h)))


def place(scene, h, readings):
    """how node h sits in each reading: {reading: [same_as | composed_of | part_of | overlaps, count]}"""
    import arcgraph_rel as X
    return {k: list(v) for k, v in X.place(readings, scene._p(h)).items()}


def _ring_t(a):
    if a['colour'] is None: return None
    h, w = a['height'], a['width']; f = a['form']
    for t in range(1, max(h, w) + 1):
        if {(y, x) for y in range(h) for x in range(w) if y < t or x < t or y >= h - t or x >= w - t} == f: return t
    return None


def _d4(P, t):
    """node P's coloured shape under the D4 map t (arcgraph_rel.D4), normalized"""
    import arcgraph_rel as X
    S = norm(P); h = max(y for y, x, c in S) + 1; w = max(x for y, x, c in S) + 1
    return frozenset((*X.D4[t](y, x, h, w), c) for y, x, c in S)


def _scaled(P, k):
    return frozenset((y * k + a, x * k + b, c) for y, x, c in norm(P) for a in range(k) for b in range(k))


def _sweep(P, d, n):
    dy, dx = DIRS[d]; Q = dict(P)
    for _ in range(n):
        Q.update({(y + dy, x + dx): c for (y, x), c in Q.items() if (y + dy, x + dx) not in Q})
    return Q


def _place(S, top, left):
    return {(y + top, x + left): c for y, x, c in S}


def _ring(top, left, h, w, k, t):
    return {(y, x): k for y in range(top, top + h) for x in range(left, left + w)
            if y < top + t or x < left + t or y >= top + h - t or x >= left + w - t}


def describe_new(C, R):
    """a created node C ({cell: colour}) relative to the roles' nodes R ({role: cells}): (pattern, extra slots)"""
    import arcgraph_rel as X
    sc, fc = norm(C), norm(C, False)
    for i, P in R.items():
        if sc == norm(P): return 'copy of %s' % i, {}
    for i, P in R.items():
        if fc == norm(P, False) and len(set(C.values())) == 1: return 'recoloured copy of %s' % i, {}
    for i, P in R.items():
        for t in X.D4:
            if sc == _d4(P, t): return '%s copy of %s' % (t, i), {}
    for i, P in R.items():
        for t in X.D4:
            if fc == frozenset((y, x) for y, x, c in _d4(P, t)) and len(set(C.values())) == 1: return 'recoloured %s copy of %s' % (t, i), {}
    for i, P in R.items():
        for k in (2, 3, 4, 5):
            if len(C) == len(P) * k * k and sc == _scaled(P, k): return 'scaled %d copy of %s' % (k, i), {}
    a = _attrs_of(C); t = _ring_t(a)
    if t: return 'ring', {'thickness': t}
    for i, P in R.items():
        for j, Q in R.items():
            if i < j and set(C) == set(P) | set(Q) and C == {**P, **Q}: return 'union of %s and %s' % (i, j), {}
    return 'other', {}


def describe_change(B, A, R, i):
    """role i's node changed from B to A: (descriptor, slots), generative where the DSL can realize it"""
    import arcgraph_rel as X
    Ba, Aa = _attrs_of(B), _attrs_of(A)
    if Ba['form'] == Aa['form'] and Ba['shape'] != Aa['shape'] and Aa['colour'] is not None and Ba['top'] == Aa['top'] and Ba['left'] == Aa['left']:
        return '%s recoloured' % i, {'colour': Aa['colour']}
    if Ba['shape'] == Aa['shape']:
        return '%s moved' % i, {'dy': Aa['top'] - Ba['top'], 'dx': Aa['left'] - Ba['left']}
    for t in X.D4:
        if norm(A) == _d4(B, t): return '%s turned %s' % (i, t), {'top': Aa['top'], 'left': Aa['left']}
    if set(A) < set(B) and A == {p: c for p, c in B.items() if Aa['top'] <= p[0] <= Aa['bottom'] and Aa['left'] <= p[1] <= Aa['right']}:
        return '%s cropped' % i, {'top': Aa['top'], 'left': Aa['left'], 'bottom': Aa['bottom'], 'right': Aa['right']}
    if A == {p: c for p, c in B.items() if p[0] in (Ba['top'], Ba['bottom']) or p[1] in (Ba['left'], Ba['right'])}:
        return '%s hollowed' % i, {}
    if set(A) > set(B):
        for d in range(8):
            dy, dx = DIRS[d]
            n = (Aa['height'] - Ba['height']) if dy else (Aa['width'] - Ba['width'])
            if n > 0 and (not dx or Aa['width'] - Ba['width'] == n) and (not dy or Aa['height'] - Ba['height'] == n) and _sweep(B, d, n) == A:
                return '%s swept %d' % (i, d), {'steps': n}
        for j, Q in R.items():
            if j != i and A == {**B, **Q}: return '%s merged with %s' % (i, j), {}
    t = _ring_t(Aa)
    if t: return '%s becomes ring' % i, {'top': Aa['top'], 'left': Aa['left'], 'height': Aa['height'], 'width': Aa['width'],
                                         'colour': Aa['colour'], 'thickness': t}
    sl = {k: Aa[k] for k in ('top', 'left', 'bottom', 'right')}
    if Aa['colour'] is not None: sl['colour'] = Aa['colour']
    return '%s reshaped' % i, sl


def slots_needed(item):
    """the slot names realize() reads for an effect item (None: every observed slot; the item is not generative)"""
    w = item.split()
    if w[0] == 'created':
        p = w[1:]
        if p[0] == 'ring': return ('top', 'left', 'height', 'width', 'colour', 'thickness')
        if p[0] == 'union': return ()
        if p[0] == 'recoloured': return ('top', 'left', 'colour')
        if p[0] == 'other': return None
        return ('top', 'left')
    if w[0] == 'canvas': return ('h', 'w', 'bg')
    verb = w[1] if len(w) > 1 else ''
    return {'recoloured': ('colour',), 'moved': ('dy', 'dx'), 'turned': ('top', 'left'), 'deleted': (),
            'cropped': ('top', 'left', 'bottom', 'right'), 'hollowed': (), 'swept': ('steps',), 'merged': (),
            'becomes': ('top', 'left', 'height', 'width', 'colour', 'thickness')}.get(verb)


def realize(item, v, R, scene=None):
    """the node an effect item makes, from its slot values v and the roles' nodes R; None when not generative.
    item: an effect entry with role names ('created copy of p1', 'p0 turned r90', ...)."""
    w = item.split()
    try:
        if w[0] == 'created':
            pat = w[1:]
            if pat[0] == 'ring': return _ring(v['top'], v['left'], v['height'], v['width'], v['colour'], v['thickness'])
            if pat[0] == 'copy': return _place(norm(R[pat[2]]), v['top'], v['left'])
            if pat[0] == 'recoloured' and pat[1] == 'copy':
                return {p: v['colour'] for p in _place(norm(R[pat[3]]), v['top'], v['left'])}
            if pat[0] == 'scaled': return _place(_scaled(R[pat[4]], int(pat[1])), v['top'], v['left'])
            if pat[0] == 'union': return {**R[pat[2]], **R[pat[4]]}
            if pat[0] == 'recoloured' and pat[2] == 'copy':
                return {p: v['colour'] for p in _place(_d4(R[pat[4]], pat[1]), v['top'], v['left'])}
            if len(pat) == 4 and pat[1] == 'copy': return _place(_d4(R[pat[3]], pat[0]), v['top'], v['left'])
            return None
        i, verb = w[0], w[1]; B = R[i]
        if verb == 'recoloured': return {p: v['colour'] for p in B}
        if verb == 'moved': return {(y + v['dy'], x + v['dx']): c for (y, x), c in B.items()}
        if verb == 'turned': return _place(_d4(B, w[2]), v['top'], v['left'])
        if verb == 'cropped': return {p: c for p, c in B.items() if v['top'] <= p[0] <= v['bottom'] and v['left'] <= p[1] <= v['right']}
        if verb == 'hollowed':
            t, l, b, r = box(B); return {p: c for p, c in B.items() if p[0] in (t, b) or p[1] in (l, r)}
        if verb == 'swept': return _sweep(B, int(w[2]), v['steps'])
        if verb == 'merged': return {**B, **R[w[3]]}
        if verb == 'becomes': return _ring(v['top'], v['left'], v['height'], v['width'], v['colour'], v['thickness'])
        return None
    except (KeyError, ValueError, IndexError, TypeError):
        return None


MAX_SIDE = 8


def effect(before, after, roles, dims_before, dims_after):
    """the effect of a call, relative to its roles ({role: handle} in `before`): (effect shape, observed values,
    generative flags). Each item is a role's change (describe_change), a deletion, a created node (describe_new), or
    the canvas; its slots are observed values. An item is generative when realize() rebuilds the node from the
    item, its slot values and the roles' nodes exactly (checked here, on the call itself). Nodes the call changed or
    deleted that are none of its roles become subject roles s0, s1, ... (added to `roles`)."""
    R = {r: before._p(h) for r, h in roles.items()}
    rid = {}
    for r, h in sorted(roles.items(), key=lambda x: (x[0].startswith('g:'), x[0])):
        if r != 'last': rid.setdefault(h, r)            # arguments first, then registers
    side = [h for h in sorted(before.mir) if h not in rid and (h not in after.mir or after.mir[h] != before.mir[h])]
    for k, h in enumerate(side[:MAX_SIDE]):           # a node the call reached by itself: a subject role s<k>
        rid[h] = 's%d' % k; R['s%d' % k] = before.mir[h]; roles['s%d' % k] = h
    shape, obs, gen = [], {}, []
    for h in sorted(before.mir):
        if h in after.mir and after.mir[h] != before.mir[h]:
            if h not in rid: shape.append('side change'); gen.append(False); continue
            i = rid[h]; item, sl = describe_change(before.mir[h], after.mir[h], R, i)
            shape.append(item); obs.update({'%s.%s' % (i, k): v for k, v in sl.items()})
            gen.append(realize(item, sl, R) == after.mir[h])
    for h in sorted(before.mir):
        if h not in after.mir:
            shape.append('%s deleted' % rid[h] if h in rid else 'side delete'); gen.append(h in rid)
    for j, h in enumerate(sorted(x for x in after.mir if x not in before.mir)):
        C = after.mir[h]; a = _attrs_of(C); pat, extra = describe_new(C, R)
        sl = {k: a[k] for k in ('top', 'left', 'height', 'width')}
        if a['colour'] is not None: sl['colour'] = a['colour']
        sl.update(extra)
        shape.append('created %s' % pat); obs.update({'c%d.%s' % (j, k): v for k, v in sl.items()})
        gen.append(realize('created %s' % pat, sl, R) == C)
    if tuple(dims_before) != tuple(dims_after):
        shape.append('canvas'); obs['canvas.h'], obs['canvas.w'], obs['canvas.bg'] = dims_after; gen.append(True)
    return shape, obs, gen

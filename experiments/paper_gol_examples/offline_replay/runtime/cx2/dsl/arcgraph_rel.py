"""ARCGraph extension (DSL, behind the barrier): relations between nodes, a node's symmetries, and the hierarchy across
Image's readings of one grid. Everything is read off ARCGraph's own structure: a node's subnodes (the pixel nodes of
the image graph it covers) and colours, ARCGraph's direction edges, and its D4 shape variants (fit_shape_variants).
The container calls these; the harness computes nothing.

Attached to ARCGraph as methods by attach(ARCGraph):
  G.symmetries(n)              the subset of the 7 non-identity D4 maps that leave n's coloured shape unchanged
  G.relations_between(a, b)    typed relations from a to b: in, holds, touch, same_shape, same_shape_d4, mirror,
                               same_size, row, col, and ARCGraph's own edge direction (edge:horizontal / edge:vertical)
and module functions over two readings of the same grid:
  hierarchy(Ga, a, Gb, b)      same_as / part_of / contains / overlaps / None, from the two nodes' subnode sets
  place(G_levels, cells)       how a set of subnodes sits in each reading: same_as a node, composed_of n nodes, part_of
                               a node, or overlaps"""

_AG = None


def _ag():
    """the ARCGraph class of the room's package (imported after arcroom has set the path)"""
    global _AG
    if _AG is None:
        from ARCGraph import ARCGraph as A
        _AG = A
    return _AG


class _View:
    """one detached node, so that ARCGraph's own methods read its attributes"""
    def __init__(self, cells):
        import networkx as nx
        self.graph = nx.Graph(); pts = sorted(cells)
        self.graph.add_node(0, nodes=pts, color=[cells[p] for p in pts], size=len(pts))


def node_attrs(cells):
    """a node's attributes, read by ARCGraph's methods (_node_bbox, get_shape, get_node_dimensions,
    fit_shape_variants): box, extents, size, ARCGraph's run dimensions, colour, shape and its D4 class"""
    A = _ag(); v = _View(cells)
    t, b, l, r = A._node_bbox(v, 0)
    form = A.get_shape(v, 0)
    rh, rw = A.get_node_dimensions(list(cells))
    cols = set(cells.values())
    return {'top': t, 'left': l, 'bottom': b, 'right': r, 'height': b - t + 1, 'width': r - l + 1, 'size': len(cells),
            'run_h': rh, 'run_w': rw, 'colour': next(iter(cols)) if len(cols) == 1 else None, 'ncolours': len(cols),
            'shape': frozenset((y - t, x - l, c) for (y, x), c in cells.items()), 'form': form,
            'd4': min(tuple(sorted(s)) for s in A.fit_shape_variants(form, 'd4'))}


STRICT = {'up': 'above', 'down': 'below', 'left': 'left_of', 'right': 'right_of'}


def directions(sa, sb):
    """ARCGraph's fit_relative_directions, kept only where the two boxes are apart on that axis"""
    A = _ag()
    ya = [y for y, x in sa]; yb = [y for y, x in sb]; xa = [x for y, x in sa]; xb = [x for y, x in sb]
    apart_y = max(ya) < min(yb) or min(ya) > max(yb); apart_x = max(xa) < min(xb) or min(xa) > max(xb)
    out = set()
    for d in A.fit_relative_directions(list(sa), list(sb)):
        if (d in ('up', 'down') and apart_y) or (d in ('left', 'right') and apart_x): out.add(STRICT[d])
    return out


D4 = {
    'r90': lambda y, x, h, w: (x, h - 1 - y), 'r180': lambda y, x, h, w: (h - 1 - y, w - 1 - x),
    'r270': lambda y, x, h, w: (w - 1 - x, y), 'flip_lr': lambda y, x, h, w: (y, w - 1 - x),
    'flip_ud': lambda y, x, h, w: (h - 1 - y, x), 'transpose': lambda y, x, h, w: (x, y),
    'anti': lambda y, x, h, w: (w - 1 - x, h - 1 - y)}


def cells_of(G, n):
    """{(row, col): colour} of node n: its subnodes and their colours"""
    d = G.graph.nodes[n]
    pts = [tuple(map(int, p)) for p in d['nodes']]
    col = d['color']
    cols = [int(c) for c in col] if isinstance(col, list) else [int(col)] * len(pts)
    return dict(zip(pts, cols))


def norm(cells):
    t = min(y for y, x in cells); l = min(x for y, x in cells)
    return {(y - t, x - l): c for (y, x), c in cells.items()}


def symmetries_of(cells):
    s = norm(cells); h = max(y for y, x in s) + 1; w = max(x for y, x in s) + 1
    out = set()
    for name, f in D4.items():
        if name in ('r90', 'r270', 'transpose', 'anti') and h != w: continue
        if {f(y, x, h, w): c for (y, x), c in s.items()} == s: out.add(name)
    return frozenset(out)


def filled(cells):
    """the node's cells plus the cells it encloses (4-connected, within its box)"""
    ys = [y for y, x in cells]; xs = [x for y, x in cells]
    t, b, l, r = min(ys), max(ys), min(xs), max(xs)
    free = {(y, x) for y in range(t, b + 1) for x in range(l, r + 1)} - set(cells)
    seen, stack = set(), [p for p in free if p[0] in (t, b) or p[1] in (l, r)]
    while stack:
        p = stack.pop()
        if p in seen or p not in free: continue
        seen.add(p); y, x = p
        stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return set(cells) | (free - seen)


def relations_cells(A, B, edge=None):
    """typed relations from node A to node B, given as {(row, col): colour}"""
    R = set()
    sa, sb = set(A), set(B)
    if sa <= filled(B) and not sa & sb: R.add('in')
    if sb <= filled(A) and not sa & sb: R.add('holds')
    if not sa & sb and any((y + dy, x + dx) in sb for (y, x) in sa for dy in (-1, 0, 1) for dx in (-1, 0, 1)): R.add('touch')
    na, nb = norm(A), norm(B)
    if set(na) == set(nb): R.add('same_shape')
    else:
        h = max(y for y, x in na) + 1; w = max(x for y, x in na) + 1
        for name, f in D4.items():
            if set(norm({f(y, x, h, w): 0 for (y, x) in na})) == set(nb):
                R.add('same_shape_d4')
                if name in ('flip_lr', 'flip_ud'): R.add('mirror')
                break
    if len(A) == len(B): R.add('same_size')
    ya = {y for y, x in sa}; yb = {y for y, x in sb}; xa = {x for y, x in sa}; xb = {x for y, x in sb}
    if min(ya) <= max(yb) and min(yb) <= max(ya): R.add('row')
    if min(xa) <= max(xb) and min(xb) <= max(xa): R.add('col')
    ca, cb = set(A.values()), set(B.values())
    if len(ca) == 1 and ca == cb: R.add('same_colour')
    if not sa & sb:
        try: R |= directions(sa, sb)
        except Exception: pass
    if edge: R.add('edge:' + str(edge))
    return frozenset(R)


def hierarchy_cells(sa, sb):
    sa, sb = set(sa), set(sb)
    if sa == sb: return 'same_as'
    if sa < sb: return 'part_of'
    if sa > sb: return 'contains'
    if sa & sb: return 'overlaps'
    return None


def place(levels, cells):
    """levels: {reading name: ARCGraph}; cells: a set of subnodes. -> {reading: (relation, count)}"""
    s = set(cells); out = {}
    for name, G in levels.items():
        nodes = {n: set(cells_of(G, n)) for n in G.graph.nodes}
        same = [n for n, c in nodes.items() if c == s]
        if same: out[name] = ('same_as', 1); continue
        inside = [n for n, c in nodes.items() if c <= s]
        if inside and set().union(*[nodes[n] for n in inside]) == s: out[name] = ('composed_of', len(inside)); continue
        cont = [n for n, c in nodes.items() if s < c]
        if cont: out[name] = ('part_of', 1); continue
        if any(c & s for c in nodes.values()): out[name] = ('overlaps', sum(1 for c in nodes.values() if c & s))
    return out


def attach(ARCGraph):
    def symmetries(self, n): return symmetries_of(cells_of(self, n))
    def relations_between(self, a, b):
        e = self.graph.get_edge_data(a, b) or self.graph.get_edge_data(b, a) or {}
        return relations_cells(cells_of(self, a), cells_of(self, b), e.get('direction'))
    ARCGraph.symmetries = symmetries
    ARCGraph.relations_between = relations_between
    return ARCGraph

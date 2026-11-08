"""Derived descriptions that perception offers (B.7 round 7, rev 13). Perception, not a reading: the harness offers
these over every base abstraction so that the reader can consider every way of describing a state, and the
experiment can ask what the reader adds on its own (Len, Oct 28: "the perception code should offer all possible
abstractions - because LLM may not have its own abstraction capabilities").

  invariant_node(G, colors)   the objects of the colours every demonstration leaves unchanged become one node (the
                              invariant part), on the bottom layer
  regular_parts(G)            each one-colour object is split into its largest inscribed rectangle (its regular part)
                              and the remainder deconstructed into its 4-connected pieces, each a node
  regular_compound(G)         the same, but the remainder is one node of same-colour parts
  completion(G)               a one-colour object that fills at least half its box, whose missing box cells are all
                              covered by other objects, becomes its solid box; the objects covering it (noise, pieces,
                              marks) go on the layer above
A derivation never changes the rendered grid; the harness checks that every offered description is lossless.
"""
DERIVATIONS = ('invariant_node', 'regular_parts', 'regular_compound', 'completion')


def _merge():
    try:
        import arcroom
        return arcroom.merge_nodes
    except ImportError:
        from dsl_extension import scene_ops
        return scene_ops.merge_nodes


def _one_colour(d):
    if not isinstance(d['color'], list): return d['color']
    ks = set(d['color'])
    return next(iter(ks)) if len(ks) == 1 else None


def _new(G, pts, color, z):
    nid = G.generate_node_id(G.graph, list(pts), reuse_existing=False)
    G.graph.add_node(nid, nodes=list(pts), color=color, size=len(pts), z_order=z)
    G.refresh_node_dimensions(nid)
    return nid


def largest_rectangle(cells):
    """(area, (r0, c0, r1, c1)) of the largest axis-aligned rectangle made only of the given cells"""
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    R0, C0 = min(rs), min(cs); H, W = max(rs) - R0 + 1, max(cs) - C0 + 1
    heights = [0] * W; best = (0, None)
    for r in range(H):
        for c in range(W): heights[c] = heights[c] + 1 if (R0 + r, C0 + c) in cells else 0
        stack = []
        for c in range(W + 1):
            h = heights[c] if c < W else 0
            start = c
            while stack and stack[-1][1] >= h:
                s, hh = stack.pop()
                if hh * (c - s) > best[0]: best = (hh * (c - s), (R0 + r - hh + 1, C0 + s, R0 + r, C0 + c - 1))
                start = s
            stack.append((start, h))
    return best


def _pieces(cells):
    left, out = set(cells), []
    while left:
        seed = min(left); left.discard(seed); todo, grp = [seed], [seed]
        while todo:
            r, c = todo.pop()
            for q in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if q in left: left.discard(q); grp.append(q); todo.append(q)
        out.append(sorted(grp))
    return out


def _regular(G, compound):
    for n in list(G.graph.nodes):
        d = G.graph.nodes[n]; k = _one_colour(d)
        if k is None or len(d['nodes']) < 5: continue
        cells = {tuple(p) for p in d['nodes']}
        area, box = largest_rectangle(cells)
        if area == len(cells) or area < 4 or 2 * area < len(cells): continue
        r0, c0, r1, c1 = box
        rect = [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
        rest = sorted(cells - set(rect))
        z = d.get('z_order', 0)
        d['nodes'] = rect; d['size'] = len(rect)
        if isinstance(d['color'], list): d['color'] = [k] * len(rect)
        G.refresh_node_dimensions(n)
        for grp in ([rest] if compound else _pieces(rest)): _new(G, grp, d['color'] if not isinstance(d['color'], list) else [k] * len(grp), z)
    return G


def regular_parts(G):
    return _regular(G, False)


def regular_compound(G):
    return _regular(G, True)


def completion(G):
    where = {}
    for n, d in G.graph.nodes(data=True):
        for p in d['nodes']: where.setdefault(tuple(p), []).append(n)
    done = set()
    for n in sorted(G.graph.nodes, key=lambda x: -G.graph.nodes[x]['size']):
        d = G.graph.nodes[n]; k = _one_colour(d)
        if k is None: continue
        cells = {tuple(p) for p in d['nodes']}
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        box = {(r, c) for r in range(min(rs), max(rs) + 1) for c in range(min(cs), max(cs) + 1)}
        holes = box - cells
        if not holes or 2 * len(cells) < len(box): continue
        cover = {m for p in holes for m in where.get(p, []) if m != n}
        if any(not [m for m in where.get(p, []) if m != n] for p in holes): continue
        if cover & done: continue                    # covering stays one way: a completed object is never raised
        z = d.get('z_order', 0)
        if z >= 2: continue
        d['nodes'] = sorted(box); d['size'] = len(box)
        if isinstance(d['color'], list): d['color'] = [k] * len(box)
        G.refresh_node_dimensions(n)
        for p in holes: where.setdefault(p, []).append(n)
        for m in cover: G.graph.nodes[m]['z_order'] = max(G.graph.nodes[m].get('z_order', 0), z + 1)
        done.add(n)
    return G


def invariant_node(G, colors):
    merge = _merge()
    keep = None
    for n in list(G.graph.nodes):
        if _one_colour(G.graph.nodes[n]) in colors:
            keep = n if keep is None else merge(G, keep, n)
    if keep is not None: G.graph.nodes[keep]['z_order'] = 0
    return G


def derive(G, items):
    """apply derived descriptions in order: items = [{'name': one of DERIVATIONS, 'params': {...}}]"""
    for it in items or []:
        name = it['name'] if isinstance(it, dict) else it
        if name not in DERIVATIONS: raise ValueError('unknown derivation %r' % name)
        globals()[name](G, **(it.get('params', {}) if isinstance(it, dict) else {}))
    return G


def invariant_colors(task):
    """the colours whose cells every demonstration leaves unchanged (present in some input)"""
    seen, keep = set(), None
    for p in task['train']:
        a, b = p['input'], p['output']
        if len(a) != len(b) or len(a[0]) != len(b[0]): return []
        cols = {v for row in a for v in row}; seen |= cols
        ok = set()
        for k in cols | {v for row in b for v in row}:
            ca = {(r, c) for r, row in enumerate(a) for c, v in enumerate(row) if v == k}
            cb = {(r, c) for r, row in enumerate(b) for c, v in enumerate(row) if v == k}
            if ca == cb: ok.add(k)
        keep = ok if keep is None else keep & ok
    return sorted((keep or set()) & seen)

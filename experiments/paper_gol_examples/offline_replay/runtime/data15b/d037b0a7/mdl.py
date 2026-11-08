"""Description length of a scene, in object terms (the harness's MDL ranking of descriptions; B.7 round 7).
Copied from tools/dream/o0/b7r7/perceive.py: shapes (shape_topology concepts, symmetries), film generators
(reflections, rotations and translations that map a film's objects onto its objects), and shape cost. The harness
uses it to rank the descriptions it offers; the container never reads cells."""
import itertools, math
import shape_topology as ST

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def norm(coords):
    r0 = min(p[0] for p in coords); c0 = min(p[1] for p in coords)
    return tuple(sorted((r - r0, c - c0) for r, c in coords))


def d4(mask):
    out = []
    pts = list(mask)
    for k in range(4):
        pts = [(c, -r) for r, c in pts]
        out.append(norm(pts)); out.append(norm([(r, -c) for r, c in pts]))
    return out


def holes_of(mask):
    h = max(p[0] for p in mask) + 1; w = max(p[1] for p in mask) + 1; m = set(mask)
    seen = set(); n = 0
    for r in range(h):
        for c in range(w):
            if (r, c) in m or (r, c) in seen: continue
            st = [(r, c)]; seen.add((r, c)); edge = False
            while st:
                a, b = st.pop()
                if a in (0, h - 1) or b in (0, w - 1): edge = True
                for dr, dc in N4:
                    p, q = a + dr, b + dc
                    if 0 <= p < h and 0 <= q < w and (p, q) not in m and (p, q) not in seen:
                        seen.add((p, q)); st.append((p, q))
            if not edge: n += 1
    return n


def shape_record(mask):
    h = max(p[0] for p in mask) + 1; w = max(p[1] for p in mask) + 1; m = set(mask)
    tile = [[1 if (r, c) in m else 0 for c in range(w)] for r in range(h)]
    try: concept = ST.classify_binary_tile_concept(tile)
    except ValueError: concept = None
    sym = []
    if norm([(r, w - 1 - c) for r, c in mask]) == mask: sym.append('mirror_lr')
    if norm([(h - 1 - r, c) for r, c in mask]) == mask: sym.append('mirror_ud')
    if h == w and norm([(c, r) for r, c in mask]) == mask: sym.append('mirror_diag')
    if h == w and norm([(w - 1 - c, h - 1 - r) for r, c in mask]) == mask: sym.append('mirror_anti')
    if norm([(h - 1 - r, w - 1 - c) for r, c in mask]) == mask: sym.append('rot180')
    if h == w and norm([(c, h - 1 - r) for r, c in mask]) == mask: sym.append('rot90')
    return {'h': h, 'w': w, 'n': len(mask), 'concept': concept, 'holes': holes_of(mask), 'sym': sym,
            'cls': min(d4(mask)), 'mask': [list(p) for p in mask]}


# ------------------------------------------------------------------ symmetry generators per film (object level)
def _key(o):
    return (tuple(map(tuple, o['coords'])), tuple(o.get('colours') or [o['colour']] * len(o['coords'])))


def _apply(o, fn):
    cols = o.get('colours') or [o['colour']] * len(o['coords'])
    pts = sorted(zip((fn(r, c) for r, c in o['coords']), cols))
    return (tuple(p for p, _ in pts), tuple(k for _, k in pts))


def film_generators(objs):
    """generators that map the film's objects onto its objects: reflections and rotations about the film's box
    (every object must map onto an object), translations by a vector between two equal objects (every object maps
    onto an object or wholly outside the film's box). Greedy: keep a generator when it frees at least one object."""
    real = [o for o in objs if not o.get('region')]
    if len(real) < 2: return [], set()
    pts = [p for o in real for p in o['coords']]
    r0 = min(p[0] for p in pts); r1 = max(p[0] for p in pts); c0 = min(p[1] for p in pts); c1 = max(p[1] for p in pts)
    keys = {_key(o): i for i, o in enumerate(real)}
    cands = [('mirror_lr', lambda r, c: (r, c0 + c1 - c)), ('mirror_ud', lambda r, c: (r0 + r1 - r, c)),
             ('rot180', lambda r, c: (r0 + r1 - r, c0 + c1 - c))]
    if r1 - r0 == c1 - c0:
        cands += [('mirror_diag', lambda r, c: (r0 + (c - c0), c0 + (r - r0))),
                  ('mirror_anti', lambda r, c: (r0 + (c1 - c), c0 + (r1 - r))),
                  ('rot90', lambda r, c: (r0 + (c - c0), c0 + (r1 - r)))]
    gens, maps = [], []
    for name, fn in cands:
        m = {}
        for i, o in enumerate(real):
            j = keys.get(_apply(o, fn))
            if j is None: m = None; break
            m[i] = j
        if m and any(i != j for i, j in m.items()):
            gens.append({'kind': name, 'box': [r0, c0, r1 - r0 + 1, c1 - c0 + 1]}); maps.append(m)
    seenv = set()
    for a, b in itertools.permutations(range(len(real)), 2):
        oa, ob = real[a], real[b]
        if oa['colour'] != ob['colour'] or len(oa['coords']) != len(ob['coords']): continue
        v = (ob['coords'][0][0] - oa['coords'][0][0], ob['coords'][0][1] - oa['coords'][0][1])
        if v in seenv or v == (0, 0): continue
        seenv.add(v)
        if len(seenv) > 60: break
        fn = lambda r, c, v=v: (r + v[0], c + v[1])
        m = {}
        ok = True
        for i, o in enumerate(real):
            img = _apply(o, fn); j = keys.get(img)
            if j is not None: m[i] = j; continue
            if all(not (r0 <= r <= r1 and c0 <= c <= c1) for r, c in img[0]): continue
            ok = False; break
        if ok and len(m) >= 1:
            gens.append({'kind': 'translate', 'v': list(v), 'box': [r0, c0, r1 - r0 + 1, c1 - c0 + 1]}); maps.append(m)
    # greedy choice: the generator freeing the most objects first; at most 3
    chosen, freed = [], set()
    while len(chosen) < 3:
        best, bgain = None, 0
        for gi, m in enumerate(maps):
            if gi in chosen: continue
            trial = _freed(maps, chosen + [gi], len(real))
            gain = len(trial) - len(freed)
            if gain > bgain: best, bgain = gi, gain
        if best is None: break
        chosen.append(best); freed = _freed(maps, chosen, len(real))
    return [gens[g] for g in chosen], {id(real[i]) for i in freed}


def _freed(maps, chosen, n):
    """objects that are images of others under the chosen generators (a motif is what is left)"""
    parent = list(range(n))

    def f(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for g in chosen:
        for i, j in maps[g].items():
            a, b = f(i), f(j)
            if a != b: parent[max(a, b)] = min(a, b)
    return {i for i in range(n) if f(i) != i}



def shape_bits(rec):
    """10 bits for height and width, plus 4 bits for a shape concept or one bit per coordinate of its box"""
    return 10 + (4 if rec['concept'] else rec['h'] * rec['w'])


# ------------------------------------------------------------------ the description length of a state (rev 12)
_SHAPE_BITS = {}


def scene_dl(G, H, W):
    """bits to describe one state as the ARCGraph G on an H x W frame: the canvas as one number; shapes (shape-topology
    concept, else one bit per box cell) once each; per object not generated by a film generator, its shape index,
    position and colour (one colour, or one per cell for a multicolour object); 12 bits per generator; 12 bits per
    extra film layer plus log2(L) per object; per compound node, its construct, one bit per part and a role label
    per bound part (slightly more than a simple node); per added relation edge, its two ends"""
    nodes = list(G.graph.nodes(data=True))
    canvas = G.graph.graph.get('canvas_color', -1)
    bits = 2 + (math.log2(10) if canvas not in (-1, None) else 0)
    if not nodes: return bits
    objs = [{'coords': [tuple(p) for p in d['nodes']], 'colour': None if isinstance(d['color'], list) else d['color'],
             'colours': d['color'] if isinstance(d['color'], list) else None} for _, d in nodes]
    gens, freed = film_generators(objs)
    used = {norm(o['coords']) for o in objs}
    bits += 12 * len(gens)
    L = len({d.get('z_order', 0) for _, d in nodes})
    if L > 1: bits += 12 * (L - 1) + len(objs) * math.log2(L)
    for o in objs:
        if id(o) in freed: continue
        bits += math.log2(max(2, len(used))) + math.log2(H) + math.log2(W) + math.log2(10) * (len(o['coords']) if o['colours'] else 1)
    for m in used:
        if m not in _SHAPE_BITS: _SHAPE_BITS[m] = shape_bits(shape_record(m))
        bits += _SHAPE_BITS[m]
    n = math.log2(max(2, len(objs)))
    insts = G.graph.graph.get('constructs', [])
    kinds = max(2, len({i['construct'] for i in insts}))
    # a compound node costs only slightly more than a simple node (Len, Oct 28): its construct, one bit per part for
    # the nesting, and a role label per bound part
    for i in insts:
        roles = max(2, len(set(i.get('bindings', {}))))
        bits += math.log2(kinds) + len(set(i.get('parts', [])) | set(i.get('bindings', {}).values())) + len(i.get('bindings', {})) * math.log2(roles)
    bits += sum(2 * n for _, _, e in G.graph.edges(data=True) if 'relation' in e)
    return bits

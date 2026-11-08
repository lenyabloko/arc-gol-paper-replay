"""Round 7 room runtime: the project's own ARCGraph wrapper (GitLab r7/eight-connected-abstractions: image.py with 20
abstractions, ARCGraph.py, the ontology's background hypotheses), for one task.

The brain (your reading) works on ARCGraph graphs: nodes are objects, a node's data is
  nodes  the coordinates the object occupies (its own cells: read them only through the node)
  color  its colour (a list, one per coordinate, for a multicolour node)
  size, dim  its size and (height, width)
  z_order    its film layer (0 = bottom; nodes are painted in z_order); missing means 0
and edges are relations (ARCGraph's `direction` edges, plus any you add with `add_relation`). The canvas is the
graph's background colour (G.graph.graph['canvas_color']), or a node when the abstraction keeps it.

API (the brain may use these, the DSL in DSL.md, and networkx on G.graph):
  grid_names(), size(name), dims(G)                the grids of the task: d0_in, d0_out, ..., t0_in; (H, W)
  canvas_colour(name, background)                  the colour a background hypothesis selects on a grid, or None
  scene(name, abstraction, background, derive=None) a fresh ARCGraph of that grid (derive: perception's derived
                                                   descriptions, see perception.py)
  set_layer(G, node, z), layer(G, node)            film layers (at most 3: 0, 1, 2)
  merge_nodes(G, a, b), split_node(G, node, by, z=None)   regroup objects (parts of an object may lie on other layers)
  add_relation(G, a, b, relation, **attrs)         an edge for a relation between two objects
  instantiate(G, construct, bindings, parts)       a compound object: an instance of an abstract construct with its role
                                                   bindings and parts; the program filters on it with
                                                   filter_by_role(construct, role) / filter_by_part_of(construct), and
                                                   its parts stay ordinary nodes (it can be broken into them)
  run(G, steps, terms=None)                        a program (a mechanism): ARCGraph `apply` steps and regroup,
                                                   relation and layer steps (see DSL.md), with the extension bound
Backgrounds: 'modal_color', 'boundary_supported', 'corner_supported', 'literal_black' (the ontology's hypotheses),
'contact_canvas' (the colour every component of every other colour touches), or None (no canvas: every colour an
object)."""
import json, os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, 'arc', '_stubs'), os.path.join(HERE, 'arc')):
    if p not in sys.path: sys.path.insert(0, p)
import networkx as nx                                       # noqa: E402
import image as _IM                                         # noqa: E402
from ARCGraph import ARCGraph                               # noqa: E402
from ontology import background_canvas as _BC               # noqa: E402
from ontology.runtime_registry import execution_policy      # noqa: E402
from utils import Direction, Rotation, Mirror, ImagePoints, RelativePosition   # noqa: E402,F401

ABSTRACTIONS = tuple(_IM.Image.abstractions)
BACKGROUNDS = ('modal_color', 'boundary_supported', 'corner_supported', 'literal_black', 'contact_canvas', None)
_ALLOWED = json.load(open(os.path.join(HERE, 'dsl_allowed.json')))
_T = json.load(open(os.path.join(HERE, 'task.json')))
_GRIDS = {}
for _i, _p in enumerate(_T['train']):
    _GRIDS['d%d_in' % _i] = _p['input']
    if 'output' in _p: _GRIDS['d%d_out' % _i] = _p['output']
for _j, _p in enumerate(_T['test']): _GRIDS['t%d_in' % _j] = _p['input']


class _Task:
    max_abstract_nodes = execution_policy('task.max_abstract_nodes')
    stop_search = False


class _Image(_IM.Image):
    binding = (None, -1)

    def background_binding_for_abstraction(self, abstraction):
        return self.binding


def grid_names():
    return list(_GRIDS)


def size(name):
    g = _GRIDS[name]; return (len(g), len(g[0]))


def _contact(img):
    nodes = img.get_no_color_connected_components_graph().graph.nodes(data=True)
    where = {}
    comps = []
    for _, d in nodes:
        comps.append((d['color'], [tuple(p) for p in d['nodes']]))
        for p in d['nodes']: where[tuple(p)] = d['color']
    cols = sorted({k for k, _ in comps})
    if len(cols) < 2: return None
    good = [k for k in cols if all(kk == k or any(where.get((r + a, c + b)) == k for r, c in cm
                                                  for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))) for kk, cm in comps)]
    if not good: return None
    return max(good, key=lambda k: (sum(len(cm) for kk, cm in comps if kk == k), -k))


def dims(G):
    """(H, W) of the coordinate system of graph G"""
    return (G.image.height, G.image.width)


def canvas_colour(name, background):
    if background is None: return None
    g = _GRIDS[name]
    if background == 'contact_canvas':
        img = _Image(_Task(), grid=g); img.binding = ('no_color_canvas', -1); return _contact(img)
    d = _BC.resolve_background_hypothesis(g, hypothesis_id=background)
    return d['selected_color'] if d.get('resolution_status') == 'selected' else None


def scene(name, abstraction, background, derive=None):
    """a fresh ARCGraph of grid `name` under `abstraction`, with the canvas colour chosen by `background`, and the
    derived descriptions perception offers applied in order (perception.py: invariant_node, regular_parts,
    regular_compound, completion)"""
    if abstraction not in ABSTRACTIONS: raise ValueError('unknown abstraction %r' % abstraction)
    if background not in BACKGROUNDS: raise ValueError('unknown background %r' % background)
    k = canvas_colour(name, background)
    img = _Image(_Task(), grid=_GRIDS[name])
    img.binding = (background or 'no_color_canvas', -1 if k is None else k)
    img.background_color = -1 if k is None else k
    G = getattr(img, img.abstraction_ops[abstraction])()
    G.graph.graph['canvas_color'] = -1 if k is None else k
    G.graph.graph['scene'] = {'grid': name, 'abstraction': abstraction, 'background': background}
    for n in G.graph.nodes: G.graph.nodes[n].setdefault('z_order', 0)
    if derive:
        import perception
        perception.derive(G, derive)
        G.graph.graph['scene']['derive'] = derive
    return G


def layer(G, node):
    return G.graph.nodes[node].get('z_order', 0)


def set_layer(G, node, z):
    if z not in (0, 1, 2): raise ValueError('a film layer is 0, 1 or 2')
    G.graph.nodes[node]['z_order'] = z


def merge_nodes(G, a, b):
    """one object from a and b (b's coordinates join a's); returns the new node id"""
    da, db = G.graph.nodes[a], G.graph.nodes[b]
    pa, pb = [tuple(p) for p in da['nodes']], [tuple(p) for p in db['nodes']]
    ca = da['color'] if isinstance(da['color'], list) else [da['color']] * len(pa)
    cb = db['color'] if isinstance(db['color'], list) else [db['color']] * len(pb)
    seen = set(pa); pts = list(pa); cols = list(ca)
    for p, k in zip(pb, cb):
        if p not in seen: pts.append(p); cols.append(k); seen.add(p)
    z = max(da.get('z_order', 0), db.get('z_order', 0))
    G.graph.remove_node(a); G.graph.remove_node(b)
    col = cols[0] if len(set(cols)) == 1 and not G.is_multicolor else cols
    nid = G.generate_node_id(G.graph, pts)
    G.graph.add_node(nid, nodes=pts, color=col, size=len(pts), z_order=z)
    G.refresh_node_dimensions(nid)
    return nid


def split_node(G, node, by, z=None):
    """the part of `node` on the coordinates of node `by` becomes its own node (on layer z, or the same layer); an
    object may so be broken between layers. Returns the new node id, or None if they share no coordinate."""
    d = G.graph.nodes[node]; pts = [tuple(p) for p in d['nodes']]
    cols = d['color'] if isinstance(d['color'], list) else [d['color']] * len(pts)
    there = {tuple(p) for p in G.graph.nodes[by]['nodes']}
    part = [(p, k) for p, k in zip(pts, cols) if p in there]
    rest = [(p, k) for p, k in zip(pts, cols) if p not in there]
    if not part or not rest: return None
    multi = isinstance(d['color'], list)
    d['nodes'] = [p for p, _ in rest]; d['size'] = len(rest)
    if multi: d['color'] = [k for _, k in rest]
    G.refresh_node_dimensions(node)
    pp = [p for p, _ in part]
    nid = G.generate_node_id(G.graph, pp, reuse_existing=False)
    G.graph.add_node(nid, nodes=pp, color=[k for _, k in part] if multi else d['color'], size=len(pp),
                     z_order=d.get('z_order', 0) if z is None else z)
    G.refresh_node_dimensions(nid)
    return nid


def add_relation(G, a, b, relation, **attrs):
    ARCGraph.add_edge_safe(G.graph, a, b, relation=relation, **attrs)


def instantiate(G, construct, bindings, parts=()):
    """a compound object: an instance of an abstract construct, with its role bindings (role -> node) and its parts
    (the nodes it consists of; they may lie on different layers). The program sees it (filter_by_role,
    filter_by_part_of, instances) and can still break it into its parts, which stay ordinary nodes. Returns its id."""
    insts = G.graph.graph.setdefault('constructs', [])
    iid = len(insts)
    insts.append({'id': iid, 'construct': construct, 'bindings': dict(bindings), 'parts': list(parts)})
    for r, n in bindings.items(): G.graph.nodes[n].setdefault('roles', []).append([construct, r, iid])
    for n in parts: G.graph.nodes[n].setdefault('part_of', []).append([construct, iid])
    return iid


def instances(G, construct=None):
    return [i for i in G.graph.graph.get('constructs', []) if construct is None or i['construct'] == construct]


def _filter_by_role(self, node, construct, role=None, exclude=False):
    v = any(c == construct and (role is None or r == role) for c, r, _ in self.graph.nodes[node].get('roles', []))
    return v != exclude


def _filter_by_part_of(self, node, construct, exclude=False):
    v = any(c == construct for c, _ in self.graph.nodes[node].get('part_of', []))
    return v != exclude


def bind_terms(G, terms_module, terms):
    """your filter, binding and operation terms become methods of this graph, so steps can name them"""
    for t in terms:
        if t.get('kind') in ('selector', 'filter', 'binding', 'operation'):
            f = getattr(terms_module, t['name'])
            setattr(G, t['name'], types.MethodType(lambda self, node, _f=f, **kw: _f(self, node, **kw), G))
            if t.get('kind') == 'operation':
                for ab in G.transformation_ops: G.transformation_ops[ab] = list(G.transformation_ops[ab]) + [t['name']]
    return G


STRUCTURE_KINDS = ('deconstruction', 'reconstruction', 'regrouping', 'layering', 'regroup')
STEP_KEYS = STRUCTURE_KINDS + ('relation', 'layer')


def _kind_fits(key, kind):
    if key in ('relation', 'layer'): return kind == key
    return kind == key or kind == 'regroup' or (key == 'regroup' and kind in STRUCTURE_KINDS)


def run(G, steps, terms_module=None, terms=()):
    """run a program (a mechanism: a sequence of steps). A step is an ARCGraph `apply` step (selectors, an offered
    transformation or an extension operation), or a structure step {key: name, 'params'} with key deconstruction (split
    one object into many), reconstruction (join objects into one), regrouping (compound nodes or re-positioned nodes,
    no split or join), layering (a regular shape completed under a layer above: noise, pieces, marks), relation or
    layer, naming an extension function of that kind"""
    if terms_module is not None: bind_terms(G, terms_module, terms)
    G.filter_by_role = types.MethodType(_filter_by_role, G); G.filter_by_part_of = types.MethodType(_filter_by_part_of, G)
    kinds = {t['name']: t.get('kind') for t in terms}
    ops = {n for n, k in kinds.items() if k == 'operation'}
    target = {}
    for st in steps:
        for key in STEP_KEYS:
            if key in st:
                name = st[key]
                if not _kind_fits(key, kinds.get(name)): raise ValueError('%s step %r names no extension function of that kind' % (key, name))
                f = getattr(terms_module, name); p = dict(st.get('params', {}))
                if key == 'relation':
                    for e in f(G, **p): add_relation(G, e[0], e[1], e[2] if len(e) > 2 else name)
                elif key == 'layer':
                    for n in list(G.graph.nodes): set_layer(G, n, f(G, n, **p))
                else: f(G, **p)
                break
        else:
            tr = st['transformation']
            if tr not in _ALLOWED['transformations'] and tr not in ops:
                raise ValueError('transformation %r is not offered (grid-level or unknown)' % tr)
            for f in st.get('filters', []):
                if not hasattr(G, f): raise ValueError('unknown selector %r' % f)
            reps = st.get('repeat', 1)
            for _ in range(reps if isinstance(reps, int) else 30):
                before = sorted((str(n), str(d.get('nodes')), str(d.get('color'))) for n, d in G.graph.nodes(data=True))
                G.apply(target, list(st.get('filters', [])), list(st.get('filter_params', [{}] * len(st.get('filters', [])))),
                        [tr], [dict(st.get('params', {}))])
                if reps == 'fixpoint':
                    after = sorted((str(n), str(d.get('nodes')), str(d.get('color'))) for n, d in G.graph.nodes(data=True))
                    if after == before: break
    return G


def _render(G):
    """the harness's rendering (ARCGraph.undo_abstraction): used by check8.py, never by a reading"""
    out = G.undo_abstraction().graph
    H, W = G.image.height, G.image.width
    return [[out.nodes[(r, c)]['color'] for c in range(W)] for r in range(H)]

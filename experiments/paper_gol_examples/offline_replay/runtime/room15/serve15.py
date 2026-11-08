"""Rev 15 harness: runs GOL plans for the planner and the leaf coder. Object-level answers only for the planner.
usage:
  python3 serve15.py check <task> <planner room>          per demonstration: exact?, out's objects vs the expected
  python3 serve15.py probe <task> <planner room> <grid> <probe json file>   run a term, read registers/tags/tables/objects
  python3 serve15.py objects <task> <planner room>        writes objects.json into the room (no pixels)
  python3 serve15.py code <task> <coder room>             run the plan with the coder's leaves.py; record leaf calls
The interpreter is GRAIN-1 at the paper pins, unchanged; the starting states come from data15/<task>/states.json."""
import ast, hashlib, json, os, signal, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'grain'))
for p in ('container/gol', 'store/rev15'): sys.path.insert(0, os.path.join(HERE, '..', '..', p))   # repo layout (GitLab)
import grain1 as G1
from grain import GrainError

PINS = {'grain1.py': 'fc9177d14a9d4914', 'grain.py': '26e675858e1673b2'}
for _f, _p in PINS.items():
    assert hashlib.sha256(open(os.path.join(os.path.dirname(G1.__file__), _f), 'rb').read()).hexdigest().startswith(_p), 'not at the pin: ' + _f
DATA = os.environ.get('DATA15', '/home/claude/work/r7/data15')
STORE = os.environ.get('STORE15', '/home/claude/work/r7/store15')
FUEL = 3_000_000
CAP = 10


class Wall(BaseException): pass


def _alarm(*a): raise Wall()


def states(task):
    return json.load(open(os.path.join(DATA, task, 'states.json')))


def make_state(s):
    S = G1.State.__new__(G1.State)
    S.A, S.mode = 'nbccg', 'modal'
    sc = G1.Scene(s['H'], s['W'], s['canvas'] if s['canvas'] >= 0 else 0)
    for i, n in enumerate(s['nodes'], 1):
        sc.nodes[i] = {(y, x): c for y, x, c in n['pix']}; sc._rehash(i)
    S.sc = {'in': sc, 'out': sc.clone()}
    S.next_id = len(s['nodes']) + 1; S.last = -1; S.r = {}; S.tags = {}; S.tables = {}; S.th = 0
    return S


def store():
    def ld(f):
        p = os.path.join(STORE, f)
        return json.load(open(p)) if os.path.exists(p) else []
    return ld('defs.json'), ld('leaves.json'), ld('constructs.json')


STUB = 'def %s(S, *args):\n    raise NotImplementedError("leaf %s is declared but not implemented yet")\n'


def program(task, plan, leaf_src=None):
    """plan: the planner's plan.json. leaf_src: {name: python source} for the plan's own leaves (None: from data15)."""
    sdefs, sleaves, _ = store()
    if leaf_src is None:
        p = os.path.join(DATA, task, 'leaves_py.json')
        leaf_src = json.load(open(p)) if os.path.exists(p) else {}
    stored_leaf = {l['name']: l for l in sleaves}
    taken = [l['name'] for l in plan.get('leaves', []) if l['name'] in stored_leaf and stored_leaf[l['name']]['task'] != task]
    if taken: raise GrainError('leaf name taken in the store: %s (call the stored leaf, or choose another name)' % sorted(taken))
    leaves = [{'name': l['name'], 'kind': l['kind'], 'params': l['params'], 'pre': l.get('pre', ''), 'effect': l.get('effect', ''),
               'py': l['py']} for l in sleaves]
    for l in plan.get('leaves', []):
        if l['name'] in stored_leaf: continue          # this task's own leaf, already harvested and loaded
        leaves.append({'name': l['name'], 'kind': l['kind'], 'params': l['params'], 'pre': l.get('pre', ''),
                       'effect': l.get('effect', ''), 'py': leaf_src.get(l['name']) or STUB % (l['name'], l['name'])})
    defs = [{'name': d['name'], 'kind': d['kind'], 'params': d['params'], 'body': d['body']} for d in sdefs]
    sd = {d['name']: d for d in sdefs}
    for d in plan.get('defs', []):
        if d['name'] in sd and sd[d['name']]['task'] == task and sd[d['name']]['body'] == d['body']: continue   # own, harvested
        defs.append({'name': d['name'], 'kind': d['kind'], 'params': d['params'], 'body': d['body']})
    tr = {'task': task, 'basis': 'obj1', 'abstraction': 'nbccg', 'bg': plan.get('bg', 'modal'), 'defs': defs,
          'leaves': leaves, 'main': plan['main']}
    return G1.Program(tr)


def desc(pix, i=None, layer=None):
    cols = {}
    for c in pix.values(): cols[c] = cols.get(c, 0) + 1
    t, l, b, r = G1.box(pix)
    d = {'colours': {str(k): v for k, v in sorted(cols.items())}, 'box': [t, l, b, r], 'size': len(pix)}
    if i is not None: d = dict({'id': i}, **d)
    if layer is not None: d['layer'] = layer
    return d


def run(P, s, record=None):
    S = make_state(s)
    R = G1.Run(P, FUEL)
    if record is not None:
        for name, L in P.leaves.items():
            if getattr(L['fn'], '_wrapped', False): continue
            f = L['fn']

            def w(S_, *args, _f=f, _n=name):
                ids = [a for a in args if isinstance(a, int) and a in S_.sc['out'].nodes]
                before = {o: sorted([y, x, c] for (y, x), c in S_.sc['out'].nodes[o].items()) for o in ids}
                n0 = S_.next_id
                out = _f(S_, *args)
                after = {o: (sorted([y, x, c] for (y, x), c in S_.sc['out'].nodes[o].items()) if o in S_.sc['out'].nodes else None) for o in ids}
                created = {o: sorted([y, x, c] for (y, x), c in S_.sc['out'].nodes[o].items()) for o in range(n0, S_.next_id) if o in S_.sc['out'].nodes}
                if len(record) < 400:
                    record.append({'leaf': _n, 'args': list(args), 'returned': out if isinstance(out, (int, bool, type(None))) else str(out)[:40],
                                   'before': before, 'after': after, 'created': created})
                return out
            w._wrapped = True
            L['fn'] = w
    signal.signal(signal.SIGALRM, _alarm); signal.setitimer(signal.ITIMER_REAL, CAP)
    t0 = time.time()
    try:
        R.do(S, P.expanded); st = 'ok'
    except Wall: st = 'timeout (%d s)' % CAP
    except G1.NonTerminating as e: st = 'nonterminating: %s' % e
    except G1.OutOfFuel as e: st = 'out of fuel: %s' % e
    except G1.Abort as e: st = 'abort: %s' % e
    except RecursionError: st = 'abort: recursion'
    except NotImplementedError as e: st = 'needs leaf: %s' % e
    except Exception as e: st = 'error in a leaf or the plan: %s: %s' % (type(e).__name__, str(e)[:200])
    finally: signal.setitimer(signal.ITIMER_REAL, 0)
    return st, S, R.steps, round(time.time() - t0, 2)


def diff(S, s_out):
    """out's objects vs the expected output objects (the chosen output description): matched, missing, extra"""
    want = [({(y, x): c for y, x, c in n['pix']}, n.get('layer', 0)) for n in s_out['nodes']]
    have = dict(S.sc['out'].nodes)
    used = set(); missing = []
    for k, (p, z) in enumerate(want, 1):
        hit = next((o for o, q in have.items() if o not in used and q == p), None)
        if hit is None: missing.append(dict({'expected': 'e%d' % k}, **desc(p, layer=z)))
        else: used.add(hit)
    extra = [desc(q, o) for o, q in sorted(have.items()) if o not in used]
    return {'matched': len(used), 'missing': missing[:25], 'extra': extra[:25], 'n_missing': len(missing), 'n_extra': len(extra)}


def demo_names(st):
    return sorted({g[:-3] for g in st if g.startswith('d') and g.endswith('_in')}, key=lambda x: int(x[1:]))


def cmd_check(task, room, quiet=False, log_it=True):
    plan = json.load(open(os.path.join(room, 'plan.json')))
    st = states(task)
    try:
        P = program(task, plan)
    except (GrainError, Exception) as e:
        res = {'static': 'rejected: %s' % str(e)[:500]}
        log(room, 'check', res); print(json.dumps(res, indent=1)); return res
    stats = P.stats()
    res = {'static': 'ok', 'L': stats['L'], 'loop_depth': stats['loop_depth'], 'pixel_level': stats['pixel_level'],
           'leaves_declared': [l['name'] for l in plan.get('leaves', [])], 'demonstrations': {}, 'test_inputs': {}}
    allx = True
    for d in demo_names(st):
        s_in, s_out = st[d + '_in'], st[d + '_out']
        status, S, steps, sec = run(P, s_in)
        r = {'status': status, 'steps': steps, 'seconds': sec}
        if status == 'ok':
            out = S.sc['out']
            r['canvas'] = {'produced': [out.H, out.W, out.bg], 'expected': [s_out['H'], s_out['W'], s_out['canvas']]}
            r['exact'] = out.render() == s_out['grid']
            r['objects'] = diff(S, s_out)
        else:
            r['exact'] = False
        allx = allx and r['exact']
        res['demonstrations'][d] = r
    for g in sorted(x for x in st if x.startswith('t')):
        status, S, steps, sec = run(P, st[g])
        res['test_inputs'][g] = {'status': status, 'steps': steps}
    res['exact_on_every_demonstration'] = allx
    if log_it: log(room, 'check', res)
    if not quiet: print(json.dumps(res, indent=1))
    return res


def cmd_probe(task, room, grid, pfile):
    plan = json.load(open(os.path.join(room, 'plan.json')))
    pr = json.load(open(os.path.join(room, pfile)))
    p2 = dict(plan, main=pr['main'])
    if 'defs' in pr: p2['defs'] = plan.get('defs', []) + pr['defs']
    st = states(task)
    if grid not in st or grid.endswith('_out'): raise SystemExit('probe runs on an input grid: d<i>_in or t<j>_in')
    try:
        P = program(task, p2)
    except Exception as e:
        print(json.dumps({'static': 'rejected: %s' % str(e)[:500]})); return
    status, S, steps, sec = run(P, st[grid])
    out = S.sc['out']
    res = {'status': status, 'steps': steps, 'registers': S.r, 'tags': {str(k): v for k, v in S.tags.items() if v},
           'tables': {'%s[%d]' % k: v for k, v in S.tables.items() if v}, 'last': S.last,
           'out': {'canvas': [out.H, out.W, out.bg], 'objects': [desc(p, o) for o, p in sorted(out.nodes.items())][:80],
                   'n_objects': len(out.nodes)}}
    log(room, 'probe', {'grid': grid, 'main': pr['main'][:300], 'status': status})
    print(json.dumps(res, indent=1))


def cmd_objects(task, room):
    st = states(task)
    spec = json.load(open(os.path.join(DATA, task, 'spec.json')))
    res = {'descriptions': {'in': {k: spec['in'][k] for k in ('name', 'abstraction', 'background', 'derive')},
                            'out': {k: spec['out'][k] for k in ('name', 'abstraction', 'background', 'derive')}},
           'grids': {}}
    for g in sorted(st, key=lambda x: (x[0] != 'd', int(x[1:].split('_')[0]), x.endswith('_out'))):
        s = st[g]
        res['grids'][g] = {'H': s['H'], 'W': s['W'], 'canvas': s['canvas'],
                           'objects': [desc({(y, x): c for y, x, c in n['pix']}, i, n['layer']) for i, n in enumerate(s['nodes'], 1)]}
    json.dump(res, open(os.path.join(room, 'objects.json'), 'w'), indent=1)
    print('objects.json:', len(res['grids']), 'grids')


ALLOWED_IMPORTS = {'collections', 'itertools', 'math', 'functools', 'heapq'}
ALLOWED_STR = {'in', 'out'} | {'t%d' % i for i in range(10)}


def _mark_docstrings(tree):
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n): c.parent = n


def barrier_src(src):
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return ['syntax: %s' % e]
    _mark_docstrings(tree)
    flags = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant):
            v = n.value
            if isinstance(v, bool) or v is None: continue
            if isinstance(v, (int, float)) and v not in (0, 1, 2): flags.append('literal %r (line %d)' % (v, n.lineno))
            if isinstance(v, str) and v not in ALLOWED_STR and not isinstance(getattr(n, 'parent', None), ast.Expr):
                flags.append('string %r (line %d)' % (v[:30], n.lineno))
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            mods = [a.name.split('.')[0] for a in n.names] if isinstance(n, ast.Import) else [(n.module or '').split('.')[0]]
            for m in mods:
                if m not in ALLOWED_IMPORTS: flags.append('import %s (line %d)' % (m, n.lineno))
        if isinstance(n, ast.Name) and n.id in ('open', 'exec', 'eval', 'compile', '__import__', 'globals', 'locals', 'vars', 'input'):
            flags.append('%s (line %d)' % (n.id, n.lineno))
        if isinstance(n, ast.Attribute) and n.attr.startswith('__'):
            flags.append('dunder attribute %s (line %d)' % (n.attr, n.lineno))
    return flags


def cmd_code(task, room):
    plan = json.load(open(os.path.join(room, 'plan.json')))
    src = open(os.path.join(room, 'leaves.py')).read()
    flags = barrier_src(src)
    names = [l['name'] for l in plan.get('leaves', [])]
    ns = {}
    try:
        exec(compile(src, 'leaves.py', 'exec'), ns)
    except Exception as e:
        res = {'leaves.py': 'does not load: %s: %s' % (type(e).__name__, e)}
        log(room, 'code', res); print(json.dumps(res, indent=1)); return
    missing = [n for n in names if not callable(ns.get(n))]
    leaf_src = {n: src for n in names if n not in missing}
    st = states(task)
    try:
        P = program(task, plan, leaf_src)
    except Exception as e:
        res = {'static': 'rejected: %s' % str(e)[:500]}
        log(room, 'code', res); print(json.dumps(res, indent=1)); return
    res = {'barrier_flags': flags, 'not_defined': missing, 'demonstrations': {}, 'calls': {}}
    allx = True
    for d in demo_names(st):
        rec = []
        status, S, steps, sec = run(P, st[d + '_in'], record=rec)
        r = {'status': status, 'steps': steps}
        if status == 'ok':
            r['exact'] = S.sc['out'].render() == st[d + '_out']['grid']
            r['objects'] = {k: v for k, v in diff(S, st[d + '_out']).items() if k in ('matched', 'n_missing', 'n_extra')}
        else: r['exact'] = False
        allx = allx and r['exact']
        res['demonstrations'][d] = r
        res['calls'][d] = rec[:12]
        res['calls'][d + '_count'] = len(rec)
    for g in sorted(x for x in st if x.startswith('t')):
        status, S, steps, sec = run(P, st[g])
        res['demonstrations'][g] = {'status': status}
    res['exact_on_every_demonstration'] = allx
    res['accepted'] = allx and not flags and not missing
    log(room, 'code', {k: v for k, v in res.items() if k != 'calls'})
    out = json.dumps(res)
    if len(out) > 60000:
        for d in res['calls']:
            if isinstance(res['calls'][d], list): res['calls'][d] = res['calls'][d][:3]
    print(json.dumps(res, indent=1)[:120000])


def edge_tests(P, plan, c):
    """the plan's own relations of a construct: GOL tests of two nodes reachable from its realizing definition and its
    instance term (and any it lists under "edges"). -> {name: type key}; the key hashes the expanded body, so one
    definition is one edge type in every task"""
    from grain import parse, unparse
    sdefs, _, _ = store()
    defs = {d['name']: d for d in sdefs}
    defs.update({d['name']: d for d in plan.get('defs', [])})
    def heads(x, acc):
        if isinstance(x, list) and x:
            if isinstance(x[0], str): acc.add(x[0])
            for y in x[1:]: heads(y, acc)
        elif isinstance(x, str): acc.add(x)
        return acc
    todo = set(c.get('edges', []))
    rb = (c.get('realized_by') or {}).get('gol')
    if rb: todo.add(rb)
    if c.get('instance'):
        try: heads(parse(c['instance']), todo)
        except Exception: pass
    seen = set()
    while todo:
        n = todo.pop()
        if n in seen or n not in defs: continue
        seen.add(n)
        heads(parse(defs[n]['body']) if isinstance(defs[n]['body'], str) else defs[n]['body'], todo)
    out = {}
    for n in sorted(seen):
        d = defs[n]
        if d['kind'] == 'test' and len(d['params']) == 2:
            try:
                body = unparse(P.expand(['%s' % n, 900001, 900002]))
            except Exception:
                continue
            if not (_node_use(P.expand([n, 900001, 900002]), 900001) and _node_use(P.expand([n, 900001, 900002]), 900002)): continue
            out[n] = 'T:' + hashlib.sha1(body.replace('900001', '#1').replace('900002', '#2').encode()).hexdigest()[:6]
    return out


_NODE_ARG = {'color': (1,), 'ncolors': (1,), 'npix': (1,), 'size': (1,), 'top': (1,), 'left': (1,), 'bottom': (1,), 'right': (1,),
             'alive': (1,), 'dist': (1, 2), 'tag': (0,), 'inbounds': (0,), 'overlaps': (0,), 'free': (0,),
             'rcc': (1, 2), 'dir_rel': (1, 2), 'adjacent': (1, 2), 'aligned': (1, 2), 'allen': (1, 2), 'between': (1, 2, 3),
             'sees': (1, 2), 'on_ray': (1, 2), 'nearest': (1, 2), 'translate_of': (1, 2), 'reflection_of': (1, 2),
             'rotation_of': (1, 2), 'same_form': (1, 2), 'mirror_cell': (1, 2), 'period': (1, 2)}


def _node_use(x, v):
    """does value v appear in a node position of the expanded term x"""
    if not isinstance(x, list) or not x: return False
    h = x[0]; a = x[1:]
    if isinstance(h, str) and h in _NODE_ARG and any(i < len(a) and a[i] == v for i in _NODE_ARG[h]): return True
    return any(_node_use(y, v) for y in a)


def typed_edges(P, S, ids, tests):
    """evaluate each two-node test on every ordered pair of the instance's nodes in the state S"""
    R2 = G1.Run(P, FUEL)
    E = {}
    for name, key in tests.items():
        for a in ids:
            for b in ids:
                if a == b: continue
                R2.steps = 0
                try:
                    ok = R2.T(S, P.expand([name, a, b]))
                except BaseException:
                    ok = False
                if ok: E.setdefault((a, b), set()).add(key)
    return E


def cmd_instances(task, room, quiet=False, log_it=True):
    """each construct's instance term, run on every demonstration input: the typed graph of each instance
    (tables t9 = instance, t8 = role), its schema, by graph15"""
    import graph15
    from collections import Counter
    plan = json.load(open(os.path.join(room, 'plan.json')))
    st = states(task)
    out = {}
    for c in plan.get('constructs', []):
        term = c.get('instance')
        r = {'instances': 0, 'spread': Counter(), 'errors': [], 'roles': Counter()}
        if not term:
            r['errors'].append('no instance term'); out[c['name']] = r; continue
        try:
            P = program(task, dict(plan, main=term))
        except Exception as e:
            r['errors'].append('rejected: %s' % str(e)[:300]); out[c['name']] = r; continue
        tests = edge_tests(P, plan, c)
        r['edge_types'] = tests
        an = []
        for d in demo_names(st):
            status, S, steps, sec = run(P, st[d + '_in'])
            if status != 'ok': r['errors'].append('%s: %s' % (d, status)); continue
            nodes = S.sc['out'].nodes
            inst = {}
            for (t, i), v in S.tables.items():
                if t == 't9' and v and i in nodes: inst.setdefault(v, {})[i] = nodes[i]
                if t == 't8' and v and i in nodes: r['roles'][v] += 1
            for k, ns in sorted(inst.items()):
                typed = typed_edges(P, S, sorted(ns), tests) if tests and len(ns) > 1 else {}
                a = graph15.analyze(ns, typed, (S.sc['out'].H, S.sc['out'].W))
                if not a: continue
                r['spread'][(a['sig'], a['readable'])] += 1; r['instances'] += 1
                an.append(a)
        if r['spread']:
            (sig, readable), n = r['spread'].most_common(1)[0]
            r['signature'] = sig; r['graph'] = readable
            r['schema'] = graph15.schema(an)
        r['spread'] = {rd: n for (sg, rd), n in r['spread'].most_common()}
        r['roles'] = dict(r['roles'])
        out[c['name']] = r
    if log_it: log(room, 'instances', {k: {x: y for x, y in v.items() if x != 'schema'} for k, v in out.items()})
    if not quiet: print(json.dumps({k: {x: y for x, y in v.items() if x != 'schema'} for k, v in out.items()}, indent=1))
    return out


def cmd_scope(task, room, quiet=False, log_it=True):
    """does the plan meet, on the test inputs, constructs or bindings that no demonstration showed? Each construct's
    instance term runs on the demonstration inputs and on the test inputs; a test instance is flagged when its graph
    differs from every demonstration instance (PSI relational similarity < 0.95 over the typed edges and in, holds, touch,
    same shape and mirror; row, column, closeness and same size are incidental to placement and left out). Bindings a
    role's nodes never had on the demonstrations (symmetry pattern, colour count) are reported, not flagged. Object level only; no test output
    exists or is read."""
    import graph15
    plan = json.load(open(os.path.join(room, 'plan.json')))
    st = states(task)
    tests_in = sorted(g for g in st if g.startswith('t'))
    out = {}
    for c in plan.get('constructs', []):
        term = c.get('instance')
        if not term: continue
        try:
            P = program(task, dict(plan, main=term))
        except Exception as e:
            out[c['name']] = {'error': str(e)[:200]}; continue
        tests = edge_tests(P, plan, c)
        def collect(grids):
            an, nodes_by_role = [], {}
            for g in grids:
                status, S, steps, sec = run(P, st[g])
                if status != 'ok': continue
                nodes = S.sc['out'].nodes
                inst = {}
                for (t, i), v in S.tables.items():
                    if t == 't9' and v and i in nodes: inst.setdefault(v, {})[i] = nodes[i]
                roles = {i: v for (t, i), v in S.tables.items() if t == 't8' and v}
                for k, ns in inst.items():
                    typed = typed_edges(P, S, sorted(ns), tests) if tests and len(ns) > 1 else {}
                    a = graph15.analyze(ns, typed, (S.sc['out'].H, S.sc['out'].W))
                    if a: an.append((g, a))
                    for o, p in ns.items():
                        na = graph15.node_attrs(p)
                        nodes_by_role.setdefault(roles.get(o, 0), []).append((g, tuple(na[4:]), int(na[1]), len(p)))
            return an, nodes_by_role
        dan, dnodes = collect([d + '_in' for d in demo_names(st)])
        tan, tnodes = collect(tests_in)
        sch = graph15.schema([a for g, a in dan])
        r = {'demo_instances': len(dan), 'test_instances': len(tan), 'graph_flags': [], 'binding_flags': [], 'size_outside': []}
        dsch = [graph15.schema([a]) for g, a in dan]
        for g, a in tan:
            ta = graph15.schema([a])
            sim = max([graph15.similarity(ta, x, 0.0, graph15.INCIDENTAL) for x in dsch] or [0.0])
            if sim < 0.95: r['graph_flags'].append({'grid': g, 'graph': a['readable'][:160], 'nearest_demo_similarity': sim})
        for role, ns in tnodes.items():
            seen_sym = {x[1] for x in dnodes.get(role, [])}; seen_col = {x[2] for x in dnodes.get(role, [])}
            sizes = [x[3] for x in dnodes.get(role, [])]
            for g, sym, nc, sz in ns:
                if sym not in seen_sym or nc not in seen_col:
                    r['binding_flags'].append({'grid': g, 'role': role, 'symmetries': sym, 'colours': nc, 'size': sz})
                if sizes and not (min(sizes) <= sz <= max(sizes)):
                    r['size_outside'].append({'grid': g, 'role': role, 'size': sz, 'demo_range': [min(sizes), max(sizes)]})
        out[c['name']] = r
    if log_it: log(room, 'scope', out)
    if not quiet: print(json.dumps(out, indent=1))
    return out


def log(room, kind, res):
    with open(os.path.join(room, 'check_log.jsonl'), 'a') as f:
        f.write(json.dumps({'kind': kind, 'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'result': res})[:200000] + '\n')


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'check': cmd_check(sys.argv[2], sys.argv[3])
    elif c == 'probe': cmd_probe(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif c == 'objects': cmd_objects(sys.argv[2], sys.argv[3])
    elif c == 'code': cmd_code(sys.argv[2], sys.argv[3])
    elif c == 'instances': cmd_instances(sys.argv[2], sys.argv[3])
    elif c == 'scope': cmd_scope(sys.argv[2], sys.argv[3])
    else: raise SystemExit(__doc__)

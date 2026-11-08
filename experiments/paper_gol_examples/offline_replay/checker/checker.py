"""The study checker (protocol draft v2.2, sections 1, 4, 5, 7). No LLM.
  python3 checker.py <room.meta.json> <plan.json> <out_dir> [--mode=reader]
Every mode, every condition:
- the program runs on the room's frozen view and on the room's execution store (A and B: an explicit empty store, so a
  library call that does not resolve is rejected);
- operation boundary, enforced at execution: (split o 1), (new k) and (segment ...) abort the run;
- literal node numbers: the expanded program is scanned (an integer where an act expects a node), and every demonstration
  is run twice, with node numbering starting at 1 and at 1001; different results mean the program depends on node numbers
  (also when they are computed, e.g. (set o 1)) and it is rejected.
reader mode: pass/fail per SEEN demonstration and one feedback picture (input, expected, produced): nothing else.
final mode: adds the HIDDEN demonstration (independent validation, run once, never used for ranking), ARCGraph = mirror
after every act, and a full trace (<out>/trace.json): expanded program, every act with the graph rendering after it,
guard-comparison provenance (operator, operand terms with registers resolved to node handles, values, result), relation
witnesses, and the manifest of every source file opened (sha256). verdict.json summarises it."""
import hashlib, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as CM, relations as REL

ACTS_NODE = ('recolor', 'move', 'extend', 'shrink', 'border', 'fillrect', 'hollow', 'flip', 'rotate', 'copy', 'delete', 'merge', 'split')
FORBIDDEN_HEADS = ('new', 'segment')
MAX_GUARDS = 2000
NODE_ATTRS = ('top', 'bottom', 'left', 'right', 'size', 'height', 'width', 'ncolors', 'colour', 'color')


def expanded_violations(term, out=None):
    """scan the EXPANDED program (store definitions included): integer literal as a node argument, literal (split o 1),
    forbidden heads"""
    out = [] if out is None else out
    if isinstance(term, list) and term:
        h = term[0]
        if h in ACTS_NODE and len(term) > 1 and isinstance(term[1], int): out.append('literal node %d in (%s ...)' % (term[1], h))
        if h == 'merge' and len(term) > 2 and isinstance(term[2], int): out.append('literal node %d in (merge ...)' % term[2])
        if h == 'split' and len(term) > 2 and term[2] == 1: out.append('(split o 1): single pieces')
        if h in FORBIDDEN_HEADS: out.append('(%s ...) is forbidden' % h)
        for t in term[1:]: expanded_violations(t, out)
    return out


def main(metap, planp, outd, mode='--mode=final'):
    final = 'reader' not in mode
    meta = json.load(open(metap)); plan = json.load(open(planp)); outd = os.path.abspath(outd); os.makedirs(outd, exist_ok=True)
    work = os.path.join(outd, '_runtime'); os.makedirs(work, exist_ok=True)
    rt = CM.runtime_room(meta['task'], work)
    os.environ['STORE15'] = meta['store_exec']   # every condition names its execution store; A and B: the empty store
    OPENED = set(); r7 = os.path.realpath(CM.R7) + os.sep; rr = os.path.realpath(rt) + os.sep
    def hook(ev, args):
        if ev == 'open' and args and isinstance(args[0], str):
            q = os.path.realpath(args[0])
            if (q.startswith(r7) or q.startswith(rr) or q.startswith(os.path.realpath(meta['store_exec']))) and '__pycache__' not in q and os.path.isfile(q): OPENED.add(q)
    if final: sys.addaudithook(hook)
    GOL = CM.enter(rt)
    import arcroom as AR
    Dm = GOL.D
    view = meta['view']; spec = {'abstraction': view['abstraction'], 'background': view['background'], 'derive': None}
    verdict = {'key': meta['key'], 'condition': meta['condition'], 'order': meta['order'], 'view': [view['abstraction'], view['background']],
               'store_exec_sha256': meta.get('store_exec_sha256'), 'registry': json.load(open(os.path.join(rt, 'REGISTRY.json')))}
    # ---- operation boundary at execution
    for name, why in (('new', '(new k) is forbidden'), ('segment', '(segment ...) is forbidden')):
        def forb(self, *a, why=why): raise Dm.Refused(why)
        setattr(Dm.GolScene, name, forb)
    orig_split = Dm.GolScene.split
    def split(self, o, m, tick):
        if m == 1: raise Dm.Refused('(split o 1) is forbidden')
        return orig_split(self, o, m, tick)
    Dm.GolScene.split = split
    # ---- final-mode instrumentation: acts (graph = mirror, rendering), guard comparisons
    log = {'acts': [], 'guards': [], 'mismatch': 0}
    def gstate(sc):
        res = {}
        for h, k in sc.key.items():
            nd = sc.G.graph.nodes[k]; pts = [tuple(map(int, p)) for p in nd['nodes']]
            cl = nd['color'] if isinstance(nd['color'], list) else [nd['color']] * len(pts)
            res[h] = dict(zip(pts, map(int, cl)))
        return res
    def grender(sc):
        g = [[sc.bg] * sc.W for _ in range(sc.H)]
        for h, p in sorted(gstate(sc).items()):
            for (y, x), c in p.items():
                if 0 <= y < sc.H and 0 <= x < sc.W: g[y][x] = c
        return g
    if final:
        for name in Dm.ACTS:
            if name in ('new',): continue
            orig = getattr(Dm.GolScene, name)
            def wrap(orig=orig, name=name):
                def f(self, *a):
                    r = orig(self, *a); gs = gstate(self)
                    eq = all(gs.get(h) == p for h, p in self.mir.items()) and set(gs) == set(self.mir)
                    if not eq: log['mismatch'] += 1
                    log['acts'].append({'op': name, 'args': [x for x in a[:-1] if isinstance(x, (int, str))], 'returned': r,
                                        'graph_equals_mirror': eq, 'render_from_graph': grender(self)})
                    return r
                return f
            setattr(Dm.GolScene, name, wrap())
        origT = GOL.Run.T
        def T(self, S, b):
            r = origT(self, S, b)
            if isinstance(b, list) and b and b[0] in ('=', '!=', '<', '<=') and len(log['guards']) < MAX_GUARDS:
                def res(t):   # operand term with registers resolved to their values at this moment
                    if isinstance(t, list):
                        out = [t[0]] + [res(x) for x in t[1:]]
                        if t[0] in NODE_ATTRS and len(t) == 3 and isinstance(t[1], str):   # attribute of a node: keep its geometry
                            try:
                                h = self.E(S, t[2]); sc = S.scene(t[1])
                                if sc.alive(h): out.append({'members': sorted([y, x] for (y, x) in sc.mir[h]), 'colours': [sc.mir[h][q] for q in sorted(sc.mir[h])]})
                            except Exception: pass
                        return out
                    if isinstance(t, str) and t in S.r: return {'reg': t, 'value': S.r[t]}
                    return t
                try: u, v = self.E(S, b[1]), self.E(S, b[2])
                except Exception: u = v = None
                log['guards'].append({'op': b[0], 'left': res(b[1]), 'right': res(b[2]), 'values': [u, v], 'result': r})
            return r
        GOL.Run.T = T
    try:
        P = GOL.program(meta['task'], {'task': meta['task'], 'main': plan['main'], 'defs': plan.get('defs', []),
                                       **{k: v for k, v in plan.items() if k not in ('main', 'defs')}}, traced=final)
    except Exception as e:   # e.g. a call to a definition that neither the plan nor the execution store defines
        verdict.update({'static_violations': ['program rejected before running: %s: %s' % (type(e).__name__, str(e)[:200])],
                        'seen': {str(i): {'pass': False, 'error': 'rejected'} for i in meta['seen']}, 'all_seen_pass': False})
        if final: verdict.update({'hidden': {str(i): {'pass': False, 'error': 'rejected'} for i in meta['hidden']},
                                  'independent_validation': (False if meta['hidden'] else None), 'void': False,
                                  'arcgraph_equals_mirror': {'acts_checked': 0, 'mismatches': 0}})
        json.dump(verdict, open(os.path.join(outd, 'verdict.json' if final else 'reader_feedback.json'), 'w'), indent=1, sort_keys=True, default=str)
        print(json.dumps({'key': verdict['key'], 'condition': verdict['condition'], 'rejected': verdict['static_violations'][0][:160]})); return
    static = expanded_violations(P.expanded)
    verdict['static_violations'] = static

    def run(i, base=1, record=False):
        name = 'd%d_in' % i
        G, H, W, bg = Dm.reading(name, spec['abstraction'], spec['background'], None)
        S = GOL.State(Dm.GolScene.of_graph(G, H, W, bg, [base]))
        R = (GOL.TRun(P, GOL.FUEL * 10, {}) if final else GOL.Run(P, GOL.FUEL * 10))
        a0, g0 = len(log['acts']), len(log['guards'])
        try:
            R.do(S, P.expanded); out = S.sc['out'].render(); err = None
        except Exception as e:
            out, err = None, '%s: %s' % (type(e).__name__, str(e)[:200])
        rec = None
        if record:
            sin = S.sc['in']; wit = []
            for e in getattr(R, 'events', []):
                nodes = {}
                for rname, v in e['roles'].items():
                    if sin.alive(v):
                        pts = sorted(sin.mir[v]); nodes[rname] = {'members': [list(p) for p in pts], 'colours': [sin.mir[v][p] for p in pts]}
                wit.append({'def': e['def'], 'roles': e['roles'], 'effect': e.get('shape'), 'relations': REL.relations(nodes) if len(nodes) >= 2 else {}})
            rec = {'acts': log['acts'][a0:], 'guards': log['guards'][g0:], 'witnesses': wit}
        else:
            del log['acts'][a0:]; del log['guards'][g0:]
        return out, err, rec

    trace = {'expanded_program': P.expanded, 'demos': {}}
    def judge(i, record):
        out, err, rec = run(i, 1, record); out2, err2, _ = run(i, 1001, False)
        literal = (out != out2) or ((err is None) != (err2 is None))
        ok = (out == AR._GRIDS['d%d_out' % i]) and not static and not literal
        row = {'pass': ok, 'error': err, 'depends_on_node_numbers': literal}
        if rec is not None: trace['demos'][str(i)] = dict(rec, output=out, error=err)
        return row, out

    seen = {}; first_fail = None
    for i in meta['seen']:
        row, out = judge(i, final); seen[str(i)] = row
        if not row['pass'] and first_fail is None: first_fail = (i, out)
    verdict['seen'] = seen
    if first_fail is not None and first_fail[1] is not None:
        i, out = first_fail
        CM.picture([{'input': AR._GRIDS['d%d_in' % i], 'output': AR._GRIDS['d%d_out' % i]}, {'input': AR._GRIDS['d%d_in' % i], 'output': out}],
                   os.path.join(outd, 'feedback.png'))
    verdict['all_seen_pass'] = all(v['pass'] for v in seen.values())
    if final:
        hid = {}
        for i in meta['hidden']:
            row, _ = judge(i, True); hid[str(i)] = row
        verdict['hidden'] = hid
        verdict['independent_validation'] = (all(v['pass'] for v in hid.values()) if hid else None)
        verdict['validation_kind'] = 'hidden demonstration (never used for ranking)' if hid else 'conditional only (fewer than 3 demonstrations)'
        verdict['arcgraph_equals_mirror'] = {'acts_checked': sum(len(d['acts']) for d in trace['demos'].values()), 'mismatches': log['mismatch']}
        verdict['void'] = bool(log['mismatch'])
        trace['opened_sources_sha256'] = {os.path.relpath(f, CM.R7 if f.startswith(r7) else os.path.dirname(rr.rstrip(os.sep))).replace(os.sep, '/'): CM.sha(f) for f in sorted(OPENED)}
        txt = json.dumps(trace, sort_keys=True, default=str)
        open(os.path.join(outd, 'trace.json'), 'w').write(txt); verdict['trace_sha256'] = hashlib.sha256(txt.encode()).hexdigest()
        verdict['guards_recorded'] = sum(len(d['guards']) for d in trace['demos'].values())
    json.dump(verdict, open(os.path.join(outd, 'verdict.json' if final else 'reader_feedback.json'), 'w'), indent=1, sort_keys=True, default=str)
    print(json.dumps({k: verdict.get(k) for k in ('key', 'condition', 'all_seen_pass', 'independent_validation', 'static_violations', 'arcgraph_equals_mirror', 'void', 'guards_recorded')}, default=str))


if __name__ == '__main__': main(*sys.argv[1:])

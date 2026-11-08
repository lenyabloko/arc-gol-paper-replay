"""Container: the GOL interpreter over ARCGraph, and the tracer of contract instances.

Ports and adapters: GOL's primitive signature is the port; the ARCGraph GOL extension (cx2/dsl/gol_arcgraph.py) is
the adapter, behind the barrier. The interpreter holds handles, values, registers, tags and tables. Every primitive
is a call into the DSL with handles and values; no subnode reaches this file. Programs are parsed, checked and
expanded by GRAIN-1's Program (control level only; no new leaves: Python leaves would be code past the port).

Tracing: every call of a traced definition is bracketed at expansion (cx_trace.TProgram). When a call returns, the DSL
describes, from a snapshot taken when it started: its effect relative to its roles, the roles' attributes (ARCGraph's
methods), the typed relations among them, their symmetries, and their place in Image's readings of the same grid.
The relations among the roles that are input nodes are also read in the input scene (edges_in): the precondition as
the input states it, not as the plan's working state has it.
Run inside a room (arcroom.py, task.json, spec.json, scenes12.json).
usage: python3 gol.py trace <task> <plan.json> <out.json>
       python3 gol.py run <task> <plan.json> <out.json>        outputs of every demonstration and test input"""
import json, os, sys
ROOM = os.getcwd(); sys.path.insert(0, ROOM)
HERE = os.path.dirname(os.path.abspath(__file__))
R15 = '/home/claude/work/r7/room15'
for p in (os.path.join(HERE, '..', 'dsl'), os.path.join(R15, 'grain'), R15): sys.path.insert(0, p)
import arcroom as AR                    # noqa: E402  (sets the ARCGraph path)
import grain1 as G1                     # noqa: E402
import gol_arcgraph as D                # noqa: E402

FUEL = 3_000_000
MAX_EVENTS = 1500
MAY_CREATE = ('border', 'fillrect', 'copy', 'split', 'new')


class State:
    def __init__(self, scene_in):
        self.sc = {'in': scene_in, 'out': scene_in.clone()}
        self.last = -1; self.r = {}; self.tags = {}; self.tables = {}; self.th = 0; self.mode = 'modal'

    def scene(self, name):
        if name not in self.sc: raise G1.Abort('no scene %s' % name)
        return self.sc[name]

    def settag(self, o, v):
        old = self.tags.get(o, 0)
        if old != v: self.th ^= G1._zh(1, o, old) ^ G1._zh(1, o, v)
        self.tags[o] = v

    def put(self, t, i, v):
        old = self.tables.get((t, i), 0); ti = G1.TABLES.index(t) + 2
        if old != v: self.th ^= G1._zh(ti, i, old) ^ G1._zh(ti, i, v)
        self.tables[(t, i)] = v

    def key(self):
        s = self.sc['out']
        return (s.hsum, self.th, s.H, s.W, s.bg, frozenset(self.r.items()), self.last, s.ids[0])


def start(name, spec_in):
    """the starting state of grid `name` under the planner's reading (an ARCGraph, built by the DSL)"""
    G, H, W, bg = D.reading(name, spec_in['abstraction'], spec_in['background'], spec_in.get('derive'))
    return State(D.GolScene.of_graph(G, H, W, bg, [1]))


class Run:
    def __init__(self, prog, fuel=FUEL):
        self.p, self.fuel, self.steps, self.max_loop_iters = prog, fuel, 0, 0

    def tick(self, n=1):
        self.steps += n
        if self.steps > self.fuel: raise G1.OutOfFuel('step bound %d reached' % self.fuel)

    def call(self, f, *a):
        try: return f(*a)
        except D.Refused as e: raise G1.Abort(str(e))

    def h(self, S, sc, e):
        o = self.E(S, e)
        if not S.scene(sc).alive(o): raise G1.Abort('%s has no node %s' % (sc, o))
        return o

    def E(self, S, e):
        if isinstance(e, int): return e
        if isinstance(e, str): return S.r.get(e, 0)
        self.tick(); h = e[0]; a = e[1:]
        if h == '+': return self.E(S, a[0]) + self.E(S, a[1])
        if h == '-': return self.E(S, a[0]) - self.E(S, a[1])
        if h == 'first':
            ks = S.scene(a[0]).handles(); return min(ks) if ks else -1
        if h == 'next':
            o = self.E(S, a[1]); ks = [k for k in S.scene(a[0]).handles() if k > o]; return min(ks) if ks else -1
        if h == 'count': return len(S.scene(a[0]).handles())
        if h == 'last': return S.last
        if h in ('color', 'ncolors', 'size', 'top', 'left', 'bottom', 'right'):
            return self.call(S.scene(a[0]).attr, h, self.h(S, a[0], a[1]), self.tick)
        if h == 'npix': return self.call(S.scene(a[0]).npix, self.h(S, a[0], a[1]), self.E(S, a[2]))
        if h == 'H': return S.scene(a[0]).H
        if h == 'W': return S.scene(a[0]).W
        if h == 'bg': return S.scene(a[0]).bg
        if h == 'tag': return S.tags.get(self.E(S, a[0]), 0)
        if h == 'get': return S.tables.get((a[0], self.E(S, a[1])), 0)
        if h == 'dist': return self.call(S.scene(a[0]).dist, self.h(S, a[0], a[1]), self.h(S, a[0], a[2]), self.tick)
        raise G1.Abort('unknown operator at run time: %s' % h)

    def d(self, S, e):
        d = self.E(S, e)
        if not (isinstance(d, int) and 0 <= d < 8): raise G1.Abort('direction out of range: %s' % d)
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
        if h == 'alive': return S.scene(a[0]).alive(self.E(S, a[1]))
        out = S.sc['out']
        if h == 'inbounds': return self.call(out.inbounds, self.h(S, 'out', a[0]))
        if h == 'free': return self.call(out.free, self.h(S, 'out', a[0]), self.d(S, a[1]), self.tick)
        if h == 'overlaps': return self.call(out.overlaps, self.h(S, 'out', a[0]), self.tick)
        if h in D.TESTS:
            sc = S.scene(a[0]); o = self.h(S, a[0], a[1]); p = self.h(S, a[0], a[2])
            if h == 'rcc': x = [a[3]]
            elif h == 'between': x = [self.h(S, a[0], a[3]), self.E(S, a[4])]
            elif h in ('dir_rel', 'adjacent', 'on_ray'): x = [self.d(S, a[3])]
            elif h in ('allen', 'period'): x = [self.E(S, a[3]), self.E(S, a[4])]
            elif h in ('nearest', 'translate_of', 'same_form'): x = []
            else: x = [self.E(S, a[3])]
            if h == 'between': return self.call(sc.between, o, p, x[0], x[1], self.tick)
            return self.call(getattr(sc, h), o, p, *x, self.tick)
        raise G1.Abort('unknown test at run time: %s' % h)

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
                if k in seen: raise G1.NonTerminating('state repeats at a while head: %s' % G1.unparse(a[0])[:80])
                seen.add(k); n += 1
                self.do(S, a[1])
            self.max_loop_iters = max(self.max_loop_iters, n)
            return
        if h == 'set': S.r[a[0]] = self.E(S, a[1]); return
        if h == 'settag': S.settag(self.E(S, a[0]), self.E(S, a[1])); return
        if h == 'put': S.put(a[0], self.E(S, a[1]), self.E(S, a[2])); return
        out = S.sc['out']
        if h == 'canvas': return self.call(out.canvas, self.E(S, a[0]), self.E(S, a[1]), self.E(S, a[2]))
        if h == 'segment':
            S.sc['out'] = self.call(out.segment, a[0], S.mode, self.tick); S.last = -1; return
        if h in D.ACTS:
            if h == 'new': args = [self.E(S, a[0])]
            else:
                o = self.h(S, 'out', a[0])
                if h in ('move', 'extend', 'shrink'): args = [o, self.d(S, a[1])]
                elif h == 'merge': args = [o, self.h(S, 'out', a[1])]
                elif h in ('recolor', 'border', 'fillrect', 'flip', 'split'): args = [o, self.E(S, a[1])]
                else: args = [o]
            made = self.call(getattr(out, h), *args, self.tick)
            if h in MAY_CREATE: S.last = made[-1] if made else -1
            return
        raise G1.Abort('unknown act at run time: %s' % h)


class TRun(Run):
    """the tracer: each bracketed call becomes a contract instance, described by the DSL"""

    def __init__(self, prog, fuel, readings):
        super().__init__(prog, fuel)
        self.stack, self.events, self.readings = [], [], readings

    def do(self, S, t):
        h = t[0] if isinstance(t, list) and t else None
        if h == '__b':
            n = t[2]; vals = []
            for e in t[3:3 + n]:
                try: vals.append(self.E(S, e))
                except Exception: vals.append(None)
            regs = {r: S.r.get(r) for r in t[3 + n:]}
            out = S.sc['out']
            self.stack.append((t[1], vals, out.clone(), (out.H, out.W, out.bg), regs, S.last))
            return
        if h == '__e':
            name, vals, before, dims, regs0, last0 = self.stack.pop()
            after = S.sc['out']; dims2 = (after.H, after.W, after.bg)
            if len(self.events) >= MAX_EVENTS or (before.mir == after.mir and dims == dims2): return
            roles = {}
            for i, v in enumerate(vals):
                if isinstance(v, int) and before.alive(v): roles['p%d' % i] = v
            for r, v in regs0.items():
                if isinstance(v, int) and before.alive(v) and v not in vals: roles['g:' + r] = v
            if before.alive(last0): roles['last'] = last0
            shape, obs, gen = D.effect(before, after, roles, dims, dims2)
            ev = {'def': name, 'args': vals, 'roles': roles, 'shape': shape, 'obs': obs, 'generative': gen}
            if shape and not all(s.startswith('side') for s in shape):
                ev['attrs'] = {r: D.attrs(before, v) for r, v in roles.items()}
                ev['edges'] = sorted([a, b, l] for a in roles for b in roles if a != b
                                     for l in D.relations(before, roles[a], roles[b]))
                sin = S.sc['in']                       # the same roles read in the input scene, where they are input nodes
                rin = {r: v for r, v in roles.items() if sin.alive(v)}
                ev['edges_in'] = sorted([a, b, l] for a in rin for b in rin if a != b for l in D.relations(sin, rin[a], rin[b]))
                ev['input_roles'] = sorted(rin)
                ev['symmetries'] = {r: D.symmetries(before, v) for r, v in roles.items()}
                ev['places'] = {r: D.place(before, v, self.readings) for r, v in roles.items()} if self.readings else {}
            self.events.append(ev)
            return
        return super().do(S, t)


def program(task, plan, traced=False):
    import serve15 as SV
    SV.DATA = os.environ.get('DATA15', SV.DATA)
    P0 = SV.program(task, plan)
    tr = {'task': task, 'basis': 'obj1', 'abstraction': 'nbccg', 'bg': plan.get('bg', 'modal'),
          'defs': [{'name': n, 'kind': d['kind'], 'params': d['params'], 'body': d['body']} for n, d in P0.defs.items()],
          'leaves': [], 'main': plan['main']}
    if not traced: return G1.Program(tr)
    import cx_trace as CT
    CT.TProgram.traced = {n for n, d in P0.defs.items() if d['kind'] == 'act'}
    return CT.TProgram(tr)


def demo_names():
    return sorted({g[:-3] for g in AR.grid_names() if g.startswith('d') and g.endswith('_in')}, key=lambda d: int(d[1:]))


def run_grid(P, name, spec_in, fuel=FUEL * 10):
    S = start(name, spec_in); R = Run(P, fuel)
    try:
        R.do(S, P.expanded); return S.sc['out'].render(), None
    except Exception as e:
        return None, '%s: %s' % (type(e).__name__, str(e)[:200])


def main():
    mode, task, plan_f, out = sys.argv[1:5]
    plan = json.load(open(plan_f)); spec = json.load(open('spec.json'))
    if mode == 'run':
        P = program(task, plan); res = {'task': task, 'grids': {}}
        for g in AR.grid_names():
            if g.endswith('_out'): continue
            grid, err = run_grid(P, g, spec['in'])
            res['grids'][g] = {'grid': grid, 'error': err}
        json.dump(res, open(out, 'w'))
        print(json.dumps({'task': task, 'errors': sum(1 for v in res['grids'].values() if v['error'])}))
        return
    P = program(task, plan, traced=True)
    res = {'task': task, 'demos': {}}
    for d in demo_names():
        rd = D.offers(d + '_in', spec, 'scenes12.json')
        S = start(d + '_in', spec['in']); R = TRun(P, FUEL * 10, rd)
        try:
            R.do(S, P.expanded); err = None
            exact = S.sc['out'].render() == AR._GRIDS[d + '_out']
        except Exception as e:
            exact, err = False, '%s: %s' % (type(e).__name__, str(e)[:200])
        res['demos'][d] = {'exact': exact, 'error': err, 'events': R.events, 'readings': sorted(rd)}
    json.dump(res, open(out, 'w'))
    print(json.dumps({'task': task, 'demos': {d: [v['exact'], len(v['events']), v['error']] for d, v in res['demos'].items()}}))


if __name__ == '__main__':
    main()

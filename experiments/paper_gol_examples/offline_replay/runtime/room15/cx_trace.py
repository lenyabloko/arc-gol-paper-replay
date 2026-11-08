"""Contracts learned from the LLM's GOL plans by tracing (action-model learning; Len, Oct 29: "build full solution to
our tasks", contracts = precondition graph + effect, identity up to polymorphism and graph isomorphism).

For every exact plan (plan15/<task>, plan15b/<task>): run its main on each demonstration input in GRAIN-1, with every
call of a node-taking act definition bracketed by markers. Each call is a contract instance:
  - the arguments (node ids and values) and the state of the scene when the call starts;
  - the effect: the nodes that changed, were created or were deleted when it returns.
The instances are written to cx/<task>.json for cx_learn.py, which folds them into contract schemas.
usage: python3 cx_trace.py <task> <plan room dir> <data dir>"""
import json, os, sys, copy
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'grain'))
import grain1 as G1

OUT = '/home/claude/work/r7/cx'
MAX_EVENTS = 1500


class TProgram(G1.Program):
    """expansion brackets each call of a traced act definition with markers"""
    traced = set()

    def _check(self, x, kind, params, where):
        if isinstance(x, list) and x and x[0] in ('__b', '__e'): return
        return super()._check(x, kind, params, where)

    def expand(self, x, depth=0):
        if depth > 60: raise G1.GrainError('definition nesting too deep (recursive definition?)')
        if not isinstance(x, list): return x
        h = x[0]
        if isinstance(h, str) and h in self.defs:
            d = self.defs[h]
            args = [self.expand(y, depth) for y in x[1:]]
            body = self.expand(G1._subst(d['body'], dict(zip(d['params'], args))), depth + 1)
            if h in self.traced:
                regs = sorted(registers(d['body'], set(d['params']), self))
                return ['seq', ['__b', h, len(args)] + args + regs, body, ['__e', h, regs]]
            return body
        return [h] + [self.expand(y, depth) for y in x[1:]]


import re


def registers(x, params, prog, acc=None):
    """register names a definition's body reads or writes (bare symbols that are not operators, parameters, scene names
    or tables)"""
    acc = set() if acc is None else acc
    if isinstance(x, str):
        if x not in params and x not in G1.SIG and x not in prog.defs and x not in prog.leaves and x not in ('in', 'out') \
                and not re.fullmatch(r't\d', x) and not x.startswith('_'):
            acc.add(x)
    elif isinstance(x, list):
        for i, y in enumerate(x):
            if i == 0 and isinstance(y, str): continue
            registers(y, params, prog, acc)
    return acc


class TRun(G1.Run):
    def __init__(self, prog, fuel):
        super().__init__(prog, fuel)
        self.stack, self.events = [], []

    def do(self, S, t):
        h = t[0] if isinstance(t, list) and t else None
        if h == '__b':
            n = t[2]; vals = []
            for e in t[3:3 + n]:
                try: vals.append(self.E(S, e))
                except Exception: vals.append(None)
            regs = {r: S.r.get(r) for r in t[3 + n:]}
            self.stack.append((t[1], vals, {o: dict(p) for o, p in S.sc['out'].nodes.items()}, S.next_id,
                               (S.sc['out'].H, S.sc['out'].W, S.sc['out'].bg), regs, S.last))
            return
        if h == '__e':
            name, vals, before, nid0, dims, regs0, last0 = self.stack.pop()
            if len(self.events) < MAX_EVENTS:
                after = S.sc['out'].nodes
                changed = {o: [sorted([y, x, c] for (y, x), c in before[o].items()), sorted([y, x, c] for (y, x), c in after[o].items())]
                           for o in before if o in after and after[o] != before[o]}
                deleted = [o for o in before if o not in after]
                created = {o: sorted([y, x, c] for (y, x), c in after[o].items()) for o in after if o not in before}
                if changed or deleted or created or dims != (S.sc['out'].H, S.sc['out'].W, S.sc['out'].bg):
                    args_nodes = {i: sorted([y, x, c] for (y, x), c in before[v].items())
                                  for i, v in enumerate(vals) if isinstance(v, int) and v in before}
                    reg_nodes = {r: sorted([y, x, c] for (y, x), c in before[v].items()) for r, v in regs0.items()
                                 if isinstance(v, int) and v in before and v not in vals}
                    regs_after = {r: S.r.get(r) for r in regs0}
                    self.events.append({'def': name, 'args': vals, 'arg_nodes': args_nodes, 'reg_nodes': reg_nodes,
                                        'reg_ids': {r: v for r, v in regs0.items() if isinstance(v, int) and v in before},
                                        'last_before': sorted([y, x, c] for (y, x), c in before[last0].items()) if last0 in before else None,
                                        'changed': changed,
                                        'deleted': deleted, 'created': created,
                                        'scene_before': {o: sorted([y, x, c] for (y, x), c in p.items()) for o, p in before.items()},
                                        'dims_before': list(dims), 'dims_after': [S.sc['out'].H, S.sc['out'].W, S.sc['out'].bg]})
            return
        return super().do(S, t)


def main():
    task, room, data = sys.argv[1], sys.argv[2], sys.argv[3]
    os.environ['DATA15'] = data
    import importlib
    import serve15 as SV
    SV.DATA = data
    plan = json.load(open(os.path.join(room, 'plan.json')))
    st = SV.states(task)
    P0 = SV.program(task, plan)                      # store + own definitions, as the harness builds them
    acts = {n for n, d in P0.defs.items() if d['kind'] == 'act'}      # procedures too: their nodes come through registers
    TProgram.traced = acts
    tr = {'task': task, 'basis': 'obj1', 'abstraction': 'nbccg', 'bg': plan.get('bg', 'modal'),
          'defs': [{'name': n, 'kind': d['kind'], 'params': d['params'], 'body': d['body']} for n, d in P0.defs.items()],
          'leaves': [], 'main': plan['main']}
    P = TProgram(tr)
    own = {d['name'] for d in plan.get('defs', [])}
    res = {'task': task, 'traced_defs': len(acts), 'demos': {}}
    for d in SV.demo_names(st):
        S = SV.make_state(st[d + '_in'])
        R = TRun(P, SV.FUEL * 10)
        try:
            R.do(S, P.expanded)
            exact = S.sc['out'].render() == st[d + '_out']['grid']
            err = None
        except Exception as e:
            exact, err = False, '%s: %s' % (type(e).__name__, str(e)[:200])
        res['demos'][d] = {'exact': exact, 'error': err, 'events': R.events,
                           'own_defs': sorted({e['def'] for e in R.events} & own)}
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, task + '.json'), 'w'))
    print(json.dumps({'task': task, 'traced_defs': len(acts),
                      'demos': {d: [v['exact'], len(v['events']), v['error']] for d, v in res['demos'].items()}}))


if __name__ == '__main__':
    main()

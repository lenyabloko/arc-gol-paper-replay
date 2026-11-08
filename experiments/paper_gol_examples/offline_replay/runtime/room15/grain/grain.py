"""GRAIN-0: derivations over a minimal cell-level basis (Fable v35 M1; design_revision_minimal_grain_oct14 R1-R3).

A translation is a JSON object
  {"task": id, "basis": "cell" | "obj", "defs": [DEF...], "leaves": [LEAF...], "main": TERM}
  DEF  = {"name", "kind": "act" | "test" | "expr", "params": [names], "body": S-expression string}
  LEAF = {"name", "kind": "act" | "test" | "expr", "params": [names], "pre": text, "effect": text,
          "py": "def <name>(S, *args): ..."}   -- a NEW leaf, declared only where no term over the basis fits
Terms, tests and expressions are S-expressions (README.md has the full grammar and the basis table).
Definitions are macros: a use is replaced by the body with the parameters substituted (static expansion), so they may
not be recursive (a definition may use only definitions listed before it). Recursion is While.

State: grids `in` (read-only), `out` (initially a copy of `in`: the identity is the interface default), scratch grids
s0..s9 (unallocated until `canvas`), and integer registers (any other lower-case name; unset registers read as 0).
Directions 0..7 = N, E, S, W, NE, SE, SW, NW. Reading outside a grid gives -1; writing outside a grid aborts the run.

Ruler (R3): L(t) = number of operator nodes of the statically expanded term (control constructors, basis actions,
tests and expression operators, declared leaves); operands (literals, register and grid names) are free; a loop counts
once. Execution: guards are evaluated outermost-first and lazily (and/or short-circuit left to right).
Termination (R3, rev 5): a run has a step bound (FUEL operator evaluations); at every While head the full state
(registers and grids, registers exactly, grids via an incremental hash) is recorded for that loop entry; a repeated state at the same loop
entry means the loop cannot terminate (the run is deterministic) and the run is rejected as non-terminating. A state
that never repeats at the loop head is the well-foundedness witness on the trace (the measure: steps to exit, finite
because the run ended within the bound)."""
import json, re

DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1), (-1, 1), (1, 1), (1, -1), (-1, -1)]   # N E S W NE SE SW NW
GRIDS = ('in', 'out') + tuple('s%d' % i for i in range(10))
GID = {g: i for i, g in enumerate(GRIDS)}
FUEL = 3_000_000

CONTROL = {'skip', 'seq', 'if', 'while'}
ACTIONS = {'canvas': 4, 'paint': 4, 'copy': 6, 'set': 2, 'step': 3}
TESTS_CORE = {'true': 0, 'false': 0, 'not': 1, 'and': -1, 'or': -1, '=': 2, '!=': 2, '<': 2, '<=': 2, 'inb': 3}
EXPRS = {'read': 3, 'h': 1, 'w': 1, '+': 2, '-': 2, 'dy': 1, 'dx': 1}
# O0 items at cell grain (cells as the individuals; object-level items enter with the obj basis)
O0_CELL = {'adjacent_dir': 5, 'dir_rel': 5, 'aligned': 5, 'between': 7, 'line_of_sight': 6, 'on_ray': 8, 'within': 6,
           'mirror_cell': 6, 'period_cell': 5, 'border': 3, 'rcc8_eq': 4, 'rcc8_ec': 4, 'rcc8_dc': 4}
OBJ_LEAVES = {}          # filled by grain_obj.py for the obj basis (M3)
BASIS_CELL = sorted(ACTIONS) + sorted(TESTS_CORE) + sorted(EXPRS) + sorted(O0_CELL)
RESERVED = set(GRIDS) | CONTROL | set(ACTIONS) | set(TESTS_CORE) | set(EXPRS) | set(O0_CELL)


class GrainError(Exception): pass
class Abort(Exception): pass
class NonTerminating(Exception): pass
class OutOfFuel(Exception): pass


# ------------------------------------------------------------------ parsing
TOK = re.compile(r'\(|\)|[^\s()]+')


def parse(src):
    toks = TOK.findall(src); pos = 0
    def rd():
        nonlocal pos
        if pos >= len(toks): raise GrainError('unexpected end of term')
        t = toks[pos]; pos += 1
        if t == '(':
            out = []
            while True:
                if pos >= len(toks): raise GrainError('missing )')
                if toks[pos] == ')': pos += 1; return out
                out.append(rd())
        if t == ')': raise GrainError('unexpected )')
        if re.fullmatch(r'-?\d+', t): return int(t)
        return t
    x = rd()
    if pos != len(toks): raise GrainError('trailing tokens after the term')
    return x


def unparse(x):
    if isinstance(x, list): return '(' + ' '.join(unparse(y) for y in x) + ')'
    return str(x)


class Program:
    """a parsed, statically checked translation"""
    def __init__(self, tr, basis='cell'):
        self.task = tr.get('task'); self.basis = tr.get('basis', basis)
        self.defs, self.leaves = {}, {}
        self.extra = dict(OBJ_LEAVES) if self.basis == 'obj' else {}
        for lf in tr.get('leaves', []):
            n = lf['name']
            if n in RESERVED or n in self.extra or n in self.leaves: raise GrainError('leaf name taken: ' + n)
            for k in ('pre', 'effect', 'py', 'kind', 'params'):
                if k not in lf: raise GrainError('leaf %s lacks %s' % (n, k))
            ns = {'__builtins__': __builtins__}
            exec(compile(lf['py'], 'leaf_' + n, 'exec'), ns)
            if not callable(ns.get(n)): raise GrainError('leaf %s: py defines no function %s' % (n, n))
            self.leaves[n] = {'kind': lf['kind'], 'params': list(lf['params']), 'fn': ns[n]}
        for d in tr.get('defs', []):
            n = d['name']
            if n in RESERVED or n in self.extra or n in self.leaves or n in self.defs: raise GrainError('def name taken: ' + n)
            body = parse(d['body']) if isinstance(d['body'], str) else d['body']
            self.defs[n] = {'kind': d['kind'], 'params': list(d['params']), 'body': body}
            self._check(body, d['kind'], set(d['params']), n)
        self.main = parse(tr['main']) if isinstance(tr['main'], str) else tr['main']
        self._check(self.main, 'act', set(), 'main')
        self.expanded = self.expand(self.main)

    def _arity(self, head):
        if head in ACTIONS: return ACTIONS[head], 'act'
        if head in TESTS_CORE: return TESTS_CORE[head], 'test'
        if head in EXPRS: return EXPRS[head], 'expr'
        if head in O0_CELL: return O0_CELL[head], 'test'
        if head in self.extra: return self.extra[head]['arity'], self.extra[head]['kind']
        if head in self.leaves: return len(self.leaves[head]['params']), self.leaves[head]['kind']
        if head in self.defs: return len(self.defs[head]['params']), self.defs[head]['kind']
        raise GrainError('unknown operator: %s' % head)

    def _check(self, x, kind, params, where):
        """static well-formedness: known heads, arities, kinds (act / test / expr) in their positions"""
        if not isinstance(x, list):
            if kind in ('act', 'test') and x not in params:
                raise GrainError('%s: a bare atom where a %s is expected: %s' % (where, 'term' if kind == 'act' else 'test', x))
            return
        if not x: raise GrainError(where + ': empty form')
        h = x[0]
        if not isinstance(h, str): raise GrainError('%s: operator must be a name: %s' % (where, unparse(x)))
        if h in params and kind != 'act': return
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
        n, k = self._arity(h)
        if k != kind: raise GrainError('%s: %s is a %s used as a %s' % (where, h, k, kind))
        if h in ('and', 'or'):
            if len(a) < 2: raise GrainError(where + ': and/or need 2+ tests')
            for y in a: self._check(y, 'test', params, where)
            return
        if len(a) != n: raise GrainError('%s: %s takes %d arguments, got %d' % (where, h, n, len(a)))
        if h == 'not': self._check(a[0], 'test', params, where); return
        if h in ('canvas', 'paint', 'read', 'h', 'w', 'inb', 'line_of_sight', 'on_ray', 'mirror_cell', 'period_cell', 'border'):
            g = a[0]
            if g not in GRIDS and g not in params: raise GrainError('%s: %s needs a grid name first, got %s' % (where, h, g))
            if h in ('canvas', 'paint') and g == 'in': raise GrainError(where + ': in is read-only')
            rest = a[1:]
        elif h == 'copy':
            for g in (a[0], a[3]):
                if g not in GRIDS and g not in params: raise GrainError('%s: copy needs grid names, got %s' % (where, g))
            if a[3] == 'in': raise GrainError(where + ': in is read-only')
            rest = a[1:3] + a[4:6]
        elif h in ('set', 'step'):
            regs = a[:1] if h == 'set' else a[:2]
            for r in regs:
                if not isinstance(r, str) or r in RESERVED: raise GrainError('%s: %s needs a register name, got %s' % (where, h, r))
            rest = a[1:] if h == 'set' else a[2:]
        else:
            rest = a
        for y in rest: self._check(y, 'expr', params, where)

    # -------------------------------------------------------------- static expansion and the ruler
    def expand(self, x, depth=0):
        if depth > 60: raise GrainError('definition nesting too deep (recursive definition?)')
        if not isinstance(x, list): return x
        h = x[0]
        if isinstance(h, str) and h in self.defs:
            d = self.defs[h]; sub = dict(zip(d['params'], [self.expand(y, depth) for y in x[1:]]))
            return self.expand(_subst(d['body'], sub), depth + 1)
        return [h] + [self.expand(y, depth) for y in x[1:]]

    def length(self):
        """L(t): operator nodes of the expanded term"""
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
        guards = sorted(h for h in ops if h in TESTS_CORE or h in O0_CELL or (h in self.extra and self.extra[h]['kind'] == 'test')
                        or (h in self.leaves and self.leaves[h]['kind'] == 'test'))
        return {'L': self.length(), 'loop_depth': depth[0], 'ops': ops, 'guards': guards,
                'new_leaves': sorted(self.leaves), 'defs': len(self.defs),
                'L_unexpanded_main': _nodes(self.main), 'L_defs': {n: _nodes(d['body']) for n, d in self.defs.items()}}


def _subst(x, sub):
    if isinstance(x, list): return [_subst(y, sub) for y in x]
    if isinstance(x, str) and x in sub: return sub[x]
    return x


def _nodes(x):
    if not isinstance(x, list): return 0
    return 1 + sum(_nodes(y) for y in x[1:])


# ------------------------------------------------------------------ execution
class State:
    def __init__(self, grid):
        self.g = {'in': [list(r) for r in grid], 'out': [list(r) for r in grid]}
        self.r = {}
        self.hash = 0
        for name in ('out',):
            for y, row in enumerate(self.g[name]):
                for x, c in enumerate(row): self.hash ^= _z(GID[name], y, x, c)

    def grid(self, name):
        if name not in self.g: raise Abort('grid %s used before canvas' % name)
        return self.g[name]

    def read(self, name, y, x):
        g = self.grid(name)
        if 0 <= y < len(g) and 0 <= x < len(g[0]): return g[y][x]
        return -1

    def write(self, name, y, x, c):
        if name == 'in': raise Abort('in is read-only')
        g = self.grid(name)
        if not (0 <= y < len(g) and 0 <= x < len(g[0])): raise Abort('write outside %s at (%s, %s)' % (name, y, x))
        if not isinstance(c, int): raise Abort('colour must be an int')
        old = g[y][x]
        if old != c:
            gi = GID[name]; self.hash ^= _z(gi, y, x, old) ^ _z(gi, y, x, c); g[y][x] = c

    def canvas(self, name, h, w, c):
        if name == 'in': raise Abort('in is read-only')
        if not (1 <= h <= 60 and 1 <= w <= 60): raise Abort('canvas size out of range: %s x %s' % (h, w))
        gi = GID[name]
        if name in self.g:
            for y, row in enumerate(self.g[name]):
                for x, v in enumerate(row): self.hash ^= _z(gi, y, x, v)
        self.g[name] = [[c] * w for _ in range(h)]
        for y in range(h):
            for x in range(w): self.hash ^= _z(gi, y, x, c)
        self.hash ^= _z(gi, -1, h, w)

    def key(self):
        # registers exactly (not by hash: CPython's hash(-1) == hash(-2)); grids by the incremental 64-bit hash
        return (self.hash, frozenset(self.r.items()), tuple((n, len(v), len(v[0]) if v else 0) for n, v in sorted(self.g.items())))


_OFF = 1 << 40


def _z(g, y, x, c):
    # every component shifted positive, so CPython's hash(-1) == hash(-2) cannot make two keys collide
    return hash((0x5bd1e995, g + _OFF, y + _OFF, x + _OFF, c + _OFF)) * 0x9E3779B97F4A7C15 & 0xFFFFFFFFFFFFFFFF


class Run:
    def __init__(self, prog, fuel=FUEL):
        self.p, self.fuel, self.steps, self.loop_iters, self.max_loop_iters = prog, fuel, 0, 0, 0

    def tick(self):
        self.steps += 1
        if self.steps > self.fuel: raise OutOfFuel('step bound %d reached' % self.fuel)

    def ev(self, S, e):
        if isinstance(e, int): return e
        if isinstance(e, str): return S.r.get(e, 0)
        self.tick(); h = e[0]; a = e[1:]
        if h == 'read': return S.read(a[0], self.ev(S, a[1]), self.ev(S, a[2]))
        if h == 'h': return len(S.grid(a[0]))
        if h == 'w': g = S.grid(a[0]); return len(g[0]) if g else 0
        if h == '+': return self.ev(S, a[0]) + self.ev(S, a[1])
        if h == '-': return self.ev(S, a[0]) - self.ev(S, a[1])
        if h == 'dy': return DIRS[self._dir(S, a[0])][0]
        if h == 'dx': return DIRS[self._dir(S, a[0])][1]
        return self._leaf(S, h, a, 'expr')

    def _dir(self, S, e):
        d = self.ev(S, e)
        if not (isinstance(d, int) and 0 <= d < 8): raise Abort('direction out of range: %s' % d)
        return d

    def test(self, S, b):
        self.tick(); h = b[0]; a = b[1:]
        if h == 'true': return True
        if h == 'false': return False
        if h == 'not': return not self.test(S, a[0])
        if h == 'and': return all(self.test(S, y) for y in a)        # lazy, left to right (outermost first)
        if h == 'or': return any(self.test(S, y) for y in a)
        if h in ('=', '!=', '<', '<='):
            u, v = self.ev(S, a[0]), self.ev(S, a[1])
            return {'=': u == v, '!=': u != v, '<': u < v, '<=': u <= v}[h]
        if h == 'inb':
            g = S.grid(a[0]); y, x = self.ev(S, a[1]), self.ev(S, a[2])
            return 0 <= y < len(g) and 0 <= x < len(g[0])
        if h in O0_CELL: return O0(self, S, h, a)
        return bool(self._leaf(S, h, a, 'test'))

    def _leaf(self, S, h, a, kind):
        L = self.p.leaves.get(h) or self.p.extra.get(h)
        if L is None: raise Abort('unknown operator at run time: %s' % h)
        args = [x if (isinstance(x, str) and x in GRIDS) else self.ev(S, x) for x in a]
        return L['fn'](S, *args)

    def do(self, S, t):
        self.tick(); h = t[0]; a = t[1:]
        if h == 'skip': return
        if h == 'seq':
            for y in a: self.do(S, y)
            return
        if h == 'if':
            if self.test(S, a[0]): self.do(S, a[1])
            elif len(a) == 3: self.do(S, a[2])
            return
        if h == 'while':
            seen = set(); n = 0
            while self.test(S, a[0]):
                k = S.key()
                if k in seen: raise NonTerminating('state repeats at a while head: %s' % unparse(a[0])[:80])
                seen.add(k); n += 1
                self.do(S, a[1])
            self.max_loop_iters = max(self.max_loop_iters, n)
            return
        if h == 'canvas': S.canvas(a[0], self.ev(S, a[1]), self.ev(S, a[2]), self.ev(S, a[3])); return
        if h == 'paint': S.write(a[0], self.ev(S, a[1]), self.ev(S, a[2]), self.ev(S, a[3])); return
        if h == 'copy':
            v = S.read(a[0], self.ev(S, a[1]), self.ev(S, a[2]))
            if v < 0: raise Abort('copy reads outside %s' % a[0])
            S.write(a[3], self.ev(S, a[4]), self.ev(S, a[5]), v); return
        if h == 'set': S.r[a[0]] = self.ev(S, a[1]); return
        if h == 'step':
            d = self._dir(S, a[2]); S.r[a[0]] = S.r.get(a[0], 0) + DIRS[d][0]; S.r[a[1]] = S.r.get(a[1], 0) + DIRS[d][1]; return
        self._leaf(S, h, a, 'act')


def O0(run, S, h, a):
    """O0 items with single cells as the individuals (the cell basis). Arguments are expressions except grid names."""
    E = lambda i: run.ev(S, a[i])
    if h == 'adjacent_dir':          # (adjacent_dir y1 x1 y2 x2 d): cell 2 = cell 1 + one step in direction d
        d = run._dir(S, a[4]); return (E(2), E(3)) == (E(0) + DIRS[d][0], E(1) + DIRS[d][1])
    if h == 'dir_rel':               # (dir_rel y1 x1 y2 x2 d): cell 2 lies on the open ray from cell 1 in direction d
        y1, x1, y2, x2 = E(0), E(1), E(2), E(3); dy, dx = DIRS[run._dir(S, a[4])]
        k = max(abs(y2 - y1), abs(x2 - x1))
        return k > 0 and (y1 + k * dy, x1 + k * dx) == (y2, x2)
    if h == 'aligned':               # (aligned y1 x1 y2 x2 axis): same row (axis 0) or same column (axis 1)
        return (E(0) == E(2)) if E(4) == 0 else (E(1) == E(3))
    if h == 'between':               # (between y x y1 x1 y2 x2 axis): cell strictly between cells 1 and 2 on their row / column
        y, x, y1, x1, y2, x2, ax = (E(i) for i in range(7))
        if ax == 0: return y == y1 == y2 and min(x1, x2) < x < max(x1, x2)
        return x == x1 == x2 and min(y1, y2) < y < max(y1, y2)
    if h == 'line_of_sight':         # (line_of_sight G y1 x1 y2 x2 bg): same row / column, only bg strictly between
        g = a[0]; y1, x1, y2, x2, bg = E(1), E(2), E(3), E(4), E(5)
        if y1 == y2: return all(S.read(g, y1, x) == bg for x in range(min(x1, x2) + 1, max(x1, x2)))
        if x1 == x2: return all(S.read(g, y, x1) == bg for y in range(min(y1, y2) + 1, max(y1, y2)))
        return False
    if h == 'on_ray':                # (on_ray G y1 x1 y2 x2 d stop bg): cell 2 on the ray from cell 1 in direction d,
        g = a[0]; y1, x1, y2, x2 = E(1), E(2), E(3), E(4); dy, dx = DIRS[run._dir(S, a[5])]; stop, bg = E(6), E(7)
        y, x = y1 + dy, x1 + dx       # the ray ending at the border (stop 0) or at the first non-bg cell (stop 1, included)
        while S.read(g, y, x) != -1:
            run.tick()
            if (y, x) == (y2, x2): return True
            if stop == 1 and S.read(g, y, x) != bg: return False
            y, x = y + dy, x + dx
        return False
    if h == 'within':                # (within y1 x1 y2 x2 k metric): Chebyshev (0) or Manhattan (1) distance <= k
        dy, dx = abs(E(0) - E(2)), abs(E(1) - E(3))
        return (max(dy, dx) if E(5) == 0 else dy + dx) <= E(4)
    if h == 'mirror_cell':           # (mirror_cell G y1 x1 y2 x2 axis): cell 2 mirrors cell 1 across G's centre line
        g = S.grid(a[0]); H, W = len(g), len(g[0]); y1, x1, y2, x2, ax = E(1), E(2), E(3), E(4), E(5)
        return (y2, x2) == ((H - 1 - y1, x1) if ax == 0 else (y1, W - 1 - x1))
    if h == 'period_cell':           # (period_cell G y x axis p): G[y][x] equals the cell p further along the axis (when inside)
        g = a[0]; y, x, ax, p = E(1), E(2), E(3), E(4)
        v = S.read(g, y + p, x) if ax == 0 else S.read(g, y, x + p)
        return v == -1 or v == S.read(g, y, x)
    if h == 'border':                # (border G y x): on G's outer ring
        g = S.grid(a[0]); y, x = E(1), E(2)
        return 0 <= y < len(g) and 0 <= x < len(g[0]) and (y in (0, len(g) - 1) or x in (0, len(g[0]) - 1))
    if h == 'rcc8_eq': return (E(0), E(1)) == (E(2), E(3))
    if h == 'rcc8_ec': return abs(E(0) - E(2)) + abs(E(1) - E(3)) == 1
    if h == 'rcc8_dc': return abs(E(0) - E(2)) + abs(E(1) - E(3)) > 1
    raise Abort('unknown O0 item ' + h)


def execute(prog, grid, fuel=FUEL):
    """-> (output grid or None, info)"""
    S = State(grid); R = Run(prog, fuel)
    try:
        R.do(S, prog.expanded)
        return S.g['out'], {'steps': R.steps, 'status': 'ok', 'max_loop_iters': R.max_loop_iters}
    except NonTerminating as e: return None, {'steps': R.steps, 'status': 'nonterminating', 'detail': str(e)}
    except OutOfFuel as e: return None, {'steps': R.steps, 'status': 'out_of_fuel', 'detail': str(e)}
    except Abort as e: return None, {'steps': R.steps, 'status': 'abort', 'detail': str(e)}
    except RecursionError: return None, {'steps': R.steps, 'status': 'abort', 'detail': 'recursion depth'}
    except Exception as e: return None, {'steps': R.steps, 'status': 'error', 'detail': '%s: %s' % (type(e).__name__, e)}

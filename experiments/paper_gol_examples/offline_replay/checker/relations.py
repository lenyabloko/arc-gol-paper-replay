"""The frozen relation catalog (protocol draft v2, section 7): formal predicates over ARCGraph node geometry and colours.
A node is given as {'members': [[y, x], ...], 'colours': [c, ...]} (one colour per member). Every relation is decided
from these alone, so its truth on any input (demonstration, distinguishing case or control) is independent of the
program being evaluated. D4 maps each relation name under the 8 symmetries of the square."""
import itertools

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
N8 = N4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))


def _box(n):
    ys = [m[0] for m in n['members']]; xs = [m[1] for m in n['members']]
    return min(ys), min(xs), max(ys), max(xs)


def _cells(n): return {tuple(m) for m in n['members']}


def _filled(n):
    """the node's cells plus every cell of its box it encloses (not reachable from outside the box without crossing it)"""
    t, l, b, r = _box(n); C = _cells(n); out = set()
    st = [(y, x) for y in range(t - 1, b + 2) for x in (l - 1, r + 1)] + [(y, x) for x in range(l - 1, r + 2) for y in (t - 1, b + 1)]
    seen = set(st)
    while st:
        y, x = st.pop(); out.add((y, x))
        for dy, dx in N4:
            q = (y + dy, x + dx)
            if q not in seen and t - 1 <= q[0] <= b + 1 and l - 1 <= q[1] <= r + 1 and q not in C: seen.add(q); st.append(q)
    return {(y, x) for y in range(t, b + 1) for x in range(l, r + 1)} - out


def _norm(n):
    t, l, _, _ = _box(n); return tuple(sorted((y - t, x - l) for y, x in _cells(n)))


BINARY = {
    'above': lambda a, b: _box(a)[2] < _box(b)[0],
    'below': lambda a, b: _box(a)[0] > _box(b)[2],
    'left_of': lambda a, b: _box(a)[3] < _box(b)[1],
    'right_of': lambda a, b: _box(a)[1] > _box(b)[3],
    'row_overlap': lambda a, b: not (_box(a)[2] < _box(b)[0] or _box(b)[2] < _box(a)[0]),
    'col_overlap': lambda a, b: not (_box(a)[3] < _box(b)[1] or _box(b)[3] < _box(a)[1]),
    'adjacent4': lambda a, b: any((y + dy, x + dx) in _cells(b) for y, x in _cells(a) for dy, dx in N4),
    'adjacent8': lambda a, b: any((y + dy, x + dx) in _cells(b) for y, x in _cells(a) for dy, dx in N8),
    'inside': lambda a, b: _cells(a) <= _filled(b) and not (_cells(a) & _cells(b)),
    'contains': lambda a, b: _cells(b) <= _filled(a) and not (_cells(a) & _cells(b)),
    'centre_row_aligned': lambda a, b: _box(a)[0] + _box(a)[2] == _box(b)[0] + _box(b)[2],
    'centre_col_aligned': lambda a, b: _box(a)[1] + _box(a)[3] == _box(b)[1] + _box(b)[3],
    'top_aligned': lambda a, b: _box(a)[0] == _box(b)[0],
    'bottom_aligned': lambda a, b: _box(a)[2] == _box(b)[2],
    'left_aligned': lambda a, b: _box(a)[1] == _box(b)[1],
    'right_aligned': lambda a, b: _box(a)[3] == _box(b)[3],
    'same_colour': lambda a, b: set(a['colours']) == set(b['colours']),
    'same_shape': lambda a, b: _norm(a) == _norm(b),
    'same_size': lambda a, b: len(a['members']) == len(b['members']),
    'larger': lambda a, b: len(a['members']) > len(b['members']),
    'smaller': lambda a, b: len(a['members']) < len(b['members']),
}
UNARY = {'touches_border': lambda a, H, W: any(y in (0, H - 1) or x in (0, W - 1) for y, x in _cells(a))}

# D4: k quarter turns clockwise, then a mirror across the vertical axis if m; how each direction-bearing relation maps
_TURN = {'above': 'right_of', 'right_of': 'below', 'below': 'left_of', 'left_of': 'above',
         'top_aligned': 'right_aligned', 'right_aligned': 'bottom_aligned', 'bottom_aligned': 'left_aligned', 'left_aligned': 'top_aligned',
         'row_overlap': 'col_overlap', 'col_overlap': 'row_overlap', 'centre_row_aligned': 'centre_col_aligned',
         'centre_col_aligned': 'centre_row_aligned'}
_MIRROR = {'left_of': 'right_of', 'right_of': 'left_of', 'left_aligned': 'right_aligned', 'right_aligned': 'left_aligned'}


def d4_name(rel, k, m):
    for _ in range(k % 4): rel = _TURN.get(rel, rel)
    return _MIRROR.get(rel, rel) if m else rel


def relations(nodes, H=None, W=None):
    """every catalog relation that holds between ordered pairs of `nodes` ({handle: node}); unary ones too"""
    out = {}
    for a, b in itertools.permutations(sorted(nodes), 2):
        out['%s>%s' % (a, b)] = [r for r, f in BINARY.items() if f(nodes[a], nodes[b])]
    if H is not None:
        for a in sorted(nodes): out[str(a)] = [r for r, f in UNARY.items() if f(nodes[a], H, W)]
    return out


def compatible(truth_by_case, cases):
    """the catalog relations compatible with a guard comparison: those whose truth on the bound pair equals the guard's on
    every case. truth_by_case: [(guard_value, node_a, node_b)]; returns the set of relation names (kept whole)"""
    return sorted(r for r, f in BINARY.items() if all(bool(f(a, b)) == bool(g) for g, a, b in truth_by_case))

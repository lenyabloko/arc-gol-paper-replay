"""Shared runtime for the re-hosted study's interfaces (protocol draft v2). No LLM anywhere in this package.
Code root: $TRACE_R7 (default /home/claude/work/r7), laid out like the replay kit (cx2/, room15/, data15b/, plan15b/,
store15/, gitlab/fullcheck/). A runtime room is a scratch copy of the task's round-7 room (arcroom.py, mdl.py,
perception.py, task.json, spec.json, dsl_allowed.json, arc -> the ARCGraph package); readers never see it."""
import hashlib, json, os, shutil, sys

R7 = os.path.realpath(os.environ.get('TRACE_R7', '/home/claude/work/r7'))
CX = os.path.join(R7, 'cx2')
PALETTE = [(0, 0, 0), (0, 116, 217), (255, 65, 54), (46, 204, 64), (255, 220, 0), (170, 170, 170), (240, 18, 190),
           (255, 133, 27), (127, 219, 255), (135, 12, 37)]          # the usual ARC colours; pictures carry no grid lines


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def data_dir(task):
    d = os.path.join(R7, 'data15b', task)
    return d if os.path.isdir(d) else os.path.join(R7, 'data15', task)


def plan_dir(task):
    d = os.path.join(R7, 'plan15b', task)
    return d if os.path.isdir(d) else os.path.join(R7, 'plan15', task)


def runtime_room(task, where):
    """a scratch runtime room for `task` under `where` (never shown to a reader); returns its path"""
    D = data_dir(task); room = os.path.join(where, 'runtime_' + task)
    if os.path.exists(room): shutil.rmtree(room)
    os.makedirs(room)
    for f in ('arcroom.py', 'mdl.py', 'perception.py', 'task.json', 'spec.json', 'dsl_allowed.json'):
        if os.path.exists(os.path.join(D, f)): shutil.copy(os.path.join(D, f), room)
    arc = os.path.join(D, 'arc')
    arc = os.path.realpath(arc) if os.path.exists(arc) else os.path.join(R7, 'gitlab', 'fullcheck')
    shutil.copytree(arc, os.path.join(room, 'arc'), ignore=shutil.ignore_patterns('__pycache__'))
    reg = registry_choice()
    if reg == 'original':   # the recovery commit's own registry (verified on the PC); needs rdflib
        shutil.copy(os.path.join(R7, 'gitlab', 'pinned_9d446873', 'ontology', 'runtime_registry.py'),
                    os.path.join(room, 'arc', 'ontology', 'runtime_registry.py'))
    json.dump({'registry': reg, 'runtime_registry_sha256': sha(os.path.join(room, 'arc', 'ontology', 'runtime_registry.py'))},
              open(os.path.join(room, 'REGISTRY.json'), 'w'))
    return room


def registry_choice():
    """STUDY_REGISTRY=original|shim; default: original when rdflib is importable, else the cloud shim (labelled; not valid
    for the frozen study, which requires the original registry)"""
    r = os.environ.get('STUDY_REGISTRY')
    if r in ('original', 'shim'): return r
    try:
        import importlib.util
        return 'original' if importlib.util.find_spec('rdflib') else 'shim'
    except Exception:
        return 'shim'


def enter(room):
    """import the room runtime and the container (GOL on ARCGraph) with `room` as the working room"""
    os.chdir(room); sys.path.insert(0, room)
    if not os.environ.get('STORE15'): raise SystemExit('STORE15 must name the execution store explicitly (empty for A and B)')
    os.environ['DATA15'] = os.path.dirname(data_dir(os.path.basename(room)[len('runtime_'):]))
    for p in (os.path.join(R7, 'room15'), os.path.join(R7, 'room15', 'grain'), os.path.join(CX, 'dsl'), os.path.join(CX, 'container')):
        sys.path.insert(0, p)
    import gol as GOL
    return GOL


def split_demos(task_json):
    """seen and hidden demonstrations (protocol v2 section 5): the last demonstration is hidden when there are >= 3"""
    tr = task_json['train']; n = len(tr)
    return (list(range(n - 1)), [n - 1]) if n >= 3 else (list(range(n)), [])


def picture(pairs, path, scale=None):
    """one picture of demonstration pairs (input -> output per row), no grid lines"""
    from PIL import Image, ImageDraw
    side = max(max(len(g), len(g[0])) for p in pairs for g in (p['input'], p['output']))
    c = scale or max(6, min(20, 300 // side)); gap = 2 * c
    rows = []
    for p in pairs:
        ims = []
        for g in (p['input'], p['output']):
            im = Image.new('RGB', (len(g[0]) * c, len(g) * c))
            dr = ImageDraw.Draw(im)
            for y, r in enumerate(g):
                for x, v in enumerate(r): dr.rectangle([x * c, y * c, x * c + c - 1, y * c + c - 1], fill=PALETTE[v])
            ims.append(im)
        rows.append(ims)
    W = max(a.width + b.width for a, b in rows) + 3 * gap; H = sum(max(a.height, b.height) for a, b in rows) + gap * (len(rows) + 1)
    S = Image.new('RGB', (W, H), (40, 40, 48)); d = ImageDraw.Draw(S); y = gap
    for a, b in rows:
        S.paste(a, (gap, y)); x2 = gap + a.width + gap
        d.line([(gap + a.width + 4, y + a.height // 2), (x2 - 4, y + a.height // 2)], fill=(230, 230, 230), width=2)
        S.paste(b, (x2, y)); y += max(a.height, b.height) + gap
    S.save(path)


def numbered_picture(grid, nodes, path):
    """the grid with each node's handle written at its first member (B and D only)"""
    from PIL import Image, ImageDraw
    c = max(14, min(28, 420 // max(len(grid), len(grid[0]))))
    im = Image.new('RGB', (len(grid[0]) * c, len(grid) * c)); d = ImageDraw.Draw(im)
    for y, r in enumerate(grid):
        for x, v in enumerate(r): d.rectangle([x * c, y * c, x * c + c - 1, y * c + c - 1], fill=PALETTE[v])
    for h, n in nodes.items():
        y, x = min(tuple(m) for m in n['members'])
        d.text((x * c + 2, y * c + 1), str(h), fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    im.save(path)


def manifest(room):
    out = {}
    for r, ds, fs in os.walk(room):
        for f in fs:
            if f == 'ROOM_MANIFEST.json': continue
            p = os.path.join(r, f); out[os.path.relpath(p, room).replace(os.sep, '/')] = sha(p)
    return dict(sorted(out.items()))

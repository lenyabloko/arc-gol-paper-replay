"""Widened bounded synthesis over existing ARCGraph abstractions and object operations.

Extends experiments/object_dsl_recovery/search.py (unchanged, imported) with:
  * every object-level abstraction registered in the runtime registry (not only nbccg);
  * an ARGA-style bounded enumerator over the abstraction's registered object transformations
    (update_color, extend_node, move_node_max, fill_rectangle, hollow_rectangle, add_border,
    rotate_node, flip, remove_node) with parameter domains drawn only from the task's own
    training pairs (colors present) and the typed enums (Direction, Rotation, Mirror);
  * ranked results so attempt_2 can use the second-best training-exact program.
No task identifiers, no held-out outputs, no new grid-level executors.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

from image import Image
from experiments.object_dsl_recovery import search as base
from experiments.object_dsl_recovery.search import (
    FragmentGap, Limits, canonical, compile_program, digest, direct_step, grid_of,
    observation, propose, proposal_order, residual, selectors, shadow_step,
)

OBJECT_ABSTRACTIONS = ("nbccg", "ccgbr", "ccgbr2", "nbvcg", "nbhcg", "mcccg", "lrg")
DIRECTIONS = ("UP", "DOWN", "LEFT", "RIGHT", "UP_LEFT", "UP_RIGHT", "DOWN_LEFT", "DOWN_RIGHT")
GENERIC = {
    "extend_node": lambda cs: [{"direction": d, "overlap": o} for d in DIRECTIONS for o in (False, True)],
    "move_node_max": lambda cs: [{"direction": d} for d in DIRECTIONS],
    "fill_rectangle": lambda cs: [{"fill_color": c, "overlap": o} for c in cs for o in (False, True)],
    "hollow_rectangle": lambda cs: [{"fill_color": c} for c in cs],
    "add_border": lambda cs: [{"border_color": c} for c in cs],
    "rotate_node": lambda cs: [{"rotation_dir": r} for r in ("CW", "CCW", "CW2")],
    "flip": lambda cs: [{"mirror_direction": m} for m in ("VERTICAL", "HORIZONTAL", "DIAGONAL_LEFT", "DIAGONAL_RIGHT")],
    "update_color": lambda cs: [{"color": c} for c in cs],
    "remove_node": lambda cs: [{}],
}


def abstract(grid, abstraction):
    if not grid or not grid[0] or len(grid) * len(grid[0]) > 900:
        raise FragmentGap("grid_outside_fragment")
    if any(len(row) != len(grid[0]) for row in grid):
        raise FragmentGap("nonrectangular_grid")
    image = Image(SimpleNamespace(stop_search=False, check_time_limit=lambda: False,
                                  max_abstract_nodes=64),
                  grid=copy.deepcopy(grid), name="object_program")
    graph = getattr(image, Image.abstraction_ops[abstraction])()
    if len(graph.graph) > 64:
        raise FragmentGap("object_count_outside_fragment")
    if not len(graph.graph):
        raise FragmentGap("empty_abstraction")
    return graph


def generic_proposals(graph, colors):
    allowed = set(graph.transformation_ops[graph.abstraction]) if hasattr(graph, "transformation_ops") else set()
    steps = {}
    for node in graph.graph:
        for filter_name, filter_params in selectors(graph, node):
            for name, domain in GENERIC.items():
                if allowed and name not in allowed:
                    continue
                for params in domain(colors):
                    step = {"filter": filter_name, "filter_params": filter_params,
                            "action": name, "params": params}
                    steps[canonical(step)] = step
    return steps


def infer(train, abstraction, limits=Limits(), want=2):
    if not train:
        return {"status": "empty_training", "programs": []}
    try:
        starts = [abstract(p["input"], abstraction) for p in train]
        targets = [abstract(p["output"], abstraction) for p in train]
    except FragmentGap as error:
        return {"status": str(error), "programs": [], "evaluations": 0}
    except Exception as error:  # abstraction constructor refused this grid
        return {"status": f"abstraction_error:{type(error).__name__}", "programs": [], "evaluations": 0}
    if any((len(p["input"]), len(p["input"][0])) != (len(p["output"]), len(p["output"][0])) for p in train):
        return {"status": "extent_change_outside_fragment", "programs": [], "evaluations": 0}
    colors = sorted({c for p in train for row in p["output"] for c in row})
    outputs = [p["output"] for p in train]
    initial = residual(starts, outputs, targets)
    beam = [(sum(initial), [], starts, initial)]
    seen = {base.state_key(starts)}
    evaluations = 0
    found = []
    for depth in range(limits.depth + 1):
        for entry in beam:
            if entry[0] == 0 and entry[1] and canonical(entry[1]) not in {canonical(f) for f in found}:
                found.append(entry[1])
        if len(found) >= want or depth == limits.depth:
            break
        successors = []
        for _, program, graphs, prior in beam:
            proposals = {}
            for graph, target in zip(graphs, targets):
                proposals.update({canonical(s): s for s in propose(graph, target)})
            generic = {}
            for graph in graphs:
                generic.update(generic_proposals(graph, colors))
            ordered = sorted(proposals, key=proposal_order)[:limits.candidates_per_state]
            ordered += [k for k in sorted(generic) if k not in proposals]
            for key in ordered:
                if evaluations >= limits.evaluations:
                    break
                step = proposals.get(key) or generic[key]
                evaluations += 1
                try:
                    transformed = [direct_step(g, step) for g in graphs]
                    errors = residual(transformed, outputs, targets)
                except Exception:
                    continue
                if sum(errors) >= sum(prior) or any(a > b for a, b in zip(errors, prior)):
                    continue
                identity = base.state_key(transformed)
                if identity in seen:
                    continue
                seen.add(identity)
                successors.append((sum(errors), program + [step], transformed, errors))
            if evaluations >= limits.evaluations:
                break
        successors.sort(key=lambda e: (e[0], len(e[1]), canonical(e[1])))
        beam = successors[:limits.beam]
        if not beam:
            break
    for entry in beam:
        if entry[0] == 0 and canonical(entry[1]) not in {canonical(f) for f in found}:
            found.append(entry[1])
    return {"status": "train_exact" if found else ("budget_exhausted_unknown" if evaluations >= limits.evaluations
                                                   else "no_program_in_explored_fragment"),
            "programs": found[:want], "evaluations": evaluations, "abstraction": abstraction}


def execute(grid, program, abstraction):
    graph = abstract(grid, abstraction)
    code = compile_program(program)
    for instructions in code["statements"]:
        graph, _ = shadow_step(graph, instructions)
    return grid_of(graph)


def execute_direct(grid, program, abstraction):
    graph = abstract(grid, abstraction)
    for step in program:
        graph = direct_step(graph, step)
    return grid_of(graph)

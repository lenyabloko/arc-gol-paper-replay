"""Bounded, residual-directed synthesis over existing abstract-object DSL operations.

No family registry, task identifiers, expected test outputs, or legacy solver.
This is an experimental search adapter, not an activated Wake rule producer.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace

from scipy.optimize import linear_sum_assignment

from ARCGraph import ARCGraph
from image import Image
from connectors.dsl_shadows import DSL_CONNECTOR_SHADOWS
from utils import Direction
from experiments.object_dsl_recovery.object_queries import (
    ObjectRelations, QueryGap, compile_query, direction_hypotheses,
    evaluate_query, execute_query,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Limits:
    depth: int = 3
    beam: int = 4
    evaluations: int = 256
    nodes: int = 64
    candidates_per_state: int = 64


class FragmentGap(ValueError):
    pass


def abstract(grid):
    if not grid or not grid[0] or len(grid) * len(grid[0]) > 900:
        raise FragmentGap("grid_outside_fragment")
    if any(len(row) != len(grid[0]) for row in grid):
        raise FragmentGap("nonrectangular_grid")
    graph = Image(SimpleNamespace(stop_search=False), grid=copy.deepcopy(grid),
                  name="object_program").get_non_black_components_graph()
    if len(graph.graph) > 64:
        raise FragmentGap("object_count_outside_fragment")
    return graph


def observation(graph):
    """Actual abstract-object observations, refreshed after every statement."""
    nodes = []
    for node, data in graph.graph.nodes(data=True):
        cells = sorted([list(p) for p in data["nodes"]])
        nodes.append({"id": list(node), "color": data["color"],
                      "size": len(cells), "cells": cells})
    edges = sorted([[list(a), list(b), dict(data)]
                    for a, b, data in graph.graph.edges(data=True)], key=canonical)
    return {"objects": sorted(nodes, key=canonical), "edges": edges,
            "abstraction": graph.abstraction,
            "ontology": graph.graph.graph.get("root_arcgraph_contract_iri")}


def grid_of(graph):
    return graph.undo_abstraction().graph_to_grid()


def state_key(graphs):
    # Object identities/edges matter even when their rendered grids are equal.
    return digest([observation(g) for g in graphs])


def decode_parameters(params):
    values = copy.deepcopy(params)
    if "direction" in values and not isinstance(values["direction"], dict):
        values["direction"] = Direction(values["direction"])
    return values


def slide_node(graph, node, direction, stationary):
    """Guarded repetition of the existing unit move with swept clearance.

    Object supports are inspected, never painted or replaced by this macro.
    Swept clearance applies to stationary boundaries. Movable selected objects
    occupy their current positions for destination collision only.
    """
    name = direction.value
    dy = 1 if "DOWN" in name else -1 if "UP" in name else 0
    dx = 1 if "RIGHT" in name else -1 if "LEFT" in name else 0
    if not (dy or dx):
        raise FragmentGap("invalid_slide_direction")
    offsets = [(dy, dx)] + ([(dy, 0), (0, dx)] if dy and dx else [])
    walls = {tuple(p) for other in stationary for p in graph.graph.nodes[other]["nodes"]}
    for _ in range(900):
        support = graph.graph.nodes[node]["nodes"]
        swept = {(y + sy, x + sx) for y, x in support for sy, sx in offsets}
        destination = [(y + dy, x + dx) for y, x in support]
        if (not graph.check_inbound(sorted(swept)) or swept & walls or
                graph.check_collision(node, destination)):
            return graph
        graph.move_node(node, direction, steps=1)
    raise FragmentGap("slide_bound_exhausted")


def direct_step(graph, step):
    result = graph.copy()
    queries = {slot: value["query"] for slot, value in step["params"].items()
               if isinstance(value, dict) and "query" in value}
    if queries or step["action"] == "slide_node":
        relations = ObjectRelations(result)
        qualified = []
        for node in result.graph:
            if not getattr(result, step["filter"])(node, **step["filter_params"]):
                continue
            params = copy.deepcopy(step["params"])
            for slot, tree in queries.items():
                if slot != "direction" or compile_query(tree)["output_type"] != "arga:DirectionValue":
                    raise FragmentGap("unsupported_query_binding")
                params[slot] = evaluate_query(tree, relations, node)
            qualified.append((node, decode_parameters(params)))
        stationary = set(result.graph) - {node for node, _ in qualified}
        for node, params in qualified:
            if step["action"] == "slide_node":
                slide_node(result, node, stationary=stationary, **params)
            else:
                result.apply_transformation(node, [step["action"]], params)
        result.update_abstracted_graph([node for node, _ in qualified])
        return result
    result.apply({}, [step["filter"]], [step["filter_params"]],
                 [step["action"]], [decode_parameters(step["params"])])
    return result


ALLOWED = {"filter_by_color": "filter", "filter_by_size": "filter",
           "param_bind_node_by_size": "binder", "update_color": "action",
           "move_node": "action", "move_node_max": "action", "slide_node": "action", "remove_node": "action"}


def instruction(name, role, params):
    if ALLOWED.get(name) != role:
        raise FragmentGap("operation_outside_fragment")
    if name == "slide_node":
        if set(params) != {"direction"}:
            raise FragmentGap("invalid_slide_parameters")
        return {"role": role, "operation": name,
                "connector": "experimental:guarded_object_slide",
                "action_iri": "experimental:slide_node", "callable": "move_node",
                "implementation_digest": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "guarded_repeat": {"guard": "in_bounds_and_stationary_swept_clearance_and_all_destination_collision_free",
                                   "stationary_binding": "graph_objects_minus_statement_selection",
                                   "unit_effect": instruction("move_node", "action", {"direction": params["direction"], "steps": 1}),
                                   "limit": 900},
                "params": copy.deepcopy(params)}
    effect = DSL_CONNECTOR_SHADOWS[name].connectors[-1]
    if effect.wake_lowering.module != "ARCGraph" or effect.wake_lowering.callable_name != name:
        raise FragmentGap("shadow_lowering_mismatch")
    if set(params) - set(effect.action.parameters):
        raise FragmentGap("unknown_parameter")
    return {"role": role, "connector": effect.schema_id,
            "action_iri": effect.action.action_id, "callable": name,
            "implementation_digest": effect.implementation_digest,
            "params": copy.deepcopy(params)}


def compile_program(program):
    compiled = []
    for step in program:
        code = [instruction(step["filter"], "filter", step["filter_params"])]
        params = copy.deepcopy(step["params"])
        for slot, value in list(params.items()):
            if isinstance(value, dict):
                if "query" in value:
                    compiled_query = compile_query(value["query"])
                    if slot != "direction" or compiled_query["output_type"] != "arga:DirectionValue":
                        raise FragmentGap("unsupported_query_binding")
                    code.append({"role": "query_binding", "slot": slot,
                                 "query": value["query"], "compiled_query": compiled_query})
                    params[slot] = {"bound_slot": slot}
                    continue
                if slot != "color":
                    raise FragmentGap("unsupported_relational_binding")
                bind = instruction(value["filters"][0], "binder", value["filter_params"][0])
                bind["slot"] = slot
                code.append(bind)
                params[slot] = {"bound_slot": slot}
        code.append(instruction(step["action"], "action", params))
        compiled.append(code)
    return {"version": 1, "abstraction": "nbccg", "statements": compiled}


def shadow_step(graph, code):
    """Interpret the connector instructions, independently of ARCGraph.apply."""
    result = graph.copy()
    for op in code:
        if op["role"] == "query_binding":
            if op["compiled_query"] != compile_query(op["query"]):
                raise FragmentGap("stale_or_modified_query")
            continue
        # Stored code must still resolve to exactly the registered primitive.
        expected = instruction(op.get("operation", op["callable"]), op["role"], op["params"])
        for field in ("connector", "action_iri", "implementation_digest"):
            if op[field] != expected[field]:
                raise FragmentGap("stale_or_modified_instruction")
        if op.get("operation") == "slide_node" and op != expected:
            raise FragmentGap("stale_or_modified_instruction")
    test, effect = code[0], code[-1]
    selected = [node for node in result.graph
                if getattr(result, test["callable"])(node, **test["params"])]
    # Resolve every binding before mutating any selected node (DSL transaction).
    qualified = []
    relations = ObjectRelations(result) if any(op["role"] == "query_binding" for op in code) else None
    for node in selected:
        bound = {}
        for bind in code[1:-1]:
            if bind["role"] == "query_binding":
                bound[bind["slot"]] = execute_query(bind["compiled_query"], relations, node)
                continue
            target = getattr(result, bind["callable"])(node, **bind["params"])
            if target is None:
                raise FragmentGap("unresolved_binding")
            bound[bind["slot"]] = result.get_color(target)
        params = {key: bound[value["bound_slot"]] if isinstance(value, dict) else value
                  for key, value in effect["params"].items()}
        qualified.append((node, decode_parameters(params)))
    for node, params in qualified:
        if effect.get("operation") == "slide_node":
            slide_node(result, node, stationary=set(result.graph) - set(selected), **params)
        else:
            getattr(result, effect["callable"])(node, **params)
    affected = list(result.graph) if effect["callable"] == "remove_node" else selected
    result.update_abstracted_graph(affected)
    return result, {"selected": [list(n) for n in selected],
                    "bindings": [{"node": list(n), "params": p} for n, p in qualified]}


def execute(grid, program, *, backend="shadow", trace=False):
    graph = abstract(grid)
    code = compile_program(program)
    states = [{"objects": observation(graph), "grid": grid_of(graph)}] if trace else []
    for step, instructions in zip(program, code["statements"]):
        if backend == "direct":
            graph = direct_step(graph, step)
            event = {}
        elif backend == "shadow":
            graph, event = shadow_step(graph, instructions)
        else:
            raise ValueError(backend)
        if trace:
            states.append({"objects": observation(graph), "grid": grid_of(graph),
                           "instructions": instructions, "event": event})
    return {"grid": grid_of(graph), "trace": states}


def shape_and_anchor(data):
    cells = data["nodes"]
    row, col = min(r for r, c in cells), min(c for r, c in cells)
    return tuple(sorted((r - row, c - col) for r, c in cells)), (row, col)


def selectors(graph, node):
    data = graph.graph.nodes[node]
    choices = [("filter_by_size", {"size": 0, "exclude": True}),
               ("filter_by_color", {"color": data["color"], "exclude": False})]
    for size in ("min", "max", len(data["nodes"])):
        params = {"size": size, "exclude": False}
        if graph.filter_by_size(node, **params):
            choices.append(("filter_by_size", params))
    return choices


def propose(graph, target):
    """Abduce primitive changes from shape-preserving object correspondences.

    These are defeasible hypotheses, not an oracle correspondence assignment.
    All proposals must subsequently improve and fit every demonstration.
    """
    proposed = {}
    relations = ObjectRelations(graph)
    for node, source in graph.graph.nodes(data=True):
        source_shape, (row, col) = shape_and_anchor(source)
        matches = []
        for _, dest in target.graph.nodes(data=True):
            dest_shape, (dy, dx) = shape_and_anchor(dest)
            if source_shape == dest_shape:
                distance = abs(dy - row) + abs(dx - col)
                matches.append((int(dest["color"] != source["color"]), distance, dy - row, dx - col, dest))
        # Keep ambiguous nearest correspondences, not a task-family classifier.
        nearest = min(((m[0], m[1]) for m in matches), default=None)
        effects = []
        for color_difference, distance, dr, dc, dest in matches:
            if (color_difference, distance) != nearest:
                continue
            if dest["color"] != source["color"]:
                effects.append(("update_color", {"color": dest["color"]}))
                for size in ("min", "max"):
                    ref = graph.param_bind_node_by_size(node, size, False)
                    if ref is not None and graph.get_color(ref) == dest["color"]:
                        effects.append(("update_color", {"color": {
                            "filters": ["param_bind_node_by_size"],
                            "filter_params": [{"size": size, "exclude": False}]}}))
            if (dr or dc) and (not dr or not dc or abs(dr) == abs(dc)):
                direction = "_".join(p for p in ("DOWN" if dr > 0 else "UP" if dr < 0 else "",
                                               "RIGHT" if dc > 0 else "LEFT" if dc < 0 else "") if p)
                effects.append(("move_node", {"direction": direction, "steps": abs(dr or dc)}))
                effects.append(("move_node_max", {"direction": direction}))
                effects.append(("slide_node", {"direction": direction}))
                for query in direction_hypotheses(relations, node, direction):
                    effects.append(("move_node_max", {"direction": {"query": query}}))
                    effects.append(("slide_node", {"direction": {"query": query}}))
        if not matches:
            effects.append(("remove_node", {}))
        for name, params in effects:
            for filter_name, filter_params in selectors(graph, node):
                step = {"filter": filter_name, "filter_params": filter_params,
                        "action": name, "params": params}
                proposed[canonical(step)] = step
    # Prefer relational binding over literal constants at equal explanatory fit.
    return [proposed[key] for key in sorted(proposed, key=proposal_order)]


def proposal_order(key):
    # Prefer reference roles without palette constants; then shorter queries.
    # This prior uses syntax only, never held-out inputs or answers.
    def query_cost(tree):
        children = [query_cost(child) for child in tree["args"]]
        return (int(tree["op"] == "color") + sum(c[0] for c in children),
                1 + sum(c[1] for c in children))
    step = json.loads(key)
    costs = [query_cost(value["query"]) for value in step["params"].values()
             if isinstance(value, dict) and "query" in value]
    return (not costs, sum(c[0] for c in costs), sum(c[1] for c in costs),
            step["action"] != "slide_node", "param_bind" not in key, key)


def object_distance(graph, target):
    """Minimum-cost object correspondence, including unmatched components.

    A color change and a unit translation each cost one. Thus a recoloring
    that prepares a later translation is visible even if pixel error is flat.
    This is a search heuristic, not a proof of program distance or completeness.
    """
    left, right = list(graph.graph.nodes(data=True)), list(target.graph.nodes(data=True))
    n, m = len(left), len(right)
    if not n and not m:
        return 0
    costs = [[0] * (n + m) for _ in range(n + m)]
    for i, (_, source) in enumerate(left):
        source_shape, (sy, sx) = shape_and_anchor(source)
        for j, (_, dest) in enumerate(right):
            target_shape, (ty, tx) = shape_and_anchor(dest)
            costs[i][j] = (abs(sy - ty) + abs(sx - tx) + int(source["color"] != dest["color"])) \
                if source_shape == target_shape else 10000
        for j in range(m, m + n):
            costs[i][j] = len(source["nodes"]) + 1
    for i in range(n, n + m):
        for j, (_, dest) in enumerate(right):
            costs[i][j] = len(dest["nodes"]) + 1
    rows, cols = linear_sum_assignment(costs)
    return sum(costs[i][j] for i, j in zip(rows, cols))


def residual(graphs, outputs, targets):
    errors = []
    for graph, target, target_graph in zip(graphs, outputs, targets):
        actual = grid_of(graph)
        if len(actual) != len(target) or any(len(a) != len(b) for a, b in zip(actual, target)):
            raise FragmentGap("extent_changed")
        pixel_error = sum(x != y for a, b in zip(actual, target) for x, y in zip(a, b))
        # Exact rendered equality remains the success condition. Otherwise,
        # object discrepancy is primary, with pixel discrepancy breaking ties.
        errors.append(0 if pixel_error == 0 else object_distance(graph, target_graph) * 901 + pixel_error)
    return tuple(errors)


def infer(train, limits=Limits()):
    """Only training pairs enter synthesis. No test inputs or identifiers."""
    if not train:
        return {"status": "empty_training", "program": None}
    try:
        starts = [abstract(pair["input"]) for pair in train]
        targets = [abstract(pair["output"]) for pair in train]
    except FragmentGap as error:
        return {"status": str(error), "program": None, "evaluations": 0}
    if any((len(p["input"]), len(p["input"][0])) !=
           (len(p["output"]), len(p["output"][0])) for p in train):
        return {"status": "extent_change_outside_fragment", "program": None, "evaluations": 0}
    outputs = [p["output"] for p in train]
    initial = residual(starts, outputs, targets)
    beam = [(sum(initial), [], starts, initial)]
    seen = {state_key(starts)}
    evaluations, rejected, history = 0, 0, []
    for depth in range(limits.depth + 1):
        exact = [entry for entry in beam if entry[0] == 0]
        if exact:
            _, program, _, _ = min(exact, key=lambda entry: canonical(entry[1]))
            return {"status": "train_exact", "program": program,
                    "compiled": compile_program(program), "evaluations": evaluations,
                    "rejected": rejected, "search_trace": history,
                    "training_digest": digest(train), "limits": asdict(limits),
                    "selection": "shortest_depth_then_lexical_within_retained_beam",
                    "uniqueness_proved": False}
        if depth == limits.depth:
            break
        successors = []
        for _, program, graphs, prior in beam:
            proposals = {}
            for graph, target in zip(graphs, targets):
                proposals.update({canonical(step): step for step in propose(graph, target)})
            ordered = sorted(proposals, key=proposal_order)
            for key in ordered[:limits.candidates_per_state]:
                if evaluations >= limits.evaluations:
                    break
                evaluations += 1
                step = proposals[key]
                try:
                    transformed = [direct_step(graph, step) for graph in graphs]
                    errors = residual(transformed, outputs, targets)
                except (ValueError, KeyError, TypeError, AssertionError, IndexError):
                    rejected += 1
                    continue
                # Casewise residual improvement: never hide damage in aggregate fit.
                if sum(errors) >= sum(prior) or any(a > b for a, b in zip(errors, prior)):
                    continue
                identity = state_key(transformed)
                if identity in seen:
                    continue
                seen.add(identity)
                successors.append((sum(errors), program + [step], transformed, errors))
            if evaluations >= limits.evaluations:
                break
        successors.sort(key=lambda entry: (entry[0], canonical(entry[1])))
        beam = successors[:limits.beam]
        history.append({"depth": depth + 1, "evaluations": evaluations,
                        "retained": [{"residual": list(e[3]), "program": e[1]} for e in beam]})
        if not beam:
            break
    return {"status": "budget_exhausted_unknown" if evaluations >= limits.evaluations
            else "no_program_in_explored_fragment", "program": None,
            "evaluations": evaluations, "rejected": rejected,
            "search_trace": history, "limits": asdict(limits)}

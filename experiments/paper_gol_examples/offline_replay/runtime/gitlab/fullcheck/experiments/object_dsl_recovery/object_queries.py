"""Experimental typed queries over abstract objects; no grid transformations.

Tree and linear connector interpreters share these small relation primitives.
These signatures are local to the pilot, not additions to authority registries.
"""
from __future__ import annotations

from collections import deque
from fractions import Fraction
from hashlib import sha256
from pathlib import Path


SIGNATURES = {
    "selected": ((), "ObjectSet"),
    "parents": (("ObjectSet",), "ObjectSet"),
    "color_parents": (("ObjectSet",), "ObjectSet"),
    "same_color": (("ObjectSet",), "ObjectSet"),
    "children": (("ObjectSet",), "ObjectSet"),
    "color": (("ObjectSet",), "ObjectSet"),
    "difference": (("ObjectSet", "ObjectSet"), "ObjectSet"),
    "color_mass": (("ObjectSet",), "ObjectSet"),
    "direction": (("ObjectSet", "ObjectSet"), "arga:DirectionValue"),
}


class QueryGap(ValueError):
    pass


def implementation_sha():
    return sha256(Path(__file__).read_bytes()).hexdigest()


class ObjectRelations:
    def __init__(self, graph):
        self.graph = graph
        self.nodes = dict(graph.graph.nodes(data=True))
        self.children = {}
        for parent, data in self.nodes.items():
            wall = set(map(tuple, data["nodes"]))
            self.children[parent] = self.contained_by(wall)
        self.color_groups = {}
        for color in sorted({d["color"] for d in self.nodes.values()}):
            parents = frozenset(n for n, d in self.nodes.items() if d["color"] == color)
            wall = {tuple(p) for n in parents for p in self.nodes[n]["nodes"]}
            self.color_groups[color] = (parents, self.contained_by(wall))

    def contained_by(self, wall):
        lo_y, hi_y = min(p[0] for p in wall) - 1, max(p[0] for p in wall) + 1
        lo_x, hi_x = min(p[1] for p in wall) - 1, max(p[1] for p in wall) + 1
        outside = {(lo_y, lo_x)}
        queue = deque(outside)
        while queue:
            y, x = queue.popleft()
            for point in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                py, px = point
                if lo_y <= py <= hi_y and lo_x <= px <= hi_x and point not in wall and point not in outside:
                    outside.add(point)
                    queue.append(point)
        inside = {(y, x) for y in range(lo_y + 1, hi_y)
                  for x in range(lo_x + 1, hi_x)
                  if (y, x) not in wall and (y, x) not in outside}
        return frozenset(child for child, attrs in self.nodes.items()
                         if set(map(tuple, attrs["nodes"])).issubset(inside))

    def apply(self, operation, arguments, params, selected):
        if operation == "selected":
            return frozenset((selected,))
        if operation == "parents":
            return frozenset(parent for parent, children in self.children.items() if children & arguments[0])
        if operation == "color_parents":
            return frozenset(parent for parents, children in self.color_groups.values()
                             if children & arguments[0] for parent in parents)
        if operation == "same_color":
            colors = {self.nodes[n]["color"] for n in arguments[0]}
            return frozenset(n for n, d in self.nodes.items() if d["color"] in colors)
        if operation == "children":
            return frozenset(child for parent in arguments[0] for child in self.children[parent])
        if operation == "color":
            return frozenset(n for n in arguments[0] if self.nodes[n]["color"] == params["value"])
        if operation == "difference":
            return arguments[0] - arguments[1]
        if operation == "color_mass":
            groups = {}
            for node in arguments[0]:
                groups.setdefault(self.nodes[node]["color"], set()).add(node)
            if not groups:
                return frozenset()
            masses = {color: len({tuple(p) for n in nodes for p in self.nodes[n]["nodes"]})
                      for color, nodes in groups.items()}
            extreme = (min if params["extreme"] == "min" else max)(masses.values())
            return frozenset(n for color, nodes in groups.items() if masses[color] == extreme for n in nodes)
        if operation == "direction":
            centers = []
            for group in arguments:
                cells = {tuple(p) for node in group for p in self.nodes[node]["nodes"]}
                if not cells:
                    raise QueryGap("empty_direction_reference")
                centers.append(tuple(Fraction(sum(p[i] for p in cells), len(cells)) for i in (0, 1)))
            dy, dx = (centers[1][i] - centers[0][i] for i in (0, 1))
            if dy == 0 and dx == 0:
                raise QueryGap("coincident_reference_centroids")
            return "_".join(p for p in (
                "DOWN" if dy > 0 else "UP" if dy < 0 else "",
                "RIGHT" if dx > 0 else "LEFT" if dx < 0 else "") if p)
        raise QueryGap("unknown_query_operation")


def expression(operation, *arguments, **params):
    return {"op": operation, "args": list(arguments), "params": params}


def compile_query(tree):
    code = []

    def lower(node, depth=0):
        if depth > 12 or len(code) >= 64:
            raise QueryGap("query_size_limit")
        name = node["op"]
        if name not in SIGNATURES:
            raise QueryGap("unknown_query_operation")
        expected_inputs, output = SIGNATURES[name]
        lowered = [lower(child, depth+1) for child in node["args"]]
        if tuple(t for _, t in lowered) != expected_inputs:
            raise QueryGap("query_type_mismatch")
        params = node["params"]
        required_params = {"value"} if name == "color" else {"extreme"} if name == "color_mass" else set()
        if set(params) != required_params:
            raise QueryGap("query_parameter_mismatch")
        if name == "color" and (type(params["value"]) is not int or not 0 <= params["value"] <= 9):
            raise QueryGap("invalid_color_parameter")
        if name == "color_mass" and params["extreme"] not in ("min", "max"):
            raise QueryGap("invalid_extreme_parameter")
        index = len(code)
        code.append({"connector": "experimental:object_query:" + name,
                     "operation": name, "inputs": [i for i, _ in lowered],
                     "params": params, "output_type": output})
        return index, output

    _, output = lower(tree)
    return {"source_sha256": implementation_sha(), "output_type": output, "instructions": code}


def evaluate_query(tree, relations, selected):
    return relations.apply(tree["op"],
                           [evaluate_query(c, relations, selected) for c in tree["args"]],
                           tree["params"], selected)


def execute_query(code, relations, selected):
    if code["source_sha256"] != implementation_sha():
        raise QueryGap("stale_query_source")
    values = []
    for instruction in code["instructions"]:
        if any(type(i) is not int or i < 0 or i >= len(values) for i in instruction["inputs"]):
            raise QueryGap("invalid_query_reference")
        value = relations.apply(instruction["operation"], [values[i] for i in instruction["inputs"]],
                                instruction["params"], selected)
        values.append(value)
    return values[-1]


def direction_hypotheses(relations, selected, observed_direction):
    """Compose bounded context queries, then abduce reference roles from objects.

    No expected output is retained by a query. The observed direction only
    decides which hypotheses to offer to demonstration-wide program validation.
    """
    subject = expression("selected")
    scopes = [expression("children", expression("parents", subject)),
              expression("children", expression("same_color", expression("parents", subject))),
              expression("children", expression("color_parents", subject))]
    scopes += [expression("difference", scope, expression("same_color", subject))
               for scope in scopes]
    for scope in scopes:
        objects = evaluate_query(scope, relations, selected)
        colors = sorted({relations.nodes[n]["color"] for n in objects})
        references = [expression("color", scope, value=color) for color in colors]
        references += [expression("color_mass", scope, extreme=extreme) for extreme in ("min", "max")]
        values = [evaluate_query(reference, relations, selected) for reference in references]
        for start, start_value in zip(references, values):
            for end, end_value in zip(references, values):
                if not start_value or not end_value or start_value == end_value:
                    continue
                try:
                    if relations.apply("direction", [start_value, end_value], {}, selected) == observed_direction:
                        yield expression("direction", start, end)
                except QueryGap:
                    continue

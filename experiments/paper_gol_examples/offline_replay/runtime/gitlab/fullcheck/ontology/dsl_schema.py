"""Wake/dream DSL ontology projection.

This module is the executable projection of the DSL schema ontology.
Bridge code must resolve solution-path actions, filters, and parameters through
this schema before a support profile can be emitted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


SCHEMA_VERSION = "dsl_schema.v1"
SCHEMA_TTL_PATH = "ontology/wake_action_schema.ttl"
SHACL_TTL_PATH = "ontology/wake_action_shapes.ttl"


class OntologySchemaError(ValueError):
    """Raised when a wake solution path is not linked to ontology schema."""


@dataclass(frozen=True)
class ActionSchema:
    name: str
    role: str
    ontology_iri: str
    class_iri: str
    domain_iri: str
    range_iri: str
    parameter_keys: frozenset[str] | None = None


@dataclass(frozen=True)
class ParameterSchema:
    name: str
    ontology_iri: str
    class_iri: str
    domain_iri: str
    range_iri: str


@dataclass(frozen=True)
class ParameterSlot:
    name: str
    ontology_iri: str
    range_iri: str
    node_id: str = ""
    owner_kind: str = ""


@dataclass(frozen=True)
class DSLSpectrumMark:
    name: str
    ontology_iri: str
    matching_terms: frozenset[str]
    family_vector_dimension: str
    class_iri: str = "arga:DSLSpectrumMark"
    domain_iri: str = "arga:DSLExpression"
    range_iri: str = "arga:FamilyVectorDimension"


TRANSFORMATION_NAMES = frozenset({
    "add_border",
    "basic_grid",
    "beam",
    "connect_aligned_nodes",
    "count_grid",
    "crop",
    "downscale_grid",
    "duplicate",
    "extend_node",
    "extract",
    "fill",
    "hollow_rectangle",
    "insert",
    "magnet",
    "move_node",
    "move_node_max",
    "overlay",
    "recolor",
    "remove_node",
    "summary_grid",
    "symmetry_grid",
    "tile_grid",
    "update_color",
    "upscale_grid",
    "arbitrary_duplicate",
    "connect",
    "fill_rectangle",
    "flip",
    "mirror",
    "mirror_grid",
    "neighborhood_grid",
    "placement_grid",
    "pyramid_grid",
    "rotate_duplicate",
    "rotate_grid",
    "rotate_node",
    "shift",
    "squeeze",
    "truncate",
})


FILTER_PARAMETER_KEYS = {
    "filter_by_color": frozenset({"color", "exclude"}),
    "filter_by_color_component_count": frozenset({"count", "exclude"}),
    "filter_by_fit": frozenset({
        "source_shape",
        "target_shape",
        "cavity_color",
        "min_surrounding_sides",
        "facing",
        "shape_transform",
        "min_contact_count",
        "max_axis_gap",
        "alignment",
        "exclude",
    }),
    "filter_by_occlusion": frozenset({"occluded", "exclude"}),
    "filter_by_shape": frozenset({"shape", "exclude"}),
    "filter_by_size": frozenset({"size", "exclude"}),
    "filter_by_target": frozenset({"target", "exclude"}),
    "filter_by_degree": frozenset({"degree", "exclude"}),
    "filter_by_neighbor_color": frozenset({"color", "exclude"}),
    "filter_by_neighbor_degree": frozenset({"degree", "exclude"}),
    "filter_by_neighbor_size": frozenset({"size", "exclude"}),
}


BINDER_PARAMETER_KEYS = {
    "param_bind_aligned_node_by_color": frozenset({"color", "exclude"}),
    "param_bind_neighbor_by_color": frozenset({"color", "exclude"}),
    "param_bind_neighbor_by_size": frozenset({"size", "exclude"}),
    "param_bind_neighbor_by_degree": frozenset({"degree", "exclude"}),
    "param_bind_node_by_color": frozenset({"color", "exclude"}),
    "param_bind_node_by_shape": frozenset(),
    "param_bind_node_by_size": frozenset({"size", "exclude"}),
    "param_bind_other_node_same_color": frozenset(),
}


TRANSFORMATION_PARAMETER_KEYS = {
    "add_border": frozenset({"border_color", "border_type"}),
    "arbitrary_duplicate": frozenset({"mirror", "duplicate_arbitrary", "axis", "mirror_grid", "combine_pattern", "concat_axis"}),
    "basic_grid": frozenset({"transform_type", "background_color", "factor", "degrees", "mirror_axis", "component_mode", "selection", "output_mode", "crop_height", "crop_width", "corner", "height_divisor", "width_divisor", "split_mode", "pattern_mode", "marker_color", "padding_rows", "padding_cols", "frequency_mode", "require_full_extent", "require_isolated"}),
    "beam": frozenset({"color1", "color2", "beam_type", "classifier_params"}),
    "connect": frozenset({"connect_mode", "color", "fill_color", "border_color", "inherit_vertical"}),
    "connect_aligned_nodes": frozenset({"connector_type"}),
    "count_grid": frozenset({"count_type", "background_color", "output_color"}),
    "crop": frozenset({"corner", "crop_type", "grid_size", "fill_color", "border_color", "fill_direction", "connect_all"}),
    "downscale_grid": frozenset({"factor", "downscale_type", "background_color"}),
    "duplicate": frozenset({"axis", "duplicate", "color1", "mirror", "concat_axis", "combine_pattern", "duplication_type"}),
    "extend_node": frozenset({"direction", "overlap"}),
    "extract": frozenset({"fill_color", "crop_filterless", "fraction", "extract_type"}),
    "fill": frozenset({"object", "color", "color1", "classifier_params"}),
    "fill_rectangle": frozenset({"fill_color", "overlap"}),
    "flip": frozenset({"mirror_direction"}),
    "hollow_rectangle": frozenset({"fill_color"}),
    "insert": frozenset({"object_index", "point", "relative_pos"}),
    "magnet": frozenset({"magnet_type", "shifting_direction", "color1", "color2", "grid_size"}),
    "mirror": frozenset({"mirror_axis"}),
    "mirror_grid": frozenset({"mirror_axis", "mirror_type", "color1", "color2"}),
    "move_node": frozenset({"direction", "steps"}),
    "move_node_max": frozenset({"direction"}),
    "neighborhood_grid": frozenset({"neighborhood_type", "object_color", "background_color", "color1", "color2", "color3", "color4", "classifier_params"}),
    "overlay": frozenset({"fold", "overlay", "marker_color", "separator_color", "background_color", "connectivity", "output_color", "split_axis"}),
    "placement_grid": frozenset({"placement_type", "object_color", "guide_color", "separator_color", "background_color"}),
    "pyramid_grid": frozenset({"pattern_type", "base_color", "upper_color", "lower_color", "background_color"}),
    "recolor": frozenset({"recolor_type", "color1", "color2", "shifting_direction", "classifier_params"}),
    "remove_node": frozenset(),
    "rotate_duplicate": frozenset({"mirror", "rotation_degrees"}),
    "rotate_grid": frozenset({"degrees"}),
    "rotate_node": frozenset({"rotation_dir"}),
    "shift": frozenset({"color1"}),
    "squeeze": frozenset({"axis", "keep_occluded"}),
    "summary_grid": frozenset({"summary_type", "background_color", "output_width", "output_color", "color1", "classifier_params"}),
    "symmetry_grid": frozenset({"source_color", "fill_color", "symmetry_type", "center_mode", "background_color", "mirror_axis", "duplicate_mode", "occluder_color", "occluder_colors", "period_mode", "max_period", "pattern_type", "unknown_mode", "out_shift_row", "out_shift_col", "direction", "output_scale", "output_height", "output_width", "selector_mode", "selector_color", "tile_source"}),
    "tile_grid": frozenset({"tile_type", "background_color", "fill_color", "output_width", "output_color", "color1", "classifier_params"}),
    "truncate": frozenset({"color1", "color2", "grid_size", "truncate_type", "mirror"}),
    "update_color": frozenset({"color"}),
    "upscale_grid": frozenset({"factor", "mirror", "upscale_type", "color", "border_color", "fill_color", "classifier_params"}),
}


DSL_SPECTRUM_MARK_TERMS: dict[str, frozenset[str]] = {
    "marker_anchor_guided": frozenset({
        "marker", "markers", "anchor", "anchors", "target", "targets",
        "placeholder", "placeholders", "satellite", "pivot", "seed", "guide",
        "guides",
    }),
    "separator_region_guided": frozenset({
        "separator", "separators", "lattice", "cell", "cells", "region",
        "regions", "block", "blocks", "partition", "partitions",
        "split", "splits", "fold", "folds", "folding",
    }),
    "rectangle_frame_geometry": frozenset({
        "rectangle", "rectangles", "rectangular", "frame", "frames",
        "border", "borders", "hollow", "square", "squares", "ring",
        "rings", "corner", "corners", "bbox", "bounding",
    }),
    "projection_path_line": frozenset({
        "project", "projection", "diagonal", "diagonals", "line", "lines",
        "ray", "rays", "path", "paths", "corridor", "corridors", "bridge",
        "span", "between", "connect", "connector", "connectors", "through",
        "across", "waterfall", "staircase", "beam", "beams",
    }),
    "template_pattern_stamp": frozenset({
        "stamp", "template", "copy", "duplicate", "tile", "tiles", "tiling",
        "motif", "motifs", "overlay", "overlap", "layer", "layers",
        "compose", "composition",
        "pattern", "patterns", "mask", "masks", "repeat", "repeated",
        "periodic", "unit", "external", "symbol", "symbols",
    }),
    "symmetry_reflection_rotation": frozenset({
        "reflect", "reflection", "mirror", "mirrored", "symmetric",
        "symmetry", "symmetrize", "opposite", "counterpart", "rotate",
        "rotation", "axis", "axes",
    }),
    "component_shape_object": frozenset({
        "component", "components", "shape", "shapes", "foreground",
        "object", "objects", "blob", "blobs", "cluster", "clusters",
        "isolated", "isolate",
    }),
    "background_hole_gap": frozenset({
        "background", "hole", "holes", "empty", "gap", "gaps", "zero",
        "blank", "cutout", "enclosure", "inside", "interior",
        "cavity", "cavities", "pocket", "pockets", "void", "voids",
    }),
    "partially_surrounded_subshape": frozenset({
        "subshape", "subshapes", "partial", "partially", "surround",
        "surrounded", "surrounding", "enclose", "enclosed", "enclosing",
    }),
    "shape_fit_relation": frozenset({
        "fit", "fits", "fitting", "match", "matches", "matching",
        "compatible", "compatibility", "shapelet", "shapelets",
    }),
    "row_column_band": frozenset({
        "row", "rows", "column", "columns", "vertical", "horizontal",
        "top", "bottom", "left", "right", "middle", "strip", "strips",
        "bar", "bars", "band", "bands", "prefix",
    }),
    "color_label_count_rank": frozenset({
        "color", "colors", "colored", "recolor", "palette", "label",
        "labels", "count", "counts", "distinct", "role", "roles", "value",
        "values", "rank", "frequency", "frequent", "rarest", "unique",
        "dominant", "parity",
    }),
    "scale_size_quantity": frozenset({
        "scale", "scaled", "upscale", "downscale", "expand", "expanded",
        "expansion", "subgrid", "subgrids", "extent", "full", "size", "sizes",
        "largest", "smallest", "height", "width", "area", "length",
        "quantity", "number",
    }),
    "adjacency_proximity": frozenset({
        "adjacent", "adjacency", "neighbor", "neighborhood", "nearest",
        "proximity", "touch", "touching", "edge", "edges", "side", "sides",
    }),
    "unclassified_operation_mode": frozenset(),
}


DSL_SPECTRUM_STOP_TERMS = frozenset({
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into",
    "of", "on", "or", "the", "to", "with",
})


PARAMETER_RANGES = {
    "axis": "arga:AxisValue",
    "background_color": "arga:Color",
    "beam_type": "arga:SemanticNameValue",
    "border_color": "arga:Color",
    "border_type": "arga:SemanticNameValue",
    "class_color_map": "arga:StructuredValue",
    "cavity_color": "arga:Color",
    "classifier_params": "arga:StructuredValue",
    "color": "arga:Color",
    "color1": "arga:Color",
    "color2": "arga:Color",
    "color_map": "arga:StructuredValue",
    "combine_pattern": "arga:SemanticNameValue",
    "concat_axis": "arga:AxisValue",
    "connector_type": "arga:SemanticNameValue",
    "count": "arga:CountValue",
    "crop_filterless": "arga:BooleanValue",
    "crop_type": "arga:SemanticNameValue",
    "direction": "arga:DirectionValue",
    "degree": "arga:CountValue",
    "downscale_type": "arga:SemanticNameValue",
    "duplicate": "arga:BooleanValue",
    "duplicate_type": "arga:SemanticNameValue",
    "duplication_type": "arga:SemanticNameValue",
    "exclude": "arga:BooleanValue",
    "extract_type": "arga:SemanticNameValue",
    "factor": "arga:IntegerValue",
    "facing": "arga:SemanticNameValue",
    "fill_type": "arga:SemanticNameValue",
    "fill_color": "arga:Color",
    "fold": "arga:SemanticNameValue",
    "frequency_mode": "arga:SemanticNameValue",
    "fraction": "arga:NumericValue",
    "frame_color": "arga:Color",
    "grid_size": "arga:IntegerValue",
    "kind": "arga:SemanticNameValue",
    "magnet_type": "arga:SemanticNameValue",
    "marker_color": "arga:Color",
    "alignment": "arga:SemanticNameValue",
    "mirror": "arga:BooleanValue",
    "mirror_axis": "arga:AxisValue",
    "mirror_color": "arga:Color",
    "mode": "arga:SemanticNameValue",
    "min_surrounding_sides": "arga:IntegerValue",
    "min_contact_count": "arga:IntegerValue",
    "object": "arga:SemanticNameValue",
    "object_index": "arga:IntegerValue",
    "occluded": "arga:BooleanValue",
    "operation": "arga:SemanticNameValue",
    "other_marker_color": "arga:Color",
    "output_color": "arga:Color",
    "output_mode": "arga:SemanticNameValue",
    "overlap": "arga:SemanticNameValue",
    "overlay": "arga:SemanticNameValue",
    "pattern_type": "arga:SemanticNameValue",
    "placement_type": "arga:SemanticNameValue",
    "point": "arga:StructuredValue",
    "recolor_type": "arga:SemanticNameValue",
    "relative_pos": "arga:RelativePositionValue",
    "require_full_extent": "arga:BooleanValue",
    "selection": "arga:SemanticNameValue",
    "shape": "arga:ShapeValue",
    "shape_transform": "arga:SemanticNameValue",
    "shifting_direction": "arga:DirectionValue",
    "size": "arga:SizeValue",
    "source_color": "arga:Color",
    "source_shape": "arga:ShapeValue",
    "split_axis": "arga:AxisValue",
    "split_mode": "arga:SemanticNameValue",
    "rotation_count": "arga:RotationCountValue",
    "rotations": "arga:RotationCountValue",
    "steps": "arga:DistanceValue",
    "supported_variants": "arga:StructuredValue",
    "symmetry": "arga:SemanticNameValue",
    "symmetry_type": "arga:SemanticNameValue",
    "target": "arga:StructuredValue",
    "target_color": "arga:Color",
    "target_shape": "arga:ShapeValue",
    "max_axis_gap": "arga:IntegerValue",
    "test_guard": "arga:StructuredValue",
    "tile_type": "arga:SemanticNameValue",
    "transform_type": "arga:SemanticNameValue",
    "upscale_type": "arga:SemanticNameValue",
    "variant": "arga:SemanticNameValue",
    "base_color": "arga:Color",
    "center_mode": "arga:SemanticNameValue",
    "color3": "arga:Color",
    "color4": "arga:Color",
    "component_mode": "arga:SemanticNameValue",
    "connect_all": "arga:BooleanValue",
    "connect_mode": "arga:SemanticNameValue",
    "connectivity": "arga:SemanticNameValue",
    "corner": "arga:SemanticNameValue",
    "count_type": "arga:SemanticNameValue",
    "crop_height": "arga:IntegerValue",
    "crop_width": "arga:IntegerValue",
    "degrees": "arga:RotationCountValue",
    "duplicate_arbitrary": "arga:IntegerValue",
    "duplicate_mode": "arga:SemanticNameValue",
    "fill_direction": "arga:DirectionValue",
    "grid": "arga:StructuredValue",
    "guide_color": "arga:Color",
    "height_divisor": "arga:IntegerValue",
    "inherit_vertical": "arga:BooleanValue",
    "keep_occluded": "arga:BooleanValue",
    "lower_color": "arga:Color",
    "max_period": "arga:IntegerValue",
    "mirror_direction": "arga:DirectionValue",
    "mirror_grid": "arga:BooleanValue",
    "mirror_type": "arga:SemanticNameValue",
    "neighborhood_type": "arga:SemanticNameValue",
    "object_color": "arga:Color",
    "occluder_color": "arga:Color",
    "occluder_colors": "arga:StructuredValue",
    "out_shift_col": "arga:DistanceValue",
    "out_shift_row": "arga:DistanceValue",
    "output_height": "arga:IntegerValue",
    "output_scale": "arga:IntegerValue",
    "output_width": "arga:IntegerValue",
    "padding_cols": "arga:IntegerValue",
    "padding_rows": "arga:IntegerValue",
    "pattern_mode": "arga:SemanticNameValue",
    "period_mode": "arga:SemanticNameValue",
    "require_isolated": "arga:BooleanValue",
    "rotation_degrees": "arga:RotationCountValue",
    "rotation_dir": "arga:SemanticNameValue",
    "selector_color": "arga:Color",
    "selector_mode": "arga:SemanticNameValue",
    "separator_color": "arga:Color",
    "tile_source": "arga:SemanticNameValue",
    "truncate_type": "arga:SemanticNameValue",
    "unknown_mode": "arga:SemanticNameValue",
    "upper_color": "arga:Color",
    "width_divisor": "arga:IntegerValue",
    "summary_type": "arga:SemanticNameValue",
}


RANGE_PARENTS = {
    "arga:AxisValue": {"arga:ParameterValue"},
    "arga:BooleanValue": {"arga:ParameterValue"},
    "arga:Color": {"arga:DiscreteValue"},
    "arga:CountValue": {"arga:IntegerValue"},
    "arga:DirectionValue": {"arga:ParameterValue"},
    "arga:DiscreteValue": {"arga:ParameterValue"},
    "arga:DistanceValue": {"arga:IntegerValue"},
    "arga:IntegerValue": {"arga:NumericValue", "arga:DiscreteValue"},
    "arga:NumericValue": {"arga:ParameterValue"},
    "arga:RelativePositionValue": {"arga:ParameterValue"},
    "arga:RotationCountValue": {"arga:IntegerValue"},
    "arga:SemanticNameValue": {"arga:ParameterValue"},
    "arga:ShapeValue": {"arga:ParameterValue"},
    "arga:SizeValue": {"arga:IntegerValue"},
    "arga:StructuredValue": {"arga:ParameterValue"},
}


EXPLICIT_RANGE_COMPATIBILITY = {
    frozenset({"arga:Color", "arga:CountValue"}),
    frozenset({"arga:Color", "arga:IntegerValue"}),
    frozenset({"arga:DistanceValue", "arga:RotationCountValue"}),
}


TRANSFORMATION_ACTIONS = {
    name: ActionSchema(
        name=name,
        role="transform",
        ontology_iri=f"arga:action_{name}",
        class_iri="arga:TransformationAction",
        domain_iri="arga:ARCGraph",
        range_iri="arga:ARCGraph",
        parameter_keys=TRANSFORMATION_PARAMETER_KEYS[name],
    )
    for name in sorted(TRANSFORMATION_NAMES)
}


FILTER_ACTIONS = {
    name: ActionSchema(
        name=name,
        role="filter",
        ontology_iri=f"arga:filter_{name}",
        class_iri="arga:FilterAction",
        domain_iri="arga:ARCGraph",
        range_iri="arga:OperationBinding",
        parameter_keys=parameter_keys,
    )
    for name, parameter_keys in sorted(FILTER_PARAMETER_KEYS.items())
}


BINDER_ACTIONS = {
    name: ActionSchema(
        name=name,
        role="binder",
        ontology_iri=f"arga:binder_{name}",
        class_iri="arga:BinderAction",
        domain_iri="arga:OperationBinding",
        range_iri="arga:OperationBinding",
        parameter_keys=parameter_keys,
    )
    for name, parameter_keys in sorted(BINDER_PARAMETER_KEYS.items())
}


REALIZED_RULE_ACTION = ActionSchema(
    name="dream_rule:*",
    role="transform",
    ontology_iri="arga:action_realized_wake_rule",
    class_iri="arga:RealizedWakeRuleAction",
    domain_iri="arga:ARCGraph",
    range_iri="arga:ARCGraph",
    parameter_keys=None,
)


PARAMETERS = {
    name: ParameterSchema(
        name=name,
        ontology_iri=f"arga:param_{name}",
        class_iri="arga:ActionParameter",
        domain_iri="arga:ParameterizedNode",
        range_iri=range_iri,
    )
    for name, range_iri in sorted(PARAMETER_RANGES.items())
}


DSL_SPECTRUM_MARKS = {
    name: DSLSpectrumMark(
        name=name,
        ontology_iri=f"arga:dslSpectrumMark_{name}",
        matching_terms=terms,
        family_vector_dimension=name,
    )
    for name, terms in sorted(DSL_SPECTRUM_MARK_TERMS.items())
}


def resolve_action(role: str, name: str) -> ActionSchema:
    if role == "transform":
        if name.startswith("dream_rule:"):
            return REALIZED_RULE_ACTION
        schema = TRANSFORMATION_ACTIONS.get(name)
    elif role == "filter":
        schema = FILTER_ACTIONS.get(name)
    else:
        schema = None
    if schema is None:
        raise OntologySchemaError(f"unknown {role} action {name!r}")
    return schema


def resolve_parameter(owner_schema: ActionSchema | None, name: str) -> ParameterSchema:
    if owner_schema and owner_schema.parameter_keys is not None:
        if name not in owner_schema.parameter_keys:
            raise OntologySchemaError(
                f"parameter {name!r} is not declared for {owner_schema.name!r}"
            )
    schema = PARAMETERS.get(name)
    if schema is None:
        raise OntologySchemaError(f"unknown parameter {name!r}")
    return schema


def resolve_spectrum_mark(name: str) -> DSLSpectrumMark:
    schema = DSL_SPECTRUM_MARKS.get(name)
    if schema is None:
        raise OntologySchemaError(f"unknown dsl_spectrum mark {name!r}")
    return schema


def schema_ref(value: ActionSchema | ParameterSchema | DSLSpectrumMark) -> dict[str, Any]:
    return {
        "ontology_iri": value.ontology_iri,
        "class_iri": value.class_iri,
        "domain_iri": value.domain_iri,
        "range_iri": value.range_iri,
    }


def dsl_terms_for_value(value: str) -> list[str]:
    return [
        term
        for term in re.split(r"[_\W]+", str(value).lower())
        if term and term not in DSL_SPECTRUM_STOP_TERMS
    ]


def spectrum_marks_for_terms(terms: list[str]) -> list[str]:
    term_set = set(terms)
    marks = [
        name
        for name, schema in DSL_SPECTRUM_MARKS.items()
        if schema.matching_terms and term_set & set(schema.matching_terms)
    ]
    return marks or ["unclassified_operation_mode"]


def spectrum_marks_for_value(value: str) -> list[str]:
    return spectrum_marks_for_terms(dsl_terms_for_value(value))


def all_schema_iris() -> set[str]:
    iris = {REALIZED_RULE_ACTION.ontology_iri}
    iris.update(schema.ontology_iri for schema in TRANSFORMATION_ACTIONS.values())
    iris.update(schema.ontology_iri for schema in FILTER_ACTIONS.values())
    iris.update(schema.ontology_iri for schema in PARAMETERS.values())
    iris.update(schema.ontology_iri for schema in DSL_SPECTRUM_MARKS.values())
    return iris


def range_ancestors(range_iri: str) -> set[str]:
    """Return range_iri plus its declared ontology ancestors."""

    seen: set[str] = set()
    frontier = [range_iri]
    while frontier:
        current = frontier.pop()
        if not current or current in seen:
            continue
        seen.add(current)
        frontier.extend(sorted(RANGE_PARENTS.get(current, set())))
    return seen


def parameter_ranges_compatible(left: str, right: str) -> bool:
    """Return whether two parameter value domains can be probed as compatible."""

    if not left or not right:
        return False
    if left == right:
        return True
    left_ancestors = range_ancestors(left)
    right_ancestors = range_ancestors(right)
    if left in right_ancestors or right in left_ancestors:
        return True
    if frozenset({left, right}) in EXPLICIT_RANGE_COMPATIBILITY:
        return True
    for left_item in left_ancestors:
        for right_item in right_ancestors:
            if frozenset({left_item, right_item}) in EXPLICIT_RANGE_COMPATIBILITY:
                return True
    return False


def parameter_slot_from_node(node: dict[str, Any]) -> ParameterSlot:
    return ParameterSlot(
        name=str(node.get("name") or ""),
        ontology_iri=str(node.get("ontology_iri") or ""),
        range_iri=str(node.get("range_iri") or ""),
        node_id=str(node.get("id") or ""),
        owner_kind=str(node.get("owner_kind") or ""),
    )


def parameter_slots_from_profile(graph: dict[str, Any]) -> list[ParameterSlot]:
    return [
        parameter_slot_from_node(node)
        for node in graph.get("nodes") or []
        if isinstance(node, dict) and node.get("kind") == "parameter"
    ]


def parameter_slots_compatible(source: ParameterSlot, target: ParameterSlot) -> bool:
    if not source.range_iri or not target.range_iri:
        return False
    return parameter_ranges_compatible(source.range_iri, target.range_iri)


def compatible_parameter_mappings(
    source_slots: list[ParameterSlot],
    target_slots: list[ParameterSlot],
) -> list[dict[str, Any]]:
    """Return all ontology-compatible parameter slot pairings.

    Exact parameter-name equality is only one case. A mapping is also valid when
    the SHACL/ontology value-domain graph says the source and target ranges are
    compatible.
    """

    mappings: list[dict[str, Any]] = []
    for source in source_slots:
        for target in target_slots:
            if not parameter_slots_compatible(source, target):
                continue
            mappings.append({
                "source_name": source.name,
                "source_ontology_iri": source.ontology_iri,
                "source_range_iri": source.range_iri,
                "target_name": target.name,
                "target_ontology_iri": target.ontology_iri,
                "target_range_iri": target.range_iri,
                "match_kind": "exact_name"
                if source.name == target.name
                else "compatible_range",
            })
    return mappings


def validate_operation_profile_graph(graph: dict[str, Any]) -> list[str]:
    """Return SHACL-equivalent validation errors for a serialized profile graph."""

    errors: list[str] = []
    if graph.get("ontology_bound") is not True:
        errors.append("graph must be ontology_bound")
    if graph.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"graph schema_version must be {SCHEMA_VERSION}")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append("graph must contain nodes")
        return errors
    operation_nodes = [
        node for node in nodes
        if isinstance(node, dict) and node.get("kind") == "operation_expression"
    ]
    if not operation_nodes:
        errors.append("graph must contain operation_expression nodes")
    for node in nodes:
        if not isinstance(node, dict):
            errors.append("graph node must be an object")
            continue
        kind = node.get("kind")
        node_id = node.get("id") or "<node>"
        if kind in {"operation_expression", "action", "parameter", "selector"}:
            for key in ("class", "ontology_iri", "domain_iri", "range_iri"):
                if not node.get(key):
                    errors.append(f"{node_id} missing {key}")
        if kind == "action":
            role = str(node.get("role") or "")
            name = str(node.get("name") or "")
            try:
                schema = resolve_action(role, name)
            except OntologySchemaError as exc:
                errors.append(str(exc))
                continue
            if node.get("ontology_iri") != schema.ontology_iri:
                errors.append(f"{node_id} ontology_iri must be {schema.ontology_iri}")
            if node.get("domain_iri") != schema.domain_iri:
                errors.append(f"{node_id} domain_iri must be {schema.domain_iri}")
            if node.get("range_iri") != schema.range_iri:
                errors.append(f"{node_id} range_iri must be {schema.range_iri}")
        elif kind == "parameter":
            name = str(node.get("name") or "")
            try:
                schema = resolve_parameter(None, name)
            except OntologySchemaError as exc:
                errors.append(str(exc))
                continue
            if node.get("ontology_iri") != schema.ontology_iri:
                errors.append(f"{node_id} ontology_iri must be {schema.ontology_iri}")
            if node.get("domain_iri") != schema.domain_iri:
                errors.append(f"{node_id} domain_iri must be {schema.domain_iri}")
            if node.get("range_iri") != schema.range_iri:
                errors.append(f"{node_id} range_iri must be {schema.range_iri}")
    return errors

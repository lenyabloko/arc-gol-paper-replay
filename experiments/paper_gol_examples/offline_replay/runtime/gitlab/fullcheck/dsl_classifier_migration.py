"""Factored DSL classifier migration helpers.

Legacy DSL classifier strings such as ``solid_2x2_component_count_prefix``
mix three different layers:

- primitive numeric detection parameters (for example ``side=2``),
- OWL-level semantic classes (for example ``component_count_summary``),
- the executable DSL action (for example ``component_count_prefix``).

This module keeps a single migration table and exposes helpers that convert
legacy or descriptor values into canonical action names plus explicit
``classifier_params``.  The compatibility path lets old saved solutions replay
while new generated candidates can use factored descriptors.
"""

from copy import deepcopy


LEGACY_OWL_CLASSES_KEY = "owl_" + "guards"


SLOT_ALIASES = {
    "fill_object": "object",
}


def _spec(action, numeric=None, owl=None, primitive=None):
    return {
        "action": action,
        "numeric_parameters": numeric or {},
        "owl_classes": owl or [],
        "primitive_filters": primitive or [],
    }


CLASSIFIER_MIGRATIONS = {
    "beam_type": {
        # A one- or two-pixel periodic repeat is a primitive DSL repeat.
        # More than two pixels is a semantic line motif and must carry an
        # OWL class; the executable beam remains the DSL action.
        "pattern_line": _spec(
            "pattern_line",
            numeric={"min_source_pixels": 3},
            owl=["line_template_shape"],
        ),
        "center_node_pattern_line": _spec(
            "center_node_pattern_line",
            numeric={"min_source_pixels": 3},
            owl=["center_node_template_shape"],
        ),
        "periodic_line_alternation": _spec(
            "periodic_line_alternation",
            numeric={"min_source_pixels": 3},
            owl=["periodic_line_orbit_shape"],
        ),
    },
    "summary_type": {
        "binary_3x3_shape_symbol": _spec(
            "shape_symbol_summary",
            numeric={"tile_width": 3, "tile_height": 3, "output_width": 3, "output_height": 3},
            owl=["shape_symbol", "tile_shape"],
            primitive=[{"shape": "rectangle", "width": 3, "height": 3}],
        ),
        "three_4x4_glyph_rows": _spec(
            "glyph_row_summary",
            numeric={"tile_width": 4, "tile_height": 4, "row_count": 3},
            owl=["glyph_tile_shape", "horizontal_glyph_row"],
            primitive=[{"shape": "rectangle", "width": 4, "height": 4}],
        ),
        "single_color_label_marker_3x3": _spec(
            "label_marker_summary",
            numeric={"output_width": 3, "output_height": 3},
            owl=["single_color_label_marker"],
        ),
        "corner_center_line_marker_3x3": _spec(
            "marker_relation_summary",
            numeric={"output_width": 3, "output_height": 3},
            owl=["corner_marker", "center_line_marker"],
        ),
        "container_vertical_gap_prefix_3x3": _spec(
            "gap_prefix_summary",
            numeric={"output_width": 3, "output_height": 1},
            owl=["container_gap", "vertical_gap"],
        ),
        "solid_2x2_component_count_prefix": _spec(
            "component_count_prefix",
            numeric={"side": 2},
            owl=["component_count_summary"],
            primitive=[{"shape": "square", "side": 2, "solid": True}],
        ),
        "solid_2x2_component_count_checkerboard": _spec(
            "component_count_pattern_summary",
            numeric={"side": 2, "slot_pattern": "checkerboard_even"},
            owl=["component_count_summary", "checkerboard_slot_pattern"],
            primitive=[{"shape": "square", "side": 2, "solid": True}],
        ),
        "arrange_2x2_l_by_missing_corner": _spec(
            "arrange_by_missing_corner",
            numeric={"bbox_width": 2, "bbox_height": 2},
            owl=["l_component_shape", "missing_corner_role"],
        ),
    },
    "recolor_type": {
        "hollow_3x3_square_to_plus": _spec(
            "hollow_square_to_plus",
            numeric={"side": 3},
            owl=["hollow_frame_shape", "plus_shape"],
            primitive=[{"shape": "square", "side": 3}],
        ),
        "component_size_code_123": _spec(
            "component_size_code_palette",
            numeric={"palette": [1, 2, 3], "rank_order": "size_ascending"},
            owl=["component_size_rank"],
        ),
        "component_bbox_topology_126": _spec(
            "component_bbox_topology_palette",
            numeric={"palette": [1, 2, 6]},
            owl=["component_bbox_topology"],
        ),
        "component_shape_multiplicity_12": _spec(
            "component_shape_multiplicity_palette",
            numeric={"palette": [1, 2]},
            owl=["shape_multiplicity"],
        ),
        "gray_bar_extremes_12": _spec(
            "bar_extreme_rank_palette",
            numeric={"palette": [1, 2]},
            owl=["bar_shape", "extreme_rank"],
        ),
        "marker_column_palette_rows_243": _spec(
            "marker_column_row_palette",
            numeric={"palette": [2, 4, 3], "row_order": "top_to_bottom"},
            owl=["marker_column", "row_role"],
        ),
    },
    "neighborhood_type": {
        "marker_3x3_halo": _spec(
            "marker_halo",
            numeric={"halo_radius": 1, "output_width": 3, "output_height": 3},
            owl=["marker_shape", "halo_target"],
        ),
        "rare_singleton_3x3_border": _spec(
            "singleton_border",
            numeric={"border_size": 1, "output_width": 3, "output_height": 3},
            owl=["rare_singleton", "border_target"],
        ),
        "block_2x2_outer_corners": _spec(
            "outer_corner_labels",
            numeric={"side": 2},
            owl=["outer_corner_label_target", "marker_block"],
            primitive=[{"shape": "square", "side": 2, "solid": True}],
        ),
    },
    "upscale_type": {
        "sparse_odd_cells_to_4x4_blocks": _spec(
            "lattice_cells_to_blocks",
            numeric={"block_width": 4, "block_height": 4, "factor": 4},
            owl=["sparse_lattice_cell", "odd_cell"],
        ),
    },
    "object": {
        "background_square_3x3": _spec(
            "fill_background_square",
            numeric={"side": 3},
            owl=["square_hole", "background_region"],
            primitive=[{"shape": "square", "side": 3}],
        ),
        "separator_cross_region_palette_24631": _spec(
            "separator_cross_region_palette",
            numeric={"palette": [2, 4, 6, 3, 1], "region_order": "separator_cross"},
            owl=["separator_cross_region"],
        ),
        "reflect_foreground_across_2x2_marker": _spec(
            "reflect_foreground",
            numeric={"side": 2},
            owl=["marker_shape", "reflection_axis_marker"],
            primitive=[{"shape": "square", "side": 2, "solid": True}],
        ),
        "opposite_corner_blocks_from_2x2": _spec(
            "opposite_corner_projection",
            numeric={"side": 2},
            owl=["opposite_corner_projection_source"],
            primitive=[{"shape": "square", "side": 2, "solid": True}],
        ),
        "topological_2x2_square_packing_recolor": _spec(
            "square_packing_recolor",
            numeric={"side": 2},
            owl=["square_packing_region", "residual_topology"],
            primitive=[{"shape": "square", "side": 2, "solid": True}],
        ),
    },
    "tile_type": {
        "repeat_2x2_diagonal_neighbor_fill": _spec(
            "repeat_diagonal_neighbor_fill",
            numeric={"repeat_factor": 2},
            owl=["diagonal_neighbor_relation"],
        ),
    },
}


def canonical_slot(slot):
    return SLOT_ALIASES.get(slot, slot)


def classifier_descriptor(slot, legacy_name):
    """Return a DSL-visible factored descriptor for a legacy classifier."""
    slot = canonical_slot(slot)
    spec = deepcopy(CLASSIFIER_MIGRATIONS[slot][legacy_name])
    spec.update({
        "dsl_classifier": True,
        "slot": slot,
        "legacy": legacy_name,
    })
    return spec


def _descriptor_from_spec(slot, spec):
    spec = deepcopy(spec)
    spec.update({
        "dsl_classifier": True,
        "slot": slot,
    })
    return spec


def _action_migrations(slot):
    return {
        spec["action"]: spec
        for spec in CLASSIFIER_MIGRATIONS.get(slot, {}).values()
    }


def migrated_classifier_values(slot, values):
    """Replace audited legacy classifier strings with factored descriptors."""
    slot = canonical_slot(slot)
    migrations = CLASSIFIER_MIGRATIONS.get(slot, {})
    action_migrations = _action_migrations(slot)
    return [
        classifier_descriptor(slot, value)
        if value in migrations
        else _descriptor_from_spec(slot, action_migrations[value])
        if value in action_migrations
        else value
        for value in values
    ]


def _classifier_params_from_spec(slot, legacy_name, spec, existing=None):
    params = deepcopy(existing) if isinstance(existing, dict) else {}
    params.setdefault("slot", slot)
    primitive_filters = deepcopy(spec.get("primitive_filters", []))
    if primitive_filters:
        params.setdefault("primitive_filters", primitive_filters)
    elif "primitive_filters" in params and not params["primitive_filters"]:
        params.pop("primitive_filters")
    if "owl_classes" not in params and LEGACY_OWL_CLASSES_KEY in params:
        params["owl_classes"] = deepcopy(params[LEGACY_OWL_CLASSES_KEY])
    params.pop(LEGACY_OWL_CLASSES_KEY, None)
    params.setdefault(
        "owl_classes",
        deepcopy(spec.get("owl_classes", spec.get(LEGACY_OWL_CLASSES_KEY, []))),
    )
    numeric = deepcopy(spec.get("numeric_parameters", {}))
    params.setdefault("numeric_parameters", numeric)
    for key, value in numeric.items():
        params.setdefault(key, value)
    return params


def normalize_classifier(slot, value, classifier_params=None):
    """Return (canonical_action, classifier_params)."""
    slot = canonical_slot(slot)
    if isinstance(value, dict) and value.get("dsl_classifier"):
        legacy = value.get("legacy")
        action = value.get("action")
        params = _classifier_params_from_spec(slot, legacy, value, classifier_params)
        return action, params

    migrations = CLASSIFIER_MIGRATIONS.get(slot, {})
    if isinstance(value, str) and value in migrations:
        spec = migrations[value]
        return spec["action"], _classifier_params_from_spec(slot, value, spec, classifier_params)
    action_migrations = _action_migrations(slot)
    if isinstance(value, str) and value in action_migrations:
        spec = action_migrations[value]
        return value, _classifier_params_from_spec(slot, value, spec, classifier_params)

    return value, classifier_params


def expand_classifier_params(param_vals):
    """Normalize classifier slot values inside an operation parameter dict."""
    if not isinstance(param_vals, dict):
        return param_vals

    expanded = deepcopy(param_vals)
    for slot in ("beam_type", "summary_type", "recolor_type", "neighborhood_type", "upscale_type", "object", "tile_type"):
        if slot not in expanded:
            continue
        action, classifier_params = normalize_classifier(
            slot,
            expanded[slot],
            expanded.get("classifier_params"),
        )
        expanded[slot] = action
        if classifier_params is not None:
            expanded["classifier_params"] = classifier_params
    return expanded


def classifier_action(slot, value, classifier_params=None):
    """Convenience wrapper for extended transformations."""
    action, params = normalize_classifier(slot, value, classifier_params)
    return action, params


def audited_legacy_names():
    for migrations in CLASSIFIER_MIGRATIONS.values():
        yield from migrations

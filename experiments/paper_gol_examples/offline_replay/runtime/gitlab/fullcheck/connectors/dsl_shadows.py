"""Connector-calculus shadows for every executable ARCGraph DSL element."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import inspect

from ARCGraph import ARCGraph
from connectors.schema import (
    ActionSignature,
    ConnectorChain,
    ConnectorDecomposition,
    ConnectorSchema,
    GuardAtom,
    OperationalContract,
    PropertyRef,
    RuleGraph,
    RuleGraphEdge,
    RuleGraphNode,
    WakeLowering,
)
from ontology.dsl_connector_audit import executable_inventory
from ontology.dsl_schema import BINDER_ACTIONS, FILTER_ACTIONS, PARAMETERS, TRANSFORMATION_ACTIONS


ACTION_SCHEMAS = {
    "transformation": TRANSFORMATION_ACTIONS,
    "filter": FILTER_ACTIONS,
    "binder": BINDER_ACTIONS,
}


EFFECTS = {
    "add_border": "add_boundary_pixels",
    "arbitrary_duplicate": "duplicate_grid_with_layout",
    "basic_grid": "construct_basic_grid",
    "beam": "draw_bounded_beam",
    "connect": "draw_component_connector",
    "connect_aligned_nodes": "draw_aligned_component_connector",
    "count_grid": "construct_count_summary_grid",
    "crop": "extract_bounded_region",
    "downscale_grid": "collapse_uniform_logical_cells",
    "duplicate": "duplicate_selected_structure",
    "extend_node": "extend_component_along_direction",
    "extract": "extract_selected_structure",
    "fill": "fill_selected_cells",
    "fill_rectangle": "fill_rectangle_interior",
    "flip": "reflect_component_about_axis",
    "hollow_rectangle": "remove_rectangle_interior",
    "insert": "insert_bound_object",
    "magnet": "translate_components_by_attraction",
    "mirror": "reflect_component_about_line",
    "mirror_grid": "reflect_grid_about_axis",
    "move_node": "translate_component_fixed_distance",
    "move_node_max": "translate_component_to_collision_boundary",
    "neighborhood_grid": "construct_neighborhood_summary_grid",
    "overlay": "compose_partition_layers",
    "placement_grid": "place_components_on_grid",
    "pyramid_grid": "construct_pyramid_pattern",
    "recolor": "apply_palette_rewrite",
    "remove_node": "remove_selected_component",
    "rotate_duplicate": "rotate_and_duplicate_grid",
    "rotate_grid": "rotate_grid_quarter_turns",
    "rotate_node": "rotate_component_quarter_turns",
    "shift": "shift_grid_by_color_relation",
    "squeeze": "compact_components_along_axis",
    "summary_grid": "construct_component_summary_grid",
    "symmetry_grid": "complete_or_construct_symmetry",
    "tile_grid": "repeat_logical_tile",
    "truncate": "truncate_grid_by_bound",
    "update_color": "replace_component_color",
    "upscale_grid": "expand_logical_cells_uniformly",
}


COMPOSITION_LAWS = {
    "downscale_grid": (
        "inverse_of_uniform_upscale_when_blocks_are_uniform",
        "preserves_logical_occupancy",
    ),
    "upscale_grid": (
        "inverse_of_uniform_downscale_on_logical_grid",
        "preserves_palette_labels_per_logical_cell",
        "integer_factor_composition_multiplies_factors",
    ),
    "rotate_grid": (
        "member_of_D4",
        "four_quarter_turns_equal_identity",
        "preserves_palette_and_adjacency",
    ),
    "rotate_node": (
        "member_of_D4",
        "four_quarter_turns_equal_identity",
        "preserves_palette_and_adjacency",
    ),
    "mirror": (
        "member_of_D4",
        "self_inverse",
        "preserves_palette_and_adjacency",
    ),
    "mirror_grid": (
        "member_of_D4",
        "self_inverse",
        "preserves_palette_and_adjacency",
    ),
    "flip": (
        "member_of_D4",
        "self_inverse",
        "preserves_palette_and_adjacency",
    ),
}


def _implementation_digest(name: str) -> str:
    source = inspect.getsource(getattr(ARCGraph, name))
    return sha256(source.encode("utf-8")).hexdigest()[:16]


def _graph(graph_id: str, kind: str, phase: str) -> RuleGraph:
    if kind == "transformation":
        nodes = (
            RuleGraphNode(
                "carrier",
                "arga:ARCGraph",
                properties=(PropertyRef("arga:hasExtent", "arga:ARCGraph", "arga:Region", "exactly_one"),),
                attributes={"phase": phase, "preserved": phase == "interface"},
            ),
            RuleGraphNode(
                "selection",
                "arga:OperationBinding",
                attributes={"role": "selected_target", "phase": phase},
            ),
        )
        edges = (RuleGraphEdge("carrier", "arga:hasOperationBinding", "selection"),)
    elif kind == "filter":
        nodes = (
            RuleGraphNode("carrier", "arga:ARCGraph", attributes={"phase": phase, "read_only": True}),
            RuleGraphNode("candidate", "arga:OperationBinding", attributes={"phase": phase}),
        )
        edges = (RuleGraphEdge("carrier", "arga:hasCandidateBinding", "candidate"),)
    else:
        nodes = (
            RuleGraphNode("binding", "arga:OperationBinding", attributes={"phase": phase}),
            RuleGraphNode("candidate", "arga:OperationBinding", attributes={"phase": phase}),
        )
        edges = (RuleGraphEdge("binding", "arga:hasCandidateBinding", "candidate"),)
    return RuleGraph(graph_id, nodes=nodes, edges=edges)


def _shadow(entry) -> ConnectorChain:
    schema = ACTION_SCHEMAS[entry.kind][entry.name]
    parameter_bindings = {
        name: PARAMETERS[name].ontology_iri for name in entry.parameters
    }
    typed_binders = tuple(f"bind_typed_parameter:{name}" for name in entry.parameters) or ("bind_no_external_parameters",)
    if entry.kind == "transformation":
        selectors = ("select_operation_target_or_whole_graph",)
        binders = typed_binders
        effects = (EFFECTS[entry.name],)
        postconditions = ("produces_typed_ARCGraph", "input_carrier_extent_accounted_for")
        invariants = ("parameter_domains_preserved",)
    elif entry.kind == "filter":
        selectors = (entry.name,)
        binders = typed_binders
        effects = ("select_operation_binding_without_mutation",)
        postconditions = ("returns_boolean_selection_for_candidate",)
        invariants = ("input_graph_unchanged",)
    else:
        selectors = ("use_current_operation_binding",)
        binders = (entry.name,) + typed_binders
        effects = ("derive_related_operation_binding",)
        postconditions = ("returns_typed_related_binding_or_none",)
        invariants = ("input_graph_unchanged",)

    root = ConnectorSchema(
        schema_id=f"connector:dsl:{entry.name}",
        lifecycle_stage="realized",
        strata="realized",
        left=_graph(f"connector:dsl:{entry.name}:L", entry.kind, "left"),
        interface=_graph(f"connector:dsl:{entry.name}:K", entry.kind, "interface"),
        right=_graph(f"connector:dsl:{entry.name}:R", entry.kind, "right"),
        guards=(
            GuardAtom("guard:ontology_action_resolved", {"action": schema.ontology_iri}),
            GuardAtom("guard:typed_parameters_complete", parameters=parameter_bindings),
            GuardAtom("guard:bounded_runtime", parameters={"max_grid_cells": 900}),
        ),
        action=ActionSignature(
            schema.ontology_iri,
            arguments={"carrier": "arga:ARCGraph"},
            parameters=parameter_bindings,
        ),
        wake_lowering=WakeLowering(
            f"lowering:ARCGraph.{entry.name}",
            "ARCGraph",
            entry.name,
            budget={"max_grid_cells": 900, "deterministic": True},
        ),
        decomposition=ConnectorDecomposition(
            selectors=selectors,
            binders=binders,
            effects=effects,
            components=selectors + binders + effects,
            ordering=("selector_before_binder", "binder_before_effect"),
        ),
        operational_contract=OperationalContract(
            preconditions=("ontology_action_resolved", "typed_parameters_complete", "grid_within_bounds"),
            invariants=invariants,
            postconditions=postconditions,
            failure_conditions=("unresolved_parameter", "ambiguous_binding", "resource_bound_exceeded"),
            ambiguity_policy="reject",
            boundedness={"max_grid_cells": 900, "finite_parameter_domains": True},
            composition_laws=COMPOSITION_LAWS.get(entry.name, ()),
        ),
        implementation_digest=_implementation_digest(entry.name),
        support={
            "implementation_kind": entry.kind,
            "agreement_test": "tests.test_dsl_connector_shadows.DslConnectorShadowTests",
            "agreement_status": "signature_and_lowering_verified",
            "behavioral_agreement_status": "pending_representative_cases",
            "semantic_decomposition_status": "first_pass_connector_chain",
            "ontology_schema_version": "dsl_schema.v1",
        },
    )
    selector = replace(
        root,
        schema_id=f"connector:dsl:{entry.name}:selector",
        action=None,
        wake_lowering=None,
        decomposition=ConnectorDecomposition(
            selectors=selectors,
            components=selectors,
        ),
        operational_contract=replace(
            root.operational_contract,
            postconditions=("selected_typed_operation_target",),
            composition_laws=(),
        ),
    )
    binder = replace(
        root,
        schema_id=f"connector:dsl:{entry.name}:binder",
        action=None,
        wake_lowering=None,
        decomposition=ConnectorDecomposition(
            binders=binders,
            components=binders,
        ),
        operational_contract=replace(
            root.operational_contract,
            postconditions=("all_external_parameters_bound_to_typed_values",),
            composition_laws=(),
        ),
    )
    effect = replace(
        root,
        schema_id=f"connector:dsl:{entry.name}:effect",
        decomposition=ConnectorDecomposition(
            effects=effects,
            components=effects,
        ),
    )
    connectors = (selector, binder, effect)
    return ConnectorChain(
        chain_id=f"connector_chain:dsl:{entry.name}",
        connectors=connectors,
        dataflow=(
            RuleGraphEdge(selector.schema_id, "arga:nextConnector", binder.schema_id),
            RuleGraphEdge(binder.schema_id, "arga:nextConnector", effect.schema_id),
        ),
        join_policy="sequential",
        lifecycle_stage="realized",
    )


DSL_CONNECTOR_SHADOWS = {
    entry.name: _shadow(entry) for entry in executable_inventory()
}

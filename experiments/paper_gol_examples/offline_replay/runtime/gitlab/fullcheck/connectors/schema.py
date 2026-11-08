"""Typed connector schema data structures.

A connector schema is the persistent Python shape for:

    guard ; ConnectorSchema(L <- K -> R, properties) ; action

`L`, `K`, and `R` are lightweight rule graphs, not concrete ARCGraph instances.
Runtime matching maps schema nodes/properties into a concrete ARCGraph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class PropertyRef:
    """Reference to an ontology property with declared domain/range."""

    property_id: str
    domain_class_id: str
    range_class_id: str
    cardinality: str = "zero_or_more"


@dataclass(frozen=True)
class RuleGraphNode:
    """Node in a lightweight L/K/R schema graph."""

    node_id: str
    class_id: str
    properties: Sequence[PropertyRef] = field(default_factory=tuple)
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleGraphEdge:
    """Typed relation inside a lightweight schema graph."""

    source_id: str
    relation_id: str
    target_id: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleGraph:
    """Lightweight typed graph used for L, K, or R."""

    graph_id: str
    nodes: Sequence[RuleGraphNode] = field(default_factory=tuple)
    edges: Sequence[RuleGraphEdge] = field(default_factory=tuple)


@dataclass(frozen=True)
class GuardAtom:
    """Guard/test atom declared by a connector schema."""

    atom_id: str
    arguments: Mapping[str, str] = field(default_factory=dict)
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionSignature:
    """Wake action interface used by a connector."""

    action_id: str
    arguments: Mapping[str, str] = field(default_factory=dict)
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WakeLowering:
    """Executable projection for wake, if realized."""

    lowering_id: str
    module: str
    callable_name: str
    budget: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorDecomposition:
    """Named selector/binder/effect pieces exposed to composition inference."""

    selectors: Sequence[str] = field(default_factory=tuple)
    binders: Sequence[str] = field(default_factory=tuple)
    effects: Sequence[str] = field(default_factory=tuple)
    components: Sequence[str] = field(default_factory=tuple)
    ordering: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class OperationalContract:
    """Declarative pre/post/failure contract for a connector lowering."""

    preconditions: Sequence[str] = field(default_factory=tuple)
    invariants: Sequence[str] = field(default_factory=tuple)
    postconditions: Sequence[str] = field(default_factory=tuple)
    failure_conditions: Sequence[str] = field(default_factory=tuple)
    ambiguity_policy: str = "reject"
    boundedness: Mapping[str, Any] = field(default_factory=dict)
    composition_laws: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class ConnectorSchema:
    """Typed guarded connector schema with optional wake lowering."""

    schema_id: str
    lifecycle_stage: str
    strata: str
    left: RuleGraph
    interface: RuleGraph
    right: RuleGraph
    guards: Sequence[GuardAtom] = field(default_factory=tuple)
    action: ActionSignature | None = None
    wake_lowering: WakeLowering | None = None
    decomposition: ConnectorDecomposition | None = None
    operational_contract: OperationalContract | None = None
    implementation_digest: str = ""
    support: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorChain:
    """Ordered connector expression shadowing one executable DSL construct."""

    chain_id: str
    connectors: Sequence[ConnectorSchema]
    dataflow: Sequence[RuleGraphEdge] = field(default_factory=tuple)
    join_policy: str = "sequential"
    lifecycle_stage: str = "realized"


@dataclass(frozen=True)
class ConnectorRef:
    """Stable reference to a connector that may gain a later decomposition."""

    connector_id: str
    expected_left_classes: Sequence[str] = field(default_factory=tuple)
    expected_right_classes: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class ConnectorRefinement:
    """Versioned replacement of one connector leaf by a connector expression."""

    connector_id: str
    refinement: ConnectorChain
    revision: str
    lifecycle_stage: str = "realized"


@dataclass(frozen=True)
class ConnectorClosure:
    """Fully expanded acyclic connector expression plus provenance."""

    root_chain_id: str
    connectors: Sequence[ConnectorSchema]
    expanded_connector_ids: Sequence[str] = field(default_factory=tuple)
    refinement_revisions: Sequence[str] = field(default_factory=tuple)
    primitive_leaf_ids: Sequence[str] = field(default_factory=tuple)

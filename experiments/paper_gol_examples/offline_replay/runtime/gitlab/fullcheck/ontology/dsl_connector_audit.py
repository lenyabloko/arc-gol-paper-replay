"""Exhaustive executable-DSL to ontology/connector coverage audit.

The executable registries are authoritative.  Ontology declarations and
connector shadows are projections which must cover that inventory without
drift.  This module deliberately reports coverage levels separately so a name
stub cannot be mistaken for a complete operational mapping.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import inspect
from pathlib import Path
from typing import Iterable, Mapping

from ARCGraph import ARCGraph
from ontology.dsl_schema import (
    BINDER_ACTIONS,
    FILTER_ACTIONS,
    PARAMETERS,
    TRANSFORMATION_ACTIONS,
)


@dataclass(frozen=True)
class ExecutableDSLEntry:
    name: str
    kind: str
    module: str
    callable_name: str
    parameters: tuple[str, ...]


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def executable_names() -> dict[str, tuple[str, ...]]:
    """Return the runtime DSL inventory, including implemented inactive DSL.

    ``summary_grid`` is implemented and ontology-visible even though it is not
    currently enabled in a search registry.  Prefix-discovered filters and
    binders prevent inactive implementations from escaping the audit.
    """

    transformations = set(ARCGraph.insertion_transformation_ops)
    transformations.update(ARCGraph.whole_graph_transformation_ops)
    for names in ARCGraph.transformation_ops.values():
        transformations.update(names)
    transformations.add("summary_grid")
    filters = {
        name for name, value in vars(ARCGraph).items()
        if name.startswith("filter_by_") and callable(value)
    }
    binders = {
        name for name, value in vars(ARCGraph).items()
        if name.startswith("param_bind_") and callable(value)
    }
    return {
        "transformation": _unique(transformations),
        "filter": _unique(filters),
        "binder": _unique(binders),
    }


def _external_parameters(callable_value) -> tuple[str, ...]:
    return tuple(
        parameter.name
        for parameter in inspect.signature(callable_value).parameters.values()
        if parameter.name not in {"self", "node"}
    )


def executable_inventory() -> tuple[ExecutableDSLEntry, ...]:
    entries = []
    for kind, names in executable_names().items():
        for name in names:
            value = getattr(ARCGraph, name, None)
            parameters = _external_parameters(value) if callable(value) else ()
            entries.append(ExecutableDSLEntry(
                name=name,
                kind=kind,
                module="ARCGraph",
                callable_name=f"ARCGraph.{name}",
                parameters=parameters,
            ))
    return tuple(sorted(entries, key=lambda entry: (entry.kind, entry.name)))


def _schemas(kind: str):
    return {
        "transformation": TRANSFORMATION_ACTIONS,
        "filter": FILTER_ACTIONS,
        "binder": BINDER_ACTIONS,
    }[kind]


def audit_connector_coverage(
    connector_shadows: Mapping[str, object] | None = None,
) -> dict:
    if connector_shadows is None:
        from connectors.dsl_shadows import DSL_CONNECTOR_SHADOWS
        connector_shadows = DSL_CONNECTOR_SHADOWS
    entries = []
    for executable in executable_inventory():
        schema = _schemas(executable.kind).get(executable.name)
        declared_parameters = set(schema.parameter_keys or ()) if schema else set()
        python_parameters = set(executable.parameters)
        missing_parameter_types = sorted(python_parameters - PARAMETERS.keys())
        missing_owned_parameters = sorted(python_parameters - declared_parameters)
        extra_owned_parameters = sorted(declared_parameters - python_parameters)
        shadow = connector_shadows.get(executable.name)
        declared = schema is not None
        interface_mapped = bool(
            declared
            and not missing_parameter_types
            and not missing_owned_parameters
            and not extra_owned_parameters
        )
        connector_errors = validate_connector_shadow(executable, shadow) if shadow else ["missing connector chain"]
        completion_gaps = connector_completion_gaps(shadow) if shadow else ["missing connector chain"]
        connector_shadowed = bool(interface_mapped and not connector_errors)
        connector_mapped = bool(connector_shadowed and not completion_gaps)
        entries.append({
            **asdict(executable),
            "ontology_declared": declared,
            "ontology_iri": schema.ontology_iri if schema else None,
            "missing_parameter_types": missing_parameter_types,
            "missing_owned_parameters": missing_owned_parameters,
            "extra_owned_parameters": extra_owned_parameters,
            "connector_shadow": shadow is not None,
            "connector_errors": connector_errors,
            "completion_gaps": completion_gaps,
            "coverage_level": (
                "connector_mapped" if connector_mapped else
                "connector_shadowed" if connector_shadowed else
                "interface_mapped" if interface_mapped else
                "declared" if declared else "unmapped"
            ),
        })

    executable_by_kind = {
        kind: {entry["name"] for entry in entries if entry["kind"] == kind}
        for kind in ("transformation", "filter", "binder")
    }
    schema_by_kind = {
        "transformation": set(TRANSFORMATION_ACTIONS),
        "filter": set(FILTER_ACTIONS),
        "binder": set(BINDER_ACTIONS),
    }
    return {
        "artifact_kind": "dsl_connector_coverage_audit",
        "schema_version": "dsl_connector_coverage_audit.v1",
        "source": "ARCGraph executable registries and implemented DSL methods",
        "summary": {
            "entry_count": len(entries),
            "declared_count": sum(row["ontology_declared"] for row in entries),
            "interface_mapped_count": sum(row["coverage_level"] in {"interface_mapped", "connector_shadowed", "connector_mapped"} for row in entries),
            "connector_shadowed_count": sum(row["coverage_level"] in {"connector_shadowed", "connector_mapped"} for row in entries),
            "connector_mapped_count": sum(row["coverage_level"] == "connector_mapped" for row in entries),
            "missing_shadow_count": sum(not row["connector_shadow"] for row in entries),
            "fully_mapped": bool(entries) and all(row["coverage_level"] == "connector_mapped" for row in entries),
        },
        "stale_schema_entries": {
            kind: sorted(schema_by_kind[kind] - executable_by_kind[kind])
            for kind in schema_by_kind
        },
        "entries": entries,
    }


def validate_connector_shadow(executable: ExecutableDSLEntry, shadow: object) -> list[str]:
    """Validate a one-or-more connector expression against the strict contract."""
    from connectors.schema import ConnectorChain

    errors: list[str] = []
    if not isinstance(shadow, ConnectorChain):
        return ["shadow must be ConnectorChain"]
    connectors = tuple(shadow.connectors)
    if len(connectors) < 2:
        errors.append("connector chain must expose separate selection/binding and effect stages")
    if shadow.join_policy not in {"sequential", "deterministic_branch_join"}:
        errors.append("connector chain join policy is not deterministic")
    if len(shadow.dataflow) != max(0, len(connectors) - 1):
        errors.append("connector chain dataflow does not connect every adjacent stage")
    for index, connector in enumerate(connectors):
        prefix = f"connector[{index}]"
        if not connector.left.nodes or not connector.interface.nodes or not connector.right.nodes:
            errors.append(f"{prefix} has empty L/K/R graph")
        if connector.decomposition is None or not connector.decomposition.components:
            errors.append(f"{prefix} has no selector/binder/effect decomposition")
        if connector.operational_contract is None:
            errors.append(f"{prefix} has no operational contract")
        else:
            contract = connector.operational_contract
            if not contract.preconditions or not contract.postconditions:
                errors.append(f"{prefix} lacks preconditions or postconditions")
            if not contract.failure_conditions or not contract.boundedness:
                errors.append(f"{prefix} lacks failure or boundedness contract")
        if not connector.implementation_digest:
            errors.append(f"{prefix} has no implementation digest")
        if connector.support.get("agreement_status") != "signature_and_lowering_verified":
            errors.append(f"{prefix} lacks signature/lowering agreement evidence")
        for graph in (connector.left, connector.interface, connector.right):
            for node in graph.nodes:
                if not node.class_id.startswith("arga:"):
                    errors.append(f"{prefix} has unresolved class {node.class_id}")
            for edge in graph.edges:
                if not edge.relation_id.startswith("arga:"):
                    errors.append(f"{prefix} has unresolved relation {edge.relation_id}")
    for left, right in zip(connectors, connectors[1:]):
        right_types = {node.class_id for node in left.right.nodes}
        left_types = {node.class_id for node in right.left.nodes}
        if not right_types & left_types:
            errors.append(f"incompatible connector boundary {left.schema_id} -> {right.schema_id}")
    effect = connectors[-1]
    if effect.action is None or effect.wake_lowering is None:
        errors.append("final effect connector lacks action or wake lowering")
    else:
        if effect.wake_lowering.callable_name != executable.name:
            errors.append("wake lowering callable differs from executable inventory")
        if set(effect.action.parameters) != set(executable.parameters):
            errors.append("effect action parameters differ from executable signature")
    if not connectors[0].decomposition.selectors:
        errors.append("first connector is not a selector")
    if not any(connector.decomposition.binders for connector in connectors[:-1]):
        errors.append("connector chain has no binder stage")
    if not effect.decomposition.effects:
        errors.append("final connector is not an effect")
    return sorted(set(errors))


def connector_completion_gaps(shadow: object) -> list[str]:
    from connectors.schema import ConnectorChain

    if not isinstance(shadow, ConnectorChain) or not shadow.connectors:
        return ["missing connector chain"]
    support = shadow.connectors[-1].support
    gaps = []
    if support.get("behavioral_agreement_status") != "verified_representative_cases":
        gaps.append("representative positive/negative/boundary/ambiguous behavior cases not verified")
    if support.get("semantic_decomposition_status") != "validated_compositional_closure":
        gaps.append("connector decomposition has not reached validated compositional closure")
    return gaps


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    payload = audit_connector_coverage()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if payload["summary"]["fully_mapped"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

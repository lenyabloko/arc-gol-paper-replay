"""Digest-bound runtime projection of Brain--Blood Barrier contracts.

The JSON document beside this module is declarative ontology authority.  This
module compiles it once into immutable Python values.  Solver modules may keep
an implementation whitelist, but they must obtain semantic values through this
registry rather than redeclaring them.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF


CONTRACT_PATH = Path(__file__).with_name("runtime_semantics.json")
ONTOLOGY_PATH = Path(__file__).with_name("runtime_semantics.ttl")
ARGA = Namespace("https://example.org/arga#")


class RuntimeRegistryError(RuntimeError):
    """Raised when ontology authority cannot be compiled without ambiguity."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def payload_digest(document: Mapping[str, Any]) -> str:
    payload = dict(document)
    payload.pop("payload_digest", None)
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def canonical_ontology_bytes(value: bytes) -> bytes:
    """Canonicalize transport-only newline differences before digesting TTL."""
    return value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def thaw(value: Any) -> Any:
    """Return an ordinary mutable copy for instance-local working state."""

    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, frozenset)):
        return [thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class AbstractionContract:
    name: str
    ontology_iri: str
    implementation_id: str
    module: str
    callable_name: str
    implementation_digest: str
    input_type: str
    output_type: str
    background_policy: str
    background_color: int | None
    connectivity: str
    color_partition: str
    preconditions: tuple[str, ...]
    invariants: tuple[str, ...]
    postconditions: tuple[str, ...]
    ambiguity_policy: str
    failure_conditions: tuple[str, ...]
    supported_filters: tuple[str, ...]
    supported_transformations: tuple[str, ...]
    fixtures: Mapping[str, str]
    wake_authorized: bool


@dataclass(frozen=True)
class BackgroundHypothesisContract:
    hypothesis_id: str
    ontology_iri: str
    parent_ontology_iri: str
    selection_policy: str
    literal_color: int | None
    canvas_kind: str
    priority: int
    wake_authorized: bool


@dataclass(frozen=True)
class CanvasSupportHypothesisContract:
    hypothesis_id: str
    ontology_iri: str
    parent_ontology_iri: str
    support_policy: str
    priority: int
    wake_authorized: bool


@dataclass(frozen=True)
class BackgroundRDRRuleContract:
    rule_id: str
    ontology_iri: str
    role: str
    conclusion_hypothesis_id: str
    parent_rule_id: str | None
    exception_predicates: tuple[str, ...]


@dataclass(frozen=True)
class SceneDecompositionRuleContract:
    contract_id: str
    rule_id: str
    ontology_iri: str
    profile_id: str
    profile_ontology_iri: str
    connector_chain_id: str
    rdr_role: str
    parent_rule_id: str | None
    feature_ids: tuple[str, ...]
    ontology_binding_iris: tuple[str, ...]
    binding_slots: tuple[str, ...]
    wake_authorized: bool


@dataclass(frozen=True)
class RootAbstractionContract:
    contract_id: str
    ontology_iri: str
    owner_class: str
    construction_stage: str
    connector_chain_id: str
    input_type: str
    output_type: str
    required_scene_binding_fields: tuple[str, ...]
    wake_authorized: bool


@dataclass(frozen=True)
class RuntimeRegistry:
    schema_version: str
    ontology_iri: str
    ontology_graph_digest: str
    digest: str
    semantic_priors: Mapping[str, Any]
    execution_policy: Mapping[str, Any]
    field_classifications: Mapping[str, str]
    abstractions: Mapping[str, AbstractionContract]
    background_hypotheses: Mapping[str, BackgroundHypothesisContract]
    canvas_support_hypotheses: Mapping[str, CanvasSupportHypothesisContract]
    abstraction_background_hypotheses: Mapping[str, tuple[str, ...]]
    background_rdr_rules: tuple[BackgroundRDRRuleContract, ...]
    scene_decomposition_rules: Mapping[str, SceneDecompositionRuleContract]
    root_abstraction_contracts: Mapping[str, RootAbstractionContract]
    fixtures: Mapping[str, Any]

    def prior(self, identifier: str) -> Any:
        try:
            return self.semantic_priors[identifier]
        except KeyError as exc:
            raise RuntimeRegistryError(
                f"unknown ontology-bound semantic prior: {identifier}"
            ) from exc

    def policy(self, identifier: str) -> Any:
        try:
            return self.execution_policy[identifier]
        except KeyError as exc:
            raise RuntimeRegistryError(
                f"unknown versioned execution policy: {identifier}"
            ) from exc

    def abstraction(self, name: str) -> AbstractionContract:
        try:
            return self.abstractions[name]
        except KeyError as exc:
            raise RuntimeRegistryError(
                f"abstraction {name!r} is not authorized by ontology"
            ) from exc

    def background_hypothesis(self, hypothesis_id: str) -> BackgroundHypothesisContract:
        try:
            return self.background_hypotheses[hypothesis_id]
        except KeyError as exc:
            raise RuntimeRegistryError(
                f"unknown background hypothesis: {hypothesis_id}"
            ) from exc

    def canvas_support_hypothesis(
        self,
        hypothesis_id: str,
    ) -> CanvasSupportHypothesisContract:
        try:
            return self.canvas_support_hypotheses[hypothesis_id]
        except KeyError as exc:
            raise RuntimeRegistryError(
                f"unknown canvas-support hypothesis: {hypothesis_id}"
            ) from exc

    def scene_decomposition_rule(
        self,
        contract_id: str,
    ) -> SceneDecompositionRuleContract:
        try:
            return self.scene_decomposition_rules[contract_id]
        except KeyError as exc:
            raise RuntimeRegistryError(
                f"unknown scene-decomposition rule contract: {contract_id}"
            ) from exc

    def root_abstraction_contract(self, contract_id: str) -> RootAbstractionContract:
        try:
            return self.root_abstraction_contracts[contract_id]
        except KeyError as exc:
            raise RuntimeRegistryError(
                f"unknown root-abstraction contract: {contract_id}"
            ) from exc


def _compile(document: Mapping[str, Any]) -> RuntimeRegistry:
    expected_digest = str(document.get("payload_digest") or "")
    actual_digest = payload_digest(document)
    if expected_digest != actual_digest:
        raise RuntimeRegistryError(
            "runtime semantics digest mismatch: "
            f"declared={expected_digest or '<missing>'} actual={actual_digest}"
        )

    try:
        ontology_bytes = ONTOLOGY_PATH.read_bytes()
    except OSError as exc:
        raise RuntimeRegistryError(f"cannot load runtime ontology graph: {ONTOLOGY_PATH}") from exc
    ontology_graph_digest = hashlib.sha256(
        canonical_ontology_bytes(ontology_bytes)
    ).hexdigest()
    if document.get("ontology_graph_digest") != ontology_graph_digest:
        raise RuntimeRegistryError(
            "runtime ontology graph digest mismatch: "
            f"declared={document.get('ontology_graph_digest') or '<missing>'} "
            f"actual={ontology_graph_digest}"
        )
    graph = Graph()
    try:
        graph.parse(data=ontology_bytes.decode("utf-8"), format="turtle")
    except Exception as exc:
        raise RuntimeRegistryError("runtime ontology graph is not valid Turtle") from exc
    ontology_iri = URIRef(str(document.get("ontology_iri") or ""))
    if (ontology_iri, RDF.type, OWL.Ontology) not in graph:
        raise RuntimeRegistryError("runtime ontology IRI is not declared as owl:Ontology")

    def ontology_resource(compact_iri: str, expected_type: URIRef) -> URIRef:
        if not compact_iri.startswith("arga:"):
            raise RuntimeRegistryError(f"unsupported ontology IRI form: {compact_iri}")
        resource = ARGA[compact_iri.split(":", 1)[1]]
        if (resource, RDF.type, expected_type) not in graph:
            raise RuntimeRegistryError(
                f"ontology resource {compact_iri} is not declared as {expected_type}"
            )
        return resource

    prior_rows = document.get("semantic_priors")
    if not isinstance(prior_rows, dict):
        raise RuntimeRegistryError("semantic_priors must be an object")
    semantic_priors: dict[str, Any] = {}
    seen_iris: set[str] = set()
    for identifier, row in prior_rows.items():
        if not isinstance(row, dict) or row.get("classification") != "ontology_bound_semantic_prior":
            raise RuntimeRegistryError(f"invalid semantic prior record: {identifier}")
        iri = str(row.get("ontology_iri") or "")
        if not iri or iri in seen_iris:
            raise RuntimeRegistryError(f"missing or duplicate semantic prior IRI: {identifier}")
        seen_iris.add(iri)
        ontology_resource(iri, ARGA.SemanticPrior)
        if "value" not in row:
            raise RuntimeRegistryError(f"semantic prior has no value: {identifier}")
        semantic_priors[identifier] = _freeze(row["value"])

    policy_rows = document.get("execution_policy")
    if not isinstance(policy_rows, dict):
        raise RuntimeRegistryError("execution_policy must be an object")
    execution_policy = {
        identifier: _freeze(row["value"])
        for identifier, row in policy_rows.items()
        if isinstance(row, dict)
        and row.get("classification") == "versioned_execution_policy"
        and "value" in row
        and row.get("ontology_iri")
    }
    if len(execution_policy) != len(policy_rows):
        raise RuntimeRegistryError("invalid versioned execution-policy record")
    for row in policy_rows.values():
        ontology_resource(str(row["ontology_iri"]), ARGA.VersionedExecutionPolicy)

    background_rows = document.get("background_hypotheses")
    if not isinstance(background_rows, dict) or not background_rows:
        raise RuntimeRegistryError("background_hypotheses must be a nonempty object")
    background_hypotheses: dict[str, BackgroundHypothesisContract] = {}
    for hypothesis_id, row in background_rows.items():
        if not isinstance(row, dict):
            raise RuntimeRegistryError(f"invalid background hypothesis: {hypothesis_id}")
        ontology_iri = str(row.get("ontology_iri") or "")
        ontology_resource(ontology_iri, ARGA.BackgroundHypothesis)
        background_hypotheses[hypothesis_id] = BackgroundHypothesisContract(
            hypothesis_id=hypothesis_id,
            ontology_iri=ontology_iri,
            parent_ontology_iri=str(row.get("parent_ontology_iri") or ""),
            selection_policy=str(row["selection_policy"]),
            literal_color=row.get("literal_color"),
            canvas_kind=str(row["canvas_kind"]),
            priority=int(row["priority"]),
            wake_authorized=bool(row.get("wake_authorized")),
        )

    canvas_support_rows = document.get("canvas_support_hypotheses")
    if not isinstance(canvas_support_rows, dict) or not canvas_support_rows:
        raise RuntimeRegistryError("canvas_support_hypotheses must be a nonempty object")
    canvas_support_hypotheses: dict[str, CanvasSupportHypothesisContract] = {}
    for hypothesis_id, row in canvas_support_rows.items():
        if not isinstance(row, dict):
            raise RuntimeRegistryError(
                f"invalid canvas-support hypothesis: {hypothesis_id}"
            )
        ontology_iri = str(row.get("ontology_iri") or "")
        ontology_resource(ontology_iri, ARGA.CanvasSupportHypothesis)
        canvas_support_hypotheses[hypothesis_id] = CanvasSupportHypothesisContract(
            hypothesis_id=hypothesis_id,
            ontology_iri=ontology_iri,
            parent_ontology_iri=str(row.get("parent_ontology_iri") or ""),
            support_policy=str(row["support_policy"]),
            priority=int(row["priority"]),
            wake_authorized=bool(row.get("wake_authorized")),
        )

    abstraction_background_rows = document.get("abstraction_background_hypotheses")
    if not isinstance(abstraction_background_rows, dict):
        raise RuntimeRegistryError("abstraction_background_hypotheses must be an object")

    rdr_rows = document.get("background_rdr_rules")
    if not isinstance(rdr_rows, list) or not rdr_rows:
        raise RuntimeRegistryError("background_rdr_rules must be a nonempty array")
    background_rdr_rules: list[BackgroundRDRRuleContract] = []
    seen_rdr_ids: set[str] = set()
    for row in rdr_rows:
        if not isinstance(row, dict):
            raise RuntimeRegistryError("invalid background RDR rule")
        rule_id = str(row.get("rule_id") or "")
        if not rule_id or rule_id in seen_rdr_ids:
            raise RuntimeRegistryError(f"missing or duplicate background RDR rule id: {rule_id}")
        seen_rdr_ids.add(rule_id)
        ontology_iri = str(row.get("ontology_iri") or "")
        ontology_resource(ontology_iri, ARGA.DefeasibleRDRRule)
        conclusion = str(row.get("conclusion_hypothesis_id") or "")
        if conclusion not in background_hypotheses:
            raise RuntimeRegistryError(f"background RDR rule has unknown conclusion: {rule_id}")
        exception_predicates = tuple(row.get("exception_predicates") or ())
        for predicate_iri in exception_predicates:
            ontology_resource(str(predicate_iri), ARGA.AbductivePredicate)
        background_rdr_rules.append(BackgroundRDRRuleContract(
            rule_id=rule_id,
            ontology_iri=ontology_iri,
            role=str(row["role"]),
            conclusion_hypothesis_id=conclusion,
            parent_rule_id=(str(row["parent_rule_id"]) if row.get("parent_rule_id") else None),
            exception_predicates=exception_predicates,
        ))
    for rule in background_rdr_rules:
        if rule.parent_rule_id is not None and rule.parent_rule_id not in seen_rdr_ids:
            raise RuntimeRegistryError(f"background RDR rule has unknown parent: {rule.rule_id}")

    scene_rule_rows = document.get("scene_decomposition_rules")
    if not isinstance(scene_rule_rows, dict) or not scene_rule_rows:
        raise RuntimeRegistryError("scene_decomposition_rules must be a nonempty object")
    scene_decomposition_rules: dict[str, SceneDecompositionRuleContract] = {}
    for contract_id, row in scene_rule_rows.items():
        if not isinstance(row, dict):
            raise RuntimeRegistryError(
                f"invalid scene-decomposition rule contract: {contract_id}"
            )
        rule_id = str(row.get("rule_id") or "")
        ontology_iri = str(row.get("ontology_iri") or "")
        ontology_resource(ontology_iri, ARGA.DefeasibleRDRRule)
        ontology_binding_iris = tuple(
            str(value) for value in row.get("ontology_binding_iris") or ()
        )
        for binding_iri in ontology_binding_iris:
            if not binding_iri.startswith("arga:"):
                raise RuntimeRegistryError(
                    f"unsupported scene-decomposition binding IRI: {binding_iri}"
                )
            resource = ARGA[binding_iri.split(":", 1)[1]]
            if not any(graph.triples((resource, None, None))):
                raise RuntimeRegistryError(
                    f"undeclared scene-decomposition binding IRI: {binding_iri}"
                )
        if not rule_id or not str(row.get("connector_chain_id") or ""):
            raise RuntimeRegistryError(
                f"incomplete scene-decomposition rule contract: {contract_id}"
            )
        scene_decomposition_rules[contract_id] = SceneDecompositionRuleContract(
            contract_id=contract_id,
            rule_id=rule_id,
            ontology_iri=ontology_iri,
            profile_id=str(row.get("profile_id") or ""),
            profile_ontology_iri=str(row.get("profile_ontology_iri") or ""),
            connector_chain_id=str(row.get("connector_chain_id") or ""),
            rdr_role=str(row.get("rdr_role") or ""),
            parent_rule_id=(
                str(row["parent_rule_id"]) if row.get("parent_rule_id") else None
            ),
            feature_ids=tuple(str(value) for value in row.get("feature_ids") or ()),
            ontology_binding_iris=ontology_binding_iris,
            binding_slots=tuple(str(value) for value in row.get("binding_slots") or ()),
            wake_authorized=bool(row.get("wake_authorized")),
        )

    root_rows = document.get("root_abstraction_contracts")
    if not isinstance(root_rows, dict) or not root_rows:
        raise RuntimeRegistryError("root_abstraction_contracts must be a nonempty object")
    root_abstraction_contracts: dict[str, RootAbstractionContract] = {}
    for contract_id, row in root_rows.items():
        if not isinstance(row, dict):
            raise RuntimeRegistryError(f"invalid root-abstraction contract: {contract_id}")
        ontology_iri = str(row.get("ontology_iri") or "")
        ontology_resource(ontology_iri, ARGA.RootAbstractionContract)
        required_fields = tuple(
            str(value) for value in row.get("required_scene_binding_fields") or ()
        )
        if not required_fields:
            raise RuntimeRegistryError(
                f"root-abstraction contract has no scene binding fields: {contract_id}"
            )
        root_abstraction_contracts[contract_id] = RootAbstractionContract(
            contract_id=contract_id,
            ontology_iri=ontology_iri,
            owner_class=str(row.get("owner_class") or ""),
            construction_stage=str(row.get("construction_stage") or ""),
            connector_chain_id=str(row.get("connector_chain_id") or ""),
            input_type=str(row.get("input_type") or ""),
            output_type=str(row.get("output_type") or ""),
            required_scene_binding_fields=required_fields,
            wake_authorized=bool(row.get("wake_authorized")),
        )

    abstraction_rows = document.get("abstractions")
    if not isinstance(abstraction_rows, dict):
        raise RuntimeRegistryError("abstractions must be an object")
    abstractions: dict[str, AbstractionContract] = {}
    implementation_ids: set[str] = set()
    abstraction_iris: set[str] = set()
    required_fixture_kinds = {"positive", "negative", "boundary", "counterexample"}
    for name, row in abstraction_rows.items():
        if not isinstance(row, dict):
            raise RuntimeRegistryError(f"invalid abstraction contract: {name}")
        implementation_id = str(row.get("implementation_id") or "")
        ontology_iri = str(row.get("ontology_iri") or "")
        if not implementation_id or implementation_id in implementation_ids:
            raise RuntimeRegistryError(f"missing or duplicate implementation id: {name}")
        if not ontology_iri or ontology_iri in abstraction_iris:
            raise RuntimeRegistryError(f"missing or duplicate abstraction IRI: {name}")
        implementation_ids.add(implementation_id)
        abstraction_iris.add(ontology_iri)
        abstraction_resource = ontology_resource(ontology_iri, ARGA.AbstractionContract)
        ttl_implementation_ids = {str(value) for value in graph.objects(abstraction_resource, ARGA.implementationId)}
        ttl_callable_names = {str(value) for value in graph.objects(abstraction_resource, ARGA.callableName)}
        if ttl_implementation_ids != {implementation_id} or ttl_callable_names != {str(row.get("callable_name") or "")}:
            raise RuntimeRegistryError(f"Turtle/JSON implementation binding drift: {name}")
        fixtures = row.get("fixtures") or {}
        if set(fixtures) != required_fixture_kinds:
            raise RuntimeRegistryError(f"incomplete fixture classes for abstraction: {name}")
        abstractions[name] = AbstractionContract(
            name=name,
            ontology_iri=ontology_iri,
            implementation_id=implementation_id,
            module=str(row["module"]),
            callable_name=str(row["callable_name"]),
            implementation_digest=str(row["implementation_digest"]),
            input_type=str(row["input_type"]),
            output_type=str(row["output_type"]),
            background_policy=str(row["background_policy"]),
            background_color=row.get("background_color"),
            connectivity=str(row["connectivity"]),
            color_partition=str(row["color_partition"]),
            preconditions=tuple(row["preconditions"]),
            invariants=tuple(row["invariants"]),
            postconditions=tuple(row["postconditions"]),
            ambiguity_policy=str(row["ambiguity_policy"]),
            failure_conditions=tuple(row["failure_conditions"]),
            supported_filters=tuple(row["supported_filters"]),
            supported_transformations=tuple(row["supported_transformations"]),
            fixtures=MappingProxyType(dict(fixtures)),
            wake_authorized=bool(row.get("wake_authorized")),
        )

    if set(abstraction_background_rows) != set(abstractions):
        raise RuntimeRegistryError("every abstraction must have one background-hypothesis mapping")
    abstraction_background_hypotheses: dict[str, tuple[str, ...]] = {}
    for abstraction_name, hypothesis_ids in abstraction_background_rows.items():
        if not isinstance(hypothesis_ids, list) or not hypothesis_ids:
            raise RuntimeRegistryError(
                f"abstraction background mapping must be a nonempty array: {abstraction_name}"
            )
        unknown = set(hypothesis_ids) - set(background_hypotheses)
        if unknown:
            raise RuntimeRegistryError(
                f"abstraction {abstraction_name} has unknown background hypotheses: {sorted(unknown)}"
            )
        abstraction_background_hypotheses[abstraction_name] = tuple(hypothesis_ids)

    fixtures = document.get("fixtures")
    if not isinstance(fixtures, dict):
        raise RuntimeRegistryError("fixtures must be an object")
    fixture_ids = set(fixtures)
    for contract in abstractions.values():
        missing = set(contract.fixtures.values()) - fixture_ids
        if missing:
            raise RuntimeRegistryError(
                f"abstraction {contract.name} has unknown fixtures: {sorted(missing)}"
            )

    classifications = document.get("field_classifications")
    if not isinstance(classifications, dict):
        raise RuntimeRegistryError("field_classifications must be an object")
    allowed = {
        "ontology_bound_semantic_prior",
        "versioned_execution_policy",
        "derived_runtime_state",
        "implementation_only_mechanism",
    }
    invalid = {name: value for name, value in classifications.items() if value not in allowed}
    if invalid:
        raise RuntimeRegistryError(f"invalid field classifications: {invalid}")

    return RuntimeRegistry(
        schema_version=str(document["schema_version"]),
        ontology_iri=str(document["ontology_iri"]),
        ontology_graph_digest=ontology_graph_digest,
        digest=actual_digest,
        semantic_priors=MappingProxyType(semantic_priors),
        execution_policy=MappingProxyType(execution_policy),
        field_classifications=MappingProxyType(dict(classifications)),
        abstractions=MappingProxyType(abstractions),
        background_hypotheses=MappingProxyType(background_hypotheses),
        canvas_support_hypotheses=MappingProxyType(canvas_support_hypotheses),
        abstraction_background_hypotheses=MappingProxyType(abstraction_background_hypotheses),
        background_rdr_rules=tuple(background_rdr_rules),
        scene_decomposition_rules=MappingProxyType(scene_decomposition_rules),
        root_abstraction_contracts=MappingProxyType(root_abstraction_contracts),
        fixtures=_freeze(fixtures),
    )


@lru_cache(maxsize=1)
def runtime_registry() -> RuntimeRegistry:
    try:
        document = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeRegistryError(f"cannot load runtime ontology: {CONTRACT_PATH}") from exc
    return _compile(document)


def semantic_prior(identifier: str) -> Any:
    return runtime_registry().prior(identifier)


def execution_policy(identifier: str) -> Any:
    return runtime_registry().policy(identifier)


def abstraction_contract(name: str) -> AbstractionContract:
    return runtime_registry().abstraction(name)


def background_hypothesis_contract(hypothesis_id: str) -> BackgroundHypothesisContract:
    return runtime_registry().background_hypothesis(hypothesis_id)


def canvas_support_hypothesis_contract(
    hypothesis_id: str,
) -> CanvasSupportHypothesisContract:
    return runtime_registry().canvas_support_hypothesis(hypothesis_id)


def background_rdr_rule_contracts() -> tuple[BackgroundRDRRuleContract, ...]:
    return runtime_registry().background_rdr_rules


def scene_decomposition_rule_contract(
    contract_id: str,
) -> SceneDecompositionRuleContract:
    return runtime_registry().scene_decomposition_rule(contract_id)


def root_abstraction_contract(contract_id: str) -> RootAbstractionContract:
    return runtime_registry().root_abstraction_contract(contract_id)


def expand_runtime_iri(compact_iri: str) -> str:
    if not compact_iri.startswith("arga:"):
        raise RuntimeRegistryError(f"unsupported runtime ontology IRI: {compact_iri}")
    return str(ARGA[compact_iri.split(":", 1)[1]])


def abstraction_callable_names() -> Mapping[str, str]:
    return MappingProxyType({
        name: contract.callable_name
        for name, contract in runtime_registry().abstractions.items()
        if contract.wake_authorized
    })


def registry_manifest() -> Mapping[str, str]:
    registry = runtime_registry()
    return MappingProxyType({
        "schema_version": registry.schema_version,
        "ontology_iri": registry.ontology_iri,
        "ontology_graph_digest": registry.ontology_graph_digest,
        "runtime_registry_digest": registry.digest,
    })

"""Ontology-authorized background/canvas selection semantics.

This module is the executable boundary for choosing a palette color (or the
absence of one) from a ``BackgroundHypothesis``. Abstraction, RDR revision,
and reconstruction all call the same selectors so a revised hypothesis cannot
silently fall back to an unrelated legacy definition of background.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Iterable

from ontology.runtime_registry import (
    BackgroundHypothesisContract,
    background_hypothesis_contract,
    runtime_registry,
)


Grid = list[list[int]]
BackgroundSelector = Callable[[Grid], int | None]


class BackgroundSelectorRegistry:
    """Extensible executable policies for ontology background hypotheses.

    The ontology contract names a selection policy; this registry supplies its
    implementation.  Keeping that lookup out of a closed conditional means a
    new background sibling can be added without editing every consumer.
    """

    def __init__(self) -> None:
        self._selectors: dict[str, BackgroundSelector] = {}

    def register(
        self,
        selection_policy: str,
        selector: BackgroundSelector,
        *,
        replace: bool = False,
    ) -> None:
        if not selection_policy:
            raise ValueError("background selection policy must be nonempty")
        if selection_policy in self._selectors and not replace:
            raise ValueError(f"background selection policy already registered: {selection_policy}")
        self._selectors[selection_policy] = selector

    def selector(self, selection_policy: str) -> BackgroundSelector:
        try:
            return self._selectors[selection_policy]
        except KeyError as exc:
            raise ValueError(
                f"unsupported background selection policy: {selection_policy}"
            ) from exc


def _deterministic_mode(values: Iterable[int]) -> int | None:
    counts = Counter(int(value) for value in values)
    if not counts:
        return None
    maximum = max(counts.values())
    return min(value for value, count in counts.items() if count == maximum)


def _frequency_decision(
    values: Iterable[int],
    *,
    contract: BackgroundHypothesisContract,
) -> dict[str, Any]:
    counts = Counter(int(value) for value in values)
    ordered_counts = {
        str(color): int(count)
        for color, count in sorted(counts.items())
    }
    if not counts:
        return {
            "schema_version": "background_hypothesis_decision.v1",
            "background_hypothesis_id": contract.hypothesis_id,
            "background_hypothesis_iri": contract.ontology_iri,
            "selection_policy": contract.selection_policy,
            "status": "no_observation",
            "accepted": False,
            "selected_color": None,
            "candidate_colors": [],
            "deterministic_tie_break_color": None,
            "color_counts": ordered_counts,
            "top_count": 0,
            "count_margin": 0,
            "ambiguity_reason": "grid_has_no_color_observations",
        }
    maximum = max(counts.values())
    candidates = sorted(
        color for color, count in counts.items()
        if count == maximum
    )
    second_count = max(
        (count for color, count in counts.items() if color not in candidates),
        default=0,
    )
    ambiguous = len(candidates) != 1
    return {
        "schema_version": "background_hypothesis_decision.v1",
        "background_hypothesis_id": contract.hypothesis_id,
        "background_hypothesis_iri": contract.ontology_iri,
        "selection_policy": contract.selection_policy,
        "status": "ambiguous" if ambiguous else "selected",
        "accepted": not ambiguous,
        "selected_color": None if ambiguous else int(candidates[0]),
        "candidate_colors": [int(color) for color in candidates],
        "deterministic_tie_break_color": int(candidates[0]),
        "color_counts": ordered_counts,
        "top_count": int(maximum),
        "count_margin": 0 if ambiguous else int(maximum - second_count),
        "ambiguity_reason": (
            "multiple_colors_share_the_maximum_support"
            if ambiguous else ""
        ),
    }


def modal_color(grid: Grid) -> int | None:
    return _deterministic_mode(value for row in grid or [] for value in row)


def boundary_supported_color(grid: Grid) -> int | None:
    if not grid or not grid[0]:
        return None
    height = len(grid)
    width = len(grid[0])
    return _deterministic_mode(
        grid[row][column]
        for row in range(height)
        for column in range(width)
        if row in {0, height - 1} or column in {0, width - 1}
    )


def corner_supported_color(grid: Grid) -> int | None:
    if not grid or not grid[0]:
        return None
    height = len(grid)
    width = len(grid[0])
    corners = {
        (0, 0),
        (0, width - 1),
        (height - 1, 0),
        (height - 1, width - 1),
    }
    return _deterministic_mode(grid[row][column] for row, column in corners)


def background_hypothesis_decision(
    contract_or_id: BackgroundHypothesisContract | str,
    grid: Grid,
) -> dict[str, Any]:
    """Return an explicit, provenance-ready decision for one hypothesis.

    Legacy selectors remain deterministic so existing abstraction contracts can
    replay exactly. Semantic detectors use this decision surface instead: a
    frequency tie is an unresolved hypothesis and must not silently acquire
    background meaning from a numeric or traversal-order tie break.
    """

    contract = (
        contract_or_id
        if isinstance(contract_or_id, BackgroundHypothesisContract)
        else background_hypothesis_contract(contract_or_id)
    )
    if contract.selection_policy == "most_frequent_color_per_grid":
        return _frequency_decision(
            (value for row in grid or [] for value in row),
            contract=contract,
        )
    if contract.selection_policy == "boundary_supported_color":
        values = []
        if grid and grid[0]:
            height = len(grid)
            width = len(grid[0])
            values = [
                grid[row][column]
                for row in range(height)
                for column in range(width)
                if row in {0, height - 1}
                or column in {0, width - 1}
            ]
        return _frequency_decision(values, contract=contract)
    if contract.selection_policy == "corner_supported_color":
        values = []
        if grid and grid[0]:
            height = len(grid)
            width = len(grid[0])
            corners = {
                (0, 0),
                (0, width - 1),
                (height - 1, 0),
                (height - 1, width - 1),
            }
            values = [grid[row][column] for row, column in sorted(corners)]
        return _frequency_decision(values, contract=contract)
    selected = selector_for_background_hypothesis(contract)(grid)
    return {
        "schema_version": "background_hypothesis_decision.v1",
        "background_hypothesis_id": contract.hypothesis_id,
        "background_hypothesis_iri": contract.ontology_iri,
        "selection_policy": contract.selection_policy,
        "status": "selected",
        "accepted": True,
        "selected_color": (
            int(selected) if selected is not None else None
        ),
        "candidate_colors": (
            [int(selected)] if selected is not None else []
        ),
        "deterministic_tie_break_color": (
            int(selected) if selected is not None else None
        ),
        "color_counts": {},
        "top_count": 0,
        "count_margin": 0,
        "ambiguity_reason": "",
    }


def accepted_background_color(
    contract_or_id: BackgroundHypothesisContract | str,
    grid: Grid,
) -> int | None:
    """Return a color only when the hypothesis has an unambiguous decision."""

    decision = background_hypothesis_decision(contract_or_id, grid)
    selected = decision.get("selected_color")
    return int(selected) if decision.get("accepted") and selected is not None else None


def resolve_background_hypothesis(
    grid: Grid,
    *,
    hypothesis_id: str = "modal_color",
) -> dict[str, Any]:
    """Resolve one explicitly selected ontology background hypothesis.

    The generic detector has no downstream typed-derivation failure from which
    to induce an RDR exception, so it evaluates only the ontology default.
    Callers that already possess a persisted RDR/abstraction selection may name
    that sibling explicitly.  An ambiguous default is never converted into a
    semantic fact by tie breaking or by trying every sibling in an opaque loop.
    """

    palette = {
        int(value)
        for row in grid or []
        for value in row
    }
    contract = background_hypothesis_contract(hypothesis_id)
    if not contract.wake_authorized:
        raise ValueError(
            f"background hypothesis is not Wake-authorized: {hypothesis_id}"
        )
    decision = background_hypothesis_decision(contract, grid)
    if (
        contract.selection_policy == "literal_color"
        and decision.get("selected_color") not in palette
    ):
        decision = {
            **decision,
            "status": "not_applicable",
            "accepted": False,
            "ambiguity_reason": "literal_color_absent_from_grid",
        }
    attempts = [decision]
    if decision.get("accepted"):
        return {
            **decision,
            "schema_version": "background_hypothesis_resolution.v1",
            "resolution_status": "selected",
            "attempted_hypotheses": attempts,
            "unresolved_hypothesis_ids": [],
        }
    return {
        **decision,
        "schema_version": "background_hypothesis_resolution.v1",
        "status": "ambiguous",
        "resolution_status": "unresolved",
        "accepted": False,
        "selected_color": None,
        "attempted_hypotheses": attempts,
        "unresolved_hypothesis_ids": [
            str(row.get("background_hypothesis_id") or "")
            for row in attempts
            if not row.get("accepted")
        ],
    }


def cross_sample_background_hypothesis_decision(
    pair_decisions: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve one conservative background conclusion across training pairs.

    Per-grid decisions remain evidence, not task conclusions. A task-level
    background is selected when every public training input and output has an
    accepted decision for the same hypothesis and each pair preserves the
    selected color. A detector-grounded background-overlay relation may also
    bind the accepted input background as the source canvas even when the
    overlay makes another color modal in the output. Any other missing,
    ambiguous, or pair-inconsistent observation fails closed to
    ``background = none``.

    The selected color may vary between training pairs. That is a case binding
    of one stable hypothesis, not a change in detector policy.
    """

    pairs = [
        dict(pair)
        for pair in pair_decisions
        if isinstance(pair, dict)
    ]
    observations: list[dict[str, Any]] = []
    consistent_pair_count = 0
    case_bindings: list[dict[str, Any]] = []
    hypothesis_ids: set[str] = set()
    hypothesis_iris: set[str] = set()
    selection_policies: set[str] = set()
    source_case_bindings: list[dict[str, Any]] = []
    source_hypothesis_ids: set[str] = set()
    source_hypothesis_iris: set[str] = set()
    source_selection_policies: set[str] = set()
    semantic_defeaters: list[dict[str, Any]] = []

    for case_index, pair in enumerate(pairs):
        input_decision = pair.get("input")
        output_decision = pair.get("output")
        pair_rows = []
        for role, decision in (
            ("input", input_decision),
            ("output", output_decision),
        ):
            if not isinstance(decision, dict):
                decision = {}
            accepted = (
                decision.get("accepted") is True
                and decision.get("selected_color") is not None
            )
            hypothesis_id = str(
                decision.get("background_hypothesis_id") or ""
            )
            hypothesis_iri = str(
                decision.get("background_hypothesis_iri") or ""
            )
            selection_policy = str(decision.get("selection_policy") or "")
            if hypothesis_id:
                hypothesis_ids.add(hypothesis_id)
            if hypothesis_iri:
                hypothesis_iris.add(hypothesis_iri)
            if selection_policy:
                selection_policies.add(selection_policy)
            row = {
                "public_training_case_index": case_index,
                "role": role,
                "accepted": accepted,
                "selected_color": (
                    int(decision["selected_color"]) if accepted else None
                ),
                "background_hypothesis_id": hypothesis_id,
                "background_hypothesis_iri": hypothesis_iri,
                "selection_policy": selection_policy,
                "status": str(decision.get("status") or "not_recorded"),
            }
            observations.append(row)
            pair_rows.append(row)

        pair_consistent = (
            len(pair_rows) == 2
            and all(row["accepted"] for row in pair_rows)
            and pair_rows[0]["background_hypothesis_id"]
            == pair_rows[1]["background_hypothesis_id"]
            and pair_rows[0]["selection_policy"]
            == pair_rows[1]["selection_policy"]
            and pair_rows[0]["selected_color"]
            == pair_rows[1]["selected_color"]
        )
        if pair_consistent:
            consistent_pair_count += 1
            case_bindings.append({
                "public_training_case_index": case_index,
                "selected_color": pair_rows[0]["selected_color"],
            })
        semantic_defeater = pair.get("background_semantic_defeater")
        if isinstance(semantic_defeater, dict):
            relation = str(semantic_defeater.get("relation") or "")
            ontology_iri = str(
                semantic_defeater.get("ontology_iri") or ""
            )
            occluder_color = semantic_defeater.get("occluder_color")
            if (
                relation == "paired_affine_axis_symmetry_occlusion"
                and ontology_iri
                and occluder_color is not None
            ):
                semantic_defeaters.append({
                    "public_training_case_index": case_index,
                    "relation": relation,
                    "ontology_iri": ontology_iri,
                    "occluder_color": int(occluder_color),
                    "evidence_digest": str(
                        semantic_defeater.get("evidence_digest") or ""
                    ),
                })
        if (
            str(pair.get("source_background_relation") or "")
            == "background_overlay_effect"
            and pair_rows[0]["accepted"]
        ):
            source_case_bindings.append({
                "public_training_case_index": case_index,
                "selected_color": pair_rows[0]["selected_color"],
                "binding_role": "input",
            })
            if pair_rows[0]["background_hypothesis_id"]:
                source_hypothesis_ids.add(
                    pair_rows[0]["background_hypothesis_id"]
                )
            if pair_rows[0]["background_hypothesis_iri"]:
                source_hypothesis_iris.add(
                    pair_rows[0]["background_hypothesis_iri"]
                )
            if pair_rows[0]["selection_policy"]:
                source_selection_policies.add(
                    pair_rows[0]["selection_policy"]
                )

    observation_count = len(observations)
    accepted_count = sum(
        1 for observation in observations if observation["accepted"]
    )
    rejected_count = observation_count - accepted_count
    support_fraction = (
        accepted_count / observation_count if observation_count else 0.0
    )
    fully_supported = bool(pairs) and (
        observation_count == len(pairs) * 2
        and accepted_count == observation_count
        and consistent_pair_count == len(pairs)
        and len(hypothesis_ids) == 1
        and len(hypothesis_iris) == 1
        and len(selection_policies) == 1
    )
    source_fully_supported = bool(pairs) and (
        len(source_case_bindings) == len(pairs)
        and len(source_hypothesis_ids) == 1
        and len(source_hypothesis_iris) == 1
        and len(source_selection_policies) == 1
    )
    semantic_defeater_fully_supported = bool(pairs) and (
        len(semantic_defeaters) == len(pairs)
        and len({row["relation"] for row in semantic_defeaters}) == 1
        and len({row["ontology_iri"] for row in semantic_defeaters}) == 1
    )

    common = {
        "schema_version": (
            "cross_sample_background_hypothesis_decision.v1"
        ),
        "scope": "all_public_training_input_output_grids",
        "public_training_only": True,
        "held_out_expected_output_used": False,
        "pair_count": len(pairs),
        "observation_count": observation_count,
        "accepted_observation_count": accepted_count,
        "unresolved_observation_count": rejected_count,
        "consistent_pair_count": consistent_pair_count,
        "source_binding_pair_count": len(source_case_bindings),
        "evidence_support_fraction": support_fraction,
    }
    if semantic_defeater_fully_supported:
        occluder_colors = {
            int(row["occluder_color"]) for row in semantic_defeaters
        }
        occluder_binding_scope = (
            "constant_across_training_pairs"
            if len(occluder_colors) == 1
            else "per_training_pair"
        )
        return {
            **common,
            "status": "defeated",
            "conclusion": "background_none",
            "background": None,
            "selected_background_hypothesis_id": None,
            "selected_background_hypothesis_iri": None,
            "selection_policy": None,
            "binding_scope": "none",
            "case_bindings": [],
            "reason": (
                "paired_affine_axis_occlusion_defeats_modal_background"
            ),
            "defeating_relation": semantic_defeaters[0]["relation"],
            "defeating_ontology_iri": semantic_defeaters[0][
                "ontology_iri"
            ],
            "occluder_binding_scope": occluder_binding_scope,
            "occluder_selected_color": (
                next(iter(occluder_colors))
                if len(occluder_colors) == 1 else None
            ),
            "occluder_case_bindings": semantic_defeaters,
        }
    if not fully_supported and source_fully_supported:
        selected_colors = {
            int(row["selected_color"])
            for row in source_case_bindings
            if row["selected_color"] is not None
        }
        hypothesis_id = next(iter(source_hypothesis_ids))
        hypothesis_iri = next(iter(source_hypothesis_iris))
        selection_policy = next(iter(source_selection_policies))
        binding_scope = (
            "source_constant_across_training_pairs"
            if len(selected_colors) == 1
            else "source_per_training_pair"
        )
        background = {
            "background_hypothesis_id": hypothesis_id,
            "background_hypothesis_iri": hypothesis_iri,
            "selection_policy": selection_policy,
            "binding_scope": binding_scope,
            "binding_basis": "input_background_overlay_effect",
            "selected_color": (
                next(iter(selected_colors))
                if len(selected_colors) == 1 else None
            ),
            "case_bindings": source_case_bindings,
        }
        return {
            **common,
            "status": "selected",
            "conclusion": "background_selected",
            "background": background,
            "selected_background_hypothesis_id": hypothesis_id,
            "selected_background_hypothesis_iri": hypothesis_iri,
            "selection_policy": selection_policy,
            "binding_scope": binding_scope,
            "case_bindings": source_case_bindings,
            "reason": "complete_input_background_overlay_support",
        }
    if not fully_supported:
        reason = (
            "no_public_training_pairs"
            if not pairs
            else "not_sufficient_cross_sample_evidence"
        )
        return {
            **common,
            "status": "insufficient_evidence",
            "conclusion": "background_none",
            "background": None,
            "selected_background_hypothesis_id": None,
            "selected_background_hypothesis_iri": None,
            "selection_policy": None,
            "binding_scope": "none",
            "case_bindings": [],
            "reason": reason,
        }

    selected_colors = {
        int(row["selected_color"])
        for row in case_bindings
        if row["selected_color"] is not None
    }
    hypothesis_id = next(iter(hypothesis_ids))
    hypothesis_iri = next(iter(hypothesis_iris))
    selection_policy = next(iter(selection_policies))
    binding_scope = (
        "constant_across_training_pairs"
        if len(selected_colors) == 1
        else "per_training_pair"
    )
    background = {
        "background_hypothesis_id": hypothesis_id,
        "background_hypothesis_iri": hypothesis_iri,
        "selection_policy": selection_policy,
        "binding_scope": binding_scope,
        "selected_color": (
            next(iter(selected_colors))
            if len(selected_colors) == 1 else None
        ),
        "case_bindings": case_bindings,
    }
    return {
        **common,
        "status": "selected",
        "conclusion": "background_selected",
        "background": background,
        "selected_background_hypothesis_id": hypothesis_id,
        "selected_background_hypothesis_iri": hypothesis_iri,
        "selection_policy": selection_policy,
        "binding_scope": binding_scope,
        "case_bindings": case_bindings,
        "reason": "complete_consistent_cross_sample_support",
    }


BACKGROUND_SELECTOR_REGISTRY = BackgroundSelectorRegistry()
BACKGROUND_SELECTOR_REGISTRY.register("most_frequent_color_per_grid", modal_color)
BACKGROUND_SELECTOR_REGISTRY.register("boundary_supported_color", boundary_supported_color)
BACKGROUND_SELECTOR_REGISTRY.register("corner_supported_color", corner_supported_color)
BACKGROUND_SELECTOR_REGISTRY.register("no_palette_color", lambda _grid: None)


def selector_for_background_hypothesis(
    contract_or_id: BackgroundHypothesisContract | str,
    *,
    registry: BackgroundSelectorRegistry = BACKGROUND_SELECTOR_REGISTRY,
):
    contract = (
        contract_or_id
        if isinstance(contract_or_id, BackgroundHypothesisContract)
        else background_hypothesis_contract(contract_or_id)
    )
    if contract.selection_policy == "literal_color":
        return lambda _grid: contract.literal_color
    return registry.selector(contract.selection_policy)


def select_background_color(
    contract_or_id: BackgroundHypothesisContract | str,
    grid: Grid,
) -> int | None:
    return selector_for_background_hypothesis(contract_or_id)(grid)


def primary_background_hypothesis_id(abstraction: str) -> str:
    try:
        return runtime_registry().abstraction_background_hypotheses[abstraction][0]
    except KeyError as exc:
        raise ValueError(f"abstraction has no background hypothesis: {abstraction}") from exc


def select_abstraction_background_color(abstraction: str, grid: Grid) -> int | None:
    return select_background_color(primary_background_hypothesis_id(abstraction), grid)


def select_abstraction_background_from_image(abstraction: str, image) -> int | None:
    """Resolve an abstraction binding from an Image or a minimal test double.

    Literal/no-color hypotheses do not require pixel access. Modal selection
    may reuse the image's already-derived modal color. Spatial selectors still
    fail closed when the pixel grid is unavailable.
    """

    hypothesis_id = primary_background_hypothesis_id(abstraction)
    contract = background_hypothesis_contract(hypothesis_id)
    grid_reader = getattr(image, "_grid_array", None)
    if callable(grid_reader):
        return select_background_color(contract, grid_reader().tolist())
    if contract.selection_policy in {"literal_color", "no_palette_color"}:
        return select_background_color(contract, [])
    if contract.selection_policy == "most_frequent_color_per_grid":
        return getattr(image, "most_common_color", None)
    raise ValueError(
        f"{contract.selection_policy} requires pixel-grid evidence for {abstraction}"
    )

import networkx as nx
import numpy as np
from itertools import product, combinations
from networkx.algorithms.components import connected_components
from ARCGraph import *
from utils import Mirror
from ontology.runtime_registry import (
    abstraction_callable_names,
    abstraction_contract,
    expand_runtime_iri,
    execution_policy,
    root_abstraction_contract,
    semantic_prior,
)
from ontology.background_canvas import (
    modal_color,
    primary_background_hypothesis_id,
    select_abstraction_background_color,
)


_UNSET_BACKGROUND = object()


class Image:
    max_allowd_pixels = execution_policy("image.max_allowed_pixels")
    max_arc_dimension = execution_policy("image.max_arc_dimension")
    abstractions = semantic_prior("image.abstraction_order")
    abstraction_ops = abstraction_callable_names()
    multicolor_abstractions = frozenset(semantic_prior("image.multicolor_abstractions"))

    def __init__(self, task, grid=None, width=None, height=None, graph=None, name="image"):
        """
        an image represents a 2D grid of pixels.
        the coordinate system follows the convention of 0,0 being the top left pixel of the image
        :param grid: a grid that represent the image
        :param width: if a grid is not given, determines the width of the graph
        :param height: if a grid is not given, determines the height of the graph
        :param graph: if a networkx graph is given, use it directly as the graph
        """
        self.task = task

        self.name = name
        self.grid = grid
        self.arc_graph = None 
        self.colors_included = set()
        self.background_color = semantic_prior("image.default_background_color")
        self.most_common_color = 0
        self.least_common_color = 0

        if not grid and not graph:
            # create a blank 2D graph with default color
            self.width = width
            self.height = height
            self.size = (width, height)
            self.graph = nx.grid_2d_graph(height, width)
            self.init()
            #complete() called later
        elif graph:
            self.init_from_graph(graph)
            self.complete()
        else:
            self.init_from_grid(grid)
            self.complete()
        
    def copy(self):
        """
        return a copy of the image
        """
        return Image(self.task, grid=self.grid, width=self.width, height=self.height, graph=self.graph ,name=self.name)

    def cooperative_stop_requested(self):
        if getattr(self.task, "stop_search", False):
            return True
        check_time_limit = getattr(self.task, "check_time_limit", None)
        if callable(check_time_limit):
            return bool(check_time_limit())
        return False

    def abort_if_stop_requested(self, context="image operation"):
        if self.cooperative_stop_requested():
            raise TimeoutError(f"{self.name} stopped during {context}")

    def init(self):
        """
        set the colors of the graph to be the default color
        """
        nx.set_node_attributes(self.graph, 0, "color")
        self._bind_raw_pixel_canvas()
        self.arc_graph = ARCGraph(self.graph, self.name, self) # wrapper ARCGraph
        self.colors_included.add(0)
    
    def init_from_graph(self, graph:nx.grid_2d_graph):
        """
        set the colors of the graph from the given graph
        :param graph: a networkx graph that represent the image
        """
        self.width = max([node[1] for node in graph.nodes()]) + 1
        self.height = max([node[0] for node in graph.nodes()]) + 1
        self.size = (self.width, self.height)
        self.graph = graph
        self._bind_raw_pixel_canvas()
        self.arc_graph = ARCGraph(self.graph, self.name, self) # wrapper ARCGraph
        
    def init_from_grid(self, grid):
        """
        set the colors of the graph from the grid
        :param grid: array or color rows (matrix)
        """
        self.width = len(grid[0])
        self.height = len(grid)
        self.size = (self.width, self.height)
        self.graph = nx.grid_2d_graph(self.height, self.width)
        self._bind_raw_pixel_canvas()

        colors = []
        for r, row in enumerate(grid):
            for c, color in enumerate(row):
                self.graph.nodes[r, c]["color"] = color # set pixel color
                colors.append(color)
        self.arc_graph = ARCGraph(self.graph, self.name, self) # wrapper ARCGraph
        self.colors_included = colors
        self.grid = grid    

    def _bind_raw_pixel_canvas(self):
        """Construct the default ontology-bound AbstractScene for this grid."""

        contract = root_abstraction_contract("image_scene_construction")
        if not contract.wake_authorized:
            raise ValueError("Image root abstraction is not wake-authorized")
        self.graph.graph.setdefault(
            "background_hypothesis_id",
            primary_background_hypothesis_id("nbccg"),
        )
        self.graph.graph.setdefault(
            "canvas_support_hypothesis_id", "whole_grid_canvas"
        )
        self.graph.graph.setdefault(
            "scene_decomposition_rule_id",
            "rdr_rule:whole_grid_scene_decomposition_default",
        )
        self.graph.graph.setdefault(
            "scene_decomposition_rule_ontology_iri",
            expand_runtime_iri("arga:rdr_default_whole_grid_scene_decomposition"),
        )
        self.graph.graph["root_abstraction_contract_id"] = contract.contract_id
        self.graph.graph["root_abstraction_contract_iri"] = expand_runtime_iri(
            contract.ontology_iri
        )
        self.graph.graph["abstract_scene_composition"] = (
            "PixelGridGraph+BackgroundHypothesis+CanvasSupportHypothesis"
        )
        self.graph.graph.setdefault("canvas_color", self.background_color)

    def bind_scene_decomposition_contract(self, binding):
        """Revise the root AbstractScene and propagate it into its ARCGraph."""

        metadata = {
            "scene_decomposition_rule_id": binding["scene_decomposition_rule_id"],
            "scene_decomposition_rule_ontology_iri": binding[
                "scene_decomposition_rule_ontology_iri"
            ],
            "scene_decomposition_profile_id": binding["concept_profile_id"],
            "scene_decomposition_profile_iri": binding["concept_profile_iri"],
            "scene_decomposition_connector_chain_id": binding["connector_chain_id"],
            "background_hypothesis_id": binding["background_hypothesis_id"],
            "canvas_support_hypothesis_id": binding[
                "canvas_support_hypothesis_id"
            ],
            "ontology_binding_iris": list(binding["ontology_binding_iris"]),
            "abstract_scene_composition": (
                "PixelGridGraph+BackgroundHypothesis+CanvasSupportHypothesis"
            ),
        }
        self.graph.graph.update(metadata)
        if self.arc_graph is not None:
            self.arc_graph.bind_root_scene_contract(metadata)
    
    def complete(self):
        self.corners = {(0, 0), (0, self.width - 1), (self.height - 1, 0), (self.height - 1, self.width - 1)}
        self.edges = frozenset(node for node in self.graph.nodes() \
                if node[0] == 0 or node[0] == self.height - 1 or node[1] == 0 or node[1] == self.width - 1)
        colors = []
        for node, data in self.graph.nodes(data=True):
            colors.append(data["color"])
        self.colors_included = set(colors)
        if len(colors) != 0: # from __init__
            self.most_common_color = modal_color([colors])
            self.least_common_color = min(set(colors), key=colors.count)

        """
        # background is defined as a node that includes a corner and has the most common color
        if self.background_color != self.most_common_color:
            for node, data in self.graph.nodes(data=True):
                if node in self.corners and data.get("color") == self.most_common_color:
                    self.background_color = self.most_common_color
                    break   
        """

    def _grid_array(self):
        """
        Return the current image colors as a dense numpy array.

        `self.grid` is populated for normal task images, but images created from
        graphs may not retain the original nested-list representation.
        """
        if self.grid is not None:
            return np.asarray(self.grid)
        return np.asarray([
            [self.graph.nodes[row, col]["color"] for col in range(self.width)]
            for row in range(self.height)
        ])

    def background_binding_for_abstraction(self, abstraction):
        """Return the ontology hypothesis and selected canvas color together."""

        grid = self._grid_array().tolist()
        return (
            primary_background_hypothesis_id(abstraction),
            select_abstraction_background_color(abstraction, grid),
        )

    @staticmethod
    def _foreground_overlap_score(grid, reflected_grid, background_color):
        """
        Score colored reflectional overlap without letting background pixels
        dominate the result.

        This is the ARC-grid equivalent of the binary IoU score used by
        symmetry_extraction.py: only cells occupied by foreground in either
        image participate, and overlapping cells must also preserve color.
        """
        original_foreground = grid != background_color
        reflected_foreground = reflected_grid != background_color
        union = original_foreground | reflected_foreground
        union_size = np.count_nonzero(union)
        if union_size == 0:
            return 1.0
        color_matches = (grid == reflected_grid) & union
        return np.count_nonzero(color_matches) / union_size

    def get_reflectional_symmetry_scores(self, include_diagonal=True):
        """
        Return per-axis reflectional symmetry scores for this image.

        The standalone symmetry_extraction.py rotates a general bitmap through
        many angles. ARC grids are discrete and transformations elsewhere in the
        codebase already use canonical mirror directions, so this method checks
        the four exact axes that preserve grid structure:

        - vertical
        - horizontal
        - diagonal-left (\\)
        - diagonal-right (/)

        Diagonal axes are only meaningful for square grids.
        """
        grid = self._grid_array()
        reflected_grids = {
            Mirror.VERTICAL: np.fliplr(grid),
            Mirror.HORIZONTAL: np.flipud(grid),
        }
        if include_diagonal and self.height == self.width:
            reflected_grids[Mirror.DIAGONAL_LEFT] = grid.T
            reflected_grids[Mirror.DIAGONAL_RIGHT] = np.rot90(grid, 2).T

        return {
            axis: self._foreground_overlap_score(grid, reflected_grid, self.background_color)
            for axis, reflected_grid in reflected_grids.items()
        }

    def detect_reflectional_symmetry(self, min_score=1.0, include_diagonal=True):
        """
        Detect the strongest reflectional symmetry of this image.

        Returns a dictionary with:
        - axis: best-scoring mirror axis
        - score: best overlap score
        - is_symmetric: whether the best score reaches `min_score`
        - symmetric_axes: every axis meeting `min_score`
        - scores: all measured axis scores

        `min_score=1.0` requires exact colored symmetry. Lower thresholds expose
        approximate symmetry in the same spirit as symmetry_extraction.py.
        """
        scores = self.get_reflectional_symmetry_scores(include_diagonal=include_diagonal)
        axis_priority = {
            Mirror.VERTICAL: 0,
            Mirror.HORIZONTAL: 1,
            Mirror.DIAGONAL_LEFT: 2,
            Mirror.DIAGONAL_RIGHT: 3,
        }
        best_axis, best_score = max(
            scores.items(),
            key=lambda item: (item[1], -axis_priority[item[0]]),
        )
        symmetric_axes = [
            axis
            for axis, score in scores.items()
            if score >= min_score or np.isclose(score, min_score)
        ]
        return {
            "axis": best_axis,
            "score": best_score,
            "is_symmetric": best_score >= min_score or np.isclose(best_score, min_score),
            "symmetric_axes": symmetric_axes,
            "scores": scores,
        }

    def find_reflectional_symmetry(self, min_score=1.0, include_diagonal=True):
        """
        Compatibility wrapper mirroring the name used by symmetry_extraction.py.
        """
        return self.detect_reflectional_symmetry(
            min_score=min_score,
            include_diagonal=include_diagonal,
        )

    def get_rotational_symmetry_scores(self, include_quarter_turns=True):
        """
        Return exact-grid rotational symmetry scores for the whole image.

        Background cells do not dominate the score: overlap is measured only
        where either orientation has foreground.
        """
        grid = self._grid_array()
        rotations = {180: np.rot90(grid, 2)}
        if include_quarter_turns and self.height == self.width:
            rotations[90] = np.rot90(grid, 1)
            rotations[270] = np.rot90(grid, 3)
        return {
            degrees: self._foreground_overlap_score(
                grid,
                rotated_grid,
                self.background_color,
            )
            for degrees, rotated_grid in rotations.items()
        }

    def detect_rotational_symmetry(self, min_score=1.0, include_quarter_turns=True):
        """Detect the strongest whole-image rotational symmetry."""
        scores = self.get_rotational_symmetry_scores(
            include_quarter_turns=include_quarter_turns,
        )
        best_degrees, best_score = max(
            scores.items(),
            key=lambda item: (item[1], -item[0]),
        )
        symmetric_rotations = [
            degrees
            for degrees, score in scores.items()
            if score >= min_score or np.isclose(score, min_score)
        ]
        return {
            "degrees": best_degrees,
            "score": best_score,
            "is_symmetric": best_score >= min_score or np.isclose(best_score, min_score),
            "symmetric_rotations": symmetric_rotations,
            "scores": scores,
        }

    def has_symmetry_absent_from(self, other, min_score=1.0):
        """
        Return whole-image symmetries present here but absent from another image.

        This is the comparison signal needed for latent-canvas tasks: when the
        output is symmetric and the input is not, the output may expose a canvas
        rule while the input carries occluders or defects.
        """
        self_reflection = self.detect_reflectional_symmetry(min_score=min_score)
        other_reflection = other.detect_reflectional_symmetry(min_score=min_score)
        self_rotation = self.detect_rotational_symmetry(min_score=min_score)
        other_rotation = other.detect_rotational_symmetry(min_score=min_score)
        return {
            "reflection_axes": [
                axis
                for axis in self_reflection["symmetric_axes"]
                if axis not in other_reflection["symmetric_axes"]
            ],
            "rotations": [
                degrees
                for degrees in self_rotation["symmetric_rotations"]
                if degrees not in other_rotation["symmetric_rotations"]
            ],
        }

    def component_texture_profile(self):
        """
        Summarize whether monochrome fragmentation looks canvas-like.

        A richly patterned canvas often appears as many tiny same-color
        components even though semantically it is one field. Keeping this at
        Image scope helps avoid committing to hundreds of graph objects too
        early.
        """
        sizes = []
        for color in self.colors_included:
            color_nodes = (
                node
                for node, data in self.graph.nodes(data=True)
                if data.get("color") == color
            )
            color_subgraph = self.graph.subgraph(color_nodes)
            sizes.extend(
                len(component)
                for component in connected_components(color_subgraph)
            )
        if not sizes:
            return {
                "component_count": 0,
                "mean_size": 0,
                "median_size": 0,
                "component_density": 0,
                "small_component_fraction": 0,
                "canvas_like": False,
            }

        component_count = len(sizes)
        mean_size = float(np.mean(sizes))
        median_size = float(np.median(sizes))
        area = max(1, self.width * self.height)
        component_density = component_count / area
        small_component_fraction = sum(size <= 2 for size in sizes) / component_count
        return {
            "component_count": component_count,
            "mean_size": mean_size,
            "median_size": median_size,
            "component_density": component_density,
            "small_component_fraction": small_component_fraction,
            "canvas_like": (
                component_density >= 0.1
                and median_size <= 2
                and small_component_fraction >= 0.5
            ),
        }

    def _mask_component_sizes(self, mask):
        """Return 4-connected component sizes for a boolean grid mask."""
        rows, cols = mask.shape
        nodes = {
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if mask[row, col]
        }
        if not nodes:
            return []
        return [
            len(component)
            for component in connected_components(self.graph.subgraph(nodes))
        ]

    @staticmethod
    def _regular_spans(separator_indices, limit):
        bounds = [-1] + sorted(separator_indices) + [limit]
        spans = [
            (bounds[index] + 1, bounds[index + 1])
            for index in range(len(bounds) - 1)
            if bounds[index] + 1 < bounds[index + 1]
        ]
        if not spans:
            return [], False
        widths = {end - start for start, end in spans}
        return spans, len(widths) == 1

    def _foreground_profile_outside_canvas_colors(self, canvas_colors):
        grid = self._grid_array()
        canvas_colors = set(canvas_colors)
        foreground_mask = np.ones(grid.shape, dtype=bool)
        for canvas_color in canvas_colors | {self.background_color}:
            foreground_mask &= grid != canvas_color
        sizes = self._mask_component_sizes(foreground_mask)
        foreground_pixels = int(np.count_nonzero(foreground_mask))
        area = max(1, self.width * self.height)
        return {
            "foreground_component_count": len(sizes),
            "foreground_pixels": foreground_pixels,
            "foreground_size_ratio": foreground_pixels / area,
            "foreground_component_median_size": float(np.median(sizes)) if sizes else 0,
        }

    def detect_regular_lattice_canvas_context(self):
        """
        Detect a cheap present-canvas context: one color forms full row/column
        separators with regular cells.  This is evidence for an adapter mask,
        not an OWL classification and not a whole-image solution.
        """
        grid = self._grid_array()
        rows, cols = grid.shape
        if rows == 0 or cols == 0:
            return None

        candidates = []
        for color in sorted(set(grid.flatten().tolist())):
            if color == self.background_color:
                continue
            full_rows = [
                row
                for row in range(rows)
                if np.all(grid[row, :] == color)
            ]
            full_cols = [
                col
                for col in range(cols)
                if np.all(grid[:, col] == color)
            ]
            if not full_rows or not full_cols:
                continue
            row_spans, rows_regular = self._regular_spans(full_rows, rows)
            col_spans, cols_regular = self._regular_spans(full_cols, cols)
            if not rows_regular or not cols_regular:
                continue

            mask = np.zeros((rows, cols), dtype=bool)
            if full_rows:
                mask[full_rows, :] = True
            if full_cols:
                mask[:, full_cols] = True
            foreground_profile = self._foreground_profile_outside_canvas_colors({color})
            candidates.append({
                "kind": "present_canvas_context",
                "evidence_type": "regular_lattice",
                "canvas_colors": [int(color)],
                "mask": frozenset(
                    (int(row), int(col))
                    for row in range(rows)
                    for col in range(cols)
                    if mask[row, col]
                ),
                "mask_pixel_count": int(np.count_nonzero(mask)),
                "mask_coverage": int(np.count_nonzero(mask)) / max(1, rows * cols),
                "row_separators": [int(row) for row in full_rows],
                "col_separators": [int(col) for col in full_cols],
                "row_cell_size": int(row_spans[0][1] - row_spans[0][0]) if row_spans else 0,
                "col_cell_size": int(col_spans[0][1] - col_spans[0][0]) if col_spans else 0,
                "template_grid": [list(row) for row in grid.tolist()],
                **foreground_profile,
            })

        if not candidates:
            return None
        return max(
            candidates,
            key=lambda context: (
                len(context["row_separators"]) + len(context["col_separators"]),
                context["mask_pixel_count"],
                -context["canvas_colors"][0],
            ),
        )

    def detect_symmetric_color_canvas_contexts(self):
        """
        Detect cheap symmetric/periodic-looking color masks as possible canvas
        context.  This is deliberately evidence only; solver acceptance still
        requires exact train validation.
        """
        grid = self._grid_array()
        rows, cols = grid.shape
        if rows == 0 or cols == 0:
            return []

        contexts = []
        for color in sorted(set(grid.flatten().tolist())):
            if color == self.background_color:
                continue
            mask = grid == color
            mask_count = int(np.count_nonzero(mask))
            if mask_count == 0:
                continue
            coverage = mask_count / max(1, rows * cols)
            component_sizes = self._mask_component_sizes(mask)
            component_count = len(component_sizes)
            median_size = float(np.median(component_sizes)) if component_sizes else 0
            # A symmetric single object is usually foreground, not canvas.  This
            # generic detector is for fragmented/patterned canvas fields.
            if component_count < 6 or median_size > 4 or coverage > 0.6:
                continue

            axes = []
            rotations = []
            if np.array_equal(mask, np.fliplr(mask)):
                axes.append("VERTICAL")
            if np.array_equal(mask, np.flipud(mask)):
                axes.append("HORIZONTAL")
            if rows == cols:
                if np.array_equal(mask, mask.T):
                    axes.append("DIAGONAL_LEFT")
                if np.array_equal(mask, np.rot90(mask, 2).T):
                    axes.append("DIAGONAL_RIGHT")
                if np.array_equal(mask, np.rot90(mask, 1)):
                    rotations.append(90)
                if np.array_equal(mask, np.rot90(mask, 3)):
                    rotations.append(270)
            if np.array_equal(mask, np.rot90(mask, 2)):
                rotations.append(180)
            if not axes and not rotations:
                continue

            foreground_profile = self._foreground_profile_outside_canvas_colors({color})
            contexts.append({
                "kind": "present_canvas_context",
                "evidence_type": "symmetric_color_mask",
                "canvas_colors": [int(color)],
                "mask": frozenset(
                    (int(row), int(col))
                    for row in range(rows)
                    for col in range(cols)
                    if mask[row, col]
                ),
                "mask_pixel_count": mask_count,
                "mask_coverage": coverage,
                "component_count": component_count,
                "component_median_size": median_size,
                "reflection_axes": axes,
                "rotations": rotations,
                "template_grid": [list(row) for row in grid.tolist()],
                **foreground_profile,
            })
        return contexts

    def detect_canvas_contexts(self):
        """
        Return cheap Image-level present-canvas evidence.  The detector emits
        primitive masks/templates only; OWL classes may label this evidence
        later, but reasoning is not part of the hot path.
        """
        contexts = []
        lattice_context = self.detect_regular_lattice_canvas_context()
        if lattice_context is not None:
            contexts.append(lattice_context)
        contexts.extend(self.detect_symmetric_color_canvas_contexts())
        return contexts

    def detect_preserved_substrate_context(self, output_image):
        """
        Detect an arbitrary full-grid substrate: same-size input/output where
        every cell belongs to the same canvas/substrate and the output makes a
        sparse edit on top of that substrate.

        This is intentionally broader than lattice/symmetry canvas evidence.
        It marks tasks where the whole image is a substrate/obstacle field.
        The exact edit semantics are recorded as `edit_profile`; consumers that
        need a path/overlay rule must check that profile explicitly.
        """
        if output_image is None or self.size != output_image.size:
            return None

        input_grid = self._grid_array()
        output_grid = output_image._grid_array()
        rows, cols = input_grid.shape
        area = max(1, rows * cols)

        changed = input_grid != output_grid
        changed_count = int(np.count_nonzero(changed))

        overlay_ratio = changed_count / area
        if overlay_ratio > 0.20:
            return None

        background = self.background_color
        changed_from_background = changed & (input_grid == background)
        changed_non_background = changed & (input_grid != background)
        changed_to_background = changed & (output_grid == background)
        changed_from_background_count = int(np.count_nonzero(changed_from_background))
        changed_non_background_count = int(np.count_nonzero(changed_non_background))
        changed_to_background_count = int(np.count_nonzero(changed_to_background))

        added_colors = sorted(
            int(color)
            for color in set(output_grid[changed_from_background].flatten().tolist())
            if color != background
        )
        recolor_output_colors = sorted(
            int(color)
            for color in set(output_grid[changed_non_background].flatten().tolist())
            if color != background
        )
        output_changed_colors = sorted(
            int(color)
            for color in set(output_grid[changed].flatten().tolist())
        )
        input_changed_colors = sorted(
            int(color)
            for color in set(input_grid[changed].flatten().tolist())
        )

        if changed_count == 0:
            edit_profile = "identity_preserved_substrate"
        elif changed_from_background_count == changed_count and added_colors:
            edit_profile = "sparse_background_overlay"
        elif (
            changed_non_background_count == changed_count
            and changed_to_background_count == 0
            and recolor_output_colors
        ):
            edit_profile = "sparse_foreground_recolor"
        elif (
            changed_non_background_count == changed_count
            and changed_to_background_count == changed_count
        ):
            edit_profile = "sparse_foreground_erase"
        else:
            edit_profile = "mixed_sparse_edit"

        input_non_background = input_grid != background
        input_non_background_count = int(np.count_nonzero(input_non_background))
        substrate_component_sizes = self._mask_component_sizes(input_non_background)
        substrate_component_count = len(substrate_component_sizes)
        substrate_component_density = substrate_component_count / area
        substrate_component_to_pixel_ratio = (
            substrate_component_count / input_non_background_count
            if input_non_background_count
            else 0.0
        )
        substrate_component_median_size = (
            float(np.median(substrate_component_sizes))
            if substrate_component_sizes
            else 0.0
        )
        foreground_profile = self._foreground_profile_outside_canvas_colors(
            set(int(color) for color in set(input_grid.flatten().tolist()))
            | set(output_changed_colors)
        )
        return {
            "kind": "present_canvas_context",
            "evidence_type": "arbitrary_preserved_substrate",
            "canvas_scope": "full_grid",
            "canvas_colors": sorted(int(color) for color in set(input_grid.flatten().tolist())),
            "edit_profile": edit_profile,
            "added_colors": added_colors,
            "recolor_output_colors": recolor_output_colors,
            "input_changed_colors": input_changed_colors,
            "output_changed_colors": output_changed_colors,
            "mask": frozenset(
                (int(row), int(col))
                for row in range(rows)
                for col in range(cols)
            ),
            "mask_pixel_count": area,
            "mask_coverage": 1.0,
            "changed_pixel_count": changed_count,
            "overlay_ratio": overlay_ratio,
            "changed_from_background_count": changed_from_background_count,
            "changed_non_background_count": changed_non_background_count,
            "changed_to_background_count": changed_to_background_count,
            "input_non_background_count": input_non_background_count,
            "substrate_component_count": substrate_component_count,
            "substrate_component_density": substrate_component_density,
            "substrate_component_to_pixel_ratio": substrate_component_to_pixel_ratio,
            "substrate_component_median_size": substrate_component_median_size,
            "foreground_component_count": foreground_profile["foreground_component_count"],
            "foreground_size_ratio": foreground_profile["foreground_size_ratio"],
            "template_grid": [list(row) for row in input_grid.tolist()],
        }

    def canvas_context_preserved_by(self, output_image, context):
        """True if immutable canvas-mask cells are unchanged in output."""
        if output_image is None or self.size != output_image.size:
            return False
        input_grid = self._grid_array()
        output_grid = output_image._grid_array()
        for row, col in context.get("mask", ()):
            if input_grid[row, col] != output_grid[row, col]:
                return False
        return True
     
    def validate_grid_shape(self, grid, context="grid"):
        rows = len(grid) if grid is not None else 0
        cols = len(grid[0]) if rows > 0 else 0
        if rows <= 0 or cols <= 0:
            raise ValueError(f"{context} produced invalid grid size [{cols}x{rows}]")
        for row in grid:
            if len(row) != cols:
                raise ValueError(f"{context} produced non-rectangular grid")
        total_pixels = rows * cols
        if total_pixels > self.max_allowd_pixels:
            raise ValueError(
                f"{context} exceeds allowed pixels {self.max_allowd_pixels}: "
                f"[{cols}x{rows}] = {total_pixels}"
            )
        max_dim = getattr(self, "max_arc_dimension", 30)
        if rows > max_dim or cols > max_dim:
            raise ValueError(
                f"{context} exceeds ARC grid dimension {max_dim}: [{cols}x{rows}]"
            )
        return rows, cols

    def graph_from_grid(self, grid): # 2D_graph from grid
        """
        Create 2D graph based on the grid representation.
        """
        self.validate_grid_shape(grid, "graph_from_grid")
        self.abort_if_stop_requested("graph_from_grid")
        colors = []
        graph = nx.grid_2d_graph(len(grid), len(grid[0]))
        for y, row in enumerate(grid):
            self.abort_if_stop_requested("graph_from_grid")
            for x, color in enumerate(row):   
                graph.nodes[(y, x)]['color'] = color
                colors.append(color)
        return graph
      
    def get_abstract_graph(self, grid, graph:nx.grid_2d_graph, abstraction="na"):
        contract = abstraction_contract(abstraction)
        if not contract.wake_authorized:
            raise ValueError(f"abstraction {abstraction!r} is not wake-authorized")
        support_binding = getattr(
            self.task,
            "canvas_support_by_image_name",
            {},
        ).get(self.name)
        if abstraction != "na" and support_binding is not None:
            # The support premise is learned once across examples.  Every
            # component abstraction sees the same projected scene, so outside
            # noise cannot silently become a foreground component in one rule.
            from ontology.scene_decomposition import clear_outside_canvas

            grid = clear_outside_canvas(
                grid,
                background_color=int(support_binding["background_color"]),
                evidence=support_binding["evidence"],
            )
            graph = self.graph_from_grid(grid)
        if abstraction != "na":
            rows, cols = self.validate_grid_shape(grid, "get_abstract_graph")
            if rows != max([node[0] for node in graph.nodes()]) + 1 or \
               cols != max([node[1] for node in graph.nodes()]) + 1:
                raise ValueError(f"{graph} does not match grid [{cols}x{rows}] dimensions.")
        new_image = self.copy() # make a copy of original image
        new_image.init_from_grid(grid) # reset image from grid   
        new_image.init_from_graph(graph) # reset from new graph 
        if support_binding is not None:
            new_image.bind_scene_decomposition_contract(support_binding)
        new_image.abort_if_stop_requested(f"{abstraction} abstraction")
        abstract_graph = getattr(new_image, contract.callable_name)()
        if support_binding is not None:
            abstract_graph.graph.graph["canvas_support_hypothesis_id"] = (
                support_binding["canvas_support_hypothesis_id"]
            )
            abstract_graph.graph.graph["scene_background_hypothesis_id"] = (
                support_binding["background_hypothesis_id"]
            )
            abstract_graph.graph.graph["canvas_bounds"] = [
                0,
                0,
                int(support_binding["evidence"]["bound_height"]),
                int(support_binding["evidence"]["bound_width"]),
            ]
            abstract_graph.bind_root_scene_contract(new_image.graph.graph)
        new_image.abort_if_stop_requested(f"{abstraction} abstraction")
        if abstract_graph.graph.number_of_nodes() > self.max_allowd_pixels:
            raise ValueError(
                f"too many abstract nodes {abstract_graph.graph.number_of_nodes()}"
            )
        abstract_graph.image = new_image # set image reference to the new image
        return abstract_graph
        
    def get_connected_components(self, nodes:set):
        """
        return a list of connected components in the subgraph
        """
        subgraph = self.graph.subgraph(nodes)
        return list(connected_components(subgraph))    
        
    def get_connected_components_graph(self, graph=None):
        """
        return an abstracted graph where a node is defined as: 
        a group of adjacent pixels of the same color in the original graph
        """
        if not graph:
            graph = self.graph

        color_connected_components_graph = nx.DiGraph()

        for color in self.colors_included:
            self.abort_if_stop_requested("connected components")
            color_nodes = (node for node, data in graph.nodes(data=True) if data.get("color") == color)
            color_subgraph = graph.subgraph(color_nodes)
            color_connected_components = connected_components(color_subgraph) 
            for i, component in enumerate(color_connected_components): # every monochrome connected components      
                self.abort_if_stop_requested("connected components")
                node_id = self.arc_graph.generate_node_id(color_connected_components_graph, list(component))    
                color_connected_components_graph.add_node(node_id, nodes=list(component), color=color,
                                                                size=len(list(component)))
        hypothesis_id, background_color = self.background_binding_for_abstraction("ccg")
        converted = self.convert(
            graph,
            color_connected_components_graph,
            background_color=background_color,
        )
        converted.graph["background_hypothesis_id"] = hypothesis_id
        # ``ccg`` retains components of every color, so its selection
        # hypothesis is the structural no-color sibling.  Reconstruction is
        # a separate AbstractScene concern: moved components must expose the
        # root scene's render canvas, not a Python None sentinel.
        converted.graph["canvas_color"] = self.graph.graph.get(
            "canvas_color", self.background_color
        )
        return ARCGraph(converted, self.name, self, "ccg")

    def get_no_color_connected_components_graph(self, graph=None):
        """Represent every colored cell over a structural no-color canvas.

        Unlike a monochrome background abstraction, ``ncccg`` excludes no ARC
        palette value.  The canvas has no color binding, so every pixel remains
        represented by a monochrome scene component and reconstruction is a
        lossless overlay over the structural canvas.
        """
        if not graph:
            graph = self.graph

        components_graph = nx.DiGraph()
        for color in self.colors_included:
            self.abort_if_stop_requested("no-color connected components")
            color_nodes = (
                node
                for node, data in graph.nodes(data=True)
                if data.get("color") == color
            )
            for component in connected_components(graph.subgraph(color_nodes)):
                self.abort_if_stop_requested("no-color connected components")
                pixels = list(component)
                node_id = self.arc_graph.generate_node_id(components_graph, pixels)
                components_graph.add_node(
                    node_id,
                    nodes=pixels,
                    color=color,
                    size=len(pixels),
                    canvas_hypothesis="no_color_canvas",
                )
        hypothesis_id, background_color = self.background_binding_for_abstraction("ncccg")
        converted = self.convert(graph, components_graph, background_color=background_color)
        converted.graph["background_hypothesis_id"] = hypothesis_id
        converted.graph["canvas_color"] = background_color
        return ARCGraph(converted, self.name, self, "ncccg")
    
    
    def get_connected_components_graph_background_removed(self, graph=None):
        """
        return an abstracted graph where a node is defined as: 
        a group of adjacent pixels of the same color in the original graph.
        remove nodes identified as background.
        background is defined as a node that includes a corner and has the most common color
        """
        if not graph:
            graph = self.graph
        ccgbr = nx.DiGraph()
        hypothesis_id, background_color = self.background_binding_for_abstraction("ccgbr")

        for color in self.colors_included:
            self.abort_if_stop_requested("background-removed connected components")
            color_nodes = (node for node, data in graph.nodes(data=True) if data.get("color") == color)
            color_subgraph = graph.subgraph(color_nodes)
            color_connected_components = connected_components(color_subgraph)
            if color != background_color:
                for i, component in enumerate(color_connected_components): # non-backgroubd connected components
                    self.abort_if_stop_requested("background-removed connected components")
                    node_id = self.arc_graph.generate_node_id(ccgbr, list(component))
                    ccgbr.add_node(node_id, nodes=list(component), color=color, size=len(list(component)))
            else:
                for i, component in enumerate(color_connected_components): # background removed only if has corners
                    self.abort_if_stop_requested("background-removed connected components")
                    if len(set(component) & self.corners) == 0:  # background color + does not contains a corner
                        node_id = self.arc_graph.generate_node_id(ccgbr, list(component))
                        ccgbr.add_node(node_id, nodes=list(component), color=color, size=len(list(component)))
        converted = self.convert(graph, ccgbr, background_color=background_color)
        converted.graph["background_hypothesis_id"] = hypothesis_id
        converted.graph["canvas_color"] = background_color
        return ARCGraph(converted, self.name, self, "ccgbr")

    def get_connected_components_graph_background_removed_2(self, graph=None):
        """
        return an abstracted graph where a node is defined as: 
        a group of adjacent pixels of the same color in the original graph.
        remove nodes identified as background.
        background is defined as a node that includes a corner or an edge node and has the most common color
        """
        if not graph:
            graph = self.graph

        ccgbr2 = nx.DiGraph()
        hypothesis_id, background_color = self.background_binding_for_abstraction("ccgbr2")

        for color in self.colors_included:
            color_nodes = (node for node, data in graph.nodes(data=True) if data.get("color") == color)
            color_subgraph = graph.subgraph(color_nodes)
            color_connected_components = connected_components(color_subgraph)

            for i, component in enumerate(color_connected_components):  # every monochrome connected components
                if color != background_color:
                    node_id = self.arc_graph.generate_node_id(ccgbr2, list(component))            
                    ccgbr2.add_node(node_id, nodes=list(component), color=color, size=len(list(component)))
                else:
                    component = list(component) # background removed only if contains some corner or edge
                    for node in component:
                        if len(set(component) & self.corners) > 0 or len(set(component) & self.edges) > 0:
                            break # background color + contains a corner or an edge node
                    else:
                        node_id = self.arc_graph.generate_node_id(ccgbr2, list(component))
                        ccgbr2.add_node(node_id, nodes=list(component), color=color, size=len(list(component)))    
        converted = self.convert(graph, ccgbr2, background_color=background_color)
        converted.graph["background_hypothesis_id"] = hypothesis_id
        converted.graph["canvas_color"] = background_color
        return ARCGraph(converted, self.name, self, "ccgbr2")

    def get_connected_components_graph_corner_edge_removed(self, graph=None):
        """
        return an abstracted graph where a node is defined as: 
        a group of adjacent pixels of the same color in the original graph.
        remove nodes identified as background.
        background is defined as a node that includes a corner or an edge node and has the most common color
        """
        if not graph:
            graph = self.graph

        ccgbcr = nx.DiGraph()
        hypothesis_id, background_color = self.background_binding_for_abstraction("ccgbcr")

        for color in self.colors_included:
            color_nodes = (node for node, data in graph.nodes(data=True) if data.get("color") == color)
            color_subgraph = graph.subgraph(color_nodes)
            color_connected_components = connected_components(color_subgraph)
            
            for i, component in enumerate(color_connected_components):  # every monochrome connected components
                component = list(component) 
                for node in component:  # any node removed if contains some corner or edge
                    if len(set(component) & self.corners) > 0: # or len(set(component) & self.edges) > 0:
                        break # contains a corner or an edge node
                else: 
                    node_id = self.arc_graph.generate_node_id(ccgbcr, list(component))
                    ccgbcr.add_node(node_id, nodes=list(component), color=color, size=len(list(component)))         
        converted = self.convert(graph, ccgbcr, background_color=background_color)
        converted.graph["background_hypothesis_id"] = hypothesis_id
        converted.graph["canvas_color"] = background_color
        return ARCGraph(converted, self.name, self, "ccgbcr")


    def get_non_background_vertical_connected_components_graph(self, graph=None):
        """
        return an abstracted graph where a node is defined as: 
        a group of vertically adjacent pixels of the same color in the original graph, excluding background color.
        """
        if not graph:
            graph = self.graph

        non_background_v_connected_components_graph = nx.DiGraph()
        polarize = "horizontal" # only consider vertical connections, so ignore horizontal connections when adding edges between abstracted nodes
        hypothesis_id, background_color = self.background_binding_for_abstraction("nbvcg")

        for color in self.colors_included:
            color_connected_components = []
            if color == background_color:
                continue # excluding background color
            for column in range(self.width):
                color_nodes = (node for node, data in graph.nodes(data=True) if
                               node[1] == column and data.get("color") == color)
                color_subgraph = graph.subgraph(color_nodes)
                color_connected_components.extend(list(connected_components(color_subgraph)))
            for i, component in enumerate(color_connected_components):   
                node_id = self.arc_graph.generate_node_id(non_background_v_connected_components_graph, list(component))
                non_background_v_connected_components_graph.add_node(node_id, nodes=list(component),
                                                                color=color, size=len(list(component)))    
        converted = self.convert(
            graph,
            non_background_v_connected_components_graph,
            polarize,
            background_color=background_color,
        )
        converted.graph["background_hypothesis_id"] = hypothesis_id
        converted.graph["canvas_color"] = background_color
        return ARCGraph(converted, self.name, self, "nbvcg")

    def get_non_background_horizontal_connected_components_graph(self, graph=None):
        """
        return an abstracted graph where a node is defined as: 
        a group of horizontally adjacent pixels of the same color in the original graph, excluding background color.
        """
        if not graph:
            graph = self.graph

        non_background_h_connected_components_graph = nx.DiGraph()
        polarize = "vertical" # only consider horizontal connections, so ignore vertical connections when adding edges between abstracted nodes
        hypothesis_id, background_color = self.background_binding_for_abstraction("nbhcg")

        for color in self.colors_included:
            color_connected_components = []
            if color == background_color:
                continue
            for row in range(self.height):
                color_nodes = (node for node, data in graph.nodes(data=True) if
                               node[0] == row and data.get("color") == color)
                color_subgraph = graph.subgraph(color_nodes)
                color_connected_components.extend(list(connected_components(color_subgraph)))
            for i, component in enumerate(color_connected_components):   
                node_id = self.arc_graph.generate_node_id(non_background_h_connected_components_graph, list(component))
                non_background_h_connected_components_graph.add_node(node_id, nodes=list(component),
                                                            color=color, size=len(list(component)))
        converted = self.convert(
            graph,
            non_background_h_connected_components_graph,
            polarize,
            background_color=background_color,
        )
        converted.graph["background_hypothesis_id"] = hypothesis_id
        converted.graph["canvas_color"] = background_color
        return ARCGraph(converted, self.name, self, "nbhcg")

    
    def get_non_black_components_graph(self, graph=None):
        if not graph:
            graph = self.graph

        non_black_components_graph = nx.DiGraph()
        # `nbccg` means non-black, not non-background. The ontology hierarchy
        # binds it to the literal-black sibling even when another color is modal.
        hypothesis_id, background_color = self.background_binding_for_abstraction("nbccg")

        for color in self.colors_included:
            if color == background_color:
                continue
            color_nodes = (node for node, data in graph.nodes(data=True) if data.get("color") == color)
            color_subgraph = graph.subgraph(color_nodes)
            color_connected_components = connected_components(color_subgraph)
            for i, component in enumerate(color_connected_components):
                node_id = self.arc_graph.generate_node_id(non_black_components_graph, list(component))
                non_black_components_graph.add_node(node_id, nodes=list(component), color=color,
                                                    size=len(list(component)))
        converted = self.convert(
            graph,
            non_black_components_graph,
            background_color=background_color,
        )
        converted.graph["background_hypothesis_id"] = hypothesis_id
        converted.graph["canvas_color"] = background_color
        return ARCGraph(converted, self.name, self, "nbccg")

    def get_largest_rectangle_graph(self, graph=None):
        """
        return an abstracted graph where a node is defined as:
        a group of adjacent pixels of the same color in the original graph that makes up a rectangle, excluding black.
        rectangles are identified from largest to smallest.
        """
        if not graph:
            graph = self.graph
        hypothesis_id, background_color = self.background_binding_for_abstraction("lrg")

        def finish_lrg():
            converted = self.convert(graph, lrg, background_color=background_color)
            converted.graph["background_hypothesis_id"] = hypothesis_id
            converted.graph["canvas_color"] = background_color
            return ARCGraph(converted, self.name, self, "lrg")

        # https://www.drdobbs.com/database/the-maximal-rectangle-problem/184410529?pgno=1
        def area(llx, lly, urx, ury):
            if llx > urx or lly > ury or [llx, lly, urx, ury] == [0, 0, 0, 0]:
                return 0
            else:
                return (urx - llx + 1) * (ury - lly + 1)

        def all_nb(llx, lly, urx, ury, g):
            for x in range(llx, urx + 1):
                for y in range(lly, ury + 1):
                    if (y, x) not in g:
                        return False
            return True

        lrg = nx.DiGraph()
        for color in range(10):
            if color == background_color:
                continue
            color_nodes = (node for node, data in graph.nodes(data=True) if data.get("color") == color)
            color_subgraph = graph.subgraph(color_nodes)
            subgraph_nodes = set(color_subgraph.nodes())
            if len(subgraph_nodes) == 0:
                continue
            if self.width * self.height > self.task.max_abstract_nodes: # fail fast rother than trying to find all rectangles
                node_id = self.arc_graph.generate_node_id(lrg, list(subgraph_nodes))
                lrg.add_node(node_id, nodes=list(subgraph_nodes), color=color, size=len(subgraph_nodes))
                return finish_lrg()
            
            i = 0
            while len(subgraph_nodes) != 0:
                if lrg.number_of_nodes() > self.task.max_abstract_nodes:
                    return finish_lrg()
                best = [0, 0, 0, 0]
                for llx in range(self.width):
                    for lly in range(self.height):
                        for urx in range(self.width):
                            for ury in range(self.height):
                                cords = [llx, lly, urx, ury]
                                if area(*cords) > area(*best) and all_nb(*cords, subgraph_nodes):
                                    best = cords
                component = []
                for x in range(best[0], best[2] + 1):
                    for y in range(best[1], best[3] + 1):
                        component.append((y, x))
                        subgraph_nodes.remove((y, x))
                
                node_id = self.arc_graph.generate_node_id(lrg, component)
                lrg.add_node(node_id, nodes=component, color=color, size=len(component))
                i += 1
        return finish_lrg()

    def get_multicolor_connected_components_graph(self, graph=None):
        """
        return an abstracted graph where a node is defined as:
        a group of adjacent pixels of any non-background color in the original graph.
        """
        if not graph:
            graph = self.graph
        multicolor_connected_components_graph = nx.DiGraph()
        hypothesis_id, background_color = self.background_binding_for_abstraction("mcccg")

        non_background_nodes = [node for node, data in graph.nodes(data=True) if data["color"] != background_color]
        color_subgraph = graph.subgraph(non_background_nodes)
        multicolor_connected_components = connected_components(color_subgraph) # all non-background but connected pixels

        for i, component in enumerate(multicolor_connected_components):
            sub_nodes = []
            sub_nodes_color = []
            for node in component:
                sub_nodes.append(node)
                sub_nodes_color.append(graph.nodes[node]["color"])
            
            node_id = self.arc_graph.generate_node_id(multicolor_connected_components_graph, sub_nodes)
            multicolor_connected_components_graph.add_node(node_id, nodes=sub_nodes, 
                                            color=sub_nodes_color, size=len(sub_nodes))              
        converted = self.convert(
            graph,
            multicolor_connected_components_graph,
            background_color=background_color,
        )
        converted.graph["background_hypothesis_id"] = hypothesis_id
        converted.graph["canvas_color"] = background_color
        return ARCGraph(converted, self.name, self, "mcccg")

    def get_occlusion_connected_components_graph(self, graph=None):
        """
        Return an occlusion-tolerant multicolor component graph.

        This starts from monochrome foreground components, then merges component
        groups when differently colored foreground touches or when same-color
        visible subsegments are collinear with non-background colors between
        them.  The merged node keeps the original cell colors and records the
        merge evidence as occlusion metadata.
        """
        if not graph:
            graph = self.graph

        hypothesis_id, background_color = self.background_binding_for_abstraction("occg")
        component_cells: list[set[tuple[int, int]]] = []
        component_color: list[int] = []
        cell_component: dict[tuple[int, int], int] = {}
        for color in sorted(self.colors_included):
            if color == background_color:
                continue
            color_nodes = [
                node
                for node, data in graph.nodes(data=True)
                if data.get("color") == color
            ]
            for component in connected_components(graph.subgraph(color_nodes)):
                component_id = len(component_cells)
                cells = set(component)
                component_cells.append(cells)
                component_color.append(color)
                for cell in cells:
                    cell_component[cell] = component_id

        merge_graph = nx.Graph()
        merge_graph.add_nodes_from(range(len(component_cells)))
        occlusion_edges: dict[tuple[int, int], list[dict[str, object]]] = {}

        def add_merge(
            left: int,
            right: int,
            evidence: dict[str, object],
        ) -> None:
            if left == right:
                return
            key = tuple(sorted((left, right)))
            merge_graph.add_edge(*key)
            occlusion_edges.setdefault(key, []).append(evidence)

        for cell, left in sorted(cell_component.items()):
            row, col = cell
            for dr, dc in ((1, 0), (0, 1)):
                neighbor = (row + dr, col + dc)
                right = cell_component.get(neighbor)
                if right is None or right == left:
                    continue
                add_merge(left, right, {
                    "relation": "touching_foreground",
                    "cells": [list(cell), list(neighbor)],
                    "colors": sorted({component_color[left], component_color[right]}),
                })

        axes = ((0, 1), (1, 0), (1, 1), (1, -1))
        starts_by_axis = {
            (0, 1): [(row, 0) for row in range(self.height)],
            (1, 0): [(0, col) for col in range(self.width)],
            (1, 1): [(0, col) for col in range(self.width)] + [(row, 0) for row in range(1, self.height)],
            (1, -1): [(0, col) for col in range(self.width)] + [(row, self.width - 1) for row in range(1, self.height)],
        }
        for direction in axes:
            direction_name = {
                (0, 1): "right",
                (1, 0): "down",
                (1, 1): "down_right",
                (1, -1): "down_left",
            }[direction]
            dr, dc = direction
            for start in starts_by_axis[direction]:
                line: list[tuple[int, int]] = []
                row, col = start
                while 0 <= row < self.height and 0 <= col < self.width:
                    line.append((row, col))
                    row += dr
                    col += dc
                if len(line) < 3:
                    continue
                values = [graph.nodes[cell]["color"] for cell in line]
                for color in sorted(set(values)):
                    if color == background_color:
                        continue
                    indices = [index for index, value in enumerate(values) if value == color]
                    if len(indices) < 2:
                        continue
                    for left_index, right_index in zip(indices, indices[1:]):
                        if right_index == left_index + 1:
                            continue
                        between = list(range(left_index + 1, right_index))
                        between_values = [values[index] for index in between]
                        if not between_values or any(value == background_color for value in between_values):
                            continue
                        if all(value == color for value in between_values):
                            continue
                        left_component = cell_component.get(line[left_index])
                        right_component = cell_component.get(line[right_index])
                        if left_component is None or right_component is None:
                            continue
                        add_merge(left_component, right_component, {
                            "relation": "mixed_color_occlusion",
                            "direction": direction_name,
                            "visible_color": int(color),
                            "visible_cells": [list(line[left_index]), list(line[right_index])],
                            "occlusion_cells": [
                                {
                                    "cell": list(line[index]),
                                    "color": int(values[index]),
                                }
                                for index in between
                            ],
                        })

        occg = nx.DiGraph()
        for component_group in connected_components(merge_graph):
            sub_nodes: list[tuple[int, int]] = []
            source_component_ids = sorted(component_group)
            for component_id in source_component_ids:
                sub_nodes.extend(component_cells[component_id])
            sub_nodes = sorted(sub_nodes)
            sub_node_colors = [graph.nodes[node]["color"] for node in sub_nodes]
            group_edges: list[dict[str, object]] = []
            for left, right in combinations(source_component_ids, 2):
                group_edges.extend(occlusion_edges.get(tuple(sorted((left, right))), []))
            node_id = self.arc_graph.generate_node_id(occg, sub_nodes)
            occg.add_node(
                node_id,
                nodes=sub_nodes,
                color=sub_node_colors,
                colors=sorted(set(sub_node_colors)),
                size=len(sub_nodes),
                source_component_count=len(source_component_ids),
                source_component_colors=sorted({
                    component_color[component_id]
                    for component_id in source_component_ids
                }),
                occlusion_hypothesis=bool(group_edges),
                occlusion_edges=group_edges,
            )

        converted = self.convert(graph, occg, background_color=background_color)
        converted.graph["background_hypothesis_id"] = hypothesis_id
        converted.graph["canvas_color"] = background_color
        return ARCGraph(converted, self.name, self, "occg")

    # ------------------------------------------------------------------ 8-connected abstractions
    # The abstractions above take their components in the pixel graph (nx.grid_2d_graph), where a pixel's neighbours
    # are the four that share a side.  Each 8-connected variant below runs the same abstraction over the pixel graph
    # with the diagonal neighbours added, so a component also continues through a corner (a diagonal stroke is one
    # node, not one node per pixel).  Background binding, node attributes and edges (convert) are the base
    # abstraction's; only connectedness differs.  Which connectedness describes a task is left to the search (and to
    # description length in the round-7 perception), not fixed here.
    eight_connected_bases = {
        "nbccg8": "nbccg",
        "ccgbr8": "ccgbr",
        "ccgbr28": "ccgbr2",
        "ccgbcr8": "ccgbcr",
        "ncccg8": "ncccg",
        "ccg8": "ccg",
        "mcccg8": "mcccg",
        "occg8": "occg",
    }

    def get_eight_connected_pixel_graph(self, graph=None):
        """Return the pixel graph with diagonal neighbours added (same nodes and colours)."""
        if not graph:
            graph = self.graph
        eight_connected = graph.copy()
        for row, col in list(graph.nodes()):
            for d_row, d_col in ((1, 1), (1, -1)):
                neighbour = (row + d_row, col + d_col)
                if neighbour in graph:
                    eight_connected.add_edge((row, col), neighbour)
        return eight_connected

    def _eight_connected_abstraction(self, abstraction, graph=None):
        base = self.eight_connected_bases[abstraction]
        base_graph = getattr(self, Image.abstraction_ops[base])(self.get_eight_connected_pixel_graph(graph))
        return ARCGraph(base_graph.graph, self.name, self, abstraction)

    def get_non_black_components_graph_8(self, graph=None):
        """nbccg with 8-connected components."""
        return self._eight_connected_abstraction("nbccg8", graph)

    def get_connected_components_graph_background_removed_8(self, graph=None):
        """ccgbr with 8-connected components."""
        return self._eight_connected_abstraction("ccgbr8", graph)

    def get_connected_components_graph_background_removed_2_8(self, graph=None):
        """ccgbr2 with 8-connected components."""
        return self._eight_connected_abstraction("ccgbr28", graph)

    def get_connected_components_graph_corner_edge_removed_8(self, graph=None):
        """ccgbcr with 8-connected components."""
        return self._eight_connected_abstraction("ccgbcr8", graph)

    def get_no_color_connected_components_graph_8(self, graph=None):
        """ncccg with 8-connected components: every colour, components joined through corners."""
        return self._eight_connected_abstraction("ncccg8", graph)

    def get_connected_components_graph_8(self, graph=None):
        """ccg with 8-connected components."""
        return self._eight_connected_abstraction("ccg8", graph)

    def get_multicolor_connected_components_graph_8(self, graph=None):
        """mcccg with 8-connected components."""
        return self._eight_connected_abstraction("mcccg8", graph)

    def get_occlusion_connected_components_graph_8(self, graph=None):
        """occg with 8-connected monochrome components before the occlusion merge."""
        return self._eight_connected_abstraction("occg8", graph)

    def get_no_abstraction_graph(self, graph=None):
        """
        return an abstracted graph where a node is defined as:
        the entire graph as one multi-color node.
        """
        if not graph:
            graph = self.graph

        no_abs_graph = nx.DiGraph()
        sub_nodes = []
        sub_nodes_color = []
        for node, data in graph.nodes(data=True):
            sub_nodes.append(node)
            sub_nodes_color.append(graph.nodes[node]["color"])
        node_id = self.arc_graph.generate_node_id(no_abs_graph, sub_nodes)
        no_abs_graph.add_node(node_id, nodes=sub_nodes, color=sub_nodes_color, size=len(sub_nodes))

        return ARCGraph(no_abs_graph, self.name, self, "na") # no_abs_graph represents the image

    # undo abstraction
    def undo_abstraction(self, arc_graph):
        return arc_graph.undo_abstraction() # delegate to wrapper ARCGraph
    
    
    def convert(
        self,
        graph: nx.grid_2d_graph,
        connected_components_graph: nx.DiGraph,
        polarity: str = None,
        background_color=_UNSET_BACKGROUND,
    ):
        if background_color is _UNSET_BACKGROUND:
            background_color = self.background_color
        # add edges between the abstracted nodes
        for node_1, node_2 in combinations(connected_components_graph.nodes, 2): # pairwise combinations
            nodes_1 = connected_components_graph.nodes[node_1]["nodes"]
            nodes_2 = connected_components_graph.nodes[node_2]["nodes"]
            centroid_direction = ARCGraph.get_centroid_direction_from_pixels(
                nodes_1,
                nodes_2,
                connected_components_graph.nodes[node_1].get("color"),
                connected_components_graph.nodes[node_2].get("color"),
                background_color,
            )
            for item in product(nodes_1,nodes_2):
                n1 = item[0]
                n2 = item[1]
                if n1 == n2: # it is the same pixel
                    continue 
                if n1[0] == n2[0] and polarity != "horizontal":  # two pixels on the same row
                    for column_index in range(min(n1[1], n2[1]) + 1, max(n1[1], n2[1])):
                        if graph.nodes[n1[0], column_index]["color"] != background_color:
                            break   # first non-background pixel
                    else:
                        edge_direction = centroid_direction
                        if edge_direction is None:
                            edge_direction = "w" if n1[1] > n2[1] else "e"
                        if n1[1] > n2[1]:
                            ARCGraph.add_edge_safe(connected_components_graph, node_1, node_2, direction=edge_direction)
                        elif n2[1] > n1[1]:
                            ARCGraph.add_edge_safe(connected_components_graph, node_1, node_2, direction=edge_direction)
                        else:
                            ARCGraph.add_edge_safe(connected_components_graph, node_1, node_2, direction="h")
                        break       # only one edge between two nodes        
                elif n1[1] == n2[1] and polarity != "vertical":  # two pixels on the same column:
                    for row_index in range(min(n1[0], n2[0]) + 1, max(n1[0], n2[0])):
                        if graph.nodes[row_index, n1[1]]["color"] != background_color:
                            break
                    else:
                        edge_direction = centroid_direction
                        if edge_direction is None:
                            edge_direction = "n" if n1[0] > n2[0] else "s"
                        if n1[0] > n2[0]:
                            ARCGraph.add_edge_safe(connected_components_graph, node_1, node_2, direction=edge_direction)
                        elif n2[0] > n1[0]:
                            ARCGraph.add_edge_safe(connected_components_graph, node_1, node_2, direction=edge_direction) 
                        else:        
                            ARCGraph.add_edge_safe(connected_components_graph, node_1, node_2, direction="v")
                        break  # only one edge between two nodes
        return connected_components_graph


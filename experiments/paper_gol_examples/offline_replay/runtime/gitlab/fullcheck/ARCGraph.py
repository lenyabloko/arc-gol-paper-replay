import copy
import numpy as np
import networkx as nx
try:
    import matplotlib.pyplot as plt
except ImportError:  # plotting is optional for headless Dream/connector analysis
    plt = None

from tqdm import tqdm
from colorama import Fore, Style
from itertools import combinations, product
from collections import deque
from typing import Optional, List
from copy import deepcopy

from utils import *
from dsl_classifier_migration import expand_classifier_params

from extended_transformations.crop_grid import crop_grid_based
from extended_transformations.extract_grid import extract_grid_based
from extended_transformations.connect_grid import connect_grid_based
from extended_transformations.magnet_grid import magnet_grid_based
from extended_transformations.overlay_grid import overlay_grid_based
from extended_transformations.upscale_grid import upscale_grid_based
from extended_transformations.rotate_grid import rotate_grid_based
from extended_transformations.mirror_grid import mirror_grid_based
from extended_transformations.symmetry_grid import symmetry_grid_based
from extended_transformations.placement_grid import placement_grid_based
from extended_transformations.basic_grid import basic_grid_based
from extended_transformations.neighborhood_grid import neighborhood_grid_based
from extended_transformations.count_grid import count_grid_based
from extended_transformations.summary_grid import summary_grid_based
from extended_transformations.tile_grid import tile_grid_based
from extended_transformations.pyramid_grid import pyramid_grid_based
from extended_transformations.fill_grid import fill_grid_based
from extended_transformations.beam_grid import beam_grid_based
from extended_transformations.squeeze_grid import squeeze_grid_based
from extended_transformations.recolor_grid import recolor_grid_based
from extended_transformations.shift_grid import shift_grid_based
from extended_transformations.truncate_grid import truncate_grid_based
from extended_transformations.downscale_grid import downscale_grid_based
from extended_transformations.rotate_duplicate import rotate_duplicate_grid_based
from extended_transformations.arbitrary_duplicate_grid import arbitrary_duplicate_grid_based
from ontology.runtime_registry import (
    expand_runtime_iri,
    execution_policy,
    root_abstraction_contract,
    semantic_prior,
    thaw,
)
from ontology.background_canvas import select_abstraction_background_from_image

def swap_with_zero(grid):
    color = next(cell for row in grid for cell in row if cell != 0)
    return [[0 if cell == color else color for cell in row] for row in grid]

def count_unique_colors_except_zero(grid):
    """Count the number of unique colors in the grid, excluding 0."""
    unique_colors = set()
    for row in grid:
        for color in row:
            if color != 0:
                unique_colors.add(color)
    return len(unique_colors)

def count_most_frequent_color_except_zero(grid):
    color_count = {}
    for row in grid:
        for color in row:
            if color != 0:
                color_count[color] = color_count.get(color, 0) + 1
    return color_count


class ARCGraph:
    colors = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00", "#AAAAAA",
              "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
    img_dir = "images"
    max_nodes_to_update = execution_policy("arc_graph.max_nodes_to_update")
    insertion_transformation_ops = semantic_prior("arc_graph.insertion_transformation_ops")
    whole_graph_transformation_ops = semantic_prior("arc_graph.whole_graph_transformation_ops")
    dynamic_transformation_allowlist = semantic_prior("arc_graph.dynamic_transformation_allowlist")
    filter_ops = semantic_prior("arc_graph.filter_ops")
    param_binding_ops = semantic_prior("arc_graph.param_binding_ops")
    transformation_ops = semantic_prior("arc_graph.transformation_ops")
    dynamic_parameters = frozenset(semantic_prior("arc_graph.dynamic_parameters"))
    direction_from = {
        key: Direction[value]
        for key, value in semantic_prior("arc_graph.direction_from").items()
    }
    direction_to = {
        key: Direction[value]
        for key, value in semantic_prior("arc_graph.direction_to").items()
    }
    point_map = {
        key: ImagePoints[value]
        for key, value in semantic_prior("arc_graph.point_map").items()
    }
    shape_maps = {}
    
    def __init__(self, graph, name, image, abstraction=None):
        #self.transformation_ops["na"] = [] # reset dynamic operations
        #self.transformation_ops["ccg"]= [] # reset dynamic operations
        self.graph = graph
        self.image = image
        self.abstraction = abstraction
        contract = root_abstraction_contract("arcgraph_scene_construction")
        if not contract.wake_authorized:
            raise ValueError("ARCGraph root abstraction is not wake-authorized")
        self.root_abstraction_contract_id = contract.contract_id
        self.root_abstraction_contract_iri = expand_runtime_iri(contract.ontology_iri)
        self.graph.graph["root_arcgraph_contract_id"] = contract.contract_id
        self.graph.graph["root_arcgraph_contract_iri"] = self.root_abstraction_contract_iri
        image_scene_metadata = getattr(getattr(image, "graph", None), "graph", {})
        for key, value in image_scene_metadata.items():
            if (
                key in contract.required_scene_binding_fields
                or key.startswith("scene_decomposition_")
                or key in {
                    "ontology_binding_iris",
                    "abstract_scene_composition",
                }
            ):
                self.graph.graph.setdefault(key, copy.deepcopy(value))
        missing = [
            field
            for field in contract.required_scene_binding_fields
            if field not in self.graph.graph
        ]
        if missing:
            raise ValueError(
                "ARCGraph construction lacks ontology-bound AbstractScene fields: "
                + ", ".join(missing)
            )
        self.bind_root_scene_contract(self.graph.graph)
        self.transformation_ops = thaw(type(self).transformation_ops)
        self.shape_maps = {}
        if abstraction is None:
            self.name = name
        elif abstraction in name.split("_"):
            self.name = name
        else:
            self.name = name + "_" + abstraction
            
        if self.abstraction in image.multicolor_abstractions:
            self.is_multicolor = True
            self.most_common_color = 0
            self.least_common_color = 0
        else:
            self.is_multicolor = False
            self.most_common_color = image.most_common_color
            self.least_common_color = image.least_common_color
        
        self.used_colors = []
        self.object_size = []
        self.object_dim = []
        self.object_degree = []
        self.object_shape = []
        self.objects_for_insertion = [] # moved from Task

        for node, data in self.graph.nodes(data=True):
            if "nodes" in data:
                self.refresh_node_dimensions(node)

        self.task_id = self.name.split("_")[0]
        self.save_dir = self.img_dir + "/" + self.task_id

    def bind_root_scene_contract(self, metadata):
        """Shadow the Brain scene contract on this concrete ARCGraph wrapper."""

        keys = (
            "scene_decomposition_rule_id",
            "scene_decomposition_rule_ontology_iri",
            "scene_decomposition_profile_id",
            "scene_decomposition_profile_iri",
            "scene_decomposition_connector_chain_id",
            "background_hypothesis_id",
            "canvas_support_hypothesis_id",
            "ontology_binding_iris",
            "abstract_scene_composition",
        )
        self.brain_scene_contract = {
            key: copy.deepcopy(metadata[key]) for key in keys if key in metadata
        }
        self.graph.graph.update(self.brain_scene_contract)

    def cooperative_stop_requested(self):
        task = getattr(self.image, "task", None)
        if task is None:
            return False
        if getattr(task, "stop_search", False):
            return True
        check_time_limit = getattr(task, "check_time_limit", None)
        if callable(check_time_limit):
            return bool(check_time_limit())
        return False

    def abort_if_stop_requested(self, context="operation"):
        if self.cooperative_stop_requested():
            raise TimeoutError(f"{self.name} stopped during {context}")
    
    def is_directed(self):
        return True

    def abstraction_background_color(self):
        if "canvas_color" in self.graph.graph:
            return self.graph.graph["canvas_color"]
        return select_abstraction_background_from_image(self.abstraction, self.image)

    def has_colors(self):
        if len(self.used_colors) > 0:
            return self.used_colors
        for node in self.graph.nodes():
            color = self.graph.nodes[node]["color"]
            if isinstance(color, list): # if 'na' or multicolor abstraction, color is a list of colors
                for c in color:
                    if c not in self.used_colors:
                        self.used_colors.append(c)
            else:            
                if color not in self.used_colors:
                    self.used_colors.append(color)
        return self.used_colors
    
    def object_sizes(self):
        if len(self.object_size) > 0:
            return self.object_size
        for node in self.graph.nodes():
            size = self.graph.nodes[node]["size"]
            if size not in self.object_size:
                self.object_size.append(size)
        return self.object_size

    def object_dims(self):
        if len(self.object_dim) > 0:
            return self.object_dim
        for node in self.graph.nodes():
            dim = self.graph.nodes[node].get("dim")
            if dim is None and "nodes" in self.graph.nodes[node]:
                dim = self.refresh_node_dimensions(node)
            if dim is not None and dim not in self.object_dim:
                self.object_dim.append(dim)
        return self.object_dim

    @staticmethod
    def max_consecutive_run(values):
        if len(values) == 0:
            return 0
        sorted_values = sorted(set(values))
        max_run = 1
        current_run = 1
        for previous, current in zip(sorted_values, sorted_values[1:]):
            if current == previous + 1:
                current_run += 1
            else:
                max_run = max(max_run, current_run)
                current_run = 1
        return max(max_run, current_run)

    @classmethod
    def get_node_dimensions(cls, pixels):
        if len(pixels) == 0:
            return (0, 0)
        by_column = {}
        by_row = {}
        for y, x in pixels:
            by_column.setdefault(x, []).append(y)
            by_row.setdefault(y, []).append(x)
        height = max(cls.max_consecutive_run(rows) for rows in by_column.values())
        width = max(cls.max_consecutive_run(cols) for cols in by_row.values())
        return (height, width)

    def refresh_node_dimensions(self, node):
        dim = self.get_node_dimensions(self.graph.nodes[node].get("nodes", []))
        self.graph.nodes[node]["dim"] = dim
        self.object_dim = []
        return dim

    @staticmethod
    def direction_delta(direction: Direction):
        delta_x = 0
        delta_y = 0
        if direction == Direction.UP or direction == Direction.UP_LEFT or direction == Direction.UP_RIGHT:
            delta_y = -1
        elif direction == Direction.DOWN or direction == Direction.DOWN_LEFT or direction == Direction.DOWN_RIGHT:
            delta_y = 1
        if direction == Direction.LEFT or direction == Direction.UP_LEFT or direction == Direction.DOWN_LEFT:
            delta_x = -1
        elif direction == Direction.RIGHT or direction == Direction.UP_RIGHT or direction == Direction.DOWN_RIGHT:
            delta_x = 1
        return delta_y, delta_x

    def object_shapes(self):
        if len(self.object_shape) > 0:
            return self.object_shape
        for node in self.graph.nodes():
            shape = self.get_shape(node)
            if shape != frozenset({(0, 0)}) and shape not in self.object_shape:
                self.object_shape.append(shape)
        return self.object_shape

    
    def object_degrees(self):
        if len(self.object_degree) > 0:
            return self.object_degree
        for node in self.graph.nodes():
            degree = self.graph.degree[node]
            if degree not in self.object_degree:
                self.object_degree.append(degree)
        return self.object_degree

    def get_transformations(self):
        return list(dict.fromkeys(self.transformation_ops[self.abstraction]))

    def ensure_transformation_op(self, abstraction, transformation):
        if abstraction not in self.transformation_ops:
            raise ValueError(f"Unknown abstraction '{abstraction}' for dynamic transformation '{transformation}'")
        if transformation in self.transformation_ops[abstraction]:
            return True
        if transformation in self.whole_graph_transformation_ops and abstraction != "na":
            raise ValueError(
                f"Whole-graph transformation '{transformation}' is not allowed for abstraction '{abstraction}'"
            )
        if transformation not in self.dynamic_transformation_allowlist.get(abstraction, set()):
            raise ValueError(
                f"Dynamic transformation '{transformation}' is not allowed for abstraction '{abstraction}'"
            )
        self.transformation_ops[abstraction].append(transformation)
        return True

    def find_common_reachable_hubs(self):
        descendants = {}
        for node in self.graph.nodes():
            descendants[node] = nx.descendants(self.graph, node)
        return descendants
    
    def identify_hubs(self, descendants, threshold):
        hubs = []
        for node, desc in descendants.items():
            for des in desc: 
                des_color = self.graph.nodes[des]["color"]
                node_color = self.graph.nodes[node]["color"]
                if len(hubs) > 0:
                    hub_color = self.graph.nodes[hubs[0]]["color"]
                    if hub_color != des_color: # wrong descendant
                        continue                
                if  des_color != node_color and len(des) >= threshold:
                    hubs.append(node)
        return hubs
        
    def find_common_reachable_nodes(self, hubs, descendants): # or ancestors (see below)
        common_reachable = {}
        for i in range(len(hubs)):
            for j in range(i + 1, len(hubs)):
                hub1 = hubs[i]
                hub2 = hubs[j]
                common_reachable[(hub1, hub2)] = descendants[hub1] & descendants[hub2]
        return common_reachable

    def find_common_ancestors(self):
        descendants = self.find_common_reachable_hubs()
        hubs = self.identify_hubs(descendants, 2) # at least two decendants to qualify as hub
        common_reachable = self.find_common_reachable_nodes(hubs, descendants)
        return common_reachable
    
    def find_common_descendants(self):
        ancestors = self.find_ancestors()
        sinks = self.identify_hubs(ancestors, 2) # at least two ancestors to qualify as hub
        return sinks
    
    def find_ancestors(self):
        ancestors = {}
        for node in self.graph.nodes():
            ancestors[node] = nx.ancestors(self.graph, node)
        return ancestors
    
    # ------------------------------------- filters ------------------------------------------
    #  filters take the form of filter(node, params), return true if node satisfies filter
    def filter_by_target(self, node, target, exclude: bool = False):
        """
        return true if node is in the graph.
        if exclude, return true if node is not in the graph.
        """
        # Stored JSON calls deserialize tuple-like targets as lists.
        # Normalize to tuple so direct replay matches in-memory solver calls.
        if isinstance(target, list):
            target = tuple(target)
        if not exclude:
            return target == node
        else:
            return target not in self.graph.nodes()
    
    def filter_by_color(self, node, color: int, exclude: bool = False):
        """
        return true if node has given color.
        if exclude is true, return true if node does not have given color.
        """
        if color == "most":
            color = self.most_common_color
        elif color == "least":
            color = self.least_common_color

        if self.is_multicolor:
            if not exclude:
                return self.graph.nodes[node]["color"] == color # for 'na' self.graph.nodes[node]["color"] is array
            else:
                return self.graph.nodes[node]["color"] != color
        else:
            if not exclude:
                return self.graph.nodes[node]["color"] == color
            else:
                return self.graph.nodes[node]["color"] != color

    def filter_by_size(self, node, size, exclude: bool = False):
        """
        return true if node has size equal to given size.
        if exclude, return true if node does not have size equal to given size.
        """
        if size == "max":
            size = self.get_attribute_max("size")
        elif size == "min":
            size = self.get_attribute_min("size")

        if size == "odd" and not exclude:
            return self.graph.nodes[node]["size"] % 2 != 0
        elif size == "odd" and exclude:
            return self.graph.nodes[node]["size"] % 2 == 0
        elif not exclude:
            return self.graph.nodes[node]["size"] == size
        elif exclude:
            return self.graph.nodes[node]["size"] != size

    def filter_by_color_component_count(self, node, count, exclude: bool = False):
        """
        Return true based on how many abstract nodes share this node's color.

        `count="multiple"` selects colors split into at least two components;
        `count="single"` selects colors represented by exactly one component.
        """
        node_color = self.graph.nodes[node]["color"]
        same_color_count = sum(
            1
            for other_node in self.graph.nodes()
            if self.graph.nodes[other_node]["color"] == node_color
        )
        if count == "multiple":
            result = same_color_count > 1
        elif count == "single":
            result = same_color_count == 1
        else:
            result = same_color_count == count
        return not result if exclude else result

    def filter_by_degree(self, node, degree, exclude: bool = False):
        """
        return true if node has degree equal to given degree.
        if exclude, return true if node does not have degree equal to given degree.
        """
        if not exclude:
            return self.graph.degree[node] == degree
        else:
            return self.graph.degree[node] != degree

    def filter_by_shape(self, node, shape, exclude: bool = False):
        """
        return true if node has shape equal to given shape.
        if exclude, return true if node does not have shape equal to given shape.
        """
        if not exclude:
            return self.get_shape(node) == shape
        else:
            return self.get_shape(node) != shape

    def filter_by_fit(
        self,
        node,
        source_shape=None,
        target_shape=None,
        cavity_color=None,
        min_surrounding_sides=3,
        facing=None,
        shape_transform=None,
        min_contact_count=None,
        max_axis_gap=None,
        alignment=None,
        exclude: bool = False,
    ):
        """
        Return true when the node's shape can fit an empty partly surrounded
        target footprint in this graph.  When ``facing`` is ``toward_source``,
        the target footprint must have an open side toward the source node.
        """
        result = self.node_shape_fits_cavity(
            node,
            source_shape=source_shape,
            target_shape=target_shape,
            cavity_color=cavity_color,
            min_surrounding_sides=min_surrounding_sides,
            facing=facing,
            shape_transform=shape_transform,
            min_contact_count=min_contact_count,
            max_axis_gap=max_axis_gap,
            alignment=alignment,
        )
        return not result if exclude else result

    def filter_by_occlusion(self, node, occluded: bool = True, exclude: bool = False):
        """
        Return true when a component covers/encloses at least one non-component
        cell inside its bounding box.

        This is a component-level occlusion discriminator: a looped or covered
        object has an interior region that cannot reach the bbox boundary
        without crossing the component.
        """
        pixels = set(self.graph.nodes[node].get("nodes", []))
        if not pixels:
            has_occlusion = False
        else:
            rows = [row for row, _ in pixels]
            cols = [col for _, col in pixels]
            min_row, max_row = min(rows), max(rows)
            min_col, max_col = min(cols), max(cols)
            free = {
                (row, col)
                for row in range(min_row, max_row + 1)
                for col in range(min_col, max_col + 1)
                if (row, col) not in pixels
            }
            seen = set()
            has_occlusion = False
            for cell in free:
                if cell in seen:
                    continue
                stack = [cell]
                seen.add(cell)
                touches_boundary = False
                while stack:
                    row, col = stack.pop()
                    if row in (min_row, max_row) or col in (min_col, max_col):
                        touches_boundary = True
                    for next_row, next_col in (
                        (row - 1, col),
                        (row + 1, col),
                        (row, col - 1),
                        (row, col + 1),
                    ):
                        if (next_row, next_col) in free and (next_row, next_col) not in seen:
                            seen.add((next_row, next_col))
                            stack.append((next_row, next_col))
                if not touches_boundary:
                    has_occlusion = True
                    break

        result = has_occlusion == occluded
        return not result if exclude else result

    def filter_by_neighbor_size(self, node, size, exclude: bool = False):
        """
        return true if node has a neighbor of a given size.
        if exclude is true, return true if node does not have a neighbor of a given size.
        """
        if size == "max":
            size = self.get_attribute_max("size")
        elif size == "min":
            size = self.get_attribute_min("size")

        for neighbor in self.graph.neighbors(node):
            if size == "odd" and not exclude:
                if self.graph.nodes[neighbor]["size"] % 2 != 0:
                    return True
            elif size == "odd" and exclude:
                if self.graph.nodes[neighbor]["size"] % 2 == 0:
                    return True
            elif not exclude:
                if self.graph.nodes[neighbor]["size"] == size:
                    return True
            elif exclude:
                if self.graph.nodes[neighbor]["size"] != size:
                    return True
        return False

    def filter_by_neighbor_color(self, node, color, exclude: bool = False):
        """
        return true if node has a neighbor of a given color.
        if exclude, return true if node does not have a neighbor of a given color.
        """
        if color == "same":
            color = self.graph.nodes[node]["color"]
        elif color == "most":
            color = self.most_common_color
        elif color == "least":
            color = self.least_common_color

        for neighbor in self.graph.neighbors(node):
            if not exclude:
                if self.graph.nodes[neighbor]["color"] == color:
                    return True
            elif exclude:
                if self.graph.nodes[neighbor]["color"] != color:
                    return True
        return False

    def filter_by_neighbor_degree(self, node, degree, exclude: bool = False):
        """
        return true if node has a neighbor of a given degree.
        if exclude, return true if node does not have a neighbor of a given degree.
        """
        for neighbor in self.graph.neighbors(node):
            if not exclude:
                if self.graph.degree[neighbor] == degree:
                    return True
            else:
                if self.graph.degree[neighbor] != degree:
                    return True
        return False

    # --------------------------------- parameter binding functions ------------------------------------------
    # parameter binding takes the form of param_binding(node, params),
    # return node2 if rel(node, node2) and filter(node2, params). ex. neighbor of node with color blue

    def param_bind_neighbor_by_color(self, node, color, exclude: bool = False):
        """
        return the neighbor of node satisfying given color filter
        """
        for neighbor in self.graph.neighbors(node):
            if self.filter_by_color(neighbor, color, exclude):
                return neighbor
        return None

    def param_bind_neighbor_by_size(self, node, size, exclude: bool = False):
        """
        return the neighbor of node satisfying given size filter
        """
        for neighbor in self.graph.neighbors(node):
            if self.filter_by_size(neighbor, size, exclude):
                return neighbor
        return None

    def param_bind_node_by_size(self, node, size, exclude: bool = False): # node required for universal signature
        """
        return first node satisfying given size filter
        """
        for n in self.graph.nodes():
            if self.filter_by_size(n, size, exclude):
                return n
        return None

    def param_bind_node_by_color(self, node, color, exclude: bool = False):
        """
        return first node satisfying given color filter
        """
        for n in self.graph.nodes():
            if n == node:
                continue
            if self.filter_by_color(n, color, exclude):
                return n
        return None

    def param_bind_other_node_same_color(self, node):
        """Return the nearest other component with the same color as `node`."""
        source_color = self.graph.nodes[node]["color"]
        source_center = self.get_centroid_from_pixels(
            self.graph.nodes[node].get("nodes", [node])
        )
        candidates = []
        for other_node in self.graph.nodes():
            if other_node == node:
                continue
            if self.graph.nodes[other_node]["color"] != source_color:
                continue
            target_center = self.get_centroid_from_pixels(
                self.graph.nodes[other_node].get("nodes", [other_node])
            )
            distance = (
                (target_center[0] - source_center[0]) ** 2
                + (target_center[1] - source_center[1]) ** 2
            )
            candidates.append((distance, other_node))
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])[1]

    def param_bind_aligned_node_by_color(self, node, color, exclude: bool = False):
        """
        Return the nearest other node sharing a row or column and satisfying a
        color predicate. This supports relational parameters such as "use the
        color of the aligned marker" without hard-coding task-specific colors.
        """
        if node not in self.graph.nodes():
            return None

        source_pixels = self.graph.nodes[node].get("nodes", [])
        if not source_pixels:
            return None
        source_rows = {row for row, _ in source_pixels}
        source_cols = {col for _, col in source_pixels}
        source_center = self.get_centroid_from_pixels(source_pixels)

        candidates = []
        for candidate in self.graph.nodes():
            if candidate == node:
                continue
            if not self.filter_by_color(candidate, color, exclude):
                continue
            candidate_pixels = self.graph.nodes[candidate].get("nodes", [])
            if not candidate_pixels:
                continue
            aligned = any(row in source_rows for row, _ in candidate_pixels) or any(
                col in source_cols for _, col in candidate_pixels
            )
            if not aligned:
                continue
            candidate_center = self.get_centroid_from_pixels(candidate_pixels)
            distance = abs(candidate_center[0] - source_center[0]) + abs(
                candidate_center[1] - source_center[1]
            )
            candidates.append((distance, candidate))

        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])[1]

    def param_bind_neighbor_by_degree(self, node, degree, exclude: bool = False):
        """
        return the neighbor of node satisfying given degree filter
        """
        for neighbor in self.graph.neighbors(node):
            if self.filter_by_degree(neighbor, degree, exclude):
                return neighbor
        return None

    def param_bind_node_by_shape(self, node):
        """
        return any other node in the graph with the same shape as node
        """
        target_shape = self.get_shape(node)
        for param_bind_node in self.graph.nodes:
            if param_bind_node != node:
                candidate_shape = self.get_shape(param_bind_node)
                if candidate_shape == target_shape:
                    return param_bind_node
        return None

    # ------------------------------------------ graph operations ------------------------------------------
    def update_color(self, node, color):
        """
        update node color to given color
        """
        if color == "most":
            color = self.most_common_color
        elif color == "least":
            color = self.least_common_color
        self.graph.nodes[node]["color"] = color
        return self

    def move_node(self, node, direction: Direction, steps: int = 1):
        """
        move node by a fixed number of pixels in a given direction
        """
        assert direction is not None
        if not isinstance(steps, (int, np.integer)):
            raise ValueError(f"move_node steps must be an integer, got {steps!r}")
        steps = int(steps)

        updated_sub_nodes = []
        delta_y, delta_x = self.direction_delta(direction)
        for sub_node in self.graph.nodes[node]["nodes"]:
            updated_sub_nodes.append((sub_node[0] + delta_y * steps, sub_node[1] + delta_x * steps))
        self.graph.nodes[node]["nodes"] = updated_sub_nodes

        return self

    def extend_node(self, node, direction: Direction, overlap: bool = False):
        """
        extend node in a given direction,
        if overlap is true, extend node even if it overlaps with another node
        if overlap is false, stop extending before it overlaps with another node
        """
        assert direction is not None

        updated_sub_nodes = []
        delta_y, delta_x = self.direction_delta(direction)
        for sub_node in self.graph.nodes[node]["nodes"]:
            sub_node_y = sub_node[0]
            sub_node_x = sub_node[1]
            max_allowed = 1000
            for foo in range(max_allowed):
                updated_sub_nodes.append((sub_node_y, sub_node_x))
                sub_node_y += delta_y
                sub_node_x += delta_x
                if overlap and not self.check_inbound((sub_node_y, sub_node_x)):
                    # if overlap allowed, stop extending node until hitting edge of image
                    break
                elif not overlap and (self.check_collision(node, [(sub_node_y, sub_node_x)])
                                      or not self.check_inbound((sub_node_y, sub_node_x))):
                    # if overlap not allowed, stop extending node until hitting edge of image or another node
                    break
        self.graph.nodes[node]["nodes"] = list(set(updated_sub_nodes))
        self.graph.nodes[node]["size"] = len(updated_sub_nodes)
        if overlap:
            self.graph.nodes[node]["z_order"] = max(
                [data.get("z_order", 0) for _, data in self.graph.nodes(data=True)],
                default=0,
            ) + 1

        return self

    def move_node_max(self, node, direction: Direction):
        """
        move node in a given direction until it hits another node or the edge of the image
        """
        assert direction is not None

        delta_x = 0
        delta_y = 0
        if direction == Direction.UP or direction == Direction.UP_LEFT or direction == Direction.UP_RIGHT:
            delta_y = -1
        elif direction == Direction.DOWN or direction == Direction.DOWN_LEFT or direction == Direction.DOWN_RIGHT:
            delta_y = 1
        if direction == Direction.LEFT or direction == Direction.UP_LEFT or direction == Direction.DOWN_LEFT:
            delta_x = -1
        elif direction == Direction.RIGHT or direction == Direction.UP_RIGHT or direction == Direction.DOWN_RIGHT:
            delta_x = 1
        max_allowed = 1000
        for foo in range(max_allowed):
            updated_nodes = []
            for sub_node in self.graph.nodes[node]["nodes"]:
                updated_nodes.append((sub_node[0] + delta_y, sub_node[1] + delta_x))
            if self.check_collision(node, updated_nodes) or not self.check_inbound(updated_nodes):
                break
            self.graph.nodes[node]["nodes"] = updated_nodes

        return self

    def rotate_node(self, node, rotation_dir: Rotation):
        """
        rotates node around its center point in a given rotational direction
        """
        rotate_times = 1
        if rotation_dir == Rotation.CW:
            mul = -1
        elif rotation_dir == Rotation.CCW:
            mul = 1
        elif rotation_dir == Rotation.CW2:
            rotate_times = 2
            mul = -1

        for t in range(rotate_times):
            center_point = (sum([n[0] for n in self.graph.nodes[node]["nodes"]]) // self.graph.nodes[node]["size"],
                            sum([n[1] for n in self.graph.nodes[node]["nodes"]]) // self.graph.nodes[node]["size"])
            new_nodes = []
            for sub_node in self.graph.nodes[node]["nodes"]:
                new_sub_node = (sub_node[0] - center_point[0], sub_node[1] - center_point[1])
                new_sub_node = (- new_sub_node[1] * mul, new_sub_node[0] * mul)
                new_sub_node = (new_sub_node[0] + center_point[0], new_sub_node[1] + center_point[1])
                new_nodes.append(new_sub_node)
            self.graph.nodes[node]["nodes"] = new_nodes
        return self

    def rotate_mask(self, nodes, rotation_dir: Rotation):
        """
        rotates node around its center point in a given rotational direction
        """
        rotate_times = 1
        if rotation_dir == Rotation.CW:
            mul = -1
        elif rotation_dir == Rotation.CCW:
            mul = 1
        elif rotation_dir == Rotation.CW2:
            rotate_times = 2
            mul = -1

        for t in range(rotate_times):
            center_point = (sum([n[0] for n in nodes]) // len(nodes),
                            sum([n[1] for n in nodes]) // len(nodes))
            new_nodes = []
            for sub_node in nodes:
                new_sub_node = (sub_node[0] - center_point[0], sub_node[1] - center_point[1])
                new_sub_node = (- new_sub_node[1] * mul, new_sub_node[0] * mul)
                new_sub_node = (new_sub_node[0] + center_point[0], new_sub_node[1] + center_point[1])
                new_nodes.append(new_sub_node)
        return new_nodes


    @staticmethod
    def border_offsets(border_type=None):
        if border_type in (None, "full", "all", "moore"):
            return [
                (dy, dx)
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
                if not (dy == 0 and dx == 0)
            ]
        if border_type in ("corner", "corners", "corner_anchors", "diagonal", "diagonal_corners"):
            return [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        if border_type in ("edge", "edges", "edge_anchors", "orthogonal", "cardinal"):
            return [(-1, 0), (0, -1), (0, 1), (1, 0)]
        raise ValueError(f"Unsupported border_type {border_type!r}")

    def add_border(self, node, border_color, border_type=None):
        """
        add a border with thickness 1 and border_color around the given node
        """
        border_pixels = self.get_border_pixels(node, border_type)
                    
        if len(border_pixels) == 0:
            node_id = self.get_node_id(node)
            raise ValueError("Can not add border size 0 pixels color {} to node {}".format(border_color,node_id))
        
        new_node_id = self.generate_node_id(self.graph, list(border_pixels))            
        if self.is_multicolor:
            self.graph.add_node(new_node_id, nodes=list(border_pixels), color=[border_color for j in border_pixels],
                                size=len(border_pixels))
        else:
            self.graph.add_node(new_node_id, nodes=list(border_pixels), color=border_color, size=len(border_pixels))
        return self

    def get_border_pixels(self, node, border_type=None):
        border_pixels = []
        sub_nodes = self.graph.nodes[node]["nodes"]
        for sub_node in sub_nodes:
            for y, x in self.border_offsets(border_type):
                border_pixel = (sub_node[0] + y, sub_node[1] + x)
                if border_type is not None:
                    if not (0 <= border_pixel[0] < self.image.height and 0 <= border_pixel[1] < self.image.width):
                        continue
                if border_pixel not in border_pixels and not self.check_pixel_occupied(border_pixel):
                    border_pixels.append(border_pixel)
        return border_pixels

    def can_add_border(self, node, border_type=None):
        return len(self.get_border_pixels(node, border_type)) > 0

    def fill_rectangle(self, node, fill_color, overlap: bool):
        """
        fill the rectangle containing the given node with the given color.
        if overlap is True, fill the rectangle even if it overlaps with other nodes.
        """

        if fill_color == "same":
            fill_color = self.graph.nodes[node]["color"]

        all_x = [sub_node[1] for sub_node in self.graph.nodes[node]["nodes"]]
        all_y = [sub_node[0] for sub_node in self.graph.nodes[node]["nodes"]]
        min_x, min_y, max_x, max_y = min(all_x), min(all_y), max(all_x), max(all_y)
        unfilled_pixels = []
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                pixel = (y, x)
                if pixel not in self.graph.nodes[node]["nodes"]:
                    if overlap:
                        unfilled_pixels.append(pixel)
                    elif not self.check_pixel_occupied(pixel):
                        unfilled_pixels.append(pixel)
        if len(unfilled_pixels) > 0:
            new_node_id = self.generate_node_id(self.graph, list(unfilled_pixels))
            if self.is_multicolor:
                self.graph.add_node(new_node_id, nodes=list(unfilled_pixels),
                                    color=[fill_color for j in unfilled_pixels], size=len(unfilled_pixels))
            else:
                self.graph.add_node(new_node_id, nodes=list(unfilled_pixels), color=fill_color,
                                    size=len(unfilled_pixels))
        return self

    def hollow_rectangle(self, node, fill_color):
        """
        hollowing the rectangle containing the given node with the given color.
        """

        all_y = [n[0] for n in self.graph.nodes[node]["nodes"]]
        all_x = [n[1] for n in self.graph.nodes[node]["nodes"]]
        border_y = [min(all_y), max(all_y)]
        border_x = [min(all_x), max(all_x)]
        non_border_pixels = []
        new_subnodes = []
        for subnode in self.graph.nodes[node]["nodes"]:
            if subnode[0] in border_y or subnode[1] in border_x:
                new_subnodes.append(subnode)
            else:
                non_border_pixels.append(subnode)
        self.graph.nodes[node]["nodes"] = new_subnodes
        if fill_color != self.image.background_color:
            new_node_id = self.generate_node_id(self.graph, list(non_border_pixels))
            self.graph.add_node(new_node_id, nodes=list(non_border_pixels), color=fill_color,
                                size=len(non_border_pixels))
        return self

    def mirror(self, node, mirror_axis):
        """
        mirroring a node with respect to the given axis.
        mirror_axis takes the form of (y, x) where one of y, x equals None to
        indicate the other being the axis of mirroring
        """
        if mirror_axis[1] is None and mirror_axis[0] is not None:
            axis = mirror_axis[0]
            new_subnodes = []
            for subnode in self.graph.nodes[node]["nodes"]:
                new_y = axis - (subnode[0] - axis)
                new_x = subnode[1]
                new_subnodes.append((new_y, new_x))
            if not self.check_collision(node, new_subnodes):
                self.graph.nodes[node]["nodes"] = new_subnodes
        elif mirror_axis[0] is None and mirror_axis[1] is not None:
            axis = mirror_axis[1]
            new_subnodes = []
            for subnode in self.graph.nodes[node]["nodes"]:
                new_y = subnode[0]
                new_x = axis - (subnode[1] - axis)
                new_subnodes.append((new_y, new_x))
            if not self.check_collision(node, new_subnodes):
                self.graph.nodes[node]["nodes"] = new_subnodes
        return self

    def flip(self, node, mirror_direction: Mirror):
        """
        flips the given node given direction horizontal, vertical, diagonal left/right
        """
        if mirror_direction == Mirror.VERTICAL:
            max_y = max([subnode[0] for subnode in self.graph.nodes[node]["nodes"]])
            min_y = min([subnode[0] for subnode in self.graph.nodes[node]["nodes"]])
            new_subnodes = []
            for subnode in self.graph.nodes[node]["nodes"]:
                new_y = max_y - (subnode[0] - min_y)
                new_x = subnode[1]
                new_subnodes.append((new_y, new_x))
            if not self.check_collision(node, new_subnodes):
                self.graph.nodes[node]["nodes"] = new_subnodes
        elif mirror_direction == Mirror.HORIZONTAL:
            max_x = max([subnode[1] for subnode in self.graph.nodes[node]["nodes"]])
            min_x = min([subnode[1] for subnode in self.graph.nodes[node]["nodes"]])
            new_subnodes = []
            for subnode in self.graph.nodes[node]["nodes"]:
                new_y = subnode[0]
                new_x = max_x - (subnode[1] - min_x)
                new_subnodes.append((new_y, new_x))
            if not self.check_collision(node, new_subnodes):
                self.graph.nodes[node]["nodes"] = new_subnodes
        elif mirror_direction == Mirror.DIAGONAL_LEFT:  # \
            min_x = min([subnode[1] for subnode in self.graph.nodes[node]["nodes"]])
            min_y = min([subnode[0] for subnode in self.graph.nodes[node]["nodes"]])
            new_subnodes = []
            for subnode in self.graph.nodes[node]["nodes"]:
                new_subnode = (subnode[0] - min_y, subnode[1] - min_x)
                new_subnode = (new_subnode[1], new_subnode[0])
                new_subnode = (new_subnode[0] + min_y, new_subnode[1] + min_x)
                new_subnodes.append(new_subnode)
            if not self.check_collision(node, new_subnodes):
                self.graph.nodes[node]["nodes"] = new_subnodes
        elif mirror_direction == Mirror.DIAGONAL_RIGHT:  # /
            max_x = max([subnode[1] for subnode in self.graph.nodes[node]["nodes"]])
            min_y = min([subnode[0] for subnode in self.graph.nodes[node]["nodes"]])
            new_subnodes = []
            for subnode in self.graph.nodes[node]["nodes"]:
                new_subnode = (subnode[0] - min_y, subnode[1] - max_x)
                new_subnode = (- new_subnode[1], - new_subnode[0])
                new_subnode = (new_subnode[0] + min_y, new_subnode[1] + max_x)
                new_subnodes.append(new_subnode)
            if not self.check_collision(node, new_subnodes):
                self.graph.nodes[node]["nodes"] = new_subnodes
        return self

    def insert(self, node, object_index, point, relative_pos: RelativePosition):
        """
        insert some pattern identified by object_index at some location,
        the location is defined as, the relative position between the given node and point.
        for example, point=top, relative_pos=middle will insert the pattern between the given node
        and the top of the image.
        if object_index is -1, use the pattern given by node
        """
        #parent_centroid = self.get_centroid(node) # (row,col) center point of the parent node
        parent_pixels = self.graph.nodes[node]["nodes"] # pixels of the parent node
        parent_pixel_set = set(parent_pixels)
        parent_centroid = self.get_centroid_from_pixels(parent_pixels)
        if isinstance(point, tuple):
            reference = point
        elif point == ImagePoints.TOP:
            reference = (0, parent_centroid[1])   # (0,col) center point at the top edge of image
        elif point == ImagePoints.BOTTOM:
            reference = (self.image.height - 1, parent_centroid[1]) # assuming the entire image!!!
        elif point == ImagePoints.LEFT:
            reference = (parent_centroid[0], 0)   # (row,0) center point at the left edge of image
        elif point == ImagePoints.RIGHT:
            reference = (parent_centroid[0], self.image.width - 1)
        elif point == ImagePoints.TOP_LEFT:
            reference = (0, 0)
        elif point == ImagePoints.TOP_RIGHT:
            reference = (0, self.image.width - 1)
        elif point == ImagePoints.BOTTOM_LEFT:
            reference = (self.image.height - 1, 0)
        elif point == ImagePoints.BOTTOM_RIGHT:
            reference = (self.image.height - 1, self.image.width - 1)
        else:
            raise ValueError(f"Unsupported insert point: {point}")

        if object_index == -1:
            # special id for dynamic objects, which uses the given target nodes as objects
            insert_object = self.graph.nodes[node] # ex. [{'nodes': [...], 'color': 2, 'size': 6}]
        else:
            if object_index < 0 or object_index >= len(self.objects_for_insertion):
                raise ValueError(f"Invalid insertion object_index {object_index}")
            insert_object = self.objects_for_insertion[object_index]
        child_pixels = insert_object["nodes"]
        child_centroid = self.get_centroid_from_pixels(child_pixels) # center of new object on output image
        
        dest_point = self.get_point_from_relative_pos(parent_centroid, reference, relative_pos) # proposed destination

        def translated_pixels(anchor):
            offset_y = int(round(anchor[0] - child_centroid[0]))
            offset_x = int(round(anchor[1] - child_centroid[1]))
            return [
                (int(round(child_pixel[0] + offset_y)), int(round(child_pixel[1] + offset_x)))
                for child_pixel in child_pixels
            ]

        inserted_pixels = translated_pixels(dest_point)
        # SOURCE insertions are overlays: the source node stays whole underneath.
        if relative_pos != RelativePosition.SOURCE:
            max_shifts = self.image.height + self.image.width + len(child_pixels)
            for _ in range(max_shifts):
                colliding_pixels = [pixel for pixel in inserted_pixels if pixel in parent_pixel_set]
                if not colliding_pixels:
                    break
                child_coords = colliding_pixels[0]
                if child_coords[0] > reference[0]: # destination row below reference row
                    dest_point = (dest_point[0] - 1, dest_point[1]) # shift up
                elif child_coords[0] < reference[0]: # destination row above reference row
                    dest_point = (dest_point[0] + 1, dest_point[1]) # shift down
                if child_coords[1] > reference[1]: # destination col right of reference col
                    dest_point = (dest_point[0], dest_point[1] - 1) # shift left
                elif child_coords[1] < reference[1]: # destination col left of reference col
                    dest_point = (dest_point[0], dest_point[1] + 1)  # shift right
                inserted_pixels = translated_pixels(dest_point)
            
        new_node_id = self.generate_node_id(self.graph, list(inserted_pixels), reuse_existing=False)
        z_order = max(
            [data.get("z_order", 0) for _, data in self.graph.nodes(data=True)],
            default=0,
        ) + 1
        self.graph.add_node(
            new_node_id,
            nodes=list(inserted_pixels),
            color=insert_object["color"],
            size=len(list(inserted_pixels)),
            z_order=z_order,
            _inserted=True,
            _insert_source=node,
            _insert_source_base=self.get_base_node_id(node),
        )
        return self

    def remove_node(self, node):
        """
        remove a node from the graph
        """
        self.graph.remove_node(node)

    def refresh(self, graph, nodes:list, fraction:float=1):
        self.graph.clear()
        
        total_height = graph.image.height
        total_width = graph.image.width
        if total_height >= total_width:
            axis = 'vertical'
        else:
            axis = 'horizontal'
        
        for node in graph.graph.nodes():
            data = graph.graph.nodes[node]
            sub_nodes = data.get('nodes', [node])
            if len(sub_nodes) > self.max_nodes_to_update:
                raise ValueError(f" Too many sub_nodes to refresh: {len(sub_nodes)}'")
            sub_nodes_colors = data.get('color', [0] * len(sub_nodes))
            new_sub_nodes = []
            new_sub_nodes_colors = [] if isinstance(sub_nodes_colors, list) else sub_nodes_colors
            """
            ys = [n[0] for n in sub_nodes]
            xs = [n[1] for n in sub_nodes]
            min_y, max_y = min(ys), max(ys)
            min_x, max_x = min(xs), max(xs)
            """
            if axis == 'horizontal':
                width = int(total_width * fraction)
                portion_width = max(1, width)
                new_min_x = 0
                new_max_x = portion_width - 1
                for i, n in enumerate(sub_nodes): 
                    if new_min_x <= n[1] <= new_max_x:
                        new_sub_nodes.append(n)
                        if isinstance(sub_nodes_colors, list):
                            new_sub_nodes_colors.append(sub_nodes_colors[i])
                        else:
                            new_sub_nodes_colors = sub_nodes_colors # int    
            elif axis == 'vertical':
                height =  int(total_height * fraction)
                portion_height = max(1, height)
                new_min_y = 0
                new_max_y = portion_height - 1
                for i, n in enumerate(sub_nodes):
                    if new_min_y <= n[0] <= new_max_y:
                        new_sub_nodes.append(n)
                        if isinstance(sub_nodes_colors,list):
                            new_sub_nodes_colors.append(sub_nodes_colors[i])
                        else:
                            new_sub_nodes_colors = sub_nodes_colors # int
            else:
                raise ValueError(f" Invalid axis {axis}. Must be 'horizontal' or 'vertical'.")

            self.graph.add_node(node)
            self.graph.nodes[node]['nodes'] = new_sub_nodes
            self.graph.nodes[node]['color'] = new_sub_nodes_colors
            self.graph.nodes[node]['size'] = len(new_sub_nodes)
        self.image = graph.image

    def validate_pixel_budget(self, rows:int, cols:int, transformation_name:str="transformation"):
        max_allowed_pixels = getattr(self.image, "max_allowd_pixels", self.max_nodes_to_update)
        if rows <= 0 or cols <= 0:
            raise ValueError(
                f"{Fore.RED}{transformation_name} produced invalid grid size [{cols}x{rows}]{Style.RESET_ALL}"
            )
        total_pixels = rows * cols
        if total_pixels > max_allowed_pixels:
            raise ValueError(
                f"{Fore.RED}{transformation_name} exceeds allowed pixels {max_allowed_pixels}: "
                f"[{cols}x{rows}] = {total_pixels}{Style.RESET_ALL}"
            )

    def validate_grid_pixel_budget(self, grid:list, transformation_name:str="transformation"):
        rows = len(grid)
        cols = len(grid[0]) if rows > 0 else 0
        self.validate_pixel_budget(rows, cols, transformation_name)

    #-------------------------------------- extended ---------------------------------------
    def magnet(self, node, magnet_type="dynamic", shifting_direction="dynamic",
               color1=0, color2=0, 
               #color3=0, color4=0,
               grid_size=0
               ):
        grid = self.graph_to_grid()
        transformed_grid = magnet_grid_based(grid, magnet_type, shifting_direction, color1, color2, grid_size)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self
    
    def fill(self, node, object, color, color1, classifier_params=None):
        grid = self.graph_to_grid()
        transformed_grid = fill_grid_based(grid, object, color, color1, classifier_params=classifier_params)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self
    
    def truncate(self, node, color1, color2, grid_size, truncate_type, mirror):
        grid = self.graph_to_grid()
        transformed_grid = truncate_grid_based(grid, color1, color2, grid_size, truncate_type, mirror)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self

    def shift(self, node, color1):
        grid = self.graph_to_grid()
        transformed_grid = shift_grid_based(grid, color1)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self
    
    def recolor(self, node, recolor_type, color1, color2, shifting_direction, classifier_params=None):
        grid = self.graph_to_grid()
        transformed_grid = recolor_grid_based(
            grid,
            recolor_type,
            color1,
            color2,
            shifting_direction,
            classifier_params=classifier_params,
        )
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self

    def upscale_grid(self, node, factor, mirror, upscale_type, color, border_color, fill_color, classifier_params=None):
        grid = self.graph_to_grid()
        transformed_grid = upscale_grid_based(
            grid,
            factor,
            mirror,
            upscale_type,
            color,
            border_color,
            fill_color,
            classifier_params=classifier_params,
        )
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node]) # reset self with abstract graph.iamge and nodes
        return self

    def downscale_grid(self, node, factor=2, downscale_type="pixel_based", background_color=0):
        grid = self.graph_to_grid()
        transformed_grid = downscale_grid_based(grid, factor, downscale_type, background_color)
        abstract_graph = self.image.get_abstract_graph(
            transformed_grid,
            self.image.graph_from_grid(transformed_grid),
            self.abstraction,
        )
        self.refresh(abstract_graph, [node])
        return self

    def rotate_grid(self, node, degrees):
        grid = self.graph_to_grid()
        transformed_grid = rotate_grid_based(grid, degrees)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self

    def mirror_grid(self, node, mirror_axis="diagonal", mirror_type="color", color1:int=0, color2:int=0):
        grid = self.graph_to_grid()
        transformed_grid = mirror_grid_based(grid, mirror_axis, mirror_type, color1, color2)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self

    def symmetry_grid(
        self,
        node,
        source_color=None,
        fill_color=None,
        symmetry_type="rot90_missing_orbit",
        center_mode="best",
        background_color=0,
        mirror_axis="DIAGONAL_LEFT",
        duplicate_mode="infer_rows_cols",
        occluder_color=None,
        occluder_colors=None,
        period_mode="minimal_2d",
        max_period=12,
        pattern_type="visible_period_shift",
        unknown_mode="auto_single",
        out_shift_row=0,
        out_shift_col=1,
        direction="up_right",
        output_scale=2,
        output_height=0,
        output_width=0,
        selector_mode="nonzero",
        selector_color=None,
        tile_source="grid",
    ):
        grid = self.graph_to_grid()
        transformed_grid = symmetry_grid_based(
            grid,
            source_color,
            fill_color,
            symmetry_type,
            center_mode,
            background_color,
            mirror_axis,
            duplicate_mode,
            occluder_color,
            occluder_colors,
            period_mode,
            max_period,
            pattern_type,
            unknown_mode,
            out_shift_row,
            out_shift_col,
            direction,
            output_scale,
            output_height,
            output_width,
            selector_mode,
            selector_color,
            tile_source,
        )
        abstract_graph = self.image.get_abstract_graph(
            transformed_grid,
            self.image.graph_from_grid(transformed_grid),
            self.abstraction,
        )
        self.refresh(abstract_graph, [node])
        return self

    def placement_grid(
        self,
        node,
        placement_type="center_object_in_frame",
        object_color=2,
        guide_color=3,
        separator_color=8,
        background_color=0,
    ):
        grid = self.graph_to_grid()
        transformed_grid = placement_grid_based(
            grid,
            placement_type=placement_type,
            object_color=object_color,
            guide_color=guide_color,
            separator_color=separator_color,
            background_color=background_color,
        )
        abstract_graph = self.image.get_abstract_graph(
            transformed_grid,
            self.image.graph_from_grid(transformed_grid),
            self.abstraction,
        )
        self.refresh(abstract_graph, [node])
        return self

    def neighborhood_grid(
        self,
        node,
        neighborhood_type="diagonal_quadrant_neighbors",
        object_color=2,
        background_color=0,
        color1=3,
        color2=6,
        color3=8,
        color4=7,
        classifier_params=None,
    ):
        grid = self.graph_to_grid()
        transformed_grid = neighborhood_grid_based(
            grid,
            neighborhood_type=neighborhood_type,
            object_color=object_color,
            background_color=background_color,
            color1=color1,
            color2=color2,
            color3=color3,
            color4=color4,
            classifier_params=classifier_params,
        )
        abstract_graph = self.image.get_abstract_graph(
            transformed_grid,
            self.image.graph_from_grid(transformed_grid),
            self.abstraction,
        )
        self.refresh(abstract_graph, [node])
        return self

    def count_grid(
        self,
        node,
        count_type="foreground_count_prefix",
        background_color=0,
        output_color=2,
    ):
        grid = self.graph_to_grid()
        transformed_grid = count_grid_based(
            grid,
            count_type=count_type,
            background_color=background_color,
            output_color=output_color,
        )
        abstract_graph = self.image.get_abstract_graph(
            transformed_grid,
            self.image.graph_from_grid(transformed_grid),
            self.abstraction,
        )
        self.refresh(abstract_graph, [node])
        return self

    def summary_grid(
        self,
        node,
        summary_type="component_color_size_desc",
        background_color=0,
        output_width=1,
        output_color=1,
        color1=7,
        classifier_params=None,
    ):
        return self.tile_grid(
            node,
            tile_type=summary_type,
            background_color=background_color,
            output_width=output_width,
            output_color=output_color,
            color1=color1,
            classifier_params=classifier_params,
        )

    summary_tile_types = frozenset(semantic_prior("arc_graph.summary_tile_types"))

    def tile_grid(
        self,
        node,
        tile_type="horizontal_mirror_vertical_palindrome",
        background_color=0,
        fill_color=None,
        output_width=1,
        output_color=1,
        color1=7,
        classifier_params=None,
    ):
        grid = self.graph_to_grid()
        if tile_type in self.summary_tile_types:
            transformed_grid = summary_grid_based(
                grid,
                summary_type=tile_type,
                background_color=background_color,
                output_width=output_width,
                output_color=output_color,
                color1=color1,
                classifier_params=classifier_params,
            )
        else:
            transformed_grid = tile_grid_based(
                grid,
                tile_type=tile_type,
                background_color=background_color,
                fill_color=fill_color,
                classifier_params=classifier_params,
            )
        abstract_graph = self.image.get_abstract_graph(
            transformed_grid,
            self.image.graph_from_grid(transformed_grid),
            self.abstraction,
        )
        self.refresh(abstract_graph, [node])
        return self

    def pyramid_grid(
        self,
        node,
        pattern_type="horizontal_run_triangles",
        base_color=2,
        upper_color=3,
        lower_color=1,
        background_color=0,
    ):
        grid = self.graph_to_grid()
        transformed_grid = pyramid_grid_based(
            grid,
            pattern_type=pattern_type,
            base_color=base_color,
            upper_color=upper_color,
            lower_color=lower_color,
            background_color=background_color,
        )
        abstract_graph = self.image.get_abstract_graph(
            transformed_grid,
            self.image.graph_from_grid(transformed_grid),
            self.abstraction,
        )
        self.refresh(abstract_graph, [node])
        return self

    def basic_grid(
        self,
        node,
        transform_type="crop_non_background_bbox",
        background_color=0,
        factor=2,
        degrees=90,
        mirror_axis="horizontal",
        component_mode="same_color",
        selection="size_max",
        output_mode="subgrid",
        crop_height=1,
        crop_width=1,
        corner="left upper",
        height_divisor=1,
        width_divisor=2,
        split_mode="zero_separator",
        pattern_mode="mask",
        marker_color=5,
        padding_rows=0,
        padding_cols=0,
        frequency_mode="most",
        require_full_extent=True,
        require_isolated=False,
    ):
        grid = self.graph_to_grid()
        transformed_grid = basic_grid_based(
            grid,
            transform_type=transform_type,
            background_color=background_color,
            factor=factor,
            degrees=degrees,
            mirror_axis=mirror_axis,
            component_mode=component_mode,
            selection=selection,
            output_mode=output_mode,
            crop_height=crop_height,
            crop_width=crop_width,
            corner=corner,
            height_divisor=height_divisor,
            width_divisor=width_divisor,
            split_mode=split_mode,
            pattern_mode=pattern_mode,
            marker_color=marker_color,
            padding_rows=padding_rows,
            padding_cols=padding_cols,
            frequency_mode=frequency_mode,
            require_full_extent=require_full_extent,
            require_isolated=require_isolated,
        )
        abstract_graph = self.image.get_abstract_graph(
            transformed_grid,
            self.image.graph_from_grid(transformed_grid),
            self.abstraction,
        )
        self.refresh(abstract_graph, [node])
        return self

    def connect(self, node, connect_mode: str, color: int, fill_color: int, border_color:int, inherit_vertical:bool):
        grid = self.graph_to_grid()
        transformed_grid = connect_grid_based(grid, connect_mode, color, fill_color, border_color, inherit_vertical)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self

    def _scalar_node_color(self, node):
        color = self.graph.nodes[node].get("color")
        if isinstance(color, list):
            unique = list(dict.fromkeys(color))
            return unique[0] if len(unique) == 1 else None
        return color

    def _node_bbox(self, node):
        pixels = list(self.graph.nodes[node].get("nodes", []))
        if not pixels:
            return None
        rows = [row for row, _ in pixels]
        cols = [col for _, col in pixels]
        return min(rows), max(rows), min(cols), max(cols)

    def _node_is_solid_rectangle(self, node):
        bbox = self._node_bbox(node)
        if bbox is None:
            return False
        min_row, max_row, min_col, max_col = bbox
        height = max_row - min_row + 1
        width = max_col - min_col + 1
        if height < 2 or width < 2:
            return False
        pixels = set(self.graph.nodes[node].get("nodes", []))
        return len(pixels) == height * width

    def _largest_unique_solid_rectangle_node(self, excluded_node=None):
        background_color = self._background_color_for_connector()
        candidates = []
        for candidate, data in self.graph.nodes(data=True):
            if candidate == excluded_node:
                continue
            if self._scalar_node_color(candidate) == background_color:
                continue
            if not self._node_is_solid_rectangle(candidate):
                continue
            candidates.append((int(data.get("size", 0)), candidate))
        if not candidates:
            return None
        candidates.sort(reverse=True, key=lambda item: item[0])
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            return None
        return candidates[0][1]

    def _background_color_for_connector(self):
        # Component abstractions may carry Image.background_color=0 even when
        # the actual substrate is another dominant color.  Connector spans are
        # defined over the writable substrate, so prefer the graph's observed
        # dominant color.
        return self.most_common_color

    def _pixel_is_background_or_empty(self, pixel, background_color):
        occupied = False
        for node, data in self.graph.nodes(data=True):
            if pixel not in data.get("nodes", []):
                continue
            occupied = True
            if self._scalar_node_color(node) != background_color:
                return False
        return True if occupied else True

    def _connector_path_is_clear(self, path, background_color):
        for pixel in path:
            if not self.check_inbound(pixel):
                return False
            if not self._pixel_is_background_or_empty(pixel, background_color):
                return False
        return True

    def _aligned_point_to_rectangle_corridor(self, point, rectangle_node, background_color):
        bbox = self._node_bbox(rectangle_node)
        if bbox is None:
            return []
        row, col = point
        min_row, max_row, min_col, max_col = bbox
        candidate_paths = []
        if min_row <= row <= max_row:
            if col < min_col:
                candidate_paths.append([(row, c) for c in range(col + 1, min_col)])
            elif col > max_col:
                candidate_paths.append([(row, c) for c in range(max_col + 1, col)])
        if min_col <= col <= max_col:
            if row < min_row:
                candidate_paths.append([(r, col) for r in range(row + 1, min_row)])
            elif row > max_row:
                candidate_paths.append([(r, col) for r in range(max_row + 1, row)])

        clear_paths = [
            path
            for path in candidate_paths
            if path and self._connector_path_is_clear(path, background_color)
        ]
        if not clear_paths:
            return []
        return min(clear_paths, key=len)

    def _aligned_point_to_point_corridor(self, source, target, background_color):
        src_row, src_col = source
        dst_row, dst_col = target
        path = []
        if src_row == dst_row:
            step = 1 if dst_col > src_col else -1
            path = [(src_row, col) for col in range(src_col + step, dst_col, step)]
        elif src_col == dst_col:
            step = 1 if dst_row > src_row else -1
            path = [(row, src_col) for row in range(src_row + step, dst_row, step)]
        elif abs(dst_row - src_row) == abs(dst_col - src_col):
            row_step = 1 if dst_row > src_row else -1
            col_step = 1 if dst_col > src_col else -1
            length = abs(dst_row - src_row)
            path = [
                (src_row + row_step * offset, src_col + col_step * offset)
                for offset in range(1, length)
            ]
        if path and self._connector_path_is_clear(path, background_color):
            return path
        return []

    def connect_aligned_nodes_pixels(self, node, connector_type="marker_to_largest_rectangle"):
        """Return background pixels for a bounded component-level connector.

        This is deliberately relation-gated. It does not enumerate arbitrary
        whole-grid connection modes; it only exposes connector spans inferred
        from already-reified component nodes.
        """
        if node not in self.graph.nodes:
            return []
        connector_type = connector_type or "marker_to_largest_rectangle"
        source_color = self._scalar_node_color(node)
        if source_color is None:
            return []
        background_color = self._background_color_for_connector()
        if source_color == background_color:
            return []

        source_pixels = list(self.graph.nodes[node].get("nodes", []))
        if not source_pixels:
            return []

        connector_pixels = []
        if connector_type == "marker_to_largest_rectangle":
            rectangle_node = self._largest_unique_solid_rectangle_node(excluded_node=node)
            if rectangle_node is None:
                return []
            if self._scalar_node_color(rectangle_node) == source_color:
                return []
            for pixel in source_pixels:
                connector_pixels.extend(
                    self._aligned_point_to_rectangle_corridor(
                        pixel,
                        rectangle_node,
                        background_color,
                    )
                )
        elif connector_type == "same_color_marker_pair":
            for other_node in self.graph.nodes:
                if other_node == node:
                    continue
                if self._scalar_node_color(other_node) != source_color:
                    continue
                for source_pixel in source_pixels:
                    for target_pixel in self.graph.nodes[other_node].get("nodes", []):
                        connector_pixels.extend(
                            self._aligned_point_to_point_corridor(
                                source_pixel,
                                target_pixel,
                                background_color,
                            )
                        )
        else:
            return []

        seen = set()
        clean_pixels = []
        for pixel in connector_pixels:
            if pixel in seen:
                continue
            seen.add(pixel)
            if not self._pixel_is_background_or_empty(pixel, background_color):
                continue
            clean_pixels.append(pixel)
        return clean_pixels

    def connect_aligned_nodes(self, node, connector_type="marker_to_largest_rectangle"):
        connector_pixels = self.connect_aligned_nodes_pixels(node, connector_type)
        if not connector_pixels:
            return self
        source_color = self._scalar_node_color(node)
        if source_color is None:
            return self
        new_node_id = self.generate_node_id(self.graph, list(connector_pixels))
        if new_node_id in self.graph.nodes:
            return self
        z_order = max(
            [data.get("z_order", 0) for _, data in self.graph.nodes(data=True)],
            default=0,
        ) + 1
        self.graph.add_node(
            new_node_id,
            nodes=list(connector_pixels),
            color=source_color,
            size=len(connector_pixels),
            z_order=z_order,
        )
        return self
    
    def crop(self, node, 
             corner: str = "right upper", 
             crop_type: str = "corner_based", 
             grid_size: int = 3,
             fill_color:int = 0, 
             border_color:int=0, 
             fill_direction:str = "left_to_right", 
             connect_all:bool=True):
        grid = self.graph_to_grid()
        transformed_grid = crop_grid_based(grid, corner, crop_type, grid_size, fill_color, border_color, fill_direction, connect_all)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self        

    def extract(
        self,
        node,
        fill_color: int = 0,
        crop_filterless: bool = False,
        fraction: float = 1,
        extract_type: str = "fill_color_bbox",
    ):
        grid = self.graph_to_grid()
        if extract_type == "node_bbox":
            pixels = self.graph.nodes[node].get("nodes", [node])
            if not pixels:
                raise ValueError("extract(node_bbox) received an empty node")
            rows = [row for row, _ in pixels]
            cols = [col for _, col in pixels]
            min_row, max_row = min(rows), max(rows)
            min_col, max_col = min(cols), max(cols)
            transformed_grid = [
                row[min_col : max_col + 1]
                for row in grid[min_row : max_row + 1]
            ]
        else:
            transformed_grid = extract_grid_based(grid, fill_color, extract_type=extract_type)#, crop_filterless, fraction)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])#, fraction) 
        return self

    def overlay(
        self,
        node,
        fold: str = "marker_components",
        overlay: str = "align_marker",
        marker_color: int = 5,
        separator_color: int = 5,
        background_color: int = 0,
        connectivity: int = 8,
        output_color=None,
        split_axis: str = "auto",
    ):
        grid = self.graph_to_grid()
        transformed_grid = overlay_grid_based(
            grid,
            fold=fold,
            overlay=overlay,
            marker_color=marker_color,
            separator_color=separator_color,
            background_color=background_color,
            connectivity=connectivity,
            output_color=output_color,
            split_axis=split_axis,
        )
        abstract_graph = self.image.get_abstract_graph(
            transformed_grid,
            self.image.graph_from_grid(transformed_grid),
            self.abstraction,
        )
        self.refresh(abstract_graph, [node])
        return self

    def beam(self, node, color1=0, color2=0, beam_type:str="color_inheritance", classifier_params=None):
        grid = self.graph_to_grid()
        transformed_grid = beam_grid_based(
            grid,
            color1,
            color2,
            beam_type,
            classifier_params=classifier_params,
        )
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self

    def squeeze(self, node, axis: str = "horizontal", keep_occluded: bool = True):
        self.abort_if_stop_requested("squeeze")
        grid = self.graph_to_grid()
        transformed_grid = squeeze_grid_based(
            grid,
            axis=axis,
            keep_occluded=keep_occluded,
            background_color=self.image.background_color,
        )
        self.abort_if_stop_requested("squeeze abstraction rebuild")
        abstract_graph = self.image.get_abstract_graph(
            transformed_grid,
            self.image.graph_from_grid(transformed_grid),
            self.abstraction,
        )
        self.refresh(abstract_graph, [node])
        return self
    
    def arbitrary_duplicate(self, node, mirror, duplicate_arbitrary, axis, mirror_grid, combine_pattern, concat_axis):
        grid = self.graph_to_grid()
        transformed_grid = arbitrary_duplicate_grid_based(grid, mirror, duplicate_arbitrary, axis, mirror_grid, combine_pattern, concat_axis)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self
    
    def rotate_duplicate(self, node, mirror, rotation_degrees):
        grid = self.graph_to_grid()
        transformed_grid = rotate_duplicate_grid_based(grid, mirror, rotation_degrees)
        abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
        self.refresh(abstract_graph, [node])
        return self

    def duplicate(self, node, axis: str ='horizontal', duplicate: int=2, color1:int=0,
                  mirror: bool=False,
                  #mirror_grid: Optional[str] = None,
                  concat_axis = "y",
                  combine_pattern: str = "grid1 + grid2",
                  duplication_type: str="grid_based",
                  #rotation_degrees: List[int]=None
                  ):
        grid = self.graph_to_grid()
        if duplication_type == "mirror_markers_inside_canvas":
            rows = len(grid)
            cols = len(grid[0]) if rows else 0
            transformed_grid = copy.deepcopy(grid)
            mirror_axes = {"both", "horizontal", "vertical"}
            if axis not in mirror_axes:
                raise ValueError(
                    f"{Fore.RED}mirror_markers_inside_canvas axis must be one of {sorted(mirror_axes)}{Style.RESET_ALL}"
                )

            for row in range(rows):
                for col in range(cols):
                    value = grid[row][col]
                    if value == color1:
                        continue
                    targets = {(row, col)}
                    if axis in {"horizontal", "both"}:
                        targets.add((rows - 1 - row, col))
                    if axis in {"vertical", "both"}:
                        targets.add((row, cols - 1 - col))
                    if axis == "both":
                        targets.add((rows - 1 - row, cols - 1 - col))
                    for target_row, target_col in targets:
                        existing = transformed_grid[target_row][target_col]
                        if existing not in (color1, value):
                            raise ValueError(
                                f"{Fore.RED}mirror_markers_inside_canvas collision at {(target_row, target_col)}{Style.RESET_ALL}"
                            )
                        transformed_grid[target_row][target_col] = value

            abstract_graph = self.image.get_abstract_graph(
                transformed_grid,
                self.image.graph_from_grid(transformed_grid),
                self.abstraction,
            )
            self.refresh(abstract_graph, [node])
            return self

        if duplication_type == "pixel_based":
            def find_objects(grid, color1):
                visited = set()
                objects = []
                rows = len(grid)
                cols = len(grid[0]) if rows > 0 else 0

                directions = [(-1, 0), (1, 0), (0, -1), (0, 1),
                            (-1, -1), (-1, 1), (1, -1), (1, 1)]

                for i in range(rows):
                    for j in range(cols):
                        if (i, j) not in visited and grid[i][j] == color1:
                            queue = deque()
                            queue.append((i, j))
                            object_cells = set()

                            while queue:
                                x, y = queue.popleft()
                                if (x, y) in visited:
                                    continue
                                if grid[x][y] == color1:
                                    visited.add((x, y))
                                    object_cells.add((x, y))
                                    for dx, dy in directions:
                                        nx, ny = x + dx, y + dy
                                        if 0 <= nx < rows and 0 <= ny < cols:
                                            if (nx, ny) not in visited and grid[nx][ny] == color1:
                                                queue.append((nx, ny))
                            if object_cells:
                                objects.append(object_cells)
                return objects

            def find_replication_pixels(grid, obj_cells):
                replication_pixels = set()
                rows = len(grid)
                cols = len(grid[0]) if rows > 0 else 0

                for i in range(rows):
                    for j in range(cols):
                        if (i, j) not in obj_cells and grid[i][j] != 0:
                            replication_pixels.add((i, j, grid[i][j]))

                return list(replication_pixels)

            def crop_object(grid, obj_cells):

                if not obj_cells:
                    return []

                min_row = min(x for x, y in obj_cells)
                max_row = max(x for x, y in obj_cells)
                min_col = min(y for x, y in obj_cells)
                max_col = max(y for x, y in obj_cells)

                cropped = []
                for i in range(min_row, max_row + 1):
                    row = []
                    for j in range(min_col, max_col + 1):
                        val = grid[i][j] if (i, j) in obj_cells else 0
                        row.append(val)
                    cropped.append(row)
                return cropped

            def replicate_object(cropped_obj, color):
                replicated_obj = [[color if val != 0 else 0 for val in row] for row in cropped_obj]
                return replicated_obj
            
            objects = find_objects(grid, color1)
            if not objects:
                raise ValueError(f"{Fore.RED}No objects found for pixel_based duplicate color {color1}{Style.RESET_ALL}")
            desired_grid = []
            obj = objects[0]
            
            replication_pixels = find_replication_pixels(grid, obj)
            if not replication_pixels:
                raise ValueError("No Replication pixels!")
            rp_rows = [rp[0] for rp in replication_pixels]
            rp_cols = [rp[1] for rp in replication_pixels]

            if concat_axis=="xy":
                if all(r == rp_rows[0] for r in rp_rows):
                    arrangement = 'horizontal'
                    replication_pixels.sort(key=lambda x: x[1])
                elif all(c == rp_cols[0] for c in rp_cols):
                    arrangement = 'vertical'
                    replication_pixels.sort(key=lambda x: x[0])
                else:
                    raise ValueError(f'{Fore.RED}Replication pixels are not arranged strictly horizontally or vertically.{Style.RESET_ALL}')
            elif concat_axis == 'y':
                arrangement = "vertical"
            elif concat_axis == "x":
                arrangement = "horizontal"
                
            cropped_obj = crop_object(grid, obj)
            obj_height = len(cropped_obj)

            replicated_objects = []
            for rp in replication_pixels:
                _, _, rp_color = rp
                if mirror:
                    replicated_obj = replicate_object(cropped_obj, rp_color)
                else:
                    replicated_obj = replicate_object(cropped_obj, color1)
                replicated_objects.append(replicated_obj)

            if arrangement == 'horizontal':
                desired_grid = [[] for _ in range(obj_height)]
                for replica in replicated_objects:
                    for i in range(obj_height):
                        desired_grid[i].extend(replica[i])
            elif arrangement == 'vertical':
                desired_grid = []
                for replica in replicated_objects:
                    desired_grid.extend(replica)
            if not mirror and len(desired_grid) != duplicate:
                zero_row = [0] * len(desired_grid[0])
                desired_grid.insert(0, zero_row)
            self.validate_grid_pixel_budget(desired_grid, "duplicate")
            abstract_graph = self.image.get_abstract_graph(desired_grid, self.image.graph_from_grid(desired_grid), self.abstraction)
            self.refresh(abstract_graph, [node])
            return self
        
        if duplication_type == "sibling_pixel":
            grid = deepcopy(grid)
            
            rows = len(grid)
            cols = len(grid[0]) if rows > 0 else 0
            
            visited = [[False for _ in range(cols)] for _ in range(rows)]
            components = []
            
            def bfs(start_r, start_c):
                q = deque()
                q.append((start_r, start_c))
                visited[start_r][start_c] = True
                component = [(start_r, start_c)]
                
                while q:
                    x, y = q.popleft()
                    for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < rows and 0 <= ny < cols:
                            if grid[nx][ny] != 0 and not visited[nx][ny]:
                                visited[nx][ny] = True
                                q.append((nx, ny))
                                component.append((nx, ny))
                return component
            
            for r in range(rows):
                for c in range(cols):
                    if grid[r][c] != 0 and not visited[r][c]:
                        comp = bfs(r, c)
                        components.append(comp)
            
            if len(components) != 2:
                raise ValueError(f"{Fore.RED}Grid does not contain exactly one object and one single pixel.{Style.RESET_ALL}")
            
            object_component = None
            single_pixel = None
            for comp in components:
                if len(comp) == 1:
                    single_pixel = comp[0]
                else:
                    object_component = comp
            
            if object_component is None or single_pixel is None:
                raise ValueError(f"{Fore.RED}Failed to identify object or single pixel.{Style.RESET_ALL}")
            
            single_r, single_c = single_pixel
            single_color = grid[single_r][single_c]
            
            matching_pixel = None
            for (r, c) in object_component:
                if grid[r][c] == single_color:
                    matching_pixel = (r, c)
                    break
            
            if matching_pixel is None:
                raise ValueError(f"{Fore.RED}No matching pixel found in the object.{Style.RESET_ALL}")
            
            obj_r, obj_c = matching_pixel
            relative_positions = []
            for (r, c) in object_component:
                dx = r - obj_r
                dy = c - obj_c
                relative_positions.append((dx, dy, grid[r][c]))
            
            single_new_r, single_new_c = single_pixel
            
            for (dx, dy, val) in relative_positions:
                new_r = single_new_r + dx
                new_c = single_new_c + dy
                if 0 <= new_r < rows and 0 <= new_c < cols:
                    grid[new_r][new_c] = val
                else:
                    pass
            
            grid[single_new_r][single_new_c] = 0
            self.validate_grid_pixel_budget(grid, "duplicate")
            abstract_graph = self.image.get_abstract_graph(grid, self.image.graph_from_grid(grid), self.abstraction)
            self.refresh(abstract_graph, [node])
            return self
        
        if duplication_type == "grid_based":
            total_rows = len(grid)
            start_index = (total_rows // 2) + (total_rows % 2)
            bottom_half = grid[start_index:]
            mirrored_bottom = bottom_half[::-1]
            transformed_grid = mirrored_bottom + bottom_half
            self.validate_grid_pixel_budget(transformed_grid, "duplicate")
            abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
            self.refresh(abstract_graph, [node])
            return self
                
        if duplication_type == "top_bottom_duplication":
            def mirror_grid(grid, axis=None):
                if axis == 'horizontal':
                    return grid[::-1]
                elif axis == 'vertical':
                    return [row[::-1] for row in grid]
                elif axis == 'both':
                    return [row[::-1] for row in grid[::-1]]
                else:
                    return grid
            def hconcat(grid1, grid2):
                return [row1 + row2 for row1, row2 in zip(grid1, grid2)]
            MhO = mirror_grid(grid, axis='horizontal')
            MvO = mirror_grid(grid, axis='vertical')
            MvMhO = mirror_grid(grid, axis='both')
            top = hconcat(MvMhO, MhO)
            bottom = hconcat(MvO, grid)
            transformed_grid = top + bottom
            self.validate_grid_pixel_budget(transformed_grid, "duplicate")
            abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
            self.refresh(abstract_graph, [node])
            return self
    
        if duplication_type == "object_based":
            color_counts = {}
            for row in grid:
                for value in row:
                    color_counts[value] = color_counts.get(value, 0) + 1
            if mirror:
                most_common_color = max(color_counts, key=color_counts.get)
            else:
                most_common_color = min(color_counts, key=color_counts.get)
            horizontally_concatenated = [row + row for row in grid]
            upscale_factor = duplicate
            upscaled_grid = []
            for row in grid:
                upscaled_row = []
                for value in row:
                    upscaled_row.extend([value] * upscale_factor)
                for _ in range(upscale_factor):
                    upscaled_grid.append(upscaled_row.copy())
            positions_with_most_common_color = set()
            for i, row in enumerate(upscaled_grid):
                for j, value in enumerate(row):
                    if value == most_common_color:
                        positions_with_most_common_color.add((i, j))
            total_rows = len(upscaled_grid)
            total_cols = len(upscaled_grid[0]) if total_rows > 0 else 0
            all_positions = set((i, j) for i in range(total_rows) for j in range(total_cols))
            positions_to_zero = all_positions - positions_with_most_common_color
            extended_horizontally = []
            for i in range(len(horizontally_concatenated)):
                if i < len(grid):
                    extended_horizontally.append(horizontally_concatenated[i] + grid[i])
                else:
                    extended_horizontally.append(horizontally_concatenated[i] + [0] * len(grid[0]))
            vertically_concatenated_stage1 = extended_horizontally + extended_horizontally
            vertically_concatenated_final = vertically_concatenated_stage1 + extended_horizontally
            
            transformed_grid = []
            for i, row in enumerate(vertically_concatenated_final):
                new_row = []
                for j, value in enumerate(row):
                    if (i, j) in positions_to_zero:
                        new_row.append(0)
                    else:
                        new_row.append(value)
                transformed_grid.append(new_row)
            self.validate_grid_pixel_budget(transformed_grid, "duplicate")
            abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
            self.refresh(abstract_graph, [node])
            return self
        
        if duplication_type == "unique_color":
            if mirror:
                unique_colors = count_unique_colors_except_zero(grid)
            else:
                unique_colors = len(grid)
        
            if concat_axis == "x":
                duplicated_grid = []
                for row in grid:
                    new_row = row * unique_colors
                    duplicated_grid.append(new_row)
            
            elif concat_axis == "y":
                duplicated_grid = grid * unique_colors
            
            elif concat_axis == "xy":
                duplicated_grid_horizontal = []
                for row in grid:
                    new_row = row * unique_colors
                    duplicated_grid_horizontal.append(new_row)
                duplicated_grid = duplicated_grid_horizontal * unique_colors
            
            else:
                raise ValueError(f"{Fore.RED}Invalid value for concat_axis. Use 'x', 'y', or 'xy'.{Style.RESET_ALL}")
            if len(duplicated_grid) == 0 or len(duplicated_grid[0]) == 0 or len(duplicated_grid) > 99:
                raise ValueError(f"{Fore.RED}Duplicated grid has invalid size: {len(duplicated_grid)}{Style.RESET_ALL}")
            self.validate_grid_pixel_budget(duplicated_grid, "duplicate")
            abstract_graph = self.image.get_abstract_graph(duplicated_grid, self.image.graph_from_grid(duplicated_grid), self.abstraction)
            self.refresh(abstract_graph, [node])
            return self

        if duplication_type == "alternating_mirror_tile":
            if not isinstance(duplicate, int) or duplicate < 2:
                raise ValueError(f"{Fore.RED}alternating_mirror_tile requires duplicate >= 2{Style.RESET_ALL}")
            if concat_axis not in {"x", "y", "xy"}:
                raise ValueError(f"{Fore.RED}alternating_mirror_tile concat_axis must be x, y, or xy{Style.RESET_ALL}")
            if axis not in {"vertical", "horizontal", "both"}:
                raise ValueError(f"{Fore.RED}alternating_mirror_tile axis must be vertical, horizontal, or both{Style.RESET_ALL}")

            def mirrored_tile(tile):
                result = [row[:] for row in tile]
                if axis in {"vertical", "both"}:
                    result = [list(reversed(row)) for row in result]
                if axis in {"horizontal", "both"}:
                    result = list(reversed(result))
                return result

            base_tile = [row[:] for row in grid]
            mirror_tile = mirrored_tile(base_tile)

            def tile_for(tile_row, tile_col):
                if not mirror:
                    return base_tile
                if concat_axis == "x":
                    return mirror_tile if tile_col % 2 else base_tile
                if concat_axis == "y":
                    return mirror_tile if tile_row % 2 else base_tile
                return mirror_tile if tile_row % 2 else base_tile

            tile_rows = duplicate if concat_axis in {"y", "xy"} else 1
            tile_cols = duplicate if concat_axis in {"x", "xy"} else 1
            transformed_grid = []
            for tile_row in range(tile_rows):
                band = [[] for _ in range(len(base_tile))]
                for tile_col in range(tile_cols):
                    tile = tile_for(tile_row, tile_col)
                    for row_index, row_values in enumerate(tile):
                        band[row_index].extend(row_values)
                transformed_grid.extend(band)

            self.validate_grid_pixel_budget(transformed_grid, "duplicate")
            abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
            self.refresh(abstract_graph, [node])
            return self
        
        if duplicate == 2:
            grid = self.graph_to_grid()
            if mirror and axis == "vertical":
                vmirrored_grid = [row[::-1] for row in grid]
                transformed_grid = [original_row + mirrored_row for original_row, mirrored_row in zip(grid, vmirrored_grid)]
            
            elif mirror and axis == "horizontal":
                hmirrored_grid = grid[::-1]
                if combine_pattern == "grid1+grid2":
                    transformed_grid = grid + hmirrored_grid
                elif combine_pattern == "grid2+grid1":
                    transformed_grid = hmirrored_grid + grid    
            
            elif not mirror and axis == "vertical":
                transformed_grid = [row + row for row in grid]
            
            elif not mirror and axis == "horizontal":
                transformed_grid = grid + grid
            
            else:
                raise ValueError(f"{Fore.RED}Invalid combination of mirror and axis parameters.{Style.RESET_ALL}")
            self.validate_grid_pixel_budget(transformed_grid, "duplicate")
            abstract_graph = self.image.get_abstract_graph(transformed_grid, self.image.graph_from_grid(transformed_grid), self.abstraction)
            self.refresh(abstract_graph, [node])
            return self

        elif duplicate == 4:
            original_nodes = list(self.graph.nodes(data=True))
            original_width = self.image.width
            original_height = self.image.height
            self.validate_pixel_budget(original_height * 2, original_width * 2, "duplicate")
            self.image.width *= 2
            self.image.height *= 2
            transforms = [
                ('original', 0, 0),
                ('h_mirror', original_width, 0),
                ('v_mirror', 0, original_height),
                ('hv_mirror', original_width, original_height),
            ]

            for transform_name, shift_x, shift_y in transforms:
                for node, data in original_nodes:
                    subnodes = data.get('nodes', [node])
                    if transform_name == 'original':
                        transformed_subnodes = subnodes
                    elif transform_name == 'h_mirror':
                        transformed_subnodes = [
                            (y, (original_width - 1) - x) for y, x in subnodes
                        ]
                    elif transform_name == 'v_mirror':
                        transformed_subnodes = [
                            ((original_height - 1) - y, x) for y, x in subnodes
                        ]
                    elif transform_name == 'hv_mirror':
                        transformed_subnodes = [
                            ((original_height - 1) - y, (original_width - 1) - x)
                            for y, x in subnodes
                        ]
                    else:
                        raise ValueError(f"{Fore.RED}Unsupported transform {transform_name}{Style.RESET_ALL}")

                    new_subnodes = [(y + shift_y, x + shift_x) for y, x in transformed_subnodes]
                    new_node_id = self.generate_node_id(self.graph, new_subnodes)
                    self.graph.add_node(
                        new_node_id,
                        nodes=new_subnodes,
                        color=data['color'],
                        size=data.get('size', len(new_subnodes))
                    )
        else:
            raise ValueError(f"{Fore.RED}Unsupported duplicate value. Supported values are 2 and 4. You provided {duplicate}{Style.RESET_ALL}")

        return self
    


    # ------------------------------------- utils ------------------------------------------
    def get_attribute_max(self, attribute_name):
        """
        get the maximum value of the given attribute
        """
        if len(list(self.graph.nodes)) == 0:
            return None
        return max([data[attribute_name] for node, data in self.graph.nodes(data=True)])

    def get_attribute_min(self, attribute_name):
        """
        get the minimum value of the given attribute
        """
        if len(list(self.graph.nodes)) == 0:
            return None
        return min([data[attribute_name] for node, data in self.graph.nodes(data=True)])

    def get_color(self, node):
        """
        return the color of the node
        """
        if isinstance(node, list):
            return [self.graph.nodes[node_i]["color"] for node_i in node]
        else:
            return self.graph.nodes[node]["color"]
        
    def get_direction_by_color(self, color, graph):
        for from_node, to_nodes in self.graph.adjacency(): # source node and the list of targets
            if len(to_nodes) == 0:
                continue # no outgoing edge from this node
            for to_node, arrow in to_nodes.items():
                if self.graph.nodes[to_node]["color"] == color: 
                    return self.direction_to[arrow["direction"]]

    def get_direction_by_shape(self, shape, graph):
        for from_node, to_nodes in self.graph.adjacency(): # source node and the list of targets
            if len(to_nodes) == 0:
                continue # no outgoing edge from this node
            for to_node, arrow in to_nodes.items():
                if self.get_shape(to_node) == shape:
                    return self.direction_to[arrow["direction"]]

    def get_direction_by_node(self, node):
        for from_node, to_nodes in self.graph.adjacency():
            for to_node, arrow in to_nodes.items():
                direction = arrow.get("direction")
                if to_node == node and direction in self.direction_to:
                    return self.direction_to[direction]
        for from_node, to_nodes in self.graph.adjacency():
            if from_node != node:
                continue
            for _, arrow in to_nodes.items():
                direction = arrow.get("direction")
                if direction in self.direction_from:
                    return self.direction_from[direction]

    def get_point_by_color(self, color):
        for edge in self.graph.edges():
            node1, node2 = edge
            if self.graph.nodes[node1]["color"] == color or self.graph.nodes[node2]["color"] == color:   
                return self.point_map[self.graph.edges[node1, node2]["direction"]]

    def get_points_by_color(self, color):
        points = []
        for edge in self.graph.edges():
            node1, node2 = edge
            if self.graph.nodes[node1]["color"] == color or self.graph.nodes[node2]["color"] == color:
                point = self.point_map[self.graph.edges[edge]["direction"]]
                if point not in points:
                    points.append(point)
        return points

    def get_points_by_size(self, size):
        points = []
        for edge in self.graph.edges():
            node1, node2 = edge
            if self.graph.nodes[node1]["size"] == size or self.graph.nodes[node2]["size"] == size:
                point = self.point_map[self.graph.edges[edge]["direction"]]
                if point not in points:
                    points.append(point)
        return points
    
    def get_points_by_degree(self, degree):
        points = []
        for edge in self.graph.edges():
            node1, node2 = edge
            if self.graph.degree[node1] == degree or self.graph.degree[node2] == degree:
                points.append(self.point_map[self.graph.edges[edge]["direction"]])
        return points
    
    def get_points_by_target(self, target_node):
        points = []
        for edge in self.graph.edges():
            node1, node2 = edge
            if node1 == target_node or node2 == target_node:
                points.append(self.point_map[self.graph.edges[edge]["direction"]])
        return [point for point in ImagePoints if point.value not in points]
    
    def get_nodes_by_shape(self, shape):
        nodes = []
        for node in self.graph.nodes():
            if self.get_shape(node) == shape:
                nodes.append(node)
        return nodes
    
    
    def get_constraints_global(self, output_graph):
        """
        find the constraints that all nodes in the example must follow
        """
        no_movements = True
        for node, data in output_graph.graph.nodes(data=True):
            input_nodes = self.graph.nodes
            if node not in input_nodes:
                continue
            if (data["color"] != self.image.background_color and input_nodes[node]["color"] == self.image.background_color) \
                or (data["color"] == self.image.background_color and input_nodes[node]["color"] != self.image.background_color):
                no_movements = False
        if no_movements:
            pruned_transformations = ["move_node", "extend_node", "move_node_max", "fill_rectangle", "add_border"]
            self.transformation_ops[self.abstraction] = [t for t in self.transformation_ops[self.abstraction] if
                                                         t not in pruned_transformations]                      
    
    def get_inserted_objects(self, output_graph):
        """
        find new objects in the output graph, including objects that occlude
        existing input objects and objects that are absent from the input graph
        """
        initial_count = len(self.objects_for_insertion)

        def color_key(color):
            return tuple(color) if isinstance(color, list) else color

        def object_key(data):
            nodes = data.get("nodes", [])
            centroid = None
            if len(nodes) > 0:
                centroid = self.get_base_node_id(self.get_centroid_from_pixels(nodes))
            return (color_key(data.get("color")), self.get_footprint(nodes), centroid)

        existing_objects = {object_key(data) for data in self.objects_for_insertion}
        input_occupied_pixels = {
            pixel
            for _, input_data in self.graph.nodes(data=True)
            if input_data.get("color") != self.image.background_color
            for pixel in input_data.get("nodes", [])
        }

        def remember_object(data):
            key = object_key(data)
            if key not in existing_objects:
                existing_objects.add(key)
                self.objects_for_insertion.append(data.copy())

        def is_insert_candidate(data):
            nodes = data.get("nodes", [])
            if len(nodes) == 0:
                return False
            color = data.get("color")
            if color == self.image.background_color or color == output_graph.image.background_color:
                return False
            if set(nodes) <= input_occupied_pixels:
                return False
            return True

        for out_node, data in output_graph.graph.nodes(data=True):
            if out_node in self.graph.nodes():
                continue
            if not is_insert_candidate(data):
                continue
            nodes = list(data.get("nodes", []))
            remember_object({
                "nodes": nodes,
                "color": data.get("color"),
                "size": data.get("size", len(nodes)),
            })

        def output_color_at(pixel):
            try:
                return output_graph.image.graph.nodes[pixel]["color"]
            except KeyError:
                return None

        def connected_pixel_components(pixels):
            remaining = set(pixels)
            components = []
            while remaining:
                start = remaining.pop()
                component = [start]
                queue = deque([start])
                while queue:
                    row, col = queue.popleft()
                    for neighbor in [
                        (row - 1, col),
                        (row + 1, col),
                        (row, col - 1),
                        (row, col + 1),
                    ]:
                        if neighbor in remaining:
                            remaining.remove(neighbor)
                            queue.append(neighbor)
                            component.append(neighbor)
                components.append(sorted(component))
            return components

        for in_node, data in self.graph.nodes(data=True):
            source_color = data.get("color")
            occluded_pixels_by_color = {}
            for index, pixel in enumerate(data.get("nodes", [])):
                if isinstance(source_color, list):
                    if index >= len(source_color):
                        continue
                    input_color = source_color[index]
                else:
                    input_color = source_color
                output_color = output_color_at(pixel)
                if output_color is None:
                    continue
                if output_color == input_color or output_color == self.image.background_color:
                    continue
                occluded_pixels_by_color.setdefault(output_color, []).append(pixel)

            for color, pixels in occluded_pixels_by_color.items():
                for component in connected_pixel_components(pixels):
                    if set(component) == set(data.get("nodes", [])):
                        continue
                    remember_object({
                        "nodes": component,
                        "color": color,
                        "size": len(component),
                    })

        if len(self.objects_for_insertion) == initial_count:
            pruned_transformations = ["insert"]
            self.transformation_ops[self.abstraction] = [t for t in self.transformation_ops[self.abstraction] if
                                                        t not in pruned_transformations]
        return self.objects_for_insertion        
            
    def check_inbound(self, pixels):
        """
        check if given pixels are all within the image boundary
        """
        if not isinstance(pixels, list):
            pixels = [pixels]
        for pixel in pixels:
            y, x = pixel
            if x < 0 or y < 0 or x >= self.image.width or y >= self.image.height:
                return False
        return True

    def check_collision(self, node_id, pixels_list=None):
        """
        check if given pixels_list collide with other nodes in the graph
        node_id is used to retrieve pixels_list if not given.
        node_id is also used so that only collision with other nodes are detected.
        """
        if pixels_list is None:
            pixels_set = set(self.graph.nodes[node_id]["nodes"])
        else:
            pixels_set = set(pixels_list)
        for node, data in self.graph.nodes(data=True):
            if len(set(data["nodes"]) & pixels_set) != 0 and node != node_id:
                return True
        return False

    def check_pixel_occupied(self, pixel):
        """
        check if a pixel is occupied by any node in the graph
        """
        for node, data in self.graph.nodes(data=True):
            if pixel in data["nodes"]:
                return True
        return False

    def copy_colors_to(self, component):
        for node, data in component.graph.nodes(data=True):
            component.graph.nodes[node]["color"] = self.graph.nodes[node]["color"]

    def get_shape(self, node):
        """
        given a node, get the shape of the node.
        the shape of the node is defined using its pixels shifted so that the top left is 0,0
        """
        sub_nodes = self.graph.nodes[node]["nodes"]
        if len(sub_nodes) == 0:
            return set()
        min_x = min([sub_node[1] for sub_node in sub_nodes])
        min_y = min([sub_node[0] for sub_node in sub_nodes])
        return frozenset([(y - min_y, x - min_x) for y, x in sub_nodes])

    def get_footprint(self, nodes):
        """
        get the fit of the object in the graph
        """
        if len(nodes) == 0:
            return []
        min_x = min([node[1] for node in nodes])
        min_y = min([node[0] for node in nodes])
        return frozenset([(y - min_y, x - min_x) for y, x in nodes])

    @staticmethod
    def normalize_shape_value(shape):
        if shape is None:
            return None
        if len(shape) == 0:
            return frozenset()
        normalized_pixels = []
        for pixel in shape:
            try:
                row, col = pixel
            except (TypeError, ValueError):
                raise ValueError(f"shape contains non-coordinate value {pixel!r}")
            if isinstance(row, bool) or isinstance(col, bool):
                raise ValueError(f"shape contains boolean coordinate {pixel!r}")
            if not isinstance(row, (int, np.integer)) or not isinstance(col, (int, np.integer)):
                raise ValueError(f"shape contains non-integer coordinate {pixel!r}")
            normalized_pixels.append((int(row), int(col)))
        min_row = min(row for row, _ in normalized_pixels)
        min_col = min(col for _, col in normalized_pixels)
        return frozenset((row - min_row, col - min_col) for row, col in normalized_pixels)

    def occupied_pixel_owner(self, pixel, excluded_node=None):
        for node, data in self.graph.nodes(data=True):
            if node == excluded_node:
                continue
            if pixel in data.get("nodes", []):
                return node
        return None

    def fit_target_pixels(self, target_shape, anchor):
        target_shape = self.normalize_shape_value(target_shape)
        if not target_shape:
            return []
        anchor_row, anchor_col = anchor
        return sorted(
            (anchor_row + row, anchor_col + col)
            for row, col in target_shape
        )

    def fit_surrounding_sides(
        self,
        target_pixels,
        excluded_node=None,
        cavity_color=None,
    ):
        return self.fit_surrounding_context(
            target_pixels,
            excluded_node=excluded_node,
            cavity_color=cavity_color,
        )[0]

    def fit_surrounding_context(
        self,
        target_pixels,
        excluded_node=None,
        cavity_color=None,
    ):
        target_set = set(target_pixels)
        sides = set()
        contact_count = 0
        for row, col in target_set:
            for side, delta_row, delta_col in [
                ("up", -1, 0),
                ("down", 1, 0),
                ("left", 0, -1),
                ("right", 0, 1),
            ]:
                neighbor = (row + delta_row, col + delta_col)
                if neighbor in target_set:
                    continue
                owner = self.occupied_pixel_owner(neighbor, excluded_node=excluded_node)
                if owner is None:
                    continue
                owner_color = self.graph.nodes[owner].get("color")
                if cavity_color is not None and owner_color != cavity_color:
                    continue
                if owner is not None:
                    sides.add(side)
                    contact_count += 1
        return sides, contact_count

    @classmethod
    def fit_shape_variants(cls, shape, shape_transform=None):
        normalized_shape = cls.normalize_shape_value(shape)
        if not normalized_shape:
            return []
        if shape_transform in (None, "", "identity", "same"):
            return [normalized_shape]
        mode = str(shape_transform).strip().lower().replace("-", "_")
        if mode not in {"d4", "dihedral", "rotate_reflect", "rotations_reflections"}:
            return [normalized_shape]

        points = list(normalized_shape)
        height = max(row for row, _ in points) + 1
        width = max(col for _, col in points) + 1
        transforms = [
            lambda row, col: (row, col),
            lambda row, col: (col, height - 1 - row),
            lambda row, col: (height - 1 - row, width - 1 - col),
            lambda row, col: (width - 1 - col, row),
            lambda row, col: (row, width - 1 - col),
            lambda row, col: (height - 1 - row, col),
            lambda row, col: (col, row),
            lambda row, col: (width - 1 - col, height - 1 - row),
        ]
        variants = []
        for transform in transforms:
            transformed = [transform(row, col) for row, col in points]
            variant = cls.normalize_shape_value(transformed)
            if variant not in variants:
                variants.append(variant)
        return variants

    @staticmethod
    def interval_gap(min_a, max_a, min_b, max_b):
        if max_a < min_b:
            return min_b - max_a
        if max_b < min_a:
            return min_a - max_b
        return 0

    @classmethod
    def fit_projected_axis_gap(cls, source_pixels, target_pixels):
        if not source_pixels or not target_pixels:
            return None
        source_rows = [row for row, _ in source_pixels]
        source_cols = [col for _, col in source_pixels]
        target_rows = [row for row, _ in target_pixels]
        target_cols = [col for _, col in target_pixels]
        source_min_row, source_max_row = min(source_rows), max(source_rows)
        source_min_col, source_max_col = min(source_cols), max(source_cols)
        target_min_row, target_max_row = min(target_rows), max(target_rows)
        target_min_col, target_max_col = min(target_cols), max(target_cols)
        if source_min_row > target_max_row or source_max_row < target_min_row:
            return cls.interval_gap(
                source_min_col,
                source_max_col,
                target_min_col,
                target_max_col,
            )
        if source_min_col > target_max_col or source_max_col < target_min_col:
            return cls.interval_gap(
                source_min_row,
                source_max_row,
                target_min_row,
                target_max_row,
            )
        return 0

    @staticmethod
    def fit_relative_directions(source_pixels, target_pixels):
        if not source_pixels or not target_pixels:
            return set()
        source_rows = [row for row, _ in source_pixels]
        source_cols = [col for _, col in source_pixels]
        target_rows = [row for row, _ in target_pixels]
        target_cols = [col for _, col in target_pixels]
        source_min_row, source_max_row = min(source_rows), max(source_rows)
        source_min_col, source_max_col = min(source_cols), max(source_cols)
        target_min_row, target_max_row = min(target_rows), max(target_rows)
        target_min_col, target_max_col = min(target_cols), max(target_cols)
        directions = set()
        if source_max_row < target_min_row:
            directions.add("up")
        elif source_min_row > target_max_row:
            directions.add("down")
        if source_max_col < target_min_col:
            directions.add("left")
        elif source_min_col > target_max_col:
            directions.add("right")
        if directions:
            return directions
        source_center_row = (source_min_row + source_max_row) / 2
        source_center_col = (source_min_col + source_max_col) / 2
        target_center_row = (target_min_row + target_max_row) / 2
        target_center_col = (target_min_col + target_max_col) / 2
        row_delta = source_center_row - target_center_row
        col_delta = source_center_col - target_center_col
        if abs(row_delta) >= abs(col_delta) and row_delta != 0:
            directions.add("down" if row_delta > 0 else "up")
        if abs(col_delta) >= abs(row_delta) and col_delta != 0:
            directions.add("right" if col_delta > 0 else "left")
        return directions

    @staticmethod
    def normalize_fit_facing(facing):
        if facing in (None, "", "any"):
            return None
        value = str(facing).strip().lower().replace("-", "_")
        aliases = {
            "source": "toward_source",
            "towards_source": "toward_source",
            "facing_source": "toward_source",
            "source_facing": "toward_source",
        }
        return aliases.get(value, value)

    @classmethod
    def fit_facing_matches(cls, target_pixels, surrounding_sides, source_pixels=None, facing=None):
        facing = cls.normalize_fit_facing(facing)
        if facing is None:
            return True
        open_sides = {"up", "down", "left", "right"} - set(surrounding_sides)
        if not open_sides:
            return False
        if facing in {"up", "down", "left", "right"}:
            return facing in open_sides
        if facing == "toward_source":
            source_directions = cls.fit_relative_directions(source_pixels, target_pixels)
            return bool(open_sides & source_directions)
        return False

    def fit_candidate_anchors(
        self,
        target_shape,
        excluded_node=None,
        min_surrounding_sides=3,
        cavity_color=None,
        facing=None,
        source_pixels=None,
        shape_transform=None,
        min_contact_count=None,
        max_axis_gap=None,
    ):
        return [
            match["anchor"]
            for match in self.fit_candidate_matches(
                target_shape,
                excluded_node=excluded_node,
                min_surrounding_sides=min_surrounding_sides,
                cavity_color=cavity_color,
                facing=facing,
                source_pixels=source_pixels,
                shape_transform=shape_transform,
                min_contact_count=min_contact_count,
                max_axis_gap=max_axis_gap,
            )
        ]

    def fit_candidate_matches(
        self,
        target_shape,
        excluded_node=None,
        min_surrounding_sides=3,
        cavity_color=None,
        facing=None,
        source_pixels=None,
        shape_transform=None,
        min_contact_count=None,
        max_axis_gap=None,
    ):
        target_shape = self.normalize_shape_value(target_shape)
        if not target_shape:
            return []
        matches = []
        for candidate_shape in self.fit_shape_variants(target_shape, shape_transform):
            max_row = max(row for row, _ in candidate_shape)
            max_col = max(col for _, col in candidate_shape)
            for anchor_row in range(0, self.image.height - max_row):
                for anchor_col in range(0, self.image.width - max_col):
                    target_pixels = self.fit_target_pixels(
                        candidate_shape,
                        (anchor_row, anchor_col),
                    )
                    if not self.check_inbound(target_pixels):
                        continue
                    if any(
                        self.occupied_pixel_owner(pixel, excluded_node=excluded_node) is not None
                        for pixel in target_pixels
                    ):
                        continue
                    surrounding_sides, contact_count = self.fit_surrounding_context(
                        target_pixels,
                        excluded_node,
                        cavity_color=cavity_color,
                    )
                    if len(surrounding_sides) < min_surrounding_sides:
                        continue
                    if min_contact_count is not None and contact_count < min_contact_count:
                        continue
                    if not self.fit_facing_matches(
                        target_pixels,
                        surrounding_sides,
                        source_pixels=source_pixels,
                        facing=facing,
                    ):
                        continue
                    axis_gap = self.fit_projected_axis_gap(source_pixels, target_pixels)
                    if max_axis_gap is not None and axis_gap is not None and axis_gap > max_axis_gap:
                        continue
                    matches.append({
                        "anchor": (anchor_row, anchor_col),
                        "target_shape": candidate_shape,
                        "target_pixels": target_pixels,
                        "surrounding_sides": surrounding_sides,
                        "contact_count": contact_count,
                        "axis_gap": axis_gap,
                    })
        return matches

    @staticmethod
    def normalize_fit_alignment(alignment):
        if alignment in (None, "", "any"):
            return None
        value = str(alignment).strip().lower().replace("-", "_")
        aliases = {
            "prefer": "prefer_projected",
            "prefer_axis": "prefer_projected",
            "prefer_aligned": "prefer_projected",
            "projected": "require_projected",
            "aligned": "require_projected",
            "require_axis": "require_projected",
            "require_aligned": "require_projected",
        }
        return aliases.get(value, value)

    def graph_has_projected_fit_candidate(
        self,
        source_color,
        source_shape=None,
        target_shape=None,
        cavity_color=None,
        min_surrounding_sides=3,
        facing=None,
        shape_transform=None,
        min_contact_count=None,
        max_axis_gap=None,
    ):
        expected_source_shape = self.normalize_shape_value(source_shape)
        expected_target_shape = self.normalize_shape_value(target_shape)
        for candidate_node, data in self.graph.nodes(data=True):
            if source_color is not None and data.get("color") != source_color:
                continue
            try:
                actual_shape = self.get_shape(candidate_node)
            except Exception:
                continue
            if expected_source_shape is not None and actual_shape != expected_source_shape:
                continue
            candidate_target_shape = expected_target_shape or actual_shape
            source_pixels = set(data.get("nodes", []))
            matches = self.fit_candidate_matches(
                candidate_target_shape,
                excluded_node=candidate_node,
                min_surrounding_sides=min_surrounding_sides,
                cavity_color=cavity_color,
                facing=facing,
                source_pixels=source_pixels,
                shape_transform=shape_transform,
                min_contact_count=min_contact_count,
                max_axis_gap=max_axis_gap,
            )
            if any(
                set(match["target_pixels"]) != source_pixels
                for match in matches
            ):
                return True
        return False

    def node_shape_fits_cavity(
        self,
        node,
        source_shape=None,
        target_shape=None,
        cavity_color=None,
        min_surrounding_sides=3,
        facing=None,
        shape_transform=None,
        min_contact_count=None,
        max_axis_gap=None,
        alignment=None,
    ):
        if node not in self.graph.nodes:
            return False
        actual_source_shape = self.get_shape(node)
        expected_source_shape = self.normalize_shape_value(source_shape)
        if expected_source_shape is not None and actual_source_shape != expected_source_shape:
            return False
        expected_target_shape = self.normalize_shape_value(target_shape)
        if expected_target_shape is None:
            expected_target_shape = actual_source_shape
        if shape_transform in (None, "", "identity", "same") and actual_source_shape != expected_target_shape:
            return False
        current_pixels = set(self.graph.nodes[node].get("nodes", []))
        matches = [
            match
            for match in self.fit_candidate_matches(
                expected_target_shape,
                excluded_node=node,
                min_surrounding_sides=min_surrounding_sides,
                cavity_color=cavity_color,
                facing=facing,
                source_pixels=current_pixels,
                shape_transform=shape_transform,
                min_contact_count=min_contact_count,
            )
            if set(match["target_pixels"]) != current_pixels
        ]
        if not matches:
            return False

        alignment = self.normalize_fit_alignment(alignment)
        if max_axis_gap is None or alignment is None:
            return True

        projected_matches = [
            match
            for match in matches
            if match["axis_gap"] is not None and match["axis_gap"] <= max_axis_gap
        ]
        if alignment == "require_projected":
            return bool(projected_matches)
        if alignment != "prefer_projected":
            return True

        source_color = self.graph.nodes[node].get("color")
        has_projected_fit = self.graph_has_projected_fit_candidate(
            source_color,
            source_shape=source_shape,
            target_shape=target_shape,
            cavity_color=cavity_color,
            min_surrounding_sides=min_surrounding_sides,
            facing=facing,
            shape_transform=shape_transform,
            min_contact_count=min_contact_count,
            max_axis_gap=max_axis_gap,
        )
        if has_projected_fit:
            return bool(projected_matches)
        return True

    def get_centroid(self, node):
        """
        get the centroid of a abstract node on original image grid
        """
        if len(self.graph.nodes[node]["nodes"]) == 1:
            return (self.graph.nodes[node]["nodes"][0][0], self.graph.nodes[node]["nodes"][0][1])
        
        center_y = (sum([n[0] for n in self.graph.nodes[node]["nodes"]]) + self.graph.nodes[node]["size"] / 2) / \
                   self.graph.nodes[node]["size"]
        center_x = (sum([n[1] for n in self.graph.nodes[node]["nodes"]]) + self.graph.nodes[node]["size"] / 2) / \
                   self.graph.nodes[node]["size"]
        return (center_y, center_x) # (row, col)

    @staticmethod
    def get_centroid_from_pixels(pixels):
        """
        get the centroid of a list of pixels
        """
        size = len(pixels)
        if size == 0:
            return (0,0)
        if size == 1:
            return (pixels[0][0], pixels[0][1])
        center_y = (sum([n[0] for n in pixels])) / size
        center_x = (sum([n[1] for n in pixels])) / size
        return (round(center_y,2), round(center_x,2))

    @classmethod
    def get_centroid_direction_from_pixels(
        cls,
        source_pixels,
        target_pixels,
        source_color=None,
        target_color=None,
        background_color=0,
    ):
        source_y, source_x = cls.get_centroid_from_pixels(source_pixels)
        target_y, target_x = cls.get_centroid_from_pixels(target_pixels)
        delta_y = target_y - source_y
        delta_x = target_x - source_x
        if delta_y == 0 and delta_x == 0:
            return None
        if (
            source_color == background_color
            and target_color != background_color
            and delta_y != 0
        ):
            return "s" if delta_y > 0 else "n"
        if (
            target_color == background_color
            and source_color != background_color
            and delta_y != 0
        ):
            return "s" if delta_y > 0 else "n"
        if abs(delta_y) >= abs(delta_x):
            return "s" if delta_y > 0 else "n"
        return "e" if delta_x > 0 else "w"

    def get_relative_pos(self, node1, node2):
        """
        direction of where node 2 is relative to node 1, ie what is the direction going from 1 to 2
        """
        for sub_node_1 in self.graph.nodes[node1]["nodes"]:
            for sub_node_2 in self.graph.nodes[node2]["nodes"]:
                if sub_node_1[0] == sub_node_2[0]:
                    if sub_node_1[1] < sub_node_2[1]:
                        return Direction.RIGHT
                    elif sub_node_1[1] > sub_node_2[1]:
                        return Direction.LEFT
                elif sub_node_1[1] == sub_node_2[1]:
                    if sub_node_1[0] < sub_node_2[0]:
                        return Direction.DOWN
                    elif sub_node_1[0] > sub_node_2[0]:
                        return Direction.UP
        return None

    def get_mirror_axis(self, node1, node2):
        """
        get the axis to mirror node1 with given node2
        """
        node2_centroid = self.get_centroid(node2)
        if self.graph.edges[node1, node2]["direction"] == "vertical":
            return (node2_centroid[0], None)
        else:
            return (None, node2_centroid[1])

    def get_point_from_relative_pos(self, filtered_point, relative_point, relative_pos: RelativePosition):
        """
        get the point to insert new node given
        filtered_point: the centroid of the source node relative to which the new node is inserted
        relative_point: the centroid of the target node, or static point such as (0,0)
        relative_pos: the relative position of the filtered_point to the relative_point
        """
        if relative_pos == RelativePosition.SOURCE:
            return filtered_point   # input node  (i.e parent object centroid)
        elif relative_pos == RelativePosition.TARGET:
            return relative_point   # output node (i.e child object centroid)
        elif relative_pos == RelativePosition.MIDDLE:
            y = (filtered_point[0] + relative_point[0]) / 2
            x = (filtered_point[1] + relative_point[1]) / 2
            return (round(y), round(x))

    def get_common_shapes(self, nodes1, nodes2):
        common_shapes = [] 
        node_map = {}
        for node1, object1 in nodes1:
            for node2, object2 in nodes2:
                if object1["color"] == object2["color"] and \
                    object1["size"] > 1 and object2["size"] > 1:
                    if object1["size"] < object2["size"]:
                        part = self.get_footprint(object1["nodes"])
                        whole = object2["nodes"]
                    elif object1["size"] > object2["size"]:
                        part = self.get_footprint(object2["nodes"])    
                        whole = object1["nodes"]
                    else:
                        continue
                    
                    if len(whole) > 1:
                        subgraph = self.image.graph.subgraph(whole)
                        communities = nx.community.girvan_newman(subgraph)
                        for community in communities:
                            if len(community) > 0 and len(community[0]) == len(part):
                                partition = self.image.graph.subgraph(community[0])
                                mask = self.get_footprint(partition)
                                if mask != part:
                                    mask = self.get_footprint(self.rotate_mask(partition, Rotation.CW))
                                if mask != part:
                                    mask = self.get_footprint(self.rotate_mask(partition, Rotation.CCW))    
                                if mask != part:
                                    mask = self.get_footprint(self.rotate_mask(partition, Rotation.CW2))                    
                                if mask == part and len(mask) > 1 and mask not in common_shapes:
                                    common_shapes.append(mask)
                                    node_map[node1] = node2                   
        return common_shapes, node_map        
    
    def get_rank_of_node(self, in_node, key):
        in_value = self.graph.nodes[in_node][key]
        node_values = nx.get_node_attributes(self.graph,key)
        sorted_nodes = sorted(node_values.items(), key=lambda x: x[1])
        for i, node in enumerate(sorted_nodes):
            if in_value == node[1]:            
                return i+1
    
    def get_rank_of_value(self, filter, value):
        node_values = nx.get_node_attributes(self.graph, filter)
        sorted_nodes = sorted(node_values.items(), key=lambda x: x[1])
        for i, node in enumerate(sorted_nodes):
            if value == node[1]: # color           
                return i+1
            
    def get_color_of_value(self, filter, value):
        """
        given a filter and a value, return the color of the node that has the value
        """
        if filter == "node" or filter == "target":
           return self.graph.nodes[value]["color"] 
        elif filter == "shape": # this attribute is not stored in node data
            for node, data in self.graph.nodes(data=True):
                if self.get_shape(node) == value:
                    return data.get("color") # this attribute is in data
        else: # by default get the node attribute called as filter   
            node_values = nx.get_node_attributes(self.graph, filter)
            if not node_values:
                raise ValueError(f"No nodes have the attribute '{filter}'")
            for node, node_value in node_values:
                if node_value == value:              
                    return self.graph.nodes[node]["color"]
        
    def get_match(self, graph):
        DiGM = nx.isomorphism.DiGraphMatcher(self.graph, graph)
        iso = DiGM.is_isomorphic()
        mapping = list(DiGM.subgraph_isomorphisms_iter())
        return mapping
            
    def get_largest_common_subgraph(self, graph):
        ismags = nx.isomorphism.ISMAGS(self.graph, graph.graph)
        graphs = list(ismags.largest_common_subgraph())
        return graphs
    
    def get_decomposition_at(self, nodes):
        for node in nodes: 
            components = self.decompose_by(node)
        return components    
    
    def get_orientation(self, object): # oject = subnode.data
        """
        get the decomposition of the graph into its components
        """
        template = self.get_footprint(object["nodes"])
        for edge in self.graph.edges():
            direction = self.direction_from[self.graph.edges[edge]["direction"]]
            #orientation = self.point_map[(k for k, v in self.direction_from.items() if v == direction)]
            node1, node2 = edge
            subnodes1 = self.graph.nodes[node1]["nodes"]
            subnodes2 = self.graph.nodes[node2]["nodes"]
            intersection = set(subnodes1) & set(subnodes2)
            if len(intersection) > 0:
                print("{} has overlap between nodes {} and {}".format(self.name, node1, node2))
                return None
            self.get_common_shapes(subnodes1, subnodes2)
            return direction    

                       
    # ------------------------------------------ apply -----------------------------------
    def apply(self, target_nodes, filters, filter_params, transformation, transformation_params=None):
        """
        perform a full operation on the abstracted graph
        1. apply filters to get a list of nodes to transform
        2. apply param binding to the filtered nodes to retrieve parameters for the transformation
        3. apply transformation to the nodes
        """
        if transformation_params is not None:
            transformation_params = [expand_classifier_params(transformation_params[0])]
        transformation_name = transformation[0] if isinstance(transformation, list) else transformation
        track_target_nodes = transformation_name not in self.whole_graph_transformation_ops
        if not track_target_nodes:
            target_nodes.clear()
        if len(self.graph.nodes()) > self.max_nodes_to_update:
            raise ValueError(f" {self.name} has too many nodes to '{transformation_name}': {len(self.graph.nodes())}")
         
        qualified_nodes = {} 
        source_nodes = self.graph.nodes() # NodeView has no copy() attribue(function) bevcause it is a generator object 
        for node in source_nodes: # abstract graph nodes that have image cells as subnodes (ie. pixels)
            self.abort_if_stop_requested(f"{transformation_name} filter scan")
            if transformation_name == "insert" and self.graph.nodes[node].get("_inserted"):
                continue
            if self.apply_filters(node, filters, filter_params): # only apply transformation to nodes that satisfy the filters
                if transformation_name == "add_border" and not self.can_add_border(node):
                    continue
                if track_target_nodes and node in target_nodes: # nodes that already was a target in the same transaction (i.e task.apply(calls))
                    continue # skip already transformed original nodes(ie contains all previous pixels, even if have few extra)     
                params = self.apply_param_binding(node, transformation_params) # swap original params to dynamic(results of binding) 
                if transformation_name == "add_border" and not self.can_add_border(
                    node,
                    params.get("border_type") if isinstance(params, dict) else None,
                ):
                    continue
                qualified_nodes[node] = params 

        if transformation_name in self.whole_graph_transformation_ops and len(qualified_nodes) > 1:
            first_node = next(iter(qualified_nodes))
            qualified_nodes = {first_node: qualified_nodes[first_node]}
        
        for node, params in qualified_nodes.items(): # abstract nodes that satisfy filters and should be transformed as result
            self.abort_if_stop_requested(transformation_name)
            if node not in self.graph.nodes():
                raise ValueError(f"Source node {node} disappeared unexpectedly")
            if transformation_name == "add_border" and not self.can_add_border(
                node,
                params.get("border_type") if isinstance(params, dict) else None,
            ):
                continue
            if track_target_nodes:
                old_identity = self.graph.nodes[node]["color"] # old "identity"= target node pixels before the transformation
                if transformation_name == "insert":
                    old_identity = {"color": old_identity, "_insert_target": True}
                target_nodes.update({node: old_identity})
            self.apply_transformation(node, transformation, params)
            if track_target_nodes and transformation_name == "remove_node":
                # Keep removed nodes in branch-local target_nodes so later apply() calls
                # do not mistake intentional deletion for stale graph mutation.
                target_nodes[node] = None

        if track_target_nodes:
            for target_node, old_colors in target_nodes.copy().items(): 
                if target_node not in self.graph.nodes():
                    if old_colors is None:
                        continue
                    raise ValueError(f"target node {target_node} disappeared unexpectedly")
                if old_colors is None:
                    continue
                if isinstance(old_colors, dict) and old_colors.get("_insert_target"):
                    continue
                if isinstance(old_colors, dict) and "color" in old_colors:
                    old_colors = old_colors["color"]
                new_colors = self.graph.nodes[target_node]["color"]
                new_color_set = set(new_colors) if isinstance(new_colors, list) else {new_colors}
                old_color_set = set(old_colors) if isinstance(old_colors, list) else {old_colors}
                if new_color_set <= old_color_set: # if new color of target node are a subset of the old colors
                    target_nodes.pop(target_node) # assume target_node not changed (ie. color is the same or has fewer pixels, so assume the same)
            
        # update the edges in the abstracted graph to reflect the changes
        if len(self.graph.nodes()) > self.max_nodes_to_update:
            raise ValueError(f" {self.name} has too many nodes to '{transformation_name}': {len(self.graph.nodes())}")
        else:
            if transformation_name == "remove_node":
                affected_nodes = list(self.graph.nodes())
            else:
                affected_nodes = [node for node in qualified_nodes if node in self.graph.nodes()]
            self.update_abstracted_graph(affected_nodes) # update only targeted nodes unless ids were regenerated
        return target_nodes    

    def apply_filters(self, node, filters, filter_params, transformation=None, transformation_params=None):
        """
        given filters and a node, return True if node satisfies all filters
        """
        satisfy = True
        for filter, filter_param in zip(filters, filter_params): # ex. filters=['filter_by_color'] filter_params={'color': 0, 'exclude': True}
            satisfy = satisfy and getattr(self, filter)(node, **filter_param) # filter_by_color(self, node, color: int, exclude: bool = False):
        return satisfy

    def apply_param_binding(self, node, transformation_params=None):
        """
        handle dynamic parameters: if a dictionary is passed as a parameter value, this means the parameter
        value needs to be retrieved from the parameter-binded nodes during the search

        example: set param "color" to the color of the neighbor with size 1
        """
        if transformation_params is None:
            return {}
        transformation_params_retrieved = copy.deepcopy(transformation_params[0])
        for param_key, param_value in transformation_params[0].items():
            if (
                isinstance(param_value, dict)
                and "filters" in param_value
                and "filter_params" in param_value
            ): # what if isinstance(param_value, Enum) ??
                param_bind_function = param_value["filters"][0]
                param_bind_function_params = param_value["filter_params"][0]
                target_node = getattr(self, param_bind_function)(node, **param_bind_function_params)

                #  retrieve value, ex. color of the neighbor with size 1
                if param_key in {"color", "border_color", "fill_color"}:
                    target_color = self.get_color(target_node) # ex. neighbor
                    transformation_params_retrieved[param_key] = target_color
                elif param_key == "direction":
                    target_direction = self.get_relative_pos(node, target_node)
                    if target_direction is None and target_node is not None:
                        source_y, source_x = self.get_centroid_from_pixels(
                            self.graph.nodes[node]["nodes"]
                        )
                        target_y, target_x = self.get_centroid_from_pixels(
                            self.graph.nodes[target_node]["nodes"]
                        )
                        delta_y = target_y - source_y
                        delta_x = target_x - source_x
                        if delta_y < 0 and delta_x < 0:
                            target_direction = Direction.UP_LEFT
                        elif delta_y < 0 and delta_x > 0:
                            target_direction = Direction.UP_RIGHT
                        elif delta_y > 0 and delta_x < 0:
                            target_direction = Direction.DOWN_LEFT
                        elif delta_y > 0 and delta_x > 0:
                            target_direction = Direction.DOWN_RIGHT
                        elif delta_y < 0:
                            target_direction = Direction.UP
                        elif delta_y > 0:
                            target_direction = Direction.DOWN
                        elif delta_x < 0:
                            target_direction = Direction.LEFT
                        elif delta_x > 0:
                            target_direction = Direction.RIGHT
                    transformation_params_retrieved[param_key] = target_direction
                elif param_key == "mirror_point" or param_key == "point":
                    target_point = self.get_centroid(target_node)
                    transformation_params_retrieved[param_key] = target_point
                #elif param_key == "mirror_axis":
                #    target_axis = self.get_mirror_axis(node, target_node)
                #    transformation_params_retrieved[param_key] = target_axis
                #elif param_key == "mirror_direction":
                #    target_mirror_dir = self.get_mirror_direction(node, target_node)
                #    transformation_params_retrieved[param_key] = target_mirror_dir
                else:
                    raise ValueError("unsupported dynamic parameter")
        return transformation_params_retrieved

    def apply_transformation(self, node, transformation, transformation_params):
        """
        apply transformation to a node
        """
        self.abort_if_stop_requested(transformation[0])
        getattr(self, transformation[0])(node, **transformation_params)  # currently only allow one transformation
        self.abort_if_stop_requested(f"{transformation[0]} post-check")

    # ------------------------------------------ meta utils -----------------------------------

    def copy(self):
        """
        return a copy of this ARCGraph object
        """
        graph_copy = ARCGraph(self.graph.copy(), self.name, self.image.copy(), self.abstraction)
        graph_copy.transformation_ops = copy.deepcopy(self.transformation_ops) # dynamicly set operations
        return graph_copy

    def get_node_id(self, node):
        return '('+str(node[0])+','+str(node[1])+')'

    @staticmethod
    def get_base_node_id(node):
        if not isinstance(node, tuple) or len(node) != 2:
            return node
        y, x = node
        numeric_types = (int, float, np.integer, np.floating)
        if (
            isinstance(y, bool)
            or isinstance(x, bool)
            or not isinstance(y, numeric_types)
            or not isinstance(x, numeric_types)
        ):
            return node
        return (round(float(y), 2), round(float(x), 2))

    @staticmethod
    def is_grid_coordinate(value):
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, np.integer)):
            return True
        if isinstance(value, (float, np.floating)):
            return float(value).is_integer()
        return False

    def normalize_pixel(self, pixel, context="pixel"):
        try:
            y, x = pixel
        except (TypeError, ValueError):
            raise ValueError(f"{context} is not a pixel coordinate: {pixel!r}")

        if not self.is_grid_coordinate(y) or not self.is_grid_coordinate(x):
            raise ValueError(
                f"{context} has non-integer pixel coordinate {pixel!r}; "
                "abstract node ids must not be stored as subnodes"
            )
        return (int(y), int(x))

    def normalize_pixels(self, pixels, context="pixels"):
        return [
            self.normalize_pixel(pixel, f"{context}[{index}]")
            for index, pixel in enumerate(pixels)
        ]

    @staticmethod
    def add_edge_safe(graph, node1, node2, **attrs):
        """
        NetworkX add_edge creates missing nodes implicitly.
        Abstract graphs should never grow through edge creation.
        """
        if node1 not in graph.nodes() or node2 not in graph.nodes():
            raise ValueError(f"Can not add edge between missing nodes {node1} and {node2}")
        graph.add_edge(node1, node2, **attrs)

    def generate_node_id(self, graph:nx.DiGraph, pixels:list, reuse_existing=True):
        """
        find the next available id for a given set of pixels,
        """
        pixels = self.normalize_pixels(pixels, "generate_node_id pixels")
        if reuse_existing:
            pixel_set = frozenset(pixels)
            for node, data in graph.nodes(data=True):
                if frozenset(data.get("nodes", [])) == pixel_set:
                    return node

        max_allowed_nodes = getattr(self.image, "max_allowd_pixels", self.max_nodes_to_update)
        if graph.number_of_nodes() >= max_allowed_nodes:
            raise ValueError(f"{self.name} exceeds allowed abstract nodes {max_allowed_nodes}")

        centroid = self.get_centroid_from_pixels(pixels)
        centroid = tuple(round(float(value), 2) for value in centroid)

        attempts = 0
        while centroid in graph.nodes():
            attempts += 1
            if attempts > max_allowed_nodes:
                raise ValueError(f"{self.name} could not allocate a unique node id within {max_allowed_nodes} attempts")
            centroid = tuple(round(value + 0.001, 3) for value in centroid)
        return centroid

    def undo_abstraction(self, component=None): # by default undo all components
        """
        undo the abstraction to get the corresponding 2D grid
        return it as an ARCGraph object
        """

        #width, height = self.image.size
        self.abort_if_stop_requested("undo_abstraction")
        reconstructed_graph = nx.grid_2d_graph(self.image.height, self.image.width)
        background_color = self.abstraction_background_color()
        nx.set_node_attributes(reconstructed_graph, background_color, "color")
        reconstructed_graph.graph["background_hypothesis_id"] = self.graph.graph.get(
            "background_hypothesis_id"
        )
        reconstructed_graph.graph["canvas_color"] = background_color

        graph_nodes = sorted(
            list(self.graph.nodes(data=True)),
            key=lambda item: item[1].get("z_order", 0),
        )

        if self.abstraction in self.image.multicolor_abstractions:
            for comp, data in graph_nodes:
                self.abort_if_stop_requested("undo_abstraction")
                if component == None or comp == component: 
                    for i, node in enumerate(data["nodes"]):
                        self.abort_if_stop_requested("undo_abstraction")
                        try:
                            reconstructed_graph.nodes[node]["color"] = data["color"][i]
                        except: # KeyError:  # ignore pixels outside of frame
                            pass
        else:
            for comp, data in graph_nodes:
                self.abort_if_stop_requested("undo_abstraction")
                if component == None or comp == component: 
                    for node in data["nodes"]: # subnodes of abstraced component node 
                        self.abort_if_stop_requested("undo_abstraction")
                        try:
                            reconstructed_graph.nodes[node]["color"] = data["color"]
                        except: #KeyError:  # ignore pixels outside of frame
                            pass

        return ARCGraph(reconstructed_graph, self.name + "_X", self.image, None)

    def carve_at(self, joints=None): # all common sink nodes of abstracted graph
        """
        undo the abstraction and divide into 2D grids corresponding to connected components left after joints removed
        return all resulting ARCGraph objects
        """

        reconstructed_graph = nx.grid_2d_graph(self.image.height, self.image.width)
        nx.set_node_attributes(reconstructed_graph, self.abstraction_background_color(), "color")

        if self.abstraction in self.image.multicolor_abstractions:
            for cut, data in self.graph.nodes(data=True):
                for i, node in enumerate(data["nodes"]):
                    if joints != None and cut in joints:
                        reconstructed_graph.remove_node(node) # carve by cutting out joints
                    else:    
                        try:
                            reconstructed_graph.nodes[node]["color"] = data["color"][i]
                        except: # KeyError:  # ignore pixels outside of frame
                            pass
        else:
            for cut, data in self.graph.nodes(data=True):
                for node in data["nodes"]: # subnodes of abstraced component node 
                    if joints != None and cut in joints:
                        reconstructed_graph.remove_node(node)
                    else:    
                        try:
                            reconstructed_graph.nodes[node]["color"] = data["color"]
                        except: #KeyError:  # ignore pixels outside of frame
                            pass        
        
        partition = []                                    
        for i, component in enumerate(nx.connected_components(reconstructed_graph)):
            rows = [node[0] for node in component]
            cols = [node[1] for node in component]
            height = max(rows) - min(rows) + 1
            width = max(cols) - min (cols) + 1
            
            if height < self.image.height or width < self.image.width:
                grid = nx.grid_2d_graph(height, width)
                
                shift = (0,0)
                dx = max(rows) - min(rows) + len(joints) + 1
                dy = max(cols) - min(cols) + len(joints) + 1
                orientation = max(cols) - max(rows)
                if orientation > 0:
                    shift = (0, dy)
                elif orientation < 0:
                    shift = (dx, 0)    
                array = self.grid_graph_to_2d_array(grid, height, width, reconstructed_graph, shift) 
                partition.append(array.tolist())
        return partition    

    def grid_graph_to_2d_array(self, grid, height, width, graph, shift):
        """Converts a NetworkX 2D grid graph to a 2D NumPy array."""
        dx, dy = shift
        # Create an empty 2D array
        array = np.zeros((height, width)).astype(int)
        # Fill the array with edge information
        try:
            for node in grid: # graph.nodes(data=True):
                x,y = node      
                color = graph.nodes[(x+dx,y+dy)]["color"]    
                array[x, y] = color
        except KeyError as e:
            raise ValueError(f"{grid} has invalid pixel: {e}")
        except Exception as e:
            raise ValueError(f"{graph} failed conversion to array: {e}")         
        return array

    def get_relative_shift(self, component, grid):
        for node in component:
            x,y = node
            if not node in grid.nodes:
                return (x,y)      
        return (0,0)        

    def shift_isomorphic_grid(self, grid):
        """Return an isomorphic pixel graph translated onto this graph.

        This helper is not the public DSL ``shift`` transformation.  Keeping a
        distinct name prevents it from replacing the earlier DSL action at
        class creation time.
        """
        shifted = None
        if nx.is_isomorphic(self.graph, grid.graph):     
            dx, dy = self.get_relative_shift(grid.graph)  
            shifted = self.shift_by(dx, dy, grid.graph) # makes copy, then shifts it                   
        return shifted
   
    def shift_by(self, dx, dy, graph):
        shifted = graph.copy()
        for node, data in graph.nodes(data=True):
            x, y = node
            new_node = (x + dx, y + dy)
            shifted.remove_node(node)
            shifted.add_node(new_node, **data)
        for edge in graph.edges():
            node1, node2 = edge
            new_node1 = (node1[0] + dx, node1[1] + dy)
            new_node2 = (node2[0] + dx, node2[1] + dy)
            self.add_edge_safe(shifted, new_node1, new_node2)
        return shifted
                    

    def update_abstracted_graph(self, affected_nodes):
        """
        update the abstracted graphs so that they remain consistent after transformation
        """
        for node, data in self.graph.nodes(data=True):
            self.abort_if_stop_requested("update_abstracted_graph")
            try:
                data["nodes"] = self.normalize_pixels(data["nodes"], f"{self.name} node {node} subnodes")
                data["size"] = len(data["nodes"])
                data["dim"] = self.get_node_dimensions(data["nodes"])
            except KeyError as e:
                raise ValueError("Node {} has no subnodes".format(node))

        pixel_assignments = {} # all abstract nodes covering(assigned) each pixel in the image
        for node, data in self.graph.nodes(data=True):
            self.abort_if_stop_requested("update_abstracted_graph")
            if node not in affected_nodes:
                continue    
            for subnode in data["nodes"]: # subnode(pixel) of transformed abstract nodes
                self.abort_if_stop_requested("update_abstracted_graph")
                if subnode in pixel_assignments:
                    pixel_assignments[subnode].append(node) # overlapping abstract nodes
                else:
                    pixel_assignments[subnode] = [node] # many(sub)-to-one abstract node
        '''
        for pixel, nodes in pixel_assignments.items():
            if len(nodes) > 1: # more than 1 abstract node assigned to pixel(russian doll)
                for node_1, node_2 in combinations(nodes, 2):
                    if not self.graph.has_edge(node_1, node_2):
                        self.add_edge_safe(self.graph, node_1, node_2, direction="o") # merged inside
        '''
        for node1, node2 in combinations(self.graph.nodes, 2):
            self.abort_if_stop_requested("update_abstracted_graph")
            if node1 == node2:
                continue
            else:
                nodes_1 = self.graph.nodes[node1]["nodes"]
                nodes_2 = self.graph.nodes[node2]["nodes"]
                centroid_direction = self.get_centroid_direction_from_pixels(
                    nodes_1,
                    nodes_2,
                    self.graph.nodes[node1].get("color"),
                    self.graph.nodes[node2].get("color"),
                    self.image.background_color,
                )
                for item in product(nodes_1,nodes_2):
                    self.abort_if_stop_requested("update_abstracted_graph")
                    n1 = item[0]
                    n2 = item[1]
                    if n1 == n2:
                        continue
                    if n1[0] == n2[0]:  # two nodes on the same row
                        for column_index in range(min(n1[1], n2[1]) + 1, max(n1[1], n2[1])):
                            self.abort_if_stop_requested("update_abstracted_graph")
                            # try:
                            pixel_assignment = pixel_assignments.get((n1[0], column_index), [])
                            if len(pixel_assignment) == 0 or (len(pixel_assignment) == 1 and (
                                    pixel_assignment[0] == node1 or pixel_assignment[0] == node2)):
                                continue
                            break
                        else:
                            edge_direction = centroid_direction
                            if edge_direction is None:
                                edge_direction = "w" if n1[1] > n2[1] else "e"
                            if self.graph.has_edge(node1, node2):
                                if n1[1] > n2[1] or n2[1] > n1[1]:
                                    self.graph.edges[node1, node2]["direction"] = edge_direction
                                else:
                                    self.graph.edges[node1, node2]["direction"] = "h"
                            else:
                                if n1[1] > n2[1] or n2[1] > n1[1]:
                                    self.add_edge_safe(self.graph, node1, node2, direction=edge_direction)
                                else:
                                    self.add_edge_safe(self.graph, node1, node2, direction="h")
                            break  # only one edge between two nodes        
                    elif n1[1] == n2[1]:  # two nodes on the same column:
                        for row_index in range(min(n1[0], n2[0]) + 1, max(n1[0], n2[0])):
                            self.abort_if_stop_requested("update_abstracted_graph")
                            pixel_assignment = pixel_assignments.get((row_index, n1[1]), [])
                            if len(pixel_assignment) == 0 or (len(pixel_assignment) == 1 and (
                                    pixel_assignment[0] == node1 or pixel_assignment[0] == node2)):
                                continue
                            break
                        else:
                            edge_direction = centroid_direction
                            if edge_direction is None:
                                edge_direction = "n" if n1[0] > n2[0] else "s"
                            if self.graph.has_edge(node1, node2):
                                if n1[0] > n2[0] or n2[0] > n1[0]:
                                    self.graph.edges[node1, node2]["direction"] = edge_direction
                                else:        
                                    self.graph.edges[node1, node2]["direction"] = "v"
                            else:
                                if n1[0] > n2[0] or n2[0] > n1[0]:
                                    self.add_edge_safe(self.graph, node1, node2, direction=edge_direction)
                                else:        
                                    self.add_edge_safe(self.graph, node1, node2, direction="v")
                            break  # only one edge between two nodes        
            
    def get_node_positions(self):
        positions = {}
        for node in self.graph.nodes:
            centroid = self.get_centroid(node)
            positions[node] = (centroid[1], -centroid[0])
        return positions    

    def get_node_sizes(self): 
        sizes = {}
        for node in self.graph.nodes:
            node_size = self.graph.nodes[node]["size"]
            sizes[node] = node_size   
        return sizes

    def get_node_dims(self, index=None):
        dims = {}
        for node in self.graph.nodes:
            node_dim = self.graph.nodes[node].get("dim")
            if node_dim is None:
                node_dim = self.refresh_node_dimensions(node)
            dims[node] = node_dim[index] if index is not None else node_dim
        return dims

    def get_node_colors(self):
        colors = {}
        for node in self.graph.nodes:
            colors[node] = self.graph.nodes[node]["color"]
        return colors
    
    def get_node_shapes(self): 
        shapes = {}
        for node in self.graph.nodes:
            node_shape = self.get_shape(node)
            shapes[node] = node_shape   
        return shapes
    
    
    def graph_to_grid(self):
        """
        Converts the graph to a grid representation.
        """
        self.abort_if_stop_requested("graph_to_grid")
        height = self.image.height
        width = self.image.width
        background_color = self.abstraction_background_color()
        grid = [[background_color for _ in range(width)] for _ in range(height)]
        graph_nodes = sorted(
            list(self.graph.nodes(data=True)),
            key=lambda item: item[1].get("z_order", 0),
        )
        for node, data in graph_nodes:
            self.abort_if_stop_requested("graph_to_grid")
            color = data.get('color', background_color)
            sub_nodes = data.get('nodes', [node])
            if isinstance(color, list):
                for idx, sub_node in enumerate(sub_nodes):
                    self.abort_if_stop_requested("graph_to_grid")
                    if idx >= len(color):
                        continue
                    y, x = sub_node
                    if not (0 <= y < height and 0 <= x < width):
                        continue
                    grid[y][x] = color[idx]
            else:
                for y, x in sub_nodes:
                    self.abort_if_stop_requested("graph_to_grid")
                    if not (0 <= y < height and 0 <= x < width):
                        continue
                    grid[y][x] = color
        return grid


    def plot(self, ax=None, save_fig=False, file_name=None):
        """
        visualize the graph
        """
        if plt is None:
            raise RuntimeError("ARCGraph.plot requires optional matplotlib")
        if ax is None:
            if self.abstraction is None:
                fig = plt.figure(figsize=(6, 6))
            else:
                fig = plt.figure(figsize=(4, 4))
        else:
            fig = ax.get_figure()

        if self.abstraction is None:
            pos = {(x, y): (y, -x) for x, y in self.graph.nodes()}
            try:
                color = [self.colors[self.graph.nodes[x, y]["color"]] for x, y in self.graph.nodes()]
                
                nx.draw(self.graph, ax=ax, pos=pos, node_color=color, node_size=600)
                nx.draw_networkx_labels(self.graph, ax=ax, font_color="#676767", pos=pos, font_size=8)
            except Exception as e:
                print(f"{Fore.RED}{self.name} could not be plotted: {e}{Style.RESET_ALL}")
        else:
            pos = self.get_node_positions()
            try:
                if self.abstraction in {"mcccg", "occg", "na"}:
                    color = [self.colors[0] for node, data in self.graph.nodes(data=True)]
                else:
                    color = [self.colors[data["color"]] for node, data in self.graph.nodes(data=True)]
                size = [300 * data["size"] for node, data in self.graph.nodes(data=True)]

                nx.draw(self.graph, pos=pos, node_color=color, node_size=size)
                nx.draw_networkx_labels(self.graph, font_color="#676767", pos=pos, font_size=8)

                edge_labels = nx.get_edge_attributes(self.graph, "direction")
                nx.draw_networkx_edge_labels(self.graph, pos=pos, edge_labels=edge_labels)
            except Exception as e:
                print(f"{Fore.RED}{self.name} could not be plotted: {e}{Style.RESET_ALL}")
                
        if save_fig:
            if file_name is not None:
                try:
                    fig.savefig(self.save_dir + "/" + file_name)
                except Exception as e:
                    print(f"{Fore.RED} Could not save figure {file_name}{Style.RESET_ALL}: {e}")
                    pass    
            else:
                try:
                    fig.savefig(self.save_dir + "/" + self.name)
                except Exception as e:
                    print(f"{Fore.RED} Could not save figure {file_name}{Style.RESET_ALL}: {e}")
                    pass    
        plt.close()

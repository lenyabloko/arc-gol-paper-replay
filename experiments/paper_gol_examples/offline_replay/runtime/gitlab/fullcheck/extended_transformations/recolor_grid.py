from collections import deque, defaultdict
import copy
from dsl_classifier_migration import classifier_action

try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def _component_bbox_topology_code(pixels):
    """Classify a same-color component by bbox topology.

    Codes intentionally match the compact e509e548-style topology language:
    1 = thin corner/L path, 2 = component has bbox-interior pixels,
    6 = bbox-border-only component that is not a thin corner path.
    """
    min_row, max_row, min_col, max_col = find_bounding_rectangle(pixels)
    height = max_row - min_row + 1
    width = max_col - min_col + 1
    normalized_pixels = {
        (row - min_row, col - min_col)
        for row, col in pixels
    }
    local_row_counts = [
        sum((local_row, local_col) in normalized_pixels for local_col in range(width))
        for local_row in range(height)
    ]
    local_col_counts = [
        sum((local_row, local_col) in normalized_pixels for local_row in range(height))
        for local_col in range(width)
    ]
    local_full_rows = {
        local_row
        for local_row, count in enumerate(local_row_counts)
        if count == width
    }
    local_full_cols = {
        local_col
        for local_col, count in enumerate(local_col_counts)
        if count == height
    }
    interior_pixels = sum(
        1
        for local_row, local_col in normalized_pixels
        if 0 < local_row < height - 1
        and 0 < local_col < width - 1
    )
    l_path_size = height + width - 1
    thin_corner_path = (
        len(pixels) == l_path_size
        and (
            (0 in local_full_rows and 0 in local_full_cols)
            or (0 in local_full_rows and width - 1 in local_full_cols)
            or (height - 1 in local_full_rows and 0 in local_full_cols)
            or (height - 1 in local_full_rows and width - 1 in local_full_cols)
        )
    )
    if thin_corner_path:
        return 1
    if interior_pixels > 0:
        return 2
    return 6


def _normalized_component_mask(pixels):
    min_row, max_row, min_col, max_col = find_bounding_rectangle(pixels)
    pixel_set = set(pixels)
    return tuple(
        tuple(
            1 if (row, col) in pixel_set else 0
            for col in range(min_col, max_col + 1)
        )
        for row in range(min_row, max_row + 1)
    )


def _is_exact_rectangle_border_pixels(pixels):
    min_row, max_row, min_col, max_col = find_bounding_rectangle(pixels)
    height = max_row - min_row + 1
    width = max_col - min_col + 1
    if height < 3 or width < 3:
        return False
    border = {
        (row, col)
        for row in range(min_row, max_row + 1)
        for col in range(min_col, max_col + 1)
        if row in (min_row, max_row) or col in (min_col, max_col)
    }
    return set(pixels) == border


def _same_color_components(grid, source_color):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    visited = set()
    components = []
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] != source_color or (row, col) in visited:
                continue
            stack = [(row, col)]
            visited.add((row, col))
            pixels = []
            while stack:
                current_row, current_col = stack.pop()
                pixels.append((current_row, current_col))
                for next_row, next_col in (
                    (current_row - 1, current_col),
                    (current_row + 1, current_col),
                    (current_row, current_col - 1),
                    (current_row, current_col + 1),
                ):
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if (next_row, next_col) in visited:
                        continue
                    if grid[next_row][next_col] != source_color:
                        continue
                    visited.add((next_row, next_col))
                    stack.append((next_row, next_col))
            components.append(pixels)
    return components


def recolor_grid_based(grid, recolor_type, color1, color2, shifting_direction, classifier_params=None):
    recolor_type, classifier_params = classifier_action(
        "recolor_type",
        recolor_type,
        classifier_params,
    )
    if recolor_type == "observed_color_permutation":
        if not isinstance(color2, (list, tuple)) or len(color2) < 10:
            raise ValueError("observed_color_permutation requires a length-10 color map")
        return [
            [
                color2[value] if isinstance(value, int) and 0 <= value < len(color2) else value
                for value in row
            ]
            for row in grid
        ]

    if recolor_type == "uniform_row_mask":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("uniform_row_mask requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("uniform_row_mask requires a rectangular grid")
        full_row_color = color1
        other_row_color = color2
        if not isinstance(full_row_color, int) or not isinstance(other_row_color, int):
            raise ValueError("uniform_row_mask requires integer output colors")
        return [
            [
                full_row_color if len(set(row_values)) == 1 else other_row_color
                for _ in row_values
            ]
            for row_values in grid
        ]

    if recolor_type == "solid_square_blank_regions":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("solid_square_blank_regions requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("solid_square_blank_regions requires a rectangular grid")
        background_color = color1
        fill_color = color2
        if not isinstance(background_color, int) or not isinstance(fill_color, int):
            raise ValueError("solid_square_blank_regions requires integer colors")
        if background_color == fill_color:
            raise ValueError("solid_square_blank_regions requires distinct colors")

        output = copy.deepcopy(grid)
        changed = False
        for pixels in _same_color_components(grid, background_color):
            pixel_set = set(pixels)
            if any(row in (0, rows - 1) or col in (0, cols - 1) for row, col in pixel_set):
                continue
            min_row, max_row, min_col, max_col = find_bounding_rectangle(pixels)
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            if height != width or len(pixel_set) != height * width:
                continue
            for row, col in pixel_set:
                output[row][col] = fill_color
                changed = True
        return output

    if recolor_type == "blank_region_rectangularity":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("blank_region_rectangularity requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("blank_region_rectangularity requires a rectangular grid")
        rectangle_color = color1
        irregular_color = color2
        background_color = 0
        if not isinstance(rectangle_color, int) or not isinstance(irregular_color, int):
            raise ValueError("blank_region_rectangularity requires integer output colors")
        if rectangle_color == irregular_color or background_color in (rectangle_color, irregular_color):
            raise ValueError("blank_region_rectangularity requires distinct non-background output colors")

        output = copy.deepcopy(grid)
        changed = False
        for pixels in _same_color_components(grid, background_color):
            pixel_set = set(pixels)
            min_row, max_row, min_col, max_col = find_bounding_rectangle(pixels)
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            target_color = (
                rectangle_color
                if len(pixel_set) == height * width
                else irregular_color
            )
            for row, col in pixel_set:
                output[row][col] = target_color
                changed = True
        if not changed:
            raise ValueError("blank_region_rectangularity found no background regions")
        return output

    if recolor_type == "hollow_rectangle_interior_fill_remove_frame":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("hollow_rectangle_interior_fill_remove_frame requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("hollow_rectangle_interior_fill_remove_frame requires a rectangular grid")
        frame_color = color1
        fill_color = color2
        background_color = 0
        if not isinstance(frame_color, int) or not isinstance(fill_color, int):
            raise ValueError("hollow_rectangle_interior_fill_remove_frame requires integer colors")
        if frame_color in (background_color, fill_color):
            raise ValueError("hollow_rectangle_interior_fill_remove_frame requires distinct colors")

        output = copy.deepcopy(grid)
        changed = False
        for pixels in _same_color_components(grid, frame_color):
            for row, col in pixels:
                output[row][col] = background_color
                changed = True
            if not _is_exact_rectangle_border_pixels(pixels):
                continue
            min_row, max_row, min_col, max_col = find_bounding_rectangle(pixels)
            for row in range(min_row + 1, max_row):
                for col in range(min_col + 1, max_col):
                    output[row][col] = fill_color
                    changed = True
        if not changed:
            raise ValueError("hollow_rectangle_interior_fill_remove_frame found no frame color")
        return output

    if recolor_type == "enclosed_square_size_palette":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("enclosed_square_size_palette requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("enclosed_square_size_palette requires a rectangular grid")
        background_color = color1
        palette = color2
        if not isinstance(background_color, int):
            raise ValueError("enclosed_square_size_palette requires an integer background color")
        if not isinstance(palette, (list, tuple)) or not palette:
            raise ValueError("enclosed_square_size_palette requires a side-length palette")

        output = copy.deepcopy(grid)
        for pixels in _same_color_components(grid, background_color):
            pixel_set = set(pixels)
            if any(row in (0, rows - 1) or col in (0, cols - 1) for row, col in pixel_set):
                continue
            min_row, max_row, min_col, max_col = find_bounding_rectangle(pixels)
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            if height != width or len(pixel_set) != height * width:
                continue
            if height < 1 or height > len(palette):
                raise ValueError("enclosed_square_size_palette missing side-length color")
            target_color = palette[height - 1]
            if not isinstance(target_color, int):
                raise ValueError("enclosed_square_size_palette colors must be integers")
            for row, col in pixel_set:
                output[row][col] = target_color
        return output

    if recolor_type == "component_size_rank_palette":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("component_size_rank_palette requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("component_size_rank_palette requires a rectangular grid")
        source_color = color1
        if source_color is None:
            raise ValueError("component_size_rank_palette requires a source color")
        if not isinstance(color2, (list, tuple)) or not color2:
            raise ValueError("component_size_rank_palette requires a rank palette")

        visited = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != source_color or (row, col) in visited:
                    continue
                stack = [(row, col)]
                visited.add((row, col))
                pixels = []
                while stack:
                    current_row, current_col = stack.pop()
                    pixels.append((current_row, current_col))
                    for next_row, next_col in (
                        (current_row - 1, current_col),
                        (current_row + 1, current_col),
                        (current_row, current_col - 1),
                        (current_row, current_col + 1),
                    ):
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited:
                            continue
                        if grid[next_row][next_col] != source_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                min_row, max_row, min_col, max_col = find_bounding_rectangle(pixels)
                components.append({
                    "pixels": pixels,
                    "size": len(pixels),
                    "bbox": (min_row, max_row, min_col, max_col),
                })
        if len(components) < 2:
            raise ValueError("component_size_rank_palette requires multiple source components")
        if len(color2) < len(components):
            raise ValueError("component_size_rank_palette palette is shorter than component count")

        output = copy.deepcopy(grid)
        for rank, component in enumerate(
            sorted(components, key=lambda item: (-item["size"], item["bbox"]))
        ):
            rank_color = color2[rank]
            for row, col in component["pixels"]:
                output[row][col] = rank_color
        return output

    if recolor_type == "matching_shape_exemplar_recolor":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("matching_shape_exemplar_recolor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("matching_shape_exemplar_recolor requires a rectangular grid")
        source_color = color1
        background_color = 0
        if source_color in (None, background_color):
            raise ValueError("matching_shape_exemplar_recolor requires a source color")

        visited = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] == background_color or (row, col) in visited:
                    continue
                component_color = grid[row][col]
                stack = [(row, col)]
                visited.add((row, col))
                pixels = []
                while stack:
                    current_row, current_col = stack.pop()
                    pixels.append((current_row, current_col))
                    for next_row, next_col in (
                        (current_row - 1, current_col),
                        (current_row + 1, current_col),
                        (current_row, current_col - 1),
                        (current_row, current_col + 1),
                    ):
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited:
                            continue
                        if grid[next_row][next_col] != component_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                components.append({
                    "color": component_color,
                    "pixels": pixels,
                    "shape": _normalized_component_mask(pixels),
                })

        exemplar_colors_by_shape = defaultdict(set)
        for component in components:
            if component["color"] == source_color:
                continue
            exemplar_colors_by_shape[component["shape"]].add(component["color"])
        exemplar_colors_by_shape = {
            shape: next(iter(colors))
            for shape, colors in exemplar_colors_by_shape.items()
            if len(colors) == 1
        }
        if not exemplar_colors_by_shape:
            raise ValueError("matching_shape_exemplar_recolor found no shape exemplars")

        output = copy.deepcopy(grid)
        changed = False
        for component in components:
            if component["color"] != source_color:
                continue
            target_color = exemplar_colors_by_shape.get(component["shape"])
            if target_color is None or target_color == source_color:
                continue
            for row, col in component["pixels"]:
                output[row][col] = target_color
                changed = True
        if not changed:
            raise ValueError("matching_shape_exemplar_recolor produced no change")
        return output

    if recolor_type in {"nested_ring_color_cycle", "nested_ring_color_reverse"}:
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError(f"{recolor_type} requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError(f"{recolor_type} requires a rectangular grid")

        layer_count = (min(rows, cols) + 1) // 2
        ring_colors = []
        for layer in range(layer_count):
            cells = []
            top = layer
            bottom = rows - layer - 1
            left = layer
            right = cols - layer - 1
            for col in range(left, right + 1):
                cells.append(grid[top][col])
                if bottom != top:
                    cells.append(grid[bottom][col])
            for row in range(top + 1, bottom):
                cells.append(grid[row][left])
                if right != left:
                    cells.append(grid[row][right])
            if not cells or len(set(cells)) != 1:
                raise ValueError(f"{recolor_type} requires uniform rings")
            ring_colors.append(cells[0])

        color_cycle = []
        for value in ring_colors:
            if value not in color_cycle:
                color_cycle.append(value)
        if len(color_cycle) < 2:
            raise ValueError(f"{recolor_type} requires at least two ring colors")
        if recolor_type == "nested_ring_color_reverse":
            color_map = {
                value: color_cycle[-index - 1]
                for index, value in enumerate(color_cycle)
            }
        else:
            color_map = {
                value: color_cycle[index - 1]
                for index, value in enumerate(color_cycle)
            }
        return [
            [
                color_map.get(value, value)
                for value in row
            ]
            for row in grid
        ]

    if recolor_type == "object_bbox_pattern_recolor":
        object_color = color1
        target_color = color2
        if object_color in (None, 0):
            raise ValueError("object_bbox_pattern_recolor requires a non-background object color")
        if target_color in (None, 0, object_color):
            raise ValueError("object_bbox_pattern_recolor requires a distinct target color")

        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("object_bbox_pattern_recolor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("object_bbox_pattern_recolor requires a rectangular grid")

        pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == object_color
        ]
        if not pixels:
            raise ValueError("object_bbox_pattern_recolor found no object pixels")
        min_row = min(row for row, _ in pixels)
        max_row = max(row for row, _ in pixels)
        min_col = min(col for _, col in pixels)
        max_col = max(col for _, col in pixels)

        transformed_grid = copy.deepcopy(grid)
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                if transformed_grid[row][col] not in (0, object_color):
                    transformed_grid[row][col] = target_color
        return transformed_grid

    if recolor_type == "mask_color_to_other":
        source_color = color1
        if source_color in (None, 0):
            raise ValueError("mask_color_to_other requires a non-background source color")
        target_color = color2
        if target_color == "other_non_background":
            other_colors = sorted({
                value
                for row in grid
                for value in row
                if value not in (0, source_color)
            })
            if len(other_colors) != 1:
                raise ValueError("mask_color_to_other requires exactly one other foreground color")
            target_color = other_colors[0]
        if target_color in (None, 0, source_color):
            raise ValueError("mask_color_to_other requires a distinct target color")
        return [
            [
                target_color if value == source_color else 0
                for value in row
            ]
            for row in grid
        ]

    if recolor_type == "periodic_column_mod3_recolor":
        if color1 is None or color2 is None:
            raise ValueError("periodic_column_mod3_recolor requires source and target colors")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if any(len(row) != cols for row in grid):
            raise ValueError("periodic_column_mod3_recolor requires a rectangular grid")
        transformed_grid = copy.deepcopy(grid)
        for row in range(rows):
            for col in range(cols):
                if col % 3 == 0 and transformed_grid[row][col] == color1:
                    transformed_grid[row][col] = color2
        return transformed_grid

    if recolor_type == "width_parity_column_recolor":
        source_color = color1
        target_color = color2
        if source_color in (None, 0):
            raise ValueError("width_parity_column_recolor requires a non-background source color")
        if target_color in (None, 0, source_color):
            raise ValueError("width_parity_column_recolor requires a distinct target color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("width_parity_column_recolor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("width_parity_column_recolor requires a rectangular grid")

        target_parity = 0 if cols % 2 else 1
        transformed_grid = copy.deepcopy(grid)
        changed = False
        for row in range(rows):
            for col in range(cols):
                if transformed_grid[row][col] == source_color and col % 2 == target_parity:
                    transformed_grid[row][col] = target_color
                    changed = True
        if not changed:
            raise ValueError("width_parity_column_recolor produced no change")
        return transformed_grid

    if recolor_type == "full_span_points_to_lines":
        ignore_color = color1
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("full_span_points_to_lines requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("full_span_points_to_lines requires a rectangular grid")

        positions_by_color = defaultdict(list)
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value in (0, ignore_color):
                    continue
                positions_by_color[value].append((row, col))
        best = None
        for value, positions in positions_by_color.items():
            full_span_rows = []
            for row in sorted({point_row for point_row, _ in positions}):
                row_cols = sorted(col for point_row, col in positions if point_row == row)
                if row_cols == [0, cols - 1]:
                    full_span_rows.append(row)
            full_span_cols = []
            for col in sorted({point_col for _, point_col in positions}):
                col_rows = sorted(row for row, point_col in positions if point_col == col)
                if col_rows == [0, rows - 1]:
                    full_span_cols.append(col)
            score = len(full_span_rows) + len(full_span_cols)
            if score and (best is None or (score, value) > (best[0], best[1])):
                best = (score, value, full_span_rows, full_span_cols)
        if best is None:
            raise ValueError("full_span_points_to_lines found no spanning endpoint pairs")
        _, line_color, strong_rows, strong_cols = best
        output = [[0 for _ in range(cols)] for _ in range(rows)]
        for row in strong_rows:
            for col in range(cols):
                output[row][col] = line_color
        for col in strong_cols:
            for row in range(rows):
                output[row][col] = line_color
        return output

    if recolor_type == "diagonal_modulo_cycle_synthesis":
        background_color = 0 if color1 is None else color1
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("diagonal_modulo_cycle_synthesis requires a non-empty grid")
        points = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if len(points) < 2:
            raise ValueError("diagonal_modulo_cycle_synthesis requires at least two points")
        for period in range(2, min(10, rows + cols) + 1):
            cycle = {}
            compatible = True
            for row, col, value in points:
                residue = (row + col) % period
                if residue in cycle and cycle[residue] != value:
                    compatible = False
                    break
                cycle[residue] = value
            if compatible and len(cycle) == period:
                return [
                    [cycle[(row + col) % period] for col in range(cols)]
                    for row in range(rows)
                ]
        raise ValueError("diagonal_modulo_cycle_synthesis found no complete modulo cycle")

    if recolor_type == "center_arm_plus_expansion":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("center_arm_plus_expansion requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("center_arm_plus_expansion requires a rectangular grid")
        pattern = (
            ("b", 0, "a", 0, "b"),
            (0, "b", "a", "b", 0),
            ("a", "a", "b", "a", "a"),
            (0, "b", "a", "b", 0),
            ("b", 0, "a", 0, "b"),
        )
        output = copy.deepcopy(grid)
        changed = False
        for row in range(1, rows - 1):
            for col in range(1, cols - 1):
                center = grid[row][col]
                if center == 0:
                    continue
                arms = [
                    grid[row - 1][col],
                    grid[row + 1][col],
                    grid[row][col - 1],
                    grid[row][col + 1],
                ]
                if len(set(arms)) != 1 or arms[0] in (0, center):
                    continue
                arm = arms[0]
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        value = pattern[dr + 2][dc + 2]
                        if value == 0:
                            continue
                        out_row = row + dr
                        out_col = col + dc
                        if 0 <= out_row < rows and 0 <= out_col < cols:
                            output[out_row][out_col] = arm if value == "a" else center
                            changed = True
        if not changed:
            raise ValueError("center_arm_plus_expansion produced no change")
        return output

    if recolor_type == "vertical_rays_from_separator":
        separator_color = color1
        short_ray_color = color2
        if separator_color in (None, 0):
            raise ValueError("vertical_rays_from_separator requires a separator color")
        if short_ray_color in (None, 0, separator_color):
            raise ValueError("vertical_rays_from_separator requires a short-ray color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("vertical_rays_from_separator requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("vertical_rays_from_separator requires a rectangular grid")
        separator_rows = [
            row
            for row, values in enumerate(grid)
            if len(set(values)) == 1 and values[0] == separator_color
        ]
        if len(separator_rows) != 1:
            raise ValueError("vertical_rays_from_separator requires one full separator row")
        separator_row = separator_rows[0]
        output = copy.deepcopy(grid)
        changed = False
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value in (0, separator_color):
                    continue
                if row < separator_row:
                    end = separator_row - 1 if value == short_ray_color else 0
                else:
                    end = separator_row + 1 if value == short_ray_color else rows - 1
                step = 1 if end >= row else -1
                for ray_row in range(row, end + step, step):
                    if output[ray_row][col] != value:
                        changed = True
                    output[ray_row][col] = value
        if not changed:
            raise ValueError("vertical_rays_from_separator produced no change")
        return output

    if recolor_type == "bar_extreme_rank_palette":
        bar_color = color1
        if bar_color in (None, 0):
            raise ValueError("bar_extreme_rank_palette requires a non-background bar color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("bar_extreme_rank_palette requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("bar_extreme_rank_palette requires a rectangular grid")
        heights = []
        for col in range(cols):
            colored_rows = [row for row in range(rows) if grid[row][col] == bar_color]
            if colored_rows:
                heights.append((len(colored_rows), col, min(colored_rows), max(colored_rows)))
        if len(heights) < 2:
            raise ValueError("bar_extreme_rank_palette requires at least two bars")
        tallest = max(heights)
        shortest = min(heights)
        output = [[0 for _ in range(cols)] for _ in range(rows)]
        for row in range(tallest[2], tallest[3] + 1):
            output[row][tallest[1]] = 1
        for row in range(shortest[2], shortest[3] + 1):
            output[row][shortest[1]] = 2
        return output

    if recolor_type == "single_seed_vertical_stripe_top_bottom":
        marker_color = color1
        if marker_color in (None, 0):
            raise ValueError("single_seed_vertical_stripe_top_bottom requires a marker color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("single_seed_vertical_stripe_top_bottom requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("single_seed_vertical_stripe_top_bottom requires a rectangular grid")
        points = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != 0
        ]
        if len(points) != 1:
            raise ValueError("single_seed_vertical_stripe_top_bottom requires one seed pixel")
        _, start_col, stripe_color = points[0]
        output = [[0 for _ in range(cols)] for _ in range(rows)]
        for row in range(rows):
            for col in range(start_col, cols, 2):
                output[row][col] = stripe_color
        for col in range(start_col + 1, cols, 4):
            output[0][col] = marker_color
        for col in range(start_col + 3, cols, 4):
            output[rows - 1][col] = marker_color
        return output

    if recolor_type == "nearest_edge_color":
        transformed_grid = copy.deepcopy(grid)
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("nearest_edge_color requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("nearest_edge_color requires a rectangular grid")

        marker_color = color1
        markers = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == marker_color
        ]
        if not markers:
            raise ValueError("nearest_edge_color requires marker pixels")

        edge_guides = []
        for row in range(rows):
            for col in range(cols):
                if row not in (0, rows - 1) and col not in (0, cols - 1):
                    continue
                value = grid[row][col]
                if value in (0, marker_color):
                    continue
                edge_guides.append((row, col, value))
        if len({value for _, _, value in edge_guides}) < 2:
            raise ValueError("nearest_edge_color requires at least two edge guide colors")

        for row, col in markers:
            _, _, guide_color = min(
                edge_guides,
                key=lambda guide: (
                    abs(guide[0] - row) + abs(guide[1] - col),
                    guide[0],
                    guide[1],
                    guide[2],
                ),
            )
            transformed_grid[row][col] = guide_color
        return transformed_grid

    if recolor_type == "marker_column_inheritance":
        transformed_grid = copy.deepcopy(grid)
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if not rows or not cols:
            return transformed_grid

        marker_row = color2 if color2 is not None else 0
        source_color = color1
        markers = [
            (col, grid[marker_row][col])
            for col in range(cols)
            if grid[marker_row][col] not in (0, source_color)
        ]
        if not markers:
            raise ValueError("marker_column_inheritance requires marker pixels")

        components = find_connected_components(
            grid,
            target_colors={source_color},
            background_color=0,
            connectivity=4,
        )
        for component in components:
            pixels = component["pixels"]
            center_col = sum(col for _, col in pixels) / len(pixels)
            _, marker_color = min(
                markers,
                key=lambda item: (abs(item[0] - center_col), item[0]),
            )
            for row, col in pixels:
                transformed_grid[row][col] = marker_color
        return transformed_grid

    if recolor_type == "marker_column_row_palette":
        marker_color = color1
        if marker_color in (None, 0):
            raise ValueError("marker_column_row_palette requires a marker color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("marker_column_row_palette requires a non-empty grid")
        palette = {0: 2, 1: 4, 2: 3}
        if cols > len(palette):
            raise ValueError("marker_column_row_palette expects at most three columns")
        output = []
        for row in grid:
            marker_cols = [col for col, value in enumerate(row) if value == marker_color]
            if len(marker_cols) != 1 or marker_cols[0] not in palette:
                raise ValueError("marker_column_row_palette requires one marker per row")
            output.append([palette[marker_cols[0]] for _ in row])
        return output

    if recolor_type == "column_lower_half_floor":
        source_color = color1
        target_color = color2
        if source_color in (None, 0):
            raise ValueError("column_lower_half_floor requires a non-background source color")
        if target_color in (None, 0, source_color):
            raise ValueError("column_lower_half_floor requires a distinct target color")

        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("column_lower_half_floor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("column_lower_half_floor requires a rectangular grid")

        transformed_grid = copy.deepcopy(grid)
        changed = False
        for col in range(cols):
            source_rows = [
                row
                for row in range(rows)
                if grid[row][col] == source_color
            ]
            if not source_rows:
                continue
            min_row = min(source_rows)
            max_row = max(source_rows)
            if source_rows != list(range(min_row, max_row + 1)):
                raise ValueError("column_lower_half_floor requires contiguous source spans")
            recolor_count = len(source_rows) // 2
            if recolor_count == 0:
                continue
            for row in source_rows[-recolor_count:]:
                transformed_grid[row][col] = target_color
                changed = True
        if not changed:
            raise ValueError("column_lower_half_floor produced no change")
        return transformed_grid

    if recolor_type == "component_size_code_palette":
        source_color = color1
        if source_color is None:
            raise ValueError("component_size_code_palette requires a source color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("component_size_code_palette requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("component_size_code_palette requires a rectangular grid")

        components = find_connected_components(
            grid,
            target_colors={source_color},
            background_color=None,
            connectivity=4,
        )
        if not components:
            raise ValueError("component_size_code_palette found no source components")

        transformed_grid = copy.deepcopy(grid)
        for component in components:
            pixels = component["pixels"]
            if len(pixels) == 1:
                code = 3
            elif len(pixels) == 2:
                code = 2
            else:
                code = 1
            for row, col in pixels:
                transformed_grid[row][col] = code
        return transformed_grid

    if recolor_type == "exact_rectangle_border_recolor":
        source_color = color1
        target_color = color2
        if source_color in (None, 0):
            raise ValueError("exact_rectangle_border_recolor requires a non-background source color")
        if target_color in (None, 0, source_color):
            raise ValueError("exact_rectangle_border_recolor requires a distinct target color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("exact_rectangle_border_recolor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("exact_rectangle_border_recolor requires a rectangular grid")

        components = find_connected_components(
            grid,
            target_colors={source_color},
            background_color=None,
            connectivity=4,
        )
        transformed_grid = copy.deepcopy(grid)
        changed = False
        for component in components:
            if not _is_exact_rectangle_border_pixels(component["pixels"]):
                continue
            for row, col in component["pixels"]:
                transformed_grid[row][col] = target_color
                changed = True
        if not changed:
            raise ValueError("exact_rectangle_border_recolor found no rectangle borders")
        return transformed_grid

    if recolor_type == "component_shape_multiplicity_palette":
        source_color = color1
        if source_color in (None, 0):
            raise ValueError("component_shape_multiplicity_palette requires a non-background source color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("component_shape_multiplicity_palette requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("component_shape_multiplicity_palette requires a rectangular grid")

        components = find_connected_components(
            grid,
            target_colors={source_color},
            background_color=None,
            connectivity=4,
        )
        if not components:
            raise ValueError("component_shape_multiplicity_palette found no source components")
        mask_counts = defaultdict(int)
        for component in components:
            mask_counts[_normalized_component_mask(component["pixels"])] += 1

        transformed_grid = copy.deepcopy(grid)
        for component in components:
            code = 1 if mask_counts[_normalized_component_mask(component["pixels"])] > 1 else 2
            for row, col in component["pixels"]:
                transformed_grid[row][col] = code
        return transformed_grid

    if recolor_type == "same_shape_color_outlier_recolor":
        target_color = color1
        if target_color in (None, 0):
            raise ValueError("same_shape_color_outlier_recolor requires a target color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("same_shape_color_outlier_recolor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("same_shape_color_outlier_recolor requires a rectangular grid")

        components = [
            component
            for component in find_connected_components(
                grid,
                target_colors=None,
                background_color=0,
                connectivity=4,
            )
            if component["color"] != target_color
        ]
        groups = defaultdict(list)
        for component in components:
            pixels = component["pixels"]
            min_row, max_row, min_col, max_col = find_bounding_rectangle(pixels)
            groups[_normalized_component_mask(pixels)].append({
                **component,
                "bbox": (min_row, max_row, min_col, max_col),
            })
        candidates = [
            group
            for group in groups.values()
            if len({component["color"] for component in group}) > 1
        ]
        if not candidates:
            raise ValueError("same_shape_color_outlier_recolor found no same-shape color outlier")
        group = max(
            candidates,
            key=lambda items: max((component["bbox"][0], component["bbox"][2]) for component in items),
        )
        selected = max(group, key=lambda component: (component["bbox"][0], component["bbox"][2]))
        transformed_grid = copy.deepcopy(grid)
        for row, col in selected["pixels"]:
            transformed_grid[row][col] = target_color
        return transformed_grid

    if recolor_type == "quadrant_points_to_center_corners":
        center_color = color1
        if center_color in (None, 0):
            raise ValueError("quadrant_points_to_center_corners requires a center color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("quadrant_points_to_center_corners requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("quadrant_points_to_center_corners requires a rectangular grid")
        components = find_connected_components(
            grid,
            target_colors=None,
            background_color=0,
            connectivity=4,
        )
        centers = [component for component in components if component["color"] == center_color]
        if len(centers) != 1:
            raise ValueError("quadrant_points_to_center_corners requires one center component")
        min_row, max_row, min_col, max_col = find_bounding_rectangle(centers[0]["pixels"])
        point_colors = []
        for component in components:
            if component["color"] == center_color or len(component["pixels"]) != 1:
                continue
            row, col = component["pixels"][0]
            point_colors.append((row, col, component["color"]))
        top_left = min((p for p in point_colors if p[0] < min_row and p[1] < min_col), default=None)
        top_right = min((p for p in point_colors if p[0] < min_row and p[1] > max_col), default=None)
        bottom_left = min((p for p in point_colors if p[0] > max_row and p[1] < min_col), default=None)
        bottom_right = min((p for p in point_colors if p[0] > max_row and p[1] > max_col), default=None)
        if any(item is None for item in (top_left, top_right, bottom_left, bottom_right)):
            raise ValueError("quadrant_points_to_center_corners requires one point in each quadrant")
        output = [[0 for _ in range(cols)] for _ in range(rows)]
        output[min_row][min_col] = top_left[2]
        output[min_row][max_col] = top_right[2]
        output[max_row][min_col] = bottom_left[2]
        output[max_row][max_col] = bottom_right[2]
        return output

    if recolor_type == "adjacent_two_three_transfer":
        delete_color = color1
        promote_color = color2
        if delete_color in (None, 0):
            raise ValueError("adjacent_two_three_transfer requires a delete color")
        if promote_color in (None, 0, delete_color):
            raise ValueError("adjacent_two_three_transfer requires a promote color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("adjacent_two_three_transfer requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("adjacent_two_three_transfer requires a rectangular grid")
        output = copy.deepcopy(grid)
        to_promote = set()
        to_delete = set()
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != promote_color:
                    continue
                for next_row, next_col in (
                    (row - 1, col),
                    (row + 1, col),
                    (row, col - 1),
                    (row, col + 1),
                ):
                    if 0 <= next_row < rows and 0 <= next_col < cols and grid[next_row][next_col] == delete_color:
                        to_promote.add((row, col))
                        to_delete.add((next_row, next_col))
        if not to_promote:
            raise ValueError("adjacent_two_three_transfer found no adjacent pairs")
        for row, col in to_delete:
            output[row][col] = 0
        for row, col in to_promote:
            output[row][col] = 8
        return output

    if recolor_type == "dominant_line_intersection_patch":
        patch_color = color1
        if patch_color in (None, 0):
            raise ValueError("dominant_line_intersection_patch requires a patch color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("dominant_line_intersection_patch requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("dominant_line_intersection_patch requires a rectangular grid")
        row_counts = defaultdict(int)
        col_counts = defaultdict(int)
        points = []
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == 0:
                    continue
                points.append((row, col, value))
                row_counts[(row, value)] += 1
                col_counts[(col, value)] += 1
        if not points:
            raise ValueError("dominant_line_intersection_patch found no foreground")
        horizontal_row, _ = max(row_counts, key=lambda item: row_counts[item])
        vertical_col, _ = max(col_counts, key=lambda item: col_counts[item])
        output = copy.deepcopy(grid)
        for row in range(max(0, horizontal_row - 1), min(rows, horizontal_row + 2)):
            for col in range(max(0, vertical_col - 1), min(cols, vertical_col + 2)):
                if (row, col) != (horizontal_row, vertical_col):
                    output[row][col] = patch_color
        return output

    if recolor_type == "mirror_gray_components_across_red_frame_sides":
        frame_color = color1
        mirror_color = color2
        if frame_color in (None, 0):
            raise ValueError("mirror_gray_components_across_red_frame_sides requires a frame color")
        if mirror_color in (None, 0, frame_color):
            raise ValueError("mirror_gray_components_across_red_frame_sides requires a mirror color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("mirror_gray_components_across_red_frame_sides requires a non-empty grid")
        frame_points = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == frame_color
        ]
        if not frame_points:
            raise ValueError("mirror_gray_components_across_red_frame_sides found no frame")
        frame_min_row = min(row for row, _ in frame_points)
        frame_max_row = max(row for row, _ in frame_points)
        frame_min_col = min(col for _, col in frame_points)
        frame_max_col = max(col for _, col in frame_points)
        frame_mid_row = (frame_min_row + frame_max_row) / 2
        frame_mid_col = (frame_min_col + frame_max_col) / 2
        output = copy.deepcopy(grid)
        changed = False

        def write_translated(component, row_fn, col_fn):
            nonlocal changed
            for row, col in component["pixels"]:
                out_row = row_fn(row)
                out_col = col_fn(col)
                if 0 <= out_row < rows and 0 <= out_col < cols:
                    output[out_row][out_col] = mirror_color
                    changed = True

        for component in find_connected_components(
            grid,
            target_colors={mirror_color},
            background_color=0,
            connectivity=4,
        ):
            for row, col in component["pixels"]:
                output[row][col] = 0
            min_row, max_row, min_col, max_col = find_bounding_rectangle(component["pixels"])
            if max_row < frame_min_row:
                candidates = [row for row, _ in frame_points if row < frame_mid_row]
                if not candidates:
                    raise ValueError("mirror_gray_components_across_red_frame_sides missing top boundary")
                boundary = max(candidates)
                write_translated(
                    component,
                    lambda row, max_row=max_row, boundary=boundary: boundary + 1 + (max_row - row),
                    lambda col: col,
                )
            elif min_row > frame_max_row:
                candidates = [row for row, _ in frame_points if row > frame_mid_row]
                if not candidates:
                    raise ValueError("mirror_gray_components_across_red_frame_sides missing bottom boundary")
                boundary = min(candidates)
                write_translated(
                    component,
                    lambda row, min_row=min_row, boundary=boundary: boundary - 1 - (row - min_row),
                    lambda col: col,
                )
            elif max_col < frame_min_col:
                candidates = [col for _, col in frame_points if col < frame_mid_col]
                if not candidates:
                    raise ValueError("mirror_gray_components_across_red_frame_sides missing left boundary")
                boundary = max(candidates)
                write_translated(
                    component,
                    lambda row: row,
                    lambda col, max_col=max_col, boundary=boundary: boundary + 1 + (max_col - col),
                )
            elif min_col > frame_max_col:
                candidates = [col for _, col in frame_points if col > frame_mid_col]
                if not candidates:
                    raise ValueError("mirror_gray_components_across_red_frame_sides missing right boundary")
                boundary = min(candidates)
                write_translated(
                    component,
                    lambda row: row,
                    lambda col, min_col=min_col, boundary=boundary: boundary - 1 - (col - min_col),
                )
        if not changed:
            raise ValueError("mirror_gray_components_across_red_frame_sides produced no change")
        return output

    if recolor_type == "component_bbox_topology_palette":
        source_color = color1
        if source_color in (None, 0):
            raise ValueError("component_bbox_topology_palette requires a non-background source color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("component_bbox_topology_palette requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("component_bbox_topology_palette requires a rectangular grid")

        components = find_connected_components(
            grid,
            target_colors={source_color},
            background_color=None,
            connectivity=4,
        )
        if not components:
            raise ValueError("component_bbox_topology_palette found no source components")

        transformed_grid = copy.deepcopy(grid)
        for component in components:
            code = _component_bbox_topology_code(component["pixels"])
            for row, col in component["pixels"]:
                transformed_grid[row][col] = code
        return transformed_grid

    if recolor_type == "hollow_square_to_plus":
        source_color = color1
        target_color = color2
        if source_color in (None, 0):
            raise ValueError("hollow_square_to_plus requires a non-background source color")
        if target_color in (None, 0, source_color):
            raise ValueError("hollow_square_to_plus requires a distinct target color")
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("hollow_square_to_plus requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("hollow_square_to_plus requires a rectangular grid")

        transformed_grid = copy.deepcopy(grid)
        changed = False
        for row in range(rows - 2):
            for col in range(cols - 2):
                border = [
                    (row + dr, col + dc)
                    for dr in range(3)
                    for dc in range(3)
                    if dr in (0, 2) or dc in (0, 2)
                ]
                if any(grid[r][c] != source_color for r, c in border):
                    continue
                if grid[row + 1][col + 1] != 0:
                    continue
                for dr in range(3):
                    for dc in range(3):
                        transformed_grid[row + dr][col + dc] = 0
                for dr, dc in ((0, 1), (1, 0), (1, 1), (1, 2), (2, 1)):
                    transformed_grid[row + dr][col + dc] = target_color
                changed = True
        if not changed:
            raise ValueError("hollow_square_to_plus found no hollow 3x3 squares")
        return transformed_grid

    if recolor_type == "fill_blank":
        transformed_grid = copy.deepcopy(grid)
        objects = find_connected_components(
            grid, target_colors={color1}, connectivity=8
        )

        for idx, obj in enumerate(objects, 1):
            pixels = obj["pixels"]
            rows = [cell[0] for cell in pixels]
            min_row = min(rows)
            max_row = max(rows)
            height = max_row - min_row + 1
            midpoint = min_row + height // 2

            for i, j in pixels:
                if i >= midpoint:
                    transformed_grid[i][j] = color2

        return transformed_grid

    elif recolor_type == "moving_recolor":
        num_rows, num_cols = len(grid), len(grid[0])
        new_grid = [[color1] * num_cols for _ in range(num_rows)]
        shift_map = {
            "left": (0, -1, range(num_rows), range(num_cols)),
            "right": (0, 1, range(num_rows), reversed(range(num_cols))),
            "up": (-1, 0, range(num_rows), range(num_cols)),
            "down": (1, 0, range(num_rows), reversed(range(num_cols))),
        }
        dr, dc, row_iter, col_iter = shift_map[shifting_direction]
        for r in row_iter:
            for c in col_iter:
                if grid[r][c] != 0:
                    new_r, new_c = r + dr, c + dc
                    if 0 <= new_r < num_rows and 0 <= new_c < num_cols:
                        new_grid[new_r][new_c] = grid[r][c]
        return new_grid

    if recolor_type == "nearest_pixels":
        objects = find_connected_components(grid, background_color=0, connectivity=4)
        transformed_grid = [[0 for _ in range(len(grid[0]))] for _ in range(len(grid))]
        recolored_object_pixels = set()
        for obj in objects:
            if obj["color"] == color1:
                nearest_color = find_nearest_color(grid, obj)
                for r, c in obj["pixels"]:
                    transformed_grid[r][c] = nearest_color
                    recolored_object_pixels.add((r, c))
        for r in range(len(grid)):
            for c in range(len(grid[0])):
                if (r, c) not in recolored_object_pixels:
                    transformed_grid[r][c] = 0
        return transformed_grid

    elif recolor_type == "line_inheritance":
        return [[row[0] if cell == color1 else cell for cell in row] for row in grid]

    elif recolor_type == "square_spread":
        H, W = len(grid), len(grid[0])
        squares = defaultdict(list)
        for i in range(H - 1):
            for j in range(W - 1):
                square = (
                    (grid[i][j], grid[i][j + 1]),
                    (grid[i + 1][j], grid[i + 1][j + 1]),
                )
                if any(v != 0 for row in square for v in row):
                    squares[square].append((i, j))
        unique = next(
            ((sq, pos[0]) for sq, pos in squares.items() if len(pos) == 1), None
        )
        unique_square, (i, j) = unique
        color = next(v for row in unique_square for v in row if v != 0)
        positions = {
            (p, q)
            for offset in [0, 1]
            for k in range(W - 1)
            for p in [i + offset, i + offset + 1]
            for q in [k, k + 1]
            if grid[p][q] != 0
        }.union(
            {
                (p, q)
                for offset in [0, 1]
                for k in range(H - 1)
                for p in [k, k + 1]
                for q in [j + offset, j + offset + 1]
                if grid[p][q] != 0
            }
        )
        for p, q in positions:
            grid[p][q] = color
        return grid

    elif recolor_type == "border_based":
        for comp in find_connected_components(grid, target_colors={color1}):
            min_r, max_r, min_c, max_c = find_bounding_rectangle(comp["pixels"])
            ir_min, ir_max, ic_min, ic_max = min_r + 1, max_r - 1, min_c + 1, max_c - 1
            sub = extract_rectangle(grid, (ir_min, ic_min, ir_max, ic_max))
            unique = {c for row in sub for c in row if c not in (0, color1)}
            if len(unique) < 2:
                continue
            c1, c2 = list(unique)[:2]
            sub_np = np.array(sub)
            sub_np = np.where(sub_np == c1, c2, np.where(sub_np == c2, c1, sub_np))
            for i, r in enumerate(range(ir_min, ir_max + 1)):
                grid[r][ic_min : ic_max + 1] = sub_np[i].tolist()
        return grid


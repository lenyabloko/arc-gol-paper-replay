import numpy as np
from collections import deque, Counter
import copy

try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def mirror_grid_based(
    grid, mirror_axis="diagonal", mirror_type="color", color1: int = 0, color2: int = 0
):
    if mirror_type == "color":
        for r, row in enumerate(grid):
            if color1 in row:
                c = row.index(color1)
                break
        else:
            return grid
        rows, cols = len(grid), len(grid[0]) if grid else 0
        new_grid = [[0] * cols for _ in range(rows)]
        for i in range(rows):
            for j in range(cols):
                val = grid[i][j]
                if val != 0:
                    mir_i, mir_j = 2 * r - i, 2 * c - j
                    if 0 <= mir_i < rows and 0 <= mir_j < cols:
                        new_grid[mir_i][mir_j] = val

        return new_grid

    elif mirror_type == "axis":
        if mirror_axis == "diagonal":
            transposed_grid = [list(col) for col in zip(*grid)]
        elif mirror_axis == "horizontal":
            transposed_grid = [row[::-1] for row in grid]
        elif mirror_axis == "vertical":
            transposed_grid = grid[::-1]
        else:
            raise ValueError(f"Wrong mirror axis! You provided {mirror_axis}")
        return transposed_grid

    elif mirror_type == "upside_down_each_object":
        grid_np = np.array(grid)
        new_grid = np.zeros_like(grid_np)
        unique_colors = np.unique(grid_np)
        for color in unique_colors[unique_colors != 0]:
            positions = np.argwhere(grid_np == color)
            if positions.size:
                min_r, min_c = positions.min(axis=0)
                max_r, max_c = positions.max(axis=0)
                subgrid = grid_np[min_r : max_r + 1, min_c : max_c + 1]
                flipped = np.flipud(subgrid == color) * color
                new_grid[min_r : max_r + 1, min_c : max_c + 1] = np.maximum(
                    new_grid[min_r : max_r + 1, min_c : max_c + 1], flipped
                )
        return new_grid.tolist()

    elif mirror_type == "upside_down":
        rows, cols = len(grid), len(grid[0])
        objects = find_connected_components(grid, background_color=0, connectivity=8)
        objects.sort(
            key=lambda obj: find_bounding_rectangle(obj["pixels"])[0]
        )  # Sort by min_row
        for obj in objects:
            min_row, max_row, min_col, max_col = find_bounding_rectangle(
                [(r, c) for r, c in obj["pixels"]]
            )
            target_min_row = rows - 1 - max_row
            vertical_shift = target_min_row - min_row
            obj["vertical_shift"] = vertical_shift
        new_grid = [[0 for _ in range(cols)] for _ in range(rows)]
        for obj in objects:
            vertical_shift = obj["vertical_shift"]
            color = obj["color"]
            for x, y in obj["pixels"]:
                new_x = x + vertical_shift
                if 0 <= new_x < rows:
                    new_grid[new_x][y] = color
                else:
                    raise IndexError(
                        f"Mirrored object exceeds the grid bounds at position ({new_x}, {y})."
                    )
        return new_grid

    elif mirror_type == "object_fit":
        color1_components = find_connected_all_directions_by_color(grid, color1)
        color2_components = find_connected_all_directions_by_color(grid, color2)
        color_bounds = [find_bounding_rectangle(c1) for c1 in color1_components]

        new_grid = copy.deepcopy(grid)

        for c2 in color2_components:
            for cbound_idx, _ in enumerate(color1_components):
                bounds = color_bounds[cbound_idx]
                if is_component_inside(c2, bounds):
                    min_row, max_row, min_col, max_col = bounds
                    center_row = (min_row + max_row) / 2
                    center_col = (min_col + max_col) / 2

                    mirrored_y = mirror_component(c2, "y", center_row, center_col)
                    if is_valid_duplication(
                        new_grid, mirrored_y, bounds, color1, color2
                    ):
                        for r, c in mirrored_y:
                            new_grid[r][c] = color2
                    else:
                        mirrored_x = mirror_component(c2, "x", center_row, center_col)
                        if is_valid_duplication(
                            new_grid, mirrored_x, bounds, color1, color2
                        ):
                            for r, c in mirrored_x:
                                new_grid[r][c] = color2
                    break

        return new_grid

    elif mirror_type == "fill":
        background_color = count_most_frequent_color_except_zero(grid)
        zero_components = find_connected_all_directions_by_color(grid, color=0)
        zero_component = max(zero_components, key=lambda comp: len(comp))
        min_row, max_row, min_col, max_col = find_bounding_rectangle(zero_component)
        all_colors = set(cell for row in grid for cell in row)
        target_colors = all_colors - {0, background_color}
        objects = find_connected_components(
            grid, target_colors=target_colors, background_color=background_color
        )
        for obj in objects:
            pixels = obj["pixels"]
            overlaps = any(
                min_row <= r <= max_row and min_col <= c <= max_col for r, c in pixels
            )
            if not overlaps:
                break

        obj_min_r, obj_max_r, obj_min_c, obj_max_c = find_bounding_rectangle(pixels)
        object_subgrid = extract_rectangle(
            grid, (obj_min_r, obj_min_c, obj_max_r, obj_max_c)
        )
        mirrored_object = [row[::-1] for row in object_subgrid]
        obj_height = len(mirrored_object)
        obj_width = len(mirrored_object[0])
        rect_height = max_row - min_row + 1
        rect_width = max_col - min_col + 1
        pad_top = (rect_height - obj_height) // 2
        pad_left = (rect_width - obj_width) // 2
        new_rectangle = [[0 for _ in range(rect_width)] for _ in range(rect_height)]
        for r in range(obj_height):
            for c in range(obj_width):
                target_r = r + pad_top
                target_c = c + pad_left
                if 0 <= target_r < rect_height and 0 <= target_c < rect_width:
                    new_rectangle[target_r][target_c] = mirrored_object[r][c]
        transformed_grid = [row.copy() for row in grid]
        for r in range(rect_height):
            for c in range(rect_width):
                transformed_grid[min_row + r][min_col + c] = new_rectangle[r][c]
        return transformed_grid

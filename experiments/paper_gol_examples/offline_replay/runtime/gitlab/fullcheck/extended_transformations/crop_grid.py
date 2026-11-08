from colorama import Fore, Style
from collections import deque, defaultdict, Counter
import copy
import numpy as np

try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def crop_grid_based(
    grid,
    corner: str = "right upper",
    crop_type: str = "corner_based",
    grid_size: int = 3,
    fill_color: int = 0,
    border_color: int = 0,
    fill_direction: str = "left_to_right",
    connect_all: bool = True,
):
    if crop_type == "symetrics_based":
        mirrored = tuple(row[::-1] for row in grid)
        color_to_fill = fill_color if mirrored == tuple(grid) else border_color
        return [[color_to_fill] * grid_size for _ in range(grid_size)]

    elif crop_type == "count_rectangle":
        positions = [
            (i, j)
            for i, row in enumerate(grid)
            for j, cell in enumerate(row)
            if cell == fill_color
        ]
        min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
        rectangle = [row[min_col : max_col + 1] for row in grid[min_row : max_row + 1]]
        other_colors = set()
        for row in rectangle:
            for cell in row:
                if cell != fill_color and cell != 0:
                    other_colors.add(cell)
        other_color = other_colors.pop()
        count_other_color = sum(
            cell == other_color for row in rectangle for cell in row
        )
        n = count_other_color
        output_grid = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
        for idx in range(min(n, grid_size**2)):
            row = idx // grid_size
            col = idx % grid_size
            output_grid[row][col] = other_color
        return output_grid

    elif crop_type == "crop_quadrants":
        positions = [
            (i, j)
            for i, row in enumerate(grid)
            for j, cell in enumerate(row)
            if cell == fill_color
        ]
        if not positions:
            raise ValueError(f"{Fore.RED}No pixels of color {fill_color} found in the grid.{Style.RESET_ALL}")
        min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
        enclosure = [row[min_col : max_col + 1] for row in grid[min_row : max_row + 1]]
        mid_row, mid_col = len(enclosure) // 2, len(enclosure[0]) // 2
        quadrants = {
            "top_left": [row[:mid_col] for row in enclosure[:mid_row]],
            "top_right": [row[mid_col:] for row in enclosure[:mid_row]],
            "bottom_left": [row[:mid_col] for row in enclosure[mid_row:]],
            "bottom_right": [row[mid_col:] for row in enclosure[mid_row:]],
        }
        output_grid = [[0, 0], [0, 0]]
        quadrant_mapping = {
            "top_left": (0, 0),
            "top_right": (0, 1),
            "bottom_left": (1, 0),
            "bottom_right": (1, 1),
        }
        for name, quadrant in quadrants.items():
            unique = {cell for row in quadrant for cell in row} - {0, border_color}
            if len(unique) == 1:
                color = unique.pop()
                i, j = quadrant_mapping[name]
                output_grid[i][j] = color
        return output_grid

    elif crop_type == "cross_crop":
        num_rows, num_cols = len(grid), len(grid[0])
        cross_color = None
        cross_row = cross_col = None
        for r in range(num_rows):
            if len(set(grid[r])) == 1 and grid[r][0] != 0:
                cross_color = grid[r][0]
                cross_row = r
                break
        for c in range(num_cols):
            col = [grid[r][c] for r in range(num_rows)]
            if len(set(col)) == 1 and col[0] == cross_color:
                cross_col = c
                break
        quadrants = []
        for rs in [slice(0, cross_row), slice(cross_row + 1, num_rows)]:
            for cs in [slice(0, cross_col), slice(cross_col + 1, num_cols)]:
                subgrid = [row[cs] for row in grid[rs]]
                quadrants.append(subgrid)

        def process_quadrant(subgrid):
            positions = [
                (i, j)
                for i, row in enumerate(subgrid)
                for j, cell in enumerate(row)
                if cell != 0 and cell != cross_color
            ]
            if positions:
                min_r = min(i for i, _ in positions)
                max_r = max(i for i, _ in positions)
                min_c = min(j for _, j in positions)
                max_c = max(j for _, j in positions)
                cropped = [
                    [
                        cell if cell != cross_color else 0
                        for cell in row[min_c : max_c + 1]
                    ]
                    for row in subgrid[min_r : max_r + 1]
                ]
            else:
                cropped = []
            padded = [[0] * grid_size for _ in range(grid_size)]
            cr, cc = len(cropped), len(cropped[0]) if cropped else 0
            pr, pc = (grid_size - cr) // 2, (grid_size - cc) // 2
            for i in range(cr):
                for j in range(cc):
                    padded[pr + i][pc + j] = cropped[i][j]
            return padded

        output_quadrants = [process_quadrant(q) for q in quadrants]
        output = []
        for i in range(grid_size):
            output.append(output_quadrants[0][i] + output_quadrants[1][i])
        for i in range(grid_size):
            output.append(output_quadrants[2][i] + output_quadrants[3][i])
        return output

    elif crop_type == "most_frequent_color_based_grid":
        color_to_fill = count_most_frequent_color_except_zero(grid)
        if color_to_fill is None:
            raise ValueError(f"{Fore.RED}No colors found in the grid except zero.{Style.RESET_ALL}")
        transformed_grid = [
            [color_to_fill for _ in range(grid_size)] for _ in range(grid_size)
        ]
        return transformed_grid

    elif crop_type == "object_symmetry":
        objects = find_objects(grid)
        symmetric_objects = []
        for obj in objects:
            positions = [(i, j) for i, j, color in obj]
            min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
            local_grid = [
                [grid[i][j] for j in range(min_col, max_col + 1)]
                for i in range(min_row, max_row + 1)
            ]
            is_symmetric = all(row == row[::-1] for row in local_grid)
            if is_symmetric:
                symmetric_objects.append(obj)
        sym_obj = symmetric_objects[0]
        positions = [(i, j) for i, j, color in sym_obj]
        min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
        desired_grid = [
            [grid[i][j] for j in range(min_col, max_col + 1)]
            for i in range(min_row, max_row + 1)
        ]
        return desired_grid

    elif crop_type == "nearest_corner_crop":
        grid_copy = copy.deepcopy(grid)
        height, width = len(grid), len(grid[0])
        objects = find_objects(grid_copy)
        placed_corners = set()
        corners_coords = {
            "top-left": (0, 0),
            "top-right": (0, width - 1),
            "bottom-left": (height - 1, 0),
            "bottom-right": (height - 1, width - 1),
        }

        for object_pixels in objects:
            top = min(i for i, j, _ in object_pixels)
            bottom = max(i for i, j, _ in object_pixels)
            left = min(j for i, j, _ in object_pixels)
            right = max(j for i, j, _ in object_pixels)
            obj_h, obj_w = bottom - top + 1, right - left + 1
            center = ((top + bottom) / 2, (left + right) / 2)

            distances = {
                corner: ((center[0] - y) ** 2 + (center[1] - x) ** 2)
                for corner, (y, x) in corners_coords.items()
                if corner not in placed_corners
            }
            nearest_corner = min(distances, key=distances.get)
            placed_corners.add(nearest_corner)

            new_top = 0 if "top" in nearest_corner else height - obj_h
            new_left = 0 if "left" in nearest_corner else width - obj_w
            object_pixels_rel = [(i - top, j - left, v) for i, j, v in object_pixels]

            for i, j, _ in object_pixels:
                grid_copy[i][j] = 0
            for i_rel, j_rel, v in object_pixels_rel:
                i_new, j_new = new_top + i_rel, new_left + j_rel
                if 0 <= i_new < height and 0 <= j_new < width:
                    grid_copy[i_new][j_new] = v
                else:
                    raise IndexError(
                        f"Cannot place pixel at ({i_new}, {j_new}) - out of bounds"
                    )

        transformed_grid = resize_grid(grid_copy, grid_size)
        return transformed_grid

    elif crop_type == "most_frequent_color_based_flat":
        color_counts = Counter(color for row in grid for color in row if color != 0)
        if not color_counts:
            raise ValueError(f"{Fore.RED}No colors found in the grid except zero.{Style.RESET_ALL}")
        color_to_fill, count = color_counts.most_common(1)[0]
        return [[color_to_fill] * count]

    elif crop_type == "gray_columns_to_color_rows":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("gray_columns_to_color_rows requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("gray_columns_to_color_rows requires a rectangular grid")
        gray_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == 5
        ]
        if not gray_pixels:
            raise ValueError("gray_columns_to_color_rows found no gray canvas")
        gray_height = max(row for row, _ in gray_pixels) - min(row for row, _ in gray_pixels) + 1
        gray_width = max(col for _, col in gray_pixels) - min(col for _, col in gray_pixels) + 1

        row_colors = []
        for row in range(rows):
            nonzero = [value for value in grid[row] if value not in (0, 5)]
            if nonzero and len(set(nonzero)) == 1:
                value = nonzero[0]
                if value not in row_colors:
                    row_colors.append(value)
        if len(row_colors) == gray_height:
            return [[value for _ in range(gray_width)] for value in row_colors]

        col_colors = []
        for col in range(cols):
            nonzero = [
                grid[row][col]
                for row in range(rows)
                if grid[row][col] not in (0, 5)
            ]
            if nonzero and len(set(nonzero)) == 1:
                value = nonzero[0]
                if value not in col_colors:
                    col_colors.append(value)
        if len(col_colors) == gray_width:
            return [[value for value in col_colors] for _ in range(gray_height)]
        raise ValueError("gray_columns_to_color_rows could not align color runs to gray canvas")

    elif crop_type == "zero_bbox_horizontal_mirror_crop":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("zero_bbox_horizontal_mirror_crop requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("zero_bbox_horizontal_mirror_crop requires a rectangular grid")
        zero_points = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == 0
        ]
        if not zero_points:
            raise ValueError("zero_bbox_horizontal_mirror_crop found no zero bbox")
        min_row = min(row for row, _ in zero_points)
        max_row = max(row for row, _ in zero_points)
        min_col = min(col for _, col in zero_points)
        max_col = max(col for _, col in zero_points)
        height = max_row - min_row + 1
        width = max_col - min_col + 1
        mirror_col = cols - max_col - 1
        if mirror_col < 0 or mirror_col + width > cols:
            raise ValueError("zero_bbox_horizontal_mirror_crop mirror bbox is out of bounds")
        mirrored = [
            row[mirror_col : mirror_col + width]
            for row in grid[min_row : min_row + height]
        ]
        return [row[::-1] for row in mirrored]

    elif crop_type == "two_panel_blank_intersection":
        if not grid or not grid[0] or len(grid[0]) < 7:
            raise ValueError("two_panel_blank_intersection requires width at least 7")
        output = []
        for row in grid:
            left = row[:3]
            right = row[4:7]
            output.append([3 if left[col] == 0 and right[col] == 0 else 0 for col in range(3)])
        return output

    elif crop_type == "grouped_span_mode_matrix":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("grouped_span_mode_matrix requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("grouped_span_mode_matrix requires a rectangular grid")
        nonzero_rows = [
            row for row in range(rows)
            if any(grid[row][col] != 0 for col in range(cols))
        ]
        nonzero_cols = [
            col for col in range(cols)
            if any(grid[row][col] != 0 for row in range(rows))
        ]
        if not nonzero_rows or not nonzero_cols:
            raise ValueError("grouped_span_mode_matrix found no foreground spans")

        def grouped_spans(indices, signature):
            result = []
            start = previous = indices[0]
            previous_signature = signature(previous)
            for index in indices[1:]:
                current_signature = signature(index)
                if index == previous + 1 and current_signature == previous_signature:
                    previous = index
                else:
                    result.append((start, previous + 1))
                    start = previous = index
                    previous_signature = current_signature
            result.append((start, previous + 1))
            return result

        row_spans = grouped_spans(
            nonzero_rows,
            lambda row: tuple(grid[row][col] for col in range(cols)),
        )
        col_spans = grouped_spans(
            nonzero_cols,
            lambda col: tuple(grid[row][col] for row in range(rows)),
        )
        output = []
        for row_start, row_end in row_spans:
            output_row = []
            for col_start, col_end in col_spans:
                values = [
                    grid[row][col]
                    for row in range(row_start, row_end)
                    for col in range(col_start, col_end)
                    if grid[row][col] != 0
                ]
                if not values:
                    raise ValueError("grouped_span_mode_matrix found an empty non-background span")
                output_row.append(Counter(values).most_common(1)[0][0])
            output.append(output_row)
        return output

    elif crop_type == "adjacent_blocks_indicator":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("adjacent_blocks_indicator requires a non-empty grid")
        blocks = [
            component
            for component in find_connected_components(
                grid,
                target_colors={2},
                background_color=0,
                connectivity=4,
            )
            if len(component["pixels"]) == 4
        ]
        if len(blocks) != 2:
            raise ValueError("adjacent_blocks_indicator requires two 2-blocks")
        adjacent_to_both = False
        for component in find_connected_components(
            grid,
            target_colors={8},
            background_color=0,
            connectivity=4,
        ):
            component_pixels = set(component["pixels"])
            touches = []
            for block in blocks:
                touches.append(any(
                    (row + dr, col + dc) in component_pixels
                    for row, col in block["pixels"]
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
                ))
            if all(touches):
                adjacent_to_both = True
                break
        return [[8 if adjacent_to_both else 0]]

    elif crop_type == "crop_marker_component_replace_marker":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("crop_marker_component_replace_marker requires a non-empty grid")
        marker_color = 8
        visited = set()
        for start_row in range(rows):
            for start_col in range(cols):
                if grid[start_row][start_col] == 0 or (start_row, start_col) in visited:
                    continue
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                pixels = []
                while stack:
                    row, col = stack.pop()
                    pixels.append((row, col))
                    for next_row, next_col in (
                        (row - 1, col),
                        (row + 1, col),
                        (row, col - 1),
                        (row, col + 1),
                    ):
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited or grid[next_row][next_col] == 0:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                values = Counter(grid[row][col] for row, col in pixels)
                if marker_color not in values:
                    continue
                non_marker = [value for value in values if value != marker_color]
                if len(non_marker) != 1:
                    continue
                replacement = non_marker[0]
                min_row = min(row for row, _ in pixels)
                max_row = max(row for row, _ in pixels)
                min_col = min(col for _, col in pixels)
                max_col = max(col for _, col in pixels)
                return [
                    [
                        replacement if grid[row][col] == marker_color else grid[row][col]
                        for col in range(min_col, max_col + 1)
                    ]
                    for row in range(min_row, max_row + 1)
                ]
        raise ValueError("crop_marker_component_replace_marker found no marker component")

    elif crop_type == "separator_partition_shape_grid":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_partition_shape_grid requires a non-empty grid")
        counts = Counter(value for row in grid for value in row)
        if len(counts) < 2:
            raise ValueError("separator_partition_shape_grid requires at least two colors")
        main_color = counts.most_common(1)[0][0]
        separator_color = counts.most_common(2)[1][0]
        full_rows = [
            row
            for row, values in enumerate(grid)
            if all(value == separator_color for value in values)
        ]
        full_cols = [
            col
            for col in range(cols)
            if all(grid[row][col] == separator_color for row in range(rows))
        ]
        if not full_rows and not full_cols:
            raise ValueError("separator_partition_shape_grid found no separators")
        return [
            [main_color for _ in range(len(full_cols) + 1)]
            for _ in range(len(full_rows) + 1)
        ]

    elif crop_type == "cross_separator_reflect_mask":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("cross_separator_reflect_mask requires a non-empty grid")
        split_rows = [
            (row, values[0])
            for row, values in enumerate(grid)
            if values and values[0] != 0 and len(set(values)) == 1
        ]
        split_cols = []
        for col in range(cols):
            values = [grid[row][col] for row in range(rows)]
            if values and values[0] != 0 and len(set(values)) == 1:
                split_cols.append((col, values[0]))
        if not split_rows or not split_cols:
            raise ValueError("cross_separator_reflect_mask requires full row/col separators")
        split_row, separator_color = split_rows[0]
        matching_cols = [col for col, col_color in split_cols if col_color == separator_color]
        if not matching_cols:
            raise ValueError("cross_separator_reflect_mask requires matching separator colors")
        split_col = matching_cols[0]
        out_rows = rows - 1
        out_cols = cols - 1
        output = [[0 for _ in range(out_cols)] for _ in range(out_rows)]
        mask = [
            (
                row if row < split_row else row - 1,
                col if col < split_col else col - 1,
            )
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] not in (0, separator_color)
        ]
        for row, col in mask:
            for out_row, out_col in (
                (row, col),
                (out_rows - 1 - row, col),
                (row, out_cols - 1 - col),
                (out_rows - 1 - row, out_cols - 1 - col),
            ):
                output[out_row][out_col] = separator_color
        return output

    elif crop_type == "frame_pattern_overlay":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("frame_pattern_overlay requires a non-empty grid")
        four_points = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == 4
        ]
        if not four_points:
            raise ValueError("frame_pattern_overlay requires frame corner color 4")
        min_row = min(row for row, _ in four_points)
        max_row = max(row for row, _ in four_points)
        min_col = min(col for _, col in four_points)
        max_col = max(col for _, col in four_points)
        output = [
            row[min_col : max_col + 1]
            for row in grid[min_row : max_row + 1]
        ]
        pattern_pixels = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != 0
            and not (min_row <= row <= max_row and min_col <= col <= max_col)
        ]
        if not pattern_pixels:
            return output
        pattern_min_row = min(row for row, _, _ in pattern_pixels)
        pattern_max_row = max(row for row, _, _ in pattern_pixels)
        pattern_min_col = min(col for _, col, _ in pattern_pixels)
        pattern_max_col = max(col for _, col, _ in pattern_pixels)
        pattern = [
            row[pattern_min_col : pattern_max_col + 1]
            for row in grid[pattern_min_row : pattern_max_row + 1]
        ]
        frame_left_colors = [
            grid[row][min_col]
            for row in range(min_row + 1, max_row)
            if grid[row][min_col] != 0
        ]
        frame_left = Counter(frame_left_colors).most_common(1)[0][0] if frame_left_colors else None
        pattern_left_colors = [row[0] for row in pattern if row[0] != 0]
        pattern_right_colors = [row[-1] for row in pattern if row[-1] != 0]
        pattern_left = Counter(pattern_left_colors).most_common(1)[0][0] if pattern_left_colors else None
        pattern_right = Counter(pattern_right_colors).most_common(1)[0][0] if pattern_right_colors else None
        if frame_left is not None and pattern_left != frame_left and pattern_right == frame_left:
            pattern = [row[::-1] for row in pattern]
        for row, values in enumerate(pattern):
            for col, value in enumerate(values):
                if value == 0:
                    continue
                out_row = 1 + row
                out_col = 1 + col
                if 0 <= out_row < len(output) and 0 <= out_col < len(output[0]):
                    output[out_row][out_col] = value
        return output

    elif crop_type == "delta_max" or crop_type == "delta_min":
        objects = find_connected_components(grid, target_colors={1}, background_color=0)
        if not objects:
            raise ValueError(f"{Fore.RED}No objects of color 1 found in the grid.{Style.RESET_ALL}")

        def delta(obj):
            positions = obj["pixels"]
            min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
            area = (max_row - min_row + 1) * (max_col - min_col + 1)
            delta_value = area - len(positions)
            return delta_value

        if crop_type == "delta_max":
            selected_object = max(objects, key=delta)
        else:
            selected_object = min(objects, key=delta)
        positions = selected_object["pixels"]
        min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
        transformed_grid = [
            row[min_col : max_col + 1] for row in grid[min_row : max_row + 1]
        ]
        return transformed_grid

    elif crop_type == "extract_colors_adjust":
        groups = [[row] for i, row in enumerate(grid) if i == 0 or row != grid[i - 1]]
        split_indices = [
            i
            for i in range(1, len(groups[0][0]))
            if groups[0][0][i] != groups[0][0][i - 1]
        ]
        split_indices = [0] + split_indices + [len(groups[0][0])]
        desired_grid = [
            [group[0][start] for start in split_indices[:-1]] for group in groups
        ]
        return desired_grid

    elif crop_type == "extract_colors":
        color_counts = Counter(val for row in grid for val in row)
        bg = color_counts.most_common(1)[0][0]
        objects, visited, height, width = (
            [],
            set(),
            len(grid),
            len(grid[0]) if grid else 0,
        )
        for i in range(height):
            for j in range(width):
                if (i, j) not in visited and grid[i][j] != bg:
                    queue, component = deque([(i, j)]), set()
                    while queue:
                        x, y = queue.popleft()
                        if (x, y) in visited or grid[x][y] == bg:
                            continue
                        visited.add((x, y))
                        component.add((x, y))
                        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < height and 0 <= ny < width:
                                queue.append((nx, ny))
                    objects.append(component)
        first = objects[0]
        min_r, max_r = min(i for i, _ in first), max(i for i, _ in first)
        min_c, max_c = min(j for _, j in first), max(j for _, j in first)
        sub = tuple(
            tuple(grid[i][j] for j in range(min_c, max_c + 1))
            for i in range(min_r, max_r + 1)
        )
        dedup = tuple(dict.fromkeys(sub))
        rotated = tuple(zip(*dedup[::-1]))
        dedup_rot = tuple(dict.fromkeys(rotated))
        rotated_final = tuple(zip(*dedup_rot))[::-1]
        return tuple(tuple(row) for row in rotated_final)

    elif crop_type == "inferior_based":
        objects = find_connected_components(grid, background_color=0)
        counts = []
        for obj in objects:
            positions = obj["pixels"]
            min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
            subgrid = [
                row[min_col : max_col + 1] for row in grid[min_row : max_row + 1]
            ]

            rows = len(subgrid)
            cols = len(subgrid[0])
            visited = [[False] * cols for _ in range(rows)]

            queue = deque()
            for i in range(rows):
                for j in range(cols):
                    if (i == 0 or i == rows - 1 or j == 0 or j == cols - 1) and subgrid[
                        i
                    ][j] == 0:
                        queue.append((i, j))
                        visited[i][j] = True
            while queue:
                x, y = queue.popleft()
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < rows and 0 <= ny < cols and not visited[nx][ny]:
                        if subgrid[nx][ny] == 0:
                            visited[nx][ny] = True
                            queue.append((nx, ny))
            inferior_count = 0
            for i in range(rows):
                for j in range(cols):
                    if subgrid[i][j] == 0 and not visited[i][j]:
                        inferior_count += 1
            counts.append({"color": obj["color"], "count": inferior_count})
        output_grid = [[0] * grid_size for _ in range(grid_size)]
        current_row = 0
        for item in counts:
            color = item["color"]
            count = item["count"]
            while count > 0 and current_row < grid_size:
                pixels_to_place = min(count, grid_size)
                for col in range(pixels_to_place):
                    output_grid[current_row][col] = color
                count -= pixels_to_place
                current_row += 1
        return output_grid

    elif crop_type == "rotation":
        rows, cols = len(grid), len(grid[0])
        subgrids = [
            [row[c : c + 2] for row in grid[r : r + 2]]
            for r, c in [(0, 0), (0, cols - 2), (rows - 2, 0)]
        ]
        all_rotations = {
            angle: rotate_grid(subgrids[0], angle) for angle in [0, 90, 180, 270]
        }
        present_rotations = {
            angle
            for angle, pattern in all_rotations.items()
            for obj in subgrids
            if obj == pattern
        }
        missing_angle = (set([0, 90, 180, 270]) - present_rotations).pop()
        return all_rotations[missing_angle]

    elif crop_type == "whole_based":
        objects = find_connected_components(grid, background_color=0, connectivity=8)
        if not objects:
            raise ValueError(f"{Fore.RED}No objects found in the grid.{Style.RESET_ALL}")
        object_holes = []
        for obj in objects:
            positions = obj["pixels"]
            min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
            subgrid = [
                row[min_col : max_col + 1] for row in grid[min_row : max_row + 1]
            ]
            rows = len(subgrid)
            cols = len(subgrid[0])
            visited = [[False] * cols for _ in range(rows)]
            queue = deque()
            directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            for i in range(rows):
                for j in range(cols):
                    if (i == 0 or i == rows - 1 or j == 0 or j == cols - 1) and subgrid[
                        i
                    ][j] == 0:
                        queue.append((i, j))
                        visited[i][j] = True
            while queue:
                x, y = queue.popleft()
                for dx, dy in directions:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < rows and 0 <= ny < cols and not visited[nx][ny]:
                        if subgrid[nx][ny] == 0:
                            visited[nx][ny] = True
                            queue.append((nx, ny))
            holes = detect_holes(subgrid, directions)
            object_holes.append((obj["pixels"], holes))
        hole_count_freq = defaultdict(int)
        for _, holes in object_holes:
            hole_count_freq[holes] += 1
        unique_object = None
        for pixels, holes in object_holes:
            if hole_count_freq[holes] == 1:
                unique_object = pixels
                break
        if unique_object is None:
            raise ValueError(f"{Fore.RED}No unique object found with a distinct number of holes.{Style.RESET_ALL}")
        min_row, max_row, min_col, max_col = find_bounding_rectangle(unique_object)
        desired_rows = max_row - min_row + 1
        desired_cols = max_col - min_col + 1
        desired_grid = [[0 for _ in range(desired_cols)] for _ in range(desired_rows)]
        for r, c in unique_object:
            desired_grid[r - min_row][c - min_col] = grid[r][c]
        return desired_grid

    elif crop_type == "rectangle_count":
        rows = len(grid)
        cols = len(grid[0])

        color_counts = defaultdict(int)
        for row in grid:
            for color in row:
                color_counts[color] += 1
        background_color = max(color_counts.items(), key=lambda x: x[1])[0]
        rectangle_counts = defaultdict(int)
        for r in range(rows):
            c = 0
            while c < cols:
                current_color = grid[r][c]
                if current_color == background_color:
                    c += 1
                    continue
                start_c = c
                while c < cols and grid[r][c] == current_color:
                    c += 1
                end_c = c
                rectangle_counts[current_color] += 1

        sorted_colors = sorted(rectangle_counts.items(), key=lambda x: (-x[0], -x[1]))

        output_grid = [[0 for _ in range(fill_color)] for _ in range(border_color)]
        out_r = 0
        out_c = 0
        for color, count in sorted_colors:
            for _ in range(count):
                if out_r >= border_color:
                    break
                if out_c >= fill_color:
                    out_r += 1
                    out_c = 0
                    if out_r >= border_color:
                        break
                if out_r < border_color and out_c < fill_color:
                    output_grid[out_r][out_c] = color
                    out_c += 1
        return output_grid

    elif crop_type == "rectangle_contain":
        rectangles = find_all_rectangles(grid)
        selected_rect = (
            select_smallest_rectangle(grid, rectangles)
            if connect_all
            else select_biggest_rectangle(grid, rectangles)
        )
        extracted_grid = extract_rectangle(grid, selected_rect)
        return extracted_grid

    elif crop_type == "extract_objects":
        if not grid or not grid[0]:
            return [[0] * grid_size for _ in range(grid_size)]
        objects = find_connected_components(grid, background_color=0)
        if not objects:
            raise ValueError(f"{Fore.RED}No objects found in the grid.{Style.RESET_ALL}")
        largest_object = (
            max(objects, key=lambda obj: len(obj["pixels"]))
            if connect_all
            else min(objects, key=lambda obj: len(obj["pixels"]))
        )
        color_largest = largest_object["color"]
        return [[color_largest] * grid_size for _ in range(grid_size)]

    elif crop_type in ["most_frequent_object", "least_frequent_object"]:
        objects = find_connected_components(grid, background_color=0)
        color_counts = Counter(obj["color"] for obj in objects)
        if crop_type == "most_frequent_object":
            target_color = color_counts.most_common(1)[0][0]
        else:
            target_color = color_counts.most_common()[-1][0]
        target_objects = [obj for obj in objects if obj["color"] == target_color]
        if not target_objects:
            raise ValueError(f"{Fore.RED}No objects found with color {target_color}.{Style.RESET_ALL}")
        target_object = target_objects[0]
        positions = target_object["pixels"]
        min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
        desired_grid = [
            row[min_col : max_col + 1] for row in grid[min_row : max_row + 1]
        ]
        return desired_grid

    elif crop_type == "extract_colors_and_sort":
        height, width = len(grid), len(grid[0]) if grid else 0
        if height == 0 or any(len(row) != width for row in grid):
            raise ValueError(
                f"{Fore.RED}Invalid grid: All rows must have the same number of columns and grid must not be empty.{Style.RESET_ALL}"
            )
        visited = [[False] * width for _ in range(height)]
        objects = []
        if connect_all:
            for i in range(height):
                for j in range(width):
                    if grid[i][j] != 0 and not visited[i][j]:
                        obj = []
                        deep_first_search_object_based(
                            i, j, obj, height, width, visited, grid
                        )
                        if obj:
                            objects.append(obj)
        color_count = {}
        if connect_all:
            for obj in objects:
                color = obj[0]
                color_count[color] = color_count.get(color, 0) + 1
        else:
            for row in grid:
                for color in row:
                    if color != 0:
                        color_count[color] = color_count.get(color, 0) + 1
        sorted_colors = sorted(color_count.items(), key=lambda x: -x[1])
        max_count, num_colors = max(count for _, count in sorted_colors), len(
            color_count
        )
        row_dirs, col_dirs = {"left_to_right", "right_to_left"}, {
            "up_to_down",
            "down_to_up",
        }
        if fill_direction in row_dirs:
            rows, cols = num_colors, max_count
        elif fill_direction in col_dirs:
            rows, cols = max_count, num_colors
        else:
            raise ValueError(
                f"{Fore.RED}fill_direction must be 'left_to_right', 'right_to_left', 'up_to_down', or 'down_to_up'{Style.RESET_ALL}"
            )
        result = [[0] * cols for _ in range(rows)]
        for idx, (color, count) in enumerate(
            sorted_colors[: rows if fill_direction in row_dirs else cols]
        ):
            for n in range(min(count, cols if fill_direction in row_dirs else rows)):
                if fill_direction == "left_to_right":
                    result[idx][n] = color
                elif fill_direction == "right_to_left":
                    result[idx][-1 - n] = color
                elif fill_direction == "up_to_down":
                    result[n][idx] = color
                elif fill_direction == "down_to_up":
                    result[-1 - n][idx] = color
        return result

    elif crop_type == "from_rectangles":
        grid_np = np.array(grid)
        background_color = count_most_frequent_color_except_zero(grid)
        zero_rectangles = find_zero_rectangles(grid_np, background_color)
        first_rect = zero_rectangles[0]
        m = first_rect["max_row"] - first_rect["min_row"] + 1
        n = first_rect["max_col"] - first_rect["min_col"] + 1
        for rect in zero_rectangles[1:]:
            rect_m = rect["max_row"] - rect["min_row"] + 1
            rect_n = rect["max_col"] - rect["min_col"] + 1
            if rect_m != m or rect_n != n:
                raise ValueError(f"{Fore.RED}Zero rectangles have inconsistent sizes{Style.RESET_ALL}")
        output_grid = np.zeros((m, n), dtype=int)
        for rect in zero_rectangles:
            min_row, max_row = rect["min_row"], rect["max_row"]
            min_col, max_col = rect["min_col"], rect["max_col"]
            subgrid = grid_np[min_row : max_row + 1, min_col : max_col + 1]
            for i in range(subgrid.shape[0]):
                for j in range(subgrid.shape[1]):
                    val = subgrid[i][j]
                    if val != background_color and val != 0:
                        output_grid[i][j] = val
        return output_grid.tolist()

    elif crop_type == "corner_based":
        h, w = len(grid), len(grid[0])
        corners = {
            "left upper": (0, 0),
            "right upper": (0, w - grid_size),
            "left lower": (h - grid_size, 0),
            "right lower": (h - grid_size, w - grid_size),
        }
        start = corners.get(corner)
        if not start:
            raise ValueError(
                f"{Fore.RED}Invalid corner. Choose from 'left upper', 'right upper', 'left lower', 'right lower'.{Style.RESET_ALL}"
            )
        return [
            row[start[1] : start[1] + grid_size]
            for row in grid[start[0] : start[0] + grid_size]
        ]
    else:
        raise Exception(f"Wrong crop_type! You provided {crop_type}")

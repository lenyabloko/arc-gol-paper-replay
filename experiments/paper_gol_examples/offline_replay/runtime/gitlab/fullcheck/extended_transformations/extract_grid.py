try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *

from math import gcd


def extract_grid_based(
    grid,
    fill_color=0,
    extract_type="fill_color_bbox",
):
    if extract_type == "smallest_unique_color_component_prefer_tall":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("smallest_unique_color_component_prefer_tall requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("smallest_unique_color_component_prefer_tall requires a rectangular grid")

        color_counts = {}
        for values in grid:
            for value in values:
                color_counts[value] = color_counts.get(value, 0) + 1
        background_color = max(color_counts.items(), key=lambda item: (item[1], -item[0]))[0]

        visited = set()
        components = []
        for start_row in range(rows):
            for start_col in range(cols):
                color = grid[start_row][start_col]
                if color == background_color or (start_row, start_col) in visited:
                    continue
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                pixels = []
                while stack:
                    row, col = stack.pop()
                    pixels.append((row, col))
                    for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        next_row = row + delta_row
                        next_col = col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited:
                            continue
                        if grid[next_row][next_col] != color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                min_row = min(row for row, _ in pixels)
                max_row = max(row for row, _ in pixels)
                min_col = min(col for _, col in pixels)
                max_col = max(col for _, col in pixels)
                height = max_row - min_row + 1
                width = max_col - min_col + 1
                components.append({
                    "color": color,
                    "bbox": (min_row, max_row, min_col, max_col),
                    "area": height * width,
                    "height": height,
                    "width": width,
                    "min_row": min_row,
                    "min_col": min_col,
                })

        component_counts_by_color = {}
        for component in components:
            color = component["color"]
            component_counts_by_color[color] = component_counts_by_color.get(color, 0) + 1
        candidates = [
            component
            for component in components
            if component_counts_by_color[component["color"]] == 1
        ]
        if not candidates:
            raise ValueError("smallest_unique_color_component_prefer_tall found no unique-color component")

        selected = min(
            candidates,
            key=lambda component: (
                component["area"],
                -component["height"],
                component["width"],
                component["min_col"],
                component["min_row"],
            ),
        )
        min_row, max_row, min_col, max_col = selected["bbox"]
        return [
            row[min_col:max_col + 1]
            for row in grid[min_row:max_row + 1]
        ]

    if extract_type == "hidden_patch_180_from_solid_color":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("hidden_patch_180_from_solid_color requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("hidden_patch_180_from_solid_color requires a rectangular grid")
        occluder_color = fill_color
        positions = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == occluder_color
        ]
        if not positions:
            raise ValueError("hidden_patch_180_from_solid_color requires occluder pixels")

        position_set = set(positions)
        seen = set()
        components = []
        for start in sorted(position_set):
            if start in seen:
                continue
            stack = [start]
            seen.add(start)
            component = []
            while stack:
                row, col = stack.pop()
                component.append((row, col))
                for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    neighbor = (row + delta_row, col + delta_col)
                    if neighbor in position_set and neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
            components.append(component)

        rectangles = []
        for component in components:
            min_row = min(row for row, _ in component)
            max_row = max(row for row, _ in component)
            min_col = min(col for _, col in component)
            max_col = max(col for _, col in component)
            area = (max_row - min_row + 1) * (max_col - min_col + 1)
            if area != len(component):
                continue
            if all(
                grid[row][col] == occluder_color
                for row in range(min_row, max_row + 1)
                for col in range(min_col, max_col + 1)
            ):
                rectangles.append((area, min_row, max_row, min_col, max_col))
        if not rectangles:
            raise ValueError("hidden_patch_180_from_solid_color found no solid occluder rectangle")

        _, min_row, max_row, min_col, max_col = max(rectangles)
        source_min_row = rows - 1 - max_row
        source_max_row = rows - 1 - min_row
        source_min_col = cols - 1 - max_col
        source_max_col = cols - 1 - min_col
        if not (
            0 <= source_min_row <= source_max_row < rows
            and 0 <= source_min_col <= source_max_col < cols
        ):
            raise ValueError("hidden_patch_180_from_solid_color counterpart is out of bounds")

        return [
            [
                grid[source_max_row - row_offset][source_max_col - col_offset]
                for col_offset in range(source_max_col - source_min_col + 1)
            ]
            for row_offset in range(source_max_row - source_min_row + 1)
        ]

    if extract_type == "separator_box_crop_extend_side_colors":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_box_crop_extend_side_colors requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_box_crop_extend_side_colors requires a rectangular grid")

        full_rows = [
            row
            for row in range(rows)
            if all(grid[row][col] != fill_color for col in range(cols))
        ]
        full_cols = [
            col
            for col in range(cols)
            if all(grid[row][col] != fill_color for row in range(rows))
        ]
        if len(full_rows) != 2 or len(full_cols) != 2:
            raise ValueError("separator_box_crop_extend_side_colors requires exactly two full rows and columns")

        top, bottom = full_rows
        left, right = full_cols
        if bottom - top < 2 or right - left < 2:
            raise ValueError("separator_box_crop_extend_side_colors requires a non-empty separator box interior")

        output = [
            list(grid[row][left:right + 1])
            for row in range(top, bottom + 1)
        ]
        height = len(output)
        width = len(output[0])

        def mode(values):
            counts = {}
            for value in values:
                counts[value] = counts.get(value, 0) + 1
            if not counts:
                raise ValueError("separator_box_crop_extend_side_colors requires side colors")
            return max(counts.items(), key=lambda item: (item[1], -item[0]))[0]

        top_color = mode(output[0][1:-1])
        bottom_color = mode(output[-1][1:-1])
        left_color = mode(output[row][0] for row in range(1, height - 1))
        right_color = mode(output[row][-1] for row in range(1, height - 1))

        for row in range(1, height - 1):
            for col in range(1, width - 1):
                value = output[row][col]
                if value == fill_color:
                    continue
                if value == top_color:
                    for target_row in range(1, row + 1):
                        output[target_row][col] = value
                if value == bottom_color:
                    for target_row in range(row, height - 1):
                        output[target_row][col] = value
                if value == left_color:
                    for target_col in range(1, col + 1):
                        output[row][target_col] = value
                if value == right_color:
                    for target_col in range(col, width - 1):
                        output[row][target_col] = value
        return output

    if extract_type == "largest_frame_recolor_with_marker":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("largest_frame_recolor_with_marker requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("largest_frame_recolor_with_marker requires a rectangular grid")

        foreground_colors = sorted({
            value
            for row in grid
            for value in row
            if value != fill_color
        })
        if len(foreground_colors) < 2:
            raise ValueError("largest_frame_recolor_with_marker requires frame and marker colors")

        frame_candidates = []
        for frame_color in foreground_colors:
            visited = set()
            for start_row in range(rows):
                for start_col in range(cols):
                    if grid[start_row][start_col] != frame_color or (start_row, start_col) in visited:
                        continue
                    stack = [(start_row, start_col)]
                    visited.add((start_row, start_col))
                    component = []
                    while stack:
                        row, col = stack.pop()
                        component.append((row, col))
                        for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            next_row = row + delta_row
                            next_col = col + delta_col
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if (next_row, next_col) in visited or grid[next_row][next_col] != frame_color:
                                continue
                            visited.add((next_row, next_col))
                            stack.append((next_row, next_col))

                    min_row = min(row for row, _ in component)
                    max_row = max(row for row, _ in component)
                    min_col = min(col for _, col in component)
                    max_col = max(col for _, col in component)
                    height = max_row - min_row + 1
                    width = max_col - min_col + 1
                    if height < 3 or width < 3:
                        continue
                    border = {
                        (row, col)
                        for row in range(min_row, max_row + 1)
                        for col in range(min_col, max_col + 1)
                        if row in (min_row, max_row) or col in (min_col, max_col)
                    }
                    if set(component) != border:
                        continue
                    frame_candidates.append((height * width, frame_color, min_row, max_row, min_col, max_col))

        if not frame_candidates:
            raise ValueError("largest_frame_recolor_with_marker requires a rectangular frame component")
        _, frame_color, min_row, max_row, min_col, max_col = max(
            frame_candidates,
            key=lambda item: (item[0], -item[1]),
        )
        marker_colors = [value for value in foreground_colors if value != frame_color]
        if len(marker_colors) != 1:
            raise ValueError("largest_frame_recolor_with_marker requires one marker color")
        marker_color = marker_colors[0]

        return [
            [
                fill_color if grid[row][col] == fill_color else marker_color
                for col in range(min_col, max_col + 1)
            ]
            for row in range(min_row, max_row + 1)
        ]

    if extract_type == "largest_field_marker_rowcol_matrix":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("largest_field_marker_rowcol_matrix requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("largest_field_marker_rowcol_matrix requires a rectangular grid")

        visited = set()
        largest_component = None
        for start_row in range(rows):
            for start_col in range(cols):
                if (start_row, start_col) in visited:
                    continue
                component_color = grid[start_row][start_col]
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                component = []
                while stack:
                    row, col = stack.pop()
                    component.append((row, col))
                    for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        next_row = row + delta_row
                        next_col = col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited or grid[next_row][next_col] != component_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                if largest_component is None or len(component) > len(largest_component[1]):
                    largest_component = (component_color, component)

        if largest_component is None:
            raise ValueError("largest_field_marker_rowcol_matrix requires a component")
        field_color, component = largest_component
        min_row = min(row for row, _ in component)
        max_row = max(row for row, _ in component)
        min_col = min(col for _, col in component)
        max_col = max(col for _, col in component)

        candidate_marker_colors = sorted({
            grid[row][col]
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
            if grid[row][col] != field_color
        })

        candidates = []
        for marker_color in candidate_marker_colors:
            top = min_row
            bottom = max_row
            left = min_col
            right = max_col
            allowed = {field_color, marker_color}
            while top <= bottom and left <= right:
                side_bad_counts = [
                    (
                        sum(grid[top][col] not in allowed for col in range(left, right + 1)),
                        "top",
                    ),
                    (
                        sum(grid[bottom][col] not in allowed for col in range(left, right + 1)),
                        "bottom",
                    ),
                    (
                        sum(grid[row][left] not in allowed for row in range(top, bottom + 1)),
                        "left",
                    ),
                    (
                        sum(grid[row][right] not in allowed for row in range(top, bottom + 1)),
                        "right",
                    ),
                ]
                bad_count, side = max(side_bad_counts, key=lambda item: item[0])
                if bad_count == 0:
                    break
                if side == "top":
                    top += 1
                elif side == "bottom":
                    bottom -= 1
                elif side == "left":
                    left += 1
                else:
                    right -= 1
            if top > bottom or left > right:
                continue
            marker_positions = [
                (row, col)
                for row in range(top, bottom + 1)
                for col in range(left, right + 1)
                if grid[row][col] == marker_color
            ]
            if not marker_positions:
                continue
            area = (bottom - top + 1) * (right - left + 1)
            candidates.append((area, len(marker_positions), marker_color, top, bottom, left, right, marker_positions))

        if not candidates:
            raise ValueError("largest_field_marker_rowcol_matrix requires marker pixels in the field")
        _, _, marker_color, top, bottom, left, right, marker_positions = max(
            candidates,
            key=lambda item: (item[0], item[1], -item[2]),
        )
        marker_rows = {row - top for row, _ in marker_positions}
        marker_cols = {col - left for _, col in marker_positions}
        return [
            [
                marker_color if row in marker_rows or col in marker_cols else field_color
                for col in range(right - left + 1)
            ]
            for row in range(bottom - top + 1)
        ]

    if extract_type == "marker_box_inner_shape_recolor":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("marker_box_inner_shape_recolor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("marker_box_inner_shape_recolor requires a rectangular grid")

        background_color = fill_color
        candidates = []
        colors = sorted({
            value
            for row in grid
            for value in row
            if value != background_color
        })
        for marker_color in colors:
            marker_pixels = [
                (row_index, col_index)
                for row_index in range(rows)
                for col_index in range(cols)
                if grid[row_index][col_index] == marker_color
            ]
            if len(marker_pixels) != 4:
                continue
            marker_rows = sorted({row_index for row_index, _ in marker_pixels})
            marker_cols = sorted({col_index for _, col_index in marker_pixels})
            if len(marker_rows) != 2 or len(marker_cols) != 2:
                continue
            if set(marker_pixels) != {
                (marker_rows[0], marker_cols[0]),
                (marker_rows[0], marker_cols[1]),
                (marker_rows[1], marker_cols[0]),
                (marker_rows[1], marker_cols[1]),
            }:
                continue

            shape_pixels = [
                (row_index, col_index)
                for row_index in range(marker_rows[0] + 1, marker_rows[1])
                for col_index in range(marker_cols[0] + 1, marker_cols[1])
                if grid[row_index][col_index] not in (background_color, marker_color)
            ]
            if not shape_pixels:
                continue
            output = []
            for row_index in range(marker_rows[0] + 1, marker_rows[1]):
                output_row = []
                for col_index in range(marker_cols[0] + 1, marker_cols[1]):
                    value = grid[row_index][col_index]
                    output_row.append(
                        marker_color
                        if value not in (background_color, marker_color)
                        else background_color
                    )
                output.append(output_row)
            candidates.append(output)

        unique = []
        seen = set()
        for candidate in candidates:
            key = tuple(tuple(row) for row in candidate)
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        if len(unique) != 1:
            raise ValueError("marker_box_inner_shape_recolor requires a unique marker rectangle")
        return unique[0]

    if extract_type == "foreground_bbox_mirror_h":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("foreground_bbox_mirror_h requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("foreground_bbox_mirror_h requires a rectangular grid")
        points = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != fill_color
        ]
        if not points:
            raise ValueError("foreground_bbox_mirror_h requires foreground")
        min_row = min(row for row, _ in points)
        max_row = max(row for row, _ in points)
        min_col = min(col for _, col in points)
        max_col = max(col for _, col in points)
        return [
            list(reversed(grid[row][min_col:max_col + 1]))
            for row in range(min_row, max_row + 1)
        ]

    if extract_type == "frame_inner_pattern_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("frame_inner_pattern_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("frame_inner_pattern_fill requires a rectangular grid")

        frame_candidates = []
        colors = sorted({
            value
            for row in grid
            for value in row
            if value != fill_color
        })
        for candidate_color in colors:
            pixels = [
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] == candidate_color
            ]
            if not pixels:
                continue
            min_row = min(row for row, _ in pixels)
            max_row = max(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            max_col = max(col for _, col in pixels)
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            if height < 3 or width < 3:
                continue
            border = {
                (row, col)
                for row in range(min_row, max_row + 1)
                for col in range(min_col, max_col + 1)
                if row in (min_row, max_row) or col in (min_col, max_col)
            }
            if not all(grid[row][col] == candidate_color for row, col in border):
                continue
            if any(
                grid[row][col] == candidate_color
                for row in range(min_row + 1, max_row)
                for col in range(min_col + 1, max_col)
            ):
                continue
            frame_candidates.append((height * width, candidate_color, min_row, max_row, min_col, max_col))
        if len(frame_candidates) != 1:
            raise ValueError("frame_inner_pattern_fill requires one hollow frame")

        _, frame_color, frame_min_row, frame_max_row, frame_min_col, frame_max_col = frame_candidates[0]
        pattern_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] not in (fill_color, frame_color)
        ]
        if not pattern_pixels:
            raise ValueError("frame_inner_pattern_fill requires an outside pattern")
        if any(
            frame_min_row <= row <= frame_max_row and frame_min_col <= col <= frame_max_col
            for row, col in pattern_pixels
        ):
            raise ValueError("frame_inner_pattern_fill expects pattern outside frame")

        pat_min_row = min(row for row, _ in pattern_pixels)
        pat_max_row = max(row for row, _ in pattern_pixels)
        pat_min_col = min(col for _, col in pattern_pixels)
        pat_max_col = max(col for _, col in pattern_pixels)
        pattern = [
            [grid[row][col] for col in range(pat_min_col, pat_max_col + 1)]
            for row in range(pat_min_row, pat_max_row + 1)
        ]
        pattern_height = len(pattern)
        pattern_width = len(pattern[0]) if pattern else 0
        inner_height = frame_max_row - frame_min_row - 1
        inner_width = frame_max_col - frame_min_col - 1
        if (
            pattern_height == 0
            or pattern_width == 0
            or inner_height % pattern_height != 0
            or inner_width % pattern_width != 0
        ):
            raise ValueError("frame_inner_pattern_fill requires integer pattern scaling")
        row_scale = inner_height // pattern_height
        col_scale = inner_width // pattern_width
        if row_scale != col_scale or row_scale < 1:
            raise ValueError("frame_inner_pattern_fill requires uniform positive scale")

        output = [
            [grid[row][col] for col in range(frame_min_col, frame_max_col + 1)]
            for row in range(frame_min_row, frame_max_row + 1)
        ]
        for pattern_row in range(pattern_height):
            for pattern_col in range(pattern_width):
                value = pattern[pattern_row][pattern_col]
                for delta_row in range(row_scale):
                    for delta_col in range(col_scale):
                        output[1 + pattern_row * row_scale + delta_row][1 + pattern_col * col_scale + delta_col] = value
        return output

    if extract_type == "colored_frame_template_nearest_side_overlay":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("colored_frame_template_nearest_side_overlay requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("colored_frame_template_nearest_side_overlay requires a rectangular grid")

        frame_candidates = []
        for top in range(rows):
            for bottom in range(top + 2, rows):
                for left in range(cols):
                    for right in range(left + 2, cols):
                        if (
                            grid[top][left] != fill_color
                            or grid[top][right] != fill_color
                            or grid[bottom][left] != fill_color
                            or grid[bottom][right] != fill_color
                        ):
                            continue

                        top_side = grid[top][left + 1:right]
                        bottom_side = grid[bottom][left + 1:right]
                        left_side = [grid[row][left] for row in range(top + 1, bottom)]
                        right_side = [grid[row][right] for row in range(top + 1, bottom)]
                        if not top_side or not bottom_side or not left_side or not right_side:
                            continue
                        if not (
                            len(set(top_side)) == 1
                            and len(set(bottom_side)) == 1
                            and len(set(left_side)) == 1
                            and len(set(right_side)) == 1
                        ):
                            continue

                        side_colors = (top_side[0], bottom_side[0], left_side[0], right_side[0])
                        if any(color == fill_color for color in side_colors):
                            continue
                        if not all(
                            grid[row][col] == fill_color
                            for row in range(top + 1, bottom)
                            for col in range(left + 1, right)
                        ):
                            continue

                        height = bottom - top + 1
                        width = right - left + 1
                        frame_candidates.append((height * width, height, width, top, bottom, left, right, side_colors))

        if len(frame_candidates) != 1:
            raise ValueError("colored_frame_template_nearest_side_overlay requires one colored rectangular frame")

        _, _, _, frame_top, frame_bottom, frame_left, frame_right, side_colors = frame_candidates[0]
        top_color, bottom_color, left_color, right_color = side_colors
        ignored_colors = {fill_color, top_color, bottom_color, left_color, right_color}
        template_pixels = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if not (frame_top <= row <= frame_bottom and frame_left <= col <= frame_right)
            and grid[row][col] not in ignored_colors
        ]
        if not template_pixels:
            raise ValueError("colored_frame_template_nearest_side_overlay requires an outside template")
        template_colors = {value for _, _, value in template_pixels}
        if len(template_colors) != 1:
            raise ValueError("colored_frame_template_nearest_side_overlay requires one template color")
        template_color = next(iter(template_colors))

        template_top = min(row for row, _, _ in template_pixels)
        template_bottom = max(row for row, _, _ in template_pixels)
        template_left = min(col for _, col, _ in template_pixels)
        template_right = max(col for _, col, _ in template_pixels)
        template_height = template_bottom - template_top + 1
        template_width = template_right - template_left + 1
        inner_height = frame_bottom - frame_top - 1
        inner_width = frame_right - frame_left - 1
        if template_height != inner_height or template_width != inner_width:
            raise ValueError("colored_frame_template_nearest_side_overlay requires template size to match frame interior")

        output = [
            [grid[row][col] for col in range(frame_left, frame_right + 1)]
            for row in range(frame_top, frame_bottom + 1)
        ]
        for row, col, _ in template_pixels:
            rel_row = row - template_top
            rel_col = col - template_left
            side_distances = [
                (rel_row, top_color),
                (template_height - 1 - rel_row, bottom_color),
                (rel_col, left_color),
                (template_width - 1 - rel_col, right_color),
            ]
            min_distance = min(distance for distance, _ in side_distances)
            nearest = [color for distance, color in side_distances if distance == min_distance]
            output_value = nearest[0] if len(nearest) == 1 else template_color
            output[1 + rel_row][1 + rel_col] = output_value
        return output

    if extract_type == "assemble_accent_tiles_by_accent_position":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("assemble_accent_tiles_by_accent_position requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("assemble_accent_tiles_by_accent_position requires a rectangular grid")

        counts = {}
        for row in grid:
            for value in row:
                if value != 0:
                    counts[value] = counts.get(value, 0) + 1
        if not counts:
            raise ValueError("assemble_accent_tiles_by_accent_position requires foreground tiles")
        base_color = max(counts, key=lambda value: (counts[value], -value))

        slots = {}
        for top in range(rows - 2):
            for left in range(cols - 2):
                tile = [
                    [grid[row][col] for col in range(left, left + 3)]
                    for row in range(top, top + 3)
                ]
                values = {value for tile_row in tile for value in tile_row}
                if 0 in values or base_color not in values or len(values) > 2:
                    continue
                accent_values = values - {base_color}
                if not accent_values:
                    slot = (1, 1)
                elif len(accent_values) == 1:
                    accent = next(iter(accent_values))
                    accent_cells = [
                        (row, col)
                        for row in range(3)
                        for col in range(3)
                        if tile[row][col] == accent
                    ]
                    mean_row = sum(row for row, _ in accent_cells) / len(accent_cells)
                    mean_col = sum(col for _, col in accent_cells) / len(accent_cells)
                    slot = (round(mean_row), round(mean_col))
                else:
                    continue
                if slot in slots:
                    raise ValueError("assemble_accent_tiles_by_accent_position found duplicate slot candidates")
                slots[slot] = tile

        expected_slots = {(row, col) for row in range(3) for col in range(3)}
        if set(slots) != expected_slots:
            raise ValueError("assemble_accent_tiles_by_accent_position requires one tile for each output slot")

        output = []
        for slot_row in range(3):
            for tile_row in range(3):
                output.append(
                    slots[(slot_row, 0)][tile_row]
                    + slots[(slot_row, 1)][tile_row]
                    + slots[(slot_row, 2)][tile_row]
                )
        return output

    if extract_type == "corner_marker_scaled_pattern_overlay":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("corner_marker_scaled_pattern_overlay requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("corner_marker_scaled_pattern_overlay requires a rectangular grid")

        marker_color = None
        marker_bbox = None
        for candidate_color in sorted({value for row in grid for value in row if value != fill_color}):
            positions = [
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] == candidate_color
            ]
            if len(positions) != 4:
                continue
            min_row = min(row for row, _ in positions)
            max_row = max(row for row, _ in positions)
            min_col = min(col for _, col in positions)
            max_col = max(col for _, col in positions)
            if set(positions) == {
                (min_row, min_col),
                (min_row, max_col),
                (max_row, min_col),
                (max_row, max_col),
            }:
                marker_color = candidate_color
                marker_bbox = (min_row, max_row, min_col, max_col)
                break
        if marker_color is None:
            raise ValueError("corner_marker_scaled_pattern_overlay requires four corner markers")

        crop_min_row, crop_max_row, crop_min_col, crop_max_col = marker_bbox
        output = [
            [grid[row][col] for col in range(crop_min_col, crop_max_col + 1)]
            for row in range(crop_min_row, crop_max_row + 1)
        ]
        output_rows = len(output)
        output_cols = len(output[0])

        pattern_points = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] not in (fill_color, marker_color)
            and not (crop_min_row <= row <= crop_max_row and crop_min_col <= col <= crop_max_col)
        ]
        if not pattern_points:
            raise ValueError("corner_marker_scaled_pattern_overlay requires an outside pattern")
        pattern_min_row = min(row for row, _ in pattern_points)
        pattern_max_row = max(row for row, _ in pattern_points)
        pattern_min_col = min(col for _, col in pattern_points)
        pattern_max_col = max(col for _, col in pattern_points)
        pattern = [
            [grid[row][col] for col in range(pattern_min_col, pattern_max_col + 1)]
            for row in range(pattern_min_row, pattern_max_row + 1)
        ]

        best = None
        for scale in range(1, 6):
            scaled = []
            for pattern_row in pattern:
                expanded_row = []
                for value in pattern_row:
                    expanded_row.extend([value] * scale)
                for _ in range(scale):
                    scaled.append(expanded_row[:])
            scaled_rows = len(scaled)
            scaled_cols = len(scaled[0]) if scaled else 0
            if scaled_rows == 0 or scaled_cols == 0:
                continue
            if scaled_rows > output_rows or scaled_cols > output_cols:
                continue
            nonzero_scaled = [
                (row, col, scaled[row][col])
                for row in range(scaled_rows)
                for col in range(scaled_cols)
                if scaled[row][col] != fill_color
            ]
            for top in range(output_rows - scaled_rows + 1):
                for left in range(output_cols - scaled_cols + 1):
                    conflict = False
                    overlap = 0
                    new_cells = 0
                    for delta_row, delta_col, value in nonzero_scaled:
                        current = output[top + delta_row][left + delta_col]
                        if current != fill_color and current != value:
                            conflict = True
                            break
                        if current == value:
                            overlap += 1
                        else:
                            new_cells += 1
                    if conflict:
                        continue
                    for row in range(output_rows):
                        for col in range(output_cols):
                            current = output[row][col]
                            if current in (fill_color, marker_color):
                                continue
                            pattern_row = row - top
                            pattern_col = col - left
                            if not (
                                0 <= pattern_row < scaled_rows
                                and 0 <= pattern_col < scaled_cols
                                and scaled[pattern_row][pattern_col] == current
                            ):
                                conflict = True
                                break
                        if conflict:
                            break
                    if conflict:
                        continue
                    candidate = (overlap, new_cells, -scale, top, left, scaled)
                    if best is None or candidate > best:
                        best = candidate

        if best is None:
            raise ValueError("corner_marker_scaled_pattern_overlay found no scaled placement")
        _, _, _, top, left, scaled = best
        result = [row[:] for row in output]
        for row in range(len(scaled)):
            for col in range(len(scaled[0])):
                value = scaled[row][col]
                if value != fill_color and result[top + row][left + col] == fill_color:
                    result[top + row][left + col] = value
        return result

    if extract_type == "base_rectangle_external_tile_overlay":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("base_rectangle_external_tile_overlay requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("base_rectangle_external_tile_overlay requires a rectangular grid")

        color_counts = {}
        for row in grid:
            for value in row:
                if value != fill_color:
                    color_counts[value] = color_counts.get(value, 0) + 1
        if not color_counts:
            raise ValueError("base_rectangle_external_tile_overlay requires foreground")
        base_color = max(color_counts, key=lambda value: (color_counts[value], -value))

        visited = set()
        components = []
        for start_row in range(rows):
            for start_col in range(cols):
                if grid[start_row][start_col] == fill_color or (start_row, start_col) in visited:
                    continue
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                cells = []
                counts = {}
                while stack:
                    row, col = stack.pop()
                    cells.append((row, col))
                    value = grid[row][col]
                    counts[value] = counts.get(value, 0) + 1
                    for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        next_row = row + delta_row
                        next_col = col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (
                            (next_row, next_col) in visited
                            or grid[next_row][next_col] == fill_color
                        ):
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                min_row = min(row for row, _ in cells)
                max_row = max(row for row, _ in cells)
                min_col = min(col for _, col in cells)
                max_col = max(col for _, col in cells)
                components.append({
                    "cells": set(cells),
                    "counts": counts,
                    "bbox": (min_row, max_row, min_col, max_col),
                    "area": (max_row - min_row + 1) * (max_col - min_col + 1),
                })

        main_candidates = [
            component
            for component in components
            if component["counts"].get(base_color, 0) > 0
        ]
        if not main_candidates:
            raise ValueError("base_rectangle_external_tile_overlay found no base component")
        main = max(
            main_candidates,
            key=lambda component: (component["area"], len(component["cells"])),
        )
        crop_min_row, crop_max_row, crop_min_col, crop_max_col = main["bbox"]
        original = [
            [grid[row][col] for col in range(crop_min_col, crop_max_col + 1)]
            for row in range(crop_min_row, crop_max_row + 1)
        ]
        output = [
            [value if value != fill_color else base_color for value in row]
            for row in original
        ]
        output_rows = len(output)
        output_cols = len(output[0])

        def rotate_90(tile):
            return [list(row) for row in zip(*tile[::-1])]

        def flip_horizontal(tile):
            return [list(reversed(row)) for row in tile]

        def tile_variants(tile):
            variants = []
            seen = set()
            current = tile
            for _ in range(4):
                for candidate in (current, flip_horizontal(current)):
                    key = tuple(tuple(row) for row in candidate)
                    if key not in seen:
                        seen.add(key)
                        variants.append([list(row) for row in candidate])
                current = rotate_90(current)
            return variants

        external_tiles = []
        for component in components:
            if component is main:
                continue
            counts = component["counts"]
            if counts.get(base_color, 0) == 0 or len(counts) < 2:
                continue
            tile_min_row, tile_max_row, tile_min_col, tile_max_col = component["bbox"]
            if not (
                tile_max_row < crop_min_row
                or tile_min_row > crop_max_row
                or tile_max_col < crop_min_col
                or tile_min_col > crop_max_col
            ):
                continue
            tile = [
                [grid[row][col] for col in range(tile_min_col, tile_max_col + 1)]
                for row in range(tile_min_row, tile_max_row + 1)
            ]
            if any(
                value not in (fill_color, base_color)
                for tile_row in tile
                for value in tile_row
            ):
                external_tiles.append((len(component["cells"]), tile))

        if not external_tiles:
            raise ValueError("base_rectangle_external_tile_overlay requires external tiles")

        for _, tile in sorted(external_tiles, key=lambda item: -item[0]):
            best = None
            for variant in tile_variants(tile):
                tile_rows = len(variant)
                tile_cols = len(variant[0])
                base_cells = [
                    (row, col)
                    for row in range(tile_rows)
                    for col in range(tile_cols)
                    if variant[row][col] == base_color
                ]
                accent_cells = [
                    (row, col, variant[row][col])
                    for row in range(tile_rows)
                    for col in range(tile_cols)
                    if variant[row][col] not in (fill_color, base_color)
                ]
                if not base_cells or not accent_cells:
                    continue
                for top in range(output_rows - tile_rows + 1):
                    for left in range(output_cols - tile_cols + 1):
                        base_hole_matches = sum(
                            1
                            for row, col in base_cells
                            if original[top + row][left + col] == fill_color
                        )
                        if base_hole_matches == 0:
                            continue
                        conflict = False
                        accent_on_base = 0
                        for row, col, _ in accent_cells:
                            current = original[top + row][left + col]
                            if current not in (fill_color, base_color):
                                conflict = True
                                break
                            if current == base_color:
                                accent_on_base += 1
                        if conflict:
                            continue
                        margin = (
                            int(top > 0)
                            + int(left > 0)
                            + int(top + tile_rows < output_rows)
                            + int(left + tile_cols < output_cols)
                        )
                        candidate = (
                            base_hole_matches,
                            accent_on_base,
                            len(accent_cells),
                            margin,
                            -top,
                            -left,
                            variant,
                            top,
                            left,
                        )
                        if best is None or candidate > best:
                            best = candidate

            if best is None:
                continue
            variant = best[6]
            top = best[7]
            left = best[8]
            for row in range(len(variant)):
                for col in range(len(variant[0])):
                    value = variant[row][col]
                    if value in (fill_color, base_color):
                        continue
                    current = output[top + row][left + col]
                    if current not in (base_color, value):
                        raise ValueError("base_rectangle_external_tile_overlay found overlapping accents")
                    output[top + row][left + col] = value

        return output

    if extract_type == "corner_label_inner_mask_quadrants":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("corner_label_inner_mask_quadrants requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("corner_label_inner_mask_quadrants requires a rectangular grid")

        candidates = []
        for color in sorted({value for row in grid for value in row if value != fill_color}):
            full_rows = [
                row
                for row in range(rows)
                if all(grid[row][col] == color for col in range(cols))
            ]
            full_cols = [
                col
                for col in range(cols)
                if all(grid[row][col] == color for row in range(rows))
            ]
            if len(full_rows) >= 2 and len(full_cols) >= 2:
                candidates.append((color, full_rows[0], full_rows[-1], full_cols[0], full_cols[-1]))
        if not candidates:
            raise ValueError("corner_label_inner_mask_quadrants requires a rectangular frame")

        for frame_color, top, bottom, left, right in candidates:
            if bottom - top <= 1 or right - left <= 1:
                continue
            labels = {
                "tl": grid[0][0],
                "tr": grid[0][cols - 1],
                "bl": grid[rows - 1][0],
                "br": grid[rows - 1][cols - 1],
            }
            if any(value in (fill_color, frame_color) for value in labels.values()):
                continue
            inner = [
                grid[row][left + 1:right]
                for row in range(top + 1, bottom)
            ]
            inner_h = len(inner)
            inner_w = len(inner[0]) if inner else 0
            if inner_h == 0 or inner_w == 0 or inner_h % 2 or inner_w % 2:
                continue
            mask_colors = {
                value
                for row in inner
                for value in row
                if value not in (fill_color, frame_color)
            }
            if len(mask_colors) != 1:
                continue
            mask_color = next(iter(mask_colors))
            output = []
            for row in range(inner_h):
                output_row = []
                for col in range(inner_w):
                    if inner[row][col] != mask_color:
                        output_row.append(fill_color)
                    elif row < inner_h // 2 and col < inner_w // 2:
                        output_row.append(labels["tl"])
                    elif row < inner_h // 2:
                        output_row.append(labels["tr"])
                    elif col < inner_w // 2:
                        output_row.append(labels["bl"])
                    else:
                        output_row.append(labels["br"])
                output.append(output_row)
            return output

        raise ValueError("corner_label_inner_mask_quadrants found no valid frame")

    if extract_type == "separator_metadata_tile_recolor":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_metadata_tile_recolor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_metadata_tile_recolor requires a rectangular grid")

        colors = sorted({value for row in grid for value in row})
        separator_candidates = []
        for candidate in colors:
            if candidate == fill_color:
                continue
            full_rows = [
                row
                for row in range(1, rows - 1)
                if all(grid[row][col] == candidate for col in range(cols))
            ]
            full_cols = [
                col
                for col in range(1, cols - 1)
                if all(grid[row][col] == candidate for row in range(rows))
            ]
            if len(full_rows) == 1 and len(full_cols) == 1:
                separator_candidates.append((candidate, full_rows[0], full_cols[0]))
        if not separator_candidates:
            raise ValueError("separator_metadata_tile_recolor requires one full row/column separator")

        def quadrant(row_start, row_end, col_start, col_end):
            return {
                "row_start": row_start,
                "row_end": row_end,
                "col_start": col_start,
                "col_end": col_end,
                "height": row_end - row_start,
                "width": col_end - col_start,
                "grid": [grid[row][col_start:col_end] for row in range(row_start, row_end)],
            }

        for separator_color, separator_row, separator_col in separator_candidates:
            quadrants = [
                quadrant(0, separator_row, 0, separator_col),
                quadrant(0, separator_row, separator_col + 1, cols),
                quadrant(separator_row + 1, rows, 0, separator_col),
                quadrant(separator_row + 1, rows, separator_col + 1, cols),
            ]
            for meta_index, metadata in enumerate(quadrants):
                if metadata["height"] <= 0 or metadata["width"] <= 0:
                    continue
                if any(
                    value in (fill_color, separator_color)
                    for row in metadata["grid"]
                    for value in row
                ):
                    continue
                body_index = 3 - meta_index
                body = quadrants[body_index]
                if body["height"] != metadata["height"] * 3 or body["width"] != metadata["width"] * 3:
                    continue
                body_values = [
                    value
                    for row in body["grid"]
                    for value in row
                    if value not in (fill_color, separator_color)
                ]
                body_colors = set(body_values)
                if len(body_colors) != 1:
                    continue
                marker_color = next(iter(body_colors))
                output = []
                for local_row, body_row in enumerate(body["grid"]):
                    tile_row = local_row // 3
                    output_row = []
                    for local_col, value in enumerate(body_row):
                        tile_col = local_col // 3
                        output_row.append(
                            metadata["grid"][tile_row][tile_col]
                            if value == marker_color
                            else fill_color
                        )
                    output.append(output_row)
                return output

        raise ValueError("separator_metadata_tile_recolor found no metadata/body pair")

    if extract_type == "macro_shape_masked_matrix":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("macro_shape_masked_matrix requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("macro_shape_masked_matrix requires a rectangular grid")

        all_counts = {}
        for row in grid:
            for value in row:
                all_counts[value] = all_counts.get(value, 0) + 1
        if fill_color != max(all_counts, key=lambda value: (all_counts[value], -value)):
            raise ValueError("macro_shape_masked_matrix fill_color must be image background")

        counts = {}
        for row in grid:
            for value in row:
                if value == fill_color:
                    continue
                counts[value] = counts.get(value, 0) + 1
        if not counts:
            raise ValueError("macro_shape_masked_matrix requires foreground")
        shape_color = max(counts, key=lambda value: (counts[value], -value))
        shape_components = [
            component["pixels"]
            for component in find_connected_components(
                grid,
                target_colors={shape_color},
                background_color=fill_color,
                connectivity=4,
            )
        ]
        if not shape_components:
            raise ValueError("macro_shape_masked_matrix requires shape components")
        shape_pixels_set = {
            pixel
            for component in shape_components
            if len(component) > 1
            for pixel in component
        }
        if not shape_pixels_set:
            shape_pixels_set = set(max(shape_components, key=len))
        shape_pixels = sorted(shape_pixels_set)
        matrix_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != fill_color and (row, col) not in shape_pixels_set
        ]
        if not shape_pixels or not matrix_pixels:
            raise ValueError("macro_shape_masked_matrix requires shape and matrix pixels")

        min_shape_row, max_shape_row, min_shape_col, max_shape_col = find_bounding_rectangle(shape_pixels)

        def run_lengths_by_row():
            lengths = []
            for row in range(min_shape_row, max_shape_row + 1):
                col = min_shape_col
                while col <= max_shape_col:
                    if grid[row][col] != shape_color:
                        col += 1
                        continue
                    start = col
                    while col <= max_shape_col and grid[row][col] == shape_color:
                        col += 1
                    lengths.append(col - start)
            return lengths

        def run_lengths_by_col():
            lengths = []
            for col in range(min_shape_col, max_shape_col + 1):
                row = min_shape_row
                while row <= max_shape_row:
                    if grid[row][col] != shape_color:
                        row += 1
                        continue
                    start = row
                    while row <= max_shape_row and grid[row][col] == shape_color:
                        row += 1
                    lengths.append(row - start)
            return lengths

        horizontal_runs = run_lengths_by_row()
        vertical_runs = run_lengths_by_col()
        if not horizontal_runs or not vertical_runs:
            raise ValueError("macro_shape_masked_matrix found no shape runs")
        cell_width = horizontal_runs[0]
        for length in horizontal_runs[1:]:
            cell_width = gcd(cell_width, length)
        cell_height = vertical_runs[0]
        for length in vertical_runs[1:]:
            cell_height = gcd(cell_height, length)
        if cell_height <= 0 or cell_width <= 0:
            raise ValueError("macro_shape_masked_matrix inferred empty cell size")

        shape_height = max_shape_row - min_shape_row + 1
        shape_width = max_shape_col - min_shape_col + 1
        if shape_height % cell_height != 0 or shape_width % cell_width != 0:
            raise ValueError("macro_shape_masked_matrix shape bbox not divisible by cell size")
        mask_height = shape_height // cell_height
        mask_width = shape_width // cell_width
        mask = []
        for mask_row in range(mask_height):
            output_row = []
            for mask_col in range(mask_width):
                occupied = any(
                    grid[row][col] == shape_color
                    for row in range(min_shape_row + mask_row * cell_height, min_shape_row + (mask_row + 1) * cell_height)
                    for col in range(min_shape_col + mask_col * cell_width, min_shape_col + (mask_col + 1) * cell_width)
                )
                output_row.append(occupied)
            mask.append(output_row)

        min_matrix_row, max_matrix_row, min_matrix_col, max_matrix_col = find_bounding_rectangle(matrix_pixels)
        matrix = [
            row[min_matrix_col : max_matrix_col + 1]
            for row in grid[min_matrix_row : max_matrix_row + 1]
        ]
        if len(matrix) != mask_height or len(matrix[0]) != mask_width:
            raise ValueError("macro_shape_masked_matrix matrix and mask dimensions differ")
        return [
            [
                matrix[row][col] if mask[row][col] else fill_color
                for col in range(mask_width)
            ]
            for row in range(mask_height)
        ]

    if extract_type == "periodic_hole_patch":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("periodic_hole_patch requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("periodic_hole_patch requires a rectangular grid")

        holes = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == fill_color
        ]
        if not holes:
            raise ValueError("periodic_hole_patch requires fill-color holes")

        known = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != fill_color
        ]
        if not known:
            raise ValueError("periodic_hole_patch requires known pattern cells")

        def infer_pattern(period_rows, period_cols):
            pattern = {}
            for row, col, value in known:
                key = (row % period_rows, col % period_cols)
                if key in pattern and pattern[key] != value:
                    return None
                pattern[key] = value
            if any((row % period_rows, col % period_cols) not in pattern for row, col in holes):
                return None
            return pattern

        candidates = []
        for period_rows in range(1, rows + 1):
            for period_cols in range(1, cols + 1):
                pattern = infer_pattern(period_rows, period_cols)
                if pattern is None:
                    continue
                candidates.append((period_rows * period_cols, period_rows + period_cols, period_rows, period_cols, pattern))
        if not candidates:
            raise ValueError("periodic_hole_patch found no consistent period")

        _, _, period_rows, period_cols, pattern = min(candidates, key=lambda item: item[:4])
        min_row, max_row, min_col, max_col = find_bounding_rectangle(holes)
        return [
            [
                pattern[(row % period_rows, col % period_cols)]
                for col in range(min_col, max_col + 1)
            ]
            for row in range(min_row, max_row + 1)
        ]

    if extract_type == "foreground_bbox_swap_two_colors":
        foreground = [
            (i, j)
            for i, row in enumerate(grid)
            for j, cell in enumerate(row)
            if cell != 0
        ]
        if not foreground:
            raise ValueError("foreground_bbox_swap_two_colors requires foreground")
        min_row, max_row, min_col, max_col = find_bounding_rectangle(foreground)
        rectangle = [
            row[min_col : max_col + 1]
            for row in grid[min_row : max_row + 1]
        ]
        colors = sorted({
            cell
            for row in rectangle
            for cell in row
            if cell != 0
        })
        if len(colors) != 2:
            raise ValueError("foreground_bbox_swap_two_colors requires exactly two colors")
        left, right = colors
        return [
            [
                right if cell == left else left if cell == right else cell
                for cell in row
            ]
            for row in rectangle
        ]

    if extract_type == "non_fill_color_bbox_zero_fill":
        foreground = [
            (i, j)
            for i, row in enumerate(grid)
            for j, cell in enumerate(row)
            if cell != fill_color
        ]
        if not foreground:
            raise ValueError("non_fill_color_bbox_zero_fill requires foreground")
        min_row, max_row, min_col, max_col = find_bounding_rectangle(foreground)
        rectangle = [
            row[min_col : max_col + 1]
            for row in grid[min_row : max_row + 1]
        ]
        return [
            [
                0 if cell == fill_color else cell
                for cell in row
            ]
            for row in rectangle
        ]

    if extract_type != "fill_color_bbox":
        raise ValueError(f"Unsupported extract type: {extract_type}")

    positions = [
            (i, j)
            for i, row in enumerate(grid)
            for j, cell in enumerate(row)
            if cell == fill_color
        ]
    if not positions:
        return [row[:] for row in grid]
    min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
    rectangle = [row[min_col : max_col + 1] for row in grid[min_row : max_row + 1]]
    other_colors = set()
    for row in rectangle:
        for cell in row:
            if cell != fill_color and cell != 0:
                other_colors.add(cell)
    n = 0            
    if len(other_colors) > 0:
        other_color = other_colors.pop()
        count_other_color = sum(
            cell == other_color for row in rectangle for cell in row
        )
        n = count_other_color
        grid_size = len(rectangle)
        output_grid = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
        for idx in range(min(n, grid_size**2)):
            row = idx // grid_size
            col = idx % grid_size
            output_grid[row][col] = other_color
        return output_grid
    else:
        return [[0 for _ in range(len(rectangle))] for _ in range(len(rectangle))]

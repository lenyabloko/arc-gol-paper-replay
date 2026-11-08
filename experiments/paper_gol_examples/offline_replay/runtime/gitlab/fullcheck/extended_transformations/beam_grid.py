import numpy as np
from collections import Counter, deque, defaultdict
import copy

try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def _non_background_points(grid, background_color=0):
    return [
        (row, col, value)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value != background_color
    ]


def _right_edge_waterfall(grid, background_color=0):
    rows, cols = len(grid), len(grid[0]) if grid else 0
    points = _non_background_points(grid, background_color=background_color)
    if not points:
        raise ValueError("right_edge_waterfall requires marker pixels")
    if len({(row, col) for row, col, _ in points}) != len(points):
        raise ValueError("right_edge_waterfall requires unique marker pixels")
    if len({row for row, _, _ in points}) != len(points):
        raise ValueError("right_edge_waterfall requires at most one marker per row")

    transformed = copy.deepcopy(grid)
    points = sorted(points)
    marker_rows = [row for row, _, _ in points]
    for index, (row, col, color) in enumerate(points):
        next_row = marker_rows[index + 1] if index + 1 < len(marker_rows) else rows
        for fill_col in range(col, cols):
            if transformed[row][fill_col] == background_color or fill_col == col:
                transformed[row][fill_col] = color
        for fill_row in range(row + 1, next_row):
            if transformed[fill_row][cols - 1] == background_color:
                transformed[fill_row][cols - 1] = color
    return transformed


def _repeat_pattern_line(grid, background_color=0):
    rows, cols = len(grid), len(grid[0]) if grid else 0
    points = _non_background_points(grid, background_color=background_color)
    if len(points) != 2:
        raise ValueError("repeat_pattern_line requires exactly two source pixels")

    (row_a, col_a, color_a), (row_b, col_b, color_b) = points
    output = [[background_color for _ in range(cols)] for _ in range(rows)]
    row_step = abs(row_b - row_a)
    col_step = abs(col_b - col_a)

    if col_step == 0 or (row_step and row_step <= col_step):
        step = row_step
        if step == 0:
            raise ValueError("repeat_pattern_line requires separated pixels")
        if row_b < row_a:
            row_a, row_b = row_b, row_a
            color_a, color_b = color_b, color_a
        period = step * 2
        for row in range(row_a, rows):
            offset = (row - row_a) % period
            if offset == 0:
                output[row] = [color_a for _ in range(cols)]
            elif offset == step:
                output[row] = [color_b for _ in range(cols)]
        return output

    step = col_step
    period = step * 2
    first_col, first_color = col_a, color_a
    second_col, second_color = col_b, color_b
    if second_col < first_col:
        first_col, second_col = second_col, first_col
        first_color, second_color = second_color, first_color
    for row in range(rows):
        for col in range(first_col, cols):
            offset = (col - first_col) % period
            if offset == 0:
                output[row][col] = first_color
            elif offset == step:
                output[row][col] = second_color
    return output


def _positions(grid, color):
    return [
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value == color
    ]


def _color_components(grid, color, connectivity=4):
    if not grid:
        return []
    rows, cols = len(grid), len(grid[0])
    if connectivity == 8:
        deltas = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ]
    else:
        deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    seen = set()
    components = []
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] != color or (row, col) in seen:
                continue
            stack = [(row, col)]
            seen.add((row, col))
            component = []
            while stack:
                r, c = stack.pop()
                component.append((r, c))
                for dr, dc in deltas:
                    nr, nc = r + dr, c + dc
                    if (
                        0 <= nr < rows
                        and 0 <= nc < cols
                        and (nr, nc) not in seen
                        and grid[nr][nc] == color
                    ):
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            components.append(component)
    return components


def _fill_component_bbox_holes(grid, source_color, fill_color, background_color=0):
    transformed = copy.deepcopy(grid)
    for component in _color_components(grid, source_color, connectivity=8):
        rows = [row for row, _ in component]
        cols = [col for _, col in component]
        for row in range(min(rows), max(rows) + 1):
            for col in range(min(cols), max(cols) + 1):
                if transformed[row][col] == background_color:
                    transformed[row][col] = fill_color
    return transformed


def _fill_open_frame_from_marker(grid, frame_color, background_color=0):
    transformed = copy.deepcopy(grid)
    rows, cols = len(grid), len(grid[0]) if grid else 0

    # Markers can sit inside the cup without being 4-connected to the frame, so
    # frame components must be analyzed independently from the marker component.
    for frame_component in _color_components(grid, frame_color, connectivity=4):
        if not frame_component:
            continue
        min_row, max_row, min_col, max_col = _component_bbox(frame_component)
        if max_col - min_col < 2 or max_row - min_row < 2:
            continue

        marker_colors = {
            grid[row][col]
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
            if grid[row][col] not in {background_color, frame_color}
        }
        if len(marker_colors) != 1:
            continue
        marker_color = next(iter(marker_colors))

        for fill_row in range(max(0, min_row - 1), max_row):
            for fill_col in range(min_col, max_col + 1):
                if transformed[fill_row][fill_col] == background_color:
                    transformed[fill_row][fill_col] = marker_color
    return transformed


def _l_path_between_markers(grid, source_color, fill_color, background_color=0):
    transformed = copy.deepcopy(grid)
    source_positions = _positions(grid, source_color)
    marker_positions = [
        (row, col, value)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value != background_color
    ]
    if len(source_positions) != 1 or len(marker_positions) != 2:
        raise ValueError("l_path_between_markers requires exactly two marker pixels")
    source = source_positions[0]
    target = next((row, col) for row, col, value in marker_positions if value != source_color)
    source_row, source_col = source
    target_row, target_col = target
    step_col = 1 if target_col >= source_col else -1
    for col in range(source_col + step_col, target_col + step_col, step_col):
        if transformed[source_row][col] == background_color:
            transformed[source_row][col] = fill_color
    step_row = 1 if target_row >= source_row else -1
    for row in range(source_row + step_row, target_row, step_row):
        if transformed[row][target_col] == background_color:
            transformed[row][target_col] = fill_color
    return transformed


def _corner_anchor_rectangle_fill(grid, anchor_color, fill_color, background_color=0):
    transformed = copy.deepcopy(grid)
    positions = set(_positions(grid, anchor_color))
    rows = sorted({row for row, _ in positions})
    cols = sorted({col for _, col in positions})
    for top_i, top in enumerate(rows):
        for bottom in rows[top_i + 1:]:
            for left_i, left in enumerate(cols):
                for right in cols[left_i + 1:]:
                    if {
                        (top, left),
                        (top, right),
                        (bottom, left),
                        (bottom, right),
                    } <= positions:
                        for row in range(top + 1, bottom):
                            for col in range(left + 1, right):
                                if transformed[row][col] == background_color:
                                    transformed[row][col] = fill_color
    return transformed


def _component_bbox(component):
    rows = [row for row, _ in component]
    cols = [col for _, col in component]
    return min(rows), max(rows), min(cols), max(cols)


def _rectangle_gap_fill(grid, fill_color, background_color=0):
    transformed = copy.deepcopy(grid)
    components = []
    colors = sorted({
        value
        for row in grid
        for value in row
        if value not in (background_color, fill_color)
    })
    for color in colors:
        for component in _color_components(grid, color, connectivity=4):
            if not component:
                continue
            min_row, max_row, min_col, max_col = _component_bbox(component)
            area = (max_row - min_row + 1) * (max_col - min_col + 1)
            if area == len(component):
                components.append((min_row, max_row, min_col, max_col))
    if len(components) < 2:
        raise ValueError("rectangle_gap_fill requires at least two solid rectangles")

    for index, first in enumerate(components):
        for second in components[index + 1:]:
            a_min_r, a_max_r, a_min_c, a_max_c = first
            b_min_r, b_max_r, b_min_c, b_max_c = second
            # Horizontal gap.
            if a_max_c < b_min_c or b_max_c < a_min_c:
                left, right = (first, second) if a_max_c < b_min_c else (second, first)
                l_min_r, l_max_r, _, l_max_c = left
                r_min_r, r_max_r, r_min_c, _ = right
                overlap_min = max(l_min_r, r_min_r)
                overlap_max = min(l_max_r, r_max_r)
                for row in range(overlap_min + 1, overlap_max):
                    for col in range(l_max_c + 1, r_min_c):
                        if transformed[row][col] == background_color:
                            transformed[row][col] = fill_color
            # Vertical gap.
            if a_max_r < b_min_r or b_max_r < a_min_r:
                top, bottom = (first, second) if a_max_r < b_min_r else (second, first)
                _, t_max_r, t_min_c, t_max_c = top
                b_min_r, _, b_min_c, b_max_c = bottom
                overlap_min = max(t_min_c, b_min_c)
                overlap_max = min(t_max_c, b_max_c)
                for row in range(t_max_r + 1, b_min_r):
                    for col in range(overlap_min + 1, overlap_max):
                        if transformed[row][col] == background_color:
                            transformed[row][col] = fill_color
    return transformed


def _midpoint_cross_between_markers(grid, marker_color, fill_color, background_color=0):
    positions = _positions(grid, marker_color)
    if len(positions) != 2:
        raise ValueError("midpoint_cross_between_markers requires exactly two markers")
    (r1, c1), (r2, c2) = positions
    center_row = (r1 + r2) // 2
    center_col = (c1 + c2) // 2
    transformed = copy.deepcopy(grid)
    for row, col in (
        (center_row, center_col),
        (center_row - 1, center_col),
        (center_row + 1, center_col),
        (center_row, center_col - 1),
        (center_row, center_col + 1),
    ):
        if 0 <= row < len(grid) and 0 <= col < len(grid[0]) and transformed[row][col] == background_color:
            transformed[row][col] = fill_color
    return transformed


def _infer_bracketed_base_run_color(grid, background_color=0):
    if not grid:
        return None
    rows, cols = len(grid), len(grid[0])
    for row in range(rows - 1, -1, -1):
        runs = []
        col = 0
        while col < cols:
            value = grid[row][col]
            if value == background_color:
                col += 1
                continue
            start = col
            while col + 1 < cols and grid[row][col + 1] == value:
                col += 1
            end = col
            runs.append((value, start, end))
            col += 1
        if not runs:
            continue

        bracketed = [
            (value, start, end)
            for value, start, end in runs
            if (
                start - 1 >= 0
                and end + 1 < cols
                and grid[row][start - 1] == grid[row][end + 1]
                and grid[row][start - 1] not in {background_color, value}
            )
        ]
        if bracketed:
            return max(bracketed, key=lambda item: item[2] - item[1])[0]

        counts = {}
        for value, start, end in runs:
            counts[value] = counts.get(value, 0) + (end - start + 1)
        return min(counts, key=lambda value: (counts[value], value))
    return None


def _diagonal_pyramid_from_base_run(grid, target_color, background_color=0):
    transformed = copy.deepcopy(grid)
    rows, cols = len(grid), len(grid[0]) if grid else 0
    if target_color in (None, background_color):
        target_color = _infer_bracketed_base_run_color(grid, background_color)
    if target_color in (None, background_color):
        raise ValueError("diagonal_pyramid_from_base_run requires target run")
    runs = []
    for row in range(rows):
        col = 0
        while col < cols:
            if grid[row][col] != target_color:
                col += 1
                continue
            start = col
            while col + 1 < cols and grid[row][col + 1] == target_color:
                col += 1
            end = col
            runs.append((row, start, end))
            col += 1
    if not runs:
        raise ValueError("diagonal_pyramid_from_base_run requires target run")
    base_row, start_col, end_col = max(runs, key=lambda item: (item[0], item[2] - item[1]))
    offset = 1
    while True:
        row = base_row - 1 - offset
        left = start_col - offset
        right = end_col + offset
        if row < 0 or (left < 0 and right >= cols):
            break
        for col in (left, right):
            if 0 <= col < cols and transformed[row][col] == background_color:
                transformed[row][col] = target_color
        offset += 1
    return transformed


def _diagonal_endpoint_rays(grid, source_color, background_color=0):
    transformed = copy.deepcopy(grid)
    rows, cols = len(grid), len(grid[0]) if grid else 0
    if source_color in (None, background_color):
        colors = {
            value
            for row in grid
            for value in row
            if value != background_color
        }
        if len(colors) == 1:
            source_color = next(iter(colors))
    points = set(_positions(grid, source_color))
    if len(points) < 2:
        raise ValueError("diagonal_endpoint_rays requires at least two source pixels")

    core = None
    for row in range(rows - 1):
        for col in range(cols - 1):
            square = {(row, col), (row, col + 1), (row + 1, col), (row + 1, col + 1)}
            if square <= points:
                core = (row, col)
                break
        if core is not None:
            break
    if core is None:
        raise ValueError("diagonal_endpoint_rays requires a 2x2 source core")

    core_row, core_col = core
    core_cells = {
        (core_row, core_col),
        (core_row, core_col + 1),
        (core_row + 1, core_col),
        (core_row + 1, core_col + 1),
    }
    for row, col in sorted(points - core_cells):
        if row <= core_row and col >= core_col + 1:
            dr, dc = -1, 1
        elif row >= core_row + 1 and col >= core_col + 1:
            dr, dc = 1, 1
        elif row >= core_row + 1 and col <= core_col:
            dr, dc = 1, -1
        elif row <= core_row and col <= core_col:
            dr, dc = -1, -1
        else:
            continue

        nr, nc = row + dr, col + dc
        while 0 <= nr < rows and 0 <= nc < cols:
            if transformed[nr][nc] == background_color:
                transformed[nr][nc] = source_color
            nr += dr
            nc += dc
    return transformed


def _diagonal_cross_from_singleton(grid, source_color=0, background_color=0):
    if not grid:
        return copy.deepcopy(grid)
    rows, cols = len(grid), len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("diagonal_cross_from_singleton requires a rectangular grid")
    if source_color in (None, background_color):
        colors = sorted({
            value
            for row in grid
            for value in row
            if value != background_color
        })
        if len(colors) != 1:
            raise ValueError("diagonal_cross_from_singleton requires one source color")
        source_color = colors[0]
    points = _positions(grid, source_color)
    if len(points) != 1:
        raise ValueError("diagonal_cross_from_singleton requires one source pixel")
    seed_row, seed_col = points[0]
    transformed = copy.deepcopy(grid)
    for delta_row, delta_col in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        row = seed_row
        col = seed_col
        while 0 <= row < rows and 0 <= col < cols:
            if transformed[row][col] not in (background_color, source_color):
                raise ValueError("diagonal_cross_from_singleton collides with non-background")
            transformed[row][col] = source_color
            row += delta_row
            col += delta_col
    return transformed


def _diagonal_rays_from_marker_corners(grid, marker_color, fill_color=0, background_color=0):
    transformed = copy.deepcopy(grid)
    rows, cols = len(grid), len(grid[0]) if grid else 0
    matched = False

    for top in range(rows - 1):
        for left in range(cols - 1):
            cells = [
                (top, left),
                (top, left + 1),
                (top + 1, left),
                (top + 1, left + 1),
            ]
            values = [grid[row][col] for row, col in cells]
            if any(value == background_color for value in values):
                continue
            other_colors = {value for value in values if value != marker_color}
            if marker_color not in values or len(other_colors) != 1:
                continue

            inferred_fill = next(iter(other_colors))
            if fill_color not in (None, background_color) and fill_color != inferred_fill:
                continue
            fill = inferred_fill
            marker_dirs = {
                (top, left): (-1, -1),
                (top, left + 1): (-1, 1),
                (top + 1, left): (1, -1),
                (top + 1, left + 1): (1, 1),
            }
            directions = [
                marker_dirs[(row, col)]
                for row, col in cells
                if grid[row][col] == marker_color
            ]
            if not directions:
                continue

            matched = True
            for row, col in cells:
                transformed[row][col] = fill
            for dr, dc in directions:
                for row, col in cells:
                    nr, nc = row + dr, col + dc
                    while 0 <= nr < rows and 0 <= nc < cols:
                        if transformed[nr][nc] in {background_color, marker_color}:
                            transformed[nr][nc] = fill
                        nr += dr
                        nc += dc

    if not matched:
        raise ValueError("diagonal_rays_from_marker_corners requires a two-color 2x2 marker block")
    return transformed


def _edge_barrier_orientation(grid, barrier_color):
    rows, cols = len(grid), len(grid[0]) if grid else 0
    if rows == 0 or cols == 0:
        return None

    left_width = 0
    while (
        left_width < cols
        and all(grid[row][left_width] == barrier_color for row in range(rows))
    ):
        left_width += 1
    if left_width:
        return "left"

    right_width = 0
    while (
        right_width < cols
        and all(grid[row][cols - 1 - right_width] == barrier_color for row in range(rows))
    ):
        right_width += 1
    if right_width:
        return "right"

    top_height = 0
    while (
        top_height < rows
        and all(grid[top_height][col] == barrier_color for col in range(cols))
    ):
        top_height += 1
    if top_height:
        return "top"

    bottom_height = 0
    while (
        bottom_height < rows
        and all(grid[rows - 1 - bottom_height][col] == barrier_color for col in range(cols))
    ):
        bottom_height += 1
    if bottom_height:
        return "bottom"

    return None


def _is_diagonal_segment(points):
    if len(points) < 2:
        return False
    ordered = sorted(points)
    row_diffs = [right[0] - left[0] for left, right in zip(ordered, ordered[1:])]
    col_diffs = [right[1] - left[1] for left, right in zip(ordered, ordered[1:])]
    return (
        all(delta == 1 for delta in row_diffs)
        and len(set(col_diffs)) == 1
        and abs(col_diffs[0]) == 1
    )


def _diagonal_reflect_edge_barrier(
    grid,
    fill_color,
    barrier_color,
    background_color=0,
):
    """Continue a diagonal seed as a ray that reflects off a solid edge barrier."""
    if not grid:
        return copy.deepcopy(grid)
    rows, cols = len(grid), len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("diagonal_reflect_edge_barrier requires a rectangular grid")
    if fill_color in (None, background_color) or barrier_color in (None, background_color):
        raise ValueError("diagonal_reflect_edge_barrier requires fill and barrier colors")

    orientation = _edge_barrier_orientation(grid, barrier_color)
    if orientation is None:
        raise ValueError("diagonal_reflect_edge_barrier requires a solid edge barrier")

    seed_colors = sorted(
        {
            value
            for row in grid
            for value in row
            if value not in (background_color, barrier_color)
        }
    )
    if len(seed_colors) != 1:
        raise ValueError("diagonal_reflect_edge_barrier requires one seed color")
    seed_color = seed_colors[0]
    seed_points = _positions(grid, seed_color)
    if not _is_diagonal_segment(seed_points):
        raise ValueError("diagonal_reflect_edge_barrier requires a diagonal seed segment")

    if orientation == "right":
        allowed_directions = [(-1, 1), (1, 1)]
        reflect_axis = "vertical"
    elif orientation == "left":
        allowed_directions = [(-1, -1), (1, -1)]
        reflect_axis = "vertical"
    elif orientation == "bottom":
        allowed_directions = [(1, -1), (1, 1)]
        reflect_axis = "horizontal"
    else:
        allowed_directions = [(-1, -1), (-1, 1)]
        reflect_axis = "horizontal"

    seed_set = set(seed_points)
    endpoints = [
        point
        for point in seed_points
        if sum(
            (point[0] + dr, point[1] + dc) in seed_set
            for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1))
        ) == 1
    ]
    if len(endpoints) != 2:
        raise ValueError("diagonal_reflect_edge_barrier requires two seed endpoints")

    candidates = []
    for endpoint in endpoints:
        for delta_row, delta_col in allowed_directions:
            previous = (endpoint[0] - delta_row, endpoint[1] - delta_col)
            start = (endpoint[0] + delta_row, endpoint[1] + delta_col)
            if previous not in seed_set:
                continue
            if not (0 <= start[0] < rows and 0 <= start[1] < cols):
                continue
            if grid[start[0]][start[1]] != background_color:
                continue
            candidates.append((endpoint, delta_row, delta_col))

    if len(candidates) != 1:
        raise ValueError("diagonal_reflect_edge_barrier requires one outgoing seed direction")

    endpoint, delta_row, delta_col = candidates[0]
    row = endpoint[0] + delta_row
    col = endpoint[1] + delta_col
    transformed = copy.deepcopy(grid)
    changed = False

    while 0 <= row < rows and 0 <= col < cols:
        value = transformed[row][col]
        if value == background_color:
            transformed[row][col] = fill_color
            changed = True
        elif value in (barrier_color, seed_color):
            break
        elif value != fill_color:
            raise ValueError("diagonal_reflect_edge_barrier ray collides with non-background")

        next_row = row + delta_row
        next_col = col + delta_col
        if not (0 <= next_row < rows and 0 <= next_col < cols):
            break
        if grid[next_row][next_col] == barrier_color:
            if reflect_axis == "vertical":
                delta_col *= -1
            else:
                delta_row *= -1
            next_row = row + delta_row
            next_col = col + delta_col
            if not (0 <= next_row < rows and 0 <= next_col < cols):
                break
            if grid[next_row][next_col] == barrier_color:
                break
        row, col = next_row, next_col

    if not changed:
        raise ValueError("diagonal_reflect_edge_barrier produced no ray")
    return transformed


def _orthogonal_marker_extend_overlap(grid, vertical_color=0, background_color=0):
    """Extend one marker color vertically and all other marker colors horizontally.

    This is the grid-level equivalent of applying `extend_node(overlap=True)`:
    vertical-color columns are drawn first, then horizontal marker rows are
    drawn over them.  The overwrite order is intentional; tasks in this family
    treat row beams as the foreground layer at intersections.
    """
    if not grid:
        return []
    rows, cols = len(grid), len(grid[0])
    points = _non_background_points(grid, background_color=background_color)
    if not points:
        raise ValueError("orthogonal_marker_extend_overlap requires foreground markers")

    colors = sorted({value for _, _, value in points})
    if vertical_color in (None, background_color):
        # Infer a stable vertical color only when there is exactly one repeated
        # foreground color; otherwise the caller should pass color1 explicitly.
        counts = Counter(value for _, _, value in points)
        repeated = [color for color, count in counts.items() if count > 1]
        if len(repeated) == 1:
            vertical_color = repeated[0]
        elif 2 in colors:
            vertical_color = 2
        else:
            raise ValueError("orthogonal_marker_extend_overlap needs a vertical marker color")
    if vertical_color not in colors:
        raise ValueError("orthogonal_marker_extend_overlap vertical color is absent")

    transformed = [[background_color for _ in range(cols)] for _ in range(rows)]
    for _, col, value in points:
        if value != vertical_color:
            continue
        for row in range(rows):
            transformed[row][col] = vertical_color

    for row, _, value in points:
        if value == vertical_color:
            continue
        for col in range(cols):
            transformed[row][col] = value

    return transformed


def _sign(value):
    return -1 if value < 0 else (1 if value > 0 else 0)


def _center_node_pattern_line(grid, background_color=0):
    """Repeat the central/largest component mask along marker directions.

    Marker components are interpreted as visible fragments of the next copy of
    the center pattern.  The copy step is one pattern bbox plus one blank gutter
    in the direction from the source pattern to the marker.
    """
    if not grid:
        return []
    rows, cols = len(grid), len(grid[0])
    components = []
    for color in sorted({
        value
        for row in grid
        for value in row
        if value != background_color
    }):
        for component in _color_components(grid, color, connectivity=8):
            if component:
                min_row, max_row, min_col, max_col = _component_bbox(component)
                components.append({
                    "color": color,
                    "pixels": set(component),
                    "bbox": (min_row, max_row, min_col, max_col),
                })
    if len(components) < 2:
        raise ValueError("center_node_pattern_line requires a source pattern and markers")

    source = max(
        components,
        key=lambda item: (
            len(item["pixels"]),
            (item["bbox"][1] - item["bbox"][0] + 1) * (item["bbox"][3] - item["bbox"][2] + 1),
        ),
    )
    src_min_r, src_max_r, src_min_c, src_max_c = source["bbox"]
    pattern_h = src_max_r - src_min_r + 1
    pattern_w = src_max_c - src_min_c + 1
    if pattern_h == 0 or pattern_w == 0:
        raise ValueError("center_node_pattern_line source pattern has empty bbox")
    mask = {
        (row - src_min_r, col - src_min_c)
        for row, col in source["pixels"]
    }
    if not mask:
        raise ValueError("center_node_pattern_line source pattern has empty mask")

    transformed = copy.deepcopy(grid)
    used_marker = False
    for marker in components:
        if marker is source:
            continue
        marker_pixels = marker["pixels"]
        mark_min_r, mark_max_r, mark_min_c, mark_max_c = marker["bbox"]
        # Direction is measured from the source bbox to the marker bbox.  A
        # marker overlapping the source span on one axis repeats along the other
        # axis; diagonal markers repeat diagonally.
        if mark_max_r < src_min_r:
            dir_r = -1
        elif mark_min_r > src_max_r:
            dir_r = 1
        else:
            dir_r = 0
        if mark_max_c < src_min_c:
            dir_c = -1
        elif mark_min_c > src_max_c:
            dir_c = 1
        else:
            dir_c = 0
        if dir_r == 0 and dir_c == 0:
            continue

        step_r = dir_r * (pattern_h + 1)
        step_c = dir_c * (pattern_w + 1)
        first_top = src_min_r + step_r
        first_left = src_min_c + step_c

        translated_mask = {
            (first_top + rel_r, first_left + rel_c)
            for rel_r, rel_c in mask
        }
        if not marker_pixels <= translated_mask:
            # Some singleton markers may identify any visible cell of the first
            # copy.  If the canonical gutter step does not explain the fragment,
            # try the placement implied directly by marker-to-mask alignment and
            # keep the closest placement in the same direction.
            candidates = []
            for marker_row, marker_col in marker_pixels:
                for rel_r, rel_c in mask:
                    top = marker_row - rel_r
                    left = marker_col - rel_c
                    candidate_mask = {
                        (top + r, left + c)
                        for r, c in mask
                    }
                    if marker_pixels <= candidate_mask:
                        delta_r = top - src_min_r
                        delta_c = left - src_min_c
                        if _sign(delta_r) == dir_r and _sign(delta_c) == dir_c:
                            candidates.append((
                                abs(top - first_top) + abs(left - first_left),
                                top,
                                left,
                            ))
            if not candidates:
                continue
            _, first_top, first_left = min(candidates)
            step_r = first_top - src_min_r
            step_c = first_left - src_min_c
            if step_r == 0 and step_c == 0:
                continue

        top, left = first_top, first_left
        while True:
            bbox_outside = (
                top >= rows
                or left >= cols
                or top + pattern_h - 1 < 0
                or left + pattern_w - 1 < 0
            )
            if bbox_outside:
                break
            for rel_r, rel_c in mask:
                row = top + rel_r
                col = left + rel_c
                if 0 <= row < rows and 0 <= col < cols:
                    transformed[row][col] = marker["color"]
            used_marker = True
            top += step_r
            left += step_c

    if not used_marker:
        raise ValueError("center_node_pattern_line found no usable marker directions")
    return transformed


def _split_endpoint_lines(grid, separator_color=5, background_color=0):
    if not grid:
        return []
    rows, cols = len(grid), len(grid[0])
    transformed = copy.deepcopy(grid)
    changed = False

    row_pairs = []
    for row_index, row in enumerate(grid):
        points = [(col, value) for col, value in enumerate(row) if value != background_color]
        if len(points) != 2:
            continue
        (left_col, left_color), (right_col, right_color) = sorted(points)
        if right_col - left_col < 2:
            continue
        row_pairs.append((row_index, left_col, left_color, right_col, right_color))

    for row_index, left_col, left_color, right_col, right_color in row_pairs:
        mid_col = (left_col + right_col) // 2
        for col in range(left_col, right_col + 1):
            if col < mid_col:
                transformed[row_index][col] = left_color
            elif col == mid_col:
                transformed[row_index][col] = separator_color
            else:
                transformed[row_index][col] = right_color
        changed = True

    if not row_pairs:
        for col_index in range(cols):
            points = [
                (row_index, grid[row_index][col_index])
                for row_index in range(rows)
                if grid[row_index][col_index] != background_color
            ]
            if len(points) != 2:
                continue
            (top_row, top_color), (bottom_row, bottom_color) = sorted(points)
            if bottom_row - top_row < 2:
                continue
            mid_row = (top_row + bottom_row) // 2
            for row in range(top_row, bottom_row + 1):
                if row < mid_row:
                    transformed[row][col_index] = top_color
                elif row == mid_row:
                    transformed[row][col_index] = separator_color
                else:
                    transformed[row][col_index] = bottom_color
            changed = True

    if not changed:
        raise ValueError("split_endpoint_lines found no separated endpoint pairs")
    return transformed


def _orthogonal_endpoint_lines(grid, intersection_color=4, background_color=0):
    if not grid:
        return []
    rows, cols = len(grid), len(grid[0])
    by_color = defaultdict(list)
    for row in range(rows):
        for col in range(cols):
            value = grid[row][col]
            if value != background_color:
                by_color[value].append((row, col))

    horizontal = []
    vertical = []
    for color, points in by_color.items():
        if len(points) < 2:
            continue
        point_rows = {row for row, _ in points}
        point_cols = {col for _, col in points}
        if len(point_rows) == 1:
            horizontal.append((next(iter(point_rows)), color))
        if len(point_cols) == 1:
            vertical.append((next(iter(point_cols)), color))

    if not horizontal or not vertical:
        raise ValueError("orthogonal_endpoint_lines requires horizontal and vertical endpoint runs")

    transformed = copy.deepcopy(grid)
    for row, color in horizontal:
        for col in range(cols):
            transformed[row][col] = color
    for col, color in vertical:
        for row in range(rows):
            if any(row == horizontal_row for horizontal_row, _ in horizontal):
                transformed[row][col] = intersection_color
            else:
                transformed[row][col] = color
    return transformed


def _same_color_components(grid, color):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    visited = set()
    components = []
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] != color or (row, col) in visited:
                continue
            stack = [(row, col)]
            visited.add((row, col))
            pixels = []
            while stack:
                current_row, current_col = stack.pop()
                pixels.append((current_row, current_col))
                for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    next_row = current_row + delta_row
                    next_col = current_col + delta_col
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if (next_row, next_col) in visited:
                        continue
                    if grid[next_row][next_col] != color:
                        continue
                    visited.add((next_row, next_col))
                    stack.append((next_row, next_col))
            components.append(pixels)
    return components


def _color_order_diagonal_component_rays(
    grid,
    northwest_color=1,
    southeast_color=2,
    background_color=0,
):
    if not grid:
        return []
    rows, cols = len(grid), len(grid[0])
    transformed = copy.deepcopy(grid)
    changed = False

    for color, delta_row, delta_col, corner in (
        (northwest_color, -1, -1, "northwest"),
        (southeast_color, 1, 1, "southeast"),
    ):
        components = _same_color_components(grid, color)
        if not components:
            raise ValueError("diagonal component rays require both ordered colors")
        for pixels in components:
            min_row = min(row for row, _ in pixels)
            max_row = max(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            max_col = max(col for _, col in pixels)
            if corner == "northwest":
                row, col = min_row - 1, min_col - 1
            else:
                row, col = max_row + 1, max_col + 1
            while 0 <= row < rows and 0 <= col < cols:
                if transformed[row][col] not in (background_color, color):
                    raise ValueError("diagonal component ray collides with non-background")
                transformed[row][col] = color
                changed = True
                row += delta_row
                col += delta_col

    if not changed:
        raise ValueError("diagonal component rays produced no extension")
    return transformed


def _l_component_missing_corner_rays(grid, background_color=0):
    if not grid:
        return []
    rows, cols = len(grid), len(grid[0])
    colors = sorted(
        {
            value
            for row in grid
            for value in row
            if value != background_color
        }
    )
    if len(colors) != 1:
        raise ValueError("L-component corner rays require one foreground color")
    color = colors[0]
    components = _same_color_components(grid, color)
    if not components:
        raise ValueError("L-component corner rays require components")

    transformed = copy.deepcopy(grid)
    changed = False
    for pixels in components:
        min_row = min(row for row, _ in pixels)
        max_row = max(row for row, _ in pixels)
        min_col = min(col for _, col in pixels)
        max_col = max(col for _, col in pixels)
        bbox_cells = {
            (row, col)
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
        }
        pixel_set = set(pixels)
        missing = sorted(bbox_cells - pixel_set)
        if len(pixel_set) != 3 or len(bbox_cells) != 4 or len(missing) != 1:
            raise ValueError("L-component corner rays require 2x2 L components")
        missing_row, missing_col = missing[0]
        if missing_row == min_row and missing_col == min_col:
            delta_row, delta_col = -1, -1
        elif missing_row == min_row and missing_col == max_col:
            delta_row, delta_col = -1, 1
        elif missing_row == max_row and missing_col == min_col:
            delta_row, delta_col = 1, -1
        elif missing_row == max_row and missing_col == max_col:
            delta_row, delta_col = 1, 1
        else:
            raise ValueError("L-component missing cell is not a bbox corner")

        row = missing_row + delta_row
        col = missing_col + delta_col
        while 0 <= row < rows and 0 <= col < cols:
            if transformed[row][col] not in (background_color, color):
                raise ValueError("L-component corner ray collides with non-background")
            transformed[row][col] = color
            changed = True
            row += delta_row
            col += delta_col

    if not changed:
        raise ValueError("L-component corner rays produced no extension")
    return transformed


def _aligned_marker_rectangle_beams(grid, background_color=0):
    if not grid:
        return []
    rows, cols = len(grid), len(grid[0])
    components = []
    visited = set()
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] == background_color or (row, col) in visited:
                continue
            color = grid[row][col]
            stack = [(row, col)]
            visited.add((row, col))
            pixels = []
            while stack:
                current_row, current_col = stack.pop()
                pixels.append((current_row, current_col))
                for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    next_row = current_row + delta_row
                    next_col = current_col + delta_col
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if (next_row, next_col) in visited:
                        continue
                    if grid[next_row][next_col] != color:
                        continue
                    visited.add((next_row, next_col))
                    stack.append((next_row, next_col))
            min_row = min(r for r, _ in pixels)
            max_row = max(r for r, _ in pixels)
            min_col = min(c for _, c in pixels)
            max_col = max(c for _, c in pixels)
            area = (max_row - min_row + 1) * (max_col - min_col + 1)
            components.append({
                "color": color,
                "pixels": pixels,
                "bbox": (min_row, max_row, min_col, max_col),
                "solid": area == len(pixels),
                "area": area,
            })

    rectangles = [
        component
        for component in components
        if component["solid"] and component["area"] >= 4
    ]
    if not rectangles:
        raise ValueError("aligned marker beams require a solid rectangle")
    rectangle = max(rectangles, key=lambda component: (component["area"], len(component["pixels"])))
    rect_color = rectangle["color"]
    min_row, max_row, min_col, max_col = rectangle["bbox"]

    transformed = copy.deepcopy(grid)
    changed = False
    for component in components:
        if component is rectangle or len(component["pixels"]) != 1:
            continue
        marker_row, marker_col = component["pixels"][0]
        marker_color = component["color"]
        line = []
        if min_row <= marker_row <= max_row:
            if marker_col < min_col:
                line = [(marker_row, col) for col in range(marker_col, min_col)]
            elif marker_col > max_col:
                line = [(marker_row, col) for col in range(max_col + 1, marker_col + 1)]
        elif min_col <= marker_col <= max_col:
            if marker_row < min_row:
                line = [(row, marker_col) for row in range(marker_row, min_row)]
            elif marker_row > max_row:
                line = [(row, marker_col) for row in range(max_row + 1, marker_row + 1)]

        for row, col in line:
            if transformed[row][col] not in (background_color, marker_color):
                raise ValueError("aligned marker beam collides with non-background")
            if transformed[row][col] == background_color:
                changed = True
            transformed[row][col] = marker_color

    if not changed:
        raise ValueError("aligned marker beams produced no extension")
    return transformed


def _source_pattern_line(grid, source_color, fill_color, background_color=0):
    if not grid:
        return copy.deepcopy(grid)
    rows, cols = len(grid), len(grid[0])
    transformed = copy.deepcopy(grid)
    threshold = max(1, cols // 2)
    template_rows = [
        row
        for row in grid
        if sum(value == source_color for value in row) >= threshold
    ]
    if not template_rows:
        raise ValueError("pattern_line requires at least one source template row")

    for row_index, row in enumerate(grid):
        source_cols = [col for col, value in enumerate(row) if value == source_color]
        if not source_cols or len(source_cols) >= threshold:
            continue
        if row_index > 0:
            previous_cols = [
                col for col, value in enumerate(grid[row_index - 1])
                if value == source_color
            ]
            if (
                previous_cols
                and len(previous_cols) < threshold
                and max(source_cols) == max(previous_cols) + 1
            ):
                continue
        for template in template_rows:
            if all(template[col] == source_color for col in source_cols):
                last_source_col = max(source_cols)
                for col in range(last_source_col + 1, cols):
                    if row[col] == background_color and template[col] == source_color:
                        transformed[row_index][col] = fill_color
                break

    # Some source patterns are multi-row line motifs.  If two sparse rows form
    # a one-step diagonal prefix and the following row is blank, continue the
    # motif on that following row with the fill color.
    for row_index in range(rows - 2):
        first_cols = [
            col for col, value in enumerate(grid[row_index])
            if value == source_color
        ]
        second_cols = [
            col for col, value in enumerate(grid[row_index + 1])
            if value == source_color
        ]
        if not first_cols or not second_cols:
            continue
        if len(first_cols) >= threshold or len(second_cols) >= threshold:
            continue
        if max(second_cols) != max(first_cols) + 1:
            continue
        if any(value != background_color for value in grid[row_index + 2]):
            continue
        start_col = max(second_cols) + 1
        if start_col >= cols:
            continue
        for col in range(start_col, cols):
            if transformed[row_index + 2][col] == background_color:
                transformed[row_index + 2][col] = fill_color

    return transformed


def _mirrored_interval_pattern_line(grid, background_color=0):
    if not grid:
        return copy.deepcopy(grid)
    rows, cols = len(grid), len(grid[0])
    transformed = copy.deepcopy(grid)
    color_counts = defaultdict(int)
    for row in grid:
        for value in row:
            if value != background_color:
                color_counts[value] += 1
    if not color_counts:
        raise ValueError("pattern_line requires source colors")
    max_count = max(color_counts.values())
    line_colors = {
        color
        for color, count in color_counts.items()
        if count == max_count and count >= 2
    }
    if not line_colors:
        raise ValueError("pattern_line found no repeated line colors")

    def fill_axis(groups, total_points, horizontal=True):
        if total_points < 4:
            return
        for color, positions in groups.items():
            if color not in line_colors:
                continue
            ordered = sorted(positions)
            for start, end in zip(ordered, ordered[1:]):
                distance = (
                    end[1] - start[1]
                    if horizontal
                    else end[0] - start[0]
                )
                if distance <= 2 or distance % 2 != 0:
                    continue
                if horizontal:
                    row = start[0]
                    path = [(row, col) for col in range(start[1] + 2, end[1], 2)]
                    blockers = [
                        (row, col)
                        for col in range(start[1] + 1, end[1])
                        if grid[row][col] != background_color
                    ]
                else:
                    col = start[1]
                    path = [(row, col) for row in range(start[0] + 2, end[0], 2)]
                    blockers = [
                        (row, col)
                        for row in range(start[0] + 1, end[0])
                        if grid[row][col] != background_color
                    ]
                if blockers:
                    continue
                for row, col in path:
                    transformed[row][col] = color

    row_groups = defaultdict(lambda: defaultdict(list))
    col_groups = defaultdict(lambda: defaultdict(list))
    for row in range(rows):
        for col in range(cols):
            value = grid[row][col]
            if value == background_color:
                continue
            row_groups[row][value].append((row, col))
            col_groups[col][value].append((row, col))

    for groups in row_groups.values():
        fill_axis(
            groups,
            sum(len(positions) for positions in groups.values()),
            horizontal=True,
        )
    for groups in col_groups.values():
        fill_axis(
            groups,
            sum(len(positions) for positions in groups.values()),
            horizontal=False,
        )

    return transformed


def _recolor_periodic_line_alternation(grid, fill_color, background_color=0):
    """Recolor every second occurrence on periodic diagonal line orbits."""
    if not grid:
        return copy.deepcopy(grid)
    rows, cols = len(grid), len(grid[0])
    transformed = copy.deepcopy(grid)
    colors = sorted(
        {
            value
            for row in grid
            for value in row
            if value != background_color
        }
    )
    if len(colors) != 1:
        raise ValueError("periodic_line_alternation requires one source color")
    source_color = colors[0]

    total_points = sum(value == source_color for row in grid for value in row)
    for direction in (1, -1):
        grouped = defaultdict(list)
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != source_color:
                    continue
                key = (row - col) % cols if direction == 1 else (row + col) % cols
                grouped[key].append((row, col))

        coverage = []
        for positions in grouped.values():
            if len(positions) < 3:
                continue
            ordered = sorted(positions)
            if all(
                ordered[index + 1][0] - ordered[index][0] == 1
                for index in range(len(ordered) - 1)
            ):
                coverage.append(ordered)

        if coverage and sum(len(group) for group in coverage) == total_points:
            for ordered in coverage:
                for index, (row, col) in enumerate(ordered):
                    if index % 2 == 1:
                        transformed[row][col] = fill_color
            return transformed

    raise ValueError("periodic_line_alternation found no periodic line orbits")


def _frame_marker_projection(grid, background_color=0):
    """Project embedded frame markers through a two-color rectangular field.

    The common ARC shape here is a thick rectangular frame of one color around
    another fill color.  Fill-colored pixels embedded in the frame are markers:
    vertical markers carve border-colored columns through the fill and extend
    fill-colored rays outside the rectangle; horizontal markers do the analogous
    row projection.
    """
    if not grid:
        return copy.deepcopy(grid)

    rows, cols = len(grid), len(grid[0])
    output = copy.deepcopy(grid)
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background_color
    )
    if len(counts) != 2:
        raise ValueError("frame_marker_projection requires exactly two foreground colors")

    points = [
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if grid[row][col] != background_color
    ]
    if not points:
        raise ValueError("frame_marker_projection requires foreground pixels")

    min_row = min(row for row, _ in points)
    max_row = max(row for row, _ in points)
    min_col = min(col for _, col in points)
    max_col = max(col for _, col in points)
    width = max_col - min_col + 1
    height = max_row - min_row + 1
    if width < 3 or height < 3:
        raise ValueError("frame_marker_projection requires a rectangular field")

    corner_values = [
        grid[min_row][min_col],
        grid[min_row][max_col],
        grid[max_row][min_col],
        grid[max_row][max_col],
    ]
    corner_counts = Counter(
        value for value in corner_values if value != background_color
    )
    if not corner_counts:
        raise ValueError("frame_marker_projection could not infer frame color")
    border_color = corner_counts.most_common(1)[0][0]
    fill_colors = [color for color in counts if color != border_color]
    if len(fill_colors) != 1:
        raise ValueError("frame_marker_projection could not infer fill color")
    fill_color = fill_colors[0]

    def border_count_in_row(row):
        return sum(grid[row][col] == border_color for col in range(min_col, max_col + 1))

    # A frame band is a run from an edge whose cells are mostly border color.
    row_threshold = max(1, width // 2)

    top_band = []
    row = min_row
    while row <= max_row and border_count_in_row(row) >= row_threshold:
        top_band.append(row)
        row += 1

    bottom_band = []
    row = max_row
    while row >= min_row and border_count_in_row(row) >= row_threshold:
        bottom_band.append(row)
        row -= 1
    bottom_band = list(reversed(bottom_band))

    # The side frame thickness follows the top/bottom band thickness in this
    # family.  Scanning full columns by majority is too permissive when the
    # inner field has tall solid regions adjacent to the side frame.
    side_width = min(len(top_band), len(bottom_band))
    left_band = list(range(min_col, min(min_col + side_width, max_col + 1)))
    right_band = list(range(max(max_col - side_width + 1, min_col), max_col + 1))

    if not (top_band and bottom_band and left_band and right_band):
        raise ValueError("frame_marker_projection could not infer all frame bands")

    inner_top = min_row + len(top_band)
    inner_bottom = max_row - len(bottom_band)
    inner_left = min_col + len(left_band)
    inner_right = max_col - len(right_band)
    if inner_top > inner_bottom or inner_left > inner_right:
        raise ValueError("frame_marker_projection frame consumes entire field")

    marker_cols = {
        col
        for row in top_band + bottom_band
        for col in range(min_col, max_col + 1)
        if grid[row][col] == fill_color
    }
    marker_rows = {
        row
        for row in range(min_row, max_row + 1)
        for col in left_band + right_band
        if grid[row][col] == fill_color
    }
    if not marker_cols and not marker_rows:
        raise ValueError("frame_marker_projection found no embedded markers")

    # Repair marker pixels in the frame itself back to the border color.
    for row in top_band + bottom_band:
        for col in range(min_col, max_col + 1):
            if output[row][col] == fill_color:
                output[row][col] = border_color
    for row in range(min_row, max_row + 1):
        for col in left_band + right_band:
            if output[row][col] == fill_color:
                output[row][col] = border_color

    for col in marker_cols:
        for row in range(rows):
            if row < min_row or row > max_row:
                output[row][col] = fill_color
            elif inner_top <= row <= inner_bottom and output[row][col] == fill_color:
                output[row][col] = border_color

    for row in marker_rows:
        for col in range(cols):
            if col < min_col or col > max_col:
                output[row][col] = fill_color
            elif inner_left <= col <= inner_right and output[row][col] == fill_color:
                output[row][col] = border_color

    return output


def _between_runs_horizontal(grid, color1, color2, background_color=0):
    """Fill horizontal gaps between consecutive same-color runs.

    This is stricter than the point-pair beam: it works at run level and avoids
    long connections into a singleton endpoint, which otherwise creates spurious
    bridges in dense line drawings.
    """
    transformed = copy.deepcopy(grid)
    if not grid:
        return transformed

    for row_index, row in enumerate(grid):
        runs = []
        col = 0
        while col < len(row):
            if row[col] != color1:
                col += 1
                continue
            start = col
            while col + 1 < len(row) and row[col + 1] == color1:
                col += 1
            end = col
            runs.append((start, end))
            col += 1

        for (left_start, left_end), (right_start, right_end) in zip(runs, runs[1:]):
            gap_start = left_end + 1
            gap_end = right_start - 1
            if gap_start > gap_end:
                continue
            gap_len = gap_end - gap_start + 1
            left_len = left_end - left_start + 1
            right_len = right_end - right_start + 1
            if min(left_len, right_len) == 1 and gap_len > 1:
                continue
            if any(row[col] != background_color for col in range(gap_start, gap_end + 1)):
                continue
            for col in range(gap_start, gap_end + 1):
                transformed[row_index][col] = color2

    return transformed


def _horizontal_frame_fill(grid, color1, color2, background_color=0):
    """Fill interiors implied by matching horizontal frame runs.

    A pair of equal horizontal runs of `color1` forms the top/bottom of a
    rectangular frame.  If the intervening rows carry the required side boundary
    cells, fill the interior background cells with `color2`.  Runs touching the
    left or right image edge use that edge as the missing side boundary.
    """
    transformed = copy.deepcopy(grid)
    if not grid:
        return transformed

    rows, cols = len(grid), len(grid[0])

    def horizontal_runs(row):
        runs = []
        col = 0
        while col < cols:
            if row[col] != color1:
                col += 1
                continue
            start = col
            while col + 1 < cols and row[col + 1] == color1:
                col += 1
            end = col
            if end - start + 1 >= 2:
                runs.append((start, end))
            col += 1
        return runs

    runs_by_row = [horizontal_runs(row) for row in grid]
    for top_row, runs in enumerate(runs_by_row):
        for start_col, end_col in runs:
            for bottom_row in range(top_row + 2, rows):
                if (start_col, end_col) not in runs_by_row[bottom_row]:
                    continue
                if any(
                    (start_col, end_col) in runs_by_row[mid_row]
                    for mid_row in range(top_row + 1, bottom_row)
                ):
                    continue

                if start_col == 0:
                    fill_start, fill_end = start_col, end_col - 1
                    boundary_cols = [end_col]
                elif end_col == cols - 1:
                    fill_start, fill_end = start_col + 1, end_col
                    boundary_cols = [start_col]
                else:
                    fill_start, fill_end = start_col + 1, end_col - 1
                    boundary_cols = [start_col, end_col]

                if fill_start > fill_end:
                    continue

                if not all(
                    grid[row][boundary_col] == color1
                    for row in range(top_row + 1, bottom_row)
                    for boundary_col in boundary_cols
                ):
                    continue

                for row in range(top_row + 1, bottom_row):
                    for col in range(fill_start, fill_end + 1):
                        if grid[row][col] == background_color:
                            transformed[row][col] = color2

    return transformed


def _classifier_owl_classes(classifier_params):
    if not isinstance(classifier_params, dict):
        return set()
    classes = set()
    owl_class = classifier_params.get("owl_class")
    if owl_class:
        classes.add(owl_class)
    owl_classes = classifier_params.get("owl_classes") or []
    if isinstance(owl_classes, str):
        classes.add(owl_classes)
    else:
        classes.update(owl_classes)
    return classes


def _require_complex_pattern_line_class(beam_type, classifier_params):
    required_owl_classes = {
        "pattern_line": "line_template_shape",
        "center_node_pattern_line": "center_node_template_shape",
        "periodic_line_alternation": "periodic_line_orbit_shape",
    }
    owl_class = required_owl_classes.get(beam_type)
    if not owl_class:
        return
    if owl_class not in _classifier_owl_classes(classifier_params):
        raise ValueError(f"{beam_type} requires OWL class {owl_class}")


def beam_grid_based(grid, color1=0, color2: int = 0, beam_type="color_inheritance", classifier_params=None):
    if beam_type == "box_based":
        flat_grid = [val for row in grid for val in row]
        background_color = max(set(flat_grid), key=flat_grid.count)
        object_colors = set(flat_grid) - {background_color}
        objects = find_connected_components(
            grid,
            target_colors=object_colors,
            background_color=background_color,
            connectivity=4,
        )
        transformed_grid = [list(row) for row in grid]
        for obj in objects:
            object_cells = set(obj["pixels"])
            min_row, max_row, min_col, max_col = find_bounding_rectangle(obj["pixels"])

            delta_cells = {
                (row, col)
                for row in range(min_row, max_row + 1)
                for col in range(min_col, max_col + 1)
                if (row, col) not in object_cells
            }

            for row, col in delta_cells:
                transformed_grid[row][col] = color1

            perimeter_cells = (
                {(min_row, col) for col in range(min_col, max_col + 1)}
                .union({(max_row, col) for col in range(min_col, max_col + 1)})
                .union({(row, min_col) for row in range(min_row, max_row + 1)})
                .union({(row, max_col) for row in range(min_row, max_row + 1)})
            )

            perimeter_diff = perimeter_cells - object_cells

            center_row = (min_row + max_row) / 2
            center_col = (min_col + max_col) / 2

            shooting_directions = {}
            for row, col in perimeter_diff:
                dr = -1 if row < center_row else (1 if row > center_row else 0)
                dc = -1 if col < center_col else (1 if col > center_col else 0)
                if abs(row - center_row) > abs(col - center_col):
                    dc = 0
                elif abs(col - center_col) > abs(row - center_row):
                    dr = 0
                if dr != 0 or dc != 0:
                    shooting_directions[(row, col)] = (dr, dc)

            for (row, col), (dr, dc) in shooting_directions.items():
                current_row, current_col = row + dr, col + dc
                while 0 <= current_row < len(grid) and 0 <= current_col < len(grid[0]):
                    if (current_row, current_col) in object_cells:
                        break
                    transformed_grid[current_row][current_col] = color1
                    current_row += dr
                    current_col += dc
        return transformed_grid

    elif beam_type == "infect":
        transformed_grid = copy.deepcopy(grid)
        rows, cols = len(grid), len(grid[0]) if grid else 0
        connected_components = find_connected_components(
            transformed_grid,
            target_colors=[color1],
            background_color=-1,
            connectivity=4,
        )
        rectangle_labels = [[-1] * cols for _ in range(rows)]
        rectangles = [component["pixels"] for component in connected_components]
        for idx, component in enumerate(connected_components):
            for r, c in component["pixels"]:
                rectangle_labels[r][c] = idx
        edge_pixels = (
            [(0, c, 1, 0) for c in range(cols) if transformed_grid[0][c] == color2]
            + [
                (rows - 1, c, -1, 0)
                for c in range(cols)
                if transformed_grid[rows - 1][c] == color2
            ]
            + [(r, 0, 0, 1) for r in range(rows) if transformed_grid[r][0] == color2]
            + [
                (r, cols - 1, 0, -1)
                for r in range(rows)
                if transformed_grid[r][cols - 1] == color2
            ]
        )
        recolored_rectangles = set()
        for r, c, dr, dc in edge_pixels:
            nr, nc = r + dr, c + dc
            while 0 <= nr < rows and 0 <= nc < cols:
                if transformed_grid[nr][nc] == color1:
                    rect_id = rectangle_labels[nr][nc]
                    if rect_id not in recolored_rectangles:
                        for rr, cc in rectangles[rect_id]:
                            transformed_grid[rr][cc] = color2
                        recolored_rectangles.add(rect_id)
                else:
                    transformed_grid[nr][nc] = color2

                for adj_r, adj_c in get_neighbors(
                    (nr, nc), (rows, cols), connectivity=4
                ):
                    if transformed_grid[adj_r][adj_c] == color1:
                        adj_rect_id = rectangle_labels[adj_r][adj_c]
                        if adj_rect_id not in recolored_rectangles:
                            for arr, acc in rectangles[adj_rect_id]:
                                transformed_grid[arr][acc] = color2
                            recolored_rectangles.add(adj_rect_id)
                nr, nc = nr + dr, nc + dc
        return transformed_grid

    elif beam_type == "linspace":
        n_rows, n_cols = len(grid), len(grid[0]) if grid else 0
        positions = sorted(
            (i, j)
            for i, row in enumerate(grid)
            for j, val in enumerate(row)
            if val == color1
        )
        delta_row, delta_col = (
            positions[1][0] - positions[0][0],
            positions[1][1] - positions[0][1],
        )
        new_grid = [row[:] for row in grid]
        last_row, last_col = positions[-1]
        while 0 <= last_row + delta_row < n_rows and 0 <= last_col + delta_col < n_cols:
            last_row += delta_row
            last_col += delta_col
            new_grid[last_row][last_col] = color2
        return new_grid

    elif beam_type in {
        "between_pairs",
        "between_pairs_horizontal",
        "between_pairs_vertical",
    }:
        transformed_grid = copy.deepcopy(grid)
        if not grid:
            return transformed_grid

        flat_grid = [value for row in grid for value in row]
        background_color = 0 if 0 in flat_grid else max(set(flat_grid), key=flat_grid.count)
        rows, cols = len(grid), len(grid[0])

        def fill_segments(grouped_positions, horizontal):
            for positions in grouped_positions.values():
                ordered = sorted(positions)
                for start, end in zip(ordered, ordered[1:]):
                    if horizontal:
                        row = start[0]
                        between = [(row, col) for col in range(start[1] + 1, end[1])]
                    else:
                        col = start[1]
                        between = [(row, col) for row in range(start[0] + 1, end[0])]
                    if between and all(grid[row][col] == background_color for row, col in between):
                        for row, col in between:
                            transformed_grid[row][col] = color2

        row_groups = defaultdict(list)
        col_groups = defaultdict(list)
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] == color1:
                    row_groups[row].append((row, col))
                    col_groups[col].append((row, col))

        if beam_type in {"between_pairs", "between_pairs_horizontal"}:
            fill_segments(row_groups, horizontal=True)
        if beam_type in {"between_pairs", "between_pairs_vertical"}:
            fill_segments(col_groups, horizontal=False)
        return transformed_grid

    elif beam_type == "broken_line":
        transformed_grid = copy.deepcopy(grid)
        if not grid:
            return transformed_grid

        flat_grid = [value for row in grid for value in row]
        background_color = max(set(flat_grid), key=flat_grid.count)
        rows, cols = len(grid), len(grid[0])

        if color1 == 0:
            marker_positions = [
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] not in {background_color, color2}
            ]
        else:
            marker_positions = [
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] == color1
            ]

        row_groups = defaultdict(list)
        col_groups = defaultdict(list)
        for row, col in marker_positions:
            row_groups[row].append((row, col))
            col_groups[col].append((row, col))

        def add_broken_segment(start, end, horizontal):
            distance = (
                abs(end[1] - start[1])
                if horizontal
                else abs(end[0] - start[0])
            )
            if distance <= 2:
                return

            if horizontal:
                row = start[0]
                low_col, high_col = sorted((start[1], end[1]))
                between = [(row, col) for col in range(low_col + 1, high_col)]
                direction_cells = lambda offset: (
                    (row, low_col + offset),
                    (row, high_col - offset),
                )
            else:
                col = start[1]
                low_row, high_row = sorted((start[0], end[0]))
                between = [(row, col) for row in range(low_row + 1, high_row)]
                direction_cells = lambda offset: (
                    (low_row + offset, col),
                    (high_row - offset, col),
                )

            if not between or any(grid[row][col] != background_color for row, col in between):
                return

            offset = 2
            while offset <= distance / 2:
                for row, col in direction_cells(offset):
                    if grid[row][col] == background_color:
                        transformed_grid[row][col] = color2
                offset += 2

        for positions in row_groups.values():
            ordered = sorted(positions)
            for start, end in zip(ordered, ordered[1:]):
                add_broken_segment(start, end, horizontal=True)

        for positions in col_groups.values():
            ordered = sorted(positions)
            for start, end in zip(ordered, ordered[1:]):
                add_broken_segment(start, end, horizontal=False)

        return transformed_grid

    elif beam_type == "repeat_pattern_line":
        return _repeat_pattern_line(grid)

    elif beam_type == "pattern_line":
        _require_complex_pattern_line_class(beam_type, classifier_params)
        if color2 == 0:
            return _mirrored_interval_pattern_line(grid)
        return _source_pattern_line(grid, source_color=color1, fill_color=color2)

    elif beam_type == "center_node_pattern_line":
        _require_complex_pattern_line_class(beam_type, classifier_params)
        return _center_node_pattern_line(grid)

    elif beam_type == "split_endpoint_lines":
        return _split_endpoint_lines(grid, separator_color=color1)

    elif beam_type == "orthogonal_endpoint_lines":
        return _orthogonal_endpoint_lines(grid, intersection_color=color1)

    elif beam_type == "color_order_diagonal_component_rays":
        return _color_order_diagonal_component_rays(
            grid,
            northwest_color=color1,
            southeast_color=color2,
        )

    elif beam_type == "l_component_missing_corner_rays":
        return _l_component_missing_corner_rays(grid)

    elif beam_type == "aligned_marker_rectangle_beams":
        return _aligned_marker_rectangle_beams(grid)

    elif beam_type == "periodic_line_alternation":
        _require_complex_pattern_line_class(beam_type, classifier_params)
        return _recolor_periodic_line_alternation(grid, fill_color=color2)

    elif beam_type == "fill_component_bbox_holes":
        return _fill_component_bbox_holes(grid, source_color=color1, fill_color=color2)

    elif beam_type == "fill_open_frame_from_marker":
        return _fill_open_frame_from_marker(grid, frame_color=color1)

    elif beam_type == "l_path_between_markers":
        return _l_path_between_markers(grid, source_color=color1, fill_color=color2)

    elif beam_type == "corner_anchor_rectangle_fill":
        return _corner_anchor_rectangle_fill(grid, anchor_color=color1, fill_color=color2)

    elif beam_type == "rectangle_gap_fill":
        return _rectangle_gap_fill(grid, fill_color=color2)

    elif beam_type == "midpoint_cross_between_markers":
        return _midpoint_cross_between_markers(grid, marker_color=color1, fill_color=color2)

    elif beam_type == "diagonal_pyramid_from_base_run":
        return _diagonal_pyramid_from_base_run(grid, target_color=color1)

    elif beam_type == "right_edge_waterfall":
        return _right_edge_waterfall(grid)

    elif beam_type == "diagonal_endpoint_rays":
        return _diagonal_endpoint_rays(grid, source_color=color1)

    elif beam_type == "diagonal_cross_from_singleton":
        return _diagonal_cross_from_singleton(grid, source_color=color1)

    elif beam_type == "diagonal_rays_from_marker_corners":
        return _diagonal_rays_from_marker_corners(
            grid,
            marker_color=color1,
            fill_color=color2,
        )

    elif beam_type == "diagonal_reflect_edge_barrier":
        return _diagonal_reflect_edge_barrier(
            grid,
            fill_color=color1,
            barrier_color=color2,
        )

    elif beam_type == "orthogonal_marker_extend_overlap":
        return _orthogonal_marker_extend_overlap(
            grid,
            vertical_color=color1,
        )

    elif beam_type == "frame_marker_projection":
        return _frame_marker_projection(grid)

    elif beam_type == "between_runs_horizontal":
        return _between_runs_horizontal(grid, color1=color1, color2=color2)

    elif beam_type == "horizontal_frame_fill":
        return _horizontal_frame_fill(grid, color1=color1, color2=color2)

    elif beam_type == "rectangle_shooting":
        rows, cols = len(grid), len(grid[0])
        positions = [
            (r, c) for r in range(rows) for c in range(cols) if grid[r][c] == color1
        ]
        min_row = min(r for r, _ in positions)
        max_row = max(r for r, _ in positions)
        min_col = min(c for _, c in positions)
        max_col = max(c for _, c in positions)
        new_grid = copy.deepcopy(grid)
        all_cells_to_set = set()
        directions = {
            "up": lambda: [
                (r, c)
                for c in range(min_col, max_col + 1)
                if all(grid[r_clear][c] == 0 for r_clear in range(min_row))
                for r in range(min_row)
            ],
            "down": lambda: [
                (r, c)
                for c in range(min_col, max_col + 1)
                if all(grid[r_clear][c] == 0 for r_clear in range(max_row + 1, rows))
                for r in range(max_row + 1, rows)
            ],
            "left": lambda: [
                (r, c)
                for r in range(min_row, max_row + 1)
                if all(grid[r][c_clear] == 0 for c_clear in range(min_col))
                for c in range(min_col)
            ],
            "right": lambda: [
                (r, c)
                for r in range(min_row, max_row + 1)
                if all(grid[r][c_clear] == 0 for c_clear in range(max_col + 1, cols))
                for c in range(max_col + 1, cols)
            ],
        }
        for cells in directions.values():
            all_cells_to_set.update(cells())
        for r, c in all_cells_to_set:
            new_grid[r][c] = color1
        return new_grid

    elif beam_type == "space_based":
        transformed_grid = [row.copy() for row in grid]
        rows, cols = len(grid), len(grid[0])
        separation_rows = [
            i
            for i in range(1, rows - 1)
            if all(cell == 0 for cell in grid[i])
            and any(grid[k][j] != 0 for k in range(0, i) for j in range(cols))
            and any(grid[k][j] != 0 for k in range(i + 1, rows) for j in range(cols))
        ]
        separation_cols = [
            j
            for j in range(1, cols - 1)
            if all(grid[i][j] == 0 for i in range(rows))
            and any(grid[i][k] != 0 for i in range(rows) for k in range(0, j))
            and any(grid[i][k] != 0 for i in range(rows) for k in range(j + 1, cols))
        ]
        if len(separation_rows) == 1 and not separation_cols:
            for j in range(cols):
                transformed_grid[separation_rows[0]][j] = color1
        elif len(separation_cols) == 1 and not separation_rows:
            for i in range(rows):
                transformed_grid[i][separation_cols[0]] = color1
        else:
            raise ValueError(
                "Multiple separation spaces found. Only one separation space is allowed."
            )
        return transformed_grid

    elif beam_type == "most_color_line":
        transformed_grid = [row.copy() for row in grid]
        rows, cols = len(grid), len(grid[0])
        mid_col = cols // 2
        line_of_color1_row = next(
            (i for i, row in enumerate(grid) if all(cell == color1 for cell in row)),
            None,
        )
        color_counts = Counter(
            cell
            for i in range(line_of_color1_row)
            for cell in grid[i]
            if cell not in {0, color1}
        )
        most_frequent_color = min(
            (
                color
                for color, count in color_counts.items()
                if count == max(color_counts.values())
            ),
            default=0,
        )
        transformed_grid[-1][mid_col] = most_frequent_color
        return transformed_grid

    elif beam_type == "color_inheritance":
        grid_np = np.array(grid)
        flat = grid_np.flatten()
        background_color = np.bincount(flat).argmax()
        unique, counts = np.unique(flat, return_counts=True)
        mask = unique != background_color
        beam_color = unique[mask][np.argmin(counts[mask])]
        beam_cells = np.argwhere(grid_np == beam_color)
        beam_center = (
            beam_cells.mean(axis=0)
            if beam_cells.size
            else np.array([len(grid) / 2, len(grid[0]) / 2])
        )
        object_colors = set(unique) - {background_color, beam_color}
        if object_colors:
            object_cells = np.argwhere(np.isin(grid_np, list(object_colors)))
            object_center = (
                object_cells.mean(axis=0)
                if object_cells.size
                else np.array([len(grid) / 2, len(grid[0]) / 2])
            )
        else:
            object_center = np.array([len(grid) / 2, len(grid[0]) / 2])
        delta = object_center - beam_center
        if abs(delta[0]) > abs(delta[1]):
            dr, dc = (1 if delta[0] > 0 else -1, 0)
        elif abs(delta[1]) > abs(delta[0]):
            dr, dc = (0, 1 if delta[1] > 0 else -1)
        else:
            dr, dc = (1 if delta[0] > 0 else -1, 1 if delta[1] > 0 else -1)
        transformed_grid = grid_np.copy()
        not_zero = np.argwhere(transformed_grid != 0)
        if dr == -1 and dc == 0:
            start_idx = not_zero[:, 0].argmin()
        elif dr == 1 and dc == 0:
            start_idx = not_zero[:, 0].argmax()
        elif dr == 0 and dc == 1:
            start_idx = not_zero[:, 1].argmax()
        elif dr == 0 and dc == -1:
            start_idx = not_zero[:, 1].argmin()
        else:
            start_idx = 0
        i0, j0 = not_zero[start_idx]
        i, j = i0 + dr, j0 + dc
        while 0 <= i < transformed_grid.shape[0] and 0 <= j < transformed_grid.shape[1]:
            transformed_grid[i, j] = beam_color
            i += dr
            j += dc
        return transformed_grid.tolist()

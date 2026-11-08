from copy import deepcopy
import numpy as np
from collections import deque

try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def magnet_grid_based(
    grid,
    magnet_type="dynamic",
    shifting_direction="dynamic",
    color1=0,
    color2=0,
    grid_size=0,
):
    if magnet_type == "project_stray_pixels_to_matching_full_lines":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("project_stray_pixels_to_matching_full_lines magnet requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_stray_pixels_to_matching_full_lines magnet requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        foreground_colors = sorted({
            value
            for row in grid
            for value in row
            if value != background_color
        })
        full_rows_by_color = {}
        full_cols_by_color = {}
        for candidate_color in foreground_colors:
            full_rows = [
                row
                for row in range(rows)
                if all(grid[row][col] == candidate_color for col in range(cols))
            ]
            full_cols = [
                col
                for col in range(cols)
                if all(grid[row][col] == candidate_color for row in range(rows))
            ]
            if full_rows:
                full_rows_by_color[candidate_color] = full_rows
            if full_cols:
                full_cols_by_color[candidate_color] = full_cols
        if not full_rows_by_color and not full_cols_by_color:
            raise ValueError("project_stray_pixels_to_matching_full_lines magnet requires full row or column lines")

        output = [
            [background_color for _ in range(cols)]
            for _ in range(rows)
        ]
        for line_color, full_rows in full_rows_by_color.items():
            for row in full_rows:
                for col in range(cols):
                    output[row][col] = line_color
        for line_color, full_cols in full_cols_by_color.items():
            for col in full_cols:
                for row in range(rows):
                    output[row][col] = line_color

        projected = False
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                if value in full_rows_by_color:
                    nearest_row = min(full_rows_by_color[value], key=lambda line_row: abs(line_row - row))
                    if row != nearest_row:
                        target_row = nearest_row + (1 if row > nearest_row else -1)
                        if 0 <= target_row < rows:
                            output[target_row][col] = value
                            projected = True
                if value in full_cols_by_color:
                    nearest_col = min(full_cols_by_color[value], key=lambda line_col: abs(line_col - col))
                    if col != nearest_col:
                        target_col = nearest_col + (1 if col > nearest_col else -1)
                        if 0 <= target_col < cols:
                            output[row][target_col] = value
                            projected = True
        if not projected:
            raise ValueError("project_stray_pixels_to_matching_full_lines magnet found no stray line-color pixels")
        return output

    if magnet_type == "object_center_to_edge_marker":
        direction = shifting_direction
        if direction not in {"down", "up", "left", "right"}:
            raise ValueError(
                "object_center_to_edge_marker magnet requires one of "
                "'down', 'up', 'left', or 'right'."
            )

        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if not rows or not cols:
            return grid

        marker_color = color2
        if marker_color == 0:
            raise ValueError("object_center_to_edge_marker requires a non-background color2 marker.")

        visited = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == 0 or (color1 not in (0, value)) or (row, col) in visited:
                    continue
                stack = [(row, col)]
                visited.add((row, col))
                component = []
                while stack:
                    current_row, current_col = stack.pop()
                    component.append((current_row, current_col))
                    for next_row, next_col in (
                        (current_row - 1, current_col),
                        (current_row + 1, current_col),
                        (current_row, current_col - 1),
                        (current_row, current_col + 1),
                    ):
                        if (
                            0 <= next_row < rows
                            and 0 <= next_col < cols
                            and (next_row, next_col) not in visited
                            and grid[next_row][next_col] == value
                        ):
                            visited.add((next_row, next_col))
                            stack.append((next_row, next_col))
                components.append(component)

        transformed_grid = deepcopy(grid)
        for component in components:
            component_rows = [row for row, _ in component]
            component_cols = [col for _, col in component]
            center_row = (min(component_rows) + max(component_rows)) // 2
            center_col = (min(component_cols) + max(component_cols)) // 2

            if direction == "down":
                target_row, target_col = rows - 1, center_col
            elif direction == "up":
                target_row, target_col = 0, center_col
            elif direction == "left":
                target_row, target_col = center_row, 0
            else:
                target_row, target_col = center_row, cols - 1

            if transformed_grid[target_row][target_col] in {0, marker_color}:
                transformed_grid[target_row][target_col] = marker_color

        return transformed_grid

    if magnet_type == "attract_to_object":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if not rows or not cols:
            return grid

        mover_color = color1
        target_color = color2

        def components_for_color(target):
            visited = set()
            components = []
            for r in range(rows):
                for c in range(cols):
                    if grid[r][c] != target or (r, c) in visited:
                        continue
                    stack = [(r, c)]
                    visited.add((r, c))
                    component = []
                    while stack:
                        cr, cc = stack.pop()
                        component.append((cr, cc))
                        for nr, nc in ((cr - 1, cc), (cr + 1, cc), (cr, cc - 1), (cr, cc + 1)):
                            if (
                                0 <= nr < rows
                                and 0 <= nc < cols
                                and (nr, nc) not in visited
                                and grid[nr][nc] == target
                            ):
                                visited.add((nr, nc))
                                stack.append((nr, nc))
                    components.append(component)
            return components

        target_components = components_for_color(target_color) if target_color else []
        if not target_components:
            candidate_colors = sorted(
                {
                    value
                    for row in grid
                    for value in row
                    if value not in {0, mover_color}
                }
            )
            for candidate_color in candidate_colors:
                candidate_components = components_for_color(candidate_color)
                if candidate_components:
                    target_components.extend(candidate_components)

        if not target_components:
            raise ValueError("attract_to_object magnet requires a target object.")

        target_component = max(target_components, key=len)
        target_rows = [r for r, _ in target_component]
        target_cols = [c for _, c in target_component]
        min_r, max_r = min(target_rows), max(target_rows)
        min_c, max_c = min(target_cols), max(target_cols)

        transformed_grid = [
            [0 if value == mover_color else value for value in row]
            for row in grid
        ]

        for r in range(rows):
            for c in range(cols):
                if grid[r][c] != mover_color:
                    continue

                if r < min_r:
                    target_r = min_r - 1
                elif r > max_r:
                    target_r = max_r + 1
                else:
                    target_r = r

                if c < min_c:
                    target_c = min_c - 1
                elif c > max_c:
                    target_c = max_c + 1
                else:
                    target_c = c

                if not (0 <= target_r < rows and 0 <= target_c < cols):
                    continue
                if transformed_grid[target_r][target_c] in {0, mover_color}:
                    transformed_grid[target_r][target_c] = mover_color

        return transformed_grid

    if magnet_type == "singleton_marker_to_component_boundary":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("singleton_marker_to_component_boundary magnet requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("singleton_marker_to_component_boundary magnet requires a rectangular grid")

        marker_color = color1
        target_color = color2
        if not isinstance(marker_color, int) or marker_color == 0:
            raise ValueError("singleton_marker_to_component_boundary requires a non-background marker color")

        visited = set()
        markers = []
        rectangles = []
        for start_row in range(rows):
            for start_col in range(cols):
                value = grid[start_row][start_col]
                if value == 0 or (start_row, start_col) in visited:
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
                        if (
                            0 <= next_row < rows
                            and 0 <= next_col < cols
                            and (next_row, next_col) not in visited
                            and grid[next_row][next_col] == value
                        ):
                            visited.add((next_row, next_col))
                            stack.append((next_row, next_col))

                if value == marker_color:
                    if len(pixels) == 1:
                        markers.append(pixels[0])
                    continue
                if target_color not in (0, value):
                    continue
                min_row = min(row for row, _ in pixels)
                max_row = max(row for row, _ in pixels)
                min_col = min(col for _, col in pixels)
                max_col = max(col for _, col in pixels)
                height = max_row - min_row + 1
                width = max_col - min_col + 1
                if height < 2 or width < 2 or len(pixels) != height * width:
                    continue
                rectangles.append({
                    "min_row": min_row,
                    "max_row": max_row,
                    "min_col": min_col,
                    "max_col": max_col,
                })

        if not markers:
            raise ValueError("singleton_marker_to_component_boundary magnet requires singleton markers")
        if not rectangles:
            raise ValueError("singleton_marker_to_component_boundary magnet requires rectangular target components")

        def clear_path(source, dest):
            source_row, source_col = source
            dest_row, dest_col = dest
            if source_row == dest_row:
                start = min(source_col, dest_col) + 1
                end = max(source_col, dest_col)
                return all(grid[source_row][col] == 0 for col in range(start, end))
            if source_col == dest_col:
                start = min(source_row, dest_row) + 1
                end = max(source_row, dest_row)
                return all(grid[row][source_col] == 0 for row in range(start, end))
            return False

        def candidate_for(marker):
            marker_row, marker_col = marker
            candidates = []
            for rect_index, rect in enumerate(rectangles):
                if rect["min_row"] <= marker_row <= rect["max_row"]:
                    if marker_col < rect["min_col"]:
                        candidates.append((
                            rect["min_col"] - marker_col,
                            (marker_row, rect["min_col"] - 1),
                            "left",
                            rect_index,
                        ))
                    elif marker_col > rect["max_col"]:
                        candidates.append((
                            marker_col - rect["max_col"],
                            (marker_row, rect["max_col"] + 1),
                            "right",
                            rect_index,
                        ))
                if rect["min_col"] <= marker_col <= rect["max_col"]:
                    if marker_row < rect["min_row"]:
                        candidates.append((
                            rect["min_row"] - marker_row,
                            (rect["min_row"] - 1, marker_col),
                            "up",
                            rect_index,
                        ))
                    elif marker_row > rect["max_row"]:
                        candidates.append((
                            marker_row - rect["max_row"],
                            (rect["max_row"] + 1, marker_col),
                            "down",
                            rect_index,
                        ))
            if not candidates:
                return None
            candidates.sort(key=lambda item: (item[0], item[1][0], item[1][1], item[2]))
            best_distance = candidates[0][0]
            best = [item for item in candidates if item[0] == best_distance]
            if len({item[1] for item in best}) != 1:
                raise ValueError("singleton_marker_to_component_boundary found ambiguous nearest boundary")
            distance, dest, side, rect_index = best[0]
            dest_row, dest_col = dest
            if not (0 <= dest_row < rows and 0 <= dest_col < cols):
                raise ValueError("singleton_marker_to_component_boundary projection leaves grid")
            if grid[dest_row][dest_col] != 0:
                raise ValueError("singleton_marker_to_component_boundary found destination collision")
            if not clear_path(marker, dest):
                raise ValueError("singleton_marker_to_component_boundary found blocked projection path")
            return {
                "source": marker,
                "dest": dest,
                "side": side,
                "rect_index": rect_index,
                "distance": distance,
            }

        candidate_records = []
        for marker in markers:
            candidate = candidate_for(marker)
            if candidate is not None:
                candidate_records.append(candidate)

        if not candidate_records:
            raise ValueError("singleton_marker_to_component_boundary magnet made no changes")

        output = [row[:] for row in grid]
        destinations = set()
        moved = False
        for candidate in candidate_records:
            source_row, source_col = candidate["source"]
            dest_row, dest_col = candidate["dest"]
            if (dest_row, dest_col) in destinations:
                raise ValueError("singleton_marker_to_component_boundary found duplicate destination")
            destinations.add((dest_row, dest_col))
            output[source_row][source_col] = 0
            output[dest_row][dest_col] = marker_color
            moved = True

        if not moved:
            raise ValueError("singleton_marker_to_component_boundary magnet made no changes")
        return output

    if magnet_type == "pixel_all":
        direction = shifting_direction
        if direction not in {"left", "right", "up", "down"}:
            raise ValueError(
                "pixel_all magnet requires one of 'left', 'right', 'up', or 'down'."
            )

        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        transformed_grid = [[0 for _ in range(cols)] for _ in range(rows)]

        if direction in {"up", "down"}:
            for col in range(cols):
                values = [grid[row][col] for row in range(rows) if grid[row][col] != 0]
                target_rows = (
                    range(len(values))
                    if direction == "up"
                    else range(rows - len(values), rows)
                )
                for row, value in zip(target_rows, values):
                    transformed_grid[row][col] = value
        else:
            for row in range(rows):
                values = [grid[row][col] for col in range(cols) if grid[row][col] != 0]
                target_cols = (
                    range(len(values))
                    if direction == "left"
                    else range(cols - len(values), cols)
                )
                for col, value in zip(target_cols, values):
                    transformed_grid[row][col] = value

        return transformed_grid

    if magnet_type == "object":
        direction = shifting_direction

        if direction not in {"dynamic", "right", "left", "up", "down"}:
            raise ValueError(
                "Invalid direction. Choose from 'right', 'left', 'up', 'down' or 'dynamic'."
            )

        rows = len(grid)
        cols = len(grid[0]) if grid else 0

        visited = [[False for _ in range(cols)] for _ in range(rows)]
        connectivity_directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        objects = []

        def dfs(r, c):
            stack = [(r, c)]
            object_cells = []
            while stack:
                x, y = stack.pop()
                if visited[x][y]:
                    continue
                visited[x][y] = True
                object_cells.append((x, y))
                for dx, dy in connectivity_directions:
                    nx, ny = x + dx, y + dy
                    if (
                        0 <= nx < rows
                        and 0 <= ny < cols
                        and not visited[nx][ny]
                        and grid[nx][ny] != 0
                    ):
                        stack.append((nx, ny))
            return object_cells

        for i in range(rows):
            for j in range(cols):
                if grid[i][j] != 0 and not visited[i][j]:
                    obj_cells = dfs(i, j)
                    objects.append(obj_cells)

        object_positions = []
        for idx, obj in enumerate(objects):
            if direction == "right":
                position = max(col for row, col in obj)
            elif direction == "left":
                position = min(col for row, col in obj)
            elif direction == "down":
                position = max(row for row, col in obj)
            elif direction == "up":
                position = min(row for row, col in obj)
            elif direction == "dynamic":
                continue  # dynamic direction will be handled later    
            object_positions.append((position, idx))

        reverse = direction in {"right", "down"}
        object_positions.sort(reverse=reverse)

        occupied = [[0 for _ in range(cols)] for _ in range(rows)]

        for _, obj_idx in object_positions:
            obj = objects[obj_idx]

            if direction == "right":
                max_shift = cols - 1 - max(col for row, col in obj)
                axis = "col"
                shift_increment = 1
            elif direction == "left":
                max_shift = min(col for row, col in obj)
                axis = "col"
                shift_increment = -1
            elif direction == "down":
                max_shift = rows - 1 - max(row for row, col in obj)
                axis = "row"
                shift_increment = 1
            elif direction == "up":
                max_shift = min(row for row, col in obj)
                axis = "row"
                shift_increment = -1

            for shift in range(max_shift, -1, -1):
                can_shift = True
                for row, col in obj:
                    if axis == "col":
                        new_row, new_col = row, col + shift * shift_increment
                    else:
                        new_row, new_col = row + shift * shift_increment, col

                    if (
                        not (0 <= new_row < rows and 0 <= new_col < cols)
                        or occupied[new_row][new_col]
                    ):
                        can_shift = False
                        break
                if can_shift:
                    for row, col in obj:
                        if axis == "col":
                            new_row, new_col = row, col + shift * shift_increment
                        else:
                            new_row, new_col = row + shift * shift_increment, col
                        occupied[new_row][new_col] = grid[row][col]
                    break
            else:
                for row, col in obj:
                    occupied[row][col] = grid[row][col]

        return occupied

    if magnet_type == "magnet_crop":
        from scipy.ndimage import label, find_objects

        grid_np = np.array(grid)

        structure = np.ones((grid_size, grid_size))
        labeled_grid = label(grid_np, structure=structure)[0]
        slices = find_objects(labeled_grid)

        objects = []
        centroids = []
        for i, slc in enumerate(slices):
            obj = grid_np[slc] * (labeled_grid[slc] == (i + 1))
            objects.append(obj)

            positions = np.argwhere(obj)
            y_coords, x_coords = positions[:, 0], positions[:, 1]
            centroid_x = x_coords.mean() + slc[1].start
            centroid_y = y_coords.mean() + slc[0].start
            centroids.append((centroid_x, centroid_y))

        centroids_x = [c[0] for c in centroids]
        centroids_y = [c[1] for c in centroids]
        range_x = max(centroids_x) - min(centroids_x)
        range_y = max(centroids_y) - min(centroids_y)

        if range_x > range_y:
            sorted_indices = np.argsort(centroids_x)
            concatenated = np.hstack([objects[i] for i in sorted_indices])
        else:
            sorted_indices = np.argsort(centroids_y)
            concatenated = np.vstack([objects[i] for i in sorted_indices])

        transformed_grid = concatenated.tolist()
        return transformed_grid

    if magnet_type == "pixel":
        direction = shifting_direction
        if direction not in {"left", "right", "up", "down", "dynamic"}:
            raise ValueError(
                "Invalid direction. Choose from 'left', 'right', 'up', 'down' or 'dynamic'."
            )

        new_grid = deepcopy(grid)

        rows = len(new_grid)
        cols = len(new_grid[0]) if rows > 0 else 0

        if direction in {"left", "right"}:
            for row in range(rows):
                if direction == "left":
                    for col in range(cols):
                        if new_grid[row][col] == color1:
                            target_col = col
                            while target_col > 0 and new_grid[row][target_col - 1] == 0:
                                target_col -= 1
                            if target_col != col:
                                new_grid[row][col] = 0
                                new_grid[row][target_col] = color1
                elif direction == "right":
                    for col in range(cols - 1, -1, -1):
                        if new_grid[row][col] == color1:
                            target_col = col
                            while (
                                target_col < cols - 1
                                and new_grid[row][target_col + 1] == 0
                            ):
                                target_col += 1
                            if target_col != col:
                                new_grid[row][col] = 0
                                new_grid[row][target_col] = color1

        elif direction in {"up", "down"}:
            for col in range(cols):
                if direction == "up":
                    for row in range(rows):
                        if new_grid[row][col] == color1:
                            target_row = row
                            while target_row > 0 and new_grid[target_row - 1][col] == 0:
                                target_row -= 1
                            if target_row != row:
                                new_grid[row][col] = 0
                                new_grid[target_row][col] = color1
                elif direction == "down":
                    for row in range(rows - 1, -1, -1):
                        if new_grid[row][col] == color1:
                            target_row = row
                            while (
                                target_row < rows - 1
                                and new_grid[target_row + 1][col] == 0
                            ):
                                target_row += 1
                            if target_row != row:
                                new_grid[row][col] = 0
                                new_grid[target_row][col] = color1

        return new_grid

    if magnet_type == "whole_sort":

        def rearrange_grid(grid, sorted_objects):
            new_grid = [[0 for _ in row] for row in grid]
            rows = len(grid)
            cols = len(grid[0]) if rows > 0 else 0
            next_available_col = [0] * rows
            for obj in sorted_objects:
                obj_height = obj["max_r"] - obj["min_r"] + 1
                obj_width = obj["max_c"] - obj["min_c"] + 1
                for r in range(rows - obj_height + 1):
                    max_col = max(next_available_col[r : r + obj_height])
                    if max_col + obj_width <= cols:
                        for orig_r, orig_c in obj["pixels"]:
                            new_r = r + (orig_r - obj["min_r"])
                            new_c = max_col + (orig_c - obj["min_c"])
                            new_grid[new_r][new_c] = 2
                        for dr in range(obj_height):
                            next_available_col[r + dr] = max_col + obj_width + 1
                        break
            return new_grid

        sorted_objects = detect_and_sort_objects(grid, color1)
        transformed_grid = rearrange_grid(grid, sorted_objects)
        return transformed_grid

    if magnet_type == "match_ver_line_union":
        try:
            col = next(
                j
                for j, col_vals in enumerate(zip(*grid))
                if all(val == color1 for val in col_vals)
            )
        except StopIteration:
            raise ValueError(f"No vertical line of {color1}'s found in the grid.")

        left_grid = [row[:col] for row in grid]
        right_grid = [row[col + 1 :] for row in grid]
        min_cols = min(len(left_grid[0]), len(right_grid[0]))

        return [
            [
                color2 if left_grid[i][j] != 0 or right_grid[i][j] != 0 else 0
                for j in range(min_cols)
            ]
            for i in range(len(grid))
        ]

    if magnet_type == "magnet_to_line":

        def detect_line(grid, color1):
            edges = {
                "up": grid[0],
                "down": grid[-1],
                "left": [row[0] for row in grid],
                "right": [row[-1] for row in grid],
            }
            for direction, edge in edges.items():
                if all(cell == color1 for cell in edge):
                    return direction

        def sort_objects(objects, direction, rows, cols):
            def compute_distance(obj):
                positions = obj["pixels"]
                min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
                if direction == "down":
                    return rows - 1 - max_row
                elif direction == "up":
                    return min_row
                elif direction == "right":
                    return cols - 1 - max_col
                elif direction == "left":
                    return min_col
                elif direction == "dynamic":
                    return (
                        max_row - min_row + max_col - min_col
                    ) / 2 # Average distance
                else:
                    raise ValueError(f"Invalid direction: '{direction}'.")

            sorted_objects = sorted(objects, key=compute_distance)
            return sorted_objects

        def move_objects(grid, sorted_objects, direction):
            rows, cols = len(grid), len(grid[0])
            transformed_grid = [row[:] for row in grid]

            for obj in sorted_objects:
                for x, y in obj["pixels"]:
                    transformed_grid[x][y] = 0

            moves = {"down": (1, 0), "up": (-1, 0), "right": (0, 1), "left": (0, -1)}
            dx, dy = moves[direction]

            for obj in sorted_objects:
                obj_pixels = obj["pixels"]
                obj_color = obj["color"]
                moved = True

                while moved:
                    next_pixels = set()
                    for x, y in obj_pixels:
                        new_x, new_y = x + dx, y + dy
                        if (
                            0 <= new_x < rows
                            and 0 <= new_y < cols
                            and transformed_grid[new_x][new_y] == 0
                        ):
                            next_pixels.add((new_x, new_y))
                        else:
                            moved = False
                            break
                    else:
                        obj_pixels = next_pixels
                        continue
                    break

                for x, y in obj_pixels:
                    transformed_grid[x][y] = obj_color

            return transformed_grid

        try:
            direction = detect_line(grid, color1)
        except ValueError as ve:
            print(str(ve))
            return grid

        rows = len(grid)
        cols = len(grid[0])
        objects = find_connected_components(
            grid, target_colors=None, background_color=0, connectivity=4
        )
        sorted_objects = sort_objects(objects, direction, rows, cols)
        transformed_grid = move_objects(grid, sorted_objects, direction)
        return transformed_grid

    if magnet_type == "punch":

        def detect_objects(grid):
            object_color = count_most_frequent_color_except_zero(grid)
            objects = find_connected_components(
                grid, target_colors={object_color}, background_color=0, connectivity=8
            )
            for obj in objects:
                positions = obj["pixels"]
                min_r, max_r, min_c, max_c = find_bounding_rectangle(positions)
                obj["min_r"] = min_r
                obj["max_r"] = max_r
                obj["min_c"] = min_c
                obj["max_c"] = max_c
            return objects

        def sort_objects(objects, zero_counts):
            combined = list(zip(objects, zero_counts))
            combined_sorted = sorted(combined, key=lambda x: x[1], reverse=True)
            sorted_objects = [item[0] for item in combined_sorted]
            return sorted_objects

        def count_zeros_in_second_column(grid, obj):
            min_r, max_r = obj["min_r"], obj["max_r"]
            second_col = obj["min_c"] + 1
            zero_count = 0
            for r in range(min_r, max_r + 1):
                if grid[r][second_col] == 0:
                    zero_count += 1
            return zero_count

        def rearrange_grid_with_spacing_refined(grid, sorted_objects, object_color):
            rows = len(grid)
            cols = len(grid[0]) if rows > 0 else 0
            new_grid = [[0 for _ in range(cols)] for _ in range(rows)]
            next_available_col = [0 for _ in range(rows)]

            for obj in sorted_objects:
                obj_height = obj["max_r"] - obj["min_r"] + 1
                obj_width = obj["max_c"] - obj["min_c"] + 1
                placed = False

                for r in range(rows - obj_height + 1):
                    max_next_col = max(
                        next_available_col[r + dr] for dr in range(obj_height)
                    )
                    if max_next_col + obj_width <= cols:
                        overlap = False
                        for dr in range(obj_height):
                            for dc in range(obj_width):
                                new_r = r + dr
                                new_c = max_next_col + dc
                                if new_grid[new_r][new_c] == object_color:
                                    overlap = True
                                    break
                            if overlap:
                                break
                        if not overlap:
                            for orig_r, orig_c in obj["pixels"]:
                                rel_r = orig_r - obj["min_r"]
                                rel_c = orig_c - obj["min_c"]
                                new_r = r + rel_r
                                new_c = max_next_col + rel_c
                                new_grid[new_r][new_c] = object_color
                            for dr in range(obj_height):
                                next_available_col[r + dr] = (
                                    max_next_col + obj_width + 1
                                )
                            placed = True
                            break
                if not placed:
                    raise Exception(
                        "Not enough space to place all objects with spacing."
                    )
            return new_grid

        object_color = count_most_frequent_color_except_zero(grid)
        objects = detect_objects(grid)
        zero_counts = [count_zeros_in_second_column(grid, obj) for obj in objects]
        sorted_objects = sort_objects(objects, zero_counts)
        transformed_grid = rearrange_grid_with_spacing_refined(
            grid, sorted_objects, object_color
        )
        return transformed_grid

    if magnet_type == "distract":
        mapping = {
            (0, 0): grid[grid_size - 2][grid_size - 2],
            (0, grid_size): grid[grid_size - 2][grid_size - 1],
            (grid_size, 0): grid[grid_size - 1][grid_size - 2],
            (grid_size, grid_size): grid[grid_size - 1][grid_size - 1],
        }
        return [[mapping.get((i, j), 0) for j in range(color1)] for i in range(color1)]

    if magnet_type == "match_hor_no_line":
        columns = len(grid[0]) // 2
        left_half = [row[:columns] for row in grid]
        right_half = [row[columns:] for row in grid]

        output_grid = [[0 for _ in range(columns)] for _ in range(columns)]

        for i in range(columns):
            for j in range(columns):
                if left_half[i][j] == 0 and right_half[i][j] == 0:
                    output_grid[i][j] = color1
                else:
                    output_grid[i][j] = 0

        return output_grid

    if magnet_type == "match_ver_no_line":
        rows = len(grid) // 2
        cols = len(grid[0]) if rows > 0 else 0
        upper_half = grid[:rows]
        lower_half = grid[rows:]

        num_rows = len(upper_half)
        num_cols = len(upper_half[0])
        output_grid = [[0 for _ in range(num_cols)] for _ in range(num_rows)]

        for i in range(num_rows):
            for j in range(num_cols):
                if upper_half[i][j] != 0 or lower_half[i][j] != 0:
                    output_grid[i][j] = color1
                else:
                    output_grid[i][j] = 0

        return output_grid

    if magnet_type == "match_ver_diff":
        try:
            # Find the column index where all cells have color1 (vertical line)
            line_col = next(
                idx
                for idx, col in enumerate(zip(*grid))
                if all(cell == color1 for cell in col)
            )
        except StopIteration:
            return grid  # If no such line is found, return the original grid

        # Extract the object on the left side of the line
        object_left = {
            (i, j) for i in range(len(grid)) for j in range(line_col) if grid[i][j] != 0
        }

        # Extract the object on the right side of the line
        object_right = {
            (i, j - (line_col + 1))
            for i in range(len(grid))
            for j in range(line_col + 1, len(grid[0]))
            if grid[i][j] != 0
        }

        # Combine positions from both objects
        all_positions = object_left | object_right

        if not all_positions:
            return grid  # If no objects are found, return the original grid

        # Determine the size of the desired grid based on the objects' positions
        num_rows = max(i for i, _ in all_positions) + 1
        num_cols = max(j for _, j in all_positions) + 1

        # Create a new grid filled with color2
        desired_grid = [[color2 for _ in range(num_cols)] for _ in range(num_rows)]

        # Set positions where objects are present to 0
        for x, y in all_positions:
            if 0 <= x < num_rows and 0 <= y < num_cols:
                desired_grid[x][y] = 0

        return desired_grid

    if magnet_type == "match_hor_line_union":
        try:
            # Find the row index where all cells have color1 (horizontal line)
            row_idx = next(
                i for i, row in enumerate(grid) if all(cell == color1 for cell in row)
            )
        except StopIteration:
            raise ValueError(f"No horizontal line of {color1}'s found in the grid.")

        # Split the grid into top and bottom parts, excluding the line
        top_grid = grid[:row_idx]
        bottom_grid = grid[row_idx + 1 :]

        # Determine the minimum number of rows to iterate over
        min_rows = min(len(top_grid), len(bottom_grid))
        cols = len(grid[0]) if grid else 0

        # Merge the top and bottom grids by taking the union of their non-zero cells
        transformed_grid = [
            [
                color2 if top_grid[i][j] != 0 or bottom_grid[i][j] != 0 else 0
                for j in range(cols)
            ]
            for i in range(min_rows)
        ]

        return transformed_grid

    if magnet_type == "match_hor_diff":
        try:
            line_row = next(
                idx
                for idx, row in enumerate(grid)
                if all(cell == color1 for cell in row)
            )
        except StopIteration:
            return grid
        object_above = {
            (i, j)
            for i in range(line_row)
            for j, cell in enumerate(grid[i])
            if cell != 0
        }
        num_rows = max(x for x, _ in object_above) + 1
        num_cols = max(y for _, y in object_above) + 1
        object_below = {
            (i - line_row - 1, j)
            for i in range(line_row + 1, line_row + 1 + num_rows)
            for j, cell in enumerate(grid[i])
            if cell != 0
        }
        desired_grid = [[color2] * num_cols for _ in range(num_rows)]
        for x, y in object_above | object_below:
            if 0 <= x < num_rows and 0 <= y < num_cols:
                desired_grid[x][y] = 0
        return desired_grid

    if magnet_type in ["match_blank", "match_ver_union", "match_hor_union"]:

        def find_line(grid, color, orientation="vertical"):
            if orientation == "vertical":
                for c, col in enumerate(zip(*grid)):
                    if all(cell == color for cell in col):
                        return c
            else:
                for r, row in enumerate(grid):
                    if all(cell == color for cell in row):
                        return r
            return -1

        def extract_objects(grid, index, orientation="vertical"):
            if orientation == "vertical":
                return [row[:index] for row in grid], [row[index + 1 :] for row in grid]
            else:
                return grid[:index], grid[index + 1 :]

        def can_merge(left, right):
            return all(
                left[r][c] == 0 or left[r][c] == right[r][c]
                for r in range(len(left))
                for c in range(len(left[0]))
                if right[r][c] != 0
            )

        def merge_objects(left, right):
            merged = deepcopy(left)
            for r in range(len(right)):
                for c in range(len(right[0])):
                    if right[r][c] != 0:
                        merged[r][c] = right[r][c]
            return merged

        def create_final_grid(left, right, fill_color, size=3):
            try:
                return [
                    [fill_color if left[r][c] or right[r][c] else 0 for c in range(size)]
                    for r in range(size)
                ]
            except IndexError:
                raise ValueError(
                    "grid size is smaller than the required size "+ str(size)
                )    

        if magnet_type != "match_hor_union":
            line_col = find_line(grid, color1, "vertical")
            if line_col == -1:
                raise ValueError(f"No vertical line of {color1}'s found in the grid.")
            left_grid, right_grid = extract_objects(grid, line_col, "vertical")
            if magnet_type == "match_blank":
                return (
                    merge_objects(left_grid, right_grid)
                    if can_merge(left_grid, right_grid)
                    else left_grid
                )
            elif magnet_type == "match_ver_union":
                return create_final_grid(left_grid, right_grid, color2, size=3)
        else:
            line_row = find_line(grid, color1, "horizontal")
            if line_row == -1:
                raise ValueError(f"No horizontal line of {color1}'s found in the grid.")
            top_grid, bottom_grid = extract_objects(grid, line_row, "horizontal")
            desired_rows = grid_size
            cols = len(grid[0])

            def adjust_grid(obj, desired, cols):
                return (obj + [[0] * cols for _ in range(desired - len(obj))])[:desired]

            top_grid = adjust_grid(top_grid, desired_rows, cols)
            bottom_grid = adjust_grid(bottom_grid, desired_rows, cols)
            final_grid = [
                [
                    color2 if top_grid[r][c] or bottom_grid[r][c] else 0
                    for c in range(cols)
                ]
                for r in range(desired_rows)
            ]
            return final_grid
    if magnet_type == "magnet_line":
        height, width = len(grid), len(grid[0]) if grid else 0
        color_positions = {}
        for y, row in enumerate(grid):
            for x, color in enumerate(row):
                if color:
                    color_positions.setdefault(color, set()).add((x, y))
        line_color = (
            color1 * 2
            if color1 * 2 in color_positions
            else next(
                (
                    c
                    for c, pos in color_positions.items()
                    if len({x for x, _ in pos}) == 1 or len({y for _, y in pos}) == 1
                ),
                None,
            )
        )
        if not line_color:
            return grid
        line_pos = color_positions[line_color]
        xs, ys = {x for x, _ in line_pos}, {y for _, y in line_pos}
        if len(ys) == 1:
            orientation, coord = "horizontal", next(iter(ys))
        elif len(xs) == 1:
            orientation, coord = "vertical", next(iter(xs))
        else:
            return grid
        new_grid = [[0] * width for _ in range(height)]
        for x, y in line_pos:
            new_grid[y][x] = line_color
        for c, pos in color_positions.items():
            if c == line_color:
                continue
            for x, y in pos:
                if orientation == "horizontal" and x in xs:
                    new_y = coord - 1 if y < coord else coord + 1
                    if 0 <= new_y < height and not new_grid[new_y][x]:
                        new_grid[new_y][x] = c
                elif orientation == "vertical" and y in ys:
                    new_x = coord - 1 if x < coord else coord + 1
                    if 0 <= new_x < width and not new_grid[y][new_x]:
                        new_grid[y][new_x] = c
        return new_grid

    if magnet_type == "corner_magnet":
        rows, cols = len(grid), len(grid[0]) if grid else 0
        group_size = -(-rows // grid_size)
        groups = [[] for _ in range(grid_size)]
        for r, row in enumerate(grid):
            for c, val in enumerate(row):
                if val:
                    idx = min(r // group_size, grid_size - 1)
                    groups[idx].append((c, val))
        output_grid = [
            [val for _, val in sorted(group, key=lambda x: x[0])]
            + [0] * (grid_size - len(group))
            for group in groups
        ]
        output_grid = (output_grid + [[0] * grid_size] * grid_size)[:grid_size]
        return output_grid

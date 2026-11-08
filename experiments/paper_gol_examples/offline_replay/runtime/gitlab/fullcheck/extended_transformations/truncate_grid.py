from collections import Counter, deque
from copy import deepcopy

try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def truncate_grid_based(grid, color1, color2, grid_size, truncate_type, mirror):
    if truncate_type == "remove_8connected_singletons":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("remove_8connected_singletons requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("remove_8connected_singletons requires a rectangular grid")
        background_color = 0 if color2 is None else color2
        target_color = None if color1 in (None, 0) else color1
        output = deepcopy(grid)
        visited = set()
        removed = False
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                if target_color is not None and value != target_color:
                    continue
                if (row, col) in visited:
                    continue
                queue = deque([(row, col)])
                visited.add((row, col))
                pixels = []
                while queue:
                    current_row, current_col = queue.popleft()
                    pixels.append((current_row, current_col))
                    for delta_row in (-1, 0, 1):
                        for delta_col in (-1, 0, 1):
                            if delta_row == 0 and delta_col == 0:
                                continue
                            next_row = current_row + delta_row
                            next_col = current_col + delta_col
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if (next_row, next_col) in visited:
                                continue
                            if grid[next_row][next_col] != value:
                                continue
                            visited.add((next_row, next_col))
                            queue.append((next_row, next_col))
                if len(pixels) == 1:
                    only_row, only_col = pixels[0]
                    output[only_row][only_col] = background_color
                    removed = True
        if not removed:
            raise ValueError("remove_8connected_singletons removed nothing")
        return output

    if truncate_type == "keep_component_rectangular_cores":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("keep_component_rectangular_cores requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("keep_component_rectangular_cores requires a rectangular grid")
        background_color = 0 if color2 is None else color2
        target_color = None if color1 in (None, 0) else color1
        output = deepcopy(grid)
        visited = set()
        changed = False
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                if target_color is not None and value != target_color:
                    continue
                if (row, col) in visited:
                    continue
                queue = deque([(row, col)])
                visited.add((row, col))
                pixels = []
                while queue:
                    current_row, current_col = queue.popleft()
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
                        if grid[next_row][next_col] != value:
                            continue
                        visited.add((next_row, next_col))
                        queue.append((next_row, next_col))
                component = set(pixels)
                best = None
                min_row = min(pixel_row for pixel_row, _ in pixels)
                max_row = max(pixel_row for pixel_row, _ in pixels)
                min_col = min(pixel_col for _, pixel_col in pixels)
                max_col = max(pixel_col for _, pixel_col in pixels)
                for top in range(min_row, max_row + 1):
                    for bottom in range(top, max_row + 1):
                        for left in range(min_col, max_col + 1):
                            for right in range(left, max_col + 1):
                                area = (bottom - top + 1) * (right - left + 1)
                                if best is not None and area < best[0]:
                                    continue
                                if all(
                                    (rect_row, rect_col) in component
                                    for rect_row in range(top, bottom + 1)
                                    for rect_col in range(left, right + 1)
                                ):
                                    candidate = (area, -top, -left, -bottom, -right, top, left, bottom, right)
                                    if best is None or candidate > best:
                                        best = candidate
                keep = set()
                if best is not None and best[0] > 1:
                    _, _, _, _, _, top, left, bottom, right = best
                    keep = {
                        (rect_row, rect_col)
                        for rect_row in range(top, bottom + 1)
                        for rect_col in range(left, right + 1)
                    }
                for pixel_row, pixel_col in component - keep:
                    output[pixel_row][pixel_col] = background_color
                    changed = True
        if not changed:
            raise ValueError("keep_component_rectangular_cores removed nothing")
        return output

    if truncate_type in {"keep_largest_component_rectangle", "keep_largest_component"}:
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("keep_largest_component_rectangle requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("keep_largest_component_rectangle requires a rectangular grid")
        background_color = 0 if color2 is None else color2
        target_color = None if color1 in (None, 0) else color1

        visited = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                if target_color is not None and value != target_color:
                    continue
                if (row, col) in visited:
                    continue
                queue = deque([(row, col)])
                visited.add((row, col))
                pixels = []
                while queue:
                    current_row, current_col = queue.popleft()
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
                        if grid[next_row][next_col] != value:
                            continue
                        visited.add((next_row, next_col))
                        queue.append((next_row, next_col))
                components.append((len(pixels), min(pixels), value, pixels))

        if not components:
            raise ValueError("keep_largest_component_rectangle found no foreground components")
        max_size = max(size for size, _, _, _ in components)
        largest = [component for component in components if component[0] == max_size]
        if len(largest) != 1:
            raise ValueError("keep_largest_component_rectangle requires a unique largest component")
        _, _, _, component_pixels = largest[0]
        component = set(component_pixels)

        # The retained object in this family is the largest filled rectangular
        # core of the dominant component; attached same-color spurs are noise.
        occupancy = [[0] * (cols + 1) for _ in range(rows + 1)]
        for row in range(rows):
            running = 0
            for col in range(cols):
                running += 1 if (row, col) in component else 0
                occupancy[row + 1][col + 1] = occupancy[row][col + 1] + running

        def rect_sum(top, left, bottom, right):
            return (
                occupancy[bottom + 1][right + 1]
                - occupancy[top][right + 1]
                - occupancy[bottom + 1][left]
                + occupancy[top][left]
            )

        best = None
        for top in range(rows):
            for bottom in range(top, rows):
                height = bottom - top + 1
                for left in range(cols):
                    for right in range(left, cols):
                        area = height * (right - left + 1)
                        if best is not None and area < best[0]:
                            continue
                        if rect_sum(top, left, bottom, right) != area:
                            continue
                        candidate = (area, -top, -left, -bottom, -right, top, left, bottom, right)
                        if best is None or candidate > best:
                            best = candidate

        if best is None:
            raise ValueError("keep_largest_component_rectangle found no rectangular core")
        _, _, _, _, _, top, left, bottom, right = best
        keep = {
            (row, col)
            for row in range(top, bottom + 1)
            for col in range(left, right + 1)
        }
        return [
            [
                cell if (row, col) in keep else background_color
                for col, cell in enumerate(values)
            ]
            for row, values in enumerate(grid)
        ]

    if truncate_type == "keep_center_column":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("keep_center_column requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("keep_center_column requires a rectangular grid")
        if cols % 2 == 0:
            raise ValueError("keep_center_column requires odd width")
        background_color = 0 if color2 is None else color2
        center_col = cols // 2
        return [
            [
                cell if col == center_col else background_color
                for col, cell in enumerate(row)
            ]
            for row in grid
        ]

    if truncate_type == "noise_repair_by_local_support":
        noise_color = color1
        if noise_color in {"least", "least_non_background", "minority"}:
            counts = Counter(
                value
                for row in grid
                for value in row
                if value != 0
            )
            if not counts:
                return grid
            noise_color = min(counts, key=lambda value: (counts[value], value))
        if noise_color == 0:
            raise ValueError("noise_repair_by_local_support requires a non-background color1")

        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        transformed_grid = deepcopy(grid)
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != noise_color:
                    continue

                neighbor_counts = {}
                for next_row, next_col in (
                    (row - 1, col),
                    (row + 1, col),
                    (row, col - 1),
                    (row, col + 1),
                ):
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    value = grid[next_row][next_col]
                    if value in (0, noise_color):
                        continue
                    neighbor_counts[value] = neighbor_counts.get(value, 0) + 1

                supported = [
                    (count, -value, value)
                    for value, count in neighbor_counts.items()
                    if count >= 2
                ]
                if supported:
                    transformed_grid[row][col] = max(supported)[2]
                else:
                    transformed_grid[row][col] = 0
        return transformed_grid

    if truncate_type == "position_based":
        target_color = grid[color1][color2]
        return [
            [
                0 if (i, j) != (color1, color2) and cell == target_color else cell
                for j, cell in enumerate(row)
            ]
            for i, row in enumerate(grid)
        ]
    if truncate_type == "inferior_based":
        transformed_grid = deepcopy(grid)
        rectangles = find_connected_components_multicolor(grid, color1, color2)
        if mirror:
            condition = lambda rect: rect["count_1"] >= grid_size
        else:
            min_count_1 = min(rect["count_1"] for rect in rectangles)
            condition = lambda rect: rect["count_1"] == min_count_1
        pixels_to_recolor = [
            (r, c)
            for rect in rectangles
            if condition(rect)
            for (r, c) in rect["pixels"]
        ]
        for r, c in pixels_to_recolor:
            transformed_grid[r][c] = 0
        return transformed_grid

from collections import deque, defaultdict, Counter
import copy
import numpy as np


def find_objects(grid):
    height, width = len(grid), len(grid[0])
    visited = [[False] * width for _ in range(height)]
    objects = []

    def dfs(i, j, current_object):
        if 0 <= i < height and 0 <= j < width and not visited[i][j] and grid[i][j] != 0:
            visited[i][j] = True
            current_object.append((i, j, grid[i][j]))
            for di in [-1, 0, 1]:
                for dj in [-1, 0, 1]:
                    if di != 0 or dj != 0:
                        dfs(i + di, j + dj, current_object)

    for i in range(height):
        for j in range(width):
            if grid[i][j] != 0 and not visited[i][j]:
                current_object = []
                dfs(i, j, current_object)
                objects.append(current_object)
    return objects


def count_most_frequent_color_except_zero(grid):
    color_count = Counter()
    for row in grid:
        for color in row:
            if color != 0:
                color_count[color] += 1
    if not color_count:
        return None
    most_common_color = color_count.most_common(1)[0][0]
    return most_common_color


def swap_with_zero(grid, color=None):
    if color is None:
        color = count_most_frequent_color_except_zero(grid)
    return [
        [0 if cell == color else (color if cell == 0 else cell) for cell in row]
        for row in grid
    ]


def count_unique_colors_except_zero(grid):
    unique_colors = set()
    for row in grid:
        for color in row:
            if color != 0:
                unique_colors.add(color)
    return len(unique_colors)


def find_connected_components_multicolor(grid, color1, color2):
    rows, cols = len(grid), len(grid[0]) if grid else 0
    visited = [[False for _ in range(cols)] for _ in range(rows)]
    rectangles = []
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] in [color2, color1] and not visited[r][c]:
                queue = deque()
                queue.append((r, c))
                visited[r][c] = True
                pixels = []
                count_1 = 0

                while queue:
                    cr, cc = queue.popleft()
                    pixels.append((cr, cc))
                    if grid[cr][cc] == color1:
                        count_1 += 1

                    for dr, dc in directions:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if grid[nr][nc] in [color2, color1] and not visited[nr][nc]:
                                visited[nr][nc] = True
                                queue.append((nr, nc))

                rectangles.append({"pixels": pixels, "count_1": count_1})

    return rectangles


def find_nearest_color(grid, obj):
    rows, cols = len(grid), len(grid[0])
    visited = [[False] * cols for _ in range(rows)]
    queue = deque()
    for r, c in obj["pixels"]:
        queue.append((r, c, 0))
        visited[r][c] = True
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    while queue:
        current_distance = queue[0][2]
        colors_found = set()
        while queue and queue[0][2] == current_distance:
            cr, cc, dist = queue.popleft()
            for dr, dc in directions:
                nr, nc = cr + dr, cc + dc
                if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc]:
                    if grid[nr][nc] != obj["color"] and grid[nr][nc] != 0:
                        colors_found.add(grid[nr][nc])
                    visited[nr][nc] = True
                    queue.append((nr, nc, dist + 1))
        if colors_found:
            return max(colors_found)
    return obj["color"]


def rotate_grid(grid, degrees):
    if degrees == 90:
        return [list(row) for row in zip(*grid[::-1])]
    elif degrees == 180:
        return [row[::-1] for row in grid[::-1]]
    elif degrees == 270:
        return [list(row) for row in zip(*grid)][::-1]
    elif degrees == 0:
        return grid
    else:
        raise ValueError(
            f"Invalid rotation angle: {degrees}. Use 0, 90, 180, or 270 degrees."
        )


def is_component_inside(color, bounds):
    min_row, max_row, min_col, max_col = bounds
    for r, c in color:
        if not (min_row < r < max_row and min_col < c < max_col):
            return False
    return True


def collect_positions_by_color(grid, colors):
    positions_by_color = {}
    for color in colors:
        positions = [
            (i, j)
            for i, row in enumerate(grid)
            for j, val in enumerate(row)
            if val == color
        ]
        positions_by_color[color] = positions
    return positions_by_color


def find_bounding_rectangle(positions):
    min_row = min(r for r, _ in positions)
    max_row = max(r for r, _ in positions)
    min_col = min(c for _, c in positions)
    max_col = max(c for _, c in positions)
    return min_row, max_row, min_col, max_col


def get_unique_colors_except_background(grid, background_color):
    unique_colors = set()
    for row in grid:
        for color in row:
            if color != background_color:
                unique_colors.add(color)
    return unique_colors


def get_neighbors(pos, grid_size, connectivity=4):
    rows, cols = grid_size
    i, j = pos
    neighbors = []
    directions = [(-1, 0), (0, -1), (0, 1), (1, 0)]
    if connectivity == 8:
        directions += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for di, dj in directions:
        ni, nj = i + di, j + dj
        if 0 <= ni < rows and 0 <= nj < cols:
            neighbors.append((ni, nj))
    return neighbors


def detect_and_sort_objects(grid, color1):
    components = find_connected_all_directions_by_color(grid, color1)
    objects = []
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for component in components:
        obj_pixels = list(component)
        min_r = min(r for r, c in obj_pixels)
        max_r = max(r for r, c in obj_pixels)
        min_c = min(c for r, c in obj_pixels)
        max_c = max(c for r, c in obj_pixels)
        subgrid = [row[min_c : max_c + 1] for row in grid[min_r : max_r + 1]]
        hole_count = detect_holes(subgrid, directions)
        objects.append(
            {
                "pixels": obj_pixels,
                "min_r": min_r,
                "max_r": max_r,
                "min_c": min_c,
                "max_c": max_c,
                "holes": hole_count,
            }
        )
    sorted_objects = sorted(objects, key=lambda obj: obj["holes"])
    return sorted_objects


def detect_holes(subgrid, directions):
    rows = len(subgrid)
    cols = len(subgrid[0]) if rows > 0 else 0
    visited = [[False for _ in range(cols)] for _ in range(rows)]
    holes = 0
    queue = deque()

    for i in range(rows):
        for j in range(cols):
            if subgrid[i][j] == 0 and not visited[i][j]:
                holes += 1
                queue.append((i, j))
                visited[i][j] = True
                while queue:
                    cx, cy = queue.popleft()
                    for dx, dy in directions:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < rows and 0 <= ny < cols:
                            if subgrid[nx][ny] == 0 and not visited[nx][ny]:
                                visited[nx][ny] = True
                                queue.append((nx, ny))

    return holes


def mirror_component(component, axis, center_row, center_col):
    mirrored = set()
    for r, c in component:
        if axis == "y":
            mirrored_r = r
            mirrored_c = int(round(2 * center_col - c))
        elif axis == "x":
            mirrored_r = int(round(2 * center_row - r))
            mirrored_c = c
        else:
            raise ValueError("Axis must be 'x' or 'y'.")
        mirrored.add((mirrored_r, mirrored_c))
    return mirrored


def is_valid_duplication(grid, mirrored_component, color_bounds, color1, color2):
    min_row, max_row, min_col, max_col = color_bounds
    for r, c in mirrored_component:
        if not (min_row < r < max_row and min_col < c < max_col):
            return False
        if grid[r][c] == color2:
            return False
        if grid[r][c] == color1:
            return False
    return True


def find_connected_components(
    grid, target_colors=None, background_color=0, connectivity=4
):
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0
    visited = [[False for _ in range(cols)] for _ in range(rows)]
    objects = []

    if target_colors is None:
        all_colors = set(cell for row in grid for cell in row)
        target_colors = all_colors - {background_color}

    for r in range(rows):
        for c in range(cols):
            color = grid[r][c]
            if color in target_colors and not visited[r][c]:
                queue = deque()
                queue.append((r, c))
                visited[r][c] = True
                pixels = []

                while queue:
                    x, y = queue.popleft()
                    pixels.append((x, y))
                    neighbors = get_neighbors((x, y), (rows, cols), connectivity)
                    for nx, ny in neighbors:
                        if not visited[nx][ny] and grid[nx][ny] == color:
                            visited[nx][ny] = True
                            queue.append((nx, ny))

                objects.append({"color": color, "pixels": pixels})

    return objects


def deep_first_search_object_based(i, j, obj, height, width, visited, grid):
    if 0 <= i < height and 0 <= j < width and not visited[i][j] and grid[i][j] != 0:
        visited[i][j] = True
        obj.append(grid[i][j])
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di or dj:
                    deep_first_search_object_based(
                        i + di, j + dj, obj, height, width, visited, grid
                    )


def resize_grid(grid, size):
    current_h, current_w = len(grid), len(grid[0])
    while current_h > size:
        for idx in [0, -1]:
            if all(cell == 0 for cell in grid[idx]):
                grid.pop(idx)
                current_h -= 1
                break
        else:
            break
    while current_w > size:
        for idx in [0, -1]:
            if all(row[idx] == 0 for row in grid):
                for row in grid:
                    row.pop(idx)
                current_w -= 1
                break
        else:
            break
    while current_h < size:
        grid.insert(0, [0] * current_w)
        current_h += 1
    while current_w < size:
        for row in grid:
            row.insert(0, 0)
        current_w += 1
    while current_h > size:
        grid.pop(current_h // 2)
        current_h -= 1
    while current_w > size:
        for row in grid:
            row.pop(current_w // 2)
        current_w -= 1
    return grid


def find_all_rectangles(grid):
    rows, cols = len(grid), len(grid[0])
    visited = [[False] * cols for _ in range(rows)]
    rectangles = []

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1 and not visited[r][c]:
                queue = deque()
                queue.append((r, c))
                visited[r][c] = True
                min_r, max_r = r, r
                min_c, max_c = c, c

                while queue:
                    curr_r, curr_c = queue.popleft()
                    min_r = min(min_r, curr_r)
                    max_r = max(max_r, curr_r)
                    min_c = min(min_c, curr_c)
                    max_c = max(max_c, curr_c)
                    for dr, dc in [
                        (-1, 0),
                        (1, 0),
                        (0, -1),
                        (0, 1),
                        (-1, -1),
                        (-1, 1),
                        (1, -1),
                        (1, 1),
                    ]:
                        nr, nc = curr_r + dr, curr_c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if grid[nr][nc] == 1 and not visited[nr][nc]:
                                visited[nr][nc] = True
                                queue.append((nr, nc))
                rectangles.append((min_r, min_c, max_r, max_c))
    return rectangles


def count_colored_pixels_inside(grid, rectangle):
    min_r, min_c, max_r, max_c = rectangle
    count = 0
    for r in range(min_r, max_r + 1):
        for c in range(min_c, max_c + 1):
            if grid[r][c] != 1:
                count += 1
    return count


def select_smallest_rectangle(grid, rectangles):
    min_count = float("inf")
    selected_rectangle = None
    for rect in rectangles:
        count = count_colored_pixels_inside(grid, rect)
        if count < min_count:
            min_count = count
            selected_rectangle = rect
        elif count == min_count:
            area_current = (rect[2] - rect[0] + 1) * (rect[3] - rect[1] + 1)
            area_selected = (selected_rectangle[2] - selected_rectangle[0] + 1) * (
                selected_rectangle[3] - selected_rectangle[1] + 1
            )
            if area_current < area_selected:
                selected_rectangle = rect
    return selected_rectangle


def select_biggest_rectangle(grid, rectangles):
    max_count = float("-inf")
    selected_rectangle = None
    for rect in rectangles:
        count = count_colored_pixels_inside(grid, rect)
        if count > max_count:
            max_count = count
            selected_rectangle = rect
        elif count == max_count:
            area_current = (rect[2] - rect[0] + 1) * (rect[3] - rect[1] + 1)
            area_selected = (selected_rectangle[2] - selected_rectangle[0] + 1) * (
                selected_rectangle[3] - selected_rectangle[1] + 1
            )
            if area_current > area_selected:
                selected_rectangle = rect
    return selected_rectangle


def extract_rectangle(grid, rectangle):
    min_r, min_c, max_r, max_c = rectangle
    extracted = []
    for r in range(min_r, max_r + 1):
        extracted.append(grid[r][min_c : max_c + 1])
    return extracted


def find_connected_all_directions_by_color(grid, color):
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0
    visited = [[False for _ in range(cols)] for _ in range(rows)]
    components = []

    directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == color and not visited[r][c]:
                queue = deque()
                queue.append((r, c))
                visited[r][c] = True
                component = set()
                component.add((r, c))

                while queue:
                    current_r, current_c = queue.popleft()
                    for dr, dc in directions:
                        nr, nc = current_r + dr, current_c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if grid[nr][nc] == color and not visited[nr][nc]:
                                visited[nr][nc] = True
                                queue.append((nr, nc))
                                component.add((nr, nc))
                components.append(component)
    return components


def find_zero_rectangles(grid_np, background_color):
    rows, cols = grid_np.shape
    visited = np.zeros_like(grid_np, dtype=bool)
    rectangles = []
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

    for i in range(rows):
        for j in range(cols):
            if grid_np[i][j] != background_color and not visited[i][j]:
                queue = deque()
                queue.append((i, j))
                visited[i][j] = True
                min_row, max_row = i, i
                min_col, max_col = j, j

                while queue:
                    x, y = queue.popleft()
                    min_row = min(min_row, x)
                    max_row = max(max_row, x)
                    min_col = min(min_col, y)
                    max_col = max(max_col, y)

                    for dx, dy in directions:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < rows and 0 <= ny < cols:
                            if (
                                not visited[nx][ny]
                                and grid_np[nx][ny] != background_color
                            ):
                                visited[nx][ny] = True
                                queue.append((nx, ny))

                rectangles.append(
                    {
                        "min_row": min_row,
                        "max_row": max_row,
                        "min_col": min_col,
                        "max_col": max_col,
                    }
                )

    return rectangles

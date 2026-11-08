from colorama import Fore, Style
from collections import deque

try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def connect_grid_based(
    grid,
    connect_mode: str,
    color: int,
    fill_color: int,
    border_color: int,
    inherit_vertical: bool,
):
    def fill(grid, value, indices):
        grid_filled = [list(row) for row in grid]
        for i, j in indices:
            if 0 <= i < len(grid_filled) and 0 <= j < len(grid_filled[0]):
                grid_filled[i][j] = value
        return tuple(tuple(row) for row in grid_filled)

    if connect_mode == "connect_rectangles":
        bg_color = max(
            Counter(cell for row in grid for cell in row).items(),
            key=lambda x: x[1],
            default=(0, 0),
        )[0]
        color_to_positions = collect_positions_by_color(
            grid, get_unique_colors_except_background(grid, bg_color)
        )

        for color, positions in color_to_positions.items():
            if positions:
                min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
                transformed_objects = {
                    (color, (i, j))
                    for i in range(min_row, max_row + 1)
                    for j in range(min_col, max_col + 1)
                    if (i, j) not in positions
                }
                for _, (i, j) in transformed_objects:
                    if 0 <= i < len(grid) and 0 <= j < len(grid[0]):
                        grid[i][j] = color
        return tuple(tuple(row) for row in grid)

    elif connect_mode == "connect_fill":
        rows, cols = len(grid), len(grid[0])
        twos = [
            (r, c) for r in range(rows) for c in range(cols) if grid[r][c] == fill_color
        ]
        for r, c in twos:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r, c
                while 0 <= nr < rows and 0 <= nc < cols:
                    grid[nr][nc] = fill_color
                    nr, nc = nr + dr, nc + dc
        visited = [[False] * cols for _ in range(rows)]
        queue = deque(
            [(r, c) for r in range(rows) for c in [0, cols - 1] if grid[r][c] == 0]
            + [(r, c) for c in range(cols) for r in [0, rows - 1] if grid[r][c] == 0]
        )
        for r, c in queue:
            visited[r][c] = True
        while queue:
            r, c = queue.popleft()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (
                    0 <= nr < rows
                    and 0 <= nc < cols
                    and not visited[nr][nc]
                    and grid[nr][nc] == 0
                ):
                    visited[nr][nc] = True
                    queue.append((nr, nc))
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 0 and not visited[r][c]:
                    grid[r][c] = border_color
        return grid

    elif connect_mode == "connect_to_rectangle":
        positions = [
            (r, c)
            for r, row in enumerate(grid)
            for c, v in enumerate(row)
            if v == fill_color
        ]
        min_row, max_row, min_col, max_col = find_bounding_rectangle(positions)
        for r in range(min_row, max_row + 1):
            for c in range(min_col, max_col + 1):
                if r in {min_row, max_row} or c in {min_col, max_col}:
                    grid[r][c] = (
                        border_color if grid[r][c] != fill_color else grid[r][c]
                    )
        return grid

    elif connect_mode == "connect_with_line":
        c_bf, c_fw = color, fill_color
        cells = {
            (i, j)
            for i, row in enumerate(grid)
            for j, cell in enumerate(row)
            if cell == c_bf
        }

        def connect(a, b):
            ai, aj = a
            bi, bj = b
            si, ei = sorted([ai, bi])
            sj, ej = sorted([aj, bj])

            if ai == bi:
                return frozenset((ai, j) for j in range(sj, ej + 1))
            if aj == bj:
                return frozenset((i, aj) for i in range(si, ei + 1))
            if (bi - ai) == (bj - aj):
                return frozenset(zip(range(si, ei + 1), range(sj, ej + 1)))
            if (bi - ai) == (aj - bj):
                return frozenset(zip(range(si, ei + 1), range(ej, sj - 1, -1)))
            return frozenset()

        connected_patches = {
            patch for a in cells for b in cells if (patch := connect(a, b))
        }

        line_patches = {
            patch
            for patch in connected_patches
            if len(patch) > 1
            and (len({j for _, j in patch}) == 1 or len({i for i, _ in patch}) == 1)
        }
        merged_line_indices = set().union(*line_patches) if line_patches else set()
        grid_with_lines = fill(grid, c_fw, merged_line_indices)
        transformed_grid = fill(grid_with_lines, c_bf, cells)
        return transformed_grid

    elif connect_mode == "connect_taxicab":
        color_cells = [
            (r, c)
            for r, row in enumerate(grid)
            for c, v in enumerate(row)
            if v == color
        ]
        fill_cells = [
            (r, c)
            for r, row in enumerate(grid)
            for c, v in enumerate(row)
            if v == fill_color
        ]
        anchor = (fill_cells[0][0], color_cells[0][1])

        def connect(start, end):
            r1, c1, r2, c2 = *start, *end
            return (
                [(r1, c) for c in range(min(c1, c2), max(c1, c2) + 1)]
                if r1 == r2
                else [(r, c1) for r in range(min(r1, r2), max(r1, r2) + 1)]
            )

        paths = set(connect(anchor, color_cells[0]) + connect(anchor, fill_cells[0]))
        for r, c in paths:
            if 0 <= r < len(grid) and 0 <= c < len(grid[0]) and grid[r][c] == 0:
                grid[r][c] = border_color
        return grid

    elif connect_mode == "connect_with_intersection":
        partitioned_objects = frozenset(
            frozenset(
                (v, (i, j))
                for i, row in enumerate(grid)
                for j, v in enumerate(row)
                if v == color
            )
            for color in frozenset({v for row in grid for v in row})
        )

        recolored_objects = frozenset(
            frozenset(
                (next(iter(obj))[0], (i, j))
                for i in range(min(x[1][0] for x in obj), max(x[1][0] for x in obj) + 1)
                for j in range(min(x[1][1] for x in obj), max(x[1][1] for x in obj) + 1)
            )
            for obj in partitioned_objects
        )

        filtered_horizontal = frozenset(
            obj
            for obj in recolored_objects
            if len(set(i for _, (i, _) in obj)) == 1
            and len(set(j for _, (_, j) in obj)) > 1
        )

        filtered_vertical = frozenset(
            obj
            for obj in recolored_objects
            if len(set(j for _, (_, j) in obj)) == 1
            and len(set(i for _, (i, _) in obj)) > 1
        )

        h, w = len(grid), len(grid[0])
        I_painted_horizontal = [[grid[i][j] for j in range(w)] for i in range(h)]
        for obj in filtered_horizontal:
            for value, (i, j) in obj:
                if 0 <= i < h and 0 <= j < w:
                    I_painted_horizontal[i][j] = value

        grid_painted_vertical = [
            [I_painted_horizontal[i][j] for j in range(w)] for i in range(h)
        ]
        for obj in filtered_vertical:
            for value, (i, j) in obj:
                if 0 <= i < h and 0 <= j < w:
                    if inherit_vertical or I_painted_horizontal[i][j] == value:
                        grid_painted_vertical[i][j] = value

        transformed_grid = tuple(tuple(row) for row in grid_painted_vertical)
        return transformed_grid

    elif connect_mode == "cross_mode":
        background_color = max(
            set(val for row in grid for val in row),
            key=lambda c: sum(row.count(c) for row in grid),
        )
        foreground_components = find_connected_components(
            grid,
            target_colors=get_unique_colors_except_background(grid, background_color),
            background_color=background_color,
            connectivity=8,
        )

        recolored_patches = {
            (comp["color"], (i, loc[1]))
            for comp in foreground_components
            for loc in comp["pixels"]
            for i in range(30)
        } | {
            (comp["color"], (loc[0], j))
            for comp in foreground_components
            for loc in comp["pixels"]
            for j in range(30)
        }
        height, width = len(grid), len(grid[0])
        grid_painted = [
            [
                next(
                    (color for color, pos in recolored_patches if pos == (i, j)),
                    grid[i][j],
                )
                for j in range(width)
            ]
            for i in range(height)
        ]
        extended_lines = [
            {(i, loc[1]) for i in range(30) for _, loc in patch}
            | {(loc[0], j) for j in range(30) for _, loc in patch}
            for patch in (
                frozenset((comp["color"], (r, c)) for (r, c) in comp["pixels"])
                for comp in foreground_components
            )
        ]
        intersection_lines = (
            set.intersection(*extended_lines) if extended_lines else set()
        )
        for i, j in intersection_lines:
            if 0 <= i < height and 0 <= j < width:
                grid_painted[i][j] = color
        return tuple(map(tuple, grid_painted))

    elif connect_mode == "star_mode":
        grid_height, grid_width = len(grid), len(grid[0])
        diagonals = {(i, i) for i in range(min(grid_height, grid_width))} | {
            (i, grid_width - 1 - i) for i in range(min(grid_height, grid_width))
        }
        grid_filled = [list(row) for row in grid]
        for i, j in diagonals:
            if 0 <= i < grid_height and 0 <= j < grid_width:
                grid_filled[i][j] = color
        return tuple(tuple(row) for row in grid_filled)

    elif connect_mode == "diagonal":
        background_color = max(
            (value for row in grid for value in row),
            key=lambda v: sum(row.count(v) for row in grid),
        )
        foreground_colors = {
            value for row in grid for value in row if value != background_color
        }
        positions_by_color = collect_positions_by_color(grid, foreground_colors)
        final_recolored_patches = set()
        for color, positions in positions_by_color.items():
            if positions:
                first, last = min(positions), max(positions)
                si, sj, ei, ej = *first, *last
                if si == ei:
                    connected_line = {
                        (si, j) for j in range(min(sj, ej), max(sj, ej) + 1)
                    }
                elif sj == ej:
                    connected_line = {
                        (i, sj) for i in range(min(si, ei), max(si, ei) + 1)
                    }
                elif ei - si == ej - sj:
                    connected_line = {
                        (i, j) for i, j in zip(range(si, ei + 1), range(sj, ej + 1))
                    }
                elif ei - si == sj - ej:
                    connected_line = {
                        (i, j) for i, j in zip(range(si, ei + 1), range(sj, ej - 1, -1))
                    }
                else:
                    continue
                final_recolored_patches.update((color, pos) for pos in connected_line)

        height, width = len(grid), len(grid[0])
        grid_painted = [list(row) for row in grid]
        for color, (i, j) in final_recolored_patches:
            if 0 <= i < height and 0 <= j < width:
                grid_painted[i][j] = color
        return tuple(map(tuple, grid_painted))
    else:
        raise ValueError(f"{Fore.RED}Wrong mode. You provided {connect_mode}{Style.RESET_ALL}")

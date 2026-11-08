import copy
from collections import defaultdict


def _color_components(grid, color, connectivity=8):
    if not grid:
        return []
    rows, cols = len(grid), len(grid[0])
    deltas = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ] if connectivity == 8 else [(-1, 0), (1, 0), (0, -1), (0, 1)]
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


def _component_bbox(component):
    rows = [row for row, _ in component]
    cols = [col for _, col in component]
    return min(rows), max(rows), min(cols), max(cols)


def _transpose(grid):
    if not grid:
        return []
    return [list(row) for row in zip(*grid)]


def _squeeze_frame_horizontal(grid, keep_occluded=True, background_color=0):
    """Compact skewed frame rows toward the right edge of each component bbox."""
    if not grid:
        return []
    transformed = copy.deepcopy(grid)
    colors = sorted({
        value
        for row in grid
        for value in row
        if value != background_color
    })
    if not colors:
        raise ValueError("squeeze requires foreground")

    for color in colors:
        for component in _color_components(grid, color, connectivity=8):
            if not component:
                continue
            _, _, _, max_col = _component_bbox(component)
            rows_to_cols = defaultdict(list)
            for row, col in component:
                rows_to_cols[row].append(col)

            updated_component = set()
            changed = False
            for row, cols in rows_to_cols.items():
                ordered = sorted(cols)
                contiguous_suffix = ordered == list(range(min(ordered), max_col + 1))
                if max(ordered) == max_col and contiguous_suffix:
                    new_cols = ordered
                elif max(ordered) == max_col:
                    new_cols = [col if col == max_col else col + 1 for col in ordered]
                else:
                    new_cols = [col + 1 for col in ordered]

                if not keep_occluded and new_cols:
                    new_cols = list(range(min(new_cols), max(new_cols) + 1))
                if new_cols != ordered:
                    changed = True
                updated_component.update((row, col) for col in new_cols)

            if not changed:
                continue
            for row, col in component:
                transformed[row][col] = background_color
            for row, col in updated_component:
                transformed[row][col] = color

    return transformed


def squeeze_grid_based(grid, axis="horizontal", keep_occluded=True, background_color=0):
    if axis == "horizontal":
        return _squeeze_frame_horizontal(
            grid,
            keep_occluded=keep_occluded,
            background_color=background_color,
        )
    if axis == "vertical":
        squeezed = _squeeze_frame_horizontal(
            _transpose(grid),
            keep_occluded=keep_occluded,
            background_color=background_color,
        )
        return _transpose(squeezed)
    raise ValueError(f"squeeze axis must be 'horizontal' or 'vertical', got {axis!r}")

from collections import Counter
import copy


def _background_color(grid, background_color=None):
    if background_color is not None:
        return background_color
    counts = Counter(value for row in grid for value in row)
    return counts.most_common(1)[0][0]


def _most_common_non_background_color(grid, background_color=0):
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background_color
    )
    if not counts:
        raise ValueError("No non-background color")
    return counts.most_common(1)[0][0]


def _fill_with_most_frequent_non_background(grid, background_color=0):
    color = _most_common_non_background_color(grid, background_color=background_color)
    return [[color for _ in row] for row in grid]


def _repeat_nonzero_row_period(grid, background_color=0):
    if not grid:
        return []
    rows = len(grid)
    nonzero_rows = [
        row
        for row, values in enumerate(grid)
        if any(value != background_color for value in values)
    ]
    if not nonzero_rows:
        return [row[:] for row in grid]
    start = min(nonzero_rows)
    end = max(nonzero_rows)
    pattern = [grid[row][:] for row in range(start, end + 1)]
    sparse_rows = [
        (index, [col for col, value in enumerate(values) if value != background_color])
        for index, values in enumerate(pattern)
        if any(value != background_color for value in values)
        and any(value == background_color for value in values)
    ]
    if sparse_rows:
        first_index, _ = max(
            sparse_rows,
            key=lambda item: (min(item[1]), -item[0]),
        )
        pattern = pattern[first_index:] + pattern[:first_index]
    return [pattern[row % len(pattern)][:] for row in range(rows)]


def _foreground_bbox(grid, background_color):
    points = [
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value != background_color
    ]
    if not points:
        raise ValueError("No foreground pixels found")
    return (
        min(row for row, _ in points),
        max(row for row, _ in points),
        min(col for _, col in points),
        max(col for _, col in points),
    )


def _crop_non_background_bbox(grid, background_color=None):
    background_color = _background_color(grid, background_color)
    min_row, max_row, min_col, max_col = _foreground_bbox(grid, background_color)
    return [
        row[min_col:max_col + 1]
        for row in grid[min_row:max_row + 1]
    ]


def _remove_background_rows_cols(grid, background_color=None):
    background_color = _background_color(grid, background_color)
    rows = [
        row
        for row, values in enumerate(grid)
        if any(value != background_color for value in values)
    ]
    cols = [
        col
        for col in range(len(grid[0]))
        if any(grid[row][col] != background_color for row in range(len(grid)))
    ]
    if not rows or not cols:
        raise ValueError("No foreground rows/columns found")
    return [
        [grid[row][col] for col in cols]
        for row in rows
    ]


def _rotate(grid, degrees):
    turns = (int(degrees) // 90) % 4
    result = copy.deepcopy(grid)
    for _ in range(turns):
        result = [list(row) for row in zip(*result)][::-1]
    return result


def _mirror(grid, mirror_axis):
    if mirror_axis == "horizontal":
        return [list(reversed(row)) for row in grid]
    if mirror_axis == "vertical":
        return list(reversed(copy.deepcopy(grid)))
    if mirror_axis == "diagonal":
        return [list(col) for col in zip(*grid)]
    raise ValueError(f"Unsupported mirror axis: {mirror_axis}")


def _upscale_pixel(grid, factor):
    factor = int(factor)
    return [
        [value for value in row for _ in range(factor)]
        for row in grid
        for _ in range(factor)
    ]


def _downscale_block_mode(grid, factor, background_color=None):
    factor = int(factor)
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if rows % factor or cols % factor:
        raise ValueError("Grid size must be divisible by downscale factor")
    transformed = []
    for row in range(0, rows, factor):
        out_row = []
        for col in range(0, cols, factor):
            values = [
                grid[r][c]
                for r in range(row, row + factor)
                for c in range(col, col + factor)
            ]
            out_row.append(Counter(values).most_common(1)[0][0])
        transformed.append(out_row)
    return transformed


def _extract_periodic_unit(grid):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    for tile_rows in range(1, rows + 1):
        if rows % tile_rows:
            continue
        for tile_cols in range(1, cols + 1):
            if cols % tile_cols:
                continue
            tile = [
                row[:tile_cols]
                for row in grid[:tile_rows]
            ]
            if all(
                grid[row][col] == tile[row % tile_rows][col % tile_cols]
                for row in range(rows)
                for col in range(cols)
            ):
                return tile
    return copy.deepcopy(grid)


def _corner_crop(grid, crop_height, crop_width, corner="left upper"):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    crop_height = int(crop_height)
    crop_width = int(crop_width)
    if crop_height > rows or crop_width > cols:
        raise ValueError("Corner crop larger than grid")
    start_row = 0 if "upper" in corner else rows - crop_height
    start_col = 0 if "left" in corner else cols - crop_width
    return [
        row[start_col:start_col + crop_width]
        for row in grid[start_row:start_row + crop_height]
    ]


def _corner_crop_ratio(
    grid,
    height_divisor=1,
    width_divisor=2,
    corner="left upper",
):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    height_divisor = int(height_divisor)
    width_divisor = int(width_divisor)
    if rows % height_divisor or cols % width_divisor:
        raise ValueError("Grid dimensions not divisible by corner crop ratio")
    return _corner_crop(
        grid,
        rows // height_divisor,
        cols // width_divisor,
        corner=corner,
    )


def _grid_key(grid):
    return tuple(tuple(row) for row in grid)


def _mask_key(grid, background_color=0):
    return tuple(
        tuple(0 if value == background_color else 1 for value in row)
        for row in grid
    )


def _flat(grid):
    return [value for row in grid for value in row]


def _tile_key(tile, pattern_mode="mask", background_color=0):
    if pattern_mode == "mask":
        return _mask_key(tile, background_color=background_color)
    if pattern_mode == "exact":
        return _grid_key(tile)
    raise ValueError(f"Unsupported tile pattern mode: {pattern_mode}")


def _zero_separator_tiles(grid, background_color=0):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    separator_rows = [
        row
        for row, values in enumerate(grid)
        if all(value == background_color for value in values)
    ]
    separator_cols = [
        col
        for col in range(cols)
        if all(grid[row][col] == background_color for row in range(rows))
    ]

    row_spans = []
    start = 0
    for row in separator_rows + [rows]:
        if start < row:
            row_spans.append((start, row))
        start = row + 1

    col_spans = []
    start = 0
    for col in separator_cols + [cols]:
        if start < col:
            col_spans.append((start, col))
        start = col + 1

    tiles = []
    for row_start, row_end in row_spans:
        for col_start, col_end in col_spans:
            tile = [
                row[col_start:col_end]
                for row in grid[row_start:row_end]
            ]
            if tile and tile[0] and any(
                value != background_color for value in _flat(tile)
            ):
                tiles.append(tile)
    return tiles


def _chunk_tiles(grid, crop_height, crop_width, background_color=0):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    crop_height = int(crop_height)
    crop_width = int(crop_width)
    if crop_height <= 0 or crop_width <= 0:
        raise ValueError("Chunk dimensions must be positive")
    if rows % crop_height or cols % crop_width:
        raise ValueError("Grid dimensions are not divisible by chunk size")

    return [
        [
            row[col:col + crop_width]
            for row in grid[row_start:row_start + crop_height]
        ]
        for row_start in range(0, rows, crop_height)
        for col in range(0, cols, crop_width)
        if any(
            value != background_color
            for source_row in grid[row_start:row_start + crop_height]
            for value in source_row[col:col + crop_width]
        )
    ]


def _symmetry_count(mask):
    rows = len(mask)
    cols = len(mask[0]) if rows else 0
    score = 0
    if all(mask[row][col] == mask[row][cols - 1 - col] for row in range(rows) for col in range(cols)):
        score += 1
    if all(mask[row][col] == mask[rows - 1 - row][col] for row in range(rows) for col in range(cols)):
        score += 1
    if all(mask[row][col] == mask[rows - 1 - row][cols - 1 - col] for row in range(rows) for col in range(cols)):
        score += 1
    if rows == cols and all(mask[row][col] == mask[col][row] for row in range(rows) for col in range(cols)):
        score += 1
    if rows == cols and all(mask[row][col] == mask[cols - 1 - col][rows - 1 - row] for row in range(rows) for col in range(cols)):
        score += 1
    return score


def _tile_symmetry_score(tile, background_color=None):
    colors = set(_flat(tile))
    if background_color is not None:
        colors.discard(background_color)
    if not colors:
        raise ValueError("No colors to score")

    score = 0
    for color in colors:
        mask = [
            [1 if value == color else 0 for value in row]
            for row in tile
        ]
        score += _symmetry_count(mask)
    return score


def _select_tile(
    grid,
    background_color=0,
    split_mode="zero_separator",
    selection="unique_pattern",
    pattern_mode="mask",
    crop_height=3,
    crop_width=3,
):
    if split_mode == "zero_separator":
        tiles = _zero_separator_tiles(grid, background_color=background_color)
    elif split_mode == "chunk":
        tiles = _chunk_tiles(
            grid,
            crop_height=crop_height,
            crop_width=crop_width,
            background_color=background_color,
        )
    else:
        raise ValueError(f"Unsupported tile split mode: {split_mode}")

    if not tiles:
        raise ValueError("No candidate tiles found")

    if selection == "unique_pattern":
        keys = [
            _tile_key(tile, pattern_mode=pattern_mode, background_color=background_color)
            for tile in tiles
        ]
        counts = Counter(keys)
        unique_indices = [
            index for index, key in enumerate(keys)
            if counts[key] == 1
        ]
        if len(unique_indices) != 1:
            raise ValueError("Expected exactly one uniquely patterned tile")
        return copy.deepcopy(tiles[unique_indices[0]])

    if selection == "unique_color":
        colors = []
        for tile in tiles:
            non_background = set(_flat(tile)) - {background_color}
            if len(non_background) != 1:
                raise ValueError("Expected each tile to have exactly one non-background color")
            colors.append(next(iter(non_background)))
        counts = Counter(colors)
        unique_indices = [
            index for index, color in enumerate(colors)
            if counts[color] == 1
        ]
        if len(unique_indices) != 1:
            raise ValueError("Expected exactly one uniquely colored tile")
        return copy.deepcopy(tiles[unique_indices[0]])

    if selection in {"symmetry_min", "symmetry_max"}:
        scores = [
            _tile_symmetry_score(tile, background_color=None)
            for tile in tiles
        ]
        target = min(scores) if selection == "symmetry_min" else max(scores)
        indices = [
            index for index, score in enumerate(scores)
            if score == target
        ]
        if len(indices) != 1:
            raise ValueError("Expected exactly one tile at selected symmetry score")
        return copy.deepcopy(tiles[indices[0]])

    raise ValueError(f"Unsupported tile selection: {selection}")


def _window_full_extent(window, background_color=0):
    points = [
        (row, col)
        for row, values in enumerate(window)
        for col, value in enumerate(values)
        if value != background_color
    ]
    if not points:
        return False
    rows = len(window)
    cols = len(window[0]) if rows else 0
    return (
        min(row for row, _ in points) == 0
        and max(row for row, _ in points) == rows - 1
        and min(col for _, col in points) == 0
        and max(col for _, col in points) == cols - 1
    )


def _window_is_isolated(grid, row_start, col_start, crop_height, crop_width, background_color=0):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    for row in range(max(0, row_start - 1), min(rows, row_start + crop_height + 1)):
        for col in range(max(0, col_start - 1), min(cols, col_start + crop_width + 1)):
            if row_start <= row < row_start + crop_height and col_start <= col < col_start + crop_width:
                continue
            if grid[row][col] != background_color:
                return False
    return True


def _candidate_windows(
    grid,
    crop_height,
    crop_width,
    background_color=0,
    require_full_extent=False,
    require_isolated=False,
):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    crop_height = int(crop_height)
    crop_width = int(crop_width)
    if crop_height <= 0 or crop_width <= 0:
        raise ValueError("Window dimensions must be positive")
    if crop_height > rows or crop_width > cols:
        raise ValueError("Window larger than grid")

    windows = []
    for row in range(rows - crop_height + 1):
        for col in range(cols - crop_width + 1):
            window = [
                source_row[col:col + crop_width]
                for source_row in grid[row:row + crop_height]
            ]
            if not any(value != background_color for value in _flat(window)):
                continue
            if require_full_extent and not _window_full_extent(
                window,
                background_color=background_color,
            ):
                continue
            if require_isolated and not _window_is_isolated(
                grid,
                row,
                col,
                crop_height,
                crop_width,
                background_color=background_color,
            ):
                continue
            windows.append((row, col, window))
    return windows


def _select_repeated_window(
    grid,
    background_color=0,
    crop_height=3,
    crop_width=3,
    pattern_mode="exact",
    frequency_mode="most",
    require_full_extent=True,
    require_isolated=False,
):
    windows = _candidate_windows(
        grid,
        crop_height=crop_height,
        crop_width=crop_width,
        background_color=background_color,
        require_full_extent=require_full_extent,
        require_isolated=require_isolated,
    )
    if not windows:
        raise ValueError("No candidate windows found")

    keys = [
        _tile_key(window, pattern_mode=pattern_mode, background_color=background_color)
        for _, _, window in windows
    ]
    counts = Counter(keys)
    target = max(counts.values()) if frequency_mode == "most" else min(counts.values())
    selected_keys = [
        key for key, count in counts.items()
        if count == target
    ]
    if len(selected_keys) != 1:
        raise ValueError("Expected exactly one selected repeated-window pattern")
    selected_key = selected_keys[0]
    for _, _, window in windows:
        if _tile_key(window, pattern_mode=pattern_mode, background_color=background_color) == selected_key:
            return copy.deepcopy(window)
    raise ValueError("Selected repeated window not found")


def _select_window_adjacent_to_color(
    grid,
    background_color=0,
    marker_color=5,
    crop_height=3,
    crop_width=3,
    require_full_extent=True,
):
    marker_pixels = {
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value == marker_color
    }
    if not marker_pixels:
        raise ValueError("No marker pixels found")

    windows = _candidate_windows(
        grid,
        crop_height=crop_height,
        crop_width=crop_width,
        background_color=background_color,
        require_full_extent=require_full_extent,
        require_isolated=False,
    )
    selected = []
    for row_start, col_start, window in windows:
        values = set(_flat(window))
        if marker_color in values:
            continue
        non_background = values - {background_color}
        if not non_background:
            continue

        touches_marker = False
        for local_row, values_row in enumerate(window):
            for local_col, value in enumerate(values_row):
                if value == background_color:
                    continue
                row = row_start + local_row
                col = col_start + local_col
                for delta_row, delta_col in (
                    (-1, -1), (-1, 0), (-1, 1),
                    (0, -1),           (0, 1),
                    (1, -1),  (1, 0),  (1, 1),
                ):
                    if (row + delta_row, col + delta_col) in marker_pixels:
                        touches_marker = True
                        break
                if touches_marker:
                    break
            if touches_marker:
                break
        if touches_marker:
            selected.append(window)

    selected_keys = {_grid_key(window) for window in selected}
    if len(selected_keys) != 1:
        raise ValueError("Expected exactly one marker-adjacent window")
    return copy.deepcopy(selected[0])


def _foreground_bbox_corner_crop_ratio(
    grid,
    background_color=0,
    height_divisor=2,
    width_divisor=2,
    corner="left upper",
):
    min_row, max_row, min_col, max_col = _foreground_bbox(grid, background_color)
    height = max_row - min_row + 1
    width = max_col - min_col + 1
    height_divisor = int(height_divisor)
    width_divisor = int(width_divisor)
    if height % height_divisor or width % width_divisor:
        raise ValueError("Foreground bbox dimensions not divisible by crop ratio")
    crop_height = height // height_divisor
    crop_width = width // width_divisor
    start_row = min_row if "upper" in corner else max_row - crop_height + 1
    start_col = min_col if "left" in corner else max_col - crop_width + 1
    return [
        row[start_col:start_col + crop_width]
        for row in grid[start_row:start_row + crop_height]
    ]


def _select_cross_split_block(
    grid,
    background_color=0,
    selection="unique_marker_color",
):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    row_candidates = [
        (row, values[0])
        for row, values in enumerate(grid)
        if values and len(set(values)) == 1
    ]
    col_candidates = []
    for col in range(cols):
        values = [grid[row][col] for row in range(rows)]
        if values and len(set(values)) == 1:
            col_candidates.append((col, values[0]))

    for split_row, row_color in row_candidates:
        for split_col, col_color in col_candidates:
            if row_color != col_color:
                continue
            spans = [
                (0, split_row, 0, split_col),
                (0, split_row, split_col + 1, cols),
                (split_row + 1, rows, 0, split_col),
                (split_row + 1, rows, split_col + 1, cols),
            ]
            if any(row_start >= row_end or col_start >= col_end for row_start, row_end, col_start, col_end in spans):
                continue
            blocks = [
                [
                    row[col_start:col_end]
                    for row in grid[row_start:row_end]
                ]
                for row_start, row_end, col_start, col_end in spans
            ]

            if selection != "unique_marker_color":
                raise ValueError(f"Unsupported cross split selection: {selection}")

            color_blocks = {}
            for index, block in enumerate(blocks):
                for color in set(_flat(block)) - {row_color}:
                    color_blocks.setdefault(color, set()).add(index)
            unique_colors = [
                (color, next(iter(indices)))
                for color, indices in color_blocks.items()
                if len(indices) == 1
            ]
            if not unique_colors:
                continue
            candidates = []
            for color, index in unique_colors:
                count = sum(value == color for value in _flat(blocks[index]))
                candidates.append((count, color, index))
            candidates.sort()
            if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
                continue
            return copy.deepcopy(blocks[candidates[0][2]])

    raise ValueError("No cross-split block selected")


def _components(grid, background_color=0, component_mode="same_color"):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    visited = [[False for _ in range(cols)] for _ in range(rows)]
    components = []

    for row in range(rows):
        for col in range(cols):
            if visited[row][col] or grid[row][col] == background_color:
                continue
            color = grid[row][col]
            stack = [(row, col)]
            visited[row][col] = True
            pixels = []
            while stack:
                current_row, current_col = stack.pop()
                pixels.append((current_row, current_col))
                for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    next_row = current_row + delta_row
                    next_col = current_col + delta_col
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if visited[next_row][next_col] or grid[next_row][next_col] == background_color:
                        continue
                    if component_mode == "same_color" and grid[next_row][next_col] != color:
                        continue
                    visited[next_row][next_col] = True
                    stack.append((next_row, next_col))

            min_row = min(point[0] for point in pixels)
            max_row = max(point[0] for point in pixels)
            min_col = min(point[1] for point in pixels)
            max_col = max(point[1] for point in pixels)
            area = (max_row - min_row + 1) * (max_col - min_col + 1)
            components.append({
                "color": color,
                "pixels": pixels,
                "size": len(pixels),
                "bbox": (min_row, max_row, min_col, max_col),
                "area": area,
                "height": max_row - min_row + 1,
                "width": max_col - min_col + 1,
            })
    return components


def _components_8_connected(grid, background_color=0):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    visited = [[False for _ in range(cols)] for _ in range(rows)]
    components = []

    for row in range(rows):
        for col in range(cols):
            if visited[row][col] or grid[row][col] == background_color:
                continue
            stack = [(row, col)]
            visited[row][col] = True
            pixels = []
            while stack:
                current_row, current_col = stack.pop()
                pixels.append((current_row, current_col))
                for delta_row in (-1, 0, 1):
                    for delta_col in (-1, 0, 1):
                        if delta_row == 0 and delta_col == 0:
                            continue
                        next_row = current_row + delta_row
                        next_col = current_col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if visited[next_row][next_col] or grid[next_row][next_col] == background_color:
                            continue
                        visited[next_row][next_col] = True
                        stack.append((next_row, next_col))

            min_row = min(point[0] for point in pixels)
            max_row = max(point[0] for point in pixels)
            min_col = min(point[1] for point in pixels)
            max_col = max(point[1] for point in pixels)
            area = (max_row - min_row + 1) * (max_col - min_col + 1)
            components.append({
                "pixels": pixels,
                "bbox": (min_row, max_row, min_col, max_col),
                "size": len(pixels),
                "area": area,
                "height": max_row - min_row + 1,
                "width": max_col - min_col + 1,
            })
    return components


def _component_mask(component):
    min_row, max_row, min_col, max_col = component["bbox"]
    pixels = set(component["pixels"])
    return [
        [
            1 if (row, col) in pixels else 0
            for col in range(min_col, max_col + 1)
        ]
        for row in range(min_row, max_row + 1)
    ]


def _is_vertically_symmetric(mask):
    rows = len(mask)
    cols = len(mask[0]) if rows else 0
    return all(
        mask[row][col] == mask[row][cols - 1 - col]
        for row in range(rows)
        for col in range(cols)
    )


def _select_component(components, selection):
    if not components:
        raise ValueError("No components found")

    if selection == "size_max":
        return max(components, key=lambda item: (item["size"], -item["bbox"][0], -item["bbox"][2]))
    if selection == "size_min":
        return min(components, key=lambda item: (item["size"], item["bbox"][0], item["bbox"][2]))
    if selection == "area_max":
        return max(components, key=lambda item: (item["area"], -item["bbox"][0], -item["bbox"][2]))
    if selection == "area_min":
        return min(components, key=lambda item: (item["area"], item["bbox"][0], item["bbox"][2]))
    if selection == "height_max":
        return max(components, key=lambda item: (item["height"], item["width"]))
    if selection == "width_max":
        return max(components, key=lambda item: (item["width"], item["height"]))
    if selection == "unique_color":
        counts = Counter(item["color"] for item in components)
        unique = [item for item in components if counts[item["color"]] == 1]
        if len(unique) != 1:
            raise ValueError("Expected exactly one uniquely colored component")
        return unique[0]
    if selection == "least_color_count":
        counts = Counter(item["color"] for item in components)
        return min(components, key=lambda item: (counts[item["color"]], item["size"]))
    if selection == "most_color_count":
        counts = Counter(item["color"] for item in components)
        return max(components, key=lambda item: (counts[item["color"]], item["size"]))
    raise ValueError(f"Unsupported component selection: {selection}")


def _extract_component(
    grid,
    background_color=0,
    component_mode="same_color",
    selection="size_max",
    output_mode="subgrid",
    crop_height=1,
    crop_width=1,
    corner="left upper",
):
    components = _components(
        grid,
        background_color=background_color,
        component_mode=component_mode,
    )
    component = _select_component(components, selection)
    min_row, max_row, min_col, max_col = component["bbox"]
    if output_mode == "subgrid":
        return [
            row[min_col:max_col + 1]
            for row in grid[min_row:max_row + 1]
        ]
    if output_mode == "mask":
        pixels = set(component["pixels"])
        return [
            [
                grid[row][col] if (row, col) in pixels else background_color
                for col in range(min_col, max_col + 1)
            ]
            for row in range(min_row, max_row + 1)
        ]
    raise ValueError(f"Unsupported component output mode: {output_mode}")


def _extract_8_connected_asymmetric_component(grid, background_color=0):
    components = _components_8_connected(grid, background_color=background_color)
    selected = [
        component
        for component in components
        if not _is_vertically_symmetric(_component_mask(component))
    ]
    if len(selected) != 1:
        raise ValueError("Expected exactly one vertically asymmetric 8-connected component")
    return _component_to_grid(
        grid,
        selected[0],
        background_color=background_color,
        output_mode="mask",
    )


def _component_to_grid(grid, component, background_color=0, output_mode="subgrid"):
    min_row, max_row, min_col, max_col = component["bbox"]
    if output_mode == "subgrid":
        return [
            row[min_col:max_col + 1]
            for row in grid[min_row:max_row + 1]
        ]
    if output_mode == "mask":
        pixels = set(component["pixels"])
        return [
            [
                grid[row][col] if (row, col) in pixels else background_color
                for col in range(min_col, max_col + 1)
            ]
            for row in range(min_row, max_row + 1)
        ]
    raise ValueError(f"Unsupported component output mode: {output_mode}")


def _component_count_for_color(grid, color):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    visited = [[False for _ in range(cols)] for _ in range(rows)]
    sizes = []
    for row in range(rows):
        for col in range(cols):
            if visited[row][col] or grid[row][col] != color:
                continue
            stack = [(row, col)]
            visited[row][col] = True
            size = 0
            while stack:
                current_row, current_col = stack.pop()
                size += 1
                for next_row, next_col in (
                    (current_row - 1, current_col),
                    (current_row + 1, current_col),
                    (current_row, current_col - 1),
                    (current_row, current_col + 1),
                ):
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if visited[next_row][next_col] or grid[next_row][next_col] != color:
                        continue
                    visited[next_row][next_col] = True
                    stack.append((next_row, next_col))
            sizes.append(size)
    return sizes


def _foreground_marker_color(grid, background_color=0):
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background_color
    )
    if not counts:
        raise ValueError("No foreground color")
    return min(counts, key=lambda color: (counts[color], color))


def _extract_component_by_foreground_count(
    grid,
    background_color=0,
    output_mode="subgrid",
):
    components = _components(
        grid,
        background_color=background_color,
        component_mode="multi_color",
    )
    if not components:
        raise ValueError("No components found")

    marker_color = _foreground_marker_color(grid, background_color=background_color)
    scored = []
    for component in components:
        component_grid = _component_to_grid(
            grid,
            component,
            background_color=background_color,
            output_mode="subgrid",
        )
        marker_sizes = _component_count_for_color(component_grid, marker_color)
        single_square_count = sum(1 for size in marker_sizes if size == 1)
        multisquare_count = sum(1 for size in marker_sizes if size > 1)
        if single_square_count > multisquare_count or multisquare_count <= 0:
            continue
        foreground_pixel_count = sum(marker_sizes)
        score = (-foreground_pixel_count, multisquare_count)
        scored.append((score, component))

    if not scored:
        raise ValueError("No component matches foreground-count constraint")

    best_score = min(score for score, _ in scored)
    selected = [component for score, component in scored if score == best_score]
    if len(selected) != 1:
        raise ValueError("Expected exactly one component selected by foreground count")
    return _component_to_grid(
        grid,
        selected[0],
        background_color=background_color,
        output_mode=output_mode,
    )


def _extract_component_by_color_count(
    grid,
    background_color=0,
    marker_color=2,
    frequency_mode="most",
    output_mode="subgrid",
):
    components = _components(
        grid,
        background_color=background_color,
        component_mode="multi_color",
    )
    scored = []
    for component in components:
        marker_count = sum(
            1
            for row, col in component["pixels"]
            if grid[row][col] == marker_color
        )
        if marker_count > 0:
            scored.append((marker_count, component))
    if not scored:
        raise ValueError("No component contains marker color")

    if frequency_mode == "most":
        target = max(score for score, _ in scored)
    elif frequency_mode == "least":
        target = min(score for score, _ in scored)
    else:
        raise ValueError(f"Unsupported frequency mode: {frequency_mode}")

    selected = [
        component for score, component in scored
        if score == target
    ]
    if len(selected) != 1:
        raise ValueError("Expected exactly one component selected by marker count")
    return _component_to_grid(
        grid,
        selected[0],
        background_color=background_color,
        output_mode=output_mode,
    )


def _extract_color_bbox_by_feature(
    grid,
    background_color=0,
    selection="symmetry_max",
):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    candidates = []
    for color in set(_flat(grid)) - {background_color}:
        pixels = [
            (row, col)
            for row, values in enumerate(grid)
            for col, value in enumerate(values)
            if value == color
        ]
        if not pixels:
            continue
        min_row = min(row for row, _ in pixels)
        max_row = max(row for row, _ in pixels)
        min_col = min(col for _, col in pixels)
        max_col = max(col for _, col in pixels)
        subgrid = [
            row[min_col:max_col + 1]
            for row in grid[min_row:max_row + 1]
        ]
        mask = [
            [1 if value == color else 0 for value in row]
            for row in subgrid
        ]
        candidates.append({
            "color": color,
            "subgrid": subgrid,
            "symmetry": _symmetry_count(mask),
            "area": (max_row - min_row + 1) * (max_col - min_col + 1),
            "count": len(pixels),
            "row": min_row,
            "col": min_col,
        })
    if not candidates:
        raise ValueError("No foreground color bboxes found")

    if selection == "symmetry_max":
        target = max(candidate["symmetry"] for candidate in candidates)
        selected = [
            candidate for candidate in candidates
            if candidate["symmetry"] == target
        ]
    else:
        raise ValueError(f"Unsupported color bbox selection: {selection}")

    if len(selected) != 1:
        raise ValueError("Expected exactly one color bbox selected by feature")
    return copy.deepcopy(selected[0]["subgrid"])


def _crop_color_bbox_with_padding(
    grid,
    marker_color=5,
    padding_rows=0,
    padding_cols=0,
):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    pixels = [
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value == marker_color
    ]
    if not pixels:
        raise ValueError("No marker-color pixels found")

    padding_rows = int(padding_rows)
    padding_cols = int(padding_cols)
    min_row = max(0, min(row for row, _ in pixels) - padding_rows)
    max_row = min(rows - 1, max(row for row, _ in pixels) + padding_rows)
    min_col = max(0, min(col for _, col in pixels) - padding_cols)
    max_col = min(cols - 1, max(col for _, col in pixels) + padding_cols)
    return [
        row[min_col:max_col + 1]
        for row in grid[min_row:max_row + 1]
    ]


def _crop_inside_repeated_horizontal_bar(grid, background_color=0):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    runs = []
    for row_index, values in enumerate(grid):
        col = 0
        while col < cols:
            end_col = col
            while end_col < cols and values[end_col] == values[col]:
                end_col += 1
            run_length = end_col - col
            if values[col] != background_color and run_length >= 3:
                runs.append((row_index, col, end_col - 1, values[col], run_length))
            col = end_col

    pairs = []
    for first_index, first in enumerate(runs):
        for second in runs[first_index + 1:]:
            row_a, col_a, end_a, color_a, length_a = first
            row_b, col_b, end_b, color_b, _ = second
            if (
                color_a == color_b
                and col_a == col_b
                and end_a == end_b
                and row_b - row_a > 1
                and end_a - col_a >= 2
            ):
                pairs.append((length_a, row_b - row_a, row_a, row_b, col_a, end_a))

    if not pairs:
        raise ValueError("No repeated horizontal bar pair found")
    longest = max(length for length, *_ in pairs)
    selected = [
        pair for pair in pairs
        if pair[0] == longest
    ]
    if len(selected) != 1:
        raise ValueError("Expected exactly one repeated horizontal bar pair")
    _, _, row_a, row_b, col_a, end_a = selected[0]
    return [
        row[col_a + 1:end_a]
        for row in grid[row_a + 1:row_b]
    ]


def _same_color_components_for_color(grid, color):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    visited = [[False for _ in range(cols)] for _ in range(rows)]
    components = []
    for row in range(rows):
        for col in range(cols):
            if visited[row][col] or grid[row][col] != color:
                continue
            stack = [(row, col)]
            visited[row][col] = True
            pixels = []
            while stack:
                current_row, current_col = stack.pop()
                pixels.append((current_row, current_col))
                for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    next_row = current_row + delta_row
                    next_col = current_col + delta_col
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if visited[next_row][next_col] or grid[next_row][next_col] != color:
                        continue
                    visited[next_row][next_col] = True
                    stack.append((next_row, next_col))
            components.append(pixels)
    return components


def _enclosed_cells_inside_component_bbox(grid, pixels):
    min_row = min(row for row, _ in pixels)
    max_row = max(row for row, _ in pixels)
    min_col = min(col for _, col in pixels)
    max_col = max(col for _, col in pixels)
    height = max_row - min_row + 1
    width = max_col - min_col + 1
    blocked = {
        (row - min_row, col - min_col)
        for row, col in pixels
    }

    seen = set()
    stack = []
    for row in range(height):
        for col in (0, width - 1):
            if (row, col) not in blocked and (row, col) not in seen:
                seen.add((row, col))
                stack.append((row, col))
    for col in range(width):
        for row in (0, height - 1):
            if (row, col) not in blocked and (row, col) not in seen:
                seen.add((row, col))
                stack.append((row, col))

    while stack:
        row, col = stack.pop()
        for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_row = row + delta_row
            next_col = col + delta_col
            if not (0 <= next_row < height and 0 <= next_col < width):
                continue
            if (next_row, next_col) in blocked or (next_row, next_col) in seen:
                continue
            seen.add((next_row, next_col))
            stack.append((next_row, next_col))

    enclosed = []
    for row in range(height):
        for col in range(width):
            if (row, col) in blocked or (row, col) in seen:
                continue
            source_row = min_row + row
            source_col = min_col + col
            enclosed.append((source_row, source_col, grid[source_row][source_col]))
    return enclosed


def _select_color_with_enclosed_background_hole(grid, background_color=0):
    candidates = []
    for color in set(_flat(grid)) - {background_color}:
        for pixels in _same_color_components_for_color(grid, color):
            enclosed = _enclosed_cells_inside_component_bbox(grid, pixels)
            background_holes = [
                value for _, _, value in enclosed
                if value == background_color
            ]
            if background_holes:
                candidates.append((color, len(background_holes), len(pixels)))
    if len(candidates) != 1:
        raise ValueError("Expected exactly one color enclosing background")
    return [[candidates[0][0]]]


def _select_enclosed_nonself_color(grid, background_color=0):
    enclosed_values = []
    for color in set(_flat(grid)) - {background_color}:
        for pixels in _same_color_components_for_color(grid, color):
            enclosed = _enclosed_cells_inside_component_bbox(grid, pixels)
            for _, _, value in enclosed:
                if value not in (background_color, color):
                    enclosed_values.append(value)
    counts = Counter(enclosed_values)
    if len(counts) != 1:
        raise ValueError("Expected exactly one enclosed non-self color")
    return [[next(iter(counts))]]


def _select_color_most_adjacent_to_rarest_color(grid, background_color=0):
    counts = Counter(_flat(grid))
    rare_candidates = [
        (count, color)
        for color, count in counts.items()
        if color != background_color
    ]
    if not rare_candidates:
        raise ValueError("No non-background colors found")
    rare_candidates.sort()
    if len(rare_candidates) > 1 and rare_candidates[0][0] == rare_candidates[1][0]:
        raise ValueError("Rarest color is tied")
    rare_color = rare_candidates[0][1]

    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    adjacency = Counter()
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] != rare_color:
                continue
            for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                next_row = row + delta_row
                next_col = col + delta_col
                if not (0 <= next_row < rows and 0 <= next_col < cols):
                    continue
                value = grid[next_row][next_col]
                if value not in (background_color, rare_color):
                    adjacency[value] += 1
    if not adjacency:
        raise ValueError("Rarest color has no colored adjacency")
    target = max(adjacency.values())
    colors = [
        color for color, count in adjacency.items()
        if count == target
    ]
    if len(colors) != 1:
        raise ValueError("Most-adjacent color is tied")
    return [[colors[0]]]


def _sparse_points_macro_cell_square(grid, background_color=0):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    points = [
        (row, col, value)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value != background_color
    ]
    if not points:
        raise ValueError("No sparse points found")
    side = int(len(points) ** 0.5)
    if side * side != len(points) or side < 2:
        raise ValueError("Sparse point count must be a square")
    if rows % side or cols % side:
        raise ValueError("Sparse point grid dimensions must divide into square macro-cells")
    cell_rows = rows // side
    cell_cols = cols // side

    output = [[background_color for _ in range(side)] for _ in range(side)]
    seen_cells = set()
    for row, col, value in points:
        macro_row = row // cell_rows
        macro_col = col // cell_cols
        cell = (macro_row, macro_col)
        if cell in seen_cells:
            raise ValueError("Expected one sparse point per macro-cell")
        seen_cells.add(cell)
        output[macro_row][macro_col] = value
    if len(seen_cells) != side * side:
        raise ValueError("Expected every macro-cell to contain one sparse point")
    return [
        row[:]
        for row in output
    ]


def _x_marker_compact_5x5(grid, background_color=0):
    if len(grid) != 5 or any(len(row) != 5 for row in grid):
        raise ValueError("X-marker compaction requires a 5x5 grid")
    positions = [
        (0, 0), (1, 1), (0, 4),
        (1, 3), (2, 2), (3, 1),
        (4, 0), (3, 3), (4, 4),
    ]
    required = set(positions)
    for row in range(5):
        for col in range(5):
            value = grid[row][col]
            if (row, col) in required:
                if value == background_color:
                    raise ValueError("X-marker compaction requires all marker positions")
            elif value != background_color:
                raise ValueError("X-marker compaction requires only X marker positions")
    return [
        [grid[row][col] for row, col in positions[index:index + 3]]
        for index in range(0, len(positions), 3)
    ]


def _cluster_intervals(intervals):
    clusters = []
    for start, end in sorted(intervals):
        if not clusters or start > clusters[-1][1]:
            clusters.append([start, end])
        else:
            clusters[-1][1] = max(clusters[-1][1], end)
    return [(start, end) for start, end in clusters]


def _dominant_rectangle_block_grid(grid, background_color=0):
    non_background = [
        value
        for row in grid
        for value in row
        if value != background_color
    ]
    if not non_background:
        raise ValueError("Dominant rectangle block grid requires foreground colors")
    frame_color = Counter(non_background).most_common(1)[0][0]
    components = [
        component
        for component in _components(grid, background_color=background_color)
        if component["color"] != frame_color
    ]
    if len(components) < 2:
        raise ValueError("Dominant rectangle block grid requires multiple colored blocks")
    for component in components:
        if component["size"] != component["area"]:
            raise ValueError("Colored blocks must be solid rectangles")

    row_clusters = _cluster_intervals([
        (component["bbox"][0], component["bbox"][1])
        for component in components
    ])
    col_clusters = _cluster_intervals([
        (component["bbox"][2], component["bbox"][3])
        for component in components
    ])
    if not row_clusters or not col_clusters:
        raise ValueError("No block row/column clusters found")

    output = [
        [background_color for _ in col_clusters]
        for _ in row_clusters
    ]
    for component in components:
        min_row, max_row, min_col, max_col = component["bbox"]
        row_indices = [
            index for index, (start, end) in enumerate(row_clusters)
            if not (max_row < start or min_row > end)
        ]
        col_indices = [
            index for index, (start, end) in enumerate(col_clusters)
            if not (max_col < start or min_col > end)
        ]
        if len(row_indices) != 1 or len(col_indices) != 1:
            raise ValueError("Colored block did not map to one compact cell")
        row_index = row_indices[0]
        col_index = col_indices[0]
        current = output[row_index][col_index]
        if current != background_color and current != component["color"]:
            raise ValueError("Multiple colored blocks conflict in one compact cell")
        output[row_index][col_index] = component["color"]
    return output


def _horizontal_run_color_summary(grid, background_color=0, output_width=3):
    source_background = _background_color(grid, None)
    output_width = int(output_width)
    if output_width <= 0:
        raise ValueError("Horizontal run color summary requires positive output width")
    runs = []
    for row in grid:
        col = 0
        while col < len(row):
            value = row[col]
            start = col
            while col < len(row) and row[col] == value:
                col += 1
            if value != source_background and col - start > 1:
                runs.append(value)
    if not runs:
        raise ValueError("Horizontal run color summary requires non-background runs")

    counts = Counter(runs)
    values = []
    for color in sorted(counts, reverse=True):
        values.extend([color] * counts[color])

    output = []
    for start in range(0, len(values), output_width):
        row = values[start:start + output_width]
        if len(row) < output_width:
            row.extend([background_color] * (output_width - len(row)))
        output.append(row)
    return output


def _separator_post_count_delta_fill(
    grid,
    background_color=0,
    output_height=2,
    output_width=2,
):
    output_height = int(output_height)
    output_width = int(output_width)
    if output_height <= 0 or output_width <= 0:
        raise ValueError("Separator count-delta fill requires positive output dimensions")
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    separator_rows = []
    for row_index, row in enumerate(grid):
        counts = Counter(row)
        if len(counts) == 1:
            color = row[0]
            if color != background_color:
                separator_rows.append((row_index, color))
    if len(separator_rows) != 1:
        raise ValueError("Expected exactly one non-background full-row separator")
    separator_row, separator_color = separator_rows[0]

    before = Counter(
        value
        for row in grid[:separator_row]
        for value in row
        if value not in (background_color, separator_color)
    )
    after = Counter(
        value
        for row in grid[separator_row + 1:]
        for value in row
        if value not in (background_color, separator_color)
    )
    candidates = [
        (after[color] - before[color], color)
        for color in sorted(set(before) | set(after))
    ]
    candidates = [item for item in candidates if item[0] > 0]
    if not candidates:
        raise ValueError("No color increased after separator")
    candidates.sort(reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise ValueError("Separator count-delta fill has tied colors")
    target_color = candidates[0][1]
    return [
        [target_color for _ in range(output_width)]
        for _ in range(output_height)
    ]


def _reverse_row_bands(grid, background_color=0, band_height=2):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    band_height = int(band_height)
    if rows == 0 or cols == 0 or band_height <= 0:
        raise ValueError("Reverse row bands requires a non-empty grid and positive band height")
    if any(len(row) != cols for row in grid):
        raise ValueError("Reverse row bands requires a rectangular grid")
    if rows % band_height:
        raise ValueError("Reverse row bands requires band height to divide row count")
    bands = [
        [row[:] for row in grid[start:start + band_height]]
        for start in range(0, rows, band_height)
    ]
    if len(bands) < 2:
        raise ValueError("Reverse row bands requires at least two bands")
    for band in bands:
        if not any(value != background_color for row in band for value in row):
            raise ValueError("Reverse row bands rejects empty foreground bands")
    output = [
        row
        for band in reversed(bands)
        for row in band
    ]
    if output == grid:
        raise ValueError("Reverse row bands made no change")
    return output


def _component_count_plus_one_column(grid, background_color=0):
    if not grid or not grid[0]:
        raise ValueError("Component-count column requires a non-empty grid")
    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Component-count column requires a rectangular grid")
    visited = set()
    component_count = 0
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] == background_color or (row, col) in visited:
                continue
            component_count += 1
            stack = [(row, col)]
            visited.add((row, col))
            while stack:
                current_row, current_col = stack.pop()
                for next_row, next_col in (
                    (current_row - 1, current_col),
                    (current_row + 1, current_col),
                    (current_row, current_col - 1),
                    (current_row, current_col + 1),
                ):
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if (
                        grid[next_row][next_col] == background_color
                        or (next_row, next_col) in visited
                    ):
                        continue
                    visited.add((next_row, next_col))
                    stack.append((next_row, next_col))
    if component_count <= 0:
        raise ValueError("Component-count column requires foreground components")
    return [[background_color] for _ in range(component_count + 1)]


def _rectangular_frame_components(grid, background_color=0):
    frames = []
    for component in _components(grid, background_color=background_color):
        min_row, max_row, min_col, max_col = component["bbox"]
        if max_row - min_row < 2 or max_col - min_col < 2:
            continue
        border = {
            (row, col)
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
            if row in (min_row, max_row) or col in (min_col, max_col)
        }
        if set(component["pixels"]) == border:
            frames.append(component)
    return sorted(frames, key=lambda item: (-item["area"], item["bbox"]))


def _even_spans(length, count):
    if count <= 0 or length <= 0 or length % count:
        raise ValueError("Frame interior matrix requires even partition spans")
    span = length // count
    return [(index * span, (index + 1) * span) for index in range(count)]


def _frame_interior_palette_grid_expand(grid, background_color=0):
    if not grid or not grid[0]:
        raise ValueError("Frame interior expansion requires a non-empty grid")
    if any(len(row) != len(grid[0]) for row in grid):
        raise ValueError("Frame interior expansion requires a rectangular grid")

    frames = _rectangular_frame_components(grid, background_color=background_color)
    if len(frames) != 1:
        raise ValueError("Frame interior expansion requires one rectangular frame")

    frame = frames[0]
    frame_color = frame["color"]
    min_row, max_row, min_col, max_col = frame["bbox"]
    inner_height = max_row - min_row - 1
    inner_width = max_col - min_col - 1
    if inner_height <= 0 or inner_width <= 0:
        raise ValueError("Frame interior expansion requires a hollow frame")

    interior = [
        row[min_col + 1:max_col]
        for row in grid[min_row + 1:max_row]
    ]
    if any(value == frame_color for row in interior for value in row):
        raise ValueError("Frame interior expansion rejects frame-color interior cells")
    components = _components(interior, background_color=background_color)
    if not components:
        raise ValueError("Frame interior expansion requires interior color cells")
    if any(component["size"] != component["area"] for component in components):
        raise ValueError("Interior palette cells must be solid rectangles")

    row_clusters = _cluster_intervals([
        (component["bbox"][0], component["bbox"][1])
        for component in components
    ])
    col_clusters = _cluster_intervals([
        (component["bbox"][2], component["bbox"][3])
        for component in components
    ])
    if not row_clusters or not col_clusters:
        raise ValueError("Interior palette matrix requires row and column clusters")

    palette = {}
    for component in components:
        min_r, max_r, min_c, max_c = component["bbox"]
        row_matches = [
            index for index, (start, end) in enumerate(row_clusters)
            if start <= min_r and max_r <= end
        ]
        col_matches = [
            index for index, (start, end) in enumerate(col_clusters)
            if start <= min_c and max_c <= end
        ]
        if len(row_matches) != 1 or len(col_matches) != 1:
            raise ValueError("Interior palette component does not map to one matrix slot")
        key = (row_matches[0], col_matches[0])
        if key in palette:
            raise ValueError("Interior palette matrix slot has multiple components")
        palette[key] = component["color"]

    if len(palette) != len(row_clusters) * len(col_clusters):
        raise ValueError("Interior palette matrix must be complete")

    row_spans = _even_spans(inner_height, len(row_clusters))
    col_spans = _even_spans(inner_width, len(col_clusters))
    output = [
        row[min_col:max_col + 1]
        for row in grid[min_row:max_row + 1]
    ]
    for row_index, (row_start, row_end) in enumerate(row_spans):
        for col_index, (col_start, col_end) in enumerate(col_spans):
            color = palette[(row_index, col_index)]
            for row in range(row_start + 1, row_end + 1):
                for col in range(col_start + 1, col_end + 1):
                    output[row][col] = color
    if output == [
        row[min_col:max_col + 1]
        for row in grid[min_row:max_row + 1]
    ]:
        raise ValueError("Frame interior expansion made no change")
    return output


def _normalized_cells(cells):
    min_row = min(row for row, _ in cells)
    min_col = min(col for _, col in cells)
    return tuple(sorted((row - min_row, col - min_col) for row, col in cells))


def _background_components_inside_box(grid, box, background_color=0):
    min_row, max_row, min_col, max_col = box
    visited = set()
    components = []
    for row in range(min_row + 1, max_row):
        for col in range(min_col + 1, max_col):
            if grid[row][col] != background_color or (row, col) in visited:
                continue
            stack = [(row, col)]
            visited.add((row, col))
            cells = []
            while stack:
                current_row, current_col = stack.pop()
                cells.append((current_row, current_col))
                for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    next_row = current_row + delta_row
                    next_col = current_col + delta_col
                    if not (
                        min_row < next_row < max_row
                        and min_col < next_col < max_col
                    ):
                        continue
                    if (
                        (next_row, next_col) in visited
                        or grid[next_row][next_col] != background_color
                    ):
                        continue
                    visited.add((next_row, next_col))
                    stack.append((next_row, next_col))
            components.append(cells)
    return components


def _partition_frame_components(grid, background_color=0):
    frames = []
    for component in _components(grid, background_color=background_color):
        min_row, max_row, min_col, max_col = component["bbox"]
        if max_row - min_row < 2 or max_col - min_col < 2:
            continue
        color = component["color"]
        if not all(grid[min_row][col] == color and grid[max_row][col] == color for col in range(min_col, max_col + 1)):
            continue
        if not all(grid[row][min_col] == color and grid[row][max_col] == color for row in range(min_row, max_row + 1)):
            continue
        if not _background_components_inside_box(
            grid,
            component["bbox"],
            background_color=background_color,
        ):
            continue
        frames.append(component)
    return sorted(frames, key=lambda item: (-item["area"], item["bbox"]))


def _frame_hole_shape_donor_fill(grid, background_color=0):
    if not grid or not grid[0]:
        raise ValueError("Frame hole donor fill requires a non-empty grid")
    if any(len(row) != len(grid[0]) for row in grid):
        raise ValueError("Frame hole donor fill requires a rectangular grid")

    candidates = []
    frames = _partition_frame_components(grid, background_color=background_color)
    for frame in frames:
        frame_color = frame["color"]
        min_row, max_row, min_col, max_col = frame["bbox"]
        holes = _background_components_inside_box(
            grid,
            frame["bbox"],
            background_color=background_color,
        )
        if not holes:
            continue
        donors_by_shape = {}
        for component in _components(grid, background_color=background_color):
            if component["color"] == frame_color:
                continue
            if any(
                min_row <= row <= max_row and min_col <= col <= max_col
                for row, col in component["pixels"]
            ):
                continue
            donors_by_shape.setdefault(
                _normalized_cells(component["pixels"]),
                [],
            ).append(component)

        output = [
            row[min_col:max_col + 1]
            for row in grid[min_row:max_row + 1]
        ]
        used = set()
        matched = True
        for hole in sorted(holes, key=lambda cells: (min(row for row, _ in cells), min(col for _, col in cells))):
            shape = _normalized_cells(hole)
            donors = [
                donor
                for donor in donors_by_shape.get(shape, [])
                if tuple(donor["pixels"]) not in used
            ]
            if len(donors) != 1:
                matched = False
                break
            donor = donors[0]
            used.add(tuple(donor["pixels"]))
            for row, col in hole:
                output[row - min_row][col - min_col] = donor["color"]
        if matched and output != [
            row[min_col:max_col + 1]
            for row in grid[min_row:max_row + 1]
        ]:
            candidates.append(output)

    unique = []
    seen = set()
    for candidate in candidates:
        key = _grid_key(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    if len(unique) != 1:
        raise ValueError("Frame hole donor fill requires one unambiguous candidate")
    return unique[0]


def _nested_component_bbox_frames(grid, background_color=0):
    if not grid or not grid[0]:
        raise ValueError("Nested component bbox frames require a non-empty grid")
    if any(len(row) != len(grid[0]) for row in grid):
        raise ValueError("Nested component bbox frames require a rectangular grid")
    cells_by_color = {}
    for row, values in enumerate(grid):
        for col, value in enumerate(values):
            if value != background_color:
                cells_by_color.setdefault(value, []).append((row, col))
    if len(cells_by_color) < 2:
        raise ValueError("Nested component bbox frames require multiple colors")

    items = []
    for color, cells in cells_by_color.items():
        min_row = min(row for row, _ in cells)
        max_row = max(row for row, _ in cells)
        min_col = min(col for _, col in cells)
        max_col = max(col for _, col in cells)
        height = max_row - min_row + 1
        width = max_col - min_col + 1
        area = height * width
        side = max(height, width)
        if side <= 0:
            continue
        items.append((
            side,
            color,
            {
                "area": area,
                "size": len(cells),
            },
        ))
    if len({side for side, _, _ in items}) != len(items):
        raise ValueError("Nested component bbox frame side lengths must be unique")
    items.sort(key=lambda item: (-item[0], item[1]))
    max_side = items[0][0]
    expected_sides = list(range(max_side, 0, -2))
    sides = [side for side, _, _ in items]
    if sides != expected_sides[:len(sides)]:
        raise ValueError("Nested component bbox frame side lengths must decrease by two")
    if any((max_side - side) % 2 for side in sides):
        raise ValueError("Nested component bbox frames require centered parity")

    output = [
        [background_color for _ in range(max_side)]
        for _ in range(max_side)
    ]
    for side, color, component in items:
        inset = (max_side - side) // 2
        solid = side <= 2 or component["size"] == component["area"]
        for row in range(inset, inset + side):
            for col in range(inset, inset + side):
                if solid or row in (inset, inset + side - 1) or col in (inset, inset + side - 1):
                    output[row][col] = color
    return output


def _center_2x2_block_to_corners(grid, background_color=0):
    if len(grid) != 4 or any(len(row) != 4 for row in grid):
        raise ValueError("Center 2x2 block to corners requires a 4x4 grid")
    center_positions = {
        (1, 1): (0, 0),
        (1, 2): (0, 3),
        (2, 1): (3, 0),
        (2, 2): (3, 3),
    }
    if any(
        grid[row][col] != background_color
        for row in range(4)
        for col in range(4)
        if (row, col) not in center_positions
    ):
        raise ValueError("Center 2x2 block to corners requires empty outer cells")
    if any(grid[row][col] == background_color for row, col in center_positions):
        raise ValueError("Center 2x2 block to corners requires a full center block")

    output = [[background_color for _ in range(4)] for _ in range(4)]
    for source, target in center_positions.items():
        output[target[0]][target[1]] = grid[source[0]][source[1]]
    return output


def _tile_by_unique_color_count(grid):
    if not grid or not grid[0]:
        raise ValueError("Tile by unique color count requires a non-empty grid")
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Tile by unique color count requires a rectangular grid")
    factor = len({value for row in grid for value in row})
    if factor < 2 or factor > 8:
        raise ValueError("Tile by unique color count requires a bounded factor")
    return [
        [grid[row % len(grid)][col % cols] for col in range(cols * factor)]
        for row in range(len(grid) * factor)
    ]


def basic_grid_based(
    grid,
    transform_type="crop_non_background_bbox",
    background_color=0,
    factor=2,
    degrees=90,
    mirror_axis="horizontal",
    component_mode="same_color",
    selection="size_max",
    output_mode="subgrid",
    crop_height=1,
    crop_width=1,
    corner="left upper",
    height_divisor=1,
    width_divisor=2,
    split_mode="zero_separator",
    pattern_mode="mask",
    marker_color=5,
    padding_rows=0,
    padding_cols=0,
    frequency_mode="most",
    require_full_extent=True,
    require_isolated=False,
):
    if transform_type == "fill_with_most_frequent_non_background":
        return _fill_with_most_frequent_non_background(
            grid,
            background_color=background_color,
        )
    if transform_type == "repeat_nonzero_row_period":
        return _repeat_nonzero_row_period(
            grid,
            background_color=background_color,
        )
    if transform_type == "crop_non_background_bbox":
        return _crop_non_background_bbox(grid, background_color=background_color)
    if transform_type == "remove_background_rows_cols":
        return _remove_background_rows_cols(grid, background_color=background_color)
    if transform_type == "rotate":
        return _rotate(grid, degrees=degrees)
    if transform_type == "mirror":
        return _mirror(grid, mirror_axis=mirror_axis)
    if transform_type == "upscale_pixel":
        return _upscale_pixel(grid, factor=factor)
    if transform_type == "downscale_block_mode":
        return _downscale_block_mode(
            grid,
            factor=factor,
            background_color=background_color,
        )
    if transform_type == "extract_periodic_unit":
        return _extract_periodic_unit(grid)
    if transform_type == "corner_crop":
        return _corner_crop(
            grid,
            crop_height=crop_height,
            crop_width=crop_width,
            corner=corner,
        )
    if transform_type == "corner_crop_ratio":
        return _corner_crop_ratio(
            grid,
            height_divisor=height_divisor,
            width_divisor=width_divisor,
            corner=corner,
        )
    if transform_type == "foreground_bbox_corner_crop_ratio":
        return _foreground_bbox_corner_crop_ratio(
            grid,
            background_color=background_color,
            height_divisor=height_divisor,
            width_divisor=width_divisor,
            corner=corner,
        )
    if transform_type == "select_tile":
        return _select_tile(
            grid,
            background_color=background_color,
            split_mode=split_mode,
            selection=selection,
            pattern_mode=pattern_mode,
            crop_height=crop_height,
            crop_width=crop_width,
        )
    if transform_type == "select_repeated_window":
        return _select_repeated_window(
            grid,
            background_color=background_color,
            crop_height=crop_height,
            crop_width=crop_width,
            pattern_mode=pattern_mode,
            frequency_mode=frequency_mode,
            require_full_extent=require_full_extent,
            require_isolated=require_isolated,
        )
    if transform_type == "select_window_adjacent_to_color":
        return _select_window_adjacent_to_color(
            grid,
            background_color=background_color,
            marker_color=marker_color,
            crop_height=crop_height,
            crop_width=crop_width,
            require_full_extent=require_full_extent,
        )
    if transform_type == "select_cross_split_block":
        return _select_cross_split_block(
            grid,
            background_color=background_color,
            selection=selection,
        )
    if transform_type == "extract_component":
        return _extract_component(
            grid,
            background_color=background_color,
            component_mode=component_mode,
            selection=selection,
            output_mode=output_mode,
        )
    if transform_type == "extract_component_by_color_count":
        return _extract_component_by_color_count(
            grid,
            background_color=background_color,
            marker_color=marker_color,
            frequency_mode=frequency_mode,
            output_mode=output_mode,
        )
    if transform_type == "extract_component_by_foreground_count":
        return _extract_component_by_foreground_count(
            grid,
            background_color=background_color,
            output_mode=output_mode,
        )
    if transform_type == "extract_8_connected_asymmetric_component":
        return _extract_8_connected_asymmetric_component(
            grid,
            background_color=background_color,
        )
    if transform_type == "extract_color_bbox_by_feature":
        return _extract_color_bbox_by_feature(
            grid,
            background_color=background_color,
            selection=selection,
        )
    if transform_type == "crop_color_bbox_with_padding":
        return _crop_color_bbox_with_padding(
            grid,
            marker_color=marker_color,
            padding_rows=padding_rows,
            padding_cols=padding_cols,
        )
    if transform_type == "crop_inside_repeated_horizontal_bar":
        return _crop_inside_repeated_horizontal_bar(
            grid,
            background_color=background_color,
        )
    if transform_type == "select_color_with_enclosed_background_hole":
        return _select_color_with_enclosed_background_hole(
            grid,
            background_color=background_color,
        )
    if transform_type == "select_enclosed_nonself_color":
        return _select_enclosed_nonself_color(
            grid,
            background_color=background_color,
        )
    if transform_type == "select_color_most_adjacent_to_rarest_color":
        return _select_color_most_adjacent_to_rarest_color(
            grid,
            background_color=background_color,
        )
    if transform_type == "sparse_points_macro_cell_square":
        return _sparse_points_macro_cell_square(
            grid,
            background_color=background_color,
        )
    if transform_type == "x_marker_compact_5x5":
        return _x_marker_compact_5x5(
            grid,
            background_color=background_color,
        )
    if transform_type == "dominant_rectangle_block_grid":
        return _dominant_rectangle_block_grid(
            grid,
            background_color=background_color,
        )
    if transform_type == "horizontal_run_color_summary":
        return _horizontal_run_color_summary(
            grid,
            background_color=background_color,
            output_width=crop_width,
        )
    if transform_type == "separator_post_count_delta_fill":
        return _separator_post_count_delta_fill(
            grid,
            background_color=background_color,
            output_height=crop_height,
            output_width=crop_width,
        )
    if transform_type == "reverse_row_bands":
        return _reverse_row_bands(
            grid,
            background_color=background_color,
            band_height=crop_height,
        )
    if transform_type == "component_count_plus_one_column":
        return _component_count_plus_one_column(
            grid,
            background_color=background_color,
        )
    if transform_type == "frame_interior_palette_grid_expand":
        return _frame_interior_palette_grid_expand(
            grid,
            background_color=background_color,
        )
    if transform_type == "frame_hole_shape_donor_fill":
        return _frame_hole_shape_donor_fill(
            grid,
            background_color=background_color,
        )
    if transform_type == "nested_component_bbox_frames":
        return _nested_component_bbox_frames(
            grid,
            background_color=background_color,
        )
    if transform_type == "center_2x2_block_to_corners":
        return _center_2x2_block_to_corners(
            grid,
            background_color=background_color,
        )
    if transform_type == "tile_by_unique_color_count":
        return _tile_by_unique_color_count(grid)
    raise ValueError(f"Unsupported basic grid transform: {transform_type}")

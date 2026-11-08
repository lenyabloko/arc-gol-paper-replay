try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def _marker_component_overlay(
    grid,
    marker_color=5,
    background_color=0,
    connectivity=8,
):
    if not grid or not grid[0]:
        return []

    rows = len(grid)
    cols = len(grid[0])
    if connectivity == 8:
        neighbors = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ]
    elif connectivity == 4:
        neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    else:
        raise ValueError("marker component overlay connectivity must be 4 or 8")

    visited = set()
    components = []
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] == background_color or (row, col) in visited:
                continue
            stack = [(row, col)]
            visited.add((row, col))
            component = []
            while stack:
                r, c = stack.pop()
                component.append((r, c, grid[r][c]))
                for dr, dc in neighbors:
                    nr, nc = r + dr, c + dc
                    if (
                        0 <= nr < rows
                        and 0 <= nc < cols
                        and (nr, nc) not in visited
                        and grid[nr][nc] != background_color
                    ):
                        visited.add((nr, nc))
                        stack.append((nr, nc))
            components.append(component)

    if not components:
        return [row[:] for row in grid]

    overlay_cells = {}
    for component in components:
        markers = [(r, c) for r, c, color in component if color == marker_color]
        if len(markers) != 1:
            raise ValueError(
                "marker component overlay requires each component to contain exactly one marker"
            )
        marker_row, marker_col = markers[0]
        for row, col, color in component:
            rel = (row - marker_row, col - marker_col)
            previous = overlay_cells.get(rel, background_color)
            if (
                previous != background_color
                and previous != color
                and color != marker_color
            ):
                raise ValueError(
                    f"conflicting overlay colors at relative cell {rel}: "
                    f"{previous} vs {color}"
                )
            if color != marker_color or rel not in overlay_cells:
                overlay_cells[rel] = color

    min_row = min(row for row, _ in overlay_cells)
    max_row = max(row for row, _ in overlay_cells)
    min_col = min(col for _, col in overlay_cells)
    max_col = max(col for _, col in overlay_cells)
    output = [
        [background_color for _ in range(max_col - min_col + 1)]
        for _ in range(max_row - min_row + 1)
    ]
    for (row, col), color in overlay_cells.items():
        output[row - min_row][col - min_col] = color
    return output


def _full_separator_segments_with_axis(grid, separator_color):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    full_cols = [
        col
        for col in range(cols)
        if all(grid[row][col] == separator_color for row in range(rows))
    ]
    if full_cols:
        segments = []
        start = 0
        for col in full_cols + [cols]:
            if start < col:
                segments.append([row[start:col] for row in grid])
            start = col + 1
        return [segment for segment in segments if segment and segment[0]], "vertical"

    full_rows = [
        row
        for row in range(rows)
        if all(grid[row][col] == separator_color for col in range(cols))
    ]
    if full_rows:
        segments = []
        start = 0
        for row in full_rows + [rows]:
            if start < row:
                segments.append([source_row[:] for source_row in grid[start:row]])
            start = row + 1
        return [segment for segment in segments if segment and segment[0]], "horizontal"

    return [], None


def _full_separator_segments(grid, separator_color):
    segments, _ = _full_separator_segments_with_axis(grid, separator_color)
    return segments


def _separator_region_overlay(
    grid,
    separator_color=5,
    background_color=0,
    overlay="intersection",
    output_color=None,
):
    if not grid or not grid[0]:
        return []

    regions = _full_separator_segments(grid, separator_color)
    if len(regions) < 2:
        raise ValueError("separator region overlay requires at least two regions")

    return _overlay_regions(
        regions,
        background_color=background_color,
        ignored_colors={background_color, separator_color},
        overlay=overlay,
        output_color=output_color,
    )


def _separator_quadrant_overlay(
    grid,
    separator_color=5,
    background_color=0,
    overlay="priority_union",
    output_color=None,
):
    if not grid or not grid[0]:
        return []

    rows = len(grid)
    cols = len(grid[0])
    full_rows = [
        row
        for row in range(rows)
        if all(grid[row][col] == separator_color for col in range(cols))
    ]
    full_cols = [
        col
        for col in range(cols)
        if all(grid[row][col] == separator_color for row in range(rows))
    ]
    if len(full_rows) != 1 or len(full_cols) != 1:
        raise ValueError("separator quadrant overlay requires exactly one full separator row and column")

    sep_row = full_rows[0]
    sep_col = full_cols[0]
    regions = [
        [source_row[:sep_col] for source_row in grid[:sep_row]],
        [source_row[sep_col + 1:] for source_row in grid[:sep_row]],
        [source_row[:sep_col] for source_row in grid[sep_row + 1:]],
        [source_row[sep_col + 1:] for source_row in grid[sep_row + 1:]],
    ]
    if any(not region or not region[0] for region in regions):
        raise ValueError("separator quadrant overlay requires non-empty quadrants")

    return _overlay_regions(
        regions,
        background_color=background_color,
        ignored_colors={background_color, separator_color},
        overlay=overlay,
        output_color=output_color,
    )


def _quadrant_overlay(
    grid,
    background_color=0,
    overlay="priority_tr_bl_br_tl",
    output_color=None,
):
    if not grid or not grid[0]:
        return []

    rows = len(grid)
    cols = len(grid[0])
    if rows % 2 != 0 or cols % 2 != 0:
        raise ValueError("quadrant overlay requires even grid dimensions")
    half_rows = rows // 2
    half_cols = cols // 2
    regions_by_name = {
        "tl": [source_row[:half_cols] for source_row in grid[:half_rows]],
        "tr": [source_row[half_cols:] for source_row in grid[:half_rows]],
        "bl": [source_row[:half_cols] for source_row in grid[half_rows:]],
        "br": [source_row[half_cols:] for source_row in grid[half_rows:]],
    }

    if overlay == "priority_tr_bl_br_tl":
        regions = [
            regions_by_name["tr"],
            regions_by_name["bl"],
            regions_by_name["br"],
            regions_by_name["tl"],
        ]
        return _overlay_regions(
            regions,
            background_color=background_color,
            overlay="priority_union",
            output_color=output_color,
        )

    if overlay == "priority_union":
        regions = [
            regions_by_name["tl"],
            regions_by_name["tr"],
            regions_by_name["bl"],
            regions_by_name["br"],
        ]
        return _overlay_regions(
            regions,
            background_color=background_color,
            overlay=overlay,
            output_color=output_color,
        )

    raise ValueError(f"unsupported quadrant overlay mode: {overlay}")


def _separator_mirror_region_overlay(
    grid,
    separator_color=5,
    background_color=0,
    overlay="union",
    output_color=None,
):
    if not grid or not grid[0]:
        return []

    regions, axis = _full_separator_segments_with_axis(grid, separator_color)
    if len(regions) != 2:
        raise ValueError("separator mirror overlay requires exactly two regions")
    if len(regions[0]) != len(regions[1]) or len(regions[0][0]) != len(regions[1][0]):
        raise ValueError("separator mirror overlay requires equal-size regions")

    first, second = regions
    if axis == "vertical":
        second = [row[::-1] for row in second]
    elif axis == "horizontal":
        second = list(reversed(second))
    else:
        raise ValueError("separator mirror overlay requires a full row or column separator")

    return _overlay_regions(
        [first, second],
        background_color=background_color,
        ignored_colors={background_color, separator_color},
        overlay=overlay,
        output_color=output_color,
    )


def _background_separator_segments(grid, axis, background_color=0):
    if not grid or not grid[0]:
        return []
    rows = len(grid)
    cols = len(grid[0])
    size = rows if axis == "row" else cols

    def is_blank(index):
        if axis == "row":
            return all(grid[index][col] == background_color for col in range(cols))
        return all(grid[row][index] == background_color for row in range(rows))

    segments = []
    start = None
    for index in range(size):
        if is_blank(index):
            if start is not None:
                segments.append((start, index))
                start = None
        elif start is None:
            start = index
    if start is not None:
        segments.append((start, size))
    return segments


def _corner_region_overlay(
    grid,
    background_color=0,
    overlay="union",
    output_color=None,
):
    if not grid or not grid[0]:
        return []

    row_segments = _background_separator_segments(grid, "row", background_color)
    col_segments = _background_separator_segments(grid, "col", background_color)
    if len(row_segments) != 2 or len(col_segments) != 2:
        raise ValueError("corner region overlay requires two row bands and two column bands")

    (top_start, top_end), (bottom_start, bottom_end) = row_segments
    (left_start, left_end), (right_start, right_end) = col_segments
    top_height = top_end - top_start
    bottom_height = bottom_end - bottom_start
    left_width = left_end - left_start
    right_width = right_end - right_start

    output_height = max(3, max(top_height, bottom_height) * 2 - 1)
    output_width = max(3, max(left_width, right_width) * 2 - 1)
    if output_height <= 0 or output_width <= 0:
        raise ValueError("corner region overlay requires non-empty corner regions")

    placements = [
        (top_start, left_start, top_height, left_width, 0, 0),
        (top_start, right_start, top_height, right_width, 0, output_width - right_width),
        (bottom_start, left_start, bottom_height, left_width, output_height - bottom_height, 0),
        (
            bottom_start,
            right_start,
            bottom_height,
            right_width,
            output_height - bottom_height,
            output_width - right_width,
        ),
    ]
    layers = []
    for source_row, source_col, height, width, target_row, target_col in placements:
        layer = [[background_color for _ in range(output_width)] for _ in range(output_height)]
        for dr in range(height):
            for dc in range(width):
                layer[target_row + dr][target_col + dc] = grid[source_row + dr][source_col + dc]
        layers.append(layer)

    return _overlay_regions(
        layers,
        background_color=background_color,
        overlay=overlay,
        output_color=output_color,
    )


def _overlay_regions(
    regions,
    background_color=0,
    ignored_colors=None,
    overlay="intersection",
    output_color=None,
):
    height = len(regions[0])
    width = len(regions[0][0])
    if any(len(region) != height or len(region[0]) != width for region in regions):
        raise ValueError("region overlay requires equal-size regions")

    output = [[background_color for _ in range(width)] for _ in range(height)]
    ignored = ignored_colors or {background_color}
    for row in range(height):
        for col in range(width):
            values = [region[row][col] for region in regions]
            foreground = [value for value in values if value not in ignored]
            if overlay == "intersection":
                if len(foreground) == len(regions):
                    output[row][col] = output_color if output_color is not None else foreground[-1]
            elif overlay == "union":
                if foreground:
                    output[row][col] = output_color if output_color is not None else foreground[-1]
            elif overlay in {"priority_union", "first_non_background"}:
                if foreground:
                    output[row][col] = output_color if output_color is not None else foreground[0]
            elif overlay in {"symmetric_difference", "xor"}:
                if 0 < len(foreground) < len(regions):
                    output[row][col] = output_color if output_color is not None else foreground[-1]
            elif overlay == "background_intersection":
                if not foreground:
                    output[row][col] = output_color
            else:
                raise ValueError(f"unsupported separator overlay mode: {overlay}")
    return output


def _equal_split_regions(grid, split_axis="auto"):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if split_axis == "horizontal" or (split_axis == "auto" and rows % 2 == 0 and cols % 2 != 0):
        if rows % 2 != 0:
            raise ValueError("horizontal equal split requires an even row count")
        mid = rows // 2
        return [
            [row[:] for row in grid[:mid]],
            [row[:] for row in grid[mid:]],
        ]
    if split_axis == "vertical" or (split_axis == "auto" and cols % 2 == 0 and rows % 2 != 0):
        if cols % 2 != 0:
            raise ValueError("vertical equal split requires an even column count")
        mid = cols // 2
        return [
            [row[:mid] for row in grid],
            [row[mid:] for row in grid],
        ]
    if split_axis == "auto":
        raise ValueError("equal split overlay requires exactly one even dimension or explicit split_axis")
    raise ValueError(f"unsupported equal split axis: {split_axis}")


def _equal_stack_regions(grid, split_axis="auto", split_count=3):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if split_count < 2:
        raise ValueError("equal stack overlay requires at least two regions")

    horizontal_possible = rows % split_count == 0
    vertical_possible = cols % split_count == 0
    if split_axis == "auto":
        if horizontal_possible == vertical_possible:
            raise ValueError("equal stack overlay requires exactly one compatible split axis")
        split_axis = "horizontal" if horizontal_possible else "vertical"

    if split_axis == "horizontal":
        if not horizontal_possible:
            raise ValueError("horizontal equal stack requires row count divisible by split_count")
        height = rows // split_count
        return [
            [source_row[:] for source_row in grid[index * height:(index + 1) * height]]
            for index in range(split_count)
        ]

    if split_axis == "vertical":
        if not vertical_possible:
            raise ValueError("vertical equal stack requires column count divisible by split_count")
        width = cols // split_count
        return [
            [source_row[index * width:(index + 1) * width] for source_row in grid]
            for index in range(split_count)
        ]

    raise ValueError(f"unsupported equal stack axis: {split_axis}")


def _reorder_regions_by_priority(regions, priority_order):
    if priority_order is None:
        return regions
    order = [int(index) for index in priority_order]
    if sorted(order) != list(range(len(regions))):
        raise ValueError("priority_order must be a permutation of equal-stack region indices")
    return [regions[index] for index in order]


def _colored_components(grid, background_color=0, connectivity=4):
    if not grid or not grid[0]:
        return []

    rows = len(grid)
    cols = len(grid[0])
    if connectivity == 8:
        neighbors = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ]
    elif connectivity == 4:
        neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    else:
        raise ValueError("colored component overlay connectivity must be 4 or 8")

    visited = set()
    components = []
    for row in range(rows):
        for col in range(cols):
            color = grid[row][col]
            if color == background_color or (row, col) in visited:
                continue
            stack = [(row, col)]
            visited.add((row, col))
            pixels = []
            while stack:
                current_row, current_col = stack.pop()
                pixels.append((current_row, current_col, color))
                for delta_row, delta_col in neighbors:
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


def _crop_component_to_bbox(component, background_color=0):
    min_row = min(row for row, _, _ in component)
    max_row = max(row for row, _, _ in component)
    min_col = min(col for _, col, _ in component)
    max_col = max(col for _, col, _ in component)
    crop = [
        [background_color for _ in range(max_col - min_col + 1)]
        for _ in range(max_row - min_row + 1)
    ]
    for row, col, color in component:
        crop[row - min_row][col - min_col] = color
    return crop


def _component_bbox_overlay(
    grid,
    background_color=0,
    overlay="minimal_full_union",
    connectivity=4,
):
    if overlay != "minimal_full_union":
        raise ValueError(f"unsupported component bbox overlay mode: {overlay}")

    components = _colored_components(
        grid,
        background_color=background_color,
        connectivity=connectivity,
    )
    if len(components) != 2:
        raise ValueError("component bbox overlay requires exactly two colored components")

    crops = [_crop_component_to_bbox(component, background_color) for component in components]
    max_height = max(len(crop) for crop in crops)
    max_width = max(len(crop[0]) for crop in crops)
    if max_height > 6 or max_width > 6:
        raise ValueError("component bbox overlay is bounded to small component crops")

    max_candidate_height = min(sum(len(crop) for crop in crops), max_height + 3)
    max_candidate_width = min(sum(len(crop[0]) for crop in crops), max_width + 3)
    best_output = None
    best_key = None

    def placement_options(height, width, crop):
        return [
            (row, col)
            for row in range(height - len(crop) + 1)
            for col in range(width - len(crop[0]) + 1)
        ]

    for height in range(max_height, max_candidate_height + 1):
        for width in range(max_width, max_candidate_width + 1):
            options = [
                placement_options(height, width, crop)
                for crop in crops
            ]
            for first_placement in options[0]:
                for second_placement in options[1]:
                    output = [
                        [background_color for _ in range(width)]
                        for _ in range(height)
                    ]
                    conflict = False
                    for crop, (target_row, target_col) in zip(crops, (first_placement, second_placement)):
                        for row_index, row in enumerate(crop):
                            for col_index, color in enumerate(row):
                                if color == background_color:
                                    continue
                                output_row = target_row + row_index
                                output_col = target_col + col_index
                                previous = output[output_row][output_col]
                                if previous != background_color and previous != color:
                                    conflict = True
                                    break
                                output[output_row][output_col] = color
                            if conflict:
                                break
                        if conflict:
                            break
                    if conflict:
                        continue
                    if any(color == background_color for row in output for color in row):
                        continue
                    key = (height * width, height, width, first_placement, second_placement)
                    if best_key is None or key < best_key:
                        best_key = key
                        best_output = output

    if best_output is None:
        raise ValueError("component bbox overlay found no compact full union")
    return best_output


def overlay_grid_based(
    grid,
    fold="marker_components",
    overlay="align_marker",
    marker_color=5,
    separator_color=5,
    background_color=0,
    connectivity=8,
    output_color=None,
    split_axis="auto",
    split_count=2,
    priority_order=None,
):
    """
    DSL-level overlay operation.

    `fold` chooses how the input is decomposed; `overlay` chooses how the
    decomposed pieces are recombined.  Keeping these arguments explicit makes
    output programs report the actual abstraction instead of hiding overlay
    inside an unrelated transform.
    """
    if fold in {"marker_components", "mcccg_extracts"}:
        if overlay not in {"align_marker", "marker_anchor"}:
            raise ValueError(f"unsupported marker component overlay mode: {overlay}")
        return _marker_component_overlay(
            grid,
            marker_color=marker_color,
            background_color=background_color,
            connectivity=connectivity,
        )

    if fold in {"separator_regions", "separator"}:
        return _separator_region_overlay(
            grid,
            separator_color=separator_color,
            background_color=background_color,
            overlay=overlay,
            output_color=output_color,
        )

    if fold == "separator_quadrants":
        return _separator_quadrant_overlay(
            grid,
            separator_color=separator_color,
            background_color=background_color,
            overlay=overlay,
            output_color=output_color,
        )

    if fold == "quadrants":
        return _quadrant_overlay(
            grid,
            background_color=background_color,
            overlay=overlay,
            output_color=output_color,
        )

    if fold == "separator_mirror_regions":
        return _separator_mirror_region_overlay(
            grid,
            separator_color=separator_color,
            background_color=background_color,
            overlay=overlay,
            output_color=output_color,
        )

    if fold == "corner_regions":
        return _corner_region_overlay(
            grid,
            background_color=background_color,
            overlay=overlay,
            output_color=output_color,
        )

    if fold == "equal_split":
        regions = _equal_split_regions(grid, split_axis=split_axis)
        return _overlay_regions(
            regions,
            background_color=background_color,
            overlay=overlay,
            output_color=output_color,
        )

    if fold == "equal_stack":
        regions = _equal_stack_regions(
            grid,
            split_axis=split_axis,
            split_count=split_count,
        )
        if overlay in {"priority_union", "first_non_background"}:
            regions = _reorder_regions_by_priority(regions, priority_order)
        return _overlay_regions(
            regions,
            background_color=background_color,
            overlay=overlay,
            output_color=output_color,
        )

    if fold in {"component_bboxes", "colored_component_bboxes"}:
        return _component_bbox_overlay(
            grid,
            background_color=background_color,
            overlay=overlay,
            connectivity=connectivity,
        )

    raise ValueError(f"unsupported overlay fold: {fold}")

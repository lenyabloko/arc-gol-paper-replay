import copy
from statistics import median


_SPLIT_MARKER_MAX_SEARCH_BRANCHES = 200_000


def _positions(grid, color):
    return [
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value == color
    ]


def _bbox(points):
    if not points:
        raise ValueError("Cannot compute bbox of empty point set")
    rows = [row for row, _ in points]
    cols = [col for _, col in points]
    return min(rows), max(rows), min(cols), max(cols)


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
            components.append({
                "pixels": pixels,
                "bbox": _bbox(pixels),
            })
    return components


def _dominant_color(grid):
    counts = {}
    for row in grid:
        for value in row:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        raise ValueError("Cannot infer dominant color of empty grid")
    return max(counts, key=counts.get)


def _multicolor_components(grid, background_color):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    visited = set()
    components = []
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] == background_color or (row, col) in visited:
                continue
            stack = [(row, col)]
            visited.add((row, col))
            pixels = []
            while stack:
                current_row, current_col = stack.pop()
                pixels.append((current_row, current_col, grid[current_row][current_col]))
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
                        if grid[next_row][next_col] == background_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
            components.append(pixels)
    return components


def _split_marker_template_overlay(grid):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if rows == 0 or cols == 0:
        raise ValueError("split_marker_template_overlay requires a non-empty grid")
    if any(len(row) != cols for row in grid):
        raise ValueError("split_marker_template_overlay requires a rectangular grid")

    split_candidates = []
    if cols % 2 == 0:
        half_cols = cols // 2
        split_candidates.append((
            [row[:half_cols] for row in grid],
            [row[half_cols:] for row in grid],
        ))
    if rows % 2 == 0:
        half_rows = rows // 2
        split_candidates.append((
            [row[:] for row in grid[:half_rows]],
            [row[:] for row in grid[half_rows:]],
        ))

    def translated_match(source_points, target_points):
        if len(source_points) != len(target_points) or not source_points:
            return None
        source_sorted = sorted(source_points)
        target_sorted = sorted(target_points)
        delta_row = target_sorted[0][0] - source_sorted[0][0]
        delta_col = target_sorted[0][1] - source_sorted[0][1]
        if {
            (row + delta_row, col + delta_col)
            for row, col in source_points
        } != set(target_points):
            return None
        return delta_row, delta_col

    outputs = []
    for first, second in split_candidates:
        for source, target in ((first, second), (second, first)):
            source_bg = _dominant_color(source)
            target_bg = _dominant_color(target)
            target_color_points = {}
            for row, values in enumerate(target):
                for col, value in enumerate(values):
                    if value == target_bg:
                        continue
                    target_color_points.setdefault(value, []).append((row, col))
            if not target_color_points:
                continue

            components = _multicolor_components(source, source_bg)
            candidate_lists = []
            for component in components:
                component_colors = sorted({value for _, _, value in component})
                candidate_placements = []
                for marker_color in component_colors:
                    if marker_color not in target_color_points:
                        continue
                    source_points = [
                        (row, col)
                        for row, col, value in component
                        if value == marker_color
                    ]
                    target_set = set(target_color_points[marker_color])
                    source_sorted = sorted(source_points)
                    for target_anchor in sorted(target_set):
                        delta_row = target_anchor[0] - source_sorted[0][0]
                        delta_col = target_anchor[1] - source_sorted[0][1]
                        translated = {
                            (row + delta_row, col + delta_col)
                            for row, col in source_points
                        }
                        if translated <= target_set:
                            candidate_placements.append((
                                marker_color,
                                (delta_row, delta_col),
                                frozenset((row, col, marker_color) for row, col in translated),
                            ))
                unique_component_candidates = []
                seen_component_candidates = set()
                for placement in candidate_placements:
                    key = (placement[0], placement[1], placement[2])
                    if key in seen_component_candidates:
                        continue
                    seen_component_candidates.add(key)
                    unique_component_candidates.append(placement)
                if unique_component_candidates:
                    candidate_lists.append((component, unique_component_candidates))

            search_space = 1
            too_many_alignments = False
            for _, placements in candidate_lists:
                search_space *= len(placements) + 1
                if search_space > _SPLIT_MARKER_MAX_SEARCH_BRANCHES:
                    too_many_alignments = True
                    break
            if too_many_alignments:
                continue

            base_output = [[target_bg for _ in row] for row in target]
            expected_markers = {
                (row, col, value)
                for value, points in target_color_points.items()
                for row, col in points
            }
            if not candidate_lists:
                continue

            suffix_marker_coverage = [set() for _ in range(len(candidate_lists) + 1)]
            for index in range(len(candidate_lists) - 1, -1, -1):
                suffix_marker_coverage[index] = set(suffix_marker_coverage[index + 1])
                for placement in candidate_lists[index][1]:
                    suffix_marker_coverage[index].update(placement[2])

            def place_component(current_output, component, placement):
                marker_color, (delta_row, delta_col), covered = placement
                next_output = [row[:] for row in current_output]
                for row, col, value in component:
                    out_row = row + delta_row
                    out_col = col + delta_col
                    if not (0 <= out_row < len(next_output) and 0 <= out_col < len(next_output[0])):
                        return None
                    current = next_output[out_row][out_col]
                    if current not in (target_bg, value):
                        return None
                    next_output[out_row][out_col] = value
                return next_output, covered

            def search(index, current_output, covered_markers, placed_count):
                if not expected_markers <= covered_markers | suffix_marker_coverage[index]:
                    return
                if index == len(candidate_lists):
                    if placed_count and expected_markers <= covered_markers:
                        outputs.append(current_output)
                    return
                component, placements = candidate_lists[index]
                search(index + 1, current_output, covered_markers, placed_count)
                for placement in placements:
                    placement_covered = set(placement[2])
                    if covered_markers & placement_covered:
                        continue
                    placed_result = place_component(current_output, component, placement)
                    if placed_result is None:
                        continue
                    next_output, covered = placed_result
                    search(
                        index + 1,
                        next_output,
                        covered_markers | set(covered),
                        placed_count + 1,
                    )

            search(0, base_output, set(), 0)

    unique = []
    seen = set()
    for output in outputs:
        key = tuple(tuple(row) for row in output)
        if key in seen:
            continue
        seen.add(key)
        unique.append(output)
    if len(unique) != 1:
        raise ValueError("split_marker_template_overlay requires a unique split/template alignment")
    return unique[0]


def _marker_template_overlay_output(source, target):
    source_bg = _dominant_color(source)
    target_bg = _dominant_color(target)
    target_color_points = {}
    for row, values in enumerate(target):
        for col, value in enumerate(values):
            if value == target_bg:
                continue
            target_color_points.setdefault(value, []).append((row, col))
    if not target_color_points:
        raise ValueError("Target field requires at least one marker")

    components = _multicolor_components(source, source_bg)
    candidate_lists = []
    for component in components:
        component_colors = sorted({value for _, _, value in component})
        candidate_placements = []
        for marker_color in component_colors:
            if marker_color not in target_color_points:
                continue
            source_points = [
                (row, col)
                for row, col, value in component
                if value == marker_color
            ]
            target_set = set(target_color_points[marker_color])
            source_sorted = sorted(source_points)
            for target_anchor in sorted(target_set):
                delta_row = target_anchor[0] - source_sorted[0][0]
                delta_col = target_anchor[1] - source_sorted[0][1]
                translated = {
                    (row + delta_row, col + delta_col)
                    for row, col in source_points
                }
                if translated <= target_set:
                    candidate_placements.append((
                        marker_color,
                        (delta_row, delta_col),
                        frozenset((row, col, marker_color) for row, col in translated),
                    ))
        unique_component_candidates = []
        seen_component_candidates = set()
        for placement in candidate_placements:
            key = (placement[0], placement[1], placement[2])
            if key in seen_component_candidates:
                continue
            seen_component_candidates.add(key)
            unique_component_candidates.append(placement)
        if unique_component_candidates:
            candidate_lists.append((component, unique_component_candidates))

    search_space = 1
    for _, placements in candidate_lists:
        search_space *= len(placements) + 1
        if search_space > _SPLIT_MARKER_MAX_SEARCH_BRANCHES:
            raise ValueError("Too many marker-template alignments")
    if not candidate_lists:
        raise ValueError("No source component can cover target markers")

    base_output = [[target_bg for _ in row] for row in target]
    expected_markers = {
        (row, col, value)
        for value, points in target_color_points.items()
        for row, col in points
    }
    suffix_marker_coverage = [set() for _ in range(len(candidate_lists) + 1)]
    for index in range(len(candidate_lists) - 1, -1, -1):
        suffix_marker_coverage[index] = set(suffix_marker_coverage[index + 1])
        for placement in candidate_lists[index][1]:
            suffix_marker_coverage[index].update(placement[2])

    outputs = []

    def place_component(current_output, component, placement):
        _, (delta_row, delta_col), covered = placement
        next_output = [row[:] for row in current_output]
        for row, col, value in component:
            out_row = row + delta_row
            out_col = col + delta_col
            if not (0 <= out_row < len(next_output) and 0 <= out_col < len(next_output[0])):
                return None
            current = next_output[out_row][out_col]
            if current not in (target_bg, value):
                return None
            next_output[out_row][out_col] = value
        return next_output, covered

    def search(index, current_output, covered_markers, placed_count):
        if not expected_markers <= covered_markers | suffix_marker_coverage[index]:
            return
        if index == len(candidate_lists):
            if placed_count and expected_markers <= covered_markers:
                outputs.append(current_output)
            return
        component, placements = candidate_lists[index]
        search(index + 1, current_output, covered_markers, placed_count)
        for placement in placements:
            placement_covered = set(placement[2])
            if covered_markers & placement_covered:
                continue
            placed_result = place_component(current_output, component, placement)
            if placed_result is None:
                continue
            next_output, covered = placed_result
            search(
                index + 1,
                next_output,
                covered_markers | set(covered),
                placed_count + 1,
            )

    search(0, base_output, set(), 0)
    unique = []
    seen = set()
    for output in outputs:
        key = tuple(tuple(row) for row in output)
        if key in seen:
            continue
        seen.add(key)
        unique.append(output)
    if len(unique) != 1:
        raise ValueError("marker-template overlay requires a unique alignment")
    return unique[0]


def _dominant_field_components(grid):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if rows == 0 or cols == 0 or any(len(row) != cols for row in grid):
        raise ValueError("field overlay requires a rectangular grid")
    surround = _dominant_color(grid)
    visited = set()
    fields = []
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] == surround or (row, col) in visited:
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
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if (next_row, next_col) in visited:
                        continue
                    if grid[next_row][next_col] == surround:
                        continue
                    visited.add((next_row, next_col))
                    stack.append((next_row, next_col))
            min_row, max_row, min_col, max_col = _bbox(cells)
            crop = [
                values[min_col:max_col + 1]
                for values in grid[min_row:max_row + 1]
            ]
            field_bg = _dominant_color(crop)
            marker_count = sum(
                1
                for values in crop
                for value in values
                if value != field_bg
            )
            fields.append({
                "bbox": (min_row, max_row, min_col, max_col),
                "grid": crop,
                "background": field_bg,
                "marker_count": marker_count,
            })
    return fields


def _field_marker_template_overlay(grid):
    fields = _dominant_field_components(grid)
    outputs = []
    for source in fields:
        for target in fields:
            if source is target:
                continue
            if source["background"] != target["background"]:
                continue
            if source["marker_count"] <= target["marker_count"]:
                continue
            try:
                outputs.append(_marker_template_overlay_output(source["grid"], target["grid"]))
            except ValueError:
                continue

    unique = []
    seen = set()
    for output in outputs:
        key = tuple(tuple(row) for row in output)
        if key in seen:
            continue
        seen.add(key)
        unique.append(output)
    if len(unique) != 1:
        raise ValueError("field marker-template overlay requires a unique source/target field")
    return unique[0]


def _move_color_pixels(grid, object_color, delta_row, delta_col, background_color=0):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    transformed = copy.deepcopy(grid)
    object_pixels = _positions(grid, object_color)
    if not object_pixels:
        raise ValueError("No object pixels found")

    for row, col in object_pixels:
        transformed[row][col] = background_color
    for row, col in object_pixels:
        new_row = row + delta_row
        new_col = col + delta_col
        if not (0 <= new_row < rows and 0 <= new_col < cols):
            raise ValueError("Moved object leaves grid")
        transformed[new_row][new_col] = object_color
    return transformed


def _center_object_in_frame(grid, object_color=2, guide_color=3, background_color=0):
    """
    Translate an object so its bbox is centered in the guide-color frame bbox.
    """
    object_pixels = _positions(grid, object_color)
    guide_pixels = _positions(grid, guide_color)
    if not object_pixels or len(guide_pixels) < 2:
        raise ValueError("Center-in-frame requires object and guide pixels")

    obj_min_row, obj_max_row, obj_min_col, obj_max_col = _bbox(object_pixels)
    guide_min_row, guide_max_row, guide_min_col, guide_max_col = _bbox(guide_pixels)

    obj_row_span = obj_max_row - obj_min_row
    obj_col_span = obj_max_col - obj_min_col
    target_min_row = (guide_min_row + guide_max_row - obj_row_span) // 2
    target_min_col = (guide_min_col + guide_max_col - obj_col_span) // 2

    return _move_color_pixels(
        grid,
        object_color,
        target_min_row - obj_min_row,
        target_min_col - obj_min_col,
        background_color=background_color,
    )


def _dominant_guide_line(guide_pixels):
    rows = {}
    cols = {}
    for row, col in guide_pixels:
        rows.setdefault(row, []).append(col)
        cols.setdefault(col, []).append(row)
    best_row, row_values = max(rows.items(), key=lambda item: (len(item[1]), -item[0]))
    best_col, col_values = max(cols.items(), key=lambda item: (len(item[1]), -item[0]))
    if len(row_values) >= len(col_values):
        return "horizontal", best_row, sorted(row_values)
    return "vertical", best_col, sorted(col_values)


def _guide_spacing(values):
    diffs = [
        right - left
        for left, right in zip(values, values[1:])
        if right > left
    ]
    if not diffs:
        raise ValueError("Guide line has no spacing")
    return int(median(diffs))


def _move_object_along_guide(grid, object_color=2, guide_color=3, background_color=0):
    """
    Move object pixels one guide-lattice step along the dominant guide line.

    The direction is toward the center/continuation of the guide line. Ties use
    the positive direction, matching the ARC convention in the motivating tasks.
    """
    object_pixels = _positions(grid, object_color)
    guide_pixels = _positions(grid, guide_color)
    if not object_pixels or len(guide_pixels) < 2:
        raise ValueError("Guide placement requires object and guide pixels")

    axis, _, coordinates = _dominant_guide_line(guide_pixels)
    spacing = _guide_spacing(coordinates)

    if axis == "horizontal":
        object_center = sum(col for _, col in object_pixels) / len(object_pixels)
        guide_center = (min(coordinates) + max(coordinates)) / 2
        direction = 1 if object_center <= guide_center else -1
        return _move_color_pixels(
            grid,
            object_color,
            0,
            direction * spacing,
            background_color=background_color,
        )

    object_center = sum(row for row, _ in object_pixels) / len(object_pixels)
    guide_center = (min(coordinates) + max(coordinates)) / 2
    direction = 1 if object_center <= guide_center else -1
    return _move_color_pixels(
        grid,
        object_color,
        direction * spacing,
        0,
        background_color=background_color,
    )


def _dominant_guide_axis(guide_pixels):
    row_counts = {}
    col_counts = {}
    for row, col in guide_pixels:
        row_counts[row] = row_counts.get(row, 0) + 1
        col_counts[col] = col_counts.get(col, 0) + 1
    max_row_count = max(row_counts.values())
    max_col_count = max(col_counts.values())
    if max_row_count >= max_col_count:
        edge_rows = sorted(row for row, count in row_counts.items() if count == max_row_count)
        if len(edge_rows) < 2:
            raise ValueError("Outward reflection requires two guide rows")
        return "vertical", edge_rows[0], edge_rows[-1]
    edge_cols = sorted(col for col, count in col_counts.items() if count == max_col_count)
    if len(edge_cols) < 2:
        raise ValueError("Outward reflection requires two guide columns")
    return "horizontal", edge_cols[0], edge_cols[-1]


def _reflect_inner_objects_outward(grid, object_color=5, guide_color=2, background_color=0):
    """
    Reflect compact object-color components from inside a guide-color field to
    the outside of the field.

    The guide is detected at image level. Its dominant repeated edge direction
    determines the active axis: long guide rows imply top/bottom reflection;
    long guide columns imply left/right reflection. This captures tasks where a
    compact inner color field is re-expressed outward from a more compact
    guide/frame color field, with the inward/outward order reversed.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if any(len(row) != cols for row in grid):
        raise ValueError("Outward reflection requires a rectangular grid")

    guide_pixels = _positions(grid, guide_color)
    components = _same_color_components(grid, object_color)
    if len(guide_pixels) < 2 or not components:
        raise ValueError("Outward reflection requires guide and object pixels")

    guide_min_row, guide_max_row, guide_min_col, guide_max_col = _bbox(guide_pixels)
    axis, lower_edge, upper_edge = _dominant_guide_axis(guide_pixels)
    center = (lower_edge + upper_edge) / 2

    transformed = copy.deepcopy(grid)
    for component in components:
        min_row, max_row, min_col, max_col = component["bbox"]
        if not (
            guide_min_row <= min_row <= max_row <= guide_max_row
            and guide_min_col <= min_col <= max_col <= guide_max_col
        ):
            raise ValueError("Object component is not inside guide field")
        for row, col in component["pixels"]:
            transformed[row][col] = background_color

    for component in components:
        min_row, max_row, min_col, max_col = component["bbox"]
        if axis == "vertical":
            component_center = (min_row + max_row) / 2
            edge = lower_edge if component_center <= center else upper_edge
            reflected_pixels = [
                (2 * edge - row, col)
                for row, col in component["pixels"]
            ]
        else:
            component_center = (min_col + max_col) / 2
            edge = lower_edge if component_center <= center else upper_edge
            reflected_pixels = [
                (row, 2 * edge - col)
                for row, col in component["pixels"]
            ]

        for row, col in reflected_pixels:
            if not (0 <= row < rows and 0 <= col < cols):
                raise ValueError("Reflected object leaves grid")
            if transformed[row][col] not in (background_color, object_color):
                raise ValueError("Reflected object collides with non-background")
            transformed[row][col] = object_color

    return transformed


def _project_markers_to_guide_line(
    grid,
    object_color=1,
    guide_color=5,
    background_color=0,
):
    """
    Project sparse marker pixels onto the dominant same-color guide line.

    Horizontal guide lines keep marker columns and replace the guide-line cell
    at that column.  Vertical guide lines keep marker rows and replace the
    guide-line cell at that row.  Original marker pixels are cleared.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if any(len(row) != cols for row in grid):
        raise ValueError("Guide-line projection requires a rectangular grid")

    marker_pixels = _positions(grid, object_color)
    guide_pixels = _positions(grid, guide_color)
    if not marker_pixels or len(guide_pixels) < 2:
        raise ValueError("Guide-line projection requires markers and guide pixels")

    row_counts = {}
    col_counts = {}
    for row, col in guide_pixels:
        row_counts[row] = row_counts.get(row, 0) + 1
        col_counts[col] = col_counts.get(col, 0) + 1

    best_row, best_row_count = max(row_counts.items(), key=lambda item: (item[1], item[0]))
    best_col, best_col_count = max(col_counts.items(), key=lambda item: (item[1], item[0]))

    transformed = copy.deepcopy(grid)
    for row, col in marker_pixels:
        transformed[row][col] = background_color

    if best_row_count >= best_col_count:
        for _, col in marker_pixels:
            if not (0 <= col < cols):
                raise ValueError("Projected marker leaves grid")
            transformed[best_row][col] = object_color
        return transformed

    for row, _ in marker_pixels:
        if not (0 <= row < rows):
            raise ValueError("Projected marker leaves grid")
        transformed[row][best_col] = object_color
    return transformed


def _reflect_object_by_guide_orientation(
    grid,
    object_color=8,
    guide_color=4,
    background_color=0,
):
    """
    Copy an object by reflecting it across the side indicated by a guide shape.

    The guide is treated as a directional marker.  For a horizontal guide bar,
    a top protrusion left/right of the bar center selects the side of the
    object bbox to reflect across.  The original object is preserved.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if any(len(row) != cols for row in grid):
        raise ValueError("Guide reflection requires a rectangular grid")

    object_pixels = _positions(grid, object_color)
    guide_pixels = _positions(grid, guide_color)
    if not object_pixels or len(guide_pixels) < 3:
        raise ValueError("Guide reflection requires object and guide pixels")

    obj_min_row, obj_max_row, obj_min_col, obj_max_col = _bbox(object_pixels)

    row_groups = {}
    col_groups = {}
    for row, col in guide_pixels:
        row_groups.setdefault(row, []).append(col)
        col_groups.setdefault(col, []).append(row)

    best_row, best_row_cols = max(row_groups.items(), key=lambda item: (len(item[1]), -item[0]))
    best_col, best_col_rows = max(col_groups.items(), key=lambda item: (len(item[1]), -item[0]))

    transformed = copy.deepcopy(grid)
    reflected = []
    if len(best_row_cols) >= len(best_col_rows):
        bar_center = (min(best_row_cols) + max(best_row_cols)) / 2
        off_bar = [(row, col) for row, col in guide_pixels if row != best_row]
        if not off_bar:
            raise ValueError("Guide reflection needs an off-bar direction marker")
        top = [(row, col) for row, col in off_bar if row < best_row]
        bottom = [(row, col) for row, col in off_bar if row > best_row]
        direction_pixels = top or bottom
        direction_center = sum(col for _, col in direction_pixels) / len(direction_pixels)
        side = "left" if direction_center < bar_center else "right"
        for row, col in object_pixels:
            new_col = 2 * obj_min_col - 1 - col if side == "left" else 2 * obj_max_col + 1 - col
            reflected.append((row, new_col))
    else:
        bar_center = (min(best_col_rows) + max(best_col_rows)) / 2
        off_bar = [(row, col) for row, col in guide_pixels if col != best_col]
        if not off_bar:
            raise ValueError("Guide reflection needs an off-bar direction marker")
        left = [(row, col) for row, col in off_bar if col < best_col]
        right = [(row, col) for row, col in off_bar if col > best_col]
        direction_pixels = left or right
        direction_center = sum(row for row, _ in direction_pixels) / len(direction_pixels)
        side = "up" if direction_center < bar_center else "down"
        for row, col in object_pixels:
            new_row = 2 * obj_min_row - 1 - row if side == "up" else 2 * obj_max_row + 1 - row
            reflected.append((new_row, col))

    for row, col in reflected:
        if not (0 <= row < rows and 0 <= col < cols):
            raise ValueError("Reflected object leaves grid")
        if transformed[row][col] not in (background_color, object_color):
            raise ValueError("Reflected object collides with non-background")
        transformed[row][col] = object_color
    return transformed


def _move_object_adjacent_to_guide_line(
    grid,
    object_color=3,
    guide_color=2,
    separator_color=8,
    background_color=0,
):
    """
    Move one object next to a dominant guide line and mark the far side.

    The object stays on its original side of the guide.  The guide line remains
    fixed; the object bbox is translated to touch it, and a separator line is
    placed immediately outside the moved object over the guide's span.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if any(len(row) != cols for row in grid):
        raise ValueError("Adjacent guide placement requires a rectangular grid")

    object_pixels = _positions(grid, object_color)
    guide_pixels = _positions(grid, guide_color)
    if not object_pixels or not guide_pixels:
        raise ValueError("Adjacent guide placement requires object and guide pixels")

    obj_min_row, obj_max_row, obj_min_col, obj_max_col = _bbox(object_pixels)
    guide_min_row, guide_max_row, guide_min_col, guide_max_col = _bbox(guide_pixels)

    guide_rows = {row for row, _ in guide_pixels}
    guide_cols = {col for _, col in guide_pixels}
    if len(guide_cols) == 1:
        guide_col = next(iter(guide_cols))
        if obj_max_col < guide_col:
            target_max_col = guide_col - 1
            target_min_col = target_max_col - (obj_max_col - obj_min_col)
            separator_col = target_min_col - 1
        elif obj_min_col > guide_col:
            target_min_col = guide_col + 1
            target_max_col = target_min_col + (obj_max_col - obj_min_col)
            separator_col = target_max_col + 1
        else:
            raise ValueError("Object already overlaps guide column")
        delta_row = guide_min_row - obj_min_row
        delta_col = target_min_col - obj_min_col
        separator_pixels = [(row, separator_col) for row in range(guide_min_row, guide_max_row + 1)]
    elif len(guide_rows) == 1:
        guide_row = next(iter(guide_rows))
        if obj_max_row < guide_row:
            target_max_row = guide_row - 1
            target_min_row = target_max_row - (obj_max_row - obj_min_row)
            separator_row = target_min_row - 1
        elif obj_min_row > guide_row:
            target_min_row = guide_row + 1
            target_max_row = target_min_row + (obj_max_row - obj_min_row)
            separator_row = target_max_row + 1
        else:
            raise ValueError("Object already overlaps guide row")
        delta_row = target_min_row - obj_min_row
        delta_col = guide_min_col - obj_min_col
        separator_pixels = [(separator_row, col) for col in range(guide_min_col, guide_max_col + 1)]
    else:
        raise ValueError("Guide must be a straight row or column")

    transformed = copy.deepcopy(grid)
    for row, col in object_pixels:
        transformed[row][col] = background_color

    moved_pixels = [(row + delta_row, col + delta_col) for row, col in object_pixels]
    for row, col in moved_pixels:
        if not (0 <= row < rows and 0 <= col < cols):
            raise ValueError("Moved object leaves grid")
        if transformed[row][col] not in (background_color, object_color):
            raise ValueError("Moved object collides with non-background")
        transformed[row][col] = object_color

    for row, col in separator_pixels:
        if not (0 <= row < rows and 0 <= col < cols):
            raise ValueError("Separator leaves grid")
        if transformed[row][col] != background_color:
            raise ValueError("Separator collides with non-background")
        transformed[row][col] = separator_color

    return transformed


def _align_all_colors_to_guide_top(
    grid,
    guide_color=1,
    background_color=0,
):
    """
    Vertically align every non-guide color shape to the guide color's top row.

    Each color is treated as one shape, preserving all of its pixels and
    columns.  Original non-guide pixels are cleared before moved shapes are
    written.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if any(len(row) != cols for row in grid):
        raise ValueError("Guide-top alignment requires a rectangular grid")

    guide_pixels = _positions(grid, guide_color)
    if not guide_pixels:
        raise ValueError("Guide-top alignment requires guide pixels")
    guide_top = min(row for row, _ in guide_pixels)

    colors = sorted({
        value
        for row in grid
        for value in row
        if value not in (background_color, guide_color)
    })
    if not colors:
        raise ValueError("Guide-top alignment requires movable colors")

    transformed = copy.deepcopy(grid)
    for color in colors:
        for row, col in _positions(grid, color):
            transformed[row][col] = background_color

    for color in colors:
        pixels = _positions(grid, color)
        color_top = min(row for row, _ in pixels)
        delta_row = guide_top - color_top
        for row, col in pixels:
            new_row = row + delta_row
            if not (0 <= new_row < rows):
                raise ValueError("Guide-top aligned object leaves grid")
            if transformed[new_row][col] not in (background_color, color):
                raise ValueError("Guide-top aligned object collides with non-background")
            transformed[new_row][col] = color
    return transformed


def _move_object_by_marker_count_diagonal(
    grid,
    object_color="non_guide_color",
    guide_color=5,
    background_color=0,
):
    """
    Move a full-row/full-column cross down-left by the number of guide markers.

    The guide is a compact count marker rather than a destination.  The object
    is represented by its two axes, so the output redraws a full cross at the
    shifted row/column instead of clipping individual source pixels.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if any(len(row) != cols for row in grid):
        raise ValueError("Marker-count diagonal move requires a rectangular grid")

    guide_pixels = _positions(grid, guide_color)
    if not guide_pixels:
        raise ValueError("Marker-count diagonal move requires guide markers")

    resolved_object_color = object_color
    if object_color in (None, "non_guide_color"):
        object_colors = sorted({
            value
            for row in grid
            for value in row
            if value not in (background_color, guide_color)
        })
        if len(object_colors) != 1:
            raise ValueError("Marker-count diagonal move requires one non-guide object color")
        resolved_object_color = object_colors[0]

    full_rows = [
        row
        for row in range(rows)
        if all(grid[row][col] == resolved_object_color for col in range(cols))
    ]
    full_cols = [
        col
        for col in range(cols)
        if all(grid[row][col] == resolved_object_color for row in range(rows))
    ]
    if len(full_rows) != 1 or len(full_cols) != 1:
        raise ValueError("Marker-count diagonal move requires one full cross")

    shift = len(guide_pixels)
    new_row = full_rows[0] + shift
    new_col = full_cols[0] - shift
    if not (0 <= new_row < rows and 0 <= new_col < cols):
        raise ValueError("Marker-count diagonal move leaves grid")

    transformed = [
        [background_color for _ in range(cols)]
        for _ in range(rows)
    ]
    for row in range(rows):
        transformed[row][new_col] = resolved_object_color
    for col in range(cols):
        transformed[new_row][col] = resolved_object_color
    return transformed


def _sort_horizontal_bars_right_aligned(grid, background_color=0):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if rows == 0 or cols == 0:
        raise ValueError("Horizontal bar sort requires a non-empty grid")
    if any(len(row) != cols for row in grid):
        raise ValueError("Horizontal bar sort requires a rectangular grid")

    bars = []
    for row_index, row in enumerate(grid):
        occupied = [col for col, value in enumerate(row) if value != background_color]
        if not occupied:
            continue
        values = {row[col] for col in occupied}
        if len(values) != 1:
            raise ValueError("Horizontal bar sort requires single-color bars")
        start = min(occupied)
        end = max(occupied)
        if occupied != list(range(start, end + 1)):
            raise ValueError("Horizontal bar sort requires contiguous bars")
        bar_color = next(iter(values))
        bars.append({
            "row": row_index,
            "color": bar_color,
            "length": end - start + 1,
        })

    if len(bars) < 2:
        raise ValueError("Horizontal bar sort requires at least two bars")
    if len({bar["length"] for bar in bars}) != len(bars):
        raise ValueError("Horizontal bar sort requires distinct bar lengths")

    output = [[background_color for _ in range(cols)] for _ in range(rows)]
    for output_row, bar in zip(
        range(rows - len(bars), rows),
        sorted(bars, key=lambda item: (item["length"], item["row"], item["color"])),
    ):
        for col in range(cols - bar["length"], cols):
            output[output_row][col] = bar["color"]
    return output


def placement_grid_based(
    grid,
    placement_type="center_object_in_frame",
    object_color=2,
    guide_color=3,
    separator_color=8,
    background_color=0,
):
    if placement_type == "sort_horizontal_bars_right_aligned":
        return _sort_horizontal_bars_right_aligned(
            grid,
            background_color=background_color,
        )
    if placement_type == "split_marker_template_overlay":
        return _split_marker_template_overlay(grid)
    if placement_type == "field_marker_template_overlay":
        return _field_marker_template_overlay(grid)
    if placement_type == "center_object_in_frame":
        return _center_object_in_frame(
            grid,
            object_color=object_color,
            guide_color=guide_color,
            background_color=background_color,
        )
    if placement_type == "move_object_along_guide":
        return _move_object_along_guide(
            grid,
            object_color=object_color,
            guide_color=guide_color,
            background_color=background_color,
        )
    if placement_type == "reflect_inner_objects_outward":
        return _reflect_inner_objects_outward(
            grid,
            object_color=object_color,
            guide_color=guide_color,
            background_color=background_color,
        )
    if placement_type == "project_markers_to_guide_line":
        return _project_markers_to_guide_line(
            grid,
            object_color=object_color,
            guide_color=guide_color,
            background_color=background_color,
        )
    if placement_type == "reflect_object_by_guide_orientation":
        return _reflect_object_by_guide_orientation(
            grid,
            object_color=object_color,
            guide_color=guide_color,
            background_color=background_color,
        )
    if placement_type == "move_object_adjacent_to_guide_line":
        return _move_object_adjacent_to_guide_line(
            grid,
            object_color=object_color,
            guide_color=guide_color,
            separator_color=separator_color,
            background_color=background_color,
        )
    if placement_type == "align_all_colors_to_guide_top":
        return _align_all_colors_to_guide_top(
            grid,
            guide_color=guide_color,
            background_color=background_color,
        )
    if placement_type == "move_object_by_marker_count_diagonal":
        return _move_object_by_marker_count_diagonal(
            grid,
            object_color=object_color,
            guide_color=guide_color,
            background_color=background_color,
        )
    raise ValueError(f"Unsupported placement type: {placement_type}")

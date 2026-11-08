from dsl_classifier_migration import classifier_action


def fill_grid_based(grid, object, color, color1, classifier_params=None):
    object, classifier_params = classifier_action("object", object, classifier_params)
    if object == "separator_lattice_background_component_size_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_lattice_background_component_size_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_lattice_background_component_size_fill requires a rectangular grid")

        small_component_color = color
        large_component_color = color1
        background_color = 0
        if small_component_color in (None, background_color):
            raise ValueError("separator_lattice_background_component_size_fill requires a non-background small component color")
        if large_component_color in (None, background_color):
            raise ValueError("separator_lattice_background_component_size_fill requires a non-background large component color")
        if small_component_color == large_component_color:
            raise ValueError("separator_lattice_background_component_size_fill requires distinct fill colors")

        non_background_counts = {}
        for row in grid:
            for value in row:
                if value != background_color:
                    non_background_counts[value] = non_background_counts.get(value, 0) + 1
        if not non_background_counts:
            raise ValueError("separator_lattice_background_component_size_fill requires a separator color")
        separator_color = max(
            sorted(non_background_counts),
            key=lambda value: non_background_counts[value],
        )

        row_threshold = max(2, int(cols * 0.5))
        col_threshold = max(2, int(rows * 0.5))
        separator_rows = [
            row
            for row in range(rows)
            if sum(1 for col in range(cols) if grid[row][col] == separator_color) >= row_threshold
        ]
        separator_cols = [
            col
            for col in range(cols)
            if sum(1 for row in range(rows) if grid[row][col] == separator_color) >= col_threshold
        ]
        if not separator_rows or not separator_cols:
            raise ValueError("separator_lattice_background_component_size_fill requires separator rows and columns")

        def spans(separators, limit):
            bounds = [-1] + sorted(separators) + [limit]
            result = []
            for index in range(len(bounds) - 1):
                start = bounds[index] + 1
                end = bounds[index + 1]
                if start < end:
                    result.append((start, end))
            return result

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        if not row_spans or not col_spans:
            raise ValueError("separator_lattice_background_component_size_fill found no lattice cells")

        row_heights = {end - start for start, end in row_spans}
        col_widths = {end - start for start, end in col_spans}
        if len(row_heights) != 1 or len(col_widths) != 1:
            raise ValueError("separator_lattice_background_component_size_fill requires uniform cell spans")
        unit_component_size = next(iter(row_heights)) * next(iter(col_widths))
        if unit_component_size <= 0:
            raise ValueError("separator_lattice_background_component_size_fill requires positive cell area")

        output = [row[:] for row in grid]
        visited = set()
        changed = False
        for start_row in range(rows):
            for start_col in range(cols):
                if grid[start_row][start_col] != background_color:
                    continue
                if (start_row, start_col) in visited:
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
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited:
                            continue
                        if grid[next_row][next_col] != background_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                fill_color = (
                    small_component_color
                    if len(pixels) == unit_component_size
                    else large_component_color
                )
                for row, col in pixels:
                    if output[row][col] != fill_color:
                        output[row][col] = fill_color
                        changed = True

        if not changed:
            raise ValueError("separator_lattice_background_component_size_fill made no changes")
        return output

    if object == "edge_anchor_orthogonal_bar_projection":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("edge_anchor_orthogonal_bar_projection requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("edge_anchor_orthogonal_bar_projection requires a rectangular grid")

        background_color = 0 if color in (None, 0) else color

        edge_anchors = []
        for row, edge_name in ((0, "top"), (rows - 1, "bottom")):
            edge_color = grid[row][0]
            if edge_color != background_color and all(grid[row][col] == edge_color for col in range(cols)):
                edge_anchors.append({
                    "axis": "horizontal",
                    "edge": edge_name,
                    "index": row,
                    "anchor_color": edge_color,
                })
        for col, edge_name in ((0, "left"), (cols - 1, "right")):
            edge_color = grid[0][col]
            if edge_color != background_color and all(grid[row][col] == edge_color for row in range(rows)):
                edge_anchors.append({
                    "axis": "vertical",
                    "edge": edge_name,
                    "index": col,
                    "anchor_color": edge_color,
                })

        if len(edge_anchors) != 1:
            raise ValueError("edge_anchor_orthogonal_bar_projection requires exactly one full-span edge anchor")

        anchor = edge_anchors[0]
        anchor_color = anchor["anchor_color"]

        visited = set()
        components = []
        for start_row in range(rows):
            for start_col in range(cols):
                value = grid[start_row][start_col]
                if value in (background_color, anchor_color):
                    continue
                if (start_row, start_col) in visited:
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
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited:
                            continue
                        if grid[next_row][next_col] != value:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                min_row = min(row for row, _ in pixels)
                max_row = max(row for row, _ in pixels)
                min_col = min(col for _, col in pixels)
                max_col = max(col for _, col in pixels)
                if anchor["axis"] == "horizontal":
                    if min_row != max_row:
                        raise ValueError("edge_anchor_orthogonal_bar_projection requires horizontal bars")
                    distance = (
                        min_row
                        if anchor["edge"] == "top"
                        else (rows - 1) - max_row
                    )
                else:
                    if min_col != max_col:
                        raise ValueError("edge_anchor_orthogonal_bar_projection requires vertical bars")
                    distance = (
                        min_col
                        if anchor["edge"] == "left"
                        else (cols - 1) - max_col
                    )
                if distance <= 0:
                    raise ValueError("edge_anchor_orthogonal_bar_projection found a bar on the anchor edge")
                components.append({
                    "color": value,
                    "min_row": min_row,
                    "max_row": max_row,
                    "min_col": min_col,
                    "max_col": max_col,
                    "distance": distance,
                })

        if not components:
            raise ValueError("edge_anchor_orthogonal_bar_projection requires source bars")

        output = [row[:] for row in grid]
        changed = False
        # Render farthest bars first.  Bars closer to the anchor overwrite them,
        # which matches the training evidence for overlapping projected lanes.
        components.sort(key=lambda component: component["distance"], reverse=True)
        for component in components:
            source_color = component["color"]
            if anchor["axis"] == "horizontal":
                cols_to_fill = range(component["min_col"], component["max_col"] + 1)
                if anchor["edge"] == "top":
                    rows_to_fill = range(1, component["max_row"] + 1)
                else:
                    rows_to_fill = range(component["min_row"], rows - 1)
                for row in rows_to_fill:
                    for col in cols_to_fill:
                        if output[row][col] != source_color:
                            output[row][col] = source_color
                            changed = True
            else:
                rows_to_fill = range(component["min_row"], component["max_row"] + 1)
                if anchor["edge"] == "left":
                    cols_to_fill = range(1, component["max_col"] + 1)
                else:
                    cols_to_fill = range(component["min_col"], cols - 1)
                for row in rows_to_fill:
                    for col in cols_to_fill:
                        if output[row][col] != source_color:
                            output[row][col] = source_color
                            changed = True

        if not changed:
            raise ValueError("edge_anchor_orthogonal_bar_projection made no changes")
        return output

    if object == "full_span_separator_projection":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("full_span_separator_projection requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("full_span_separator_projection requires a rectangular grid")

        source_recolor = color
        separator_color = color1
        background_color = 0
        if source_recolor in (None, background_color):
            raise ValueError("full_span_separator_projection requires a non-background source recolor")
        if separator_color in (None, background_color):
            raise ValueError("full_span_separator_projection requires a non-background separator color")

        full_lines = []
        for row in range(rows):
            line_color = grid[row][0]
            if line_color == background_color:
                continue
            if all(grid[row][col] == line_color for col in range(cols)):
                full_lines.append({
                    "axis": "horizontal",
                    "index": row,
                    "color": line_color,
                })
        for col in range(cols):
            line_color = grid[0][col]
            if line_color == background_color:
                continue
            if all(grid[row][col] == line_color for row in range(rows)):
                full_lines.append({
                    "axis": "vertical",
                    "index": col,
                    "color": line_color,
                })

        separator_lines = [
            line for line in full_lines
            if line["color"] == separator_color
        ]
        if not separator_lines:
            raise ValueError("full_span_separator_projection requires a full-span separator")

        def component_list(target_color):
            visited = set()
            components = []
            for start_row in range(rows):
                for start_col in range(cols):
                    if grid[start_row][start_col] != target_color:
                        continue
                    if (start_row, start_col) in visited:
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
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if (next_row, next_col) in visited:
                                continue
                            if grid[next_row][next_col] != target_color:
                                continue
                            visited.add((next_row, next_col))
                            stack.append((next_row, next_col))
                    min_row = min(row for row, _ in pixels)
                    max_row = max(row for row, _ in pixels)
                    min_col = min(col for _, col in pixels)
                    max_col = max(col for _, col in pixels)
                    components.append({
                        "pixels": pixels,
                        "min_row": min_row,
                        "max_row": max_row,
                        "min_col": min_col,
                        "max_col": max_col,
                    })
            return components

        def signed_side(value, separator_index):
            if value < separator_index:
                return -1
            if value > separator_index:
                return 1
            return 0

        def positions_on_side(candidate_color, axis, separator_index, side_sign, parallel_min, parallel_max):
            positions = []
            for row in range(rows):
                for col in range(cols):
                    if grid[row][col] != candidate_color:
                        continue
                    if axis == "horizontal":
                        if not (parallel_min <= col <= parallel_max):
                            continue
                        if signed_side(row, separator_index) != side_sign:
                            continue
                    else:
                        if not (parallel_min <= row <= parallel_max):
                            continue
                        if signed_side(col, separator_index) != side_sign:
                            continue
                    positions.append((row, col))
            return positions

        def render_candidate(axis, separator_index, terminal_index, terminal_color, source_color, source_components):
            output = [row[:] for row in grid]
            terminal_sign = signed_side(terminal_index, separator_index)
            source_sign = -terminal_sign
            changed = False

            for component in source_components:
                for row, col in component["pixels"]:
                    if output[row][col] != source_recolor:
                        output[row][col] = source_recolor
                        changed = True

                if axis == "horizontal":
                    parallel_min = component["min_col"]
                    parallel_max = component["max_col"]
                    if source_sign < 0:
                        source_rows = range(component["max_row"] + 1, separator_index)
                    else:
                        source_rows = range(separator_index + 1, component["min_row"])
                    for row in source_rows:
                        for col in range(parallel_min, parallel_max + 1):
                            if output[row][col] != source_color:
                                output[row][col] = source_color
                                changed = True

                    terminal_rows = (
                        range(separator_index + 1, rows)
                        if terminal_sign > 0
                        else range(separator_index - 1, -1, -1)
                    )
                    for row in terminal_rows:
                        for col in range(parallel_min, parallel_max + 1):
                            if output[row][col] != separator_color:
                                output[row][col] = separator_color
                                changed = True

                    terminal_positions = positions_on_side(
                        terminal_color,
                        axis,
                        separator_index,
                        terminal_sign,
                        parallel_min,
                        parallel_max,
                    )
                    if not terminal_positions:
                        raise ValueError("full_span_separator_projection found no terminal mask in lane")
                    if terminal_sign > 0:
                        shift = (rows - 1) - max(row for row, _ in terminal_positions)
                    else:
                        shift = 0 - min(row for row, _ in terminal_positions)
                    for row, col in terminal_positions:
                        target_row = row + shift
                        if 0 <= target_row < rows:
                            if output[target_row][col] != terminal_color:
                                output[target_row][col] = terminal_color
                                changed = True
                else:
                    parallel_min = component["min_row"]
                    parallel_max = component["max_row"]
                    if source_sign < 0:
                        source_cols = range(component["max_col"] + 1, separator_index)
                    else:
                        source_cols = range(separator_index + 1, component["min_col"])
                    for col in source_cols:
                        for row in range(parallel_min, parallel_max + 1):
                            if output[row][col] != source_color:
                                output[row][col] = source_color
                                changed = True

                    terminal_cols = (
                        range(separator_index + 1, cols)
                        if terminal_sign > 0
                        else range(separator_index - 1, -1, -1)
                    )
                    for col in terminal_cols:
                        for row in range(parallel_min, parallel_max + 1):
                            if output[row][col] != separator_color:
                                output[row][col] = separator_color
                                changed = True

                    terminal_positions = positions_on_side(
                        terminal_color,
                        axis,
                        separator_index,
                        terminal_sign,
                        parallel_min,
                        parallel_max,
                    )
                    if not terminal_positions:
                        raise ValueError("full_span_separator_projection found no terminal mask in lane")
                    if terminal_sign > 0:
                        shift = (cols - 1) - max(col for _, col in terminal_positions)
                    else:
                        shift = 0 - min(col for _, col in terminal_positions)
                    for row, col in terminal_positions:
                        target_col = col + shift
                        if 0 <= target_col < cols:
                            if output[row][target_col] != terminal_color:
                                output[row][target_col] = terminal_color
                                changed = True

            if not changed:
                raise ValueError("full_span_separator_projection made no changes")
            return output

        candidates = []
        for separator_line in separator_lines:
            axis = separator_line["axis"]
            separator_index = separator_line["index"]
            terminal_lines = [
                line for line in full_lines
                if line["axis"] == axis
                and line["index"] != separator_index
                and line["color"] not in (background_color, separator_color)
            ]
            for terminal_line in terminal_lines:
                terminal_color = terminal_line["color"]
                terminal_index = terminal_line["index"]
                terminal_sign = signed_side(terminal_index, separator_index)
                if terminal_sign == 0:
                    continue
                source_sign = -terminal_sign
                source_colors = set()
                invalid_extra_color = False
                for row in range(rows):
                    for col in range(cols):
                        value = grid[row][col]
                        if value in (background_color, separator_color, terminal_color):
                            continue
                        side_value = signed_side(
                            row if axis == "horizontal" else col,
                            separator_index,
                        )
                        if side_value == source_sign:
                            source_colors.add(value)
                        else:
                            invalid_extra_color = True
                            break
                    if invalid_extra_color:
                        break
                if invalid_extra_color or len(source_colors) != 1:
                    continue

                source_color = next(iter(source_colors))
                source_components = []
                for component in component_list(source_color):
                    if axis == "horizontal":
                        component_side = (
                            signed_side(component["min_row"], separator_index),
                            signed_side(component["max_row"], separator_index),
                        )
                    else:
                        component_side = (
                            signed_side(component["min_col"], separator_index),
                            signed_side(component["max_col"], separator_index),
                        )
                    if component_side != (source_sign, source_sign):
                        continue
                    source_components.append(component)
                if not source_components:
                    continue

                try:
                    candidate_grid = render_candidate(
                        axis,
                        separator_index,
                        terminal_index,
                        terminal_color,
                        source_color,
                        source_components,
                    )
                except ValueError:
                    continue
                source_pixel_count = sum(len(component["pixels"]) for component in source_components)
                candidates.append((
                    source_pixel_count,
                    len(source_components),
                    axis,
                    separator_index,
                    terminal_index,
                    candidate_grid,
                ))

        if not candidates:
            raise ValueError("full_span_separator_projection found no valid separator projection")
        candidates.sort(key=lambda item: (item[0], item[1], item[2], -abs(item[4] - item[3])))
        return candidates[-1][-1]

    if object == "border_components_and_recolor_singletons":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("border_components_and_recolor_singletons requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("border_components_and_recolor_singletons requires a rectangular grid")

        source_color = color
        border_color = color1
        background_color = 0
        if source_color in (None, background_color) or border_color in (None, background_color):
            raise ValueError("border_components_and_recolor_singletons requires source/border colors")

        visited = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != source_color or (row, col) in visited:
                    continue
                stack = [(row, col)]
                visited.add((row, col))
                pixels = []
                while stack:
                    current_row, current_col = stack.pop()
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
                        if grid[next_row][next_col] != source_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                components.append(pixels)
        if not components:
            raise ValueError("border_components_and_recolor_singletons found no source components")

        output = [row[:] for row in grid]
        changed = False
        for pixels in components:
            for row, col in pixels:
                for delta_row in (-1, 0, 1):
                    for delta_col in (-1, 0, 1):
                        if delta_row == 0 and delta_col == 0:
                            continue
                        next_row = row + delta_row
                        next_col = col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if output[next_row][next_col] == background_color:
                            output[next_row][next_col] = border_color
                            changed = True
            if len(pixels) == 1:
                row, col = pixels[0]
                output[row][col] = border_color
                changed = True
        if not changed:
            raise ValueError("border_components_and_recolor_singletons produced no change")
        return output

    if object == "shape_donor_swap":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("shape_donor_swap requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("shape_donor_swap requires a rectangular grid")

        background_color = 0 if color1 is None else color1

        def component_touches_edge(pixels):
            return any(
                row == 0 or row == rows - 1 or col == 0 or col == cols - 1
                for row, col in pixels
            )

        def normalized_shape(pixels):
            min_row = min(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            return tuple(sorted((row - min_row, col - min_col) for row, col in pixels))

        def component_bounds(pixels):
            return (
                min(row for row, _ in pixels),
                max(row for row, _ in pixels),
                min(col for _, col in pixels),
                max(col for _, col in pixels),
            )

        def centroid(pixels):
            return (
                sum(row for row, _ in pixels) / len(pixels),
                sum(col for _, col in pixels) / len(pixels),
            )

        visited = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                if (row, col) in visited:
                    continue
                component_color = grid[row][col]
                stack = [(row, col)]
                visited.add((row, col))
                pixels = []
                while stack:
                    current_row, current_col = stack.pop()
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
                        if grid[next_row][next_col] != component_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                components.append({
                    "color": component_color,
                    "pixels": tuple(sorted(pixels)),
                })

        targets = [
            component
            for component in components
            if component["color"] == background_color
            and not component_touches_edge(component["pixels"])
        ]
        donors_by_shape = {}
        for component in components:
            if component["color"] == background_color:
                continue
            donors_by_shape.setdefault(
                normalized_shape(component["pixels"]),
                [],
            ).append(component)

        output = [row[:] for row in grid]
        used_donors = set()
        changed = False
        for target in targets:
            target_shape = normalized_shape(target["pixels"])
            donor_candidates = [
                donor
                for donor in donors_by_shape.get(target_shape, [])
                if donor["pixels"] not in used_donors
            ]
            if not donor_candidates:
                continue
            target_centroid = centroid(target["pixels"])
            donor = min(
                donor_candidates,
                key=lambda candidate: (
                    (centroid(candidate["pixels"])[0] - target_centroid[0]) ** 2
                    + (centroid(candidate["pixels"])[1] - target_centroid[1]) ** 2,
                    component_bounds(candidate["pixels"]),
                ),
            )
            for row, col in target["pixels"]:
                output[row][col] = donor["color"]
            for row, col in donor["pixels"]:
                output[row][col] = background_color
            used_donors.add(donor["pixels"])
            changed = True

        if not changed:
            raise ValueError("shape_donor_swap found no same-shape donor/hole pairs")
        return output

    if object == "separator_cross_region_palette":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_cross_region_palette requires a non-empty grid")
        separator_color = color
        if separator_color in (None, 0):
            raise ValueError("separator_cross_region_palette requires a separator color")
        separator_rows = [
            row for row, values in enumerate(grid)
            if len(set(values)) == 1 and values[0] == separator_color
        ]
        separator_cols = [
            col for col in range(cols)
            if len({grid[row][col] for row in range(rows)}) == 1
            and grid[0][col] == separator_color
        ]
        if len(separator_rows) < 1 or len(separator_cols) < 1:
            raise ValueError("separator_cross_region_palette requires row/column separators")

        def spans(indices, limit):
            result = []
            start = 0
            for index in indices + [limit]:
                if start < index:
                    result.append((start, index))
                start = index + 1
            return result

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        fill_map = {
            (0, 1): 2,
            (1, 0): 4,
            (1, 1): 6,
            (1, 2): 3,
            (2, 1): 1,
        }
        output = [row[:] for row in grid]
        changed = False
        for (region_row, region_col), fill_color in fill_map.items():
            if region_row >= len(row_spans) or region_col >= len(col_spans):
                continue
            row_start, row_end = row_spans[region_row]
            col_start, col_end = col_spans[region_col]
            for row in range(row_start, row_end):
                for col in range(col_start, col_end):
                    if output[row][col] == 0:
                        output[row][col] = fill_color
                        changed = True
        if not changed:
            raise ValueError("separator_cross_region_palette produced no change")
        return output

    if object == "rectangle_border_fill_by_height_parity":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("rectangle_border_fill_by_height_parity requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("rectangle_border_fill_by_height_parity requires a rectangular grid")
        border_color = color
        background_color = 0 if color1 is None else color1
        if border_color in (None, background_color):
            raise ValueError("rectangle_border_fill_by_height_parity requires a border color")

        def component_pixels(start_row, start_col, visited):
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
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if (next_row, next_col) in visited:
                        continue
                    if grid[next_row][next_col] != border_color:
                        continue
                    visited.add((next_row, next_col))
                    stack.append((next_row, next_col))
            return pixels

        def is_exact_rectangle_border(pixels):
            min_row = min(row for row, _ in pixels)
            max_row = max(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            max_col = max(col for _, col in pixels)
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            if height < 3 or width < 3:
                return None
            border = {
                (row, col)
                for row in range(min_row, max_row + 1)
                for col in range(min_col, max_col + 1)
                if row in (min_row, max_row) or col in (min_col, max_col)
            }
            return (min_row, max_row, min_col, max_col) if set(pixels) == border else None

        output = [row[:] for row in grid]
        visited = set()
        changed = False
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != border_color or (row, col) in visited:
                    continue
                pixels = component_pixels(row, col, visited)
                bbox = is_exact_rectangle_border(pixels)
                if bbox is None:
                    continue
                min_row, max_row, min_col, max_col = bbox
                fill_color = 7 if (max_row - min_row + 1) % 2 == 1 else 2
                for fill_row in range(min_row + 1, max_row):
                    for fill_col in range(min_col + 1, max_col):
                        output[fill_row][fill_col] = fill_color
                        changed = True
        if not changed:
            raise ValueError("rectangle_border_fill_by_height_parity found no rectangle interiors")
        return output

    if object == "dominant_axis_line_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("dominant_axis_line_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("dominant_axis_line_fill requires a rectangular grid")

        def mode(values):
            counts = {}
            first_seen = {}
            for index, value in enumerate(values):
                counts[value] = counts.get(value, 0) + 1
                first_seen.setdefault(value, index)
            return sorted(counts, key=lambda value: (-counts[value], first_seen[value], value))[0], max(counts.values())

        row_modes = []
        row_score = 0
        for row in grid:
            value, count = mode(row)
            row_modes.append(value)
            row_score += count
        col_modes = []
        col_score = 0
        for col in range(cols):
            value, count = mode([grid[row][col] for row in range(rows)])
            col_modes.append(value)
            col_score += count
        if row_score == col_score:
            raise ValueError("dominant_axis_line_fill requires a dominant axis")
        if row_score > col_score:
            return [[row_modes[row] for _ in range(cols)] for row in range(rows)]
        return [[col_modes[col] for col in range(cols)] for _ in range(rows)]

    if object == "row_label_recolor_target_blocks":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("row_label_recolor_target_blocks requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("row_label_recolor_target_blocks requires a rectangular grid")
        target_color = color
        background_color = 0 if color1 is None else color1
        if target_color in (None, background_color):
            raise ValueError("row_label_recolor_target_blocks requires a target color")
        output = [row[:] for row in grid]
        changed = False
        for row_index, row in enumerate(grid):
            labels = [
                value
                for value in row
                if value not in (background_color, target_color)
            ]
            if not labels:
                continue
            row_label = labels[0]
            for col_index, value in enumerate(row):
                if value == target_color:
                    output[row_index][col_index] = row_label
                    changed = True
        if not changed:
            raise ValueError("row_label_recolor_target_blocks found no target blocks")
        return output

    if object == "solid_rectangle_role_recolor":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("solid_rectangle_role_recolor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("solid_rectangle_role_recolor requires a rectangular grid")
        target_color = color
        background_color = 0 if color1 is None else color1
        if target_color in (None, background_color):
            raise ValueError("solid_rectangle_role_recolor requires a target color")

        output = [row[:] for row in grid]
        visited = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != target_color or (row, col) in visited:
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
                        if (next_row, next_col) in visited or grid[next_row][next_col] != target_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                components.append(pixels)
        if not components:
            raise ValueError("solid_rectangle_role_recolor found no target rectangles")

        for pixels in components:
            min_row = min(row for row, _ in pixels)
            max_row = max(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            max_col = max(col for _, col in pixels)
            rectangle = {
                (row, col)
                for row in range(min_row, max_row + 1)
                for col in range(min_col, max_col + 1)
            }
            if set(pixels) != rectangle:
                raise ValueError("solid_rectangle_role_recolor requires solid rectangles")
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            if height < 2 or width < 2:
                raise ValueError("solid_rectangle_role_recolor requires rectangles at least 2x2")
            for row, col in pixels:
                on_top_or_bottom = row in (min_row, max_row)
                on_left_or_right = col in (min_col, max_col)
                if on_top_or_bottom and on_left_or_right:
                    output[row][col] = 1
                elif on_top_or_bottom or on_left_or_right:
                    output[row][col] = 4
                else:
                    output[row][col] = 2
        return output

    if object == "copy_template_to_solid_placeholders":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("copy_template_to_solid_placeholders requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("copy_template_to_solid_placeholders requires a rectangular grid")
        placeholder_color = color
        background_color = 0 if color1 is None else color1
        if placeholder_color in (None, background_color):
            raise ValueError("copy_template_to_solid_placeholders requires a placeholder color")

        template_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] not in (background_color, placeholder_color)
        ]
        if not template_pixels:
            raise ValueError("copy_template_to_solid_placeholders requires a source template")
        template_min_row = min(row for row, _ in template_pixels)
        template_max_row = max(row for row, _ in template_pixels)
        template_min_col = min(col for _, col in template_pixels)
        template_max_col = max(col for _, col in template_pixels)
        template_height = template_max_row - template_min_row + 1
        template_width = template_max_col - template_min_col + 1
        template = [
            [
                grid[row][col]
                if grid[row][col] not in (background_color, placeholder_color)
                else background_color
                for col in range(template_min_col, template_max_col + 1)
            ]
            for row in range(template_min_row, template_max_row + 1)
        ]

        visited = set()
        placeholders = []
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != placeholder_color or (row, col) in visited:
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
                        if (next_row, next_col) in visited or grid[next_row][next_col] != placeholder_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                min_row = min(row for row, _ in pixels)
                max_row = max(row for row, _ in pixels)
                min_col = min(col for _, col in pixels)
                max_col = max(col for _, col in pixels)
                rectangle = {
                    (row, col)
                    for row in range(min_row, max_row + 1)
                    for col in range(min_col, max_col + 1)
                }
                if set(pixels) != rectangle:
                    raise ValueError("copy_template_to_solid_placeholders requires solid placeholder rectangles")
                if max_row - min_row + 1 != template_height or max_col - min_col + 1 != template_width:
                    raise ValueError("copy_template_to_solid_placeholders requires placeholders matching template size")
                placeholders.append((min_row, min_col))
        if not placeholders:
            raise ValueError("copy_template_to_solid_placeholders found no placeholders")

        output = [row[:] for row in grid]
        for min_row, min_col in placeholders:
            for delta_row in range(template_height):
                for delta_col in range(template_width):
                    output[min_row + delta_row][min_col + delta_col] = background_color
            for delta_row, template_row in enumerate(template):
                for delta_col, value in enumerate(template_row):
                    if value != background_color:
                        output[min_row + delta_row][min_col + delta_col] = value
        return output

    if object == "separator_left_template_to_markers":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_left_template_to_markers requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_left_template_to_markers requires a rectangular grid")
        marker_color = color
        background_color = 0 if color1 is None else color1
        if marker_color in (None, background_color):
            raise ValueError("separator_left_template_to_markers requires a marker color")

        separator_cols = [
            col
            for col in range(1, cols - 1)
            if grid[0][col] != background_color
            and all(grid[row][col] == grid[0][col] for row in range(rows))
        ]
        if len(separator_cols) != 1:
            raise ValueError("separator_left_template_to_markers requires one full separator column")
        separator_col = separator_cols[0]
        separator_color = grid[0][separator_col]

        template_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(separator_col)
            if grid[row][col] not in (background_color, separator_color)
        ]
        if not template_pixels:
            raise ValueError("separator_left_template_to_markers requires a left template")
        template_min_row = min(row for row, _ in template_pixels)
        template_max_row = max(row for row, _ in template_pixels)
        template_min_col = min(col for _, col in template_pixels)
        template_max_col = max(col for _, col in template_pixels)
        template_height = template_max_row - template_min_row + 1
        template_width = template_max_col - template_min_col + 1
        if template_height % 2 == 0 or template_width % 2 == 0:
            raise ValueError("separator_left_template_to_markers requires an odd template size")
        template = [
            [
                grid[row][col]
                if grid[row][col] not in (background_color, separator_color)
                else background_color
                for col in range(template_min_col, template_max_col + 1)
            ]
            for row in range(template_min_row, template_max_row + 1)
        ]
        center_row = template_height // 2
        center_col = template_width // 2

        markers = [
            (row, col)
            for row in range(rows)
            for col in range(separator_col + 1, cols)
            if grid[row][col] == marker_color
        ]
        if not markers:
            raise ValueError("separator_left_template_to_markers found no markers")

        output = [[background_color for _ in range(cols)] for _ in range(rows)]
        for row in range(rows):
            output[row][separator_col] = separator_color
        for row in range(template_min_row, template_max_row + 1):
            for col in range(template_min_col, template_max_col + 1):
                output[row][col] = grid[row][col]
        for marker_row, marker_col in markers:
            top = marker_row - center_row
            left = marker_col - center_col
            for delta_row, template_row in enumerate(template):
                for delta_col, value in enumerate(template_row):
                    if value == background_color:
                        continue
                    out_row = top + delta_row
                    out_col = left + delta_col
                    if 0 <= out_row < rows and 0 <= out_col < cols:
                        output[out_row][out_col] = value
        return output

    if object == "extend_hollow_rectangle_to_marker":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("extend_hollow_rectangle_to_marker requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("extend_hollow_rectangle_to_marker requires a rectangular grid")
        marker_color = color
        background_color = 0 if color1 is None else color1
        if marker_color in (None, background_color):
            raise ValueError("extend_hollow_rectangle_to_marker requires a marker color")
        markers = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == marker_color
        ]
        if len(markers) != 1:
            raise ValueError("extend_hollow_rectangle_to_marker requires one marker")
        marker_row, marker_col = markers[0]
        rectangle_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] not in (background_color, marker_color)
        ]
        if not rectangle_pixels:
            raise ValueError("extend_hollow_rectangle_to_marker requires a rectangle")
        min_row = min(row for row, _ in rectangle_pixels)
        max_row = max(row for row, _ in rectangle_pixels)
        min_col = min(col for _, col in rectangle_pixels)
        max_col = max(col for _, col in rectangle_pixels)
        if max_row - min_row + 1 < 3 or max_col - min_col + 1 < 3:
            raise ValueError("extend_hollow_rectangle_to_marker requires a hollow rectangle")

        border_values = []
        inner_values = []
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                value = grid[row][col]
                on_border = row in (min_row, max_row) or col in (min_col, max_col)
                if on_border:
                    border_values.append(value)
                elif value != background_color:
                    inner_values.append(value)
        if not border_values or not inner_values:
            raise ValueError("extend_hollow_rectangle_to_marker requires border and interior colors")

        def most_common(values):
            counts = {}
            for value in values:
                counts[value] = counts.get(value, 0) + 1
            return sorted(counts, key=lambda value: (-counts[value], value))[0]

        border_color = most_common(border_values)
        inner_color = most_common(inner_values)
        new_min_row, new_max_row = min_row, max_row
        new_min_col, new_max_col = min_col, max_col
        if marker_col >= min_col and marker_col <= max_col and marker_row < min_row:
            new_min_row = marker_row
        elif marker_col >= min_col and marker_col <= max_col and marker_row > max_row:
            new_max_row = marker_row
        elif marker_row >= min_row and marker_row <= max_row and marker_col < min_col:
            new_min_col = marker_col
        elif marker_row >= min_row and marker_row <= max_row and marker_col > max_col:
            new_max_col = marker_col
        else:
            raise ValueError("extend_hollow_rectangle_to_marker marker must align with rectangle")

        output = [row[:] for row in grid]
        output[marker_row][marker_col] = background_color
        for row in range(new_min_row, new_max_row + 1):
            for col in range(new_min_col, new_max_col + 1):
                if row in (new_min_row, new_max_row) or col in (new_min_col, new_max_col):
                    output[row][col] = border_color
                else:
                    output[row][col] = inner_color
        return output

    if object == "aligned_marker_bridge_boxes":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("aligned_marker_bridge_boxes requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("aligned_marker_bridge_boxes requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        markers = [
            (row, col, value)
            for row in range(rows)
            for col in range(cols)
            for value in [grid[row][col]]
            if value != background_color
        ]
        if len(markers) != 2:
            raise ValueError("aligned_marker_bridge_boxes requires exactly two markers")
        (row_a, col_a, color_a), (row_b, col_b, color_b) = markers
        if color_a == color_b:
            raise ValueError("aligned_marker_bridge_boxes requires two colors")
        output = [[background_color for _ in range(cols)] for _ in range(rows)]

        half_width = 2
        if col_a == col_b:
            if row_a > row_b:
                row_a, col_a, color_a, row_b, col_b, color_b = row_b, col_b, color_b, row_a, col_a, color_a
            gap = row_b - row_a
            if gap < 5:
                raise ValueError("aligned_marker_bridge_boxes requires separated vertical markers")
            offset = max(2, (gap - 3) // 2)
            center_top = row_a + offset
            center_bottom = row_b - offset - (1 if gap % 2 == 0 else 0)
            if center_top >= center_bottom:
                raise ValueError("aligned_marker_bridge_boxes requires room between vertical boxes")
            center_col = col_a
            left_col = max(0, center_col - half_width)
            right_col = min(cols - 1, center_col + half_width)
            for row in range(row_a, center_top + 1):
                output[row][center_col] = color_a
            for col in range(left_col, right_col + 1):
                output[center_top][col] = color_a
            if center_top + 1 < center_bottom:
                output[center_top + 1][left_col] = color_a
                output[center_top + 1][right_col] = color_a
                output[center_bottom - 1][left_col] = color_b
                output[center_bottom - 1][right_col] = color_b
            for col in range(left_col, right_col + 1):
                output[center_bottom][col] = color_b
            for row in range(center_bottom, row_b + 1):
                output[row][center_col] = color_b
            return output

        if row_a == row_b:
            if col_a > col_b:
                row_a, col_a, color_a, row_b, col_b, color_b = row_b, col_b, color_b, row_a, col_a, color_a
            gap = col_b - col_a
            if gap < 5:
                raise ValueError("aligned_marker_bridge_boxes requires separated horizontal markers")
            offset = max(2, (gap - 3) // 2)
            center_left = col_a + offset
            center_right = col_b - offset - (1 if gap % 2 == 0 else 0)
            if center_left >= center_right:
                raise ValueError("aligned_marker_bridge_boxes requires room between horizontal boxes")
            center_row = row_a
            top_row = max(0, center_row - half_width)
            bottom_row = min(rows - 1, center_row + half_width)
            for col in range(col_a, center_left + 1):
                output[center_row][col] = color_a
            for row in range(top_row, bottom_row + 1):
                output[row][center_left] = color_a
            if center_left + 1 < center_right:
                output[top_row][center_left + 1] = color_a
                output[bottom_row][center_left + 1] = color_a
                output[top_row][center_right - 1] = color_b
                output[bottom_row][center_right - 1] = color_b
            for row in range(top_row, bottom_row + 1):
                output[row][center_right] = color_b
            for col in range(center_right, col_b + 1):
                output[center_row][col] = color_b
            return output

        raise ValueError("aligned_marker_bridge_boxes requires aligned markers")

    if object == "copy_template_centered_on_marker":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("copy_template_centered_on_marker requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("copy_template_centered_on_marker requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        marker_color = color
        if marker_color == "input_non_background":
            by_color = {}
            for row in range(rows):
                for col in range(cols):
                    value = grid[row][col]
                    if value != background_color:
                        by_color.setdefault(value, []).append((row, col))
            isolated_singletons = []
            for candidate_color, positions in by_color.items():
                if len(positions) != 1:
                    continue
                row, col = positions[0]
                if all(
                    not (
                        0 <= row + delta_row < rows
                        and 0 <= col + delta_col < cols
                    )
                    or grid[row + delta_row][col + delta_col] == background_color
                    for delta_row in (-1, 0, 1)
                    for delta_col in (-1, 0, 1)
                    if not (delta_row == 0 and delta_col == 0)
                ):
                    isolated_singletons.append(candidate_color)
            if len(isolated_singletons) != 1:
                raise ValueError("copy_template_centered_on_marker requires one isolated marker color")
            marker_color = isolated_singletons[0]
        if marker_color in (None, background_color):
            raise ValueError("copy_template_centered_on_marker requires an explicit marker color")
        markers = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == marker_color
        ]
        if len(markers) != 1:
            raise ValueError("copy_template_centered_on_marker requires one marker")
        marker_row, marker_col = markers[0]
        template_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] not in (background_color, marker_color)
        ]
        if not template_pixels:
            raise ValueError("copy_template_centered_on_marker requires a template")
        min_row = min(row for row, _ in template_pixels)
        max_row = max(row for row, _ in template_pixels)
        min_col = min(col for _, col in template_pixels)
        max_col = max(col for _, col in template_pixels)
        template = [
            [grid[row][col] for col in range(min_col, max_col + 1)]
            for row in range(min_row, max_row + 1)
        ]
        target_top = marker_row - 1
        target_left = marker_col - 1
        if target_top < 0 or target_left < 0:
            raise ValueError("copy_template_centered_on_marker marker is too close to edge")
        if target_top + len(template) > rows or target_left + len(template[0]) > cols:
            raise ValueError("copy_template_centered_on_marker template does not fit")
        output = [row[:] for row in grid]
        output[marker_row][marker_col] = background_color
        changed = False
        for delta_row, template_row in enumerate(template):
            for delta_col, value in enumerate(template_row):
                if value == background_color:
                    continue
                row = target_top + delta_row
                col = target_left + delta_col
                if output[row][col] != value:
                    changed = True
                output[row][col] = value
        if not changed:
            raise ValueError("copy_template_centered_on_marker produced no copy")
        return output

    if object == "copy_template_from_embedded_marker_to_singleton":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("copy_template_from_embedded_marker_to_singleton requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("copy_template_from_embedded_marker_to_singleton requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        visited = set()
        components = []
        for start_row in range(rows):
            for start_col in range(cols):
                if (start_row, start_col) in visited or grid[start_row][start_col] == background_color:
                    continue
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                pixels = []
                while stack:
                    row, col = stack.pop()
                    pixels.append((row, col))
                    for delta_row in (-1, 0, 1):
                        for delta_col in (-1, 0, 1):
                            if delta_row == 0 and delta_col == 0:
                                continue
                            next_row = row + delta_row
                            next_col = col + delta_col
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if (
                                (next_row, next_col) in visited
                                or grid[next_row][next_col] == background_color
                            ):
                                continue
                            visited.add((next_row, next_col))
                            stack.append((next_row, next_col))
                components.append({
                    "pixels": tuple(sorted(pixels)),
                    "colors": {grid[row][col] for row, col in pixels},
                })

        candidates = []
        for marker_color in sorted({
            grid[row][col]
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        }):
            source_components = [
                component
                for component in components
                if len(component["pixels"]) > 1
                and marker_color in component["colors"]
                and sum(1 for row, col in component["pixels"] if grid[row][col] == marker_color) == 1
            ]
            singleton_components = [
                component
                for component in components
                if len(component["pixels"]) == 1
                and grid[component["pixels"][0][0]][component["pixels"][0][1]] == marker_color
            ]
            if len(source_components) == 1 and len(singleton_components) == 1:
                candidates.append((marker_color, source_components[0], singleton_components[0]))
        if len(candidates) != 1:
            raise ValueError("copy_template_from_embedded_marker_to_singleton requires one source/singleton marker pair")

        marker_color, source_component, singleton_component = candidates[0]
        source_marker = [
            (row, col)
            for row, col in source_component["pixels"]
            if grid[row][col] == marker_color
        ][0]
        target_marker = singleton_component["pixels"][0]
        output = [row[:] for row in grid]
        output[target_marker[0]][target_marker[1]] = background_color
        changed = True
        for row, col in source_component["pixels"]:
            value = grid[row][col]
            if value == marker_color:
                continue
            target_row = target_marker[0] + row - source_marker[0]
            target_col = target_marker[1] + col - source_marker[1]
            if not (0 <= target_row < rows and 0 <= target_col < cols):
                raise ValueError("copy_template_from_embedded_marker_to_singleton copy leaves grid")
            if output[target_row][target_col] not in (background_color, value):
                raise ValueError("copy_template_from_embedded_marker_to_singleton copy collides")
            if output[target_row][target_col] != value:
                changed = True
            output[target_row][target_col] = value
        if not changed:
            raise ValueError("copy_template_from_embedded_marker_to_singleton produced no copy")
        return output

    if object == "same_color_pair_bounding_rectangles":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("same_color_pair_bounding_rectangles requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("same_color_pair_bounding_rectangles requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        positions_by_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                positions_by_color.setdefault(value, []).append((row, col))
        output = [row[:] for row in grid]
        changed = False
        for rect_color, positions in positions_by_color.items():
            if len(positions) != 2:
                continue
            min_row = min(row for row, _ in positions)
            max_row = max(row for row, _ in positions)
            min_col = min(col for _, col in positions)
            max_col = max(col for _, col in positions)
            for row in range(min_row, max_row + 1):
                for col in range(min_col, max_col + 1):
                    if output[row][col] != rect_color:
                        output[row][col] = rect_color
                        changed = True
        if not changed:
            raise ValueError("same_color_pair_bounding_rectangles produced no change")
        return output

    if object == "two_color_marker_cross":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("two_color_marker_cross requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("two_color_marker_cross requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        intersection_color = color
        markers = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if len(markers) != 2:
            raise ValueError("two_color_marker_cross requires exactly two markers")
        (row_a, col_a, color_a), (row_b, col_b, color_b) = markers
        if color_a == color_b:
            raise ValueError("two_color_marker_cross requires two marker colors")
        if row_a == row_b or col_a == col_b:
            raise ValueError("two_color_marker_cross requires distinct marker rows and columns")
        if intersection_color in (None, background_color, color_a, color_b):
            raise ValueError("two_color_marker_cross requires a third intersection color")
        output = [[background_color for _ in range(cols)] for _ in range(rows)]
        for row in range(rows):
            output[row][col_a] = color_a
            output[row][col_b] = color_b
        for col in range(cols):
            output[row_a][col] = color_a
            output[row_b][col] = color_b
        output[row_a][col_b] = intersection_color
        output[row_b][col_a] = intersection_color
        return output

    if object == "reflect_foreground":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("reflect_foreground requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("reflect_foreground requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        marker_color = color
        if marker_color in (None, background_color):
            raise ValueError("reflect_foreground requires a marker color")
        marker_cells = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == marker_color
        ]
        if len(marker_cells) != 4:
            raise ValueError("reflect_foreground requires one 2x2 marker")
        marker_rows = sorted({row for row, _ in marker_cells})
        marker_cols = sorted({col for _, col in marker_cells})
        if len(marker_rows) != 2 or len(marker_cols) != 2:
            raise ValueError("reflect_foreground requires a 2x2 marker")
        marker_top, marker_bottom = marker_rows
        marker_left, marker_right = marker_cols
        if marker_bottom != marker_top + 1 or marker_right != marker_left + 1:
            raise ValueError("reflect_foreground requires adjacent marker cells")
        if set(marker_cells) != {
            (marker_top, marker_left),
            (marker_top, marker_right),
            (marker_bottom, marker_left),
            (marker_bottom, marker_right),
        }:
            raise ValueError("reflect_foreground marker must be solid")
        source_pixels = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] not in (background_color, marker_color)
        ]
        if not source_pixels:
            raise ValueError("reflect_foreground requires foreground to reflect")
        output = [row[:] for row in grid]
        marker_set = set(marker_cells)
        for row, col, value in source_pixels:
            reflected_row = marker_top + marker_bottom - row
            reflected_col = marker_left + marker_right - col
            for target_row, target_col in (
                (row, col),
                (row, reflected_col),
                (reflected_row, col),
                (reflected_row, reflected_col),
            ):
                if not (0 <= target_row < rows and 0 <= target_col < cols):
                    raise ValueError("reflect_foreground reflection is out of bounds")
                if (target_row, target_col) in marker_set:
                    raise ValueError("reflect_foreground reflection hits marker")
                existing = output[target_row][target_col]
                if existing not in (background_color, value):
                    raise ValueError("reflect_foreground conflicting reflection")
                output[target_row][target_col] = value
        return output

    if object == "rightward_alternating_marker_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("rightward_alternating_marker_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("rightward_alternating_marker_fill requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        fill_color = color
        if fill_color in (None, background_color):
            raise ValueError("rightward_alternating_marker_fill requires a fill color")
        output = [row[:] for row in grid]
        changed = False
        for row in range(rows):
            marker_cols = [
                col
                for col in range(cols)
                if grid[row][col] not in (background_color, fill_color)
            ]
            if len(marker_cols) != 1:
                continue
            start_col = marker_cols[0]
            marker_color = grid[row][start_col]
            for col in range(start_col, cols):
                value = marker_color if (col - start_col) % 2 == 0 else fill_color
                if output[row][col] != value:
                    changed = True
                output[row][col] = value
        if not changed:
            raise ValueError("rightward_alternating_marker_fill produced no change")
        return output

    if object == "bottom_pattern_shift_right_at_markers":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("bottom_pattern_shift_right_at_markers requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("bottom_pattern_shift_right_at_markers requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        marker_color = color
        if marker_color in (None, background_color):
            raise ValueError("bottom_pattern_shift_right_at_markers requires a marker color")
        bottom = rows - 1
        pattern_colors = {
            value
            for value in grid[bottom]
            if value not in (background_color, marker_color)
        }
        if len(pattern_colors) != 1:
            raise ValueError("bottom_pattern_shift_right_at_markers requires one bottom pattern color")
        pattern_color = next(iter(pattern_colors))
        source_cols = [
            col
            for col, value in enumerate(grid[bottom])
            if value == pattern_color
        ]
        if not source_cols:
            raise ValueError("bottom_pattern_shift_right_at_markers requires bottom pattern cells")
        marker_cells = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == marker_color
        ]
        if not marker_cells:
            raise ValueError("bottom_pattern_shift_right_at_markers requires markers")

        output = [[background_color for _ in range(cols)] for _ in range(rows)]
        for row, col in marker_cells:
            output[row][col] = marker_color

        changed_by_marker = False
        for source_col in source_cols:
            current_col = source_col
            for row in range(bottom, -1, -1):
                if not (0 <= current_col < cols):
                    raise ValueError("bottom_pattern_shift_right_at_markers shifted out of bounds")
                if grid[row][current_col] == marker_color:
                    shifted_col = current_col + 1
                    if shifted_col >= cols:
                        raise ValueError("bottom_pattern_shift_right_at_markers marker blocks right edge")
                    if output[row][shifted_col] not in (background_color, pattern_color):
                        raise ValueError("bottom_pattern_shift_right_at_markers conflicting shifted cell")
                    output[row][shifted_col] = pattern_color
                    if row + 1 < rows:
                        if output[row + 1][shifted_col] not in (background_color, pattern_color):
                            raise ValueError("bottom_pattern_shift_right_at_markers conflicting connector")
                        output[row + 1][shifted_col] = pattern_color
                    current_col = shifted_col
                    changed_by_marker = True
                if output[row][current_col] not in (background_color, pattern_color, marker_color):
                    raise ValueError("bottom_pattern_shift_right_at_markers conflicting pattern cell")
                if output[row][current_col] != marker_color:
                    output[row][current_col] = pattern_color
        if not changed_by_marker:
            raise ValueError("bottom_pattern_shift_right_at_markers produced no marker shift")
        return output

    if object == "connect_same_color_diagonal_pairs":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("connect_same_color_diagonal_pairs requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("connect_same_color_diagonal_pairs requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        positions_by_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                positions_by_color.setdefault(value, []).append((row, col))

        output = [row[:] for row in grid]
        changed = False
        for pair_color, positions in positions_by_color.items():
            if len(positions) != 2:
                continue
            (row1, col1), (row2, col2) = positions
            delta_row = row2 - row1
            delta_col = col2 - col1
            if abs(delta_row) != abs(delta_col) or delta_row == 0:
                continue
            step_row = 1 if delta_row > 0 else -1
            step_col = 1 if delta_col > 0 else -1
            steps = abs(delta_row)
            for step in range(steps + 1):
                row = row1 + step * step_row
                col = col1 + step * step_col
                if output[row][col] == background_color:
                    output[row][col] = pair_color
                    changed = True
        if not changed:
            raise ValueError("connect_same_color_diagonal_pairs produced no change")
        return output

    if object == "frame_center_crosses":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("frame_center_crosses requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("frame_center_crosses requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        cross_color = color
        if cross_color in (None, background_color):
            raise ValueError("frame_center_crosses requires a cross color")
        frame_cells = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] not in (background_color, cross_color)
        ]
        if not frame_cells:
            raise ValueError("frame_center_crosses requires frame cells")

        visited = set()
        components = []
        for start in frame_cells:
            if start in visited:
                continue
            frame_color = grid[start[0]][start[1]]
            stack = [start]
            visited.add(start)
            component = []
            while stack:
                row, col = stack.pop()
                component.append((row, col))
                for next_row, next_col in (
                    (row - 1, col),
                    (row + 1, col),
                    (row, col - 1),
                    (row, col + 1),
                ):
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        continue
                    if (next_row, next_col) in visited:
                        continue
                    if grid[next_row][next_col] != frame_color:
                        continue
                    visited.add((next_row, next_col))
                    stack.append((next_row, next_col))
            components.append((frame_color, component))

        output = [row[:] for row in grid]
        changed = False
        for frame_color, component in components:
            min_row = min(row for row, _ in component)
            max_row = max(row for row, _ in component)
            min_col = min(col for _, col in component)
            max_col = max(col for _, col in component)
            if (max_row - min_row) % 2 != 0 or (max_col - min_col) % 2 != 0:
                raise ValueError("frame_center_crosses requires odd-sized frame bboxes")
            if max_row - min_row < 2 or max_col - min_col < 2:
                raise ValueError("frame_center_crosses requires non-trivial frames")
            component_set = set(component)
            for col in range(min_col, max_col + 1):
                if (min_row, col) not in component_set or (max_row, col) not in component_set:
                    raise ValueError("frame_center_crosses requires complete frame rows")
            for row in range(min_row, max_row + 1):
                if (row, min_col) not in component_set or (row, max_col) not in component_set:
                    raise ValueError("frame_center_crosses requires complete frame columns")
            center_row = (min_row + max_row) // 2
            center_col = (min_col + max_col) // 2
            for col in range(cols):
                if output[center_row][col] == background_color:
                    output[center_row][col] = cross_color
                    changed = True
            for row in range(rows):
                if output[row][center_col] == background_color:
                    output[row][center_col] = cross_color
                    changed = True
        if not changed:
            raise ValueError("frame_center_crosses produced no change")
        return output

    if object == "swap_frame_and_project_border":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("swap_frame_and_project_border requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("swap_frame_and_project_border requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        foreground = {
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        }
        if not foreground:
            raise ValueError("swap_frame_and_project_border requires foreground")

        components = []
        visited = set()
        for start in sorted(foreground):
            if start in visited:
                continue
            stack = [start]
            visited.add(start)
            component = []
            while stack:
                row, col = stack.pop()
                component.append((row, col))
                for next_row, next_col in (
                    (row - 1, col),
                    (row + 1, col),
                    (row, col - 1),
                    (row, col + 1),
                ):
                    if (next_row, next_col) in visited or (next_row, next_col) not in foreground:
                        continue
                    visited.add((next_row, next_col))
                    stack.append((next_row, next_col))
            components.append(component)

        output = [row[:] for row in grid]
        changed = False
        for component in components:
            min_row = min(row for row, _ in component)
            max_row = max(row for row, _ in component)
            min_col = min(col for _, col in component)
            max_col = max(col for _, col in component)
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            if height < 3 or width < 3:
                raise ValueError("swap_frame_and_project_border requires rectangular frames")
            component_set = set(component)
            if len(component_set) != height * width:
                raise ValueError("swap_frame_and_project_border requires a solid foreground rectangle")

            border_cells = [
                (row, col)
                for row in range(min_row, max_row + 1)
                for col in range(min_col, max_col + 1)
                if row in (min_row, max_row) or col in (min_col, max_col)
            ]
            interior_cells = [
                (row, col)
                for row in range(min_row + 1, max_row)
                for col in range(min_col + 1, max_col)
            ]
            border_colors = {grid[row][col] for row, col in border_cells}
            interior_colors = {grid[row][col] for row, col in interior_cells}
            if len(border_colors) != 1 or len(interior_colors) != 1:
                raise ValueError("swap_frame_and_project_border requires uniform frame/interior colors")
            frame_color = next(iter(border_colors))
            inner_color = next(iter(interior_colors))
            if frame_color == inner_color or background_color in (frame_color, inner_color):
                raise ValueError("swap_frame_and_project_border requires two foreground colors")

            for row, col in border_cells:
                if output[row][col] != inner_color:
                    output[row][col] = inner_color
                    changed = True
            for row, col in interior_cells:
                if output[row][col] != frame_color:
                    output[row][col] = frame_color
                    changed = True

            inner_height = height - 2
            inner_width = width - 2
            projected_spans = [
                (range(min_row - inner_height, min_row), range(min_col, max_col + 1)),
                (range(max_row + 1, max_row + 1 + inner_height), range(min_col, max_col + 1)),
                (range(min_row, max_row + 1), range(min_col - inner_width, min_col)),
                (range(min_row, max_row + 1), range(max_col + 1, max_col + 1 + inner_width)),
            ]
            for row_span, col_span in projected_spans:
                for row in row_span:
                    for col in col_span:
                        if not (0 <= row < rows and 0 <= col < cols):
                            raise ValueError("swap_frame_and_project_border projected frame out of bounds")
                        if output[row][col] not in (background_color, frame_color):
                            raise ValueError("swap_frame_and_project_border conflicting projection")
                        if output[row][col] != frame_color:
                            output[row][col] = frame_color
                            changed = True
        if not changed:
            raise ValueError("swap_frame_and_project_border produced no change")
        return output

    if object == "bounded_empty_crossbars":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("bounded_empty_crossbars requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("bounded_empty_crossbars requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        fill_color = color
        if fill_color in (None, background_color):
            raise ValueError("bounded_empty_crossbars requires a fill color")

        foreground = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if not foreground:
            raise ValueError("bounded_empty_crossbars requires a foreground boundary")
        min_row = min(row for row, _ in foreground)
        max_row = max(row for row, _ in foreground)
        min_col = min(col for _, col in foreground)
        max_col = max(col for _, col in foreground)
        if max_row - min_row < 2 or max_col - min_col < 2:
            raise ValueError("bounded_empty_crossbars requires an interior")
        interior_rows = range(min_row + 1, max_row)
        interior_cols = range(min_col + 1, max_col)

        empty_rows = [
            row
            for row in interior_rows
            if all(grid[row][col] == background_color for col in interior_cols)
        ]
        empty_cols = [
            col
            for col in interior_cols
            if all(grid[row][col] == background_color for row in interior_rows)
        ]
        if not empty_rows and not empty_cols:
            raise ValueError("bounded_empty_crossbars found no empty interior rows or columns")

        output = [row[:] for row in grid]
        changed = False
        for row in empty_rows:
            for col in interior_cols:
                if output[row][col] == background_color:
                    output[row][col] = fill_color
                    changed = True
        for col in empty_cols:
            for row in interior_rows:
                if output[row][col] == background_color:
                    output[row][col] = fill_color
                    changed = True
        if not changed:
            raise ValueError("bounded_empty_crossbars produced no change")
        return output

    if object == "component_border_and_holes":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("component_border_and_holes requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("component_border_and_holes requires a rectangular grid")

        counts = {}
        for row in grid:
            for value in row:
                counts[value] = counts.get(value, 0) + 1
        background_color = max(counts, key=counts.get)
        object_pixels = {
            (row_index, col_index)
            for row_index, row in enumerate(grid)
            for col_index, value in enumerate(row)
            if value != background_color
        }
        if not object_pixels:
            raise ValueError("component_border_and_holes requires foreground components")

        def neighbors4(pixel):
            row_index, col_index = pixel
            for row_delta, col_delta in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                next_row = row_index + row_delta
                next_col = col_index + col_delta
                if 0 <= next_row < rows and 0 <= next_col < cols:
                    yield next_row, next_col

        unvisited = set(object_pixels)
        components = []
        while unvisited:
            start = unvisited.pop()
            stack = [start]
            component = {start}
            while stack:
                pixel = stack.pop()
                for neighbor in neighbors4(pixel):
                    if neighbor not in unvisited:
                        continue
                    unvisited.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
            components.append(component)

        output = [row[:] for row in grid]
        all_holes = set()
        for component in components:
            min_row = min(row_index for row_index, _ in component)
            max_row = max(row_index for row_index, _ in component)
            min_col = min(col_index for _, col_index in component)
            max_col = max(col_index for _, col_index in component)
            bbox_background = {
                (row_index, col_index)
                for row_index in range(min_row, max_row + 1)
                for col_index in range(min_col, max_col + 1)
                if (row_index, col_index) not in component
                and grid[row_index][col_index] == background_color
            }
            exterior = set()
            stack = [
                pixel
                for pixel in bbox_background
                if pixel[0] in (min_row, max_row) or pixel[1] in (min_col, max_col)
            ]
            while stack:
                pixel = stack.pop()
                if pixel in exterior:
                    continue
                exterior.add(pixel)
                for neighbor in neighbors4(pixel):
                    if neighbor in bbox_background and neighbor not in exterior:
                        stack.append(neighbor)
            holes = bbox_background - exterior
            all_holes.update(holes)

        for row_index, col_index in all_holes:
            output[row_index][col_index] = color1

        for component in components:
            for row_index, col_index in component:
                for row_delta in (-1, 0, 1):
                    for col_delta in (-1, 0, 1):
                        if row_delta == 0 and col_delta == 0:
                            continue
                        next_row = row_index + row_delta
                        next_col = col_index + col_delta
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in all_holes:
                            continue
                        if grid[next_row][next_col] == background_color:
                            output[next_row][next_col] = color

        return output

    if object == "copy_template_to_placeholder_components":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("copy_template_to_placeholder_components requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("copy_template_to_placeholder_components requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        def components_for_color(target_color):
            visited = set()
            components = []
            for start_row in range(rows):
                for start_col in range(cols):
                    if grid[start_row][start_col] != target_color or (start_row, start_col) in visited:
                        continue
                    stack = [(start_row, start_col)]
                    visited.add((start_row, start_col))
                    pixels = []
                    while stack:
                        current_row, current_col = stack.pop()
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
                            if grid[next_row][next_col] != target_color:
                                continue
                            visited.add((next_row, next_col))
                            stack.append((next_row, next_col))
                    min_row = min(row for row, _ in pixels)
                    max_row = max(row for row, _ in pixels)
                    min_col = min(col for _, col in pixels)
                    max_col = max(col for _, col in pixels)
                    components.append((pixels, min_row, max_row, min_col, max_col))
            return components

        non_background_colors = sorted({
            value
            for row in grid
            for value in row
            if value != background_color
        })
        candidates = []
        for placeholder_color in non_background_colors:
            placeholder_components = components_for_color(placeholder_color)
            if not placeholder_components:
                continue
            template_pixels = [
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] not in (background_color, placeholder_color)
            ]
            if not template_pixels:
                continue
            template_min_row = min(row for row, _ in template_pixels)
            template_max_row = max(row for row, _ in template_pixels)
            template_min_col = min(col for _, col in template_pixels)
            template_max_col = max(col for _, col in template_pixels)
            template_height = template_max_row - template_min_row + 1
            template_width = template_max_col - template_min_col + 1
            if template_height <= 0 or template_width <= 0:
                continue
            if not all(
                max_row - min_row + 1 == template_height
                and max_col - min_col + 1 == template_width
                for _, min_row, max_row, min_col, max_col in placeholder_components
            ):
                continue
            if len(placeholder_components) < 1:
                continue
            candidates.append((
                placeholder_color,
                placeholder_components,
                template_min_row,
                template_max_row,
                template_min_col,
                template_max_col,
            ))

        if len(candidates) != 1:
            raise ValueError("copy_template_to_placeholder_components requires one placeholder color")

        (
            _,
            placeholder_components,
            template_min_row,
            template_max_row,
            template_min_col,
            template_max_col,
        ) = candidates[0]
        template = [
            [
                grid[row][col]
                for col in range(template_min_col, template_max_col + 1)
            ]
            for row in range(template_min_row, template_max_row + 1)
        ]
        output = [[background_color for _ in range(cols)] for _ in range(rows)]
        for _, min_row, _, min_col, _ in placeholder_components:
            for delta_row, template_row in enumerate(template):
                for delta_col, value in enumerate(template_row):
                    if value == background_color:
                        continue
                    output[min_row + delta_row][min_col + delta_col] = value
        return output

    if object == "four_equal_shape_decomposition_lattice":
        from itertools import combinations

        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("four_equal_shape_decomposition_lattice requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("four_equal_shape_decomposition_lattice requires a rectangular grid")

        background_color = 0 if color1 is None else color1
        foreground_colors = sorted({
            value
            for row in grid
            for value in row
            if value != background_color
        })
        if len(foreground_colors) != 1:
            raise ValueError("four_equal_shape_decomposition_lattice requires one foreground color")
        foreground_color = foreground_colors[0]
        if color not in (None, "input_non_background", foreground_color):
            raise ValueError("four_equal_shape_decomposition_lattice foreground color mismatch")

        foreground = {
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == foreground_color
        }
        if len(foreground) < 4 or len(foreground) % 4 != 0:
            raise ValueError("four_equal_shape_decomposition_lattice requires four equal parts")
        part_size = len(foreground) // 4
        if part_size > 8:
            raise ValueError("four_equal_shape_decomposition_lattice part size is too large")

        def normalize(cells):
            min_row = min(row for row, _ in cells)
            min_col = min(col for _, col in cells)
            return tuple(sorted((row - min_row, col - min_col) for row, col in cells))

        candidate_masks = set()
        max_box_side = min(2, max(rows, cols))
        for height in range(1, max_box_side + 1):
            for width in range(1, max_box_side + 1):
                if height * width < part_size:
                    continue
                box_cells = [(row, col) for row in range(height) for col in range(width)]
                for mask_cells in combinations(box_cells, part_size):
                    mask = normalize(mask_cells)
                    mask_height = max(row for row, _ in mask) + 1
                    mask_width = max(col for _, col in mask) + 1
                    if mask_height != height or mask_width != width:
                        continue
                    candidate_masks.add(mask)

        plans = []
        for mask in sorted(candidate_masks):
            mask_height = max(row for row, _ in mask) + 1
            mask_width = max(col for _, col in mask) + 1
            placements = []
            for top in range(0, rows - mask_height + 1):
                for left in range(0, cols - mask_width + 1):
                    placed = tuple(sorted((top + row, left + col) for row, col in mask))
                    if set(placed) <= foreground:
                        placements.append(placed)
            covers = []
            for placement_group in combinations(placements, 4):
                covered = set()
                for placement in placement_group:
                    covered.update(placement)
                if len(covered) == len(foreground) and covered == foreground:
                    covers.append(placement_group)
                    if len(covers) > 1:
                        break
            if len(covers) == 1:
                plans.append({
                    "mask": mask,
                    "height": mask_height,
                    "width": mask_width,
                })

        if len(plans) != 1:
            raise ValueError("four_equal_shape_decomposition_lattice requires one exact four-part decomposition")

        plan = plans[0]
        output_rows = plan["height"] * 2 + 1
        output_cols = plan["width"] * 2 + 1
        output = [[background_color for _ in range(output_cols)] for _ in range(output_rows)]
        anchors = (
            (0, 0),
            (0, plan["width"] + 1),
            (plan["height"] + 1, 0),
            (plan["height"] + 1, plan["width"] + 1),
        )
        for anchor_row, anchor_col in anchors:
            for delta_row, delta_col in plan["mask"]:
                output[anchor_row + delta_row][anchor_col + delta_col] = foreground_color
        return output

    if object == "same_shape_component_lattice_completion":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("same_shape_component_lattice_completion requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("same_shape_component_lattice_completion requires a rectangular grid")

        background_color = 0 if color1 is None else color1
        fill_color = color
        if fill_color in (None, background_color):
            raise ValueError("same_shape_component_lattice_completion requires a non-background fill color")
        if isinstance(fill_color, str):
            raise ValueError("same_shape_component_lattice_completion requires a concrete fill color")

        def components_for_color(target_color):
            visited = set()
            components = []
            for start_row in range(rows):
                for start_col in range(cols):
                    if grid[start_row][start_col] != target_color or (start_row, start_col) in visited:
                        continue
                    stack = [(start_row, start_col)]
                    visited.add((start_row, start_col))
                    cells = []
                    while stack:
                        current_row, current_col = stack.pop()
                        cells.append((current_row, current_col))
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
                            if grid[next_row][next_col] != target_color:
                                continue
                            visited.add((next_row, next_col))
                            stack.append((next_row, next_col))
                    min_row = min(row for row, _ in cells)
                    max_row = max(row for row, _ in cells)
                    min_col = min(col for _, col in cells)
                    max_col = max(col for _, col in cells)
                    mask = tuple(sorted(
                        (row - min_row, col - min_col)
                        for row, col in cells
                    ))
                    components.append({
                        "bbox": (min_row, max_row, min_col, max_col),
                        "height": max_row - min_row + 1,
                        "width": max_col - min_col + 1,
                        "mask": mask,
                        "top_left": (min_row, min_col),
                    })
            return components

        non_background_colors = sorted({
            value
            for row in grid
            for value in row
            if value not in (background_color, fill_color)
        })
        plans = []
        for source_color in non_background_colors:
            components = components_for_color(source_color)
            if len(components) < 3:
                continue
            signatures = {
                (component["height"], component["width"], component["mask"])
                for component in components
            }
            if len(signatures) != 1:
                continue
            height, width, mask = next(iter(signatures))
            if height <= 0 or width <= 0 or len(mask) < 3:
                continue
            if height > 10 or width > 10 or height * width > 100:
                continue

            positions = {component["top_left"] for component in components}
            row_starts = sorted({row for row, _ in positions})
            col_starts = sorted({col for _, col in positions})
            if len(row_starts) < 2 or len(col_starts) < 2:
                continue

            row_counts = {
                row: sum(1 for position_row, _ in positions if position_row == row)
                for row in row_starts
            }
            col_counts = {
                col: sum(1 for _, position_col in positions if position_col == col)
                for col in col_starts
            }
            if max(row_counts.values()) != len(col_starts):
                continue
            if max(col_counts.values()) != len(row_starts):
                continue

            full_positions = {
                (row, col)
                for row in row_starts
                for col in col_starts
            }
            missing_positions = sorted(full_positions - positions)
            if not missing_positions:
                continue

            conflict = False
            for top, left in missing_positions:
                if top + height > rows or left + width > cols:
                    conflict = True
                    break
                for delta_row, delta_col in mask:
                    if grid[top + delta_row][left + delta_col] != background_color:
                        conflict = True
                        break
                if conflict:
                    break
            if conflict:
                continue

            plans.append({
                "source_color": source_color,
                "height": height,
                "width": width,
                "mask": mask,
                "missing_positions": missing_positions,
                "existing_count": len(positions),
                "slot_count": len(full_positions),
            })

        if not plans:
            raise ValueError("same_shape_component_lattice_completion found no component lattice")
        plans.sort(
            key=lambda plan: (
                -plan["slot_count"],
                -len(plan["missing_positions"]),
                -plan["existing_count"],
                plan["source_color"],
            )
        )
        if len(plans) > 1 and (
            plans[0]["slot_count"],
            len(plans[0]["missing_positions"]),
            plans[0]["existing_count"],
        ) == (
            plans[1]["slot_count"],
            len(plans[1]["missing_positions"]),
            plans[1]["existing_count"],
        ):
            raise ValueError("same_shape_component_lattice_completion found ambiguous lattices")

        best_plan = plans[0]
        output = [row[:] for row in grid]
        changed = False
        for top, left in best_plan["missing_positions"]:
            for delta_row, delta_col in best_plan["mask"]:
                row = top + delta_row
                col = left + delta_col
                if output[row][col] != background_color:
                    raise ValueError("same_shape_component_lattice_completion encountered a fill conflict")
                output[row][col] = fill_color
                changed = True
        if not changed:
            raise ValueError("same_shape_component_lattice_completion made no changes")
        return output

    if object == "matching_edge_marker_row_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("matching_edge_marker_row_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("matching_edge_marker_row_fill requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        output = [row[:] for row in grid]
        for row, values in enumerate(grid):
            edge_color = values[0]
            if edge_color != background_color and values[-1] == edge_color:
                for col in range(cols):
                    output[row][col] = edge_color
        return output

    if object == "project_markers_to_rectangular_object":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("project_markers_to_rectangular_object requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_markers_to_rectangular_object requires a rectangular grid")
        counts = {}
        for row in grid:
            for value in row:
                counts[value] = counts.get(value, 0) + 1
        background_color = max(counts, key=lambda value: (counts[value], -value))

        visited = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color or (row, col) in visited:
                    continue
                stack = [(row, col)]
                visited.add((row, col))
                pixels = []
                while stack:
                    current_row, current_col = stack.pop()
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
                        stack.append((next_row, next_col))
                min_row = min(pixel_row for pixel_row, _ in pixels)
                max_row = max(pixel_row for pixel_row, _ in pixels)
                min_col = min(pixel_col for _, pixel_col in pixels)
                max_col = max(pixel_col for _, pixel_col in pixels)
                area = (max_row - min_row + 1) * (max_col - min_col + 1)
                is_solid_rectangle = area == len(pixels) and area > 1
                components.append((len(pixels), value, pixels, min_row, max_row, min_col, max_col, is_solid_rectangle))

        rectangle_components = [component for component in components if component[-1]]
        if not rectangle_components:
            raise ValueError("project_markers_to_rectangular_object found no rectangular object")
        rectangle_components.sort(key=lambda component: component[0], reverse=True)
        if len(rectangle_components) > 1 and rectangle_components[0][0] == rectangle_components[1][0]:
            raise ValueError("project_markers_to_rectangular_object requires a unique largest rectangle")
        _, rectangle_color, rectangle_pixels, min_row, max_row, min_col, max_col, _ = rectangle_components[0]
        rectangle_set = set(rectangle_pixels)
        marker_pixels = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color and (row, col) not in rectangle_set
        ]
        marker_colors = {value for _, _, value in marker_pixels}
        if len(marker_colors) != 1 or rectangle_color in marker_colors:
            raise ValueError("project_markers_to_rectangular_object requires one marker color outside the rectangle")
        marker_color = next(iter(marker_colors))

        output = [row[:] for row in grid]
        changed = False

        def paint(row, col):
            nonlocal changed
            if output[row][col] == background_color:
                output[row][col] = marker_color
                changed = True

        for row, col, _ in marker_pixels:
            if min_row <= row <= max_row:
                if col < min_col:
                    for paint_col in range(col, min_col):
                        paint(row, paint_col)
                elif col > max_col:
                    for paint_col in range(max_col + 1, col + 1):
                        paint(row, paint_col)
            if min_col <= col <= max_col:
                if row < min_row:
                    for paint_row in range(row, min_row):
                        paint(paint_row, col)
                elif row > max_row:
                    for paint_row in range(max_row + 1, row + 1):
                        paint(paint_row, col)

        if not changed:
            raise ValueError("project_markers_to_rectangular_object produced no projection")
        return output

    if object == "move_inner_markers_to_outer_opposite_corners":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("move_inner_markers_to_outer_opposite_corners requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("move_inner_markers_to_outer_opposite_corners requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        frame_candidates = []
        for candidate_color in sorted({
            value for row in grid for value in row if value != background_color
        }):
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
            if max_row - min_row < 2 or max_col - min_col < 2:
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
            frame_candidates.append((len(border), candidate_color, min_row, max_row, min_col, max_col))
        if len(frame_candidates) != 1:
            raise ValueError("move_inner_markers_to_outer_opposite_corners requires one hollow frame")

        _, frame_color, min_row, max_row, min_col, max_col = frame_candidates[0]
        top_outer = min_row - 1
        bottom_outer = max_row + 1
        left_outer = min_col - 1
        right_outer = max_col + 1
        if not (0 <= top_outer < rows and 0 <= bottom_outer < rows and 0 <= left_outer < cols and 0 <= right_outer < cols):
            raise ValueError("move_inner_markers_to_outer_opposite_corners requires exterior corner cells")

        markers = [
            (row, col, grid[row][col])
            for row in range(min_row + 1, max_row)
            for col in range(min_col + 1, max_col)
            if grid[row][col] not in (background_color, frame_color)
        ]
        if not markers:
            raise ValueError("move_inner_markers_to_outer_opposite_corners requires inner markers")

        output = [row[:] for row in grid]
        destinations = {}
        for row, col, marker_color in markers:
            output[row][col] = background_color
            dest_row = bottom_outer if (row - min_row) <= (max_row - row) else top_outer
            dest_col = right_outer if (col - min_col) <= (max_col - col) else left_outer
            if (dest_row, dest_col) in destinations:
                raise ValueError("move_inner_markers_to_outer_opposite_corners found ambiguous marker quadrant")
            destinations[(dest_row, dest_col)] = marker_color

        for (row, col), marker_color in destinations.items():
            if output[row][col] != background_color:
                raise ValueError("move_inner_markers_to_outer_opposite_corners destination is occupied")
            output[row][col] = marker_color
        return output

    if object == "two_by_two_distinct_count_shadow":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("two_by_two_distinct_count_shadow requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("two_by_two_distinct_count_shadow requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        fill_color = color
        if fill_color in (None, background_color):
            raise ValueError("two_by_two_distinct_count_shadow requires a fill color")

        blocks = []
        for row in range(rows - 1):
            for col in range(cols - 1):
                values = [
                    grid[row][col],
                    grid[row][col + 1],
                    grid[row + 1][col],
                    grid[row + 1][col + 1],
                ]
                if all(value not in (background_color, fill_color) for value in values):
                    # Keep only maximal 2x2 source blocks; larger solid regions
                    # or overlapping windows are outside this compact pattern.
                    touches_source = any(
                        0 <= neighbor_row < rows
                        and 0 <= neighbor_col < cols
                        and grid[neighbor_row][neighbor_col] not in (background_color, fill_color)
                        for neighbor_row, neighbor_col in (
                            (row - 1, col),
                            (row - 1, col + 1),
                            (row + 2, col),
                            (row + 2, col + 1),
                            (row, col - 1),
                            (row + 1, col - 1),
                            (row, col + 2),
                            (row + 1, col + 2),
                        )
                    )
                    if not touches_source:
                        blocks.append((row, col, len(set(values))))
        if not blocks:
            raise ValueError("two_by_two_distinct_count_shadow found no 2x2 source blocks")

        occupied = set()
        for row, col, _ in blocks:
            for block_row in (row, row + 1):
                for block_col in (col, col + 1):
                    if (block_row, block_col) in occupied:
                        raise ValueError("two_by_two_distinct_count_shadow found overlapping blocks")
                    occupied.add((block_row, block_col))

        output = [row[:] for row in grid]
        changed = False
        for row, col, height in blocks:
            for shadow_row in range(row + 2, min(rows, row + 2 + height)):
                for shadow_col in (col, col + 1):
                    if output[shadow_row][shadow_col] == background_color:
                        output[shadow_row][shadow_col] = fill_color
                        changed = True
        if not changed:
            raise ValueError("two_by_two_distinct_count_shadow produced no change")
        return output

    if object == "empty_square_spiral":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0 or rows != cols:
            raise ValueError("empty_square_spiral requires a non-empty square grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("empty_square_spiral requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        fill_color = color
        if fill_color in (None, background_color):
            raise ValueError("empty_square_spiral requires a non-background fill color")
        if any(value != background_color for row in grid for value in row):
            raise ValueError("empty_square_spiral expects an empty background grid")

        n = rows
        output = [row[:] for row in grid]
        layer = 0
        while True:
            top = 2 * layer
            if top >= n:
                break
            if layer == 0:
                left = 0
                right = n - 1
                bottom = n - 1
            else:
                left = 2 * layer - 2
                right = n - 1 - 2 * layer
                bottom = n - 1 - 2 * layer

            if left <= right:
                for col in range(left, right + 1):
                    output[top][col] = fill_color
            if top <= bottom and 0 <= right < n:
                for row in range(top, bottom + 1):
                    output[row][right] = fill_color
            bottom_left = 0 if layer == 0 else 2 * layer
            if top <= bottom and bottom_left <= right:
                for col in range(bottom_left, right + 1):
                    output[bottom][col] = fill_color
            vertical_col = 0 if layer == 0 else 2 * layer
            if 0 <= vertical_col < n:
                for row in range(top + 2, bottom + 1):
                    output[row][vertical_col] = fill_color
            layer += 1
        return output

    if object == "orthogonal_skeleton_gap_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("orthogonal_skeleton_gap_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("orthogonal_skeleton_gap_fill requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        fill_color = color
        if fill_color in (None, background_color):
            raise ValueError("orthogonal_skeleton_gap_fill requires a fill color")
        source_colors = sorted({
            value
            for row in grid
            for value in row
            if value not in (background_color, fill_color)
        })
        if len(source_colors) != 1:
            raise ValueError("orthogonal_skeleton_gap_fill requires one source color")
        source_color = source_colors[0]

        active_rows = [
            row
            for row in range(rows)
            if any(
                grid[row][col] == source_color and grid[row][col + 1] == source_color
                for col in range(cols - 1)
            )
        ]
        active_cols = [
            col
            for col in range(cols)
            if any(
                grid[row][col] == source_color and grid[row + 1][col] == source_color
                for row in range(rows - 1)
            )
        ]
        if not active_rows or not active_cols:
            raise ValueError("orthogonal_skeleton_gap_fill requires active rows and columns")

        min_row, max_row = min(active_rows), max(active_rows)
        min_col, max_col = min(active_cols), max(active_cols)
        output = [row[:] for row in grid]
        changed = False
        for row in active_rows:
            for col in range(min_col, max_col + 1):
                if output[row][col] == background_color:
                    output[row][col] = fill_color
                    changed = True
        for col in active_cols:
            for row in range(min_row, max_row + 1):
                if output[row][col] == background_color:
                    output[row][col] = fill_color
                    changed = True
        if not changed:
            raise ValueError("orthogonal_skeleton_gap_fill produced no change")
        return output

    if object == "left_line_antidiagonal_bottom":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0 or rows != cols:
            raise ValueError("left_line_antidiagonal_bottom requires a non-empty square grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("left_line_antidiagonal_bottom requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        left_values = [grid[row][0] for row in range(rows)]
        line_color = left_values[0]
        if line_color == background_color or any(value != line_color for value in left_values):
            raise ValueError("left_line_antidiagonal_bottom requires a solid non-background left line")
        if any(
            grid[row][col] != background_color
            for row in range(rows)
            for col in range(1, cols)
        ):
            raise ValueError("left_line_antidiagonal_bottom expects empty cells off the left line")

        output = [row[:] for row in grid]
        for row in range(rows - 1):
            output[row][cols - 1 - row] = 2
        for col in range(1, cols):
            output[rows - 1][col] = 4
        return output

    if object == "single_marker_diagonal_staircase":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("single_marker_diagonal_staircase requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("single_marker_diagonal_staircase requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        fill_color = color
        if fill_color in (None, background_color):
            raise ValueError("single_marker_diagonal_staircase requires a fill color")
        markers = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if len(markers) != 1:
            raise ValueError("single_marker_diagonal_staircase requires one marker")
        marker_row, marker_col = markers[0]
        output = [row[:] for row in grid]

        def paint(row, start_col, end_col):
            if not (0 <= row < rows):
                return
            for col in range(start_col, end_col + 1):
                if 0 <= col < cols and output[row][col] == background_color:
                    output[row][col] = fill_color

        for step in range(1, rows + cols + 1):
            up_row = marker_row - step
            down_row = marker_row + step
            if up_row < 0 and down_row >= rows:
                break

            if step % 2 == 1:
                offset = 2 * ((step - 1) // 2)
                paint(up_row, marker_col + offset, marker_col + offset)
                paint(down_row, marker_col - offset, marker_col - offset)
            else:
                offset = 2 * (step // 2 - 1)
                paint(up_row, marker_col + offset, marker_col + offset + 2)
                paint(down_row, marker_col - offset - 2, marker_col - offset)
        if output == grid:
            raise ValueError("single_marker_diagonal_staircase produced no change")
        return output

    if object == "right_triangle_marker_center_projection":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("right_triangle_marker_center_projection requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("right_triangle_marker_center_projection requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        center_color = color
        if not isinstance(center_color, int) or center_color == background_color:
            raise ValueError("right_triangle_marker_center_projection requires a center color")

        markers = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if len(markers) != 3:
            raise ValueError("right_triangle_marker_center_projection requires three markers")
        if len({marker_color for _, _, marker_color in markers}) != 3:
            raise ValueError("right_triangle_marker_center_projection requires distinct marker colors")

        min_row = min(row for row, _, _ in markers)
        max_row = max(row for row, _, _ in markers)
        min_col = min(col for _, col, _ in markers)
        max_col = max(col for _, col, _ in markers)
        side = max_row - min_row
        if side < 4 or side != max_col - min_col or side % 2 != 0:
            raise ValueError("right_triangle_marker_center_projection requires an even square marker bbox")

        corner_positions = {
            (min_row, min_col),
            (min_row, max_col),
            (max_row, min_col),
            (max_row, max_col),
        }
        marker_positions = {(row, col) for row, col, _ in markers}
        if len(marker_positions) != 3 or not marker_positions.issubset(corner_positions):
            raise ValueError("right_triangle_marker_center_projection requires three bbox-corner markers")

        center_row = min_row + side // 2
        center_col = min_col + side // 2
        if not (0 <= center_row < rows and 0 <= center_col < cols):
            raise ValueError("right_triangle_marker_center_projection center is out of bounds")
        if grid[center_row][center_col] != background_color:
            raise ValueError("right_triangle_marker_center_projection requires an empty center")

        offset = side // 2 - 1
        if offset < 1:
            raise ValueError("right_triangle_marker_center_projection requires a non-trivial projection offset")

        output = [row[:] for row in grid]
        changed = False
        for marker_row, marker_col, marker_color in markers:
            row_dir = 1 if center_row > marker_row else -1
            col_dir = 1 if center_col > marker_col else -1
            target_row = marker_row + row_dir * offset
            target_col = marker_col + col_dir * offset
            if (target_row, target_col) == (center_row, center_col):
                raise ValueError("right_triangle_marker_center_projection marker projection collided with center")
            if not (0 <= target_row < rows and 0 <= target_col < cols):
                raise ValueError("right_triangle_marker_center_projection target is out of bounds")
            if output[target_row][target_col] != background_color:
                raise ValueError("right_triangle_marker_center_projection target is occupied")
            output[target_row][target_col] = marker_color
            changed = True

        output[center_row][center_col] = center_color
        changed = True
        if not changed:
            raise ValueError("right_triangle_marker_center_projection produced no change")
        return output

    if object == "top_row_neighbor_alternating_rows":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("top_row_neighbor_alternating_rows requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("top_row_neighbor_alternating_rows requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        top_markers = [
            (col, grid[0][col])
            for col in range(cols)
            if grid[0][col] != background_color
        ]
        if not top_markers:
            raise ValueError("top_row_neighbor_alternating_rows requires top-row markers")
        if any(
            grid[row][col] != background_color
            for row in range(1, rows)
            for col in range(cols)
        ):
            raise ValueError("top_row_neighbor_alternating_rows expects empty lower rows")

        neighbor_row = [background_color for _ in range(cols)]
        for col, marker_color in top_markers:
            for target_col in (col - 1, col + 1):
                if 0 <= target_col < cols:
                    neighbor_row[target_col] = marker_color
        top_row = grid[0][:]
        return [
            top_row[:] if row % 2 == 0 else neighbor_row[:]
            for row in range(rows)
        ]

    if object == "separator_lattice_three_region_labels":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_lattice_three_region_labels requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_lattice_three_region_labels requires a rectangular grid")
        separator_color = color
        background_color = 0 if color1 is None else color1
        if separator_color in (None, background_color):
            raise ValueError("separator_lattice_three_region_labels requires a separator color")

        full_rows = [
            row
            for row in range(rows)
            if all(grid[row][col] == separator_color for col in range(cols))
        ]
        if len(full_rows) < 2:
            raise ValueError("separator_lattice_three_region_labels requires at least two separator rows")

        non_separator_rows = [row for row in range(rows) if row not in set(full_rows)]
        vertical_cols = [
            col
            for col in range(cols)
            if all(grid[row][col] == separator_color for row in non_separator_rows)
        ]
        if len(vertical_cols) < 2:
            raise ValueError("separator_lattice_three_region_labels requires at least two separator columns")

        mid_row_index = len(full_rows) // 2
        mid_col_index = len(vertical_cols) // 2
        top_row_end = full_rows[0]
        bottom_row_start = full_rows[-1] + 1
        left_col_end = vertical_cols[0]
        right_col_start = vertical_cols[-1] + 1
        middle_row_start = full_rows[mid_row_index - 1] + 1
        middle_row_end = full_rows[mid_row_index]
        middle_col_start = vertical_cols[mid_col_index - 1] + 1
        middle_col_end = vertical_cols[mid_col_index]

        output = [row[:] for row in grid]

        def paint(row_start, row_end, col_start, col_end, fill_color):
            for row in range(row_start, row_end):
                for col in range(col_start, col_end):
                    if output[row][col] == background_color:
                        output[row][col] = fill_color

        paint(0, top_row_end, 0, left_col_end, 1)
        paint(middle_row_start, middle_row_end, middle_col_start, middle_col_end, 2)
        paint(bottom_row_start, rows, right_col_start, cols, 3)
        return output

    if object == "separator_lattice_max_marker_regions":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_lattice_max_marker_regions requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_lattice_max_marker_regions requires a rectangular grid")
        separator_color = color
        background_color = 0 if color1 is None else color1
        if separator_color in (None, background_color):
            raise ValueError("separator_lattice_max_marker_regions requires a separator color")

        full_rows = [
            row
            for row in range(rows)
            if all(grid[row][col] == separator_color for col in range(cols))
        ]
        if not full_rows:
            raise ValueError("separator_lattice_max_marker_regions requires separator rows")
        full_row_set = set(full_rows)
        non_separator_rows = [row for row in range(rows) if row not in full_row_set]
        if not non_separator_rows:
            raise ValueError("separator_lattice_max_marker_regions requires data rows")

        min_separator_hits = max(2, len(non_separator_rows) // 2 + 1)
        vertical_cols = [
            col
            for col in range(cols)
            if sum(grid[row][col] == separator_color for row in non_separator_rows) >= min_separator_hits
        ]
        if not vertical_cols:
            raise ValueError("separator_lattice_max_marker_regions requires separator columns")

        def spans_from_separators(limit, separators):
            spans = []
            start = 0
            for separator in sorted(separators):
                if start < separator:
                    spans.append((start, separator))
                start = separator + 1
            if start < limit:
                spans.append((start, limit))
            return spans

        row_spans = spans_from_separators(rows, full_rows)
        col_spans = spans_from_separators(cols, vertical_cols)
        if not row_spans or not col_spans:
            raise ValueError("separator_lattice_max_marker_regions requires non-empty cells")

        marker_colors = set()
        counts = {}
        for row_start, row_end in row_spans:
            for col_start, col_end in col_spans:
                cell_counts = {}
                for row in range(row_start, row_end):
                    for col in range(col_start, col_end):
                        value = grid[row][col]
                        if value in (background_color, separator_color):
                            continue
                        marker_colors.add(value)
                        cell_counts[value] = cell_counts.get(value, 0) + 1
                counts[(row_start, row_end, col_start, col_end)] = cell_counts
        if len(marker_colors) != 1:
            raise ValueError("separator_lattice_max_marker_regions requires one marker color")
        marker_color = next(iter(marker_colors))
        max_count = max(
            (cell_counts.get(marker_color, 0) for cell_counts in counts.values()),
            default=0,
        )
        if max_count == 0:
            raise ValueError("separator_lattice_max_marker_regions requires markers")

        output = [[background_color for _ in range(cols)] for _ in range(rows)]
        for row in full_rows:
            for col in range(cols):
                output[row][col] = separator_color
        for col in vertical_cols:
            for row in range(rows):
                output[row][col] = separator_color

        for row_start, row_end, col_start, col_end in counts:
            if counts[(row_start, row_end, col_start, col_end)].get(marker_color, 0) != max_count:
                continue
            for row in range(row_start, row_end):
                for col in range(col_start, col_end):
                    output[row][col] = marker_color
        return output

    if object == "opposite_corner_projection":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("opposite_corner_projection requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("opposite_corner_projection requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        foreground = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if len(foreground) != 4:
            raise ValueError("opposite_corner_projection requires exactly four source pixels")
        min_row = min(row for row, _ in foreground)
        max_row = max(row for row, _ in foreground)
        min_col = min(col for _, col in foreground)
        max_col = max(col for _, col in foreground)
        if max_row - min_row != 1 or max_col - min_col != 1:
            raise ValueError("opposite_corner_projection requires a 2x2 source block")
        if any(
            grid[row][col] == background_color
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
        ):
            raise ValueError("opposite_corner_projection requires a complete 2x2 block")

        top_rows = range(max(0, min_row - 2), min_row)
        bottom_rows = range(max_row + 1, min(rows, max_row + 3))
        left_cols = range(0, min(2, min_col))
        right_start = min(max_col + 1, max(0, cols - 2))
        right_cols = range(right_start, min(cols, right_start + 2))
        placements = [
            (top_rows, left_cols, grid[max_row][max_col]),
            (top_rows, right_cols, grid[max_row][min_col]),
            (bottom_rows, left_cols, grid[min_row][max_col]),
            (bottom_rows, right_cols, grid[min_row][min_col]),
        ]

        output = [row[:] for row in grid]
        changed = False
        for row_span, col_span, fill_color in placements:
            for row in row_span:
                for col in col_span:
                    if output[row][col] != background_color:
                        raise ValueError("opposite_corner_projection target region is not empty")
                    output[row][col] = fill_color
                    changed = True
        if not changed:
            raise ValueError("opposite_corner_projection produced no change")
        return output

    if object == "largest_background_rectangle":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("largest_background_rectangle requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("largest_background_rectangle requires a rectangular grid")
        fill_color = color
        background_color = 0 if color1 is None else color1
        if fill_color in (None, background_color):
            raise ValueError("largest_background_rectangle requires a non-background fill color")
        if any(value == fill_color for row in grid for value in row):
            raise ValueError("largest_background_rectangle expects a newly inserted fill color")

        best = None
        heights = [0 for _ in range(cols)]
        for bottom in range(rows):
            for col in range(cols):
                heights[col] = heights[col] + 1 if grid[bottom][col] == background_color else 0

            stack = []
            for col in range(cols + 1):
                height = heights[col] if col < cols else 0
                start = col
                while stack and stack[-1][1] > height:
                    left, rect_height = stack.pop()
                    start = left
                    width = col - left
                    if rect_height > 1 and width > 1:
                        top = bottom - rect_height + 1
                        area = rect_height * width
                        candidate_key = (area, -top, -left, rect_height, width)
                        if best is None or candidate_key > best[0]:
                            best = (candidate_key, top, bottom, left, col - 1)
                if not stack or stack[-1][1] < height:
                    stack.append((start, height))

        if best is None:
            raise ValueError("largest_background_rectangle found no rectangle")
        _, top, bottom, left, right = best
        output = [row[:] for row in grid]
        for row in range(top, bottom + 1):
            for col in range(left, right + 1):
                output[row][col] = fill_color
        return output

    if object == "separator_pattern_rotations":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_pattern_rotations requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_pattern_rotations requires a rectangular grid")
        separator_color = color
        background_color = 0 if color1 is None else color1
        if separator_color in (None, background_color):
            raise ValueError("separator_pattern_rotations requires a non-background separator")

        separator_cols = [
            col
            for col in range(1, cols - 1)
            if all(grid[row][col] == separator_color for row in range(rows))
        ]
        if len(separator_cols) != 2:
            raise ValueError("separator_pattern_rotations requires two separator columns")

        bounds = [-1] + separator_cols + [cols]
        col_spans = [
            (bounds[index] + 1, bounds[index + 1])
            for index in range(len(bounds) - 1)
            if bounds[index] + 1 < bounds[index + 1]
        ]
        if len(col_spans) != 3:
            raise ValueError("separator_pattern_rotations requires three cells")
        widths = [end - start for start, end in col_spans]
        if len(set(widths)) != 1 or widths[0] != rows:
            raise ValueError("separator_pattern_rotations requires square cells")

        def cell_values(span):
            start, end = span
            return [row[start:end] for row in grid]

        source = cell_values(col_spans[0])
        if any(value in (background_color, separator_color) for row in source for value in row):
            raise ValueError("separator_pattern_rotations requires a complete source pattern")
        for span in col_spans[1:]:
            if any(
                grid[row][col] != background_color
                for row in range(rows)
                for col in range(span[0], span[1])
            ):
                raise ValueError("separator_pattern_rotations requires empty target cells")

        size = rows
        rotated_90 = [
            [source[size - 1 - col][row] for col in range(size)]
            for row in range(size)
        ]
        rotated_180 = [
            [source[size - 1 - row][size - 1 - col] for col in range(size)]
            for row in range(size)
        ]

        output = [row[:] for row in grid]
        for pattern, (col_start, _) in zip((rotated_90, rotated_180), col_spans[1:]):
            for row in range(size):
                for col in range(size):
                    output[row][col_start + col] = pattern[row][col]
        return output

    if object == "project_diagonal_through_frame_corners":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("project_diagonal_through_frame_corners requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_diagonal_through_frame_corners requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        non_background_colors = sorted({
            value
            for row in grid
            for value in row
            if value != background_color
        })

        def corners_for(frame_color):
            corners = set()
            for row in range(rows):
                for col in range(cols):
                    if grid[row][col] != frame_color:
                        continue
                    has_vertical = (
                        (row > 0 and grid[row - 1][col] == frame_color)
                        or (row + 1 < rows and grid[row + 1][col] == frame_color)
                    )
                    has_horizontal = (
                        (col > 0 and grid[row][col - 1] == frame_color)
                        or (col + 1 < cols and grid[row][col + 1] == frame_color)
                    )
                    if has_vertical and has_horizontal:
                        corners.add((row, col))
            return corners

        def max_run_for(candidate):
            max_run = 0
            for row in range(rows):
                run = 0
                for col in range(cols):
                    run = run + 1 if grid[row][col] == candidate else 0
                    max_run = max(max_run, run)
            for col in range(cols):
                run = 0
                for row in range(rows):
                    run = run + 1 if grid[row][col] == candidate else 0
                    max_run = max(max_run, run)
            return max_run

        if color == "input_non_background":
            frame_candidates = [
                (max_run_for(candidate), len(corners_for(candidate)), candidate, corners_for(candidate))
                for candidate in non_background_colors
            ]
            frame_candidates = [
                item for item in frame_candidates
                if item[1] > 0
            ]
            if not frame_candidates:
                raise ValueError("project_diagonal_through_frame_corners requires one frame color")
            best_run = max(item[0] for item in frame_candidates)
            frame_candidates = [
                item for item in frame_candidates
                if item[0] == best_run
            ]
            if len(frame_candidates) != 1:
                raise ValueError("project_diagonal_through_frame_corners requires one dominant frame color")
            _, _, frame_color, frame_corners = frame_candidates[0]
            object_colors = [
                candidate
                for candidate in non_background_colors
                if candidate != frame_color
            ]
            if len(object_colors) != 1:
                raise ValueError("project_diagonal_through_frame_corners requires one object color")
            object_color = object_colors[0]
        else:
            object_color = color
            if object_color in (None, background_color):
                raise ValueError("project_diagonal_through_frame_corners requires an object color")
            frame_colors = [
                value
                for value in non_background_colors
                if value != object_color
            ]
            if len(frame_colors) != 1:
                raise ValueError("project_diagonal_through_frame_corners requires one frame color")
            frame_color = frame_colors[0]
            frame_corners = corners_for(frame_color)
        if not frame_corners:
            raise ValueError("project_diagonal_through_frame_corners found no frame corners")

        object_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == object_color
        ]
        if not object_pixels:
            raise ValueError("project_diagonal_through_frame_corners found no object pixels")

        output = [row[:] for row in grid]
        changed = False
        for start_row, start_col in object_pixels:
            for delta_row, delta_col in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                row = start_row + delta_row
                col = start_col + delta_col
                while 0 <= row < rows and 0 <= col < cols:
                    value = grid[row][col]
                    if (row, col) in frame_corners:
                        paint_row = row + delta_row
                        paint_col = col + delta_col
                        while 0 <= paint_row < rows and 0 <= paint_col < cols:
                            if output[paint_row][paint_col] != background_color:
                                break
                            output[paint_row][paint_col] = object_color
                            changed = True
                            paint_row += delta_row
                            paint_col += delta_col
                        break
                    if value not in (background_color, object_color):
                        break
                    row += delta_row
                    col += delta_col
        if not changed:
            raise ValueError("project_diagonal_through_frame_corners produced no change")
        return output

    if object == "separator_block_value_plus5_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_block_value_plus5_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_block_value_plus5_fill requires a rectangular grid")

        separator_color = color if color not in (None, 0) else 5
        output = [row[:] for row in grid]
        full_separator_rows = {
            row
            for row in range(rows)
            if all(grid[row][col] == separator_color for col in range(cols))
        }
        row_segments = []
        start = 0
        for row in range(rows + 1):
            if row == rows or row in full_separator_rows:
                if start < row:
                    row_segments.append((start, row))
                start = row + 1

        for row_start, row_end in row_segments:
            full_separator_cols = {
                col
                for col in range(cols)
                if all(grid[row][col] == separator_color for row in range(row_start, row_end))
            }
            col_segments = []
            start = 0
            for col in range(cols + 1):
                if col == cols or col in full_separator_cols:
                    if start < col:
                        col_segments.append((start, col))
                    start = col + 1
            if not col_segments:
                raise ValueError("separator_block_value_plus5_fill found no column segments")

            for col_start, col_end in col_segments:
                markers = {
                    grid[row][col]
                    for row in range(row_start, row_end)
                    for col in range(col_start, col_end)
                    if grid[row][col] not in (0, separator_color)
                }
                if len(markers) != 1:
                    raise ValueError("separator_block_value_plus5_fill requires one marker per block")
                fill_value = next(iter(markers)) + 5
                for row in range(row_start, row_end):
                    for col in range(col_start, col_end):
                        output[row][col] = fill_value
        return output

    if object == "top_row_color_cycle_below_separator":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("top_row_color_cycle_below_separator requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("top_row_color_cycle_below_separator requires a rectangular grid")

        separator_rows = [
            row
            for row in range(1, rows)
            if grid[row][0] != 0 and all(grid[row][col] == grid[row][0] for col in range(cols))
        ]
        if not separator_rows:
            raise ValueError("top_row_color_cycle_below_separator requires a solid separator row")
        separator_row = separator_rows[0]
        if separator_row == 0:
            raise ValueError("top_row_color_cycle_below_separator requires a header above separator")
        header = grid[separator_row - 1]
        if any(value == 0 for value in header):
            raise ValueError("top_row_color_cycle_below_separator requires a nonzero header row")
        output = [row[:] for row in grid]
        for row in range(separator_row + 1, rows):
            value = header[(row - separator_row - 1) % cols]
            output[row] = [value for _ in range(cols)]
        return output

    if object == "copy_hollow_rectangle_to_partial_frame":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("copy_hollow_rectangle_to_partial_frame requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("copy_hollow_rectangle_to_partial_frame requires a rectangular grid")

        requested_color = None if color in (None, 0) else color

        def border_cells(top, left, height, width):
            return {
                (row, col)
                for row in range(top, top + height)
                for col in range(left, left + width)
                if row in (top, top + height - 1) or col in (left, left + width - 1)
            }

        visited = set()
        hollow_rectangles = []
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == 0 or (requested_color is not None and value != requested_color):
                    continue
                if (row, col) in visited:
                    continue
                stack = [(row, col)]
                visited.add((row, col))
                pixels = []
                while stack:
                    current_row, current_col = stack.pop()
                    pixels.append((current_row, current_col))
                    for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        next_row = current_row + delta_row
                        next_col = current_col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited:
                            continue
                        if grid[next_row][next_col] != value:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                min_row = min(row for row, _ in pixels)
                max_row = max(row for row, _ in pixels)
                min_col = min(col for _, col in pixels)
                max_col = max(col for _, col in pixels)
                height = max_row - min_row + 1
                width = max_col - min_col + 1
                if height < 3 or width < 3:
                    continue
                expected = border_cells(min_row, min_col, height, width)
                if set(pixels) == expected:
                    hollow_rectangles.append((value, min_row, min_col, height, width))

        if len(hollow_rectangles) != 1:
            raise ValueError("copy_hollow_rectangle_to_partial_frame requires a unique source hollow rectangle")
        source_color, source_row, source_col, height, width = hollow_rectangles[0]
        border = border_cells(0, 0, height, width)
        interior = {
            (row, col)
            for row in range(1, height - 1)
            for col in range(1, width - 1)
        }
        border_size = len(border)

        candidates = []
        for top in range(0, rows - height + 1):
            for left in range(0, cols - width + 1):
                if top == source_row and left == source_col:
                    continue
                if not all(grid[top + row][left + col] == 0 for row, col in interior):
                    continue
                border_values = [
                    grid[top + row][left + col]
                    for row, col in border
                ]
                nonzero_count = sum(value != 0 for value in border_values)
                source_count = sum(value == source_color for value in border_values)
                if nonzero_count < max(2, border_size // 2):
                    continue
                if source_count == border_size:
                    continue
                candidates.append((nonzero_count, -source_count, -top, -left, top, left))

        if not candidates:
            raise ValueError("copy_hollow_rectangle_to_partial_frame found no target partial frame")
        _, _, _, _, target_row, target_col = max(candidates)

        output = [row[:] for row in grid]
        for row, col in border:
            output[target_row + row][target_col + col] = source_color
        return output

    if object == "complete_diagonal_counterpart_blocks":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("complete_diagonal_counterpart_blocks requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("complete_diagonal_counterpart_blocks requires a rectangular grid")
        fill_color = color
        if fill_color in (None, 0):
            raise ValueError("complete_diagonal_counterpart_blocks requires a fill color")

        object_colors = sorted({
            value
            for row in grid
            for value in row
            if value not in (0, fill_color)
        })
        if len(object_colors) != 1:
            raise ValueError("complete_diagonal_counterpart_blocks requires one object color")
        object_color = object_colors[0]

        visited = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != object_color or (row, col) in visited:
                    continue
                stack = [(row, col)]
                visited.add((row, col))
                pixels = []
                while stack:
                    current_row, current_col = stack.pop()
                    pixels.append((current_row, current_col))
                    for delta_row, delta_col in (
                        (-1, -1), (-1, 0), (-1, 1),
                        (0, -1),           (0, 1),
                        (1, -1),  (1, 0),  (1, 1),
                    ):
                        next_row = current_row + delta_row
                        next_col = current_col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited:
                            continue
                        if grid[next_row][next_col] != object_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                min_row = min(row for row, _ in pixels)
                max_row = max(row for row, _ in pixels)
                min_col = min(col for _, col in pixels)
                max_col = max(col for _, col in pixels)
                components.append({
                    "pixels": set(pixels),
                    "min_row": min_row,
                    "max_row": max_row,
                    "min_col": min_col,
                    "max_col": max_col,
                    "height": max_row - min_row + 1,
                    "width": max_col - min_col + 1,
                })

        if not components:
            raise ValueError("complete_diagonal_counterpart_blocks found no components")

        output = [row[:] for row in grid]
        changed = False

        def paint_rect(start_row, start_col, height, width):
            nonlocal changed
            for row in range(start_row, start_row + height):
                for col in range(start_col, start_col + width):
                    if 0 <= row < rows and 0 <= col < cols:
                        if output[row][col] != fill_color:
                            changed = True
                        output[row][col] = fill_color

        all_diagonal_pairs = all(
            component["height"] == 2
            and component["width"] == 2
            and len(component["pixels"]) == 2
            for component in components
        )
        if all_diagonal_pairs:
            for component in components:
                r0, r1 = component["min_row"], component["max_row"]
                c0, c1 = component["min_col"], component["max_col"]
                pixels = component["pixels"]
                if {(r0, c0), (r1, c1)} == pixels:
                    candidates = [(r0 - 1, c1 + 1), (r1 + 1, c0 - 1)]
                elif {(r0, c1), (r1, c0)} == pixels:
                    candidates = [(r0 - 1, c0 - 1), (r1 + 1, c1 + 1)]
                else:
                    raise ValueError("complete_diagonal_counterpart_blocks found non-diagonal pair")
                for row, col in candidates:
                    if 0 <= row < rows and 0 <= col < cols:
                        if output[row][col] != fill_color:
                            changed = True
                        output[row][col] = fill_color
            if not changed:
                raise ValueError("complete_diagonal_counterpart_blocks produced no change")
            return output

        visited = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != object_color or (row, col) in visited:
                    continue
                stack = [(row, col)]
                visited.add((row, col))
                pixels = []
                while stack:
                    current_row, current_col = stack.pop()
                    pixels.append((current_row, current_col))
                    for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        next_row = current_row + delta_row
                        next_col = current_col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited:
                            continue
                        if grid[next_row][next_col] != object_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))
                min_row = min(row for row, _ in pixels)
                max_row = max(row for row, _ in pixels)
                min_col = min(col for _, col in pixels)
                max_col = max(col for _, col in pixels)
                components.append({
                    "pixels": set(pixels),
                    "min_row": min_row,
                    "max_row": max_row,
                    "min_col": min_col,
                    "max_col": max_col,
                    "height": max_row - min_row + 1,
                    "width": max_col - min_col + 1,
                })

        solid_rectangles = []
        for component in components:
            expected = {
                (row, col)
                for row in range(component["min_row"], component["max_row"] + 1)
                for col in range(component["min_col"], component["max_col"] + 1)
            }
            if component["pixels"] != expected:
                raise ValueError("complete_diagonal_counterpart_blocks expected solid rectangles")
            solid_rectangles.append(component)
        if len(solid_rectangles) != 2:
            raise ValueError("complete_diagonal_counterpart_blocks requires two solid rectangles")
        first, second = sorted(solid_rectangles, key=lambda comp: (comp["min_row"], comp["min_col"]))
        height = first["height"]
        width = first["width"]
        if second["height"] != height or second["width"] != width:
            raise ValueError("complete_diagonal_counterpart_blocks requires equal-size rectangles")
        row_delta = second["min_row"] - first["min_row"]
        col_delta = second["min_col"] - first["min_col"]
        if row_delta != height or abs(col_delta) != width:
            raise ValueError("complete_diagonal_counterpart_blocks requires adjacent diagonal rectangles")
        if col_delta < 0:
            # Existing rectangles occupy top-right and bottom-left cells.
            paint_rect(first["min_row"] - height, second["min_col"] - width, height, width)
            paint_rect(second["min_row"] + height, first["min_col"] + width, height, width)
        else:
            # Existing rectangles occupy top-left and bottom-right cells.
            paint_rect(first["min_row"] - height, second["min_col"] + width, height, width)
            paint_rect(second["min_row"] + height, first["min_col"] - width, height, width)
        if not changed:
            raise ValueError("complete_diagonal_counterpart_blocks produced no change")
        return output

    if object == "flood_fill_from_color":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("flood_fill_from_color requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("flood_fill_from_color requires a rectangular grid")
        if color in (None, 0):
            raise ValueError("flood_fill_from_color requires a non-background seed color")

        seeds = [
            (row, col)
            for row, values in enumerate(grid)
            for col, value in enumerate(values)
            if value == color
        ]
        if not seeds:
            raise ValueError("flood_fill_from_color found no seed pixels")

        output = [row[:] for row in grid]
        queue = list(seeds)
        visited = set(seeds)
        changed = False
        while queue:
            row, col = queue.pop(0)
            for next_row, next_col in (
                (row - 1, col),
                (row + 1, col),
                (row, col - 1),
                (row, col + 1),
            ):
                if not (0 <= next_row < rows and 0 <= next_col < cols):
                    continue
                if (next_row, next_col) in visited:
                    continue
                value = grid[next_row][next_col]
                if value not in (0, color):
                    continue
                visited.add((next_row, next_col))
                queue.append((next_row, next_col))
                if output[next_row][next_col] == 0:
                    output[next_row][next_col] = color
                    changed = True
        if not changed:
            raise ValueError("flood_fill_from_color produced no change")
        return output

    if object == "row_span_between_same_color_pairs":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("row_span_between_same_color_pairs requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("row_span_between_same_color_pairs requires a rectangular grid")

        target_color = None if color in (None, 0) else color
        output = [row[:] for row in grid]
        changed = False
        for row, values in enumerate(grid):
            row_colors = sorted({
                value
                for value in values
                if value != 0 and (target_color is None or value == target_color)
            })
            for row_color in row_colors:
                cols_with_color = [
                    col
                    for col, value in enumerate(values)
                    if value == row_color
                ]
                if len(cols_with_color) < 2:
                    continue
                start_col = min(cols_with_color)
                end_col = max(cols_with_color)
                if any(
                    values[col] not in (0, row_color)
                    for col in range(start_col, end_col + 1)
                ):
                    raise ValueError("row_span_between_same_color_pairs found conflicting span color")
                for col in range(start_col, end_col + 1):
                    if output[row][col] != row_color:
                        changed = True
                    output[row][col] = row_color
        if not changed:
            raise ValueError("row_span_between_same_color_pairs produced no change")
        return output

    if object == "two_marker_horizontal_frames":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows < 2 or cols < 2:
            raise ValueError("two_marker_horizontal_frames requires a non-trivial grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("two_marker_horizontal_frames requires a rectangular grid")

        markers = [
            (row, col, value)
            for row, values in enumerate(grid)
            for col, value in enumerate(values)
            if value != 0
        ]
        if len(markers) != 2:
            raise ValueError("two_marker_horizontal_frames requires exactly two marker pixels")
        markers = sorted(markers)
        (top_row, _, top_color), (bottom_row, _, bottom_color) = markers
        if top_color == bottom_color or top_row >= bottom_row:
            raise ValueError("two_marker_horizontal_frames requires distinct vertically ordered colors")

        split_row = (top_row + bottom_row) // 2
        output = [[0 for _ in range(cols)] for _ in range(rows)]

        def draw_region(start_row, end_row, marker_row, marker_color, full_edge_row):
            for row in range(start_row, end_row + 1):
                if row in (marker_row, full_edge_row):
                    output[row] = [marker_color for _ in range(cols)]
                else:
                    output[row][0] = marker_color
                    output[row][cols - 1] = marker_color

        draw_region(0, split_row, top_row, top_color, 0)
        draw_region(split_row + 1, rows - 1, bottom_row, bottom_color, rows - 1)
        return output

    if object == "project_edge_markers_into_rectangle":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("project_edge_markers_into_rectangle requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_edge_markers_into_rectangle requires a rectangular grid")
        target_color = color
        if target_color in (None, 0):
            non_background = [
                value
                for row in grid
                for value in row
                if value != 0
            ]
            if not non_background:
                raise ValueError("project_edge_markers_into_rectangle requires foreground")
            target_color = max(
                sorted(set(non_background)),
                key=lambda value: non_background.count(value),
            )

        target_pixels = [
            (row, col)
            for row, values in enumerate(grid)
            for col, value in enumerate(values)
            if value == target_color
        ]
        if not target_pixels:
            raise ValueError("project_edge_markers_into_rectangle requires target rectangle")
        min_row = min(row for row, _ in target_pixels)
        max_row = max(row for row, _ in target_pixels)
        min_col = min(col for _, col in target_pixels)
        max_col = max(col for _, col in target_pixels)
        rectangle_pixels = {
            (row, col)
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
        }
        if set(target_pixels) != rectangle_pixels:
            raise ValueError("project_edge_markers_into_rectangle target must be a solid rectangle")

        output = [row[:] for row in grid]
        projected = {}
        for row, values in enumerate(grid):
            for col, value in enumerate(values):
                if value in (0, target_color):
                    continue
                target = None
                if row < min_row and min_col <= col <= max_col:
                    target = (min_row, col)
                elif row > max_row and min_col <= col <= max_col:
                    target = (max_row, col)
                elif col < min_col and min_row <= row <= max_row:
                    target = (row, min_col)
                elif col > max_col and min_row <= row <= max_row:
                    target = (row, max_col)
                else:
                    raise ValueError("project_edge_markers_into_rectangle found unaligned marker")
                if target in projected and projected[target] != value:
                    raise ValueError("project_edge_markers_into_rectangle marker collision")
                projected[target] = value

        if not projected:
            raise ValueError("project_edge_markers_into_rectangle found no aligned markers")
        for (row, col), value in projected.items():
            output[row][col] = value
        return output

    if object == "project_marker_cross_to_frame_boundary":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("project_marker_cross_to_frame_boundary requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_marker_cross_to_frame_boundary requires a rectangular grid")

        background_color = 0 if color1 is None else color1
        colors = sorted({
            value
            for row in grid
            for value in row
            if value != background_color
        })
        if len(colors) != 2:
            raise ValueError("project_marker_cross_to_frame_boundary requires two foreground colors")

        frame_candidates = []
        for frame_color in colors:
            pixels = [
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] == frame_color
            ]
            if not pixels:
                continue
            min_row = min(row for row, _ in pixels)
            max_row = max(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            max_col = max(col for _, col in pixels)
            if max_row - min_row + 1 < 3 or max_col - min_col + 1 < 3:
                continue
            border = {
                (row, col)
                for row in range(min_row, max_row + 1)
                for col in range(min_col, max_col + 1)
                if row in (min_row, max_row) or col in (min_col, max_col)
            }
            if border and all(grid[row][col] == frame_color for row, col in border):
                frame_candidates.append((frame_color, min_row, max_row, min_col, max_col))

        if len(frame_candidates) != 1:
            raise ValueError("project_marker_cross_to_frame_boundary requires one rectangular frame")
        frame_color, min_row, max_row, min_col, max_col = frame_candidates[0]
        marker_colors = [candidate for candidate in colors if candidate != frame_color]
        if len(marker_colors) != 1:
            raise ValueError("project_marker_cross_to_frame_boundary requires one marker color")
        marker_color = marker_colors[0]

        marker_rows = [
            row
            for row in range(rows)
            if sum(1 for col in range(cols) if grid[row][col] == marker_color) >= cols - 2
        ]
        marker_cols = [
            col
            for col in range(cols)
            if sum(1 for row in range(rows) if grid[row][col] == marker_color) >= rows - 2
        ]
        if len(marker_rows) != 1 or len(marker_cols) != 1:
            raise ValueError("project_marker_cross_to_frame_boundary requires one marker row and column")
        marker_row = marker_rows[0]
        marker_col = marker_cols[0]
        if not (min_row < marker_row < max_row and min_col < marker_col < max_col):
            raise ValueError("project_marker_cross_to_frame_boundary marker cross must pass through frame interior")

        output = [row[:] for row in grid]
        changed = False
        for row in range(rows):
            for col in range(cols):
                if output[row][col] == marker_color:
                    output[row][col] = background_color
                    changed = True

        for col in list(range(0, min_col)) + list(range(max_col + 1, cols)):
            if output[min_row][col] != marker_color:
                output[min_row][col] = marker_color
                changed = True
        for row in list(range(0, min_row)) + list(range(max_row + 1, rows)):
            if output[row][max_col] != marker_color:
                output[row][max_col] = marker_color
                changed = True

        if not changed:
            raise ValueError("project_marker_cross_to_frame_boundary made no changes")
        return output

    if object == "frame_corner_marker_quadrant_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("frame_corner_marker_quadrant_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("frame_corner_marker_quadrant_fill requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        colors = sorted({
            value
            for row in grid
            for value in row
            if value != background_color
        })
        frame_candidates = []
        for frame_color in colors:
            cells = {
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] == frame_color
            }
            if not cells:
                continue
            min_row = min(row for row, _ in cells)
            max_row = max(row for row, _ in cells)
            min_col = min(col for _, col in cells)
            max_col = max(col for _, col in cells)
            if max_row - min_row < 3 or max_col - min_col < 3:
                continue
            border = {
                (row, col)
                for row in range(min_row, max_row + 1)
                for col in range(min_col, max_col + 1)
                if row in (min_row, max_row) or col in (min_col, max_col)
            }
            if cells != border:
                continue
            if any(
                grid[row][col] != background_color
                for row in range(min_row + 1, max_row)
                for col in range(min_col + 1, max_col)
            ):
                continue
            frame_candidates.append((frame_color, min_row, max_row, min_col, max_col))

        if len(frame_candidates) != 1:
            raise ValueError("frame_corner_marker_quadrant_fill requires one hollow frame")
        frame_color, min_row, max_row, min_col, max_col = frame_candidates[0]
        interior_height = max_row - min_row - 1
        interior_width = max_col - min_col - 1
        if (
            interior_height < 2
            or interior_width < 2
            or interior_height % 2 != 0
            or interior_width % 2 != 0
        ):
            raise ValueError("frame_corner_marker_quadrant_fill requires an even interior")

        corner_positions = {
            "TL": (min_row - 1, min_col - 1),
            "TR": (min_row - 1, max_col + 1),
            "BL": (max_row + 1, min_col - 1),
            "BR": (max_row + 1, max_col + 1),
        }
        corner_for_position = {
            position: corner
            for corner, position in corner_positions.items()
            if 0 <= position[0] < rows and 0 <= position[1] < cols
        }
        markers = []
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value in (background_color, frame_color):
                    continue
                corner = corner_for_position.get((row, col))
                if corner is None:
                    raise ValueError("frame_corner_marker_quadrant_fill found an unaligned marker")
                markers.append((corner, value))

        if len(markers) != 2:
            raise ValueError("frame_corner_marker_quadrant_fill requires exactly two markers")
        if markers[0][1] == markers[1][1]:
            raise ValueError("frame_corner_marker_quadrant_fill requires distinct marker colors")
        marker_corners = {corner for corner, _ in markers}
        if marker_corners in ({"TL", "BR"}, {"TR", "BL"}):
            raise ValueError("frame_corner_marker_quadrant_fill requires adjacent marker corners")

        opposite = {"TL": "BR", "BR": "TL", "TR": "BL", "BL": "TR"}
        quadrant_for_color = {}
        for corner, marker_color in markers:
            for quadrant in (corner, opposite[corner]):
                if quadrant in quadrant_for_color and quadrant_for_color[quadrant] != marker_color:
                    raise ValueError("frame_corner_marker_quadrant_fill found conflicting quadrant colors")
                quadrant_for_color[quadrant] = marker_color
        if set(quadrant_for_color) != {"TL", "TR", "BL", "BR"}:
            raise ValueError("frame_corner_marker_quadrant_fill did not bind every quadrant")

        row_mid = min_row + 1 + interior_height // 2
        col_mid = min_col + 1 + interior_width // 2
        quadrant_ranges = {
            "TL": (min_row + 1, row_mid, min_col + 1, col_mid),
            "TR": (min_row + 1, row_mid, col_mid, max_col),
            "BL": (row_mid, max_row, min_col + 1, col_mid),
            "BR": (row_mid, max_row, col_mid, max_col),
        }

        output = [row[:] for row in grid]
        changed = False
        for quadrant, fill_color in quadrant_for_color.items():
            start_row, end_row, start_col, end_col = quadrant_ranges[quadrant]
            for row in range(start_row, end_row):
                for col in range(start_col, end_col):
                    if output[row][col] != background_color:
                        raise ValueError("frame_corner_marker_quadrant_fill encountered a fill conflict")
                    output[row][col] = fill_color
                    changed = True
        if not changed:
            raise ValueError("frame_corner_marker_quadrant_fill made no changes")
        return output

    if object == "project_frame_side_colors_to_border":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows < 3 or cols < 3:
            raise ValueError("project_frame_side_colors_to_border requires a framed grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_frame_side_colors_to_border requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        top_color = grid[0][1]
        bottom_color = grid[rows - 1][1]
        left_color = grid[1][0]
        right_color = grid[1][cols - 1]
        side_colors = {top_color, bottom_color, left_color, right_color}
        if background_color in side_colors or len(side_colors) < 4:
            raise ValueError("project_frame_side_colors_to_border requires four distinct side colors")
        if any(grid[0][col] != top_color for col in range(1, cols - 1)):
            raise ValueError("project_frame_side_colors_to_border requires a uniform top frame side")
        if any(grid[rows - 1][col] != bottom_color for col in range(1, cols - 1)):
            raise ValueError("project_frame_side_colors_to_border requires a uniform bottom frame side")
        if any(grid[row][0] != left_color for row in range(1, rows - 1)):
            raise ValueError("project_frame_side_colors_to_border requires a uniform left frame side")
        if any(grid[row][cols - 1] != right_color for row in range(1, rows - 1)):
            raise ValueError("project_frame_side_colors_to_border requires a uniform right frame side")

        output = [
            [background_color for _ in range(cols)]
            for _ in range(rows)
        ]
        for col in range(1, cols - 1):
            output[0][col] = top_color
            output[rows - 1][col] = bottom_color
        for row in range(1, rows - 1):
            output[row][0] = left_color
            output[row][cols - 1] = right_color

        changed = False
        for row in range(1, rows - 1):
            for col in range(1, cols - 1):
                value = grid[row][col]
                if value == top_color:
                    output[1][col] = value
                    changed = True
                elif value == bottom_color:
                    output[rows - 2][col] = value
                    changed = True
                elif value == left_color:
                    output[row][1] = value
                    changed = True
                elif value == right_color:
                    output[row][cols - 2] = value
                    changed = True
        if not changed:
            raise ValueError("project_frame_side_colors_to_border found no side-color markers")
        return output

    if object == "stripe_middle_row_of_3_high_bars":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("stripe_middle_row_of_3_high_bars requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("stripe_middle_row_of_3_high_bars requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        output = [row[:] for row in grid]
        visited = set()
        changed = False
        for start_row in range(rows):
            for start_col in range(cols):
                component_color = grid[start_row][start_col]
                if component_color == background_color or (start_row, start_col) in visited:
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
                        if (next_row, next_col) in visited or grid[next_row][next_col] != component_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                min_row = min(row for row, _ in component)
                max_row = max(row for row, _ in component)
                min_col = min(col for _, col in component)
                max_col = max(col for _, col in component)
                if max_row - min_row + 1 != 3:
                    continue
                rectangle = {
                    (row, col)
                    for row in range(min_row, max_row + 1)
                    for col in range(min_col, max_col + 1)
                }
                if set(component) != rectangle:
                    continue
                middle_row = min_row + 1
                for col in range(min_col, max_col + 1):
                    value = component_color if (col - min_col) % 2 == 0 else background_color
                    if output[middle_row][col] != value:
                        output[middle_row][col] = value
                        changed = True
        if not changed:
            raise ValueError("stripe_middle_row_of_3_high_bars found no 3-high bars")
        return output

    if object == "connect_aligned_color_pairs_vertical_priority":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("connect_aligned_color_pairs_vertical_priority requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("connect_aligned_color_pairs_vertical_priority requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        positions_by_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                positions_by_color.setdefault(value, []).append((row, col))
        if not positions_by_color:
            raise ValueError("connect_aligned_color_pairs_vertical_priority requires marker pairs")

        horizontal_segments = []
        vertical_segments = []
        for marker_color, positions in positions_by_color.items():
            if len(positions) != 2:
                raise ValueError("connect_aligned_color_pairs_vertical_priority requires exactly two markers per color")
            (row_a, col_a), (row_b, col_b) = positions
            if row_a == row_b:
                horizontal_segments.append((marker_color, row_a, min(col_a, col_b), max(col_a, col_b)))
            elif col_a == col_b:
                vertical_segments.append((marker_color, col_a, min(row_a, row_b), max(row_a, row_b)))
            else:
                raise ValueError("connect_aligned_color_pairs_vertical_priority requires aligned marker pairs")

        output = [row[:] for row in grid]
        for marker_color, row, start_col, end_col in horizontal_segments:
            for col in range(start_col, end_col + 1):
                output[row][col] = marker_color
        for marker_color, col, start_row, end_row in vertical_segments:
            for row in range(start_row, end_row + 1):
                output[row][col] = marker_color
        return output

    if object == "draw_frame_between_four_markers":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("draw_frame_between_four_markers requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("draw_frame_between_four_markers requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        positions_by_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                positions_by_color.setdefault(value, []).append((row, col))
        marker_candidates = [
            marker_color
            for marker_color, positions in positions_by_color.items()
            if len(positions) == 4
        ]
        if len(marker_candidates) != 1:
            raise ValueError("draw_frame_between_four_markers requires one four-marker color")
        marker_color = marker_candidates[0]
        object_colors = [value for value in positions_by_color if value != marker_color]
        if not object_colors:
            raise ValueError("draw_frame_between_four_markers requires an object color")
        object_color = max(
            object_colors,
            key=lambda value: (len(positions_by_color[value]), -value),
        )

        marker_positions = positions_by_color[marker_color]
        top = min(row for row, _ in marker_positions) + 1
        bottom = max(row for row, _ in marker_positions) - 1
        left = min(col for _, col in marker_positions) + 1
        right = max(col for _, col in marker_positions) - 1
        if top >= bottom or left >= right:
            raise ValueError("draw_frame_between_four_markers requires markers around a non-empty frame")

        output = [row[:] for row in grid]
        for col in range(left, right + 1):
            output[top][col] = object_color
            output[bottom][col] = object_color
        for row in range(top, bottom + 1):
            output[row][left] = object_color
            output[row][right] = object_color
        return output

    if object == "project_stray_pixels_to_matching_full_lines":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("project_stray_pixels_to_matching_full_lines requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_stray_pixels_to_matching_full_lines requires a rectangular grid")
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
            raise ValueError("project_stray_pixels_to_matching_full_lines requires full row or column lines")

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
            raise ValueError("project_stray_pixels_to_matching_full_lines found no stray line-color pixels")
        return output

    if object == "hollow_out_solid_rectangles":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("hollow_out_solid_rectangles requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("hollow_out_solid_rectangles requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        output = [row[:] for row in grid]
        visited = set()
        changed = False
        for start_row in range(rows):
            for start_col in range(cols):
                component_color = grid[start_row][start_col]
                if component_color == background_color or (start_row, start_col) in visited:
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
                        if (next_row, next_col) in visited or grid[next_row][next_col] != component_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                min_row = min(row for row, _ in component)
                max_row = max(row for row, _ in component)
                min_col = min(col for _, col in component)
                max_col = max(col for _, col in component)
                rectangle = {
                    (row, col)
                    for row in range(min_row, max_row + 1)
                    for col in range(min_col, max_col + 1)
                }
                if set(component) != rectangle:
                    continue
                for row in range(min_row + 1, max_row):
                    for col in range(min_col + 1, max_col):
                        if output[row][col] != background_color:
                            output[row][col] = background_color
                            changed = True
        if not changed:
            raise ValueError("hollow_out_solid_rectangles found no solid rectangle interiors")
        return output

    if object == "mirror_shape_across_marker_axis":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("mirror_shape_across_marker_axis requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("mirror_shape_across_marker_axis requires a rectangular grid")
        output_background = color
        input_background = 0 if color1 is None else color1
        if output_background is None or output_background == input_background:
            raise ValueError("mirror_shape_across_marker_axis requires output background color")

        foreground_colors = sorted({
            value
            for row in grid
            for value in row
            if value != input_background
        })
        if len(foreground_colors) != 2:
            raise ValueError("mirror_shape_across_marker_axis requires marker and shape colors")

        candidates = []
        for marker_color in foreground_colors:
            shape_colors = [value for value in foreground_colors if value != marker_color]
            shape_color = shape_colors[0]
            marker_pixels = [
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] == marker_color
            ]
            shape_pixels = [
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] == shape_color
            ]
            if not marker_pixels or not shape_pixels:
                continue
            marker_rows = {row for row, _ in marker_pixels}
            marker_cols = {col for _, col in marker_pixels}
            shape_rows = [row for row, _ in shape_pixels]
            shape_cols = [col for _, col in shape_pixels]
            shape_min_row, shape_max_row = min(shape_rows), max(shape_rows)
            shape_min_col, shape_max_col = min(shape_cols), max(shape_cols)

            reflected = set(shape_pixels)
            axis_description = None
            if len(marker_cols) == 1:
                marker_col = next(iter(marker_cols))
                if marker_col == shape_max_col + 1:
                    for row, col in shape_pixels:
                        reflected.add((row, 2 * marker_col - 1 - col))
                    axis_description = ("vertical", marker_col)
                elif marker_col == shape_min_col - 1:
                    for row, col in shape_pixels:
                        reflected.add((row, 2 * marker_col + 1 - col))
                    axis_description = ("vertical", marker_col)
            if axis_description is None and len(marker_rows) == 1:
                marker_row = next(iter(marker_rows))
                if marker_row == shape_max_row + 1:
                    for row, col in shape_pixels:
                        reflected.add((2 * marker_row - 1 - row, col))
                    axis_description = ("horizontal", marker_row)
                elif marker_row == shape_min_row - 1:
                    for row, col in shape_pixels:
                        reflected.add((2 * marker_row + 1 - row, col))
                    axis_description = ("horizontal", marker_row)
            if axis_description is None:
                continue
            if any(not (0 <= row < rows and 0 <= col < cols) for row, col in reflected):
                continue
            if not set(marker_pixels).issubset(reflected):
                continue
            candidates.append((len(reflected), shape_color, reflected))

        if len(candidates) != 1:
            raise ValueError("mirror_shape_across_marker_axis requires a unique marker-axis interpretation")
        _, shape_color, reflected_pixels = candidates[0]
        output = [
            [output_background for _ in range(cols)]
            for _ in range(rows)
        ]
        for row, col in reflected_pixels:
            output[row][col] = shape_color
        return output

    if object == "reflect_foreground_across_x_anchor":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("reflect_foreground_across_x_anchor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("reflect_foreground_across_x_anchor requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        positions_by_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                positions_by_color.setdefault(value, []).append((row, col))

        anchor_candidates = []
        for candidate_color, positions in positions_by_color.items():
            if len(positions) != 5:
                continue
            min_row = min(row for row, _ in positions)
            max_row = max(row for row, _ in positions)
            min_col = min(col for _, col in positions)
            max_col = max(col for _, col in positions)
            if max_row - min_row != 2 or max_col - min_col != 2:
                continue
            center_row = min_row + 1
            center_col = min_col + 1
            expected = {
                (min_row, min_col),
                (min_row, max_col),
                (center_row, center_col),
                (max_row, min_col),
                (max_row, max_col),
            }
            if set(positions) == expected:
                anchor_candidates.append((candidate_color, center_row, center_col, expected))

        if len(anchor_candidates) != 1:
            raise ValueError("reflect_foreground_across_x_anchor requires a unique 5-pixel X anchor")
        anchor_color, center_row, center_col, anchor_pixels = anchor_candidates[0]
        output = [row[:] for row in grid]
        changed = False
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value in (background_color, anchor_color):
                    continue
                for target_row in {row, 2 * center_row - row}:
                    for target_col in {col, 2 * center_col - col}:
                        if not (0 <= target_row < rows and 0 <= target_col < cols):
                            continue
                        if (target_row, target_col) in anchor_pixels:
                            continue
                        if output[target_row][target_col] != value:
                            output[target_row][target_col] = value
                            changed = True
        if not changed:
            raise ValueError("reflect_foreground_across_x_anchor found no reflected pixels")
        return output

    if object == "largest_zero_rectangle_per_component":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("largest_zero_rectangle_per_component requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("largest_zero_rectangle_per_component requires a rectangular grid")
        target_color = 0 if color1 is None else color1
        fill_color = color
        if fill_color is None or fill_color == target_color:
            raise ValueError("largest_zero_rectangle_per_component requires a fill color")

        output = [row[:] for row in grid]
        visited = set()
        changed = False
        for start_row in range(rows):
            for start_col in range(cols):
                if grid[start_row][start_col] != target_color or (start_row, start_col) in visited:
                    continue
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                component = []
                component_set = set()
                while stack:
                    row, col = stack.pop()
                    component.append((row, col))
                    component_set.add((row, col))
                    for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        next_row = row + delta_row
                        next_col = col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited or grid[next_row][next_col] != target_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                min_row = min(row for row, _ in component)
                max_row = max(row for row, _ in component)
                min_col = min(col for _, col in component)
                max_col = max(col for _, col in component)
                best = None
                for top in range(min_row, max_row + 1):
                    for bottom in range(top + 1, max_row + 1):
                        for left in range(min_col, max_col + 1):
                            for right in range(left + 1, max_col + 1):
                                area = (bottom - top + 1) * (right - left + 1)
                                if best is not None and area <= best[0]:
                                    continue
                                if all(
                                    (row, col) in component_set
                                    for row in range(top, bottom + 1)
                                    for col in range(left, right + 1)
                                ):
                                    best = (area, top, bottom, left, right)
                if best is None:
                    continue
                _, top, bottom, left, right = best
                for row in range(top, bottom + 1):
                    for col in range(left, right + 1):
                        if output[row][col] != fill_color:
                            output[row][col] = fill_color
                            changed = True
        if not changed:
            raise ValueError("largest_zero_rectangle_per_component found no fillable rectangles")
        return output

    if object == "stamp_external_pattern_on_internal_markers":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("stamp_external_pattern_on_internal_markers requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("stamp_external_pattern_on_internal_markers requires a rectangular grid")

        counts = {}
        for row in grid:
            for value in row:
                counts[value] = counts.get(value, 0) + 1
        background_color = max(counts.items(), key=lambda item: (item[1], -item[0]))[0]
        foreground_counts = {
            value: count
            for value, count in counts.items()
            if value != background_color
        }
        if not foreground_counts:
            raise ValueError("stamp_external_pattern_on_internal_markers requires foreground")
        base_color = max(foreground_counts.items(), key=lambda item: (item[1], -item[0]))[0]

        visited = set()
        rectangle_regions = []
        internal_markers = []
        marker_color = None
        for start_row in range(rows):
            for start_col in range(cols):
                if grid[start_row][start_col] != base_color or (start_row, start_col) in visited:
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
                        if (next_row, next_col) in visited or grid[next_row][next_col] != base_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                min_row = min(row for row, _ in component)
                max_row = max(row for row, _ in component)
                min_col = min(col for _, col in component)
                max_col = max(col for _, col in component)
                if (max_row - min_row + 1) * (max_col - min_col + 1) < 16:
                    continue

                region_markers = []
                valid_rectangle = True
                for row in range(min_row, max_row + 1):
                    for col in range(min_col, max_col + 1):
                        value = grid[row][col]
                        if value == base_color:
                            continue
                        if value == background_color:
                            valid_rectangle = False
                            break
                        region_markers.append((row, col, value))
                    if not valid_rectangle:
                        break
                if not valid_rectangle or not region_markers:
                    continue
                marker_colors = {value for _, _, value in region_markers}
                if len(marker_colors) != 1:
                    continue
                region_marker_color = next(iter(marker_colors))
                if marker_color is None:
                    marker_color = region_marker_color
                elif marker_color != region_marker_color:
                    continue
                rectangle_regions.append((min_row, max_row, min_col, max_col))
                internal_markers.extend((row, col) for row, col, _ in region_markers)

        if not rectangle_regions or not internal_markers or marker_color is None:
            raise ValueError("stamp_external_pattern_on_internal_markers requires marked base rectangles")

        def inside_rectangle(row, col):
            return any(
                min_row <= row <= max_row and min_col <= col <= max_col
                for min_row, max_row, min_col, max_col in rectangle_regions
            )

        pattern_pixels = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] not in (background_color, base_color)
            and not inside_rectangle(row, col)
        ]
        if not pattern_pixels:
            raise ValueError("stamp_external_pattern_on_internal_markers requires an external pattern")
        pattern_min_row = min(row for row, _, _ in pattern_pixels)
        pattern_max_row = max(row for row, _, _ in pattern_pixels)
        pattern_min_col = min(col for _, col, _ in pattern_pixels)
        pattern_max_col = max(col for _, col, _ in pattern_pixels)
        anchor_row = (pattern_min_row + pattern_max_row) // 2
        anchor_col = (pattern_min_col + pattern_max_col) // 2
        if grid[anchor_row][anchor_col] != marker_color:
            marker_positions = [
                (row, col)
                for row, col, value in pattern_pixels
                if value == marker_color
            ]
            if not marker_positions:
                raise ValueError("stamp_external_pattern_on_internal_markers requires marker color in external pattern")
            anchor_row, anchor_col = min(
                marker_positions,
                key=lambda point: abs(point[0] - (pattern_min_row + pattern_max_row) / 2)
                + abs(point[1] - (pattern_min_col + pattern_max_col) / 2),
            )

        output = [row[:] for row in grid]
        for row, col, _ in pattern_pixels:
            output[row][col] = background_color

        pattern_offsets_by_color = {}
        for pattern_row, pattern_col, value in pattern_pixels:
            pattern_offsets_by_color.setdefault(value, []).append(
                (pattern_row - anchor_row, pattern_col - anchor_col)
            )
        axis_only_colors = {
            value
            for value, offsets in pattern_offsets_by_color.items()
            if value != marker_color
            and all(delta_row == 0 or delta_col == 0 for delta_row, delta_col in offsets)
        }

        def containing_rectangle(row, col):
            for min_row, max_row, min_col, max_col in rectangle_regions:
                if min_row <= row <= max_row and min_col <= col <= max_col:
                    return min_row, max_row, min_col, max_col
            return None

        for marker_row, marker_col in internal_markers:
            bounds = containing_rectangle(marker_row, marker_col)
            if bounds is None:
                continue
            min_row, max_row, min_col, max_col = bounds
            for pattern_row, pattern_col, value in pattern_pixels:
                delta_row = pattern_row - anchor_row
                delta_col = pattern_col - anchor_col
                if delta_row == 0 and delta_col == 0:
                    output[marker_row][marker_col] = value
                elif delta_row == 0 and value in axis_only_colors:
                    for target_col in range(min_col, max_col + 1):
                        if target_col != marker_col:
                            output[marker_row][target_col] = value
                elif delta_col == 0 and value in axis_only_colors:
                    for target_row in range(min_row, max_row + 1):
                        if target_row != marker_row:
                            output[target_row][marker_col] = value
                else:
                    target_row = marker_row + delta_row
                    target_col = marker_col + delta_col
                    if min_row <= target_row <= max_row and min_col <= target_col <= max_col:
                        output[target_row][target_col] = value
        return output

    if object == "propagate_holes_across_color_rectangles":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("propagate_holes_across_color_rectangles requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("propagate_holes_across_color_rectangles requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        output = [row[:] for row in grid]
        visited = set()
        changed = False
        for start_row in range(rows):
            for start_col in range(cols):
                component_color = grid[start_row][start_col]
                if component_color == background_color or (start_row, start_col) in visited:
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
                        if (next_row, next_col) in visited or grid[next_row][next_col] != component_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                min_row = min(row for row, _ in component)
                max_row = max(row for row, _ in component)
                min_col = min(col for _, col in component)
                max_col = max(col for _, col in component)
                height = max_row - min_row + 1
                width = max_col - min_col + 1
                if height < 2 or width < 2:
                    continue
                holes = []
                valid_field = True
                for row in range(min_row, max_row + 1):
                    for col in range(min_col, max_col + 1):
                        value = grid[row][col]
                        if value == component_color:
                            continue
                        if value == background_color:
                            holes.append((row, col))
                        else:
                            valid_field = False
                            break
                    if not valid_field:
                        break
                if not valid_field or not holes:
                    continue
                if height <= width:
                    for _, col in holes:
                        for row in range(min_row, max_row + 1):
                            if output[row][col] != background_color:
                                output[row][col] = background_color
                                changed = True
                else:
                    for row, _ in holes:
                        for col in range(min_col, max_col + 1):
                            if output[row][col] != background_color:
                                output[row][col] = background_color
                                changed = True
        if not changed:
            raise ValueError("propagate_holes_across_color_rectangles found no holes")
        return output

    if object == "move_satellite_rectangle_to_touch_anchor":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("move_satellite_rectangle_to_touch_anchor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("move_satellite_rectangle_to_touch_anchor requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        positions_by_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                positions_by_color.setdefault(value, []).append((row, col))
        if len(positions_by_color) != 2:
            raise ValueError("move_satellite_rectangle_to_touch_anchor requires exactly two foreground colors")

        def bounding_box(positions):
            return (
                min(row for row, _ in positions),
                max(row for row, _ in positions),
                min(col for _, col in positions),
                max(col for _, col in positions),
            )

        def is_exact_rectangle(positions):
            min_row, max_row, min_col, max_col = bounding_box(positions)
            return set(positions) == {
                (row, col)
                for row in range(min_row, max_row + 1)
                for col in range(min_col, max_col + 1)
            }

        anchor_colors = [
            candidate_color
            for candidate_color, positions in positions_by_color.items()
            if is_exact_rectangle(positions)
        ]
        if len(anchor_colors) != 1:
            raise ValueError("move_satellite_rectangle_to_touch_anchor requires one exact anchor rectangle")
        anchor_color = anchor_colors[0]
        satellite_color = next(value for value in positions_by_color if value != anchor_color)
        anchor_min_row, anchor_max_row, anchor_min_col, anchor_max_col = bounding_box(positions_by_color[anchor_color])
        satellite_positions = set(positions_by_color[satellite_color])
        sat_min_row, sat_max_row, sat_min_col, sat_max_col = bounding_box(satellite_positions)

        best_rectangle = None
        widths = sat_max_col - sat_min_col + 1
        heights = [0] * widths
        for row in range(sat_min_row, sat_max_row + 1):
            for offset_col, col in enumerate(range(sat_min_col, sat_max_col + 1)):
                heights[offset_col] = heights[offset_col] + 1 if (row, col) in satellite_positions else 0

            stack = []
            for index, height in enumerate(heights + [0]):
                start = index
                while stack and stack[-1][1] > height:
                    start, popped_height = stack.pop()
                    width = index - start
                    if popped_height >= 2 and width >= 2:
                        area = popped_height * width
                        if best_rectangle is None or area > best_rectangle[0]:
                            bottom = row
                            top = row - popped_height + 1
                            left = sat_min_col + start
                            right = sat_min_col + index - 1
                            best_rectangle = (area, top, bottom, left, right)
                stack.append((start, height))
        if best_rectangle is None:
            raise ValueError("move_satellite_rectangle_to_touch_anchor requires a solid satellite rectangle")
        _, sat_rect_top, sat_rect_bottom, sat_rect_left, sat_rect_right = best_rectangle
        sat_height = sat_rect_bottom - sat_rect_top + 1
        sat_width = sat_rect_right - sat_rect_left + 1

        anchor_center_row = (anchor_min_row + anchor_max_row) / 2
        anchor_center_col = (anchor_min_col + anchor_max_col) / 2
        satellite_center_row = (sat_rect_top + sat_rect_bottom) / 2
        satellite_center_col = (sat_rect_left + sat_rect_right) / 2
        if abs(satellite_center_row - anchor_center_row) >= abs(satellite_center_col - anchor_center_col):
            target_top = anchor_max_row + 1 if satellite_center_row > anchor_center_row else anchor_min_row - sat_height
            target_left = sat_rect_left
        else:
            target_left = anchor_max_col + 1 if satellite_center_col > anchor_center_col else anchor_min_col - sat_width
            target_top = sat_rect_top
        if not (0 <= target_top <= rows - sat_height and 0 <= target_left <= cols - sat_width):
            raise ValueError("move_satellite_rectangle_to_touch_anchor target rectangle is out of bounds")

        output = [row[:] for row in grid]
        for row, col in satellite_positions:
            output[row][col] = background_color
        for row in range(target_top, target_top + sat_height):
            for col in range(target_left, target_left + sat_width):
                output[row][col] = satellite_color
        return output

    if object == "color_empty_background_lines":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("color_empty_background_lines requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("color_empty_background_lines requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        fill_color = color
        if fill_color is None or fill_color == background_color:
            raise ValueError("color_empty_background_lines requires a non-background fill color")

        empty_rows = [
            row
            for row in range(rows)
            if all(grid[row][col] == background_color for col in range(cols))
        ]
        empty_cols = [
            col
            for col in range(cols)
            if all(grid[row][col] == background_color for row in range(rows))
        ]
        if not empty_rows and not empty_cols:
            raise ValueError("color_empty_background_lines found no empty rows or columns")

        output = [row[:] for row in grid]
        changed = False
        for row in empty_rows:
            for col in range(cols):
                if output[row][col] != fill_color:
                    output[row][col] = fill_color
                    changed = True
        for col in empty_cols:
            for row in range(rows):
                if output[row][col] != fill_color:
                    output[row][col] = fill_color
                    changed = True
        if not changed:
            raise ValueError("color_empty_background_lines made no changes")
        return output

    if object == "project_marker_columns_through_arch":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("project_marker_columns_through_arch requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_marker_columns_through_arch requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        positions_by_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                positions_by_color.setdefault(value, []).append((row, col))
        if len(positions_by_color) != 2:
            raise ValueError("project_marker_columns_through_arch requires exactly two foreground colors")

        def component_count_8(positions):
            position_set = set(positions)
            seen = set()
            count = 0
            for start in positions:
                if start in seen:
                    continue
                count += 1
                stack = [start]
                seen.add(start)
                while stack:
                    row, col = stack.pop()
                    for delta_row in (-1, 0, 1):
                        for delta_col in (-1, 0, 1):
                            if delta_row == 0 and delta_col == 0:
                                continue
                            neighbor = (row + delta_row, col + delta_col)
                            if neighbor in position_set and neighbor not in seen:
                                seen.add(neighbor)
                                stack.append(neighbor)
            return count

        color_stats = [
            (component_count_8(positions), len(positions), value)
            for value, positions in positions_by_color.items()
        ]
        color_stats.sort()
        if len(color_stats) != 2 or color_stats[0][0] != 1 or color_stats[0][0] == color_stats[1][0]:
            raise ValueError("project_marker_columns_through_arch requires one 8-connected arch color")
        arch_color = color_stats[0][2]
        marker_color = color_stats[1][2]

        arch_rows = {}
        for row, col in positions_by_color[arch_color]:
            arch_rows.setdefault(row, []).append(col)
        min_arch_row = min(arch_rows)
        max_arch_row = max(arch_rows)

        interior_by_row = {}
        all_interior_cols = set()
        for row, row_cols in arch_rows.items():
            if len(row_cols) < 2:
                continue
            row_cols = sorted(row_cols)
            occupied = set(row_cols)
            interior_cols = {
                col
                for col in range(row_cols[0] + 1, row_cols[-1])
                if col not in occupied
            }
            if interior_cols:
                interior_by_row[row] = interior_cols
                all_interior_cols.update(interior_cols)
        if not all_interior_cols:
            raise ValueError("project_marker_columns_through_arch found no arch interior")

        seed_cols = {
            col
            for row, col in positions_by_color[marker_color]
            if row >= min_arch_row and col in all_interior_cols
        }
        if not seed_cols:
            raise ValueError("project_marker_columns_through_arch found no marker columns inside arch")

        output = [row[:] for row in grid]
        changed = False
        for col in sorted(seed_cols):
            start_row = None
            for row in range(min_arch_row, max_arch_row + 1):
                if col in interior_by_row.get(row, set()) and grid[row][col] == background_color:
                    start_row = row
                    break
            if start_row is None:
                start_row = max_arch_row + 1
            for row in range(start_row, rows):
                if output[row][col] == background_color:
                    output[row][col] = marker_color
                    changed = True
        if not changed:
            raise ValueError("project_marker_columns_through_arch made no changes")
        return output

    if object == "local_center_surround_template_completion":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("local_center_surround_template_completion requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("local_center_surround_template_completion requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        allowed_offset_sets = [
            frozenset(((0, -1), (0, 1))),
            frozenset(((-1, 0), (1, 0))),
            frozenset(((-1, 0), (1, 0), (0, -1), (0, 1))),
            frozenset(((-1, -1), (-1, 1), (1, -1), (1, 1))),
        ]
        motifs = set()
        for row in range(rows):
            for col in range(cols):
                center_color = grid[row][col]
                if center_color == background_color:
                    continue
                for offsets in allowed_offset_sets:
                    surround_values = []
                    in_bounds = True
                    for delta_row, delta_col in offsets:
                        neighbor_row = row + delta_row
                        neighbor_col = col + delta_col
                        if not (0 <= neighbor_row < rows and 0 <= neighbor_col < cols):
                            in_bounds = False
                            break
                        surround_values.append(grid[neighbor_row][neighbor_col])
                    if not in_bounds:
                        continue
                    surround_colors = set(surround_values)
                    if len(surround_colors) != 1:
                        continue
                    surround_color = next(iter(surround_colors))
                    if surround_color == background_color or surround_color == center_color:
                        continue
                    motifs.add((center_color, surround_color, offsets))
        if not motifs:
            raise ValueError("local_center_surround_template_completion found no local templates")

        output = [row[:] for row in grid]
        changed = False

        for center_color, surround_color, offsets in sorted(
            motifs,
            key=lambda motif: (motif[0], motif[1], sorted(motif[2])),
        ):
            for row in range(rows):
                for col in range(cols):
                    if grid[row][col] != center_color:
                        continue
                    for delta_row, delta_col in offsets:
                        neighbor_row = row + delta_row
                        neighbor_col = col + delta_col
                        if not (0 <= neighbor_row < rows and 0 <= neighbor_col < cols):
                            continue
                        if output[neighbor_row][neighbor_col] == background_color:
                            output[neighbor_row][neighbor_col] = surround_color
                            changed = True

            for row in range(rows):
                for col in range(cols):
                    if output[row][col] != background_color:
                        continue
                    matches = True
                    for delta_row, delta_col in offsets:
                        neighbor_row = row + delta_row
                        neighbor_col = col + delta_col
                        if not (0 <= neighbor_row < rows and 0 <= neighbor_col < cols):
                            matches = False
                            break
                        if output[neighbor_row][neighbor_col] != surround_color:
                            matches = False
                            break
                    if matches:
                        output[row][col] = center_color
                        changed = True

        if not changed:
            raise ValueError("local_center_surround_template_completion made no changes")
        return output

    if object == "project_bar_marker_cross_sections":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("project_bar_marker_cross_sections requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_bar_marker_cross_sections requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        foreground_counts = {}
        for row in grid:
            for value in row:
                if value != background_color:
                    foreground_counts[value] = foreground_counts.get(value, 0) + 1
        if len(foreground_counts) != 2:
            raise ValueError("project_bar_marker_cross_sections requires exactly two foreground colors")
        main_color = max(foreground_counts, key=lambda value: foreground_counts[value])
        marker_color = min(foreground_counts, key=lambda value: foreground_counts[value])

        foreground = {
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        }
        seen = set()
        components = []
        for start in sorted(foreground):
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
                    if neighbor in foreground and neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
            components.append(component)
        if len(components) != 2:
            raise ValueError("project_bar_marker_cross_sections requires two foreground bar components")

        output = [row[:] for row in grid]
        changed = False
        for component in components:
            min_row = min(row for row, _ in component)
            max_row = max(row for row, _ in component)
            min_col = min(col for _, col in component)
            max_col = max(col for _, col in component)
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            marker_positions = [
                (row, col)
                for row, col in component
                if grid[row][col] == marker_color
            ]
            if len(marker_positions) != 1:
                raise ValueError("project_bar_marker_cross_sections requires one marker per bar")
            marker_row, marker_col = marker_positions[0]

            if height >= width:
                radius = width - 1
                top = max(0, marker_row - radius)
                bottom = min(rows - 1, marker_row + radius)
                if marker_col == min_col:
                    projection_cols = range(0, min_col)
                elif marker_col == max_col:
                    projection_cols = range(max_col + 1, cols)
                else:
                    raise ValueError("vertical bar marker must be on a horizontal edge")
                for row in range(top, bottom + 1):
                    paint_color = marker_color if row == marker_row else main_color
                    for col in projection_cols:
                        if output[row][col] == background_color:
                            output[row][col] = paint_color
                            changed = True
            else:
                radius = height - 1
                left = max(0, marker_col - radius)
                right = min(cols - 1, marker_col + radius)
                if marker_row == min_row:
                    projection_rows = range(0, min_row)
                elif marker_row == max_row:
                    projection_rows = range(max_row + 1, rows)
                else:
                    raise ValueError("horizontal bar marker must be on a vertical edge")
                for row in projection_rows:
                    for col in range(left, right + 1):
                        paint_color = marker_color if col == marker_col else main_color
                        if output[row][col] == background_color:
                            output[row][col] = paint_color
                            changed = True

        if not changed:
            raise ValueError("project_bar_marker_cross_sections made no changes")
        return output

    if object == "wall_enclosure_background_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("wall_enclosure_background_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("wall_enclosure_background_fill requires a rectangular grid")
        background_color = 0
        inside_color = color
        outside_color = color1
        if inside_color in (None, background_color) or outside_color in (None, background_color):
            raise ValueError("wall_enclosure_background_fill requires non-background inside/outside colors")
        if inside_color == outside_color:
            raise ValueError("wall_enclosure_background_fill requires distinct inside/outside colors")
        if any(value in (inside_color, outside_color) for row in grid for value in row):
            raise ValueError("wall_enclosure_background_fill expects newly inserted fill colors")
        wall_colors = {
            value
            for row in grid
            for value in row
            if value != background_color
        }
        if not wall_colors:
            raise ValueError("wall_enclosure_background_fill requires wall pixels")

        outside = set()
        queue = []
        for row in range(rows):
            for col in (0, cols - 1):
                if grid[row][col] == background_color and (row, col) not in outside:
                    outside.add((row, col))
                    queue.append((row, col))
        for col in range(cols):
            for row in (0, rows - 1):
                if grid[row][col] == background_color and (row, col) not in outside:
                    outside.add((row, col))
                    queue.append((row, col))
        while queue:
            row, col = queue.pop()
            for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor_row = row + delta_row
                neighbor_col = col + delta_col
                neighbor = (neighbor_row, neighbor_col)
                if not (0 <= neighbor_row < rows and 0 <= neighbor_col < cols):
                    continue
                if neighbor in outside:
                    continue
                if grid[neighbor_row][neighbor_col] != background_color:
                    continue
                outside.add(neighbor)
                queue.append(neighbor)

        output = [row[:] for row in grid]
        changed = False
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != background_color:
                    continue
                fill_color = outside_color if (row, col) in outside else inside_color
                output[row][col] = fill_color
                changed = True
        if not changed:
            raise ValueError("wall_enclosure_background_fill made no changes")
        return output

    if object == "paired_vertical_line_marker_beams":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("paired_vertical_line_marker_beams requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("paired_vertical_line_marker_beams requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        cap_color = color
        if cap_color in (None, background_color):
            raise ValueError("paired_vertical_line_marker_beams requires a cap color")

        positions_by_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                positions_by_color.setdefault(value, []).append((row, col))
        if len(positions_by_color) != 2:
            raise ValueError("paired_vertical_line_marker_beams requires exactly two input foreground colors")

        def components_for(positions):
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
            return components

        line_color = None
        line_components = None
        for value, positions in positions_by_color.items():
            components = components_for(positions)
            if len(components) != 2:
                continue
            if all(
                len({col for _, col in component}) == 1
                and len(component) == (
                    max(row for row, _ in component)
                    - min(row for row, _ in component)
                    + 1
                )
                for component in components
            ):
                line_color = value
                line_components = components
                break
        if line_color is None:
            raise ValueError("paired_vertical_line_marker_beams found no paired vertical line color")
        marker_color = next(value for value in positions_by_color if value != line_color)
        marker_positions = positions_by_color[marker_color]
        marker_components = components_for(marker_positions)
        if any(len(component) != 1 for component in marker_components):
            raise ValueError("paired_vertical_line_marker_beams requires singleton markers")

        line_specs = []
        for component in line_components:
            line_col = next(iter({col for _, col in component}))
            min_row = min(row for row, _ in component)
            max_row = max(row for row, _ in component)
            line_specs.append({
                "col": line_col,
                "min_row": min_row,
                "max_row": max_row,
                "height": max_row - min_row + 1,
            })
        if line_specs[0]["height"] != line_specs[1]["height"]:
            raise ValueError("paired_vertical_line_marker_beams requires equal-height line segments")

        aligned_by_line = []
        for spec in line_specs:
            aligned = [
                (row, col)
                for row, col in marker_positions
                if spec["min_row"] <= row <= spec["max_row"] and col != spec["col"]
            ]
            aligned_by_line.append(aligned)
        source_indices = [
            index
            for index, aligned in enumerate(aligned_by_line)
            if aligned
        ]
        if len(source_indices) != 1:
            raise ValueError("paired_vertical_line_marker_beams requires markers aligned to exactly one line")
        source_index = source_indices[0]
        target_index = 1 - source_index
        source = line_specs[source_index]
        target = line_specs[target_index]

        output = [row[:] for row in grid]
        changed = False
        for marker_row, marker_col in sorted(aligned_by_line[source_index]):
            direction = 1 if marker_col > source["col"] else -1
            for col in range(source["col"] + direction, marker_col, direction):
                if output[marker_row][col] == background_color:
                    output[marker_row][col] = marker_color
                    changed = True
            if output[marker_row][marker_col] != cap_color:
                output[marker_row][marker_col] = cap_color
                changed = True

            target_row = target["min_row"] + (marker_row - source["min_row"])
            if not (target["min_row"] <= target_row <= target["max_row"]):
                continue
            if target["col"] < source["col"]:
                target_cols = range(target["col"] + 1, cols)
            else:
                target_cols = range(0, target["col"])
            for col in target_cols:
                if output[target_row][col] == background_color:
                    output[target_row][col] = marker_color
                    changed = True

        if not changed:
            raise ValueError("paired_vertical_line_marker_beams made no changes")
        return output

    if object == "project_markers_to_strip_boundary":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("project_markers_to_strip_boundary requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_markers_to_strip_boundary requires a rectangular grid")

        target_color = color
        if target_color in (None, 0):
            non_background = [
                value
                for row in grid
                for value in row
                if value != 0
            ]
            if not non_background:
                raise ValueError("project_markers_to_strip_boundary requires foreground")
            target_color = max(
                sorted(set(non_background)),
                key=lambda value: non_background.count(value),
            )

        marker_color = color1 if color1 not in (None, 0) else None
        target_pixels = [
            (row, col)
            for row, values in enumerate(grid)
            for col, value in enumerate(values)
            if value == target_color
        ]
        if not target_pixels:
            raise ValueError("project_markers_to_strip_boundary requires target pixels")

        min_row = min(row for row, _ in target_pixels)
        max_row = max(row for row, _ in target_pixels)
        min_col = min(col for _, col in target_pixels)
        max_col = max(col for _, col in target_pixels)
        full_width_strip = min_col == 0 and max_col == cols - 1
        full_height_strip = min_row == 0 and max_row == rows - 1
        if full_width_strip == full_height_strip:
            raise ValueError("project_markers_to_strip_boundary requires exactly one full-span strip axis")

        markers = []
        for row, values in enumerate(grid):
            for col, value in enumerate(values):
                if value in (0, target_color):
                    continue
                if marker_color is not None and value != marker_color:
                    continue
                markers.append((row, col))
        if not markers:
            raise ValueError("project_markers_to_strip_boundary found no markers")

        output = [
            [target_color if value == target_color else 0 for value in values]
            for values in grid
        ]
        projected = set()
        groups = {}
        for row, col in markers:
            if full_width_strip:
                if row < min_row:
                    groups.setdefault(("above", col), 0)
                    groups[("above", col)] += 1
                elif row > max_row:
                    groups.setdefault(("below", col), 0)
                    groups[("below", col)] += 1
                else:
                    raise ValueError("project_markers_to_strip_boundary marker lies inside horizontal strip")
            else:
                if col < min_col:
                    groups.setdefault(("left", row), 0)
                    groups[("left", row)] += 1
                elif col > max_col:
                    groups.setdefault(("right", row), 0)
                    groups[("right", row)] += 1
                else:
                    raise ValueError("project_markers_to_strip_boundary marker lies inside vertical strip")

        for (side, index), count in groups.items():
            for offset in range(1, count + 1):
                if side == "above":
                    target = (min_row - offset, index)
                elif side == "below":
                    target = (max_row + offset, index)
                elif side == "left":
                    target = (index, min_col - offset)
                elif side == "right":
                    target = (index, max_col + offset)
                else:
                    raise ValueError(f"unsupported projection side: {side}")
                target_row, target_col = target
                if not (0 <= target_row < rows and 0 <= target_col < cols):
                    raise ValueError("project_markers_to_strip_boundary projection leaves grid")
                projected.add(target)

        for row, col in projected:
            output[row][col] = target_color
        return output

    if object == "singleton_marker_quadrant_edge_rays":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("singleton_marker_quadrant_edge_rays requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("singleton_marker_quadrant_edge_rays requires a rectangular grid")

        background_color = 0 if color1 is None else color1
        markers = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if not markers:
            raise ValueError("singleton_marker_quadrant_edge_rays requires foreground markers")
        counts = {}
        for _row, _col, marker_color in markers:
            counts[marker_color] = counts.get(marker_color, 0) + 1
        if any(count != 1 for count in counts.values()):
            raise ValueError("singleton_marker_quadrant_edge_rays requires singleton marker colors")

        output = [row[:] for row in grid]
        changed = False

        def paint(row, col, marker_color):
            nonlocal changed
            value = output[row][col]
            if value == background_color:
                output[row][col] = marker_color
                changed = True
                return
            if value != marker_color:
                raise ValueError("singleton_marker_quadrant_edge_rays found ray collision")

        for marker_row, marker_col, marker_color in markers:
            if marker_row * 2 < rows:
                row_range = range(0, marker_row + 1)
            else:
                row_range = range(marker_row, rows)
            if marker_col * 2 < cols:
                col_range = range(0, marker_col + 1)
            else:
                col_range = range(marker_col, cols)
            for row in row_range:
                paint(row, marker_col, marker_color)
            for col in col_range:
                paint(marker_row, col, marker_color)

        if not changed:
            raise ValueError("singleton_marker_quadrant_edge_rays made no changes")
        return output

    if object == "project_markers_to_nearest_full_lines":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("project_markers_to_nearest_full_lines requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("project_markers_to_nearest_full_lines requires a rectangular grid")

        non_background_colors = sorted({
            value
            for row in grid
            for value in row
            if value != 0
        })
        if len(non_background_colors) != 2:
            raise ValueError("project_markers_to_nearest_full_lines requires two foreground colors")

        requested_marker_color = color if color not in (None, 0) else None
        requested_line_color = color1 if color1 not in (None, 0) else None

        def full_lines_for(candidate_color):
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
            return full_rows, full_cols

        line_candidates = []
        for candidate_color in non_background_colors:
            full_rows, full_cols = full_lines_for(candidate_color)
            if full_rows or full_cols:
                line_candidates.append((candidate_color, full_rows, full_cols))

        if requested_line_color is not None:
            line_candidates = [
                candidate
                for candidate in line_candidates
                if candidate[0] == requested_line_color
            ]
        if len(line_candidates) != 1:
            raise ValueError("project_markers_to_nearest_full_lines requires one full-line color")

        line_color, full_rows, full_cols = line_candidates[0]
        marker_colors = [
            candidate_color
            for candidate_color in non_background_colors
            if candidate_color != line_color
        ]
        if requested_marker_color is not None:
            marker_colors = [
                candidate_color
                for candidate_color in marker_colors
                if candidate_color == requested_marker_color
            ]
        if len(marker_colors) != 1:
            raise ValueError("project_markers_to_nearest_full_lines requires one marker color")
        marker_color = marker_colors[0]

        markers = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == marker_color
        ]
        if not markers:
            raise ValueError("project_markers_to_nearest_full_lines requires marker pixels")
        if not full_rows and not full_cols:
            raise ValueError("project_markers_to_nearest_full_lines requires a full row or column")

        output = [row[:] for row in grid]
        changed = False

        def paint_block(center_row, center_col):
            nonlocal changed
            for row in range(center_row - 1, center_row + 2):
                for col in range(center_col - 1, center_col + 2):
                    if 0 <= row < rows and 0 <= col < cols and output[row][col] != line_color:
                        output[row][col] = line_color
                        changed = True
            if output[center_row][center_col] != marker_color:
                output[center_row][center_col] = marker_color
                changed = True

        for marker_row, marker_col in markers:
            nearest_rows = []
            above = [row for row in full_rows if row < marker_row]
            below = [row for row in full_rows if row > marker_row]
            if above:
                nearest_rows.append(max(above))
            if below:
                nearest_rows.append(min(below))

            for line_row in nearest_rows:
                direction = 1 if line_row > marker_row else -1
                paint_block(line_row, marker_col)
                if direction > 0:
                    path_rows = range(marker_row, line_row - 1)
                else:
                    path_rows = range(line_row + 2, marker_row + 1)
                for row in path_rows:
                    if output[row][marker_col] != marker_color:
                        output[row][marker_col] = marker_color
                        changed = True

            nearest_cols = []
            left = [col for col in full_cols if col < marker_col]
            right = [col for col in full_cols if col > marker_col]
            if left:
                nearest_cols.append(max(left))
            if right:
                nearest_cols.append(min(right))

            for line_col in nearest_cols:
                direction = 1 if line_col > marker_col else -1
                paint_block(marker_row, line_col)
                if direction > 0:
                    path_cols = range(marker_col, line_col - 1)
                else:
                    path_cols = range(line_col + 2, marker_col + 1)
                for col in path_cols:
                    if output[marker_row][col] != marker_color:
                        output[marker_row][col] = marker_color
                        changed = True

        if not changed:
            raise ValueError("project_markers_to_nearest_full_lines made no changes")
        return output

    if object == "singleton_marker_crosshair_lattice":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("singleton_marker_crosshair_lattice requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("singleton_marker_crosshair_lattice requires a rectangular grid")

        background_color = 0 if color1 is None else color1
        intersection_color = color
        if not isinstance(intersection_color, int):
            raise ValueError("singleton_marker_crosshair_lattice requires an integer intersection color")
        if intersection_color == background_color:
            raise ValueError("singleton_marker_crosshair_lattice requires a non-background intersection color")

        markers = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if len(markers) < 2:
            raise ValueError("singleton_marker_crosshair_lattice requires at least two singleton markers")
        marker_colors = [marker_color for _row, _col, marker_color in markers]
        if len(marker_colors) != len(set(marker_colors)):
            raise ValueError("singleton_marker_crosshair_lattice requires distinct marker colors")
        if intersection_color in marker_colors:
            raise ValueError("singleton_marker_crosshair_lattice requires a separate intersection color")
        marker_rows = [row for row, _col, _color in markers]
        marker_cols = [col for _row, col, _color in markers]
        if len(marker_rows) != len(set(marker_rows)) or len(marker_cols) != len(set(marker_cols)):
            raise ValueError("singleton_marker_crosshair_lattice requires distinct marker rows and columns")

        for marker_row, marker_col, _marker_color in markers:
            for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                adjacent_row = marker_row + delta_row
                adjacent_col = marker_col + delta_col
                if (
                    0 <= adjacent_row < rows
                    and 0 <= adjacent_col < cols
                    and grid[adjacent_row][adjacent_col] != background_color
                ):
                    raise ValueError("singleton_marker_crosshair_lattice requires isolated markers")

        output = [row[:] for row in grid]
        marker_by_row = {row: marker_color for row, _col, marker_color in markers}
        marker_by_col = {col: marker_color for _row, col, marker_color in markers}
        changed = False
        for row in range(rows):
            for col in range(cols):
                row_color = marker_by_row.get(row)
                col_color = marker_by_col.get(col)
                if row_color is None and col_color is None:
                    continue
                if row_color is not None and col_color is not None and row_color != col_color:
                    target_color = intersection_color
                else:
                    target_color = row_color if row_color is not None else col_color
                if grid[row][col] not in (background_color, target_color):
                    raise ValueError("singleton_marker_crosshair_lattice found projection collision")
                if output[row][col] != target_color:
                    output[row][col] = target_color
                    changed = True

        if not changed:
            raise ValueError("singleton_marker_crosshair_lattice made no changes")
        return output

    if object == "top_pattern_vertical_projection_obstacle_shift":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("top_pattern_vertical_projection_obstacle_shift requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("top_pattern_vertical_projection_obstacle_shift requires a rectangular grid")

        background_color = 0 if color1 is None else color1
        top_pattern = tuple(grid[0])
        guide_colors = sorted({value for value in top_pattern if value != background_color})
        if len(guide_colors) != 1:
            raise ValueError("top_pattern_vertical_projection_obstacle_shift requires one guide color")
        guide_color = guide_colors[0]
        guide_cols = [col for col, value in enumerate(top_pattern) if value == guide_color]
        if len(guide_cols) < 2:
            raise ValueError("top_pattern_vertical_projection_obstacle_shift requires at least two guide columns")

        top_row_count = 0
        while top_row_count < rows and tuple(grid[top_row_count]) == top_pattern:
            top_row_count += 1
        if top_row_count < 2 or top_row_count >= rows:
            raise ValueError("top_pattern_vertical_projection_obstacle_shift requires a repeated top pattern")

        candidate_object_rows = []
        for row in range(top_row_count, rows):
            values = {grid[row][col] for col in range(cols) if grid[row][col] != background_color}
            values.discard(guide_color)
            if values:
                candidate_object_rows.append((row, sorted(values)))
        if len(candidate_object_rows) != 1 or len(candidate_object_rows[0][1]) != 1:
            raise ValueError("top_pattern_vertical_projection_obstacle_shift requires one object row and color")
        object_row, object_values = candidate_object_rows[0]
        object_color = object_values[0]

        runs = []
        start = None
        for col in range(cols + 1):
            value = grid[object_row][col] if col < cols else background_color
            if value == object_color and start is None:
                start = col
            elif value != object_color and start is not None:
                runs.append((start, col - 1))
                start = None
        if not runs:
            raise ValueError("top_pattern_vertical_projection_obstacle_shift requires object runs")

        shifted_targets = {}
        for run_start, run_end in runs:
            in_run_guides = [col for col in guide_cols if run_start <= col <= run_end]
            if not in_run_guides:
                continue
            if len(in_run_guides) == 1:
                run_center = (run_start + run_end) / 2
                grid_center = (cols - 1) / 2
                preferred = run_start - 1 if run_center < grid_center else run_end + 1
                fallback = run_end + 1 if preferred == run_start - 1 else run_start - 1
                target = preferred if 0 <= preferred < cols else fallback
                if not (0 <= target < cols):
                    raise ValueError("top_pattern_vertical_projection_obstacle_shift has no shift target")
                shifted_targets[in_run_guides[0]] = target
                continue

            middle = (len(in_run_guides) - 1) / 2
            for index, guide_col in enumerate(in_run_guides):
                target = run_start - 1 if index <= middle else run_end + 1
                if not (0 <= target < cols):
                    raise ValueError("top_pattern_vertical_projection_obstacle_shift has no split target")
                shifted_targets[guide_col] = target

        target_by_guide = {
            guide_col: shifted_targets.get(guide_col, guide_col)
            for guide_col in guide_cols
        }
        if all(guide_col == target_col for guide_col, target_col in target_by_guide.items()):
            raise ValueError("top_pattern_vertical_projection_obstacle_shift found no obstacle shift")

        output = [row[:] for row in grid]
        changed = False
        for guide_col, target_col in target_by_guide.items():
            for row in range(top_row_count, rows):
                if grid[row][target_col] not in (background_color, guide_color):
                    raise ValueError("top_pattern_vertical_projection_obstacle_shift found projection collision")
                if output[row][target_col] != guide_color:
                    output[row][target_col] = guide_color
                    changed = True

            if guide_col != target_col:
                connector_row = object_row - 1
                if connector_row >= 0:
                    start_col = min(guide_col, target_col)
                    end_col = max(guide_col, target_col)
                    for col in range(start_col, end_col + 1):
                        if grid[connector_row][col] not in (background_color, guide_color):
                            raise ValueError("top_pattern_vertical_projection_obstacle_shift found connector collision")
                        if output[connector_row][col] != guide_color:
                            output[connector_row][col] = guide_color
                            changed = True

        if not changed:
            raise ValueError("top_pattern_vertical_projection_obstacle_shift made no changes")
        return output

    if object == "colored_corner_chebyshev_even_rings":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("colored_corner_chebyshev_even_rings requires a non-empty grid")
        if rows != cols:
            raise ValueError("colored_corner_chebyshev_even_rings requires a square grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("colored_corner_chebyshev_even_rings requires a rectangular grid")

        corner_positions = {
            (0, 0),
            (0, cols - 1),
            (rows - 1, 0),
            (rows - 1, cols - 1),
        }
        colored_corners = [
            (row, col, grid[row][col])
            for row, col in sorted(corner_positions)
            if grid[row][col] != 0
        ]
        if not colored_corners:
            raise ValueError("colored_corner_chebyshev_even_rings requires colored corners")
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] != 0 and (row, col) not in corner_positions:
                    raise ValueError("colored_corner_chebyshev_even_rings requires only corner markers")

        output = [[0 for _ in range(cols)] for _ in range(rows)]
        for row in range(rows):
            for col in range(cols):
                ownership_distances = [
                    (abs(row - corner_row) + abs(col - corner_col), corner_row, corner_col, corner_color)
                    for corner_row, corner_col, corner_color in colored_corners
                ]
                nearest_distance = min(distance for distance, _, _, _ in ownership_distances)
                nearest = [
                    (corner_row, corner_col, corner_color)
                    for distance, corner_row, corner_col, corner_color in ownership_distances
                    if distance == nearest_distance
                ]
                if len(nearest) == 1:
                    corner_row, corner_col, corner_color = nearest[0]
                    ring_distance = max(abs(row - corner_row), abs(col - corner_col))
                    if ring_distance % 2 == 0:
                        output[row][col] = corner_color
        return output

    if object == "parallel_diagonal_around_obstacle":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("parallel_diagonal_around_obstacle requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("parallel_diagonal_around_obstacle requires a rectangular grid")

        positions_by_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value != 0:
                    positions_by_color.setdefault(value, []).append((row, col))
        if len(positions_by_color) != 2:
            raise ValueError("parallel_diagonal_around_obstacle requires one line color and one obstacle color")

        line_candidates = []
        for candidate_color, positions in positions_by_color.items():
            offsets = {col - row for row, col in positions}
            if len(offsets) == 1 and len(positions) >= 2:
                line_candidates.append((candidate_color, next(iter(offsets))))
        if len(line_candidates) != 1:
            raise ValueError("parallel_diagonal_around_obstacle requires one slope-one diagonal line")

        line_color, line_offset = line_candidates[0]
        obstacle_positions = [
            position
            for candidate_color, positions in positions_by_color.items()
            if candidate_color != line_color
            for position in positions
        ]
        if not obstacle_positions:
            raise ValueError("parallel_diagonal_around_obstacle requires obstacle pixels")

        obstacle_offsets = [col - row for row, col in obstacle_positions]
        output_offsets = {line_offset}
        if any(obstacle_offset > line_offset for obstacle_offset in obstacle_offsets):
            output_offsets.add(max(obstacle_offsets) + 2)
        if any(obstacle_offset < line_offset for obstacle_offset in obstacle_offsets):
            output_offsets.add(min(obstacle_offsets) - 2)

        output = [[0 for _ in range(cols)] for _ in range(rows)]
        for diagonal_offset in output_offsets:
            for row in range(rows):
                col = row + diagonal_offset
                if 0 <= col < cols:
                    output[row][col] = line_color
        return output

    if object == "remove_rect_occluder_reflect_vertical_shape":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("remove_rect_occluder_reflect_vertical_shape requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("remove_rect_occluder_reflect_vertical_shape requires a rectangular grid")

        positions_by_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value != 0:
                    positions_by_color.setdefault(value, []).append((row, col))
        if len(positions_by_color) != 2:
            raise ValueError("remove_rect_occluder_reflect_vertical_shape requires two foreground colors")

        def components_for(positions):
            position_set = set(positions)
            seen = set()
            components = []
            for start in positions:
                if start in seen:
                    continue
                stack = [start]
                seen.add(start)
                component = []
                while stack:
                    row, col = stack.pop()
                    component.append((row, col))
                    for next_row, next_col in (
                        (row - 1, col),
                        (row + 1, col),
                        (row, col - 1),
                        (row, col + 1),
                    ):
                        if (next_row, next_col) in position_set and (next_row, next_col) not in seen:
                            seen.add((next_row, next_col))
                            stack.append((next_row, next_col))
                components.append(component)
            return components

        rectangular_components = []
        for candidate_color, positions in positions_by_color.items():
            for component in components_for(positions):
                component_set = set(component)
                min_row = min(row for row, _ in component)
                max_row = max(row for row, _ in component)
                min_col = min(col for _, col in component)
                max_col = max(col for _, col in component)
                area = (max_row - min_row + 1) * (max_col - min_col + 1)
                if area == len(component_set):
                    rectangular_components.append((
                        area,
                        candidate_color,
                        component_set,
                        min_row,
                        max_row,
                        min_col,
                        max_col,
                    ))
        if not rectangular_components:
            raise ValueError("remove_rect_occluder_reflect_vertical_shape found no solid rectangular occluder")

        _, occluder_color, occluder_positions, _, _, _, _ = max(rectangular_components)
        target_colors = [candidate for candidate in positions_by_color if candidate != occluder_color]
        if len(target_colors) != 1:
            raise ValueError("remove_rect_occluder_reflect_vertical_shape requires one target color")
        target_color = target_colors[0]
        target_positions = set(positions_by_color[target_color])

        best_axis = None
        best_score = None
        for axis2 in range(0, 2 * (cols - 1) + 1):
            penalty = 0
            matched = 0
            hidden = 0
            for row, col in target_positions:
                reflected_col = axis2 - col
                if not (0 <= reflected_col < cols):
                    penalty += 1
                elif (row, reflected_col) in target_positions:
                    matched += 1
                elif (row, reflected_col) in occluder_positions:
                    hidden += 1
                else:
                    penalty += 1
            if hidden == 0:
                continue
            score = (penalty, -hidden, -matched)
            if best_score is None or score < best_score:
                best_score = score
                best_axis = axis2

        if best_axis is None:
            raise ValueError("remove_rect_occluder_reflect_vertical_shape found no vertical symmetry axis")

        output = [row[:] for row in grid]
        for row, col in occluder_positions:
            output[row][col] = 0

        changed = False
        for row, col in target_positions:
            reflected_col = best_axis - col
            if (row, reflected_col) in occluder_positions:
                output[row][reflected_col] = target_color
                changed = True
        if not changed:
            raise ValueError("remove_rect_occluder_reflect_vertical_shape made no changes")
        return output

    if object == "proximity_marker_bbox_background_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("proximity_marker_bbox_background_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("proximity_marker_bbox_background_fill requires a rectangular grid")
        fill_color = color
        if fill_color in (None, 0):
            raise ValueError("proximity_marker_bbox_background_fill requires a non-background fill color")
        if any(value == fill_color for row in grid for value in row):
            raise ValueError("proximity_marker_bbox_background_fill expects a newly inserted fill color")

        counts = {}
        for row in grid:
            for value in row:
                if value != 0:
                    counts[value] = counts.get(value, 0) + 1
        if len(counts) < 2:
            raise ValueError("proximity_marker_bbox_background_fill requires background and marker colors")
        background_color = max(counts, key=lambda value: counts[value])
        marker_candidates = [
            value
            for value in sorted(counts)
            if value != background_color and value != fill_color
        ]
        if len(marker_candidates) != 1:
            raise ValueError("proximity_marker_bbox_background_fill requires one marker color")
        marker_color = marker_candidates[0]

        marker_positions = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == marker_color
        ]
        if not marker_positions:
            raise ValueError("proximity_marker_bbox_background_fill requires marker pixels")

        radius = 2
        remaining = set(marker_positions)
        groups = []
        while remaining:
            start = remaining.pop()
            stack = [start]
            group = [start]
            while stack:
                row, col = stack.pop()
                nearby = [
                    position
                    for position in remaining
                    if abs(position[0] - row) <= radius and abs(position[1] - col) <= radius
                ]
                for position in nearby:
                    remaining.remove(position)
                    stack.append(position)
                    group.append(position)
            groups.append(group)

        output = [row[:] for row in grid]
        changed = False
        for group in groups:
            min_row = min(row for row, _ in group)
            max_row = max(row for row, _ in group)
            min_col = min(col for _, col in group)
            max_col = max(col for _, col in group)
            for row in range(min_row, max_row + 1):
                for col in range(min_col, max_col + 1):
                    if output[row][col] == background_color:
                        output[row][col] = fill_color
                        changed = True

        if not changed:
            raise ValueError("proximity_marker_bbox_background_fill made no changes")
        return output

    if object == "repeat_hole_mask_from_marker_vector":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("repeat_hole_mask_from_marker_vector requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("repeat_hole_mask_from_marker_vector requires a rectangular grid")

        counts = {}
        for row in grid:
            for value in row:
                counts[value] = counts.get(value, 0) + 1
        background_color = max(counts, key=lambda value: counts[value])
        hole_color = 0
        if background_color == hole_color:
            raise ValueError("repeat_hole_mask_from_marker_vector requires nonzero dominant background")

        marker_colors = [
            value
            for value, count in sorted(counts.items())
            if value not in (background_color, hole_color) and count == 1
        ]
        if color not in (None, 0):
            marker_colors = [value for value in marker_colors if value == color]
        if len(marker_colors) != 1:
            raise ValueError("repeat_hole_mask_from_marker_vector requires one singleton marker color")
        marker_color = marker_colors[0]
        marker_position = next(
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == marker_color
        )

        hole_positions = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == hole_color
        ]
        if not hole_positions:
            raise ValueError("repeat_hole_mask_from_marker_vector requires hole pixels")

        diagonal_vectors = []
        marker_row, marker_col = marker_position
        for row, col in hole_positions:
            delta_row = marker_row - row
            delta_col = marker_col - col
            if delta_row != 0 and abs(delta_row) == abs(delta_col):
                diagonal_vectors.append((abs(delta_row), delta_row, delta_col))
        if not diagonal_vectors:
            raise ValueError("repeat_hole_mask_from_marker_vector found no diagonal marker vector")
        _, step_row, step_col = max(diagonal_vectors)

        output = [row[:] for row in grid]
        changed = False
        multiple = 1
        while True:
            any_in_bounds = False
            for row, col in hole_positions:
                target_row = row + multiple * step_row
                target_col = col + multiple * step_col
                if 0 <= target_row < rows and 0 <= target_col < cols:
                    any_in_bounds = True
                    if output[target_row][target_col] == background_color:
                        output[target_row][target_col] = marker_color
                        changed = True
            if not any_in_bounds:
                break
            multiple += 1

        if not changed:
            raise ValueError("repeat_hole_mask_from_marker_vector made no changes")
        return output

    if object == "eroded_zero_corridors":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("eroded_zero_corridors requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("eroded_zero_corridors requires a rectangular grid")
        if color in (None, 0):
            raise ValueError("eroded_zero_corridors requires a non-background fill color")

        background_color = 0 if color1 is None else color1
        zero_mask = [[grid[row][col] == background_color for col in range(cols)] for row in range(rows)]
        rectangles = []
        for top in range(rows):
            active_cols = [True] * cols
            for bottom in range(top, rows):
                for col in range(cols):
                    active_cols[col] = active_cols[col] and zero_mask[bottom][col]
                col = 0
                while col < cols:
                    if not active_cols[col]:
                        col += 1
                        continue
                    left = col
                    while col < cols and active_cols[col]:
                        col += 1
                    right = col - 1
                    rectangles.append((top, bottom, left, right))

        maximal_rectangles = []
        for rect in rectangles:
            top, bottom, left, right = rect
            rect_area = (bottom - top + 1) * (right - left + 1)
            contained = False
            for other in rectangles:
                if other == rect:
                    continue
                other_top, other_bottom, other_left, other_right = other
                other_area = (other_bottom - other_top + 1) * (other_right - other_left + 1)
                if (
                    other_area > rect_area
                    and other_top <= top
                    and other_bottom >= bottom
                    and other_left <= left
                    and other_right >= right
                ):
                    contained = True
                    break
            if not contained:
                maximal_rectangles.append(rect)

        def rect_area(rect):
            top, bottom, left, right = rect
            return (bottom - top + 1) * (right - left + 1)

        def intersection_area(first, second):
            top = max(first[0], second[0])
            bottom = min(first[1], second[1])
            left = max(first[2], second[2])
            right = min(first[3], second[3])
            if top > bottom or left > right:
                return 0
            return (bottom - top + 1) * (right - left + 1)

        corridor_candidates = []
        for rect in maximal_rectangles:
            top, bottom, left, right = rect
            height = bottom - top + 1
            width = right - left + 1
            area = height * width
            if (
                min(height, width) < 2
                or area < rows * cols * 0.05
                or max(height, width) < max(rows, cols) * 0.45
            ):
                continue

            core_top, core_bottom, core_left, core_right = top, bottom, left, right
            if height <= width:
                if height > 2:
                    core_top += 1
                    core_bottom -= 1
                if left > 0 and width > 2:
                    core_left += 1
                if right < cols - 1 and width > 2:
                    core_right -= 1
            else:
                if width > 2:
                    core_left += 1
                    core_right -= 1
                if top > 0 and height > 2:
                    core_top += 1
                if bottom < rows - 1 and height > 2:
                    core_bottom -= 1
                    if width <= 3:
                        core_bottom -= 1
            if core_top <= core_bottom and core_left <= core_right:
                corridor_candidates.append((area, (core_top, core_bottom, core_left, core_right)))

        selected_cores = []
        for _, core in sorted(corridor_candidates, reverse=True):
            area = rect_area(core)
            if any(intersection_area(core, selected) / area > 0.75 for selected in selected_cores):
                continue
            selected_cores.append(core)

        output = [row[:] for row in grid]
        changed = False
        for top, bottom, left, right in selected_cores:
            for row in range(top, bottom + 1):
                for col in range(left, right + 1):
                    if output[row][col] == background_color:
                        output[row][col] = color
                        changed = True
        if not changed:
            raise ValueError("eroded_zero_corridors made no changes")
        return output

    if object == "checkerboard_seed_component_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("checkerboard_seed_component_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("checkerboard_seed_component_fill requires a rectangular grid")

        background_color = 0 if color1 is None else color1
        counts = {}
        for row in grid:
            for value in row:
                counts[value] = counts.get(value, 0) + 1
        non_background = [value for value in counts if value != background_color]
        if len(non_background) < 3:
            raise ValueError("checkerboard_seed_component_fill requires wall color and two seed colors")

        wall_color = max(non_background, key=lambda value: (counts[value], -value))
        seed_colors = sorted(value for value in non_background if value != wall_color)
        if len(seed_colors) != 2:
            raise ValueError("checkerboard_seed_component_fill requires exactly two seed colors")

        parity_to_color = {}
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value not in seed_colors:
                    continue
                parity = (row + col) % 2
                if parity in parity_to_color and parity_to_color[parity] != value:
                    raise ValueError("checkerboard_seed_component_fill found inconsistent seed parity")
                parity_to_color[parity] = value
        if len(parity_to_color) != 2:
            raise ValueError("checkerboard_seed_component_fill requires both parities")

        output = [row[:] for row in grid]
        visited = set()
        changed = False
        for start_row in range(rows):
            for start_col in range(cols):
                if (start_row, start_col) in visited or grid[start_row][start_col] == wall_color:
                    continue
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                component = []
                has_seed = False
                while stack:
                    row, col = stack.pop()
                    component.append((row, col))
                    if grid[row][col] in seed_colors:
                        has_seed = True
                    for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        next_row = row + delta_row
                        next_col = col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (next_row, next_col) in visited:
                            continue
                        if grid[next_row][next_col] == wall_color:
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                if not has_seed:
                    continue
                for row, col in component:
                    if output[row][col] == background_color:
                        output[row][col] = parity_to_color[(row + col) % 2]
                        changed = True

        if not changed:
            raise ValueError("checkerboard_seed_component_fill made no changes")
        return output

    if object == "stamp_scaled_template_from_anchor_components":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("stamp_scaled_template_from_anchor_components requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("stamp_scaled_template_from_anchor_components requires a rectangular grid")

        visited = set()
        components = []
        for start_row in range(rows):
            for start_col in range(cols):
                if grid[start_row][start_col] == 0 or (start_row, start_col) in visited:
                    continue
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                cells = []
                while stack:
                    row, col = stack.pop()
                    cells.append((row, col))
                    for delta_row in (-1, 0, 1):
                        for delta_col in (-1, 0, 1):
                            if delta_row == 0 and delta_col == 0:
                                continue
                            next_row = row + delta_row
                            next_col = col + delta_col
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if (next_row, next_col) in visited or grid[next_row][next_col] == 0:
                                continue
                            visited.add((next_row, next_col))
                            stack.append((next_row, next_col))

                min_row = min(row for row, _ in cells)
                max_row = max(row for row, _ in cells)
                min_col = min(col for _, col in cells)
                max_col = max(col for _, col in cells)
                pattern = [
                    [grid[row][col] for col in range(min_col, max_col + 1)]
                    for row in range(min_row, max_row + 1)
                ]
                components.append({
                    "index": len(components),
                    "cells": set(cells),
                    "colors": {grid[row][col] for row, col in cells},
                    "bbox": (min_row, max_row, min_col, max_col),
                    "pattern": pattern,
                    "has_hole": any(value == 0 for pattern_row in pattern for value in pattern_row),
                })

        candidates = [
            component
            for component in components
            if len(component["colors"]) == 2
        ]
        source_candidates = [
            component
            for component in candidates
            if component["has_hole"]
        ]
        if not source_candidates:
            raise ValueError("stamp_scaled_template_from_anchor_components found no source template")

        def scaled_pattern(source, anchor_color, source_fill_color, target_fill_color, scale):
            scaled = []
            for pattern_row in source["pattern"]:
                expanded_row = []
                for value in pattern_row:
                    if value == anchor_color:
                        mapped_value = anchor_color
                    elif value == source_fill_color:
                        mapped_value = target_fill_color
                    else:
                        mapped_value = 0
                    expanded_row.extend([mapped_value] * scale)
                for _ in range(scale):
                    scaled.append(expanded_row[:])
            return scaled

        best_plan = None
        for source in source_candidates:
            plan = []
            for target in candidates:
                if target["index"] == source["index"]:
                    continue
                shared_colors = source["colors"] & target["colors"]
                if len(shared_colors) != 1:
                    continue
                anchor_color = next(iter(shared_colors))
                source_fill_color = next(iter(source["colors"] - {anchor_color}))
                target_fill_color = next(iter(target["colors"] - {anchor_color}))

                target_plan_candidates = []
                for scale in range(1, 6):
                    scaled = scaled_pattern(source, anchor_color, source_fill_color, target_fill_color, scale)
                    height = len(scaled)
                    width = len(scaled[0]) if scaled else 0
                    if height == 0 or width == 0 or height > rows or width > cols:
                        continue
                    nonzero = [
                        (row, col, scaled[row][col])
                        for row in range(height)
                        for col in range(width)
                        if scaled[row][col] != 0
                    ]
                    for top in range(rows - height + 1):
                        for left in range(cols - width + 1):
                            if all(
                                0 <= row - top < height
                                and 0 <= col - left < width
                                and scaled[row - top][col - left] == grid[row][col]
                                for row, col in target["cells"]
                            ):
                                conflict = False
                                new_cells = 0
                                for delta_row, delta_col, value in nonzero:
                                    row = top + delta_row
                                    col = left + delta_col
                                    current = grid[row][col]
                                    if current != 0 and current != value and (row, col) not in target["cells"]:
                                        conflict = True
                                        break
                                    if current == 0:
                                        new_cells += 1
                                if conflict or new_cells == 0:
                                    continue
                                target_plan_candidates.append((
                                    height * width,
                                    new_cells,
                                    top,
                                    left,
                                    nonzero,
                                ))
                if target_plan_candidates:
                    _, _, top, left, nonzero = min(target_plan_candidates)
                    plan.append((top, left, nonzero))

            if plan:
                source_height = source["bbox"][1] - source["bbox"][0] + 1
                source_width = source["bbox"][3] - source["bbox"][2] + 1
                score = (len(plan), -source_height * source_width, plan)
                if best_plan is None or score > best_plan:
                    best_plan = score

        if best_plan is None:
            raise ValueError("stamp_scaled_template_from_anchor_components found no target stamps")

        output = [row[:] for row in grid]
        changed = False
        for top, left, nonzero in best_plan[2]:
            for delta_row, delta_col, value in nonzero:
                row = top + delta_row
                col = left + delta_col
                if output[row][col] == 0:
                    output[row][col] = value
                    changed = True
        if not changed:
            raise ValueError("stamp_scaled_template_from_anchor_components made no changes")
        return output

    if object == "stamp_source_shape_to_marker_components":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("stamp_source_shape_to_marker_components requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("stamp_source_shape_to_marker_components requires a rectangular grid")

        background_color = color1

        visited = set()
        components = []
        for start_row in range(rows):
            for start_col in range(cols):
                if grid[start_row][start_col] == background_color or (start_row, start_col) in visited:
                    continue
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                cells = []
                colors = set()
                while stack:
                    row, col = stack.pop()
                    cells.append((row, col))
                    colors.add(grid[row][col])
                    for delta_row in (-1, 0, 1):
                        for delta_col in (-1, 0, 1):
                            if delta_row == 0 and delta_col == 0:
                                continue
                            next_row = row + delta_row
                            next_col = col + delta_col
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if (
                                (next_row, next_col) in visited
                                or grid[next_row][next_col] == background_color
                            ):
                                continue
                            visited.add((next_row, next_col))
                            stack.append((next_row, next_col))

                min_row = min(row for row, _ in cells)
                max_row = max(row for row, _ in cells)
                min_col = min(col for _, col in cells)
                max_col = max(col for _, col in cells)
                pattern = [
                    [grid[row][col] for col in range(min_col, max_col + 1)]
                    for row in range(min_row, max_row + 1)
                ]
                components.append({
                    "cells": set(cells),
                    "colors": colors,
                    "bbox": (min_row, max_row, min_col, max_col),
                    "pattern": pattern,
                })

        source_plans = []
        for source in components:
            if len(source["colors"]) != 2:
                continue

            source_cells = source["cells"]
            for marker_color in source["colors"]:
                outside_markers = [
                    (row, col)
                    for row in range(rows)
                    for col in range(cols)
                    if grid[row][col] == marker_color and (row, col) not in source_cells
                ]
                if not outside_markers:
                    continue

                placements = []
                for scale in range(1, 8):
                    scaled = []
                    for pattern_row in source["pattern"]:
                        expanded_row = []
                        for value in pattern_row:
                            expanded_row.extend([value] * scale)
                        for _ in range(scale):
                            scaled.append(expanded_row[:])

                    scaled_rows = len(scaled)
                    scaled_cols = len(scaled[0]) if scaled else 0
                    if scaled_rows == 0 or scaled_cols == 0:
                        continue

                    nonzero = [
                        (row, col, scaled[row][col])
                        for row in range(scaled_rows)
                        for col in range(scaled_cols)
                        if scaled[row][col] != background_color
                    ]

                    for top in range(-scaled_rows + 1, rows):
                        for left in range(-scaled_cols + 1, cols):
                            anchor_cells = 0
                            new_cells = 0
                            covers_outside_marker = False
                            conflict = False

                            for delta_row, delta_col, value in nonzero:
                                row = top + delta_row
                                col = left + delta_col
                                if not (0 <= row < rows and 0 <= col < cols):
                                    continue

                                current = grid[row][col]
                                if value == marker_color:
                                    if current != marker_color:
                                        conflict = True
                                        break
                                    anchor_cells += 1
                                    if (row, col) not in source_cells:
                                        covers_outside_marker = True
                                else:
                                    if current != background_color and current != value:
                                        conflict = True
                                        break
                                    if current == background_color:
                                        new_cells += 1

                            if conflict or anchor_cells == 0 or new_cells == 0 or not covers_outside_marker:
                                continue

                            placements.append({
                                "anchor": anchor_cells,
                                "new": new_cells,
                                "scale": scale,
                                "top": top,
                                "left": left,
                                "nonzero": nonzero,
                            })

                if placements:
                    source_plans.append({
                        "source": source,
                        "marker_color": marker_color,
                        "placements": placements,
                    })

        if not source_plans:
            raise ValueError("stamp_source_shape_to_marker_components found no source/marker placements")

        best_plan = max(
            source_plans,
            key=lambda plan: (
                sum(placement["new"] for placement in plan["placements"]),
                len(plan["placements"]),
            ),
        )

        output = [row[:] for row in grid]
        used_marker_cells = set()
        changed = False
        placements = sorted(
            best_plan["placements"],
            key=lambda placement: (
                -placement["anchor"],
                -placement["new"],
                placement["scale"],
                placement["top"],
                placement["left"],
            ),
        )
        source_cells = best_plan["source"]["cells"]
        marker_color = best_plan["marker_color"]
        for placement in placements:
            marker_cells = {
                (placement["top"] + delta_row, placement["left"] + delta_col)
                for delta_row, delta_col, value in placement["nonzero"]
                if value == marker_color
                and 0 <= placement["top"] + delta_row < rows
                and 0 <= placement["left"] + delta_col < cols
                and (placement["top"] + delta_row, placement["left"] + delta_col) not in source_cells
            }
            if not marker_cells or marker_cells & used_marker_cells:
                continue

            conflict = False
            for delta_row, delta_col, value in placement["nonzero"]:
                row = placement["top"] + delta_row
                col = placement["left"] + delta_col
                if not (0 <= row < rows and 0 <= col < cols):
                    continue
                current = output[row][col]
                if current != background_color and current != value:
                    conflict = True
                    break
            if conflict:
                continue

            for delta_row, delta_col, value in placement["nonzero"]:
                row = placement["top"] + delta_row
                col = placement["left"] + delta_col
                if 0 <= row < rows and 0 <= col < cols and output[row][col] == background_color:
                    output[row][col] = value
                    changed = True
            used_marker_cells |= marker_cells

        if not changed:
            raise ValueError("stamp_source_shape_to_marker_components made no changes")
        return output

    if object == "stamp_scaled_motif_to_marker_pairs":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("stamp_scaled_motif_to_marker_pairs requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("stamp_scaled_motif_to_marker_pairs requires a rectangular grid")

        color_counts = {}
        for row in grid:
            for value in row:
                color_counts[value] = color_counts.get(value, 0) + 1
        background_color = max(color_counts, key=lambda value: (color_counts[value], -value))

        source_plan = None
        for top in range(rows):
            for bottom in range(top, min(rows, top + 6)):
                for left in range(cols):
                    for right in range(left, min(cols, left + 6)):
                        cells = {
                            (row, col)
                            for row in range(top, bottom + 1)
                            for col in range(left, right + 1)
                            if grid[row][col] != background_color
                        }
                        if len(cells) < 4:
                            continue
                        colors = {grid[row][col] for row, col in cells}
                        if len(colors) != 3:
                            continue

                        outside_counts = {candidate_color: 0 for candidate_color in colors}
                        for row in range(rows):
                            for col in range(cols):
                                value = grid[row][col]
                                if value in colors and (row, col) not in cells:
                                    outside_counts[value] += 1

                        fill_candidates = [
                            candidate_color
                            for candidate_color in colors
                            if outside_counts[candidate_color] == 0
                        ]
                        marker_candidates = {
                            candidate_color
                            for candidate_color in colors
                            if outside_counts[candidate_color] > 0
                        }
                        if len(fill_candidates) != 1 or len(marker_candidates) != 2:
                            continue

                        motif = [
                            [grid[row][col] for col in range(left, right + 1)]
                            for row in range(top, bottom + 1)
                        ]
                        fill_color = fill_candidates[0]
                        fill_count = sum(1 for row, col in cells if grid[row][col] == fill_color)
                        area = (bottom - top + 1) * (right - left + 1)
                        score = (-area, fill_count, len(cells), -top, -left)
                        candidate = (
                            score,
                            cells,
                            fill_color,
                            marker_candidates,
                            motif,
                        )
                        if source_plan is None or score > source_plan[0]:
                            source_plan = candidate

        if source_plan is None:
            raise ValueError("stamp_scaled_motif_to_marker_pairs found no source motif")

        _, source_cells, fill_color, marker_colors, motif = source_plan

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

        def scale_tile(tile, scale):
            scaled = []
            for tile_row in tile:
                expanded_row = []
                for value in tile_row:
                    expanded_row.extend([value] * scale)
                for _ in range(scale):
                    scaled.append(expanded_row[:])
            return scaled

        placements = []
        for variant in tile_variants(motif):
            for scale in range(1, 8):
                scaled = scale_tile(variant, scale)
                scaled_rows = len(scaled)
                scaled_cols = len(scaled[0]) if scaled else 0
                if scaled_rows == 0 or scaled_cols == 0 or scaled_rows > rows or scaled_cols > cols:
                    continue
                non_background = [
                    (row, col, scaled[row][col])
                    for row in range(scaled_rows)
                    for col in range(scaled_cols)
                    if scaled[row][col] != background_color
                ]
                if any(
                    not any(value == marker_color for _, _, value in non_background)
                    for marker_color in marker_colors
                ):
                    continue

                for top in range(rows - scaled_rows + 1):
                    for left in range(cols - scaled_cols + 1):
                        anchors = {marker_color: 0 for marker_color in marker_colors}
                        outside_anchor = False
                        new_cells = 0
                        conflict = False

                        for delta_row, delta_col, value in non_background:
                            row = top + delta_row
                            col = left + delta_col
                            current = grid[row][col]
                            if value in marker_colors:
                                if current != value:
                                    conflict = True
                                    break
                                anchors[value] += 1
                                if (row, col) not in source_cells:
                                    outside_anchor = True
                            elif value == fill_color:
                                if current not in (background_color, fill_color):
                                    conflict = True
                                    break
                                if current == background_color:
                                    new_cells += 1
                            else:
                                conflict = True
                                break

                        if (
                            conflict
                            or new_cells == 0
                            or not outside_anchor
                            or any(anchors[marker_color] == 0 for marker_color in marker_colors)
                        ):
                            continue
                        if all(
                            (top + delta_row, left + delta_col) in source_cells
                            for delta_row, delta_col, value in non_background
                            if value in marker_colors
                        ):
                            continue

                        placements.append((
                            sum(anchors.values()),
                            new_cells,
                            scale,
                            top,
                            left,
                            non_background,
                        ))

        if not placements:
            raise ValueError("stamp_scaled_motif_to_marker_pairs found no target placements")

        output = [row[:] for row in grid]
        used_marker_cells = set()
        changed = False
        for _, _, _, top, left, non_background in sorted(
            placements,
            key=lambda item: (-item[0], -item[1], item[3], item[4]),
        ):
            marker_cells = {
                (top + delta_row, left + delta_col)
                for delta_row, delta_col, value in non_background
                if value in marker_colors
                and (top + delta_row, left + delta_col) not in source_cells
            }
            if not marker_cells or marker_cells & used_marker_cells:
                continue

            conflict = False
            for delta_row, delta_col, value in non_background:
                row = top + delta_row
                col = left + delta_col
                current = output[row][col]
                if value in marker_colors:
                    if current != value:
                        conflict = True
                        break
                elif value == fill_color:
                    if current not in (background_color, fill_color):
                        conflict = True
                        break
            if conflict:
                continue

            for delta_row, delta_col, value in non_background:
                row = top + delta_row
                col = left + delta_col
                if value == fill_color and output[row][col] == background_color:
                    output[row][col] = fill_color
                    changed = True
            used_marker_cells |= marker_cells

        if not changed:
            raise ValueError("stamp_scaled_motif_to_marker_pairs made no changes")
        return output

    if object == "reposition_source_motifs_to_marker_targets":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("reposition_source_motifs_to_marker_targets requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("reposition_source_motifs_to_marker_targets requires a rectangular grid")

        background_color = 0

        visited = set()
        components = []
        for start_row in range(rows):
            for start_col in range(cols):
                if grid[start_row][start_col] == background_color or (start_row, start_col) in visited:
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
                    for delta_row in (-1, 0, 1):
                        for delta_col in (-1, 0, 1):
                            if delta_row == 0 and delta_col == 0:
                                continue
                            next_row = row + delta_row
                            next_col = col + delta_col
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if (
                                (next_row, next_col) in visited
                                or grid[next_row][next_col] == background_color
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
                })

        sources = []
        for component in components:
            if len(component["counts"]) < 3:
                continue
            fill_color = max(
                component["counts"],
                key=lambda value: (component["counts"][value], -value),
            )
            if component["counts"][fill_color] < 2:
                continue
            marker_colors = set(component["counts"]) - {fill_color}
            min_row, max_row, min_col, max_col = component["bbox"]
            motif = [
                [
                    grid[row][col] if (row, col) in component["cells"] else background_color
                    for col in range(min_col, max_col + 1)
                ]
                for row in range(min_row, max_row + 1)
            ]
            sources.append({
                "cells": component["cells"],
                "fill_color": fill_color,
                "marker_colors": marker_colors,
                "motif": motif,
                "area": (max_row - min_row + 1) * (max_col - min_col + 1),
            })

        if not sources:
            raise ValueError("reposition_source_motifs_to_marker_targets found no source motifs")

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

        source_cells = set()
        for source in sources:
            source_cells.update(source["cells"])

        output = [row[:] for row in grid]
        for row, col in source_cells:
            output[row][col] = background_color

        placements = []
        for source_index, source in enumerate(sources):
            for variant in tile_variants(source["motif"]):
                variant_rows = len(variant)
                variant_cols = len(variant[0]) if variant else 0
                non_background = [
                    (row, col, variant[row][col])
                    for row in range(variant_rows)
                    for col in range(variant_cols)
                    if variant[row][col] != background_color
                ]
                marker_cells = [
                    (row, col, value)
                    for row, col, value in non_background
                    if value in source["marker_colors"]
                ]
                fill_cells = [
                    (row, col, value)
                    for row, col, value in non_background
                    if value == source["fill_color"]
                ]
                if not marker_cells or not fill_cells:
                    continue

                for top in range(rows - variant_rows + 1):
                    for left in range(cols - variant_cols + 1):
                        placed_cells = {
                            (top + row, left + col)
                            for row, col, _ in non_background
                        }
                        if placed_cells & source["cells"]:
                            continue

                        anchors = 0
                        new_cells = 0
                        conflict = False
                        for delta_row, delta_col, value in marker_cells:
                            row = top + delta_row
                            col = left + delta_col
                            if grid[row][col] != value:
                                conflict = True
                                break
                            anchors += 1
                        if conflict:
                            continue

                        for delta_row, delta_col, _ in fill_cells:
                            row = top + delta_row
                            col = left + delta_col
                            current = grid[row][col]
                            if current not in (background_color, source["fill_color"]):
                                conflict = True
                                break
                            if current == background_color:
                                new_cells += 1
                        if conflict or new_cells == 0:
                            continue

                        placements.append((
                            anchors,
                            new_cells,
                            -source["area"],
                            source_index,
                            top,
                            left,
                            non_background,
                            source,
                        ))

        if not placements:
            raise ValueError("reposition_source_motifs_to_marker_targets found no placements")

        used_marker_cells = set()
        changed = False
        for _, _, _, _, top, left, non_background, source in sorted(
            placements,
            key=lambda item: (-item[0], -item[1], item[4], item[5]),
        ):
            marker_targets = {
                (top + delta_row, left + delta_col)
                for delta_row, delta_col, value in non_background
                if value in source["marker_colors"]
            }
            if marker_targets & used_marker_cells:
                continue

            conflict = False
            for delta_row, delta_col, value in non_background:
                row = top + delta_row
                col = left + delta_col
                current = output[row][col]
                if value in source["marker_colors"]:
                    if current != value:
                        conflict = True
                        break
                elif value == source["fill_color"]:
                    if current not in (background_color, source["fill_color"]):
                        conflict = True
                        break
            if conflict:
                continue

            for delta_row, delta_col, value in non_background:
                row = top + delta_row
                col = left + delta_col
                if value == source["fill_color"] and output[row][col] == background_color:
                    output[row][col] = value
                    changed = True
            used_marker_cells |= marker_targets

        if not changed:
            raise ValueError("reposition_source_motifs_to_marker_targets made no changes")
        return output

    if object == "marker_pair_maximal_corridor_path":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("marker_pair_maximal_corridor_path requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("marker_pair_maximal_corridor_path requires a rectangular grid")

        background_color = 0
        source_color = 3
        target_color = 2

        def components_of(component_color):
            seen = set()
            components = []
            for start_row in range(rows):
                for start_col in range(cols):
                    if grid[start_row][start_col] != component_color or (start_row, start_col) in seen:
                        continue
                    stack = [(start_row, start_col)]
                    seen.add((start_row, start_col))
                    cells = []
                    while stack:
                        row, col = stack.pop()
                        cells.append((row, col))
                        for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            next_row = row + delta_row
                            next_col = col + delta_col
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if (
                                (next_row, next_col) in seen
                                or grid[next_row][next_col] != component_color
                            ):
                                continue
                            seen.add((next_row, next_col))
                            stack.append((next_row, next_col))
                    components.append(set(cells))
            return components

        def extension(cells, direction):
            result = set()
            if direction == "UP":
                for col in sorted({col for _, col in cells}):
                    row = min(row for row, cell_col in cells if cell_col == col) - 1
                    while row >= 0 and grid[row][col] == background_color:
                        result.add((row, col))
                        row -= 1
            elif direction == "DOWN":
                for col in sorted({col for _, col in cells}):
                    row = max(row for row, cell_col in cells if cell_col == col) + 1
                    while row < rows and grid[row][col] == background_color:
                        result.add((row, col))
                        row += 1
            elif direction == "LEFT":
                for row in sorted({row for row, _ in cells}):
                    col = min(col for cell_row, col in cells if cell_row == row) - 1
                    while col >= 0 and grid[row][col] == background_color:
                        result.add((row, col))
                        col -= 1
            elif direction == "RIGHT":
                for row in sorted({row for row, _ in cells}):
                    col = max(col for cell_row, col in cells if cell_row == row) + 1
                    while col < cols and grid[row][col] == background_color:
                        result.add((row, col))
                        col += 1
            else:
                raise ValueError(f"Unknown direction: {direction}")
            return result

        def corridor_path(source_cells, target_cells, source_direction, target_direction):
            source_extension = extension(source_cells, source_direction)
            target_extension = extension(target_cells, target_direction)
            if not source_extension or not target_extension:
                return None
            if (
                source_direction in ("UP", "DOWN")
                and {col for _, col in source_extension} != {col for _, col in source_cells}
            ):
                return None
            if (
                target_direction in ("UP", "DOWN")
                and {col for _, col in target_extension} != {col for _, col in target_cells}
            ):
                return None
            if (
                source_direction in ("LEFT", "RIGHT")
                and {row for row, _ in source_extension} != {row for row, _ in source_cells}
            ):
                return None
            if (
                target_direction in ("LEFT", "RIGHT")
                and {row for row, _ in target_extension} != {row for row, _ in target_cells}
            ):
                return None

            candidates = []
            if source_direction in ("LEFT", "RIGHT") and target_direction in ("LEFT", "RIGHT"):
                common_cols = sorted(
                    {col for _, col in source_extension}
                    & {col for _, col in target_extension}
                )
                for col in common_cols:
                    source_rows = {row for row, cell_col in source_extension if cell_col == col}
                    target_rows = {row for row, cell_col in target_extension if cell_col == col}
                    for source_row in source_rows:
                        for target_row in target_rows:
                            min_row = min(source_row, target_row)
                            max_row = max(source_row, target_row)
                            connector = {(row, col) for row in range(min_row, max_row + 1)}
                            if any(
                                grid[row][col] != background_color
                                and (row, col) not in source_cells
                                and (row, col) not in target_cells
                                for row, col in connector
                            ):
                                continue
                            path = {
                                point
                                for point in source_extension
                                if point[0] == source_row
                                and (
                                    point[1] <= col
                                    if source_direction == "RIGHT"
                                    else point[1] >= col
                                )
                            }
                            path |= {
                                point
                                for point in target_extension
                                if point[0] == target_row
                                and (
                                    point[1] <= col
                                    if target_direction == "RIGHT"
                                    else point[1] >= col
                                )
                            }
                            path |= connector
                            candidates.append(path)

            if source_direction in ("UP", "DOWN") and target_direction in ("UP", "DOWN"):
                common_rows = sorted(
                    {row for row, _ in source_extension}
                    & {row for row, _ in target_extension}
                )
                for row in common_rows:
                    source_cols = {col for cell_row, col in source_extension if cell_row == row}
                    target_cols = {col for cell_row, col in target_extension if cell_row == row}
                    for source_col in source_cols:
                        for target_col in target_cols:
                            min_col = min(source_col, target_col)
                            max_col = max(source_col, target_col)
                            connector = {(row, col) for col in range(min_col, max_col + 1)}
                            if any(
                                grid[row][col] != background_color
                                and (row, col) not in source_cells
                                and (row, col) not in target_cells
                                for row, col in connector
                            ):
                                continue
                            path = {
                                point
                                for point in source_extension
                                if point[1] == source_col
                                and (
                                    point[0] <= row
                                    if source_direction == "DOWN"
                                    else point[0] >= row
                                )
                            }
                            path |= {
                                point
                                for point in target_extension
                                if point[1] == target_col
                                and (
                                    point[0] <= row
                                    if target_direction == "DOWN"
                                    else point[0] >= row
                                )
                            }
                            path |= connector
                            candidates.append(path)

            if not candidates:
                return None
            return max(candidates, key=len)

        source_components = components_of(source_color)
        target_components = components_of(target_color)
        if not source_components or not target_components:
            raise ValueError("marker_pair_maximal_corridor_path requires source and target markers")

        path_candidates = []
        for source_cells in source_components:
            for target_cells in target_components:
                source_min_row = min(row for row, _ in source_cells)
                source_max_row = max(row for row, _ in source_cells)
                source_min_col = min(col for _, col in source_cells)
                source_max_col = max(col for _, col in source_cells)
                target_min_row = min(row for row, _ in target_cells)
                target_max_row = max(row for row, _ in target_cells)
                target_min_col = min(col for _, col in target_cells)
                target_max_col = max(col for _, col in target_cells)
                col_overlap = not (source_max_col < target_min_col or target_max_col < source_min_col)
                row_overlap = not (source_max_row < target_min_row or target_max_row < source_min_row)

                preferred = []
                if col_overlap:
                    preferred = [("RIGHT", "RIGHT"), ("LEFT", "LEFT")]
                elif row_overlap:
                    preferred = [("DOWN", "DOWN"), ("UP", "UP")]
                else:
                    if source_max_row < target_min_row:
                        preferred.append(("DOWN", "UP"))
                    else:
                        preferred.append(("UP", "DOWN"))
                    if source_max_col < target_min_col:
                        preferred.append(("RIGHT", "RIGHT"))
                    else:
                        preferred.append(("LEFT", "LEFT"))

                for rank, (source_direction, target_direction) in enumerate(preferred):
                    path = corridor_path(source_cells, target_cells, source_direction, target_direction)
                    if not path:
                        continue
                    path_candidates.append((len(path), -rank, path))

        if not path_candidates:
            raise ValueError("marker_pair_maximal_corridor_path found no corridor")

        _, _, path = max(path_candidates, key=lambda item: item[:2])
        output = [row[:] for row in grid]
        changed = False
        for row, col in path:
            if output[row][col] == background_color:
                output[row][col] = source_color
                changed = True
        if not changed:
            raise ValueError("marker_pair_maximal_corridor_path made no changes")
        return output

    if object == "stamp_template_from_compact_markers":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("stamp_template_from_compact_markers requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("stamp_template_from_compact_markers requires a rectangular grid")

        stamp_color = 1 if any(1 in row for row in grid) else color
        marker_color = 4 if any(4 in row for row in grid) else color1
        if stamp_color == 0 or marker_color == 0 or stamp_color == marker_color:
            raise ValueError("stamp_template_from_compact_markers requires stamp and marker colors")

        def mixed_components():
            seen = set()
            components = []
            for row in range(rows):
                for col in range(cols):
                    if grid[row][col] not in (stamp_color, marker_color) or (row, col) in seen:
                        continue
                    stack = [(row, col)]
                    seen.add((row, col))
                    comp = []
                    while stack:
                        rr, cc = stack.pop()
                        comp.append((rr, cc, grid[rr][cc]))
                        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            nr, nc = rr + dr, cc + dc
                            if not (0 <= nr < rows and 0 <= nc < cols):
                                continue
                            if grid[nr][nc] not in (stamp_color, marker_color) or (nr, nc) in seen:
                                continue
                            seen.add((nr, nc))
                            stack.append((nr, nc))
                    components.append(comp)
            return components

        components = mixed_components()
        source = max(components, key=len)
        source_cells = {(row, col) for row, col, _ in source}
        if not any(value == stamp_color for _, _, value in source) or not any(value == marker_color for _, _, value in source):
            raise ValueError("stamp_template_from_compact_markers requires a mixed source template")
        min_row = min(row for row, _, _ in source)
        min_col = min(col for _, col, _ in source)
        source_ones = {
            (row - min_row, col - min_col)
            for row, col, value in source
            if value == stamp_color
        }
        source_markers = {
            (row - min_row, col - min_col)
            for row, col, value in source
            if value == marker_color
        }
        source_height = max(row for row, _, _ in source) - min_row + 1
        source_width = max(col for _, col, _ in source) - min_col + 1
        if not source_ones or not source_markers:
            raise ValueError("stamp_template_from_compact_markers found no usable source template")

        all_markers = {
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == marker_color
        }

        def d4_variants(ones, markers, height, width):
            transforms = [
                lambda row, col: (row, col),
                lambda row, col: (col, height - 1 - row),
                lambda row, col: (height - 1 - row, width - 1 - col),
                lambda row, col: (width - 1 - col, row),
                lambda row, col: (row, width - 1 - col),
                lambda row, col: (height - 1 - row, col),
                lambda row, col: (col, row),
                lambda row, col: (width - 1 - col, height - 1 - row),
            ]
            variants = []
            for transform in transforms:
                all_points = [transform(row, col) for row, col in ones | markers]
                row0 = min(row for row, _ in all_points)
                col0 = min(col for _, col in all_points)
                var_ones = {
                    (transform(row, col)[0] - row0, transform(row, col)[1] - col0)
                    for row, col in ones
                }
                var_markers = {
                    (transform(row, col)[0] - row0, transform(row, col)[1] - col0)
                    for row, col in markers
                }
                var_height = max(row for row, _ in var_ones | var_markers) + 1
                var_width = max(col for _, col in var_ones | var_markers) + 1
                variant = (var_ones, var_markers, var_height, var_width)
                if variant not in variants:
                    variants.append(variant)
            return variants

        def connected(cells):
            cells = set(cells)
            if not cells:
                return False
            stack = [next(iter(cells))]
            seen = {stack[0]}
            while stack:
                row, col = stack.pop()
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nxt = (row + dr, col + dc)
                    if nxt in cells and nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            return seen == cells

        def compact_marker_overlap(overlap):
            if len(overlap) == len(source_markers):
                return True
            overlap_rows = [row for row, _ in overlap]
            overlap_cols = [col for _, col in overlap]
            area = (
                (max(overlap_rows) - min(overlap_rows) + 1)
                * (max(overlap_cols) - min(overlap_cols) + 1)
            )
            if area > 6:
                return False
            if len(overlap) == 2 and not connected(overlap):
                return False
            return True

        min_stamp_size = (7 * len(source_ones) + 9) // 10
        candidates = []
        for var_ones, var_markers, var_height, var_width in d4_variants(
            source_ones,
            source_markers,
            source_height,
            source_width,
        ):
            for row0 in range(-var_height + 1, rows):
                for col0 in range(-var_width + 1, cols):
                    placed_ones = {
                        (row0 + row, col0 + col)
                        for row, col in var_ones
                        if 0 <= row0 + row < rows and 0 <= col0 + col < cols
                    }
                    placed_markers = {
                        (row0 + row, col0 + col)
                        for row, col in var_markers
                        if 0 <= row0 + row < rows and 0 <= col0 + col < cols
                    }
                    if len(placed_ones) < min_stamp_size:
                        continue
                    if placed_ones & source_cells:
                        continue
                    if not all(grid[row][col] in (0, stamp_color) for row, col in placed_ones):
                        continue
                    overlap = placed_markers & all_markers
                    if len(overlap) < 2:
                        continue
                    if not compact_marker_overlap(overlap):
                        continue
                    candidates.append((
                        -len(overlap),
                        -len(placed_ones),
                        row0,
                        col0,
                        placed_ones,
                    ))

        output = [row[:] for row in grid]
        used = set()
        for _, _, _, _, placed_ones in sorted(candidates):
            if used & placed_ones:
                continue
            for row, col in placed_ones:
                if output[row][col] == 0:
                    output[row][col] = stamp_color
            used |= placed_ones

        if output == grid:
            raise ValueError("stamp_template_from_compact_markers found no target stamps")
        return output

    if object == "reflect_source_shape_to_adjacent_markers":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("reflect_source_shape_to_adjacent_markers requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("reflect_source_shape_to_adjacent_markers requires a rectangular grid")

        directions = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ]

        seen = set()
        components = []
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] == 0 or (row, col) in seen:
                    continue
                stack = [(row, col)]
                seen.add((row, col))
                comp = []
                while stack:
                    rr, cc = stack.pop()
                    comp.append((rr, cc, grid[rr][cc]))
                    for dr, dc in directions:
                        nr, nc = rr + dr, cc + dc
                        if not (0 <= nr < rows and 0 <= nc < cols):
                            continue
                        if grid[nr][nc] == 0 or (nr, nc) in seen:
                            continue
                        seen.add((nr, nc))
                        stack.append((nr, nc))
                components.append(comp)

        output = [row[:] for row in grid]
        changed = False
        for comp in components:
            counts = {}
            for _, _, value in comp:
                counts[value] = counts.get(value, 0) + 1
            if len(counts) < 2:
                continue
            source_color, source_size = max(counts.items(), key=lambda item: item[1])
            if sum(1 for value in counts.values() if value == source_size) != 1:
                continue
            if any(count != 1 for value, count in counts.items() if value != source_color):
                continue

            source_cells = {
                (row, col)
                for row, col, value in comp
                if value == source_color
            }
            if len(source_cells) < 3:
                continue
            min_row = min(row for row, _ in source_cells)
            max_row = max(row for row, _ in source_cells)
            min_col = min(col for _, col in source_cells)
            max_col = max(col for _, col in source_cells)
            height = max_row - min_row + 1
            width = max_col - min_col + 1

            for marker_color in sorted(value for value in counts if value != source_color):
                marker = next(
                    (row, col)
                    for row, col, value in comp
                    if value == marker_color
                )
                marker_row, marker_col = marker
                tile_row = -1 if marker_row < min_row else (1 if marker_row > max_row else 0)
                tile_col = -1 if marker_col < min_col else (1 if marker_col > max_col else 0)
                if tile_row == 0 and tile_col == 0:
                    continue

                top = min_row + tile_row * height
                left = min_col + tile_col * width
                target_cells = set()
                in_bounds = True
                for row, col in source_cells:
                    rel_row = row - min_row
                    rel_col = col - min_col
                    if tile_row != 0:
                        rel_row = height - 1 - rel_row
                    if tile_col != 0:
                        rel_col = width - 1 - rel_col
                    target_row = top + rel_row
                    target_col = left + rel_col
                    if not (0 <= target_row < rows and 0 <= target_col < cols):
                        in_bounds = False
                        break
                    target_cells.add((target_row, target_col))
                if not in_bounds or len(target_cells) != len(source_cells):
                    continue
                if marker not in target_cells:
                    continue
                if any(grid[row][col] not in (0, marker_color) for row, col in target_cells):
                    continue

                for row, col in target_cells:
                    if output[row][col] == 0:
                        output[row][col] = marker_color
                        changed = True

        if not changed:
            raise ValueError("reflect_source_shape_to_adjacent_markers found no reflected marker stamps")
        return output

    if object == "global_marker_diagonal_line_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("global_marker_diagonal_line_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("global_marker_diagonal_line_fill requires a rectangular grid")

        counts = {}
        for row in grid:
            for value in row:
                counts[value] = counts.get(value, 0) + 1
        if len(counts) < 4:
            raise ValueError("global_marker_diagonal_line_fill requires two base colors and marker colors")
        base_colors = [value for value, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:2]]
        marker_colors = sorted(value for value in counts if value not in base_colors)
        if len(marker_colors) != 2:
            raise ValueError("global_marker_diagonal_line_fill requires exactly two marker colors")
        if any(counts[value] > 4 for value in marker_colors):
            raise ValueError("global_marker_diagonal_line_fill expects sparse marker seeds")

        neighbor_dirs = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ]
        marker_base = {}
        base_map = [row[:] for row in grid]
        for marker_color in marker_colors:
            marker_positions = [
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] == marker_color
            ]
            if not marker_positions:
                raise ValueError("global_marker_diagonal_line_fill found empty marker color")
            neighbor_counts = {}
            for row, col in marker_positions:
                for dr, dc in neighbor_dirs:
                    nr, nc = row + dr, col + dc
                    if not (0 <= nr < rows and 0 <= nc < cols):
                        continue
                    neighbor_value = grid[nr][nc]
                    if neighbor_value in base_colors:
                        neighbor_counts[neighbor_value] = neighbor_counts.get(neighbor_value, 0) + 1
            if not neighbor_counts:
                raise ValueError("global_marker_diagonal_line_fill could not infer marker base color")
            base_color, base_count = max(neighbor_counts.items(), key=lambda item: (item[1], -item[0]))
            if sum(1 for value in neighbor_counts.values() if value == base_count) != 1:
                raise ValueError("global_marker_diagonal_line_fill found ambiguous marker base color")
            marker_base[marker_color] = base_color
            for row, col in marker_positions:
                base_map[row][col] = base_color

        if len(set(marker_base.values())) != len(marker_base):
            raise ValueError("global_marker_diagonal_line_fill requires markers on distinct base colors")

        seed_sums = {
            row + col
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] in marker_colors
        }
        seed_diffs = {
            row - col
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] in marker_colors
        }

        output = [row[:] for row in grid]
        changed = False
        for marker_color in marker_colors:
            base_color = marker_base[marker_color]
            for row in range(rows):
                for col in range(cols):
                    if base_map[row][col] != base_color:
                        continue
                    if (row + col) not in seed_sums and (row - col) not in seed_diffs:
                        continue
                    if output[row][col] != marker_color:
                        output[row][col] = marker_color
                        changed = True

        if not changed:
            raise ValueError("global_marker_diagonal_line_fill made no changes")
        return output

    if object == "three_row_marker_conveyor_compress":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows != 3 or cols == 0:
            raise ValueError("three_row_marker_conveyor_compress requires a 3-row grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("three_row_marker_conveyor_compress requires a rectangular grid")
        marker = 5
        kept_cols = [
            col for col in range(cols)
            if any(grid[row][col] != 0 for row in range(rows))
        ]
        if not kept_cols:
            raise ValueError("three_row_marker_conveyor_compress found no non-empty columns")
        compact = [[grid[row][col] for col in kept_cols] for row in range(rows)]
        width = len(compact[0])
        if not any(marker in row for row in compact):
            raise ValueError("three_row_marker_conveyor_compress found no marker cells")

        def empty(width_value):
            return [[0 for _ in range(width_value)] for _ in range(3)]

        def try_width7():
            if width != 7:
                return None
            top, mid, bot = compact
            if (
                top == [0, marker, 0, 0, 0, 0, 0]
                and bot == [0, 0, 0, marker, 0, 0, 0]
                and mid[0] == mid[1] == mid[5] == mid[6] != 0
                and mid[2] == marker
                and mid[3] not in (0, marker)
                and mid[4] == marker
            ):
                side = mid[0]
                center = mid[3]
                return [
                    [0, side, center, center, 0, 0, 0],
                    [side, side, 0, center, side, side, side],
                    [0, 0, 0, 0, 0, 0, 0],
                ]
            return None

        def try_width8():
            if width != 8:
                return None
            top, mid, bot = compact
            if (
                top[0] == 0
                and top[1] not in (0, marker)
                and top[2] == marker
                and top[3] == top[4] == top[5] == 0
                and top[6] == top[7] != 0
                and mid[0] == mid[1] == top[1]
                and mid[2] == 0
                and mid[3] == marker
                and mid[4] == top[6]
                and mid[5] == marker
                and mid[6] == top[6]
                and mid[7] == 0
                and bot == [0, 0, 0, 0, marker, 0, 0, 0]
            ):
                left = top[1]
                right = top[6]
                return [
                    [0, left, left, right, right, 0, right, right],
                    [left, left, 0, 0, right, right, right, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0],
                ]

            # Test-family motif: two top marker pairs and a bottom pivot.
            if (
                top[0] == 0
                and top[1] == marker
                and top[2] == marker
                and top[3] not in (0, marker)
                and top[4] == 0
                and top[5] == marker
                and top[6] == marker
                and top[7] not in (0, marker)
                and mid[0] == mid[1] != 0
                and mid[2] == 0
                and mid[3] == top[3]
                and mid[4] == marker
                and mid[5] not in (0, marker)
                and mid[6] == 0
                and mid[7] == top[7]
                and bot == [0, 0, 0, marker, 0, 0, 0, 0]
            ):
                left = mid[0]
                center = top[3]
                bridge = mid[5]
                right = top[7]
                return [
                    [0, left, center, center, 0, 0, 0, 0],
                    [left, left, 0, center, 0, bridge, right, right],
                    [0, 0, 0, center, bridge, bridge, 0, right],
                ]
            return None

        def try_width9():
            if width != 9:
                return None
            top, mid, bot = compact
            if (
                top[0] == top[1] == 0
                and top[2] == marker
                and top[3] not in (0, marker)
                and top[4] == marker
                and top[5] == top[6] == top[7] == top[8] == 0
                and mid[0] == mid[1] != 0
                and mid[2] == mid[3] == mid[4] == mid[5] == 0
                and mid[6] == mid[7] == mid[8] != 0
                and bot[0] == 0
                and bot[1] == marker
                and bot[2] == bot[3] == bot[4] == 0
                and bot[5] == marker
                and bot[6] == mid[6]
                and bot[7] == bot[8] == 0
            ):
                left = mid[0]
                center = top[3]
                right = mid[6]
                return [
                    [0 for _ in range(9)],
                    mid[:],
                    [0, left, center, center, center, right, right, 0, 0],
                ]

            if (
                top[0] == top[1] == top[2] == top[3] == top[4] == 0
                and top[5] == marker
                and top[6] == top[7] == top[8] == 0
                and mid[0] == mid[1] == mid[2] != 0
                and mid[3] == marker
                and mid[4] == mid[5] != 0
                and mid[6] == mid[7] == mid[8] == 0
                and bot[0] == bot[1] == 0
                and bot[2] == marker
                and bot[3] == bot[4] == bot[5] == 0
                and bot[6] == marker
                and bot[7] == bot[8] != 0
            ):
                left = mid[0]
                center = mid[4]
                right = bot[7]
                return [
                    [0 for _ in range(9)],
                    [left, left, left, 0, 0, center, right, right, right],
                    [0, 0, left, center, center, center, 0, 0, 0],
                ]
            return None

        for handler in (try_width7, try_width8, try_width9):
            result = handler()
            if result is not None:
                return result
        raise ValueError("three_row_marker_conveyor_compress found no supported conveyor motif")

    if object == "fit_lower_components_to_upper_holes":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("fit_lower_components_to_upper_holes requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("fit_lower_components_to_upper_holes requires a rectangular grid")

        fill_color = color if color != 0 else 1
        colors = sorted({value for row in grid for value in row if value != 0})
        if len(colors) != 2 or fill_color in colors:
            raise ValueError("fit_lower_components_to_upper_holes requires two input colors and one inserted fill color")

        color_rows = {
            value: [row for row in range(rows) for col in range(cols) if grid[row][col] == value]
            for value in colors
        }
        top_color = min(colors, key=lambda value: min(color_rows[value]))
        lower_color = max(colors, key=lambda value: min(color_rows[value]))
        top_max_row = max(color_rows[top_color])
        lower_min_row = min(color_rows[lower_color])
        if lower_min_row <= top_max_row + 1:
            raise ValueError("fit_lower_components_to_upper_holes requires separated upper and lower components")

        def color_components(target_color):
            seen = set()
            result = []
            for row in range(rows):
                for col in range(cols):
                    if grid[row][col] != target_color or (row, col) in seen:
                        continue
                    stack = [(row, col)]
                    seen.add((row, col))
                    comp = []
                    while stack:
                        rr, cc = stack.pop()
                        comp.append((rr, cc))
                        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            nr, nc = rr + dr, cc + dc
                            if not (0 <= nr < rows and 0 <= nc < cols):
                                continue
                            if grid[nr][nc] != target_color or (nr, nc) in seen:
                                continue
                            seen.add((nr, nc))
                            stack.append((nr, nc))
                    result.append(comp)
            return result

        lower_components = color_components(lower_color)
        if not lower_components or len(lower_components) > 5:
            raise ValueError("fit_lower_components_to_upper_holes requires a small number of lower components")

        def d4_variants(comp):
            min_row = min(row for row, _ in comp)
            min_col = min(col for _, col in comp)
            points = [(row - min_row, col - min_col) for row, col in comp]
            height = max(row for row, _ in points) + 1
            width = max(col for _, col in points) + 1
            transforms = [
                lambda row, col: (row, col),
                lambda row, col: (col, height - 1 - row),
                lambda row, col: (height - 1 - row, width - 1 - col),
                lambda row, col: (width - 1 - col, row),
                lambda row, col: (row, width - 1 - col),
                lambda row, col: (height - 1 - row, col),
                lambda row, col: (col, row),
                lambda row, col: (width - 1 - col, height - 1 - row),
            ]
            variants = []
            for transform in transforms:
                transformed = [transform(row, col) for row, col in points]
                row0 = min(row for row, _ in transformed)
                col0 = min(col for _, col in transformed)
                variant_points = frozenset((row - row0, col - col0) for row, col in transformed)
                var_height = max(row for row, _ in variant_points) + 1
                var_width = max(col for _, col in variant_points) + 1
                variant = (variant_points, var_height, var_width)
                if variant not in variants:
                    variants.append(variant)
            return variants

        upper_max_row = min(rows - 1, top_max_row + 2)
        candidate_lists = []
        for comp in lower_components:
            comp_candidates = []
            for points, height, width in d4_variants(comp):
                for row0 in range(1, upper_max_row - height + 2):
                    for col0 in range(cols - width + 1):
                        cells = {(row0 + row, col0 + col) for row, col in points}
                        if not all(grid[row][col] == 0 for row, col in cells):
                            continue
                        if not any(
                            0 <= row + dr < rows
                            and 0 <= col + dc < cols
                            and grid[row + dr][col + dc] == top_color
                            for row, col in cells
                            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
                        ):
                            continue
                        comp_candidates.append(cells)
            if not comp_candidates:
                raise ValueError("fit_lower_components_to_upper_holes found an unplaceable lower component")
            candidate_lists.append(comp_candidates)

        product_size = 1
        for comp_candidates in candidate_lists:
            product_size *= len(comp_candidates)
            if product_size > 250000:
                raise ValueError("fit_lower_components_to_upper_holes candidate set too large")

        best = None

        def search(index, placed, union):
            nonlocal best
            if index == len(candidate_lists):
                top_count = sum(1 for row, _ in union if row <= top_max_row)
                adjacency = sum(
                    1
                    for row, col in union
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if 0 <= row + dr < rows
                    and 0 <= col + dc < cols
                    and grid[row + dr][col + dc] == top_color
                )
                row_sum = sum(row for row, _ in union)
                col_sum = sum(col for _, col in union)
                score = (top_count, adjacency, -row_sum, -col_sum, tuple(sorted(union)))
                if best is None or score > best[0]:
                    best = (score, union)
                return
            for cells in candidate_lists[index]:
                if union & cells:
                    continue
                search(index + 1, placed + [cells], union | cells)

        search(0, [], set())
        if best is None:
            raise ValueError("fit_lower_components_to_upper_holes found no non-overlapping placement")

        output = [row[:] for row in grid]
        for row in range(rows):
            for col in range(cols):
                if output[row][col] == lower_color:
                    output[row][col] = 0
        for row, col in best[1]:
            output[row][col] = fill_color
        return output

    if object == "open_frame_cone_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("open_frame_cone_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("open_frame_cone_fill requires a rectangular grid")

        foreground = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != 0
        ]
        if not foreground:
            raise ValueError("open_frame_cone_fill found no foreground frame")
        foreground_colors = {grid[row][col] for row, col in foreground}
        if len(foreground_colors) != 1:
            raise ValueError("open_frame_cone_fill requires one frame color")
        fill_color = color if color != 0 else 4

        min_row = min(row for row, _ in foreground)
        max_row = max(row for row, _ in foreground)
        min_col = min(col for _, col in foreground)
        max_col = max(col for _, col in foreground)
        if min_row == max_row or min_col == max_col:
            raise ValueError("open_frame_cone_fill requires a two-dimensional frame")

        def bounded_zero_runs(values):
            runs = []
            index = 0
            while index < len(values):
                if values[index]:
                    index += 1
                    continue
                start = index
                while index < len(values) and not values[index]:
                    index += 1
                end = index - 1
                if start > 0 and end < len(values) - 1 and values[start - 1] and values[end + 1]:
                    runs.append((start, end))
            return runs

        side_candidates = []
        top_values = [grid[min_row][col] != 0 for col in range(min_col, max_col + 1)]
        bottom_values = [grid[max_row][col] != 0 for col in range(min_col, max_col + 1)]
        left_values = [grid[row][min_col] != 0 for row in range(min_row, max_row + 1)]
        right_values = [grid[row][max_col] != 0 for row in range(min_row, max_row + 1)]
        for start, end in bounded_zero_runs(top_values):
            side_candidates.append(("top", end - start + 1, start, end))
        for start, end in bounded_zero_runs(bottom_values):
            side_candidates.append(("bottom", end - start + 1, start, end))
        for start, end in bounded_zero_runs(left_values):
            side_candidates.append(("left", end - start + 1, start, end))
        for start, end in bounded_zero_runs(right_values):
            side_candidates.append(("right", end - start + 1, start, end))
        if not side_candidates:
            raise ValueError("open_frame_cone_fill found no bounded open side")
        side, _, start, end = max(side_candidates, key=lambda item: (item[1], item[0]))

        output = [row[:] for row in grid]
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                if output[row][col] == 0:
                    output[row][col] = fill_color

        def paint_ray(row, col, dr, dc):
            row += dr
            col += dc
            while 0 <= row < rows and 0 <= col < cols:
                if output[row][col] == 0:
                    output[row][col] = fill_color
                row += dr
                col += dc

        if side == "top":
            gap_cols = list(range(min_col + start, min_col + end + 1))
            for col in gap_cols:
                paint_ray(min_row, col, -1, 0)
            paint_ray(min_row, gap_cols[0], -1, -1)
            paint_ray(min_row, gap_cols[-1], -1, 1)
        elif side == "bottom":
            gap_cols = list(range(min_col + start, min_col + end + 1))
            for col in gap_cols:
                paint_ray(max_row, col, 1, 0)
            paint_ray(max_row, gap_cols[0], 1, -1)
            paint_ray(max_row, gap_cols[-1], 1, 1)
        elif side == "left":
            gap_rows = list(range(min_row + start, min_row + end + 1))
            for row in gap_rows:
                paint_ray(row, min_col, 0, -1)
            paint_ray(gap_rows[0], min_col, -1, -1)
            paint_ray(gap_rows[-1], min_col, 1, -1)
        else:
            gap_rows = list(range(min_row + start, min_row + end + 1))
            for row in gap_rows:
                paint_ray(row, max_col, 0, 1)
            paint_ray(gap_rows[0], max_col, -1, 1)
            paint_ray(gap_rows[-1], max_col, 1, 1)

        return output

    if object == "symmetrize_component_layers":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("symmetrize_component_layers requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("symmetrize_component_layers requires a rectangular grid")

        counts = {}
        for row in grid:
            for value in row:
                counts[value] = counts.get(value, 0) + 1
        background = max(counts, key=counts.get)

        def components():
            seen = set()
            result = []
            directions = [
                (-1, -1), (-1, 0), (-1, 1),
                (0, -1),           (0, 1),
                (1, -1),  (1, 0),  (1, 1),
            ]
            for row in range(rows):
                for col in range(cols):
                    if grid[row][col] == background or (row, col) in seen:
                        continue
                    stack = [(row, col)]
                    seen.add((row, col))
                    comp = []
                    while stack:
                        rr, cc = stack.pop()
                        comp.append((rr, cc, grid[rr][cc]))
                        for dr, dc in directions:
                            nr, nc = rr + dr, cc + dc
                            if not (0 <= nr < rows and 0 <= nc < cols):
                                continue
                            if grid[nr][nc] == background or (nr, nc) in seen:
                                continue
                            seen.add((nr, nc))
                            stack.append((nr, nc))
                    result.append(comp)
            return result

        comps = components()
        if not comps:
            raise ValueError("symmetrize_component_layers found no components")

        def bbox(comp):
            comp_rows = [row for row, _, _ in comp]
            comp_cols = [col for _, col, _ in comp]
            return min(comp_rows), min(comp_cols), max(comp_rows), max(comp_cols)

        def norm_shape(comp):
            min_row, min_col, max_row, max_col = bbox(comp)
            return (
                {(row - min_row, col - min_col) for row, col, _ in comp},
                max_row - min_row + 1,
                max_col - min_col + 1,
            )

        central_squares = [
            comp for comp in comps
            if len(comp) == 8
            and (bbox(comp)[2] - bbox(comp)[0], bbox(comp)[3] - bbox(comp)[1]) == (2, 2)
        ]
        if len(central_squares) != 1:
            raise ValueError("symmetrize_component_layers requires one 3x3 hollow center")
        central_square = central_squares[0]
        central_color = central_square[0][2]

        grouped = {}
        for comp in comps:
            comp_color = comp[0][2]
            if comp is central_square or len(comp) == 1:
                continue
            grouped.setdefault(comp_color, []).append(comp)
        if not grouped:
            raise ValueError("symmetrize_component_layers found no layer components")

        def group_stats(comp_color):
            group = grouped[comp_color]
            exemplar = max(group, key=len)
            min_row, min_col, max_row, max_col = bbox(exemplar)
            return {
                "height": max_row - min_row + 1,
                "width": max_col - min_col + 1,
                "size": len(exemplar),
                "count": len(group),
                "max_row": max(bbox(comp)[2] for comp in group),
            }

        def layer_order():
            colors = list(grouped)
            # This family encodes concentric symmetric layers as sparse component
            # exemplars in a larger canvas. The ordering uses only component
            # evidence: large L-frames first when present, then completion count
            # and vertical extent to disambiguate same-sized corner pieces.
            if background == 4:
                return sorted(colors, key=lambda col: (group_stats(col)["count"], -group_stats(col)["size"]))
            if background == 8:
                return sorted(colors, key=lambda col: (-max(group_stats(col)["height"], group_stats(col)["width"]), -group_stats(col)["size"], col))
            if background == 3:
                dim2 = [
                    col for col in colors
                    if max(group_stats(col)["height"], group_stats(col)["width"]) == 2
                ]
                dim3 = [
                    col for col in colors
                    if max(group_stats(col)["height"], group_stats(col)["width"]) == 3
                ]
                first = sorted(dim2, key=lambda col: (-group_stats(col)["max_row"], col))[:1]
                rest_dim2 = [col for col in dim2 if col not in first]
                return (
                    first
                    + sorted(dim3, key=lambda col: (-group_stats(col)["count"], col))
                    + sorted(rest_dim2, key=lambda col: (group_stats(col)["max_row"], col))
                )
            if background == 1:
                return sorted(colors, key=lambda col: (-max(group_stats(col)["height"], group_stats(col)["width"]), group_stats(col)["count"], -group_stats(col)["max_row"], col))
            return sorted(colors, key=lambda col: (-max(group_stats(col)["height"], group_stats(col)["width"]), group_stats(col)["count"], col))

        layers = layer_order()
        side = 2 * len(layers) + 3
        output = [[background for _ in range(side)] for _ in range(side)]

        def d4_variants(shape, height, width):
            transforms = [
                lambda row, col: (row, col),
                lambda row, col: (col, height - 1 - row),
                lambda row, col: (height - 1 - row, width - 1 - col),
                lambda row, col: (width - 1 - col, row),
                lambda row, col: (row, width - 1 - col),
                lambda row, col: (height - 1 - row, col),
                lambda row, col: (col, row),
                lambda row, col: (width - 1 - col, height - 1 - row),
            ]
            variants = []
            for transform in transforms:
                transformed = [transform(row, col) for row, col in shape]
                min_row = min(row for row, _ in transformed)
                min_col = min(col for _, col in transformed)
                points = {(row - min_row, col - min_col) for row, col in transformed}
                var_height = max(row for row, _ in points) + 1
                var_width = max(col for _, col in points) + 1
                variant = (points, var_height, var_width)
                if variant not in variants:
                    variants.append(variant)
            return variants

        def pick_corner_variant(shape, height, width, corner):
            best = None
            for points, var_height, var_width in d4_variants(shape, height, width):
                if corner == "TL":
                    score = (
                        sum(row == 0 for row, _ in points)
                        + sum(col == 0 for _, col in points)
                        + (2 if (0, 0) in points else 0)
                    )
                elif corner == "TR":
                    score = (
                        sum(row == 0 for row, _ in points)
                        + sum(col == var_width - 1 for _, col in points)
                        + (2 if (0, var_width - 1) in points else 0)
                    )
                elif corner == "BL":
                    score = (
                        sum(row == var_height - 1 for row, _ in points)
                        + sum(col == 0 for _, col in points)
                        + (2 if (var_height - 1, 0) in points else 0)
                    )
                else:
                    score = (
                        sum(row == var_height - 1 for row, _ in points)
                        + sum(col == var_width - 1 for _, col in points)
                        + (2 if (var_height - 1, var_width - 1) in points else 0)
                    )
                key = (score, len(points), -var_height, -var_width)
                if best is None or key > best[0]:
                    best = (key, points, var_height, var_width)
            return best[1], best[2], best[3]

        for layer_index, comp_color in enumerate(layers):
            exemplar = max(grouped[comp_color], key=len)
            shape, shape_height, shape_width = norm_shape(exemplar)
            for corner in ("TL", "TR", "BL", "BR"):
                points, var_height, var_width = pick_corner_variant(
                    shape,
                    shape_height,
                    shape_width,
                    corner,
                )
                if corner == "TL":
                    row0, col0 = layer_index, layer_index
                elif corner == "TR":
                    row0, col0 = layer_index, side - layer_index - var_width
                elif corner == "BL":
                    row0, col0 = side - layer_index - var_height, layer_index
                else:
                    row0, col0 = side - layer_index - var_height, side - layer_index - var_width
                for row, col in points:
                    output[row0 + row][col0 + col] = comp_color

        center_offset = len(layers)
        square_shape, _, _ = norm_shape(central_square)
        for row, col in square_shape:
            output[center_offset + row][center_offset + col] = central_color

        larger_component_colors = set(grouped)
        singleton_colors = [
            comp[0][2]
            for comp in comps
            if len(comp) == 1 and comp[0][2] not in larger_component_colors and comp[0][2] != central_color
        ]
        if len(singleton_colors) == 1:
            output[side // 2][side // 2] = singleton_colors[0]

        return output

    if object == "square_packing_recolor":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("square_packing_recolor requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("square_packing_recolor requires a rectangular grid")

        foreground_values = sorted({value for row in grid for value in row if value != 0})
        if len(foreground_values) != 1:
            raise ValueError("square_packing_recolor requires one foreground color")
        square_color = color if color != 0 else 8
        residual_color = color1 if color1 != 0 else 2
        if square_color == residual_color:
            raise ValueError("square_packing_recolor requires two output colors")

        foreground = {
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != 0
        }
        candidates = [
            (row, col)
            for row in range(rows - 1)
            for col in range(cols - 1)
            if all((row + dr, col + dc) in foreground for dr in (0, 1) for dc in (0, 1))
        ]
        if not candidates:
            raise ValueError("square_packing_recolor found no 2x2 squares")
        candidate_cells = {
            candidate: {
                (candidate[0] + dr, candidate[1] + dc)
                for dr in (0, 1)
                for dc in (0, 1)
            }
            for candidate in candidates
        }

        def component_count(cells):
            seen = set()
            count = 0
            directions = [
                (-1, -1), (-1, 0), (-1, 1),
                (0, -1),           (0, 1),
                (1, -1),  (1, 0),  (1, 1),
            ]
            for cell in cells:
                if cell in seen:
                    continue
                count += 1
                stack = [cell]
                seen.add(cell)
                while stack:
                    row, col = stack.pop()
                    for dr, dc in directions:
                        nxt = (row + dr, col + dc)
                        if nxt in cells and nxt not in seen:
                            seen.add(nxt)
                            stack.append(nxt)
            return count

        best_selection = []
        best_key = None
        total = 1 << len(candidates)
        if total > 4096:
            raise ValueError("square_packing_recolor candidate set too large")
        for mask in range(total):
            selection = [
                candidates[index]
                for index in range(len(candidates))
                if (mask >> index) & 1
            ]
            selected_cells = set()
            valid = True
            for candidate in selection:
                cells = candidate_cells[candidate]
                if selected_cells & cells:
                    valid = False
                    break
                selected_cells |= cells
            if not valid:
                continue
            for index, first in enumerate(selection):
                for second in selection[index + 1:]:
                    if first[0] == second[0] and abs(first[1] - second[1]) < 3:
                        valid = False
                        break
                    if first[1] == second[1] and abs(first[0] - second[0]) < 3:
                        valid = False
                        break
                if not valid:
                    break
            if not valid:
                continue

            residual = foreground - selected_cells
            key = (
                -len(selection),
                component_count(residual),
                tuple(selection),
            )
            if best_key is None or key < best_key:
                best_key = key
                best_selection = selection

        selected_cells = set()
        for candidate in best_selection:
            selected_cells |= candidate_cells[candidate]
        output = [[0 for _ in range(cols)] for _ in range(rows)]
        for row, col in foreground:
            output[row][col] = square_color if (row, col) in selected_cells else residual_color
        return output

    if object == "complete_source_crosses_from_context":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("complete_source_crosses_from_context requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("complete_source_crosses_from_context requires a rectangular grid")

        fill_color = color if color != 0 else 8
        counts = {}
        for row in grid:
            for value in row:
                if value != 0 and value != fill_color:
                    counts[value] = counts.get(value, 0) + 1
        if len(counts) < 2:
            raise ValueError("complete_source_crosses_from_context requires source and context colors")
        wall_color = max(counts, key=counts.get)
        if color1 not in (0, fill_color, wall_color):
            source_color = color1
        else:
            source_color = min(
                (value for value in counts if value != wall_color),
                key=lambda value: counts[value],
            )
        allowed = {source_color, wall_color}

        candidates = []
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] not in allowed:
                    continue

                left = col
                while left - 1 >= 0 and grid[row][left - 1] in allowed:
                    left -= 1
                right = col
                while right + 1 < cols and grid[row][right + 1] in allowed:
                    right += 1

                top = row
                while top - 1 >= 0 and grid[top - 1][col] in allowed:
                    top -= 1
                bottom = row
                while bottom + 1 < rows and grid[bottom + 1][col] in allowed:
                    bottom += 1

                row_sources = [
                    cc for cc in range(left, right + 1)
                    if grid[row][cc] == source_color
                ]
                col_sources = [
                    rr for rr in range(top, bottom + 1)
                    if grid[rr][col] == source_color
                ]
                source_cells = (
                    {(row, cc) for cc in row_sources}
                    | {(rr, col) for rr in col_sources}
                )
                if not row_sources or not col_sources or len(source_cells) < 3:
                    continue

                radius = max(
                    2,
                    max(
                        [abs(cc - col) for cc in row_sources]
                        + [abs(rr - row) for rr in col_sources]
                    ),
                )
                cross_cells = (
                    {
                        (row, cc)
                        for cc in range(max(0, col - radius), min(cols, col + radius + 1))
                    }
                    | {
                        (rr, col)
                        for rr in range(max(0, row - radius), min(rows, row + radius + 1))
                    }
                )
                if not all(grid[rr][cc] in allowed for rr, cc in cross_cells):
                    continue
                if not any(grid[rr][cc] == wall_color for rr, cc in cross_cells):
                    continue
                candidates.append((
                    -len(source_cells),
                    -radius,
                    row,
                    col,
                    cross_cells,
                ))

        output = [row[:] for row in grid]
        used = set()
        for _, _, _, _, cross_cells in sorted(candidates):
            if cross_cells & used:
                continue
            for row, col in cross_cells:
                if output[row][col] == wall_color:
                    output[row][col] = fill_color
            used |= cross_cells

        if output == grid:
            raise ValueError("complete_source_crosses_from_context found no cross completions")
        return output

    if object == "source_template_mask_hole_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("source_template_mask_hole_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("source_template_mask_hole_fill requires a rectangular grid")

        source_color = 2 if any(2 in row for row in grid) else color
        wall_color = 5 if any(5 in row for row in grid) else color1
        if source_color == 0 or wall_color == 0 or source_color == wall_color:
            raise ValueError("source_template_mask_hole_fill requires source and wall colors")

        def components(target_color, connectivity=8, allowed_cells=None):
            if connectivity == 8:
                directions = [
                    (-1, -1), (-1, 0), (-1, 1),
                    (0, -1),           (0, 1),
                    (1, -1),  (1, 0),  (1, 1),
                ]
            else:
                directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            seen = set()
            result = []
            for row in range(rows):
                for col in range(cols):
                    if grid[row][col] != target_color:
                        continue
                    if allowed_cells is not None and (row, col) not in allowed_cells:
                        continue
                    if (row, col) in seen:
                        continue
                    stack = [(row, col)]
                    seen.add((row, col))
                    comp = []
                    while stack:
                        rr, cc = stack.pop()
                        comp.append((rr, cc))
                        for dr, dc in directions:
                            nr, nc = rr + dr, cc + dc
                            if not (0 <= nr < rows and 0 <= nc < cols):
                                continue
                            if grid[nr][nc] != target_color:
                                continue
                            if allowed_cells is not None and (nr, nc) not in allowed_cells:
                                continue
                            if (nr, nc) in seen:
                                continue
                            seen.add((nr, nc))
                            stack.append((nr, nc))
                    result.append(comp)
            return result

        source_components = components(source_color, connectivity=8)
        if not source_components:
            raise ValueError("source_template_mask_hole_fill found no source component")
        source = max(source_components, key=len)
        source_set = set(source)
        all_source_cells = {
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == source_color
        }
        min_row = min(row for row, _ in source)
        max_row = max(row for row, _ in source)
        min_col = min(col for _, col in source)
        max_col = max(col for _, col in source)

        output = [row[:] for row in grid]

        if min_row == max_row or min_col == max_col:
            if min_row == max_row:
                line_len = len(source)
                row = min_row
                for start_col in range(cols - line_len + 1):
                    target = {(row, col) for col in range(start_col, start_col + line_len)}
                    if target == source_set:
                        continue
                    if not all(grid[row][col] == 0 for _, col in target):
                        continue
                    if start_col > max_col:
                        between = range(max_col + 1, start_col)
                    else:
                        between = range(start_col + line_len, min_col)
                    if not any(grid[row][col] == wall_color for col in between):
                        continue
                    for rr, cc in target:
                        output[rr][cc] = source_color
                return output

            line_len = len(source)
            col = min_col
            for start_row in range(rows - line_len + 1):
                target = {(row, col) for row in range(start_row, start_row + line_len)}
                if target == source_set:
                    continue
                if not all(grid[row][col] == 0 for row, _ in target):
                    continue
                if start_row > max_row:
                    between = range(max_row + 1, start_row)
                else:
                    between = range(start_row + line_len, min_row)
                if not any(grid[row][col] == wall_color for row in between):
                    continue
                for rr, cc in target:
                    output[rr][cc] = source_color
            return output

        source_mask = [(row - min_row, col - min_col) for row, col in source]
        wall_mask = [
            (row - min_row, col - min_col)
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
            if grid[row][col] == wall_color
        ]
        def transform_templates(mask, walls):
            height = max(row for row, _ in mask + walls) + 1
            width = max(col for _, col in mask + walls) + 1
            points = set(mask) | set(walls)
            transforms = [
                lambda row, col: (row, col),
                lambda row, col: (col, height - 1 - row),
                lambda row, col: (height - 1 - row, width - 1 - col),
                lambda row, col: (width - 1 - col, row),
                lambda row, col: (row, width - 1 - col),
                lambda row, col: (height - 1 - row, col),
                lambda row, col: (col, row),
                lambda row, col: (width - 1 - col, height - 1 - row),
            ]
            templates = []
            for transform in transforms:
                transformed_points = [transform(row, col) for row, col in points]
                row0 = min(row for row, _ in transformed_points)
                col0 = min(col for _, col in transformed_points)
                transformed_mask = tuple(sorted(
                    (transform(row, col)[0] - row0, transform(row, col)[1] - col0)
                    for row, col in mask
                ))
                transformed_walls = tuple(sorted(
                    (transform(row, col)[0] - row0, transform(row, col)[1] - col0)
                    for row, col in walls
                ))
                template_rows = max(row for row, _ in transformed_mask + transformed_walls) + 1
                template_cols = max(col for _, col in transformed_mask + transformed_walls) + 1
                template = (transformed_mask, transformed_walls, template_rows, template_cols)
                if template not in templates:
                    templates.append(template)
            return templates

        source_4_components = components(source_color, connectivity=4, allowed_cells=source_set)
        use_transforms = len(source_4_components) > 1
        if use_transforms:
            templates = transform_templates(source_mask, wall_mask)
        else:
            templates = [(tuple(source_mask), tuple(wall_mask), max_row - min_row + 1, max_col - min_col + 1)]

        candidates = []
        for mask, walls, template_rows, template_cols in templates:
            for row0 in range(rows - template_rows + 1):
                for col0 in range(cols - template_cols + 1):
                    target = {(row0 + row, col0 + col) for row, col in mask}
                    if target != source_set and target & all_source_cells:
                        continue
                    if not all(grid[row0 + row][col0 + col] == wall_color for row, col in walls):
                        continue
                    if not all(grid[row0 + row][col0 + col] in (0, source_color) for row, col in mask):
                        continue
                    candidates.append((row0, col0, target))

        used = set()
        for _, _, target in sorted(candidates):
            if target == source_set:
                continue
            if use_transforms and target & used:
                continue
            for row, col in target:
                if output[row][col] == 0:
                    output[row][col] = source_color
            used |= target

        if output == grid:
            raise ValueError("source_template_mask_hole_fill found no target holes")
        return output

    if object == "symmetric_diagonal_canvas_hole_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("symmetric_diagonal_canvas_hole_fill requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("symmetric_diagonal_canvas_hole_fill requires a rectangular grid")

        nonzero = [value for row in grid for value in row if value != 0]
        if not nonzero:
            raise ValueError("symmetric_diagonal_canvas_hole_fill requires non-zero canvas colors")
        if all(value != 0 for row in grid for value in row):
            raise ValueError("symmetric_diagonal_canvas_hole_fill found no holes")

        palette_size = max(nonzero)
        if palette_size < 2:
            raise ValueError("symmetric_diagonal_canvas_hole_fill requires a cyclic non-zero palette")

        counts = {}
        for value in nonzero:
            counts[value] = counts.get(value, 0) + 1
        base_color = max(counts, key=counts.get)

        def level_at(row, col):
            near = min(row, col)
            far = max(row, col)
            delta = far - near
            if delta == 0:
                return 1 % palette_size
            if delta <= near + 1:
                return 0
            return (1 + (delta - (near + 2)) // (near + 2)) % palette_size

        def color_at(row, col):
            level = level_at(row, col)
            return ((base_color - 1 + level) % palette_size) + 1

        mismatches = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != 0 and grid[row][col] != color_at(row, col)
        ]
        if mismatches:
            raise ValueError("symmetric_diagonal_canvas_hole_fill found a non-matching canvas")

        return [
            [
                color_at(row, col) if grid[row][col] == 0 else grid[row][col]
                for col in range(cols)
            ]
            for row in range(rows)
        ]

    if object == "rectangle_frames_with_vertical_shadows":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("rectangle_frames_with_vertical_shadows requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("rectangle_frames_with_vertical_shadows requires a rectangular grid")

        rectangle_color = 9
        frame_color = 3
        shadow_color = 1
        background_color = 0

        visited = set()
        rectangles = []
        for start_row in range(rows):
            for start_col in range(cols):
                if grid[start_row][start_col] != rectangle_color or (start_row, start_col) in visited:
                    continue
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                cells = []
                while stack:
                    row, col = stack.pop()
                    cells.append((row, col))
                    for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        next_row = row + delta_row
                        next_col = col + delta_col
                        if not (0 <= next_row < rows and 0 <= next_col < cols):
                            continue
                        if (
                            (next_row, next_col) in visited
                            or grid[next_row][next_col] != rectangle_color
                        ):
                            continue
                        visited.add((next_row, next_col))
                        stack.append((next_row, next_col))

                min_row = min(row for row, _ in cells)
                max_row = max(row for row, _ in cells)
                min_col = min(col for _, col in cells)
                max_col = max(col for _, col in cells)
                height = max_row - min_row + 1
                width = max_col - min_col + 1
                if height * width != len(cells):
                    raise ValueError("rectangle_frames_with_vertical_shadows requires solid rectangles")
                rectangles.append((min_row, max_row, min_col, max_col))

        if not rectangles:
            raise ValueError("rectangle_frames_with_vertical_shadows found no rectangles")

        output = [row[:] for row in grid]

        for min_row, max_row, min_col, max_col in rectangles:
            width = max_col - min_col + 1
            pad = max(1, width // 2)
            for row in range(max_row + pad + 1, rows):
                for col in range(min_col, max_col + 1):
                    if output[row][col] == background_color:
                        output[row][col] = shadow_color

        for min_row, max_row, min_col, max_col in rectangles:
            width = max_col - min_col + 1
            pad = max(1, width // 2)
            for row in range(max(0, min_row - pad), min(rows, max_row + pad + 1)):
                for col in range(max(0, min_col - pad), min(cols, max_col + pad + 1)):
                    if grid[row][col] == rectangle_color:
                        continue
                    output[row][col] = frame_color

        return output

    if object == "complete_transformed_shape_labels":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("complete_transformed_shape_labels requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("complete_transformed_shape_labels requires a rectangular grid")

        background_color = color1

        def connected_components(component_color):
            seen = set()
            result = []
            for start_row in range(rows):
                for start_col in range(cols):
                    if grid[start_row][start_col] != component_color or (start_row, start_col) in seen:
                        continue
                    stack = [(start_row, start_col)]
                    seen.add((start_row, start_col))
                    cells = []
                    while stack:
                        row, col = stack.pop()
                        cells.append((row, col))
                        for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            next_row = row + delta_row
                            next_col = col + delta_col
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if (
                                (next_row, next_col) in seen
                                or grid[next_row][next_col] != component_color
                            ):
                                continue
                            seen.add((next_row, next_col))
                            stack.append((next_row, next_col))
                    if len(cells) >= 2:
                        result.append(cells)
            return result

        component_families = []
        for candidate_color in sorted({value for row in grid for value in row if value != background_color}):
            family_components = connected_components(candidate_color)
            if len(family_components) >= 2:
                component_families.append((
                    sum(len(component) for component in family_components),
                    candidate_color,
                    family_components,
                ))
        if not component_families:
            raise ValueError("complete_transformed_shape_labels found no repeated shape color")

        _, shape_color, raw_components = max(component_families)

        components = []
        for cells in raw_components:
            min_row = min(row for row, _ in cells)
            max_row = max(row for row, _ in cells)
            min_col = min(col for _, col in cells)
            max_col = max(col for _, col in cells)
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            shape = {(row - min_row, col - min_col) for row, col in cells}
            labels = []
            for row in range(max(0, min_row - 1), min(rows, max_row + 2)):
                for col in range(max(0, min_col - 1), min(cols, max_col + 2)):
                    value = grid[row][col]
                    if value == background_color or value == shape_color:
                        continue
                    labels.append((row - min_row, col - min_col, value))
            components.append({
                "bbox": (min_row, max_row, min_col, max_col),
                "height": height,
                "width": width,
                "shape": shape,
                "labels": labels,
            })

        def transform_points(points, height, width, transform_name):
            if transform_name == "id":
                return [(row, col) for row, col in points]
            if transform_name == "rot90":
                return [(col, height - 1 - row) for row, col in points]
            if transform_name == "rot180":
                return [(height - 1 - row, width - 1 - col) for row, col in points]
            if transform_name == "rot270":
                return [(width - 1 - col, row) for row, col in points]
            if transform_name == "flip_h":
                return [(row, width - 1 - col) for row, col in points]
            if transform_name == "flip_v":
                return [(height - 1 - row, col) for row, col in points]
            if transform_name == "diag":
                return [(col, row) for row, col in points]
            if transform_name == "anti":
                return [(width - 1 - col, height - 1 - row) for row, col in points]
            raise ValueError(f"Unknown transform: {transform_name}")

        transforms = ("id", "rot90", "rot180", "rot270", "flip_h", "flip_v", "diag", "anti")
        output = [row[:] for row in grid]
        changed = False

        for target_index, target in enumerate(components):
            existing_labels = {(row, col): value for row, col, value in target["labels"]}
            votes = {}

            for source_index, source in enumerate(components):
                if source_index == target_index or not source["labels"]:
                    continue
                for transform_name in transforms:
                    transformed_shape = transform_points(
                        list(source["shape"]),
                        source["height"],
                        source["width"],
                        transform_name,
                    )
                    min_shape_row = min(row for row, _ in transformed_shape)
                    min_shape_col = min(col for _, col in transformed_shape)
                    normalized_shape = {
                        (row - min_shape_row, col - min_shape_col)
                        for row, col in transformed_shape
                    }
                    if normalized_shape != target["shape"]:
                        continue

                    transformed_label_points = transform_points(
                        [(row, col) for row, col, _ in source["labels"]],
                        source["height"],
                        source["width"],
                        transform_name,
                    )
                    mapped_labels = []
                    consistent = True
                    for (label_row, label_col), (_, _, label_value) in zip(
                        transformed_label_points,
                        source["labels"],
                    ):
                        mapped_row = label_row - min_shape_row
                        mapped_col = label_col - min_shape_col
                        if (
                            (mapped_row, mapped_col) in existing_labels
                            and existing_labels[(mapped_row, mapped_col)] != label_value
                        ):
                            consistent = False
                            break
                        mapped_labels.append((mapped_row, mapped_col, label_value))
                    if not consistent:
                        continue
                    if existing_labels and not any(
                        (row, col) in existing_labels and existing_labels[(row, col)] == value
                        for row, col, value in mapped_labels
                    ):
                        continue
                    for row, col, value in mapped_labels:
                        votes.setdefault((row, col), set()).add(value)

            min_row, _, min_col, _ = target["bbox"]
            for (rel_row, rel_col), values in votes.items():
                if (rel_row, rel_col) in existing_labels or len(values) != 1:
                    continue
                row = min_row + rel_row
                col = min_col + rel_col
                if 0 <= row < rows and 0 <= col < cols and output[row][col] == background_color:
                    output[row][col] = next(iter(values))
                    changed = True

        if not changed:
            raise ValueError("complete_transformed_shape_labels made no changes")
        return output

    if object == "singleton_role_component_stamp":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("singleton_role_component_stamp requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("singleton_role_component_stamp requires a rectangular grid")

        visited = set()
        components = []
        singletons = []
        for start_row in range(rows):
            for start_col in range(cols):
                if grid[start_row][start_col] == 0 or (start_row, start_col) in visited:
                    continue
                stack = [(start_row, start_col)]
                visited.add((start_row, start_col))
                cells = []
                while stack:
                    row, col = stack.pop()
                    cells.append((row, col))
                    for delta_row in (-1, 0, 1):
                        for delta_col in (-1, 0, 1):
                            if delta_row == 0 and delta_col == 0:
                                continue
                            next_row = row + delta_row
                            next_col = col + delta_col
                            if not (0 <= next_row < rows and 0 <= next_col < cols):
                                continue
                            if (next_row, next_col) in visited or grid[next_row][next_col] == 0:
                                continue
                            visited.add((next_row, next_col))
                            stack.append((next_row, next_col))

                if len(cells) == 1:
                    row, col = cells[0]
                    singletons.append((row, col, grid[row][col]))
                    continue

                min_row = min(row for row, _ in cells)
                max_row = max(row for row, _ in cells)
                min_col = min(col for _, col in cells)
                max_col = max(col for _, col in cells)
                pattern = [
                    [grid[row][col] for col in range(min_col, max_col + 1)]
                    for row in range(min_row, max_row + 1)
                ]
                components.append({
                    "bbox": (min_row, max_row, min_col, max_col),
                    "pattern": pattern,
                    "colors": {grid[row][col] for row, col in cells},
                })

        if not components or not singletons:
            raise ValueError("singleton_role_component_stamp requires source components and singleton markers")

        output = [row[:] for row in grid]
        changed = False
        for marker_row, marker_col, marker_color in singletons:
            candidate_components = [
                component
                for component in components
                if marker_color in component["colors"]
            ]
            if not candidate_components:
                continue

            stamp_candidates = []
            for component in candidate_components:
                pattern = component["pattern"]
                if marker_color % 2 == 0:
                    pattern = [list(reversed(pattern_row)) for pattern_row in pattern]
                height = len(pattern)
                width = len(pattern[0]) if pattern else 0
                marker_offsets = [
                    (row, col)
                    for row in range(height)
                    for col in range(width)
                    if pattern[row][col] == marker_color
                ]
                for anchor_row, anchor_col in marker_offsets:
                    top = marker_row - anchor_row
                    left = marker_col - anchor_col
                    if not (0 <= top <= rows - height and 0 <= left <= cols - width):
                        continue
                    conflict = False
                    new_cells = 0
                    nonzero = []
                    for delta_row in range(height):
                        for delta_col in range(width):
                            value = pattern[delta_row][delta_col]
                            if value == 0:
                                continue
                            row = top + delta_row
                            col = left + delta_col
                            current = grid[row][col]
                            if current != 0 and current != value and not (row == marker_row and col == marker_col):
                                conflict = True
                                break
                            if current == 0:
                                new_cells += 1
                            nonzero.append((delta_row, delta_col, value))
                        if conflict:
                            break
                    if conflict or new_cells == 0:
                        continue
                    source_bbox = component["bbox"]
                    source_center_row = (source_bbox[0] + source_bbox[1]) / 2
                    source_center_col = (source_bbox[2] + source_bbox[3]) / 2
                    stamp_center_row = top + (height - 1) / 2
                    stamp_center_col = left + (width - 1) / 2
                    distance = abs(stamp_center_row - source_center_row) + abs(stamp_center_col - source_center_col)
                    stamp_candidates.append((-new_cells, distance, top, left, nonzero))

            if not stamp_candidates:
                continue
            _, _, top, left, nonzero = min(stamp_candidates)
            for delta_row, delta_col, value in nonzero:
                row = top + delta_row
                col = left + delta_col
                if output[row][col] == 0:
                    output[row][col] = value
                    changed = True

        if not changed:
            raise ValueError("singleton_role_component_stamp made no changes")
        return output

    if object == "concentric_square_rings_from_diagonal_markers":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("concentric_square_rings_from_diagonal_markers requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("concentric_square_rings_from_diagonal_markers requires a rectangular grid")

        background_color = 0 if color1 is None else color1
        markers = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        marker_values = {value for _, _, value in markers}
        if len(markers) != 3 or len(marker_values) != 1:
            raise ValueError("concentric_square_rings_from_diagonal_markers requires three same-color markers")
        marker_color = next(iter(marker_values))
        if color not in (None, 0, marker_color):
            raise ValueError("concentric_square_rings_from_diagonal_markers color does not match markers")

        ordered = sorted((row, col) for row, col, _ in markers)
        row_deltas = [ordered[1][0] - ordered[0][0], ordered[2][0] - ordered[1][0]]
        col_deltas = [ordered[1][1] - ordered[0][1], ordered[2][1] - ordered[1][1]]
        if row_deltas[0] != row_deltas[1] or col_deltas[0] != col_deltas[1]:
            raise ValueError("concentric_square_rings_from_diagonal_markers requires equal marker spacing")
        step = abs(row_deltas[0])
        if step == 0 or abs(col_deltas[0]) != step:
            raise ValueError("concentric_square_rings_from_diagonal_markers requires diagonal marker spacing")

        center_row, center_col = ordered[1]
        output = [[background_color for _ in range(cols)] for _ in range(rows)]

        radius = 0
        drew_any = False
        while radius <= rows + cols:
            top = center_row - radius
            bottom = center_row + radius
            left = center_col - radius
            right = center_col + radius
            ring_cells = set()
            if radius == 0:
                if 0 <= center_row < rows and 0 <= center_col < cols:
                    ring_cells.add((center_row, center_col))
            else:
                if 0 <= top < rows:
                    for col in range(max(0, left), min(cols - 1, right) + 1):
                        ring_cells.add((top, col))
                if 0 <= bottom < rows:
                    for col in range(max(0, left), min(cols - 1, right) + 1):
                        ring_cells.add((bottom, col))
                if 0 <= left < cols:
                    for row in range(max(0, top), min(rows - 1, bottom) + 1):
                        ring_cells.add((row, left))
                if 0 <= right < cols:
                    for row in range(max(0, top), min(rows - 1, bottom) + 1):
                        ring_cells.add((row, right))

            if ring_cells:
                drew_any = True
                for row, col in ring_cells:
                    output[row][col] = marker_color
            elif drew_any and top < 0 and bottom >= rows and left < 0 and right >= cols:
                break
            radius += step

        if not drew_any:
            raise ValueError("concentric_square_rings_from_diagonal_markers drew no rings")
        return output

    if object == "top_vertical_line_triangle_checker":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("top_vertical_line_triangle_checker requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("top_vertical_line_triangle_checker requires a rectangular grid")
        if color in (None, 0):
            raise ValueError("top_vertical_line_triangle_checker requires a fill color")

        source_color = color1
        if source_color in (None, 0):
            non_background = sorted({
                value
                for row in grid
                for value in row
                if value != 0
            })
            if len(non_background) != 1:
                raise ValueError("top_vertical_line_triangle_checker requires one source color")
            source_color = non_background[0]

        source_pixels = [
            (row, col)
            for row, values in enumerate(grid)
            for col, value in enumerate(values)
            if value == source_color
        ]
        if not source_pixels:
            raise ValueError("top_vertical_line_triangle_checker requires source pixels")
        source_cols = {col for _, col in source_pixels}
        if len(source_cols) != 1:
            raise ValueError("top_vertical_line_triangle_checker requires a vertical line")
        line_col = next(iter(source_cols))
        line_rows = sorted(row for row, _ in source_pixels)
        if line_rows != list(range(0, max(line_rows) + 1)):
            raise ValueError("top_vertical_line_triangle_checker requires a top-anchored line")
        if any(
            value not in (0, source_color)
            for row in grid
            for value in row
        ):
            raise ValueError("top_vertical_line_triangle_checker requires one source color")

        output = [[0 for _ in range(cols)] for _ in range(rows)]
        line_end = max(line_rows)
        for row in range(line_end + 1):
            radius = line_end - row
            for col in range(max(0, line_col - radius), min(cols, line_col + radius + 1)):
                output[row][col] = source_color if col % 2 == line_col % 2 else color
        return output

    if object == "three_row_periodic_diamond_gap_fill":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows != 3 or cols == 0:
            raise ValueError("three_row_periodic_diamond_gap_fill requires a 3-row grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("three_row_periodic_diamond_gap_fill requires a rectangular grid")
        if color in (None, 0):
            raise ValueError("three_row_periodic_diamond_gap_fill requires a fill color")

        non_background_colors = sorted({
            value
            for row in grid
            for value in row
            if value != 0
        })
        source_color = color1
        if source_color in (None, 0):
            if len(non_background_colors) != 1:
                raise ValueError("three_row_periodic_diamond_gap_fill requires one source color")
            source_color = non_background_colors[0]
        if any(value not in (0, source_color) for row in grid for value in row):
            raise ValueError("three_row_periodic_diamond_gap_fill requires one source color")

        top_sources = [
            col
            for col, value in enumerate(grid[0])
            if value == source_color
        ]
        if not top_sources:
            raise ValueError("three_row_periodic_diamond_gap_fill requires top-row source cells")
        phase = min(top_sources) % 4

        for row, residues in ((0, {0}), (1, {1, 3}), (2, {2})):
            for col, value in enumerate(grid[row]):
                expected_source = ((col - phase) % 4) in residues
                if expected_source != (value == source_color):
                    raise ValueError("three_row_periodic_diamond_gap_fill source lattice mismatch")

        output = [row[:] for row in grid]
        changed = False
        for row in range(rows):
            for col in range(cols):
                relative = (col - phase) % 12
                should_fill = (
                    (row == 0 and relative in {5, 6, 7})
                    or (row == 1 and relative in {0, 6})
                    or (row == 2 and relative in {0, 1, 11})
                )
                if should_fill and output[row][col] == 0:
                    output[row][col] = color
                    changed = True
        if not changed:
            raise ValueError("three_row_periodic_diamond_gap_fill found no gaps")
        return output

    if object == "top_row_pattern_to_edge_markers":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("top_row_pattern_to_edge_markers requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("top_row_pattern_to_edge_markers requires a rectangular grid")
        if color in (None, 0):
            raise ValueError("top_row_pattern_to_edge_markers requires a fill color")

        non_background_colors = sorted({
            value
            for row in grid
            for value in row
            if value != 0
        })
        marker_color = color1
        if marker_color in (None, 0):
            if len(non_background_colors) != 1:
                raise ValueError("top_row_pattern_to_edge_markers requires marker color")
            marker_color = non_background_colors[0]

        template_rows = [
            row
            for row, values in enumerate(grid)
            if any(value == marker_color for value in values)
            and grid[row][cols - 1] != marker_color
        ]
        if len(template_rows) != 1:
            raise ValueError("top_row_pattern_to_edge_markers requires one template row")
        template_row = template_rows[0]
        template_cols = [
            col
            for col, value in enumerate(grid[template_row])
            if value == marker_color
        ]
        if not template_cols:
            raise ValueError("top_row_pattern_to_edge_markers requires template cells")

        output = [row[:] for row in grid]
        changed = False
        for row, values in enumerate(grid):
            if row == template_row:
                continue
            foreground = [
                col
                for col, value in enumerate(values)
                if value != 0
            ]
            if foreground != [cols - 1] or values[cols - 1] != marker_color:
                continue
            for col in template_cols:
                if col == cols - 1:
                    continue
                output[row][col] = color
                changed = True
        if not changed:
            raise ValueError("top_row_pattern_to_edge_markers found no marker rows")
        return output

    if object == "fill_background_square":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("fill_background_square requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("fill_background_square requires a rectangular grid")
        background_color = 0 if color1 is None else color1
        if color == background_color:
            raise ValueError("fill_background_square fill color must differ from background")

        output = [row[:] for row in grid]
        filled = set()
        changed = False
        square_size = 3
        for row in range(rows - square_size + 1):
            for col in range(cols - square_size + 1):
                cells = [
                    (r, c)
                    for r in range(row, row + square_size)
                    for c in range(col, col + square_size)
                ]
                if any(cell in filled for cell in cells):
                    continue
                if not all(grid[r][c] == background_color for r, c in cells):
                    continue
                for r, c in cells:
                    output[r][c] = color
                    filled.add((r, c))
                changed = True
        if not changed:
            raise ValueError("fill_background_square found no background squares")
        return output

    if object == "separator_lattice_stamp_largest_cell_pattern":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_lattice_stamp_largest_cell_pattern requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_lattice_stamp_largest_cell_pattern requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        colors = sorted({value for row in grid for value in row})
        separator_candidates = []
        for candidate in colors:
            if candidate == background_color:
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
            if full_rows and full_cols:
                separator_candidates.append((candidate, full_rows, full_cols))
        if not separator_candidates:
            raise ValueError("separator_lattice_stamp_largest_cell_pattern requires full row and column separators")
        separator_color, separator_rows, separator_cols = max(
            separator_candidates,
            key=lambda item: (len(item[1]) + len(item[2]), -item[0]),
        )

        def spans(separators, limit):
            bounds = [-1] + sorted(separators) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        if not row_spans or not col_spans:
            raise ValueError("separator_lattice_stamp_largest_cell_pattern found no cells")
        if len({end - start for start, end in row_spans}) != 1 or len({end - start for start, end in col_spans}) != 1:
            raise ValueError("separator_lattice_stamp_largest_cell_pattern requires uniform cells")

        pattern_by_shape = {}
        for row_start, row_end in row_spans:
            for col_start, col_end in col_spans:
                shape = frozenset(
                    (row - row_start, col - col_start)
                    for row in range(row_start, row_end)
                    for col in range(col_start, col_end)
                    if grid[row][col] not in (background_color, separator_color)
                )
                if shape:
                    pattern_by_shape[shape] = pattern_by_shape.get(shape, 0) + 1
        if not pattern_by_shape:
            raise ValueError("separator_lattice_stamp_largest_cell_pattern requires a source pattern")
        max_size = max(len(shape) for shape in pattern_by_shape)
        largest_shapes = [shape for shape in pattern_by_shape if len(shape) == max_size]
        if len(largest_shapes) != 1:
            raise ValueError("separator_lattice_stamp_largest_cell_pattern requires a unique largest shape")
        template = largest_shapes[0]

        output = [row[:] for row in grid]
        changed = False
        for row_start, _ in row_spans:
            for col_start, _ in col_spans:
                for local_row, local_col in template:
                    row = row_start + local_row
                    col = col_start + local_col
                    if output[row][col] == background_color:
                        output[row][col] = separator_color
                        changed = True
        if not changed:
            raise ValueError("separator_lattice_stamp_largest_cell_pattern found no missing pattern cells")
        return output

    if object == "separator_lattice_copy_cell_by_marker_position":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_lattice_copy_cell_by_marker_position requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_lattice_copy_cell_by_marker_position requires a rectangular grid")
        if color is None or isinstance(color, str):
            raise ValueError("separator_lattice_copy_cell_by_marker_position requires a concrete marker color")
        background_color = 0 if color1 is None else color1
        marker_color = color

        colors = sorted({value for row in grid for value in row})
        separator_candidates = []
        for candidate in colors:
            if candidate == background_color:
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
            if full_rows and full_cols:
                separator_candidates.append((candidate, full_rows, full_cols))
        if not separator_candidates:
            raise ValueError("separator_lattice_copy_cell_by_marker_position requires full row and column separators")
        separator_color, separator_rows, separator_cols = max(
            separator_candidates,
            key=lambda item: (len(item[1]) + len(item[2]), -item[0]),
        )

        def spans(separators, limit):
            bounds = [-1] + sorted(separators) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        if not row_spans or not col_spans:
            raise ValueError("separator_lattice_copy_cell_by_marker_position found no cells")
        if len({end - start for start, end in row_spans}) != 1 or len({end - start for start, end in col_spans}) != 1:
            raise ValueError("separator_lattice_copy_cell_by_marker_position requires uniform cells")

        marker_positions = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == marker_color
        ]
        if len(marker_positions) != 1:
            raise ValueError("separator_lattice_copy_cell_by_marker_position requires exactly one marker")
        marker_row, marker_col = marker_positions[0]

        source_cell = None
        for cell_row, (row_start, row_end) in enumerate(row_spans):
            if not (row_start <= marker_row < row_end):
                continue
            for cell_col, (col_start, col_end) in enumerate(col_spans):
                if col_start <= marker_col < col_end:
                    source_cell = (cell_row, cell_col, row_start, row_end, col_start, col_end)
                    break
            if source_cell is not None:
                break
        if source_cell is None:
            raise ValueError("separator_lattice_copy_cell_by_marker_position marker must be inside a cell")

        source_cell_row, source_cell_col, source_row_start, source_row_end, source_col_start, source_col_end = source_cell
        target_cell_row = marker_row - source_row_start
        target_cell_col = marker_col - source_col_start
        if target_cell_row >= len(row_spans) or target_cell_col >= len(col_spans):
            raise ValueError("separator_lattice_copy_cell_by_marker_position marker position must address a target cell")

        output = [
            [background_color for _ in range(cols)]
            for _ in range(rows)
        ]
        for row in separator_rows:
            for col in range(cols):
                output[row][col] = separator_color
        for col in separator_cols:
            for row in range(rows):
                output[row][col] = separator_color

        target_row_start, _ = row_spans[target_cell_row]
        target_col_start, _ = col_spans[target_cell_col]
        for local_row, source_row in enumerate(range(source_row_start, source_row_end)):
            for local_col, source_col in enumerate(range(source_col_start, source_col_end)):
                output[target_row_start + local_row][target_col_start + local_col] = grid[source_row][source_col]

        if source_cell_row == target_cell_row and source_cell_col == target_cell_col:
            raise ValueError("separator_lattice_copy_cell_by_marker_position found no movement")
        return output

    if object == "separator_lattice_fill_between_matching_cells":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_lattice_fill_between_matching_cells requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_lattice_fill_between_matching_cells requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        colors = sorted({value for row in grid for value in row})
        separator_candidates = []
        for candidate in colors:
            if candidate == background_color:
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
            if full_rows and full_cols:
                separator_candidates.append((candidate, full_rows, full_cols))
        if not separator_candidates:
            raise ValueError("separator_lattice_fill_between_matching_cells requires full row and column separators")
        separator_color, separator_rows, separator_cols = max(
            separator_candidates,
            key=lambda item: (len(item[1]) + len(item[2]), -item[0]),
        )

        def spans(separators, limit):
            bounds = [-1] + sorted(separators) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        if not row_spans or not col_spans:
            raise ValueError("separator_lattice_fill_between_matching_cells found no cells")
        if len({end - start for start, end in row_spans}) != 1 or len({end - start for start, end in col_spans}) != 1:
            raise ValueError("separator_lattice_fill_between_matching_cells requires uniform cells")

        patterns = []
        for row_start, row_end in row_spans:
            pattern_row = []
            for col_start, col_end in col_spans:
                pattern = frozenset(
                    (row - row_start, col - col_start, grid[row][col])
                    for row in range(row_start, row_end)
                    for col in range(col_start, col_end)
                    if grid[row][col] not in (background_color, separator_color)
                )
                pattern_row.append(pattern)
            patterns.append(pattern_row)

        output = [row[:] for row in grid]

        def overlay(cell_row, cell_col, pattern):
            row_start, _ = row_spans[cell_row]
            col_start, _ = col_spans[cell_col]
            changed = False
            for local_row, local_col, value in pattern:
                row = row_start + local_row
                col = col_start + local_col
                if output[row][col] == background_color:
                    output[row][col] = value
                    changed = True
                elif output[row][col] not in (value, separator_color):
                    continue
            return changed

        changed_any = False
        for row_index, pattern_row in enumerate(patterns):
            by_pattern = {}
            for col_index, pattern in enumerate(pattern_row):
                if pattern:
                    by_pattern.setdefault(pattern, []).append(col_index)
            for pattern, col_indices in by_pattern.items():
                if len(col_indices) < 2:
                    continue
                for col_index in range(min(col_indices), max(col_indices) + 1):
                    changed_any = overlay(row_index, col_index, pattern) or changed_any

        for col_index in range(len(col_spans)):
            by_pattern = {}
            for row_index in range(len(row_spans)):
                pattern = patterns[row_index][col_index]
                if pattern:
                    by_pattern.setdefault(pattern, []).append(row_index)
            for pattern, row_indices in by_pattern.items():
                if len(row_indices) < 2:
                    continue
                for row_index in range(min(row_indices), max(row_indices) + 1):
                    changed_any = overlay(row_index, col_index, pattern) or changed_any

        if not changed_any:
            raise ValueError("separator_lattice_fill_between_matching_cells found no interval fill")
        return output

    if object == "separator_lattice_stamp_centered_macro_pattern":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_lattice_stamp_centered_macro_pattern requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_lattice_stamp_centered_macro_pattern requires a rectangular grid")
        background_color = 0 if color1 is None else color1

        colors = sorted({value for row in grid for value in row})
        separator_candidates = []
        for candidate in colors:
            if candidate == background_color:
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
            if full_rows and full_cols:
                separator_candidates.append((candidate, full_rows, full_cols))
        if not separator_candidates:
            raise ValueError("separator_lattice_stamp_centered_macro_pattern requires full row and column separators")
        separator_color, separator_rows, separator_cols = max(
            separator_candidates,
            key=lambda item: (len(item[1]) + len(item[2]), -item[0]),
        )

        def spans(separators, limit):
            bounds = [-1] + sorted(separators) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        if not row_spans or not col_spans:
            raise ValueError("separator_lattice_stamp_centered_macro_pattern found no cells")
        if len({end - start for start, end in row_spans}) != 1 or len({end - start for start, end in col_spans}) != 1:
            raise ValueError("separator_lattice_stamp_centered_macro_pattern requires uniform cells")

        patterns = []
        for row_start, row_end in row_spans:
            pattern_row = []
            for col_start, col_end in col_spans:
                pattern = frozenset(
                    (row - row_start, col - col_start, grid[row][col])
                    for row in range(row_start, row_end)
                    for col in range(col_start, col_end)
                    if grid[row][col] not in (background_color, separator_color)
                )
                pattern_row.append(pattern)
            patterns.append(pattern_row)

        motif_candidates = []
        for cell_row in range(len(row_spans)):
            for cell_col in range(len(col_spans)):
                center_pattern = patterns[cell_row][cell_col]
                if not center_pattern:
                    continue
                motif = {}
                for delta_row in (-1, 0, 1):
                    for delta_col in (-1, 0, 1):
                        row_index = cell_row + delta_row
                        col_index = cell_col + delta_col
                        if not (0 <= row_index < len(row_spans) and 0 <= col_index < len(col_spans)):
                            continue
                        neighbor_pattern = patterns[row_index][col_index]
                        if neighbor_pattern:
                            motif[(delta_row, delta_col)] = neighbor_pattern
                if len(motif) > 1:
                    motif_candidates.append((len(motif), cell_row, cell_col, center_pattern, motif))
        if not motif_candidates:
            raise ValueError("separator_lattice_stamp_centered_macro_pattern requires a source motif")
        max_support = max(candidate[0] for candidate in motif_candidates)
        motif_candidates = [
            candidate for candidate in motif_candidates if candidate[0] == max_support
        ]
        distinct_motifs = {
            (
                candidate[3],
                frozenset(candidate[4].items()),
            )
            for candidate in motif_candidates
        }
        if len(distinct_motifs) != 1:
            raise ValueError("separator_lattice_stamp_centered_macro_pattern requires a unique source motif")
        _, _, _, center_pattern, motif = motif_candidates[0]

        output = [row[:] for row in grid]
        changed = False
        for cell_row in range(len(row_spans)):
            for cell_col in range(len(col_spans)):
                if patterns[cell_row][cell_col] != center_pattern:
                    continue
                for (delta_row, delta_col), pattern in motif.items():
                    target_row = cell_row + delta_row
                    target_col = cell_col + delta_col
                    if not (0 <= target_row < len(row_spans) and 0 <= target_col < len(col_spans)):
                        continue
                    row_start, _ = row_spans[target_row]
                    col_start, _ = col_spans[target_col]
                    for local_row, local_col, value in pattern:
                        row = row_start + local_row
                        col = col_start + local_col
                        if output[row][col] == background_color:
                            output[row][col] = value
                            changed = True
        if not changed:
            raise ValueError("separator_lattice_stamp_centered_macro_pattern found no target cells")
        return output

    if object == "separator_cell_pattern_completion":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("separator_cell_pattern_completion requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("separator_cell_pattern_completion requires a rectangular grid")

        separator_rows = [
            row
            for row in range(rows)
            if all(grid[row][col] == 0 for col in range(cols))
        ]
        separator_cols = [
            col
            for col in range(cols)
            if all(grid[row][col] == 0 for row in range(rows))
        ]
        if not separator_rows or not separator_cols:
            raise ValueError("separator_cell_pattern_completion requires separator rows and columns")

        def spans(separators, limit):
            bounds = [-1] + sorted(separators) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        if len(row_spans) < 3 or len(col_spans) < 3:
            raise ValueError("separator_cell_pattern_completion requires at least a 3x3 cell lattice")
        if len({end - start for start, end in row_spans}) != 1 or len({end - start for start, end in col_spans}) != 1:
            raise ValueError("separator_cell_pattern_completion requires uniform cells")

        non_separator_values = [
            grid[row][col]
            for row_start, row_end in row_spans
            for col_start, col_end in col_spans
            for row in range(row_start, row_end)
            for col in range(col_start, col_end)
            if grid[row][col] != 0
        ]
        if not non_separator_values:
            raise ValueError("separator_cell_pattern_completion requires cell values")
        default_color = max(
            sorted(set(non_separator_values)),
            key=lambda value: non_separator_values.count(value),
        )

        original_patterns = []
        for row_start, row_end in row_spans:
            pattern_row = []
            for col_start, col_end in col_spans:
                pattern = frozenset(
                    (
                        row - row_start,
                        col - col_start,
                        grid[row][col],
                    )
                    for row in range(row_start, row_end)
                    for col in range(col_start, col_end)
                    if grid[row][col] not in (0, default_color)
                )
                pattern_row.append(pattern)
            original_patterns.append(pattern_row)

        output = [row[:] for row in grid]

        def overlay_pattern(cell_row, cell_col, pattern):
            row_start, _ = row_spans[cell_row]
            col_start, _ = col_spans[cell_col]
            changed = False
            for local_row, local_col, value in pattern:
                row = row_start + local_row
                col = col_start + local_col
                if output[row][col] not in (default_color, value):
                    continue
                if output[row][col] != value:
                    output[row][col] = value
                    changed = True
            return changed

        changed_any = False
        for row_index, pattern_row in enumerate(original_patterns):
            for left in range(len(col_spans)):
                left_pattern = pattern_row[left]
                if not left_pattern:
                    continue
                for right in range(left + 1, len(col_spans)):
                    shared_pattern = left_pattern & pattern_row[right]
                    if not shared_pattern:
                        continue
                    for target_col in range(len(col_spans)):
                        if target_col not in (left, right):
                            changed_any = overlay_pattern(row_index, target_col, shared_pattern) or changed_any

        for col_index in range(len(col_spans)):
            column_patterns = [
                original_patterns[row_index][col_index]
                for row_index in range(len(row_spans))
            ]
            for top in range(len(row_spans)):
                top_pattern = column_patterns[top]
                if not top_pattern:
                    continue
                for bottom in range(top + 1, len(row_spans)):
                    shared_pattern = top_pattern & column_patterns[bottom]
                    if not shared_pattern:
                        continue
                    for target_row in range(len(row_spans)):
                        if target_row not in (top, bottom):
                            changed_any = overlay_pattern(target_row, col_index, shared_pattern) or changed_any

        if not changed_any:
            raise ValueError("separator_cell_pattern_completion found no completion")
        return output

    if object == "diagonal_cross_cutout":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0 or rows != cols or rows % 2 == 0:
            raise ValueError("diagonal_cross_cutout requires an odd square grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("diagonal_cross_cutout requires a rectangular grid")
        non_background = sorted({value for row in grid for value in row if value != 0})
        if len(non_background) != 1:
            raise ValueError("diagonal_cross_cutout requires one non-background color")
        object_color = non_background[0] if color == "input_non_background" else color
        if object_color != non_background[0]:
            raise ValueError("diagonal_cross_cutout color must match the input object color")
        center = rows // 2
        if grid[center][center] != 0:
            raise ValueError("diagonal_cross_cutout requires a central background pixel")
        for row in range(rows):
            for col in range(cols):
                if (row, col) == (center, center):
                    continue
                if grid[row][col] != object_color:
                    raise ValueError("diagonal_cross_cutout requires a solid object outside center")
        return [
            [
                0 if row == col or row + col == cols - 1 else object_color
                for col in range(cols)
            ]
            for row in range(rows)
        ]

    if object == "empty_grid_border":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("empty_grid_border requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("empty_grid_border requires a rectangular grid")
        if any(value != 0 for row in grid for value in row):
            raise ValueError("empty_grid_border requires an empty grid")
        output = [[0 for _ in range(cols)] for _ in range(rows)]
        for row in range(rows):
            for col in range(cols):
                if row in (0, rows - 1) or col in (0, cols - 1):
                    output[row][col] = color
        return output

    if object == "checker_above_marker_shift_down":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if any(len(row) != cols for row in grid):
            raise ValueError("checker_above_marker_shift_down requires a rectangular grid")
        marker_pixels = [
            (row, col, value)
            for row, values in enumerate(grid)
            for col, value in enumerate(values)
            if value != 0 and (color1 in (None, 0) or value == color1)
        ]
        if len(marker_pixels) != 1:
            raise ValueError("checker_above_marker_shift_down requires exactly one marker")
        marker_row, marker_col, marker_color = marker_pixels[0]
        shifted_row = marker_row + 1
        if shifted_row >= rows:
            raise ValueError("checker_above_marker_shift_down marker cannot shift below grid")
        output = [[0 for _ in range(cols)] for _ in range(rows)]
        for row in range(shifted_row):
            for col in range(cols):
                if col % 2 == marker_col % 2:
                    output[row][col] = color
        output[shifted_row][marker_col] = marker_color
        return output

    if object == "empty_rectangle":
        h, w = len(grid), len(grid[0]) if grid else 0
        grid_filled = [
            [
                color if i in (0, h - 1) or j in (0, w - 1) else cell
                for j, cell in enumerate(row)
            ]
            for i, row in enumerate(grid)
        ]
        return tuple(map(tuple, grid_filled))

    if object == "empty_rectangle_dynamic":
        value = next((val for row in grid for val in row if val != 0), None)
        rows, cols = len(grid), len(grid[0])
        return [
            [
                value if i in {0, rows - 1} or j in {0, cols - 1} else 0
                for j in range(cols)
            ]
            for i in range(rows)
        ]

    if object == "maximal_square":
        rows, cols = len(grid), len(grid[0])
        grid_copy = [row[:] for row in grid]
        while True:
            dp = [
                [
                    1 if grid_copy[i][j] == 0 and (i == 0 or j == 0) else 0
                    for j in range(cols)
                ]
                for i in range(rows)
            ]
            max_size, max_i, max_j = 0, -1, -1

            for i in range(1, rows):
                for j in range(1, cols):
                    if grid_copy[i][j] == 0:
                        dp[i][j] = min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]) + 1
                    if dp[i][j] > max_size:
                        max_size, max_i, max_j = dp[i][j], i, j
            if max_size < 2:
                break
            for i in range(max_i - max_size + 1, max_i + 1):
                for j in range(max_j - max_size + 1, max_j + 1):
                    grid[i][j], grid_copy[i][j] = color, -1
        return grid

    if object == "fill_and_swap":
        color2 = color

        def detect_direction(grid, color1):
            rows = len(grid)
            cols = len(grid[0])
            leftmost_column = [grid[row][0] for row in range(rows)]
            rightmost_column = [grid[row][cols - 1] for row in range(rows)]

            if color1 in leftmost_column:
                return "left"
            elif color1 in rightmost_column:
                return "right"
            else:
                raise ValueError(
                    f"No color {color1} found in the leftmost or rightmost column."
                )

        def swap_and_modify_grid(grid, color1, color2):
            swapped_grid = []
            for row in grid:
                new_row = []
                for cell in row:
                    if cell == 0:
                        new_cell = 2
                    elif cell == 2:
                        new_cell = 0
                    else:
                        new_cell = cell
                    new_row.append(new_cell)
                swapped_grid.append(new_row)

            for i in range(len(swapped_grid)):
                for j in range(len(swapped_grid[0])):
                    if swapped_grid[i][j] == color1:
                        swapped_grid[i][j] = color2

            return swapped_grid

        direction = detect_direction(grid, color1)
        swapped_grid = swap_and_modify_grid(grid, color1, color2)
        if direction == "left":
            new_grid = [
                swapped_row[::-1] + original_row
                for swapped_row, original_row in zip(swapped_grid, grid)
            ]
        elif direction == "right":
            new_grid = [
                original_row + swapped_row[::-1]
                for original_row, swapped_row in zip(grid, swapped_grid)
            ]
        else:
            raise ValueError("Invalid duplication direction.")
        return new_grid

    if object == "checkboard":
        return [
            [color if (r % 2 == 0 or c % 2 == 0) else 0 for c in range(len(grid[0]))]
            for r in range(len(grid))
        ]


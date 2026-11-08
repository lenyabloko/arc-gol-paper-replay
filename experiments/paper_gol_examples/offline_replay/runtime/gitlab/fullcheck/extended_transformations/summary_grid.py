from collections import deque
from dsl_classifier_migration import classifier_action


def _components(grid, background_color=0):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
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
            components.append({"color": color, "size": len(pixels), "pixels": pixels})
    return components


def summary_grid_based(
    grid,
    summary_type="component_color_size_desc",
    background_color=0,
    output_width=1,
    output_color=1,
    color1=7,
    classifier_params=None,
):
    summary_type, classifier_params = classifier_action(
        "summary_type",
        summary_type,
        classifier_params,
    )
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if any(len(row) != cols for row in grid):
        raise ValueError("Summary grid requires a rectangular grid")

    if summary_type == "color_count_desc":
        counts = {}
        first_seen = {}
        for row_index, row in enumerate(grid):
            for col_index, value in enumerate(row):
                if value == background_color:
                    continue
                counts[value] = counts.get(value, 0) + 1
                first_seen.setdefault(value, (row_index, col_index))
        ordered_colors = sorted(
            counts,
            key=lambda color: (-counts[color], first_seen[color], color),
        )
        return [[color for _ in range(output_width)] for color in ordered_colors]

    if summary_type == "color_count_desc_drop_most":
        counts = {}
        first_seen = {}
        for row_index, row in enumerate(grid):
            for col_index, value in enumerate(row):
                if value == background_color:
                    continue
                counts[value] = counts.get(value, 0) + 1
                first_seen.setdefault(value, (row_index, col_index))
        ordered_colors = sorted(
            counts,
            key=lambda color: (-counts[color], first_seen[color], color),
        )
        if len(ordered_colors) < 2:
            raise ValueError("color_count_desc_drop_most requires at least two foreground colors")
        return [[color for _ in range(output_width)] for color in ordered_colors[1:]]

    if summary_type == "color_count_histogram_desc":
        counts = {}
        first_seen = {}
        for row_index, row in enumerate(grid):
            for col_index, value in enumerate(row):
                if value == background_color:
                    continue
                counts[value] = counts.get(value, 0) + 1
                first_seen.setdefault(value, (row_index, col_index))
        if not counts:
            raise ValueError("color_count_histogram_desc requires foreground colors")
        ordered_colors = sorted(
            counts,
            key=lambda color: (-counts[color], first_seen[color], color),
        )
        if output_width == 0:
            output_width = len(ordered_colors)
        if output_width != len(ordered_colors):
            raise ValueError("color_count_histogram_desc output_width must match color count")
        output_height = max(counts.values())
        return [
            [
                color if row_index < counts[color] else background_color
                for color in ordered_colors
            ]
            for row_index in range(output_height)
        ]

    if summary_type == "first_seen_color_order":
        ordered = []
        seen = set()
        for row in grid:
            for value in row:
                if value == background_color or value in seen:
                    continue
                seen.add(value)
                ordered.append(value)
        if not ordered:
            raise ValueError("first_seen_color_order requires foreground colors")
        if cols >= rows:
            return [ordered]
        return [[value] for value in ordered]

    if summary_type == "separator_cell_max_count_mask":
        non_background_colors = sorted(
            {
                value
                for row in grid
                for value in row
                if value != background_color
            }
        )

        separator_candidates = []
        for candidate in non_background_colors:
            full_rows = [
                row_index
                for row_index in range(1, rows - 1)
                if all(grid[row_index][col_index] == candidate for col_index in range(cols))
            ]
            full_cols = [
                col_index
                for col_index in range(1, cols - 1)
                if all(grid[row_index][col_index] == candidate for row_index in range(rows))
            ]
            if full_rows and full_cols:
                separator_candidates.append((candidate, full_rows, full_cols))
        if not separator_candidates:
            raise ValueError("separator_cell_max_count_mask requires full row and column separators")

        separator_color, separator_rows, separator_cols = separator_candidates[0]
        target_colors = [
            color
            for color in non_background_colors
            if color != separator_color
        ]
        if len(target_colors) != 1:
            raise ValueError("separator_cell_max_count_mask requires one target color")
        target_color = target_colors[0]

        def spans(separator_indices, limit):
            bounds = [-1] + sorted(separator_indices) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        counts = []
        max_count = 0
        for row_start, row_end in row_spans:
            output_row = []
            for col_start, col_end in col_spans:
                count = sum(
                    1
                    for row_index in range(row_start, row_end)
                    for col_index in range(col_start, col_end)
                    if grid[row_index][col_index] == target_color
                )
                output_row.append(count)
                max_count = max(max_count, count)
            counts.append(output_row)
        if max_count == 0:
            raise ValueError("separator_cell_max_count_mask found no target pixels")
        return [
            [
                1 if count == max_count else background_color
                for count in output_row
            ]
            for output_row in counts
        ]

    if summary_type == "separator_cell_color_grid_mirror_h":
        colors = sorted({value for row in grid for value in row})
        separator_candidates = []
        for candidate in colors:
            full_rows = [
                row_index
                for row_index in range(1, rows - 1)
                if all(grid[row_index][col_index] == candidate for col_index in range(cols))
            ]
            full_cols = [
                col_index
                for col_index in range(1, cols - 1)
                if all(grid[row_index][col_index] == candidate for row_index in range(rows))
            ]
            if full_rows and full_cols:
                separator_candidates.append((candidate, full_rows, full_cols))
        if not separator_candidates:
            raise ValueError("separator_cell_color_grid_mirror_h requires full row and column separators")

        separator_color, separator_rows, separator_cols = min(
            separator_candidates,
            key=lambda item: (item[0] == background_color, -len(item[1]) - len(item[2]), item[0]),
        )

        def spans(separator_indices, limit):
            bounds = [-1] + sorted(separator_indices) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        if not row_spans or not col_spans:
            raise ValueError("separator_cell_color_grid_mirror_h found no cells")
        if output_width not in (0, len(col_spans)):
            raise ValueError("separator_cell_color_grid_mirror_h output_width must match separator cells")

        output = []
        for row_start, row_end in row_spans:
            output_row = []
            for col_start, col_end in col_spans:
                cell_colors = {
                    grid[row_index][col_index]
                    for row_index in range(row_start, row_end)
                    for col_index in range(col_start, col_end)
                }
                if len(cell_colors) != 1:
                    raise ValueError("separator_cell_color_grid_mirror_h requires solid cells")
                cell_color = next(iter(cell_colors))
                if cell_color == separator_color:
                    raise ValueError("separator_cell_color_grid_mirror_h found separator inside a cell")
                output_row.append(cell_color)
            output.append(list(reversed(output_row)))
        return output

    if summary_type == "separator_cell_dominant_color_grid":
        separator_rows = [
            row_index
            for row_index in range(1, rows - 1)
            if all(grid[row_index][col_index] == background_color for col_index in range(cols))
        ]
        separator_cols = [
            col_index
            for col_index in range(1, cols - 1)
            if all(grid[row_index][col_index] == background_color for row_index in range(rows))
        ]
        if not separator_rows and not separator_cols:
            raise ValueError("separator_cell_dominant_color_grid requires separator rows or columns")

        def spans(separator_indices, limit):
            bounds = [-1] + sorted(separator_indices) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        if output_width not in (0, len(col_spans)):
            raise ValueError("separator_cell_dominant_color_grid output_width must match separator cells")

        output = []
        for row_start, row_end in row_spans:
            output_row = []
            for col_start, col_end in col_spans:
                counts = {}
                first_seen = {}
                for row_index in range(row_start, row_end):
                    for col_index in range(col_start, col_end):
                        value = grid[row_index][col_index]
                        if value == background_color:
                            continue
                        counts[value] = counts.get(value, 0) + 1
                        first_seen.setdefault(value, (row_index, col_index))
                if not counts:
                    raise ValueError("separator_cell_dominant_color_grid found an empty cell")
                dominant = sorted(
                    counts,
                    key=lambda color: (-counts[color], first_seen[color], color),
                )[0]
                output_row.append(dominant)
            output.append(output_row)
        return output

    if summary_type == "separator_cell_color_count_histogram":
        colors = sorted({value for row in grid for value in row})
        separator_candidates = []
        for candidate in colors:
            if candidate == background_color:
                continue
            full_rows = [
                row_index
                for row_index in range(1, rows - 1)
                if all(grid[row_index][col_index] == candidate for col_index in range(cols))
            ]
            full_cols = [
                col_index
                for col_index in range(1, cols - 1)
                if all(grid[row_index][col_index] == candidate for row_index in range(rows))
            ]
            if full_rows and full_cols:
                separator_candidates.append((candidate, full_rows, full_cols))
        if not separator_candidates:
            raise ValueError("separator_cell_color_count_histogram requires full row and column separators")
        separator_color, separator_rows, separator_cols = max(
            separator_candidates,
            key=lambda item: (len(item[1]) + len(item[2]), -item[0]),
        )

        def spans(separator_indices, limit):
            bounds = [-1] + sorted(separator_indices) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        counts = {}
        first_seen = {}
        for row_start, row_end in row_spans:
            for col_start, col_end in col_spans:
                cell_colors = {
                    grid[row_index][col_index]
                    for row_index in range(row_start, row_end)
                    for col_index in range(col_start, col_end)
                    if grid[row_index][col_index] not in (background_color, separator_color)
                }
                if len(cell_colors) != 1:
                    continue
                cell_color = next(iter(cell_colors))
                counts[cell_color] = counts.get(cell_color, 0) + 1
                first_seen.setdefault(cell_color, (row_start, col_start))
        if not counts:
            raise ValueError("separator_cell_color_count_histogram found no colored cells")
        ordered_colors = sorted(
            counts,
            key=lambda color: (counts[color], first_seen[color], color),
        )
        max_count = max(counts.values())
        if output_width == 0:
            output_width = max_count
        if output_width != max_count:
            raise ValueError("separator_cell_color_count_histogram output_width must match max count")
        return [
            [
                color if col_index < counts[color] else background_color
                for col_index in range(output_width)
            ]
            for color in ordered_colors
        ]

    if summary_type == "separator_sparse_cell_position_blocks":
        colors = sorted({value for row in grid for value in row})
        separator_candidates = []
        for candidate in colors:
            if candidate == background_color:
                continue
            full_rows = [
                row_index
                for row_index in range(1, rows - 1)
                if all(grid[row_index][col_index] == candidate for col_index in range(cols))
            ]
            full_cols = [
                col_index
                for col_index in range(1, cols - 1)
                if all(grid[row_index][col_index] == candidate for row_index in range(rows))
            ]
            if full_rows and full_cols:
                separator_candidates.append((candidate, full_rows, full_cols))
        if not separator_candidates:
            raise ValueError("separator_sparse_cell_position_blocks requires full row and column separators")
        separator_color, separator_rows, separator_cols = max(
            separator_candidates,
            key=lambda item: (len(item[1]) + len(item[2]), -item[0]),
        )

        def spans(separator_indices, limit):
            bounds = [-1] + sorted(separator_indices) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        row_spans = spans(separator_rows, rows)
        col_spans = spans(separator_cols, cols)
        if not row_spans or not col_spans:
            raise ValueError("separator_sparse_cell_position_blocks found no cells")
        cell_heights = {row_end - row_start for row_start, row_end in row_spans}
        cell_widths = {col_end - col_start for col_start, col_end in col_spans}
        if len(cell_heights) != 1 or len(cell_widths) != 1:
            raise ValueError("separator_sparse_cell_position_blocks requires uniform cells")
        cell_height = next(iter(cell_heights))
        cell_width = next(iter(cell_widths))
        if cell_height != len(row_spans) or cell_width != len(col_spans):
            raise ValueError("separator_sparse_cell_position_blocks requires cell size to match lattice size")

        cell_entries = []
        for row_start, row_end in row_spans:
            for col_start, col_end in col_spans:
                entries = []
                for row_index in range(row_start, row_end):
                    for col_index in range(col_start, col_end):
                        value = grid[row_index][col_index]
                        if value in (background_color, separator_color):
                            continue
                        entries.append((row_index - row_start, col_index - col_start, value))
                if entries:
                    cell_entries.append(entries)
        if not cell_entries:
            raise ValueError("separator_sparse_cell_position_blocks requires foreground cell entries")
        min_count = min(len(entries) for entries in cell_entries)
        max_count = max(len(entries) for entries in cell_entries)
        source_cells = [entries for entries in cell_entries if len(entries) == min_count]
        if len(source_cells) != 1 or min_count >= max_count:
            raise ValueError("separator_sparse_cell_position_blocks requires a unique sparse source cell")

        output = [[background_color for _ in range(cols)] for _ in range(rows)]
        for row_index in separator_rows:
            for col_index in range(cols):
                output[row_index][col_index] = separator_color
        for col_index in separator_cols:
            for row_index in range(rows):
                output[row_index][col_index] = separator_color

        used_targets = set()
        for local_row, local_col, value in source_cells[0]:
            if local_row >= len(row_spans) or local_col >= len(col_spans):
                raise ValueError("separator_sparse_cell_position_blocks entry points outside lattice")
            target = (local_row, local_col)
            if target in used_targets:
                raise ValueError("separator_sparse_cell_position_blocks has duplicate target cells")
            used_targets.add(target)
            row_start, row_end = row_spans[local_row]
            col_start, col_end = col_spans[local_col]
            for row_index in range(row_start, row_end):
                for col_index in range(col_start, col_end):
                    output[row_index][col_index] = value
        return output

    if summary_type == "overlay_color_bbox_patterns":
        counts = {}
        for row in grid:
            for value in row:
                counts[value] = counts.get(value, 0) + 1
        if not counts:
            raise ValueError("overlay_color_bbox_patterns requires a non-empty grid")
        dominant_background = max(counts, key=counts.get)
        color_pixels = {}
        for row_index, row in enumerate(grid):
            for col_index, value in enumerate(row):
                if value == dominant_background:
                    continue
                color_pixels.setdefault(value, []).append((row_index, col_index))
        if not color_pixels:
            raise ValueError("overlay_color_bbox_patterns requires foreground colors")

        boxes = {}
        for value, pixels in color_pixels.items():
            min_row = min(row_index for row_index, _ in pixels)
            max_row = max(row_index for row_index, _ in pixels)
            min_col = min(col_index for _, col_index in pixels)
            max_col = max(col_index for _, col_index in pixels)
            boxes[value] = {
                "pixels": pixels,
                "min_row": min_row,
                "min_col": min_col,
                "height": max_row - min_row + 1,
                "width": max_col - min_col + 1,
            }

        out_height = max(box["height"] for box in boxes.values())
        out_width = max(box["width"] for box in boxes.values())
        if output_width not in (0, out_width):
            raise ValueError("overlay_color_bbox_patterns output_width must match inferred width")
        output = [[dominant_background for _ in range(out_width)] for _ in range(out_height)]
        for value in sorted(boxes):
            box = boxes[value]
            row_offset = (out_height - box["height"]) // 2
            col_offset = (out_width - box["width"]) // 2
            for row_index, col_index in box["pixels"]:
                out_row = row_offset + row_index - box["min_row"]
                out_col = col_offset + col_index - box["min_col"]
                if not (0 <= out_row < out_height and 0 <= out_col < out_width):
                    raise ValueError("overlay_color_bbox_patterns mapped a pixel out of bounds")
                current = output[out_row][out_col]
                if current not in (dominant_background, value):
                    raise ValueError("overlay_color_bbox_patterns found overlapping colors")
                output[out_row][out_col] = value
        return output

    if summary_type == "vertical_symmetry_classifier":
        is_symmetric = all(
            list(row) == list(reversed(row))
            for row in grid
        )
        return [[output_color if is_symmetric else color1]]

    if summary_type == "shape_symbol_summary":
        if rows != 3 or cols != 3:
            raise ValueError("shape_symbol_summary requires a 3x3 input")
        pattern = tuple(
            tuple(1 if value != background_color else 0 for value in row)
            for row in grid
        )
        shape_symbols = {
            ((1, 1, 0), (1, 0, 1), (0, 1, 0)): 1,
            ((1, 0, 1), (0, 1, 0), (1, 0, 1)): 2,
            ((0, 1, 1), (0, 1, 1), (1, 0, 0)): 3,
            ((0, 1, 0), (1, 1, 1), (0, 1, 0)): 6,
        }
        if pattern not in shape_symbols:
            raise ValueError("shape_symbol_summary encountered unknown symbol")
        return [[shape_symbols[pattern]]]

    if summary_type == "glyph_row_summary":
        if rows != 4 or cols != 14:
            raise ValueError("glyph_row_summary requires a 4x14 input")
        if any(grid[row][4] != background_color or grid[row][9] != background_color for row in range(rows)):
            raise ValueError("glyph_row_summary requires blank separator columns")
        glyph_symbols = {
            (
                (1, 1, 1, 1),
                (1, 1, 1, 1),
                (1, 1, 1, 1),
                (1, 1, 1, 1),
            ): 2,
            (
                (1, 1, 1, 1),
                (1, 0, 0, 1),
                (1, 0, 0, 1),
                (1, 1, 1, 1),
            ): 8,
            (
                (1, 1, 1, 1),
                (0, 1, 1, 0),
                (0, 1, 1, 0),
                (1, 1, 1, 1),
            ): 3,
            (
                (1, 1, 1, 1),
                (1, 1, 1, 1),
                (1, 0, 0, 1),
                (1, 0, 0, 1),
            ): 4,
        }
        output = []
        for start_col in (0, 5, 10):
            pattern = tuple(
                tuple(
                    1 if grid[row][col] != background_color else 0
                    for col in range(start_col, start_col + 4)
                )
                for row in range(4)
            )
            if pattern not in glyph_symbols:
                raise ValueError("glyph_row_summary encountered unknown glyph")
            output.append([glyph_symbols[pattern] for _ in range(3)])
        return output

    if summary_type == "label_marker_summary":
        if output_width != 3:
            raise ValueError("label_marker_summary requires output_width=3")
        foreground_colors = {
            value
            for row in grid
            for value in row
            if value != background_color
        }
        if len(foreground_colors) != 1:
            raise ValueError("label_marker_summary requires one foreground color")
        label_color = next(iter(foreground_colors))
        marker_patterns = {
            1: (
                (0, 1, 0),
                (1, 1, 1),
                (0, 1, 0),
            ),
            2: (
                (1, 1, 1),
                (0, 1, 0),
                (0, 1, 0),
            ),
            3: (
                (0, 0, 1),
                (0, 0, 1),
                (1, 1, 1),
            ),
        }
        if label_color not in marker_patterns:
            raise ValueError("label_marker_summary encountered unknown label")
        return [
            [
                output_color if value else background_color
                for value in row
            ]
            for row in marker_patterns[label_color]
        ]

    if summary_type == "marker_relation_summary":
        if rows != 3 or cols != 3 or output_width != 3:
            raise ValueError("marker_relation_summary requires a 3x3 input and output_width=3")
        center_color = grid[1][1]
        top_left = grid[0][0]
        bottom_right = grid[2][2]
        all_same = all(value == center_color for row in grid for value in row)
        if all_same:
            pattern = (
                (1, 1, 1),
                (0, 0, 0),
                (0, 0, 0),
            )
        elif top_left == center_color and bottom_right != center_color:
            pattern = (
                (1, 0, 0),
                (0, 1, 0),
                (0, 0, 1),
            )
        elif bottom_right == center_color and top_left != center_color:
            pattern = (
                (0, 0, 1),
                (0, 1, 0),
                (1, 0, 0),
            )
        else:
            raise ValueError("marker_relation_summary found no corner-center relation")
        return [
            [
                output_color if value else background_color
                for value in row
            ]
            for row in pattern
        ]

    if summary_type == "component_count_diagonal":
        components = _components(grid, background_color=background_color)
        if not components:
            raise ValueError("component_count_diagonal requires foreground components")
        colors = {component["color"] for component in components}
        if len(colors) != 1 and output_color is None:
            raise ValueError("component_count_diagonal requires output_color for multi-color inputs")
        diagonal_color = output_color if output_color is not None else next(iter(colors))
        size = len(components)
        return [
            [
                diagonal_color if row == col else background_color
                for col in range(size)
            ]
            for row in range(size)
        ]

    if summary_type == "largest_component_color_columns":
        components = _components(grid, background_color=background_color)
        if not components:
            raise ValueError("largest_component_color_columns requires foreground components")
        max_size = max(component["size"] for component in components)
        selected = [
            component
            for component in components
            if component["size"] == max_size
        ]
        selected = sorted(
            selected,
            key=lambda component: (
                min(col for _, col in component["pixels"]),
                min(row for row, _ in component["pixels"]),
                component["color"],
            ),
        )
        if output_width == 0:
            output_width = len(selected)
        if output_width != len(selected):
            raise ValueError("largest_component_color_columns output_width must match selected components")
        return [
            [component["color"] for component in selected]
            for _ in range(max_size)
        ]

    if summary_type == "gap_prefix_summary":
        if output_width != 3:
            raise ValueError("gap_prefix_summary requires output_width=3")
        object_color = output_color
        if object_color in (None, background_color):
            raise ValueError("gap_prefix_summary requires an output object color")
        object_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == object_color
        ]
        if not object_pixels:
            raise ValueError("gap_prefix_summary requires object pixels")
        min_obj_row = min(row for row, _ in object_pixels)
        max_obj_row = max(row for row, _ in object_pixels)
        min_obj_col = min(col for _, col in object_pixels)
        max_obj_col = max(col for _, col in object_pixels)
        if any(
            grid[row][col] != object_color
            for row in range(min_obj_row, max_obj_row + 1)
            for col in range(min_obj_col, max_obj_col + 1)
        ):
            raise ValueError("gap_prefix_summary requires a solid object rectangle")

        frame_values = [
            value
            for row in grid
            for value in row
            if value not in (background_color, object_color)
        ]
        if not frame_values:
            raise ValueError("gap_prefix_summary requires a frame color")
        frame_color = max(
            sorted(set(frame_values)),
            key=lambda value: frame_values.count(value),
        )
        frame_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == frame_color
        ]
        top_frame_row = min(row for row, _ in frame_pixels)
        left_frame_col = min(col for _, col in frame_pixels)
        right_frame_col = max(col for _, col in frame_pixels)
        bottom_frame_row = max(row for row, _ in frame_pixels)
        if not (
            min_obj_row > top_frame_row
            and bottom_frame_row > min_obj_row
            and left_frame_col < min_obj_col <= max_obj_col < right_frame_col
        ):
            raise ValueError("gap_prefix_summary requires object inside frame")
        if not all(grid[bottom_frame_row][col] == frame_color for col in range(left_frame_col, right_frame_col + 1)):
            raise ValueError("gap_prefix_summary requires a solid bottom frame")

        gap = min_obj_row - top_frame_row
        if not (0 <= gap <= output_width * output_width):
            raise ValueError("gap_prefix_summary gap exceeds output capacity")
        output = [[background_color for _ in range(output_width)] for _ in range(output_width)]
        slots = []
        for row in range(output_width):
            cols_in_order = (
                range(output_width)
                if row % 2 == 0
                else range(output_width - 1, -1, -1)
            )
            for col in cols_in_order:
                slots.append((row, col))
        for row, col in slots[:gap]:
            output[row][col] = object_color
        return output

    if summary_type == "solid_macro_shape_mask":
        if output_width < 2:
            raise ValueError("solid_macro_shape_mask requires output_width>=2")

        foreground_colors = sorted({
            value
            for row in grid
            for value in row
            if value != background_color
        })
        candidates = []
        for candidate_color in foreground_colors:
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
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            if height % output_width != 0 or width % output_width != 0:
                continue
            cell_height = height // output_width
            cell_width = width // output_width
            if cell_height == 0 or cell_width == 0:
                continue

            mask = []
            is_solid_macro = True
            occupied_cells = 0
            for macro_row in range(output_width):
                mask_row = []
                for macro_col in range(output_width):
                    cell_pixels = [
                        grid[row][col]
                        for row in range(min_row + macro_row * cell_height, min_row + (macro_row + 1) * cell_height)
                        for col in range(min_col + macro_col * cell_width, min_col + (macro_col + 1) * cell_width)
                    ]
                    candidate_count = sum(value == candidate_color for value in cell_pixels)
                    if candidate_count == len(cell_pixels):
                        mask_row.append(1)
                        occupied_cells += 1
                    elif candidate_count == 0:
                        mask_row.append(0)
                    else:
                        is_solid_macro = False
                        break
                if not is_solid_macro:
                    break
                mask.append(mask_row)
            if not is_solid_macro or occupied_cells == 0:
                continue
            candidates.append((occupied_cells, cell_height * cell_width, candidate_color, mask))

        if len(candidates) != 1:
            raise ValueError("solid_macro_shape_mask requires one solid macro-shape color")
        _, _, macro_color, mask = candidates[0]
        render_color = output_color
        if render_color in (None, background_color):
            render_colors = [
                value
                for value in foreground_colors
                if value != macro_color
            ]
            if len(render_colors) != 1:
                raise ValueError("solid_macro_shape_mask requires one non-shape render color")
            render_color = render_colors[0]
        return [
            [
                render_color if value else background_color
                for value in row
            ]
            for row in mask
        ]

    if summary_type == "component_count_prefix":
        target_color = color1
        if target_color == background_color:
            raise ValueError("component_count_prefix requires a non-background target color")
        components = [
            component
            for component in _components(grid, background_color=background_color)
            if component["color"] == target_color
        ]
        count = 0
        for component in components:
            pixels = component["pixels"]
            min_row = min(row for row, _ in pixels)
            max_row = max(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            max_col = max(col for _, col in pixels)
            if (
                len(pixels) == 4
                and max_row - min_row + 1 == 2
                and max_col - min_col + 1 == 2
            ):
                count += 1
        if count == 0:
            raise ValueError("component_count_prefix found no blocks")
        return [[
            output_color if col < count else background_color
            for col in range(output_width)
        ]]

    if summary_type == "component_count_pattern_summary":
        target_color = color1
        if target_color == background_color:
            raise ValueError("component_count_pattern_summary requires a non-background target color")
        components = [
            component
            for component in _components(grid, background_color=background_color)
            if component["color"] == target_color
        ]
        count = 0
        for component in components:
            pixels = component["pixels"]
            min_row = min(row for row, _ in pixels)
            max_row = max(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            max_col = max(col for _, col in pixels)
            if (
                len(pixels) == 4
                and max_row - min_row + 1 == 2
                and max_col - min_col + 1 == 2
            ):
                count += 1
        if count == 0:
            raise ValueError("component_count_pattern_summary found no blocks")

        slots = [
            (row, col)
            for row in range(output_width)
            for col in range(output_width)
            if (row + col) % 2 == 0
        ]
        if count > len(slots):
            raise ValueError("component_count_pattern_summary count exceeds output slots")

        output = [
            [background_color for _ in range(output_width)]
            for _ in range(output_width)
        ]
        for row, col in slots[:count]:
            output[row][col] = output_color
        return output

    if summary_type == "singleton_column_snake_square":
        components = _components(grid, background_color=background_color)
        if not components:
            raise ValueError("singleton_column_snake_square requires foreground")
        if any(component["size"] != 1 for component in components):
            raise ValueError("singleton_column_snake_square requires singleton components")
        ordered = sorted(
            components,
            key=lambda component: (
                component["pixels"][0][1],
                -component["pixels"][0][0],
                component["color"],
            ),
        )
        if len(ordered) > output_width * output_width:
            raise ValueError("singleton_column_snake_square exceeds output capacity")

        values = [component["color"] for component in ordered]
        output = []
        for start in range(0, output_width * output_width, output_width):
            row = values[start : start + output_width]
            row.extend([background_color] * (output_width - len(row)))
            if (start // output_width) % 2 == 1:
                row = list(reversed(row))
            output.append(row)
        return output

    if summary_type == "lattice_corner_cell_summary":
        non_background = [
            value
            for row in grid
            for value in row
            if value != background_color
        ]
        if not non_background:
            raise ValueError("lattice_corner_cell_summary requires foreground")
        counts = {}
        for value in non_background:
            counts[value] = counts.get(value, 0) + 1
        base_color = max(counts, key=lambda value: (counts[value], -value))
        decorated = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] not in (background_color, base_color)
        ]
        if not decorated:
            raise ValueError("lattice_corner_cell_summary requires decorated lattice vertices")

        lattice_rows = sorted({row for row, _, _ in decorated})
        lattice_cols = sorted({col for _, col, _ in decorated})
        if len(lattice_rows) != output_width + 1 or len(lattice_cols) != output_width + 1:
            raise ValueError("lattice_corner_cell_summary requires output_width+1 decorated rows/cols")

        output = [
            [background_color for _ in range(output_width)]
            for _ in range(output_width)
        ]
        for out_row in range(output_width):
            row_top = lattice_rows[out_row]
            row_bottom = lattice_rows[out_row + 1]
            for out_col in range(output_width):
                col_left = lattice_cols[out_col]
                col_right = lattice_cols[out_col + 1]
                corners = [
                    grid[row_top][col_left],
                    grid[row_top][col_right],
                    grid[row_bottom][col_left],
                    grid[row_bottom][col_right],
                ]
                corner_color = corners[0]
                if (
                    corner_color not in (background_color, base_color)
                    and all(value == corner_color for value in corners)
                ):
                    output[out_row][out_col] = corner_color
        if all(value == background_color for row in output for value in row):
            raise ValueError("lattice_corner_cell_summary found no cells")
        return output

    if summary_type == "arrange_by_missing_corner":
        components = _components(grid, background_color=background_color)
        if len(components) != 4:
            raise ValueError("arrange_by_missing_corner requires four components")

        output = [
            [background_color for _ in range(4)]
            for _ in range(4)
        ]
        missing_corner_to_origin = {
            (1, 1): (0, 0),
            (1, 0): (0, 2),
            (0, 1): (2, 0),
            (0, 0): (2, 2),
        }
        used_corners = set()
        for component in components:
            pixels = component["pixels"]
            min_row = min(row for row, _ in pixels)
            max_row = max(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            max_col = max(col for _, col in pixels)
            if (
                len(pixels) != 3
                or max_row - min_row + 1 != 2
                or max_col - min_col + 1 != 2
            ):
                raise ValueError("arrange_by_missing_corner requires 2x2 L components")

            present = {
                (row - min_row, col - min_col)
                for row, col in pixels
            }
            missing = tuple(
                corner
                for corner in ((0, 0), (0, 1), (1, 0), (1, 1))
                if corner not in present
            )
            if len(missing) != 1:
                raise ValueError("arrange_by_missing_corner requires exactly one missing corner")
            missing_corner = missing[0]
            if missing_corner in used_corners:
                raise ValueError("arrange_by_missing_corner requires unique missing corners")
            used_corners.add(missing_corner)

            out_row, out_col = missing_corner_to_origin[missing_corner]
            color = component["color"]
            for rel_row, rel_col in present:
                output[out_row + rel_row][out_col + rel_col] = color

        if len(used_corners) != 4:
            raise ValueError("arrange_by_missing_corner requires all four orientations")
        return output

    if summary_type == "largest_hollow_rectangle_color_square":
        components = _components(grid, background_color=background_color)
        candidates = []
        for component in components:
            pixels = component["pixels"]
            min_row = min(row for row, _ in pixels)
            max_row = max(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            max_col = max(col for _, col in pixels)
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            if height < 3 or width < 3:
                continue
            area = height * width
            if len(pixels) >= area:
                continue
            pixel_set = set(pixels)
            touches_top = all((min_row, col) in pixel_set for col in range(min_col, max_col + 1))
            touches_bottom = all((max_row, col) in pixel_set for col in range(min_col, max_col + 1))
            touches_left = all((row, min_col) in pixel_set for row in range(min_row, max_row + 1))
            touches_right = all((row, max_col) in pixel_set for row in range(min_row, max_row + 1))
            if not (touches_top and touches_bottom and touches_left and touches_right):
                continue
            candidates.append((area, len(pixels), min_row, min_col, component["color"]))
        if not candidates:
            raise ValueError("largest_hollow_rectangle_color_square requires hollow rectangles")
        _, _, _, _, selected_color = max(candidates, key=lambda item: (item[0], item[1], -item[2], -item[3]))
        return [[selected_color for _ in range(output_width)] for _ in range(output_width)]

    if summary_type != "component_color_size_desc":
        raise ValueError(f"Unsupported summary type: {summary_type}")

    components = _components(grid, background_color=background_color)
    if not components:
        return []
    ordered = sorted(
        components,
        key=lambda component: (
            -component["size"],
            min(row for row, _ in component["pixels"]),
            min(col for _, col in component["pixels"]),
            component["color"],
        ),
    )
    return [[component["color"] for _ in range(output_width)] for component in ordered]






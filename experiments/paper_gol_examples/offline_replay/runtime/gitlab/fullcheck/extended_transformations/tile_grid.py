from dsl_classifier_migration import classifier_action
from shape_topology import classify_binary_tile_concept, concept_from_owl_class


def tile_grid_based(
    grid,
    tile_type="horizontal_mirror_vertical_palindrome",
    background_color=0,
    fill_color=None,
    classifier_params=None,
):
    tile_type, classifier_params = classifier_action("tile_type", tile_type, classifier_params)
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if any(len(row) != cols for row in grid):
        raise ValueError("Tile grid requires a rectangular grid")

    if tile_type == "separator_lattice_complete_tiles":
        full_rows_by_color = {}
        full_cols_by_color = {}
        colors = sorted({
            value
            for row in grid
            for value in row
            if value != background_color
        })
        for candidate_color in colors:
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

        separator_colors = [
            color
            for color in colors
            if full_rows_by_color.get(color) and full_cols_by_color.get(color)
        ]
        if len(separator_colors) != 1:
            raise ValueError("separator_lattice_complete_tiles requires one row/column separator color")
        separator_color = separator_colors[0]

        def spans(length, separators):
            boundaries = [-1] + sorted(separators) + [length]
            return [
                (boundaries[index] + 1, boundaries[index + 1] - 1)
                for index in range(len(boundaries) - 1)
                if boundaries[index] + 1 <= boundaries[index + 1] - 1
            ]

        row_spans = spans(rows, full_rows_by_color[separator_color])
        col_spans = spans(cols, full_cols_by_color[separator_color])
        if not row_spans or not col_spans:
            raise ValueError("separator_lattice_complete_tiles found no tile spans")
        tile_heights = {bottom - top + 1 for top, bottom in row_spans}
        tile_widths = {right - left + 1 for left, right in col_spans}
        if len(tile_heights) != 1 or len(tile_widths) != 1:
            raise ValueError("separator_lattice_complete_tiles requires uniform tile spans")

        motif_counts = {}
        for top, bottom in row_spans:
            for left, right in col_spans:
                motif = frozenset(
                    (row - top, col - left)
                    for row in range(top, bottom + 1)
                    for col in range(left, right + 1)
                    if grid[row][col] not in {background_color, separator_color}
                )
                if motif:
                    motif_counts[motif] = motif_counts.get(motif, 0) + 1
        if not motif_counts:
            raise ValueError("separator_lattice_complete_tiles requires at least one non-separator tile motif")
        motif = max(motif_counts, key=lambda item: (len(item), motif_counts[item]))

        output = [row[:] for row in grid]
        for top, bottom in row_spans:
            for left, right in col_spans:
                for local_row, local_col in motif:
                    row = top + local_row
                    col = left + local_col
                    if top <= row <= bottom and left <= col <= right and output[row][col] == background_color:
                        output[row][col] = separator_color
        return output

    if tile_type == "tile_class_rules":
        if not isinstance(classifier_params, dict):
            raise ValueError("tile_class_rules requires classifier_params")
        numeric_parameters = classifier_params.get("numeric_parameters") or {}
        tile_height = classifier_params.get("tile_height", numeric_parameters.get("tile_height"))
        tile_width = classifier_params.get("tile_width", numeric_parameters.get("tile_width"))
        owl_classes = classifier_params.get("owl_classes") or []
        owl_rule_outputs = classifier_params.get("owl_rule_outputs") or []
        if not isinstance(tile_height, int) or tile_height <= 0:
            raise ValueError("tile_class_rules requires positive tile_height")
        if not isinstance(tile_width, int) or tile_width <= 0:
            raise ValueError("tile_class_rules requires positive tile_width")
        if not rows or rows % tile_height != 0 or cols % tile_width != 0:
            raise ValueError("tile_class_rules requires grid dimensions divisible by tile size")
        if not owl_classes:
            raise ValueError("tile_class_rules requires owl_classes")
        if not isinstance(owl_rule_outputs, list) or not owl_rule_outputs:
            raise ValueError("tile_class_rules requires owl_rule_outputs")

        class_concepts = {}
        for owl_class in owl_classes:
            try:
                concept = concept_from_owl_class(owl_class)
            except ValueError:
                continue
            if owl_class in class_concepts and class_concepts[owl_class] != concept:
                raise ValueError("tile_class_rules found conflicting owl classes")
            class_concepts[owl_class] = concept
        if not class_concepts:
            raise ValueError("tile_class_rules requires at least one topology owl_class")

        concept_to_output_color = {}
        for rule_output in owl_rule_outputs:
            if not isinstance(rule_output, dict):
                raise ValueError("tile_class_rules rule outputs must be dicts")
            owl_class = (
                rule_output.get("owl_class")
                or rule_output.get("class")
            )
            if owl_class not in class_concepts:
                raise ValueError("tile_class_rules rule output references unknown owl_class")
            if "output_color" in rule_output:
                color = rule_output["output_color"]
            elif "color" in rule_output:
                color = rule_output["color"]
            else:
                raise ValueError("tile_class_rules rule output requires output_color")
            if not isinstance(color, int):
                raise ValueError("tile_class_rules output_color must be an integer")
            concept = class_concepts[owl_class]
            if concept in concept_to_output_color and concept_to_output_color[concept] != color:
                raise ValueError("tile_class_rules found conflicting rule outputs")
            concept_to_output_color[concept] = color

        output = [[background_color for _ in range(cols)] for _ in range(rows)]
        for top in range(0, rows, tile_height):
            for left in range(0, cols, tile_width):
                tile = [
                    [
                        grid[row][col]
                        for col in range(left, left + tile_width)
                    ]
                    for row in range(top, top + tile_height)
                ]
                concept = classify_binary_tile_concept(tile, background_color=background_color)
                if concept not in concept_to_output_color:
                    raise ValueError("tile_class_rules encountered unknown tile concept")
                color = concept_to_output_color[concept]
                for row in range(top, top + tile_height):
                    for col in range(left, left + tile_width):
                        output[row][col] = color
        return output
    if tile_type == "horizontal_mirror_vertical_palindrome":
        mirrored_rows = [list(reversed(row)) + list(row) for row in grid]
        return (
            [row[:] for row in reversed(mirrored_rows)]
            + [row[:] for row in mirrored_rows]
            + [row[:] for row in reversed(mirrored_rows)]
        )

    if tile_type == "diagonal_slide_self":
        output = [[background_color for _ in range(cols * 2)] for _ in range(rows * 2)]
        for offset in range(max(rows * 2, cols * 2)):
            for row in range(rows):
                for col in range(cols):
                    value = grid[row][col]
                    if (
                        value != background_color
                        and row + offset < rows * 2
                        and col + offset < cols * 2
                    ):
                        output[row + offset][col + offset] = value
        return output

    if tile_type == "complement_tile_x2":
        foreground_colors = {
            value
            for row in grid
            for value in row
            if value != background_color
        }
        if len(foreground_colors) != 1:
            raise ValueError("complement_tile_x2 requires one foreground color")
        fill = next(iter(foreground_colors))
        if not any(value == background_color for row in grid for value in row):
            raise ValueError("complement_tile_x2 requires background cells")
        complement = [
            [fill if value == background_color else background_color for value in row]
            for row in grid
        ]
        return [
            [complement[row % rows][col % cols] for col in range(cols * 2)]
            for row in range(rows * 2)
        ]

    if tile_type == "duplicate_outer_rows_cols":
        if rows < 2 or cols < 2:
            raise ValueError("duplicate_outer_rows_cols requires at least 2x2 input")
        row_indices = [0, *range(rows), rows - 1]
        col_indices = [0, *range(cols), cols - 1]
        return [[grid[row][col] for col in col_indices] for row in row_indices]

    if tile_type in {"rotation_quadrants", "rotation_quadrants_ccw_first"}:
        if rows != cols:
            raise ValueError("rotation_quadrants requires a square grid")
        rot90_cw = [list(row) for row in zip(*reversed(grid))]
        rot90_ccw = [list(row) for row in reversed(list(zip(*grid)))]
        rot180 = [list(reversed(row)) for row in reversed(grid)]
        if tile_type == "rotation_quadrants":
            top = [grid[row][:] + rot90_cw[row] for row in range(rows)]
            bottom = [rot90_ccw[row] + rot180[row] for row in range(rows)]
        else:
            top = [grid[row][:] + rot90_ccw[row] for row in range(rows)]
            bottom = [rot180[row] + rot90_cw[row] for row in range(rows)]
        return top + bottom

    if tile_type == "corner_basis_quadrants_x2":
        if not rows or not cols:
            return []
        base_color = grid[0][0]
        if base_color == background_color:
            raise ValueError("corner_basis_quadrants_x2 requires non-background top-left color")
        normalized = [
            [base_color if value == background_color else value for value in row]
            for row in grid
        ]

        trailing_background_cols = 0
        for col in range(cols - 1, -1, -1):
            if all(grid[row][col] == background_color for row in range(rows)):
                trailing_background_cols += 1
            else:
                break
        trailing_background_rows = 0
        for row in range(rows - 1, -1, -1):
            if all(grid[row][col] == background_color for col in range(cols)):
                trailing_background_rows += 1
            else:
                break

        def shifted_row(row):
            return [
                row[col + trailing_background_cols]
                if col + trailing_background_cols < cols
                else base_color
                for col in range(cols)
            ]

        def shifted_col(col_values):
            return [
                col_values[row + trailing_background_rows]
                if row + trailing_background_rows < rows
                else base_color
                for row in range(rows)
            ]

        top_row = shifted_row(normalized[0])
        left_col = shifted_col([row[0] for row in normalized])
        shifted_matrix = [
            shifted_row(
                normalized[row + trailing_background_rows]
                if row + trailing_background_rows < rows
                else [base_color for _ in range(cols)]
            )
            for row in range(rows)
        ]
        output = []
        for row_index in range(rows):
            output.append(normalized[row_index][:] + top_row[:])
        for row_index in range(rows):
            output.append([left_col[row_index] for _ in range(cols)] + shifted_matrix[row_index][:])
        return output

    if tile_type == "repeat_diagonal_neighbor_fill":
        if fill_color is None or fill_color == background_color:
            raise ValueError("repeat_diagonal_neighbor_fill requires a non-background fill_color")
        if not rows or not cols:
            return []
        if not any(grid[row][col] != background_color for row in range(rows) for col in range(cols)):
            raise ValueError("repeat_diagonal_neighbor_fill requires foreground")
        output = [
            [grid[row % rows][col % cols] for col in range(cols * 2)]
            for row in range(rows * 2)
        ]
        source = [row[:] for row in output]
        for row in range(rows * 2):
            for col in range(cols * 2):
                if source[row][col] != background_color:
                    continue
                if any(
                    0 <= neighbor_row < rows * 2
                    and 0 <= neighbor_col < cols * 2
                    and source[neighbor_row][neighbor_col] != background_color
                    for neighbor_row in (row - 1, row + 1)
                    for neighbor_col in (col - 1, col + 1)
                ):
                    output[row][col] = fill_color
        return output

    if tile_type == "tile_x2_recolor_foreground_columns":
        if fill_color is None:
            raise ValueError("tile_x2_recolor_foreground_columns requires fill_color")
        if not rows or not cols:
            return []
        foreground_cols = {
            col
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        }
        return [
            [
                (
                    fill_color
                    if (
                        grid[row % rows][col % cols] == background_color
                        and (col % cols) in foreground_cols
                    )
                    else grid[row % rows][col % cols]
                )
                for col in range(cols * 2)
            ]
            for row in range(rows * 2)
        ]

    if tile_type == "sparse_diagonal_anchor_tile_x2":
        if fill_color is None:
            raise ValueError("sparse_diagonal_anchor_tile_x2 requires fill_color")
        foreground_colors = {
            value
            for row in grid
            for value in row
            if value != background_color
        }
        if len(foreground_colors) != 1:
            raise ValueError("sparse_diagonal_anchor_tile_x2 requires one foreground color")
        anchor_diagonals = {
            row - col
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        }
        if not anchor_diagonals:
            raise ValueError("sparse_diagonal_anchor_tile_x2 requires foreground anchors")
        return [
            [
                (
                    grid[row // 2][col // 2]
                    if grid[row // 2][col // 2] != background_color
                    else (
                        fill_color
                        if (
                            (row // 2) - (col // 2) in anchor_diagonals
                            and row % 2 == col % 2
                        )
                        else background_color
                    )
                )
                for col in range(cols * 2)
            ]
            for row in range(rows * 2)
        ]

    if tile_type == "vertical_pair_separator_diagonal_copy_x2":
        if fill_color is None:
            raise ValueError("vertical_pair_separator_diagonal_copy_x2 requires fill_color")
        foreground_colors = {
            value
            for row in grid
            for value in row
            if value != background_color
        }
        if len(foreground_colors) != 1:
            raise ValueError("vertical_pair_separator_diagonal_copy_x2 requires one foreground color")
        output = [
            [background_color for _ in range(cols * 2)]
            for _ in range(rows * 2)
        ]
        separator_rows = set()
        for row in range(rows - 2):
            for col in range(cols):
                if (
                    grid[row][col] != background_color
                    and grid[row + 2][col] == grid[row][col]
                ):
                    separator_rows.add(row + 1)
                    separator_rows.add(row + 1 + rows)
        if not separator_rows:
            raise ValueError("vertical_pair_separator_diagonal_copy_x2 requires vertical foreground pairs")
        for row in separator_rows:
            for col in range(cols * 2):
                output[row][col] = fill_color
        for row in range(rows):
            for col in range(cols):
                if grid[row][col] == background_color:
                    continue
                output[row][col] = grid[row][col]
                output[row + rows][col + cols] = grid[row][col]
        return output

    if tile_type == "solid_color_square_separator_lattice_15":
        if rows != cols or not rows:
            raise ValueError("solid_color_square_separator_lattice_15 requires a square input")
        foreground_colors = {
            value
            for row in grid
            for value in row
            if value != background_color
        }
        if len(foreground_colors) != 1:
            raise ValueError("solid_color_square_separator_lattice_15 requires one solid foreground color")
        fill = next(iter(foreground_colors))
        if any(value != fill for row in grid for value in row):
            raise ValueError("solid_color_square_separator_lattice_15 requires a solid square")
        output_size = 15
        separator_indices = {
            index
            for index in range(output_size)
            if index % (rows + 1) == rows
        }
        return [
            [
                fill if row in separator_indices or col in separator_indices else background_color
                for col in range(output_size)
            ]
            for row in range(output_size)
        ]

    if tile_type == "foreground_count_copies_in_background_square":
        if not rows or not cols:
            return []
        foreground_count = sum(
            1
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        )
        background_count = rows * cols - foreground_count
        if foreground_count == 0 or background_count == 0:
            raise ValueError("foreground_count_copies_in_background_square requires both foreground and background")
        output = [
            [background_color for _ in range(cols * background_count)]
            for _ in range(rows * background_count)
        ]
        for block_index in range(foreground_count):
            block_row = block_index // background_count
            block_col = block_index % background_count
            if block_row >= background_count:
                raise ValueError("foreground_count_copies_in_background_square exceeds block capacity")
            for row in range(rows):
                for col in range(cols):
                    output[block_row * rows + row][block_col * cols + col] = grid[row][col]
        return output

    if tile_type == "edge_color_border_zero_corners":
        if not rows or not cols:
            return []
        output = [
            [background_color for _ in range(cols + 2)]
            for _ in range(rows + 2)
        ]
        for row in range(rows):
            output[row + 1][0] = grid[row][0]
            output[row + 1][cols + 1] = grid[row][cols - 1]
            for col in range(cols):
                output[row + 1][col + 1] = grid[row][col]
        for col in range(cols):
            output[0][col + 1] = grid[0][col]
            output[rows + 1][col + 1] = grid[rows - 1][col]
        return output

    if tile_type == "foreground_bbox_repeat_x2":
        foreground = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if not foreground:
            raise ValueError("foreground_bbox_repeat_x2 requires foreground pixels")
        min_row = min(row for row, _ in foreground)
        max_row = max(row for row, _ in foreground)
        min_col = min(col for _, col in foreground)
        max_col = max(col for _, col in foreground)
        bbox = [
            [grid[row][col] for col in range(min_col, max_col + 1)]
            for row in range(min_row, max_row + 1)
        ]
        return [row + row[:] for row in bbox]

    if tile_type == "split_color_grid_mask_stamp":
        if not rows or not cols:
            raise ValueError("split_color_grid_mask_stamp requires a non-empty grid")

        mask_colors = (
            [fill_color]
            if fill_color is not None
            else sorted({
                grid[row][col]
                for row in range(rows)
                for col in range(cols)
                if grid[row][col] != background_color
            })
        )

        def stamped(color_grid, mask, mask_color):
            mask_height = len(mask)
            mask_width = len(mask[0]) if mask_height else 0
            color_height = len(color_grid)
            color_width = len(color_grid[0]) if color_height else 0
            if not mask_height or not mask_width or not color_height or not color_width:
                raise ValueError("split_color_grid_mask_stamp found an empty half")
            if any(value not in (background_color, mask_color) for row in mask for value in row):
                raise ValueError("split_color_grid_mask_stamp mask half is not binary")
            if not any(value == mask_color for row in mask for value in row):
                raise ValueError("split_color_grid_mask_stamp mask half has no mask pixels")
            if any(value == mask_color for row in color_grid for value in row):
                raise ValueError("split_color_grid_mask_stamp color half contains mask color")

            output = [
                [background_color for _ in range(color_width * mask_width)]
                for _ in range(color_height * mask_height)
            ]
            changed = False
            for color_row in range(color_height):
                for color_col in range(color_width):
                    cell_color = color_grid[color_row][color_col]
                    if cell_color == background_color:
                        continue
                    for mask_row in range(mask_height):
                        for mask_col in range(mask_width):
                            if mask[mask_row][mask_col] != mask_color:
                                continue
                            output[color_row * mask_height + mask_row][
                                color_col * mask_width + mask_col
                            ] = cell_color
                            changed = True
            if not changed:
                raise ValueError("split_color_grid_mask_stamp produced no foreground")
            return output

        candidates = []
        for mask_color in mask_colors:
            if mask_color in (None, background_color):
                continue
            if cols % 2 == 0:
                split_col = cols // 2
                left = [row[:split_col] for row in grid]
                right = [row[split_col:] for row in grid]
                for color_grid, mask in ((left, right), (right, left)):
                    try:
                        candidates.append(stamped(color_grid, mask, mask_color))
                    except ValueError:
                        pass
            if rows % 2 == 0:
                split_row = rows // 2
                top = [row[:] for row in grid[:split_row]]
                bottom = [row[:] for row in grid[split_row:]]
                for color_grid, mask in ((top, bottom), (bottom, top)):
                    try:
                        candidates.append(stamped(color_grid, mask, mask_color))
                    except ValueError:
                        pass

        unique = []
        seen = set()
        for candidate in candidates:
            key = tuple(tuple(row) for row in candidate)
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        if len(unique) != 1:
            raise ValueError("split_color_grid_mask_stamp requires a unique split/mask interpretation")
        return unique[0]

    if tile_type == "macro_mask_self_substitution":
        foreground = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if not foreground:
            raise ValueError("macro_mask_self_substitution requires foreground")
        foreground_colors = {value for _, _, value in foreground}
        if fill_color is None:
            if len(foreground_colors) != 1:
                raise ValueError("macro_mask_self_substitution requires fill_color for multi-color input")
            fill_color = next(iter(foreground_colors))

        min_row = min(row for row, _, _ in foreground)
        max_row = max(row for row, _, _ in foreground)
        min_col = min(col for _, col, _ in foreground)
        max_col = max(col for _, col, _ in foreground)
        height = max_row - min_row + 1
        width = max_col - min_col + 1
        macro_size = 3
        if height % macro_size != 0 or width % macro_size != 0:
            raise ValueError("macro_mask_self_substitution requires a 3x3 macro bbox")
        cell_height = height // macro_size
        cell_width = width // macro_size
        if cell_height == 0 or cell_width == 0:
            raise ValueError("macro_mask_self_substitution has empty macro cells")

        mask = []
        for macro_row in range(macro_size):
            mask_row = []
            for macro_col in range(macro_size):
                values = [
                    grid[row][col]
                    for row in range(min_row + macro_row * cell_height, min_row + (macro_row + 1) * cell_height)
                    for col in range(min_col + macro_col * cell_width, min_col + (macro_col + 1) * cell_width)
                ]
                occupied = any(value != background_color for value in values)
                if occupied and any(value not in (background_color, fill_color) for value in values):
                    raise ValueError("macro_mask_self_substitution found unexpected cell color")
                mask_row.append(occupied)
            mask.append(mask_row)

        output = [[background_color for _ in range(macro_size * macro_size)] for _ in range(macro_size * macro_size)]
        for macro_row in range(macro_size):
            for macro_col in range(macro_size):
                if not mask[macro_row][macro_col]:
                    continue
                for mask_row in range(macro_size):
                    for mask_col in range(macro_size):
                        if mask[mask_row][mask_col]:
                            output[macro_row * macro_size + mask_row][macro_col * macro_size + mask_col] = fill_color
        return output

    if tile_type == "macro_mask_complement_substitution":
        foreground = [
            (row, col, grid[row][col])
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != background_color
        ]
        if not foreground:
            raise ValueError("macro_mask_complement_substitution requires foreground")
        foreground_colors = {value for _, _, value in foreground}
        if len(foreground_colors) != 1:
            raise ValueError("macro_mask_complement_substitution requires one foreground color")
        fill = next(iter(foreground_colors))
        if not any(grid[row][col] == background_color for row in range(rows) for col in range(cols)):
            raise ValueError("macro_mask_complement_substitution requires background cells")

        complement = [
            [fill if value == background_color else background_color for value in row]
            for row in grid
        ]
        output = [
            [background_color for _ in range(cols * cols)]
            for _ in range(rows * rows)
        ]
        for macro_row in range(rows):
            for macro_col in range(cols):
                if grid[macro_row][macro_col] == background_color:
                    continue
                for row in range(rows):
                    for col in range(cols):
                        output[macro_row * rows + row][macro_col * cols + col] = complement[row][col]
        return output

    if tile_type == "copy_top_band_to_bottom_reverse":
        if not rows:
            return []
        band_end = 0
        while band_end < rows and any(
            grid[band_end][col] != background_color
            for col in range(cols)
        ):
            band_end += 1
        if band_end == 0 or band_end * 2 > rows:
            raise ValueError("copy_top_band_to_bottom_reverse requires a top foreground band")
        if any(
            grid[row][col] != background_color
            for row in range(band_end, rows - band_end)
            for col in range(cols)
        ):
            raise ValueError("copy_top_band_to_bottom_reverse requires blank middle rows")
        output = [row[:] for row in grid]
        top_band = [row[:] for row in grid[:band_end]]
        output[rows - band_end:] = [row[:] for row in reversed(top_band)]
        return output

    if tile_type == "separator_region_repeat":
        if not rows or not cols:
            raise ValueError("separator_region_repeat requires a non-empty grid")
        full_rows_by_color = {}
        for row in range(rows):
            row_values = set(grid[row])
            if len(row_values) == 1:
                value = next(iter(row_values))
                if value != background_color:
                    full_rows_by_color.setdefault(value, []).append(row)
        full_cols_by_color = {}
        for col in range(cols):
            col_values = {grid[row][col] for row in range(rows)}
            if len(col_values) == 1:
                value = next(iter(col_values))
                if value != background_color:
                    full_cols_by_color.setdefault(value, []).append(col)

        separator_candidates = sorted(set(full_rows_by_color) | set(full_cols_by_color))
        outputs = []

        def spans(separators, limit):
            bounds = [-1] + sorted(separators) + [limit]
            return [
                (bounds[index] + 1, bounds[index + 1])
                for index in range(len(bounds) - 1)
                if bounds[index] + 1 < bounds[index + 1]
            ]

        for separator_color in separator_candidates:
            separator_rows = full_rows_by_color.get(separator_color, [])
            separator_cols = full_cols_by_color.get(separator_color, [])
            if not separator_rows and not separator_cols:
                continue
            row_spans = spans(separator_rows, rows)
            col_spans = spans(separator_cols, cols)
            if not row_spans or not col_spans:
                continue
            region_shapes = {
                (row_end - row_start, col_end - col_start)
                for row_start, row_end in row_spans
                for col_start, col_end in col_spans
            }
            if len(region_shapes) != 1:
                continue

            non_empty_regions = []
            for row_start, row_end in row_spans:
                for col_start, col_end in col_spans:
                    region = [
                        grid[row][col_start:col_end]
                        for row in range(row_start, row_end)
                    ]
                    if any(
                        value not in (background_color, separator_color)
                        for region_row in region
                        for value in region_row
                    ):
                        non_empty_regions.append(region)
            unique_regions = []
            seen_regions = set()
            for region in non_empty_regions:
                key = tuple(tuple(row) for row in region)
                if key in seen_regions:
                    continue
                seen_regions.add(key)
                unique_regions.append(region)
            if len(unique_regions) != 1:
                continue
            source_region = unique_regions[0]
            output = [row[:] for row in grid]
            for row_start, row_end in row_spans:
                for col_start, col_end in col_spans:
                    for delta_row, source_row in enumerate(source_region):
                        for delta_col, value in enumerate(source_row):
                            output[row_start + delta_row][col_start + delta_col] = value
            outputs.append(output)

        unique_outputs = []
        seen_outputs = set()
        for output in outputs:
            key = tuple(tuple(row) for row in output)
            if key in seen_outputs:
                continue
            seen_outputs.add(key)
            unique_outputs.append(output)
        if len(unique_outputs) != 1:
            raise ValueError("separator_region_repeat requires a unique separator/source region")
        return unique_outputs[0]

    if tile_type == "periodic_cross_from_seed_sequence":
        if not rows or not cols:
            raise ValueError("periodic_cross_from_seed_sequence requires a non-empty grid")

        row_runs = []
        for row in range(rows):
            col = 0
            while col < cols:
                if grid[row][col] == background_color:
                    col += 1
                    continue
                start_col = col
                values = []
                while col < cols and grid[row][col] != background_color:
                    values.append(grid[row][col])
                    col += 1
                if len(values) >= 2:
                    row_runs.append((len(values), row, start_col, values))
        if not row_runs:
            raise ValueError("periodic_cross_from_seed_sequence requires a foreground row run")
        max_len = max(length for length, _, _, _ in row_runs)
        seed_runs = [run for run in row_runs if run[0] == max_len]
        if len(seed_runs) != 1:
            raise ValueError("periodic_cross_from_seed_sequence requires a unique longest row run")
        _, seed_row, start_col, sequence = seed_runs[0]
        period = len(sequence)

        anchor_candidates = []
        for anchor_index in range(period):
            anchor_col = start_col + anchor_index
            outside_cells = [
                (row, grid[row][anchor_col])
                for row in range(rows)
                if row != seed_row and grid[row][anchor_col] != background_color
            ]
            if not outside_cells:
                continue
            vertical_sequences = [sequence]
            reversed_sequence = list(reversed(sequence))
            if reversed_sequence != sequence:
                vertical_sequences.append(reversed_sequence)
            for vertical_sequence in vertical_sequences:
                vertical_indices = [
                    index
                    for index, value in enumerate(vertical_sequence)
                    if value == sequence[anchor_index]
                ]
                for vertical_index in vertical_indices:
                    if all(
                        value == vertical_sequence[(row - seed_row + vertical_index) % period]
                        for row, value in outside_cells
                    ):
                        anchor_candidates.append((len(outside_cells), anchor_col, vertical_sequence, vertical_index))
        if len(anchor_candidates) != 1:
            max_support = max((support for support, _, _, _ in anchor_candidates), default=0)
            anchor_candidates = [
                candidate for candidate in anchor_candidates if candidate[0] == max_support
            ]
        if len(anchor_candidates) != 1:
            raise ValueError("periodic_cross_from_seed_sequence requires a unique vertical anchor")
        _, anchor_col, vertical_sequence, vertical_index = anchor_candidates[0]

        output = [[background_color for _ in range(cols)] for _ in range(rows)]
        for col in range(cols):
            output[seed_row][col] = sequence[(col - start_col) % period]
        for row in range(rows):
            output[row][anchor_col] = vertical_sequence[(row - seed_row + vertical_index) % period]
        return output

    raise ValueError(f"Unsupported tile type: {tile_type}")




import copy


class _UnionFind:
    def __init__(self, size):
        self.parent = list(range(size))

    def find(self, item):
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left, right):
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _rot90_orbit(pixel, center2, rows, cols):
    """
    Return the three non-identity 90-degree rotations of a pixel.

    Coordinates stay doubled while rotating so integer and half-cell centers are
    both represented exactly.
    """
    row2 = 2 * pixel[0] - center2[0]
    col2 = 2 * pixel[1] - center2[1]
    orbit = []
    for _ in range(3):
        row2, col2 = col2, -row2
        rotated_row2 = center2[0] + row2
        rotated_col2 = center2[1] + col2
        if rotated_row2 % 2 or rotated_col2 % 2:
            return []
        rotated = (rotated_row2 // 2, rotated_col2 // 2)
        if not (0 <= rotated[0] < rows and 0 <= rotated[1] < cols):
            return []
        orbit.append(rotated)
    return orbit


def _candidate_centers(rows, cols):
    return [
        (row2, col2)
        for row2 in range(2 * rows - 1)
        for col2 in range(2 * cols - 1)
    ]


def _rot90_missing_orbit_pixels(grid, source_color, background_color, center2):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    missing = []
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] != background_color:
                continue
            orbit = _rot90_orbit((row, col), center2, rows, cols)
            if orbit and all(grid[r][c] == source_color for r, c in orbit):
                missing.append((row, col))
    return missing


def _rot90_color_orbit_completion(grid, background_color=0, center_mode="best"):
    """
    Close 90-degree rotation orbits for each color around an inferred center.

    A center is accepted only when every observed non-background orbit contains
    at most one color.  Every background cell in that orbit is then painted with
    the orbit color.  The selected center uses an MDL tie-breaker: smallest
    completion first, then more existing support, then earlier center only as a
    deterministic final tie-breaker.
    """
    if center_mode != "best":
        raise ValueError(f"Unsupported center mode: {center_mode}")
    if not grid:
        return copy.deepcopy(grid)

    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("rot90_color_orbit_completion requires a rectangular grid")

    def orbit_for(pixel, center2):
        orbit = [pixel]
        rotated = _rot90_orbit(pixel, center2, rows, cols)
        if not rotated:
            return None
        for point in rotated:
            if point not in orbit:
                orbit.append(point)
        return tuple(sorted(orbit))

    best = None
    for center2 in _candidate_centers(rows, cols):
        orbit_map = {}
        valid = True
        support = 0
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == background_color:
                    continue
                orbit = orbit_for((row, col), center2)
                if orbit is None:
                    valid = False
                    break
                orbit_map.setdefault(orbit, set()).add(value)
                support += 1
            if not valid:
                break
        if not valid:
            continue

        transformed = copy.deepcopy(grid)
        additions = 0
        for orbit, colors in orbit_map.items():
            if len(colors) != 1:
                valid = False
                break
            orbit_color = next(iter(colors))
            for row, col in orbit:
                value = transformed[row][col]
                if value == background_color:
                    transformed[row][col] = orbit_color
                    additions += 1
                elif value != orbit_color:
                    valid = False
                    break
            if not valid:
                break
        if not valid or additions == 0:
            continue

        candidate_key = (additions, -support, center2[0], center2[1])
        if best is None or candidate_key < best[0]:
            best = (candidate_key, transformed)

    if best is None:
        raise ValueError("No supported rot90 color orbit completion found")
    return best[1]


def _normalize_unknown_colors(occluder_color=None, occluder_colors=None):
    if occluder_colors is not None:
        return set(occluder_colors)
    if occluder_color is not None:
        return {occluder_color}
    return set()


def _lines_are_compatible(left, right, unknown_colors, min_support=2):
    compared = 0
    for left_value, right_value in zip(left, right):
        if left_value in unknown_colors or right_value in unknown_colors:
            continue
        compared += 1
        if left_value != right_value:
            return False, compared
    return compared >= min_support, compared


def _infer_duplicate_line_pairs(lines, unknown_colors):
    """
    Infer exact duplicate line pairs while ignoring occluder cells.

    A pair is accepted only when it is the unique reciprocal compatible match.
    This keeps the repair conservative on rich textures while still recovering
    repeated row/column structure from partially masked canvases.
    """
    compatible_matches = []
    for index, line in enumerate(lines):
        matches = []
        for other_index, other_line in enumerate(lines):
            if index == other_index:
                continue
            compatible, compared = _lines_are_compatible(
                line,
                other_line,
                unknown_colors,
            )
            if compatible:
                matches.append((other_index, compared))
        compatible_matches.append(matches)

    pairs = []
    for index, matches in enumerate(compatible_matches):
        if len(matches) != 1:
            continue
        other_index, _ = matches[0]
        if index >= other_index:
            continue
        reciprocal_matches = compatible_matches[other_index]
        if len(reciprocal_matches) != 1:
            continue
        reciprocal_index, _ = reciprocal_matches[0]
        if reciprocal_index == index:
            pairs.append((index, other_index))
    return pairs


def _diagonal_canvas_repair(
    grid,
    mirror_axis="DIAGONAL_LEFT",
    duplicate_mode="infer_rows_cols",
    occluder_color=None,
    occluder_colors=None,
):
    """
    Repair masked cells on a symmetric textured canvas.

    The value of an occluded cell may be recoverable from:
    - the diagonal-reflection partner, and
    - duplicate row/column partners inferred while ignoring occluder cells.

    The transform only fills an orbit when all visible donor cells agree.
    """
    if not grid:
        return copy.deepcopy(grid)
    if mirror_axis != "DIAGONAL_LEFT":
        raise ValueError(f"Unsupported canvas repair mirror axis: {mirror_axis}")
    if duplicate_mode != "infer_rows_cols":
        raise ValueError(f"Unsupported duplicate mode: {duplicate_mode}")

    rows = len(grid)
    cols = len(grid[0])
    if rows != cols:
        raise ValueError("Diagonal canvas repair requires a square grid")

    unknown_colors = _normalize_unknown_colors(
        occluder_color=occluder_color,
        occluder_colors=occluder_colors,
    )
    if not unknown_colors:
        raise ValueError("Diagonal canvas repair requires at least one occluder color")

    row_pairs = _infer_duplicate_line_pairs(grid, unknown_colors)
    columns = [list(column) for column in zip(*grid)]
    column_pairs = _infer_duplicate_line_pairs(columns, unknown_colors)

    union_find = _UnionFind(rows * cols)

    def index(row, col):
        return row * cols + col

    # The canvas itself is symmetric across the main diagonal.
    for row in range(rows):
        for col in range(cols):
            union_find.union(index(row, col), index(col, row))

    # Repeated canvas lines provide additional donors when both diagonal
    # partners are masked.
    for first_row, second_row in row_pairs:
        for col in range(cols):
            union_find.union(index(first_row, col), index(second_row, col))
    for first_col, second_col in column_pairs:
        for row in range(rows):
            union_find.union(index(row, first_col), index(row, second_col))

    orbits = {}
    for row in range(rows):
        for col in range(cols):
            orbits.setdefault(union_find.find(index(row, col)), []).append((row, col))

    transformed_grid = copy.deepcopy(grid)
    for orbit in orbits.values():
        donors = {
            grid[row][col]
            for row, col in orbit
            if grid[row][col] not in unknown_colors
        }
        if len(donors) != 1:
            continue
        donor = next(iter(donors))
        for row, col in orbit:
            if transformed_grid[row][col] in unknown_colors:
                transformed_grid[row][col] = donor
    return transformed_grid


def _periodic_canvas_repair(
    grid,
    occluder_color=None,
    occluder_colors=None,
    period_mode="minimal_2d",
    max_period=12,
):
    """
    Repair holes in a repeated 2D canvas.

    Unknown / occluder cells are ignored while inferring the smallest repeating
    row/column period. A candidate period is accepted only when every residue
    class has at least one visible donor, which keeps the transform from
    hallucinating unsupported pattern cells.
    """
    if not grid:
        return copy.deepcopy(grid)
    if period_mode != "minimal_2d":
        raise ValueError(f"Unsupported periodic canvas mode: {period_mode}")

    unknown_colors = _normalize_unknown_colors(
        occluder_color=occluder_color,
        occluder_colors=occluder_colors,
    )
    if not unknown_colors:
        raise ValueError("Periodic canvas repair requires at least one occluder color")

    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Periodic canvas repair requires a rectangular grid")

    max_row_period = min(rows, int(max_period))
    max_col_period = min(cols, int(max_period))
    best = None

    for row_period in range(1, max_row_period + 1):
        for col_period in range(1, max_col_period + 1):
            pattern = {}
            visible_support = 0
            compatible = True

            for row in range(rows):
                for col in range(cols):
                    value = grid[row][col]
                    if value in unknown_colors:
                        continue
                    visible_support += 1
                    key = (row % row_period, col % col_period)
                    if key in pattern and pattern[key] != value:
                        compatible = False
                        break
                    pattern[key] = value
                if not compatible:
                    break

            if not compatible:
                continue
            if len(pattern) != row_period * col_period:
                continue

            # MDL preference: smallest tile first; then squarer/shorter periods;
            # then more visible support only as a deterministic final tie-break.
            candidate_key = (
                row_period * col_period,
                row_period + col_period,
                abs(row_period - col_period),
                -visible_support,
            )
            if best is None or candidate_key < best[0]:
                best = (candidate_key, row_period, col_period, pattern)

    if best is None:
        raise ValueError("No supported periodic canvas found")

    _, row_period, col_period, pattern = best
    transformed_grid = copy.deepcopy(grid)
    for row in range(rows):
        for col in range(cols):
            if transformed_grid[row][col] in unknown_colors:
                transformed_grid[row][col] = pattern[(row % row_period, col % col_period)]
    return transformed_grid


def _infer_periodic_pattern(
    grid,
    unknown_colors=None,
    max_period=12,
):
    """Infer the smallest fully-supported 2D pattern from visible cells."""
    unknown_colors = set(unknown_colors or [])
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    max_row_period = min(rows, int(max_period))
    max_col_period = min(cols, int(max_period))
    best = None

    for row_period in range(1, max_row_period + 1):
        for col_period in range(1, max_col_period + 1):
            pattern = {}
            visible_support = 0
            compatible = True
            for row in range(rows):
                for col in range(cols):
                    value = grid[row][col]
                    if value in unknown_colors:
                        continue
                    visible_support += 1
                    key = (row % row_period, col % col_period)
                    if key in pattern and pattern[key] != value:
                        compatible = False
                        break
                    pattern[key] = value
                if not compatible:
                    break
            if not compatible:
                continue
            if len(pattern) != row_period * col_period:
                continue
            candidate_key = (
                row_period * col_period,
                row_period + col_period,
                abs(row_period - col_period),
                -visible_support,
            )
            if best is None or candidate_key < best[0]:
                best = (candidate_key, row_period, col_period, pattern)
    if best is None:
        return None
    _, row_period, col_period, pattern = best
    return row_period, col_period, pattern


def _periodic_visible_synthesis(
    grid,
    occluder_color=None,
    occluder_colors=None,
    unknown_mode="auto_single",
    out_shift_row=0,
    out_shift_col=1,
    max_period=12,
):
    """
    Synthesize a whole canvas from visible periodic evidence.

    Unlike `periodic_canvas_repair`, this writes the entire grid and may shift
    the learned phase. It is intended for examples where an incomplete visible
    patch tells us the wallpaper, while a marked color denotes non-canvas area.
    """
    if not grid:
        return copy.deepcopy(grid)

    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Periodic visible synthesis requires a rectangular grid")

    if unknown_mode not in {"auto_single", "given"}:
        raise ValueError(f"Unsupported unknown mode: {unknown_mode}")

    if unknown_mode == "given":
        unknown_candidates = [
            _normalize_unknown_colors(
                occluder_color=occluder_color,
                occluder_colors=occluder_colors,
            )
        ]
    else:
        colors = sorted({value for row in grid for value in row})
        unknown_candidates = [{color} for color in colors]

    best = None
    for unknowns in unknown_candidates:
        if not unknowns:
            continue
        inferred = _infer_periodic_pattern(
            grid,
            unknown_colors=unknowns,
            max_period=max_period,
        )
        if inferred is None:
            continue
        row_period, col_period, pattern = inferred
        unknown_area = sum(
            1
            for row in grid
            for value in row
            if value in unknowns
        )
        if unknown_area == 0:
            continue
        candidate_key = (
            row_period * col_period,
            row_period + col_period,
            -unknown_area,
            tuple(sorted(unknowns)),
        )
        if best is None or candidate_key < best[0]:
            best = (candidate_key, row_period, col_period, pattern)

    if best is None:
        raise ValueError("No visible periodic synthesis pattern found")

    _, row_period, col_period, pattern = best
    return [
        [
            pattern[
                (
                    (row + int(out_shift_row)) % row_period,
                    (col + int(out_shift_col)) % col_period,
                )
            ]
            for col in range(cols)
        ]
        for row in range(rows)
    ]


def _bounce_index(start, velocity, steps, width):
    if width <= 1:
        return 0
    period = 2 * (width - 1)
    unfolded = (start + velocity * steps) % period
    return unfolded if unfolded < width else period - unfolded


def _bouncing_diagonal_seed(
    grid,
    source_color,
    fill_color,
    direction="up_right",
):
    """
    Draw a one-pixel-wide diagonal wave from a seed, reflecting at side walls.
    """
    if source_color is None or fill_color is None:
        raise ValueError("Bouncing diagonal synthesis requires source_color and fill_color")
    if not grid:
        return copy.deepcopy(grid)

    rows = len(grid)
    cols = len(grid[0])
    seed_pixels = [
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if grid[row][col] == source_color
    ]
    if len(seed_pixels) != 1:
        raise ValueError("Bouncing diagonal synthesis requires exactly one seed pixel")
    seed_row, seed_col = seed_pixels[0]

    directions = {
        "up_right": (-1, 1),
        "up_left": (-1, -1),
        "down_right": (1, 1),
        "down_left": (1, -1),
    }
    if direction not in directions:
        raise ValueError(f"Unsupported bouncing direction: {direction}")
    delta_row, delta_col = directions[direction]

    transformed_grid = [
        [fill_color for _ in range(cols)]
        for _ in range(rows)
    ]
    for row in range(rows):
        if delta_row == -1:
            steps = seed_row - row
        else:
            steps = row - seed_row
        col = _bounce_index(seed_col, delta_col, steps, cols)
        transformed_grid[row][col] = source_color
    return transformed_grid


def _checker_from_row_colors(grid):
    """
    Make a two-color checkerboard from two uniform input rows.
    """
    if not grid:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Checker synthesis requires a rectangular grid")
    row_colors = []
    for row in grid:
        colors = set(row)
        if len(colors) != 1:
            raise ValueError("Checker synthesis requires uniform input rows")
        color = next(iter(colors))
        if color not in row_colors:
            row_colors.append(color)
    if len(row_colors) != 2:
        raise ValueError("Checker synthesis requires exactly two row colors")
    return [
        [row_colors[(row + col) % 2] for col in range(cols)]
        for row in range(rows)
    ]


def _minimal_period(sequence):
    for period in range(1, len(sequence) + 1):
        if all(value == sequence[index % period] for index, value in enumerate(sequence)):
            return sequence[:period]
    return list(sequence)


def _periodic_extend_x(grid, output_scale=2):
    """Extend every row horizontally by continuing its shortest period."""
    if not grid:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Periodic extension requires a rectangular grid")
    output_cols = cols * int(output_scale)
    transformed_grid = []
    for row in grid:
        period = _minimal_period(row)
        transformed_grid.append([
            period[col % len(period)]
            for col in range(output_cols)
        ])
    return transformed_grid


def _row_prefix_periodic_fill(grid, output_width=0, background_color=0):
    """
    Fill trailing background cells by continuing each row's visible prefix.

    The known evidence for a row is the span from column zero through the last
    non-background cell.  Background cells inside that span remain real pattern
    evidence; only the suffix after the last foreground cell is treated as
    unknown canvas to be completed.
    """
    if not grid:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Row prefix periodic fill requires a rectangular grid")

    output_width = int(output_width or cols)
    if output_width < cols:
        raise ValueError("Row prefix periodic fill cannot shrink width")

    transformed_grid = []
    for row in grid:
        foreground_cols = [
            col
            for col, value in enumerate(row)
            if value != background_color
        ]
        if not foreground_cols:
            transformed_grid.append([background_color for _ in range(output_width)])
            continue

        evidence_len = max(foreground_cols) + 1
        evidence = row[:evidence_len]
        period = None
        for period_len in range(1, evidence_len + 1):
            candidate = evidence[:period_len]
            if all(
                value == candidate[index % period_len]
                for index, value in enumerate(evidence)
            ):
                period = candidate
                break
        if period is None:
            raise ValueError("No row-prefix period found")

        transformed_grid.append([
            period[col % len(period)]
            for col in range(output_width)
        ])
    return transformed_grid


def _minimal_period_length(sequence):
    for period in range(1, len(sequence) + 1):
        if all(value == sequence[index % period] for index, value in enumerate(sequence)):
            return period
    return len(sequence)


def _row_foreground_signature(row, background_color=0):
    cells = [
        (col, value)
        for col, value in enumerate(row)
        if value != background_color
    ]
    if not cells:
        return (), 0
    min_col = min(col for col, _ in cells)
    return tuple((col - min_col, value) for col, value in cells), min_col


def _infer_vertical_signature_period(row_states):
    signatures = [signature for signature, _ in row_states]
    for period in range(1, len(row_states) + 1):
        if not all(
            signature == signatures[index % period]
            for index, signature in enumerate(signatures)
        ):
            continue

        residue_deltas = {}
        stable = True
        for residue in range(period):
            observed = [
                min_col
                for row_index, (_, min_col) in enumerate(row_states)
                if row_index % period == residue
            ]
            if len(observed) < 2:
                residue_deltas[residue] = 0
                continue
            diffs = [
                right - left
                for left, right in zip(observed, observed[1:])
            ]
            if len(set(diffs)) != 1:
                stable = False
                break
            residue_deltas[residue] = diffs[0]
        if stable:
            return period, residue_deltas
    raise ValueError("No stable row-shape period for vertical extension")


def _periodic_extend_y(
    grid,
    output_height=0,
    output_width=0,
    output_scale=2,
    background_color=0,
):
    """
    Extend rows downward by repeating the shortest row-shape period.

    Rows are compared by foreground shape after translating each row to its
    leftmost foreground cell.  For each residue class in the row period, a
    stable horizontal drift is inferred from repeated observations.  This
    captures both exact row repetition and diagonal "line motif" continuation.
    """
    if not grid:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Periodic vertical extension requires a rectangular grid")

    output_height = int(output_height or rows * int(output_scale))
    output_width = int(output_width or cols)
    if output_height < rows:
        raise ValueError("Periodic vertical extension cannot shrink height")
    if output_width <= 0:
        raise ValueError("Periodic vertical extension requires positive output width")

    row_states = [
        _row_foreground_signature(row, background_color=background_color)
        for row in grid
    ]
    if not any(signature for signature, _ in row_states):
        raise ValueError("Periodic vertical extension requires foreground evidence")

    period, residue_deltas = _infer_vertical_signature_period(row_states)

    transformed_grid = [
        [background_color for _ in range(output_width)]
        for _ in range(output_height)
    ]
    for row in range(output_height):
        residue = row % period
        signature, base_min_col = row_states[residue]
        drift_steps = row // period
        min_col = base_min_col + residue_deltas[residue] * drift_steps
        for offset, value in signature:
            col = min_col + offset
            if 0 <= col < output_width:
                transformed_grid[row][col] = value
    return transformed_grid


def _periodic_extend_y_recolor(
    grid,
    output_height=0,
    output_width=0,
    output_scale=2,
    background_color=0,
    fill_color=None,
):
    if fill_color is None:
        raise ValueError("periodic_extend_y_recolor requires fill_color")
    extended = _periodic_extend_y(
        grid,
        output_height=output_height,
        output_width=output_width,
        output_scale=output_scale,
        background_color=background_color,
    )
    return [
        [
            fill_color if value != background_color else background_color
            for value in row
        ]
        for row in extended
    ]


def _row_prefix_staircase_y(
    grid,
    output_height=0,
    output_width=0,
    background_color=0,
):
    """
    Expand a single leading color prefix downward as a right-growing staircase.

    The input is one row containing a contiguous foreground prefix followed by
    background. Each synthesized row extends that prefix by one cell.
    """
    if not grid or not grid[0]:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if rows != 1:
        raise ValueError("row_prefix_staircase_y requires a single input row")
    if any(len(row) != cols for row in grid):
        raise ValueError("row_prefix_staircase_y requires a rectangular grid")

    output_width = int(output_width or cols)
    output_height = int(output_height or (cols // 2))
    if output_width < cols:
        raise ValueError("row_prefix_staircase_y cannot shrink width")
    if output_height <= 0:
        raise ValueError("row_prefix_staircase_y requires positive output height")

    row = grid[0]
    prefix_color = row[0]
    if prefix_color == background_color:
        raise ValueError("row_prefix_staircase_y requires a foreground prefix at column zero")

    prefix_len = 0
    while prefix_len < cols and row[prefix_len] == prefix_color:
        prefix_len += 1
    if any(value != background_color for value in row[prefix_len:]):
        raise ValueError("row_prefix_staircase_y requires only background after the prefix")

    output = []
    for row_index in range(output_height):
        fill_len = min(output_width, prefix_len + row_index)
        output.append([
            prefix_color if col < fill_len else background_color
            for col in range(output_width)
        ])
    return output


def _row_token_diagonal_slide(
    grid,
    background_color=0,
):
    """
    Slide a one-row token down-left across a square canvas.

    The canvas side is input_width * non-background-count.  Row zero contains
    only the token's first cell at the far right; each next row shifts the full
    token one cell left, clipping outside the canvas.
    """
    if not grid or not grid[0]:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if rows != 1:
        raise ValueError("row_token_diagonal_slide requires a single input row")
    if any(len(row) != cols for row in grid):
        raise ValueError("row_token_diagonal_slide requires a rectangular grid")

    token = list(grid[0])
    foreground_count = sum(value != background_color for value in token)
    if foreground_count == 0:
        raise ValueError("row_token_diagonal_slide requires foreground cells")
    output_size = cols * foreground_count
    output = [
        [background_color for _ in range(output_size)]
        for _ in range(output_size)
    ]
    for row_index in range(output_size):
        start_col = output_size - 1 - row_index
        for offset, value in enumerate(token):
            col = start_col + offset
            if 0 <= col < output_size:
                output[row_index][col] = value
    return output


def _vertical_edge_palindrome_repeat(grid, background_color=0):
    """
    Repeat a vertical row path top->bottom->top without duplicating endpoints.

    For an input with rows [A, ..., Z], the period is
    rows + reversed(rows[1:-1]), and the output is two full periods plus the
    first row.  This gives height 4 * input_height - 3.
    """
    if not grid:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("vertical_edge_palindrome_repeat requires a rectangular grid")
    if rows < 2:
        raise ValueError("vertical_edge_palindrome_repeat requires at least two rows")
    period = [row[:] for row in grid] + [row[:] for row in reversed(grid[1:-1])]
    return [row[:] for row in period + period + [grid[0][:]]]


def _foreground_bbox(grid, background_color):
    pixels = [
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value != background_color
    ]
    if not pixels:
        raise ValueError("No foreground pattern found")
    min_row = min(row for row, _ in pixels)
    max_row = max(row for row, _ in pixels)
    min_col = min(col for _, col in pixels)
    max_col = max(col for _, col in pixels)
    return min_row, max_row, min_col, max_col


def _tile_by_self_mask(
    grid,
    selector_mode="nonzero",
    selector_color=None,
    tile_source="grid",
    background_color=0,
):
    """
    Tile a pattern into macro-cells selected by the pattern's own mask.

    - tile_source="grid": the whole input grid is the tile and selector.
      Output size is input_height^2 x input_width^2.
    - tile_source="object_bbox": the foreground bounding box is the tile.
      The containing image is treated as a macro-grid of bbox-sized cells.
    """
    if not grid:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Self-mask tiling requires a rectangular grid")

    if tile_source == "grid":
        tile = copy.deepcopy(grid)
        selector_grid = grid
        tile_rows, tile_cols = rows, cols
        macro_rows, macro_cols = rows, cols
        output_rows, output_cols = rows * rows, cols * cols
    elif tile_source == "object_bbox":
        min_row, max_row, min_col, max_col = _foreground_bbox(grid, background_color)
        tile = [
            row[min_col:max_col + 1]
            for row in grid[min_row:max_row + 1]
        ]
        tile_rows = len(tile)
        tile_cols = len(tile[0])
        if rows % tile_rows or cols % tile_cols:
            raise ValueError("Object tile does not divide the grid")
        macro_rows, macro_cols = rows // tile_rows, cols // tile_cols
        if tile_rows != macro_rows or tile_cols != macro_cols:
            raise ValueError("Object tile shape must match macro-grid shape")
        selector_grid = tile
        output_rows, output_cols = rows, cols
    else:
        raise ValueError(f"Unsupported tile source: {tile_source}")

    def selected(value):
        if selector_mode == "nonzero":
            return value != background_color
        if selector_mode == "color":
            return value == selector_color
        raise ValueError(f"Unsupported selector mode: {selector_mode}")

    output = [
        [background_color for _ in range(output_cols)]
        for _ in range(output_rows)
    ]
    for macro_row in range(macro_rows):
        for macro_col in range(macro_cols):
            if not selected(selector_grid[macro_row][macro_col]):
                continue
            row_offset = macro_row * tile_rows
            col_offset = macro_col * tile_cols
            for row in range(tile_rows):
                for col in range(tile_cols):
                    output[row_offset + row][col_offset + col] = tile[row][col]
    return output


def _row_template_color_extend(grid, background_color=0):
    """
    Extend partial rows by color-mapping a complete non-background template row.

    A row such as `88400000` can be completed from template `33233233` by
    inferring `3->8, 2->4` from the visible prefix, producing `88488488`.
    """
    if not grid:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Row template extension requires a rectangular grid")

    template_rows = [
        row
        for row in grid
        if all(value != background_color for value in row)
    ]
    if not template_rows:
        raise ValueError("No complete template row found")

    transformed = copy.deepcopy(grid)
    for row_index, row in enumerate(grid):
        if all(value == background_color for value in row):
            continue
        if all(value != background_color for value in row):
            continue

        prefix_len = 0
        while prefix_len < cols and row[prefix_len] != background_color:
            prefix_len += 1
        if prefix_len == 0:
            continue
        if any(value != background_color for value in row[prefix_len:]):
            raise ValueError("Partial row must have a leading visible prefix")

        best_row = None
        best_key = None
        for template in template_rows:
            forward = {}
            reverse = {}
            compatible = True
            for col in range(prefix_len):
                src = template[col]
                dst = row[col]
                if src in forward and forward[src] != dst:
                    compatible = False
                    break
                if dst in reverse and reverse[dst] != src:
                    compatible = False
                    break
                forward[src] = dst
                reverse[dst] = src
            if not compatible:
                continue
            if not all(value in forward for value in template):
                continue
            candidate = [forward[value] for value in template]
            # Prefer the template with strongest prefix evidence, then fewer
            # colors; this keeps the choice stable if several full rows exist.
            key = (-prefix_len, len(set(template)), template)
            if best_key is None or key < best_key:
                best_key = key
                best_row = candidate

        if best_row is None:
            raise ValueError("No compatible row template found")
        transformed[row_index] = best_row
    return transformed


def _foreground_line_runs(mask, axis_count, cross_count, vertical=True):
    runs = []
    for axis in range(axis_count):
        cross = 0
        while cross < cross_count:
            while cross < cross_count and (
                (cross, axis) if vertical else (axis, cross)
            ) not in mask:
                cross += 1
            start = cross
            while cross < cross_count and (
                (cross, axis) if vertical else (axis, cross)
            ) in mask:
                cross += 1
            end = cross - 1
            if end - start + 1 >= 2:
                runs.append({"axis": axis, "start": start, "end": end})
    return runs


def _paint_line_progression(
    completed,
    runs,
    axis_limit,
    cross_limit,
    vertical=True,
):
    changed = False
    max_steps = max(axis_limit, cross_limit) + 1

    for first in runs:
        for second in runs:
            axis_delta = second["axis"] - first["axis"]
            if axis_delta == 0:
                continue

            abs_axis_delta = abs(axis_delta)
            # This abstraction captures diagonal progressions of orthogonal
            # segments: as the carrier row/column advances by d, each segment
            # endpoint either stays fixed or shifts by +/-d.
            start_delta = second["start"] - first["start"]
            end_delta = second["end"] - first["end"]
            allowed_endpoint_deltas = {0, abs_axis_delta, -abs_axis_delta}
            if start_delta not in allowed_endpoint_deltas:
                continue
            if end_delta not in allowed_endpoint_deltas:
                continue

            for step in range(-max_steps, max_steps + 1):
                axis = first["axis"] + step * axis_delta
                if axis < 0 or axis >= axis_limit:
                    continue

                start = first["start"] + step * start_delta
                end = first["end"] + step * end_delta
                start = max(0, min(cross_limit - 1, start))
                end = max(0, min(cross_limit - 1, end))
                if start > end:
                    start, end = end, start
                if end - start + 1 < 2:
                    continue

                for cross in range(start, end + 1):
                    point = (cross, axis) if vertical else (axis, cross)
                    if point not in completed:
                        completed.add(point)
                        changed = True
    return changed


def _orthogonal_line_progression_field(
    grid,
    fill_color=None,
    background_color=0,
):
    """
    Complete sparse orthogonal line fields by extending arithmetic progressions
    of horizontal and vertical foreground runs, then color the remaining
    background with `fill_color`.

    The foreground is a compact line scaffold: repeated row/column segments
    imply neighboring segments whose endpoints move by 0 or one carrier-step.
    This is an image-level field completion, not per-cell insertion.
    """
    if fill_color in (None, background_color):
        raise ValueError("orthogonal_line_progression_field requires fill_color")
    if not grid:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("orthogonal_line_progression_field requires a rectangular grid")

    foreground_colors = sorted({
        value
        for row in grid
        for value in row
        if value != background_color
    })
    if len(foreground_colors) != 1:
        raise ValueError("orthogonal_line_progression_field requires one foreground color")
    foreground_color = foreground_colors[0]
    if foreground_color == fill_color:
        raise ValueError("orthogonal_line_progression_field fill matches foreground")

    mask = {
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value == foreground_color
    }
    if not mask:
        raise ValueError("orthogonal_line_progression_field requires foreground")

    vertical_runs = _foreground_line_runs(
        mask,
        axis_count=cols,
        cross_count=rows,
        vertical=True,
    )
    horizontal_runs = _foreground_line_runs(
        mask,
        axis_count=rows,
        cross_count=cols,
        vertical=False,
    )
    if len(vertical_runs) + len(horizontal_runs) < 2:
        raise ValueError("orthogonal_line_progression_field requires line progressions")

    completed = set(mask)
    changed = False
    changed |= _paint_line_progression(
        completed,
        vertical_runs,
        axis_limit=cols,
        cross_limit=rows,
        vertical=True,
    )
    changed |= _paint_line_progression(
        completed,
        horizontal_runs,
        axis_limit=rows,
        cross_limit=cols,
        vertical=False,
    )
    if not changed:
        raise ValueError("orthogonal_line_progression_field made no foreground completion")

    return [
        [
            foreground_color if (row, col) in completed else fill_color
            for col in range(cols)
        ]
        for row in range(rows)
    ]


def _marker_guided_row_period_fill(grid, background_color=0):
    """
    Synthesize horizontal row periods from sparse marker guidance.

    Two cases are handled by the same image-level abstraction:
    - a visible source row is shifted one column after each marker row;
    - edge seeds emit one cycle of separator-defined horizontal intervals upward.

    This is periodic row synthesis, not a beam: marker rows/columns choose a
    phase of a row-period field.
    """
    if not grid:
        return copy.deepcopy(grid)
    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("marker_guided_row_period_fill requires a rectangular grid")

    non_background_colors = sorted({
        value
        for row in grid
        for value in row
        if value != background_color
    })
    if len(non_background_colors) != 2:
        raise ValueError("marker_guided_row_period_fill requires two foreground colors")

    positions_by_color = {
        color: [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == color
        ]
        for color in non_background_colors
    }

    foreground_rows = sorted({
        row
        for points in positions_by_color.values()
        for row, _ in points
    })
    if not foreground_rows:
        raise ValueError("marker_guided_row_period_fill requires foreground rows")
    min_foreground_row = foreground_rows[0]
    max_foreground_row = foreground_rows[-1]

    # Case 1: a source row at the top supplies the binary row pattern; marker
    # rows shift the pattern left/right by one phase for all following rows.
    template_specs = []
    for color in non_background_colors:
        for row in range(rows):
            cols_for_row = [
                col
                for col in range(cols)
                if grid[row][col] == color
            ]
            if len(cols_for_row) >= 2 and row == min_foreground_row:
                template_specs.append((row, color, cols_for_row))
    if len(template_specs) == 1:
        template_row, source_color, _ = template_specs[0]
        marker_color = next(color for color in non_background_colors if color != source_color)
        marker_positions = positions_by_color[marker_color]
        if not marker_positions:
            raise ValueError("marker_guided_row_period_fill requires marker rows")
        if any(row <= template_row for row, _ in marker_positions):
            raise ValueError("marker rows must follow the source row")

        marker_cols = [col for _, col in marker_positions]
        shift_direction = 1 if sum(marker_cols) / len(marker_cols) < (cols - 1) / 2 else -1
        marker_rows = sorted({row for row, _ in marker_positions})
        source_cols = [
            col
            for col in range(cols)
            if grid[template_row][col] == source_color
        ]

        output = [[background_color for _ in range(cols)] for _ in range(rows)]
        marker_set = set(marker_positions)
        for row in range(rows):
            shift_count = sum(1 for marker_row in marker_rows if marker_row <= row)
            col_shift = shift_direction * shift_count
            for col in source_cols:
                target_col = col + col_shift
                if 0 <= target_col < cols:
                    output[row][target_col] = source_color
        for row, col in marker_set:
            output[row][col] = marker_color
        return output

    # Case 2: separator markers on the last foreground row partition columns
    # into intervals.  Edge singleton seeds choose a cyclic interval phase and
    # emit one upward cycle of filled intervals.
    separator_specs = []
    for color in non_background_colors:
        row_counts = {}
        for row, _ in positions_by_color[color]:
            row_counts[row] = row_counts.get(row, 0) + 1
        for row, count in row_counts.items():
            if count >= 2 and row == max_foreground_row:
                separator_specs.append((row, color))
    if len(separator_specs) != 1:
        raise ValueError("marker_guided_row_period_fill requires one separator row or one source row")
    separator_row, marker_color = separator_specs[0]
    source_color = next(color for color in non_background_colors if color != marker_color)

    seed_positions = positions_by_color[source_color]
    if not seed_positions:
        raise ValueError("marker_guided_row_period_fill requires source seeds")
    edge_cols = {col for _, col in seed_positions}
    if edge_cols == {0}:
        seed_side = "left"
    elif edge_cols == {cols - 1}:
        seed_side = "right"
    else:
        raise ValueError("marker_guided_row_period_fill requires seeds on one edge")

    separator_cols = sorted(col for row, col in positions_by_color[marker_color] if row == separator_row)
    if len(separator_cols) < 2:
        raise ValueError("marker_guided_row_period_fill requires multiple separators")

    if seed_side == "left":
        starts = [0] + separator_cols
        ends = [col - 1 for col in separator_cols] + [cols - 1]
        base_index = 0
        phase_delta = 1
    else:
        starts = [0] + [col + 1 for col in separator_cols]
        ends = separator_cols + [cols - 1]
        base_index = len(starts) - 1
        phase_delta = -1
    intervals = [
        (start, end)
        for start, end in zip(starts, ends)
        if 0 <= start <= end < cols
    ]
    if len(intervals) < 2:
        raise ValueError("marker_guided_row_period_fill requires usable intervals")

    output = [[background_color for _ in range(cols)] for _ in range(rows)]
    for seed_row, _ in seed_positions:
        if seed_row >= separator_row:
            raise ValueError("source seeds must be above separator row")
        for offset in range(len(intervals)):
            target_row = seed_row - offset
            if target_row < 0:
                break
            interval_index = (base_index + phase_delta * offset) % len(intervals)
            start, end = intervals[interval_index]
            for col in range(start, end + 1):
                output[target_row][col] = source_color

    for row, col in positions_by_color[marker_color]:
        output[row][col] = marker_color
    return output


def _periodic_pattern_synthesis(
    grid,
    pattern_type="visible_period_shift",
    source_color=None,
    fill_color=None,
    direction="up_right",
    occluder_color=None,
    occluder_colors=None,
    unknown_mode="auto_single",
    out_shift_row=0,
    out_shift_col=1,
    max_period=12,
    output_scale=2,
    output_height=0,
    output_width=0,
    selector_mode="nonzero",
    selector_color=None,
    tile_source="grid",
    background_color=0,
):
    if pattern_type == "visible_period_shift":
        return _periodic_visible_synthesis(
            grid,
            occluder_color=occluder_color,
            occluder_colors=occluder_colors,
            unknown_mode=unknown_mode,
            out_shift_row=out_shift_row,
            out_shift_col=out_shift_col,
            max_period=max_period,
        )
    if pattern_type == "bouncing_diagonal_seed":
        return _bouncing_diagonal_seed(
            grid,
            source_color=source_color,
            fill_color=fill_color,
            direction=direction,
        )
    if pattern_type == "checker_from_row_colors":
        return _checker_from_row_colors(grid)
    if pattern_type == "periodic_extend_x":
        return _periodic_extend_x(grid, output_scale=output_scale)
    if pattern_type == "row_prefix_periodic_fill":
        return _row_prefix_periodic_fill(
            grid,
            output_width=output_width,
            background_color=background_color,
        )
    if pattern_type == "periodic_extend_y":
        return _periodic_extend_y(
            grid,
            output_height=output_height,
            output_width=output_width,
            output_scale=output_scale,
            background_color=background_color,
        )
    if pattern_type == "periodic_extend_y_recolor":
        return _periodic_extend_y_recolor(
            grid,
            output_height=output_height,
            output_width=output_width,
            output_scale=output_scale,
            background_color=background_color,
            fill_color=fill_color,
        )
    if pattern_type == "row_prefix_staircase_y":
        return _row_prefix_staircase_y(
            grid,
            output_height=output_height,
            output_width=output_width,
            background_color=background_color,
        )
    if pattern_type == "row_token_diagonal_slide":
        return _row_token_diagonal_slide(
            grid,
            background_color=background_color,
        )
    if pattern_type == "vertical_edge_palindrome_repeat":
        return _vertical_edge_palindrome_repeat(
            grid,
            background_color=background_color,
        )
    if pattern_type == "tile_by_self_mask":
        return _tile_by_self_mask(
            grid,
            selector_mode=selector_mode,
            selector_color=selector_color,
            tile_source=tile_source,
            background_color=background_color,
        )
    if pattern_type == "row_template_color_extend":
        return _row_template_color_extend(
            grid,
            background_color=background_color,
        )
    if pattern_type == "orthogonal_line_progression_field":
        return _orthogonal_line_progression_field(
            grid,
            fill_color=fill_color,
            background_color=background_color,
        )
    if pattern_type == "marker_guided_row_period_fill":
        return _marker_guided_row_period_fill(
            grid,
            background_color=background_color,
        )
    raise ValueError(f"Unsupported periodic synthesis type: {pattern_type}")


def symmetry_grid_based(
    grid,
    source_color=None,
    fill_color=None,
    symmetry_type="rot90_missing_orbit",
    center_mode="best",
    background_color=0,
    mirror_axis="DIAGONAL_LEFT",
    duplicate_mode="infer_rows_cols",
    occluder_color=None,
    occluder_colors=None,
    period_mode="minimal_2d",
    max_period=12,
    pattern_type="visible_period_shift",
    unknown_mode="auto_single",
    out_shift_row=0,
    out_shift_col=1,
    direction="up_right",
    output_scale=2,
    output_height=0,
    output_width=0,
    selector_mode="nonzero",
    selector_color=None,
    tile_source="grid",
):
    """
    Complete reusable image-level symmetry patterns.

    Current family:
    - rot90_missing_orbit: fill background pixels whose other three 90-degree
      rotations are already present in `source_color`. `center_mode="best"`
      chooses the center yielding the largest supported missing orbit.
    - diagonal_canvas_repair: repair occluded cells on a diagonally symmetric
      textured canvas, using duplicate row/column lines as extra donors.
    - periodic_canvas_repair: repair occluded cells by inferring the smallest
      supported 2D repeating tile from visible cells.
    - periodic_pattern_synthesis: synthesize a full repeated/checker pattern
      from visible periodic or seed evidence.
    """
    if symmetry_type == "rot90_color_orbit_completion":
        return _rot90_color_orbit_completion(
            grid,
            background_color=background_color,
            center_mode=center_mode,
        )
    if symmetry_type == "diagonal_canvas_repair":
        return _diagonal_canvas_repair(
            grid,
            mirror_axis=mirror_axis,
            duplicate_mode=duplicate_mode,
            occluder_color=occluder_color,
            occluder_colors=occluder_colors,
        )
    if symmetry_type == "periodic_canvas_repair":
        return _periodic_canvas_repair(
            grid,
            occluder_color=occluder_color,
            occluder_colors=occluder_colors,
            period_mode=period_mode,
            max_period=max_period,
        )
    if symmetry_type == "periodic_pattern_synthesis":
        return _periodic_pattern_synthesis(
            grid,
            pattern_type=pattern_type,
            source_color=source_color,
            fill_color=fill_color,
            direction=direction,
            occluder_color=occluder_color,
            occluder_colors=occluder_colors,
            unknown_mode=unknown_mode,
            out_shift_row=out_shift_row,
            out_shift_col=out_shift_col,
            max_period=max_period,
            output_scale=output_scale,
            output_height=output_height,
            output_width=output_width,
            selector_mode=selector_mode,
            selector_color=selector_color,
            tile_source=tile_source,
            background_color=background_color,
        )
    if symmetry_type != "rot90_missing_orbit":
        raise ValueError(f"Unsupported symmetry type: {symmetry_type}")
    if center_mode != "best":
        raise ValueError(f"Unsupported center mode: {center_mode}")
    if source_color is None or fill_color is None:
        raise ValueError("rot90_missing_orbit requires source_color and fill_color")
    if not grid:
        return copy.deepcopy(grid)

    rows = len(grid)
    cols = len(grid[0])
    best_center = None
    best_missing = []
    for center2 in _candidate_centers(rows, cols):
        missing = _rot90_missing_orbit_pixels(
            grid,
            source_color,
            background_color,
            center2,
        )
        candidate_key = (len(missing), -center2[0], -center2[1])
        best_key = (
            len(best_missing),
            -best_center[0],
            -best_center[1],
        ) if best_center is not None else None
        if best_key is None or candidate_key > best_key:
            best_center = center2
            best_missing = missing

    transformed_grid = copy.deepcopy(grid)
    for row, col in best_missing:
        transformed_grid[row][col] = fill_color
    return transformed_grid

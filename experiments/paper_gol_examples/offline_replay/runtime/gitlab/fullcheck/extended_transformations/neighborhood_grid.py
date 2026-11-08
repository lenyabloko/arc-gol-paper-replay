from dsl_classifier_migration import classifier_action


def neighborhood_grid_based(
    grid,
    neighborhood_type="diagonal_quadrant_neighbors",
    object_color=2,
    background_color=0,
    color1=3,
    color2=6,
    color3=8,
    color4=7,
    classifier_params=None,
):
    neighborhood_type, classifier_params = classifier_action(
        "neighborhood_type",
        neighborhood_type,
        classifier_params,
    )
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if any(len(row) != cols for row in grid):
        raise ValueError("Neighborhood projection requires a rectangular grid")

    markers = [
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value == object_color
    ]
    if not markers:
        raise ValueError("Neighborhood projection requires marker pixels")

    if neighborhood_type == "outer_corner_labels":
        transformed = [row[:] for row in grid]
        seen = set()
        blocks = []
        for row in range(rows - 1):
            for col in range(cols - 1):
                block = {
                    (row, col),
                    (row, col + 1),
                    (row + 1, col),
                    (row + 1, col + 1),
                }
                if not all(grid[r][c] == object_color for r, c in block):
                    continue
                if block & seen:
                    continue
                # Keep this operation narrow: every object component must be a
                # standalone 2x2 block, not part of a larger rectangle.
                for r, c in block:
                    for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                        if (nr, nc) not in block and 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == object_color:
                            raise ValueError("outer_corner_labels requires standalone 2x2 blocks")
                seen |= block
                blocks.append((row, col))
        if not blocks or seen != set(markers):
            raise ValueError("outer_corner_labels requires only 2x2 marker blocks")
        for row, col in blocks:
            for out_row, out_col, out_color in (
                (row - 1, col - 1, color1),
                (row - 1, col + 2, color2),
                (row + 2, col - 1, color3),
                (row + 2, col + 2, color4),
            ):
                if 0 <= out_row < rows and 0 <= out_col < cols:
                    if transformed[out_row][out_col] not in (background_color, out_color):
                        raise ValueError("outer_corner_labels collides with non-background")
                    transformed[out_row][out_col] = out_color
        return transformed

    if neighborhood_type == "marker_halo":
        transformed = [[background_color for _ in range(cols)] for _ in range(rows)]
        for row, col in markers:
            for delta_row, delta_col in (
                (-1, -1), (-1, 1), (1, -1), (1, 1)
            ):
                out_row = row + delta_row
                out_col = col + delta_col
                if 0 <= out_row < rows and 0 <= out_col < cols:
                    transformed[out_row][out_col] = object_color
            for delta_row, delta_col in (
                (-1, 0), (0, -1), (0, 1), (1, 0)
            ):
                out_row = row + delta_row
                out_col = col + delta_col
                if 0 <= out_row < rows and 0 <= out_col < cols:
                    transformed[out_row][out_col] = color1
        return transformed

    if neighborhood_type == "singleton_border":
        counts = {}
        positions = {}
        for row, values in enumerate(grid):
            for col, value in enumerate(values):
                if value == background_color:
                    continue
                counts[value] = counts.get(value, 0) + 1
                positions.setdefault(value, []).append((row, col))
        singleton_colors = [
            value
            for value, count in counts.items()
            if count == 1 and value != object_color
        ]
        if not singleton_colors:
            raise ValueError("singleton_border requires a singleton target")
        singleton_colors = sorted(singleton_colors)
        target_color = singleton_colors[-1]
        target_row, target_col = positions[target_color][0]

        transformed = [[background_color for _ in range(cols)] for _ in range(rows)]
        for delta_row in (-1, 0, 1):
            for delta_col in (-1, 0, 1):
                out_row = target_row + delta_row
                out_col = target_col + delta_col
                if not (0 <= out_row < rows and 0 <= out_col < cols):
                    continue
                transformed[out_row][out_col] = (
                    target_color
                    if delta_row == 0 and delta_col == 0
                    else object_color
                )
        return transformed

    if neighborhood_type == "ray_aligned_singleton_cross":
        counts = {}
        positions = {}
        for row, values in enumerate(grid):
            for col, value in enumerate(values):
                if value == background_color:
                    continue
                counts[value] = counts.get(value, 0) + 1
                positions.setdefault(value, []).append((row, col))

        transformed = [[background_color for _ in range(cols)] for _ in range(rows)]
        changed = False
        for center_color in sorted(counts):
            if counts[center_color] != 1:
                continue
            center_row, center_col = positions[center_color][0]
            support_candidates = []
            for support_color, support_positions in positions.items():
                if support_color == center_color:
                    continue
                directions = set()
                aligned_count = 0
                for row, col in support_positions:
                    if row == center_row and col < center_col:
                        directions.add((0, -1))
                        aligned_count += 1
                    elif row == center_row and col > center_col:
                        directions.add((0, 1))
                        aligned_count += 1
                    elif col == center_col and row < center_row:
                        directions.add((-1, 0))
                        aligned_count += 1
                    elif col == center_col and row > center_row:
                        directions.add((1, 0))
                        aligned_count += 1
                if directions:
                    support_candidates.append((
                        -len(directions),
                        -aligned_count,
                        support_color,
                        directions,
                    ))
            if not support_candidates:
                continue
            support_candidates.sort()
            if len(support_candidates) > 1 and support_candidates[0][:2] == support_candidates[1][:2]:
                raise ValueError("ray_aligned_singleton_cross requires a unique support color")
            _, _, support_color, directions = support_candidates[0]
            transformed[center_row][center_col] = center_color
            for delta_row, delta_col in directions:
                out_row = center_row + delta_row
                out_col = center_col + delta_col
                if 0 <= out_row < rows and 0 <= out_col < cols:
                    transformed[out_row][out_col] = support_color
                    changed = True
        if not changed:
            raise ValueError("ray_aligned_singleton_cross found no aligned singleton")
        return transformed

    if neighborhood_type == "diagonal_quadrant_neighbors":
        deltas = {
            (-1, -1): color1,
            (-1, 1): color2,
            (1, -1): color3,
            (1, 1): color4,
        }
    elif neighborhood_type == "cardinal_cross_neighbors":
        deltas = {
            (-1, 0): color1,
            (0, -1): color2,
            (0, 1): color3,
            (1, 0): color4,
        }
    else:
        raise ValueError(f"Unsupported neighborhood type: {neighborhood_type}")

    transformed = [[background_color for _ in range(cols)] for _ in range(rows)]
    for row, col in markers:
        if neighborhood_type == "cardinal_cross_neighbors":
            transformed[row][col] = object_color
        for (delta_row, delta_col), color in deltas.items():
            out_row = row + delta_row
            out_col = col + delta_col
            if 0 <= out_row < rows and 0 <= out_col < cols:
                transformed[out_row][out_col] = color
    return transformed


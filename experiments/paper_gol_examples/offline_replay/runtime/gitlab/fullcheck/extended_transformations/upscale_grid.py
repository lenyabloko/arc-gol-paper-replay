try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *
from dsl_classifier_migration import classifier_action


def upscale_grid_based(
    grid, factor, mirror, upscale_type, color, border_color, fill_color, classifier_params=None
):
    upscale_type, classifier_params = classifier_action(
        "upscale_type",
        upscale_type,
        classifier_params,
    )
    if upscale_type == "lattice_cells_to_blocks":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("lattice_cells_to_blocks requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("lattice_cells_to_blocks requires a rectangular grid")
        output = [[0 for _ in range(cols * 2)] for _ in range(rows * 2)]
        for row in range(rows):
            for col in range(cols):
                value = grid[row][col]
                if value == 0:
                    continue
                if row % 2 != 1 or col % 2 != 1:
                    raise ValueError("lattice_cells_to_blocks expects foreground on odd lattice")
                out_row = ((row - 1) // 2) * 4
                out_col = ((col - 1) // 2) * 4
                for delta_row in range(4):
                    for delta_col in range(4):
                        output[out_row + delta_row][out_col + delta_col] = value
        return output

    if upscale_type == "unique_colors_corner_diagonals":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("unique_colors_corner_diagonals requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("unique_colors_corner_diagonals requires a rectangular grid")
        diagonal_color = fill_color
        if diagonal_color in (None, 0):
            raise ValueError("unique_colors_corner_diagonals requires a diagonal color")
        if any(value == diagonal_color for row in grid for value in row):
            raise ValueError("unique_colors_corner_diagonals expects a newly inserted diagonal color")

        factor = count_unique_colors_except_zero(grid)
        if factor <= 1:
            raise ValueError("unique_colors_corner_diagonals requires multiple foreground colors")
        output = [
            [value for value in row for _ in range(factor)]
            for row in grid
            for _ in range(factor)
        ]

        components = find_connected_components(grid, background_color=0, connectivity=4)
        candidates = []
        for component in components:
            pixels = component["pixels"]
            if len(pixels) <= 1:
                continue
            min_row = min(row for row, _ in pixels)
            max_row = max(row for row, _ in pixels)
            min_col = min(col for _, col in pixels)
            max_col = max(col for _, col in pixels)
            height = max_row - min_row + 1
            width = max_col - min_col + 1
            if height <= 1 or width <= 1:
                continue
            if len(pixels) != height * width:
                continue
            if max_row >= rows - 1 or max_col >= cols - 1:
                continue
            candidates.append((height * width, -min_row, -min_col, min_row, max_row, min_col, max_col))
        if not candidates:
            raise ValueError("unique_colors_corner_diagonals found no source rectangle")
        _, _, _, min_row, max_row, min_col, max_col = max(candidates)

        diagonal_specs = [
            (min_row - 1, min_col - 1, "main"),
            (min_row - 1, max_col + 1, "anti"),
            (max_row + 1, min_col - 1, "anti"),
            (max_row + 1, max_col + 1, "main"),
        ]
        changed = False
        for cell_row, cell_col, diagonal_type in diagonal_specs:
            if not (0 <= cell_row < rows and 0 <= cell_col < cols):
                continue
            if grid[cell_row][cell_col] != 0:
                continue
            for offset in range(factor):
                out_row = cell_row * factor + offset
                out_col = (
                    cell_col * factor + offset
                    if diagonal_type == "main"
                    else cell_col * factor + (factor - 1 - offset)
                )
                output[out_row][out_col] = diagonal_color
                changed = True
        if not changed:
            raise ValueError("unique_colors_corner_diagonals found no diagonal cells")
        return output

    if upscale_type == "marker_square_diagonal_blocks":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("marker_square_diagonal_blocks requires a non-empty grid")
        if any(len(row) != cols for row in grid):
            raise ValueError("marker_square_diagonal_blocks requires a rectangular grid")
        if factor != 3:
            raise ValueError("marker_square_diagonal_blocks expects factor=3")

        object_color = color
        object_pixels = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] == object_color
        ]
        if not object_pixels:
            raise ValueError("marker_square_diagonal_blocks requires object-color pixels")

        marker_pixels = [
            (row, col, value)
            for row in range(rows)
            for col in range(cols)
            for value in [grid[row][col]]
            if value not in (0, object_color)
        ]
        if len(marker_pixels) != 1:
            raise ValueError("marker_square_diagonal_blocks requires exactly one marker")
        marker_row, marker_col, _ = marker_pixels[0]

        square_top_left = None
        marker_local = None
        for top in (marker_row - 1, marker_row):
            for left in (marker_col - 1, marker_col):
                if top < 0 or left < 0 or top + 1 >= rows or left + 1 >= cols:
                    continue
                values = [
                    grid[row][col]
                    for row in (top, top + 1)
                    for col in (left, left + 1)
                ]
                if values.count(object_color) != 3:
                    continue
                marker_count = sum(
                    1
                    for value in values
                    if value not in (0, object_color)
                )
                if marker_count != 1:
                    continue
                square_top_left = (top, left)
                marker_local = (marker_row - top, marker_col - left)
                break
            if square_top_left is not None:
                break
        if square_top_left is None:
            raise ValueError("marker_square_diagonal_blocks requires a 2x2 marker square")

        out_rows = rows * factor
        out_cols = cols * factor
        block_size = factor + 1
        top, left = square_top_left
        if marker_local in {(0, 0), (1, 1)}:
            anchors = [
                (top, left),
                (top + block_size, left + block_size),
            ]
        else:
            anchors = [
                (top, left + block_size),
                (top + block_size, left),
            ]

        output = [[0 for _ in range(out_cols)] for _ in range(out_rows)]
        for anchor_row, anchor_col in anchors:
            for row in range(anchor_row, min(anchor_row + block_size, out_rows)):
                for col in range(anchor_col, min(anchor_col + block_size, out_cols)):
                    output[row][col] = object_color
        return output

    if upscale_type == "foreground_bbox_pixel_based":
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            return []
        if any(len(row) != cols for row in grid):
            raise ValueError("foreground_bbox_pixel_based requires a rectangular grid")
        foreground = [
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if grid[row][col] != 0
        ]
        if not foreground:
            raise ValueError("foreground_bbox_pixel_based requires foreground")
        min_row = min(row for row, _ in foreground)
        max_row = max(row for row, _ in foreground)
        min_col = min(col for _, col in foreground)
        max_col = max(col for _, col in foreground)
        cropped = [
            source_row[min_col : max_col + 1]
            for source_row in grid[min_row : max_row + 1]
        ]
        return [
            [value for value in row for _ in range(factor)]
            for row in cropped
            for _ in range(factor)
        ]

    column_count = 0 
    if upscale_type == "standard":
        upscaled_grid = []
        for i, row in enumerate(grid):
            #new_rows = [[] for _ in range(factor)]
            new_rows = []
            for j, value in enumerate(row):
                if value == 0:
                    for k in range(factor):
                        #new_rows[k].extend([0] * factor)
                        if len(new_rows) <= k:
                            new_rows.append([0] * factor)
                        else:    
                            new_rows[k] = [0] * factor
                elif value == border_color:
                    for k in range(factor):
                        for l in range(factor):
                            if ((i * factor + k) + (j * factor + l)) % 2 == 0:
                                val = color
                            else:
                                val = fill_color
                            #new_rows[k].append(val)
                            if len(new_rows) <= k:
                                new_rows.append(val)
                            else:
                                new_rows[k] = val
            if column_count == 0 or column_count == len(new_rows):               
                upscaled_grid.append(new_rows)
                column_count = len(new_rows)
            else:
                raise ValueError(f"Row {i} has inconsistent column count: {len(new_rows[0])} vs {column_count}")    
        return upscaled_grid

    if upscale_type == "pixel_based":
        if mirror:
            grid = swap_with_zero(grid)
        upscaled_grid = [
            [value for value in row for _ in range(factor)]
            for row in grid
            for _ in range(factor)
        ]
        if mirror:
            tiled_grid = [row * factor for _ in range(factor) for row in grid]
            transformed_grid = [
                [u if u == t else 0 for u, t in zip(u_row, t_row)]
                for u_row, t_row in zip(upscaled_grid, tiled_grid)
            ]
            return transformed_grid
        return upscaled_grid

    if upscale_type == "unique_colors":
        factor = count_unique_colors_except_zero(grid)

    return tuple(
        [value for value in row for _ in range(factor)]
        for row in grid
        for _ in range(factor)
    )


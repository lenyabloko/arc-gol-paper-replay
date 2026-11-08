def _horizontal_runs(grid, color):
    runs = []
    for row, values in enumerate(grid):
        col = 0
        while col < len(values):
            if values[col] != color:
                col += 1
                continue
            start = col
            while col + 1 < len(values) and values[col + 1] == color:
                col += 1
            runs.append((row, start, col))
            col += 1
    return runs


def pyramid_grid_based(
    grid,
    pattern_type="horizontal_run_triangles",
    base_color=2,
    upper_color=3,
    lower_color=1,
    background_color=0,
):
    if pattern_type != "horizontal_run_triangles":
        raise ValueError(f"Unsupported pyramid pattern type: {pattern_type}")
    if not grid or not grid[0]:
        return []

    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("Pyramid grid requires a rectangular grid")
    if base_color == background_color:
        raise ValueError("Pyramid grid requires a non-background base color")

    runs = _horizontal_runs(grid, base_color)
    if not runs:
        raise ValueError("Pyramid grid requires a horizontal base run")
    base_row, start_col, end_col = max(runs, key=lambda item: (item[2] - item[1] + 1, -item[0]))
    base_len = end_col - start_col + 1

    output = [row[:] for row in grid]

    for distance in range(1, base_row + 1):
        row = base_row - distance
        fill_end = min(cols - 1, end_col + distance)
        for col in range(start_col, fill_end + 1):
            if output[row][col] == background_color:
                output[row][col] = upper_color

    for distance in range(1, base_len):
        row = base_row + distance
        if row >= rows:
            break
        fill_end = end_col - distance
        if fill_end < start_col:
            break
        for col in range(start_col, fill_end + 1):
            if output[row][col] == background_color:
                output[row][col] = lower_color

    return output

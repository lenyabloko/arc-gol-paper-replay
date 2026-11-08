def count_grid_based(
    grid,
    count_type="foreground_count_prefix",
    background_color=0,
    output_color=2,
):
    if count_type != "foreground_count_prefix":
        raise ValueError(f"Unsupported count type: {count_type}")

    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if any(len(row) != cols for row in grid):
        raise ValueError("Count grid requires a rectangular grid")

    count = sum(
        value != background_color
        for row in grid
        for value in row
    )
    output = [[background_color for _ in range(cols)] for _ in range(rows)]
    positions = []
    if rows:
        positions.extend((0, col) for col in range(cols))
    center = (rows // 2, cols // 2)
    if 0 <= center[0] < rows and 0 <= center[1] < cols and center not in positions:
        positions.append(center)
    positions.extend(
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if (row, col) not in positions
    )

    for row, col in positions[:count]:
        output[row][col] = output_color
    return output

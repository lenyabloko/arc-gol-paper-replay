import copy

try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def arbitrary_duplicate_grid_based(
    grid, mirror, duplicate_arbitrary, axis, mirror_grid, combine_pattern, concat_axis
):
    duplicate = duplicate_arbitrary
    if mirror:
        grid = swap_with_zero(grid)

    def duplicate_rows(grid, steps, mirror_axis=None):
        if mirror_axis == "horizontal":
            grid = [row[::-1] for row in grid]
        elif mirror_axis == "vertical":
            grid = grid[::-1]
        grid = [row * (steps + 1) for row in grid]
        return grid

    grid1 = copy.deepcopy(grid)
    if mirror_grid == "grid1":
        grid1 = duplicate_rows(grid1, duplicate, axis)
    else:
        grid1 = duplicate_rows(grid1, duplicate, None)

    grid2 = copy.deepcopy(grid)
    if mirror_grid == "grid2":
        grid2 = duplicate_rows(grid2, duplicate, axis)
    else:
        grid2 = duplicate_rows(grid2, duplicate, None)

    grid3 = copy.deepcopy(grid1)

    transformed_grid = []
    pattern = combine_pattern.split("+")
    if concat_axis == "y":
        for part in pattern:
            part = part.strip()
            if part == "grid1":
                transformed_grid += grid1
            elif part == "grid2":
                transformed_grid += grid2
            elif part == "grid3":
                transformed_grid += grid3
            else:
                raise ValueError(f"Unknown grid part in combine_pattern: {part}")
    elif concat_axis == "x":
        max_rows = max(len(grid1), len(grid2), len(grid3))

        def pad_grid(grid, num_rows):
            return grid + [[]] * (num_rows - len(grid))

        grid1 = pad_grid(grid1, max_rows)
        grid2 = pad_grid(grid2, max_rows)
        grid3 = pad_grid(grid3, max_rows)

        for row_idx in range(max_rows):
            new_row = []
            for part in pattern:
                part = part.strip()
                if part == "grid1":
                    new_row += grid1[row_idx]
                elif part == "grid2":
                    new_row += grid2[row_idx]
                elif part == "grid3":
                    new_row += grid3[row_idx]
                else:
                    raise ValueError(f"Unknown grid part in combine_pattern: {part}")
            transformed_grid.append(new_row)
    else:
        raise ValueError(f"Invalid concat_axis: {concat_axis}. Use 'x' or 'y'.")

    return transformed_grid

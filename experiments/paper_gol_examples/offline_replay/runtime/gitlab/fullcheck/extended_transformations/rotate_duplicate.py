try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def rotate_duplicate_grid_based(grid, mirror, rotation_degrees):
    if mirror:
        grid = swap_with_zero(grid)

    def rotate_90_clockwise(grid):
        return [list(row) for row in zip(*grid[::-1])]

    def rotate_180(grid):
        return [row[::-1] for row in grid[::-1]]

    def rotate_270_clockwise(grid):
        return [list(row) for row in zip(*grid)][::-1]

    def apply_rotation(grid, degrees):
        if degrees == 0:
            return grid
        elif degrees == 90:
            return rotate_90_clockwise(grid)
        elif degrees == 180:
            return rotate_180(grid)
        elif degrees == 270:
            return rotate_270_clockwise(grid)
        else:
            raise ValueError("Rotation must be 0, 90, 180, or 270 degrees.")

    if len(rotation_degrees) != 4:
        raise ValueError("rotation_degrees must be a list of four elements.")

    top_left = apply_rotation(grid, rotation_degrees[0])
    bottom_left = apply_rotation(grid, rotation_degrees[1])
    top_right = apply_rotation(grid, rotation_degrees[2])
    bottom_right = apply_rotation(grid, rotation_degrees[3])

    top_row = [top_left[i] + top_right[i] for i in range(len(grid))]
    bottom_row = [bottom_left[i] + bottom_right[i] for i in range(len(grid))]

    transformed_grid = top_row + bottom_row
    return transformed_grid

try:
    from extended_transformations.utils import rotate_grid
except ModuleNotFoundError:
    from utils import rotate_grid


def rotate_grid_based(grid, degrees):
    return rotate_grid(grid, degrees)

try:
    from extended_transformations.utils import *
except ModuleNotFoundError:
    from utils import *


def shift_grid_based(grid, color1):
    rows, cols = len(grid), len(grid[0]) if grid else 0
    objects = find_connected_components(grid)
    color_objs = [obj for obj in objects if obj["color"] == color1]
    color_top = min(x for x, y in color_objs[0]["pixels"])
    new_grid = [[0 for _ in range(cols)] for _ in range(rows)]

    for x, y in color_objs[0]["pixels"]:
        new_grid[x][y] = color1

    for obj in objects:
        if obj["color"] == color1:
            continue

        obj_top = min(x for x, y in obj["pixels"])
        shift = color_top - obj_top
        shifted = [(x + shift, y) for x, y in obj["pixels"]]
        min_shifted_x = min(x for x, y in shifted)
        max_shifted_x = max(x for x, y in shifted)

        if min_shifted_x < 0:
            shift -= min_shifted_x
            shifted = [(x + shift, y) for x, y in obj["pixels"]]
        elif max_shifted_x >= rows:
            shift -= max_shifted_x - rows + 1
            shifted = [(x + shift, y) for x, y in obj["pixels"]]
        for x, y in shifted:
            new_grid[x][y] = obj["color"]

    return new_grid

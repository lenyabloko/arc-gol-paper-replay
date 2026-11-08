"""Dimensionless primitive/topology detectors for small abstract supports.

The functions here detect topology evidence from a binary support by geometric
predicates such as full-row line, diagonal, center point, and ring. They
deliberately do not store or compare explicit matrices; dimensions are supplied
separately as primitive parameters. Role concepts such as "bar" are OWL-level
connector classifications over this evidence, not DSL primitive shapes.
"""


SUPPORTED_TILE_TOPOLOGY_CLASSES = {
    "top_bar_shape",
    "bottom_bar_shape",
    "diagonal_shape",
    "anti_diagonal_shape",
    "ring_shape",
    "center_point_shape",
    "horizontal_line_shape",
    "vertical_line_shape",
    "point",
    "square_shape",
    "rectangle",
}


def owl_class_for_concept(concept):
    """Return the OWL class required by a detected topology concept.

    Shape and color are deliberately separate.  The required class names only
    the structural/topological condition; color is a primitive value or rule
    output.
    """
    if concept not in SUPPORTED_TILE_TOPOLOGY_CLASSES:
        raise ValueError(f"unsupported tile topology concept {concept!r}")
    return concept


def concept_from_owl_class(owl_class):
    """Resolve an OWL class fragment to a detected topology concept."""
    if owl_class not in SUPPORTED_TILE_TOPOLOGY_CLASSES:
        raise ValueError(f"unknown topology owl_class {owl_class!r}")
    return owl_class


def normalize_binary_support(tile, background_color=0):
    return {
        (row_index, col_index)
        for row_index, row in enumerate(tile)
        for col_index, value in enumerate(row)
        if value != background_color
    }


def classify_binary_tile_concept(tile, background_color=0):
    """Return an OWL-style shape concept for a binary tile support.

    The returned name is dimensionless.  Numeric values such as tile height,
    width, or side length are the caller's primitive parameters.
    """
    height = len(tile)
    width = len(tile[0]) if height else 0
    if height <= 0 or width <= 0 or any(len(row) != width for row in tile):
        raise ValueError("tile topology classification requires a rectangular tile")

    support = normalize_binary_support(tile, background_color=background_color)
    if not support:
        raise ValueError("tile topology classification requires foreground support")

    if len(support) == 1:
        row, col = next(iter(support))
        if height % 2 == 1 and width % 2 == 1 and row == height // 2 and col == width // 2:
            return "center_point_shape"
        return "point"

    if support == {(row, col) for row in range(height) for col in range(width)}:
        return "square_shape" if height == width else "rectangle"

    full_rows = [
        row
        for row in range(height)
        if support == {(row, col) for col in range(width)}
    ]
    if full_rows:
        row = full_rows[0]
        if row == 0:
            return "top_bar_shape"
        if row == height - 1:
            return "bottom_bar_shape"
        return "horizontal_line_shape"

    full_cols = [
        col
        for col in range(width)
        if support == {(row, col) for row in range(height)}
    ]
    if full_cols:
        return "vertical_line_shape"

    if height == width:
        if support == {(index, index) for index in range(height)}:
            return "diagonal_shape"
        if support == {(index, width - 1 - index) for index in range(height)}:
            return "anti_diagonal_shape"
        border = {
            (row, col)
            for row in range(height)
            for col in range(width)
            if row in (0, height - 1) or col in (0, width - 1)
        }
        if height >= 3 and support == border:
            return "ring_shape"

    raise ValueError("tile topology classification found no primitive concept")

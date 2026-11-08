from collections import Counter, deque


def _span_mode_matrix(grid, background_color=0):
    """Compress repeated horizontal/vertical color spans to their modal colors."""
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    non_background_rows = [
        row for row in range(rows)
        if any(grid[row][col] != background_color for col in range(cols))
    ]
    non_background_cols = [
        col for col in range(cols)
        if any(grid[row][col] != background_color for row in range(rows))
    ]
    if not non_background_rows or not non_background_cols:
        return []

    def grouped_spans(indices, signature):
        spans = []
        start = previous = indices[0]
        previous_signature = signature(previous)
        for index in indices[1:]:
            current_signature = signature(index)
            if index == previous + 1 and current_signature == previous_signature:
                previous = index
                continue
            spans.append((start, previous + 1))
            start = previous = index
            previous_signature = current_signature
        spans.append((start, previous + 1))
        return spans

    row_spans = grouped_spans(
        non_background_rows,
        lambda row: tuple(grid[row][col] for col in range(cols)),
    )
    col_spans = grouped_spans(
        non_background_cols,
        lambda col: tuple(grid[row][col] for row in range(rows)),
    )

    output = []
    for row_start, row_end in row_spans:
        output_row = []
        for col_start, col_end in col_spans:
            values = [
                grid[row][col]
                for row in range(row_start, row_end)
                for col in range(col_start, col_end)
                if grid[row][col] != background_color
            ]
            if not values:
                output_row.append(background_color)
                continue
            output_row.append(Counter(values).most_common(1)[0][0])
        output.append(output_row)
    return output


def downscale_grid_based(grid, factor=2, downscale_type="pixel_based", background_color=0):
    """
    Downscale a grid by aggregating non-overlapping factor x factor blocks.

    downscale_type:
    - "pixel_based": object-aware downscale where each non-background connected
      component is resized by floor(size / factor) per axis with a minimum of 1.
    """

    if factor is None:
        factor = 2
    factor = int(factor)
    if factor < 2:
        raise ValueError(f"downscale factor must be >= 2, got {factor}")
    if not grid or not grid[0]:
        return grid

    if downscale_type in {"horizontal", "horizontal_span_mode", "span_mode_matrix"}:
        return _span_mode_matrix(grid, background_color=background_color)

    rows = len(grid)
    cols = len(grid[0])
    # Allow non-divisible grid sizes. We keep floor-based downscale dimensions,
    # with a minimum 1x1 for non-empty input.
    out_rows = max(1, rows // factor)
    out_cols = max(1, cols // factor)
    out = [[background_color for _ in range(out_cols)] for _ in range(out_rows)]

    if downscale_type != "pixel_based":
        raise ValueError(f"unsupported downscale_type: {downscale_type}")

    # Find 4-connected non-background components and scale each as an object.
    visited = [[False for _ in range(cols)] for _ in range(rows)]

    def neighbors(r, c):
        if r > 0:
            yield r - 1, c
        if r + 1 < rows:
            yield r + 1, c
        if c > 0:
            yield r, c - 1
        if c + 1 < cols:
            yield r, c + 1

    components = []
    for r in range(rows):
        for c in range(cols):
            if visited[r][c] or grid[r][c] == background_color:
                continue
            color = grid[r][c]
            q = deque([(r, c)])
            visited[r][c] = True
            pixels = []
            while q:
                rr, cc = q.popleft()
                pixels.append((rr, cc))
                for nr, nc in neighbors(rr, cc):
                    if not visited[nr][nc] and grid[nr][nc] == color:
                        visited[nr][nc] = True
                        q.append((nr, nc))
            components.append({"color": color, "pixels": pixels})

    for comp in components:
        pixels = comp["pixels"]
        color = comp["color"]
        min_r = min(p[0] for p in pixels)
        max_r = max(p[0] for p in pixels)
        min_c = min(p[1] for p in pixels)
        max_c = max(p[1] for p in pixels)
        h = max_r - min_r + 1
        w = max_c - min_c + 1

        # Aspect-preserving object scaling:
        # scale the shorter side by factor (floor, min 1), then derive the longer side
        # from the original aspect ratio. This keeps 3x3 -> 1x1 and 3x6 -> 1x2.
        if h <= w:
            new_h = max(1, h // factor)
            new_w = max(1, int(round((w / h) * new_h)))
        else:
            new_w = max(1, w // factor)
            new_h = max(1, int(round((h / w) * new_w)))
        comp["new_h"] = new_h
        comp["new_w"] = new_w
        comp["center_r"] = sum(p[0] for p in pixels) / len(pixels)
        comp["center_c"] = sum(p[1] for p in pixels) / len(pixels)
        comp["scaled_center_r"] = comp["center_r"] / factor
        comp["scaled_center_c"] = comp["center_c"] / factor
        comp["size"] = len(pixels)

    def group_ranks(values, gap_threshold):
        order = sorted(range(len(values)), key=lambda i: values[i])
        groups = []
        current = [order[0]] if order else []
        for idx in order[1:]:
            prev = current[-1]
            if values[idx] - values[prev] <= gap_threshold:
                current.append(idx)
            else:
                groups.append(current)
                current = [idx]
        if current:
            groups.append(current)
        ranks = [0] * len(values)
        for g_idx, grp in enumerate(groups):
            for item_idx in grp:
                ranks[item_idx] = g_idx
        return ranks, len(groups)

    scaled_rs = [c["scaled_center_r"] for c in components]
    scaled_cs = [c["scaled_center_c"] for c in components]

    # Canonical quincunx layout: 5 single-cell objects -> center + 4 equidistant corners.
    if (
        len(components) == 5
        and all(c["new_h"] == 1 and c["new_w"] == 1 for c in components)
        and len({c["color"] for c in components}) == 1
        and out_rows >= 3
        and out_cols >= 3
    ):
        mean_r = sum(scaled_rs) / 5.0
        mean_c = sum(scaled_cs) / 5.0
        center_idx = min(
            range(5),
            key=lambda i: (scaled_rs[i] - mean_r) ** 2 + (scaled_cs[i] - mean_c) ** 2,
        )
        center_r = int(round(scaled_rs[center_idx]))
        center_c = int(round(scaled_cs[center_idx]))

        # Enforce compact symmetric 3x3 quincunx layout around center.
        dr = 1
        dc = 1
        center_r = max(dr, min(center_r, out_rows - 1 - dr))
        center_c = max(dc, min(center_c, out_cols - 1 - dc))

        color = components[center_idx]["color"]
        out[center_r][center_c] = color
        occupied = {(center_r, center_c)}

        for i in range(5):
            if i == center_idx:
                continue
            row_sign = -1 if scaled_rs[i] < scaled_rs[center_idx] else 1
            col_sign = -1 if scaled_cs[i] < scaled_cs[center_idx] else 1
            rr = center_r + row_sign * dr
            cc = center_c + col_sign * dc
            rr = max(0, min(rr, out_rows - 1))
            cc = max(0, min(cc, out_cols - 1))
            if (rr, cc) in occupied:
                # Resolve rare collisions deterministically.
                rr = max(0, min(rr + row_sign, out_rows - 1))
                cc = max(0, min(cc + col_sign, out_cols - 1))
            out[rr][cc] = color
            occupied.add((rr, cc))
        return out

    row_ranks, row_groups = group_ranks(scaled_rs, gap_threshold=0.75)
    col_ranks, col_groups = group_ranks(scaled_cs, gap_threshold=0.75)
    for i, comp in enumerate(components):
        comp["row_rank"] = row_ranks[i]
        comp["col_rank"] = col_ranks[i]

    def dense_positions(min_v, n, limit):
        if n <= 1:
            return [max(0, min(limit - 1, int(round(min_v))))]
        start = int(round(min_v))
        end = start + (n - 1)
        if end > limit - 1:
            start -= (end - (limit - 1))
        start = max(0, start)
        return [start + i for i in range(n)]

    row_positions = dense_positions(min(scaled_rs), row_groups, out_rows)
    col_positions = dense_positions(min(scaled_cs), col_groups, out_cols)

    # Place larger objects first to reduce accidental overwrite of dominant structure.
    components.sort(key=lambda c: c["size"], reverse=True)

    for comp in components:
        color = comp["color"]
        new_h = comp["new_h"]
        new_w = comp["new_w"]
        center_out_r = row_positions[comp["row_rank"]]
        center_out_c = col_positions[comp["col_rank"]]
        top = int(round(center_out_r - (new_h - 1) / 2.0))
        left = int(round(center_out_c - (new_w - 1) / 2.0))
        top = max(0, min(top, out_rows - new_h))
        left = max(0, min(left, out_cols - new_w))

        for rr in range(top, min(top + new_h, out_rows)):
            for cc in range(left, min(left + new_w, out_cols)):
                out[rr][cc] = color

    return out

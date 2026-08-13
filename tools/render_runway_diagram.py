import math


def parse_magnetic_variation(mag_var_str: str | None) -> float:
    """
    Parse magnetic variation string like "10W" or "5E" to signed degrees.

    Args:
        mag_var_str: string like "10W" (10 degrees west = subtract) or "5E" (5 degrees east = add)

    Returns:
        signed float: positive = east, negative = west. Returns 0 if parsing fails.
    """
    if not mag_var_str:
        return 0

    mag_var_str = mag_var_str.strip()
    if not mag_var_str:
        return 0

    try:
        # Extract numeric part and direction
        direction = mag_var_str[-1].upper()
        value_str = mag_var_str[:-1].strip()
        value = float(value_str)

        # W (west) = subtract, E (east) = add
        if direction == 'W':
            return -value
        elif direction == 'E':
            return value
        else:
            return 0
    except (ValueError, IndexError):
        return 0


def compute_magnetic_heading(true_heading: float, magnetic_variation: float) -> float:
    """
    Convert true heading to magnetic heading.

    Magnetic heading = True heading - Magnetic variation
    (Variation is positive for east, negative for west)

    Args:
        true_heading: degrees (0-360)
        magnetic_variation: signed degrees from parse_magnetic_variation

    Returns:
        magnetic heading in range 0-360
    """
    magnetic_heading = (true_heading - magnetic_variation) % 360
    return magnetic_heading


def render_runway_svg(airport: dict) -> str:
    """
    Generate SVG diagram for an airport's runways.

    Args:
        airport: dict with keys 'ident', 'runways', 'runway_ends', 'magnetic_variation'
                 runways: list of {id, length_ft, width_ft, surface, condition}
                 runway_ends: dict mapping (ident, id) -> list of {end, true_heading, ils, displaced_threshold_ft, ...}
                 magnetic_variation: string like "10W" or "5E"

    Returns:
        SVG string with runways, labels, ILS indicators, and displaced threshold marks.
        The viewBox is computed to fit tightly around the actual drawn geometry.
    """
    if not airport.get("runways"):
        return _empty_svg()

    # Calculate scale based on runway geometry — draw into a virtual 500px space
    runways = airport["runways"]
    draw_size = 500
    scale = 1.0

    max_length = max(r.get("length_ft", 0) for r in runways) or 5000
    if max_length > draw_size:
        scale = draw_size / max_length * 0.8

    # Parse magnetic variation once for the airport
    mag_var_str = airport.get("magnetic_variation", "")
    magnetic_variation = parse_magnetic_variation(mag_var_str)

    # Color mapping for surface types
    surface_colors = {
        "asphalt": "#4a4a4a",
        "concrete": "#b0b0b0",
        "grass": "#7cb342",
        "gravel": "#c9a961",
        "water": "#2196f3",
        None: "#9e9e9e",
    }

    # Center point for drawing (everything is placed relative to this)
    cx, cy = 0.0, 0.0

    # --- First pass: compute geometry so we can build a tight bounding box ---
    runway_geom = []
    for i, runway in enumerate(runways):
        rwy_id = runway.get("id", f"RWY{i}")
        length_ft = runway.get("length_ft", 5000)
        width_ft = runway.get("width_ft", 100)
        surface = runway.get("surface", "asphalt").lower()
        color = surface_colors.get(surface, surface_colors[None])

        ends_key = (airport.get("ident"), rwy_id)
        ends = airport.get("runway_ends", {}).get(ends_key, [])
        heading_1 = ends[0].get("true_heading") if ends else None
        heading_1 = heading_1 if heading_1 is not None else 0

        heading_rad = math.radians(heading_1)
        length_px = length_ft * scale
        perp_rad = heading_rad + math.pi / 2

        x1 = cx - length_px / 2 * math.cos(heading_rad)
        y1 = cy - length_px / 2 * math.sin(heading_rad)
        x2 = cx + length_px / 2 * math.cos(heading_rad)
        y2 = cy + length_px / 2 * math.sin(heading_rad)

        runway_geom.append({
            "rwy_id": rwy_id, "length_ft": length_ft, "width_ft": width_ft,
            "color": color, "ends": ends,
            "heading_1": heading_1, "heading_rad": heading_rad, "perp_rad": perp_rad,
            "length_px": length_px,
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        })

    # Compute bounding box across all runway endpoints (with label headroom)
    PAD = 50  # padding around drawn content
    all_x = [g["x1"] for g in runway_geom] + [g["x2"] for g in runway_geom]
    all_y = [g["y1"] for g in runway_geom] + [g["y2"] for g in runway_geom]
    min_x = min(all_x) - PAD
    max_x = max(all_x) + PAD
    min_y = min(all_y) - PAD
    max_y = max(all_y) + PAD

    vb_w = max_x - min_x
    vb_h = max_y - min_y

    # --- Build SVG with tight viewBox ---
    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x:.1f} {min_y:.1f} {vb_w:.1f} {vb_h:.1f}" width="100%" style="max-width:600px;display:block">',
        '<style>',
        '.rwy-line { stroke-width: 8; fill: none; cursor: pointer; }',
        '.rwy-line:hover { stroke-width: 12; opacity: 0.8; }',
        '.rwy-label { font-size: 14px; font-weight: bold; font-family: monospace; }',
        '.rwy-heading { font-size: 11px; font-family: monospace; }',
        '.rwy-ils { font-size: 10px; font-weight: bold; fill: #d32f2f; }',
        '.rwy-displaced-tick { stroke: #ff9800; stroke-width: 2; }',
        '</style>',
        f'<rect x="{min_x:.1f}" y="{min_y:.1f}" width="{vb_w:.1f}" height="{vb_h:.1f}" fill="#f5f5f5" />',
    ]

    # --- Second pass: emit SVG elements ---
    for g in runway_geom:
        rwy_id = g["rwy_id"]
        length_ft = g["length_ft"]
        width_ft = g["width_ft"]
        color = g["color"]
        ends = g["ends"]
        heading_1 = g["heading_1"]
        heading_2 = (heading_1 + 180) % 360
        heading_rad = g["heading_rad"]
        perp_rad = g["perp_rad"]
        x1, y1, x2, y2 = g["x1"], g["y1"], g["x2"], g["y2"]

        svg_lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" class="rwy-line" data-id="{rwy_id}" />'
        )

        label_x = (x1 + x2) / 2
        label_y = (y1 + y2) / 2
        svg_lines.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" '
            f'class="rwy-label" data-id="{rwy_id}">{rwy_id}</text>'
        )

        if ends:
            for end_idx, end_data in enumerate(ends):
                true_hdg = end_data.get("true_heading", heading_1 if end_idx == 0 else heading_2)
                ils = end_data.get("ils")
                displaced_threshold_ft = end_data.get("displaced_threshold_ft", 0)

                if end_idx == 0:
                    end_x, end_y = x1, y1
                    hdg_offset_y = -20
                else:
                    end_x, end_y = x2, y2
                    hdg_offset_y = 20

                mag_hdg = compute_magnetic_heading(true_hdg, magnetic_variation)
                heading_text = f"{int(true_hdg)}°T / {int(mag_hdg)}°M" if magnetic_variation != 0 else f"{int(true_hdg)}°T"

                svg_lines.append(
                    f'<text x="{end_x:.1f}" y="{end_y + hdg_offset_y:.1f}" text-anchor="middle" '
                    f'class="rwy-heading">{heading_text}</text>'
                )

                if ils:
                    svg_lines.append(
                        f'<text x="{end_x:.1f}" y="{end_y + hdg_offset_y + 15:.1f}" text-anchor="middle" '
                        f'class="rwy-ils">ILS</text>'
                    )

                if displaced_threshold_ft and displaced_threshold_ft > 0:
                    inset_px = displaced_threshold_ft * scale
                    inset_x = end_x + inset_px * math.cos(heading_rad) * (1 if end_idx == 0 else -1)
                    inset_y = end_y + inset_px * math.sin(heading_rad) * (1 if end_idx == 0 else -1)

                    tick_len = 15
                    tick_x1 = inset_x - tick_len / 2 * math.cos(perp_rad)
                    tick_y1 = inset_y - tick_len / 2 * math.sin(perp_rad)
                    tick_x2 = inset_x + tick_len / 2 * math.cos(perp_rad)
                    tick_y2 = inset_y + tick_len / 2 * math.sin(perp_rad)

                    svg_lines.append(
                        f'<line x1="{tick_x1:.1f}" y1="{tick_y1:.1f}" x2="{tick_x2:.1f}" y2="{tick_y2:.1f}" '
                        f'class="rwy-displaced-tick" />'
                    )
        else:
            svg_lines.append(
                f'<text x="{x1:.1f}" y="{y1 - 20:.1f}" text-anchor="middle" '
                f'class="rwy-heading">{int(heading_1)}°T</text>'
            )
            svg_lines.append(
                f'<text x="{x2:.1f}" y="{y2 + 20:.1f}" text-anchor="middle" '
                f'class="rwy-heading">{int(heading_2)}°T</text>'
            )

        svg_lines.append(
            f'<text x="{label_x:.1f}" y="{label_y + 20:.1f}" text-anchor="middle" '
            f'class="rwy-heading">{int(length_ft)}\' x {int(width_ft)}\'</text>'
        )

    svg_lines.append('</svg>')
    return "\n".join(svg_lines)


def _empty_svg():
    """Return a placeholder SVG for airports with no runway data."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">'
        '<rect width="200" height="200" fill="#f5f5f5" />'
        '<text x="100" y="100" text-anchor="middle" font-size="14" fill="#999">No runway data</text>'
        '</svg>'
    )

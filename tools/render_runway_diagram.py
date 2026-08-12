import math

def parse_magnetic_variation(mag_var_str):
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


def compute_magnetic_heading(true_heading, magnetic_variation):
    """
    Convert true heading to magnetic heading.

    Magnetic heading = True heading + Magnetic variation
    (Variation is positive for east, negative for west)

    Args:
        true_heading: degrees (0-360)
        magnetic_variation: signed degrees from parse_magnetic_variation

    Returns:
        magnetic heading in range 0-360
    """
    magnetic_heading = (true_heading + magnetic_variation) % 360
    return magnetic_heading


def render_runway_svg(airport):
    """
    Generate SVG diagram for an airport's runways.

    Args:
        airport: dict with keys 'ident', 'runways', 'runway_ends', 'magnetic_variation'
                 runways: list of {id, length_ft, width_ft, surface, condition}
                 runway_ends: dict mapping (ident, id) -> list of {end, true_heading, ils, displaced_threshold_ft, ...}
                 magnetic_variation: string like "10W" or "5E"

    Returns:
        SVG string with runways, labels, ILS indicators, and displaced threshold marks.
    """
    if not airport.get("runways"):
        return _empty_svg()

    # Calculate SVG canvas size based on runway geometry
    runways = airport["runways"]
    width_svg = 600
    height_svg = 600
    scale = 1.0  # 1 ft = 1 px (will adjust for large airports)

    # Adjust scale if airport is very large
    max_length = max(r.get("length_ft", 0) for r in runways) or 5000
    if max_length > width_svg:
        scale = width_svg / max_length * 0.8

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

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_svg} {height_svg}" width="{width_svg}" height="{height_svg}">',
        '<style>',
        '.rwy-line { stroke-width: 8; fill: none; cursor: pointer; }',
        '.rwy-line:hover { stroke-width: 12; opacity: 0.8; }',
        '.rwy-label { font-size: 14px; font-weight: bold; font-family: monospace; }',
        '.rwy-heading { font-size: 11px; font-family: monospace; }',
        '.rwy-ils { font-size: 10px; font-weight: bold; fill: #d32f2f; }',
        '.rwy-displaced-tick { stroke: #ff9800; stroke-width: 2; }',
        '</style>',
        f'<rect width="{width_svg}" height="{height_svg}" fill="#f5f5f5" />',
    ]

    # Center point for drawing
    cx, cy = width_svg / 2, height_svg / 2

    # Render each runway
    for i, runway in enumerate(runways):
        rwy_id = runway.get("id", f"RWY{i}")
        length_ft = runway.get("length_ft", 5000)
        width_ft = runway.get("width_ft", 100)
        surface = runway.get("surface", "asphalt").lower()
        color = surface_colors.get(surface, surface_colors[None])

        # Get runway heading from runway_ends
        ends_key = (airport.get("ident"), rwy_id)
        ends = airport.get("runway_ends", {}).get(ends_key, [])
        heading_1 = ends[0].get("true_heading") if ends else None
        heading_1 = heading_1 if heading_1 is not None else 0
        heading_2 = (heading_1 + 180) % 360

        # Convert heading to radians and calculate runway line endpoints
        heading_rad = math.radians(heading_1)
        length_px = length_ft * scale
        half_width_px = (width_ft / 2) * scale

        # Runway endpoints
        x1 = cx - length_px / 2 * math.cos(heading_rad)
        y1 = cy - length_px / 2 * math.sin(heading_rad)
        x2 = cx + length_px / 2 * math.cos(heading_rad)
        y2 = cy + length_px / 2 * math.sin(heading_rad)

        # Perpendicular offset for width
        perp_rad = heading_rad + math.pi / 2
        offset_x = half_width_px * math.cos(perp_rad)
        offset_y = half_width_px * math.sin(perp_rad)

        # Runway rectangle (as path for simplicity)
        svg_lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" class="rwy-line" data-id="{rwy_id}" />'
        )

        # Labels: runway ID at center
        label_x = (x1 + x2) / 2
        label_y = (y1 + y2) / 2
        svg_lines.append(
            f'<text x="{label_x}" y="{label_y}" text-anchor="middle" '
            f'class="rwy-label" data-id="{rwy_id}">{rwy_id}</text>'
        )

        # Headings at each end with ILS and displaced threshold
        if ends:
            for end_idx, end_data in enumerate(ends):
                true_hdg = end_data.get("true_heading", heading_1 if end_idx == 0 else heading_2)
                ils = end_data.get("ils")
                displaced_threshold_ft = end_data.get("displaced_threshold_ft", 0)

                # Choose endpoint
                if end_idx == 0:
                    end_x, end_y = x1, y1
                    hdg_offset_y = -20
                    text_offset = 5
                else:
                    end_x, end_y = x2, y2
                    hdg_offset_y = 20
                    text_offset = -5

                # Compute magnetic heading if variation available
                mag_hdg = compute_magnetic_heading(true_hdg, magnetic_variation)
                heading_text = f"{int(true_hdg)}°T / {int(mag_hdg)}°M" if magnetic_variation != 0 else f"{int(true_hdg)}°T"

                # Heading label
                svg_lines.append(
                    f'<text x="{end_x}" y="{end_y + hdg_offset_y}" text-anchor="middle" '
                    f'class="rwy-heading">{heading_text}</text>'
                )

                # ILS indicator if present
                if ils:
                    svg_lines.append(
                        f'<text x="{end_x}" y="{end_y + hdg_offset_y + 15}" text-anchor="middle" '
                        f'class="rwy-ils">ILS</text>'
                    )

                # Displaced threshold tick mark if present
                if displaced_threshold_ft and displaced_threshold_ft > 0:
                    # Calculate inset point from runway end
                    inset_px = displaced_threshold_ft * scale
                    inset_x = end_x + inset_px * math.cos(heading_rad) * (1 if end_idx == 0 else -1)
                    inset_y = end_y + inset_px * math.sin(heading_rad) * (1 if end_idx == 0 else -1)

                    # Perpendicular tick mark (offset perpendicular to runway)
                    tick_len = 15
                    tick_x1 = inset_x - tick_len / 2 * math.cos(perp_rad)
                    tick_y1 = inset_y - tick_len / 2 * math.sin(perp_rad)
                    tick_x2 = inset_x + tick_len / 2 * math.cos(perp_rad)
                    tick_y2 = inset_y + tick_len / 2 * math.sin(perp_rad)

                    svg_lines.append(
                        f'<line x1="{tick_x1}" y1="{tick_y1}" x2="{tick_x2}" y2="{tick_y2}" '
                        f'class="rwy-displaced-tick" />'
                    )
        else:
            # Fallback if no ends data
            svg_lines.append(
                f'<text x="{x1}" y="{y1 - 20}" text-anchor="middle" '
                f'class="rwy-heading">{int(heading_1)}°T</text>'
            )
            svg_lines.append(
                f'<text x="{x2}" y="{y2 + 20}" text-anchor="middle" '
                f'class="rwy-heading">{int(heading_2)}°T</text>'
            )

        # Length label
        svg_lines.append(
            f'<text x="{label_x}" y="{label_y + 20}" text-anchor="middle" '
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

import math

def render_runway_svg(airport):
    """
    Generate SVG diagram for an airport's runways.

    Args:
        airport: dict with keys 'ident', 'runways', 'runway_ends'
                 runways: list of {id, length_ft, width_ft, surface, condition}
                 runway_ends: dict mapping (ident, id) -> list of {end, true_heading, ...}

    Returns:
        SVG string with runways, labels, and interactive layers.
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

        # Headings at each end
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

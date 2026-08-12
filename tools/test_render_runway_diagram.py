from render_runway_diagram import render_runway_svg, parse_magnetic_variation, compute_magnetic_heading

def test_render_single_runway():
    """Test SVG output for a single runway."""
    airport = {
        "ident": "TEST",
        "runways": [
            {
                "id": "09",
                "length_ft": 5000,
                "width_ft": 100,
                "surface": "asphalt",
                "condition": "good",
            }
        ],
        "runway_ends": {
            ("TEST", "09"): [
                {
                    "end": "09",
                    "true_heading": 90,
                    "ils": None,
                    "displaced_threshold_ft": 0,
                    "traffic_pattern": "L",
                }
            ]
        },
    }
    svg = render_runway_svg(airport)
    assert "<svg" in svg
    assert "09" in svg
    assert "90" in svg
    assert "5000" in svg


def test_render_parallel_runways():
    """Test SVG output for parallel runways (01L, 01R) with ILS and displaced threshold."""
    airport = {
        "ident": "KORD",
        "magnetic_variation": "5W",  # 5 degrees west
        "runways": [
            {
                "id": "01L",
                "length_ft": 10000,
                "width_ft": 150,
                "surface": "asphalt",
                "condition": "good",
            },
            {
                "id": "01R",
                "length_ft": 10000,
                "width_ft": 150,
                "surface": "concrete",
                "condition": "good",
            },
        ],
        "runway_ends": {
            ("KORD", "01L"): [
                {"end": "01L", "true_heading": 10, "ils": "ILS", "displaced_threshold_ft": 0, "traffic_pattern": "L"},
                {"end": "19L", "true_heading": 190, "ils": None, "displaced_threshold_ft": 500, "traffic_pattern": "L"},
            ],
            ("KORD", "01R"): [
                {"end": "01R", "true_heading": 10, "ils": None, "displaced_threshold_ft": 0, "traffic_pattern": "L"},
                {"end": "19R", "true_heading": 190, "ils": "ILS", "displaced_threshold_ft": 0, "traffic_pattern": "L"},
            ],
        },
    }
    svg = render_runway_svg(airport)
    assert "01L" in svg
    assert "01R" in svg
    assert "#4a4a4a" in svg  # asphalt
    assert "#b0b0b0" in svg  # concrete

    # Verify ILS indicators are present
    assert svg.count("ILS") >= 2  # At least 2 ILS indicators (01L and 19R)

    # Verify magnetic headings are displayed (with variation)
    assert "°M" in svg  # Magnetic heading indicator
    assert "°T" in svg  # True heading indicator

    # Verify displaced threshold marks are rendered (orange color)
    assert "#ff9800" in svg  # Displaced threshold tick color


def test_parse_magnetic_variation():
    """Test magnetic variation parsing."""
    assert parse_magnetic_variation("5W") == -5  # West subtracts
    assert parse_magnetic_variation("5E") == 5   # East adds
    assert parse_magnetic_variation("10W") == -10
    assert parse_magnetic_variation("") == 0
    assert parse_magnetic_variation(None) == 0


def test_compute_magnetic_heading():
    """Test magnetic heading computation."""
    assert compute_magnetic_heading(90, 5) == 95    # 90 + 5 = 95
    assert compute_magnetic_heading(90, -5) == 85   # 90 - 5 = 85
    assert compute_magnetic_heading(350, 15) == 5   # 350 + 15 wraps to 5
    assert compute_magnetic_heading(10, 0) == 10    # No variation


if __name__ == "__main__":
    test_render_single_runway()
    print("✓ test_render_single_runway passed")

    test_render_parallel_runways()
    print("✓ test_render_parallel_runways passed")

    test_parse_magnetic_variation()
    print("✓ test_parse_magnetic_variation passed")

    test_compute_magnetic_heading()
    print("✓ test_compute_magnetic_heading passed")

    print("\nAll tests passed!")

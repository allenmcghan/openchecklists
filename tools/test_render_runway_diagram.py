from render_runway_diagram import render_runway_svg

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
    """Test SVG output for parallel runways (01L, 01R)."""
    airport = {
        "ident": "KORD",
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
            ],
            ("KORD", "01R"): [
                {"end": "01R", "true_heading": 10, "ils": "ILS", "displaced_threshold_ft": 0, "traffic_pattern": "L"},
            ],
        },
    }
    svg = render_runway_svg(airport)
    assert "01L" in svg
    assert "01R" in svg
    assert "#4a4a4a" in svg  # asphalt
    assert "#b0b0b0" in svg  # concrete

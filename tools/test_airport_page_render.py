from build_site import render_airport_page


def test_render_airport_page_basic():
    """Test that airport page includes required sections."""
    airport = {
        "ident": "KJFK",
        "icao": "KJFK",
        "name": "John F. Kennedy International Airport",
        "city": "New York",
        "state": "NY",
        "state_name": "New York",
        "elevation_ft": 13,
        "pattern_altitude_ft": 1500,
        "sectional": "New York",
        "lat": 40.6413,
        "lon": -73.7781,
        "frequencies": [
            {
                "frequency": "118.75",
                "use": "Tower",
                "facility": "Kennedy Tower",
                "callsign": "Kennedy",
                "hours": "24h",
            }
        ],
        "runways": [
            {
                "id": "04L",
                "length_ft": 11351,
                "width_ft": 200,
                "surface": "asphalt",
            }
        ],
        "runway_ends": {
            ("KJFK", "04L"): [
                {"end": "04L", "true_heading": 40, "ils": "ILS", "displaced_threshold_ft": 0, "traffic_pattern": "L"}
            ]
        },
        "remarks": [],
    }

    html = render_airport_page(airport, "2026-08-15")

    # Check required sections
    assert "KJFK" in html
    assert "Kennedy" in html
    assert "118.75" in html
    assert "04L" in html
    assert "<svg" in html  # SVG diagram
    assert 'id="weather"' in html  # Weather zone
    assert 'id="notams"' in html  # NOTAMs zone
    assert 'id="airspace"' in html  # Airspace zone
    assert "2026-08-15" in html  # Effective date


if __name__ == "__main__":
    test_render_airport_page_basic()
    print("✓ test_render_airport_page_basic passed")
    print("\nAll tests passed!")

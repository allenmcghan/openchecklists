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
            },
            {
                "frequency": "121.5",
                "use": "CTAF",
                "facility": "Kennedy CTAF",
                "callsign": "Kennedy",
                "hours": "continuous",
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

    # Check table structure
    assert "<thead>" in html
    assert "Frequency" in html
    assert "Navigation Aids" in html
    assert "Status" in html
    assert "Ownership" in html

    # Check frequency sort: CTAF should appear before Tower
    ctaf_pos = html.find("121.5")  # CTAF frequency
    tower_pos = html.find("118.75")  # Tower frequency
    assert ctaf_pos < tower_pos, "CTAF frequency should be sorted before Tower"


def test_render_airport_page_xss_protection():
    """Test that airport data is HTML-escaped to prevent XSS."""
    airport = {
        "ident": "KXSS",
        "name": "Test <script>alert('XSS')</script>",
        "city": "Evil & <img src=x onerror=alert(1)>",
        "state": "XX",
        "elevation_ft": 100,
        "lat": 40.0,
        "lon": -73.0,
        "frequencies": [
            {
                "frequency": "123.45",
                "use": "Tower<script>",
                "facility": "<b>Bad</b>",
                "callsign": "Test&Co",
                "hours": "24/7",
            }
        ],
        "runways": [],
        "remarks": [],
    }

    html = render_airport_page(airport, "2026-08-15")

    # Ensure dangerous content from user data is escaped, not executable
    # The onerror attribute value should appear escaped as &lt;img...&gt;, not as <img...>
    assert "<img src=x onerror=" not in html  # Raw dangerous tag should not appear
    assert "&lt;img" in html  # Should be HTML-escaped
    assert "&lt;script&gt;" in html  # Script tags should be escaped
    assert "&lt;b&gt;" in html  # B tags should be escaped


def test_render_airport_page_missing_coords():
    """Test that missing lat/lon coordinates don't crash with invalid JS."""
    airport = {
        "ident": "KNULL",
        "name": "No Coordinates Airport",
        "city": "Nowhere",
        "state": "XX",
        "elevation_ft": 100,
        "lat": "",  # Empty coordinates
        "lon": "",
        "frequencies": [],
        "runways": [],
        "remarks": [],
    }

    html = render_airport_page(airport, "2026-08-15")

    # Should not contain invalid setView
    assert "setView([, ], 14)" not in html
    # Should have error message instead
    assert "Map coordinates unavailable" in html or "error" in html.lower()


if __name__ == "__main__":
    test_render_airport_page_basic()
    print("✓ test_render_airport_page_basic passed")
    test_render_airport_page_xss_protection()
    print("✓ test_render_airport_page_xss_protection passed")
    test_render_airport_page_missing_coords()
    print("✓ test_render_airport_page_missing_coords passed")
    print("\nAll tests passed!")

"""Tests for airport page generation in the build pipeline."""

import json
import tempfile
from pathlib import Path

from build_site import render_airport_page


def test_airport_build_generates_files():
    """Test that build_airport_pages generates HTML files for airports."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create mock airport data
        airports = [
            {
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
                "magnetic_variation": "12W",
                "type": "airport",
                "use": "public",
                "owner": "public",
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
                        {"end": "04L", "true_heading": 40, "ils": "ILS", "displaced_threshold_ft": 0}
                    ]
                },
                "remarks": [],
            },
            {
                "ident": "KORD",
                "icao": "KORD",
                "name": "Chicago O'Hare International Airport",
                "city": "Chicago",
                "state": "IL",
                "state_name": "Illinois",
                "elevation_ft": 668,
                "pattern_altitude_ft": 2000,
                "sectional": "Chicago",
                "lat": 41.9742,
                "lon": -87.9073,
                "magnetic_variation": "6W",
                "type": "airport",
                "use": "public",
                "owner": "public",
                "frequencies": [
                    {
                        "frequency": "119.0",
                        "use": "Tower",
                        "facility": "ORD Tower",
                        "callsign": "O'Hare",
                        "hours": "24h",
                    }
                ],
                "runways": [
                    {
                        "id": "27L",
                        "length_ft": 13000,
                        "width_ft": 200,
                        "surface": "concrete",
                    }
                ],
                "runway_ends": {
                    ("KORD", "27L"): [
                        {"end": "27L", "true_heading": 270, "ils": "ILS", "displaced_threshold_ft": 0}
                    ]
                },
                "remarks": [],
            }
        ]

        effective_date = "2026-08-06"

        # Generate airport pages (simulating build_airport_pages function)
        out_dir = tmpdir / "airport"
        out_dir.mkdir(parents=True)

        for airport in airports:
            ident = airport["ident"].lower()
            html = render_airport_page(airport, effective_date)
            out_file = out_dir / f"{ident}.html"
            out_file.write_text(html, encoding="utf-8")

        # Assertions
        # 1. Output directory was created
        assert out_dir.exists()

        # 2. Files were generated for test airports
        assert (out_dir / "kjfk.html").exists()
        assert (out_dir / "kord.html").exists()

        # 3. File content checks
        kjfk_html = (out_dir / "kjfk.html").read_text()
        assert "KJFK" in kjfk_html
        assert "Kennedy" in kjfk_html
        assert "118.75" in kjfk_html  # Tower frequency
        assert "121.5" in kjfk_html   # CTAF frequency
        assert "<svg" in kjfk_html    # Runway diagram
        assert "2026-08-06" in kjfk_html  # Effective date

        kord_html = (out_dir / "kord.html").read_text()
        assert "KORD" in kord_html
        assert ("O'Hare" in kord_html or "O&#x27;Hare" in kord_html or "O&apos;Hare" in kord_html)
        assert "119.0" in kord_html
        assert "<svg" in kord_html

        # 4. Both files should have HTML structure
        assert kjfk_html.startswith("<!DOCTYPE html>")
        assert kord_html.startswith("<!DOCTYPE html>")


def test_airport_pages_include_weather_zones():
    """Test that generated airport pages have live data zones."""
    airport = {
        "ident": "KLAS",
        "icao": "KLAS",
        "name": "Harry Reid International Airport",
        "city": "Las Vegas",
        "state": "NV",
        "state_name": "Nevada",
        "elevation_ft": 2181,
        "pattern_altitude_ft": 3000,
        "sectional": "Las Vegas",
        "lat": 36.0794,
        "lon": -115.1537,
        "magnetic_variation": "11E",
        "type": "airport",
        "use": "public",
        "owner": "public",
        "frequencies": [],
        "runways": [],
        "runway_ends": {},
        "remarks": [],
    }

    html = render_airport_page(airport, "2026-08-06")

    # Check for live data zone IDs
    assert 'id="weather"' in html
    assert 'id="notams"' in html
    assert 'id="airspace"' in html
    assert 'id="fuel"' in html
    assert "loadLiveData" in html  # JavaScript function


def test_airport_pages_handle_missing_data():
    """Test graceful handling of incomplete airport data."""
    minimal_airport = {
        "ident": "KXXX",
        "name": "Test Airport",
        "city": "Test",
        "state": "XX",
        # Missing many fields
    }

    html = render_airport_page(minimal_airport, "2026-08-06")

    # Should still generate valid HTML
    assert "<!DOCTYPE html>" in html
    assert "KXXX" in html
    assert "Test Airport" in html
    # Should not crash with KeyError


if __name__ == "__main__":
    test_airport_build_generates_files()
    print("✓ test_airport_build_generates_files passed")
    test_airport_pages_include_weather_zones()
    print("✓ test_airport_pages_include_weather_zones passed")
    test_airport_pages_handle_missing_data()
    print("✓ test_airport_pages_handle_missing_data passed")
    print("\nAll tests passed!")

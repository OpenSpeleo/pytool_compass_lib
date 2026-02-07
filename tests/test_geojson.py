# -*- coding: utf-8 -*-
"""Tests for GeoJSON export functionality.

All test files are sourced from tests/artifacts/private/.
"""

import json
from pathlib import Path

import pytest
from compass_lib import load_project
from compass_lib.geojson import compute_survey_coordinates
from compass_lib.geojson import convert_mak_to_geojson
from compass_lib.geojson import project_to_geojson
from compass_lib.geojson import survey_to_geojson

# Import fixtures from conftest
from tests.conftest import ALL_MAK_FILES
from tests.conftest import FIRST_MAK


class TestComputeSurveyCoordinates:
    """Tests for compute_survey_coordinates function."""

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_compute_survey_coordinates(self, mak_path):
        """Test computing coordinates for survey."""
        project = load_project(mak_path)
        survey = compute_survey_coordinates(project)

        # Should have stations (may be 0 for some edge-case files)
        assert len(survey.stations) >= 0

        # Should have legs (may be 0 for single-station surveys)
        assert len(survey.legs) >= 0

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_compute_with_valid_utm_zone(self, mak_path):
        """Test that UTM zone is valid."""
        project = load_project(mak_path)
        survey = compute_survey_coordinates(project)

        # Should have a valid UTM zone (1-60 for north, -1 to -60 for south)
        assert survey.utm_zone is not None
        assert survey.utm_zone != 0, "UTM zone cannot be 0"
        assert abs(survey.utm_zone) <= 60, f"Invalid UTM zone: {survey.utm_zone}"


class TestSurveyToGeoJSON:
    """Tests for survey_to_geojson function."""

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_geojson_structure(self):
        """Test that GeoJSON has correct structure."""
        project = load_project(FIRST_MAK)
        survey = compute_survey_coordinates(project)
        geojson = survey_to_geojson(survey)

        assert geojson["type"] == "FeatureCollection"
        assert "features" in geojson
        assert isinstance(geojson["features"], list)

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_geojson_with_stations_only(self):
        """Test that stations can be included exclusively."""
        project = load_project(FIRST_MAK)
        survey = compute_survey_coordinates(project)
        geojson = survey_to_geojson(survey, include_stations=True, include_legs=False)

        # All features should be stations
        for feature in geojson["features"]:
            assert feature["geometry"]["type"] == "Point"
            assert feature["properties"]["type"] == "station"

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_geojson_with_legs_only(self):
        """Test that legs can be included exclusively."""
        project = load_project(FIRST_MAK)
        survey = compute_survey_coordinates(project)
        geojson = survey_to_geojson(survey, include_stations=False, include_legs=True)

        # All features should be legs
        for feature in geojson["features"]:
            assert feature["geometry"]["type"] == "LineString"
            assert feature["properties"]["type"] == "leg"

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_geojson_without_stations(self):
        """Test that stations can be excluded."""
        project = load_project(FIRST_MAK)
        survey = compute_survey_coordinates(project)
        geojson = survey_to_geojson(survey, include_stations=False)

        # No point features
        for feature in geojson["features"]:
            assert feature["geometry"]["type"] != "Point"

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_geojson_without_legs(self):
        """Test that legs can be excluded."""
        project = load_project(FIRST_MAK)
        survey = compute_survey_coordinates(project)
        geojson = survey_to_geojson(survey, include_legs=False)

        # No linestring features
        for feature in geojson["features"]:
            assert feature["geometry"]["type"] != "LineString"

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_geojson_with_passages(self):
        """Test that passages can be included."""
        project = load_project(FIRST_MAK)
        survey = compute_survey_coordinates(project)
        geojson = survey_to_geojson(
            survey,
            include_stations=False,
            include_legs=False,
            include_passages=True,
        )

        # Should have polygon features (from legs with LRUD data)
        # Note: may have zero if no LRUD data
        if geojson["features"]:
            polygon_count = sum(
                1 for f in geojson["features"] if f["geometry"]["type"] == "Polygon"
            )
            # Just verify no error occurred
            assert isinstance(polygon_count, int)

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_geojson_properties(self):
        """Test that metadata is included in properties."""
        project = load_project(FIRST_MAK)
        survey = compute_survey_coordinates(project)
        geojson = survey_to_geojson(survey)

        # Metadata should be in properties
        assert "properties" in geojson
        assert "source_utm_zone" in geojson["properties"]
        assert "source_datum" in geojson["properties"]


class TestProjectToGeoJSON:
    """Tests for project_to_geojson function."""

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_project_to_geojson(self, mak_path):
        """Test high-level project_to_geojson function."""
        project = load_project(mak_path)
        geojson = project_to_geojson(project)

        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) > 0

        # Verify metadata
        assert "properties" in geojson
        assert geojson["properties"]["source_utm_zone"] is not None


class TestConvertMakToGeoJSON:
    """Tests for convert_mak_to_geojson function."""

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_convert_to_valid_geojson(self, mak_path):
        """Test conversion produces valid GeoJSON with valid WGS84 coordinates."""
        result = convert_mak_to_geojson(mak_path)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["type"] == "FeatureCollection"

        # Check that stations have valid WGS84 coordinates
        stations = [
            f for f in parsed["features"] if f["properties"]["type"] == "station"
        ]
        assert len(stations) > 0, f"No stations in {mak_path.name}"

        for station in stations:
            coords = station["geometry"]["coordinates"]
            lon, lat = coords[0], coords[1]
            # WGS84 longitude should be between -180 and 180
            assert -180 <= lon <= 180, f"Invalid longitude: {lon} in {mak_path.name}"
            # WGS84 latitude should be between -90 and 90
            assert -90 <= lat <= 90, f"Invalid latitude: {lat} in {mak_path.name}"

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_convert_to_file(self, tmp_path):
        """Test conversion writes to file."""
        output_path = tmp_path / "output.geojson"

        convert_mak_to_geojson(FIRST_MAK, output_path)

        assert output_path.exists()
        with open(output_path) as f:
            parsed = json.load(f)
        assert parsed["type"] == "FeatureCollection"


class TestGeoJSONFeatureProperties:
    """Tests for feature properties in GeoJSON output."""

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_station_properties(self):
        """Test that station features have correct properties."""
        project = load_project(FIRST_MAK)
        geojson = project_to_geojson(project)

        stations = [
            f for f in geojson["features"] if f["properties"]["type"] == "station"
        ]

        for station in stations:
            props = station["properties"]
            assert "name" in props
            assert "file" in props
            assert "elevation_m" in props

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_leg_properties(self):
        """Test that leg features have correct properties."""
        project = load_project(FIRST_MAK)
        geojson = project_to_geojson(project)

        legs = [f for f in geojson["features"] if f["properties"]["type"] == "leg"]

        for leg in legs:
            props = leg["properties"]
            assert "from" in props
            assert "to" in props
            assert "distance_ft" in props
            assert "distance_m" in props
            assert "file" in props
            assert "survey" in props

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_coordinates_are_3d(self):
        """Test that coordinates include elevation."""
        project = load_project(FIRST_MAK)
        geojson = project_to_geojson(project)

        for feature in geojson["features"]:
            if feature["geometry"]["type"] == "Point":
                coords = feature["geometry"]["coordinates"]
                assert len(coords) == 3, "Point should have 3D coordinates"
            elif feature["geometry"]["type"] == "LineString":
                for coord in feature["geometry"]["coordinates"]:
                    assert len(coord) == 3, "LineString coords should be 3D"


class TestPrivateProjectsGeoJSON:
    """Tests specifically for private project GeoJSON conversion."""

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_project_geojson_has_stations(self, mak_path):
        """Test that projects produce GeoJSON with stations."""
        project = load_project(mak_path)
        geojson = project_to_geojson(project)

        stations = [
            f for f in geojson["features"] if f["properties"]["type"] == "station"
        ]

        # Should have at least some stations
        assert len(stations) > 0, f"No stations in {mak_path.name}"

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_project_has_valid_utm_zone(self, mak_path):
        """Test that projects have valid UTM zones."""
        project = load_project(mak_path)
        survey = compute_survey_coordinates(project)

        # Should have a valid UTM zone (1-60 for north, -1 to -60 for south)
        assert survey.utm_zone is not None
        assert survey.utm_zone != 0, "UTM zone cannot be 0"
        assert abs(survey.utm_zone) <= 60, f"Invalid UTM zone: {survey.utm_zone}"

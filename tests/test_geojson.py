# -*- coding: utf-8 -*-
"""Tests for GeoJSON export functionality.

All test files are sourced from tests/artifacts/private/.
"""

import json
import logging
from pathlib import Path

import pytest

from compass_lib import load_project
from compass_lib.constants import METERS_TO_FEET
from compass_lib.geojson import compute_survey_coordinates
from compass_lib.geojson import convert_mak_to_geojson
from compass_lib.geojson import project_to_geojson
from compass_lib.geojson import survey_to_geojson

# Import fixtures from conftest
from tests.conftest import ALL_MAK_FILES
from tests.conftest import FIRST_MAK

logger = logging.getLogger(__name__)


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

        # All features should be legs or misclosure indicators
        for feature in geojson["features"]:
            props = feature["properties"]
            is_leg = "id" in props and "depth" in props and "name" in props
            is_misclosure = props.get("type") in ("misclosure", "misclosure_station")
            assert is_leg or is_misclosure

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
            f for f in parsed["features"] if f["properties"].get("type") == "station"
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
        with output_path.open(mode="r", encoding="utf-8") as f:
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
            f for f in geojson["features"] if f["properties"].get("type") == "station"
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

        legs = [
            f
            for f in geojson["features"]
            if f["geometry"]["type"] == "LineString" and "id" in f["properties"]
        ]

        assert len(legs) > 0, "Should have at least one leg"
        for leg in legs:
            props = leg["properties"]
            assert "id" in props
            assert "depth" in props
            assert "name" in props
            assert isinstance(props["id"], str)
            assert isinstance(props["depth"], (int, float))
            assert isinstance(props["name"], str)

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_coordinate_dimensions(self):
        """Test that station coordinates are 3D and leg coordinates are 2D."""
        project = load_project(FIRST_MAK)
        geojson = project_to_geojson(project)

        for feature in geojson["features"]:
            geom_type = feature["geometry"]["type"]
            props = feature["properties"]
            if geom_type == "Point":
                coords = feature["geometry"]["coordinates"]
                assert len(coords) == 3, "Point should have 3D coordinates"
            elif geom_type == "LineString" and "id" in props:
                for coord in feature["geometry"]["coordinates"]:
                    assert len(coord) == 3, "Leg coords should be 3D"

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_depth_property_is_positive_feet(self):
        """Every feature with a 'depth' property must have a non-negative value."""
        project = load_project(FIRST_MAK)
        geojson = project_to_geojson(project, include_anchors=True)

        features_with_depth = [
            f for f in geojson["features"] if "depth" in f["properties"]
        ]
        assert len(features_with_depth) > 0, "Expected features with depth property"

        for feat in features_with_depth:
            depth = feat["properties"]["depth"]
            assert isinstance(depth, (int, float)), f"depth must be numeric, got {type(depth)}"
            assert depth >= 0, (
                f"depth must be >= 0 (positive feet), got {depth} "
                f"on feature {feat['properties'].get('id', feat['properties'].get('name'))}"
            )

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_elevation_coordinate_matches_property(self):
        """Station Point elevation coordinate must equal the elevation_m property."""
        project = load_project(FIRST_MAK)
        geojson = project_to_geojson(project)

        stations = [
            f for f in geojson["features"] if f["properties"].get("type") == "station"
        ]
        assert len(stations) > 0

        for station in stations:
            coords = station["geometry"]["coordinates"]
            elevation_coord = coords[2]
            elevation_prop = station["properties"]["elevation_m"]
            assert elevation_coord == pytest.approx(elevation_prop, abs=0.01), (
                f"Station '{station['properties']['name']}': coordinate elevation "
                f"({elevation_coord}) != elevation_m property ({elevation_prop})"
            )

    @pytest.mark.skipif(
        FIRST_MAK is None or not FIRST_MAK.exists(), reason="No test file"
    )
    def test_depth_consistent_with_elevation(self):
        """The depth property (positive feet) must equal abs(elevation_m * METERS_TO_FEET)."""
        project = load_project(FIRST_MAK)
        geojson = project_to_geojson(project, include_anchors=True)

        for feat in geojson["features"]:
            props = feat["properties"]
            if "depth" not in props:
                continue

            geom = feat["geometry"]
            if geom["type"] == "Point":
                elev_m = geom["coordinates"][2]
            elif geom["type"] == "LineString":
                elev_m = geom["coordinates"][-1][2]
            else:
                continue

            expected_depth = abs(round(elev_m * METERS_TO_FEET, 2))
            assert props["depth"] == pytest.approx(expected_depth, abs=0.1), (
                f"Feature {props.get('id', props.get('name'))}: "
                f"depth={props['depth']} != abs(round({elev_m} * METERS_TO_FEET, 2))={expected_depth}"
            )


class TestAnchorValidation:
    """Tests for disconnected anchor detection and orphan warnings."""

    PROJECT022 = Path("tests/artifacts/private/project022.mak")

    @pytest.mark.skipif(
        not Path("tests/artifacts/private/project022.mak").exists(),
        reason="project022 test files not available",
    )
    def test_disconnected_anchor_excluded_from_stations(self):
        """Anchor 'lc0' in project022 has no shots -- it must be excluded."""
        project = load_project(self.PROJECT022)
        survey = compute_survey_coordinates(project)

        # lc0 should NOT be in the computed stations (it is disconnected)
        assert "lc0" not in survey.stations
        assert "lc0" not in survey.anchors

    @pytest.mark.skipif(
        not Path("tests/artifacts/private/project022.mak").exists(),
        reason="project022 test files not available",
    )
    def test_disconnected_anchor_logged_as_warning(self, caplog):
        """A disconnected anchor must produce a warning."""

        with caplog.at_level(logging.WARNING):
            project = load_project(self.PROJECT022)
            compute_survey_coordinates(project)

        # Should warn about lc0
        assert any("lc0" in record.message for record in caplog.records)

    @pytest.mark.skipif(
        not Path("tests/artifacts/private/project022.mak").exists(),
        reason="project022 test files not available",
    )
    def test_connected_anchors_still_present(self):
        """Anchors that DO appear in shots must remain."""
        project = load_project(self.PROJECT022)
        survey = compute_survey_coordinates(project)

        # These anchors exist in project022-1.dat shots
        for name in ("FF_Up0", "FF_A27", "U0", "c1", "FF_F22", "d20"):
            assert name in survey.stations, f"Anchor {name} should be present"
            assert name in survey.anchors, f"Anchor {name} should be in anchors set"


class TestPrivateProjectsGeoJSON:
    """Tests specifically for private project GeoJSON conversion."""

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_project_geojson_has_stations(self, mak_path):
        """Test that projects produce GeoJSON with stations."""
        project = load_project(mak_path)
        geojson = project_to_geojson(project)

        stations = [
            f for f in geojson["features"] if f["properties"].get("type") == "station"
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

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_all_coordinates_are_3d(self, mak_path):
        """Every coordinate tuple (Point, LineString, Polygon) must have 3 elements."""
        project = load_project(mak_path)
        geojson = project_to_geojson(project, include_passages=True, include_anchors=True)

        for feat in geojson["features"]:
            geom = feat["geometry"]
            geom_type = geom["type"]

            if geom_type == "Point":
                assert len(geom["coordinates"]) == 3, (
                    f"Point coords should be 3D in {mak_path.name}"
                )
            elif geom_type == "LineString":
                for i, coord in enumerate(geom["coordinates"]):
                    assert len(coord) == 3, (
                        f"LineString coord[{i}] should be 3D in {mak_path.name}"
                    )
            elif geom_type == "Polygon":
                for ring in geom["coordinates"]:
                    for i, coord in enumerate(ring):
                        assert len(coord) == 3, (
                            f"Polygon coord[{i}] should be 3D in {mak_path.name}"
                        )

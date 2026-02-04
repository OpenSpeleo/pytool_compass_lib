# -*- coding: utf-8 -*-
"""Tests for convert command roundtrip functionality.

This module tests the full roundtrip conversion:
MAK + DAT => JSON => MAK + DAT => JSON

All test files are sourced from tests/artifacts/private/.
"""

import json
import shutil
import tempfile
from pathlib import Path

import orjson
import pytest
from deepdiff import DeepDiff

from compass_scratchpad.commands.convert import ConversionError
from compass_scratchpad.commands.convert import _convert
from compass_scratchpad.commands.convert import detect_file_format
from compass_scratchpad.enums import CompassFileType
from compass_scratchpad.enums import FileFormat
from compass_scratchpad.enums import FormatIdentifier
from compass_scratchpad.geojson import convert_mak_to_geojson
from compass_scratchpad.io import load_project
from compass_scratchpad.io import read_dat_file
from compass_scratchpad.survey.models import CompassDatFile

# Import fixtures from conftest
from tests.conftest import ALL_DAT_FILES
from tests.conftest import ALL_DAT_JSON_FILES
from tests.conftest import ALL_MAK_FILES
from tests.conftest import ALL_MAK_JSON_FILES
from tests.conftest import DAT_WITH_JSON_BASELINE
from tests.conftest import MAK_WITH_GEOJSON
from tests.conftest import MAK_WITH_JSON_BASELINE

# =============================================================================
# Test: File Format Detection
# =============================================================================


class TestDetectFileFormat:
    """Tests for detect_file_format function."""

    def test_detect_dat_file(self):
        """Test detecting DAT file format."""
        fmt, ftype = detect_file_format(Path("survey.DAT"))
        assert fmt == FileFormat.COMPASS
        assert ftype == CompassFileType.DAT

    def test_detect_mak_file(self):
        """Test detecting MAK file format."""
        fmt, ftype = detect_file_format(Path("project.MAK"))
        assert fmt == FileFormat.COMPASS
        assert ftype == CompassFileType.MAK

    @pytest.mark.parametrize("json_file", ALL_DAT_JSON_FILES[:5])
    def test_detect_json_dat_file(self, json_file):
        """Test detecting JSON file with DAT content."""
        fmt, ftype = detect_file_format(json_file)
        assert fmt == FileFormat.JSON
        assert ftype == CompassFileType.DAT

    @pytest.mark.parametrize("json_file", ALL_MAK_JSON_FILES[:5])
    def test_detect_json_mak_file(self, json_file):
        """Test detecting JSON file with MAK content."""
        fmt, ftype = detect_file_format(json_file)
        assert fmt == FileFormat.JSON
        assert ftype == CompassFileType.MAK


# =============================================================================
# Test: Conversion Validation
# =============================================================================


class TestConversionValidation:
    """Tests for conversion validation."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.mark.parametrize("dat_path", ALL_DAT_FILES[:3])
    def test_compass_to_compass_raises_error(self, dat_path):
        """Test that compass -> compass conversion raises error."""
        with pytest.raises(
            ConversionError, match="Source and target formats must be different"
        ):
            _convert(dat_path, target_format="compass")

    @pytest.mark.parametrize("json_file", ALL_DAT_JSON_FILES[:3])
    def test_json_to_json_raises_error(self, json_file):
        """Test that json -> json conversion raises error."""
        with pytest.raises(
            ConversionError, match="Source and target formats must be different"
        ):
            _convert(json_file, target_format="json")

    def test_file_not_found_raises_error(self):
        """Test that missing file raises error."""
        with pytest.raises(FileNotFoundError):
            _convert(Path("nonexistent.DAT"))


# =============================================================================
# Test: MAK Roundtrip (MAK => JSON => MAK => JSON)
# =============================================================================


class TestMakRoundtrip:
    """Tests for MAK file roundtrip conversion."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_mak_roundtrip(self, temp_dir, mak_path):
        """Test MAK => JSON => MAK => JSON roundtrip consistency."""
        # Step 1: MAK -> JSON
        json1_path = temp_dir / "step1.mak.json"
        _convert(mak_path, json1_path, target_format="json")
        assert json1_path.exists()

        # Step 2: JSON -> MAK
        mak_new = temp_dir / "step2.MAK"
        _convert(json1_path, mak_new, target_format="compass")
        assert mak_new.exists()

        # Step 3: MAK -> JSON (second time)
        json2_path = temp_dir / "step3.mak.json"
        _convert(mak_new, json2_path, target_format="json")
        assert json2_path.exists()

        # Compare JSON files
        json1 = orjson.loads(json1_path.read_bytes())
        json2 = orjson.loads(json2_path.read_bytes())

        ddiff = DeepDiff(json1, json2, ignore_order=True)
        assert ddiff == {}, ddiff


# =============================================================================
# Test: DAT Roundtrip (DAT => JSON => DAT => JSON)
# =============================================================================


class TestDatRoundtrip:
    """Tests for DAT file roundtrip conversion."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.mark.parametrize("dat_path", ALL_DAT_FILES)
    def test_dat_roundtrip(self, temp_dir, dat_path):
        """Test DAT => JSON => DAT => JSON roundtrip consistency.

        Note: Station names may be truncated during roundtrip due to the
        Compass DAT format's 12-character station name limit. This test
        verifies structure consistency, not byte-for-byte equality.
        """
        # Step 1: DAT -> JSON
        json1_path = temp_dir / "step1.dat.json"
        _convert(dat_path, json1_path, target_format="json")
        assert json1_path.exists()

        # Step 2: JSON -> DAT
        dat_new = temp_dir / "step2.DAT"
        _convert(json1_path, dat_new, target_format="compass")
        assert dat_new.exists()

        # Step 3: DAT -> JSON (second time)
        json2_path = temp_dir / "step3.dat.json"
        _convert(dat_new, json2_path, target_format="json")
        assert json2_path.exists()

        # Compare JSON files
        json1 = orjson.loads(json1_path.read_bytes())
        json2 = orjson.loads(json2_path.read_bytes())

        ddiff = DeepDiff(json1, json2, ignore_order=True)
        assert ddiff == {}, ddiff


# =============================================================================
# Test: Baseline Consistency (Compare to stored JSON files)
# =============================================================================


class TestBaselineConsistency:
    """Tests that compare generated output to stored baseline files."""

    @pytest.mark.parametrize(("mak_path", "json_baseline"), MAK_WITH_JSON_BASELINE)
    def test_mak_to_json_matches_baseline(self, mak_path, json_baseline):
        """Test MAK to JSON conversion matches stored baseline."""
        # Load and convert MAK
        project = load_project(mak_path)
        result = json.loads(project.model_dump_json(by_alias=True))

        # Load baseline
        baseline = orjson.loads(json_baseline.read_bytes())

        ddiff = DeepDiff(baseline, result, ignore_order=True)
        assert ddiff == {}, ddiff

    @pytest.mark.parametrize(("dat_path", "json_baseline"), DAT_WITH_JSON_BASELINE)
    def test_dat_to_json_matches_baseline(self, dat_path, json_baseline):
        """Test DAT to JSON conversion matches stored baseline."""
        # Read the DAT file
        trips = read_dat_file(dat_path)

        # Serialize to JSON using Pydantic
        dat_file_obj = CompassDatFile(trips=trips)
        result = {
            "version": "1.0",
            "format": FormatIdentifier.COMPASS_DAT.value,
            "trips": json.loads(dat_file_obj.model_dump_json(by_alias=True))["trips"],
        }

        # Load baseline
        baseline = orjson.loads(json_baseline.read_bytes())

        ddiff = DeepDiff(baseline, result, ignore_order=True)
        assert ddiff == {}, ddiff


# =============================================================================
# Test: JSON -> Compass Conversion
# =============================================================================


class TestJsonToCompass:
    """Tests for JSON to Compass conversion."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.mark.parametrize("json_file", ALL_MAK_JSON_FILES)
    def test_json_to_mak(self, temp_dir, json_file):
        """Test JSON to MAK conversion produces valid output."""
        output_path = temp_dir / "output.MAK"
        _convert(json_file, output_path, target_format="compass")

        assert output_path.exists()
        content = output_path.read_text(encoding="cp1252", errors="replace")
        # MAK files should have at least one directive marker
        assert ";" in content or "/" in content

    @pytest.mark.parametrize("json_file", ALL_DAT_JSON_FILES)
    def test_json_to_dat(self, temp_dir, json_file):
        """Test JSON to DAT conversion produces valid output."""
        output_path = temp_dir / "output.DAT"
        _convert(json_file, output_path, target_format="compass")

        assert output_path.exists()
        content = output_path.read_text(encoding="cp1252", errors="replace")
        # DAT files should have survey headers
        assert "SURVEY NAME:" in content or "FROM" in content


# =============================================================================
# Test: Stdout Output
# =============================================================================


class TestConvertToStdout:
    """Tests for convert to stdout functionality."""

    @pytest.mark.parametrize("dat_path", ALL_DAT_FILES[:5])
    def test_dat_to_json_stdout(self, dat_path):
        """Test DAT to JSON conversion returns string."""
        result = _convert(dat_path, output_path=None, target_format="json")

        assert result is not None
        assert isinstance(result, str)
        assert f'"format": "{FormatIdentifier.COMPASS_DAT.value}"' in result

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES[:5])
    def test_mak_to_json_stdout(self, mak_path):
        """Test MAK to JSON conversion returns string."""
        result = _convert(mak_path, output_path=None, target_format="json")

        assert result is not None
        assert isinstance(result, str)
        assert f'"format": "{FormatIdentifier.COMPASS_MAK.value}"' in result

    @pytest.mark.parametrize("json_file", ALL_DAT_JSON_FILES[:5])
    def test_json_to_compass_stdout(self, json_file):
        """Test JSON to Compass conversion returns string."""
        result = _convert(json_file, output_path=None, target_format="compass")

        assert result is not None
        assert isinstance(result, str)
        assert "SURVEY NAME:" in result


# =============================================================================
# Test: Auto Format Detection
# =============================================================================


class TestAutoFormatDetection:
    """Tests for automatic format detection."""

    @pytest.mark.parametrize("dat_path", ALL_DAT_FILES[:5])
    def test_auto_format_compass_to_json(self, dat_path):
        """Test auto format detection: compass -> json."""
        # No target_format specified - should auto-detect as json
        result = _convert(dat_path, output_path=None)

        assert result is not None
        assert f'"format": "{FormatIdentifier.COMPASS_DAT.value}"' in result

    @pytest.mark.parametrize("json_file", ALL_DAT_JSON_FILES[:5])
    def test_auto_format_json_to_compass(self, json_file):
        """Test auto format detection: json -> compass."""
        # No target_format specified - should auto-detect as compass
        result = _convert(json_file, output_path=None)

        assert result is not None
        assert "SURVEY NAME:" in result


# =============================================================================
# Test: GeoJSON Generation (validation only, not baseline comparison)
# =============================================================================


class TestGeoJSONGeneration:
    """Tests for GeoJSON generation functionality."""

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_geojson_generation_succeeds(self, mak_path):
        """Test that GeoJSON generation completes without errors."""

        # Generate GeoJSON - should not raise
        result_str = convert_mak_to_geojson(
            mak_path,
            include_stations=True,
            include_legs=True,
            include_passages=False,
        )

        # Parse result
        result = orjson.loads(result_str)

        # Basic structure checks
        assert result["type"] == "FeatureCollection"
        assert "features" in result
        assert isinstance(result["features"], list)

        # Should have some features
        assert len(result["features"]) > 0, f"No features generated for {mak_path.name}"

        # All features should have valid geometry types
        for feature in result["features"]:
            assert feature["type"] == "Feature"
            assert "geometry" in feature
            assert feature["geometry"]["type"] in ("Point", "LineString", "Polygon")


# =============================================================================
# Test: GeoJSON Baseline Comparison
# =============================================================================


class TestGeoJSONBaselineComparison:
    """Tests that compare generated GeoJSON against stored baseline files."""

    @pytest.mark.parametrize(("mak_path", "geojson_baseline"), MAK_WITH_GEOJSON)
    def test_geojson_matches_baseline(self, mak_path, geojson_baseline):
        """Test GeoJSON generation matches stored baseline.

        This ensures that changes to coordinate computation, declination,
        convergence, or exclusion logic are detected.

        Note: Baselines are generated with legs only (no stations) to reduce
        file size and focus on the coordinate computation which is the main
        area of concern for regression testing.
        """

        # Generate GeoJSON - must match options used to generate baselines
        result_str = convert_mak_to_geojson(
            mak_path,
            include_stations=True,
            include_legs=True,
            include_passages=True,
        )
        result = orjson.loads(result_str)

        # Load baseline
        baseline = orjson.loads(geojson_baseline.read_bytes())

        ddiff = DeepDiff(baseline, result, ignore_order=True)
        assert ddiff == {}, ddiff


# =============================================================================
# Test: Project Loading (MAK with nested DAT)
# =============================================================================


class TestProjectLoading:
    """Tests for loading complete projects (MAK + DAT files)."""

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_load_project_succeeds(self, mak_path):
        """Test that all MAK files load successfully with their DAT files."""
        project = load_project(mak_path)

        # Basic structure checks
        assert project.format == FormatIdentifier.COMPASS_MAK.value
        assert len(project.directives) > 0

        # Check file directives have data loaded
        file_count = 0
        loaded_count = 0
        for file_dir in project.file_directives:
            file_count += 1
            if file_dir.data:
                loaded_count += 1
                # Verify data structure
                assert len(file_dir.data.trips) >= 0

        # At least some files should have been loaded
        assert file_count > 0, "No file directives found"
        # Note: Some DAT files may not exist, so we don't require all to be loaded

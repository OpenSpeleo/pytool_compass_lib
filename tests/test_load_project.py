# -*- coding: utf-8 -*-
"""Tests for load_project functionality and nested models.

This module tests the hierarchical project loading where MAK files
include and load their referenced DAT files.
"""

import pytest

from compass_lib import load_project
from compass_lib import save_project
from compass_lib.io import CancellationToken
from compass_lib.project.models import CompassMakFile
from compass_lib.project.models import FileDirective
from compass_lib.project.models import LocationDirective
from compass_lib.survey.models import CompassDatFile

# Import fixtures from conftest
from tests.conftest import ALL_MAK_FILES
from tests.conftest import ARTIFACTS_DIR


class TestLoadProject:
    """Tests for load_project function."""

    def test_load_simple_mak(self):
        """Test loading a simple MAK file."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        assert isinstance(project, CompassMakFile)
        assert len(project.directives) > 0

    def test_load_project_file_directives(self):
        """Test that file directives are populated."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        # Should have at least one file directive
        file_directives = project.file_directives
        assert len(file_directives) >= 1

        # Each file directive should have the file name
        for fd in file_directives:
            assert isinstance(fd, FileDirective)
            assert fd.file is not None
            assert len(fd.file) > 0

    def test_load_project_with_dat_data(self):
        """Test that DAT file data is loaded into directives."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        # Find file directives with data
        loaded_files = [fd for fd in project.file_directives if fd.data is not None]

        # At least one DAT file should be loaded
        assert len(loaded_files) >= 1

        # Check the data structure
        for fd in loaded_files:
            assert isinstance(fd.data, CompassDatFile)
            assert hasattr(fd.data, "surveys")
            assert len(fd.data.surveys) >= 1

    def test_load_project_nested_surveys(self):
        """Test accessing surveys through the nested structure."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        total_surveys = 0
        total_shots = 0

        for fd in project.file_directives:
            if fd.data:
                for survey in fd.data.surveys:
                    total_surveys += 1
                    total_shots += len(survey.shots)
                    assert survey.header.survey_name is not None

        assert total_surveys >= 1
        assert total_shots >= 1

    def test_load_project_with_link_stations(self):
        """Test loading a project with link stations."""
        mak_path = ARTIFACTS_DIR / "link_stations.mak"
        project = load_project(mak_path)

        # Find file directives with link stations
        with_links = [fd for fd in project.file_directives if fd.link_stations]

        # Should have at least one with link stations
        assert len(with_links) >= 1

        # Check link station structure
        for fd in with_links:
            for ls in fd.link_stations:
                assert ls.name is not None
                assert len(ls.name) > 0

    def test_load_project_location_property(self):
        """Test accessing the project location."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        loc = project.location
        if loc:
            assert isinstance(loc, LocationDirective)
            assert loc.easting is not None
            assert loc.northing is not None
            assert loc.utm_zone >= 1

    def test_load_project_datum_property(self):
        """Test accessing the project datum."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        datum = project.datum
        if datum:
            assert isinstance(datum, str)
            assert len(datum) > 0

    def test_project_total_surveys(self):
        """Test the total_surveys property."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        total = project.total_surveys
        assert isinstance(total, int)
        assert total >= 1

    def test_project_total_shots(self):
        """Test the total_shots property."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        total = project.total_shots
        assert isinstance(total, int)
        assert total >= 1

    def test_project_get_all_stations(self):
        """Test getting all station names."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        stations = project.get_all_stations()
        assert isinstance(stations, set)
        assert len(stations) >= 1

    def test_project_iter_files(self):
        """Test iterating over file directives."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        file_count = 0
        for fd in project.iter_files():
            assert isinstance(fd, FileDirective)
            file_count += 1

        assert file_count == len(project.file_directives)


class TestCompassDatFile:
    """Tests for CompassDatFile model."""

    def test_dat_file_properties(self):
        """Test CompassDatFile helper properties."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        for fd in project.file_directives:
            if fd.data:
                dat = fd.data
                assert isinstance(dat.total_shots, int)
                assert isinstance(dat.survey_names, list)
                assert isinstance(dat.get_all_stations(), set)


class TestLoadProjectCancellation:
    """Tests for cancellation support."""

    def test_cancellation_token(self):
        """Test that cancellation token works."""
        token = CancellationToken()
        assert not token.cancelled

        token.cancel()
        assert token.cancelled

    def test_load_project_with_cancellation(self):
        """Test loading project with pre-cancelled token."""
        mak_path = ARTIFACTS_DIR / "simple.mak"
        token = CancellationToken()
        token.cancel()

        # Should raise InterruptedError
        with pytest.raises(InterruptedError):
            load_project(mak_path, cancellation=token)


class TestPrivateProjects:
    """Tests using the private project data."""

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_load_project(self, mak_path):
        """Test loading the project."""
        project = load_project(mak_path)

        assert isinstance(project, CompassMakFile)
        assert len(project.file_directives) >= 1

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_nested_data(self, mak_path):
        """Test accessing nested data in project."""
        project = load_project(mak_path)

        # Check that DAT files are loaded (at least one should have data)
        loaded_count = sum(1 for fd in project.file_directives if fd.data)
        assert loaded_count >= 1

        # Some projects may have missing DAT files, just ensure no errors

        # surveys/shots properties should work (may be 0 for some projects)
        assert project.total_surveys >= 0
        assert project.total_shots >= 0

    @pytest.mark.parametrize("mak_path", ALL_MAK_FILES)
    def test_stations(self, mak_path):
        """Test getting stations from project."""
        project = load_project(mak_path)

        stations = project.get_all_stations()
        # Some projects may have 0 or 1 station, just ensure no errors
        assert isinstance(stations, set)


class TestSaveProject:
    """Tests for save_project function."""

    def test_save_project(self, tmp_path):
        """Test saving a project."""
        # Load a project
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        # Save to a new location
        new_mak_path = tmp_path / "saved.mak"
        save_project(new_mak_path, project, save_dat_files=True)

        # MAK file should exist
        assert new_mak_path.exists()

        # DAT files should exist
        for fd in project.file_directives:
            if fd.data:
                dat_path = tmp_path / fd.file
                assert dat_path.exists(), f"DAT file {fd.file} should exist"

    def test_save_project_mak_only(self, tmp_path):
        """Test saving only the MAK file."""
        # Load a project
        mak_path = ARTIFACTS_DIR / "simple.mak"
        project = load_project(mak_path)

        # Save without DAT files
        new_mak_path = tmp_path / "saved.mak"
        save_project(new_mak_path, project, save_dat_files=False)

        # MAK file should exist
        assert new_mak_path.exists()

        # DAT files should NOT exist in the new location
        for fd in project.file_directives:
            if fd.data:
                dat_path = tmp_path / fd.file
                assert not dat_path.exists(), f"DAT file {fd.file} should not exist"

"""End-to-end Gaussian loop closure of source measurements through GeoJSON APIs."""

import pytest
from cave_closure import LoopClosureAlgorithm
from cave_closure import LoopClosureMode

from compass_lib.geojson import compute_survey_coordinates
from compass_lib.loop_closure import LoopClosure
from compass_lib.models import NEVLocation
from compass_lib.project.models import CompassMakFile
from compass_lib.project.models import FileDirective
from compass_lib.project.models import LinkStation
from compass_lib.project.models import UTMZoneDirective
from compass_lib.survey.models import CompassDatFile
from compass_lib.survey.models import CompassShot
from compass_lib.survey.models import CompassSurvey
from compass_lib.survey.models import CompassSurveyHeader


@pytest.mark.parametrize("algorithm", LoopClosureAlgorithm.variants())
def test_source_loop_closure_keeps_controls_and_measurements(algorithm):
    survey = CompassSurvey(
        header=CompassSurveyHeader(survey_name="Traverse"),
        shots=[
            CompassShot(
                from_station=u,
                to_station=v,
                distance=10.0,
                frontsight_azimuth=90.0,
                frontsight_inclination=0.0,
            )
            for u, v in [("A", "B"), ("B", "C")]
        ],
    )
    source = CompassMakFile(
        directives=[
            UTMZoneDirective(utm_zone=18),
            FileDirective(
                file="survey.dat",
                data=CompassDatFile(surveys=[survey]),
                link_stations=[
                    LinkStation(
                        name="A",
                        location=NEVLocation(
                            easting=500000.0,
                            northing=4400000.0,
                            elevation=0.0,
                            unit="m",
                        ),
                    ),
                    LinkStation(
                        name="C",
                        location=NEVLocation(
                            easting=500006.4,
                            northing=4400000.0,
                            elevation=0.0,
                            unit="m",
                        ),
                    ),
                ],
            ),
        ]
    )
    adjusted = compute_survey_coordinates(
        source,
        loop_closure=LoopClosure(
            mode=LoopClosureMode.SPATIAL,
            sigma_m=1.0,
            algorithm=algorithm,
            frame_corrections={("survey.dat", 0): (0.0, 0.0)},
        ),
    )
    assert adjusted.stations["A"].easting == 500000.0
    assert adjusted.stations["C"].easting == 500006.4
    middle = next(
        station for station in adjusted.stations.values() if station.name == "B"
    )
    assert middle.easting == pytest.approx(500003.2)
    # Colors are derived display metadata; measurement fields are unchanged.
    assert [(shot.length, shot.frontsight_azimuth) for shot in survey.shots] == [
        (10.0, 90.0),
        (10.0, 90.0),
    ]
    assert not adjusted.misclosures

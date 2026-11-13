"""Vendor-order and orientation tests independent of formatter/parser agreement."""

import math

import pytest
from cave_closure import LoopClosureAlgorithm
from cave_closure import LoopClosureMode

from compass_lib.geojson import compute_shot_delta
from compass_lib.loop_closure import normalized_delta
from compass_lib.loop_closure import prepare_loop_closure
from compass_lib.project.models import CompassMakFile
from compass_lib.project.models import FileDirective
from compass_lib.survey.format import format_survey_header
from compass_lib.survey.models import CompassDatFile
from compass_lib.survey.models import CompassShot
from compass_lib.survey.models import CompassSurvey
from compass_lib.survey.models import CompassSurveyHeader
from compass_lib.survey.parser import CompassSurveyParser


def test_native_correction_order_and_backsight_only_roundtrip():
    header = CompassSurveyHeader(
        frontsight_azimuth_correction=2.0,
        frontsight_inclination_correction=3.0,
        length_correction=4.0,
    )
    assert "CORRECTIONS: 2.00 3.00 4.00" in format_survey_header(header)
    parsed = CompassSurveyParser()._parse_survey_header_to_dict(  # noqa: SLF001 - header wire characterization
        "CAVE\nSURVEY NAME: A\nSURVEY DATE: 1 1 2026\n"
        "DECLINATION: 0 CORRECTIONS: 2 3 4 CORRECTIONS2: 5 6"
    )
    assert (
        parsed["frontsight_azimuth_correction"],
        parsed["frontsight_inclination_correction"],
        parsed["length_correction"],
    ) == (2.0, 3.0, 4.0)
    only = CompassSurveyHeader(
        backsight_azimuth_correction=5.0, backsight_inclination_correction=6.0
    )
    assert "CORRECTIONS2: 5.00 6.00" in format_survey_header(only)


@pytest.mark.parametrize("angle", [-60.0, -15.0, 0.0, 20.0, 75.0])
def test_reverse_backsights_negate_forward_vector(angle):
    shot = CompassShot(
        from_station="A",
        to_station="B",
        distance=10.0,
        frontsight_azimuth=30.0,
        frontsight_inclination=angle,
        backsight_azimuth=210.0,
        backsight_inclination=-angle,
    )
    forward = compute_shot_delta(
        shot, is_reverse=False, declination=3.0, convergence=1.0
    )
    reverse = compute_shot_delta(
        shot, is_reverse=True, declination=3.0, convergence=1.0
    )
    assert reverse == pytest.approx(tuple(-v for v in forward), abs=1e-12)


def test_calibration_is_derived_and_w_format_does_not_invent_depths():
    header = CompassSurveyHeader(
        frontsight_azimuth_correction=2.0,
        frontsight_inclination_correction=3.0,
        length_correction=4.0,
    )
    shot = CompassShot(
        from_station="A",
        to_station="B",
        distance=6.0,
        frontsight_azimuth=-2.0,
        frontsight_inclination=-3.0,
    )
    before = shot.model_dump()
    assert normalized_delta(
        shot, header, declination=0.0, convergence=0.0
    ) == pytest.approx((0.0, 3.048, 0.0))
    header.format_string = "W"
    assert normalized_delta(
        shot, header, declination=0.0, convergence=0.0
    ) == pytest.approx((0.0, 3.048, 0.0))
    assert shot.model_dump() == before


@pytest.mark.parametrize(
    "algorithm",
    [
        LoopClosureAlgorithm.LSE_REDUCED_PCG,
        LoopClosureAlgorithm.LSE_UNREDUCED_PCG,
        LoopClosureAlgorithm.LSE_SPARSE_QR,
        LoopClosureAlgorithm.LSE_SPARSE_CHOLESKY,
    ],
)
def test_repeated_reversed_protected_and_display_flags(algorithm):
    shots = [
        CompassShot(
            from_station="A",
            to_station="B",
            distance=10.0,
            frontsight_azimuth=90.0,
            frontsight_inclination=0.0,
            do_not_adjust=True,
        ),
        CompassShot(
            from_station="A",
            to_station="B",
            distance=11.0,
            frontsight_azimuth=90.0,
            frontsight_inclination=0.0,
            excluded_from_plotting=True,
        ),
        CompassShot(
            from_station="B",
            to_station="A",
            distance=12.0,
            frontsight_azimuth=270.0,
            frontsight_inclination=0.0,
            excluded_from_length=True,
        ),
        CompassShot(
            from_station="A",
            to_station="B",
            distance=500.0,
            frontsight_azimuth=90.0,
            frontsight_inclination=0.0,
            excluded_from_all_processing=True,
        ),
    ]
    source = CompassMakFile(
        directives=[
            FileDirective(
                file="a.dat",
                data=CompassDatFile(
                    surveys=[CompassSurvey(header=CompassSurveyHeader(), shots=shots)]
                ),
            )
        ]
    )
    before = source.directives[0].data.model_dump_json()
    snapshot = prepare_loop_closure(
        source,
        algorithm=algorithm,
        mode=LoopClosureMode.SPATIAL,
        sigma_m=1.0,
        frame_corrections={("a.dat", 0): (0.0, 0.0)},
    )
    result = snapshot.solve()
    assert len(result.observations) == 3
    points = dict(result.coordinates)
    assert math.dist(*points.values()) == pytest.approx(3.048)
    assert source.directives[0].data.model_dump_json() == before

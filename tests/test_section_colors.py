"""Section colors are topology-aware display metadata, never source data."""

from __future__ import annotations

import colorsys
import datetime
import json
from collections import deque
from itertools import islice
from itertools import pairwise
from typing import TYPE_CHECKING

import pytest

from compass_lib import section_colors
from compass_lib.commands.geojson import geojson
from compass_lib.constants import SURVEY_COLORS
from compass_lib.geojson import ComputedSurvey
from compass_lib.geojson import Station
from compass_lib.geojson import SurveyLeg
from compass_lib.geojson import build_station_graph
from compass_lib.geojson import compute_survey_coordinates
from compass_lib.geojson import convert_mak_to_geojson
from compass_lib.geojson import project_to_geojson
from compass_lib.geojson import survey_to_geojson
from compass_lib.io import load_project
from compass_lib.io import save_project
from compass_lib.models import NEVLocation
from compass_lib.project.models import CompassMakFile
from compass_lib.project.models import FileDirective
from compass_lib.project.models import LinkStation
from compass_lib.project.models import UTMZoneDirective
from compass_lib.section_colors import _additional_colors
from compass_lib.section_colors import assign_section_colors
from compass_lib.solver.noop import NoopSolver
from compass_lib.solver.sparse import SparseSolver
from compass_lib.survey.models import CompassDatFile
from compass_lib.survey.models import CompassShot
from compass_lib.survey.models import CompassSurvey
from compass_lib.survey.models import CompassSurveyHeader

if TYPE_CHECKING:
    from pathlib import Path

    from compass_lib.solver.base import SurveyAdjuster


def section(*edges: tuple[str, str], name: str = "Duplicate") -> CompassSurvey:
    return CompassSurvey(
        header=CompassSurveyHeader(survey_name=name, date=datetime.date(2020, 1, 1)),
        shots=[
            CompassShot(
                from_station_name=start,
                to_station_name=end,
                length=10,
                frontsight_azimuth=90,
                frontsight_inclination=0,
                left=2,
                right=2,
            )
            for start, end in edges
        ],
    )


def project(*sections: CompassSurvey) -> CompassMakFile:
    return CompassMakFile(
        directives=[
            UTMZoneDirective(utm_zone=18),
            FileDirective(
                file="synthetic.dat",
                data=CompassDatFile(surveys=list(sections)),
                link_stations=[
                    LinkStation(
                        name="A",
                        location=NEVLocation(
                            easting=500000, northing=4400000, elevation=0
                        ),
                    )
                ],
            ),
        ]
    )


def assign(survey_project: CompassMakFile) -> None:
    adjacency, _ = build_station_graph(survey_project)
    assign_section_colors(
        survey_project,
        ([entry[3] for entry in entries] for entries in adjacency.values()),
    )


def test_palette_and_overflow_colors_are_bright_and_saturated() -> None:
    overflow = list(islice(_additional_colors(), 4096))
    assert len(set(overflow)) == len(overflow)
    assert len(set(SURVEY_COLORS)) == len(SURVEY_COLORS)
    for color in [*SURVEY_COLORS, *overflow]:
        channels = [int(color[offset : offset + 2], 16) / 255 for offset in (1, 3, 5)]
        _, saturation, value = colorsys.rgb_to_hsv(*channels)
        assert saturation >= 0.8 or saturation == pytest.approx(0.8)
        assert value >= 0.9


def test_empty_project_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_choice(available: list[str]) -> str:
        pytest.fail("An empty project must not allocate colors")

    monkeypatch.setattr(section_colors.random, "choice", unexpected_choice)
    assign(project())


def test_long_chain_does_not_recurse() -> None:
    count = 1500  # Above Python's normal recursion limit.
    survey_project = project(*(section((str(i), str(i + 1))) for i in range(count)))
    assign(survey_project)
    sections = survey_project.file_directives[0].data.surveys
    assert all(s.color in SURVEY_COLORS for s in sections)
    assert all(left.color != right.color for left, right in pairwise(sections))


def test_rgb_enumerator_has_a_finite_scan_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(section_colors, "RGB_COLOR_COUNT", 1)
    assert list(_additional_colors()) == []


@pytest.mark.parametrize(
    "edges",
    [
        [("A", "B"), ("B", "C"), ("C", "D")],
        [("A", "B"), ("B", "C"), ("B", "D")],
        [("A", "B"), ("B", "C"), ("C", "A")],
        [("A", "B"), ("C", "D"), ("E", "F")],
    ],
)
def test_shared_station_sections_have_distinct_colors(
    edges: list[tuple[str, str]],
) -> None:
    survey_project = project(*(section(edge) for edge in edges))
    assign(survey_project)
    sections = survey_project.file_directives[0].data.surveys
    for index, edge in enumerate(edges):
        assert sections[index].color in SURVEY_COLORS
        for other_index, other in enumerate(edges):
            if index != other_index and set(edge) & set(other):
                assert sections[index].color != sections[other_index].color


def test_crowded_junction_extends_palette_instead_of_reusing_a_color() -> None:
    count = len(SURVEY_COLORS) + 5
    survey_project = project(*(section(("A", f"B{index}")) for index in range(count)))
    assign(survey_project)
    colors = [s.color for s in survey_project.file_directives[0].data.surveys]
    assert len(set(colors)) == count
    assert all(color.startswith("#") and len(color) == 7 for color in colors)


def test_linked_dat_sections_touch_but_same_names_in_separate_scopes_do_not() -> None:
    first = section(("A", "LOCAL"))
    second = section(("A", "LOCAL"))
    isolated = section(("LOCAL", "OTHER"))
    survey_project = project(first)
    survey_project.directives.extend(
        [
            FileDirective(
                file="linked.dat",
                data=CompassDatFile(surveys=[second]),
                link_stations=[LinkStation(name="A")],
            ),
            FileDirective(
                file="isolated.dat",
                data=CompassDatFile(surveys=[isolated]),
                link_stations=[LinkStation(name="UNUSED")],
            ),
        ]
    )
    adjacency, _ = build_station_graph(survey_project)
    owners = [{id(edge[3]) for edge in entries} for entries in adjacency.values()]
    assert any({id(first), id(second)} <= group for group in owners)
    assert all(id(isolated) not in group or len(group) == 1 for group in owners)
    assign(survey_project)
    assert first.color != second.color
    assert isolated.color in SURVEY_COLORS


def test_assignment_does_not_change_dat_serialization() -> None:
    survey_project = project(section(("A", "B")), section(("B", "C")))
    source = survey_project.file_directives[0].data.model_dump_json()
    assign(survey_project)
    assert survey_project.file_directives[0].data.model_dump_json() == source
    clone = survey_project.model_copy(deep=True)
    for item in clone.file_directives[0].data.surveys:
        item.color = "#000000"
    assign(clone)
    assigned = [s.color for s in clone.file_directives[0].data.surveys]
    assert all(color in SURVEY_COLORS for color in assigned)
    assert assigned[0] != assigned[1]


@pytest.mark.parametrize("solver", [None, NoopSolver(), SparseSolver()])
def test_color_is_carried_through_forward_reverse_and_secondary_propagation(
    solver: SurveyAdjuster | None,
) -> None:
    first = section(("A", "B"), ("B", "C"), name="First")
    reverse = section(("D", "C"), name="Reverse")
    secondary = section(("E", "F"), ("F", "G"), ("G", "E"), name="Separate")
    survey_project = project(first, reverse, secondary)
    survey_project.file_directives[0].link_stations.append(
        LinkStation(
            name="E",
            location=NEVLocation(easting=501000, northing=4400000, elevation=0),
        )
    )
    computed = compute_survey_coordinates(survey_project, solver=solver)
    expected = {s.header.survey_name: s.color for s in [first, reverse, secondary]}
    assert len(computed.legs) == 6
    assert all(leg.color == expected[leg.survey] for leg in computed.legs)
    assert first.color != reverse.color
    for color_by_origin in [True, False]:
        exported = survey_to_geojson(computed, color_by_origin=color_by_origin)
        legs = [f for f in exported["features"] if "depth" in f["properties"]]
        assert len(legs) == 6
        for feature in legs:
            assert (
                feature["properties"]["color"]
                == expected[feature["properties"]["name"]]
            )
            assert ("stroke" in feature["properties"]) == color_by_origin


def test_passages_and_clipped_fragments_keep_their_leg_color() -> None:
    survey_project = project(
        section(("A", "B"), ("B", "C"), name="Main"),
        section(("B", "D"), name="Branch"),
    )
    survey_project.file_directives[0].data.surveys[1].shots[0].frontsight_azimuth = 100
    computed = compute_survey_coordinates(survey_project)
    exported = survey_to_geojson(computed, include_passages=True)
    expected = {
        (leg.from_station.name, leg.to_station.name): leg.color for leg in computed.legs
    }
    passages = [
        f for f in exported["features"] if f["properties"].get("type") == "passage"
    ]
    assert passages
    for feature in passages:
        props = feature["properties"]
        assert props["color"] == expected[props["from"], props["to"]]


def test_exclusions_and_empty_sections_keep_existing_geometry_rules() -> None:
    visible = section(("A", "B"))
    hidden = section(("B", "C"))
    hidden.shots[0].excluded_from_plotting = True
    excluded = section(("B", "D"))
    excluded.shots[0].excluded_from_all_processing = True
    empty = section()
    survey_project = project(visible, hidden, excluded, empty)
    computed = compute_survey_coordinates(survey_project)
    assert visible.color != hidden.color
    assert all(s.color is not None for s in [visible, hidden, excluded, empty])
    assert len(computed.legs) == 2
    exported = survey_to_geojson(computed, include_stations=False)
    assert len(exported["features"]) == 1
    assert exported["features"][0]["properties"]["color"] == visible.color


def test_actual_clipped_passage_fragments_preserve_color() -> None:
    computed = ComputedSurvey(
        utm_zone=18,
        legs=[
            SurveyLeg(
                from_station=Station("A", 500000, 4400000, 0),
                to_station=Station("B", 500020, 4400000, 0),
                distance=65.6,
                azimuth=90,
                inclination=0,
                left=2,
                right=2,
                color="#ff0000",
            ),
            SurveyLeg(
                from_station=Station("C", 500010, 4399990, 0),
                to_station=Station("D", 500010, 4400010, 0),
                distance=65.6,
                azimuth=0,
                inclination=0,
                left=2,
                right=2,
                color="#0000ff",
            ),
        ],
    )
    exported = survey_to_geojson(
        computed, include_stations=False, include_legs=False, include_passages=True
    )
    assert len(exported["features"]) == 3  # Crossing passage is split in two.
    colors = [feature["properties"]["color"] for feature in exported["features"]]
    assert colors.count("#ff0000") == 1
    assert colors.count("#0000ff") == 2


def test_reloaded_sources_export_section_colors_without_changing_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic.mak"
    survey_project = project(section(("A", "B")), section(("B", "C")))
    save_project(source, survey_project)
    expected = json.loads(convert_mak_to_geojson(source, color_by_origin=False))
    assert all(
        "color" in feature["properties"]
        for feature in expected["features"]
        if feature["geometry"]["type"] == "LineString"
    )
    colors = [
        f["properties"]["color"]
        for f in expected["features"]
        if f["geometry"]["type"] == "LineString"
    ]
    assert len(colors) == 2
    assert colors[0] != colors[1]
    loaded = load_project(source)
    before = loaded.file_directives[0].data.model_dump_json()
    project_to_geojson(loaded)
    assert loaded.file_directives[0].data.model_dump_json() == before


def test_pass_limit_uses_vibrant_extras_without_color_conflicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(section_colors, "MAX_COLORING_PASSES", 1)
    count = len(SURVEY_COLORS) + 5
    survey_project = project(*(section(("A", f"B{i}")) for i in range(count)))
    assign(survey_project)
    colors = [s.color for s in survey_project.file_directives[0].data.surveys]
    assert None not in colors
    assert len(set(colors)) == count


def test_zero_pass_budget_still_colors_every_touching_section(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(section_colors, "MAX_COLORING_PASSES", 0)
    survey_project = project(*(section(("A", f"B{i}")) for i in range(4)))
    assign(survey_project)
    sections = survey_project.file_directives[0].data.surveys
    colors = [s.color for s in sections]
    assert None not in colors
    assert len(set(colors)) == 4
    assert not caplog.records


def test_no_improvement_exits_after_two_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draws: list[str] = []

    def choose(available: list[str]) -> str:
        draws.append(available[0])
        return available[0]

    monkeypatch.setattr(section_colors.random, "choice", choose)
    count = len(SURVEY_COLORS) + 1
    survey_project = project(*(section(("A", f"B{i}")) for i in range(count)))
    assign(survey_project)
    assert len(draws) == 2 * len(SURVEY_COLORS)
    colors = [s.color for s in survey_project.file_directives[0].data.surveys]
    assert None not in colors
    assert len(set(colors)) == count


def test_completion_stops_after_one_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    draws: list[str] = []

    def choose(available: list[str]) -> str:
        draws.append(available[0])
        return available[0]

    monkeypatch.setattr(section_colors.random, "choice", choose)
    survey_project = project(*(section(("A", f"B{i}")) for i in range(3)))
    assign(survey_project)
    assert len(draws) == 3
    assert len({s.color for s in survey_project.file_directives[0].data.surveys}) == 3


def test_equal_candidate_does_not_replace_the_previous_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    palette = SURVEY_COLORS[:2]
    monkeypatch.setattr(section_colors, "SURVEY_COLORS", palette)
    draws = deque([palette[0], palette[1], palette[1], palette[0]])

    def choose(available: list[str]) -> str:
        color = draws.popleft()
        assert color in available
        return color

    monkeypatch.setattr(section_colors.random, "choice", choose)
    survey_project = project(*(section(("A", f"B{i}")) for i in range(3)))
    assign(survey_project)
    sections = survey_project.file_directives[0].data.surveys
    assert not draws
    assert [s.color for s in sections[:2]] == list(palette)
    assert None not in {s.color for s in sections}
    assert len({s.color for s in sections}) == 3


def _crown_graph(count: int) -> tuple[list[CompassSurvey], list[list[CompassSurvey]]]:
    """Degree-two graph: greedy two-coloring can color four or all six vertices."""
    sections = [section() for _ in range(6 * count + 3)]
    pairs = [(0, 3), (0, 5), (2, 1), (2, 5), (4, 1), (4, 3)]
    owners = [
        [sections[6 * group + left], sections[6 * group + right]]
        for group in range(count)
        for left, right in pairs
    ]
    # A triangle remains incomplete with two colors even after every crown
    # improves, so the hard pass limit can be exercised independently of success.
    owners.extend(
        [
            [sections[-3], sections[-2]],
            [sections[-2], sections[-1]],
            [sections[-1], sections[-3]],
        ]
    )
    return sections, owners


def test_hard_pass_limit_stops_even_when_every_pass_improves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    palette = SURVEY_COLORS[:2]
    monkeypatch.setattr(section_colors, "SURVEY_COLORS", palette)
    limit = section_colors.MAX_COLORING_PASSES
    sections, owners = _crown_graph(limit)
    draws: deque[str] = deque()
    for pass_index in range(limit):
        for group in range(limit):
            pattern = [0, 1, 0, 1, 0, 1] if group < pass_index else [0, 0, 1, 1]
            draws.extend(palette[index] for index in pattern)
        draws.extend(palette)

    def choose(available: list[str]) -> str:
        color = draws.popleft()  # Any call beyond the pass limit fails the test.
        assert color in available
        return color

    monkeypatch.setattr(section_colors.random, "choice", choose)
    assign_section_colors(project(*sections), owners)
    assert not draws
    assert all(s.color is not None for s in sections)
    assert all(left.color != right.color for left, right in owners)


def test_worse_pass_keeps_best_assignment_before_safe_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    palette = SURVEY_COLORS[:2]
    monkeypatch.setattr(section_colors, "SURVEY_COLORS", palette)
    sections, owners = _crown_graph(2)
    first = [0, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0, 1]
    worse = [0, 0, 1, 1, 0, 0, 1, 1, 0, 1]
    draws = deque(palette[index] for index in first + worse)

    def choose(available: list[str]) -> str:
        color = draws.popleft()
        assert color in available
        return color

    monkeypatch.setattr(section_colors.random, "choice", choose)
    assign_section_colors(project(*sections), owners)
    assert not draws
    assert [s.color for s in sections[:6]] == [palette[i] for i in first[:6]]
    assert all(s.color is not None for s in sections)
    assert all(left.color != right.color for left, right in owners)


def test_fallback_budget_accounts_for_colors_already_in_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(section_colors, "MAX_COLORING_PASSES", 1)
    monkeypatch.setattr(section_colors, "SURVEY_COLORS", SURVEY_COLORS[:2])
    monkeypatch.setattr(
        section_colors, "_additional_colors", lambda: iter(SURVEY_COLORS[:3])
    )
    survey_project = project(*(section(("A", f"B{i}")) for i in range(3)))
    assign(survey_project)
    assert {s.color for s in survey_project.file_directives[0].data.surveys} == set(
        SURVEY_COLORS[:3]
    )


def test_unavailable_color_space_exits_safely_and_clears_stale_colors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Only physical color-space exhaustion may omit a color, not a pass limit.
    monkeypatch.setattr(section_colors, "MAX_COLORING_PASSES", 0)
    monkeypatch.setattr(section_colors, "_additional_colors", lambda: iter(()))
    survey_project = project(section(("A", "B")), section(("B", "C")))
    for item in survey_project.file_directives[0].data.surveys:
        item.color = "#000000"
    assign(survey_project)
    assert all(s.color is None for s in survey_project.file_directives[0].data.surveys)
    assert "RGB color space exhausted" in caplog.text


def test_cli_no_colors_keeps_section_colors_and_failed_input_keeps_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic.mak"
    target = tmp_path / "colors.geojson"
    save_project(source, project(section(("A", "B")), section(("B", "C"))))
    assert (
        geojson(["-i", str(source), "-o", str(target), "--no-colors", "--no-stations"])
        == 0
    )
    output = target.read_bytes()
    features = json.loads(output)["features"]
    assert len(features) == 2
    assert len({feature["properties"]["color"] for feature in features}) == 2
    assert all("stroke" not in feature["properties"] for feature in features)
    assert geojson(["-i", str(tmp_path / "missing.mak"), "-o", str(target)]) == 1
    assert target.read_bytes() == output

"""Bounded coloring passes respecting the computed station topology."""

from __future__ import annotations

import logging
import random
from itertools import islice
from typing import TYPE_CHECKING

from compass_lib.constants import SURVEY_COLOR_MIN_SATURATION
from compass_lib.constants import SURVEY_COLOR_MIN_VALUE
from compass_lib.constants import SURVEY_COLORS

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator

    from compass_lib.project.models import CompassMakFile
    from compass_lib.survey.models import CompassSurvey

logger = logging.getLogger(__name__)

MAX_COLORING_PASSES = 16
RGB_COLOR_COUNT = 1 << 24


def _additional_colors() -> Iterator[str]:
    """Visit distinct RGB values, accepting only bright, saturated colors."""
    for index in range(RGB_COLOR_COUNT):
        # The odd multiplier visits every RGB value once without a growing set.
        rgb = (0x68BDEB + index * 0x9E3779) % RGB_COLOR_COUNT
        channels = ((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)
        peak = max(channels)
        if peak / 255 < SURVEY_COLOR_MIN_VALUE:
            continue
        saturation = (peak - min(channels)) / peak
        if saturation >= SURVEY_COLOR_MIN_SATURATION:
            yield f"#{rgb:06x}"


def assign_section_colors(
    project: CompassMakFile,
    station_sections: Iterable[Iterable[CompassSurvey]],
) -> None:
    """Try random palette assignments in bounded passes, then use vivid extras.

    Each DAT survey block is a separate section, even when names repeat. The
    existing station graph supplies connectivity, including MAK station scopes.
    Only conflict-free candidates coloring more sections improve the assignment;
    no-progress and pass-budget exhaustion lead to a bounded fallback.
    """
    sections = [
        section
        for directive in project.file_directives
        if directive.data is not None
        for section in directive.data.surveys
    ]
    section_indices = {id(section): index for index, section in enumerate(sections)}
    neighbors: list[set[int]] = [set() for _ in sections]
    for owners in station_sections:
        indices = {section_indices[id(section)] for section in owners}
        for index in indices:
            neighbors[index].update(indices - {index})

    order = sorted(range(len(sections)), key=lambda index: -len(neighbors[index]))
    colors: dict[int, str] = {}
    for _ in range(MAX_COLORING_PASSES):
        candidate: dict[int, str] = {}
        for index in order:
            forbidden = {
                candidate[other] for other in neighbors[index] if other in candidate
            }
            available = [color for color in SURVEY_COLORS if color not in forbidden]
            if available:
                candidate[index] = random.choice(available)
        if len(candidate) <= len(colors):
            break
        colors = candidate
        if len(colors) == len(sections):
            break

    # Finish unresolved sections with distinct bright colors. The generator is
    # unique, so at most len(used) candidates can collide with assigned colors.
    # This input-sized bound completes the fallback without an arbitrary cap
    # leaving touching sections to render the same survey fallback color.
    used = set(colors.values())
    candidate_budget = len(sections) - len(colors) + len(used)
    extras = iter(islice(_additional_colors(), candidate_budget))
    for index in order:
        if index in colors:
            continue
        color = next((value for value in extras if value not in used), None)
        if color is None:
            logger.warning(
                "Vibrant RGB color space exhausted; %s sections use viewer fallback",
                len(sections) - len(colors),
            )
            break
        colors[index] = color
        used.add(color)

    for index, section in enumerate(sections):
        # Omit unassigned colors instead of exporting a conflicting color.
        section.color = colors.get(index)

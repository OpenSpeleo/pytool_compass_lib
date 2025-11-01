from __future__ import annotations

import contextlib
import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from compass_lib.constants import COMPASS_DATE_COMMENT_RE
from compass_lib.constants import COMPASS_END_OF_FILE
from compass_lib.constants import COMPASS_SECTION_NAME_RE
from compass_lib.constants import COMPASS_SECTION_SPLIT_RE
from compass_lib.constants import COMPASS_SHOT_FLAGS_RE
from compass_lib.enums import CompassFileType
from compass_lib.models import Survey
from compass_lib.models import SurveySection

if TYPE_CHECKING:
    from typing_extensions import Self


@dataclass
class CompassDataRow:
    """Basic Dataclass that represent one row of 'data' from the DAT file.
    This contains no validation logic, the validation is being performed by
    the PyDantic class: `ShotData`.
    The sole purpose of this class is to aggregate the parsing logic."""

    from_: str
    to: str
    length: float
    azimuth: float
    inclination: float
    left: float
    up: float
    down: float
    right: float

    # optional attributes
    azimuth2: float = 0.0
    inclination2: float = 0.0
    flags: str | None = None
    comment: str | None = None

    @classmethod
    def from_str_data(cls, str_data: str, header_row: str) -> Self:
        shot_data = str_data.split(maxsplit=9)

        instance = cls(*shot_data[:9])  # pyright: ignore[reportArgumentType]

        def split1_str(val: str | None) -> tuple[str, str | None]:
            """
            Splits the input string into at most two parts.

            Args:
                val (str): The string to be split.

            Returns:
                tuple[str]: A tuple containing the first part of the split string and
                            the second part if it exists, otherwise None.

            Raises:
                ValueError: If the input string is None.
            """
            if val is None:
                raise ValueError("Received a NoneValue.")

            rslt = val.split(maxsplit=1)
            if len(rslt) == 1:
                return rslt[0], None

            return rslt  # pyright: ignore[reportReturnType]

        with contextlib.suppress(IndexError):
            optional_data = shot_data[9]

            if "AZM2" in header_row:
                instance.azimuth2, optional_data = split1_str(optional_data)  # pyright: ignore[reportAttributeAccessIssue]

            if "INC2" in header_row:
                instance.inclination2, optional_data = split1_str(optional_data)  # pyright: ignore[reportAttributeAccessIssue]

            if (
                all(x in header_row for x in ["FLAGS", "COMMENTS"])
                and optional_data is not None
            ):
                if (
                    match := re.search(COMPASS_SHOT_FLAGS_RE, optional_data)
                ) is not None:
                    _, flag_str, comment = match.groups()
                    instance.comment = comment.strip() if comment != "" else None
                    instance.flags = flag_str

        # Input Normalization
        instance.azimuth = float(instance.azimuth)
        instance.azimuth = instance.azimuth % 360.0 if instance.azimuth >= 0 else 0.0

        instance.azimuth2 = float(instance.azimuth2)
        instance.azimuth2 = instance.azimuth2 % 360.0 if instance.azimuth2 >= 0 else 0.0

        return instance


class CompassParser:
    def __init__(self, *args: Any, **kwargs: dict[str, Any]) -> None:
        raise NotImplementedError(
            "This class is not meant to be instantiated directly."
        )

    @classmethod
    def load_dat_file(cls, filepath: str | Path) -> Survey:
        filepath = Path(filepath)

        if not filepath.is_file():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Ensure at least that the file type is valid
        with filepath.open(mode="r", encoding="windows-1252") as f:
            # Skip all the comments
            file_content = "".join(
                [line for line in f.readlines() if not line.startswith("/")]
            )

        file_content = file_content.split(COMPASS_END_OF_FILE, maxsplit=1)[0]
        raw_sections = [
            section.rstrip()
            for section in re.split(COMPASS_SECTION_SPLIT_RE, file_content)
            if section.rstrip() != ""
        ]

        try:
            return cls._parse_dat_file(raw_sections)
        except (UnicodeDecodeError, ValueError, IndexError, TypeError) as e:
            raise ValueError(f"Failed to parse file: `{filepath}`") from e

    @classmethod
    def _parse_date(cls, date_str: str) -> datetime.date:
        for date_format in ["%m %d %Y", "%m %d %y", "%d %m %Y", "%d %m %y"]:
            try:
                return datetime.datetime.strptime(date_str, date_format).date()
            except ValueError:  # noqa: PERF203
                continue
        raise ValueError("Unknown date format: `%s`", date_str)

    @classmethod
    def _parse_dat_file(cls, raw_sections: list[str]) -> Survey:
        survey_sections: list[SurveySection] = []
        for raw_section in raw_sections:
            section_data_iter = iter(raw_section.splitlines())

            # Note: not used
            cave_name = next(section_data_iter)

            # -------------- Survey Name -------------- #
            input_str = next(section_data_iter)
            if (match := COMPASS_SECTION_NAME_RE.match(input_str)) is None:
                raise ValueError("Compass section name not found: `%s`", input_str)

            survey_name = match.group("section_name").strip()

            # -------------- Survey Date & Comment -------------- #
            input_str = next(section_data_iter).replace("\t", " ")
            if (match := COMPASS_DATE_COMMENT_RE.match(input_str)) is None:
                raise ValueError(
                    "Compass date and comment name not found: `%s`", input_str
                )

            survey_date = (
                cls._parse_date(match.group("date"))
                if match.group("date") != "None"
                else None
            )
            section_comment = (
                match.group("comment").strip() if match.group("comment") else ""
            )

            # -------------- Surveyors -------------- #
            if (surveyor_header := next(section_data_iter).strip()) != "SURVEY TEAM:":
                raise ValueError("Unknown surveyor string: `%s`", surveyor_header)
            survey_team = next(section_data_iter).rstrip(";, ").rstrip()

            # -------------- Optional Data -------------- #

            optional_data = next(section_data_iter).split()
            declination_str = format_str = None

            correct_A = correct_B = correct_C = correct2_A = correct2_B = 0.0
            discovery_date = survey_date

            with contextlib.suppress(IndexError, ValueError):
                _header, declination_str = optional_data[0:2]
                _header, format_str = optional_data[2:4]
                _header, correct_A, correct_B, correct_C = optional_data[4:8]
                _header, correct2_A, correct2_B = optional_data[8:11]
                _header, d_month, d_day, d_year = optional_data[11:15]
                discovery_date = cls._parse_date(f"{d_month} {d_day} {d_year}")

            # -------------- Skip Rows -------------- #
            _ = next(section_data_iter)  # empty row
            header_row = next(section_data_iter)
            _ = next(section_data_iter)  # empty row

            # -------------- Section Shots -------------- #

            shots: list[dict[str, Any]] = []

            with contextlib.suppress(StopIteration):
                while shot_str := next(section_data_iter):
                    shot_data = CompassDataRow.from_str_data(
                        str_data=shot_str, header_row=header_row
                    )

                    shots.append(
                        {
                            "from_": shot_data.from_,
                            "to": shot_data.to,
                            "azimuth": float(shot_data.azimuth),
                            "inclination": float(shot_data.inclination),
                            "length": float(shot_data.length),
                            # Optional Values
                            "comment": shot_data.comment,
                            "flags": shot_data.flags,
                            "azimuth2": float(shot_data.azimuth2),
                            "inclination2": float(shot_data.inclination2),
                            # LRUD
                            "left": float(shot_data.left),
                            "right": float(shot_data.right),
                            "up": float(shot_data.up),
                            "down": float(shot_data.down),
                        }
                    )

            survey_sections.append(
                {
                    "cave_name": cave_name,
                    "name": survey_name,
                    "comment": section_comment,
                    "correction": [
                        float(correct_A),
                        float(correct_B),
                        float(correct_C),
                    ],
                    "correction2": [float(correct2_A), float(correct2_B)],
                    "format": format_str,  # pyright: ignore[reportArgumentType]
                    "unit": (
                        "feet"
                        if format_str is None or format_str[1] == "D"
                        else "meters"
                    ),
                    "survey_date": survey_date,  # pyright: ignore[reportArgumentType]
                    "discovery_date": discovery_date,
                    "declination": float(declination_str),  # pyright: ignore[reportArgumentType]
                    "shots": shots,
                    "survey_team": survey_team,  # pyright: ignore[reportArgumentType]
                }
            )

        return Survey.model_validate({"sections": survey_sections})

    # =================== Export Formats =================== #

    # @classmethod
    # def calculate_depth(
    #     self, filepath: str | Path | None = None, include_depth: bool = False
    # ) -> str:
    #     data = self.data.model_dump(by_alias=True)

    #     all_shots = [
    #       shot for section in data["sections"] for shot in section["shots"]
    #     ]

    #     if not include_depth:
    #         for shot in all_shots:
    #             del shot["depth"]

    #     else:
    #         # create an index of all the shots by "ID"
    #         # use a copy to avoid data corruption.
    #         shot_by_origins = defaultdict(list)
    #         shot_by_destinations = defaultdict(list)
    #         for shot in all_shots:
    #             shot_by_origins[shot["from_"]].append(shot)
    #             shot_by_destinations[shot["to"]].append(shot)

    #         origin_keys = set(shot_by_origins.keys())
    #         destination_keys = set(shot_by_destinations.keys())

    #         # Finding the "origin stations" - aka. stations with no incoming
    #         # shots. They are assumed at depth 0.0
    #         origin_stations = set()
    #         for shot_key in origin_keys:
    #             if shot_key in destination_keys:
    #                 continue
    #             origin_stations.add(shot_key)

    #         processing_queue = OrderedQueue()

    #         def collect_downstream_stations(target: str) -> list[str]:
    #             if target in processing_queue:
    #                 return

    #             processing_queue.add(target, value=None, fail_if_present=True)
    #             direct_shots = shot_by_origins[target]

    #             for shot in direct_shots:
    #                 processing_queue.add(
    #                     shot["from_"], value=None, fail_if_present=False
    #                 )
    #                 if (next_shot := shot["to"]) not in processing_queue:
    #                     collect_downstream_stations(next_shot)

    #         for station in sorted(origin_stations):
    #             collect_downstream_stations(station)

    #         def calculate_depth(
    #             target: str, fail_if_unknown: bool = False
    #         ) -> float | None:
    #             if target in origin_stations:
    #                 return 0.0

    #             if (depth := processing_queue[target]) is not None:
    #                 return depth

    #             if fail_if_unknown:
    #                 return None

    #             for shot in shot_by_destinations[target]:
    #                 start_depth = calculate_depth(
    #                   shot["from_"], fail_if_unknown=True
    # )
    #                 if start_depth is not None:
    #                     break
    #             else:
    #                 raise RuntimeError("None of the previous shot has a known depth")

    #             vertical_delta = math.cos(
    #                 math.radians(90 + float(shot["inclination"]))
    #             ) * float(shot["length"])

    #             return round(start_depth + vertical_delta, ndigits=4)

    #         for shot in processing_queue:
    #             processing_queue[shot] = calculate_depth(shot)

    #         for shot in all_shots:
    #             shot["depth"] = round(processing_queue[shot["to"]], ndigits=1)

    @classmethod
    def export_to_dat(cls, survey: Survey, filepath: Path | str) -> None:
        filepath = Path(filepath)

        filetype = CompassFileType.from_path(filepath)

        if filetype != CompassFileType.DAT:
            raise TypeError(
                f"Unsupported fileformat: `{filetype.name}`. "
                f"Expected: `{CompassFileType.DAT.name}`"
            )

        with filepath.open(mode="w", encoding="windows-1252") as fp:
            survey.export_to_dat(fp)

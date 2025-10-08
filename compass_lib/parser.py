from __future__ import annotations

import contextlib
import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from compass_lib.constants import COMPASS_DATE_COMMENT_RE
from compass_lib.constants import COMPASS_END_OF_FILE
from compass_lib.constants import COMPASS_SECTION_NAME_RE
from compass_lib.constants import COMPASS_SECTION_SEPARATOR
from compass_lib.constants import COMPASS_SECTION_SPLIT_RE
from compass_lib.constants import COMPASS_SHOT_FLAGS_RE
from compass_lib.enums import CompassFileType
from compass_lib.enums import ShotFlag
from compass_lib.models import Survey
from compass_lib.models import SurveySection
from compass_lib.models import SurveyShot

if TYPE_CHECKING:
    from typing_extensions import Self


@dataclass
class CompassDataRow:
    """Basic Dataclass that represent one row of 'data' from the DAT file.
    This contains no validation logic, the validation is being performed by
    the PyDantic class: `ShotData`.
    The sole purpose of this class is to aggregate the parsing logic."""

    from_id: str
    to_id: str
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

        instance = cls(*shot_data[:9])

        def split1_str(val: str) -> tuple[str]:
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
            return rslt

        with contextlib.suppress(IndexError):
            optional_data = shot_data[9]

            if "AZM2" in header_row:
                instance.azimuth2, optional_data = split1_str(optional_data)

            if "INC2" in header_row:
                instance.inclination2, optional_data = split1_str(optional_data)

            if (
                all(x in header_row for x in ["FLAGS", "COMMENTS"])
                and optional_data is not None
            ):
                flags_comment = optional_data

                _, flag_str, comment = re.search(
                    COMPASS_SHOT_FLAGS_RE, flags_comment
                ).groups()

                instance.comment = comment.strip() if comment != "" else None

                instance.flags = (
                    [ShotFlag._value2member_map_[f] for f in flag_str]
                    if flag_str
                    else None
                )
                if instance.flags is not None:
                    instance.flags = sorted(set(instance.flags), key=lambda f: f.value)

        # Input Normalization
        instance.azimuth = float(instance.azimuth)
        instance.azimuth = instance.azimuth % 360.0 if instance.azimuth >= 0 else 0.0

        instance.azimuth2 = float(instance.azimuth2)
        instance.azimuth2 = instance.azimuth2 % 360.0 if instance.azimuth2 >= 0 else 0.0

        return instance


class CompassParser:
    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "This class is not meant to be instantiated directly."
        )

    @classmethod
    def load_dat_file(cls, filepath: str) -> Survey:
        filepath = Path(filepath)

        if not filepath.is_file():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Ensure at least that the file type is valid
        with Path(filepath).open(mode="r", encoding="windows-1252") as f:
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
        survey = Survey(cave_name=raw_sections[0].split("\n", maxsplit=1)[0].strip())

        for raw_section in raw_sections:
            section_data_iter = iter(raw_section.splitlines())

            # Note: not used
            # cave_name = next(section_data_iter)
            _ = next(section_data_iter)

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
            surveyors = next(section_data_iter).rstrip(";, ").rstrip()

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

            shots = []

            with contextlib.suppress(StopIteration):
                while shot_str := next(section_data_iter):
                    shot_data = CompassDataRow.from_str_data(
                        str_data=shot_str, header_row=header_row
                    )

                    shots.append(
                        SurveyShot(
                            from_id=shot_data.from_id,
                            to_id=shot_data.to_id,
                            azimuth=float(shot_data.azimuth),
                            inclination=float(shot_data.inclination),
                            length=float(shot_data.length),
                            # Optional Values
                            comment=shot_data.comment,
                            flags=shot_data.flags,
                            azimuth2=float(shot_data.azimuth2),
                            inclination2=float(shot_data.inclination2),
                            # LRUD
                            left=float(shot_data.left),
                            right=float(shot_data.right),
                            up=float(shot_data.up),
                            down=float(shot_data.down),
                        )
                    )

            survey.sections.append(
                SurveySection(
                    name=survey_name,
                    comment=section_comment,
                    correction=(float(correct_A), float(correct_B), float(correct_C)),
                    correction2=(float(correct2_A), float(correct2_B)),
                    survey_date=survey_date,
                    discovery_date=discovery_date,
                    declination=float(declination_str),
                    format=format_str if format_str is not None else "DDDDUDLRLADN",
                    shots=shots,
                    surveyors=surveyors,
                )
            )

        return survey

    # =================== Export Formats =================== #

    # @classmethod
    # def calculate_depth(
    #     self, filepath: str | Path | None = None, include_depth: bool = False
    # ) -> str:
    #     data = self.data.model_dump()

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
    #             shot_by_origins[shot["from_id"]].append(shot)
    #             shot_by_destinations[shot["to_id"]].append(shot)

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
    #                     shot["from_id"], value=None, fail_if_present=False
    #                 )
    #                 if (next_shot := shot["to_id"]) not in processing_queue:
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
    #                   shot["from_id"], fail_if_unknown=True
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
    #             shot["depth"] = round(processing_queue[shot["to_id"]], ndigits=1)

    @classmethod
    def export_to_dat(cls, survey: Survey, filepath: Path | str) -> None:
        filepath = Path(filepath)

        filetype = CompassFileType.from_path(filepath)

        if filetype != CompassFileType.DAT:
            raise TypeError(
                f"Unsupported fileformat: `{filetype.name}`. "
                f"Expected: `{CompassFileType.DAT.name}`"
            )

        with filepath.open(mode="w", encoding="windows-1252") as f:
            for section in survey.sections:
                # Section Header
                f.write(f"{survey.cave_name}\n")
                f.write(f"SURVEY NAME: {section.name}\n")
                f.write(
                    "".join(
                        (
                            "SURVEY DATE: ",
                            section.survey_date.strftime("%m %-d %Y")
                            if section.survey_date
                            else "None",
                            " ",
                        )
                    )
                )
                f.write(f"COMMENT:{section.comment}\n")
                f.write(f"SURVEY TEAM:\n{section.surveyors}\n")
                f.write(f"DECLINATION: {section.declination:>7.02f}  ")
                f.write(f"FORMAT: {section.format}  ")
                f.write(
                    f"CORRECTIONS:  {' '.join(f'{nbr:.02f}' for nbr in section.correction)}  "  # noqa: E501
                )
                f.write(
                    f"CORRECTIONS2:  {' '.join(f'{nbr:.02f}' for nbr in section.correction2)}  "  # noqa: E501
                )
                f.write(
                    "".join(
                        (
                            "DISCOVERY: ",
                            section.discovery_date.strftime("%m %-d %Y")
                            if section.discovery_date
                            else "None",
                            "\n\n",
                        )
                    )
                )

                # Shots - Header
                f.write("        FROM           TO   LENGTH  BEARING      INC")
                f.write("     LEFT       UP     DOWN    RIGHT")
                f.write("     AZM2     INC2   FLAGS  COMMENTS\n\n")

                # Shots - Data
                for shot in section.shots:
                    f.write(f"{shot.from_id: >12} ")
                    f.write(f"{shot.to_id: >12} ")
                    f.write(f"{shot.length:8.2f} ")
                    f.write(f"{shot.azimuth:8.2f} ")
                    f.write(f"{shot.inclination:8.3f} ")
                    f.write(f"{shot.left:8.2f} ")
                    f.write(f"{shot.up:8.2f} ")
                    f.write(f"{shot.down:8.2f} ")
                    f.write(f"{shot.right:8.2f} ")
                    f.write(f"{shot.azimuth2:8.2f} ")
                    f.write(f"{shot.inclination2:8.3f}")
                    if shot.flags is not None:
                        escaped_start_token = str(ShotFlag.__start_token__).replace(
                            "\\", ""
                        )
                        f.write(f" {escaped_start_token}")
                        f.write("".join([flag.value for flag in shot.flags]))
                        f.write(ShotFlag.__end_token__)
                    if shot.comment is not None:
                        f.write(f" {shot.comment}")
                    f.write("\n")

                # End of Section - Form_feed: https://www.ascii-code.com/12
                f.write(f"{COMPASS_SECTION_SEPARATOR}\n")

            # End of File - Substitute: https://www.ascii-code.com/26
            f.write(f"{COMPASS_END_OF_FILE}\n")

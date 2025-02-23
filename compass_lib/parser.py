#!/usr/bin/env python

import codecs
import contextlib
import datetime
import hashlib
import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Self

from compass_lib.encoding import EnhancedJSONEncoder
from compass_lib.enums import CompassFileType
from compass_lib.enums import ShotFlag
from compass_lib.models import Survey
from compass_lib.models import SurveySection
from compass_lib.models import SurveyShot
from compass_lib.utils import OrderedQueue


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

                flag_regex = (
                    rf"({ShotFlag.__start_token__}"
                    rf"([{''.join(ShotFlag._value2member_map_.keys())}]*){ShotFlag.__end_token__})*(.*)"
                )

                _, flag_str, comment = re.search(flag_regex, flags_comment).groups()

                instance.comment = comment.strip() if comment != "" else None

                instance.flags = (
                    [ShotFlag._value2member_map_[f] for f in flag_str]
                    if flag_str
                    else None
                )
                if instance.flags is not None:
                    instance.flags = sorted(set(instance.flags), key=lambda f: f.value)

        return instance


class CompassParser:
    SEPARATOR = "\f"  # Form_feed: https://www.ascii-code.com/12
    END_OF_FILE = "\x1a"  # Substitute: https://www.ascii-code.com/26

    def __init__(self, filepath: str) -> None:
        self._filepath = Path(filepath)

        if not self.filepath.is_file():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Ensure at least that the file type is valid
        with codecs.open(self.filepath, "rb", "windows-1252") as f:
            self._file_content = f.read()

        self._raw_sections = [
            section.strip()
            for section in self._file_content.split(CompassParser.SEPARATOR)
            if CompassParser.END_OF_FILE not in section
        ]

    # =================== File Properties =================== #

    def __repr__(self) -> str:
        return f"[CompassSurveyFile {self.filetype.upper()}] `{self.filepath}`:"

    def __hash__(self) -> int:
        sha256_hash = hashlib.sha256(self._file_content.encode("utf-8")).hexdigest()
        return int(sha256_hash, 16)

    # =============== Descriptive Properties =============== #

    @property
    def filepath(self) -> Path:
        return self._filepath

    @property
    def filetype(self) -> str:
        return self.filepath.suffix[1:]

    @property
    def lstat(self) -> os.stat_result:
        return self.filepath.lstat()

    @property
    def date_created(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.lstat.st_ctime)  # noqa: DTZ006

    @property
    def date_last_modified(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.lstat.st_mtime)  # noqa: DTZ006

    @property
    def date_last_opened(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.lstat.st_atime)  # noqa: DTZ006

    # =================== Data  Processing =================== #

    @cached_property
    def data(self):  # noqa: C901
        survey = Survey(
            cave_name=self._raw_sections[0].split("\n", maxsplit=1)[0].strip()
        )

        for raw_section in self._raw_sections:
            section_data = raw_section.splitlines()

            # Note: not used
            # cave_name = section_data[0].strip()

            if "SURVEY NAME: " not in section_data[1]:
                raise RuntimeError

            survey_name = section_data[1].split(":")[-1].strip()

            try:
                date_str, comment_str = section_data[2].split("  ", maxsplit=1)
            except ValueError:
                date_str = section_data[2]
                comment_str = None

            if "SURVEY DATE: " not in date_str:
                raise RuntimeError

            date = date_str.split(":")[-1].strip()

            for date_format in ["%m %d %Y", "%m %d %y"]:
                try:
                    date = datetime.datetime.strptime(date, date_format).date()
                    break
                except ValueError:
                    continue

            if comment_str is None:
                survey_comment = ""
            elif "COMMENT:" not in comment_str:
                raise ValueError(f"Improper Comment Format: `{survey_comment}`")
            else:
                survey_comment = comment_str.split(":")[-1].strip()

            if section_data[3].strip() != "SURVEY TEAM:":
                raise RuntimeError

            surveyors = [
                suveyor.strip()
                for suveyor in section_data[4].split(",")
                if suveyor.strip() != ""
            ]

            optional_data = section_data[5].split()
            declination_str = format_str = None

            correct_A = correct_B = correct_C = correct2_A = correct2_B = 0.0

            with contextlib.suppress(IndexError, ValueError):
                header, declination_str = optional_data[0:2]
                header, format_str = optional_data[2:4]
                header, correct_A = optional_data[4:6]
                header, correct_B = optional_data[6:8]
                header, correct_C = optional_data[8:10]
                header, correct2_A = optional_data[10:12]
                header, correct2_B = optional_data[12:14]

            shots = []

            for shot_str in section_data[9:]:
                shot_data = CompassDataRow.from_str_data(
                    str_data=shot_str, header_row=section_data[7]
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
                    comment=survey_comment,
                    correction=(float(correct_A), float(correct_B), float(correct_C)),
                    correction2=(float(correct2_A), float(correct2_B)),
                    date=date,
                    declination=float(declination_str),
                    format=format_str if format_str is not None else "DDDDUDLRLADN",
                    shots=shots,
                    surveyors=surveyors,
                )
            )

        return survey

    # =================== Export Formats =================== #

    def to_json(  # noqa: C901
        self, filepath: str | Path | None = None, include_depth: bool = False
    ) -> str:
        data = self.data.model_dump()

        all_shots = [shot for section in data["sections"] for shot in section["shots"]]

        if not include_depth:
            for shot in all_shots:
                del shot["depth"]

        else:
            # create an index of all the shots by "ID"
            # use a copy to avoid data corruption.
            shot_by_origins = defaultdict(list)
            shot_by_destinations = defaultdict(list)
            for shot in all_shots:
                shot_by_origins[shot["from_id"]].append(shot)
                shot_by_destinations[shot["to_id"]].append(shot)

            origin_keys = set(shot_by_origins.keys())
            destination_keys = set(shot_by_destinations.keys())

            # Finding the "origin stations" - aka. stations with no incoming
            # shots. They are assumed at depth 0.0
            origin_stations = set()
            for shot_key in origin_keys:
                if shot_key in destination_keys:
                    continue
                origin_stations.add(shot_key)

            processing_queue = OrderedQueue()

            def collect_downstream_stations(target: str) -> list[str]:
                if target in processing_queue:
                    return

                processing_queue.add(target, value=None, fail_if_present=True)
                direct_shots = shot_by_origins[target]

                for shot in direct_shots:
                    processing_queue.add(
                        shot["from_id"], value=None, fail_if_present=False
                    )
                    if (next_shot := shot["to_id"]) not in processing_queue:
                        collect_downstream_stations(next_shot)

            for station in sorted(origin_stations):
                collect_downstream_stations(station)

            def calculate_depth(
                target: str, fail_if_unknown: bool = False
            ) -> float | None:
                if target in origin_stations:
                    return 0.0

                if (depth := processing_queue[target]) is not None:
                    return depth

                if fail_if_unknown:
                    return None

                for shot in shot_by_destinations[target]:
                    start_depth = calculate_depth(shot["from_id"], fail_if_unknown=True)
                    if start_depth is not None:
                        break
                else:
                    raise RuntimeError("None of the previous shot has a known depth")

                vertical_delta = math.cos(
                    math.radians(90 + float(shot["inclination"]))
                ) * float(shot["length"])

                return round(start_depth + vertical_delta, ndigits=4)

            for shot in processing_queue:
                processing_queue[shot] = calculate_depth(shot)

            for shot in all_shots:
                shot["depth"] = round(processing_queue[shot["to_id"]], ndigits=1)

        json_str = json.dumps(data, indent=4, sort_keys=True, cls=EnhancedJSONEncoder)

        if filepath is not None:
            if not isinstance(filepath, Path):
                filepath = Path(filepath)

            with filepath.open(mode="w") as file:
                file.write(json_str)

        return json_str

    def to_dat(self, filepath: Path | str) -> None:
        if isinstance(filepath, str):
            filepath = Path(filepath)

        filetype = CompassFileType.from_path(filepath)

        if filetype != CompassFileType.DAT:
            raise TypeError(
                f"Unsupported fileformat: `{filetype.name}`. "
                f"Expected: `{CompassFileType.DAT.name}`"
            )

        with codecs.open(filepath, "wb", "windows-1252") as f:
            survey = self.data
            for section in survey.sections:
                # Section Header
                f.write(f"{survey.cave_name}\n")
                f.write(f"SURVEY NAME: {section.name}\n")
                f.write(f"SURVEY DATE: {section.date.strftime('%m %-d %Y')}  ")
                f.write(f"COMMENT:{section.comment}\n")
                f.write("SURVEY TEAM:\n")
                f.write(f"{','.join(section.surveyors)}\n")
                f.write(f"DECLINATION: {section.declination: >7}  ")
                f.write(f"FORMAT: {section.format}  ")
                f.write(
                    f"CORRECTIONS: {' '.join(f'{nbr:.02f}' for nbr in section.correction)}  "  # noqa: E501
                )
                f.write(
                    f"CORRECTIONS2: {' '.join(f'{nbr:.02f}' for nbr in section.correction2)}\n\n"  # noqa: E501
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
                    f.write(f"{shot.inclination:8.2f} ")
                    f.write(f"{shot.left:8.2f} ")
                    f.write(f"{shot.up:8.2f} ")
                    f.write(f"{shot.down:8.2f} ")
                    f.write(f"{shot.right:8.2f} ")
                    f.write(f"{shot.azimuth2:8.2f} ")
                    f.write(f"{shot.inclination2:8.2f}")
                    if shot.flags is not None:
                        f.write(f" {str(ShotFlag.__start_token__).replace('\\', '')}")
                        f.write("".join([flag.value for flag in shot.flags]))
                        f.write(ShotFlag.__end_token__)
                    if shot.comment is not None:
                        f.write(f" {shot.comment}")
                    f.write("\n")

                # End of Section
                f.write(
                    f"{self.SEPARATOR}\n"
                )  # Form_feed: https://www.ascii-code.com/12
            f.write(
                f"{self.END_OF_FILE}\n"
            )  # Substitute: https://www.ascii-code.com/26

    # ==================== Public APIs ====================== #

    @cached_property
    def shots(self):
        return []
        # return [
        #     SurveyShot(data=survey_shot)
        #     for survey_shot in self._KEY_MAP.fetch(self._shots_list, "_shots")
        # ]

    @cached_property
    def sections(self):
        return []
        # section_map = dict()
        # for shot in self.shots:
        #     try:
        #         section_map[shot.section].add_shot(shot)
        #     except KeyError:
        #         section_map[shot.section] = SurveySection(shot=shot)
        # return list(section_map.values())

#!/usr/bin/env python

import codecs
import contextlib
import datetime
import hashlib
import json
import math
import re
from collections import defaultdict
from functools import cached_property
from pathlib import Path

from compass_lib.encoding import EnhancedJSONEncoder
from compass_lib.enums import CompassFileType
from compass_lib.enums import ShotFlag

# from compass_lib.section import SurveySection
# from compass_lib.shot import SurveyShot
from compass_lib.models import Survey
from compass_lib.models import SurveySection
from compass_lib.models import SurveyShot
from compass_lib.utils import OrderedQueue


class CompassParser:
    SEPARATOR = "\f"  # Form_feed: https://www.ascii-code.com/12
    END_OF_FILE = "\x1A"  # Substitute: https://www.ascii-code.com/26

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

    @cached_property
    def __hash__(self):
        return hashlib.sha256(self._file_content).hexdigest()

    @property
    def hash(self):
        return self.__hash__

    # =============== Descriptive Properties =============== #

    @property
    def filepath(self):
        return self._filepath

    @property
    def filetype(self):
        return self.filepath.suffix[1:]

    @property
    def lstat(self):
        return self.filepath.lstat()

    @property
    def date_created(self):
        return self.lstat.st_ctime

    @property
    def date_last_modified(self):
        return self.lstat.st_mtime

    @property
    def date_last_opened(self):
        return self.lstat.st_atime

    # =================== Data  Processing =================== #

    @cached_property
    def data(self):

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
                suveyor.strip() for suveyor in section_data[4].split(",")
                if suveyor.strip() != ""
            ]

            optional_data = section_data[5].split()
            declination_str = format_str = None

            correct_A = correct_B = correct_C = \
            correct2_A = correct2_B = 0.0

            with contextlib.suppress(IndexError, ValueError):
                header, declination_str = optional_data[0:2]
                header, format_str = optional_data[2:4]
                header, correct_A = optional_data[4:6]
                header, correct_B = optional_data[6:8]
                header, correct_C = optional_data[8:10]
                header, correct2_A = optional_data[10:12]
                header, correct2_B = optional_data[12:14]

            shots = []

            for shot in section_data[9:]:
                shot_data = shot.split(maxsplit=9)

                from_id, to_id, length, bearing, incl, left, up, down, right = shot_data[:9]  # noqa: E501

                try:
                    azm2 = 0.0
                    incl2 = 0.0

                    flags_comment = shot_data[9]

                    flag_regex = (
                        rf"({ShotFlag.__start_token__}"
                        rf"([{''.join(ShotFlag._value2member_map_.keys())}]*){ShotFlag.__end_token__})*(.*)"  # noqa: SLF001
                    )

                    _, flag_str, comment = re.search(flag_regex, flags_comment).groups()

                    flags = (
                        [ShotFlag._value2member_map_[f] for f in flag_str]  # noqa: SLF001
                        if flag_str else
                        None
                    )

                except IndexError:
                    flags = None
                    comment = None

                shots.append(SurveyShot(
                    from_id=from_id,
                    to_id=to_id,
                    azimuth=float(bearing),
                    inclination=float(incl),
                    length=float(length),

                    # Optional Values
                    comment=comment.strip() if comment else None,
                    flags=sorted(set(flags), key=lambda f: f.value) if flags else None,

                    azimuth2=float(azm2),
                    inclination2=float(incl2),

                    # LRUD
                    left=float(left),
                    right=float(right),
                    up=float(up),
                    down=float(down)
                ))

            survey.sections.append(SurveySection(
                name=survey_name,
                comment=survey_comment,
                correction=(float(correct_A), float(correct_B), float(correct_C)),
                correction2=(float(correct2_A), float(correct2_B)),
                date=date,
                declination=float(declination_str),
                format=format_str if format_str is not None else "DDDDUDLRLADN",
                shots=shots,
                surveyors=surveyors,
            ))

        return survey


    # =================== Export Formats =================== #

    def to_json(self, filepath: str | Path | None = None, include_depth: bool = False) -> str:  # noqa: E501
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
                processing_queue.add(target)
                direct_shots = shot_by_origins[target]
                for shot in direct_shots:
                    processing_queue.add(shot["from_id"])
                    if (next_shot := shot["to_id"]) not in  processing_queue:
                        collect_downstream_stations(next_shot)

            for station in origin_stations:
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

        json_str = json.dumps(
            data,
            indent=4,
            sort_keys=True,
            cls=EnhancedJSONEncoder
        )

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
            raise TypeError(f"Unsupported fileformat: `{filetype.name}`. "
                            f"Expected: `{CompassFileType.DAT.name}`")

        with codecs.open(filepath, "wb", "windows-1252") as f:
            for section in self.data:
                # Section Header
                f.write(f"{section.cave_name}\n")
                f.write(f"SURVEY NAME: {section.survey_name}\n")
                f.write(f"SURVEY DATE: {section.date.strftime('%m %-d %Y')}  ")
                f.write(f"COMMENT:{section.comment}\n")
                f.write("SURVEY TEAM:\n")
                f.write(f"{','.join(section.surveyors)}\n")
                f.write(f"DECLINATION: {section.declination: >7}  ")
                f.write(f"FORMAT: {section.format}  ")
                f.write(f"CORRECTIONS: {" ".join(f'{nbr:.02f}' for nbr in section.correction)}  ")  # noqa: E501
                f.write(f"CORRECTIONS2: {" ".join(f'{nbr:.02f}' for nbr in section.correction2)}\n\n")  # noqa: E501

                # Shots - Header
                f.write("        FROM           TO   LENGTH  BEARING      INC")
                f.write("     LEFT       UP     DOWN    RIGHT")
                f.write("     AZM2     INC2   FLAGS  COMMENTS\n\n")

                # Shots - Data
                for shot in section.shots:
                    f.write(f"{shot.from_id: >12} ")
                    f.write(f"{shot.to_id: >12} ")
                    f.write(f"{shot.length:8.2f} ")
                    f.write(f"{shot.bearing:8.2f} ")
                    f.write(f"{shot.inclination:8.2f} ")
                    f.write(f"{shot.left:8.2f} ")
                    f.write(f"{shot.up:8.2f} ")
                    f.write(f"{shot.down:8.2f} ")
                    f.write(f"{shot.right:8.2f} ")
                    f.write(f"{shot.azimuth2:8.2f} ")
                    f.write(f"{shot.inclination2:8.2f}")
                    if shot.flags is not None:
                        f.write(f" {shot.flags} ")
                    if shot.comment is not None:
                        f.write(f" {shot.comment}")
                    f.write("\n")

                # End of Section
                f.write(f"{self.SEPARATOR}\n")  # Form_feed: https://www.ascii-code.com/12
            f.write(f"{self.END_OF_FILE}\n")    # Substitute: https://www.ascii-code.com/26

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

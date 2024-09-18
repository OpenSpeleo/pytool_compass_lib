#!/usr/bin/env python

import datetime
import hashlib
import json
import re
from dataclasses import asdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from compass_lib.encoding import EnhancedJSONEncoder
from compass_lib.enums import ShotFlag
from compass_lib.section import SurveySection
from compass_lib.shot import SurveyShot

# ============================== CompassFileFormat ============================== #

#   _formatFormat(): string {
#     const {
#       displayAzimuthUnit,
#       displayLengthUnit,
#       displayLrudUnit,
#       displayInclinationUnit,
#       lrudOrder,
#       shotMeasurementOrder,
#       hasBacksights,
#       lrudAssociation,
#     } = this
#     return `${inverseAzimuthUnits[displayAzimuthUnit]}${
#       inverseLengthUnits[displayLengthUnit]
#     }${inverseLengthUnits[displayLrudUnit]}${
#       inverseInclinationUnits[displayInclinationUnit]
#     }${lrudOrder
#       .map(i => inverseLrudItems[i])
#       .join('')}${shotMeasurementOrder
#       .map(i => inverseShotMeasurementItems[i])
#       .join('')}${hasBacksights ? 'B' : 'N'}${
#       lrudAssociation != null ? inverseStationSides[lrudAssociation] : ''
#     }`
#   }

@dataclass
class CompassFileFormat:
    displayAzimuthUnit: str
    displayLengthUnit: str
    displayLrudUnit: str
    displayInclinationUnit: str
    lrudOrder: str
    shotMeasurementOrder: str
    hasBacksights: str
    lrudAssociation: str

    @classmethod
    def from_str(cls, input):
        # TODO
        raise NotImplementedError
        # return cls(
        #     displayAzimuthUnit="",
        #     displayLengthUnit="",
        #     displayLrudUnit="",
        #     displayInclinationUnit="",
        #     lrudOrder="",
        #     shotMeasurementOrder="",
        #     hasBacksights="",
        #     lrudAssociation="",
        # )


class CompassParser:
    SEPARATOR = "\f"  # Form_feed: https://www.ascii-code.com/12
    END_OF_FILE = "\x1A"  # Substitute: https://www.ascii-code.com/26

    def __init__(self, filepath: str) -> None:

        self._filepath = Path(filepath)

        if not self.filepath.is_file():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Ensure at least that the file type is valid
        _ = self._data

    # =================== Data Loading =================== #

    @cached_property
    def _data(self):

        with self.filepath.open(mode="r") as f:
            data = f.read()

        return [
            activity.strip()
            for activity in data.split(CompassParser.SEPARATOR)
            if CompassParser.END_OF_FILE not in activity
        ]

    # =================== File Properties =================== #

    def __repr__(self) -> str:
        return f"[CompassSurveyFile {self.filetype.upper()}] `{self.filepath}`:"
        # for key in self._KEY_MAP.keys():
        #     if key.startswith("_"):
        #         continue
        #     repr += f"\n\t- {key}: {getattr(self, key)}"
        # repr += f"\n\t- shots: Total Shots: {len(self.shots)}"
        # repr += f"\n\t- hash: {self.hash}"

    @cached_property
    def __hash__(self):
        # return hashlib.sha256(self._as_binary()).hexdigest()
        return hashlib.sha256(b"0").hexdigest()

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
        # try:
        #     return ArianeFileType.from_str(self.filepath.suffix[1:])
        # except ValueError as e:
        #     raise TypeError(e) from e

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
        sections = []
        for activity in self._data:
            entries = activity.splitlines()

            cave_name = entries[0].strip()

            if "SURVEY NAME: " not in entries[1]:
                raise RuntimeError
            survey_name = entries[1].split(":")[-1].strip()

            date_str, comment_str = entries[2].split("  ", maxsplit=1)

            if "SURVEY DATE: " not in date_str:
                raise RuntimeError
            date = date_str.split(":")[-1].strip()

            if "COMMENT:" not in comment_str:
                raise RuntimeError
            survey_comment = comment_str.split(":")[-1].strip()

            if entries[3].strip() != "SURVEY TEAM:":
                raise RuntimeError

            surveyors = [
                suveyor.strip() for suveyor in entries[4].split(",")
                if suveyor.strip() != ""
            ]

            for _str in ["DECLINATION:", "FORMAT:", "CORRECTIONS:"]:
                if _str not in entries[5]:
                    raise RuntimeError(f"`{_str}` not found in {entries[5]=}")

            try:
                _, declination_str, _, format_str, _, correct_A, correct_B, correct_C = entries[5].split()  # noqa: E501
                correct2_A, correct2_B = 0, 0
            except ValueError:
                _, declination_str, _, format_str, _, correct_A, correct_B, correct_C, _, correct2_A, correct2_B = entries[5].split()  # noqa: E501

            shots = []

            for shot in entries[9:]:
                shot_data = shot.split(maxsplit=9)

                from_id, to_id, length, bearing, incl, left, up, down, right = shot_data[:9]  # noqa: E501

                try:
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
                    length=float(length),
                    bearing=float(bearing),
                    inclination=float(incl),
                    left=float(left),
                    up=float(up),
                    down=float(down),
                    right=float(right),
                    flags=sorted(set(flags), key=lambda f: f.value) if flags else None,
                    comment=comment.strip() if comment else None
                ))

            section = SurveySection(
                cave_name=cave_name,
                survey_name=survey_name,
                date=datetime.datetime.strptime(date, "%m %d %Y").date(),
                comment=survey_comment,
                surveyors=surveyors,
                declination=float(declination_str),
                format=format_str,
                correction=(float(correct_A), float(correct_B), float(correct_C)),
                correction2=(float(correct2_A), float(correct2_B)),
                shots=shots
            )
            sections.append(section)

        return sections


    # =================== Export Formats =================== #

    def to_json(self, filepath: str | Path | None = None, include_depth: bool = False) -> str:  # noqa: E501
        data = [asdict(section) for section in self.data]

        if not include_depth:
            for section in data:
                for shot in section["shots"]:
                    del shot["depth"]
        else:
            import copy
            shots = {
                shot["to_id"]: copy.deepcopy(shot)
                for section in data
                for shot in section["shots"]
            }

            import math
            from functools import lru_cache

            @lru_cache(maxsize=99999)
            def find_depth_shot(target: str):
                # if target not in shots:
                if False:
                    print("hello")
                    return 0.0

                try:
                    if shots[target]["depth"] is not None:
                        print(f"{target=}, {shots[target]}")
                        print("---- TEST _----")
                        return shots[target]["depth"]
                except KeyError:
                    return 0.0

                start_depth = find_depth_shot(target=shots[target]["from_id"])
                vertical_delta = math.cos(math.radians(90 + float(shot["inclination"]))) * float(shot["length"])
                rslt = round(start_depth + vertical_delta, ndigits=4)
                print(f"{target=}  => {start_depth} + {vertical_delta} = {rslt}")
                return rslt

            for section in data:
                for shot in section["shots"]:
                    shot["depth"] = find_depth_shot(target=shot["to_id"])

        print(data)
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

from __future__ import annotations

import re

from compass_lib.enums import ShotFlag

# ============================== SPECIAL CHARS ============================== #

COMPASS_SECTION_SEPARATOR = "\f"  # Form_feed: https://www.ascii-code.com/12
COMPASS_END_OF_FILE = "\x1a"  # Substitute: https://www.ascii-code.com/26

# ================================== REGEX ================================== #
# Priorized regex:
# 1. Section Split with `\r\n`
# 2. Section Split with `\n`
# 3. Section Split with `\f` alone
COMPASS_SECTION_SPLIT_RE = re.compile(
    rf"{COMPASS_SECTION_SEPARATOR}\r\n|{COMPASS_SECTION_SEPARATOR}\n|{COMPASS_SECTION_SEPARATOR}"
)

# String format:
# - `SURVEY NAME: toc+187?`
COMPASS_SECTION_NAME_RE = re.compile(r"SURVEY NAME:\s*(?P<section_name>\S*)")

# String format:
# - `SURVEY DATE: 1 26 86`
# - `SURVEY DATE: 4 22 2001`
# - `SURVEY DATE: 8 28 1988  COMMENT:Surface to shelter`
COMPASS_DATE_COMMENT_RE = re.compile(
    r"^SURVEY DATE:\s*(?P<date>\d{1,2}\s+\d{1,2}\s+\d{2,4}|None)(?:\s+COMMENT:\s*(?P<comment>.*))?$"  # noqa: E501
)

COMPASS_SHOT_FLAGS_RE = re.compile(
    rf"({ShotFlag.__start_token__}"
    rf"([{''.join(ShotFlag._value2member_map_.keys())}]*){ShotFlag.__end_token__})*(.*)"
)

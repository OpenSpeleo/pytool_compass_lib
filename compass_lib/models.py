import datetime
import uuid
from typing import Annotated
from typing import Any

from pydantic import UUID4
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from compass_lib.constants import COMPASS_MAX_NAME_LENGTH
from compass_lib.generators import UniqueNameGenerator
from compass_lib.mixins import BaseMixin


class SurveyShot(BaseMixin, BaseModel):
    from_id: str
    to_id: str = Field(
        default_factory=lambda: UniqueNameGenerator.get(str_len=6),
        min_length=2,
        max_length=COMPASS_MAX_NAME_LENGTH
    )

    azimuth: Annotated[float, Field(ge=0, lt=360)]

    inclination: Annotated[float, Field(ge=-90, le=90)]
    length: Annotated[float, Field(ge=0)]

    # Optional Values
    comment: str | None = None
    flags: Any | None = None

    azimuth2: Annotated[float, Field(ge=0, lt=360)] | None = None
    inclination2: Annotated[float, Field(ge=-90, le=90)] | None = None

    # calculated
    depth: Annotated[float, Field(ge=0)] | None = None

    # LRUD
    left: Annotated[float, Field(ge=0)] = 0.0
    right: Annotated[float, Field(ge=0)] = 0.0
    up: Annotated[float, Field(ge=0)] = 0.0
    down: Annotated[float, Field(ge=0)] = 0.0

    model_config = ConfigDict(extra="forbid")

    @field_validator("left", "right", "up", "down", mode="before")
    @classmethod
    def validate_lrud(cls, value: float) -> float:
        return value if value > 0 else 0.0

    # @field_validator("to_id", mode="before")
    # @classmethod
    # def validate_unique_to_id(cls, value: str | None) -> str:
    #     """Note: Validators are only ran with custom fed values.
    #     Not autogenerated ones. Hence we need to register the name."""

    #     if value is None or value == "":
    #         return cls.to_id.default_factory()

    #     # 1. Verify the name is only composed of valid chars.
    #     for char in value:
    #         if char.upper() not in [
    #             *UniqueNameGenerator.VOCAB,
    #             *list("_-~:!?.'()[]{}@*&#%|$")
    #         ]:
    #             raise ValueError(f"The character `{char}` is not allowed as `name`.")

    #     if len(value) > COMPASS_MAX_NAME_LENGTH:
    #         raise ValueError(f"Name {value} is too long, maximum allowed: "
    #                          f"{COMPASS_MAX_NAME_LENGTH}")

    #     UniqueNameGenerator.register(value=value)
    #     return value



class SurveySection(BaseModel):
    name: str
    comment: str
    correction: list[float]
    correction2: list[float]
    date: datetime.date
    declination: float
    format: str
    shots: list[SurveyShot]
    surveyors: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


class Survey(BaseModel):
    speleodb_id: UUID4 = Field(default_factory=uuid.uuid4)
    cave_name: str
    description: str = ""

    sections: list[SurveySection] = []

    model_config = ConfigDict(extra="forbid")

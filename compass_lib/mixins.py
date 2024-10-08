import json

from iteration_utilities import duplicates
from pydantic import model_validator

from compass_lib.errors import DuplicateValueError


class BaseMixin:

    @model_validator(mode="before")
    @classmethod
    def enforce_snake_and_remove_none(cls, data: dict) -> dict:
        return {k: v for k, v in data.items() if v is not None}

    def to_json(self) -> str:
        """
        Serialize the model to a JSON string with indentation and sorted keys.

        Returns:
            str: The JSON representation of the model.
        """
        return json.dumps(self.model_dump(), indent=4, sort_keys=True)

    # ======================== VALIDATOR UTILS ======================== #

    @classmethod
    def validate_unique(cls, field: str, values: list) -> list:
        vals2check = [getattr(val, field) for val in values]
        dupl_vals = list(duplicates(vals2check))
        if dupl_vals:
            raise DuplicateValueError(
                f"[{cls.__name__}] Duplicate value found for `{field}`: "
                f"{dupl_vals}"
            )
        return values

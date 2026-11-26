"""Internal normalized contract only; no device transport or production receiver."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas import require_aware


class NormalizedReading(BaseModel):
    property_id: int = Field(gt=0)
    component_id: int = Field(gt=0)
    component_type: Literal["level_station", "hydrometer"]
    variable: Literal["level", "totalizer"]
    value: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    unit: Literal["m", "m3"]
    observed_at: datetime
    collected_at: datetime
    source: Literal["manual", "test", "equipment"]
    origin_id: str = Field(min_length=1, max_length=120)

    @field_validator("observed_at", "collected_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value)

    @field_validator("origin_id")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Identificador de origem vazio")
        return value.strip()

    @model_validator(mode="after")
    def validate_combination(self):
        expected = {"level_station": ("level", "m"), "hydrometer": ("totalizer", "m3")}
        if (self.variable, self.unit) != expected[self.component_type]:
            raise ValueError("Variável e unidade incompatíveis com o componente")
        return self

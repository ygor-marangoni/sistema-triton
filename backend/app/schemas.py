import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator, model_validator


def valid_cpf(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11 or len(set(digits)) == 1:
        raise ValueError("CPF inválido")
    for length in (9, 10):
        total = sum(int(digits[i]) * (length + 1 - i) for i in range(length))
        digit = (total * 10 % 11) % 10
        if digit != int(digits[length]):
            raise ValueError("CPF inválido")
    return digits


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Informe data e hora com fuso horário")
    return value


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    cpf: str
    business_address: str = Field(min_length=5, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, v): return valid_cpf(v)


class AdminUserIn(RegisterIn):
    role: Literal["user", "admin"] = "user"
    is_active: bool = True


class AdminUserPatch(BaseModel):
    role: Literal["user", "admin"] | None = None
    is_active: bool | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORMModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    cpf_masked: str | None = None


class PropertyIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    cep: str = Field(pattern=r"^\d{5}-?\d{3}$")
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(pattern=r"^[A-Za-z]{2}$")
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)
    boundary_kml: str | None = Field(default=None, max_length=1_000_000)

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Informe latitude e longitude juntas, ou deixe ambas vazias")
        return self


class PropertyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    cep: str | None = Field(default=None, pattern=r"^\d{5}-?\d{3}$")
    city: str | None = Field(default=None, min_length=2, max_length=100)
    state: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)
    boundary_kml: str | None = Field(default=None, max_length=1_000_000)

    @model_validator(mode="after")
    def coordinate_pair(self):
        provided = self.model_fields_set
        if ("latitude" in provided) != ("longitude" in provided):
            raise ValueError("Para alterar a posição, informe latitude e longitude juntas")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Informe latitude e longitude juntas, ou deixe ambas vazias")
        return self


class AdminPropertyIn(PropertyIn):
    owner_id: int


class PropertyOut(ORMModel):
    id: int
    owner_id: int
    name: str
    cep: str
    city: str
    state: str
    latitude: Decimal | None
    longitude: Decimal | None
    has_boundary: bool
    is_archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime


class ReservoirMapOut(BaseModel):
    id: int
    property_id: int
    name: str
    geometry_kml: str


class ReservoirIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    base_width_m: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    base_length_m: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    top_width_m: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    top_length_m: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    height_m: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    geometry_kml: str = Field(min_length=20, max_length=1_000_000)

    @model_validator(mode="after")
    def dimensions(self):
        if self.top_width_m < self.base_width_m or self.top_length_m < self.base_length_m:
            raise ValueError("Dimensões do topo devem ser iguais ou maiores que as da base")
        return self


class ReservoirOut(ORMModel):
    id: int
    property_id: int
    name: str
    base_width_m: Decimal
    base_length_m: Decimal
    top_width_m: Decimal
    top_length_m: Decimal
    height_m: Decimal
    geometry_assumption: str


class DemandIn(BaseModel):
    month: int = Field(ge=1, le=12)
    max_flow_m3_h: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    daily_hours: Decimal = Field(ge=0, le=24, max_digits=6, decimal_places=2)
    authorized_days: int = Field(ge=0, le=31)
    monthly_volume_m3: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    extracted_values: dict | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.max_flow_m3_h == 0 and (self.daily_hours or self.authorized_days or self.monthly_volume_m3):
            raise ValueError("Vazão zero exige horas, dias e volume zero")
        expected = self.max_flow_m3_h * self.daily_hours * self.authorized_days
        if self.monthly_volume_m3 != expected:
            raise ValueError("Volume mensal deve ser igual a vazão × horas × dias autorizados")
        return self


class OutorgaIn(BaseModel):
    property_id: int
    name: str = Field(min_length=2, max_length=160)
    permit_number: str = Field(min_length=1, max_length=100)
    issued_on: date
    valid_from: date
    valid_until: date
    water_body: str = Field(min_length=2, max_length=160)
    municipality: str = Field(min_length=2, max_length=100)
    coordinates_gms: str = Field(min_length=4, max_length=120)
    state: str = Field(pattern=r"^[A-Za-z]{2}$")
    irrigated_area_ha: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    demands: list[DemandIn] = Field(min_length=12, max_length=12)

    @model_validator(mode="after")
    def validate_dates_months(self):
        if self.valid_until < self.valid_from or self.issued_on > self.valid_from:
            raise ValueError("Datas de vigência da outorga inválidas")
        if {d.month for d in self.demands} != set(range(1, 13)):
            raise ValueError("Cadastre exatamente uma demanda para cada mês")
        return self


class DemandOut(ORMModel):
    id: int
    outorga_id: int
    month: int
    max_flow_m3_h: Decimal
    daily_hours: Decimal
    authorized_days: int
    monthly_volume_m3: Decimal
    extracted_values: dict | None


class OutorgaOut(ORMModel):
    id: int
    property_id: int
    name: str
    permit_number: str
    issued_on: date
    valid_from: date
    valid_until: date
    water_body: str
    municipality: str
    coordinates_gms: str
    state: str
    irrigated_area_ha: Decimal
    is_demo: bool
    is_active: bool
    demands: list[DemandOut]

    @computed_field
    @property
    def validity_status(self) -> str:
        if not self.is_active: return "inativa"
        today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        if today < self.valid_from: return "a iniciar"
        if today > self.valid_until: return "vencida"
        return "vigente"


class DemandPatch(BaseModel):
    max_flow_m3_h: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    daily_hours: Decimal = Field(ge=0, le=24, max_digits=6, decimal_places=2)
    authorized_days: int = Field(ge=0, le=31)
    monthly_volume_m3: Decimal = Field(ge=0, max_digits=14, decimal_places=3)


class HydrometerIn(BaseModel):
    reservoir_id: int
    outorga_id: int | None = None
    name: str = Field(min_length=2, max_length=120)
    kind: Literal["entrada", "saída"]
    rated_power_kw: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    rated_power_cv: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def power_choice(self):
        if self.rated_power_kw and self.rated_power_cv:
            raise ValueError("Informe potência elétrica em kW ou potência mecânica em CV, não ambas")
        return self


class HydrometerOut(ORMModel):
    id: int
    reservoir_id: int
    outorga_id: int | None
    name: str
    kind: str
    rated_power_kw: Decimal | None
    rated_power_cv: Decimal | None
    latitude: Decimal | None
    longitude: Decimal | None
    is_demo: bool
    is_active: bool


class HydrometerReadingIn(BaseModel):
    flow_m3_h: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    volume_m3: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    raw_totalizer_m3: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    interval_start_at: datetime | None = None
    observed_at: datetime
    source: Literal["manual", "simulada"] = "manual"
    external_id: str | None = Field(default=None, max_length=120)
    quality: str = Field(default="não revisada", max_length=120)

    @field_validator("observed_at", "interval_start_at")
    @classmethod
    def aware(cls, v): return require_aware(v) if v is not None else None

    @field_validator("quality")
    @classmethod
    def user_cannot_mark_reviewed(cls, value):
        if value.strip().casefold() in {"revisada", "validada", "confirmed", "confirmada"}:
            raise ValueError("A validação só pode ser registrada pelo fluxo de revisão")
        return value.strip()

    @model_validator(mode="after")
    def has_volume_or_totalizer(self):
        if self.volume_m3 is None and self.raw_totalizer_m3 is None:
            raise ValueError("Informe o volume do intervalo ou o totalizador bruto")
        if self.volume_m3 is not None and self.raw_totalizer_m3 is not None:
            raise ValueError("Informe volume derivado ou totalizador bruto, não ambos")
        if self.interval_start_at is not None and self.interval_start_at >= self.observed_at:
            raise ValueError("O início do intervalo deve anteceder o horário observado")
        if self.raw_totalizer_m3 is not None and self.interval_start_at is not None:
            raise ValueError("O intervalo do totalizador é determinado pela leitura anterior")
        return self


class HydrometerReadingOut(ORMModel):
    id: int
    hydrometer_id: int
    flow_m3_h: Decimal | None
    volume_m3: Decimal | None
    interval_start_at: datetime | None
    observed_at: datetime
    created_at: datetime
    source: str
    unit: str
    external_id: str | None
    quality: str
    raw_totalizer_m3: Decimal | None


class LevelStationIn(BaseModel):
    reservoir_id: int
    name: str = Field(min_length=2, max_length=120)
    minimum_m: Decimal = Field(ge=0, max_digits=8, decimal_places=3)
    maximum_m: Decimal = Field(gt=0, max_digits=8, decimal_places=3)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def range_ok(self):
        if self.maximum_m <= self.minimum_m:
            raise ValueError("Faixa máxima deve superar a mínima")
        return self


class LevelStationUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    minimum_m: Decimal = Field(ge=0, max_digits=8, decimal_places=3)
    maximum_m: Decimal = Field(gt=0, max_digits=8, decimal_places=3)

    @model_validator(mode="after")
    def range_ok(self):
        if self.maximum_m <= self.minimum_m:
            raise ValueError("Faixa máxima deve superar a mínima")
        return self


class LevelStationOut(ORMModel):
    id: int
    reservoir_id: int
    name: str
    minimum_m: Decimal
    maximum_m: Decimal
    latitude: Decimal | None
    longitude: Decimal | None


class LevelReadingIn(BaseModel):
    level_m: Decimal = Field(ge=0, max_digits=8, decimal_places=3)
    observed_at: datetime
    source: Literal["manual", "simulada"] = "manual"
    quality: str = Field(default="não revisada", max_length=120)

    @field_validator("observed_at")
    @classmethod
    def aware(cls, v): return require_aware(v)

    @field_validator("quality")
    @classmethod
    def user_cannot_mark_reviewed(cls, value):
        if value.strip().casefold() in {"revisada", "validada", "confirmed", "confirmada"}:
            raise ValueError("A validação só pode ser registrada pelo fluxo de revisão")
        return value.strip()


class LevelReadingOut(ORMModel):
    id: int
    station_id: int
    level_m: Decimal
    observed_at: datetime
    created_at: datetime
    source: str
    quality: str
    image_review_id: int | None = None


class ImagePixelPoint(BaseModel):
    x: Decimal = Field(ge=0, max_digits=9, decimal_places=2)
    y: Decimal = Field(ge=0, max_digits=9, decimal_places=2)


class RulerReferencePoint(ImagePixelPoint):
    level_m: Decimal = Field(ge=0, max_digits=8, decimal_places=3)


class RulerCalibrationIn(BaseModel):
    reference_1: RulerReferencePoint
    reference_2: RulerReferencePoint
    waterline: ImagePixelPoint


class LevelImageSuggestionIn(BaseModel):
    level_m: Decimal = Field(ge=0, max_digits=8, decimal_places=3)


class LevelImageReviewOut(ORMModel):
    id: int
    property_id: int
    station_id: int
    uploaded_by_id: int
    reviewed_by_id: int | None
    original_name: str
    content_type: str
    size_bytes: int
    width_px: int
    height_px: int
    captured_at: datetime
    created_at: datetime
    unit: str
    status: str
    method: str
    suggested_level_m: Decimal | None
    confirmed_level_m: Decimal | None
    confidence: Decimal | None
    inconclusive_reason: str | None
    analysis_details: dict
    calibration: dict | None
    reviewed_at: datetime | None


class LevelImageReviewRevisionOut(ORMModel):
    id: int
    review_id: int
    user_id: int
    action: str
    previous_values: dict
    corrected_values: dict
    created_at: datetime


class LevelImageConfirmationOut(BaseModel):
    review: LevelImageReviewOut
    reading: LevelReadingOut


class TariffIn(BaseModel):
    property_id: int
    distributor: str = Field(min_length=2, max_length=100)
    tariff_class: str = Field(min_length=2, max_length=80)
    modality: str = Field(min_length=2, max_length=80)
    locality: str | None = Field(default=None, max_length=100)
    value_brl_kwh: Decimal = Field(gt=0, max_digits=12, decimal_places=6)
    valid_from: date
    valid_until: date | None = None
    source: Literal["manual"] = "manual"

    @model_validator(mode="after")
    def date_range(self):
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("Período de tarifa inválido")
        return self


class TariffOut(ORMModel):
    id: int
    property_id: int
    distributor: str
    tariff_class: str
    modality: str
    locality: str | None
    value_brl_kwh: Decimal
    valid_from: date
    valid_until: date | None
    source: str
    collected_at: datetime
    source_reference: str | None = None
    source_details: dict | None = None
    created_by_id: int | None = None


class AneelTariffImportIn(BaseModel):
    property_id: int
    source_row_id: int = Field(ge=1)


class AlertOut(ORMModel):
    id: int
    property_id: int
    origin: str
    rule: str
    fingerprint: str
    details: dict
    occurred_at: datetime
    severity: str
    status: str
    resolved_at: datetime | None
    resolved_by_id: int | None
    resolution_history: list


class AlertResolveIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class AlertEvaluationOut(BaseModel):
    created: int
    reopened: int
    automatically_resolved: int
    active: int
    alerts: list[AlertOut]


class MeteorologicalStationIn(BaseModel):
    station_code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=2, max_length=160)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)


class MeteorologicalStationOut(ORMModel):
    id: int
    property_id: int
    source: str
    station_code: str
    name: str
    city: str | None
    state: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    is_active: bool
    created_at: datetime


class MeteorologicalObservationOut(ORMModel):
    id: int
    property_id: int | None
    station_id: int | None
    source: str
    station_code: str
    variable: str
    value: Decimal
    unit: str
    interval_start_at: datetime | None = None
    observed_at: datetime
    collected_at: datetime
    reference: str | None = None
    created_by_id: int | None = None
    reviewed_by_id: int | None = None
    reviewed_at: datetime | None = None
    is_valid: bool
    quality: str


class CollectionRunOut(ORMModel):
    id: int
    source: str
    requested_year: int | None
    started_at: datetime
    finished_at: datetime | None
    status: str
    message: str | None
    imported_count: int
    last_valid_at: datetime | None


class MeteorologyOut(BaseModel):
    is_demo: bool = False
    station: MeteorologicalStationOut | None
    configured: bool
    configuration_message: str
    configured_variables: list[str]
    latest_observations: list[MeteorologicalObservationOut]
    recent_observations: list[MeteorologicalObservationOut]
    last_observation_at: datetime | None
    last_collected_at: datetime | None
    last_collection: CollectionRunOut | None


class MeteorologySyncIn(BaseModel):
    year: int = Field(ge=2000, le=2100)


class MeteorologySyncOut(BaseModel):
    status: str
    imported_count: int
    message: str
    last_valid_at: datetime | None


class CurvePoint(BaseModel):
    level: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    volume: Decimal = Field(ge=0, max_digits=16, decimal_places=3)


class CurveIn(BaseModel):
    survey_date: date
    survey_source: str = Field(min_length=1, max_length=255)
    survey_responsible: str = Field(min_length=1, max_length=160)
    level_unit: Literal["m"]
    volume_unit: Literal["m3"]
    points: list[CurvePoint] = Field(min_length=2, max_length=10000)

    @model_validator(mode="after")
    def ordered(self):
        if not self.survey_source.strip() or not self.survey_responsible.strip():
            raise ValueError("Informe a origem e o responsável pelo levantamento")
        for a, b in zip(self.points, self.points[1:]):
            if a.level >= b.level or a.volume > b.volume:
                raise ValueError("Cotas devem crescer sem duplicidade e volumes não podem diminuir")
        return self


class CurveApprovalIn(BaseModel):
    valid_from: date
    valid_until: date

    @model_validator(mode="after")
    def validity_order(self):
        if self.valid_until < self.valid_from:
            raise ValueError("O fim da vigência deve ser igual ou posterior ao início")
        return self


class HydrometerOutorgaLinkIn(BaseModel):
    outorga_id: int = Field(gt=0)
    valid_from_at: datetime
    valid_until_at: datetime | None = None

    @field_validator("valid_from_at", "valid_until_at")
    @classmethod
    def aware_link_times(cls, value):
        return require_aware(value) if value is not None else None

    @model_validator(mode="after")
    def valid_interval(self):
        if self.valid_until_at is not None and self.valid_until_at <= self.valid_from_at:
            raise ValueError("O fim da vigência deve ser posterior ao início")
        return self


class HydrometerOutorgaLinkCloseIn(BaseModel):
    valid_until_at: datetime

    @field_validator("valid_until_at")
    @classmethod
    def aware_link_end(cls, value): return require_aware(value)


class MeasurementReviewIn(BaseModel):
    approved: bool
    note: str = Field(min_length=1, max_length=1000)

    @field_validator("note")
    @classmethod
    def review_note_not_blank(cls, value):
        if not value.strip(): raise ValueError("Informe a justificativa da revisão")
        return value.strip()


class RainfallIntervalIn(BaseModel):
    station_id: int = Field(gt=0)
    value_mm: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    period_start_at: datetime
    period_end_at: datetime
    source: Literal["manual", "medida", "simulada"] = "manual"
    reference: str = Field(min_length=1, max_length=255)

    @field_validator("period_start_at", "period_end_at")
    @classmethod
    def aware_rain_times(cls, value): return require_aware(value)

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_end_at <= self.period_start_at:
            raise ValueError("O fim do intervalo de chuva deve ser posterior ao início")
        if not self.reference.strip():
            raise ValueError("Informe a origem ou documento da medição")
        return self


class BalanceFlowEvidenceIn(BaseModel):
    value_m3: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    period_start_at: datetime
    period_end_at: datetime
    source: Literal["manual", "medida", "documento"]
    reference: str = Field(min_length=1, max_length=255)

    @field_validator("period_start_at", "period_end_at")
    @classmethod
    def aware_flow_times(cls, value): return require_aware(value)

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_end_at <= self.period_start_at:
            raise ValueError("O fim do intervalo deve ser posterior ao início")
        if not self.reference.strip():
            raise ValueError("Informe a evidência da saída quantificada")
        return self


class RecordStateIn(BaseModel):
    is_active: bool


class MeterEdit(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    rated_power_kw: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    rated_power_cv: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)

    @model_validator(mode="after")
    def power_choice(self):
        if self.rated_power_kw is not None and self.rated_power_cv is not None:
            raise ValueError("Informe potência em kW ou em CV, não ambas")
        return self


class PermitEdit(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    permit_number: str = Field(min_length=1, max_length=100)
    issued_on: date
    valid_from: date
    valid_until: date
    water_body: str = Field(min_length=2, max_length=160)
    municipality: str = Field(min_length=2, max_length=100)
    coordinates_gms: str = Field(min_length=4, max_length=120)
    state: str = Field(pattern=r"^[A-Za-z]{2}$")
    irrigated_area_ha: Decimal = Field(gt=0, max_digits=12, decimal_places=3)

    @model_validator(mode="after")
    def dates(self):
        if self.valid_until < self.valid_from or self.issued_on > self.valid_from:
            raise ValueError("Datas de vigência inválidas")
        return self


class DocumentReviewIn(BaseModel):
    fields: dict[str, str | None]
    approve: bool = False

    @field_validator("fields")
    @classmethod
    def bounded_fields(cls, value):
        if len(value) > 40 or any(not k.strip() or len(k) > 100 or (v is not None and len(v) > 2000) for k, v in value.items()):
            raise ValueError("Campos de revisão inválidos ou extensos demais")
        return value


class DocumentExtractIn(BaseModel):
    field: Literal["holder", "permit_number", "water_body", "valid_from", "valid_until", "monthly_demands"]
    exact_text: str = Field(min_length=1, max_length=2000)

    @field_validator("exact_text")
    @classmethod
    def nonblank_excerpt(cls, value):
        if not value.strip(): raise ValueError("Informe um trecho localizado no texto")
        return value


class BalanceDatum(BaseModel):
    value: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    unit: str = Field(min_length=1, max_length=12)
    source: Literal["manual", "medida", "estimada", "simulada"]
    reference: str = Field(min_length=1, max_length=255)
    period_start: datetime
    period_end: datetime
    coverage_complete: bool
    observed_at: datetime | None = None

    @field_validator("period_start", "period_end", "observed_at")
    @classmethod
    def aware_balance_times(cls, value):
        return require_aware(value) if value is not None else None

    @field_validator("reference")
    @classmethod
    def reference_not_blank(cls, value):
        if not value.strip(): raise ValueError("Informe identificação da origem")
        return value.strip()


class BalanceMonthIn(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    inputs: dict[str, BalanceDatum]


class TotalizerEventIn(BaseModel):
    event_type: Literal["reinicio", "troca", "retorno"]
    observed_at: datetime
    note: str = Field(min_length=1, max_length=2000)

    @field_validator("observed_at")
    @classmethod
    def event_time_aware(cls, value): return require_aware(value)

    @field_validator("note")
    @classmethod
    def note_not_blank(cls, value):
        if not value.strip(): raise ValueError("Informe a evidência do evento")
        return value.strip()

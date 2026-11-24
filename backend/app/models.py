from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


def now_utc():
    return datetime.now(timezone.utc)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class User(Timestamped, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    cpf_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    cpf_fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    business_address: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    properties: Mapped[list["Property"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Property(Timestamped, Base):
    __tablename__ = "properties"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    cep: Mapped[str] = mapped_column(String(9), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    boundary_kml: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[User] = relationship(back_populates="properties")
    reservoirs: Mapped[list["Reservoir"]] = relationship(back_populates="property", cascade="all, delete-orphan")
    outorgas: Mapped[list["Outorga"]] = relationship(back_populates="property", cascade="all, delete-orphan")
    meteorological_stations: Mapped[list["MeteorologicalStation"]] = relationship(back_populates="property", cascade="all, delete-orphan")


class Reservoir(Timestamped, Base):
    __tablename__ = "reservoirs"
    __table_args__ = (
        CheckConstraint("base_width_m > 0 AND base_length_m > 0 AND top_width_m >= base_width_m AND top_length_m >= base_length_m AND height_m > 0", name="ck_reservoir_dimensions"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    base_width_m: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    base_length_m: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    top_width_m: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    top_length_m: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    height_m: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    geometry_kml: Mapped[str] = mapped_column(Text, nullable=False)
    geometry_assumption: Mapped[str] = mapped_column(String(120), default="frustum_rectangular_prism", nullable=False)
    property: Mapped[Property] = relationship(back_populates="reservoirs")
    hydrometers: Mapped[list["Hydrometer"]] = relationship(back_populates="reservoir", cascade="all, delete-orphan")
    level_station: Mapped["LevelStation | None"] = relationship(back_populates="reservoir", cascade="all, delete-orphan", uselist=False)


class Outorga(Timestamped, Base):
    __tablename__ = "outorgas"
    __table_args__ = (Index("ix_outorga_property_validity", "property_id", "valid_from", "valid_until"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    permit_number: Mapped[str] = mapped_column(String(100), nullable=False)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    water_body: Mapped[str] = mapped_column(String(160), nullable=False)
    municipality: Mapped[str] = mapped_column(String(100), nullable=False)
    coordinates_gms: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    irrigated_area_ha: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    property: Mapped[Property] = relationship(back_populates="outorgas")
    demands: Mapped[list["MonthlyDemand"]] = relationship(back_populates="outorga", cascade="all, delete-orphan", order_by="MonthlyDemand.month")
    hydrometers: Mapped[list["Hydrometer"]] = relationship(back_populates="outorga")


class MonthlyDemand(Timestamped, Base):
    __tablename__ = "monthly_demands"
    __table_args__ = (
        UniqueConstraint("outorga_id", "month", name="uq_demand_outorga_month"),
        CheckConstraint("month >= 1 AND month <= 12 AND max_flow_m3_h >= 0 AND daily_hours >= 0 AND authorized_days >= 0 AND monthly_volume_m3 >= 0", name="ck_demand_values"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    outorga_id: Mapped[int] = mapped_column(ForeignKey("outorgas.id", ondelete="CASCADE"), index=True, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    max_flow_m3_h: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    daily_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    authorized_days: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_volume_m3: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    extracted_values: Mapped[dict | None] = mapped_column(JSON)
    outorga: Mapped[Outorga] = relationship(back_populates="demands")


class DemandRevision(Timestamped, Base):
    __tablename__ = "demand_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    demand_id: Mapped[int] = mapped_column(ForeignKey("monthly_demands.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    previous_values: Mapped[dict] = mapped_column(JSON, nullable=False)
    corrected_values: Mapped[dict] = mapped_column(JSON, nullable=False)


class Hydrometer(Timestamped, Base):
    __tablename__ = "hydrometers"
    id: Mapped[int] = mapped_column(primary_key=True)
    reservoir_id: Mapped[int] = mapped_column(ForeignKey("reservoirs.id", ondelete="CASCADE"), index=True, nullable=False)
    outorga_id: Mapped[int | None] = mapped_column(ForeignKey("outorgas.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    rated_power_kw: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    rated_power_cv: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    device_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reservoir: Mapped[Reservoir] = relationship(back_populates="hydrometers")
    outorga: Mapped[Outorga | None] = relationship(back_populates="hydrometers")
    readings: Mapped[list["HydrometerReading"]] = relationship(back_populates="hydrometer", cascade="all, delete-orphan")


class HydrometerReading(Timestamped, Base):
    __tablename__ = "hydrometer_readings"
    __table_args__ = (
        UniqueConstraint("hydrometer_id", "external_id", name="uq_hydrometer_external_id"),
        UniqueConstraint("hydrometer_id", "observed_at", name="uq_hydrometer_observed_at"),
        CheckConstraint("volume_m3 >= 0 AND (flow_m3_h IS NULL OR flow_m3_h >= 0)", name="ck_hydrometer_reading_values"),
        Index("ix_hydrometer_reading_observed", "hydrometer_id", "observed_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    hydrometer_id: Mapped[int] = mapped_column(ForeignKey("hydrometers.id", ondelete="CASCADE"), index=True, nullable=False)
    flow_m3_h: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="m³", nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(120))
    quality: Mapped[str] = mapped_column(String(120), default="não revisada", nullable=False)
    raw_totalizer_m3: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    hydrometer: Mapped[Hydrometer] = relationship(back_populates="readings")


class LevelStation(Timestamped, Base):
    __tablename__ = "level_stations"
    __table_args__ = (UniqueConstraint("reservoir_id", name="uq_level_station_reservoir"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    reservoir_id: Mapped[int] = mapped_column(ForeignKey("reservoirs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    minimum_m: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    maximum_m: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    reservoir: Mapped[Reservoir] = relationship(back_populates="level_station")
    readings: Mapped[list["LevelReading"]] = relationship(back_populates="station", cascade="all, delete-orphan")


class LevelReading(Timestamped, Base):
    __tablename__ = "level_readings"
    __table_args__ = (Index("ix_level_reading_observed", "station_id", "observed_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("level_stations.id", ondelete="CASCADE"), index=True, nullable=False)
    level_m: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    image_review_id: Mapped[int | None] = mapped_column(ForeignKey("level_image_reviews.id", ondelete="SET NULL"), unique=True)
    quality: Mapped[str] = mapped_column(String(120), default="não revisada", nullable=False)
    station: Mapped[LevelStation] = relationship(back_populates="readings")


class LevelImageReview(Timestamped, Base):
    __tablename__ = "level_image_reviews"
    __table_args__ = (
        CheckConstraint("status IN ('inconclusive', 'pending_review', 'confirmed')", name="ck_level_image_review_status"),
        CheckConstraint("size_bytes > 0 AND width_px > 0 AND height_px > 0", name="ck_level_image_review_file_dimensions"),
        Index("ix_level_image_review_station_captured", "station_id", "captured_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True, nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("level_stations.id", ondelete="CASCADE"), index=True, nullable=False)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    storage_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(180), nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), default="m", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="inconclusive", nullable=False)
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    suggested_level_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    confirmed_level_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    inconclusive_reason: Mapped[str | None] = mapped_column(Text)
    analysis_details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    calibration: Mapped[dict | None] = mapped_column(JSON)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revisions: Mapped[list["LevelImageReviewRevision"]] = relationship(cascade="all, delete-orphan", order_by="LevelImageReviewRevision.created_at")


class LevelImageReviewRevision(Base):
    __tablename__ = "level_image_review_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("level_image_reviews.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_values: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    corrected_values: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class EnergyTariff(Timestamped, Base):
    __tablename__ = "energy_tariffs"
    __table_args__ = (Index("ix_tariff_property_validity", "property_id", "valid_from", "valid_until"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True, nullable=False)
    distributor: Mapped[str] = mapped_column(String(100), nullable=False)
    tariff_class: Mapped[str] = mapped_column(String(80), nullable=False)
    modality: Mapped[str] = mapped_column(String(80), nullable=False)
    locality: Mapped[str | None] = mapped_column(String(100))
    value_brl_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class MeteorologicalObservation(Timestamped, Base):
    __tablename__ = "meteorological_observations"
    __table_args__ = (
        UniqueConstraint("property_id", "station_id", "variable", "observed_at", name="uq_weather_property_station_observation"),
        Index("ix_weather_station_observed", "station_code", "observed_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable to preserve records imported by earlier versions without property linkage.
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("meteorological_stations.id", ondelete="SET NULL"), index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    station_code: Mapped[str] = mapped_column(String(80), nullable=False)
    variable: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quality: Mapped[str] = mapped_column(String(80), default="raw_unvalidated", nullable=False)
    property: Mapped[Property | None] = relationship()
    station: Mapped["MeteorologicalStation | None"] = relationship(back_populates="observations")


class MeteorologicalStation(Timestamped, Base):
    __tablename__ = "meteorological_stations"
    __table_args__ = (
        UniqueConstraint("property_id", "source", "station_code", name="uq_weather_property_source_station"),
        Index("ix_weather_property_active", "property_id", "is_active"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="INMET", nullable=False)
    station_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    property: Mapped[Property] = relationship(back_populates="meteorological_stations")
    observations: Mapped[list[MeteorologicalObservation]] = relationship(back_populates="station", cascade="all, delete-orphan")


class CollectionRun(Timestamped, Base):
    __tablename__ = "collection_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("meteorological_stations.id", ondelete="SET NULL"), index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requested_year: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    imported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_valid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ManagedDocument(Timestamped, Base):
    __tablename__ = "managed_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True, nullable=False)
    outorga_id: Mapped[int | None] = mapped_column(ForeignKey("outorgas.id", ondelete="SET NULL"), index=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(180), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), default="pendente", nullable=False)
    extracted_fields: Mapped[dict | None] = mapped_column(JSON)


class Alert(Timestamped, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_alert_fingerprint"),
        CheckConstraint("severity IN ('info', 'warning', 'critical')", name="ck_alert_severity"),
        CheckConstraint("status IN ('open', 'resolved')", name="ck_alert_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(220), nullable=False)
    origin: Mapped[str] = mapped_column(String(80), nullable=False)
    rule: Mapped[str] = mapped_column(String(160), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="warning", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolution_history: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

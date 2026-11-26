"""Versioned surveys, reviewed permits and audit routes; no external transports."""
import hashlib
import re
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import File, HTTPException, Query, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.main import (app, Db, CurrentUser, ensure_outorga, ensure_property,
                      ensure_reservoir, private_media_root, settings)
from app.models import (AlertEvaluation, BalanceFlowEvidence, Hydrometer, HydrometerOutorgaLink,
                        HydrometerReading, LevelReading, LevelStation, ManagedDocument,
                        MeteorologicalObservation, MeteorologicalStation, MonthlyBalance,
                        NormalizedTelemetry, Outorga, RecordRevision, Reservoir, StageVolumeCurve,
                        TotalizerEvent)
from app.schemas import (BalanceFlowEvidenceIn, BalanceMonthIn, CurveApprovalIn, CurveIn,
                         DocumentExtractIn, DocumentReviewIn, HydrometerOutorgaLinkCloseIn,
                         HydrometerOutorgaLinkIn, HydrometerOut, MeasurementReviewIn,
                         MeterEdit, OutorgaOut, PermitEdit, RainfallIntervalIn,
                         RecordStateIn, TotalizerEventIn)
from app.services.balance_auto import assess_automatic_month, month_bounds_utc
from app.services.balance_period import assess_month
from app.services.permit_pdf import MAX_PDF_BYTES, inspect_pdf
from app.services.ruler_images import sanitize_original_filename
from app.services.stage_volume import interpolate_volume
from app.services.telemetry_contract import NormalizedReading
from app.services.permit_links import resolve_link, utc as aware_utc, validate_no_overlap


def audit(db, user, property_id, record_type, record_id, action, previous, new):
    db.add(RecordRevision(property_id=property_id, user_id=user.id, record_type=record_type,
                          record_id=record_id, action=action, previous_values=jsonable_encoder(previous),
                          new_values=jsonable_encoder(new)))


def meter_for_user(db, user, meter_id):
    meter = db.get(Hydrometer, meter_id)
    if meter is None:
        raise HTTPException(status_code=404, detail="Hidrômetro não encontrado")
    reservoir = ensure_reservoir(db, meter.reservoir_id, user)
    return meter, reservoir


def revision_rows(db, property_id, record_type, record_id, skip, limit):
    rows = db.scalars(select(RecordRevision).where(RecordRevision.property_id == property_id,
        RecordRevision.record_type == record_type, RecordRevision.record_id == record_id)
        .order_by(RecordRevision.id.desc()).offset(skip).limit(limit)).all()
    return [{"id": r.id, "user_id": r.user_id, "action": r.action, "previous_values": r.previous_values,
             "new_values": r.new_values, "created_at": r.created_at} for r in rows]


@app.patch("/hydrometers/{meter_id}", response_model=HydrometerOut)
def edit_meter(meter_id: int, data: MeterEdit, db: Db, user: CurrentUser):
    meter, reservoir = meter_for_user(db, user, meter_id)
    values = data.model_dump(exclude_unset=True)
    previous = {key: getattr(meter, key) for key in values}
    audit(db, user, reservoir.property_id, "hydrometer", meter.id, "edit", previous, values)
    for key, value in values.items(): setattr(meter, key, value)
    db.commit(); db.refresh(meter)
    return meter


@app.patch("/hydrometers/{meter_id}/state", response_model=HydrometerOut)
def meter_state(meter_id: int, data: RecordStateIn, db: Db, user: CurrentUser):
    meter, reservoir = meter_for_user(db, user, meter_id)
    audit(db, user, reservoir.property_id, "hydrometer", meter.id, "state", {"is_active": meter.is_active}, data.model_dump())
    meter.is_active = data.is_active
    db.commit(); db.refresh(meter)
    return meter


@app.get("/hydrometers/{meter_id}/history")
def meter_history(meter_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    meter, reservoir = meter_for_user(db, user, meter_id)
    link_ids = select(HydrometerOutorgaLink.id).where(HydrometerOutorgaLink.hydrometer_id == meter.id)
    rows = db.scalars(select(RecordRevision).where(RecordRevision.property_id == reservoir.property_id,
        or_(and_(RecordRevision.record_type == "hydrometer", RecordRevision.record_id == meter.id),
            and_(RecordRevision.record_type == "hydrometer_outorga_link", RecordRevision.record_id.in_(link_ids))))
        .order_by(RecordRevision.id.desc()).offset(skip).limit(limit)).all()
    return [{"id": r.id, "user_id": r.user_id, "action": r.action, "previous_values": r.previous_values,
             "new_values": r.new_values, "created_at": r.created_at} for r in rows]


def link_view(link):
    return {"id": link.id, "property_id": link.property_id, "hydrometer_id": link.hydrometer_id,
            "outorga_id": link.outorga_id, "valid_from_at": link.valid_from_at,
            "valid_until_at": link.valid_until_at, "outorga_valid_from_snapshot": link.outorga_valid_from_snapshot,
            "outorga_valid_until_snapshot": link.outorga_valid_until_snapshot, "created_by_id": link.created_by_id,
            "created_at": link.created_at, "closed_by_id": link.closed_by_id, "closed_at": link.closed_at}


@app.get("/hydrometers/{meter_id}/outorga-links")
def list_meter_outorga_links(meter_id: int, db: Db, user: CurrentUser,
                             skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    meter, _ = meter_for_user(db, user, meter_id)
    rows = db.scalars(select(HydrometerOutorgaLink).where(HydrometerOutorgaLink.hydrometer_id == meter.id)
        .order_by(HydrometerOutorgaLink.valid_from_at.desc(), HydrometerOutorgaLink.id.desc())
        .offset(skip).limit(limit)).all()
    return [link_view(row) for row in rows]


@app.post("/hydrometers/{meter_id}/outorga-links", status_code=201)
def create_meter_outorga_link(meter_id: int, data: HydrometerOutorgaLinkIn, db: Db, user: CurrentUser):
    meter, reservoir = meter_for_user(db, user, meter_id)
    if meter.kind != "entrada":
        raise HTTPException(status_code=422, detail="Vínculo de outorga só se aplica a hidrômetro de entrada")
    outorga = ensure_outorga(db, data.outorga_id, user)
    if outorga.property_id != reservoir.property_id:
        raise HTTPException(status_code=422, detail="Hidrômetro e outorga devem pertencer à mesma propriedade")
    if not outorga.is_active:
        raise HTTPException(status_code=409, detail="Não é possível iniciar um vínculo com outorga inativa")
    local_tz = ZoneInfo("America/Sao_Paulo")
    legal_start = datetime.combine(outorga.valid_from, time.min, local_tz).astimezone(timezone.utc)
    legal_end = datetime.combine(outorga.valid_until + timedelta(days=1), time.min, local_tz).astimezone(timezone.utc)
    start = aware_utc(data.valid_from_at)
    end = aware_utc(data.valid_until_at) if data.valid_until_at else None
    if start < legal_start or (end is not None and end > legal_end) or (end is None and start >= legal_end):
        raise HTTPException(status_code=422, detail="Vigência do vínculo precisa caber na vigência informada da outorga")
    # Serializes concurrent assignment changes for this meter in PostgreSQL.
    db.scalar(select(Hydrometer).where(Hydrometer.id == meter.id).with_for_update())
    existing = db.scalars(select(HydrometerOutorgaLink).where(HydrometerOutorgaLink.hydrometer_id == meter.id)
        .order_by(HydrometerOutorgaLink.valid_from_at).with_for_update()).all()
    try:
        normalized_existing = [SimpleNamespace(id=link.id, valid_from_at=_stored_utc(link.valid_from_at),
            valid_until_at=_stored_utc(link.valid_until_at)) for link in existing]
        validate_no_overlap(normalized_existing, data.valid_from_at, data.valid_until_at)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    link = HydrometerOutorgaLink(property_id=reservoir.property_id, hydrometer_id=meter.id, outorga_id=outorga.id,
        valid_from_at=start, valid_until_at=end, outorga_valid_from_snapshot=outorga.valid_from,
        outorga_valid_until_snapshot=outorga.valid_until, created_by_id=user.id, created_at=datetime.now(timezone.utc))
    db.add(link)
    db.flush()
    old_current = meter.outorga_id
    if end is None:
        meter.outorga_id = outorga.id  # Compatibility/display only; historical queries use the temporal table.
    audit(db, user, reservoir.property_id, "hydrometer_outorga_link", link.id, "create",
          {"outorga_id": old_current}, {"outorga_id": outorga.id, "valid_from_at": start, "valid_until_at": end})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Vínculo duplicado ou conflitante")
    db.refresh(link)
    return link_view(link)


@app.post("/hydrometer-outorga-links/{link_id}/close")
def close_meter_outorga_link(link_id: int, data: HydrometerOutorgaLinkCloseIn, db: Db, user: CurrentUser):
    link = db.get(HydrometerOutorgaLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado")
    ensure_property(db, link.property_id, user)
    if link.valid_until_at is not None:
        raise HTTPException(status_code=409, detail="Esse vínculo já tem fim de vigência registrado")
    end = aware_utc(data.valid_until_at)
    if end <= _stored_utc(link.valid_from_at):
        raise HTTPException(status_code=422, detail="O fim deve ser posterior ao início da vigência")
    legal_end = datetime.combine(link.outorga_valid_until_snapshot + timedelta(days=1), time.min,
                                 ZoneInfo("America/Sao_Paulo")).astimezone(timezone.utc)
    if end > legal_end:
        raise HTTPException(status_code=422, detail="O vínculo não pode ultrapassar a vigência documentada da outorga")
    before = {"valid_until_at": None, "closed_by_id": None, "closed_at": None}
    link.valid_until_at = end
    link.closed_by_id = user.id
    link.closed_at = datetime.now(timezone.utc)
    meter = db.get(Hydrometer, link.hydrometer_id)
    if meter and meter.outorga_id == link.outorga_id:
        now = datetime.now(timezone.utc)
        current = db.scalar(select(HydrometerOutorgaLink).where(
            HydrometerOutorgaLink.hydrometer_id == meter.id,
            HydrometerOutorgaLink.valid_from_at <= now,
            (HydrometerOutorgaLink.valid_until_at.is_(None) | (HydrometerOutorgaLink.valid_until_at > now)),
            HydrometerOutorgaLink.id != link.id,
        ).order_by(HydrometerOutorgaLink.valid_from_at.desc()).limit(1))
        meter.outorga_id = current.outorga_id if current else None
    audit(db, user, link.property_id, "hydrometer_outorga_link", link.id, "close", before,
          {"valid_until_at": end, "closed_by_id": user.id, "closed_at": link.closed_at})
    db.commit(); db.refresh(link)
    return link_view(link)


@app.post("/hydrometer-readings/{reading_id}/review")
def review_hydrometer_reading(reading_id: int, data: MeasurementReviewIn, db: Db, user: CurrentUser):
    reading = db.get(HydrometerReading, reading_id)
    if reading is None:
        raise HTTPException(status_code=404, detail="Leitura não encontrada")
    meter, reservoir = meter_for_user(db, user, reading.hydrometer_id)
    if data.approved:
        if reading.source == "simulada" or reading.volume_m3 is None:
            raise HTTPException(status_code=409, detail="Leitura simulada ou sem volume não pode comprovar cobertura")
        if reading.interval_start_at is None or _stored_utc(reading.interval_start_at) >= _stored_utc(reading.observed_at):
            raise HTTPException(status_code=409, detail="Informe e confira o início real do intervalo antes da revisão")
        if reading.unit.strip().lower() not in {"m3", "m³"}:
            raise HTTPException(status_code=409, detail="Unidade incompatível; não é possível aprovar a leitura")
    previous = {"quality": reading.quality, "interval_start_at": reading.interval_start_at,
                "observed_at": reading.observed_at, "volume_m3": reading.volume_m3, "unit": reading.unit}
    reading.quality = "validada" if data.approved else "rejeitada"
    audit(db, user, reservoir.property_id, "hydrometer_reading", reading.id, "review", previous,
          {"quality": reading.quality, "note": data.note, "reviewed_by_id": user.id, "reviewed_at": datetime.now(timezone.utc)})
    db.commit(); db.refresh(reading)
    return {"id": reading.id, "hydrometer_id": reading.hydrometer_id, "quality": reading.quality,
            "reviewed_by_id": user.id, "reviewed_at": datetime.now(timezone.utc)}


@app.post("/level-readings/{reading_id}/review")
def review_level_reading(reading_id: int, data: MeasurementReviewIn, db: Db, user: CurrentUser):
    reading = db.get(LevelReading, reading_id)
    if reading is None:
        raise HTTPException(status_code=404, detail="Leitura de nível não encontrada")
    station = db.get(LevelStation, reading.station_id)
    reservoir = ensure_reservoir(db, station.reservoir_id, user)
    if data.approved and reading.source == "simulada":
        raise HTTPException(status_code=409, detail="Leitura simulada não pode comprovar cobertura")
    if data.approved and (reading.level_m < station.minimum_m or reading.level_m > min(station.maximum_m, reservoir.height_m)):
        raise HTTPException(status_code=409, detail="Leitura fora da faixa da estação ou do reservatório; corrija com evidência antes de aprovar")
    previous = {"quality": reading.quality, "level_m": reading.level_m, "observed_at": reading.observed_at}
    reading.quality = "validada" if data.approved else "rejeitada"
    audit(db, user, reservoir.property_id, "level_reading", reading.id, "review", previous,
          {"quality": reading.quality, "note": data.note, "reviewed_by_id": user.id, "reviewed_at": datetime.now(timezone.utc)})
    db.commit(); db.refresh(reading)
    return {"id": reading.id, "station_id": reading.station_id, "quality": reading.quality,
            "reviewed_by_id": user.id, "reviewed_at": datetime.now(timezone.utc)}


@app.post("/properties/{property_id}/rainfall-intervals", status_code=201)
def create_rainfall_interval(property_id: int, data: RainfallIntervalIn, db: Db, user: CurrentUser):
    ensure_property(db, property_id, user)
    station = db.get(MeteorologicalStation, data.station_id)
    if station is None or station.property_id != property_id or not station.is_active:
        raise HTTPException(status_code=404, detail="Estação ativa desta propriedade não encontrada")
    existing = db.scalar(select(MeteorologicalObservation).where(
        MeteorologicalObservation.property_id == property_id,
        MeteorologicalObservation.station_id == station.id,
        MeteorologicalObservation.variable == "precipitation",
        MeteorologicalObservation.observed_at == data.period_end_at,
    ))
    if existing:
        raise HTTPException(status_code=409, detail="Já existe precipitação registrada neste instante de término")
    row = MeteorologicalObservation(property_id=property_id, station_id=station.id, source=data.source,
        station_code=station.station_code, variable="precipitation", value=data.value_mm, unit="mm",
        interval_start_at=aware_utc(data.period_start_at), observed_at=aware_utc(data.period_end_at),
        collected_at=datetime.now(timezone.utc), reference=data.reference.strip(), is_valid=True,
        quality="pendente de revisão", created_by_id=user.id)
    db.add(row)
    db.flush()
    audit(db, user, property_id, "meteorological_observation", row.id, "create", {},
          {"station_id": station.id, "variable": "precipitation", "value": str(data.value_mm), "unit": "mm",
           "interval_start_at": row.interval_start_at, "observed_at": row.observed_at,
           "source": data.source, "reference": row.reference, "quality": row.quality})
    db.commit(); db.refresh(row)
    return row


@app.post("/meteorological-observations/{observation_id}/review")
def review_meteorological_observation(observation_id: int, data: MeasurementReviewIn, db: Db, user: CurrentUser):
    row = db.get(MeteorologicalObservation, observation_id)
    if row is None or row.property_id is None:
        raise HTTPException(status_code=404, detail="Observação não encontrada")
    ensure_property(db, row.property_id, user)
    if row.variable != "precipitation":
        raise HTTPException(status_code=422, detail="A revisão de balanço aceita apenas observações de precipitação")
    if data.approved:
        if row.source == "simulada" or row.unit.strip().lower() != "mm" or row.interval_start_at is None:
            raise HTTPException(status_code=409, detail="Origem, unidade ou intervalo não comprovam precipitação")
        if _stored_utc(row.interval_start_at) >= _stored_utc(row.observed_at):
            raise HTTPException(status_code=409, detail="Intervalo de precipitação inválido")
    previous = {"quality": row.quality, "is_valid": row.is_valid, "interval_start_at": row.interval_start_at,
                "observed_at": row.observed_at, "value": row.value, "unit": row.unit}
    row.quality = "validada" if data.approved else "rejeitada"
    row.is_valid = data.approved
    row.reviewed_by_id = user.id
    row.reviewed_at = datetime.now(timezone.utc)
    audit(db, user, row.property_id, "meteorological_observation", row.id, "review", previous,
          {"quality": row.quality, "is_valid": row.is_valid, "note": data.note,
           "reviewed_by_id": user.id, "reviewed_at": row.reviewed_at})
    db.commit(); db.refresh(row)
    return row


@app.post("/reservoirs/{reservoir_id}/water-balance/other-outflows", status_code=201)
def create_other_outflow_evidence(reservoir_id: int, data: BalanceFlowEvidenceIn, db: Db, user: CurrentUser):
    ensure_reservoir(db, reservoir_id, user)
    overlap = db.scalar(select(BalanceFlowEvidence.id).where(
        BalanceFlowEvidence.reservoir_id == reservoir_id,
        BalanceFlowEvidence.period_start_at < aware_utc(data.period_end_at),
        BalanceFlowEvidence.period_end_at > aware_utc(data.period_start_at),
    ).limit(1))
    if overlap:
        raise HTTPException(status_code=409, detail="Intervalo sobreposto a outra evidência de outras saídas")
    row = BalanceFlowEvidence(reservoir_id=reservoir_id, kind="other_outflow", value_m3=data.value_m3,
        unit="m3", period_start_at=aware_utc(data.period_start_at), period_end_at=aware_utc(data.period_end_at),
        source=data.source, reference=data.reference.strip(), quality="pendente de revisao", created_by_id=user.id,
        created_at=datetime.now(timezone.utc))
    db.add(row); db.flush()
    reservoir = db.get(Reservoir, reservoir_id)
    audit(db, user, reservoir.property_id, "balance_flow_evidence", row.id, "create", {},
          {"kind": row.kind, "value_m3": str(row.value_m3), "period_start_at": row.period_start_at,
           "period_end_at": row.period_end_at, "source": row.source, "reference": row.reference,
           "quality": row.quality})
    db.commit(); db.refresh(row)
    return row


@app.post("/water-balance/other-outflows/{evidence_id}/review")
def review_other_outflow_evidence(evidence_id: int, data: MeasurementReviewIn, db: Db, user: CurrentUser):
    row = db.get(BalanceFlowEvidence, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evidência de saída não encontrada")
    reservoir = ensure_reservoir(db, row.reservoir_id, user)
    previous = {"quality": row.quality, "value_m3": row.value_m3, "unit": row.unit,
                "period_start_at": row.period_start_at, "period_end_at": row.period_end_at}
    row.quality = "validada" if data.approved else "rejeitada"
    row.reviewed_by_id = user.id
    row.reviewed_at = datetime.now(timezone.utc)
    audit(db, user, reservoir.property_id, "balance_flow_evidence", row.id, "review", previous,
          {"quality": row.quality, "note": data.note, "reviewed_by_id": user.id, "reviewed_at": row.reviewed_at})
    db.commit(); db.refresh(row)
    return row


@app.get("/reservoirs/{reservoir_id}/water-balance/source-evidence")
def list_balance_source_evidence(reservoir_id: int, db: Db, user: CurrentUser,
                                 year: int = Query(ge=2000, le=2100), month: int = Query(ge=1, le=12),
                                 skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    reservoir = ensure_reservoir(db, reservoir_id, user)
    start, end = month_bounds_utc(year, month)
    stations = db.scalars(select(MeteorologicalStation).where(
        MeteorologicalStation.property_id == reservoir.property_id,
        MeteorologicalStation.source == "INMET", MeteorologicalStation.is_active.is_(True))
        .order_by(MeteorologicalStation.id)).all()
    rain_stmt = select(MeteorologicalObservation).where(
        MeteorologicalObservation.property_id == reservoir.property_id,
        MeteorologicalObservation.variable == "precipitation",
        or_(and_(MeteorologicalObservation.interval_start_at.is_not(None),
                 MeteorologicalObservation.interval_start_at < end,
                 MeteorologicalObservation.observed_at > start),
            and_(MeteorologicalObservation.interval_start_at.is_(None),
                 MeteorologicalObservation.observed_at >= start,
                 MeteorologicalObservation.observed_at < end)))
    rain_rows = db.scalars(rain_stmt.order_by(MeteorologicalObservation.observed_at,
        MeteorologicalObservation.id).offset(skip).limit(limit + 1)).all()
    level_station = db.scalar(select(LevelStation).where(LevelStation.reservoir_id == reservoir_id))
    level_rows = []
    if level_station:
        level_rows = db.scalars(select(LevelReading).where(LevelReading.station_id == level_station.id,
            LevelReading.observed_at >= start, LevelReading.observed_at <= end)
            .order_by(LevelReading.observed_at, LevelReading.id).offset(skip).limit(limit + 1)).all()
    outflow_rows = db.scalars(select(BalanceFlowEvidence).where(
        BalanceFlowEvidence.reservoir_id == reservoir_id,
        BalanceFlowEvidence.period_start_at < end, BalanceFlowEvidence.period_end_at > start)
        .order_by(BalanceFlowEvidence.period_start_at, BalanceFlowEvidence.id)
        .offset(skip).limit(limit + 1)).all()

    def page(rows, view):
        has_more = len(rows) > limit
        items = [view(row) for row in rows[:limit]]
        return {"items": items, "has_more": has_more, "next_skip": skip + limit if has_more else None}

    return {"reservoir_id": reservoir_id, "year": year, "month": month,
        "stations": [{"id": station.id, "station_code": station.station_code,
                      "name": station.name, "source": station.source} for station in stations],
        "rainfall": page(rain_rows, lambda row: {"id": row.id, "station_id": row.station_id,
            "station_code": row.station_code, "value": row.value, "unit": row.unit,
            "period_start_at": row.interval_start_at, "period_end_at": row.observed_at,
            "source": row.source, "quality": row.quality, "reference": row.reference,
            "created_by_id": row.created_by_id, "reviewed_by_id": row.reviewed_by_id,
            "reviewed_at": row.reviewed_at}),
        "levels": page(level_rows, lambda row: {"id": row.id, "level_m": row.level_m,
            "unit": "m", "observed_at": row.observed_at, "source": row.source,
            "quality": row.quality, "image_review_id": row.image_review_id}),
        "other_outflows": page(outflow_rows, lambda row: {"id": row.id, "value": row.value_m3,
            "unit": row.unit, "period_start_at": row.period_start_at, "period_end_at": row.period_end_at,
            "source": row.source, "quality": row.quality, "reference": row.reference,
            "created_by_id": row.created_by_id, "reviewed_by_id": row.reviewed_by_id,
            "reviewed_at": row.reviewed_at})}


def event_view(event):
    return {"id": event.id, "hydrometer_id": event.hydrometer_id, "user_id": event.user_id,
            "event_type": event.event_type, "observed_at": event.observed_at, "note": event.note, "created_at": event.created_at}


@app.post("/hydrometers/{meter_id}/totalizer-events", status_code=201)
def create_totalizer_event(meter_id: int, data: TotalizerEventIn, db: Db, user: CurrentUser):
    meter, reservoir = meter_for_user(db, user, meter_id)
    event = TotalizerEvent(hydrometer_id=meter.id, user_id=user.id, event_type=data.event_type,
                           observed_at=data.observed_at.astimezone(timezone.utc), note=data.note)
    db.add(event); db.commit(); db.refresh(event)
    return event_view(event)


@app.get("/hydrometers/{meter_id}/totalizer-events")
def list_totalizer_events(meter_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    meter_for_user(db, user, meter_id)
    rows = db.scalars(select(TotalizerEvent).where(TotalizerEvent.hydrometer_id == meter_id).order_by(TotalizerEvent.id.desc()).offset(skip).limit(limit)).all()
    return [event_view(row) for row in rows]


@app.patch("/outorgas/{outorga_id}", response_model=OutorgaOut)
def edit_permit(outorga_id: int, data: PermitEdit, db: Db, user: CurrentUser):
    permit = ensure_outorga(db, outorga_id, user)
    values = data.model_dump(); values["state"] = values["state"].upper()
    if any(values[key] != getattr(permit, key) for key in ("issued_on", "valid_from", "valid_until")):
        linked_reading = db.scalar(select(HydrometerReading.id).join(Hydrometer).where(Hydrometer.outorga_id == permit.id).limit(1))
        temporal_link = db.scalar(select(HydrometerOutorgaLink.id).where(HydrometerOutorgaLink.outorga_id == permit.id).limit(1))
        if linked_reading or temporal_link:
            raise HTTPException(status_code=409, detail="Vigência legal não pode ser alterada após leituras ou vínculos históricos; preserve a versão documentada e registre novo vínculo quando aplicável.")
    previous = {key: getattr(permit, key) for key in values}
    audit(db, user, permit.property_id, "outorga", permit.id, "edit", previous, values)
    for key, value in values.items(): setattr(permit, key, value)
    db.commit(); db.refresh(permit)
    return permit


@app.patch("/outorgas/{outorga_id}/state", response_model=OutorgaOut)
def permit_state(outorga_id: int, data: RecordStateIn, db: Db, user: CurrentUser):
    permit = ensure_outorga(db, outorga_id, user)
    audit(db, user, permit.property_id, "outorga", permit.id, "state", {"is_active": permit.is_active}, data.model_dump())
    permit.is_active = data.is_active
    db.commit(); db.refresh(permit)
    return permit


@app.get("/outorgas/{outorga_id}/history")
def permit_history(outorga_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    permit = ensure_outorga(db, outorga_id, user)
    return revision_rows(db, permit.property_id, "outorga", permit.id, skip, limit)


def curve_view(curve):
    return {"id": curve.id, "reservoir_id": curve.reservoir_id, "created_by_id": curve.created_by_id,
            "created_at": curve.created_at, "survey_date": curve.survey_date, "survey_source": curve.survey_source,
            "survey_responsible": curve.survey_responsible, "level_unit": curve.level_unit,
            "volume_unit": curve.volume_unit, "points": curve.points, "valid_from": curve.valid_from,
            "valid_until": curve.valid_until, "is_approved": curve.is_approved,
            "approved_by_id": curve.approved_by_id, "approved_at": curve.approved_at}


@app.post("/reservoirs/{reservoir_id}/stage-volume-curves", status_code=201)
def create_curve(reservoir_id: int, data: CurveIn, db: Db, user: CurrentUser):
    ensure_reservoir(db, reservoir_id, user)
    values = data.model_dump(exclude={"points"})
    points = [{"level": str(p.level), "volume": str(p.volume)} for p in data.points]
    curve = StageVolumeCurve(reservoir_id=reservoir_id, created_by_id=user.id, points=points, **values)
    db.add(curve); db.commit(); db.refresh(curve)
    return curve_view(curve)


@app.get("/reservoirs/{reservoir_id}/stage-volume-curves")
def list_curves(reservoir_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    ensure_reservoir(db, reservoir_id, user)
    rows = db.scalars(select(StageVolumeCurve).where(StageVolumeCurve.reservoir_id == reservoir_id).order_by(StageVolumeCurve.id.desc()).offset(skip).limit(limit)).all()
    return [curve_view(row) for row in rows]


@app.post("/stage-volume-curves/{curve_id}/approve")
def approve_curve(curve_id: int, data: CurveApprovalIn, db: Db, user: CurrentUser):
    curve = db.get(StageVolumeCurve, curve_id)
    if curve is None:
        raise HTTPException(status_code=404, detail="Curva não encontrada")
    reservoir = ensure_reservoir(db, curve.reservoir_id, user)
    if data.valid_from > curve.survey_date or data.valid_until < curve.survey_date:
        raise HTTPException(status_code=422, detail="A vigência aprovada deve incluir a data do levantamento")
    overlapping = db.scalars(select(StageVolumeCurve).where(
        StageVolumeCurve.reservoir_id == reservoir.id,
        StageVolumeCurve.is_approved.is_(True),
        StageVolumeCurve.id != curve.id,
        StageVolumeCurve.valid_from <= data.valid_until,
        StageVolumeCurve.valid_until >= data.valid_from,
    ).with_for_update()).all()
    if overlapping:
        raise HTTPException(status_code=409, detail="Já existe outra curva aprovada com vigência sobreposta")
    before = {"is_approved": curve.is_approved, "valid_from": curve.valid_from, "valid_until": curve.valid_until,
              "approved_by_id": curve.approved_by_id, "approved_at": curve.approved_at}
    curve.valid_from = data.valid_from
    curve.valid_until = data.valid_until
    curve.is_approved = True
    curve.approved_by_id = user.id
    curve.approved_at = datetime.now(timezone.utc)
    audit(db, user, reservoir.property_id, "stage_volume_curve", curve.id, "approve", before,
          {"is_approved": True, "valid_from": data.valid_from, "valid_until": data.valid_until,
           "approved_by_id": user.id, "approved_at": curve.approved_at})
    db.commit(); db.refresh(curve)
    return curve_view(curve)


@app.get("/stage-volume-curves/{curve_id}/volume")
def curve_volume(curve_id: int, level: Decimal, at: date, db: Db, user: CurrentUser):
    curve = db.get(StageVolumeCurve, curve_id)
    if not curve: raise HTTPException(status_code=404, detail="Curva não encontrada")
    ensure_reservoir(db, curve.reservoir_id, user)
    if not curve.is_approved:
        raise HTTPException(status_code=409, detail="Curva ainda aguarda aprovação")
    if curve.valid_from is None or curve.valid_until is None or not (curve.valid_from <= at <= curve.valid_until):
        raise HTTPException(status_code=409, detail="A curva não está aprovada para a data informada")
    try:
        volume = interpolate_volume([(Decimal(p["level"]), Decimal(p["volume"])) for p in curve.points], level)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"curve_id": curve.id, "at": at, "level": level, "level_unit": "m", "volume": volume, "volume_unit": "m3", "method": "interpolação linear dentro da vigência e sem extrapolação"}


def document_for_user(db, user, document_id):
    document = db.get(ManagedDocument, document_id)
    if not document: raise HTTPException(status_code=404, detail="Documento não encontrado")
    ensure_property(db, document.property_id, user)
    return document


def document_view(doc):
    return {"id": doc.id, "property_id": doc.property_id, "outorga_id": doc.outorga_id,
            "uploaded_by_id": doc.uploaded_by_id, "original_name": doc.original_name, "content_type": doc.content_type,
            "size_bytes": doc.size_bytes, "sha256": doc.sha256, "created_at": doc.created_at,
            "processing_status": doc.processing_status, "extracted_text": doc.extracted_text,
            "extracted_fields": doc.extracted_fields, "reviewed_fields": doc.reviewed_fields}


@app.post("/properties/{property_id}/permit-documents", status_code=201)
def upload_permit_document(property_id: int, db: Db, user: CurrentUser, file: UploadFile = File(...), outorga_id: int | None = None):
    ensure_property(db, property_id, user)
    if outorga_id is not None and ensure_outorga(db, outorga_id, user).property_id != property_id:
        raise HTTPException(status_code=422, detail="Outorga pertence a outra propriedade")
    payload = file.file.read(MAX_PDF_BYTES + 1)
    try:
        status, extracted_text, fields = inspect_pdf(payload, file.content_type, ocr_config=settings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    root = private_media_root(); root.mkdir(parents=True, exist_ok=True)
    key = f"permit-{uuid4().hex}.pdf"
    path = root / key
    try:
        with path.open("xb") as output: output.write(payload)
        doc = ManagedDocument(property_id=property_id, outorga_id=outorga_id, uploaded_by_id=user.id,
            storage_key=key, original_name=sanitize_original_filename(file.filename), content_type="application/pdf",
            size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), processing_status=status,
            extracted_text=extracted_text, extracted_fields=fields)
        db.add(doc); db.flush()
        audit(db, user, property_id, "permit_document", doc.id, "upload", {}, {"sha256": doc.sha256, "status": status})
        db.commit(); db.refresh(doc)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return document_view(doc)


@app.get("/properties/{property_id}/permit-documents")
def list_permit_documents(property_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    ensure_property(db, property_id, user)
    docs = db.scalars(select(ManagedDocument).where(ManagedDocument.property_id == property_id).order_by(ManagedDocument.id.desc()).offset(skip).limit(limit)).all()
    return [document_view(doc) for doc in docs]


@app.get("/permit-documents/{document_id}/file")
def get_permit_document_file(document_id: int, db: Db, user: CurrentUser):
    doc = document_for_user(db, user, document_id)
    if not re.fullmatch(r"permit-[0-9a-f]{32}\.pdf", doc.storage_key) or not doc.sha256:
        raise HTTPException(status_code=404, detail="Arquivo não disponível")
    root = private_media_root().resolve(); path = (root / doc.storage_key).resolve()
    if path.parent != root or not path.is_file(): raise HTTPException(status_code=404, detail="Arquivo não disponível")
    payload = path.read_bytes()
    if len(payload) != doc.size_bytes or hashlib.sha256(payload).hexdigest() != doc.sha256:
        raise HTTPException(status_code=409, detail="Integridade do arquivo não confere")
    return Response(content=payload, media_type="application/pdf", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": "attachment"})


@app.post("/permit-documents/{document_id}/review")
def review_document(document_id: int, data: DocumentReviewIn, db: Db, user: CurrentUser):
    doc = document_for_user(db, user, document_id)
    previous = {"fields": doc.reviewed_fields, "status": doc.processing_status}
    doc.reviewed_fields = data.fields
    doc.processing_status = "approved" if data.approve else "pending_review"
    audit(db, user, doc.property_id, "permit_document", doc.id, "approve" if data.approve else "review", previous,
          {"fields": data.fields, "status": doc.processing_status})
    db.commit(); db.refresh(doc)
    return document_view(doc)


@app.post("/permit-documents/{document_id}/extract")
def extract_document_field(document_id: int, data: DocumentExtractIn, db: Db, user: CurrentUser):
    doc = document_for_user(db, user, document_id)
    if not doc.extracted_text or data.exact_text not in doc.extracted_text:
        raise HTTPException(status_code=422, detail="Trecho não localizado no texto extraído do PDF")
    old_fields = dict(doc.extracted_fields or {})
    old = old_fields.get(data.field)
    new_fields = dict(old_fields)
    new_fields[data.field] = {"status": "pendente de revisão", "value": data.exact_text}
    audit(db, user, doc.property_id, "permit_document", doc.id, "extract", {"field": data.field, "value": old, "status": doc.processing_status},
          {"field": data.field, "value": new_fields[data.field], "status": "pending_review"})
    doc.extracted_fields = new_fields
    doc.processing_status = "pending_review"
    db.commit(); db.refresh(doc)
    return document_view(doc)


@app.get("/permit-documents/{document_id}/history")
def document_history(document_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    doc = document_for_user(db, user, document_id)
    return revision_rows(db, doc.property_id, "permit_document", doc.id, skip, limit)


@app.get("/properties/{property_id}/alert-evaluations")
def list_alert_evaluations(property_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    ensure_property(db, property_id, user)
    rows = db.scalars(select(AlertEvaluation).where(AlertEvaluation.property_id == property_id).order_by(AlertEvaluation.id.desc()).offset(skip).limit(limit)).all()
    return [{"id": row.id, "user_id": row.user_id, "evaluated_at": row.evaluated_at, "rules": row.rules, "evidence": row.evidence} for row in rows]


@app.get("/properties/{property_id}/water-balance/monthly")
def monthly_history(property_id: int, db: Db, user: CurrentUser, year: int = Query(ge=2000, le=2100)):
    ensure_property(db, property_id, user)
    reservoirs = db.scalars(select(Reservoir).where(Reservoir.property_id == property_id).order_by(Reservoir.id)).all()
    results = []
    zone = ZoneInfo("America/Sao_Paulo")
    for reservoir in reservoirs:
        saved = db.scalars(select(MonthlyBalance).where(MonthlyBalance.reservoir_id == reservoir.id, MonthlyBalance.year == year).order_by(MonthlyBalance.id.desc())).all()
        latest_by_month = {}
        for record in saved:
            latest_by_month.setdefault((record.month, record.calculation_mode), record)
        for month in range(1, 13):
            start = datetime(year, month, 1, tzinfo=zone)
            end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=zone)
            utc_start, utc_end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
            levels = db.scalar(select(func.count(LevelReading.id)).join(LevelStation).where(LevelStation.reservoir_id == reservoir.id, LevelReading.observed_at >= utc_start, LevelReading.observed_at <= utc_end))
            meters = db.scalar(select(func.count(HydrometerReading.id)).join(Hydrometer).where(Hydrometer.reservoir_id == reservoir.id,
                or_(and_(HydrometerReading.interval_start_at.is_not(None), HydrometerReading.interval_start_at < utc_end, HydrometerReading.observed_at > utc_start),
                    and_(HydrometerReading.interval_start_at.is_(None), HydrometerReading.observed_at >= utc_start, HydrometerReading.observed_at < utc_end))))
            rain = db.scalar(select(func.count(MeteorologicalObservation.id)).where(MeteorologicalObservation.property_id == property_id,
                MeteorologicalObservation.variable == "precipitation", MeteorologicalObservation.observed_at >= utc_start,
                MeteorologicalObservation.observed_at <= utc_end))
            automatic = _automatic_balance(db, reservoir, property_id, year, month)
            entry = {"reservoir_id": reservoir.id, "reservoir_name": reservoir.name, "year": year, "month": month,
                "period_start": start.date().isoformat(),
                "period_end": date(year, month, monthrange(year, month)[1]).isoformat(),
                "period_start_utc": utc_start.isoformat(), "period_end_utc_exclusive": utc_end.isoformat(),
                "timezone": "America/Sao_Paulo", **automatic,
                "period_complete": end.astimezone(timezone.utc) <= datetime.now(timezone.utc),
                "available_records": {"level_readings": levels, "hydrometer_readings": meters, "precipitation_observations": rain},
                "note": "O resultado automático só inclui registros revisados, intervalos contínuos e uma curva aprovada. A contagem não prova cobertura."}
            automatic_record = latest_by_month.get((month, "automatico"))
            declared_record = latest_by_month.get((month, "declarado"))
            if automatic_record:
                entry["automatic_assessment"] = {"id": automatic_record.id, "user_id": automatic_record.user_id,
                    "created_at": automatic_record.created_at, "result": automatic_record.result, "inputs": automatic_record.inputs}
            if declared_record:
                entry["declared_assessment"] = {"id": declared_record.id, "user_id": declared_record.user_id,
                    "created_at": declared_record.created_at, "result": declared_record.result, "inputs": declared_record.inputs,
                    "coverage": declared_record.result.get("coverage", "declarada pelo usuário")}
            results.append(entry)
    return {"property_id": property_id, "year": year, "history": results}


def _automatic_balance(db, reservoir, property_id, year, month):
    start, end = month_bounds_utc(year, month)
    meter_rows = db.scalars(select(Hydrometer).where(Hydrometer.reservoir_id == reservoir.id,
        Hydrometer.is_active.is_(True)).order_by(Hydrometer.id)).all()
    meters = []
    for meter in meter_rows:
        meter_links = db.scalars(select(HydrometerOutorgaLink).where(
            HydrometerOutorgaLink.hydrometer_id == meter.id).order_by(HydrometerOutorgaLink.valid_from_at)).all()
        normalized_links = [SimpleNamespace(id=link.id, outorga_id=link.outorga_id,
            valid_from_at=_stored_utc(link.valid_from_at), valid_until_at=_stored_utc(link.valid_until_at))
            for link in meter_links]
        readings = db.scalars(select(HydrometerReading).where(HydrometerReading.hydrometer_id == meter.id,
            or_(and_(HydrometerReading.interval_start_at.is_not(None), HydrometerReading.interval_start_at < end, HydrometerReading.observed_at > start),
                and_(HydrometerReading.interval_start_at.is_(None), HydrometerReading.observed_at >= start, HydrometerReading.observed_at < end)))
            .order_by(HydrometerReading.interval_start_at, HydrometerReading.observed_at, HydrometerReading.id)).all()
        if meter.kind == "entrada":
            for reading in readings:
                link, link_status = resolve_link(normalized_links,
                    _stored_utc(reading.interval_start_at), _stored_utc(reading.observed_at))
                reading.outorga_link_status = "confirmado" if link else link_status
                reading.outorga_link_id = link.id if link else None
                reading.outorga_id = link.outorga_id if link else None
        meters.append(SimpleNamespace(id=meter.id, kind=meter.kind, readings=readings))

    stations = db.scalars(select(MeteorologicalStation).where(MeteorologicalStation.property_id == property_id,
        MeteorologicalStation.source == "INMET", MeteorologicalStation.is_active.is_(True)).order_by(MeteorologicalStation.id.desc())).all()
    # A single explicitly configured station is required; never merge rain across stations.
    station = stations[0] if len(stations) == 1 else None
    rainfall_rows = []
    if station:
        rainfall_rows = db.scalars(select(MeteorologicalObservation).where(
            MeteorologicalObservation.property_id == property_id, MeteorologicalObservation.station_id == station.id,
            MeteorologicalObservation.variable == "precipitation",
            or_(and_(MeteorologicalObservation.interval_start_at.is_not(None), MeteorologicalObservation.interval_start_at < end,
                     MeteorologicalObservation.observed_at > start),
                and_(MeteorologicalObservation.interval_start_at.is_(None), MeteorologicalObservation.observed_at >= start,
                     MeteorologicalObservation.observed_at < end)))
            .order_by(MeteorologicalObservation.interval_start_at, MeteorologicalObservation.observed_at,
                      MeteorologicalObservation.id)).all()
    level_station = db.scalar(select(LevelStation).where(LevelStation.reservoir_id == reservoir.id))
    level_rows = []
    if level_station:
        level_rows = db.scalars(select(LevelReading).where(LevelReading.station_id == level_station.id,
            LevelReading.observed_at >= start, LevelReading.observed_at <= end)
            .order_by(LevelReading.observed_at, LevelReading.id)).all()
    curves = db.scalars(select(StageVolumeCurve).where(StageVolumeCurve.reservoir_id == reservoir.id,
        StageVolumeCurve.is_approved.is_(True)).order_by(StageVolumeCurve.id)).all()
    other_outflows = db.scalars(select(BalanceFlowEvidence).where(BalanceFlowEvidence.reservoir_id == reservoir.id,
        BalanceFlowEvidence.period_start_at < end, BalanceFlowEvidence.period_end_at > start)
        .order_by(BalanceFlowEvidence.period_start_at, BalanceFlowEvidence.period_end_at, BalanceFlowEvidence.id)).all()
    result = assess_automatic_month(year=year, month=month, now=datetime.now(timezone.utc),
        rainfall_rows=rainfall_rows, inlet_meters=[m for m in meters if m.kind == "entrada"],
        outlet_meters=[m for m in meters if m.kind == "saída"], level_readings=level_rows,
        curves=curves, other_outflow_rows=other_outflows)
    if len(stations) > 1:
        result["missing"].append("seleção de uma única estação pluviométrica para o período")
        result["status"] = "dados insuficientes"
        result["coverage"] = "incompleta"
    return result


def _stored_utc(value):
    """Normalize a DB timestamp; SQLite drops tzinfo although values are UTC."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@app.post("/reservoirs/{reservoir_id}/water-balance/monthly", status_code=201)
def record_monthly_balance(reservoir_id: int, data: BalanceMonthIn, db: Db, user: CurrentUser):
    ensure_reservoir(db, reservoir_id, user)
    result = assess_month(data.year, data.month, data.inputs)
    result["calculation_mode"] = "declarado"
    row = MonthlyBalance(reservoir_id=reservoir_id, user_id=user.id, year=data.year, month=data.month,
        inputs=data.model_dump(mode="json")["inputs"], result=jsonable_encoder(result, custom_encoder={Decimal: str}),
        calculation_mode="declarado")
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "reservoir_id": reservoir_id, "user_id": row.user_id, "created_at": row.created_at,
            "inputs": row.inputs, **row.result}


@app.post("/reservoirs/{reservoir_id}/water-balance/monthly/automatic", status_code=201)
def calculate_automatic_balance(reservoir_id: int, db: Db, user: CurrentUser,
                                year: int = Query(ge=2000, le=2100), month: int = Query(ge=1, le=12)):
    reservoir = ensure_reservoir(db, reservoir_id, user)
    result = _automatic_balance(db, reservoir, reservoir.property_id, year, month)
    row = MonthlyBalance(reservoir_id=reservoir.id, user_id=user.id, year=year, month=month,
        inputs=jsonable_encoder(result.get("data_sources", {})),
        result=jsonable_encoder(result, custom_encoder={Decimal: str}), calculation_mode="automatico")
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "reservoir_id": reservoir.id, "user_id": row.user_id,
            "created_at": row.created_at, "calculation_mode": row.calculation_mode, **row.result}


@app.get("/reservoirs/{reservoir_id}/water-balance/assessments")
def balance_assessments(reservoir_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    ensure_reservoir(db, reservoir_id, user)
    rows = db.scalars(select(MonthlyBalance).where(MonthlyBalance.reservoir_id == reservoir_id).order_by(MonthlyBalance.id.desc()).offset(skip).limit(limit)).all()
    return [{"id": row.id, "year": row.year, "month": row.month, "user_id": row.user_id, "inputs": row.inputs,
             "result": row.result, "created_at": row.created_at} for row in rows]


def telemetry_view(row):
    return {"id": row.id, "property_id": row.property_id, "component_type": row.component_type,
            "component_id": row.component_id, "variable": row.variable, "value": row.value, "unit": row.unit,
            "observed_at": row.observed_at, "collected_at": row.collected_at, "registered_at": row.registered_at,
            "source": row.source, "origin_id": row.origin_id, "out_of_order": row.out_of_order,
            "user_id": row.user_id, "status": "bruto; não aplicado a cálculos"}


@app.post("/telemetry/normalized", status_code=201)
def save_normalized_reading(data: NormalizedReading, db: Db, user: CurrentUser, response: Response):
    ensure_property(db, data.property_id, user)
    if data.source == "equipment":
        raise HTTPException(status_code=403, detail="Recepção de equipamento não habilitada; protocolo e autenticação não foram confirmados")
    if data.collected_at < data.observed_at:
        raise HTTPException(status_code=422, detail="Coleta não pode anteceder a observação")
    if data.component_type == "hydrometer":
        meter, reservoir = meter_for_user(db, user, data.component_id)
        if not meter.is_active: raise HTTPException(status_code=409, detail="Hidrômetro inativo")
    else:
        station = db.get(LevelStation, data.component_id)
        if not station: raise HTTPException(status_code=404, detail="Estação não encontrada")
        reservoir = ensure_reservoir(db, station.reservoir_id, user)
    if reservoir.property_id != data.property_id:
        raise HTTPException(status_code=404, detail="Componente não pertence à propriedade")
    filters = (NormalizedTelemetry.property_id == data.property_id, NormalizedTelemetry.component_type == data.component_type,
               NormalizedTelemetry.component_id == data.component_id, NormalizedTelemetry.source == data.source,
               NormalizedTelemetry.origin_id == data.origin_id)
    old = db.scalar(select(NormalizedTelemetry).where(*filters))
    def utc(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if old:
        if (old.variable, old.value, old.unit, utc(old.observed_at), utc(old.collected_at)) != (data.variable, data.value, data.unit, utc(data.observed_at), utc(data.collected_at)):
            raise HTTPException(status_code=409, detail="Identificador de origem já usado por outro conteúdo")
        response.status_code = 200
        return telemetry_view(old)
    latest = db.scalar(select(NormalizedTelemetry.observed_at).where(NormalizedTelemetry.property_id == data.property_id,
        NormalizedTelemetry.component_type == data.component_type, NormalizedTelemetry.component_id == data.component_id)
        .order_by(NormalizedTelemetry.observed_at.desc()).limit(1))
    row = NormalizedTelemetry(**(data.model_dump() | {"observed_at": utc(data.observed_at), "collected_at": utc(data.collected_at)}),
        user_id=user.id, out_of_order=bool(latest and utc(data.observed_at) < utc(latest)))
    db.add(row)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        old = db.scalar(select(NormalizedTelemetry).where(*filters))
        if old and (old.variable, old.value, old.unit, utc(old.observed_at), utc(old.collected_at)) == (data.variable, data.value, data.unit, utc(data.observed_at), utc(data.collected_at)):
            response.status_code = 200
            return telemetry_view(old)
        raise HTTPException(status_code=409, detail="Identificador de origem já registrado")
    db.refresh(row)
    return telemetry_view(row)


@app.get("/properties/{property_id}/telemetry/normalized")
def list_normalized_readings(property_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    ensure_property(db, property_id, user)
    rows = db.scalars(select(NormalizedTelemetry).where(NormalizedTelemetry.property_id == property_id).order_by(NormalizedTelemetry.id.desc()).offset(skip).limit(limit)).all()
    return [telemetry_view(row) for row in rows]

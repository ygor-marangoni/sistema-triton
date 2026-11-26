from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

OPERATIONAL_TZ = ZoneInfo("America/Sao_Paulo")


def reservoir_volume(base_width: Decimal, base_length: Decimal, top_width: Decimal, top_length: Decimal, height: Decimal, level: Decimal) -> Decimal:
    """Volume for a rectangular frustum with planar sides; no irregular geometry inference."""
    values = [Decimal(v) for v in (base_width, base_length, top_width, top_length, height, level)]
    bw, bl, tw, tl, h, z = values
    if min(bw, bl, tw, tl, h) <= 0 or tw < bw or tl < bl or z < 0 or z > h:
        raise ValueError("Dimensões ou nível incompatíveis com o modelo geométrico")
    dw, dl = tw - bw, tl - bl
    return bw * bl * z + (bw * dl + bl * dw) * z**2 / (2 * h) + dw * dl * z**3 / (3 * h**2)


def compare_month(outorga, demand, readings, year: int, month: int) -> dict:
    """Compare explicitly bounded meter intervals without inventing daily allocation.

    A known interval may contribute to the month total only when the complete
    interval is inside the month. Daily quota comparisons accept only intervals
    whose start and end fall on the same operational date. Cross-midnight and
    legacy readings without a start remain visible as unassigned evidence.
    """
    if month < 1 or month > 12:
        raise ValueError("Mês inválido")
    daily_quota = Decimal(demand.max_flow_m3_h) * Decimal(demand.daily_hours)
    days_authorized = int(demand.authorized_days)
    period_start = datetime(year, month, 1, tzinfo=OPERATIONAL_TZ)
    next_month = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=OPERATIONAL_TZ)
    period_start_utc = period_start.astimezone(timezone.utc)
    period_end_utc = next_month.astimezone(timezone.utc)
    by_day: dict[date, Decimal] = {}
    pending = duplicate_readings = unassigned_intervals = out_of_order = delayed = 0
    monthly_volume = Decimal(0)
    monthly_count = 0
    accepted = []
    review_items = []
    seen = set()
    previous_order = None
    def needs_review(reading, reason, start=None, observed=None):
        review_items.append({
            "reading_id": getattr(reading, "id", None),
            "external_id": getattr(reading, "external_id", None),
            "interval_start_at": start or getattr(reading, "interval_start_at", None),
            "observed_at": observed or getattr(reading, "observed_at", None),
            "reason": reason,
        })
    for reading in readings:
        observed = getattr(reading, "observed_at", None)
        if observed is None or observed.tzinfo is None or observed.utcoffset() is None:
            pending += 1
            needs_review(reading, "horário observado ausente ou sem fuso")
            continue
        observed_utc = observed.astimezone(timezone.utc)
        order_key = (observed_utc, getattr(reading, "id", 0) or 0)
        if previous_order is not None and order_key < previous_order:
            out_of_order += 1
        previous_order = order_key
        created = getattr(reading, "created_at", None)
        if created is not None and created.tzinfo is not None and created.astimezone(timezone.utc) > observed_utc:
            delayed += 1

        start = getattr(reading, "interval_start_at", None)
        if start is None or start.tzinfo is None or start.utcoffset() is None or start.astimezone(timezone.utc) >= observed_utc:
            if period_start_utc <= observed_utc < period_end_utc:
                pending += 1
                unassigned_intervals += 1
                needs_review(reading, "início do intervalo ausente ou inválido", observed=observed_utc)
            continue
        start_utc = start.astimezone(timezone.utc)
        # Readings from other months are not relevant to this comparison.
        if observed_utc <= period_start_utc or start_utc >= period_end_utc:
            continue
        if start_utc < period_start_utc or observed_utc > period_end_utc:
            pending += 1
            unassigned_intervals += 1
            needs_review(reading, "intervalo atravessa o limite do mês", start_utc, observed_utc)
            continue

        external_id = getattr(reading, "external_id", None)
        meter_key = getattr(reading, "hydrometer_id", None)
        identity = ("external", meter_key, external_id) if external_id else (
            ("id", getattr(reading, "id")) if getattr(reading, "id", None) is not None
            else ("interval", start_utc, observed_utc)
        )
        if identity in seen:
            duplicate_readings += 1
            pending += 1
            needs_review(reading, "identificador de leitura duplicado", start_utc, observed_utc)
            continue
        seen.add(identity)
        if (getattr(reading, "unit", "m³") or "").strip().lower() not in {"m3", "m³"}:
            pending += 1
            needs_review(reading, "unidade incompatível", start_utc, observed_utc)
            continue
        value = getattr(reading, "volume_m3", None)
        quality = str(getattr(reading, "quality", "")).strip().lower()
        if value is None or value < 0 or getattr(reading, "source", "") == "simulada" or quality.startswith(("pendente", "inconsistente", "inconclusiva", "linha de base", "não revisada", "simulada")):
            pending += 1
            needs_review(reading, "valor ausente, simulado ou pendente de revisão", start_utc, observed_utc)
            continue
        if hasattr(reading, "outorga_link_status") and reading.outorga_link_status != "confirmado":
            pending += 1
            needs_review(reading, "vínculo histórico de outorga não comprovado", start_utc, observed_utc)
            continue
        if hasattr(reading, "resolved_outorga_id") and reading.resolved_outorga_id != getattr(outorga, "id", None):
            pending += 1
            needs_review(reading, "leitura associada a outra outorga", start_utc, observed_utc)
            continue
        start_day = start.astimezone(OPERATIONAL_TZ).date()
        last_instant = observed_utc - timedelta(microseconds=1)
        end_day = last_instant.astimezone(OPERATIONAL_TZ).date()
        if not (outorga.valid_from <= start_day <= outorga.valid_until and outorga.valid_from <= end_day <= outorga.valid_until):
            pending += 1
            needs_review(reading, "intervalo fora da vigência legal da outorga", start_utc, observed_utc)
            continue
        accepted.append((start_utc, observed_utc, Decimal(value), reading, start_day, end_day))

    # Chronological sorting makes delayed imports deterministic. Overlapping
    # intervals are retained as evidence but cannot be summed twice.
    last_end_by_meter = {}
    eligible_intervals = []
    for start_utc, observed_utc, value, reading, start_day, end_day in sorted(accepted, key=lambda row: (row[0], row[1], getattr(row[3], "id", 0) or 0)):
        meter_key = getattr(reading, "hydrometer_id", None)
        last_end = last_end_by_meter.get(meter_key)
        if last_end is not None and start_utc < last_end:
            pending += 1
            unassigned_intervals += 1
            needs_review(reading, "intervalo sobreposto a outra leitura", start_utc, observed_utc)
            continue
        last_end_by_meter[meter_key] = observed_utc
        monthly_volume += value
        monthly_count += 1
        if start_day == end_day:
            by_day[start_day] = by_day.get(start_day, Decimal(0)) + value
            daily_assignment = start_day.isoformat()
        else:
            pending += 1
            unassigned_intervals += 1
            daily_assignment = None
            needs_review(reading, "intervalo cruza dias operacionais; não foi distribuído", start_utc, observed_utc)
        eligible_intervals.append({
            "reading_id": getattr(reading, "id", None),
            "external_id": getattr(reading, "external_id", None),
            "interval_start_at": start_utc,
            "observed_at": observed_utc,
            "volume_m3": value,
            "flow_m3_h": getattr(reading, "flow_m3_h", None),
            "hydrometer_id": getattr(reading, "hydrometer_id", None),
            "unit": getattr(reading, "unit", "m³"),
            "source": getattr(reading, "source", None),
            "quality": getattr(reading, "quality", None),
            "outorga_link_id": getattr(reading, "outorga_link_id", None),
            "resolved_outorga_id": getattr(reading, "resolved_outorga_id", None),
            "daily_assignment": daily_assignment,
        })
    allowed_days_used = 0
    inside = Decimal(0)
    surplus = Decimal(0)
    over = Decimal(0)
    daily = []
    for day, volume in sorted(by_day.items()):
        if volume > 0:
            allowed_days_used += 1
        if volume > 0 and allowed_days_used > days_authorized:
            day_inside, day_surplus, day_over = Decimal(0), Decimal(0), volume
            status = "dia de operação excedente"
        else:
            day_inside = min(volume, daily_quota)
            day_surplus = max(daily_quota - volume, Decimal(0)) if days_authorized else Decimal(0)
            day_over = max(volume - daily_quota, Decimal(0))
            status = "extrapolado" if day_over else ("dentro do limite diário" if volume else "sem captação")
        inside += day_inside
        surplus += day_surplus
        over += day_over
        daily.append({"date": day.isoformat(), "volume_m3": volume, "inside_limit_m3": day_inside, "non_transferable_surplus_m3": day_surplus, "extrapolated_m3": day_over, "status": status})
    days_in_month = monthrange(year, month)[1]
    return {
        "year": year, "month": month, "measured_volume_m3": monthly_volume if monthly_count else None,
        "inside_limit_m3": inside, "non_transferable_surplus_m3": surplus, "extrapolated_m3": over,
        "operating_days_used": allowed_days_used, "operating_days_authorized": days_authorized,
        "monthly_reference_limit_m3": Decimal(demand.monthly_volume_m3),
        "daily_reference_limit_m3": daily_quota, "missing_days": days_in_month - len(by_day),
        "pending_readings": pending, "duplicate_readings": duplicate_readings,
        "out_of_order_readings": out_of_order, "delayed_readings": delayed,
        "unassigned_intervals": unassigned_intervals,
        "eligible_intervals": eligible_intervals,
        "review_items": review_items,
        "status": "dados insuficientes" if monthly_count == 0 else "parcial; intervalos não comprovam cobertura mensal",
        "coverage": "incompleto", "daily": daily,
        "notes": "Intervalos entre dias não são distribuídos por dia. Leituras ausentes, sem início ou duplicadas não viram zero; sobras diárias não são transferidas.",
    }


def energy_estimate(hydrometers, readings, tariff: Decimal | None) -> dict:
    total_kwh = Decimal(0)
    rows = []
    for meter in hydrometers:
        if meter.rated_power_kw is None:
            rows.append({"hydrometer_id": meter.id, "name": meter.name, "status": "potência elétrica de entrada em kW não cadastrada", "kwh": None, "hours": None, "reading_count": 0})
            continue
        meter_readings = readings.get(meter.id, [])
        if not meter_readings or any(r.volume_m3 is None or getattr(r, "quality", "").startswith(("pendente", "inconsistente", "inconclusiva", "linha de base")) or r.flow_m3_h is None or Decimal(r.flow_m3_h) <= 0 or Decimal(r.volume_m3) <= 0 for r in meter_readings):
            rows.append({"hydrometer_id": meter.id, "name": meter.name, "status": "dados insuficientes: leituras positivas com vazão média são necessárias para inferir horas", "kwh": None, "hours": None, "reading_count": len(meter_readings)})
            continue
        hrs = Decimal(0)
        volume = Decimal(0)
        for reading in meter_readings:
            hrs += Decimal(reading.volume_m3) / Decimal(reading.flow_m3_h)
            volume += Decimal(reading.volume_m3)
        kwh = Decimal(meter.rated_power_kw) * hrs
        total_kwh += kwh
        rows.append({"hydrometer_id": meter.id, "name": meter.name, "status": "estimativa; tempo inferido como volume ÷ vazão média", "hours": hrs, "volume_m3": volume, "kwh": kwh, "power_kw": meter.rated_power_kw, "reading_count": len(meter_readings)})
    complete_rows = bool(rows) and all(r["kwh"] is not None for r in rows)
    return {"energy_kwh": total_kwh if complete_rows else None, "tariff_brl_kwh": tariff, "estimated_cost_brl": total_kwh * tariff if tariff is not None and complete_rows else None, "status": "estimativa" if tariff is not None and complete_rows else "dados insuficientes", "coverage": "incompleta; leituras existentes não comprovam todas as horas de operação", "premises": "Potência elétrica nominal × horas estimadas (volume ÷ vazão média). Sem rendimento ou fator de carga aplicados; informe apenas bombas elétricas de entrada e confira a cobertura do período.", "pumps": rows}


def water_balance(**data) -> dict:
    required = ("area_m2", "duration_days", "rain_mm", "inflow_m3", "outflow_m3", "other_outflow_m3", "initial_volume_m3", "final_volume_m3")
    missing = [key for key in required if data.get(key) is None]
    if missing:
        return {"status": "dados insuficientes", "loss_residual_m3": None, "loss_residual_mm_day": None, "missing": missing, "interpretation": "Perda residual estimada pelo balanço hídrico não calculada."}
    try:
        values = {key: Decimal(data[key]) for key in required}
        if any(not value.is_finite() or value < 0 for value in values.values()):
            raise ValueError("Valores negativos ou não finitos")
    except (ValueError, TypeError, ArithmeticError):
        return {"status": "inconsistente", "loss_residual_m3": None, "loss_residual_mm_day": None, "missing": [], "interpretation": "As entradas devem ser números finitos e não negativos."}
    area, duration = values["area_m2"], values["duration_days"]
    if area <= 0 or duration <= 0:
        return {"status": "inconsistente", "loss_residual_m3": None, "loss_residual_mm_day": None, "missing": [], "interpretation": "Área e duração devem ser positivas."}
    residual = Decimal(data["inflow_m3"]) + Decimal(data["rain_mm"]) / 1000 * area - Decimal(data["outflow_m3"]) - Decimal(data["other_outflow_m3"]) - (Decimal(data["final_volume_m3"]) - Decimal(data["initial_volume_m3"]))
    if residual < 0:
        return {"status": "inconsistente", "loss_residual_m3": residual, "loss_residual_mm_day": None, "missing": [], "interpretation": "Residual negativo; revise fluxos, nível-volume e intervalos."}
    return {"status": "perda residual estimada pelo balanço hídrico", "loss_residual_m3": residual, "loss_residual_mm_day": 1000 * residual / (area * duration), "missing": [], "interpretation": "Não equivale a evaporação sem identificar as demais entradas e saídas relevantes."}

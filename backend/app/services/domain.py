from calendar import monthrange
from datetime import date, datetime, timezone
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
    """Compare each operating day with its own quota; no daily surplus rollover."""
    if month < 1 or month > 12:
        raise ValueError("Mês inválido")
    daily_quota = Decimal(demand.max_flow_m3_h) * Decimal(demand.daily_hours)
    days_authorized = int(demand.authorized_days)
    by_day: dict[date, Decimal] = {}
    eligible = 0
    pending = 0
    for reading in readings:
        observed = reading.observed_at
        if observed.tzinfo is None or observed.utcoffset() is None:
            pending += 1
            continue
        local_day = observed.astimezone(OPERATIONAL_TZ).date()
        if local_day.year != year or local_day.month != month:
            continue
        if reading.volume_m3 is None or getattr(reading, "quality", "").startswith(("pendente", "inconsistente", "inconclusiva", "linha de base")):
            pending += 1
            continue
        if not (outorga.valid_from <= local_day <= outorga.valid_until):
            pending += 1
            continue
        by_day[local_day] = by_day.get(local_day, Decimal(0)) + Decimal(reading.volume_m3)
        eligible += 1
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
        "year": year, "month": month, "measured_volume_m3": sum(by_day.values(), Decimal(0)),
        "inside_limit_m3": inside, "non_transferable_surplus_m3": surplus, "extrapolated_m3": over,
        "operating_days_used": allowed_days_used, "operating_days_authorized": days_authorized,
        "monthly_reference_limit_m3": Decimal(demand.monthly_volume_m3),
        "daily_reference_limit_m3": daily_quota, "missing_days": days_in_month - len(by_day),
        "pending_readings": pending, "coverage": "incompleto", "daily": daily,
        "notes": "Leituras registradas não comprovam cobertura contínua; sobras diárias não são transferidas.",
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
    area, duration = Decimal(data["area_m2"]), Decimal(data["duration_days"])
    if area <= 0 or duration <= 0:
        return {"status": "inconsistente", "loss_residual_m3": None, "loss_residual_mm_day": None, "missing": [], "interpretation": "Área e duração devem ser positivas."}
    residual = Decimal(data["inflow_m3"]) + Decimal(data["rain_mm"]) / 1000 * area - Decimal(data["outflow_m3"]) - Decimal(data["other_outflow_m3"]) - (Decimal(data["final_volume_m3"]) - Decimal(data["initial_volume_m3"]))
    if residual < 0:
        return {"status": "inconsistente", "loss_residual_m3": residual, "loss_residual_mm_day": None, "missing": [], "interpretation": "Residual negativo; revise fluxos, nível-volume e intervalos."}
    return {"status": "perda residual estimada pelo balanço hídrico", "loss_residual_m3": residual, "loss_residual_mm_day": 1000 * residual / (area * duration), "missing": [], "interpretation": "Não equivale a evaporação sem identificar as demais entradas e saídas relevantes."}

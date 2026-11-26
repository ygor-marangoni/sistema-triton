"""Automatic monthly residual assembly from complete, reviewed source intervals."""
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from app.services.domain import water_balance
from app.services.stage_volume import interpolate_volume

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
APPROVED_QUALITIES = {"validada", "revisada", "confirmed", "confirmada", "approved"}


def month_bounds_utc(year, month):
    if month < 1 or month > 12:
        raise ValueError("Mês inválido")
    start_local = datetime(year, month, 1, tzinfo=LOCAL_TZ)
    end_local = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=LOCAL_TZ)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _utc(value):
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _get(row, name, default=None):
    return row.get(name, default) if isinstance(row, dict) else getattr(row, name, default)


def _provenance(row, start, end, value, unit):
    record = {
        "id": _get(row, "id"),
        "source": _get(row, "source"),
        "quality": _get(row, "quality"),
        "value": str(value),
        "unit": unit,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "observed_at": (_get(row, "observed_at") or end).isoformat(),
        "reference": _get(row, "reference"),
    }
    for key in ("outorga_id", "outorga_link_id", "hydrometer_id", "kind"):
        if _get(row, key) is not None:
            record[key] = _get(row, key)
    return record


def _sum_full_coverage(rows, start, end, *, start_key, end_key, value_key, unit_key,
                       unit, require_review=True, require_outorga_link=False):
    relevant = []
    issues = []
    for row in rows:
        row_start = _utc(_get(row, start_key))
        row_end = _utc(_get(row, end_key))
        if row_start is None or row_end is None:
            if row_end and start <= row_end < end:
                issues.append("intervalo sem início confiável")
            continue
        if row_end <= start or row_start >= end:
            continue
        relevant.append((row_start, row_end, row))

    relevant.sort(key=lambda item: (item[0], item[1], _get(item[2], "id") or 0))
    cursor = start
    total = Decimal(0)
    sources = []
    seen = set()
    for row_start, row_end, row in relevant:
        row_id = _get(row, "id")
        key = ("id", row_id) if row_id is not None else (row_start, row_end)
        if key in seen:
            issues.append("registro duplicado")
            continue
        seen.add(key)
        if row_start != cursor:
            issues.append("lacuna ou sobreposição entre intervalos")
            if row_start < cursor:
                continue
        if row_start < start or row_end > end or row_end <= row_start:
            issues.append("intervalo fora dos limites do mês")
            continue
        if str(_get(row, unit_key, "")).strip().lower() != unit:
            issues.append("unidade incompatível")
            continue
        source = str(_get(row, "source", "")).casefold()
        if source == "simulada":
            issues.append("dados simulados não comprovam cobertura operacional")
            continue
        if require_review and str(_get(row, "quality", "")).casefold() not in APPROVED_QUALITIES:
            issues.append("registro pendente de revisão")
            continue
        if require_outorga_link and _get(row, "outorga_link_status") != "confirmado":
            issues.append("hidrômetro de entrada sem vínculo histórico comprovado para o intervalo")
            continue
        value = _get(row, value_key)
        try:
            value = Decimal(value)
            if not value.is_finite() or value < 0:
                raise InvalidOperation
        except (InvalidOperation, TypeError, ValueError):
            issues.append("valor ausente ou inválido")
            continue
        total += value
        sources.append(_provenance(row, row_start, row_end, value, unit))
        cursor = row_end
    if cursor != end:
        issues.append("cobertura incompleta até o fim do mês")
    complete = not issues and cursor == end and bool(sources)
    return (total if complete else None), sources, list(dict.fromkeys(issues))


def _curve_for_month(curves, year, month):
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    matches = [curve for curve in curves
               if _get(curve, "is_approved", False)
               and _get(curve, "valid_from") is not None
               and _get(curve, "valid_until") is not None
               and _get(curve, "valid_from") <= start_date
               and _get(curve, "valid_until") >= end_date]
    return matches[0] if len(matches) == 1 else None, len(matches)


def _one_boundary_reading(readings, expected_at):
    matches = [r for r in readings if _utc(_get(r, "observed_at")) == expected_at]
    good = [r for r in matches
            if str(_get(r, "quality", "")).casefold() in APPROVED_QUALITIES
            or str(_get(r, "quality", "")).casefold().startswith(("revisada", "validada", "confirmed", "confirmada", "approved"))]
    good = [r for r in good if str(_get(r, "source", "")).casefold() != "simulada"]
    return good[0] if len(good) == 1 and len(matches) == 1 else None


def _area_between_curve_levels(curve, start_level, end_level):
    if start_level == end_level:
        return None
    points = [(Decimal(p["level"]), Decimal(p["volume"])) for p in curve.points]
    initial = interpolate_volume(points, start_level)
    final = interpolate_volume(points, end_level)
    area = (final - initial) / (end_level - start_level)
    return area if area > 0 else None


def assess_automatic_month(*, year, month, now, rainfall_rows, inlet_meters, outlet_meters,
                           level_readings, curves, other_outflow_rows):
    """Return a proven result only when every required monthly interval is reviewed.

    This function does not use a meter's current outorga pointer, synthesize zeros,
    fill gaps, or distribute volumes between days.
    """
    start, end = month_bounds_utc(year, month)
    now_utc = _utc(now) or datetime.now(timezone.utc)
    missing, problems, source_records = [], [], {}
    period_days = Decimal(str((end - start).total_seconds())) / Decimal(86400)
    if end > now_utc:
        missing.append("período mensal ainda não encerrado")

    rain, rain_sources, rain_issues = _sum_full_coverage(
        rainfall_rows, start, end, start_key="interval_start_at", end_key="observed_at",
        value_key="value", unit_key="unit", unit="mm")
    if rain is None:
        missing.append("precipitação com intervalos revisados cobrindo o mês")
        problems.extend(f"precipitação: {issue}" for issue in rain_issues)
    else:
        source_records["rain_mm"] = rain_sources

    def meter_total(meters, kind, label, result_key):
        if not meters:
            missing.append(f"hidrômetro(s) de {label} ativo(s) cadastrado(s)")
            return None
        aggregate = Decimal(0)
        records = []
        complete = True
        for meter in meters:
            value, rows, issues = _sum_full_coverage(
                _get(meter, "readings", []), start, end,
                start_key="interval_start_at", end_key="observed_at",
                value_key="volume_m3", unit_key="unit", unit="m³",
                require_outorga_link=(kind == "entrada"))
            if value is None:
                complete = False
                problems.extend(f"hidrômetro {_get(meter, 'id')}: {issue}" for issue in issues)
            else:
                aggregate += value
                records.extend({**row, "hydrometer_id": _get(meter, "id"), "kind": kind} for row in rows)
        if not complete:
            missing.append(f"cobertura completa de hidrômetro(s) de {label}")
            return None
        source_records[result_key] = records
        return aggregate

    inflow = meter_total(inlet_meters, "entrada", "entrada", "inflow_m3")
    outflow = meter_total(outlet_meters, "saída", "saída", "outflow_m3")

    other_outflow, other_sources, other_issues = _sum_full_coverage(
        other_outflow_rows, start, end, start_key="period_start_at", end_key="period_end_at",
        value_key="value_m3", unit_key="unit", unit="m3")
    if other_outflow is None:
        missing.append("outras saídas quantificadas e revisadas cobrindo o mês")
        problems.extend(f"outras saídas: {issue}" for issue in other_issues)
    else:
        source_records["other_outflow_m3"] = other_sources

    curve, curve_count = _curve_for_month(curves, year, month)
    if curve is None:
        missing.append("uma única curva cota-volume aprovada e vigente durante todo o mês")
        if curve_count > 1:
            problems.append("mais de uma curva aprovada cobre o período")
    expected_end = end
    initial_level_reading = _one_boundary_reading(level_readings, start)
    final_level_reading = _one_boundary_reading(level_readings, expected_end)
    if initial_level_reading is None:
        missing.append("leitura de nível revisada no início exato do mês")
    if final_level_reading is None:
        missing.append("leitura de nível revisada no fim exato do mês")

    initial_volume = final_volume = area = None
    if curve is not None and initial_level_reading is not None and final_level_reading is not None:
        try:
            points = [(Decimal(p["level"]), Decimal(p["volume"])) for p in curve.points]
            initial_level = Decimal(initial_level_reading.level_m)
            final_level = Decimal(final_level_reading.level_m)
            initial_volume = interpolate_volume(points, initial_level)
            final_volume = interpolate_volume(points, final_level)
            area = _area_between_curve_levels(curve, initial_level, final_level)
            if area is None:
                missing.append("área superficial média não derivável sem variação de nível")
            source_records["initial_volume_m3"] = [{"id": initial_level_reading.id, "level_reading_id": initial_level_reading.id,
                "level_m": str(initial_level), "level_unit": "m", "volume_m3": str(initial_volume), "volume_unit": "m3",
                "source": initial_level_reading.source, "quality": initial_level_reading.quality,
                "image_review_id": _get(initial_level_reading, "image_review_id"),
                "observed_at": _get(initial_level_reading, "observed_at").isoformat(), "curve_id": curve.id}]
            source_records["final_volume_m3"] = [{"id": final_level_reading.id, "level_reading_id": final_level_reading.id,
                "level_m": str(final_level), "level_unit": "m", "volume_m3": str(final_volume), "volume_unit": "m3",
                "source": final_level_reading.source, "quality": final_level_reading.quality,
                "image_review_id": _get(final_level_reading, "image_review_id"),
                "observed_at": _get(final_level_reading, "observed_at").isoformat(), "curve_id": curve.id}]
            if area is not None:
                source_records["area_m2"] = [{"curve_id": curve.id, "curve_survey_date": curve.survey_date.isoformat(),
                    "level_start_m": str(initial_level), "level_end_m": str(final_level), "value": str(area), "unit": "m2",
                    "method": "variação média do volume interpolado dividida pela variação de nível"}]
            if curve.valid_from > date(year, month, 1) or curve.valid_until < date(year, month, monthrange(year, month)[1]):
                missing.append("curva cota-volume vigente em todo o intervalo")
        except (ValueError, InvalidOperation, KeyError, TypeError) as exc:
            problems.append(f"curva/nível incompatível: {exc}")

    inputs = {"area_m2": area, "duration_days": period_days, "rain_mm": rain,
              "inflow_m3": inflow, "outflow_m3": outflow, "other_outflow_m3": other_outflow,
              "initial_volume_m3": initial_volume, "final_volume_m3": final_volume}
    result = {
        "year": year, "month": month, "period_start": start.astimezone(LOCAL_TZ).date().isoformat(),
        "period_end": (end - timedelta(microseconds=1)).astimezone(LOCAL_TZ).date().isoformat(),
        "period_start_utc": start.isoformat(), "period_end_utc_exclusive": end.isoformat(),
        "timezone": "America/Sao_Paulo", "calculation_mode": "automatico",
        "status": "dados insuficientes", "coverage": "incompleta",
        "loss_residual_m3": None, "loss_residual_mm_day": None,
        "missing": list(dict.fromkeys(missing)), "problems": list(dict.fromkeys(problems)),
        "inputs": {key: None if value is None else str(value) for key, value in inputs.items()},
        "data_sources": source_records, "curve_id": curve.id if curve else None,
        "interpretation": "Perda residual estimada pelo balanço hídrico; não é evaporação medida.",
    }
    if curve is not None:
        result["data_sources"]["curve"] = [{"id": curve.id, "survey_date": curve.survey_date.isoformat(),
            "survey_source": curve.survey_source, "survey_responsible": curve.survey_responsible,
            "created_by_id": curve.created_by_id, "approved_by_id": curve.approved_by_id,
            "approved_at": curve.approved_at.isoformat() if curve.approved_at else None,
            "valid_from": curve.valid_from.isoformat() if curve.valid_from else None,
            "valid_until": curve.valid_until.isoformat() if curve.valid_until else None,
            "level_unit": curve.level_unit, "volume_unit": curve.volume_unit}]
    if result["missing"] or result["problems"]:
        if result["problems"] and not result["missing"]:
            result["status"] = "inconsistente"
        return result
    calculated = water_balance(**inputs)
    result.update(calculated)
    result["coverage"] = "comprovada" if calculated["status"] == "perda residual estimada pelo balanço hídrico" else "inconsistente"
    result["origin"] = "medida"
    result["curve_id"] = curve.id
    return result

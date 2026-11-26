"""Validate an explicitly documented monthly input set before computing a residual."""
from calendar import monthrange
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.services.domain import water_balance

UNITS = {"area_m2": "m2", "rain_mm": "mm", "inflow_m3": "m3", "outflow_m3": "m3",
         "other_outflow_m3": "m3", "initial_volume_m3": "m3", "final_volume_m3": "m3"}


def assess_month(year, month, inputs, now=None):
    tz = ZoneInfo("America/Sao_Paulo")
    start = datetime(year, month, 1, tzinfo=tz).astimezone(timezone.utc)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=tz).astimezone(timezone.utc)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    missing = [key for key in UNITS if key not in inputs]
    problems = []
    if set(inputs) - set(UNITS): problems.append("variáveis desconhecidas")
    sources = {datum.source for datum in inputs.values()}
    if "simulada" in sources and len(sources) > 1: problems.append("dados simulados não podem ser misturados com outras origens")
    for key, datum in inputs.items():
        if key not in UNITS: continue
        if datum.unit != UNITS[key]: problems.append(f"unidade incompatível: {key}")
        if datum.period_start.astimezone(timezone.utc) != start or datum.period_end.astimezone(timezone.utc) != end:
            problems.append(f"intervalo incompatível: {key}")
        if not datum.coverage_complete: missing.append(f"cobertura incompleta: {key}")
        if key in ("initial_volume_m3", "final_volume_m3"):
            expected = start if key == "initial_volume_m3" else end
            if datum.observed_at is None or datum.observed_at.astimezone(timezone.utc) != expected:
                problems.append(f"horário de referência incompatível: {key}")
    if end > now: missing.append("período mensal ainda não encerrado")
    result = {"period_start": start.date().isoformat(), "period_end": f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}",
              "timezone": "America/Sao_Paulo", "period_start_utc": start.isoformat(), "period_end_utc_exclusive": end.isoformat(),
              "loss_residual_m3": None, "loss_residual_mm_day": None, "missing": missing,
              "problems": problems, "coverage": "incompleta", "status": "dados insuficientes",
              "note": "Cobertura e origem declaradas pelo usuário; confira as referências antes de interpretar o resultado."}
    if problems:
        result["status"] = "inconsistente"
    elif not missing:
        duration_days = Decimal(str((end - start).total_seconds())) / Decimal(86400)
        result.update(water_balance(**{key: datum.value for key, datum in inputs.items()}, duration_days=duration_days))
        result["coverage"] = "declarada completa" if result["status"] == "perda residual estimada pelo balanço hídrico" else "inconsistente"
        result["origin"] = next(iter(sources)) if len(sources) == 1 else "mista"
    return result

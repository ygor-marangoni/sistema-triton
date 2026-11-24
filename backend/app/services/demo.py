"""Synthetic fixtures for properties owned by the local demo account only."""

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.services.domain import compare_month, water_balance


def is_demo_property(settings, user, prop):
    return (settings.app_env.lower() in {"development", "local", "test"}
            and user.email == "demo@example.com" and prop.owner_id == user.id)


def demo_balance(reservoir_id: int, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    history = []
    for offset in range(6, 0, -1):
        serial = today.year * 12 + today.month - 1 - offset
        year, zero_month = divmod(serial, 12)
        month = zero_month + 1
        days = monthrange(year, month)[1]
        step = 6 - offset
        result = water_balance(
            area_m2=Decimal("3500"), duration_days=Decimal(days), rain_mm=Decimal(45 + step * 7),
            inflow_m3=Decimal(2350 + step * 55), outflow_m3=Decimal(1950 + step * 45),
            other_outflow_m3=Decimal("220"), initial_volume_m3=Decimal("10000"),
            final_volume_m3=Decimal(10000 + step * 15),
        )
        history.append({"reservoir_id": reservoir_id, "period_start": date(year, month, 1).isoformat(),
                        "period_end": date(year, month, days).isoformat(), "coverage": "completa",
                        "origin": "simulada", **result})
    return {**history[-1], "history": history, "is_demo": True,
            "interpretation": "Demonstração: perda residual calculada com entradas inteiramente simuladas."}


def demo_weather(property_id: int, now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    variables = [
        ("temperature_air", Decimal("26.4"), "°C"), ("relative_humidity", Decimal("64"), "%"),
        ("wind_speed", Decimal("2.8"), "m/s"), ("wind_direction", Decimal("135"), "°"),
        ("precipitation", Decimal("3.6"), "mm"), ("solar_radiation", Decimal("1850"), "kJ/m²"),
    ]
    station = {"id": -1, "property_id": property_id, "source": "simulada", "station_code": "DEMO-001",
               "name": "Estação meteorológica demonstrativa", "city": None, "state": None,
               "latitude": None, "longitude": None, "is_active": True, "created_at": now}
    observations = []
    for day in range(5):
        observed = now - timedelta(days=day)
        for index, (variable, value, unit) in enumerate(variables):
            observations.append({"id": -(day * len(variables) + index + 1), "property_id": property_id,
                                 "station_id": -1, "source": "simulada", "station_code": "DEMO-001",
                                 "variable": variable, "value": value, "unit": unit,
                                 "observed_at": observed, "collected_at": now, "is_valid": True,
                                 "quality": "simulada para demonstração"})
    return {"station": station, "configured": False, "configuration_message": "Dados simulados; nenhuma coleta oficial foi realizada.",
            "configured_variables": [v[0] for v in variables], "latest_observations": observations[:6],
            "recent_observations": observations, "last_observation_at": now, "last_collected_at": now,
            "last_collection": None, "is_demo": True}


def demo_permit_comparison(permit, demand, today: date) -> dict:
    """Use an explicitly simulated month-to-date series, separate from saved readings."""
    readings = []
    for day in range(1, today.day + 1):
        observed = datetime(today.year, today.month, day, 12, tzinfo=ZoneInfo("America/Sao_Paulo"))
        volume = Decimal(18 + (day % 8)) if day <= int(demand.authorized_days) else Decimal(0)
        readings.append(SimpleNamespace(observed_at=observed, volume_m3=volume, quality="simulada"))
    result = compare_month(permit, demand, readings, today.year, today.month)
    result.update({"is_demo": True, "coverage": "simulada", "missing_days": 0,
                   "notes": "Exemplo sintético até hoje, independente das leituras salvas. Não representa captação real."})
    return result

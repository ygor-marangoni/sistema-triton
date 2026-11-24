from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from app.services.domain import compare_month


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def stale_measurement_candidate(component_type: str, component_id: int, name: str, last_observed_at: datetime | None,
                                component_created_at: datetime, now: datetime, threshold_hours: int) -> dict | None:
    reference = last_observed_at or component_created_at
    age = _utc(now) - _utc(reference)
    if age <= timedelta(hours=threshold_hours):
        return None
    return {
        "fingerprint": f"stale:{component_type}:{component_id}",
        "origin": component_type,
        "rule": "Medição atrasada",
        "severity": "warning",
        "details": {
            "component_id": component_id,
            "component_name": name,
            "last_observed_at": last_observed_at.isoformat() if last_observed_at else None,
            "hours_without_valid_reading": round(age.total_seconds() / 3600, 1),
            "threshold_hours": threshold_hours,
            "message": "Sem leitura observada dentro do prazo configurado." if last_observed_at else "Equipamento sem primeira leitura dentro do prazo configurado.",
        },
    }


def missing_outorga_candidate(meter) -> dict | None:
    if meter.kind != "entrada" or meter.outorga_id is not None:
        return None
    return {
        "fingerprint": f"missing-outorga:hydrometer:{meter.id}",
        "origin": "hidrômetro",
        "rule": "Captação sem outorga associada",
        "severity": "warning",
        "details": {"component_id": meter.id, "component_name": meter.name, "message": "Leituras são preservadas, mas não entram na comparação de conformidade."},
    }


def expired_outorga_candidate(outorga, today: date) -> dict | None:
    if outorga.valid_until >= today:
        return None
    return {
        "fingerprint": f"expired-outorga:{outorga.id}",
        "origin": "outorga",
        "rule": "Outorga fora da vigência",
        "severity": "warning",
        "details": {"outorga_id": outorga.id, "permit_number": outorga.permit_number, "valid_until": outorga.valid_until.isoformat(), "message": "Confira a vigência cadastrada antes de interpretar comparações."},
    }


def daily_extrapolation_candidates(outorga, demand, readings, year: int, month: int) -> list[dict]:
    summary = compare_month(outorga, demand, readings, year, month)
    candidates = []
    for day in summary["daily"]:
        excess = Decimal(day["extrapolated_m3"])
        if excess <= 0:
            continue
        candidates.append({
            "fingerprint": f"outorga-extrapolation:{outorga.id}:{day['date']}",
            "origin": "outorga",
            "rule": "Extrapolação diária da cota" if day["status"] != "dia de operação excedente" else "Dias de operação autorizados excedidos",
            "severity": "critical",
            "details": {
                "outorga_id": outorga.id,
                "outorga_name": outorga.name,
                "operating_date": day["date"],
                "measured_volume_m3": str(day["volume_m3"]),
                "daily_reference_limit_m3": str(summary["daily_reference_limit_m3"]),
                "extrapolated_m3": str(excess),
                "operating_days_used": summary["operating_days_used"],
                "operating_days_authorized": summary["operating_days_authorized"],
                "message": "A sobra de outros dias não compensa este excesso; verifique o registro e as condições da outorga.",
            },
        })
    return candidates


def quality_review_candidate(meter, reading) -> dict | None:
    if not (reading.quality.startswith("pendente") or reading.quality.startswith("inconsistente")):
        return None
    return {
        "fingerprint": f"reading-review:hydrometer:{reading.id}",
        "origin": "hidrômetro",
        "rule": "Leitura exige conferência",
        "severity": "warning",
        "details": {"component_id": meter.id, "component_name": meter.name, "reading_id": reading.id, "observed_at": reading.observed_at.isoformat(), "source": reading.source, "quality": reading.quality},
    }


def level_quality_review_candidate(station, reading) -> dict | None:
    if not (reading.quality.startswith("pendente") or reading.quality.startswith("inconsistente") or reading.quality.startswith("inconclusiva")):
        return None
    return {
        "fingerprint": f"reading-review:level-station:{reading.id}",
        "origin": "nível",
        "rule": "Leitura exige conferência",
        "severity": "warning",
        "details": {"component_id": station.id, "component_name": station.name, "reading_id": reading.id, "observed_at": reading.observed_at.isoformat(), "source": reading.source, "quality": reading.quality},
    }

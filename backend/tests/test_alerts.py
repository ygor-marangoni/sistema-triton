from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.services.alerts import daily_extrapolation_candidates, level_quality_review_candidate, stale_measurement_candidate


def test_stale_alert_uses_the_configured_threshold_and_keeps_timestamp():
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    last = now - timedelta(hours=49)

    alert = stale_measurement_candidate("hidrômetro", 7, "Captação", last, last, now, 48)

    assert alert is not None
    assert alert["fingerprint"] == "stale:hidrômetro:7"
    assert alert["details"]["last_observed_at"] == last.isoformat()
    assert stale_measurement_candidate("hidrômetro", 7, "Captação", now, now, now, 48) is None


def test_alerts_flag_the_excess_day_without_using_another_days_surplus():
    outorga = SimpleNamespace(id=9, name="Outorga de referência", valid_from=date(2026, 1, 1), valid_until=date(2026, 12, 31))
    demand = SimpleNamespace(max_flow_m3_h=Decimal("10"), daily_hours=Decimal("10"), authorized_days=20, monthly_volume_m3=Decimal("2000"))
    readings = [
        SimpleNamespace(observed_at=datetime(2026, 3, 1, 12, tzinfo=timezone.utc), volume_m3=Decimal("0")),
        SimpleNamespace(observed_at=datetime(2026, 3, 2, 12, tzinfo=timezone.utc), volume_m3=Decimal("200")),
    ]

    candidates = daily_extrapolation_candidates(outorga, demand, readings, 2026, 3)

    assert len(candidates) == 1
    assert candidates[0]["fingerprint"] == "outorga-extrapolation:9:2026-03-02"
    assert candidates[0]["details"]["extrapolated_m3"] == "100"
    assert "não compensa" in candidates[0]["details"]["message"]


def test_days_beyond_the_authorized_count_flag_the_entire_later_day():
    outorga = SimpleNamespace(id=10, name="Outorga", valid_from=date(2026, 1, 1), valid_until=date(2026, 12, 31))
    demand = SimpleNamespace(max_flow_m3_h=Decimal("10"), daily_hours=Decimal("10"), authorized_days=1, monthly_volume_m3=Decimal("100"))
    readings = [
        SimpleNamespace(observed_at=datetime(2026, 3, 1, 12, tzinfo=timezone.utc), volume_m3=Decimal("10")),
        SimpleNamespace(observed_at=datetime(2026, 3, 2, 12, tzinfo=timezone.utc), volume_m3=Decimal("10")),
    ]

    candidates = daily_extrapolation_candidates(outorga, demand, readings, 2026, 3)

    assert len(candidates) == 1
    assert candidates[0]["details"]["operating_date"] == "2026-03-02"
    assert candidates[0]["details"]["extrapolated_m3"] == "10"


def test_inconclusive_level_reading_is_a_review_alert_not_a_level_estimate():
    station = SimpleNamespace(id=4, name="Régua do reservatório")
    reading = SimpleNamespace(id=22, observed_at=datetime(2026, 3, 1, 12, tzinfo=timezone.utc), source="manual", quality="inconclusiva: escala obstruída")

    candidate = level_quality_review_candidate(station, reading)

    assert candidate["fingerprint"] == "reading-review:level-station:22"
    assert candidate["details"]["quality"] == "inconclusiva: escala obstruída"

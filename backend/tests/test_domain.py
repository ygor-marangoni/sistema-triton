from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
import pytest
from app.services.domain import compare_month, reservoir_volume, water_balance


def test_frustum_volume_empty_midpoint_and_full():
    # Base 10 m x 10 m, top 20 m x 20 m, height 10 m.
    args = tuple(map(Decimal, ("10", "10", "20", "20", "10")))
    assert reservoir_volume(*args, Decimal(0)) == Decimal(0)
    assert reservoir_volume(*args, Decimal(10)) == Decimal("2333.333333333333333333333333")
    assert reservoir_volume(*args, Decimal(5)) == Decimal("791.6666666666666666666666667")


def test_daily_surplus_never_offsets_another_day_excess():
    outorga = SimpleNamespace(valid_from=date(2026, 1, 1), valid_until=date(2026, 12, 31))
    demand = SimpleNamespace(max_flow_m3_h=Decimal(10), daily_hours=Decimal(10), authorized_days=20, monthly_volume_m3=Decimal(2000))
    readings = [SimpleNamespace(observed_at=datetime(2026, 3, 1, 12, tzinfo=timezone.utc), volume_m3=Decimal(0)), SimpleNamespace(observed_at=datetime(2026, 3, 2, 12, tzinfo=timezone.utc), volume_m3=Decimal(200))]
    result = compare_month(outorga, demand, readings, 2026, 3)
    assert result["non_transferable_surplus_m3"] == Decimal(100)
    assert result["extrapolated_m3"] == Decimal(100)
    assert result["coverage"] == "incompleto"


def test_excess_operating_days_count_all_volume_as_extrapolated():
    outorga = SimpleNamespace(valid_from=date(2026, 1, 1), valid_until=date(2026, 12, 31))
    demand = SimpleNamespace(max_flow_m3_h=Decimal(10), daily_hours=Decimal(10), authorized_days=1, monthly_volume_m3=Decimal(100))
    readings = [SimpleNamespace(observed_at=datetime(2026, 3, day, 12, tzinfo=timezone.utc), volume_m3=Decimal(1)) for day in (1, 2)]
    result = compare_month(outorga, demand, readings, 2026, 3)
    assert result["operating_days_used"] == 2
    assert result["extrapolated_m3"] == Decimal(1)


def test_water_balance_stays_insufficient_without_inputs():
    result = water_balance(area_m2=None, duration_days=None, rain_mm=None, inflow_m3=None, outflow_m3=None, other_outflow_m3=None, initial_volume_m3=None, final_volume_m3=None)
    assert result["status"] == "dados insuficientes"
    assert result["loss_residual_mm_day"] is None


def test_geometry_rejects_level_outside_physical_range():
    with pytest.raises(ValueError):
        reservoir_volume(*(Decimal(10) for _ in range(5)), Decimal(11))


def test_inconsistent_and_unknown_intervals_do_not_enter_permit_totals():
    permit = SimpleNamespace(valid_from=date(2026, 1, 1), valid_until=date(2026, 12, 31))
    demand = SimpleNamespace(max_flow_m3_h=Decimal(10), daily_hours=Decimal(2), authorized_days=5, monthly_volume_m3=Decimal(100))
    readings = [SimpleNamespace(observed_at=datetime(2026, 3, day, 12, tzinfo=timezone.utc), volume_m3=value, quality=quality)
                for day, value, quality in [(1, Decimal(8), "não revisada"), (2, None, "inconsistente: reinício"), (3, Decimal(90), "inconsistente: revisar")]]
    result = compare_month(permit, demand, readings, 2026, 3)
    assert result["measured_volume_m3"] == Decimal(8)
    assert result["pending_readings"] == 2
    assert len(result["daily"]) == 1

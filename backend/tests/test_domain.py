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
    readings = [
        SimpleNamespace(id=1, interval_start_at=datetime(2026, 3, 1, 3, tzinfo=timezone.utc), observed_at=datetime(2026, 3, 1, 15, tzinfo=timezone.utc), volume_m3=Decimal(0), unit="m³", quality="validada"),
        SimpleNamespace(id=2, interval_start_at=datetime(2026, 3, 2, 3, tzinfo=timezone.utc), observed_at=datetime(2026, 3, 2, 15, tzinfo=timezone.utc), volume_m3=Decimal(200), unit="m³", quality="validada"),
    ]
    result = compare_month(outorga, demand, readings, 2026, 3)
    assert result["non_transferable_surplus_m3"] == Decimal(100)
    assert result["extrapolated_m3"] == Decimal(100)
    assert result["coverage"] == "incompleto"


def test_excess_operating_days_count_all_volume_as_extrapolated():
    outorga = SimpleNamespace(valid_from=date(2026, 1, 1), valid_until=date(2026, 12, 31))
    demand = SimpleNamespace(max_flow_m3_h=Decimal(10), daily_hours=Decimal(10), authorized_days=1, monthly_volume_m3=Decimal(100))
    readings = [SimpleNamespace(id=day, interval_start_at=datetime(2026, 3, day, 3, tzinfo=timezone.utc),
                                observed_at=datetime(2026, 3, day, 15, tzinfo=timezone.utc), volume_m3=Decimal(1),
                                unit="m³", quality="validada") for day in (1, 2)]
    result = compare_month(outorga, demand, readings, 2026, 3)
    assert result["operating_days_used"] == 2
    assert result["extrapolated_m3"] == Decimal(1)


def test_water_balance_stays_insufficient_without_inputs():
    result = water_balance(area_m2=None, duration_days=None, rain_mm=None, inflow_m3=None, outflow_m3=None, other_outflow_m3=None, initial_volume_m3=None, final_volume_m3=None)
    assert result["status"] == "dados insuficientes"
    assert result["loss_residual_mm_day"] is None


BALANCE_FIXTURE = dict(area_m2=1000, duration_days=10, rain_mm=10, inflow_m3=50,
                       outflow_m3=20, other_outflow_m3=5, initial_volume_m3=100, final_volume_m3=110)


def test_synthetic_water_balance_equation():
    result = water_balance(**BALANCE_FIXTURE)
    assert result["loss_residual_m3"] == Decimal(25)
    assert result["loss_residual_mm_day"] == Decimal("2.5")


@pytest.mark.parametrize("missing", list(BALANCE_FIXTURE))
def test_synthetic_water_balance_does_not_fill_missing_input(missing):
    result = water_balance(**(BALANCE_FIXTURE | {missing: None}))
    assert result["status"] == "dados insuficientes"
    assert result["missing"] == [missing]
    assert result["loss_residual_m3"] is None


@pytest.mark.parametrize("invalid", [-1, "NaN", "Infinity"])
def test_water_balance_rejects_invalid_values(invalid):
    assert water_balance(**(BALANCE_FIXTURE | {"rain_mm": invalid}))["status"] == "inconsistente"


def test_geometry_rejects_level_outside_physical_range():
    with pytest.raises(ValueError):
        reservoir_volume(*(Decimal(10) for _ in range(5)), Decimal(11))


def test_inconsistent_and_unknown_intervals_do_not_enter_permit_totals():
    permit = SimpleNamespace(valid_from=date(2026, 1, 1), valid_until=date(2026, 12, 31))
    demand = SimpleNamespace(max_flow_m3_h=Decimal(10), daily_hours=Decimal(2), authorized_days=5, monthly_volume_m3=Decimal(100))
    readings = [SimpleNamespace(id=day, interval_start_at=datetime(2026, 3, day, 3, tzinfo=timezone.utc),
                observed_at=datetime(2026, 3, day, 15, tzinfo=timezone.utc), volume_m3=value, unit="m³", quality=quality)
                for day, value, quality in [(1, Decimal(8), "validada"), (2, None, "inconsistente: reinício"), (3, Decimal(90), "inconsistente: revisar")]]
    result = compare_month(permit, demand, readings, 2026, 3)
    assert result["measured_volume_m3"] == Decimal(8)
    assert result["pending_readings"] == 2
    assert len(result["daily"]) == 1


def _eligible_reading(reading_id, start, end, volume, **extra):
    return SimpleNamespace(id=reading_id, interval_start_at=start, observed_at=end, volume_m3=Decimal(volume),
        unit="m³", quality="validada", **extra)


def test_simultaneous_intervals_on_different_meters_are_not_duplicates():
    permit = SimpleNamespace(valid_from=date(2026, 1, 1), valid_until=date(2026, 12, 31))
    demand = SimpleNamespace(max_flow_m3_h=Decimal(10), daily_hours=Decimal(10), authorized_days=20, monthly_volume_m3=Decimal(2000))
    start = datetime(2026, 3, 2, 3, tzinfo=timezone.utc)
    end = datetime(2026, 3, 2, 6, tzinfo=timezone.utc)
    rows = [_eligible_reading(1, start, end, '10', hydrometer_id=1, external_id='same'),
            _eligible_reading(2, start, end, '20', hydrometer_id=2, external_id='same')]
    result = compare_month(permit, demand, rows, 2026, 3)
    assert result['measured_volume_m3'] == Decimal(30)
    assert result['duplicate_readings'] == 0
    assert result['unassigned_intervals'] == 0


def _comparison(readings):
    permit = SimpleNamespace(id=7, valid_from=date(2026, 1, 1), valid_until=date(2026, 12, 31))
    demand = SimpleNamespace(max_flow_m3_h=Decimal(10), daily_hours=Decimal(10), authorized_days=20, monthly_volume_m3=Decimal(2000))
    return compare_month(permit, demand, readings, 2026, 3)


def test_no_eligible_meter_readings_is_missing_not_zero():
    result = _comparison([])
    assert result["measured_volume_m3"] is None
    assert result["status"] == "dados insuficientes"
    assert result["daily"] == []


def test_same_day_interval_is_attributed_to_its_operational_day():
    reading = _eligible_reading(1, datetime(2026, 3, 1, 3, tzinfo=timezone.utc),
        datetime(2026, 3, 1, 15, tzinfo=timezone.utc), "12")
    result = _comparison([reading])
    assert result["measured_volume_m3"] == Decimal(12)
    assert result["daily"][0]["date"] == "2026-03-01"
    assert result["daily"][0]["volume_m3"] == Decimal(12)
    assert result["eligible_intervals"][0]["interval_start_at"] == datetime(2026, 3, 1, 3, tzinfo=timezone.utc)
    assert result["eligible_intervals"][0]["daily_assignment"] == "2026-03-01"


def test_cross_midnight_interval_is_monthly_evidence_but_not_daily_allocated():
    reading = _eligible_reading(1, datetime(2026, 3, 2, 2, tzinfo=timezone.utc),
        datetime(2026, 3, 2, 4, tzinfo=timezone.utc), "12")
    result = _comparison([reading])
    assert result["measured_volume_m3"] == Decimal(12)
    assert result["daily"] == []
    assert result["unassigned_intervals"] == 1
    assert result["eligible_intervals"][0]["interval_start_at"] == datetime(2026, 3, 2, 2, tzinfo=timezone.utc)
    assert result["eligible_intervals"][0]["daily_assignment"] is None
    assert result["review_items"][0]["reason"] == "intervalo cruza dias operacionais; não foi distribuído"


def test_duplicate_external_id_is_counted_once_and_flagged():
    start, end = datetime(2026, 3, 1, 3, tzinfo=timezone.utc), datetime(2026, 3, 1, 15, tzinfo=timezone.utc)
    result = _comparison([_eligible_reading(1, start, end, "4", external_id="synthetic-dup"),
                          _eligible_reading(2, start, end, "4", external_id="synthetic-dup")])
    assert result["measured_volume_m3"] == Decimal(4)
    assert result["duplicate_readings"] == 1
    assert result["review_items"][0]["reason"] == "identificador de leitura duplicado"


def test_out_of_order_input_is_sorted_before_daily_comparison():
    later = _eligible_reading(2, datetime(2026, 3, 2, 3, tzinfo=timezone.utc), datetime(2026, 3, 2, 15, tzinfo=timezone.utc), "7")
    earlier = _eligible_reading(1, datetime(2026, 3, 1, 3, tzinfo=timezone.utc), datetime(2026, 3, 1, 15, tzinfo=timezone.utc), "5")
    result = _comparison([later, earlier])
    assert result["measured_volume_m3"] == Decimal(12)
    assert [item["date"] for item in result["daily"]] == ["2026-03-01", "2026-03-02"]
    assert result["out_of_order_readings"] == 1


def test_incompatible_unit_is_not_summed():
    reading = _eligible_reading(1, datetime(2026, 3, 1, 3, tzinfo=timezone.utc),
        datetime(2026, 3, 1, 15, tzinfo=timezone.utc), "12")
    reading.unit = "L"
    result = _comparison([reading])
    assert result["measured_volume_m3"] is None
    assert result["pending_readings"] == 1


def test_legacy_reading_without_interval_is_preserved_but_not_assigned_to_day():
    reading = SimpleNamespace(id=1, observed_at=datetime(2026, 3, 1, 15, tzinfo=timezone.utc),
        volume_m3=Decimal(15), unit="m³", quality="validada")
    result = _comparison([reading])
    assert result["measured_volume_m3"] is None
    assert result["unassigned_intervals"] == 1

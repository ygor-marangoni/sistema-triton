"""Synthetic-only tests for interval-complete automatic water-balance assembly."""
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.balance_auto import assess_automatic_month, month_bounds_utc


def synthetic_evidence():
    start, end = month_bounds_utc(2025, 1)
    rain = [SimpleNamespace(id=101, interval_start_at=start, observed_at=end, value=Decimal("10"), unit="mm",
                            quality="validada", source="manual", reference="fixture sintética de chuva")]
    inlet = [SimpleNamespace(id=201, interval_start_at=start, observed_at=end, volume_m3=Decimal("50"),
                             unit="m³", quality="validada", source="manual", outorga_id=701,
                             outorga_link_id=801, outorga_link_status="confirmado")]
    outlet = [SimpleNamespace(id=301, interval_start_at=start, observed_at=end, volume_m3=Decimal("20"),
                              unit="m³", quality="validada", source="manual")]
    levels = [SimpleNamespace(id=401, level_m=Decimal("1"), observed_at=start, quality="validada", source="manual"),
              SimpleNamespace(id=402, level_m=Decimal("2"), observed_at=end, quality="validada", source="manual")]
    curve = SimpleNamespace(id=501, is_approved=True, valid_from=date(2024, 1, 1), valid_until=date(2026, 12, 31),
                            survey_date=date(2024, 1, 1), survey_source="fixture sintética",
                            survey_responsible="fixture sintética", created_by_id=1, approved_by_id=1,
                            approved_at=datetime(2024, 1, 2, tzinfo=timezone.utc), level_unit="m",
                            volume_unit="m3", points=[{"level": "0", "volume": "90"},
                                {"level": "1", "volume": "100"}, {"level": "2", "volume": "110"}])
    other = [SimpleNamespace(id=601, period_start_at=start, period_end_at=end, value_m3=Decimal("5"), unit="m3",
                             quality="validada", source="documento", reference="fixture sintética de saída")]
    meters_in = [SimpleNamespace(id=1, kind="entrada", readings=inlet)]
    meters_out = [SimpleNamespace(id=2, kind="saída", readings=outlet)]
    return dict(year=2025, month=1, now=datetime(2025, 2, 2, tzinfo=timezone.utc), rainfall_rows=rain,
                inlet_meters=meters_in, outlet_meters=meters_out, level_readings=levels,
                curves=[curve], other_outflow_rows=other)


def test_synthetic_full_month_is_automatically_proven_and_traceable():
    result = assess_automatic_month(**synthetic_evidence())
    assert result["status"] == "perda residual estimada pelo balanço hídrico"
    assert result["coverage"] == "comprovada"
    assert result["loss_residual_m3"] == Decimal("15.1")
    assert result["curve_id"] == 501
    assert result["data_sources"]["rain_mm"][0]["id"] == 101
    assert result["data_sources"]["inflow_m3"][0]["id"] == 201
    assert result["data_sources"]["inflow_m3"][0]["outorga_link_id"] == 801
    assert result["data_sources"]["other_outflow_m3"][0]["reference"] == "fixture sintética de saída"


def test_month_partial_and_gap_in_rainfall_stay_insufficient():
    fixture = synthetic_evidence()
    fixture["rainfall_rows"] = []
    result = assess_automatic_month(**fixture)
    assert result["status"] == "dados insuficientes"
    assert result["loss_residual_m3"] is None
    assert any("precipitação" in value for value in result["missing"])

    fixture = synthetic_evidence()
    start, end = month_bounds_utc(2025, 1)
    split = start + (end - start) / 2
    fixture["rainfall_rows"] = [
        SimpleNamespace(id=1, interval_start_at=start, observed_at=split, value=Decimal("3"), unit="mm", quality="validada", source="manual"),
        SimpleNamespace(id=2, interval_start_at=split + (end - start) / 100, observed_at=end, value=Decimal("7"), unit="mm", quality="validada", source="manual"),
    ]
    result = assess_automatic_month(**fixture)
    assert result["loss_residual_m3"] is None
    assert any("precipitação" in value for value in result["missing"])
    assert any("lacuna" in value for value in result["problems"])


@pytest.mark.parametrize("field,label", [("inlet_meters", "entrada"), ("outlet_meters", "saída")])
def test_missing_inlet_or_outlet_is_not_assumed_zero(field, label):
    fixture = synthetic_evidence()
    fixture[field] = []
    result = assess_automatic_month(**fixture)
    assert result["loss_residual_m3"] is None
    assert any(label in value for value in result["missing"])


def test_curve_not_applicable_to_period_is_not_used():
    fixture = synthetic_evidence()
    fixture["curves"][0].valid_until = date(2025, 1, 15)
    result = assess_automatic_month(**fixture)
    assert result["curve_id"] is None
    assert result["loss_residual_m3"] is None
    assert any("curva cota-volume" in value for value in result["missing"])


def test_incompatible_flow_interval_or_unreviewed_value_does_not_prove_coverage():
    fixture = synthetic_evidence()
    fixture["inlet_meters"][0].readings[0].quality = "não revisada"
    result = assess_automatic_month(**fixture)
    assert result["loss_residual_m3"] is None
    assert any("cobertura completa de hidrômetro(s) de entrada" in value for value in result["missing"])

    fixture = synthetic_evidence()
    fixture["inlet_meters"][0].readings[0].interval_start_at = datetime(2025, 1, 2, 3, tzinfo=timezone.utc)
    result = assess_automatic_month(**fixture)
    assert result["loss_residual_m3"] is None
    assert any("lacuna" in value for value in result["problems"])

    fixture = synthetic_evidence()
    fixture["inlet_meters"][0].readings[0].outorga_link_status = "sem vínculo comprovável"
    result = assess_automatic_month(**fixture)
    assert result["loss_residual_m3"] is None
    assert any("vínculo histórico" in value for value in result["problems"])


def test_synthetic_curve_out_of_range_and_equal_level_do_not_extrapolate_area():
    fixture = synthetic_evidence()
    fixture["level_readings"][1].level_m = Decimal("3")
    result = assess_automatic_month(**fixture)
    assert result["loss_residual_m3"] is None
    assert any("fora da faixa" in value for value in result["problems"])

    fixture = synthetic_evidence()
    fixture["level_readings"][1].level_m = Decimal("1")
    result = assess_automatic_month(**fixture)
    assert result["loss_residual_m3"] is None
    assert any("área superficial média" in value for value in result["missing"])


def test_incomplete_month_never_returns_a_residual():
    fixture = synthetic_evidence()
    fixture["now"] = datetime(2025, 1, 10, tzinfo=timezone.utc)
    result = assess_automatic_month(**fixture)
    assert result["status"] == "dados insuficientes"
    assert result["loss_residual_m3"] is None
    assert "período mensal ainda não encerrado" in result["missing"]

"""Synthetic data only; these tests do not exercise an external device or survey."""
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.services.stage_volume import interpolate_volume
from app.services.telemetry_contract import NormalizedReading


def sample_reading():
    return dict(property_id=1, component_id=2, component_type="hydrometer", variable="totalizer",
                value="10.250", unit="m3", observed_at="2026-01-02T10:00:00Z",
                collected_at="2026-01-03T10:00:00Z", source="test", origin_id="synthetic-1")


def test_normalized_contract_preserves_delayed_observation():
    reading = NormalizedReading(**sample_reading())
    assert reading.collected_at > reading.observed_at
    assert reading.value == Decimal("10.250")


@pytest.mark.parametrize("change", [
    {"unit": "m"}, {"component_id": 0}, {"property_id": 0}, {"origin_id": "  "},
    {"observed_at": "2026-01-02T10:00:00"}, {"value": "-1"}, {"source": "mqtt"},
])
def test_normalized_contract_rejects_invalid_inputs(change):
    with pytest.raises(ValidationError):
        NormalizedReading(**(sample_reading() | change))


def test_curve_interpolates_only_within_synthetic_survey():
    points = [(Decimal("1"), Decimal("100")), (Decimal("2"), Decimal("300"))]
    assert interpolate_volume(points, Decimal("1.5")) == Decimal("200")
    with pytest.raises(ValueError, match="extrapolação"):
        interpolate_volume(points, Decimal("2.1"))
    with pytest.raises(ValueError):
        interpolate_volume(list(reversed(points)), Decimal("1.5"))
    with pytest.raises(ValueError):
        interpolate_volume([(Decimal("1"), Decimal("300")), (Decimal("2"), Decimal("100"))], Decimal("1.5"))

"""All monthly evidence in this module is synthetic."""
from datetime import datetime, timezone

import pytest

from app.schemas import BalanceDatum
from app.services.balance_period import UNITS, assess_month


def synthetic_inputs():
    start = datetime(2025, 1, 1, 3, tzinfo=timezone.utc)
    end = datetime(2025, 2, 1, 3, tzinfo=timezone.utc)
    values = {"area_m2": 1000, "rain_mm": 10, "inflow_m3": 50, "outflow_m3": 20,
              "other_outflow_m3": 5, "initial_volume_m3": 100, "final_volume_m3": 110}
    return {key: BalanceDatum(value=value, unit=UNITS[key], source="simulada", reference=f"fixture-{key}",
                              period_start=start, period_end=end, coverage_complete=True,
                              observed_at=start if key == "initial_volume_m3" else end if key == "final_volume_m3" else None)
            for key, value in values.items()}


def test_synthetic_complete_month_residual_and_provenance():
    result = assess_month(2025, 1, synthetic_inputs(), datetime(2025, 2, 2, tzinfo=timezone.utc))
    assert result["status"] == "perda residual estimada pelo balanço hídrico"
    assert result["loss_residual_m3"] == 25
    assert result["origin"] == "simulada" and result["coverage"] == "declarada completa"


@pytest.mark.parametrize("key", list(UNITS))
def test_missing_each_synthetic_input_stays_insufficient(key):
    inputs = synthetic_inputs(); inputs.pop(key)
    result = assess_month(2025, 1, inputs)
    assert result["status"] == "dados insuficientes" and key in result["missing"]
    assert result["loss_residual_m3"] is None


def test_incompatible_unit_period_coverage_and_unfinished_month():
    inputs = synthetic_inputs()
    inputs["rain_mm"] = inputs["rain_mm"].model_copy(update={"unit": "m"})
    assert assess_month(2025, 1, inputs)["status"] == "inconsistente"
    inputs = synthetic_inputs()
    inputs["rain_mm"] = inputs["rain_mm"].model_copy(update={"period_start": datetime(2024, 12, 1, tzinfo=timezone.utc)})
    assert assess_month(2025, 1, inputs)["status"] == "inconsistente"
    inputs = synthetic_inputs()
    inputs["rain_mm"] = inputs["rain_mm"].model_copy(update={"coverage_complete": False})
    assert assess_month(2025, 1, inputs)["status"] == "dados insuficientes"
    assert assess_month(2025, 1, synthetic_inputs(), datetime(2025, 1, 10, tzinfo=timezone.utc))["status"] == "dados insuficientes"
    inputs = synthetic_inputs()
    inputs["rain_mm"] = inputs["rain_mm"].model_copy(update={"source": "medida"})
    assert assess_month(2025, 1, inputs)["status"] == "inconsistente"

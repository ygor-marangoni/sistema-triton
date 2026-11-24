from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.services.demo import demo_balance, demo_weather, is_demo_property


def test_demo_data_is_restricted_to_demo_owner_and_development():
    user = SimpleNamespace(id=1, email="demo@example.com")
    prop = SimpleNamespace(owner_id=1, name="[DEMO] Fazenda Horizonte")
    assert is_demo_property(SimpleNamespace(app_env="development"), user, prop)
    assert not is_demo_property(SimpleNamespace(app_env="production"), user, prop)
    assert not is_demo_property(SimpleNamespace(app_env="development"), SimpleNamespace(id=2, email="outro@example.com"), prop)
    assert not is_demo_property(SimpleNamespace(app_env="development"), user, SimpleNamespace(owner_id=2, name="Fazenda de outra conta"))


def test_demo_balance_has_calculated_labeled_full_months():
    result = demo_balance(7, date(2026, 3, 15))
    assert result["is_demo"] is True
    assert len(result["history"]) == 6
    assert result["history"][-1]["period_start"] == "2026-02-01"
    assert result["history"][-1]["period_end"] == "2026-02-28"
    assert all(item["origin"] == "simulada" and item["reservoir_id"] == 7 for item in result["history"])
    assert all(item["loss_residual_mm_day"] > 0 for item in result["history"])


def test_demo_weather_is_never_labeled_as_inmet():
    now = datetime(2026, 11, 24, 9, tzinfo=timezone.utc)
    result = demo_weather(3, now)
    assert result["is_demo"] is True and result["station"]["source"] == "simulada"
    assert len(result["latest_observations"]) == 6
    assert all(item["source"] == "simulada" and "simulada" in item["quality"] for item in result["recent_observations"])
    assert result["last_collection"] is None

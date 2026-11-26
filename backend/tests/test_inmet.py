"""Offline INMET adapter checks using only synthetic fixture data."""
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
import io
import json
import zipfile

import pytest

from app.integrations.inmet import CsvSchema, InmetAdapter, InmetError, VariableColumn, load_csv_schema, parse_archive

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "inmet" / "weather_fixture.csv"
FIXTURE_COLUMNS = {
    "temperature_air": VariableColumn("fixture_air_temp", "fixture-unit-temp"),
    "relative_humidity": VariableColumn("fixture_relative_humidity", "fixture-unit-rh"),
    "wind_speed": VariableColumn("fixture_wind_speed", "fixture-unit-wind"),
    "wind_direction": VariableColumn("fixture_wind_direction", "fixture-unit-direction"),
    "precipitation": VariableColumn("fixture_precipitation", "fixture-unit-rain"),
    "solar_radiation": VariableColumn("fixture_solar_radiation", "fixture-unit-radiation"),
}
FIXTURE_SCHEMA = CsvSchema(
    encoding="utf-8", delimiter=";", header_row=0,
    station_code_column="fixture_station", date_column="fixture_date", time_column="fixture_time",
    date_format="%Y-%m-%d", time_format="%H:%M", decimal_separator=",", thousands_separator="", variables=FIXTURE_COLUMNS,
    datetime_column=None, datetime_format=None, source_timezone="UTC",
)


def fixture_archive(csv_text=None):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("synthetic_fixture.csv", csv_text if csv_text is not None else FIXTURE_CSV.read_text(encoding="utf-8"))
    return archive.getvalue()


def test_fixture_archive_maps_station_variables_and_utc_timestamp_without_zero_filling():
    collected_at = datetime(2025, 1, 3, 9, tzinfo=timezone.utc)
    result = parse_archive(fixture_archive(), 2025, "FIXTURE-123", FIXTURE_SCHEMA, collected_at)
    by_key = {(item.variable, item.observed_at.hour): item for item in result}
    assert len(result) == 10
    assert by_key[("temperature_air", 12)].value == Decimal("25.1")
    assert by_key[("precipitation", 12)].value == Decimal("0.0")  # measured zero is distinct from a missing value
    assert by_key[("temperature_air", 12)].observed_at == datetime(2025, 1, 2, 12, tzinfo=timezone.utc)
    assert by_key[("temperature_air", 12)].collected_at == collected_at
    assert by_key[("temperature_air", 12)].quality == "raw_unvalidated"
    assert ("solar_radiation", 12) not in by_key  # official missing marker 9999 is omitted
    assert ("relative_humidity", 13) in by_key and ("temperature_air", 13) not in by_key
    assert all(item.station_code == "FIXTURE-123" for item in result)
    assert all(item.unit.startswith("fixture-unit") for item in result)


def test_schema_requires_explicit_source_headers_and_units():
    with pytest.raises(InmetError, match="não configurada"):
        load_csv_schema("")
    with pytest.raises(InmetError, match="cabeçalho"):
        parse_archive(fixture_archive("wrong;header\nvalue;value\n"), 2025, "FIXTURE-123", FIXTURE_SCHEMA, datetime.now(timezone.utc))


def test_invalid_numeric_value_rejects_the_whole_archive():
    malformed = FIXTURE_CSV.read_text(encoding="utf-8").replace("25,1", "sem-numero")
    with pytest.raises(InmetError, match="nenhum dado foi importado"):
        parse_archive(fixture_archive(malformed), 2025, "FIXTURE-123", FIXTURE_SCHEMA, datetime.now(timezone.utc))


def test_value_beyond_persisted_decimal_precision_rejects_whole_archive():
    too_precise = FIXTURE_CSV.read_text(encoding="utf-8").replace("25,1", "25,123456789")
    with pytest.raises(InmetError, match="precisão de armazenamento"):
        parse_archive(fixture_archive(too_precise), 2025, "FIXTURE-123", FIXTURE_SCHEMA, datetime.now(timezone.utc))


def test_conflicting_duplicate_fixture_record_rejects_archive():
    contents = FIXTURE_CSV.read_text(encoding="utf-8")
    duplicate = "FIXTURE-123;2025-01-02;12:00;26,0;75;2,3;180;0,0;450\n"
    with pytest.raises(InmetError, match="conflitantes"):
        parse_archive(fixture_archive(contents + duplicate), 2025, "FIXTURE-123", FIXTURE_SCHEMA, datetime.now(timezone.utc))


def test_archive_cache_avoids_second_request_within_configured_ttl():
    class NeverClient:
        def __init__(self, **kwargs):
            raise AssertionError("cache hit must avoid a network request")

    InmetAdapter._archive_cache[2025] = (100.0, fixture_archive())
    adapter = InmetAdapter(FIXTURE_SCHEMA, client_factory=NeverClient, cache_ttl_seconds=60, clock=lambda: 110.0)
    assert adapter.download_archive(2025) == fixture_archive()
    InmetAdapter._archive_cache.pop(2025, None)


def test_schema_and_single_timestamp_column_are_supported_explicitly():
    mapping = {
        "encoding": "utf-8", "delimiter": ";", "header_row": 0,
        "station_code_column": "fixture_station", "datetime_column": "fixture_timestamp",
        "datetime_format": "%Y-%m-%dT%H:%M", "decimal_separator": ",", "source_timezone": "UTC",
        "variables": {
            "temperature_air": {"column": "fixture_air_temp", "unit": "fixture-unit-temp"},
            "relative_humidity": {"column": "fixture_relative_humidity", "unit": "fixture-unit-rh"},
            "wind_speed": {"column": "fixture_wind_speed", "unit": "fixture-unit-wind"},
            "wind_direction": {"column": "fixture_wind_direction", "unit": "fixture-unit-direction"},
            "precipitation": {"column": "fixture_precipitation", "unit": "fixture-unit-rain"},
        },
    }
    schema = load_csv_schema(json.dumps(mapping))
    content = "fixture_station;fixture_timestamp;fixture_air_temp;fixture_relative_humidity;fixture_wind_speed;fixture_wind_direction;fixture_precipitation\nFIXTURE-123;2025-03-04T08:00;21,5;70;1,0;90;0,0\n"
    rows = parse_archive(fixture_archive(content), 2025, "FIXTURE-123", schema, datetime.now(timezone.utc))
    assert len(rows) == 5
    assert rows[0].observed_at == datetime(2025, 3, 4, 8, tzinfo=timezone.utc)
    with pytest.raises(InmetError, match="source_timezone"):
        load_csv_schema(json.dumps({key: value for key, value in mapping.items() if key != "source_timezone"}))
    schema_local = load_csv_schema(json.dumps(mapping | {"source_timezone": "America/Sao_Paulo"}))
    local_rows = parse_archive(fixture_archive(content), 2025, "FIXTURE-123", schema_local, datetime.now(timezone.utc))
    assert local_rows[0].observed_at == datetime(2025, 3, 4, 11, tzinfo=timezone.utc)


def test_upstream_rate_limit_or_server_failure_is_retried_once_then_reported(monkeypatch):
    class Response:
        status_code = 503
        headers = {}

        def __enter__(self): return self
        def __exit__(self, *args): return False

    class Client:
        def __init__(self, **kwargs): self.calls = 0
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def stream(self, *args, **kwargs):
            self.calls += 1
            return Response()

    monkeypatch.setattr("app.integrations.inmet.time.sleep", lambda _: None)
    client = Client()
    adapter = InmetAdapter(FIXTURE_SCHEMA, client_factory=lambda **kwargs: client, cache_ttl_seconds=0)
    with pytest.raises(InmetError, match="limite de requisições"):
        adapter.download_archive(2024)
    assert client.calls == 2

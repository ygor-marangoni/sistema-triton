import pytest
from io import BytesIO
from datetime import datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.session import get_db
from app.main import app, _cpf_fingerprint, _fernet, password_hash
from app.models import User, LevelImageReview
from app.integrations.inmet import InmetError, ParsedObservation
import app.main as main_module


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with test_session() as db:
        for user_id, name, email, cpf in [
            (1, "Proprietário A", "a@example.com", "12345678909"),
            (2, "Proprietário B", "b@example.com", "98765432100"),
        ]:
            db.add(User(id=user_id, name=name, email=email,
                        password_hash=password_hash.hash("Senha-Segura-123!"),
                        cpf_encrypted=_fernet().encrypt(cpf.encode()).decode(),
                        cpf_fingerprint=_cpf_fingerprint(cpf), business_address="Endereço fictício", role="user"))
        db.commit()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_property_data_isolated_between_users(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    created = client.post("/properties", json={"name": "Fazenda de A", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG"})
    assert created.status_code == 201
    property_id = created.json()["id"]
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    assert client.get(f"/properties/{property_id}").status_code == 404
    assert client.patch(f"/properties/{property_id}", json={"name": "Tomada"}).status_code == 404


def test_property_map_coordinates_are_validated_editable_and_isolated(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    created = client.post("/properties", json={
        "name": "Fazenda mapeada", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG",
        "latitude": -18.731234, "longitude": -47.498765,
    })
    assert created.status_code == 201
    prop = created.json()
    assert prop["latitude"] == "-18.731234"
    assert prop["longitude"] == "-47.498765"

    updated = client.patch(f"/properties/{prop['id']}", json={"latitude": -18.75, "longitude": -47.52})
    assert updated.status_code == 200
    assert updated.json()["latitude"] == "-18.750000"
    assert updated.json()["longitude"] == "-47.520000"
    cleared = client.patch(f"/properties/{prop['id']}", json={"latitude": None, "longitude": None})
    assert cleared.status_code == 200
    assert cleared.json()["latitude"] is None and cleared.json()["longitude"] is None

    assert client.post("/properties", json={
        "name": "Coordenada incompleta", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG",
        "latitude": -18.7,
    }).status_code == 422
    assert client.post("/properties", json={
        "name": "Latitude fora da faixa", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG",
        "latitude": -91, "longitude": -47,
    }).status_code == 422
    assert client.patch(f"/properties/{prop['id']}", json={"latitude": -18.7}).status_code == 422

    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    assert client.get(f"/properties/{prop['id']}").status_code == 404
    assert client.patch(f"/properties/{prop['id']}", json={"latitude": -18.7, "longitude": -47.4}).status_code == 404


def test_reservoir_map_geometry_is_isolated(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    _, station = create_test_station(client)
    reservoir_id = station["reservoir_id"]
    geometry = client.get(f"/reservoirs/{reservoir_id}/map-geometry")
    assert geometry.status_code == 200
    assert geometry.json()["name"] == "Reservatório teste"
    assert "<Polygon>" in geometry.json()["geometry_kml"]
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    assert client.get(f"/reservoirs/{reservoir_id}/map-geometry").status_code == 404


def test_health_and_docs_are_available(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200


def test_session_probe_is_clean_for_guests_and_logged_in_users(client):
    guest = client.get("/auth/session")
    assert guest.status_code == 200
    assert guest.json() == {"authenticated": False, "user": None}
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    authenticated = client.get("/auth/session")
    assert authenticated.status_code == 200
    assert authenticated.json()["authenticated"] is True
    assert authenticated.json()["user"]["email"] == "a@example.com"


def synthetic_ruler_png():
    """Synthetic HTTP fixture only; it is not evidence of a real field reading."""
    image = Image.new("RGB", (120, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((42, 20, 76, 220), outline="black", width=2)
    for y in (50, 100, 150, 200):
        draw.line((42, y, 76, y), fill="black", width=2)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def create_test_station(client, property_name="Fazenda de A"):
    prop = client.post("/properties", json={"name": property_name, "cep": "38500-000", "city": "Monte Carmelo", "state": "MG"}).json()
    reservoir = client.post(f"/properties/{prop['id']}/reservoirs", json={
        "name": "Reservatório teste", "base_width_m": 10, "base_length_m": 12,
        "top_width_m": 12, "top_length_m": 14, "height_m": 4,
        "geometry_kml": "<kml><Document><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>-46,-17 -45.9,-17 -45.9,-16.9 -46,-16.9 -46,-17</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>",
    }).json()
    station = client.post("/level-stations", json={"reservoir_id": reservoir["id"], "name": "Régua de teste", "minimum_m": 0, "maximum_m": 4})
    assert station.status_code == 201
    return prop, station.json()


def test_demo_loader_creates_usable_labeled_account_without_overwriting(client, monkeypatch):
    import scripts.load_demo as demo
    reserved = client.post('/auth/register', json={"name": "Conta comum", "email": "demo@example.com", "cpf": "11144477735", "business_address": "Endereço de teste", "password": "Senha-Segura-123!"})
    assert reserved.status_code == 409
    sessions = []
    def session_factory():
        generator = app.dependency_overrides[get_db]()
        sessions.append(generator)
        return next(generator)
    monkeypatch.setattr(demo, "SessionLocal", session_factory)
    try:
        demo.main()
        demo.main()
        login = client.post("/auth/login", json={"email": demo.DEMO_EMAIL, "password": demo.DEMO_PASSWORD})
        assert login.status_code == 200
        properties = client.get("/properties").json()
        assert len(properties) == 1 and properties[0]["name"].startswith("[DEMO]")
        assert properties[0]["latitude"] is not None and properties[0]["longitude"] is not None
        dashboard = client.get(f"/dashboard/{properties[0]['id']}").json()
        assert dashboard["recent_hydrometers"][0]["readings"][0]["source"] == "simulada"
        comparison = dashboard["monthly_comparisons"][0]
        assert comparison["is_demo"] is True and comparison["coverage"] == "simulada"
        assert comparison["missing_days"] == 0 and "independente das leituras salvas" in comparison["notes"]
        assert client.get(f"/alerts/{properties[0]['id']}").json()[0]["origin"] == "demonstração"
        weather = client.get(f"/properties/{properties[0]['id']}/meteorology").json()
        assert weather["is_demo"] is True and weather["station"]["source"] == "simulada"
        assert len(weather["latest_observations"]) == 6
        assert all(item["source"] == "simulada" for item in weather["recent_observations"])
        balance = client.get(f"/evaporation/estimate/{properties[0]['id']}").json()
        assert balance["is_demo"] is True and len(balance["history"]) == 6
        assert all(item["origin"] == "simulada" and item["coverage"] == "completa" for item in balance["history"])
        client.post("/auth/logout")
        assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
        assert client.get(f"/properties/{properties[0]['id']}/meteorology").status_code == 404
        assert client.get(f"/evaporation/estimate/{properties[0]['id']}").status_code == 404
        own = client.post("/properties", json={"name": "[DEMO] Fazenda Horizonte", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG"}).json()
        assert client.get(f"/properties/{own['id']}/meteorology").json()["is_demo"] is False
        assert "history" not in client.get(f"/evaporation/estimate/{own['id']}").json()
    finally:
        for generator in sessions: generator.close()


def test_station_edit_and_delete_are_owned_and_preserve_reading_history(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    _, station = create_test_station(client)
    station_url = f"/level-stations/{station['id']}"
    updated = client.patch(station_url, json={"name": "Régua corrigida", "minimum_m": 0, "maximum_m": 3})
    assert updated.status_code == 200 and updated.json()["name"] == "Régua corrigida"
    assert client.patch(station_url, json={"name": "Régua", "minimum_m": 0, "maximum_m": 5}).status_code == 422
    reading = client.post(f"{station_url}/readings", json={"level_m": 1, "observed_at": "2026-03-01T12:00:00Z", "source": "manual"})
    assert reading.status_code == 201
    assert client.patch(station_url, json={"name": "Régua", "minimum_m": 0, "maximum_m": 4}).status_code == 409
    assert client.delete(station_url).status_code == 409
    assert len(client.get(f"{station_url}/readings").json()) == 1
    assert client.patch(station_url, json={"name": "Régua renomeada", "minimum_m": 0, "maximum_m": 3}).status_code == 200
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    assert client.patch(station_url, json={"name": "Outra conta", "minimum_m": 0, "maximum_m": 3}).status_code == 404
    assert client.delete(station_url).status_code == 404


def test_station_without_history_can_be_deleted(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    _, station = create_test_station(client)
    station_url = f"/level-stations/{station['id']}"
    assert client.delete(station_url).status_code == 204
    assert client.get(f"{station_url}/readings").status_code == 404


def test_station_with_image_history_cannot_be_deleted_or_recalibrated(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop, station = create_test_station(client)
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    db.add(LevelImageReview(property_id=prop["id"], station_id=station["id"], uploaded_by_id=1,
                            storage_key="fixture-image-station", original_name="fixture.png", content_type="image/png",
                            size_bytes=1, width_px=1, height_px=1, captured_at=datetime.now(timezone.utc),
                            status="inconclusive", method="fixture", analysis_details={}))
    db.commit(); db_gen.close()
    url = f"/level-stations/{station['id']}"
    assert client.delete(url).status_code == 409
    assert client.patch(url, json={"name": "Régua", "minimum_m": 0, "maximum_m": 3}).status_code == 409
    assert len(client.get(f"{url}/image-reviews").json()) == 1


def test_totalizer_reset_and_duplicate_integrity(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    _, station = create_test_station(client)
    meter = client.post("/hydrometers", json={"reservoir_id": station["reservoir_id"], "name": "Captação", "kind": "entrada"}).json()
    url = f"/hydrometers/{meter['id']}/readings"
    first = {"raw_totalizer_m3": 100, "observed_at": "2026-03-01T12:00:00Z", "external_id": "fixture-1", "source": "manual"}
    baseline = client.post(url, json=first)
    assert baseline.status_code == 201 and baseline.json()["volume_m3"] is None
    assert client.post(url, json=first).status_code == 200
    assert client.post(url, json={**first, "raw_totalizer_m3": 101}).status_code == 409
    reset = client.post(url, json={"raw_totalizer_m3": 2, "observed_at": "2026-03-02T12:00:00Z"})
    assert reset.status_code == 201 and reset.json()["volume_m3"] is None
    assert reset.json()["quality"].startswith("inconsistente")
    following = client.post(url, json={"raw_totalizer_m3": 5, "observed_at": "2026-03-03T12:00:00Z"})
    assert following.json()["volume_m3"] is None
    assert following.json()["quality"].startswith("pendente: totalizador anterior")
    assert client.post(url, json={"raw_totalizer_m3": 99, "observed_at": "2026-02-28T12:00:00Z"}).status_code == 409


def test_pending_image_alert_resolves_after_confirmation(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop, station = create_test_station(client)
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    review = LevelImageReview(property_id=prop["id"], station_id=station["id"], uploaded_by_id=1,
                              storage_key="fixture-image", original_name="fixture.png", content_type="image/png",
                              size_bytes=1, width_px=1, height_px=1, captured_at=datetime.now(timezone.utc),
                              status="inconclusive", method="fixture", analysis_details={})
    db.add(review)
    db.commit()
    review_id = review.id
    assert client.post(f"/alerts/{prop['id']}/evaluate").status_code == 200
    alerts = client.get(f"/alerts/{prop['id']}").json()
    alert = next(a for a in alerts if a["details"].get("review_id") == review_id)
    assert alert["status"] == "open"
    review.status = "confirmed"
    db.commit()
    assert client.post(f"/alerts/{prop['id']}/evaluate").status_code == 200
    alerts = client.get(f"/alerts/{prop['id']}").json()
    assert next(a for a in alerts if a["id"] == alert["id"])["status"] == "resolved"
    db_gen.close()


def upload_synthetic_ruler(client, station_id, payload=None, filename="fixture-synthetic.png", content_type="image/png"):
    return client.post(
        f"/level-stations/{station_id}/image-reviews",
        data={"captured_at": "2026-11-19T10:00:00-03:00"},
        files={"file": (filename, payload or synthetic_ruler_png(), content_type)},
    )


def test_ruler_image_review_manual_confirmation_and_correction_history(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main_module.settings, "media_storage_directory", str(tmp_path))
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    _, station = create_test_station(client)
    uploaded = upload_synthetic_ruler(client, station["id"], filename="fixture-synthetic.png")
    assert uploaded.status_code == 201
    review = uploaded.json()
    assert review["status"] == "inconclusive"
    assert review["suggested_level_m"] is None
    assert client.get(f"/level-stations/{station['id']}/readings").json() == []
    image_response = client.get(f"/level-image-reviews/{review['id']}/image")
    assert image_response.status_code == 200 and image_response.content.startswith(b"\x89PNG")
    assert client.post(f"/level-image-reviews/{review['id']}/confirm", json={"level_m": 0.7}).status_code == 409

    calibrated = client.post(f"/level-image-reviews/{review['id']}/calibrate", json={
        "reference_1": {"x": 60, "y": 50, "level_m": 1.000},
        "reference_2": {"x": 60, "y": 150, "level_m": 0.000},
        "waterline": {"x": 60, "y": 75},
    })
    assert calibrated.status_code == 200 and calibrated.json()["status"] == "pending_review"
    assert calibrated.json()["suggested_level_m"] == "0.750"
    confirmation = client.post(f"/level-image-reviews/{review['id']}/confirm", json={"level_m": 0.7})
    assert confirmation.status_code == 200
    assert confirmation.json()["reading"]["level_m"] == "0.700"
    assert confirmation.json()["reading"]["source"] == "imagem_revisada"
    assert confirmation.json()["reading"]["observed_at"].startswith("2026-11-19T13:00:00")

    reopened = client.post(f"/level-image-reviews/{review['id']}/suggestion", json={"level_m": 0.8})
    assert reopened.status_code == 200 and reopened.json()["status"] == "pending_review"
    readings = client.get(f"/level-stations/{station['id']}/readings").json()
    assert readings[0]["quality"].startswith("inconclusiva")
    corrected = client.post(f"/level-image-reviews/{review['id']}/confirm", json={"level_m": 0.8})
    assert corrected.status_code == 200 and corrected.json()["reading"]["level_m"] == "0.800"
    history = client.get(f"/level-image-reviews/{review['id']}/history").json()
    assert [entry["action"] for entry in history] == ["uploaded", "image_calibrated", "confirmed_or_corrected", "manual_suggestion", "confirmed_or_corrected"]


def test_ruler_image_upload_validation_and_property_isolation(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main_module.settings, "media_storage_directory", str(tmp_path))
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    _, station = create_test_station(client)
    assert upload_synthetic_ruler(client, station["id"], payload=b"not an image").status_code == 422
    assert client.get(f"/level-stations/{station['id']}/image-reviews").json() == []
    created = upload_synthetic_ruler(client, station["id"])
    assert created.status_code == 201
    review_id = created.json()["id"]

    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    assert client.get(f"/level-image-reviews/{review_id}").status_code == 404
    assert client.get(f"/level-image-reviews/{review_id}/image").status_code == 404
    assert client.get(f"/level-image-reviews/{review_id}/history").status_code == 404
    assert client.get(f"/level-stations/{station['id']}/image-reviews").status_code == 404


def test_alerts_persist_reopen_and_remain_isolated_by_property(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop = client.post("/properties", json={"name": "Sítio de A", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG"}).json()
    reservoir_response = client.post(
        f"/properties/{prop['id']}/reservoirs",
        json={
            "name": "Reservatório principal",
            "base_width_m": 10,
            "base_length_m": 12,
            "top_width_m": 12,
            "top_length_m": 14,
            "height_m": 4,
            "geometry_kml": "<kml><Document><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>-46,-17 -45.9,-17 -45.9,-16.9 -46,-16.9 -46,-17</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>",
        },
    )
    assert reservoir_response.status_code == 201
    meter_response = client.post("/hydrometers", json={"reservoir_id": reservoir_response.json()["id"], "name": "Captação", "kind": "entrada"})
    assert meter_response.status_code == 201

    first = client.post(f"/alerts/{prop['id']}/evaluate").json()
    assert first["created"] == 1
    alert = client.get(f"/alerts/{prop['id']}").json()[0]
    assert alert["rule"] == "Captação sem outorga associada"
    alert_id = alert["id"]

    resolved = client.post(f"/alerts/{alert_id}/resolve", json={"note": "Vínculo conferido pelo responsável."}).json()
    assert resolved["status"] == "resolved"
    assert resolved["resolution_history"][-1]["note"] == "Vínculo conferido pelo responsável."

    reopened = client.post(f"/alerts/{prop['id']}/evaluate").json()
    assert reopened["reopened"] == 1
    assert client.get(f"/alerts/{prop['id']}", params={"status": "open"}).json()[0]["status"] == "open"

    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    assert client.get(f"/alerts/{prop['id']}").status_code == 404
    assert client.post(f"/alerts/{alert_id}/resolve", json={}).status_code == 404


def test_monthly_demand_correction_keeps_previous_and_corrected_values(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop = client.post("/properties", json={"name": "Sítio de A", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG"}).json()
    demands = [
        {"month": month, "max_flow_m3_h": 10 if month == 1 else 0, "daily_hours": 2 if month == 1 else 0,
         "authorized_days": 3 if month == 1 else 0, "monthly_volume_m3": 60 if month == 1 else 0}
        for month in range(1, 13)
    ]
    created = client.post("/outorgas", json={
        "property_id": prop["id"], "name": "Outorga de teste", "permit_number": "TESTE-REV-01",
        "issued_on": "2025-01-01", "valid_from": "2025-01-01", "valid_until": "2027-12-31",
        "water_body": "Curso d'água sintético", "municipality": "Monte Carmelo", "coordinates_gms": "18°00' S, 47°00' O",
        "state": "MG", "irrigated_area_ha": 10, "demands": demands,
    })
    assert created.status_code == 201
    outorga_id = created.json()["id"]

    corrected = client.patch(f"/outorgas/{outorga_id}/monthly-demands/1", json={
        "max_flow_m3_h": 12, "daily_hours": 2, "authorized_days": 3, "monthly_volume_m3": 72,
    })
    assert corrected.status_code == 200
    history = client.get(f"/outorgas/{outorga_id}/monthly-demands/1/history").json()

    assert len(history) == 1
    assert Decimal(history[0]["previous_values"]["monthly_volume_m3"]) == Decimal("60")
    assert Decimal(history[0]["corrected_values"]["monthly_volume_m3"]) == Decimal("72")


def test_api_rejects_unclosed_property_kml_and_duplicate_monthly_demands(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    bad_kml = client.post("/properties", json={
        "name": "Geometria inválida", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG",
        "boundary_kml": "<kml><Polygon><outerBoundaryIs><LinearRing><coordinates>0,0 1,0 1,1 0,1</coordinates></LinearRing></outerBoundaryIs></Polygon></kml>",
    })
    assert bad_kml.status_code == 422

    prop = client.post("/properties", json={"name": "Sítio de A", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG"}).json()
    duplicate_months = [
        {"month": month, "max_flow_m3_h": 0, "daily_hours": 0, "authorized_days": 0, "monthly_volume_m3": 0}
        for month in (*range(1, 12), 11)
    ]
    response = client.post("/outorgas", json={
        "property_id": prop["id"], "name": "Outorga incompleta", "permit_number": "TESTE-12-MESES",
        "issued_on": "2025-01-01", "valid_from": "2025-01-01", "valid_until": "2027-12-31",
        "water_body": "Curso d'água sintético", "municipality": "Monte Carmelo", "coordinates_gms": "18°00' S, 47°00' O",
        "state": "MG", "irrigated_area_ha": 10, "demands": duplicate_months,
    })
    assert response.status_code == 422


def test_inmet_sync_is_idempotent_and_weather_isolated_by_property(client, monkeypatch):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop = client.post("/properties", json={"name": "Sítio meteorológico", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG"}).json()
    station_response = client.put(f"/properties/{prop['id']}/meteorology/station", json={"station_code": "FIXTURE-123", "name": "Estação de fixture", "city": "Monte Carmelo", "state": "MG"})
    assert station_response.status_code == 200
    station_id = station_response.json()["id"]
    monkeypatch.setattr(main_module.settings, "inmet_csv_schema_json", '{"encoding":"utf-8","delimiter":";","header_row":0,"station_code_column":"s","date_column":"d","time_column":"t","date_format":"%Y-%m-%d","time_format":"%H:%M","decimal_separator":",","variables":{"temperature_air":{"column":"a","unit":"fixture-unit"},"relative_humidity":{"column":"b","unit":"fixture-unit"},"wind_speed":{"column":"c","unit":"fixture-unit"},"wind_direction":{"column":"d2","unit":"fixture-unit"},"precipitation":{"column":"e","unit":"fixture-unit"}}}')

    class FixtureAdapter:
        def __init__(self, *args, **kwargs):
            pass

        def collect(self, year, station_code, collected_at=None):
            collected_at = collected_at or datetime.now(timezone.utc)
            return [ParsedObservation(station_code, "temperature_air", Decimal("22.5"), "fixture-unit", datetime(year, 6, 1, 12, tzinfo=timezone.utc), collected_at)]

    monkeypatch.setattr(main_module, "InmetAdapter", FixtureAdapter)
    first = client.post(f"/properties/{prop['id']}/meteorology/sync", json={"year": 2025})
    second = client.post(f"/properties/{prop['id']}/meteorology/sync", json={"year": 2025})
    assert first.status_code == 200 and first.json()["imported_count"] == 1
    assert second.status_code == 200 and second.json()["imported_count"] == 0
    weather = client.get(f"/properties/{prop['id']}/meteorology")
    assert weather.status_code == 200
    assert weather.json()["station"]["id"] == station_id
    assert len(weather.json()["recent_observations"]) == 1
    assert weather.json()["latest_observations"][0]["source"] == "INMET"
    assert weather.json()["latest_observations"][0]["quality"] == "raw_unvalidated"

    class InvalidArchiveAdapter:
        def __init__(self, *args, **kwargs):
            pass

        def collect(self, *args, **kwargs):
            raise InmetError("Fixture de resposta inválida; nenhum dado foi importado.")

    monkeypatch.setattr(main_module, "InmetAdapter", InvalidArchiveAdapter)
    failed = client.post(f"/properties/{prop['id']}/meteorology/sync", json={"year": 2025})
    retained = client.get(f"/properties/{prop['id']}/meteorology").json()
    assert failed.json()["status"] == "failed"
    assert len(retained["recent_observations"]) == 1
    assert retained["last_collection"]["status"] == "failed"

    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    assert client.get(f"/properties/{prop['id']}/meteorology").status_code == 404
    assert client.post(f"/properties/{prop['id']}/meteorology/sync", json={"year": 2025}).status_code == 404


def test_unconfigured_inmet_sync_is_recorded_as_failure_without_fake_observations(client, monkeypatch):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop = client.post("/properties", json={"name": "Sítio sem configuração", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG"}).json()
    client.put(f"/properties/{prop['id']}/meteorology/station", json={"station_code": "FIXTURE-EMPTY", "name": "Estação sem mapeamento"})
    monkeypatch.setattr(main_module.settings, "inmet_csv_schema_json", "")
    response = client.post(f"/properties/{prop['id']}/meteorology/sync", json={"year": 2025})
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "não configurada" in response.json()["message"]
    weather = client.get(f"/properties/{prop['id']}/meteorology").json()
    assert weather["recent_observations"] == []
    assert weather["last_collection"]["status"] == "failed"

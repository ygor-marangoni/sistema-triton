import os
import pytest
from io import BytesIO
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.session import get_db
from app.main import app, _cpf_fingerprint, _fernet, password_hash
from app.models import User, LevelImageReview, HydrometerReading, LevelReading
from app.integrations.inmet import InmetError, ParsedObservation
import app.main as main_module


@pytest.fixture
def client():
    postgres_test_url = os.environ.get("TRITON_TEST_DATABASE_URL")
    connection = None
    outer_transaction = None
    if postgres_test_url:
        parsed_url = make_url(postgres_test_url)
        assert parsed_url.get_backend_name() == "postgresql"
        assert parsed_url.database == "triton_integration_test"
        assert (parsed_url.host or "").casefold() in {"localhost", "127.0.0.1", "::1"}
        engine = create_engine(postgres_test_url, pool_pre_ping=True)
        connection = engine.connect()
        revision = connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
        assert revision == "0011_meter_coordinates"
        connection.commit()
        outer_transaction = connection.begin()
        test_session = sessionmaker(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
    else:
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
        for name, email in [
            ("Proprietário A", "a@example.com"),
            ("Proprietário B", "b@example.com"),
        ]:
            # Test identities must not collide with persistent synthetic demo data.
            while True:
                cpf = f"{uuid4().int % 10**11:011d}"
                if not db.query(User.id).filter_by(cpf_fingerprint=_cpf_fingerprint(cpf)).first():
                    break
            db.add(User(name=name, email=email,
                        password_hash=password_hash.hash("Senha-Segura-123!"),
                        cpf_encrypted=_fernet().encrypt(cpf.encode()).decode(),
                        cpf_fingerprint=_cpf_fingerprint(cpf), business_address="Endereço fictício", role="user"))
            db.flush()
        db.commit()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    if outer_transaction is not None:
        outer_transaction.rollback()
        connection.close()
    else:
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


def test_synthetic_level_history_period_and_suspect_reading(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop, station = create_test_station(client)
    url = f"/level-stations/{station['id']}/readings"
    for level, observed in [(1, "2026-01-01T12:00:00Z"), (5, "2026-01-02T12:00:00Z")]:
        result = client.post(url, json={"level_m": level, "observed_at": observed, "source": "simulada"})
        assert result.status_code == 201
    history = client.get(url, params={"start": "2026-01-02T00:00:00Z", "end": "2026-01-03T00:00:00Z"})
    assert len(history.json()) == 1
    assert history.json()[0]["quality"].startswith("inconsistente")
    assert client.get(url, params={"start": "2026-01-02T00:00:00"}).status_code == 422
    assert client.get(url, params={"start": "2026-01-03T00:00:00Z", "end": "2026-01-02T00:00:00Z"}).status_code == 422
    assert client.get(f"/dashboard/{prop['id']}").json()["latest_levels"][0]["volume_m3"] is None
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"})
    assert client.get(url).status_code == 404


def test_property_archive_preserves_history_and_can_be_restored(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop, station = create_test_station(client)
    reading_url = f"/level-stations/{station['id']}/readings"
    assert client.post(reading_url, json={"level_m": 1, "observed_at": "2026-01-01T12:00:00Z", "source": "manual"}).status_code == 201
    result = client.delete(f"/properties/{prop['id']}")
    assert result.status_code == 204
    assert client.get(f"/properties/{prop['id']}").status_code == 404
    assert client.get("/properties").json() == []
    archived = client.get("/properties", params={"include_archived": "true"}).json()
    assert len(archived) == 1 and archived[0]["is_archived"] is True

    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    revisions = db.query(main_module.RecordRevision).filter_by(record_type="property", record_id=prop["id"]).all()
    assert [revision.action for revision in revisions] == ["archive"]
    assert db.query(LevelReading).filter_by(station_id=station["id"]).count() == 1
    db_generator.close()

    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"})
    assert client.post(f"/properties/{prop['id']}/restore").status_code == 404
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"})
    assert client.post(f"/properties/{prop['id']}/restore").status_code == 200
    assert len(client.get(reading_url).json()) == 1
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    revisions = db.query(main_module.RecordRevision).filter_by(record_type="property", record_id=prop["id"]).all()
    assert [revision.action for revision in revisions] == ["archive", "restore"]
    db_generator.close()


def test_permit_document_collection_route_and_property_isolation(client):
    client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"})
    prop = client.post("/properties", json={"name": "Fazenda A", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG"}).json()
    route = f"/properties/{prop['id']}/permit-documents"
    assert client.get(route).status_code == 200
    assert client.get(route).json() == []
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"})
    assert client.get(route).status_code == 404


def test_cemig_tariff_catalog_and_import_are_scoped_and_idempotent(client, monkeypatch):
    client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"})
    prop = client.post("/properties", json={"name": "Fazenda A", "cep": "38500-000", "city": "Monte Carmelo", "state": "MG"}).json()
    row = {
        "source_row_id": 456,
        "distributor": "CEMIG-D",
        "tariff_class": "B1 · Residencial · Normal",
        "modality": "Convencional",
        "value_brl_kwh": "0.800000",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31",
        "source_reference": main_module.ANEEL_TARIFF_SOURCE_URL,
        "source_details": {"_id": 456, "VlrTUSD": 500, "VlrTE": 300},
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "price_scope": "TUSD + TE; antes de impostos e bandeiras tarifárias",
    }
    fixture_catalog = {"source": "fixture sintética", "source_reference": row["source_reference"], "fetched_at": row["fetched_at"], "records": [row]}
    monkeypatch.setattr(main_module, "fetch_cemig_application_rows", lambda: fixture_catalog)
    catalog = client.get(f"/energy/tariffs/aneel/cemig/catalog/{prop['id']}")
    assert catalog.status_code == 200 and catalog.json()["records"][0]["value_brl_kwh"] == "0.800000"
    payload = {"property_id": prop["id"], "source_row_id": 456}
    first = client.post("/energy/tariffs/aneel/cemig/import", json=payload)
    second = client.post("/energy/tariffs/aneel/cemig/import", json=payload)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["source"] == "aneel_cemig"
    assert first.json()["created_by_id"] == client.get('/auth/session').json()['user']['id']
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"})
    assert client.get(f"/energy/tariffs/aneel/cemig/catalog/{prop['id']}").status_code == 404


def test_totalizer_audit_reports_old_inconsistencies_without_changing_them(client):
    client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"})
    _, station = create_test_station(client)
    meter = client.post("/hydrometers", json={"reservoir_id": station["reservoir_id"], "name": "Medidor sintético", "kind": "saída"}).json()
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    for day, totalizer, volume in [(1, 100, 10), (2, 90, 4), (3, 100, 8)]:
        db.add(HydrometerReading(hydrometer_id=meter["id"], observed_at=datetime(2026, 1, day, tzinfo=timezone.utc), raw_totalizer_m3=totalizer, volume_m3=volume, source="simulada"))
    db.commit()
    db_generator.close()
    audit = client.get(f"/hydrometers/{meter['id']}/totalizer-audit")
    assert audit.status_code == 200
    assert audit.json()["totalizer_readings_checked"] == 3
    assert len(audit.json()["issues"]) == 3
    assert len(client.get(f"/hydrometers/{meter['id']}/readings").json()) == 3


def test_synthetic_curve_versions_no_extrapolation_and_isolation(client):
    client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"})
    prop, station = create_test_station(client)
    url = f"/reservoirs/{station['reservoir_id']}/stage-volume-curves"
    data = {"survey_date": "2026-01-01", "survey_source": "levantamento sintético", "survey_responsible": "Pessoa de teste", "level_unit": "m", "volume_unit": "m3", "points": [{"level": 0, "volume": 0}, {"level": 2, "volume": 100}]}
    result = client.post(url, json=data)
    assert result.status_code == 201
    curve_id = result.json()["id"]
    assert client.get(f"/stage-volume-curves/{curve_id}/volume", params={"level": 1, "at": "2026-06-01"}).status_code == 409
    approved = client.post(f"/stage-volume-curves/{curve_id}/approve", json={"valid_from": "2026-01-01", "valid_until": "2026-12-31"})
    assert approved.status_code == 200
    assert Decimal(str(client.get(f"/stage-volume-curves/{curve_id}/volume", params={"level": 1, "at": "2026-06-01"}).json()["volume"])) == 50
    assert client.get(f"/stage-volume-curves/{curve_id}/volume", params={"level": 3, "at": "2026-06-01"}).status_code == 422
    assert client.get(f"/stage-volume-curves/{curve_id}/volume", params={"level": 1, "at": "2027-01-01"}).status_code == 409
    assert client.post(url, json=data | {"points": [{"level": 2, "volume": 100}, {"level": 2, "volume": 110}]}).status_code == 422
    assert client.post(url, json=data).status_code == 201
    assert len(client.get(url).json()) == 2
    history = client.get(f"/properties/{prop['id']}/water-balance/monthly", params={"year": 2026}).json()["history"]
    assert len(history) == 12 and all(row["loss_residual_m3"] is None and row["coverage"] == "incompleta" for row in history)
    units = {"area_m2": "m2", "rain_mm": "mm", "inflow_m3": "m3", "outflow_m3": "m3", "other_outflow_m3": "m3", "initial_volume_m3": "m3", "final_volume_m3": "m3"}
    values = {"area_m2": 1000, "rain_mm": 10, "inflow_m3": 50, "outflow_m3": 20, "other_outflow_m3": 5, "initial_volume_m3": 100, "final_volume_m3": 110}
    start, end = "2025-01-01T03:00:00Z", "2025-02-01T03:00:00Z"
    inputs = {key: {"value": value, "unit": units[key], "source": "simulada", "reference": f"fixture-{key}", "period_start": start, "period_end": end, "coverage_complete": True,
        "observed_at": start if key == "initial_volume_m3" else end if key == "final_volume_m3" else None} for key, value in values.items()}
    balance_url = f"/reservoirs/{station['reservoir_id']}/water-balance/monthly"
    recorded = client.post(balance_url, json={"year": 2025, "month": 1, "inputs": inputs})
    assert recorded.status_code == 201 and Decimal(recorded.json()["loss_residual_m3"]) == 25
    jan = client.get(f"/properties/{prop['id']}/water-balance/monthly", params={"year": 2025}).json()["history"][0]
    assert jan["declared_assessment"]["result"]["origin"] == "simulada"
    assert jan["declared_assessment"]["inputs"]["rain_mm"]["reference"] == "fixture-rain_mm"
    client.post("/auth/logout"); client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"})
    assert client.get(url).status_code == 404
    assert client.get(f"/stage-volume-curves/{curve_id}/volume", params={"level": 1, "at": "2026-06-01"}).status_code == 404
    assert client.post(balance_url, json={"year": 2025, "month": 1, "inputs": inputs}).status_code == 404


def test_synthetic_permit_document_private_review_and_integrity(client, monkeypatch, tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    monkeypatch.setattr(main_module.settings, "media_storage_directory", str(tmp_path))
    client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"})
    prop, _ = create_test_station(client)
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
    buffer = BytesIO(); writer.write(buffer); payload = buffer.getvalue()
    url = f"/properties/{prop['id']}/permit-documents"
    assert client.post(url, files={"file": ("bad.pdf", b"not pdf", "application/pdf")}).status_code == 422
    created = client.post(url, files={"file": ("fixture.pdf", payload, "application/pdf")})
    assert created.status_code == 201
    doc = created.json(); assert doc["processing_status"] == "no_text_found"
    assert doc["extracted_fields"]["permit_number"]["value"] is None
    assert client.get(f"/permit-documents/{doc['id']}/file").content == payload
    reviewed = client.post(f"/permit-documents/{doc['id']}/review", json={"fields": {"permit_number": "SYNTHETIC"}, "approve": True})
    assert reviewed.json()["processing_status"] == "approved"
    assert reviewed.json()["extracted_fields"]["permit_number"]["value"] is None
    assert len(client.get(f"/permit-documents/{doc['id']}/history").json()) == 2
    next(tmp_path.glob("permit-*.pdf")).write_bytes(b"fixture adulterada")
    assert client.get(f"/permit-documents/{doc['id']}/file").status_code == 409
    text_writer = PdfWriter(); page = text_writer.add_blank_page(width=200, height=100)
    font = text_writer._add_object(DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')}))
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    stream = DecodedStreamObject(); stream.set_data(b'BT /F1 12 Tf 10 50 Td (SYNTHETIC-123) Tj ET')
    page[NameObject('/Contents')] = text_writer._add_object(stream)
    buffer = BytesIO(); text_writer.write(buffer)
    text_doc = client.post(url, files={"file": ("fixture-text.pdf", buffer.getvalue(), "application/pdf")}).json()
    assert "SYNTHETIC-123" in text_doc["extracted_text"]
    extract_url = f"/permit-documents/{text_doc['id']}/extract"
    assert client.post(extract_url, json={"field": "permit_number", "exact_text": "inventado"}).status_code == 422
    extracted = client.post(extract_url, json={"field": "permit_number", "exact_text": "SYNTHETIC-123"}).json()
    assert extracted["extracted_fields"]["permit_number"]["status"] == "pendente de revisão"
    assert extracted["reviewed_fields"] is None
    client.post("/auth/logout"); client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"})
    assert client.get(f"/permit-documents/{doc['id']}/file").status_code == 404
    assert client.post(f"/permit-documents/{doc['id']}/review", json={"fields": {}}).status_code == 404


def test_synthetic_meter_edit_state_and_normalized_telemetry(client):
    client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"})
    prop, station = create_test_station(client)
    meter = client.post("/hydrometers", json={"reservoir_id": station["reservoir_id"], "name": "Medidor teste", "kind": "saída"}).json()
    second = client.post("/hydrometers", json={"reservoir_id": station["reservoir_id"], "name": "Outro sintético", "kind": "saída"}).json()
    page = client.get("/hydrometers", params={"property_id": prop["id"], "skip": 1, "limit": 1}).json()
    assert len(page) == 1 and page[0]["id"] == second["id"]
    meter_url = f"/hydrometers/{meter['id']}"
    assert client.patch(meter_url, json={"name": "Medidor revisado", "rated_power_kw": "2"}).status_code == 200
    data = {"property_id": prop["id"], "component_id": meter["id"], "component_type": "hydrometer", "variable": "totalizer", "unit": "m3", "value": "20", "observed_at": "2026-01-02T12:00:00Z", "collected_at": "2026-01-03T12:00:00Z", "source": "test", "origin_id": "fixture-1"}
    assert client.post("/telemetry/normalized", json=data).status_code == 201
    assert client.post("/telemetry/normalized", json=data).status_code == 200
    assert client.post("/telemetry/normalized", json=data | {"value": "21"}).status_code == 409
    late = client.post("/telemetry/normalized", json=data | {"origin_id": "fixture-2", "observed_at": "2026-01-01T12:00:00Z"})
    assert late.status_code == 201 and late.json()["out_of_order"] is True
    assert client.post("/telemetry/normalized", json=data | {"source": "equipment"}).status_code == 403
    event = client.post(f"{meter_url}/totalizer-events", json={"event_type": "reinicio", "observed_at": "2026-01-03T12:00:00Z", "note": "registro sintético"})
    assert event.status_code == 201 and event.json()["user_id"] == client.get('/auth/session').json()['user']['id']
    assert len(client.get(f"{meter_url}/totalizer-events").json()) == 1
    assert client.patch(f"{meter_url}/state", json={"is_active": False}).status_code == 200
    assert client.post(f"{meter_url}/readings", json={"observed_at": "2026-01-01T12:00:00Z", "volume_m3": 1}).status_code == 409
    assert len(client.get(f"{meter_url}/history").json()) == 3
    assert client.delete(meter_url).status_code == 405
    client.post("/auth/logout"); client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"})
    assert client.get(f"{meter_url}/history").status_code == 404
    assert client.get(f"{meter_url}/totalizer-events").status_code == 404
    assert client.get(f"/properties/{prop['id']}/telemetry/normalized").status_code == 404


def test_permit_edit_state_and_link_history_protect_existing_readings(client):
    client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"})
    prop, station = create_test_station(client)
    demands = [{"month": month, "max_flow_m3_h": 0, "daily_hours": 0, "authorized_days": 0, "monthly_volume_m3": 0} for month in range(1, 13)]
    fields = {"name": "Outorga sintética", "permit_number": "FICTICIO", "issued_on": "2025-01-01", "valid_from": "2025-01-01", "valid_until": "2027-12-31", "water_body": "Rio fictício", "municipality": "Cidade teste", "coordinates_gms": "teste", "state": "MG", "irrigated_area_ha": 1}
    permit = client.post("/outorgas", json=fields | {"property_id": prop["id"], "demands": demands}).json()
    meter = client.post("/hydrometers", json={"reservoir_id": station["reservoir_id"], "name": "Entrada sintética", "kind": "entrada"}).json()
    link = client.post(f"/hydrometers/{meter['id']}/outorga-links", json={"outorga_id": permit["id"], "valid_from_at": "2025-01-01T03:00:00Z"})
    assert link.status_code == 201
    assert client.patch(f"/hydrometers/{meter['id']}/outorga/{permit['id']}").status_code == 409
    assert client.post(f"/hydrometers/{meter['id']}/readings", json={"volume_m3": 2, "interval_start_at": "2026-01-01T03:00:00Z", "observed_at": "2026-01-01T12:00:00Z"}).status_code == 201
    assert client.patch(f"/outorgas/{permit['id']}", json=fields | {"valid_until": "2028-12-31"}).status_code == 409
    assert client.patch(f"/outorgas/{permit['id']}", json=fields | {"name": "Outorga revisada"}).status_code == 200
    assert client.patch(f"/outorgas/{permit['id']}/state", json={"is_active": False}).status_code == 200
    assert len(client.get(f"/outorgas/{permit['id']}/history").json()) == 3
    assert len(client.get(f"/hydrometers/{meter['id']}/history").json()) == 2
    assert len(client.get(f"/hydrometers/{meter['id']}/outorga-links").json()) == 1
    assert client.delete(f"/outorgas/{permit['id']}").status_code == 405
    assert len(client.get(f"/hydrometers/{meter['id']}/readings").json()) == 1
    client.post("/auth/logout"); client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"})
    assert client.patch(f"/outorgas/{permit['id']}", json=fields).status_code == 404
    assert client.patch(f"/outorgas/{permit['id']}/state", json={"is_active": True}).status_code == 404
    assert client.get(f"/outorgas/{permit['id']}/history").status_code == 404


def test_annual_outorga_usage_preserves_gaps_and_user_isolation(client):
    assert client.post('/auth/login', json={'email': 'a@example.com', 'password': 'Senha-Segura-123!'}).status_code == 200
    prop, station = create_test_station(client)
    demands = [{'month': month, 'max_flow_m3_h': 2, 'daily_hours': 5, 'authorized_days': 10, 'monthly_volume_m3': 100} for month in range(1, 13)]
    fields = {'name': 'Outorga sintética', 'permit_number': 'FICTICIO-ANUAL', 'issued_on': '2025-01-01', 'valid_from': '2025-01-01', 'valid_until': '2027-12-31', 'water_body': 'Rio fictício', 'municipality': 'Cidade teste', 'coordinates_gms': 'teste', 'state': 'MG', 'irrigated_area_ha': 1}
    permit = client.post('/outorgas', json=fields | {'property_id': prop['id'], 'demands': demands}).json()
    response = client.get(f"/outorgas/{permit['id']}/usage/annual?year=2025")
    assert response.status_code == 200
    assert response.json()['coverage'] == 'incompleto'
    assert len(response.json()['months']) == 12
    assert all(month['measured_volume_m3'] is None for month in response.json()['months'])
    meter = client.post('/hydrometers', json={'reservoir_id': station['reservoir_id'], 'name': 'Entrada sintética', 'kind': 'entrada'}).json()
    assert client.post(f"/hydrometers/{meter['id']}/outorga-links", json={'outorga_id': permit['id'], 'valid_from_at': '2025-01-01T03:00:00Z'}).status_code == 201
    reading = client.post(f"/hydrometers/{meter['id']}/readings", json={'volume_m3': 12, 'interval_start_at': '2025-01-02T03:00:00Z', 'observed_at': '2025-01-02T12:00:00Z', 'source': 'manual'}).json()
    assert client.post(f"/hydrometer-readings/{reading['id']}/review", json={'approved': True, 'note': 'Fixture sintética revisada'}).status_code == 200
    months = client.get(f"/outorgas/{permit['id']}/usage/annual?year=2025").json()['months']
    assert Decimal(str(months[0]['measured_volume_m3'])) == Decimal(12)
    assert months[1]['measured_volume_m3'] is None
    assert months[0]['coverage'] == 'incompleto'
    assert client.get(f"/outorgas/{permit['id']}/usage/annual?year=2100").status_code == 422
    client.post('/auth/logout')
    assert client.post('/auth/login', json={'email': 'b@example.com', 'password': 'Senha-Segura-123!'}).status_code == 200
    assert client.get(f"/outorgas/{permit['id']}/usage/annual?year=2025").status_code == 404


def test_temporal_outorga_link_switch_keeps_boundary_reading_unassigned_and_isolates_users(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop, station = create_test_station(client)
    demands = [{"month": month, "max_flow_m3_h": 0, "daily_hours": 0, "authorized_days": 0, "monthly_volume_m3": 0} for month in range(1, 13)]
    fields = {"name": "Outorga temporal sintética", "permit_number": "FICTICIO-2", "issued_on": "2025-01-01", "valid_from": "2025-01-01", "valid_until": "2027-12-31", "water_body": "Rio teste", "municipality": "Cidade teste", "coordinates_gms": "teste", "state": "MG", "irrigated_area_ha": 1}
    permit = client.post("/outorgas", json=fields | {"property_id": prop["id"], "demands": demands}).json()
    meter = client.post("/hydrometers", json={"reservoir_id": station["reservoir_id"], "name": "Hidrômetro temporal", "kind": "entrada"}).json()
    links_url = f"/hydrometers/{meter['id']}/outorga-links"
    first = client.post(links_url, json={"outorga_id": permit["id"], "valid_from_at": "2025-01-01T03:00:00Z"})
    assert first.status_code == 201
    assert client.post(links_url, json={"outorga_id": permit["id"], "valid_from_at": "2025-12-01T03:00:00Z"}).status_code == 409
    boundary = "2026-01-01T03:00:00Z"
    assert client.post(f"/hydrometer-outorga-links/{first.json()['id']}/close", json={"valid_until_at": boundary}).status_code == 200
    second = client.post(links_url, json={"outorga_id": permit["id"], "valid_from_at": boundary})
    assert second.status_code == 201
    crossing = client.post(f"/hydrometers/{meter['id']}/readings", json={"volume_m3": 3, "interval_start_at": "2026-01-01T02:30:00Z", "observed_at": "2026-01-01T03:30:00Z"})
    assert crossing.status_code == 201
    assert crossing.json()["quality"].startswith("pendente: vínculo histórico")
    within = client.post(f"/hydrometers/{meter['id']}/readings", json={"volume_m3": 4, "interval_start_at": "2026-01-01T03:30:00Z", "observed_at": "2026-01-01T04:30:00Z"})
    assert within.status_code == 201 and within.json()["quality"] == "não revisada"
    assert len(client.get(f"/hydrometers/{meter['id']}/history").json()) >= 3
    links = client.get(links_url)
    assert links.status_code == 200 and len(links.json()) == 2
    assert client.post(f"/hydrometer-outorga-links/{second.json()['id']}/close", json={"valid_until_at": "2027-01-01T03:00:00Z"}).status_code == 200
    assert client.patch(f"/outorgas/{permit['id']}", json=fields | {"valid_until": "2028-12-31"}).status_code == 409
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    assert client.get(links_url).status_code == 404
    assert client.post(f"/hydrometer-outorga-links/{first.json()['id']}/close", json={"valid_until_at": "2027-01-01T03:00:00Z"}).status_code == 404


def test_balance_source_evidence_is_reviewable_paginated_and_property_scoped(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop, station = create_test_station(client)
    weather = client.put(f"/properties/{prop['id']}/meteorology/station", json={
        "station_code": "FIXTURE-CHUVA", "name": "Estação sintética",
    })
    assert weather.status_code == 200
    reservoir_id = station["reservoir_id"]
    rainfall = client.post(f"/properties/{prop['id']}/rainfall-intervals", json={
        "station_id": weather.json()["id"], "value_mm": "12", "period_start_at": "2025-01-01T03:00:00Z",
        "period_end_at": "2025-02-01T03:00:00Z", "source": "manual", "reference": "fixture sintética",
    })
    assert rainfall.status_code == 201 and rainfall.json()["quality"] == "pendente de revisão"
    outflow = client.post(f"/reservoirs/{reservoir_id}/water-balance/other-outflows", json={
        "value_m3": "4", "period_start_at": "2025-01-01T03:00:00Z", "period_end_at": "2025-02-01T03:00:00Z",
        "source": "documento", "reference": "fixture sintética",
    })
    assert outflow.status_code == 201
    level = client.post(f"/level-stations/{station['id']}/readings", json={
        "level_m": "1.5", "observed_at": "2025-01-01T03:00:00Z", "source": "manual",
    })
    assert level.status_code == 201 and level.json()["quality"] == "não revisada"
    listed = client.get(f"/reservoirs/{reservoir_id}/water-balance/source-evidence?year=2025&month=1&limit=1")
    assert listed.status_code == 200
    assert listed.json()["rainfall"]["items"][0]["id"] == rainfall.json()["id"]
    assert listed.json()["other_outflows"]["items"][0]["id"] == outflow.json()["id"]
    assert listed.json()["levels"]["items"][0]["id"] == level.json()["id"]
    reviewed_rain = client.post(f"/meteorological-observations/{rainfall.json()['id']}/review", json={"approved": True, "note": "intervalo confirmado no fixture sintético"})
    reviewed_outflow = client.post(f"/water-balance/other-outflows/{outflow.json()['id']}/review", json={"approved": True, "note": "documento de teste conferido"})
    reviewed_level = client.post(f"/level-readings/{level.json()['id']}/review", json={"approved": True, "note": "leitura de teste conferida"})
    assert reviewed_rain.status_code == 200 and reviewed_rain.json()["quality"] == "validada"
    assert reviewed_outflow.status_code == 200 and reviewed_outflow.json()["quality"] == "validada"
    assert reviewed_level.status_code == 200 and reviewed_level.json()["quality"] == "validada"
    automatic = client.post(f"/reservoirs/{reservoir_id}/water-balance/monthly/automatic?year=2025&month=1")
    assert automatic.status_code == 201
    assert automatic.json()["loss_residual_m3"] is None
    assert automatic.json()["coverage"] == "incompleta"
    monthly = client.get(f"/properties/{prop['id']}/water-balance/monthly?year=2025")
    assert monthly.status_code == 200
    january = next(item for item in monthly.json()["history"] if item["reservoir_id"] == reservoir_id and item["month"] == 1)
    assert january["status"] == "dados insuficientes"
    assert "uma única curva cota-volume aprovada" in " ".join(january["missing"])
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    assert client.get(f"/reservoirs/{reservoir_id}/water-balance/source-evidence?year=2025&month=1").status_code == 404


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


def test_outdated_schema_returns_cors_and_safe_error():
    class MissingColumn(Exception):
        sqlstate = "42703"

    class BrokenDatabase:
        def scalars(self, statement):
            raise ProgrammingError("SELECT secret", {}, MissingColumn("private detail"))

    app.dependency_overrides[get_db] = lambda: BrokenDatabase()
    app.dependency_overrides[main_module.cookie_current_user] = lambda: User(id=1, role="user")
    try:
        origin = main_module.settings.origins[0]
        with TestClient(app) as test_client:
            response = test_client.get("/properties", headers={"Origin": origin})
        assert response.status_code == 503
        assert response.headers["access-control-allow-origin"] == origin
        assert "estrutura do banco" in response.json()["detail"]
        assert "secret" not in response.text and "private detail" not in response.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(main_module.cookie_current_user, None)


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
    if os.environ.get("TRITON_TEST_DATABASE_URL"):
        check_session = app.dependency_overrides[get_db]()
        try:
            if next(check_session).query(User.id).filter_by(email=demo.DEMO_EMAIL).first():
                pytest.skip("Conta demo persistente já existe; preservada para a apresentação.")
        finally:
            check_session.close()
    reserved = client.post('/auth/register', json={"name": "Conta comum", "email": "demo@example.com", "cpf": "11144477735", "business_address": "Endereço de teste", "password": "Senha-Segura-123!"})
    assert reserved.status_code == 409
    sessions = []
    def session_factory():
        generator = app.dependency_overrides[get_db]()
        sessions.append(generator)
        return next(generator)
    monkeypatch.setattr(demo, "SessionLocal", session_factory)
    if not os.environ.get("TRITON_TEST_DATABASE_URL"):
        # SQLite exercises the synthetic data only; the PostgreSQL run checks the real guard.
        monkeypatch.setattr(demo, "ensure_demo_database", lambda db, settings: None)
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
        assert comparison["coverage"] == "incompleto"
        assert comparison["measured_volume_m3"] is None
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
        assert client.get(f"/evaporation/estimate/{own['id']}").json()["history"] == []
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


def test_legacy_image_is_preserved_without_new_image_alerts(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop, station = create_test_station(client)
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    user_id = client.get("/auth/session").json()["user"]["id"]
    review = LevelImageReview(property_id=prop["id"], station_id=station["id"], uploaded_by_id=user_id,
                              storage_key="fixture-image", original_name="fixture.png", content_type="image/png",
                              size_bytes=1, width_px=1, height_px=1, captured_at=datetime.now(timezone.utc),
                              status="inconclusive", method="fixture", analysis_details={})
    db.add(review); db.commit(); review_id = review.id; db_gen.close()
    assert client.post(f"/alerts/{prop['id']}/evaluate").status_code == 200
    alerts = client.get(f"/alerts/{prop['id']}").json()
    assert not any(a["details"].get("review_id") == review_id for a in alerts)
    assert client.get(f"/level-image-reviews/{review_id}").status_code == 200


def upload_synthetic_ruler(client, station_id, payload=None, filename="fixture-synthetic.png", content_type="image/png"):
    return client.post(
        f"/level-stations/{station_id}/image-reviews",
        data={"captured_at": "2026-11-19T10:00:00-03:00"},
        files={"file": (filename, payload or synthetic_ruler_png(), content_type)},
    )


def test_assisted_image_reading_is_retired_and_manual_level_remains_available(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    _, station = create_test_station(client)
    assert upload_synthetic_ruler(client, station["id"]).status_code == 410
    assert client.post("/level-image-reviews/1/suggestion", json={"level_m": 0.7}).status_code == 410
    assert client.post("/level-image-reviews/1/confirm", json={"level_m": 0.7}).status_code == 410
    result = client.post(f"/level-stations/{station['id']}/readings", json={"level_m": 0.7, "observed_at": "2026-11-19T13:00:00Z", "source": "manual"})
    assert result.status_code == 201
    assert result.json()["source"] == "manual"


def test_meter_coordinates_are_paired_audited_and_isolated(client):
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    prop, station = create_test_station(client)
    values = {"reservoir_id": station["reservoir_id"], "name": "Hidrômetro sintético", "kind": "entrada"}
    assert client.post("/hydrometers", json={**values, "latitude": -18.123456}).status_code == 422
    created = client.post("/hydrometers", json={**values, "latitude": -18.123456, "longitude": -47.123456})
    assert created.status_code == 201
    meter = created.json()
    assert float(meter["latitude"]) == -18.123456
    assert client.patch(f"/hydrometers/{meter['id']}", json={"name": "Atualizado", "latitude": -19}).status_code == 422
    updated = client.patch(f"/hydrometers/{meter['id']}", json={"name": "Atualizado", "latitude": -19.0, "longitude": -48.0})
    assert updated.status_code == 200 and float(updated.json()["longitude"]) == -48.0
    history = client.get(f"/hydrometers/{meter['id']}/history").json()
    assert any(entry["new_values"].get("latitude") is not None for entry in history)
    assert client.get(f"/properties/{prop['id']}/map-geometry").status_code == 200
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "b@example.com", "password": "Senha-Segura-123!"}).status_code == 200
    assert client.get(f"/properties/{prop['id']}/map-geometry").status_code == 404
    assert client.patch(f"/hydrometers/{meter['id']}", json={"name": "Não autorizado", "latitude": 0, "longitude": 0}).status_code == 404


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
    monkeypatch.setattr(main_module.settings, "inmet_csv_schema_json", '{"encoding":"utf-8","delimiter":";","header_row":0,"source_timezone":"UTC","station_code_column":"s","date_column":"d","time_column":"t","date_format":"%Y-%m-%d","time_format":"%H:%M","decimal_separator":",","variables":{"temperature_air":{"column":"a","unit":"fixture-unit"},"relative_humidity":{"column":"b","unit":"fixture-unit"},"wind_speed":{"column":"c","unit":"fixture-unit"},"wind_direction":{"column":"d2","unit":"fixture-unit"},"precipitation":{"column":"e","unit":"fixture-unit"}}}')

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
    assert client.post(f"/alerts/{prop['id']}/evaluate").status_code == 200
    assert client.post(f"/alerts/{prop['id']}/evaluate").status_code == 200
    alerts = client.get(f"/alerts/{prop['id']}").json()
    failures = [item for item in alerts if item["rule"] == "Falha na coleta"]
    assert len(failures) == 1 and failures[0]["status"] == "open"
    evaluations = client.get(f"/properties/{prop['id']}/alert-evaluations").json()
    assert len(evaluations) == 2 and evaluations[0]["evidence"]["latest_collection"]["status"] == "failed"
    monkeypatch.setattr(main_module, "InmetAdapter", FixtureAdapter)
    assert client.post(f"/properties/{prop['id']}/meteorology/sync", json={"year": 2025}).json()["status"] == "success"
    client.post(f"/alerts/{prop['id']}/evaluate")
    assert next(item for item in client.get(f"/alerts/{prop['id']}").json() if item["id"] == failures[0]["id"])["status"] == "resolved"

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

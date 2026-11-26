"""Guard, seed and verify the isolated PostgreSQL integration-test database."""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


DATABASE_NAME = "triton_integration_test"
EXPECTED_HEAD = "0011_meter_coordinates"
ALLOWED_REVISIONS = {
    None,
    "0006_nullable_interval_volume",
    "0007_integration_history",
    "0008_proven_intervals",
    "0009_property_archive_tariff_source",
    "0010_period_constraints",
    EXPECTED_HEAD,
}
MARKER_EMAIL = "synthetic-legacy-20261125@example.invalid"
MARKER_READING = "synthetic-legacy-reading-20261125"
MARKER_FINGERPRINT = hashlib.sha256(MARKER_EMAIL.encode("utf-8")).hexdigest()


class VerificationError(Exception):
    """Safe, locally generated schema verification details."""


def _engine():
    raw_url = os.environ.get("TRITON_TEST_DATABASE_URL")
    if not raw_url:
        raise RuntimeError("TRITON_TEST_DATABASE_URL não foi configurada pelo script PowerShell.")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("A validação exige PostgreSQL; outro backend foi recusado.")
    if (url.database or "").casefold() == "triton":
        raise RuntimeError("Banco `triton` recusado por segurança.")
    if url.database != DATABASE_NAME:
        raise RuntimeError(f"Use somente o banco isolado `{DATABASE_NAME}`.")
    if (url.host or "").casefold() not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("A validação aceita somente PostgreSQL local em loopback.")
    return create_engine(url, pool_pre_ping=True)


def _state(connection):
    exists = connection.execute(
        text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
    ).scalar_one()
    if not exists:
        existing_tables = connection.execute(text("""
            SELECT tablename
            FROM pg_catalog.pg_tables
            WHERE schemaname = 'public'
              AND tablename NOT LIKE 'pg_%'
            ORDER BY tablename
        """)).scalars().all()
        if existing_tables:
            raise RuntimeError("Banco sem alembic_version, mas com tabelas existentes; inspeção manual necessária.")
        return None
    rows = connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars().all()
    if len(rows) != 1:
        raise RuntimeError("alembic_version ausente ou ambígua; inspeção manual necessária.")
    revision = rows[0]
    if revision not in ALLOWED_REVISIONS:
        raise RuntimeError(f"Revisão inesperada ({revision}); nenhuma migração foi iniciada.")
    return revision


def _identity(connection):
    database, user = connection.execute(
        text("SELECT current_database(), current_user")
    ).one()
    if database != DATABASE_NAME:
        raise RuntimeError("O servidor resolveu a conexão para um banco diferente do permitido.")
    return database, user


def _seed_legacy(connection):
    existing_user = connection.execute(
        text("SELECT id FROM users WHERE email = :email"), {"email": MARKER_EMAIL}
    ).scalar_one_or_none()
    existing_reading = connection.execute(
        text("SELECT id, volume_m3 FROM hydrometer_readings WHERE external_id = :external_id"),
        {"external_id": MARKER_READING},
    ).one_or_none()
    if existing_user is not None or existing_reading is not None:
        if existing_user is None or existing_reading is None:
            raise RuntimeError("Seed sintético incompleto; não alterei nem removi os registros existentes.")
        reading_id, volume = existing_reading
        if str(volume) != "3.250":
            raise RuntimeError("Leitura sintética existente diverge; preservada sem correção automática.")
        return {"user_id": existing_user, "reading_id": reading_id, "created": False}

    now = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    user_id = connection.execute(
        text("""
            INSERT INTO users
                (name, email, password_hash, cpf_encrypted, cpf_fingerprint,
                 business_address, role, is_active, created_at, updated_at)
            VALUES
                ('Fixture sintética de migração', :email, 'not-a-login-hash',
                 'synthetic-only', :fingerprint, 'fixture sintética', 'user', TRUE, :now, :now)
            RETURNING id
        """), {"email": MARKER_EMAIL, "fingerprint": MARKER_FINGERPRINT, "now": now}
    ).scalar_one()
    property_id = connection.execute(
        text("""
            INSERT INTO properties
                (name, cep, city, state, owner_id, created_at, updated_at)
            VALUES ('Propriedade sintética para migração', '00000-000', 'Fixture', 'MG', :owner, :now, :now)
            RETURNING id
        """), {"owner": user_id, "now": now}
    ).scalar_one()
    reservoir_id = connection.execute(
        text("""
            INSERT INTO reservoirs
                (property_id, name, base_width_m, base_length_m, top_width_m, top_length_m,
                 height_m, geometry_kml, geometry_assumption, created_at, updated_at)
            VALUES
                (:property_id, 'Reservatório sintético', 10, 10, 12, 12, 2,
                 '<kml><!-- fixture sintética --></kml>', 'fixture_sintetica', :now, :now)
            RETURNING id
        """), {"property_id": property_id, "now": now}
    ).scalar_one()
    outorga_id = connection.execute(
        text("""
            INSERT INTO outorgas
                (property_id, name, permit_number, issued_on, valid_from, valid_until,
                 water_body, municipality, coordinates_gms, state, irrigated_area_ha,
                 is_demo, created_at, updated_at)
            VALUES
                (:property_id, 'Outorga sintética', 'SYNTHETIC-ONLY', DATE '2025-01-01',
                 DATE '2025-01-01', DATE '2027-12-31', 'corpo hídrico sintético',
                 'Fixture', 'não informado', 'MG', 1, TRUE, :now, :now)
            RETURNING id
        """), {"property_id": property_id, "now": now}
    ).scalar_one()
    hydrometer_id = connection.execute(
        text("""
            INSERT INTO hydrometers
                (reservoir_id, outorga_id, name, kind, is_demo, created_at, updated_at)
            VALUES (:reservoir_id, :outorga_id, 'Hidrômetro sintético', 'entrada', TRUE, :now, :now)
            RETURNING id
        """), {"reservoir_id": reservoir_id, "outorga_id": outorga_id, "now": now}
    ).scalar_one()
    reading_id = connection.execute(
        text("""
            INSERT INTO hydrometer_readings
                (hydrometer_id, flow_m3_h, volume_m3, observed_at, source, unit,
                 external_id, quality, raw_totalizer_m3, created_at, updated_at)
            VALUES
                (:hydrometer_id, NULL, 3.250, :now, 'manual', 'm3', :external_id,
                 'fixture sintética de migração', 103.250, :now, :now)
            RETURNING id
        """), {"hydrometer_id": hydrometer_id, "external_id": MARKER_READING, "now": now}
    ).scalar_one()
    return {
        "user_id": user_id,
        "property_id": property_id,
        "reservoir_id": reservoir_id,
        "outorga_id": outorga_id,
        "hydrometer_id": hydrometer_id,
        "reading_id": reading_id,
        "created": True,
    }


def _verify(connection):
    revision = _state(connection)
    if revision != EXPECTED_HEAD:
        raise RuntimeError(f"Revisão final inesperada: {revision!r}.")
    required_columns = {
        "properties": {"is_archived", "archived_at"},
        "outorgas": {"is_active"},
        "hydrometers": {"is_active", "latitude", "longitude"},
        "hydrometer_readings": {"interval_start_at"},
        "stage_volume_curves": {"valid_from", "valid_until", "is_approved"},
        "energy_tariffs": {"source_reference", "source_details", "created_by_id"},
    }
    from sqlalchemy import inspect

    inspector = inspect(connection)
    tables = set(inspector.get_table_names(schema="public"))
    issues = []
    for table, columns in required_columns.items():
        if table not in tables:
            issues.append(f"Tabela esperada ausente: {table}.")
            continue
        actual = {column["name"] for column in inspector.get_columns(table, schema="public")}
        if not columns.issubset(actual):
            issues.append(f"Colunas esperadas ausentes em {table}: {sorted(columns - actual)}.")
    required_tables = {
        "record_revisions", "stage_volume_curves", "alert_evaluations", "normalized_telemetry",
        "monthly_balances", "totalizer_events", "hydrometer_outorga_links", "balance_flow_evidence",
    }
    if not required_tables.issubset(tables):
        issues.append(f"Tabelas de integração ausentes: {sorted(required_tables - tables)}.")
    required_indexes = {
        "record_revisions": {"ix_record_revisions_property_id"},
        "stage_volume_curves": {"ix_stage_volume_curves_reservoir_id"},
        "hydrometer_outorga_links": {
            "ix_hydrometer_outorga_links_property_id", "ix_hydrometer_outorga_links_hydrometer_id",
            "ix_hydrometer_outorga_links_outorga_id", "ix_hydrometer_outorga_link_period",
        },
        "balance_flow_evidence": {"ix_balance_flow_evidence_reservoir_id", "ix_balance_flow_reservoir_period"},
        "energy_tariffs": {"ix_energy_tariffs_created_by_id"},
    }
    for table, expected in required_indexes.items():
        if table not in tables:
            continue
        actual = {index["name"] for index in inspector.get_indexes(table, schema="public")}
        if not expected.issubset(actual):
            issues.append(f"Índices esperados ausentes em {table}: {sorted(expected - actual)}.")
    required_checks = {
        "stage_volume_curves": {"ck_stage_curve_validity", "ck_stage_curve_approval"},
        "hydrometer_outorga_links": {"ck_hydrometer_outorga_link_period"},
        "balance_flow_evidence": {"ck_balance_flow_evidence_value", "ck_balance_flow_evidence_period"},
    }
    for table, expected in required_checks.items():
        if table not in tables:
            continue
        actual = {constraint.get("name") for constraint in inspector.get_check_constraints(table, schema="public")}
        if not expected.issubset(actual):
            issues.append(f"Restrições esperadas ausentes em {table}: {sorted(expected - actual)}.")
    expected_foreign_keys = {
        "hydrometer_outorga_links": {
            ("property_id", "properties"), ("hydrometer_id", "hydrometers"), ("outorga_id", "outorgas"),
        },
        "balance_flow_evidence": {("reservoir_id", "reservoirs"), ("created_by_id", "users")},
    }
    for table, expected in expected_foreign_keys.items():
        if table not in tables:
            continue
        actual = {
            (foreign_key["constrained_columns"][0], foreign_key["referred_table"])
            for foreign_key in inspector.get_foreign_keys(table, schema="public")
            if len(foreign_key["constrained_columns"]) == 1
        }
        if not expected.issubset(actual):
            issues.append(f"Chaves estrangeiras esperadas ausentes em {table}: {sorted(expected - actual)}.")
    if issues:
        raise VerificationError("\n".join(issues))
    user_id = connection.execute(
        text("SELECT id FROM users WHERE email = :email"), {"email": MARKER_EMAIL}
    ).scalar_one_or_none()
    preserved = connection.execute(
        text("""
            SELECT r.id, r.volume_m3, r.raw_totalizer_m3, h.outorga_id, o.property_id, p.owner_id
            FROM hydrometer_readings r
            JOIN hydrometers h ON h.id = r.hydrometer_id
            JOIN outorgas o ON o.id = h.outorga_id
            JOIN properties p ON p.id = o.property_id
            WHERE r.external_id = :external_id
        """), {"external_id": MARKER_READING}
    ).one_or_none()
    if user_id is None or preserved is None or str(preserved.volume_m3) != "3.250":
        raise RuntimeError("Os registros sintéticos legados não foram preservados integralmente.")
    if preserved.owner_id != user_id:
        raise RuntimeError("Vínculo sintético legado inconsistente após migração.")
    return {"revision": revision, "tables": len(tables), "legacy_reading_id": preserved.id}


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    engine = _engine()
    try:
        with engine.begin() as connection:
            database, user = _identity(connection)
            if action == "state":
                print(_state(connection) or "empty")
            elif action == "seed":
                revision = _state(connection)
                if revision not in ALLOWED_REVISIONS - {None}:
                    raise RuntimeError("Banco precisa estar numa revisão conhecida entre 0006 e 0011.")
                result = _seed_legacy(connection)
                print(f"Seed sintético {'criado' if result.get('created') else 'já presente'}; banco={database}; role={user}.")
            elif action == "verify":
                result = _verify(connection)
                print(f"PostgreSQL verificado; revisão={result['revision']}; tabelas={result['tables']}; leitura legada preservada.")
            else:
                raise RuntimeError("Uso: postgres_test_support.py state|seed|verify")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except VerificationError as exc:
        print(f"Verificação do esquema: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except Exception as exc:  # Do not print URLs or driver details that may contain connection data.
        print(f"Validação PostgreSQL interrompida: {type(exc).__name__}. Detalhe omitido; banco não foi limpo.", file=sys.stderr)
        raise SystemExit(2)

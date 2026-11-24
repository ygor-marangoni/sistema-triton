"""Carrega dados sintéticos somente quando chamado explicitamente."""
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings  # noqa: E402,F401
from app.db.session import SessionLocal  # noqa: E402
from app.main import _cpf_fingerprint, _fernet, password_hash  # noqa: E402
from app.models import Alert, EnergyTariff, Hydrometer, HydrometerReading, LevelReading, LevelStation, MonthlyDemand, Outorga, Property, Reservoir, User  # noqa: E402

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "Triton-Demo-2026!"
KML = """<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>-47.5010,-18.7210 -47.5000,-18.7210 -47.5000,-18.7200 -47.5010,-18.7200 -47.5010,-18.7210</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>"""


def main():
    from app.core.config import get_settings
    if get_settings().app_env.lower() not in {"development", "local", "test"}:
        raise SystemExit("A carga de demonstração só é permitida em ambiente local/de desenvolvimento.")
    db = SessionLocal()
    try:
        if db.query(User).filter_by(email=DEMO_EMAIL).first():
            print(f"Conta de demonstração já existe ({DEMO_EMAIL}); nada foi alterado.")
            return
        # CPF usado somente pela conta sintética, sem alterar usuários existentes.
        cpf = next((value for value in ("12345678909", "11144477735", "52998224725") if not db.query(User.id).filter_by(cpf_fingerprint=_cpf_fingerprint(value)).first()), None)
        if not cpf:
            raise SystemExit("Não foi possível escolher um CPF de teste disponível; nenhum dado foi alterado.")
        this_year = datetime.now(timezone.utc).year
        owner = User(name="Usuário Demonstração", email=DEMO_EMAIL, password_hash=password_hash.hash(DEMO_PASSWORD),
                     cpf_encrypted=_fernet().encrypt(cpf.encode()).decode(), cpf_fingerprint=_cpf_fingerprint(cpf),
                     business_address="Endereço fictício para demonstração", role="user")
        prop = Property(name="[DEMO] Fazenda Horizonte", cep="38500-000", city="Monte Carmelo", state="MG", latitude=Decimal("-18.720500"), longitude=Decimal("-47.499500"), owner=owner)
        res = Reservoir(name="[DEMO] Reservatório principal", base_width_m=Decimal("40"), base_length_m=Decimal("60"), top_width_m=Decimal("50"), top_length_m=Decimal("70"), height_m=Decimal("8"), geometry_kml=KML)
        res.property = prop
        permit = Outorga(property=prop, name="Outorga demonstrativa", permit_number="DEMO-01", issued_on=date(this_year, 1, 1), valid_from=date(this_year, 1, 1), valid_until=date(this_year + 1, 12, 31), water_body="Córrego fictício", municipality="Monte Carmelo", coordinates_gms="18°43' S, 47°29' O", state="MG", irrigated_area_ha=Decimal("12"), is_demo=True)
        permit.demands = [MonthlyDemand(month=m, max_flow_m3_h=Decimal("12"), daily_hours=Decimal("5"), authorized_days=15, monthly_volume_m3=Decimal("900")) for m in range(1, 13)]
        meter = Hydrometer(reservoir=res, outorga=permit, name="Captação demonstrativa", kind="entrada", rated_power_kw=Decimal("7.500"), is_demo=True)
        station = LevelStation(reservoir=res, name="Régua demonstrativa", minimum_m=Decimal("0"), maximum_m=Decimal("8"))
        now = datetime.now(timezone.utc).replace(microsecond=0)
        station.readings = [LevelReading(level_m=Decimal("4.250") + Decimal(i) / 100, observed_at=now - timedelta(days=6-i), source="simulada", quality="demonstração") for i in range(7)]
        meter.readings = [HydrometerReading(flow_m3_h=Decimal("10"), volume_m3=Decimal("20") + Decimal(i), observed_at=now - timedelta(days=6-i), source="simulada", quality="demonstração") for i in range(7)]
        db.add(owner)
        db.flush()
        db.add(EnergyTariff(property_id=prop.id, distributor="Tarifa demonstrativa", tariff_class="Rural (exemplo)", modality="Convencional", value_brl_kwh=Decimal("0.650000"), valid_from=date(this_year, 1, 1), source="manual"))
        db.add(Alert(property_id=prop.id, fingerprint=f"demo:exemplo:{prop.id}", origin="demonstração", rule="Alerta de demonstração", details={"message": "Registro fictício para testar a visualização de alertas."}, occurred_at=now, severity="warning", status="open"))
        db.commit()
        print("Dados sintéticos criados. Acesso local:")
        print(f"  e-mail: {DEMO_EMAIL}\n  senha: {DEMO_PASSWORD}")
        print("Tarifa fictícia para demonstração; não representa tarifa vigente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

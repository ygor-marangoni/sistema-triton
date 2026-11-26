from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.integrations.aneel_tariffs import API_URL, RESOURCE_ID, AneelTariffError, fetch_cemig_application_rows, parse_cemig_application_rows


def synthetic_aneel_row(**changes):
    row = {
        "_id": 456,
        "SigAgente": "CEMIG-D",
        "DatInicioVigencia": "2026-01-01T00:00:00",
        "DatFimVigencia": "2026-12-31T00:00:00",
        "DscBaseTarifaria": "Aplicação",
        "DscSubGrupo": "B1",
        "DscModalidadeTarifaria": "Convencional",
        "DscClasse": "Residencial",
        "DscSubClasse": "Normal",
        "DscDetalhe": "",
        "NomPostoTarifario": "Não se aplica",
        "DscUnidadeTerciaria": "R$/MWh",
        "VlrTUSD": "500",
        "VlrTE": "300",
    }
    return row | changes


def test_synthetic_cemig_application_tariff_is_converted_and_source_is_retained():
    fetched_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    result = parse_cemig_application_rows([synthetic_aneel_row()], fetched_at=fetched_at)
    assert len(result) == 1
    tariff = result[0]
    assert Decimal(tariff["value_brl_kwh"]) == Decimal("0.800000")
    assert tariff["valid_from"] == "2026-01-01"
    assert tariff["valid_until"] == "2026-12-31"
    assert tariff["source_details"]["VlrTUSD"] == "500"
    assert tariff["source_details"]["VlrTE"] == "300"
    assert tariff["fetched_at"] == fetched_at.isoformat()


def test_synthetic_non_application_and_time_of_use_rows_are_not_imported():
    rows = parse_cemig_application_rows([
        synthetic_aneel_row(_id=457, DscBaseTarifaria="Tarifa homologada"),
        synthetic_aneel_row(_id=458, NomPostoTarifario="Ponta"),
        synthetic_aneel_row(_id=459, DscModalidadeTarifaria="Horária Azul"),
        synthetic_aneel_row(_id=460, DscSubGrupo="A4"),
    ])
    assert rows == []


def test_unknown_official_unit_is_rejected_without_guessing_conversion():
    with pytest.raises(AneelTariffError, match="Unidade de tarifa"):
        parse_cemig_application_rows([synthetic_aneel_row(DscUnidadeTerciaria="R$/kW")])


def test_missing_component_is_not_treated_as_zero():
    with pytest.raises(AneelTariffError, match="dois componentes"):
        parse_cemig_application_rows([synthetic_aneel_row(VlrTE=None)])


def test_non_numeric_source_row_id_is_not_offered_for_import():
    assert parse_cemig_application_rows([synthetic_aneel_row(_id="sem-id")]) == []


def test_synthetic_ckan_response_uses_paged_official_resource_contract_without_network():
    calls = []

    class SyntheticResponse:
        content = b"synthetic fixture"

        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "result": {"total": 1, "records": [synthetic_aneel_row()]}}

    def synthetic_get(url, *, params, timeout):
        calls.append((url, params, timeout))
        return SyntheticResponse()

    result = fetch_cemig_application_rows(request_get=synthetic_get, now=datetime(2026, 2, 1, tzinfo=timezone.utc))
    assert len(calls) == 1
    assert calls[0][0] == API_URL
    assert calls[0][1]["resource_id"] == RESOURCE_ID
    assert calls[0][1]["q"] == "CEMIG"
    assert result["records"][0]["value_brl_kwh"] == "0.800000"

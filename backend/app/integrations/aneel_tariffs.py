"""Read CEMIG application tariffs from ANEEL's public CKAN data API."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import re
import unicodedata

import httpx


RESOURCE_ID = "fcf2906c-7c32-4b9b-a637-054e7a5234f4"
API_URL = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
SOURCE_URL = f"https://dadosabertos.aneel.gov.br/dataset/tarifas-distribuidoras-energia-eletrica/resource/{RESOURCE_ID}"
PAGE_SIZE = 1000
MAX_ROWS = 20000
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


class AneelTariffError(ValueError):
    pass


def _normalized(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).casefold().strip()


def _decimal(value) -> Decimal:
    if value is None or str(value).strip() == "":
        raise AneelTariffError("A fonte não informa os dois componentes tarifários.")
    try:
        result = Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation as exc:
        raise AneelTariffError("A fonte retornou um valor tarifário inválido.") from exc
    if not result.is_finite() or result < 0:
        raise AneelTariffError("A fonte retornou um valor tarifário inválido.")
    return result


def _date(value, *, required: bool) -> date | None:
    raw = str(value or "").strip()
    if not raw or _normalized(raw) in {"null", "none", "nao informado"}:
        if required:
            raise AneelTariffError("A fonte não informa o início de vigência.")
        return None
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], pattern).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise AneelTariffError("A fonte retornou uma data de vigência inválida.") from exc


def _rate_per_kwh(row: dict) -> Decimal:
    tusd = _decimal(row.get("VlrTUSD"))
    te = _decimal(row.get("VlrTE"))
    unit = _normalized(row.get("DscUnidadeTerciaria")).replace(" ", "")
    if unit in {"r$/mwh", "r$/mw.h", "r$/megawatt-hora"}:
        return (tusd + te) / Decimal(1000)
    if unit in {"r$/kwh", "r$/kw.h", "r$/kilowatt-hora"}:
        return tusd + te
    raise AneelTariffError("Unidade de tarifa da ANEEL não reconhecida; nenhum valor foi convertido.")


def parse_cemig_application_rows(records: list[dict], *, fetched_at: datetime | None = None) -> list[dict]:
    """Return only flat, low-voltage application rates; exclude time-of-use rates."""
    fetched_at = fetched_at or datetime.now(timezone.utc)
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise ValueError("fetched_at precisa conter fuso horário")
    rows = []
    seen_ids = set()
    for row in records:
        if not isinstance(row, dict):
            continue
        row_id = row.get("_id")
        agent = _normalized(row.get("SigAgente"))
        tariff_base = _normalized(row.get("DscBaseTarifaria"))
        group = str(row.get("DscSubGrupo") or "").strip()
        modality = str(row.get("DscModalidadeTarifaria") or "").strip()
        post = _normalized(row.get("NomPostoTarifario"))
        unit = str(row.get("DscUnidadeTerciaria") or "").strip()

        # The current energy estimator accepts one flat kWh rate. Do not import
        # demand charges, economic-base rates, high-voltage or time-of-use rows.
        if not str(row_id or "").isdigit():
            continue
        if "cemig" not in agent or "aplica" not in tariff_base:
            continue
        if not re.match(r"^B\d", group, flags=re.IGNORECASE):
            continue
        if _normalized(modality) != "convencional":
            continue
        if post and post not in {"nao se aplica", "unico", "convencional"}:
            continue
        if row_id in seen_ids:
            continue

        value = _rate_per_kwh(row)
        if value <= 0:
            continue
        start = _date(row.get("DatInicioVigencia"), required=True)
        end = _date(row.get("DatFimVigencia"), required=False)
        if end and end < start:
            continue

        class_parts = [group, row.get("DscClasse"), row.get("DscSubClasse"), row.get("DscDetalhe")]
        tariff_class = " · ".join(str(part).strip() for part in class_parts if str(part or "").strip())
        row_details = {
            key: row.get(key)
            for key in (
                "_id", "SigAgente", "DscREH", "NumCNPJDistribuidora", "DatInicioVigencia", "DatFimVigencia",
                "DscBaseTarifaria", "DscSubGrupo", "DscModalidadeTarifaria", "DscClasse", "DscSubClasse",
                "DscDetalhe", "NomPostoTarifario", "DscUnidadeTerciaria", "VlrTUSD", "VlrTE",
            )
        }
        rows.append({
            "source_row_id": int(row_id) if str(row_id or "").isdigit() else None,
            "distributor": str(row.get("SigAgente")).strip(),
            "tariff_class": tariff_class[:80],
            "modality": modality[:80],
            "value_brl_kwh": str(value.quantize(Decimal("0.000001"))),
            "valid_from": start.isoformat(),
            "valid_until": end.isoformat() if end else None,
            "source_reference": SOURCE_URL,
            "source_details": row_details,
            "unit_as_published": unit,
            "fetched_at": fetched_at.isoformat(),
            "price_scope": "TUSD + TE; antes de impostos e bandeiras tarifárias",
        })
        if row_id is not None:
            seen_ids.add(row_id)
    return rows


def fetch_cemig_application_rows(*, request_get=None, now: datetime | None = None) -> dict:
    """Fetch the current CEMIG rows through ANEEL CKAN; never download its full CSV."""
    now = now or datetime.now(timezone.utc)
    request_get = request_get or httpx.get
    collected: list[dict] = []
    offset = 0
    total = None
    while total is None or offset < total:
        response = request_get(API_URL, params={
            "resource_id": RESOURCE_ID,
            "q": "CEMIG",
            "limit": PAGE_SIZE,
            "offset": offset,
        }, timeout=httpx.Timeout(20.0, connect=5.0))
        response.raise_for_status()
        body = response.content
        if len(body) > MAX_RESPONSE_BYTES:
            raise AneelTariffError("A resposta da fonte tarifária excede o limite de segurança.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AneelTariffError("A fonte da ANEEL retornou uma resposta inválida.") from exc
        result = payload.get("result") if isinstance(payload, dict) and payload.get("success") is True else None
        if not isinstance(result, dict) or not isinstance(result.get("records"), list):
            raise AneelTariffError("A resposta da ANEEL não corresponde ao catálogo de tarifas esperado.")
        page = result["records"]
        total = result.get("total")
        if not isinstance(total, int) or total < 0:
            raise AneelTariffError("A ANEEL não retornou contagem válida para a consulta.")
        collected.extend(page)
        offset += len(page)
        if not page or len(collected) >= MAX_ROWS:
            break
    if total is not None and total > MAX_ROWS and offset >= MAX_ROWS:
        raise AneelTariffError("A consulta excedeu o limite de registros; nenhum catálogo parcial será usado.")
    rows = parse_cemig_application_rows(collected, fetched_at=now)
    if not rows:
        raise AneelTariffError("A fonte respondeu, mas não há tarifas convencionais CEMIG compatíveis com o cálculo atual.")
    return {
        "source": "ANEEL — tarifas homologadas das distribuidoras",
        "source_reference": SOURCE_URL,
        "fetched_at": now.isoformat(),
        "records": rows,
    }

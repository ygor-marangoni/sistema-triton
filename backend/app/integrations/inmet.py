"""INMET annual ZIP adapter with explicit CSV schema configuration.

The official archive's headers and units are deliberately not guessed here.
An operator must map the exact headers/units from a downloaded official archive.
"""
from __future__ import annotations

import csv
import codecs
import io
import json
import threading
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable


OFFICIAL_ARCHIVE_URL = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"
CORE_VARIABLES = {"temperature_air", "relative_humidity", "wind_speed", "wind_direction", "precipitation"}
ALLOWED_VARIABLES = CORE_VARIABLES | {"solar_radiation"}
MISSING_MARKERS = {"", "null", "9999"}
MAX_PARSED_OBSERVATIONS = 250_000
MAX_CSV_MEMBERS = 5_000


class InmetError(RuntimeError):
    """Safe, user-facing source/configuration failure."""


@dataclass(frozen=True)
class VariableColumn:
    column: str
    unit: str


@dataclass(frozen=True)
class CsvSchema:
    encoding: str
    delimiter: str
    header_row: int
    station_code_column: str
    date_column: str | None
    time_column: str | None
    date_format: str | None
    time_format: str | None
    datetime_column: str | None
    datetime_format: str | None
    decimal_separator: str
    thousands_separator: str
    variables: dict[str, VariableColumn]


@dataclass(frozen=True)
class ParsedObservation:
    station_code: str
    variable: str
    value: Decimal
    unit: str
    observed_at: datetime
    collected_at: datetime
    quality: str = "raw_unvalidated"


class InmetAdapter:
    _archive_cache: dict[int, tuple[float, bytes]] = {}
    _cache_lock = threading.Lock()

    def __init__(
        self,
        schema: CsvSchema,
        *,
        timeout_seconds: float = 20,
        cache_ttl_seconds: int = 3600,
        max_archive_bytes: int = 536870912,
        max_uncompressed_bytes: int = 4294967296,
        client_factory: Callable | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.schema = schema
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_archive_bytes = max_archive_bytes
        self.max_uncompressed_bytes = max_uncompressed_bytes
        self.client_factory = client_factory
        self.clock = clock

    def download_archive(self, year: int) -> bytes:
        now = self.clock()
        with self._cache_lock:
            cached = self._archive_cache.get(year)
            if cached and self.cache_ttl_seconds > 0 and now - cached[0] < self.cache_ttl_seconds:
                return cached[1]

        try:
            import httpx

            client_factory = self.client_factory or httpx.Client
            with client_factory(timeout=self.timeout_seconds, follow_redirects=True) as client:
                for attempt in range(2):
                    try:
                        with client.stream("GET", OFFICIAL_ARCHIVE_URL.format(year=year)) as response:
                            if response.status_code == 429 or response.status_code >= 500:
                                if attempt == 0:
                                    if response.status_code == 429:
                                        try:
                                            retry_after = float(response.headers.get("retry-after", "1"))
                                        except (TypeError, ValueError):
                                            retry_after = 1
                                        time.sleep(min(max(retry_after, 0), 5))
                                    else:
                                        time.sleep(1)
                                    continue
                                raise InmetError("INMET indisponível ou com limite de requisições no momento.")
                            if response.status_code != 200:
                                raise InmetError(f"Arquivo oficial do INMET indisponível (HTTP {response.status_code}).")
                            length = response.headers.get("content-length")
                            if length and int(length) > self.max_archive_bytes:
                                raise InmetError("Arquivo do INMET excede o limite de tamanho configurado.")
                            body = bytearray()
                            for chunk in response.iter_bytes():
                                body.extend(chunk)
                                if len(body) > self.max_archive_bytes:
                                    raise InmetError("Arquivo do INMET excede o limite de tamanho configurado.")
                            archive = bytes(body)
                            break
                    except httpx.TransportError:
                        if attempt == 0:
                            time.sleep(1)
                            continue
                        raise InmetError("Falha de rede ao consultar o arquivo oficial do INMET.")
                else:  # pragma: no cover - loop always returns or raises
                    raise InmetError("Não foi possível obter o arquivo oficial do INMET.")
        except InmetError:
            raise
        except Exception as exc:
            raise InmetError("Falha ao consultar o arquivo oficial do INMET.") from exc

        if not archive.startswith(b"PK\x03\x04"):
            raise InmetError("A resposta oficial do INMET não é um arquivo ZIP válido.")
        if self.cache_ttl_seconds > 0:
            with self._cache_lock:
                for cached_year in list(self._archive_cache):
                    if cached_year != year:
                        self._archive_cache.pop(cached_year, None)
                self._archive_cache[year] = (self.clock(), archive)
        return archive

    def collect(self, year: int, station_code: str, collected_at: datetime | None = None) -> list[ParsedObservation]:
        archive = self.download_archive(year)
        return parse_archive(archive, year, station_code, self.schema, collected_at or datetime.now(timezone.utc), self.max_uncompressed_bytes)


def load_csv_schema(raw: str) -> CsvSchema:
    if not raw.strip():
        raise InmetError("Integração INMET não configurada: defina INMET_CSV_SCHEMA_JSON após conferir o cabeçalho do arquivo oficial.")
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise InmetError("INMET_CSV_SCHEMA_JSON precisa ser um JSON válido.") from exc
    required = ("encoding", "delimiter", "header_row", "station_code_column", "decimal_separator", "variables")
    if not isinstance(data, dict) or any(key not in data for key in required):
        raise InmetError("Mapeamento INMET incompleto; confira o formato documentado no README.")
    if not isinstance(data["delimiter"], str) or len(data["delimiter"]) != 1 or data["delimiter"] in "\r\n":
        raise InmetError("O separador CSV do INMET deve ter exatamente um caractere.")
    if data["decimal_separator"] not in (",", "."):
        raise InmetError("O separador decimal configurado deve ser ponto ou vírgula.")
    if data.get("thousands_separator", "") and (not isinstance(data["thousands_separator"], str) or len(data["thousands_separator"]) != 1 or data["thousands_separator"] == data["decimal_separator"]):
        raise InmetError("O separador de milhar precisa ser um caractere diferente do separador decimal.")
    if not isinstance(data["header_row"], int) or data["header_row"] < 0 or data["header_row"] > 100:
        raise InmetError("header_row deve ser a posição do cabeçalho entre 0 e 100.")
    if not isinstance(data["variables"], dict) or not CORE_VARIABLES.issubset(data["variables"]):
        raise InmetError("Configure temperatura, umidade relativa, vento, direção do vento e precipitação conforme a Entrega 1.")
    if set(data["variables"]) - ALLOWED_VARIABLES:
        raise InmetError("O mapeamento contém variável meteorológica não reconhecida pelo Triton.")
    variables: dict[str, VariableColumn] = {}
    for key, mapping in data["variables"].items():
        if not isinstance(mapping, dict) or not isinstance(mapping.get("column"), str) or not mapping["column"].strip() or not isinstance(mapping.get("unit"), str) or not mapping["unit"].strip():
            raise InmetError(f"Mapeamento da variável {key} precisa identificar coluna e unidade observadas na fonte.")
        if len(mapping["unit"].strip()) > 32:
            raise InmetError(f"Unidade da variável {key} excede o limite de armazenamento.")
        variables[key] = VariableColumn(mapping["column"].strip(), mapping["unit"].strip())
    if len({item.column for item in variables.values()}) != len(variables):
        raise InmetError("Cada variável meteorológica precisa apontar para sua própria coluna no CSV.")
    scalar_names = ("encoding", "station_code_column")
    if any(not isinstance(data[name], str) or not data[name].strip() for name in scalar_names):
        raise InmetError("Mapeamento INMET contém coluna ou formato vazio.")
    split_datetime = all(isinstance(data.get(name), str) and data[name].strip() for name in ("date_column", "time_column", "date_format", "time_format"))
    combined_datetime = all(isinstance(data.get(name), str) and data[name].strip() for name in ("datetime_column", "datetime_format"))
    if split_datetime == combined_datetime:
        raise InmetError("Configure data/hora em uma coluna com formato único ou em duas colunas com formatos explícitos.")
    if (any(name in data for name in ("date_column", "time_column", "date_format", "time_format")) and not split_datetime) or (any(name in data for name in ("datetime_column", "datetime_format")) and not combined_datetime):
        raise InmetError("Mapeamento de data/hora parcial; informe todas as colunas e formatos do modo escolhido.")
    try:
        codecs.lookup(data["encoding"])
        now = datetime.now()
        if split_datetime:
            datetime.strptime(now.strftime(data["date_format"]) + " " + now.strftime(data["time_format"]), data["date_format"] + " " + data["time_format"])
        else:
            datetime.strptime(now.strftime(data["datetime_format"]), data["datetime_format"])
    except (LookupError, ValueError) as exc:
        raise InmetError("Codificação ou formato de data/hora inválido no mapeamento INMET.") from exc
    return CsvSchema(
        encoding=data["encoding"], delimiter=data["delimiter"], header_row=data["header_row"],
        station_code_column=data["station_code_column"].strip(), date_column=data["date_column"].strip() if split_datetime else None,
        time_column=data["time_column"].strip() if split_datetime else None,
        date_format=data["date_format"] if split_datetime else None,
        time_format=data["time_format"] if split_datetime else None,
        datetime_column=data["datetime_column"].strip() if combined_datetime else None,
        datetime_format=data["datetime_format"] if combined_datetime else None,
        decimal_separator=data["decimal_separator"], thousands_separator=data.get("thousands_separator", ""), variables=variables,
    )


def _parse_decimal(raw: str, schema: CsvSchema) -> Decimal | None:
    normalized = raw.strip()
    if normalized.casefold() in MISSING_MARKERS:
        return None
    if schema.thousands_separator:
        normalized = normalized.replace(schema.thousands_separator, "")
    if schema.decimal_separator != ".":
        normalized = normalized.replace(schema.decimal_separator, ".")
    try:
        value = Decimal(normalized)
    except InvalidOperation as exc:
        raise InmetError("A resposta do INMET contém valor numérico inválido; nenhum dado foi importado.") from exc
    if not value.is_finite():
        raise InmetError("A resposta do INMET contém valor não finito; nenhum dado foi importado.")
    if value == Decimal("9999"):
        return None
    normalized_value = value.normalize()
    if (normalized_value != 0 and normalized_value.adjusted() >= 12) or max(0, -normalized_value.as_tuple().exponent) > 8:
        raise InmetError("Valor do INMET excede a precisão de armazenamento; nenhum dado foi importado.")
    return value


def parse_archive(archive: bytes, year: int, station_code: str, schema: CsvSchema, collected_at: datetime, max_uncompressed_bytes: int = 268435456) -> list[ParsedObservation]:
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("collected_at precisa conter fuso horário")
    try:
        zipped = zipfile.ZipFile(io.BytesIO(archive))
    except (zipfile.BadZipFile, OSError) as exc:
        raise InmetError("O arquivo do INMET não pôde ser lido como ZIP; nenhum dado foi importado.") from exc
    with zipped:
        members = [item for item in zipped.infolist() if item.filename.lower().endswith(".csv") and not item.is_dir()]
        if not members or sum(item.file_size for item in members) > max_uncompressed_bytes or len(members) > MAX_CSV_MEMBERS:
            raise InmetError("Estrutura ou tamanho do ZIP do INMET inválido; nenhum dado foi importado.")
        for item in members:
            if item.flag_bits & 0x1:
                raise InmetError("O ZIP do INMET contém membro criptografado e não foi processado.")
        found: dict[tuple[str, datetime], ParsedObservation] = {}
        for item in members:
            try:
                with zipped.open(item) as binary:
                    text_stream = io.TextIOWrapper(binary, encoding=schema.encoding, newline="")
                    reader = csv.reader(text_stream, delimiter=schema.delimiter)
                    header = None
                    for _ in range(schema.header_row + 1):
                        header = next(reader, None)
                    if not header:
                        raise InmetError("O cabeçalho configurado não foi localizado no CSV; nenhum dado foi importado.")
                    header = [cell.strip().lstrip("\ufeff") for cell in header]
                    if len(header) != len(set(header)):
                        raise InmetError("Cabeçalho CSV ambíguo no arquivo do INMET; nenhum dado foi importado.")
                    time_columns = {schema.date_column, schema.time_column} if schema.date_column else {schema.datetime_column}
                    required_columns = {schema.station_code_column} | {column for column in time_columns if column} | {item.column for item in schema.variables.values()}
                    missing = required_columns - set(header)
                    if missing:
                        raise InmetError("O cabeçalho do ZIP não corresponde ao mapeamento configurado; confira a versão do arquivo oficial.")
                    indexes = {name: header.index(name) for name in required_columns}
                    for row in reader:
                        if not row or not any(cell.strip() for cell in row):
                            continue
                        if len(row) < len(header):
                            raise InmetError("Linha CSV incompleta no arquivo do INMET; nenhum dado foi importado.")
                        if row[indexes[schema.station_code_column]].strip() != station_code:
                            continue
                        try:
                            if schema.date_column:
                                date_text = row[indexes[schema.date_column]].strip()
                                time_text = row[indexes[schema.time_column]].strip()
                                observed_naive = datetime.strptime(f"{date_text} {time_text}", f"{schema.date_format} {schema.time_format}")
                            else:
                                datetime_text = row[indexes[schema.datetime_column]].strip()
                                observed_naive = datetime.strptime(datetime_text, schema.datetime_format)
                        except ValueError as exc:
                            raise InmetError("Data/hora inválida em registro da estação; nenhum dado foi importado.") from exc
                        if observed_naive.year != year:
                            continue
                        observed_at = observed_naive.replace(tzinfo=timezone.utc) if observed_naive.tzinfo is None else observed_naive.astimezone(timezone.utc)
                        for variable, mapping in schema.variables.items():
                            raw_value = row[indexes[mapping.column]]
                            value = _parse_decimal(raw_value, schema)
                            if value is None:
                                continue
                            record = ParsedObservation(station_code, variable, value, mapping.unit, observed_at, collected_at.astimezone(timezone.utc))
                            key = (variable, observed_at)
                            previous = found.get(key)
                            if previous and (previous.value != value or previous.unit != mapping.unit):
                                raise InmetError("A mesma observação aparece com valores conflitantes no ZIP; nenhum dado foi importado.")
                            if previous is None and len(found) >= MAX_PARSED_OBSERVATIONS:
                                raise InmetError("O ZIP excedeu o limite de observações desta sincronização; nenhum dado foi importado.")
                            found[key] = record
            except UnicodeError as exc:
                raise InmetError("Codificação do CSV não corresponde ao mapeamento; nenhum dado foi importado.") from exc
            except (csv.Error, LookupError) as exc:
                raise InmetError("CSV do INMET inválido ou incompatível com a configuração; nenhum dado foi importado.") from exc
            except InmetError:
                raise
            except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
                raise InmetError("Um membro do ZIP está corrompido; nenhum dado foi importado.") from exc
    return sorted(found.values(), key=lambda item: (item.observed_at, item.variable))

"""Safe, conservative processing for human-reviewed ruler photographs.

Pixels are not converted to metres unless a reviewer supplies two scale marks
for that specific image. OpenCV only reports edge visibility; it never declares
an automatic waterline measurement.
"""

from __future__ import annotations

import io
import re
import unicodedata
import warnings
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
FORMAT_SUFFIX = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
LEVEL_QUANTUM = Decimal("0.001")


class RulerImageError(ValueError):
    """An uploaded image or a reviewer calibration is invalid."""


@dataclass(frozen=True)
class DecodedImage:
    width: int
    height: int
    image_format: str
    content_type: str
    method: str
    reason: str
    analysis_details: dict


def sanitize_original_filename(filename: str | None) -> str:
    """Keep a readable basename; never use this value as a filesystem path."""
    raw = (filename or "imagem").replace("\\", "/").split("/")[-1]
    normalized = unicodedata.normalize("NFKC", raw)
    safe = "".join(ch for ch in normalized if ch.isprintable() and ch not in "\r\n\x00")
    safe = re.sub(r"[^\w.() -]", "_", safe, flags=re.UNICODE).strip(" .")
    return (safe or "imagem")[:180]


def validate_and_analyze_image(
    payload: bytes,
    declared_content_type: str | None,
    *,
    max_bytes: int = 10 * 1024 * 1024,
    max_pixels: int = 20_000_000,
) -> DecodedImage:
    """Validate actual bytes, fully decode a static image, and inspect edges.

    MIME and extension are never trusted as evidence of image format. Canny
    edge density is diagnostic only and is not a confidence score or reading.
    """
    if not payload:
        raise RulerImageError("O arquivo de imagem está vazio.")
    if len(payload) > max_bytes:
        raise RulerImageError(f"A imagem excede o limite de {max_bytes // (1024 * 1024)} MiB.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as source:
                image_format = source.format
                if image_format not in ALLOWED_FORMATS:
                    raise RulerImageError("Formato não aceito. Envie uma imagem PNG, JPEG ou WebP estática.")
                if getattr(source, "n_frames", 1) != 1:
                    raise RulerImageError("Imagens animadas não são aceitas; envie uma fotografia estática.")
                width, height = source.size
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise RulerImageError("As dimensões da imagem são inválidas ou excedem o limite de pixels.")
                source.verify()
            with Image.open(io.BytesIO(payload)) as decoded:
                decoded.load()
                oriented = ImageOps.exif_transpose(decoded)
                width, height = oriented.size
                if width * height > max_pixels:
                    raise RulerImageError("As dimensões da imagem excedem o limite de pixels.")
                rgb = oriented.convert("RGB")
                pixels = rgb.tobytes()
    except RulerImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise RulerImageError("O arquivo não contém uma imagem completa e decodificável.") from exc

    expected_type = ALLOWED_FORMATS[image_format]
    supplied_type = (declared_content_type or "").split(";", 1)[0].strip().lower()
    if supplied_type and supplied_type != expected_type:
        raise RulerImageError("O tipo declarado não corresponde ao formato real da imagem.")

    details: dict[str, str | int] = {"format": image_format, "static": True}
    method = "pillow_decode_manual_calibration"
    reason = "A imagem não foi calibrada. Marque duas graduações legíveis e a linha d’água, ou informe a leitura manualmente."
    try:
        import cv2
        import numpy as np

        rgb_array = np.frombuffer(pixels, dtype=np.uint8).reshape((height, width, 3))
        gray = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        edge_pixels = int(cv2.countNonZero(edges))
        edge_density = Decimal(edge_pixels) / Decimal(width * height)
        details.update({
            "processor": "OpenCV Canny",
            "edge_pixels": edge_pixels,
            "edge_density": str(edge_density.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
            "edge_density_is_confidence": False,
        })
        method = "opencv_edges_manual_calibration"
        if edge_pixels < max(12, int(width * height * 0.00005)):
            reason = "Poucos contornos de contraste foram encontrados. A leitura é inconclusiva; confira a foto ou informe o nível manualmente."
        else:
            reason = "Os contornos não distinguem automaticamente a régua, suas graduações e a linha d’água. Calibre esta imagem e revise o valor."
    except Exception:
        details["opencv_status"] = "unavailable_or_processing_error"
        details["processor"] = "Pillow: validação e decodificação"

    return DecodedImage(width, height, image_format, expected_type, method, reason, details)


def storage_key_for(image_format: str) -> str:
    if image_format not in FORMAT_SUFFIX:
        raise RulerImageError("Formato de imagem não aceito.")
    return f"ruler-{uuid4().hex}{FORMAT_SUFFIX[image_format]}"


def calibrated_level(
    *,
    width: int,
    height: int,
    reference_1: dict,
    reference_2: dict,
    waterline: dict,
    minimum_m: Decimal,
    maximum_m: Decimal,
) -> Decimal:
    """Interpolate an individually calibrated y-position without extrapolation."""
    points = (reference_1, reference_2, waterline)
    for point in points:
        x, y = Decimal(str(point["x"])), Decimal(str(point["y"]))
        if x < 0 or y < 0 or x > width - 1 or y > height - 1:
            raise RulerImageError("Os pontos de calibração precisam estar dentro da imagem original.")

    y1, y2, yw = (Decimal(str(item["y"])) for item in points)
    x_values = [Decimal(str(item["x"])) for item in points]
    if y1 == y2:
        raise RulerImageError("As duas graduações precisam estar em posições verticais diferentes.")
    if Decimal(str(reference_1["level_m"])) == Decimal(str(reference_2["level_m"])):
        raise RulerImageError("Informe alturas diferentes para as duas graduações.")
    if max(x_values) - min(x_values) > max(Decimal(8), Decimal(width) * Decimal("0.02")):
        raise RulerImageError("Marque as duas graduações e a linha d’água sobre o mesmo eixo vertical da régua.")
    if not min(y1, y2) <= yw <= max(y1, y2):
        raise RulerImageError("A linha d’água precisa ficar entre as duas graduações de referência; extrapolação não é aceita.")

    level_1 = Decimal(str(reference_1["level_m"]))
    level_2 = Decimal(str(reference_2["level_m"]))
    result = level_1 + (yw - y1) * (level_2 - level_1) / (y2 - y1)
    result = result.quantize(LEVEL_QUANTUM, rounding=ROUND_HALF_UP)
    if result < minimum_m or result > maximum_m:
        raise RulerImageError("A leitura calibrada está fora da faixa física da estação.")
    return result


def persist_original(payload: bytes, root: Path, image_format: str) -> str:
    """Store original bytes using only a random, server-generated key."""
    key = storage_key_for(image_format)
    root.mkdir(parents=True, exist_ok=True)
    target = root / key
    target.write_bytes(payload)
    return key


def resolve_private_image(root: Path, storage_key: str) -> Path:
    """Resolve only a generated image key and reject any path traversal."""
    if not re.fullmatch(r"ruler-[0-9a-f]{32}\.(?:jpg|png|webp)", storage_key):
        raise RulerImageError("Identificador de arquivo inválido.")
    base = root.resolve()
    target = (base / storage_key).resolve()
    if target.parent != base:
        raise RulerImageError("Caminho de arquivo inválido.")
    return target

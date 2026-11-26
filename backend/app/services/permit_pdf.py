"""Local PDF inspection only. No network calls and no inferred field values."""
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import tempfile

from pypdf import PdfReader

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PAGES = 50
MAX_TEXT = 1_000_000
FIELDS = ("holder", "permit_number", "water_body", "valid_from", "valid_until", "monthly_demands")


def _page_has_image(page) -> bool:
    try:
        resources = page.get("/Resources") or {}
        xobjects = resources.get("/XObject") or {}
        for reference in xobjects.values():
            obj = reference.get_object()
            if obj.get("/Subtype") == "/Image":
                return True
    except Exception:
        return False
    return False


def _resolve_binary(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    candidate = Path(value.strip())
    if candidate.is_file():
        return str(candidate.resolve())
    return shutil.which(value.strip())


def _run_local_ocr(payload: bytes, pages, tesseract, renderer, languages, timeout_seconds):
    fragments = []
    with tempfile.TemporaryDirectory(prefix="triton-local-ocr-") as work:
        root = Path(work)
        pdf_path = root / "source.pdf"
        pdf_path.write_bytes(payload)
        for page_number in pages:
            prefix = root / f"page-{page_number}"
            subprocess.run(
                [renderer, "-f", str(page_number), "-l", str(page_number), "-singlefile", "-r", "200", "-png", str(pdf_path), str(prefix)],
                check=True, capture_output=True, timeout=timeout_seconds,
            )
            image_path = prefix.with_suffix(".png")
            extracted = subprocess.run(
                [tesseract, str(image_path), "stdout", "-l", languages],
                check=True, capture_output=True, timeout=timeout_seconds,
            )
            fragments.append(extracted.stdout.decode("utf-8", errors="replace"))
    return "\n".join(fragments)


def inspect_pdf(payload: bytes, content_type: str | None, *, ocr_config=None) -> tuple[str, str, dict]:
    if content_type != "application/pdf" or not payload.startswith(b"%PDF-") or len(payload) > MAX_PDF_BYTES:
        raise ValueError("Envie um PDF válido de até 10 MiB")
    try:
        reader = PdfReader(BytesIO(payload), strict=True)
        if reader.is_encrypted:
            raise ValueError("PDF protegido por senha não é aceito")
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise ValueError("O PDF deve conter entre 1 e 50 páginas")
        fragments = []
        image_pages = []
        total = 0
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            total += len(text)
            if total > MAX_TEXT:
                raise ValueError("Texto extraído excede o limite permitido")
            fragments.append(text)
            if not text.strip() and _page_has_image(page):
                image_pages.append(page_number)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF inválido ou não suportado") from exc
    text = "\n".join(fragments)
    status = "pending_review" if text.strip() else ("ocr_unavailable" if image_pages else "no_text_found")
    if image_pages:
        enabled = bool(getattr(ocr_config, "ocr_enabled", False))
        tesseract = _resolve_binary(getattr(ocr_config, "ocr_tesseract_command", "")) if ocr_config else None
        renderer = _resolve_binary(getattr(ocr_config, "ocr_pdf_renderer_command", "")) if ocr_config else None
        if enabled and tesseract and renderer:
            try:
                scanned_text = _run_local_ocr(
                    payload, image_pages, tesseract, renderer,
                    getattr(ocr_config, "ocr_languages", "por+eng"),
                    getattr(ocr_config, "ocr_timeout_seconds", 30),
                )
                text = (text + "\n" + scanned_text).strip()
                status = "pending_review" if text else "ocr_empty"
            except (OSError, subprocess.SubprocessError):
                status = "ocr_failed"
        else:
            status = "ocr_unavailable"
    elif text.strip():
        status = "pending_review"
    fields = {field: {"status": "não localizado", "value": None} for field in FIELDS}
    return status, text, fields

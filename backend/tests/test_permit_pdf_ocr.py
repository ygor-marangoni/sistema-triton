"""Synthetic PDF tests only; no real permit documents or OCR precision claims."""
from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from app.services.permit_pdf import inspect_pdf


def synthetic_scan_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    image = DecodedStreamObject()
    image.set_data(b"\x00\x00\x00")
    image.update({
        NameObject("/Type"): NameObject("/XObject"),
        NameObject("/Subtype"): NameObject("/Image"),
        NameObject("/Width"): NumberObject(1),
        NameObject("/Height"): NumberObject(1),
        NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
        NameObject("/BitsPerComponent"): NumberObject(8),
    })
    image_ref = writer._add_object(image)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/XObject"): DictionaryObject({NameObject("/Im0"): image_ref})
    })
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_synthetic_scanned_pdf_reports_ocr_unavailable_when_not_configured():
    config = SimpleNamespace(ocr_enabled=False, ocr_tesseract_command="", ocr_pdf_renderer_command="")
    status, extracted_text, fields = inspect_pdf(synthetic_scan_pdf(), "application/pdf", ocr_config=config)
    assert status == "ocr_unavailable"
    assert extracted_text == ""
    assert all(field["status"] == "não localizado" for field in fields.values())


def test_synthetic_scanned_pdf_does_not_invent_fields():
    status, extracted_text, fields = inspect_pdf(synthetic_scan_pdf(), "application/pdf")
    assert status == "ocr_unavailable"
    assert not extracted_text
    assert all(field["value"] is None for field in fields.values())

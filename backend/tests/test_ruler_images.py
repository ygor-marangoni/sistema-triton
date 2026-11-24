"""Tests use generated synthetic images only; none represents a field reading."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.services.ruler_images import (
    RulerImageError,
    calibrated_level,
    persist_original,
    resolve_private_image,
    sanitize_original_filename,
    validate_and_analyze_image,
)


def synthetic_png(*, blank=False):
    """Create a labelled test fixture in memory, never a measurement artifact."""
    image = Image.new("RGB", (120, 240), "white")
    if not blank:
        draw = ImageDraw.Draw(image)
        draw.rectangle((42, 20, 76, 220), outline="black", width=2)
        for y in (50, 100, 150, 200):
            draw.line((42, y, 76, y), fill="black", width=2)
    data = BytesIO()
    image.save(data, format="PNG")
    return data.getvalue()


def test_valid_synthetic_png_is_decoded_but_not_measured():
    decoded = validate_and_analyze_image(synthetic_png(), "image/png")
    assert decoded.image_format == "PNG"
    assert (decoded.width, decoded.height) == (120, 240)
    assert decoded.method in {"opencv_edges_manual_calibration", "pillow_decode_manual_calibration"}
    assert "calibr" in decoded.reason.lower()
    assert decoded.analysis_details.get("edge_density_is_confidence") in (0, None)


def test_blank_synthetic_image_remains_inconclusive():
    decoded = validate_and_analyze_image(synthetic_png(blank=True), "image/png")
    assert "calibr" in decoded.reason.lower() or "contorno" in decoded.reason.lower()
    assert "suggested_level_m" not in decoded.analysis_details


@pytest.mark.parametrize("payload, content_type", [
    (b"plain text, not an image", "image/png"),
    (synthetic_png(), "image/jpeg"),
])
def test_invalid_or_mismatched_image_is_rejected(payload, content_type):
    with pytest.raises(RulerImageError):
        validate_and_analyze_image(payload, content_type)


def test_size_limit_and_non_static_types_are_rejected():
    with pytest.raises(RulerImageError, match="limite"):
        validate_and_analyze_image(synthetic_png(), "image/png", max_bytes=20)
    gif = BytesIO()
    Image.new("RGB", (8, 8), "white").save(gif, format="GIF")
    with pytest.raises(RulerImageError, match="Formato"):
        validate_and_analyze_image(gif.getvalue(), "image/gif")


def test_per_image_calibration_interpolates_only_between_known_marks():
    result = calibrated_level(
        width=120,
        height=240,
        reference_1={"x": 60, "y": 50, "level_m": "1.000"},
        reference_2={"x": 60, "y": 150, "level_m": "0.000"},
        waterline={"x": 60, "y": 75},
        minimum_m=Decimal("0"),
        maximum_m=Decimal("2"),
    )
    assert result == Decimal("0.750")


@pytest.mark.parametrize("waterline, message", [
    ({"x": 60, "y": 151}, "entre"),
    ({"x": 110, "y": 75}, "mesmo eixo"),
    ({"x": 60, "y": 240}, "dentro"),
])
def test_calibration_rejects_extrapolation_or_bad_points(waterline, message):
    with pytest.raises(RulerImageError, match=message):
        calibrated_level(
            width=120,
            height=240,
            reference_1={"x": 60, "y": 50, "level_m": "1.000"},
            reference_2={"x": 60, "y": 150, "level_m": "0.000"},
            waterline=waterline,
            minimum_m=Decimal("0"),
            maximum_m=Decimal("2"),
        )


def test_storage_uses_random_private_filename_and_sanitizes_original(monkeypatch):
    writes = {}

    def capture_write(path, payload):
        writes[str(path)] = payload
        return len(payload)

    monkeypatch.setattr(Path, "write_bytes", capture_write)
    payload = synthetic_png()
    root = Path.cwd()
    key = persist_original(payload, root, "PNG")
    assert key.startswith("ruler-") and "/" not in key and "\\" not in key
    target = resolve_private_image(root, key)
    assert writes[str(target)] == payload
    assert sanitize_original_filename("..\\folder/name\r\n.png") == "name.png"
    with pytest.raises(RulerImageError):
        resolve_private_image(root, "..\\private.png")

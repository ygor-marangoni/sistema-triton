"""Temporal outorga-link tests use synthetic timestamps only."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.permit_links import resolve_link, validate_no_overlap


def link(id, start, end, outorga):
    return SimpleNamespace(id=id, valid_from_at=start, valid_until_at=end, outorga_id=outorga)


def test_adjacent_assignment_periods_resolve_the_full_reading_interval():
    boundary = datetime(2026, 4, 1, tzinfo=timezone.utc)
    old = link(1, datetime(2026, 1, 1, tzinfo=timezone.utc), boundary, 10)
    new = link(2, boundary, None, 11)
    found, status = resolve_link([old, new], datetime(2026, 3, 31, tzinfo=timezone.utc), boundary)
    assert status == "confirmado" and found.outorga_id == 10
    found, status = resolve_link([old, new], boundary, datetime(2026, 4, 2, tzinfo=timezone.utc))
    assert status == "confirmado" and found.outorga_id == 11


def test_overlapping_validity_is_rejected_but_adjacent_is_allowed():
    existing = [link(1, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 4, 1, tzinfo=timezone.utc), 10)]
    validate_no_overlap(existing, datetime(2026, 4, 1, tzinfo=timezone.utc), None)
    with pytest.raises(ValueError, match="conflita"):
        validate_no_overlap(existing, datetime(2026, 3, 31, tzinfo=timezone.utc), None)


def test_legacy_reading_without_known_interval_has_no_historical_assignment():
    found, status = resolve_link([link(1, datetime(2020, 1, 1, tzinfo=timezone.utc), None, 10)],
                                 None, datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert found is None
    assert "sem início" in status


def test_reading_crossing_a_link_change_is_not_assigned_to_either_outorga():
    boundary = datetime(2026, 4, 1, tzinfo=timezone.utc)
    links = [link(1, datetime(2026, 1, 1, tzinfo=timezone.utc), boundary, 10),
             link(2, boundary, None, 11)]
    found, status = resolve_link(links, datetime(2026, 3, 31, 23, tzinfo=timezone.utc),
                                datetime(2026, 4, 1, 1, tzinfo=timezone.utc))
    assert found is None
    assert "sem vínculo" in status

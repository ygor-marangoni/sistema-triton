import pytest

from app.services.geometry import validate_polygon_kml


VALID_KML = """<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>-46,-17 -45.9,-17 -45.9,-16.9 -46,-16.9 -46,-17</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>"""


def test_accepts_a_closed_kml_polygon_with_geographic_coordinates():
    validate_polygon_kml(VALID_KML)


@pytest.mark.parametrize(
    "kml",
    [
        "<root><Polygon><coordinates>0,0 1,0 1,1 0,1</coordinates></Polygon></root>",
        "<kml><Polygon><outerBoundaryIs><LinearRing><coordinates>0,0 1,0 1,1 0,1</coordinates></LinearRing></outerBoundaryIs></Polygon></kml>",
        "<kml><Polygon><outerBoundaryIs><LinearRing><coordinates>181,0 1,0 1,1 181,0</coordinates></LinearRing></outerBoundaryIs></Polygon></kml>",
        "<!DOCTYPE kml [<!ENTITY xxe SYSTEM 'file:///c:/windows/win.ini'>]><kml>&xxe;</kml>",
    ],
)
def test_rejects_documents_that_are_not_a_safe_closed_geographic_polygon(kml):
    with pytest.raises(ValueError):
        validate_polygon_kml(kml)


def test_rejects_kml_larger_than_one_megabyte():
    oversized = "<kml>" + (" " * 1_000_001) + "</kml>"
    with pytest.raises(ValueError, match="1 MB"):
        validate_polygon_kml(oversized)

"""Validation helpers for user supplied reservoir geometry."""

from math import isfinite

from defusedxml.ElementTree import fromstring as safe_xml_fromstring


MAX_KML_BYTES = 1_000_000


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_ring(coordinates: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for position in coordinates.split():
        fields = position.split(",")
        if len(fields) not in (2, 3):
            raise ValueError("Coordenada KML deve conter longitude, latitude e altitude opcional")
        try:
            longitude, latitude = float(fields[0]), float(fields[1])
            altitude = float(fields[2]) if len(fields) == 3 else None
        except ValueError as exc:
            raise ValueError("KML contém coordenada não numérica") from exc
        if not isfinite(longitude) or not isfinite(latitude) or (altitude is not None and not isfinite(altitude)):
            raise ValueError("KML contém coordenada não finita")
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError("Coordenada KML fora da faixa de longitude/latitude")
        points.append((longitude, latitude))

    if len(points) < 4 or len(set(points[:-1])) < 3:
        raise ValueError("O anel externo precisa de ao menos três pontos distintos e o fechamento")
    if points[0] != points[-1]:
        raise ValueError("O anel externo do polígono KML precisa estar fechado")
    return points


def validate_polygon_kml(kml: str) -> None:
    """Require a bounded, well formed KML document with a closed outer polygon ring.

    This validates that the uploaded geometry is structurally usable. It does not
    infer a reservoir's cota-volume relationship from the polygon.
    """
    if len(kml.encode("utf-8")) > MAX_KML_BYTES:
        raise ValueError("KML excede o limite de 1 MB")
    if "<!DOCTYPE" in kml.upper() or "<!ENTITY" in kml.upper():
        raise ValueError("KML não pode declarar DTD ou entidades XML")
    try:
        root = safe_xml_fromstring(kml)
    except Exception as exc:
        raise ValueError("KML inválido") from exc

    if _local_name(root.tag) != "kml":
        raise ValueError("O documento precisa ter a raiz KML")

    for polygon in (element for element in root.iter() if _local_name(element.tag) == "Polygon"):
        for outer in (element for element in polygon.iter() if _local_name(element.tag) == "outerBoundaryIs"):
            for ring in (element for element in outer.iter() if _local_name(element.tag) == "LinearRing"):
                for coordinates in (element for element in ring.iter() if _local_name(element.tag) == "coordinates"):
                    if coordinates.text:
                        _parse_ring(coordinates.text)
                        return

    raise ValueError("KML precisa conter um polígono com anel externo válido")

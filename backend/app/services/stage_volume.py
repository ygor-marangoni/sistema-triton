"""Interpolation of supplied survey points; no inference from KML or extrapolation."""
from decimal import Decimal


def interpolate_volume(points: list[tuple[Decimal, Decimal]], level_m: Decimal) -> Decimal:
    values = [(Decimal(level), Decimal(volume)) for level, volume in points]
    if len(values) < 2 or any(not level.is_finite() or not volume.is_finite() or level < 0 or volume < 0 for level, volume in values):
        raise ValueError("A curva precisa de pelo menos dois pontos finitos e não negativos")
    if any(a[0] >= b[0] or a[1] > b[1] for a, b in zip(values, values[1:])):
        raise ValueError("Cotas devem crescer e volumes não podem diminuir")
    level = Decimal(level_m)
    if not level.is_finite() or level < values[0][0] or level > values[-1][0]:
        raise ValueError("Cota fora da faixa levantada; extrapolação não autorizada")
    for (z1, v1), (z2, v2) in zip(values, values[1:]):
        if z1 <= level <= z2:
            return v1 + (v2 - v1) * (level - z1) / (z2 - z1)
    raise ValueError("Cota indisponível")

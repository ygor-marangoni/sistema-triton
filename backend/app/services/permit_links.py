"""Temporal hydrometer/outorga links with half-open intervals."""
from datetime import datetime, timezone


def utc(value):
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Vigências e leituras precisam informar fuso horário")
    return value.astimezone(timezone.utc)


def validate_no_overlap(existing_links, valid_from_at, valid_until_at=None, exclude_id=None):
    start = utc(valid_from_at)
    end = utc(valid_until_at) if valid_until_at is not None else None
    if end is not None and end <= start:
        raise ValueError("O fim da vigência deve ser posterior ao início")
    for link in existing_links:
        if getattr(link, "id", None) == exclude_id:
            continue
        other_start = utc(link.valid_from_at)
        other_end = utc(link.valid_until_at) if link.valid_until_at else None
        # Half-open [start, end), so an assignment may begin when the prior one ends.
        if (end is None or other_start < end) and (other_end is None or start < other_end):
            raise ValueError("A vigência conflita com outro vínculo temporal do hidrômetro")


def resolve_link(links, interval_start_at, observed_at):
    if interval_start_at is None:
        return None, "sem início de intervalo; vínculo histórico não comprovável"
    start, end = utc(interval_start_at), utc(observed_at)
    if start >= end:
        return None, "intervalo de leitura inválido"
    matches = []
    for link in links:
        link_start = utc(link.valid_from_at)
        link_end = utc(link.valid_until_at) if link.valid_until_at else None
        if link_start <= start and (link_end is None or end <= link_end):
            matches.append(link)
    if len(matches) == 1:
        return matches[0], "confirmado"
    if not matches:
        return None, "sem vínculo histórico comprovável para todo o intervalo"
    return None, "mais de um vínculo cobre o intervalo; revisão necessária"

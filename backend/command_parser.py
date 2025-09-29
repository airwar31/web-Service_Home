import re
from typing import Dict, Any

ROOMS_MAP = {
    # кухня
    "кухне": "кухня", "кухня": "кухня",
    # спальня
    "спальне": "спальня", "спальня": "спальня",
    # гостиная / зал
    "гостиной": "гостиная", "гостиная": "гостиная", "зале": "зал", "зал": "зал",
    # ванная / санузел / туалет
    "ванной": "ванная", "ванна": "ванная", "санузле": "туалет", "санузел": "туалет", "туалете": "туалет", "туалет": "туалет",
    # коридор / прихожая / холл
    "коридоре": "коридор", "коридор": "коридор", "прихожей": "прихожая", "прихожая": "прихожая", "холле": "холл", "холл": "холл",
    # кабинет / офис
    "кабинете": "кабинет", "кабинет": "кабинет", "офисе": "офис", "офис": "офис",
    # детская / комната
    "детской": "детская", "детская": "детская", "комнате": "комната", "комната": "комната",
}

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())

def parse_command(text: str) -> Dict[str, Any]:
    t = normalize(text)

    if re.search(r"\bвключ(и|ить)\b.*\bсвет\b", t):
        room = _extract_room(t)
        return {"action": "turn_on_light", "params": {"room": room}, "raw": text}
    if re.search(r"\bвыключ(и|ить)\b.*\bсвет\b", t):
        room = _extract_room(t)
        return {"action": "turn_off_light", "params": {"room": room}, "raw": text}

    m = re.search(r"таймер.*?на\s+(\d+)\s+(секунд(?:у|ы|)|минут(?:у|ы|)|час(?:|а|ов))", t)
    if m:
        value = int(m.group(1))
        unit = m.group(2)
        return {"action": "set_timer", "params": {"value": value, "unit": unit}, "raw": text}

    m = re.search(r"\bоткрой\b\s+([a-zA-Zа-яА-Я0-9._-]+)", t)
    if m:
        target = m.group(1)
        return {"action": "open_app", "params": {"target": target}, "raw": text}

    m = re.search(r"\bгромкост[ьи]\b\s+(\d{1,3})", t)
    if m:
        vol = max(0, min(100, int(m.group(1))))
        return {"action": "set_volume", "params": {"value": vol}, "raw": text}

    # Снизить температуру
    m = re.search(r"сниз(ь|ить|и) температуру( в ([а-я]+))?", t)
    if m:
        room = _extract_room(t)
        return {"action": "decrease_temperature", "params": {"room": room}, "raw": text}
    # Снизить влажность
    m = re.search(r"сниз(ь|ить|и) влажность( в ([а-я]+))?", t)
    if m:
        room = _extract_room(t)
        return {"action": "decrease_humidity", "params": {"room": room}, "raw": text}

    # Установить температуру/влажность: 'установи температуру на кухне 50', 'сделай влажность на кухне 40', 'температуру в зале 25', 'влажность в ванной 60'
    m = re.search(r'(установи|установить|поставь|измени|задать|сделай)? ?температур[ауыи]* ?(на|в)? ?([а-я]+)? ?(\d{1,2})', t)
    if m:
        value = int(m.group(4))
        room = _extract_room(m.group(3) or t)
        return {"action": "set_temperature", "params": {"room": room, "value": value}, "raw": text}
    m = re.search(r'(установи|установить|поставь|измени|задать|сделай)? ?влажност[ьи]* ?(на|в)? ?([а-я]+)? ?(\d{1,2})', t)
    if m:
        value = int(m.group(4))
        room = _extract_room(m.group(3) or t)
        return {"action": "set_humidity", "params": {"room": room, "value": value}, "raw": text}

    return {"action": "unknown", "params": {}, "raw": text}

def _extract_room(t: str):
    for form, canonical in ROOMS_MAP.items():
        if form in t:
            return canonical
    return None

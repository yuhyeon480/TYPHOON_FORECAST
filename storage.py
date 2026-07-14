"""
태풍/통보문 상태를 JSON 파일로 관리한다.
SQLite 대신 JSON을 쓰는 이유: GitHub Actions에서 이 파일을 그대로 커밋해두면
다음 실행(다른 러너)에서도 이전 상태를 그대로 이어받을 수 있고, git diff로
무엇이 바뀌었는지 눈으로 바로 확인할 수 있기 때문.
"""
import json
import os

from config import DB_PATH as STATE_PATH

_DEFAULT_STATE = {"known_typhoons": {}, "seen_bulletins": {}}


def _load() -> dict:
    if not os.path.exists(STATE_PATH):
        return dict(_DEFAULT_STATE)
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("known_typhoons", {})
        data.setdefault("seen_bulletins", {})
        return data
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_STATE)


def _save(data: dict):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)


def init_db():
    """상태 파일이 없으면 빈 상태로 새로 만든다."""
    if not os.path.exists(STATE_PATH):
        _save(dict(_DEFAULT_STATE))


def is_new_typhoon(typ_seq: str) -> bool:
    return typ_seq not in _load()["known_typhoons"]


def register_typhoon(typ_seq: str, name_kr: str, name_en: str, tm_fc: str):
    data = _load()
    data["known_typhoons"].setdefault(typ_seq, {
        "name_kr": name_kr, "name_en": name_en, "first_seen_tm_fc": tm_fc,
    })
    _save(data)


def is_new_bulletin(uid: str) -> bool:
    return uid not in _load()["seen_bulletins"]


def register_bulletin(uid: str, typ_seq: str, tm_fc: str, pressure_hpa, max_wind_ms):
    data = _load()
    data["seen_bulletins"].setdefault(uid, {
        "typ_seq": typ_seq, "tm_fc": tm_fc,
        "pressure_hpa": pressure_hpa, "max_wind_ms": max_wind_ms,
    })
    _save(data)

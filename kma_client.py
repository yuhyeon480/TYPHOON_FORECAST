"""
기상청 API허브(apihub.kma.go.kr) 태풍정보 클라이언트.

실제 응답 확인 결과(2026-07-14 실측):
- typ_now.php(disp=1,help=2)는 '요약 라인' 없이 경로(분석/예측) 라인만 내려준다.
- 각 라인은 21개 필드 + 끝에 구분자 '=' 가 붙어 총 22개 토큰으로 split된다.
- 결측치는 -999 로 표기된다 (RAD15, RAD25, ER15, ER25R 등).
- 태풍 이름(한글/영문)은 이 엔드포인트에 없어서, 필요시 typ_lst.php를 별도 호출해서 채운다.

경로 라인 필드 순서: FT,YY,TYP,SEQ,TMD,TYP_TM,FT_TM,LAT,LON,DIR,SP,PS,WS,
                     RAD15,RAD25,RAD,ED15,ER15,LOC,ED25,ER25R,(=)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

from config import KMA_AUTH_KEY, KMA_TYP_NOW_URL, KMA_TYP_LST_URL, DEBUG_RAW_RESPONSE

log = logging.getLogger("kma_client")

TRACK_FIELDS = [
    "FT", "YY", "TYP", "SEQ", "TMD", "TYP_TM", "FT_TM", "LAT", "LON", "DIR", "SP", "PS", "WS",
    "RAD15", "RAD25", "RAD", "ED15", "ER15", "LOC", "ED25", "ER25R",
]
SUMMARY_FIELDS = ["YY", "SEQ", "NOW", "EFF", "TM_ST", "TM_ED", "TYP_NAME", "TYP_EN", "REM"]

MISSING = "-999"


class KmaApiError(RuntimeError):
    pass


@dataclass
class TyphoonSummary:
    yy: str
    seq: str          # 태풍번호
    now: str           # 진행여부
    eff: str            # 한반도영향
    tm_st: str           # 시작시각 UTC
    tm_ed: str            # 종료시각 UTC
    name_kr: str
    name_en: str
    rem: str

    @property
    def typ_id(self) -> str:
        return f"{self.yy}-{self.seq}"


@dataclass
class TyphoonTrackPoint:
    ft: str            # 0=분석, 1=예측
    yy: str
    typ: str            # 태풍번호
    seq: str             # 발표번호
    tmd: str
    typ_tm: str           # 분석시각 UTC
    ft_tm: str             # 예측시각 UTC
    lat: Optional[float]
    lon: Optional[float]
    direction: Optional[str]
    speed_kmh: Optional[float]
    pressure_hpa: Optional[float]
    max_wind_ms: Optional[float]
    loc: str

    @property
    def typ_id(self) -> str:
        return f"{self.yy}-{self.typ}"

    @property
    def uid(self) -> str:
        return f"{self.yy}-{self.typ}-{self.seq}"


def _to_float(v: str):
    v = (v or "").strip()
    if v == "" or v == MISSING:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _to_str_or_none(v: str):
    v = (v or "").strip()
    if v in ("", "-", MISSING):
        return None
    return v


def _strip_trailing_terminator(fields: list[str]) -> list[str]:
    """줄 끝에 붙는 '=' 구분자를 제거한다."""
    if fields and fields[-1] == "=":
        return fields[:-1]
    return fields


def _now_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M")


def fetch_snapshot(tm: str | None = None, mode: int = 2) -> tuple[list[TyphoonSummary], list[TyphoonTrackPoint]]:
    """
    현재(또는 지정 tm) 기준 최근 12시간 내 발표된 모든 태풍의 요약+경로 정보를 조회한다.
    tm: 'YYYYMMDDHHmm' (UTC). 생략하면 현재 UTC 시각 사용.
    """
    if not KMA_AUTH_KEY:
        raise KmaApiError("KMA_AUTH_KEY가 설정되지 않았습니다. .env를 확인하세요.")

    params = {
        "tm": tm or _now_utc_str(),
        "mode": mode,
        "disp": 1,   # 콤마 구분
        "help": 2,   # 값만 (헤더/설명 없음)
        "authKey": KMA_AUTH_KEY,
    }
    resp = requests.get(KMA_TYP_NOW_URL, params=params, timeout=15)
    resp.raise_for_status()
    text = resp.text

    if DEBUG_RAW_RESPONSE:
        log.info("RAW RESPONSE:\n%s", text)

    if "authKey" in text and ("잘못" in text or "AUTH" in text.upper() and "FAIL" in text.upper()):
        raise KmaApiError(f"인증키 오류로 추정되는 응답: {text[:200]}")

    summaries: list[TyphoonSummary] = []
    tracks: list[TyphoonTrackPoint] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = _strip_trailing_terminator([f.strip() for f in line.split(",")])

        if len(fields) == len(SUMMARY_FIELDS):
            d = dict(zip(SUMMARY_FIELDS, fields))
            summaries.append(TyphoonSummary(
                yy=d["YY"], seq=d["SEQ"], now=d["NOW"], eff=d["EFF"],
                tm_st=d["TM_ST"], tm_ed=d["TM_ED"], name_kr=d["TYP_NAME"],
                name_en=d["TYP_EN"], rem=d["REM"],
            ))
        elif len(fields) == len(TRACK_FIELDS):
            d = dict(zip(TRACK_FIELDS, fields))
            tracks.append(TyphoonTrackPoint(
                ft=d["FT"], yy=d["YY"], typ=d["TYP"], seq=d["SEQ"], tmd=d["TMD"],
                typ_tm=d["TYP_TM"], ft_tm=d["FT_TM"], lat=_to_float(d["LAT"]), lon=_to_float(d["LON"]),
                direction=_to_str_or_none(d["DIR"]), speed_kmh=_to_float(d["SP"]),
                pressure_hpa=_to_float(d["PS"]), max_wind_ms=_to_float(d["WS"]),
                loc=_to_str_or_none(d["LOC"]) or "",
            ))
        else:
            log.warning(
                "알 수 없는 형식의 라인(필드 %d개) - 파서 조정이 필요할 수 있음: %s",
                len(fields), line[:150],
            )

    return summaries, tracks


def fetch_typhoon_name(yy: str, typ: str) -> tuple[str, str] | None:
    """
    typ_lst.php로 해당 연도 태풍목록을 조회해서 typ(태풍번호)에 해당하는
    (한글이름, 영문이름)을 찾는다. 실패하면 None을 반환 (알림 자체는 막지 않음).
    """
    if not KMA_AUTH_KEY:
        return None
    try:
        params = {"YY": yy, "disp": 1, "help": 2, "authKey": KMA_AUTH_KEY}
        resp = requests.get(KMA_TYP_LST_URL, params=params, timeout=10)
        resp.raise_for_status()
        text = resp.text
        if DEBUG_RAW_RESPONSE:
            log.info("RAW RESPONSE(typ_lst):\n%s", text)

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = _strip_trailing_terminator([f.strip() for f in line.split(",")])
            if len(fields) != len(SUMMARY_FIELDS):
                continue
            d = dict(zip(SUMMARY_FIELDS, fields))
            if d["SEQ"] == typ:
                return d["TYP_NAME"], d["TYP_EN"]
    except Exception:
        log.exception("태풍 이름 조회 실패 (typ=%s) - 이름 없이 진행", typ)
    return None

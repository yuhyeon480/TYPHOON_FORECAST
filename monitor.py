"""
메인 폴링 루프 (기상청 API허브 typ_now.php 기준).
- 주기적으로 현재 활동 중인 모든 태풍의 요약+경로 스냅샷 조회
- DB에 없던 태풍(YY-SEQ)이 나타나면 '신규 태풍 발생' 푸시
- 경로 데이터 중 가장 최근 분석시각(FT=0)의 위치/기압/풍속을 알림 본문에 포함
- 이미 보낸 통보문(uid = YY-TYP-발표번호)은 재알림하지 않음
"""
import logging
import time

from config import POLL_INTERVAL_SEC
import kma_client
import storage
import notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("monitor")


def _latest_analysis_point(tracks: list[kma_client.TyphoonTrackPoint], typ_id: str):
    """해당 태풍(typ_id)의 트랙 중 분석(FT='0')이면서 가장 최신 typ_tm인 지점을 반환."""
    candidates = [t for t in tracks if t.typ_id == typ_id and t.ft == "0"]
    if not candidates:
        candidates = [t for t in tracks if t.typ_id == typ_id]
    if not candidates:
        return None
    return max(candidates, key=lambda t: t.typ_tm)


def process_snapshot(summaries: list[kma_client.TyphoonSummary], tracks: list[kma_client.TyphoonTrackPoint]):
    # typ_now.php 실측 결과: 요약 라인 없이 트랙 라인만 내려옴 -> 트랙에 등장하는 typ_id 자체로 신규 감지
    typ_ids = sorted({t.typ_id for t in tracks})

    for typ_id in typ_ids:
        yy, typ = typ_id.split("-", 1)
        point = _latest_analysis_point(tracks, typ_id)
        is_new = storage.is_new_typhoon(typ_id)

        if is_new:
            name = kma_client.fetch_typhoon_name(yy, typ)
            name_kr, name_en = name if name else ("이름 미상", "")
            loc_text = (point.loc if point else "") or ""
            storage.register_typhoon(
                typ_id, name_kr, name_en, point.typ_tm if point else "",
                loc=loc_text, lat=point.lat if point else None, lon=point.lon if point else None,
            )

            title = f"제{typ}호 태풍 '{name_kr}({name_en})' 발생" if name else f"제{typ}호 태풍 발생"
            if point:
                loc_display = point.loc or (f"{point.lat}N {point.lon}E" if point.lat is not None else "위치 정보 없음")
                body = (
                    f"중심기압 {point.pressure_hpa}hPa, 최대풍속 {point.max_wind_ms}m/s, "
                    f"위치 {loc_display} (UTC {point.typ_tm})"
                )
            else:
                body = "상세 경로 정보는 조금 뒤 갱신됩니다."
            log.info("신규 태풍 감지: %s", title)
            notifier.send_push(title, body, data={"typ_id": typ_id, "type": "NEW_TYPHOON"})

        # 이번 폴링에 API에 나타났다는 것 자체가 '현재 활동 중'이라는 뜻이므로,
        # 신규/기존 관계없이 매번 최신 상태를 갱신해서 웹페이지가 최신 위치를 보여줄 수 있게 한다.
        if point:
            storage.update_typhoon_latest(
                typ_id, point.typ_tm, point.loc or "", point.lat, point.lon,
                point.pressure_hpa, point.max_wind_ms,
            )

        # 새 통보문(발표번호 기준)이면 기록만 해둔다 (원하면 여기서 강도변화 알림 로직 추가 가능)
        if point and storage.is_new_bulletin(point.uid):
            storage.register_bulletin(point.uid, typ_id, point.typ_tm, point.pressure_hpa, point.max_wind_ms)


def poll_once():
    try:
        summaries, tracks = kma_client.fetch_snapshot()
        log.info("태풍 요약 %d건, 경로 포인트 %d건 조회", len(summaries), len(tracks))
        process_snapshot(summaries, tracks)
    except Exception:
        log.exception("폴링 중 오류 발생 (다음 주기에 재시도)")


def run_forever():
    storage.init_db()
    log.info("태풍 모니터링 시작 (주기 %d초)", POLL_INTERVAL_SEC)
    while True:
        poll_once()
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    run_forever()

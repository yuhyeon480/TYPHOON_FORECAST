"""
GitHub Actions 같은 스케줄러에서 '한 번 실행하고 종료'하는 용도의 진입점.
monitor.py의 무한루프(run_forever) 대신 이걸 실행한다.

실행마다 last_run.json을 갱신해서, 새 태풍이 없어도 매번 저장소에 변경사항이
생기게 한다 (GitHub Actions는 저장소가 60일간 조용하면 예약 실행을 자동으로
꺼버리기 때문에, 이 파일 하나로 그 문제를 같이 해결한다).
"""
import json
import logging
from datetime import datetime, timezone

import monitor
import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("run_once")

STATUS_PATH = "last_run.json"


def _write_status(ok: bool, message: str = ""):
    status = {
        "last_run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": ok,
        "message": message,
    }
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    storage.init_db()
    try:
        monitor.poll_once()
        _write_status(True)
        log.info("1회 실행 완료")
    except Exception as e:
        log.exception("run_once 실행 중 예상치 못한 오류")
        _write_status(False, str(e))
        raise

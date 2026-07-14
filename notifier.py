"""
Firebase Cloud Messaging HTTP v1 API를 이용한 푸시 발송.

사전 준비:
1. Firebase 콘솔 > 프로젝트 설정 > 서비스 계정 > '새 비공개 키 생성'으로 JSON 다운로드
2. 앱(iOS/Android/Web) 클라이언트에서 FCM_TOPIC(config.py 기본값 'typhoon_alerts')을 구독하도록 구현
   (앱단: FirebaseMessaging.getInstance().subscribeToTopic("typhoon_alerts"))
"""
import json
import logging
import os

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from config import FCM_PROJECT_ID, FCM_SERVICE_ACCOUNT_FILE, FCM_SERVICE_ACCOUNT_JSON, FCM_TOPIC

log = logging.getLogger("notifier")

SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]

_PLACEHOLDER_PROJECT_IDS = {"", "your-firebase-project-id"}


def _fcm_ready() -> bool:
    if FCM_PROJECT_ID in _PLACEHOLDER_PROJECT_IDS:
        return False
    if FCM_SERVICE_ACCOUNT_JSON.strip():
        return True
    return os.path.exists(FCM_SERVICE_ACCOUNT_FILE)


def _get_access_token() -> str:
    if FCM_SERVICE_ACCOUNT_JSON.strip():
        info = json.loads(FCM_SERVICE_ACCOUNT_JSON)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        credentials = service_account.Credentials.from_service_account_file(
            FCM_SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
    credentials.refresh(Request())
    return credentials.token


def send_push(title: str, body: str, data: dict | None = None):
    """FCM_TOPIC을 구독 중인 모든 클라이언트에게 푸시를 보낸다.
    FCM이 아직 설정되지 않았거나 발송 중 오류가 나도, 예외를 밖으로 던지지 않고
    콘솔 출력으로 안전하게 대체한다 (알림 실패로 전체 폴링이 멈추면 안 되므로)."""
    if not _fcm_ready():
        log.warning("FCM 미설정(FCM_PROJECT_ID 또는 서비스계정 파일 없음) - 콘솔 출력으로 대체합니다.")
        print(f"[알림 미발송-설정필요] {title}\n{body}\n{data}")
        return

    try:
        access_token = _get_access_token()
        url = f"https://fcm.googleapis.com/v1/projects/{FCM_PROJECT_ID}/messages:send"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        message = {
            "message": {
                "topic": FCM_TOPIC,
                "notification": {"title": title, "body": body},
                "data": {k: str(v) for k, v in (data or {}).items()},
            }
        }
        resp = requests.post(url, headers=headers, json=message, timeout=10)
        if resp.status_code != 200:
            log.error("FCM 발송 실패: %s %s", resp.status_code, resp.text)
        else:
            log.info("FCM 발송 성공: %s", title)
    except Exception:
        log.exception("FCM 발송 중 예외 발생 - 알림은 실패했지만 모니터링은 계속됩니다: %s", title)

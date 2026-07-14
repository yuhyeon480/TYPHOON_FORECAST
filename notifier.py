"""
알림 발송: 웹 푸시(VAPID, Firebase 불필요) 우선 시도 → 안 되면 FCM 시도 → 둘 다 없으면 콘솔 출력.

웹 푸시 사전 준비:
1. site/index.html에서 "알림 켜기"를 눌러 구독을 만든다.
2. 화면에 뜨는 구독 JSON을 통째로 복사해 PUSH_SUBSCRIPTION_JSON 시크릿으로 등록한다.
3. VAPID_PRIVATE_KEY_PEM 시크릿에 발급받은 개인키 PEM 전체를 등록한다.

FCM(Firebase) 사전 준비(선택, 웹 푸시만으로 충분하면 생략 가능):
1. Firebase 콘솔 > 프로젝트 설정 > 서비스 계정 > '새 비공개 키 생성'으로 JSON 다운로드
2. 앱 클라이언트에서 FCM_TOPIC을 구독하도록 구현
"""
import json
import logging
import os

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from pywebpush import webpush, WebPushException

from config import (
    FCM_PROJECT_ID, FCM_SERVICE_ACCOUNT_FILE, FCM_SERVICE_ACCOUNT_JSON, FCM_TOPIC,
    VAPID_PRIVATE_KEY_PEM, PUSH_SUBSCRIPTION_JSON, VAPID_CLAIMS_EMAIL,
)

log = logging.getLogger("notifier")

SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]

_PLACEHOLDER_PROJECT_IDS = {"", "your-firebase-project-id"}


def _web_push_ready() -> bool:
    return bool(VAPID_PRIVATE_KEY_PEM and PUSH_SUBSCRIPTION_JSON)


def _send_web_push(title: str, body: str, data: dict | None = None) -> bool:
    """성공하면 True, 설정이 없거나 실패하면 False (예외는 던지지 않음)."""
    if not _web_push_ready():
        return False
    try:
        subscription_info = json.loads(PUSH_SUBSCRIPTION_JSON)
        payload = json.dumps({"title": title, "body": body, "url": "./", **(data or {})})
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY_PEM,
            vapid_claims={"sub": VAPID_CLAIMS_EMAIL},
        )
        log.info("웹 푸시 발송 성공: %s", title)
        return True
    except WebPushException:
        log.exception("웹 푸시 발송 실패 - 구독이 만료됐을 수 있음(브라우저에서 알림을 다시 켜야 할 수 있음)")
        return False
    except Exception:
        log.exception("웹 푸시 발송 중 예상치 못한 오류")
        return False


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


def _send_fcm(title: str, body: str, data: dict | None = None) -> bool:
    if not _fcm_ready():
        return False
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
            return False
        log.info("FCM 발송 성공: %s", title)
        return True
    except Exception:
        log.exception("FCM 발송 중 예외 발생")
        return False


def send_push(title: str, body: str, data: dict | None = None):
    """웹 푸시 → FCM 순서로 시도하고, 둘 다 설정 안 됐거나 실패하면 콘솔 출력으로 대체한다.
    알림 발송 실패로 전체 폴링이 멈추면 안 되므로 예외를 절대 밖으로 던지지 않는다."""
    if _send_web_push(title, body, data):
        return
    if _send_fcm(title, body, data):
        return
    log.warning("웹 푸시/FCM 모두 미설정 또는 실패 - 콘솔 출력으로 대체합니다.")
    print(f"[알림 미발송-설정필요] {title}\n{body}\n{data}")

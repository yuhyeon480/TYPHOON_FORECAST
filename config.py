"""
환경변수 기반 설정 (기상청 API허브 apihub.kma.go.kr 기준).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# apihub.kma.go.kr 회원가입(휴대폰 인증 필요) 후 발급받는 인증키
KMA_AUTH_KEY = os.getenv("KMA_AUTH_KEY", "")

# 1.3 태풍정보+예측(시점기준) - 실시간 폴링용 메인 엔드포인트
KMA_TYP_NOW_URL = "https://apihub.kma.go.kr/api/typ01/url/typ_now.php"

# 1.1 태풍목록 - 올해 태풍 목록 조회용 (보조, 필요시 사용)
KMA_TYP_LST_URL = "https://apihub.kma.go.kr/api/typ01/url/typ_lst.php"

# 1.2 태풍정보+예측(특정 태풍 상세) - 상세페이지 구현시 사용
KMA_TYP_DATA_URL = "https://apihub.kma.go.kr/api/typ01/url/typ_data.php"

# 폴링 주기(초). 기본 10분
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "600"))

# 상태 저장용 파일 경로 (JSON) - GitHub Actions에서는 이 파일을 저장소에 커밋해 상태를 유지함
DB_PATH = os.getenv("DB_PATH", "typhoon_state.json")

# Firebase 프로젝트 ID (FCM HTTP v1 API 사용)
FCM_PROJECT_ID = os.getenv("FCM_PROJECT_ID", "")

# 방법 A) 로컬 실행용: 서비스 계정 키 JSON '파일 경로'
FCM_SERVICE_ACCOUNT_FILE = os.getenv("FCM_SERVICE_ACCOUNT_FILE", "service-account.json")

# 방법 B) GitHub Actions 등: 서비스 계정 키 JSON '내용 자체'를 시크릿으로 주입 (파일 불필요)
FCM_SERVICE_ACCOUNT_JSON = os.getenv("FCM_SERVICE_ACCOUNT_JSON", "")

FCM_TOPIC = os.getenv("FCM_TOPIC", "typhoon_alerts")

# 응답 원문을 콘솔에 그대로 찍어서 파싱 형식을 눈으로 확인하고 싶을 때 True로
DEBUG_RAW_RESPONSE = os.getenv("DEBUG_RAW_RESPONSE", "0") == "1"

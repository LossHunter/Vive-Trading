from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os
from typing import Optional
from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트 디렉토리에서 찾음)
env_path = Path(__file__).parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)
# load_dotenv()

class Settings(BaseSettings):
    # vLLM 서버의 base URL. 환경 변수에서 읽어옵니다.
    VLLM_BASE_URL: str = "https://unmummied-keshia-feelingly.ngrok-free.dev/v1" # 디폴트
    
    # vLLM API 키 (필요한 경우). 현재는 비워둡니다.
    VLLM_API_KEY: str = ""
    UPBIT_ACCESS_KEY: str
    UPBIT_SECRET_KEY: str
    VLLM_DEFAULT_MODEL: str = "Qwen/Qwen3-30B-A3B-Thinking-2507-FP8"

    # Chroma DB 인증 정보 (필요한 경우). 환경 변수에서 읽어옵니다.
    CHROMA_AUTH_CREDENTIALS: str = "your_secure_password" # Docker Compose에서 설정한 비밀번호와 일치해야 합니다.

    # .env 파일을 읽도록 설정 (선택 사항)
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra="ignore") # extra 설정(모르는 키 있어도 무시)

# 설정 객체 생성
settings = Settings()


class DatabaseConfig:
    """데이터베이스 연결 설정 클래스
    
    모든 설정은 .env 파일에서만 가져옵니다.
    DB_URL이 설정되어 있으면 우선 사용하고, 없으면 개별 설정(DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)을 사용합니다.
    """
    
    # PostgreSQL 연결 정보 (.env 파일에서만 가져옴)
    DB_URL: Optional[str] = os.getenv("DB_URL")
    DB_HOST: Optional[str] = os.getenv("DB_HOST")
    DB_PORT: Optional[str] = os.getenv("DB_PORT")
    DB_NAME: Optional[str] = os.getenv("DB_NAME")
    DB_USER: Optional[str] = os.getenv("DB_USER")
    DB_PASSWORD: Optional[str] = os.getenv("DB_PASSWORD")
    
    @classmethod
    def get_connection_string(cls) -> str:
        """
        PostgreSQL 연결 문자열 생성
        DB_URL이 설정되어 있으면 우선 사용, 없으면 개별 설정으로 생성
        형식: postgresql://사용자명:비밀번호@호스트:포트/데이터베이스명
        
        Raises:
            ValueError: 필수 환경 변수가 설정되지 않은 경우
        """
        # DB_URL이 있으면 우선 사용
        if cls.DB_URL:
            return cls.DB_URL
        
        # 개별 설정 사용 (모든 값이 .env에서 가져와야 함)
        if not all([cls.DB_HOST, cls.DB_PORT, cls.DB_NAME, cls.DB_USER, cls.DB_PASSWORD]):
            missing = []
            if not cls.DB_HOST:
                missing.append("DB_HOST")
            if not cls.DB_PORT:
                missing.append("DB_PORT")
            if not cls.DB_NAME:
                missing.append("DB_NAME")
            if not cls.DB_USER:
                missing.append("DB_USER")
            if not cls.DB_PASSWORD:
                missing.append("DB_PASSWORD")
            
            raise ValueError(
                f"데이터베이스 연결 설정이 누락되었습니다. "
                f".env 파일에 다음 중 하나를 설정해주세요:\n"
                f"  - DB_URL (전체 연결 문자열)\n"
                f"  또는 다음 개별 설정들: {', '.join(missing)}"
                f"env_path: {env_path}"
            )
        
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"


class UpbitAPIConfig:
    """Upbit API 설정 클래스"""
    
    # Upbit API 기본 URL
    BASE_URL: str = "https://api.upbit.com/v1"
    
    # WebSocket URL
    WEBSOCKET_URL: str = "wss://api.upbit.com/websocket/v1"
    
    # Upbit API 키 (선택사항 - 인증이 필요한 API 사용 시)
    UPBIT_ACCESS_KEY: Optional[str] = os.getenv("UPBIT_ACCESS_KEY")
    UPBIT_SECRET_KEY: Optional[str] = os.getenv("UPBIT_SECRET_KEY")
    
    # API 엔드포인트 경로
    MARKETS_ENDPOINT: str = "/market/all"
    TICKER_ENDPOINT: str = "/ticker"
    CANDLES_MINUTE3_ENDPOINT: str = "/candles/minutes/3"
    CANDLES_DAY_ENDPOINT: str = "/candles/days"
    TRADES_ENDPOINT: str = "/trades/ticks"
    ORDERBOOK_ENDPOINT: str = "/orderbook"
    ACCOUNTS_ENDPOINT: str = "/v1/accounts"
    
    # 주요 거래 대상 마켓 코드 (KRW 기준)
    MAIN_MARKETS: list = [
        "KRW-BTC",   # 비트코인
        "KRW-ETH",   # 이더리움
        "KRW-DOGE",  # 도지코인
        "KRW-SOL",   # 솔라나
        "KRW-XRP",   # 리플
    ]
    
    # API 요청 제한 설정 (초당 요청 수)
    RATE_LIMIT_PER_SECOND: int = 10


class ServerConfig:
    """서버 설정 클래스"""
    
    # FastAPI 서버 포트
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # 서버 호스트
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # CORS 설정 (프론트엔드 연결 허용)
    CORS_ORIGINS: list = [
        "http://localhost:5173",  # Vite 기본 포트
        "http://localhost:5432",  # DB 기본 포트
        "http://localhost:3000",  # React 기본 포트
        "http://localhost:8000", # 현재 FE에서 사용 중인 포트 --> 53756에서 8000으로 변경
    ]
    
    # WebSocket 경로
    WEBSOCKET_PATH: str = "/ws/chartdata"


class DataCollectionConfig:
    """데이터 수집 설정 클래스"""
    
    # 데이터 수집 주기 (초 단위)
    TICKER_COLLECTION_INTERVAL: int = 1      # 티커 데이터: 1초마다
    CANDLE_COLLECTION_INTERVAL: int = 180    # 3분봉 캔들: 180초마다
    TRADES_COLLECTION_INTERVAL: int = 1      # 체결 데이터: 1초마다
    ORDERBOOK_COLLECTION_INTERVAL: int = 1   # 호가창 데이터: 1초마다
    
    # 데이터 수집 활성화 여부
    ENABLE_TICKER: bool = True
    ENABLE_CANDLES: bool = True
    ENABLE_TRADES: bool = True
    ENABLE_ORDERBOOK: bool = True


class IndicatorsConfig:
    """기술 지표 계산 설정 클래스"""
    
    # 기술 지표 계산 주기 (초 단위)
    INDICATORS_CALCULATION_INTERVAL: int = 3600  # 일봉 기반 기술 지표: 3600초(1시간)마다
    
    # RSI 계산 기간 (기본값)
    RSI_PERIOD: int = 14

    # LLM 프롬프트용 세부 설정
    LLM_EMA_PERIOD: int = 20
    LLM_EMA_LONG_PERIOD: int = 50
    LLM_MACD_FAST_PERIOD: int = 12
    LLM_MACD_SLOW_PERIOD: int = 26
    LLM_RSI_SHORT_PERIOD: int = 7
    LLM_RSI_LONG_PERIOD: int = 14
    LLM_ATR_SHORT_PERIOD: int = 3
    LLM_ATR_LONG_PERIOD: int = 14

class WalletConfig:
    """지갑 데이터 설정 클래스"""
    
    # 지갑 데이터 전송 주기 (초 단위)
    WALLET_BROADCAST_INTERVAL: int = 60  # 지갑 데이터: 60초(1분)마다 WebSocket으로 전송


class LLMPromptConfig:
    """LLM 프롬프트 생성 설정 클래스"""
    
    # LLM 프롬프트 데이터 생성 주기 (초 단위)
    PROMPT_GENERATION_INTERVAL: int = 180  # 3분(180초)마다 프롬프트 데이터 생성
    
    # 프롬프트 생성 활성화 여부
    ENABLE_PROMPT_GENERATION: bool = True


class LLMAccountConfig:
    """LLM 모델별 account_id 매핑 설정 클래스"""
    
    # 모델명과 account_id suffix 매핑
    MODEL_ACCOUNT_SUFFIX_MAP: dict = {
        "google/gemma-3-27b-it": "1",
        "openai/gpt-oss-120b": "2",
        "Qwen/Qwen3-30B-A3B-Thinking-2507-FP8": "3",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B": "4",
    }
    
    @classmethod
    def get_account_id_for_model(cls, model_name: str) -> str:
        """
        모델명에 해당하는 UUID 형식의 account_id 반환
        
        Args:
            model_name: LLM 모델명
        
        Returns:
            str: UUID 형식의 account_id (예: "00000000-0000-0000-0000-000000000001")
        
        Raises:
            ValueError: 모델명이 매핑에 없는 경우
        """
        suffix = cls.MODEL_ACCOUNT_SUFFIX_MAP.get(model_name)
        if suffix is None:
            raise ValueError(f"모델 '{model_name}'에 대한 account_id 매핑을 찾을 수 없습니다.")
        
        # suffix를 12자리로 패딩 (앞을 0으로 채움)
        padded_suffix = suffix.zfill(12)
        
        # UUID 형식으로 변환: 00000000-0000-0000-0000-000000000001
        return f"00000000-0000-0000-0000-{padded_suffix}"
    
    @classmethod
    def get_model_for_account_id(cls, account_id: str) -> Optional[str]:
        """
        account_id에 해당하는 모델명 반환 (역방향 조회)
        
        Args:
            account_id: UUID 형식의 account_id
        
        Returns:
            str | None: 모델명, 찾지 못하면 None
        """
        # UUID에서 마지막 12자리 추출
        suffix = account_id.split("-")[-1].lstrip("0") or "0"
        
        # suffix로 모델 찾기
        for model_name, model_suffix in cls.MODEL_ACCOUNT_SUFFIX_MAP.items():
            if model_suffix == suffix:
                return model_name
        
        return None
    

    
class ScriptConfig:
    """스크립트 및 API 테스트용 설정 클래스"""
    
    # API 테스트 및 데이터 수집 기본값
    DEFAULT_CANDLE_COUNT: int = 200  # 기본 캔들 데이터 개수
    DEFAULT_TRADES_COUNT: int = 10  # 기본 체결 데이터 개수
    DEFAULT_RSI_PERIOD: int = 14  # 기본 RSI 기간
    DEFAULT_RSI_PERIOD_SHORT: int = 7  # 단기 RSI 기간
    DEFAULT_INDICATORS_CANDLE_COUNT: int = 200  # 지표 계산용 캔들 개수
    DEFAULT_INTRADAY_SERIES_COUNT: int = 10  # LLM 프롬프트용 일중 시리즈 개수
    
    # 테스트용 마켓 리스트
    TEST_MARKETS: list = [
        "KRW-BTC",
        "KRW-ETH",
        "KRW-DOGE",
        "KRW-SOL",
        "KRW-XRP",
    ]

# ============================================================================
# [임시 테스트용] 주문 체결 기능 설정
# ============================================================================
# 이 섹션은 임시 테스트용 주문 체결 기능을 제어합니다.
# 나중에 실제 외부 시스템으로 교체할 때 이 기능을 비활성화하거나 제거할 수 있습니다.
# ============================================================================
class OrderExecutionConfig:
    """주문 체결 기능 설정 클래스 (임시 테스트용)"""
    
    # 주문 체결 기능 활성화 여부
    # False로 설정하면 주문 체결 API가 비활성화됩니다.
    ENABLE_ORDER_EXECUTION: bool = os.getenv("ENABLE_ORDER_EXECUTION", "True").lower() == "true"
    
    # 주문 체결 로깅 레벨
    # "INFO": 일반 정보만 로깅
    # "DEBUG": 상세 디버그 정보 포함
    ORDER_EXECUTION_LOG_LEVEL: str = os.getenv("ORDER_EXECUTION_LOG_LEVEL", "INFO")
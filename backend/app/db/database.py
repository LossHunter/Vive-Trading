"""
데이터베이스 연결 및 모델 관리 모듈
PostgreSQL 데이터베이스와의 연결을 관리하고, SQLAlchemy를 사용하여 ORM 모델을 정의합니다.
"""

from sqlalchemy import create_engine, Column, BigInteger, Text, Numeric, Integer, Boolean, DateTime, JSON, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
import logging

from app.core.config import DatabaseConfig

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Export list
__all__ = [
    # Database models
    "UpbitMarkets",
    "UpbitTicker",
    "UpbitCandlesMinute3",
    "UpbitDayCandles",
    "UpbitTrades",
    "UpbitOrderbook",
    "UpbitAccounts",
    "UpbitRSI",
    "UpbitIndicators",
    "LLMPromptData",
    "LLMTradingSignal",
    "LLMTradingExecution",
    # Database utilities
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    "test_connection",
]


# SQLAlchemy Base 클래스 생성 (모든 모델이 상속받을 기본 클래스)
Base = declarative_base()

# 데이터베이스 엔진 생성 (연결 풀 관리)
engine = create_engine(
    DatabaseConfig.get_connection_string(),
    pool_size=10,           # 연결 풀 크기
    max_overflow=20,        # 추가 연결 허용 수
    pool_pre_ping=True,      # 연결 유효성 자동 확인
    echo=False              # SQL 쿼리 로그 출력 여부 (디버깅 시 True)
)

# 세션 팩토리 생성 (데이터베이스 세션을 생성하는 함수)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ==================== 데이터베이스 모델 정의 ====================

class UpbitMarkets(Base):
    """Upbit 거래 가능 마켓 기본 정보 테이블"""
    __tablename__ = "upbit_markets"
    
    market = Column(Text, primary_key=True, comment="마켓 코드 (예: KRW-BTC)")
    korean_name = Column(Text, comment="한글명 (예: 비트코인)")
    english_name = Column(Text, comment="영문명 (예: Bitcoin)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="행 생성 시각 (UTC)")


class UpbitTicker(Base):
    """Upbit 현재가 정보 테이블"""
    __tablename__ = "upbit_ticker"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    market = Column(Text, nullable=False, comment="마켓 코드 FK (예: KRW-BTC)")
    trade_price = Column(Numeric(20, 8), comment="현재가 (최근 체결가)")
    opening_price = Column(Numeric(20, 8), comment="시가 (당일 첫 거래가)")
    high_price = Column(Numeric(20, 8), comment="고가 (당일 최고가)")
    low_price = Column(Numeric(20, 8), comment="저가 (당일 최저가)")
    prev_closing_price = Column(Numeric(20, 8), comment="전일 종가")
    change = Column(Text, comment="상승/하락/보합 상태 (RISE/FALL/EVEN)")
    signed_change_rate = Column(Numeric(10, 6), comment="전일 대비 등락률 (%)")
    acc_trade_price_24h = Column(Numeric(30, 10), comment="최근 24시간 누적 거래금액")
    acc_trade_volume_24h = Column(Numeric(30, 10), comment="최근 24시간 누적 거래량")
    timestamp = Column(BigInteger, comment="Upbit 서버 타임스탬프(ms)")
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), comment="데이터 수집 시각(UTC)")


class UpbitCandlesMinute3(Base):
    """Upbit 3분봉 캔들 데이터 테이블"""
    __tablename__ = "upbit_candles_minute3"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    market = Column(Text, nullable=False, comment="마켓 코드 FK (예: KRW-BTC)")
    candle_date_time_utc = Column(DateTime(timezone=True), nullable=False, comment="UTC 기준 캔들 시각")
    candle_date_time_kst = Column(DateTime(timezone=True), comment="KST 기준 캔들 시각")
    opening_price = Column(Numeric(20, 8), comment="시가 (Open)")
    high_price = Column(Numeric(20, 8), comment="고가 (High)")
    low_price = Column(Numeric(20, 8), comment="저가 (Low)")
    trade_price = Column(Numeric(20, 8), comment="종가 (Close)")
    prev_closing_price = Column(Numeric(20, 8), comment="전일 종가")
    change_price = Column(Numeric(20, 8), comment="전일 대비 가격 변화량")
    change_rate = Column(Numeric(10, 6), comment="전일 대비 변화율 (%)")
    candle_acc_trade_price = Column(Numeric(30, 10), comment="캔들 누적 거래금액")
    candle_acc_trade_volume = Column(Numeric(30, 10), comment="캔들 누적 거래량")
    unit = Column(Integer, default=3, comment="캔들 단위(3분봉 고정)")
    timestamp = Column(BigInteger, comment="Upbit 서버 타임스탬프(ms)")
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), comment="데이터 수집 시각")


class UpbitDayCandles(Base):
    """Upbit 일봉 캔들 데이터 테이블"""
    __tablename__ = "upbit_day_candles"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    market = Column(Text, nullable=False, comment="마켓 코드 FK (예: KRW-BTC)")
    candle_date_time_utc = Column(DateTime(timezone=True), nullable=False, comment="UTC 기준 캔들 시각")
    candle_date_time_kst = Column(DateTime(timezone=True), comment="KST 기준 캔들 시각")
    opening_price = Column(Numeric(20, 8), comment="시가 (Open)")
    high_price = Column(Numeric(20, 8), comment="고가 (High)")
    low_price = Column(Numeric(20, 8), comment="저가 (Low)")
    trade_price = Column(Numeric(20, 8), comment="종가 (Close)")
    prev_closing_price = Column(Numeric(20, 8), comment="전일 종가")
    change_price = Column(Numeric(20, 8), comment="전일 대비 가격 변화량")
    change_rate = Column(Numeric(10, 6), comment="전일 대비 변화율 (%)")
    candle_acc_trade_price = Column(Numeric(30, 10), comment="일봉 누적 거래금액")
    candle_acc_trade_volume = Column(Numeric(30, 10), comment="일봉 누적 거래량")
    timestamp = Column(BigInteger, comment="Upbit 서버 타임스탬프(ms)")
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), comment="데이터 수집 시각")
    raw_json = Column(JSON, comment="원본 JSON 데이터")


class UpbitTrades(Base):
    """Upbit 체결 데이터 테이블"""
    __tablename__ = "upbit_trades"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    market = Column(Text, nullable=False, comment="마켓 코드 FK")
    trade_timestamp = Column(BigInteger, comment="Unix timestamp(ms) 기준 체결 시각")
    trade_date_time_utc = Column(DateTime(timezone=True), comment="UTC 변환 체결 시각")
    trade_price = Column(Numeric(20, 8), comment="체결 가격")
    trade_volume = Column(Numeric(30, 10), comment="체결 수량")
    ask_bid = Column(Text, comment="매수(BID) 또는 매도(ASK) 구분")
    prev_closing_price = Column(Numeric(20, 8), comment="전일 종가")
    change = Column(Text, comment="상승/하락/보합 (RISE/FALL/EVEN)")
    sequential_id = Column(BigInteger, unique=True, comment="Upbit 거래 고유 식별자 (순차 ID)")
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), comment="데이터 수집 시각")


class UpbitOrderbook(Base):
    """Upbit 호가창 데이터 테이블"""
    __tablename__ = "upbit_orderbook"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    market = Column(Text, nullable=False, comment="마켓 코드 FK")
    timestamp = Column(BigInteger, comment="Unix timestamp(ms) 기준 호가창 시각")
    total_ask_size = Column(Numeric(30, 10), comment="전체 매도호가 수량 합계")
    total_bid_size = Column(Numeric(30, 10), comment="전체 매수호가 수량 합계")
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), comment="데이터 수집 시각")


class UpbitAccounts(Base):
    """Upbit 보유 자산 정보 테이블"""
    __tablename__ = "upbit_accounts"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    account_id = Column(UUID(as_uuid=False), comment="계정 식별자 (accounts 테이블 FK 가능)")  # UUID 타입 (문자열로 저장/조회)
    currency = Column(Text, nullable=False, comment="보유 자산 화폐 코드 (예: BTC, KRW)")
    balance = Column(Numeric(30, 10), comment="주문 가능 잔고 수량")
    locked = Column(Numeric(30, 10), comment="거래/주문 등에 묶여있는 잔고 수량")
    avg_buy_price = Column(Numeric(30, 10), comment="평균 매수가격 (평균 단가)")
    avg_buy_price_modified = Column(Boolean, comment="평균가 수동 수정 여부")
    unit_currency = Column(Text, comment="평균가 기준 통화 (예: KRW)")
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), comment="API 응답 수집 시각")


class UpbitRSI(Base):
    """RSI 계산 결과 테이블"""
    __tablename__ = "upbit_rsi"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    market = Column(Text, nullable=False, comment="마켓 코드 FK")
    candle_date_time_utc = Column(DateTime(timezone=True), nullable=False, comment="RSI 기준 시점 (캔들 UTC)")
    interval = Column(Text, nullable=False, comment="캔들 간격 (day, minute3)")
    period = Column(Integer, default=14, comment="RSI 계산 기간 (일/분 단위)")
    au = Column(Numeric(18, 8), comment="Average Up (평균 상승폭)")
    ad = Column(Numeric(18, 8), comment="Average Down (평균 하락폭)")
    rs = Column(Numeric(18, 8), comment="RS = AU / AD")
    rsi = Column(Numeric(10, 4), comment="RSI (0~100) 값")
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), comment="계산 완료 시각")


class UpbitIndicators(Base):
    """Upbit 기술지표 통합 테이블 (EMA, MACD, RSI, ATR, Bollinger 등)"""
    __tablename__ = "upbit_indicators"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    market = Column(Text, nullable=False, comment="마켓 코드 FK")
    candle_date_time_utc = Column(DateTime(timezone=True), nullable=False, comment="지표 계산 기준 시각 (UTC)")
    interval = Column(Text, comment="지표 계산 주기 (예: minute3, day 등)")
    ema12 = Column(Numeric(20, 8), comment="EMA(12)")
    ema20 = Column(Numeric(20, 8), comment="EMA(20)")
    ema26 = Column(Numeric(20, 8), comment="EMA(26)")
    ema50 = Column(Numeric(20, 8), comment="EMA(50)")
    macd = Column(Numeric(20, 8), comment="MACD 지표 값")
    macd_signal = Column(Numeric(20, 8), comment="MACD 시그널 라인")
    macd_hist = Column(Numeric(20, 8), comment="MACD 히스토그램 값")
    rsi14 = Column(Numeric(10, 4), comment="RSI(14)")
    atr3 = Column(Numeric(20, 8), comment="ATR(3) 평균진폭")
    atr14 = Column(Numeric(20, 8), comment="ATR(14) 평균진폭")
    bb_upper = Column(Numeric(20, 8), comment="볼린저밴드 상단")
    bb_middle = Column(Numeric(20, 8), comment="볼린저밴드 중단 (이동평균선)")
    bb_lower = Column(Numeric(20, 8), comment="볼린저밴드 하단")
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), comment="지표 계산 시각")


class LLMPromptData(Base):
    """LLM 프롬프트 생성용 데이터 테이블"""
    __tablename__ = "llm_prompt_data"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="프롬프트 생성 시각 (UTC)")
    trading_minutes = Column(Integer, comment="거래 시작 후 경과 시간 (분)")
    prompt_text = Column(Text, comment="생성된 프롬프트 텍스트")
    market_data_json = Column(JSON, comment="시장 데이터 JSON (모든 코인)")
    account_data_json = Column(JSON, comment="계정 정보 및 성과 JSON")
    indicator_config_json = Column(JSON, comment="사용된 지표 설정 JSON (기간 등)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="레코드 생성 시각")


class LLMTradingSignal(Base):
    """LLM 거래 신호 응답 테이블"""
    __tablename__ = "llm_trading_signal"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    prompt_id = Column(BigInteger, nullable=False, comment="프롬프트 ID (llm_prompt_data FK)")
    account_id = Column(UUID(as_uuid=False), comment="계정 식별자")
    coin = Column(Text, nullable=False, comment="코인 심볼 (예: BTC, ETH)")
    signal = Column(Text, nullable=False, comment="거래 신호 (예: buy_to_enter, sell_to_exit, hold)")
    stop_loss = Column(Numeric(20, 8), comment="손절가")
    profit_target = Column(Numeric(20, 8), comment="익절가")
    quantity = Column(Numeric(30, 10), comment="거래 수량")
    leverage = Column(Numeric(10, 2), comment="레버리지 배수")
    risk_usd = Column(Numeric(20, 8), comment="리스크 금액 (USD)")
    confidence = Column(Numeric(5, 4), comment="신뢰도 (0.0 ~ 1.0)")
    invalidation_condition = Column(Text, comment="무효화 조건 설명")
    justification = Column(Text, comment="거래 근거 설명")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="신호 생성 시각 (UTC)")

class LLMTradingExecution(Base):
    """LLM 거래 실행 기록 테이블"""
    __tablename__ = "llm_trading_execution"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="내부 식별자 (자동 증가)")
    signal_id = Column(BigInteger, nullable=False, comment="거래 신호 ID (llm_trading_signal FK)")
    account_id = Column(UUID(as_uuid=True), nullable=True, comment="계정 ID")
    coin = Column(Text, nullable=False, comment="코인 심볼")
    signal_type = Column(Text, nullable=False, comment="신호 타입 (buy_to_enter, sell_to_exit, hold)")
    
    # 실행 정보
    execution_status = Column(Text, nullable=False, comment="실행 상태 (success, failed, skipped)")
    failure_reason = Column(Text, comment="실패 사유")
    
    # 가격 정보
    intended_price = Column(Numeric(20, 8), comment="LLM이 판단한 가격 (신호 생성 시각)")
    executed_price = Column(Numeric(20, 8), comment="실제 체결 가격 (실행 시각)")
    price_slippage = Column(Numeric(10, 4), comment="슬리피지 (%) = (executed - intended) / intended * 100")
    
    # 수량 정보
    intended_quantity = Column(Numeric(30, 10), comment="의도한 수량")
    executed_quantity = Column(Numeric(30, 10), comment="실제 체결 수량")
    
    # 잔액 정보
    balance_before = Column(Numeric(30, 10), comment="거래 전 잔액")
    balance_after = Column(Numeric(30, 10), comment="거래 후 잔액")
    
    # 시각 정보
    signal_created_at = Column(DateTime(timezone=True), comment="신호 생성 시각")
    executed_at = Column(DateTime(timezone=True), server_default=func.now(), comment="실행 시각")
    time_delay = Column(Numeric(10, 3), comment="실행 지연 시간 (초)")
    
    # 추가 정보
    profit_target = Column(Numeric(20, 8), comment="목표가")
    stop_loss = Column(Numeric(20, 8), comment="손절가")
    notes = Column(Text, comment="비고")


# ==================== 데이터베이스 유틸리티 함수 ====================

def get_db() -> Session:
    """
    데이터베이스 세션 생성 함수 (의존성 주입용)
    FastAPI의 Depends()에서 사용하여 각 요청마다 새로운 DB 세션을 제공합니다.
    
    Yields:
        Session: SQLAlchemy 데이터베이스 세션
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    데이터베이스 테이블 초기화 함수
    모든 테이블을 생성합니다. (이미 존재하면 무시됨)
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 데이터베이스 테이블 초기화 완료")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 실패: {e}")
        raise


def test_connection() -> bool:
    """
    데이터베이스 연결 테스트 함수
    
    Returns:
        bool: 연결 성공 여부
    """
    try:
        with engine.connect() as conn:
            # SQLAlchemy 2.0에서는 text() 함수를 사용해야 함
            conn.execute(text("SELECT 1"))
        logger.info("✅ 데이터베이스 연결 성공")
        return True
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        return False
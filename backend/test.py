"""
과거 데이터 기반 거래 시뮬레이션 스크립트

이 스크립트는 이미 수집된 과거 데이터를 사용하여 거래 시뮬레이션을 실행합니다.
기존 코드를 수정하지 않으며, 독립적으로 실행 가능합니다.

사용법:
    docker-compose exec backend python test.py
    82번째 줄"account_id_suffix": "2",  # 본인 모델 넘버에 맞춰 수정
설정:
    스크립트 내부의 SIMULATION_CONFIG를 수정하여 시뮬레이션 범위를 지정합니다.

주의사항:
    - 기존 코드를 수정하지 않음
    - 독립적으로 실행 가능
    - 삭제해도 기존 시스템에 영향 없음
    - 시뮬레이션 결과는 기존 테이블에 저장되지만, account_id로 구분 가능
    - 기존 시장 데이터(upbit_ticker, upbit_candles 등)는 조회만 하며 변경하지 않음
"""

import asyncio
import json
import logging
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict, List, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import desc
from openai import OpenAI

from app.core.prompts import STRATEGY_PROMPTS, TradingStrategy
from app.core.config import LLMAccountConfig

# 기존 모듈 import (수정 없음)
from app.db.database import (
    SessionLocal,
    UpbitTicker,
    UpbitCandlesMinute3,
    UpbitDayCandles,
    UpbitIndicators,
    UpbitRSI,
    UpbitAccounts,
    LLMPromptData,
    LLMTradingSignal,
    LLMTradingExecution,
)
from app.schemas.llm import TradeDecision
from app.core.config import (
    settings,
    UpbitAPIConfig,
    IndicatorsConfig,
    LLMAccountConfig,
    ScriptConfig,
)
from app.services.vllm_model_registry import get_preferred_model_name
from app.services.llm_response_validator import validate_trade_decision, build_retry_prompt

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OpenAI(vLLM) 클라이언트 초기화
client = OpenAI(
    base_url=settings.VLLM_BASE_URL,
    api_key=settings.VLLM_API_KEY,
)

# 테스트시 날짜 및 account_id_suffix 번호 수정하고 돌리기
# config.py에서 VLLM_BASE_URL 및 VLLM_API_KEY 수정하고 돌리기
# docker-compose exec backend python test.py  명령어 터미널에서 사용하면됨.         
# 시뮬레이션 설정 (스크립트 내부에서 수정)
SIMULATION_CONFIG = {
    "start_time": datetime(2025, 11, 23, 8, 3, tzinfo=timezone.utc),
    "end_time": datetime(2025, 11, 26, 8, 3, tzinfo=timezone.utc),
    "interval_minutes": 3,  # 3분마다 거래 결정
    "model_name": None,  # None이면 기본 모델 사용
    "account_id_suffix": "2",  # 시뮬레이션용 계좌 구분 (기존 1-4와 구분)
    "initial_capital": Decimal("10000000"),  # 초기 자본금 (1000만원)
}

# 시뮬레이션용 account_id 생성
SIMULATION_ACCOUNT_ID = UUID(f"00000000-0000-0000-0000-{SIMULATION_CONFIG['account_id_suffix'].zfill(12)}")


def _to_decimal(value: Any) -> Optional[Decimal]:
    """
    PostgreSQL Numeric 컬럼에 적합하도록 Decimal로 변환
    None이면 None을 반환 (Optional 필드 지원)
    """
    if value is None:
        return None
    return Decimal(str(value))

# test.py에 추가할 함수

# def save_simulation_account_information(
#     db: Session,
#     account_id: UUID,
#     simulation_time: datetime
# ) -> bool:
#     """
#     시뮬레이션 계좌 정보를 account_information 테이블에 저장
    
#     Args:
#         db: 데이터베이스 세션
#         account_id: 시뮬레이션 계좌 ID
#         simulation_time: 시뮬레이션 시점
    
#     Returns:
#         bool: 저장 성공 여부
#     """
#     try:
#         from app.db.database import AccountInformation
        
#         # 시뮬레이션 시점의 계좌 데이터 조회
#         data_querier = HistoricalDataQuerier(db, simulation_time)
#         account_data = data_querier.get_account_data(account_id)
        
#         # 코인별 보유량 추출
#         positions = account_data.get('positions', [])
#         holdings = {
#             'BTC': Decimal("0"),
#             'ETH': Decimal("0"),
#             'DOGE': Decimal("0"),
#             'SOL': Decimal("0"),
#             'XRP': Decimal("0"),
#         }
        
#         for position in positions:
#             coin = position['coin'].upper()
#             if coin in holdings:
#                 holdings[coin] = Decimal(str(position['quantity']))
        
#         # 최신 신호 조회 (position, why 정보용)
#         latest_signal = db.query(LLMTradingSignal).filter(
#             LLMTradingSignal.account_id == account_id,
#             LLMTradingSignal.created_at <= simulation_time
#         ).order_by(desc(LLMTradingSignal.created_at)).first()
        
#         position_value = "hold"
#         why_value = ""
#         if latest_signal:
#             position_value = latest_signal.signal or "hold"
#             why_value = latest_signal.justification or ""
        
#         # AccountInformation 레코드 생성
#         account_info = AccountInformation(
#             user_id="5",  # 시뮬레이션 계좌는 userId 5
#             username="Simulation",
#             model_name="Historical Simulation",
#             logo="",  # 로고 없음
#             why=why_value,  # 최신 신호의 justification
#             position=position_value,  # 최신 신호의 signal
#             btc=holdings['BTC'],
#             eth=holdings['ETH'],
#             doge=holdings['DOGE'],
#             sol=holdings['SOL'],
#             xrp=holdings['XRP'],
#             krw=Decimal(str(account_data.get('available_cash', 0))),
#             total=Decimal(str(account_data.get('current_account_value', 0))),
#             created_at=simulation_time  # 시뮬레이션 시점으로 저장
#         )
        
#         db.add(account_info)
#         db.commit()
        
#         logger.info(f"✅ 시뮬레이션 계좌 정보 저장 완료 (시점: {simulation_time})")
#         return True
    
#     except Exception as e:
#         logger.error(f"❌ 시뮬레이션 계좌 정보 저장 실패: {e}", exc_info=True)
#         db.rollback()
#         return False
    
class HistoricalDataQuerier:
    """시뮬레이션 시점의 데이터 조회 클래스 (조회만 수행, 변경 없음)"""
    
    def __init__(self, db: Session, simulation_time: datetime):
        """
        Args:
            db: 데이터베이스 세션
            simulation_time: 시뮬레이션 시점 (이 시점 이전의 데이터만 조회)
        """
        self.db = db
        self.simulation_time = simulation_time
    
    def get_price_at_time(self, market: str) -> Optional[float]:
        """특정 시점의 가격 조회 (조회만 수행) - 티커 우선, 없으면 캔들 사용"""
         # 1. 티커 데이터 조회 시도
        ticker = self.db.query(UpbitTicker).filter(
            UpbitTicker.market == market,
            UpbitTicker.collected_at <= self.simulation_time
        ).order_by(desc(UpbitTicker.collected_at)).first()
        
        if ticker and ticker.trade_price:
            logger.debug(f"✅ {market} 가격 조회 성공 (티커): {ticker.trade_price} @ {ticker.collected_at}")
            return float(ticker.trade_price)
        
        # 2. 티커 데이터가 없으면 캔들 데이터 사용 (fallback)
        logger.warning(f"⚠️ {market} 티커 데이터 없음, 캔들 데이터로 대체 시도 (시점: {self.simulation_time})")
        
        # 시뮬레이션 시점과 가장 가까운 캔들 조회
        candle = self.db.query(UpbitCandlesMinute3).filter(
            UpbitCandlesMinute3.market == market,
            UpbitCandlesMinute3.candle_date_time_utc <= self.simulation_time
        ).order_by(desc(UpbitCandlesMinute3.candle_date_time_utc)).first()
        
        if candle and candle.trade_price:
            logger.info(f"✅ {market} 가격 조회 성공 (캔들): {candle.trade_price} @ {candle.candle_date_time_utc}")
            return float(candle.trade_price)
        
        # 3. 일봉 캔들도 시도
        day_candle = self.db.query(UpbitDayCandles).filter(
            UpbitDayCandles.market == market,
            UpbitDayCandles.candle_date_time_utc <= self.simulation_time
        ).order_by(desc(UpbitDayCandles.candle_date_time_utc)).first()
        
        if day_candle and day_candle.trade_price:
            logger.info(f"✅ {market} 가격 조회 성공 (일봉): {day_candle.trade_price} @ {day_candle.candle_date_time_utc}")
            return float(day_candle.trade_price)
        
        logger.error(f"❌ {market} 가격 조회 실패: 티커/캔들 데이터 모두 없음 (시점: {self.simulation_time})")
        return None
        
    def get_intraday_series(self, market: str, count: int = 10) -> Dict:
        """3분봉 인트라데이 시리즈 데이터 조회 (조회만 수행)"""
        # 시뮬레이션 시점 이전의 캔들만 조회
        candles = self.db.query(UpbitCandlesMinute3).filter(
            UpbitCandlesMinute3.market == market,
            UpbitCandlesMinute3.candle_date_time_utc <= self.simulation_time
        ).order_by(desc(UpbitCandlesMinute3.candle_date_time_utc)).limit(count).all()
        
        candles = list(reversed(candles))  # 오래된 것부터 정렬
        
        if len(candles) < count:
            logger.warning(f"⚠️ {market} 인트라데이 데이터 부족: {len(candles)}개 < {count}개 필요")
        
        # Mid prices 계산
        mid_prices = []
        for candle in candles:
            if candle.high_price and candle.low_price:
                mid = (float(candle.high_price) + float(candle.low_price)) / 2
                mid_prices.append(mid)
            elif candle.trade_price:
                mid_prices.append(float(candle.trade_price))
            else:
                mid_prices.append(0.0)
        
        # 지표 조회 (시뮬레이션 시점 이전)
        indicators_from_db = self.db.query(UpbitIndicators).filter(
            UpbitIndicators.market == market,
            UpbitIndicators.interval == 'minute3',
            UpbitIndicators.candle_date_time_utc <= self.simulation_time
        ).order_by(desc(UpbitIndicators.candle_date_time_utc)).limit(count).all()
        
        indicators_from_db = list(reversed(indicators_from_db))
        
        MAX_INDICATOR_COUNT = 10
        
        # MACD indicators
        macd_indicators = []
        if indicators_from_db:
            for indicator in indicators_from_db:
                if indicator.macd is not None:
                    macd_indicators.append(float(indicator.macd))
        macd_indicators = macd_indicators[-MAX_INDICATOR_COUNT:]
        
        # EMA(20) indicators
        ema_indicators = []
        if indicators_from_db:
            for indicator in indicators_from_db:
                if indicator.ema20 is not None:
                    ema_indicators.append(float(indicator.ema20))
        ema_indicators = ema_indicators[-MAX_INDICATOR_COUNT:]
        
        # RSI(14)
        rsi_indicators_14 = []
        if candles:
            candle_times = [candle.candle_date_time_utc for candle in candles]
            rsi_from_db_14 = self.db.query(UpbitRSI).filter(
                UpbitRSI.market == market,
                UpbitRSI.period == IndicatorsConfig.LLM_RSI_LONG_PERIOD,
                UpbitRSI.interval == 'minute3',
                UpbitRSI.candle_date_time_utc.in_(candle_times),
                UpbitRSI.candle_date_time_utc <= self.simulation_time
            ).order_by(desc(UpbitRSI.candle_date_time_utc)).limit(count).all()
            
            rsi_from_db_14 = list(reversed(rsi_from_db_14))
            for rsi in rsi_from_db_14:
                if rsi.rsi is not None:
                    rsi_indicators_14.append(float(rsi.rsi))
            rsi_indicators_14 = rsi_indicators_14[-MAX_INDICATOR_COUNT:]
        
        # RSI(7)
        rsi_indicators_7 = []
        if candles:
            candle_times = [candle.candle_date_time_utc for candle in candles]
            rsi_from_db_7 = self.db.query(UpbitRSI).filter(
                UpbitRSI.market == market,
                UpbitRSI.period == IndicatorsConfig.LLM_RSI_SHORT_PERIOD,
                UpbitRSI.interval == 'minute3',
                UpbitRSI.candle_date_time_utc.in_(candle_times),
                UpbitRSI.candle_date_time_utc <= self.simulation_time
            ).order_by(desc(UpbitRSI.candle_date_time_utc)).limit(count).all()
            
            rsi_from_db_7 = list(reversed(rsi_from_db_7))
            for rsi in rsi_from_db_7:
                if rsi.rsi is not None:
                    rsi_indicators_7.append(float(rsi.rsi))
            rsi_indicators_7 = rsi_indicators_7[-MAX_INDICATOR_COUNT:]
        
        mid_prices = mid_prices[-MAX_INDICATOR_COUNT:]
        
        return {
            'mid_prices': mid_prices,
            'ema_indicators': ema_indicators,
            'macd_indicators': macd_indicators,
            'rsi_indicators_7': rsi_indicators_7,
            'rsi_indicators_14': rsi_indicators_14
        }
    
    def get_longer_term_context(self, market: str) -> Dict:
        """일봉 기반 장기 컨텍스트 데이터 조회 (조회만 수행)"""
        day_candles = self.db.query(UpbitDayCandles).filter(
            UpbitDayCandles.market == market,
            UpbitDayCandles.candle_date_time_utc <= self.simulation_time
        ).order_by(desc(UpbitDayCandles.candle_date_time_utc)).limit(50).all()
        
        day_candles = list(reversed(day_candles))
        
        volumes = []
        for candle in day_candles:
            if candle.candle_acc_trade_volume:
                volumes.append(float(candle.candle_acc_trade_volume))
            else:
                volumes.append(0.0)
        
        indicators_from_db = self.db.query(UpbitIndicators).filter(
            UpbitIndicators.market == market,
            UpbitIndicators.interval == 'day',
            UpbitIndicators.candle_date_time_utc <= self.simulation_time
        ).order_by(desc(UpbitIndicators.candle_date_time_utc)).limit(50).all()
        
        indicators_from_db = list(reversed(indicators_from_db))
        
        atr14 = None
        if indicators_from_db and indicators_from_db[-1].atr14 is not None:
            atr14 = float(indicators_from_db[-1].atr14)
        
        atr3 = None
        if indicators_from_db and indicators_from_db[-1].atr3 is not None:
            atr3 = float(indicators_from_db[-1].atr3)
        
        ema20 = None
        if indicators_from_db and indicators_from_db[-1].ema20 is not None:
            ema20 = float(indicators_from_db[-1].ema20)
        
        ema50 = None
        if indicators_from_db and indicators_from_db[-1].ema50 is not None:
            ema50 = float(indicators_from_db[-1].ema50)
        
        if volumes:
            current_volume = volumes[-1]
            avg_volume = sum(volumes) / len(volumes)
        else:
            current_volume = 0.0
            avg_volume = 0.0
        
        MAX_INDICATOR_COUNT = 10
        macd_indicators = []
        if indicators_from_db:
            for indicator in indicators_from_db:
                if indicator.macd is not None:
                    macd_indicators.append(float(indicator.macd))
        macd_indicators = macd_indicators[-MAX_INDICATOR_COUNT:]
        
        rsi_indicators_14 = []
        if day_candles:
            day_candle_times = [candle.candle_date_time_utc for candle in day_candles]
            rsi_from_db = self.db.query(UpbitRSI).filter(
                UpbitRSI.market == market,
                UpbitRSI.period == IndicatorsConfig.LLM_RSI_LONG_PERIOD,
                UpbitRSI.interval == 'day',
                UpbitRSI.candle_date_time_utc.in_(day_candle_times),
                UpbitRSI.candle_date_time_utc <= self.simulation_time
            ).order_by(desc(UpbitRSI.candle_date_time_utc)).limit(MAX_INDICATOR_COUNT).all()
            
            rsi_from_db = list(reversed(rsi_from_db))
            for rsi in rsi_from_db:
                if rsi.rsi is not None:
                    rsi_indicators_14.append(float(rsi.rsi))
            rsi_indicators_14 = rsi_indicators_14[-MAX_INDICATOR_COUNT:]
        
        return {
            'ema20': ema20,
            'ema50': ema50,
            'atr3': atr3,
            'atr14': atr14,
            'current_volume': current_volume,
            'avg_volume': avg_volume,
            'macd_indicators': macd_indicators,
            'rsi_indicators_14': rsi_indicators_14
        }
    
    def get_coin_data(self, market: str) -> Dict:
        """특정 코인의 모든 데이터 수집 (조회만 수행)"""
        current_price = self.get_price_at_time(market)
        
        intraday_series = self.get_intraday_series(market, count=ScriptConfig.DEFAULT_INTRADAY_SERIES_COUNT)
        
        current_ema20 = None
        if intraday_series['ema_indicators']:
            current_ema20 = intraday_series['ema_indicators'][-1]
        
        current_macd = None
        if intraday_series['macd_indicators']:
            current_macd = intraday_series['macd_indicators'][-1]
        else:
            latest_indicator = self.db.query(UpbitIndicators).filter(
                UpbitIndicators.market == market,
                UpbitIndicators.interval == 'minute3',
                UpbitIndicators.candle_date_time_utc <= self.simulation_time
            ).order_by(desc(UpbitIndicators.candle_date_time_utc)).first()
            if latest_indicator and latest_indicator.macd is not None:
                current_macd = float(latest_indicator.macd)
        
        current_rsi7 = None
        if intraday_series['rsi_indicators_7']:
            current_rsi7 = intraday_series['rsi_indicators_7'][-1]
        
        longer_term = self.get_longer_term_context(market)
        
        return {
            'market': market,
            'current_price': current_price,
            'current_ema20': current_ema20,
            'current_macd': current_macd,
            'current_rsi7': current_rsi7,
            'intraday_series': intraday_series,
            'longer_term_context': longer_term,
            'open_interest_latest': None,
            'open_interest_avg': None,
            'funding_rate': None
        }
    
    def get_account_data(self, account_id: UUID) -> Dict:
        """계정 정보 조회 (조회만 수행, 시뮬레이션 시점 기준)"""
        # 시뮬레이션 시점 이전의 계정 데이터만 조회
        accounts = self.db.query(UpbitAccounts).filter(
            UpbitAccounts.account_id == str(account_id),
            UpbitAccounts.collected_at <= self.simulation_time
        ).order_by(desc(UpbitAccounts.collected_at)).all()
        
        # currency별로 최신 데이터만 추출
        latest_accounts = {}
        for acc in accounts:
            currency = acc.currency.upper() if acc.currency else None
            if currency and currency not in latest_accounts:
                latest_accounts[currency] = acc
        
        available_cash = 0.0
        if 'KRW' in latest_accounts and latest_accounts['KRW'].balance:
            available_cash = float(latest_accounts['KRW'].balance)
        
        ticker_prices = {}
        for market in UpbitAPIConfig.MAIN_MARKETS:
            price = self.get_price_at_time(market)
            if price:
                currency = market.split("-")[1] if "-" in market else market
                ticker_prices[currency] = price
        
        positions = []
        total_value = available_cash
        
        for currency, account in latest_accounts.items():
            if currency == 'KRW':
                continue
            
            balance = float(account.balance) if account.balance else 0.0
            avg_buy_price = float(account.avg_buy_price) if account.avg_buy_price else 0.0
            current_price = ticker_prices.get(currency, 0.0)
            
            if balance > 0:
                profit_loss = (current_price - avg_buy_price) * balance if avg_buy_price > 0 else 0.0
                profit_loss_percent = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0.0
                
                positions.append({
                    'coin': currency,
                    'quantity': balance,
                    'avg_buy_price': avg_buy_price,
                    'current_price': current_price,
                    'profit_loss': profit_loss,
                    'profit_loss_percent': profit_loss_percent
                })
                
                total_value += current_price * balance
        
        return {
            'current_total_return_percent': 0.0,
            'available_cash': available_cash,
            'current_account_value': total_value,
            'positions': positions,
            'sharpe_ratio': 0.0
        }


class HistoricalPromptGenerator:
    """시뮬레이션용 프롬프트 생성 클래스"""
    
    def __init__(self, db: Session, simulation_time: datetime, trading_start_time: datetime):
        self.db = db
        self.simulation_time = simulation_time
        self.trading_start_time = trading_start_time
        self.data_querier = HistoricalDataQuerier(db, simulation_time)
    
    def calculate_trading_minutes(self) -> int:
        """거래 시작 후 경과 시간(분) 계산"""
        elapsed = self.simulation_time - self.trading_start_time
        return int(elapsed.total_seconds() / 60)
    
    def generate_prompt_text(self, market_data: Dict, account_data: Dict, trading_minutes: int) -> str:
        """프롬프트 텍스트 생성 (기존 로직 참고)"""
        prompt = f"It has been {trading_minutes} minute since you started trading.\n\n"
        prompt += "…\n\n"
        prompt += "Below, we are providing you with a variety of state data, price data, and predictive signals so you can discover alpha. "
        prompt += "Below that is your current account information, value, performance, positions, etc.\n\n"
        prompt += "**ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST**\n\n"
        prompt += "**Timeframes note:** Unless stated otherwise in a section title, intraday series are provided at **3‑minute intervals**. "
        prompt += "If a coin uses a different interval, it is explicitly stated in that coin's section.\n\n"
        prompt += "---\n\n"
        prompt += "### CURRENT MARKET STATE FOR ALL COINS\n\n"
        
        for market in UpbitAPIConfig.MAIN_MARKETS:
            coin_data = market_data.get(market, {})
            if not coin_data:
                continue
            
            coin_name = market.split('-')[1] if '-' in market else market
            
            prompt += f"### ALL {coin_name} DATA\n\n"
            prompt += f"current_price = {coin_data.get('current_price', 'N/A')}, "
            prompt += f"current_ema20 = {coin_data.get('current_ema20', 'N/A')}, "
            prompt += f"current_macd = {coin_data.get('current_macd', 'N/A')}, "
            prompt += f"current_rsi (7 period) = {coin_data.get('current_rsi7', 'N/A')}\n\n"
            
            intraday = coin_data.get('intraday_series', {})
            prompt += "**Intraday series (by 3-minute, oldest → latest):**\n\n"
            prompt += f"Mid prices: {intraday.get('mid_prices', [])}\n\n"
            prompt += f"EMA indicators (20‑period): {intraday.get('ema_indicators', [])}\n\n"
            prompt += f"MACD indicators: {intraday.get('macd_indicators', [])}\n\n"
            prompt += f"RSI indicators (7‑Period): {intraday.get('rsi_indicators_7', [])}\n\n"
            prompt += f"RSI indicators (14‑Period): {intraday.get('rsi_indicators_14', [])}\n\n"
            
            longer_term = coin_data.get('longer_term_context', {})
            prompt += "**Longer‑term context (1‑day timeframe):**\n\n"
            prompt += f"20‑Period EMA: {longer_term.get('ema20', 'N/A')} vs. "
            prompt += f"50‑Period EMA: {longer_term.get('ema50', 'N/A')}\n\n"
            prompt += f"3‑Period ATR: {longer_term.get('atr3', 'N/A')} vs. "
            prompt += f"14‑Period ATR: {longer_term.get('atr14', 'N/A')}\n\n"
            prompt += f"Current Volume: {longer_term.get('current_volume', 'N/A')} vs. "
            prompt += f"Average Volume: {longer_term.get('avg_volume', 'N/A')}\n\n"
            prompt += f"MACD indicators: {longer_term.get('macd_indicators', [])}\n\n"
            prompt += f"RSI indicators (14‑Period): {longer_term.get('rsi_indicators_14', [])}\n\n"
            prompt += "---\n\n"
        
        prompt += "### HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE\n\n"
        prompt += f"Current Total Return (percent): {account_data.get('current_total_return_percent', 0)}%\n\n"
        prompt += f"Available Cash: {account_data.get('available_cash', 0)}\n\n"
        prompt += f"**Current Account Value:** {account_data.get('current_account_value', 0)}\n\n"
        prompt += "Current live positions & performance:\n\n"
        prompt += f"{account_data.get('positions', [])}\n\n"
        prompt += f"Sharpe Ratio: {account_data.get('sharpe_ratio', 0)}\n"
        
        return prompt
    
    # def generate_and_save_prompt(self, account_id: UUID) -> Optional[LLMPromptData]:
    #     """프롬프트 데이터 생성 및 저장 (LLM 관련 데이터 생성)"""
    #     try:
    #         # 기존 프롬프트 데이터 확인 (같은 시점에 생성된 것이 있는지)
    #         existing_prompt = self.db.query(LLMPromptData).filter(
    #             LLMPromptData.generated_at == self.simulation_time
    #         ).first()
            
    #         if existing_prompt:
    #             logger.info(f"✅ 기존 프롬프트 데이터 사용 (시점: {self.simulation_time}, ID: {existing_prompt.id})")
    #             return existing_prompt
            
    #         # 기존 데이터가 없으면 새로 생성
    #         market_data = {}
    #         for market in UpbitAPIConfig.MAIN_MARKETS:
    #             coin_data = self.data_querier.get_coin_data(market)
    #             market_data[market] = coin_data
            
    #         account_data = self.data_querier.get_account_data(account_id)
            
    #         indicator_config = {
    #             'ema_period': IndicatorsConfig.LLM_EMA_PERIOD,
    #             'ema_long_period': IndicatorsConfig.LLM_EMA_LONG_PERIOD,
    #             'macd_fast_period': IndicatorsConfig.LLM_MACD_FAST_PERIOD,
    #             'macd_slow_period': IndicatorsConfig.LLM_MACD_SLOW_PERIOD,
    #             'rsi_short_period': IndicatorsConfig.LLM_RSI_SHORT_PERIOD,
    #             'rsi_long_period': IndicatorsConfig.LLM_RSI_LONG_PERIOD,
    #             'atr_short_period': IndicatorsConfig.LLM_ATR_SHORT_PERIOD,
    #             'atr_long_period': IndicatorsConfig.LLM_ATR_LONG_PERIOD
    #         }
            
    #         trading_minutes = self.calculate_trading_minutes()
            
    #         prompt_text = self.generate_prompt_text(market_data, account_data, trading_minutes)
            
    #         prompt_data = LLMPromptData(
    #             generated_at=self.simulation_time,
    #             trading_minutes=trading_minutes,
    #             prompt_text=prompt_text,
    #             market_data_json=market_data,
    #             account_data_json=account_data,
    #             indicator_config_json=indicator_config
    #         )
            
    #         self.db.add(prompt_data)
    #         self.db.commit()
    #         self.db.refresh(prompt_data)
            
    #         logger.info(f"✅ 시뮬레이션 프롬프트 생성 완료 (시점: {self.simulation_time}, ID: {prompt_data.id})")
    #         return prompt_data
        
    #     except Exception as e:
    #         logger.error(f"❌ 프롬프트 생성 실패: {e}", exc_info=True)
    #         self.db.rollback()
    #         return None

    def generate_and_save(self, account_id: UUID) -> Optional[LLMPromptData]:
        """프롬프트 데이터 생성 및 저장 (LLM 관련 데이터 생성)"""
        try:
            market_data = {}
            for market in UpbitAPIConfig.MAIN_MARKETS:
                coin_data = self.data_querier.get_coin_data(market)
                market_data[market] = coin_data
            
            account_data = self.data_querier.get_account_data(account_id)
            
            indicator_config = {
                'ema_period': IndicatorsConfig.LLM_EMA_PERIOD,
                'ema_long_period': IndicatorsConfig.LLM_EMA_LONG_PERIOD,
                'macd_fast_period': IndicatorsConfig.LLM_MACD_FAST_PERIOD,
                'macd_slow_period': IndicatorsConfig.LLM_MACD_SLOW_PERIOD,
                'rsi_short_period': IndicatorsConfig.LLM_RSI_SHORT_PERIOD,
                'rsi_long_period': IndicatorsConfig.LLM_RSI_LONG_PERIOD,
                'atr_short_period': IndicatorsConfig.LLM_ATR_SHORT_PERIOD,
                'atr_long_period': IndicatorsConfig.LLM_ATR_LONG_PERIOD
            }
            
            trading_minutes = self.calculate_trading_minutes()
            
            prompt_text = self.generate_prompt_text(market_data, account_data, trading_minutes)
            
            prompt_data = LLMPromptData(
                generated_at=self.simulation_time,
                trading_minutes=trading_minutes,
                prompt_text=prompt_text,
                market_data_json=market_data,
                account_data_json=account_data,
                indicator_config_json=indicator_config
            )
            
            self.db.add(prompt_data)
            self.db.commit()
            self.db.refresh(prompt_data)
            
            logger.info(f"✅ 시뮬레이션 프롬프트 생성 완료 (시점: {self.simulation_time}, ID: {prompt_data.id})")
            return prompt_data
        
        except Exception as e:
            logger.error(f"❌ 프롬프트 생성 실패: {e}", exc_info=True)
            self.db.rollback()
            return None


class HistoricalTradingSimulator:
    """시뮬레이션용 거래 시뮬레이터"""
    
    def __init__(self, db: Session, simulation_time: datetime, account_id: UUID):
        self.db = db
        self.simulation_time = simulation_time
        self.account_id = account_id
        self.data_querier = HistoricalDataQuerier(db, simulation_time)
    
    def get_current_price(self, coin: str) -> Optional[Decimal]:
        """시뮬레이션 시점의 가격 조회 (조회만 수행)"""
        market = f"KRW-{coin.upper()}"
        price = self.data_querier.get_price_at_time(market)
        return Decimal(str(price)) if price else None
    
    def get_account_balance(self, currency: str) -> Decimal:
        """시뮬레이션 시점의 계좌 잔액 조회 (조회만 수행)"""
        account = self.db.query(UpbitAccounts).filter(
            UpbitAccounts.account_id == str(self.account_id),
            UpbitAccounts.currency == currency.upper(),
            UpbitAccounts.collected_at <= self.simulation_time
        ).order_by(desc(UpbitAccounts.collected_at)).first()
        
        if account and account.balance:
            return Decimal(str(account.balance))
        return Decimal("0")
    
    def initialize_account_if_needed(self, initial_capital: Decimal) -> bool:
        """계좌 초기화 (시뮬레이션용 계좌 생성)"""
        try:
            account_id_str = str(self.account_id)
            
            # KRW 계좌 확인
            krw_account = self.db.query(UpbitAccounts).filter(
                UpbitAccounts.account_id == account_id_str,
                UpbitAccounts.currency == "KRW"
            ).order_by(desc(UpbitAccounts.collected_at)).first()
            
            if krw_account:
                logger.info(f"✅ 계좌 {account_id_str}는 이미 존재합니다.")
                return True
            
            # 초기화: KRW 계좌 생성
            krw_account = UpbitAccounts(
                account_id=account_id_str,
                currency="KRW",
                balance=initial_capital,
                locked=Decimal("0"),
                avg_buy_price=Decimal("0"),
                avg_buy_price_modified=False,
                unit_currency="KRW",
                collected_at=self.simulation_time
            )
            self.db.add(krw_account)
            
            # 코인 계좌 생성
            for market in UpbitAPIConfig.MAIN_MARKETS:
                currency = market.split("-")[1]
                coin_account = UpbitAccounts(
                    account_id=account_id_str,
                    currency=currency,
                    balance=Decimal("0"),
                    locked=Decimal("0"),
                    avg_buy_price=Decimal("0"),
                    avg_buy_price_modified=False,
                    unit_currency="KRW",
                    collected_at=self.simulation_time
                )
                self.db.add(coin_account)
            
            self.db.commit()
            logger.info(f"✅ 계좌 {account_id_str} 초기화 완료 (KRW: {initial_capital:,})")
            return True
        
        except Exception as e:
            logger.error(f"❌ 계좌 초기화 실패: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    def execute_buy(self, coin: str, quantity: Decimal, price: Decimal) -> bool:
        """매수 실행 (시뮬레이션용 계좌 업데이트)"""
        try:
            coin = coin.upper()
            total_cost = quantity * price
            
            krw_balance = self.get_account_balance("KRW")
            if krw_balance < total_cost:
                logger.warning(f"⚠️ 매수 실패: 잔액 부족 (필요: {total_cost:,.0f} KRW, 보유: {krw_balance:,.0f} KRW)")
                return False
            
            # KRW 차감
            new_krw_balance = krw_balance - total_cost
            self._update_balance("KRW", new_krw_balance)
            
            # 코인 추가
            current_coin_balance = self.get_account_balance(coin)
            new_coin_balance = current_coin_balance + quantity
            
            # 평균 매수가 계산
            if current_coin_balance > 0:
                current_avg_price = self._get_avg_buy_price(coin)
                total_value = (current_coin_balance * current_avg_price) + total_cost
                avg_buy_price = total_value / new_coin_balance
            else:
                avg_buy_price = price
            
            self._update_balance(coin, new_coin_balance, avg_buy_price)
            
            logger.info(f"✅ 매수 성공: {quantity:.8f} {coin} @ {price:,.2f} KRW")
            return True
        
        except Exception as e:
            logger.error(f"❌ 매수 실행 실패: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    def execute_sell(self, coin: str, quantity: Decimal, price: Decimal) -> bool:
        """매도 실행 (시뮬레이션용 계좌 업데이트)"""
        try:
            coin = coin.upper()
            coin_balance = self.get_account_balance(coin)
            
            if coin_balance < quantity:
                logger.warning(f"⚠️ 매도 실패: 코인 부족 (필요: {quantity:.8f} {coin}, 보유: {coin_balance:.8f} {coin})")
                return False
            
            new_coin_balance = coin_balance - quantity
            self._update_balance(coin, new_coin_balance)
            
            total_revenue = quantity * price
            krw_balance = self.get_account_balance("KRW")
            new_krw_balance = krw_balance + total_revenue
            
            self._update_balance("KRW", new_krw_balance)
            
            logger.info(f"✅ 매도 성공: {quantity:.8f} {coin} @ {price:,.0f} KRW (총: {total_revenue:,.0f} KRW)")
            return True
        
        except Exception as e:
            logger.error(f"❌ 매도 실행 실패: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    def _update_balance(self, currency: str, new_balance: Decimal, avg_buy_price: Optional[Decimal] = None):
        """잔액 업데이트 (시뮬레이션용 계좌만 업데이트)"""
        try:
            account_id_str = str(self.account_id)
            
            account = self.db.query(UpbitAccounts).filter(
                UpbitAccounts.account_id == account_id_str,
                UpbitAccounts.currency == currency
            ).order_by(desc(UpbitAccounts.collected_at)).first()
            
            if account:
                avg_price = avg_buy_price if avg_buy_price is not None else account.avg_buy_price
            else:
                avg_price = avg_buy_price if avg_buy_price is not None else Decimal("0")
            
            new_account = UpbitAccounts(
                account_id=account_id_str,
                currency=currency,
                balance=new_balance,
                locked=Decimal("0"),
                avg_buy_price=avg_price,
                avg_buy_price_modified=False,
                unit_currency="KRW",
                collected_at=self.simulation_time
            )
            
            self.db.add(new_account)
            self.db.commit()
        
        except Exception as e:
            logger.error(f"❌ 잔액 업데이트 실패: {e}", exc_info=True)
            self.db.rollback()
            raise
    
    def _get_avg_buy_price(self, currency: str) -> Decimal:
        """평균 매수가 조회 (조회만 수행)"""
        account = self.db.query(UpbitAccounts).filter(
            UpbitAccounts.account_id == str(self.account_id),
            UpbitAccounts.currency == currency,
            UpbitAccounts.collected_at <= self.simulation_time
        ).order_by(desc(UpbitAccounts.collected_at)).first()
        
        if account and account.avg_buy_price:
            return Decimal(str(account.avg_buy_price))
        return Decimal("0")

        
    
    def _save_execution_record(
        self,
        prompt_id: int,
        coin: str,
        signal_type: str,
        execution_status: str,
        signal_created_at: Optional[datetime] = None,
        intended_price: Optional[Decimal] = None,
        executed_price: Optional[Decimal] = None,
        intended_quantity: Optional[Decimal] = None,
        executed_quantity: Optional[Decimal] = None,
        balance_before: Optional[Decimal] = None,
        balance_after: Optional[Decimal] = None,
        failure_reason: Optional[str] = None,
        confidence: Optional[Decimal] = None,
        justification: Optional[str] = None,
        thinking: Optional[str] = None,
        full_prompt: Optional[str] = None,
        full_response: Optional[str] = None,
    ):
        """거래 실행 기록 저장 (LLM 관련 데이터 생성)"""
        try:
            execution = LLMTradingExecution(
                prompt_id=prompt_id,
                account_id=self.account_id,
                coin=coin,
                signal_type=signal_type,
                execution_status=execution_status,
                failure_reason=failure_reason,
                intended_price=intended_price,
                executed_price=executed_price,
                intended_quantity=intended_quantity,
                executed_quantity=executed_quantity,
                balance_before=balance_before,
                balance_after=balance_after,
                signal_created_at=signal_created_at,
                confidence=confidence,
                justification=justification,
                thinking=thinking,
                full_prompt=full_prompt,
                full_response=full_response,
            )
            
            self.db.add(execution)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"❌ 실행 기록 저장 실패: {e}", exc_info=True)
            self.db.rollback()
    
    def execute_trade_signal(self, signal: LLMTradingSignal) -> bool:
        """거래 신호 실행 (시뮬레이션용 계좌 업데이트 및 LLM 실행 기록 생성)"""
        execution_record = {
            "prompt_id": signal.prompt_id,
            "coin": signal.coin,
            "signal_type": signal.signal,
            "signal_created_at": signal.created_at,
            "intended_price": signal.current_price,
            "confidence": _to_decimal(signal.confidence) if signal.confidence is not None else None,
            "justification": signal.justification,
            "thinking": signal.thinking,
            "full_prompt": signal.full_prompt,
            "full_response": signal.full_response,
        }
        
        try:
            signal_type = signal.signal.lower()
            
            # HOLD 신호 처리
            if "hold" in signal_type:
                logger.info(f"📊 HOLD 신호: {signal.coin}")
                self._save_execution_record(
                    **execution_record,
                    execution_status="skipped",
                    failure_reason="HOLD 신호"
                )
                return True
            
            # 가격 조회
            current_price = self.get_current_price(signal.coin)
            if not current_price:
                logger.error(f"❌ {signal.coin} 가격 조회 실패")
                self._save_execution_record(
                    **execution_record,
                    execution_status="failed",
                    failure_reason=f"{signal.coin} 가격 조회 실패"
                )
                return False
            
            execution_record["executed_price"] = current_price
            
            # quantity 검증
            if signal.quantity is None or Decimal(str(signal.quantity)) <= 0:
                logger.error(f"❌ quantity가 유효하지 않음: {signal.quantity}")
                self._save_execution_record(
                    **execution_record,
                    execution_status="failed",
                    failure_reason=f"quantity가 유효하지 않음: {signal.quantity}"
                )
                return False
            
            quantity = Decimal(str(signal.quantity))
            execution_record["intended_quantity"] = quantity
            
            # 거래 실행
            if "buy" in signal_type or "enter" in signal_type:
                # 매수 전 잔액
                balance_before = self.get_account_balance("KRW")
                execution_record["balance_before"] = balance_before
                
                success = self.execute_buy(signal.coin, quantity, current_price)
                
                if success:
                    balance_after = self.get_account_balance("KRW")
                    execution_record["balance_after"] = balance_after
                    execution_record["executed_quantity"] = quantity
                    self._save_execution_record(
                        **execution_record,
                        execution_status="success"
                    )
                else:
                    execution_record["balance_after"] = balance_before
                    execution_record["executed_quantity"] = Decimal("0")
                    self._save_execution_record(
                        **execution_record,
                        execution_status="failed",
                        failure_reason="매수 실행 실패"
                    )
                
                return success
            
            elif "sell" in signal_type or "exit" in signal_type:
                # 매도 전 잔액
                balance_before = self.get_account_balance(signal.coin)
                execution_record["balance_before"] = balance_before
                
                success = self.execute_sell(signal.coin, quantity, current_price)
                
                if success:
                    balance_after = self.get_account_balance(signal.coin)
                    execution_record["balance_after"] = balance_after
                    execution_record["executed_quantity"] = quantity
                    self._save_execution_record(
                        **execution_record,
                        execution_status="success"
                    )
                else:
                    execution_record["balance_after"] = balance_before
                    execution_record["executed_quantity"] = Decimal("0")
                    self._save_execution_record(
                        **execution_record,
                        execution_status="failed",
                        failure_reason="매도 실행 실패"
                    )
                
                return success
            
            else:
                logger.error(f"❌ 알 수 없는 신호 타입: {signal.signal}")
                self._save_execution_record(
                    **execution_record,
                    execution_status="failed",
                    failure_reason=f"알 수 없는 신호 타입: {signal.signal}"
                )
                return False
        
        except Exception as e:
            logger.error(f"❌ 거래 신호 실행 실패: {e}", exc_info=True)
            self._save_execution_record(
                **execution_record,
                execution_status="failed",
                failure_reason=f"예외 발생: {str(e)}"
            )
            return False




def _build_system_message(model_name: Optional[str] = None) -> str:
    """시스템 프롬프트 생성 (전략 포함)"""
    schema = TradeDecision.model_json_schema()
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
    
    strategy_prompt = ""
    if model_name:
        strategy_key = LLMAccountConfig.get_strategy_for_model(model_name)
        strategy_prompt = STRATEGY_PROMPTS.get(
            strategy_key, 
            STRATEGY_PROMPTS[TradingStrategy.NEUTRAL]
        )
    
    return f"""You are a trading decision assistant. You must respond with a valid JSON object that matches the following schema:

{schema_str}

IMPORTANT RULES:

**Required Fields:**
- "coin" (string): The cryptocurrency symbol (e.g., "BTC", "ETH")
- "signal" (string): One of: buy_to_enter, sell_to_exit, hold, close_position, buy, sell, exit

**Recommended Fields:**
- "justification" (string): Trade rationale based on market conditions
- "thinking" (string): Step-by-step reasoning process
- "confidence" (float 0.0-1.0): Confidence level in this decision

**Trading Parameters (REQUIRED for buy/sell signals ONLY):**
- "quantity" (float): Amount to trade (REQUIRED for buy_to_enter, sell_to_exit, buy, sell)
- "stop_loss" (float): Stop loss price (REQUIRED for buy_to_enter, sell_to_exit, buy, sell)
- "profit_target" (float): Target profit price (REQUIRED for buy_to_enter, sell_to_exit, buy, sell)
- "leverage" (int): MUST ALWAYS BE 1 (Upbit does not support leverage trading)
- "risk_usd" (float): Risk amount in USD (optional but recommended)

**CRITICAL: HOLD Signal Behavior:**
- When signal is "hold", you MUST set the following fields to null:
  - quantity: null
  - stop_loss: null
  - profit_target: null
  - risk_usd: null
  - invalidation_condition: null
- HOLD means "do nothing", so trading parameters are not needed
- Only provide justification, thinking, and confidence for HOLD signals

**Response Format:**
- Return ONLY the JSON object, nothing else
- Do not include the schema or any explanatory text

{strategy_prompt}"""

async def get_trade_decision_for_simulation(
    db: Session,
    prompt_data: LLMPromptData,
    model_name: Optional[str],
    account_id: UUID,
    simulation_time: datetime,
    extra_context: Optional[Dict[str, Any]] = None
) -> Optional[TradeDecision]:
    """시뮬레이션용 거래 결정 요청 (LLM 관련 데이터 생성)"""
    try:
        model = get_preferred_model_name(model_name)
        
        system_content = _build_system_message(model)  # model_name 전달
        user_content = f"""Here is the current market situation and account information:

## Prompt Text
{prompt_data.prompt_text}

## Extra Context
{json.dumps(extra_context, ensure_ascii=False, indent=2) if extra_context else "None"}

Based on the information above, please make a trading decision. You must respond in JSON format, and the "coin" and "signal" fields are mandatory."""        
        # ORPO 학습용 전체 프롬프트 구성 (System + User)
        full_prompt_for_training = f"""=== SYSTEM PROMPT ===
{system_content}

=== USER PROMPT ===
{user_content}
"""
        
        # vLLM API 호출 (오류 처리 포함)
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.error(f"❌ vLLM API 호출 실패: {e}")
            logger.error(f"   모델: {model}")
            logger.error(f"   System 메시지 길이: {len(system_content)} 문자")
            logger.error(f"   User 메시지 길이: {len(user_content)} 문자")
            raise
        
        # completion 타입 확인 및 처리 (문자열 반환 오류 처리)
        try:
            if isinstance(completion, str):
                logger.warning(f"⚠️ vLLM API가 문자열을 직접 반환했습니다. 문자열을 raw_content로 사용합니다.")
                raw_content = completion
            elif hasattr(completion, 'choices') and completion.choices:
                raw_content = completion.choices[0].message.content or ""
            else:
                logger.error(f"❌ completion 형식이 예상과 다릅니다.")
                logger.error(f"   타입: {type(completion)}")
                logger.error(f"   내용 (처음 200자): {str(completion)[:200]}")
                return None
        except AttributeError as e:
            logger.error(f"❌ completion에서 content 추출 실패: {e}")
            logger.error(f"   completion 타입: {type(completion)}")
            logger.error(f"   completion 내용 (처음 500자): {str(completion)[:500]}")
            return None
        
        # 빈 응답 체크
        if not raw_content or not raw_content.strip():
            logger.error(f"❌ vLLM API가 빈 응답을 반환했습니다.")
            return None
        
        full_response = raw_content  # 전체 응답 저장 (ORPO 학습용)
        
        thinking_part = None
        
        # 1) <thinking> 태그에서 추출 시도
        if "<thinking>" in raw_content:
            thinking_start = raw_content.find("<thinking>")
            thinking_end = raw_content.find("</thinking>") + len("</thinking>")
            thinking_part = raw_content[thinking_start:thinking_end]
        
        json_part = raw_content.split("</thinking>")[-1].strip() if "</thinking>" in raw_content else raw_content
        
        # ========== 1단계: JSON 파싱 ==========
        # JSON 파싱 (오류 처리 강화)
        if not json_part or not json_part.strip():
            logger.error(f"❌ JSON 파싱할 내용이 없습니다.")
            logger.error(f"Raw content (처음 500자): {raw_content[:500]}")
            return None
        
        try:
            decision_data = json.loads(json_part)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON 파싱 실패: {e}")
            logger.error(f"   JSON 파싱 시도한 내용 (처음 500자): {json_part[:500]}")
            logger.error(f"   전체 Raw content (처음 1000자): {raw_content[:1000]}")
            
            # JSON이 아닌 경우, JSON 부분만 추출 시도
            if "{" in json_part and "}" in json_part:
                json_start = json_part.find("{")
                json_end = json_part.rfind("}") + 1
                if json_start < json_end:
                    try:
                        json_part_extracted = json_part[json_start:json_end]
                        decision_data = json.loads(json_part_extracted)
                        logger.info(f"✅ JSON 추출 후 파싱 성공")
                    except json.JSONDecodeError:
                        logger.error(f"❌ JSON 추출 후에도 파싱 실패")
                        return None
                else:
                    return None
            else:
                return None
        
        # ========== 2단계: 배열/딕셔너리 형태 확인 및 리스트로 통일 ==========
        # 배열 형태인 경우 모든 요소 처리, 딕셔너리인 경우 리스트로 변환하여 통일된 처리
        decision_list = []
        if isinstance(decision_data, list):
            if len(decision_data) == 0:
                logger.error("❌ LLM 응답이 빈 배열입니다.")
                return None
            logger.info(f"📋 LLM 응답이 배열 형태입니다. 총 {len(decision_data)}개의 거래 결정을 처리합니다.")
            decision_list = decision_data
        elif isinstance(decision_data, dict):
            # 딕셔너리인 경우 리스트로 변환하여 통일된 처리
            logger.info(f"📋 LLM 응답이 딕셔너리 형태입니다. 1개의 거래 결정을 처리합니다.")
            decision_list = [decision_data]
        else:
            logger.error(f"❌ LLM 응답이 딕셔너리 또는 배열이 아닙니다. 타입: {type(decision_data)}")
            logger.error(f"응답 내용: {json.dumps(decision_data, ensure_ascii=False, indent=2)[:500]}")
            return None
        
        # ========== 3단계: 배열의 각 요소를 처리하고 저장 ==========
        saved_signals = []
        final_decision = None
        
        for idx, item_data in enumerate(decision_list):
            logger.info(f"📝 [{idx+1}/{len(decision_list)}] 거래 결정 처리 중...")
            
            # expected_response_schema 제거 (있을 경우)
            if "expected_response_schema" in item_data:
                item_data.pop("expected_response_schema")
            
            # thinking 추출 (각 요소별로)
            item_thinking = None
            # 1) <thinking> 태그에서 추출 시도 (공통 thinking_part 사용)
            if thinking_part:
                item_thinking = thinking_part
            # 2) JSON 내부의 thinking 필드도 확인 (태그가 없을 경우)
            elif "thinking" in item_data:
                item_thinking = item_data.get("thinking")
            
            # 필수 필드 확인
            if "coin" not in item_data or "signal" not in item_data:
                logger.error(f"❌ [{idx+1}] 필수 필드 누락: coin={item_data.get('coin')}, signal={item_data.get('signal')}. 건너뜁니다.")
                continue
            
            # Pydantic 검증
            try:
                validated_decision = TradeDecision(**item_data)
            except Exception as e:
                logger.error(f"❌ [{idx+1}] Pydantic 검증 실패: {e}. 건너뜁니다.")
                continue
            
            # 거래 결정 검증
            is_valid, validation_errors = validate_trade_decision(
                validated_decision,
                account_id,
                db,
                prompt_id=prompt_data.id,
                signal_created_at=simulation_time
            )
            
            if is_valid:
                logger.info(f"✅ [{idx+1}] 검증 통과! llm_trading_signal에 저장합니다.")
                
                # current_price 조회 (시뮬레이션 시점 기준) - HistoricalDataQuerier 사용
                coin_upper = validated_decision.coin.upper()
                market = f"KRW-{coin_upper}"
                current_price = None
                
                try:
                    data_querier = HistoricalDataQuerier(db, simulation_time)
                    price_float = data_querier.get_price_at_time(market)
                    if price_float:
                        current_price = _to_decimal(price_float)
                    else:
                        logger.warning(f"⚠️ [{idx+1}] {market} 가격 조회 실패: 데이터 없음")
                except Exception as e:
                    logger.warning(f"⚠️ [{idx+1}] 현재가 조회 실패: {e}")
                
                # 신호 저장 (LLM 관련 데이터 생성) - full_prompt, full_response, thinking 포함
                signal = LLMTradingSignal(
                    prompt_id=prompt_data.id,
                    account_id=account_id,
                    coin=coin_upper,
                    signal=validated_decision.signal,
                    current_price=current_price,
                    stop_loss=_to_decimal(validated_decision.stop_loss),
                    profit_target=_to_decimal(validated_decision.profit_target),
                    quantity=_to_decimal(validated_decision.quantity),
                    leverage=_to_decimal(validated_decision.leverage),
                    risk_usd=_to_decimal(validated_decision.risk_usd),
                    confidence=_to_decimal(validated_decision.confidence),
                    invalidation_condition=validated_decision.invalidation_condition,
                    justification=validated_decision.justification,
                    thinking=item_thinking,  # <thinking> 태그 또는 JSON 필드에서 추출
                    full_prompt=full_prompt_for_training,  # ORPO 학습용 전체 프롬프트
                    full_response=full_response,  # ORPO 학습용 전체 응답
                    created_at=simulation_time
                )
                
                db.add(signal)
                db.commit()
                db.refresh(signal)
                saved_signals.append(signal)
                final_decision = validated_decision  # 마지막으로 검증 통과한 결정을 최종 결정으로
                
                logger.info(
                    f"✅ [{idx+1}] LLM 거래 신호 저장 완료 (signal_id={signal.id}, coin={validated_decision.coin}, account_id={account_id})"
                )
            else:
                logger.warning(f"⚠️ [{idx+1}] 검증 실패: {validation_errors}")
                logger.info(f"📝 [{idx+1}] 검증 실패 기록은 llm_trading_execution에만 저장됩니다.")
        
        # ========== 4단계: 저장 결과 확인 ==========
        # 저장된 신호가 없으면 재요청 시도 (첫 번째 요소 기준으로 재요청)
        if not saved_signals:
            if len(decision_list) > 0:
                logger.warning(f"⚠️ 모든 거래 결정이 검증에 실패했습니다. 첫 번째 요소 기준으로 재요청을 시도합니다.")
                
                # 재요청은 첫 번째 요소 기준으로 진행 (단일 결정 재요청)
                first_item = decision_list[0]
                
                # 첫 번째 요소로 TradeDecision 생성 시도
                try:
                    first_decision = TradeDecision(**first_item)
                except Exception as e:
                    logger.error(f"❌ 첫 번째 요소로 TradeDecision 생성 실패: {e}")
                    return None
                
                # 재요청 프롬프트 생성
                retry_prompt_text = build_retry_prompt(
                    original_prompt=user_content,
                    rejection_reasons=["모든 거래 결정이 검증에 실패했습니다."],
                    original_decision=first_decision
                )
                
                # ========== 5단계: LLM에 재요청 ==========
                try:
                    logger.info("🔄 LLM 재요청 중...")
                    
                    retry_completion = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_content},
                            {"role": "user", "content": retry_prompt_text},
                        ],
                        temperature=0.0,
                        response_format={"type": "json_object"},
                    )
                    
                    # 재요청 응답 파싱
                    retry_raw_content = None
                    try:
                        if isinstance(retry_completion, str):
                            retry_raw_content = retry_completion
                        elif hasattr(retry_completion, 'choices') and retry_completion.choices:
                            retry_raw_content = retry_completion.choices[0].message.content or ""
                        else:
                            logger.error(f"❌ 재요청 completion 형식이 예상과 다릅니다.")
                            return None
                    except AttributeError as e:
                        logger.error(f"❌ 재요청 completion에서 content 추출 실패: {e}")
                        return None
                    
                    if not retry_raw_content or not retry_raw_content.strip():
                        logger.error(f"❌ 재요청 응답이 비어있습니다.")
                        return None
                    
                    # 재요청 thinking 추출
                    retry_thinking = None
                    if "<thinking>" in retry_raw_content:
                        thinking_start = retry_raw_content.find("<thinking>")
                        thinking_end = retry_raw_content.find("</thinking>") + len("</thinking>")
                        retry_thinking = retry_raw_content[thinking_start:thinking_end]
                    
                    retry_json_part = retry_raw_content.split("</thinking>")[-1].strip() if "</thinking>" in retry_raw_content else retry_raw_content
                    
                    # 재요청 JSON 파싱
                    try:
                        retry_decision_data = json.loads(retry_json_part)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ 재요청 JSON 파싱 실패: {e}")
                        logger.error(f"Retry raw content: {retry_raw_content[:500]}")
                        
                        # JSON 추출 시도
                        if "{" in retry_json_part and "}" in retry_json_part:
                            json_start = retry_json_part.find("{")
                            json_end = retry_json_part.rfind("}") + 1
                            if json_start < json_end:
                                try:
                                    retry_json_part_extracted = retry_json_part[json_start:json_end]
                                    retry_decision_data = json.loads(retry_json_part_extracted)
                                    logger.info(f"✅ 재요청 JSON 추출 후 파싱 성공")
                                except json.JSONDecodeError:
                                    logger.error(f"❌ 재요청 JSON 추출 후에도 파싱 실패")
                                    return None
                            else:
                                return None
                        else:
                            return None
                    
                    # ========== 6단계: 재요청 응답 배열/딕셔너리 형태 확인 및 리스트로 통일 ==========
                    # 재요청 응답이 배열 형태인 경우 모든 요소 처리
                    retry_decision_list = []
                    if isinstance(retry_decision_data, list):
                        if len(retry_decision_data) == 0:
                            logger.error("❌ 재요청 LLM 응답이 빈 배열입니다.")
                            return None
                        logger.info(f"📋 재요청 LLM 응답이 배열 형태입니다. 총 {len(retry_decision_data)}개의 거래 결정을 처리합니다.")
                        retry_decision_list = retry_decision_data
                    elif isinstance(retry_decision_data, dict):
                        logger.info(f"📋 재요청 LLM 응답이 딕셔너리 형태입니다. 1개의 거래 결정을 처리합니다.")
                        retry_decision_list = [retry_decision_data]
                    else:
                        logger.error(f"❌ 재요청 LLM 응답이 딕셔너리 또는 배열이 아닙니다. 타입: {type(retry_decision_data)}")
                        logger.error(f"응답 내용: {json.dumps(retry_decision_data, ensure_ascii=False, indent=2)[:500]}")
                        return None
                    
                    # ========== 7단계: 재요청 배열의 각 요소를 처리하고 저장 ==========
                    retry_saved_signals = []
                    retry_final_decision = None
                    
                    for retry_idx, retry_item_data in enumerate(retry_decision_list):
                        logger.info(f"📝 [재요청 {retry_idx+1}/{len(retry_decision_list)}] 거래 결정 처리 중...")
                        
                        # expected_response_schema 제거
                        if "expected_response_schema" in retry_item_data:
                            retry_item_data.pop("expected_response_schema")
                        
                        # 재요청에서 thinking 필드 확인
                        retry_item_thinking = None
                        if retry_thinking:
                            retry_item_thinking = retry_thinking
                        elif "thinking" in retry_item_data:
                            retry_item_thinking = retry_item_data.get("thinking")
                        
                        # 필수 필드 확인
                        if "coin" not in retry_item_data or "signal" not in retry_item_data:
                            logger.error(f"❌ [재요청 {retry_idx+1}] 필수 필드 누락: coin={retry_item_data.get('coin')}, signal={retry_item_data.get('signal')}. 건너뜁니다.")
                            continue
                        
                        # Pydantic 검증
                        try:
                            retry_decision = TradeDecision(**retry_item_data)
                        except Exception as e:
                            logger.error(f"❌ [재요청 {retry_idx+1}] Pydantic 검증 실패: {e}. 건너뜁니다.")
                            continue
                        
                        # 재요청 결과 검증
                        retry_is_valid, retry_validation_errors = validate_trade_decision(
                            retry_decision,
                            account_id,
                            db,
                            prompt_id=prompt_data.id,
                            signal_created_at=simulation_time
                        )
                        
                        if retry_is_valid:
                            logger.info(f"✅ [재요청 {retry_idx+1}] 검증 통과! llm_trading_signal에 저장합니다.")
                            
                            # current_price 조회 (시뮬레이션 시점 기준)
                            retry_coin_upper = retry_decision.coin.upper()
                            retry_market = f"KRW-{retry_coin_upper}"
                            retry_current_price = None
                            
                            try:
                                data_querier = HistoricalDataQuerier(db, simulation_time)
                                price_float = data_querier.get_price_at_time(retry_market)
                                if price_float:
                                    retry_current_price = _to_decimal(price_float)
                                else:
                                    logger.warning(f"⚠️ [재요청 {retry_idx+1}] {retry_market} 가격 조회 실패: 데이터 없음")
                            except Exception as e:
                                logger.warning(f"⚠️ [재요청 {retry_idx+1}] 현재가 조회 실패: {e}")
                            
                            # 재요청 신호 저장
                            retry_signal = LLMTradingSignal(
                                prompt_id=prompt_data.id,
                                account_id=account_id,
                                coin=retry_coin_upper,
                                signal=retry_decision.signal,
                                current_price=retry_current_price,
                                stop_loss=_to_decimal(retry_decision.stop_loss),
                                profit_target=_to_decimal(retry_decision.profit_target),
                                quantity=_to_decimal(retry_decision.quantity),
                                leverage=_to_decimal(retry_decision.leverage),
                                risk_usd=_to_decimal(retry_decision.risk_usd),
                                confidence=_to_decimal(retry_decision.confidence),
                                invalidation_condition=retry_decision.invalidation_condition,
                                justification=retry_decision.justification,
                                thinking=retry_item_thinking,
                                full_prompt=full_prompt_for_training,  # ORPO 학습용 전체 프롬프트
                                full_response=retry_raw_content,  # 재요청 응답으로 업데이트
                                created_at=simulation_time
                            )
                            
                            db.add(retry_signal)
                            db.commit()
                            db.refresh(retry_signal)
                            retry_saved_signals.append(retry_signal)
                            retry_final_decision = retry_decision
                            
                            logger.info(
                                f"✅ [재요청 {retry_idx+1}] LLM 거래 신호 저장 완료 (signal_id={retry_signal.id}, coin={retry_decision.coin}, account_id={account_id})"
                            )
                        else:
                            logger.warning(f"⚠️ [재요청 {retry_idx+1}] 검증 실패: {retry_validation_errors}. 건너뜁니다.")
                    
                    # ========== 8단계: 재요청 저장 결과 확인 ==========
                    if not retry_saved_signals:
                        logger.error(f"❌ 재요청도 모든 거래 결정이 검증에 실패했습니다.")
                        return None
                    
                    logger.info(f"✅ 재요청으로 총 {len(retry_saved_signals)}개의 거래 신호가 저장되었습니다.")
                    final_decision = retry_final_decision
                    
                except Exception as e:
                    logger.error(f"❌ 재요청 실패: {e}", exc_info=True)
                    return None
            else:
                # decision_list가 비어있는 경우
                logger.error("❌ 처리할 거래 결정이 없습니다.")
                return None
        
        # ========== 9단계: 최종 결과 반환 ==========
        # 저장된 신호가 있는 경우 최종 결정 반환
        if saved_signals:
            logger.info(f"✅ 총 {len(saved_signals)}개의 거래 신호가 저장되었습니다.")
            logger.debug(f"   thinking 길이: {len(thinking_part) if thinking_part else 0} 문자")
            logger.debug(f"   full_prompt 길이: {len(full_prompt_for_training)} 문자")
            logger.debug(f"   full_response 길이: {len(full_response)} 문자")
            return final_decision
        else:
            # 재요청에서 저장된 경우는 위에서 처리됨
            return None
    
    except Exception as e:
        logger.error(f"❌ 거래 결정 요청 실패: {e}", exc_info=True)
        db.rollback()
        return None


class HistoricalSimulator:
    """과거 데이터 기반 시뮬레이터 메인 클래스"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.start_time = config["start_time"]
        self.end_time = config["end_time"]
        self.interval_minutes = config["interval_minutes"]
        self.model_name = config.get("model_name")
        self.account_id = SIMULATION_ACCOUNT_ID
        self.initial_capital = config["initial_capital"]
        
        self.stats = {
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "hold_signals": 0,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
    
    def generate_simulation_times(self) -> List[datetime]:
        """시뮬레이션 시점 리스트 생성"""
        times = []
        current = self.start_time
        while current <= self.end_time:
            times.append(current)
            current += timedelta(minutes=self.interval_minutes)
        return times
    
    async def run_simulation(self):
        """시뮬레이션 실행"""
        logger.info("=" * 80)
        logger.info("🚀 과거 데이터 기반 거래 시뮬레이션 시작")
        logger.info(f"   시작 시점: {self.start_time}")
        logger.info(f"   종료 시점: {self.end_time}")
        logger.info(f"   간격: {self.interval_minutes}분")
        logger.info(f"   계좌 ID: {self.account_id}")
        logger.info("=" * 80)
        
        simulation_times = self.generate_simulation_times()
        total_steps = len(simulation_times)
        
        logger.info(f"📊 총 {total_steps}개 시점에서 시뮬레이션 실행 예정")
        
        db = SessionLocal()
        try:
            # 계좌 초기화 (시작 시점 기준)
            simulator = HistoricalTradingSimulator(db, self.start_time, self.account_id)
            if not simulator.initialize_account_if_needed(self.initial_capital):
                logger.error("❌ 계좌 초기화 실패")
                return
            
            logger.info(f"✅ 계좌 초기화 완료 (초기 자본금: {self.initial_capital:,} KRW)")
            
            # 시뮬레이션 실행
            for step, sim_time in enumerate(simulation_times, 1):
                logger.info("-" * 80)
                logger.info(f"[{step}/{total_steps}] 시뮬레이션 시점: {sim_time}")
                
                try:
                    # 1. 프롬프트 생성 (LLM 관련 데이터 생성)
                    prompt_generator = HistoricalPromptGenerator(
                        db, sim_time, self.start_time
                    )
                    prompt_data = prompt_generator.generate_and_save(self.account_id)
                    
                    if not prompt_data:
                        logger.warning(f"⚠️ 프롬프트 생성 실패, 건너뜀")
                        continue
                    
                    # 2. LLM에게 거래 결정 요청 (LLM 관련 데이터 생성)
                    decision = await get_trade_decision_for_simulation(
                        db, prompt_data, self.model_name, self.account_id, sim_time
                    )
                    
                    if not decision:
                        logger.warning(f"⚠️ 거래 결정 실패, 건너뜀")
                        continue
                    
                    # 3. 거래 실행 (시뮬레이션용 계좌 업데이트 및 LLM 실행 기록 생성)
                    trading_simulator = HistoricalTradingSimulator(db, sim_time, self.account_id)
                    
                    # 저장된 모든 신호 조회 (여러 신호가 저장되었을 수 있음)
                    signals = db.query(LLMTradingSignal).filter(
                        LLMTradingSignal.prompt_id == prompt_data.id,
                        LLMTradingSignal.account_id == self.account_id
                    ).order_by(desc(LLMTradingSignal.created_at)).all()
                    
                    if signals:
                        logger.info(f"📋 저장된 신호 개수: {len(signals)}개")
                        # 모든 신호 처리 (배열 처리 로직 지원)
                        for signal in signals:
                            if "hold" in signal.signal.lower():
                                self.stats["hold_signals"] += 1
                                logger.info(f"📊 HOLD 신호: {signal.coin} - 거래하지 않음")
                            else:
                                self.stats["total_trades"] += 1
                                success = trading_simulator.execute_trade_signal(signal)
                                if success:
                                    self.stats["successful_trades"] += 1
                                else:
                                    self.stats["failed_trades"] += 1
                    else:
                        logger.warning(f"⚠️ 저장된 신호가 없습니다. (prompt_id: {prompt_data.id})")
                    
                    # # 4. account_information 저장 (거래 실행 후 계좌 정보 갱신 시 저장)
                    # try:
                    #     save_simulation_account_information(db, self.account_id, sim_time)
                    # except Exception as e:
                    #     logger.warning(f"⚠️ account_information 저장 실패 (건너뜀): {e}")
              
                    # 진행 상황 로깅
                    if step % 10 == 0:
                        logger.info(f"📈 진행 상황: {step}/{total_steps} ({step*100//total_steps}%)")
                
                except Exception as e:
                    logger.error(f"❌ 시뮬레이션 단계 오류: {e}", exc_info=True)
                    continue
            
            # 최종 통계
            self._print_final_stats(db)
        
        finally:
            db.close()
    
    def _print_final_stats(self, db: Session):
        """최종 통계 출력"""
        logger.info("=" * 80)
        logger.info("📊 시뮬레이션 최종 통계")
        logger.info("=" * 80)
        
        # 계좌 최종 상태
        final_simulator = HistoricalTradingSimulator(
            db, self.end_time, self.account_id
        )
        
        krw_balance = final_simulator.get_account_balance("KRW")
        total_value = float(krw_balance)
        
        for market in UpbitAPIConfig.MAIN_MARKETS:
            currency = market.split("-")[1]
            coin_balance = final_simulator.get_account_balance(currency)
            if coin_balance > 0:
                price = final_simulator.get_current_price(currency)
                if price:
                    total_value += float(coin_balance * price)
        
        profit_loss = total_value - float(self.initial_capital)
        profit_loss_rate = (profit_loss / float(self.initial_capital)) * 100
        
        logger.info(f"초기 자본금: {self.initial_capital:,.0f} KRW")
        logger.info(f"최종 자산: {total_value:,.0f} KRW")
        logger.info(f"손익: {profit_loss:+,.0f} KRW ({profit_loss_rate:+.2f}%)")
        logger.info(f"총 거래 횟수: {self.stats['total_trades']}")
        logger.info(f"성공: {self.stats['successful_trades']}")
        logger.info(f"실패: {self.stats['failed_trades']}")
        logger.info(f"HOLD 신호: {self.stats['hold_signals']}")
        logger.info("=" * 80)


def parse_arguments():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(description="과거 데이터 기반 거래 시뮬레이션")
    parser.add_argument(
        "--start",
        type=str,
        help="시작 시점 (YYYY-MM-DD HH:MM:SS, UTC)",
        default=None
    )
    parser.add_argument(
        "--end",
        type=str,
        help="종료 시점 (YYYY-MM-DD HH:MM:SS, UTC)",
        default=None
    )
    parser.add_argument(
        "--interval",
        type=int,
        help="간격 (분 단위, 기본값: 3)",
        default=3
    )
    parser.add_argument(
        "--model",
        type=str,
        help="사용할 LLM 모델명 (기본값: 설정 파일의 기본값)",
        default=None
    )
    
    return parser.parse_args()


def main():
    """메인 함수"""
    args = parse_arguments()
    
    # 설정 업데이트
    config = SIMULATION_CONFIG.copy()
    
    if args.start:
        try:
            config["start_time"] = datetime.strptime(args.start, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            logger.error(f"❌ 시작 시점 형식 오류: {args.start} (예: 2024-01-01 00:00:00)")
            return
    
    if args.end:
        try:
            config["end_time"] = datetime.strptime(args.end, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            logger.error(f"❌ 종료 시점 형식 오류: {args.end} (예: 2024-01-31 23:59:59)")
            return
    
    if args.interval:
        config["interval_minutes"] = args.interval
    
    if args.model:
        config["model_name"] = args.model
    
    # 시뮬레이션 실행
    simulator = HistoricalSimulator(config)
    asyncio.run(simulator.run_simulation())


if __name__ == "__main__":
    main()
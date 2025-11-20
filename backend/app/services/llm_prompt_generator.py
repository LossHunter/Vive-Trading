"""
LLM 프롬프트 생성 모듈
기존 DB 데이터를 기반으로 LLM에게 보낼 프롬프트를 생성합니다.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import UpbitAPIConfig, IndicatorsConfig, LLMPromptConfig
from app.db.database import (
    UpbitTicker, UpbitCandlesMinute3, UpbitDayCandles,
    UpbitIndicators, UpbitRSI, UpbitAccounts, LLMPromptData, SessionLocal
)
from app.core.schedule_utils import calculate_wait_seconds_until_next_scheduled_time
# 계산 로직은 indicators_calculator.py에서 처리하므로 import 불필요

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 전역 서버 시작 시간 (서버 시작 시 설정됨)
_server_start_time: Optional[datetime] = None


def set_server_start_time(start_time: datetime) -> None:
    """
    서버 시작 시간 설정 (전역 변수)
    
    Args:
        start_time: 서버 시작 시각 (UTC)
    """
    global _server_start_time
    _server_start_time = start_time
    logger.info(f"서버 시작 시간 설정: {start_time}")


def get_server_start_time() -> Optional[datetime]:
    """
    서버 시작 시간 조회
    
    Returns:
        datetime | None: 서버 시작 시각 (UTC), 설정되지 않았으면 None
    """
    return _server_start_time


# 전역 서버 시작 시간 (서버 시작 시 설정됨)
_server_start_time: Optional[datetime] = None


def set_server_start_time(start_time: datetime) -> None:
    """
    서버 시작 시간 설정 (전역 변수)
    
    Args:
        start_time: 서버 시작 시각 (UTC)
    """
    global _server_start_time
    _server_start_time = start_time
    logger.info(f"서버 시작 시간 설정: {start_time}")


def get_server_start_time() -> Optional[datetime]:
    """
    서버 시작 시간 조회
    
    Returns:
        datetime | None: 서버 시작 시각 (UTC), 설정되지 않았으면 None
    """
    return _server_start_time


class LLMPromptGenerator:
    """LLM 프롬프트 생성 클래스"""
    
    def __init__(self, db: Session, trading_start_time: Optional[datetime] = None):
        """
        초기화
        
        Args:
            db: 데이터베이스 세션
            trading_start_time: 거래 시작 시각 (None이면 현재 시각에서 2399분 전으로 설정)
        """
        self.db = db
        if trading_start_time is None:
            # 전역 서버 시작 시간이 설정되어 있으면 사용, 없으면 기본값 사용
            global _server_start_time
            if _server_start_time is not None:
                self.trading_start_time = _server_start_time
            else:
                # 기본값: 현재 시각에서 2399분 전
                self.trading_start_time = datetime.now(timezone.utc) - timedelta(minutes=2399)
        else:
            self.trading_start_time = trading_start_time

    def calculate_trading_minutes(self) -> int:
        """거래 시작 후 경과 시간(분) 계산"""
        elapsed = datetime.now(timezone.utc) - self.trading_start_time
        return int(elapsed.total_seconds() / 60)
    
    def get_current_price(self, market: str) -> Optional[float]:
        """현재가 조회"""
        ticker = self.db.query(UpbitTicker).filter(
            UpbitTicker.market == market
        ).order_by(desc(UpbitTicker.collected_at)).first()
        
        if ticker and ticker.trade_price:
            return float(ticker.trade_price)
        return None
    
    def get_intraday_series(self, market: str, count: int = 10) -> Dict:
        """
        3분봉 인트라데이 시리즈 데이터 조회
        upbit_indicators 및 upbit_rsi 테이블에서 저장된 지표를 조회합니다.
        
        Returns:
            Dict: mid_prices, ema_indicators, macd_indicators, rsi_indicators_7, rsi_indicators_14
        """
        # 최근 count개의 3분봉 캔들 조회
        candles = self.db.query(UpbitCandlesMinute3).filter(
            UpbitCandlesMinute3.market == market
        ).order_by(desc(UpbitCandlesMinute3.candle_date_time_utc)).limit(count).all()
        
        candles = list(reversed(candles))  # 오래된 것부터 정렬
        
        if len(candles) < count:
            logger.warning(f"⚠️ {market} 인트라데이 데이터 부족: {len(candles)}개 < {count}개 필요")
        
        # Mid prices 계산 (고가+저가)/2
        mid_prices = []
        for candle in candles:
            if candle.high_price and candle.low_price:
                mid = (float(candle.high_price) + float(candle.low_price)) / 2
                mid_prices.append(mid)
            elif candle.trade_price:
                mid_prices.append(float(candle.trade_price))
            else:
                mid_prices.append(0.0)
        
        # upbit_indicators 테이블에서 저장된 지표 조회 (3분봉)
        indicators_from_db = self.db.query(UpbitIndicators).filter(
            UpbitIndicators.market == market,
            UpbitIndicators.interval == 'minute3'
        ).order_by(desc(UpbitIndicators.candle_date_time_utc)).limit(count).all()
        
        indicators_from_db = list(reversed(indicators_from_db))  # 오래된 것부터 정렬
        
        # MACD indicators: DB에서 조회 (최대 10개)
        MAX_INDICATOR_COUNT = 10
        macd_indicators = []
        if indicators_from_db:
            for indicator in indicators_from_db:
                if indicator.macd is not None:
                    macd_indicators.append(float(indicator.macd))
        macd_indicators = macd_indicators[-MAX_INDICATOR_COUNT:]  # 최대 10개로 제한
        
        # EMA(20) indicators: DB에서 조회 (최대 10개)
        ema_indicators = []
        if indicators_from_db:
            for indicator in indicators_from_db:
                if indicator.ema20 is not None:
                    ema_indicators.append(float(indicator.ema20))
        ema_indicators = ema_indicators[-MAX_INDICATOR_COUNT:]  # 최대 10개로 제한
        
        # RSI(14): upbit_rsi 테이블에서 조회 (3분봉 캔들 시각과 일치하는 RSI만)
        # 3분봉 RSI는 3분봉 캔들 시각과 일치하는 데이터만 조회
        rsi_indicators_14 = []
        if candles:
            # 3분봉 캔들 시각 목록 추출
            candle_times = [candle.candle_date_time_utc for candle in candles]
            
            # 해당 시각들과 일치하는 RSI만 조회 (3분봉 RSI)
            rsi_from_db_14 = self.db.query(UpbitRSI).filter(
                UpbitRSI.market == market,
                UpbitRSI.period == IndicatorsConfig.LLM_RSI_LONG_PERIOD,
                UpbitRSI.interval == 'minute3',
                UpbitRSI.candle_date_time_utc.in_(candle_times)
            ).order_by(desc(UpbitRSI.candle_date_time_utc)).limit(count).all()
            
            rsi_from_db_14 = list(reversed(rsi_from_db_14))  # 오래된 것부터 정렬
            for rsi in rsi_from_db_14:
                if rsi.rsi is not None:
                    rsi_indicators_14.append(float(rsi.rsi))
            rsi_indicators_14 = rsi_indicators_14[-MAX_INDICATOR_COUNT:]  # 최대 10개로 제한
        
        # RSI(7): upbit_rsi 테이블에서 조회 (3분봉 캔들 시각과 일치하는 RSI만)
        rsi_indicators_7 = []
        if candles:
            # 3분봉 캔들 시각 목록 추출
            candle_times = [candle.candle_date_time_utc for candle in candles]
            
            # 해당 시각들과 일치하는 RSI만 조회 (3분봉 RSI)
            rsi_from_db_7 = self.db.query(UpbitRSI).filter(
                UpbitRSI.market == market,
                UpbitRSI.period == IndicatorsConfig.LLM_RSI_SHORT_PERIOD,
                UpbitRSI.interval == 'minute3',
                UpbitRSI.candle_date_time_utc.in_(candle_times)
            ).order_by(desc(UpbitRSI.candle_date_time_utc)).limit(count).all()
            
            rsi_from_db_7 = list(reversed(rsi_from_db_7))  # 오래된 것부터 정렬
            for rsi in rsi_from_db_7:
                if rsi.rsi is not None:
                    rsi_indicators_7.append(float(rsi.rsi))
            rsi_indicators_7 = rsi_indicators_7[-MAX_INDICATOR_COUNT:]  # 최대 10개로 제한
        
        # Mid prices도 최대 10개로 제한
        mid_prices = mid_prices[-MAX_INDICATOR_COUNT:]
        
        return {
            'mid_prices': mid_prices,
            'ema_indicators': ema_indicators,
            'macd_indicators': macd_indicators,
            'rsi_indicators_7': rsi_indicators_7,
            'rsi_indicators_14': rsi_indicators_14
        }
    
    def get_longer_term_context(self, market: str) -> Dict:
        """
        4시간봉 장기 컨텍스트 데이터 조회
        upbit_indicators 및 upbit_rsi 테이블에서 저장된 지표를 조회합니다.
        
        Returns:
            Dict: ema20, ema50, atr3, atr14, volume, avg_volume, macd_indicators, rsi_indicators_14
        """
        # 일봉 데이터를 4시간봉으로 간주 (근사치)
        # 최근 50개 일봉 조회
        day_candles = self.db.query(UpbitDayCandles).filter(
            UpbitDayCandles.market == market
        ).order_by(desc(UpbitDayCandles.candle_date_time_utc)).limit(50).all()
        
        day_candles = list(reversed(day_candles))  # 오래된 것부터 정렬
        
        if len(day_candles) < 50:
            logger.warning(f"⚠️ {market} 장기 데이터 부족: {len(day_candles)}개 < 50개 필요")
        
        volumes = []
        for candle in day_candles:
            if candle.candle_acc_trade_volume:
                volumes.append(float(candle.candle_acc_trade_volume))
            else:
                volumes.append(0.0)
        
        # upbit_indicators 테이블에서 저장된 지표 조회 (일봉)
        indicators_from_db = self.db.query(UpbitIndicators).filter(
            UpbitIndicators.market == market,
            UpbitIndicators.interval == 'day'
        ).order_by(desc(UpbitIndicators.candle_date_time_utc)).limit(50).all()
        
        indicators_from_db = list(reversed(indicators_from_db))  # 오래된 것부터 정렬
        
        # ATR(14): DB에서 최신 값 조회
        atr14 = None
        if indicators_from_db and indicators_from_db[-1].atr14 is not None:
            atr14 = float(indicators_from_db[-1].atr14)
        
        # ATR(3): DB에서 최신 값 조회
        atr3 = None
        if indicators_from_db and indicators_from_db[-1].atr3 is not None:
            atr3 = float(indicators_from_db[-1].atr3)
        
        # EMA(20): DB에서 최신 값 조회
        ema20 = None
        if indicators_from_db and indicators_from_db[-1].ema20 is not None:
            ema20 = float(indicators_from_db[-1].ema20)
        
        # EMA(50): DB에서 최신 값 조회
        ema50 = None
        if indicators_from_db and indicators_from_db[-1].ema50 is not None:
            ema50 = float(indicators_from_db[-1].ema50)
        
        # Volume 및 Average Volume
        if volumes:
            current_volume = volumes[-1]
            avg_volume = sum(volumes) / len(volumes)
        else:
            current_volume = 0.0
            avg_volume = 0.0
        
        # MACD indicators (시리즈): DB에서 조회 (최대 10개)
        MAX_INDICATOR_COUNT = 10
        macd_indicators = []
        if indicators_from_db:
            for indicator in indicators_from_db:
                if indicator.macd is not None:
                    macd_indicators.append(float(indicator.macd))
        macd_indicators = macd_indicators[-MAX_INDICATOR_COUNT:]  # 최대 10개로 제한
        
        # RSI(14) indicators (시리즈): upbit_rsi 테이블에서 조회 (일봉 캔들 시각과 일치하는 RSI만)
        # 일봉 RSI는 일봉 캔들 시각(자정)과 일치하는 데이터만 조회
        rsi_indicators_14 = []
        if day_candles:
            # 일봉 캔들 시각 목록 추출
            day_candle_times = [candle.candle_date_time_utc for candle in day_candles]
            
            # 해당 시각들과 일치하는 RSI만 조회 (일봉 RSI)
            rsi_from_db = self.db.query(UpbitRSI).filter(
                UpbitRSI.market == market,
                UpbitRSI.period == IndicatorsConfig.LLM_RSI_LONG_PERIOD,
                UpbitRSI.interval == 'day',
                UpbitRSI.candle_date_time_utc.in_(day_candle_times)
            ).order_by(desc(UpbitRSI.candle_date_time_utc)).limit(MAX_INDICATOR_COUNT).all()
            
            rsi_from_db = list(reversed(rsi_from_db))  # 오래된 것부터 정렬
            for rsi in rsi_from_db:
                if rsi.rsi is not None:
                    rsi_indicators_14.append(float(rsi.rsi))
            rsi_indicators_14 = rsi_indicators_14[-MAX_INDICATOR_COUNT:]  # 최대 10개로 제한
        
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
        """
        특정 코인의 모든 데이터 수집
        현재가, 기술 지표(EMA, MACD, RSI), 인트라데이 시리즈, 장기 컨텍스트 등을 조회합니다.
        upbit_indicators 테이블에서 저장된 지표를 우선 사용하며, 없으면 실시간 계산합니다.
        
        Args:
            market: 마켓 코드 (예: "KRW-BTC")
        
        Returns:
            Dict: 다음 키를 포함한 딕셔너리
                - market: 마켓 코드
                - current_price: 현재가
                - current_ema20: 현재 EMA(20) 값
                - current_macd: 현재 MACD 값
                - current_rsi7: 현재 RSI(7) 값
                - intraday_series: 3분봉 기반 인트라데이 시리즈 데이터
                - longer_term_context: 일봉 기반 장기 컨텍스트 데이터
                - open_interest_latest: 최신 미결제약정 (현재 None, 외부 데이터 소스 필요)
                - open_interest_avg: 평균 미결제약정 (현재 None)
                - funding_rate: 펀딩비 (현재 None, 외부 데이터 소스 필요)
        """
        current_price = self.get_current_price(market)
        
        # 인트라데이 시리즈 조회 (DB 우선 사용)
        from app.core.config import ScriptConfig
        intraday_series = self.get_intraday_series(market, count=ScriptConfig.DEFAULT_INTRADAY_SERIES_COUNT)
        
        # 현재 지표 값 (인트라데이 시리즈의 최신 값 사용)
        current_ema20 = None
        if intraday_series['ema_indicators']:
            current_ema20 = intraday_series['ema_indicators'][-1]
        
        # MACD: DB에서 최신 값 조회 시도
        current_macd = None
        if intraday_series['macd_indicators']:
            current_macd = intraday_series['macd_indicators'][-1]
        else:
            # DB에 없으면 최신 지표에서 조회
            latest_indicator = self.db.query(UpbitIndicators).filter(
                UpbitIndicators.market == market,
                UpbitIndicators.interval == 'minute3'
            ).order_by(desc(UpbitIndicators.candle_date_time_utc)).first()
            if latest_indicator and latest_indicator.macd is not None:
                current_macd = float(latest_indicator.macd)
        
        # RSI(7): 인트라데이 시리즈에서 최신 값 사용
        current_rsi7 = None
        if intraday_series['rsi_indicators_7']:
            current_rsi7 = intraday_series['rsi_indicators_7'][-1]
        
        # 장기 컨텍스트 조회 (DB 우선 사용)
        longer_term = self.get_longer_term_context(market)
        
        # Open Interest 및 Funding Rate는 Upbit에서 제공하지 않으므로 None으로 설정
        # (실제로는 다른 데이터 소스가 필요)
        open_interest_latest = None
        open_interest_avg = None
        funding_rate = None
        
        return {
            'market': market,
            'current_price': current_price,
            'current_ema20': current_ema20,
            'current_macd': current_macd,
            'current_rsi7': current_rsi7,
            'intraday_series': intraday_series,
            'longer_term_context': longer_term,
            'open_interest_latest': open_interest_latest,
            'open_interest_avg': open_interest_avg,
            'funding_rate': funding_rate
        }
    
    def get_account_data(self) -> Dict:
        """
        계정 정보 및 성과 데이터 조회
        DB에서 실제 계정 데이터를 조회하여 현금 잔액, 포지션 정보, 손익 등을 계산합니다.
        
        Returns:
            Dict: 다음 키를 포함한 딕셔너리
                - current_total_return_percent: 현재 총 수익률 (%, 초기 가치 기준 필요)
                - available_cash: 사용 가능한 현금(KRW) 잔액
                - current_account_value: 현재 계정 총 가치 (현금 + 포지션 평가액)
                - positions: 현재 보유 포지션 리스트 (코인별 수량, 평균 매수가, 현재가, 손익 등)
                - sharpe_ratio: 샤프 비율 (현재 0, 과거 수익률 데이터 필요)
        
        Note:
            - 초기 투자금액이 별도로 저장되어 있지 않아 total_return_percent는 0으로 설정됩니다.
            - Sharpe Ratio 계산을 위해서는 일일 수익률의 표준편차와 평균이 필요합니다.
        """
        from app.db.database import UpbitTicker
        from app.core.config import UpbitAPIConfig
        
        # 최신 계정 데이터 조회
        accounts = self.db.query(UpbitAccounts).order_by(
            desc(UpbitAccounts.collected_at)
        ).all()
        
        # KRW 잔액 조회
        available_cash = 0.0
        for account in accounts:
            if account.currency and account.currency.upper() == 'KRW' and account.balance:
                available_cash = float(account.balance)
                break
        
        # 각 코인의 현재가 조회
        ticker_prices = {}
        for market in UpbitAPIConfig.MAIN_MARKETS:
            ticker = self.db.query(UpbitTicker).filter(
                UpbitTicker.market == market
            ).order_by(desc(UpbitTicker.collected_at)).first()
            
            if ticker and ticker.trade_price:
                currency = market.split("-")[1] if "-" in market else market
                ticker_prices[currency] = float(ticker.trade_price)
        
        # 포지션 정보 수집 (코인 보유량)
        positions = []
        total_value = available_cash  # 현금부터 시작
        
        seen_currencies = set()
        for account in accounts:
            if not account.currency:
                continue
            
            currency = account.currency.upper()
            if currency in seen_currencies:
                continue
            seen_currencies.add(currency)
            
            # KRW는 포지션이 아니므로 제외
            if currency == 'KRW':
                continue
            
            balance = float(account.balance) if account.balance else 0.0
            avg_buy_price = float(account.avg_buy_price) if account.avg_buy_price else 0.0
            current_price = ticker_prices.get(currency, 0.0)
            
            if balance > 0:
                # 손익 계산
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
                
                # 총 계정 가치에 추가
                total_value += current_price * balance
        
        # Total Return 계산
        # 초기 투자금액이 필요하지만, 여기서는 간단히 현재 가치 기준으로 계산
        # 실제로는 거래 시작 시점의 초기 가치가 필요함
        initial_value = total_value  # TODO: 거래 시작 시점의 초기 가치를 별도로 저장해야 함
        total_return_percent = 0.0  # 초기 가치가 없으면 0으로 설정
        
        # Sharpe Ratio 계산
        # 실제로는 일일 수익률의 표준편차와 평균이 필요하므로 여기서는 0으로 설정
        sharpe_ratio = 0.0  # TODO: 과거 수익률 데이터를 기반으로 계산 필요
        
        return {
            'current_total_return_percent': total_return_percent,
            'available_cash': available_cash,
            'current_account_value': total_value,
            'positions': positions,
            'sharpe_ratio': sharpe_ratio
        }
    
    @staticmethod
    def generate_prompt_text_from_data(market_data: Dict, account_data: Dict, trading_minutes: int) -> str:
        """
        저장된 데이터를 기반으로 프롬프트 텍스트 생성
        llm_prompt_data 테이블에서 조회한 데이터를 파싱하여 프롬프트 텍스트를 생성합니다.
        
        Args:
            market_data: 시장 데이터 JSON
            account_data: 계정 데이터 JSON
            trading_minutes: 거래 시작 후 경과 시간 (분)
        
        Returns:
            str: 생성된 프롬프트 텍스트
        """
        from app.core.config import UpbitAPIConfig
        
        prompt = f"It has been {trading_minutes} minute since you started trading.\n\n"
        prompt += "…\n\n"
        prompt += "Below, we are providing you with a variety of state data, price data, and predictive signals so you can discover alpha. "
        prompt += "Below that is your current account information, value, performance, positions, etc.\n\n"
        prompt += "**ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST**\n\n"
        prompt += "**Timeframes note:** Unless stated otherwise in a section title, intraday series are provided at **3‑minute intervals**. "
        prompt += "If a coin uses a different interval, it is explicitly stated in that coin's section.\n\n"
        prompt += "---\n\n"
        prompt += "### CURRENT MARKET STATE FOR ALL COINS\n\n"
        
        # 각 코인 데이터 추가
        for market in UpbitAPIConfig.MAIN_MARKETS:
            coin_data = market_data.get(market, {})
            if not coin_data:
                continue
            
            if '-' in market:
                coin_name = market.split('-')[1]
            else:
                coin_name = market
            
            prompt += f"### ALL {coin_name} DATA\n\n"
            prompt += f"current_price = {coin_data.get('current_price', 'N/A')}, "
            prompt += f"current_ema20 = {coin_data.get('current_ema20', 'N/A')}, "
            prompt += f"current_macd = {coin_data.get('current_macd', 'N/A')}, "
            prompt += f"current_rsi (7 period) = {coin_data.get('current_rsi7', 'N/A')}\n\n"
            
            # Open Interest 및 Funding Rate
            if coin_data.get('open_interest_latest') is not None:
                prompt += f"In addition, here is the latest {coin_name} open interest and funding rate for perps (the instrument you are trading):\n\n"
                prompt += f"Open Interest: Latest: {coin_data.get('open_interest_latest', 'N/A')}  "
                prompt += f"Average: {coin_data.get('open_interest_avg', 'N/A')}\n\n"
                prompt += f"Funding Rate: {coin_data.get('funding_rate', 'N/A')}\n\n"
            
            # Intraday series
            intraday = coin_data.get('intraday_series', {})
            prompt += "**Intraday series (by 3-minute, oldest → latest):**\n\n"
            prompt += f"Mid prices: {intraday.get('mid_prices', [])}\n\n"
            prompt += f"EMA indicators (20‑period): {intraday.get('ema_indicators', [])}\n\n"
            prompt += f"MACD indicators: {intraday.get('macd_indicators', [])}\n\n"
            prompt += f"RSI indicators (7‑Period): {intraday.get('rsi_indicators_7', [])}\n\n"
            prompt += f"RSI indicators (14‑Period): {intraday.get('rsi_indicators_14', [])}\n\n"
            
            # Longer-term context
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
        
        # Account information
        prompt += "### HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE\n\n"
        prompt += f"Current Total Return (percent): {account_data.get('current_total_return_percent', 0)}%\n\n"
        prompt += f"Available Cash: {account_data.get('available_cash', 0)}\n\n"
        prompt += f"**Current Account Value:** {account_data.get('current_account_value', 0)}\n\n"
        prompt += "Current live positions & performance:\n\n"
        prompt += f"{account_data.get('positions', [])}\n\n"
        prompt += f"Sharpe Ratio: {account_data.get('sharpe_ratio', 0)}\n"
        
        return prompt
    
    def generate_and_save(self) -> Optional[LLMPromptData]:
        """
        DB에서 데이터를 조회하여 llm_prompt_data 테이블에 저장
        모든 주요 마켓의 시장 데이터와 계정 데이터를 조회하여 프롬프트 텍스트를 생성하고 저장합니다.
        
        Returns:
            Optional[LLMPromptData]: 저장된 LLMPromptData 객체 또는 None (실패 시)
        
        Process:
            1. 모든 주요 마켓(KRW-BTC, KRW-ETH 등)의 시장 데이터 조회
            2. 계정 정보 및 성과 데이터 조회
            3. 지표 설정 정보 수집
            4. 거래 시작 후 경과 시간 계산
            5. 프롬프트 텍스트 생성
            6. 데이터베이스에 저장 (프롬프트 텍스트 포함)
        """
        try:
            # 시장 데이터 수집 (DB에서 조회)
            market_data = {}
            for market in UpbitAPIConfig.MAIN_MARKETS:
                coin_data = self.get_coin_data(market)
                market_data[market] = coin_data
            
            # 계정 데이터 수집 (DB에서 조회)
            account_data = self.get_account_data()
            
            # 지표 설정 정보
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
            
            # 거래 경과 시간 계산
            trading_minutes = self.calculate_trading_minutes()
            
            # 프롬프트 텍스트 생성
            prompt_text = self.generate_prompt_text_from_data(
                market_data=market_data,
                account_data=account_data,
                trading_minutes=trading_minutes
            )
            
            # 데이터베이스에 저장 (프롬프트 텍스트 포함)
            prompt_data = LLMPromptData(
                generated_at=datetime.now(timezone.utc),
                trading_minutes=trading_minutes,
                prompt_text=prompt_text,
                market_data_json=market_data,
                account_data_json=account_data,
                indicator_config_json=indicator_config
            )
            
            self.db.add(prompt_data)
            self.db.commit()
            
            logger.info(f"✅ LLM 프롬프트 데이터 저장 완료 (거래 시작 후 {trading_minutes}분, 프롬프트 텍스트 포함)")
            
            return prompt_data
        
        except Exception as e:
            logger.error(f"❌ LLM 프롬프트 데이터 저장 오류: {e}")
            self.db.rollback()
            return None


async def generate_prompt_data_periodically():
    """
    LLM 프롬프트 데이터 주기적 생성 (정3분 기준)
    정3분마다 모든 마켓의 데이터를 조회하여 llm_prompt_data 테이블에 저장합니다.
    서버 시작 시 즉시 실행하지 않고 다음 정3분까지 대기합니다.
    """
    while True:
        try:
            # 다음 정3분까지 대기
            wait_seconds = calculate_wait_seconds_until_next_scheduled_time('minute', 3)
            if wait_seconds > 0:
                logger.debug(f"⏰ 다음 정3분까지 {wait_seconds:.1f}초 대기...")
                await asyncio.sleep(wait_seconds)
            
            db = SessionLocal()
            try:
                generator = LLMPromptGenerator(db)
                prompt_data = generator.generate_and_save()
                
                if prompt_data:
                    logger.info(f"✅ LLM 프롬프트 데이터 주기적 저장 완료 (ID: {prompt_data.id}, 거래 경과: {prompt_data.trading_minutes}분, 정3분 기준)")
                else:
                    logger.warning("⚠️ LLM 프롬프트 데이터 저장 실패")
            finally:
                db.close()
        
        except asyncio.CancelledError:
            logger.info("🛑 LLM 프롬프트 데이터 생성 중지")
            break
        except Exception as e:
            logger.error(f"❌ LLM 프롬프트 데이터 주기적 생성 오류: {e}")
            await asyncio.sleep(60)  # 오류 발생 시 1분 대기 후 재시도
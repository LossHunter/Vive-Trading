"""
Upbit 데이터 저장 모듈
수집된 Upbit API 데이터를 PostgreSQL 데이터베이스에 저장합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from app.db.database import (
    UpbitMarkets, UpbitTicker, UpbitCandlesMinute3, 
    UpbitDayCandles, UpbitTrades, UpbitOrderbook, UpbitAccounts
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UpbitDataStorage:
    """
    Upbit 데이터 저장 클래스
    수집된 데이터를 적절한 테이블에 저장하는 메서드들을 제공합니다.
    """
    
    def __init__(self, db: Session):
        """
        초기화
        
        Args:
            db: SQLAlchemy 데이터베이스 세션
        """
        self.db = db
    
    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """
        ISO 8601 형식의 문자열을 datetime 객체로 변환
        
        Args:
            dt_str: ISO 8601 형식의 날짜/시간 문자열
        
        Returns:
            datetime 객체 또는 None
        """
        if not dt_str:
            return None
        
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))

            # 핵심: -9시간 적용 (KST → UTC 변환)
            dt = dt - timedelta(hours=9)
            return dt
            
        except Exception as e:
            logger.warning(f"⚠️ 날짜 파싱 실패: {dt_str} - {e}")
            return None
    
    def _parse_numeric(self, value: Optional[any]) -> Optional[Decimal]:
        """
        숫자 값을 Decimal로 변환
        정확한 금액 계산을 위해 모든 숫자 값을 Decimal 타입으로 변환합니다.
        
        Args:
            value: 변환할 값 (int, float, str, Decimal 등)
        
        Returns:
            Decimal 객체 또는 None (변환 실패 시)
        
        Note:
            - None 값은 그대로 None을 반환합니다.
            - 변환 실패 시 경고 로그를 출력하고 None을 반환합니다.
        """
        if value is None:
            return None
        
        try:
            return Decimal(str(value))
        except Exception as e:
            logger.warning(f"⚠️ 숫자 변환 실패: {value} - {e}")
            return None
    
    def save_markets(self, markets_data: List[Dict]) -> int:
        """
        마켓 정보 저장
        거래 가능한 마켓 목록을 데이터베이스에 저장합니다.
        중복된 마켓은 무시됩니다 (ON CONFLICT 처리).
        
        Args:
            markets_data: 마켓 정보 딕셔너리 리스트
        
        Returns:
            int: 저장된 레코드 수
        """
        saved_count = 0
        
        for market_data in markets_data:
            try:
                # 마켓 코드가 KRW로 시작하는 것만 저장 (원화 거래만)
                market = market_data.get("market", "")
                if not market.startswith("KRW-"):
                    continue
                
                market_obj = UpbitMarkets(
                    market=market,
                    korean_name=market_data.get("korean_name"),
                    english_name=market_data.get("english_name")
                )
                
                # 중복 체크 후 저장
                existing = self.db.query(UpbitMarkets).filter(
                    UpbitMarkets.market == market
                ).first()
                
                if not existing:
                    self.db.add(market_obj)
                    saved_count += 1
            except Exception as e:
                logger.error(f"❌ 마켓 저장 실패: {market_data} - {e}")
                continue
        
        try:
            self.db.commit()
            logger.info(f"✅ {saved_count}개 마켓 정보 저장 완료")
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ 마켓 저장 커밋 실패: {e}")
        
        return saved_count
    
    def save_ticker(self, ticker_data: List[Dict]) -> int:
        """
        티커(현재가) 데이터 저장
        실시간 현재가 정보를 데이터베이스에 저장합니다.
        
        Args:
            ticker_data: 티커 정보 딕셔너리 리스트
        
        Returns:
            int: 저장된 레코드 수
        """
        saved_count = 0
        
        for ticker in ticker_data:
            try:
                ticker_obj = UpbitTicker(
                    market=ticker.get("market"),
                    trade_price=self._parse_numeric(ticker.get("trade_price")),
                    opening_price=self._parse_numeric(ticker.get("opening_price")),
                    high_price=self._parse_numeric(ticker.get("high_price")),
                    low_price=self._parse_numeric(ticker.get("low_price")),
                    prev_closing_price=self._parse_numeric(ticker.get("prev_closing_price")),
                    change=ticker.get("change"),
                    signed_change_rate=self._parse_numeric(ticker.get("signed_change_rate")),
                    acc_trade_price_24h=self._parse_numeric(ticker.get("acc_trade_price_24h")),
                    acc_trade_volume_24h=self._parse_numeric(ticker.get("acc_trade_volume_24h")),
                    timestamp=ticker.get("timestamp")
                )
                
                self.db.add(ticker_obj)
                saved_count += 1
            except Exception as e:
                logger.error(f"❌ 티커 저장 실패: {ticker} - {e}")
                continue
        
        try:
            self.db.commit()
            # 정상적인 저장은 debug 레벨로 (로그가 너무 많아서)
            logger.debug(f"✅ {saved_count}개 티커 데이터 저장 완료")
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ 티커 저장 커밋 실패: {e}")
        
        return saved_count
    
    def save_candles_minute3(self, candles_data: List[Dict], market: str) -> int:
        """
        3분봉 캔들 데이터 저장
        3분 단위 캔들 데이터를 데이터베이스에 저장합니다.
        중복된 캔들은 무시됩니다 (UNIQUE 제약조건).
        
        prev_closing_price는 직전 분봉(3분 전)의 trade_price로 설정됩니다.
        change_price와 change_rate는 항상 재계산됩니다.
        
        Args:
            candles_data: 캔들 데이터 딕셔너리 리스트
            market: 마켓 코드
        
        Returns:
            int: 저장된 레코드 수
        """
        if not candles_data:
            logger.debug(f"🔍 [저장] {market} 3분봉: 입력 데이터 없음")
            return 0
        
        saved_count = 0
        skipped_count = 0
        error_count = 0
        
        logger.info(f"🔍 [저장] {market} 3분봉: {len(candles_data)}개 데이터 저장 시작")
        
        # 입력 데이터를 시간순으로 정렬 (오래된 것부터)
        # candle_date_time_utc를 기준으로 정렬
        sorted_candles = sorted(
            candles_data,
            key=lambda x: self._parse_datetime(x.get("candle_date_time_utc")) or datetime.min
        )
        
        for idx, candle in enumerate(sorted_candles, 1):
            try:
                candle_time_str = candle.get("candle_date_time_utc")
                logger.info(f"🔍 [저장] {market} 3분봉 #{idx}/{len(sorted_candles)}: 시간={candle_time_str}")
                
                # 가격 데이터 파싱
                trade_price = self._parse_numeric(candle.get("trade_price"))
                
                # prev_closing_price 설정: 직전 분봉(3분 전)의 trade_price
                # 입력 데이터 내에서 이전 인덱스의 trade_price를 사용
                prev_closing_price = None
                if idx > 1:
                    # 이전 캔들의 trade_price를 prev_closing_price로 사용
                    prev_candle = sorted_candles[idx - 2]  # idx는 1부터 시작하므로 -2
                    prev_closing_price = self._parse_numeric(prev_candle.get("trade_price"))
                else:
                    # 첫 번째 데이터는 DB에서 3분 전 데이터를 조회
                    candle_time_utc = self._parse_datetime(candle_time_str)
                    if candle_time_utc:
                        prev_time = candle_time_utc - timedelta(minutes=3)
                        prev_candle_db = self.db.query(UpbitCandlesMinute3).filter(
                            UpbitCandlesMinute3.market == market,
                            UpbitCandlesMinute3.candle_date_time_utc == prev_time
                        ).first()
                        if prev_candle_db and prev_candle_db.trade_price:
                            prev_closing_price = prev_candle_db.trade_price
                
                # change_price 재계산: trade_price - prev_closing_price
                change_price = None
                if trade_price is not None and prev_closing_price is not None:
                    change_price = trade_price - prev_closing_price
                
                # change_rate 재계산: (trade_price - prev_closing_price) / prev_closing_price
                change_rate = None
                if trade_price is not None and prev_closing_price is not None and prev_closing_price != Decimal("0"):
                    change_rate = (trade_price - prev_closing_price) / prev_closing_price
                
                candle_obj = UpbitCandlesMinute3(
                    market=market,
                    candle_date_time_utc=self._parse_datetime(candle.get("candle_date_time_utc")),
                    candle_date_time_kst=self._parse_datetime(candle.get("candle_date_time_kst")),
                    opening_price=self._parse_numeric(candle.get("opening_price")),
                    high_price=self._parse_numeric(candle.get("high_price")),
                    low_price=self._parse_numeric(candle.get("low_price")),
                    trade_price=trade_price,
                    prev_closing_price=prev_closing_price,  # 직전 분봉 종가
                    change_price=change_price,  # 재계산된 값
                    change_rate=change_rate,  # 재계산된 값
                    candle_acc_trade_price=self._parse_numeric(candle.get("candle_acc_trade_price")),
                    candle_acc_trade_volume=self._parse_numeric(candle.get("candle_acc_trade_volume")),
                    unit=3,
                    timestamp=candle.get("timestamp")
                )
                
                # 중복 체크 (market + candle_date_time_utc)
                existing = self.db.query(UpbitCandlesMinute3).filter(
                    UpbitCandlesMinute3.market == market,
                    UpbitCandlesMinute3.candle_date_time_utc == candle_obj.candle_date_time_utc
                ).first()
                
                if not existing:
                    self.db.add(candle_obj)
                    saved_count += 1
                    logger.info(f"✅ [저장] {market} 3분봉 #{idx}: 저장됨 (시간: {candle_obj.candle_date_time_utc}, prev_closing_price: {prev_closing_price})")
                else:
                    skipped_count += 1
                    logger.info(f"⏭️ [저장] {market} 3분봉 #{idx}: 중복 건너뜀 (시간: {candle_obj.candle_date_time_utc})")
            except Exception as e:
                error_count += 1
                logger.error(f"❌ [저장] {market} 3분봉 #{idx} 저장 실패: {candle.get('candle_date_time_utc', 'N/A')} - {e}")
                continue
        
        try:
            self.db.commit()
            logger.debug(f"🔍 [저장] {market} 3분봉: 저장={saved_count}개, 중복={skipped_count}개, 오류={error_count}개 (총 {len(sorted_candles)}개)")
            if saved_count > 0:
                logger.info(f"✅ [저장] {market} 3분봉: {saved_count}개 저장 완료 (중복 {skipped_count}개 제외)")
            elif skipped_count > 0:
                logger.info(f"⏭️ [저장] {market} 3분봉: 모든 데이터 중복 (저장 0개, 중복 {skipped_count}개)")
            elif error_count > 0:
                logger.warning(f"⚠️ [저장] {market} 3분봉: 저장 실패 (저장 0개, 오류 {error_count}개)")
            else:
                logger.warning(f"⚠️ [저장] {market} 3분봉: 저장 결과 없음 (저장 0개, 중복 0개, 오류 0개)")
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ [저장] {market} 3분봉 커밋 실패: {e}")
        
        return saved_count
    
    def save_candles_day(self, candles_data: List[Dict], market: str) -> int:
        """
        일봉 캔들 데이터 저장
        일 단위 캔들 데이터를 데이터베이스에 저장합니다.
        중복된 캔들은 무시됩니다 (UNIQUE 제약조건: market + candle_date_time_utc).
        
        Args:
            candles_data: 캔들 데이터 딕셔너리 리스트
                - 각 딕셔너리는 Upbit API 응답 형식의 캔들 데이터
            market: 마켓 코드 (예: "KRW-BTC")
        
        Returns:
            int: 저장된 레코드 수 (중복 제외)
        
        Note:
            - 원본 JSON 데이터는 raw_json 컬럼에 전체 저장됩니다.
            - 저장 실패한 레코드는 로그에 기록되지만 전체 프로세스는 계속 진행됩니다.
        """
        if not candles_data:
            logger.debug(f"🔍 [저장] {market} 일봉: 입력 데이터 없음")
            return 0
        
        saved_count = 0
        skipped_count = 0
        error_count = 0
        
        logger.debug(f"🔍 [저장] {market} 일봉: {len(candles_data)}개 데이터 저장 시작")
        
        for candle in candles_data:
            try:
                candle_obj = UpbitDayCandles(
                    market=market,
                    candle_date_time_utc=self._parse_datetime(candle.get("candle_date_time_utc")),
                    candle_date_time_kst=self._parse_datetime(candle.get("candle_date_time_kst")),
                    opening_price=self._parse_numeric(candle.get("opening_price")),
                    high_price=self._parse_numeric(candle.get("high_price")),
                    low_price=self._parse_numeric(candle.get("low_price")),
                    trade_price=self._parse_numeric(candle.get("trade_price")),
                    prev_closing_price=self._parse_numeric(candle.get("prev_closing_price")),
                    change_price=self._parse_numeric(candle.get("change_price")),
                    change_rate=self._parse_numeric(candle.get("change_rate")),
                    candle_acc_trade_price=self._parse_numeric(candle.get("candle_acc_trade_price")),
                    candle_acc_trade_volume=self._parse_numeric(candle.get("candle_acc_trade_volume")),
                    timestamp=candle.get("timestamp"),
                    raw_json=candle  # 원본 JSON 전체 저장
                )
                
                # 중복 체크 (market + candle_date_time_utc)
                existing = self.db.query(UpbitDayCandles).filter(
                    UpbitDayCandles.market == market,
                    UpbitDayCandles.candle_date_time_utc == candle_obj.candle_date_time_utc
                ).first()
                
                if not existing:
                    self.db.add(candle_obj)
                    saved_count += 1
                    logger.debug(f"✅ [저장] {market} 일봉: 저장됨 (시간: {candle_obj.candle_date_time_utc})")
                else:
                    skipped_count += 1
                    logger.debug(f"⏭️ [저장] {market} 일봉: 중복 건너뜀 (시간: {candle_obj.candle_date_time_utc})")
            except Exception as e:
                error_count += 1
                logger.error(f"❌ [저장] {market} 일봉 저장 실패: {candle.get('candle_date_time_utc', 'N/A')} - {e}")
                continue
        
        try:
            self.db.commit()
            logger.debug(f"🔍 [저장] {market} 일봉: 저장={saved_count}개, 중복={skipped_count}개, 오류={error_count}개 (총 {len(candles_data)}개)")
            if saved_count > 0:
                logger.info(f"✅ [저장] {market} 일봉: {saved_count}개 저장 완료 (중복 {skipped_count}개 제외)")
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ [저장] {market} 일봉 커밋 실패: {e}")
        
        return saved_count
    
    def save_trades(self, trades_data: List[Dict], market: str) -> int:
        """
        체결 내역 저장
        최근 체결 거래 내역을 데이터베이스에 저장합니다.
        중복된 체결은 무시됩니다 (sequential_id UNIQUE 제약조건).
        
        Args:
            trades_data: 체결 내역 딕셔너리 리스트
                - 각 딕셔너리는 Upbit API 응답 형식의 체결 데이터
                - sequential_id: 체결 고유 식별자 (중복 체크용)
            market: 마켓 코드 (예: "KRW-BTC")
        
        Returns:
            int: 저장된 레코드 수 (중복 제외)
        
        Note:
            - sequential_id가 없는 체결은 중복 체크 없이 저장됩니다.
            - 저장 실패한 레코드는 로그에 기록되지만 전체 프로세스는 계속 진행됩니다.
        """
        saved_count = 0
        
        for trade in trades_data:
            try:
                trade_obj = UpbitTrades(
                    market=market,
                    trade_timestamp=trade.get("timestamp"),
                    trade_date_time_utc=self._parse_datetime(trade.get("trade_date_time_utc")),
                    trade_price=self._parse_numeric(trade.get("trade_price")),
                    trade_volume=self._parse_numeric(trade.get("trade_volume")),
                    ask_bid=trade.get("ask_bid"),
                    prev_closing_price=self._parse_numeric(trade.get("prev_closing_price")),
                    change=trade.get("change"),
                    sequential_id=trade.get("sequential_id")
                )
                
                # 중복 체크 (sequential_id)
                if trade_obj.sequential_id:
                    existing = self.db.query(UpbitTrades).filter(
                        UpbitTrades.sequential_id == trade_obj.sequential_id
                    ).first()
                    
                    if existing:
                        continue
                
                self.db.add(trade_obj)
                saved_count += 1
            except Exception as e:
                logger.error(f"❌ 체결 내역 저장 실패: {trade} - {e}")
                continue
        
        try:
            self.db.commit()
            # 정상적인 저장은 debug 레벨로 (로그가 너무 많아서)
            logger.debug(f"✅ {saved_count}개 체결 내역 저장 완료")
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ 체결 내역 저장 커밋 실패: {e}")
        
        return saved_count
    
    def save_orderbook(self, orderbook_data: List[Dict]) -> int:
        """
        호가창 데이터 저장
        현재 호가창 정보를 데이터베이스에 저장합니다.
        매도/매수 호가의 총 수량을 계산하여 저장합니다.
        
        Args:
            orderbook_data: 호가창 정보 딕셔너리 리스트
                - 각 딕셔너리는 Upbit API 응답 형식의 호가창 데이터
                - orderbook_units: 호가 단위 리스트 (매도/매수 호가 정보 포함)
        
        Returns:
            int: 저장된 레코드 수
        
        Note:
            - total_ask_size: 모든 매도 호가의 총 수량
            - total_bid_size: 모든 매수 호가의 총 수량
            - 저장 실패한 레코드는 로그에 기록되지만 전체 프로세스는 계속 진행됩니다.
        """
        saved_count = 0
        
        for orderbook in orderbook_data:
            try:
                # 매도/매수 호가 합계 계산
                total_ask_size = Decimal(0)
                total_bid_size = Decimal(0)
                
                orderbook_units = orderbook.get("orderbook_units", [])
                for unit in orderbook_units:
                    ask_size = self._parse_numeric(unit.get("ask_size"))
                    bid_size = self._parse_numeric(unit.get("bid_size"))
                    if ask_size:
                        total_ask_size += ask_size
                    if bid_size:
                        total_bid_size += bid_size
                
                orderbook_obj = UpbitOrderbook(
                    market=orderbook.get("market"),
                    timestamp=orderbook.get("timestamp"),
                    total_ask_size=total_ask_size,
                    total_bid_size=total_bid_size
                )
                
                self.db.add(orderbook_obj)
                saved_count += 1
            except Exception as e:
                logger.error(f"❌ 호가창 저장 실패: {orderbook} - {e}")
                continue
        
        try:
            self.db.commit()
            # 정상적인 저장은 debug 레벨로 (로그가 너무 많아서)
            logger.debug(f"✅ {saved_count}개 호가창 데이터 저장 완료")
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ 호가창 저장 커밋 실패: {e}")
        
        return saved_count
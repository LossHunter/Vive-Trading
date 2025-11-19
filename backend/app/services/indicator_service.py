"""
지표 계산 서비스 모듈
기술 지표 계산 및 데이터베이스 저장을 담당합니다.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy.orm import Session
from decimal import Decimal

from app.core.config import IndicatorsConfig
from app.db.database import SessionLocal, UpbitDayCandles, UpbitCandlesMinute3, UpbitRSI, UpbitIndicators
from app.services.indicators_calculator import (
    IndicatorsCalculator, EMACalculator, MACDCalculator,
    RSICalculator, ATRCalculator, BollingerBandsCalculator
)

logger = logging.getLogger(__name__)


async def calculate_indicators_for_date_range(db: Session, market: str, start_date: datetime, end_date: datetime):
    """
    특정 날짜 범위에 대한 RSI와 indicators 계산 (일봉과 3분봉 모두 처리)
    
    Args:
        db: 데이터베이스 세션
        market: 마켓 코드
        start_date: 시작 날짜 (UTC)
        end_date: 종료 날짜 (UTC)
    
    Note:
        EMA(50) 계산을 위해 최소 50개 데이터가 필요합니다.
    """
    try:
        # 일봉 지표 계산
        # start_date 조건을 SQL WHERE 절에 추가하여 120일 범위 내 데이터만 조회
        candles_day = db.query(UpbitDayCandles).filter(
            UpbitDayCandles.market == market,
            UpbitDayCandles.candle_date_time_utc >= start_date,
            UpbitDayCandles.candle_date_time_utc <= end_date
        ).order_by(UpbitDayCandles.candle_date_time_utc.desc()).limit(2000).all()
        
        # 슬라이딩 윈도우를 위해 start_date 이전 데이터도 일부 필요 (최대 50개)
        # EMA(50) 계산을 위해 과거 데이터 추가 조회
        candles_day_before = db.query(UpbitDayCandles).filter(
            UpbitDayCandles.market == market,
            UpbitDayCandles.candle_date_time_utc < start_date
        ).order_by(UpbitDayCandles.candle_date_time_utc.desc()).limit(50).all()
        candles_day_before = list(reversed(candles_day_before))
        
        # 전체 캔들 리스트 구성 (과거 데이터 + 범위 내 데이터)
        all_candles_day = candles_day_before + candles_day
        
        if len(all_candles_day) >= 50:
            target_candles_day = [c for c in all_candles_day if c.candle_date_time_utc >= start_date and c.candle_date_time_utc <= end_date]
            
            if len(target_candles_day) > 0:
                # 각 날짜별로 지표 계산 (슬라이딩 윈도우 방식)
                for target_candle in target_candles_day:
                    target_date = target_candle.candle_date_time_utc
                    candle_subset = [c for c in all_candles_day if c.candle_date_time_utc <= target_date]
                    
                    if len(candle_subset) >= 50:
                        # RSI(14) 계산 및 저장 (일봉 기준)
                        await _calculate_and_save_rsi(db, market, target_date, candle_subset, period=14, interval='day')
                        
                        # RSI(7) 및 통합 지표 계산 및 저장 (일봉 기준)
                        await _calculate_and_save_indicators(db, market, target_date, candle_subset, interval='day')
        
        # 3분봉 지표 계산
        # start_date 조건을 SQL WHERE 절에 추가하여 120일 범위 내 데이터만 조회
        candles_minute3 = db.query(UpbitCandlesMinute3).filter(
            UpbitCandlesMinute3.market == market,
            UpbitCandlesMinute3.candle_date_time_utc >= start_date,
            UpbitCandlesMinute3.candle_date_time_utc <= end_date
        ).order_by(UpbitCandlesMinute3.candle_date_time_utc.asc()).limit(2000).all()
        
        # 슬라이딩 윈도우를 위해 start_date 이전 데이터도 일부 필요 (최대 50개)
        candles_minute3_before = db.query(UpbitCandlesMinute3).filter(
            UpbitCandlesMinute3.market == market,
            UpbitCandlesMinute3.candle_date_time_utc < start_date
        ).order_by(UpbitCandlesMinute3.candle_date_time_utc.desc()).limit(2000).all()
        candles_minute3_before = list(reversed(candles_minute3_before))
        
        # 전체 캔들 리스트 구성 (과거 데이터 + 범위 내 데이터)
        all_candles_minute3 = candles_minute3_before + candles_minute3
        
        if len(all_candles_minute3) >= 50:
            target_candles_minute3 = [c for c in all_candles_minute3 if c.candle_date_time_utc >= start_date and c.candle_date_time_utc <= end_date]
            
            if len(target_candles_minute3) > 0:
                # 각 시각별로 지표 계산 (슬라이딩 윈도우 방식)
                for target_candle in target_candles_minute3:
                    target_date = target_candle.candle_date_time_utc
                    candle_subset = [c for c in all_candles_minute3 if c.candle_date_time_utc <= target_date]
                    
                    if len(candle_subset) >= 50:
                        # RSI(14) 계산 및 저장 (3분봉 기준)
                        await _calculate_and_save_rsi(db, market, target_date, candle_subset, period=14, interval='minute3')
                        
                        # RSI(7) 및 통합 지표 계산 및 저장 (3분봉 기준)
                        await _calculate_and_save_indicators(db, market, target_date, candle_subset, interval='minute3')
        
        logger.debug(f"✅ {market} 날짜 범위 지표 계산 완료 ({start_date.date()} ~ {end_date.date()})")
    except Exception as e:
        logger.error(f"❌ {market} 날짜 범위 지표 계산 오류: {e}")


async def _calculate_and_save_rsi(db: Session, market: str, target_date: datetime, candle_subset: List, period: int, interval: str = 'day'):
    """RSI 계산 및 저장 (내부 함수)
    
    Args:
        db: 데이터베이스 세션
        market: 마켓 코드
        target_date: 대상 날짜/시각
        candle_subset: 캔들 데이터 리스트
        period: RSI 기간
        interval: 캔들 간격 ('day' 또는 'minute3')
    
    Note:
        indicators_calculator.py의 calculate_rsi_from_candles()를 재사용합니다.
    """
    try:
        existing_rsi = db.query(UpbitRSI).filter(
            UpbitRSI.market == market,
            UpbitRSI.candle_date_time_utc == target_date,
            UpbitRSI.period == period,
            UpbitRSI.interval == interval
        ).first()
        
        if existing_rsi:
            return
        
        # indicators_calculator.py의 함수 재사용
        rsi_data = IndicatorsCalculator.calculate_rsi_from_candles(
            candles=candle_subset,
            period=period,
            target_date=target_date
        )
        
        if not rsi_data:
            logger.warning(f"⚠️ {market} {target_date} RSI({period}, interval={interval}) 계산 결과 없음 (데이터 부족 또는 계산 실패)")
            return
        
        null_fields = []
        for key in ["AU", "AD", "RS", "RSI"]:
            if rsi_data.get(key) is None:
                null_fields.append(key)
        
        if null_fields:
            logger.debug(f"⚠️ {market} RSI({period}, interval={interval}) Null 값 발견: {', '.join(null_fields)}")
        
        # RSI 값이 없으면 저장하지 않음 (최소한 RSI 값은 있어야 의미가 있음)
        if rsi_data.get("RSI") is None:
            logger.warning(f"⚠️ {market} {target_date} RSI({period}, interval={interval}) RSI 값이 null입니다. 저장하지 않습니다.")
            return
        
        rsi_obj = UpbitRSI(
            market=market,
            candle_date_time_utc=target_date,
            interval=interval,
            period=period,
            au=Decimal(rsi_data["AU"]) if rsi_data.get("AU") is not None else None,
            ad=Decimal(rsi_data["AD"]) if rsi_data.get("AD") is not None else None,
            rs=Decimal(rsi_data["RS"]) if rsi_data.get("RS") is not None else None,
            rsi=Decimal(rsi_data["RSI"]) if rsi_data.get("RSI") is not None else None
        )
        db.add(rsi_obj)
        db.commit()
        logger.debug(f"✅ {market} {target_date} RSI({period}, interval={interval}) 계산 완료 (RSI={rsi_data.get('RSI')})")
    except Exception as e:
        logger.warning(f"⚠️ {market} {target_date} RSI({period}, interval={interval}) 계산 실패: {e}", exc_info=True)
        db.rollback()


async def _calculate_and_save_indicators(db: Session, market: str, target_date: datetime, candle_subset: List, interval: str = 'day'):
    """
    통합 지표 계산 및 저장 (내부 함수)
    
    Args:
        db: 데이터베이스 세션
        market: 마켓 코드
        target_date: 대상 날짜/시각
        candle_subset: 캔들 데이터 리스트
        interval: 지표 계산 주기 ('day' 또는 'minute3')
    
    Note:
        indicators_calculator.py의 calculate_all_indicators_from_candles()를 재사용합니다.
    """
    try:
        existing_indicator = db.query(UpbitIndicators).filter(
            UpbitIndicators.market == market,
            UpbitIndicators.candle_date_time_utc == target_date,
            UpbitIndicators.interval == interval
        ).first()
        
        if existing_indicator:
            return
        
        # indicators_calculator.py의 함수 재사용
        indicators = IndicatorsCalculator.calculate_all_indicators_from_candles(
            candles=candle_subset,
            target_date=target_date
        )
        
        if not indicators:
            logger.warning(f"⚠️ {market} {target_date} 통합 지표 계산 결과 없음 (데이터 부족 또는 계산 실패)")
            return
        
        # RSI(7) 데이터 추출 및 저장
        rsi7_data = indicators.pop('_rsi7_data', None)
        if rsi7_data is not None:
            await _calculate_and_save_rsi(db, market, target_date, candle_subset, period=7, interval=interval)
        
        # Indicators 저장
        null_fields = []
        indicator_values = {}
        
        for key in ['ema12', 'ema20', 'ema26', 'ema50', 'macd', 'macd_signal', 'macd_hist', 
                    'rsi14', 'atr3', 'atr14', 'bb_upper', 'bb_middle', 'bb_lower']:
            value = indicators.get(key)
            if value is not None:
                indicator_values[key] = Decimal(str(value))
            else:
                null_fields.append(key)
                indicator_values[key] = None
        
        if null_fields:
            logger.debug(f"⚠️ {market} {target_date} 통합 지표 Null 값 발견: {', '.join(null_fields)}")
        
        # 모든 값이 null인 경우 저장하지 않음
        has_any_value = any(v is not None for v in indicator_values.values())
        if not has_any_value:
            logger.warning(f"⚠️ {market} {target_date} 모든 지표 값이 null입니다. 저장하지 않습니다.")
            return
        
        indicator_obj = UpbitIndicators(
            market=market,
            candle_date_time_utc=target_date,
            interval=interval,  # 'day' 또는 'minute3'
            ema12=indicator_values['ema12'],
            ema20=indicator_values['ema20'],
            ema26=indicator_values['ema26'],
            ema50=indicator_values['ema50'],
            macd=indicator_values['macd'],
            macd_signal=indicator_values['macd_signal'],
            macd_hist=indicator_values['macd_hist'],
            rsi14=indicator_values['rsi14'],
            atr3=indicator_values['atr3'],
            atr14=indicator_values['atr14'],
            bb_upper=indicator_values['bb_upper'],
            bb_middle=indicator_values['bb_middle'],
            bb_lower=indicator_values['bb_lower']
        )
        db.add(indicator_obj)
        db.commit()
        logger.debug(f"✅ {market} {target_date} 통합 지표 저장 완료")
    except Exception as e:
        logger.warning(f"⚠️ {market} {target_date} 통합 지표 계산 실패: {e}", exc_info=True)
        db.rollback()


async def calculate_indicators_after_candle_collection(markets: List[str]):
    """
    캔들 데이터 수집 후 기술 지표 계산
    캔들 데이터가 성공적으로 수집된 후 RSI 및 모든 기술 지표를 계산합니다.
    일봉과 3분봉 모두 처리합니다.
    """
    try:
        await asyncio.sleep(1)  # 데이터베이스 커밋 완료 대기
        
        db = SessionLocal()
        try:
            # RSI 일괄 계산 (일봉 데이터 사용)
            rsi_results_day = IndicatorsCalculator.calculate_rsi_for_all_markets(
                db=db,
                markets=markets,
                period=IndicatorsConfig.RSI_PERIOD,
                use_day_candles=True
            )
            
            if rsi_results_day:
                logger.debug(f"✅ RSI 계산 완료 (일봉): {len(rsi_results_day)}개 마켓")
            
            # 모든 기술 지표 일괄 계산 (일봉 데이터 사용)
            indicators_results_day = IndicatorsCalculator.calculate_all_indicators_for_markets(
                db=db,
                markets=markets,
                use_day_candles=True
            )
            
            if indicators_results_day:
                logger.debug(f"✅ 통합 지표 계산 완료 (일봉): {len(indicators_results_day)}개 마켓")
            
            # RSI 일괄 계산 (3분봉 데이터 사용)
            rsi_results_minute3 = IndicatorsCalculator.calculate_rsi_for_all_markets(
                db=db,
                markets=markets,
                period=IndicatorsConfig.RSI_PERIOD,
                use_day_candles=False
            )
            
            if rsi_results_minute3:
                logger.debug(f"✅ RSI 계산 완료 (3분봉): {len(rsi_results_minute3)}개 마켓")
            
            # 모든 기술 지표 일괄 계산 (3분봉 데이터 사용)
            indicators_results_minute3 = IndicatorsCalculator.calculate_all_indicators_for_markets(
                db=db,
                markets=markets,
                use_day_candles=False
            )
            
            if indicators_results_minute3:
                logger.debug(f"✅ 통합 지표 계산 완료 (3분봉): {len(indicators_results_minute3)}개 마켓")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ 기술 지표 계산 오류: {e}")


async def calculate_indicators_periodically():
    """
    기술 지표 주기적 계산
    캔들 데이터 수집과 독립적으로 주기적으로 기술 지표를 계산합니다.
    매일 자정(UTC)에 실행되어 과거 120일치 데이터를 재계산합니다.
    """
    while True:
        try:
            # 다음 자정까지 대기
            now_utc = datetime.now(timezone.utc)
            next_midnight = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            wait_seconds = (next_midnight - now_utc).total_seconds()
            
            logger.info(f"⏰ 다음 지표 계산까지 {wait_seconds/3600:.1f}시간 대기...")
            await asyncio.sleep(wait_seconds)
            
            logger.info("📊 주기적 기술 지표 계산 시작...")
            
            db = SessionLocal()
            try:
                today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                one_hundred_twenty_days_ago = today_utc - timedelta(days=120)
                
                from app.core.config import UpbitAPIConfig
                
                for market in UpbitAPIConfig.MAIN_MARKETS:
                    try:
                        await calculate_indicators_for_date_range(db, market, one_hundred_twenty_days_ago, today_utc)
                    except Exception as e:
                        logger.error(f"❌ {market} 주기적 지표 계산 오류: {e}")
                        continue
                
                logger.info("✅ 주기적 기술 지표 계산 완료")
            finally:
                db.close()
        except asyncio.CancelledError:
            logger.info("🛑 주기적 지표 계산 중지")
            break
        except Exception as e:
            logger.error(f"❌ 주기적 지표 계산 오류: {e}")
            await asyncio.sleep(3600)  # 오류 발생 시 1시간 대기 후 재시도
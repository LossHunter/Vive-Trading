"""
데이터 수집 서비스 모듈
Upbit API에서 데이터를 수집하고 데이터베이스에 저장하는 함수들을 관리합니다.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import DataCollectionConfig, UpbitAPIConfig, ScriptConfig
from app.db.database import SessionLocal, UpbitDayCandles, UpbitCandlesMinute3
from app.services.upbit_collector import UpbitAPICollector
from app.services.upbit_storage import UpbitDataStorage
from app.core.schedule_utils import calculate_wait_seconds_until_next_scheduled_time
from app.core.schedule_utils import calculate_wait_seconds_until_candle_completion
from app.services.indicator_service import calculate_indicators_for_date_range

logger = logging.getLogger(__name__)


async def collect_ticker_data_periodically():
    """ 
    티커 데이터 주기적 수집
    설정된 주기마다 티커 데이터를 수집하여 데이터베이스에 저장합니다.
    """
    collection_count = 0
    last_summary_time = datetime.now(timezone.utc)
    
    while True:
        try:
            await asyncio.sleep(DataCollectionConfig.TICKER_COLLECTION_INTERVAL)
            
            async with UpbitAPICollector() as collector:
                ticker_data = await collector.get_ticker()
                
                if ticker_data:
                    db = SessionLocal()
                    try:
                        storage = UpbitDataStorage(db)
                        storage.save_ticker(ticker_data)
                        collection_count += 1
                    finally:
                        db.close()
                    
                    # 1분마다 요약 정보 출력
                    now = datetime.now(timezone.utc)
                    if (now - last_summary_time).total_seconds() >= 60:
                        logger.info(f"📊 티커 데이터 수집 통계: 지난 1분간 {collection_count}회 수집 완료")
                        collection_count = 0
                        last_summary_time = now
        except asyncio.CancelledError:
            logger.info("🛑 티커 데이터 수집 중지")
            break
        except Exception as e:
            logger.error(f"❌ 티커 데이터 수집 오류: {e}")
            await asyncio.sleep(5)


async def collect_candle_data_periodically():
    """
    캔들 데이터 주기적 수집 (정3분 기준)
    3분봉 캔들 데이터를 정3분마다 수집하여 저장합니다.
    캔들 데이터 수집 완료 후 기술 지표 계산을 트리거합니다.
    """
    while True:
        try:
            # 다음 정3분까지 대기
            # wait_seconds = calculate_wait_seconds_until_next_scheduled_time('minute', 3)
            # if wait_seconds > 0:
            #     logger.debug(f"⏰ [3분봉 주기] 다음 정3분까지 {wait_seconds:.1f}초 대기...")
            #     await asyncio.sleep(wait_seconds)
            
            # logger.debug(f"🔍 [3분봉 주기] 정3분 시점 도달, 데이터 수집 시작")
            wait_seconds = calculate_wait_seconds_until_candle_completion(interval_minutes=3, buffer_seconds=5)
            
            if wait_seconds > 0:
                logger.debug(f"⏰ [3분봉 주기] 다음 캔들 완료 후 수집까지 {wait_seconds:.1f}초 대기...")
                await asyncio.sleep(wait_seconds)
            
            logger.debug(f"🔍 [3분봉 주기] 캔들 완료 시점 도달, 데이터 수집 시작")


            async with UpbitAPICollector() as collector:
                db = SessionLocal()
                try:
                    storage = UpbitDataStorage(db)
                    
                    # 각 마켓별로 3분봉 데이터 수집 (최신 1개만)
                    collected_markets = []
                    failed_markets = []
                    
                    for market in UpbitAPIConfig.MAIN_MARKETS:
                        try:
                            logger.debug(f"🔍 [3분봉 주기] {market} 데이터 수집 시작")
                            candles = await collector.get_candles_minute3(market, count=1)
                            
                            if candles:
                                saved_count = storage.save_candles_minute3(candles, market)
                                logger.debug(f"🔍 [3분봉 주기] {market}: {len(candles)}개 수집, {saved_count}개 저장")
                                
                                if saved_count > 0:
                                    collected_markets.append(market)
                                else:
                                    logger.debug(f"⏭️ [3분봉 주기] {market}: 중복 데이터 (이미 존재)")
                            else:
                                logger.warning(f"⚠️ [3분봉 주기] {market}: API 응답 없음")
                                failed_markets.append(market)
                        except Exception as e:
                            logger.error(f"❌ [3분봉 주기] {market} 수집 오류: {e}")
                            failed_markets.append(market)
                            continue
                    
                    # 캔들 데이터가 성공적으로 수집된 경우 기술 지표 계산 트리거
                    if collected_markets:
                        logger.info(f"✅ [3분봉 주기] {len(collected_markets)}개 마켓 수집 완료 (성공: {collected_markets}, 실패: {failed_markets})")
                        from app.services.indicator_service import calculate_indicators_after_candle_collection
                        asyncio.create_task(calculate_indicators_after_candle_collection(collected_markets))
                    else:
                        logger.debug(f"⏭️ [3분봉 주기] 수집된 데이터 없음 (모두 중복 또는 실패)")
                finally:
                    db.close()
        except asyncio.CancelledError:
            logger.info("🛑 [3분봉 주기] 캔들 데이터 수집 중지")
            break
        except Exception as e:
            logger.error(f"❌ [3분봉 주기] 캔들 데이터 수집 오류: {e}", exc_info=True)
            await asyncio.sleep(60)


async def collect_trades_data_periodically():
    """
    체결 데이터 주기적 수집
    최근 체결 내역을 주기적으로 수집하여 저장합니다.
    """
    collection_count = 0
    last_summary_time = datetime.now(timezone.utc)
    
    while True:
        try:
            await asyncio.sleep(DataCollectionConfig.TRADES_COLLECTION_INTERVAL)
            
            async with UpbitAPICollector() as collector:
                db = SessionLocal()
                try:
                    storage = UpbitDataStorage(db)
                    
                    # 각 마켓별로 체결 데이터 수집
                    for market in UpbitAPIConfig.MAIN_MARKETS:
                        trades = await collector.get_trades(market, count=ScriptConfig.DEFAULT_TRADES_COUNT)
                        if trades:
                            storage.save_trades(trades, market)
                            collection_count += 1
                finally:
                    db.close()
                
                # 1분마다 요약 정보 출력
                now = datetime.now(timezone.utc)
                if (now - last_summary_time).total_seconds() >= 60:
                    logger.info(f"💱 체결 데이터 수집 통계: 지난 1분간 {collection_count}회 수집 완료")
                    collection_count = 0
                    last_summary_time = now
        except asyncio.CancelledError:
            logger.info("🛑 체결 데이터 수집 중지")
            break
        except Exception as e:
            logger.error(f"❌ 체결 데이터 수집 오류: {e}")
            await asyncio.sleep(5)


async def collect_orderbook_data_periodically():
    """
    호가창 데이터 주기적 수집
    현재 호가창 정보를 주기적으로 수집하여 저장합니다.
    """
    collection_count = 0
    last_summary_time = datetime.now(timezone.utc)
    
    while True:
        try:
            await asyncio.sleep(DataCollectionConfig.ORDERBOOK_COLLECTION_INTERVAL)
            
            async with UpbitAPICollector() as collector:
                orderbook_data = await collector.get_orderbook()
                
                if orderbook_data:
                    db = SessionLocal()
                    try:
                        storage = UpbitDataStorage(db)
                        storage.save_orderbook(orderbook_data)
                        collection_count += 1
                    finally:
                        db.close()
                
                # 1분마다 요약 정보 출력
                now = datetime.now(timezone.utc)
                if (now - last_summary_time).total_seconds() >= 60:
                    logger.info(f"📖 호가창 데이터 수집 통계: 지난 1분간 {collection_count}회 수집 완료")
                    collection_count = 0
                    last_summary_time = now
        except asyncio.CancelledError:
            logger.info("🛑 호가창 데이터 수집 중지")
            break
        except Exception as e:
            logger.error(f"❌ 호가창 데이터 수집 오류: {e}")
            await asyncio.sleep(5)


def get_latest_candle_time(db: Session, market: str, use_day_candles: bool = True) -> Optional[datetime]:
    """
    DB에서 가장 최신 캔들 데이터의 발생 시간 조회
    데이터 수집 시간(collected_at)이 아닌 데이터 자체 발생 시간(candle_date_time_utc)을 기준으로 합니다.
    
    Args:
        db: 데이터베이스 세션
        market: 마켓 코드
        use_day_candles: True면 일봉, False면 3분봉
    
    Returns:
        datetime: 가장 최신 캔들 발생 시간 (UTC, timezone-aware), 데이터가 없으면 None
    """
    if use_day_candles:
        latest = db.query(UpbitDayCandles.candle_date_time_utc).filter(
            UpbitDayCandles.market == market
        ).order_by(desc(UpbitDayCandles.candle_date_time_utc)).first()
    else:
        latest = db.query(UpbitCandlesMinute3.candle_date_time_utc).filter(
            UpbitCandlesMinute3.market == market
        ).order_by(desc(UpbitCandlesMinute3.candle_date_time_utc)).first()
    
    if latest:
        result = latest[0]
        # timezone-aware로 보장 (timezone-naive인 경우 UTC로 설정)
        if result.tzinfo is None:
            logger.debug(f"🔍 [get_latest_candle_time] {market} timezone-naive 감지, UTC로 변환")
            result = result.replace(tzinfo=timezone.utc)
        else:
            # timezone-aware인 경우 UTC로 변환 (다른 timezone일 수 있음)
            if result.tzinfo != timezone.utc:
                logger.debug(f"🔍 [get_latest_candle_time] {market} timezone 변환: {result.tzinfo} -> UTC")
                result = result.astimezone(timezone.utc)
        logger.debug(f"🔍 [get_latest_candle_time] {market} 반환 시간: {result} (tzinfo: {result.tzinfo})")
        return result
    logger.debug(f"🔍 [get_latest_candle_time] {market} 데이터 없음")
    return None


async def collect_historical_minute3_candles():
    """
    서버 시작 시 과거 3분봉 데이터 수집
    현재 시간 기준으로 최대 120일 이전 데이터까지 최대 2000개를 수집합니다.
    """
    try:
        logger.info("📅 [과거수집-3분봉] 과거 데이터 수집 시작...")
        
        db = SessionLocal()
        try:
            now_utc = datetime.now(timezone.utc)
            # 최대 수집 범위: 현재 시간 기준 120일 이전
            max_collection_start = now_utc - timedelta(days=120)
            logger.info(f"📅 [과거수집-3분봉] 현재 시각 (UTC): {now_utc}")
            logger.info(f"📅 [과거수집-3분봉] 최대 수집 시작 시각 (120일 이전): {max_collection_start}")
            
            async with UpbitAPICollector() as collector:
                storage = UpbitDataStorage(db)
                
                for market in UpbitAPIConfig.MAIN_MARKETS:
                    try:
                        logger.info(f"📅 [과거수집-3분봉] {market} 처리 시작")
                        
                        # 최대 2000개 데이터 수집 (120일 이전까지)
                        count_to_fetch = 2000
                        to_date_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                        
                        logger.info(f"📅 [과거수집-3분봉] {market}: API 요청 (count={count_to_fetch}, to={to_date_str})")
                        
                        candles = await collector.get_candles_minute3(
                            market, 
                            count=count_to_fetch,
                            to=to_date_str
                        )
                        
                        logger.info(f"📅 [과거수집-3분봉] {market}: API 응답 {len(candles) if candles else 0}개")
                        
                        if candles:
                            # 120일 제한 적용: max_collection_start 이후의 데이터만 필터링
                            filtered_candles = []
                            filtered_out_count = 0
                            
                            for candle in candles:
                                candle_time_str = candle.get("candle_date_time_utc")
                                if candle_time_str:
                                    try:
                                        if isinstance(candle_time_str, str):
                                            candle_time_str = candle_time_str.replace('Z', '+00:00')
                                            candle_dt = datetime.fromisoformat(candle_time_str)
                                        elif isinstance(candle_time_str, datetime):
                                            candle_dt = candle_time_str
                                        else:
                                            continue
                                        
                                        # timezone-aware로 보장
                                        if candle_dt.tzinfo is None:
                                            candle_dt = candle_dt.replace(tzinfo=timezone.utc)
                                        
                                        # 120일 제한 적용: max_collection_start 이후의 데이터만 포함
                                        if candle_dt >= max_collection_start and candle_dt < now_utc:
                                            filtered_candles.append(candle)
                                        else:
                                            filtered_out_count += 1
                                    except (ValueError, TypeError) as e:
                                        logger.debug(f"⚠️ [과거수집-3분봉] {market} 캔들 시간 파싱 실패: {candle_time_str} - {e}")
                                        continue
                            
                            logger.info(f"📅 [과거수집-3분봉] {market}: 필터링 결과 - 포함={len(filtered_candles)}개, 제외={filtered_out_count}개")
                            
                            if filtered_candles:
                                saved_count = storage.save_candles_minute3(filtered_candles, market)
                                logger.info(f"✅ [과거수집-3분봉] {market}: {saved_count}개 저장 완료 (필터링된 {len(filtered_candles)}개 중)")
                                
                                # 3분봉 데이터 수집 후 지표 계산 (최근 120일치)
                                if saved_count > 0:
                                    from app.services.indicator_service import calculate_indicators_for_date_range
                                    indicator_start_date = now_utc - timedelta(days=120)
                                    logger.info(f"📅 [과거수집-3분봉] {market}: 지표 계산 시작...")
                                    await calculate_indicators_for_date_range(db, market, indicator_start_date, now_utc)
                                    logger.info(f"📅 [과거수집-3분봉] {market}: 지표 계산 완료")
                            else:
                                logger.info(f"✅ [과거수집-3분봉] {market}: 저장할 데이터 없음 (모두 120일 제한 밖이거나 중복)")
                                # 데이터가 없어도 기존 데이터에 대한 지표 계산은 수행
                                from app.services.indicator_service import calculate_indicators_for_date_range
                                indicator_start_date = now_utc - timedelta(days=120)
                                await calculate_indicators_for_date_range(db, market, indicator_start_date, now_utc)
                        else:
                            logger.warning(f"⚠️ [과거수집-3분봉] {market}: API에서 데이터를 가져올 수 없음")
                            # 데이터가 없어도 기존 데이터에 대한 지표 계산은 수행
                            from app.services.indicator_service import calculate_indicators_for_date_range
                            indicator_start_date = now_utc - timedelta(days=120)
                            await calculate_indicators_for_date_range(db, market, indicator_start_date, now_utc)
                        
                    except Exception as e:
                        logger.error(f"❌ [과거수집-3분봉] {market} 과거 데이터 수집 오류: {e}", exc_info=True)
                        continue
                
                logger.info("✅ [과거수집-3분봉] 과거 데이터 수집 완료")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ [과거수집-3분봉] 과거 데이터 수집 오류: {e}", exc_info=True)


async def collect_historical_day_candles_and_indicators():
    """
    서버 시작 시 과거 일봉 데이터 수집 및 지표 계산
    현재 시간 기준으로 최대 120일 이전 데이터까지 최대 2000개를 수집합니다.
    """
    try:
        logger.info("📅 [과거수집-일봉] 과거 일봉 데이터 수집 및 지표 계산 시작...")
        
        db = SessionLocal()
        try:
            now_utc = datetime.now(timezone.utc)
            today_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            # 120일 이전까지 수집
            one_hundred_twenty_days_ago = today_utc - timedelta(days=120)
            # 지표 계산은 최근 120일치 수행
            indicator_start_date = today_utc - timedelta(days=120)
            
            async with UpbitAPICollector() as collector:
                storage = UpbitDataStorage(db)
                
                for market in UpbitAPIConfig.MAIN_MARKETS:
                    try:
                        logger.info(f"📅 [과거수집-일봉] {market} 처리 시작")
                        
                        # 최대 2000개 데이터 수집 (120일 이전까지)
                        count_to_fetch = 2000
                        to_date_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                        
                        logger.info(f"📅 [과거수집-일봉] {market}: API 요청 (count={count_to_fetch}, to={to_date_str})")
                        
                        candles = await collector.get_candles_day(
                            market, 
                            count=count_to_fetch,
                            to=to_date_str
                        )
                        
                        logger.info(f"📅 [과거수집-일봉] {market}: API 응답 {len(candles) if candles else 0}개")
                        
                        if candles:
                            # 120일 제한 적용: one_hundred_twenty_days_ago 이후의 데이터만 필터링
                            filtered_candles = []
                            filtered_out_count = 0
                            
                            for candle in candles:
                                candle_time_str = candle.get("candle_date_time_utc")
                                if candle_time_str:
                                    try:
                                        if isinstance(candle_time_str, str):
                                            candle_time_str = candle_time_str.replace('Z', '+00:00')
                                            candle_dt = datetime.fromisoformat(candle_time_str)
                                        elif isinstance(candle_time_str, datetime):
                                            candle_dt = candle_time_str
                                        else:
                                            continue
                                        
                                        # timezone-aware로 보장
                                        if candle_dt.tzinfo is None:
                                            candle_dt = candle_dt.replace(tzinfo=timezone.utc)
                                        
                                        # 120일 제한 적용: one_hundred_twenty_days_ago 이후의 데이터만 포함
                                        if candle_dt >= one_hundred_twenty_days_ago and candle_dt < now_utc:
                                            filtered_candles.append(candle)
                                        else:
                                            filtered_out_count += 1
                                    except (ValueError, TypeError) as e:
                                        logger.debug(f"⚠️ [과거수집-일봉] {market} 캔들 시간 파싱 실패: {candle_time_str} - {e}")
                                        continue
                            
                            logger.info(f"📅 [과거수집-일봉] {market}: 필터링 결과 - 포함={len(filtered_candles)}개, 제외={filtered_out_count}개")
                            
                            if filtered_candles:
                                saved_count = storage.save_candles_day(filtered_candles, market)
                                logger.info(f"✅ [과거수집-일봉] {market}: {saved_count}개 저장 완료 (필터링된 {len(filtered_candles)}개 중)")
                            else:
                                logger.info(f"✅ [과거수집-일봉] {market}: 저장할 데이터 없음 (모두 120일 제한 밖이거나 중복)")
                            
                            # RSI와 indicators 계산 (최근 120일치)
                            logger.info(f"📅 [과거수집-일봉] {market}: 지표 계산 시작...")
                            await calculate_indicators_for_date_range(db, market, indicator_start_date, today_utc)
                            logger.info(f"📅 [과거수집-일봉] {market}: 지표 계산 완료")
                        else:
                            logger.warning(f"⚠️ [과거수집-일봉] {market}: API에서 데이터를 가져올 수 없음")
                            # 데이터가 없어도 기존 데이터에 대한 지표 계산은 수행
                            await calculate_indicators_for_date_range(db, market, indicator_start_date, today_utc)
                        
                    except Exception as e:
                        logger.error(f"❌ [과거수집-일봉] {market} 과거 데이터 수집 오류: {e}")
                        continue
                
                logger.info("✅ [과거수집-일봉] 과거 일봉 데이터 수집 및 지표 계산 완료")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ [과거수집-일봉] 과거 데이터 수집 오류: {e}")


async def collect_historical_data_internal(market: str, count: int, interval: str = "minute3"):
    """
    과거 데이터 수집 (내부 함수)
    API 엔드포인트에서 호출하는 내부 함수입니다.
    
    Args:
        market: 마켓 코드
        count: 수집할 데이터 개수
        interval: 캔들 간격 (minute3, day 등)
    
    Returns:
        dict: 수집 결과
    """
    try:
        async with UpbitAPICollector() as collector:
            db = SessionLocal()
            try:
                storage = UpbitDataStorage(db)
                
                if interval == "minute3":
                    candles = await collector.get_candles_minute3(market, count=count)
                    if candles:
                        saved_count = storage.save_candles_minute3(candles, market)
                        return {"success": True, "saved_count": saved_count, "market": market}
                elif interval == "day":
                    candles = await collector.get_candles_day(market, count=count)
                    if candles:
                        saved_count = storage.save_candles_day(candles, market)
                        return {"success": True, "saved_count": saved_count, "market": market}
                else:
                    return {"success": False, "error": f"지원하지 않는 interval: {interval}"}
                
                return {"success": False, "error": "데이터 수집 실패"}
            finally:
                db.close()
    except Exception as e:
        logger.error(f"❌ 과거 데이터 수집 오류: {e}")
        return {"success": False, "error": str(e)}


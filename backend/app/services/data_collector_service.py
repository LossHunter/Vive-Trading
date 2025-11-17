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
from app.services.indicator_service import calculate_indicators_for_date_range

logger = logging.getLogger(__name__)


async def collect_ticker_data_periodically():
    """ 
    티커 데이터 주기적 수집
    설정된 주기마다 티커 데이터를 수집하여 데이터베이스에 저장합니다.
    """
    collection_count = 0
    last_summary_time = datetime.utcnow()
    
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
                    now = datetime.utcnow()
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
            wait_seconds = calculate_wait_seconds_until_next_scheduled_time('minute', 3)
            if wait_seconds > 0:
                logger.debug(f"⏰ [3분봉 주기] 다음 정3분까지 {wait_seconds:.1f}초 대기...")
                await asyncio.sleep(wait_seconds)
            
            logger.debug(f"🔍 [3분봉 주기] 정3분 시점 도달, 데이터 수집 시작")
            
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
                        from services.indicator_service import calculate_indicators_after_candle_collection
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
    last_summary_time = datetime.utcnow()
    
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
                now = datetime.utcnow()
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
    last_summary_time = datetime.utcnow()
    
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
                now = datetime.utcnow()
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
    현재 시간 기준으로 DB의 가장 최신 데이터 발생 시간부터 현재까지의 공백을 모두 채웁니다.
    """
    try:
        logger.info("📅 [3분봉] 과거 데이터 수집 시작...")
        
        db = SessionLocal()
        try:
            now_utc = datetime.now(timezone.utc)
            logger.debug(f"🔍 [3분봉] 현재 시각 (UTC): {now_utc} (tzinfo: {now_utc.tzinfo})")
            
            async with UpbitAPICollector() as collector:
                storage = UpbitDataStorage(db)
                
                for market in UpbitAPIConfig.MAIN_MARKETS:
                    try:
                        logger.debug(f"🔍 [3분봉] {market} 처리 시작")
                        
                        # DB에서 가장 최신 3분봉 데이터의 발생 시간 조회
                        latest_candle_time = get_latest_candle_time(db, market, use_day_candles=False)
                        logger.debug(f"🔍 [3분봉] {market} DB 최신 데이터 시간: {latest_candle_time}")
                        
                        if latest_candle_time is None:
                            # 데이터가 없으면 최근 200개 수집 (약 10시간치)
                            logger.info(f"📊 [3분봉] {market}: DB에 데이터 없음, 최근 200개 수집 시작")
                            candles = await collector.get_candles_minute3(market, count=200)
                            if candles:
                                saved_count = storage.save_candles_minute3(candles, market)
                                logger.info(f"✅ [3분봉] {market}: {len(candles)}개 수집, {saved_count}개 저장 완료")
                            else:
                                logger.warning(f"⚠️ [3분봉] {market}: API에서 데이터를 가져올 수 없음")
                        else:
                            # 최신 데이터 이후부터 현재까지의 공백 계산
                            # 3분봉이므로 최신 데이터 시간 + 3분부터 시작
                            # latest_candle_time은 이미 UTC timezone-aware로 보장됨
                            start_time = latest_candle_time + timedelta(minutes=3)
                            
                            # timezone 일치 확인 (둘 다 UTC여야 함)
                            if start_time.tzinfo != now_utc.tzinfo:
                                logger.warning(f"⚠️ [3분봉] {market}: timezone 불일치! start_time.tzinfo={start_time.tzinfo}, now_utc.tzinfo={now_utc.tzinfo}")
                                if start_time.tzinfo is None:
                                    start_time = start_time.replace(tzinfo=timezone.utc)
                                if now_utc.tzinfo is None:
                                    now_utc = now_utc.replace(tzinfo=timezone.utc)
                            
                            logger.debug(f"🔍 [3분봉] {market} 수집 시작 시각: {start_time} (최신 데이터: {latest_candle_time} + 3분)")
                            logger.debug(f"🔍 [3분봉] {market} 현재 시각: {now_utc}")
                            logger.debug(f"🔍 [3분봉] {market} 시간 비교: start_time >= now_utc? {start_time >= now_utc}")
                            
                            if start_time >= now_utc:
                                logger.debug(f"✅ [3분봉] {market}: 데이터 최신 상태 (start_time={start_time} >= now_utc={now_utc})")
                                continue
                            
                            # 공백 기간 계산 (분 단위)
                            time_diff = now_utc - start_time
                            minutes_diff = int(time_diff.total_seconds() / 60)
                            logger.debug(f"🔍 [3분봉] {market} 공백 기간: {minutes_diff}분 ({start_time} ~ {now_utc})")
                            
                            if minutes_diff > 0:
                                # 필요한 캔들 개수 계산 (3분 간격이므로)
                                needed_count = (minutes_diff // 3) + 1
                                # API 제한을 고려하여 최대 200개씩 나눠서 수집
                                max_count_per_request = 200
                                
                                logger.info(f"📊 [3분봉] {market}: {needed_count}개 데이터 수집 필요 (최신 DB: {latest_candle_time}, 시작: {start_time}, 종료: {now_utc})")
                                
                                collected_total = 0
                                current_time = start_time
                                iteration = 0
                                max_iterations = 1000  # 무한 루프 방지
                                
                                while current_time < now_utc:
                                    iteration += 1
                                    if iteration > max_iterations:
                                        logger.error(f"❌ [3분봉] {market}: 최대 반복 횟수({max_iterations}) 도달, 루프 종료 (current_time={current_time}, now_utc={now_utc})")
                                        break
                                    
                                    logger.debug(f"🔍 [3분봉] {market} 반복 #{iteration}: current_time={current_time}, now_utc={now_utc}")
                                    
                                    # 남은 시간 계산
                                    remaining_minutes = int((now_utc - current_time).total_seconds() / 60)
                                    count_to_fetch = min(max_count_per_request, (remaining_minutes // 3) + 1)
                                    
                                    logger.debug(f"🔍 [3분봉] {market} 반복 #{iteration}: 남은 시간={remaining_minutes}분, 요청 개수={count_to_fetch}")
                                    
                                    if count_to_fetch <= 0:
                                        logger.debug(f"✅ [3분봉] {market} 반복 #{iteration}: count_to_fetch <= 0, 루프 종료")
                                        break
                                    
                                    # Upbit API는 to 파라미터로 "해당 시점 이전"의 데이터를 반환
                                    # current_time 이후의 데이터를 수집하려면 to=current_time+3분으로 설정
                                    # 하지만 더 안전하게 to=now_utc로 설정하여 최신 데이터부터 가져온 후 필터링
                                    to_date_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                                    logger.debug(f"🔍 [3분봉] {market} 반복 #{iteration}: API 요청 (count={count_to_fetch}, to={to_date_str}, current_time={current_time})")
                                    
                                    candles = await collector.get_candles_minute3(
                                        market, 
                                        count=count_to_fetch,
                                        to=to_date_str
                                    )
                                    
                                    logger.debug(f"🔍 [3분봉] {market} 반복 #{iteration}: API 응답 {len(candles) if candles else 0}개")
                                    
                                    if candles:
                                        # current_time 이후의 데이터만 필터링
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
                                                    
                                                    # current_time 이후의 데이터만 포함
                                                    if candle_dt >= current_time and candle_dt < now_utc:
                                                        filtered_candles.append(candle)
                                                    else:
                                                        filtered_out_count += 1
                                                        logger.debug(f"🔍 [3분봉] {market} 필터링 제외: {candle_dt} (조건: {current_time} <= 시간 < {now_utc})")
                                                except (ValueError, TypeError) as e:
                                                    logger.debug(f"⚠️ [3분봉] {market} 캔들 시간 파싱 실패: {candle_time_str} - {e}")
                                                    continue
                                        
                                        logger.debug(f"🔍 [3분봉] {market} 반복 #{iteration}: 필터링 결과 - 포함={len(filtered_candles)}개, 제외={filtered_out_count}개")
                                        
                                        if filtered_candles:
                                            saved_count = storage.save_candles_minute3(filtered_candles, market)
                                            collected_total += saved_count
                                            
                                            logger.debug(f"🔍 [3분봉] {market} 반복 #{iteration}: 저장 결과 - {saved_count}개 저장 (필터링된 {len(filtered_candles)}개 중)")
                                            
                                            # 가장 최신 캔들 시간 찾기 (필터링된 데이터 중)
                                            latest_candle = filtered_candles[-1]
                                            candle_time_str = latest_candle.get("candle_date_time_utc")
                                            
                                            if candle_time_str:
                                                try:
                                                    if isinstance(candle_time_str, str):
                                                        candle_time_str = candle_time_str.replace('Z', '+00:00')
                                                        latest_in_batch = datetime.fromisoformat(candle_time_str)
                                                    elif isinstance(candle_time_str, datetime):
                                                        latest_in_batch = candle_time_str
                                                    else:
                                                        latest_in_batch = None
                                                    
                                                    if latest_in_batch:
                                                        if latest_in_batch.tzinfo is None:
                                                            latest_in_batch = latest_in_batch.replace(tzinfo=timezone.utc)
                                                        
                                                        # 다음 수집 시작 시간 = 가장 최신 캔들 시간 + 3분
                                                        next_time = latest_in_batch + timedelta(minutes=3)
                                                        logger.debug(f"🔍 [3분봉] {market} 반복 #{iteration}: 최신 캔들={latest_in_batch}, 다음 시간={next_time}")
                                                        
                                                        # 시간 전진 확인
                                                        if next_time <= current_time:
                                                            logger.warning(f"⚠️ [3분봉] {market} 반복 #{iteration}: 시간이 전진하지 않음! (current={current_time}, next={next_time}), 강제 전진")
                                                            current_time += timedelta(minutes=3)
                                                        else:
                                                            current_time = next_time
                                                        
                                                        # 저장된 데이터가 없으면 이미 모든 데이터가 있는 것이므로 종료
                                                        if saved_count == 0:
                                                            logger.info(f"✅ [3분봉] {market}: 모든 데이터가 이미 존재합니다 (현재 시점: {current_time}, 최신 캔들: {latest_in_batch})")
                                                            break
                                                    else:
                                                        logger.warning(f"⚠️ [3분봉] {market} 반복 #{iteration}: latest_in_batch 파싱 실패")
                                                        current_time += timedelta(minutes=3)
                                                except (ValueError, TypeError) as e:
                                                    logger.warning(f"⚠️ [3분봉] {market} 반복 #{iteration}: 캔들 시간 파싱 실패: {candle_time_str} - {e}")
                                                    current_time += timedelta(minutes=3)
                                            else:
                                                logger.warning(f"⚠️ [3분봉] {market} 반복 #{iteration}: 캔들 시간이 없음")
                                                current_time += timedelta(minutes=3)
                                        else:
                                            # 필터링된 데이터가 없으면 이미 모든 데이터가 있는 것
                                            logger.info(f"✅ [3분봉] {market}: {current_time} 이후의 데이터가 이미 모두 존재합니다 (API 응답: {len(candles)}개, 필터링 후: 0개)")
                                            break
                                    else:
                                        # 데이터가 없으면 종료
                                        logger.info(f"✅ [3분봉] {market}: 더 이상 수집할 데이터가 없습니다 (API 응답: 0개)")
                                        break
                                    
                                    # API 요청 제한을 고려한 짧은 대기
                                    await asyncio.sleep(0.1)
                                
                                logger.info(f"✅ [3분봉] {market}: 총 {collected_total}개 데이터 수집 완료 (반복 횟수: {iteration})")
                            else:
                                logger.debug(f"✅ [3분봉] {market}: 데이터 최신 상태 (minutes_diff={minutes_diff} <= 0)")
                        
                    except Exception as e:
                        logger.error(f"❌ [3분봉] {market} 과거 데이터 수집 오류: {e}", exc_info=True)
                        continue
                
                logger.info("✅ [3분봉] 과거 데이터 수집 완료")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ [3분봉] 과거 데이터 수집 오류: {e}", exc_info=True)


async def collect_historical_day_candles_and_indicators():
    """
    서버 시작 시 과거 일봉 데이터 수집 및 지표 계산
    현재 시간 기준으로 DB의 가장 최신 데이터 발생 시간부터 현재까지의 공백을 모두 채웁니다.
    """
    try:
        logger.info("📅 과거 일봉 데이터 수집 및 지표 계산 시작...")
        
        db = SessionLocal()
        try:
            now_utc = datetime.now(timezone.utc)
            today_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            one_month_ago = today_utc - timedelta(days=30)
            
            async with UpbitAPICollector() as collector:
                storage = UpbitDataStorage(db)
                
                for market in UpbitAPIConfig.MAIN_MARKETS:
                    try:
                        # DB에서 가장 최신 일봉 데이터의 발생 시간 조회
                        latest_candle_time = get_latest_candle_time(db, market, use_day_candles=True)
                        
                        if latest_candle_time is None:
                            # 데이터가 없으면 한달치 수집
                            logger.info(f"📊 {market}: 일봉 데이터 없음, 한달치 수집")
                            start_date = one_month_ago
                        else:
                            # 최신 데이터 다음 날부터 시작
                            start_date = (latest_candle_time + timedelta(days=1)).replace(
                                hour=0, minute=0, second=0, microsecond=0
                            )
                        
                        # 수집할 날짜 범위 계산
                        end_date = today_utc
                        
                        if start_date > end_date:
                            logger.debug(f"✅ {market}: 일봉 데이터가 최신 상태입니다")
                            # 기존 데이터에 대한 지표 계산은 수행
                            await calculate_indicators_for_date_range(db, market, one_month_ago, today_utc)
                            continue
                        
                        # 누락된 날짜 계산
                        missing_dates = []
                        current_date = start_date
                        while current_date <= end_date:
                            missing_dates.append(current_date)
                            current_date += timedelta(days=1)
                        
                        if missing_dates:
                            logger.info(f"📊 {market}: {len(missing_dates)}개 날짜의 일봉 데이터 수집 필요 (최신: {latest_candle_time})")
                            
                            # 누락된 날짜별로 데이터 수집
                            for target_date in missing_dates:
                                try:
                                    to_date_str = target_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                                    candles = await collector.get_candles_day(market, count=1, to=to_date_str)
                                    
                                    if candles:
                                        storage.save_candles_day(candles, market)
                                    
                                    # API 요청 제한을 고려한 짧은 대기
                                    await asyncio.sleep(0.1)
                                except Exception as e:
                                    logger.warning(f"⚠️ {market} {target_date.date()} 일봉 데이터 수집 실패: {e}")
                                    continue
                            
                            # RSI와 indicators 계산 (과거 한달간)
                            await calculate_indicators_for_date_range(db, market, one_month_ago, today_utc)
                        else:
                            logger.debug(f"✅ {market}: 모든 날짜의 일봉 데이터가 이미 존재합니다")
                            # 기존 데이터에 대한 지표 계산도 수행 (누락된 지표가 있을 수 있음)
                            await calculate_indicators_for_date_range(db, market, one_month_ago, today_utc)
                        
                    except Exception as e:
                        logger.error(f"❌ {market} 과거 데이터 수집 오류: {e}")
                        continue
                
                logger.info("✅ 과거 한달간 일봉 데이터 수집 및 지표 계산 완료")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ 과거 데이터 수집 오류: {e}")


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


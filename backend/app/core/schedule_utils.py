"""
정시/정각/정분 기준 스케줄링 유틸리티 모듈
주기적 작업을 정시, 정각, 정분 기준으로 실행하기 위한 헬퍼 함수들을 제공합니다.
"""

from datetime import datetime, timedelta, timezone


def calculate_next_scheduled_time(
    interval_type: str,  # 'minute', 'hour', 'day'
    interval_value: int = 1  # 간격 값 (예: 3분마다라면 3)
) -> datetime:
    """
    다음 정시/정각/정분까지의 시간 계산
    
    Args:
        interval_type: 'minute', 'hour', 'day'
        interval_value: 간격 값 (예: 3분마다라면 3)
    
    Returns:
        datetime: 다음 실행 시각 (UTC)
    """
    now = datetime.now(timezone.utc)
    
    if interval_type == 'minute':
        # 정N분 기준
        current_minute = now.minute
        remainder = current_minute % interval_value
        
        if remainder == 0 and now.second == 0:
            # 이미 정N분이면 다음 정N분
            next_time = now + timedelta(minutes=interval_value)
        else:
            # 다음 정N분까지
            minutes_to_add = interval_value - remainder
            next_time = now + timedelta(minutes=minutes_to_add)
        
        return next_time.replace(second=0, microsecond=0)
    
    elif interval_type == 'hour':
        # 정시 기준
        next_hour = (now + timedelta(hours=interval_value)).replace(
            minute=0, second=0, microsecond=0
        )
        return next_hour
    
    elif interval_type == 'day':
        # 자정 기준
        next_midnight = (now + timedelta(days=interval_value)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return next_midnight
    
    else:
        raise ValueError(f"지원하지 않는 interval_type: {interval_type}")


def calculate_wait_seconds_until_next_scheduled_time(
    interval_type: str,
    interval_value: int = 1
) -> float:
    """
    다음 정시/정각/정분까지의 대기 시간(초) 계산
    
    Args:
        interval_type: 'minute', 'hour', 'day'
        interval_value: 간격 값
    
    Returns:
        float: 대기 시간(초)
    """
    now = datetime.now(timezone.utc)
    next_time = calculate_next_scheduled_time(interval_type, interval_value)
    wait_seconds = (next_time - now).total_seconds()
    return max(0.0, wait_seconds)  # 음수 방지

def calculate_next_candle_completion_time(interval_minutes: int = 3, buffer_seconds: int = 5) -> datetime:
    """
    다음 캔들 완료 시각 계산 (버퍼 시간 포함)
    
    Args:
        interval_minutes: 캔들 간격 (3분봉이면 3)
        buffer_seconds: 캔들 완료 후 대기 시간 (초) - API가 캔들을 확정하는 시간
    
    Returns:
        datetime: 다음 캔들 완료 후 수집 시각 (UTC)
    
    예시:
        현재: 12:00:30 → 다음 캔들 완료: 12:03:00 → 수집 시각: 12:03:05
        현재: 12:03:00 → 다음 캔들 완료: 12:06:00 → 수집 시각: 12:06:05
    """
    now = datetime.now(timezone.utc)
    current_minute = now.minute
    remainder = current_minute % interval_minutes
    
    if remainder == 0:
        # 이미 정3분이면 다음 정3분
        next_completion = now + timedelta(minutes=interval_minutes)
    else:
        # 다음 정3분까지
        minutes_to_add = interval_minutes - remainder
        next_completion = now + timedelta(minutes=minutes_to_add)
    
    # 정3분 시각으로 정규화
    next_completion = next_completion.replace(second=0, microsecond=0)
    
    # 버퍼 시간 추가 (캔들 완료 후 API가 데이터를 확정하는 시간)
    collection_time = next_completion + timedelta(seconds=buffer_seconds)
    
    return collection_time

def calculate_wait_seconds_until_candle_completion(interval_minutes: int = 3, buffer_seconds: int = 5) -> float:
    """
    다음 캔들 완료 후 수집 시각까지의 대기 시간(초) 계산
    
    Args:
        interval_minutes: 캔들 간격
        buffer_seconds: 캔들 완료 후 대기 시간
    
    Returns:
        float: 대기 시간(초)
    """
    now = datetime.now(timezone.utc)
    next_collection = calculate_next_candle_completion_time(interval_minutes, buffer_seconds)
    wait_seconds = (next_collection - now).total_seconds()
    return max(0.0, wait_seconds)
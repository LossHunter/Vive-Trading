"""
통계 데이터 생성 서비스

이 모듈은 데이터베이스에 저장된 거래 데이터, 계좌 정보, 신호 데이터 등을 기반으로
다양한 통계 데이터를 생성하는 함수들을 제공합니다.

주요 기능:
- 수익성 통계: 거래 전후 잔액 변화, 코인별/모델별 수익률, 손절/익절 달성률
- 자산 통계: 총 자산 변화 추이, 코인별 보유 비중, 시간대별 자산 변화, 모델별 자산 비교
- 리스크 관리 통계: 손절가/익절가 달성률
- 모델별 통계: 평균 수익률, 신뢰도 분포, 선호 코인
- 기술 지표 통계: 기술 지표와 수익률 간의 상관관계 분석

사용 예시:
    from app.db.database import SessionLocal
    from app.services.statistics_service import get_balance_change_statistics
    
    db = SessionLocal()
    stats = get_balance_change_statistics(db)
    db.close()
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, case, or_
from uuid import UUID

from app.db.database import (
    LLMTradingExecution,
    LLMTradingSignal,
    AccountInformation,
    UpbitAccounts,
    UpbitIndicators,
    UpbitTicker,
)
from app.core.config import LLMAccountConfig

logger = logging.getLogger(__name__)


# ==================== 유틸리티 함수 ====================

def _get_model_name_from_account_id(account_id: Optional[UUID]) -> Optional[str]:
    """
    account_id로부터 모델명을 조회하는 내부 유틸리티 함수
    
    Args:
        account_id: UUID 형식의 계정 ID (예: "00000000-0000-0000-0000-000000000001")
    
    Returns:
        Optional[str]: 모델명 (예: "google/gemma-3-27b-it"), 조회 실패 시 None
    
    설명:
        - account_id는 UUID 형식이며, 마지막 12자리 숫자가 모델을 식별합니다
        - LLMAccountConfig를 통해 account_id와 모델명 간의 매핑을 조회합니다
        - 변환 실패 시 None을 반환하여 오류를 방지합니다
    """
    if not account_id:
        return None
    try:
        # LLMAccountConfig를 통해 account_id를 모델명으로 변환
        return LLMAccountConfig.get_model_for_account_id(str(account_id))
    except Exception:
        # 변환 실패 시 None 반환 (로그는 상위 함수에서 처리)
        return None


def _get_user_id_from_account_id(account_id: Optional[UUID]) -> Optional[int]:
    """
    account_id로부터 user_id를 추출하는 내부 유틸리티 함수
    
    Args:
        account_id: UUID 형식의 계정 ID (예: "00000000-0000-0000-0000-000000000001")
    
    Returns:
        Optional[int]: user_id (1, 2, 3, 4 중 하나), 추출 실패 시 None
    
    설명:
        - account_id의 마지막 12자리 숫자에서 앞의 0을 제거하여 user_id를 추출합니다
        - AccountInformation 테이블은 user_id를 문자열로 저장하므로 이를 변환합니다
        - 예: "00000000-0000-0000-0000-000000000001" -> 1
    """
    if not account_id:
        return None
    try:
        # UUID의 마지막 부분(12자리)에서 앞의 0을 제거하고 숫자로 변환
        # 예: "000000000001" -> "1" -> 1
        suffix = str(account_id).split("-")[-1].lstrip("0") or "0"
        return int(suffix)
    except Exception:
        # 변환 실패 시 None 반환
        return None


# ==================== 수익성 통계 ====================

def get_balance_change_statistics(
    db: Session,
    account_id: Optional[UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[Dict]:
    """
    거래 전후 잔액 변화 통계를 조회하는 함수
    
    각 거래 실행 기록에서 거래 전후의 잔액 변화를 계산하여 반환합니다.
    수익/손실 금액과 수익률을 포함하여 각 거래의 성과를 분석할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        account_id: 특정 계정 ID로 필터링 (None이면 전체 계정)
        start_date: 조회 시작 날짜 (None이면 제한 없음)
        end_date: 조회 종료 날짜 (None이면 제한 없음)
    
    Returns:
        List[Dict]: 각 거래별 잔액 변화 데이터 리스트
            각 딕셔너리에는 다음 키가 포함됩니다:
            - execution_id: 실행 기록 ID
            - account_id: 계정 ID (문자열)
            - model_name: 모델명
            - coin: 거래한 코인 심볼
            - signal_type: 신호 타입 (buy_to_enter, sell_to_exit, hold)
            - execution_status: 실행 상태 (success, failed, skipped)
            - balance_before: 거래 전 잔액 (KRW)
            - balance_after: 거래 후 잔액 (KRW)
            - balance_change: 잔액 변화량 (balance_after - balance_before)
            - balance_change_rate: 잔액 변화율 (%, balance_before 기준)
            - executed_at: 거래 실행 시각 (ISO 형식)
    
    처리 과정:
        1. LLMTradingExecution 테이블에서 balance_before와 balance_after가 모두 있는 기록만 조회
        2. account_id, start_date, end_date로 필터링
        3. executed_at 기준으로 정렬
        4. 각 거래에 대해 잔액 변화량과 변화율 계산
        5. 모델명을 account_id로부터 조회하여 포함
    """
    # 거래 전후 잔액이 모두 있는 실행 기록만 조회
    query = db.query(LLMTradingExecution).filter(
        LLMTradingExecution.balance_before.isnot(None),
        LLMTradingExecution.balance_after.isnot(None),
    )
    
    # 계정 ID로 필터링 (지정된 경우)
    if account_id:
        query = query.filter(LLMTradingExecution.account_id == account_id)
    # 시작 날짜로 필터링 (지정된 경우)
    if start_date:
        query = query.filter(LLMTradingExecution.executed_at >= start_date)
    # 종료 날짜로 필터링 (지정된 경우)
    if end_date:
        query = query.filter(LLMTradingExecution.executed_at <= end_date)
    
    # 실행 시각 기준으로 정렬하여 조회
    executions = query.order_by(LLMTradingExecution.executed_at).all()
    
    results = []
    for exec in executions:
        # 잔액 변화량과 변화율 초기화
        balance_change = None
        balance_change_rate = None
        
        # 거래 전후 잔액이 모두 있는 경우에만 계산
        if exec.balance_before and exec.balance_after:
            # 잔액 변화량 = 거래 후 잔액 - 거래 전 잔액
            balance_change = float(exec.balance_after - exec.balance_before)
            # 잔액 변화율 = (변화량 / 거래 전 잔액) * 100
            if exec.balance_before > 0:
                balance_change_rate = float((exec.balance_after - exec.balance_before) / exec.balance_before * 100)
        
        # account_id로부터 모델명 조회
        model_name = _get_model_name_from_account_id(exec.account_id)
        
        # 결과 딕셔너리 생성
        results.append({
            "execution_id": exec.id,
            "account_id": str(exec.account_id) if exec.account_id else None,
            "model_name": model_name,
            "coin": exec.coin,
            "signal_type": exec.signal_type,
            "execution_status": exec.execution_status,
            "balance_before": float(exec.balance_before) if exec.balance_before else None,
            "balance_after": float(exec.balance_after) if exec.balance_after else None,
            "balance_change": balance_change,
            "balance_change_rate": balance_change_rate,
            "executed_at": exec.executed_at.isoformat() if exec.executed_at else None,
        })
    
    return results


def get_coin_profit_statistics(
    db: Session,
    coin: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict:
    """
    코인별 수익률 통계를 조회하는 함수
    
    각 코인별로 총 거래 횟수, 총 수익, 평균 수익을 집계하여 반환합니다.
    특정 코인에 대한 수익성 분석이나 전체 코인 간 비교에 활용할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        coin: 특정 코인으로 필터링 (None이면 전체 코인)
        start_date: 조회 시작 날짜 (None이면 제한 없음)
        end_date: 조회 종료 날짜 (None이면 제한 없음)
    
    Returns:
        Dict: 코인별 수익률 통계 데이터
            - coin: 필터링된 코인 ("all" 또는 특정 코인명)
            - statistics: 코인별 통계 리스트
                각 항목에는 다음이 포함됩니다:
                - coin: 코인 심볼
                - total_trades: 총 거래 횟수
                - total_profit: 총 수익 (KRW, 성공한 거래만 집계)
                - avg_profit: 평균 수익 (KRW, 성공한 거래만 집계)
    
    처리 과정:
        1. LLMTradingExecution 테이블에서 성공한 거래만 조회
        2. 코인별로 그룹화하여 집계
        3. 각 코인별 총 거래 횟수, 총 수익, 평균 수익 계산
        4. 필터링 조건(coin, start_date, end_date) 적용
    """
    # 코인별 집계를 위한 쿼리 생성
    # count: 총 거래 횟수
    # sum: 총 수익 (성공한 거래만)
    # avg: 평균 수익 (성공한 거래만)
    query = db.query(
        LLMTradingExecution.coin,
        func.count(LLMTradingExecution.id).label("total_trades"),
        # 성공한 거래의 잔액 변화량 합계
        func.sum(
            case(
                (and_(
                    LLMTradingExecution.balance_after.isnot(None),
                    LLMTradingExecution.balance_before.isnot(None),
                    LLMTradingExecution.execution_status == "success"
                ),
                LLMTradingExecution.balance_after - LLMTradingExecution.balance_before),
                else_=Decimal("0")
            )
        ).label("total_profit"),
        # 성공한 거래의 잔액 변화량 평균
        func.avg(
            case(
                (and_(
                    LLMTradingExecution.balance_after.isnot(None),
                    LLMTradingExecution.balance_before.isnot(None),
                    LLMTradingExecution.execution_status == "success"
                ),
                LLMTradingExecution.balance_after - LLMTradingExecution.balance_before),
                else_=None
            )
        ).label("avg_profit"),
    )
    
    # 특정 코인으로 필터링
    if coin:
        query = query.filter(LLMTradingExecution.coin == coin)
    # 시작 날짜로 필터링
    if start_date:
        query = query.filter(LLMTradingExecution.executed_at >= start_date)
    # 종료 날짜로 필터링
    if end_date:
        query = query.filter(LLMTradingExecution.executed_at <= end_date)
    
    # 코인별로 그룹화하여 집계 결과 조회
    results = query.group_by(LLMTradingExecution.coin).all()
    
    # 결과를 딕셔너리 리스트로 변환
    statistics = []
    for r in results:
        statistics.append({
            "coin": r.coin,
            "total_trades": r.total_trades,
            "total_profit": float(r.total_profit) if r.total_profit else 0,
            "avg_profit": float(r.avg_profit) if r.avg_profit else None,
        })
    
    return {
        "coin": coin or "all",  # 필터링된 코인명 또는 "all"
        "statistics": statistics
    }


def get_model_profit_comparison(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[Dict]:
    """
    모델별 수익률 비교 통계를 조회하는 함수
    
    각 LLM 모델별로 총 거래 횟수, 총 수익, 평균 수익을 집계하여 반환합니다.
    여러 모델의 성과를 비교하여 어떤 모델이 더 우수한지 분석할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        start_date: 조회 시작 날짜 (None이면 제한 없음)
        end_date: 조회 종료 날짜 (None이면 제한 없음)
    
    Returns:
        List[Dict]: 모델별 수익률 데이터 리스트
            각 딕셔너리에는 다음이 포함됩니다:
            - account_id: 계정 ID (문자열)
            - model_name: 모델명 (예: "google/gemma-3-27b-it")
            - total_trades: 총 거래 횟수
            - total_profit: 총 수익 (KRW, 성공한 거래만 집계)
            - avg_profit: 평균 수익 (KRW, 성공한 거래만 집계)
    
    처리 과정:
        1. LLMTradingExecution 테이블에서 성공한 거래만 조회
        2. account_id별로 그룹화하여 집계
        3. 각 모델별 총 거래 횟수, 총 수익, 평균 수익 계산
        4. account_id를 모델명으로 변환하여 포함
    """
    query = db.query(
        LLMTradingExecution.account_id,
        func.count(LLMTradingExecution.id).label("total_trades"),
        func.sum(
            case(
                (and_(
                    LLMTradingExecution.balance_after.isnot(None),
                    LLMTradingExecution.balance_before.isnot(None),
                    LLMTradingExecution.execution_status == "success"
                ),
                LLMTradingExecution.balance_after - LLMTradingExecution.balance_before),
                else_=Decimal("0")
            )
        ).label("total_profit"),
        func.avg(
            case(
                (and_(
                    LLMTradingExecution.balance_after.isnot(None),
                    LLMTradingExecution.balance_before.isnot(None),
                    LLMTradingExecution.execution_status == "success"
                ),
                LLMTradingExecution.balance_after - LLMTradingExecution.balance_before),
                else_=None
            )
        ).label("avg_profit"),
    )
    
    if start_date:
        query = query.filter(LLMTradingExecution.executed_at >= start_date)
    if end_date:
        query = query.filter(LLMTradingExecution.executed_at <= end_date)
    
    results = query.group_by(LLMTradingExecution.account_id).all()
    
    model_stats = []
    for r in results:
        model_name = _get_model_name_from_account_id(r.account_id)
        
        model_stats.append({
            "account_id": str(r.account_id) if r.account_id else None,
            "model_name": model_name,
            "total_trades": r.total_trades,
            "total_profit": float(r.total_profit) if r.total_profit else 0,
            "avg_profit": float(r.avg_profit) if r.avg_profit else None,
        })
    
    return model_stats


def get_stop_loss_profit_target_achievement(
    db: Session,
    account_id: Optional[UUID] = None,
    coin: Optional[str] = None
) -> Dict:
    """
    손절/익절 달성률 통계를 조회하는 함수
    
    거래 신호에서 설정한 손절가(stop_loss)와 익절가(profit_target)가
    실제로 달성되었는지 확인하여 달성률을 계산합니다.
    리스크 관리 전략의 효과를 평가하는 데 활용할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        account_id: 특정 계정 ID로 필터링 (None이면 전체 계정)
        coin: 특정 코인으로 필터링 (None이면 전체 코인)
    
    Returns:
        Dict: 손절/익절 달성률 데이터
            - stop_loss: 손절가 달성률 정보
                - hit: 손절가 달성 횟수
                - total: 손절가가 설정된 총 거래 수
                - achievement_rate: 달성률 (%)
            - profit_target: 익절가 달성률 정보
                - hit: 익절가 달성 횟수
                - total: 익절가가 설정된 총 거래 수
                - achievement_rate: 달성률 (%)
    
    처리 과정:
        1. LLMTradingSignal에서 stop_loss 또는 profit_target이 설정된 신호 조회
        2. 각 신호에 대응하는 실행 기록(LLMTradingExecution) 조회
        3. 실행 가격과 설정된 손절가/익절가 비교
        4. 손절가: 실행 가격 <= 손절가인 경우 달성
        5. 익절가: 실행 가격 >= 익절가인 경우 달성
        6. 달성 횟수와 총 거래 수를 기반으로 달성률 계산
    """
    # 손절가 또는 익절가가 설정된 신호만 조회
    signals_query = db.query(LLMTradingSignal).filter(
        or_(
            LLMTradingSignal.stop_loss.isnot(None),
            LLMTradingSignal.profit_target.isnot(None)
        )
    )
    
    # 계정 ID로 필터링
    if account_id:
        signals_query = signals_query.filter(LLMTradingSignal.account_id == account_id)
    # 코인으로 필터링
    if coin:
        signals_query = signals_query.filter(LLMTradingSignal.coin == coin)
    
    signals = signals_query.all()
    
    # 손절가/익절가 달성 통계 변수 초기화
    stop_loss_hit = 0      # 손절가 달성 횟수
    stop_loss_total = 0    # 손절가 설정된 총 거래 수
    profit_target_hit = 0   # 익절가 달성 횟수
    profit_target_total = 0 # 익절가 설정된 총 거래 수
    
    # 각 신호에 대해 실행 기록 확인
    for signal in signals:
        # 해당 신호의 실행 기록 조회 (성공한 거래만)
        execution = db.query(LLMTradingExecution).filter(
            LLMTradingExecution.prompt_id == signal.prompt_id,
            LLMTradingExecution.coin == signal.coin,
            LLMTradingExecution.execution_status == "success"
        ).first()
        
        # 실행 기록이 없거나 실행 가격이 없으면 건너뛰기
        if not execution or not execution.executed_price:
            continue
        
        executed_price = float(execution.executed_price)
        
        # 손절가 달성 여부 확인
        if signal.stop_loss:
            stop_loss_total += 1
            # 실행 가격이 손절가 이하이면 손절가 달성
            if executed_price <= float(signal.stop_loss):
                stop_loss_hit += 1
        
        # 익절가 달성 여부 확인
        if signal.profit_target:
            profit_target_total += 1
            # 실행 가격이 익절가 이상이면 익절가 달성
            if executed_price >= float(signal.profit_target):
                profit_target_hit += 1
    
    # 결과 반환
    return {
        "stop_loss": {
            "hit": stop_loss_hit,
            "total": stop_loss_total,
            "achievement_rate": (stop_loss_hit / stop_loss_total * 100) if stop_loss_total > 0 else 0,
        },
        "profit_target": {
            "hit": profit_target_hit,
            "total": profit_target_total,
            "achievement_rate": (profit_target_hit / profit_target_total * 100) if profit_target_total > 0 else 0,
        }
    }


# ==================== 자산 통계 ====================

def get_total_asset_trend(
    db: Session,
    account_id: Optional[UUID] = None,
    days: int = 30
) -> List[Dict]:
    """
    총 자산 변화 추이를 조회하는 함수
    
    AccountInformation 테이블에서 일정 기간 동안의 자산 변화를 시간순으로 조회합니다.
    자산의 증가/감소 추세를 파악하거나 특정 시점의 자산 상태를 확인할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        account_id: 특정 계정 ID로 필터링 (None이면 전체 계정)
        days: 조회할 일수 (기본값: 30일)
    
    Returns:
        List[Dict]: 시간대별 총 자산 데이터 리스트
            각 딕셔너리에는 다음이 포함됩니다:
            - user_id: 사용자 ID
            - username: 사용자 이름
            - model_name: 모델명
            - total: 총 자산 금액 (KRW 기준)
            - btc, eth, doge, sol, xrp: 각 코인 보유량 (KRW 기준)
            - krw: 원화 잔액
            - created_at: 기록 생성 시각 (ISO 형식)
    
    처리 과정:
        1. 현재 시각에서 days일 전까지의 AccountInformation 기록 조회
        2. account_id가 지정된 경우 user_id로 변환하여 필터링
        3. created_at 기준으로 정렬
        4. 각 기록의 자산 정보를 딕셔너리로 변환
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = db.query(AccountInformation).filter(
        AccountInformation.created_at >= start_date
    )
    
    if account_id:
        user_id = _get_user_id_from_account_id(account_id)
        if user_id:
            query = query.filter(AccountInformation.user_id == str(user_id))
    
    records = query.order_by(AccountInformation.created_at).all()
    
    results = []
    for record in records:
        results.append({
            "user_id": record.user_id,
            "username": record.username,
            "model_name": record.model_name,
            "total": float(record.total) if record.total else 0,
            "btc": float(record.btc) if record.btc else 0,
            "eth": float(record.eth) if record.eth else 0,
            "doge": float(record.doge) if record.doge else 0,
            "sol": float(record.sol) if record.sol else 0,
            "xrp": float(record.xrp) if record.xrp else 0,
            "krw": float(record.krw) if record.krw else 0,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        })
    
    return results


def get_coin_holdings_distribution(
    db: Session,
    account_id: Optional[UUID] = None,
    date: Optional[datetime] = None
) -> Dict:
    """
    코인별 보유 비중을 조회하는 함수
    
    특정 시점에서 각 계정이 보유한 코인별 자산 비중을 계산합니다.
    포트폴리오 구성 분석이나 자산 분산 정도를 확인하는 데 활용할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        account_id: 특정 계정 ID로 필터링 (None이면 전체 계정)
        date: 조회할 시점 (None이면 현재 시각)
    
    Returns:
        Dict: 코인별 보유 비중 데이터
            - date: 조회 시점 (ISO 형식)
            - accounts: 계정별 보유 정보 리스트
                각 계정 정보에는 다음이 포함됩니다:
                - user_id: 사용자 ID
                - username: 사용자 이름
                - model_name: 모델명
                - total: 총 자산 금액 (KRW 기준)
                - holdings: 코인별 보유 정보 딕셔너리
                    각 코인(키: BTC, ETH, DOGE, SOL, XRP)에 대해:
                    - value: 보유 금액 (KRW 기준)
                    - percentage: 총 자산 대비 비중 (%)
    
    처리 과정:
        1. 지정된 시점 이전의 AccountInformation 기록 중 각 계정의 최신 기록 조회
        2. 각 계정의 총 자산과 코인별 보유 금액 계산
        3. 보유 금액이 0보다 큰 코인만 포함
        4. 각 코인의 총 자산 대비 비중(%) 계산
    """
    if not date:
        date = datetime.now(timezone.utc)
    
    query = db.query(AccountInformation).filter(
        AccountInformation.created_at <= date
    )
    
    if account_id:
        user_id = _get_user_id_from_account_id(account_id)
        if user_id:
            query = query.filter(AccountInformation.user_id == str(user_id))
    
    subquery = (
        db.query(
            AccountInformation.user_id,
            func.max(AccountInformation.created_at).label("max_created_at")
        )
        .filter(AccountInformation.created_at <= date)
        .group_by(AccountInformation.user_id)
        .subquery()
    )
    
    records = (
        db.query(AccountInformation)
        .join(
            subquery,
            and_(
                AccountInformation.user_id == subquery.c.user_id,
                AccountInformation.created_at == subquery.c.max_created_at
            )
        )
        .all()
    )
    
    all_holdings = []
    for record in records:
        total = float(record.total) if record.total else 0
        
        holdings = {}
        coins = [
            ("BTC", record.btc),
            ("ETH", record.eth),
            ("DOGE", record.doge),
            ("SOL", record.sol),
            ("XRP", record.xrp),
        ]
        
        for coin_name, coin_value in coins:
            value = float(coin_value) if coin_value else 0
            if value > 0:
                holdings[coin_name] = {
                    "value": value,
                    "percentage": (value / total * 100) if total > 0 else 0,
                }
        
        all_holdings.append({
            "user_id": record.user_id,
            "username": record.username,
            "model_name": record.model_name,
            "total": total,
            "holdings": holdings,
        })
    
    return {
        "date": date.isoformat(),
        "accounts": all_holdings
    }


def get_hourly_asset_changes(
    db: Session,
    account_id: Optional[UUID] = None,
    days: int = 7
) -> List[Dict]:
    """
    시간대별 자산 변화를 조회하는 함수
    
    AccountInformation 테이블에서 시간 단위로 그룹화하여
    각 시간대별 최대, 최소, 평균 자산을 계산합니다.
    시간대별 자산 변동 패턴을 분석하거나 특정 시간대의 자산 변화를 확인할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        account_id: 특정 계정 ID로 필터링 (None이면 전체 계정)
        days: 조회할 일수 (기본값: 7일)
    
    Returns:
        List[Dict]: 시간대별 자산 변화 데이터 리스트
            각 딕셔너리에는 다음이 포함됩니다:
            - hour: 시간대 (ISO 형식, 시간 단위로 반올림)
            - user_id: 사용자 ID
            - model_name: 모델명
            - max_total: 해당 시간대의 최대 자산 (KRW)
            - min_total: 해당 시간대의 최소 자산 (KRW)
            - avg_total: 해당 시간대의 평균 자산 (KRW)
    
    처리 과정:
        1. 현재 시각에서 days일 전까지의 AccountInformation 기록 조회
        2. created_at을 시간 단위로 반올림하여 그룹화
        3. 각 시간대별로 최대, 최소, 평균 자산 계산
        4. account_id가 지정된 경우 user_id로 변환하여 필터링
        5. 시간대 순서로 정렬하여 반환
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = db.query(
        func.date_trunc('hour', AccountInformation.created_at).label("hour"),
        AccountInformation.user_id,
        AccountInformation.model_name,
        func.max(AccountInformation.total).label("max_total"),
        func.min(AccountInformation.total).label("min_total"),
        func.avg(AccountInformation.total).label("avg_total"),
    ).filter(
        AccountInformation.created_at >= start_date
    )
    
    if account_id:
        user_id = _get_user_id_from_account_id(account_id)
        if user_id:
            query = query.filter(AccountInformation.user_id == str(user_id))
    
    results = query.group_by(
        func.date_trunc('hour', AccountInformation.created_at),
        AccountInformation.user_id,
        AccountInformation.model_name
    ).order_by("hour").all()
    
    return [
        {
            "hour": r.hour.isoformat() if r.hour else None,
            "user_id": r.user_id,
            "model_name": r.model_name,
            "max_total": float(r.max_total) if r.max_total else 0,
            "min_total": float(r.min_total) if r.min_total else 0,
            "avg_total": float(r.avg_total) if r.avg_total else 0,
        }
        for r in results
    ]


def get_model_asset_comparison(
    db: Session,
    date: Optional[datetime] = None
) -> List[Dict]:
    """
    모델별 자산 비교를 조회하는 함수
    
    특정 시점에서 각 모델의 최신 자산 정보를 조회하여 비교합니다.
    모델 간 자산 규모를 비교하거나 특정 시점의 모델별 자산 상태를 확인할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        date: 조회할 시점 (None이면 현재 시각)
    
    Returns:
        List[Dict]: 모델별 자산 데이터 리스트
            각 딕셔너리에는 다음이 포함됩니다:
            - user_id: 사용자 ID
            - username: 사용자 이름
            - model_name: 모델명
            - total: 총 자산 금액 (KRW 기준)
            - btc, eth, doge, sol, xrp: 각 코인 보유량 (KRW 기준)
            - krw: 원화 잔액
            - date: 조회 시점 (ISO 형식)
    
    처리 과정:
        1. 지정된 시점 이전의 AccountInformation 기록 중 각 계정의 최신 기록 조회
        2. 각 계정의 자산 정보를 딕셔너리로 변환
        3. 모든 계정의 정보를 리스트로 반환
    """
    if not date:
        date = datetime.now(timezone.utc)
    
    subquery = (
        db.query(
            AccountInformation.user_id,
            func.max(AccountInformation.created_at).label("max_created_at")
        )
        .filter(AccountInformation.created_at <= date)
        .group_by(AccountInformation.user_id)
        .subquery()
    )
    
    records = (
        db.query(AccountInformation)
        .join(
            subquery,
            and_(
                AccountInformation.user_id == subquery.c.user_id,
                AccountInformation.created_at == subquery.c.max_created_at
            )
        )
        .all()
    )
    
    return [
        {
            "user_id": r.user_id,
            "username": r.username,
            "model_name": r.model_name,
            "total": float(r.total) if r.total else 0,
            "btc": float(r.btc) if r.btc else 0,
            "eth": float(r.eth) if r.eth else 0,
            "doge": float(r.doge) if r.doge else 0,
            "sol": float(r.sol) if r.sol else 0,
            "xrp": float(r.xrp) if r.xrp else 0,
            "krw": float(r.krw) if r.krw else 0,
            "date": date.isoformat(),
        }
        for r in records
    ]


def get_max_profit_loss(
    db: Session,
    account_id: Optional[UUID] = None,
    coin: Optional[str] = None
) -> Dict:
    """
    최대 수익/손실을 조회하는 함수
    
    성공한 거래 중에서 가장 큰 수익과 가장 큰 손실을 찾아 반환합니다.
    최고 성과와 최악 성과를 파악하여 거래 전략의 변동성을 분석할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        account_id: 특정 계정 ID로 필터링 (None이면 전체 계정)
        coin: 특정 코인으로 필터링 (None이면 전체 코인)
    
    Returns:
        Dict: 최대 수익/손실 데이터
            - max_profit: 최대 수익 거래 정보 (None이면 수익 거래 없음)
                - execution_id: 실행 기록 ID
                - account_id: 계정 ID
                - model_name: 모델명
                - coin: 코인 심볼
                - profit: 수익 금액 (KRW)
                - profit_rate: 수익률 (%)
                - executed_at: 거래 실행 시각
            - max_loss: 최대 손실 거래 정보 (None이면 손실 거래 없음)
                - execution_id: 실행 기록 ID
                - account_id: 계정 ID
                - model_name: 모델명
                - coin: 코인 심볼
                - loss: 손실 금액 (KRW, 절댓값)
                - loss_rate: 손실률 (%)
                - executed_at: 거래 실행 시각
            - total_profits: 수익 거래 총 개수
            - total_losses: 손실 거래 총 개수
            - total_trades: 전체 거래 개수
    
    처리 과정:
        1. 성공한 거래 중 잔액 정보가 있는 거래만 조회
        2. 각 거래의 잔액 변화량 계산 (balance_after - balance_before)
        3. 변화량이 양수면 수익, 음수면 손실로 분류
        4. 수익 거래 중 최대값, 손실 거래 중 최대값(절댓값) 찾기
        5. 통계 정보와 함께 반환
    """
    query = db.query(LLMTradingExecution).filter(
        LLMTradingExecution.execution_status == "success",
        LLMTradingExecution.balance_before.isnot(None),
        LLMTradingExecution.balance_after.isnot(None),
    )
    
    if account_id:
        query = query.filter(LLMTradingExecution.account_id == account_id)
    if coin:
        query = query.filter(LLMTradingExecution.coin == coin)
    
    executions = query.all()
    
    profits = []
    losses = []
    
    for exec in executions:
        change = float(exec.balance_after - exec.balance_before)
        model_name = _get_model_name_from_account_id(exec.account_id)
        
        if change > 0:
            profits.append({
                "execution_id": exec.id,
                "account_id": str(exec.account_id) if exec.account_id else None,
                "model_name": model_name,
                "coin": exec.coin,
                "profit": change,
                "profit_rate": float((change / float(exec.balance_before)) * 100) if exec.balance_before > 0 else None,
                "executed_at": exec.executed_at.isoformat() if exec.executed_at else None,
            })
        elif change < 0:
            losses.append({
                "execution_id": exec.id,
                "account_id": str(exec.account_id) if exec.account_id else None,
                "model_name": model_name,
                "coin": exec.coin,
                "loss": abs(change),
                "loss_rate": float((abs(change) / float(exec.balance_before)) * 100) if exec.balance_before > 0 else None,
                "executed_at": exec.executed_at.isoformat() if exec.executed_at else None,
            })
    
    max_profit = max(profits, key=lambda x: x["profit"]) if profits else None
    max_loss = max(losses, key=lambda x: x["loss"]) if losses else None
    
    return {
        "max_profit": max_profit,
        "max_loss": max_loss,
        "total_profits": len(profits),
        "total_losses": len(losses),
        "total_trades": len(executions),
    }


# ==================== 리스크 관리 통계 ====================

def get_stop_loss_achievement_rate(
    db: Session,
    account_id: Optional[UUID] = None,
    coin: Optional[str] = None
) -> Dict:
    """
    손절가 달성률을 조회하는 함수
    
    거래 신호에서 설정한 손절가(stop_loss)가 실제로 달성되었는지 확인하여
    달성률을 계산합니다. 손절 전략의 효과를 평가하거나 리스크 관리 성과를 분석하는 데 활용할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        account_id: 특정 계정 ID로 필터링 (None이면 전체 계정)
        coin: 특정 코인으로 필터링 (None이면 전체 코인)
    
    Returns:
        Dict: 손절가 달성률 데이터
            - hit_count: 손절가 달성 횟수
            - total_count: 손절가가 설정된 총 거래 수
            - achievement_rate: 달성률 (%)
            - details: 상세 정보 리스트 (최대 10개)
                각 항목에는 다음이 포함됩니다:
                - signal_id: 신호 ID
                - coin: 코인 심볼
                - stop_loss: 설정된 손절가
                - executed_price: 실제 실행 가격
                - hit: 달성 여부 (True/False)
    
    처리 과정:
        1. LLMTradingSignal에서 stop_loss가 설정된 신호 조회
        2. 각 신호에 대응하는 실행 기록(LLMTradingExecution) 조회
        3. 실행 가격이 손절가 이하인지 확인 (executed_price <= stop_loss)
        4. 달성 횟수와 총 거래 수를 기반으로 달성률 계산
        5. 상세 정보는 최대 10개만 반환하여 성능 최적화
    """
    signals_query = db.query(LLMTradingSignal).filter(
        LLMTradingSignal.stop_loss.isnot(None)
    )
    
    if account_id:
        signals_query = signals_query.filter(LLMTradingSignal.account_id == account_id)
    if coin:
        signals_query = signals_query.filter(LLMTradingSignal.coin == coin)
    
    signals = signals_query.all()
    
    hit_count = 0
    total_count = 0
    details = []
    
    for signal in signals:
        execution = db.query(LLMTradingExecution).filter(
            LLMTradingExecution.prompt_id == signal.prompt_id,
            LLMTradingExecution.coin == signal.coin,
            LLMTradingExecution.execution_status == "success"
        ).first()
        
        if execution and execution.executed_price:
            total_count += 1
            executed_price = float(execution.executed_price)
            stop_loss_price = float(signal.stop_loss)
            hit = executed_price <= stop_loss_price
            
            if hit:
                hit_count += 1
            
            details.append({
                "signal_id": signal.id,
                "coin": signal.coin,
                "stop_loss": stop_loss_price,
                "executed_price": executed_price,
                "hit": hit,
            })
    
    return {
        "hit_count": hit_count,
        "total_count": total_count,
        "achievement_rate": (hit_count / total_count * 100) if total_count > 0 else 0,
        "details": details[:10]  # 최대 10개만 반환
    }


def get_profit_target_achievement_rate(
    db: Session,
    account_id: Optional[UUID] = None,
    coin: Optional[str] = None
) -> Dict:
    """
    익절가 달성률을 조회하는 함수
    
    거래 신호에서 설정한 익절가(profit_target)가 실제로 달성되었는지 확인하여
    달성률을 계산합니다. 익절 전략의 효과를 평가하거나 수익 실현 성과를 분석하는 데 활용할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        account_id: 특정 계정 ID로 필터링 (None이면 전체 계정)
        coin: 특정 코인으로 필터링 (None이면 전체 코인)
    
    Returns:
        Dict: 익절가 달성률 데이터
            - hit_count: 익절가 달성 횟수
            - total_count: 익절가가 설정된 총 거래 수
            - achievement_rate: 달성률 (%)
            - details: 상세 정보 리스트 (최대 10개)
                각 항목에는 다음이 포함됩니다:
                - signal_id: 신호 ID
                - coin: 코인 심볼
                - profit_target: 설정된 익절가
                - executed_price: 실제 실행 가격
                - hit: 달성 여부 (True/False)
    
    처리 과정:
        1. LLMTradingSignal에서 profit_target이 설정된 신호 조회
        2. 각 신호에 대응하는 실행 기록(LLMTradingExecution) 조회
        3. 실행 가격이 익절가 이상인지 확인 (executed_price >= profit_target)
        4. 달성 횟수와 총 거래 수를 기반으로 달성률 계산
        5. 상세 정보는 최대 10개만 반환하여 성능 최적화
    """
    signals_query = db.query(LLMTradingSignal).filter(
        LLMTradingSignal.profit_target.isnot(None)
    )
    
    if account_id:
        signals_query = signals_query.filter(LLMTradingSignal.account_id == account_id)
    if coin:
        signals_query = signals_query.filter(LLMTradingSignal.coin == coin)
    
    signals = signals_query.all()
    
    hit_count = 0
    total_count = 0
    details = []
    
    for signal in signals:
        execution = db.query(LLMTradingExecution).filter(
            LLMTradingExecution.prompt_id == signal.prompt_id,
            LLMTradingExecution.coin == signal.coin,
            LLMTradingExecution.execution_status == "success"
        ).first()
        
        if execution and execution.executed_price:
            total_count += 1
            executed_price = float(execution.executed_price)
            profit_target_price = float(signal.profit_target)
            hit = executed_price >= profit_target_price
            
            if hit:
                hit_count += 1
            
            details.append({
                "signal_id": signal.id,
                "coin": signal.coin,
                "profit_target": profit_target_price,
                "executed_price": executed_price,
                "hit": hit,
            })
    
    return {
        "hit_count": hit_count,
        "total_count": total_count,
        "achievement_rate": (hit_count / total_count * 100) if total_count > 0 else 0,
        "details": details[:10]  # 최대 10개만 반환
    }


# ==================== 모델별 통계 ====================

def get_model_avg_profit_rate(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[Dict]:
    """
    모델별 평균 수익률을 조회하는 함수
    
    각 LLM 모델별로 평균 수익률을 계산하여 반환합니다.
    모델 간 성과를 비교하거나 특정 기간의 모델 성과를 분석하는 데 활용할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        start_date: 조회 시작 날짜 (None이면 제한 없음)
        end_date: 조회 종료 날짜 (None이면 제한 없음)
    
    Returns:
        List[Dict]: 모델별 평균 수익률 데이터 리스트
            각 딕셔너리에는 다음이 포함됩니다:
            - account_id: 계정 ID (문자열)
            - model_name: 모델명
            - trade_count: 거래 횟수
            - total_profit: 총 수익 (KRW)
            - avg_profit_rate: 평균 수익률 (%)
                계산식: ((balance_after - balance_before) / balance_before) * 100의 평균
    
    처리 과정:
        1. 성공한 거래만 조회
        2. account_id별로 그룹화
        3. 각 모델별로 거래 횟수, 총 수익, 평균 수익률 계산
        4. account_id를 모델명으로 변환하여 포함
    """
    query = db.query(
        LLMTradingExecution.account_id,
        func.count(LLMTradingExecution.id).label("trade_count"),
        func.sum(
            case(
                (and_(
                    LLMTradingExecution.balance_after.isnot(None),
                    LLMTradingExecution.balance_before.isnot(None),
                    LLMTradingExecution.execution_status == "success"
                ),
                LLMTradingExecution.balance_after - LLMTradingExecution.balance_before),
                else_=Decimal("0")
            )
        ).label("total_profit"),
        func.avg(
            case(
                (and_(
                    LLMTradingExecution.balance_after.isnot(None),
                    LLMTradingExecution.balance_before.isnot(None),
                    LLMTradingExecution.execution_status == "success",
                    LLMTradingExecution.balance_before > 0
                ),
                (LLMTradingExecution.balance_after - LLMTradingExecution.balance_before) / 
                LLMTradingExecution.balance_before * 100),
                else_=None
            )
        ).label("avg_profit_rate"),
    ).filter(
        LLMTradingExecution.execution_status == "success"
    )
    
    if start_date:
        query = query.filter(LLMTradingExecution.executed_at >= start_date)
    if end_date:
        query = query.filter(LLMTradingExecution.executed_at <= end_date)
    
    results = query.group_by(LLMTradingExecution.account_id).all()
    
    model_stats = []
    for r in results:
        model_name = _get_model_name_from_account_id(r.account_id)
        
        model_stats.append({
            "account_id": str(r.account_id) if r.account_id else None,
            "model_name": model_name,
            "trade_count": r.trade_count,
            "total_profit": float(r.total_profit) if r.total_profit else 0,
            "avg_profit_rate": float(r.avg_profit_rate) if r.avg_profit_rate else None,
        })
    
    return model_stats


def get_model_confidence_distribution(
    db: Session,
    account_id: Optional[UUID] = None
) -> Dict:
    """
    모델별 신뢰도 분포를 조회하는 함수
    
    각 LLM 모델이 거래 신호를 생성할 때 표현한 신뢰도(confidence)의
    통계적 분포를 계산합니다. 평균, 최소, 최대, 표준편차를 포함하여
    모델의 신뢰도 패턴을 분석할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        account_id: 특정 계정 ID로 필터링 (None이면 전체 계정)
    
    Returns:
        Dict: 모델별 신뢰도 분포 데이터
            - distributions: 모델별 분포 정보 리스트
                각 딕셔너리에는 다음이 포함됩니다:
                - account_id: 계정 ID (문자열)
                - model_name: 모델명
                - total_signals: 총 신호 개수
                - avg_confidence: 평균 신뢰도
                - min_confidence: 최소 신뢰도
                - max_confidence: 최대 신뢰도
                - std_confidence: 신뢰도 표준편차
    
    처리 과정:
        1. LLMTradingSignal에서 confidence가 설정된 신호만 조회
        2. account_id별로 그룹화
        3. 각 모델별로 신뢰도의 통계값(평균, 최소, 최대, 표준편차) 계산
        4. account_id를 모델명으로 변환하여 포함
    """
    query = db.query(
        LLMTradingSignal.account_id,
        func.count(LLMTradingSignal.id).label("total_signals"),
        func.avg(LLMTradingSignal.confidence).label("avg_confidence"),
        func.min(LLMTradingSignal.confidence).label("min_confidence"),
        func.max(LLMTradingSignal.confidence).label("max_confidence"),
        func.stddev(LLMTradingSignal.confidence).label("std_confidence"),
    ).filter(
        LLMTradingSignal.confidence.isnot(None)
    )
    
    if account_id:
        query = query.filter(LLMTradingSignal.account_id == account_id)
    
    results = query.group_by(LLMTradingSignal.account_id).all()
    
    distributions = []
    for r in results:
        model_name = _get_model_name_from_account_id(r.account_id)
        
        distributions.append({
            "account_id": str(r.account_id) if r.account_id else None,
            "model_name": model_name,
            "total_signals": r.total_signals,
            "avg_confidence": float(r.avg_confidence) if r.avg_confidence else None,
            "min_confidence": float(r.min_confidence) if r.min_confidence else None,
            "max_confidence": float(r.max_confidence) if r.max_confidence else None,
            "std_confidence": float(r.std_confidence) if r.std_confidence else None,
        })
    
    return {"distributions": distributions}


def get_model_preferred_coins(
    db: Session,
    account_id: Optional[UUID] = None
) -> List[Dict]:
    """
    모델별 선호 코인을 조회하는 함수
    
    각 LLM 모델이 어떤 코인에 대해 거래 신호를 가장 많이 생성했는지
    집계하여 반환합니다. 모델의 코인 선호도를 파악하거나
    특정 코인에 집중하는 모델을 식별할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        account_id: 특정 계정 ID로 필터링 (None이면 전체 계정)
    
    Returns:
        List[Dict]: 모델별 코인 선호도 데이터 리스트
            각 딕셔너리에는 다음이 포함됩니다:
            - account_id: 계정 ID (문자열)
            - model_name: 모델명
            - coin: 코인 심볼
            - signal_count: 해당 코인에 대한 신호 생성 횟수
            신호 개수가 많은 순서로 정렬되어 반환됩니다.
    
    처리 과정:
        1. LLMTradingSignal에서 모든 신호 조회
        2. account_id와 coin별로 그룹화하여 신호 개수 집계
        3. 신호 개수 기준으로 내림차순 정렬
        4. account_id를 모델명으로 변환하여 포함
    """
    query = db.query(
        LLMTradingSignal.account_id,
        LLMTradingSignal.coin,
        func.count(LLMTradingSignal.id).label("signal_count"),
    )
    
    if account_id:
        query = query.filter(LLMTradingSignal.account_id == account_id)
    
    results = query.group_by(
        LLMTradingSignal.account_id,
        LLMTradingSignal.coin
    ).order_by(desc("signal_count")).all()
    
    preferred_coins = []
    for r in results:
        model_name = _get_model_name_from_account_id(r.account_id)
        
        preferred_coins.append({
            "account_id": str(r.account_id) if r.account_id else None,
            "model_name": model_name,
            "coin": r.coin,
            "signal_count": r.signal_count,
        })
    
    return preferred_coins


# ==================== 기술 지표 vs 수익률 상관관계 ====================

def get_indicator_profit_correlation(
    db: Session,
    coin: str,
    indicator_type: str = "rsi14",  # "rsi14", "macd", "ema12", etc.
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[Dict]:
    """
    기술 지표와 수익률 간의 상관관계를 분석하는 함수
    
    거래 실행 시점의 기술 지표 값과 해당 거래의 수익률을 매칭하여
    기술 지표가 수익률에 미치는 영향을 분석할 수 있습니다.
    이를 통해 어떤 지표 값에서 수익률이 높은지 파악할 수 있습니다.
    
    Args:
        db: 데이터베이스 세션 객체
        coin: 분석할 코인 심볼 (예: "BTC", "ETH")
        indicator_type: 분석할 기술 지표 타입
            지원 지표:
            - "rsi14": RSI(14)
            - "macd": MACD
            - "macd_hist": MACD 히스토그램
            - "ema12", "ema20", "ema26", "ema50": 각각의 EMA
            - "atr3", "atr14": 각각의 ATR
        start_date: 조회 시작 날짜 (None이면 제한 없음)
        end_date: 조회 종료 날짜 (None이면 제한 없음)
    
    Returns:
        List[Dict]: 지표 값과 수익률 상관관계 데이터 리스트
            각 딕셔너리에는 다음이 포함됩니다:
            - execution_id: 실행 기록 ID
            - indicator_type: 지표 타입
            - indicator_value: 지표 값
            - profit_rate: 수익률 (%)
            - executed_at: 거래 실행 시각 (ISO 형식)
    
    처리 과정:
        1. 지정된 코인의 성공한 거래 실행 기록 조회
        2. 각 거래 실행 시점 이전의 최신 기술 지표 값 조회
        3. 거래 전후 잔액을 기반으로 수익률 계산
        4. 지표 값과 수익률을 매칭하여 반환
        5. 지표 값이나 수익률이 없는 경우 제외
    """
    # 지정된 코인의 성공한 거래 실행 기록 조회
    # 잔액 정보가 모두 있어야 수익률 계산 가능
    executions = db.query(LLMTradingExecution).filter(
        LLMTradingExecution.coin == coin,
        LLMTradingExecution.execution_status == "success",
        LLMTradingExecution.balance_before.isnot(None),
        LLMTradingExecution.balance_after.isnot(None),
    )
    
    # 시작 날짜로 필터링
    if start_date:
        executions = executions.filter(LLMTradingExecution.executed_at >= start_date)
    # 종료 날짜로 필터링
    if end_date:
        executions = executions.filter(LLMTradingExecution.executed_at <= end_date)
    
    # 모든 실행 기록 조회
    executions = executions.all()
    
    correlations = []
    # 각 거래 실행 기록에 대해 기술 지표 값과 수익률 매칭
    for exec in executions:
        # 실행 시각이 없으면 건너뛰기
        if not exec.executed_at:
            continue
        
        # 거래 실행 시각 이전의 최신 기술 지표 값 조회
        # market 형식: "KRW-BTC", "KRW-ETH" 등
        indicator = db.query(UpbitIndicators).filter(
            UpbitIndicators.market == f"KRW-{coin}",
            UpbitIndicators.candle_date_time_utc <= exec.executed_at
        ).order_by(desc(UpbitIndicators.candle_date_time_utc)).first()
        
        # 기술 지표 데이터가 없으면 건너뛰기
        if not indicator:
            continue
        
        # 수익률 계산: ((거래 후 잔액 - 거래 전 잔액) / 거래 전 잔액) * 100
        profit_rate = None
        if exec.balance_before and exec.balance_after and exec.balance_before > 0:
            profit_rate = float((exec.balance_after - exec.balance_before) / exec.balance_before * 100)
        
        # 지정된 지표 타입에 해당하는 지표 값 추출
        indicator_value = None
        if indicator_type == "rsi14":
            indicator_value = float(indicator.rsi14) if indicator.rsi14 else None
        elif indicator_type == "macd":
            indicator_value = float(indicator.macd) if indicator.macd else None
        elif indicator_type == "macd_hist":
            indicator_value = float(indicator.macd_hist) if indicator.macd_hist else None
        elif indicator_type == "ema12":
            indicator_value = float(indicator.ema12) if indicator.ema12 else None
        elif indicator_type == "ema20":
            indicator_value = float(indicator.ema20) if indicator.ema20 else None
        elif indicator_type == "ema26":
            indicator_value = float(indicator.ema26) if indicator.ema26 else None
        elif indicator_type == "ema50":
            indicator_value = float(indicator.ema50) if indicator.ema50 else None
        elif indicator_type == "atr3":
            indicator_value = float(indicator.atr3) if indicator.atr3 else None
        elif indicator_type == "atr14":
            indicator_value = float(indicator.atr14) if indicator.atr14 else None
        
        # 지표 값과 수익률이 모두 있는 경우에만 결과에 추가
        if indicator_value is not None and profit_rate is not None:
            correlations.append({
                "execution_id": exec.id,
                "indicator_type": indicator_type,
                "indicator_value": indicator_value,
                "profit_rate": profit_rate,
                "executed_at": exec.executed_at.isoformat(),
            })
    
    return correlations


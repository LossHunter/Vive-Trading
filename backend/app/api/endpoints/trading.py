"""
Trading API 엔드포인트
가상 거래 시뮬레이션 관련 API를 제공합니다.
"""

import logging
from typing import List, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.config import LLMAccountConfig
from app.services.trading_simulator import TradingSimulator, initialize_all_accounts

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/initialize-accounts")
async def initialize_trading_accounts(db: Session = Depends(get_db)):
    """
    모든 LLM 모델의 가상 거래 계좌를 초기화합니다.
    각 계좌는 100만원 KRW로 시작합니다.
    
    Returns:
        dict: 초기화 결과
            - success: 성공 여부
            - message: 결과 메시지
            - results: 모델별 초기화 결과
    
    Example:
        POST /api/trading/initialize-accounts
        
        Response:
        {
            "success": true,
            "message": "4/4개 계좌 초기화 완료",
            "results": {
                "google/gemma-3-27b-it": true,
                "openai/gpt-oss-120b": true,
                "Qwen/Qwen3-30B-A3B-Thinking-2507-FP8": true,
                "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B": true
            }
        }
    """
    try:
        results = initialize_all_accounts(db)
        
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        logger.info(f"✅ 계좌 초기화 완료: {success_count}/{total_count}개 성공")
        
        return {
            "success": True,
            "message": f"{success_count}/{total_count}개 계좌 초기화 완료",
            "results": results
        }
    except Exception as e:
        logger.error(f"❌ 계좌 초기화 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"계좌 초기화 중 오류 발생: {str(e)}"
        )


@router.get("/account/{account_id}")
async def get_trading_account_summary(
    account_id: str,
    db: Session = Depends(get_db)
):
    """
    특정 계좌의 요약 정보 조회
    
    Args:
        account_id: 계정 UUID (예: 00000000-0000-0000-0000-000000000002)
    
    Returns:
        dict: 계좌 요약 정보
            - account_id: 계정 UUID
            - total_krw: 총 자산 (KRW 환산)
            - holdings: 보유 자산 목록
            - profit_loss: 손익 (KRW)
            - profit_loss_rate: 수익률 (%)
    
    Example:
        GET /api/trading/account/00000000-0000-0000-0000-000000000002
        
        Response:
        {
            "account_id": "00000000-0000-0000-0000-000000000002",
            "total_krw": 1050000.0,
            "holdings": {
                "KRW": {
                    "balance": 950000.0,
                    "krw_value": 950000.0
                },
                "BTC": {
                    "balance": 0.001,
                    "price": 100000000.0,
                    "krw_value": 100000.0,
                    "avg_buy_price": 99000000.0
                }
            },
            "profit_loss": 50000.0,
            "profit_loss_rate": 5.0
        }
    """
    try:
        account_uuid = UUID(account_id)
        simulator = TradingSimulator(db)
        summary = simulator.get_account_summary(account_uuid)
        
        if not summary:
            raise HTTPException(
                status_code=404,
                detail="계좌를 찾을 수 없습니다"
            )
        
        return summary
        
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="잘못된 UUID 형식입니다"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 계좌 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"계좌 조회 중 오류 발생: {str(e)}"
        )


@router.get("/accounts")
async def get_all_trading_accounts(db: Session = Depends(get_db)):
    """
    모든 LLM 모델 계좌의 요약 정보 조회
    
    Returns:
        dict: 전체 계좌 정보
            - success: 성공 여부
            - count: 조회된 계좌 수
            - accounts: 계좌 목록 (각 계좌는 model_name 포함)
    
    Example:
        GET /api/trading/accounts
        
        Response:
        {
            "success": true,
            "count": 4,
            "accounts": [
                {
                    "model_name": "openai/gpt-oss-120b",
                    "account_id": "00000000-0000-0000-0000-000000000002",
                    "total_krw": 1050000.0,
                    "holdings": {...},
                    "profit_loss": 50000.0,
                    "profit_loss_rate": 5.0
                },
                ...
            ]
        }
    """
    try:
        simulator = TradingSimulator(db)
        all_summaries = []
        
        for model_name in LLMAccountConfig.MODEL_ACCOUNT_SUFFIX_MAP.keys():
            try:
                account_id_str = LLMAccountConfig.get_account_id_for_model(model_name)
                account_uuid = UUID(account_id_str)
                
                summary = simulator.get_account_summary(account_uuid)
                if summary:
                    summary["model_name"] = model_name
                    all_summaries.append(summary)
                    
            except Exception as e:
                logger.warning(f"⚠️ {model_name} 계좌 조회 실패: {e}")
                continue
        
        return {
            "success": True,
            "count": len(all_summaries),
            "accounts": all_summaries
        }
        
    except Exception as e:
        logger.error(f"❌ 전체 계좌 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"계좌 조회 중 오류 발생: {str(e)}"
        )


@router.get("/executions")
async def get_trading_executions(
    limit: int = 100,
    status: str = None,
    db: Session = Depends(get_db)
):
    """
    거래 실행 기록 조회
    
    Args:
        limit: 조회할 최대 레코드 수 (기본: 100)
        status: 필터링할 상태 (success, failed, skipped)
    
    Returns:
        dict: 거래 실행 기록 목록
    
    Example:
        GET /api/trading/executions?limit=50&status=failed
    """
    try:
        from app.db.database import LLMTradingExecution
        from sqlalchemy import desc
        
        query = db.query(LLMTradingExecution)
        
        # 상태 필터링
        if status:
            query = query.filter(LLMTradingExecution.execution_status == status)
        
        # 최신순 정렬 및 limit 적용
        executions = query.order_by(
            desc(LLMTradingExecution.executed_at)
        ).limit(limit).all()
        
        results = []
        for execution in executions:
            results.append({
                "id": execution.id,
                "signal_id": execution.signal_id,
                "account_id": str(execution.account_id) if execution.account_id else None,
                "coin": execution.coin,
                "signal_type": execution.signal_type,
                "execution_status": execution.execution_status,
                "failure_reason": execution.failure_reason,
                "intended_price": float(execution.intended_price) if execution.intended_price else None,
                "executed_price": float(execution.executed_price) if execution.executed_price else None,
                "price_slippage": float(execution.price_slippage) if execution.price_slippage else None,
                "intended_quantity": float(execution.intended_quantity) if execution.intended_quantity else None,
                "executed_quantity": float(execution.executed_quantity) if execution.executed_quantity else None,
                "balance_before": float(execution.balance_before) if execution.balance_before else None,
                "balance_after": float(execution.balance_after) if execution.balance_after else None,
                "executed_at": execution.executed_at.isoformat() if execution.executed_at else None,
                "time_delay": float(execution.time_delay) if execution.time_delay else None,
                "notes": execution.notes
            })
        
        return {
            "success": True,
            "count": len(results),
            "executions": results
        }
        
    except Exception as e:
        logger.error(f"❌ 실행 기록 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"실행 기록 조회 중 오류 발생: {str(e)}"
        )


@router.get("/stats")
async def get_trading_stats(db: Session = Depends(get_db)):
    """
    거래 통계 조회
    
    Returns:
        dict: 전체 거래 통계
            - total_executions: 총 실행 횟수
            - success_count: 성공 횟수
            - failed_count: 실패 횟수
            - skipped_count: 건너뜀 횟수
            - success_rate: 성공률 (%)
            - avg_slippage: 평균 슬리피지 (%)
            - avg_delay: 평균 지연 시간 (초)
    
    Example:
        GET /api/trading/stats
    """
    try:
        from app.db.database import LLMTradingExecution
        from sqlalchemy import func
        
        # 전체 통계
        total = db.query(func.count(LLMTradingExecution.id)).scalar()
        
        success_count = db.query(func.count(LLMTradingExecution.id)).filter(
            LLMTradingExecution.execution_status == "success"
        ).scalar()
        
        failed_count = db.query(func.count(LLMTradingExecution.id)).filter(
            LLMTradingExecution.execution_status == "failed"
        ).scalar()
        
        skipped_count = db.query(func.count(LLMTradingExecution.id)).filter(
            LLMTradingExecution.execution_status == "skipped"
        ).scalar()
        
        # 성공률
        success_rate = (success_count / total * 100) if total > 0 else 0
        
        # 평균 슬리피지 (성공한 거래만)
        avg_slippage = db.query(func.avg(LLMTradingExecution.price_slippage)).filter(
            LLMTradingExecution.execution_status == "success",
            LLMTradingExecution.price_slippage != None
        ).scalar()
        
        # 평균 지연 시간
        avg_delay = db.query(func.avg(LLMTradingExecution.time_delay)).filter(
            LLMTradingExecution.time_delay != None
        ).scalar()
        
        return {
            "success": True,
            "total_executions": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "success_rate": round(float(success_rate), 2),
            "avg_slippage": round(float(avg_slippage), 4) if avg_slippage else 0,
            "avg_delay": round(float(avg_delay), 3) if avg_delay else 0
        }
        
    except Exception as e:
        logger.error(f"❌ 통계 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"통계 조회 중 오류 발생: {str(e)}"
        )

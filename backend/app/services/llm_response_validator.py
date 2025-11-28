"""
LLM 응답 검증 모듈
LLM이 생성한 거래 신호의 유효성을 검증하고 재요청을 처리합니다.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Tuple, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.llm import TradeDecision
from app.db.database import (
    UpbitAccounts,
    UpbitTicker,
    LLMTradingExecution,
    LLMTradingSignal
)

logger = logging.getLogger(__name__)

# 허용되는 신호 타입
VALID_SIGNAL_TYPES = {"buy_to_enter", "sell_to_exit", "hold", "close_position", "buy", "sell", "exit"}

# 매수 신호
BUY_SIGNALS = {"buy", "buy_to_enter"}

# 매도 신호
SELL_SIGNALS = {"sell", "sell_to_exit", "close_position", "exit"}


def _save_validation_failure(
    db: Session,
    prompt_id: int,
    account_id: Optional[UUID],
    coin: str,
    signal_type: str,
    execution_status: str,
    failure_reason: str,
    intended_price: Optional[Decimal] = None,
    executed_price: Optional[Decimal] = None,
    intended_quantity: Optional[Decimal] = None,
    executed_quantity: Optional[Decimal] = None,
    balance_before: Optional[Decimal] = None,
    balance_after: Optional[Decimal] = None,
    confidence: Optional[Decimal] = None,
    justification: Optional[str] = None,
    thinking: Optional[str] = None,
    full_prompt: Optional[str] = None,
    full_response: Optional[str] = None,
    signal_created_at: Optional[datetime] = None
) -> None:
    """
    검증 실패 기록을 llm_trading_execution 테이블에 저장
    """
    try:
        execution = LLMTradingExecution(
            prompt_id=prompt_id,
            account_id=account_id,
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
            confidence=confidence,
            justification=justification,
            thinking=thinking,
            full_prompt=full_prompt,
            full_response=full_response,
            signal_created_at=signal_created_at
        )
        db.add(execution)
        db.commit()
        logger.info(f"✅ 검증 실패 기록 저장 완료 (prompt_id={prompt_id}, reason={failure_reason})")
    except Exception as e:
        logger.error(f"❌ 검증 실패 기록 저장 실패: {e}", exc_info=True)
        db.rollback()


def validate_trade_decision(
    decision: TradeDecision,
    account_id: Optional[UUID],
    db: Session,
    prompt_id: Optional[int] = None,
    signal_created_at: Optional[datetime] = None,
    confidence: Optional[Decimal] = None,
    justification: Optional[str] = None,
    thinking: Optional[str] = None,
    full_prompt: Optional[str] = None,
    full_response: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """
    LLM 거래 신호 검증
    
    검증 항목:
    1. 필수 필드 존재 여부 (signal, quantity, coin)
    2. signal 타입 유효성 검증
    3. 계좌 잔액 대비 quantity 검증
    """
    errors: List[str] = []
    
    # -----------------------------
    # 1. 필수 필드 검증
    # -----------------------------
    if not decision.coin or not decision.coin.strip():
        errors.append("coin 필드값 누락")
    
    if not decision.signal or not decision.signal.strip():
        errors.append("signal 필드값 누락")
    
    if decision.signal and decision.signal.lower().strip() != "hold":
        if decision.quantity is None:
            errors.append("quantity 필드값 누락")
        elif decision.quantity <= 0:
            errors.append(f"quantity가 0 이하입니다. (값: {decision.quantity})")
    
    # 정규화
    coin = decision.coin.upper() if decision.coin else ""
    signal_type = decision.signal.lower().strip() if decision.signal else ""
    
    # 필수 필드 검증 실패 시 DB 저장
    if errors:
        if prompt_id:
            _save_validation_failure(
                db=db,
                prompt_id=prompt_id,
                account_id=account_id,
                coin=coin,
                signal_type=signal_type,
                execution_status="failed",
                failure_reason=", ".join(errors),
                intended_price=None,
                executed_price=None,
                intended_quantity=None,
                executed_quantity=None,
                balance_before=None,
                balance_after=None,
                confidence=confidence,
                justification=justification,
                thinking=thinking,
                full_prompt=full_prompt,
                full_response=full_response,
                signal_created_at=signal_created_at
            )
    
    # -----------------------------
    # 2. signal 타입 유효성 검증
    # -----------------------------
    if signal_type and signal_type not in VALID_SIGNAL_TYPES:
        error_msg = (
            f"알 수 없는 signal_type: '{signal_type}'. "
            f"허용된 값: {sorted(VALID_SIGNAL_TYPES)}"
        )
        errors.append(error_msg)
        
        if prompt_id:
            _save_validation_failure(
                db=db,
                prompt_id=prompt_id,
                account_id=account_id,
                coin=coin,
                signal_type=signal_type,
                execution_status="failed",
                failure_reason=error_msg,
                intended_price=None,
                executed_price=None,
                intended_quantity=None,
                executed_quantity=None,
                balance_before=None,
                balance_after=None,
                confidence=confidence,
                justification=justification,
                thinking=thinking,
                full_prompt=full_prompt,
                full_response=full_response,
                signal_created_at=signal_created_at
            )
    
    # 신호 타입 플래그
    is_buy_signal = signal_type in BUY_SIGNALS
    is_sell_signal = signal_type in SELL_SIGNALS
    is_hold_signal = (signal_type == "hold")
    
    # -----------------------------
    # 3. 계좌 잔액 초과 검증
    # -----------------------------
    if account_id and decision.quantity and decision.quantity > 0 and not is_hold_signal:
        try:
            account_id_str = str(account_id)
            quantity = Decimal(str(decision.quantity))
            
            # 매수 신호
            if is_buy_signal:
                ticker = (
                    db.query(UpbitTicker)
                    .filter(UpbitTicker.market == f"KRW-{coin}")
                    .order_by(UpbitTicker.collected_at.desc())
                    .first()
                )
                
                if ticker and ticker.trade_price:
                    current_price = Decimal(str(ticker.trade_price))
                    
                    krw_account = (
                        db.query(UpbitAccounts)
                        .filter(
                            UpbitAccounts.account_id == account_id_str,
                            UpbitAccounts.currency == "KRW"
                        )
                        .order_by(UpbitAccounts.collected_at.desc())
                        .first()
                    )
                    
                    if krw_account and krw_account.balance is not None:
                        krw_balance = Decimal(str(krw_account.balance))
                        estimated_cost = quantity * current_price
                        
                        if estimated_cost > krw_balance:
                            error_msg = (
                                f"매수 quantity가 계좌 잔액을 초과합니다. "
                                f"필요: {estimated_cost:,.2f} KRW, "
                                f"보유: {krw_balance:,.2f} KRW"
                            )
                            errors.append(error_msg)
                            
                            if prompt_id:
                                _save_validation_failure(
                                    db=db,
                                    prompt_id=prompt_id,
                                    account_id=account_id,
                                    coin=coin,
                                    signal_type=signal_type,
                                    execution_status="failed",
                                    failure_reason=error_msg,
                                    intended_quantity=quantity,
                                    balance_before=krw_balance,
                                    balance_after=None,
                                    confidence=confidence,
                                    justification=justification,
                                    thinking=thinking,
                                    full_prompt=full_prompt,
                                    full_response=full_response,
                                    signal_created_at=signal_created_at
                                )
            
            # 매도 신호
            elif is_sell_signal:
                coin_account = (
                    db.query(UpbitAccounts)
                    .filter(
                        UpbitAccounts.account_id == account_id_str,
                        UpbitAccounts.currency == coin
                    )
                    .order_by(UpbitAccounts.collected_at.desc())
                    .first()
                )
                
                if coin_account and coin_account.balance is not None:
                    coin_balance = Decimal(str(coin_account.balance))
                    
                    if quantity > coin_balance:
                        error_msg = (
                            f"매도 수량이 보유량을 초과합니다. "
                            f"의도: {quantity}, 보유: {coin_balance} {coin}"
                        )
                        errors.append(error_msg)
                        
                        if prompt_id:
                            _save_validation_failure(
                                db=db,
                                prompt_id=prompt_id,
                                account_id=account_id,
                                coin=coin,
                                signal_type=signal_type,
                                execution_status="failed",
                                failure_reason=error_msg,
                                intended_quantity=quantity,
                                balance_before=coin_balance,
                                balance_after=None,
                                confidence=confidence,
                                justification=justification,
                                thinking=thinking,
                                full_prompt=full_prompt,
                                full_response=full_response,
                                signal_created_at=signal_created_at
                            )
        
        except Exception as e:
            logger.error(f"⚠️ 잔액 검증 중 예외 발생: {e}", exc_info=True)
    
    # 최종 검증 결과 반환
    is_valid = len(errors) == 0
    return is_valid, errors


def build_retry_prompt(
    original_prompt: str,
    rejection_reasons: List[str],
    original_decision: TradeDecision
) -> str:
    """
    재요청 프롬프트 생성
    
    Args:
        original_prompt: 원본 프롬프트
        rejection_reasons: 거부 사유 목록
        original_decision: 원본 거래 결정
    
    Returns:
        str: 재요청 프롬프트
    """
    logger.info("📝 재요청 프롬프트 생성 중...")
    
    rejection_text = "\n".join([f"- {reason}" for reason in rejection_reasons])
    
    retry_prompt = f"""
[재요청] 이전 응답이 다음 이유로 거부되었습니다:

{rejection_text}

**중요 규칙:**
1. signal 값은 반드시 다음 중 하나여야 합니다: buy_to_enter, sell_to_exit, hold, close_position
2. quantity는 필수이며 0보다 커야 합니다 (hold 신호 제외)
3. quantity는 계좌 잔액을 초과할 수 없습니다

이전 응답:
- signal: {original_decision.signal}
- coin: {original_decision.coin}
- quantity: {original_decision.quantity}
- confidence: {original_decision.confidence}

위의 오류를 수정하여 올바른 JSON 응답을 생성해주세요.

원본 프롬프트:
{original_prompt}
"""
    
    logger.info("✅ 재요청 프롬프트 생성 완료")
    return retry_prompt


def validate_execution_result(
    db: Session,
    prompt_id: int,
    account_id: Optional[UUID],
    coin: str,
    signal_type: str,
    actual_signal_type: str,  # 실제 실행된 신호
    intended_price: Optional[Decimal],
    executed_price: Optional[Decimal],
    intended_quantity: Optional[Decimal],
    executed_quantity: Optional[Decimal],
    balance_before: Optional[Decimal],
    balance_after: Optional[Decimal],
    signal_created_at: Optional[datetime],
    slippage_skipped: bool = False,
    confidence: Optional[Decimal] = None,
    justification: Optional[str] = None,
    thinking: Optional[str] = None,
    full_prompt: Optional[str] = None,
    full_response: Optional[str] = None,
) -> LLMTradingExecution:
    """
    거래 실행 결과 검증 및 llm_trading_execution 저장
    
    검증 항목:
    5. LLM signal vs 실제 거래 결과 차이 검증
       - 방향(매수/매도/hold) 불일치
       - 의도한 수량 vs 실제 수량 불일치
       - balance_after 계산값 불일치
    """
    errors: List[str] = []
    execution_status: Optional[str] = None
    
    # 신호 카테고리 판별 함수
    def _signal_category(sig: str) -> str:
        sig = sig.lower()
        if sig in BUY_SIGNALS:
            return "buy"
        if sig in SELL_SIGNALS:
            return "sell"
        if sig == "hold":
            return "hold"
        return "unknown"
    
    # -----------------------------
    # (1) 매수/매도/hold 방향 불일치
    # -----------------------------
    intended_dir = _signal_category(signal_type)
    actual_dir = _signal_category(actual_signal_type)
    
    if intended_dir != "unknown" and actual_dir != "unknown" and intended_dir != actual_dir:
        errors.append(
            f"LLM 신호 방향({intended_dir})과 실제 실행 방향({actual_dir})이 다릅니다."
        )
    
    # -----------------------------
    # (2) 수량 불일치
    # -----------------------------
    if intended_quantity is not None and executed_quantity is not None and executed_quantity >= 0:
        diff = abs(executed_quantity - intended_quantity)
        if diff > Decimal("0"):
            errors.append(
                f"의도한 수량({intended_quantity})과 실제 체결 수량({executed_quantity})이 다릅니다."
            )
    
    # -----------------------------
    # (3) balance_after 검증
    # -----------------------------
    if (
        balance_before is not None
        and balance_after is not None
        and executed_price is not None
        and executed_quantity is not None
        and not slippage_skipped
    ):
        theoretical_after: Optional[Decimal] = None
        
        if intended_dir == "buy":
            # 매수: KRW 잔액 = 기존 - 체결금액
            theoretical_after = balance_before - (executed_price * executed_quantity)
        elif intended_dir == "sell":
            # 매도: KRW 잔액 = 기존 + 체결금액
            theoretical_after = balance_before + (executed_price * executed_quantity)
        
        if theoretical_after is not None:
            diff = abs(theoretical_after - balance_after)
            if diff > Decimal("1"):  # 1원 이상 차이
                errors.append(
                    f"balance_after가 계산값과 다릅니다. "
                    f"expected={theoretical_after}, actual={balance_after}, diff={diff}"
                )
    
    # -----------------------------
    # 실행 상태 최종 결정
    # -----------------------------
    if execution_status is None:
        if errors:
            execution_status = "failed"
        else:
            if intended_dir == "hold":
                execution_status = "success"
            else:
                if executed_quantity and executed_quantity > 0:
                    execution_status = "success"
                else:
                    execution_status = "failed"
    
    failure_reason = "; ".join(errors) if errors else None
    
    # -----------------------------
    # DB INSERT
    # -----------------------------
    execution_row = LLMTradingExecution(
        prompt_id=prompt_id,
        account_id=account_id,
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
        confidence=confidence,
        justification=justification,
        thinking=thinking,
        full_prompt=full_prompt,
        full_response=full_response,
        signal_created_at=signal_created_at
    )
    
    db.add(execution_row)
    db.commit()
    db.refresh(execution_row)
    
    return execution_row

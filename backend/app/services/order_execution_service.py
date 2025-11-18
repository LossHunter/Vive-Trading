"""
[임시 테스트용] 주문 체결 서비스 모듈
LLM 거래 신호를 기반으로 가상의 주문을 체결하고 upbit_accounts를 업데이트합니다.

⚠️ 주의: 이 모듈은 임시 테스트용입니다.
나중에 실제 외부 시스템으로 교체할 때 다음 파일들을 제거하거나 비활성화할 수 있습니다:
- BE/services/order_execution_service.py (이 파일)
- BE/main.py의 POST /api/order/execute 엔드포인트
- BE/config.py의 OrderExecutionConfig 클래스
- BE/database.py의 LLMTradingSignal.account_id 필드 (필요시)

제거 방법:
1. config.py에서 OrderExecutionConfig.ENABLE_ORDER_EXECUTION = False 설정
2. 또는 위 파일들을 직접 삭제
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.database import UpbitAccounts, UpbitTicker, LLMTradingSignal
from app.core.config import UpbitAPIConfig, OrderExecutionConfig

logger = logging.getLogger(__name__)


def get_account_id_from_user_id(user_id: int) -> str:
    """
    userId를 account_id로 변환
    account_id 형식: 00000000-0000-0000-0000-000000000001 (마지막 숫자가 userId)
    
    Args:
        user_id: 사용자 ID (1, 2, 3, 4)
    
    Returns:
        str: account_id (UUID 형식)
    """
    return f"00000000-0000-0000-0000-{user_id:012d}"


def get_user_id_from_account_id(account_id: str) -> Optional[int]:
    """
    account_id를 userId로 변환
    account_id의 마지막 숫자를 추출하여 userId로 변환
    
    Args:
        account_id: 계정 식별자 (UUID 형식)
    
    Returns:
        Optional[int]: userId (1, 2, 3, 4) 또는 None
    """
    try:
        if not account_id:
            return None
        # UUID의 마지막 부분에서 숫자 추출
        last_part = str(account_id).split('-')[-1]
        user_id = int(last_part)
        if 1 <= user_id <= 4:
            return user_id
        return None
    except (ValueError, AttributeError):
        return None


def get_current_price(db: Session, coin: str) -> Optional[float]:
    """
    코인의 현재가 조회
    
    Args:
        db: 데이터베이스 세션
        coin: 코인 심볼 (예: BTC, ETH)
    
    Returns:
        Optional[float]: 현재가 또는 None
    """
    market = f"KRW-{coin}"
    if market not in UpbitAPIConfig.MAIN_MARKETS:
        logger.warning(f"⚠️ {market}은(는) 지원하지 않는 마켓입니다")
        return None
    
    ticker = db.query(UpbitTicker).filter(
        UpbitTicker.market == market
    ).order_by(desc(UpbitTicker.collected_at)).first()
    
    if ticker and ticker.trade_price:
        return float(ticker.trade_price)
    
    return None


def execute_order(db: Session, signal: LLMTradingSignal) -> bool:
    """
    주문 체결 실행
    LLM 거래 신호를 기반으로 가상의 주문을 체결하고 upbit_accounts를 업데이트합니다.
    
    Args:
        db: 데이터베이스 세션
        signal: LLM 거래 신호
    
    Returns:
        bool: 체결 성공 여부
    """
    try:
        account_id = signal.account_id
        coin = signal.coin.upper()
        signal_type = signal.signal.lower()
        
        # 현재가 조회
        current_price = get_current_price(db, coin)
        if not current_price:
            logger.error(f"❌ {coin} 현재가 조회 실패")
            return False
        
        # buy_to_enter: KRW에서 코인으로 변환
        if signal_type == "buy_to_enter":
            # 수량 계산
            quantity = None
            if signal.quantity and signal.quantity > 0:
                quantity = float(signal.quantity)
            elif signal.risk_usd and signal.risk_usd > 0:
                # risk_usd 기반으로 수량 계산 (KRW 기준)
                quantity = float(signal.risk_usd) / current_price
            else:
                logger.warning(f"⚠️ {account_id} {coin} {signal_type}: 수량 정보가 없습니다")
                return False
            
            if quantity <= 0:
                logger.warning(f"⚠️ {account_id} {coin} {signal_type}: 수량이 0 이하입니다")
                return False
            
            return _execute_buy_order(db, account_id, coin, quantity, current_price)
        
        # sell_to_exit: 코인에서 KRW로 변환 (일부 판매)
        elif signal_type == "sell_to_exit":
            # 수량 계산
            quantity = None
            if signal.quantity and signal.quantity > 0:
                quantity = float(signal.quantity)
            elif signal.risk_usd and signal.risk_usd > 0:
                # risk_usd 기반으로 수량 계산 (KRW 기준)
                quantity = float(signal.risk_usd) / current_price
            else:
                logger.warning(f"⚠️ {account_id} {coin} {signal_type}: 수량 정보가 없습니다")
                return False
            
            if quantity <= 0:
                logger.warning(f"⚠️ {account_id} {coin} {signal_type}: 수량이 0 이하입니다")
                return False
            
            return _execute_sell_order(db, account_id, coin, quantity, current_price)
        
        # close_position: 포지션 종료 (전부 판매)
        elif signal_type == "close_position":
            # 보유한 코인 잔액을 전부 조회
            coin_account = db.query(UpbitAccounts).filter(
                UpbitAccounts.account_id == account_id,
                UpbitAccounts.currency == f"KRW-{coin}"
            ).order_by(desc(UpbitAccounts.collected_at)).first()
            
            if not coin_account:
                logger.error(f"❌ {account_id} {coin} 계정을 찾을 수 없습니다")
                return False
            
            current_coin_balance = float(coin_account.balance) if coin_account.balance else 0.0
            
            if current_coin_balance <= 0:
                logger.warning(f"⚠️ {account_id} {coin} {signal_type}: 보유 코인이 없습니다 (잔액: {current_coin_balance})")
                return False
            
            # 보유한 코인을 전부 매도
            logger.info(f"ℹ️ {account_id} {coin} {signal_type}: 포지션 종료 신호, 보유 코인 전부 매도 ({current_coin_balance}개)")
            return _execute_sell_order(db, account_id, coin, current_coin_balance, current_price)
        
        # hold: 변경 없음
        elif signal_type == "hold":
            logger.info(f"ℹ️ {account_id} {coin} {signal_type}: 홀드 신호, 주문 체결 없음")
            return True
        
        else:
            logger.warning(f"⚠️ {account_id} {coin} {signal_type}: 알 수 없는 신호 타입")
            return False
    
    except Exception as e:
        logger.error(f"❌ 주문 체결 오류: {e}")
        return False


def _execute_buy_order(db: Session, account_id: str, coin: str, quantity: float, price: float) -> bool:
    """
    매수 주문 체결
    KRW 잔액에서 코인 수량만큼 차감하고, 코인 잔액을 증가시킵니다.
    
    Args:
        db: 데이터베이스 세션
        account_id: 계정 식별자
        coin: 코인 심볼
        quantity: 구매 수량
        price: 구매 가격
    
    Returns:
        bool: 체결 성공 여부
    """
    try:
        # 필요한 KRW 계산
        required_krw = quantity * price
        
        # KRW 잔액 조회
        krw_account = db.query(UpbitAccounts).filter(
            UpbitAccounts.account_id == account_id,
            UpbitAccounts.currency == "KRW"
        ).order_by(desc(UpbitAccounts.collected_at)).first()
        
        if not krw_account:
            logger.error(f"❌ {account_id} KRW 계정을 찾을 수 없습니다")
            return False
        
        current_krw = float(krw_account.balance) if krw_account.balance else 0.0
        
        if current_krw < required_krw:
            logger.warning(f"⚠️ {account_id} {coin} 매수: KRW 잔액 부족 (필요: {required_krw:,.0f}, 보유: {current_krw:,.0f})")
            return False
        
        # 코인 계정 조회 또는 생성
        coin_account = db.query(UpbitAccounts).filter(
            UpbitAccounts.account_id == account_id,
            UpbitAccounts.currency == f"KRW-{coin}"
        ).order_by(desc(UpbitAccounts.collected_at)).first()
        
        current_coin_balance = float(coin_account.balance) if coin_account and coin_account.balance else 0.0
        current_avg_price = float(coin_account.avg_buy_price) if coin_account and coin_account.avg_buy_price else 0.0
        
        # 평균 매수가 계산 (가중 평균)
        new_coin_balance = current_coin_balance + quantity
        if current_coin_balance > 0:
            # 기존 보유량이 있으면 가중 평균 계산
            total_cost = (current_coin_balance * current_avg_price) + (quantity * price)
            new_avg_price = total_cost / new_coin_balance
        else:
            # 기존 보유량이 없으면 현재 가격이 평균가
            new_avg_price = price
        
        # KRW 잔액 차감
        new_krw_balance = current_krw - required_krw
        
        # 현재 시각
        now = datetime.now(timezone.utc)
        
        # account_id를 UUID로 변환 (데이터베이스가 UUID 타입이므로)
        try:
            account_id_uuid = UUID(account_id) if isinstance(account_id, str) else account_id
        except (ValueError, AttributeError):
            account_id_uuid = account_id
        
        # KRW 계정 업데이트
        new_krw_account = UpbitAccounts(
            account_id=str(account_id_uuid),  # UUID를 문자열로 변환하여 저장
            currency="KRW",
            balance=Decimal(str(new_krw_balance)),
            locked=krw_account.locked,
            avg_buy_price=krw_account.avg_buy_price,
            avg_buy_price_modified=krw_account.avg_buy_price_modified,
            unit_currency=krw_account.unit_currency,
            collected_at=now
        )
        db.add(new_krw_account)
        
        # 코인 계정 업데이트 또는 생성
        new_coin_account = UpbitAccounts(
            account_id=account_id,
            currency=f"KRW-{coin}",
            balance=Decimal(str(new_coin_balance)),
            locked=coin_account.locked if coin_account else None,
            avg_buy_price=Decimal(str(new_avg_price)),
            avg_buy_price_modified=coin_account.avg_buy_price_modified if coin_account else False,
            unit_currency="KRW",
            collected_at=now
        )
        db.add(new_coin_account)
        
        db.commit()
        
        logger.info(f"✅ {account_id} {coin} 매수 체결 완료: {quantity}개 @ {price:,.0f}원 (총 {required_krw:,.0f}원)")
        return True
    
    except Exception as e:
        db.rollback()
        logger.error(f"❌ {account_id} {coin} 매수 체결 실패: {e}")
        return False


def _execute_sell_order(db: Session, account_id: str, coin: str, quantity: float, price: float) -> bool:
    """
    매도 주문 체결
    코인 잔액에서 수량만큼 차감하고, KRW 잔액을 증가시킵니다.
    
    Args:
        db: 데이터베이스 세션
        account_id: 계정 식별자
        coin: 코인 심볼
        quantity: 판매 수량
        price: 판매 가격
    
    Returns:
        bool: 체결 성공 여부
    """
    try:
        # 코인 계정 조회
        coin_account = db.query(UpbitAccounts).filter(
            UpbitAccounts.account_id == account_id,
            UpbitAccounts.currency == f"KRW-{coin}"
        ).order_by(desc(UpbitAccounts.collected_at)).first()
        
        if not coin_account:
            logger.error(f"❌ {account_id} {coin} 계정을 찾을 수 없습니다")
            return False
        
        current_coin_balance = float(coin_account.balance) if coin_account.balance else 0.0
        
        if current_coin_balance < quantity:
            logger.warning(f"⚠️ {account_id} {coin} 매도: 코인 잔액 부족 (필요: {quantity}, 보유: {current_coin_balance})")
            return False
        
        # 받을 KRW 계산
        received_krw = quantity * price
        
        # KRW 계정 조회
        krw_account = db.query(UpbitAccounts).filter(
            UpbitAccounts.account_id == account_id,
            UpbitAccounts.currency == "KRW"
        ).order_by(desc(UpbitAccounts.collected_at)).first()
        
        if not krw_account:
            logger.error(f"❌ {account_id} KRW 계정을 찾을 수 없습니다")
            return False
        
        current_krw = float(krw_account.balance) if krw_account.balance else 0.0
        
        # 코인 잔액 차감
        new_coin_balance = current_coin_balance - quantity
        
        # KRW 잔액 증가
        new_krw_balance = current_krw + received_krw
        
        # 평균 매수가는 유지 (매도 시에는 변경 없음)
        new_avg_price = coin_account.avg_buy_price
        
        # 현재 시각
        now = datetime.now(timezone.utc)
        
        # account_id를 UUID로 변환 (데이터베이스가 UUID 타입이므로)
        try:
            account_id_uuid = UUID(account_id) if isinstance(account_id, str) else account_id
        except (ValueError, AttributeError):
            account_id_uuid = account_id
        
        # KRW 계정 업데이트
        new_krw_account = UpbitAccounts(
            account_id=str(account_id_uuid),  # UUID를 문자열로 변환하여 저장
            currency="KRW",
            balance=Decimal(str(new_krw_balance)),
            locked=krw_account.locked,
            avg_buy_price=krw_account.avg_buy_price,
            avg_buy_price_modified=krw_account.avg_buy_price_modified,
            unit_currency=krw_account.unit_currency,
            collected_at=now
        )
        db.add(new_krw_account)
        
        # 코인 계정 업데이트
        if new_coin_balance > 0:
            # 코인 잔액이 남아있으면 업데이트
            new_coin_account = UpbitAccounts(
                account_id=account_id,
                currency=f"KRW-{coin}",
                balance=Decimal(str(new_coin_balance)),
                locked=coin_account.locked,
                avg_buy_price=new_avg_price,
                avg_buy_price_modified=coin_account.avg_buy_price_modified,
                unit_currency="KRW",
                collected_at=now
            )
            db.add(new_coin_account)
        else:
            # 코인 잔액이 0이면 삭제하지 않고 0으로 업데이트
            new_coin_account = UpbitAccounts(
                account_id=account_id,
                currency=f"KRW-{coin}",
                balance=Decimal("0"),
                locked=coin_account.locked,
                avg_buy_price=new_avg_price,
                avg_buy_price_modified=coin_account.avg_buy_price_modified,
                unit_currency="KRW",
                collected_at=now
            )
            db.add(new_coin_account)
        
        db.commit()
        
        logger.info(f"✅ {account_id} {coin} 매도 체결 완료: {quantity}개 @ {price:,.0f}원 (총 {received_krw:,.0f}원)")
        return True
    
    except Exception as e:
        db.rollback()
        logger.error(f"❌ {account_id} {coin} 매도 체결 실패: {e}")
        return False


def execute_signal_orders(db: Session, prompt_id: Optional[int] = None) -> dict:
    """
    저장된 LLM 거래 신호를 기반으로 주문을 체결합니다.
    
    Args:
        db: 데이터베이스 세션
        prompt_id: 프롬프트 ID (None이면 최신 signal만 체결)
    
    Returns:
        dict: 체결 결과 통계
    """
    try:
        # 체결할 signal 조회
        if prompt_id:
            signals = db.query(LLMTradingSignal).filter(
                LLMTradingSignal.prompt_id == prompt_id
            ).all()
        else:
            # 최신 signal만 체결 (같은 prompt_id의 signal들)
            latest_prompt = db.query(LLMTradingSignal).order_by(
                desc(LLMTradingSignal.created_at)
            ).first()
            
            if not latest_prompt:
                logger.warning("⚠️ 체결할 signal이 없습니다")
                return {"success": False, "message": "체결할 signal이 없습니다"}
            
            signals = db.query(LLMTradingSignal).filter(
                LLMTradingSignal.prompt_id == latest_prompt.prompt_id
            ).all()
        
        if not signals:
            logger.warning("⚠️ 체결할 signal이 없습니다")
            return {"success": False, "message": "체결할 signal이 없습니다"}
        
        # 체결 결과 통계
        results = {
            "success": True,
            "total": len(signals),
            "executed": 0,
            "failed": 0,
            "details": []
        }
        
        # 각 signal 체결
        for signal in signals:
            success = execute_order(db, signal)
            if success:
                results["executed"] += 1
            else:
                results["failed"] += 1
            
            results["details"].append({
                "signal_id": signal.id,
                "account_id": signal.account_id,
                "coin": signal.coin,
                "signal": signal.signal,
                "success": success
            })
        
        logger.info(f"✅ 주문 체결 완료: 총 {results['total']}개, 성공 {results['executed']}개, 실패 {results['failed']}개")
        
        return results
    
    except Exception as e:
        logger.error(f"❌ 주문 체결 오류: {e}")
        return {"success": False, "message": f"주문 체결 중 오류 발생: {str(e)}"}


"""
가상 거래 시뮬레이터 모듈
LLM 거래 신호를 기반으로 가상 계좌에서 거래를 시뮬레이션합니다.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import LLMAccountConfig, UpbitAPIConfig
from app.db.database import UpbitAccounts, UpbitTicker, LLMTradingSignal, LLMTradingExecution

logger = logging.getLogger(__name__)

# 초기 자본금 설정
INITIAL_CAPITAL_KRW = Decimal("10000000")  # 1000만원


class TradingSimulator:
    """가상 거래 시뮬레이터 클래스"""
    
    def __init__(self, db: Session):
        """
        초기화
        
        Args:
            db: SQLAlchemy 데이터베이스 세션
        """
        self.db = db
    
    def initialize_account(self, account_id: UUID) -> bool:
        """
        특정 모델의 계좌 초기화 (100만원 KRW로 시작)
        
        Args:
            account_id: 계정 UUID
        
        Returns:
            bool: 초기화 성공 여부
        """
        try:
            account_id_str = str(account_id)
            for market in UpbitAPIConfig.MAIN_MARKETS:
                currency = market.split("-")[1]
                existing = self.db.query(UpbitAccounts).filter(
                    UpbitAccounts.account_id == account_id_str,
                    UpbitAccounts.currency == currency
                ).first()
                if existing:
                    logger.info(f"✅ {currency} 계좌 {account_id_str}는 이미 존재합니다.")
                    return True
        
            # KRW 초기 자본금 생성
            krw_account = UpbitAccounts(
                account_id=account_id_str,
                currency="KRW",
                balance=INITIAL_CAPITAL_KRW,
                locked=Decimal("0"),
                avg_buy_price=Decimal("0"),
                avg_buy_price_modified=False,
                unit_currency="KRW",
                collected_at=datetime.now(timezone.utc)
            )
            
            self.db.add(krw_account)
            
            # 5개 마켓 초기 계정 생성 (BTC, ETH, DOGE, SOL, XRP)
            for market in UpbitAPIConfig.MAIN_MARKETS:
                currency = market.split("-")[1]
                coin_account = UpbitAccounts(
                    account_id=account_id_str,
                    currency=currency,
                    balance=Decimal("0"),
                    locked=Decimal("0"),
                    avg_buy_price=Decimal("0"),
                    avg_buy_price_modified=False,
                    unit_currency="KRW",
                    collected_at=datetime.now(timezone.utc)
                )
                self.db.add(coin_account)
            
            self.db.commit()
            
            logger.info(f"✅ 계좌 {account_id_str} 초기화 완료 (KRW: {INITIAL_CAPITAL_KRW:,})")
            return True
            
        except Exception as e:
            logger.error(f"❌ 계좌 초기화 실패 (account_id={account_id}): {e}")
            self.db.rollback()
            return False
    
    def initialize_all_model_accounts(self) -> Dict[str, bool]:
        """
        모든 LLM 모델의 계좌 초기화
        
        Returns:
            Dict[str, bool]: 모델명별 초기화 결과
        """
        results = {}
        
        for model_name in LLMAccountConfig.MODEL_ACCOUNT_SUFFIX_MAP.keys():
            try:
                account_id_str = LLMAccountConfig.get_account_id_for_model(model_name)
                account_id = UUID(account_id_str)
                
                success = self.initialize_account(account_id)
                results[model_name] = success
                
            except Exception as e:
                logger.error(f"❌ {model_name} 계좌 초기화 실패: {e}")
                results[model_name] = False
        
        success_count = sum(1 for v in results.values() if v)
        logger.info(f"📊 계좌 초기화 완료: {success_count}/{len(results)}개 성공")
        
        return results
    
    def get_current_price(self, coin: str) -> Optional[Decimal]:
        """
        코인의 현재 가격 조회
        
        Args:
            coin: 코인 심볼 (예: BTC, ETH)
        
        Returns:
            Decimal | None: 현재 가격
        """
        try:
            market = f"KRW-{coin.upper()}"
            
            # 최신 티커 데이터 조회
            ticker = self.db.query(UpbitTicker).filter(
                UpbitTicker.market == market
            ).order_by(desc(UpbitTicker.collected_at)).first()
            
            if ticker and ticker.trade_price:
                return Decimal(str(ticker.trade_price))
            
            logger.warning(f"⚠️ {market} 가격 정보 없음")
            return None
            
        except Exception as e:
            logger.error(f"❌ 가격 조회 실패 ({coin}): {e}")
            return None
    
    def get_account_balance(self, account_id: UUID, currency: str) -> Decimal:
        """
        계좌의 특정 화폐 잔액 조회
        
        Args:
            account_id: 계정 UUID
            currency: 화폐 코드 (예: BTC, KRW)
        
        Returns:
            Decimal: 잔액 (없으면 0)
        """
        try:
            account_id_str = str(account_id)
            
            account = self.db.query(UpbitAccounts).filter(
                UpbitAccounts.account_id == account_id_str,
                UpbitAccounts.currency == currency.upper()
            ).order_by(desc(UpbitAccounts.collected_at)).first()
            
            if account and account.balance:
                return Decimal(str(account.balance))
            
            return Decimal("0")
            
        except Exception as e:
            logger.error(f"❌ 잔액 조회 실패 (account_id={account_id}, currency={currency}): {e}")
            return Decimal("0")
    
    def execute_buy(
        self,
        account_id: UUID,
        coin: str,
        quantity: Decimal,
        price: Decimal
    ) -> bool:
        """
        매수 실행 (시뮬레이션)
        
        Args:
            account_id: 계정 UUID
            coin: 코인 심볼
            quantity: 매수 수량
            price: 매수 가격 (코인 1개당)
        
        Returns:
            bool: 매수 성공 여부
        """
        try:
            account_id_str = str(account_id)
            coin = coin.upper()
            
            # 필요한 KRW 계산
            total_cost = quantity * price
            logger.info(f"      - account_id: {account_id_str}")
            logger.info(f"      - coin: {coin}")
            logger.info(f"      - quantity: {quantity}")
            logger.info(f"      - price: {price:,.2f}")
            logger.info(f"      - total_cost: {total_cost:,.2f} KRW")
            
            # KRW 잔액 확인
            krw_balance = self.get_account_balance(account_id, "KRW")
            logger.info(f"      - 현재 KRW 잔액: {krw_balance:,.2f}")
            
            if krw_balance < total_cost:
                logger.warning(
                    f"⚠️ 매수 실패: 잔액 부족 (필요: {total_cost:,.0f} KRW, 보유: {krw_balance:,.0f} KRW)"
                )
                return False
            
            # KRW 차감
            logger.info("      - KRW 차감 중...")
            self._update_balance(account_id_str, "KRW", krw_balance - total_cost)
            logger.info(f"      ✅ KRW 잔액 업데이트: {krw_balance:,.2f} → {krw_balance - total_cost:,.2f}")
            
            # 코인 추가
            logger.info(f"      - {coin} 잔액 조회 중...")
            current_coin_balance = self.get_account_balance(account_id, coin)
            new_coin_balance = current_coin_balance + quantity
            logger.info(f"      - 현재 {coin} 잔액: {current_coin_balance}")
            logger.info(f"      - 새로운 {coin} 잔액: {new_coin_balance}")
            
            # 평균 매수가 계산
            if current_coin_balance > 0:
                current_avg_price = self._get_avg_buy_price(account_id_str, coin)
                total_value = (current_coin_balance * current_avg_price) + total_cost
                avg_buy_price = total_value / new_coin_balance
                logger.info(f"      - 평균 매수가 계산: {avg_buy_price:,.2f} KRW")
            else:
                avg_buy_price = price
                logger.info(f"      - 최초 매수, 평균가 = 현재가: {avg_buy_price:,.2f} KRW")
            
            logger.info(f"      - {coin} 잔액 업데이트 중...")
            self._update_balance(account_id_str, coin, new_coin_balance, avg_buy_price)
            logger.info(f"      ✅ {coin} 잔액 업데이트 완료")
            
            logger.info(f"    ✅ [execute_buy 성공]: {quantity:.8f} {coin} @ {price:,.2f} KRW")
            return True
            
        except Exception as e:
            logger.error(f"    ❌ [execute_buy 실패]: {e}")
            logger.error("    로백 실행 중...", exc_info=True)
            self.db.rollback()
            return False
            
    
    def execute_sell(
        self,
        account_id: UUID,
        coin: str,
        quantity: Decimal,
        price: Decimal
    ) -> bool:
        """
        매도 실행 (시뮬레이션)
        
        Args:
            account_id: 계정 UUID
            coin: 코인 심볼
            quantity: 매도 수량
            price: 매도 가격 (코인 1개당)
        
        Returns:
            bool: 매도 성공 여부
        """
        try:
            account_id_str = str(account_id)
            coin = coin.upper()
            
            # 코인 잔액 확인
            coin_balance = self.get_account_balance(account_id, coin)
            
            if coin_balance < quantity:
                logger.warning(
                    f"⚠️ 매도 실패: 코인 부족 (필요: {quantity:.8f} {coin}, 보유: {coin_balance:.8f} {coin})"
                )
                return False
            
            # 코인 차감
            new_coin_balance = coin_balance - quantity
            self._update_balance(account_id_str, coin, new_coin_balance)
            
            # KRW 추가
            total_revenue = quantity * price
            krw_balance = self.get_account_balance(account_id, "KRW")
            new_krw_balance = krw_balance + total_revenue
            
            self._update_balance(account_id_str, "KRW", new_krw_balance)
            
            logger.info(
                f"✅ 매도 성공: {quantity:.8f} {coin} @ {price:,.0f} KRW (총: {total_revenue:,.0f} KRW)"
            )
            return True
            
        except Exception as e:
            logger.error(f"❌ 매도 실행 실패: {e}")
            self.db.rollback()
            return False
    
    def execute_trade_signal(self, signal: LLMTradingSignal, intended_price: Optional[Decimal] = None) -> bool:
        """
        LLM 거래 신호 실행
        
        Args:
            signal: LLM 거래 신호 객체
        
        Returns:
            bool: 실행 성공 여부
        
        Note:
            - buy_to_enter: 매수 진입
            - sell_to_exit: 매도 청산
            - hold: 유지 (거래하지 않음)
            - profit_target: 목표가 (수익 실현)
            - stop_loss: 손절가 (손실 제한)
            - quantity: 거래 수량
        """

        execution_record = {
            "prompt_id": signal.id,
            "account_id": signal.account_id,
            "coin": signal.coin,
            "signal_type": signal.signal,
            "signal_created_at": signal.created_at,
            "intended_price": intended_price,
            #"profit_target": signal.profit_target,
            #"stop_loss": signal.stop_loss,
        }

        try:
            # 1. account_id 검증
            logger.info("[1단계] account_id 검증 중...")
            if not signal.account_id:
                logger.error(f"❌ account_id가 없음! (prompt_id={signal.id})")
                self._save_execution_record(
                    **execution_record,
                    execution_status="failed",
                    failure_reason="account_id가 없음"
                )
                return False
            logger.info(f"✅ account_id 확인: {signal.account_id}")
            
            # 2. 신호 타입 확인 (HOLD는 quantity 검증 전에 처리)
            logger.info("[2단계] 신호 타입 확인 중...")
            signal_type = signal.signal.lower()
            logger.info(f"  원본 신호: {signal.signal}")
            logger.info(f"  소문자 변환: {signal_type}")
            
            # HOLD 신호는 거래하지 않음 (quantity 검증 없이 바로 skipped 처리)
            if "hold" in signal_type:
                logger.info(f"📊 HOLD 신호 감지: {signal.coin}")
                logger.info("  → 거래를 실행하지 않습니다. (quantity 검증 생략)")
                self._save_execution_record(
                    **execution_record,
                    execution_status="skipped",
                    failure_reason="HOLD 신호"
                )
                return True
            
            # 3. 현재 가격 조회 (HOLD가 아닌 경우만)
            logger.info(f"[3단계] {signal.coin} 현재 가격 조회 중...")
            current_price = self.get_current_price(signal.coin)
            if not current_price:
                logger.error(f"❌ {signal.coin} 가격 조회 실패! upbit_ticker 테이블 확인 필요")
                self._save_execution_record(
                    **execution_record,
                    execution_status="failed",
                    failure_reason=f"{signal.coin} 가격 조회 실패 (upbit_ticker 테이블에 데이터 없음)"
                )
                return False
            logger.info(f"✅ {signal.coin} 현재가: {current_price:,.2f} KRW")

            execution_record["executed_price"] = current_price
            
            # 4. quantity 검증 (HOLD가 아닌 경우만 필수)
            logger.info("[4단계] quantity 검증 중...")
            logger.info(f"  signal.quantity 값: {signal.quantity}")
            logger.info(f"  signal.quantity 타입: {type(signal.quantity)}")
            
            if signal.quantity is None:
                logger.error("❌ quantity가 None입니다!")
                self._save_execution_record(
                    **execution_record,
                    execution_status="failed",
                    failure_reason="quantity가 None"
                )
                return False
            
            # Decimal 타입으로 변환하여 0과 비교
            quantity_decimal = Decimal(str(signal.quantity))
            logger.info(f"  Decimal 변환: {quantity_decimal}")
            
            if quantity_decimal <= Decimal("0"):
                logger.error(f"❌ quantity가 0 이하입니다! (값: {quantity_decimal})")
                self._save_execution_record(
                    **execution_record,
                    execution_status="failed",
                    failure_reason=f"quantity가 0 이하 (값: {quantity_decimal})"
                )
                return False
            
            logger.info(f"✅ quantity 유효: {quantity_decimal}")
            execution_record["intended_quantity"] = signal.quantity
            
            # 5. 신호 타입에 따라 처리 (BUY/SELL)
            logger.info("[5단계] 신호 타입 처리 중...")
            
            # BUY_TO_ENTER: 매수 진입
            if "buy_to_enter" == signal_type or "buy" in signal_type or "enter" in signal_type:
                logger.info("🟢 매수 신호 감지 - 매수 프로세스 시작")
                return self._execute_buy_signal(signal, current_price, execution_record)
            
            # SELL_TO_EXIT: 매도 청산
            elif "sell_to_exit" == signal_type or "sell" in signal_type or "exit" in signal_type:
                logger.info("🔴 매도 신호 감지 - 매도 프로세스 시작")
                return self._execute_sell_signal(signal, current_price, execution_record)
            
            else:
                logger.error(f"❌ 알 수 없는 신호 타입: {signal.signal}")
                self._save_execution_record(
                    **execution_record,
                    execution_status="failed",
                    failure_reason=f"알 수 없는 신호 타입: {signal.signal}"
                )
                return False
            
        except Exception as e:
            logger.error("="*80)
            logger.error(f"❌ [거래 시뮬레이션 예외 발생] prompt_id={signal.id}")
            logger.error(f"  예외 타입: {type(e).__name__}")
            logger.error(f"  예외 메시지: {str(e)}")
            logger.error("="*80, exc_info=True)
            self._save_execution_record(
                **execution_record,
                execution_status="failed",
                failure_reason=f"예외 발생: {str(e)}"
            )
            return False
    
    def _execute_buy_signal(self, signal: LLMTradingSignal, current_price: Decimal, execution_record: Dict) -> bool:
        """
        매수 신호 실행 (내부 메서드)
        
        Args:
            signal: LLM 거래 신호
            current_price: 현재 가격
            execution_record: 실행 기록 딕셔너리
        
        Returns:
            bool: 실행 성공 여부
        """
        logger.info("-" * 80)
        logger.info("👉 [매수 실행 시작]")
        try:
            # quantity는 필수 (이미 검증됨)
            quantity = Decimal(str(signal.quantity))
            logger.info(f"  매수 수량: {quantity}")
            
            # 거래 전 잔액
            logger.info("  KRW 잔액 조회 중...")
            krw_before = self.get_account_balance(signal.account_id, "KRW")
            logger.info(f"  KRW 잔액: {krw_before:,.2f} KRW")
            execution_record["balance_before"] = krw_before
            
            # 필요한 KRW 계산
            total_cost = quantity * current_price
            logger.info(f"  필요 금액: {total_cost:,.2f} KRW ({quantity} * {current_price:,.2f})")
            
            # 잔액 확인
            if krw_before < total_cost:
                logger.error(f"  ❌ 잔액 부족! 필요: {total_cost:,.2f} KRW, 보유: {krw_before:,.2f} KRW")
                self._save_execution_record(
                    **execution_record,
                    executed_quantity=Decimal("0"),
                    balance_after=krw_before,
                    execution_status="failed",
                    failure_reason=f"잔액 부족 (필요: {total_cost:,.2f} KRW, 보유: {krw_before:,.2f} KRW)"
                )
                return False
            
            logger.info("  ✅ 잔액 충분 - 매수 실행 중...")
            
            # 매수 실행
            success = self.execute_buy(signal.account_id, signal.coin, quantity, current_price)
            logger.info(f"  execute_buy() 결과: {success}")
            
            # 거래 후 잔액
            logger.info("  거래 후 KRW 잔액 조회 중...")
            krw_after = self.get_account_balance(signal.account_id, "KRW")
            logger.info(f"  거래 후 KRW 잔액: {krw_after:,.2f} KRW")
            
            if success:
                logger.info("  ✅ 매수 성공!")
                logger.info(f"    - 수량: {quantity} {signal.coin}")
                logger.info(f"    - 가격: {current_price:,.2f} KRW")
                logger.info(f"    - 총액: {total_cost:,.2f} KRW")
                
                # profit_target과 stop_loss 로깅
                if signal.profit_target:
                    logger.info(f"    - 📈 목표가: {float(signal.profit_target):,.2f} KRW")
                if signal.stop_loss:
                    logger.info(f"    - 📉 손절가: {float(signal.stop_loss):,.2f} KRW")
                
                # 성공 기록 저장
                logger.info("  llm_trading_execution 테이블에 성공 기록 저장 중...")
                self._save_execution_record(
                    **execution_record,
                    executed_quantity=quantity,
                    balance_after=krw_after,
                    execution_status="success",
                    #notes=f"매수 완료: {quantity:.8f} {signal.coin} @ {current_price:,.2f} KRW"
                )
                logger.info("-" * 80)
                return True
            else:
                logger.error("  ❌ execute_buy() 함수가 False 반환")
                # 실패 기록 저장
                self._save_execution_record(
                    **execution_record,
                    executed_quantity=Decimal("0"),
                    balance_after=krw_before,
                    execution_status="failed",
                    failure_reason="execute_buy() 실패"
                )
                logger.info("-" * 80)
                return False
            
        except Exception as e:
            logger.error(f"  ❌ 매수 실행 중 예외 발생: {e}")
            logger.error("-" * 80, exc_info=True)
            self._save_execution_record(
                **execution_record,
                execution_status="failed",
                failure_reason=f"예외: {str(e)}"
            )
            return False
    
    def _execute_sell_signal(self, signal: LLMTradingSignal, current_price: Decimal, execution_record: Dict) -> bool:
        """
        매도 신호 실행 (내부 메서드)
        
        Args:
            signal: LLM 거래 신호
            current_price: 현재 가격
            execution_record: 실행 기록 딕셔너리
        
        Returns:
            bool: 실행 성공 여부
        """
        try:
            # quantity는 필수 (이미 검증됨)
            quantity = Decimal(str(signal.quantity))
            
            # 거래 전 잔액
            coin_before = self.get_account_balance(signal.account_id, signal.coin)
            execution_record["balance_before"] = coin_before
            
            # 보유량 확인
            if quantity > coin_before:
                # 보유량보다 많이 매도하려고 하면 보유량만큼만 매도
                logger.warning(f"⚠️ 매도 수량 조정: {quantity:.8f} → {coin_before:.8f} {signal.coin}")
                quantity = coin_before
                execution_record["intended_quantity"] = quantity
            
            if coin_before <= 0 or quantity <= 0:
                self._save_execution_record(
                    **execution_record,
                    executed_quantity=Decimal("0"),
                    balance_after=coin_before,
                    execution_status="failed",
                    failure_reason=f"매도할 {signal.coin} 없음 (보유량: {coin_before:.8f})"
                )
                logger.warning(f"⚠️ 매도할 {signal.coin} 없음 (보유량: {coin_before:.8f})")
                return False
            
            # 매도 이유 판단 (profit_target 또는 stop_loss 달성?)
            avg_buy_price = self._get_avg_buy_price(str(signal.account_id), signal.coin)
            notes_parts = []
            
            # profit_target 또는 stop_loss 달성 여부 확인
            if avg_buy_price > 0:
                profit_loss = (current_price - avg_buy_price) * quantity
                profit_loss_percent = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
                if signal.profit_target and current_price >= float(signal.profit_target):
                    notes_parts.append(f"목표가 달성 ({current_price:,.2f} >= {float(signal.profit_target):,.2f})")
                elif signal.stop_loss and current_price <= float(signal.stop_loss):
                    notes_parts.append(f"손절가 도달 ({current_price:,.2f} <= {float(signal.stop_loss):,.2f})")
                else:
                    notes_parts.append(f"수익률: {profit_loss_percent:.2f}%")
            
            logger.info("-" * 80)
            logger.info("👉 [매도 실행 시작]")
            logger.info(f"  매도 수량: {quantity}")
            logger.info(f"  현재가: {current_price:,.2f} KRW")
            logger.info(f"  거래 전 {signal.coin} 잔액: {coin_before:.8f}")
            
            # 매도 실행
            success = self.execute_sell(signal.account_id, signal.coin, quantity, current_price)
            logger.info(f"  execute_sell() 결과: {success}")
            
            # 거래 후 잔액
            coin_after = self.get_account_balance(signal.account_id, signal.coin)
            logger.info(f"  거래 후 {signal.coin} 잔액: {coin_after:.8f}")
            
            if success:
                logger.info("  ✅ 매도 성공!")
                logger.info(f"    - 수량: {quantity:.8f} {signal.coin}")
                logger.info(f"    - 가격: {current_price:,.2f} KRW")
                total_revenue = quantity * current_price
                logger.info(f"    - 총액: {total_revenue:,.2f} KRW")
                if notes_parts:
                    logger.info(f"    - 사유: {', '.join(notes_parts)}")
                
               # 성공 기록 저장
                logger.info("  llm_trading_execution 테이블에 성공 기록 저장 중...")
                self._save_execution_record(
                    **execution_record,
                    executed_quantity=quantity,
                    balance_after=coin_after,
                    execution_status="success",
                    #notes=f"매도 완료: {quantity:.8f} {signal.coin} @ {current_price:,.2f} KRW. {', '.join(notes_parts) if notes_parts else ''}"
                )
                logger.info("-" * 80)
                return True
            else:
                logger.error("  ❌ execute_sell() 함수가 False 반환")
                # 실패 기록 저장
                self._save_execution_record(
                    **execution_record,
                    executed_quantity=Decimal("0"),
                    balance_after=coin_before,
                    execution_status="failed",
                    failure_reason="execute_sell() 실패"
                )
                logger.info("-" * 80)
                return False
            
        except Exception as e:
            logger.error(f"❌ 매도 신호 실행 실패: {e}")
            logger.error("-" * 80, exc_info=True)
            self._save_execution_record(
                **execution_record,
                execution_status="failed",
                failure_reason=f"예외: {str(e)}"
            )
            return False
    
    def _update_balance(
        self,
        account_id_str: str,
        currency: str,
        new_balance: Decimal,
        avg_buy_price: Optional[Decimal] = None
    ):
        """
        잔액 업데이트 (내부 메서드)
        
        Args:
            account_id_str: 계정 ID 문자열
            currency: 화폐 코드
            new_balance: 새로운 잔액
            avg_buy_price: 평균 매수가 (선택사항)
        """
        
        # 기존 계좌 조회
        account = self.db.query(UpbitAccounts).filter(
            UpbitAccounts.account_id == account_id_str,
            UpbitAccounts.currency == currency
        ).order_by(desc(UpbitAccounts.collected_at)).first()
        
        if account:
            # 기존 레코드 업데이트 (새 레코드 생성 방식)
            new_account = UpbitAccounts(
                account_id=account_id_str,
                currency=currency,
                balance=new_balance,
                locked=Decimal("0"),
                avg_buy_price=avg_buy_price if avg_buy_price else account.avg_buy_price,
                avg_buy_price_modified=False,
                unit_currency="KRW",
                collected_at=datetime.now(timezone.utc)
            )
        else:
            # 새 레코드 생성
            new_account = UpbitAccounts(
                account_id=account_id_str,
                currency=currency,
                balance=new_balance,
                locked=Decimal("0"),
                avg_buy_price=avg_buy_price if avg_buy_price else Decimal("0"),
                avg_buy_price_modified=False,
                unit_currency="KRW",
                collected_at=datetime.now(timezone.utc)
            )
        
        self.db.add(new_account)
        
        try:
            self.db.commit()
            logger.info(f"        ✅ [_update_balance 완료] upbit_accounts에 저장됨")
        except Exception as e:
            logger.error(f"        ❌ [_update_balance 실패] DB 커밋 오류: {e}")
            logger.error(f"           Exception 타입: {type(e).__name__}", exc_info=True)
            raise
    
    def _get_avg_buy_price(self, account_id_str: str, currency: str) -> Decimal:
        """
        평균 매수가 조회 (내부 메서드)
        
        Args:
            account_id_str: 계정 ID 문자열
            currency: 화폐 코드
        
        Returns:
            Decimal: 평균 매수가
        """
        account = self.db.query(UpbitAccounts).filter(
            UpbitAccounts.account_id == account_id_str,
            UpbitAccounts.currency == currency
        ).order_by(desc(UpbitAccounts.collected_at)).first()
        
        if account and account.avg_buy_price:
            return Decimal(str(account.avg_buy_price))
        
        return Decimal("0")
    
    def _save_execution_record(
        self,
        prompt_id: int,
        account_id: Optional[UUID],
        coin: str,
        signal_type: str,
        execution_status: str,
        signal_created_at: Optional[datetime] = None,
        intended_price: Optional[Decimal] = None,
        executed_price: Optional[Decimal] = None,
        intended_quantity: Optional[Decimal] = None,
        executed_quantity: Optional[Decimal] = None,
        balance_before: Optional[Decimal] = None,
        balance_after: Optional[Decimal] = None,
        failure_reason: Optional[str] = None,
    ):
        """
        거래 실행 기록 저장 (내부 메서드)
        
        Args:
            prompt_id: 프롬프트 ID
            account_id: 계정 UUID
            coin: 코인 심볼
            signal_type: 신호 타입
            execution_status: 실행 상태 (success, failed, skipped)
            ... (나머지 파라미터들)
        """
        try:
            # 시간 지연 계산
            time_delay = None
            if signal_created_at:
                now = datetime.now(timezone.utc)
                time_delay = (now - signal_created_at).total_seconds()
            
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
                signal_created_at=signal_created_at,
              #  time_delay=Decimal(str(time_delay)) if time_delay else None,
            )
            
            self.db.add(execution)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"❌ 실행 기록 저장 실패: {e}")
            self.db.rollback()
    
    def get_account_summary(self, account_id: UUID) -> Dict[str, any]:
        """
        계좌 요약 정보 조회
        
        Args:
            account_id: 계정 UUID
        
        Returns:
            Dict: 계좌 요약 정보
        """
        try:
            account_id_str = str(account_id)
            
            # 모든 보유 자산 조회
            accounts = self.db.query(UpbitAccounts).filter(
                UpbitAccounts.account_id == account_id_str
            ).order_by(desc(UpbitAccounts.collected_at)).all()
            
            # 최신 데이터만 추출 (currency별)
            latest_accounts = {}
            for acc in accounts:
                if acc.currency not in latest_accounts:
                    latest_accounts[acc.currency] = acc
            
            # 총 자산 계산 (KRW 기준)
            total_krw = Decimal("0")
            holdings = {}
            
            for currency, acc in latest_accounts.items():
                balance = Decimal(str(acc.balance)) if acc.balance else Decimal("0")
                
                if currency == "KRW":
                    total_krw += balance
                    holdings[currency] = {
                        "balance": float(balance),
                        "krw_value": float(balance)
                    }
                else:
                    # 코인 가격 조회
                    price = self.get_current_price(currency)
                    if price:
                        krw_value = balance * price
                        total_krw += krw_value
                        holdings[currency] = {
                            "balance": float(balance),
                            "price": float(price),
                            "krw_value": float(krw_value),
                            "avg_buy_price": float(acc.avg_buy_price) if acc.avg_buy_price else 0
                        }
            
            return {
                "account_id": account_id_str,
                "total_krw": float(total_krw),
                "holdings": holdings,
                "profit_loss": float(total_krw - INITIAL_CAPITAL_KRW),
                "profit_loss_rate": float((total_krw - INITIAL_CAPITAL_KRW) / INITIAL_CAPITAL_KRW * 100)
            }
            
        except Exception as e:
            logger.error(f"❌ 계좌 요약 조회 실패 (account_id={account_id}): {e}")
            return {}


# 전역 헬퍼 함수
def initialize_all_accounts(db: Session) -> Dict[str, bool]:
    """
    모든 LLM 모델 계좌 초기화 (편의 함수)
    
    Args:
        db: 데이터베이스 세션
    
    Returns:
        Dict[str, bool]: 모델명별 초기화 결과
    """
    simulator = TradingSimulator(db)
    return simulator.initialize_all_model_accounts()
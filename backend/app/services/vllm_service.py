import asyncio
import json
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from uuid import UUID
from app.core.config import settings, LLMAccountConfig
from sqlalchemy import desc, cast, Text

from app.db.database import LLMTradingSignal, SessionLocal, UpbitAccounts
from app.schemas.llm import TradeDecision
from app.services.llm_prompt_generator import LLMPromptGenerator
from app.services.vllm_model_registry import get_preferred_model_name
from app.services.trading_simulator import TradingSimulator

logger = logging.getLogger(__name__)


# OpenAI(vLLM) 클라이언트 초기화
client = OpenAI(
    base_url=settings.VLLM_BASE_URL,
    api_key=settings.VLLM_API_KEY,
)


# DEFAULT_MODEL_NAME = "openai/gpt-oss-120b" # config.py에 기재
TRADE_DECISION_LOOP_INTERVAL = 60  # 초 단위

MODEL_ACCOUNT_SUFFIX_MAP = {
    "google/gemma-3-27b-it": "1",
    "openai/gpt-oss-120b": "2",
    "Qwen/Qwen3-30B-A3B-Thinking-2507-FP8": "3",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B": "4",
}

def _build_system_message() -> str:
    """
    시스템 프롬프트용 JSON 문자열 생성
    """
    payload = {"expected_response_schema": TradeDecision.model_json_schema()}
    return json.dumps(payload, ensure_ascii=False)


def _build_user_payload(prompt_data, extra_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    LLM에게 전달할 사용자 프롬프트 생성
    """
    payload: Dict[str, Any] = {
        "prompt_text": prompt_data.prompt_text, # 기본 프롬프트
        "market_data": prompt_data.market_data_json, # 코인별 시세/OHLC 데이터
        "account_data": prompt_data.account_data_json, # 현재 계좌상황
        "indicator_config": prompt_data.indicator_config_json, # 지표계산 값
        "metadata": {
            "prompt_id": prompt_data.id,
            "generated_at": prompt_data.generated_at.isoformat() if prompt_data.generated_at else None,
            "trading_minutes": prompt_data.trading_minutes,
        },
    }

    if extra_context:
        payload["extra_context"] = extra_context

    return payload


def _to_decimal(value: Any) -> Decimal:
    """
    PostgreSQL Numeric 컬럼에 적합하도록 Decimal로 변환: float을 바로 넣으면 오차 발생
    """
    return Decimal(str(value)) if value is not None else Decimal("0")


def _resolve_account_id(
    db: Session,
    model_name: str,
    decision: TradeDecision
) -> Optional[UUID]:
    """
    모델명을 account_id로 변환
    
    Args:
        db: 데이터베이스 세션 (확장 가능성을 위해 유지)
        model_name: 사용된 LLM 모델명
        decision: 트레이딩 결정 데이터 (확장 가능성을 위해 유지)
    
    Returns:
        UUID | None: 변환된 account_id, 실패 시 None
    """
    try:
        account_id_str = LLMAccountConfig.get_account_id_for_model(model_name)
        return UUID(account_id_str)
    except ValueError as e:
        logger.warning(f"⚠️ 모델 '{model_name}'의 account_id 변환 실패: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ account_id 변환 중 예외 발생: {e}")
        return None



def _save_trading_signal(db: Session, prompt_id: int, decision: TradeDecision, account_id: Optional[UUID] = None) -> LLMTradingSignal:
    """
    LLM 응답을 llm_trading_signal 테이블에 저장
    
    Args:
        db: 데이터베이스 세션
        prompt_id: 프롬프트 ID
        decision: 트레이딩 결정 데이터
        account_id: 계정 ID (LLM 모델별 매핑)
    
    Returns:
        LLMTradingSignal: 저장된 거래 신호 객체
    """
    signal = LLMTradingSignal(
        prompt_id=prompt_id,
        account_id=account_id,
        coin=decision.coin.upper(),
        signal=decision.signal,
        stop_loss=_to_decimal(decision.stop_loss),
        profit_target=_to_decimal(decision.profit_target),
        quantity=_to_decimal(decision.quantity),
        leverage=_to_decimal(decision.leverage),
        risk_usd=_to_decimal(decision.risk_usd),
        confidence=_to_decimal(decision.confidence),
        invalidation_condition=decision.invalidation_condition,
        justification=decision.justification,
    )

    db.add(signal) # INSERT 예약
    db.commit() # 실제 DB에 저장
    db.refresh(signal) # DB에서 최신 값(자동증가 id 포함) 다시 가져오기
    return signal


async def get_trade_decision(
    model_name: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> TradeDecision:
    """
    vLLM 서버에 트레이딩 결정 요청 -> 결과를 DB에 저장하는 함수

    Args:
        model_name: 사용할 모델 이름 (미지정 시 기본값 사용)
        extra_context: 추가로 전달할 컨텍스트 또는 사용자 입력

    Returns:
        TradeDecision: 검증된 트레이딩 결정 데이터
    """
    model = get_preferred_model_name(model_name)
    db = SessionLocal()
    try:
        generator = LLMPromptGenerator(db)
        prompt_data = generator.generate_and_save() # generate_and_save() 호출
        if not prompt_data:
            raise ValueError("프롬프트 데이터를 생성하지 못했습니다.")

        db.refresh(prompt_data)

        system_content = _build_system_message() # 응답형태 지정
        user_payload = _build_user_payload(prompt_data, extra_context)
        user_content = json.dumps(user_payload, ensure_ascii=False)

        completion = client.chat.completions.create(
            model=model, # 전달받은 모델 이름 사용
            messages=[
                {
                    "role": "system",
                    "content": system_content,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        raw_content = completion.choices[0].message.content or ""
        json_part = raw_content
        if "</thinking>" in raw_content:
            json_part = raw_content.split("</thinking>")[-1].strip() # llm이 생성한 <thinking>...</thinking> 부분 제거하고 남은 JSON 부분만 추출

        decision_data = json.loads(json_part)
        validated_decision = TradeDecision(**decision_data)

        account_id = _resolve_account_id(db, model, validated_decision)

        # DB에 저장 (account_id 포함)
        saved_signal = _save_trading_signal(db, prompt_data.id, validated_decision, account_id)

        logger.info(
            "✅ LLM 거래 신호 저장 완료 (prompt_id=%s, coin=%s, model=%s, account_id=%s)",
            prompt_data.id,
            validated_decision.coin,
            model,
            account_id,
        )

       # 거래 시뮬레이션 실행
        if account_id:
            try:
                simulator = TradingSimulator(db)
                
                # 계좌가 초기화되어 있는지 확인 (없으면 초기화)
                simulator.initialize_account(account_id)
                
                # LLM이 판단한 시점의 가격 조회 (intended_price)
                intended_price = simulator.get_current_price(validated_decision.coin)
                
                # 거래 실행 (슬리피지 체크 포함)
                trade_success = simulator.execute_trade_signal(saved_signal, intended_price)
                
                if trade_success:
                    logger.info(f"✅ 거래 실행 완료 (signal_id={saved_signal.id}, coin={validated_decision.coin})")
                else:
                    logger.warning(f"⚠️ 거래 실행 실패 (signal_id={saved_signal.id})")
                    
            except Exception as e:
                logger.error(f"❌ 거래 실행 중 오류: {e}")
                # 거래 실행 실패해도 신호는 저장되었으므로 계속 진행
                
        return validated_decision
    
    
    except json.JSONDecodeError as exc:
        logger.error("❌ LLM JSON 파싱 실패: %s", exc)
        logger.debug("LLM raw output: %s", raw_content)
        db.rollback()
        raise ValueError("LLM이 유효한 JSON을 반환하지 않았습니다.") from exc
    except Exception as exc:
        logger.error("❌ vLLM 호출 중 오류 발생: %s", exc)
        db.rollback()
        raise
    finally:
        db.close()


async def run_trade_decision_loop(
    model_name: Optional[str] = None,
    interval_seconds: int = TRADE_DECISION_LOOP_INTERVAL,
) -> None:
    """
    지정된 간격(60초)으로 LLM 트레이딩 결정을 주기적으로 실행
    """
    logger.info("🚀 LLM 거래 신호 루프 시작 (interval=%s초)", interval_seconds)
    while True:
        try:
            resolved_model = get_preferred_model_name(model_name)
            await get_trade_decision(model_name=resolved_model, extra_context=None)
        except Exception as exc:
            logger.error("⚠️ LLM 거래 신호 생성 실패: %s", exc)
        await asyncio.sleep(interval_seconds)
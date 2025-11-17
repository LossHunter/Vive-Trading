import asyncio
import json
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import LLMTradingSignal, SessionLocal
from app.schemas.llm import TradeDecision
from app.services.llm_prompt_generator import LLMPromptGenerator

logger = logging.getLogger(__name__)


# OpenAI(vLLM) 클라이언트 초기화
client = OpenAI(
    base_url=settings.VLLM_BASE_URL,
    api_key=settings.VLLM_API_KEY,
)


DEFAULT_MODEL_NAME = "openai/gpt-oss-120b" # get_trade_decision() 콜을 외부에서 모델 이름 없이 부를 경우 대비한 기본값
TRADE_DECISION_LOOP_INTERVAL = 60  # 초 단위


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


def _save_trading_signal(db: Session, prompt_id: int, decision: TradeDecision) -> LLMTradingSignal:
    """
    LLM 응답을 llm_trading_signal 테이블에 저장
    """
    signal = LLMTradingSignal(
        prompt_id=prompt_id,
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
    model = model_name or DEFAULT_MODEL_NAME
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

        _save_trading_signal(db, prompt_data.id, validated_decision) # DB에 저장
        logger.info("✅ LLM 거래 신호 저장 완료 (prompt_id=%s, coin=%s)", prompt_data.id, validated_decision.coin)

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
            await get_trade_decision(model_name=model_name, extra_context=None)
        except Exception as exc:
            logger.error("⚠️ LLM 거래 신호 생성 실패: %s", exc)
        await asyncio.sleep(interval_seconds)

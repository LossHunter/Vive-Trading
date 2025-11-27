import asyncio
import json
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from uuid import UUID
from app.core.config import settings, LLMAccountConfig
from sqlalchemy import desc
from datetime import datetime

from app.db.database import LLMTradingSignal, SessionLocal, UpbitAccounts, UpbitTicker
from app.schemas.llm import TradeDecision
from app.services.llm_prompt_generator import LLMPromptGenerator
from app.services.vllm_model_registry import get_preferred_model_name
from app.services.trading_simulator import TradingSimulator
from app.services.llm_response_validator import validate_trade_decision, build_retry_prompt
from app.core.prompts import STRATEGY_PROMPTS, TradingStrategy

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

def _build_system_message(strategy_prompt: str = "") -> str:
    """
    시스템 프롬프트용 메시지 생성
    LLM이 반환해야 할 JSON 스키마를 명시합니다.
    """
    schema = TradeDecision.model_json_schema()
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
    
    return f"""
You are an expert AI trading analyst. Your goal is to analyze the market data provided and decide on a single, actionable trade.

{schema_str}

You MUST follow this exact process:

1.  **Think (Chain-of-Thought):**
    First, think step-by-step about the provided data.
    Your thought process must be private and MUST NOT appear outside the JSON response.
    Instead, convert your internal reasoning into:
    - "thinking": a detailed, long, analytical explanation of your reasoning
    - "justification": a brief, user-facing summary of the rationale

    Your analysis MUST cover:
    - Current Position Analysis: Review any existing positions, PnL, and invalidation conditions.
    - Market Analysis: Analyze the provided data for BTC and other major coins (ETH, SOL, etc.).
    - Strategic Assessment: Synthesize all data to find the best trading opportunity.
    - Actionable Decision: Formulate a specific, justified trade with risk parameters.

2.  **Act (JSON Output):**
    You MUST output ONLY a single JSON object with the trade decision.
    Do NOT output any text outside the JSON.
    
    The JSON structure MUST look like this:

    {{
        "stop_loss": <float>,
        "signal": "<buy_to_enter | sell_to_enter | hold | close_position | buy | sell | exit>",
        "leverage": <int>,
        "risk_usd": <float>,
        "profit_target": <float>,
        "quantity": <float>,
        "invalidation_condition": "<string>",
        "justification": "<string - a brief summary of your reasoning>",
        "thinking": "<string - a long, detailed explanation of your internal reasoning>",
        "confidence": <float between 0.0 and 1.0>,
        "coin": "<string, e.g., BTC, ETH>"
    }}

The JSON object MUST follow these rules:
- It MUST include:
    - "coin": string (e.g. "BTC")
    - "signal": string (buy_to_enter, sell_to_enter, hold, close_position, buy, sell, exit)
- It SHOULD also include:
    - "thinking": string
    - "justification": string
- The output MUST be valid JSON.
- No text, markdown, or commentary is allowed outside the JSON object.

{strategy_prompt}"""


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


def _to_decimal(value: Any) -> Optional[Decimal]:
    """
    PostgreSQL Numeric 컬럼에 적합하도록 Decimal로 변환: float을 바로 넣으면 오차 발생
    None이면 None을 반환 (Optional 필드 지원)
    """
    if value is None:
        return None
    return Decimal(str(value))


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


def _save_trading_signal(
    db: Session, 
    prompt_id: int, 
    decision: TradeDecision, 
    account_id: Optional[UUID] = None,
    thinking: Optional[str] = None, # thinking 파라미터 추가
    full_prompt: Optional[str] = None, # full_prompt 파라미터 추가 (ORPO 학습용)
    full_response: Optional[str] = None # full_response 파라미터 추가 (ORPO 학습용)
) -> LLMTradingSignal:    
    """
    LLM 응답을 llm_trading_signal 테이블에 저장
    
    Args:
        db: 데이터베이스 세션
        prompt_id: 프롬프트 ID
        decision: 트레이딩 결정 데이터
        account_id: 계정 ID (LLM 모델별 매핑)
        thinking: LLM의 사고 과정 (CoT, <thinking>...</thinking>)
        full_prompt: LLM에게 전송된 전체 프롬프트 (System + User, ORPO 학습용)
        full_response: LLM이 반환한 전체 응답 (Raw Content, ORPO 학습용)
    
    Returns:
        LLMTradingSignal: 저장된 거래 신호 객체
    """
    # 현재가 조회
    current_price = None
    coin_upper = decision.coin.upper()
    market = f"KRW-{coin_upper}"
    
    try:
        ticker = db.query(UpbitTicker).filter(
            UpbitTicker.market == market
        ).order_by(desc(UpbitTicker.collected_at)).first()
        
        if ticker and ticker.trade_price:
            current_price = _to_decimal(ticker.trade_price)
            logger.debug(f"✅ {market} 현재가 조회 성공: {current_price}")
        else:
            logger.warning(f"⚠️ {market} 현재가 조회 실패: 티커 데이터 없음")
    except Exception as e:
        logger.error(f"❌ {market} 현재가 조회 중 오류 발생: {e}")
    
    signal = LLMTradingSignal(
        prompt_id=prompt_id,
        account_id=account_id,
        coin=coin_upper,
        signal=decision.signal,
        current_price=current_price,  # 추가
        stop_loss=_to_decimal(decision.stop_loss),
        profit_target=_to_decimal(decision.profit_target),
        quantity=_to_decimal(decision.quantity),
        leverage=_to_decimal(decision.leverage),
        risk_usd=_to_decimal(decision.risk_usd),
        confidence=_to_decimal(decision.confidence),
        invalidation_condition=decision.invalidation_condition,
        justification=decision.justification,
        thinking=thinking, # 추가
        full_prompt=full_prompt, # 추가 (ORPO 학습용)
        full_response=full_response, # 추가 (ORPO 학습용)
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
    raw_content = ""  # 예외 처리에서 참조할 수 있도록 초기화
    try:
        generator = LLMPromptGenerator(db)
        prompt_data = generator.generate_and_save() # generate_and_save() 호출
        if not prompt_data:
            raise ValueError("프롬프트 데이터를 생성하지 못했습니다.")

        db.refresh(prompt_data)

        # 전략 조회
        strategy_key = LLMAccountConfig.get_strategy_for_model(model)
        strategy_prompt = STRATEGY_PROMPTS.get(strategy_key, STRATEGY_PROMPTS[TradingStrategy.NEUTRAL])

        system_content = _build_system_message(strategy_prompt) # 응답형태 지정 + 전략 주입
        user_payload = _build_user_payload(prompt_data, extra_context)
        
        # 사용자 메시지를 텍스트 형식으로 변환 (JSON이 아닌 읽기 쉬운 형식) - 영어로 변경
        user_content = f"""Here is the current market situation and account information:

## Prompt Text
{prompt_data.prompt_text}

## Extra Context
{json.dumps(extra_context, ensure_ascii=False, indent=2) if extra_context else "None"}

Based on the information above, please make a trading decision. You must respond in JSON format, and the "coin" and "signal" fields are mandatory."""

        # ORPO 학습용 전체 프롬프트 구성 (System + User)
        full_prompt_for_training = f"""=== SYSTEM PROMPT ===
{system_content}

=== USER PROMPT ===
{user_content}
"""

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

        # completion 타입 확인 및 처리 (문자열 반환 오류 처리)
        try:
            if isinstance(completion, str):
                logger.warning(f"⚠️ vLLM API가 문자열을 직접 반환했습니다. 문자열을 raw_content로 사용합니다.")
                raw_content = completion
            elif hasattr(completion, 'choices') and completion.choices:
                raw_content = completion.choices[0].message.content or ""
            else:
                logger.error(f"❌ completion 형식이 예상과 다릅니다.")
                logger.error(f"   타입: {type(completion)}")
                logger.error(f"   내용 (처음 200자): {str(completion)[:200]}")
                raise ValueError("LLM 응답 형식이 올바르지 않습니다.")
        except AttributeError as e:
            logger.error(f"❌ completion에서 content 추출 실패: {e}")
            logger.error(f"   completion 타입: {type(completion)}")
            logger.error(f"   completion 내용 (처음 500자): {str(completion)[:500]}")
            raise ValueError(f"LLM 응답에서 content를 추출할 수 없습니다: {e}") from e

        # 빈 응답 체크
        if not raw_content or not raw_content.strip():
            logger.error(f"❌ vLLM API가 빈 응답을 반환했습니다.")
            raise ValueError("LLM이 빈 응답을 반환했습니다.")

        full_response = raw_content  # 전체 응답 저장 (ORPO 학습용)

        thinking_part = None

        # 1) <thinking> 태그에서 추출 시도
        if "<thinking>" in raw_content:
            thinking_start = raw_content.find("<thinking>")
            thinking_end = raw_content.find("</thinking>") + len("</thinking>")
            thinking_part = raw_content[thinking_start:thinking_end]

        json_part = raw_content.split("</thinking>")[-1].strip() if "</thinking>" in raw_content else raw_content

        # ========== 1단계: JSON 파싱 ==========
        try:
            decision_data = json.loads(json_part)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON 파싱 실패: {e}")
            logger.error(f"   JSON 파싱 시도한 내용 (처음 500자): {json_part[:500]}")
            logger.error(f"   전체 Raw content (처음 1000자): {raw_content[:1000]}")
            
            # JSON이 아닌 경우, JSON 부분만 추출 시도
            if "{" in json_part and "}" in json_part:
                json_start = json_part.find("{")
                json_end = json_part.rfind("}") + 1
                if json_start < json_end:
                    try:
                        json_part_extracted = json_part[json_start:json_end]
                        decision_data = json.loads(json_part_extracted)
                        logger.info(f"✅ JSON 추출 후 파싱 성공")
                    except json.JSONDecodeError:
                        logger.error(f"❌ JSON 추출 후에도 파싱 실패")
                        raise ValueError(f"LLM이 유효한 JSON을 반환하지 않았습니다: {e}") from e
                else:
                    raise ValueError(f"LLM이 유효한 JSON을 반환하지 않았습니다: {e}") from e
            else:
                raise ValueError(f"LLM이 유효한 JSON을 반환하지 않았습니다: {e}") from e

        # ========== 2단계: 배열/딕셔너리 형태 확인 및 리스트로 통일 ==========
        # 배열 형태인 경우 모든 요소 처리, 딕셔너리인 경우 리스트로 변환하여 통일된 처리
        decision_list = []
        if isinstance(decision_data, list):
            if len(decision_data) == 0:
                logger.error("❌ LLM 응답이 빈 배열입니다.")
                raise ValueError("LLM 응답이 빈 배열입니다.")
            logger.info(f"📋 LLM 응답이 배열 형태입니다. 총 {len(decision_data)}개의 거래 결정을 처리합니다.")
            decision_list = decision_data
        elif isinstance(decision_data, dict):
            # 딕셔너리인 경우 리스트로 변환하여 통일된 처리
            logger.info(f"📋 LLM 응답이 딕셔너리 형태입니다. 1개의 거래 결정을 처리합니다.")
            decision_list = [decision_data]
        else:
            logger.error(f"❌ LLM 응답이 딕셔너리 또는 배열이 아닙니다. 타입: {type(decision_data)}")
            logger.error(f"응답 내용: {json.dumps(decision_data, ensure_ascii=False, indent=2)[:500]}")
            raise ValueError(f"LLM 응답이 딕셔너리 또는 배열이 아닙니다. 타입: {type(decision_data)}")

        account_id = None
        final_decision = None
        saved_signals = []

        # ========== 3단계: 배열의 각 요소를 처리하고 저장 ==========
        for idx, item_data in enumerate(decision_list):
            logger.info(f"📝 [{idx+1}/{len(decision_list)}] 거래 결정 처리 중...")

            # expected_response_schema 제거 (있을 경우)
            if "expected_response_schema" in item_data:
                item_data.pop("expected_response_schema")

            # thinking 추출 (각 요소별로)
            item_thinking = None
            # 1) <thinking> 태그에서 추출 시도 (공통 thinking_part 사용)
            if thinking_part:
                item_thinking = thinking_part
            # 2) JSON 내부의 thinking 필드도 확인 (태그가 없을 경우)
            elif "thinking" in item_data:
                item_thinking = item_data.get("thinking")

            # 필수 필드 확인
            if "coin" not in item_data or "signal" not in item_data:
                logger.error(f"❌ [{idx+1}] 필수 필드 누락: coin={item_data.get('coin')}, signal={item_data.get('signal')}. 건너뜁니다.")
                continue

            # Pydantic 검증
            try:
                validated_decision = TradeDecision(**item_data)
            except Exception as e:
                logger.error(f"❌ [{idx+1}] Pydantic 검증 실패: {e}. 건너뜁니다.")
                continue

            # account_id는 첫 번째 유효한 결정에서만 조회
            if account_id is None:
                account_id = _resolve_account_id(db, model, validated_decision)

            # 거래 결정 검증
            is_valid, validation_errors = validate_trade_decision(
                validated_decision,
                account_id,
                db,
                prompt_id=prompt_data.id,
                signal_created_at=datetime.utcnow()
            )

            if is_valid:
                logger.info(f"✅ [{idx+1}] 검증 통과! llm_trading_signal에 저장합니다.")
                saved_signal = _save_trading_signal(
                    db=db,
                    prompt_id=prompt_data.id,
                    decision=validated_decision,
                    account_id=account_id,
                    thinking=item_thinking,  # <thinking> 태그 또는 JSON 필드에서 추출
                    full_prompt=full_prompt_for_training,  # ORPO 학습용 전체 프롬프트 전달
                    full_response=full_response  # ORPO 학습용 전체 응답 전달
                )
                saved_signals.append(saved_signal)
                final_decision = validated_decision  # 마지막으로 검증 통과한 결정을 최종 결정으로

                logger.info(
                    f"✅ [{idx+1}] LLM 거래 신호 저장 완료 (signal_id={saved_signal.id}, coin={validated_decision.coin}, account_id={account_id})"
                )
            else:
                logger.warning(f"⚠️ [{idx+1}] 검증 실패: {validation_errors}")
                logger.info(f"📝 [{idx+1}] 검증 실패 기록은 llm_trading_execution에만 저장됩니다.")

        # ========== 4단계: 저장 결과 확인 ==========
        # 저장된 신호가 없으면 재요청 시도 (첫 번째 요소 기준으로 재요청)
        if not saved_signals:
            if len(decision_list) > 0:
                logger.warning(f"⚠️ 모든 거래 결정이 검증에 실패했습니다. 첫 번째 요소 기준으로 재요청을 시도합니다.")

                # 재요청은 첫 번째 요소 기준으로 진행 (단일 결정 재요청)
                first_item = decision_list[0]

                # 첫 번째 요소로 TradeDecision 생성 시도
                try:
                    first_decision = TradeDecision(**first_item)
                except Exception as e:
                    logger.error(f"❌ 첫 번째 요소로 TradeDecision 생성 실패: {e}")
                    raise ValueError("모든 거래 결정이 검증에 실패했고, 재요청도 불가능합니다.") from e

                # 재요청 프롬프트 생성
                retry_prompt_text = build_retry_prompt(
                    original_prompt=user_content,
                    rejection_reasons=["모든 거래 결정이 검증에 실패했습니다."],
                    original_decision=first_decision
                )

                # ========== 5단계: LLM에 재요청 ==========
                try:
                    logger.info("🔄 LLM 재요청 중...")

                    retry_completion = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_content},
                            {"role": "user", "content": retry_prompt_text},
                        ],
                        temperature=0.0,
                        response_format={"type": "json_object"},
                    )

                    # 재요청 응답 파싱
                    retry_raw_content = None
                    try:
                        if isinstance(retry_completion, str):
                            retry_raw_content = retry_completion
                        elif hasattr(retry_completion, 'choices') and retry_completion.choices:
                            retry_raw_content = retry_completion.choices[0].message.content or ""
                        else:
                            logger.error(f"❌ 재요청 completion 형식이 예상과 다릅니다.")
                            raise ValueError("재요청 응답 형식이 올바르지 않습니다.")
                    except AttributeError as e:
                        logger.error(f"❌ 재요청 completion에서 content 추출 실패: {e}")
                        raise ValueError(f"재요청 응답에서 content를 추출할 수 없습니다: {e}") from e

                    if not retry_raw_content or not retry_raw_content.strip():
                        logger.error(f"❌ 재요청 응답이 비어있습니다.")
                        raise ValueError("재요청 응답이 비어있습니다.")

                    # 재요청 thinking 추출
                    retry_thinking = None
                    if "<thinking>" in retry_raw_content:
                        thinking_start = retry_raw_content.find("<thinking>")
                        thinking_end = retry_raw_content.find("</thinking>") + len("</thinking>")
                        retry_thinking = retry_raw_content[thinking_start:thinking_end]

                    retry_json_part = retry_raw_content.split("</thinking>")[-1].strip() if "</thinking>" in retry_raw_content else retry_raw_content

                    # 재요청 JSON 파싱
                    try:
                        retry_decision_data = json.loads(retry_json_part)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ 재요청 JSON 파싱 실패: {e}")
                        logger.error(f"Retry raw content: {retry_raw_content[:500]}")

                        # JSON 추출 시도
                        if "{" in retry_json_part and "}" in retry_json_part:
                            json_start = retry_json_part.find("{")
                            json_end = retry_json_part.rfind("}") + 1
                            if json_start < json_end:
                                try:
                                    retry_json_part_extracted = retry_json_part[json_start:json_end]
                                    retry_decision_data = json.loads(retry_json_part_extracted)
                                    logger.info(f"✅ 재요청 JSON 추출 후 파싱 성공")
                                except json.JSONDecodeError:
                                    logger.error(f"❌ 재요청 JSON 추출 후에도 파싱 실패")
                                    raise ValueError(f"재요청 JSON 파싱 실패: {e}") from e
                            else:
                                raise ValueError(f"재요청 JSON 파싱 실패: {e}") from e
                        else:
                            raise ValueError(f"재요청 JSON 파싱 실패: {e}") from e

                    # ========== 6단계: 재요청 응답 배열/딕셔너리 형태 확인 및 리스트로 통일 ==========
                    retry_decision_list = []
                    if isinstance(retry_decision_data, list):
                        if len(retry_decision_data) == 0:
                            logger.error("❌ 재요청 LLM 응답이 빈 배열입니다.")
                            raise ValueError("재요청 LLM 응답이 빈 배열입니다.")
                        logger.info(f"📋 재요청 LLM 응답이 배열 형태입니다. 총 {len(retry_decision_data)}개의 거래 결정을 처리합니다.")
                        retry_decision_list = retry_decision_data
                    elif isinstance(retry_decision_data, dict):
                        logger.info(f"📋 재요청 LLM 응답이 딕셔너리 형태입니다. 1개의 거래 결정을 처리합니다.")
                        retry_decision_list = [retry_decision_data]
                    else:
                        logger.error(f"❌ 재요청 LLM 응답이 딕셔너리 또는 배열이 아닙니다. 타입: {type(retry_decision_data)}")
                        logger.error(f"응답 내용: {json.dumps(retry_decision_data, ensure_ascii=False, indent=2)[:500]}")
                        raise ValueError(f"재요청 LLM 응답이 딕셔너리 또는 배열이 아닙니다.")

                    # ========== 7단계: 재요청 배열의 각 요소를 처리하고 저장 ==========
                    retry_saved_signals = []
                    retry_final_decision = None

                    for retry_idx, retry_item_data in enumerate(retry_decision_list):
                        logger.info(f"📝 [재요청 {retry_idx+1}/{len(retry_decision_list)}] 거래 결정 처리 중...")

                        # expected_response_schema 제거
                        if "expected_response_schema" in retry_item_data:
                            retry_item_data.pop("expected_response_schema")

                        # 재요청에서 thinking 필드 확인
                        retry_item_thinking = None
                        if retry_thinking:
                            retry_item_thinking = retry_thinking
                        elif "thinking" in retry_item_data:
                            retry_item_thinking = retry_item_data.get("thinking")

                        # 필수 필드 확인
                        if "coin" not in retry_item_data or "signal" not in retry_item_data:
                            logger.error(f"❌ [재요청 {retry_idx+1}] 필수 필드 누락: coin={retry_item_data.get('coin')}, signal={retry_item_data.get('signal')}. 건너뜁니다.")
                            continue

                        # Pydantic 검증
                        try:
                            retry_decision = TradeDecision(**retry_item_data)
                        except Exception as e:
                            logger.error(f"❌ [재요청 {retry_idx+1}] Pydantic 검증 실패: {e}. 건너뜁니다.")
                            continue

                        # 재요청 결과 검증
                        retry_is_valid, retry_validation_errors = validate_trade_decision(
                            retry_decision,
                            account_id,
                            db,
                            prompt_id=prompt_data.id,
                            signal_created_at=datetime.utcnow()
                        )

                        if retry_is_valid:
                            logger.info(f"✅ [재요청 {retry_idx+1}] 검증 통과! llm_trading_signal에 저장합니다.")
                            saved_signal = _save_trading_signal(
                                db=db,
                                prompt_id=prompt_data.id,
                                decision=retry_decision,
                                account_id=account_id,
                                thinking=retry_item_thinking,
                                full_prompt=full_prompt_for_training,  # ORPO 학습용 전체 프롬프트 전달
                                full_response=retry_raw_content  # 재요청 응답으로 업데이트
                            )
                            retry_saved_signals.append(saved_signal)
                            retry_final_decision = retry_decision

                            logger.info(
                                f"✅ [재요청 {retry_idx+1}] LLM 거래 신호 저장 완료 (signal_id={saved_signal.id}, coin={retry_decision.coin}, account_id={account_id})"
                            )
                        else:
                            logger.warning(f"⚠️ [재요청 {retry_idx+1}] 검증 실패: {retry_validation_errors}. 건너뜁니다.")

                    # ========== 8단계: 재요청 저장 결과 확인 ==========
                    if not retry_saved_signals:
                        logger.error(f"❌ 재요청도 모든 거래 결정이 검증에 실패했습니다.")
                        raise ValueError("재요청도 모든 거래 결정이 검증에 실패했습니다.")

                    logger.info(f"✅ 재요청으로 총 {len(retry_saved_signals)}개의 거래 신호가 저장되었습니다.")
                    saved_signals = retry_saved_signals
                    final_decision = retry_final_decision

                except Exception as retry_error:
                    logger.error(f"❌ 재요청 실패: {retry_error}", exc_info=True)
                    raise ValueError("재요청 실패") from retry_error
            else:
                # decision_list가 비어있는 경우
                logger.error("❌ 처리할 거래 결정이 없습니다.")
                raise ValueError("처리할 거래 결정이 없습니다.")

        # ========== 9단계: 최종 결과 확인 ==========
        if not saved_signals or not final_decision:
            logger.error("❌ 저장된 거래 신호가 없습니다.")
            raise ValueError("저장된 거래 신호가 없습니다.")

        logger.info(f"✅ 총 {len(saved_signals)}개의 거래 신호가 저장되었습니다.")

        # 거래 시뮬레이션 실행 (검증 통과 & signal 저장된 경우에만)
        if account_id and saved_signals:
            try:
                simulator = TradingSimulator(db)
                
                # 계좌가 초기화되어 있는지 확인 (없으면 초기화)
                simulator.initialize_account(account_id)
                
                # 모든 저장된 신호에 대해 거래 실행
                for idx, signal in enumerate(saved_signals, 1):
                    try:
                        # HOLD 신호는 건너뜀
                        if "hold" in signal.signal.lower():
                            logger.info(f"📊 [{idx}/{len(saved_signals)}] HOLD 신호: {signal.coin} - 거래하지 않음")
                            continue
                        
                        logger.info(f"🎯 [{idx}/{len(saved_signals)}] 거래 시뮬레이션 시작 (signal_id={signal.id}, coin={signal.coin})")
                        
                        # 각 신호의 코인에 맞는 가격 조회
                        intended_price = simulator.get_current_price(signal.coin)
                        
                        # 거래 실행 (슬리피지 체크 포함)
                        trade_success = simulator.execute_trade_signal(signal, intended_price)
                        
                        if trade_success:
                            logger.info(f"✅ [{idx}/{len(saved_signals)}] 거래 실행 완료 (signal_id={signal.id}, coin={signal.coin})")
                        else:
                            logger.warning(f"⚠️ [{idx}/{len(saved_signals)}] 거래 실행 실패 (signal_id={signal.id})")
                            
                    except Exception as e:
                        logger.error(f"❌ [{idx}/{len(saved_signals)}] 거래 실행 중 오류: {e}", exc_info=True)
                        # 하나의 거래 실패해도 다른 거래는 계속 진행
                        continue
                        
            except Exception as e:
                logger.error(f"❌ 거래 시뮬레이션 초기화 중 오류: {e}", exc_info=True)
                # 거래 실행 실패해도 신호는 저장되었으므로 계속 진행
        else:
            if not saved_signals:
                logger.warning(
                    f"⚠️ 검증 실패로 거래 시뮬레이션을 실행하지 않습니다. "
                    f"(prompt_id={prompt_data.id})"
                )
                
        return final_decision
    
    
    except json.JSONDecodeError as exc:
        logger.error("❌ LLM JSON 파싱 실패: %s", exc)
        logger.debug("LLM raw output: %s", raw_content)
        db.rollback()
        raise ValueError("LLM이 유효한 JSON을 반환하지 않았습니다.") from exc
    except Exception as exc:
        logger.error("❌ vLLM 호출 중 오류 발생: %s", exc)
        if raw_content:
            logger.debug("LLM raw output: %s", raw_content)
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
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional, List, Literal

ModelName = str

# LLM의 응답 JSON 구조를 검증하기 위한 Pydantic 모델
class TradeDecision(BaseModel):
    coin: str
    signal: Literal["buy_to_enter", "sell_to_exit", "hold", "close_position", "buy", "sell", "exit"]
    quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    profit_target: Optional[float] = None
    leverage: Optional[int] = None
    risk_usd: Optional[float] = None
    invalidation_condition: Optional[str] = None
    justification: Optional[str] = None
    thinking: Optional[str] = None # thinking 추가
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    account_id: Optional[str] = None

# RAG 기능이 포함된 API 요청 본문 스키마
class TradeDecisionRequest(BaseModel):
    user_data_prompt: Optional[str] = None
    model_name: Optional[ModelName] = None
    market_data: Optional[Dict[str, Any]] = None  # RAG를 위한 구조화된 시장 데이터


    @field_validator("model_name", mode="after")
    def validate_model_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None

        from app.services.vllm_model_registry import get_available_models

        available = get_available_models()
        if available and normalized not in available:
            raise ValueError(
                f"요청한 모델 '{normalized}'을(를) 사용할 수 없습니다. 사용 가능: {', '.join(available)}"
            )
        return normalized
    

# 컨텍스트 요약 스키마
class ContextSummary(BaseModel):
    success_cases: int
    failure_cases: int
    expert_analysis: int
    contrarian_views: int

# 최종 API 응답 스키마
class TradeDecisionResponse(BaseModel):
    status: str
    rag_context_used: bool
    trade_decision: TradeDecision
    context_summary: Optional[ContextSummary] = None

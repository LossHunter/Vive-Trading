from pydantic import BaseModel, Field
from typing import Literal, Dict, Any, Optional, List

# 사용 가능한 모델 이름들을 Literal 타입으로 정의
ModelName = Literal[
    "google/gemma-3-27b-it",
    "openai/gpt-oss-120b",
    "Qwen/Qwen3-30B-A3B-Thinking-2507-FP8",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B"
]

# LLM의 응답 JSON 구조를 검증하기 위한 Pydantic 모델
class TradeDecision(BaseModel):
    stop_loss: float
    signal: Literal["buy_to_enter", "sell_to_enter", "hold", "close_position"]
    leverage: int
    risk_usd: float
    profit_target: float
    quantity: float
    invalidation_condition: str
    justification: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    coin: str

# RAG 기능이 포함된 API 요청 본문 스키마
class TradeDecisionRequest(BaseModel):
    user_data_prompt: Optional[str] = None
    model_name: ModelName = "openai/gpt-oss-120b"
    market_data: Optional[Dict[str, Any]] = None  # RAG를 위한 구조화된 시장 데이터

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

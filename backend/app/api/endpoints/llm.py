import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.schemas.llm import TradeDecisionRequest, TradeDecisionResponse, ContextSummary
from app.services import vllm_service
from app.rag.query_engine import RAGQueryEngine

router = APIRouter()
logger = logging.getLogger(__name__)

# RAGQueryEngine 인스턴스는 애플리케이션 시작 시 한 번만 생성
rag_engine = RAGQueryEngine()

@router.post("/trade-decision", response_model=TradeDecisionResponse)
async def get_trade_decision(request: TradeDecisionRequest):
    """
    RAG 컨텍스트를 사용하여 LLM으로부터 트레이딩 결정을 생성합니다.
    `market_data`가 제공되면 RAG 검색을 수행하고, 그렇지 않으면 직접 LLM을 호출합니다.
    """
    rag_context = ""
    context_summary = None
    
    try:
        # 1. RAG 컨텍스트 검색 (market_data가 제공된 경우)
        if request.market_data:
            try:
                context_results = rag_engine.get_balanced_context(
                    market_data=request.market_data,
                    n_results_per_category=2
                )
                rag_context = rag_engine.format_context_for_llm(context_results)
                
                context_summary = ContextSummary(
                    success_cases=len(context_results["success_cases"]),
                    failure_cases=len(context_results["failure_cases"]),
                    expert_analysis=len(context_results["expert_analysis"]),
                    contrarian_views=len(context_results["contrarian_views"])
                )
                logger.info(f"RAG context retrieved: {context_summary.model_dump()}")
                
            except Exception as e:
                logger.warning(f"RAG context retrieval failed: {str(e)}")
                rag_context = "RAG context retrieval failed, proceeding without context."

        # # 2. LLM에 전달할 최종 프롬프트 생성
        # # RAG 컨텍스트가 있을 경우, 이를 user_data_prompt 앞에 추가하여 LLM이 먼저 참고하도록 함
        # final_prompt = f"""
        # ### 참고 자료 (과거 사례 및 분석)
        # {rag_context if rag_context else '사용 가능한 참고 자료 없음.'}
        
        # ---
        
        # ### 현재 시장 데이터 및 분석 요청
        # {request.user_data_prompt}
        
        # ---
        
        # ### 지시사항
        # 위 '참고 자료'와 '현재 시장 데이터'를 모두 종합적으로 고려하여, 전문가 트레이딩 분석가로서 단 하나의 실행 가능한 트레이딩 결정을 내려주세요.
        # 반드시 아래 JSON 형식에 맞춰 응답해야 합니다.
        # """

        # LLM 서비스 호출용 추가 컨텍스트 구성
        extra_context: Dict[str, Any] = {}
        if rag_context:
            extra_context["rag_context"] = rag_context
        if request.user_data_prompt:
            extra_context["user_prompt"] = request.user_data_prompt
        if request.market_data:
            extra_context["request_market_data"] = request.market_data


        # 3. LLM 서비스 호출
        llm_response = await vllm_service.get_trade_decision(
            # user_data_prompt=final_prompt,
            model_name=request.model_name,
            extra_context=extra_context or None
        )
        
        # 4. 최종 응답 구성
        return TradeDecisionResponse(
            status="success",
            rag_context_used=bool(rag_context and "failed" not in rag_context),
            trade_decision=llm_response,
            context_summary=context_summary
        )
        
    except Exception as e:
        logger.error(f"Trade decision process failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

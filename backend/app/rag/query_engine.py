import logging
from typing import Dict, List, Any, Optional
from .chroma_client import ChromaDBClient
from datetime import datetime

logger = logging.getLogger(__name__)

class RAGQueryEngine:
    def __init__(self):
        self.chroma_client = ChromaDBClient()
        
    def generate_market_context_query(self, market_data: Dict[str, Any]) -> str:
        """
        현재 시장 상황을 기반으로 RAG 쿼리 생성
        
        Args:
            market_data: {
                "rsi": 65.2,
                "fear_greed_index": 75,  # 탐욕
                "user_risk_profile": "aggressive",
                "current_position": "considering_buy",
                "market_volatility": "high",
                "btc_price": 60000,
                "eth_price": 3000
            }
        """
        volatility_desc = "높은 변동성" if market_data.get("market_volatility", "medium") == "high" else "낮은 변동성"
        risk_profile_desc = {
            "conservative": "보수적",
            "moderate": "중립적",
            "aggressive": "적극적"
        }.get(market_data.get("user_risk_profile", "moderate"), "중립적")
        
        position_desc = {
            "considering_buy": "매수 고려 중",
            "considering_sell": "매도 고려 중",
            "holding": "보유 중"
        }.get(market_data.get("current_position", "holding"), "보유 중")
        
        query = f"""
        현재 시장 상황:
        - RSI: {market_data.get('rsi', 50)}
        - 탐욕지수: {market_data.get('fear_greed_index', 50)}
        - 시장 변동성: {volatility_desc}
        - 사용자 성향: {risk_profile_desc}
        - 현재 포지션: {position_desc}
        - BTC 가격: ${market_data.get('btc_price', 0):,.2f}
        - ETH 가격: ${market_data.get('eth_price', 0):,.2f}
        
        이와 유사한 과거 시장 상황과 전문가 분석을 찾아주세요.
        """
        
        return query.strip()

    def get_balanced_context(self, market_data: Dict[str, Any], n_results_per_category: int = 3) -> Dict[str, List[Dict[str, Any]]]:
        """
        균형 잡힌 컨텍스트 검색 - 4가지 카테고리별로 검색
        
        Args:
            market_data: 시장 데이터
            n_results_per_category: 카테고리당 결과 수
            
        Returns:
            {
                "success_cases": [...],
                "failure_cases": [...],
                "expert_analysis": [...],
                "contrarian_views": [...]
            }
        """
        # 문서 수가 50개 미만이면 RAG를 실행하지 않음
        total_docs = self.chroma_client.count_documents()
        if total_docs < 50:
            logger.warning(f"Total documents ({total_docs}) is less than 50. Skipping RAG query.")
            return {
                "success_cases": [], "failure_cases": [],
                "expert_analysis": [], "contrarian_views": []
            }

        query = self.generate_market_context_query(market_data)
        market_condition = self._determine_market_condition(market_data)
        
        results = {
            "success_cases": [],
            "failure_cases": [],
            "expert_analysis": [],
            "contrarian_views": []
        }
        
        # 각 카테고리별로 검색
        categories = {
            "success_cases": "success_case",
            "failure_cases": "failure_case", 
            "expert_analysis": "expert_analysis",
            "contrarian_views": "contrarian_view"
        }
        
        for result_key, category in categories.items():
            try:
                category_results = self.chroma_client.query(
                    query_text=query,
                    n_results=n_results_per_category,
                    category_filter=category,
                    market_condition_filter=market_condition
                )
                results[result_key] = category_results
                logger.info(f"Found {len(category_results)} results for {category}")
            except Exception as e:
                logger.error(f"Error searching {category}: {str(e)}")
                results[result_key] = []
        
        return results

    def _determine_market_condition(self, market_data: Dict[str, Any]) -> str:
        """시장 조건 판단"""
        rsi = market_data.get("rsi", 50)
        fear_greed = market_data.get("fear_greed_index", 50)
        volatility = market_data.get("market_volatility", "medium")
        
        if rsi > 70 and fear_greed > 70:
            return "bull" if volatility == "low" else "volatile"
        elif rsi < 30 and fear_greed < 30:
            return "bear" if volatility == "low" else "volatile"
        else:
            return "sideways" if volatility == "low" else "volatile"

    def format_context_for_llm(self, context_results: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        LLM에 전달할 형식으로 컨텍스트 포맷팅
        """
        formatted_context = []
        
        # 성공 사례
        if context_results["success_cases"]:
            formatted_context.append("### 성공 사례 ###")
            for i, case in enumerate(context_results["success_cases"], 1):
                text = case["text"].strip()
                metadata = case["metadata"]
                similarity = case["similarity"]
                formatted_context.append(f"사례 {i} (유사도: {similarity:.2f}):")
                formatted_context.append(f"- 시장 조건: {metadata.get('market_condition', 'N/A')}")
                formatted_context.append(f"- 자산: {metadata.get('asset', 'N/A')}")
                formatted_context.append(f"- 설명: {text}")
                formatted_context.append("")
        
        # 실패 사례
        if context_results["failure_cases"]:
            formatted_context.append("### 실패 사례 ###")
            for i, case in enumerate(context_results["failure_cases"], 1):
                text = case["text"].strip()
                metadata = case["metadata"]
                similarity = case["similarity"]
                formatted_context.append(f"사례 {i} (유사도: {similarity:.2f}):")
                formatted_context.append(f"- 시장 조건: {metadata.get('market_condition', 'N/A')}")
                formatted_context.append(f"- 자산: {metadata.get('asset', 'N/A')}")
                formatted_context.append(f"- 설명: {text}")
                formatted_context.append("")
        
        # 전문가 분석
        if context_results["expert_analysis"]:
            formatted_context.append("### 전문가 분석 ###")
            for i, analysis in enumerate(context_results["expert_analysis"], 1):
                text = analysis["text"].strip()
                metadata = analysis["metadata"]
                similarity = analysis["similarity"]
                formatted_context.append(f"분석 {i} (유사도: {similarity:.2f}):")
                formatted_context.append(f"- 출처: {metadata.get('source', 'N/A')}")
                formatted_context.append(f"- 작성일: {metadata.get('date', 'N/A')}")
                formatted_context.append(f"- 내용: {text}")
                formatted_context.append("")
        
        # 상반되는 정보
        if context_results["contrarian_views"]:
            formatted_context.append("### 상반되는 의견 ###")
            for i, view in enumerate(context_results["contrarian_views"], 1):
                text = view["text"].strip()
                metadata = view["metadata"]
                similarity = view["similarity"]
                formatted_context.append(f"의견 {i} (유사도: {similarity:.2f}):")
                formatted_context.append(f"- 근거: {metadata.get('reasoning', 'N/A')}")
                formatted_context.append(f"- 내용: {text}")
                formatted_context.append("")
        
        return "\n".join(formatted_context)

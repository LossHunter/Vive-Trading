import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import numpy as np

from app.core.config import settings # config.py에서 설정 가져오기

logger = logging.getLogger(__name__)

class ChromaDBClient:
    def __init__(self):
        self.host = os.getenv("CHROMA_HOST", "chroma-db")
        self.port = int(os.getenv("CHROMA_PORT", "8000"))
        self.collection_name = os.getenv("CHROMA_COLLECTION_NAME", "trading_cases")
        
        # SentenceTransformer 임베딩 함수 사용
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        try:
            self.client = chromadb.HttpClient(
                host=self.host,
                port=self.port,
                settings=Settings(
                    chroma_client_auth_provider="chromadb.auth.token_authn.TokenAuthenticationClientProvider",
                    chroma_client_auth_credentials=settings.CHROMA_AUTH_CREDENTIALS # config.py에서 가져온 설정 사용
                )
            )
            logger.info(f"Connected to Chroma DB at {self.host}:{self.port}")
            
            # 컬렉션 생성 또는 가져오기
            self.collection = self._get_or_create_collection()
            
        except Exception as e:
            logger.error(f"Failed to connect to Chroma DB: {str(e)}")
            raise

    def _get_or_create_collection(self):
        """컬렉션 가져오기 또는 생성"""
        try:
            collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function
            )
            logger.info(f"Found existing collection: {self.collection_name}")
        except: # chromadb.exceptions.CollectionNotFoundError를 명시적으로 잡는 것이 더 좋음
            logger.info(f"Creating new collection: {self.collection_name}")
            collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}
            )
        return collection

    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        문서 추가
        
        Args:
            documents: [
                {
                    "id": "doc1",
                    "text": "문서 내용",
                    "metadata": {
                        "category": "success_case",
                        "market_condition": "bull",
                        "asset": "BTC",
                        "date": "2024-01-01",
                        "confidence": 0.95
                    }
                },
                ...
            ]
        """
        try:
            ids = [doc["id"] for doc in documents]
            texts = [doc["text"] for doc in documents]
            metadatas = [doc["metadata"] for doc in documents]
            
            self.collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            logger.info(f"Added {len(documents)} documents to collection")
            return True
        except Exception as e:
            logger.error(f"Error adding documents: {str(e)}")
            return False

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        category_filter: Optional[str] = None,
        market_condition_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        문서 쿼리
        
        Args:
            query_text: 검색 쿼리
            n_results: 반환할 결과 수
            category_filter: 카테고리 필터 (success_case, failure_case, expert_analysis, contrarian_view)
            market_condition_filter: 시장 조건 필터 (bull, bear, sideways, volatile)
        """
        try:
            # 필터 조건 구성
            where_clause = {}
            if category_filter:
                where_clause["category"] = category_filter
            if market_condition_filter:
                where_clause["market_condition"] = market_condition_filter
            
            where_clause = where_clause if where_clause else None
            
            # 쿼리 실행
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # 결과 포맷팅
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                    "similarity": 1 - (results["distances"][0][i] / 2)  # 코사인 유사도 변환
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error querying documents: {str(e)}")
            return []

    def get_category_distribution(self) -> Dict[str, int]:
        """카테고리별 문서 수 반환"""
        try:
            # 모든 문서 가져오기 (메타데이터만)
            results = self.collection.get(include=["metadatas"])
            
            category_count = {}
            for metadata in results["metadatas"]:
                category = metadata.get("category", "unknown")
                category_count[category] = category_count.get(category, 0) + 1
            
            return category_count
        except Exception as e:
            logger.error(f"Error getting category distribution: {str(e)}")
            return {}

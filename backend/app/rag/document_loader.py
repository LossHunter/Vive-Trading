import os
import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from .chroma_client import ChromaDBClient

logger = logging.getLogger(__name__)

class DocumentLoader:
    def __init__(self):
        self.chroma_client = ChromaDBClient()
        self.data_dir = "/app/rag-data"
        
    def load_all_documents(self):
        """모든 카테고리의 문서 로드"""
        try:
            categories = {
                "success_case": "success_cases",
                "failure_case": "failure_cases", 
                "expert_analysis": "expert_analysis",
                "contrarian_view": "contrarian_views"
            }
            
            for category, folder_name in categories.items():
                folder_path = os.path.join(self.data_dir, folder_name)
                if os.path.exists(folder_path):
                    self.load_category_documents(category, folder_path)
                else:
                    logger.warning(f"Folder not found: {folder_path}")
            
            # 카테고리 분포 확인
            distribution = self.chroma_client.get_category_distribution()
            logger.info(f"Document distribution: {distribution}")
            
        except Exception as e:
            logger.error(f"Error loading all documents: {str(e)}")
    
    def load_category_documents(self, category: str, folder_path: str):
        """특정 카테고리의 문서 로드"""
        try:
            documents = []
            files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
            
            for file_name in files:
                file_path = os.path.join(folder_path, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # 문서 ID 생성
                        doc_id = f"{category}_{os.path.splitext(file_name)[0]}_{int(datetime.now().timestamp())}"
                        
                        # 메타데이터 구성
                        metadata = {
                            "category": category,
                            "source_file": file_name,
                            "created_at": datetime.now().isoformat(),
                            **data.get("metadata", {})
                        }
                        
                        # 필수 필드 확인
                        if "text" not in data:
                            logger.warning(f"Missing 'text' field in {file_name}")
                            continue
                        
                        document = {
                            "id": doc_id,
                            "text": data["text"],
                            "metadata": metadata
                        }
                        documents.append(document)
                        
                except Exception as e:
                    logger.error(f"Error loading {file_name}: {str(e)}")
            
            if documents:
                success = self.chroma_client.add_documents(documents)
                if success:
                    logger.info(f"Successfully loaded {len(documents)} documents for category: {category}")
                else:
                    logger.error(f"Failed to load documents for category: {category}")
            
        except Exception as e:
            logger.error(f"Error loading category {category}: {str(e)}")

# 초기화 함수
def initialize_rag_data():
    """앱 시작 시 RAG 데이터 초기화"""
    try:
        loader = DocumentLoader()
        loader.load_all_documents()
        logger.info("RAG data initialization completed successfully")
    except Exception as e:
        logger.error(f"RAG data initialization failed: {str(e)}")

import logging
import threading
from fastapi import FastAPI, APIRouter
from app.api.endpoints import llm, market, trading
from app.rag.document_loader import initialize_rag_data

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="VT Backend API",
    description="API for vLLM, Upbit, and Trading functionalities with RAG",
    version="0.2.0",
)

@app.on_event("startup")
async def startup_event():
    """
    애플리케이션 시작 시 RAG 데이터 로딩을 백그라운드에서 수행합니다.
    """
    logger.info("Application startup: Starting RAG data initialization in a background thread.")
    try:
        init_thread = threading.Thread(target=initialize_rag_data)
        init_thread.daemon = True  # 메인 스레드 종료 시 함께 종료되도록 설정
        init_thread.start()
    except Exception as e:
        logger.error(f"Failed to start RAG data initialization thread: {str(e)}")

# 메인 API 라우터 생성
api_router = APIRouter()

# 기능별 라우터 포함
api_router.include_router(llm.router, prefix="/llm", tags=["LLM & RAG"])
api_router.include_router(market.router, prefix="/market", tags=["Market Data"])
api_router.include_router(trading.router, prefix="/trading", tags=["Trading"])

# FastAPI 앱에 메인 라우터 포함
app.include_router(api_router, prefix="/api")

# 루트 엔드포인트 (헬스 체크용)
@app.get("/")
async def root():
    return {"message": "VT Backend API is running"}
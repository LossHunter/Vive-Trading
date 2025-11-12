"""서버 / 헬스 체크 라우터"""

from fastapi import APIRouter

from app.core.config import ServerConfig
from app.db.database import test_connection
from app.services.frontend.connection_manager import manager

router = APIRouter()


@router.get("/", summary="루트 엔드포인트")
async def root():
    return {
        "message": "Upbit 데이터 수집 및 통신 API",
        "status": "running",
        "version": "1.0.0",
    }


@router.get("/api/health", summary="헬스 체크")
async def health_check():
    db_status = test_connection()
    return {
        "status": "healthy" if db_status else "unhealthy",
        "database": "connected" if db_status else "disconnected",
        "websocket_connections": len(manager.active_connections),
        "websocket_path": ServerConfig.WEBSOCKET_PATH,
    }

import json
import logging
from typing import Set
from fastapi import WebSocket


logger = logging.getLogger(__name__)

# WebSocket 연결 관리
class ConnectionManager:
    """WebSocket 연결 관리 클래스"""
    
    def __init__(self):
        """초기화: 활성 연결 세트 생성"""
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """WebSocket 연결 추가"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"✅ WebSocket 연결 추가 (총 {len(self.active_connections)}개)")
    
    def disconnect(self, websocket: WebSocket):
        """WebSocket 연결 제거"""
        self.active_connections.discard(websocket)
        logger.info(f"🔌 WebSocket 연결 제거 (총 {len(self.active_connections)}개)")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """특정 WebSocket에 메시지 전송"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"❌ 메시지 전송 실패: {e}")
    
    async def broadcast(self, message: str):
        """모든 연결된 WebSocket에 메시지 브로드캐스트"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"❌ 브로드캐스트 실패: {e}")
                disconnected.append(connection)
        
        # 연결이 끊어진 소켓 제거
        for connection in disconnected:
            self.disconnect(connection)

# 전역 연결 관리자
manager = ConnectionManager()
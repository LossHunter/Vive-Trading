"""
Upbit API 데이터 수집 모듈
Upbit 공개 API를 호출하여 실시간 시장 데이터를 수집합니다.
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from decimal import Decimal

from app.core.config import UpbitAPIConfig

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UpbitAPICollector:
    """
    Upbit API 데이터 수집 클래스
    HTTP 요청을 통해 Upbit API에서 데이터를 가져옵니다.
    """
    
    def __init__(self):
        """초기화: 세션 및 기본 설정"""
        self.base_url = UpbitAPIConfig.BASE_URL
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입: 세션 생성"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료: 세션 종료"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Upbit API에 HTTP GET 요청을 보내는 내부 메서드
        
        Args:
            endpoint: API 엔드포인트 경로
            params: 쿼리 파라미터 딕셔너리
        
        Returns:
            List[Dict]: API 응답 JSON 데이터 리스트
        
        Raises:
            Exception: API 요청 실패 시
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data if isinstance(data, list) else [data]
                else:
                    error_text = await response.text()
                    logger.error(f"❌ API 요청 실패: {response.status} - {error_text}")
                    return []
        except Exception as e:
            logger.error(f"❌ API 요청 중 오류 발생: {e}")
            return []
    
    async def get_markets(self) -> List[Dict]:
        """
        거래 가능한 모든 마켓 목록 조회
        Upbit에서 거래 가능한 모든 코인 마켓 정보를 가져옵니다.
        
        Returns:
            List[Dict]: 마켓 정보 리스트 (market, korean_name, english_name 포함)
        """
        logger.info("📊 마켓 목록 조회 중...")
        data = await self._make_request(UpbitAPIConfig.MARKETS_ENDPOINT)
        logger.info(f"✅ {len(data)}개 마켓 정보 수집 완료")
        return data
    
    async def get_ticker(self, markets: Optional[List[str]] = None) -> List[Dict]:
        """
        현재가(Ticker) 정보 조회
        지정된 마켓들의 현재가, 시가, 고가, 저가 등 실시간 가격 정보를 가져옵니다.
        
        Args:
            markets: 조회할 마켓 코드 리스트 (None이면 기본 마켓 사용)
        
        Returns:
            List[Dict]: 티커 정보 리스트
        """
        if markets is None:
            markets = UpbitAPIConfig.MAIN_MARKETS
        
        markets_str = ",".join(markets)
        params = {"markets": markets_str}
        
        # 정상적인 수집은 debug 레벨로 (로그가 너무 많아서)
        logger.debug(f"📈 티커 데이터 조회 중: {markets_str}")
        data = await self._make_request(UpbitAPIConfig.TICKER_ENDPOINT, params)
        logger.debug(f"✅ {len(data)}개 티커 데이터 수집 완료")
        return data
    
    async def get_candles_minute3(
        self, 
        market: str, 
        count: int = 200,
        to: Optional[str] = None
    ) -> List[Dict]:
        """
        3분봉 캔들 데이터 조회
        지정된 마켓의 3분 단위 캔들(시가, 고가, 저가, 종가) 데이터를 가져옵니다.
        
        Args:
            market: 마켓 코드 (예: "KRW-BTC")
            count: 조회할 캔들 개수 (최대 200)
            to: 조회 기준 시각 (ISO 8601 형식, None이면 최신 데이터)
        
        Returns:
            List[Dict]: 캔들 데이터 리스트
        """
        params = {"market": market, "count": count}
        if to:
            params["to"] = to
        
        logger.info(f"🕯️ 3분봉 캔들 데이터 조회 중: {market}")
        data = await self._make_request(UpbitAPIConfig.CANDLES_MINUTE3_ENDPOINT, params)
        logger.info(f"✅ {len(data)}개 3분봉 캔들 데이터 수집 완료")
        return data
    
    async def get_candles_day(
        self, 
        market: str, 
        count: int = 200,
        to: Optional[str] = None
    ) -> List[Dict]:
        """
        일봉 캔들 데이터 조회
        지정된 마켓의 일 단위 캔들 데이터를 가져옵니다.
        
        Args:
            market: 마켓 코드 (예: "KRW-BTC")
            count: 조회할 캔들 개수 (최대 200)
            to: 조회 기준 시각 (ISO 8601 형식, None이면 최신 데이터)
        
        Returns:
            List[Dict]: 일봉 캔들 데이터 리스트
        """
        params = {"market": market, "count": count}
        if to:
            params["to"] = to
        
        logger.info(f"📅 일봉 캔들 데이터 조회 중: {market}")
        data = await self._make_request(UpbitAPIConfig.CANDLES_DAY_ENDPOINT, params)
        logger.info(f"✅ {len(data)}개 일봉 캔들 데이터 수집 완료")
        return data
    
    async def get_trades(self, market: str, count: int = 100) -> List[Dict]:
        """
        최근 체결 내역 조회
        지정된 마켓의 최근 체결 거래 내역을 가져옵니다.
        
        Args:
            market: 마켓 코드 (예: "KRW-BTC")
            count: 조회할 체결 내역 개수 (최대 100)
        
        Returns:
            List[Dict]: 체결 내역 리스트
        """
        params = {"market": market, "count": count}
        
        # 정상적인 수집은 debug 레벨로 (로그가 너무 많아서)
        logger.debug(f"💱 체결 내역 조회 중: {market}")
        data = await self._make_request(UpbitAPIConfig.TRADES_ENDPOINT, params)
        logger.debug(f"✅ {len(data)}개 체결 내역 수집 완료")
        return data
    
    async def get_orderbook(self, markets: Optional[List[str]] = None) -> List[Dict]:
        """
        호가창(Orderbook) 정보 조회
        지정된 마켓들의 현재 호가창 정보를 가져옵니다.
        
        Args:
            markets: 조회할 마켓 코드 리스트 (None이면 기본 마켓 사용)
        
        Returns:
            List[Dict]: 호가창 정보 리스트
        """
        if markets is None:
            markets = UpbitAPIConfig.MAIN_MARKETS
        
        markets_str = ",".join(markets)
        params = {"markets": markets_str}
        
        # 정상적인 수집은 debug 레벨로 (로그가 너무 많아서)
        logger.debug(f"📖 호가창 데이터 조회 중: {markets_str}")
        data = await self._make_request(UpbitAPIConfig.ORDERBOOK_ENDPOINT, params)
        logger.debug(f"✅ {len(data)}개 호가창 데이터 수집 완료")
        return data


class UpbitWebSocketCollector:
    """
    Upbit WebSocket 데이터 수집 클래스
    WebSocket을 통해 실시간 데이터를 스트리밍으로 수신합니다.
    (현재는 HTTP API를 주로 사용하므로, 필요 시 확장 가능)
    """
    
    def __init__(self):
        """초기화: WebSocket URL 설정"""
        self.ws_url = UpbitAPIConfig.WEBSOCKET_URL
        self.websocket = None
    
    async def connect_ticker(self, markets: List[str], callback):
        """
        티커 데이터 WebSocket 연결 및 수신
        (향후 확장용 - 현재는 HTTP API 사용)
        
        Args:
            markets: 구독할 마켓 코드 리스트
            callback: 데이터 수신 시 호출할 콜백 함수
        """
        try:
            import websockets
            
            # WebSocket 연결
            async with websockets.connect(self.ws_url) as websocket:
                self.websocket = websocket
                
                # 구독 메시지 전송
                subscribe_message = [
                    {"ticket": "ticker-subscription"},
                    {
                        "type": "ticker",
                        "codes": markets
                    }
                ]
                await websocket.send(json.dumps(subscribe_message))
                logger.info(f"✅ WebSocket 연결 성공: {markets}")
                
                # 메시지 수신 루프
                async for message in websocket:
                    try:
                        # WebSocket 메시지는 바이너리 형식이므로 텍스트로 디코딩
                        if isinstance(message, bytes):
                            text = message.decode('utf-8')
                        else:
                            text = message
                        
                        data = json.loads(text)
                        
                        # 티커 타입 데이터만 처리
                        if data.get("type") == "ticker":
                            await callback(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ JSON 디코딩 오류: {e}")
                    except Exception as e:
                        logger.error(f"❌ 메시지 처리 오류: {e}")
        except ImportError:
            logger.warning("⚠️ websockets 패키지가 설치되지 않았습니다. HTTP API를 사용합니다.")
        except Exception as e:
            logger.error(f"❌ WebSocket 연결 오류: {e}")
            raise


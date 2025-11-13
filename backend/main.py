"""
FastAPI 메인 애플리케이션
프론트엔드와의 REST API 및 WebSocket 통신을 담당합니다.
"""

import asyncio
import json
import logging
import threading
from datetime import datetime
from typing import List, Dict, Set, Optional
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from pydantic import BaseModel

from app.api.endpoints import llm, market, trading
from app.rag.document_loader import initialize_rag_data
from app.core.config import ServerConfig, UpbitAPIConfig, DataCollectionConfig, IndicatorsConfig, WalletConfig
from app.db.database import get_db, init_db, test_connection, SessionLocal
from app.services.upbit_collector import UpbitAPICollector
from app.services.upbit_storage import UpbitDataStorage
from app.services.indicators_calculator import IndicatorsCalculator

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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

# 데이터 수집 태스크 관리
collection_tasks: List[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 생명주기 관리
    시작 시 데이터베이스 초기화 및 데이터 수집 시작
    종료 시 모든 태스크 정리
    """
    # 시작 시 실행
    logger.info("🚀 백엔드 서버 시작 중...")
    
    # 데이터베이스 연결 테스트
    if not test_connection():
        logger.error("❌ 데이터베이스 연결 실패. 서버를 종료합니다.")
        raise Exception("데이터베이스 연결 실패")
    
    # 데이터베이스 테이블 초기화
    init_db()
    
    # 데이터 수집 태스크 시작
    if DataCollectionConfig.ENABLE_TICKER:
        task = asyncio.create_task(collect_ticker_data_periodically())
        collection_tasks.append(task)
    
    if DataCollectionConfig.ENABLE_CANDLES:
        task = asyncio.create_task(collect_candle_data_periodically())
        collection_tasks.append(task)
    
    if DataCollectionConfig.ENABLE_TRADES:
        task = asyncio.create_task(collect_trades_data_periodically())
        collection_tasks.append(task)
    
    if DataCollectionConfig.ENABLE_ORDERBOOK:
        task = asyncio.create_task(collect_orderbook_data_periodically())
        collection_tasks.append(task)
    
    # 지갑 데이터 주기적 전송 시작
    task = asyncio.create_task(broadcast_wallet_data_periodically())
    collection_tasks.append(task)
    
    # 기술 지표 주기적 계산 시작 (일봉 데이터 기반)
    task = asyncio.create_task(calculate_indicators_periodically())
    collection_tasks.append(task)
    
    logger.info("✅ 백엔드 서버 시작 완료")
    
    yield
    
    # 종료 시 실행
    logger.info("🛑 백엔드 서버 종료 중...")
    
    # 모든 데이터 수집 태스크 취소
    for task in collection_tasks:
        task.cancel()
    
    # 태스크 완료 대기
    await asyncio.gather(*collection_tasks, return_exceptions=True)
    
    logger.info("✅ 백엔드 서버 종료 완료")


# FastAPI 애플리케이션 생성
app = FastAPI(
    title="Upbit 데이터 수집 및 통신 API",
    description="Upbit API 데이터를 수집하고 프론트엔드와 통신하는 백엔드 시스템",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 미들웨어 설정 (프론트엔드에서 API 호출 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ServerConfig.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== RAG 함수 ====================
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

# ==================== 데이터 수집 함수 ====================

async def collect_ticker_data_periodically():
    """
    티커 데이터 주기적 수집
    설정된 주기마다 티커 데이터를 수집하여 데이터베이스에 저장합니다.
    """
    collection_count = 0
    last_summary_time = datetime.utcnow()
    
    while True:
        try:
            await asyncio.sleep(DataCollectionConfig.TICKER_COLLECTION_INTERVAL)
            
            async with UpbitAPICollector() as collector:
                ticker_data = await collector.get_ticker()
                
                if ticker_data:
                    # 데이터베이스에 저장
                    db = SessionLocal()
                    try:
                        storage = UpbitDataStorage(db)
                        storage.save_ticker(ticker_data)
                        collection_count += 1
                    finally:
                        db.close()
                    
                    # 1분마다 요약 정보 출력
                    now = datetime.utcnow()
                    if (now - last_summary_time).total_seconds() >= 60:
                        logger.info(f"📊 티커 데이터 수집 통계: 지난 1분간 {collection_count}회 수집 완료")
                        collection_count = 0
                        last_summary_time = now
        except asyncio.CancelledError:
            logger.info("🛑 티커 데이터 수집 중지")
            break
        except Exception as e:
            logger.error(f"❌ 티커 데이터 수집 오류: {e}")
            await asyncio.sleep(5)  # 오류 발생 시 5초 대기 후 재시도


async def collect_candle_data_periodically():
    """
    캔들 데이터 주기적 수집
    3분봉 및 일봉 캔들 데이터를 주기적으로 수집하여 저장합니다.
    캔들 데이터 수집 완료 후 기술 지표 계산을 트리거합니다.
    """
    while True:
        try:
            await asyncio.sleep(DataCollectionConfig.CANDLE_COLLECTION_INTERVAL)
            
            async with UpbitAPICollector() as collector:
                db = SessionLocal()
                try:
                    storage = UpbitDataStorage(db)
                    
                    # 각 마켓별로 3분봉 데이터 수집
                    collected_markets = []
                    for market in UpbitAPIConfig.MAIN_MARKETS:
                        candles = await collector.get_candles_minute3(market, count=1)
                        if candles:
                            saved_count = storage.save_candles_minute3(candles, market)
                            if saved_count > 0:
                                collected_markets.append(market)
                    
                    # 캔들 데이터가 성공적으로 수집된 경우 기술 지표 계산 트리거
                    if collected_markets:
                        logger.debug(f"✅ 캔들 데이터 수집 완료: {len(collected_markets)}개 마켓")
                        # 이벤트를 통해 기술 지표 계산 함수에 알림 (비동기로 처리)
                        asyncio.create_task(calculate_indicators_after_candle_collection(collected_markets))
                finally:
                    db.close()
        except asyncio.CancelledError:
            logger.info("🛑 캔들 데이터 수집 중지")
            break
        except Exception as e:
            logger.error(f"❌ 캔들 데이터 수집 오류: {e}")
            await asyncio.sleep(60)  # 오류 발생 시 1분 대기 후 재시도


async def collect_trades_data_periodically():
    """
    체결 데이터 주기적 수집
    최근 체결 내역을 주기적으로 수집하여 저장합니다.
    """
    collection_count = 0
    last_summary_time = datetime.utcnow()
    
    while True:
        try:
            await asyncio.sleep(DataCollectionConfig.TRADES_COLLECTION_INTERVAL)
            
            async with UpbitAPICollector() as collector:
                db = SessionLocal()
                try:
                    storage = UpbitDataStorage(db)
                    
                    # 각 마켓별로 체결 데이터 수집
                    for market in UpbitAPIConfig.MAIN_MARKETS:
                        trades = await collector.get_trades(market, count=10)
                        if trades:
                            storage.save_trades(trades, market)
                            collection_count += 1
                finally:
                    db.close()
                
                # 1분마다 요약 정보 출력
                now = datetime.utcnow()
                if (now - last_summary_time).total_seconds() >= 60:
                    logger.info(f"💱 체결 데이터 수집 통계: 지난 1분간 {collection_count}회 수집 완료")
                    collection_count = 0
                    last_summary_time = now
        except asyncio.CancelledError:
            logger.info("🛑 체결 데이터 수집 중지")
            break
        except Exception as e:
            logger.error(f"❌ 체결 데이터 수집 오류: {e}")
            await asyncio.sleep(5)  # 오류 발생 시 5초 대기 후 재시도


async def collect_orderbook_data_periodically():
    """
    호가창 데이터 주기적 수집
    현재 호가창 정보를 주기적으로 수집하여 저장합니다.
    """
    collection_count = 0
    last_summary_time = datetime.utcnow()
    
    while True:
        try:
            await asyncio.sleep(DataCollectionConfig.ORDERBOOK_COLLECTION_INTERVAL)
            
            async with UpbitAPICollector() as collector:
                orderbook_data = await collector.get_orderbook()
                
                if orderbook_data:
                    # 데이터베이스에 저장
                    db = SessionLocal()
                    try:
                        storage = UpbitDataStorage(db)
                        storage.save_orderbook(orderbook_data)
                        collection_count += 1
                    finally:
                        db.close()
                
                # 1분마다 요약 정보 출력
                now = datetime.utcnow()
                if (now - last_summary_time).total_seconds() >= 60:
                    logger.info(f"📖 호가창 데이터 수집 통계: 지난 1분간 {collection_count}회 수집 완료")
                    collection_count = 0
                    last_summary_time = now
        except asyncio.CancelledError:
            logger.info("🛑 호가창 데이터 수집 중지")
            break
        except Exception as e:
            logger.error(f"❌ 호가창 데이터 수집 오류: {e}")
            await asyncio.sleep(5)  # 오류 발생 시 5초 대기 후 재시도


async def calculate_indicators_after_candle_collection(markets: List[str]):
    """
    캔들 데이터 수집 후 기술 지표 계산
    캔들 데이터가 성공적으로 수집된 후 RSI 및 모든 기술 지표를 계산합니다.
    
    Args:
        markets: 캔들 데이터가 수집된 마켓 리스트
    """
    try:
        # 약간의 지연을 두어 데이터베이스 커밋이 완료되도록 함
        await asyncio.sleep(1)
        
        db = SessionLocal()
        try:
            # RSI 일괄 계산
            rsi_results = IndicatorsCalculator.calculate_rsi_for_all_markets(
                db=db,
                markets=markets,
                period=IndicatorsConfig.RSI_PERIOD,
                use_day_candles=False  # 3분봉 데이터 사용
            )
            
            if rsi_results:
                logger.debug(f"✅ RSI 계산 완료: {len(rsi_results)}개 마켓")
            
            # 모든 기술 지표 일괄 계산
            indicators_results = IndicatorsCalculator.calculate_all_indicators_for_markets(
                db=db,
                markets=markets,
                use_day_candles=False  # 3분봉 데이터 사용
            )
            
            if indicators_results:
                logger.debug(f"✅ 통합 지표 계산 완료: {len(indicators_results)}개 마켓")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ 기술 지표 계산 오류: {e}")


async def calculate_indicators_periodically():
    """
    기술 지표 주기적 계산
    캔들 데이터 수집과 독립적으로 주기적으로 기술 지표를 계산합니다.
    (일봉 데이터 기반으로 계산)
    """
    while True:
        try:
            # 일봉 데이터 기반 계산은 더 긴 주기로 실행
            await asyncio.sleep(IndicatorsConfig.INDICATORS_CALCULATION_INTERVAL)
            
            db = SessionLocal()
            try:
                # 일봉 데이터 기반 RSI 계산
                rsi_results = IndicatorsCalculator.calculate_rsi_for_all_markets(
                    db=db,
                    markets=UpbitAPIConfig.MAIN_MARKETS,
                    period=IndicatorsConfig.RSI_PERIOD,
                    use_day_candles=True  # 일봉 데이터 사용
                )
                
                if rsi_results:
                    logger.info(f"✅ 일봉 기반 RSI 계산 완료: {len(rsi_results)}개 마켓")
                
                # 일봉 데이터 기반 모든 기술 지표 계산
                indicators_results = IndicatorsCalculator.calculate_all_indicators_for_markets(
                    db=db,
                    markets=UpbitAPIConfig.MAIN_MARKETS,
                    use_day_candles=True  # 일봉 데이터 사용
                )
                
                if indicators_results:
                    logger.info(f"✅ 일봉 기반 통합 지표 계산 완료: {len(indicators_results)}개 마켓")
            finally:
                db.close()
        
        except asyncio.CancelledError:
            logger.info("🛑 기술 지표 계산 중지")
            break
        except Exception as e:
            logger.error(f"❌ 기술 지표 계산 오류: {e}")
            await asyncio.sleep(60)  # 오류 발생 시 1분 대기 후 재시도


async def get_wallet_data(db: Session, target_date: Optional[datetime] = None) -> List[Dict]:
    """
    지갑 데이터 생성
    upbit_accounts 테이블에서 데이터를 조회하여 지갑 정보를 생성합니다.
    
    Args:
        db: 데이터베이스 세션
        target_date: 조회할 날짜 (None이면 현재 날짜)
    
    Returns:
        List[Dict]: 지갑 데이터 리스트 (4개 사용자)
    """
    from app.db.database import UpbitAccounts, UpbitTicker
    from sqlalchemy import desc
    from datetime import timedelta
    
    # 사용자 정보 (4개만, 하드코딩, 나중에 다른 테이블에서 가져올 예정)
    users = [
        {"userId": 1, "username": "GPT", "colors": "#3b82f6", "logo": "GPT_Logo.png", "why": "Time is a precious resource."},
        {"userId": 2, "username": "Gemini", "colors": "#22c55e", "logo": "Gemini_LOGO.png", "why": "Consistency is key."},
        {"userId": 3, "username": "Grok", "colors": "#f59e0b", "logo": "Grok_LOGO.png", "why": "Be fearless in pursuit of goals."},
        {"userId": 4, "username": "DeepSeek", "colors": "#ef4444", "logo": "DeepSeek_LOGO.png", "why": "Your potential is limitless."},
    ]
    
    # 조회할 날짜 설정
    if target_date is None:
        target_date = datetime.utcnow()
    
    # 날짜 문자열 (일 기준)
    date_str = target_date.strftime("%Y/%m/%d")
    
    # 해당 날짜의 시작과 끝 시간 계산
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    
    # 해당 날짜의 티커 가격 조회 (각 마켓별 해당 날짜의 최신 가격)
    ticker_prices = {}
    for market in UpbitAPIConfig.MAIN_MARKETS:
        ticker = db.query(UpbitTicker).filter(
            UpbitTicker.market == market,
            UpbitTicker.collected_at >= start_of_day,
            UpbitTicker.collected_at < end_of_day
        ).order_by(desc(UpbitTicker.collected_at)).first()
        
        # 해당 날짜에 데이터가 없으면 전체 최신 데이터 사용
        if not ticker:
            ticker = db.query(UpbitTicker).filter(
                UpbitTicker.market == market
            ).order_by(desc(UpbitTicker.collected_at)).first()
        
        if ticker and ticker.trade_price:
            # 마켓 코드에서 화폐 코드 추출 (예: KRW-BTC -> BTC)
            currency = market.split("-")[1] if "-" in market else market
            ticker_prices[currency] = float(ticker.trade_price)
    
    # 각 사용자별 지갑 데이터 생성
    wallet_data = []
    
    for user in users:
        # upbit_accounts에서 해당 날짜의 계정 정보 조회
        # account_id는 UUID 타입이므로 필터링하지 않고, 모든 계정을 조회한 후 사용자별로 매핑
        # 현재는 account_id가 없거나 NULL인 경우를 처리하기 위해 전체 조회
        accounts = db.query(UpbitAccounts).filter(
            UpbitAccounts.collected_at >= start_of_day,
            UpbitAccounts.collected_at < end_of_day
        ).order_by(desc(UpbitAccounts.collected_at)).all()
        
        # 해당 날짜에 데이터가 없으면 전체 최신 데이터 사용
        if not accounts:
            accounts = db.query(UpbitAccounts).order_by(desc(UpbitAccounts.collected_at)).all()
        
        # 코인 수량 초기화
        btc = 0.0
        eth = 0.0
        doge = 0.0
        sol = 0.0
        xrp = 0.0
        non = 0.0  # KRW 현금 잔액
        
        # 계정 정보에서 코인 수량 추출 (같은 currency가 여러 개면 가장 최신 것 사용)
        seen_currencies = set()
        for account in accounts:
            currency = account.currency.upper() if account.currency else ""
            if currency in seen_currencies:
                continue
            seen_currencies.add(currency)
            
            balance = float(account.balance) if account.balance else 0.0
            
            if currency == "BTC":
                btc = balance
            elif currency == "ETH":
                eth = balance
            elif currency == "DOGE":
                doge = balance
            elif currency == "SOL":
                sol = balance
            elif currency == "XRP":
                xrp = balance
            elif currency == "KRW":
                non = balance
        
        # 전체 잔액 계산 (코인 가치 + 현금)
        total = (
            (btc * ticker_prices.get("BTC", 0)) +
            (eth * ticker_prices.get("ETH", 0)) +
            (doge * ticker_prices.get("DOGE", 0)) +
            (sol * ticker_prices.get("SOL", 0)) +
            (xrp * ticker_prices.get("XRP", 0)) +
            non
        )
        
        wallet_data.append({
            "userId": user["userId"],
            "username": user["username"],
            "colors": user["colors"],
            "logo": user["logo"],
            "time": date_str,
            "why": user["why"],
            "btc": btc,
            "eth": eth,
            "doge": doge,
            "sol": sol,
            "xrp": xrp,
            "non": non,
            "total": total
        })
    
    return wallet_data


async def get_wallet_data_30days(db: Session) -> List[Dict]:
    """
    30일치 지갑 데이터 생성
    최근 30일간의 지갑 데이터를 생성합니다.
    
    Args:
        db: 데이터베이스 세션
    
    Returns:
        List[Dict]: 30일치 지갑 데이터 리스트
    """
    from datetime import timedelta
    
    all_wallet_data = []
    
    # 최근 30일 데이터 생성
    for days_ago in range(30):
        target_date = datetime.utcnow() - timedelta(days=days_ago)
        daily_data = await get_wallet_data(db, target_date)
        all_wallet_data.extend(daily_data)
    
    return all_wallet_data


async def broadcast_wallet_data_periodically():
    """
    지갑 데이터 주기적 전송
    WebSocket으로 지갑 데이터를 주기적으로 브로드캐스트합니다.
    """
    while True:
        try:
            await asyncio.sleep(WalletConfig.WALLET_BROADCAST_INTERVAL)
            
            db = SessionLocal()
            try:
                wallet_data = await get_wallet_data(db)
                
                # WebSocket으로 브로드캐스트
                await manager.broadcast(json.dumps({
                    "type": "wallet",
                    "data": wallet_data,
                    "timestamp": datetime.utcnow().isoformat()
                }))
                
                logger.debug(f"✅ 지갑 데이터 전송 완료 ({len(wallet_data)}명)")
            finally:
                db.close()
        
        except asyncio.CancelledError:
            logger.info("🛑 지갑 데이터 전송 중지")
            break
        except Exception as e:
            logger.error(f"❌ 지갑 데이터 전송 오류: {e}")
            await asyncio.sleep(60)  # 오류 발생 시 1분 대기 후 재시도


# ==================== REST API 엔드포인트 ====================

@app.get("/")
async def root():
    """루트 엔드포인트: 서버 상태 확인"""
    return {
        "message": "Upbit 데이터 수집 및 통신 API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    db_status = test_connection()
    return {
        "status": "healthy" if db_status else "unhealthy",
        "database": "connected" if db_status else "disconnected",
        "websocket_connections": len(manager.active_connections)
    }


@app.get("/api/ticker")
async def get_ticker(db: Session = Depends(get_db)):
    """
    최신 티커 데이터 조회
    데이터베이스에서 가장 최근의 티커 데이터를 가져옵니다.
    """
    from app.db.database import UpbitTicker
    from sqlalchemy import desc
    
    tickers = db.query(UpbitTicker).order_by(desc(UpbitTicker.collected_at)).limit(10).all()
    
    result = []
    for ticker in tickers:
        result.append({
            "market": ticker.market,
            "trade_price": float(ticker.trade_price) if ticker.trade_price else None,
            "opening_price": float(ticker.opening_price) if ticker.opening_price else None,
            "high_price": float(ticker.high_price) if ticker.high_price else None,
            "low_price": float(ticker.low_price) if ticker.low_price else None,
            "signed_change_rate": float(ticker.signed_change_rate) if ticker.signed_change_rate else None,
            "collected_at": ticker.collected_at.isoformat() if ticker.collected_at else None
        })
    
    return result


@app.get("/api/wallet")
async def get_wallet(db: Session = Depends(get_db)):
    """
    지갑 데이터 조회
    upbit_accounts 테이블에서 데이터를 조회하여 지갑 정보를 반환합니다.
    4개 사용자의 코인 보유량과 현금 잔액을 조회하고, 현재가를 기준으로 전체 잔액을 계산합니다.
    """
    try:
        wallet_data = await get_wallet_data(db)
        return wallet_data
    except Exception as e:
        logger.error(f"❌ 지갑 데이터 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"지갑 데이터 조회 중 오류 발생: {str(e)}")


@app.get("/api/data_stream")
async def get_data_stream():
    """
    데이터 스트림 엔드포인트
    프론트엔드에서 초기 데이터를 스트리밍으로 받기 위한 엔드포인트입니다.
    30일치 지갑 데이터를 포함하여 전송합니다.
    """
    from app.db.database import UpbitTicker, UpbitCandlesMinute3
    from sqlalchemy import desc
    
    async def generate():
        """스트리밍 데이터 생성기"""
        db = SessionLocal()
        try:
            # 30일치 지갑 데이터 조회
            wallet_data_30days = await get_wallet_data_30days(db)
            
            # 최신 티커 데이터 조회
            tickers = db.query(UpbitTicker).order_by(desc(UpbitTicker.collected_at)).limit(100).all()
            
            # 최신 캔들 데이터 조회
            candles = db.query(UpbitCandlesMinute3).order_by(desc(UpbitCandlesMinute3.collected_at)).limit(100).all()
            
            # 데이터를 JSON 형식으로 변환하여 스트리밍
            data_list = []
            
            # 30일치 지갑 데이터 추가
            for wallet in wallet_data_30days:
                data_list.append({
                    "type": "wallet",
                    "data": wallet
                })
            
            # 티커 데이터 추가
            for ticker in tickers:
                data_list.append({
                    "type": "ticker",
                    "market": ticker.market,
                    "trade_price": float(ticker.trade_price) if ticker.trade_price else None,
                    "collected_at": ticker.collected_at.isoformat() if ticker.collected_at else None
                })
            
            # 캔들 데이터 추가
            for candle in candles:
                data_list.append({
                    "type": "candle",
                    "market": candle.market,
                    "trade_price": float(candle.trade_price) if candle.trade_price else None,
                    "candle_date_time_utc": candle.candle_date_time_utc.isoformat() if candle.candle_date_time_utc else None
                })
            
            # JSON 라인으로 전송
            for data in data_list:
                yield json.dumps(data) + "\n"
        finally:
            db.close()
    
    return StreamingResponse(generate(), media_type="application/json")


# ==================== 과거 데이터 수집 API ====================

class HistoricalDataRequest(BaseModel):
    """과거 데이터 수집 요청 모델"""
    market: str  # 마켓 코드 (예: "KRW-BTC")
    data_type: str  # 데이터 타입: "candles_minute3" 또는 "candles_day"
    count: int = 200  # 가져올 데이터 개수 (최대 200)
    to: Optional[str] = None  # 시작 시각 (ISO 8601 형식, 예: "2024-01-01T00:00:00+00:00")


class HistoricalDataBatchRequest(BaseModel):
    """과거 데이터 일괄 수집 요청 모델"""
    markets: List[str]  # 마켓 코드 리스트
    data_type: str  # 데이터 타입: "candles_minute3" 또는 "candles_day"
    count: int = 200  # 가져올 데이터 개수 (최대 200)
    to: Optional[str] = None  # 시작 시각 (ISO 8601 형식)


@app.post("/api/collect/historical")
async def collect_historical_data(request: HistoricalDataRequest):
    """
    과거 데이터 수집 API
    사용자가 지정한 조건으로 과거 캔들 데이터를 수집하여 데이터베이스에 저장합니다.
    
    요청 예시:
    {
        "market": "KRW-BTC",
        "data_type": "candles_minute3",
        "count": 200,
        "to": "2024-01-01T00:00:00+00:00"
    }
    """
    try:
        async with UpbitAPICollector() as collector:
            db = SessionLocal()
            try:
                storage = UpbitDataStorage(db)
                
                if request.data_type == "candles_minute3":
                    # 3분봉 데이터 수집
                    candles = await collector.get_candles_minute3(
                        market=request.market,
                        count=request.count,
                        to=request.to
                    )
                    if candles:
                        saved_count = storage.save_candles_minute3(candles, request.market)
                        return {
                            "success": True,
                            "message": f"{request.market} 3분봉 데이터 수집 완료",
                            "collected": len(candles),
                            "saved": saved_count,
                            "market": request.market,
                            "data_type": request.data_type
                        }
                    else:
                        return {
                            "success": False,
                            "message": "데이터를 가져올 수 없습니다",
                            "market": request.market
                        }
                
                elif request.data_type == "candles_day":
                    # 일봉 데이터 수집
                    candles = await collector.get_candles_day(
                        market=request.market,
                        count=request.count,
                        to=request.to
                    )
                    if candles:
                        saved_count = storage.save_candles_day(candles, request.market)
                        return {
                            "success": True,
                            "message": f"{request.market} 일봉 데이터 수집 완료",
                            "collected": len(candles),
                            "saved": saved_count,
                            "market": request.market,
                            "data_type": request.data_type
                        }
                    else:
                        return {
                            "success": False,
                            "message": "데이터를 가져올 수 없습니다",
                            "market": request.market
                        }
                
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"지원하지 않는 데이터 타입: {request.data_type}. 'candles_minute3' 또는 'candles_day'를 사용하세요."
                    )
            finally:
                db.close()
    
    except Exception as e:
        logger.error(f"❌ 과거 데이터 수집 오류: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 수집 중 오류 발생: {str(e)}")


@app.post("/api/collect/historical/batch")
async def collect_historical_data_batch(request: HistoricalDataBatchRequest):
    """
    과거 데이터 일괄 수집 API
    여러 마켓의 과거 데이터를 한 번에 수집합니다.
    
    요청 예시:
    {
        "markets": ["KRW-BTC", "KRW-ETH", "KRW-DOGE"],
        "data_type": "candles_minute3",
        "count": 200,
        "to": "2024-01-01T00:00:00+00:00"
    }
    """
    results = []
    
    async with UpbitAPICollector() as collector:
        db = SessionLocal()
        try:
            storage = UpbitDataStorage(db)
            
            for market in request.markets:
                try:
                    if request.data_type == "candles_minute3":
                        candles = await collector.get_candles_minute3(
                            market=market,
                            count=request.count,
                            to=request.to
                        )
                        if candles:
                            saved_count = storage.save_candles_minute3(candles, market)
                            results.append({
                                "market": market,
                                "success": True,
                                "collected": len(candles),
                                "saved": saved_count
                            })
                        else:
                            results.append({
                                "market": market,
                                "success": False,
                                "message": "데이터를 가져올 수 없습니다"
                            })
                    
                    elif request.data_type == "candles_day":
                        candles = await collector.get_candles_day(
                            market=market,
                            count=request.count,
                            to=request.to
                        )
                        if candles:
                            saved_count = storage.save_candles_day(candles, market)
                            results.append({
                                "market": market,
                                "success": True,
                                "collected": len(candles),
                                "saved": saved_count
                            })
                        else:
                            results.append({
                                "market": market,
                                "success": False,
                                "message": "데이터를 가져올 수 없습니다"
                            })
                    
                    # API 요청 제한을 고려하여 약간의 지연
                    await asyncio.sleep(0.1)
                
                except Exception as e:
                    logger.error(f"❌ {market} 데이터 수집 오류: {e}")
                    results.append({
                        "market": market,
                        "success": False,
                        "message": str(e)
                    })
        finally:
            db.close()
    
    success_count = sum(1 for r in results if r.get("success", False))
    return {
        "success": True,
        "message": f"{len(request.markets)}개 마켓 중 {success_count}개 수집 완료",
        "total_markets": len(request.markets),
        "success_count": success_count,
        "results": results
    }


@app.post("/api/calculate/rsi")
async def calculate_rsi_endpoint(
    market: str = Body(...),
    period: int = Body(IndicatorsConfig.RSI_PERIOD),
    use_day_candles: bool = Body(True),
    db: Session = Depends(get_db)
):
    """
    RSI 계산 API
    지정한 마켓의 RSI를 계산하여 데이터베이스에 저장합니다.
    
    요청 본문 예시:
    {
        "market": "KRW-BTC",
        "period": 14,
        "use_day_candles": true
    }
    """
    try:
        result = IndicatorsCalculator.calculate_and_save_rsi(
            db=db,
            market=market,
            period=period,
            use_day_candles=use_day_candles
        )
        
        if result:
            return {
                "success": True,
                "message": f"{market} RSI 계산 완료",
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"{market} RSI 계산 실패: 데이터가 부족합니다"
            )
    
    except Exception as e:
        logger.error(f"❌ RSI 계산 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"RSI 계산 중 오류 발생: {str(e)}")


@app.post("/api/calculate/rsi/batch")
async def calculate_rsi_batch_endpoint(
    markets: List[str] = Body(...),
    period: int = Body(IndicatorsConfig.RSI_PERIOD),
    use_day_candles: bool = Body(True),
    db: Session = Depends(get_db)
):
    """
    RSI 일괄 계산 API
    여러 마켓의 RSI를 한 번에 계산합니다.
    
    요청 본문 예시:
    {
        "markets": ["KRW-BTC", "KRW-ETH", "KRW-DOGE"],
        "period": 14,
        "use_day_candles": true
    }
    """
    try:
        results = IndicatorsCalculator.calculate_rsi_for_all_markets(
            db=db,
            markets=markets,
            period=period,
            use_day_candles=use_day_candles
        )
        
        return {
            "success": True,
            "message": f"{len(markets)}개 마켓 중 {len(results)}개 RSI 계산 완료",
            "total_markets": len(markets),
            "success_count": len(results),
            "results": results
        }
    
    except Exception as e:
        logger.error(f"❌ RSI 일괄 계산 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"RSI 일괄 계산 중 오류 발생: {str(e)}")


@app.post("/api/calculate/indicators")
async def calculate_all_indicators_endpoint(
    market: str = Body(...),
    use_day_candles: bool = Body(True),
    db: Session = Depends(get_db)
):
    """
    모든 기술 지표 계산 API
    지정한 마켓의 모든 기술 지표(RSI, MACD, EMA, ATR, Bollinger Bands)를 계산하여 저장합니다.
    
    요청 본문 예시:
    {
        "market": "KRW-BTC",
        "use_day_candles": true
    }
    """
    try:
        result = IndicatorsCalculator.calculate_all_indicators(
            db=db,
            market=market,
            use_day_candles=use_day_candles
        )
        
        if result:
            return {
                "success": True,
                "message": f"{market} 모든 기술 지표 계산 완료",
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"{market} 기술 지표 계산 실패: 데이터가 부족합니다"
            )
    
    except Exception as e:
        logger.error(f"❌ 통합 지표 계산 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"기술 지표 계산 중 오류 발생: {str(e)}")


@app.post("/api/calculate/indicators/batch")
async def calculate_all_indicators_batch_endpoint(
    markets: List[str] = Body(...),
    use_day_candles: bool = Body(True),
    db: Session = Depends(get_db)
):
    """
    모든 기술 지표 일괄 계산 API
    여러 마켓의 모든 기술 지표를 한 번에 계산합니다.
    
    요청 본문 예시:
    {
        "markets": ["KRW-BTC", "KRW-ETH", "KRW-DOGE"],
        "use_day_candles": true
    }
    """
    try:
        results = IndicatorsCalculator.calculate_all_indicators_for_markets(
            db=db,
            markets=markets,
            use_day_candles=use_day_candles
        )
        
        return {
            "success": True,
            "message": f"{len(markets)}개 마켓 중 {len(results)}개 통합 지표 계산 완료",
            "total_markets": len(markets),
            "success_count": len(results),
            "results": results
        }
    
    except Exception as e:
        logger.error(f"❌ 통합 지표 일괄 계산 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"기술 지표 일괄 계산 중 오류 발생: {str(e)}")


# ==================== WebSocket 엔드포인트 ====================

@app.websocket(ServerConfig.WEBSOCKET_PATH)
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 엔드포인트
    프론트엔드와의 실시간 양방향 통신을 담당합니다.
    """
    await manager.connect(websocket)
    
    try:
        # 연결 확인 메시지 전송
        await manager.send_personal_message(
            json.dumps({
                "type": "connection",
                "message": "WebSocket 연결 성공",
                "timestamp": datetime.utcnow().isoformat()
            }),
            websocket
        )
        
        # 메시지 수신 루프
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                # 클라이언트 요청 처리
                if message_type == "ping":
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        websocket
                    )
                elif message_type == "subscribe":
                    # 구독 요청 처리 (필요 시 구현)
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "subscribed",
                            "message": "구독 완료",
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        websocket
                    )
            except json.JSONDecodeError:
                logger.warning(f"⚠️ 잘못된 JSON 형식: {data}")
            except Exception as e:
                logger.error(f"❌ 메시지 처리 오류: {e}")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("🔌 WebSocket 연결 종료")
    except Exception as e:
        logger.error(f"❌ WebSocket 오류: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    
    # 서버 실행
    uvicorn.run(
        "main:app",
        host=ServerConfig.HOST,
        port=ServerConfig.PORT,
        reload=True,  # 개발 모드: 코드 변경 시 자동 재시작
        log_level="info"
    )

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
from app.core.config import ServerConfig, UpbitAPIConfig, DataCollectionConfig, IndicatorsConfig, WalletConfig, OrderExecutionConfig
from app.db.database import get_db, init_db, test_connection, SessionLocal, LLMPromptData, LLMTradingSignal
from app.services.llm_prompt_generator import LLMPromptGenerator
from app.services.upbit_collector import UpbitAPICollector
from app.services.upbit_storage import UpbitDataStorage
from app.services.indicators_calculator import IndicatorsCalculator
from app.services.vllm_service import run_trade_decision_loop
from app.services.connection_manager import manager
from app.services.wallet_service import (
    get_wallet_data,
    get_wallet_data_30days,
    broadcast_wallet_data_periodically
)
from app.services.order_execution_service import execute_signal_orders
from app.services.data_collector_service import (
    collect_ticker_data_periodically,
    collect_candle_data_periodically,
    collect_trades_data_periodically,
    collect_orderbook_data_periodically
)
from app.services.indicator_service import (
    calculate_indicators_after_candle_collection,
    calculate_indicators_periodically
)
from app.services.vllm_model_registry import refresh_available_models
from sqlalchemy import desc

from app.services.trading_simulator import initialize_all_accounts


# 로깅 설정
logging.basicConfig( # 로그출력 형식
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 데이터 수집 태스크 관리
collection_tasks: List[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    refresh_available_models()
    """
    애플리케이션 생명주기 관리
    시작 시 데이터베이스 초기화 및 데이터 수집 시작
    종료 시 모든 태스크 정리
    """
    # 시작 시 실행
    logger.info("🚀 백엔드 서버 시작 중...")
    

    try:
        # DB 연결 테스트
        if not test_connection():
            logger.error("❌ 데이터베이스 연결 실패. 서버를 종료합니다.")
            raise RuntimeError("데이터베이스 연결 실패")

        # DB 초기화
        init_db()

        # 가상 거래 계좌 초기화 (최초 실행 시에만 생성됨)
        logger.info("🔍 가상 거래 계좌 확인 중...")
        try:
            db_for_init = SessionLocal()
            try:
                results = initialize_all_accounts(db_for_init)
                success_count = sum(1 for v in results.values() if v)
                logger.info(f"✅ 가상 거래 계좌 준비 완료 ({success_count}/{len(results)}개)")
            finally:
                db_for_init.close()
        except Exception as init_error:
            logger.warning(f"⚠️ 계좌 초기화 중 오류 (계속 진행): {init_error}")

        # RAG 데이터 초기화 (백그라운드 스레드에서 실행)
        logger.info("▶️ 백그라운드 태스크 시작: RAG 데이터 초기화")
        try:
            init_thread = threading.Thread(target=initialize_rag_data)
            init_thread.daemon = True
            init_thread.start()
        except Exception as e:
            logger.error(f"❌ RAG 데이터 초기화 스레드 시작 실패: {str(e)}")


    except Exception:
        # exception()을 사용해 스택 트레이스 남김 -> 어떤줄에서 오류났는지)
        logger.exception("❌ 서버 시작 중 치명적 오류 발생. 서버 기동을 중단합니다.")
        # FastAPI가 기동되지 않도록 예외 재발생
        raise


    # 3) 백그라운드 태스크 실행
    try:
        def start_task(coro, name: str):
            task = asyncio.create_task(coro, name=name)
            collection_tasks.append(task)
            logger.info(f"▶️ 백그라운드 태스크 시작: {name}")
            return task

        if DataCollectionConfig.ENABLE_TICKER:
            start_task(collect_ticker_data_periodically(), "collect_ticker_data")

        if DataCollectionConfig.ENABLE_CANDLES:
            start_task(collect_candle_data_periodically(), "collect_candle_data")

        if DataCollectionConfig.ENABLE_TRADES:
            start_task(collect_trades_data_periodically(), "collect_trades_data")

        if DataCollectionConfig.ENABLE_ORDERBOOK:
            start_task(collect_orderbook_data_periodically(), "collect_orderbook_data")

        start_task(broadcast_wallet_data_periodically(manager), "broadcast_wallet_data")
        start_task(calculate_indicators_periodically(), "calculate_indicators")

        # LLM 거래 의사결정 루프 시작 (60초 간격)
        start_task(run_trade_decision_loop(), "llm_trade_decision_loop")

        logger.info("✅ 백엔드 서버 시작 완료")

    except Exception:
        logger.exception("❌ 백그라운드 태스크 시작 중 오류 발생. 서버 기동을 중단합니다.")
        # 혹시 이미 시작된 태스크가 있으면 정리
        for task in collection_tasks:
            task.cancel()
        await asyncio.gather(*collection_tasks, return_exceptions=True)
        raise

    # 앱이 정상 기동된 상태
    try:
        yield
    finally:
        # 여기서 finally로 묶으면, 앱이 어떤 이유로든 내려갈 때 항상 호출됨
        logger.info("🛑 백엔드 서버 종료 중...")

        for task in collection_tasks:
            if not task.done():
                task.cancel()

        results = await asyncio.gather(*collection_tasks, return_exceptions=True)
        # 각 태스크 종료 결과 로깅
        for idx, result in enumerate(results):
            task = collection_tasks[idx]
            name = getattr(task, "get_name", lambda: f"task-{idx}")()
            if isinstance(result, asyncio.CancelledError):
                logger.info(f"✅ 태스크 정상 취소: {name}")
            elif isinstance(result, Exception):
                logger.error(f"⚠️ 태스크 종료 중 예외 발생 ({name}): {result}")
            else:
                logger.info(f"ℹ️ 태스크 정상 종료: {name}")

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

# 메인 API 라우터 생성
api_router = APIRouter()
# 기능별 라우터 포함
api_router.include_router(llm.router, prefix="/llm", tags=["LLM & RAG"])
api_router.include_router(market.router, prefix="/market", tags=["Market Data"])
api_router.include_router(trading.router, prefix="/trading", tags=["Trading"])

# FastAPI 앱에 메인 라우터 포함
app.include_router(api_router, prefix="/api")


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
async def get_wallet_endpoint(db: Session = Depends(get_db)):
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


# ==================== LLM 관련 API ====================
# LLM 프롬프트 생성 및 거래 신호 저장 관련 API

# --- LLM 프롬프트 생성 API ---

class PromptGenerationRequest(BaseModel):
    """프롬프트 생성 요청 모델"""
    trading_start_time: Optional[str] = None  # ISO 8601 형식 (예: "2024-01-01T00:00:00+00:00")


@app.post("/api/llm/generate-prompt")
async def generate_llm_prompt(
    request: PromptGenerationRequest = Body(None),
    db: Session = Depends(get_db)
):
    """
    LLM 프롬프트 생성 API
    기존 DB 데이터를 기반으로 LLM에게 보낼 프롬프트를 생성하고 저장합니다.
    
    요청 본문 예시:
    {
        "trading_start_time": "2024-01-01T00:00:00+00:00"  # 선택사항
    }
    """
    try:
        trading_start_time = None
        if request is not None and request.trading_start_time is not None:
            try:
                trading_start_time = datetime.fromisoformat(request.trading_start_time.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"⚠️ 거래 시작 시각 파싱 실패: {e}")
        
        generator = LLMPromptGenerator(db, trading_start_time)
        prompt_data = generator.generate_and_save()
        
        if prompt_data:
            return {
                "success": True,
                "message": "LLM 프롬프트 생성 완료",
                "data": {
                    "id": prompt_data.id,
                    "generated_at": prompt_data.generated_at.isoformat() if prompt_data.generated_at else None,
                    "trading_minutes": prompt_data.trading_minutes,
                    "prompt_text": prompt_data.prompt_text,
                    "market_data": prompt_data.market_data_json,
                    "account_data": prompt_data.account_data_json,
                    "indicator_config": prompt_data.indicator_config_json
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="프롬프트 생성 실패"
            )
    
    except Exception as e:
        logger.error(f"❌ LLM 프롬프트 생성 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"프롬프트 생성 중 오류 발생: {str(e)}")

@app.get("/api/llm/prompt/latest")
async def get_latest_prompt(db: Session = Depends(get_db)):
    """
    최신 LLM 프롬프트 데이터 조회 API
    가장 최근에 저장된 프롬프트 데이터를 조회합니다.
    """
    try:
        prompt_data = db.query(LLMPromptData).order_by(
            desc(LLMPromptData.generated_at)
        ).first()
        
        if prompt_data:
            return {
                "success": True,
                "data": {
                    "id": prompt_data.id,
                    "generated_at": prompt_data.generated_at.isoformat() if prompt_data.generated_at else None,
                    "trading_minutes": prompt_data.trading_minutes,
                    "prompt_text": prompt_data.prompt_text,  # None일 수 있음 (나중에 파싱하여 생성)
                    "market_data": prompt_data.market_data_json,
                    "account_data": prompt_data.account_data_json,
                    "indicator_config": prompt_data.indicator_config_json
                }
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="저장된 프롬프트 데이터가 없습니다"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 최신 프롬프트 조회 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"프롬프트 조회 중 오류 발생: {str(e)}")

@app.get("/api/llm/prompt/{prompt_id}")
async def get_prompt_by_id(prompt_id: int, db: Session = Depends(get_db)):
    """
    특정 ID의 LLM 프롬프트 데이터 조회 API
    """
    try:
        prompt_data = db.query(LLMPromptData).filter(
            LLMPromptData.id == prompt_id
        ).first()
        
        if prompt_data:
            return {
                "success": True,
                "data": {
                    "id": prompt_data.id,
                    "generated_at": prompt_data.generated_at.isoformat() if prompt_data.generated_at else None,
                    "trading_minutes": prompt_data.trading_minutes,
                    "prompt_text": prompt_data.prompt_text,  # None일 수 있음 (나중에 파싱하여 생성)
                    "market_data": prompt_data.market_data_json,
                    "account_data": prompt_data.account_data_json,
                    "indicator_config": prompt_data.indicator_config_json
                }
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"ID {prompt_id}의 프롬프트 데이터를 찾을 수 없습니다"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 프롬프트 조회 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"프롬프트 조회 중 오류 발생: {str(e)}")

@app.get("/api/llm/prompt/{prompt_id}/text")
async def get_prompt_text_by_id(prompt_id: int, db: Session = Depends(get_db)):
    """
    특정 ID의 LLM 프롬프트 텍스트 조회 API
    저장된 프롬프트 텍스트를 반환합니다. 없으면 생성하여 반환합니다.
    """
    try:
        prompt_data = db.query(LLMPromptData).filter(
            LLMPromptData.id == prompt_id
        ).first()
        
        if not prompt_data:
            raise HTTPException(
                status_code=404,
                detail=f"ID {prompt_id}의 프롬프트 데이터를 찾을 수 없습니다"
            )
        
        # 저장된 프롬프트 텍스트가 있으면 직접 반환
        if prompt_data.prompt_text:
            prompt_text = prompt_data.prompt_text
        else:
            # 프롬프트 텍스트가 없으면 생성 (하위 호환성)
            if not prompt_data.market_data_json or not prompt_data.account_data_json:
                raise HTTPException(
                    status_code=400,
                    detail="프롬프트 데이터가 불완전합니다"
                )
            
            prompt_text = LLMPromptGenerator.generate_prompt_text_from_data(
                market_data=prompt_data.market_data_json,
                account_data=prompt_data.account_data_json,
                trading_minutes=prompt_data.trading_minutes or 0
            )
        
        return {
            "success": True,
            "data": {
                "id": prompt_data.id,
                "trading_minutes": prompt_data.trading_minutes,
                "prompt_text": prompt_text
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 프롬프트 텍스트 조회 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"프롬프트 텍스트 조회 중 오류 발생: {str(e)}")

# --- LLM 거래 신호 저장 API ---

class LLMTradingSignalRequest(BaseModel):
    """LLM 거래 신호 저장 요청 모델"""
    prompt_id: int  # 프롬프트 ID
    stop_loss: Optional[float] = None
    signal: str  # buy_to_enter, sell_to_exit, hold 등
    leverage: Optional[float] = None
    risk_usd: Optional[float] = None
    profit_target: Optional[float] = None
    quantity: Optional[float] = None
    invalidation_condition: Optional[str] = None
    justification: Optional[str] = None
    confidence: Optional[float] = None
    coin: str  # BTC, ETH 등

@app.post("/api/llm/signal/save")
async def save_llm_trading_signal(
    request: LLMTradingSignalRequest,
    db: Session = Depends(get_db)
):
    """
    LLM 거래 신호 저장 API
    LLM이 생성한 거래 신호를 데이터베이스에 저장합니다.
    
    요청 본문 예시:
    {
        "prompt_id": 21,
        "stop_loss": 107200.0,
        "signal": "buy_to_enter",
        "leverage": 2,
        "risk_usd": 1000.0,
        "profit_target": 109000.0,
        "quantity": 0.0185,
        "invalidation_condition": "Price breaks below 107000...",
        "justification": "BTC shows strong bullish momentum...",
        "confidence": 0.75,
        "coin": "BTC"
    }
    """
    try:
        # 프롬프트 ID 유효성 검사
        prompt_data = db.query(LLMPromptData).filter(
            LLMPromptData.id == request.prompt_id
        ).first()
        
        if not prompt_data:
            raise HTTPException(
                status_code=404,
                detail=f"프롬프트 ID {request.prompt_id}를 찾을 수 없습니다"
            )
        
        # LLM 거래 신호 저장
        trading_signal = LLMTradingSignal(
            prompt_id=request.prompt_id,
            account_id=request.account_id,
            coin=request.coin,
            signal=request.signal,
            stop_loss=request.stop_loss,
            profit_target=request.profit_target,
            quantity=request.quantity,
            leverage=request.leverage,
            risk_usd=request.risk_usd,
            confidence=request.confidence,
            invalidation_condition=request.invalidation_condition,
            justification=request.justification
        )
        
        db.add(trading_signal)
        db.commit()
        db.refresh(trading_signal)
        
        logger.info(f"✅ LLM 거래 신호 저장 완료 (ID: {trading_signal.id}, 프롬프트 ID: {request.prompt_id}, 코인: {request.coin})")
        
        return {
            "success": True,
            "message": "LLM 거래 신호 저장 완료",
            "data": {
                "id": trading_signal.id,
                "prompt_id": trading_signal.prompt_id,
                "coin": trading_signal.coin,
                "signal": trading_signal.signal,
                "created_at": trading_signal.created_at.isoformat() if trading_signal.created_at else None
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ LLM 거래 신호 저장 오류: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"거래 신호 저장 중 오류 발생: {str(e)}")

@app.get("/api/llm/signal/{signal_id}")
async def get_llm_trading_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    특정 ID의 LLM 거래 신호 조회 API
    """
    try:
        signal = db.query(LLMTradingSignal).filter(
            LLMTradingSignal.id == signal_id
        ).first()
        
        if not signal:
            raise HTTPException(
                status_code=404,
                detail=f"ID {signal_id}의 거래 신호를 찾을 수 없습니다"
            )
        
        return {
            "success": True,
            "data": {
                "id": signal.id,
                "prompt_id": signal.prompt_id,
                "account_id": signal.account_id,
                "coin": signal.coin,
                "signal": signal.signal,
                "stop_loss": float(signal.stop_loss) if signal.stop_loss else None,
                "profit_target": float(signal.profit_target) if signal.profit_target else None,
                "quantity": float(signal.quantity) if signal.quantity else None,
                "leverage": float(signal.leverage) if signal.leverage else None,
                "risk_usd": float(signal.risk_usd) if signal.risk_usd else None,
                "confidence": float(signal.confidence) if signal.confidence else None,
                "invalidation_condition": signal.invalidation_condition,
                "justification": signal.justification,
                "created_at": signal.created_at.isoformat() if signal.created_at else None
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ LLM 거래 신호 조회 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"거래 신호 조회 중 오류 발생: {str(e)}")

@app.get("/api/llm/signal/prompt/{prompt_id}")
async def get_llm_trading_signals_by_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """
    특정 프롬프트 ID에 대한 모든 LLM 거래 신호 조회 API
    """
    try:
        signals = db.query(LLMTradingSignal).filter(
            LLMTradingSignal.prompt_id == prompt_id
        ).order_by(LLMTradingSignal.created_at.desc()).all()
        
        result = []
        for signal in signals:
            result.append({
                "id": signal.id,
                "prompt_id": signal.prompt_id,
                "account_id": signal.account_id,
                "coin": signal.coin,
                "signal": signal.signal,
                "stop_loss": float(signal.stop_loss) if signal.stop_loss else None,
                "profit_target": float(signal.profit_target) if signal.profit_target else None,
                "quantity": float(signal.quantity) if signal.quantity else None,
                "leverage": float(signal.leverage) if signal.leverage else None,
                "risk_usd": float(signal.risk_usd) if signal.risk_usd else None,
                "confidence": float(signal.confidence) if signal.confidence else None,
                "invalidation_condition": signal.invalidation_condition,
                "justification": signal.justification,
                "created_at": signal.created_at.isoformat() if signal.created_at else None
            })
        
        return {
            "success": True,
            "prompt_id": prompt_id,
            "count": len(result),
            "data": result
        }
    
    except Exception as e:
        logger.error(f"❌ LLM 거래 신호 조회 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"거래 신호 조회 중 오류 발생: {str(e)}")

# ============================================================================
# [임시 테스트용] 주문 체결 API
# ============================================================================
# ⚠️ 주의: 이 API는 임시 테스트용입니다.
# 나중에 실제 외부 시스템으로 교체할 때 이 엔드포인트를 제거하거나 비활성화할 수 있습니다.
# 비활성화 방법: config.py에서 OrderExecutionConfig.ENABLE_ORDER_EXECUTION = False 설정
# ============================================================================
@app.post("/api/order/execute")
async def execute_orders(
    prompt_id: Optional[int] = Body(None, description="프롬프트 ID (None이면 최신 signal만 체결)"),
    db: Session = Depends(get_db)
):
    """
    [임시 테스트용] 주문 체결 API
    저장된 LLM 거래 신호를 기반으로 가상의 주문을 체결하고 upbit_accounts를 업데이트합니다.
    
    ⚠️ 주의: 이 API는 임시 테스트용입니다.
    실제 외부 시스템으로 교체할 때 이 엔드포인트를 제거하거나 비활성화할 수 있습니다.
    
    Args:
        prompt_id: 프롬프트 ID (None이면 최신 signal만 체결)
    
    Returns:
        dict: 체결 결과 통계
    """
    # 주문 체결 기능이 비활성화되어 있으면 403 반환
    if not OrderExecutionConfig.ENABLE_ORDER_EXECUTION:
        raise HTTPException(
            status_code=403,
            detail="주문 체결 기능이 비활성화되어 있습니다. (임시 테스트용 기능)"
        )
    
    try:
        results = execute_signal_orders(db, prompt_id)
        return results
    except Exception as e:
        logger.error(f"❌ 주문 체결 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"주문 체결 중 오류 발생: {str(e)}")
    


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
